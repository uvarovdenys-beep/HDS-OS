"""Acceptance checks: prove generated code is RIGHT, not merely that it runs.

The load-bearing test here is `test_monte_carlo_blindness_is_covered`: it pins
the exact gap this module exists to close, on one file, with both verifiers.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WRONG = (
    "def add(a: int, b: int) -> int:\n"
    "    return a - b\n"
)
RIGHT = (
    "def add(a: int, b: int) -> int:\n"
    "    return a + b\n"
)


def _write(name, code):
    p = Path(ROOT) / "storage" / "acc_test"
    p.mkdir(parents=True, exist_ok=True)
    f = p / name
    f.write_text(code)
    return f


def test_correct_code_passes_declared_checks():
    import acceptance
    f = _write("right.py", RIGHT)
    try:
        r = acceptance.check_module(f, ["add(2, 3) == 5", "add(-1, 1) == 0"])
        if r.get("note"):
            return          # sandbox unavailable — nothing to assert
        assert r["ok"] and r["checked"] == 2
    finally:
        f.unlink(missing_ok=True)


def test_wrong_but_stable_logic_is_caught():
    import acceptance
    f = _write("wrong.py", WRONG)
    try:
        r = acceptance.check_module(f, ["add(2, 3) == 5"])
        if r.get("note"):
            return
        assert not r["ok"]
        assert r["failures"][0]["check"] == "add(2, 3) == 5"
    finally:
        f.unlink(missing_ok=True)


def test_monte_carlo_blindness_is_covered():
    """The reason this module exists, pinned on one file.

    Randomised calls cannot fail `a - b`: it never crashes. Only a declared
    expectation catches it. If this ever passes Monte Carlo AND acceptance,
    something has silently stopped checking.
    """
    import acceptance
    import montecarlo
    f = _write("blind.py", WRONG)
    try:
        mc = montecarlo.verify_module(f, trials=25)
        acc = acceptance.check_module(f, ["add(2, 3) == 5"])
        if mc.get("note") or acc.get("note"):
            return
        assert mc["ok"], "Monte Carlo is expected to be blind here"
        assert not acc["ok"], "acceptance must catch what Monte Carlo cannot"
    finally:
        f.unlink(missing_ok=True)


def test_nothing_declared_is_not_a_pass():
    """checked=0 means unverified. A caller must not read it as correct."""
    import acceptance
    f = _write("bare.py", RIGHT)
    try:
        r = acceptance.check_module(f, [])
        assert r["checked"] == 0
        assert r["note"]           # says why, so ok=True cannot be misread
    finally:
        f.unlink(missing_ok=True)


def test_import_error_is_reported_not_raised():
    import acceptance
    f = _write("boom.py", "raise RuntimeError('bad module')\n")
    try:
        r = acceptance.check_module(f, ["1 == 1"])
        if r.get("note"):
            return
        assert not r["ok"]
        assert r["failures"][0]["check"] == "<import>"
    finally:
        f.unlink(missing_ok=True)


def test_bad_expression_is_a_failure_not_a_crash():
    import acceptance
    f = _write("expr.py", RIGHT)
    try:
        r = acceptance.check_module(f, ["nonexistent(1) == 2"])
        if r.get("note"):
            return
        assert not r["ok"] and r["failures"]
    finally:
        f.unlink(missing_ok=True)


def test_non_python_is_skipped_not_failed():
    import acceptance
    r = acceptance.check_module(Path(ROOT) / "README.md", ["1 == 1"])
    assert r["ok"] and r["checked"] == 0


def test_missing_file_is_skipped_not_failed():
    import acceptance
    r = acceptance.check_module(Path(ROOT) / "storage" / "no_such.py", ["1 == 1"])
    assert r["ok"] and r["checked"] == 0


def test_assertion_count_is_capped():
    import acceptance
    f = _write("cap.py", RIGHT)
    try:
        many = ["add(1, 1) == 2"] * 50
        r = acceptance.check_module(f, many)
        if r.get("note"):
            return
        assert r["checked"] == acceptance.MAX_ASSERTIONS
    finally:
        f.unlink(missing_ok=True)


def test_feedback_names_the_failing_check():
    import acceptance
    verdict = {"ok": False, "checked": 1,
               "failures": [{"check": "add(2, 3) == 5", "error": "evaluated false"}]}
    msg = acceptance.feedback(verdict)
    assert "add(2, 3) == 5" in msg and "evaluated false" in msg


def test_feedback_is_empty_when_nothing_failed():
    import acceptance
    assert acceptance.feedback({"ok": True, "checked": 2, "failures": []}) == ""


# ── JavaScript acceptance: the same behavioural verifier Python has ─────────
# These need the node sandbox; when it is unavailable they self-skip via the
# note guard, exactly like the Python cases above.

def test_js_correct_code_passes_declared_checks():
    import acceptance
    f = _write("right.js", "function add(a, b) { return a + b; }\n")
    try:
        r = acceptance.check_module(f, ["add(2, 3) === 5", "add(-1, 1) === 0"])
        if r.get("note"):
            return          # sandbox unavailable — nothing to assert
        assert r["ok"] and r["checked"] == 2
    finally:
        f.unlink(missing_ok=True)


def test_js_wrong_code_fails_declared_checks():
    import acceptance
    f = _write("wrong.js", "function add(a, b) { return a - b; }\n")
    try:
        r = acceptance.check_module(f, ["add(2, 3) === 5"])
        if r.get("note"):
            return
        assert r["ok"] is False and r["failures"]
    finally:
        f.unlink(missing_ok=True)


def test_ts_correct_code_passes_via_type_stripping():
    # Node strips the type annotations and runs the code; the cage already
    # type-checked it with tsc.
    import acceptance
    f = _write("right.ts", "function add(a: number, b: number): number { return a + b; }\n")
    try:
        r = acceptance.check_module(f, ["add(2, 3) === 5", "add(-1, 1) === 0"])
        if r.get("note"):
            return
        assert r["ok"] and r["checked"] == 2
    finally:
        f.unlink(missing_ok=True)


def test_ts_wrong_code_fails_declared_checks():
    import acceptance
    f = _write("wrong.ts", "function add(a: number, b: number): number { return a - b; }\n")
    try:
        r = acceptance.check_module(f, ["add(2, 3) === 5"])
        if r.get("note"):
            return
        assert r["ok"] is False and r["failures"]
    finally:
        f.unlink(missing_ok=True)


def test_unsupported_language_is_unverified_not_failed():
    # A language with no runner must never be a false pass — it is "unverified".
    import acceptance
    f = _write("thing.rb", "def add(a, b)\n  a + b\nend\n")
    try:
        r = acceptance.check_module(f, ["add(2, 3) == 5"])
        assert r["ok"] is True and r["checked"] == 0 and r["note"]
    finally:
        f.unlink(missing_ok=True)
