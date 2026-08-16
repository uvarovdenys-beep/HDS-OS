---
name: markup
description: Use for HTML/SVG tasks. The cage refuses inline handlers and dynamic code.
applies_when: lang=HTML
---

- No inline event handlers (onclick=…), no `javascript:` URLs.
- No eval( or Function( in inline scripts. Ordinary `function(){}` expressions
  are fine — only dynamic code construction is refused.
- SVG must be static markup: no script, no external references.
