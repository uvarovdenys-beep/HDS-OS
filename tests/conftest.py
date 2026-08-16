"""Shared pytest config — keep the suite runnable on any machine.

Tests that need a live local model must be marked `@pytest.mark.live_model`.
They are auto-skipped when neither Ollama (:11434) nor LM Studio (:1234) is
reachable, so the suite passes on CI / a reviewer's laptop with no models.
"""
import socket
import pytest


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def local_ai_available() -> bool:
    """True if a local model endpoint (Ollama or LM Studio) is reachable."""
    return _port_open("localhost", 11434) or _port_open("localhost", 1234)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live_model: test requires a live local model (Ollama/LM Studio)")


def pytest_collection_modifyitems(config, items):
    if local_ai_available():
        return
    skip = pytest.mark.skip(reason="no local model endpoint (Ollama/LM Studio) reachable")
    for item in items:
        if "live_model" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def local_ai():
    """Fixture that skips the test if no local model endpoint is up."""
    if not local_ai_available():
        pytest.skip("no local model endpoint reachable")
    return True


@pytest.fixture(autouse=True)
def _restore_cage_root():
    """Put scribe's ROOT back after every test.

    test_fuzzer repoints the cage at a temp directory and never restored it, so
    every LATER test that wrote through scribe saw an alien root and failed with
    R-PATH: "escapes project root". The leak was invisible until the rollback
    tests started writing real files. Guarding it here covers every test file,
    not just the one that happened to leak.
    """
    import scribe
    saved = scribe.ROOT
    yield
    if scribe.ROOT != saved:
        scribe.configure(root=saved)
