# HDS core — the OS manifest

`core/` is a **complete, self-contained AI operating system** for new projects:
everything needed to run autonomous, contained software development. Copy the
folder, run a launcher, point it at a local model. The *creator* repo only
builds this OS — `core/` is the product.

## Layout

```
core/
  # ── kernel (the cage) ──
  scribe.py            executor: path/size/capability/content gates (R-19)
  ast_validator.py     content HYGIENE scan (denylist; not containment)
  write_path_audit.py  Level-3 integrity: single write path
  events.py            event bus (pub/sub) — voice/log/metrics are sinks
  benchmark.py         structural-containment proof (100% / 0% false-positive)
  example.py           hello-cage demo

  agent/               # ── runtime brain + daemons ──
    orchestrator_index, auto_decompose, knowledge_gatekeeper, task_yaml_support
    model_router, cost_router, fallback_model_chain, conductor
    protocol_diagnostic, canary_tests, shadow_verifier, progressive_trust,
    degradation_detector, protocol_enforcer            # trust & verification
    universal_ai_interface, microkernel_ipc, token_wallet, agent
    port_registry, port_checker                        # per-project ports
    webhook_server_enhanced                            # API + dashboard
    vision_daemon, browser_daemon, web_search_daemon, doc_daemon,
    hibernation_daemon, ai_experience                  # autonomous daemons
    vox, vox_events, vox_speech                        # optional voice sink

  scripts/             orchestrator, ai_core, queue_manager, fs, ops, text,
                       gate, search_os, protocol_guard, mem_clear
  gui/                 dashboard (served by the API, relative URLs)
  ai-mind/             runtime data: config, protocols, tasks, deployment
  storage/  tasks/     sandboxes / queues (S-level write targets)
  tests/               OS test suite (live-model tests auto-skip)

  README.md  OS_MANIFEST.md  WRITE_PATHS.md  api.md  LICENSE
```

## What is NOT in the OS (stays in the creator repo)

`SCIENCE/` (experiments), `game/` (separate project), `build/ dist/ backups/
logs/`, and creator tooling (`build_deploy.sh`, `deploy_hds_instance.sh`,
`cleanup_to_archive.sh`, `test_multi_instance.sh`). These build or study the OS;
they are not part of it.

## Ports — per project, never hardcoded

`core/agent/port_registry.py --allocate` generates ports after a system
occupancy check (avoids known apps). API resolves its port from the registry;
the dashboard uses relative URLs, so it always reaches the right port. There is
no default port.

## Boundaries that hold regardless of which model runs

1. **intent** *(containment)* — scribe path/size/capability gates
2. **content** *(hygiene, not containment)* — AST denylist scan (Python; others
   default-denied). Catches naive-dangerous code; bypassable by attribute
   dispatch / runtime IO — see tests/test_cage_adversarial.py.
3. **integrity** *(containment)* — write_path_audit freezes the write surface;
   exec_path_audit freezes the spawn surface (single exec-path → sandbox/)
4. **trust** — diagnostic gates autonomy by *compliance*, not capability

Verified — STRUCTURAL containment (intent/integrity): 100% blocked / 0%
false-positive (`benchmark.py`). CONTENT hygiene is a denylist with documented
limits, NOT a containment guarantee; true isolation of executed code is the
sandbox (process isolation), not the source scan.
