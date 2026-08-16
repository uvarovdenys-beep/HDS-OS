# task_yaml_support.py
# HDS Mixin for YAML task support in HDS

import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional

class YAMLTaskSupportMixin:
    """Adds YAML task support to HDSAgent."""

    def scan_yaml_tasks(self) -> List[Dict]:
        """Scan active YAML tasks."""
        tasks = []
        # Use self.TASKS_ACTIVE, which should be available in Agent
        for f in self.TASKS_ACTIVE.glob("*.yaml"):
            task_info = self._parse_yaml_task(f)
            if task_info:
                tasks.append(task_info)
        return tasks

    def _parse_yaml_task(self, filepath: Path) -> Optional[Dict]:
        """Parse a YAML task file."""
        # Support: 001-task, TKT-WEB-001-task, idea-001-task, AIVC-001-task
        match = re.match(r"^(\d+|[A-Za-z]+-\w+-\d+|[A-Za-z]+-\d+)[-_]", filepath.name)
        if not match:
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            if not content:
                return None

            return {
                "id": match.group(1),
                "file": filepath,
                "type": "yaml",
                "name": content.get("name", filepath.stem),
                "content": content
            }
        except Exception as e:
            self.logger.error(f"Error parsing YAML task {filepath.name}: {e}")
            return None

    def execute_yaml_task(self, task: Dict) -> bool:
        """Execute a YAML task."""
        content = task["content"]
        task_id = task["id"]

        self.logger.info(f"Executing YAML Task {task_id}: {task['name']}")

        try:
            steps = content.get("steps", [])
            if not steps:
                self.logger.warning(f"No steps found in YAML task {task_id}")
                return True

            for i, step in enumerate(steps):
                step_name = step.get("name", f"Step {i+1}")
                self.log(f"Executing: {step_name}")

                action = step.get("action")
                if action == "run_script":
                    script_path = self.BASE_DIR / step.get("path")
                    # Use existing agent method to execute the script
                    if not self.execute_task_script({"id": f"{task_id}_{i}", "file": script_path, "name": step_name}):
                        return False
                elif action == "ai_analyze":
                    # Integration with Universal AI Interface
                    prompt = step.get("prompt")
                    image = step.get("image")
                    context = {"image_path": image} if image else {}
                    req = self.ai.create_request("ANALYSIS", prompt, context=context)
                    # Note: execute_yaml_task should be async or use run_until_complete
                    # For simplicity, assume synchronous processing or logging for now
                    self.log(f"AI Request queued: {prompt[:50]}...")
                elif action == "aivc":
                    # AIVC: autonomous AI Vision & Control goal execution
                    try:
                        from aivc_controller import AIVCController, make_lmstudio_caller, make_ollama_caller
                    except ImportError:
                        from .aivc_controller import AIVCController, make_lmstudio_caller, make_ollama_caller
                    goal = step.get("goal", "")
                    context = step.get("context", "")
                    server = step.get("server", "lmstudio")
                    model = step.get("model", "")
                    max_steps = step.get("max_steps", 10)
                    if server == "ollama":
                        ai_fn = make_ollama_caller(model=model or "qwen2.5:7b")
                    else:
                        ai_fn = make_lmstudio_caller(model=model)
                    ctrl = AIVCController(ai_call_fn=ai_fn, max_steps=max_steps)
                    result = ctrl.execute_goal(goal, context)
                    self.log(f"AIVC result: {'✅' if result['success'] else '❌'} in {result['steps']} steps ({result['total_time']}s)")
                    if not result['success']:
                        return False
                elif action == "shell":
                    # Route through the single exec-path: NO shell (no injection),
                    # argv-only, sandboxed when a container runtime is present.
                    import shlex
                    import sys as _sys
                    from pathlib import Path as _Path
                    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
                    from sandbox.runner import SandboxRunner, RunRequest
                    cmd = step.get("command")
                    parts = shlex.split(cmd)
                    res = SandboxRunner().run(RunRequest(
                        tool=parts[0], args=parts[1:], workdir=str(self.BASE_DIR)))
                    if res.code != 0:
                        raise RuntimeError(f"shell step failed ({res.code}): {res.stderr[:200]}")
                else:
                    self.logger.warning(f"Unknown action '{action}' in task {task_id}")

            return True
        except Exception as e:
            self.logger.error(f"Error executing YAML task {task_id}: {e}")
            return False
