"""DockerBackend workdir staging: workdirs outside VM-visible roots must not
silently mount empty. Requires a live Docker daemon; skips otherwise."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_needs_stage_logic():
    from sandbox.docker_backend import DockerBackend, _VM_VISIBLE_ROOTS
    home = _VM_VISIBLE_ROOTS[0]
    assert DockerBackend._needs_stage("/Volumes/External/proj") is True
    assert DockerBackend._needs_stage(os.path.join(home, "proj")) is False


def test_staged_run_sees_files():
    """A file in an out-of-home workdir must be visible inside the container."""
    from sandbox.runner import SandboxRunner, RunRequest
    from sandbox.docker_backend import DockerBackend
    if not DockerBackend().available():
        return  # no daemon — isolation path not exercised
    r = SandboxRunner()
    if not r.isolated:
        return
    # Only meaningful when the repo actually lives outside HOME:
    here = str(Path.cwd().resolve())
    if not DockerBackend._needs_stage(here):
        return
    with tempfile.TemporaryDirectory(dir=here) as td:
        (Path(td) / "marker.txt").write_text("staged-ok\n")
        res = r.run(RunRequest(tool="cat", args=["marker.txt"], workdir=td,
                               image="alpine:3.20", timeout=60))
        assert res.code == 0, res.stderr
        assert "staged-ok" in res.stdout


def test_staged_writes_copied_back():
    from sandbox.runner import SandboxRunner, RunRequest
    from sandbox.docker_backend import DockerBackend
    if not DockerBackend().available() or not SandboxRunner().isolated:
        return
    here = str(Path.cwd().resolve())
    if not DockerBackend._needs_stage(here):
        return
    with tempfile.TemporaryDirectory(dir=here) as td:
        res = SandboxRunner().run(RunRequest(
            tool="sh", args=["-c", "echo produced > out.txt"], workdir=td,
            image="alpine:3.20", writable=True, timeout=60))
        assert res.code == 0, res.stderr
        assert (Path(td) / "out.txt").read_text().strip() == "produced"
