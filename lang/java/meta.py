"""Machine-readable facts for java."""

LANG = {
    "name": "java",
    "exts": ['.java'],
    "kind": "compiled",
    "validator": "lang.java.validator:validate_java",
    "decomposer": None,
    "decompose_unit": ["function"],
    "roles": ["product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated" if 'javac' else "hygiene-only",
}
