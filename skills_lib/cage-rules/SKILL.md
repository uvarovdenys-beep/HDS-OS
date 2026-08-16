---
name: cage-rules
description: Always applies. The four cage rules that cause most rejections, in every language.
applies_when: always
---

- Never delete or rename an existing declaration you were not asked to change;
  a rewrite that drops one is refused (R-PRESERVE).
- If something must stay unimplemented, say so: raise NotImplementedError or
  write a STUB:/TODO: comment. A silently empty body is refused (R-STUB).
- No eval, exec, compile, getattr/setattr or dynamic import. No subprocess and
  no os.system/popen/exec*/spawn* — running a process is the sandbox's job.
- Keep the file under 300 lines; one class per file.
