#!/usr/bin/env python3
"""console_chat.py — the console's dialogue, backed by a local model.

Forms made the operator do the decomposition; the point of HDS is that the AI
does it and a human accepts. So the console talks instead: you say what you
want, the model answers, and when it proposes structure it comes back as a
SELECTABLE SET that lands in the tree as draft.

WHAT TRAVELS WITH A REQUEST. One request, but not the whole plan. Sending the
entire tree every turn is how a greeting came to cost 17k tokens in another
tool; on a fifty-file project it is worse. The LEVEL picks the slice:

    ask       project name + pipeline counters
    idea      project name + existing idea titles
    structure the idea's note + the file registry
    task      the file + its siblings' signatures + declared module state

MODEL BY JOB, not by size. Measured today: a coder model rendered "greenest" as
"most experienced" while the general model got it right — and the coder model
wrote correct C the general one is slow at. Planning and implementing want
different models.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PROJECTS_FILE = ROOT / "ai-mind" / "knowledge" / "projects.json"

FIT = {"ask": "qwen3.5:27b", "idea": "qwen3.5:27b",
       "structure": "qwen3.5:27b", "task": "qwen2.5-coder-14b"}

_SHAPE = {
    "idea": ('[{"title": "one line: what to build", '
             '"why": "one line: why it is worth doing"}]'),
    "structure": ('[{"file": "dir/name.ext", '
                  '"title": "what this file is responsible for"}]'),
    "task": ('[{"title": "functionName", '
             '"signature": "<one line, exact, in the file\'s language>", '
             '"contract": "one line: what it must do", '
             '"depends": ["functions THIS one calls"]}]'),
}


# ── projects ──────────────────────────────────────────────────────────────

def projects() -> list:
    """Registered projects. The file is the same one the agent already reads
    to decide which directories it may write to."""
    if not PROJECTS_FILE.exists():
        return []
    try:
        data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data.get("active_projects", [])


def add_project(name: str, path: str) -> dict:
    """Register a project. Its path becomes an allowed workspace.

    This is a PRIVILEGE GRANT, not a label, so it is gated like any other
    client write. An earlier version passed protocol_size=None here while its
    own docstring claimed the cage was applied — None skips the content scan,
    which is exactly wrong for the file that decides where the agent may write.
    """
    import scribe
    name, path = str(name).strip(), str(path).strip()
    if not name or not path:
        raise ValueError("both name and path are required")
    items = [p for p in projects() if p.get("name") != name]
    items.append({"name": name, "path": path})
    scribe.execute({"op": "write", "path": str(PROJECTS_FILE),
                    "content": json.dumps({"active_projects": items}, indent=2)},
                   protocol_size="l")
    return {"ok": True, "projects": items}


# ── context slices ────────────────────────────────────────────────────────

def _slice(level: str, project: str, node_id: str = "") -> str:
    """Build the smallest context that still fully specifies the question."""
    import pipeline
    lines = [f"Project: {project}"]

    if level == "ask":
        t = pipeline.status(project)["totals"]
        lines.append("Pipeline: " + ", ".join(f"{v} {k}" for k, v in t.items() if v))
        return "\n".join(lines)

    if level == "idea":
        for name in pipeline.ideas(project):
            root, _ = pipeline._load(project, name)
            lines.append(f"- {name}: {root.title}")
        return "\n".join(lines) if len(lines) > 1 else lines[0] + "\n(no ideas yet)"

    import idea_tree
    if level == "structure":
        for name in pipeline.ideas(project):
            root, _ = pipeline._load(project, name)
            if node_id and root.id != node_id.split(".")[0]:
                continue
            lines.append(f"Idea: {root.title}")
            if root.note:
                lines.append(f"Constraints: {root.note}")
            files = sorted({n.file for n in idea_tree.walk(root) if n.file})
            if files:
                lines.append("Files that already exist: " + ", ".join(files))
        return "\n".join(lines)

    # task: the grate — file, siblings, declared state
    for name in pipeline.ideas(project):
        root, _ = pipeline._load(project, name)
        node = idea_tree.find(root, node_id) if node_id else None
        if node is None:
            continue
        lines.append(f"File: {node.file}")
        if node.title:
            lines.append(f"It is responsible for: {node.title}")
        if node.context:
            lines.append("Module state already declared in the file: "
                         + json.dumps(node.context))
        sig = [c.signature for c in node.children if c.signature]
        if sig:
            lines.append("Functions already planned:\n  " + "\n  ".join(sig))
        break
    return "\n".join(lines)


def _prompt(level: str, text: str, context: str) -> str:
    if level == "ask":
        return (f"You are HDS, an assistant that plans and builds software with "
                f"a local model, inside a cage that verifies every write.\n"
                f"Answer briefly and concretely.\n\n{context}\n\nQuestion: {text}")
    return (f"{context}\n\nRequest: {text}\n\n"
            f"Propose 2 to 5 options. Return ONLY a JSON array, no prose:\n"
            f"{_SHAPE[level]}\n"
            f"Every field is required. No explanation before or after the array.")


def _caller(model: str):
    """Bind a model NAME to a caller for the model this machine actually serves.

    An earlier version guessed the provider from whether the name contained a
    slash. It sent "qwen2.5-coder-14b" to ollama, which serves it as
    "qwen/qwen2.5-coder-14b" under LM Studio, and got a 404. HDS already solves
    this — model_scan reports what is really served — so guessing was both
    wrong and unnecessary.

    The substring match needs a floor: normalising a non-latin name leaves an
    empty string, and `"" in anything` is true, so an unknown model silently
    bound to the first one served. An unrecognised name must fail loudly.
    """
    from ai_callers import make_lmstudio_caller, make_ollama_caller
    from model_scan import discover_models

    served = discover_models()
    want = re.sub(r"[^a-z0-9]", "", (model or "").lower())
    if len(want) < 3:
        raise RuntimeError(f"'{model}' is not a usable model name")
    for provider in ("lmstudio", "ollama"):
        for sid in served.get(provider, []):
            norm = re.sub(r"[^a-z0-9]", "", sid.lower())
            if norm == want or want in norm:
                return (make_lmstudio_caller(model=sid) if provider == "lmstudio"
                        else make_ollama_caller(model=sid))
    raise RuntimeError(
        f"'{model}' is not served by this machine. Available: "
        + ", ".join(sorted(s for v in served.values() for s in v)))


def _array(raw: str) -> list:
    """Pull the JSON array out of whatever the model said. Fail closed."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("\n")
        text = "\n".join(parts[1:-1] if parts[-1].strip().startswith("```") else parts[1:])
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        out = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    return [x for x in out if isinstance(x, dict)] if isinstance(out, list) else []


def chat(project: str, level: str, text: str, model: str = "",
         node: str = "") -> dict:
    """One turn. Returns {reply, proposal, level, model, context_chars}."""
    level = level if level in FIT else "ask"
    model = model or FIT[level]
    context = _slice(level, project, node)
    prompt = _prompt(level, text, context)

    try:
        raw = _caller(model)(prompt)
    except Exception as e:
        return {"ok": False, "reply": f"модель недоступна: {e}",
                "proposal": [], "level": level, "model": model}

    if level == "ask":
        return {"ok": True, "reply": raw.strip()[:2000], "proposal": [],
                "level": level, "model": model, "context_chars": len(context)}

    items = _array(raw)
    reply = (f"Пропоную {len(items)} варіант(и) на рівні «{level}». "
             f"Обери потрібні — вони ляжуть у дерево як чернетки."
             if items else
             "Модель не повернула структурованої відповіді. Спробуй "
             "переформулювати або обрати іншу модель.")
    return {"ok": True, "reply": reply, "proposal": items,
            "level": level, "model": model, "context_chars": len(context)}
