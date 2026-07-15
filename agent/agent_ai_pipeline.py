#!/usr/bin/env python3
"""agent_ai_pipeline.py — the AI code-generation pipeline, split out of agent.py.

AICodePipelineMixin holds the "brain" that turns a task into validated, caged
code: model resolution (bind to what the box actually serves), language-aware
generation, a language-mismatch guard, security validation, the R-19 write
through scribe, auto-decompose, and JSON/project task routing.

Kept as a mixin so HDSAgent stays under the R-01 1000-line limit while these
methods still run with full access to the agent's vox/log/state via self.
"""
import json
from pathlib import Path
from typing import Dict, List

try:
    from .ast_validator import SecurityLevel
except (ImportError, ValueError):
    from ast_validator import SecurityLevel
try:
    from .protocol_enforcer import ProtocolEnforcer
except (ImportError, ValueError):
    from protocol_enforcer import ProtocolEnforcer
try:
    from .auto_decompose import check_and_decompose
except (ImportError, ValueError):
    from auto_decompose import check_and_decompose


try:
    from .pipeline_helpers import PipelineHelpersMixin
except (ImportError, ValueError):
    from pipeline_helpers import PipelineHelpersMixin


class AICodePipelineMixin(PipelineHelpersMixin):
    """AI code-generation + task-routing methods for HDSAgent."""

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

        # Shared contract: every subtask sees ALL sibling files and their roles.
        # Without this, files are generated in isolation and invent each other's
        # APIs (e.g. main.py calling math_utils.sqrt() that was never written).
        siblings = "\n".join(
            f"- {it.get('file', f'module_{j}.py')}: {it.get('instruction','')}"
            for j, it in enumerate(structure[:8], 1))
        contract = (
            "PROJECT CONTEXT — these files make up one project; when a file "
            "imports or calls another, use the EXACT module and function names "
            "implied below and do NOT invent APIs that are not described:\n"
            f"{siblings}\n\n")

        # Order matters: generate dependency/library files FIRST and entry-point
        # consumers (main/run/app/demo/report/pipe) LAST, so the consumer sees
        # the siblings' real code (added to its prompt) and matches their API.
        _ENTRY = ("main", "run", "app", "demo", "report", "pipe", "usebank")
        ordered = sorted(
            structure[:8],
            key=lambda it: 1 if Path(it.get("file", "")).stem.lower() in _ENTRY else 0)

        subtask_count = 0
        for i, item in enumerate(ordered, 1):
            filename = item.get("file", f"module_{i}.py")
            sub_instruction = item.get("instruction", "")

            subtask_id = f"{task_id}-{i:02d}"
            subtask = {
                "task_id": subtask_id,
                "type": "generate_code",
                "instruction": f"{contract}Now write ONLY this one file:\n"
                               f"File: {filename}\n{sub_instruction}",
                "model": model,
                "output_dir": str(project_dir),
                "output_filename": filename,
            }
            # Propagate reference examples to every file of the project.
            if task_data.get("reference_files"):
                subtask["reference_files"] = task_data["reference_files"]

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










    def _resolve_model(self, requested: str):
        """Bind a requested model to an actually-served (provider, id, caller).

        Returns None if nothing on this machine matches. Prefers LM Studio, then
        Ollama; within a provider prefers an exact normalized match over a
        substring match. This is why the agent needs no hardcoded model list —
        it uses whatever the box is serving.
        """
        from aivc_controller import make_lmstudio_caller, make_ollama_caller
        try:
            from model_scan import discover_models
        except Exception:
            return None
        served = discover_models()  # {"ollama": [...], "lmstudio": [...]}
        want = self._norm_model(requested) if requested else ""

        candidates = []  # (exact?, provider, served_id)
        for prov in ("lmstudio", "ollama"):
            for sid in served.get(prov, []):
                nsid = self._norm_model(sid)
                if not want or nsid == want or want in nsid:
                    candidates.append((nsid != want, prov, sid))
        if not candidates:
            return None
        candidates.sort(key=lambda c: c[0])  # exact matches first
        _, prov, sid = candidates[0]
        caller = (make_lmstudio_caller(model=sid) if prov == "lmstudio"
                  else make_ollama_caller(model=sid))
        return prov, sid, caller

    def _execute_ai_task(self, task_id: str, instruction: str, model_name: str = "",
                         output_dir: str = "", output_filename: str = "",
                         reference_files=None) -> bool:
        """
        Full AI code generation pipeline: prompt → generate → enforce → validate → decompose → test.
        This is the 'brain' that makes local models useful for programming.

        reference_files: small files shown to the model as EXAMPLES to follow —
        a design system to match, an API to conform to, a house style. Showing
        an example beats describing it in prose. Either paths (read from the
        project) or inline {"name":…, "content":…} dicts.
        """
        from canary_tests import CanaryTestRunner

        # 1. Bind the requested model to what this machine ACTUALLY serves.
        # OS principle (model_scan): never trust a hardcoded id — LM Studio
        # serves "qwen/qwen2.5-coder-14b", not "qwen2.5-coder-14b", so a
        # hardcoded short name returns HTTP 400. The resolver picks the real
        # served id + the right backend (lmstudio/ollama).
        resolved = self._resolve_model(model_name)
        if resolved is None:
            avail = ", ".join(self._served_model_ids()) or "none"
            self.vox.speak(
                f"No local model serves '{model_name or 'any'}'. "
                f"Available: {avail}", "ERROR")
            return False
        provider, served_id, ai_call = resolved
        if served_id != model_name:
            self.log(f"[Model] '{model_name or '(default)'}' → {provider}:{served_id}")
        model_name = served_id
        # SINGLE_MODEL memory safety: evict any other resident ollama model so
        # switching models across tasks never stacks them in RAM.
        self._enforce_single_model(served_id if provider == "ollama" else "")
        # RAM pre-flight (the SINGLE_MODEL rule): after eviction, refuse to load
        # a model if free RAM is below the floor — never thrash the machine.
        ram_ok, free_mb = self._ram_ok_for_model()
        if not ram_ok:
            self.vox.speak(f"Skipping {task_id}: low RAM ({free_mb}MB free)", "ERROR")
            return False
        enforcer = ProtocolEnforcer(model_name)

        # Canary gate — verify model quality before trusting it
        if model_name not in self._trusted_models:
            self.vox.speak(f"Running canary test for {model_name}", "INFO")
            try:
                runner = CanaryTestRunner(ai_call_fn=ai_call)
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

        # 3. Generate code — language follows the OUTPUT FILE EXTENSION, not a
        # hardcoded "Python" assumption. A .html/.css/.js task must not be asked
        # for Python (it would produce the wrong language or refuse).
        fname = output_filename if output_filename else f"{task_id}.py"
        ext = Path(fname).suffix.lower()
        _LANG = {
            ".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript",
            ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript",
            ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".svg": "SVG",
            ".php": "PHP", ".cpp": "C++", ".cc": "C++", ".c": "C",
            ".cs": "C#", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
            ".sh": "POSIX shell", ".json": "JSON", ".md": "Markdown",
        }
        lang = _LANG.get(ext, "code")
        is_python = ext == ".py"
        doc_rules = ("- All classes and public methods have docstrings\n"
                     if is_python else "")
        safety = ("- No inline event handlers, no eval, no javascript: URIs\n"
                  if ext in (".html", ".htm", ".svg", ".js", ".ts", ".jsx",
                             ".tsx", ".mjs") else "")
        # TypeScript is cage-checked by `tsc` (strict). The common local-model
        # slip is an untyped parameter/callback arg (TS7006 implicit any), which
        # the cage rightly rejects — so demand explicit types up front.
        ts_rule = ("- Type EVERY parameter, callback argument and return "
                   "explicitly; never leave an implicit any. tsc --noEmit must "
                   "pass.\n" if ext in (".ts", ".tsx") else "")
        # Local models often answer a '.css'/'.html' task with a Python web app
        # (e.g. a Flask server that RETURNS the markup). Forbid that explicitly.
        no_python = ("" if is_python else
                     f"- Write PURE {lang} only. Do NOT write Python. Do NOT use "
                     f"Flask/Django or any server framework. The file is a plain "
                     f"'{fname}' — its entire content must be valid {lang}.\n")
        # Project coherence: show the ACTUAL code of sibling files already
        # written in this project dir. The prose contract fixes NAMES, but files
        # still disagreed on exact signatures/conventions (e.g. compute('+') vs
        # compute('add'), or Task(done=...) the constructor doesn't accept).
        # Real sibling code lets this file match their true interface.
        siblings_ctx = ""
        if output_dir:
            try:
                here = Path(output_dir)
                sibs = []
                for p in sorted(here.glob("*")):
                    if p.is_file() and p.name != fname and p.suffix in (
                            ".py", ".js", ".ts", ".css", ".html"):
                        body = p.read_text(encoding="utf-8", errors="ignore")
                        if body.strip():
                            sibs.append(f"# ==== {p.name} (already written — "
                                        f"use its REAL API) ====\n{body[:1500]}")
                if sibs:
                    siblings_ctx = ("\nEXISTING PROJECT FILES — call/import them "
                                    "using EXACTLY these signatures:\n"
                                    + "\n\n".join(sibs) + "\n")
            except Exception:
                pass
        # An EXAMPLE steers a local model far harder than prose ever does.
        refs_ctx = self._reference_block(reference_files)
        base_prompt = (
            f"You are an HDS agent. Write {lang} for the following task.\n"
            f"Rules:\n"
            f"- Maximum 200 lines\n"
            f"{doc_rules}{safety}{ts_rule}{no_python}"
            f"- Output ONLY the {lang} content for file '{fname}', no explanation, "
            f"no markdown fences\n"
            f"{refs_ctx}{siblings_ctx}\n"
            f"Task: {instruction}"
        )

        # SELF-CORRECTION LOOP. When the cage (or a guard) rejects a generation,
        # feed the EXACT reason back into the next attempt so the model fixes that
        # specific error instead of blindly re-rolling. This is the agent reading
        # its own error and correcting in another iteration. Tunable via
        # HDS_SELF_CORRECT (default 3). Cross-cycle model-escalation still applies
        # on top for the outer retries.
        import os as _os
        import scribe
        tries = max(1, int(_os.environ.get("HDS_SELF_CORRECT", "3")))
        dest_dir = output_dir if output_dir else "storage/generated"
        rel_path = f"{dest_dir}/{fname}"
        gate = (self._trusted_models.get(model_name, "L") or "L").lower()
        feedback = ""

        for attempt in range(1, tries + 1):
            prompt = base_prompt
            if feedback:
                prompt += ("\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED. Output the "
                           "FULL corrected file that fixes EXACTLY this:\n"
                           f"{feedback}\n")
            self.vox.speak(f"Generating {lang} for task {task_id} "
                           f"(attempt {attempt}/{tries})", "INFO")
            try:
                code, timed_out = self._call_with_deadline(ai_call, prompt)
            except Exception as e:
                self.vox.speak(f"AI generation failed: {e}", "ERROR")
                return False
            if timed_out:
                self.vox.speak(f"Model hung >deadline on {task_id} — aborted", "ERROR")
                return False

            # Strip markdown code blocks
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            # 3a. Empty / refusal guard (feedable).
            stripped = code.strip()
            if len(stripped) < 8:
                feedback = "You returned empty output. Output the full file."
                continue
            _refusal = ("i cannot", "i can't", "i'm sorry", "i am sorry", "as an ai",
                        "due to your request", "cannot provide", "i won't", "i will not")
            head = stripped[:120].lower()
            if any(head.startswith(p) or p in head[:60] for p in _refusal):
                self.vox.speak(f"Rejected: model refused task {task_id}", "ERROR")
                return False  # a refusal won't be fixed by re-asking

            # 3b. Language-mismatch guard (feedable).
            mismatch = self._language_mismatch(code, ext)
            if mismatch:
                feedback = f"Output was not valid {lang}: {mismatch}."
                continue

            # 3c. Missing-sibling-import fix (Python projects) — deterministic.
            if is_python and output_dir:
                code = self._add_missing_sibling_imports(code, output_dir, fname)

            # 4. Python pre-check (feedable).
            if is_python:
                try:
                    import ast as _ast
                    _ast.parse(code)
                except SyntaxError as e:
                    feedback = f"Python syntax error: {e}"
                    continue
                level, findings = self.ast_validator.validate(code)
                if level in (SecurityLevel.CRITICAL, SecurityLevel.DANGER):
                    names = ", ".join(sorted({f.get("name", "?") for f in findings}))
                    self.vox.speak(f"Generated code rejected ({level.value}): {names}", "ERROR")
                    return False  # dangerous intent — do NOT invite a retry

            # 5. Write THROUGH THE CAGE (R-19). On rejection, feed the cage's
            # exact verdict back and try again.
            try:
                scribe.execute({"op": "write", "path": rel_path, "content": code},
                               protocol_size=gate if gate in ("s", "m", "l", "xl") else "l")
            except scribe.ScribeError as e:
                feedback = str(e)
                self.vox.speak(f"Cage rejected (attempt {attempt}): {str(e)[:80]}", "ERROR")
                continue
            # 5b. MONTE CARLO. The cage proves the code is safe and well-formed;
            # it cannot prove it runs. Call each function with randomised inputs
            # in the sandbox. A crash is fed back like any cage verdict, so the
            # model fixes the actual traceback. Honest limit: this catches
            # crashes and hangs, not wrong-but-stable logic.
            if is_python:
                verdict = self._monte_carlo(rel_path)
                if verdict is not None and not verdict.get("ok"):
                    fail = verdict["failures"][0]
                    feedback = ("Your code crashed when run with random inputs:\n"
                                f"{fail.get('func')}({fail.get('args')})\n"
                                f"{fail.get('error')}")
                    self.vox.speak(f"Monte Carlo failed (attempt {attempt})", "ERROR")
                    continue
            break  # written, cage-approved and it actually runs
        else:
            self.vox.speak(f"Task {task_id} failed after {tries} self-correct attempts", "ERROR")
            return False

        output_file = self.BASE_DIR / rel_path
        self.vox.speak(f"Code written: {output_file.name}", "INFO")

        # 6. Auto-decompose if too large
        decompose_result = check_and_decompose(str(output_file), model_size="m")
        if decompose_result:
            self.vox.speak(f"Auto-decomposed into {decompose_result.files_created} files", "INFO")

        # 7. (removed) A subprocess `ast.parse` re-check lived here — redundant:
        # step 4 already AST-parses Python, and scribe re-validates on write. It
        # also opened a second exec surface outside SandboxRunner. Dropped.

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
            return self._execute_ai_task(task_id, instruction, model, output_dir,
                                         output_filename,
                                         data.get("reference_files"))

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
