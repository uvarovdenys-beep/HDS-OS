#!/usr/bin/env python3
"""
model_router.py
HDS Model Router — determines protocol size (XL/L/M/S) for a model.

Two classification modes:
  1. STATIC — by model name (fast, for known models)
  2. DIAGNOSTIC — via 6 psychological tests (precise, for unknown models)

Tasks are UNIVERSAL for all models.
Protocol is ADAPTIVE to cognitive level.

Authors: HDS Development Team
License: HDS Standard
"""

import re
import json
import logging
from enum import Enum
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger("model_router")


# ──────────────────────────────────────────────────────────────
# PROTOCOL SIZES
# ──────────────────────────────────────────────────────────────

class ProtocolSize(Enum):
    """HDS protocol size."""
    XL = "xl"    # Architect — full autonomy
    L = "l"      # Engineer — guided autonomy
    M = "m"      # Executor — structured execution
    S = "s"      # Helper — instruction → action


@dataclass
class ModelProfile:
    """Full model profile."""
    name: str
    size: ProtocolSize
    max_context: int
    max_task_complexity: int     # 1-10
    can_discover: bool
    can_create_modules: bool
    can_decompose: bool
    can_aivc: bool
    can_refactor: bool
    can_self_correct: bool
    max_lines_per_change: int
    max_files_per_session: int
    protocol_file: str
    boot_steps: int
    rules_count: int


# ──────────────────────────────────────────────────────────────
# SIZE PROFILES — capabilities per size
# ──────────────────────────────────────────────────────────────

SIZE_PROFILES = {
    ProtocolSize.XL: {
        "max_task_complexity": 10,
        "can_discover": True,
        "can_create_modules": True,
        "can_decompose": True,
        "can_aivc": True,
        "can_refactor": True,
        "can_self_correct": True,
        "max_lines_per_change": 1000,
        "max_files_per_session": 999,   # unlimited
        "protocol_file": "ai-mind/protocols/hds_xl.md",
        "boot_steps": 4,
        "rules_count": 12,
    },
    ProtocolSize.L: {
        "max_task_complexity": 7,
        "can_discover": True,
        "can_create_modules": True,
        "can_decompose": False,
        "can_aivc": True,
        "can_refactor": True,
        "can_self_correct": True,
        "max_lines_per_change": 500,
        "max_files_per_session": 15,
        "protocol_file": "ai-mind/protocols/hds_l.md",
        "boot_steps": 3,
        "rules_count": 8,
    },
    ProtocolSize.M: {
        "max_task_complexity": 5,
        "can_discover": False,
        "can_create_modules": False,
        "can_decompose": False,
        "can_aivc": False,
        "can_refactor": False,
        "can_self_correct": False,
        "max_lines_per_change": 200,
        "max_files_per_session": 8,
        "protocol_file": "ai-mind/protocols/hds_m.md",
        "boot_steps": 2,
        "rules_count": 5,
    },
    ProtocolSize.S: {
        "max_task_complexity": 3,
        "can_discover": False,
        "can_create_modules": False,
        "can_decompose": False,
        "can_aivc": False,
        "can_refactor": False,
        "can_self_correct": False,
        "max_lines_per_change": 50,
        "max_files_per_session": 3,
        "protocol_file": "ai-mind/protocols/hds_s.md",
        "boot_steps": 1,
        "rules_count": 3,
    },
}


# ──────────────────────────────────────────────────────────────
# STATIC CLASSIFICATION — by model name
# ──────────────────────────────────────────────────────────────

# (regex_pattern, ProtocolSize, approx_context_tokens)
MODEL_PATTERNS: List[Tuple[str, ProtocolSize, int]] = [
    # ── XL (Architect) ─────────────────────────────────────
    (r"claude.*opus",               ProtocolSize.XL, 200000),
    (r"gpt-4o(?!-mini)",            ProtocolSize.XL, 128000),
    (r"gpt-4-turbo",                ProtocolSize.XL, 128000),
    (r"gpt-4(?!o)",                 ProtocolSize.XL, 128000),
    (r"o[13]-",                     ProtocolSize.XL, 200000),  # o1, o3
    (r"deepseek.*r1.*(70|67)b",     ProtocolSize.XL, 128000),
    (r"qwen.*3\.?[56].*(3[05]|27)b",ProtocolSize.XL, 128000),
    (r"qwen.*coder.*30b",           ProtocolSize.XL, 128000),
    (r"qwen.*(30|72)b",             ProtocolSize.XL, 128000),
    (r"llama.*(70|405)b",           ProtocolSize.XL, 128000),
    (r"gemma.*27b",                 ProtocolSize.XL, 128000),
    (r"gpt-oss.*20b",               ProtocolSize.XL, 64000),

    # ── L (Engineer) ───────────────────────────────────────
    (r"claude.*sonnet",             ProtocolSize.L, 200000),
    (r"gpt-4o-mini",                ProtocolSize.L, 128000),
    (r"qwen.*coder.*14b",           ProtocolSize.L, 64000),
    (r"qwen.*(14|20)b",             ProtocolSize.L, 64000),
    (r"llama.*(13|34)b",            ProtocolSize.L, 8000),
    (r"gemma.*[49]b",               ProtocolSize.L, 64000),
    (r"deepseek.*r1.*8b",           ProtocolSize.L, 64000),
    (r"mistral.*large",             ProtocolSize.L, 128000),
    (r"mistral.*medium",            ProtocolSize.L, 32000),

    # ── M (Executor) ───────────────────────────────────────
    (r"qwen.*3\.?5.*(9|12)b",       ProtocolSize.M, 32000),
    (r"qwen.*(7|9)b",              ProtocolSize.M, 32000),
    (r"llama.*[78]b",              ProtocolSize.M, 8000),
    (r"mistral(?!.*large|.*medium)",ProtocolSize.M, 32000),
    (r"gemma.*[24]b",              ProtocolSize.M, 8000),
    (r"phi-[34]",                  ProtocolSize.M, 16000),
    (r"yi.*[69]b",                 ProtocolSize.M, 16000),

    # ── S (Helper) ────────────────────────────────────────
    (r"claude.*haiku",              ProtocolSize.S, 200000),
    (r"qwen.*[1-4]b(?!0)",         ProtocolSize.S, 32000),
    (r"phi-[12]",                  ProtocolSize.S, 4000),
    (r"tinyllama",                 ProtocolSize.S, 4000),
    (r"gemma.*2b",                 ProtocolSize.S, 8000),
    (r"stablelm",                  ProtocolSize.S, 4000),
]


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────

def classify_model(model_name: str) -> Tuple[ProtocolSize, int]:
    """
    Static classification by model name.

    Returns:
        (ProtocolSize, approximate_context_tokens)
    """
    name = model_name.lower().strip()

    for pattern, size, ctx in MODEL_PATTERNS:
        if re.search(pattern, name):
            logger.info(f"[Router] {model_name} → {size.value.upper()}")
            return size, ctx

    # Default: M (safe middle ground)
    logger.warning(f"[Router] Unknown model '{model_name}' → M (default)")
    return ProtocolSize.M, 32000


def get_model_profile(model_name: str) -> ModelProfile:
    """Get full model profile."""
    size, ctx = classify_model(model_name)
    props = SIZE_PROFILES[size]

    return ModelProfile(
        name=model_name,
        size=size,
        max_context=ctx,
        **props,
    )


def get_protocol_path(model_name: str) -> str:
    """Get protocol file path for model."""
    size, _ = classify_model(model_name)
    return SIZE_PROFILES[size]["protocol_file"]


# ──────────────────────────────────────────────────────────────
# TASK ADAPTER — adapts a UNIVERSAL task to model's protocol size
# ──────────────────────────────────────────────────────────────

def adapt_task(task: Dict, model_name: str) -> str:
    """
    Adapt a universal task to the model's protocol size.

    task format (universal):
        task_id: str
        goal: str
        priority: str
        complexity: int (1-10)
        target:
            file: str
            line: int (optional)
            function: str (optional)
        context: str (optional)
        solution_hint: str (optional)
        test: str
        decomposition: list (optional)

    Returns:
        Formatted task string appropriate for the model's level
    """
    size, _ = classify_model(model_name)

    if size == ProtocolSize.XL:
        return _adapt_xl(task)
    elif size == ProtocolSize.L:
        return _adapt_l(task)
    elif size == ProtocolSize.M:
        return _adapt_m(task)
    else:
        return _adapt_s(task)


def _adapt_xl(task: Dict) -> str:
    """XL sees full task with goal-based description."""
    parts = [f"## GOAL\n{task.get('goal', '')}"]

    if task.get("context"):
        parts.append(f"\n## CONTEXT\n{task['context']}")

    target = task.get("target", {})
    if target:
        parts.append(f"\n## TARGET\n- File: `{target.get('file', '')}`")
        if target.get("function"):
            parts.append(f"- Function: `{target['function']}`")

    if task.get("decomposition"):
        dec = "\n".join(
            f"- [ ] {s.get('name', '')} → `{s.get('target', '')}`"
            for s in task["decomposition"]
        )
        parts.append(f"\n## DECOMPOSITION\n{dec}")

    if task.get("test"):
        parts.append(f"\n## VALIDATOR\n```bash\n{task['test']}\n```")

    parts.append("\n## DVP LOG\n| Timestamp | Step | Result |\n|---|---|---|")
    return "\n".join(parts)


def _adapt_l(task: Dict) -> str:
    """L sees task with steps and hints."""
    parts = [f"## GOAL\n{task.get('goal', '')}"]

    target = task.get("target", {})
    if target:
        line_info = f" (line ~{target['line']})" if target.get("line") else ""
        parts.append(f"\n## TARGET\n`{target.get('file', '')}`{line_info}")

    if task.get("solution_hint"):
        parts.append(f"\n## HINT\n{task['solution_hint']}")

    if task.get("decomposition"):
        steps = "\n".join(f"- [ ] {s.get('name', '')}" for s in task["decomposition"])
        parts.append(f"\n## STEPS\n{steps}")

    if task.get("test"):
        parts.append(f"\n## TEST\n```bash\n{task['test']}\n```\nExpected: PASSED")

    return "\n".join(parts)


def _adapt_m(task: Dict) -> str:
    """M sees concrete instruction."""
    target = task.get("target", {})
    file_path = target.get("file", "")
    line = target.get("line")

    parts = [f"# What to do\n{task.get('goal', '')}"]

    if file_path:
        line_info = f" — line ~{line}" if line else ""
        parts.append(f"\n# Target file\n`{file_path}`{line_info}")

    if task.get("solution_hint"):
        parts.append(f"\n# Hint\n```\n{task['solution_hint']}\n```")

    if task.get("test"):
        parts.append(f"\n# Test\n```bash\n{task['test']}\n```")

    return "\n".join(parts)


def _adapt_s(task: Dict) -> str:
    """S sees copy-paste instruction."""
    target = task.get("target", {})
    file_path = target.get("file", "")
    line = target.get("line", "?")

    parts = [f"FILE: {file_path}", f"LINE: {line}"]

    if task.get("solution_hint"):
        parts.append(f"CHANGE:\n{task['solution_hint']}")
    else:
        parts.append(f"CHANGE: {task.get('goal', '')}")

    if task.get("test"):
        parts.append(f"TEST: {task['test']}")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────
# BOOT PROMPT GENERATOR
# ──────────────────────────────────────────────────────────────

def get_boot_prompt(model_name: str, task_path: str = "") -> str:
    """
    Generate boot prompt for the model.

    This is the first thing the model should read at session start.
    """
    profile = get_model_profile(model_name)
    size = profile.size

    if size == ProtocolSize.XL:
        return (
            f"# HDS — Mode XL (Architect)\n"
            f"Model: {model_name} | Context: {profile.max_context:,} tokens\n\n"
            f"You have full autonomy. Read protocol: {profile.protocol_file}\n"
            f"Boot: config → architecture → tasks → ideas\n"
        )
    elif size == ProtocolSize.L:
        return (
            f"# HDS — Mode L (Engineer)\n"
            f"Model: {model_name}\n\n"
            f"Follow task steps. Max {profile.max_files_per_session} files.\n"
            f"Protocol: {profile.protocol_file}\n"
            f"{f'Task: {task_path}' if task_path else 'Task: ai-mind/tasks/active/'}\n"
        )
    elif size == ProtocolSize.M:
        return (
            f"# HDS — Mode M (Executor)\n"
            f"Rules: READ → DO → TEST. Max {profile.max_lines_per_change} lines.\n"
            f"{f'Task: {task_path}' if task_path else 'Task: ai-mind/tasks/active/'}\n"
            f"Do not search files. Do not 'improve'. Do only what was asked.\n"
        )
    else:  # S
        return (
            f"# HDS — Mode S (Helper)\n"
            f"Read the task. Execute. Show test result.\n"
            f"{f'Task: {task_path}' if task_path else 'Task: ai-mind/tasks/active/'}\n"
            f"Do nothing extra. If unclear — STOP.\n"
        )


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    test_models = [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-3-5",
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
        "qwen/qwen3.6-35b-a3b",
        "qwen3.5:27b",
        "qwen3.5:9b",
        "qwen3.5:4b",
        "llama3:latest",
        "mistral:latest",
        "deepseek-r1:8b",
        "deepseek-r1:70b",
        "phi-3",
        "tinyllama",
        "unknown-model",
    ]

    print("=" * 75)
    print(f"{'MODEL':<30} {'SIZE':>4} {'CTX':>8} {'DISC':>5} {'AIVC':>5} {'LINES':>6} {'FILES':>6} {'RULES':>6}")
    print("=" * 75)

    for m in test_models:
        p = get_model_profile(m)
        print(
            f"{m:<30} {p.size.value.upper():>4} {p.max_context:>8,} "
            f"{'✓' if p.can_discover else '✗':>5} "
            f"{'✓' if p.can_aivc else '✗':>5} "
            f"{p.max_lines_per_change:>6} "
            f"{p.max_files_per_session:>6} "
            f"{p.rules_count:>6}"
        )

    # Show boot prompts
    if "--boot" in sys.argv:
        for m in ["claude-opus-4-6", "qwen3.5:9b", "claude-haiku-3-5"]:
            print(f"\n{'─'*60}")
            print(get_boot_prompt(m))

    # Show task adaptation
    if "--task" in sys.argv:
        sample_task = {
            "task_id": "TASK-001",
            "goal": "Add email validation to registration form",
            "complexity": 6,
            "target": {"file": "src/auth/register.py", "line": 142, "function": "validate_input"},
            "context": "Form accepts any text as email. Validation needed.",
            "solution_hint": "import re\nEMAIL_RE = r'^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$'",
            "test": 'python3 -c "from src.auth.register import validate_input; assert validate_input(\'a@b.c\'); print(\'PASSED\')"',
            "decomposition": [
                {"name": "Add import re", "target": "src/auth/register.py"},
                {"name": "Create validate_email()", "target": "src/auth/register.py"},
            ],
        }

        for m in ["claude-opus-4-6", "claude-sonnet-4-6", "qwen3.5:9b", "claude-haiku-3-5"]:
            print(f"\n{'═'*60}")
            print(f"TASK for {m} [{classify_model(m)[0].value.upper()}]:")
            print("─" * 60)
            print(adapt_task(sample_task, m))
