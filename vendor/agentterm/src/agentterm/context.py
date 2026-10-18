"""Build a fresh, small, explainable context for each agent session.

The model's window is never the memory. For every session the terminal composes
a new context from the ledger under a token budget: North Star and pinned facts
always go in, the last checkpoint is compacted to a cap, and the remaining
budget is spent on retrieved history (BM25 + kind weights + recency). Every item
records its provenance so ``agentterm why`` can show exactly what was injected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import ledger as L
from .canon import est_tokens

HISTORY_KINDS = (L.DECISION, L.FAILED, L.OUTCOME, L.VERIFICATION, L.TASK, L.NOTE, L.CLAIM, L.RESPONSE)
_KIND_WEIGHT = {
    L.DECISION: 1.6, L.FAILED: 1.6, L.OUTCOME: 1.2, L.VERIFICATION: 1.1,
    L.TASK: 1.0, L.NOTE: 1.0, L.CLAIM: 0.8, L.RESPONSE: 0.8,
}
PIN_CAP = 0.30
CHECKPOINT_CAP = 0.25
HISTORY_ITEM_CHARS = 800


@dataclass
class Item:
    section: str
    text: str
    tokens: int
    event_ids: list[str] = field(default_factory=list)
    mandatory: bool = False
    note: str = ""


@dataclass
class ContextPack:
    budget: int
    query: str
    items: list[Item] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)

    @property
    def used(self) -> int:
        return sum(i.tokens for i in self.items)

    @property
    def over_budget(self) -> bool:
        return self.used > self.budget

    def sections(self) -> list[tuple[str, list[Item]]]:
        order: list[str] = []
        grouped: dict[str, list[Item]] = {}
        for item in self.items:
            if item.section not in grouped:
                grouped[item.section] = []
                order.append(item.section)
            grouped[item.section].append(item)
        return [(name, grouped[name]) for name in order]

    def render(self) -> str:
        parts = [
            "# agentterm session context",
            "Generated fresh for this session from the project's append-only ledger. "
            "The ledger, not this prompt, is the source of truth.",
        ]
        for name, items in self.sections():
            parts.append(f"\n## {name}")
            parts.extend(i.text for i in items)
        return "\n".join(parts) + "\n"

    def summary(self) -> dict[str, Any]:
        return {
            "budget": self.budget,
            "used": self.used,
            "over_budget": self.over_budget,
            "query": self.query[:300],
            "items": [
                {
                    "section": i.section, "tokens": i.tokens, "event_ids": i.event_ids,
                    "mandatory": i.mandatory, "note": i.note,
                    "preview": re.sub(r"\s+", " ", i.text)[:160],
                }
                for i in self.items
            ],
            "dropped": self.dropped,
        }


def _one_line(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def north_star_text(body: dict[str, Any]) -> str:
    return "\n".join([
        f"- Final intended objective: {body.get('objective', '')}",
        f"- Required proof: {body.get('proof') or 'NOT RECORDED'}",
        f"- Explicitly out of scope: {body.get('out_of_scope') or 'NOT RECORDED'}",
        f"- Stop / promotion boundary: {body.get('stop') or 'NOT RECORDED'}",
    ])


def checkpoint_text(cp: dict[str, Any]) -> str:
    lines = [f"- Status: {cp.get('status')}  (checkpoint {cp.get('checkpoint_id')}, validated HEAD {cp.get('validated_head') or 'none'})"]
    for label, key in (("Verified completed", "completed"), ("Binding decisions", "decisions"),
                       ("Failed approaches / blockers (do not repeat)", "failed")):
        values = cp.get(key) or []
        if values:
            lines.append(f"- {label}:")
            lines.extend(f"  - {_one_line(v, 300)}" for v in values)
    lines.append(f"- Next approved action: {cp.get('next_action')}")
    return "\n".join(lines)


def build_context(
    ledger: L.Ledger,
    project: str,
    *,
    task_text: str,
    budget: int,
    allowed: list[str],
    forbidden: list[str],
    mutation_allowed: bool,
    playbook_text: str | None = None,
    staleness: list[str] | None = None,
    extra: dict[str, str] | None = None,
) -> ContextPack:
    pack = ContextPack(budget=budget, query=task_text)

    def add(section: str, text: str, *, ids: list[str] | None = None, mandatory: bool = False,
            note: str = "") -> Item:
        item = Item(section, text, est_tokens(text), ids or [], mandatory, note)
        pack.items.append(item)
        return item

    objective = ledger.objective(project)
    if objective:
        add("North Star", north_star_text(objective.body), ids=[objective.id], mandatory=True)
    else:
        add("North Star", "- NOT SET (run `agentterm objective set`). Stay within the task below.", mandatory=True)

    pins = ledger.pins(project)
    cap = int(budget * PIN_CAP)
    used = 0
    kept: list[L.Event] = []
    for ev in reversed(pins):  # newest first when trimming
        t = est_tokens(ev.text) + 2
        if used + t > cap and kept:
            pack.dropped.append({"event_id": ev.id, "reason": "pinned-facts cap", "preview": _one_line(ev.text, 80)})
            continue
        kept.append(ev)
        used += t
    for ev in reversed(kept):
        add("Pinned facts", f"- {_one_line(ev.text, 600)}", ids=[ev.id], mandatory=True)

    scope = [
        f"- Mutation allowed: {'YES' if mutation_allowed else 'NO (read-only)'}",
        f"- Allowed paths: {', '.join(allowed) if allowed else 'none'}",
        f"- Forbidden paths: {', '.join(forbidden) if forbidden else 'none'}",
        f"- Stop condition: ONE_VERIFIED_CHECKPOINT. Do not start another task.",
    ]
    add("Scope", "\n".join(scope), mandatory=True)
    add("Task", task_text.strip(), mandatory=True)
    if playbook_text:
        add("Procedure", playbook_text, mandatory=True)
    for name, text in (extra or {}).items():
        add(name, text, mandatory=True)

    cp_event = ledger.latest(project, L.CHECKPOINT)
    if cp_event:
        text = checkpoint_text(cp_event.body)
        limit_chars = int(budget * CHECKPOINT_CAP) * 4
        note = ""
        if len(text) > limit_chars:
            text = text[:limit_chars].rstrip() + "\n  - [checkpoint truncated to fit budget; full text is in the ledger]"
            note = "truncated"
        add("Last checkpoint", text, ids=[cp_event.id], note=note)
    if staleness:
        add("Staleness and contradictions", "\n".join(f"- {s}" for s in staleness), mandatory=True)

    # Retrieved history fills whatever budget remains.
    exclude = {i for item in pack.items for i in item.event_ids}
    query = task_text + " " + (objective.body.get("objective", "") if objective else "")
    candidates = [e for e in ledger.search(project, query, limit=60, kinds=HISTORY_KINDS) if e.id not in exclude]
    if candidates:
        lo = min(e.seq for e in candidates)
        hi = max(e.seq for e in candidates)
        span = (hi - lo) or 1

        def rank(e: L.Event) -> float:
            recency = (e.seq - lo) / span
            return (-e.score) * _KIND_WEIGHT.get(e.kind, 1.0) * (1 + 0.5 * recency)

        candidates.sort(key=rank, reverse=True)
        for ev in candidates:
            remaining = budget - pack.used
            if remaining < 50:
                pack.dropped.append({"event_id": ev.id, "reason": "budget exhausted", "preview": _one_line(ev.text, 80)})
                continue
            line = f"- [{ev.kind} {ev.ts[:10]} {ev.agent or '-'} #{ev.short_id}] {_one_line(ev.text, HISTORY_ITEM_CHARS)}"
            if est_tokens(line) > remaining:
                line = line[: remaining * 4 - 3] + "..."
            add("Relevant history (retrieved)", line, ids=[ev.id])
    return pack


def explain(summary: dict[str, Any]) -> str:
    lines = [f"Budget {summary['used']}/{summary['budget']} tokens"
             + (" (OVER BUDGET: mandatory items exceed it)" if summary.get("over_budget") else "")]
    for item in summary["items"]:
        ids = ",".join(i[:8] for i in item["event_ids"]) or "-"
        flag = "*" if item["mandatory"] else " "
        lines.append(f" {flag} {item['tokens']:>5}t  {item['section']:<30} src={ids:<20} {item['preview'][:70]}")
    if summary["dropped"]:
        lines.append(f"Dropped ({len(summary['dropped'])}):")
        for d in summary["dropped"][:15]:
            lines.append(f"   - {d['event_id'][:8]} {d['reason']}: {d['preview']}")
    lines.append("(* = mandatory: always injected)")
    return "\n".join(lines)
