#!/usr/bin/env python3
"""
orchestrator_index.py
HDS Orchestrator Index — auto-generated module map for AI context efficiency.

Scans all agent/*.py files, extracts class/function docstrings,
and builds a compact INDEX that an AI model reads INSTEAD of
opening every file. This saves 90%+ tokens on codebase navigation.

Integration with auto_decompose:
  When auto_decompose splits a file, it calls rebuild_index()
  so the orchestrator always has an up-to-date map.

Usage:
    # Generate index
    python3 orchestrator_index.py

    # In code
    from orchestrator_index import get_index, get_module_summary
    index = get_index()  # Full map
    summary = get_module_summary("conductor")  # One module
"""

import ast
import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("orchestrator_index")

INDEX_FILE = "ai-mind/orchestrator_index.json"


@dataclass
class SymbolInfo:
    """Info about a class or function."""
    name: str
    kind: str               # "class" or "function"
    docstring: str          # First line of docstring
    lines: int              # Number of lines
    start_line: int
    methods: List[str] = field(default_factory=list)  # For classes: method names + 1-line docs


@dataclass
class ModuleInfo:
    """Info about a Python module."""
    filename: str
    docstring: str          # Module-level docstring (first line)
    total_lines: int
    symbols: List[SymbolInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


def scan_module(filepath: str) -> ModuleInfo:
    """
    Extract module structure from a Python file using AST.
    Returns compact info: module doc, classes, functions, their docs.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    total_lines = len(source.split("\n"))

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return ModuleInfo(
            filename=os.path.basename(filepath),
            docstring=f"SyntaxError: {e}",
            total_lines=total_lines,
        )

    # Module docstring
    mod_doc = ast.get_docstring(tree) or ""
    mod_doc_short = mod_doc.strip().split("\n")[0][:120] if mod_doc else ""

    # Imports
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    # Classes and functions
    symbols = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            doc_short = doc.strip().split("\n")[0][:100] if doc else ""
            size = node.end_lineno - node.lineno + 1

            # Extract method names with their 1-line docs
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_doc = ast.get_docstring(item) or ""
                    m_doc_short = m_doc.strip().split("\n")[0][:80] if m_doc else ""
                    if item.name.startswith("_") and item.name != "__init__":
                        continue  # Skip private methods in index
                    methods.append(f"{item.name}(): {m_doc_short}" if m_doc_short else item.name + "()")

            symbols.append(SymbolInfo(
                name=node.name,
                kind="class",
                docstring=doc_short,
                lines=size,
                start_line=node.lineno,
                methods=methods,
            ))

        elif isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node) or ""
            doc_short = doc.strip().split("\n")[0][:100] if doc else ""
            size = node.end_lineno - node.lineno + 1

            if node.name.startswith("_"):
                continue  # Skip private functions

            symbols.append(SymbolInfo(
                name=node.name,
                kind="function",
                docstring=doc_short,
                lines=size,
                start_line=node.lineno,
            ))

    return ModuleInfo(
        filename=os.path.basename(filepath),
        docstring=mod_doc_short,
        total_lines=total_lines,
        symbols=symbols,
        imports=imports,
    )


def build_index(agent_dir: str = ".") -> Dict:
    """
    Scan all .py files in agent/ and build the orchestrator index.
    Returns a dict ready to serialize to JSON.
    """
    modules = []

    for fname in sorted(os.listdir(agent_dir)):
        if not fname.endswith(".py"):
            continue
        if fname.startswith("__"):
            continue

        filepath = os.path.join(agent_dir, fname)
        info = scan_module(filepath)

        mod_entry = {
            "file": info.filename,
            "doc": info.docstring,
            "lines": info.total_lines,
            "symbols": [],
        }

        for sym in info.symbols:
            sym_entry = {
                "name": sym.name,
                "kind": sym.kind,
                "doc": sym.docstring,
                "lines": sym.lines,
            }
            if sym.methods:
                sym_entry["methods"] = sym.methods
            mod_entry["symbols"].append(sym_entry)

        modules.append(mod_entry)

    index = {
        "version": "1.1.0",
        "generated": datetime.now().isoformat(),
        "total_modules": len(modules),
        "total_lines": sum(m["lines"] for m in modules),
        "modules": modules,
    }

    return index


def save_index(index: Dict, output_path: str = INDEX_FILE):
    """Save index to JSON file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    logger.info(f"Index saved: {output_path}")


def rebuild_index(agent_dir: str = "."):
    """Rebuild and save the orchestrator index. Call after any file changes."""
    index = build_index(agent_dir)
    save_index(index)
    return index


def get_index(index_path: str = INDEX_FILE) -> Optional[Dict]:
    """Load the cached orchestrator index."""
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def get_module_summary(module_name: str, index_path: str = INDEX_FILE) -> Optional[str]:
    """Get a human-readable summary of one module."""
    index = get_index(index_path)
    if not index:
        return None

    fname = f"{module_name}.py" if not module_name.endswith(".py") else module_name

    for mod in index["modules"]:
        if mod["file"] == fname:
            lines = [f"## {mod['file']} ({mod['lines']} lines)", f"{mod['doc']}", ""]
            for sym in mod["symbols"]:
                prefix = "class" if sym["kind"] == "class" else "def"
                lines.append(f"  {prefix} {sym['name']} ({sym['lines']}L): {sym['doc']}")
                if "methods" in sym:
                    for m in sym["methods"][:10]:
                        lines.append(f"    .{m}")
            return "\n".join(lines)

    return None


def print_compact_index(index: Dict):
    """Print a compact human-readable index to stdout."""
    print(f"HDS Orchestrator Index v{index['version']}")
    print(f"Generated: {index['generated']}")
    print(f"Modules: {index['total_modules']} | Total lines: {index['total_lines']}")
    print("=" * 70)

    for mod in index["modules"]:
        sym_count = len(mod["symbols"])
        if sym_count == 0:
            continue
        print(f"\n{mod['file']:35s} {mod['lines']:>5}L  {mod['doc'][:50]}")
        for sym in mod["symbols"]:
            prefix = "C" if sym["kind"] == "class" else "F"
            print(f"  [{prefix}] {sym['name']:30s} {sym['lines']:>4}L  {sym['doc'][:45]}")
            if "methods" in sym:
                for m in sym["methods"][:5]:
                    print(f"       .{m[:60]}")
                if len(sym["methods"]) > 5:
                    print(f"       ... +{len(sym['methods'])-5} more methods")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="HDS Orchestrator Index Generator")
    parser.add_argument("--dir", default=".", help="Agent directory to scan")
    parser.add_argument("--output", default=INDEX_FILE, help="Output JSON path")
    parser.add_argument("--module", default="", help="Show summary for one module")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.module:
        summary = get_module_summary(args.module, args.output)
        if summary:
            print(summary)
        else:
            print(f"Module '{args.module}' not found in index")
    else:
        index = build_index(args.dir)
        save_index(index, args.output)
        if args.json:
            print(json.dumps(index, indent=2))
        else:
            print_compact_index(index)
