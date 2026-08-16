#!/usr/bin/env python3
"""
web_search_daemon.py
HDS Web Search Daemon — internet search and fact verification for local AI models.

Allows local AI models (qwen, deepseek, llama, etc.) to search the web,
fetch page content, and verify their own outputs against real data.

Task types:
  - search:       Run a web search query, return top results
  - fetch_page:   Fetch a URL and extract clean text (markdown)
  - verify_fact:  Search for a claim and return evidence (supports/contradicts)

Integration:
  - Runs as microkernel daemon on port 9003
  - Agent sends tasks via IPC (same as vision/browser daemons)
  - Results injected into AI prompt as grounding context

Anti-hallucination flow:
  1. AI generates answer
  2. Agent extracts key claims
  3. verify_fact checks each claim against web
  4. If contradiction found → re-prompt AI with evidence

Dependencies:
  duckduckgo-search>=7.0.0   # No API key needed
  requests>=2.28.0            # Page fetching
  beautifulsoup4>=4.11.0      # HTML parsing

Port: 9003 (configurable via WEB_SEARCH_PORT env var)

Authors: HDS Development Team
License: HDS Standard
"""

import os
import re
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("web_search_daemon")

DEFAULT_PORT = int(os.environ.get("WEB_SEARCH_PORT", "9003"))
MAX_RESULTS = 8
MAX_PAGE_CHARS = 5000
FETCH_TIMEOUT = 10


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    source: str = ""


@dataclass
class FactCheck:
    """Result of fact verification against web sources."""
    claim: str
    verdict: str          # "supported", "contradicted", "uncertain"
    confidence: float     # 0.0–1.0
    evidence: List[Dict] = field(default_factory=list)
    sources_checked: int = 0


def _safe_import_duckduckgo():
    """Import duckduckgo_search with graceful fallback."""
    try:
        from duckduckgo_search import DDGS
        return DDGS
    except ImportError:
        logger.error("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return None


def _safe_import_requests():
    """Import requests with graceful fallback."""
    try:
        import requests
        return requests
    except ImportError:
        logger.error("requests not installed. Run: pip install requests")
        return None


def _safe_import_bs4():
    """Import BeautifulSoup with graceful fallback."""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 not installed. Run: pip install beautifulsoup4")
        return None


def web_search(query: str, max_results: int = MAX_RESULTS, region: str = "wt-wt") -> List[SearchResult]:
    """
    Search the web using DuckDuckGo. No API key required.

    Args:
        query: Search query string
        max_results: Maximum number of results (default 8)
        region: Region code (default "wt-wt" = worldwide)

    Returns:
        List of SearchResult objects
    """
    DDGS = _safe_import_duckduckgo()
    if not DDGS:
        return []

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results, region=region):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", r.get("link", "")),
                    snippet=r.get("body", r.get("snippet", "")),
                    source=r.get("source", ""),
                ))
    except Exception as e:
        logger.error(f"Search failed: {e}")

    return results


def fetch_page_text(url: str, max_chars: int = MAX_PAGE_CHARS) -> Dict:
    """
    Fetch a URL and extract clean text content.

    Strips scripts, styles, nav elements. Returns plain text
    truncated to max_chars for token efficiency.

    Args:
        url: URL to fetch
        max_chars: Maximum characters to return (default 5000)

    Returns:
        Dict with keys: text, title, url, char_count, truncated
    """
    requests = _safe_import_requests()
    BeautifulSoup = _safe_import_bs4()
    if not requests or not BeautifulSoup:
        return {"error": "Missing dependencies", "url": url}

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (HDS WebSearch/1.1; Research Bot)",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Extract text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + "\n\n[...truncated]"

        return {
            "text": text,
            "title": title,
            "url": url,
            "char_count": len(text),
            "truncated": truncated,
        }

    except Exception as e:
        logger.error(f"Fetch failed for {url}: {e}")
        return {"error": str(e), "url": url}


def verify_fact(claim: str, max_sources: int = 5) -> FactCheck:
    """
    Verify a factual claim against web sources.

    Searches for the claim, analyzes snippets for agreement/contradiction.
    Uses keyword overlap scoring — not AI-based (keeps it fast and free).

    Args:
        claim: The factual claim to verify
        max_sources: How many sources to check (default 5)

    Returns:
        FactCheck with verdict and evidence
    """
    # Search for the claim directly
    results = web_search(claim, max_results=max_sources)
    if not results:
        return FactCheck(
            claim=claim,
            verdict="uncertain",
            confidence=0.0,
            sources_checked=0,
        )

    # Extract key terms from claim (words 4+ chars, lowered)
    claim_terms = set(
        w.lower() for w in re.findall(r'\b\w{4,}\b', claim)
    )

    evidence = []
    support_score = 0
    contradict_score = 0

    # Contradiction signals
    contradict_signals = [
        "not true", "false", "incorrect", "myth", "debunked",
        "misleading", "inaccurate", "wrong", "no evidence",
        "contrary", "disproven", "hoax", "fake",
    ]

    # Support signals
    support_signals = [
        "confirmed", "verified", "according to", "research shows",
        "study found", "evidence suggests", "data shows",
        "scientists found", "report confirms",
    ]

    for r in results:
        snippet_lower = r.snippet.lower()

        # Count claim term overlap
        snippet_terms = set(re.findall(r'\b\w{4,}\b', snippet_lower))
        overlap = len(claim_terms & snippet_terms)
        relevance = overlap / max(len(claim_terms), 1)

        # Skip low-relevance results
        if relevance < 0.2:
            continue

        # Check for contradiction/support signals
        has_contradict = any(s in snippet_lower for s in contradict_signals)
        has_support = any(s in snippet_lower for s in support_signals)

        stance = "neutral"
        if has_contradict:
            contradict_score += relevance
            stance = "contradicts"
        elif has_support:
            support_score += relevance
            stance = "supports"
        else:
            support_score += relevance * 0.3  # Weak implicit support

        evidence.append({
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet[:200],
            "stance": stance,
            "relevance": round(relevance, 2),
        })

    # Determine verdict
    total = support_score + contradict_score
    if total == 0:
        verdict = "uncertain"
        confidence = 0.0
    elif support_score > contradict_score * 1.5:
        verdict = "supported"
        confidence = min(support_score / max(total, 1), 1.0)
    elif contradict_score > support_score * 1.5:
        verdict = "contradicted"
        confidence = min(contradict_score / max(total, 1), 1.0)
    else:
        verdict = "uncertain"
        confidence = 0.3

    return FactCheck(
        claim=claim,
        verdict=verdict,
        confidence=round(confidence, 2),
        evidence=evidence,
        sources_checked=len(results),
    )


def format_search_for_prompt(results: List[SearchResult], max_results: int = 5) -> str:
    """
    Format search results for injection into AI prompt.

    Compact format optimized for token efficiency.

    Args:
        results: List of SearchResult
        max_results: Max results to include

    Returns:
        Formatted string ready for prompt injection
    """
    if not results:
        return "[No web results found]"

    lines = ["[Web Search Results]"]
    for i, r in enumerate(results[:max_results], 1):
        lines.append(f"{i}. {r.title}")
        lines.append(f"   {r.snippet[:150]}")
        lines.append(f"   Source: {r.url}")
    return "\n".join(lines)


def format_factcheck_for_prompt(fc: FactCheck) -> str:
    """
    Format fact-check result for injection into AI prompt.

    Args:
        fc: FactCheck result

    Returns:
        Formatted string for prompt
    """
    lines = [
        f"[Fact Check: {fc.verdict.upper()}]",
        f"Claim: {fc.claim}",
        f"Confidence: {fc.confidence}",
        f"Sources checked: {fc.sources_checked}",
    ]
    for e in fc.evidence[:3]:
        lines.append(f"  - [{e['stance']}] {e['title'][:80]}")
        lines.append(f"    {e['snippet'][:120]}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# MICROKERNEL DAEMON SERVER
# ──────────────────────────────────────────────────────────────

class WebSearchDaemonServer:
    """
    Web Search Daemon for HDS microkernel architecture.

    Runs on port 9003, accepts tasks via HTTP POST /execute.
    Provides search, fetch, and fact-verification capabilities
    to the agent and local AI models.

    Task types:
        search:      {"type": "search", "query": "...", "max_results": 5}
        fetch_page:  {"type": "fetch_page", "url": "...", "max_chars": 5000}
        verify_fact: {"type": "verify_fact", "claim": "...", "max_sources": 5}
    """

    def __init__(self, port: int = DEFAULT_PORT):
        """Initialize web search daemon."""
        self.port = port
        self.stats = {
            "searches": 0,
            "fetches": 0,
            "verifications": 0,
            "errors": 0,
            "started": datetime.now().isoformat(),
        }

    def execute_task(self, task_data: Dict) -> Dict:
        """
        Dispatch task to appropriate handler.

        Args:
            task_data: Dict with 'type' and type-specific params

        Returns:
            Dict with results or error
        """
        task_type = task_data.get("type", "")
        task_id = task_data.get("task_id", "UNKNOWN")

        try:
            if task_type == "search":
                return self._handle_search(task_id, task_data)
            elif task_type == "fetch_page":
                return self._handle_fetch(task_id, task_data)
            elif task_type == "verify_fact":
                return self._handle_verify(task_id, task_data)
            else:
                return {"error": f"Unknown task type: {task_type}"}
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Task {task_id} failed: {e}")
            return {"error": str(e), "task_id": task_id}

    def _handle_search(self, task_id: str, data: Dict) -> Dict:
        """Handle search task."""
        query = data.get("query", "")
        max_results = data.get("max_results", MAX_RESULTS)

        if not query:
            return {"error": "No query provided"}

        start = time.time()
        results = web_search(query, max_results=max_results)
        duration = time.time() - start

        self.stats["searches"] += 1

        return {
            "task_id": task_id,
            "type": "search",
            "query": query,
            "results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet}
                for r in results
            ],
            "count": len(results),
            "duration_seconds": round(duration, 2),
            "prompt_text": format_search_for_prompt(results),
        }

    def _handle_fetch(self, task_id: str, data: Dict) -> Dict:
        """Handle page fetch task."""
        url = data.get("url", "")
        max_chars = data.get("max_chars", MAX_PAGE_CHARS)

        if not url:
            return {"error": "No URL provided"}

        start = time.time()
        result = fetch_page_text(url, max_chars=max_chars)
        duration = time.time() - start

        self.stats["fetches"] += 1
        result["task_id"] = task_id
        result["type"] = "fetch_page"
        result["duration_seconds"] = round(duration, 2)
        return result

    def _handle_verify(self, task_id: str, data: Dict) -> Dict:
        """Handle fact verification task."""
        claim = data.get("claim", "")
        max_sources = data.get("max_sources", 5)

        if not claim:
            return {"error": "No claim provided"}

        start = time.time()
        fc = verify_fact(claim, max_sources=max_sources)
        duration = time.time() - start

        self.stats["verifications"] += 1

        return {
            "task_id": task_id,
            "type": "verify_fact",
            "claim": fc.claim,
            "verdict": fc.verdict,
            "confidence": fc.confidence,
            "evidence": fc.evidence,
            "sources_checked": fc.sources_checked,
            "duration_seconds": round(duration, 2),
            "prompt_text": format_factcheck_for_prompt(fc),
        }

    def get_stats(self) -> Dict:
        """Daemon statistics."""
        return self.stats

    def start(self):
        """Start the daemon HTTP server."""
        from microkernel_ipc import MicrokernelIPCServer

        class _Server(MicrokernelIPCServer):
            def __init__(inner_self, daemon_instance):
                super().__init__("web_search", self.port)
                inner_self.daemon = daemon_instance

            def execute_task(inner_self, task_data):
                return inner_self.daemon.execute_task(task_data)

            def get_stats(inner_self):
                return inner_self.daemon.get_stats()

        server = _Server(self)
        logger.info(f"Web Search Daemon starting on port {self.port}")
        server.start()


def run_web_search_daemon():
    """Start web search daemon."""
    daemon = WebSearchDaemonServer()
    daemon.start()


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="HDS Web Search Daemon")
    parser.add_argument("--search", type=str, help="Run a web search")
    parser.add_argument("--fetch", type=str, help="Fetch page text from URL")
    parser.add_argument("--verify", type=str, help="Verify a factual claim")
    parser.add_argument("--daemon", action="store_true", help="Start as daemon on port 9003")
    parser.add_argument("--max", type=int, default=5, help="Max results (default 5)")
    args = parser.parse_args()

    if args.daemon:
        run_web_search_daemon()
    elif args.search:
        results = web_search(args.search, max_results=args.max)
        for r in results:
            print(f"  {r.title}")
            print(f"  {r.snippet[:120]}")
            print(f"  {r.url}\n")
    elif args.fetch:
        result = fetch_page_text(args.fetch)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Title: {result['title']}")
            print(f"Chars: {result['char_count']}")
            print(f"\n{result['text'][:500]}")
    elif args.verify:
        fc = verify_fact(args.verify, max_sources=args.max)
        print(format_factcheck_for_prompt(fc))
    else:
        parser.print_help()
