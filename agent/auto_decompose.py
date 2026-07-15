#!/usr/bin/env python3
"""
auto_decompose.py
HDS Auto-Decomposer — AST-based automatic file splitting.

When a model (especially L/XL) creates files that exceed line limits,
the Auto-Decomposer automatically splits large classes/functions into
separate modules, preserving imports and adding proper re-imports.

Integrates with ProtocolEnforcer:
  - S: max 50 lines → if output > 50, auto-decompose
  - M: max 200 lines → if output > 200, auto-decompose
  - L: max 500 lines → if output > 500, auto-decompose
  - XL: no limit, but can run manually

Also supports:
  - Versioned backups before any change (archive/)
  - Rollback to previous version
  - Dry-run mode (show what would be extracted)

Based on original concept from UAIT_PAN project.

Authors: HDS Development Team
License: HDS Standard
"""

import ast
import os
import shutil
import sys
import glob
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("auto_decompose")


@dataclass
class ExtractionResult:
    """Result of extracting a structure from a file."""
    node_name: str
    node_type: str          # "ClassDef" or "FunctionDef"
    original_lines: int     # How many lines it was
    new_file: str           # Path to the new module file
    import_statement: str   # The import line added to original


@dataclass
class DecomposeReport:
    """Full report of a decomposition operation."""
    source_file: str
    backup_path: str
    extracted: List[ExtractionResult] = field(default_factory=list)
    total_lines_before: int = 0
    total_lines_after: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    dry_run: bool = False


def rollback(filepath: str) -> bool:
    """
    Rollback a file to its most recent backup.

    Backups are stored in archive/ directory next to the file,
    named: back_{timestamp}_{filename}

    Returns True if rollback succeeded.
    """
    archive_dir = os.path.join(os.path.dirname(filepath) or ".", "archive")
    base_name = os.path.basename(filepath)
    pattern = os.path.join(archive_dir, f"back_*_{base_name}")
    existing = glob.glob(pattern)

    if not existing:
        logger.warning(f"No backups available for rollback: {filepath}")
        return False

    # Sort by filename (contains timestamp) — newest first
    existing.sort(reverse=True)
    latest_file = existing[0]

    shutil.copy2(latest_file, filepath)
    logger.info(f"Rollback successful: restored from {os.path.basename(latest_file)}")
    os.remove(latest_file)
    return True


def analyze_file(filepath: str, max_lines: int = 200) -> List[Dict]:
    """
    Analyze a Python file and find structures exceeding max_lines.

    Returns list of dicts with info about large structures.
    Does NOT modify anything — safe for inspection.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    large_nodes = []

    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            size = node.end_lineno - node.lineno + 1
            if size > max_lines:
                docstring = ast.get_docstring(node) or ""
                short_doc = docstring.strip().split("\n")[0][:80] if docstring else ""
                large_nodes.append({
                    "name": node.name,
                    "type": type(node).__name__,
                    "lines": size,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "docstring": short_doc,
                })

    return large_nodes


def decompose_python_file(
    filepath: str,
    out_dir: str = "core",
    max_lines: int = 200,
    dry_run: bool = False,
) -> DecomposeReport:
    """
    Automatically split large classes/functions into separate module files.

    Process:
    1. Parse the file with AST
    2. Collect all imports
    3. Find structures (classes/functions) exceeding max_lines
    4. For each: extract to out_dir/{name}.py with imports
    5. Replace original code with import statement
    6. Save versioned backup before modifying

    Args:
        filepath: Path to the Python file to decompose
        out_dir: Directory for extracted modules (relative to file's dir)
        max_lines: Threshold — structures larger than this get extracted
        dry_run: If True, only analyze without modifying files

    Returns:
        DecomposeReport with all extraction details
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    lines = source.split("\n")
    tree = ast.parse(source)
    report = DecomposeReport(
        source_file=filepath,
        backup_path="",
        total_lines_before=len(lines),
        dry_run=dry_run,
    )

    # 1. Collect all imports for transfer to new files
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.extend(lines[node.lineno - 1 : node.end_lineno])

    # 2. Find large structures (classes or functions)
    extract_nodes = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            size = node.end_lineno - node.lineno + 1
            if size > max_lines:
                extract_nodes.append(node)

    if not extract_nodes:
        logger.info(f"No structures exceeding {max_lines} lines found in {filepath}")
        report.total_lines_after = len(lines)
        return report

    if dry_run:
        for node in extract_nodes:
            size = node.end_lineno - node.lineno + 1
            result = ExtractionResult(
                node_name=node.name,
                node_type=type(node).__name__,
                original_lines=size,
                new_file=f"{out_dir}/{node.name.lower()}.py",
                import_statement=f"from {os.path.basename(out_dir)}.{node.name.lower()} import {node.name}",
            )
            report.extracted.append(result)
            logger.info(f"[DRY RUN] Would extract {node.name} ({size} lines)")
        report.total_lines_after = report.total_lines_before
        return report

    # 3. Create output directory
    base_dir = os.path.dirname(filepath)
    base_name = os.path.basename(filepath)
    name_no_ext = os.path.splitext(base_name)[0]

    if not os.path.isabs(out_dir):
        out_dir = os.path.join(base_dir, out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # Create __init__.py for import support
    init_path = os.path.join(out_dir, "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, "w").close()

    # 4. Extract from end to start (to preserve line numbers)
    extract_nodes.sort(key=lambda n: n.lineno, reverse=True)

    for node in extract_nodes:
        size = node.end_lineno - node.lineno + 1
        logger.info(f"Extracting {node.name} ({size} lines)...")

        comp_filename = f"{node.name.lower()}.py"
        comp_filepath = os.path.join(out_dir, comp_filename)

        # Build new module content
        comp_lines = import_lines.copy()
        comp_lines.append(f"\n# Auto-extracted from {base_name} by HDS Auto-Decomposer")
        comp_lines.append(f"# Original location: lines {node.lineno}-{node.end_lineno}\n")

        # Add the actual class/function code
        comp_lines.extend(lines[node.lineno - 1 : node.end_lineno])

        with open(comp_filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(comp_lines) + "\n")

        # Replace code in original file with import
        module_path = os.path.basename(out_dir)
        import_stmt = f"from {module_path}.{node.name.lower()} import {node.name}"

        # Extract docstring for comment
        docstring = ast.get_docstring(node)
        if docstring:
            short_doc = docstring.strip().split("\n")[0][:80]
            eng_comment = f"# Extracted {type(node).__name__}: {node.name} — {short_doc}"
        else:
            eng_comment = f"# Extracted {type(node).__name__}: {node.name}"

        lines[node.lineno - 1 : node.end_lineno] = [
            f"# {node.name} auto-moved to module '{module_path}' by HDS",
            eng_comment,
            import_stmt,
        ]

        result = ExtractionResult(
            node_name=node.name,
            node_type=type(node).__name__,
            original_lines=size,
            new_file=comp_filepath,
            import_statement=import_stmt,
        )
        report.extracted.append(result)

    # 5. Save versioned backup
    archive_dir = os.path.join(base_dir or ".", "archive")
    os.makedirs(archive_dir, exist_ok=True)
    dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(archive_dir, f"back_{dt_str}_{base_name}")
    shutil.copy2(filepath, backup_path)
    report.backup_path = backup_path
    logger.info(f"Backup saved: {backup_path}")

    # 6. Write modified original
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    report.total_lines_after = len(lines)
    logger.info(
        f"Decomposed {len(report.extracted)} structures: "
        f"{report.total_lines_before} → {report.total_lines_after} lines"
    )

    return report


def check_and_decompose(filepath: str, model_size: str = "m") -> Optional[DecomposeReport]:
    """
    Integration point for ProtocolEnforcer.

    Checks if a file exceeds the line limit for the given model size,
    and auto-decomposes if needed.

    Args:
        filepath: Path to check
        model_size: "xl", "l", "m", or "s"

    Returns:
        DecomposeReport if decomposition happened, None otherwise
    """
    size_limits = {"xl": 1000, "l": 500, "m": 200, "s": 50}
    max_lines = size_limits.get(model_size.lower(), 200)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            total_lines = len(f.readlines())
    except (OSError, UnicodeDecodeError):
        return None

    if total_lines <= max_lines:
        return None

    logger.warning(
        f"File {filepath} has {total_lines} lines, "
        f"exceeds {model_size.upper()} limit of {max_lines}. Auto-decomposing..."
    )

    return decompose_python_file(filepath, max_lines=max_lines)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(
        description="HDS Auto-Decomposer — split large Python files into modules"
    )
    parser.add_argument("file", help="Python file to decompose")
    parser.add_argument(
        "--dir", default="core",
        help="Output directory for extracted modules (default: 'core')"
    )
    parser.add_argument(
        "--max", type=int, default=200,
        help="Max lines per structure before extraction (default: 200)"
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="Rollback file to previous version from archive"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Analyze only, do not modify files"
    )
    parser.add_argument(
        "--analyze", action="store_true",
        help="Show large structures without modifying"
    )
    args = parser.parse_args()

    if args.rollback:
        success = rollback(args.file)
        sys.exit(0 if success else 1)
    elif args.analyze:
        nodes = analyze_file(args.file, args.max)
        if nodes:
            print(f"\nLarge structures in {args.file} (>{args.max} lines):")
            for n in nodes:
                print(f"  {n['type']:12} {n['name']:30} {n['lines']:>5} lines  (L{n['start_line']}-L{n['end_line']})")
                if n["docstring"]:
                    print(f"  {'':12} {n['docstring']}")
        else:
            print(f"No structures exceeding {args.max} lines.")
    else:
        report = decompose_python_file(args.file, args.dir, args.max, dry_run=args.dry_run)
        if report.extracted:
            print(f"\n{'=' * 60}")
            print(f"Decomposition Report: {report.source_file}")
            print(f"{'=' * 60}")
            print(f"  Lines: {report.total_lines_before} → {report.total_lines_after}")
            print(f"  Backup: {report.backup_path}")
            print(f"  Extracted {len(report.extracted)} structures:")
            for e in report.extracted:
                print(f"    {e.node_type:12} {e.node_name:30} ({e.original_lines} lines) → {e.new_file}")
        else:
            print("Nothing to decompose.")
