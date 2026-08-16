"""The mirror graph: plan vs code, and the diff between them.

Locks the diff semantics (unimplemented / unplanned / broken contract) and the
code-graph side (call edges parsed from real files) so the disagreement the
mirror surfaces stays trustworthy. In-process only — no subprocess, no models.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent"))

import mirror_graph as mg
from call_edges import extract_calls
import ast


def test_extract_calls_names_and_dedupes():
    node = ast.parse("a(); a(); obj.b(); c()")
    assert extract_calls(node) == ["a", "b", "c"]


def test_extract_calls_ignores_non_calls():
    assert extract_calls(ast.parse("x = 1")) == []


def test_diff_unimplemented_is_plan_minus_code():
    diff = mg.diff_graphs({"f::a": {"depends": []}, "f::b": {"depends": []}},
                          {"f::a": {"calls": []}})
    assert diff["unimplemented"] == ["f::b"]
    assert diff["unplanned"] == []


def test_diff_unplanned_is_code_minus_plan():
    diff = mg.diff_graphs({}, {"f::x": {"calls": []}})
    assert diff["unplanned"] == ["f::x"]


def test_diff_broken_contract_flags_unmet_dependency():
    diff = mg.diff_graphs({"f::a": {"depends": ["b", "z"]}},
                          {"f::a": {"calls": ["b"]}})
    assert diff["broken_contract"] == [
        {"symbol": "f::a", "declared_but_not_called": ["z"]}]


def test_diff_honored_dependency_is_not_broken():
    diff = mg.diff_graphs({"f::a": {"depends": ["b"]}},
                          {"f::a": {"calls": ["b"]}})
    assert diff["broken_contract"] == []


def test_code_graph_reads_real_file_and_matches_plan():
    # A real, existing file: its extract_calls symbol must surface, and calling
    # ast.walk means a declared dependency on `walk` is honored (not broken).
    code = mg.code_graph(["agent/call_edges.py"], root=str(ROOT))
    assert "agent/call_edges.py::extract_calls" in code
    plan = {"agent/call_edges.py::extract_calls": {"depends": ["walk"]},
            "agent/call_edges.py::ghost": {"depends": []}}
    diff = mg.diff_graphs(plan, code)
    assert diff["unimplemented"] == ["agent/call_edges.py::ghost"]
    assert diff["broken_contract"] == []


def test_decl_name_extracts_identifier_from_signatures():
    assert mg._decl_name("def open_session(name: str) -> dict") == "open_session"
    assert mg._decl_name("export function activate(context): void") == "activate"


# ── signature drift: same symbol on both sides, different parameters ────────

def test_plan_params_ignores_types_and_defaults():
    # `name: str = ""` in the plan and `name=""` in the code is agreement.
    assert mg.plan_params('def open_session(name: str, mode: str = "r") -> dict') == ["name", "mode"]
    assert mg.plan_params("export function activate(context: vscode.Ctx): void") == ["context"]
    assert mg.plan_params("def f()") == []


def test_plan_params_handles_nested_generics():
    assert mg.plan_params("def f(a: Dict[str, int], b: List[int]) -> None") == ["a", "b"]


def test_no_drift_when_parameters_agree():
    assert mg.signature_drift({"f::a": {"signature": "def a(x)"}},
                              {"f::a": {"params": ["x"]}}) == []


def test_drift_reported_when_parameters_differ():
    got = mg.signature_drift({"f::a": {"signature": "def a(x)"}},
                             {"f::a": {"params": ["y"]}})
    assert got == [{"symbol": "f::a", "plan": ["x"], "code": ["y"]}]


def test_empty_plan_signature_cannot_drift():
    # Nothing was promised, so nothing can have drifted.
    assert mg.signature_drift({"f::a": {"signature": ""}},
                              {"f::a": {"params": ["x"]}}) == []


def test_diff_graphs_exposes_the_drift_bucket():
    d = mg.diff_graphs({"f::a": {"signature": "def a(x)", "depends": []}},
                       {"f::a": {"params": ["x", "extra"], "calls": []}})
    assert d["signature_drift"] == [
        {"symbol": "f::a", "plan": ["x"], "code": ["x", "extra"]}]
