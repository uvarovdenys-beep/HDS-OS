#!/usr/bin/env python3
"""
HDS Webhook Server with Dashboard API
Serves both HTTP webhook tasks and control dashboard
"""

import os
import json
import time
import secrets
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="HDS Webhook API")

# Enable CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data paths
PORT_REGISTRY_FILE = Path("ai-mind/deployment/port_registry.json")
TASKS_DIR = Path("ai-mind/tasks")
RESULTS_DIR = TASKS_DIR / "results"
API_KEY_FILE = Path("ai-mind/config/api_key")


# ============================================================================
# AUTH — external (server-side) AI connects through an API key
# ============================================================================

def get_api_key() -> str:
    """Resolve the inbound API key.

    Precedence: env HDS_API_KEY > ai-mind/config/api_key file. If neither
    exists a key is generated and persisted, so the server is never silently
    unauthenticated. Local orchestrators/models bypass this — auth only gates
    the external (server AI) entry points.
    """
    env_key = os.environ.get("HDS_API_KEY")
    if env_key:
        return env_key.strip()
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()
    key = secrets.token_urlsafe(32)
    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    API_KEY_FILE.write_text(key)
    return key


def verify_api_key(authorization: str = Header(None),
                   x_api_key: str = Header(None)) -> str:
    """FastAPI dependency: accept 'Authorization: Bearer <key>' or 'X-API-Key'."""
    presented = x_api_key
    if not presented and authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    if not presented or not secrets.compare_digest(presented, get_api_key()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return presented


def load_port_registry() -> Dict:
    """Load port registry"""
    if PORT_REGISTRY_FILE.exists():
        try:
            return json.loads(PORT_REGISTRY_FILE.read_text())
        except:
            return {}
    return {}


def load_tasks() -> List[Dict]:
    """Load recent tasks"""
    tasks = []
    if RESULTS_DIR.exists():
        for task_file in sorted(RESULTS_DIR.glob("*.json"), reverse=True)[:10]:
            try:
                task = json.loads(task_file.read_text())
                tasks.append(task)
            except:
                pass
    return tasks


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@app.get("/")
async def serve_dashboard():
    """Serve dashboard HTML"""
    dashboard_path = Path("gui/dashboard/index.html")
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    return {"error": "Dashboard not found"}


@app.get("/api/v1/agents")
async def get_agents():
    """Get list of active agents"""
    registry = load_port_registry()
    agents = []
    
    for instance_id, config in registry.items():
        agent = {
            "instance_id": instance_id,
            "name": config.get("deploying_ai", "Unknown"),
            "status": "online" if is_agent_alive(config) else "offline",
            "vision_port": config.get("vision_daemon_port"),
            "browser_port": config.get("browser_daemon_port"),
            "webhook_port": config.get("webhook_port"),
            "memory": 256,  # Placeholder
            "task_count": 0,  # Placeholder
            "uptime": int(time.time() - config.get("created_at", time.time()))
        }
        agents.append(agent)
    
    return agents


@app.get("/api/v1/stats")
async def get_stats():
    """Get system statistics"""
    registry = load_port_registry()
    tasks = load_tasks()
    
    return {
        "agents": len(registry),
        "tasks": len(tasks),
        "daemons": len(registry) * 3,  # vision, browser, webhook per agent
        "memory": len(registry) * 256,  # Approximate
        "uptime": 0
    }


@app.get("/api/v1/tasks")
async def get_tasks(limit: int = 10):
    """Get recent tasks"""
    tasks = load_tasks()
    return tasks[:limit]


@app.post("/api/v1/agent/start")
async def start_agent(request: dict):
    """Start new agent"""
    ai_name = request.get("ai_name", "Agent")
    mode = request.get("mode", "monitor")
    auto_kill = request.get("auto_kill", False)
    audio = request.get("audio", False)
    
    # In real implementation, would spawn agent process
    return {
        "status": "started",
        "ai_name": ai_name,
        "mode": mode,
        "message": f"Agent '{ai_name}' started in {mode} mode"
    }


@app.post("/api/v1/agent/{instance_id}/stop")
async def stop_agent(instance_id: str):
    """Stop agent"""
    # In real implementation, would kill agent process
    return {
        "status": "stopped",
        "instance_id": instance_id,
        "message": f"Agent '{instance_id}' stopped"
    }


# ============================================================================
# WEBHOOK TASK ENDPOINTS
# ============================================================================

@app.post("/api/v1/task")
async def submit_task(task_data: dict):
    """Submit task via webhook. AIVC tasks are executed asynchronously."""
    task_id = task_data.get("task_id", f"TASK-{int(time.time()*1000)}")

    task_result = {
        "task_id": task_id,
        "status": "queued",
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "data": task_data
    }

    # Save task
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_file = RESULTS_DIR / f"{task_id}.json"
    result_file.write_text(json.dumps(task_result, indent=2))

    # If AIVC task — launch async execution
    inner_task = task_data.get("task", {})
    if inner_task.get("type") == "aivc":
        import threading
        threading.Thread(
            target=_execute_aivc_task,
            args=(task_id, inner_task),
            daemon=True
        ).start()

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Task received and queued"
    }


def _execute_aivc_task(task_id: str, task: dict):
    """Execute AIVC task in background thread."""
    try:
        from aivc_controller import AIVCController, make_lmstudio_caller, make_ollama_caller

        goal = task.get("goal", "")
        context = task.get("context", "")
        max_steps = task.get("max_steps", 10)
        server = task.get("server", "lmstudio")
        model = task.get("model", "")

        # Build AI caller
        if server == "ollama":
            ai_fn = make_ollama_caller(model=model or "qwen2.5:7b")
        else:
            ai_fn = make_lmstudio_caller(model=model)

        # Update status to running
        result_file = RESULTS_DIR / f"{task_id}.json"
        task_state = json.loads(result_file.read_text())
        task_state["status"] = "running"
        result_file.write_text(json.dumps(task_state, indent=2))

        # Execute AIVC loop
        ctrl = AIVCController(ai_call_fn=ai_fn, max_steps=max_steps)
        result = ctrl.execute_goal(goal, context)

        # Update status
        task_state["status"] = "completed" if result["success"] else "error"
        task_state["result"] = result
        task_state["completed_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
        result_file.write_text(json.dumps(task_state, indent=2, ensure_ascii=False))

    except Exception as e:
        try:
            result_file = RESULTS_DIR / f"{task_id}.json"
            task_state = json.loads(result_file.read_text())
            task_state["status"] = "error"
            task_state["error"] = str(e)
            result_file.write_text(json.dumps(task_state, indent=2))
        except:
            pass


@app.get("/api/v1/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    task_file = RESULTS_DIR / f"{task_id}.json"
    if task_file.exists():
        return json.loads(task_file.read_text())
    raise HTTPException(status_code=404, detail="Task not found")


# ============================================================================
# EXTERNAL AI ENDPOINTS — a server-side AI connects here via an external agent
# ============================================================================

@app.get("/api/v1/external/connect")
async def external_connect(_: str = Depends(verify_api_key)):
    """Handshake for an external server AI agent.

    The external agent authenticates with the API key and receives the HDS
    contract: which local executor/orchestrator is reachable and how to submit
    work. This is the single advertised entry point for server-side AI.
    """
    return {
        "service": "HDS",
        "status": "connected",
        "role": "external-server-ai",
        "contract": {
            "submit": "POST /api/v1/external/task",
            "poll": "GET /api/v1/task/{task_id}",
            "auth": "Authorization: Bearer <key>  (or  X-API-Key: <key>)",
        },
        "executor": {
            "engine": "agent/scribe.py",
            "rules": ["R-19 zero-direct-write", "R-13 script-first", "R-01 size-limit"],
        },
        "local_orchestrator": {
            "script": "scripts/orchestrator.py",
            "single_model": True,
            "servers": ["lmstudio", "ollama"],
        },
        "agents": len(load_port_registry()),
    }


@app.post("/api/v1/external/task")
async def external_task(task_data: dict, _: str = Depends(verify_api_key)):
    """Submit a task as an external server AI (API-key protected).

    Same task contract as /api/v1/task, but authenticated and tagged so the
    GUI can distinguish server-AI-driven work from local-orchestrator work.
    """
    task_data.setdefault("source", "external-server-ai")
    return await submit_task(task_data)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "HDS Webhook Server",
        "uptime": int(time.time()),
        "agents": len(load_port_registry())
    }


# ============================================================================
# UTILITIES
# ============================================================================

def is_agent_alive(config: Dict) -> bool:
    """Check if agent process is alive"""
    # Simplified - in real implementation would check PID or health endpoint
    created_at = config.get("created_at", 0)
    age = time.time() - created_at
    return age < 86400  # Assume alive if less than 24h old


def resolve_webhook_port() -> int:
    """Resolve this project's webhook port — NEVER a hardcoded default.

    Ports are per-project and system-verified. Precedence:
      1. $WEBHOOK_PORT (set by the launcher / deploy script)
      2. the webhook_port of the latest allocated instance in port_registry
    If neither exists the registry has not been initialised — fail loud rather
    than silently grabbing a 'standard' port that may belong to another app.
    """
    env_port = os.environ.get("WEBHOOK_PORT")
    if env_port:
        return int(env_port)

    registry = load_port_registry()
    if registry:
        latest = max(registry.values(), key=lambda c: c.get("created_at", 0))
        port = latest.get("webhook_port")
        if port:
            return int(port)

    raise SystemExit(
        "❌ No webhook port allocated. Run: "
        "python3 agent/port_registry.py --allocate  (ports are per-project, "
        "generated after a system occupancy check — there is no default port)."
    )


def main():
    """Start webhook server"""
    port = resolve_webhook_port()

    print("\n" + "="*70)
    print("HDS Webhook Server + Dashboard")
    print("="*70)
    print(f"\n🌐 Dashboard:   http://localhost:{port}")
    print(f"📡 Webhook API: http://localhost:{port}/api/v1/task")
    print(f"📊 Agents API:  http://localhost:{port}/api/v1/agents")
    print(f"🔑 External AI: http://localhost:{port}/api/v1/external/connect")
    print(f"   API key:     {get_api_key()[:6]}…  (full key in {API_KEY_FILE} or $HDS_API_KEY)")
    print(f"❤️  Health:      http://localhost:{port}/health")
    print("\n" + "="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
