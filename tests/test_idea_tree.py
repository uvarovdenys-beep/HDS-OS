#!/usr/bin/env python3
"""Tests for idea_tree — idea -> structure -> task.

Run, stop and correct must work at EVERY level. The operator edits this file by
hand, so the tests that matter most are the ones proving a bad edit is refused
at load rather than half-executed.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)

from idea_tree import (  # noqa: E402
    Node, TreeError, child_id, find, from_dict, load, runnable_leaves, save,
    set_status, stop_subtree, walk,
)

FILE = "storage/x.py"


def task(node_id, status="ready", name="f"):
    return Node(id=node_id, level="task", title=name, status=status,
                file=FILE, signature=f"def {name}() -> None",
                contract="does one thing")


def tree(structure_status="ready", task_status="ready"):
    return Node(id="I1", level="idea", title="an idea", status="ready", children=[
        Node(id="I1.S1", level="structure", title="a module", status=structure_status,
             file=FILE, children=[task("I1.S1.T1", task_status, "one"),
                                  task("I1.S1.T2", task_status, "two")]),
    ])


@pytest.fixture
def tree_path():
    """A path inside whatever root scribe is currently confined to.

    Resolved at call time on purpose: other tests in this suite repoint
    scribe.ROOT at a temp dir, and a hardcoded path would escape it (R-PATH).
    """
    import scribe as _scribe

    p = Path(_scribe.ROOT) / "storage" / "test_trees" / "idea.json"
    yield p
    if p.exists():
        p.unlink()


# ── shape ────────────────────────────────────────────────────────────────

def test_round_trip_preserves_tree(tree_path):
    save(tree(), tree_path)
    back = load(tree_path)
    assert [n.id for n in walk(back)] == ["I1", "I1.S1", "I1.S1.T1", "I1.S1.T2"]
    assert find(back, "I1.S1.T2").signature == "def two() -> None"


def test_saved_file_is_human_readable_json(tree_path):
    save(tree(), tree_path)
    raw = json.loads(tree_path.read_text(encoding="utf-8"))
    assert raw["id"] == "I1"
    assert raw["children"][0]["level"] == "structure"
    assert raw["children"][0]["children"][0]["level"] == "task"


def test_level_nesting_is_enforced():
    # A structure inside a structure would break "idea -> structure -> task".
    with pytest.raises(TreeError, match="may only contain"):
        from_dict({"id": "I1", "level": "idea", "title": "x", "children": [
            {"id": "I1.S1", "level": "structure", "title": "s", "children": [
                {"id": "bad", "level": "structure", "title": "nested"}]}]})


def test_task_under_idea_is_refused():
    # The structure level may not be skipped — that is the point of adding it.
    with pytest.raises(TreeError, match="may only contain"):
        from_dict({"id": "I1", "level": "idea", "title": "x", "children": [
            {"id": "I1.T1", "level": "task", "title": "t"}]})


def test_task_cannot_have_children():
    with pytest.raises(TreeError, match="no children"):
        from_dict({"id": "t", "level": "task", "title": "x",
                   "children": [{"id": "c", "level": "task", "title": "y"}]})


def test_child_id_is_positional():
    idea = Node(id="I1", level="idea", title="x")
    structure = Node(id="I1.S2", level="structure", title="y")
    assert child_id(idea, 2) == "I1.S2"
    assert child_id(structure, 3) == "I1.S2.T3"


# ── a hand-edit must fail loudly, not halfway ────────────────────────────

def test_broken_json_is_refused(tree_path):
    tree_path.parent.mkdir(parents=True, exist_ok=True)
    tree_path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(TreeError, match="invalid JSON"):
        load(tree_path)


def test_ready_task_without_signature_is_refused():
    with pytest.raises(TreeError, match="invent"):
        from_dict({"id": "t", "level": "task", "title": "x",
                   "status": "ready", "file": FILE})


def test_ready_structure_without_file_is_refused():
    # The architecture was decided but not where it lives.
    with pytest.raises(TreeError, match="names no file"):
        from_dict({"id": "I1", "level": "idea", "title": "x", "children": [
            {"id": "I1.S1", "level": "structure", "title": "s", "status": "ready",
             "children": [{"id": "I1.S1.T1", "level": "task", "title": "t"}]}]})


def test_ready_parent_without_children_is_refused():
    with pytest.raises(TreeError, match="decompose it first"):
        from_dict({"id": "I1", "level": "idea", "title": "x", "status": "ready"})


def test_unknown_status_is_refused():
    with pytest.raises(TreeError, match="unknown status"):
        from_dict({"id": "t", "level": "task", "title": "x", "status": "wat"})


# ── run / stop / correct, at every level ─────────────────────────────────

def test_illegal_transition_is_refused():
    t = tree()
    with pytest.raises(TreeError, match="cannot go"):
        set_status(t, "I1.S1.T1", "done")      # ready -> done skips running


def test_legal_run_then_finish():
    t = tree()
    set_status(t, "I1.S1.T1", "running")
    set_status(t, "I1.S1.T1", "done")
    assert find(t, "I1.S1.T1").status == "done"


def test_stopping_a_structure_holds_its_whole_subtree():
    t = tree()
    assert stop_subtree(t, "I1.S1") == 3       # the structure and its two tasks
    assert [n.status for n in walk(find(t, "I1.S1"))] == ["stopped"] * 3


def test_stop_never_destroys_finished_work():
    t = tree()
    set_status(t, "I1.S1.T1", "running")
    set_status(t, "I1.S1.T1", "done")
    stop_subtree(t, "I1")
    assert find(t, "I1.S1.T1").status == "done"


def test_stopped_structure_blocks_its_tasks():
    t = tree()
    assert len(runnable_leaves(t)) == 2
    stop_subtree(t, "I1.S1")
    assert runnable_leaves(t) == []


def test_stopping_the_idea_stops_everything():
    t = tree()
    stop_subtree(t, "I1")
    assert runnable_leaves(t) == []


def test_stopped_work_resumes():
    t = tree()
    stop_subtree(t, "I1.S1")
    set_status(t, "I1.S1", "ready")
    for tid in ("I1.S1.T1", "I1.S1.T2"):
        set_status(t, tid, "ready")
    assert len(runnable_leaves(t)) == 2


def test_correcting_a_done_node_reopens_it():
    t = tree()
    set_status(t, "I1.S1.T1", "running")
    set_status(t, "I1.S1.T1", "done")
    set_status(t, "I1.S1.T1", "draft")
    assert find(t, "I1.S1.T1").status == "draft"


def test_draft_tasks_are_not_run():
    # AI output lands in draft, so nothing runs before it is accepted.
    t = tree(task_status="draft")
    assert runnable_leaves(t) == []
