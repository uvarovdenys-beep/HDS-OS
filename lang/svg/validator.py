"""SVG guard: parser-based — <script>, event handlers, foreignObject, SMIL retargeting."""
from .. import register
from .._markup import scan_markup


@register(".svg", ".svgz", kind="markup")
def validate_svg(content, path):
    scan_markup(content, path, svg_mode=True)
