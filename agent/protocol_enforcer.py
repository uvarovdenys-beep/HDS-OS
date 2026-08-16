#!/usr/bin/env python3
"""
protocol_enforcer.py
HDS Protocol Enforcer — runtime enforcement middleware

Intercepts model actions and BLOCKS forbidden ones based on protocol size (XL/L/M/S).
This is the "police" module — without it the protocol is just text the model can ignore.

Authors: HDS Development Team
License: HDS Standard
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Dict, Optional

from model_router import get_model_profile, ProtocolSize, classify_model

logger = logging.getLogger("protocol_enforcer")


# ──────────────────────────────────────────────────────────────
# ALLOWED ACTIONS BY PROTOCOL SIZE
# ──────────────────────────────────────────────────────────────

# Action types and which sizes are allowed to perform them
ACTION_PERMISSIONS: Dict[str, List[ProtocolSize]] = {
    "discover":              [ProtocolSize.XL, ProtocolSize.L],
    "create_module":         [ProtocolSize.XL, ProtocolSize.L],
    "refactor":              [ProtocolSize.XL, ProtocolSize.L],
    "decompose":             [ProtocolSize.XL],
    "aivc":                  [ProtocolSize.XL, ProtocolSize.L],
    "create_task":           [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M],
    "delete_code":           [ProtocolSize.XL, ProtocolSize.L],
    "change_api":            [ProtocolSize.XL],
    "architecture_decision": [ProtocolSize.XL],
    # Code generation permissions
    "write_file":            [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M],
    "execute_code":          [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M],
    "run_test":              [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M, ProtocolSize.S],
    "read_file":             [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M, ProtocolSize.S],
    # Browser/vision (AIVC subtasks)
    "navigate":              [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M],
    "click":                 [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M],
    "type":                  [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M],
    "screenshot":            [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M, ProtocolSize.S],
}

# Task creation hierarchy: who can create tasks for whom
# Key — size of the creator; value — which sizes it can create tasks for
TASK_CREATION_HIERARCHY: Dict[ProtocolSize, List[ProtocolSize]] = {
    ProtocolSize.XL: [ProtocolSize.XL, ProtocolSize.L, ProtocolSize.M, ProtocolSize.S],
    ProtocolSize.L:  [ProtocolSize.L, ProtocolSize.M, ProtocolSize.S],
    ProtocolSize.M:  [ProtocolSize.M, ProtocolSize.S],
    ProtocolSize.S:  [],  # S cannot create tasks at all
}

# Protected directories (not writable by models below XL)
PROTECTED_PATHS = [
    "ai-mind/protocols/",
    "ai-mind/config/",
    "agent/",
]


# ──────────────────────────────────────────────────────────────
# PROTOCOL ENFORCER
# ──────────────────────────────────────────────────────────────

class ProtocolEnforcer:
    """
    Runtime enforcement middleware for HDS.

    Checks every model action before execution.
    If the action is forbidden — returns (False, reason).
    """

    def __init__(self, model_name: str):
        """
        Initialize the enforcer for a specific model.

        Args:
            model_name: Model name (e.g. "claude-opus-4-6", "qwen3.5:9b")
        """
        self.model_name = model_name
        self.profile = get_model_profile(model_name)
        self.size = self.profile.size

        # Session counters
        self._files_accessed: int = 0
        self._total_lines_changed: int = 0
        self._violations: List[Dict] = []

        # Path for violation logging
        self._violations_log = Path("ai-mind/protocols/violations.log")

        logger.info(
            f"[Enforcer] Initialized for {model_name} "
            f"(size: {self.size.value.upper()})"
        )

    # ──────────────────────────────────────────────────────────
    # MAIN CHECKS
    # ──────────────────────────────────────────────────────────

    def check_action(self, action_type: str, **kwargs) -> Tuple[bool, str]:
        """
        Check an action by type.

        Args:
            action_type: Action type (discover, create_module, refactor, etc.)
            **kwargs: Additional action parameters

        Returns:
            (allowed: bool, reason: str)
        """
        if action_type not in ACTION_PERMISSIONS:
            return False, f"Unknown action type: {action_type}"

        allowed_sizes = ACTION_PERMISSIONS[action_type]

        if self.size in allowed_sizes:
            return True, f"Action '{action_type}' allowed for {self.size.value.upper()}"

        reason = (
            f"BLOCKED: action '{action_type}' is forbidden for size "
            f"{self.size.value.upper()}. Allowed only for: "
            f"{', '.join(s.value.upper() for s in allowed_sizes)}"
        )
        self.log_violation(action_type, reason)
        return False, reason

    def check_file_access(self, filepath: str, mode: str = "read") -> Tuple[bool, str]:
        """
        Check file access permissions.

        Args:
            filepath: Path to the file
            mode: "read" or "write"

        Returns:
            (allowed: bool, reason: str)
        """
        # Read is allowed for all
        if mode == "read":
            return True, "Read allowed"

        # Write to protected directories — only XL
        for protected in PROTECTED_PATHS:
            if filepath.startswith(protected) or f"/{protected}" in filepath:
                if self.size != ProtocolSize.XL:
                    reason = (
                        f"BLOCKED: write to protected directory '{protected}' "
                        f"is forbidden for {self.size.value.upper()}. XL only."
                    )
                    self.log_violation(f"write:{filepath}", reason)
                    return False, reason

        # Check per-session file limit
        if self._files_accessed >= self.profile.max_files_per_session:
            reason = (
                f"BLOCKED: exceeded per-session file limit "
                f"({self.profile.max_files_per_session}) for "
                f"{self.size.value.upper()}"
            )
            self.log_violation(f"write:{filepath}", reason)
            return False, reason

        self._files_accessed += 1
        return True, f"Write allowed (files: {self._files_accessed}/{self.profile.max_files_per_session})"

    def check_task_creation(
        self, task_complexity: int, target_size: str
    ) -> Tuple[bool, str]:
        """
        Check task creation permissions.

        Args:
            task_complexity: Task complexity (1-10)
            target_size: Target model size ("xl", "l", "m", "s")

        Returns:
            (allowed: bool, reason: str)
        """
        # S cannot create tasks at all
        if self.size == ProtocolSize.S:
            reason = "BLOCKED: size S cannot create tasks"
            self.log_violation("create_task", reason)
            return False, reason

        # Check hierarchy
        try:
            target = ProtocolSize(target_size.lower())
        except ValueError:
            return False, f"Unknown target size: {target_size}"

        allowed_targets = TASK_CREATION_HIERARCHY[self.size]
        if target not in allowed_targets:
            reason = (
                f"BLOCKED: {self.size.value.upper()} cannot create tasks "
                f"for {target.value.upper()}. Allowed: "
                f"{', '.join(t.value.upper() for t in allowed_targets)}"
            )
            self.log_violation("create_task", reason)
            return False, reason

        # Check complexity
        if task_complexity > self.profile.max_task_complexity:
            reason = (
                f"BLOCKED: task complexity ({task_complexity}) exceeds "
                f"maximum for {self.size.value.upper()} "
                f"({self.profile.max_task_complexity})"
            )
            self.log_violation("create_task", reason)
            return False, reason

        return True, (
            f"Task creation allowed: {self.size.value.upper()} -> "
            f"{target.value.upper()}, complexity {task_complexity}"
        )

    def check_lines_changed(self, lines: int) -> Tuple[bool, str]:
        """
        Check the number of changed lines.

        Args:
            lines: Number of lines being changed

        Returns:
            (allowed: bool, reason: str)
        """
        max_lines = self.profile.max_lines_per_change

        if lines > max_lines:
            reason = (
                f"BLOCKED: {lines} lines exceeds limit of "
                f"{max_lines} for {self.size.value.upper()}"
            )
            self.log_violation(f"lines_changed:{lines}", reason)
            return False, reason

        self._total_lines_changed += lines
        return True, f"Allowed: {lines}/{max_lines} lines"

    def check_files_accessed(self, count: int) -> Tuple[bool, str]:
        """
        Check the number of files accessed in a session.

        Args:
            count: Current number of files in the session

        Returns:
            (allowed: bool, reason: str)
        """
        max_files = self.profile.max_files_per_session

        if count > max_files:
            reason = (
                f"BLOCKED: {count} files exceeds limit of "
                f"{max_files} for {self.size.value.upper()}"
            )
            self.log_violation(f"files_accessed:{count}", reason)
            return False, reason

        return True, f"Allowed: {count}/{max_files} files"

    # ──────────────────────────────────────────────────────────
    # VIOLATION LOGGING
    # ──────────────────────────────────────────────────────────

    def log_violation(self, action: str, reason: str) -> None:
        """
        Log a protocol violation.

        Stores in memory and writes to violations.log.
        """
        violation = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model_name,
            "size": self.size.value.upper(),
            "action": action,
            "reason": reason,
        }

        self._violations.append(violation)
        logger.warning(f"[VIOLATION] {self.model_name}: {reason}")

        # Write to file (create directory if it doesn't exist)
        try:
            self._violations_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._violations_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(violation, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error(f"[Enforcer] Failed to write violation: {e}")

    def get_violations(self) -> List[Dict]:
        """Returns the list of violations for the current session."""
        return self._violations.copy()

    # ──────────────────────────────────────────────────────────
    # UTILITIES
    # ──────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Current enforcer status."""
        return {
            "model": self.model_name,
            "size": self.size.value.upper(),
            "files_accessed": self._files_accessed,
            "max_files": self.profile.max_files_per_session,
            "total_lines_changed": self._total_lines_changed,
            "max_lines_per_change": self.profile.max_lines_per_change,
            "violations_count": len(self._violations),
        }

    def __repr__(self) -> str:
        return (
            f"ProtocolEnforcer(model={self.model_name}, "
            f"size={self.size.value.upper()}, "
            f"violations={len(self._violations)})"
        )


# ──────────────────────────────────────────────────────────────
# CLI — enforcement demonstration for different sizes
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    # Test models of different sizes
    test_cases = [
        ("claude-opus-4-6", ProtocolSize.XL),    # Architect
        ("claude-sonnet-4-6", ProtocolSize.L),   # Engineer
        ("qwen3.5:9b", ProtocolSize.M),          # Worker
        ("claude-haiku-3-5", ProtocolSize.S),    # Assistant
    ]

    # Actions to check
    test_actions = [
        "discover",
        "create_module",
        "refactor",
        "decompose",
        "aivc",
        "create_task",
        "delete_code",
        "change_api",
        "architecture_decision",
    ]

    print("=" * 80)
    print("HDS PROTOCOL ENFORCER — DEMONSTRATION")
    print("=" * 80)

    # -- Test 1: Action permission check -------------------------
    print("\n┌─────────────────────────────────────────────────────────────────────────┐")
    print("│ TEST 1: Action permissions                                             │")
    print("└─────────────────────────────────────────────────────────────────────────┘")

    header = f"{'ACTION':<25}"
    for model, size in test_cases:
        header += f" {size.value.upper():>4}"
    print(f"\n{header}")
    print("─" * 45)

    for action in test_actions:
        row = f"{action:<25}"
        for model, _ in test_cases:
            enforcer = ProtocolEnforcer(model)
            allowed, _ = enforcer.check_action(action)
            row += f" {'✓':>4}" if allowed else f" {'✗':>4}"
        print(row)

    # -- Test 2: Task creation hierarchy -------------------------
    print("\n┌─────────────────────────────────────────────────────────────────────────┐")
    print("│ TEST 2: Task creation hierarchy                                        │")
    print("└─────────────────────────────────────────────────────────────────────────┘\n")

    for model, size in test_cases:
        enforcer = ProtocolEnforcer(model)
        print(f"  {size.value.upper()} ({model}):")
        for target in ["xl", "l", "m", "s"]:
            allowed, reason = enforcer.check_task_creation(5, target)
            status = "✓" if allowed else "✗"
            print(f"    -> create for {target.upper()}: {status}")
        print()

    # -- Test 3: Line limits ------------------------------------
    print("┌─────────────────────────────────────────────────────────────────────────┐")
    print("│ TEST 3: Lines per change limits                                        │")
    print("└─────────────────────────────────────────────────────────────────────────┘\n")

    line_tests = [50, 200, 500, 1000]
    for model, size in test_cases:
        enforcer = ProtocolEnforcer(model)
        results = []
        for lines in line_tests:
            allowed, _ = enforcer.check_lines_changed(lines)
            results.append(f"{lines}->{'✓' if allowed else '✗'}")
        print(f"  {size.value.upper():>2} (max {enforcer.profile.max_lines_per_change:>4}): {' | '.join(results)}")

    # -- Test 4: Protected directory access ----------------------
    print("\n┌─────────────────────────────────────────────────────────────────────────┐")
    print("│ TEST 4: Write to protected directories                                 │")
    print("└─────────────────────────────────────────────────────────────────────────┘\n")

    protected_file = "ai-mind/protocols/hds_xl.md"
    normal_file = "src/utils/helpers.py"

    for model, size in test_cases:
        enforcer = ProtocolEnforcer(model)
        allowed_p, _ = enforcer.check_file_access(protected_file, "write")
        allowed_n, _ = enforcer.check_file_access(normal_file, "write")
        print(
            f"  {size.value.upper():>2}: protected directory -> {'✓' if allowed_p else '✗'} | "
            f"normal file -> {'✓' if allowed_n else '✗'}"
        )

    # -- Test 5: Violations -------------------------------------
    print("\n┌─────────────────────────────────────────────────────────────────────────┐")
    print("│ TEST 5: Violations log                                                 │")
    print("└─────────────────────────────────────────────────────────────────────────┘\n")

    # Simulate an M-model session with violations
    enforcer_m = ProtocolEnforcer("qwen3.5:9b")
    enforcer_m.check_action("discover")
    enforcer_m.check_action("refactor")
    enforcer_m.check_action("architecture_decision")
    enforcer_m.check_lines_changed(300)
    enforcer_m.check_file_access("ai-mind/protocols/hds_m.md", "write")

    violations = enforcer_m.get_violations()
    print(f"  Model: qwen3.5:9b (M)")
    print(f"  Violations this session: {len(violations)}")
    for v in violations:
        print(f"    ! {v['action']}: {v['reason'][:60]}...")

    print(f"\n{'=' * 80}")
    print("ENFORCER READY — protocol now has teeth")
    print(f"{'=' * 80}")
