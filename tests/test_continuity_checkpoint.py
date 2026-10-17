"""Synthetic contract tests for the Phase 1 continuity checkpoint."""

from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import unittest


ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "templates" / "CONTINUE_TOMORROW_TEMPLATE.md"

REQUIRED_SECTIONS = (
    "Original Objective",
    "Objective Source",
    "Repository Identity",
    "Repository Remote",
    "HEAD",
    "Checkpoint Revision",
    "Current Observed HEAD",
    "Material Source Changes Since Validation",
    "Dirty-Worktree Evidence",
    "Approved Scope",
    "Binding Decisions",
    "Verified Completed Work",
    "Evidence References",
    "Failed Approaches and Blockers",
    "Contradictions and Staleness",
    "Codebase Memory Fallback",
    "Next Approved Action",
    "Recovery Classification",
    "ChatGPT / Codex Handoff Projection",
)


def validate_checkpoint(
    checkpoint,
    current_head,
    current_repository="example/repository",
    current_remote="https://example.test/repository.git",
    current_branch="main",
    worktree_dirty=False,
):
    """Validate bounded recovery fields without creating a second store."""
    required = {
        "checkpoint_id",
        "objective",
        "objective_source",
        "repository_identity",
        "repository_path",
        "repository_remote",
        "head",
        "validated_source_revision",
        "checkpoint_revision",
        "current_observed_head",
        "material_source_changes",
        "dirty_worktree_evidence",
        "branch",
        "worktree_state",
        "approved_scope",
        "decisions",
        "completed",
        "evidence",
        "failures_or_blockers",
        "status",
        "contradictions_or_staleness",
        "next_action",
    }
    missing = required - checkpoint.keys()
    if missing:
        return False, f"missing fields: {sorted(missing)}"
    if checkpoint["repository_path"] != current_repository:
        return False, "checkpoint belongs to another repository"
    if checkpoint["repository_remote"] != current_remote:
        return False, "checkpoint belongs to another remote"
    if checkpoint["branch"] != current_branch:
        return False, "checkpoint branch does not match"
    if checkpoint["head"] != checkpoint["validated_source_revision"]:
        return False, "validated source revision is inconsistent"
    if checkpoint["current_observed_head"] != current_head:
        return False, "checkpoint current observed HEAD is stale"
    if current_head != checkpoint["validated_source_revision"] and checkpoint["material_source_changes"] != "NONE":
        return False, "material source changes since validation are unresolved"
    expected_worktree_state = "DIRTY" if worktree_dirty else "CLEAN"
    if checkpoint["worktree_state"] != expected_worktree_state:
        return False, "checkpoint worktree state is stale"
    if checkpoint["contradictions_or_staleness"] != "NONE":
        return False, "checkpoint has unresolved contradiction or staleness"
    if worktree_dirty and not checkpoint["dirty_worktree_evidence"]:
        return False, "dirty worktree evidence is missing"
    if checkpoint["status"] == "STOP_COMPLETE" and checkpoint["next_action"] != "STOP_COMPLETE":
        return False, "STOP_COMPLETE requires STOP_COMPLETE next action"
    if checkpoint["status"] != "STOP_COMPLETE" and not checkpoint["next_action"]:
        return False, "active checkpoint requires one next action"
    return True, "PASS"


class ContinuityCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.head = "a" * 40
        self.checkpoint = {
            "checkpoint_id": "task-1/checkpoint-1",
            "objective": "Preserve the approved objective",
            "objective_source": "approved task packet",
            "repository_identity": "example/repository",
            "repository_path": "example/repository",
            "repository_remote": "https://example.test/repository.git",
            "head": self.head,
            "validated_source_revision": self.head,
            "checkpoint_revision": "UNCOMMITTED:task-1/checkpoint-1",
            "current_observed_head": self.head,
            "material_source_changes": "NONE",
            "dirty_worktree_evidence": "NONE",
            "branch": "main",
            "worktree_state": "CLEAN",
            "approved_scope": "templates and prompts only",
            "decisions": ["Use one canonical checkpoint"],
            "completed": ["Updated continuity contract"],
            "evidence": ["tests/test_continuity_checkpoint.py"],
            "failures_or_blockers": ["NONE RECORDED"],
            "status": "PASS",
            "contradictions_or_staleness": "NONE",
            "next_action": "Run fresh-session acceptance test",
        }

    def test_template_contains_the_canonical_recovery_fields(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            self.assertIn(section, text)

    def test_fresh_session_recovery_and_scope_retention(self):
        valid, reason = validate_checkpoint(self.checkpoint, self.head)
        self.assertTrue(valid, reason)
        self.assertEqual(self.checkpoint["approved_scope"], "templates and prompts only")

    def test_foreign_project_checkpoint_is_rejected(self):
        foreign = dict(self.checkpoint, repository_path="other/repository")
        valid, reason = validate_checkpoint(foreign, self.head)
        self.assertFalse(valid)
        self.assertIn("another repository", reason)

        foreign_remote = dict(self.checkpoint, repository_remote="https://other.test/repo.git")
        valid, reason = validate_checkpoint(foreign_remote, self.head)
        self.assertFalse(valid)
        self.assertIn("another remote", reason)

    def test_missing_checkpoint_has_no_cross_project_fallback(self):
        text = (ROOT / "prompts" / "NEW_TASK_START.md").read_text(encoding="utf-8")
        self.assertIn("do not fall back to another project's memory", text)
        self.assertIn("Reject a checkpoint belonging to another repository", text)

    def test_original_objective_decisions_completed_failures_and_next_action_recover(self):
        valid, reason = validate_checkpoint(self.checkpoint, self.head)
        self.assertTrue(valid, reason)
        self.assertEqual(self.checkpoint["objective"], "Preserve the approved objective")
        self.assertEqual(self.checkpoint["decisions"], ["Use one canonical checkpoint"])
        self.assertEqual(self.checkpoint["completed"], ["Updated continuity contract"])
        self.assertEqual(self.checkpoint["failures_or_blockers"], ["NONE RECORDED"])
        self.assertEqual(self.checkpoint["next_action"], "Run fresh-session acceptance test")

    def test_original_objective_completed_work_failures_and_next_action_recover(self):
        valid, reason = validate_checkpoint(self.checkpoint, self.head)
        self.assertTrue(valid, reason)
        self.assertEqual(self.checkpoint["objective"], "Preserve the approved objective")
        self.assertEqual(self.checkpoint["completed"], ["Updated continuity contract"])
        self.assertEqual(self.checkpoint["failures_or_blockers"], ["NONE RECORDED"])
        self.assertEqual(self.checkpoint["next_action"], "Run fresh-session acceptance test")

    def test_stale_head_and_contradiction_fail_closed(self):
        valid, reason = validate_checkpoint(self.checkpoint, "b" * 40)
        self.assertFalse(valid)
        self.assertIn("stale", reason)

        contradictory = dict(self.checkpoint, contradictions_or_staleness="PRESENT")
        valid, reason = validate_checkpoint(contradictory, self.head)
        self.assertFalse(valid)
        self.assertIn("unresolved", reason)

    def test_dirty_worktree_is_valid_when_recorded(self):
        dirty = dict(self.checkpoint, worktree_state="DIRTY")
        valid, reason = validate_checkpoint(dirty, self.head, worktree_dirty=True)
        self.assertTrue(valid, reason)

        unrecorded = dict(self.checkpoint)
        valid, reason = validate_checkpoint(unrecorded, self.head, worktree_dirty=True)
        self.assertFalse(valid)
        self.assertIn("worktree state", reason)

    def test_checkpoint_revision_drift_is_accepted_without_material_source_changes(self):
        committed = dict(
            self.checkpoint,
            current_observed_head="b" * 40,
            checkpoint_revision="COMMITTED:" + "b" * 40,
        )
        valid, reason = validate_checkpoint(committed, "b" * 40)
        self.assertTrue(valid, reason)

    def test_material_source_changes_fail_closed_after_revision_drift(self):
        changed = dict(
            self.checkpoint,
            current_observed_head="b" * 40,
            checkpoint_revision="COMMITTED:" + "b" * 40,
            material_source_changes="GLOBAL_PROJECT_BOOTSTRAP.md",
        )
        valid, reason = validate_checkpoint(changed, "b" * 40)
        self.assertFalse(valid)
        self.assertIn("material source changes", reason)

    def test_utc_local_boundary_is_reconciled(self):
        timestamp = datetime.fromisoformat("2026-10-17T00:02:54+00:00")
        local = timestamp.astimezone(ZoneInfo("America/New_York"))
        self.assertEqual(local.strftime("%Y-%m-%d %H:%M:%S %Z"), "2026-10-16 20:02:54 EDT")

    def test_optional_authority_files_do_not_block_bootstrap_fixture(self):
        self.assertFalse((ROOT / "AGENTS.md").exists())
        self.assertFalse((ROOT / "KNOWN_GOOD_CONTRACTS.md").exists())
        text = (ROOT / "GLOBAL_PROJECT_BOOTSTRAP.md").read_text(encoding="utf-8")
        self.assertIn("For substantial projects, normally establish", text)

    def test_memory_fallback_and_no_duplicate_store_are_explicit(self):
        checkpoint = (ROOT / "CONTINUE_TOMORROW.md").read_text(encoding="utf-8")
        bootstrap = (ROOT / "GLOBAL_PROJECT_BOOTSTRAP.md").read_text(encoding="utf-8")
        self.assertIn("MIS-SCOPED / BLOCKED", checkpoint)
        self.assertIn("Do not create a second memory", bootstrap)
        self.assertIn("do not fall back to another project's memory", bootstrap)

    def test_completed_work_is_not_reopened_without_new_evidence(self):
        agents = (ROOT / "templates" / "AGENTS_TEMPLATE.md").read_text(encoding="utf-8")
        prompt = (ROOT / "prompts" / "NEW_TASK_START.md").read_text(encoding="utf-8")
        self.assertIn("Do not reopen `ALREADY_SATISFIED` work without new evidence", agents)
        self.assertIn("Do not reopen completed work without new evidence", prompt)

    def test_approval_provenance_remains_distinct(self):
        checkpoint = (ROOT / "CONTINUE_TOMORROW.md").read_text(encoding="utf-8")
        self.assertIn("no independent approval packet is present", checkpoint)
        self.assertIn("not retroactive Phase 2A", checkpoint)
        self.assertIn("HUMAN_APPROVAL", (ROOT / "templates" / "CONTINUE_TOMORROW_TEMPLATE.md").read_text(encoding="utf-8"))

    def test_handoff_projection_contains_required_recovery_facts(self):
        text = (ROOT / "templates" / "CONTINUE_TOMORROW_TEMPLATE.md").read_text(encoding="utf-8")
        for field in (
            "Repository Identity",
            "Original Objective",
            "Verified Completed Work",
            "Binding Decisions",
            "Failed Approaches and Blockers",
            "Protected / Untouched",
            "Next Approved Action",
            "Evidence References",
        ):
            self.assertIn(field, text)

    def test_stop_complete_is_terminal(self):
        complete = dict(self.checkpoint, status="STOP_COMPLETE", next_action="STOP_COMPLETE")
        valid, reason = validate_checkpoint(complete, self.head)
        self.assertTrue(valid, reason)

        invalid = dict(self.checkpoint, status="STOP_COMPLETE", next_action="start another task")
        valid, reason = validate_checkpoint(invalid, self.head)
        self.assertFalse(valid)

    def test_handoff_completeness_requires_all_fields(self):
        incomplete = dict(self.checkpoint)
        del incomplete["evidence"]
        valid, reason = validate_checkpoint(incomplete, self.head)
        self.assertFalse(valid)
        self.assertIn("evidence", reason)


if __name__ == "__main__":
    unittest.main()
