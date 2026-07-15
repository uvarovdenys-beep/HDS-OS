"""Isolation auto-provision: status report + offer-on-degradation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_status_shape():
    from sandbox.provision import status
    s = status()
    assert set(s) == {"docker_cli", "docker_daemon", "colima", "limactl", "isolated"}
    assert all(isinstance(v, bool) for v in s.values())


def test_isolated_implies_daemon():
    from sandbox.provision import status
    s = status()
    # isolated=True must mean a reachable daemon, never just a CLI on disk
    if s["isolated"]:
        assert s["docker_daemon"]


def test_offer_emits_event_once_per_call():
    from events import subscribe, bus
    from sandbox.provision import offer
    hits = []
    handler = lambda ev: hits.append(ev)
    subscribe("isolation_missing", handler)
    try:
        offer()
        assert len(hits) == 1
        # remedy differs: --install (nothing present) vs --ensure (VM stopped)
        assert "sandbox.provision --" in hits[0].data.get("install", "")
    finally:
        bus.unsubscribe("isolation_missing", handler)


def test_runner_degradation_offers():
    """SandboxRunner without docker must fire isolation_missing (visible degrade)."""
    from events import subscribe, bus
    from sandbox.runner import SandboxRunner
    from sandbox.provision import status
    if status()["isolated"]:
        return  # real isolation present — degradation path not reachable
    hits = []
    handler = lambda ev: hits.append(ev)
    subscribe("isolation_missing", handler)
    try:
        r = SandboxRunner()
        assert r.isolated is False
        assert len(hits) == 1
    finally:
        bus.unsubscribe("isolation_missing", handler)


def test_pinned_urls_match_arch():
    import platform
    from sandbox import provision
    arch = platform.machine()
    assert ("arm64" if arch == "arm64" else "x86_64") in provision.LIMA_URL
    assert provision.COLIMA_URL.startswith("https://github.com/abiosoft/colima/")
    assert provision.DOCKER_URL.startswith("https://download.docker.com/")
