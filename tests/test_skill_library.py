"""The skill library: the POSITIVE half of memory.

Only fully verified code is admitted (cage + acceptance + Monte Carlo), because
an unproven example propagates its own mistake to every later task.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import skill_library as lib


def _fresh():
    """Isolated store, and NO embedding call.

    These tests assert the library's logic, not the embedding model. Letting
    them reach the local model made the suite twice as slow (41s -> 77s) and
    made a green run depend on a service being up. Semantic recall itself is
    covered in test_reflexion, which skips when the model is absent.
    """
    p = Path(tempfile.mkdtemp()) / "skills.jsonl"
    lib.LIB = p
    lib._embed = lambda _text: None
    return p


def test_record_and_read_back():
    _fresh()
    assert lib.record("clamp", "def clamp(x): return x", "Python", "limit a value") is True
    rows = lib.entries()
    assert len(rows) == 1 and rows[0]["name"] == "clamp"


def test_empty_or_oversized_is_refused():
    _fresh()
    assert lib.record("x", "", "Python") is False
    assert lib.record("", "code", "Python") is False
    assert lib.record("big", "x" * (lib.MAX_CODE_CHARS + 1), "Python") is False


def test_newest_version_of_a_name_wins():
    _fresh()
    lib.record("f", "def f(): return 1", "Python")
    lib.record("f", "def f(): return 2", "Python")
    rows = [r for r in lib.entries() if r["name"] == "f"]
    assert len(rows) == 1 and "return 2" in rows[0]["code"]


def test_recall_is_empty_without_a_query():
    _fresh()
    lib.record("f", "def f(): return 1", "Python", "does a thing")
    assert lib.recall("", "Python") == []


def test_block_is_empty_when_library_is_empty():
    _fresh()
    assert lib.block("anything", "Python") == ""


def test_language_filter_excludes_other_languages():
    _fresh()
    lib.record("f", "function f(){}", "JavaScript", "js thing")
    assert lib.recall("js thing", "Python") == []
