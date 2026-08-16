#!/usr/bin/env python3
"""
build_certify.py
HDS Build & Certify Pipeline — automated packaging and code signing.

Handles the full build-to-release pipeline:
  1. Validate code (AST + tests)
  2. Package (pyinstaller / zipapp / wheel)
  3. Code sign (macOS codesign + notarize, Windows signtool)
  4. Create distributable (DMG / EXE / ZIP)
  5. Generate build report

Supports:
  - macOS: codesign → notarize → staple → DMG
  - Windows: signtool → EXE
  - Cross-platform: ZIP / wheel / pip package

Environment variables for signing:
  macOS:  MAC_CERT_ID, APPLE_ID_EMAIL, APPLE_APP_PASSWORD, APPLE_TEAM_ID
  Windows: WIN_CERT_PATH, WIN_CERT_PASS

Based on original concept from UAIT_PAN project.

Authors: HDS Development Team
License: HDS Standard
"""

import os
import sys
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("build_certify")


@dataclass
class BuildStep:
    """A single step in the build pipeline."""
    name: str
    command: str
    success: bool = False
    output: str = ""
    duration_seconds: float = 0.0


@dataclass
class BuildReport:
    """Full build pipeline report."""
    app_name: str
    platform: str
    version: str
    steps: List[BuildStep] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    signed: bool = False
    notarized: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = False


def run_cmd(cmd: str, capture: bool = False) -> tuple:
    """
    Execute a build command through the single exec-path (NO shell).

    argv-only via shlex (no shell injection), sandboxed when a container runtime
    is present. Returns (success: bool, output: str).
    """
    import shlex
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from sandbox.runner import SandboxRunner, RunRequest

    logger.info(f"[EXEC] {cmd}")
    parts = shlex.split(cmd)
    res = SandboxRunner().run(RunRequest(tool=parts[0], args=parts[1:], timeout=600))
    out = (res.stdout or "") + (res.stderr or "")
    if res.code != 0:
        logger.error(f"Command failed (exit {res.code}): {cmd}")
        return (False, out) if capture else (False, res.stderr or "failed")
    return (True, out) if capture else (True, "")


class BuildPipeline:
    """
    Automated build and certification pipeline for HDS components.

    Usage:
        pipeline = BuildPipeline(
            app_name="HDSAgent",
            entry_point="agent/agent.py",
            version="1.1.0",
        )
        report = pipeline.run()

        if report.success:
            print(f"Build successful! Artifacts: {report.artifacts}")
    """

    def __init__(
        self,
        app_name: str = "HDS",
        entry_point: str = "agent/agent.py",
        version: str = "1.1.0",
        icon_path: Optional[str] = None,
        dist_dir: str = "dist",
        include_tests: bool = True,
    ):
        self.app_name = app_name
        self.entry_point = entry_point
        self.version = version
        self.icon_path = icon_path
        self.dist_dir = dist_dir
        self.include_tests = include_tests
        self.platform = sys.platform
        self.report = BuildReport(
            app_name=app_name,
            platform=self.platform,
            version=version,
        )

    def _add_step(self, name: str, cmd: str) -> bool:
        """Run a build step and record result."""
        import time
        start = time.time()
        success, output = run_cmd(cmd, capture=True)
        duration = time.time() - start

        step = BuildStep(
            name=name,
            command=cmd,
            success=success,
            output=output[:2000],  # Truncate for report
            duration_seconds=round(duration, 2),
        )
        self.report.steps.append(step)

        if success:
            logger.info(f"  [{name}] OK ({duration:.1f}s)")
        else:
            logger.error(f"  [{name}] FAILED ({duration:.1f}s)")

        return success

    # ──────────────────────────────────────────────────────────
    # PHASE 1: VALIDATION
    # ──────────────────────────────────────────────────────────

    def validate(self) -> bool:
        """Run pre-build validation: syntax check + tests."""
        logger.info("Phase 1: Validation")

        # AST syntax check
        if not self._add_step(
            "syntax_check",
            f'python3 -c "import ast; ast.parse(open(\'{self.entry_point}\').read())"'
        ):
            return False

        # Run tests if enabled
        if self.include_tests:
            test_dir = "tests"
            if os.path.isdir(test_dir):
                test_files = list(Path(test_dir).glob("test_*.py"))
                for tf in test_files[:5]:  # Max 5 test files
                    self._add_step(f"test:{tf.name}", f"python3 {tf}")
            else:
                logger.info("No tests directory found, skipping tests")

        return True

    # ──────────────────────────────────────────────────────────
    # PHASE 2: PACKAGE
    # ──────────────────────────────────────────────────────────

    def package_pyinstaller(self) -> bool:
        """Package with PyInstaller (creates standalone executable)."""
        logger.info("Phase 2: Packaging with PyInstaller")

        cmd_parts = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            f"--name {self.app_name}",
        ]

        if self.platform == "darwin":
            cmd_parts.append("--windowed")
        elif self.platform == "win32":
            cmd_parts.extend(["--windowed", "--onefile"])

        if self.icon_path and os.path.exists(self.icon_path):
            cmd_parts.append(f"--icon={self.icon_path}")

        cmd_parts.append(self.entry_point)
        return self._add_step("pyinstaller", " ".join(cmd_parts))

    def package_zipapp(self) -> bool:
        """Package as a Python zipapp (.pyz) — no external tools needed."""
        logger.info("Phase 2: Packaging as zipapp")
        output = os.path.join(self.dist_dir, f"{self.app_name}.pyz")
        os.makedirs(self.dist_dir, exist_ok=True)

        cmd = f'python3 -m zipapp agent -o "{output}" -m "agent:main" -p "/usr/bin/env python3"'
        success = self._add_step("zipapp", cmd)
        if success:
            self.report.artifacts.append(output)
        return success

    def package_zip(self) -> bool:
        """Create a simple ZIP distribution."""
        logger.info("Phase 2: Creating ZIP distribution")
        output = os.path.join(self.dist_dir, f"{self.app_name}-{self.version}.zip")
        os.makedirs(self.dist_dir, exist_ok=True)

        # Include agent/, ai-mind/, and key files
        dirs_to_include = ["agent", "ai-mind", "tests", "gui"]
        files_to_include = ["start_hds.sh", "requirements.txt"]

        existing = [d for d in dirs_to_include if os.path.isdir(d)]
        existing += [f for f in files_to_include if os.path.isfile(f)]

        if existing:
            items = " ".join(existing)
            success = self._add_step("zip", f'zip -r "{output}" {items}')
            if success:
                self.report.artifacts.append(output)
            return success
        return False

    # ──────────────────────────────────────────────────────────
    # PHASE 3: CODE SIGNING
    # ──────────────────────────────────────────────────────────

    def sign_macos(self) -> bool:
        """Sign macOS app with codesign + optional notarization."""
        logger.info("Phase 3: macOS Code Signing")

        app_path = os.path.join("dist", f"{self.app_name}.app")
        cert_id = os.environ.get("MAC_CERT_ID")

        if not os.path.exists(app_path):
            logger.warning(f"App bundle not found: {app_path}")
            return False

        if cert_id:
            # Full signing with developer certificate
            success = self._add_step(
                "codesign",
                f'codesign --deep --force --verify --verbose '
                f'--options runtime --sign "{cert_id}" "{app_path}"'
            )
            if success:
                self.report.signed = True

            # Notarization
            apple_id = os.environ.get("APPLE_ID_EMAIL")
            apple_pwd = os.environ.get("APPLE_APP_PASSWORD")
            team_id = os.environ.get("APPLE_TEAM_ID")

            if apple_id and apple_pwd and team_id:
                zip_path = os.path.join("dist", f"{self.app_name}.zip")
                self._add_step(
                    "archive_for_notarize",
                    f'/usr/bin/ditto -c -k --keepParent "{app_path}" "{zip_path}"'
                )
                notarize_ok = self._add_step(
                    "notarize",
                    f'xcrun notarytool submit "{zip_path}" '
                    f'--apple-id "{apple_id}" --password "{apple_pwd}" '
                    f'--team-id "{team_id}" --wait'
                )
                if notarize_ok:
                    self._add_step("staple", f'xcrun stapler staple "{app_path}"')
                    self.report.notarized = True
            else:
                logger.info("Notarization skipped (missing APPLE_ID_EMAIL / APPLE_APP_PASSWORD / APPLE_TEAM_ID)")
        else:
            # Ad-hoc signing (local only)
            logger.info("No MAC_CERT_ID — using ad-hoc signing")
            self._add_step("codesign_adhoc", f'codesign --force --deep -s - "{app_path}"')

        return True

    def sign_windows(self) -> bool:
        """Sign Windows EXE with signtool."""
        logger.info("Phase 3: Windows Code Signing")

        exe_path = os.path.join("dist", f"{self.app_name}.exe")
        pfx_path = os.environ.get("WIN_CERT_PATH")
        pfx_pass = os.environ.get("WIN_CERT_PASS")

        if not os.path.exists(exe_path):
            logger.warning(f"EXE not found: {exe_path}")
            return False

        if pfx_path and pfx_pass:
            success = self._add_step(
                "signtool",
                f'signtool sign /f "{pfx_path}" /p "{pfx_pass}" '
                f'/tr http://timestamp.digicert.com /td sha256 /fd sha256 "{exe_path}"'
            )
            if success:
                self.report.signed = True
            return success
        else:
            logger.info("Windows signing skipped (missing WIN_CERT_PATH / WIN_CERT_PASS)")
            return True

    # ──────────────────────────────────────────────────────────
    # PHASE 4: DISTRIBUTABLE
    # ──────────────────────────────────────────────────────────

    def create_dmg(self) -> bool:
        """Create macOS DMG disk image."""
        logger.info("Phase 4: Creating DMG")

        app_path = os.path.join("dist", f"{self.app_name}.app")
        dmg_path = os.path.join("dist", f"{self.app_name}-{self.version}.dmg")

        if not os.path.exists(app_path):
            return False

        if os.path.exists(dmg_path):
            os.remove(dmg_path)

        success = self._add_step(
            "dmg",
            f'hdiutil create -volname "{self.app_name} v{self.version}" '
            f'-srcfolder "{app_path}" -ov -format UDZO "{dmg_path}"'
        )

        if success:
            self.report.artifacts.append(dmg_path)

            # Sign DMG if cert available
            cert_id = os.environ.get("MAC_CERT_ID")
            if cert_id:
                self._add_step("sign_dmg", f'codesign --force --sign "{cert_id}" "{dmg_path}"')

        return success

    # ──────────────────────────────────────────────────────────
    # MAIN PIPELINE
    # ──────────────────────────────────────────────────────────

    def run(self, mode: str = "zip") -> BuildReport:
        """
        Run the full build pipeline.

        Args:
            mode: "zip" (simple), "pyinstaller" (standalone), "zipapp" (python)

        Returns:
            BuildReport with all results
        """
        logger.info(f"{'=' * 60}")
        logger.info(f"HDS Build Pipeline: {self.app_name} v{self.version}")
        logger.info(f"Platform: {self.platform} | Mode: {mode}")
        logger.info(f"{'=' * 60}")

        # Phase 1: Validate
        self.validate()

        # Phase 2: Package
        if mode == "pyinstaller":
            self.package_pyinstaller()
        elif mode == "zipapp":
            self.package_zipapp()
        else:
            self.package_zip()

        # Phase 3: Sign (if applicable)
        if mode == "pyinstaller":
            if self.platform == "darwin":
                self.sign_macos()
            elif self.platform == "win32":
                self.sign_windows()

        # Phase 4: Distributable
        if mode == "pyinstaller" and self.platform == "darwin":
            self.create_dmg()

        # Final status
        failed_steps = [s for s in self.report.steps if not s.success]
        self.report.success = len(failed_steps) == 0

        # Save report
        self._save_report()

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Build {'SUCCESSFUL' if self.report.success else 'FAILED'}")
        logger.info(f"Steps: {len(self.report.steps)} total, {len(failed_steps)} failed")
        logger.info(f"Artifacts: {self.report.artifacts}")
        logger.info(f"{'=' * 60}")

        return self.report

    def _save_report(self):
        """Save build report to JSON."""
        report_path = os.path.join(self.dist_dir, "build_report.json")
        os.makedirs(self.dist_dir, exist_ok=True)

        data = {
            "app_name": self.report.app_name,
            "version": self.report.version,
            "platform": self.report.platform,
            "success": self.report.success,
            "signed": self.report.signed,
            "notarized": self.report.notarized,
            "artifacts": self.report.artifacts,
            "timestamp": self.report.timestamp,
            "steps": [
                {
                    "name": s.name,
                    "success": s.success,
                    "duration": s.duration_seconds,
                }
                for s in self.report.steps
            ],
        }

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Build report saved: {report_path}")
        except OSError as e:
            logger.error(f"Failed to save build report: {e}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(
        description="HDS Build & Certify Pipeline"
    )
    parser.add_argument(
        "--name", default="HDS",
        help="Application name (default: HDS)"
    )
    parser.add_argument(
        "--entry", default="agent/agent.py",
        help="Entry point script (default: agent/agent.py)"
    )
    parser.add_argument(
        "--version", default="1.1.0",
        help="Version string (default: 1.1.0)"
    )
    parser.add_argument(
        "--mode", choices=["zip", "pyinstaller", "zipapp"],
        default="zip",
        help="Build mode (default: zip)"
    )
    parser.add_argument(
        "--icon", default=None,
        help="Path to icon file"
    )
    parser.add_argument(
        "--no-tests", action="store_true",
        help="Skip running tests"
    )
    args = parser.parse_args()

    pipeline = BuildPipeline(
        app_name=args.name,
        entry_point=args.entry,
        version=args.version,
        icon_path=args.icon,
        include_tests=not args.no_tests,
    )

    report = pipeline.run(mode=args.mode)
    sys.exit(0 if report.success else 1)
