#!/usr/bin/env python3
"""Tests for task_tree — the grates must REJECT, not merely exist.

Each rejection test names the failure it prevents: a plan that passes validation
is a plan an implementer cannot guess its way around.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)

from task_tree import (  # noqa: E402
    FunctionSpec, PlanError, api_surface, build_order, parse_plan,
    plan_to_subtasks, validate_plan,
)


def spec(name, depends=None, file="storage/x.py", contract="does a thing"):
    return FunctionSpec(name=name, file=file, signature=f"def {name}(a: int) -> int",
                        contract=contract, depends=depends or [])


# ── the plan must be structurally sound ──────────────────────────────────

def test_valid_plan_survives():
    specs = [spec("base"), spec("caller", depends=["base"])]
    assert [s.name for s in validate_plan(specs)] == ["base", "caller"]


def test_empty_plan_rejected():
    with pytest.raises(PlanError, match="empty"):
        validate_plan([])


def test_duplicate_name_rejected():
    # Two functions with one name make the scribe patch target ambiguous.
    with pytest.raises(PlanError, match="duplicate"):
        validate_plan([spec("same"), spec("same")])


def test_unknown_dependency_rejected():
    # The failure this prevents: the implementer invents the missing API.
    with pytest.raises(PlanError, match="unknown"):
        validate_plan([spec("solo", depends=["ghost"])])


def test_self_dependency_rejected():
    with pytest.raises(PlanError, match="itself"):
        validate_plan([spec("loop", depends=["loop"])])


def test_long_contract_rejected():
    # Prose is what local models drop; the contract must stay a wall.
    with pytest.raises(PlanError, match="contract"):
        validate_plan([spec("wordy", contract="x" * 500)])


def test_multiline_signature_rejected():
    s = spec("multi")
    s.signature = "def multi(\n    a: int,\n) -> int"
    with pytest.raises(PlanError, match="one line"):
        validate_plan([s])


def test_oversized_plan_rejected():
    with pytest.raises(PlanError, match="decompose"):
        validate_plan([spec(f"f{i}") for i in range(40)])


# ── ordering ─────────────────────────────────────────────────────────────

def test_dependencies_are_built_first():
    specs = [spec("top", depends=["mid"]), spec("mid", depends=["base"]), spec("base")]
    assert [s.name for s in build_order(specs)] == ["base", "mid", "top"]


def test_cycle_is_named_not_routed_around():
    specs = [spec("a", depends=["b"]), spec("b", depends=["a"])]
    with pytest.raises(PlanError, match="cycle"):
        build_order(specs)


# ── the grate handed to the implementer ──────────────────────────────────

def test_api_surface_shows_siblings_and_hides_self():
    specs = [spec("me"), spec("sibling")]
    surface = api_surface(specs, exclude="me")
    assert "sibling" in surface
    assert "def me(" not in surface


def test_subtask_carries_patch_target_and_grate():
    specs = [spec("base"), spec("caller", depends=["base"])]
    tasks = plan_to_subtasks(specs)
    assert [t["patch_target"] for t in tasks] == ["base", "caller"]

    caller = tasks[1]
    grate = caller["reference_files"][0]["content"]
    # The signature is fixed and the callable surface is closed.
    assert "def caller(a: int) -> int" in grate
    assert "def base(a: int) -> int" in grate
    assert "EXACTLY ONE function" in grate


def test_subtask_splits_file_into_dir_and_name():
    tasks = plan_to_subtasks([spec("f", file="storage/pkg/mod.py")])
    assert tasks[0]["output_dir"] == "storage/pkg"
    assert tasks[0]["output_filename"] == "mod.py"


# ── JSON entry point ─────────────────────────────────────────────────────

def test_parse_plan_accepts_well_formed_json():
    raw = [{"name": "f", "file": "storage/x.py",
            "signature": "def f() -> None", "contract": "does it"}]
    assert parse_plan(raw)[0].name == "f"


def test_parse_plan_rejects_missing_fields():
    with pytest.raises(PlanError, match="missing"):
        parse_plan([{"name": "f", "file": "storage/x.py"}])


def test_parse_plan_rejects_non_list():
    with pytest.raises(PlanError, match="array"):
        parse_plan({"name": "f"})


def test_write_op_inserts_when_target_is_not_in_the_file_yet():
    """The bug this pins: a three-function module lost two of its functions.

    write_op used to ask only whether the FILE existed. The first task creates
    it; the second was then told to PATCH a target that is not in it yet, the
    cage answered "R-PATCH: target not found", and the task failed. Every file
    with more than one function was broken.
    """
    from task_tree import write_op
    source = "def alpha():\n    return 1\n"

    # file absent -> write
    assert write_op("x.py", "code", "alpha", False, "")["op"] == "write"

    # target present -> patch exactly it
    op = write_op("x.py", "code", "alpha", True, source)
    assert op["op"] == "patch" and op["target"] == "alpha"

    # file there, target absent -> insert, and BELOW the existing code
    op = write_op("x.py", "def beta():\n    return 2\n", "beta", True, source)
    assert op["op"] == "insert", "a missing target must not be patched"
    assert op["after_line"] == len(source.splitlines())


def test_write_op_without_a_target_stays_whole_file():
    from task_tree import write_op
    assert write_op("x.py", "code", "", True, "def a(): pass")["op"] == "write"
