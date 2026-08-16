"""Machine-readable facts for rs."""

LANG = {
    "name": "rs",
    "exts": ['.rs'],
    "kind": "compiled",
    "validator": "lang.rs.validator:validate_rs",
    "decomposer": None,
    "decompose_unit": ["function"],
    "roles": ["product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated" if 'rustc' else "hygiene-only",
}
