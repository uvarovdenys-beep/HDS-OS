"""Go validator: hygiene denylist + real parse via `gofmt -e`.

`gofmt -e` parses and reports syntax errors without building or running.
When the Go toolchain is absent this degrades to hygiene only and the install
command is offered — the same honest degradation the other languages use.
"""
import re

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

_PAT = [
    ("os/exec", re.compile(r'"os/exec"|\bexec\.Command\b')),
    ("syscall", re.compile(r'"syscall"|\bsyscall\.')),
    ("unsafe", re.compile(r'"unsafe"|\bunsafe\.Pointer\b')),
    ("os.RemoveAll", re.compile(r"\bos\.RemoveAll\b")),
    ("plugin loading", re.compile(r'"plugin"|\bplugin\.Open\b')),
]


@register(".go", kind="compiled")
def validate_go(content, path):
    deny_scan(content, path, _PAT)
    check(["gofmt", "-e"], content, path, suffix=".go", label="gofmt -e")
