"""The `os` policy: ban the operation, not the module.

`os` is ordinary in real programs (os.path, os.environ, os.makedirs …), so it is
allowed. The process-spawning surface (os.system/popen/exec*/spawn*/fork) is the
real danger — it bypasses the single sandboxed exec surface — so it stays
CRITICAL for everyone. In-process, no sandbox.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ast_validator import ASTValidator, SecurityLevel


def _level(code):
    return ASTValidator().validate(code)[0]


# ── benign os: must pass ────────────────────────────────────────────────
def test_os_path_is_allowed():
    assert _level("import os\np = os.path.join('a', 'b')\n") == SecurityLevel.SAFE


def test_os_environ_is_allowed():
    assert _level("import os\nx = os.environ.get('HOME')\n") == SecurityLevel.SAFE


def test_os_makedirs_and_listdir_allowed():
    assert _level("import os\nos.makedirs('d', exist_ok=True)\nos.listdir('.')\n") == SecurityLevel.SAFE


def test_from_os_import_path_allowed():
    assert _level("from os import path\np = path.dirname('/a/b')\n") == SecurityLevel.SAFE


# ── the exec surface: must be CRITICAL ──────────────────────────────────
def test_os_system_is_critical():
    assert _level("import os\nos.system('rm -rf /')\n") == SecurityLevel.CRITICAL


def test_os_popen_is_critical():
    assert _level("import os\nos.popen('ls')\n") == SecurityLevel.CRITICAL


def test_os_execv_is_critical():
    assert _level("import os\nos.execv('/bin/sh', [])\n") == SecurityLevel.CRITICAL


def test_os_alias_exec_is_critical():
    # import os as o; o.system(...) — the alias is tracked.
    assert _level("import os as o\no.system('x')\n") == SecurityLevel.CRITICAL


def test_from_os_import_system_is_critical():
    assert _level("from os import system\nsystem('x')\n") == SecurityLevel.CRITICAL


def test_from_os_import_star_is_critical():
    # A star import could pull in the exec names, so it is refused.
    assert _level("from os import *\n") == SecurityLevel.CRITICAL


def test_subprocess_still_banned():
    assert _level("import subprocess\n") == SecurityLevel.CRITICAL


# ── inline <script>: ban the operation, not the keyword ────────────────
# `Function(` (the constructor) is dynamic code; `function(){}` is the most
# common construct in JS. A case-insensitive rule conflated them.

def test_benign_function_expression_allowed_in_markup():
    from lang._markup import _SCRIPT_BODY_DENY as D
    assert not D.search("var f = function(){ return 1; };")
    assert not D.search("setInterval(function(){ tick(); }, 100);")


def test_dynamic_code_still_blocked_in_markup():
    from lang._markup import _SCRIPT_BODY_DENY as D
    assert D.search('eval("x")')
    assert D.search('new Function("return 1")')
    assert D.search('Function("a","return a")')
    assert D.search('import("./x.js")')
