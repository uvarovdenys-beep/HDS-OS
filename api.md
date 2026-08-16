# HDS Agent API

HTTP API served by `agent/webhook_server_enhanced.py`. Serves the GUI dashboard
and the task API.

## Port — per project, NOT a fixed default

**There is no default port.** Ports are allocated per project/instance by
`agent/port_registry.py`, which **verifies system occupancy** (via
`port_checker.py`) and **avoids standard ports of known programs** before
assigning. The server resolves its port as:

1. `$WEBHOOK_PORT` (set by the launcher / deploy script), else
2. the `webhook_port` of the latest allocated instance in the port registry.

If nothing is allocated the server **refuses to start** rather than grabbing a
standard port. Allocate first:

```bash
python3 agent/port_registry.py --allocate          # generates verified ports
python3 agent/port_registry.py --list              # shows this project's ports
```

The base pattern (instance 0 → 8080, instance 1 → 8090, …) is only a starting
point for the availability scan — the actual port is whatever passed the check.
In every example below, substitute **your project's allocated port** for
`<PORT>`; do not assume 8080.

## Two AI connection modes

The GUI agent works with AI in two directions:

| Mode | Direction | Who | Auth |
|------|-----------|-----|------|
| **Local** | agent → model | local orchestrator + models (`lmstudio`, `ollama`) via `scripts/orchestrator.py` | none (loopback, SINGLE MODEL) |
| **Server** | server AI → agent | an **external server AI** connects in through an **external agent** | **API key required** |

Local orchestrators/models are trusted (loopback) and need no key. The
**external (server-side) AI** path is the only authenticated surface.

## Authentication (external AI only)

The key is resolved as: `$HDS_API_KEY` → `ai-mind/config/api_key` (auto-generated
on first start if absent). Present it as either header:

```
Authorization: Bearer <key>
X-API-Key: <key>
```

Set your own key:

```bash
export HDS_API_KEY="my-secret-key"
# or write it to:
echo "my-secret-key" > ai-mind/config/api_key
```

## Server-AI provider keys (OpenAI / Gemini) — env only, never in the file

The agent can call out to **server AIs**. Their keys live in environment
variables, NOT in `ai-mind/config/ai_providers.json` (which is committed and would
leak into the deploy repo). The provider's `api_key` field uses `${ENV}`
interpolation, resolved at startup:

```bash
export OPENAI_API_KEY="sk-..."     # or HDS_OPENAI_KEY
export GEMINI_API_KEY="..."        # or HDS_GEMINI_KEY / GOOGLE_API_KEY
```

`ai_providers.json` ships with `"api_key": "${OPENAI_API_KEY}"` — no secret in
the repo. A raw key pasted into that file still works but is **discouraged** (it
is not gitignored). Local orchestrators (lmstudio/ollama) are loopback and need
no key.

## Endpoints

### External server AI (API-key protected)

#### `GET /api/v1/external/connect` — handshake
The single advertised entry point for a server AI. Returns the HDS contract:
executor rules, local-orchestrator info, and where to submit work.

```bash
curl http://localhost:<PORT>/api/v1/external/connect \
  -H "Authorization: Bearer $HDS_API_KEY"
```
```json
{
  "service": "HDS", "status": "connected", "role": "external-server-ai",
  "contract": { "submit": "POST /api/v1/external/task",
                "poll": "GET /api/v1/task/{task_id}",
                "auth": "Authorization: Bearer <key>  (or  X-API-Key: <key>)" },
  "executor": { "engine": "agent/scribe.py",
                "rules": ["R-19 zero-direct-write", "R-13 script-first", "R-01 size-limit"] },
  "local_orchestrator": { "script": "scripts/orchestrator.py",
                          "single_model": true, "servers": ["lmstudio", "ollama"] }
}
```

#### `POST /api/v1/external/task` — submit work as a server AI
Same body as `/api/v1/task`, but authenticated and tagged `"source":
"external-server-ai"`. Returns `{task_id, status}`; poll the result below.

```bash
curl -X POST http://localhost:<PORT>/api/v1/external/task \
  -H "Authorization: Bearer $HDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": {"type": "aivc", "goal": "...", "server": "ollama", "model": "qwen3.5:4b"}}'
```

### Open endpoints (GUI / loopback)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Dashboard HTML |
| GET | `/api/v1/agents` | List agents |
| GET | `/api/v1/stats` | Stats |
| GET | `/api/v1/tasks` | Recent tasks |
| POST | `/api/v1/task` | Submit task (local/GUI) |
| GET | `/api/v1/task/{task_id}` | Task status/result |
| POST | `/api/v1/agent/start` | Start an agent instance |
| POST | `/api/v1/agent/{instance_id}/stop` | Stop an agent instance |
| GET | `/health` | Health check |

## Connection flow: external server AI → HDS

```
server AI ──(external agent)──► GET  /api/v1/external/connect   (Bearer key)
                                  ◄── contract + capabilities
          ──────────────────────► POST /api/v1/external/task    (Bearer key)
                                  ◄── { task_id }
          ──────────────────────► GET  /api/v1/task/{task_id}    (poll)
                                  ◄── { status, result }
```

The server AI **plans**; the local executor (`scribe.py`) **writes** under
R-19/R-13/R-01. SINGLE MODEL still holds locally: only one local model is ever
resident, regardless of how many external agents are connected.

## Security notes

- CORS is currently `allow_origins=["*"]` for the dashboard. The external
  endpoints are still protected by the API key, but tighten CORS before exposing
  the port beyond localhost.
- The auto-generated key lives in `ai-mind/config/api_key` — do not commit it.
- Use `secrets.compare_digest` (already used server-side) — never log the full key.
