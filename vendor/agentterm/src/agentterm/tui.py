"""Terminal dashboard: context budget, recent events, pins/parked, status.

``build_view`` and ``render_text`` are pure so they can be tested; ``run`` wraps them in curses.
"""

from __future__ import annotations

import sys
import textwrap
from typing import Any

from . import ledger as L
from . import gitinfo


def build_view(ledger: L.Ledger, project: str, snap: gitinfo.Snapshot, *, budget: int) -> dict[str, list[str]]:
    status = [
        f"repo    {snap.identity}",
        f"branch  {snap.branch or '-'}   head {(snap.head or '-')[:12]}   worktree {snap.worktree_state}",
        f"ledger  {ledger.count(project)} events   {'verified' if ledger.verify(project).ok else 'FAILED VERIFICATION'}",
    ]
    objective = ledger.objective(project)
    status.append("goal    " + (objective.body.get("objective", "")[:120] if objective else "NOT SET"))
    last = ledger.latest(project, L.OUTCOME)
    status.append("last    " + (f"{last.body.get('outcome')} - {last.body.get('task', '')[:80]}" if last else "no sessions yet"))
    cp = ledger.latest(project, L.CHECKPOINT)
    status.append("next    " + (str(cp.body.get("next_action"))[:120] if cp else "-"))

    pack = ledger.latest(project, L.CONTEXT_PACK)
    budget_lines = ["no session yet"]
    if pack:
        used, total = pack.body.get("used", 0), pack.body.get("budget", budget)
        filled = int(30 * min(used, total) / max(total, 1))
        budget_lines = [f"[{'#' * filled}{'.' * (30 - filled)}] {used}/{total} tokens"]
        per: dict[str, int] = {}
        for item in pack.body.get("items", []):
            per[item["section"]] = per.get(item["section"], 0) + item["tokens"]
        budget_lines += [f"{v:>6}  {k}" for k, v in sorted(per.items(), key=lambda kv: -kv[1])]
        if pack.body.get("dropped"):
            budget_lines.append(f"{len(pack.body['dropped'])} item(s) dropped (see `agentterm why`)")

    recent = [f"{e.ts[11:19]} {e.kind:<14} {e.text.splitlines()[0][:60] if e.text else ''}"
              for e in ledger.events(project, limit=12, desc=True)]
    mem = [f"PIN    {e.text[:70]}" for e in ledger.pins(project)] + [f"PARKED {e.text[:70]}" for e in ledger.parked(project)]
    return {"Status": status, "Context budget (last session)": budget_lines, "Recent events": recent,
            "Pinned facts and parked ideas": mem or ["none"]}


def render_text(view: dict[str, list[str]], width: int = 100) -> str:
    out: list[str] = []
    for title, lines in view.items():
        out.append(f"== {title} " + "=" * max(0, width - len(title) - 4))
        for line in lines:
            out.extend(textwrap.wrap(line, width - 2, subsequent_indent="  ") or [""])
    return "\n".join(out)


def run(ledger: L.Ledger, project: str, snap_fn: Any, *, budget: int) -> int:  # pragma: no cover - interactive
    if not sys.stdout.isatty():
        print(render_text(build_view(ledger, project, snap_fn(), budget=budget)))
        return 0
    import curses

    def loop(stdscr: Any) -> None:
        curses.curs_set(0)
        stdscr.timeout(2000)
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            text = render_text(build_view(ledger, project, snap_fn(), budget=budget), w - 1)
            for i, line in enumerate(text.splitlines()[: h - 2]):
                stdscr.addnstr(i, 0, line, w - 1)
            stdscr.addnstr(h - 1, 0, "q quit  r refresh (auto every 2s)", w - 1)
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), 27):
                return

    curses.wrapper(loop)
    return 0
