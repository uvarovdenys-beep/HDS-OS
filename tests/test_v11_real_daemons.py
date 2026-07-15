#!/usr/bin/env python3
"""
test_v11_real_daemons.py — Tests for HDS v1.1 real daemon implementations.
Tests: VisionUtils, BrowserUtils, WebhookServer, WebSearchDaemon
"""

import sys
import json
import time
import threading
import tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))


# ===== VISION UTILS TESTS =====

def test_vision_utils_load_image():
    """VisionUtils.load_image returns None for missing file."""
    from vision_utils import VisionUtils
    result = VisionUtils.load_image("/nonexistent/path.png")
    assert result is None, "Should return None for missing file"
    print("  PASS: load_image returns None for missing file")


def test_vision_utils_metadata():
    """VisionUtils.get_image_metadata extracts correct dimensions."""
    import numpy as np
    from vision_utils import VisionUtils

    # Create fake image (100x200, 3 channels)
    fake_img = np.zeros((100, 200, 3), dtype=np.uint8)
    meta = VisionUtils.get_image_metadata(fake_img)

    assert meta["width"] == 200, f"Expected width 200, got {meta['width']}"
    assert meta["height"] == 100, f"Expected height 100, got {meta['height']}"
    assert meta["channels"] == 3
    print("  PASS: get_image_metadata extracts correct dimensions")


def test_vision_utils_detect_buttons():
    """VisionUtils.detect_buttons returns list of dicts with bbox_relative."""
    import numpy as np
    from vision_utils import VisionUtils

    # Create image with a rectangle (button-like)
    import cv2
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (50, 50), (200, 100), (0, 0, 0), 2)

    buttons = VisionUtils.detect_buttons(img)
    assert isinstance(buttons, list), "Should return a list"
    # Each button should have bbox_relative
    for b in buttons:
        assert "bbox_relative" in b
        assert "type" in b
        assert b["type"] == "button"
    print(f"  PASS: detect_buttons returned {len(buttons)} buttons")


def test_vision_utils_color_analysis():
    """VisionUtils.analyze_colors returns dominant color."""
    import numpy as np
    from vision_utils import VisionUtils

    # All-red image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :, 2] = 255  # BGR: red channel

    colors = VisionUtils.analyze_colors(img)
    assert colors["dominant_color"]["R"] == 255
    assert colors["dominant_color"]["G"] == 0
    assert colors["dominant_color"]["B"] == 0
    print("  PASS: analyze_colors detects dominant red")


def test_ocr_helper_simple():
    """OCRHelper.extract_text_simple works on blank image."""
    import numpy as np
    from vision_utils import OCRHelper

    # White image (no text)
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    result = OCRHelper.extract_text_simple(img)
    assert "No significant text" in result
    print("  PASS: OCRHelper handles blank image")


# ===== BROWSER UTILS TESTS =====

def test_browser_utils_html_to_markdown():
    """BrowserUtils.html_to_markdown converts basic HTML."""
    from browser_utils import BrowserUtils

    html = "<h1>Title</h1><p>Hello <strong>world</strong></p>"
    md = BrowserUtils.html_to_markdown(html)

    assert "# Title" in md or "#" in md
    assert "**" in md  # bold markers present
    assert "world" in md
    print("  PASS: html_to_markdown converts H1 and bold")


def test_browser_utils_token_estimation():
    """BrowserUtils.estimate_tokens gives reasonable estimate."""
    from browser_utils import BrowserUtils

    text = "Hello world this is a test"
    tokens = BrowserUtils.estimate_tokens(text)
    # ~26 chars / 4 = ~6 tokens
    assert 4 <= tokens <= 10, f"Expected 4-10, got {tokens}"
    print("  PASS: estimate_tokens gives reasonable count")


def test_browser_utils_calculate_savings():
    """BrowserUtils.calculate_savings shows markdown is smaller."""
    from browser_utils import BrowserUtils

    html = "<html><head><style>body{}</style></head><body><p>Hi</p></body></html>"
    md = BrowserUtils.html_to_markdown(html)
    savings = BrowserUtils.calculate_savings(html, md)

    assert savings["savings_percent"] > 0, "Markdown should be smaller than HTML"
    print(f"  PASS: calculate_savings shows {savings['savings_percent']}% savings")


def test_browser_utils_clean_selector():
    """BrowserUtils.clean_selector validates input."""
    from browser_utils import BrowserUtils

    assert BrowserUtils.clean_selector("  #btn  ") == "#btn"

    try:
        BrowserUtils.clean_selector("")
        assert False, "Should raise for empty"
    except ValueError:
        pass
    print("  PASS: clean_selector validates and strips")


# ===== WEB SEARCH DAEMON TESTS =====

def test_web_search_daemon_import():
    """WebSearchDaemon can be imported."""
    from web_search_daemon import WebSearchDaemonServer
    assert WebSearchDaemonServer is not None
    print("  PASS: WebSearchDaemonServer imports OK")


def test_web_search_format_prompt():
    """format_search_for_prompt produces compact output."""
    from web_search_daemon import format_search_for_prompt, SearchResult

    results = [
        SearchResult(title="Test Result", url="https://example.com", snippet="Some text here", source="duckduckgo")
    ]
    prompt = format_search_for_prompt(results)
    assert "Test Result" in prompt
    assert len(prompt) < 500  # Should be compact
    print("  PASS: format_search_for_prompt is compact")


def test_web_search_format_factcheck():
    """format_factcheck_for_prompt gives structured output."""
    from web_search_daemon import format_factcheck_for_prompt, FactCheck

    fc = FactCheck(
        claim="Python is fast",
        verdict="partially_supported",
        confidence=0.6,
        evidence=[{"stance": "contradicts", "title": "Python is interpreted", "snippet": "Python uses an interpreter", "url": "https://example.com"}],
        sources_checked=3
    )
    prompt = format_factcheck_for_prompt(fc)
    assert "PARTIALLY_SUPPORTED" in prompt
    assert "Python is fast" in prompt
    print("  PASS: format_factcheck_for_prompt structured")


# ===== REAL VISION DAEMON SERVER TESTS =====

def test_vision_daemon_unknown_task():
    """RealVisionDaemonServer handles unknown task type."""
    from vision_daemon_real import RealVisionDaemonServer

    server = RealVisionDaemonServer.__new__(RealVisionDaemonServer)
    server.memory = []
    server.captures_dir = Path(tempfile.mkdtemp())

    result = server.execute_task({"type": "unknown_type", "task_id": "T-1"})
    assert result["status"] == "error"
    assert "Unknown" in result["error"]
    print("  PASS: vision daemon handles unknown task type")


# ===== REAL BROWSER DAEMON SERVER TESTS =====

def test_browser_daemon_no_page():
    """RealBrowserDaemonServer returns error when no page loaded."""
    from browser_daemon_real import RealBrowserDaemonServer

    server = RealBrowserDaemonServer.__new__(RealBrowserDaemonServer)
    server.last_page = None
    server.last_context = None
    server.state_dir = Path(tempfile.mkdtemp())

    result = server._click_real("T-1", {"selector": "#btn"})
    assert result["status"] == "error"
    assert "No page" in result["error"]

    result = server._type_real("T-1", {"selector": "#input", "text": "hi"})
    assert result["status"] == "error"

    result = server._dom_to_markdown_real("T-1", {})
    assert result["status"] == "error"
    print("  PASS: browser daemon returns error when no page loaded")


# ===== RUNNER =====

def main():
    """Run all tests."""
    tests = [
        ("VisionUtils.load_image", test_vision_utils_load_image),
        ("VisionUtils.metadata", test_vision_utils_metadata),
        ("VisionUtils.detect_buttons", test_vision_utils_detect_buttons),
        ("VisionUtils.color_analysis", test_vision_utils_color_analysis),
        ("OCRHelper.simple", test_ocr_helper_simple),
        ("BrowserUtils.html_to_markdown", test_browser_utils_html_to_markdown),
        ("BrowserUtils.estimate_tokens", test_browser_utils_token_estimation),
        ("BrowserUtils.calculate_savings", test_browser_utils_calculate_savings),
        ("BrowserUtils.clean_selector", test_browser_utils_clean_selector),
        ("WebSearch.import", test_web_search_daemon_import),
        ("WebSearch.format_prompt", test_web_search_format_prompt),
        ("WebSearch.format_factcheck", test_web_search_format_factcheck),
        ("VisionDaemon.unknown_task", test_vision_daemon_unknown_task),
        ("BrowserDaemon.no_page", test_browser_daemon_no_page),
    ]

    print(f"\n{'='*60}")
    print(f"HDS v1.1 REAL DAEMON TESTS ({len(tests)} tests)")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name} — {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
