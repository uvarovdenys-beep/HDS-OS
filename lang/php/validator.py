"""PHP validator: hygiene denylist + real syntax check via `php -l` when present."""
import re

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

_PAT = [
    ("eval()", re.compile(r"\beval\s*\(")),
    ("exec/system family", re.compile(
        r"\b(exec|system|shell_exec|passthru|proc_open|popen)\s*\(")),
    ("backticks", re.compile(r"`[^`]*`")),
    ("create_function", re.compile(r"create_function\s*\(")),
    ("variable include/require", re.compile(
        r"\b(include|require)(_once)?\s*\(?\s*\$")),
]


@register(".php", kind="exec")
def validate_php(content, path):
    deny_scan(content, path, _PAT)
    # real syntax gate (php -l); auto-falls back to hygiene-only if php absent
    check(["php", "-l"], content, path, suffix=".php", label="php -l")
