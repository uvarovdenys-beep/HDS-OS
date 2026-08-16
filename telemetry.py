#!/usr/bin/env python3
"""telemetry.py — structured events, so nothing has to grep a human log.

hds_failures parsed vox.log with regexes: change a word in vox.speak and the
taxonomy silently breaks. This writes one JSON object per line instead —
task_id, stage, verdict, ms — which is both a stable analytics source and the
live `stage` the console rail needs for its verification lanes.

Append-only JSONL. Best-effort: telemetry must never break a build.
"""
import json
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent / "ai-mind" / "logs" / "events.jsonl"

STAGES = ("generate", "cage", "acceptance", "montecarlo", "written", "gave_up")
VERDICTS = ("ok", "fail", "start")


def record(task_id: str, stage: str, verdict: str = "ok", ms: int = 0, **extra):
    """Append one event. Never raises."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        row = {"t": round(time.time(), 3), "task_id": task_id, "stage": stage,
               "verdict": verdict, "ms": int(ms)}
        row.update({k: v for k, v in extra.items() if v is not None})
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def events(path=None) -> list:
    """Every recorded event, oldest first. Malformed lines are skipped."""
    p = Path(path) if path else LOG
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def stage_report(evts) -> dict:
    """
    Build and return a dict mapping each stage seen to a counts dict.
    
    For every event: if verdict == 'ok' increment result[stage]['ok'];
    if verdict == 'fail' increment result[stage]['fail']; ignore any other
    verdict (such as 'start') entirely. A stage key appears ONLY if it got at
    least one ok or fail. Every counts dict must contain BOTH keys 'ok' and
    'fail' (use 0 when absent). Skip events missing 'stage' or 'verdict'.
    
    Parameters:
        evts (list of dict): A list of events, each with keys 'stage' and 'verdict'.
    
    Returns:
        dict: A dictionary mapping each stage to a counts dictionary with 'ok' and 'fail'.
    """
    result = {}
    
    for evt in evts:
        if 'stage' not in evt or 'verdict' not in evt:
            continue
        
        stage = evt['stage']
        verdict = evt['verdict']
        
        if verdict not in ('ok', 'fail'):
            continue
        
        if stage not in result:
            result[stage] = {'ok': 0, 'fail': 0}
        
        result[stage][verdict] += 1
    
    return result


def current_stage(task_id: str, evts) -> dict:
    """
    Return a dictionary describing the live state of a task with the given task_id.

    Parameters:
        task_id (str): The ID of the task to check.
        evts (list): A list of event dictionaries, each containing 'task_id', 'stage', and 'verdict'.

    Returns:
        dict: A dictionary with keys 'stage', 'verdict', and 'stages'.
    """
    last_stage = ''
    last_verdict = ''
    stages = {}

    for evt in evts:
        if evt['task_id'] == task_id:
            last_stage = evt['stage']
            last_verdict = evt['verdict']
            stages[evt['stage']] = evt['verdict']

    return {
        'stage': last_stage,
        'verdict': last_verdict,
        'stages': stages
    }


def main():
    evts = events()
    rep = stage_report(evts)
    print("HDS — stages (from structured telemetry)")
    if not rep:
        print("  (no events yet — run a task)")
        return
    for stage in STAGES:
        row = rep.get(stage)
        if not row:
            continue
        ok, bad = row.get("ok", 0), row.get("fail", 0)
        total = ok + bad
        rate = (100.0 * ok / total) if total else 0.0
        print(f"  {stage:12s} ok {ok:5d}  fail {bad:5d}   {rate:5.1f}% pass")


if __name__ == "__main__":
    main()
