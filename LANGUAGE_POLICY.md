# Language policy — HDS OS

> Status: **PLAN**. Source of truth = `HDS_CORE`; propagate core → deploy.
> This is the single home for language support. There is **no separate `web/`** —
> web languages are just modules under `lang/`. (`WEB_MODULE.md` is superseded.)

## Decision: lang/js · lang/php · lang/html are INTERIM bootstrap hygiene

Under the target model (one caged Python agent orchestrating mature toolchains in
a sandbox), these regex validators are strictly weaker than eslint / php-cs-fixer
and would be dead weight. They are kept **only** because they are currently the
sole thing letting scribe author `.js`/`.php` at all — without a validator the
extension is default-DENIED. So:

- **Keep** them as interim hygiene; do **not** delete until the sandboxed
  toolchain path (eslint/php-cs-fixer via SandboxRunner) exists.
- **Do not add** more language validators. New languages are handled by the
  sandbox + their real toolchain, not by hand-written regex here.
- When the sandbox path lands, replace each `lang/<x>/validator.py` with a thin
  "run <tool> in sandbox" adapter and drop the regex.

## The one rule everything obeys (fail-closed)

A language is "supported" **only** when a validator module for it exists in
`lang/`. Capability is granted **by code, never by a data file**.
`scribe._content_validator` treats any exec/compiled extension without a
resolvable validator as **default-DENY**. This holds `benchmark.py` at
100% blocked / 0% false-positive no matter what config says.

| | Can ENABLE a language? | Can DISABLE? |
|---|---|---|
| `lang/<x>/validator.py` (code) | ✅ yes — the only way | — |
| `capabilities.json` (data) | ⛔ **never** | ✅ yes |

Config is **subtract-only**: it can strip an existing capability or tighten the
cage, never add one. "Enable the unknown" → ignored, fail-closed.

## One home, one module per language — discovery, not declaration

```
lang/
  python/  validator.py  meta.py  tests/   (ast_validator moves here)
  js/      validator.py  meta.py  tests/   (covers .js .ts .jsx .tsx)
  php/     validator.py  meta.py  tests/
  html/    validator.py  meta.py  tests/   (guard: scans embedded <script>/on*=)
  css/     meta.py        tests/           (kind=data — inert, whitelist, no validator)
  cpp/     validator.py  meta.py  tests/   (.cpp .cc .h .hpp)
  cs/      validator.py  meta.py  tests/
```

- Each `validator.py` **self-registers**: `@register(".cpp", ".hpp", kind="compiled")`.
- `scribe` builds `CODE_EXTS` + the dispatcher **from registered modules**, not
  from a file. Dropping in a `lang/<x>/` is what makes a language writable.
- Every validator shares the `ast_validator.py` contract:
  `(worst_level, violations)` over `SAFE/WARNING/DANGER/CRITICAL`; scribe rejects
  `>= DANGER`. Parsing for non-Python langs = `tree-sitter` (pure pip; no
  node/php/compiler needed to *parse*).

## `kind` semantics

- `exec` — interpreted/runtime (python, js/ts, php): write-gate = validator.
- `markup` — passive but injection-prone (html): guard scans embedded JS.
- `data` — inert (css): whitelist, no content gate.
- `compiled` — **two risk moments**, see below (cpp, cs).

## Compiled languages — the extra surface (C++ / C#)

The source-scan handles *writing* the source, but **not** building/running the
binary. A clean `.cpp` can still `system()`/inline-`asm`; a `.cs` can
`Process.Start`/`DllImport`/`Assembly.Load`.

- `lang/cpp/validator.py` — CRITICAL: `system`/`exec*`/`popen`/`fork`, inline
  `asm`, `dlopen`/`LoadLibrary`, fn-ptr casts. DANGER: process calls + stdlib,
  abs-path `ofstream`, non-literal `#include`. WARNING: `goto`, `while(true)`.
- `lang/cs/validator.py` — CRITICAL: `Process.Start`, `DllImport`, `Assembly.Load*`/
  `Activator.CreateInstance(string)`, `unsafe`/`stackalloc`, `Marshal.*`.
  DANGER: `Reflection.Emit`, abs-path `File.*`, Roslyn compile-at-runtime.
  WARNING: `dynamic`, `goto`, `while(true)`.

**Build boundary:** compilation does NOT belong to scribe. Until a **sandboxed
builder daemon** exists in `agent/` (no network, scratch dir, dropped privs),
the OS may **write & scan** C++/C# but **must not compile/run** them. Global
guard `compiled_build:false` in `capabilities.json` enforces this.

## Subtract-only config

`ai-mind/config/capabilities.json`:

```json
{ "disabled": [".php"], "compiled_build": false }
```

## Master matrix (ACTUAL state)

Validation tiers: **toolchain** = real parser via SandboxRunner (best);
**hygiene** = regex denylist (interim, weaker than a toolchain); **data** = inert.

| Lang | Ext | kind | Validation | State |
|------|-----|------|-----------|-------|
| Python | `.py` | exec | AST (full) | ✅ done |
| JS | `.js` | exec | **runtime-aware**: browser-hygiene (DOM/XSS) vs node-hygiene (`child_process`), by context; `node --check` as ES-syntax parser only | ✅ toolchain-validated |
| TS | `.ts .tsx` | exec | **tsc `--noEmit`** + hygiene | ✅ toolchain-validated |
| JSX | `.jsx` | exec | hygiene | 🟡 hygiene (JS-flavoured, no plain parser) |
| PHP | `.php` | exec | **`php -l`** + hygiene | ✅ toolchain-validated |
| HTML | `.html` | markup | embedded-script / XSS hygiene | ✅ correct level — HTML has no syntax-error concept (tidy is a corrector, never errors); injection hygiene is the meaningful gate |
| CSS | `.css` | data | none (inert) | 🟡 writable as data (lint optional via stylelint) |
| C++ | `.cpp .cc .hpp` | compiled | **clang++ `-fsyntax-only`** + hygiene | ✅ toolchain-validated (build still gated) |
| C# | `.cs` | compiled | **dotnet build** (Roslyn) + hygiene | ✅ toolchain-validated (build still gated) |
| Go / Rust / … | — | compiled | — | ⛔ not enabled |

**A language is "finished" by wiring its real toolchain here, not by more regex.**
Python/JS/TS/C++/C# are done (node, tsc, clang++, dotnet installed). Only **PHP**
stays interim hygiene — no `php` toolchain installed and no clean no-root install
path. The validator auto-falls back to hygiene when a tool is absent (never a
silent pass). `.cs .cc .hpp` were added to `scribe.CODE_EXTS` so they are gated.

## Build order

1. `lang/` registry + self-registration; `scribe.configure()` reads from it, not
   from a data file. Move `ast_validator` → `lang/python/`.
2. `lang/js/` validator + tests (containment 100%/0%).
3. `lang/php/` validator + tests.
4. `lang/html/` guard, `lang/css/` whitelist.
5. `lang/cpp/` + `lang/cs/` validators (source-scan only) + tests.
6. Sandboxed builder daemon in `agent/` (gates compile+run for compiled langs).
7. `verify_system.sh` checks registry ⇔ validators; update `OS_MANIFEST.md`;
   propagate core → deploy.
