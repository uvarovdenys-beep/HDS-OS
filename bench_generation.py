#!/usr/bin/env python3
"""bench_generation.py — HDS generation benchmark. Turn "plausible" into "measured".

`benchmark.py` proves what the cage STOPS. This proves what the agent BUILDS.
Until now every claim about HDS generation quality rested on single anecdotes;
Parsel and CodePlan could report 67%->85% and 0/6->5/6 precisely because they
built the measurement before the improvement. This is that measurement.

What it measures: pass@1 of the FULL pipeline — model resolution, generation,
the cage (R-19/R-01/R-AST), self-correction, Monte Carlo — on HumanEval. Not the
raw model: the agent, as it actually runs.

Every generated solution is executed against the official HumanEval test inside
SandboxRunner (the single audited exec surface), never on the host.

Run:  python3 bench_generation.py --n 100 --model qwen/qwen2.5-coder-14b
"""
import argparse
import gzip
import json
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HUMANEVAL_URL = ("https://raw.githubusercontent.com/openai/human-eval/"
                 "master/data/HumanEval.jsonl.gz")
CACHE = ROOT / "storage" / "bench" / "humaneval.jsonl"
OUT_DIR = "storage/bench/gen"


def load_problems(limit: int) -> list:
    """HumanEval, cached through the cage on first fetch."""
    if not CACHE.exists():
        print(f"fetching HumanEval -> {CACHE.relative_to(ROOT)}")
        with urllib.request.urlopen(HUMANEVAL_URL, timeout=60) as r:
            body = gzip.decompress(r.read()).decode("utf-8")
        import scribe
        scribe.execute({"op": "write", "path": str(CACHE), "content": body},
                       protocol_size=None)
    rows = [json.loads(line) for line in
            CACHE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit]


def run_official_test(solution: str, problem: dict, timeout: int = 30) -> tuple:
    """Execute the problem's own test against the solution, in the sandbox.

    Returns (passed, detail). A sandbox that cannot run is reported as an error,
    never as a pass — an unmeasurable result is not a good result.
    """
    program = (solution + "\n\n" + problem["test"] + "\n"
               + f"check({problem['entry_point']})\n")
    try:
        from sandbox.runner import RunRequest, SandboxRunner
        with tempfile.TemporaryDirectory(prefix="hds_bench_") as td:
            work = Path(td)
            (work / "prog.py").write_text(program, encoding="utf-8")
            res = SandboxRunner().run(RunRequest(
                tool="python3", args=["prog.py"], workdir=str(work),
                image="python:3.12-alpine", timeout=timeout))
    except Exception as e:
        return False, f"sandbox unavailable: {e}"
    if res.timed_out:
        return False, "timed out"
    if res.code == 0:
        return True, ""
    tail = (res.stderr or res.stdout or "").strip().splitlines()
    return False, (tail[-1][:160] if tail else f"exit {res.code}")


def propose_tests(problem: dict, model: str) -> list:
    """Ask the model for assertions the solution must satisfy.

    Parsel's HumanEval gain (67 -> 85) came with AUTOMATICALLY generated tests,
    so this is the same protocol: the planner writes the checks, the OFFICIAL
    hidden tests still judge the result. Honest risk, which the report measures:
    a wrong self-generated check pushes the model AWAY from the right answer.
    """
    from ai_callers import make_lmstudio_caller, make_ollama_caller
    caller = (make_lmstudio_caller(model=model) if "/" in model
              else make_ollama_caller(model=model))
    prompt = (
        "Write 3 to 5 assertions any correct implementation must satisfy.\n"
        "Return ONLY a JSON array of Python expressions that evaluate to True.\n"
        'Example: ["f(2) == 4", "f(0) == 0"]\n'
        "Use the exact function name. No explanation.\n\n"
        + problem["prompt"])
    try:
        raw = caller(prompt)
    except Exception:
        return []
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:])
    import re as _re
    match = _re.search(r"\[.*\]", text, _re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group())
    except Exception:
        return []
    return [str(x) for x in items if isinstance(x, str)][:8] if isinstance(items, list) else []


def cage_rejections(task_id: str, since_line: int) -> int:
    """How often the cage sent this task back — read from the agent's own log."""
    log = ROOT / "ai-mind" / "logs" / "vox.log"
    if not log.exists():
        return 0
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[since_line:]
    return sum(1 for ln in lines if task_id in ln and "Cage rejected" in ln)


def log_length() -> int:
    log = ROOT / "ai-mind" / "logs" / "vox.log"
    if not log.exists():
        return 0
    return len(log.read_text(encoding="utf-8", errors="replace").splitlines())


def bench(n: int, model: str, with_acceptance: bool = False) -> dict:
    from agent import HDSAgent

    problems = load_problems(n)
    agent = HDSAgent()
    results = []
    t0 = time.time()

    for i, p in enumerate(problems, 1):
        tid = p["task_id"].replace("/", "_")
        fname = f"{tid}.py"
        mark = log_length()
        start = time.time()

        # The prompt IS the specification: signature + docstring, nothing added.
        instruction = (
            "Implement this Python function completely. Output the whole file: "
            "the imports it needs, the function signature exactly as given, and "
            "a working body.\n\n" + p["prompt"])
        checks = propose_tests(p, model) if with_acceptance else []
        try:
            written = agent._execute_ai_task(
                task_id=f"BENCH-{tid}", instruction=instruction, model_name=model,
                output_dir=OUT_DIR, output_filename=fname,
                acceptance_tests=checks)
        except Exception as e:
            written, err = False, str(e)[:120]
        else:
            err = "" if written else "pipeline gave up"

        passed, detail = False, err
        if written:
            path = ROOT / OUT_DIR / fname
            if path.exists():
                passed, detail = run_official_test(path.read_text(encoding="utf-8"), p)
            else:
                detail = "reported success but wrote nothing"

        row = {"task_id": p["task_id"], "written": bool(written), "passed": passed,
               "cage_rejections": cage_rejections(f"BENCH-{tid}", mark),
               "declared_checks": len(checks),
               "seconds": round(time.time() - start, 1), "detail": detail}
        results.append(row)
        flag = "PASS" if passed else ("FAIL" if written else "NOWRITE")
        print(f"[{i:>3}/{len(problems)}] {flag:<7} {p['task_id']:<16} "
              f"{row['seconds']:>5}s  rej={row['cage_rejections']}  {detail[:60]}")

    return summarise(results, model, time.time() - t0)


def summarise(results: list, model: str, elapsed: float) -> dict:
    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    written = sum(1 for r in results if r["written"])
    rejections = sum(r["cage_rejections"] for r in results)
    report = {
        "model": model, "n": n,
        "pass_at_1": round(100.0 * passed / n, 1) if n else 0.0,
        "written": written, "passed": passed,
        "written_but_wrong": written - passed,
        "never_written": n - written,
        "cage_rejections_total": rejections,
        "seconds_total": round(elapsed, 1),
        "seconds_per_task": round(elapsed / n, 1) if n else 0.0,
        "results": results,
    }
    print("\n" + "=" * 56)
    print(f"  MODEL            : {model}")
    print(f"  PASS@1           : {passed}/{n} = {report['pass_at_1']}%")
    print(f"  written but wrong: {report['written_but_wrong']}"
          f"   (cage passed it, the test did not)")
    print(f"  never written    : {report['never_written']}"
          f"   (pipeline gave up)")
    print(f"  cage rejections  : {rejections} across {n} tasks")
    print(f"  time             : {report['seconds_total']}s"
          f"  ({report['seconds_per_task']}s/task)")
    print("=" * 56)
    return report


def main():
    ap = argparse.ArgumentParser(description="HDS generation benchmark")
    ap.add_argument("--n", type=int, default=100, help="how many problems")
    ap.add_argument("--model", default="", help="model hint; HDS binds it to what is served")
    ap.add_argument("--acceptance", action="store_true",
                    help="model declares checks and the build is gated on them "
                         "(Parsel protocol); official tests still judge")
    ap.add_argument("--out", default="storage/bench/report.json")
    args = ap.parse_args()

    report = bench(args.n, args.model, with_acceptance=args.acceptance)
    import scribe
    scribe.execute({"op": "write", "path": args.out,
                    "content": json.dumps(report, indent=2)}, protocol_size=None)
    print(f"report -> {args.out}")


if __name__ == "__main__":
    main()
