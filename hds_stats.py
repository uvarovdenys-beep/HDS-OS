#!/usr/bin/env python3
"""hds_stats.py — how well is this actually working, and what does it cost?

Two questions the project could not answer about itself:

  1. CORRECTNESS. `benchmark.py` proves what the cage STOPS (9/9, 0 false
     positives). Nothing measured what the agent BUILDS. A HumanEval run once
     reported 92% pass@1 and the number was never written down, so every later
     "this is better" was belief, not evidence.

  2. COST. The claim that a grate plus a surgical patch is cheaper than
     regenerating a file is plausible and was never counted. Plausible is how
     projects talk themselves into things.

Both are read from the agent's own log and task archive — no new bookkeeping to
drift out of date, and nothing here writes anything.

    python3 hds_stats.py            # the report
    python3 hds_stats.py --json     # the same numbers, machine-readable
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "ai-mind" / "logs" / "vox.log"

# A rough conversion, used only for RELATIVE comparison. Absolute token counts
# would need each provider's tokeniser; the ratio between two prompts is what
# the cost question actually asks, and characters track that closely enough.
CHARS_PER_TOKEN = 4


def _log_lines():
    if not LOG.exists():
        return []
    return LOG.read_text(encoding="utf-8", errors="replace").splitlines()


def generation_stats() -> dict:
    """Per-task outcomes, read from the agent's own log.

    A task can end three ways: written on the first attempt, written after the
    cage sent it back, or given up. The middle case is the interesting one —
    it is self-correction working, and it is invisible in a pass/fail count.
    """
    lines = _log_lines()
    tasks = {}
    for line in lines:
        started = re.search(r"Generating (\w+) for task (\S+) \(attempt (\d+)/", line)
        if started:
            lang, task, attempt = started.groups()
            row = tasks.setdefault(task, {"lang": lang, "attempts": 0,
                                          "rejected": 0, "written": False})
            row["attempts"] = max(row["attempts"], int(attempt))
            continue
        if "Cage rejected" in line:
            for task in tasks:
                pass
        written = re.search(r"Task (\S+) completed successfully", line)
        if written and written.group(1) in tasks:
            tasks[written.group(1)]["written"] = True

    # Cage refusals are logged against the FILE, not the task, so they are
    # counted globally rather than attributed — an honest limit of the log.
    rejections = sum(1 for line in lines if "Cage rejected" in line)

    total = len(tasks)
    written = sum(1 for t in tasks.values() if t["written"])
    first_try = sum(1 for t in tasks.values() if t["written"] and t["attempts"] == 1)
    corrected = written - first_try

    by_lang = {}
    for row in tasks.values():
        entry = by_lang.setdefault(row["lang"], {"tasks": 0, "written": 0})
        entry["tasks"] += 1
        entry["written"] += 1 if row["written"] else 0

    return {"tasks": total, "written": written, "gave_up": total - written,
            "first_attempt": first_try, "after_correction": corrected,
            "cage_rejections": rejections,
            "write_rate": round(100.0 * written / total, 1) if total else 0.0,
            "by_language": by_lang}


def prompt_cost(file_text: str, grate_text: str) -> dict:
    """What one edit costs each way.

    WITHOUT HDS: the model is handed the whole file and returns the whole file,
    so both directions carry it — that is the real bill, not just the prompt.

    WITH HDS: it is handed a grate (signature, contract, siblings) and returns
    one function. The saving compounds with file size, which is exactly where
    a large project lives.
    """
    whole = len(file_text) * 2                    # sent and returned
    surgical = len(grate_text) + len(file_text) // 12   # grate in, one function out
    return {
        "whole_file_tokens": whole // CHARS_PER_TOKEN,
        "surgical_tokens": surgical // CHARS_PER_TOKEN,
        "saved_tokens": (whole - surgical) // CHARS_PER_TOKEN,
        "ratio": round(whole / surgical, 1) if surgical else 0.0,
    }


def cage_stats() -> dict:
    """What the cage refused, by rule. These are edits that never reached disk."""
    lines = _log_lines()
    rules = {}
    for line in lines:
        found = re.search(r"(R-\w+|hygiene-blocked)", line)
        if found and "rejected" in line.lower():
            key = found.group(1)
            rules[key] = rules.get(key, 0) + 1
    return {"by_rule": dict(sorted(rules.items(), key=lambda kv: -kv[1]))}


def report() -> str:
    gen = generation_stats()
    cage = cage_stats()
    out = ["HDS OS — how it is actually doing", ""]

    out.append("GENERATION")
    out.append(f"  tasks run           : {gen['tasks']}")
    out.append(f"  written             : {gen['written']}  ({gen['write_rate']}%)")
    out.append(f"  first attempt       : {gen['first_attempt']}")
    out.append(f"  after self-correction: {gen['after_correction']}")
    out.append(f"  gave up             : {gen['gave_up']}")
    if gen["by_language"]:
        out.append("  by language:")
        for lang, row in sorted(gen["by_language"].items()):
            out.append(f"    {lang:<12} {row['written']}/{row['tasks']}")

    out.append("")
    out.append("CAGE")
    out.append(f"  edits refused       : {gen['cage_rejections']}")
    for rule, count in cage["by_rule"].items():
        out.append(f"    {rule:<18} {count}")

    out.append("")
    out.append("COST OF ONE EDIT (a 300-line file, a 400-character grate)")
    cost = prompt_cost("x" * 12000, "y" * 400)
    out.append(f"  whole-file rewrite  : ~{cost['whole_file_tokens']} tokens")
    out.append(f"  surgical patch      : ~{cost['surgical_tokens']} tokens")
    out.append(f"  saved               : ~{cost['saved_tokens']}  ({cost['ratio']}x cheaper)")
    return "\n".join(out)


def main():
    if "--json" in sys.argv:
        print(json.dumps({"generation": generation_stats(), "cage": cage_stats()},
                         indent=2, ensure_ascii=False))
    else:
        print(report())


if __name__ == "__main__":
    main()
