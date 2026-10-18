import hashlib
import hmac
import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import open_terminal_bridge as bridge


class TerminalSecurityUnitTests(unittest.TestCase):
    def test_invalid_and_replayed_capabilities_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = b"s" * 32
            capability = {"expires_at": bridge.time.time() + 60}
            seen = set()
            request = {"type": "submit", "request_id": "request-one", "authorization": "bad"}
            allowed, reason = bridge._authorize_request(request, secret=secret, project_root=root,
                                                        seen=seen, capability=capability)
            self.assertFalse(allowed)
            self.assertIn("invalid capability", reason)
            message = f"submit|request-one|{root.resolve()}".encode()
            request["request_id"] = "request-three"
            message = f"submit|request-three|{root.resolve()}".encode()
            request["authorization"] = hmac.new(secret, message, hashlib.sha256).hexdigest()
            allowed, reason = bridge._authorize_request(request, secret=secret, project_root=root,
                                                        seen=seen, capability=capability)
            self.assertTrue(allowed, reason)
            replay, reason = bridge._authorize_request(request, secret=secret, project_root=root,
                                                       seen=seen, capability=capability)
            self.assertFalse(replay)
            self.assertIn("replayed", reason)

    def test_capability_cannot_authorize_another_project(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first"
            second = Path(directory) / "second"
            first.mkdir(); second.mkdir()
            secret = b"s" * 32
            request_id = "request-two"
            message = f"submit|{request_id}|{first.resolve()}".encode()
            request = {"type": "submit", "request_id": request_id,
                       "authorization": hmac.new(secret, message, hashlib.sha256).hexdigest()}
            allowed, reason = bridge._authorize_request(request, secret=secret, project_root=second,
                                                        seen=set(), capability={"expires_at": bridge.time.time() + 60})
            self.assertFalse(allowed)
            self.assertIn("invalid capability", reason)

    def test_process_group_timeout_terminates_only_started_group(self):
        process = subprocess.Popen(["/bin/sh", "-c", "sleep 60"], start_new_session=True)
        try:
            self.assertEqual(bridge._terminate_process_group(process.pid, grace=0.2), "CLOSED")
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill(); process.wait()

    def test_native_metadata_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("open_terminal_bridge._native_osascript", return_value="123"):
                session = bridge.open_session(root, mode="native", approved=True)
            path = root / ".agentterm" / "terminal-sessions" / f"{session['session_id']}.json"
            body = __import__("json").loads(path.read_text())
            body["mode"] = "managed"
            path.write_text(__import__("json").dumps(body))
            with self.assertRaises(bridge.TerminalBridgeError):
                bridge._load_metadata(root, session["session_id"])

    def test_failed_close_preserves_failure_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_id = "terminal-12345678"
            sessions = root / ".agentterm" / "terminal-sessions"
            sessions.mkdir(parents=True)
            cap = sessions / f".{session_id}.capability"
            secret = bridge._write_secret(cap, project_root=root, session_id=session_id)
            metadata = {"schema": bridge.SESSION_SCHEMA, "session_id": session_id,
                        "project_root": str(root.resolve()), "mode": "managed", "state": "OPEN",
                        "socket": str(root / "missing.sock"), "capability_file": str(cap)}
            metadata["integrity"] = bridge._metadata_mac(metadata, secret)
            bridge._write_metadata(sessions / f"{session_id}.json", metadata)
            result = bridge.close_session(root, session_id, approved=True)
            self.assertEqual(result["outcome"], "CLOSE_FAILED")
            stored = __import__("json").loads((sessions / f"{session_id}.json").read_text())
            self.assertEqual(stored["state"], "CLOSE_FAILED")


if __name__ == "__main__":
    unittest.main()
