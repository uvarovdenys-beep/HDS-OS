#!/usr/bin/env python3
"""Tests for decomposer — the planner is injected, so no model is needed.

Most of these are rejection tests. A planner that returns something unusable
must be caught here, because everything below a bad plan inherits it.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)

from decomposer import (  # noqa: E402
    attach, decompose, decompose_idea, decompose_structure, extract_json_array,
)
from idea_tree import Node, TreeError  # noqa: E402


def says(payload):
    """A planner that answers with exactly this."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda _prompt: text


IDEA = Node(id="I1", level="idea", title="an idea")


def structure(file="src/mod.ts"):
    return Node(id="I1.S1", level="structure", title="the module", file=file)


# ── reading whatever the model actually said ─────────────────────────────

def test_plain_array_is_read():
    assert extract_json_array('[{"a": 1}]') == [{"a": 1}]


def test_fenced_array_is_read():
    assert extract_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_array_after_chatter_is_read():
    # Models narrate before answering; take the array, not the sentence.
    assert extract_json_array('Sure! Here you go:\n[{"a": 1}]') == [{"a": 1}]


def test_no_array_is_refused():
    with pytest.raises(TreeError, match="no JSON array"):
        extract_json_array("I cannot help with that.")


def test_malformed_array_is_refused():
    with pytest.raises(TreeError, match="malformed"):
        extract_json_array('[{"a": 1},]')


def test_object_instead_of_array_is_refused():
    with pytest.raises(TreeError, match="must return a JSON array"):
        extract_json_array('{"a": 1}')


# ── idea -> structure ────────────────────────────────────────────────────

def test_idea_becomes_files():
    kids = decompose_idea(IDEA, says([
        {"title": "the client", "file": "src/client.ts"},
        {"title": "the entry point", "file": "src/main.ts"},
    ]))
    assert [k.id for k in kids] == ["I1.S1", "I1.S2"]
    assert [k.level for k in kids] == ["structure", "structure"]
    assert kids[0].file == "src/client.ts"


def test_structure_without_a_file_is_refused():
    with pytest.raises(TreeError, match="names no file"):
        decompose_idea(IDEA, says([{"title": "somewhere"}]))


def test_too_many_files_is_refused():
    many = [{"title": f"f{i}", "file": f"src/f{i}.ts"} for i in range(20)]
    with pytest.raises(TreeError, match="too coarse"):
        decompose_idea(IDEA, says(many))


def test_empty_plan_is_refused():
    with pytest.raises(TreeError, match="proposed nothing"):
        decompose_idea(IDEA, says([]))


# ── structure -> tasks ───────────────────────────────────────────────────

def good_tasks():
    return [
        {"title": "parse", "signature": "function parse(s: string): string[]",
         "contract": "split the buffer into complete lines"},
        {"title": "send", "signature": "function send(m: string): void",
         "contract": "write one framed message", "depends": ["parse"]},
    ]


def test_structure_becomes_functions():
    kids = decompose_structure(structure(), says(good_tasks()))
    assert [k.id for k in kids] == ["I1.S1.T1", "I1.S1.T2"]
    assert [k.level for k in kids] == ["task", "task"]
    assert kids[1].depends == ["parse"]


def test_tasks_inherit_the_structure_file():
    kids = decompose_structure(structure("src/only.ts"), says(good_tasks()))
    assert {k.file for k in kids} == {"src/only.ts"}


def test_missing_signature_is_refused():
    with pytest.raises(TreeError, match="no signature"):
        decompose_structure(structure(), says(
            [{"title": "x", "contract": "does a thing"}]))


def test_missing_contract_is_refused():
    with pytest.raises(TreeError, match="no contract"):
        decompose_structure(structure(), says(
            [{"title": "x", "signature": "function x(): void"}]))


def test_duplicate_function_is_refused():
    dup = [{"title": "same", "signature": "function same(): void", "contract": "a"},
           {"title": "same", "signature": "function same(n: number): void",
            "contract": "b"}]
    with pytest.raises(TreeError, match="duplicate"):
        decompose_structure(structure(), says(dup))


def test_unknown_dependency_is_refused():
    # The failure this prevents: the implementer invents the missing API.
    bad = [{"title": "solo", "signature": "function solo(): void",
            "contract": "a", "depends": ["ghost"]}]
    with pytest.raises(TreeError, match="unknown 'ghost'"):
        decompose_structure(structure(), says(bad))


def test_multiline_signature_is_flattened():
    wrapped = [{"title": "wide",
                "signature": "function wide(\n  a: number,\n): void",
                "contract": "does it"}]
    kids = decompose_structure(structure(), says(wrapped))
    assert kids[0].signature == "function wide( a: number, ): void"


def test_structure_without_file_cannot_be_planned():
    with pytest.raises(TreeError, match="decide where it lives"):
        decompose_structure(structure(file=""), says(good_tasks()))


# ── nothing the model invents may run ────────────────────────────────────

def test_all_proposals_land_as_draft():
    kids = decompose_idea(IDEA, says([{"title": "a", "file": "src/a.ts"}]))
    kids += decompose_structure(structure(), says(good_tasks()))
    assert {k.status for k in kids} == {"draft"}


# ── routing and attachment ───────────────────────────────────────────────

def test_decompose_routes_by_level():
    assert decompose(IDEA, says([{"title": "a", "file": "src/a.ts"}]))[0].level \
        == "structure"
    assert decompose(structure(), says(good_tasks()))[0].level == "task"


def test_a_task_is_implemented_not_decomposed():
    leaf = Node(id="I1.S1.T1", level="task", title="x")
    with pytest.raises(TreeError, match="implemented, not decomposed"):
        decompose(leaf, says([]))


def test_attach_refuses_to_discard_existing_children():
    parent = structure()
    attach(parent, decompose_structure(parent, says(good_tasks())))
    with pytest.raises(TreeError, match="replace=True"):
        attach(parent, [], replace=False)


def test_replanning_is_allowed_when_explicit():
    parent = structure()
    attach(parent, decompose_structure(parent, says(good_tasks())))
    attach(parent, decompose_structure(parent, says(good_tasks()[:1])),
           replace=True)
    assert len(parent.children) == 1
