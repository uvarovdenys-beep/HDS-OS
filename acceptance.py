#!/usr/bin/env python3
"""acceptance.py — check generated code against tests declared in the plan.

Monte Carlo proves a function does not CRASH. It cannot prove the function is
RIGHT: `def add(a, b): return a - b` survives a thousand random calls. Measured,
not argued — 100 random calls, verdict OK, both functions wrong.

This closes that gap the way Parsel does: the plan declares what the function
must satisfy, and the generated code is executed against those assertions. A
failure feeds the self-correction loop exactly like a cage verdict, so the model
fixes the specific wrong answer instead of re-rolling.

Assertions are expressions that must evaluate truthy, IN THE SUBJECT'S LANGUAGE:

    Python : ["add(2, 3) == 5", "add(-1, 1) == 0"]
    JS     : ["add(2, 3) === 5", "JSON.stringify(tidy([3,1,1])) === '[1,3]'"]

(JS `==` on arrays/objects is reference equality — compare primitives or
serialise, exactly as a JS author would.)

They run inside SandboxRunner — the single audited exec surface, no network —
never on the host. Python and JavaScript are verified; a language without a
runner here is reported "unverified" (never a false pass).
"""
import json
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT = 30
MAX_ASSERTIONS = 12

_PY_EXTS = {".py"}
_JS_EXTS = {".js", ".cjs", ".mjs"}
_TS_EXTS = {".ts"}   # .tsx needs a JSX transform — out of scope here

# Python: import the module in a probe, eval each assertion against its symbols.
_PY_PROBE = '''
import json, sys, importlib.util

path, raw = sys.argv[1], sys.argv[2]
checks = json.loads(raw)

spec = importlib.util.spec_from_file_location("subject", path)
mod = importlib.util.module_from_spec(spec)
failures = []
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print(json.dumps({"loaded": False, "checked": 0,
                      "failures": [{"check": "<import>", "error": repr(e)}]}))
    sys.exit(0)

env = {k: getattr(mod, k) for k in dir(mod) if not k.startswith("__")}
for c in checks:
    try:
        if not eval(c, dict(env)):
            failures.append({"check": c, "error": "evaluated false"})
    except Exception as e:
        failures.append({"check": c, "error": repr(e)})

print(json.dumps({"loaded": True, "checked": len(checks), "failures": failures}))
'''

# JavaScript: no module system needed. The subject's top-level `function`
# declarations are hoisted into scope, so a footer appended after the source can
# call them directly. A direct eval inside the footer sees those declarations.
_JS_FOOTER = '''
;(function () {
  var __checks = %s;
  var __res = [];
  for (var __i = 0; __i < __checks.length; __i++) {
    var __c = __checks[__i];
    try { __res.push({ check: __c, ok: Boolean(eval(__c)) }); }
    catch (e) { __res.push({ check: __c, ok: false, error: String((e && e.message) || e) }); }
  }
  var failures = __res.filter(function (x) { return !x.ok; })
    .map(function (x) { return { check: x.check, error: x.error || "evaluated false" }; });
  console.log(JSON.stringify({ loaded: true, checked: __checks.length, failures: failures }));
})();
'''


def _clean(assertions):
    checks = [str(a).strip() for a in (assertions or []) if str(a).strip()]
    return checks[:MAX_ASSERTIONS]


def _unverified(note):
    return {"ok": True, "checked": 0, "failures": [], "note": note}


def _run_python(src, checks, timeout):
    from sandbox.runner import RunRequest, SandboxRunner
    with tempfile.TemporaryDirectory(prefix="hds_acc_") as td:
        work = Path(td)
        (work / "subject.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        (work / "probe.py").write_text(_PY_PROBE, encoding="utf-8")
        return SandboxRunner().run(RunRequest(
            tool="python3", args=["probe.py", "subject.py", json.dumps(checks)],
            workdir=str(work), image="python:3.12-alpine", timeout=timeout))


def _run_js(src, checks, timeout):
    from sandbox.runner import RunRequest, SandboxRunner
    ext = src.suffix
    run_name = "run" + ext            # keep .mjs so node picks ESM mode
    combined = src.read_text(encoding="utf-8") + "\n" + (_JS_FOOTER % json.dumps(checks))
    with tempfile.TemporaryDirectory(prefix="hds_acc_") as td:
        work = Path(td)
        (work / run_name).write_text(combined, encoding="utf-8")
        return SandboxRunner().run(RunRequest(
            tool="node", args=[run_name],
            workdir=str(work), image="node:20-alpine", timeout=timeout))


def _run_ts(src, checks, timeout):
    # Node >=22.6 runs TypeScript by STRIPPING types (no type-check — the cage
    # already ran `tsc --noEmit`; acceptance only needs the code to RUN). The
    # footer is plain JS appended to the .ts subject.
    from sandbox.runner import RunRequest, SandboxRunner
    combined = src.read_text(encoding="utf-8") + "\n" + (_JS_FOOTER % json.dumps(checks))
    with tempfile.TemporaryDirectory(prefix="hds_acc_") as td:
        work = Path(td)
        (work / "run.ts").write_text(combined, encoding="utf-8")
        return SandboxRunner().run(RunRequest(
            tool="node", args=["--experimental-strip-types", "run.ts"],
            workdir=str(work), image="node:22-alpine", timeout=timeout))


def check_module(path, assertions, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Run declared assertions against a module. Returns a verdict dict:

    {"ok": bool, "checked": int, "failures": [{"check", "error"}], "note": str}

    ok=True with checked=0 means nothing was declared OR the language is not
    verifiable here — that is "unverified", not "correct", and callers must not
    read it as a pass. Never raises: a verifier that breaks the build is worse
    than no verifier.
    """
    src = Path(path)
    if not src.exists():
        return _unverified("file absent")
    ext = src.suffix
    if ext in _PY_EXTS:
        runner = _run_python
    elif ext in _JS_EXTS:
        runner = _run_js
    elif ext in _TS_EXTS:
        runner = _run_ts
    else:
        return _unverified(f"no acceptance runner for '{ext}'")

    checks = _clean(assertions)
    if not checks:
        return _unverified("none declared")

    try:
        res = runner(src, checks, timeout)
    except Exception as e:
        return _unverified(f"sandbox unavailable: {e}")

    if res.timed_out:
        return {"ok": False, "checked": len(checks),
                "failures": [{"check": "<all>", "error": f"timed out after {timeout}s"}],
                "note": "timeout"}
    try:
        data = json.loads((res.stdout or "").strip().splitlines()[-1])
    except Exception:
        return _unverified("probe produced no verdict")
    data["ok"] = not data.get("failures")
    data.setdefault("note", "")
    return data


def feedback(verdict: dict) -> str:
    """Turn a failure into the exact sentence the model must act on."""
    fails = verdict.get("failures") or []
    if not fails:
        return ""
    lines = [f"{f.get('check')}  ->  {f.get('error')}" for f in fails[:4]]
    return ("Your code did not satisfy the declared checks:\n"
            + "\n".join(lines)
            + "\nFix the logic so every check holds. Keep the signature.")


def summarise(verdict: dict) -> str:
    """One line for the log."""
    if verdict.get("note") and not verdict.get("checked"):
        return f"Acceptance: {verdict['note']}"
    n = verdict.get("checked", 0)
    bad = len(verdict.get("failures") or [])
    if bad:
        return f"Acceptance: {bad}/{n} check(s) FAILED"
    return f"Acceptance: {n}/{n} check(s) passed"
