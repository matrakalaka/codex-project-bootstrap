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

    def test_global_north_star_uses_one_discovery_classification(self):
        text = (ROOT / "PROJECT_NORTH_STAR.md").read_text(encoding="utf-8")
        for phrase in (
            "## Discovery classification",
            "`REQUIRED_FOR_OBJECTIVE`",
            "`ALREADY_SATISFIED`",
            "`BLOCKER`",
            "`PARKED`",
            "introduce another discovery classification",
        ):
            self.assertIn(phrase, text)

    def test_global_north_star_requires_dependency_proof(self):
        text = (ROOT / "PROJECT_NORTH_STAR.md").read_text(encoding="utf-8")
        for phrase in (
            "Before a discovered dependency may expand scope",
            "What exact part of the approved objective cannot complete without it?",
            "What concrete evidence demonstrates that necessity?",
            "Why is the existing mechanism insufficient?",
            "What is the minimum additional change required?",
            "What happens if it is not addressed now?",
            "Cleaner architecture",
            "future usefulness",
            "optional-tool",
        ):
            self.assertIn(phrase, text)

    def test_global_north_star_defines_coherent_delta_and_phase_gate(self):
        text = (ROOT / "PROJECT_NORTH_STAR.md").read_text(encoding="utf-8")
        for phrase in (
            "smallest coherent change that safely",
            "not simply the fewest changed lines",
            "Favor existing mechanisms",
            "preservation of known-good behavior",
            "Its complexity is proportional to the objective.",
            "Otherwise classify the work as `PARKED`.",
        ):
            self.assertIn(phrase, text)

    def test_global_north_star_completion_discipline(self):
        text = (ROOT / "PROJECT_NORTH_STAR.md").read_text(encoding="utf-8")
        for phrase in (
            "original approved objective",
            "required verification passed",
            "changed paths stayed",
            "any scope expansion had verified dependency proof",
            "optional tooling did not silently become scope",
            "the `STOP` boundary was reached",
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

    def test_task_launcher_records_operational_boundaries(self):
        text = (ROOT / "prompts" / "NEW_TASK_START.md").read_text(encoding="utf-8")
        for phrase in (
            "ORIGINAL APPROVED OBJECTIVE",
            "INTENDED CHANGE",
            "REQUIRED PROOF",
            "EXPECTED CHANGE UNIT",
            "OUT OF SCOPE",
            "NEW DEPENDENCIES REQUIRED: YES / NO / UNKNOWN",
            "EXACT OBJECTIVE REQUIRING EACH DEPENDENCY",
            "OPTIONAL TOOLING REQUIRED: YES / NO",
            "STOP / PROMOTION BOUNDARY",
            "objective satisfied",
            "dependency proof existed for any expansion",
            "unrelated findings were PARKED",
            "STOP reached",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
