#!/usr/bin/env python3
"""pipeline.py — the runner that joins the PLAN to the QUEUE.

Before this module they were two state machines that could not see each other.
The tree knew a task was `ready`; the queue knew a task was running; nothing
marked a node dispatched, nothing wrote a verdict back, and stopping a node in
the tree left its queued task to finish anyway. That is precisely the drift
`task_bridge` was written to end — the webhook wrote to results/ while the agent
read active/, so external tasks never ran.

The rule here is one sentence: **the tree is the source of truth; the queue is
transport.** Only this module moves a node between ready → running → done/failed,
and it does so from the queue's own verdict, never from a guess.

    cycle(project)      one turn: reconcile finished work, then dispatch more
    status(project)     what is queued, running, done, failed — and why
    stop(project, id)   halt a node and everything under it
    resume(project, id) put it back in play

HONEST LIMIT ON STOP. HDS has a single sealed exec surface, so this module
cannot kill a process. `stop` removes queue entries the agent has NOT yet picked
up and refuses to dispatch anything more; a task already in flight runs to
completion and its verdict is still recorded. Stopping is prompt, not instant,
and pretending otherwise would be worse than saying so.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TREES = ROOT / "ai-mind" / "tasks" / "trees"
ACTIVE = ROOT / "ai-mind" / "tasks" / "active"
DEFAULT_PROJECT = "default"

# How many tasks may be in flight at once. One, deliberately: the agent loads a
# single model at a time (SINGLE_MODEL), so a second concurrent task would only
# queue behind the first while making the pipeline harder to reason about.
MAX_IN_FLIGHT = 1


class PipelineError(Exception):
    """The runner refuses to act on something it cannot trust."""


# ── where plans live ──────────────────────────────────────────────────────

def _project_dir(project: str) -> Path:
    """Trees for one project. The flat legacy layout is the 'default' project."""
    return TREES if project == DEFAULT_PROJECT else TREES / project


def projects() -> list:
    """Every project that has at least one plan."""
    out = []
    if any(TREES.glob("*.json")):
        out.append(DEFAULT_PROJECT)
    if TREES.exists():
        out += sorted(p.name for p in TREES.iterdir()
                      if p.is_dir() and any(p.glob("*.json")))
    return out


def ideas(project: str = DEFAULT_PROJECT) -> list:
    d = _project_dir(project)
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def _load(project: str, idea: str):
    import idea_tree
    path = _project_dir(project) / f"{idea}.json"
    if not path.exists():
        raise PipelineError(f"no plan '{idea}' in project '{project}'")
    return idea_tree.load(path), path


def _save(root, path) -> None:
    import idea_tree
    idea_tree.save(root, path)


# ── reading the pipeline ──────────────────────────────────────────────────

def status(project: str = DEFAULT_PROJECT) -> dict:
    """What the pipeline is doing, per idea and in total."""
    import idea_tree
    per_idea, totals = [], {s: 0 for s in idea_tree.STATUSES}
    for name in ideas(project):
        root, _ = _load(project, name)
        counts = {s: 0 for s in idea_tree.STATUSES}
        running, failed = [], []
        for n in idea_tree.walk(root):
            if not n.is_leaf():
                continue
            counts[n.status] += 1
            totals[n.status] += 1
            if n.status == "running":
                running.append({"id": n.id, "task_id": n.task_id,
                                "attempts": n.attempts})
            if n.status == "failed":
                failed.append({"id": n.id, "error": n.error[:120]})
        per_idea.append({"idea": name, "title": root.title, "counts": counts,
                         "running": running, "failed": failed})
    return {"project": project, "ideas": per_idea, "totals": totals,
            "in_flight": totals["running"]}


# ── moving work ───────────────────────────────────────────────────────────

def dispatch(project: str = DEFAULT_PROJECT, limit: int = MAX_IN_FLIGHT) -> list:
    """Claim ready tasks and hand them to the queue.

    Claiming is what makes the pipeline observable: the node moves to `running`
    and records its task_id BEFORE the submit, so a crash between the two leaves
    a node that reconcile can see and recover, rather than a task nobody owns.

    The task itself is built by task_tree.to_subtask — NOT here. An earlier
    version assembled its own dict and quietly lost the one sentence that
    matters, "Implement EXACTLY ONE function": the model then wrote the whole
    module on every task and the file filled with duplicates. Two places
    building the same contract is the drift task_bridge exists to prevent.

    The structure's shared state is materialised FIRST. A session module whose
    three functions each wrote `global _session` failed to import, because the
    declaration belongs to no function and so no function emitted it. Writing
    the header before the tasks run means they patch into a file where the name
    already exists — they cannot invent a different one and still resolve.
    """
    import idea_tree
    import task_bridge
    from context import materialise
    from task_tree import FunctionSpec, to_subtask

    sent = []
    for name in ideas(project):
        root, path = _load(project, name)
        in_flight = sum(1 for n in idea_tree.walk(root)
                        if n.is_leaf() and n.status == "running")
        for node in idea_tree.runnable_leaves(root):
            if in_flight >= limit:
                break
            parent = next((s for s in idea_tree.walk(root)
                           if s.is_structure() and node in s.children), None)
            if parent is not None:
                materialise(parent)
            siblings = [FunctionSpec(name=s.title, file=s.file,
                                     signature=s.signature, contract=s.contract,
                                     depends=list(s.depends))
                        for s in idea_tree.walk(root)
                        if s.is_leaf() and s.file == node.file]
            me = next(s for s in siblings if s.name == node.title)
            task = to_subtask(me, siblings)
            node.status = "running"
            node.attempts += 1
            node.task_id = task_bridge.submit(task)["task_id"]
            node.error = ""
            _save(root, path)
            sent.append({"idea": name, "node": node.id, "task_id": node.task_id})
            in_flight += 1
    return sent


def reconcile(project: str = DEFAULT_PROJECT) -> list:
    """Write the queue's verdicts back into the plan.

    A node stays `running` until the queue says otherwise. An unknown task id
    (the queue was cleared under us) is reported as failed rather than left
    running forever — a stuck node is worse than an honest failure.
    """
    import idea_tree
    import task_bridge

    changed = []
    for name in ideas(project):
        root, path = _load(project, name)
        dirty = False
        for node in idea_tree.walk(root):
            if not (node.is_leaf() and node.status == "running" and node.task_id):
                continue
            verdict = task_bridge.status(node.task_id)
            if verdict is None:
                node.status, node.error = "failed", "task vanished from the queue"
            elif verdict.get("status") == "completed":
                node.status, node.error = "done", ""
            elif verdict.get("status") in ("failed", "error"):
                node.status = "failed"
                node.error = str(verdict.get("detail") or verdict.get("status"))[:200]
            else:
                continue                      # still queued or running
            dirty = True
            changed.append({"idea": name, "node": node.id, "status": node.status,
                            "error": node.error})
        if dirty:
            _save(root, path)
    return changed


def cycle(project: str = DEFAULT_PROJECT) -> dict:
    """One turn of the pipeline: settle what finished, then start what can start."""
    done = reconcile(project)
    started = dispatch(project)
    return {"reconciled": done, "dispatched": started}


# ── control ───────────────────────────────────────────────────────────────

def stop(project: str, node_id: str) -> dict:
    """Halt a node and everything under it.

    Also drops any queue entry that has not been picked up yet. A task already
    in flight cannot be killed — HDS has one sealed exec surface and this is not
    it — so it finishes and its verdict is still recorded.
    """
    import idea_tree

    for name in ideas(project):
        root, path = _load(project, name)
        target = idea_tree.find(root, node_id)
        if target is None:
            continue
        dropped, in_flight = 0, []
        for n in idea_tree.walk(target):
            if n.is_leaf() and n.status == "running" and n.task_id:
                queued = ACTIVE / f"{n.task_id}.json"
                if queued.exists():
                    queued.unlink()           # not started yet — drop it
                    dropped += 1
                else:
                    in_flight.append(n.id)    # already running — let it land
        halted = idea_tree.stop_subtree(root, node_id)
        _save(root, path)
        return {"ok": True, "idea": name, "halted": halted,
                "dropped_from_queue": dropped, "still_in_flight": in_flight,
                "note": "in-flight tasks finish; their verdicts are recorded"}
    raise PipelineError(f"no node '{node_id}' in project '{project}'")


def resume(project: str, node_id: str) -> dict:
    """Put a stopped subtree back in play. Finished work is left finished."""
    import idea_tree

    for name in ideas(project):
        root, path = _load(project, name)
        target = idea_tree.find(root, node_id)
        if target is None:
            continue
        moved = []
        for n in idea_tree.walk(target):
            if n.status == "stopped":
                n.status = "ready" if n.children or n.is_leaf() else "draft"
                moved.append(n.id)
        _save(root, path)
        return {"ok": True, "idea": name, "resumed": moved}
    raise PipelineError(f"no node '{node_id}' in project '{project}'")


def retry(project: str, node_id: str) -> dict:
    """Send a failed task back to the queue, keeping its attempt count."""
    import idea_tree

    for name in ideas(project):
        root, path = _load(project, name)
        node = idea_tree.find(root, node_id)
        if node is None:
            continue
        if node.status != "failed":
            raise PipelineError(f"'{node_id}' is {node.status}, not failed")
        node.status, node.task_id, node.error = "ready", "", ""
        _save(root, path)
        return {"ok": True, "idea": name, "node": node_id,
                "attempts_so_far": node.attempts}
    raise PipelineError(f"no node '{node_id}' in project '{project}'")


def run(project: str = DEFAULT_PROJECT, poll: float = 5.0,
        max_cycles: int = 0) -> dict:
    """Drive the pipeline until nothing is ready or running.

    Stops on its own when the work is done, so it is safe to call from a script
    as well as from a daemon. max_cycles=0 means no cap.
    """
    turns = 0
    while True:
        result = cycle(project)
        turns += 1
        state = status(project)
        if state["totals"]["ready"] == 0 and state["totals"]["running"] == 0:
            return {"finished": True, "cycles": turns, "status": state}
        if max_cycles and turns >= max_cycles:
            return {"finished": False, "cycles": turns, "status": state}
        if not result["dispatched"] and not result["reconciled"]:
            time.sleep(poll)
