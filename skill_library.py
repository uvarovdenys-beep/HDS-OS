#!/usr/bin/env python3
"""skill_library.py — the POSITIVE half of HDS memory.

ai_experience remembers what went WRONG. Nothing remembered what went RIGHT, so
every task started from zero even when a near-identical function had already
passed every check. Voyager's finding is the one that applies here: an agent
that keeps a library of VERIFIED skills and shows itself the relevant ones
solves harder tasks than one that only avoids past mistakes.

Only fully verified work is admitted — the code passed the cage, its declared
acceptance assertions, and Monte Carlo. That is the whole point: an example that
has not been proven is just another guess, and showing a guess to a small model
propagates it.

Recall is semantic (embed.py -> local nomic), same as lesson recall, with a
similarity floor so an irrelevant example never enters the prompt.
"""
import json
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent / "ai-mind" / "experience" / "skills.jsonl"
RECALL_MIN = 0.60      # a hair stricter than lessons: a wrong EXAMPLE misleads
RECALL_MAX = 2         # two examples is steering; five is a wall of text
MAX_CODE_CHARS = 1200


def _embed(text):
    try:
        from embed import embed
        return embed(text)
    except Exception:
        return None


def record(name: str, code: str, lang: str, contract: str = "",
           symbol: str = "") -> bool:
    """Admit one VERIFIED function. Never raises."""
    code = (code or "").strip()
    if not name or not code or len(code) > MAX_CODE_CHARS:
        return False
    try:
        LIB.parent.mkdir(parents=True, exist_ok=True)
        # Skip a duplicate name+lang: the newest verified version wins, but
        # rewriting the file for every save would not scale, so an append with a
        # newest-wins read is the cheaper truth.
        row = {"t": round(time.time(), 3), "name": name, "lang": lang,
               "contract": contract[:200], "code": code, "symbol": symbol}
        vec = _embed(f"{name} {contract}")
        if vec:
            row["embedding"] = vec
        with open(LIB, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def entries(path=None) -> list:
    """Every verified skill, newest-wins per (name, lang)."""
    p = Path(path) if path else LIB
    if not p.exists():
        return []
    best = {}
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("name"):
            best[(row["name"], row.get("lang", ""))] = row
    return list(best.values())


def recall(instruction: str, lang: str = "", limit: int = RECALL_MAX) -> list:
    """Verified examples similar to what is being asked. Empty when unsure."""
    rows = [r for r in entries() if not lang or r.get("lang") == lang]
    rows = [r for r in rows if r.get("embedding")]
    if not rows or not instruction:
        return []
    qvec = _embed(instruction)
    if qvec is None:
        return []
    from embed import cosine
    scored = []
    for r in rows:
        sim = cosine(qvec, r["embedding"])
        if sim >= RECALL_MIN:
            scored.append((sim, r))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [r for _, r in scored[:limit]]


def block(instruction: str, lang: str = "") -> str:
    """Verified examples as a prompt fragment. Empty when none are close."""
    hits = recall(instruction, lang)
    if not hits:
        return ""
    parts = ["WORKED BEFORE (these passed the cage, their assertions and "
             "Monte Carlo — follow their style, do not copy blindly):"]
    for r in hits:
        head = f"# {r['name']}"
        if r.get("contract"):
            head += f" — {r['contract']}"
        parts.append(head + "\n" + r["code"])
    return "\n".join(parts) + "\n\n"


def main():
    rows = entries()
    print(f"HDS skill library — {len(rows)} verified skill(s)")
    for r in sorted(rows, key=lambda r: r.get("lang", "")):
        print(f"  {r.get('lang',''):12s} {r['name']:24s} {r.get('contract','')[:44]}")


if __name__ == "__main__":
    main()
