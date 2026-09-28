from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import install_bootstrap_launcher_windows as installer


ROOT = Path(__file__).resolve().parents[1]

HISTORICAL_LAUNCHER = (
    b"function codex-bootstrap {\n"
    b"    codex --sandbox read-only 'Initialize this project using the canonical bootstrap repository:\n"
    b"\n"
    b"https://github.com/matrakalaka/codex-project-bootstrap\n"
    b"\n"
    b"Read GLOBAL_PROJECT_BOOTSTRAP.md first. Perform READ-ONLY discovery only, respect existing project authority, return the PROJECT BOOTSTRAP ASSESSMENT, and stop at the human-approval gate.'\n"
    b"}"
)


class WindowsLauncherInstallerTests(unittest.TestCase):
    def install(self, profile: Path) -> Path | None:
        with patch.object(installer, "verify_repository"):
            return installer.install(profile, ROOT)

    def test_historical_fixture_is_the_profile_derived_pattern(self):
        self.assertEqual(
            hashlib.sha256(HISTORICAL_LAUNCHER).hexdigest(),
            installer.HISTORICAL_LAUNCHER_SHA256,
        )

    def test_repository_verification_accepts_current_canonical_checkout(self):
        resolver = installer.verify_repository(ROOT)
        self.assertEqual(resolver, ROOT / "scripts" / "bootstrap_authority.py")

    def test_clean_profile_install(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "Microsoft.PowerShell_profile.ps1"
            original = b"$env:KEEP = 'yes'\n"
            profile.write_bytes(original)
            backup = self.install(profile)
            self.assertIsNotNone(backup)
            self.assertEqual(backup.read_bytes(), original)
            self.assertTrue(profile.read_bytes().startswith(original))
            self.assertEqual(len(installer._function_blocks(profile.read_bytes())), 1)

    def test_historical_launcher_upgrade_preserves_prefix_and_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.ps1"
            prefix = b"$prefix = 1\n\n"
            suffix = b"\n$ suffix = 2\n"
            original = prefix + HISTORICAL_LAUNCHER + suffix
            profile.write_bytes(original)
            backup = self.install(profile)
            self.assertEqual(backup.read_bytes(), original)
            updated = profile.read_bytes()
            self.assertTrue(updated.startswith(prefix))
            self.assertTrue(updated.endswith(suffix))
            self.assertEqual(installer._recognized(installer._function_blocks(updated)[0]), "current")

    def test_current_launcher_is_idempotent_without_backup_or_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.ps1"
            original = b"$prefix = 1\n" + installer.INSTALLED_LAUNCHER + b"\n$suffix = 2\n"
            profile.write_bytes(original)
            self.assertIsNone(self.install(profile))
            self.assertEqual(profile.read_bytes(), original)
            self.assertEqual(list(profile.parent.iterdir()), [profile])

    def test_crlf_current_launcher_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.ps1"
            current = installer.INSTALLED_LAUNCHER.replace(b"\n", b"\r\n")
            profile.write_bytes(current)
            self.assertIsNone(self.install(profile))
            self.assertEqual(profile.read_bytes(), current)

    def test_unknown_or_modified_launcher_is_rejected_without_change(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.ps1"
            original = HISTORICAL_LAUNCHER.replace(b"read-only", b"read-write")
            profile.write_bytes(original)
            with self.assertRaises(installer.InstallerBlocked):
                self.install(profile)
            self.assertEqual(profile.read_bytes(), original)
            self.assertEqual(list(profile.parent.iterdir()), [profile])

    def test_duplicate_launchers_are_rejected_without_change(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.ps1"
            original = HISTORICAL_LAUNCHER + b"\n" + HISTORICAL_LAUNCHER
            profile.write_bytes(original)
            with self.assertRaises(installer.InstallerBlocked):
                self.install(profile)
            self.assertEqual(profile.read_bytes(), original)
            self.assertEqual(list(profile.parent.iterdir()), [profile])

    def test_backup_collision_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.ps1"
            original = b"$keep = 1\n"
            profile.write_bytes(original)
            collision = Path(directory) / "collision.backup"
            collision.write_bytes(b"do-not-overwrite")
            with patch.object(installer, "_backup_path", return_value=collision):
                with self.assertRaises(installer.InstallerBlocked):
                    self.install(profile)
            self.assertEqual(profile.read_bytes(), original)
            self.assertEqual(collision.read_bytes(), b"do-not-overwrite")

    def test_launcher_uses_canonical_git_and_preserves_cwd(self):
        text = installer.INSTALLED_LAUNCHER.decode()
        self.assertIn("git clone --depth 1 --no-tags --branch $canonicalRef", text)
        self.assertIn("--source-dir $canonicalCheckout", text)
        self.assertIn("--sandbox read-only", text)
        self.assertNotIn("Set-Location", text)
        self.assertNotIn("canonical_revision=", text)
        self.assertNotIn("/Users/", text)
        self.assertNotIn(".zshrc", text)

    def test_launcher_has_verified_fallback_and_fail_closed_paths(self):
        text = installer.INSTALLED_LAUNCHER.decode()
        self.assertIn("CODEX_BOOTSTRAP_CACHE", text)
        self.assertIn("CODEX_BOOTSTRAP_RESOLVER", text)
        self.assertIn("Get-FileHash", text)
        self.assertIn("canonical resolver unavailable or divergent", text)
        self.assertIn("verified historical fallback", text)
        self.assertIn("PROJECT BOOTSTRAP ASSESSMENT", text)
        self.assertIn("human-approval gate", text)


if __name__ == "__main__":
    unittest.main()
