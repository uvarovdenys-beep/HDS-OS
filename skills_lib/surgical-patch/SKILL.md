---
name: surgical-patch
description: Use when patching one named declaration in an existing file — everything except that declaration is discarded.
applies_when: patch_target
---

This is a surgical patch: emit ONLY the named declaration, nothing around it.

Anything else you return is discarded, and re-emitting neighbours risks
deleting them.
