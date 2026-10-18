"""Scope enforcement and outcome classification.

The agent proposes; the terminal observes. Changed paths come from Git, never
from the agent's own claims, and scope violations produce DIVERGENCE.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass


def _norm(path: str) -> str:
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.strip("/")


def matches(path: str, pattern: str) -> bool:
    """Match ``path`` against a scope pattern.

    ``dir/**`` and ``dir`` cover everything under ``dir``; ``**`` covers everything;
    other patterns use fnmatch semantics (``*`` crosses ``/`` so ``*.md`` matches any depth).
    """
    path, pattern = _norm(path), _norm(pattern)
    if pattern in ("**", "*", ""):
        return pattern != ""
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    if not any(ch in pattern for ch in "*?["):
        return path == pattern or path.startswith(pattern + "/")
    return fnmatch.fnmatchcase(path, pattern)


@dataclass(frozen=True)
class Violation:
    path: str
    reason: str


def scope_violations(changed: list[str], allowed: list[str], forbidden: list[str]) -> list[Violation]:
    """Forbidden always wins. An empty ``allowed`` list allows nothing."""
    found: list[Violation] = []
    for path in changed:
        if any(matches(path, f) for f in forbidden):
            found.append(Violation(path, "matches a forbidden path"))
        elif not any(matches(path, a) for a in allowed):
            found.append(Violation(path, "is outside the allowed paths"))
    return found


def classify(
    *,
    preconditions_ok: bool,
    executed: bool,
    agent_ok: bool,
    verification_ok: bool,
    violations: list[Violation],
) -> str:
    """Map observed facts to the standard outcome vocabulary.

    DIVERGENCE (a boundary was crossed) outranks FAILED_AFTER_EXECUTION, which
    outranks PASS. Anything that stopped before execution is BLOCKED_PRECONDITION.
    """
    if not preconditions_ok or not executed:
        return "BLOCKED_PRECONDITION"
    if violations:
        return "DIVERGENCE"
    if not agent_ok or not verification_ok:
        return "FAILED_AFTER_EXECUTION"
    return "PASS"
