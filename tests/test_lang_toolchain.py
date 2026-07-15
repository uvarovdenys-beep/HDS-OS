"""Toolchain-backed language validation — each test auto-skips if its tool absent.

Real parsers/compilers via SandboxRunner reject broken code and accept valid;
hygiene fires regardless of toolchain.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scribe
from lang._toolchain import resolve


def _verdict(path, content):
    try:
        scribe.execute({"op": "write", "path": path, "content": content}, "l")
        return "ALLOW"
    except scribe.ScribeError:
        return "DENY"


def _need(tool):
    return pytest.mark.skipif(resolve(tool) is None, reason=f"{tool} not installed")


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for p in Path("storage").glob("t_*"):
        p.unlink(missing_ok=True)


@_need("node")
def test_js_node_check():
    assert _verdict("storage/t_ok.js", "function f(){ return 1; }\n") == "ALLOW"
    assert _verdict("storage/t_bad.js", "function f(){ return 1+ }\n") == "DENY"


@_need("tsc")
def test_ts_tsc_check():
    assert _verdict("storage/t_ok.ts", "const x: number = 1 + 2;\n") == "ALLOW"
    assert _verdict("storage/t_bad.ts", "const x: number = 1 +;\n") == "DENY"


@_need("clang++")
def test_cpp_clang_syntax():
    assert _verdict("storage/t_ok.cpp", "int f(){ return 1; }\n") == "ALLOW"
    assert _verdict("storage/t_bad.cpp", "int f(){ return 1+ }\n") == "DENY"


@_need("dotnet")
def test_cs_dotnet_build():
    assert _verdict("storage/t_Ok.cs",
                    "public class C { public int F(){ return 1; } }\n") == "ALLOW"
    assert _verdict("storage/t_Bad.cs",
                    "public class C { public int F(){ return 1+ } }\n") == "DENY"


@_need("php")
def test_php_lint():
    assert _verdict("storage/t_ok.php", "<?php function f($a){ return $a + 1; }\n") == "ALLOW"
    assert _verdict("storage/t_bad.php", "<?php function f($a){ return $a + ; }\n") == "DENY"


def test_hygiene_fires_without_toolchain():
    assert _verdict("storage/t_eval.js", 'eval("1");\n') == "DENY"


def test_toolchain_status_and_missing():
    from lang import _toolchain
    rows = _toolchain.status()
    assert {r["tool"] for r in rows} >= {"node", "tsc", "clang++", "dotnet", "php"}
    assert all(r["install"] for r in rows)                # every tool has a hint
    assert all(not r["present"] for r in _toolchain.missing())


def test_offer_on_missing_tool():
    from pathlib import Path
    from lang import _toolchain
    _toolchain._offered.discard("nope_tool_xyz")
    # absent tool → degrade (False) AND record the one-time offer (not silent)
    out = _toolchain.check(["nope_tool_xyz"], "x", Path("t.js"),
                           suffix=".js", label="bogus")
    assert out is False
    assert "nope_tool_xyz" in _toolchain._offered


def test_ts_ignores_missing_ambient_but_catches_real_errors():
    """Dogfooding fix: a lone .ts referencing node globals (Buffer,
    child_process) PASSES — @types supply them in the real project — while
    genuine errors (implicit any) still fail."""
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    import lang
    from lang import LangReject
    from lang._toolchain import resolve
    if resolve("tsc") is None:
        return  # no tsc → validator degrades to hygiene, nothing to assert
    v = lang.get_validator(".ts")
    ok = ('import * as cp from "child_process";\n'
          "export class C { p?: cp.ChildProcess; "
          "b(s: string): Buffer { return Buffer.from(s); } }\n")
    v(ok, _P("ok.ts"))  # must not raise
    try:
        v("export function f(x) { return x; }\n", _P("bad.ts"))
        assert False, "implicit any not caught"
    except LangReject:
        pass


def test_ts_inference_noise_only_tolerated_when_imports_unresolved():
    """Implicit-any is signal ONLY when the type graph is complete. A VS Code
    file whose `vscode` types are absent must PASS (its callbacks are typed in
    the real project); a self-contained file with implicit-any must still FAIL."""
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    import lang
    from lang import LangReject
    from lang._toolchain import resolve
    if resolve("tsc") is None:
        return
    v = lang.get_validator(".ts")
    vs = ('import * as vscode from "vscode";\n'
          "export function activate(): void {\n"
          '  vscode.window.withProgress({}, async (progress) => { progress.report({}); });\n'
          "}\n")
    v(vs, _P("extension.ts"))  # unresolved import → inference noise tolerated
    try:
        v("export function f(x) { return x; }\n", _P("plain.ts"))
        assert False, "self-contained implicit-any must still fail"
    except LangReject:
        pass
