#!/usr/bin/env python3
"""
conductor.py
HDS Conductor — automatic task distribution across protocol sizes.

IMPORTANT: This is NOT a multi-model pipeline. Only ONE model runs at a time.
The conductor assigns different protocol contexts (XL/L/M/S boot prompts,
rules, and limits) to the SAME model depending on task complexity.

Think of it as "mode switching" — the model wears different hats.
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

from model_router import ProtocolSize, classify_model, get_model_profile, adapt_task, get_boot_prompt

logger = logging.getLogger("conductor")


@dataclass
class TaskSpec:
    """A task specification for the conductor."""
    task_id: str
    description: str
    complexity: int  # 1-10
    target_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # task_ids this depends on
    estimated_lines: int = 0
    status: str = "pending"  # pending, running, completed, failed, blocked
    assigned_size: Optional[ProtocolSize] = None
    result: Optional[Dict] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class Conductor:
    """
    Orchestrates task execution using a SINGLE model with different protocol contexts.

    Flow:
    1. User submits an idea/goal
    2. Conductor classifies the current model
    3. If model is XL-capable: decompose idea into sub-tasks
    4. Route each sub-task to appropriate protocol size (context/rules)
    5. Execute tasks sequentially (one at a time, same model)
    6. Verify results after each task
    7. Report back
    """

    def __init__(self, model_name: str, ai_call_fn=None):
        self.model_name = model_name
        self.ai_call_fn = ai_call_fn
        self.model_size, self.model_context = classify_model(model_name)
        self.task_queue: List[TaskSpec] = []
        self.completed: List[TaskSpec] = []
        self.failed: List[TaskSpec] = []
        self._log_path = Path("ai-mind/tasks/conductor_log.json")

    def estimate_complexity(self, description: str) -> int:
        """Estimate task complexity from description (1-10)."""
        # Heuristic-based estimation
        complexity = 3  # default

        high_markers = ["architecture", "redesign", "refactor entire", "create system", "decompose"]
        medium_markers = ["create module", "implement", "integrate", "test suite", "refactor"]
        low_markers = ["fix typo", "add import", "rename", "copy", "update config"]

        desc_lower = description.lower()
        for marker in high_markers:
            if marker in desc_lower:
                complexity = max(complexity, 8)
        for marker in medium_markers:
            if marker in desc_lower:
                complexity = max(complexity, 5)
        for marker in low_markers:
            if marker in desc_lower:
                complexity = min(complexity, 3)

        return complexity

    def assign_protocol_size(self, task: TaskSpec) -> ProtocolSize:
        """Determine which protocol size context to use for a task."""
        # Map complexity to minimum required size
        if task.complexity >= 8:
            required = ProtocolSize.XL
        elif task.complexity >= 5:
            required = ProtocolSize.L
        elif task.complexity >= 3:
            required = ProtocolSize.M
        else:
            required = ProtocolSize.S

        # Can't assign higher than model's capability
        size_order = [ProtocolSize.S, ProtocolSize.M, ProtocolSize.L, ProtocolSize.XL]
        model_idx = size_order.index(self.model_size)
        required_idx = size_order.index(required)

        if required_idx > model_idx:
            # Task too complex for this model — assign max capability
            logger.warning(
                f"Task '{task.task_id}' requires {required.value.upper()} "
                f"but model only supports {self.model_size.value.upper()}"
            )
            return self.model_size

        return required

    def add_task(self, task_id: str, description: str, complexity: int = 0,
                 target_files: List[str] = None, dependencies: List[str] = None,
                 estimated_lines: int = 0) -> TaskSpec:
        """Add a task to the queue."""
        if complexity == 0:
            complexity = self.estimate_complexity(description)

        task = TaskSpec(
            task_id=task_id,
            description=description,
            complexity=complexity,
            target_files=target_files or [],
            dependencies=dependencies or [],
            estimated_lines=estimated_lines,
        )
        task.assigned_size = self.assign_protocol_size(task)
        self.task_queue.append(task)

        logger.info(
            f"Task '{task_id}' added: complexity={complexity}, "
            f"assigned={task.assigned_size.value.upper()}"
        )
        return task

    def get_execution_order(self) -> List[TaskSpec]:
        """Sort tasks by dependencies and complexity (high first)."""
        # Simple topological sort
        ordered = []
        remaining = list(self.task_queue)
        completed_ids = {t.task_id for t in self.completed}

        max_iterations = len(remaining) * 2
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            for task in remaining[:]:
                deps_met = all(
                    d in completed_ids or d in {t.task_id for t in ordered}
                    for d in task.dependencies
                )
                if deps_met:
                    ordered.append(task)
                    remaining.remove(task)

        if remaining:
            logger.warning(f"Circular dependencies detected for: {[t.task_id for t in remaining]}")
            ordered.extend(remaining)

        return ordered

    def build_task_prompt(self, task: TaskSpec) -> str:
        """Build the full prompt for executing a task with appropriate protocol context."""
        boot = get_boot_prompt(self.model_name)
        adapted = adapt_task(
            {"description": task.description, "complexity": task.complexity},
            self.model_name
        )

        prompt = f"{boot}\n\n---\n\nTASK: {task.task_id}\n{adapted}"

        if task.target_files:
            prompt += f"\n\nTarget files: {', '.join(task.target_files)}"

        return prompt

    def execute_task(self, task: TaskSpec) -> Dict:
        """Execute a single task using the AI with appropriate protocol context."""
        if not self.ai_call_fn:
            return {"success": True, "result": "No AI function — dry run", "task_id": task.task_id}

        task.status = "running"
        prompt = self.build_task_prompt(task)

        try:
            response = self.ai_call_fn(prompt)
            task.status = "completed"
            task.result = {"response": response}
            self.completed.append(task)
            return {"success": True, "result": response, "task_id": task.task_id}
        except Exception as e:
            task.status = "failed"
            task.result = {"error": str(e)}
            self.failed.append(task)
            return {"success": False, "error": str(e), "task_id": task.task_id}

    def execute_all(self) -> Dict:
        """Execute all queued tasks in dependency order."""
        order = self.get_execution_order()
        results = []

        logger.info(f"Executing {len(order)} tasks for model {self.model_name} ({self.model_size.value.upper()})")

        for task in order:
            logger.info(f"Executing task '{task.task_id}' with {task.assigned_size.value.upper()} context")
            result = self.execute_task(task)
            results.append(result)

            if not result["success"]:
                logger.error(f"Task '{task.task_id}' failed: {result.get('error')}")
                # Check if any pending tasks depend on this
                blocked = [t for t in self.task_queue if task.task_id in t.dependencies]
                for bt in blocked:
                    bt.status = "blocked"
                    logger.warning(f"Task '{bt.task_id}' blocked due to '{task.task_id}' failure")

        self.task_queue = [t for t in self.task_queue if t.status == "pending"]

        report = {
            "model": self.model_name,
            "model_size": self.model_size.value.upper(),
            "total_tasks": len(order),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "blocked": len([t for t in order if t.status == "blocked"]),
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

        self._save_log(report)
        return report

    def _save_log(self, report: Dict):
        """Save execution log."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Failed to save conductor log: {e}")

    def get_status(self) -> Dict:
        """Get current conductor status."""
        return {
            "model": self.model_name,
            "model_size": self.model_size.value.upper(),
            "queued": len(self.task_queue),
            "completed": len(self.completed),
            "failed": len(self.failed),
        }


# CLI demo
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("HDS CONDUCTOR — Task Distribution Demo")
    print("=" * 60)

    conductor = Conductor("qwen3.5:9b")

    # Add sample tasks
    conductor.add_task("T-001", "Fix typo in README", complexity=1)
    conductor.add_task("T-002", "Create test module for auth system", complexity=6,
                       target_files=["tests/test_auth.py"])
    conductor.add_task("T-003", "Add import for logging in agent.py", complexity=2,
                       target_files=["agent/agent.py"])
    conductor.add_task("T-004", "Implement vision daemon error handling", complexity=7,
                       target_files=["agent/vision_daemon_real.py"],
                       dependencies=["T-003"])

    # Show execution plan
    order = conductor.get_execution_order()
    print("\nExecution Plan:")
    for i, task in enumerate(order, 1):
        print(f"  {i}. [{task.assigned_size.value.upper()}] {task.task_id}: {task.description}")

    # Dry run
    report = conductor.execute_all()
    print(f"\nResults: {report['completed']}/{report['total_tasks']} completed")
    print(f"Status: {conductor.get_status()}")
