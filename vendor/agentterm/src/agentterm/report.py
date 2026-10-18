"""Static, self-contained HTML evidence report: the audit trail for AI agent sessions."""

from __future__ import annotations

from html import escape
from typing import Any

from . import ledger as L
from .canon import utc_now

_BADGE = {"PASS": "ok", "BLOCKED_PRECONDITION": "warn", "FAILED_AFTER_EXECUTION": "bad", "DIVERGENCE": "bad"}

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--ok:#1a7f37;--warn:#9a6700;--bad:#cf222e;--card:#f6f8fa}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--line:#30363d;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--card:#161b22}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.mut{color:var(--mut)}code{font:13px ui-monospace,monospace;background:var(--card);padding:1px 5px;border-radius:4px;word-break:break-all}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.badge{font-size:12px;font-weight:600;padding:2px 8px;border-radius:10px;color:#fff;white-space:nowrap}
.ok{background:var(--ok)}.warn{background:var(--warn)}.bad{background:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:8px 0}
details summary{cursor:pointer}ul{margin:4px 0 4px 20px;padding:0}
"""


def _badge(outcome: str) -> str:
    return f'<span class="badge {_BADGE.get(outcome, "warn")}">{escape(outcome)}</span>'


def _list(items: list[str], empty: str = "none") -> str:
    if not items:
        return f'<span class="mut">{escape(empty)}</span>'
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def render_report(ledger: L.Ledger, project: str, *, title: str | None = None) -> str:
    verification = ledger.verify(project)
    outcomes = ledger.events(project, kinds=[L.OUTCOME])
    by_session: dict[str, dict[str, L.Event]] = {}
    for ev in ledger.events(project, kinds=[L.TASK, L.APPROVAL]):
        by_session.setdefault(ev.session or "", {})[ev.kind] = ev
    counts: dict[str, int] = {}
    for ev in outcomes:
        counts[ev.body.get("outcome", "?")] = counts.get(ev.body.get("outcome", "?"), 0) + 1

    rows, details = [], []
    for ev in reversed(outcomes):
        body = ev.body
        packet = body.get("result_packet", {})
        task_ev = by_session.get(ev.session or "", {}).get(L.TASK)
        approval_ev = by_session.get(ev.session or "", {}).get(L.APPROVAL)
        scope = (task_ev.body.get("packet", {}).get("scope", {}) if task_ev else {})
        checks = packet.get("verification", {}).get("checks", [])
        rows.append(
            f"<tr><td>{escape(ev.ts[:19])}Z</td><td>{escape(ev.agent or '-')}</td><td>{escape(body.get('task', '')[:120])}</td>"
            f"<td>{_badge(body.get('outcome', '?'))}</td><td>{len(body.get('changed_paths', []))}</td>"
            f"<td>{escape(packet.get('verification', {}).get('result', 'NOT_RUN'))}</td></tr>"
        )
        approver = (approval_ev.body.get("packet", {}).get("approver", {}).get("identifier") if approval_ev else None)
        check_lines = [str(c.get("id")) + ": " + str(c.get("result")) + " (exit " + str(c.get("exit_code")) + ")" for c in checks]
        details.append(
            f'<details class="card"><summary>{_badge(body.get("outcome", "?"))} {escape(body.get("task", "")[:140])}'
            f' <span class="mut">{escape(ev.ts[:19])}Z</span></summary>'
            f"<p><b>Agent:</b> {escape(ev.agent or '-')} &middot; <b>Approved by:</b> {escape(approver or ('n/a (read-only)' if not scope.get('allowed_paths') else 'NOT RECORDED'))}</p>"
            f"<p><b>Allowed:</b> {_list(scope.get('allowed_paths', []), 'none (read-only)')}</p>"
            f"<p><b>Forbidden:</b> {_list(scope.get('forbidden_paths', []))}</p>"
            f"<p><b>Changed paths (observed through Git):</b> {_list(body.get('changed_paths', []))}</p>"
            f"<p><b>Verification:</b> {_list(check_lines, 'NOT_RUN')}</p>"
            f"<p><b>Reasons:</b> {_list(body.get('reasons', []))}</p>"
            f"<p><b>HEAD:</b> <code>{escape(str(packet.get('repository', {}).get('starting_head')))}</code> &rarr; "
            f"<code>{escape(str(packet.get('repository', {}).get('ending_head')))}</code></p>"
            f"<p class='mut'>receipt <code>{escape(body.get('receipt_id', ''))}</code> &middot; event hash <code>{escape(ev.hash)}</code></p></details>"
        )

    decisions = [e.text for e in ledger.events(project, kinds=[L.DECISION])]
    failed = [e.text for e in ledger.events(project, kinds=[L.FAILED])]
    parked = [e.text for e in ledger.parked(project)]
    status = ('<span class="badge ok">ledger verified</span>' if verification.ok
              else '<span class="badge bad">LEDGER FAILED VERIFICATION</span>')
    summary = " ".join(f"{_badge(k)} &times; {v}" for k, v in sorted(counts.items())) or '<span class="mut">no sessions yet</span>'
    problems = "" if verification.ok else "<div class='card'>" + _list(verification.problems) + "</div>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title or 'Agent evidence report')}</title>
<style>{CSS}</style></head><body>
<h1>{escape(title or 'Agent evidence report')}</h1>
<p class="mut">Repository <code>{escape(project)}</code> &middot; generated {escape(utc_now()[:19])}Z by agentterm</p>
<p>{status} {verification.checked} events checked &middot; chain head <code>{escape(ledger.chain_head(project))}</code></p>{problems}
<h2>Sessions</h2><p>{summary}</p>
<table><tr><th>When</th><th>Agent</th><th>Task</th><th>Outcome</th><th>Changed</th><th>Verification</th></tr>{''.join(rows) or '<tr><td colspan=6 class="mut">No sessions recorded.</td></tr>'}</table>
<h2>Session details</h2>{''.join(details) or '<p class="mut">None.</p>'}
<h2>Binding decisions</h2>{_list(decisions)}
<h2>Failed approaches</h2>{_list(failed)}
<h2>Parked ideas</h2>{_list(parked)}
<p class="mut">Changed paths come from Git observation, not from the agent's own claims. Re-verify with <code>agentterm verify</code>.</p>
</body></html>"""
