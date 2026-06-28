"""DockerBackend — container isolation for the single exec-path.

This module is the ONLY place in the OS permitted to import/use subprocess.
exec_path_audit.py enforces that. The argv is hardened by default: no network,
read-only root, dropped capabilities, no privilege escalation, resource limits.
"""

import shutil
import subprocess  # the one allowed spawn import — confined to this file
from typing import List

from .runner import RunRequest, RunResult, SandboxBackend


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

    def run(self, req: RunRequest) -> RunResult:
        argv = self.build_argv(req)
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=req.timeout)
            return RunResult(code=r.returncode, stdout=r.stdout,
                             stderr=r.stderr, argv=argv)
        except subprocess.TimeoutExpired as e:
            return RunResult(code=124, stdout=e.stdout or "",
                             stderr="sandbox timeout", timed_out=True, argv=argv)
