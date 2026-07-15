"""Machine-readable facts for C#. Real build validation; execution still gated."""

LANG = {
    "name": "cs",
    "exts": [".cs"],
    "kind": "compiled",
    "validator": "lang.cs.validator:validate_cs",
    "decomposer": None,
    "decompose_unit": ["class", "function"],
    "roles": ["dotnet-product"],
    "enabled": True,
    "build": "sandboxed-builder-required",
    "state": "build-validated",
}
