"""lang/ — per-language content validators for the HDS cage.

One home per language (`lang/<x>/validator.py`). A language gains a *content
validator* ONLY by a module here that calls `register(...)`. No data file can
enable a language — capability is granted by code (fail-closed). Config may only
*disable* an already-registered language via `apply_disabled()`.

This registry does NOT decide what counts as code — `scribe.CODE_EXTS` is the
"danger universe". An extension that is code but has no registered validator is
default-DENIED by scribe. The registry only supplies the validators.

A validator is `fn(content: str, path) -> None` that raises `LangReject(msg)`
when the content must not be written. scribe adapts that into a ScribeError.
"""

import importlib
import pkgutil


class LangReject(Exception):
    """Raised by a language validator to reject content (scribe → ScribeError)."""


# ext -> {"kind": str, "fn": callable}
_REGISTRY: dict[str, dict] = {}

# ext -> decomposer callable. Per-language, because decomposition differs
# fundamentally by stack: Python = AST extraction by file size; web (JS/PHP) =
# feature/contract split across files. A language with no decomposer here is
# simply NOT auto-decomposed (honest), never force-fit through Python's AST.
_DECOMPOSERS: dict[str, object] = {}

VALID_KINDS = ("exec", "markup", "data", "compiled")


def register(*exts: str, kind: str):
    """Decorator: register a validator for one or more extensions.

    Example:  @register(".cpp", ".hpp", kind="compiled")
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown kind '{kind}' (expected {VALID_KINDS})")

    def deco(fn):
        for ext in exts:
            _REGISTRY[ext] = {"kind": kind, "fn": fn}
        return fn

    return deco


def get_validator(ext: str):
    """Return the validator callable for an extension, or None if unregistered."""
    entry = _REGISTRY.get(ext)
    return entry["fn"] if entry else None


def register_decomposer(*exts: str):
    """Decorator: register a per-language decomposer for one or more extensions.

    Signature of the decomposed fn is left to each stack — Python splits one file
    by AST; a future web decomposer would split a feature across files around an
    API contract. The registry only dispatches; it does not assume a strategy.
    """
    def deco(fn):
        for ext in exts:
            _DECOMPOSERS[ext] = fn
        return fn

    return deco


def get_decomposer(ext: str):
    """Return the decomposer for an extension, or None (⇒ no auto-decomposition)."""
    return _DECOMPOSERS.get(ext)


def kind_of(ext: str):
    """Return the registered kind for an extension, or None."""
    entry = _REGISTRY.get(ext)
    return entry["kind"] if entry else None


def registered_exts() -> tuple[str, ...]:
    """All extensions that currently have a validator."""
    return tuple(sorted(_REGISTRY))


def apply_disabled(exts) -> None:
    """Subtract-only config: drop validators for these extensions.

    Removing a validator makes scribe default-DENY that extension again (it is
    still code per CODE_EXTS). Config can only tighten the cage, never loosen it.
    """
    for ext in exts or ():
        _REGISTRY.pop(ext, None)


def _autoload() -> None:
    """Import every `lang.<pkg>.validator` so it self-registers on startup."""
    for mod in pkgutil.iter_modules(__path__):
        if not mod.ispkg:
            continue
        for sub in ("validator", "decompose"):
            try:
                importlib.import_module(f"{__name__}.{mod.name}.{sub}")
            except ModuleNotFoundError:
                # Missing validator.py (css = data) or decompose.py (web) is fine.
                pass


_autoload()
