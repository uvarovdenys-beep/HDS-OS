"""Python decomposition strategy — delegates to the existing AST splitter.

Wraps agent/auto_decompose (do not reimplement). Registered for .py only; this
is the ONE language whose unit-of-decomposition is a single-file AST node. Web
stacks decompose by feature/contract and intentionally have no decomposer.
"""
import sys
from pathlib import Path

from .. import register_decomposer

_CORE = Path(__file__).resolve().parents[2]
for p in (str(_CORE), str(_CORE / "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)


@register_decomposer(".py")
def decompose_python(filepath, max_lines=200, **kw):
    from auto_decompose import decompose_python_file
    return decompose_python_file(filepath, max_lines=max_lines, **kw)
