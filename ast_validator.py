#!/usr/bin/env python3
"""
ast_validator.py
HDS6 TKT-003a: AST-based Script Validation

Replaces simple regex matching with Abstract Syntax Tree analysis.

SCOPE — this is code HYGIENE, not containment. It is a name-based denylist over
an AST: it catches naive-dangerous constructs (bare eval/exec/subprocess/import),
but cannot stop attribute-form dispatch (``x.eval()`` where x is __builtins__) or
runtime file IO (``open(...)``) — see tests/test_cage_adversarial.py for the
documented limits. Real containment of executed code is process isolation
(sandbox/), not source scanning. Do not rely on this scan as a security boundary.

Authors: HDS6 Development Team
License: HDS6 Standard
"""

import ast
from typing import Tuple, List, Dict
from enum import Enum


class SecurityLevel(Enum):
    """Code security levels."""
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


class ASTValidator:
    """
    Checks Python code for dangerous constructs via AST.
    Unlike regex, AST understands code structure.
    """

    # Forbidden functions/methods
    FORBIDDEN_CALLS = {
        "eval": SecurityLevel.CRITICAL,  # Execute strings as code
        "exec": SecurityLevel.CRITICAL,  # Execute strings as code
        "compile": SecurityLevel.CRITICAL,  # Dynamic compilation
        "__import__": SecurityLevel.DANGER,  # Dynamic import
        "getattr": SecurityLevel.DANGER,  # Reflection
        "setattr": SecurityLevel.DANGER,  # Object modification
        "delattr": SecurityLevel.DANGER,  # Attribute deletion
        "globals": SecurityLevel.DANGER,  # Reach __builtins__ / module globals
        "vars": SecurityLevel.DANGER,     # Same reach as globals()
    }

    # Forbidden modules
    FORBIDDEN_MODULES = {
        "os": SecurityLevel.DANGER,
        "sys": SecurityLevel.WARNING,  # Allowed but needs context
        "subprocess": SecurityLevel.CRITICAL,
        "importlib": SecurityLevel.DANGER,  # Dynamic import → reach denied modules
        "socket": SecurityLevel.WARNING,
        "urllib": SecurityLevel.WARNING,
        "requests": SecurityLevel.WARNING,  # Network — needs context
    }

    def __init__(self):
        self.violations: List[Dict] = []

    def validate(self, code: str) -> Tuple[SecurityLevel, List[Dict]]:
        """
        Validate code for security.
        Returns (worst_level, violations_list).
        """
        self.violations = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return SecurityLevel.DANGER, [
                {
                    "type": "syntax_error",
                    "message": f"Syntax error: {e}",
                    "line": e.lineno,
                }
            ]

        # Walk AST tree
        for node in ast.walk(tree):
            # Check function calls
            if isinstance(node, ast.Call):
                self._check_function_call(node)

            # Check imports
            elif isinstance(node, ast.Import):
                self._check_import(node)
            elif isinstance(node, ast.ImportFrom):
                self._check_import_from(node)

            # Check for infinite loops
            elif isinstance(node, ast.While):
                self._check_while_loop(node)

        # Find worst severity level.
        # NOTE: SecurityLevel.value is a STRING ("safe"/"danger"/...), so
        # comparing .value ranks lexicographically and is WRONG. Rank explicitly.
        level_map = {
            "critical": SecurityLevel.CRITICAL,
            "danger": SecurityLevel.DANGER,
            "warning": SecurityLevel.WARNING,
            "safe": SecurityLevel.SAFE,
        }
        severity = {
            SecurityLevel.SAFE: 0,
            SecurityLevel.WARNING: 1,
            SecurityLevel.DANGER: 2,
            SecurityLevel.CRITICAL: 3,
        }
        worst_level = SecurityLevel.SAFE
        for violation in self.violations:
            level = level_map.get(violation.get("level", "safe").lower(), SecurityLevel.SAFE)
            if severity[level] > severity[worst_level]:
                worst_level = level

        return worst_level, self.violations

    def _check_function_call(self, node: ast.Call):
        """Check function calls.

        FORBIDDEN_CALLS are all builtins (eval/exec/compile/__import__/getattr/
        ...), which are invoked by bare name. A method call with the same final
        attribute (e.g. ``re.compile``, ``obj.eval``) is NOT the builtin, so we
        match ``ast.Name`` only — matching ``ast.Attribute`` here false-positives
        on legitimate methods like ``re.compile``.
        """
        func_name = None

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Subscript):
            # __builtins__['eval']('x') or vars()['exec']('x') pattern
            val = node.func.value
            slc = node.func.slice
            if isinstance(val, ast.Name) and val.id in ("__builtins__", "vars", "globals"):
                if isinstance(slc, ast.Constant) and isinstance(slc.value, str):
                    func_name = slc.value  # extract 'eval', 'exec', etc.

        if func_name and func_name in self.FORBIDDEN_CALLS:
            level = self.FORBIDDEN_CALLS[func_name]
            self.violations.append(
                {
                    "type": "forbidden_call",
                    "function": func_name,
                    "level": level.value,
                    "message": f"Forbidden function: {func_name}",
                    "line": node.lineno,
                }
            )

    def _check_import(self, node: ast.Import):
        """Check imports (import X)."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]  # Get base module
            if module_name in self.FORBIDDEN_MODULES:
                level = self.FORBIDDEN_MODULES[module_name]
                self.violations.append(
                    {
                        "type": "forbidden_import",
                        "module": module_name,
                        "level": level.value,
                        "message": f"Potentially dangerous import: {module_name}",
                        "line": node.lineno,
                    }
                )

    def _check_import_from(self, node: ast.ImportFrom):
        """Check imports (from X import Y)."""
        module_name = node.module.split(".")[0] if node.module else None
        if module_name and module_name in self.FORBIDDEN_MODULES:
            level = self.FORBIDDEN_MODULES[module_name]
            self.violations.append(
                {
                    "type": "forbidden_import",
                    "module": module_name,
                    "level": level.value,
                    "message": f"Potentially dangerous import: {module_name}",
                    "line": node.lineno,
                }
            )

    def _check_while_loop(self, node: ast.While):
        """Check while True loops without exit."""
        # If condition is True or 1, potentially infinite loop
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            # Check if there is a break inside
            has_break = any(isinstance(n, ast.Break) for n in ast.walk(node))
            if not has_break:
                self.violations.append(
                    {
                        "type": "infinite_loop",
                        "level": "warning",
                        "message": "Potentially infinite loop without break detected",
                        "line": node.lineno,
                    }
                )
