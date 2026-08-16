"""cage_help.explain: terse verdict -> one actionable sentence.

Written by the local model, acceptance-verified; pinned here so the guidance the
self-correction loop feeds back stays accurate as verdicts evolve.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cage_help import explain


def test_known_verdicts_get_actionable_hints():
    assert explain("R-AST: R-PRESERVE: 'x.js' rewrite drops 1 declaration(s)").startswith("Do not delete")
    assert "placeholder" in explain("R-STUB: empty function")
    assert "exact name" in explain("R-PATCH: target not found")
    assert "os.path" in explain("R-AST: 'x.py' rejected (DANGER: forbidden_import)")
    assert "without it" in explain("R-AST: 'x.py' rejected (CRITICAL: forbidden_call)")
    assert "explicit type" in explain("error TS7006: Parameter 'x' implicitly has an 'any' type")


def test_unknown_verdict_is_empty():
    assert explain("some unrelated message") == ""
