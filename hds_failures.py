#!/usr/bin/env python3
"""hds_failures.py — WHY generations fail, per category.

hds_stats counts pass/fail; this classifies each failed attempt by REASON from
the agent's own log (cage / acceptance / monte_carlo / timeout / refused /
gave_up), so "improve the numbers" has a target instead of a guess.
"""
from collections import Counter
from pathlib import Path

LOG = Path(__file__).resolve().parent / "ai-mind" / "logs" / "vox.log"


def classify_failure_line(line: str) -> str:
    """
    Classify the failure category based on the log line.

    Parameters:
        line (str): The log line to classify.

    Returns:
        str: The failure category or an empty string if no match is found.
    """
    if 'Cage rejected' in line:
        return 'cage'
    elif 'code rejected (' in line:
        return 'cage'
    elif 'Acceptance failed' in line:
        return 'acceptance'
    elif 'Monte Carlo failed' in line:
        return 'monte_carlo'
    elif 'hung >deadline' in line:
        return 'timeout'
    elif 'refused task' in line:
        return 'refused'
    elif 'self-correct attempts' in line:
        return 'gave_up'
    else:
        return ''


def attribute_giveups(lines) -> dict:
    """
    Scan `lines` IN ORDER, tracking the most recent REAL failure cause.
    When classify_failure_line(line) == 'gave_up', add 1 to a result dict under
    the last cause seen, or under 'unknown' if no cause was seen yet, then reset
    the last cause to None.
    Return the dict {cause: count}.
    """
    result = {}
    last_cause = None

    for line in lines:
        cause = classify_failure_line(line)
        if cause == 'gave_up':
            if last_cause:
                result[last_cause] = result.get(last_cause, 0) + 1
            else:
                result['unknown'] = result.get('unknown', 0) + 1
            last_cause = None
        elif cause in ['cage', 'acceptance', 'monte_carlo', 'timeout', 'refused']:
            last_cause = cause

    return result


def failure_report(lines):
    """Count failure lines by category."""
    counts = Counter()
    for line in lines:
        cat = classify_failure_line(line)
        if cat:
            counts[cat] += 1
    return dict(counts)


def main():
    lines = LOG.read_text(encoding="utf-8", errors="ignore").splitlines() if LOG.exists() else []
    report = failure_report(lines)
    total = sum(report.values())
    print("HDS — failures by reason")
    for cat, n in sorted(report.items(), key=lambda kv: kv[1], reverse=True):
        pct = (100.0 * n / total) if total else 0.0
        print(f"  {cat:14s} {n:6d}  {pct:5.1f}%")
    print(f"  {'total':14s} {total:6d}")

    giveups = attribute_giveups(lines)
    if giveups:
        gt = sum(giveups.values())
        print("\nGive-ups by last cause")
        for cat, n in sorted(giveups.items(), key=lambda kv: kv[1], reverse=True):
            print(f"  {cat:14s} {n:6d}  {100.0 * n / gt:5.1f}%")


if __name__ == "__main__":
    main()
