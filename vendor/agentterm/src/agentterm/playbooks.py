"""Versioned engineering playbooks (engineering_playbook.v0) with fingerprint checks."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .canon import canonical_hash


class PlaybookError(ValueError):
    pass


def fingerprint(playbook: dict[str, Any]) -> str:
    body = {k: v for k, v in playbook.items() if k != "fingerprint"}
    return canonical_hash(body)


def _all() -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for entry in resources.files("agentterm").joinpath("playbooks").iterdir():
        if entry.name.endswith(".json"):
            data = json.loads(entry.read_text(encoding="utf-8"))
            found[data["id"]] = data
    return found


def list_playbooks() -> list[dict[str, str]]:
    return [
        {"id": p["id"], "version": p["version"], "purpose": p.get("purpose", "")}
        for p in sorted(_all().values(), key=lambda p: p["id"])
    ]


def load(playbook_id: str) -> dict[str, Any]:
    books = _all()
    if playbook_id not in books:
        raise PlaybookError(f"unknown playbook {playbook_id!r}; available: {', '.join(sorted(books))}")
    book = books[playbook_id]
    if fingerprint(book) != book.get("fingerprint"):
        raise PlaybookError(f"playbook {playbook_id} fails fingerprint verification")
    return book


def reference(book: dict[str, Any], parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """The fingerprinted reference carried by a task packet (grants no permission)."""
    return {
        "id": book["id"],
        "version": book["version"],
        "fingerprint": book["fingerprint"],
        "parameters": parameters or {},
    }


def render(book: dict[str, Any]) -> str:
    lines = [
        f"Playbook {book['id']} v{book['version']} ({book['fingerprint'][:19]}...): {book.get('purpose', '')}",
        "This is procedural guidance only. It grants no permission and cannot widen scope.",
        "",
    ]
    for i, phase in enumerate(book.get("phases", []), 1):
        lines.append(f"{i}. {phase['id']}: {phase['objective']}")
        if phase.get("required_artifacts"):
            lines.append("   artifacts: " + "; ".join(phase["required_artifacts"]))
        if phase.get("required_verification"):
            lines.append("   verify: " + "; ".join(phase["required_verification"]))
    if book.get("stop_conditions"):
        lines.append("Stop when: " + "; ".join(book["stop_conditions"]))
    if book.get("prohibited_shortcuts"):
        lines.append("Never: " + "; ".join(book["prohibited_shortcuts"]))
    return "\n".join(lines)
