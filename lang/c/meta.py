"""Machine-readable facts for C. Real syntax validation; build still gated."""

LANG = {
    "name": "c",
    "exts": [".c", ".h"],
    "kind": "compiled",
    "validator": "lang.c.validator:validate_c",
    "decomposer": None,
    "decompose_unit": ["function"],
    "roles": ["native-product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated",
}
