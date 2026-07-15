"""model_scan: discovery is dynamic, portable, and graceful when nothing is up."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import model_scan


def test_discover_returns_dict():
    assert isinstance(model_scan.discover_models(), dict)


def test_available_names_is_list():
    assert isinstance(model_scan.available_model_names(), list)


def test_dead_endpoint_is_graceful():
    # no exception, just None — so a machine with no models is fine
    assert model_scan._get("http://localhost:59999/none", timeout=1) is None


def test_no_hardcoded_models_in_scan_source():
    # specific model tags only (avoid 'llama' which is a substring of 'ollama')
    src = Path(model_scan.__file__).read_text().lower()
    for pinned in ("qwen", "gemma", "gpt-oss", "deepseek", ":30b", ":9b"):
        assert pinned not in src, f"scan must not hardcode '{pinned}'"
