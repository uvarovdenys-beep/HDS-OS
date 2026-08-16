#!/usr/bin/env python3
"""skills.py — orchestrator skills, in the Claude Skills format.

WHY THIS EXISTS. A grate fixes the signature, but a signature carries no
NUANCE. Asked for `_escalate_to` — a @staticmethod inside a class — a 14B
returned the whole class four times, and R-PRESERVE refused every one. The model
was not weak; nobody told it the target was a METHOD.

That knowledge belongs to the ORCHESTRATOR, and it must be extensible without
touching code — so skills live on disk exactly as they do in Claude: one folder
per skill, a SKILL.md with YAML frontmatter, and a `description` that says WHEN
it applies. Progressive disclosure: only skills whose trigger matches are read
and put in the prompt, so an unused skill costs nothing.

    skills_lib/<name>/SKILL.md
    ---
    name: python
    description: Use for Python tasks…
    applies_when: lang=Python        # or: always | patch_target | target_has_dot
    ---
    - the rules, as short imperative lines

This is the PROACTIVE half of HDS's knowledge. cage_help is the reactive half
(what to do after a rejection); ai_experience is the remembered half (what went
wrong before).
"""
from pathlib import Path

LIB = Path(__file__).resolve().parent / "skills_lib"


def _parse(text: str) -> dict:
    """Split a SKILL.md into its frontmatter fields and body. Tolerant: a file
    without frontmatter is still usable, it just never triggers on a field."""
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2]
    return {"meta": meta, "body": body.strip()}


def available() -> list:
    """Every skill on disk: [{name, description, applies_when, body}]."""
    out = []
    if not LIB.is_dir():
        return out
    for folder in sorted(LIB.iterdir()):
        f = folder / "SKILL.md"
        if not f.is_file():
            continue
        try:
            parsed = _parse(f.read_text(encoding="utf-8"))
        except OSError:
            continue
        m = parsed["meta"]
        out.append({"name": m.get("name", folder.name),
                    "description": m.get("description", ""),
                    "applies_when": m.get("applies_when", ""),
                    "body": parsed["body"]})
    return out


def _matches(rule: str, lang: str, patch_target: str, file_exists: bool) -> bool:
    """Does this skill's trigger fire for the task at hand?"""
    rule = (rule or "").strip()
    if rule == "always":
        return True
    if rule == "target_has_dot":
        return "." in (patch_target or "")
    if rule == "patch_target":
        # the generic patch skill is redundant once the method skill fires
        return bool(patch_target) and "." not in patch_target
    if rule == "new_file":
        return not file_exists and not patch_target
    if rule.startswith("lang="):
        return rule.split("=", 1)[1].strip().lower() == (lang or "").lower()
    return False


def for_task(lang: str, patch_target: str = "", file_exists: bool = True) -> list:
    """The skills whose triggers fire, most specific first."""
    order = {"target_has_dot": 0, "patch_target": 0, "new_file": 0}
    hits = [s for s in available()
            if _matches(s["applies_when"], lang, patch_target, file_exists)]
    hits.sort(key=lambda s: (order.get(s["applies_when"], 1),
                             2 if s["applies_when"] == "always" else 1))
    return hits


def block(lang: str, patch_target: str = "", file_exists: bool = True) -> str:
    """The matching skills as a prompt fragment. Empty when none apply."""
    hits = for_task(lang, patch_target, file_exists)
    if not hits:
        return ""
    parts = ["KNOW THIS (orchestrator skills for this task):"]
    for s in hits:
        parts.append(s["body"])
    return "\n".join(parts) + "\n\n"


def main():
    print("HDS orchestrator skills")
    for s in available():
        print(f"  {s['name']:18s} [{s['applies_when'] or '-':16s}] "
              f"{s['description'][:60]}")


if __name__ == "__main__":
    main()
