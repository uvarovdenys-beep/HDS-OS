"""Toolchain-backed validation via the single exec-path (SandboxRunner).

A language is "finished" when its real toolchain validates it here, instead of a
hand-written regex. Syntax-check tools (node --check, clang++ -fsyntax-only) do
NOT execute the code — only parse it — so they are safe even on the degraded
(non-isolated) backend. If the tool is absent, returns False so the caller can
fall back to interim hygiene (honest degradation, never a silent pass).
"""
import shutil
import sys
import tempfile
from pathlib import Path

from . import LangReject

_CORE = Path(__file__).resolve().parents[1]
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

# User-prefix install locations searched beyond PATH (no-root toolchains).
_EXTRA_BIN = [
    Path.home() / ".npm-global" / "bin",   # npm --prefix ~/.npm-global
    Path.home() / ".dotnet",               # dotnet-install.sh
    Path.home() / ".dotnet" / "tools",
    Path.home() / ".local" / "bin",        # static binaries (e.g. php)
]


# Install commands to UPGRADE a missing toolchain (the auto-offer, no-root where
# possible). When a language is used but its tool is absent, we surface this
# instead of silently degrading to hygiene.
INSTALL = {
    "node":    "install Node.js — https://nodejs.org (provides node/npm)",
    "tsc":     "npm install -g typescript --prefix ~/.npm-global",
    "clang++": "xcode-select --install   (macOS)  |  apt install clang  (linux)",
    "dotnet":  "curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- "
               "--channel LTS --install-dir ~/.dotnet",
    "php":     "download a static php-cli into ~/.local/bin — https://dl.static-php.dev",
}

_offered = set()


def _offer(tool):
    """Surface a one-time, actionable install hint when a toolchain is missing.

    Non-blocking: the write still proceeds under hygiene. This just makes the
    degradation visible and tells the operator exactly how to upgrade.
    """
    if tool in _offered:
        return
    _offered.add(tool)
    hint = INSTALL.get(tool, f"install '{tool}' and put it on PATH")
    try:
        from events import emit
        emit("toolchain_missing", level="WARNING",
             message=f"'{tool}' not installed — hygiene-only validation. "
                     f"For full validation: {hint}")
    except Exception:
        pass


def status():
    """Per-tool availability + install command (onboarding / `--status`)."""
    return [{"tool": t, "present": resolve(t) is not None, "install": cmd}
            for t, cmd in INSTALL.items()]


def missing():
    """Tools that are declared but not installed (with their install command)."""
    return [r for r in status() if not r["present"]]


def resolve(tool):
    """Full path to a tool from PATH or known user-prefix dirs, else None."""
    found = shutil.which(tool)
    if found:
        return found
    for d in _EXTRA_BIN:
        cand = d / tool
        if cand.exists():
            return str(cand)
    return None


def check(tool_argv, content, path, *, suffix, label):
    """Run `tool_argv + tmpfile` over content. Raise LangReject on non-zero.

    tool_argv: e.g. ["node", "--check"] or ["clang++", "-fsyntax-only", "-x", "c++"]
    Returns True if validated, False if the tool is not installed (and offers
    the install command via the event bus, once per tool).
    """
    resolved = resolve(tool_argv[0])
    if resolved is None:
        _offer(tool_argv[0])
        return False
    tool_argv = [resolved, *tool_argv[1:]]
    # Syntax checks run the HOST toolchain (resolved above) with fixed argv
    # over a temp copy — a parse, not an execution of the artifact. Pin the
    # SubprocessBackend explicitly: auto-selection would pick Docker when
    # available and look for the host binary inside the container (absent ->
    # every valid file DENIED). Containers stay the backend for RUNNING
    # artifacts (SandboxRunner default), not for parsing them.
    from sandbox.runner import SandboxRunner, RunRequest
    from sandbox.subprocess_backend import SubprocessBackend
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / ("check" + suffix)
        f.write_text(content, encoding="utf-8")
        argv = tool_argv + [f.name]
        res = SandboxRunner(backend=SubprocessBackend()).run(RunRequest(
            tool=argv[0], args=argv[1:], workdir=td, timeout=30))
        if res.code != 0:
            msg = (res.stderr or res.stdout or "").strip().splitlines()
            tail = msg[-1][:160] if msg else "non-zero exit"
            raise LangReject(f"{Path(path).name} failed {label}: {tail}")
    return True


if __name__ == "__main__":
    # Toolchain onboarding report: what's present, what to install for the rest.
    rows = status()
    print("HDS toolchain status (full validation needs these; else hygiene-only)\n")
    for r in rows:
        if r["present"]:
            print(f"  ✅ {r['tool']:8} present")
        else:
            print(f"  ⬇️  {r['tool']:8} MISSING → {r['install']}")
    miss = missing()
    print(f"\n{len(rows) - len(miss)}/{len(rows)} toolchains present.", end=" ")
    print("All present." if not miss else f"{len(miss)} to install for full coverage.")
