"""py CONTROL surface over language policy. Read by AI/dev scripts.

Cross-checks the hard meta.py structures against the code registry. The rule a
py script enforces: a language is *writable* only if its validator exists AND
meta marks it enabled. meta cannot grant capability a validator doesn't back.
"""

import importlib
import pkgutil
from pathlib import Path

import lang


def load_meta():
    """Return {name: LANG dict} from every lang/<x>/meta.py."""
    out = {}
    for mod in pkgutil.iter_modules([str(Path(__file__).resolve().parent)]):
        if not mod.ispkg:
            continue
        try:
            m = importlib.import_module("lang." + mod.name + ".meta")
        except ModuleNotFoundError:
            continue
        out[mod.name] = m.LANG
    return out


def policy():
    """Flatten meta + registry into per-ext control rows."""
    rows = []
    for name, spec in load_meta().items():
        for ext in spec["exts"]:
            has = lang.get_validator(ext) is not None
            enabled = bool(spec.get("enabled", False))
            rows.append({
                "name": name,
                "ext": ext,
                "kind": spec["kind"],
                "enabled": enabled,
                "has_validator": has,
                "writable": has and enabled,
            })
    return rows


def audit():
    """Fail-closed audit: exec/compiled marked enabled but lacking a validator."""
    return [r for r in policy()
            if r["enabled"] and r["kind"] in ("exec", "compiled")
            and not r["has_validator"]]
