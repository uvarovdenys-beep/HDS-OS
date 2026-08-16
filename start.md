# HDS OS — session start

Read this first. It is the handoff: where the project stands, the rules that
govern how we work, and what comes next.

---

## Working rules (non-negotiable)

> Rules that live only in prose are rules an AI ignores. The ones below that
> can be enforced ARE enforced, by scripts with exit codes:
> `write_path_audit.py` (R-19), `exec_path_audit.py` (single exec surface),
> `decompose_audit.py` (R-300), and the cage itself inside `scribe.py`.
> Run all three before committing; the test suite runs them too.

1. **Local AI develops. The operator orchestrates.**
   Code is produced by the HDS agent through the cage — not hand-written by the
   assistant. The operator writes *specifications*, *references*, and *prompts*.
   Hand-written code is the exception (creator path), and even then it goes
   through `scribe.execute(..., protocol_size="l")` so it is cage-verified too.

2. **Decompose at 300 lines, not at the R-01 limit.**
   R-01 (1000 lines) is the hard cage ceiling. The *working* rule is stricter:
   a file over **300 lines** should be split. One class per file.

3. **Keep the request window minimal.**
   Trim the prompt to the smallest thing that still fully specifies the task.
   Measured: a grate plus a surgical patch is **17x cheaper** than handing over
   a 300-line file and taking one back (`hds_stats.py`).

4. **Surgical edits, not whole-file rewrites.** *(ENFORCED)*
   ```
   {"op":"patch",  "path":"x.js", "target":"renderTokens", "content":"..."}
   {"op":"patch",  "path":"x.py", "target":"Thing.method", "content":"..."}
   {"op":"insert", "path":"x.py", "after_target":"keep_me", "content":"..."}
   ```
   Python resolves through the AST. **Ten other languages resolve through
   `lang/_locate.py`** — a brace/keyword walker that skips strings and comments.
   It refuses rather than guesses: ambiguous or unbalanced raises, and the
   caller falls back to explicit `start`/`end`.

5. **One model in memory. Check free RAM before loading.**
   Run ONE `agent.py` at a time (`HDS_SILENT=1`), and
   `pkill -f "agent/agent.py"` before starting another.
   **Restart the daemon after changing core** — it holds the old modules in
   memory and will silently test yesterday's code.

6. **Never commit keys.** `api_key` and `github_token` are gitignored.
   Verify: `git ls-files | grep -i -E "api_key|token"` must be empty.

7. **Commit as you go.** This was violated for a whole session: 200+ changes
   uncommitted, and code was lost twice with nowhere to roll back to.

---

## Where the project stands

**Cage (mature, measured).** R-19 zero-direct-write, R-01 size, R-PATH,
R-KERNEL, R-SEAL, R-CAP, R-AST per-language validation (fail-closed).
`benchmark.py`: **9/9 dangerous writes blocked, 0 false positives.**

**Three structural rules added this session, all enforced from `lang/register`
so a new language cannot forget them:**

- **R-PRESERVE** (`lang/_preserve.py`) — a rewrite may not silently DELETE a
  declaration, nor declare one twice at module scope. Found because a model
  re-emitted a whole file nine times, each valid JavaScript, each dropping
  working functions. Validity is not preservation.
- **R-STUB** (`lang/_stubs.py`) — an empty function must say it is a
  placeholder (`STUB:`/`TODO:`/`NotImplementedError`). A stub has the SHAPE of
  working code, so every check that reads shape says yes.
- **Multi-language locate** (`lang/_locate.py`) — surgical patching now works
  in **10 languages**, not just Python.

**Language coverage.** 15 extensions validated: `.py .js .mjs .cjs .jsx .ts
.tsx .c .h .cpp .cc .hpp .cs .rb .go .rs .php .sh .swift .html .svg`.
Real parsers, not regex: `clang`, `clang++`, `dotnet`, `node`, `tsc`, `ruby`,
`bash`, `php`. Absent toolchain degrades to hygiene and prints the install line.

**Agent (measured over 253 tasks this session).**
```
written 234/253 (92.5%) · first attempt 204 · after self-correction 30
gave up 19 · cage refusals 1939
C 10/10 · C++ 10/10 · C# 10/10 · PHP 10/10 · Ruby 10/11 · Python 130/139
```
`hds_stats.py` reads this from the agent's own log — no separate bookkeeping.

**Three levels: idea → structure → task.**
`agent/idea_tree.py` (tree + status + JSON the operator edits by hand),
`agent/decomposer.py` (AI proposes, human accepts — everything lands as draft),
`agent/task_tree.py` (the grate: a fixed signature the implementer cannot
change), `pipeline.py` (the runner joining plan to queue).
Proven end to end: a three-function module with shared state, built one
function at a time, working.

**Context materialisation** (`agent/context.py`). A structure declares its
module state and it is written to the file BEFORE any task runs. Without it,
three functions each wrote `global _session` that nothing had declared and the
module would not import.

**Console** (`console_server.py` + `storage/mockup/console.html`) — live plan,
pipeline control, dialogue with a local model. Port from the instance registry,
never a constant.

**MCP surface** — 14 tools: `cage_write/patch/insert`, `tree_*`, `agent_*`.
Works inside Cline; `.clinerules/workflows/` holds `/idea`, `/makestructure`,
`/maketasks`, `/build`.

**VS Code plugin** — `HDS_VSCODE/hds-vscode-0.1.0.vsix`, installed and working.
Its `mcpClient.ts` and `extension.ts` were written by local models.

---

## Honest gaps (next priorities)

1. **The mirror graph — BUILT (first cut). Cross-file contracts, was the
   biggest hole.** Two graphs that mirror each other: the PLAN graph (idea_tree
   — signatures, depends, files: what should be) and the CODE graph (parsed from
   the files — declarations, calls: what is). Neither is authoritative. The
   value is the DIFF between them, surfaced for a human, not enforced:
     in plan, not in code   -> task unimplemented
     in code, not in plan   -> code outside the plan
     signatures differ      -> drift  (DONE — signature_drift)
     plan: A depends B / code: A never calls B -> broken contract
   This replaces the earlier R-SIGNATURE idea, which made the plan authoritative
   over the code — wrong, because a stale plan would then reject correct code. A
   mirror does not decide who is right; it makes the disagreement visible, the
   way hds_doctor does for system state.

   DONE this session (both through the cage; diff_graphs & extract_calls written
   by the local model, acceptance-verified):
     a) CALL EDGES — `agent/call_edges.py::extract_calls` (AST walk) fills a
        `calls` list per symbol in orchestrator_index; 151 symbols across 51
        modules now carry edges. `used_by` is NOT stored — compute on demand.
        (Modifying the index through the cage forced dropping its module-level
        `import os`, which the Python validator rejects as DANGER — now pathlib.)
     b) THE DIFF — `agent/mirror_graph.py`: load_plan + code_graph + diff_graphs
        + a CLI (`python3 agent/mirror_graph.py <tree.json> --root .`) and 8
        tests. On I1/I4 it correctly reports the plan's functions unimplemented
        and the storage/ files absent.

   THE MIRROR GRAPH IS NOW COMPLETE. All four disagreements are surfaced, for
   Python AND for JavaScript/TypeScript (`js_graph.py`, regex by the same
   reasoning as lang/_locate). Run against the real I2 plan it found 9 planned
   functions missing from extension.ts, 1 unplanned symbol and 2 broken
   contracts (activate declares initializeMcpClient and registerCommands and
   calls neither) — invisible before. Comparison lives in `graph_diff.py`.
   Remaining nuance:
     · SIGNATURE-DRIFT is now DONE: code_graph records each function's real
       parameter names, plan_params reads the promised ones from the plan
       signature, and signature_drift reports the disagreements. Types and
       defaults are ignored on purpose — `name: str = ""` vs `name=""` is
       agreement. All three disagreement kinds are now surfaced.
     · broken_contract currently means "a declared `depends` the code never
       calls"; the reverse (code calls a sibling the plan never declared) is
       visible only as edges, not yet a bucket.

   Also unmeasured but present: `agent/context.py` materialises shared state,
   `acceptance.py` runs plan-declared assertions (catches wrong-but-stable
   logic Monte Carlo cannot), never benchmarked at scale.

   MEMORY (episodic) is now live and closes the loop: a corrected failure is
   recorded as a lesson (`reflexion.lesson_from_error` → `AIExperienceModule`),
   and `_execute_ai_task` RECALLS relevant lessons before generating. Recall is
   SEMANTIC (`embed.py` → local nomic-embed-text, cosine × severity, boosted for
   lessons anchored to the file being changed) with a similarity floor
   (`HDS_RECALL_MIN=0.55`) — no "last-N" leak. Falls back to keyword when the
   embed model is down. `consolidate()`/`consolidate_store()` drop near-duplicate
   lessons (cosine ≥ 0.92). Cage rejections now carry an actionable hint back to
   the model (`cage_help.explain`, wired into the self-correction feedback) —
   aimed at the top give-up cause. Still to do: distil the raw error line into a
   GENERALISED rule (an LLM-reflection step, not just dedup), and a
   skill-library of verified reusable functions.

2. **Generation quality is not tracked over time.** `hds_stats.py` reports the
   current log; nothing writes the number into CHANGELOG per release, so
   "better" stays a belief. Wire `bench_generation.py` into CI on 20 tasks.
   PARTIAL: `hds_failures.py` now classifies failures by REASON (cage /
   acceptance / monte_carlo / timeout / refused / gave_up) from the log — the
   "why" is measured (cage rejections dominate, then refusals, 62 real
   give-ups). `attribute_giveups` now credits each give-up to its LAST cause:
   of 62 give-ups, cage 61% / monte_carlo 19% / unknown 16% / acceptance 3% —
   the target is cage-unsatisfiable and runtime crashes. Still missing: tracking
   the numbers ACROSS releases (snapshot per release into a history/CHANGELOG).
   NOTE: `hds_failures.py`, `cage_help.py`, `embed.py` and the reflexion/memory
   functions were all written by the LOCAL model through the cage
   (acceptance-verified) — the operator wrote only grates and checks.

3. **`agent_ai_pipeline.py` does too much** (681-line baseline) — model
   resolution, canary, generation, self-correction, cage, Monte Carlo, accept,
   archive in one flow. Split into `generate` → `verify` → `commit`.
   FIXED this session: step 6 read `decompose_result.files_created` (never a
   field on DecomposeReport) and crashed the post-write reporting on any
   generation over 200 lines — now `len(.extracted)`. Also freed the file of
   `import os` (moved the HDS_SELF_CORRECT read to
   `pipeline_helpers._self_correct_tries`) so the flow file is itself
   cage-patchable. The split is still to do.

4. **Seven services, each its own `http.server`** (webhook 8110, console 8114,
   site 8231, panel 8242, mockup 8253, game 8275). One server by prefix.

5. **Unwritten conventions.** `os` POLICY IS NOW OPERATION-LEVEL (changed this
   session, `ast_validator.py`): `import os` and the benign surface (os.path,
   os.environ, os.makedirs, os.listdir …) are **allowed** — the earlier
   "no os / use pathlib" rule is retired. Only the process-spawning surface
   (`os.system/popen/exec*/spawn*/fork/posix_spawn`) is CRITICAL-forbidden for
   everyone (it bypasses the single sandboxed exec surface). So the pathlib
   refactors in orchestrator_index / agent_ai_pipeline were a one-time cost, no
   longer required for new os-using code. Other conventions still tacit:
   `protocol_size=None` is for trusted system calls only; `delete` needs
   protocol `xl` (R-CAP), `write`/`patch` accept `l`. Written: see `CONVENTIONS.md`.

6. **`.h .mjs .cjs .vue .svelte .kt .scala` are not in `scribe.CODE_EXTS`** —
   written as unscanned data. `.h` and `.mjs` matter most. Editing that list
   needs a human: R-KERNEL forbids writing `scribe.py`, deliberately.

7. **Monte Carlo catches crashes, not wrongness.** Now classified by meaning:
   `NameError`/`RecursionError` fail, domain rejections pass. A destructive
   `size()` that ate the queue still got through — only a declared assertion
   caught it (`acceptance.py`, written but never measured at scale).
   Monte Carlo now runs for **Python, JavaScript and TypeScript**
   (`montecarlo.py` dispatches by extension; JS/TS parse top-level function
   declarations and call them in a node sandbox, .ts via
   `--experimental-strip-types`). ReferenceError/RangeError are the JS
   analogues of NameError/RecursionError and count as failures; other throws are
   domain guards.

8. **Verification parity — WHY JS/TS trailed Python, now half-closed.** Python
   got THREE self-correction signals (cage + acceptance + Monte Carlo); every
   other language got only the cage. That, not model strength, explained
   Python 93% vs JS 85% / TS 83%. DONE this session: **acceptance now runs for
   JavaScript and TypeScript**, not just Python (`acceptance.py` dispatches by
   extension; .js/.cjs/.mjs → `node:20-alpine`, .ts → `node:22-alpine` with
   `--experimental-strip-types`; assertions are written in the subject's
   language — JS uses `===`/`JSON.stringify`). Verified live: JS and TS greet()
   each failed acceptance then self-corrected. **JS/TS Monte Carlo now DONE too**
   (gap #7): Python, JavaScript and TypeScript share all THREE signals (cage +
   acceptance + Monte Carlo). Surgical patching: measured that the brace walker
   already locates all top-level functions (7/10 realistic targets); the one gap
   was class methods, now closed for **JS/TS** (`Class.method` via
   `lang/_locate._js_method_span`). C#/C++/Java/Swift methods (return type before
   the name) stay on the safe fallback — that is the one place tree-sitter would
   still earn its dependency, deliberately deferred (the walker is stdlib by
   design).
   **New sandbox deps:** `node:20-alpine` and `node:22-alpine` images must be
   pulled (hds_doctor does not yet check for them).

---

## Measured on the models (2026-08-02)

Same tasks, real pipeline, acceptance-checked:

    qwen2.5-coder-14b   3/3 easy/medium/hard in 25s; 2/2 genuinely hard
                        (interval merge, precedence expr eval) in 27s
    prism-ml/bonsai-27b 3/3 in 131s (5x slower — a reasoning model, ~280 of
                        295 tokens spent thinking on a trivial task)

The finding that matters: the 14B WITH the scaffolding (grate + acceptance +
self-correction + orchestrator skills) solves tasks that would normally be
reached for a bigger model. Escalation should therefore be rare, and the ladder
is ordered by capability-per-RAM, not parameter count. Bonsai works with HDS
unchanged because make_lmstudio_caller already falls back to reasoning_content;
it is only ~4GB resident, which is why it is the first rung. qwen3-coder:30b is
LAST: it goes resident at 44.5GB, left this box with 8.5GB free, and stalled on
its own canary.

## What is unfinished

- **The site** (`storage/site/`) — DONE: 5 languages, two inline-SVG charts from
  real `hds_stats` figures (redrawn on language switch), and a repository link
  (hero + footer) to the now-PUBLIC `github.com/uvarovdenys-beep/HDS-OS`. Served
  by `hds-site` (port 8231); `storage/` is gitignored (deploy artifact) so the
  changes live on disk — propagate to `HDS_DEPLOY` to publish. Richer long-form
  copy is still thin if more is wanted.
- **The game** (`storage/game/`) — «Лис Микита». Design and map are right:
  four 18-cell serpentine tracks from the corners, a 40-cell fox burrow
  crossing all zones, a 4×4 court. `createBoard` still runs an older 32-cell
  table; the zone names (Пасіка/Ліс/Село/Комора) and the fox rules (rolls for
  movement along the burrow, plants a trap in its current zone each turn) are
  agreed but not implemented.
  Monte Carlo on 20 000 games: **beasts 85.4%, fox 14.6%** — the fox needs
  a stronger lever; converting seized evidence into bribe is the thematic fix.
- **204 uncommitted changes.** Commit before anything else.

---

## Start a session

```bash
cd HDS_CORE
export PATH="$HOME/.local/bin:$PATH"

python3 -m pytest tests/ -q | tail -1     # expect: 276 passed
python3 write_path_audit.py | tail -1     # expect: Level-3 OK
python3 exec_path_audit.py  | tail -1     # expect: single exec-path sealed
python3 decompose_audit.py  | tail -1     # expect: R-300 OK
python3 benchmark.py | tail -3            # expect: 9/9, 0 false positives

python3 hds_doctor.py                     # isolation, toolchains, models, RAM
python3 hds_stats.py                      # how generation is actually doing

pkill -f "agent/agent.py"                 # one instance only
HDS_SILENT=1 python3 agent/agent.py --monitor &
```

Build through the agent, one function at a time:

```python
agent._execute_ai_task(
    task_id="X", instruction="...", model_name="qwen/qwen2.5-coder-14b",
    output_dir="storage/x", output_filename="y.js",
    patch_target="theFunction",          # surgical: 10 languages supported
    reference_files=[{"name": "spec.md", "content": grate}])
```

Finish every session: stop daemons, unload models, clear test artifacts, run
the checks above, **commit**, propagate to deploy, keep deploy at ONE commit.
