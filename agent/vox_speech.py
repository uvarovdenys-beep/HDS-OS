#!/usr/bin/env python3
"""
vox_speech.py
HDS6 PowerVox Speech Module - Якісна британська озвучка

Authors: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна
License: HDS6 Standard

Призначення:
- Високоякісна британська озвучка системних повідомлень
- Інтеграція з Microsoft Edge TTS (Neural Voices)
- Fallback на системний TTS
- PowerVox Protocol: Signal -> Pause -> Message

Вимоги:
  pip install edge-tts  # Основний high-quality engine
  # або
  pip install pyttsx3  # Fallback локальний engine

Використання:
  python vox_speech.py "System operational"  # Озвучити текст
  python vox_speech.py --test                 # Тест голосів
  python vox_speech.py --announce            # Системне привітання
"""

import os
import sys
import time
import asyncio
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

try:
    from vox import VoxService
except ImportError:
    VoxService = None


@dataclass
class VoiceProfile:
    """Профіль голосу."""
    name: str
    language: str
    region: str
    gender: str
    quality: str
    engine: str  # 'edge', 'system', 'azure'


class HDS6VoxSpeech:
    """
    PowerVox Speech Engine - Якісна британська озвучка.
    
    Пріоритет движків (за замовчуванням EDGE - якісний звук):
    1. Microsoft Edge TTS (Neural) - найвища якість, британський акцент
    2. System TTS (SAPI5) - локальний fallback
    3. Тільки текст - fallback
    """
    
    # Британські голоси (British English)
    BRITISH_VOICES = {
        "sonia": VoiceProfile("en-GB-SoniaNeural", "en", "GB", "Female", "Neural-HD", "edge"),
        "ryan": VoiceProfile("en-GB-RyanNeural", "en", "GB", "Male", "Neural-HD", "edge"),
        "libby": VoiceProfile("en-GB-LibbyNeural", "en", "GB", "Female", "Neural", "edge"),
        "abbie": VoiceProfile("en-GB-AbbieNeural", "en", "GB", "Female", "Neural", "edge"),
        # System default (auto-detected)
        "system_gb": VoiceProfile("system-default", "en", "GB", "Auto", "Standard", "system"),
    }
    
    # PowerVox Protocol константи
    SIGNAL_SOUND = "[SYSTEM BELL]"  # Можна замінити на реальний звуковий файл
    TACTICAL_PAUSE_MS = 600  # 600ms як в специфікації
    DEFAULT_VOICE = "ryan"  # Британський голос Ryan (Neural-HD) за замовчуванням
    
    def __init__(self, base_dir: Path = None, voice: str = None, prefer_system: bool = False):
        self.base_dir = base_dir or Path(__file__).parent.parent.resolve()
        self.selected_voice = voice or self.DEFAULT_VOICE
        self.prefer_system = prefer_system  # За замовчуванням Edge TTS для якості
        self.vox = VoxService(self.base_dir / "ai-mind" / "logs") if VoxService else None
        
        # Перевірка доступних движків
        self.edge_available = self._check_edge_tts()
        self.system_available = self._check_system_tts()
        
        # Вибір голосового профілю з урахуванням пріоритету - Edge TTS для якості
        if self.edge_available and not self.prefer_system:
            self.voice_profile = self.BRITISH_VOICES.get(self.selected_voice, self.BRITISH_VOICES["ryan"])
            self._notify("Using Edge TTS (British Neural) - High Quality", "INFO")
        elif self.system_available and self.prefer_system:
            self.voice_profile = self.BRITISH_VOICES.get("system_gb", self.BRITISH_VOICES["system_gb"])
            self._notify("Using SYSTEM TTS (offline mode)", "INFO")
        else:
            self.voice_profile = self.BRITISH_VOICES.get(self.selected_voice, self.BRITISH_VOICES["sonia"])
            if self.edge_available:
                self._notify("Using Edge TTS (online mode)", "INFO")
        
        # Тимчасова тека для аудіо
        self.temp_dir = Path(tempfile.gettempdir()) / "hds6_vox"
        self.temp_dir.mkdir(exist_ok=True)
        
    def _notify(self, message: str, level: str = "INFO"):
        """Логування."""
        if self.vox:
            self.vox.speak(message, level)
        else:
            print(f"[{level}] {message}")
    
    def _check_edge_tts(self) -> bool:
        """Перевірка наявності edge-tts."""
        try:
            import edge_tts
            return True
        except ImportError:
            return False
    
    def _check_system_tts(self) -> bool:
        """Перевірка наявності системного TTS."""
        try:
            import pyttsx3
            return True
        except ImportError:
            return False
    
    def _play_audio_file(self, filepath: Path) -> bool:
        """Відтворення аудіо файлу (MP3/WAV) без відкриття вікон."""
        try:
            if os.name == "nt":  # Windows
                abs_path = str(filepath.resolve())
                # Використання System.Media.MediaPlayer через PowerShell (без візуального інтерфейсу)
                ps_cmd = (
                    f"Add-Type -AssemblyName presentationCore; "
                    f"$player = New-Object system.windows.media.mediaplayer; "
                    f"$player.open('{abs_path}'); "
                    f"$player.Play(); "
                    f"Start-Sleep -Milliseconds 100; "
                    f"while ($player.NaturalDuration -eq $null -or $player.Position -lt $player.NaturalDuration.TimeSpan) {{ Start-Sleep -Milliseconds 200 }}"
                )
                subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd], 
                                capture_output=True, check=True)
                return True
            else:  # Linux/Mac
                # Використання available player
                for player in ["paplay", "aplay", "afplay"]:
                    try:
                        subprocess.run([player, str(filepath)], check=True, capture_output=True)
                        return True
                    except:
                        continue
            return True
        except Exception as e:
            self._notify(f"Audio playback failed: {e}", "WARN")
            return False
    
    async def _edge_tts_speak(self, text: str) -> bool:
        """
        Озвучка через Microsoft Edge TTS (Neural).
        Найвища якість, британський акцент.
        """
        if not self.edge_available:
            return False
        
        try:
            import edge_tts
            
            # Створення унікального імені файлу
            timestamp = datetime.now().strftime("%H%M%S")
            temp_file = self.temp_dir / f"hds6_vox_{timestamp}.mp3"
            
            # Генерація аудіо
            communicate = edge_tts.Communicate(text, self.voice_profile.name)
            await communicate.save(str(temp_file))
            
            # Відтворення
            if temp_file.exists():
                success = self._play_audio_file(temp_file)
                # Очищення
                temp_file.unlink(missing_ok=True)
                return success
            
            return False
            
        except Exception as e:
            self._notify(f"Edge TTS failed: {e}", "WARN")
            return False
    
    def _system_tts_speak(self, text: str) -> bool:
        """
        Озвучка через системний TTS (SAPI5) через subprocess.
        За замовчуванням використовується для офлайн режиму.
        """
        if not self.system_available:
            return False
        
        try:
            import subprocess
            import sys
            import os
            
            # Викликаємо окремий процес для TTS (уникаємо "run loop already started")
            script_path = Path(__file__).parent / "vox_system_tts.py"
            
            # Windows: DETACHED_PROCESS щоб не блокувати
            if os.name == 'nt':
                subprocess.Popen(
                    [sys.executable, str(script_path), text],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(script_path), text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            return True
            
        except Exception as e:
            self._notify(f"System TTS subprocess error: {e}", "DEBUG")
            return False
    
    def _clean_text(self, text: str) -> str:
        """
        Очищення тексту перед озвучкою.
        Замінює символи '_' та '-' на пробіли, щоб вони не озвучувались.
        """
        if not text:
            return ""
        # Заміна '_' та '-' на пробіли
        cleaned = text.replace("_", " ").replace("-", " ")
        return cleaned

    def speak(self, text: str, level: str = "INFO") -> bool:
        """
        Повний PowerVox Protocol:
        1. Signal
        2. Tactical Pause (600ms)
        3. British Voice Message
        
        Args:
            text: Текст для озвучки
            level: Рівень повідомлення (INFO, WARN, ERROR)
        
        Returns:
            True якщо озвучка успішна
        """
        # Очищення тексту від символів _ та -
        cleaned_text = self._clean_text(text)
        
        # Логування (завжди оригінальний текст)
        if self.vox:
            self.vox.speak(text, level)
        
        print(f"[BELL] {cleaned_text}")  # Візуальний сигнал
        
        # PowerVox Protocol Step 1: Signal
        # (Можна додати реальний звуковий сигнал тут)
        
        # PowerVox Protocol Step 2: Tactical Pause
        time.sleep(self.TACTICAL_PAUSE_MS / 1000)
        
        # PowerVox Protocol Step 3: Voice
        success = False
        
        # Спроба Edge TTS (найвища якість, британський голос)
        if self.edge_available:
            try:
                success = asyncio.run(self._edge_tts_speak(cleaned_text))
                if success:
                    self._notify(f"Spoke (Edge TTS): {cleaned_text[:50]}...")
                    return True
            except Exception as e:
                self._notify(f"Edge TTS failed: {e}", "WARN")
        
        # Fallback на System TTS (локальний, офлайн)
        if not success and self.system_available:
            try:
                success = self._system_tts_speak(cleaned_text)
                if success:
                    self._notify(f"Spoke (System TTS): {cleaned_text[:50]}...")
                    return True
            except Exception as e:
                self._notify(f"System TTS failed: {e}", "WARN")
        
        # Останній fallback - тільки текст
        if not success:
            print(f"[VOX: {self.voice_profile.name}] {cleaned_text}")
            self._notify(f"Text-only (TTS unavailable): {cleaned_text[:50]}...", "WARN")
        
        return success
    
    def system_announcement(self) -> bool:
        """Системне привітання при старті."""
        announcement = "HDS6 Agent Nucleus operational. Monitoring active."
        return self.speak(announcement, "INFO")
    
    def protocol_alert(self, rule_code: str, description: str) -> bool:
        """Оголошення порушення протоколу з відповідним тоном."""
        text = f"Protocol Alert {rule_code}. {description}"
        return self.speak(text, "WARN")
    
    def task_complete(self, task_id: str) -> bool:
        """Оголошення виконання задачі."""
        text = f"Task {task_id} executed successfully."
        return self.speak(text, "INFO")
    
    def list_available_voices(self) -> List[VoiceProfile]:
        """Список доступних голосів."""
        available = []
        
        # Edge TTS voices
        if self.edge_available:
            available.extend([
                self.BRITISH_VOICES["sonia"],
                self.BRITISH_VOICES["ryan"],
                self.BRITISH_VOICES["libby"],
            ])
        
        # System voices
        if self.system_available:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                voices = engine.getProperty('voices')
                for v in voices:
                    if 'en-GB' in v.id or 'British' in v.name:
                        available.append(VoiceProfile(
                            v.id, "en", "GB", "Unknown", "System", "system"
                        ))
            except:
                pass
        
        return available
    
    def test_all_voices(self):
        """Тест всіх доступних голосів."""
        test_text = "HDS6 PowerVox test. System operational."
        
        print("=" * 60)
        print("HDS6 PowerVox Voice Test")
        print("=" * 60)
        print(f"Test phrase: '{test_text}'")
        print("=" * 60)
        
        voices = self.list_available_voices()
        
        if not voices:
            print("No TTS voices available. Install edge-tts or pyttsx3.")
            return
        
        for voice in voices:
            print(f"\nTesting: {voice.name} ({voice.engine})")
            print(f"  Language: {voice.language}-{voice.region}")
            print(f"  Quality: {voice.quality}")
            
            if voice.engine == "edge":
                self.voice_profile = voice
                try:
                    asyncio.run(self._edge_tts_speak(test_text))
                    print("  [OK] Edge TTS played")
                except Exception as e:
                    print(f"  [FAIL] {e}")
            elif voice.engine == "system":
                try:
                    self._system_tts_speak(test_text)
                    print("  [OK] System TTS played")
                except Exception as e:
                    print(f"  [FAIL] {e}")
            
            time.sleep(1)  # Пауза між тестами
        
        print("\n" + "=" * 60)
        print("Voice test complete")
        print("=" * 60)


def main():
    """CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="HDS6 PowerVox Speech - Quality British Voice",
        epilog="Requires: pip install edge-tts (high quality) or pyttsx3 (fallback)"
    )
    
    parser.add_argument("text", nargs="?", default=None,
                       help="Text to speak")
    parser.add_argument("--test", action="store_true",
                       help="Test all available voices")
    parser.add_argument("--announce", action="store_true",
                       help="System announcement")
    parser.add_argument("--voice", default="sonia",
                       choices=["sonia", "ryan", "libby", "abbie"],
                       help="Select British voice (default: sonia)")
    parser.add_argument("--check", action="store_true",
                       help="Check TTS availability")
    
    args = parser.parse_args()
    
    vox = HDS6VoxSpeech(voice=args.voice)
    
    if args.check:
        print("HDS6 PowerVox Speech Check")
        print("=" * 40)
        print(f"Edge TTS (Neural): {'Available' if vox.edge_available else 'Not installed'}")
        print(f"System TTS (SAPI5): {'Available' if vox.system_available else 'Not installed'}")
        print(f"Selected voice: {vox.voice_profile.name}")
        print(f"Quality: {vox.voice_profile.quality}")
        print("=" * 40)
        
    elif args.test:
        vox.test_all_voices()
        
    elif args.announce:
        vox.system_announcement()
        
    elif args.text:
        vox.speak(args.text)
        
    else:
        parser.print_help()
        print("\nExamples:")
        print('  python vox_speech.py "System ready"')
        print('  python vox_speech.py --voice ryan --announce')
        print('  python vox_speech.py --test')


if __name__ == "__main__":
    main()
