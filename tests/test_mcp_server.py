"""agent-as-MCP: protocol contract + the bridge every front-end shares.

These run without any model: they assert the JSON-RPC surface and that the
bridge's enqueue/poll contract is the single implementation both the HTTP
webhook and the MCP server use.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent"))


def _rpc(*messages):
    """Drive the MCP router in-process (no subprocess: the OS keeps a single
    exec-path, and tests must not open a second one). Returns responses by id.
    """
    import mcp_server
    out = {}
    for m in messages:
        resp = mcp_server.handle(m)
        if resp is not None:
            out[resp.get("id")] = resp
    return out


def test_initialize_handshake():
    r = _rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    res = r[1]["result"]
    assert res["serverInfo"]["name"] == "hds-os"
    assert "protocolVersion" in res
    assert "tools" in res["capabilities"]


def test_tools_list_exposes_the_agent_not_just_the_cage():
    r = _rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in r[2]["result"]["tools"]}
    # agent-as-MCP: the full pipeline is exposed, not a bare write_file gate
    assert {"agent_build", "agent_build_project", "agent_status",
            "agent_models"} <= names
    assert "write_file" not in names


def test_unknown_method_errors_cleanly():
    r = _rpc({"jsonrpc": "2.0", "id": 9, "method": "nope/there"})
    assert r[9]["error"]["code"] == -32601


def test_notification_produces_no_response():
    r = _rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert r == {}


def test_bridge_is_shared_by_webhook_and_mcp():
    """Both front-ends must import the same bridge — no duplicated contract."""
    hook = (ROOT / "agent" / "webhook_server_enhanced.py").read_text()
    mcp = (ROOT / "mcp_server.py").read_text()
    assert "task_bridge" in hook and "task_bridge" in mcp
    # the old inline duplicate must be gone from the webhook
    assert "BUILD_TYPES = {" not in hook


def test_bridge_status_of_unknown_task_is_none():
    import task_bridge
    assert task_bridge.status("NO-SUCH-TASK-xyz") is None


def test_bridge_classifies_build_tasks():
    import task_bridge
    assert task_bridge.is_build_task({"type": "generate_code"})
    assert task_bridge.is_build_task({"type": "create_project"})
    assert not task_bridge.is_build_task({"type": "capture_screen"})
    assert not task_bridge.is_build_task({})


def test_missing_sibling_import_fixer():
    """Adds `import <sibling>` when a sibling module is referenced but not
    imported (the stack_vm/opcodes coherence slip); no dup, no false add."""
    import tempfile
    from pathlib import Path as _P
    sys.path.insert(0, str(ROOT))
    from agent import HDSAgent as A
    with tempfile.TemporaryDirectory() as td:
        _P(td, "opcodes.py").write_text("PUSH=1")
        _P(td, "vm.py").write_text("class VM: pass")
        # referenced but not imported → added
        bad = "from vm import VM\nx = opcodes.PUSH\n"
        assert "import opcodes" in A._add_missing_sibling_imports(bad, td, "demo.py")
        # already imported → not duplicated
        good = "import opcodes\nx = opcodes.PUSH\n"
        assert A._add_missing_sibling_imports(good, td, "demo.py").count("import opcodes") == 1
        # not referenced → untouched
        none = "from vm import VM\nx = 1\n"
        assert "import opcodes" not in A._add_missing_sibling_imports(none, td, "demo.py")


def test_ram_preflight_enforces_single_model_floor():
    """SINGLE_MODEL rule: refuse to load a model when free RAM is below the
    floor; allow when above; never block when RAM is unmeasurable."""
    import os as _os
    sys.path.insert(0, str(ROOT))
    from agent import HDSAgent as A

    class Stub(A):
        def __init__(self):
            pass
    s = Stub()
    free = A._free_ram_mb()
    if free is None:
        # unmeasurable → must ALLOW (never block on inability to measure)
        assert s._ram_ok_for_model()[0] is True
        return
    _os.environ["HDS_MIN_FREE_MB"] = "1"
    assert s._ram_ok_for_model()[0] is True
    _os.environ["HDS_MIN_FREE_MB"] = str(free + 10_000_000)
    assert s._ram_ok_for_model()[0] is False
    del _os.environ["HDS_MIN_FREE_MB"]


def test_model_advisor_suggests_install_when_no_coder():
    """Code task + no coder served → propose an install command (for the USER).
    A served coder → recommend it, no install nag. Never pulls models itself."""
    sys.path.insert(0, str(ROOT / "agent"))
    import model_advisor as ma
    orig = ma.suggest_models.__globals__.get("discover_models")
    # monkeypatch discovery via the function's import site
    import model_scan
    saved = model_scan.discover_models
    try:
        model_scan.discover_models = lambda: {"ollama": ["llama3:latest",
                                                          "mistral:latest"]}
        r = ma.suggest_models("a python function")
        assert r["is_code_task"] is True
        assert r["install_suggestion"] is not None
        assert "ollama pull" in r["install_suggestion"]["install"]

        model_scan.discover_models = lambda: {"ollama": ["qwen2.5-coder:14b"]}
        r2 = ma.suggest_models("a python function")
        assert r2["install_suggestion"] is None
        assert "coder" in r2["recommended"].lower()

        r3 = ma.suggest_models("write a haiku")
        assert r3["is_code_task"] is False
    finally:
        model_scan.discover_models = saved
        _ = orig


def test_reference_files_block():
    """Small files can be passed as EXAMPLES: inline dicts, paths, size-capped,
    and a bad reference is skipped rather than breaking the build."""
    import tempfile
    from pathlib import Path as _P
    sys.path.insert(0, str(ROOT))
    from agent import HDSAgent as A

    class Stub(A):
        BASE_DIR = _P(".")
        def __init__(self):
            pass
    s = Stub()
    b = s._reference_block([{"name": "tokens.css", "content": ":root{--accent:#37c2c4}"}])
    assert "REFERENCE EXAMPLE" in b and "--accent" in b
    with tempfile.NamedTemporaryFile("w", suffix=".css", delete=False) as f:
        f.write("body{background:#0e1318}")
        path = f.name
    assert "#0e1318" in s._reference_block([path])
    assert "truncated" in s._reference_block([{"name": "big.css", "content": "x" * 99999}])
    assert s._reference_block(["/nope/missing.css"]) == ""
    assert s._reference_block(None) == ""


def test_mcp_build_tools_accept_reference_files():
    r = _rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = {t["name"]: t for t in r[2]["result"]["tools"]}
    for name in ("agent_build", "agent_build_project"):
        assert "reference_files" in tools[name]["inputSchema"]["properties"]
