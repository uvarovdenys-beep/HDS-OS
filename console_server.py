#!/usr/bin/env python3
"""console_server.py — the agent console, backed by the real pipeline.

The mockup proved the layout; it could not prove the WORKFLOW, because every
number in it was invented. A console that shows fabricated state cannot be
tested — it can only be admired. This serves the same page against the actual
tree, so clicking "accept" moves a real node and "dispatch" queues a real task.

Read paths return live state. Write paths go through tree_tools / pipeline,
which go through the cage — the console gets no privilege the MCP client does
not already have.

NOTE this is an OS-INTERNAL module: it reads os.environ for its port override
(HDS_CONSOLE_PORT). The cage rejects `os` in AI-GENERATED payloads by design;
OS internals are written as trusted system calls instead. That distinction is
deliberate, not a bypass.

    python3 console_server.py       # port from the instance registry
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATIC = ROOT / "storage" / "mockup"


def resolve_port() -> int:
    """This instance's console port — from the registry, never a constant.

    Ports are per-project in HDS: each instance is allocated its own block
    (vision/browser/webhook) so two projects can run side by side without
    fighting for a socket. This file shipped with `PORT = 8264` hardcoded,
    which breaks the moment a second project exists.

    Precedence mirrors the webhook server: $HDS_CONSOLE_PORT, then the latest
    allocated instance, offset from its webhook port so the console lands in
    that same per-instance block.
    """
    import os as _os
    env = _os.environ.get("HDS_CONSOLE_PORT")
    if env:
        return int(env)
    try:
        from port_registry import PortRegistry
        registry = PortRegistry.load_registry()
    except Exception:
        registry = None
    if registry:
        latest = max(registry.values(), key=lambda c: c.get("created_at", 0))
        webhook = latest.get("webhook_port")
        if webhook:
            return int(webhook) + 4
    raise SystemExit(
        "No console port allocated. Run: python3 agent/port_registry.py "
        "--allocate  (ports are per-project; there is no default)")


def _tree_json(project, idea):
    import idea_tree
    import pipeline
    root, _ = pipeline._load(project, idea)
    return root.to_dict()


def state(project="default"):
    """Everything the console draws, in one call — plan, pipeline, health."""
    import pipeline
    from lang._toolchain import missing as missing_tools
    out = {"project": project, "projects": pipeline.projects(),
           "ideas": [], "status": pipeline.status(project)}
    # Live verification stage per running task — what the console rail draws in
    # its cage/acceptance/monte lanes. Structured telemetry, not a parsed log.
    try:
        import telemetry
        _evts = telemetry.events()
        out["stages"] = {r["task_id"]: telemetry.current_stage(r["task_id"], _evts)
                         for idea in out["status"].get("ideas", [])
                         for r in idea.get("running", []) if r.get("task_id")}
    except Exception:
        out["stages"] = {}
    # Live verification stage per running task — what the console rail draws in
    # its cage/acceptance/monte lanes. Structured telemetry, not a parsed log.
    try:
        import telemetry
        _evts = telemetry.events()
        out["stages"] = {r["task_id"]: telemetry.current_stage(r["task_id"], _evts)
                         for idea in out["status"].get("ideas", [])
                         for r in idea.get("running", []) if r.get("task_id")}
    except Exception:
        out["stages"] = {}
    for name in pipeline.ideas(project):
        out["ideas"].append({"id": name, "tree": _tree_json(project, name)})

    try:
        from sandbox.runner import SandboxRunner
        isolated = SandboxRunner().isolated
    except Exception:
        isolated = False
    try:
        from sysmon import free_ram_mb
        ram = free_ram_mb()
    except Exception:
        ram = None
    out["health"] = {"isolated": isolated, "free_ram_mb": ram,
                     "missing_tools": [t["tool"] for t in missing_tools()]}
    return out


def registry(project="default"):
    """Files and the symbols already in them — what a task may reuse."""
    from orchestrator_index import build_index
    try:
        idx = build_index(str(ROOT / "agent"))
    except Exception as e:
        return {"files": [], "note": f"index unavailable: {e}"}
    files = []
    for mod in idx.get("modules", []):
        files.append({"file": "agent/" + mod.get("filename", ""),
                      "symbols": [s.get("name") for s in mod.get("symbols", [])][:24]})
    return {"files": files, "total": len(files)}


def act(body):
    """One write. Everything routes through the same tools the MCP client uses."""
    import pipeline
    import tree_tools
    what = body.get("action")
    project = body.get("project", "default")

    if what == "chat":
        from console_chat import chat
        return chat(project, body.get("level", "ask"), body.get("text", ""),
                    body.get("model", ""), body.get("node", ""))
    if what == "projects":
        from console_chat import projects
        return {"projects": projects()}
    if what == "add_project":
        from console_chat import add_project
        return add_project(body.get("name", ""), body.get("path", ""))

    if what in ("tree_create", "tree_propose", "tree_accept", "tree_next",
                "tree_stop", "tree_show"):
        res = tree_tools.call(what, body.get("args") or {})
        return json.loads(res["content"][0]["text"])
    if what == "cycle":
        return pipeline.cycle(project)
    if what == "dispatch":
        return {"dispatched": pipeline.dispatch(project)}
    if what == "stop":
        return pipeline.stop(project, body["node"])
    if what == "resume":
        return pipeline.resume(project, body["node"])
    if what == "retry":
        return pipeline.retry(project, body["node"])
    raise ValueError(f"unknown action: {what}")


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            try:
                return self._send(state())
            except Exception as e:
                return self._send({"error": str(e)}, 500)
        if path == "/api/models":
            # Listing models must not COST a model call. An earlier console
            # routed this through chat(), so startup blocked on an inference
            # and the page sat blank with a disabled composer.
            try:
                from model_scan import discover_models
                served = discover_models()
                return self._send({"models": sorted(
                    s for v in served.values() for s in v)})
            except Exception as e:
                return self._send({"models": [], "error": str(e)})
        if path == "/api/registry":
            return self._send(registry())

        name = path.lstrip("/") or "console.html"
        target = (STATIC / name).resolve()
        # Serve only from the static dir: a console is not a file browser.
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            return self._send({"error": "not found"}, 404)
        data = target.read_bytes()
        ctype = ("text/html; charset=utf-8" if target.suffix == ".html"
                 else "image/svg+xml" if target.suffix == ".svg"
                 else "text/plain; charset=utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlparse(self.path).path != "/api/act":
            return self._send({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            return self._send(act(body))
        except Exception as e:
            return self._send({"ok": False, "error": str(e)}, 400)

    def log_message(self, *args):
        pass  # NO-OP: the console polls; an access log would drown the terminal


def main():
    """Threaded on purpose: a chat turn blocks for seconds while the local model
    thinks, and the console polls state throughout. Single-threaded, that one
    request froze the whole page — including the reply it was waiting for."""
    port = resolve_port()
    print(f"console  http://127.0.0.1:{port}/console.html")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
