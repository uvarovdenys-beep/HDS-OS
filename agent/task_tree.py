#!/usr/bin/env python3
"""task_tree.py — deepen a task into function-level subtasks.

WHY. The pipeline generates whole files. To change two lines of a 202-line
TypeScript file it regenerated all 202, five times, on three models — ~3000
generated lines for a two-line fix, and it still failed: the model must
reproduce 200 correct lines in order to alter two.

The unit of work is wrong. This module makes it a FUNCTION.

A plan is not prose telling the model what to do; it is a set of fixed
signatures. The implementer cannot invent an API — the signature is already
decided, its siblings are already declared, and it emits ~30 lines instead of
200. The signature is the cell wall, not an instruction.

Flow:
    idea  ->  plan (FunctionSpec[])  ->  one subtask per function  ->  patch
Each subtask lands through scribe `patch`/`insert`, so the whole file re-passes
the cage after every function. A wrong function is rejected on its own, and the
other functions are unaffected.

Planning and implementing are deliberately separate: the planner never writes
code, the implementer never chooses an API.
"""
from dataclasses import dataclass, field
from typing import Dict, List

# A contract is one line. Longer contracts drift into prose, and prose is what
# the local models ignore — the whole point is that the signature carries the
# meaning.
MAX_CONTRACT_CHARS = 200
MAX_FUNCTIONS = 24


class PlanError(Exception):
    """A plan that cannot be trusted. Fail closed — never implement a bad plan."""


@dataclass
class FunctionSpec:
    """One leaf of work: exactly one function, with its API already decided."""

    name: str                              # "parse_frame" / "McpClient.build"
    file: str                              # path relative to the HDS root
    signature: str                         # exact, language-native
    contract: str                          # one line: what it must do
    depends: List[str] = field(default_factory=list)   # sibling names it may call

    def target(self) -> str:
        """The scribe patch target — the same name the AST locator resolves."""
        return self.name


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PlanError(msg)


def parse_plan(raw: object) -> List[FunctionSpec]:
    """Turn a planner's JSON into specs. Structure only — no code is accepted."""
    _require(isinstance(raw, list), "plan must be a JSON array of functions")
    specs: List[FunctionSpec] = []
    for i, item in enumerate(raw, 1):
        _require(isinstance(item, dict), f"function {i} is not an object")
        missing = [k for k in ("name", "file", "signature", "contract")
                   if not str(item.get(k, "")).strip()]
        _require(not missing, f"function {i} missing: {', '.join(missing)}")
        depends = item.get("depends") or []
        _require(isinstance(depends, list),
                 f"function {i} ('{item['name']}'): depends must be a list")
        specs.append(FunctionSpec(
            name=str(item["name"]).strip(),
            file=str(item["file"]).strip(),
            signature=str(item["signature"]).strip(),
            contract=str(item["contract"]).strip(),
            depends=[str(d).strip() for d in depends],
        ))
    return validate_plan(specs)


def validate_plan(specs: List[FunctionSpec]) -> List[FunctionSpec]:
    """Reject a plan that would let an implementer guess. Fail closed.

    Every rule here exists because its absence produces a specific failure:
    duplicate names make the patch target ambiguous, an unknown dependency
    means the implementer will invent that API, and a long contract means the
    model is being told a story instead of given a wall.
    """
    _require(bool(specs), "plan is empty")
    _require(len(specs) <= MAX_FUNCTIONS,
             f"plan has {len(specs)} functions, limit is {MAX_FUNCTIONS} — "
             f"decompose the idea further before planning")

    seen: Dict[str, str] = {}
    for s in specs:
        _require(s.name not in seen,
                 f"duplicate function '{s.name}' — a patch target must be unique")
        seen[s.name] = s.file

    for s in specs:
        _require(len(s.contract) <= MAX_CONTRACT_CHARS,
                 f"'{s.name}': contract is {len(s.contract)} chars, limit is "
                 f"{MAX_CONTRACT_CHARS} — state the task, do not narrate it")
        _require("\n" not in s.signature, f"'{s.name}': signature must be one line")
        for d in s.depends:
            _require(d in seen,
                     f"'{s.name}' depends on unknown '{d}' — an implementer would "
                     f"invent that API")
        _require(s.name not in s.depends, f"'{s.name}' depends on itself")
    return specs


def build_order(specs: List[FunctionSpec]) -> List[FunctionSpec]:
    """Dependencies first, so a function is written after what it calls.

    Cycles are not an error to route around — they mean the decomposition is
    wrong, so say which functions are tangled and stop.
    """
    by_name = {s.name: s for s in specs}
    done: List[FunctionSpec] = []
    placed = set()

    while len(done) < len(specs):
        ready = [s for s in specs
                 if s.name not in placed
                 and all(d in placed for d in s.depends)]
        if not ready:
            stuck = sorted(s.name for s in specs if s.name not in placed)
            raise PlanError(f"dependency cycle among: {', '.join(stuck)}")
        for s in ready:
            done.append(s)
            placed.add(s.name)
    return [by_name[s.name] for s in done]


def api_surface(specs: List[FunctionSpec], exclude: str = "") -> str:
    """The grate shown to an implementer: every sibling's signature, no bodies.

    Signatures only, deliberately. Showing sibling CODE invites copying and
    blows up the prompt; showing sibling NAMES alone lets the model guess their
    arguments. The signature is the exact amount of truth it needs.
    """
    lines = []
    for s in specs:
        if s.name == exclude:
            continue
        lines.append(f"{s.signature}    // {s.contract}")
    return "\n".join(lines)


def to_subtask(spec: FunctionSpec, specs: List[FunctionSpec],
               model: str = "") -> Dict:
    """One function → one build task, written in through a surgical patch.

    The instruction is short on purpose. Everything binding lives in the
    reference files, because a local model follows an example far harder than
    it follows a paragraph.
    """
    surface = api_surface(specs, exclude=spec.name)
    grate = (
        f"Implement EXACTLY ONE function. Nothing else.\n\n"
        f"Signature (do not change it):\n    {spec.signature}\n\n"
        f"It must: {spec.contract}\n\n"
        f"You may call ONLY these, exactly as declared:\n{surface or '    (nothing)'}\n\n"
        f"Emit only the function. No imports, no surrounding class, no examples, "
        f"no explanation."
    )
    task = {
        "type": "generate_code",
        "instruction": f"Implement {spec.name}: {spec.contract}",
        "output_dir": str(spec.file).rsplit("/", 1)[0] if "/" in spec.file else "",
        "output_filename": str(spec.file).rsplit("/", 1)[-1],
        "patch_target": spec.target(),
        "reference_files": [{"name": "grate.md", "content": grate}],
    }
    if model:
        task["model"] = model
    return task


def plan_to_subtasks(specs: List[FunctionSpec], model: str = "") -> List[Dict]:
    """A validated plan → its subtasks, in dependency order."""
    ordered = build_order(validate_plan(specs))
    return [to_subtask(s, ordered, model) for s in ordered]


def write_op(rel_path: str, code: str, patch_target: str = "",
             file_exists: bool = False, source: str = "") -> Dict:
    """Choose the scribe op for a generated unit of work.

    Three cases, and the middle one is the whole point of this function:

      file absent            -> write   (the first function creates the file)
      target already present -> patch   (replace exactly it, touch nothing else)
      file present, no target-> insert  (append; the neighbours survive)

    The earlier version only asked whether the FILE existed. That is wrong for
    every file with more than one function: the first task creates the file, and
    the second is then asked to PATCH a target that is not in it yet, so the
    cage answers "R-PATCH: target not found" and the task fails. Measured, not
    theorised — a three-function module lost two of its functions that way.
    """
    if not (patch_target and file_exists):
        return {"op": "write", "path": rel_path, "content": code}

    if _has_target(source, patch_target):
        return {"op": "patch", "path": rel_path,
                "target": patch_target, "content": code}

    # Append after the last line: `insert` with after_line=0 would put the new
    # function ABOVE the imports.
    return {"op": "insert", "path": rel_path,
            "after_line": len(source.splitlines()),
            "content": "\n\n" + code.lstrip("\n")}


def extract_target(code: str, target: str) -> str:
    """Take ONLY the named function out of whatever the model actually emitted.

    The grate says "Implement EXACTLY ONE function. Nothing else." and the model
    ignores it: asked for `is_open`, a 14B returned the whole module. Appending
    that produced duplicate definitions, and the next task then failed with
    "R-PATCH: target is ambiguous (2 matches)".

    Instructing did not work, so this stops instructing and CONSTRAINS — the
    same move as the cage itself. If the requested function is in the output it
    is cut out and the rest discarded; if it is absent the output is left alone,
    so a genuine failure still reaches the cage instead of being masked.

    Duplicates inside one generation take the FIRST definition: it is the one
    written against the signature the model was handed.
    """
    if not (code and target):
        return code
    try:
        import ast
        tree = ast.parse(code)
    except SyntaxError:
        return code                      # not parseable Python — the cage decides
    want = target.rsplit(".", 1)[-1]
    lines = code.splitlines()
    # Search top level AND one level inside classes. Asked for a METHOD, a model
    # returns the whole class; extracting nothing then appends that class beside
    # the real one and R-PRESERVE rightly refuses ("declares PipelineHelpersMixin
    # twice"). Measured: a 14B lost all four attempts to exactly this.
    candidates = list(tree.body)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            candidates.extend(node.body)
    for node in candidates:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name != want:
            continue
        first = node.lineno
        for dec in node.decorator_list:
            if dec.lineno < first:
                first = dec.lineno
        return "\n".join(lines[first - 1:node.end_lineno]).rstrip() + "\n"
    return code


def _has_target(source: str, target: str) -> bool:
    """Is this function/class already in the file? Absent source means no."""
    if not source:
        return False
    try:
        import patcher
        patcher.locate(source, target)
        return True
    except Exception:
        return False
