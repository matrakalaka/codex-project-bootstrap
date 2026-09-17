"""Bounded IC-1P contract and boundary tests."""

import json
import unittest
from pathlib import Path

from contract import (approval_binding, authorizes_mutation, binding_matches,
                      establishes_pass, fingerprint, parameters_fingerprint,
                      resolve, validate)

ROOT = Path(__file__).parent


def load(name):
    with open(ROOT / name, encoding="utf-8") as handle:
        return json.load(handle)


class PlaybookTests(unittest.TestCase):
    def setUp(self):
        self.bug = load("BUG_FIX.v0.json")
        self.ui = load("UI_VISUAL_REVIEW.v0.json")

    def test_valid_initial_playbooks(self):
        self.assertEqual(validate(self.bug), [])
        self.assertEqual(validate(self.ui), [])

    def test_missing_field_and_malformed_fingerprint(self):
        missing = dict(self.bug)
        del missing["phases"]
        self.assertTrue(any("missing required field: phases" in e for e in validate(missing)))
        malformed = dict(self.bug, fingerprint="bad")
        self.assertTrue(any("fingerprint" in e for e in validate(malformed)))

    def test_fingerprint_is_stable_and_format_key_order_independent(self):
        reordered = json.loads(json.dumps(self.bug, indent=2, sort_keys=True))
        self.assertEqual(fingerprint(self.bug), fingerprint(reordered))
        self.assertEqual(fingerprint(self.bug), self.bug["fingerprint"])

    def test_changed_procedure_changes_fingerprint(self):
        changed = json.loads(json.dumps(self.bug))
        changed["phases"][0]["objective"] += " (changed)"
        self.assertNotEqual(fingerprint(self.bug), fingerprint(changed))
        self.assertTrue(any("does not match" in e for e in validate(changed)))

    def test_resolution_accept_narrow_add_verification_and_reject(self):
        accepted = resolve(self.bug, {"decision": "ACCEPT"}, {})
        narrowed = resolve(self.bug, {"decision": "NARROW", "excluded_phase_ids": ["stop"]}, {})
        stricter = resolve(self.bug, {"decision": "ADD_VERIFICATION", "required_verification": ["authority re-check"]}, {})
        self.assertEqual(accepted["canonical_playbook_fingerprint"], self.bug["fingerprint"])
        self.assertLess(len(narrowed["phases"]), len(self.bug["phases"]))
        self.assertIn("authority re-check", stricter["required_verification"])
        with self.assertRaises(ValueError):
            resolve(self.bug, {"decision": "REJECT"}, {})

    def test_narrowing_cannot_broaden_permission(self):
        resolved = resolve(self.bug, {"decision": "NARROW"}, {"allowed_paths": ["src"]})
        self.assertFalse(authorizes_mutation(resolved))
        self.assertNotIn("authorization", resolved)

    def test_binding_changes_for_parameters_and_effective_procedure(self):
        parameters = {"scope_note": "one"}
        effective = resolve(self.bug, {"decision": "ACCEPT"}, parameters)
        binding = approval_binding(self.bug, effective, parameters)
        self.assertTrue(binding_matches(binding, binding))
        changed_parameters = {"scope_note": "two"}
        changed_effective = resolve(self.bug, {"decision": "ACCEPT"}, changed_parameters)
        self.assertNotEqual(binding["effective_parameters_hash"], parameters_fingerprint(changed_parameters))
        self.assertNotEqual(binding["effective_playbook_fingerprint"], changed_effective["fingerprint"])
        self.assertFalse(binding_matches(binding, approval_binding(self.bug, changed_effective, changed_parameters)))

    def test_stale_canonical_and_effective_fingerprints_rejected(self):
        effective = resolve(self.bug, {"decision": "ACCEPT"}, {})
        binding = approval_binding(self.bug, effective, {})
        self.assertFalse(binding_matches(dict(binding, canonical_playbook_fingerprint="sha256:" + "0" * 64), binding))
        self.assertFalse(binding_matches(dict(binding, effective_playbook_fingerprint="sha256:" + "0" * 64), binding))

    def test_authorization_pass_and_composition_boundaries(self):
        self.assertFalse(authorizes_mutation(self.bug))
        self.assertFalse(establishes_pass(self.bug))
        with self.assertRaises(ValueError):
            resolve(self.bug, {"decision": "COMPOSE", "modules": [self.ui]}, {})


if __name__ == "__main__":
    unittest.main()
