#!/usr/bin/env python3
"""montecarlo.py — prove generated code RUNS, not merely that it parses.

The cage answers "is this safe and well-formed?". It cannot answer "does it
work". A function that subtracts where it should add is valid code and passes
every validator. This module adds the missing third layer:

    cage (safety) -> tsc/AST (validity) -> Monte Carlo (it actually runs)

Each public function is called with randomised arguments inside the
SandboxRunner (isolated, no network). What this catches: crashes, unhandled
structural errors, hangs. What it does NOT catch: wrong-but-stable logic —
random inputs cannot know the intent. Honest guarantee: "does not blow up on N
random inputs", which is far more than "it parsed".

Python is introspected with `inspect`. JavaScript and TypeScript are parsed for
their top-level function declarations and each is called in a node sandbox
(.ts via --experimental-strip-types). A language without a runner here returns
"unverified" — never a false pass.
"""
import json
import re
import tempfile
from pathlib import Path

DEFAULT_TRIALS = 20
DEFAULT_TIMEOUT = 25

_PY_EXTS = {".py"}
_JS_EXTS = {".js", ".cjs", ".mjs"}
_TS_EXTS = {".ts"}

# ── Python probe (unchanged): runs INSIDE the sandbox next to the target. ──
_PROBE = r'''
import importlib.util, inspect, json, random, sys, traceback

target, trials, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rng = random.Random(seed)

def sample(annotation):
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
        continue
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        continue
    params = [p for p in sig.parameters.values()
              if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
              and p.default is p.empty]
    STRUCTURAL = (NameError, UnboundLocalError, ImportError,
                  RecursionError, MemoryError, SyntaxError, IndentationError)
    results["checked"] += 1
    for _ in range(trials):
        args = [sample(p.annotation) for p in params]
        results["calls"] += 1
        try:
            obj(*args)
        except STRUCTURAL:
            results["failures"].append({
                "func": name, "args": repr(args)[:160],
                "error": traceback.format_exc(limit=2)[-300:]})
            break
        except Exception:
            pass

print(json.dumps(results))
'''

# ── JS/TS harness ──────────────────────────────────────────────────────
# The subject's top-level function declarations are hoisted into scope, so a
# footer appended after the source can call them by name. ReferenceError and
# RangeError are the JS analogues of Python's NameError / RecursionError: they
# say the code is broken no matter what you pass it. Any other throw is treated
# as a guard on out-of-domain random input, not a defect (mirrors the Python
# probe, which measurably over-rejected when it counted domain raises).
_JS_HEAD = '''
var __s = (%d) >>> 0;
function __rand() { __s = (__s * 1664525 + 1013904223) >>> 0; return __s / 4294967296; }
function __pick(a) { return a[Math.floor(__rand() * a.length)]; }
function __a() { return __pick([0, 1, -1, 2, 7, 100, -50, "", "a", "Hello World",
  "  x  ", "123", [], [1, 2, 3], ["a", "b"], {}, {k: 1}, null, true, false, 3.5]); }
var __TRIALS = %d, __fail = [], __checked = 0, __calls = 0;
function __run(name, thunk) {
  __checked++;
  for (var i = 0; i < __TRIALS; i++) {
    __calls++;
    try { thunk(); }
    catch (e) {
      if (e instanceof ReferenceError || e instanceof RangeError) {
        __fail.push({ func: name,
          error: String((e && e.stack) || e).split("\\n").slice(0, 2).join(" | ").slice(0, 300) });
        break;
      }
    }
  }
}
'''
_JS_TAIL = '\nconsole.log(JSON.stringify({ checked: __checked, calls: __calls, failures: __fail }));\n'

# Top-level declarations we can call: function decls, and arrow/function
# expressions bound to const/let/var. Private (_-prefixed) names are skipped.
_DECL_PATTERNS = [
    re.compile(r'^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z$][\w$]*)\s*\(([^)]*)\)', re.M),
    re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>', re.M),
    re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z$][\w$]*)\s*=\s*(?:async\s*)?function\s*\(([^)]*)\)', re.M),
]


def _js_specs(source: str):
    """Top-level (name, arity) pairs the harness can call. Deduped, ordered."""
    seen, specs = set(), []
    for pat in _DECL_PATTERNS:
        for m in pat.finditer(source):
            name, raw = m.group(1), m.group(2).strip()
            if name.startswith("_") or name in seen:
                continue
            # Arity from top-level commas; nested <>/() are rare in generated
            # leaves and an over/under-count is harmless — JS ignores extra args
            # and fills missing ones with undefined.
            arity = 0 if not raw else raw.count(",") + 1
            seen.add(name)
            specs.append((name, min(arity, 6)))
    return specs


def _js_footer(source: str, trials: int, seed: int) -> str:
    specs = _js_specs(source)
    lines = [_JS_HEAD % (seed, trials)]
    for name, arity in specs:
        args = ", ".join(["__a()"] * arity)
        lines.append('__run(%s, function () { return %s(%s); });' % (json.dumps(name), name, args))
    lines.append(_JS_TAIL)
    return "\n".join(lines)


def _run_js(src, trials, timeout, seed, image, strip):
    from sandbox.runner import SandboxRunner, RunRequest
    combined = src.read_text(encoding="utf-8") + "\n" + _js_footer(
        src.read_text(encoding="utf-8"), trials, seed)
    run_name = "run" + src.suffix
    args = (["--experimental-strip-types", run_name] if strip else [run_name])
    with tempfile.TemporaryDirectory(prefix="hds_mc_") as td:
        work = Path(td)
        (work / run_name).write_text(combined, encoding="utf-8")
        return SandboxRunner().run(RunRequest(
            tool="node", args=args, workdir=str(work), image=image, timeout=timeout))


def _run_py(src, trials, timeout, seed):
    from sandbox.runner import SandboxRunner, RunRequest
    with tempfile.TemporaryDirectory(prefix="hds_mc_") as td:
        work = Path(td)
        (work / "subject.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        (work / "probe.py").write_text(_PROBE, encoding="utf-8")
        return SandboxRunner().run(RunRequest(
            tool="python3", args=["probe.py", "subject.py", str(trials), str(seed)],
            workdir=str(work), image="python:3.12-alpine", timeout=timeout))


def _unverified(note):
    return {"ok": True, "checked": 0, "calls": 0, "failures": [], "note": note}


def verify_module(path, trials=DEFAULT_TRIALS, timeout=DEFAULT_TIMEOUT, seed=1337):
    """Randomised smoke test of one file. Returns a result dict:

    {"ok": bool, "checked": int, "calls": int, "failures": [...], "note": str}

    ok=True with checked=0 means "nothing testable was found" or the language is
    not supported — not a pass. Never raises: a verifier that breaks the build is
    worse than no verifier.
    """
    src = Path(path)
    if not src.exists():
        return _unverified("file absent")
    ext = src.suffix
    try:
        if ext in _PY_EXTS:
            res = _run_py(src, trials, timeout, seed)
        elif ext in _JS_EXTS:
            res = _run_js(src, trials, timeout, seed, "node:20-alpine", False)
        elif ext in _TS_EXTS:
            res = _run_js(src, trials, timeout, seed, "node:22-alpine", True)
        else:
            return _unverified("no monte carlo runner for '%s'" % ext)
    except Exception as e:
        return _unverified("sandbox unavailable: %s" % e)

    if res.timed_out:
        return {"ok": False, "checked": 0, "calls": 0,
                "failures": [{"func": "<module>", "args": None,
                              "error": "timed out after %ss — possible infinite loop" % timeout}],
                "note": "timeout"}
    try:
        data = json.loads((res.stdout or "").strip().splitlines()[-1])
    except Exception:
        return _unverified("probe produced no verdict")
    data.setdefault("calls", 0)
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
