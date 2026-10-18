"""The governed session loop: one task, one fresh session, one verified checkpoint.

discover (read-only) -> assess -> approve (if mutating) -> build fresh context ->
run the agent -> observe changes via Git -> verify -> classify -> record -> checkpoint.
The agent is never trusted to report its own success: scope, verification and the
outcome all come from observation.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import brief, contracts, context, gitinfo, governance, playbooks
from . import ledger as L
from .canon import est_tokens
from .config import Settings

REPORT_CONTRACT = """
## Reporting contract
Work only inside the scope above and stop after this one task. End your final reply
with a section titled exactly `## Session Report`, using any of these single-line
entries (omit what does not apply):

DECISION: <a binding decision you made and why>
FAILED APPROACH: <something you tried that did not work, so it is never repeated>
PARKED IDEA: <a useful idea outside the current objective>
COMPLETED: <what you believe you finished (this is recorded as an unverified claim)>
NEXT: <the single next action you recommend>
""".strip("\n")

MAX_RESPONSE = 500_000
_REPORT_LINE = re.compile(r"^\s*[-*]?\s*(DECISION|FAILED APPROACH|PARKED IDEA|COMPLETED|NEXT)\s*:\s*(.+?)\s*$", re.I)
_KIND_FOR = {
    "DECISION": L.DECISION, "FAILED APPROACH": L.FAILED, "PARKED IDEA": L.PARKED,
    "COMPLETED": L.CLAIM, "NEXT": L.NEXT,
}


def parse_session_report(text: str) -> list[tuple[str, str]]:
    """Extract typed entries from the agent's ``## Session Report`` section."""
    index = text.lower().rfind("## session report")
    if index < 0:
        return []
    found: list[tuple[str, str]] = []
    for line in text[index:].splitlines()[1:]:
        match = _REPORT_LINE.match(line)
        if not match:
            continue
        label, value = match.group(1).upper(), match.group(2).strip()
        if (value.startswith("<") and value.endswith(">")) or not value:
            continue  # unfilled template placeholder (e.g. an echoed prompt)
        found.append((_KIND_FOR[label], value))
    return found[:60]


@dataclass
class RunRequest:
    task: str
    agent: str
    allowed: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    mutate: bool = False
    verify: list[str] = field(default_factory=list)
    yes: bool = False
    budget: int | None = None
    dry_run: bool = False
    playbook: str | None = None
    timeout: int = 3600
    verify_timeout: int = 900
    extra_context: dict[str, str] = field(default_factory=dict)
    task_id: str | None = None
    correlation_id: str | None = None
    verification_approved: bool = False


@dataclass
class RunReport:
    outcome: str
    exit_code: int
    session_id: str
    reasons: list[str]
    changed_paths: list[str] = field(default_factory=list)
    violations: list[governance.Violation] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    pack: context.ContextPack | None = None
    task_packet: dict[str, Any] | None = None
    result_packet: dict[str, Any] | None = None
    response: str = ""
    dry_run: bool = False
    brief_path: Path | None = None


def _run_check(command: str, cwd: str, timeout: int, *, authorized: bool) -> dict[str, Any]:
    base = {"id": command, "description": f"run {command}",
            "authorization": "APPROVED" if authorized else "NOT_APPROVED"}
    if not authorized:
        return {**base, "result": "BLOCKED_PRECONDITION", "exit_code": 126,
                "output_tail": "verification command requires explicit human authorization"}
    try:
        argv = shlex.split(command)
        if not argv or any(token in {";", "|", "&", "&&", "||", ">", ">>", "<"} for token in argv):
            return {**base, "result": "BLOCKED_PRECONDITION", "exit_code": 126,
                    "output_tail": "verification command contains unsafe shell syntax"}
        executable = shutil.which(argv[0]) if not Path(argv[0]).is_absolute() else argv[0]
        if not executable or not Path(executable).is_file():
            return {**base, "result": "BLOCKED_PRECONDITION", "exit_code": 127,
                    "output_tail": "verification executable is not a resolved regular file"}
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        tail = ((r.stdout or "") + (r.stderr or ""))[-1500:]
        return {**base, "result": "PASS" if r.returncode == 0 else "FAIL",
                "exit_code": r.returncode, "output_tail": tail}
    except subprocess.TimeoutExpired:
        return {**base, "result": "FAIL", "exit_code": 124, "output_tail": "timed out"}
    except (OSError, ValueError) as exc:
        return {**base, "result": "FAIL", "exit_code": 127, "output_tail": str(exc)}


def _approval_summary(req: RunRequest, snap: gitinfo.Snapshot, task: dict[str, Any]) -> str:
    return "\n".join([
        "Approval required before this agent may modify the repository:",
        f"  agent:      {req.agent}",
        f"  repository: {snap.identity}",
        f"  HEAD:       {snap.head}   branch: {snap.branch}   worktree: {snap.worktree_state}",
        f"  objective:  {task['objective'][:200]}",
        f"  allowed:    {', '.join(req.allowed)}",
        f"  forbidden:  {', '.join(req.forbidden) or 'none'}",
        f"  verify:     {', '.join(req.verify) or 'NONE (outcome will carry a risk flag)'}",
    ])


def run_task(
    settings: Settings,
    ledger: L.Ledger,
    req: RunRequest,
    *,
    confirm: Callable[[str], bool] | None = None,
    out: Callable[[str], None] = print,
) -> RunReport:
    snap = gitinfo.snapshot(settings.root)
    project = snap.identity
    session = contracts.new_id("session")
    reasons: list[str] = []
    budget = req.budget or settings.budget_tokens

    book = playbooks.load(req.playbook) if req.playbook else None
    allowed = list(req.allowed) if req.mutate else []
    task = contracts.make_task_packet(
        objective=req.task, repository_locator=snap.root, expected_identity=snap.identity,
        expected_head=snap.head, allowed=allowed, forbidden=list(req.forbidden),
        mutation_allowed=req.mutate,
        verification=[{"id": c, "description": f"run {c}"} for c in req.verify],
        playbook=playbooks.reference(book) if book else None,
        task_id=req.task_id,
        correlation_id=req.correlation_id,
    )

    # ---- preconditions (read-only discovery) ---------------------------------
    adapter = settings.adapter(req.agent)
    errors = contracts.validate("task", task)
    reasons += [f"invalid task packet: {e}" for e in errors]
    if adapter is None:
        reasons.append(f"unknown agent {req.agent!r} (known: {', '.join(settings.agent_names())})")
    elif not req.dry_run and not adapter.available():
        reasons.append(f"agent binary {adapter.binary!r} is not installed (run `agentterm init`)")
    if req.mutate:
        if not snap.is_git:
            reasons.append("mutating tasks require a Git repository (changes are observed through Git)")
        elif not snap.head:
            reasons.append("repository has no commits; make an initial commit first")
        if not req.allowed:
            reasons.append("mutating tasks need explicit --allow paths (an empty scope allows nothing)")
    elif req.verify and not req.verification_approved:
        reasons.append("verification commands require explicit human authorization")

    stale: list[str] = []
    cp_event = ledger.latest(project, L.CHECKPOINT)
    if cp_event:
        for finding in brief.validate_checkpoint(cp_event.body, snap):
            if finding.severity == "reject":
                reasons.append(finding.message)
            else:
                stale.append(finding.message)

    pack = context.build_context(
        ledger, project, task_text=req.task, budget=budget, allowed=allowed,
        forbidden=list(req.forbidden), mutation_allowed=req.mutate,
        playbook_text=playbooks.render(book) if book else None, staleness=stale,
        extra=req.extra_context,
    )
    prompt = pack.render() + "\n" + REPORT_CONTRACT + "\n"

    if req.dry_run:
        out(context.explain(pack.summary()))
        out("\n--- prompt (dry run; nothing was executed or recorded) ---\n" + prompt)
        if reasons:
            out("Would be BLOCKED_PRECONDITION: " + "; ".join(reasons))
        return RunReport("PASS" if not reasons else "BLOCKED_PRECONDITION",
                         0 if not reasons else contracts.EXIT_CODES["BLOCKED_PRECONDITION"], session,
                         reasons, pack=pack, task_packet=task, dry_run=True)

    def rec(kind: str, body: dict[str, Any], **kw: Any) -> L.Event:
        return ledger.append(project, kind, body, session=session, agent=req.agent, **kw)

    rec(L.SESSION_START, {"task_id": task["task_id"], "agent": req.agent, "mutation_allowed": req.mutate},
        text=f"session start: {req.task[:200]}")
    rec(L.TASK, {"text": req.task, "packet": task})
    tool_health = []
    if adapter is not None:
        info = adapter.doctor()
        tool_health.append({"tool": info["agent"], "configured": "YES", "operational": "YES" if info["available"] else "NO",
                            "observed_gap": ", ".join(info["missing_flags"]) or "NONE"})
    assessment = contracts.make_assessment(
        task, snap, tool_health, "agentterm", not reasons,
        "PROJECT BOOTSTRAP ASSESSMENT: " + ("safe to continue to approval." if not reasons else "blocked: " + "; ".join(reasons)))
    rec(L.ASSESSMENT, {"packet": assessment}, text=assessment["human_readable_assessment"])

    executed = False
    agent_ok = True
    response_text = ""
    changed: list[str] = []
    violations: list[governance.Violation] = []
    checks: list[dict[str, Any]] = []
    head_after = snap.head

    # ---- human approval gate (mutation only) ------------------------------------
    if not reasons and req.mutate:
        summary = _approval_summary(req, snap, task)
        approved = req.yes or (confirm(summary) if confirm else False)
        if approved:
            approver = gitinfo.user_identity(settings.root)
            how = "--yes flag" if req.yes else "interactive confirmation"
            approval = contracts.make_approval(task, assessment, identity=snap.identity, head=snap.head or "",
                                               approver=approver, reason=f"Approved exact bounded task via {how}")
            problems = contracts.validate("approval", approval)
            if problems:
                reasons += [f"invalid approval: {p}" for p in problems]
            else:
                task["approval_state"] = "APPROVED"
                req.verification_approved = True
                rec(L.APPROVAL, {"packet": approval}, text=f"approved by {approver} via {how}")
        else:
            reasons.append("approval not granted for a mutating task")
            rec(L.NOTE, {"text": "Human approval declined; nothing was executed."})

    # ---- execute ---------------------------------------------------------------
    if not reasons:
        rec(L.CONTEXT_PACK, pack.summary(), text=f"context pack {pack.used}/{pack.budget} tokens")
        rec(L.PROMPT, {"prompt": prompt}, text=f"prompt ({est_tokens(prompt)} tokens)")
        before = gitinfo.worktree_fingerprint(settings.root) if snap.is_git else {}
        out(f"[agentterm] running {req.agent} ({'read-write, approved' if req.mutate else 'read-only'}), context {pack.used}/{pack.budget} tokens")
        result = adapter.run(prompt, cwd=snap.root, mutation_allowed=req.mutate, is_git=snap.is_git,
                             timeout=req.timeout, env={"AGENTTERM_SESSION_ID": session})
        executed = True
        agent_ok = result.ok
        response_text = result.text[:MAX_RESPONSE]
        if snap.is_git:
            after = gitinfo.worktree_fingerprint(settings.root)
            head_after = gitinfo.snapshot(settings.root).head
            changed = gitinfo.changed_paths(settings.root, before, after, snap.head, head_after)
        violations = governance.scope_violations(changed, allowed, list(req.forbidden))
        if not result.ok:
            reasons.append("agent timed out" if result.timed_out else f"agent exited with code {result.returncode}"
                           + (f" ({result.error})" if result.error else ""))
        rec(L.RESPONSE, {"text": response_text, "returncode": result.returncode, "duration_s": round(result.duration, 2),
                         "timed_out": result.timed_out, "stderr_tail": result.stderr[-2000:]}, text=response_text)
        for kind, value in parse_session_report(response_text):
            body: dict[str, Any] = {"text": value, "source": "agent"}
            if kind == L.PARKED:
                body["blocks_objective"] = False
            rec(kind, body)
        for v in violations:
            reasons.append(f"scope violation: {v.path} {v.reason}")
        for command in req.verify:
            check = _run_check(command, snap.root, req.verify_timeout, authorized=req.verification_approved)
            checks.append(check)
            rec(L.VERIFICATION, check, text=f"verification {command}: {check['result']}\n{check['output_tail']}")
            if check["result"] != "PASS":
                reasons.append(f"verification failed: {command}")

    verification_ok = all(c["result"] == "PASS" for c in checks)
    outcome = governance.classify(preconditions_ok=executed or not reasons, executed=executed,
                                  agent_ok=agent_ok, verification_ok=verification_ok, violations=violations)
    risks: list[str] = []
    if executed and req.mutate and not req.verify:
        risks.append("No verification commands were run; completion is not externally evidenced.")
    if snap.dirty:
        risks.append(f"{len(snap.dirty_paths)} pre-existing dirty path(s) were present before the session and were preserved.")
    if outcome != "PASS":
        next_action = "Resolve the recorded reasons; do not retry by broadening scope."
    else:
        next_action = "STOP"
    receipt = contracts.new_id("receipt")
    result_packet = contracts.make_result(
        task, session_id=session, outcome=outcome, identity=snap.identity, head_before=snap.head,
        head_after=head_after, changed=changed,
        verification={"performed": bool(checks), "result": ("PASS" if verification_ok else "FAIL") if checks else "NOT_RUN",
                      "checks": [{k: v for k, v in c.items() if k != "output_tail"} for c in checks]},
        receipt_id=receipt, evidence_ref=f"ledger:{session}", risks=risks,
        human_action_required=outcome != "PASS" or bool(risks and req.mutate and not req.verify),
        next_action=next_action, stop_reason="ONE_VERIFIED_CHECKPOINT" if outcome == "PASS" else outcome,
    )
    problems = contracts.validate("result", result_packet)
    if problems:  # a programming error, never an agent error
        raise RuntimeError("internal: invalid result packet: " + "; ".join(problems))
    rec(L.OUTCOME, {
        "outcome": outcome, "task": req.task, "receipt_id": receipt, "reasons": reasons, "changed_paths": changed,
        "result_packet": result_packet, "verification": {"checks": result_packet["verification"]["checks"]},
    }, text=f"{outcome}: {req.task[:200]}" + ("\n" + "\n".join(reasons) if reasons else ""))
    rec(L.SESSION_END, {"outcome": outcome}, text=f"session end: {outcome}")

    cp = brief.build_checkpoint(ledger, project, gitinfo.snapshot(settings.root))
    rec(L.CHECKPOINT, cp, text=f"checkpoint {cp['status']}; next: {cp['next_action']}")
    brief_path, _ = brief.write_brief(settings.root, cp)
    return RunReport(outcome, contracts.EXIT_CODES[outcome], session, reasons, changed, violations, checks,
                     pack, task, result_packet, response_text, brief_path=brief_path)


def open_interactive(settings: Settings, ledger: L.Ledger, agent: str, *, budget: int | None = None,
                     out: Callable[[str], None] = print) -> int:
    """Launch an agent interactively with a freshly built brief; capture what changed afterwards.

    Interactive sessions cannot be sandboxed or gated by agentterm (the agent owns the
    terminal), so only the resulting Git changes and a one-line human summary are recorded.
    """
    adapter = settings.adapter(agent)
    if adapter is None or not adapter.available():
        out(f"agent {agent!r} is not available")
        return contracts.EXIT_CODES["BLOCKED_PRECONDITION"]
    snap = gitinfo.snapshot(settings.root)
    project = snap.identity
    session = contracts.new_id("session")
    cp_event = ledger.latest(project, L.CHECKPOINT)
    stale = [f.message for f in brief.validate_checkpoint(cp_event.body, snap) if f.severity != "reject"] if cp_event else []
    pack = context.build_context(ledger, project, task_text="Continue toward the objective from the last checkpoint.",
                                 budget=min(budget or settings.budget_tokens, 20_000), allowed=["(interactive: you decide)"],
                                 forbidden=[], mutation_allowed=True, staleness=stale)
    prompt = pack.render() + "\nStart by confirming the objective and next action, then work with the user.\n"
    ledger.append(project, L.SESSION_START, {"interactive": True}, text=f"interactive session with {agent}", session=session, agent=agent)
    ledger.append(project, L.CONTEXT_PACK, pack.summary(), text=f"context pack {pack.used}/{pack.budget} tokens", session=session, agent=agent)
    before = gitinfo.worktree_fingerprint(settings.root) if snap.is_git else {}
    code = subprocess.call(adapter.interactive_command(prompt), cwd=snap.root)
    changed: list[str] = []
    if snap.is_git:
        after = gitinfo.worktree_fingerprint(settings.root)
        changed = gitinfo.changed_paths(settings.root, before, after, snap.head, gitinfo.snapshot(settings.root).head)
    summary = ""
    if sys.stdin.isatty():
        try:
            summary = input("One-line summary of this session (enter to skip): ").strip()
        except EOFError:
            summary = ""
    ledger.append(project, L.NOTE, {"text": f"Interactive {agent} session changed {len(changed)} path(s): {', '.join(changed[:20])}."
                                     + (f" Human summary: {summary}" if summary else ""), "source": "interactive",
                                     "changed_paths": changed}, session=session, agent=agent)
    ledger.append(project, L.SESSION_END, {"exit_code": code}, text=f"interactive session end (exit {code})", session=session, agent=agent)
    cp = brief.build_checkpoint(ledger, project, gitinfo.snapshot(settings.root))
    ledger.append(project, L.CHECKPOINT, cp, text=f"checkpoint {cp['status']}; next: {cp['next_action']}")
    brief.write_brief(settings.root, cp)
    return code
