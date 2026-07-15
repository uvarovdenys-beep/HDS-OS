"""Parser-based markup guard for HTML/SVG (upgrade from regex deny_scan).

Uses stdlib html.parser: entities are decoded before inspection, so
obfuscations that beat a regex (&#106;avascript:, &#x65;val, split-tag
tricks) are seen in their decoded form. Still hygiene, not containment —
true containment for markup is rendering in a sandboxed viewer — but the
bar is now a parser, not a pattern.

Policy (same as before, enforced structurally):
  - any attribute named on* (onclick, onload, onmouseover ...)  → DENY
  - javascript:/vbscript: URI in any URI-bearing attribute       → DENY
  - data:text/html URI                                           → DENY
  - <script> whose body contains eval / Function( / import(     → DENY
  - SVG animation retargeting events: <set>/<animate*> with
    attributeName="on*"                                          → DENY
  - <foreignObject> in SVG (smuggles arbitrary HTML)             → DENY (svg only)
"""
import html
import re
from html.parser import HTMLParser

from . import LangReject

_URI_ATTRS = {"href", "src", "xlink:href", "action", "formaction", "data"}
_SCRIPT_BODY_DENY = re.compile(r"\beval\s*\(|\bFunction\s*\(|\bimport\s*\(", re.I)
_URI_SCHEME_DENY = re.compile(r"^\s*(javascript|vbscript)\s*:", re.I)
_DATA_HTML = re.compile(r"^\s*data\s*:\s*text/html", re.I)
_ANIM_TAGS = {"set", "animate", "animatemotion", "animatetransform"}


class _Guard(HTMLParser):
    def __init__(self, path, svg_mode):
        super().__init__(convert_charrefs=True)  # decode entities for us
        self.path = path
        self.svg_mode = svg_mode
        self._in_script = False
        self._script_body = []

    def _deny(self, label):
        raise LangReject(f"'{self.path.name}' hygiene-blocked: {label}")

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "script":
            self._in_script = True
            self._script_body = []
        if self.svg_mode and tag == "foreignobject":
            self._deny("<foreignObject> (embeds arbitrary HTML)")
        for name, value in attrs:
            name = name.lower()
            value = html.unescape(value or "")
            if name.startswith("on"):
                self._deny(f"inline event handler ({name})")
            if name in _URI_ATTRS:
                if _URI_SCHEME_DENY.search(value):
                    self._deny(f"script uri in {name}")
                if _DATA_HTML.search(value):
                    self._deny(f"data:text/html uri in {name}")
            if tag in _ANIM_TAGS and name == "attributename" \
                    and value.strip().lower().startswith("on"):
                self._deny(f"<{tag}> retargets event attribute '{value}'")

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            body = "".join(self._script_body)
            if _SCRIPT_BODY_DENY.search(body):
                self._deny("inline <script> with eval/Function/import(")
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self._script_body.append(data)


def scan_markup(content, path, svg_mode=False):
    """Parse and deny dangerous constructs. Raises LangReject."""
    guard = _Guard(path, svg_mode)
    try:
        guard.feed(content)
        guard.close()
    except LangReject:
        raise
    except Exception as e:
        # A file the parser cannot walk cannot be verified → fail closed.
        raise LangReject(f"'{path.name}' unparseable markup: {e}")
    # Unclosed <script> at EOF — check the buffered body anyway.
    if guard._in_script and _SCRIPT_BODY_DENY.search("".join(guard._script_body)):
        raise LangReject(
            f"'{path.name}' hygiene-blocked: inline <script> with eval/Function/import(")
