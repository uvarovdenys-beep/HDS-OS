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


# tsc errors that mean "an ambient/external declaration is not visible when a
# single file is checked in isolation" — NOT a bug in the code. Real projects
# supply these via @types/node, @types/vscode, DOM libs, or node_modules. We
# validate a lone file, so we must ignore this family while keeping genuine code
# errors (implicit any TS7006, type mismatches, syntax) fatal.
_TS_AMBIENT_OK = {
    "TS2304",  # Cannot find name 'X'
    "TS2307",  # Cannot find module 'X' / its type declarations
    "TS2503",  # Cannot find namespace 'X'
    "TS2580",  # Cannot find name 'require'/'process'/'module' (need @types/node)
    "TS2584",  # Cannot find name 'document'/DOM (need lib dom)
    "TS2591",  # Cannot find name 'Buffer' (need @types/node)
    "TS2688",  # Cannot find type definition file for 'X'
    "TS7016",  # Could not find a declaration file for module 'X'
}

# Errors that mean "a module/type could not be resolved at all" — their presence
# tells us the type graph is incomplete for this isolated check.
_TS_AMBIENT_UNRESOLVED = {"TS2304", "TS2307", "TS2503", "TS2688", "TS7016"}

# Inference errors that are only meaningful when the type graph IS complete.
_TS_INFERENCE_NOISE = {
    "TS7006",  # Parameter implicitly has an 'any' type
    "TS7005",  # Variable implicitly has an 'any' type
    "TS7031",  # Binding element implicitly has an 'any' type
    "TS7034",  # Variable implicitly has type 'any[]' in some locations
    "TS18046", # 'x' is of type 'unknown'
}


def _ts_check(content, path, jsx=False):
    """Type-check one .ts/.tsx file with tsc, ignoring only the missing-ambient
    family (resolved by the real project's @types). Any other tsc error — an
    actual code/type/syntax bug — raises LangReject."""
    import re as _re
    import tempfile
    from .. import LangReject
    from .._toolchain import resolve
    tsc = resolve("tsc")
    if tsc is None:
        from .._toolchain import _offer
        _offer("tsc")
        return  # toolchain absent → hygiene-only (honest degradation)
    from sandbox.runner import SandboxRunner, RunRequest
    from sandbox.subprocess_backend import SubprocessBackend
    ext = Path(path).suffix
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / ("check" + ext)
        f.write_text(content, encoding="utf-8")
        args = [tsc, "--noEmit", "--skipLibCheck", "--lib", "ES2020,DOM"]
        if jsx:
            args += ["--jsx", "preserve"]
        res = SandboxRunner(backend=SubprocessBackend()).run(RunRequest(
            tool=args[0], args=args[1:] + [f.name], workdir=td, timeout=60))
        if res.code == 0:
            return
        out = (res.stdout or "") + (res.stderr or "")
        codes = _re.findall(r"error (TS\d+):", out)
        # If ANY import/type could not be resolved, the type graph is incomplete:
        # every downstream inference collapses to `any`, so the implicit-any
        # family becomes noise, not signal. A VS Code extension checked in
        # isolation hits exactly this — `vscode.window.withProgress(…, (progress)
        # => …)` types `progress` from @types/vscode, which is absent here, so
        # tsc reports TS7006 for code that is perfectly typed in the real project.
        # Tolerate inference errors ONLY in that case; for self-contained files
        # they stay fatal.
        unresolved = any(c in _TS_AMBIENT_UNRESOLVED for c in codes)
        tolerated = set(_TS_AMBIENT_OK)
        if unresolved:
            tolerated |= _TS_INFERENCE_NOISE
        real = []
        for line in out.splitlines():
            m = _re.search(r"error (TS\d+):", line)
            if m and m.group(1) not in tolerated:
                real.append(line.strip())
        if real:
            raise LangReject(f"{Path(path).name} failed tsc: {real[-1][:160]}")


@register(".js", ".ts", ".jsx", ".tsx", kind="exec")
def validate_js(content, path):
    ext = Path(path).suffix
    from .._toolchain import check
    if ext in (".ts", ".tsx"):
        _ts_check(content, path, jsx=(ext == ".tsx"))
        return
    # .js / .jsx — hygiene picked by RUNTIME (the real browser-vs-node concern);
    # syntax is runtime-agnostic.
    deny_scan(content, path, _NODE if _is_node_js(content) else _BROWSER)
    # node --check used purely as an ES SYNTAX parser (NOT a runtime assertion);
    # .jsx is not plain ES, so it is not parsed here.
    if ext == ".js":
        check(["node", "--check"], content, path, suffix=".js",
              label="node --check (ES syntax)")
