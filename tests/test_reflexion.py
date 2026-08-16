"""Reflexion — the episodic half of HDS memory.

Locks the lesson-distillation logic and the record round-trip into
AIExperienceModule, so a corrected failure reliably becomes a durable lesson.
In-process, no model, temp store.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent"))

import reflexion
from ai_experience import AIExperienceModule


def test_no_lesson_without_correction():
    assert reflexion.lesson_from_error("t", "boom", 1) is None


def test_no_lesson_for_blank_error():
    assert reflexion.lesson_from_error("t", "   ", 3) is None


def test_rule_is_first_nonempty_line():
    lesson = reflexion.lesson_from_error("t", "\n\n  R-AST: os  \nrest", 2)
    assert lesson["anti_pattern_rule"] == "R-AST: os"


def test_error_trace_capped_at_200():
    lesson = reflexion.lesson_from_error("t", "x" * 300, 2)
    assert len(lesson["error_trace"]) == 200


def test_fields_match_register_failure_signature():
    lesson = reflexion.lesson_from_error("task9", "R-PATCH: nope", 4)
    assert set(lesson) == {"task_id", "error_trace", "ai_self_analysis",
                           "anti_pattern_rule"}
    assert lesson["task_id"] == "task9"
    assert lesson["ai_self_analysis"] == "Corrected after 4 attempts"


def test_record_round_trip_into_experience_store():
    # The exact path the _execute_ai_task hook takes: distill, then register.
    # Embedding is stubbed: this asserts the RECORD path, and reaching the
    # model here only made the suite slow and service-dependent.
    import ai_experience
    real = ai_experience._embed_text
    ai_experience._embed_text = lambda _t: None   # restored below — a leaked
    try:                                          # stub broke semantic recall
        db = Path(tempfile.mkdtemp()) / "ap.json" # in a LATER test
        exp = AIExperienceModule(db_path=db)
        assert exp.get_stats()["total_failures"] == 0
        lesson = reflexion.lesson_from_error("t", "R-AST: forbidden_import os", 2)
        assert exp.register_failure(**lesson, symbol="x.py::f") is True
        assert exp.get_stats()["total_failures"] == 1
    finally:
        ai_experience._embed_text = real


def _embeddings_available():
    import embed
    return embed.embed("probe") is not None


def test_semantic_recall_surfaces_relevant_and_not_irrelevant():
    # With embeddings: a relevant query surfaces the lesson; an unrelated one
    # returns NOTHING — no "last N regardless" leak. Skips without the model.
    if not _embeddings_available():
        return
    db = Path(tempfile.mkdtemp()) / "ap.json"
    exp = AIExperienceModule(db_path=db)
    exp.register_failure("t1", "TypeError ast.walk", "passed a callback to ast.walk",
                         "ast.walk returns an iterator; iterate it, no visitor callback")
    exp.register_failure("t2", "R-AST os", "used os.system", "never call os.system")
    hit = exp.get_context_for_prompt(["walk an AST node and collect the call names"])
    assert "ast.walk" in hit and "os.system" not in hit
    miss = exp.get_context_for_prompt(["render a bar chart of quarterly sales"])
    assert miss.strip() == ""


def test_keyword_fallback_has_no_last_n_leak():
    # No keywords -> nothing (the old code returned the last 5 regardless).
    db = Path(tempfile.mkdtemp()) / "ap.json"
    exp = AIExperienceModule(db_path=db)
    exp.register_failure("t", "e", "a", "some rule")
    assert exp._recall_keyword(exp_patterns(exp), None) == []


def exp_patterns(exp):
    import json
    return json.load(open(exp.db_path))["anti_patterns"]


def test_consolidate_drops_near_duplicates():
    from ai_experience import consolidate
    dupes = [{"embedding": [1.0, 0.0]}, {"embedding": [10.0, 1.0]}, {"embedding": [0.0, 1.0]}]
    kept = consolidate(dupes)
    assert len(kept) == 2  # the near-duplicate of the first is dropped, orthogonal kept


def test_consolidate_store_reduces_and_counts():
    import tempfile
    from pathlib import Path
    from ai_experience import AIExperienceModule
    exp = AIExperienceModule(db_path=Path(tempfile.mkdtemp()) / "ap.json")
    # inject two identical-embedding lessons directly
    import json
    data = {"anti_patterns": [
        {"derived_rule": "a", "ai_self_analysis": "x", "severity": "HIGH", "embedding": [1.0, 0.0]},
        {"derived_rule": "b", "ai_self_analysis": "y", "severity": "HIGH", "embedding": [1.0, 0.0]},
    ], "lessons_learned": 2}
    exp.db_path.write_text(json.dumps(data))
    assert exp.consolidate_store() == 1
    assert exp.get_stats()["total_failures"] == 1
