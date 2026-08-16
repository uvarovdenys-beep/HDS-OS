"""sandbox/ — the single execution surface of the HDS cage.

Mirror of write_path_audit's idea, but for *execution*: just as the cage has one
audited write path, non-Python work runs ONLY through here. The AI (Tier-1
Python, in-cage) cannot spawn processes — scribe's content gate denies
`subprocess`. This package is privileged, creator-owned code: it is the one place
allowed to spawn, and every spawn is hardened + audited.

Languages are not "understood" here; they are *contained at runtime*. A language
is available iff its toolchain image + a sandboxed adapter exist.
"""

from .runner import RunRequest, RunResult, SandboxRunner  # noqa: F401
