#!/usr/bin/env python3
"""Fail-closed, allowlisted host-operation bridge for synthetic Bootstrap checks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


OPERATIONS = {
    "git_status": lambda target: (["git", "-C", str(target), "status", "--short", "--branch"], target),
    "fixture_echo": lambda target: (["/bin/echo", "BOOTSTRAP_HOST_FIXTURE_OK"], target),
}


def _audit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def execute(request: dict[str, Any], *, audit_path: Path, approved: bool, env: dict[str, str]) -> dict[str, Any]:
    operation = request.get("operation")
    raw_target = request.get("target", ".")
    target = Path(raw_target).expanduser().resolve() if isinstance(raw_target, str) else Path(".").resolve()
    record: dict[str, Any] = {
        "timestamp": time.time(),
        "operation": operation,
        "target": str(target),
        "approved": approved,
    }
    if env.get("CODEX_BOOTSTRAP_HOST_EXECUTION") != "1":
        record.update(outcome="BLOCKED_PRECONDITION", reason="host execution is disabled")
        _audit(audit_path, record)
        return record
    if not approved or request.get("authorization") != "OWNER_APPROVED":
        record.update(outcome="BLOCKED_PRECONDITION", reason="explicit owner authorization is required")
        _audit(audit_path, record)
        return record
    if operation not in OPERATIONS:
        record.update(outcome="BLOCKED_PRECONDITION", reason="operation is not allowlisted")
        _audit(audit_path, record)
        return record
    if not isinstance(raw_target, str) or not raw_target.strip():
        record.update(outcome="BLOCKED_PRECONDITION", reason="target must be a non-empty path")
        _audit(audit_path, record)
        return record
    if operation == "git_status" and not (target / ".git").exists():
        record.update(outcome="BLOCKED_PRECONDITION", reason="git_status target is not a repository root")
        _audit(audit_path, record)
        return record
    if not target.exists() and operation == "git_status":
        record.update(outcome="BLOCKED_PRECONDITION", reason="target does not exist")
        _audit(audit_path, record)
        return record
    argv, command_target = OPERATIONS[operation](target)
    record["argv"] = argv
    record["command_preview"] = " ".join(argv)
    try:
        result = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        record.update(outcome="FAILED_AFTER_EXECUTION", reason="operation timed out")
    except OSError as error:
        record.update(outcome="FAILED_AFTER_EXECUTION", reason=f"host operation failed: {error}")
    else:
        record.update(
            outcome="PASS" if result.returncode == 0 else "FAILED_AFTER_EXECUTION",
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    _audit(audit_path, record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--audit-log", type=Path, required=True)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        result = execute(request, audit_path=args.audit_log, approved=args.approve, env=dict(os.environ))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"outcome": "BLOCKED_PRECONDITION", "reason": str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
