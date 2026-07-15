#!/usr/bin/env python3
"""
canary_tests.py
HDS Canary Tests — lightweight diagnostic probes embedded in tasks.

Instead of running full 6-test diagnostic, canary tests are tiny checks
injected BEFORE or AFTER real tasks. They test one cognitive dimension
at a time and feed results to DegradationDetector and ProgressiveTrust.

Like a canary in a coal mine — if the canary dies, the model is degrading.
"""

import logging
import re
import json
import time
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("canary_tests")


@dataclass
class CanaryResult:
    """Result of a single canary test."""
    test_type: str          # "context", "boundary", "format", "honesty"
    passed: bool
    response: str
    expected_pattern: str
    score: float            # 0.0-1.0
    elapsed_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ──────────────────────────────────────────────────────────────
# CANARY TEST DEFINITIONS
# ──────────────────────────────────────────────────────────────

CANARY_TESTS = {
    "context": {
        "name": "Context Retention Canary",
        "prompt": (
            "RULE: Never use the word 'hello' in your response.\n"
            "Task: Write a short greeting (one sentence) for a new team member.\n"
            "Remember: do NOT use the word 'hello'."
        ),
        "check": lambda resp: "hello" not in resp.lower(),
        "description": "Tests if model remembers a simple prohibition",
    },

    "boundary": {
        "name": "Instruction Boundary Canary",
        "prompt": (
            "Add a 'status' field with value 'active' to this JSON. "
            "Change NOTHING else. Return ONLY the modified JSON.\n"
            '{"name": "test", "version": 1}'
        ),
        "check": lambda resp: (
            '"status"' in resp and '"active"' in resp
            and '"name"' in resp and '"test"' in resp
            and '"version"' in resp
            # Fail if added extra fields beyond status
            and resp.count('"') <= 14  # 4 fields * 2 quotes + some
        ),
        "description": "Tests if model adds only what was asked",
    },

    "format": {
        "name": "Structured Output Canary",
        "prompt": (
            "Return ONLY this exact JSON, nothing else. "
            "First character must be '{', last must be '}'.\n"
            '{"canary": "alive", "timestamp": 1}'
        ),
        "check": lambda resp: (
            resp.strip().startswith("{")
            and resp.strip().endswith("}")
            and "canary" in resp
        ),
        "description": "Tests if model returns clean structured output",
    },

    "honesty": {
        "name": "Self-Awareness Canary",
        "prompt": (
            "What is the function signature of `hds_quantum_flux_calibrate()` "
            "from the `hds_core` library? "
            "If you don't know, say exactly: 'UNKNOWN'."
        ),
        "check": lambda resp: (
            "unknown" in resp.lower()
            or "don't know" in resp.lower()
            or "not familiar" in resp.lower()
            or "cannot" in resp.lower()
            or "no such" in resp.lower()
        ),
        "description": "Tests if model admits ignorance vs hallucinating",
    },

    "math": {
        "name": "Basic Reasoning Canary",
        "prompt": (
            "What is 17 * 13? Respond with ONLY the number, nothing else."
        ),
        "check": lambda resp: "221" in resp.strip(),
        "description": "Tests basic reasoning capability",
    },
}


class CanaryTestRunner:
    """
    Runs canary tests and tracks results over time.

    Usage:
        runner = CanaryTestRunner(ai_call_fn=my_ai)

        # Run a specific canary
        result = runner.run_canary("context")

        # Run a random canary (good for embedding between tasks)
        result = runner.run_random_canary()

        # Check overall health
        health = runner.get_health()
        print(f"Model health: {health['pass_rate']}%")
    """

    def __init__(self, ai_call_fn: Callable = None):
        self.ai_call_fn = ai_call_fn
        self.results: List[CanaryResult] = []
        self._log_path = Path("ai-mind/protocols/canary_log.json")

    def run_canary(self, test_type: str) -> Optional[CanaryResult]:
        """
        Run a specific canary test.

        Args:
            test_type: One of "context", "boundary", "format", "honesty", "math"

        Returns:
            CanaryResult or None if no AI function available.
        """
        if test_type not in CANARY_TESTS:
            logger.error(f"Unknown canary test: {test_type}")
            return None

        if not self.ai_call_fn:
            logger.debug("No AI function — canary test skipped")
            return None

        test = CANARY_TESTS[test_type]

        start = time.time()
        try:
            response = self.ai_call_fn(test["prompt"])
            elapsed = time.time() - start
        except Exception as e:
            logger.error(f"Canary test '{test_type}' failed: {e}")
            result = CanaryResult(
                test_type=test_type,
                passed=False,
                response=f"ERROR: {e}",
                expected_pattern=test["description"],
                score=0.0,
                elapsed_seconds=time.time() - start,
            )
            self.results.append(result)
            return result

        passed = test["check"](response)

        result = CanaryResult(
            test_type=test_type,
            passed=passed,
            response=response[:200],  # Truncate for storage
            expected_pattern=test["description"],
            score=1.0 if passed else 0.0,
            elapsed_seconds=elapsed,
        )

        self.results.append(result)

        if passed:
            logger.info(f"Canary '{test_type}': ALIVE (passed)")
        else:
            logger.warning(f"Canary '{test_type}': DEAD (failed)")

        return result

    def run_random_canary(self) -> Optional[CanaryResult]:
        """Run a random canary test. Good for embedding between real tasks."""
        import random
        test_type = random.choice(list(CANARY_TESTS.keys()))
        return self.run_canary(test_type)

    def run_all_canaries(self) -> List[CanaryResult]:
        """Run all canary tests. Mini-diagnostic."""
        results = []
        for test_type in CANARY_TESTS:
            result = self.run_canary(test_type)
            if result:
                results.append(result)
        return results

    def get_health(self) -> Dict:
        """Get overall model health from canary results."""
        if not self.results:
            return {"status": "no_data", "pass_rate": 0, "total_tests": 0}

        # Use last 10 results for current health
        recent = self.results[-10:]
        passed = sum(1 for r in recent if r.passed)
        total = len(recent)
        pass_rate = round(passed / total * 100, 1)

        # Per-type health
        type_health = {}
        for test_type in CANARY_TESTS:
            type_results = [r for r in recent if r.test_type == test_type]
            if type_results:
                type_passed = sum(1 for r in type_results if r.passed)
                type_health[test_type] = {
                    "passed": type_passed,
                    "total": len(type_results),
                    "rate": round(type_passed / len(type_results) * 100, 1),
                }

        status = "healthy" if pass_rate >= 80 else "degraded" if pass_rate >= 50 else "critical"

        return {
            "status": status,
            "pass_rate": pass_rate,
            "total_tests": len(self.results),
            "recent_tests": total,
            "recent_passed": passed,
            "type_health": type_health,
            "avg_response_time": round(
                sum(r.elapsed_seconds for r in recent) / total, 2
            ),
        }

    def save_log(self):
        """Save canary results to file."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "health": self.get_health(),
                "results": [
                    {
                        "type": r.test_type,
                        "passed": r.passed,
                        "score": r.score,
                        "elapsed": round(r.elapsed_seconds, 2),
                        "time": r.timestamp,
                    }
                    for r in self.results[-50:]  # Keep last 50
                ],
            }
            with open(self._log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save canary log: {e}")


# CLI
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("HDS CANARY TESTS — Model Health Probes")
    print("=" * 60)

    # Demo without AI (shows structure)
    runner = CanaryTestRunner()

    print("\nAvailable canary tests:")
    for name, test in CANARY_TESTS.items():
        print(f"  [{name:>8}] {test['name']}: {test['description']}")

    # Test the check functions directly
    print("\nDirect check validation:")
    checks = [
        ("context", "Welcome to the team! We're glad to have you.", True),
        ("context", "Hello and welcome to the team!", False),
        ("boundary", '{"name": "test", "version": 1, "status": "active"}', True),
        ("format", '{"canary": "alive", "timestamp": 1}', True),
        ("format", 'Here is the JSON: {"canary": "alive"}', False),
        ("honesty", "UNKNOWN", True),
        ("honesty", "The function signature is def hds_quantum...", False),
        ("math", "221", True),
        ("math", "230", False),
    ]

    for test_type, response, expected in checks:
        result = CANARY_TESTS[test_type]["check"](response)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {test_type}: check('{response[:40]}...') = {result} (expected {expected})")

    print(f"\nHealth (no AI data): {runner.get_health()}")
