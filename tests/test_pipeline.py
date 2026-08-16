"""pipeline + console_server: the runner and the surface that drives it.

These shipped without tests. Everything here is deterministic — no model call,
no daemon — so the parts that decide WHAT runs stay pinned even on a machine
with nothing installed.

The source-reading checks are deliberate: two of the bugs they guard were
invisible at runtime on a healthy box and only showed up as a wrong constant or
a skipped gate in the code itself.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)

import idea_tree  # noqa: E402
import pipeline  # noqa: E402


def _task(node_id, status="ready", name="f"):
    return idea_tree.Node(id=node_id, level="task", title=name, status=status,
                          file="storage/t/x.py", signature=f"def {name}() -> None",
                          contract="does one thing")


def _tree(structure_status="ready", task_status="ready"):
    return idea_tree.Node(id="I9", level="idea", title="i", status="ready", children=[
        idea_tree.Node(id="I9.S1", level="structure", title="s",
                       status=structure_status, file="storage/t/x.py",
                       children=[_task("I9.S1.T1", task_status, "one"),
                                 _task("I9.S1.T2", task_status, "two")])])


# ── the port must never be a constant ────────────────────────────────────

def test_console_declares_no_hardcoded_port():
    """Ports are per-project in HDS: each instance gets its own allocated block
    so two projects can run side by side. console_server shipped with
    `PORT = 8264`, which collides the moment a second project exists."""
    src = (ROOT / "console_server.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("PORT") and "=" in stripped:
            pytest.fail(f"hardcoded port survives: {stripped}")
    assert "resolve_port" in src, "the port must be resolved, not assumed"


def test_console_port_prefers_the_registry():
    import console_server
    port = console_server.resolve_port()
    assert isinstance(port, int) and 1024 < port < 65536


# ── privilege grants must be gated ───────────────────────────────────────

def test_add_project_is_not_a_trusted_system_call():
    """projects.json decides where the agent may write, so writing it must face
    the content scan. It was gated with the trusted-system-call level, which
    skips that scan — on the one file that grants filesystem reach.

    The check looks at the scribe CALL, not at any mention of the parameter:
    an earlier version matched its own explanatory docstring and failed on
    correct code.
    """
    src = (ROOT / "console_chat.py").read_text(encoding="utf-8")
    body = src[src.index("def add_project"):]
    call = body[body.index("scribe.execute"):]
    call = call[:call.index(")\n")]
    assert "protocol_size=None" not in call, "cage bypass on a privilege grant"
    assert "protocol_size=" in call, "the write must state a capability level"


# ── what the pipeline will and will not dispatch ─────────────────────────

def test_stopped_structure_holds_its_tasks():
    assert idea_tree.runnable_leaves(_tree(structure_status="stopped")) == []


def test_ready_tasks_are_runnable():
    root = _tree()
    assert [n.id for n in idea_tree.runnable_leaves(root)] == ["I9.S1.T1", "I9.S1.T2"]


def test_draft_tasks_are_not_dispatched():
    assert idea_tree.runnable_leaves(_tree(task_status="draft")) == []


def test_queue_link_survives_a_round_trip():
    """Without task_id a verdict has nowhere to return and the plan drifts from
    the queue — the failure task_bridge exists to prevent."""
    n = _task("I9.S1.T1")
    n.task_id, n.attempts, n.error = "TASK-1", 2, "boom"
    back = idea_tree.from_dict(n.to_dict())
    assert (back.task_id, back.attempts, back.error) == ("TASK-1", 2, "boom")


def test_structure_context_survives_a_round_trip():
    """The shared state a file's functions close over. Dropping it on save is
    how a module ends up with `global _session` that nothing declared."""
    s = idea_tree.Node(id="I9.S1", level="structure", title="s",
                       file="storage/t/x.py", context={"state": ["_q = []"]})
    assert idea_tree.from_dict(s.to_dict()).context == {"state": ["_q = []"]}


def test_dispatch_reuses_the_single_task_contract():
    """dispatch once assembled its own task dict and lost the one sentence that
    matters — "Implement EXACTLY ONE function". The model then wrote whole
    modules and files filled with duplicates."""
    src = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    body = src[src.index("def dispatch"):]
    assert "to_subtask" in body, "dispatch must not build its own task contract"


def test_max_in_flight_is_one():
    """One model is resident at a time, so a second concurrent task only queues
    behind the first while making the pipeline harder to reason about."""
    assert pipeline.MAX_IN_FLIGHT == 1
