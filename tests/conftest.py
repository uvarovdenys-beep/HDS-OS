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
