import json
import tempfile
import unittest
from pathlib import Path

from host_exec_bridge import execute


class HostExecBridgeTests(unittest.TestCase):
    def request(self, operation="fixture_echo"):
        return {"operation": operation, "target": ".", "authorization": "OWNER_APPROVED"}

    def test_disabled_bridge_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            result = execute(self.request(), audit_path=audit, approved=True, env={})
            self.assertEqual(result["outcome"], "BLOCKED_PRECONDITION")
            self.assertEqual(len(audit.read_text(encoding="utf-8").splitlines()), 1)

    def test_owner_approval_and_allowlist_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            env = {"CODEX_BOOTSTRAP_HOST_EXECUTION": "1"}
            denied = execute(self.request("not_allowed"), audit_path=audit, approved=True, env=env)
            self.assertEqual(denied["outcome"], "BLOCKED_PRECONDITION")
            no_approval = execute(self.request(), audit_path=audit, approved=False, env=env)
            self.assertEqual(no_approval["outcome"], "BLOCKED_PRECONDITION")

    def test_synthetic_fixture_executes_with_preview_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            result = execute(
                self.request(), audit_path=audit, approved=True,
                env={"CODEX_BOOTSTRAP_HOST_EXECUTION": "1"},
            )
            self.assertEqual(result["outcome"], "PASS")
            self.assertEqual(result["stdout"].strip(), "BOOTSTRAP_HOST_FIXTURE_OK")
            self.assertIn("command_preview", result)
            record = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(record["outcome"], "PASS")

    def test_git_status_is_bounded_to_repository_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.jsonl"
            request = self.request("git_status")
            request["target"] = "/"
            result = execute(
                request, audit_path=audit, approved=True,
                env={"CODEX_BOOTSTRAP_HOST_EXECUTION": "1"},
            )
            self.assertEqual(result["outcome"], "BLOCKED_PRECONDITION")


if __name__ == "__main__":
    unittest.main()
