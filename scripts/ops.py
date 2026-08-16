"""
ops.py — HDS 4.3 Operations Subagent
The high-level orchestrator. Chains atomic operations with auto-archive,
SHA256 hash verification, and drift detection. AI calls ops.py once and
gets a single PASSED/FAILED — no manual multi-step planning needed.

Usage: python AI-MIND/scripts/ops.py <command> [args]

Commands:
  plan    <operation> [args]       Preview steps WITHOUT executing
  run     <operation> [args]       Execute operation with archive+hash guard
  hash    <file>                   Print SHA256 of file
  guard   [--files f1 f2 ...]      Check hash drift on critical files
  register [--files f1 f2 ...]     Register/update hash baseline
  status                           Show hash registry status

Built-in operations for `run` / `plan`:
  safe-replace <file> <old> <new> [--regex] [--all]
  safe-delete  <file>
  safe-copy    <src> <dst>
  safe-move    <src> <dst>
  archive-old  <file>              Archive + rename with timestamp suffix
  replace-file <file> <new_content_file>  Replace entire file contents safely
"""

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).resolve().parents[2] / "AI-MIND" / "architecture" / "user.config"
ARCHIVE_SCRIPT = Path(__file__).resolve().parent / "archive.py"
TEXT_SCRIPT = Path(__file__).resolve().parent / "text.py"
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "AI-MIND" / "architecture" / "hash-registry.json"

CRITICAL_FILES = [
    "main.md",
    "AI-MIND/architecture/user.config",
    "AI-MIND/architecture/manifest.md",
    "AI-MIND/architecture/project-map.md",
]


# ── core helpers ──────────────────────────────────────────────────────────────

def load_base_dir() -> Path:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        env = cfg.get("active_env", "")
        base = cfg.get("base_dirs", {}).get(env) or cfg.get("base_dir", "")
        return Path(base).resolve() if base else Path(__file__).resolve().parents[2]
    except Exception:
        return Path(__file__).resolve().parents[2]


def resolve(raw: str, base: Path) -> Path:
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (base / p).resolve()


def guard_lock(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        print(f"FAILED: BASE_DIR_LOCK — outside base_dir: {path}")
        return False


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_archive(path: Path) -> bool:
    if not ARCHIVE_SCRIPT.exists():
        return True
    r = subprocess.run(
        [sys.executable, str(ARCHIVE_SCRIPT), "backup", str(path)],
        capture_output=True, text=True
    )
    line = (r.stdout.strip().splitlines() or [""])[0]
    ok = line.startswith("PASSED")
    print(f"  [archive] {line}")
    return ok


def run_text(args: list[str]) -> tuple[int, str]:
    if not TEXT_SCRIPT.exists():
        return 1, "FAILED: text.py not found"
    r = subprocess.run(
        [sys.executable, str(TEXT_SCRIPT)] + args,
        capture_output=True, text=True
    )
    return r.returncode, r.stdout.strip()


def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_registry(reg: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── plan / run engine ─────────────────────────────────────────────────────────

def build_steps(operation: str, op_args: list[str], base: Path) -> Optional[list[dict]]:
    """Return ordered list of step dicts for a named operation."""

    if operation == "safe-replace":
        # args: <file> <old> <new> [--regex] [--all]
        if len(op_args) < 3:
            print("FAILED: safe-replace requires <file> <old> <new>")
            return None
        file_path = resolve(op_args[0], base)
        return [
            {"desc": f"Verify file exists: {op_args[0]}", "action": "exists_check", "path": file_path},
            {"desc": f"Compute SHA256 before: {file_path.name}", "action": "hash_before", "path": file_path},
            {"desc": f"Archive backup: {file_path.name}", "action": "archive", "path": file_path},
            {"desc": f"Replace text in {file_path.name}", "action": "text_replace",
             "text_args": op_args},
            {"desc": f"Compute SHA256 after: {file_path.name}", "action": "hash_after", "path": file_path},
            {"desc": "Verify hash changed (mutation confirmed)", "action": "hash_diff"},
        ]

    if operation == "safe-delete":
        if not op_args:
            print("FAILED: safe-delete requires <file>")
            return None
        file_path = resolve(op_args[0], base)
        return [
            {"desc": f"Verify file exists: {op_args[0]}", "action": "exists_check", "path": file_path},
            {"desc": f"Archive backup: {file_path.name}", "action": "archive", "path": file_path},
            {"desc": f"Delete file: {file_path.name}", "action": "delete_file", "path": file_path},
        ]

    if operation == "safe-copy":
        if len(op_args) < 2:
            print("FAILED: safe-copy requires <src> <dst>")
            return None
        src, dst = resolve(op_args[0], base), resolve(op_args[1], base)
        return [
            {"desc": f"Verify source exists: {op_args[0]}", "action": "exists_check", "path": src},
            {"desc": f"Copy {src.name} → {dst}", "action": "copy_file", "src": src, "dst": dst},
            {"desc": f"Verify destination hash matches source", "action": "hash_copy_verify",
             "src": src, "dst": dst},
        ]

    if operation == "safe-move":
        if len(op_args) < 2:
            print("FAILED: safe-move requires <src> <dst>")
            return None
        src, dst = resolve(op_args[0], base), resolve(op_args[1], base)
        return [
            {"desc": f"Verify source exists: {op_args[0]}", "action": "exists_check", "path": src},
            {"desc": f"Archive backup of source: {src.name}", "action": "archive", "path": src},
            {"desc": f"Move {src.name} → {dst}", "action": "move_file", "src": src, "dst": dst},
        ]

    if operation == "archive-old":
        if not op_args:
            print("FAILED: archive-old requires <file>")
            return None
        file_path = resolve(op_args[0], base)
        new_name = file_path.with_name(file_path.stem + f"_{timestamp()}" + file_path.suffix)
        return [
            {"desc": f"Verify file exists: {op_args[0]}", "action": "exists_check", "path": file_path},
            {"desc": f"Archive backup: {file_path.name}", "action": "archive", "path": file_path},
            {"desc": f"Rename to timestamped: {new_name.name}", "action": "move_file",
             "src": file_path, "dst": new_name},
        ]

    if operation == "replace-file":
        if len(op_args) < 2:
            print("FAILED: replace-file requires <file> <new_content_file>")
            return None
        file_path = resolve(op_args[0], base)
        content_file = resolve(op_args[1], base)
        return [
            {"desc": f"Verify target exists: {op_args[0]}", "action": "exists_check", "path": file_path},
            {"desc": f"Verify content source exists: {op_args[1]}", "action": "exists_check",
             "path": content_file},
            {"desc": f"Archive backup: {file_path.name}", "action": "archive", "path": file_path},
            {"desc": f"Replace file contents: {file_path.name}", "action": "replace_file_contents",
             "path": file_path, "content_file": content_file},
            {"desc": f"Verify SHA256 of result", "action": "hash_after", "path": file_path},
        ]

    print(f"FAILED: unknown operation '{operation}'")
    print("  Available: safe-replace | safe-delete | safe-copy | safe-move | archive-old | replace-file")
    return None


def execute_steps(steps: list[dict]) -> int:
    state: dict = {}
    for i, step in enumerate(steps, 1):
        action = step["action"]
        print(f"  [{i}/{len(steps)}] {step['desc']}")

        if action == "exists_check":
            if not step["path"].exists():
                print(f"FAILED: file does not exist: {step['path']}")
                return 1

        elif action == "hash_before":
            state["hash_before"] = sha256(step["path"])
            print(f"         SHA256 before: {state['hash_before'][:16]}…")

        elif action == "hash_after":
            state["hash_after"] = sha256(step["path"])
            print(f"         SHA256 after:  {state['hash_after'][:16]}…")

        elif action == "hash_diff":
            if state.get("hash_before") == state.get("hash_after"):
                print("WARNING: hash unchanged — replace may have had no effect")
            else:
                print("         hash changed ✓")

        elif action == "archive":
            if not run_archive(step["path"]):
                print("FAILED: archive backup failed — aborting")
                return 1

        elif action == "text_replace":
            code, out = run_text(["replace"] + step["text_args"])
            print(f"         {out}")
            if code != 0:
                return 1

        elif action == "delete_file":
            step["path"].unlink(missing_ok=True)
            print(f"         deleted ✓")

        elif action == "copy_file":
            step["dst"].parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(step["src"], step["dst"])

        elif action == "hash_copy_verify":
            if sha256(step["src"]) != sha256(step["dst"]):
                print("FAILED: copy integrity check failed")
                return 1
            print("         copy integrity OK ✓")

        elif action == "move_file":
            step["dst"].parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(step["src"]), str(step["dst"]))
            print(f"         moved ✓")

        elif action == "replace_file_contents":
            content = step["content_file"].read_bytes()
            step["path"].write_bytes(content)
            print(f"         written ✓")

    return 0


# ── top-level commands ────────────────────────────────────────────────────────

def cmd_plan(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: plan requires <operation> [args]")
        return 1
    steps = build_steps(args[0], args[1:], base)
    if steps is None:
        return 1
    print(f"PASSED: plan for '{args[0]}' — {len(steps)} step(s)")
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s['desc']}")
    print("  (dry-run — nothing executed)")
    return 0


def cmd_run(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: run requires <operation> [args]")
        return 1
    operation = args[0]
    steps = build_steps(operation, args[1:], base)
    if steps is None:
        return 1
    print(f"PASSED: executing '{operation}' ({len(steps)} steps)")
    rc = execute_steps(steps)
    if rc == 0:
        print(f"PASSED: '{operation}' completed successfully")
    else:
        print(f"FAILED: '{operation}' aborted")
    return rc


def cmd_hash(args: list[str], base: Path) -> int:
    brief = "--brief" in args or "-b" in args
    clean = [a for a in args if a not in ("--brief", "-b")]
    if not clean:
        print("FAILED: hash requires <file>")
        return 1
    path = resolve(clean[0], base)
    if not path.is_file():
        print(f"FAILED: file not found: {path}")
        return 1
    h = sha256(path)
    if brief:
        print(h)
    else:
        print(f"PASSED: SHA256 {path.name}")
        print(f"  {h}")
    return 0


def cmd_register(args: list[str], base: Path) -> int:
    files_raw: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--files":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                files_raw.append(args[i]); i += 1
        else:
            i += 1
    if not files_raw:
        files_raw = CRITICAL_FILES

    reg = load_registry()
    reg.setdefault("registered_at", datetime.now().isoformat(timespec="seconds"))
    reg["updated_at"] = datetime.now().isoformat(timespec="seconds")
    reg.setdefault("files", {})

    registered = 0
    for raw in files_raw:
        p = resolve(raw, base)
        if not p.is_file():
            print(f"  SKIP: not found — {raw}")
            continue
        h = sha256(p)
        try:
            rel = str(p.relative_to(base))
        except ValueError:
            rel = raw
        reg["files"][rel] = {"sha256": h, "updated_at": datetime.now().isoformat(timespec="seconds")}
        print(f"  registered: {rel} → {h[:16]}…")
        registered += 1

    save_registry(reg)
    print(f"PASSED: registered {registered} file(s) in hash-registry.json")
    return 0


def cmd_guard(args: list[str], base: Path) -> int:
    reg = load_registry()
    if not reg.get("files"):
        print("WARNING: hash registry is empty — run `ops.py register` first")
        return 0

    files_to_check = list(reg["files"].keys())
    drifted = []
    missing = []
    ok = []

    for rel in files_to_check:
        p = resolve(rel, base)
        if not p.exists():
            missing.append(rel)
            continue
        current = sha256(p)
        expected = reg["files"][rel]["sha256"]
        if current != expected:
            drifted.append((rel, expected[:16], current[:16]))
        else:
            ok.append(rel)

    status = "clean" if not drifted and not missing else "DRIFT_DETECTED"
    prefix = "PASSED" if status == "clean" else "WARNING"
    print(f"{prefix}: hash-guard status={status}")
    print(f"  OK:      {len(ok)}")
    print(f"  drifted: {len(drifted)}")
    print(f"  missing: {len(missing)}")
    for rel, exp, cur in drifted:
        print(f"  [DRIFT] {rel}")
        print(f"          expected: {exp}…")
        print(f"          current:  {cur}…")
    for rel in missing:
        print(f"  [MISSING] {rel}")
    return 0 if status == "clean" else 1


def cmd_status(args: list[str], base: Path) -> int:
    brief = "--brief" in args or "-b" in args
    reg = load_registry()
    if not reg.get("files"):
        if not brief:
            print("PASSED: hash registry — empty (run `register` first)")
        return 0
    if not brief:
        print(f"PASSED: hash registry — {len(reg['files'])} file(s)")
        print(f"  updated: {reg.get('updated_at', 'unknown')}")
    for rel, meta in reg["files"].items():
        if brief:
            print(f"{rel}:{meta['sha256']}")
        else:
            print(f"  {rel}: {meta['sha256'][:16]}… (set {meta.get('updated_at','?')})")
    return 0


# ── dispatch ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "plan":     cmd_plan,
    "run":      cmd_run,
    "hash":     cmd_hash,
    "register": cmd_register,
    "guard":    cmd_guard,
    "status":   cmd_status,
}


def main() -> int:
    if len(sys.argv) < 2:
        print(f"FAILED: no command. Use: {' | '.join(COMMANDS)}")
        return 1
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"FAILED: unknown command '{cmd}'. Available: {' | '.join(COMMANDS)}")
        return 1
    return COMMANDS[cmd](sys.argv[2:], load_base_dir())


if __name__ == "__main__":
    raise SystemExit(main())
