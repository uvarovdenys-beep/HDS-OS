"""Swift validator: hygiene denylist + real parse via `swiftc -parse`.

`-parse` stops after parsing: no type-checking pass, no object file, nothing
runnable. Absent toolchain degrades to hygiene only.
"""
import re

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

_PAT = [
    ("Process/task", re.compile(r"\bProcess\s*\(\)|\bNSTask\b")),
    ("system()", re.compile(r"\bsystem\s*\(")),
    ("unsafe pointer", re.compile(r"\bUnsafe(Mutable)?(Raw)?Pointer\b")),
    ("dlopen", re.compile(r"\bdlopen\s*\(")),
    ("FileManager removeItem", re.compile(r"removeItem\s*\(")),
]


@register(".swift", kind="compiled")
def validate_swift(content, path):
    deny_scan(content, path, _PAT)
    check(["swiftc", "-parse"], content, path, suffix=".swift",
          label="swiftc -parse")
