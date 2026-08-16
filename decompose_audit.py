#!/usr/bin/env python3
"""decompose_audit.py — R-300 as a SCRIPT, not a sentence in a document.

A rule written in prose is a rule an AI can ignore. This one is executable:
new code over 300 lines fails the audit, and files already over it may not
grow. Existing debt is frozen in a baseline and can only shrink — a ratchet.

    decompose_audit.py            # check (exit 1 on violation)
    decompose_audit.py --freeze   # accept the current state as the baseline
    decompose_audit.py --debt     # list the baselined files, largest first

R-01 (1000 lines) remains the cage's hard ceiling in scribe. R-300 is the
working rule: one class per file, functions grouped by a single concrete task.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE_FILE = ROOT / "ai-mind" / "config" / "decompose_baseline.json"
LIMIT = 300

SKIP_PARTS = (".archive", "__pycache__", ".git", "storage", "ai-mind", "gui")


def _tracked():
    """Every OS Python file the rule applies to, as {relpath: line count}."""
    out = {}
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if any(part in rel.split("/") for part in SKIP_PARTS):
            continue
        try:
            out[rel] = sum(1 for _ in py.open("r", encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return out


def main():
    sizes = _tracked()
    over = {p: n for p, n in sizes.items() if n > LIMIT}

    if "--freeze" in sys.argv:
        BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(over, indent=2, sort_keys=True))
        print("frozen %d oversized file(s) as existing debt -> %s"
              % (len(over), BASELINE_FILE.name))
        return 0

    baseline = {}
    if BASELINE_FILE.exists():
        baseline = json.loads(BASELINE_FILE.read_text())

    if "--debt" in sys.argv:
        for p, n in sorted(baseline.items(), key=lambda kv: -kv[1]):
            print("  %5d  %s" % (n, p))
        print("%d file(s) awaiting decomposition" % len(baseline))
        return 0

    new = {p: n for p, n in over.items() if p not in baseline}
    grew = {p: (baseline[p], n) for p, n in over.items()
            if p in baseline and n > baseline[p]}

    if new or grew:
        print("R-300 violation - decompose before committing:")
        for p, n in sorted(new.items(), key=lambda kv: -kv[1]):
            print("   NEW  %5d lines  %s" % (n, p))
        for p, (was, now) in sorted(grew.items(), key=lambda kv: -kv[1][1]):
            print("  GREW  %5d -> %5d  %s" % (was, now, p))
        print("\nOne class per file; group functions by a single concrete task.")
        print("If a split is genuinely impossible, run --freeze deliberately.")
        return 1

    shrunk = sum(1 for p, n in baseline.items()
                 if p not in sizes or sizes.get(p, 0) <= LIMIT)
    msg = "R-300 OK - %d file(s) of debt, none new, none grown" % len(baseline)
    if shrunk:
        msg += " (%d resolved since baseline)" % shrunk
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
