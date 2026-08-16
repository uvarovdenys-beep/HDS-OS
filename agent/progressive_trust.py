#!/usr/bin/env python3
"""
progressive_trust.py
HDS Progressive Trust — dynamic promotion/demotion based on runtime performance.

Instead of fixed protocol assignment, models can EARN higher trust (promotion)
or LOSE trust (demotion) based on how well they perform tasks.

A model starts at its diagnostic-assigned level and can move up/down.
"""

import logging
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from model_router import ProtocolSize

logger = logging.getLogger("progressive_trust")

SIZE_ORDER = [ProtocolSize.S, ProtocolSize.M, ProtocolSize.L, ProtocolSize.XL]


@dataclass
class TrustRecord:
    """A record of task performance."""
    task_id: str
    assigned_size: ProtocolSize
    success: bool
    violations: int = 0       # Protocol violations during task
    quality_score: float = 0.0  # 0.0-1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ProgressiveTrust:
    """
    Manages dynamic trust levels for a model.

    Rules:
    - Start at diagnostic-assigned level
    - 3 consecutive successes at current level → eligible for promotion
    - 2 consecutive failures → immediate demotion
    - Any protocol violation → reset promotion counter
    - Cannot promote above diagnostic ceiling
    - Cannot demote below S

    Usage:
        trust = ProgressiveTrust("qwen3.5:9b", initial_size=ProtocolSize.M,
                                  ceiling=ProtocolSize.L)

        trust.record_result("T-001", success=True, quality_score=0.9)
        trust.record_result("T-002", success=True, quality_score=0.85)
        trust.record_result("T-003", success=True, quality_score=0.88)
        # After 3 successes: eligible for promotion

        print(trust.current_size)  # Might be L now
    """

    PROMOTE_THRESHOLD = 3     # Consecutive successes needed
    DEMOTE_THRESHOLD = 2      # Consecutive failures for demotion
    MIN_QUALITY_FOR_PROMOTE = 0.7  # Minimum quality score for promotion

    def __init__(self, model_name: str, initial_size: ProtocolSize,
                 ceiling: ProtocolSize = ProtocolSize.XL):
        """
        Args:
            model_name: Model identifier
            initial_size: Starting protocol size (from diagnostic)
            ceiling: Maximum size this model can be promoted to
        """
        self.model_name = model_name
        self.initial_size = initial_size
        self.current_size = initial_size
        self.ceiling = ceiling
        self.history: List[TrustRecord] = []

        self._consecutive_successes: int = 0
        self._consecutive_failures: int = 0
        self._promotions: int = 0
        self._demotions: int = 0

        self._log_path = Path("ai-mind/protocols/trust_log.json")

    def record_result(self, task_id: str, success: bool,
                      violations: int = 0, quality_score: float = 0.0) -> Optional[str]:
        """
        Record task result and check for promotion/demotion.

        Returns:
            Action taken: "promoted", "demoted", or None
        """
        record = TrustRecord(
            task_id=task_id,
            assigned_size=self.current_size,
            success=success,
            violations=violations,
            quality_score=quality_score,
        )
        self.history.append(record)

        action = None

        if violations > 0:
            # Any violation resets promotion counter
            self._consecutive_successes = 0
            logger.info(f"Trust: {violations} violations on '{task_id}', promotion counter reset")

        if success and violations == 0:
            self._consecutive_successes += 1
            self._consecutive_failures = 0

            if (self._consecutive_successes >= self.PROMOTE_THRESHOLD
                and quality_score >= self.MIN_QUALITY_FOR_PROMOTE):
                action = self._try_promote()
        else:
            self._consecutive_failures += 1
            self._consecutive_successes = 0

            if self._consecutive_failures >= self.DEMOTE_THRESHOLD:
                action = self._try_demote()

        return action

    def _try_promote(self) -> Optional[str]:
        """Attempt to promote model to next size level."""
        current_idx = SIZE_ORDER.index(self.current_size)
        ceiling_idx = SIZE_ORDER.index(self.ceiling)

        if current_idx >= ceiling_idx:
            logger.info(f"Trust: already at ceiling ({self.ceiling.value.upper()})")
            return None

        if current_idx + 1 < len(SIZE_ORDER):
            old_size = self.current_size
            self.current_size = SIZE_ORDER[current_idx + 1]
            self._promotions += 1
            self._consecutive_successes = 0

            logger.info(
                f"PROMOTED: {self.model_name} "
                f"{old_size.value.upper()} → {self.current_size.value.upper()}"
            )
            return "promoted"

        return None

    def _try_demote(self) -> Optional[str]:
        """Demote model to lower size level."""
        current_idx = SIZE_ORDER.index(self.current_size)

        if current_idx <= 0:
            logger.info("Trust: already at minimum (S)")
            return None

        old_size = self.current_size
        self.current_size = SIZE_ORDER[current_idx - 1]
        self._demotions += 1
        self._consecutive_failures = 0

        logger.warning(
            f"DEMOTED: {self.model_name} "
            f"{old_size.value.upper()} → {self.current_size.value.upper()}"
        )
        return "demoted"

    def get_status(self) -> Dict:
        """Current trust status."""
        return {
            "model": self.model_name,
            "initial_size": self.initial_size.value.upper(),
            "current_size": self.current_size.value.upper(),
            "ceiling": self.ceiling.value.upper(),
            "consecutive_successes": self._consecutive_successes,
            "consecutive_failures": self._consecutive_failures,
            "total_promotions": self._promotions,
            "total_demotions": self._demotions,
            "tasks_completed": len(self.history),
        }

    def save_log(self):
        """Save trust history to file."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "model": self.model_name,
                "status": self.get_status(),
                "history": [
                    {
                        "task_id": r.task_id,
                        "size": r.assigned_size.value.upper(),
                        "success": r.success,
                        "violations": r.violations,
                        "quality": r.quality_score,
                        "time": r.timestamp,
                    }
                    for r in self.history
                ],
            }
            with open(self._log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save trust log: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("HDS PROGRESSIVE TRUST — Demo")
    print("=" * 60)

    trust = ProgressiveTrust("qwen3.5:9b", initial_size=ProtocolSize.M,
                              ceiling=ProtocolSize.L)

    print(f"Start: {trust.get_status()['current_size']}")

    # Simulate 3 good tasks → promotion
    for i in range(3):
        action = trust.record_result(f"T-{i+1:03d}", success=True, quality_score=0.85)
        if action:
            print(f"  Task T-{i+1:03d}: {action}!")
        else:
            print(f"  Task T-{i+1:03d}: success (streak: {trust._consecutive_successes})")

    print(f"After 3 successes: {trust.get_status()['current_size']}")

    # Simulate 2 failures → demotion
    for i in range(3, 5):
        action = trust.record_result(f"T-{i+1:03d}", success=False, quality_score=0.3)
        if action:
            print(f"  Task T-{i+1:03d}: {action}!")
        else:
            print(f"  Task T-{i+1:03d}: failure (streak: {trust._consecutive_failures})")

    print(f"After 2 failures: {trust.get_status()['current_size']}")
    print(f"\nFull status: {json.dumps(trust.get_status(), indent=2)}")
