#!/usr/bin/env python3
"""
fallback_model_chain.py
HDS6 TKT-003c: High Availability Model Chain

If the main API (OpenAI) fails — automatically switches to fallback (LM Studio).
Provides High Availability without losing functionality.

Authors: HDS6 Development Team
License: HDS6 Standard
"""

import time
import logging
from typing import Optional, Dict, Any
from enum import Enum


class ModelProvider(Enum):
    """Available model providers."""
    PRIMARY = "openai"  # OpenAI GPT-4/3.5
    FALLBACK_LOCAL = "lm_studio"  # Local model (LM Studio)
    FALLBACK_ANTHROPIC = "anthropic"  # Fallback option


class FallbackModelChain:
    """
    Model chain with automatic fallback.
    If primary model unavailable, switches to the next one.
    """

    def __init__(self, primary_timeout: float = 10.0):
        self.primary_timeout = primary_timeout
        self.current_provider = ModelProvider.PRIMARY
        self.fallback_reason = None
        self.logger = logging.getLogger(__name__)

        # Transition statistics
        self.stats = {
            "primary_attempts": 0,
            "primary_failures": 0,
            "fallback_uses": 0,
            "recovery_count": 0,
        }

        print("[FallbackChain] Initialized with PRIMARY → FALLBACK_LOCAL chain")

    def query(
        self,
        prompt: str,
        task_id: str = "unknown",
        force_provider: Optional[ModelProvider] = None,
    ) -> Dict[str, Any]:
        """
        Execute query with automatic fallback.
        """
        # If provider explicitly specified, use it
        if force_provider:
            return self._query_provider(force_provider, prompt, task_id)

        # Try primary provider
        self.stats["primary_attempts"] += 1
        try:
            result = self._query_provider(
                ModelProvider.PRIMARY, prompt, task_id, timeout=self.primary_timeout
            )
            # Success! Check if we need to restore primary
            if self.current_provider != ModelProvider.PRIMARY:
                self.current_provider = ModelProvider.PRIMARY
                self.stats["recovery_count"] += 1
                print(
                    f"[FallbackChain] ✓ Recovered PRIMARY provider (Task: {task_id})"
                )

            return result
        except Exception as e:
            self.stats["primary_failures"] += 1
            print(f"[FallbackChain] ⚠️ PRIMARY failed: {e}")
            self.fallback_reason = str(e)

        # PRIMARY failed — switching to FALLBACK
        self.current_provider = ModelProvider.FALLBACK_LOCAL
        self.stats["fallback_uses"] += 1

        try:
            result = self._query_provider(
                ModelProvider.FALLBACK_LOCAL, prompt, task_id
            )
            print(
                f"[FallbackChain] 🔄 Using FALLBACK_LOCAL (Task: {task_id}). "
                f"Response quality may be lower."
            )
            return result
        except Exception as e:
            print(f"[FallbackChain ERROR] FALLBACK also failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "provider": "none",
                "message": "All providers failed",
            }

    def _query_provider(
        self,
        provider: ModelProvider,
        prompt: str,
        task_id: str,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute query to a specific provider."""
        if provider == ModelProvider.PRIMARY:
            return self._query_openai(prompt, task_id, timeout)
        elif provider == ModelProvider.FALLBACK_LOCAL:
            return self._query_lm_studio(prompt, task_id)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _query_openai(
        self, prompt: str, task_id: str, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Request до OpenAI API.
        In real implementation this would be an actual client.
        """
        # Simulation: 80% success rate for fallback demo
        import random

        if random.random() < 0.2:  # 20% error probability
            raise Exception("OpenAI API timeout (simulated)")

        return {
            "status": "success",
            "provider": "openai",
            "task_id": task_id,
            "response": f"Response from OpenAI for task {task_id}",
            "tokens_used": 150,
        }

    def _query_lm_studio(self, prompt: str, task_id: str) -> Dict[str, Any]:
        """
        Request to local model (LM Studio).
        This is a fallback option — quiet but reliable.
        """
        # In reality — HTTP request to localhost:1234 (LM Studio default port)
        return {
            "status": "success",
            "provider": "lm_studio",
            "task_id": task_id,
            "response": f"Response from LM Studio (local fallback) for task {task_id}",
            "tokens_used": 180,
            "note": "Running on local hardware, quality may be lower",
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Returns model chain health status."""
        total_attempts = self.stats["primary_attempts"]
        success_rate = (
            (total_attempts - self.stats["primary_failures"]) / total_attempts * 100
            if total_attempts > 0
            else 0
        )

        return {
            "current_provider": self.current_provider.value,
            "primary_availability": f"{success_rate:.1f}%",
            "fallback_uses": self.stats["fallback_uses"],
            "recovery_count": self.stats["recovery_count"],
            "fallback_reason": self.fallback_reason,
        }

    def export_stats(self) -> str:
        """Export statistics."""
        health = self.get_health_status()

        report = "FALLBACK MODEL CHAIN STATISTICS\n"
        report += "=" * 60 + "\n\n"
        report += f"Current Provider: {health['current_provider']}\n"
        report += f"Primary Availability: {health['primary_availability']}\n"
        report += f"Fallback Uses: {health['fallback_uses']}\n"
        report += f"Recovery Count: {health['recovery_count']}\n"

        if health["fallback_reason"]:
            report += f"Last Failure: {health['fallback_reason']}\n"

        return report
