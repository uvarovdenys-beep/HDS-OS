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


def _locate_other(source, target, ext):
    """Delegate to the brace/keyword walker for a non-Python language."""
    from lang._locate import LocateError, can_locate
    from lang._locate import locate as walk
    if not can_locate(ext):
        raise PatchError(f"no locator for '{ext}' — give explicit start/end lines")
    try:
        return walk(source, target, ext)
    except LocateError as e:
        raise PatchError(str(e))


def _guess_locate(source, target):
    """Try every non-Python grammar; accept only an unambiguous agreement.

    scribe.py cannot be changed to pass the file extension — R-KERNEL forbids
    writing it, deliberately — so when the caller does not say which language
    this is, the grammars are tried in turn. Several may match the same
    declaration and agree on its span, which is fine; disagreement means the
    language is genuinely unclear and the patch is refused rather than guessed.
    """
    from lang._locate import LocateError, _STYLE
    from lang._locate import locate as walk
    spans = set()
    for ext in _STYLE:
        try:
            spans.add(walk(source, target, ext))
        except LocateError:
            continue
    if not spans:
        raise PatchError("target not found: " + target)
    if len(spans) > 1:
        raise PatchError(
            f"'{target}' spans differ between grammars {sorted(spans)} — "
            f"give explicit start/end lines")
    return spans.pop()


def locate(source: str, target: str, ext: str = ""):
    """Return (start, end) 1-indexed inclusive for a target declaration.

    Python resolves through the AST: exact, decorator-aware. Every other
    language falls through to lang._locate, a brace/keyword walker that skips
    strings and comments. Without that fallback, surgical patching worked for
    Python and nowhere else, so a JavaScript file could only ever be rewritten
    whole — nine consecutive rewrites of one game file each silently dropped
    working functions, which is the failure this closes.

    target accepts: "name", "def name", "class Name", or "Class.method".
    Raises PatchError when the target is missing, ambiguous, or its block never
    closes. Guessing a range would delete the wrong lines, which is the exact
    harm surgical patching exists to prevent.
    """
    if ext and ext != ".py":
        return _locate_other(source, target, ext)

    want = target.strip()
    for prefix in ("async def ", "def ", "class "):
        if want.startswith(prefix):
            want = want[len(prefix):].strip()
            break

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Not Python. Fall back to the other grammars rather than refusing —
        # this is the path a .js or .go patch takes through scribe.
        return _guess_locate(source, target)

    found = []

    def scan(body, prefix):
        for node in body:
            if not isinstance(node, _DEFS):
                continue
            qualified = prefix + node.name
            if qualified == want or node.name == want:
                found.append(node)
            if isinstance(node, ast.ClassDef):
                scan(node.body, qualified + ".")

    scan(tree.body, "")
    if not found:
        raise PatchError("target not found: " + target)
    if len(found) > 1:
        raise PatchError(f"target is ambiguous ({len(found)} matches): {target}")
    return _span(found[0])


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
