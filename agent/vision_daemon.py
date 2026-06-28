#!/usr/bin/env python3
"""
vision_daemon.py
HDS Vision Daemon - REAL IMPLEMENTATION MANDATORY

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

print("[Vision Daemon] Initializing REAL implementation...")
print("[Vision Daemon] Policy: NO MOCKING ALLOWED")
print()

# MANDATORY: Real implementation must be available
# NO FALLBACK, NO MOCK, FAIL IF MISSING
try:
    from vision_daemon_real import run_vision_daemon_real, RealVisionDaemonServer
    print("[Vision Daemon] ✅ Real implementation loaded (vision_daemon_real)")
    print("[Vision Daemon] Status: REAL ONLY, NO MOCKS")

    # Expose for imports
    run_vision_daemon = run_vision_daemon_real
    VisionDaemonServer = RealVisionDaemonServer

except ImportError as e:
    print(f"[Vision Daemon] ❌ FATAL: Real implementation not available")
    print(f"[Vision Daemon] Error: {e}")
    print()
    print("HDS Policy: NO MOCKING. Real implementations are MANDATORY.")
    print()
    print("Required: OpenCV, PyAutoGUI, Tesseract")
    print("Install with: pip install opencv-python pyautogui pytesseract")
    print()
    print("SYSTEM WILL NOT CONTINUE. No mock fallback is allowed.")
    sys.exit(1)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
    run_vision_daemon(port)
