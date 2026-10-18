import json
import os
import stat
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentterm_bootstrap import AgentTermBootstrap, LifecycleBlocked
from open_terminal_bridge import TerminalBridgeError


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = {
    "revision": "b" * 40,
    "files": {"GLOBAL_PROJECT_BOOTSTRAP.md": "sha256:bootstrap", "PROJECT_NORTH_STAR.md": "sha256:north-star"},
}


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def make_project(root: Path) -> None:
    git(root, "init", "-q")
    (root / "README.md").write_text("synthetic\n", encoding="utf-8")
    git(root, "add", ".")
    subprocess.run(["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Bootstrap Test",
                    "commit", "-qm", "init"], cwd=root, check=True)


def health(path: Path) -> Path:
    path.write_text("#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo agentterm-bridge-test; else echo governed; fi\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class OpenTerminalBridgeTests(unittest.TestCase):
    def test_managed_session_is_selected_multiline_and_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            bridge = AgentTermBootstrap(ROOT, agentterm_command=str(health(project / "agentterm-health")))
            bridge.initialize(project, AUTHORITY)
            with self.assertRaises(TerminalBridgeError):
                bridge.terminal_open(project, mode="managed", approved=False)

            session = bridge.terminal_open(project, mode="managed", approved=True)
            self.assertEqual(session["mode"], "managed")
            try:
                with self.assertRaises(TerminalBridgeError):
                    bridge.terminal_submit(project, session_id=session["session_id"], text="echo DENIED", approved=False)
                result = bridge.terminal_submit(
                    project, session_id=session["session_id"],
                    text="printf 'line-one\\nline-two\\n'", approved=True,
                )
                self.assertEqual(result["outcome"], "PASS")
                self.assertEqual(result["returncode"], 0)
                self.assertIn("line-one", result["output"])
                self.assertIn("line-two", result["output"])
            finally:
                closed = bridge.terminal_close(project, session_id=session["session_id"], approved=True)
                self.assertEqual(closed["outcome"], "PASS")

            resumed = bridge.resume(project)
            self.assertTrue(resumed["ledger_verified"])
            with sqlite3.connect(project / ".agentterm" / "ledger.db") as connection:
                terminal_events = connection.execute(
                    "SELECT kind, body FROM events WHERE kind IN ('terminal_session', 'terminal_command')"
                ).fetchall()
            self.assertGreaterEqual(len(terminal_events), 4)
            self.assertTrue(any('BLOCKED_PRECONDITION' in body for _, body in terminal_events))
            ledger_events = json.loads((project / ".agentterm" / "bootstrap-session.json").read_text())
            self.assertEqual(ledger_events["project_root"], str(project.resolve()))

    @patch("open_terminal_bridge.subprocess.run")
    def test_native_mode_reports_new_tab_without_claiming_capture(self, run):
        run.return_value = subprocess.CompletedProcess(["osascript"], 0, stdout="tab-123\n", stderr="")
        import open_terminal_bridge
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = open_terminal_bridge.open_session(project, mode="native", approved=True)
            self.assertEqual(result["native_window_id"], "tab-123")
            self.assertFalse(result["output_capture"])
            self.assertIn("arbitrary existing-tab", result["limitation"])
            self.assertEqual(run.call_args.args[0][0], "osascript")


if __name__ == "__main__":
    unittest.main()
