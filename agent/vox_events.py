#!/usr/bin/env python3
"""
vox_events.py
Wire the voice agent to the event bus as a SINK.

Voice is no longer called directly from business logic. Code emits events
(core.events.emit); this module subscribes a VoxService to the bus, so voice is
fully optional and decoupled. Disable by simply not calling attach_voice().

Usage (once, at startup):
    from agent.vox_events import attach_voice
    attach_voice()                 # voice on, subscribes to the default bus

    # anywhere else, instead of vox.speak(...):
    from core.events import emit
    emit("task_done", message="Task 42 completed", level="INFO")
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # core/agent (vox)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # core/ (events)

from events import subscribe, Event
from vox import VoxService


def make_vox_sink(vox: VoxService):
    """Return an event handler that voices relevant events through VoxService.

    The existing is_technical_message filter inside VoxService.speak still
    applies, so technical noise stays log-only.
    """
    def sink(ev: Event):
        if ev.type == "protocol_violation":
            vox.protocol(ev.data.get("rule_code", "R-?"), ev.message or ev.data.get("description", ""))
        elif ev.type == "task_done":
            vox.task_executed(ev.data.get("task_id", "?"), ev.message or "done")
        elif ev.type == "system_ready":
            vox.system_ready()
        else:
            vox.speak(ev.message or ev.type, ev.level)
    return sink


def attach_voice(enable_speech: bool = True) -> VoxService:
    """Create a VoxService and subscribe it to all events on the default bus."""
    vox = VoxService(enable_speech=enable_speech)
    subscribe("*", make_vox_sink(vox))
    return vox
