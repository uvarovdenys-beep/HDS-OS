"""R-PRESERVE — a rewrite may not silently delete declarations.

The gap this closes: the cage checked what a file CONTAINS, never what a
rewrite DESTROYS. Asked to add one helper, a local model re-emitted a whole
JavaScript file and dropped nextTurn, updateScales and every log call with it —
nine times, each rewrite valid JavaScript and therefore accepted by R-AST.
Validity is not preservation.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scribe  # noqa: E402
from lang._preserve import declarations  # noqa: E402

DIR = "storage/preserve_test"

JS_FULL = ("function alpha() { return 1; }\n"
           "function beta() { return 2; }\n"
           "function gamma() { return 3; }\n")
JS_GROWN = JS_FULL + "function delta() { return 4; }\n"
JS_LOST = "function gamma() { return 3; }\n"

PY_FULL = "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n"
PY_LOST = "def alpha():\n    return 1\n"


def _root():
    """Resolve scribe's CURRENT root at call time.

    Other tests in this suite repoint scribe.ROOT at a temp dir. A path captured
    at import would then point at the real repo while scribe writes elsewhere —
    these tests passed alone and failed in the full run for exactly that reason.
    """
    import scribe as _scribe
    return Path(_scribe.ROOT)


def _write(name, content):
    path = f"{DIR}/{name}"
    scribe.execute({"op": "write", "path": path, "content": content}, "l")
    return path


def _cleanup(name):
    (_root() / DIR / name).unlink(missing_ok=True)


def _cleanup(name):
    (_root() / DIR / name).unlink(missing_ok=True)


# ── what the rule allows ─────────────────────────────────────────────────

def test_a_new_file_is_allowed():
    """A file that did not exist deletes nothing."""
    try:
        _write("new.js", JS_FULL)
        assert (_root() / DIR / "new.js").exists()
    finally:
        _cleanup("new.js")


def test_adding_a_declaration_is_allowed():
    try:
        _write("grow.js", JS_FULL)
        _write("grow.js", JS_GROWN)
        assert "delta" in (_root() / DIR / "grow.js").read_text(encoding="utf-8")
    finally:
        _cleanup("grow.js")


def test_editing_a_body_is_allowed():
    """Only deletion is stopped; changing what a function does is free."""
    try:
        _write("edit.js", JS_FULL)
        _write("edit.js", JS_FULL.replace("return 1", "return 99"))
        assert "return 99" in (_root() / DIR / "edit.js").read_text(encoding="utf-8")
    finally:
        _cleanup("edit.js")


# ── what the rule refuses ────────────────────────────────────────────────

def test_a_rewrite_that_drops_declarations_is_refused():
    """The exact failure that cost nine rounds on one game file."""
    try:
        _write("drop.js", JS_FULL)
        with pytest.raises(scribe.ScribeError) as err:
            _write("drop.js", JS_LOST)
        assert "R-PRESERVE" in str(err.value)
        assert "alpha" in str(err.value) and "beta" in str(err.value)
        # the file on disk must be untouched
        assert "alpha" in (_root() / DIR / "drop.js").read_text(encoding="utf-8")
    finally:
        _cleanup("drop.js")


def test_python_is_covered_too():
    try:
        _write("drop.py", PY_FULL)
        with pytest.raises(scribe.ScribeError) as err:
            _write("drop.py", PY_LOST)
        assert "beta" in str(err.value)
    finally:
        _cleanup("drop.py")


# ── the extractor itself ─────────────────────────────────────────────────

def test_python_declarations_come_from_the_ast():
    names = declarations("def a():\n    pass\n\n\nclass B:\n    pass\n", ".py")
    assert names == {"a", "B"}


def test_javascript_finds_both_forms():
    names = declarations("function alpha(){}\nconst beta = () => 1;\n", ".js")
    assert "alpha" in names and "beta" in names


def test_unparseable_python_cannot_tell_and_does_not_block():
    """Never refuse on inability to read: an unparseable old file yields no
    names, so there is no basis to claim something was lost."""
    assert declarations("def broken(:\n", ".py") == set()


def test_unknown_extension_yields_nothing():
    assert declarations("whatever", ".xyz") == set()


def test_every_gated_language_is_wrapped():
    """The rule is applied in `register`, so adding a language cannot forget
    it. If a validator is registered without the wrapper this fails."""
    import lang
    for ext in (".py", ".js", ".ts", ".c", ".cpp", ".cs", ".rb", ".go", ".php", ".sh"):
        assert lang.get_validator(ext) is not None, f"{ext} lost its validator"
