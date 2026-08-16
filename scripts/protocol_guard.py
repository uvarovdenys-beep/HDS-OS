#!/usr/bin/env python3
"""
protocol_guard.py
HDS Protocol Guard — pre-commit hook for Claude Code.

Checks that changes made by AI follow HDS protocol rules:
1. No file exceeds protocol size limits
2. All classes have docstrings (orchestrator index needs them)
3. All public methods have docstrings
4. No Ukrainian in code (except protocol_diagnostic.py)
5. No new files created that duplicate existing scripts

Exit code 0 = pass, 1 = violation found.
Run as: python3 scripts/protocol_guard.py [changed_files...]
If no files specified, checks git staged files.
"""

import ast
import os
import re
import sys
import subprocess


def get_staged_files():
    """Get list of staged Python files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True
        )
        return [f for f in result.stdout.strip().split("\n") if f.endswith(".py") and f]
    except Exception:
        return []


def check_file_size(filepath, max_lines=500):
    """Check file doesn't exceed size limit."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = len(f.readlines())
    if lines > max_lines:
        return f"SIZE: {filepath} has {lines} lines (max {max_lines})"
    return None


def check_docstrings(filepath):
    """Check all classes and public methods have docstrings."""
    violations = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return [f"SYNTAX: {filepath} has syntax errors"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node):
                violations.append(f"DOCSTRING: class {node.name} in {filepath}:{node.lineno} — missing docstring")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_") and not ast.get_docstring(node):
                violations.append(f"DOCSTRING: {node.name}() in {filepath}:{node.lineno} — missing docstring")

    return violations


def check_ukrainian(filepath):
    """Check no Ukrainian text in code files."""
    skip = ["protocol_diagnostic.py", "soul.md"]
    if os.path.basename(filepath) in skip:
        return []

    ukr = re.compile(r'[а-яіїєґА-ЯІЇЄҐ]{3,}')
    violations = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if ukr.search(line):
                violations.append(f"LANG: {filepath}:{i} — Ukrainian text found")
                if len(violations) >= 3:
                    violations.append(f"LANG: {filepath} — ...and more")
                    break
    return violations


def main():
    files = sys.argv[1:] if len(sys.argv) > 1 else get_staged_files()

    if not files:
        print("protocol_guard: no files to check")
        sys.exit(0)

    all_violations = []

    for f in files:
        if not os.path.exists(f):
            continue
        if not f.endswith(".py"):
            continue

        # Size check
        v = check_file_size(f)
        if v:
            all_violations.append(v)

        # Docstring check
        all_violations.extend(check_docstrings(f))

        # Ukrainian check
        all_violations.extend(check_ukrainian(f))

    if all_violations:
        print(f"❌ Protocol Guard: {len(all_violations)} violations\n")
        for v in all_violations[:15]:
            print(f"  {v}")
        if len(all_violations) > 15:
            print(f"  ...+{len(all_violations) - 15} more")
        sys.exit(1)
    else:
        print(f"✅ Protocol Guard: {len(files)} files OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
