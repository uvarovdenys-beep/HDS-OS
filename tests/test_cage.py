"""Self-contained tests for the HDS core cage. No live model, no HDS deps."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # OS root (core/)
import scribe


def test_path_escape_blocked():
    try:
        scribe.execute({"op": "write", "path": "../../evil", "content": "x"}, "xl")
        assert False, "escape not blocked"
    except scribe.ScribeError:
        pass


def test_capability_gate():
    # S may not write code, may not delete; may write sandbox text.
    for ops in ({"op": "write", "path": "agent/x.py", "content": "x=1"},
                {"op": "delete", "path": "storage/a.txt"}):
        try:
            scribe.execute(ops, "s")
            assert False, f"S allowed {ops}"
        except scribe.ScribeError:
            pass


def test_content_gate_blocks_eval():
    try:
        scribe.execute({"op": "write", "path": "storage/a.py", "content": "eval(x)"}, "l")
        assert False, "eval not blocked"
    except scribe.ScribeError:
        pass


def test_unvalidated_language_default_denied():
    try:
        # .go is code (in CODE_EXTS) but has no lang/go validator → must deny.
        scribe.execute({"op": "write", "path": "storage/a.go", "content": "x"}, "l")
        assert False, ".go not default-denied"
    except scribe.ScribeError:
        pass


def test_configure_changes_sandbox(tmp_path):
    scribe.configure(root=tmp_path, sandbox_roots=("box",), code_dirs=("src",))
    (tmp_path / "box").mkdir()
    res = scribe.execute({"op": "write", "path": "box/ok.txt", "content": "hi"}, "s")
    assert "write" in res[0]
    assert (tmp_path / "box" / "ok.txt").read_text() == "hi"
    # restore defaults for other tests
    scribe.configure(root=Path(__file__).resolve().parents[1],
                     sandbox_roots=("storage", "ai-mind/tasks"),
                     code_dirs=("agent", "scripts"))


def test_containment_benchmark_perfect():
    import benchmark
    containment, false_pos = benchmark.run()
    assert containment == 100.0
    assert false_pos == 0.0
