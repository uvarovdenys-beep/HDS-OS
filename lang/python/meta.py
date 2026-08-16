"""Machine-readable language facts for python. Read by py control scripts."""

LANG = {
    "name": "python",
    "exts": [".py"],
    "kind": "exec",
    "validator": "lang.python.validator:validate_python",
    "decomposer": "lang.python.decompose:decompose_python",
    "decompose_unit": ["class", "function"],
    "roles": ["kernel", "ai-hands"],
    "enabled": True,
    "build": None,
    "state": "ready",
}
