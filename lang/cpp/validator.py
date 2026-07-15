"""C++ validator: hygiene denylist + real syntax check via clang++.

clang++ -fsyntax-only parses ONLY — it does not compile a binary or run code, so
it is safe even on the non-isolated backend. Building/executing C++ stays gated
(compiled kind; needs the sandboxed builder before any binary is produced).
"""
import re
from pathlib import Path

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

_PAT = [
    ("system()", re.compile(r"\bsystem\s*\(")),
    ("exec*()", re.compile(r"\bexec[lv][pe]?\s*\(")),
    ("popen()", re.compile(r"\bpopen\s*\(")),
    ("inline asm", re.compile(r"\basm\s*\(|__asm__")),
]


@register(".cpp", ".cc", ".hpp", kind="compiled")
def validate_cpp(content, path):
    deny_scan(content, path, _PAT)
    check(["clang++", "-fsyntax-only", "-x", "c++", "-std=c++17"],
          content, path, suffix=".cpp", label="clang++ -fsyntax-only")
