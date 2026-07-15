#!/usr/bin/env python3
"""
cost_router.py
HDS Cost Router — routes tasks to the cheapest capable model.

Principle: Don't use XL for an S-level task.
Given a task complexity, find the smallest (cheapest) model that can handle it.

IMPORTANT: This is NOT multi-model pipeline. Only ONE model runs at a time.
The cost router recommends which model to LOAD next, not parallel execution.
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from model_router import ProtocolSize, classify_model

logger = logging.getLogger("cost_router")


@dataclass
class ModelCost:
    """Cost profile for a model."""
    name: str
    size: ProtocolSize
    ram_gb: float           # Approximate RAM usage
    tokens_per_second: float  # Approximate generation speed
    load_time_seconds: float  # Time to load model
    quality_score: float     # 0.0-1.0, from diagnostic or estimate

    @property
    def cost_score(self) -> float:
        """Lower is cheaper. Combines RAM + speed penalty."""
        # Heavier models cost more; slower models cost more
        speed_penalty = max(0, 30.0 - self.tokens_per_second) / 30.0
        return self.ram_gb + speed_penalty * 2 + self.load_time_seconds / 10


# Known local models with approximate costs
LOCAL_MODEL_COSTS: Dict[str, ModelCost] = {
    "qwen3.5:4b": ModelCost("qwen3.5:4b", ProtocolSize.S, ram_gb=3.0, tokens_per_second=40.0, load_time_seconds=5, quality_score=0.4),
    "qwen3.5:9b": ModelCost("qwen3.5:9b", ProtocolSize.M, ram_gb=6.0, tokens_per_second=25.0, load_time_seconds=8, quality_score=0.6),
    "qwen3.5:27b": ModelCost("qwen3.5:27b", ProtocolSize.XL, ram_gb=18.0, tokens_per_second=10.0, load_time_seconds=20, quality_score=0.85),
    "qwen3-coder:30b": ModelCost("qwen3-coder:30b", ProtocolSize.XL, ram_gb=20.0, tokens_per_second=8.0, load_time_seconds=25, quality_score=0.8),
    "deepseek-r1:8b": ModelCost("deepseek-r1:8b", ProtocolSize.L, ram_gb=5.5, tokens_per_second=20.0, load_time_seconds=7, quality_score=0.55),
    "mistral": ModelCost("mistral", ProtocolSize.M, ram_gb=4.5, tokens_per_second=30.0, load_time_seconds=6, quality_score=0.5),
    "llama3": ModelCost("llama3", ProtocolSize.M, ram_gb=5.0, tokens_per_second=25.0, load_time_seconds=7, quality_score=0.5),
    "gpt-oss:20b": ModelCost("gpt-oss:20b", ProtocolSize.XL, ram_gb=14.0, tokens_per_second=12.0, load_time_seconds=15, quality_score=0.75),
}

# Size hierarchy for comparison
SIZE_ORDER = [ProtocolSize.S, ProtocolSize.M, ProtocolSize.L, ProtocolSize.XL]


def _default_cost(name: str) -> "ModelCost":
    """Neutral cost for a DISCOVERED model with no hint in LOCAL_MODEL_COSTS.

    Keeps the router portable: a model the scan finds on some other machine still
    routes, even if it was never listed here.
    """
    return ModelCost(name, ProtocolSize.M, ram_gb=8.0, tokens_per_second=20.0,
                     load_time_seconds=10, quality_score=0.5)


class CostRouter:
    """
    Routes tasks to the cheapest model that can handle them.

    Usage:
        router = CostRouter(available_models=["qwen3.5:4b", "qwen3.5:9b", "qwen3.5:27b"])
        recommendation = router.recommend("qwen3.5:9b", task_complexity=2)
        # Returns: "qwen3.5:4b" — cheaper model can handle complexity 2
    """

    def __init__(self, available_models: List[str] = None):
        """
        Args:
            available_models: List of model names available on this machine.
                             If None, uses all known models.
        """
        # Models are DISCOVERED by scanning endpoints — never a hardcoded list
        # tied to one machine. LOCAL_MODEL_COSTS is only a cost-HINT table;
        # a discovered model with no hint gets a neutral default (portable).
        if available_models is None:
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from model_scan import available_model_names
                available_models = available_model_names()
            except Exception:
                available_models = []
        if not available_models:
            available_models = list(LOCAL_MODEL_COSTS)  # last-resort fallback
        self.models = {
            name: LOCAL_MODEL_COSTS.get(name, _default_cost(name))
            for name in available_models
        }

        # Load diagnostic overrides if available
        self._load_diagnostic_overrides()

        logger.info(f"CostRouter initialized with {len(self.models)} models")

    def _load_diagnostic_overrides(self):
        """Load diagnostic results to override static quality scores."""
        reports_dir = Path("ai-mind/protocols/reports")
        if not reports_dir.exists():
            return

        for report_file in reports_dir.glob("*.json"):
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    report = json.load(f)
                model_name = report.get("model", "")
                if model_name in self.models:
                    score = report.get("score", 0)
                    # Normalize to 0.0-1.0
                    self.models[model_name].quality_score = score / 18.0
                    # Override size from diagnostic
                    size_str = report.get("size", "").lower()
                    if size_str in ("xl", "l", "m", "s"):
                        self.models[model_name].size = ProtocolSize(size_str)
                    logger.info(f"Loaded diagnostic override for {model_name}: score={score}")
            except (json.JSONDecodeError, OSError):
                pass

    def minimum_size_for_complexity(self, complexity: int) -> ProtocolSize:
        """Determine minimum protocol size needed for given complexity."""
        if complexity >= 8:
            return ProtocolSize.XL
        elif complexity >= 5:
            return ProtocolSize.L
        elif complexity >= 3:
            return ProtocolSize.M
        else:
            return ProtocolSize.S

    def recommend(self, current_model: str, task_complexity: int) -> Optional[str]:
        """
        Recommend the cheapest model that can handle the task.

        Args:
            current_model: Currently loaded model name
            task_complexity: Task complexity (1-10)

        Returns:
            Recommended model name, or None if current is optimal.
            Returns current_model if no cheaper option exists.
        """
        min_size = self.minimum_size_for_complexity(task_complexity)
        min_idx = SIZE_ORDER.index(min_size)

        # Filter models that can handle this complexity
        capable = [
            (name, cost) for name, cost in self.models.items()
            if SIZE_ORDER.index(cost.size) >= min_idx
        ]

        if not capable:
            logger.warning(f"No capable model for complexity {task_complexity}")
            return current_model

        # Sort by cost (cheapest first)
        capable.sort(key=lambda x: x[1].cost_score)

        cheapest_name, cheapest_cost = capable[0]

        # If current model is already the cheapest option, keep it
        if current_model in self.models:
            current_cost = self.models[current_model]
            current_capable = SIZE_ORDER.index(current_cost.size) >= min_idx

            if current_capable and current_cost.cost_score <= cheapest_cost.cost_score:
                return None  # Current model is optimal

        return cheapest_name

    def get_routing_table(self) -> List[Dict]:
        """Generate a full routing table showing which model handles which complexity."""
        table = []
        for complexity in range(1, 11):
            min_size = self.minimum_size_for_complexity(complexity)
            rec = self.recommend("", complexity)
            cost = self.models.get(rec, None)
            table.append({
                "complexity": complexity,
                "min_size": min_size.value.upper(),
                "recommended_model": rec or "none",
                "ram_gb": cost.ram_gb if cost else 0,
                "cost_score": round(cost.cost_score, 2) if cost else 0,
            })
        return table

    def get_savings_report(self, task_history: List[Dict]) -> Dict:
        """
        Calculate potential savings from cost routing vs always using the biggest model.

        Args:
            task_history: List of {"complexity": int, "model_used": str}
        """
        biggest_model = max(self.models.values(), key=lambda m: m.ram_gb)

        actual_cost = 0.0
        optimal_cost = 0.0

        for task in task_history:
            comp = task.get("complexity", 5)
            used = task.get("model_used", "")

            if used in self.models:
                actual_cost += self.models[used].cost_score
            else:
                actual_cost += biggest_model.cost_score

            rec = self.recommend("", comp)
            if rec and rec in self.models:
                optimal_cost += self.models[rec].cost_score

        savings = actual_cost - optimal_cost if actual_cost > optimal_cost else 0

        return {
            "tasks_analyzed": len(task_history),
            "actual_cost_score": round(actual_cost, 2),
            "optimal_cost_score": round(optimal_cost, 2),
            "potential_savings": round(savings, 2),
            "savings_percent": round((savings / actual_cost * 100) if actual_cost > 0 else 0, 1),
        }


# CLI
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("HDS COST ROUTER — Cheapest Capable Model")
    print("=" * 60)

    router = CostRouter()

    print("\nRouting Table:")
    print(f"{'Complexity':>10} {'Min Size':>8} {'Recommended':>20} {'RAM (GB)':>8} {'Cost':>6}")
    print("-" * 56)

    for row in router.get_routing_table():
        print(f"{row['complexity']:>10} {row['min_size']:>8} {row['recommended_model']:>20} {row['ram_gb']:>8.1f} {row['cost_score']:>6.2f}")

    # Demo: savings report
    print("\n" + "=" * 60)
    print("Savings Demo (10 tasks always on 27b vs cost-routed)")
    history = [
        {"complexity": 1, "model_used": "qwen3.5:27b"},
        {"complexity": 2, "model_used": "qwen3.5:27b"},
        {"complexity": 3, "model_used": "qwen3.5:27b"},
        {"complexity": 2, "model_used": "qwen3.5:27b"},
        {"complexity": 8, "model_used": "qwen3.5:27b"},
        {"complexity": 5, "model_used": "qwen3.5:27b"},
        {"complexity": 1, "model_used": "qwen3.5:27b"},
        {"complexity": 4, "model_used": "qwen3.5:27b"},
        {"complexity": 9, "model_used": "qwen3.5:27b"},
        {"complexity": 3, "model_used": "qwen3.5:27b"},
    ]

    report = router.get_savings_report(history)
    print(f"  Actual cost:  {report['actual_cost_score']}")
    print(f"  Optimal cost: {report['optimal_cost_score']}")
    print(f"  Savings:      {report['potential_savings']} ({report['savings_percent']}%)")
