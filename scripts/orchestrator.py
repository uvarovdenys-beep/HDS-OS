import os
import sys
import json
import time
import subprocess
import re
from pathlib import Path

# Sibling scripts (ai_core, queue_manager)
sys.path.append(str(Path(__file__).resolve().parent))
# Runtime modules live in agent/; cage kernel (scribe, events) at OS root core/
sys.path.append(str(Path(__file__).resolve().parent.parent / "agent"))
sys.path.append(str(Path(__file__).resolve().parent.parent))  # core/ (OS root)
from ai_core import get_core
from queue_manager import HDS_Queue_Manager
import scribe
from events import emit


def _rebuild_index_hook(written_paths):
    """HDS-specific post-write hook: keep the orchestrator index fresh.

    Registered on the core cage so core itself imports nothing HDS-specific.
    """
    from orchestrator_index import rebuild_index
    agent_dir = Path(__file__).resolve().parent.parent / "agent"
    rebuild_index(str(agent_dir))


scribe.set_post_write_hook(_rebuild_index_hook)


def extract_task_script(text):
    """Pull a task-script (JSON dict or list) out of a model response.

    Priority: ```json ... ``` fence → left-to-right bracket scan (not greedy
    regex). The old r'{.*}' greedy pattern breaks on any response that contains
    CSS/HTML {} — this scanner instead tries every { or [ start position and
    returns the FIRST valid JSON object/array it can decode.
    """
    # 1) fenced code block — cleanest signal
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass  # malformed fence → fall through to scan

    # 2) left-to-right scan: find first valid JSON object or array
    for i, ch in enumerate(text):
        if ch not in ("{", "["):
            continue
        # try incrementally larger slices from this position
        close = "}" if ch == "{" else "]"
        depth = 0
        for j in range(i, len(text)):
            if text[j] == ch:
                depth += 1
            elif text[j] == close:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:j + 1])
                    except json.JSONDecodeError:
                        break  # not valid JSON at this bracket — keep scanning
    return None

def clear_vram():
    """Universal VRAM clear call"""
    scripts_dir = Path(__file__).resolve().parent
    mem_clear = scripts_dir / "mem_clear.py"
    if mem_clear.exists():
        subprocess.run([sys.executable, str(mem_clear), "--all"], capture_output=True)

class UniversalOrchestrator:
    def __init__(self, endpoint, model):
        self.core = get_core(endpoint, model)
        self.queue = HDS_Queue_Manager(Path(__file__).resolve().parent.parent / "tasks" / "queue")

    def process_task(self, name, prompt, system="You are an expert developer.", temperature=0.3, image_path=None):
        print(f"🛠️ Executing: {name}...")
        self.queue.wait_for_turn(name)
        try:
            clear_vram()
            result = self.core.query(prompt, system, temperature=temperature, image_path=image_path)
            # Remove LLM markers
            result = re.sub(r'^(?:Text|Output|Result):\s*', '', result, flags=re.IGNORECASE | re.MULTILINE)
            return result
        finally:
            self.queue.release()

    def process_and_write(self, name, prompt, system="You are an expert developer.",
                          temperature=0.3, image_path=None, protocol_size=None):
        """Full locAI cycle: model emits a task-script, model is unloaded, then
        the deterministic scribe applies it. SINGLE MODEL: by the time scribe
        writes, the LLM is out of VRAM (clear_vram), so only one model is ever
        resident — and scribe itself loads none.

        protocol_size (s/m/l/xl) is the capability gate: the model's reach in
        scribe matches the autonomy it earned in the diagnostic. A thinking-but-
        disobedient model graded 's' can only drop files in the sandbox here, no
        matter what its task-script asks for.
        """
        result = self.process_task(name, prompt, system=system,
                                   temperature=temperature, image_path=image_path)
        task_script = extract_task_script(result)
        if task_script is None:
            print("ℹ️ No task-script in response — nothing to write (R-19 idle).")
            return result, []
        clear_vram()  # unload model before the executor runs
        try:
            applied = scribe.execute(task_script, protocol_size=protocol_size)
        except (scribe.ScribeError, KeyError) as e:
            # Emit an event — do NOT call voice/log directly. Sinks decide.
            emit("write_rejected", message=f"R-19 reject: {e}", level="WARN", task=name)
            return result, []
        emit("task_done", message=f"{name}: {len(applied)} op(s) applied",
             level="INFO", task_id=name)
        for line in applied:
            print(f"✅ {line}")
        return result, applied

def main():
    if len(sys.argv) < 4:
        print("Usage: orchestrator.py <endpoint> <model> <task_file_or_prompt> [system_prompt]")
        return

    endpoint = sys.argv[1]
    model = sys.argv[2]
    task = sys.argv[3]
    sys_prompt = sys.argv[4] if len(sys.argv) > 4 else "You are an expert developer."

    orchestrator = UniversalOrchestrator(endpoint, model)

    # The untrusted-model loop starts here — freeze the cage geometry so no
    # code reached from a task can re-root scribe (R-SEAL).
    scribe.seal()
    
    if os.path.exists(task):
        with open(task, "r") as f:
            prompt = f.read()
    else:
        prompt = task

    # Inject HDS OS Context (CLAUDE.md is the canonical protocol source)
    root = Path(__file__).resolve().parent.parent
    ctx_md = root / "CLAUDE.md"
    if ctx_md.exists():
        os_context = ctx_md.read_text(encoding="utf-8")
        hds_force = (
            "\n\n[CRITICAL HDS CONSTRAINTS]\n"
            "- RULE R-19: ZERO DIRECT WRITING. Emit a task-script (JSON) and let "
            "AI-DRIVER (agent/scribe.py) perform all file operations.\n"
            "- RULE R-13: SCRIPT_FIRST implementation. All actions must be task-scripted.\n"
            "- RULE R-01: SIZE_LIMIT 1000 lines per file.\n"
            "- task-script op format: {\"op\":\"write|append|delete\",\"path\":\"...\",\"content\":\"...\"}\n"
        )
        sys_prompt += f"\n\n--- HDS OS CONTEXT ---\n{os_context}{hds_force}"

    # Parse --temp and --image if present
    temp = 0.3
    image_path = None
    if "--temp" in sys.argv:
        t_idx = sys.argv.index("--temp")
        if t_idx + 1 < len(sys.argv):
            temp = float(sys.argv[t_idx + 1])
    if "--image" in sys.argv:
        i_idx = sys.argv.index("--image")
        if i_idx + 1 < len(sys.argv):
            image_path = sys.argv[i_idx + 1]

    # --size s|m|l|xl : capability gate for the executor (default s — safest)
    protocol_size = "s"
    if "--size" in sys.argv:
        s_idx = sys.argv.index("--size")
        if s_idx + 1 < len(sys.argv):
            protocol_size = sys.argv[s_idx + 1]

    # --write : run the full locAI cycle (model emits task-script → scribe applies)
    if "--write" in sys.argv:
        result, _ = orchestrator.process_and_write(
            "Direct_Task", prompt, system=sys_prompt, temperature=temp,
            image_path=image_path, protocol_size=protocol_size)
    else:
        result = orchestrator.process_task(
            "Direct_Task", prompt, system=sys_prompt, temperature=temp, image_path=image_path)
    print("\n✅ RESULT:\n")
    print(result)

if __name__ == "__main__":
    main()
