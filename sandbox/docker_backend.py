"""DockerBackend — container isolation for the single exec-path.

This module is the ONLY place in the OS permitted to import/use subprocess.
exec_path_audit.py enforces that. The argv is hardened by default: no network,
read-only root, dropped capabilities, no privilege escalation, resource limits.
"""

import os
import shutil
import subprocess  # the one allowed spawn import — confined to this file
import tempfile
from pathlib import Path
from typing import List

from .runner import RunRequest, RunResult, SandboxBackend

# The container runtime (colima/lima VM) only bind-mounts a fixed set of host
# roots into the VM — by default the user's HOME. A workdir OUTSIDE those roots
# mounts as an EMPTY directory, silently: the tool then "can't find" files that
# clearly exist on the host. We detect that and stage the workdir into a
# VM-visible location, run there, and copy results back. Keeps the OS portable
# regardless of where the project lives (e.g. an external /Volumes disk).
_VM_VISIBLE_ROOTS = (str(Path.home()),)
_STAGE_ROOT = Path.home() / ".hds" / "sandbox_stage"


class DockerBackend(SandboxBackend):
    name = "docker"
    isolated = True  # real container isolation

    def __init__(self, binary: str = "docker"):
        self.binary = binary

    def available(self) -> bool:
        if shutil.which(self.binary) is None:
            return False
        try:
            r = subprocess.run([self.binary, "info"],
                               capture_output=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    def build_argv(self, req: RunRequest) -> List[str]:
        """Construct the hardened `docker run` argv (pure; no spawn)."""
        mount = f"{req.workdir}:/work:{'rw' if req.writable else 'ro'}"
        argv = [
            self.binary, "run", "--rm",
            "--network", "bridge" if req.network else "none",
            "--read-only",                     # immutable root fs
            "--tmpfs", "/tmp",                 # scratch space only
            "-v", mount,
            "-w", "/work",
            "--memory", req.memory,
            "--cpus", req.cpus,
            "--pids-limit", str(req.pids),
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",               # no Linux capabilities
            req.image,
            req.tool, *req.args,
        ]
        return argv

    @staticmethod
    def _needs_stage(workdir: str) -> bool:
        """True if workdir is outside every VM-visible host root."""
        wd = str(Path(workdir).resolve())
        return not any(wd == r or wd.startswith(r + os.sep)
                       for r in _VM_VISIBLE_ROOTS)

    def run(self, req: RunRequest) -> RunResult:
        stage = None
        real_workdir = req.workdir
        if self._needs_stage(req.workdir):
            _STAGE_ROOT.mkdir(parents=True, exist_ok=True)
            stage = tempfile.mkdtemp(dir=_STAGE_ROOT)
            # mirror workdir contents into the VM-visible staging dir
            shutil.copytree(req.workdir, stage, dirs_exist_ok=True)
            req.workdir = stage

        argv = self.build_argv(req)
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=req.timeout)
            result = RunResult(code=r.returncode, stdout=r.stdout,
                               stderr=r.stderr, argv=argv)
        except subprocess.TimeoutExpired as e:
            result = RunResult(code=124, stdout=e.stdout or "",
                               stderr="sandbox timeout", timed_out=True, argv=argv)
        finally:
            if stage is not None:
                # copy back any writes the tool made, then drop the staging dir
                if req.writable:
                    try:
                        shutil.copytree(stage, real_workdir, dirs_exist_ok=True)
                    except Exception:
                        pass
                shutil.rmtree(stage, ignore_errors=True)
                req.workdir = real_workdir
        return result
