"""HTML guard: parser-based (entities decoded before inspection; not containment)."""
from .. import register
from .._markup import scan_markup


@register(".html", ".htm", kind="markup")
def validate_html(content, path):
    scan_markup(content, path, svg_mode=False)
