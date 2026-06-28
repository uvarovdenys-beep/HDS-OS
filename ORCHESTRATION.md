# HDS OS — orchestration & usage (local + server AI)

How to drive the OS with a **local** model or a **server** AI, and how the
orchestration flows through the cage. For the HTTP contract see `api.md`; for the
language/validation model see `LANGUAGE_POLICY.md`.

## The one invariant (true in every mode)

No model — local or server, weak or "thinking" — writes files directly. The model
only emits a **task-script** (declarative intent); `scribe` validates it against
the cage rules (R-19 zero-direct-write, R-01 size, R-AST content, capability by
protocol size) and performs the write. The model's reasoning is free; its reach
is bounded.

```
model → task-script (JSON) → scribe.execute(ops, protocol_size) → gated write
```

`protocol_size` (`s/m/l/xl`) comes from the capability+compliance diagnostic:
`s` = sandbox only (no code, no delete) … `xl` = full. A smart-but-disobedient
model is pinned to `s` — physically contained.

**Quick reference — which size for which file type:**

| File type | Min size | Why |
|-----------|----------|-----|
| `.txt`, `.json`, `.csv`, data | `s` | plain data, no code gate |
| `.md`, `.yaml`, `.toml` | `m` | config/docs, not executable |
| `.py`, `.js`, `.ts`, `.php`, `.cpp`, `.cs` | `l` | executable code |
| `.html`, `.htm`, `.svg`, `.svgz` | `l` | markup injection surface (`<script>`, event handlers) |
| delete any file | `xl` | destructive — always requires top grade |

For a **trusted caller** (you, a cloud AI): pass `protocol_size=None` to skip
capability gating entirely — only content hygiene still runs.

## Two planes — read this first (common confusion)

HDS has **two distinct surfaces**. Conflating them is the #1 mistake:

1. **Build cage** — `scripts/orchestrator.py → scribe.py`. A resident **local
   model** (lmstudio/ollama) only *emits a task-script*; `scribe` does the write
   under the rules. This is the only path that writes code. It needs a model.
2. **HTTP daemon** (port from `port_registry`; dashboard + `/api/v1/*`) —
   document/analysis + dashboard + authenticated entry for an external server-AI.
   Its task types are a **fixed list**; there is no generic "build a file" verb
   here. Don't ask this endpoint to write code — that's the build cage's job.

**Gotchas (each one bit a previous agent):**
- **Ports are not constants.** No default port — run `python3 agent/port_registry.py
  --list` / `--allocate`. Never curl memorized port numbers.
- **scribe is root-confined.** It refuses any path outside its project root
  (`R-PATH: escapes project root`); it cannot write a sibling/parent directory.
  When HDS is a *guest* inside a larger project (e.g. site lives in the parent),
  call `scribe.configure(root=PATH_TO_SITE)` before writing — this is the designed
  escape hatch, not a workaround.
- **`protocol_size` is a real barrier.** At `s`, scribe blocks code and delete
  (sandbox only). Writing code needs `l`+, granted by the diagnostic.
  `.html`/`.htm` are now in CODE_EXTS (they contain inline `<script>`) — writing
  HTML also requires `l`+.
- **task-script extractor is fragile with {} in model output.** CSS/HTML/JS in
  a model response can fool a greedy `{.*}` regex. The extractor now uses a
  bracket-scanner instead, but the safest path for code generation is calling
  `scribe.execute(...)` directly — bypasses the extractor entirely.
- **Trusted scheduler? You only need scribe.** protocol_size grading, clear_vram,
  single-model, 180 s timeouts — all that machinery is for an *untrusted* local
  model. When the planner is trusted (e.g. a cloud AI), only R-19 matters:
  `scribe.execute(ops, protocol_size=None)` is sufficient.
- **Writing files directly (not via scribe) bypasses the cage** — that is the
  creator/operator path, not the contained-model path. With no local model the
  build cage is inactive, so direct authoring is the pragmatic (out-of-cage) route.

## Flow: orchestration

```
Conductor → assigns a protocol context to a model
   → model produces a task-script
      → scribe (cage) validates + executes
         → SandboxRunner runs/builds non-Python artifacts (single exec-path)
```

`scripts/orchestrator.py` is the local orchestrator; `agent/conductor.py` assigns
contexts; `agent/model_router.py` / `agent/cost_router.py` pick a provider.

---

## Mode A — LOCAL AI (loopback, no key, single model)

Trusted because it is loopback. Point the orchestrator at a local server:

| Runtime | Port |
|---------|------|
| LM Studio | `:1234` (OpenAI-compatible) |
| Ollama | `:11434` |

**Models are discovered by scanning** these endpoints at runtime — there is **no
hardcoded model list** tied to one machine. Whatever this machine serves is what
the router uses; the cost table is only a hint, unknown models get a default.

```bash
python3 agent/model_scan.py     # list the models THIS machine actually serves
```

```bash
# start the full stack (daemons + agent + API)
bash start_hds.sh
# or with the dashboard GUI on :3000
bash start_hds_with_dashboard.sh
```

The local orchestrator (`scripts/orchestrator.py`) sends prompts to the local
model and feeds the returned task-scripts to scribe. No API key — loopback is
trusted. One model at a time (SINGLE_MODEL).

### Launchers — one entry point

Use the single front door and pick what you want by flag (it replaced the old
`start_hds{,_audio,_silent}` matrix):

```bash
start_hds.sh [--mode daemons|agent|full|dashboard] [--voice on|off] [--monitor|--once]
             # default: --mode full --voice off ;  add --dry-run to preview
```

| `--mode` | Starts |
|----------|--------|
| `daemons` | background daemons only |
| `agent` | the agent loop only |
| `full` *(default)* | daemons (background) + agent |
| `dashboard` | full stack + web GUI `:3000` + API |

`--voice on` = spoken status · `off` = silent. Examples:
`start_hds.sh` (headless full) · `start_hds.sh --mode dashboard` (web UI) ·
`start_hds.sh --mode agent --voice on --monitor`.

The primitives it composes still exist as building blocks
(`start_hds_daemons.sh`, `start_hds_agent[_audio|_silent].sh`,
`start_hds_with_dashboard.sh`); `start_hds_smart.sh` / `hds_dev_start.sh` are
specialized startups. Windows: `.ps1` equivalents.

## Mode B — SERVER AI (OpenAI / Gemini, key required)

Keys live in **environment variables**, never in a committed file
(`ai_providers.json` ships `"${OPENAI_API_KEY}"` — no secret in the repo):

```bash
export OPENAI_API_KEY="sk-..."     # or HDS_OPENAI_KEY
export GEMINI_API_KEY="..."        # or GOOGLE_API_KEY / HDS_GEMINI_KEY
```

A server AI connects **in** through the authenticated API and submits work; the
executor is still the cage:

```bash
# allocate a port (no default port; verified per project)
python3 agent/port_registry.py --allocate
# the webhook API serves on the allocated port; auth with the HDS key:
curl -X POST http://localhost:<PORT>/api/v1/external/task \
  -H "Authorization: Bearer $HDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"op":"write","path":"storage/x.py","content":"x=1"}'
# poll:
curl http://localhost:<PORT>/api/v1/task/<task_id> -H "Authorization: Bearer $HDS_API_KEY"
```

Handshake `GET /api/v1/external/connect` returns the full contract (executor,
rules, submit/poll endpoints). See `api.md`.

---

## Direct (no model) — drive the cage yourself

The cage is usable without any AI; you (or a script) are the orchestrator:

```python
from core import scribe
scribe.execute({"op": "write", "path": "storage/x.py", "content": "x=1"},
               protocol_size="l")    # raises scribe.ScribeError on violation
```

```bash
echo '{"op":"write","path":"storage/x.py","content":"x=1"}' | python3 core/scribe.py - --size l
```

## Languages

Writes are validated per language by real toolchains where installed (Python AST,
JS node, TS tsc, C++ clang++, C# dotnet, PHP `php -l`) and hygiene otherwise. See
`LANGUAGE_POLICY.md`. Non-Python execution/build goes through `sandbox/` (the
single exec-path).

### Toolchain onboarding (auto-offer)

A language whose toolchain is absent is **not silently degraded** — the cage
emits a `toolchain_missing` warning with the exact install command, and you can
check coverage any time:

```bash
python3 -m lang._toolchain      # which toolchains are present + how to install the rest
```

Install commands are no-root where possible (e.g. `tsc` via npm user-prefix,
`dotnet` via dotnet-install.sh, static `php` into ~/.local/bin). Until a tool is
installed, that language falls back to hygiene (never a silent pass).

## Known limits (documented, not fixed)

| # | Limit | Impact | Workaround |
|---|-------|--------|-----------|
| 3 | `scribe.configure()` sets **module-level globals** — not thread-safe | Two projects in one process overwrite each other's ROOT | One process per project (current architecture); fix = Scribe class (future) |
| 4 | `auto_decompose.py` is **Python-only** — JS/HTML/CSS hit R-01 ScribeError at >1000 lines with no auto-split | Frontend files have no size safety net | Keep files under the limit; discipline is the gate, not the OS |
| 8 | `setTimeout`-based UI locking has a **micro-window race** (element visible ~300ms before hide applies) | Edge UX issue in browser | Hide via CSS class at mount, not `style.display` after timeout |
