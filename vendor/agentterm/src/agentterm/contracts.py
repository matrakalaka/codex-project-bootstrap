"""Contract-compatible packets (task, assessment, approval, result) and validation.

Field names, hash rules and the outcome vocabulary follow the Shared Stack
Contracts v0 from codex-project-bootstrap, so packets produced here are
readable by that stack and vice versa.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from .canon import canonical_hash, is_hash, utc_now

OUTCOMES = ("PASS", "BLOCKED_PRECONDITION", "FAILED_AFTER_EXECUTION", "DIVERGENCE")
EXIT_CODES = {"PASS": 0, "BLOCKED_PRECONDITION": 2, "FAILED_AFTER_EXECUTION": 3, "DIVERGENCE": 4}

_SCHEMA_VERSIONS = {
    "task": "task_packet.v0",
    "bootstrap": "bootstrap_assessment.v0",
    "approval": "human_approval.v0",
    "result": "result_packet.v0",
}
_REQUIRED = {
    "task": ("schema_version", "correlation_id", "task_id", "origin", "target", "objective",
             "scope", "authority_requirements", "mutation_allowed", "required_verification",
             "required_capabilities", "known_good_references", "approval_state", "retry",
             "stop_condition"),
    "bootstrap": ("schema_version", "assessment_id", "correlation_id", "task_id",
                  "source_revision", "target", "authority", "tool_health",
                  "known_good_references", "recommended_scope", "safe_to_bootstrap",
                  "human_readable_assessment", "assessment_hash", "created_at"),
    "approval": ("schema_version", "approval_id", "correlation_id", "task_id", "assessment_id",
                 "assessment_hash", "repository_identity", "authorized_head", "objective_hash",
                 "allowed_paths", "forbidden_paths", "approved", "approver", "approved_at",
                 "reason", "approval_sequence"),
    "result": ("schema_version", "result_id", "correlation_id", "task_id",
               "repoguard_session_id", "outcome", "repository", "changed_paths",
               "verification", "evidence", "unresolved_risks", "human_action_required",
               "next_action", "stop_reason", "created_at"),
}


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def scope_overlap(left: str, right: str) -> bool:
    def parts(value: str) -> tuple[str, ...]:
        value = value.replace("\\", "/").strip("/")
        if value.endswith("/**"):
            value = value[:-3]
        return tuple(p for p in value.split("/") if p and p != ".")

    a, b = parts(left), parts(right)
    return bool(a and b and (a == b or a[: len(b)] == b or b[: len(a)] == a))


def validate(kind: str, value: Any) -> list[str]:
    if kind not in _SCHEMA_VERSIONS:
        return [f"unknown contract kind: {kind}"]
    if not isinstance(value, dict):
        return ["contract must be an object"]
    errors: list[str] = []
    if value.get("schema_version") != _SCHEMA_VERSIONS[kind]:
        errors.append(f"schema_version must be {_SCHEMA_VERSIONS[kind]}")
    missing = [f for f in _REQUIRED[kind] if f not in value]
    errors.extend(f"missing required field: {f}" for f in missing)
    if missing:
        return errors

    if kind == "task":
        objective = value["objective"]
        if not isinstance(objective, str) or not objective.strip():
            errors.append("objective must be non-empty")
        scope = value["scope"]
        if not isinstance(scope, dict):
            errors.append("scope must be an object")
        else:
            allowed = scope.get("allowed_paths", [])
            forbidden = scope.get("forbidden_paths", [])
            if not isinstance(allowed, list) or not isinstance(forbidden, list):
                errors.append("scope paths must be arrays")
            elif any(scope_overlap(a, f) for a in allowed for f in forbidden):
                errors.append("allowed and forbidden scope collide")
        playbook = value.get("playbook")
        if playbook is not None:
            if not isinstance(playbook, dict):
                errors.append("playbook must be an object")
            else:
                for key in ("id", "version", "fingerprint", "parameters"):
                    if key not in playbook:
                        errors.append(f"missing required field: {key}")
                if "fingerprint" in playbook and not is_hash(playbook["fingerprint"]):
                    errors.append("playbook fingerprint must be sha256:<64 lowercase hex>")
    elif kind == "bootstrap":
        if not is_hash(value["assessment_hash"]):
            errors.append("assessment_hash must be sha256:<64 lowercase hex>")
    elif kind == "approval":
        if value["approved"] is not True:
            errors.append("approval must be explicitly true")
        approver = value["approver"]
        if not isinstance(approver, dict) or approver.get("type") != "HUMAN" or not approver.get("identifier"):
            errors.append("approval requires an attributable HUMAN approver")
        if not is_hash(value["assessment_hash"]) or not is_hash(value["objective_hash"]):
            errors.append("approval hashes must be sha256:<64 lowercase hex>")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", str(value["authorized_head"])):
            errors.append("authorized_head must be a full commit SHA")
    elif kind == "result":
        if value["outcome"] not in OUTCOMES:
            errors.append("outcome is not in the standard vocabulary")
    return errors


# ----------------------------------------------------------------- builders
def make_task_packet(
    *,
    objective: str,
    repository_locator: str,
    expected_identity: str | None,
    expected_head: str | None,
    allowed: list[str],
    forbidden: list[str],
    mutation_allowed: bool,
    verification: list[dict[str, str]],
    origin_label: str = "agentterm",
    playbook: dict[str, Any] | None = None,
    required_sources: list[str] | None = None,
    stop_condition: str = "ONE_VERIFIED_CHECKPOINT",
    task_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "schema_version": "task_packet.v0",
        "correlation_id": correlation_id or new_id("corr"),
        "task_id": task_id or new_id("task"),
        "origin": {"kind": "HUMAN", "label": origin_label},
        "target": {
            "repository_locator": repository_locator,
            "expected_repository_identity": expected_identity,
            "expected_head": expected_head,
        },
        "objective": objective,
        "scope": {"allowed_paths": list(allowed), "forbidden_paths": list(forbidden)},
        "authority_requirements": {
            "required_sources": list(required_sources or []),
            "authority_change_allowed_paths": [],
        },
        "mutation_allowed": mutation_allowed,
        "required_verification": verification,
        "required_capabilities": [],
        "known_good_references": [],
        "approval_state": "PENDING",
        "retry": {
            "idempotency_key": new_id("idem"),
            "attempt": 0,
            "retry_policy": "NO_AUTOMATIC_MUTATION_RETRY",
        },
        "stop_condition": stop_condition,
    }
    if playbook:
        packet["playbook"] = playbook
    return packet


def make_assessment(task: dict[str, Any], snap: Any, tool_health: list[dict[str, Any]],
                    source_revision: str, safe: bool, summary: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "bootstrap_assessment.v0",
        "assessment_id": new_id("assessment"),
        "correlation_id": task["correlation_id"],
        "task_id": task["task_id"],
        "source_revision": source_revision,
        "target": {
            "repository_locator": snap.root,
            "observed_identity": snap.identity,
            "observed_head": snap.head,
            "observed_branch": snap.branch,
            "worktree_state": snap.worktree_state,
        },
        "authority": {
            "sources": [],
            "authority_fingerprint": None,
            "conflicts": [],
            "resolution_status": "COMPLETE" if safe else "PARTIAL",
        },
        "tool_health": tool_health,
        "known_good_references": [],
        "recommended_scope": dict(task["scope"]),
        "safe_to_bootstrap": safe,
        "human_readable_assessment": summary,
        "created_at": utc_now(),
    }
    body["assessment_hash"] = canonical_hash(body)
    return body


def assessment_hash_ok(assessment: dict[str, Any]) -> bool:
    body = {k: v for k, v in assessment.items() if k != "assessment_hash"}
    return canonical_hash(body) == assessment.get("assessment_hash")


def make_approval(task: dict[str, Any], assessment: dict[str, Any], *, identity: str,
                  head: str, approver: str, reason: str, sequence: int = 1) -> dict[str, Any]:
    return {
        "schema_version": "human_approval.v0",
        "approval_id": new_id("approval"),
        "correlation_id": task["correlation_id"],
        "task_id": task["task_id"],
        "assessment_id": assessment["assessment_id"],
        "assessment_hash": assessment["assessment_hash"],
        "repository_identity": identity,
        "authorized_head": head,
        "objective_hash": canonical_hash(task["objective"]),
        "allowed_paths": list(task["scope"]["allowed_paths"]),
        "forbidden_paths": list(task["scope"]["forbidden_paths"]),
        "approved": True,
        "approver": {"type": "HUMAN", "identifier": approver},
        "approved_at": utc_now(),
        "reason": reason,
        "approval_sequence": sequence,
    }


def make_result(task: dict[str, Any], *, session_id: str, outcome: str, identity: str,
                head_before: str | None, head_after: str | None, changed: list[str],
                verification: dict[str, Any], receipt_id: str, evidence_ref: str,
                risks: list[str], human_action_required: bool, next_action: str,
                stop_reason: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "result_packet.v0",
        "result_id": new_id("result"),
        "correlation_id": task["correlation_id"],
        "task_id": task["task_id"],
        "repoguard_session_id": session_id,
        "outcome": outcome,
        "repository": {"identity": identity, "starting_head": head_before, "ending_head": head_after},
        "changed_paths": sorted(changed),
        "verification": verification,
        "evidence": {"receipt_id": receipt_id, "reference": evidence_ref, "integrity": "LEDGER_HASH_CHAINED"},
        "unresolved_risks": risks,
        "human_action_required": human_action_required,
        "next_action": next_action,
        "stop_reason": stop_reason,
        "created_at": utc_now(),
    }
    if task.get("playbook"):
        pb = task["playbook"]
        result["playbook"] = {"id": pb["id"], "version": pb["version"], "fingerprint": pb["fingerprint"]}
    return result
