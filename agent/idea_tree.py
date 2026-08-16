#!/usr/bin/env python3
"""idea_tree.py — the three-level work tree of HDS OS.

    idea  ->  structure  ->  tasks (one function each)

A STRUCTURE node is a file or module: the shape of the thing being built. Its
children are the tasks that fill it. That middle level is not decoration — it is
where the architecture is decided, and it matches what HDS already means by
"structure" in create_project ({file, instruction}).

The AI deepens one level at a time; the operator may correct ANY level at any
time; every level can be started, stopped and corrected independently.

Three properties make that possible, and each is enforced here:

1. The tree is a plain JSON file. Correcting the plan means editing text, not
   calling an API — so the operator is never locked out by a running agent.
2. Every node carries its own status, so work stops at the node the operator
   stopped and nowhere else.
3. The file is re-validated on every load. A hand-edit that breaks the plan is
   refused loudly instead of being half-executed.

Ids are positional and stable — I1, I1.S2, I1.S2.T3 — so a human editing the
file can see the shape and reference a node without inventing a key.

Task leaves carry the same fields as task_tree.FunctionSpec: the signature is
fixed at plan time so the implementer cannot invent an API.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

LEVELS = ("idea", "structure", "task")
CHILD_LEVEL = {"idea": "structure", "structure": "task", "task": None}

# draft    — proposed, not accepted yet (AI output lands here, never running)
# ready    — accepted, may be run
# running  — claimed by the agent
# stopped  — halted by the operator; resumable
# done     — finished
# failed   — attempted and rejected
STATUSES = ("draft", "ready", "running", "stopped", "done", "failed")

# Only these moves are legal. Anything else is a bug or a bad hand-edit, and is
# refused rather than silently accepted.
TRANSITIONS = {
    "draft": {"ready", "draft"},
    "ready": {"running", "draft", "stopped"},
    "running": {"done", "failed", "stopped"},
    "stopped": {"ready", "draft"},
    "done": {"draft"},        # correcting a finished node reopens it
    "failed": {"draft", "ready"},
}


class TreeError(Exception):
    """A tree that cannot be trusted. Fail closed — never run a broken plan."""


@dataclass
class Node:
    """One unit of work at any level.

    `file` is meaningful from the structure level down: a structure IS a file,
    and its tasks are written into that same file. The signature/contract pair
    is the leaf grate and is empty above the task level.

    The last three fields link a task to the QUEUE. Without them the plan and
    the queue are two state machines that cannot see each other: nothing marks a
    node as running when it is dispatched, nothing writes the verdict back, and
    stopping a node leaves its queued task running. That is the same drift
    task_bridge was written to end.
    """

    id: str
    level: str
    title: str
    status: str = "draft"
    children: List["Node"] = field(default_factory=list)

    # Structure and task: which file this belongs to.
    file: str = ""
    # Task only — the grate handed to the implementing model.
    signature: str = ""
    contract: str = ""
    depends: List[str] = field(default_factory=list)

    # Structure only — the file's shared state, materialised BEFORE its tasks
    # run. Without it each function invents its own name for the same variable
    # and the module will not import; measured on a session module whose three
    # functions all wrote `global _session` that nothing had declared.
    context: Dict = field(default_factory=dict)

    # Task only — the link to the queue.
    task_id: str = ""      # queue receipt, so a verdict can be routed back
    attempts: int = 0      # dispatches so far; a loop is invisible without it
    error: str = ""        # last failure, readable without opening the logs

    # Free text the operator writes to steer the next decomposition.
    note: str = ""

    def is_leaf(self) -> bool:
        return self.level == "task"

    def is_structure(self) -> bool:
        return self.level == "structure"

    def to_dict(self) -> Dict:
        d = {"id": self.id, "level": self.level, "title": self.title,
             "status": self.status}
        if self.file:
            d["file"] = self.file
        if self.is_structure() and self.context:
            d["context"] = self.context
        if self.is_leaf():
            d.update({"signature": self.signature, "contract": self.contract,
                      "depends": list(self.depends)})
            if self.task_id:
                d["task_id"] = self.task_id
            if self.attempts:
                d["attempts"] = self.attempts
            if self.error:
                d["error"] = self.error
        if self.note:
            d["note"] = self.note
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise TreeError(msg)


def from_dict(raw: object, parent_level: str = "") -> Node:
    """Rebuild a node from JSON, refusing anything malformed."""
    _require(isinstance(raw, dict), "node must be a JSON object")
    for key in ("id", "level", "title"):
        _require(bool(str(raw.get(key, "")).strip()), f"node missing '{key}'")

    level = str(raw["level"]).strip()
    _require(level in LEVELS, f"'{raw['id']}': unknown level '{level}'")
    if parent_level:
        _require(level == CHILD_LEVEL[parent_level],
                 f"'{raw['id']}': a {parent_level} may only contain "
                 f"{CHILD_LEVEL[parent_level]} nodes, found '{level}'")

    status = str(raw.get("status", "draft")).strip()
    _require(status in STATUSES, f"'{raw['id']}': unknown status '{status}'")

    context = raw.get("context") or {}
    _require(isinstance(context, dict), f"'{raw['id']}': context must be an object")

    node = Node(id=str(raw["id"]).strip(), level=level,
                title=str(raw["title"]).strip(), status=status,
                file=str(raw.get("file", "")).strip(),
                signature=str(raw.get("signature", "")).strip(),
                contract=str(raw.get("contract", "")).strip(),
                depends=[str(d).strip() for d in (raw.get("depends") or [])],
                context=context,
                task_id=str(raw.get("task_id", "")).strip(),
                attempts=int(raw.get("attempts", 0) or 0),
                error=str(raw.get("error", "")).strip(),
                note=str(raw.get("note", "")).strip())

    kids = raw.get("children") or []
    _require(isinstance(kids, list), f"'{node.id}': children must be a list")
    _require(not (node.is_leaf() and kids), f"'{node.id}': a task has no children")
    node.children = [from_dict(k, level) for k in kids]
    return validate_node(node)


def validate_node(node: Node) -> Node:
    """A node that is ready to run must be fully specified — no guessing.

    A structure without a file is the failure worth naming: the planner decided
    the architecture but not where it lives, and every task under it would then
    pick its own file.
    """
    if node.is_leaf() and node.status in ("ready", "running"):
        required = {"file": node.file, "signature": node.signature,
                    "contract": node.contract}
        missing = [name for name, value in required.items() if not value]
        _require(not missing,
                 f"'{node.id}' is {node.status} but missing: {', '.join(missing)} "
                 f"— an implementer would have to invent them")
        _require("\n" not in node.signature,
                 f"'{node.id}': signature must be one line")
    if node.is_structure() and node.status in ("ready", "running"):
        _require(bool(node.file),
                 f"'{node.id}' is {node.status} but names no file — its tasks "
                 f"would each choose their own")
    if not node.is_leaf() and node.status == "ready":
        _require(bool(node.children),
                 f"'{node.id}' is ready but has no children — decompose it first")
    return node


def walk(node: Node) -> Iterator[Node]:
    """Depth-first, parents before children."""
    yield node
    for child in node.children:
        yield from walk(child)


def find(root: Node, node_id: str) -> Optional[Node]:
    for n in walk(root):
        if n.id == node_id:
            return n
    return None


def child_id(parent: Node, index: int) -> str:
    """Positional id: I1 -> I1.S2 -> I1.S2.T3. Readable in a hand-edited file."""
    letter = {"idea": "S", "structure": "T"}[parent.level]
    return f"{parent.id}.{letter}{index}"


def set_status(root: Node, node_id: str, status: str) -> Node:
    """Move one node, refusing illegal transitions."""
    _require(status in STATUSES, f"unknown status '{status}'")
    node = find(root, node_id)
    _require(node is not None, f"no node '{node_id}'")
    _require(status in TRANSITIONS[node.status],
             f"'{node_id}': cannot go {node.status} -> {status}")
    node.status = status
    return validate_node(node)


def stop_subtree(root: Node, node_id: str) -> int:
    """Stop a node and everything under it. Stopping is always allowed.

    Only work that is ready or running is stopped — finished work stays
    finished, so a stop never destroys a result.
    """
    node = find(root, node_id)
    _require(node is not None, f"no node '{node_id}'")
    stopped = 0
    for n in walk(node):
        if n.status in ("ready", "running"):
            n.status = "stopped"
            stopped += 1
    return stopped


def runnable_leaves(root: Node) -> List[Node]:
    """Leaves the agent may claim: ready, and under no stopped ancestor.

    A stopped parent holds its whole subtree, which is what "stop this task"
    has to mean.
    """
    out: List[Node] = []

    def descend(node: Node, blocked: bool) -> None:
        held = blocked or node.status == "stopped"
        if node.is_leaf():
            if node.status == "ready" and not held:
                out.append(node)
            return
        for child in node.children:
            descend(child, held)

    descend(root, False)
    return out


def load(path) -> Node:
    """Read the tree, validating it — a bad hand-edit fails here, not mid-run."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise TreeError(f"{Path(path).name}: invalid JSON — {e}")
    return from_dict(raw)


def save(root: Node, path) -> None:
    """Write the tree back through the cage, formatted for a human to edit.

    Through scribe, not open(): R-19 admits no exceptions, and the plan is the
    thing that decides what gets built — the last file that should be writable
    behind the cage's back.
    """
    import scribe

    body = json.dumps(root.to_dict(), indent=2, ensure_ascii=False) + "\n"
    scribe.execute({"op": "write", "path": str(path), "content": body},
                   protocol_size=None)
