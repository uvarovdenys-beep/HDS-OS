"""Discover locally-available models by SCANNING endpoints at runtime.

Portable by design: never a hardcoded per-machine model list. Returns whatever
THIS machine actually serves right now; an empty result (no endpoints up) is
normal and safe. Stdlib only — no deps, no process spawn.
"""
import json
import urllib.request

# (provider, url, parser) — add an endpoint here, not a model name anywhere.
ENDPOINTS = [
    ("ollama", "http://localhost:11434/api/tags",
     lambda d: [m["name"] for m in d.get("models", [])]),
    ("lmstudio", "http://localhost:1234/v1/models",
     lambda d: [m["id"] for m in d.get("data", [])]),
]


def _get(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def discover_models():
    """Return {provider: [model names]} for endpoints that respond (else {})."""
    out = {}
    for name, url, parse in ENDPOINTS:
        data = _get(url)
        if data is None:
            continue
        try:
            out[name] = parse(data)
        except Exception:
            out[name] = []
    return out


def available_model_names():
    """Flat list of every model discovered on this machine right now."""
    names = []
    for models in discover_models().values():
        names.extend(models)
    return names


if __name__ == "__main__":
    disc = discover_models()
    if not disc:
        print("no local model endpoints responding "
              "(ollama :11434 / lmstudio :1234)")
    for prov, models in disc.items():
        print(f"{prov}: {', '.join(models) or '(none)'}")
