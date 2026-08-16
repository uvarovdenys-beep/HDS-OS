"""Ruby validator: hygiene denylist + real parse via `ruby -c`.

`ruby -c` checks syntax only; it does not run the file.
"""
import re

from .. import register
from .._hygiene import deny_scan
from .._toolchain import check

_PAT = [
    ("system()", re.compile(r"\bsystem\s*\(")),
    ("exec()", re.compile(r"\bexec\s*\(")),
    ("backticks", re.compile(r"`[^`\n]+`")),
    ("%x shell", re.compile(r"%x[\{\(\[]")),
    ("eval", re.compile(r"\b(eval|instance_eval|class_eval)\s*[\(\s]")),
    ("Open3/IO.popen", re.compile(r"\bOpen3\b|IO\.popen")),
    ("File.delete/FileUtils.rm_rf", re.compile(r"File\.delete|FileUtils\.rm_rf")),
]


@register(".rb", kind="exec")
def validate_rb(content, path):
    deny_scan(content, path, _PAT)
    check(["ruby", "-c"], content, path, suffix=".rb", label="ruby -c")
