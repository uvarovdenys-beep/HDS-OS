"""Hygiene-level checks (NOT containment).

Regex heuristics that catch naive-dangerous constructs in non-Python languages.
This is code HYGIENE, not a sandbox: true containment for these languages is
process isolation, not source scanning. Default-deny still holds.
"""
from . import LangReject


def deny_scan(content, path, patterns):
    for label, rx in patterns:
        if rx.search(content):
            raise LangReject(f"'{path.name}' hygiene-blocked: {label}")
