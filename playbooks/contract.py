"""Dependency-free versioned engineering playbook contract v0."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUIRED = ("schema_version", "id", "version", "fingerprint", "purpose", "applicability", "phases", "required_discovery", "required_artifacts", "required_verification", "allowed_capabilities", "human_gates", "stop_conditions", "failure_handling", "prohibited_shortcuts", "platform_requirements")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(playbook: dict[str, Any]) -> str:
    content = {key: value for key, value in playbook.items() if key != "fingerprint"}
    return "sha256:" + hashlib.sha256(canonical_bytes(content)).hexdigest()


def parameters_fingerprint(parameters: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(parameters)).hexdigest()


def validate(playbook: Any) -> list[str]:
    if not isinstance(playbook, dict):
        return ["playbook must be an object"]
    errors = [f"missing required field: {key}" for key in REQUIRED if key not in playbook]
    if errors:
        return errors
    if playbook["schema_version"] != "engineering_playbook.v0":
        errors.append("schema_version must be engineering_playbook.v0")
    if not isinstance(playbook["id"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", playbook["id"]):
        errors.append("id must be an uppercase identifier")
    if not isinstance(playbook["version"], str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", playbook["version"]):
        errors.append("version must be semver")
    if not isinstance(playbook["fingerprint"], str) or not HASH.fullmatch(playbook["fingerprint"]):
        errors.append("fingerprint must be sha256:<64 lowercase hex>")
    elif playbook["fingerprint"] != fingerprint(playbook):
        errors.append("fingerprint does not match canonical playbook content")
    if not isinstance(playbook["phases"], list) or not playbook["phases"]:
        errors.append("phases must be a non-empty array")
    if not isinstance(playbook["platform_requirements"], dict):
        errors.append("platform_requirements must be an object")
    return errors


def resolve(canonical: dict[str, Any], authority: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    """Resolve procedural narrowing only; never grants authorization."""
    if validate(canonical):
        raise ValueError("invalid canonical playbook")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    decision = authority.get("decision", "ACCEPT")
    if decision == "REJECT":
        raise ValueError("project authority rejected playbook")
    effective = deepcopy(canonical)
    if decision == "NARROW":
        excluded = set(authority.get("excluded_phase_ids", []))
        effective["phases"] = [phase for phase in effective["phases"] if phase["id"] not in excluded]
    elif decision == "REPLACE_STEP":
        replacements = authority.get("phase_replacements", {})
        for phase in effective["phases"]:
            phase.update(replacements.get(phase["id"], {}))
    elif decision == "ADD_VERIFICATION":
        effective["required_verification"] = list(effective["required_verification"]) + list(authority.get("required_verification", []))
    elif decision != "ACCEPT":
        raise ValueError("unsupported project resolution decision")
    if authority.get("required_human_gates"):
        effective["human_gates"] = list(effective["human_gates"]) + list(authority["required_human_gates"])
    effective["resolution"] = {"decision": decision, "parameters": parameters}
    effective["canonical_playbook_fingerprint"] = canonical["fingerprint"]
    effective["fingerprint"] = fingerprint(effective)
    return effective


def approval_binding(canonical: dict[str, Any], effective: dict[str, Any], parameters: dict[str, Any]) -> dict[str, str]:
    return {"canonical_playbook_fingerprint": canonical["fingerprint"], "effective_playbook_fingerprint": effective["fingerprint"], "effective_parameters_hash": parameters_fingerprint(parameters)}


def binding_matches(binding: dict[str, Any], expected: dict[str, str]) -> bool:
    return binding == expected


def authorizes_mutation(_: dict[str, Any]) -> bool:
    return False


def establishes_pass(_: dict[str, Any]) -> bool:
    return False
