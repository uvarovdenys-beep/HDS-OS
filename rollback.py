#!/usr/bin/env python3
"""rollback.py — undo a generation that never earned its place on disk.

THE HOLE THIS CLOSES. scribe writes the file BEFORE acceptance and Monte Carlo
run, and it has to: those verifiers execute the written file. But nothing put
the file back when every attempt failed. A task that gave up — or a process
killed mid-loop, which happened during development — left a REJECTED version
sitting on disk, looking exactly like finished work.

Forward-only was the gap: the cage, the audits and the tests all check what is
about to happen, and nothing could undo what already had.

HOW THE RESTORE GETS PAST THE CAGE. Putting an older version back DELETES the
declarations the failed attempt added, and R-PRESERVE refuses exactly that. Its
sanctioned escape for an intentional removal is delete-then-write, so that is
what a restore does — deliberately, through scribe, never behind its back.
"""
from pathlib import Path

ABSENT = object()      # the file did not exist before the task ran

# Why the last restore declined. A rollback that fails silently is worse than
# one that fails loudly: the rejected file stays on disk and nobody knows. This
# swallowed a cage R-PATH error for a whole test run before it was noticed.
LAST_ERROR = ""


def snapshot(path) -> object:
    """Capture a file's current contents, or ABSENT if there is no file yet.

    Never raises: a snapshot that fails must not stop a build, it only means
    the rollback will decline later.
    """
    p = Path(path)
    try:
        if not p.exists():
            return ABSENT
        return p.read_text(encoding="utf-8")
    except OSError:
        return None        # unreadable: refuse to pretend we can restore it


def restore(path, state) -> bool:
    """Put `state` back. True when the file now matches the snapshot.

    A file that did not exist is deleted again; one that did is rewritten from
    the snapshot. Both go through scribe: `xl` because a delete is involved, and
    because a rollback is a deliberate, trusted act rather than model output.
    """
    global LAST_ERROR
    LAST_ERROR = ""
    if state is None:
        LAST_ERROR = "no usable snapshot"
        return False
    p = Path(path)
    try:
        import scribe
    except ImportError:
        LAST_ERROR = "scribe unavailable"
        return False

    try:
        if state is ABSENT:
            if p.exists():
                scribe.execute({"op": "delete", "path": str(path)},
                               protocol_size="xl")
            return True
        # Delete first: rewriting in place would drop whatever the failed
        # attempt declared, and R-PRESERVE refuses that (correctly).
        if p.exists():
            scribe.execute({"op": "delete", "path": str(path)},
                           protocol_size="xl")
        scribe.execute({"op": "write", "path": str(path), "content": state},
                       protocol_size="xl")
        return True
    except Exception as e:
        LAST_ERROR = f"{type(e).__name__}: {e}"
        return False


def describe(state) -> str:
    """One line for the log, so a rollback is never silent.

    Deliberately PURE: it describes the SNAPSHOT, not the last attempt. Reading
    LAST_ERROR here made it report a stale failure for an unrelated call — check
    LAST_ERROR at the call site instead.
    """
    if state is ABSENT:
        return "removed the file it created"
    if state is None:
        return "could not roll back (no usable snapshot)"
    return f"restored {len(state.splitlines())} line(s)"
