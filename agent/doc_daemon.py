#!/usr/bin/env python3
"""
doc_daemon.py
HDS Document Daemon - Document processing for local AI models.

Provides document operations through microkernel IPC:
- read_doc: Extract text from PDF, DOCX, TXT, MD, HTML
- summarize_doc: Chunk document for AI summarization
- search_doc: Find text patterns in documents
- convert_doc: Convert between formats (md→txt, html→md)
- list_docs: List available documents in workspace

Port: 9004
Authors: HDS Development Team
"""

import sys
import time
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import deque
import logging

agent_path = Path(__file__).parent
sys.path.insert(0, str(agent_path))

from microkernel_ipc import MicrokernelIPCServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocExtractor:
    """Extract text from various document formats."""

    @staticmethod
    def extract(filepath: str) -> Dict[str, Any]:
        """Extract text from file based on extension."""
        path = Path(filepath)
        if not path.exists():
            return {"error": f"File not found: {filepath}", "text": ""}

        ext = path.suffix.lower()
        try:
            if ext in (".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml"):
                return DocExtractor._read_plain(path)
            elif ext == ".pdf":
                return DocExtractor._read_pdf(path)
            elif ext in (".docx", ".doc"):
                return DocExtractor._read_docx(path)
            elif ext in (".html", ".htm"):
                return DocExtractor._read_html(path)
            else:
                return DocExtractor._read_plain(path)
        except Exception as e:
            return {"error": str(e), "text": ""}

    @staticmethod
    def _read_plain(path: Path) -> Dict[str, Any]:
        """Read plain text file."""
        text = path.read_text(encoding="utf-8", errors="replace")
        return {
            "text": text,
            "lines": text.count("\n") + 1,
            "chars": len(text),
            "format": path.suffix
        }

    @staticmethod
    def _read_pdf(path: Path) -> Dict[str, Any]:
        """Read PDF using PyPDF2 or pdfplumber."""
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(str(path))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            text = "\n\n".join(pages)
            return {
                "text": text,
                "pages": len(reader.pages),
                "chars": len(text),
                "format": "pdf"
            }
        except ImportError:
            try:
                import pdfplumber
                with pdfplumber.open(str(path)) as pdf:
                    pages = [p.extract_text() or "" for p in pdf.pages]
                text = "\n\n".join(pages)
                return {
                    "text": text,
                    "pages": len(pdf.pages),
                    "chars": len(text),
                    "format": "pdf"
                }
            except ImportError:
                return {
                    "error": "No PDF library available (install PyPDF2 or pdfplumber)",
                    "text": ""
                }

    @staticmethod
    def _read_docx(path: Path) -> Dict[str, Any]:
        """Read DOCX using python-docx."""
        try:
            import docx
            doc = docx.Document(str(path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)
            return {
                "text": text,
                "paragraphs": len(paragraphs),
                "chars": len(text),
                "format": "docx"
            }
        except ImportError:
            return {
                "error": "python-docx not available (install python-docx)",
                "text": ""
            }

    @staticmethod
    def _read_html(path: Path) -> Dict[str, Any]:
        """Read HTML and strip tags."""
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            """Simple HTML text extractor."""

            def __init__(self):
                super().__init__()
                self.parts = []
                self.skip = False

            def handle_starttag(self, tag, attrs):
                """Skip script/style tags."""
                if tag in ("script", "style"):
                    self.skip = True

            def handle_endtag(self, tag):
                """Resume after script/style."""
                if tag in ("script", "style"):
                    self.skip = False

            def handle_data(self, data):
                """Collect text data."""
                if not self.skip:
                    text = data.strip()
                    if text:
                        self.parts.append(text)

        raw = path.read_text(encoding="utf-8", errors="replace")
        parser = TextExtractor()
        parser.feed(raw)
        text = "\n".join(parser.parts)
        return {
            "text": text,
            "chars": len(text),
            "format": "html"
        }


class DocChunker:
    """Split documents into AI-friendly chunks."""

    @staticmethod
    def chunk(text: str, max_tokens: int = 2000, overlap: int = 200) -> List[Dict[str, Any]]:
        """Split text into chunks respecting paragraph boundaries."""
        # Approximate: 1 token ~ 4 chars
        max_chars = max_tokens * 4
        overlap_chars = overlap * 4

        paragraphs = text.split("\n\n")
        chunks = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) > max_chars and current:
                chunks.append({
                    "index": len(chunks),
                    "text": current.strip(),
                    "chars": len(current),
                    "tokens_est": len(current) // 4
                })
                # Keep overlap from end of current chunk
                current = current[-overlap_chars:] + "\n\n" + para
            else:
                current += "\n\n" + para if current else para

        if current.strip():
            chunks.append({
                "index": len(chunks),
                "text": current.strip(),
                "chars": len(current),
                "tokens_est": len(current) // 4
            })

        return chunks


class DocDaemonServer(MicrokernelIPCServer):
    """
    Document processing daemon for HDS.
    Allows local AI models to read and process documents through IPC.
    """

    def __init__(self, port: int = 9004):
        super().__init__(port, "DocDaemon")
        self.cache = {}  # filepath -> extracted text cache
        self.workspace = agent_path.parent  # HDS_CORE root
        logger.info(f"[DocDaemon] Initialized. Workspace: {self.workspace}")

    def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch document task."""
        task_type = task_data.get("type", "unknown")
        task_id = task_data.get("task_id", "unknown")

        logger.info(f"[DocDaemon] Task {task_id}: {task_type}")

        if task_type == "read_doc":
            return self._read_doc(task_id, task_data)
        elif task_type == "summarize_doc":
            return self._summarize_doc(task_id, task_data)
        elif task_type == "search_doc":
            return self._search_doc(task_id, task_data)
        elif task_type == "convert_doc":
            return self._convert_doc(task_id, task_data)
        elif task_type == "list_docs":
            return self._list_docs(task_id, task_data)
        else:
            return {"status": "error", "error": f"Unknown task type: {task_type}"}

    def _read_doc(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Read and extract text from document."""
        filepath = task_data.get("filepath", "")
        max_chars = task_data.get("max_chars", 50000)

        if not filepath:
            return {"status": "error", "error": "No filepath provided"}

        # Resolve relative paths against workspace
        path = Path(filepath)
        if not path.is_absolute():
            path = self.workspace / filepath

        result = DocExtractor.extract(str(path))

        if result.get("error"):
            return {"status": "error", "error": result["error"]}

        text = result["text"][:max_chars]
        self.cache[str(path)] = text

        return {
            "status": "success",
            "task_id": task_id,
            "filepath": str(path),
            "text": text,
            "truncated": len(result["text"]) > max_chars,
            "metadata": {k: v for k, v in result.items() if k != "text"},
            "timestamp": time.time()
        }

    def _summarize_doc(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Chunk document for AI summarization."""
        filepath = task_data.get("filepath", "")
        max_tokens = task_data.get("max_tokens_per_chunk", 2000)

        path = Path(filepath)
        if not path.is_absolute():
            path = self.workspace / filepath

        # Use cache or extract
        if str(path) in self.cache:
            text = self.cache[str(path)]
        else:
            result = DocExtractor.extract(str(path))
            if result.get("error"):
                return {"status": "error", "error": result["error"]}
            text = result["text"]
            self.cache[str(path)] = text

        chunks = DocChunker.chunk(text, max_tokens=max_tokens)

        return {
            "status": "success",
            "task_id": task_id,
            "filepath": str(path),
            "total_chunks": len(chunks),
            "total_chars": len(text),
            "total_tokens_est": len(text) // 4,
            "chunks": chunks[:20],  # Max 20 chunks in response
            "timestamp": time.time()
        }

    def _search_doc(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Search for pattern in document."""
        filepath = task_data.get("filepath", "")
        pattern = task_data.get("pattern", "")
        case_sensitive = task_data.get("case_sensitive", False)

        if not pattern:
            return {"status": "error", "error": "No search pattern provided"}

        path = Path(filepath)
        if not path.is_absolute():
            path = self.workspace / filepath

        # Use cache or extract
        if str(path) in self.cache:
            text = self.cache[str(path)]
        else:
            result = DocExtractor.extract(str(path))
            if result.get("error"):
                return {"status": "error", "error": result["error"]}
            text = result["text"]
            self.cache[str(path)] = text

        # Search
        flags = 0 if case_sensitive else re.IGNORECASE
        matches = []
        for i, line in enumerate(text.split("\n"), 1):
            if re.search(pattern, line, flags):
                matches.append({"line": i, "text": line.strip()[:200]})
                if len(matches) >= 50:
                    break

        return {
            "status": "success",
            "task_id": task_id,
            "filepath": str(path),
            "pattern": pattern,
            "matches_found": len(matches),
            "matches": matches,
            "timestamp": time.time()
        }

    def _convert_doc(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """Convert document format."""
        filepath = task_data.get("filepath", "")
        target_format = task_data.get("target_format", "txt")

        path = Path(filepath)
        if not path.is_absolute():
            path = self.workspace / filepath

        result = DocExtractor.extract(str(path))
        if result.get("error"):
            return {"status": "error", "error": result["error"]}

        text = result["text"]

        if target_format == "txt":
            output = text
        elif target_format == "md":
            # Basic conversion: add headers for sections
            lines = text.split("\n")
            output_lines = []
            for line in lines:
                if line.isupper() and len(line) > 3:
                    output_lines.append(f"## {line.title()}")
                else:
                    output_lines.append(line)
            output = "\n".join(output_lines)
        else:
            output = text

        # Save converted file
        output_path = path.with_suffix(f".{target_format}")
        output_path.write_text(output, encoding="utf-8")

        return {
            "status": "success",
            "task_id": task_id,
            "source": str(path),
            "output": str(output_path),
            "target_format": target_format,
            "chars": len(output),
            "timestamp": time.time()
        }

    def _list_docs(self, task_id: str, task_data: Dict) -> Dict[str, Any]:
        """List documents in workspace directory."""
        directory = task_data.get("directory", "")
        extensions = task_data.get("extensions", [".pdf", ".docx", ".txt", ".md", ".html"])

        path = Path(directory) if directory else self.workspace
        if not path.is_absolute():
            path = self.workspace / directory

        if not path.exists():
            return {"status": "error", "error": f"Directory not found: {path}"}

        docs = []
        for ext in extensions:
            for f in path.rglob(f"*{ext}"):
                docs.append({
                    "path": str(f.relative_to(self.workspace)),
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "format": ext
                })
                if len(docs) >= 100:
                    break

        docs.sort(key=lambda x: x["name"])

        return {
            "status": "success",
            "task_id": task_id,
            "directory": str(path),
            "documents": docs[:100],
            "total_found": len(docs),
            "timestamp": time.time()
        }


def run_doc_daemon(port: int = 9004):
    """Start document daemon."""
    server = DocDaemonServer(port)
    logger.info(f"[DocDaemon] Starting on port {port}...")
    server.start()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9004
    run_doc_daemon(port)
