"""
fs.py — HDS 4.3 File System Operations
Usage: python AI-MIND/scripts/fs.py <command> [args]

Commands:
  mkdir <path>                        Create directory (recursive)
  rm <path>                           Remove file or directory tree
  cp <src> <dst>                      Copy file or directory
  mv <src> <dst>                      Move / rename
  ls <path> [--depth N] [--ext .py]  List directory contents
  tree <path> [--depth N]            ASCII tree view
  stat <path>                         File metadata (size, lines, mtime)
  exists <path>                       Check existence → PASSED/FAILED
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "AI-MIND" / "architecture" / "user.config"


# ── helpers ──────────────────────────────────────────────────────────────────

def load_base_dir() -> Path:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        env = cfg.get("active_env", "")
        base = cfg.get("base_dirs", {}).get(env) or cfg.get("base_dir", "")
        return Path(base).resolve() if base else Path(__file__).resolve().parents[2]
    except Exception:
        return Path(__file__).resolve().parents[2]


def check_lock(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def guard(path: Path, base: Path) -> bool:
    if not check_lock(path, base):
        print(f"FAILED: BASE_DIR_LOCK — path outside base_dir: {path}")
        return False
    return True


def resolve(raw: str, base: Path) -> Path:
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (base / p).resolve()


def count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    except Exception:
        return -1


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_mkdir(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: mkdir requires <path>")
        return 1
    path = resolve(args[0], base)
    if not guard(path, base):
        return 1
    path.mkdir(parents=True, exist_ok=True)
    print(f"PASSED: directory created → {path}")
    return 0


def cmd_rm(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: rm requires <path>")
        return 1
    path = resolve(args[0], base)
    if not guard(path, base):
        return 1
    if not path.exists():
        print(f"FAILED: path does not exist: {path}")
        return 1
    if path.is_file():
        path.unlink()
        print(f"PASSED: file removed → {path}")
    else:
        shutil.rmtree(path)
        print(f"PASSED: directory removed → {path}")
    return 0


def cmd_cp(args: list[str], base: Path) -> int:
    if len(args) < 2:
        print("FAILED: cp requires <src> <dst>")
        return 1
    src = resolve(args[0], base)
    dst = resolve(args[1], base)
    if not guard(src, base) or not guard(dst, base):
        return 1
    if not src.exists():
        print(f"FAILED: source does not exist: {src}")
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"PASSED: directory copied {src} → {dst}")
    else:
        shutil.copy2(src, dst)
        print(f"PASSED: file copied {src} → {dst}")
    return 0


def cmd_mv(args: list[str], base: Path) -> int:
    if len(args) < 2:
        print("FAILED: mv requires <src> <dst>")
        return 1
    src = resolve(args[0], base)
    dst = resolve(args[1], base)
    if not guard(src, base) or not guard(dst, base):
        return 1
    if not src.exists():
        print(f"FAILED: source does not exist: {src}")
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    print(f"PASSED: moved {src} → {dst}")
    return 0


def cmd_ls(args: list[str], base: Path) -> int:
    path_str = args[0] if args and not args[0].startswith("-") else "."
    depth = 2
    ext_filter: str | None = None
    brief = "--brief" in args or "-b" in args

    i = 1 if args and not args[0].startswith("-") else 0
    while i < len(args):
        if args[i] == "--depth" and i + 1 < len(args):
            depth = int(args[i + 1]); i += 2
        elif args[i] == "--ext" and i + 1 < len(args):
            ext_filter = args[i + 1] if args[i + 1].startswith(".") else "." + args[i + 1]; i += 2
        else:
            i += 1

    path = resolve(path_str, base)
    if not path.is_dir():
        print(f"FAILED: not a directory: {path}")
        return 1

    entries = []
    def walk(p: Path, current_depth: int):
        if current_depth > depth:
            return
        for child in sorted(p.iterdir()):
            if child.name in {"__pycache__", ".DS_Store", ".git"}:
                continue
            if ext_filter and child.is_file() and child.suffix != ext_filter:
                continue
            rel = child.relative_to(path)
            if brief:
                entries.append(str(rel))
            else:
                kind = "dir" if child.is_dir() else "file"
                size = f"{child.stat().st_size}B" if child.is_file() else ""
                entries.append(f"{'  ' * (current_depth - 1)}- `{rel}` ({kind}) {size}".rstrip())
            if child.is_dir():
                walk(child, current_depth + 1)

    walk(path, 1)
    if not brief:
        print(f"PASSED: {len(entries)} entries in {path}")
    for e in entries:
        print(e)
    return 0


def cmd_tree(args: list[str], base: Path) -> int:
    path_str = args[0] if args and not args[0].startswith("-") else "."
    depth = 3
    brief = "--brief" in args or "-b" in args
    if "--depth" in args:
        idx = args.index("--depth")
        if idx + 1 < len(args):
            depth = int(args[idx + 1])

    path = resolve(path_str, base)
    if not path.is_dir():
        print(f"FAILED: not a directory: {path}")
        return 1

    lines = [str(path)] if not brief else []

    def walk(p: Path, prefix: str, current_depth: int):
        if current_depth > depth:
            return
        children = sorted([c for c in p.iterdir() if c.name not in {"__pycache__", ".DS_Store", ".git"}])
        for i, child in enumerate(children):
            if brief:
                lines.append(str(child.relative_to(path)))
            else:
                connector = "└── " if i == len(children) - 1 else "├── "
                lines.append(prefix + connector + child.name + ("/" if child.is_dir() else ""))
            if child.is_dir():
                extension = "    " if i == len(children) - 1 else "│   "
                walk(child, prefix + extension if not brief else "", current_depth + 1)

    walk(path, "", 1)
    if not brief:
        print(f"PASSED: tree depth={depth}")
    for l in lines:
        print(l)
    return 0


def cmd_stat(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: stat requires <path>")
        return 1
    path = resolve(args[0], base)
    if not path.exists():
        print(f"FAILED: path does not exist: {path}")
        return 1
    s = path.stat()
    mtime = datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    if path.is_file():
        lines = count_lines(path)
        print(f"PASSED: stat for {path.name}")
        print(f"  type:  file")
        print(f"  size:  {s.st_size} bytes")
        print(f"  lines: {lines}")
        print(f"  mtime: {mtime}")
    else:
        count = sum(1 for _ in path.rglob("*") if _.is_file())
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        print(f"PASSED: stat for {path.name}/")
        print(f"  type:  directory")
        print(f"  files: {count}")
        print(f"  total: {total} bytes")
        print(f"  mtime: {mtime}")
    return 0


def cmd_exists(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: exists requires <path>")
        return 1
    path = resolve(args[0], base)
    if path.exists():
        kind = "directory" if path.is_dir() else "file"
        print(f"PASSED: exists ({kind}) → {path}")
        return 0
    else:
        print(f"FAILED: does not exist → {path}")
        return 1


# ── dispatch ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "mkdir": cmd_mkdir,
    "rm":    cmd_rm,
    "cp":    cmd_cp,
    "mv":    cmd_mv,
    "ls":    cmd_ls,
    "tree":  cmd_tree,
    "stat":  cmd_stat,
    "exists":cmd_exists,
}


def main() -> int:
    if len(sys.argv) < 2:
        cmds = " | ".join(COMMANDS)
        print(f"FAILED: no command. Use: {cmds}")
        return 1
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"FAILED: unknown command '{cmd}'. Available: {' | '.join(COMMANDS)}")
        return 1
    base = load_base_dir()
    return COMMANDS[cmd](sys.argv[2:], base)


if __name__ == "__main__":
    raise SystemExit(main())
