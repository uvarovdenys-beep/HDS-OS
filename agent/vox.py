# vox.py
# HDS6 Voice/Text Notification Service with PowerVox Speech
# Authors: Denys Uvarov, Mykyta Aleksandrov, Anastasiia Uvarova

import datetime
import sys
import time
import json
import re
from pathlib import Path
from typing import Optional, Dict

try:
    from vox_speech import HDS6VoxSpeech
except ImportError:
    HDS6VoxSpeech = None


def number_to_words(n: int) -> str:
    """Convert number to words for speech."""
    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
            "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    
    if n == 0:
        return "zero"
    if n < 20:
        return ones[n]
    if n < 100:
        return tens[n // 10] + ("" if n % 10 == 0 else "-" + ones[n % 10])
    if n < 1000:
        return ones[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + number_to_words(n % 100))
    return str(n)


_TECHNICAL_PATTERNS = re.compile(
    r'Written:.*\.py|'           # file write logs
    r'ai-mind/tasks/.*\.py|'     # task file paths
    r'\[Task:\s*\w+\]|'          # [Task: XYZ] tags
    r'\(\d+ lines?\)|'           # (2 lines)
    r'R-\d+\s+VIOLATION|'        # R-01 VIOLATION etc (better as ERROR)
    r'SECURITY:\s+\w+',          # SECURITY: ... tags
    re.IGNORECASE
)

def is_technical_message(text: str) -> bool:
    """Returns True if message is purely technical — not for speech."""
    return bool(_TECHNICAL_PATTERNS.search(text))


def format_for_speech(text: str) -> str:
    """
    Format text for natural speech:
    - Remove .py extension
    - Convert leading numbers to words (050 → fifty, 051 → fifty-one)
    - Replace underscores with spaces
    """
    # Remove .py extension
    text = re.sub(r'\.py$', '', text, flags=re.IGNORECASE)
    
    # Convert leading numbers (050, 051, etc.) to words with space after
    def convert_number(match):
        num_str = match.group(1)
        suffix = match.group(2) if match.group(2) else ''
        # Remove leading zeros for conversion
        num = int(num_str)
        word = number_to_words(num)
        # Add space if there's a suffix (like underscore)
        return word + (' ' if suffix else '')
    
    # Match numbers followed by underscore, dash, or end of word
    text = re.sub(r'\b(\d{2,})([_\-]?)', convert_number, text)
    
    # Replace remaining underscores with spaces
    text = text.replace('_', ' ')
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


class VoxConfig:
    """Load PowerVox configuration."""
    
    DEFAULT_CONFIG = {
        "speech": {
            "enabled": True,
            "voice": "ryan",
            "volume": 0.8,
            "speed": 1.0
        },
        "ui": {
            "power_vox_enabled": True,
            "power_vox_pause_ms": 600
        }
    }
    
    @classmethod
    def load(cls, base_dir: Path) -> Dict:
        """Load configuration from JSON."""
        config_path = base_dir / "ai-mind" / "knowledge" / "hds6-config.json"
        
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        
        return cls.DEFAULT_CONFIG


class VoxService:
    """
    PowerVox Protocol Implementation.
    Text-based user notification about system events.
    """
    
    SOUND_SIGNAL = "[BELL]"
    PAUSE_MS = 600
    
    def __init__(self, log_dir: Path = None, enable_speech: bool = None):
        self.base_dir = Path(__file__).parent.parent.resolve()
        self.log_dir = log_dir or self.base_dir / "ai-mind" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "vox.log"
        
        # Loading configuration
        self.config = VoxConfig.load(self.base_dir)
        
        # PowerVox Speech integration (config has priority)
        config_speech_enabled = self.config.get("speech", {}).get("enabled", True)
        if enable_speech is None:
            # Use configuration
            self.speech_enabled = config_speech_enabled and HDS6VoxSpeech is not None
        else:
            # Forced parameter (override)
            self.speech_enabled = enable_speech and HDS6VoxSpeech is not None
        
        # Voice selection from config
        config_voice = self.config.get("speech", {}).get("voice", "sonia")
        self.speech = HDS6VoxSpeech(self.base_dir, voice=config_voice) if self.speech_enabled else None
        
        # Pause from config
        self.PAUSE_MS = self.config.get("ui", {}).get("power_vox_pause_ms", 600)
    
    def _timestamp(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _log(self, message: str, level: str = "INFO"):
        entry = f"[{self._timestamp()}] [{level}] {self.SOUND_SIGNAL} {message}"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
        return entry
    
    def speak(self, message: str, level: str = "INFO", use_voice: bool = None):
        """
        Main notification method. Outputs to console and log.
        
        PowerVox Protocol:
        1. Signal [BELL]
        2. Tactical Pause (600ms)
        3. Voice (if enabled)
        
        Args:
            message: Message text
            level: Level (INFO, WARN, ERROR)
            use_voice: Force voice output (None = auto from config)
        """
        entry = self._log(message, level)
        print(entry)
        
        # PowerVox Protocol Step 2: Tactical Pause
        time.sleep(self.PAUSE_MS / 1000)
        
        # PowerVox Protocol Step 3: Voice (if available)
        if use_voice is not False and self.speech_enabled and self.speech:
            if is_technical_message(message):
                return  # technical strings — log only, no voice
            try:
                self.speech.speak(message, level)
            except Exception as e:
                # Fallback to text
                print(f"[Voice unavailable: {e}]")
    
    def protocol(self, rule_code: str, description: str):
        """Announce protocol violation."""
        msg = f"PROTOCOL ALERT [{rule_code}]: {description}"
        self.speak(msg, "WARN")
    
    def task_executed(self, task_id: str, status: str):
        """Task execution message."""
        speech_id = format_for_speech(task_id)
        self.speak(f"Task {speech_id}: {status}", "INFO")
    
    def system_ready(self):
        """System loaded notification - only on first start."""
        self.speak("Agent operational. AI-DRIVER active.", "INFO")

    def anti_gravity_signal(self):
        """Special anti-gravity pulse notification."""
        self.speak("Anti-gravity stability pulse detected. HDS is floating.", "INFO")

    def hybrid_function_gf(self, function_name: str, framework: str):
        """
        Hybrid Function announcement.
        """
        self.speak(f"GF: Executing {function_name} via {framework} framework.", "INFO")

    def voice_chat_gh(self, user_text: str, agent_response: str):
        """
        Voice Chat implementation.
        Logs dialogue and voices the response.
        """
        self._log(f"USER: {user_text}", "CHAT")
        self.speak(agent_response, "CHAT")
        self.speak(f"GF: Executing {function_name} via {framework} framework.", "INFO")

    def task_starting(self, task_id: str, title: str):
        """Task started notification."""
        speech_title = format_for_speech(title)
        speech_id = format_for_speech(task_id)
        # Clean up the speech - remove directory paths and .py extensions
        clean_title = speech_title.replace('ai mind/tasks/active/', '').replace('ai-mind/tasks/active/', '')
        clean_id = speech_id.replace('ai mind/tasks/active/', '').replace('ai-mind/tasks/active/', '')
        self.speak(f"Starting task {clean_id}: {clean_title}", "INFO")

    def task_completed(self, task_id: str):
        """Task completed successfully notification."""
        speech_id = format_for_speech(task_id)
        self.speak(f"Task {speech_id} completed successfully.", "INFO")

    def task_failed_model(self, task_id: str):
        """Task requires a different model notification."""
        speech_id = format_for_speech(task_id)
        self.speak(f"Task {speech_id} execution failed. This task requires a different AI model.", "WARN")

    def all_tasks_completed(self):
        """All tasks finished notification."""
        self.speak("All tasks completed.", "INFO")

    def waiting_for_tasks(self):
        """Waiting for new tasks notification."""
        self.speak("Waiting for new tasks.", "INFO")

    def user_decision_required(self):
        """User decision required notification."""
        self.speak("User decision required to proceed.", "WARN")

    def script_execution_required(self):
        """User script execution required notification."""
        self.speak("User must execute the script to continue.", "WARN")

    def critical_user_action(self, message: str):
        """Critical message for the user."""
        self.speak(f"Critical action required: {message}", "ERROR")

if __name__ == "__main__":
    vox = VoxService()
    vox.system_ready()
    vox.speak("PowerVox Service Test Complete.")
