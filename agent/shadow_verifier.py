#!/usr/bin/env python3
"""
shadow_verifier.py
HDS Shadow Verifier — silent verification of lower-size task results.

Concept: After an S/M-level task completes, re-verify the result using
a higher protocol context (L/XL rules). This catches errors that a
simpler protocol context might miss.

IMPORTANT: This is NOT multi-model. Same model, different protocol context.
The model "reviews its own work" wearing stricter reviewer hat.
"""

import logging
import json
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from model_router import ProtocolSize, get_boot_prompt

logger = logging.getLogger("shadow_verifier")

SIZE_ORDER = [ProtocolSize.S, ProtocolSize.M, ProtocolSize.L, ProtocolSize.XL]


@dataclass
class VerificationResult:
    """Result of shadow verification."""
    task_id: str
    original_size: ProtocolSize
    verification_size: ProtocolSize
    passed: bool
    issues: List[str]
    confidence: float  # 0.0-1.0
    timestamp: str


class ShadowVerifier:
    """
    Silently verifies task results using higher protocol context.

    Flow:
    1. S/M model completes task with result
    2. ShadowVerifier constructs a verification prompt
    3. Same model reviews the result with L/XL context
    4. If issues found → task flagged for correction

    Usage:
        verifier = ShadowVerifier(ai_call_fn=my_ai_function)

        result = verifier.verify(
            task_id="T-001",
            original_size=ProtocolSize.S,
            task_description="Add import for logging in agent.py",
            task_result="Added 'import logging' at line 3",
            target_files=["agent/agent.py"],
        )

        if not result.passed:
            print(f"Issues found: {result.issues}")
    """

    VERIFICATION_PROMPT_TEMPLATE = """You are a code reviewer operating at {verify_size} level.

Review the following task result for correctness, completeness, and safety.

TASK: {task_description}
TARGET FILES: {target_files}

RESULT SUBMITTED:
{task_result}

Check for:
1. Does the result actually accomplish the task?
2. Are there any obvious errors or omissions?
3. Could this change break existing functionality?
4. Is the change minimal and focused (no unnecessary additions)?

Respond ONLY with valid JSON:
{{"passed": true/false, "issues": ["issue1", "issue2"], "confidence": 0.0-1.0}}
"""

    def __init__(self, ai_call_fn: Callable = None, fail_closed: bool = True):
        self.ai_call_fn = ai_call_fn
        # fail_closed=True (default): on doubt — no verifier, parse error,
        # exception, or a verifier that does not explicitly say "passed" — the
        # result is treated as FAILED. A containment system must not pass work
        # it could not verify. Set fail_closed=False only for dry runs.
        self.fail_closed = fail_closed
        self.results: List[VerificationResult] = []
        self._log_path = Path("ai-mind/tasks/shadow_verification_log.json")

    def _get_verification_size(self, original: ProtocolSize) -> ProtocolSize:
        """Get the size level to use for verification (one level up)."""
        idx = SIZE_ORDER.index(original)
        verify_idx = min(idx + 1, len(SIZE_ORDER) - 1)
        return SIZE_ORDER[verify_idx]

    def should_verify(self, original_size: ProtocolSize) -> bool:
        """Determine if a task needs shadow verification."""
        # Verify S and M level tasks
        # L and XL are self-verifying
        return original_size in (ProtocolSize.S, ProtocolSize.M)

    def verify(self, task_id: str, original_size: ProtocolSize,
               task_description: str, task_result: str,
               target_files: List[str] = None) -> VerificationResult:
        """
        Verify a task result using higher protocol context.

        Returns VerificationResult with pass/fail and issues.
        """
        verify_size = self._get_verification_size(original_size)

        if not self.ai_call_fn:
            # No verifier configured. fail_closed → block (cannot verify);
            # fail_open → pass (explicit dry-run opt-out only).
            passed = not self.fail_closed
            result = VerificationResult(
                task_id=task_id,
                original_size=original_size,
                verification_size=verify_size,
                passed=passed,
                issues=[] if passed else ["No verifier configured (fail-closed)"],
                confidence=0.0,
                timestamp=datetime.now().isoformat(),
            )
            self.results.append(result)
            return result

        # Build verification prompt
        prompt = self.VERIFICATION_PROMPT_TEMPLATE.format(
            verify_size=verify_size.value.upper(),
            task_description=task_description,
            target_files=", ".join(target_files or []),
            task_result=task_result,
        )

        try:
            response = self.ai_call_fn(prompt)
            parsed = self._parse_response(response)

            result = VerificationResult(
                task_id=task_id,
                original_size=original_size,
                verification_size=verify_size,
                # Missing "passed" → do NOT assume success: default to fail when
                # fail_closed. A verifier that did not say "passed" did not pass.
                passed=parsed.get("passed", not self.fail_closed),
                issues=parsed.get("issues", []),
                confidence=parsed.get("confidence", 0.5),
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.error(f"Shadow verification failed for {task_id}: {e}")
            result = VerificationResult(
                task_id=task_id,
                original_size=original_size,
                verification_size=verify_size,
                passed=not self.fail_closed,  # fail-closed by default
                issues=[f"Verification error: {str(e)}"],
                confidence=0.0,
                timestamp=datetime.now().isoformat(),
            )

        self.results.append(result)
        self._save_log()

        if not result.passed:
            logger.warning(
                f"Shadow verification FAILED for {task_id}: {result.issues}"
            )
        else:
            logger.info(f"Shadow verification passed for {task_id}")

        return result

    def _parse_response(self, response: str) -> Dict:
        """Parse AI verification response."""
        import re
        # Try clean JSON first
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown
        match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Unparseable: omit "passed" so the caller's fail-closed default decides
        # (do NOT assume pass — an unreadable verdict is not a passing verdict).
        return {"issues": ["Could not parse verification response"], "confidence": 0.0}

    def get_stats(self) -> Dict:
        """Get verification statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        return {
            "total_verifications": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "common_issues": self._get_common_issues(),
        }

    def _get_common_issues(self) -> List[str]:
        """Get most common issues across all verifications."""
        from collections import Counter
        all_issues = []
        for r in self.results:
            all_issues.extend(r.issues)
        return [issue for issue, _ in Counter(all_issues).most_common(5)]

    def _save_log(self):
        """Save verification log."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "stats": self.get_stats(),
                "results": [
                    {
                        "task_id": r.task_id,
                        "original_size": r.original_size.value.upper(),
                        "verify_size": r.verification_size.value.upper(),
                        "passed": r.passed,
                        "issues": r.issues,
                        "confidence": r.confidence,
                        "time": r.timestamp,
                    }
                    for r in self.results[-50:]  # Keep last 50
                ],
            }
            with open(self._log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save verification log: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("HDS SHADOW VERIFIER — Demo")
    print("=" * 60)

    verifier = ShadowVerifier()

    # Demo verifications (dry run, no AI)
    tasks = [
        ("T-001", ProtocolSize.S, "Add import logging", "Added import logging at line 1"),
        ("T-002", ProtocolSize.M, "Create test function", "Created test_auth() with 3 assertions"),
        ("T-003", ProtocolSize.L, "Implement error handler", "Added try/except in daemon"),
    ]

    for tid, size, desc, result in tasks:
        should = verifier.should_verify(size)
        print(f"\n  {tid} ({size.value.upper()}): verify={should}")
        if should:
            vr = verifier.verify(tid, size, desc, result)
            print(f"    Result: {'PASS' if vr.passed else 'FAIL'}")

    print(f"\n  Stats: {json.dumps(verifier.get_stats(), indent=2)}")
