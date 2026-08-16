# HDS conventions

Rules that used to live only in people's heads, where every one of them cost
someone a failed run before they learned it. Enforced rules point at the script
that enforces them; the rest are stated so they can be followed on the first try
instead of the third.

---

## Writing files

**Everything goes through the cage.** No module writes a project file directly;
`scribe.execute()` is the only door. *(Enforced: `write_path_audit.py`. A new
direct write fails the audit until it is sanctioned in the baseline, which is
for system I/O — a store writing its own JSON — not for generated code.)*

**`protocol_size` is a capability, not a formality.**

| size | may write code | may delete |
|------|----------------|------------|
| `s` / `m` | no | no |
| `l` | yes | no |
| `xl` | yes | yes |
| `None` | yes | yes |

`None` means "trusted system call" and skips the capability gate entirely. Use
`l` for anything an AI produced, and `xl` only when a delete is genuinely
intended. *(Enforced: R-CAP inside `scribe.py`.)*

**Patch, do not rewrite.** `{"op":"patch", "target": "name"}` replaces exactly
one declaration; `{"op":"insert", "after_target": "name"}` adds after one. A
whole-file rewrite destroys comments and neighbours nobody asked to touch, and
is 17x more expensive. *(Measured: `hds_stats.py`.)*

---

## Writing Python

**`os` is judged per OPERATION, not per module.** `import os` is fine, and so
are `os.path`, `os.environ`, `os.makedirs`, `os.listdir`. Only the
process-spawning surface is forbidden — `os.system`, `os.popen`, `os.exec*`,
`os.spawn*`, `os.fork` — because those bypass the single sandboxed exec surface.
*(Enforced: `ast_validator.py`. The old rule banned the whole module and forced
pointless pathlib refactors; it was retired 2026-08-02.)*

**Nothing spawns a process except `sandbox/`.** No `subprocess` anywhere else.
*(Enforced: `exec_path_audit.py`.)*

**Also refused:** `eval`, `exec`, `compile`, `__import__`, `getattr`/`setattr`,
`globals()`/`vars()`.

**Split at 300 lines.** The cage ceiling is 1000 (R-01); the working rule is
300, one class per file. Existing debt is frozen in a baseline and may not grow.
*(Enforced: `decompose_audit.py`.)*

**Empty bodies must announce themselves.** `STUB:`, `TODO:`, `FIXME:`,
`NotImplementedError` — or, for a deliberate no-op override, `NO-OP:` with the
reason. A stub has the SHAPE of finished work, so every check that reads shape
says yes. *(Enforced: R-STUB, `lang/_stubs.py`.)*

**A rewrite may not drop a declaration**, nor declare one twice at module
scope. *(Enforced: R-PRESERVE, `lang/_preserve.py`. Found because a model
re-emitted a file nine times, each valid, each losing working functions.)*

---

## Writing for other languages

- **TypeScript** — type every parameter, callback argument and return. The cage
  runs `tsc --noEmit`, and an implicit any fails it.
- **JavaScript** — inline `<script>` may not contain `eval(`, `Function(` or
  `import(`. Ordinary `function(){}` is fine; only dynamic code construction is
  refused. No inline event handlers, no `javascript:` URLs.
- **Go** — an unused import is a compile error, so import only what is used.

Language nuances belong in `skills_lib/`, not in prose: a skill is loaded into
the prompt only when its trigger fires, so it actually reaches the implementer.

---

## Verifying generated code

Three signals, and Python, JavaScript and TypeScript now get all three:

1. **The cage** — safety and structure. Says nothing about whether it works.
2. **Acceptance** — assertions declared in the plan, executed against the code
   in the sandbox. Catches wrong-but-stable logic, which Monte Carlo cannot:
   `return a - b` survives a thousand random calls.
3. **Monte Carlo** — randomised arguments, in the sandbox. Catches crashes and
   hangs, not wrongness.

Assertions are written **in the subject's language**: JS uses `===`, and
compares arrays via `JSON.stringify` because `==` on an array is reference
equality.

A language with no runner returns `"unverified"` — never a false pass.

---

## Models

**One model in memory.** `pkill -f "agent/agent.py"` before starting another,
and check free RAM first. A 30B goes resident at ~44GB and will starve the box.

**Never hardcode a model id.** LM Studio serves `qwen/qwen2.5-coder-14b`, not
`qwen2.5-coder-14b`; `_resolve_model` binds a request to what the machine
actually serves.

**Escalate rather than re-roll.** After two failed attempts on the same
feedback, move up `PipelineHelpersMixin.LADDER`. The ladder is ordered by
measured capability-per-RAM, not parameter count.

**Reasoning models work unchanged** — `make_lmstudio_caller` falls back to
`reasoning_content` when `content` is empty. Give them token headroom
(`HDS_MAX_TOKENS`); a reasoning model can spend 280 of 295 tokens thinking.

---

## Memory

- **Failures** become lessons (`reflexion.py` → `ai_experience`), recalled
  semantically with a similarity floor. Below the floor: nothing. Silence beats
  irrelevant advice in a prompt.
- **Successes** enter `skill_library.py` ONLY after all three signals passed.
  An unproven example propagates its own mistake to every later task.

---

## Committing

Commit as you go. Never commit keys — `api_key` and `github_token` are
gitignored in core, excluded from `propagate.sh`, and blocked by the deploy's
own `.gitignore`. The deploy repository is PUBLIC; verify before pushing:

    git diff --cached --name-only | grep -iE "api_key|\.env|\.pem"

`storage/` is gitignored in core and excluded from propagation — the site and
the console mockup live there and are copied into the deploy by hand.

---

## What to delegate, and what to write yourself

The local model writes the code; the orchestrator writes the grate. That holds
for most work — but not all, and pretending otherwise burns attempts.

**Delegate** anything whose contract is short and whose correctness is
checkable: a transformation over data structures, a lookup, a diff, a
classification. `diff_graphs`, `classify_failure_line`, `lesson_from_error`,
`extract_calls` and `consolidate` were all written by a 14B on the first or
second attempt, because a one-line signature plus assertions fully described
them.

**Write it yourself** when the SPEC would be longer than the code. Character-level
scanners are the clearest case: `strip_noise` (blank out strings and comments,
preserving exact length and line structure) and `params_of` (split on
depth-zero commas, strip types and defaults) both failed four attempts each and
kept failing after escalating to a 27B — not because the models are weak, but
because every edge case has to be stated, and by then the prose IS the
implementation. Measured 2026-08-02.

**The tell:** if writing the acceptance assertions feels like enumerating the
algorithm, stop delegating and write the function.

**Escalation is not a fix for a bad grate.** It moves up the ladder after two
failures (telemetry shows it firing correctly in production), but a stronger
model given an ambiguous spec produces a different wrong answer, not a right
one. Fix the grate first.
