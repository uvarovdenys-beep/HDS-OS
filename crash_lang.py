#!/usr/bin/env python3
"""Crash test: 10 real generation tasks per compiled language, through the agent.

`benchmark.py` measures the cage against hand-written payloads. `bench_generation`
measures Python. Neither touches C, C++ or C#, and those three are the languages
whose validators call a real compiler — so a failure there is a failure nobody
would otherwise see.

Each task goes through the FULL pipeline: model resolution, generation, the cage
(hygiene + clang/dotnet syntax check), self-correction. What is measured:

  written  — survived the cage
  rejected — how many attempts the cage sent back before it did
  gave up  — the pipeline exhausted its attempts

A high rejection count with a high write count is the good outcome: it means the
cage is catching bad output AND the model is correcting from the verdict.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT / "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)

TASKS = [
    "a function that merges two sorted integer arrays into one sorted array",
    "a function that counts how many times each character appears in a string",
    "a function that validates whether brackets in a string are balanced: (), [] and {}",
    "a function that performs binary search over a sorted array, returning the index or -1",
    "a function that converts a roman numeral string to its integer value",
    "a function that finds the length of the longest run of consecutive equal values",
    "a function that computes the edit distance between two strings",
    "a function that returns the intersection of two arrays without duplicates",
    "a function that reverses the order of words in a sentence",
    "a function that parses a 'key=value' line and returns key and value, trimmed",
]

LANGS = {
    "c":   (".c",   "C",   "Plain C11. Include the headers you use. No main(). "
                           "Take array lengths as explicit parameters. "
                           "No system(), fork(), popen() or inline assembly."),
    "cpp": (".cpp", "C++", "C++17. Use std::vector and std::string where natural. "
                           "Include the headers you use. No main(). "
                           "No system(), exec*(), popen() or inline assembly."),
    "cs":  (".cs",  "C#",  "C#. Put the function in a public static class. "
                           "No Process.Start, no System.Diagnostics."),
    "py":  (".py",  "Python", "Python 3 with type hints. Standard library only. "
                              "No eval, exec or subprocess."),
    "js":  (".js",  "JavaScript", "Node-style JavaScript. Export with "
                                  "module.exports. No eval, no child_process."),
    "ts":  (".ts",  "TypeScript", "TypeScript with explicit parameter and return "
                                  "types. Export the function. No any."),
    "sh":  (".sh",  "Bash", "A bash function. Start the file with #!/bin/bash. "
                            "No rm -rf, no eval, no sudo, no curl piped to a shell."),
    "rb":  (".rb",  "Ruby", "Plain Ruby, no gems. No backticks, no system(), no eval."),
    "php": (".php", "PHP",  "PHP 8 with a declared function. Start with <?php. "
                            "No exec, no shell_exec, no eval."),
    "java":(".java","Java", "A public class holding one public static method. "
                            "No Runtime.exec, no ProcessBuilder, no reflection."),
}

def run(lang_key: str, model: str, limit: int = 10) -> dict:
    from agent import HDSAgent
    ext, name, rules = LANGS[lang_key]
    agent = HDSAgent()
    rows = []

    for i, task in enumerate(TASKS[:limit], 1):
        tid = f"CRASH-{lang_key}-{i}"
        mark = _log_len()
        t0 = time.time()
        try:
            ok = agent._execute_ai_task(
                task_id=tid,
                instruction=(f"Write {name}: {task}.\n{rules}\n"
                             f"Output only the code — no explanation, no markdown."),
                model_name=model,
                output_dir=f"storage/crash/{lang_key}",
                output_filename=f"t{i}{ext}")
        except Exception as e:
            ok, err = False, str(e)[:70]
        else:
            err = "" if ok else "pipeline gave up"
        rows.append({"task": i, "written": bool(ok),
                     "rejected": _rejections(tid, mark),
                     "seconds": round(time.time() - t0, 1), "detail": err})
        flag = "OK " if ok else "GAVE UP"
        print(f"  [{i:>2}/{limit}] {flag} {rows[-1]['seconds']:>5}s  "
              f"cage-rejects={rows[-1]['rejected']}  {err[:44]}")
    return {"lang": name, "rows": rows}


def _log_len() -> int:
    log = ROOT / "ai-mind" / "logs" / "vox.log"
    try:
        return len(log.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def _rejections(task_id: str, since: int) -> int:
    """Count cage refusals in this task's slice of the log.

    Deliberately NOT keyed on task_id: the cage logs the FILENAME it refused
    ("Cage rejected ... t7.c failed clang"), never the task. Matching on the id
    silently returned 0 for every task and made the whole column useless. Tasks
    run one at a time, so the line window is the task.
    """
    log = ROOT / "ai-mind" / "logs" / "vox.log"
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[since:]
    except OSError:
        return 0
    return sum(1 for ln in lines if "Cage rejected" in ln)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(LANGS), required=True)
    ap.add_argument("--model", default="qwen/qwen2.5-coder-14b")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    print(f"═══ {LANGS[args.lang][1]} — {args.n} задач, модель {args.model} ═══")
    report = run(args.lang, args.model, args.n)
    rows = report["rows"]
    written = sum(1 for r in rows if r["written"])
    rejects = sum(r["rejected"] for r in rows)
    secs = sum(r["seconds"] for r in rows)
    print(f"\n  {report['lang']}: записано {written}/{len(rows)} | "
          f"відмов кейджа {rejects} | {round(secs)}s "
          f"({round(secs/max(1,len(rows)),1)}s/задача)")


if __name__ == "__main__":
    main()
