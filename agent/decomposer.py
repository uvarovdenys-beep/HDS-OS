#!/usr/bin/env python3
"""decomposer.py — the AI deepens one level of the tree.

    decompose_idea      : idea       -> structure nodes (files/modules)
    decompose_structure : structure  -> task nodes (one function each)

Two rules hold this together, and both exist because of measured failures.

1. The planner returns JSON ONLY — never code. Planning and implementing are
   separate jobs: a model that writes code while planning starts inventing the
   API it is supposed to be fixing.

2. Every new node lands as `draft`. The AI proposes, the operator accepts.
   Nothing the model invented can run before a human has looked at it — which
   is the whole reason the levels are correctable.

The prompts are deliberately short. A long brief dilutes: local models drop
details from prose far faster than they drop a schema.
"""
import json
import re
from typing import Callable, Dict, List

from idea_tree import CHILD_LEVEL, Node, TreeError, child_id, validate_node

MAX_STRUCTURES = 8
MAX_TASKS = 12

_IDEA_PROMPT = """Break this idea into the FILES that implement it.

Return ONLY a JSON array, no explanation:
[{{"title": "what this file is responsible for", "file": "dir/name.ext"}}]

Maximum {max_n} files. Order them so a file comes after the files it uses.

Idea: {title}
{note}"""

_STRUCTURE_PROMPT = """List the FUNCTIONS this one file needs.

Return ONLY a JSON array, no explanation:
[{{"title": "short name", "signature": "<one line, exact, in the file\'s language>", \
"contract": "one line: what it must do", "depends": ["functions THIS one calls"]}}]

"depends" means the functions this function CALLS — not the ones that call it. \
A function that calls nothing else has "depends": []. Build order follows it, so \
the direction matters.

Maximum {max_n} functions. The signature must be complete and valid for {lang} \
— it is fixed from here on and the implementer may not change it.

File: {file}
It is responsible for: {title}
{note}"""


def _language_of(path: str) -> str:
    """Name the language so the planner writes a signature in the right syntax."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {"py": "Python", "ts": "TypeScript", "js": "JavaScript",
            "tsx": "TypeScript", "jsx": "JavaScript", "go": "Go",
            "rs": "Rust", "java": "Java", "cs": "C#", "cpp": "C++",
            "c": "C", "php": "PHP", "rb": "Ruby"}.get(ext, ext or "this language")


def extract_json_array(raw: str) -> List[Dict]:
    """Pull the JSON array out of a model's answer.

    Models fence their output, prefix it with a sentence, or think out loud
    first. Rather than trusting them to stop doing that, take the first array
    that parses and reject everything else — fail closed, never half-read.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```")
                         else lines[1:])
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise TreeError("planner returned no JSON array")
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError as e:
            raise TreeError(f"planner returned malformed JSON — {e}")
    if not isinstance(parsed, list):
        raise TreeError("planner must return a JSON array")
    return parsed


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise TreeError(msg)


def _proposed(parent: Node, items: List[Dict], limit: int) -> None:
    _require(bool(items), f"'{parent.id}': planner proposed nothing")
    _require(len(items) <= limit,
             f"'{parent.id}': planner proposed {len(items)} children, limit is "
             f"{limit} — the level above is too coarse, split it first")


def decompose_idea(node: Node, ai_call: Callable[[str], str]) -> List[Node]:
    """idea -> structure nodes. Returns drafts; does NOT attach them."""
    _require(node.level == "idea", f"'{node.id}' is a {node.level}, not an idea")
    prompt = _IDEA_PROMPT.format(max_n=MAX_STRUCTURES, title=node.title,
                                 note=node.note)
    items = extract_json_array(ai_call(prompt))
    _proposed(node, items, MAX_STRUCTURES)

    children: List[Node] = []
    for i, item in enumerate(items, 1):
        _require(isinstance(item, dict), f"'{node.id}': child {i} is not an object")
        title = str(item.get("title", "")).strip()
        path = str(item.get("file", "")).strip()
        _require(bool(title), f"'{node.id}': child {i} has no title")
        _require(bool(path),
                 f"'{node.id}': child {i} ('{title}') names no file — its tasks "
                 f"would each choose their own")
        children.append(validate_node(Node(
            id=child_id(node, i), level=CHILD_LEVEL["idea"],
            title=title, file=path, status="draft")))
    return children


def decompose_structure(node: Node, ai_call: Callable[[str], str]) -> List[Node]:
    """structure -> task nodes, each one function with a fixed signature."""
    _require(node.level == "structure",
             f"'{node.id}' is a {node.level}, not a structure")
    _require(bool(node.file),
             f"'{node.id}' names no file — decide where it lives before "
             f"planning its functions")

    prompt = _STRUCTURE_PROMPT.format(max_n=MAX_TASKS, file=node.file,
                                      title=node.title, note=node.note,
                                      lang=_language_of(node.file))
    items = extract_json_array(ai_call(prompt))
    _proposed(node, items, MAX_TASKS)

    children: List[Node] = []
    names = set()
    for i, item in enumerate(items, 1):
        _require(isinstance(item, dict), f"'{node.id}': child {i} is not an object")
        title = str(item.get("title", "")).strip()
        signature = " ".join(str(item.get("signature", "")).split())
        contract = str(item.get("contract", "")).strip()
        _require(bool(title), f"'{node.id}': child {i} has no title")
        _require(bool(signature), f"'{node.id}': '{title}' has no signature")
        _require(bool(contract), f"'{node.id}': '{title}' has no contract")
        _require(title not in names,
                 f"'{node.id}': duplicate function '{title}' — a patch target "
                 f"must be unique")
        names.add(title)

        depends = item.get("depends") or []
        _require(isinstance(depends, list),
                 f"'{node.id}': '{title}' depends must be a list")
        children.append(Node(
            id=child_id(node, i), level=CHILD_LEVEL["structure"], title=title,
            file=node.file, signature=signature, contract=contract,
            depends=[str(d).strip() for d in depends], status="draft"))

    for child in children:
        for dep in child.depends:
            _require(dep in names,
                     f"'{node.id}': '{child.title}' depends on unknown '{dep}' "
                     f"— the implementer would invent that API")
    return children


def decompose(node: Node, ai_call: Callable[[str], str]) -> List[Node]:
    """Deepen whichever level this node is. A task is already the leaf."""
    if node.level == "idea":
        return decompose_idea(node, ai_call)
    if node.level == "structure":
        return decompose_structure(node, ai_call)
    raise TreeError(f"'{node.id}' is a task — it is implemented, not decomposed")


def attach(parent: Node, children: List[Node], replace: bool = False) -> Node:
    """Hang proposed children on their parent.

    Refuses to silently discard existing work: re-decomposing a node that
    already has children is only allowed with `replace`, so a second planning
    pass cannot quietly delete results the operator kept.
    """
    if parent.children and not replace:
        raise TreeError(
            f"'{parent.id}' already has {len(parent.children)} children — pass "
            f"replace=True to plan it again, which discards them")
    parent.children = children
    return parent
