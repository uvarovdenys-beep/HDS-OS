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
   a file over **300 lines** should be split. One class per file. Functions and
   methods grouped by a single concrete task. See the backlog below.

3. **Keep the request window minimal.**
   Always trim the prompt to the smallest thing that still fully specifies the
   task. Long prose dilutes; local models drop details. Prefer a short
   instruction + a `reference_files` example over a long description.

4. **Surgical edits, not whole-file rewrites.** *(ENFORCED — scribe ops)*
   Name the target; HDS finds its exact lines and replaces only those:
   ```
   {"op":"patch",  "path":"x.py", "target":"fix_me",        "content":"..."}
   {"op":"patch",  "path":"x.py", "target":"Thing.method",  "content":"..."}
   {"op":"patch",  "path":"x.py", "start":10, "end":20,     "content":"..."}   # any language
   {"op":"insert", "path":"x.py", "after_target":"keep_me", "content":"..."}
   ```
   Python targets resolve through the AST (decorators included). The PATCHED
   RESULT then passes the full cage — surgery never becomes a hole.

5. **One model in memory. Check free RAM before loading.**
   `_enforce_single_model()` evicts other resident ollama models;
   `_ram_ok_for_model()` refuses to load below `HDS_MIN_FREE_MB` (800).
   When testing: run ONE `agent.py` at a time (`HDS_SILENT=1`), and
   `pkill -f "agent/agent.py"` before starting another.

6. **Never commit keys.** `api_key` is gitignored; test keys go in `env` only
   and are unset immediately after. Verify with
   `git ls-files | grep -i api_key` (must be empty).

---

## Where the project stands

**Cage (mature, heavily tested).** R-19 zero-direct-write, R-01 size, R-PATH,
R-KERNEL, R-SEAL, R-CAP, R-AST per-language validation (fail-closed).
Level-3 audits seal a single write surface and a single exec surface.

**Autonomous agent (works, soak-tested).** Model resolution from what the box
actually serves → canary → language-aware generation → cage → watchdog →
quarantine with coder-first model escalation → archive.
Proven over 100+ single-file tasks and 50 multi-file projects; multi-file
coherence ≈97% after the sibling-context and missing-import fixes.

**Two front ends, one contract.** `agent/task_bridge.py` is the single
enqueue/poll implementation used by BOTH the HTTP webhook (external/server AI,
API-key authenticated) and `mcp_server.py` (agent-as-MCP for editors).
Never duplicate that contract per front end — that drift was a real bug once.

**Editor integration decided.** A **VS Code plugin** over **agent-as-MCP**
(the full agent, not the bare cage). Void was dropped. The plugin is a thin TS
client; HDS stays Python and is bundled/managed by it.

**Plugin lives in `HDS_VSCODE/`** — never in `storage/`. The cage sandbox is
wiped after every test run and is excluded from propagate; plugin artifacts left
there were destroyed once. Generated candidates land in
`HDS_CORE/storage/vscode_build/`, then `_creator_tools/promote_plugin.sh` moves
them into `HDS_VSCODE/{src,media}/`.
Built and cage-verified: `package.json`, `tsconfig.json`,
`media/panel.{html,css,js}`, `design_reference.css` (the style spec passed to the
agent as `reference_files`). Still missing: `src/mcpClient.ts`,
`src/extension.ts`, npm install + compile, diff-review, async progress, `.vsix`.

---

## Honest gaps (next priorities)

1. ~~Surgical line-editing~~ — **DONE**: `patcher.py` + scribe `patch`/`insert`
   ops (Python targets via AST). Next: teach the AGENT to prefer them — the
   pipeline still emits whole files, so `_execute_ai_task` should choose `patch`
   when the target already exists. Other languages need a locator per language
   (tree-sitter is the real answer; register them like `lang/` validators —
   until then non-Python needs explicit `start`/`end` lines, fail-closed).
1b. ~~Monte Carlo verification~~ — **DONE**: `montecarlo.py` + the pipeline's
   `_monte_carlo` step. Generated Python is called with randomised, type-matched
   inputs inside the sandbox; a crash is fed back into self-correction.
   Honest limit: catches crashes and hangs, NOT wrong-but-stable logic.
2. **Diff-review before write** in the plugin — the user must see and approve
   the change before it lands.
3. **Async submit + poll with progress** in the plugin — `agent_build` blocks
   for minutes; an editor needs a background queue, not a frozen UI.
4. **300-line decomposition backlog** — now a ratchet: `decompose_audit.py`
   fails on any NEW file over 300 lines or any baselined file that GROWS.
   21 files of frozen debt (`--debt` lists them), largest first:
   `universal_ai_interface.py` 767, `aivc_controller.py` 736, `agent.py` 730,
   `agent_ai_pipeline.py` 681, `protocol_diagnostic.py` 552,
   `web_search_daemon.py` 538, `build_certify.py` 483, `model_router.py` 456,
   `protocol_enforcer.py` 446, `ops.py` 445, `vox_speech.py` 434,
   `doc_daemon.py` 430, `webhook_server_enhanced.py` 401, `auto_decompose.py` 373.
5. **Plugin i18n** — EN / UK / DE / FR / IT.
5b. **Build a SECOND variant of the plugin with the strongest local model**
   (`qwen3-coder:30b`) from the same specs + `reference_files`, then compare it
   against the 14B variant and keep the better one. Judge on: does it compile,
   cage rejections needed, self-correction attempts, adherence to the design
   reference, and whether `extension.ts` uses only APIs `mcpClient.ts` defines.
   Watch RAM — 30B is heavy; one model at a time.
6. **Local models cannot reliably write complex strict TypeScript.** The cage's
   self-correction (`HDS_SELF_CORRECT`) makes it viable; expect several attempts.

---

## Start a session

```bash
cd HDS_CORE
export PATH="$HOME/.local/bin:$PATH"

python3 -m pytest tests/ -q | tail -1     # expect: 112 passed
python3 write_path_audit.py | tail -1     # expect: Level-3 OK
python3 exec_path_audit.py  | tail -1     # expect: single exec-path sealed
python3 decompose_audit.py  | tail -1     # expect: R-300 OK (--debt to list)

python3 -c 'import sys;sys.path.insert(0,"agent");from sysmon import free_ram_mb;print(free_ram_mb(),"MB free")'
python3 agent/model_scan.py               # what this machine actually serves

pkill -f "agent/agent.py"                 # one instance only
HDS_SILENT=1 python3 agent/agent.py --monitor &   # the daemon drains the queue
```

Build through the agent (never by hand):

```bash
# via MCP (editor path)
python3 mcp_server.py        # tools: agent_build, agent_build_project,
                             # agent_status, agent_models, agent_suggest_models

# via HTTP (server-AI path, key required)
curl -X POST localhost:$PORT/api/v1/external/task \
  -H "Authorization: Bearer $HDS_API_KEY" -H "Content-Type: application/json" \
  -d '{"type":"generate_code","instruction":"…","output_dir":"storage/x",
       "output_filename":"y.py","reference_files":["storage/style_ref.css"]}'
```

Finish every session: stop daemons, unload models, clear test artifacts,
run the three checks above, propagate to deploy, keep deploy at ONE commit.
