"""_preserve.py — R-PRESERVE: a rewrite may not silently delete declarations.

THE FAILURE THIS EXISTS FOR. The cage checked what a file CONTAINS and never
what a rewrite DESTROYS. Asked to add a log helper, a local model re-emitted the
whole file and dropped nextTurn, updateScales and every log call with it. Nine
rounds, each fixing one thing and quietly removing another, and every one of
them passed the cage: the output was valid JavaScript, so R-AST was satisfied.

Validity is not preservation. A file that parses can still have lost half its
behaviour.

So: replacing an existing file is refused when the new content DROPS a top-level
declaration the old content had. Adding, editing and reordering stay free —
only deletion is stopped, because deletion is the operation nobody asked for.

WHY HERE AND NOT IN scribe. R-KERNEL forbids writing scribe.py at all, by
design. But every validator already receives (content, path), and `register`
wraps them all, so the rule reaches every language from one place.

LIMITS, STATED PLAINLY. Python names come from the AST and are exact. Other
languages use a per-language pattern, which finds ordinary declarations and will
miss exotic ones. That is a floor, not a ceiling: it catches the loud case — a
function that simply vanished — which is the case that actually happened.

Deliberate removal stays possible: delete the file, or narrow the edit to a
patch. Both are explicit acts, which is the point.
"""
import re

# Top-level declarations, per language family. Kept deliberately simple: this
# must not become a parser, only a way to notice that a name is gone.
_PATTERNS = {
    # A module-level `const X = {...}` is as much a declaration as a function:
    # declaring one twice is a TypeError at load. The first version only matched
    # `const x = function` and `const x = (`, so a duplicated lookup table went
    # unnoticed and broke the file it was patched into.
    ".js":  r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=",
    ".ts":  r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:export\s+)?(?:class|interface|type|enum)\s+(\w+)|^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=",
    ".c":   r"(?m)^\s*[A-Za-z_][\w\s\*]*?\b(\w+)\s*\([^;]*\)\s*\{",
    ".cs":  r"(?m)^\s*(?:public|private|protected|internal|static|\s)*(?:class|struct|interface|enum)\s+(\w+)|\b(\w+)\s*\([^;)]*\)\s*\{",
    ".rb":  r"(?m)^\s*(?:def|class|module)\s+([\w.]+)",
    ".go":  r"(?m)^\s*func\s+(?:\([^)]*\)\s*)?(\w+)|^\s*type\s+(\w+)",
    ".rs":  r"(?m)^\s*(?:pub\s+)?(?:fn|struct|enum|trait|impl)\s+(\w+)",
    ".php": r"(?m)^\s*(?:function|class|trait|interface)\s+(\w+)",
    ".sh":  r"(?m)^\s*(?:function\s+)?(\w+)\s*\(\)\s*\{",
    ".java": r"(?m)^\s*(?:public|private|protected|static|final|abstract|\s)*(?:class|interface|enum)\s+(\w+)",
    ".swift": r"(?m)^\s*(?:public|private|internal|\s)*(?:func|class|struct|enum|protocol)\s+(\w+)",
}
_PATTERNS[".mjs"] = _PATTERNS[".cjs"] = _PATTERNS[".jsx"] = _PATTERNS[".js"]
_PATTERNS[".tsx"] = _PATTERNS[".ts"]
_PATTERNS[".cpp"] = _PATTERNS[".cc"] = _PATTERNS[".hpp"] = _PATTERNS[".h"] = _PATTERNS[".c"]
_PATTERNS[".bash"] = _PATTERNS[".sh"]


# Words a loose pattern picks up as if they were declarations.
_NOT_NAMES = {"if", "for", "while", "switch", "catch", "return", "else",
              "do", "try", "function", "class"}


def declarations(content: str, ext: str) -> set:
    """Top-level names a file declares. An empty set means "cannot tell"."""
    if ext == ".py":
        try:
            import ast
            tree = ast.parse(content)
        except SyntaxError:
            return set()
        out = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(node.name)
        return out

    pattern = _PATTERNS.get(ext)
    if not pattern:
        return set()
    found = set()
    for match in re.finditer(pattern, content):
        for group in match.groups():
            if group:
                found.add(group)
    # Keywords that a loose pattern picks up as if they were declarations.
    return found - _NOT_NAMES


def module_scope(content: str, ext: str) -> set:
    """Declarations at the file's outermost level only.

    Deletion and duplication are both judged here rather than over every
    declaration at any depth. A function-local `const BURROW = [...]` that is
    inlined away, or a `const cell` that appears in two different functions, is
    ordinary work — refusing it blocks correct edits, which is worse than
    missing one. Scope is approximated by indentation, and only the shallowest
    depth counts.
    """
    if ext == ".py":
        try:
            import ast
            tree = ast.parse(content)
        except SyntaxError:
            return set()
        return {n.name for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}

    pattern = _PATTERNS.get(ext)
    if not pattern:
        return set()
    hits = []
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        for match in re.finditer(pattern, line):
            for group in match.groups():
                if group and group not in _NOT_NAMES:
                    hits.append((indent, group))
    if not hits:
        return set()
    outermost = min(indent for indent, _ in hits)
    return {name for indent, name in hits if indent == outermost}


def check(content: str, path) -> None:
    """Raise LangReject when a write would delete or duplicate a declaration.

    Two symmetric failures, both of which break a file just as thoroughly:

    DELETION — asked to add one helper, a model re-emitted a whole file and
    dropped nextTurn, updateScales and every log call with it. Nine rounds, each
    valid JavaScript, each accepted by R-AST. Validity is not preservation.

    DUPLICATION — a surgical patch added a second `const PATHS` beside the first.
    Two declarations of one name in one scope is a TypeError at load; the file
    parsed fine and never ran. A rule that only guards deletion would have
    allowed it, and did.

    Adding, editing and reordering stay free. Only losing a name, or having it
    twice, is refused.
    """
    from pathlib import Path

    from . import LangReject

    target = Path(path)
    ext = target.suffix

    # Duplication is checked on the NEW content alone — it needs no history.
    repeated = duplicates(content, ext)
    if repeated:
        shown = ", ".join(sorted(repeated)[:6])
        raise LangReject(
            f"R-PRESERVE: '{target.name}' declares {len(repeated)} name(s) twice: "
            f"{shown}. One scope cannot hold two declarations of a name — the "
            f"file parses and then fails at load. Patch the existing one instead "
            f"of adding a second.")

    if not target.exists():
        return                       # a new file deletes nothing
    try:
        old_text = target.read_text(encoding="utf-8")
    except OSError:
        return                       # unreadable: never block on inability to read

    before = module_scope(old_text, ext)
    if not before:
        return                       # nothing recognised: no basis to refuse
    lost = sorted(before - module_scope(content, ext))
    if not lost:
        return

    shown = ", ".join(lost[:6]) + (" …" if len(lost) > 6 else "")
    raise LangReject(
        f"R-PRESERVE: '{target.name}' rewrite drops {len(lost)} declaration(s): "
        f"{shown}. A rewrite may add or change, not delete. Patch the part you "
        f"mean to change, or delete the file first if the removal is intended.")


def duplicates(content: str, ext: str) -> set:
    """Names declared twice in the SAME scope.

    Scope is approximated by indentation, and deliberately conservatively: only
    declarations at the shallowest depth in the file count. A `const cell` in
    two different functions is ordinary and must not be flagged; a second
    `const PATHS` beside the first at module level is a TypeError at load.

    A regex cannot know scope for certain. Erring toward silence is right here:
    a false refusal blocks correct work, while a missed duplicate still fails
    loudly at load. This catches the module-level case, which is the one that
    happened.
    """
    if ext == ".py":
        try:
            import ast
            tree = ast.parse(content)
        except SyntaxError:
            return set()
        seen, twice = set(), set()
        for node in tree.body:                      # top level only, by construction
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in seen:
                    twice.add(node.name)
                seen.add(node.name)
        return twice

    pattern = _PATTERNS.get(ext)
    if not pattern:
        return set()

    hits = []                                        # (indent, name)
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        for match in re.finditer(pattern, line):
            for group in match.groups():
                if group and group not in _NOT_NAMES:
                    hits.append((indent, group))
    if not hits:
        return set()

    outermost = min(indent for indent, _ in hits)
    seen, twice = set(), set()
    for indent, name in hits:
        if indent != outermost:
            continue
        if name in seen:
            twice.add(name)
        seen.add(name)
    return twice
