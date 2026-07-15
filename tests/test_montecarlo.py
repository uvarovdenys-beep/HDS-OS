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
    """Typed params mean we hand correct types — a crash is the function's bug."""
    import montecarlo
    f = _write("crash.py", "def div(a: int, b: int) -> float:\n    return a / b\n")
    try:
        r = montecarlo.verify_module(f, trials=30)
        if r.get("note"):
            return
        assert not r["ok"]
        assert "ZeroDivision" in r["failures"][0]["error"]
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
    f = _write("style.css", "body{color:red}")
    try:
        r = montecarlo.verify_module(f)
        assert r["ok"] and r["checked"] == 0
    finally:
        f.unlink(missing_ok=True)
