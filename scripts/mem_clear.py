import json
import urllib.request
import sys
from pathlib import Path

# Resolve ROOT relative to AI-MIND/scripts/
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = ROOT_DIR / "AI-MIND" / "architecture" / "agent_roles.json"

def get_active_model_names():
    names = set()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                for role in cfg.values():
                    if "model" in role:
                        names.add(role["model"])
        except Exception:
            pass
    return names

def unload_ollama(endpoint):
    try:
        ps_url = f"{endpoint}/api/ps"
        with urllib.request.urlopen(ps_url, timeout=0.5) as res:
            data = json.loads(res.read().decode())
            for m in data.get("models", []):
                name = m["name"]
                print(f"    [!] Unloading Ollama: {name}")
                gen_url = f"{endpoint}/api/generate"
                req = urllib.request.Request(gen_url, 
                    data=json.dumps({"model": name, "keep_alive": 0}).encode())
                urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

def unload_lm_studio(endpoint, active_names):
    try:
        # 1. Try New REST API (api/v0/models)
        models_url = f"{endpoint}/api/v0/models"
        loaded_ids = []
        try:
            with urllib.request.urlopen(models_url, timeout=0.5) as res:
                data = json.loads(res.read().decode())
                for m in data.get("data", []):
                    if m.get("state") == "loaded":
                        loaded_ids.append(m["id"])
        except:
            # Fallback to v1/models
            models_url = f"{endpoint}/v1/models"
            with urllib.request.urlopen(models_url, timeout=0.5) as res:
                data = json.loads(res.read().decode())
                for m in data.get("data", []):
                    loaded_ids.append(m["id"])

        for m_id in loaded_ids:
            if not any(name in m_id for name in active_names):
                # If it's not one of our current active models, we definitely want to unload it
                pass
            
            # Print only for active roles
            if any(name in m_id for name in active_names):
                print(f"    [!] Unloading LM Studio: {m_id}")

            # Try ALL possible unload patterns for compatibility
            for path in ["/api/v1/models/unload", "/v1/models/unload", "/api/v0/models/unload"]:
                for key in ["instance_id", "identifier", "id"]:
                    try:
                        req = urllib.request.Request(f"{endpoint}{path}", 
                            data=json.dumps({key: m_id}).encode(),
                            headers={"Content-Type": "application/json"})
                        urllib.request.urlopen(req, timeout=0.5)
                    except: pass
    except Exception:
        pass

def clear_vram(silent=False):
    if not silent:
        print("🧹 VRAM Cleanup (Ollama & LM Studio New API)...")
    active_names = get_active_model_names()
    
    endpoints = {"http://127.0.0.1:11434"}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                for role in cfg.values():
                    if "endpoint" in role:
                        endpoints.add(role["endpoint"].rstrip('/'))
        except Exception: pass

    for ep in endpoints:
        unload_ollama(ep)
        unload_lm_studio(ep, active_names)
            
    if not silent:
        print("✅ Cleanup finished.")

if __name__ == "__main__":
    is_silent = "--silent" in sys.argv
    clear_vram(silent=is_silent)
