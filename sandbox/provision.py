#!/usr/bin/env python3
"""sandbox/provision.py — auto-install the isolation runtime on demand.

Same philosophy as lang/_toolchain: a missing runtime is never a silent
degradation. When SandboxRunner falls back to SubprocessBackend it emits an
`isolation_missing` event with the exact command; running

    python3 -m sandbox.provision --install

performs a no-root, no-brew install into the user's home:
    limactl  (VM manager, static tarball)   → ~/.local
    colima   (docker-on-lima frontend)      → ~/.local/bin
    docker   (CLI only, static tarball)     → ~/.local/bin
then `colima start` boots the VM and `docker info` verifies.

This module MAY use subprocess: it is provisioning tooling that runs at the
operator's request, not part of the model-reachable execution path (see
exec_path_audit allowlist).
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

LOCAL = Path.home() / ".local"
BIN = LOCAL / "bin"

# Pinned versions — bump deliberately, not implicitly.
LIMA_VERSION = "2.1.4"
COLIMA_VERSION = "0.10.3"
DOCKER_CLI_VERSION = "29.6.1"

# The colima/lima auto-installer below is macOS-only. Do NOT hard-index the arch
# maps: on Windows platform.machine() is "AMD64" (not in the map) and would
# KeyError at IMPORT — which runner.py triggers on every degraded start. Use
# .get() so this module imports cleanly on every OS; install() guards for Darwin.
_IS_MAC = platform.system() == "Darwin"
# lima/colima assets use Go arch names (arm64); docker static uses uname (aarch64)
_GOARCH = {"arm64": "arm64", "x86_64": "x86_64"}.get(platform.machine(), "x86_64")
_ARCH = {"arm64": "aarch64", "x86_64": "x86_64"}.get(platform.machine(), "x86_64")

LIMA_URL = (f"https://github.com/lima-vm/lima/releases/download/"
            f"v{LIMA_VERSION}/lima-{LIMA_VERSION}-Darwin-{_GOARCH}.tar.gz")
COLIMA_URL = (f"https://github.com/abiosoft/colima/releases/download/"
              f"v{COLIMA_VERSION}/colima-Darwin-{_GOARCH}")
DOCKER_URL = (f"https://download.docker.com/mac/static/stable/"
              f"{_ARCH}/docker-{DOCKER_CLI_VERSION}.tgz")


def _have(tool):
    return shutil.which(tool) or (BIN / tool).exists()


def status():
    """Report what isolation pieces are present."""
    docker_ok = False
    if _have("docker"):
        try:
            docker_ok = subprocess.run(
                [str(shutil.which("docker") or BIN / "docker"), "info"],
                capture_output=True, timeout=15).returncode == 0
        except Exception:
            pass
    return {
        "docker_cli": bool(_have("docker")),
        "docker_daemon": docker_ok,
        "colima": bool(_have("colima")),
        "limactl": bool(_have("limactl")),
        "isolated": docker_ok,
    }


def offer():
    """One-time actionable hint when isolation is missing (event + log).
    Platform-aware: the auto-installer is macOS-only; elsewhere point at Docker.
    """
    s = status()
    if not _IS_MAC:
        remedy = ("Install Docker Desktop (Windows/Linux) so DockerBackend can "
                  "isolate; without it the sandbox runs degraded (subprocess).")
    elif s["colima"] and s["docker_cli"]:
        # installed but VM not running (typical after reboot)
        remedy = "Start: python3 -m sandbox.provision --ensure"
    else:
        remedy = "Install: python3 -m sandbox.provision --install"
    msg = f"execution isolation missing — running degraded (subprocess). {remedy}"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from events import emit
        emit("isolation_missing", message=msg, level="WARNING", install=remedy)
    except Exception:
        print(f"⚠️  {msg}", file=sys.stderr)


def _download(url, dest):
    """Fetch via system curl: python.org builds of Python often lack the macOS
    trust store (SSL: CERTIFICATE_VERIFY_FAILED); curl always has it."""
    print(f"  ↓ {url}")
    r = subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", str(dest), url],
                       timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"download failed ({r.returncode}): {url}")


def _install_lima():
    if _have("limactl"):
        print("  ✅ limactl present")
        return
    with tempfile.TemporaryDirectory() as td:
        tgz = Path(td) / "lima.tgz"
        _download(LIMA_URL, tgz)
        LOCAL.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tgz) as t:
            t.extractall(LOCAL)   # bin/limactl, share/lima/...
    print("  ✅ limactl installed")


def _install_colima():
    if _have("colima"):
        print("  ✅ colima present")
        return
    BIN.mkdir(parents=True, exist_ok=True)
    dest = BIN / "colima"
    _download(COLIMA_URL, dest)
    dest.chmod(0o755)
    print("  ✅ colima installed")


def _install_docker_cli():
    if _have("docker"):
        print("  ✅ docker CLI present")
        return
    with tempfile.TemporaryDirectory() as td:
        tgz = Path(td) / "docker.tgz"
        _download(DOCKER_URL, tgz)
        with tarfile.open(tgz) as t:
            t.extractall(td)      # docker/docker
        BIN.mkdir(parents=True, exist_ok=True)
        shutil.move(str(Path(td) / "docker" / "docker"), BIN / "docker")
    (BIN / "docker").chmod(0o755)
    print("  ✅ docker CLI installed")


def _start_vm():
    env = os.environ.copy()
    env["PATH"] = f"{BIN}:{env.get('PATH', '')}"
    print("  ⏳ colima start (first boot downloads a VM image — minutes)...")
    r = subprocess.run([str(BIN / "colima") if not shutil.which("colima")
                        else "colima", "start", "--cpu", "2", "--memory", "2"],
                       env=env, timeout=1200)
    if r.returncode != 0:
        raise RuntimeError("colima start failed")
    v = subprocess.run(["docker", "info"], env=env, capture_output=True,
                       timeout=30)
    if v.returncode != 0:
        raise RuntimeError(f"docker daemon not reachable: {v.stderr.decode()[:200]}")
    print("  ✅ docker daemon running (isolated=True)")


_PLIST = Path.home() / "Library/LaunchAgents/com.hds.colima.plist"


def _install_autostart():
    """LaunchAgent so the VM survives reboots (colima has no autostart of its
    own; without this, isolation silently drops to subprocess after restart)."""
    colima = shutil.which("colima") or str(BIN / "colima")
    _PLIST.parent.mkdir(parents=True, exist_ok=True)
    _PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.hds.colima</string>
  <key>ProgramArguments</key>
  <array><string>{colima}</string><string>start</string>
         <string>--cpu</string><string>2</string>
         <string>--memory</string><string>2</string></array>
  <key>RunAtLoad</key><true/>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>{BIN}:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>StandardOutPath</key><string>/tmp/hds_colima_autostart.log</string>
  <key>StandardErrorPath</key><string>/tmp/hds_colima_autostart.log</string>
</dict></plist>
""")
    subprocess.run(["launchctl", "load", "-w", str(_PLIST)],
                   capture_output=True, timeout=30)
    print(f"  ✅ autostart on login installed ({_PLIST.name})")


def ensure_running():
    """Start the VM if installed but stopped (e.g. after reboot). Returns
    True if the daemon is reachable afterwards."""
    if status()["isolated"]:
        return True
    if not (_have("colima") and _have("docker")):
        return False
    try:
        _start_vm()
        return True
    except Exception:
        return False


def install(start=True):
    if not _IS_MAC:
        print("This auto-installer (lima/colima) is macOS-only.\n"
              "On Windows/Linux install Docker (Docker Desktop or the docker\n"
              "engine); HDS's DockerBackend then isolates automatically. Without\n"
              "it the sandbox runs degraded (subprocess, isolated=False).")
        return
    print(f"HDS isolation install → {LOCAL} (no root, no brew)")
    _install_lima()
    _install_colima()
    _install_docker_cli()
    _install_autostart()
    if start:
        _start_vm()
    print("\nAdd to PATH if not present:  export PATH=\"$HOME/.local/bin:$PATH\"")


def main():
    if "--install" in sys.argv:
        install(start="--no-start" not in sys.argv)
    elif "--ensure" in sys.argv:
        ok = ensure_running()
        print("isolated:", ok)
        sys.exit(0 if ok else 1)
    else:
        print(json.dumps(status(), indent=2))
        s = status()
        if not s["isolated"]:
            if s["colima"] and s["docker_cli"]:
                print("\nInstalled but VM stopped — start: "
                      "python3 -m sandbox.provision --ensure", file=sys.stderr)
            else:
                print("\nInstall: python3 -m sandbox.provision --install",
                      file=sys.stderr)


if __name__ == "__main__":
    main()
