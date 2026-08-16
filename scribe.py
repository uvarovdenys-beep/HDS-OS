#!/usr/bin/env python3
"""
scribe.py
HDS AI-DRIVER — the deterministic executor (writer) layer.

R-19: ZERO_DIRECT_WRITE. The orchestrator (local or cloud LLM) NEVER writes
files directly. It emits a task-script (declarative intent); scribe validates
it and performs the write. This keeps cheap/local models safe: a hallucinating
model can produce a bad task-script, but scribe enforces the invariants.

Task-script format (JSON), single op or list of ops:
    {"op": "write",  "path": "rel/or/abs.py", "content": "..."}
    {"op": "append", "path": "...",           "content": "..."}
    {"op": "delete", "path": "..."}

Invariants enforced:
    R-01: SIZE_LIMIT — refuse files > MAX_LINES lines.
    Path safety — no escaping the project root.
    Post-write — optional host hook (e.g. rebuild an index) for *.py changes.

CLI:
    scribe.py <task_script.json>     # run a task-script file
    scribe.py -                      # read task-script from stdin
    echo '{"op":"write",...}' | scribe.py -
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Union

logger = logging.getLogger("scribe")

ROOT = Path(__file__).resolve().parent   # core/ is the OS root
MAX_LINES = 1000  # R-01

VALID_OPS = {"write", "append", "delete", "patch", "insert"}


class ScribeError(Exception):
    """Raised when a task-script violates an invariant."""


# ── Capability gate: protocol size → what the executor is allowed to do ──
# The cage bars. A thinking-but-disobedient model is pinned to S by the
# diagnostic (protocol_diagnostic._score_to_size); here that pin becomes
# physical: S can only drop files into the sandbox, never touch code, never
# delete. Reasoning is free; reach is bounded.
_SIZE_ORDER = {"s": 0, "m": 1, "l": 2, "xl": 3}
SANDBOX_ROOTS = ("storage", "ai-mind/tasks")   # S may write only here
CODE_DIRS = ("agent", "scripts")                # writing here = touching code

# Extensions treated as executable code (capability + content gating apply).
# Adding a language here WITHOUT a validator in CONTENT_VALIDATORS makes scribe
# default-DENY writes of that language — the cage never leaks silently.
CODE_EXTS = (".py", ".sh", ".js", ".ts", ".tsx", ".jsx",
             ".go", ".rs", ".rb", ".php", ".c", ".cpp", ".cc", ".hpp",
             ".cs", ".java",
             ".html", ".htm",    # injection surface: inline <script> bypasses JS gate
             ".svg", ".svgz")   # SVG also allows <script> — same hole
                                 # without this. Validator scans embedded scripts.

# Optional callback run after a successful .py write (e.g. rebuild an index).
# Keeps core self-contained: the host registers its own hook, core imports
# nothing outside itself.
_post_write_hook = None


# Once sealed, the cage geometry (root, sandbox, code dirs) is frozen for the
# life of the process. Closes the hole where any in-process code could call
# configure(root="/") and silently relocate the cage after startup.
_sealed = False


def seal():
    """Freeze the cage configuration. Irreversible for this process.

    Call after the last configure() at startup; later configure() raises.
    """
    global _sealed
    _sealed = True


def configure(root=None, sandbox_roots=None, code_dirs=None,
              code_exts=None, max_lines=None):
    """Adapt the cage to a host project's layout. Call once at startup.

    All args optional; unset ones keep their defaults. This is what makes core
    drop-in: a new project sets its own sandbox/code dirs instead of HDS's.
    After seal(), reconfiguration is refused.
    """
    global ROOT, SANDBOX_ROOTS, CODE_DIRS, CODE_EXTS, MAX_LINES
    if _sealed:
        raise ScribeError("R-SEAL: cage configuration is sealed — "
                          "configure() refused after seal()")
    if root is not None:
        ROOT = Path(root).resolve()
    if sandbox_roots is not None:
        SANDBOX_ROOTS = tuple(sandbox_roots)
    if code_dirs is not None:
        CODE_DIRS = tuple(code_dirs)
    if code_exts is not None:
        CODE_EXTS = tuple(code_exts)
    if max_lines is not None:
        MAX_LINES = int(max_lines)


def set_post_write_hook(fn):
    """Register a callable run after a successful .py write (or None to clear).

    Signature: fn(written_paths: list[str]) -> None. Errors are swallowed so a
    hook never breaks a write.
    """
    global _post_write_hook
    _post_write_hook = fn


def _is_code(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return path.suffix in CODE_EXTS or rel.split("/", 1)[0] in CODE_DIRS


def _in_sandbox(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel == r or rel.startswith(r + "/") for r in SANDBOX_ROOTS)


def _check_permission(action: str, path: Path, size: str):
    """Enforce capability by protocol size. size=None ⇒ trusted system call."""
    if size is None:
        return
    lvl = _SIZE_ORDER.get(size.lower())
    if lvl is None:
        raise ScribeError(f"unknown protocol size '{size}'")
    # delete is destructive — XL only
    if action == "delete" and lvl < _SIZE_ORDER["xl"]:
        raise ScribeError(f"R-CAP: protocol '{size}' may not delete (XL required)")
    # writing/altering code — L or higher
    if _is_code(path) and lvl < _SIZE_ORDER["l"]:
        raise ScribeError(f"R-CAP: protocol '{size}' may not write code {path.name} (L required)")
    # S is confined to the sandbox
    if lvl == _SIZE_ORDER["s"] and not _in_sandbox(path):
        raise ScribeError(f"R-CAP: protocol 's' may only write under {SANDBOX_ROOTS}")


_CAGE_KERNEL = frozenset({
    "scribe.py", "ast_validator.py", "write_path_audit.py", "events.py",
})

def _resolve(path: str) -> Path:
    """Resolve a task-script path against ROOT and forbid escaping it.
    Also forbids overwriting the cage kernel (scribe, ast_validator, …)
    regardless of protocol_size — even trusted system calls cannot
    self-modify the enforcement layer.
    """
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    p = p.resolve()
    if ROOT not in p.parents and p != ROOT:
        raise ScribeError(f"R-PATH: '{path}' escapes project root {ROOT}")
    # Cage kernel is write-protected at all levels — no self-modification.
    # Covers both ROOT/scribe.py and agent/scribe.py (any subpath).
    if p.name in _CAGE_KERNEL:
        raise ScribeError(
            f"R-KERNEL: '{p.name}' is a protected cage file — writes forbidden")
    return p


def _check_size(content: str, path: Path):
    """R-01: refuse oversized files."""
    n = content.count("\n") + (0 if content.endswith("\n") or not content else 1)
    if n > MAX_LINES:
        raise ScribeError(f"R-01: '{path.name}' has {n} lines > {MAX_LINES} limit")


def _check_content(content: str, path: Path, size: str):
    """Level-2 gate: AST-scan Python the model wants to write.

    Reuses core's ast_validator (do not reimplement). For trusted system
    calls (size=None) the scan is skipped; for AI-driven writes, CRITICAL or
    DANGER constructs (eval/exec/subprocess/__import__/...) are rejected — the
    model's reasoning cannot smuggle a dangerous payload past the executor.
    """
    if size is None:
        return  # trusted system call
    ext = path.suffix
    if ext not in CODE_EXTS:
        return  # plain data/text — no content gate
    validator = _content_validator(ext)
    if validator is None:
        # Code language with no trusted verifier → default DENY (never leak).
        raise ScribeError(
            f"R-AST: no content validator for '{ext}' — cannot verify {path.name}. "
            f"Add a validator before writing this language.")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lang import LangReject
    try:
        validator(content, path)
    except LangReject as e:
        raise ScribeError(f"R-AST: {e}")


def _content_validator(ext: str):
    """Return the per-language content validator from the lang/ registry.

    Capability is granted by code only: a `lang/<x>/validator.py` that calls
    `register(...)`. Extensions in CODE_EXTS without a registered validator stay
    default-denied (fail-closed). No data file can add a language here.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import lang
    return lang.get_validator(ext)


def _apply(op: Dict, size: str = None) -> str:
    """Apply a single task-script op. Returns a one-line result string."""
    action = op.get("op")
    if action not in VALID_OPS:
        raise ScribeError(f"unknown op '{action}', expected one of {sorted(VALID_OPS)}")

    if action == "delete":
        path = _resolve(op["path"])
        _check_permission(action, path, size)
        if path.exists():
            path.unlink()
            return f"deleted {path.relative_to(ROOT)}"
        return f"skip (absent) {path.relative_to(ROOT)}"

    content = op.get("content", "")
    path = _resolve(op["path"])
    _check_permission(action, path, size)

    if action == "append":
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        content = existing + content

    # SURGICAL EDITS. `patch` replaces exactly one function/class (or an explicit
    # line range); `insert` adds after one. Only those lines change — the rest of
    # the file, its imports and comments, are untouched. The RESULT is then run
    # through the full size + content gates below, so surgery never weakens the
    # cage: a patch that would produce an invalid file is refused outright.
    if action in ("patch", "insert"):
        if not path.exists():
            raise ScribeError(f"R-PATCH: '{path.name}' does not exist — "
                              f"use 'write' to create a file")
        source = path.read_text(encoding="utf-8")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import patcher
        try:
            if action == "patch":
                if "target" in op:
                    start, end = patcher.locate(source, op["target"])
                else:
                    start, end = int(op["start"]), int(op["end"])
                content = patcher.replace_lines(source, start, end, content)
                span = f"{start}-{end}"
            else:
                if "after_target" in op:
                    _, line = patcher.locate(source, op["after_target"])
                else:
                    line = int(op.get("after_line", 0))
                content = patcher.insert_after(source, line, content)
                span = f"after {line}"
        except patcher.PatchError as e:
            raise ScribeError(f"R-PATCH: {e}")
        _check_size(content, path)
        _check_content(content, path, size)
        path.write_text(content, encoding="utf-8")
        return f"{action} {path.relative_to(ROOT)} lines {span}"

    _check_size(content, path)
    _check_content(content, path, size)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"{action} {path.relative_to(ROOT)} ({content.count(chr(10)) + 1} lines)"


def execute(task_script: Union[Dict, List[Dict]], protocol_size: str = None) -> List[str]:
    """Execute a task-script (single op dict or list of ops). Raises on violation.

    protocol_size (s/m/l/xl) is the capability gate from the diagnostic. Pass it
    for any AI-driven write so the model's reach matches its earned trust. Leave
    None for trusted system/local calls (no capability restriction).
    """
    ops = task_script if isinstance(task_script, list) else [task_script]
    results = [_apply(op, protocol_size) for op in ops]

    written = [op["path"] for op in ops if str(op.get("path", "")).endswith(".py")
               and op.get("op") != "delete"]

    # Announce the write on the event bus (sinks: voice/log/metrics — optional).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from events import emit
        emit("write_done", message=f"{len(results)} op(s) applied",
             level="INFO", paths=[op.get("path") for op in ops])
    except Exception as _e:
        logger.warning("event bus unavailable: %s", _e)

    # Optional host hook (e.g. rebuild an index). core imports nothing external.
    if written and _post_write_hook is not None:
        try:
            _post_write_hook(written)
            results.append("post-write hook ran")
        except Exception as e:
            results.append(f"post-write hook skipped: {e}")
    elif written:
        # .py files written but no hook registered — index may be stale.
        # This is expected when scribe is used directly (without orchestrator);
        # log so the operator knows the index won't auto-rebuild.
        logger.debug("post-write hook not set; %d .py path(s) written, "
                     "call set_post_write_hook() if index rebuild is needed",
                     len(written))

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: scribe.py <task_script.json | -> [--size s|m|l|xl]")
        sys.exit(1)

    size = None
    if "--size" in sys.argv:
        i = sys.argv.index("--size")
        if i + 1 < len(sys.argv):
            size = sys.argv[i + 1]

    src = sys.argv[1]
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")

    try:
        task_script = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ invalid task-script JSON: {e}")
        sys.exit(1)

    try:
        for line in execute(task_script, protocol_size=size):
            print(f"✅ {line}")
    except (ScribeError, KeyError) as e:
        print(f"❌ R-19 reject: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
