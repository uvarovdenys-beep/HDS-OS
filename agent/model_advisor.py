#!/usr/bin/env python3
"""model_advisor.py — recommend a local model for a task, and suggest what to
install if nothing suitable is served.

Advisory only. Discovery stays in model_scan (no hardcoded served list); this
layer ranks what's ALREADY served and, for code tasks with no coder model
present, proposes an install command. HDS never pulls a model itself — the
command is for the USER to run.
"""

_CODE_HINTS = ("code", "coder", "program", "function", "class", "app", "build",
               "python", "typescript", "javascript", " ts", " js", "php",
               "c++", "c#", "java", "go ", "rust", "html", "css", "sql",
               "script", "module", "api", "refactor")

# Curated INSTALL suggestions (only used when nothing suitable is served).
# Kept minimal + widely-available; the user runs these, HDS never does.
_CODER_SUGGEST = {"model": "qwen2.5-coder:14b",
                  "install": "ollama pull qwen2.5-coder:14b",
                  "why": "a code-specialised model markedly improves generation "
                         "and passes the cage's strict validators more often"}


def _is_coder(name: str) -> bool:
    """Code-specialised only. Plain "deepseek" would wrongly match deepseek-r1,
    which is a REASONING model — escalating to it produced syntax errors."""
    n = name.lower()
    return any(k in n for k in ("coder", "-code", "code-", "starcoder",
                                "deepseek-coder", "codellama", "codestral"))


def _is_embedding(name: str) -> bool:
    return "embed" in name.lower()


def suggest_models(task_hint: str = ""):
    """Return {served, recommended, install_suggestion, note} for a task hint."""
    try:
        from model_scan import discover_models
    except Exception:
        try:
            from .model_scan import discover_models
        except Exception:
            discover_models = lambda: {}
    served = discover_models()  # {"ollama": [...], "lmstudio": [...]}
    flat = [m for lst in served.values() for m in lst if not _is_embedding(m)]
    hint = (task_hint or "").lower()
    is_code = any(k in hint for k in _CODE_HINTS)

    coders = [m for m in flat if _is_coder(m)]
    recommended = None
    if is_code and coders:
        recommended = coders[0]
    elif flat:
        recommended = (coders or flat)[0]

    suggestion = None
    if is_code and not coders:
        suggestion = dict(_CODER_SUGGEST)

    return {
        "task_hint": task_hint,
        "is_code_task": is_code,
        "served": served,
        "recommended": recommended,
        "install_suggestion": suggestion,
        "note": "Run any install command yourself — HDS never pulls a model "
                "unprompted.",
    }
