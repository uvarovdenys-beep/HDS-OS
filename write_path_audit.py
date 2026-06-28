#!/usr/bin/env python3
"""
write_path_audit.py
HDS Level-3 guard — enforce the SINGLE WRITE PATH.

The cage (scribe.py: path/size/capability/content gates) only protects writes
that go THROUGH scribe. Any raw `open(...,'w')`, `Path.write_text`, `os.remove`,
`shutil.move`, etc. elsewhere is a hole a capable model could reach.

This auditor AST-scans agent/ and scripts/, finds every filesystem write sink,
and compares against a frozen baseline of sanctioned system-I/O sites. Goal is
NOT to forbid all writes (logs/registry/queues are legitimate) but to FREEZE the
surface: any NEW write site that is not in the baseline fails the audit. So
AI-generated code can never introduce a fresh write path past scribe.

Usage:
    write_path_audit.py            # audit; exit 1 if new sites found
    write_path_audit.py --freeze   # accept current sites as the baseline
"""

import ast
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # core/ is the OS root
BASELINE_FILE = ROOT / "ai-mind" / "config" / "write_path_baseline.json"
SCAN_DIRS = ("agent", "scripts")

# scribe is the sanctioned AI-content writer — its writes are the cage itself.
EXEMPT_FILES = {"scribe.py", "write_path_audit.py"}

# Function-call sinks (by attribute or name) that hit the filesystem.
WRITE_ATTRS = {"write_text", "write_bytes", "remove", "unlink", "rmtree",
               "copy", "copy2", "copyfile", "move", "mkdir", "makedirs"}
WRITE_NAMES = {"open"}  # only counts when opened in a write mode


def _enclosing_func(tree: ast.AST, target: ast.AST) -> str:
    """Best-effort name of the function enclosing a node (for stable keys)."""
    best = "<module>"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if getattr(node, "lineno", 0) <= target.lineno:
                best = node.name
    return best


def _is_write_open(node: ast.Call) -> bool:
    """open(path, mode) where mode contains w/a/x/+ ."""
    if not (isinstance(node.func, ast.Name) and node.func.id == "open"):
        return False
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        return any(c in str(node.args[1].value) for c in "wax+")
    # open(path) defaults to read — not a write
    return False


def find_sinks(path: Path):
    """Yield (key, lineno) for each write sink in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        sink = None
        if _is_write_open(node):
            sink = "open(w)"
        elif isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_ATTRS:
            sink = node.func.attr
        if sink:
            func = _enclosing_func(tree, node)
            yield f"{path.name}::{func}::{sink}", node.lineno


def scan():
    """Return {key: [linenos]} for all sinks across scanned dirs."""
    sites = {}
    for d in SCAN_DIRS:
        for py in sorted((ROOT / d).glob("*.py")):
            if py.name in EXEMPT_FILES:
                continue
            for key, line in find_sinks(py):
                sites.setdefault(key, []).append(line)
    return sites


def main():
    sites = scan()
    keys = set(sites)

    if "--freeze" in sys.argv:
        BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(sorted(keys), indent=2))
        print(f"✅ frozen {len(keys)} sanctioned write sites → {BASELINE_FILE.name}")
        return 0

    if not BASELINE_FILE.exists():
        print("❌ no baseline. Run: write_path_audit.py --freeze")
        return 1

    baseline = set(json.loads(BASELINE_FILE.read_text()))
    new_sites = keys - baseline
    removed = baseline - keys

    if new_sites:
        print(f"❌ {len(new_sites)} NEW write path(s) past scribe (Level-3 violation):")
        for k in sorted(new_sites):
            print(f"   + {k}  (line {sites[k][0]})")
        print("\nRoute AI-content writes through scribe, or --freeze if sanctioned system-I/O.")
        return 1

    print(f"✅ Level-3 OK — {len(keys)} write sites, all sanctioned"
          + (f" ({len(removed)} removed since baseline)" if removed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
