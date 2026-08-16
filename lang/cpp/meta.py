"""Machine-readable facts for C++. Real syntax validation; build still gated."""

LANG = {
    "name": "cpp",
    "exts": [".cpp", ".cc", ".hpp"],
    "kind": "compiled",
    "validator": "lang.cpp.validator:validate_cpp",
    "decomposer": None,
    "decompose_unit": ["class", "function"],
    "roles": ["native-product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "syntax-validated",
}
