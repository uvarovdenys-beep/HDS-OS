"""HTML guard: HTML is markup but an injection surface (regex; not containment)."""
import re

from .. import register
from .._hygiene import deny_scan

_PAT = [
    ("inline event handler", re.compile(r"<[^>]+\son\w+\s*=", re.I)),
    ("javascript: uri", re.compile(r"javascript:", re.I)),
    ("inline <script> with eval", re.compile(
        r"<script[^>]*>[^<]*\beval\s*\(", re.I | re.S)),
]


@register(".html", kind="markup")
def validate_html(content, path):
    deny_scan(content, path, _PAT)
