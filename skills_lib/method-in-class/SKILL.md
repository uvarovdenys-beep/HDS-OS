---
name: method-in-class
description: Use when the patch target contains a dot (Class.method) — the implementer must emit only the method, never the enclosing class.
applies_when: target_has_dot
---

The target is a METHOD inside a class. Emit ONLY that method, indented as a
class member, keeping any decorator (@staticmethod / @property / @classmethod)
attached to it.

Do NOT re-emit the class or its other methods. A second class declaration is
refused by the cage (R-PRESERVE: "declares X twice").

Measured: without this rule a 14B returned the whole class four times in a row
and every attempt was refused.
