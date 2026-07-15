"""
HDS core — the portable AI-containment cage.

Copy this folder into any project to put an arbitrary LLM in a verified cage:
the model PROPOSES a task-script, deterministic code DISPOSES (validates +
writes). The model never touches the filesystem directly.

Four enforcement levels (all language-agnostic except #2):
  1. intent    — scribe path / size / capability gates
  2. content   — per-language AST scan (Python built-in; others default-deny)
  3. integrity — write_path_audit freezes the write surface (no new path past scribe)
  4. harness   — wire write_path_audit into your CI / pre-commit hook

Quick start:
    from core import scribe
    scribe.execute({"op": "write", "path": "storage/x.py", "content": "x=1"},
                   protocol_size="s")   # s/m/l/xl — capability gate

Place this folder at <project>/core/ (it derives the project root as its parent).
Configure scribe.SANDBOX_ROOTS / scribe.CODE_DIRS for your layout.
"""

from . import scribe
from . import ast_validator

__all__ = ["scribe", "ast_validator"]
__version__ = "1.1.0"
