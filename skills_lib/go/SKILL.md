---
name: go
description: Use for Go tasks. Unused imports are compile errors, which is the top generated-Go failure.
applies_when: lang=Go
---

- An unused import or variable is a COMPILE ERROR — import only what you use.
- Check every returned error explicitly; never discard it with `_`.
- Exported identifiers start with a capital letter; indent with tabs (gofmt).
