#!/usr/bin/env python3
"""
microkernel_ipc.py
HDS6 TKT-006: Microkernel IPC Client & Server Infrastructure

Implements Inter-Process Communication for delegating heavy modules (Vision, Browser)
to isolated daemons. The kernel is not blocked, work is performed in parallel.

Authors: HDS6 Development Team
License: HDS6 Standard
"""

import json
import requests
import threading
import time
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from enum import Enum
import logging


class DaemonType(Enum):
    """Microkernel daemon types."""
    VISION = "vision"
    BROWSER = "browser"
    ANALYSIS = "analysis"


class MicrokernelIPCClient:
    """
    IPC client for communicating with daemons.
    Launches a task in a daemon, waits for the result (asynchronously).
    """

    def __init__(self, daemon_config: Dict[str, str]):
        """
        daemon_config: {"vision": "http://localhost:9001", "browser": "http://localhost:9002", ...}
        """
        self.daemons = daemon_config
        self.timeout = 30  # 30 sec timeout per request
        self.logger = logging.getLogger(__name__)
        print(f"[MicrokernelIPC] Initialized with {len(self.daemons)} daemon(s)")

    def send_task(
        self,
        daemon_type: DaemonType,
        task_data: Dict[str, Any],
        async_mode: bool = True,
    ) -> Dict[str, Any]:
        """
        Sends a task to a daemon.
        async_mode=True -> returns immediately, result via callback
        async_mode=False -> waits for the result (blocking)
        """
        daemon_url = self.daemons.get(daemon_type.value)
        if not daemon_url:
            return {"status": "error", "error": f"Daemon {daemon_type.value} not configured"}

        if async_mode:
            # Asynchronous - do not wait
            threading.Thread(
                target=self._send_request,
                args=(daemon_url, task_data),
                daemon=True,
            ).start()
            return {"status": "queued", "daemon": daemon_type.value, "task_id": task_data.get("task_id")}
        else:
            # Synchronous - wait for result
            return self._send_request(daemon_url, task_data)

    def _send_request(self, daemon_url: str, task_data: Dict) -> Dict[str, Any]:
        """Performs an HTTP request to the daemon."""
        try:
            response = requests.post(
                f"{daemon_url}/execute",
                json=task_data,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"status": "error", "error": f"Daemon timeout ({self.timeout}s)"}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "error": "Daemon unreachable"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def health_check(self) -> Dict[str, bool]:
        """Checks the status of all daemons."""
        status = {}
        for daemon_name, daemon_url in self.daemons.items():
            try:
                response = requests.get(f"{daemon_url}/health", timeout=5)
                status[daemon_name] = response.status_code == 200
            except Exception:
                status[daemon_name] = False

        return status

    def get_daemon_stats(self, daemon_type: DaemonType) -> Optional[Dict]:
        """Retrieves daemon performance statistics."""
        daemon_url = self.daemons.get(daemon_type.value)
        if not daemon_url:
            return None

        try:
            response = requests.get(f"{daemon_url}/stats", timeout=10)
            return response.json()
        except Exception as e:
            print(f"[MicrokernelIPC] Could not get stats: {e}")
            return None


class MicrokernelIPCServer:
    """
    Base server for a daemon.
    Each daemon (Vision, Browser) inherits from this class.
    """

    def __init__(self, port: int, daemon_name: str):
        self.port = port
        self.daemon_name = daemon_name
        self.task_count = 0
        self.task_errors = 0
        self.logger = logging.getLogger(daemon_name)
        print(f"[MicrokernelServer] {daemon_name} initialized on port {port}")

    def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Override in subclass."""
        raise NotImplementedError("Subclass must implement execute_task()")

    def get_stats(self) -> Dict[str, Any]:
        """Daemon statistics."""
        return {
            "daemon": self.daemon_name,
            "port": self.port,
            "total_tasks": self.task_count,
            "errors": self.task_errors,
            "error_rate": (
                self.task_errors / self.task_count * 100
                if self.task_count > 0
                else 0
            ),
        }

    def start(self):
        """Starts the daemon HTTP server."""
        from http.server import BaseHTTPRequestHandler, HTTPServer

        daemon_server = self
        task_count_ref = [0]

        class RequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == "/execute":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    task_data = json.loads(body.decode("utf-8"))

                    try:
                        result = daemon_server.execute_task(task_data)
                        daemon_server.task_count += 1
                        status_code = 200
                    except Exception as e:
                        result = {"status": "error", "error": str(e)}
                        daemon_server.task_errors += 1
                        status_code = 500

                    self.send_response(status_code)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode("utf-8"))

                elif self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

                elif self.path == "/stats":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps(daemon_server.get_stats()).encode("utf-8")
                    )

            def log_message(self, format, *args):
                pass  # Suppress default logging

        server = HTTPServer(("localhost", self.port), RequestHandler)
        print(f"[MicrokernelServer] {self.daemon_name} started on port {self.port}")
        server.serve_forever()
