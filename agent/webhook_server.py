#!/usr/bin/env python3
"""webhook_server.py - Webhook API for HDS v1.1"""

import json
import time
import threading
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging

logger = logging.getLogger(__name__)


class WebhookServer:
    """Simple webhook API server for task submission and polling."""

    def __init__(self, port: int = 8080, tasks_dir: Path = None):
        self.port = port
        self.tasks_dir = tasks_dir or Path("ai-mind/tasks/active")
        self.task_queue = {}
        self.result_cache = {}

    def start(self):
        """Start webhook server."""
        server = HTTPServer(("localhost", self.port), WebhookRequestHandler)
        server.webhook_server = self
        logger.info(f"[Webhook] Started on port {self.port}")
        server.serve_forever()

    def submit_task(self, task_data: Dict[str, Any]) -> str:
        """Submit task via webhook, optionally with callback_url for async delivery."""
        task_id = task_data.get("task_id", f"WH-{int(time.time())}")
        self.task_queue[task_id] = task_data

        # Write to active tasks
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        task_file = self.tasks_dir / f"{task_id}.json"
        task_file.write_text(json.dumps(task_data, indent=2))

        # If callback_url provided, monitor for completion
        callback_url = task_data.get("callback_url")
        if callback_url:
            threading.Thread(
                target=self._deliver_callback,
                args=(task_id, callback_url),
                daemon=True
            ).start()

        return task_id

    def _deliver_callback(self, task_id: str, callback_url: str, max_retries: int = 3):
        """Wait for task result and POST to callback_url with exponential backoff."""
        completed_dir = self.tasks_dir.parent / "completed"
        result_file = completed_dir / f"{task_id}_RESULT.json"

        # Poll for result (max 5 min)
        for _ in range(60):
            if result_file.exists():
                break
            time.sleep(5)
        else:
            logger.warning(f"[Webhook] Callback timeout for {task_id}")
            return

        result = json.loads(result_file.read_text())

        # Deliver with retries
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    callback_url,
                    json={"task_id": task_id, "result": result},
                    timeout=10
                )
                if resp.status_code < 400:
                    logger.info(f"[Webhook] Callback delivered for {task_id}")
                    return
            except Exception as e:
                logger.warning(f"[Webhook] Callback attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)

        logger.error(f"[Webhook] Callback failed after {max_retries} retries for {task_id}")

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status."""
        # Check completed
        completed_file = self.tasks_dir.parent / "completed" / f"{task_id}_RESULT.json"
        if completed_file.exists():
            return {
                "status": "completed",
                "result": json.loads(completed_file.read_text())
            }
        
        # Check pending
        if task_id in self.task_queue:
            return {"status": "pending"}
        
        return {"status": "not_found"}


class WebhookRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhooks."""

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/api/v1/task":
            self.handle_submit_task()
        else:
            self.send_error(404)

    def do_GET(self):
        """Handle GET requests."""
        if self.path.startswith("/api/v1/task/"):
            task_id = self.path.split("/")[-1]
            self.handle_get_status(task_id)
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(404)

    def handle_submit_task(self):
        """Submit new task."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            task_data = json.loads(body.decode("utf-8"))
            
            task_id = self.server.webhook_server.submit_task(task_data)
            
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"status": "accepted", "task_id": task_id, "poll_url": f"/api/v1/task/{task_id}"}
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def handle_get_status(self, task_id: str):
        """Get task status."""
        try:
            status = self.server.webhook_server.get_task_status(task_id)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        """Suppress request logging."""
        pass
