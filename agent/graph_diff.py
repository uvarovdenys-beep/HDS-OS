#!/usr/bin/env python3
"""graph_diff.py — compare the PLAN graph with the CODE graph.

Split out of mirror_graph when that file crossed the 300-line working limit.
The division is the honest one: mirror_graph BUILDS the two graphs, this module
COMPARES them, and neither decides who is right — the disagreement is the
product.

Four kinds of disagreement:
    in plan, not in code        -> unimplemented
    in code, not in plan        -> unplanned
    plan depends B, code never calls B -> broken contract
    same symbol, other params   -> signature drift
"""
from typing import Dict


def plan_params(signature: str) -> list:
    """Parameter NAMES declared in a one-line plan signature.

    Types and defaults are deliberately ignored: the plan writes
    `name: str = ""` and the code writes `name=""`, which is agreement, not
    drift. Only the names and their order are compared.
    """
    if "(" not in signature:
        return []
    inner = signature.split("(", 1)[1].rsplit(")", 1)[0]
    out = []
    depth = 0
    current = ""
    for ch in inner:
        if ch in "[({<":
            depth += 1
        elif ch in "])}>":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(current)
            current = ""
        else:
            current += ch
    out.append(current)
    names = []
    for part in out:
        part = part.split("=", 1)[0].split(":", 1)[0].strip()
        part = part.lstrip("*")
        if part and part not in ("self", "cls"):
            names.append(part)
    return names


def signature_drift(plan: Dict[str, dict], code: Dict[str, dict]) -> list:
    """
    Compare the expected and actual parameters of functions in plan and code.

    Args:
        plan (Dict[str, dict]): The planned function signatures.
        code (Dict[str, dict]): The actual function parameters.

    Returns:
        list: A list of differences between plan and code.
    """
    drifts = []

    for key in sorted(plan.keys() & code.keys()):
        signature = plan[key].get('signature', '')
        if not signature:
            continue          # nothing promised, so nothing can have drifted
        expected = plan_params(signature)   # shared parser: types and defaults
        actual = code[key].get('params', [])  # are agreement, not drift

        if expected != actual:
            drifts.append({'symbol': key, 'plan': expected, 'code': actual})

    return drifts


def diff_graphs(plan: Dict[str, dict], code: Dict[str, dict]) -> Dict[str, list]:
    """
    Compare a plan graph and a code graph to find differences.

    Args:
        plan (Dict[str, dict]): The planned graph with file names as keys.
        code (Dict[str, dict]): The actual code graph with file names as keys.

    Returns:
        Dict[str, list]: A dictionary containing three keys:
            'unimplemented': sorted list of keys in `plan` but NOT in `code`.
            'unplanned': sorted list of keys in `code` but NOT in `plan`.
            'broken_contract': for every key present in BOTH, read the plan entry's
                'depends' list (default []) and the code entry's 'calls' list
                (default []). If any name in depends is NOT in calls, append the dict
                {'symbol': key, 'declared_but_not_called': sorted(missing names)}.
    """
    # The third disagreement the mirror was built to surface: both sides
    # have the symbol, but they no longer promise the same parameters.
    signature_drifts = signature_drift(plan, code)
    unimplemented = sorted(set(plan) - set(code))
    unplanned = sorted(set(code) - set(plan))
    broken_contract = []

    for key in plan.keys() & code.keys():
        plan_entry = plan[key]
        code_entry = code[key]

        depends = set(plan_entry.get('depends', []))
        calls = set(code_entry.get('calls', []))

        missing_calls = depends - calls
        if missing_calls:
            broken_contract.append({
                'symbol': key,
                'declared_but_not_called': sorted(missing_calls)
            })

    return {
        'unimplemented': unimplemented,
        'unplanned': unplanned,
        'broken_contract': broken_contract,
        'signature_drift': signature_drifts
    }
