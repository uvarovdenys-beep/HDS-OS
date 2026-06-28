"""SandboxRunner — the single, audited execution point.

Contract is backend-agnostic; the production backend is containers (Docker/
Podman). The hardened argv is built and unit-tested without a daemon present, so
the security contract is provable even before a runtime is installed.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class RunRequest:
    """One sandboxed tool invocation (e.g. eslint over a workdir)."""
    tool: str                       # argv[0] inside the container
    args: List[str] = field(default_factory=list)
    workdir: str = "."              # host dir mounted at /work
    image: str = "alpine:3.20"      # toolchain image
    network: bool = False           # default-deny network (install steps opt in)
    writable: bool = True           # mount /work rw (False = read-only check)
    timeout: int = 30               # wall-clock seconds
    memory: str = "512m"
    cpus: str = "1.0"
    pids: int = 128


@dataclass
class RunResult:
    code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    argv: Optional[List[str]] = None  # the exact spawned argv (audit trail)


class SandboxBackend:
    """Interface a concrete sandbox (Docker, Podman, …) implements."""

    name = "abstract"

    def available(self) -> bool:
        raise NotImplementedError

    def build_argv(self, req: RunRequest) -> List[str]:
        raise NotImplementedError

    def run(self, req: RunRequest) -> RunResult:
        raise NotImplementedError


class SandboxRunner:
    """THE exec surface. Nothing else in the OS may spawn a process."""

    def __init__(self, backend: Optional[SandboxBackend] = None):
        if backend is None:
            backend = self._auto_backend()
        self.backend = backend

    @staticmethod
    def _auto_backend() -> "SandboxBackend":
        """Prefer real isolation (container); degrade to subprocess if absent."""
        from .docker_backend import DockerBackend
        docker = DockerBackend()
        if docker.available():
            return docker
        from .subprocess_backend import SubprocessBackend
        return SubprocessBackend()

    @property
    def isolated(self) -> bool:
        """True only if the active backend provides real isolation."""
        return getattr(self.backend, "isolated", True)

    def run(self, req: RunRequest) -> RunResult:
        # Resolve + confine the workdir to a real existing directory.
        wd = Path(req.workdir).resolve()
        if not wd.is_dir():
            raise ValueError(f"sandbox workdir does not exist: {wd}")
        req.workdir = str(wd)
        if not self.backend.available():
            raise RuntimeError(
                f"sandbox backend '{self.backend.name}' unavailable — no runtime "
                f"installed. A language is available only if its toolchain is.")
        return self.backend.run(req)
