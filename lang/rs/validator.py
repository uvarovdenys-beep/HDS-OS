"""Rust validator: hygiene denylist + real parse via `rustc --emit=metadata`.

That mode type-checks and emits metadata; it produces no runnable binary.
Absent toolchain degrades to hygiene only, with the install command offered.
"""
import re

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

_PAT = [
    ("std::process", re.compile(r"std::process::(Command|exit|abort)")),
    ("unsafe block", re.compile(r"\bunsafe\s*\{")),
    ("libc/FFI", re.compile(r"\bextern\s+\"C\"|\blibc::")),
    ("fs::remove_dir_all", re.compile(r"fs::remove_dir_all")),
    ("transmute", re.compile(r"\bmem::transmute\b")),
]


@register(".rs", kind="compiled")
def validate_rs(content, path):
    deny_scan(content, path, _PAT)
    check(["rustc", "--edition", "2021", "--emit=metadata", "-o", "/dev/null"],
          content, path, suffix=".rs", label="rustc --emit=metadata")
