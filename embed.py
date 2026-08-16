#!/usr/bin/env python3
"""embed.py — text embeddings from the local nomic model, stdlib only.

Semantic recall needs vectors, not substring matches. This calls the
nomic-embed-text model already served by ollama. Best-effort: any failure
(server down, timeout, bad response) returns None and the caller falls back to
keyword recall — memory must never break because an optional service is absent.
No dependency: urllib, like model_scan.
"""
import json
import urllib.request
from typing import List, Optional

_URL = "http://localhost:11434/api/embeddings"
_MODEL = "nomic-embed-text"


def embed(text: str, timeout: float = 6.0) -> Optional[List[float]]:
    """Return the embedding vector for `text`, or None if unavailable."""
    text = (text or "").strip()
    if not text:
        return None
    body = json.dumps({"model": _MODEL, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    vec = data.get("embedding")
    if isinstance(vec, list) and vec and all(isinstance(x, (int, float)) for x in vec):
        return [float(x) for x in vec]
    return None


def cosine(a, b) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 on mismatch/empty."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
