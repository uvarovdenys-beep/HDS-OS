#!/usr/bin/env python3
"""patcher.py — locate a function/class by NAME and return its exact line span.

Surgical edits, not whole-file rewrites. The AI names what it wants to change
("the function parse_row", "the method Store.add") and HDS finds the precise
lines; only those lines are replaced. A whole-file regeneration destroys
comments, imports and neighbouring code that nobody asked to touch.

Line numbers are 1-indexed and INCLUSIVE, matching editors and tracebacks.
Python targets resolve through the AST (exact, decorator-aware). Other
languages must supply an explicit line range — guessing spans by counting
braces is how patchers corrupt files.
"""
import ast

_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


class PatchError(Exception):
    """Target not found, ambiguous, or the range is impossible."""


def _span(node):
    """Line span of a def, decorators included — a patch that drops them
    silently changes behaviour."""
    start = node.lineno
    for dec in node.decorator_list:
        if dec.lineno < start:
            start = dec.lineno
    try:
        end = node.end_lineno
    except AttributeError:
        raise PatchError("this Python build does not report end_lineno")
    return start, end


def locate(source: str, target: str):
    """Return (start, end) 1-indexed inclusive for a Python target.

    target accepts: "name", "def name", "class Name", or "Class.method".
    Raises PatchError when the target is missing or matches more than once.
    """
    want = target.strip()
    for prefix in ("async def ", "def ", "class "):
        if want.startswith(prefix):
            want = want[len(prefix):].strip()
            break
    want = want.split("(")[0].strip()

    hits = []

    def scan(body, path):
        for node in body:
            if isinstance(node, _DEFS):
                qualified = path + "." + node.name if path else node.name
                if qualified == want:
                    hits.append(node)
                if isinstance(node, ast.ClassDef):
                    scan(node.body, qualified)

    scan(ast.parse(source).body, "")
    if not hits:
        raise PatchError("target not found: " + target)
    if len(hits) > 1:
        raise PatchError("target is ambiguous (%d matches): %s" % (len(hits), target))
    return _span(hits[0])


def replace_lines(source: str, start: int, end: int, new_text: str) -> str:
    """Replace lines [start, end] inclusive with new_text."""
    lines = source.splitlines(keepends=True)
    if start < 1 or end < start or end > len(lines):
        raise PatchError("bad range %d-%d for a %d-line file" % (start, end, len(lines)))
    body = new_text if new_text.endswith("\n") else new_text + "\n"
    return "".join(lines[:start - 1]) + body + "".join(lines[end:])


def insert_after(source: str, line: int, new_text: str) -> str:
    """Insert new_text directly after the given 1-indexed line (0 = prepend)."""
    lines = source.splitlines(keepends=True)
    if line < 0 or line > len(lines):
        raise PatchError("bad insert point %d for a %d-line file" % (line, len(lines)))
    body = new_text if new_text.endswith("\n") else new_text + "\n"
    return "".join(lines[:line]) + body + "".join(lines[line:])
