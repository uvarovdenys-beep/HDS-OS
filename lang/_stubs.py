"""_stubs.py — R-STUB: a placeholder must say that it is one.

THE FAILURE THIS EXISTS FOR. A generated `rollDice` arrived with both branches
empty — `// Move investigator` and `// Handle failure` — and the cage accepted
it, because the syntax was valid. The game then ran, logged nothing, and looked
broken for reasons no one could see. A stub is the worst kind of defect: it has
the SHAPE of working code, so every check that reads shape says yes.

So an unfinished declaration is refused unless it is declared unfinished. The
marker is a comment containing STUB: (or TODO:/FIXME:) followed by a reason:

    function rollDice() {
        // STUB: turn logic lands in the next task
    }

That costs the author one line and buys three things: the reader knows, a grep
finds every hole in the codebase, and nobody can leave one by accident.

WHAT COUNTS AS EMPTY. A body with no statements, or only comments, or only
`pass`/`...`. `raise NotImplementedError` is already self-documenting and passes
as it is. Declarations with no body at all — C prototypes, TS interface members,
abstract signatures — are not stubs; they are declarations.

LIMITS. Detection is structural for Python (AST) and brace-counting elsewhere,
so it catches the loud case: a function that plainly does nothing. It does not
judge whether a full-looking body is CORRECT — nothing here can.
"""
import re

# NO-OP: means "deliberately empty, and here is why" — finished work, not a
# hole. Without it, an intentional override (silencing a base class's
# access log) had to be mislabelled TODO: to pass, which is a lie in the
# codebase and pollutes the greppable list of real holes.
_MARKERS = ("STUB:", "TODO:", "FIXME:", "XXX:", "NOT IMPLEMENTED", "NO-OP:",
            "NotImplementedError", "@stub")


def _has_marker(text: str) -> bool:
    upper = text.upper()
    return any(m.upper() in upper for m in _MARKERS)


def _python_stubs(content: str):
    """(name, line) for every Python declaration whose body does nothing."""
    import ast
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    lines = content.splitlines()
    out = []

    def body_is_empty(node):
        real = []
        for stmt in node.body:
            if isinstance(stmt, ast.Pass):
                continue
            # A lone docstring or a bare `...` is not an implementation.
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                if stmt.value.value is Ellipsis or isinstance(stmt.value.value, str):
                    continue
            real.append(stmt)
        return not real

    def visit(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if body_is_empty(node):
                    start = node.lineno - 1
                    end = node.end_lineno
                    block = "\n".join(lines[max(0, start - 1):end])
                    if not _has_marker(block):
                        out.append((node.name, node.lineno))
            if isinstance(node, ast.ClassDef):
                visit(node.body)

    visit(tree.body)
    return out


def _brace_stubs(content: str, ext: str):
    """(name, line) for C-family/JS FUNCTIONS whose body holds no statement.

    Only functions. An earlier version walked every declaration, so
    `let PATHS = {};` — an ordinary empty initialiser — was reported as an
    unfinished placeholder. That is a false refusal, and a false refusal blocks
    correct work, which is worse than a missed one: R-STUB exists to catch a
    function that promises behaviour and delivers none, not a variable that
    starts out empty by design.
    """
    import re as _re

    from ._locate import LocateError, can_locate
    from ._locate import locate as walk

    if not can_locate(ext):
        return []
    lines = content.splitlines()
    out = []
    # Function declarations only — `function name(`, or `name(args) {` for the
    # C family. A `const x =` never reaches this list.
    fn_pattern = _re.compile(
        r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)"
        r"|^\s*(?:pub\s+)?(?:fn|func)\s+(?:\([^)]*\)\s*)?(\w+)"
        r"|^\s*(?:def)\s+([\w.]+)"
        r"|^\s*[A-Za-z_][\w\s\*<>,:]*?\b(\w+)\s*\([^;)]*\)\s*\{")
    names = set()
    for match in fn_pattern.finditer(content):
        for group in match.groups():
            if group and group not in ("if", "for", "while", "switch", "catch",
                                       "return", "else", "do", "try"):
                names.add(group)

    for name in sorted(names):
        try:
            start, end = walk(content, name, ext)
        except LocateError:
            continue
        block = "\n".join(lines[start - 1:end])
        if "{" not in block:
            continue                     # a prototype or signature, not a stub
        inner = block[block.index("{") + 1:block.rindex("}")] if "}" in block else ""
        stripped = _re.sub(r"/\*.*?\*/", "", inner, flags=_re.S)
        stripped = _re.sub(r"(?m)//.*$", "", stripped)
        stripped = _re.sub(r"(?m)^\s*#.*$", "", stripped)
        if stripped.strip():
            continue                     # it does something
        if _has_marker(block):
            continue                     # empty, but declared as such
        out.append((name, start))
    return out


def find(content: str, ext: str):
    """Unmarked placeholders in this content, as (name, line) pairs."""
    if ext == ".py":
        return _python_stubs(content)
    return _brace_stubs(content, ext)


def check(content: str, path) -> None:
    """Raise LangReject when an unmarked placeholder would be written."""
    from pathlib import Path

    from . import LangReject

    found = find(content, Path(path).suffix)
    if not found:
        return
    where = ", ".join(f"{n} (line {ln})" for n, ln in found[:5])
    more = " …" if len(found) > 5 else ""
    raise LangReject(
        f"R-STUB: '{Path(path).name}' has {len(found)} empty declaration(s) "
        f"with no note: {where}{more}. A placeholder must say it is one — add a "
        f"comment with STUB: and the reason, so the hole is greppable instead "
        f"of looking like finished work.")
