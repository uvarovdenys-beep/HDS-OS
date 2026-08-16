"""Surgical patching beyond Python — the asymmetry that cost nine rewrites.

patcher.locate called ast.parse, so a function could be replaced by NAME in
Python and nowhere else. Ten languages had validators; one could be edited
surgically. A JavaScript game file was therefore rewritten whole nine times, and
each rewrite silently dropped working functions.

These tests pin the locator for every gated language, and pin the refusals —
because a locator that guesses a range deletes the wrong lines, which is worse
than not patching at all.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import patcher  # noqa: E402
from lang._locate import LocateError  # noqa: E402
from lang._locate import locate as walk  # noqa: E402

SAMPLES = {
    ".js":   "function other(){return 1;}\nfunction target(x){\n  return x;\n}\n",
    ".ts":   "export function target(x: number): number {\n  return x;\n}\n",
    ".c":    "#include <stdio.h>\n\nint target(int a){\n  return a;\n}\n",
    ".cpp":  "int other(){return 0;}\n\nint target(int a){\n  return a;\n}\n",
    ".go":   "package main\n\nfunc target(a int) int {\n\treturn a\n}\n",
    ".rs":   "pub fn target(a: i32) -> i32 {\n    a\n}\n",
    ".rb":   "def other\n  1\nend\n\ndef target(a)\n  a\nend\n",
    ".php":  "<?php\nfunction target($a){\n  return $a;\n}\n",
    ".sh":   "target(){\n  echo 1\n}\n",
    ".swift": "func target(a: Int) -> Int {\n    return a\n}\n",
}


@pytest.mark.parametrize("ext", sorted(SAMPLES))
def test_every_gated_language_can_be_located_by_name(ext):
    """The whole point: name a function in any supported language, get its span."""
    source = SAMPLES[ext]
    start, end = walk(source, "target", ext)
    block = "\n".join(source.splitlines()[start - 1:end])
    assert "target" in block.splitlines()[0]
    assert block.rstrip().endswith(("}", "end"))


def test_a_brace_inside_a_string_does_not_end_the_block():
    """Counting braces naively is how a patcher corrupts a file."""
    src = 'function target(){\n  return "}";\n}\nfunction after(){return 1;}\n'
    assert walk(src, "target", ".js") == (1, 3)


def test_a_brace_inside_a_comment_does_not_end_the_block():
    src = "int target(void){\n  /* } */\n  return 1;\n}\n"
    assert walk(src, "target", ".c") == (1, 4)


def test_a_missing_target_is_refused():
    with pytest.raises(LocateError, match="not found"):
        walk("function a(){}\n", "ghost", ".js")


def test_an_ambiguous_target_is_refused():
    """Two declarations of one name: patching either would be a guess."""
    src = "function target(){return 1;}\nfunction target(){return 2;}\n"
    with pytest.raises(LocateError, match="ambiguous"):
        walk(src, "target", ".js")


def test_an_unclosed_block_is_refused():
    with pytest.raises(LocateError, match="never closes|unbalanced"):
        walk("function target(){\n  return 1;\n", "target", ".js")


def test_an_unsupported_extension_is_refused():
    with pytest.raises(LocateError, match="no locator"):
        walk("whatever", "target", ".xyz")


# ── the path scribe actually takes ───────────────────────────────────────

def test_patcher_routes_python_through_the_ast():
    src = "def other():\n    return 1\n\n\ndef target(x):\n    return x\n"
    assert patcher.locate(src, "target") == (5, 6)


def test_patcher_falls_back_when_the_source_is_not_python():
    """scribe calls locate() WITHOUT an extension — R-KERNEL forbids changing
    it — so the fallback has to work from the source alone."""
    src = "function other(){return 1;}\nfunction target(x){\n  return x;\n}\n"
    assert patcher.locate(src, "target") == (2, 4)


def test_explicit_extension_wins():
    src = "function target(x){\n  return x;\n}\n"
    assert patcher.locate(src, "target", ".js") == (1, 3)


def test_python_decorators_are_carried_with_the_function():
    """A patch that drops a decorator silently changes behaviour."""
    src = "@staticmethod\ndef target():\n    return 1\n"
    assert patcher.locate(src, "target") == (1, 3)


# ── JS/TS class methods: the measured gap top-level location left open ──────

def test_js_class_method_locates():
    src = "class A {\n  m(z){\n    return z;\n  }\n}\n"
    assert patcher.locate(src, "A.m", ".js") == (2, 4)


def test_ts_typed_method_locates():
    src = "class S {\n  add(a: number): void {\n    this.x = a;\n  }\n}\n"
    assert patcher.locate(src, "S.add", ".ts") == (2, 4)


def test_static_async_method_locates():
    src = "class D {\n  static async load(u){\n    return u;\n  }\n}\n"
    assert patcher.locate(src, "D.load", ".js") == (2, 4)


def test_method_decl_not_confused_with_internal_call():
    # `this.run()` inside the body must not be mistaken for the declaration.
    src = "class C {\n  run(){\n    this.run();\n  }\n  other(){ return 1; }\n}\n"
    assert patcher.locate(src, "C.run", ".js") == (2, 4)


def test_ambiguous_overload_is_refused():
    src = "class F {\n  x(a){ return a; }\n  x(a, b){ return b; }\n}\n"
    with pytest.raises(patcher.PatchError):
        patcher.locate(src, "F.x", ".ts")


def test_missing_class_is_refused():
    src = "class A {\n  m(z){ return z; }\n}\n"
    with pytest.raises(patcher.PatchError):
        patcher.locate(src, "Nope.m", ".js")
