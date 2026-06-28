"""SVG guard: SVG is markup but allows <script> — same injection surface as HTML."""
import re
from .. import register
from .._hygiene import deny_scan

_PAT = [
    ("inline event handler", re.compile(r"<[^>]+\son\w+\s*=", re.I)),
    ("javascript: uri",       re.compile(r"javascript:", re.I)),
    ("inline <script> with eval", re.compile(
        r"<script[^>]*>[^<]*\beval\s*\(", re.I | re.S)),
]


@register(".svg", ".svgz", kind="markup")
def validate_svg(content, path):
    deny_scan(content, path, _PAT)
