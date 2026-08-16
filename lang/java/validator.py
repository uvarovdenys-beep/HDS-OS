"""Java validator: hygiene denylist + real parse via `javac`.

javac cannot use the generic check() helper: it enforces that a public class
lives in a file named after it, so a temp file called `check.java` would reject
perfectly valid code with "class Foo is public, should be declared in a file
named Foo.java". The filename is derived from the source instead.
"""
import re
import tempfile
from pathlib import Path

from .. import LangReject, register
from .._hygiene import deny_scan
from .._toolchain import _offer, resolve

_PAT = [
    ("Runtime.exec", re.compile(r"Runtime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*exec")),
    ("ProcessBuilder", re.compile(r"\bnew\s+ProcessBuilder\b")),
    ("reflection", re.compile(r"\bClass\s*\.\s*forName\b|\bsetAccessible\s*\(")),
    ("ScriptEngine", re.compile(r"\bScriptEngineManager\b")),
    ("File.delete", re.compile(r"\.delete\s*\(\s*\)")),
]

_PUBLIC_CLASS = re.compile(r"\bpublic\s+(?:final\s+|abstract\s+)?"
                           r"(?:class|interface|enum|record)\s+(\w+)")


@register(".java", kind="compiled")
def validate_java(content, path):
    deny_scan(content, path, _PAT)

    javac = resolve("javac")
    if javac is None:
        _offer("javac")
        return                      # hygiene-only, honestly degraded

    match = _PUBLIC_CLASS.search(content)
    name = match.group(1) if match else "Check"

    from sandbox.runner import RunRequest, SandboxRunner
    from sandbox.subprocess_backend import SubprocessBackend
    with tempfile.TemporaryDirectory() as td:
        Path(td, f"{name}.java").write_text(content, encoding="utf-8")
        res = SandboxRunner(backend=SubprocessBackend()).run(RunRequest(
            tool=javac, args=["-d", td, f"{name}.java"], workdir=td, timeout=90))
    if res.code == 0:
        return

    out = (res.stderr or "") + (res.stdout or "")
    # macOS ships a javac STUB that exists on PATH and only tells you to install
    # a JDK. Treated as a real compiler it rejects perfectly valid Java — a
    # false denial, which is worse than no check at all. A stub is an ABSENT
    # toolchain, so degrade to hygiene and offer the install.
    if ("java.com" in out or "Unable to locate a Java Runtime" in out
            or "No Java runtime present" in out):
        _offer("javac")
        return

    tail = (out.strip().splitlines() or ["failed"])[-1]
    raise LangReject(f"{Path(path).name} failed javac: {tail[:160]}")
