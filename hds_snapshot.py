#!/usr/bin/env python3
"""hds_snapshot.py — pin the numbers to a release, so "better" stops being a belief.

hds_stats and hds_failures report the CURRENT log. Nothing kept the number from
one release to the next, so any claim of improvement rested on memory. This
appends one row per snapshot to a history file and shows the delta against the
previous one.

    python3 hds_snapshot.py              # show history and the latest delta
    python3 hds_snapshot.py --take v1.3.0 --tests 333   # record now
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "ai-mind" / "logs" / "quality_history.jsonl"


def _tests_passing(argv) -> int:
    """Passing test count, supplied by the caller as `--tests N`.

    This file does NOT run pytest. Spawning a process outside sandbox/ is
    forbidden (the cage refused an earlier version of this very file for
    importing subprocess, correctly), so the count comes from whoever already
    ran the suite — CHECK/tests, or CI.
    """
    if "--tests" in argv:
        i = argv.index("--tests")
        if len(argv) > i + 1 and argv[i + 1].isdigit():
            return int(argv[i + 1])
    return 0


def collect(version: str = "", argv=None) -> dict:
    """Every number worth comparing between releases."""
    row = {"t": round(time.time(), 3), "version": version}
    try:
        import hds_stats
        gen = hds_stats.generation_stats()
        row["tasks"] = gen.get("tasks", 0)
        row["written"] = gen.get("written", 0)
        row["write_rate"] = gen.get("write_rate", 0.0)
        row["first_try"] = gen.get("first_try", 0)
    except Exception:
        pass
    try:
        import hds_failures
        lines = (hds_failures.LOG.read_text(encoding="utf-8", errors="ignore")
                 .splitlines() if hds_failures.LOG.exists() else [])
        row["giveups_by_cause"] = hds_failures.attribute_giveups(lines)
    except Exception:
        pass
    try:
        import skill_library
        row["verified_skills"] = len(skill_library.entries())
    except Exception:
        pass
    row["tests"] = _tests_passing(argv or [])
    return row


def history() -> list:
    if not HISTORY.exists():
        return []
    out = []
    for line in HISTORY.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def take(version: str, argv=None) -> dict:
    row = collect(version, argv)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _delta(new: dict, old: dict) -> str:
    if not old:
        return "  (first snapshot — nothing to compare against yet)"
    lines = []
    for key in ("tests", "tasks", "written", "write_rate", "verified_skills"):
        a, b = old.get(key), new.get(key)
        if a is None or b is None:
            continue
        change = b - a
        arrow = "+" if change > 0 else ""
        lines.append(f"  {key:16s} {a} -> {b}   ({arrow}{round(change, 1)})")
    return "\n".join(lines) or "  (no comparable fields)"


def main():
    if "--take" in sys.argv:
        i = sys.argv.index("--take")
        version = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        rows = history()
        row = take(version, sys.argv)
        print(f"snapshot recorded: {version or '(unversioned)'}")
        print(_delta(row, rows[-1] if rows else {}))
        return
    rows = history()
    if not rows:
        print("No snapshots yet. Record one with: hds_snapshot.py --take v1.2.0")
        return
    print("HDS quality history")
    for r in rows:
        print(f"  {r.get('version','?'):10s} tests {r.get('tests',0):4d}  "
              f"written {r.get('written',0):4d}  "
              f"rate {r.get('write_rate',0):5.1f}%  "
              f"skills {r.get('verified_skills',0):3d}")
    if len(rows) > 1:
        print("\nlatest delta")
        print(_delta(rows[-1], rows[-2]))


if __name__ == "__main__":
    main()
