import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor" / "agentterm" / "src"))

from agentterm.runner import _run_check


class VerificationPolicyTests(unittest.TestCase):
    def test_unapproved_verification_is_blocked_before_execution(self):
        result = _run_check("touch SHOULD_NOT_EXIST", ".", 1, authorized=False)
        self.assertEqual(result["result"], "BLOCKED_PRECONDITION")
        self.assertEqual(result["authorization"], "NOT_APPROVED")

    def test_unresolved_executable_is_blocked_even_when_approved(self):
        result = _run_check("definitely-not-a-real-executable", ".", 1, authorized=True)
        self.assertEqual(result["result"], "BLOCKED_PRECONDITION")


if __name__ == "__main__":
    unittest.main()
