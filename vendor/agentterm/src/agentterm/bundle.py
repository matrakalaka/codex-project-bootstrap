"""Portable, verifiable memory bundles (Phase 2: sync and team memory foundation).

A bundle is a JSONL file: a header line plus one event per line. The header commits to
each hash chain's head, and may carry an HMAC so teammates sharing a key can detect
tampering. Importing re-verifies every chain before anything is written, and refuses
bundles from a different repository unless explicitly allowed (project isolation).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from .canon import canonical_bytes, utc_now
from . import ledger as L

FORMAT = "agentterm-bundle/1"


class BundleError(ValueError):
    pass


def _sign(key: bytes, header: dict[str, Any]) -> str:
    core = {k: header[k] for k in ("format", "project", "count", "heads")}
    return hmac.new(key, canonical_bytes(core), hashlib.sha256).hexdigest()


def export_bundle(ledger: L.Ledger, project: str, path: Path | str, *, key: bytes | None = None) -> dict[str, Any]:
    events = ledger.events(project)
    if not events:
        raise BundleError("nothing to export for this project")
    heads: dict[str, str] = {}
    for ev in events:
        heads[ev.origin] = ev.hash
    header: dict[str, Any] = {
        "format": FORMAT, "project": project, "count": len(events), "heads": heads,
        "exported_at": utc_now(),
    }
    header["hmac"] = _sign(key, header) if key else None
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(header, sort_keys=True) + "\n")
        for ev in events:
            handle.write(json.dumps(ev.as_dict(), sort_keys=True, ensure_ascii=False) + "\n")
    return header


def read_bundle(path: Path | str, *, key: bytes | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise BundleError("empty bundle")
    try:
        header = json.loads(lines[0])
        events = [json.loads(line) for line in lines[1:] if line.strip()]
    except json.JSONDecodeError as exc:
        raise BundleError(f"bundle is not valid JSONL: {exc}") from exc
    if header.get("format") != FORMAT:
        raise BundleError(f"unsupported bundle format {header.get('format')!r}")
    if header.get("count") != len(events):
        raise BundleError("event count does not match the header (truncated or edited bundle)")
    if key is not None:
        if not header.get("hmac"):
            raise BundleError("a key was supplied but the bundle is unsigned")
        if not hmac.compare_digest(header["hmac"], _sign(key, header)):
            raise BundleError("bundle signature does not match (wrong key or tampered header)")
    by_origin: dict[str, list[dict[str, Any]]] = {}
    for raw in events:
        if raw.get("project") != header["project"]:
            raise BundleError("bundle mixes projects")
        by_origin.setdefault(raw["origin"], []).append(raw)
    for origin, chain in by_origin.items():
        problems = L.verify_events(chain)
        if problems:
            raise BundleError(f"chain {origin[:8]} failed verification: {problems[0]}")
        if header["heads"].get(origin) != chain[-1]["hash"]:
            raise BundleError(f"chain {origin[:8]} head does not match the header")
    return header, events


def import_bundle(ledger: L.Ledger, path: Path | str, *, project: str,
                  key: bytes | None = None) -> tuple[int, int]:
    """Verify, then import. Memory is repository-owned: a bundle from another repository is refused."""
    header, events = read_bundle(path, key=key)
    if header["project"] != project:
        raise BundleError(f"bundle is for {header['project']!r}, not this repository ({project!r}); refusing")
    return ledger.import_events(events)
