"""C, C++ and C# — the three compiled languages, verified end to end.

Each language must do three things, and the tests are grouped that way:
  1. accept code that is correct;
  2. refuse a dangerous call, regardless of whether a compiler is installed;
  3. refuse code that does not parse, using the REAL compiler front-end.

`.c` is the reason this file exists. It sat in scribe.CODE_EXTS with no
registered validator, so the fail-closed default refused every C file — safe,
but the language was advertised and unusable. test_c_is_registered pins that it
stays wired up.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lang  # noqa: E402
import scribe  # noqa: E402
from lang._toolchain import resolve  # noqa: E402

DIR = "storage/c_family_test"


def _verdict(name, content):
    """ALLOW or DENY, cleaning up whatever landed."""
    path = f"{DIR}/{name}"
    try:
        scribe.execute({"op": "write", "path": path, "content": content}, "l")
        return "ALLOW"
    except scribe.ScribeError:
        return "DENY"
    finally:
        (ROOT / path).unlink(missing_ok=True)


def _need(tool):
    return pytest.mark.skipif(resolve(tool) is None, reason=f"{tool} not installed")


# ── every compiled extension must have a validator ───────────────────────

@pytest.mark.parametrize("ext", [".c", ".cpp", ".cc", ".hpp", ".cs"])
def test_compiled_extension_has_a_validator(ext):
    """A CODE_EXTS entry with no validator is refused outright — safe, but it
    means the language is advertised and unusable. Catch that here."""
    assert ext in scribe.CODE_EXTS, f"{ext} is not gated at all"
    assert lang.get_validator(ext) is not None, f"{ext} has no validator"


@pytest.mark.xfail(reason="known gap: '.h' is not in scribe.CODE_EXTS, so a C "
                          "header is written as unscanned data. Closing it means "
                          "editing scribe.py, which R-KERNEL forbids to any "
                          "automated write — a human must do it deliberately.",
                   strict=True)
def test_c_header_is_content_scanned():
    """A .h carrying system() should be refused. Today it is not.

    The validator for '.h' IS registered; the extension simply never reaches it,
    because scribe treats anything outside CODE_EXTS as plain data. When '.h' is
    added there this test starts passing and the xfail marker must be removed.
    """
    assert ".h" in scribe.CODE_EXTS
    assert _verdict("evil.h", "#include <stdlib.h>\n"
                              'static void p(void) { system("rm -rf /"); }\n') == "DENY"


# ── C ────────────────────────────────────────────────────────────────────

@_need("clang")
def test_c_valid_is_allowed():
    assert _verdict("ok.c", "#include <stdio.h>\n\n"
                            "int add(int a, int b) {\n    return a + b;\n}\n") == "ALLOW"


@_need("clang")
def test_c_header_is_allowed():
    assert _verdict("ok.h", "#ifndef OK_H\n#define OK_H\n"
                            "int add(int a, int b);\n#endif\n") == "ALLOW"


def test_c_system_is_denied():
    """Hygiene fires with or without a compiler present."""
    assert _verdict("bad.c", "#include <stdlib.h>\n\n"
                             'void pwn(void) {\n    system("rm -rf /");\n}\n') == "DENY"


def test_c_fork_is_denied():
    assert _verdict("fork.c", "#include <unistd.h>\n\n"
                              "void f(void) {\n    fork();\n}\n") == "DENY"


@_need("clang")
def test_c_broken_syntax_is_denied():
    assert _verdict("broken.c", "int add(int a, int b) {\n    return a + b;\n") == "DENY"


# ── C++ ──────────────────────────────────────────────────────────────────

@_need("clang++")
def test_cpp_valid_is_allowed():
    assert _verdict("ok.cpp", "#include <string>\n\n"
                              "int add(int a, int b) {\n    return a + b;\n}\n") == "ALLOW"


def test_cpp_system_is_denied():
    assert _verdict("bad.cpp", "#include <cstdlib>\n\n"
                               'void pwn() {\n    system("rm -rf /");\n}\n') == "DENY"


def test_cpp_inline_asm_is_denied():
    assert _verdict("asm.cpp", 'void f() {\n    __asm__("nop");\n}\n') == "DENY"


@_need("clang++")
def test_cpp_broken_syntax_is_denied():
    assert _verdict("broken.cpp", "int add(int a, int b) {\n    return a + b;\n") == "DENY"


# ── C# ───────────────────────────────────────────────────────────────────

@_need("dotnet")
def test_cs_valid_is_allowed():
    assert _verdict("Ok.cs", "public class Calc {\n"
                             "    public int Add(int a, int b) { return a + b; }\n}\n") == "ALLOW"


def test_cs_process_start_is_denied():
    assert _verdict("Bad.cs", "using System.Diagnostics;\npublic class P {\n"
                              '    public void Run() { Process.Start("cmd.exe"); }\n}\n') == "DENY"


@_need("dotnet")
def test_cs_broken_syntax_is_denied():
    assert _verdict("Broken.cs", "public class Calc {\n"
                                 "    public int Add(int a, int b) { return a + b;\n") == "DENY"


# ── the fail-closed default itself ───────────────────────────────────────

def test_unregistered_code_extension_is_refused():
    """The fail-closed default: a gated extension with no validator is denied.

    Uses a FAKE extension on purpose. This test used to name '.rs', and the
    moment Rust gained a validator it started failing — it was pinned to a
    language's current status instead of to the rule.
    """
    original = scribe.CODE_EXTS
    scribe.CODE_EXTS = original + (".zzz",)
    try:
        assert lang.get_validator(".zzz") is None
        assert _verdict("x.zzz", "anything at all\n") == "DENY"
    finally:
        scribe.CODE_EXTS = original
