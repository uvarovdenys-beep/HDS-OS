"""R-STUB — a placeholder must say that it is one.

The failure: a generated rollDice arrived with both branches empty — only
`// Move investigator` and `// Handle failure` — and the cage accepted it,
because the syntax was valid. The game ran, logged nothing and looked broken for
no visible reason. A stub has the SHAPE of working code, so every check that
reads shape says yes.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scribe  # noqa: E402
from lang._stubs import find  # noqa: E402

DIR = "storage/stub_test"


def _root():
    import scribe as _s
    return Path(_s.ROOT)


def _write(name, content):
    scribe.execute({"op": "write", "path": f"{DIR}/{name}", "content": content}, "l")


def _cleanup(name):
    (_root() / DIR / name).unlink(missing_ok=True)


# ── refused ──────────────────────────────────────────────────────────────

def test_an_empty_javascript_function_is_refused():
    """The exact shape that shipped: comments describing work never done."""
    try:
        with pytest.raises(scribe.ScribeError) as err:
            _write("hollow.js", "function work(){ return 1; }\n"
                                "function hollow(){\n  // Move investigator\n}\n")
        assert "R-STUB" in str(err.value) and "hollow" in str(err.value)
    finally:
        _cleanup("hollow.js")


def test_an_empty_python_function_is_refused():
    try:
        with pytest.raises(scribe.ScribeError) as err:
            _write("hollow.py", "def work():\n    return 1\n\n\ndef hollow():\n    pass\n")
        assert "hollow" in str(err.value)
    finally:
        _cleanup("hollow.py")


def test_a_docstring_alone_is_not_an_implementation():
    try:
        with pytest.raises(scribe.ScribeError):
            _write("doc.py", 'def hollow():\n    """Explains what it would do."""\n')
    finally:
        _cleanup("doc.py")


# ── allowed ──────────────────────────────────────────────────────────────

def test_a_marked_stub_is_allowed():
    """One line of honesty is the whole price."""
    try:
        _write("marked.js", "function hollow(){\n  // STUB: turn logic lands next task\n}\n")
        assert (_root() / DIR / "marked.js").exists()
    finally:
        _cleanup("marked.js")


def test_not_implemented_is_already_self_documenting():
    try:
        _write("ni.py", "def hollow():\n    raise NotImplementedError('planned')\n")
        assert (_root() / DIR / "ni.py").exists()
    finally:
        _cleanup("ni.py")


def test_working_code_passes_untouched():
    try:
        _write("real.js", "function work(){\n  return 1 + 1;\n}\n")
        assert (_root() / DIR / "real.js").exists()
    finally:
        _cleanup("real.js")


# ── the detector, directly ───────────────────────────────────────────────

def test_a_prototype_is_a_declaration_not_a_stub():
    """C forward declarations have no body at all — nothing was promised."""
    assert find("int later(int a);\n", ".c") == []


def test_todo_counts_as_a_marker():
    assert find("function hollow(){\n  // TODO: later\n}\n", ".js") == []


def test_detection_reports_the_line():
    found = find("function a(){return 1;}\nfunction hollow(){\n}\n", ".js")
    assert found and found[0][0] == "hollow" and found[0][1] == 2


def test_unparseable_python_reports_nothing():
    """Never block on inability to read — the syntax check owns that verdict."""
    assert find("def broken(:\n", ".py") == []
