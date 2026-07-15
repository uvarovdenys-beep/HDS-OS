#!/usr/bin/env python3
"""agent_tasks.py — task execution & file-I/O methods, split out of agent.py.

TaskExecutionMixin holds the task-lifecycle helpers (run a task script, archive
a completed task, enforce R-01 file sizes, write to production, detect completed
markdown). Kept as a mixin so HDSAgent stays well under the R-01 line limit;
these run with full access to the agent's state via self.
"""
import json
import os
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict


class TaskExecutionMixin:
    """Task execution + file-I/O helpers for HDSAgent."""

    def execute_task_script(self, task: Dict) -> bool:
        """Execute Python task script with enhanced error handling."""
        filepath = task["file"]
        task_id = task["id"]

        self.logger.info(f"Executing Task {task_id}: {filepath.name}")

        # HDS Hybrid Logic: Check if task requires AI assistance
        # If task has AI markers, we can pre-process it through AI interface

        # Validation with enhanced error handling and voice output
        try:
            valid, msg = self.validate_script(filepath)
            if not valid:
                # Detailed voice output for validation error
                self.vox.speak(f"Security violation in task {task_id}. {msg}", "ERROR")
                self.vox.protocol("R-SCRIPT", msg)
                self.logger.error(f"Task {task_id} validation failed: {msg}")
                return False
        except Exception as e:
            self.logger.error(f"Validation error for task {task_id}: {e}")
            self.vox.speak(f"Validation system error for task {task_id}. Check logs.", "ERROR")
            self.vox.protocol("VALIDATION_ERROR", f"Task {task_id} validation error: {e}")
            return False

        # Execution with comprehensive error handling
        try:
            self.logger.info(f"Loading module for task {task_id}")

            # Dynamic module loading with verification
            spec = importlib.util.spec_from_file_location(f"task_{task_id}", filepath)
            if spec is None:
                raise ImportError(f"Cannot load module spec for {filepath}")

            module = importlib.util.module_from_spec(spec)
            if spec.loader is None:
                raise ImportError(f"Module loader is None for {filepath}")

            # Execute in isolated environment with error handling
            sys.modules[f"task_{task_id}"] = module

            self.logger.info(f"Executing module {task_id}")
            with self.error_handler(f"Task {task_id} execution"):
                spec.loader.exec_module(module)

                # If module has run_task or main function - call it
                self.logger.info(f"Checking for run_task in {task_id}")
                if hasattr(module, "run_task"):
                    self.logger.info(f"Calling run_task in {task_id}")
                    module.run_task()
                elif hasattr(module, "main"):
                    self.logger.info(f"Calling main in {task_id}")
                    module.main()
                elif hasattr(module, "run"):
                    self.logger.info(f"Calling run in {task_id}")
                    module.run()
                else:
                    self.logger.warning(f"No run_task, main or run found in {task_id}")

            self.logger.info(f"Task {task_id} executed successfully")
            self.vox.task_executed(task_id, "EXECUTED SUCCESSFULLY")
            return True

        except ImportError as e:
            self.logger.error(f"Import error for task {task_id}: {e}")
            error_msg = f"Task {task_id} import failed: {str(e)[:100]}"
            self.vox.speak(f"Critical import error in task {task_id}. {error_msg}", "ERROR")
            self.vox.protocol("IMPORT_FAIL", error_msg)
            return False
        except SyntaxError as e:
            self.logger.error(f"Syntax error in task {task_id}: {e}")
            self.vox.protocol("SYNTAX_ERROR", f"Task {task_id} syntax error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Execution error for task {task_id}: {e}", exc_info=True)
            self.vox.protocol("EXEC_FAIL", f"Task {task_id} failed: {e}")
            return False

    MAX_TASK_RETRIES = 3   # quarantine a task after this many failed cycles

    def _quarantine_on_repeat_failure(self, task: Dict):
        """On failure: first ESCALATE to a different served model; only when the
        models are exhausted (or MAX_TASK_RETRIES hit) move the task to
        ai-mind/tasks/failed/ so the daemon stops retrying it every cycle.

        A weak model (graded S, garbled output) may fail where a stronger one
        succeeds — so we rotate models before giving up. Without any of this an
        unsatisfiable task is re-attempted forever and starves real work.
        """
        src = task.get("file")
        if not src or not Path(src).exists():
            return
        src = Path(src)
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        n = int(data.get("_failures", 0)) + 1
        data["_failures"] = n

        # 1) Try a DIFFERENT model before quarantine (skip embedding models).
        tried = set(data.get("_models_tried", []))
        if data.get("model"):
            tried.add(data["model"])
        try:
            served = [m for m in self._served_model_ids()
                      if "embed" not in m.lower()]
        except Exception:
            served = []
        alternatives = [m for m in served if m not in tried]
        # Escalate toward CODER models first — a code task that a general model
        # failed is far likelier to pass on a code-specialised one. Without this,
        # escalation once walked to weaker general models (qwen3.5:9b/4b) while a
        # stronger coder (qwen3-coder:30b) sat unused.
        # Match CODE-specialised models only. "deepseek" alone is wrong:
        # deepseek-r1 is a reasoning model and produced syntax errors when
        # escalated to as if it were a coder.
        _coder = lambda m: any(k in m.lower() for k in
                               ("coder", "-code", "code-", "starcoder",
                                "deepseek-coder", "codellama", "codestral"))
        alternatives.sort(key=lambda m: (not _coder(m), m))
        if n < self.MAX_TASK_RETRIES and alternatives:
            data["model"] = alternatives[0]
            data["_models_tried"] = sorted(tried)
            try:
                src.write_text(json.dumps(data, indent=2), encoding="utf-8")
                self.vox.speak(f"Task {task.get('id', src.stem)} retry on "
                               f"{alternatives[0]}", "INFO")
            except Exception:
                pass
            return

        # 2) No alternative left (or retries exhausted) → quarantine.
        if n < self.MAX_TASK_RETRIES:
            try:
                src.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass
            return
        failed_dir = self.TASKS_ACTIVE.parent / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(failed_dir / src.name))
            self.vox.speak(f"Task {task.get('id', src.stem)} quarantined "
                           f"after {n} failures across {len(tried)} model(s)",
                           "TASK_FAIL")
        except Exception as e:
            self.logger.error(f"Quarantine failed for {src.name}: {e}")

    def archive_completed_task(self, task: Dict):
        """Archive completed task with verification."""
        src = task["file"]
        if not src.exists():
            self.logger.warning(f"Cannot archive: {src} does not exist")
            return

        # Create archive directory if it does not exist
        self.TASKS_ARCHIVE.mkdir(parents=True, exist_ok=True)

        dst = self.TASKS_ARCHIVE / src.name

        try:
            # If file already exists in archive, add timestamp to avoid conflicts
            if dst.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dst = self.TASKS_ARCHIVE / f"{src.stem}_{timestamp}{src.suffix}"

            shutil.move(str(src), str(dst))
            self.log(f"Successfully archived: {src.name} to {dst.name}")
        except Exception as e:
            self.logger.error(f"Failed to archive {src.name}: {e}")
            self.vox.protocol("ARCHIVE_FAIL", f"Could not archive task {task['id']}: {e}")

    def check_file_size_limits(self):
        """Check R-01: SIZE_LIMIT for all allowed workspaces."""
        violations = []
        for workspace in self.ALLOWED_WORKSPACES:
            workspace_path = Path(workspace)
            if workspace_path.exists():
                for root, dirs, files in os.walk(workspace_path):
                    # Ignore __pycache__ and venv
                    dirs[:] = [d for d in dirs if d not in ["__pycache__", "venv", ".git", ".script_cache"]]
                    for file in files:
                        if file.endswith(".py"):
                            filepath = Path(root) / file
                            try:
                                with open(filepath, "r", encoding="utf-8") as f:
                                    line_count = len(f.readlines())
                                if line_count > self.MAX_FILE_LINES:
                                    violations.append(f"{filepath.name}: {line_count} lines")
                            except:
                                pass

        if violations:
            self.vox.protocol("R-01", f"Size limit violations: {', '.join(violations[:3])}")

    def write_to_production(self, relative_path: str, content: str) -> bool:
        """Controlled write to registered project files."""
        # Search path in allowed workspaces (excluding AI-MIND)
        if len(self.ALLOWED_WORKSPACES) <= 1:
            self.vox.protocol("WRITE_FAIL", "No external projects registered for production write")
            return False

        # By default use the first registered external project
        target_base = Path(self.ALLOWED_WORKSPACES[1])
        target = target_base / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Check R-01
            lines = content.splitlines()
            if len(lines) > self.MAX_FILE_LINES:
                self.vox.protocol("R-01", f"Cannot write: exceeds {self.MAX_FILE_LINES} lines")
                return False

            with open(target, "w", encoding="utf-8") as f:
                f.write(content)

            self.log(f"Written to production: {relative_path}")
            return True
        except Exception as e:
            self.vox.protocol("WRITE_FAIL", f"Failed to write {relative_path}: {e}")
            return False

    def _check_markdown_completed(self, filepath: Path) -> bool:
        """Check if Markdown task is complete (status: done/100/completed)."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read(2048)  # YAML front matter limit

            status_regex = re.compile(r'^status:\s*["\']?(done|100|completed)["\']?', re.MULTILINE | re.IGNORECASE)
            legacy_regex = re.compile(r'\[PROGRESS: 100%\]|PROGRESS: 100%')

            return bool(status_regex.search(content) or legacy_regex.search(content))
        except Exception:
            return False
