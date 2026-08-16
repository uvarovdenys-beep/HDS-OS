#!/usr/bin/env python3
"""context.py — write a file's shared state BEFORE its functions are generated.

Measured, not theorised. A three-function session module was generated one
function at a time. Each function correctly wrote `global _session`, and the
module still failed to import:

    NameError: name '_session' is not defined

The declaration belongs to no function, so no function emitted it. While the
model was ignoring the grate and dumping whole modules, the line appeared by
accident inside the noise; the moment extraction started cutting cleanly, it
vanished with the noise. Cleaner output exposed the real hole.

So the structure node declares its own module state, and this materialises it
into the file BEFORE any task runs. The functions are then patched into a file
where `_session` already exists — they cannot invent a different name for it,
because a different name simply will not resolve.

That is the same move as the cage: constrain, do not instruct.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# A header is state and imports, not logic. Anything longer is a function that
# has not been planned yet, and it would sit outside the tree where nothing
# tests it.
MAX_HEADER_LINES = 40


class ContextError(Exception):
    """The shared state cannot be trusted. Fail closed — never half-write it."""


def header_for(node) -> str:
    """Build the file header from a structure node's declared context.

    Shape on the node (all optional):
        node.context = {"imports": [...], "state": [...], "types": [...]}
    """
    ctx = getattr_safe(node)
    if not ctx:
        return ""
    parts = []
    for key in ("imports", "types", "state"):
        lines = [str(x).rstrip() for x in (ctx.get(key) or []) if str(x).strip()]
        if lines:
            parts.append("\n".join(lines))
    body = "\n\n".join(parts)
    if not body:
        return ""
    if len(body.splitlines()) > MAX_HEADER_LINES:
        raise ContextError(
            f"'{node.id}': header is {len(body.splitlines())} lines, limit is "
            f"{MAX_HEADER_LINES} — that is logic, and logic belongs in a task")
    return body.rstrip() + "\n"


def getattr_safe(node) -> dict:
    """Read node.context without reflection (the cage rejects getattr)."""
    try:
        ctx = node.context
    except AttributeError:
        return {}
    return ctx if isinstance(ctx, dict) else {}


def materialise(node, root_dir=None) -> dict:
    """Write the header into the structure's file through the cage.

    Returns {"ok", "path", "wrote", "note"}. Idempotent: if the declared state
    is already present the file is left untouched, so re-running a structure
    never duplicates its own header.
    """
    if node.level != "structure":
        raise ContextError(f"'{node.id}' is a {node.level}; only a structure "
                           f"owns a file and therefore its shared state")
    if not node.file:
        raise ContextError(f"'{node.id}' names no file")

    header = header_for(node)
    if not header:
        return {"ok": True, "path": node.file, "wrote": False,
                "note": "no context declared"}

    import scribe
    target = ROOT / node.file
    existing = target.read_text(encoding="utf-8") if target.exists() else ""

    missing = [ln for ln in header.splitlines()
               if ln.strip() and ln.strip() not in existing]
    if not missing:
        return {"ok": True, "path": node.file, "wrote": False,
                "note": "already present"}

    if existing:
        # Prepend: the state must precede every function that closes over it.
        content = header + "\n" + existing.lstrip("\n")
    else:
        content = header
    scribe.execute({"op": "write", "path": node.file, "content": content},
                   protocol_size="l")
    return {"ok": True, "path": node.file, "wrote": True,
            "note": f"{len(missing)} line(s) declared"}


def declared_names(node) -> list:
    """The names this header defines, so a task can be told what already exists."""
    ctx = getattr_safe(node)
    names = []
    for line in (ctx.get("state") or []):
        text = str(line).strip()
        if "=" in text:
            lhs = text.split("=", 1)[0].strip()
            if ":" in lhs:
                lhs = lhs.split(":", 1)[0].strip()
            if lhs.isidentifier():
                names.append(lhs)
    return names
