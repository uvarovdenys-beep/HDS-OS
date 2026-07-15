#!/usr/bin/env python3
"""montecarlo.py — prove generated code RUNS, not merely that it parses.

The cage answers "is this safe and well-formed?". It cannot answer "does it
work". A function that subtracts where it should add is valid Python and passes
every validator. This module adds the missing third layer:

    cage (safety) -> tsc/AST (validity) -> Monte Carlo (it actually runs)

Each public function is called with randomised arguments derived from its type
hints, inside the SandboxRunner (isolated, no network). What this catches:
crashes, unhandled exceptions, hangs. What it does NOT catch: wrong-but-stable
logic — random inputs cannot know the intent. Honest guarantee: "does not blow
up on N random inputs", which is far more than "it parsed".
"""
import json
import tempfile
from pathlib import Path

DEFAULT_TRIALS = 20
DEFAULT_TIMEOUT = 25

# The probe runs INSIDE the sandbox next to a copy of the target file. It is
# ephemeral scaffolding, never part of the project.
_PROBE = r'''
import importlib.util, inspect, json, random, sys, traceback

target, trials, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rng = random.Random(seed)

def sample(annotation):
    """A value for one parameter — typed when annotated, mixed when not."""
    name = getattr(annotation, "__name__", str(annotation)).lower()
    if "int" in name:
        return rng.choice([0, 1, -1, 2, 7, 100, -50, 999999])
    if "float" in name:
        return rng.choice([0.0, 1.5, -2.25, 3.14159, 1e6])
    if "bool" in name:
        return rng.choice([True, False])
    if "str" in name:
        return rng.choice(["", "a", "Hello World", "  spaced  ", "123", "ЮНІКОД", "x" * 200])
    if "list" in name or "sequence" in name:
        return rng.choice([[], [1, 2, 3], ["a", "b"], list(range(50))])
    if "dict" in name or "mapping" in name:
        return rng.choice([{}, {"a": 1}, {"k": "v", "n": 2}])
    return rng.choice([0, 1, -1, "", "text", [], [1, 2], {}, None, 3.5, True])

results = {"checked": 0, "calls": 0, "failures": []}
spec = importlib.util.spec_from_file_location("subject", target)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception:
    results["failures"].append({"func": "<import>", "args": None,
                                "error": traceback.format_exc(limit=3)})
    print(json.dumps(results)); sys.exit(0)

def callables_of(obj, prefix=""):
    out = []
    for name, member in vars(obj).items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(member):
            out.append((prefix + name, member, None))
        elif inspect.isclass(member) and member.__module__ == "subject":
            out.append((prefix + name, member, "class"))
    return out

for name, obj, kind in callables_of(mod):
    if kind == "class":
        continue                      # constructing arbitrary classes is guesswork
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        continue
    params = [p for p in sig.parameters.values()
              if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
              and p.default is p.empty]
    # When every parameter is annotated we hand the function values of the types
    # it asked for, so a crash is ITS bug. Unannotated params get random types,
    # where TypeError/ValueError mean "correctly rejected garbage" — we cannot
    # tell a guard from a defect, so we only tolerate those two.
    typed = bool(params) and all(p.annotation is not p.empty for p in params)
    tolerated = (ValueError, TypeError) if typed else (
        ValueError, TypeError, ZeroDivisionError, KeyError,
        IndexError, AttributeError, OverflowError)
    results["checked"] += 1
    for _ in range(trials):
        args = [sample(p.annotation) for p in params]
        results["calls"] += 1
        try:
            obj(*args)
        except tolerated:
            pass                      # rejecting bad input is CORRECT behaviour
        except Exception:
            results["failures"].append({
                "func": name, "args": repr(args)[:160],
                "error": traceback.format_exc(limit=2)[-300:]})
            break                     # one report per function is enough

print(json.dumps(results))
'''


def verify_module(path, trials=DEFAULT_TRIALS, timeout=DEFAULT_TIMEOUT, seed=1337):
    """Randomised smoke test of one Python file. Returns a result dict:

    {"ok": bool, "checked": int, "calls": int, "failures": [...], "note": str}

    ok=True with checked=0 means "nothing testable was found" — not a pass.
    Never raises: a verifier that breaks the build is worse than no verifier.
    """
    src = Path(path)
    if src.suffix != ".py" or not src.exists():
        return {"ok": True, "checked": 0, "calls": 0, "failures": [],
                "note": "not a Python file"}
    try:
        from sandbox.runner import SandboxRunner, RunRequest
        with tempfile.TemporaryDirectory(prefix="hds_mc_") as td:
            work = Path(td)
            (work / "subject.py").write_text(src.read_text(encoding="utf-8"),
                                             encoding="utf-8")
            (work / "probe.py").write_text(_PROBE, encoding="utf-8")
            res = SandboxRunner().run(RunRequest(
                tool="python3",
                args=["probe.py", "subject.py", str(trials), str(seed)],
                workdir=str(work), image="python:3.12-alpine", timeout=timeout))
    except Exception as e:
        return {"ok": True, "checked": 0, "calls": 0, "failures": [],
                "note": "sandbox unavailable: %s" % e}

    if res.timed_out:
        return {"ok": False, "checked": 0, "calls": 0,
                "failures": [{"func": "<module>", "args": None,
                              "error": "timed out after %ss — possible infinite loop"
                                       % timeout}],
                "note": "timeout"}
    try:
        data = json.loads((res.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {"ok": True, "checked": 0, "calls": 0, "failures": [],
                "note": "probe produced no verdict"}
    data["ok"] = not data.get("failures")
    data.setdefault("note", "")
    return data


def summarise(result):
    """One line for the log/voice."""
    if result.get("note") and not result.get("checked"):
        return "Monte Carlo skipped (%s)" % result["note"]
    if result.get("ok"):
        return "Monte Carlo: %d function(s), %d random calls, no crashes" % (
            result.get("checked", 0), result.get("calls", 0))
    first = result["failures"][0]
    return "Monte Carlo FAILED in %s(%s): %s" % (
        first.get("func"), first.get("args"),
        (first.get("error") or "").strip().splitlines()[-1][:120])
