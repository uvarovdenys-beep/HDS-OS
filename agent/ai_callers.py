#!/usr/bin/env python3
"""ai_callers.py — adapters that connect HDS to a real AI server.

Split out of aivc_controller.py under R-300. Each factory returns a plain
`call(prompt) -> str` closure, so the rest of the OS never knows which server
answered. Local callers (LM Studio, Ollama) share one generation budget.

NOTE this is an OS-INTERNAL module: it reads os.environ for tunables
(HDS_MAX_TOKENS, HDS_AI_TIMEOUT). The cage's Python validator rejects `os` in
AI-GENERATED payloads by design; OS internals are written as trusted system
calls instead. That distinction is deliberate, not a bypass.
"""
import requests


# ──────────────────────────────────────────────────────────────
# AI CALL ADAPTERS — connect to real AI servers
# ──────────────────────────────────────────────────────────────

def make_lmstudio_caller(
    base_url: str = "http://127.0.0.1:1234",
    model: str = "",
    temperature: float = 0.2,
    max_tokens: int = 0,
):
    """Create AI caller for LM Studio. Handles thinking-models (Qwen3.5) via reasoning_content fallback."""
    budget = max_tokens or _default_max_tokens()

    def call(prompt: str) -> str:
        r = requests.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": budget,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=_default_ai_timeout(),
        )
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content.strip() and msg.get("reasoning_content"):
            content = msg["reasoning_content"]
        return content
    return call


def make_ollama_caller(
    base_url: str = "http://127.0.0.1:11434",
    model: str = "qwen2.5:7b",
    temperature: float = 0.2,
    max_tokens: int = 0,
):
    """Create AI caller for Ollama."""
    budget = max_tokens or _default_max_tokens()

    def call(prompt: str) -> str:
        r = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": budget},
            },
            timeout=_default_ai_timeout(),
        )
        r.raise_for_status()
        return r.json().get("response", "")
    return call


def _default_max_tokens() -> int:
    """Generation ceiling for local callers.

    Pinned at 1024 this truncated any file over ~150 lines; the cage then
    rejected the fragment as a syntax error (TS1005), which reads like a model
    failure but is a budget failure. Override with HDS_MAX_TOKENS.
    """
    import os as _os
    try:
        return max(256, int(_os.environ.get("HDS_MAX_TOKENS", "4096")))
    except ValueError:
        return 4096


def _default_ai_timeout() -> int:
    """Seconds to wait for one generation. A bigger budget needs a longer wall."""
    import os as _os
    try:
        return max(30, int(_os.environ.get("HDS_AI_TIMEOUT", "300")))
    except ValueError:
        return 300


def make_anthropic_caller(
    api_key: str,
    model: str = "claude-sonnet-4-6-20250514",
    max_tokens: int = 1024,
):
    """Create AI caller for Anthropic Claude API."""
    def call(prompt: str) -> str:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    return call


def make_openai_caller(
    api_key: str,
    model: str = "gpt-4o",
    temperature: float = 0.2,
    max_tokens: int = 1024,
):
    """Create AI caller for OpenAI."""
    def call(prompt: str) -> str:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    return call

__all__ = [
    "make_lmstudio_caller",
    "make_ollama_caller",
    "make_anthropic_caller",
    "make_openai_caller",
]
