#!/usr/bin/env python3
"""
agent.py
HDS Nucleus - Core Agent
AI-DRIVER: Internal execution engine for autonomous monitoring and control
"""

import os
import sys
import time
import re
import shutil
import importlib.util
import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

# Add path to vox
try:
    from .vox import VoxService
except (ImportError, ValueError):
    from vox import VoxService

try:
    from .task_yaml_support import YAMLTaskSupportMixin
except (ImportError, ValueError):
    from task_yaml_support import YAMLTaskSupportMixin

# TKT-004 & TKT-005: Knowledge Gatekeeper + AI Experience
try:
    from .knowledge_gatekeeper import KnowledgeGatekeeper
except (ImportError, ValueError):
    from knowledge_gatekeeper import KnowledgeGatekeeper

try:
    from .ai_experience import AIExperienceModule
except (ImportError, ValueError):
    from ai_experience import AIExperienceModule

# TKT-003: System Improvements (AST, Token Wallet, Fallback, Hibernation)
try:
    from .ast_validator import ASTValidator
except (ImportError, ValueError):
    from ast_validator import ASTValidator

try:
    from .token_wallet import TokenWallet
except (ImportError, ValueError):
    from token_wallet import TokenWallet

try:
    from .fallback_model_chain import FallbackModelChain
except (ImportError, ValueError):
    from fallback_model_chain import FallbackModelChain

try:
    from .hibernation_daemon import HibernationDaemon
except (ImportError, ValueError):
    from hibernation_daemon import HibernationDaemon

# TKT-006: Microkernel IPC for delegating heavy tasks
try:
    from .microkernel_ipc import MicrokernelIPCClient, DaemonType
except (ImportError, ValueError):
    from microkernel_ipc import MicrokernelIPCClient, DaemonType

# Protocol enforcement + auto-decompose
try:
    from .protocol_enforcer import ProtocolEnforcer
except (ImportError, ValueError):
    from protocol_enforcer import ProtocolEnforcer

try:
    from .auto_decompose import check_and_decompose
except (ImportError, ValueError):
    from auto_decompose import check_and_decompose

# AIVC: AI Vision & Control autonomous loop
try:
    from .aivc_controller import AIVCController, make_lmstudio_caller, make_ollama_caller
except (ImportError, ValueError):
    try:
        from aivc_controller import AIVCController, make_lmstudio_caller, make_ollama_caller
    except ImportError:
        AIVCController = None

class HDSAgent(YAMLTaskSupportMixin):
    """
    HDS NUCLEUS
    Internal Engine: AI-DRIVER (Sub-agent)
    Executes R-Series Laws:
    - R-19: ZERO_DIRECT_WRITE - all changes via Task Scripts
    - R-13: SCRIPT_FIRST - priority for scripts
    - R-01: SIZE_LIMIT - file size verification
    """

    BASE_DIR = Path(__file__).parent.parent.resolve()
    AI_MIND_DIR = BASE_DIR / "AI-MIND"
    TASKS_ACTIVE = AI_MIND_DIR / "tasks" / "active"
    TASKS_BACKLOG = AI_MIND_DIR / "tasks" / "backlog"
    TASKS_ARCHIVE = TASKS_ACTIVE / ".archive"
    LOGS_DIR = AI_MIND_DIR / "logs"
    KNOWLEDGE_DIR = AI_MIND_DIR / "knowledge"
    IDEAS_DIR = AI_MIND_DIR / "ideas"

    MAX_FILE_LINES = 1000  # R-01
    MAX_FILE_SIZE = 1024 * 1024  # 1MB max file size

    # Project Isolation Settings
    ALLOWED_WORKSPACES = [] # Will be populated from projects
    STRICT_SANDBOX = True

    def __init__(self):
        # Check if silent mode is enabled via HDS_SILENT environment variable
        import os
        silent_mode = os.environ.get('HDS_SILENT', '0').lower() in ('1', 'true', 'yes', 'on')
        self.vox = VoxService(self.LOGS_DIR, enable_speech=not silent_mode)
        self.running = False
        self.cycle_count = 0
        self._ensure_dirs()
        self._setup_logging()
        self._load_projects()

        # Initialize Universal AI Interface for HDS
        try:
            from .universal_ai_interface import get_ai_interface
            from .vision import MARK_TWAIN_Vision
        except (ImportError, ValueError):
            from universal_ai_interface import get_ai_interface
            from vision import MARK_TWAIN_Vision

        self.ai = get_ai_interface(self.BASE_DIR)
        self.vision = MARK_TWAIN_Vision(self.BASE_DIR)

        # TKT-004 & TKT-005: Initialize Knowledge Gatekeeper & AI Experience
        self.gatekeeper = KnowledgeGatekeeper(self.BASE_DIR)
        self.experience = AIExperienceModule(self.LOGS_DIR.parent / "experience" / "anti_patterns.json")

        # TKT-003: Initialize System Improvements
        self.ast_validator = ASTValidator()
        self.token_wallet = TokenWallet(self.LOGS_DIR / "token_wallet.json")
        self.fallback_chain = FallbackModelChain()
        self.hibernation = HibernationDaemon(self.LOGS_DIR.parent / "tasks" / "background")

        # TKT-006: Initialize Microkernel IPC Client
        daemon_config = {
            "vision": "http://localhost:9001",
            "browser": "http://localhost:9002",
            "web_search": "http://localhost:9003",
            "doc": "http://localhost:9004",
        }
        self.microkernel = MicrokernelIPCClient(daemon_config)

        # v1.1: Webhook API server (port 8080)
        try:
            from webhook_server import WebhookServer
            self.webhook_server = WebhookServer(port=8080, tasks_dir=self.TASKS_ACTIVE)
            import threading
            threading.Thread(target=self.webhook_server.start, daemon=True).start()
            self.vox.speak("Webhook API started on port 8080", "INFO")
        except Exception as e:
            self.webhook_server = None
            self.logger.warning(f"Webhook server not started: {e}")

        # Model trust registry (canary-tested models)
        self._trusted_models = {}  # model_name -> protocol_level

        self.vox.speak(
            "Knowledge Gatekeeper, AI Experience, AST Validator, Token Wallet, "
            "Fallback Chain, Hibernation, Microkernel IPC, Webhook API initialized.",
            "INFO"
        )

    def _ensure_dirs(self):
        """Create necessary directories."""
        for d in [self.AI_MIND_DIR, self.TASKS_ACTIVE, self.TASKS_BACKLOG, self.TASKS_ARCHIVE,
                  self.LOGS_DIR, self.KNOWLEDGE_DIR, self.IDEAS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def _load_projects(self):
        """Load and bind external projects."""
        projects_config = self.KNOWLEDGE_DIR / "projects.json"
        # AI-MIND and SCRIPTS are always allowed
        self.ALLOWED_WORKSPACES = [
            str(self.AI_MIND_DIR),
            str(self.BASE_DIR / "scripts")
        ]

        if projects_config.exists():
            try:
                with open(projects_config, "r", encoding="utf-8") as f:
                    projects = json.load(f)
                    for p in projects.get("active_projects", []):
                        path = Path(p["path"]).resolve()
                        self.ALLOWED_WORKSPACES.append(str(path))
                        self.logger.info(f"Project Linked: {p['name']} at {path}")
            except Exception as e:
                self.logger.error(f"Failed to load projects: {e}")

    def validate_script(self, filepath: Path) -> tuple[bool, str]:
        """Validate Python script with enhanced sandboxing."""
        try:
            resolved_path = filepath.resolve()

            # STRICT SANDBOX: Check if path is within allowed workspaces
            is_allowed = False
            for workspace in self.ALLOWED_WORKSPACES:
                if str(resolved_path).lower().startswith(str(Path(workspace).resolve()).lower()):
                    is_allowed = True
                    break

            if not is_allowed:
                self.logger.error(f"SECURITY: Access Denied to {resolved_path}. Path outside allowed workspaces. Allowed: {self.ALLOWED_WORKSPACES}")
                return False, "SECURITY: Path outside allowed projects or AI-MIND"

            # Deny access to agent system directory (core protection)
            if str(resolved_path).startswith(str(self.BASE_DIR / "agent")):
                self.logger.error(f"SECURITY: Core Protection Violation. Attempt to access agent core.")
                return False, "SECURITY: Cannot access or modify Agent Core"

            # Check file existence
            if not resolved_path.exists():
                return False, "File not found"

            # Check file size
            file_size = resolved_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                self.logger.error(f"File too large: {file_size} bytes")
                return False, f"File exceeds maximum size ({self.MAX_FILE_SIZE} bytes)"

            # Safe read with size limit
            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read(self.MAX_FILE_SIZE + 1)

            # R-01: Size Limit - check line count
            lines = content.splitlines()
            if len(lines) > self.MAX_FILE_LINES:
                self.logger.warning(f"R-01 VIOLATION: {len(lines)} lines exceeds {self.MAX_FILE_LINES}")
                return False, f"R-01 VIOLATION: File exceeds {self.MAX_FILE_LINES} lines ({len(lines)})"

            # Syntax check
            try:
                compile(content, resolved_path.name, "exec")
            except SyntaxError as e:
                self.logger.error(f"Syntax error in {resolved_path.name}: {e}")
                return False, f"Syntax error: {e}"

            # Check for dangerous operations
            dangerous_patterns = [
                "os.system", "subprocess.call", "subprocess.run",
                "exec(", "eval(", "__import__", "compile("
            ]
            for pattern in dangerous_patterns:
                if pattern in content:
                    self.logger.warning(f"SECURITY: Forbidden pattern '{pattern}' detected in {resolved_path.name}")
                    return False, f"SECURITY: Forbidden pattern '{pattern}' detected"

            self.logger.info(f"Script validation passed for {resolved_path.name}")
            return True, "VALID"

        except PermissionError as e:
            self.logger.error(f"Permission denied for {filepath}: {e}")
            return False, f"Permission denied: {e}"
        except Exception as e:
            self.logger.error(f"Validation error for {filepath}: {e}")
            return False, f"VALIDATION ERROR: {e}"

    def _setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.LOGS_DIR / 'agent.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    @contextmanager
    def error_handler(self, operation: str):
        """Context manager for error handling."""
        try:
            yield
        except FileNotFoundError as e:
            self.logger.error(f"{operation}: File not found - {e}")
            raise
        except PermissionError as e:
            self.logger.error(f"{operation}: Permission denied - {e}")
            raise
        except Exception as e:
            self.logger.error(f"{operation}: Unexpected error - {e}")
            raise RuntimeError(f"{operation} failed") from e

    def log(self, msg: str, level: str = "INFO"):
        """Centralized logging."""
        self.vox.speak(msg, level)

    def scan_tasks(self) -> List[Dict]:
        """Scan active tasks."""
        tasks = []
        for f in self.TASKS_ACTIVE.glob("*.py"):
            task_info = self._parse_task_filename(f)
            if task_info:
                tasks.append(task_info)
        for f in self.TASKS_ACTIVE.glob("*.md"):
            task_info = self._parse_markdown_task(f)
            if task_info:
                tasks.append(task_info)

        # Add YAML task support via Mixin
        tasks.extend(self.scan_yaml_tasks())

        return sorted(tasks, key=lambda x: x["id"])

    def _parse_task_filename(self, filepath: Path) -> Optional[Dict]:
        """Parse Python task file."""
        match = re.match(r"^(\d+|[A-Z]+-\w+-\d+)[-_]", filepath.name)
        if match:
            return {
                "id": match.group(1),
                "file": filepath,
                "type": "python",
                "name": filepath.stem
            }
        return None

    def _parse_markdown_task(self, filepath: Path) -> Optional[Dict]:
        """Parse Markdown task file."""
        match = re.match(r"^(TKT-[A-Z]+-\d+)", filepath.name)
        if match:
            return {
                "id": match.group(1),
                "file": filepath,
                "type": "markdown",
                "name": filepath.stem
            }
        return None



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

    def cycle(self):
        """One cycle of agent operation."""
        self.cycle_count += 1
        self.log(f"Find tasks")

        # Anti-gravity stability check every 10 cycles
        if self.cycle_count % 10 == 0:
            self.vox.anti_gravity_signal()

        # 1. Check file sizes (R-01)
        self.check_file_size_limits()

        # TKT-004: Verify core system integrity
        if self.cycle_count % 5 == 0:  # Every 5 cycles
            intact, msg = self.gatekeeper.verify_core_integrity()
            if not intact:
                self.vox.speak(msg, "ERROR")
                self.log(msg)

        # 2. Collect tasks from files + webhook queue
        tasks = self.scan_tasks()
        # Add JSON tasks (from webhook or external task files)
        for f in self.TASKS_ACTIVE.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                tasks.append({
                    "id": data.get("task_id", f.stem),
                    "file": f,
                    "type": "json",
                    "name": f.stem,
                    "data": data,
                })
            except Exception:
                pass
        self.log(f"Found {len(tasks)} active tasks")

        # Voice output for task search
        if self.cycle_count == 1:
            self.vox.speak("Finding tasks", "INFO")

        completed_tasks = 0
        failed_tasks = 0

        for task in tasks:
            if task["type"] == "python":
                # TKT-005: Inject AI Experience context before execution
                task_context = self.experience.get_context_for_prompt([task['name']])
                if task_context:
                    self.log(f"[AI-Experience] Injecting lessons into task {task['id']}")

                # Voice output for task start
                self.vox.task_starting(task['id'], task['name'])

                # Python scripts - for execution
                success = self.execute_task_script(task)
                if success:
                    # R-19 & HDS BASE Policy: Remove script after successful execution
                    self.log(f"Task {task['id']} PASSED. Removing script as per HDS policy.")
                    try:
                        task['file'].unlink()
                        self.vox.task_completed(task['id'])
                        completed_tasks += 1
                    except Exception as e:
                        self.logger.error(f"Failed to remove task file {task['file']}: {e}")
                        failed_tasks += 1
                else:
                    failed_tasks += 1
                    # TKT-005: Register failure as anti-pattern
                    try:
                        error_msg = f"Task {task['id']} failed during execution"
                        self.experience.register_failure(
                            task_id=task['id'],
                            error_trace=error_msg,
                            ai_self_analysis="Task execution failed - check task logic and dependencies",
                            anti_pattern_rule=f"AVOID: {task['name']} pattern until root cause identified",
                        )
                    except Exception as e:
                        self.log(f"Could not register failure: {e}")

                    # Check if a different model is needed (simplified logic for demonstration)
                    if "model" in str(task).lower():
                        self.vox.task_failed_model(task['id'])
                    else:
                        self.vox.speak(f"Task {task['id']} failed", "TASK_FAIL")
                    failed_tasks += 1

            elif task["type"] == "yaml":
                # Execute YAML task
                self.vox.task_starting(task['id'], task['name'])
                success = self.execute_yaml_task(task)
                if success:
                    self.archive_completed_task(task)
                    self.vox.task_completed(task['id'])
                    completed_tasks += 1
                else:
                    self.vox.speak(f"YAML Task {task['id']} failed", "TASK_FAIL")
                    failed_tasks += 1

            elif task["type"] == "json":
                # JSON task — route to appropriate daemon via microkernel
                self.vox.task_starting(task['id'], task['name'])
                success = self._execute_json_task(task)
                if success:
                    self.vox.task_completed(task['id'])
                    completed_tasks += 1
                else:
                    self.vox.speak(f"JSON Task {task['id']} failed", "TASK_FAIL")
                    failed_tasks += 1

            elif task["type"] == "markdown":
                # Check for automatic archival if task was completed by user
                if self._check_markdown_completed(task["file"]):
                    self.archive_completed_task(task)
                    self.vox.task_completed(task['id'])
                    completed_tasks += 1
                else:
                    # Markdown tasks - for manual execution
                    self.log(f"Pending manual task: {task['id']}")
                    self.vox.user_decision_required()
                    if "script" in task["name"].lower():
                        self.vox.script_execution_required()

        # Voice output for cycle summary
        if completed_tasks > 0 and failed_tasks == 0 and len(tasks) == completed_tasks:
            self.vox.all_tasks_completed()

        if failed_tasks > 0:
            self.vox.speak(f"Warning: {failed_tasks} tasks failed execution. Check logs for details.", "ERROR")

        if len(tasks) == 0:
            self.vox.waiting_for_tasks()

        # 3. Check for new ideas
        ideas = list(self.IDEAS_DIR.glob("*.md"))
        if ideas:
            self.log(f"Detected {len(ideas)} new ideas for review")
            self.vox.speak(f"{len(ideas)} new ideas detected for review", "IDEAS")

    def _execute_project_task(self, task_id: str, task_data: Dict) -> bool:
        """
        Decompose a project-level task into atomic subtasks via script (not AI).
        Uses deterministic decomposition — splits instruction into file-level tasks.
        """
        project_name = task_data.get("project", task_id)
        instruction = task_data.get("instruction", "")
        structure = task_data.get("structure", [])
        model = task_data.get("model", "")

        if not structure and not instruction:
            self.vox.speak(f"Project task {task_id}: no structure or instruction", "ERROR")
            return False

        # If no structure provided, use AI to decompose (one-time, XL-level action)
        if not structure:
            from aivc_controller import make_lmstudio_caller, make_ollama_caller
            try:
                ai_call = make_lmstudio_caller(model=model) if model else make_lmstudio_caller()
            except Exception:
                ai_call = make_ollama_caller()

            prompt = (
                "Decompose this project into a list of files to create.\n"
                "Return ONLY a JSON array of objects: "
                '[{"file": "filename.py", "instruction": "what this file does"}]\n'
                "Maximum 8 files. No explanation.\n\n"
                f"Project: {instruction}"
            )
            try:
                raw = ai_call(prompt)
                # Parse JSON from response
                clean = raw.strip()
                if clean.startswith("```"):
                    clean = "\n".join(clean.split("\n")[1:-1])
                # Find JSON array in response
                import re
                match = re.search(r'\[.*\]', clean, re.DOTALL)
                if match:
                    structure = json.loads(match.group())
                else:
                    structure = json.loads(clean)
            except Exception as e:
                self.vox.speak(f"Decomposition failed: {e}", "ERROR")
                return False

        # Create atomic subtasks from structure
        project_dir = self.TASKS_ACTIVE.parent / "generated" / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        subtask_count = 0
        for i, item in enumerate(structure[:8], 1):
            filename = item.get("file", f"module_{i}.py")
            sub_instruction = item.get("instruction", "")

            subtask_id = f"{task_id}-{i:02d}"
            subtask = {
                "task_id": subtask_id,
                "type": "generate_code",
                "instruction": f"File: {filename}\n{sub_instruction}",
                "model": model,
                "output_dir": str(project_dir),
                "output_filename": filename,
            }

            # Write subtask to active queue
            subtask_file = self.TASKS_ACTIVE / f"{subtask_id}.json"
            subtask_file.write_text(json.dumps(subtask, indent=2))
            subtask_count += 1

        self.vox.speak(f"Project {task_id} decomposed into {subtask_count} subtasks", "INFO")

        # Save project manifest
        manifest = {
            "project": project_name,
            "task_id": task_id,
            "subtasks": subtask_count,
            "structure": structure,
            "output_dir": str(project_dir),
        }
        (project_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        # Remove original project task file
        task_file = self.TASKS_ACTIVE / f"{task_id}.json"
        task_file.unlink(missing_ok=True)

        return True

    def _execute_ai_task(self, task_id: str, instruction: str, model_name: str = "",
                         output_dir: str = "", output_filename: str = "") -> bool:
        """
        Full AI code generation pipeline: prompt → generate → enforce → validate → decompose → test.
        This is the 'brain' that makes local models useful for programming.
        """
        from aivc_controller import make_lmstudio_caller, make_ollama_caller
        from canary_tests import CanaryTestRunner

        # 1. Select model caller
        if not model_name:
            model_name = "qwen2.5-coder-14b"  # Best protocol compliance
        enforcer = ProtocolEnforcer(model_name)

        # Canary gate — verify model quality before trusting it
        if model_name not in self._trusted_models:
            self.vox.speak(f"Running canary test for {model_name}", "INFO")
            try:
                ai_fn = make_lmstudio_caller(model=model_name)
                runner = CanaryTestRunner(ai_call_fn=ai_fn)
                results = {}
                for test_type in ["context", "format", "boundary"]:
                    r = runner.run_test(test_type)
                    if r:
                        results[test_type] = r.get("passed", False)
                passed = sum(1 for v in results.values() if v)
                level = "M" if passed >= 2 else "L" if passed >= 1 else "BLOCKED"
                self._trusted_models[model_name] = level
                self.vox.speak(f"Model {model_name}: canary {passed}/3 → level {level}", "INFO")
            except Exception:
                self._trusted_models[model_name] = "L"

        if self._trusted_models.get(model_name) == "BLOCKED":
            self.vox.speak(f"Model {model_name} blocked by canary tests", "ERROR")
            return False

        # Check if model is allowed to write code
        allowed, reason = enforcer.check_action("write_file")
        if not allowed:
            self.vox.speak(f"Model {model_name} not allowed to write files: {reason}", "ERROR")
            return False

        # 2. Create AI caller
        try:
            ai_call = make_lmstudio_caller(model=model_name)
        except Exception:
            try:
                ai_call = make_ollama_caller(model=model_name)
            except Exception as e:
                self.vox.speak(f"No AI model available: {e}", "ERROR")
                return False

        # 3. Generate code
        self.vox.speak(f"Generating code for task {task_id}", "INFO")
        prompt = (
            f"You are an HDS agent. Write Python code for the following task.\n"
            f"Rules:\n"
            f"- Maximum 200 lines\n"
            f"- All classes must have docstrings\n"
            f"- All public methods must have docstrings\n"
            f"- English only in code\n"
            f"- Output ONLY the Python code, no explanation\n\n"
            f"Task: {instruction}"
        )

        try:
            code = ai_call(prompt)
        except Exception as e:
            self.vox.speak(f"AI generation failed: {e}", "ERROR")
            return False

        # Strip markdown code blocks
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # 4. AST validation
        valid, error = self.ast_validator.validate_string(code)
        if not valid:
            self.vox.speak(f"Generated code has syntax errors: {error}", "ERROR")
            return False

        # 5. Write file
        dest_dir = Path(output_dir) if output_dir else self.TASKS_ACTIVE.parent / "generated"
        dest_dir.mkdir(parents=True, exist_ok=True)
        fname = output_filename if output_filename else f"{task_id}.py"
        output_file = dest_dir / fname
        output_file.write_text(code, encoding="utf-8")
        self.vox.speak(f"Code written: {output_file.name}", "INFO")

        # 6. Auto-decompose if too large
        decompose_result = check_and_decompose(str(output_file), model_size="m")
        if decompose_result:
            self.vox.speak(f"Auto-decomposed into {decompose_result.files_created} files", "INFO")

        # 7. Run basic test (import check)
        allowed, _ = enforcer.check_action("run_test")
        if allowed:
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "-c", f"import ast; ast.parse(open('{output_file}').read()); print('OK')"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                self.vox.speak(f"Test failed: {result.stderr[:80]}", "ERROR")
                return False

        # 8. Save result
        completed_dir = self.TASKS_ACTIVE.parent / "completed"
        completed_dir.mkdir(exist_ok=True)
        result_file = completed_dir / f"{task_id}_RESULT.json"
        result_file.write_text(json.dumps({
            "task_id": task_id,
            "status": "success",
            "output_file": str(output_file),
            "lines": len(code.split("\n")),
            "model": model_name,
            "decomposed": decompose_result is not None,
        }, indent=2))

        self.vox.speak(f"Task {task_id} completed successfully", "SUCCESS")
        return True

    def _execute_json_task(self, task: Dict) -> bool:
        """Execute JSON task by routing to appropriate daemon via microkernel IPC."""
        data = task.get("data", {})
        task_id = task["id"]
        task_type = data.get("type", "")
        daemon = data.get("daemon", "")

        # Project-level task — decompose into subtasks
        if task_type == "create_project":
            return self._execute_project_task(task_id, data)

        # AI code generation tasks — handled by _execute_ai_task
        if task_type == "generate_code":
            instruction = data.get("instruction", "")
            model = data.get("model", "")
            output_dir = data.get("output_dir", "")
            output_filename = data.get("output_filename", "")
            return self._execute_ai_task(task_id, instruction, model, output_dir, output_filename)

        # Route to daemon based on task type or explicit daemon field
        if not daemon:
            if task_type in ("capture_screen", "analyze_image", "detect_elements"):
                daemon = "vision"
            elif task_type in ("navigate", "click", "type", "dom_to_markdown"):
                daemon = "browser"
            elif task_type in ("search", "fetch_page", "verify_fact"):
                daemon = "web_search"
            elif task_type in ("read_doc", "summarize_doc", "search_doc", "convert_doc"):
                daemon = "doc"
            else:
                self.log(f"Unknown task type: {task_type}")
                return False

        try:
            result = self.microkernel.send_task(daemon, data)
            success = result.get("status") == "success"

            # Save result
            completed_dir = self.TASKS_ACTIVE.parent / "completed"
            completed_dir.mkdir(exist_ok=True)
            result_file = completed_dir / f"{task_id}_RESULT.json"
            result_file.write_text(json.dumps(result, indent=2, default=str))

            # Remove source task file
            task["file"].unlink(missing_ok=True)

            return success
        except Exception as e:
            self.log(f"JSON task {task_id} execution error: {e}")
            return False

    def cleanup_archive_for_release(self):
        """Clean archive from development traces when building release."""
        self.vox.speak("Starting release cleanup process", "RELEASE_CLEANUP")

        try:
            # Clean task archive
            if self.TASKS_ARCHIVE.exists():
                archived_tasks = list(self.TASKS_ARCHIVE.glob("*.py"))
                self.vox.speak(f"Found {len(archived_tasks)} archived tasks for cleanup", "CLEANUP_INFO")

                for task_file in archived_tasks:
                    # Remove or anonymize depending on policy
                    task_file.unlink()
                    self.log(f"Removed archived task: {task_file.name}")

                self.vox.speak("Task archive cleaned successfully", "CLEANUP_SUCCESS")

            # Clean development logs (keep only system logs)
            if self.LOGS_DIR.exists():
                dev_logs = [f for f in self.LOGS_DIR.glob("*.log") if "dev" in f.name.lower() or "debug" in f.name.lower()]
                for log_file in dev_logs:
                    log_file.unlink()
                    self.log(f"Removed development log: {log_file.name}")

                self.vox.speak("Development logs cleaned successfully", "CLEANUP_SUCCESS")

            # Clean temporary files
            temp_files = list(self.BASE_DIR.glob("*.tmp")) + list(self.BASE_DIR.glob("*.temp"))
            for temp_file in temp_files:
                temp_file.unlink()
                self.log(f"Removed temp file: {temp_file.name}")

            self.vox.speak("Release cleanup completed successfully", "RELEASE_READY")
            return True

        except Exception as e:
            self.vox.speak(f"Release cleanup failed: {str(e)}", "CLEANUP_ERROR")
            self.logger.error(f"Release cleanup error: {e}")
            return False

    def run(self, continuous: bool = False, interval: int = 60):
        """
        Start agent execution.

        Args:
            continuous: True for continuous monitoring
            interval: seconds between cycles
        """
        self.running = True
        # System ready announced in cycle() when cycle_count == 1
        # Avoid duplicate announcements

        try:
            while self.running:
                self.cycle()

                if not continuous:
                    break

                self.log(f"Sleeping {interval}s...")
                time.sleep(interval)

        except KeyboardInterrupt:
            self.log("Shutdown signal received", "INFO")
            self.running = False

        self.log("HDS Agent Halted.")

    def stop(self):
        """Stop the agent."""
        self.running = False

    def health_check(self) -> dict:
        """Comprehensive system health check."""
        self.logger.info("Running health check...")
        results = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'checks': {}
        }

        # Check directories
        try:
            required_dirs = [self.TASKS_ACTIVE, self.LOGS_DIR, self.KNOWLEDGE_DIR]
            for dir_path in required_dirs:
                exists = dir_path.exists()
                results['checks'][f'dir_{dir_path.name}'] = {
                    'status': 'ok' if exists else 'error',
                    'exists': exists,
                    'path': str(dir_path)
                }
                if not exists:
                    results['status'] = 'degraded'
        except Exception as e:
            results['checks']['directories'] = {'status': 'error', 'error': str(e)}
            results['status'] = 'error'

        # Check access permissions
        try:
            test_file = self.LOGS_DIR / 'health_test.tmp'
            test_file.write_text('test')
            test_file.unlink()
            results['checks']['file_permissions'] = {'status': 'ok'}
        except Exception as e:
            results['checks']['file_permissions'] = {'status': 'error', 'error': str(e)}
            results['status'] = 'error'

        # Check R-01 compliance
        try:
            violations = self._check_r01_compliance()
            results['checks']['r01_compliance'] = {
                'status': 'ok' if not violations else 'warning',
                'violations': violations,
                'violation_count': len(violations)
            }
            if violations:
                results['status'] = 'degraded'
        except Exception as e:
            results['checks']['r01_compliance'] = {'status': 'error', 'error': str(e)}
            results['status'] = 'error'

        # Check Vox service
        try:
            vox_status = self.vox.health_check() if hasattr(self.vox, 'health_check') else 'unknown'
            results['checks']['vox_service'] = {
                'status': 'ok' if vox_status != 'error' else 'error',
                'vox_status': vox_status
            }
            if vox_status == 'error':
                results['status'] = 'error'
        except Exception as e:
            results['checks']['vox_service'] = {'status': 'error', 'error': str(e)}
            results['status'] = 'error'

        self.logger.info(f"Health check completed. Status: {results['status']}")
        return results

    def _check_r01_compliance(self) -> list:
        """Check R-01: SIZE_LIMIT compliance."""
        violations = []
        try:
            # Check agent's own files
            agent_files = [
                self.BASE_DIR / "agent" / "agent.py",
                self.BASE_DIR / "agent" / "compliance.py",
                self.BASE_DIR / "agent" / "vox.py"
            ]

            for file_path in agent_files:
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            line_count = len(f.readlines())
                        if line_count > self.MAX_FILE_LINES:
                            violations.append({
                                'file': str(file_path),
                                'lines': line_count,
                                'limit': self.MAX_FILE_LINES
                            })
                    except Exception as e:
                        violations.append({
                            'file': str(file_path),
                            'error': f"Cannot read file: {e}"
                        })
        except Exception as e:
            violations.append({'error': f"R-01 check failed: {e}"})

        return violations


def main():
    """Entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="HDS OS Agent")
    parser.add_argument("--monitor", "-m", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--interval", "-i", type=int, default=60, help="Cycle interval in seconds")
    parser.add_argument("--once", "-o", action="store_true", help="Single execution cycle")
    parser.add_argument("--health", action="store_true", help="Run health check and exit")
    parser.add_argument("--validate", type=str, help="Validate specific script file")
    args = parser.parse_args()

    agent = HDSAgent()

    # Health check mode
    if args.health:
        import json
        health_results = agent.health_check()
        print(json.dumps(health_results, indent=2, ensure_ascii=False))
        sys.exit(0 if health_results['status'] == 'healthy' else 1)

    # Validation mode
    if args.validate:
        from pathlib import Path
        file_path = Path(args.validate)
        valid, message = agent.validate_script(file_path)
        print(f"Validation result: {'VALID' if valid else 'INVALID'}")
        print(f"Message: {message}")
        sys.exit(0 if valid else 1)

    # Normal execution modes
    if args.once or (not args.monitor):
        agent.run(continuous=False)
    else:
        agent.run(continuous=True, interval=args.interval)


if __name__ == "__main__":
    main()
