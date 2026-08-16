---
name: typescript
description: Use for TypeScript (.ts/.tsx) tasks. The cage runs tsc --noEmit, so types must be complete.
applies_when: lang=TypeScript
---

- Type EVERY parameter, callback argument and return value explicitly — an
  implicit any fails `tsc --noEmit`, which the cage runs.
- Do not silence errors with `any` or `@ts-ignore`; give the real type.
- Optional parameters come last; handle undefined explicitly under strict null
  checks.
