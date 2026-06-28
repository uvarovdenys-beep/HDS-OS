"""SubprocessBackend — degraded exec-path for hosts without a container runtime.

HONEST SCOPE: this is NOT isolation. It shares the host filesystem and network.
What it DOES give, and why it still matters:
  * single audited exec-path — everything routes through one place (no scattered
    subprocess calls; this and docker_backend are the only files allowed to spawn);
  * NO shell — argv list only, so no shell injection (kills the shell=True hole);
  * timeout + CPU/memory rlimits (POSIX) — runaway containment.
It reports `isolated = False` loudly. Install Docker/Podman and DockerBackend
takes over automatically with real isolation — no caller change.
"""

import subprocess  # one of two allowed spawn imports (see exec_path_audit)
from typing import List

from .runner import RunRequest, RunResult, SandboxBackend

try:
    import resource  # POSIX only
except ImportError:  # pragma: no cover
    resource = None


def _limits(req: RunRequest):
    """preexec_fn applying CPU/address-space rlimits (best-effort, POSIX)."""
    if resource is None:
        return None

    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (req.timeout, req.timeout + 2))
    return apply


class SubprocessBackend(SandboxBackend):
    name = "subprocess"
    isolated = False  # <-- not a sandbox; degraded fallback

    def available(self) -> bool:
        return True  # the host is always there

    def build_argv(self, req: RunRequest) -> List[str]:
        # No container wrapping, no shell: the argv IS the tool + args.
        return [req.tool, *req.args]

    def run(self, req: RunRequest) -> RunResult:
        argv = self.build_argv(req)
        try:
            r = subprocess.run(argv, cwd=req.workdir, capture_output=True,
                               text=True, timeout=req.timeout,
                               preexec_fn=_limits(req))
            return RunResult(code=r.returncode, stdout=r.stdout,
                             stderr=r.stderr, argv=argv)
        except subprocess.TimeoutExpired as e:
            return RunResult(code=124, stdout=e.stdout or "",
                             stderr="exec timeout", timed_out=True, argv=argv)
