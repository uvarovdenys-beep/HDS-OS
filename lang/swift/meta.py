"""Machine-readable facts for Swift."""

LANG = {
    "name": "swift",
    "exts": [".swift"],
    "kind": "compiled",
    "validator": "lang.swift.validator:validate_swift",
    "decomposer": None,
    "decompose_unit": ["function", "class"],
    "roles": ["native-product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated",
}
