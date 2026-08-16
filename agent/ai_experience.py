#!/usr/bin/env python3
"""
ai_experience.py
HDS TKT-005: AI Retrospective Module (Bad practices database)

AI records its own mistakes as anti-patterns for future runs.
Before each new task the system reminds what NOT to do.

Authors: HDS Development Team
License: HDS Standard
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Optional

try:
    from vox import VoxService
except ImportError:
    VoxService = None

# Semantic recall: only lessons this similar to the query are surfaced. Below it,
# nothing is returned — no "last 5 regardless" leak of irrelevant advice.
# Calibrated on nomic-embed-text: relevant pairs ~0.68-0.73, unrelated ~0.32-0.40.
_RECALL_MIN = float(os.environ.get("HDS_RECALL_MIN", "0.55"))
_RECALL_MAX = 4
_SEVERITY_WEIGHT = {"CRITICAL": 1.15, "HIGH": 1.05, "MEDIUM": 1.0}


def _embed_text(text):
    """Embed via the local nomic model; None if the service is unavailable."""
    try:
        from embed import embed
        return embed(text)
    except Exception:
        return None


def consolidate(patterns: List[Dict], threshold: float = 0.92) -> List[Dict]:
    """
    Drop near-duplicate lessons. Iterate `patterns` in order and build a kept
    list. A pattern with no 'embedding' key is ALWAYS kept. A pattern WITH an
    'embedding' is dropped if its embedding has cosine similarity >= threshold to
    the embedding of any ALREADY-KEPT pattern; otherwise it is kept.
    
    Args:
        patterns (List[Dict]): List of patterns, each a dictionary that may contain an 'embedding'.
        threshold (float): Cosine similarity threshold for considering patterns as duplicates.
    
    Returns:
        List[Dict]: The filtered list of patterns with near-duplicates removed.
    """
    
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(y ** 2 for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
    
    kept = []
    for pattern in patterns:
        if 'embedding' not in pattern:
            kept.append(pattern)
        else:
            is_duplicate = False
            for k in kept:
                if 'embedding' in k:
                    sim = cosine_similarity(pattern['embedding'], k['embedding'])
                    if sim >= threshold:
                        is_duplicate = True
                        break
            if not is_duplicate:
                kept.append(pattern)
    
    return kept


class AIExperienceModule:
    """
    AI Retrospective & Self-Learning module.
    Stores mistakes as structured lessons for future tasks.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path(__file__).parent.parent / "ai-mind" / "experience" / "anti_patterns.json"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vox = VoxService(self.db_path.parent.parent / "logs") if VoxService else None

        self._init_db()
        print(f"[AI-Experience] Initialized at {self.db_path}")

    def _init_db(self):
        """Initialize anti-patterns DB if it does not exist."""
        if not self.db_path.exists():
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({"anti_patterns": [], "lessons_learned": 0}, f, ensure_ascii=False, indent=2)

    def register_failure(
        self,
        task_id: str,
        error_trace: str,
        ai_self_analysis: str,
        anti_pattern_rule: str,
        symbol: str = "",
    ) -> bool:
        """
        Register a failed attempt.
        AI analyzed the error and derived a rule for the future.

        `symbol` (e.g. "path/to/file.py::func") anchors the lesson to where it
        happened — the code side of the mirror graph — so recall can favour
        lessons about the file being changed.
        """
        try:
            with open(self.db_path, "r+", encoding="utf-8") as f:
                data = json.load(f)

                entry = {
                    "task_id": task_id,
                    "timestamp": time.time(),
                    "error": error_trace[:200],  # First 200 chars for brevity
                    "ai_self_analysis": ai_self_analysis,
                    "derived_rule": anti_pattern_rule,
                    "severity": self._assess_severity(error_trace),
                }
                # Embed the rule for semantic recall; store the anchor if given.
                vec = _embed_text(f"{anti_pattern_rule} {ai_self_analysis}")
                if vec:
                    entry["embedding"] = vec
                if symbol:
                    entry["symbol"] = symbol

                data["anti_patterns"].append(entry)
                data["lessons_learned"] = len(data["anti_patterns"])

                f.seek(0)
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.truncate()

            if self.vox:
                self.vox.speak(f"Learned anti-pattern: {anti_pattern_rule}", "INFO")

            print(f"[AI-Experience] Registered failure ({task_id}): {anti_pattern_rule}")
            return True
        except Exception as e:
            print(f"[AI-Experience ERROR] Could not register failure: {e}")
            return False

    def _assess_severity(self, error_trace: str) -> str:
        """Evaluate error severity."""
        if any(
            word in error_trace.lower()
            for word in ["critical", "fatal", "halt", "crash", "core dump"]
        ):
            return "CRITICAL"
        elif any(word in error_trace.lower() for word in ["error", "failed", "exception"]):
            return "HIGH"
        else:
            return "MEDIUM"

    def get_context_for_prompt(self, keywords: List[str] = None,
                               symbol: str = "") -> str:
        """Most relevant past mistakes for the system prompt.

        Semantic first: the query is embedded and lessons ranked by cosine
        similarity, weighted by severity and boosted when anchored to the same
        `symbol` being changed. Only lessons above _RECALL_MIN are returned —
        below it, nothing, so irrelevant advice never leaks. Falls back to
        keyword matching when embeddings are unavailable.
        """
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return ""
        patterns = data.get("anti_patterns", [])
        if not patterns:
            return ""

        query = " ".join(str(k) for k in keywords) if keywords else ""
        relevant = self._recall_semantic(patterns, query, symbol)
        if relevant is None:                       # embeddings unavailable
            relevant = self._recall_keyword(patterns, keywords)
        if not relevant:
            return ""
        return self._format_lessons(relevant)

    def _recall_semantic(self, patterns, query, symbol):
        """Lessons above the similarity floor, ranked; None if not embeddable."""
        embedded = [p for p in patterns if p.get("embedding")]
        qvec = _embed_text(query) if query else None
        if qvec is None or not embedded:
            return None
        from embed import cosine
        scored = []
        for p in embedded:
            sim = cosine(qvec, p["embedding"])
            if sim < _RECALL_MIN:
                continue
            weight = _SEVERITY_WEIGHT.get(p.get("severity", "MEDIUM"), 1.0)
            if symbol and p.get("symbol") == symbol:
                weight *= 1.2                       # a lesson about THIS file
            scored.append((sim * weight, p))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [p for _, p in scored[:_RECALL_MAX]]

    def _recall_keyword(self, patterns, keywords):
        """Substring fallback. No 'last N regardless' — silence beats noise."""
        if not keywords:
            return []
        return [p for p in patterns
                if any(str(kw).lower() in p.get("derived_rule", "").lower()
                       for kw in keywords)][:_RECALL_MAX]

    def _format_lessons(self, relevant) -> str:
        context = "\n" + "=" * 60 + "\n"
        context += "[CRITICAL: AI RETROSPECTIVE - PAST MISTAKES TO AVOID]\n"
        context += "=" * 60 + "\n"
        for entry in relevant:
            emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "📝"}.get(
                entry.get("severity", "MEDIUM"), "📝")
            context += (f"\n{emoji} AVOID: {entry['derived_rule']}\n"
                        f"   Reason: {entry['ai_self_analysis']}\n")
        context += "\n" + "=" * 60 + "\n\n"
        return context

    def get_stats(self) -> Dict:
        """Returns AI experience statistics."""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            patterns = data.get("anti_patterns", [])
            critical = sum(1 for p in patterns if p.get("severity") == "CRITICAL")
            high = sum(1 for p in patterns if p.get("severity") == "HIGH")

            return {
                "total_failures": len(patterns),
                "critical": critical,
                "high": high,
                "medium": len(patterns) - critical - high,
            }
        except Exception:
            return {"total_failures": 0, "critical": 0, "high": 0, "medium": 0}

    def export_lessons(self) -> str:
        """Export all lessons as text for analysis."""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            patterns = data.get("anti_patterns", [])
            if not patterns:
                return "No lessons learned yet."

            output = "AI EXPERIENCE DATABASE - ALL LESSONS\n"
            output += "=" * 60 + "\n\n"

            for i, p in enumerate(patterns, 1):
                output += f"{i}. {p['derived_rule']}\n"
                output += f"   (Task: {p['task_id']}, Severity: {p.get('severity', 'MEDIUM')})\n"
                output += f"   {p['ai_self_analysis']}\n\n"

            return output
        except Exception as e:
            return f"Error exporting lessons: {e}"


    def consolidate_store(self) -> int:
        """Merge near-duplicate lessons in place. Returns how many were removed."""
        try:
            with open(self.db_path, "r+", encoding="utf-8") as f:
                data = json.load(f)
                before = data.get("anti_patterns", [])
                kept = consolidate(before)
                removed = len(before) - len(kept)
                if removed:
                    data["anti_patterns"] = kept
                    data["lessons_learned"] = len(kept)
                    f.seek(0)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.truncate()
            return removed
        except Exception:
            return 0
