#!/usr/bin/env python3
"""
test_model_router.py — тести для маршрутизатора моделей та адаптації задач
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from model_router import (
    ProtocolSize, classify_model, get_model_profile,
    get_protocol_path, adapt_task, get_boot_prompt,
)


def test_classify_known_models():
    """Статична класифікація відомих моделей."""
    cases = [
        ("claude-opus-4-6", ProtocolSize.XL),
        ("claude-sonnet-4-6", ProtocolSize.L),
        ("claude-haiku-3-5", ProtocolSize.S),
        ("gpt-4o", ProtocolSize.XL),
        ("gpt-4o-mini", ProtocolSize.L),
        ("qwen3.5:9b", ProtocolSize.M),
        ("qwen3.5:4b", ProtocolSize.S),
        ("tinyllama", ProtocolSize.S),
        ("deepseek-r1:70b", ProtocolSize.XL),
    ]
    passed = 0
    for model, expected in cases:
        result, _ = classify_model(model)
        ok = result == expected
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {model} → {result.value.upper()} (expected {expected.value.upper()})")

    print(f"\n  Results: {passed}/{len(cases)} passed")
    return passed == len(cases)


def test_unknown_model_defaults_to_m():
    """Невідома модель → M (безпечний середній)."""
    size, ctx = classify_model("completely-unknown-model-xyz")
    ok = size == ProtocolSize.M
    print(f"  [{'PASS' if ok else 'FAIL'}] unknown → {size.value.upper()} (expected M)")
    return ok


def test_profile_capabilities():
    """Перевірка можливостей за розміром."""
    xl = get_model_profile("claude-opus-4-6")
    s = get_model_profile("claude-haiku-3-5")

    checks = [
        (xl.can_discover, True, "XL can discover"),
        (xl.can_aivc, True, "XL can AIVC"),
        (xl.can_decompose, True, "XL can decompose"),
        (xl.max_lines_per_change, 1000, "XL max 1000 lines"),
        (s.can_discover, False, "S cannot discover"),
        (s.can_aivc, False, "S cannot AIVC"),
        (s.max_lines_per_change, 50, "S max 50 lines"),
        (s.max_files_per_session, 3, "S max 3 files"),
    ]
    passed = 0
    for value, expected, desc in checks:
        ok = value == expected
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}: {value}")

    print(f"\n  Results: {passed}/{len(checks)} passed")
    return passed == len(checks)


def test_task_adaptation():
    """Одна задача — різні формати для різних розмірів."""
    task = {
        "goal": "Додати валідацію email",
        "target": {"file": "src/auth.py", "line": 42},
        "solution_hint": "import re; EMAIL_RE = r'...'",
        "test": "python3 -c \"print('PASSED')\"",
        "decomposition": [{"name": "Add import", "target": "src/auth.py"}],
    }

    xl_text = adapt_task(task, "claude-opus-4-6")
    s_text = adapt_task(task, "claude-haiku-3-5")

    checks = [
        ("## GOAL" in xl_text, "XL has ## GOAL"),
        ("## DVP LOG" in xl_text, "XL has DVP LOG"),
        ("## DECOMPOSITION" in xl_text, "XL has DECOMPOSITION"),
        ("FILE:" in s_text, "S has FILE:"),
        ("LINE:" in s_text, "S has LINE:"),
        ("DECOMPOSITION" not in s_text, "S has NO decomposition"),
        (len(s_text) < len(xl_text), "S is shorter than XL"),
    ]
    passed = 0
    for value, desc in checks:
        passed += value
        print(f"  [{'PASS' if value else 'FAIL'}] {desc}")

    print(f"\n  Results: {passed}/{len(checks)} passed")
    return passed == len(checks)


def test_boot_prompt():
    """Boot prompt відповідає розміру."""
    xl_boot = get_boot_prompt("claude-opus-4-6")
    s_boot = get_boot_prompt("claude-haiku-3-5")

    checks = [
        ("XL" in xl_boot, "XL boot mentions XL"),
        ("autonomy" in xl_boot or "Architect" in xl_boot, "XL boot mentions autonomy"),
        ("Mode S" in s_boot, "S boot mentions S"),
        ("STOP" in s_boot, "S boot says STOP"),
        (len(s_boot) < len(xl_boot), "S boot is shorter"),
    ]
    passed = 0
    for value, desc in checks:
        passed += value
        print(f"  [{'PASS' if value else 'FAIL'}] {desc}")

    print(f"\n  Results: {passed}/{len(checks)} passed")
    return passed == len(checks)


def test_protocol_files_exist():
    """Перевірка що всі файли протоколів існують."""
    base = Path(__file__).parent.parent
    files = [
        "ai-mind/protocols/hds_xl.md",
        "ai-mind/protocols/hds_l.md",
        "ai-mind/protocols/hds_m.md",
        "ai-mind/protocols/hds_s.md",
        "ai-mind/protocols/diagnostic.yaml",
        "ai-mind/protocols/README.md",
    ]
    passed = 0
    for f in files:
        exists = (base / f).exists()
        passed += exists
        print(f"  [{'PASS' if exists else 'FAIL'}] {f}")

    print(f"\n  Results: {passed}/{len(files)} passed")
    return passed == len(files)


# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("HDS Model Router Tests")
    print("=" * 60)

    tests = [
        ("Classify known models", test_classify_known_models),
        ("Unknown model → M default", test_unknown_model_defaults_to_m),
        ("Profile capabilities", test_profile_capabilities),
        ("Task adaptation", test_task_adaptation),
        ("Boot prompt", test_boot_prompt),
        ("Protocol files exist", test_protocol_files_exist),
    ]

    results = []
    for name, fn in tests:
        print(f"\n{'─'*60}")
        print(f"TEST: {name}")
        print(f"{'─'*60}")
        ok = fn()
        results.append((name, ok))

    print(f"\n{'═'*60}")
    print("SUMMARY")
    print(f"{'═'*60}")
    total_pass = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n  TOTAL: {total_pass}/{len(results)} test groups passed")

    sys.exit(0 if total_pass == len(results) else 1)
