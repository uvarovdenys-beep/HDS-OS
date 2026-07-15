#!/usr/bin/env python3
"""pipeline_helpers.py — pure helpers of the AI pipeline, split out under R-300.

None of these drive the generation flow; they answer isolated questions:
what does the box serve, is there RAM for a model, is this output the right
language, what are the reference examples, where are the missing imports.
Keeping them here holds agent_ai_pipeline.py to the flow itself.

Mixed into HDSAgent through AICodePipelineMixin — the methods resolve by MRO,
so no delegation shims are needed.

NOTE these are OS-INTERNAL modules: they read os.environ for tunables
(HDS_MIN_FREE_MB, HDS_GEN_DEADLINE). The cage's Python validator rejects `os`
in AI-GENERATED payloads by design; OS internals are written as trusted system
calls instead. That distinction is deliberate, not a bypass.
"""
from pathlib import Path


class PipelineHelpersMixin:
    """Stateless helpers used by the AI code-generation pipeline."""

    # Reference files are shown to the model verbatim — keep them small so the
    # prompt stays inside the context window of a modest local model.
    REF_MAX_FILES = 4
    REF_MAX_CHARS = 4000
    REF_TOTAL_CHARS = 12000

    @staticmethod
    def _add_missing_sibling_imports(code: str, output_dir: str, fname: str) -> str:
        """Prepend `import <sibling>` for sibling modules referenced as
        `<sibling>.attr` but never imported. Fixes the common LLM slip where a
        file uses opcodes.PUSH / geo.area but forgets the import line.
        """
        import re as _re
        try:
            here = Path(output_dir)
            sibs = [p.stem for p in here.glob("*.py")
                    if p.name != fname and p.stem.isidentifier()]
        except Exception:
            return code
        missing = []
        for s in sibs:
            used = _re.search(rf'\b{_re.escape(s)}\.\w', code)
            imported = _re.search(rf'(?m)^\s*(import\s+{_re.escape(s)}\b|'
                                  rf'from\s+{_re.escape(s)}\s+import)', code)
            if used and not imported:
                missing.append(s)
        if not missing:
            return code
        header = "".join(f"import {s}\n" for s in missing)
        # insert after any leading module docstring / existing imports block
        lines = code.split("\n")
        i = 0
        if lines and lines[0].lstrip().startswith(('"""', "'''")):
            q = lines[0].lstrip()[:3]
            i = 1
            while i < len(lines) and q not in lines[i]:
                i += 1
            i += 1
        while i < len(lines) and (lines[i].startswith(("import ", "from ")) or not lines[i].strip()):
            i += 1
        return "\n".join(lines[:i] + [header.rstrip()] + lines[i:])

    @staticmethod
    def _language_mismatch(code: str, ext: str):
        """Cheap check that generated output is the requested language.

        Returns a reason string if the content is obviously the wrong language
        (e.g. Python emitted for a .css/.html task), else None. Guards the
        languages that have NO cage validator (.css/.md/.txt) where a wrong-
        language write would otherwise slip through silently.
        """
        import re as _re
        if ext in (".py", ".md", ".txt", ".json", ""):
            return None
        # Python-specific top-level constructs never appear in CSS/HTML/JS/etc.
        if _re.search(r'(?m)^\s*(from\s+[\w.]+\s+import\s|def\s+\w+\s*\(|'
                      r'@app\.route|if\s+__name__\s*==)', code):
            return "contains Python code"
        if ext == ".css" and "{" not in code:
            return "no CSS rules"
        if ext in (".html", ".htm", ".svg"):
            s = code.lstrip()
            # Must BEGIN with a tag/doctype — a refusal that merely mentions a
            # <svg> example mid-prose (as one model did) must not pass.
            if not s.startswith("<"):
                return "does not start with a tag (prose?)"
        return None

    def _reference_block(self, reference_files):
        """Render reference files as an EXAMPLE block for the prompt.

        Accepts paths (relative to the OS root) or inline dicts
        {"name":…, "content":…}. Oversized/unreadable entries are skipped —
        a reference must never break a build.
        """
        if not reference_files:
            return ""
        if isinstance(reference_files, (str, dict)):
            reference_files = [reference_files]
        parts, total = [], 0
        for ref in list(reference_files)[:self.REF_MAX_FILES]:
            try:
                if isinstance(ref, dict):
                    name = ref.get("name", "reference")
                    body = ref.get("content", "")
                else:
                    p = Path(ref)
                    if not p.is_absolute():
                        p = self.BASE_DIR / p
                    name, body = p.name, p.read_text(encoding="utf-8",
                                                     errors="ignore")
                body = (body or "").strip()
                if not body:
                    continue
                if len(body) > self.REF_MAX_CHARS:
                    body = body[:self.REF_MAX_CHARS] + "\n/* …truncated… */"
                if total + len(body) > self.REF_TOTAL_CHARS:
                    break
                total += len(body)
                parts.append(f"# ---- {name} ----\n{body}")
            except Exception:
                continue  # a bad reference is skipped, never fatal
        if not parts:
            return ""
        return ("\nREFERENCE EXAMPLE — match this style, structure and naming "
                "closely (do NOT copy it verbatim unless asked):\n"
                + "\n\n".join(parts) + "\n")

    def _monte_carlo(self, rel_path):
        """Randomised smoke test of a just-written Python file.

        Returns the verdict dict, or None when verification is unavailable —
        an absent verifier must never fail a build that the cage approved.
        Disable with HDS_MONTECARLO=0.
        """
        import os as _os
        if _os.environ.get("HDS_MONTECARLO", "1") == "0":
            return None
        try:
            import montecarlo
            trials = int(_os.environ.get("HDS_MC_TRIALS", "20"))
            verdict = montecarlo.verify_module(self.BASE_DIR / rel_path, trials=trials)
        except Exception:
            return None
        if verdict.get("checked"):
            self.log("[MonteCarlo] " + montecarlo.summarise(verdict))
        return verdict

    @staticmethod
    def _free_ram_mb():
        """Free RAM in MB via the allowlisted sysmon (keeps this file
        subprocess-free). None if unmeasurable."""
        try:
            from sysmon import free_ram_mb
        except Exception:
            try:
                from .sysmon import free_ram_mb
            except Exception:
                return None
        return free_ram_mb()

    def _ram_ok_for_model(self):
        """Pre-flight the SINGLE_MODEL rule: refuse to load a model when free RAM
        is below HDS_MIN_FREE_MB (default 800) so we never thrash the box.
        Unmeasurable → allow (never block on inability to measure)."""
        import os as _os
        free = self._free_ram_mb()
        floor = int(_os.environ.get("HDS_MIN_FREE_MB", "800"))
        if free is not None and free < floor:
            try:
                from events import emit
                emit("low_memory", level="WARNING",
                     message=f"free RAM {free}MB < floor {floor}MB — skipping "
                             f"model load to avoid thrashing")
            except Exception:
                pass
            return False, free
        return True, free

    @staticmethod
    def _norm_model(name: str) -> str:
        """Normalize a model id for matching: drop vendor/ prefix, unify :/- ."""
        return name.lower().split("/")[-1].replace(":", "-")

    def _served_model_ids(self):
        """Every model id this machine serves right now (ollama + lmstudio)."""
        try:
            from model_scan import discover_models
        except Exception:
            return []
        ids = []
        for models in discover_models().values():
            ids.extend(models)
        return ids

    @staticmethod
    def _call_with_deadline(fn, arg, deadline=None):
        """Run fn(arg) with a hard wall-clock deadline (default HDS_GEN_DEADLINE
        or 300s). Returns (result, timed_out). On timeout the worker thread is
        a daemon and is abandoned — the caller must treat the task as failed,
        never freeze. This is the orchestrator's hang control for local models.
        """
        import os as _os, threading
        if deadline is None:
            deadline = int(_os.environ.get("HDS_GEN_DEADLINE", "300"))
        box = {}
        def _run():
            try:
                box["v"] = fn(arg)
            except Exception as e:  # surfaced to caller after join
                box["e"] = e
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(deadline)
        if t.is_alive():
            return None, True
        if "e" in box:
            raise box["e"]
        return box.get("v", ""), False

    @staticmethod
    def _enforce_single_model(keep_id: str = ""):
        """SINGLE_MODEL: unload every RESIDENT ollama model except keep_id.

        Ollama keeps each requested model in RAM (default keep_alive 5 min), so
        switching models between tasks stacks them and exhausts memory. Before a
        generation we evict the others (POST keep_alive:0) so only one stays
        resident. Best-effort and silent — never blocks generation.
        """
        import requests
        try:
            ps = requests.get("http://127.0.0.1:11434/api/ps", timeout=3).json()
        except Exception:
            return
        keep = keep_id.split("/")[-1]
        for m in ps.get("models", []):
            name = m.get("name") or m.get("model") or ""
            if name and name != keep_id and name.split("/")[-1] != keep:
                try:
                    requests.post("http://127.0.0.1:11434/api/generate",
                                  json={"model": name, "keep_alive": 0},
                                  timeout=5)
                except Exception:
                    pass
