#!/usr/bin/env python3
"""tree_tools.py — the three-level work tree, exposed over MCP.

    idea  ->  structure (a file/module)  ->  tasks (one function each)

DIVISION OF LABOUR. The editor's model PLANS; HDS VALIDATES and REMEMBERS.
Nothing here calls a model: the client proposes children, this stores them only
if they survive the same grate the local agent faces (`idea_tree.validate_node`,
`decomposer`'s uniqueness and dependency rules). A client cannot park an
underspecified plan in the tree any more than it can write past the cage.

WHY THE PLAN LIVES HERE AND NOT IN THE CHAT. An editor that keeps the whole
design in its context window pays for it on every turn, and the window is what
degrades first on a large system. Held here, the plan is fetched one node at a
time: `tree_next` hands back a single function with its signature, its contract
and its siblings' signatures — a small brick, not the whole building.

Every proposal lands as `draft`. The model proposes, the operator accepts. The
tree file is plain JSON and is meant to be hand-edited between passes.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# idea_tree and decomposer live in agent/. Put it on the path here rather than
# relying on whoever imported this module having done it — a module that only
# works when someone else set sys.path is a module that breaks when reused.
for _p in (str(ROOT), str(ROOT / "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TREES = ROOT / "ai-mind" / "tasks" / "trees"
_IDEA = {"type": "string", "description": "Idea id, e.g. 'I1' (its file is I1.json)."}
_NODE = {"type": "string", "description": "Node id, e.g. 'I1.S2' or 'I1.S2.T3'."}

TOOLS = [
    {
        "name": "tree_create",
        "description": (
            "Start a plan: idea -> structure (files) -> tasks (functions). "
            "Returns its id. Put constraints and existing APIs in 'note' — it is "
            "what the lower levels inherit."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "What is to be built."},
                "note": {"type": "string", "description": "Constraints, APIs to reuse."},
            },
            "required": ["title"],
        },
    },
    {
        "name": "tree_show",
        "description": (
            "Read a plan or one subtree: id, level, title, status. Use this "
            "instead of keeping the plan in the conversation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"idea": _IDEA, "node": _NODE},
            "required": ["idea"],
        },
    },
    {
        "name": "tree_propose",
        "description": (
            "Attach children to a node; they are stored as draft.\n"
            'Under an idea: {"title", "file"} — one per file.\n'
            'Under a structure: {"title", "signature", "contract", "depends"} — '
            "one per function; 'depends' lists functions THIS one calls.\n"
            "Refused if a file, signature or contract is missing, a name repeats, "
            "or a dependency is not in the same proposal."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "idea": _IDEA,
                "node": _NODE,
                "children": {"type": "array", "items": {"type": "object"}},
                "replace": {"type": "boolean", "description": "Re-plan, discarding children."},
            },
            "required": ["idea", "node", "children"],
        },
    },
    {
        "name": "tree_accept",
        "description": "Accept a draft so it may run. Each level is accepted on its own.",
        "inputSchema": {
            "type": "object",
            "properties": {"idea": _IDEA, "node": _NODE,
                           "recursive": {"type": "boolean",
                                         "description": "Also accept drafts below."}},
            "required": ["idea", "node"],
        },
    },
    {
        "name": "tree_next",
        "description": (
            "The next task ready to implement: its signature, contract, file, and "
            "the signatures it may call. Null when nothing is ready."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"idea": _IDEA},
            "required": ["idea"],
        },
    },
    {
        "name": "tree_stop",
        "description": ("Stop a node and everything under it. Finished work stays "
                        "finished. Resume by accepting it again."),
        "inputSchema": {
            "type": "object",
            "properties": {"idea": _IDEA, "node": _NODE},
            "required": ["idea", "node"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}


def _path(idea: str) -> Path:
    safe = str(idea).strip().replace("/", "_").replace("..", "_")
    if not safe:
        raise ValueError("idea id is required")
    return TREES / f"{safe}.json"


def _load(idea: str):
    import idea_tree
    p = _path(idea)
    if not p.exists():
        raise ValueError(f"no plan '{idea}' — create it with tree_create")
    return idea_tree.load(p)


def _save(root, idea: str) -> None:
    import idea_tree
    idea_tree.save(root, _path(idea))


def _brief(node) -> dict:
    """One node, without the fields the caller did not ask about."""
    out = {"id": node.id, "level": node.level, "title": node.title,
           "status": node.status}
    if node.file:
        out["file"] = node.file
    if node.children:
        out["children"] = [_brief(c) for c in node.children]
    return out


def call(name: str, args: dict) -> dict:
    """Run one tree op. A rejection is a result, not an exception: the model
    should read why the grate refused and re-propose."""
    try:
        return _result(_dispatch(name, args))
    except Exception as e:
        return _result({"ok": False, "refused_by": "plan grate", "reason": str(e),
                        "hint": "Re-propose with the missing detail filled in. "
                                "The stored plan is unchanged."}, is_error=True)


def _dispatch(name: str, args: dict) -> dict:
    import idea_tree
    from decomposer import attach

    if name == "tree_create":
        idea = args.get("id") or _next_id()
        root = idea_tree.Node(id=idea, level="idea", status="draft",
                              title=str(args["title"]).strip(),
                              note=str(args.get("note", "")).strip())
        _save(root, idea)
        return {"ok": True, "idea": idea, "file": str(_path(idea).relative_to(ROOT)),
                "next": "propose one structure per file with tree_propose"}

    idea = str(args["idea"]).strip()

    if name == "tree_show":
        root = _load(idea)
        node = idea_tree.find(root, args["node"]) if args.get("node") else root
        if node is None:
            raise ValueError(f"no node '{args.get('node')}' in '{idea}'")
        return {"ok": True, "tree": _brief(node)}

    if name == "tree_propose":
        root = _load(idea)
        parent = idea_tree.find(root, args["node"])
        if parent is None:
            raise ValueError(f"no node '{args['node']}' in '{idea}'")
        children = _build_children(parent, args.get("children") or [])
        attach(parent, children, replace=bool(args.get("replace")))
        _save(root, idea)
        return {"ok": True, "added": [c.id for c in children],
                "status": "draft",
                "next": f"review them, then tree_accept '{parent.id}'"}

    if name == "tree_accept":
        root = _load(idea)
        node = idea_tree.find(root, args["node"])
        if node is None:
            raise ValueError(f"no node '{args['node']}' in '{idea}'")
        targets = list(idea_tree.walk(node)) if args.get("recursive") else [node]
        moved = []
        for n in targets:
            if n.status == "draft":
                idea_tree.set_status(root, n.id, "ready")
                moved.append(n.id)
        _save(root, idea)
        return {"ok": True, "accepted": moved}

    if name == "tree_stop":
        root = _load(idea)
        stopped = idea_tree.stop_subtree(root, args["node"])
        _save(root, idea)
        return {"ok": True, "stopped": stopped}

    if name == "tree_next":
        root = _load(idea)
        ready = idea_tree.runnable_leaves(root)
        if not ready:
            return {"ok": True, "task": None,
                    "note": "nothing ready — accept a draft, or a stopped parent "
                            "is holding the work"}
        return {"ok": True, "task": _grate(root, ready[0])}

    raise ValueError(f"unknown tree tool: {name}")


def _build_children(parent, items: list) -> list:
    """Turn proposals into validated nodes — the grate, on HDS's side."""
    import idea_tree
    from decomposer import decompose_idea, decompose_structure

    payload = json.dumps(items)
    fake = lambda _prompt: payload          # noqa: E731 — reuse the same validators
    if parent.level == "idea":
        return decompose_idea(parent, fake)
    if parent.level == "structure":
        return decompose_structure(parent, fake)
    raise ValueError(f"'{parent.id}' is a task — implement it, do not decompose it")


def _grate(root, task) -> dict:
    """Exactly what an implementer needs: the wall, not the whole plan."""
    import idea_tree
    siblings = [n for n in idea_tree.walk(root)
                if n.level == "task" and n.file == task.file and n.id != task.id]
    return {
        "id": task.id, "file": task.file, "signature": task.signature,
        "contract": task.contract,
        "may_call": [{"signature": s.signature, "does": s.contract}
                     for s in siblings if s.title in task.depends],
        "siblings_in_file": [s.signature for s in siblings],
        "write_with": "cage_patch (target = the function name) so the rest of "
                      "the file is untouched; cage_write only if the file is new",
    }


def _next_id() -> str:
    TREES.mkdir(parents=True, exist_ok=True)
    used = {p.stem for p in TREES.glob("I*.json")}
    i = 1
    while f"I{i}" in used:
        i += 1
    return f"I{i}"


def _result(payload: dict, is_error: bool = False) -> dict:
    out = {"content": [{"type": "text",
                        "text": json.dumps(payload, indent=2, ensure_ascii=False)}]}
    if is_error:
        out["isError"] = True
    return out
