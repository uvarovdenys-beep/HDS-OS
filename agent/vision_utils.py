#!/usr/bin/env python3
"""
vision_utils.py
HDS Vision Utilities - Real image processing helpers

Provides utility functions for:
- Screen capture
- Image analysis
- Element detection
- OCR text extraction

Authors: HDS Development Team
License: HDS6 Standard
"""

import numpy as np
from PIL import Image
import cv2
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging

logger = logging.getLogger(__name__)


class VisionUtils:
    """Utility class for computer vision operations."""

    @staticmethod
    def load_image(image_path: str) -> Optional[np.ndarray]:
        """Load image from file using OpenCV."""
        try:
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to load image: {image_path}")
                return None
            return img
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None

    @staticmethod
    def detect_buttons(image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect button-like elements using edge detection and contours.
        Returns list of detected buttons with bounding boxes.
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)

            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            buttons = []
            h, w = image.shape[:2]

            for contour in contours:
                x, y, width, height = cv2.boundingRect(contour)

                # Filter by size (buttons are typically 30-300px)
                if 30 < width < 300 and 20 < height < 100:
                    # Check if aspect ratio looks like a button
                    aspect_ratio = width / height if height > 0 else 0
                    if 0.5 < aspect_ratio < 3.0:
                        # Convert to relative coordinates (0.0-1.0)
                        bbox_relative = (
                            x / w,
                            y / h,
                            (x + width) / w,
                            (y + height) / h
                        )

                        buttons.append({
                            "type": "button",
                            "bbox_relative": bbox_relative,
                            "bbox_absolute": (x, y, x + width, y + height),
                            "confidence": 0.7
                        })

            return buttons[:10]  # Return top 10 buttons
        except Exception as e:
            logger.error(f"Error detecting buttons: {e}")
            return []

    @staticmethod
    def detect_input_fields(image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect input field-like elements (text boxes).
        Returns list of detected input fields with bounding boxes.
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Apply adaptive thresholding to find text-like regions
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 11, 2)

            # Find contours
            contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            inputs = []
            h, w = image.shape[:2]

            for contour in contours:
                x, y, width, height = cv2.boundingRect(contour)

                # Filter by size (input fields are typically tall and narrow)
                if 40 < width < 500 and 25 < height < 60:
                    aspect_ratio = width / height if height > 0 else 0
                    # Input fields are usually wider than tall
                    if aspect_ratio > 1.5:
                        bbox_relative = (
                            x / w,
                            y / h,
                            (x + width) / w,
                            (y + height) / h
                        )

                        inputs.append({
                            "type": "input",
                            "bbox_relative": bbox_relative,
                            "bbox_absolute": (x, y, x + width, y + height),
                            "confidence": 0.65
                        })

            return inputs[:10]  # Return top 10 inputs
        except Exception as e:
            logger.error(f"Error detecting input fields: {e}")
            return []

    @staticmethod
    def get_image_metadata(image: np.ndarray) -> Dict[str, Any]:
        """Extract metadata from image."""
        try:
            h, w = image.shape[:2]
            channels = image.shape[2] if len(image.shape) == 3 else 1

            return {
                "width": int(w),
                "height": int(h),
                "channels": int(channels),
                "format": "BGR" if channels == 3 else "Grayscale",
                "size_bytes": image.nbytes
            }
        except Exception as e:
            logger.error(f"Error getting image metadata: {e}")
            return {}

    @staticmethod
    def analyze_colors(image: np.ndarray) -> Dict[str, Any]:
        """Analyze color distribution in image."""
        try:
            # Calculate histogram
            hist_b = cv2.calcHist([image], [0], None, [256], [0, 256])
            hist_g = cv2.calcHist([image], [1], None, [256], [0, 256])
            hist_r = cv2.calcHist([image], [2], None, [256], [0, 256])

            # Get dominant colors
            b_mean = np.mean(image[:, :, 0])
            g_mean = np.mean(image[:, :, 1])
            r_mean = np.mean(image[:, :, 2])

            return {
                "dominant_color": {
                    "R": int(r_mean),
                    "G": int(g_mean),
                    "B": int(b_mean)
                },
                "color_distribution": "analyzed"
            }
        except Exception as e:
            logger.error(f"Error analyzing colors: {e}")
            return {}

    @staticmethod
    def detect_text_regions(image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect regions that likely contain text."""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Use MSER (Maximally Stable Extremal Regions) detector
            mser = cv2.MSER_create()
            regions, _ = mser.detectRegions(gray)

            text_regions = []
            h, w = image.shape[:2]

            for region in regions[:15]:  # Top 15 regions
                x, y = region.min(axis=0)
                x_max, y_max = region.max(axis=0)

                width = x_max - x
                height = y_max - y

                # Filter regions that look like text
                if 10 < width < 400 and 5 < height < 100:
                    bbox_relative = (
                        x / w,
                        y / h,
                        x_max / w,
                        y_max / h
                    )

                    text_regions.append({
                        "type": "text_region",
                        "bbox_relative": bbox_relative,
                        "confidence": 0.6
                    })

            return text_regions
        except Exception as e:
            logger.error(f"Error detecting text regions: {e}")
            return []


class OCRHelper:
    """OCR text extraction helper."""

    @staticmethod
    def extract_text_simple(image: np.ndarray) -> str:
        """
        Simple text extraction using contours.
        This is a fallback when Tesseract is not available.
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

            # Simple approximation: if the image has mostly dark text, return "contains text"
            dark_pixels = np.sum(binary == 0)
            total_pixels = binary.shape[0] * binary.shape[1]
            text_ratio = dark_pixels / total_pixels

            if text_ratio > 0.1:
                return "Text detected (OCR unavailable)"
            else:
                return "No significant text detected"
        except Exception as e:
            logger.error(f"Error in simple text extraction: {e}")
            return "Error processing image"

    @staticmethod
    def try_extract_text(image_path: str) -> str:
        """
        Try to extract text using Tesseract if available, fall back to simple method.
        """
        try:
            import pytesseract
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text.strip() if text else "No text found"
        except ImportError:
            logger.warning("Tesseract not available, using fallback")
            image = cv2.imread(image_path)
            if image is not None:
                return OCRHelper.extract_text_simple(image)
            return "Failed to load image"
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return f"Error: {str(e)}"
