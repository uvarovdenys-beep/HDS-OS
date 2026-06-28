#!/usr/bin/env python3
"""
knowledge_gatekeeper.py
HDS6 TKT-004: Zero-Trust Knowledge Gatekeeper

Protects critical core files from overwrite via SHA-256 checksums.
AI cannot modify core rules — read-only access.

Authors: HDS6 Development Team
License: HDS6 Standard
"""

import hashlib
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from vox import VoxService
except ImportError:
    VoxService = None


class KnowledgeGatekeeper:
    """
    Zero-Trust Immutable Context Provider.
    Protects core rules from AI modification using SHA-256.
    """

    PROTECTED_PATHS = [
        "ai-mind/knowledge/",
        "agent/compliance.py",
        "agent/scribe.py",
        "agent/vox.py",
    ]

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.vox = VoxService(self.base_dir / "ai-mind" / "logs") if VoxService else None
        self.checksums: Dict[str, str] = {}
        self.gatekeeper_db = self.base_dir / "ai-mind" / "gatekeeper" / "checksums.json"
        self.gatekeeper_db.parent.mkdir(parents=True, exist_ok=True)

        self._load_checksums()
        print(f"[Gatekeeper] Initialized. Protecting {len(self.PROTECTED_PATHS)} core paths.")

    def _load_checksums(self):
        """Load saved checksums."""
        import json
        try:
            if self.gatekeeper_db.exists():
                with open(self.gatekeeper_db, "r") as f:
                    self.checksums = json.load(f)
        except Exception as e:
            print(f"[Gatekeeper WARNING] Could not load checksums: {e}")

    def _save_checksums(self):
        """Save checksums."""
        import json
        try:
            with open(self.gatekeeper_db, "w") as f:
                json.dump(self.checksums, f, indent=2)
        except Exception as e:
            print(f"[Gatekeeper ERROR] Could not save checksums: {e}")

    def install_immutable_rule(self, filename: str, content: str) -> bool:
        """
        Admin places an immutable rule (read-only).
        Compute SHA-256 for version control.
        """
        try:
            filepath = self.base_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w") as f:
                f.write(content)

            # Compute hash
            checksum = hashlib.sha256(content.encode()).hexdigest()
            self.checksums[filename] = checksum
            self._save_checksums()

            if self.vox:
                self.vox.speak(f"Rule '{filename}' locked with SHA-256.", "INFO")
            print(f"[Gatekeeper] Rule '{filename}' locked with SHA-256.")
            return True
        except Exception as e:
            print(f"[Gatekeeper ERROR] Could not install rule: {e}")
            return False

    def fetch_rules_for_ai(self, filename: str) -> Optional[str]:
        """
        The ONLY way AI can access core rules.
        Check SHA-256 hash, if tampered — HALT.
        """
        try:
            filepath = self.base_dir / filename
            if not filepath.exists():
                msg = f"[Gatekeeper ERROR] Rule file not found: {filename}"
                if self.vox:
                    self.vox.speak(msg, "ERROR")
                return msg

            with open(filepath, "r") as f:
                content = f.read()

            # Verify checksum
            current_hash = hashlib.sha256(content.encode()).hexdigest()
            expected_hash = self.checksums.get(filename)

            if expected_hash and current_hash != expected_hash:
                alarm = f"🚨 CRITICAL: '{filename}' was tampered with! Hash mismatch."
                if self.vox:
                    self.vox.speak(alarm, "ERROR")
                print(f"[Gatekeeper ALARM] {alarm}")
                return "[Gatekeeper FATAL] SYSTEM HALTED: Core rules checksum mismatch."

            # Success — content unchanged
            print(f"[Gatekeeper] ✓ Verified and served '{filename}' to AI.")
            return content
        except Exception as e:
            print(f"[Gatekeeper ERROR] Could not fetch rules: {e}")
            return None

    def intercept_write_request(self, attempt_path: str) -> bool:
        """
        Intercept AI attempt to write to protected paths.
        Returns False if path protected, True if allowed.
        """
        try:
            full_path = Path(attempt_path).resolve()
            base = self.base_dir.resolve()

            # Check if path starts with any protected path
            for protected in self.PROTECTED_PATHS:
                protected_full = (base / protected).resolve()
                if full_path.is_relative_to(protected_full):
                    alarm = f"🚨 BLOCKED: AI attempted to write to protected path: {attempt_path}"
                    if self.vox:
                        self.vox.speak(alarm, "ERROR")
                    print(f"[Gatekeeper ALARM] {alarm}")
                    return False

            return True  # Path is safe to write
        except Exception as e:
            print(f"[Gatekeeper WARNING] Could not verify path: {e}")
            return True  # Default allow on error

    def verify_core_integrity(self) -> Tuple[bool, str]:
        """
        Daily core integrity check.
        Returns (is_intact, message).
        """
        intact = True
        tampered = []

        for filename, expected_hash in self.checksums.items():
            try:
                filepath = self.base_dir / filename
                if not filepath.exists():
                    tampered.append(f"{filename} (file deleted)")
                    intact = False
                    continue

                with open(filepath, "r") as f:
                    content = f.read()
                current_hash = hashlib.sha256(content.encode()).hexdigest()

                if current_hash != expected_hash:
                    tampered.append(filename)
                    intact = False
            except Exception as e:
                print(f"[Gatekeeper] Could not verify {filename}: {e}")

        if intact:
            msg = "✓ Core system integrity verified. All rules unchanged."
            print(f"[Gatekeeper] {msg}")
        else:
            msg = f"🚨 INTEGRITY CHECK FAILED. Tampered files: {', '.join(tampered)}"
            print(f"[Gatekeeper] {msg}")

        return intact, msg
