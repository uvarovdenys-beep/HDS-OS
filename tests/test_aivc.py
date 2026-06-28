#!/usr/bin/env python3
"""
test_aivc.py — тести AIVC контролера (без реальних AI-дзвінків)
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from aivc_controller import (
    AIVCController, ActionType, Action, Observation,
    make_lmstudio_caller, make_ollama_caller,
)


def test_parse_json_response():
    """Парсинг чистого JSON від AI."""
    ctrl = AIVCController()

    # Clean JSON
    raw = '{"action": "navigate", "url": "https://example.com", "reason": "test"}'
    action, reasoning = ctrl._parse_ai_response(raw)
    assert action.action_type == ActionType.NAVIGATE, f"Expected NAVIGATE, got {action.action_type}"
    assert action.url == "https://example.com"
    print("  [PASS] Clean JSON parsed correctly")
    return True


def test_parse_markdown_wrapped():
    """Парсинг JSON у markdown блоці."""
    ctrl = AIVCController()

    raw = '```json\n{"action": "click", "selector": "#btn", "reason": "click button"}\n```'
    action, _ = ctrl._parse_ai_response(raw)
    assert action.action_type == ActionType.CLICK
    assert action.selector == "#btn"
    print("  [PASS] Markdown-wrapped JSON parsed")
    return True


def test_parse_done_action():
    """AI повертає done — ціль досягнута."""
    ctrl = AIVCController()

    raw = '{"action": "done", "reason": "Page title confirmed"}'
    action, _ = ctrl._parse_ai_response(raw)
    assert action.action_type == ActionType.DONE
    print("  [PASS] DONE action parsed")
    return True


def test_parse_fail_action():
    """AI повертає fail — ціль недосяжна."""
    ctrl = AIVCController()

    raw = '{"action": "fail", "reason": "Element not found after 3 attempts"}'
    action, _ = ctrl._parse_ai_response(raw)
    assert action.action_type == ActionType.FAIL
    print("  [PASS] FAIL action parsed")
    return True


def test_parse_garbage():
    """Непарсована відповідь → FAIL."""
    ctrl = AIVCController()

    raw = "I think we should navigate to the page and look for the button..."
    action, _ = ctrl._parse_ai_response(raw)
    assert action.action_type == ActionType.FAIL
    print("  [PASS] Garbage response → FAIL")
    return True


def test_no_ai_returns_done():
    """Без AI функції — повертає DONE одразу."""
    ctrl = AIVCController(ai_call_fn=None, max_steps=3)
    result = ctrl.execute_goal("Test goal")
    assert result["success"] == True
    assert result["steps"] == 1
    print("  [PASS] No AI → immediate DONE")
    return True


def test_mock_ai_navigate_done():
    """Mock AI: navigate → done."""
    responses = iter([
        '{"action": "navigate", "url": "https://test.com", "reason": "go to page"}',
        '{"action": "done", "reason": "page loaded"}',
    ])

    def mock_ai(prompt):
        return next(responses)

    ctrl = AIVCController(
        ai_call_fn=mock_ai,
        max_steps=5,
        vision_url="http://127.0.0.1:19001",   # non-existent — will error gracefully
        browser_url="http://127.0.0.1:19002",
    )

    result = ctrl.execute_goal("Navigate to test.com")
    assert result["success"] == True
    assert result["steps"] == 2
    assert result["history"][0]["action"] == "navigate"
    assert result["history"][1]["action"] == "done"
    print("  [PASS] Mock AI: navigate → done (2 steps)")
    return True


def test_max_steps_exhaustion():
    """Якщо AI ніколи не каже done — max steps зупиняє."""
    def endless_ai(prompt):
        return '{"action": "wait", "text": "0.01", "reason": "still waiting"}'

    ctrl = AIVCController(
        ai_call_fn=endless_ai,
        max_steps=3,
        vision_url="http://127.0.0.1:19001",
        browser_url="http://127.0.0.1:19002",
    )

    result = ctrl.execute_goal("Infinite goal")
    assert result["success"] == False
    assert result["steps"] == 3
    print("  [PASS] Max steps exhaustion → failure")
    return True


def test_build_prompt_contains_goal():
    """Prompt містить goal та step number."""
    ctrl = AIVCController()
    obs = Observation(
        timestamp=1.0,
        screen_width=1920, screen_height=1080,
        page_url="https://example.com",
        page_title="Test Page",
    )

    prompt = ctrl._build_prompt("Find the login button", "Project context", obs, 3)
    assert "Find the login button" in prompt
    assert "3/" in prompt
    assert "example.com" in prompt
    assert "Test Page" in prompt
    print("  [PASS] Prompt contains goal, step, page info")
    return True


def test_report_format():
    """Перевірка формату звіту."""
    ctrl = AIVCController(ai_call_fn=None, max_steps=1)
    result = ctrl.execute_goal("Quick test")

    assert "success" in result
    assert "steps" in result
    assert "total_time" in result
    assert "history" in result
    assert isinstance(result["history"], list)
    assert "final_observation" in result
    print("  [PASS] Report has correct format")
    return True


def test_caller_factories():
    """Фабрики AI callers створюються без помилок."""
    fn1 = make_lmstudio_caller(model="test-model")
    fn2 = make_ollama_caller(model="test-model")
    assert callable(fn1)
    assert callable(fn2)
    print("  [PASS] Caller factories create callables")
    return True


# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("HDS AIVC Controller Tests")
    print("=" * 60)

    tests = [
        ("Parse JSON response", test_parse_json_response),
        ("Parse markdown-wrapped", test_parse_markdown_wrapped),
        ("Parse DONE action", test_parse_done_action),
        ("Parse FAIL action", test_parse_fail_action),
        ("Parse garbage → FAIL", test_parse_garbage),
        ("No AI → immediate DONE", test_no_ai_returns_done),
        ("Mock AI navigate → done", test_mock_ai_navigate_done),
        ("Max steps exhaustion", test_max_steps_exhaustion),
        ("Prompt contains goal", test_build_prompt_contains_goal),
        ("Report format", test_report_format),
        ("Caller factories", test_caller_factories),
    ]

    results = []
    for name, fn in tests:
        print(f"\n{'─'*40}")
        print(f"TEST: {name}")
        try:
            ok = fn()
            results.append((name, True))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append((name, False))

    print(f"\n{'═'*60}")
    print("SUMMARY")
    print(f"{'═'*60}")
    total_pass = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n  TOTAL: {total_pass}/{len(results)} tests passed")

    sys.exit(0 if total_pass == len(results) else 1)
