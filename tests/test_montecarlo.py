"""Monte Carlo: prove generated code RUNS, not merely that it parses."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _write(name, code):
    p = Path(ROOT) / "storage" / "mc_test"
    p.mkdir(parents=True, exist_ok=True)
    f = p / name
    f.write_text(code)
    return f


def test_clean_code_passes():
    import montecarlo
    f = _write("ok.py", "def add(a: int, b: int) -> int:\n    return a + b\n")
    try:
        r = montecarlo.verify_module(f, trials=10)
        if r.get("note"):
            return          # sandbox unavailable — nothing to assert
        assert r["ok"] and r["checked"] == 1
    finally:
        f.unlink(missing_ok=True)


def test_annotated_crash_is_caught():
    """A structural break is caught whatever the input — that is the contract.

    This test used to assert that ZeroDivisionError in `a / b` was a defect,
    because the old rule was "annotated parameters mean any crash is the
    function's bug". That rule cost too much: the right TYPE is not the right
    DOMAIN, so a roman-numeral parser annotated `s: str` was failed for raising
    on "123" — measured at 1 valid task in 10 rejected.

    The rule is now "does this exception say the CODE is broken, regardless of
    input". `a / b` raising on zero is Python's own semantics, so it no longer
    counts; a name that was never declared always does. That is the narrower,
    honest check — and it is the one that catches the real failure mode, a
    module-level declaration no generated function emitted.
    """
    import montecarlo
    f = _write("crash.py", "def use(x: int) -> int:\n"
                           "    global _state\n"
                           "    return _state + x\n")
    try:
        r = montecarlo.verify_module(f, trials=30)
        if r.get("note"):
            return
        assert not r["ok"]
        assert "NameError" in r["failures"][0]["error"]
    finally:
        f.unlink(missing_ok=True)


def test_domain_rejection_is_not_a_defect():
    """A function that raises on out-of-domain input is CORRECT.

    Random values are almost always outside a real function's domain, so
    treating any raise as a crash punishes input validation. Pinned with the
    exact case that exposed it.
    """
    import montecarlo
    f = _write("roman.py",
               "def roman_to_int(s: str) -> int:\n"
               "    vals = {'I': 1, 'V': 5, 'X': 10}\n"
               "    return sum(vals[c] for c in s)\n")
    try:
        r = montecarlo.verify_module(f, trials=30)
        if r.get("note"):
            return
        assert r["ok"], "validating input must not be scored as a crash"
    finally:
        f.unlink(missing_ok=True)


def test_deliberate_input_rejection_is_not_a_failure():
    import montecarlo
    f = _write("guard.py",
               "def div(a: int, b: int) -> float:\n"
               "    if b == 0:\n"
               "        raise ValueError('b must not be zero')\n"
               "    return a / b\n")
    try:
        r = montecarlo.verify_module(f, trials=30)
        if r.get("note"):
            return
        assert r["ok"], r
    finally:
        f.unlink(missing_ok=True)


def test_non_python_is_skipped_not_failed():
    import montecarlo
    f = _write("thing.rb", "def f(x)\n  x\nend\n")
    try:
        r = montecarlo.verify_module(f)
        assert r["ok"] and r["checked"] == 0 and r["note"]
    finally:
        f.unlink(missing_ok=True)


# ── JavaScript / TypeScript Monte Carlo: the same third layer JS/TS lacked ──
# Need the node sandbox; self-skip via the note guard when it is unavailable.

def test_js_clean_code_passes():
    import montecarlo
    f = _write("ok.js", "function addOne(x) { return (x || 0) + 1; }\n")
    try:
        r = montecarlo.verify_module(f, trials=8)
        if r.get("note"):
            return
        assert r["ok"] and r["checked"] == 1 and r["calls"] > 0
    finally:
        f.unlink(missing_ok=True)


def test_js_reference_error_is_caught():
    # An undeclared name is JS's NameError — broken whatever the input.
    import montecarlo
    f = _write("bug.js", "function broken(x) { return undeclaredThing + x; }\n")
    try:
        r = montecarlo.verify_module(f, trials=8)
        if r.get("note"):
            return
        assert r["ok"] is False and r["failures"]
    finally:
        f.unlink(missing_ok=True)


def test_ts_clean_code_passes_via_type_stripping():
    import montecarlo
    f = _write("ok.ts", "function sq(x: number): number { return (x || 0) * (x || 0); }\n")
    try:
        r = montecarlo.verify_module(f, trials=8)
        if r.get("note"):
            return
        assert r["ok"] and r["checked"] == 1
    finally:
        f.unlink(missing_ok=True)
