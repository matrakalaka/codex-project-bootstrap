"""Dependency-free IC-1 contract validation and canonical hashing."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
SCHEMA_FILES = {
    "task": "task_packet.v0.schema.json",
    "bootstrap": "bootstrap_assessment.v0.schema.json",
    "approval": "human_approval.v0.schema.json",
    "result": "result_packet.v0.schema.json",
}
OUTCOMES = {"PASS", "BLOCKED_PRECONDITION", "FAILED_AFTER_EXECUTION", "DIVERGENCE"}
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_UNORDERED_ARRAY_KEYS = {
    "allowed_paths", "forbidden_paths", "required_sources",
    "authority_change_allowed_paths", "required_capabilities",
    "known_good_references",
}


def _normalized(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: _normalized(value[k], k) for k in sorted(value)}
    if isinstance(value, list):
        items = [_normalized(item) for item in value]
        if key in _UNORDERED_ARRAY_KEYS:
            return sorted(items, key=lambda item: json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ))
        return items
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _normalized(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _required(obj: dict, fields: tuple[str, ...], errors: list[str]) -> None:
    errors.extend(f"missing required field: {field}" for field in fields if field not in obj)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and bool(_HASH.fullmatch(value))


def _scope_overlap(left: str, right: str) -> bool:
    def parts(value: str) -> tuple[str, ...]:
        value = value.replace("\\", "/").strip("/")
        if value.endswith("/**"):
            value = value[:-3]
        return tuple(part for part in value.split("/") if part and part != ".")
    a, b = parts(left), parts(right)
    return bool(a and b and (a == b or a[:len(b)] == b or b[:len(a)] == a))


def _validate_playbook(value: Any, errors: list[str], *, result: bool = False) -> None:
    if not isinstance(value, dict):
        errors.append("playbook must be an object")
        return
    required = ("id", "version", "fingerprint")
    if not result:
        required += ("parameters",)
    _required(value, required, errors)
    if "fingerprint" in value and not _hash(value["fingerprint"]):
        errors.append("playbook fingerprint must be sha256:<64 lowercase hex>")
    if not result and "parameters" in value and not isinstance(value["parameters"], dict):
        errors.append("playbook parameters must be an object")


def validate(kind: str, value: Any) -> list[str]:
    errors: list[str] = []
    if kind not in SCHEMA_FILES:
        return [f"unknown contract kind: {kind}"]
    if not isinstance(value, dict):
        return ["contract must be an object"]
    expected = {
        "task": "task_packet.v0",
        "bootstrap": "bootstrap_assessment.v0",
        "approval": "human_approval.v0",
        "result": "result_packet.v0",
    }[kind]
    if value.get("schema_version") != expected:
        errors.append(f"schema_version must be {expected}")

    required = {
        "task": ("schema_version", "correlation_id", "task_id", "origin", "target", "objective", "scope", "authority_requirements", "mutation_allowed", "required_verification", "required_capabilities", "known_good_references", "approval_state", "retry", "stop_condition"),
        "bootstrap": ("schema_version", "assessment_id", "correlation_id", "task_id", "source_revision", "target", "authority", "tool_health", "known_good_references", "recommended_scope", "safe_to_bootstrap", "human_readable_assessment", "assessment_hash", "created_at"),
        "approval": ("schema_version", "approval_id", "correlation_id", "task_id", "assessment_id", "assessment_hash", "repository_identity", "authorized_head", "objective_hash", "allowed_paths", "forbidden_paths", "approved", "approver", "approved_at", "reason", "approval_sequence"),
        "result": ("schema_version", "result_id", "correlation_id", "task_id", "repoguard_session_id", "outcome", "repository", "changed_paths", "verification", "evidence", "unresolved_risks", "human_action_required", "next_action", "stop_reason", "created_at"),
    }[kind]
    _required(value, required, errors)
    if errors and any(field not in value for field in required):
        return errors
    if not isinstance(value.get("objective", ""), str) or not value["objective"].strip() if kind == "task" else False:
        errors.append("objective must be non-empty")

    if kind == "task":
        scope = value["scope"]
        if not isinstance(scope, dict):
            errors.append("scope must be an object")
        else:
            allowed, forbidden = scope.get("allowed_paths", []), scope.get("forbidden_paths", [])
            if not isinstance(allowed, list) or not isinstance(forbidden, list):
                errors.append("scope paths must be arrays")
            elif any(_scope_overlap(a, f) for a in allowed for f in forbidden):
                errors.append("allowed and forbidden scope collide")
        if value.get("playbook") is not None:
            _validate_playbook(value["playbook"], errors)
    elif kind == "bootstrap":
        if not _hash(value["assessment_hash"]):
            errors.append("assessment_hash must be sha256:<64 lowercase hex>")
    elif kind == "approval":
        if value["approved"] is not True:
            errors.append("approval must be explicitly true")
        approver = value["approver"]
        if not isinstance(approver, dict) or approver.get("type") != "HUMAN" or not approver.get("identifier"):
            errors.append("approval requires an attributable HUMAN approver")
        if not _hash(value["assessment_hash"]) or not _hash(value["objective_hash"]):
            errors.append("approval hashes must be sha256:<64 lowercase hex>")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", value["authorized_head"]):
            errors.append("authorized_head must be a full commit SHA")
        if "playbook_binding" in value:
            binding = value["playbook_binding"]
            if not isinstance(binding, dict) or not _hash(binding.get("fingerprint")) or not _hash(binding.get("parameters_hash")):
                errors.append("playbook binding requires valid fingerprints")
    elif kind == "result":
        if value["outcome"] not in OUTCOMES:
            errors.append("outcome is not in the standard vocabulary")
        if "playbook" in value:
            _validate_playbook(value["playbook"], errors, result=True)
    return errors


def validate_file(kind: str, path: str | Path) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        return validate(kind, json.load(handle))
