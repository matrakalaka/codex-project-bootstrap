import tempfile
import unittest
from pathlib import Path

from install_bootstrap_launcher import (
    EXPECTED_LAUNCHER,
    INSTALLED_LAUNCHER,
    InstallerBlocked,
    install,
)


ROOT = Path(__file__).parent.parent


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
            result = zshrc.read_bytes()
            self.assertEqual(result, prefix + INSTALLED_LAUNCHER + suffix)

    def test_fails_closed_when_launcher_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            zshrc = Path(directory) / ".zshrc"
            zshrc.write_bytes(b"export KEEP=1\n")
            with self.assertRaises(InstallerBlocked):
                install(zshrc, ROOT)
            self.assertEqual(zshrc.read_bytes(), b"export KEEP=1\n")
            self.assertEqual(list(Path(directory).iterdir()), [zshrc])

    def test_fails_closed_when_launcher_is_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            zshrc = Path(directory) / ".zshrc"
            zshrc.write_bytes(EXPECTED_LAUNCHER + EXPECTED_LAUNCHER)
            with self.assertRaises(InstallerBlocked):
                install(zshrc, ROOT)
            self.assertEqual(zshrc.read_bytes(), EXPECTED_LAUNCHER + EXPECTED_LAUNCHER)
            self.assertEqual(list(Path(directory).iterdir()), [zshrc])

    def test_installed_launcher_contains_required_boundaries(self):
        text = INSTALLED_LAUNCHER.decode()
        for phrase in (
            "https://github.com/matrakalaka/codex-project-bootstrap",
            "scripts/bootstrap_authority.py",
            "--output-dir",
            "--sandbox read-only",
            "BLOCKED_PRECONDITION",
            "stop",
            "authority_dir",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
