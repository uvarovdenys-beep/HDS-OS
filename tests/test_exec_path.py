"""Exec-path invariant: no spawn site outside sandbox/ except tracked debt.

Green today, and it tightens automatically: fixing a debt file makes
test_known_debt_shrinks_only fail until it is dropped from KNOWN_DEBT.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import exec_path_audit

# Empty: the two shell=True breaches now route through SandboxRunner.
# The exec-path invariant is real — every spawn is in sandbox/ or trusted infra.
KNOWN_DEBT = set()


def test_no_new_exec_path_breaches():
    breaches = {v["file"] for v in exec_path_audit.run()}
    new = breaches - KNOWN_DEBT
    assert new == set(), f"NEW exec-path breach — route via SandboxRunner: {new}"


def test_known_debt_shrinks_only():
    breaches = {v["file"] for v in exec_path_audit.run()}
    stale = KNOWN_DEBT - breaches
    assert stale == set(), f"fixed — drop these from KNOWN_DEBT: {stale}"
