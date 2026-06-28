#!/usr/bin/env python3
"""
aivc_controller.py
HDS AIVC — AI Vision & Control Controller

The autonomous loop:
  1. OBSERVE  — Vision daemon captures screen / browser state
  2. THINK    — AI model analyzes the observation, decides next action
  3. ACT      — Browser daemon executes the action (click, type, navigate)
  4. VERIFY   — Vision re-captures, AI confirms success or corrects

This is the core that turns isolated daemons into an autonomous agent.

Authors: HDS Development Team
License: HDS Standard
"""

import json
import time
import logging
import requests
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict

try:
    from vox import VoxService
except ImportError:
    VoxService = None

try:
    from protocol_enforcer import ProtocolEnforcer
except ImportError:
    ProtocolEnforcer = None

logger = logging.getLogger("aivc")

# ──────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ──────────────────────────────────────────────────────────────

class ActionType(Enum):
    NAVIGATE   = "navigate"
    CLICK      = "click"
    TYPE       = "type"
    SCROLL     = "scroll"
    SCREENSHOT = "screenshot"
    READ_DOM   = "read_dom"
    WAIT       = "wait"
    DONE       = "done"
    FAIL       = "fail"


@dataclass
class Observation:
    """What the agent sees right now."""
    timestamp: float = 0.0
    screenshot_path: str = ""
    screen_width: int = 0
    screen_height: int = 0
    elements: List[Dict] = field(default_factory=list)
    ocr_text: str = ""
    dom_markdown: str = ""
    page_title: str = ""
    page_url: str = ""
    error: str = ""


@dataclass
class Action:
    """What the agent decides to do."""
    action_type: ActionType = ActionType.DONE
    selector: str = ""
    text: str = ""
    url: str = ""
    x: float = 0.0          # relative 0.0–1.0
    y: float = 0.0          # relative 0.0–1.0
    reason: str = ""        # AI's explanation for this action


@dataclass
class StepResult:
    """Outcome of one AIVC iteration."""
    step: int = 0
    observation: Optional[Observation] = None
    action: Optional[Action] = None
    success: bool = False
    ai_reasoning: str = ""
    duration: float = 0.0


# ──────────────────────────────────────────────────────────────
# AIVC CONTROLLER
# ──────────────────────────────────────────────────────────────

class AIVCController:
    """
    Autonomous AI Vision & Control loop.

    Usage:
        ctrl = AIVCController(ai_call_fn=my_ai_fn)
        result = ctrl.execute_goal("Open github.com and find the search bar")
    """

    def __init__(
        self,
        vision_url: str = "http://127.0.0.1:9001",
        browser_url: str = "http://127.0.0.1:9002",
        ai_call_fn=None,
        max_steps: int = 15,
        timeout_per_step: float = 30.0,
        screenshot_dir: Optional[Path] = None,
        observe_mode: str = "full",  # "full" or "light"
        vox: "VoxService" = None,
        model_name: str = "unknown",
    ):
        self.vision_url = vision_url.rstrip("/")
        self.browser_url = browser_url.rstrip("/")
        self.ai_call = ai_call_fn  # callable(prompt: str) -> str
        self.max_steps = max_steps
        self.timeout = timeout_per_step
        self.screenshot_dir = screenshot_dir or Path("ai-mind/tasks/captures")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.observe_mode = observe_mode  # "light" skips vision, DOM only (~10s vs 43s)

        # Vox integration — announce actions audibly
        self.vox = vox

        # ProtocolEnforcer gate — blocks disallowed actions
        self.enforcer = ProtocolEnforcer(model_name) if ProtocolEnforcer else None

        self.history: List[StepResult] = []
        self._task_id_counter = int(time.time())

    # ──────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────

    def execute_goal(self, goal: str, context: str = "") -> Dict[str, Any]:
        """
        Execute a high-level goal autonomously.

        Args:
            goal:    Natural language description of what to achieve
            context: Optional extra context (project info, constraints)

        Returns:
            {success, steps, history, total_time, final_observation}
        """
        logger.info(f"[AIVC] Goal: {goal}")
        if self.vox:
            self.vox.speak(f"AIVC goal: {goal[:60]}", "INFO")
        start = time.time()
        self.history = []

        for step_num in range(1, self.max_steps + 1):
            step_start = time.time()
            logger.info(f"[AIVC] ── Step {step_num}/{self.max_steps} ──")

            # 1. OBSERVE
            obs = self._observe(step_num)
            if obs.error:
                logger.warning(f"[AIVC] Observation error: {obs.error}")

            # 2. THINK — ask AI what to do
            action, reasoning = self._think(goal, context, obs, step_num)
            logger.info(f"[AIVC] AI decided: {action.action_type.value} — {action.reason}")

            # 3. Check termination
            if action.action_type == ActionType.DONE:
                result = StepResult(
                    step=step_num, observation=obs, action=action,
                    success=True, ai_reasoning=reasoning,
                    duration=time.time() - step_start,
                )
                self.history.append(result)
                logger.info(f"[AIVC] ✅ Goal achieved in {step_num} steps")
                if self.vox:
                    self.vox.speak(f"Goal achieved in {step_num} steps", "SUCCESS")
                return self._make_report(True, time.time() - start)

            if action.action_type == ActionType.FAIL:
                result = StepResult(
                    step=step_num, observation=obs, action=action,
                    success=False, ai_reasoning=reasoning,
                    duration=time.time() - step_start,
                )
                self.history.append(result)
                logger.info(f"[AIVC] ❌ AI declared failure: {action.reason}")
                if self.vox:
                    self.vox.speak(f"Goal failed: {action.reason[:40]}", "ERROR")
                return self._make_report(False, time.time() - start)

            # 4. ACT
            act_ok = self._act(action, step_num)

            # 5. VERIFY — quick re-observe to capture post-action state
            post_obs = self._observe(step_num)

            result = StepResult(
                step=step_num, observation=post_obs, action=action,
                success=act_ok, ai_reasoning=reasoning,
                duration=time.time() - step_start,
            )
            self.history.append(result)

            if not act_ok:
                logger.warning(f"[AIVC] Action failed at step {step_num}, AI will re-evaluate")

        # Max steps exhausted
        logger.warning(f"[AIVC] ⚠️ Max steps ({self.max_steps}) reached without completion")
        return self._make_report(False, time.time() - start)

    # ──────────────────────────────────────────────────────────
    # 1. OBSERVE
    # ──────────────────────────────────────────────────────────

    def _observe(self, step: int) -> Observation:
        """
        Gather current state from Vision and Browser daemons.

        Two modes:
          - "full":  Vision (capture + detect + OCR) + Browser DOM (~43s)
          - "light": Browser DOM only, skip vision (~10s)

        Use light mode for simple navigation tasks where DOM is sufficient.
        Use full mode when visual element detection is needed.
        """
        obs = Observation(timestamp=time.time())
        task_id = f"aivc-{self._task_id_counter}-s{step}"

        # ── FULL MODE: Vision capture + analysis ──────────────────
        if self.observe_mode == "full":
            # Vision: capture screen
            try:
                r = requests.post(
                    f"{self.vision_url}/execute",
                    json={"type": "capture_screen", "task_id": f"{task_id}-cap"},
                    timeout=self.timeout,
                )
                if r.ok:
                    d = r.json()
                    obs.screenshot_path = d.get("filepath", "")
                    obs.screen_width = d.get("width", 0)
                    obs.screen_height = d.get("height", 0)
            except Exception as e:
                obs.error = f"Vision capture failed: {e}"

            # Vision: detect elements on the screenshot
            if obs.screenshot_path:
                try:
                    r = requests.post(
                        f"{self.vision_url}/execute",
                        json={
                            "type": "detect_elements",
                            "task_id": f"{task_id}-det",
                            "image_path": obs.screenshot_path,
                        },
                        timeout=self.timeout,
                    )
                    if r.ok:
                        d = r.json()
                        obs.elements = d.get("elements", [])
                except Exception as e:
                    logger.debug(f"Element detection error: {e}")

            # Vision: OCR
            if obs.screenshot_path:
                try:
                    r = requests.post(
                        f"{self.vision_url}/execute",
                        json={
                            "type": "analyze_image",
                            "task_id": f"{task_id}-ocr",
                            "image_path": obs.screenshot_path,
                        },
                        timeout=self.timeout,
                    )
                    if r.ok:
                        d = r.json()
                        analysis = d.get("analysis", d)
                        obs.ocr_text = (
                            analysis.get("text_content", "")
                            if isinstance(analysis, dict) else ""
                        )
                except Exception as e:
                    logger.debug(f"OCR error: {e}")
        else:
            logger.debug(f"Light observe mode — skipping vision daemon")

        # ── BOTH MODES: Browser DOM ──────────────────────────────
        try:
            r = requests.post(
                f"{self.browser_url}/execute",
                json={"type": "dom_to_markdown", "task_id": f"{task_id}-dom"},
                timeout=self.timeout,
            )
            if r.ok:
                d = r.json()
                obs.dom_markdown = d.get("markdown", "")[:3000]  # token-limit
                obs.page_title = d.get("page_title", "")
                obs.page_url = d.get("page_url", "")
        except Exception as e:
            logger.debug(f"DOM read error: {e}")

        return obs

    # ──────────────────────────────────────────────────────────
    # 2. THINK
    # ──────────────────────────────────────────────────────────

    def _think(
        self, goal: str, context: str, obs: Observation, step: int
    ) -> tuple:
        """Ask AI to decide the next action based on observation."""
        prompt = self._build_prompt(goal, context, obs, step)

        if not self.ai_call:
            logger.warning("[AIVC] No AI function set — using DONE fallback")
            return Action(action_type=ActionType.DONE, reason="No AI configured"), ""

        # Retry up to 2 times on empty/unparseable responses
        last_error = ""
        for attempt in range(3):
            try:
                raw = self.ai_call(prompt)
                if not raw or not raw.strip():
                    last_error = "AI returned empty response"
                    logger.warning(f"[AIVC] Empty AI response, retry {attempt+1}/3")
                    continue
                action, reasoning = self._parse_ai_response(raw)
                if action.action_type != ActionType.FAIL or "unparseable" not in action.reason:
                    return action, reasoning
                last_error = action.reason
                logger.warning(f"[AIVC] Unparseable response, retry {attempt+1}/3")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[AIVC] AI call error ({attempt+1}/3): {e}")

        logger.error(f"[AIVC] AI failed after 3 attempts: {last_error}")
        return Action(action_type=ActionType.FAIL, reason=f"AI error after retries: {last_error}"), ""

    def _build_prompt(
        self, goal: str, context: str, obs: Observation, step: int
    ) -> str:
        """Build structured prompt for the AI model."""

        # Summarize history (last 3 steps)
        history_text = ""
        for h in self.history[-3:]:
            a = h.action
            if a:
                history_text += (
                    f"  Step {h.step}: {a.action_type.value}"
                    f" | {'OK' if h.success else 'FAIL'}"
                    f" | {a.reason}\n"
                )

        # Summarize detected elements
        elements_text = ""
        for i, el in enumerate(obs.elements[:20]):
            etype = el.get("type", "?")
            bbox = el.get("bbox_relative", [])
            text = el.get("text", "")
            conf = el.get("confidence", 0)
            bbox_str = f"[{bbox[0]:.2f},{bbox[1]:.2f},{bbox[2]:.2f},{bbox[3]:.2f}]" if len(bbox) == 4 else "?"
            elements_text += f"  [{i}] {etype} at {bbox_str} conf={conf:.1f}"
            if text:
                elements_text += f' text="{text[:40]}"'
            elements_text += "\n"

        # DOM excerpt
        dom_excerpt = obs.dom_markdown[:1500] if obs.dom_markdown else "(no DOM available)"

        # OCR excerpt
        ocr_excerpt = obs.ocr_text[:500] if obs.ocr_text else "(no OCR text)"

        return f"""You are the AIVC (AI Vision & Control) autonomous agent for HDS.
You observe the current screen state and decide the SINGLE next action to achieve the goal.

GOAL: {goal}
{f"CONTEXT: {context}" if context else ""}

STEP: {step}/{self.max_steps}
PAGE: {obs.page_url or "(unknown)"}
PAGE TITLE: {obs.page_title or "(unknown)"}
SCREEN: {obs.screen_width}x{obs.screen_height}

PREVIOUS ACTIONS:
{history_text or "  (first step)"}

DETECTED UI ELEMENTS:
{elements_text or "  (none detected)"}

OCR TEXT ON SCREEN:
{ocr_excerpt}

PAGE DOM (markdown):
{dom_excerpt}

────────────────────────────────────
RESPOND with exactly ONE JSON object:
{{
  "action": "navigate|click|type|scroll|screenshot|read_dom|wait|done|fail",
  "selector": "CSS selector (for click/type)",
  "text": "text to type (for type action)",
  "url": "URL (for navigate action)",
  "x": 0.5,  // relative X coordinate 0.0-1.0 (for click without selector)
  "y": 0.5,  // relative Y coordinate 0.0-1.0
  "reason": "Brief explanation of WHY this action achieves the goal"
}}

RULES:
- Pick ONE action per response
- Use "done" when the goal is achieved
- Use "fail" only when the goal is impossible
- Prefer CSS selectors over coordinates for clicks
- If page hasn't loaded, use "wait"
- Be precise and concise in "reason"

Return ONLY the JSON object, no markdown, no extra text."""

    def _parse_ai_response(self, raw: str) -> tuple:
        """Parse AI response into Action + reasoning."""
        # Strip markdown code blocks if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            match_block = cleaned.split("```")
            for block in match_block:
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                if block.startswith("{"):
                    cleaned = block
                    break

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                return Action(
                    action_type=ActionType.FAIL,
                    reason=f"AI returned unparseable response: {raw[:100]}",
                ), raw

        action_str = data.get("action", "fail")
        try:
            action_type = ActionType(action_str)
        except ValueError:
            action_type = ActionType.FAIL

        action = Action(
            action_type=action_type,
            selector=data.get("selector", ""),
            text=data.get("text", ""),
            url=data.get("url", ""),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            reason=data.get("reason", ""),
        )
        return action, data.get("reason", raw[:200])

    # ──────────────────────────────────────────────────────────
    # 3. ACT
    # ──────────────────────────────────────────────────────────

    def _act(self, action: Action, step: int) -> bool:
        """Execute the decided action via Browser daemon. Enforcer + Vox integrated."""
        task_id = f"aivc-{self._task_id_counter}-act{step}"

        # ProtocolEnforcer gate
        if self.enforcer:
            action_name = action.action_type.value
            allowed, reason = self.enforcer.check_action(action_name)
            if not allowed:
                logger.warning(f"[AIVC] Enforcer blocked: {action_name} — {reason}")
                if self.vox:
                    self.vox.speak(f"Action blocked: {action_name}", "WARNING")
                return False

        # Vox announcement
        if self.vox:
            desc = action.url or action.selector or action.text or action.action_type.value
            self.vox.speak(f"Step {step}: {action.action_type.value} {desc[:40]}", "INFO")

        try:
            if action.action_type == ActionType.NAVIGATE:
                return self._browser_call({
                    "type": "navigate",
                    "task_id": task_id,
                    "url": action.url,
                })

            elif action.action_type == ActionType.CLICK:
                payload = {"type": "click", "task_id": task_id}
                if action.selector:
                    payload["selector"] = action.selector
                else:
                    # Coordinate-based click
                    payload["x"] = action.x
                    payload["y"] = action.y
                return self._browser_call(payload)

            elif action.action_type == ActionType.TYPE:
                return self._browser_call({
                    "type": "type",
                    "task_id": task_id,
                    "selector": action.selector,
                    "text": action.text,
                })

            elif action.action_type == ActionType.SCROLL:
                return self._browser_call({
                    "type": "scroll",
                    "task_id": task_id,
                    "direction": action.text or "down",
                })

            elif action.action_type == ActionType.WAIT:
                wait_time = min(float(action.text or "2"), 10.0)
                time.sleep(wait_time)
                return True

            elif action.action_type == ActionType.SCREENSHOT:
                # Just re-observe — no browser action needed
                return True

            elif action.action_type == ActionType.READ_DOM:
                # Re-observe DOM — handled in next observe step
                return True

            else:
                logger.warning(f"[AIVC] Unhandled action type: {action.action_type}")
                return False

        except Exception as e:
            logger.error(f"[AIVC] Action execution error: {e}")
            return False

    def _browser_call(self, payload: Dict) -> bool:
        """Send command to browser daemon."""
        try:
            r = requests.post(
                f"{self.browser_url}/execute",
                json=payload,
                timeout=self.timeout,
            )
            if r.ok:
                d = r.json()
                return d.get("status") != "error"
            return False
        except Exception as e:
            logger.error(f"[AIVC] Browser call failed: {e}")
            return False

    # ──────────────────────────────────────────────────────────
    # REPORT
    # ──────────────────────────────────────────────────────────

    def _make_report(self, success: bool, total_time: float) -> Dict[str, Any]:
        """Build final execution report."""
        return {
            "success": success,
            "steps": len(self.history),
            "total_time": round(total_time, 2),
            "history": [
                {
                    "step": h.step,
                    "action": h.action.action_type.value if h.action else None,
                    "reason": h.action.reason if h.action else "",
                    "success": h.success,
                    "duration": round(h.duration, 2),
                    "page_url": h.observation.page_url if h.observation else "",
                }
                for h in self.history
            ],
            "final_observation": {
                "page_url": self.history[-1].observation.page_url if self.history else "",
                "page_title": self.history[-1].observation.page_title if self.history else "",
            } if self.history else {},
        }


# ──────────────────────────────────────────────────────────────
# AI CALL ADAPTERS — connect to real AI servers
# ──────────────────────────────────────────────────────────────

def make_lmstudio_caller(
    base_url: str = "http://127.0.0.1:1234",
    model: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1024,
):
    """Create AI caller for LM Studio. Handles thinking-models (Qwen3.5) via reasoning_content fallback."""
    def call(prompt: str) -> str:
        r = requests.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content.strip() and msg.get("reasoning_content"):
            content = msg["reasoning_content"]
        return content
    return call


def make_ollama_caller(
    base_url: str = "http://127.0.0.1:11434",
    model: str = "qwen2.5:7b",
    temperature: float = 0.2,
):
    """Create AI caller for Ollama."""
    def call(prompt: str) -> str:
        r = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": 1024},
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json().get("response", "")
    return call


def make_anthropic_caller(
    api_key: str,
    model: str = "claude-sonnet-4-6-20250514",
    max_tokens: int = 1024,
):
    """Create AI caller for Anthropic Claude API."""
    def call(prompt: str) -> str:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    return call


def make_openai_caller(
    api_key: str,
    model: str = "gpt-4o",
    temperature: float = 0.2,
    max_tokens: int = 1024,
):
    """Create AI caller for OpenAI."""
    def call(prompt: str) -> str:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    return call


# ──────────────────────────────────────────────────────────────
# CLI — standalone test
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HDS AIVC Controller")
    parser.add_argument("goal", help="Goal to achieve")
    parser.add_argument("--context", default="", help="Extra context")
    parser.add_argument("--server", default="lmstudio",
                        choices=["lmstudio", "ollama", "anthropic", "openai"],
                        help="AI server to use")
    parser.add_argument("--model", default="", help="Model name")
    parser.add_argument("--api-key", default="", help="API key (for cloud providers)")
    parser.add_argument("--max-steps", type=int, default=10, help="Max AIVC steps")
    parser.add_argument("--vision-port", type=int, default=9001)
    parser.add_argument("--browser-port", type=int, default=9002)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Build AI caller
    if args.server == "lmstudio":
        ai_fn = make_lmstudio_caller(model=args.model)
    elif args.server == "ollama":
        ai_fn = make_ollama_caller(model=args.model or "qwen2.5:7b")
    elif args.server == "anthropic":
        ai_fn = make_anthropic_caller(api_key=args.api_key, model=args.model or "claude-sonnet-4-6-20250514")
    elif args.server == "openai":
        ai_fn = make_openai_caller(api_key=args.api_key, model=args.model or "gpt-4o")
    else:
        ai_fn = None

    ctrl = AIVCController(
        vision_url=f"http://127.0.0.1:{args.vision_port}",
        browser_url=f"http://127.0.0.1:{args.browser_port}",
        ai_call_fn=ai_fn,
        max_steps=args.max_steps,
    )

    result = ctrl.execute_goal(args.goal, args.context)
    print("\n" + "=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
