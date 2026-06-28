"""JS/TS validator — BROWSER JS and NODE JS are different runtimes.

Browser JS (client / HTML <script> / web-product .js) and Node JS (server) have
different dangers AND different syntax tools:
  * Browser: DOM/XSS — eval, new Function, `.innerHTML =`, document.write,
    javascript:. `child_process` is irrelevant; `node --check` is the WRONG tool
    (a Node parser, not a browser one). No browser JS parser is installed, so
    browser JS gets hygiene only (honest — never a Node check on browser code).
  * Node: child_process/eval + `node --check` as the correct ES syntax gate.
  * TS/TSX: tsc (its own checker).
A plain .js is classified by markers; ambiguous → treated as browser (safe).
"""
import re
from pathlib import Path

from .. import register
from .._hygiene import deny_scan

_BROWSER = [
    ("eval()", re.compile(r"\beval\s*\(")),
    ("Function constructor", re.compile(r"\bnew\s+Function\s*\(")),
    ("innerHTML assignment", re.compile(r"\.innerHTML\s*=")),
    ("document.write", re.compile(r"document\s*\.\s*write")),
    ("javascript: uri", re.compile(r"javascript:", re.I)),
]
_NODE = [
    ("eval()", re.compile(r"\beval\s*\(")),
    ("Function constructor", re.compile(r"\bnew\s+Function\s*\(")),
    ("child_process", re.compile(r"child_process")),
]

_NODE_MARK = re.compile(r"\brequire\s*\(|\bmodule\.exports\b|\bprocess\."
                        r"|\b__dirname\b|\bchild_process\b")
_BROWSER_MARK = re.compile(r"\bdocument\b|\bwindow\b|\.innerHTML\b|\bfetch\s*\(")


def _is_node_js(content):
    return bool(_NODE_MARK.search(content)) and not _BROWSER_MARK.search(content)


@register(".js", ".ts", ".jsx", ".tsx", kind="exec")
def validate_js(content, path):
    ext = Path(path).suffix
    from .._toolchain import check
    if ext in (".ts", ".tsx"):
        args = ["tsc", "--noEmit", "--skipLibCheck"]
        if ext == ".tsx":
            args += ["--jsx", "preserve"]
        check(args, content, path, suffix=ext, label="tsc --noEmit")
        return
    # .js / .jsx — hygiene picked by RUNTIME (the real browser-vs-node concern);
    # syntax is runtime-agnostic.
    deny_scan(content, path, _NODE if _is_node_js(content) else _BROWSER)
    # node --check used purely as an ES SYNTAX parser (NOT a runtime assertion);
    # .jsx is not plain ES, so it is not parsed here.
    if ext == ".js":
        check(["node", "--check"], content, path, suffix=".js",
              label="node --check (ES syntax)")
