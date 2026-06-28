#!/usr/bin/env python3
"""
browser_utils.py
HDS Browser Utilities - Web automation helpers
"""

import logging
import re
from typing import Dict, Any, Optional
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


class HTMLToMarkdownParser(HTMLParser):
    """Convert HTML to markdown format."""

    def __init__(self):
        super().__init__()
        self.markdown = []
        self.skip_next = False

    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.skip_next = True
        elif tag == 'h1':
            self.markdown.append('\n# ')
        elif tag == 'h2':
            self.markdown.append('\n## ')
        elif tag == 'h3':
            self.markdown.append('\n### ')
        elif tag == 'p':
            self.markdown.append('\n')
        elif tag == 'br':
            self.markdown.append('\n')
        elif tag == 'strong' or tag == 'b':
            self.markdown.append('**')
        elif tag == 'em' or tag == 'i':
            self.markdown.append('*')
        elif tag == 'a':
            self.markdown.append('[')
        elif tag == 'li':
            self.markdown.append('\n- ')

    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.skip_next = False
        elif tag in ['strong', 'b']:
            self.markdown.append('**')
        elif tag in ['em', 'i']:
            self.markdown.append('*')
        elif tag == 'a':
            self.markdown.append(']')
        elif tag == 'p':
            self.markdown.append('\n')

    def handle_data(self, data):
        if not self.skip_next:
            text = data.strip()
            if text:
                self.markdown.append(text + ' ')

    def get_markdown(self):
        return ''.join(self.markdown).strip()


class BrowserUtils:
    """Browser automation utilities."""

    @staticmethod
    def html_to_markdown(html: str) -> str:
        """Convert HTML to markdown."""
        try:
            parser = HTMLToMarkdownParser()
            parser.feed(html)
            markdown = parser.get_markdown()

            # Clean up excessive whitespace
            markdown = re.sub(r'\n\s*\n', '\n\n', markdown)
            markdown = re.sub(r' +', ' ', markdown)

            return markdown[:5000]  # Limit to 5000 chars
        except Exception as e:
            logger.error(f"HTML conversion failed: {e}")
            return "Failed to convert HTML"

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count (rough approximation)."""
        # Average: 1 token ≈ 4 characters
        return len(text) // 4

    @staticmethod
    def calculate_savings(html: str, markdown: str) -> Dict[str, Any]:
        """Calculate token savings from HTML to markdown conversion."""
        html_tokens = BrowserUtils.estimate_tokens(html)
        markdown_tokens = BrowserUtils.estimate_tokens(markdown)
        savings = html_tokens - markdown_tokens
        savings_percent = (savings / html_tokens * 100) if html_tokens > 0 else 0

        return {
            "original_tokens": html_tokens,
            "markdown_tokens": markdown_tokens,
            "savings": savings,
            "savings_percent": round(savings_percent, 2)
        }

    @staticmethod
    def clean_selector(selector: str) -> str:
        """Validate and clean CSS selector."""
        selector = selector.strip()
        if not selector:
            raise ValueError("Empty selector")
        return selector

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from URL."""
        import re
        match = re.search(r'https?://([^/]+)', url)
        return match.group(1) if match else "unknown"
