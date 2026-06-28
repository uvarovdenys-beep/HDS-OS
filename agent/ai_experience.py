#!/usr/bin/env python3
"""
ai_experience.py
HDS6 TKT-005: AI Retrospective Module (Bad practices database)

AI records its own mistakes as anti-patterns for future runs.
Before each new task the system reminds what NOT to do.

Authors: HDS6 Development Team
License: HDS6 Standard
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional

try:
    from vox import VoxService
except ImportError:
    VoxService = None


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
    ) -> bool:
        """
        Register a failed attempt.
        AI analyzed the error and derived a rule for the future.
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

    def get_context_for_prompt(self, keywords: List[str] = None) -> str:
        """
        Extract most relevant lessons for injection into system prompt.
        This encourages the AI to take precautions based on its own experience.
        """
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            patterns = data.get("anti_patterns", [])
            if not patterns:
                return ""

            # Filter by keywords if provided
            if keywords:
                relevant = [
                    p
                    for p in patterns
                    if any(kw.lower() in p["derived_rule"].lower() for kw in keywords)
                ]
            else:
                relevant = patterns

            if not relevant:
                # Take last 5 regardless
                relevant = patterns[-5:]

            # Format for injection
            context = "\n" + "=" * 60 + "\n"
            context += "[CRITICAL: AI RETROSPECTIVE - PAST MISTAKES TO AVOID]\n"
            context += "=" * 60 + "\n"

            for entry in relevant:
                severity_emoji = {
                    "CRITICAL": "🚨",
                    "HIGH": "⚠️",
                    "MEDIUM": "📝",
                }.get(entry.get("severity", "MEDIUM"), "📝")

                context += (
                    f"\n{severity_emoji} AVOID: {entry['derived_rule']}\n"
                    f"   Reason: {entry['ai_self_analysis']}\n"
                )

            context += "\n" + "=" * 60 + "\n\n"
            return context
        except Exception as e:
            print(f"[AI-Experience WARNING] Could not get context: {e}")
            return ""

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
