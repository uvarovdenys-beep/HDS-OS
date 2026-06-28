"""Adversarial probes against the cage content gate (ast_validator).

Two kinds of truth, both asserted:
  MUST_BLOCK  — bypasses the denylist catches (regression guard).
  KNOWN_LIMIT — bypasses it CANNOT catch (attribute dispatch, runtime file IO).
                These document WHY the AST scan is hygiene, not containment:
                real isolation is the sandbox's job, not source scanning.
"""
from ast_validator import ASTValidator, SecurityLevel

_DANGER = {SecurityLevel.DANGER, SecurityLevel.CRITICAL}


def _blocked(code):
    level, _ = ASTValidator().validate(code)
    return level in _DANGER


MUST_BLOCK = [
    ("bare eval", 'eval("x")'),
    ("bare exec", 'exec("x")'),
    ("import subprocess", "import subprocess"),
    ("from subprocess", "from subprocess import run"),
    ("aliased subprocess", "import subprocess as sp"),
    ("getattr bypass", 'getattr(x, "eval")'),
    ("__import__", '__import__("subprocess")'),
    ("importlib", "import importlib"),
    ("os.system", 'import os\nos.system("ls")'),
    ("os.popen", 'import os\nos.popen("ls")'),
    ("compile builtin", 'compile("1", "f", "eval")'),
    ("globals reach", "globals()"),
    ("vars reach", "vars()"),
]

KNOWN_LIMIT = [
    # Attribute-form dispatch: the receiver may be __builtins__, but a denylist
    # cannot know that without data-flow. Catching it reintroduces re.compile
    # false-positives. -> needs isolation, not scanning.
    ("attribute eval", 'x.eval("1")'),
    # Arbitrary runtime file IO: open() is dual-use and legitimate everywhere;
    # blocking it false-positives. Containing it is the sandbox's job.
    ("open file", 'open("/etc/passwd").read()'),
]


def test_must_block_all():
    leaks = [label for label, code in MUST_BLOCK if not _blocked(code)]
    assert leaks == [], f"denylist leaked: {leaks}"


def test_safe_not_false_positive():
    safe = ("x = 1 + 2", "def f():\n    return 1", 'import re\nre.compile("a")')
    for code in safe:
        assert not _blocked(code), f"false positive on: {code!r}"


def test_known_limits_are_documented_not_fixed():
    # These intentionally pass the AST scan. If one ever starts being blocked,
    # revisit the hygiene/containment boundary - do not silently rely on it.
    for label, code in KNOWN_LIMIT:
        assert not _blocked(code), f"{label} unexpectedly blocked - revisit docs"


def test_html_inline_script_gated():
    """Regression: .html is now in CODE_EXTS so inline <script> cannot bypass
    the JS gate on m-grade (the original hole)."""
    import sys; sys.path.insert(0, ".")
    import scribe
    try:
        scribe.execute({"op": "write", "path": "storage/x.html",
                        "content": "<script>eval('x')</script>"}, "m")
        assert False, "eval in <script> must be gated at m-grade"
    except scribe.ScribeError:
        pass  # correct: needs l+ and html_guard blocks eval
