"""Generated checkpoints: the CONTINUE_TOMORROW handoff, projected from the ledger.

codex-project-bootstrap keeps one canonical, hand-written continuity checkpoint.
agentterm generates the same shape deterministically from the event log, so the
checkpoint can never be missing, and checks it against live Git facts so a
stale or foreign checkpoint is reported instead of silently trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import ledger as L
from . import gitinfo
from .canon import utc_now

MARKER = "<!-- agentterm:generated -->"
STATUS_BY_OUTCOME = {
    "PASS": "PASS",
    "BLOCKED_PRECONDITION": "BLOCKED",
    "FAILED_AFTER_EXECUTION": "FAILED",
    "DIVERGENCE": "CONTRADICTORY",
}


@dataclass(frozen=True)
class Finding:
    severity: str  # "reject" | "stale" | "info"
    message: str


def _short(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def build_checkpoint(ledger: L.Ledger, project: str, snap: gitinfo.Snapshot) -> dict[str, Any]:
    objective = ledger.objective(project)
    floor = objective.seq if objective else 0
    outcomes = [e for e in ledger.events(project, kinds=[L.OUTCOME]) if e.seq > floor]
    last = outcomes[-1] if outcomes else None
    complete = ledger.latest(project, L.COMPLETE)
    is_complete = bool(complete and complete.seq > floor and (not last or complete.seq > last.seq))

    decisions = [_short(e.text) for e in ledger.events(project, kinds=[L.DECISION]) if e.seq > floor][-30:]
    completed, failed, evidence, validation = [], [], [], []
    validated_head = None
    for ev in outcomes:
        outcome = ev.body.get("outcome")
        task = _short(ev.body.get("task", ev.text), 160)
        receipt = ev.body.get("receipt_id", ev.id[:8])
        if outcome == "PASS":
            completed.append(f"{task}  [evidence {receipt}]")
            validated_head = (ev.body.get("result_packet", {}).get("repository", {}) or {}).get("ending_head") or validated_head
        else:
            reasons = "; ".join(ev.body.get("reasons", [])) or outcome
            failed.append(f"{task}: {outcome} ({_short(reasons, 160)})  [evidence {receipt}]")
        evidence.append(f"{ev.ts[:19]}Z {outcome} receipt={receipt} hash={ev.hash[:19]}")
        for check in ev.body.get("verification", {}).get("checks", []):
            validation.append(f"{check.get('id', 'check')}: {check.get('result')} (exit {check.get('exit_code')})")
    failed += [_short(e.text) for e in ledger.events(project, kinds=[L.FAILED]) if e.seq > floor][-15:]
    claims = [_short(e.text) for e in ledger.events(project, kinds=[L.CLAIM]) if e.seq > floor][-10:]
    parked = [_short(e.text) for e in ledger.parked(project)]

    next_events = [e for e in ledger.events(project, kinds=[L.NEXT]) if e.seq > floor]
    if is_complete:
        next_action = "STOP_COMPLETE"
    elif next_events:
        next_action = _short(next_events[-1].text, 300)
    elif last and last.body.get("outcome") != "PASS":
        next_action = "Resolve the recorded blocker or failure, then re-run the task (no automatic retry)."
    else:
        next_action = "NONE RECORDED (set one with `agentterm next`)"

    if is_complete:
        status = "STOP_COMPLETE"
    elif last:
        status = STATUS_BY_OUTCOME.get(last.body.get("outcome", ""), "PARTIAL")
    else:
        status = "ACTIVE"

    contradictions: list[str] = []
    material: list[str] = []
    if validated_head and snap.head and validated_head != snap.head:
        contradictions.append(f"HEAD moved since last validated session (validated {validated_head[:12]}, observed {snap.head[:12]}).")
        out = gitinfo._git(["diff", "--name-only", validated_head, snap.head], snap.root)
        material = [line for line in (out or "").splitlines() if line.strip()][:25]
    if not validated_head:
        contradictions.append("No validated (PASS) session yet; no HEAD has been verified.")
    if snap.dirty:
        contradictions.append(f"Worktree is dirty ({len(snap.dirty_paths)} path(s)); pre-existing work is preserved, not attributed to any session.")

    last_event = ledger.events(project, limit=1, desc=True)
    seq = last_event[0].seq if last_event else 0
    return {
        "checkpoint_id": f"cp-{seq}",
        "date": utc_now()[:10],
        "generated_at": utc_now(),
        "objective": objective.body if objective else None,
        "repository_identity": snap.identity,
        "remote": snap.remote,
        "root": snap.root,
        "validated_head": validated_head,
        "current_head": snap.head,
        "branch": snap.branch,
        "worktree_state": snap.worktree_state,
        "dirty_paths": list(snap.dirty_paths),
        "material_changes_since_validation": material,
        "status": status,
        "decisions": decisions,
        "completed": completed,
        "agent_claims_unverified": claims,
        "failed": failed,
        "evidence": evidence[-15:],
        "validation": validation[-15:],
        "parked": parked,
        "contradictions": contradictions,
        "next_action": next_action,
        "ledger_head": ledger.chain_head(project),
        "ledger_events": ledger.count(project),
    }


def validate_checkpoint(cp: dict[str, Any], snap: gitinfo.Snapshot) -> list[Finding]:
    """Compare a stored checkpoint with live repository facts."""
    findings: list[Finding] = []
    if cp.get("repository_identity") != snap.identity:
        findings.append(Finding("reject", f"Checkpoint belongs to {cp.get('repository_identity')!r}, not this repository ({snap.identity!r}). Rejected."))
        return findings
    if cp.get("branch") and snap.branch and cp["branch"] != snap.branch:
        findings.append(Finding("stale", f"Branch changed since checkpoint ({cp['branch']} -> {snap.branch})."))
    if cp.get("current_head") and snap.head and cp["current_head"] != snap.head:
        findings.append(Finding("stale", f"HEAD changed since checkpoint ({cp['current_head'][:12]} -> {snap.head[:12]}); re-verify before relying on completed work."))
    if cp.get("status") in ("BLOCKED", "FAILED", "CONTRADICTORY"):
        findings.append(Finding("info", f"Previous session ended {cp['status']}; see failed approaches and do not repeat them."))
    return findings


def render_markdown(cp: dict[str, Any]) -> str:
    obj = cp.get("objective") or {}

    def bullets(items: list[str], empty: str = "NONE RECORDED") -> str:
        return "\n".join(f"- {i}" for i in items) if items else f"- {empty}"

    short_head = (cp.get("current_head") or "UNKNOWN")
    return f"""{MARKER}
# CONTINUE_TOMORROW.md

## PURPOSE
Concise handoff between sessions, generated from the agentterm ledger. It is a
projection of recorded events and Git state, not a second authority or a
transcript. Verify it against the repository before relying on it.

# LATEST CHECKPOINT

**Checkpoint ID:** {cp['checkpoint_id']}
**Date:** {cp['date']}
**Original Objective:** {obj.get('objective', 'NOT SET')}
**Required Proof:** {obj.get('proof') or 'NOT RECORDED'}
**Repository Identity:** {cp['repository_identity']}
**Repository Remote:** {cp.get('remote') or 'NOT RECORDED'}
**HEAD (Validated Source Revision):** {cp.get('validated_head') or 'NOT VALIDATED'}
**Current Observed HEAD:** {short_head}
**Branch:** {cp.get('branch') or 'UNKNOWN'}
**Worktree State:** {cp['worktree_state']}{(' - ' + ', '.join(cp['dirty_paths'][:8])) if cp['dirty_paths'] else ''}
**Material Source Changes Since Validation:** {', '.join(cp['material_changes_since_validation']) or 'NONE'}
**Status:** {cp['status']}
**Ledger:** {cp['ledger_events']} events, chain head {cp['ledger_head']}

## Out of Scope / Stop Boundary
- Out of scope: {obj.get('out_of_scope') or 'NOT RECORDED'}
- Stop boundary: {obj.get('stop') or 'NOT RECORDED'}

## Binding Decisions
{bullets(cp['decisions'])}

## Verified Completed Work
{bullets(cp['completed'])}

## Agent-Reported Work (UNVERIFIED claims)
{bullets(cp['agent_claims_unverified'])}

## Evidence References
{bullets(cp['evidence'])}

## Failed Approaches and Blockers
{bullets(cp['failed'])}

## Validation Summary
{bullets(cp['validation'], 'NOT_RUN')}

## Contradictions and Staleness
{bullets(cp['contradictions'], 'NONE')}

## Parked Ideas
{bullets(cp['parked'], 'NONE')}

## Next Approved Action
{cp['next_action']}

## Stop
Do not begin another task automatically. If the status is `STOP_COMPLETE`, the
next approved action is `STOP_COMPLETE`.
"""


def write_brief(root: Path | str, cp: dict[str, Any], *, publish: bool = False, force: bool = False) -> tuple[Path, str]:
    """Write ``.agentterm/briefs/latest.md``; optionally publish ``CONTINUE_TOMORROW.md``.

    Publishing never overwrites a hand-written checkpoint unless ``force`` is set.
    Returns (path written, human-readable note).
    """
    root = Path(root)
    md = render_markdown(cp)
    briefs = root / gitinfo.INTERNAL_DIR / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)
    latest = briefs / "latest.md"
    latest.write_text(md, encoding="utf-8")
    if not publish:
        return latest, "written to .agentterm/briefs/latest.md"
    target = root / "CONTINUE_TOMORROW.md"
    if target.exists() and MARKER not in target.read_text(encoding="utf-8", errors="replace") and not force:
        sidecar = briefs / "CONTINUE_TOMORROW.generated.md"
        sidecar.write_text(md, encoding="utf-8")
        return sidecar, "existing hand-written CONTINUE_TOMORROW.md preserved; generated copy saved beside the brief (use --force to replace)"
    target.write_text(md, encoding="utf-8")
    return target, "published CONTINUE_TOMORROW.md"
