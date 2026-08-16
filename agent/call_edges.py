#!/usr/bin/env python3
"""call_edges.py — code-graph call extraction for the orchestrator index.

The code side of the mirror graph: given a parsed AST node, report the names it
invokes. Kept apart from orchestrator_index so the index stays under the 300-line
working limit and the call-graph logic has one home to grow into — the plan/code
diff (mirror-graph step b) will build on this.
"""
import ast
from typing import List


def extract_calls(node: ast.AST) -> List[str]:
    """
    Collect the names of every function/method call inside `node`.

    Args:
        node (ast.AST): The AST node to search for function/method calls.

    Returns:
        List[str]: A sorted list of unique names of function/method calls.
    """
    names = set()

    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Name):
                names.add(sub.func.id)
            elif isinstance(sub.func, ast.Attribute):
                names.add(sub.func.attr)

    return sorted(names)
