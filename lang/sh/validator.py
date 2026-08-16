"""Shell validator: hygiene denylist + real parse via `bash -n`.

`.sh` sat in scribe.CODE_EXTS with no validator, so every shell script was
refused outright — safe, and unusable. Shell is the highest-leverage language for
an attacker, so the denylist is the strictest of the set.

`bash -n` parses without executing a single command.
"""
import re

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

_PAT = [
    ("rm -rf", re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-?[rR]f?\b")),
    ("curl|wget piped to a shell", re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(ba)?sh")),
    ("eval", re.compile(r"\beval\b")),
    ("sudo", re.compile(r"\bsudo\b")),
    ("dd to a device", re.compile(r"\bdd\b[^\n]*of=/dev/")),
    ("mkfs", re.compile(r"\bmkfs\b")),
    ("chmod 777", re.compile(r"\bchmod\s+(-[a-zA-Z]+\s+)*777\b")),
    ("history wipe", re.compile(r"\bhistory\s+-c\b")),
]


@register(".sh", ".bash", kind="exec")
def validate_sh(content, path):
    deny_scan(content, path, _PAT)
    check(["bash", "-n"], content, path, suffix=".sh", label="bash -n")
