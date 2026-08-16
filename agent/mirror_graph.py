#!/usr/bin/env python3
"""mirror_graph.py — the mirror graph: PLAN vs CODE, and the diff between them.

Two graphs that mirror each other. The PLAN graph comes from an idea_tree: every
task leaf is a node (file, name, signature, depends). The CODE graph is parsed
from the files themselves: declarations and the names each one calls. Neither is
authoritative — the value is the DISAGREEMENT, surfaced for a human the way
hds_doctor surfaces system state, never enforced.

    in plan, not in code  -> unimplemented  (a task no code answers)
    in code, not in plan  -> unplanned       (code outside the plan)
    plan depends unmet    -> broken contract (declared a call it never makes)

LIMIT, STATED PLAINLY. The code graph is parsed with Python's ast, so only
Python plan files are compared here. A plan file in another language (a .ts
extension, say) is reported as unparsed, not as unimplemented — absence of a
parser must never masquerade as absence of code.
"""
import ast
from pathlib import Path
from typing import Dict, List

# Sibling imports are function-local. Kept out of module scope so the module
# loads standalone (the acceptance sandbox copies only this file), and so
# diff_graphs — pure dict logic — is testable without the code-graph parser.


_JS_EXTS = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}
_PARSED_EXTS = {".py"} | _JS_EXTS


# The comparison lives in graph_diff — this file stayed under the 300-line
# working limit by splitting BUILDING the graphs from COMPARING them.
# Re-exported so callers and the CLI keep a single entry point.
try:
    from graph_diff import diff_graphs, plan_params, signature_drift
except ImportError:
    from .graph_diff import diff_graphs, plan_params, signature_drift


def _decl_name(signature: str) -> str:
    """The declared identifier in a one-line signature.

    Handles the shapes the plan actually uses: `def NAME(...)`,
    `function NAME(...)`, `export function NAME(...)`, `NAME(...)`. The name is
    the last identifier immediately before the first '('.
    """
    head = signature.split("(", 1)[0].strip()
    return head.split()[-1] if head else ""


def load_plan(tree_path) -> Dict[str, dict]:
    """PLAN graph: every task leaf keyed as 'file::name'.

    Value carries what the plan promises — the signature, its declared depends
    (the calls it SHOULD make) and status — so the diff can compare against what
    the code actually is.
    """
    try:
        import idea_tree
    except ImportError:
        from . import idea_tree
    root = idea_tree.load(tree_path)
    plan: Dict[str, dict] = {}
    for node in idea_tree.walk(root):
        if node.level != "task" or not node.file:
            continue
        name = _decl_name(node.signature) or node.id
        plan[f"{node.file}::{name}"] = {
            "file": node.file,
            "name": name,
            "signature": node.signature,
            "depends": list(node.depends),
            "status": node.status,
        }
    return plan


def code_graph(files: List[str], root: str = ".") -> Dict[str, dict]:
    """CODE graph for the given files, keyed as 'file::name'.

    Only Python files are parsed (via scan_module). A missing or non-Python file
    contributes nothing here; callers learn about it from `unparsed_files`, not
    from a silent gap that the diff would misread as 'unimplemented'.
    """
    try:
        from orchestrator_index import scan_module
    except ImportError:
        from .orchestrator_index import scan_module
    graph: Dict[str, dict] = {}
    for rel in files:
        p = Path(root) / rel
        if not p.exists():
            continue
        if p.suffix in _JS_EXTS:
            # JavaScript/TypeScript get the same two facts Python does.
            try:
                import js_graph
            except ImportError:
                # js_graph lives at the core root; when this module is run as a
                # script sys.path[0] is agent/, so the root has to be added or
                # every .ts file is silently skipped and reported unimplemented.
                import sys as _sys
                _root = str(Path(__file__).resolve().parent.parent)
                if _root not in _sys.path:
                    _sys.path.insert(0, _root)
                try:
                    import js_graph
                except ImportError:
                    continue
            try:
                found = js_graph.symbols(p.read_text(encoding="utf-8"))
            except OSError:
                continue
            for name, info in found.items():
                graph[f"{rel}::{name}"] = {
                    "file": rel, "name": name, "kind": "function",
                    "calls": info.get("calls", []),
                    "params": info.get("params", []),
                }
            continue
        if p.suffix != ".py":
            continue
        info = scan_module(str(p))
        params = _params_in_file(p)
        for sym in info.symbols:
            graph[f"{rel}::{sym.name}"] = {
                "file": rel,
                "name": sym.name,
                "kind": sym.kind,
                "calls": list(sym.calls),
                "params": params.get(sym.name, []),
            }
    return graph


def unparsed_files(files: List[str], root: str = ".") -> List[str]:
    """Plan files the code graph cannot see: non-Python, or not yet written."""
    out = []
    for rel in sorted(set(files)):
        p = Path(root) / rel
        if p.suffix not in _PARSED_EXTS:
            out.append(f"{rel} (no parser for {p.suffix})")
        elif not p.exists():
            out.append(f"{rel} (file absent)")
    return out


def _params_in_file(path) -> dict:
    """{function name: [parameter names]} for one Python file.

    Signature drift is the third disagreement the mirror was meant to surface
    and the only one still missing: the plan promises `open_session(name)` and
    the code declares `open_session(name, mode)`. Neither side is wrong by
    itself — the point is that they no longer agree.
    """
    import ast as _ast
    try:
        tree = _ast.parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}
    out = {}
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            a = node.args
            names = [p.arg for p in list(a.posonlyargs) + list(a.args)
                     if p.arg not in ("self", "cls")]
            out[node.name] = names
    return out


def format_report(diff: Dict[str, list], unparsed: List[str]) -> str:
    """Human-readable mirror-graph report — a disagreement list, not a verdict."""
    lines = ["MIRROR GRAPH — plan vs code", "=" * 40]

    def section(title, items):
        lines.append(f"\n{title} ({len(items)})")
        for it in items:
            lines.append(f"  · {it}")
        if not items:
            lines.append("  (none)")

    section("UNIMPLEMENTED — in plan, not in code", diff.get("unimplemented", []))
    section("UNPLANNED — in code, not in plan", diff.get("unplanned", []))
    broken = [f"{b['symbol']}  →  declared but never called: "
              f"{', '.join(b['declared_but_not_called'])}"
              for b in diff.get("broken_contract", [])]
    section("BROKEN CONTRACT — plan depends unmet in code", broken)
    section("UNPARSED — plan files the code graph cannot read", unparsed)
    return "\n".join(lines)


def report(tree_path, root: str = ".") -> str:
    """Load both graphs for one plan tree and render the diff."""
    plan = load_plan(tree_path)
    files = sorted({v["file"] for v in plan.values()})
    code = code_graph(files, root)
    diff = diff_graphs(plan, code)
    return format_report(diff, unparsed_files(files, root))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HDS mirror graph — plan vs code diff")
    parser.add_argument("tree", help="path to an idea_tree JSON (e.g. ai-mind/tasks/trees/I1.json)")
    parser.add_argument("--root", default=".", help="project root the plan files are relative to")
    args = parser.parse_args()
    print(report(args.tree, args.root))
