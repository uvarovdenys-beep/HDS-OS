#!/usr/bin/env python3
"""mcp_server.py — HDS OS as an MCP server: agent-as-MCP.

Exposes the HDS **agent** (not just the cage) as MCP tools, so any MCP client
(a VS Code plugin, Claude, any MCP-capable editor) can ask HDS to develop
software and get back cage-verified files.

    agent_build          — build one file through the agent + cage
    agent_build_project  — build a coherent multi-file project
    agent_status         — poll a task
    agent_models         — what this machine actually serves

Everything runs behind the SAME hardened pipeline the local agent uses:
model resolution → canary → language-aware generation → CAGE (scribe: R-19,
R-01, R-AST, R-PATH) → watchdog → quarantine/model-escalation → archive.
The client never writes files: it states intent, the cage executes.

Requires the HDS agent daemon to be running (it drains the queue):
    HDS_SILENT=1 python3 agent/agent.py --monitor

Transport: MCP stdio (JSON-RPC 2.0 over stdin/stdout) — no SDK dependency.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import task_bridge  # noqa: E402  (single source of truth for enqueue/poll)

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "hds-os", "version": "1.1.0"}

TOOLS = [
    {
        "name": "agent_build",
        "description": (
            "Build ONE file with the HDS agent: a local model generates it and "
            "the HDS cage verifies it (no eval/exec/subprocess, syntax-checked, "
            "size-limited, path-confined) before it is written. Returns the "
            "cage's verdict and the written file path. Blocks until done."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string",
                                "description": "What the file must do."},
                "output_dir": {"type": "string",
                               "description": "Dir relative to the HDS root, e.g. 'storage/app'."},
                "output_filename": {"type": "string",
                                    "description": "File name; its extension picks the language, e.g. 'utils.py', 'app.js', 'style.css'."},
                "model": {"type": "string",
                          "description": "Optional model hint; HDS binds it to what the machine actually serves."},
                "reference_files": {
                    "type": "array",
                    "description": "Small files shown to the model as EXAMPLES to follow (a design system, an API, a house style). Paths relative to the HDS root, or inline {name, content} objects. An example steers the model far harder than prose.",
                    "items": {"type": ["string", "object"]},
                },
                "timeout": {"type": "integer",
                            "description": "Seconds to wait for a verdict (default 600)."},
            },
            "required": ["instruction", "output_dir", "output_filename"],
        },
    },
    {
        "name": "agent_build_project",
        "description": (
            "Build a coherent MULTI-FILE project. HDS decomposes it, generates "
            "dependency files before entry points, and feeds each file the real "
            "code of its siblings so imports and signatures actually match. "
            "Every file passes the cage. Blocks until done."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name (its dir)."},
                "structure": {
                    "type": "array",
                    "description": "Files to create, in dependency order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "instruction": {"type": "string"},
                        },
                        "required": ["file", "instruction"],
                    },
                },
                "model": {"type": "string"},
                "reference_files": {
                    "type": "array",
                    "description": "Small files shown to the model as EXAMPLES to follow (a design system, an API, a house style). Paths relative to the HDS root, or inline {name, content} objects. An example steers the model far harder than prose.",
                    "items": {"type": ["string", "object"]},
                },
                "timeout": {"type": "integer"},
            },
            "required": ["project", "structure"],
        },
    },
    {
        "name": "agent_status",
        "description": "Poll a previously submitted task: queued|running|completed|failed.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "agent_models",
        "description": "List the models this machine actually serves right now (ollama + LM Studio).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "agent_suggest_models",
        "description": (
            "Recommend a served model for a task, and — if a code task has no "
            "coder model available — suggest an install command for the USER to "
            "run. HDS never pulls a model itself."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_hint": {"type": "string",
                              "description": "What the task is about, e.g. 'python function', 'typescript class', 'general'."},
            },
        },
    },
]


def _text(obj) -> dict:
    """MCP tool result: a single text block."""
    body = obj if isinstance(obj, str) else json.dumps(obj, indent=2, ensure_ascii=False)
    return {"content": [{"type": "text", "text": body}]}


def _build(args: dict, project: bool) -> dict:
    task = {"type": "create_project" if project else "generate_code"}
    if project:
        task["project"] = args["project"]
        task["structure"] = args["structure"]
    else:
        task["instruction"] = args["instruction"]
        task["output_dir"] = args["output_dir"]
        task["output_filename"] = args["output_filename"]
    if args.get("model"):
        task["model"] = args["model"]
    # Reference examples ride along to the agent (and to every project subtask).
    if args.get("reference_files"):
        task["reference_files"] = args["reference_files"]

    receipt = task_bridge.submit(task)
    tid = receipt["task_id"]
    # A project fans out into subtasks; give it more room by default.
    default_to = 1800 if project else 600
    verdict = task_bridge.wait(tid, timeout=int(args.get("timeout", default_to)))
    verdict.setdefault("task_id", tid)
    if verdict.get("status") == "timeout":
        verdict["hint"] = ("Is the agent daemon running? "
                           "HDS_SILENT=1 python3 agent/agent.py --monitor")
    return verdict


def _models(_args: dict) -> dict:
    try:
        from model_scan import discover_models
        return {"served": discover_models()}
    except Exception as e:
        return {"served": {}, "error": f"model scan failed: {e}"}


def call_tool(name: str, args: dict) -> dict:
    if name == "agent_build":
        return _text(_build(args, project=False))
    if name == "agent_build_project":
        return _text(_build(args, project=True))
    if name == "agent_status":
        s = task_bridge.status(args["task_id"])
        return _text(s or {"task_id": args["task_id"], "status": "not_found"})
    if name == "agent_models":
        return _text(_models(args))
    if name == "agent_suggest_models":
        try:
            from model_advisor import suggest_models
            return _text(suggest_models(args.get("task_hint", "")))
        except Exception as e:
            return _text({"error": f"model advice failed: {e}"})
    return {"content": [{"type": "text", "text": f"unknown tool: {name}"}],
            "isError": True}


def handle(req: dict):
    """Route one JSON-RPC request. Returns a response dict, or None for notifications."""
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        p = req.get("params", {})
        try:
            result = call_tool(p.get("name", ""), p.get("arguments", {}) or {})
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"error: {e}"}],
                      "isError": True}
        return {"jsonrpc": "2.0", "id": rid, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main():
    # MCP stdio: one JSON-RPC message per line, responses on stdout.
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
