"""Rollback: a rejected generation must not stay on disk.

scribe writes BEFORE acceptance and Monte Carlo can run — they execute the
written file — so a task that ends up failing has already changed it. These
tests pin that the file goes back.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rollback
import scribe

WORK = ROOT / "storage" / "rb_test"


def _write(name, text):
    WORK.mkdir(parents=True, exist_ok=True)
    p = WORK / name
    p.write_text(text)
    return p


def test_snapshot_reports_an_absent_file():
    p = WORK / "never_created.py"
    p.unlink(missing_ok=True)
    assert rollback.snapshot(p) is rollback.ABSENT


def test_absent_file_is_deleted_again_on_rollback():
    # The task CREATED the file, then failed: it must not survive.
    p = WORK / "created.py"
    p.unlink(missing_ok=True)
    state = rollback.snapshot(p)
    _write("created.py", "def half_written():\n    pass\n")
    assert p.exists()
    assert rollback.restore(p, state) is True
    assert not p.exists()


def test_existing_file_is_restored_byte_for_byte():
    original = "def keep():\n    return 1\n"
    p = _write("existing.py", original)
    state = rollback.snapshot(p)
    p.write_text("def keep():\n    return 999\n")
    assert rollback.restore(p, state) is True
    assert p.read_text() == original
    p.unlink(missing_ok=True)


def test_restore_may_drop_declarations_the_failed_attempt_added():
    """The reason restore deletes first.

    Rolling back removes whatever the rejected attempt declared, and R-PRESERVE
    refuses a rewrite that drops a declaration. A plain write would therefore be
    refused here; delete-then-write is its sanctioned escape.
    """
    original = "def only_one():\n    return 1\n"
    p = _write("grew.py", original)
    state = rollback.snapshot(p)
    # the failed attempt added a second declaration
    p.write_text(original + "\n\ndef added_by_failure():\n    return 2\n")

    # a plain rewrite back to the original is refused by the cage
    refused = False
    try:
        scribe.execute({"op": "write", "path": str(p.relative_to(ROOT)),
                        "content": original}, protocol_size="l")
    except scribe.ScribeError as e:
        refused = "R-PRESERVE" in str(e)
    assert refused, "expected R-PRESERVE to refuse the shrinking rewrite"

    # rollback still succeeds, and the added declaration is gone
    assert rollback.restore(p, state) is True
    assert p.read_text() == original
    assert "added_by_failure" not in p.read_text()
    p.unlink(missing_ok=True)


def test_unusable_snapshot_declines_instead_of_guessing():
    p = _write("untouched.py", "def x():\n    return 1\n")
    assert rollback.restore(p, None) is False
    assert p.exists()          # nothing was destroyed on the way out
    p.unlink(missing_ok=True)


def test_describe_never_returns_an_empty_line():
    assert rollback.describe(rollback.ABSENT)
    assert rollback.describe(None)
    assert "2 line" in rollback.describe("a\nb\n")
