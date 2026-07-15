"""Python content gate — wraps core's ast_validator into the lang registry.

The trust logic stays in `ast_validator.ASTValidator`; this only adapts it to the
`lang` contract: raise LangReject on DANGER/CRITICAL.
"""

import sys
from pathlib import Path

from .. import register, LangReject

# core root holds ast_validator.py (lang/ is a subpackage of core)
_CORE = Path(__file__).resolve().parents[2]
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))


@register(".py", kind="exec")
def validate_python(content: str, path) -> None:
    from ast_validator import ASTValidator, SecurityLevel

    level, violations = ASTValidator().validate(content)
    rank = {
        SecurityLevel.SAFE: 0,
        SecurityLevel.WARNING: 1,
        SecurityLevel.DANGER: 2,
        SecurityLevel.CRITICAL: 3,
    }
    if rank.get(level, 0) >= rank[SecurityLevel.DANGER]:
        kinds = ", ".join(sorted({v.get("type", "?") for v in violations}))
        raise LangReject(f"'{Path(path).name}' rejected ({level.name}: {kinds})")
