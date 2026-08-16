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

# When run as a script (`python3 agent.py`), agent/ is on sys.path but the OS
# root (parent) is not — yet cage modules like ast_validator/scribe/events live
# there. Add both so the fallback flat imports below resolve either way.
_AGENT_DIR = Path(__file__).resolve().parent
_OS_ROOT = _AGENT_DIR.parent
for _p in (str(_AGENT_DIR), str(_OS_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

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
    from .ast_validator import ASTValidator, SecurityLevel
except (ImportError, ValueError):
    from ast_validator import ASTValidator, SecurityLevel

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

# AI code-generation pipeline (split out of this file to keep it under R-01)
try:
    from .agent_ai_pipeline import AICodePipelineMixin
except (ImportError, ValueError):
    from agent_ai_pipeline import AICodePipelineMixin

# Task execution & file-I/O helpers (also split out for R-01)
try:
    from .agent_tasks import TaskExecutionMixin
except (ImportError, ValueError):
    from agent_tasks import TaskExecutionMixin

class HDSAgent(AICodePipelineMixin, TaskExecutionMixin, YAMLTaskSupportMixin):
    """
    HDS NUCLEUS
    Internal Engine: AI-DRIVER (Sub-agent)
    Executes R-Series Laws:
    - R-19: ZERO_DIRECT_WRITE - all changes via Task Scripts
    - R-13: SCRIPT_FIRST - priority for scripts
    - R-01: SIZE_LIMIT - file size verification
    """

    BASE_DIR = Path(__file__).parent.parent.resolve()
    AI_MIND_DIR = BASE_DIR / "ai-mind"   # lowercase: canonical across the OS
                                         # (scribe SANDBOX_ROOTS, port_registry,
                                         # vox …). On case-sensitive volumes an
                                         # uppercase "AI-MIND" is a DIFFERENT dir
                                         # and splits state — never diverge.
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

        # Webhook API is NOT started here. The old embedded WebhookServer was
        # unauthenticated on a fixed port (8080) — a second, weaker HTTP surface.
        # The single webhook surface is agent/webhook_server_enhanced.py
        # (authenticated, dynamic port), started by the launchers.
        self.webhook_server = None

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
                    # Archive so the completed task is not re-run every cycle
                    # (matches the yaml branch; json previously lingered forever).
                    self.archive_completed_task(task)
                    self.vox.task_completed(task['id'])
                    completed_tasks += 1
                else:
                    self.vox.speak(f"JSON Task {task['id']} failed", "TASK_FAIL")
                    failed_tasks += 1
                    # Quarantine after too many failures. A task that keeps
                    # failing (model graded S, unparseable output, hang) was
                    # otherwise retried EVERY cycle forever, spinning the daemon.
                    self._quarantine_on_repeat_failure(task)

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

        # 3. Check for NEW ideas — announce each file once, not every cycle.
        # (In continuous mode the same idea files were re-announced forever.)
        if not hasattr(self, "_seen_ideas"):
            self._seen_ideas = set()
        current = {p.name for p in self.IDEAS_DIR.glob("*.md")}
        fresh = current - self._seen_ideas
        if fresh:
            self.log(f"Detected {len(fresh)} new ideas for review")
            self.vox.speak(f"{len(fresh)} new ideas detected for review", "IDEAS")
        self._seen_ideas = current   # forget deleted, remember announced


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

    def monitor(self, interval: int = 60):
        """Run continuously (resident daemon). Alias used by the launchers
        (start_hds_agent_*.sh call agent.monitor())."""
        self.run(continuous=True, interval=interval)

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
