#!/usr/bin/env python3
"""
degradation_detector.py
HDS Degradation Detector — detects model quality loss mid-session.

Monitors model behavior over time and flags when quality drops.
Uses lightweight canary checks embedded between real tasks.
"""

import logging
import time
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("degradation_detector")


@dataclass
class QualitySnapshot:
    """A snapshot of model quality at a point in time."""
    timestamp: float
    instruction_followed: bool   # Did model follow instructions exactly?
    output_clean: bool           # Was output format clean (no extra text)?
    context_retained: bool       # Did model remember earlier context?
    response_time: float         # Seconds to respond
    token_count: int             # Response length
    score: float = 0.0          # Computed quality score 0.0-1.0

    def compute_score(self):
        """Compute overall quality score."""
        points = 0
        if self.instruction_followed: points += 3
        if self.output_clean: points += 2
        if self.context_retained: points += 3
        # Penalize very slow responses (possible confusion)
        if self.response_time < 30: points += 1
        if self.response_time < 10: points += 1
        self.score = points / 10.0


class DegradationDetector:
    """
    Monitors model quality over a session.

    Usage:
        detector = DegradationDetector(threshold=0.3)

        # After each task, record quality:
        detector.record(instruction_followed=True, output_clean=True,
                       context_retained=True, response_time=5.2, token_count=150)

        # Check if model is degrading:
        if detector.is_degrading():
            print("WARNING: Model quality dropping!")
            print(detector.get_recommendation())
    """

    def __init__(self, threshold: float = 0.3, window_size: int = 5):
        """
        Args:
            threshold: Quality drop threshold to trigger alert (0.0-1.0).
                      0.3 means alert if quality drops by 30% from baseline.
            window_size: Number of recent snapshots to average for current quality.
        """
        self.threshold = threshold
        self.window_size = window_size
        self.snapshots: List[QualitySnapshot] = []
        self.baseline_score: Optional[float] = None
        self._degradation_count: int = 0

    def record(self, instruction_followed: bool, output_clean: bool,
               context_retained: bool, response_time: float,
               token_count: int) -> QualitySnapshot:
        """Record a quality observation."""
        snap = QualitySnapshot(
            timestamp=time.time(),
            instruction_followed=instruction_followed,
            output_clean=output_clean,
            context_retained=context_retained,
            response_time=response_time,
            token_count=token_count,
        )
        snap.compute_score()
        self.snapshots.append(snap)

        # Set baseline from first few snapshots
        if len(self.snapshots) <= 3:
            scores = [s.score for s in self.snapshots]
            self.baseline_score = sum(scores) / len(scores)

        logger.debug(f"Quality snapshot: score={snap.score:.2f}, baseline={self.baseline_score}")
        return snap

    def current_quality(self) -> float:
        """Average quality over recent window."""
        if not self.snapshots:
            return 1.0
        recent = self.snapshots[-self.window_size:]
        return sum(s.score for s in recent) / len(recent)

    def is_degrading(self) -> bool:
        """Check if model quality has dropped below threshold from baseline."""
        if self.baseline_score is None or len(self.snapshots) < 3:
            return False

        current = self.current_quality()
        drop = self.baseline_score - current

        if drop >= self.threshold:
            self._degradation_count += 1
            logger.warning(
                f"Degradation detected: baseline={self.baseline_score:.2f}, "
                f"current={current:.2f}, drop={drop:.2f}"
            )
            return True
        return False

    def get_recommendation(self) -> str:
        """Get recommendation based on current degradation state."""
        if not self.is_degrading():
            return "Model quality is stable. No action needed."

        current = self.current_quality()

        if current < 0.3:
            return ("CRITICAL: Model quality severely degraded. "
                    "Recommend: restart session or switch to smaller protocol context.")
        elif current < 0.5:
            return ("WARNING: Model quality declining. "
                    "Recommend: reduce task complexity or add verification steps.")
        else:
            return ("NOTICE: Slight quality drop detected. "
                    "Recommend: monitor closely, consider checkpoint.")

    def get_report(self) -> Dict:
        """Full degradation report."""
        return {
            "total_snapshots": len(self.snapshots),
            "baseline_score": round(self.baseline_score or 0, 3),
            "current_quality": round(self.current_quality(), 3),
            "is_degrading": self.is_degrading(),
            "degradation_events": self._degradation_count,
            "recommendation": self.get_recommendation(),
            "snapshots_summary": [
                {"time": s.timestamp, "score": round(s.score, 2)}
                for s in self.snapshots[-10:]
            ],
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("HDS DEGRADATION DETECTOR — Demo")
    print("=" * 60)

    detector = DegradationDetector(threshold=0.3)

    # Simulate good start
    for i in range(3):
        detector.record(True, True, True, 5.0, 200)
    print(f"Baseline: {detector.baseline_score:.2f}")
    print(f"Degrading: {detector.is_degrading()}")

    # Simulate gradual degradation
    detector.record(True, True, False, 15.0, 300)   # Lost context
    detector.record(True, False, False, 20.0, 500)   # Dirty output + lost context
    detector.record(False, False, False, 30.0, 800)  # Everything wrong

    print(f"\nAfter degradation:")
    print(f"Current quality: {detector.current_quality():.2f}")
    print(f"Degrading: {detector.is_degrading()}")
    print(f"Recommendation: {detector.get_recommendation()}")
