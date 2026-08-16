#!/usr/bin/env python3
"""task_bridge.py — the single way an EXTERNAL client hands work to the agent.

Any front-end (HTTP webhook, MCP server, a future VS Code plugin) submits build
tasks through here, so the enqueue/poll contract lives in ONE place. Duplicating
it per front-end is how the webhook and the agent drifted apart before (the
webhook wrote to results/ while the agent read active/, so external tasks never
ran).

Contract:
    submit(task_data) -> {"task_id", "status", "poll"}
        Build tasks (generate_code / create_project) land in the agent's active
        queue; the running agent then drives them through the FULL pipeline:
        model resolution → canary → language-aware generation → CAGE (scribe)
        → watchdog → quarantine/model-escalation → archive.

    status(task_id) -> {"task_id", "status": queued|running|completed|failed, ...}

The client never writes files itself — it states intent; the cage executes.
"""
import json
import time
from pathlib import Path

TASKS_DIR = Path("ai-mind/tasks")
TASKS_ACTIVE = TASKS_DIR / "active"
COMPLETED_DIR = TASKS_DIR / "completed"
FAILED_DIR = TASKS_DIR / "failed"
RESULTS_DIR = TASKS_DIR / "results"

# Task types that must run through the hardened agent pipeline.
BUILD_TYPES = {"generate_code", "create_project"}


def is_build_task(task_data: dict) -> bool:
    return task_data.get("type") in BUILD_TYPES


def submit(task_data: dict) -> dict:
    """Enqueue a build task for the agent. Returns the queue receipt."""
    task_id = task_data.get("task_id") or f"TASK-{int(time.time()*1000)}"
    task_data["task_id"] = task_id
    TASKS_ACTIVE.mkdir(parents=True, exist_ok=True)
    (TASKS_ACTIVE / f"{task_id}.json").write_text(
        json.dumps(task_data, indent=2), encoding="utf-8")
    return {"task_id": task_id, "status": "queued",
            "message": "Build task routed to the agent cage queue",
            "poll": f"/api/v1/task/{task_id}"}


def status(task_id: str) -> dict:
    """Where is this task? completed/failed/running/queued, else None."""
    done = COMPLETED_DIR / f"{task_id}_RESULT.json"
    if done.exists():
        try:
            return {"task_id": task_id, "status": "completed",
                    "result": json.loads(done.read_text(encoding="utf-8"))}
        except Exception as e:
            return {"task_id": task_id, "status": "completed",
                    "result": {"note": f"unreadable result: {e}"}}
    if (FAILED_DIR / f"{task_id}.json").exists():
        return {"task_id": task_id, "status": "failed",
                "detail": "quarantined after repeated failures "
                          "(model could not satisfy it, or the cage refused it)"}
    if (TASKS_ACTIVE / f"{task_id}.json").exists():
        return {"task_id": task_id, "status": "running"}
    rec = RESULTS_DIR / f"{task_id}.json"
    if rec.exists():
        try:
            return json.loads(rec.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def wait(task_id: str, timeout: int = 600, poll_every: float = 2.0) -> dict:
    """Block until the task reaches a terminal state or the timeout expires.

    For synchronous callers (an MCP tool call is one): the editor asks to build
    and wants the verdict, not a ticket.
    """
    deadline = time.time() + timeout
    last = {"task_id": task_id, "status": "unknown"}
    while time.time() < deadline:
        s = status(task_id)
        if s:
            last = s
            if s.get("status") in ("completed", "failed", "error"):
                return s
        time.sleep(poll_every)
    return {"task_id": task_id, "status": "timeout",
            "detail": f"no terminal state within {timeout}s", "last": last}
