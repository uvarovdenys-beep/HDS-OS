"""Rules as code: surgical patching and the R-300 decomposition ratchet.

These lock in two principles that used to live only in prose — and prose is
something an AI can ignore. Everything runs in-process: a test must not open a
second exec surface (the cage rejects subprocess here, correctly).
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_patch_replaces_only_the_named_function():
    """A patch touches its target lines and nothing else."""
    import scribe as sc
    src = ('"""keep."""\nimport math\n\nCONST = 1\n\n\n'
           'def keep(x):\n    return x\n\n\n'
           'def fix(a, b):\n    return a - b\n')
    f = Path(sc.ROOT) / "storage" / "patch_test.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(src)
    try:
        sc.execute({"op": "patch", "path": "storage/patch_test.py", "target": "fix",
                    "content": "def fix(a, b):\n    return a + b\n"},
                   protocol_size="l")
        out = f.read_text()
        assert "return a + b" in out
        assert '"""keep."""' in out and "import math" in out and "CONST = 1" in out
        assert "def keep(x)" in out
    finally:
        f.unlink(missing_ok=True)


def test_patch_span_includes_decorators():
    import patcher
    src = ("class A:\n"
           "    @property\n"
           "    def val(self):\n"
           "        return 1\n"
           "\n"
           "    def other(self):\n"
           "        return 2\n")
    start, end = patcher.locate(src, "A.val")
    assert (start, end) == (2, 4), (start, end)


def test_patch_refuses_unknown_target():
    import patcher
    try:
        patcher.locate("def a():\n    pass\n", "nope")
        assert False, "missing target must raise"
    except patcher.PatchError:
        pass


def test_patch_result_still_passes_the_cage():
    """Surgery is not a hole: a patch introducing forbidden code is refused."""
    import scribe as sc
    f = Path(sc.ROOT) / "storage" / "patch_guard.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("def safe():\n    return 1\n")
    try:
        try:
            sc.execute({"op": "patch", "path": "storage/patch_guard.py",
                        "target": "safe",
                        "content": "def safe():\n    return eval('1+1')\n"},
                       protocol_size="l")
            assert False, "cage must reject eval introduced by a patch"
        except sc.ScribeError:
            pass
        assert "eval" not in f.read_text()
    finally:
        f.unlink(missing_ok=True)


def test_patch_refuses_a_missing_file():
    import scribe as sc
    try:
        sc.execute({"op": "patch", "path": "storage/nope_missing.py",
                    "target": "x", "content": "def x():\n    pass\n"},
                   protocol_size="l")
        assert False, "patching a non-existent file must raise"
    except sc.ScribeError:
        pass


def test_r300_ratchet_is_executable_and_currently_clean():
    """The 300-line rule is a script with an exit code, not a sentence."""
    import decompose_audit
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["decompose_audit.py"]
    try:
        with redirect_stdout(buf):
            code = decompose_audit.main()
    finally:
        sys.argv = argv
    assert code == 0, buf.getvalue()
    assert "R-300 OK" in buf.getvalue()
