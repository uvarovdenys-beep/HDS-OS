#!/usr/bin/env python3
"""
events.py
HDS event bus — decouple WHAT happened from WHO reacts.

Code publishes events ("a rule was hit", "a task finished"); sinks subscribe.
Voice, logging, metrics, dashboards are all just sinks — none is wired into the
business logic. This keeps the cage silent and minimal (no TTS dependency in
core paths) while letting observability layers plug in.

Usage:
    from core.events import emit, subscribe, Event

    # producer (anywhere in the codebase):
    emit("task_done", message="Task 42 completed", level="INFO", task_id="42")

    # consumer (e.g. voice, registered once at startup):
    def on_event(ev: Event): ...
    subscribe("task_done", on_event)      # one type
    subscribe("*", on_event)              # all types
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any

# Canonical event types (free-form strings are allowed; these are the conventions)
PROTOCOL_VIOLATION = "protocol_violation"
TASK_DONE = "task_done"
SYSTEM_READY = "system_ready"
WRITE_REJECTED = "write_rejected"
VERIFICATION_FAILED = "verification_failed"


@dataclass
class Event:
    """A single observable occurrence."""
    type: str
    message: str = ""
    level: str = "INFO"          # INFO | WARN | ERROR
    data: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Minimal synchronous pub/sub. Sinks never raise into producers."""

    def __init__(self):
        self._subs: Dict[str, List[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        """Register a handler for an event type, or '*' for all events."""
        self._subs.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]):
        if handler in self._subs.get(event_type, []):
            self._subs[event_type].remove(handler)

    def publish(self, event: Event):
        """Deliver to type-specific and wildcard handlers. A failing sink is
        isolated — observability must never break the producer."""
        for handler in list(self._subs.get(event.type, [])) + list(self._subs.get("*", [])):
            try:
                handler(event)
            except Exception as _e:
                import logging as _log
                _log.getLogger("hds.events").warning(
                    "event sink %s raised on '%s': %s", handler, event.type, _e)


# Process-wide default bus + convenience wrappers.
bus = EventBus()


def subscribe(event_type: str, handler: Callable[[Event], None]):
    bus.subscribe(event_type, handler)


def emit(event_type: str, message: str = "", level: str = "INFO", **data):
    """Publish an event on the default bus. Producers call this — not speak()."""
    bus.publish(Event(type=event_type, message=message, level=level, data=data))
