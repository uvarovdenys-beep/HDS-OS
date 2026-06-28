#!/usr/bin/env python3
"""
vision_daemon_real.py
HDS Real Vision Daemon - Computer Vision with OpenCV + Tesseract

Replaces mock implementations with real vision processing:
- Screen capture with PyAutoGUI
- Image analysis with OpenCV + PIL
- Element detection using computer vision
- Text extraction with Tesseract (fallback: simple analysis)

Authors: HDS Development Team
License: HDS6 Standard
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any
from collections import deque
import logging

# Add agent path
agent_path = Path(__file__).parent
sys.path.insert(0, str(agent_path))

from microkernel_ipc import MicrokernelIPCServer, DaemonType
from vision_utils import VisionUtils, OCRHelper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealVisionDaemonServer(MicrokernelIPCServer):
    """
    Real Vision Daemon using OpenCV for actual image processing.
    Captures real screens and performs genuine computer vision tasks.
    """

    def __init__(self, port: int = 9001):
        super().__init__(port, "RealVisionDaemon")
        self.memory = deque(maxlen=10)  # Keep last 10 screenshots
        self.captures_dir = agent_path.parent / "ai-mind" / "tasks" / "captures"
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[RealVision] Initialized. Saves to {self.captures_dir}")

    def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch task to appropriate handler."""
        task_type = task_data.get("type", "unknown")
        task_id = task_data.get("task_id", "unknown")

        logger.info(f"[RealVision] Task {task_id}: {task_type}")

        if task_type == "capture_screen":
            return self._capture_screen_real(task_id, task_data)
        elif task_type == "analyze_image":
            return self._analyze_image_real(task_id, task_data)
        elif task_type == "detect_elements":
            return self._detect_elements_real(task_id, task_data)
        else:
            return {"status": "error", "error": f"Unknown task type: {task_type}"}

    def _capture_screen_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """
        Capture real screen using PyAutoGUI.
        Returns actual screenshot with metadata.
        """
        try:
            import pyautogui

            logger.info(f"[RealVision] Capturing screen for task {task_id}...")

            # Get screen dimensions
            screen_width, screen_height = pyautogui.size()

            # Capture screenshot
            screenshot = pyautogui.screenshot()

            # Save to disk
            filename = f"screenshot_{task_id}.png"
            filepath = self.captures_dir / filename
            screenshot.save(str(filepath))

            self.memory.append(filename)

            result = {
                "status": "success",
                "task_id": task_id,
                "filename": filename,
                "filepath": str(filepath),
                "width": screen_width,
                "height": screen_height,
                "format": "PNG",
                "memory_size": len(self.memory),
                "timestamp": time.time()
            }

            logger.info(f"[RealVision] Screenshot saved: {filename} ({screen_width}x{screen_height})")
            return result

        except ImportError:
            return {
                "status": "error",
                "error": "PyAutoGUI not available for screen capture"
            }
        except Exception as e:
            logger.error(f"[RealVision] Screen capture failed: {e}")
            return {"status": "error", "error": str(e)}

    def _analyze_image_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """
        Analyze image using real computer vision.
        Extracts text (OCR), detects objects, analyzes colors.
        """
        try:
            import cv2

            image_path = task_data.get("image_path", "unknown")

            logger.info(f"[RealVision] Analyzing image: {image_path}")

            # Load image
            image = VisionUtils.load_image(image_path)
            if image is None:
                return {
                    "status": "error",
                    "error": f"Failed to load image: {image_path}"
                }

            # Extract text with OCR
            text_content = OCRHelper.try_extract_text(image_path)

            # Get image metadata
            metadata = VisionUtils.get_image_metadata(image)

            # Analyze colors
            colors = VisionUtils.analyze_colors(image)

            # Detect buttons and inputs
            buttons = VisionUtils.detect_buttons(image)
            inputs = VisionUtils.detect_input_fields(image)

            result = {
                "status": "success",
                "task_id": task_id,
                "image": image_path,
                "analysis": {
                    "text_content": text_content,
                    "detected_buttons": len(buttons),
                    "detected_inputs": len(inputs),
                    "has_text": len(text_content) > 20,
                    "metadata": metadata,
                    "colors": colors,
                    "confidence": 0.85
                },
                "buttons_found": buttons[:3],  # Top 3
                "inputs_found": inputs[:3],    # Top 3
                "timestamp": time.time()
            }

            logger.info(f"[RealVision] Analysis complete: {len(buttons)} buttons, {len(inputs)} inputs")
            return result

        except Exception as e:
            logger.error(f"[RealVision] Image analysis failed: {e}")
            return {"status": "error", "error": str(e)}

    def _detect_elements_real(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """
        Detect UI elements on screen/image.
        Returns precise bounding boxes with relative coordinates (0.0-1.0).
        """
        try:
            image_path = task_data.get("image_path", "unknown")

            logger.info(f"[RealVision] Detecting elements in: {image_path}")

            # Load image
            image = VisionUtils.load_image(image_path)
            if image is None:
                return {
                    "status": "error",
                    "error": f"Failed to load image: {image_path}"
                }

            # Detect UI elements
            buttons = VisionUtils.detect_buttons(image)
            inputs = VisionUtils.detect_input_fields(image)
            text_regions = VisionUtils.detect_text_regions(image)

            # Combine all detections
            all_elements = buttons + inputs + text_regions

            # Sort by confidence
            all_elements.sort(key=lambda x: x.get("confidence", 0), reverse=True)

            result = {
                "status": "success",
                "task_id": task_id,
                "image": image_path,
                "elements": all_elements[:15],  # Top 15 elements
                "element_count": len(all_elements),
                "detection_summary": {
                    "buttons": len(buttons),
                    "inputs": len(inputs),
                    "text_regions": len(text_regions)
                },
                "timestamp": time.time()
            }

            logger.info(f"[RealVision] Detected {len(all_elements)} elements")
            return result

        except Exception as e:
            logger.error(f"[RealVision] Element detection failed: {e}")
            return {"status": "error", "error": str(e)}


def run_vision_daemon_real(port: int = 9001):
    """Start real vision daemon."""
    server = RealVisionDaemonServer(port)
    logger.info(f"[RealVision] Starting daemon on port {port}...")
    server.start()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
    run_vision_daemon_real(port)
