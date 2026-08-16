#!/usr/bin/env python3
"""cage_tools.py — the CAGE itself, exposed over MCP.

`mcp_server.py` offers an editor HDS's local model. This offers something an
editor cannot get anywhere else: a write surface that refuses destructive and
dangerous edits. Cline, Continue, any MCP client already has a good model — what
it does not have is protection when that model overwrites a file.

The client sends intent, never bytes to disk:

    cage_write   — create or replace a whole file
    cage_patch   — replace exactly one function/class, or one line range
Every op runs the full cage: R-19 (single write surface), R-01 (size), R-PATH
(root confinement), R-AST (per-language content validation).

SCOPE OF THE CONTENT SCAN, stated exactly. R-AST validates files whose extension
is a KNOWN code type (scribe.CODE_EXTS: .py, .ts, .js, .go, .rs, .html, .svg …).
A code extension with no registered validator is REFUSED — fail-closed, never
written blind. Anything outside that list is treated as DATA: path- and
size-confined, but not content-scanned. So `notes.txt` and `thing.wat` are
written without inspection. Containment of what executes is the sandbox's job,
not this scan's.

A patch is validated as the RESULT, so surgery can never open a hole the
whole-file gate would have closed.

CAPABILITY. Ops arrive with protocol_size="l", never None. None means "trusted
system call" and SKIPS the content scan — correct for HDS's own internals, wrong
for an external editor. Passing None here would leave the cage in the call graph
while removing what it checks.
"""
import json
import json

# External clients are gated at L: broad enough to write real code, still fully
# content-scanned. Nothing here may raise it.
CLIENT_GATE = "l"

_PATH = {"type": "string",
         "description": "Path relative to the HDS root; escaping it is refused."}
_CONTENT = {"type": "string", "description": "The exact text to write."}
TOOLS = [
    {
        "name": "cage_write",
        "description": (
            "Create or replace a whole file through the HDS cage: size-checked, "
            "path-confined, and validated for its language. Use cage_patch "
            "instead when the file already exists."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"path": _PATH, "content": _CONTENT},
            "required": ["path", "content"],
        },
    },
    {
        "name": "cage_patch",
        "description": (
            "Replace exactly one function or class in an existing file; every "
            "other line stays untouched. Give 'target' (the function name; "
            "Python resolves it via AST) or explicit 'start'/'end' lines for "
            "other languages. The result is re-validated, so a patch that would "
            "break the file is refused."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": _PATH,
                "target": {"type": "string", "description": "Function/class to replace."},
                "start": {"type": "integer", "description": "First line (1-based)."},
                "end": {"type": "integer", "description": "Last line, inclusive."},
                "content": _CONTENT,
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "cage_insert",
        "description": (
            "Insert code after a named function/class ('after_target') or after "
            "a line ('after_line'), without rewriting the file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": _PATH,
                "after_target": {"type": "string", "description": "Insert after this."},
                "after_line": {"type": "integer", "description": "Insert after this line."},
                "content": _CONTENT,
            },
            "required": ["path", "content"],
        },
    },
]


TOOL_NAMES = {t["name"] for t in TOOLS}


def _op_for(name: str, args: dict) -> dict:
    """Translate one MCP call into a scribe task-script op."""
    path, content = args.get("path", ""), args.get("content", "")
    if not path:
        raise ValueError("path is required")

    if name == "cage_write":
        return {"op": "write", "path": path, "content": content}

    if name == "cage_patch":
        op = {"op": "patch", "path": path, "content": content}
        if args.get("target"):
            op["target"] = args["target"]
        elif args.get("start") is not None and args.get("end") is not None:
            op["start"], op["end"] = int(args["start"]), int(args["end"])
        else:
            raise ValueError(
                "cage_patch needs either 'target' or both 'start' and 'end' — "
                "guessing which lines to replace is how a patch destroys code")
        return op

    if name == "cage_insert":
        op = {"op": "insert", "path": path, "content": content}
        if args.get("after_target"):
            op["after_target"] = args["after_target"]
        elif args.get("after_line") is not None:
            op["after_line"] = int(args["after_line"])
        else:
            raise ValueError(
                "cage_insert needs either 'after_target' or 'after_line'")
        return op

    raise ValueError(f"unknown cage tool: {name}")


# MCP carries JSON strings. A byte like 0x89 (the first byte of a PNG) has no
# faithful representation there: it round-trips as UTF-8 and the file lands
# corrupt — 25 bytes where 24 were meant, signature c289… instead of 8950….
# Measured, not assumed. Refusing is the honest answer; silently writing a
# broken image is the one thing worse than saying no.
BINARY_EXTS = (
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".wav", ".mov", ".avi", ".webm",
    ".so", ".dylib", ".dll", ".exe", ".wasm", ".pyc", ".class", ".jar",
)


def _refuse_binary(path: str):
    """Return a refusal for a path this transport cannot carry intact."""
    low = str(path).lower()
    if low.endswith(BINARY_EXTS):
        ext = "." + low.rsplit(".", 1)[-1]
        return {"ok": False, "refused_by": "cage",
                "reason": f"'{ext}' is a binary format and MCP carries text: "
                          f"writing it through this tool would corrupt it.",
                "hint": "Copy the file with a shell command, or have the tool "
                        "that produces it write it directly. Text formats "
                        "(.svg, .json, .md, source code) are fine."}
    return None


def call(name: str, args: dict) -> dict:
    """Run one cage op. Returns an MCP tool result.

    A refusal is returned as an ERROR RESULT, not an exception: the client's
    model should read the cage's reason and correct itself, which is the whole
    point of putting the cage in front of it.
    """
    refusal = _refuse_binary(args.get("path", ""))
    if refusal is not None:
        return _result(refusal, is_error=True)

    try:
        op = _op_for(name, args)
    except ValueError as e:
        return _result({"ok": False, "error": str(e)}, is_error=True)

    try:
        import scribe
        applied = scribe.execute(op, protocol_size=CLIENT_GATE)
    except Exception as e:
        return _result(
            {"ok": False, "refused_by": "cage", "reason": str(e),
             "hint": "Fix the content or narrow the edit, then retry. The file "
                     "on disk is unchanged."},
            is_error=True)

    return _result({"ok": True, "applied": applied,
                    "note": "written through the cage; unrelated lines untouched"})


def _result(payload: dict, is_error: bool = False) -> dict:
    out = {"content": [{"type": "text",
                        "text": json.dumps(payload, indent=2, ensure_ascii=False)}]}
    if is_error:
        out["isError"] = True
    return out
