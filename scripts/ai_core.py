import os
import sys
import json
import time
import urllib.request
from pathlib import Path

class UniversalAICore:
    def __init__(self, endpoint, model):
        self.endpoint = endpoint
        self.model = model

    def query(self, prompt, system_prompt="You are a helpful AI assistant.", temperature=0.3, image_path=None):
        content = [{"type": "text", "text": prompt}]
        
        if image_path:
            import base64
            p = Path(image_path)
            if p.exists():
                with open(p, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                })

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            "temperature": temperature
        }
        
        # Ensure correct path for OpenAI compatible APIs (Ollama / LM Studio)
        base_url = self.endpoint.rstrip('/')
        if not base_url.endswith('/v1'):
            api_url = f"{base_url}/v1/chat/completions"
        else:
            api_url = f"{base_url}/chat/completions"

        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"ERROR: AI Request Timeout or Failure (180s limit): {str(e)}"

def get_core(endpoint, model):
    return UniversalAICore(endpoint, model)
