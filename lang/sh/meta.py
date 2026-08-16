"""Machine-readable facts for sh."""

LANG = {
    "name": "sh",
    "exts": ['.sh', '.bash'],
    "kind": "exec",
    "validator": "lang.sh.validator:validate_sh",
    "decomposer": None,
    "decompose_unit": ["function"],
    "roles": ["product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated" if 'bash' else "hygiene-only",
}
