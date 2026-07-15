#!/usr/bin/env python3
"""
test_v11_modules.py — Tests for HDS v1.1 modules
Tests: ProtocolEnforcer, Conductor, CostRouter, DegradationDetector,
       ProgressiveTrust, ShadowVerifier, CanaryTests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from model_router import ProtocolSize, classify_model
from protocol_enforcer import ProtocolEnforcer
from conductor import Conductor, TaskSpec
from cost_router import CostRouter, LOCAL_MODEL_COSTS
from degradation_detector import DegradationDetector
from progressive_trust import ProgressiveTrust
from shadow_verifier import ShadowVerifier
from canary_tests import CanaryTestRunner, CANARY_TESTS


def test_enforcer_action_permissions():
    """ProtocolEnforcer blocks forbidden actions."""
    xl = ProtocolEnforcer("claude-opus-4-6")
    m = ProtocolEnforcer("qwen3.5:9b")
    s = ProtocolEnforcer("claude-haiku-3-5")

    checks = [
        (xl.check_action("decompose")[0], True, "XL can decompose"),
        (m.check_action("decompose")[0], False, "M cannot decompose"),
        (s.check_action("decompose")[0], False, "S cannot decompose"),
        (xl.check_action("discover")[0], True, "XL can discover"),
        (m.check_action("discover")[0], False, "M cannot discover"),
        (m.check_action("create_task")[0], True, "M can create_task"),
        (s.check_action("create_task")[0], False, "S cannot create_task"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    return passed == len(checks)


def test_enforcer_lines_limit():
    """ProtocolEnforcer respects lines-per-change limits."""
    m = ProtocolEnforcer("qwen3.5:9b")  # M: max 200 lines
    s = ProtocolEnforcer("claude-haiku-3-5")  # S: max 50 lines

    checks = [
        (m.check_lines_changed(100)[0], True, "M: 100 lines OK"),
        (m.check_lines_changed(300)[0], False, "M: 300 lines BLOCKED"),
        (s.check_lines_changed(30)[0], True, "S: 30 lines OK"),
        (s.check_lines_changed(60)[0], False, "S: 60 lines BLOCKED"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    return passed == len(checks)


def test_enforcer_task_hierarchy():
    """ProtocolEnforcer enforces task creation hierarchy."""
    xl = ProtocolEnforcer("claude-opus-4-6")
    m = ProtocolEnforcer("qwen3.5:9b")
    s = ProtocolEnforcer("claude-haiku-3-5")

    checks = [
        (xl.check_task_creation(5, "s")[0], True, "XL can create for S"),
        (xl.check_task_creation(5, "xl")[0], True, "XL can create for XL"),
        (m.check_task_creation(3, "s")[0], True, "M can create for S"),
        (m.check_task_creation(3, "xl")[0], False, "M cannot create for XL"),
        (s.check_task_creation(1, "s")[0], False, "S cannot create tasks"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    return passed == len(checks)


def test_conductor_task_assignment():
    """Conductor assigns protocol sizes based on complexity."""
    c = Conductor("qwen3.5:9b")  # M-level model

    t1 = c.add_task("T-001", "Fix typo", complexity=1)
    t2 = c.add_task("T-002", "Create test module", complexity=6)
    t3 = c.add_task("T-003", "Redesign architecture", complexity=9)

    checks = [
        (t1.assigned_size, ProtocolSize.S, "Complexity 1 → S"),
        (t2.assigned_size, ProtocolSize.M, "Complexity 6 → M (capped by model)"),
        (t3.assigned_size, ProtocolSize.M, "Complexity 9 → M (capped by model)"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}: got {value.value.upper()}")
    return passed == len(checks)


def test_conductor_execution_order():
    """Conductor respects dependencies."""
    c = Conductor("qwen3.5:9b")
    c.add_task("T-A", "First task", complexity=3)
    c.add_task("T-B", "Depends on A", complexity=3, dependencies=["T-A"])
    c.add_task("T-C", "Independent", complexity=2)

    order = c.get_execution_order()
    ids = [t.task_id for t in order]

    checks = [
        (ids.index("T-A") < ids.index("T-B"), True, "T-A before T-B (dependency)"),
        (len(ids), 3, "All 3 tasks in order"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    return passed == len(checks)


def test_cost_router_recommendation():
    """CostRouter recommends cheaper models for simple tasks."""
    router = CostRouter()

    checks = [
        (router.recommend("qwen3.5:27b", 1), "qwen3.5:4b", "Complexity 1: use 4b"),
        (router.recommend("qwen3.5:27b", 9), "gpt-oss:20b", "Complexity 9: gpt-oss:20b is cheapest XL"),
        (router.minimum_size_for_complexity(2), ProtocolSize.S, "Complexity 2 → S"),
        (router.minimum_size_for_complexity(5), ProtocolSize.L, "Complexity 5 → L"),
        (router.minimum_size_for_complexity(8), ProtocolSize.XL, "Complexity 8 → XL"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}: got {value}")
    return passed == len(checks)


def test_degradation_detector():
    """DegradationDetector alerts on quality drop."""
    d = DegradationDetector(threshold=0.3)

    # Good baseline
    for _ in range(3):
        d.record(True, True, True, 5.0, 200)

    baseline = d.baseline_score
    not_degrading_yet = not d.is_degrading()

    # Simulate degradation
    for _ in range(5):
        d.record(False, False, False, 30.0, 800)

    checks = [
        (baseline, 1.0, "Baseline is 1.0 (perfect)"),
        (not_degrading_yet, True, "Not degrading at start"),
        (d.is_degrading(), True, "Degrading after bad responses"),
        (d.current_quality() < 0.5, True, "Quality dropped below 0.5"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    return passed == len(checks)


def test_progressive_trust():
    """ProgressiveTrust promotes and demotes correctly."""
    t = ProgressiveTrust("qwen3.5:9b", initial_size=ProtocolSize.M,
                          ceiling=ProtocolSize.L)

    # 3 successes → promotion
    for i in range(3):
        t.record_result(f"T-{i}", success=True, quality_score=0.9)

    promoted_size = t.current_size

    # 2 failures → demotion
    t.record_result("T-F1", success=False)
    t.record_result("T-F2", success=False)

    demoted_size = t.current_size

    checks = [
        (promoted_size, ProtocolSize.L, "Promoted M → L after 3 successes"),
        (demoted_size, ProtocolSize.M, "Demoted L → M after 2 failures"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}: got {value.value.upper()}")
    return passed == len(checks)


def test_progressive_trust_ceiling():
    """ProgressiveTrust respects ceiling."""
    t = ProgressiveTrust("qwen3.5:9b", initial_size=ProtocolSize.M,
                          ceiling=ProtocolSize.M)  # Cannot promote above M

    for i in range(5):
        t.record_result(f"T-{i}", success=True, quality_score=0.95)

    checks = [
        (t.current_size, ProtocolSize.M, "Cannot promote above ceiling M"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    return passed == len(checks)


def test_shadow_verifier():
    """ShadowVerifier verifies S/M tasks, skips L/XL."""
    v = ShadowVerifier()

    checks = [
        (v.should_verify(ProtocolSize.S), True, "Should verify S"),
        (v.should_verify(ProtocolSize.M), True, "Should verify M"),
        (v.should_verify(ProtocolSize.L), False, "Should NOT verify L"),
        (v.should_verify(ProtocolSize.XL), False, "Should NOT verify XL"),
    ]

    # Dry run verification
    result = v.verify("T-001", ProtocolSize.S, "Add import", "Added import logging")
    checks.append((result.passed, False, "Dry run blocks without AI (fail-closed)"))

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    assert passed == len(checks), f"{passed}/{len(checks)} shadow_verifier checks passed"


def test_canary_checks():
    """Canary test check functions work correctly."""
    checks = [
        (CANARY_TESTS["context"]["check"]("Welcome to the team!"), True, "Context: no 'hello'"),
        (CANARY_TESTS["context"]["check"]("Hello there!"), False, "Context: has 'hello'"),
        (CANARY_TESTS["format"]["check"]('{"canary": "alive"}'), True, "Format: clean JSON"),
        (CANARY_TESTS["format"]["check"]("Here: {\"canary\": \"alive\"}"), False, "Format: dirty"),
        (CANARY_TESTS["honesty"]["check"]("UNKNOWN"), True, "Honesty: admits ignorance"),
        (CANARY_TESTS["honesty"]["check"]("The function does X"), False, "Honesty: hallucinates"),
        (CANARY_TESTS["math"]["check"]("221"), True, "Math: correct"),
        (CANARY_TESTS["math"]["check"]("230"), False, "Math: wrong"),
    ]

    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    assert passed == len(checks), f"{passed}/{len(checks)} canary checks passed"


# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("HDS v1.1 Module Tests")
    print("=" * 60)

    tests = [
        ("Enforcer: action permissions", test_enforcer_action_permissions),
        ("Enforcer: lines limit", test_enforcer_lines_limit),
        ("Enforcer: task hierarchy", test_enforcer_task_hierarchy),
        ("Conductor: task assignment", test_conductor_task_assignment),
        ("Conductor: execution order", test_conductor_execution_order),
        ("CostRouter: recommendations", test_cost_router_recommendation),
        ("DegradationDetector", test_degradation_detector),
        ("ProgressiveTrust: promote/demote", test_progressive_trust),
        ("ProgressiveTrust: ceiling", test_progressive_trust_ceiling),
        ("ShadowVerifier", test_shadow_verifier),
        ("Canary test checks", test_canary_checks),
    ]

    results = []
    for name, fn in tests:
        print(f"\n{'─'*60}")
        print(f"TEST: {name}")
        print(f"{'─'*60}")
        try:
            ok = fn()
            results.append((name, ok))
        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append((name, False))

    print(f"\n{'═'*60}")
    print("SUMMARY")
    print(f"{'═'*60}")
    total_pass = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n  TOTAL: {total_pass}/{len(results)} test groups passed")

    sys.exit(0 if total_pass == len(results) else 1)
