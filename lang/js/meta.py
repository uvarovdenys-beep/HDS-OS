LANG = {
    "name": "js",
    "exts": [".js", ".ts", ".jsx", ".tsx"],
    "kind": "exec",
    "validator": "lang.js.validator:validate_js",
    "decomposer": None,
    "decompose_unit": ["function"],
    "roles": ["web-front"],
    "enabled": True,
    "build": None,
    "state": "hygiene",
}
