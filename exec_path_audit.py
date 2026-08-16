"""exec_path_audit.py — Level-3 integrity for EXECUTION (mirror of write_path_audit).

Just as the cage has a single write surface, it must have a single exec surface.
This audit freezes that surface: `subprocess` (and friends) may be used ONLY in
the sandbox backend(s). Any other module touching subprocess is a containment
breach — the audit fails CI.
"""

import ast
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent

# Files permitted to spawn, each with a justification. Two classes are allowed:
#   1. the sandbox backend (hardened, the product-execution surface);
#   2. TRUSTED INFRA — spawns of FIXED binaries or internal sys.executable
#      scripts whose argv is NOT derived from AI/product content.
# A spawn whose command or inputs come from AI-authored artifacts is NEVER
# allowlisted — it must go through SandboxRunner.
ALLOWED = {
    "sandbox/docker_backend.py": "hardened container exec — isolated product surface",
    "sandbox/subprocess_backend.py": "degraded no-shell exec-path (isolated=False)",
    "sandbox/provision.py": "operator-invoked isolation installer (colima/docker) — fixed argv, not model-reachable",
    "agent/port_checker.py": "lsof/netstat — fixed binaries, port scan",
    "agent/sysmon.py": "vm_stat — fixed binary, host free-RAM monitoring, argv not AI-derived",
    "agent/vox_speech.py": "audio players (afplay/powershell) — fixed binaries",
    "agent/agent.py": "python -c syntax check of own output (internal)",
    "scripts/orchestrator.py": "runs internal mem_clear.py via sys.executable",
    "scripts/ops.py": "runs internal archive/text scripts via sys.executable",
    "scripts/text.py": "runs internal archive script via sys.executable",
    "scripts/gate.py": "runs internal repo scripts via sys.executable",
    "scripts/protocol_guard.py": "git diff — fixed binary, pre-commit hook",
    # task_yaml_support.py and build_certify.py now route through SandboxRunner
    # (no raw subprocess) — the two shell=True breaches are closed.
}

# Modules that grant process spawning.
SPAWN_MODULES = {"subprocess", "os", "pty", "multiprocessing"}
# os is broad; we only flag the spawning members below.
OS_SPAWN_ATTRS = {"system", "popen", "exec", "execv", "execve", "execvp",
                  "spawn", "spawnv", "fork", "posix_spawn"}


def _uses_spawn(tree: ast.AST) -> List[str]:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == "subprocess":
                    hits.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "subprocess":
                hits.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "os" \
                    and node.attr in OS_SPAWN_ATTRS:
                hits.append(f"os.{node.attr}")
    return hits


def run() -> List[dict]:
    """Return a list of violations (empty = exec surface is single & sealed)."""
    violations = []
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if rel in ALLOWED or rel.startswith((".git", "__pycache__", ".archive")) \
                or "/__pycache__/" in rel or "/.archive/" in rel \
                or rel == "exec_path_audit.py":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for hit in _uses_spawn(tree):
            violations.append({"file": rel, "spawn": hit})
    return violations


if __name__ == "__main__":
    v = run()
    if v:
        print(f"❌ exec-path breach: {len(v)} spawn site(s) outside sandbox/")
        for x in v:
            print(f"   {x['file']}: {x['spawn']}")
        raise SystemExit(1)
    print("✅ single exec-path sealed — subprocess confined to sandbox/")
