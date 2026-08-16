---
name: javascript
description: Use for JavaScript (.js/.mjs/.cjs/.jsx) tasks.
applies_when: lang=JavaScript
---

- Compare with `===`. `==` on arrays or objects is reference equality —
  serialise with JSON.stringify when comparing contents.
- Use const/let, never var. Declare before use.
- An async function returns a Promise; only await inside async.
