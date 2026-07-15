# HDS OS — Claude Code Protocol

## ⚡ Identity (read this first)
**HDS OS** = independent operating system for creating software products.
NOT a document processor. NOT a thesis tool. An OS for developers.

- Location: `this repo (run from its root)`
- Orchestrator-based: Conductor assigns protocol contexts to local AI
- Local AI: **Qwen Coder :11434** for all programming tasks
- Dashboard: `bash start_hds_with_dashboard.sh` → port :3000

## Rule Zero: Scripts First, Always
```bash
ls scripts/ *.sh                  # check before writing ANY code
bash verify_system.sh             # health check
bash start_hds.sh           # start full stack
bash deploy_hds_instance.sh      # deploy instance
bash build_deploy.sh              # build + deploy
```
First failure → diagnose root cause. Never retry same command twice.

## Rule One: Local AI for ALL Code
```bash
# Qwen Coder for programming (Ollama):
curl http://127.0.0.1:11434/api/generate -d '{
  "model":"qwen3-coder:30b",
  "prompt":"<task>",
  "stream":false
}'

# LM Studio for architecture/planning:
curl http://127.0.0.1:1234/v1/chat/completions -d '{
  "model":"qwen/qwen3.6-35b-a3b",
  "messages":[{"role":"user","content":"<task>"}]
}'
```
Cloud AI (this session) = audit/review only. Local AI does the work.

## Architecture

### Core Services
| Port | Service | Role |
|------|---------|------|
| 9001 | Vision Daemon | screen capture + understanding |
| 9002 | Browser Daemon | web automation |
| 8080 | Webhook API | external task entry |
| 3000 | GUI Dashboard | control panel (React/Vite) |
| 1234 | LM Studio | qwen3.6-35b, gemma-4-26b |
| 11434 | Ollama | **qwen3-coder:30b** + other models |

### Scripts (run these, don't rewrite them)
```
start_hds.sh          ← full stack
start_hds_with_dashboard.sh ← + GUI :3000
start_hds_daemons.sh       ← daemons only
deploy_hds_instance.sh     ← deploy to Desktop
build_deploy.sh             ← build + deploy
verify_system.sh            ← health check
```

### Key Directories
```
agent/          ← orchestrator, conductor, protocol enforcer
scripts/        ← Python helpers (ai_core, gate, ops, text, fs...)
ai-mind/        ← orchestrator_index.json, tasks/, memory/
gui/            ← React dashboard (port :3000)
build_config.yaml ← build rules
```

## Orchestrator Index
```bash
# Get module summary BEFORE reading any file:
python3 -c "import json; idx=json.load(open('ai-mind/orchestrator_index.json')); print(idx.get('modules',{}).get('MODULE_NAME',{}))"
```

## Local LLMs — DISCOVERED, not listed
Models are scanned at runtime from the local endpoints — never hardcoded to one
machine. List what THIS machine actually serves:
```bash
python3 agent/model_scan.py          # ollama :11434 + lmstudio :1234
```
- CostRouter consumes the scan; the cost table is only a hint (unknown models
  get a neutral default — portable to any machine).
- Free RAM: `bash scripts/llm_memory.sh unload` or via resource daemon :9099
- **1 model loaded at a time** — CostRouter selects next model, never parallel

## AI Failure Patterns (critical, verified in this project)

| Pattern | Symptom | Fix |
|---------|---------|-----|
| Completionism | Does extra unrequested work | Do EXACTLY what was asked, stop |
| Retry Loop | Same fail → retry with tweaks | First fail = diagnose, switch approach |
| Build Instead of Find | Creates script that already exists | `ls scripts/ *.sh` first |
| Verbose Output | Full dump → reads it → wasted tokens | `\| tail -3` always |
| Verify-Can't-Fail | Re-reads file after write | If function raises on error, no re-read needed |
| Narration | "Let me now proceed to..." | Act. Show result. Stop. |
| Agent Abuse | Spawns agent for simple task | Agent = search/research ONLY |

## Protocol Sizes
- S (Helper): max 50 lines, 3 rules
- M (Executor): max 200 lines, 5 rules
- L (Engineer): max 500 lines, 8 rules
- XL (Architect): max 1000 lines, full autonomy

## Code Rules
- All code/comments/vars: **English only**
- Ukrainian: user-facing strings only
- Output always piped: `| tail -5` or `| grep PATTERN`
- No full file reads for navigation — use `grep -n`
