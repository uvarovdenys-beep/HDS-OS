# Changelog

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
