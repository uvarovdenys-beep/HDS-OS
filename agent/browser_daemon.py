#!/usr/bin/env python3
"""
browser_daemon.py
HDS Browser Daemon - REAL IMPLEMENTATION MANDATORY

⚠️  NO MOCKING ALLOWED
Policy: HDS operates only with real implementations.
If this import fails, the system will NOT fall back to mock.
It WILL FAIL TO START.

This is intentional.

Authors: HDS Development Team
License: HDS6 Standard
"""

import sys
from pathlib import Path

print("[Browser Daemon] Initializing REAL implementation...")
print("[Browser Daemon] Policy: NO MOCKING ALLOWED")
print()

# MANDATORY: Real implementation must be available
# NO FALLBACK, NO MOCK, FAIL IF MISSING
try:
    from browser_daemon_real import run_browser_daemon_real, RealBrowserDaemonServer
    print("[Browser Daemon] ✅ Real implementation loaded (browser_daemon_real)")
    print("[Browser Daemon] Status: REAL ONLY, NO MOCKS")

    # Expose for imports
    run_browser_daemon = run_browser_daemon_real
    BrowserDaemonServer = RealBrowserDaemonServer

except ImportError as e:
    print(f"[Browser Daemon] ❌ FATAL: Real implementation not available")
    print(f"[Browser Daemon] Error: {e}")
    print()
    print("HDS Policy: NO MOCKING. Real implementations are MANDATORY.")
    print()
    print("Required: Playwright, BeautifulSoup4, html2text")
    print("Install with: pip install playwright beautifulsoup4 html2text")
    print()
    print("SYSTEM WILL NOT CONTINUE. No mock fallback is allowed.")
    sys.exit(1)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9002
    run_browser_daemon(port)
