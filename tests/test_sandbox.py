"""Sandbox runner: hardened-argv contract is provable without a container daemon."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sandbox.runner import RunRequest, RunResult, SandboxRunner, SandboxBackend
from sandbox.docker_backend import DockerBackend


def test_argv_is_hardened_by_default():
    argv = DockerBackend().build_argv(RunRequest(tool="eslint", args=["."],
                                                 workdir="/tmp", image="node:20"))
    s = " ".join(argv)
    assert "--network none" in s            # default-deny network
    assert "--read-only" in s               # immutable root
    assert "--cap-drop ALL" in s            # no capabilities
    assert "no-new-privileges" in s         # no privilege escalation
    assert "--pids-limit 128" in s
    assert argv[-2:] == ["eslint", "."]     # tool + args last
    assert ":/work:rw" in s


def test_network_and_readonly_toggles():
    a = DockerBackend().build_argv(RunRequest(tool="t", workdir="/tmp",
                                              network=True, writable=False))
    s = " ".join(a)
    assert "--network bridge" in s
    assert ":/work:ro" in s


def test_single_exec_path_runs_through_runner():
    # A fake backend proves the runner contract without docker installed.
    class Fake(SandboxBackend):
        name = "fake"
        def available(self):
            return True
        def run(self, req):
            return RunResult(code=0, stdout="ok", stderr="", argv=["fake"])

    out = SandboxRunner(backend=Fake()).run(RunRequest(tool="x", workdir="/tmp"))
    assert out.code == 0 and out.stdout == "ok"
