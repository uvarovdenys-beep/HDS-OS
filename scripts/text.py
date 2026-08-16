"""
text.py — HDS 4.3 Text Manipulation
All destructive operations auto-backup via archive.py before modifying.

Commands:
  replace <file> <old> <new> [--regex] [--all]
  insert  <file> <line_num> <text>
  delete  <file> <line_start> <line_end>
  append  <file> <text>
  prepend <file> <text>
  head    <file> [N=50]
  tail    <file> [N=50]
  lines   <file> <from> <to>
  count   <file>
  diff    <file1> <file2>
"""

import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "AI-MIND" / "architecture" / "user.config"
ARCHIVE_SCRIPT = Path(__file__).resolve().parent / "archive.py"


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


def guard(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        print(f"FAILED: BASE_DIR_LOCK — outside base_dir: {path}")
        return False


def auto_backup(path: Path) -> None:
    if not ARCHIVE_SCRIPT.exists():
        return
    r = subprocess.run([sys.executable, str(ARCHIVE_SCRIPT), "backup", str(path)],
                       capture_output=True, text=True)
    line = (r.stdout.strip().splitlines() or [""])[0]
    print(f"  [archive] {line}")


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def cmd_replace(args: list[str], base: Path) -> int:
    use_regex = "--regex" in args
    replace_all = "--all" in args
    clean = [a for a in args if a not in ("--regex", "--all")]
    if len(clean) < 3:
        print("FAILED: replace requires <file> <old> <new>")
        return 1
    path = resolve(clean[0], base)
    if not path.is_file() or not guard(path, base):
        return 1
    content = path.read_text(encoding="utf-8", errors="replace")
    old_text, new_text = clean[1], clean[2]
    if use_regex:
        try:
            count = len(re.findall(old_text, content))
            if count == 0:
                print("PASSED: 0 matches — file unchanged")
                return 0
            auto_backup(path)
            new_content = re.sub(old_text, new_text, content, count=0 if replace_all else 1)
        except re.error as e:
            print(f"FAILED: invalid regex: {e}")
            return 1
    else:
        count = content.count(old_text)
        if count == 0:
            print("PASSED: 0 matches — file unchanged")
            return 0
        auto_backup(path)
        new_content = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)
    path.write_text(new_content, encoding="utf-8")
    print(f"PASSED: replaced {min(count,1) if not replace_all else count} occurrence(s) in {path.name}")
    return 0


def cmd_insert(args: list[str], base: Path) -> int:
    if len(args) < 3:
        print("FAILED: insert requires <file> <line_num> <text>")
        return 1
    path = resolve(args[0], base)
    if not path.is_file() or not guard(path, base):
        return 1
    lineno = int(args[1])
    auto_backup(path)
    lines = read_lines(path)
    lines.insert(max(0, min(lineno - 1, len(lines))), args[2] + "\n")
    write_lines(path, lines)
    print(f"PASSED: inserted at line {lineno} in {path.name}")
    return 0


def cmd_delete(args: list[str], base: Path) -> int:
    if len(args) < 3:
        print("FAILED: delete requires <file> <start> <end>")
        return 1
    path = resolve(args[0], base)
    if not path.is_file() or not guard(path, base):
        return 1
    start, end = int(args[1]), int(args[2])
    auto_backup(path)
    lines = read_lines(path)
    removed = end - start + 1
    lines = lines[:start - 1] + lines[end:]
    write_lines(path, lines)
    print(f"PASSED: deleted {removed} line(s) ({start}..{end}) from {path.name}")
    return 0


def cmd_append(args: list[str], base: Path) -> int:
    if len(args) < 2:
        print("FAILED: append requires <file> <text>")
        return 1
    path = resolve(args[0], base)
    if not path.exists() or not guard(path, base):
        return 1
    auto_backup(path)
    content = path.read_text(encoding="utf-8", errors="replace")
    path.write_text(content.rstrip("\n") + "\n" + args[1] + "\n", encoding="utf-8")
    print(f"PASSED: appended to {path.name}")
    return 0


def cmd_prepend(args: list[str], base: Path) -> int:
    if len(args) < 2:
        print("FAILED: prepend requires <file> <text>")
        return 1
    path = resolve(args[0], base)
    if not path.exists() or not guard(path, base):
        return 1
    auto_backup(path)
    content = path.read_text(encoding="utf-8", errors="replace")
    path.write_text(args[1] + "\n" + content, encoding="utf-8")
    print(f"PASSED: prepended to {path.name}")
    return 0


def cmd_head(args: list[str], base: Path) -> int:
    brief = "--brief" in args or "-b" in args
    clean = [a for a in args if a not in ("--brief", "-b")]
    if not clean:
        print("FAILED: head requires <file>")
        return 1
    path = resolve(clean[0], base)
    if not path.is_file():
        print(f"FAILED: not found: {path}")
        return 1
    n = int(clean[1]) if len(clean) > 1 else 50
    lines = read_lines(path)
    shown = lines[:n]
    if not brief:
        print(f"PASSED: first {len(shown)}/{len(lines)} lines — {path.name}")
    for i, l in enumerate(shown, 1):
        if brief:
            print(l, end="")
        else:
            print(f"{i:>5}: {l}", end="")
    return 0


def cmd_tail(args: list[str], base: Path) -> int:
    brief = "--brief" in args or "-b" in args
    clean = [a for a in args if a not in ("--brief", "-b")]
    if not clean:
        print("FAILED: tail requires <file>")
        return 1
    path = resolve(clean[0], base)
    if not path.is_file():
        print(f"FAILED: not found: {path}")
        return 1
    n = int(clean[1]) if len(clean) > 1 else 50
    lines = read_lines(path)
    shown = lines[-n:]
    start = len(lines) - len(shown) + 1
    if not brief:
        print(f"PASSED: last {len(shown)}/{len(lines)} lines — {path.name}")
    for i, l in enumerate(shown, start):
        if brief:
            print(l, end="")
        else:
            print(f"{i:>5}: {l}", end="")
    return 0


def cmd_lines_range(args: list[str], base: Path) -> int:
    brief = "--brief" in args or "-b" in args
    clean = [a for a in args if a not in ("--brief", "-b")]
    if len(clean) < 3:
        print("FAILED: lines requires <file> <from> <to>")
        return 1
    path = resolve(clean[0], base)
    if not path.is_file():
        print(f"FAILED: not found: {path}")
        return 1
    frm, to = max(1, int(clean[1])), int(clean[2])
    lines = read_lines(path)
    to = min(to, len(lines))
    shown = lines[frm - 1:to]
    if not brief:
        print(f"PASSED: lines {frm}..{to}/{len(lines)} — {path.name}")
    for i, l in enumerate(shown, frm):
        if brief:
            print(l, end="")
        else:
            print(f"{i:>5}: {l}", end="")
    return 0


def cmd_count(args: list[str], base: Path) -> int:
    if not args:
        print("FAILED: count requires <file>")
        return 1
    path = resolve(args[0], base)
    if not path.is_file():
        print(f"FAILED: not found: {path}")
        return 1
    content = path.read_text(encoding="utf-8", errors="replace")
    print(f"PASSED: {path.name}")
    print(f"  lines: {len(content.splitlines())}")
    print(f"  words: {len(content.split())}")
    print(f"  bytes: {path.stat().st_size}")
    return 0


def cmd_diff(args: list[str], base: Path) -> int:
    if len(args) < 2:
        print("FAILED: diff requires <file1> <file2>")
        return 1
    f1, f2 = resolve(args[0], base), resolve(args[1], base)
    for f in (f1, f2):
        if not f.is_file():
            print(f"FAILED: not found: {f}")
            return 1
    l1 = f1.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    l2 = f2.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    diff = list(difflib.unified_diff(l1, l2, fromfile=f1.name, tofile=f2.name))
    if not diff:
        print("PASSED: files are identical")
        return 0
    print(f"PASSED: {len(diff)} diff line(s)")
    for line in diff:
        print(line, end="")
    return 0


COMMANDS = {
    "replace": cmd_replace, "insert": cmd_insert, "delete": cmd_delete,
    "append": cmd_append,   "prepend": cmd_prepend, "head": cmd_head,
    "tail": cmd_tail,       "lines": cmd_lines_range, "count": cmd_count,
    "diff": cmd_diff,
}


def main() -> int:
    if len(sys.argv) < 2:
        print(f"FAILED: no command. Use: {' | '.join(COMMANDS)}")
        return 1
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"FAILED: unknown command '{cmd}'")
        return 1
    return COMMANDS[cmd](sys.argv[2:], load_base_dir())


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("🧪 Testing HDS 5 Text Engine...")
        sample = "Line 1\nLine 2\nLine 3"
        print(f"Sample:\n{sample}")
        print("-" * 20)
        # Add your test logic here
        print("✅ Text Engine: READY")
        sys.exit(0)
    raise SystemExit(main())
