"""C# validator: hygiene denylist + real build via dotnet build (Roslyn).

A throwaway library project compiles the file: real syntax+reference checking,
no binary is run. Building/executing C# products stays gated (compiled kind).
Falls back to hygiene-only if dotnet is absent.
"""
import re
import sys
import tempfile
from pathlib import Path

from .. import register, LangReject
from .._hygiene import deny_scan
from .._toolchain import resolve

_CORE = Path(__file__).resolve().parents[2]
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

_PAT = [
    ("Process.Start", re.compile(r"Process\s*\.\s*Start")),
    ("DllImport", re.compile(r"\bDllImport\b")),
    ("Assembly.Load", re.compile(r"Assembly\s*\.\s*Load")),
    ("unsafe", re.compile(r"\bunsafe\b")),
]

_CSPROJ = (
    '<Project Sdk="Microsoft.NET.Sdk">\n'
    '  <PropertyGroup><OutputType>Library</OutputType>'
    '<TargetFramework>net10.0</TargetFramework>'
    '<Nullable>disable</Nullable></PropertyGroup>\n</Project>\n'
)


@register(".cs", kind="compiled")
def validate_cs(content, path):
    deny_scan(content, path, _PAT)
    dotnet = resolve("dotnet")
    if dotnet is None:
        return  # toolchain absent -> hygiene only (honest degradation)
    from sandbox.runner import SandboxRunner, RunRequest
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "p.csproj").write_text(_CSPROJ, encoding="utf-8")
        (Path(td) / "Program.cs").write_text(content, encoding="utf-8")
        res = SandboxRunner().run(RunRequest(
            tool=dotnet, args=["build", "p.csproj", "-nologo", "-clp:ErrorsOnly"],
            workdir=td, timeout=120))
        if res.code != 0:
            errs = [ln for ln in (res.stdout or "").splitlines()
                    if "error" in ln.lower()]
            tail = errs[0].strip()[:160] if errs else "build failed"
            raise LangReject(f"{Path(path).name} failed dotnet build: {tail}")
