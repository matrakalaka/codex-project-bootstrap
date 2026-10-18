import json
from pathlib import Path

import pytest

from agentterm import contracts, governance, playbooks
from agentterm.canon import canonical_hash
from agentterm.gitinfo import Snapshot

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


@pytest.mark.parametrize("kind,fixture", [
    ("task", "task_valid.json"),
    ("result", "result_pass.json"),
    ("approval", "approval_valid.json"),
    ("bootstrap", "bootstrap_valid.json"),
])
def test_real_bootstrap_fixtures_validate(kind, fixture):
    assert contracts.validate(kind, load(fixture)) == []


@pytest.mark.parametrize("kind,fixture,needle", [
    ("task", "task_empty_objective.json", "objective"),
    ("task", "task_scope_collision.json", "collide"),
    ("approval", "approval_missing_human.json", "HUMAN"),
    ("result", "result_bad_outcome.json", "vocabulary"),
])
def test_real_bootstrap_negative_fixtures_rejected(kind, fixture, needle):
    errors = contracts.validate(kind, load(fixture))
    assert errors and any(needle in e for e in errors)


def _snap():
    return Snapshot("/r", True, "https://github.com/e/p", "https://github.com/e/p",
                    "a" * 40, "main", False, ())


def test_builders_produce_valid_chain_of_packets():
    task = contracts.make_task_packet(
        objective="Fix the bug", repository_locator="/r", expected_identity="https://github.com/e/p",
        expected_head="a" * 40, allowed=["src/**"], forbidden=["secrets/**"], mutation_allowed=True,
        verification=[{"id": "tests", "description": "pytest"}])
    assert contracts.validate("task", task) == []
    assessment = contracts.make_assessment(task, _snap(), [], "agentterm-0.1.0", True, "ok")
    assert contracts.validate("bootstrap", assessment) == []
    assert contracts.assessment_hash_ok(assessment)
    approval = contracts.make_approval(task, assessment, identity="https://github.com/e/p",
                                       head="a" * 40, approver="me@example.com", reason="ok")
    assert contracts.validate("approval", approval) == []
    assert approval["objective_hash"] == canonical_hash("Fix the bug")
    result = contracts.make_result(
        task, session_id="s", outcome="PASS", identity="x", head_before="a" * 40, head_after="a" * 40,
        changed=["src/b.py", "src/a.py"], verification={"performed": True, "result": "PASS", "checks": []},
        receipt_id="r", evidence_ref="s", risks=[], human_action_required=False, next_action="STOP",
        stop_reason="ONE_VERIFIED_CHECKPOINT")
    assert contracts.validate("result", result) == []
    assert result["changed_paths"] == ["src/a.py", "src/b.py"]


def test_assessment_tamper_detected():
    task = contracts.make_task_packet(
        objective="x", repository_locator="/r", expected_identity=None, expected_head=None,
        allowed=[], forbidden=[], mutation_allowed=False, verification=[])
    a = contracts.make_assessment(task, _snap(), [], "v", True, "ok")
    a["safe_to_bootstrap"] = False
    assert not contracts.assessment_hash_ok(a)


@pytest.mark.parametrize("path,pattern,expected", [
    ("src/a/b.py", "src/**", True),
    ("src", "src/**", True),
    ("srcx/a.py", "src/**", False),
    ("src/a.py", "src", True),
    ("README.md", "*.md", True),
    ("docs/deep/x.md", "*.md", True),
    ("a.py", "**", True),
    ("a.py", "", False),
    ("./src/a.py", "src/**", True),
    ("src\\a.py", "src/**", True),
])
def test_matches(path, pattern, expected):
    assert governance.matches(path, pattern) is expected


def test_scope_violations_forbidden_wins_and_empty_allows_nothing():
    v = governance.scope_violations(["src/a.py", "secrets/k.txt", "other.md"], ["src/**", "secrets/**"], ["secrets/**"])
    assert {(x.path, x.reason) for x in v} == {
        ("secrets/k.txt", "matches a forbidden path"),
        ("other.md", "is outside the allowed paths"),
    }
    assert [x.path for x in governance.scope_violations(["a"], [], [])] == ["a"]


@pytest.mark.parametrize("kwargs,expected", [
    (dict(preconditions_ok=False, executed=False, agent_ok=True, verification_ok=True, violations=[]), "BLOCKED_PRECONDITION"),
    (dict(preconditions_ok=True, executed=False, agent_ok=True, verification_ok=True, violations=[]), "BLOCKED_PRECONDITION"),
    (dict(preconditions_ok=True, executed=True, agent_ok=True, verification_ok=True, violations=[]), "PASS"),
    (dict(preconditions_ok=True, executed=True, agent_ok=False, verification_ok=True, violations=[]), "FAILED_AFTER_EXECUTION"),
    (dict(preconditions_ok=True, executed=True, agent_ok=True, verification_ok=False, violations=[]), "FAILED_AFTER_EXECUTION"),
    (dict(preconditions_ok=True, executed=True, agent_ok=False, verification_ok=False,
          violations=[governance.Violation("x", "y")]), "DIVERGENCE"),
])
def test_classify(kwargs, expected):
    assert governance.classify(**kwargs) == expected


def test_bundled_playbooks_verify_against_bootstrap_fingerprint_scheme():
    ids = {p["id"] for p in playbooks.list_playbooks()}
    assert {"BUG_FIX", "UI_VISUAL_REVIEW"} <= ids
    for pid in ids:
        book = playbooks.load(pid)
        assert book["fingerprint"] == playbooks.fingerprint(book)
    ref = playbooks.reference(playbooks.load("BUG_FIX"))
    task = contracts.make_task_packet(
        objective="x", repository_locator="/r", expected_identity=None, expected_head=None,
        allowed=["src/**"], forbidden=[], mutation_allowed=False, verification=[], playbook=ref)
    assert contracts.validate("task", task) == []
    with pytest.raises(playbooks.PlaybookError):
        playbooks.load("NOPE")
