# vision.py
# HDS6 HDS Vision & Automation Module
# Purpose: Machine vision, screenshots and UI automation

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

try:
    import pyautogui
    from PIL import ImageGrab
except ImportError:
    pyautogui = None
    ImageGrab = None

class MARK_TWAIN_Vision:
    """
    Machine vision and automation module.
    Implements screenshot capture and mouse control.
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.screenshots_dir = base_dir / "AI-MIND" / "logs" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # pyautogui safety configuration
        if pyautogui:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.5

    def capture_screen(self, name_prefix: str = "ui_test") -> Optional[Path]:
        """Capture screenshot."""
        if not ImageGrab:
            print("[ERROR] PIL (Pillow) not installed. Cannot capture screen.")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name_prefix}_{timestamp}.png"
        filepath = self.screenshots_dir / filename
        
        try:
            screenshot = ImageGrab.grab()
            screenshot.save(filepath)
            print(f"[OK] Screenshot saved: {filepath.name}")
            return filepath
        except Exception as e:
            print(f"[ERROR] Failed to capture screen: {e}")
            return None

    def move_and_click(self, x: int, y: int, clicks: int = 1):
        """Move mouse and click (with safety logging)."""
        if not pyautogui:
            print("[ERROR] pyautogui not installed. Cannot move mouse.")
            return
            
        try:
            print(f"[VISION] Moving mouse to ({x}, {y}) and clicking {clicks} times")
            pyautogui.moveTo(x, y, duration=1.0)
            pyautogui.click(clicks=clicks)
        except Exception as e:
            print(f"[ERROR] Mouse action failed: {e}")

    def type_text(self, text: str):
        """Emulate text input."""
        if not pyautogui:
            return
            
        try:
            pyautogui.write(text, interval=0.1)
        except Exception as e:
            print(f"[ERROR] Typing failed: {e}")

    def analyze_ui_with_ai(self, screenshot_path: Path):
        """
        Prepare for UI analysis via AI (Gemini Vision / GPT-4V).
        Returns structure for universal_ai_interface.
        """
        # This will be called through universal_ai_interface.py
        return {
            "type": "vision_analysis",
            "image_path": str(screenshot_path),
            "task": "Identify UI elements and state"
        }
