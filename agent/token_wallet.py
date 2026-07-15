#!/usr/bin/env python3
"""
token_wallet.py
HDS6 TKT-003b: Token Telemetry Wallet

Logs AI API spending (OpenAI, Anthropic) without blocking the main thread.
Allows tracking cost and token usage in real time.

Authors: HDS6 Development Team
License: HDS6 Standard
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class TokenWallet:
    """
    AI request cost telemetry.
    Logs asynchronously, does not block main thread.
    """

    def __init__(self, log_path: Path = None):
        self.log_path = log_path or Path(__file__).parent.parent / "ai-mind" / "logs" / "token_wallet.json"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_wallet()
        self._lock = threading.Lock()
        print(f"[TokenWallet] Initialized at {self.log_path}")

    def _init_wallet(self):
        """Initialize wallet if it does not exist."""
        if not self.log_path.exists():
            with open(self.log_path, "w") as f:
                json.dump(
                    {
                        "created_at": datetime.now().isoformat(),
                        "total_tokens": 0,
                        "total_cost_usd": 0.0,
                        "requests": [],
                        "by_provider": {},
                    },
                    f,
                    indent=2,
                )

    def log_usage(
        self,
        task_id: str,
        provider: str = "openai",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> bool:
        """
        Records token spending.
        Runs in background thread, does not block main.
        """

        def _write():
            try:
                with self._lock:
                    with open(self.log_path, "r+") as f:
                        data = json.load(f)

                        total = prompt_tokens + completion_tokens
                        data["total_tokens"] += total
                        data["total_cost_usd"] += cost_usd

                        # Initialize provider if new
                        if provider not in data["by_provider"]:
                            data["by_provider"][provider] = {
                                "tokens": 0,
                                "cost": 0.0,
                                "requests": 0,
                            }

                        data["by_provider"][provider]["tokens"] += total
                        data["by_provider"][provider]["cost"] += cost_usd
                        data["by_provider"][provider]["requests"] += 1

                        data["requests"].append(
                            {
                                "task_id": task_id,
                                "timestamp": datetime.now().isoformat(),
                                "provider": provider,
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total,
                                "cost_usd": cost_usd,
                            }
                        )

                        f.seek(0)
                        json.dump(data, f, indent=2)
                        f.truncate()

                print(
                    f"[TokenWallet] Task {task_id}: {total} tokens, ${cost_usd:.4f} "
                    f"({provider})"
                )
                return True
            except Exception as e:
                print(f"[TokenWallet ERROR] Could not log usage: {e}")
                return False

        # Launch in background thread
        thread = threading.Thread(target=_write, daemon=True)
        thread.start()
        return True

    def get_stats(self) -> Dict:
        """Returns usage statistics."""
        try:
            with open(self.log_path, "r") as f:
                data = json.load(f)

            return {
                "total_tokens": data.get("total_tokens", 0),
                "total_cost_usd": data.get("total_cost_usd", 0.0),
                "request_count": len(data.get("requests", [])),
                "by_provider": data.get("by_provider", {}),
            }
        except Exception as e:
            print(f"[TokenWallet WARNING] Could not read stats: {e}")
            return {"total_tokens": 0, "total_cost_usd": 0.0, "request_count": 0}

    def get_daily_cost(self) -> float:
        """Returns current day spending (USD)."""
        try:
            with open(self.log_path, "r") as f:
                data = json.load(f)

            today = datetime.now().date().isoformat()
            daily_cost = 0.0

            for req in data.get("requests", []):
                req_date = req["timestamp"][:10]  # YYYY-MM-DD
                if req_date == today:
                    daily_cost += req.get("cost_usd", 0.0)

            return daily_cost
        except Exception:
            return 0.0

    def export_report(self) -> str:
        """Export spending report."""
        try:
            with open(self.log_path, "r") as f:
                data = json.load(f)

            stats = self.get_stats()
            daily_cost = self.get_daily_cost()

            report = "TOKEN WALLET REPORT\n"
            report += "=" * 60 + "\n\n"
            report += f"Total Tokens Used: {stats['total_tokens']:,}\n"
            report += f"Total Cost (USD): ${stats['total_cost_usd']:.2f}\n"
            report += f"Today's Cost (USD): ${daily_cost:.2f}\n"
            report += f"Total Requests: {stats['request_count']}\n\n"

            report += "By Provider:\n"
            for provider, info in stats["by_provider"].items():
                report += (
                    f"  {provider}: {info['tokens']:,} tokens, "
                    f"${info['cost']:.2f}, {info['requests']} requests\n"
                )

            return report
        except Exception as e:
            return f"Error generating report: {e}"
