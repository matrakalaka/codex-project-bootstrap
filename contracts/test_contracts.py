"""Offline IC-1 contract and fixture tests."""

import json
import unittest
from pathlib import Path

from contract_validator import SCHEMA_FILES, canonical_hash, validate

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures"


def load(name):
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


class ContractTests(unittest.TestCase):
    def test_schema_files_parse(self):
        for filename in SCHEMA_FILES.values():
            with open(ROOT / filename, encoding="utf-8") as handle:
                self.assertIsInstance(json.load(handle), dict)

    def test_valid_fixtures(self):
        for kind, names in {
            "task": ["task_valid.json", "task_playbook_valid.json"],
            "bootstrap": ["bootstrap_valid.json"],
            "approval": ["approval_valid.json"],
            "result": ["result_pass.json", "result_blocked.json", "result_failed.json", "result_divergence.json"],
        }.items():
            for name in names:
                self.assertEqual(validate(kind, load(name)), [], name)

    def test_invalid_fixtures_fail_with_expected_reason(self):
        cases = [
            ("task", "task_missing_required.json", "missing required field"),
            ("task", "task_unknown_version.json", "schema_version"),
            ("task", "task_empty_objective.json", "objective"),
            ("task", "task_scope_collision.json", "collide"),
            ("task", "task_playbook_bad_fingerprint.json", "fingerprint"),
            ("task", "task_playbook_incomplete.json", "missing required field"),
            ("approval", "approval_missing_human.json", "HUMAN approver"),
            ("approval", "approval_bad_binding.json", "approval hashes"),
            ("result", "result_bad_outcome.json", "outcome"),
        ]
        for kind, name, expected in cases:
            errors = validate(kind, load(name))
            self.assertTrue(any(expected in error for error in errors), (name, errors))

    def test_canonical_hash_ignores_object_order_and_formatting(self):
        left = {"objective": "x", "scope": {"allowed_paths": ["b", "a"], "forbidden_paths": []}}
        right = json.loads('{ "scope": { "forbidden_paths": [], "allowed_paths": [ "a", "b" ] }, "objective": "x" }')
        self.assertEqual(canonical_hash(left), canonical_hash(right))

    def test_approval_sensitive_change_changes_hash(self):
        value = load("approval_valid.json")
        changed = dict(value, reason="different human reason")
        self.assertNotEqual(canonical_hash(value), canonical_hash(changed))


if __name__ == "__main__":
    unittest.main()
