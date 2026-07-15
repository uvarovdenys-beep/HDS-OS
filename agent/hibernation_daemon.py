#!/usr/bin/env python3
"""
hibernation_daemon.py
HDS6 TKT-003d: Hibernation Daemon for Background Tasks

Allows running long tasks in background without blocking the main agent.
Main loop does not wait — task runs in parallel.

Authors: HDS6 Development Team
License: HDS6 Standard
"""

import threading
import time
import json
from pathlib import Path
from typing import Dict, Callable, Optional
from enum import Enum
from datetime import datetime


class TaskStatus(Enum):
    """Background task states."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HibernationDaemon:
    """
    Executes long-running tasks in a background thread.
    Core can continue working without waiting for completion.
    """

    def __init__(self, state_dir: Path = None):
        self.state_dir = state_dir or Path(__file__).parent.parent / "ai-mind" / "tasks" / "background"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        print(f"[HibernationDaemon] Initialized. State dir: {self.state_dir}")

    def spawn_task(
        self,
        task_id: str,
        task_func: Callable,
        args: tuple = (),
        kwargs: dict = None,
    ) -> bool:
        """
        Launches task in a background thread.
        Does not wait for completion.
        """
        kwargs = kwargs or {}

        try:
            with self._lock:
                # Check if task already exists
                if task_id in self.tasks:
                    print(f"[HibernationDaemon] Task {task_id} already exists")
                    return False

                # Register task
                self.tasks[task_id] = {
                    "status": TaskStatus.QUEUED.value,
                    "created_at": datetime.now().isoformat(),
                    "started_at": None,
                    "completed_at": None,
                    "result": None,
                    "error": None,
                }

                self._save_state(task_id)

            # Launch in background thread
            thread = threading.Thread(
                target=self._run_task,
                args=(task_id, task_func, args, kwargs),
                daemon=False,  # Track completion
                name=f"hibernation-{task_id}",
            )
            thread.start()

            print(f"[HibernationDaemon] ✓ Spawned task {task_id}")
            return True
        except Exception as e:
            print(f"[HibernationDaemon ERROR] Failed to spawn {task_id}: {e}")
            return False

    def _run_task(
        self,
        task_id: str,
        task_func: Callable,
        args: tuple,
        kwargs: dict,
    ):
        """Execute task in background thread."""
        try:
            with self._lock:
                self.tasks[task_id]["status"] = TaskStatus.RUNNING.value
                self.tasks[task_id]["started_at"] = datetime.now().isoformat()
                self._save_state(task_id)

            # Execute task
            result = task_func(*args, **kwargs)

            with self._lock:
                self.tasks[task_id]["status"] = TaskStatus.COMPLETED.value
                self.tasks[task_id]["result"] = str(result)
                self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
                self._save_state(task_id)

            print(f"[HibernationDaemon] ✓ Task {task_id} completed")
        except Exception as e:
            with self._lock:
                self.tasks[task_id]["status"] = TaskStatus.FAILED.value
                self.tasks[task_id]["error"] = str(e)
                self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
                self._save_state(task_id)

            print(f"[HibernationDaemon] ✗ Task {task_id} failed: {e}")

    def check_status(self, task_id: str) -> Optional[Dict]:
        """Check task status."""
        with self._lock:
            return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel task (if not already running)."""
        try:
            with self._lock:
                if task_id not in self.tasks:
                    return False

                task = self.tasks[task_id]
                if task["status"] == TaskStatus.QUEUED.value:
                    task["status"] = TaskStatus.CANCELLED.value
                    self._save_state(task_id)
                    print(f"[HibernationDaemon] Cancelled {task_id}")
                    return True
                else:
                    print(
                        f"[HibernationDaemon] Cannot cancel {task_id} "
                        f"(status: {task['status']})"
                    )
                    return False
        except Exception as e:
            print(f"[HibernationDaemon ERROR] Failed to cancel {task_id}: {e}")
            return False

    def _save_state(self, task_id: str):
        """Save task state to disk."""
        try:
            task = self.tasks[task_id]
            state_file = self.state_dir / f"{task_id}.json"
            with open(state_file, "w") as f:
                json.dump(task, f, indent=2)
        except Exception as e:
            print(f"[HibernationDaemon WARNING] Could not save state: {e}")

    def get_all_tasks(self) -> Dict[str, Dict]:
        """Returns all tasks."""
        with self._lock:
            return dict(self.tasks)

    def cleanup_completed(self) -> int:
        """Remove completed tasks older than 1 hour."""
        now = datetime.now()
        removed = 0

        with self._lock:
            for task_id in list(self.tasks.keys()):
                task = self.tasks[task_id]
                if task["status"] in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
                    if task.get("completed_at"):
                        completed = datetime.fromisoformat(task["completed_at"])
                        age = (now - completed).total_seconds()
                        if age > 3600:  # 1 hour
                            del self.tasks[task_id]
                            removed += 1

        print(f"[HibernationDaemon] Cleaned up {removed} old tasks")
        return removed

    def export_report(self) -> str:
        """Export report on background tasks."""
        tasks = self.get_all_tasks()

        report = "HIBERNATION DAEMON REPORT\n"
        report += "=" * 60 + "\n\n"

        status_counts = {}
        for task in tasks.values():
            status = task.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        report += "Task Status Summary:\n"
        for status, count in status_counts.items():
            report += f"  {status}: {count}\n"

        report += "\nRunning Tasks:\n"
        for task_id, task in tasks.items():
            if task["status"] == TaskStatus.RUNNING.value:
                report += f"  - {task_id} (started {task.get('started_at', 'unknown')})\n"

        return report
