"""Quality snapshots: pin the numbers to a release so "better" is checkable.

This module must never spawn a process — the cage refused an earlier version for
importing subprocess, correctly, since sandbox/ is the single exec surface.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hds_snapshot as snap


def test_module_does_not_spawn_processes():
    src = (ROOT / "hds_snapshot.py").read_text()
    assert "import subprocess" not in src


def test_test_count_comes_from_the_caller():
    assert snap._tests_passing(["--tests", "333"]) == 333
    assert snap._tests_passing(["--tests", "notanumber"]) == 0
    assert snap._tests_passing([]) == 0


def test_collect_returns_comparable_fields():
    row = snap.collect("vX", ["--tests", "12"])
    assert row["version"] == "vX" and row["tests"] == 12
    assert "t" in row


def test_delta_handles_a_first_snapshot():
    assert "first snapshot" in snap._delta({"tests": 1}, {})


def test_delta_reports_the_change():
    out = snap._delta({"tests": 10}, {"tests": 7})
    assert "7 -> 10" in out and "+3" in out
