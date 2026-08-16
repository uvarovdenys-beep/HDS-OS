---
name: python
description: Use for Python (.py) tasks. Nuances that trip small local models.
applies_when: lang=Python
---

- Annotate every parameter and the return type; public functions and classes
  get a one-line docstring.
- Never use a mutable default argument (`def f(x=[])` is a bug) — use None and
  build inside.
- `os` is allowed for paths and environment (os.path, os.environ, os.makedirs);
  only the process-spawning calls are forbidden.
- Do not add an `if __name__ == "__main__"` block unless asked.
