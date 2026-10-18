"""Best-effort secret redaction applied before anything enters the ledger."""

from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED:private-key]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "[REDACTED:api-key]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "[REDACTED:github-token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"), "[REDACTED:github-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED:aws-key]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[REDACTED:slack-token]"),
    (re.compile(r"(?i)\b(authorization:\s*bearer)\s+[A-Za-z0-9._\-]{16,}"), r"\1 [REDACTED]"),
    (re.compile(
        r"(?i)\b((?:api[_-]?key|secret|token|password|passwd)\s*[=:]\s*)(['\"]?)[^\s'\"]{8,}\2"),
     r"\1[REDACTED]"),
]


def redact_text(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_obj(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_obj(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_obj(v) for v in value]
    return value
