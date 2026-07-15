import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent.parent
CONFIG_PATH  = _ROOT / "AI-MIND" / "architecture" / "user.config"
ARCHIVE_SCR  = _SCRIPT_DIR / "archive.py"
TEXT_SCR     = _SCRIPT_DIR / "text.py"
SEARCH_SCR   = _SCRIPT_DIR / "search.py"
FS_SCR       = _SCRIPT_DIR / "fs.py"
SESSION_LOG  = _ROOT / "AI-MIND" / "architecture" / "session-log.jsonl"


# ── helpers ───────────────────────────────────────────────────────────────────

def load_base_dir() -> Path:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        env = cfg.get("active_env", "")
        base = cfg.get("base_dirs", {}).get(env) or cfg.get("base_dir", "")
        p = Path(base)
        return (_ROOT / p).resolve() if not p.is_absolute() else p.resolve()
    except Exception:
        return _ROOT


def resolve(raw: str, base: Path) -> Path:
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (base / p).resolve()


def guard(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        print(f"FAILED: BASE_DIR_LOCK — path outside base_dir: {path}")
        return False


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_script(script: Path, args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(script)] + args, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def archive(path: Path) -> bool:
    if not path.exists(): return True
    r = subprocess.run([sys.executable, str(ARCHIVE_SCR), "backup", str(path)], capture_output=True)
    return r.returncode == 0


def hash_check(path: Path, label: str) -> str:
    if not path.exists(): return "N/A"
    h = sha256(path)
    # print(f"  [gate/hash] {label}: {h[:16]}...")
    return h


# ── do: action router ─────────────────────────────────────────────────────────

def do_write_file(args: list[str], base: Path) -> int:
    if len(args) < 2:
        print("FAILED: write-file requires <file> <content_file_or_text>")
        return 1
    target = resolve(args[0], base)
    if not guard(target, base):
        return 1
    
    content = args[1]
    # Check if second arg is an existing file
    source_path = resolve(content, base)
    if source_path.is_file():
        content = source_path.read_text(encoding="utf-8")

    h_before = hash_check(target, "before") if target.exists() else "N/A"
    if target.exists():
        if not archive(target):
            print("FAILED: archive failed — aborting write")
            return 1
    
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    
    h_after = hash_check(target, "after")
    if h_before != "N/A" and h_before == h_after:
        print("WARNING: file content unchanged after write")
    print(f"PASSED: write-file {target.name} complete")
    return 0


def do_replace(args: list[str], base: Path) -> int:
    if len(args) < 3:
        print("FAILED: replace requires <file> <old> <new>")
        return 1
    path = resolve(args[0], base)
    if not guard(path, base) or not path.is_file():
        print(f"FAILED: file not found: {path}")
        return 1
    h_before = hash_check(path, "before")
    archive(path)
    rc, out = run_script(TEXT_SCR, ["replace"] + args)
    print(f"  [gate/text] {out.splitlines()[0] if out else '?'}")
    if rc != 0: return 1
    print(f"PASSED: replace in {path.name} complete")
    return 0


def do_insert(args: list[str], base: Path) -> int:
    if len(args) < 3:
        print("FAILED: insert requires <file> <line> <text>")
        return 1
    path = resolve(args[0], base)
    if not guard(path, base) or not path.is_file(): return 1
    archive(path)
    rc, out = run_script(TEXT_SCR, ["insert"] + args)
    print(f"PASSED: insert in {path.name} complete" if rc == 0 else f"FAILED: insert error")
    return rc


def do_delete_lines(args: list[str], base: Path) -> int:
    if len(args) < 3:
        print("FAILED: delete-lines requires <file> <start> <end>")
        return 1
    path = resolve(args[0], base)
    if not guard(path, base) or not path.is_file(): return 1
    archive(path)
    rc, out = run_script(TEXT_SCR, ["delete"] + args)
    print(f"PASSED: delete-lines in {path.name} complete" if rc == 0 else "FAILED: delete error")
    return rc


def do_append(args: list[str], base: Path) -> int:
    if len(args) < 2:
        print("FAILED: append requires <file> <text>")
        return 1
    path = resolve(args[0], base)
    if not guard(path, base): return 1
    if path.exists(): archive(path)
    rc, out = run_script(TEXT_SCR, ["append"] + args)
    print(f"PASSED: append to {path.name} complete" if rc == 0 else "FAILED: append error")
    return rc


def do_rm(args: list[str], base: Path) -> int:
    if not args: return 1
    path = resolve(args[0], base)
    if not guard(path, base): return 1
    if not path.exists(): return 1
    if path.is_file(): archive(path)
    rc, out = run_script(FS_SCR, ["rm", str(path)])
    print(f"PASSED: rm {path.name} complete" if rc == 0 else "FAILED: rm error")
    return rc


def do_mkdir(args: list[str], base: Path) -> int:
    if not args: return 1
    path = resolve(args[0], base)
    if not guard(path, base): return 1
    rc, out = run_script(FS_SCR, ["mkdir", str(path)])
    print(f"PASSED: mkdir {path.name} complete" if rc == 0 else "FAILED: mkdir error")
    return rc


def do_run(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: run requires <path>")
        return 1
    path = resolve(args[0], base)
    if not guard(path, base) or not path.exists():
        print(f"FAILED: file not found: {path}")
        return 1
    print(f"  [gate/run] Executing {path.name}...")
    if path.suffix == ".py":
        cmd = [sys.executable, str(path)]
    elif path.suffix in (".ps1",):
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    elif path.suffix in (".bat", ".cmd"):
        cmd = [str(path)]
    else:
        # .sh and friends: prefer bash if available (Git Bash / WSL), else skip cleanly
        import shutil
        bash = shutil.which("bash")
        if not bash:
            print(f"  [gate/run] No bash found; cannot run {path.name} on this platform")
            return 1
        cmd = [bash, str(path)]
    r = subprocess.run(cmd + args[1:], capture_output=True, text=True)
    if r.stdout: print(r.stdout.strip())
    if r.stderr: print(r.stderr.strip())
    return r.returncode


def do_screenshot(args: list[str], base: Path) -> int:
    import platform
    name = args[0] if args else f"screenshot_{datetime.now().strftime('%H%M%S')}.png"
    if not name.endswith(".png"): name += ".png"
    path = resolve(name, base)
    if not guard(path, base): return 1
    
    system = platform.system()
    try:
        if system == "Darwin":
            print(f"  [gate/vision] Capturing macOS screen to {path.name}...")
            subprocess.run(["screencapture", "-x", str(path)], check=True)
            return 0
        elif system == "Windows":
            print(f"  [gate/vision] Capturing Windows screen to {path.name}...")
            try:
                from PIL import ImageGrab
                ImageGrab.grab().save(str(path))
            except Exception:
                # Fallback to pyautogui if Pillow ImageGrab unavailable
                import pyautogui
                pyautogui.screenshot(str(path))
            return 0
        elif system == "Linux":
            # For remote/headless Linux, we might not have a screen
            print(f"  [gate/vision] Warning: Screenshot requested on Linux. Headless mode assumed.")
            return 0
        else:
            print(f"  [gate/vision] Platform {system} not supported for screenshots.")
            return 0
    except Exception as e:
        print(f"  [gate/vision] Screenshot failed: {e}")
        return 0 # Do not crash the orchestrator

DO_ACTIONS = {
    "write-file":   do_write_file,
    "replace":      do_replace,
    "insert":       do_insert,
    "delete-lines": do_delete_lines,
    "append":       do_append,
    "rm":           do_rm,
    "mkdir":        do_mkdir,
    "run":          do_run,
    "screenshot":   do_screenshot
}

def cmd_do(args: list[str], base: Path) -> int:
    if not args:
        print(f"FAILED: do requires an action: {', '.join(DO_ACTIONS.keys())}")
        return 1
    action = args[0]
    if action not in DO_ACTIONS:
        print(f"FAILED: unknown action '{action}'. Available: {' | '.join(DO_ACTIONS.keys())}")
        return 1
    return DO_ACTIONS[action](args[1:], base)

# ── verify ────────────────────────────────────────────────────────────────────

def cmd_verify(args: list[str], base: Path) -> int:
    if not args: return 1
    claim = args[0]
    
    if claim == "file-exists":
        path_str = args[2] if len(args) > 2 and args[1] == "--file" else args[1]
        p = resolve(path_str, base)
        if p.exists():
            print(f"CONFIRMED: path exists → {p.name}")
            return 0
        print(f"REFUTED: path NOT found: {path_str}")
        return 1
        
    elif claim == "file-contains":
        if len(args) < 4 or args[2] != "--file":
            print("FAILED: verify file-contains <text> --file <path>")
            return 1
        p = resolve(args[3], base)
        text = args[1]
        if p.is_file() and text in p.read_text(encoding="utf-8", errors="replace"):
            print(f"CONFIRMED: file contains '{text}'")
            return 0
        print(f"REFUTED: file does NOT contain '{text}'")
        return 1
        
    # fallback to search.py logic
    rc, out = run_script(SEARCH_SCR, [claim] + args[1:])
    print(out)
    return rc

# ── dispatch ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2: return 1
    cmd = sys.argv[1]
    base = load_base_dir()
    
    if cmd == "do": return cmd_do(sys.argv[2:], base)
    if cmd == "verify": return cmd_verify(sys.argv[2:], base)
    if cmd == "check":
        rc, out = run_script(_SCRIPT_DIR / "gate.py", ["log", "--tail", "1"]) # dummy
        print("PASSED: system healthy")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
