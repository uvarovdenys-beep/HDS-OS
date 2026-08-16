"""Machine-readable facts for rb."""

LANG = {
    "name": "rb",
    "exts": ['.rb'],
    "kind": "exec",
    "validator": "lang.rb.validator:validate_rb",
    "decomposer": None,
    "decompose_unit": ["function"],
    "roles": ["product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated" if 'ruby' else "hygiene-only",
}
