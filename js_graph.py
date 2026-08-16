#!/usr/bin/env python3
"""js_graph.py — declarations, parameters and calls for JavaScript/TypeScript.

The mirror graph could only parse Python, so every .ts/.js leaf of a plan came
back "unparsed" — honest, but blind on half the project (the VS Code plugin is
entirely TypeScript). This gives those files the same two facts the Python side
provides: what each top-level function DECLARES, and what it CALLS.

Regex, not a parser, and deliberately so: `lang/_locate.py` made the same call
and says why — the kernel is pure stdlib, and tree-sitter would buy precision at
the cost of a fragile dependency. The limit is stated rather than hidden: exotic
declarations are missed, and a miss shows up as "unparsed", never as a false
"unimplemented".
"""
import re

# Top-level declarations, mirroring lang/_preserve's patterns.
_DECL = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+"
               r"([A-Za-z$][\w$]*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)", re.M),
    # TypeScript puts the RETURN TYPE between the parameter list and the arrow
    # — `const f = (a: number): number => {` — so it must be allowed here, or
    # every typed arrow function is invisible to the graph.
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z$][\w$]*)\s*"
               r"(?::[^=]+)?=\s*(?:async\s*)?\(([^)]*)\)\s*"
               r"(?::[^=]+?)?\s*=>", re.M),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z$][\w$]*)\s*"
               r"(?::[^=]+)?=\s*(?:async\s*)?function\s*\(([^)]*)\)", re.M),
]

# Words that look like a call but are control flow.
NOT_CALLS = {"if", "for", "while", "switch", "catch", "return", "typeof",
             "function", "class", "await", "new", "do", "else", "in", "of"}

_CALL = re.compile(r"([A-Za-z_$][\w$]*)\s*\(")

_QUOTES = "\"'`"
_OPEN, _CLOSE = "([{<", ")]}>"


def strip_noise(source: str) -> str:
    """Blank the CONTENTS of strings and comments, keeping length and lines.

    The output has the same length and the same newlines as the input, so a line
    number computed on the cleaned text is the line number in the original.

    Written by hand deliberately. A character scanner has to state every edge
    case, and by then the spec IS the implementation — two models spent four
    attempts each on this one before the rule in CONVENTIONS.md was written.
    """
    out = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        two = source[i:i + 2]
        if two == "/*":
            out.append("  ")
            i += 2
            while i < n and source[i:i + 2] != "*/":
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue
        if two == "//":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch in _QUOTES:
            out.append(ch)              # keep the delimiters: length stays 1:1
            i += 1
            while i < n and source[i] != ch:
                if source[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                    continue
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append(ch)
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def params_of(raw: str) -> list:
    """Parameter NAMES from a raw JS/TS parameter list.

    Splits on commas at nesting depth zero, so `Map<string, number>` stays one
    parameter; drops types and defaults, because `a: number = 5` and `a` name
    the same parameter; and drops the dots from a rest argument.
    """
    parts, depth, current = [], 0, ""
    for ch in raw:
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
        if ch == "," and depth <= 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)

    names = []
    for part in parts:
        cut = len(part)
        for sep in (":", "="):
            at = part.find(sep)
            if at != -1:
                cut = min(cut, at)
        name = part[:cut].strip().lstrip(".*").strip()
        if name and name not in ("this", "cls"):
            names.append(name)
    return names


def symbols(source: str) -> dict:
    """{name: {"params": [...], "calls": [...]}} for top-level JS/TS functions.

    Calls are attributed to the declaration they sit under, by line order — a
    cheap approximation that is right for the flat, one-function-per-block files
    HDS generates, and honest about being an approximation for anything else.
    """
    clean = strip_noise(source)
    lines = clean.splitlines()
    found = {}
    for pat in _DECL:
        for m in pat.finditer(clean):
            name, raw = m.group(1), m.group(2)
            if name in found:
                continue
            found[name] = {"params": params_of(raw),
                           "start": clean[:m.start()].count("\n")}

    starts = sorted((v["start"], k) for k, v in found.items())
    for i, (line_no, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        body = "\n".join(lines[line_no:end])
        found[name]["calls"] = sorted({c for c in _CALL.findall(body)
                                       if c not in NOT_CALLS and c != name})
    for v in found.values():
        v.pop("start", None)
        v.setdefault("calls", [])
    return found
