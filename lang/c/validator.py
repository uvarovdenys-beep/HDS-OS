"""C validator: hygiene denylist + real syntax check via clang.

Same shape as the C++ module, deliberately: `.c` sat in scribe.CODE_EXTS with no
validator, so every C file was refused outright by the fail-closed default. That
is safe but it is not support — the language was advertised and unusable.

clang -fsyntax-only parses ONLY; it does not compile a binary or run anything, so
it is safe even on the non-isolated backend. Building/executing C stays gated
(compiled kind; the sandboxed builder is required before any binary exists).
"""
import re

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

# The C surface is narrower than C++ but the dangerous calls are the same, plus
# the exec family's C-only spellings.
_PAT = [
    ("system()", re.compile(r"\bsystem\s*\(")),
    ("exec*()", re.compile(r"\bexec[lv][pe]?\s*\(")),
    ("popen()", re.compile(r"\bpopen\s*\(")),
    ("fork()", re.compile(r"\bfork\s*\(")),
    ("inline asm", re.compile(r"\basm\s*\(|__asm__")),
]


@register(".c", ".h", kind="compiled")
def validate_c(content, path):
    deny_scan(content, path, _PAT)
    check(["clang", "-fsyntax-only", "-x", "c", "-std=c11"],
          content, path, suffix=".c", label="clang -fsyntax-only")
