# HDS OS — the AI-containment cage

**Turn any LLM — local or server, weak or "thinking" — into a bounded, verified
executor.** Reliability lives in the system *around* the model, not in the model.
The model proposes; deterministic code disposes.

> **v1.1.0** · 79 tests passing · write-path & exec-path sealed · 6 languages
> toolchain-validated · local + server AI orchestration

```
model → task-script (JSON) → scribe (the cage) → validated, gated write
                                   └→ sandbox/ (single exec-path) for run/build
```

## Why

Most agent projects collapse because they *trust the model* — they ask it nicely
("please follow the rules") and hope. A capable model reasons *around* the rules.
HDS removes the option to disobey: the only verb a model has is "propose a
task-script"; everything else is read-only, and every proposal passes
deterministic gates. It works the same whether the author is a tiny local model
or a frontier server AI — **its value is trust in autonomous output, not human
typing speed.**

## What it gives you

- **Capability gate by compliance, not capability.** A smart-but-disobedient
  model is pinned to `s` — it can reason freely but can only drop files in the
  sandbox; never code, never delete. (`s` → `xl`.)
- **Per-language validation by real toolchains.** Writes are checked by the
  language's own compiler/linter before they land — not by regex guesswork.
- **Two sealed Level-3 surfaces.** `write_path_audit` freezes the single *write*
  path; `exec_path_audit` freezes the single *exec* path (all process spawning
  confined to `sandbox/`).
- **Honest guarantees.** *Structural containment* (path/size/capability/integrity)
  is real and proven; *content hygiene* (the denylist scan) is documented as
  hygiene, not a security boundary — true isolation of executed code is the
  sandbox, not source scanning.
- **Local + server AI orchestration**, with provider keys via env (never in the
  repo). See **[ORCHESTRATION.md](ORCHESTRATION.md)**.

## Languages

A code extension with no registered validator is **default-denied** — the cage
never leaks silently. Validation uses the real toolchain where installed, else
interim hygiene (and it tells you how to install the rest:
`python3 -m lang._toolchain`).

| Language | Validation |
|----------|-----------|
| Python | AST (full) |
| JS | runtime-aware hygiene (browser vs node) + `node --check` syntax |
| TS | `tsc --noEmit` |
| C++ | `clang++ -fsyntax-only` |
| C# | `dotnet build` (Roslyn) |
| PHP | `php -l` |
| HTML / CSS | injection-hygiene / inert data |

Compiled languages are validated but **build/run stays gated** until a sandboxed
builder runs them. See **[LANGUAGE_POLICY.md](LANGUAGE_POLICY.md)**.

## Quickstart

Drive the cage directly (you are the orchestrator — no model needed):

```python
from core import scribe
scribe.execute({"op": "write", "path": "storage/x.py", "content": "x=1"},
               protocol_size="l")     # raises scribe.ScribeError on violation
```

```bash
echo '{"op":"write","path":"storage/x.py","content":"x=1"}' | python3 core/scribe.py - --size l
python3 core/write_path_audit.py      # CI gate: exit 1 on any new raw write
python3 core/exec_path_audit.py       # CI gate: subprocess confined to sandbox/
```

To run it with a **local** model (lmstudio/ollama) or a **server** AI
(OpenAI/Gemini), and for the orchestration flow and HTTP API, see
**[ORCHESTRATION.md](ORCHESTRATION.md)** and `api.md`.

## Layout

```
scribe.py            the cage — validates a task-script and writes
ast_validator.py     Python content hygiene (denylist)
write_path_audit.py  Level-3: single write surface, frozen
exec_path_audit.py   Level-3: single exec surface, frozen
benchmark.py         structural-containment proof (100% / 0% false-positive)
lang/<x>/            per-language validator + meta (capability granted by code)
sandbox/             the single exec-path (Docker isolation / degraded fallback)
agent/  scripts/     orchestrator, conductor, daemons, model routers, API
product/guestbook/   worked multi-file example, built through the cage
```

## Honest scope (what this is NOT)

- It does **not write code for you** — it gates and verifies an author's output.
  For a human in an IDE it is overhead; for an **untrusted agent** it is the thing
  that makes that safe.
- Execution isolation is **degraded** without a container runtime: the fallback
  backend (`isolated=False`) gives no-shell + limits, not true isolation. Install
  Docker/Podman and the hardened container backend engages with no code change.
- The Python content scan is **hygiene**, not containment — see
  `tests/test_cage_adversarial.py` for its documented limits.

## Authors & License

**Authors / Автори:** Денис Уваров · Микита Александров · Валентина Галушко
**Rights holder / Власник:** ГС «Українська асоціація інноваційних технологій»

**License: NON-COMMERCIAL use only** — free to use, modify and share for
non-commercial purposes; commercial use requires written permission from the
rights holder. See [`LICENSE`](LICENSE).
**Ліцензія: лише некомерційне використання** — комерційне застосування
заборонене без письмового дозволу власника.
