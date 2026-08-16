# Changelog

## v1.3.0 — 2026-08-16

Undo, a mirror that sees TypeScript, memory that remembers successes, and
checks a human can read.

MEASURED THIS RELEASE
  tests            359 passing (was 321)
  cage benchmark   9/9 dangerous writes blocked, 0 false positives
  models           qwen2.5-coder-14b 3/3 in 25s; bonsai-27b 3/3 in 131s.
                   The 14B also took 2/2 genuinely hard tasks (interval merge,
                   precedence expression eval) in 27s — with the scaffolding,
                   the small model is a strong default.

ROLLBACK
- scribe must write before acceptance and Monte Carlo can run, so a task that
  fails has already changed the file, and nothing put it back. Now the file is
  snapshotted before the first write and restored when every attempt fails.
  Restoring drops what the failed attempt added, which R-PRESERVE refuses, so a
  restore uses delete-then-write — its sanctioned escape. A test proves the
  plain rewrite really is refused.

THE MIRROR GRAPH IS COMPLETE
- js_graph parses JavaScript and TypeScript, so .ts leaves are no longer
  reported "unparsed". Against the real plugin plan it found 9 planned
  functions missing, 1 unplanned symbol and 2 broken contracts.
- signature_drift closes the last of the four disagreements. Types and defaults
  are ignored: `name: str = ""` and `name=""` are agreement, not drift.

MEMORY REMEMBERS SUCCESSES
- skill_library admits a function only after the cage, its assertions AND Monte
  Carlo passed. An unproven example propagates its own mistake.
- Escalation moves up a ladder of served models after two failures, ordered by
  measured capability-per-RAM rather than parameter count.

READABLE CHECKS
- hds_perevirka runs every audit and says, in Ukrainian, what was checked, what
  it means, and what to do if it is not green.
- hds_snapshot pins the numbers to a release so "better" stops being a belief.
- CONVENTIONS.md writes down the rules that used to cost a failed run to learn,
  including which work to delegate and which to write yourself.

NAME
- HDS6/HDS7 are gone; the product is HDS OS.

FOUND WHILE BUILDING
- test_fuzzer repointed the cage's ROOT and never restored it, so every later
  test writing through scribe hit R-PATH. Guarded in conftest now.
- A file can be allowlisted for subprocess by exec_path_audit and still be
  unwritable through the cage, which freezes it. Known, not yet reconciled.


## v1.2.0 — 2026-08-02

Verification parity, a memory that learns, and knowledge the orchestrator can
hand over.

MEASURED THIS RELEASE
  tests            321 passing (was 268)
  cage benchmark   9/9 dangerous writes blocked, 0 false positives
  languages        Python, JavaScript, TypeScript all get cage + declared
                   acceptance assertions + Monte Carlo (JS/TS had only the cage)
  give-up causes   cage 61%, monte_carlo 19%, unknown 16%, acceptance 3%

VERIFICATION PARITY
- acceptance.py runs for .js/.cjs/.mjs (node:20) and .ts (node:22, type
  stripping), not just Python. Assertions are written in the subject's language.
- montecarlo.py calls JS/TS functions with seeded random arguments in the same
  sandbox. ReferenceError/RangeError count as defects; other throws are treated
  as domain guards, matching the Python probe.

MEMORY
- A corrected failure becomes a lesson (reflexion.py), recalled SEMANTICALLY
  next time (embed.py -> local nomic-embed-text, cosine x severity, boosted for
  lessons anchored to the same file). A similarity floor replaces the old
  "last 5 regardless" leak. Near-duplicates are consolidated.

ORCHESTRATOR SKILLS
- skills_lib/ holds skills in the Claude Skills format: one folder, a SKILL.md
  with frontmatter, a description that says when it applies. Progressive
  disclosure — only triggered skills enter the prompt. This carries the nuance a
  signature cannot (a method inside a class, TypeScript typing, cage rules).

TELEMETRY
- Every pipeline stage emits JSONL (task_id, stage, verdict). hds_failures no
  longer depends on grepping a human log, and the console gets a live stage.

CAGE, NARROWED WHERE IT WAS TOO BROAD (all measured against the benchmark)
- `os` is judged per OPERATION, not per module: os.path/environ/makedirs are
  ordinary and allowed; os.system/popen/exec*/spawn*/fork stay CRITICAL for
  everyone, because they bypass the single sandboxed exec surface.
- The inline-script rule was case-insensitive, so every `function(){}` matched
  the `Function(` constructor rule. Case-sensitive now.
- R-STUB accepts NO-OP: for a deliberately empty override, so finished work no
  longer has to lie with TODO:.

ALSO
- Surgical patching reaches JS/TS class methods (Class.method).
- extract_target descends into classes — the real cause of a 14B failing four
  times with R-PRESERVE.
- Model escalation: after two failed attempts the loop moves up a ladder of
  served models, ordered by capability-per-RAM.
- Mirror graph: call edges in the code graph, plus a plan-vs-code diff.
- RUN_MAC/ and RUN_WIN/ launchers grouped by purpose (AGENT/API/CHECK/WEB).


## v1.1.0 — 2026-06-25

Per-language architecture + honest guarantees + the execution surface.

- **`lang/` registry** — capability granted by code only (fail-closed); per-language
  `validator`/`decompose`/`meta`. **Toolchain-backed validation** via SandboxRunner
  (`lang/_toolchain.py`): JS uses `node --check`, C++ uses `clang++ -fsyntax-only`
  (real parsers, not regex; auto-fall-back to hygiene when a tool is absent).
  Toolchain-validated: Python (AST), JS (runtime-aware: browser-vs-node hygiene +
  node `--check` as ES-syntax parser), TS (tsc), C++ (clang++), C# (dotnet build),
  PHP (`php -l`, static no-root binary). HTML stays at injection-hygiene (HTML has
  no syntax-error concept — tidy only corrects). CSS/JSX hygiene/data. `.cs .cc
  .hpp` added to CODE_EXTS; compiled langs validated but build/run still gated.
  Installed tsc (npm user-prefix), dotnet SDK + static php (no-root);
  `_toolchain.resolve()` searches `~/.npm-global`, `~/.dotnet`, `~/.local/bin`.
- **`sandbox/` + `exec_path_audit.py`** — single execution surface (mirror of
  write_path_audit), now SEALED (subprocess confined to sandbox/). Two
  `shell=True` breaches (task_yaml_support, build_certify) closed — routed through
  SandboxRunner (no shell, shlex argv). Backends: DockerBackend (`isolated=True`,
  hardened container) auto-selected when a runtime exists; SubprocessBackend
  (`isolated=False`, no-shell + rlimits) as honest degraded fallback otherwise.
- **Honest guarantees** — split *structural containment* (real) from *content
  hygiene* (AST denylist with documented bypasses; see test_cage_adversarial.py).
  Renamed benchmark "containment" → "block rate".
- **ast_validator** — fixed `re.compile` false-positive (Name-only); closed
  `importlib`/`globals`/`vars` leaks.
- **Hygiene** — removed .bak/.backup from core; creator tooling → `_creator_tools/`;
  safe core→deploy propagation (`propagate.sh`).

## v1.0.0 — 2026-06-15

First release of HDS OS — a self-contained, copyable AI-containment operating
system. Turns any LLM (local or server, weak or "thinking") into a bounded,
verified executor: the model proposes, deterministic code disposes.

### The cage (4 enforcement levels)
- **Level 1 — intent**: `scribe` gates every task-script — path-escape, size
  (R-01), capability-by-protocol (S/M/L/XL), before any write.
- **Level 2 — content**: per-language AST scan; Python via `ast_validator`,
  unknown code languages **default-denied** (no silent leak).
- **Level 3 — integrity**: `write_path_audit` freezes the write surface — no new
  write path past scribe (wired into `verify_system.sh` + CI).
- **Level 4 — trust**: two-axis diagnostic gates autonomy by **compliance**, not
  capability — a smart-but-disobedient model is pinned to S.

### Runtime
- Orchestrator: local LLM acts as both orchestrator and executor, SINGLE MODEL
  (one model in VRAM; unloaded before the deterministic write).
- Per-project ports via `port_registry` (system-checked, no hardcoded defaults);
  API resolves from registry, dashboard uses relative URLs.
- Event bus (`events`) — voice/log/metrics are optional sinks, not wired into logic.
- Daemons: vision, browser, web-search, doc, hibernation.

### Proof
- Containment benchmark: **100% dangerous blocked, 0% false-positive**.
- Test suite passes (live-model tests auto-skip without an endpoint).
- Fixed two latent fictitious guards (`ast_validator` worst-level, `shadow_verifier`
  fail-open) — now fail-closed.

### Packaging
- Pure-stdlib kernel, zero required dependencies (extras: `api`, `daemons`).
- MIT licensed. Own git repo, in-repo CI. Drop-in: copy the folder, run a launcher.
