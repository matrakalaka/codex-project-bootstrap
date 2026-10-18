import json
import io
import os
import stat
import sqlite3
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentterm_bootstrap import AgentTermBootstrap, LifecycleBlocked
from open_terminal_bridge import TerminalBridgeError
import open_terminal_bridge


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
    @classmethod
    def setUpClass(cls):
        cls.managed_socket_available = True
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "probe.sock"
            try:
                server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                server.bind(str(probe))
                server.close()
            except PermissionError:
                try:
                    server.close()
                except UnboundLocalError:
                    pass
                cls.managed_socket_available = False

    def setUp(self):
        if not self.managed_socket_available and self._testMethodName not in {
            "test_native_mode_reports_new_tab_without_claiming_capture",
            "test_managed_socket_name_stays_within_macos_path_limit",
            "test_deep_project_path_does_not_enter_socket_address",
            "test_runtime_symlink_is_rejected",
            "test_concurrent_runtime_paths_are_distinct",
            "test_startup_diagnostics_are_bounded_and_non_secret",
            "test_socket_collision_is_rejected_without_overwrite",
        }:
            self.skipTest("host sandbox denies AF_UNIX bind; managed PTY evidence is unverified")

    def test_managed_session_is_selected_multiline_and_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            bridge = AgentTermBootstrap(ROOT, agentterm_command=str(health(project / "agentterm-health")))
            bridge.initialize(project, AUTHORITY)
            with self.assertRaises(TerminalBridgeError):
                bridge.terminal_open(project, mode="managed", approved=False)

            with patch.dict(os.environ, {"CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR": str(project / "socket-dir")}):
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
                self.assertEqual(closed["outcome"], "CLOSED")

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

    def test_direct_socket_without_capability_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            bridge = AgentTermBootstrap(ROOT, agentterm_command=str(health(project / "agentterm-health")))
            bridge.initialize(project, AUTHORITY)
            with patch.dict(os.environ, {"CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR": str(project / "socket-dir")}):
                session = bridge.terminal_open(project, mode="managed", approved=True)
                try:
                    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    client.settimeout(2)
                    client.connect(session["socket"])
                    client.sendall(b'{"type":"submit","text":"touch SHOULD_NOT_EXIST","timeout":1}\n')
                    response = json.loads(client.recv(4096).decode())
                    self.assertEqual(response["outcome"], "UNAUTHORIZED")
                    self.assertFalse((project / "SHOULD_NOT_EXIST").exists())
                    client.close()
                finally:
                    bridge.terminal_close(project, session_id=session["session_id"], approved=True)

    def test_timeout_terminates_session_and_queued_input_cannot_run(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            bridge = AgentTermBootstrap(ROOT, agentterm_command=str(health(project / "agentterm-health")))
            bridge.initialize(project, AUTHORITY)
            with patch.dict(os.environ, {"CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR": str(project / "socket-dir")}):
                session = bridge.terminal_open(project, mode="managed", approved=True)
                result = bridge.terminal_submit(project, session_id=session["session_id"],
                                                text="sleep 10; touch SHOULD_NOT_EXIST", approved=True, timeout=0.2)
                self.assertEqual(result["outcome"], "TIMED_OUT_TERMINATED")
                self.assertFalse((project / "SHOULD_NOT_EXIST").exists())
                with self.assertRaises(TerminalBridgeError):
                    bridge.terminal_submit(project, session_id=session["session_id"], text="echo later", approved=True)

    def test_tampered_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            bridge = AgentTermBootstrap(ROOT, agentterm_command=str(health(project / "agentterm-health")))
            bridge.initialize(project, AUTHORITY)
            with patch.dict(os.environ, {"CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR": str(project / "socket-dir")}):
                session = bridge.terminal_open(project, mode="managed", approved=True)
                metadata_path = project / ".agentterm" / "terminal-sessions" / f"{session['session_id']}.json"
                metadata = json.loads(metadata_path.read_text())
                metadata["socket"] = "/tmp/attacker.sock"
                metadata_path.write_text(json.dumps(metadata))
                try:
                    with self.assertRaises(TerminalBridgeError):
                        bridge.terminal_submit(project, session_id=session["session_id"], text="echo no", approved=True)
                finally:
                    handle = open_terminal_bridge._PROCESS_HANDLES.pop(session["session_id"], None)
                    if handle is not None:
                        handle.terminate()
                        handle.wait(timeout=2)

    def test_managed_socket_name_stays_within_macos_path_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            long_socket_dir = Path(directory) / ("nested-" + ("x" * 70))
            with patch.dict(os.environ, {"CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR": str(long_socket_dir)}):
                socket_path = open_terminal_bridge._socket_path(
                    Path(directory) / "project", "terminal-" + ("a" * 32)
                )
            self.assertLessEqual(len(socket_path.name.encode()), 40)
            self.assertEqual(socket_path.name, "session.sock")
            open_terminal_bridge._cleanup_runtime_directory(socket_path)

    def test_deep_project_path_does_not_enter_socket_address(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for index in range(12):
                project /= "deep-project-directory-" + ("x" * 20) + str(index)
            project.mkdir(parents=True)
            with patch.dict(os.environ, {}, clear=False):
                socket_path = open_terminal_bridge._socket_path(project, "terminal-" + ("a" * 32))
            self.assertNotIn(str(project), str(socket_path))
            self.assertLess(len(os.fsencode(str(socket_path))), 104)
            open_terminal_bridge._cleanup_runtime_directory(socket_path)

    def test_runtime_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real"
            real.mkdir()
            link = Path(directory) / "runtime-link"
            link.symlink_to(real, target_is_directory=True)
            with patch.dict(os.environ, {"CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR": str(link)}):
                with self.assertRaises(TerminalBridgeError):
                    open_terminal_bridge._socket_path(Path(directory), "terminal-" + ("a" * 32))

    def test_concurrent_runtime_paths_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"CODEX_BOOTSTRAP_TERMINAL_SOCKET_DIR": directory}):
                first = open_terminal_bridge._socket_path(Path(directory), "terminal-" + ("a" * 32))
                second = open_terminal_bridge._socket_path(Path(directory), "terminal-" + ("a" * 32))
            self.assertNotEqual(first, second)
            self.assertEqual(first.parent.stat().st_uid, os.getuid())
            self.assertEqual(first.parent.stat().st_mode & 0o077, 0)
            open_terminal_bridge._cleanup_runtime_directory(first)
            open_terminal_bridge._cleanup_runtime_directory(second)

    def test_socket_collision_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            session_id = "terminal-12345678"
            capability = runtime / "capability"
            open_terminal_bridge._write_secret(capability, project_root=root, session_id=session_id)
            socket_path = runtime / "session.sock"
            socket_path.write_text("owned marker", encoding="utf-8")
            with self.assertRaises(TerminalBridgeError):
                open_terminal_bridge._serve(socket_path, root, capability)
            self.assertEqual(socket_path.read_text(encoding="utf-8"), "owned marker")

    def test_startup_diagnostics_are_bounded_and_non_secret(self):
        class FakeProcess:
            returncode = 1
            stderr = io.BytesIO(b"OSError: AF_UNIX path too long\n")
            stdin = stdout = None

        diagnostics = open_terminal_bridge._startup_diagnostics(FakeProcess(), Path("/tmp/session.sock"))
        self.assertIn("socket_path_bytes=", diagnostics)
        self.assertIn("AF_UNIX path too long", diagnostics)
        self.assertNotIn("capability", diagnostics.lower())

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
