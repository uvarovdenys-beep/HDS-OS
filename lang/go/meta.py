"""Machine-readable facts for go."""

LANG = {
    "name": "go",
    "exts": ['.go'],
    "kind": "compiled",
    "validator": "lang.go.validator:validate_go",
    "decomposer": None,
    "decompose_unit": ["function"],
    "roles": ["product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated" if 'gofmt' else "hygiene-only",
}
