"""_locate.py — find a declaration's line range in languages without an AST.

WHY THIS EXISTS. `patcher.locate` calls `ast.parse`, so surgical patching works
for Python and nowhere else. Ten languages have validators; one can be edited by
function name. That asymmetry is not academic: a game file was rewritten whole
nine times because JavaScript could not be patched, and each rewrite silently
dropped working code.

WHAT IT IS, AND IS NOT. A locator, not a parser. It finds where a declaration
starts using the same patterns `_preserve` already uses, then walks forward to
the matching close — counting braces for C-family languages, `end` keywords for
Ruby, indentation for Python-like blocks. String literals and comments are
skipped so a brace inside "}" or /* } */ cannot end a function early.

It refuses rather than guesses: an ambiguous or unbalanced target raises, and
the caller falls back to an explicit line range. A wrong range would delete
working code, which is the exact failure this is meant to prevent.

Adding tree-sitter would be more precise and would cost a dependency; the kernel
is pure stdlib on purpose. This buys most of the value for none of that.
"""
import re

from ._preserve import _PATTERNS

# How a block ends, per language family.
BRACE = "brace"      # C, C++, C#, Java, JS, TS, Go, Rust, PHP, Swift, shell
END = "end"          # Ruby
INDENT = "indent"    # Python (handled by ast elsewhere; here as a fallback)

_STYLE = {}
for _ext in (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".c", ".h", ".cpp",
             ".cc", ".hpp", ".cs", ".java", ".go", ".rs", ".php", ".swift",
             ".sh", ".bash"):
    _STYLE[_ext] = BRACE
_STYLE[".rb"] = END


class LocateError(Exception):
    """The target could not be located with certainty. Never guess a range."""


# Class methods: the measured gap. Top-level functions already locate in every
# brace language, but a `Class.method` target did not resolve anywhere. In
# JS/TS a method is simply `name(...) { … }` inside the class body (no return
# type BEFORE the name, unlike C#/C++/Java), so it can be found reliably without
# a parser. Those return-type families stay on the safe fallback — that is
# genuinely tree-sitter's job, and this file is stdlib on purpose.
_JS_METHOD_EXTS = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}
_JS_METHOD_MODS = r"(?:(?:static|async|get|set|public|private|protected|readonly|override|abstract|\*)\s+)*"


def _cleaned(lines):
    """All lines with strings/comments blanked — computed once, comment state
    carried across lines."""
    out, in_comment = [], False
    for line in lines:
        clean, in_comment = _strip_noise(line, in_comment)
        out.append(clean)
    return out


def _js_class_span(lines, cls):
    """(start, end) 0-based inclusive of `class cls { … }`. Unambiguous or raise."""
    pat = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+"
                     + re.escape(cls) + r"\b")
    clean = _cleaned(lines)
    hits = [i for i, c in enumerate(clean) if pat.search(c)]
    if not hits:
        raise LocateError(f"class not found: {cls}")
    if len(hits) > 1:
        raise LocateError(f"class is ambiguous ({len(hits)} matches): {cls}")
    return hits[0], _brace_end(lines, hits[0])


def _js_method_span(lines, cls, method):
    """(start, end) 0-based inclusive of `method` inside class `cls` (JS/TS)."""
    cstart, cend = _js_class_span(lines, cls)
    pat = re.compile(r"^\s*" + _JS_METHOD_MODS + re.escape(method)
                     + r"\s*(?:<[^>]*>)?\s*\(")
    clean = _cleaned(lines)
    hits = []
    for idx in range(cstart, cend + 1):
        c = clean[idx]
        if not pat.match(c):
            continue
        # A call statement (`method();`) is not a declaration — a real method
        # opens a body. Skip a line that ends in `;` and never opens a brace.
        if c.rstrip().endswith(";") and "{" not in c:
            continue
        hits.append(idx)
    if not hits:
        raise LocateError(f"method not found: {cls}.{method}")
    if len(hits) > 1:
        raise LocateError(f"method is ambiguous ({len(hits)} matches): {cls}.{method}")
    return hits[0], _brace_end(lines, hits[0])


def _strip_noise(line: str, in_block_comment: bool):
    """Blank out strings and comments so their braces are not counted.

    Returns (cleaned_line, still_in_block_comment). Characters are replaced by
    spaces rather than removed, so column positions stay meaningful.
    """
    out = []
    i, n = 0, len(line)
    quote = ""
    while i < n:
        two = line[i:i + 2]
        if in_block_comment:
            if two == "*/":
                in_block_comment = False
                out.append("  ")
                i += 2
                continue
            out.append(" ")
            i += 1
            continue
        if quote:
            if line[i] == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
                continue
            if line[i] == quote:
                quote = ""
            out.append(" ")
            i += 1
            continue
        if two == "/*":
            in_block_comment = True
            out.append("  ")
            i += 2
            continue
        if two == "//" or line[i] == "#":
            out.append(" " * (n - i))
            break
        if line[i] in "\"'`":
            quote = line[i]
            out.append(" ")
            i += 1
            continue
        out.append(line[i])
        i += 1
    return "".join(out), in_block_comment


def _declaration_line(lines, target, ext):
    """The 0-based line where `target` is declared. Raises if 0 or 2+ matches."""
    pattern = _PATTERNS.get(ext)
    if not pattern:
        raise LocateError(f"no declaration pattern for '{ext}'")
    hits = []
    for idx, line in enumerate(lines):
        for match in re.finditer(pattern, line):
            for group in match.groups():
                if group == target:
                    hits.append(idx)
    if not hits:
        raise LocateError(f"target not found: {target}")
    if len(hits) > 1:
        raise LocateError(f"target is ambiguous ({len(hits)} matches): {target}")
    return hits[0]


def _brace_end(lines, start):
    """Last line of a brace-delimited block that opens at or after `start`."""
    depth, seen_open, in_comment = 0, False, False
    for idx in range(start, len(lines)):
        clean, in_comment = _strip_noise(lines[idx], in_comment)
        for ch in clean:
            if ch == "{":
                depth += 1
                seen_open = True
            elif ch == "}":
                depth -= 1
                if seen_open and depth == 0:
                    return idx
        # A declaration with no body at all — a prototype or an interface line.
        if not seen_open and clean.rstrip().endswith(";"):
            return idx
    raise LocateError("unbalanced braces: the block never closes")


def _end_keyword_end(lines, start):
    """Last line of a Ruby def/class/module, matched by nesting depth."""
    opener = re.compile(r"(?m)^\s*(?:def|class|module|if|unless|case|while|until|begin|do)\b")
    closer = re.compile(r"(?m)^\s*end\b")
    depth = 0
    for idx in range(start, len(lines)):
        line = lines[idx]
        if opener.search(line):
            depth += 1
        # `x = 1 if cond` is a modifier, not a block; it takes no `end`.
        if closer.search(line):
            depth -= 1
            if depth == 0:
                return idx
    raise LocateError("unbalanced block: no matching 'end'")


def locate(source: str, target: str, ext: str):
    """Return (start, end), 1-indexed inclusive, for `target` in `source`.

    Raises LocateError when the target is missing, ambiguous or unbalanced —
    the caller must then fall back to an explicit range rather than risk
    deleting the wrong lines.
    """
    style = _STYLE.get(ext)
    if style is None:
        raise LocateError(f"no locator for '{ext}'")

    lines = source.splitlines()
    if "." in target and ext in _JS_METHOD_EXTS:
        cls, method = target.rsplit(".", 1)
        start, end = _js_method_span(lines, cls, method)
    else:
        start = _declaration_line(lines, target, ext)
        end = _brace_end(lines, start) if style == BRACE else _end_keyword_end(lines, start)

    # Carry leading decorators and attributes up with the declaration, so a
    # patch replaces the whole unit rather than orphaning them.
    lead = start
    while lead > 0:
        above = lines[lead - 1].strip()
        if above.startswith("@") or above.startswith("[") or above.startswith("///"):
            lead -= 1
        else:
            break
    return lead + 1, end + 1


def can_locate(ext: str) -> bool:
    return ext in _STYLE
