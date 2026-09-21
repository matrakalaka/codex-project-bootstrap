"""Offline checks for the global North Star discovery contract."""

import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent


class NorthStarTests(unittest.TestCase):
    def test_global_north_star_contains_core_gates(self):
        text = (ROOT / "PROJECT_NORTH_STAR.md").read_text(encoding="utf-8")
        for phrase in (
            "The approved objective is the destination.",
            "## Anti-drift gate",
            "## Ordinary engineering stays in the task",
            "## Parked ideas",
            "## Verified plan changes",
            "## Completion",
            "## Project-specific extensions",
        ):
            self.assertIn(phrase, text)

    def test_bootstrap_discovers_global_north_star(self):
        text = (ROOT / "GLOBAL_PROJECT_BOOTSTRAP.md").read_text(encoding="utf-8")
        self.assertIn("PROJECT_NORTH_STAR.md", text)
        self.assertIn("project-specific North Star", text)
        self.assertIn("Ordinary engineering obstacles stay inside the approved task", text)

    def test_task_launcher_preserves_north_star_boundary(self):
        text = (ROOT / "prompts" / "NEW_TASK_START.md").read_text(encoding="utf-8")
        self.assertIn("PROJECT_NORTH_STAR.md", text)
        self.assertIn("park non-blocking ideas", text)


if __name__ == "__main__":
    unittest.main()
