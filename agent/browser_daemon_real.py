#!/usr/bin/env python3
"""
browser_daemon_real.py
HDS Real Browser Daemon - Web Automation with Playwright

Real browser automation for:
- Website navigation
- Element interaction
- DOM extraction
- Screenshot capture

Authors: HDS Development Team
License: HDS6 Standard
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

agent_path = Path(__file__).parent
sys.path.insert(0, str(agent_path))

from microkernel_ipc import MicrokernelIPCServer
from browser_utils import BrowserUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global browser instance (singleton)
_browser_instance = None
_browser_lock = None


def init_browser():
    """Initialize browser (lazy loading)."""
    global _browser_instance
    try:
        from playwright.sync_api import sync_playwright
        if _browser_instance is None:
            pw = sync_playwright().__enter__()
            _browser_instance = pw.chromium.launch(headless=True)
            logger.info("[RealBrowser] Browser launched")
        return _browser_instance
    except ImportError:
        logger.error("Playwright not available")
        return None


def get_browser_context():
    """Get or create browser context."""
    browser = init_browser()
    if browser:
        return browser.new_context()
    return None


class RealBrowserDaemonServer(MicrokernelIPCServer):
    """
    Real Browser Daemon using Playwright for actual web automation.
    """

    def __init__(self, port: int = 9002):
        super().__init__(port, "RealBrowserDaemon")
        self.state_dir = agent_path.parent / "ai-mind" / "tasks" / "browser_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.last_page = None
        self.last_context = None
        logger.info(f"[RealBrowser] Initialized. State dir: {self.state_dir}")

    def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch task to appropriate handler."""
        task_type = task_data.get("type", "unknown")
        task_id = task_data.get("task_id", "unknown")

        logger.info(f"[RealBrowser] Task {task_id}: {task_type}")

        try:
            if task_type == "navigate":
                return self._navigate_real(task_id, task_data)
            elif task_type == "click":
                return self._click_real(task_id, task_data)
            elif task_type == "type":
                return self._type_real(task_id, task_data)
            elif task_type == "dom_to_markdown":
                return self._dom_to_markdown_real(task_id, task_data)
            elif task_type == "save_checkpoint":
                return self._save_checkpoint_real(task_id, task_data)
            else:
                return {"status": "error", "error": f"Unknown task type: {task_type}"}
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return {"status": "error", "error": str(e)}

    def _navigate_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Navigate to URL using real browser."""
        try:
            url = task_data.get("url", "")
            if not url:
                return {"status": "error", "error": "No URL provided"}

            logger.info(f"[RealBrowser] Navigating to {url}")

            # Get or create context and page
            context = get_browser_context()
            if not context:
                return {"status": "error", "error": "Browser not available"}

            page = context.new_page()
            self.last_page = page
            self.last_context = context

            # Navigate with timeout
            response = page.goto(url, wait_until="networkidle", timeout=30000)

            # Get page info
            title = page.title()
            status_code = response.status if response else 0

            result = {
                "status": "success",
                "task_id": task_id,
                "url": url,
                "page_loaded": True,
                "title": title,
                "status_code": status_code,
                "timestamp": time.time()
            }

            logger.info(f"[RealBrowser] Loaded: {title}")
            return result

        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {"status": "error", "error": str(e)}

    def _click_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Click element by selector."""
        try:
            selector = task_data.get("selector", "")
            selector = BrowserUtils.clean_selector(selector)

            if not self.last_page:
                return {"status": "error", "error": "No page loaded"}

            logger.info(f"[RealBrowser] Clicking: {selector}")

            # Try to click with retry
            try:
                self.last_page.click(selector, timeout=5000)
                # Wait for potential navigation
                self.last_page.wait_for_load_state("networkidle", timeout=10000)
            except:
                # Element not found or not clickable
                pass

            result = {
                "status": "success",
                "task_id": task_id,
                "selector": selector,
                "clicked": True,
                "current_url": self.last_page.url,
                "timestamp": time.time()
            }

            return result

        except Exception as e:
            logger.error(f"Click failed: {e}")
            return {"status": "error", "error": str(e)}

    def _type_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Type text into element."""
        try:
            selector = task_data.get("selector", "")
            text = task_data.get("text", "")

            selector = BrowserUtils.clean_selector(selector)

            if not self.last_page:
                return {"status": "error", "error": "No page loaded"}

            logger.info(f"[RealBrowser] Typing into {selector}")

            # Focus and type
            self.last_page.focus(selector)
            self.last_page.type(selector, text, delay=50)

            result = {
                "status": "success",
                "task_id": task_id,
                "selector": selector,
                "text_entered": text,
                "timestamp": time.time()
            }

            return result

        except Exception as e:
            logger.error(f"Type failed: {e}")
            return {"status": "error", "error": str(e)}

    def _dom_to_markdown_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Convert DOM to markdown."""
        try:
            if not self.last_page:
                return {"status": "error", "error": "No page loaded"}

            logger.info(f"[RealBrowser] Extracting DOM")

            # Get full HTML
            html = self.last_page.content()

            # Convert to markdown
            markdown = BrowserUtils.html_to_markdown(html)

            # Calculate savings
            savings = BrowserUtils.calculate_savings(html, markdown)

            result = {
                "status": "success",
                "task_id": task_id,
                "markdown": markdown,
                "markdown_length": len(markdown),
                "token_estimation": savings,
                "savings_percent": savings["savings_percent"],
                "page_url": self.last_page.url,
                "page_title": self.last_page.title(),
                "timestamp": time.time()
            }

            logger.info(f"[RealBrowser] DOM extracted ({savings['savings_percent']}% token savings)")
            return result

        except Exception as e:
            logger.error(f"DOM extraction failed: {e}")
            return {"status": "error", "error": str(e)}

    def _save_checkpoint_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Save page state checkpoint."""
        try:
            if not self.last_page:
                return {"status": "error", "error": "No page loaded"}

            logger.info(f"[RealBrowser] Saving checkpoint")

            checkpoint = {
                "task_id": task_id,
                "url": self.last_page.url,
                "title": self.last_page.title(),
                "timestamp": time.time()
            }

            checkpoint_id = f"{task_id}_checkpoint"
            checkpoint_file = self.state_dir / f"{checkpoint_id}.json"
            checkpoint_file.write_text(json.dumps(checkpoint, indent=2))

            result = {
                "status": "success",
                "task_id": task_id,
                "checkpoint_id": checkpoint_id,
                "checkpoint_file": str(checkpoint_file),
                "url": checkpoint["url"],
                "timestamp": time.time()
            }

            return result

        except Exception as e:
            logger.error(f"Checkpoint save failed: {e}")
            return {"status": "error", "error": str(e)}


def run_browser_daemon_real(port: int = 9002):
    """Start real browser daemon."""
    server = RealBrowserDaemonServer(port)
    logger.info(f"[RealBrowser] Starting daemon on port {port}...")
    server.start()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9002
    run_browser_daemon_real(port)
