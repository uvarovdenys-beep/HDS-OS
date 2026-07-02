# HDS OS — What Is Actually Implemented

This is a statement of what exists and works now, not a roadmap. Items that are
planned but not yet built are not listed here.

## Cage core (`scribe.py`)

- **R-19 Zero-direct-write** — only scribe writes files; any other path bypasses the cage (documented in ORCHESTRATION.md, not a bug)
- **R-01 size limit** — 1000-line hard ceiling per file
- **R-PATH** — path-escape detection; refuses writes outside `ROOT`
- **R-KERNEL** — cage files (`scribe.py`, `ast_validator.py`, `write_path_audit.py`, `events.py`) are write-protected at all capability levels
- **R-CAP / protocol_size** — `s/m/l/xl` capability ladder; `s` = sandbox-only, `l` = code+markup, `xl` = +delete; `None` = trusted caller (skips cap gate, still runs content gate)
- **R-SEAL** — `scribe.seal()` freezes the cage geometry (root, sandbox, code dirs) for the process; the orchestrator seals before the untrusted-model loop starts, so no code reached from a task can re-root the cage via `configure()`
- **R-AST** — per-language content validation via `lang/` registry; fail-closed on missing validator

## Language validators (`lang/`)

All validators self-register via `@register`; scribe reads from registry — no
hardcoded extension list in the cage.

| Language | File | Validation |
|----------|------|------------|
| Python | `lang/python/validator.py` | AST scan — blocks `eval/exec/subprocess/__import__/compile` |
| JavaScript / TypeScript | `lang/js/validator.py` | `node --check` (syntax) + `tsc` (types); browser vs Node detection |
| HTML / HTM | `lang/html/validator.py` | Parser-based (`lang/_markup.py`): entities decoded before inspection; blocks event handlers, `javascript:`/`data:text/html` URIs, `eval`/`Function`/`import()` in scripts |
| SVG / SVGZ | `lang/svg/validator.py` | Same parser + SVG-specific: `<foreignObject>`, SMIL event retargeting (`<set attributeName="on…">`) |
| PHP | `lang/php/validator.py` | `php -l` syntax check |
| C++ | `lang/cpp/validator.py` | `clang++ -fsyntax-only` |
| C# | `lang/cs/validator.py` | `dotnet build` with temp `.csproj` |

A language in `CODE_EXTS` without a validator → write is **default-denied** (not silently allowed).

Toolchain auto-offer: if a toolchain is absent, scribe emits `toolchain_missing`
event with the exact install command. Run `python3 -m lang._toolchain` for status.

## Execution sandbox (`sandbox/`)

- **SandboxRunner** — single exec-path for running/building non-Python artifacts
- **DockerBackend** — isolated=True; `--network none --read-only --cap-drop ALL --pids-limit --security-opt no-new-privileges`
- **SubprocessBackend** — degraded fallback; isolated=False; no `shell=True`; CPU rlimit

`docker_backend.py` is the only file in the OS that may use `subprocess` — enforced by `exec_path_audit.py`.

## Agent runtime

- **`agent/model_scan.py`** — discovers models from ollama `:11434` and LM Studio `:1234` at runtime; no hardcoded model names
- **`agent/cost_router.py`** — routes by cost/capability; unknown models get a default cost
- **`agent/conductor.py`** — assigns protocol contexts to models
- **`agent/universal_ai_interface.py`** — ENV-based key resolution (`${OPENAI_API_KEY}`); ships no secrets
- **`agent/port_registry.py`** — dynamic port allocation; no default port; records to `ai-mind/deployment/port_registry.json`
- **`agent/webhook_server_enhanced.py`** — FastAPI HTTP daemon; authenticated entry for server AI; started automatically by `start_hds_daemons.sh`

## Orchestration

- **`scripts/orchestrator.py`** — local AI loop; bracket-scanner task-script extractor (replaces greedy regex); single-model (clear_vram before scribe runs)
- **`agent/task_yaml_support.py`** — YAML task definitions; shell actions routed through SandboxRunner (no `shell=True`)
- **`events.py`** — synchronous pub/sub event bus; failing sink is isolated (never breaks producer)

## Launchers

| Script | Does |
|--------|------|
| `start_hds.sh` | Single front door; `--mode daemons\|agent\|full\|dashboard`, `--voice on\|off` |
| `start_hds_daemons.sh` | Vision + Browser + Webhook daemons (dynamic ports) |
| `start_hds_with_dashboard.sh` | Full stack + web GUI `:3000` |
| `start_hds_smart.sh` | Smart startup with real port-alloc logic |

## Audit / invariant enforcement

- **`write_path_audit.py`** — Level-3 invariant: all write paths go through scribe
- **`exec_path_audit.py`** — Level-3 invariant: `subprocess` allowed only in `docker_backend.py` (with documented justification)

## Tests

- `tests/test_cage_adversarial.py` — 13 MUST_BLOCK + 2 KNOWN_LIMIT cases
- `tests/test_live_cage.py` — OPT-IN (`HDS_LIVE_TESTS=1`); timeout=30 s; needs running local model
- `tests/test_lang_toolchain.py` — per-language toolchain presence + auto-offer
- `tests/test_model_scan.py` — no hardcoded model names assertion

## What is NOT implemented (by design)

- Auto-decompose for JS/HTML/CSS (Python-only; see Known Limits #4 in ORCHESTRATION.md)
- Thread-safe multi-project scribe (requires Scribe class; currently module globals; see Known Limit #3)
- Docker auto-install (SandboxRunner degrades to subprocess if Docker absent, not an error)
