"""The cage exposed over MCP — what an external editor may and may not do.

`test_client_gate_is_never_none` is the load-bearing one: protocol_size=None
means "trusted system call" and SKIPS the content scan. If a refactor ever sets
the client gate to None, every test below still passes while the cage silently
stops inspecting anything an editor sends.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CLEAN = ("def area(w: float, h: float) -> float:\n"
         "    return w * h\n\n\n"
         "def stub() -> int:\n"
         "    return 0\n")
SUBPROCESS_PAYLOAD = ("import subprocess\n\n"
                      "def pwn():\n"
                      "    subprocess.run(['echo', 'x'])\n")
EVAL_PAYLOAD = "def run(s):\n    return eval(s)\n"


def _body(result):
    return json.loads(result["content"][0]["text"])


def _demo(name="geo.py"):
    return f"storage/cage_tools_test/{name}"


def _cleanup(rel):
    p = ROOT / rel
    if p.exists():
        p.unlink()


# ── the invariant that makes all of this mean anything ───────────────────

def test_client_gate_is_never_none():
    """None disables R-AST. An external client must never be handed that."""
    import cage_tools
    assert cage_tools.CLIENT_GATE is not None
    assert cage_tools.CLIENT_GATE in ("s", "m", "l", "xl")


# ── writes ───────────────────────────────────────────────────────────────

def test_clean_write_is_applied():
    import cage_tools
    rel = _demo()
    try:
        r = cage_tools.call("cage_write", {"path": rel, "content": CLEAN})
        assert not r.get("isError")
        assert _body(r)["ok"] is True
        assert (ROOT / rel).exists()
    finally:
        _cleanup(rel)


def test_subprocess_payload_is_refused():
    import cage_tools
    rel = _demo("evil.py")
    try:
        r = cage_tools.call("cage_write", {"path": rel, "content": SUBPROCESS_PAYLOAD})
        assert r.get("isError")
        assert _body(r)["refused_by"] == "cage"
        assert not (ROOT / rel).exists(), "a refused write must not touch disk"
    finally:
        _cleanup(rel)


def test_eval_payload_is_refused():
    import cage_tools
    rel = _demo("ev.py")
    try:
        r = cage_tools.call("cage_write", {"path": rel, "content": EVAL_PAYLOAD})
        assert r.get("isError")
    finally:
        _cleanup(rel)


def test_path_escape_is_refused():
    import cage_tools
    r = cage_tools.call("cage_write",
                        {"path": "../../../tmp/hds_escape.py", "content": "x = 1\n"})
    assert r.get("isError")
    assert "R-PATH" in _body(r)["reason"]
    assert not Path("/tmp/hds_escape.py").exists()


def test_missing_path_is_an_error_not_a_crash():
    import cage_tools
    r = cage_tools.call("cage_write", {"content": "x = 1\n"})
    assert r.get("isError")
    assert "path" in _body(r)["error"]


# ── surgery: the reason an editor wants this at all ──────────────────────

def test_patch_replaces_only_its_target():
    import cage_tools
    rel = _demo()
    try:
        cage_tools.call("cage_write", {"path": rel, "content": CLEAN})
        before = (ROOT / rel).read_text(encoding="utf-8").splitlines()
        area_block = before[:2]

        r = cage_tools.call("cage_patch", {
            "path": rel, "target": "stub",
            "content": "def stub() -> int:\n    return 42\n"})
        assert not r.get("isError")

        after = (ROOT / rel).read_text(encoding="utf-8")
        assert "return 42" in after
        assert after.splitlines()[:2] == area_block, "neighbour was modified"
    finally:
        _cleanup(rel)


def test_patch_without_an_anchor_is_refused():
    """Guessing which lines to replace is how a patch destroys code."""
    import cage_tools
    rel = _demo()
    try:
        cage_tools.call("cage_write", {"path": rel, "content": CLEAN})
        r = cage_tools.call("cage_patch", {"path": rel, "content": "x = 1\n"})
        assert r.get("isError")
        assert "target" in _body(r)["error"]
    finally:
        _cleanup(rel)


def test_patch_that_would_break_the_file_is_refused():
    """Surgery never becomes a hole: the RESULT faces the whole-file gate."""
    import cage_tools
    rel = _demo()
    try:
        cage_tools.call("cage_write", {"path": rel, "content": CLEAN})
        r = cage_tools.call("cage_patch", {
            "path": rel, "target": "stub",
            "content": "def stub():\n    return eval('2+2')\n"})
        assert r.get("isError")
        assert "return 0" in (ROOT / rel).read_text(encoding="utf-8")
    finally:
        _cleanup(rel)


def test_insert_adds_without_rewriting():
    import cage_tools
    rel = _demo()
    try:
        cage_tools.call("cage_write", {"path": rel, "content": CLEAN})
        r = cage_tools.call("cage_insert", {
            "path": rel, "after_target": "stub",
            "content": "\n\ndef extra() -> int:\n    return 7\n"})
        assert not r.get("isError")
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "def extra" in text and "def area" in text and "def stub" in text
    finally:
        _cleanup(rel)


def test_insert_without_an_anchor_is_refused():
    import cage_tools
    rel = _demo()
    try:
        cage_tools.call("cage_write", {"path": rel, "content": CLEAN})
        r = cage_tools.call("cage_insert", {"path": rel, "content": "x = 1\n"})
        assert r.get("isError")
    finally:
        _cleanup(rel)


# ── wiring ───────────────────────────────────────────────────────────────

def test_unknown_tool_is_reported():
    import cage_tools
    r = cage_tools.call("cage_nope", {"path": "storage/x.py", "content": "x = 1\n"})
    assert r.get("isError")


def test_mcp_server_advertises_the_cage_tools():
    import mcp_server
    names = [t["name"] for t in mcp_server.TOOLS]
    for expected in ("cage_write", "cage_patch", "cage_insert"):
        assert expected in names


def test_binary_formats_are_refused_not_corrupted():
    """MCP carries text. A PNG written through it lands corrupt — measured: 25
    bytes for 24, signature c289… instead of 8950…. Refusing is the honest
    answer; silently writing a broken file is worse than saying no."""
    import cage_tools
    rel = _demo("pic.png")
    try:
        r = cage_tools.call("cage_write", {"path": rel, "content": "\x89PNG\r\n"})
        assert r.get("isError")
        assert "binary" in _body(r)["reason"]
        assert not (ROOT / rel).exists()
    finally:
        _cleanup(rel)


def test_text_formats_are_still_allowed():
    """.svg is markup, not binary — the refusal must not over-reach."""
    import cage_tools
    rel = _demo("logo.svg")
    try:
        r = cage_tools.call("cage_write", {
            "path": rel, "content": '<svg xmlns="http://www.w3.org/2000/svg"/>'})
        assert not r.get("isError")
    finally:
        _cleanup(rel)
