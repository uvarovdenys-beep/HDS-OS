# Write-path baseline — why 106 raw writes are safe

**Reviewer question: "raw filesystem writes outside scribe — is that safe?"**
Short answer: yes, and it is *enforced*, not assumed.

## The model

HDS distinguishes two kinds of writes:

| Kind | Who | Path | Gated by |
|------|-----|------|----------|
| **AI-content** | the LLM's proposals | `core/scribe.py` only | path/size/capability/AST gates |
| **System-I/O** | the framework itself | logs, registry, queues, caches, reports | **frozen baseline** (this file) |

The LLM **never** performs a system-I/O write. Those 106 sites are framework
plumbing in trusted modules that the model does not author or control. The
danger is not their existence — it is a *new, unsanctioned* write appearing
(e.g. AI-generated code adding `open(...,'w')`). That is exactly what the
Level-3 guard blocks.

## What the baseline contains

`ai-mind/config/write_path_baseline.json` — 106 sites across 31 framework
modules, frozen by `core/write_path_audit.py --freeze`.

Breakdown by sink:

| Sink | Count | Nature |
|------|------:|--------|
| `mkdir` / `makedirs` | 42 | create dirs for logs/results/registry — not data writes |
| `write_text` | 20 | reports, configs, registry, task results |
| `open(w)` | 19 | logs, JSON dumps, queues |
| `unlink` / `remove` | 14 | cleanup of own temp/queue files |
| `copy` / `copy2` / `move` | 9 | deploy/archive helpers |
| `rmtree` | 1 | archive cleanup |
| `write_bytes` | 1 | binary asset write |

Top modules: `agent.py` (17), `fs.py` (7), `ops.py` (7), `auto_decompose.py`
(6) — all framework infrastructure, none AI-authored.

## How safety is enforced (not trusted)

```bash
python3 core/write_path_audit.py        # CI gate: exit 1 if any NEW site appears
```

- Any write **past scribe** that is not in the baseline → audit fails.
- Wired into `verify_system.sh`, so it runs on every system check.
- To accept a *new* legitimate system-I/O site, a human must run `--freeze`
  (an explicit, reviewable act) — the model cannot expand the surface itself.

## Hardening roadmap (honest)

The baseline *freezes* the surface; it does not yet *shrink* it. The intended
direction is to route the remaining system-I/O through a single `io_guard`
module over time, reducing 106 → a small audited set. Until then, the guarantee
is: **the surface cannot grow without human sign-off**, which is the property
that matters for containing the model.
