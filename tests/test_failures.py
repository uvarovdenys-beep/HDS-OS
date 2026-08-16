"""Failure taxonomy: classify a log line by the reason it reports.

classify_failure_line was written by the local model and acceptance-verified;
these pin its contract so a log-format drift is caught.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hds_failures import classify_failure_line, failure_report


def test_each_category():
    assert classify_failure_line("[BELL] Cage rejected (attempt 2): R-AST") == "cage"
    assert classify_failure_line("Generated code rejected (CRITICAL): eval") == "cage"
    assert classify_failure_line("Acceptance failed (attempt 1)") == "acceptance"
    assert classify_failure_line("Monte Carlo failed (attempt 3)") == "monte_carlo"
    assert classify_failure_line("Task X failed after 3 self-correct attempts") == "gave_up"
    assert classify_failure_line("Model hung >deadline on X") == "timeout"
    assert classify_failure_line("Rejected: model refused task X") == "refused"


def test_non_failures_are_empty():
    assert classify_failure_line("Task X completed successfully") == ""
    assert classify_failure_line("Generating Python for task X") == ""
    assert classify_failure_line("") == ""


def test_report_aggregates():
    lines = ["Cage rejected x", "Cage rejected y", "Acceptance failed z", "all good"]
    assert failure_report(lines) == {"cage": 2, "acceptance": 1}


def test_giveup_attribution_credits_last_cause():
    lines = ["Cage rejected", "Acceptance failed", "Task X failed after 3 self-correct attempts",
             "Monte Carlo failed", "Task Y failed after 4 self-correct attempts"]
    from hds_failures import attribute_giveups
    assert attribute_giveups(lines) == {"acceptance": 1, "monte_carlo": 1}


def test_giveup_with_no_prior_cause_is_unknown():
    from hds_failures import attribute_giveups
    assert attribute_giveups(["Task Q failed after 3 self-correct attempts"]) == {"unknown": 1}


def test_escalation_ladder_picks_next_stronger_served_model():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
    from pipeline_helpers import PipelineHelpersMixin as P
    assert P._escalate_to("qwen/qwen2.5-coder-14b", ["qwen3-coder:30b"]) == "qwen3-coder:30b"
    # returns the REAL served id, not the ladder substring
    assert P._escalate_to("qwen/qwen2.5-coder-14b", ["qwen/qwen3.6-35b-a3b"]) == "qwen/qwen3.6-35b-a3b"
    # already at the top, or nothing served -> no escalation
    assert P._escalate_to("olmo-3-32b-think", ["qwen3-coder:30b"]) == ""
    assert P._escalate_to("qwen/qwen2.5-coder-14b", []) == ""
