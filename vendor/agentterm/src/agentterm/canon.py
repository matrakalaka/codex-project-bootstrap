"""Canonical JSON and SHA-256 hashing.

Same scheme as the Shared Stack Contracts v0 in codex-project-bootstrap:
UTF-8, sorted object keys, compact separators, arrays keep their order,
hashes are ``sha256:<64 lowercase hex>``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def est_tokens(text: str) -> int:
    """Cheap token estimate (~4 characters per token); good enough for budgeting."""
    return max(1, (len(text) + 3) // 4)
