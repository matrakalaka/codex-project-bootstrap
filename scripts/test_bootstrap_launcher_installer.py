import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from install_bootstrap_launcher import (
    CANONICAL_REPOSITORY,
    EXPECTED_LAUNCHER,
    INSTALLED_LAUNCHER,
    InstallerBlocked,
    VERIFIED_FALLBACK_RESOLVER_SHA256,
    install,
    verify_repository,
)


ROOT = Path(__file__).parent.parent
PUBLISHED_RESOLVER_SHA256 = "b2a307b5d8c29604e652941e63df0bda77ae16e17cc6d5332e7ea03f7cd4ad84"


class BootstrapLauncherInstallerTests(unittest.TestCase):
    def test_replaces_only_expected_launcher_and_creates_backup(self):
        prefix = b"export KEEP_BEFORE=1\n"
        suffix = b"export KEEP_AFTER=2\n"
        with tempfile.TemporaryDirectory() as directory:
            zshrc = Path(directory) / ".zshrc"
            zshrc.write_bytes(prefix + EXPECTED_LAUNCHER + suffix)
            original = zshrc.read_bytes()
            backup = install(zshrc, ROOT)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(zshrc.read_bytes(), prefix + INSTALLED_LAUNCHER + suffix)

    def test_fails_closed_when_launcher_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            zshrc = Path(directory) / ".zshrc"
            zshrc.write_bytes(b"export KEEP=1\n")
            with self.assertRaises(InstallerBlocked):
                install(zshrc, ROOT)
            self.assertEqual(list(Path(directory).iterdir()), [zshrc])

    def test_fails_closed_when_launcher_is_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            zshrc = Path(directory) / ".zshrc"
            zshrc.write_bytes(EXPECTED_LAUNCHER + EXPECTED_LAUNCHER)
            with self.assertRaises(InstallerBlocked):
                install(zshrc, ROOT)
            self.assertEqual(list(Path(directory).iterdir()), [zshrc])

    def test_generated_launcher_uses_git_ref_and_observes_source_snapshot(self):
        text = INSTALLED_LAUNCHER.decode()
        self.assertIn(f'canonical_repository="{CANONICAL_REPOSITORY}.git"', text)
        self.assertIn('canonical_ref="main"', text)
        self.assertIn("git clone --depth 1 --no-tags --branch", text)
        self.assertIn("--source-dir", text)
        self.assertNotIn("raw.githubusercontent.com", text)
        self.assertNotIn("canonical_revision=", text)

    def test_historical_fallback_hash_is_verified(self):
        self.assertEqual(VERIFIED_FALLBACK_RESOLVER_SHA256, PUBLISHED_RESOLVER_SHA256)

    def test_git_clone_failure_stops_without_arbitrary_local_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = root / "launcher.zsh"
            launcher.write_bytes(INSTALLED_LAUNCHER)
            fake_git = root / "git"
            fake_git.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake_git.chmod(0o755)
            result = subprocess.run(
                ["zsh", "-f", "-c", f"source {launcher}; codex-bootstrap"],
                env={**os.environ, "PATH": f"{root}:{os.environ['PATH']}"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("canonical resolver unavailable or divergent", result.stdout + result.stderr)

    def test_successful_launcher_preserves_target_cwd_and_dirty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            dirty_file = target / "preexisting-work.txt"
            dirty_file.write_text("protected dirty work\n", encoding="utf-8")
            launcher = root / "launcher.zsh"
            launcher.write_bytes(INSTALLED_LAUNCHER)
            fake_git = root / "git"
            fake_git.write_text(
                "#!/bin/sh\n"
                "destination=\"$8\"\n"
                "mkdir -p \"$destination/scripts\"\n"
                f"cp {ROOT / 'scripts/bootstrap_authority.py'} \"$destination/scripts/bootstrap_authority.py\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)
            fake_python = root / "python3"
            fake_python.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' '{\"source\":\"canonical_git\",\"revision\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}'\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            fake_codex = root / "codex"
            cwd_log = root / "codex-cwd"
            fake_codex.write_text(f"#!/bin/sh\npwd > {cwd_log}\nexit 0\n", encoding="utf-8")
            fake_codex.chmod(0o755)

            result = subprocess.run(
                ["zsh", "-f", "-c", f"source {launcher}; codex-bootstrap"],
                cwd=target,
                env={**os.environ, "PATH": f"{root}:{os.environ['PATH']}"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(cwd_log.read_text(encoding="utf-8").strip(), str(target.resolve()))
            self.assertEqual(dirty_file.read_text(encoding="utf-8"), "protected dirty work\n")
            self.assertEqual(sorted(path.name for path in target.iterdir()), [dirty_file.name])

    def test_installer_accepts_normal_future_head(self):
        with tempfile.TemporaryDirectory() as directory:
            resolver = Path(directory) / "scripts" / "bootstrap_authority.py"
            resolver.parent.mkdir()
            resolver.write_text("# resolver\n", encoding="utf-8")
            with patch(
                "install_bootstrap_launcher._run_git",
                side_effect=[CANONICAL_REPOSITORY, "a" * 40, ""],
            ):
                self.assertEqual(verify_repository(Path(directory)), resolver)

    def test_installer_accepts_sequential_n_to_n_plus_one_publications(self):
        with tempfile.TemporaryDirectory() as directory:
            resolver = Path(directory) / "scripts" / "bootstrap_authority.py"
            resolver.parent.mkdir()
            resolver.write_text("# resolver\n", encoding="utf-8")
            for revision in ("b" * 40, "c" * 40):
                with patch(
                    "install_bootstrap_launcher._run_git",
                    side_effect=[CANONICAL_REPOSITORY, revision, ""],
                ):
                    self.assertEqual(verify_repository(Path(directory)), resolver)

    def test_installer_rejects_missing_resolver_from_head(self):
        with tempfile.TemporaryDirectory() as directory:
            resolver = Path(directory) / "scripts" / "bootstrap_authority.py"
            resolver.parent.mkdir()
            resolver.write_text("# resolver\n", encoding="utf-8")
            with patch(
                "install_bootstrap_launcher._run_git",
                side_effect=[CANONICAL_REPOSITORY, "a" * 40, subprocess.CalledProcessError(1, "git")],
            ):
                with self.assertRaises(InstallerBlocked):
                    verify_repository(Path(directory))


if __name__ == "__main__":
    unittest.main()
