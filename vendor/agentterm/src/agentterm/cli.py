"""agentterm command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from . import __version__, brief, bundle, context, contracts, gitinfo, installer, playbooks, report, runner, tui, platform
from . import ledger as L
from .config import ConfigError, Settings, load_settings


class Fail(Exception):
    """A user-facing error: printed without a traceback, exit code 1."""


def _open(args: argparse.Namespace) -> tuple[Settings, L.Ledger, gitinfo.Snapshot]:
    settings = load_settings(Path.cwd(), getattr(args, "manifest", None))
    settings.ensure_home()
    return settings, L.Ledger(settings.ledger_path), gitinfo.snapshot(settings.root)


def _confirm(summary: str) -> bool:
    print(summary)
    if not sys.stdin.isatty():
        print("Not a terminal: pass --yes to approve non-interactively.")
        return False
    return input("Approve and run? [y/N] ").strip().lower() in ("y", "yes")


# ------------------------------------------------------------------- commands
def cmd_init(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    if args.write_manifest:
        target = settings.root / "agentterm.toml"
        if target.exists():
            print("agentterm.toml already exists; left untouched.")
        else:
            target.write_text(resources.files("agentterm").joinpath("data/default_manifest.toml").read_text(encoding="utf-8"), encoding="utf-8")
            print("wrote agentterm.toml")
            settings = load_settings(settings.root)
    manifest = settings.manifest
    if not manifest.get("tool"):
        manifest = {"tool": _default_tools()}
        print("No manifest found; using built-in defaults (run `agentterm init --write-manifest` to create agentterm.toml).\n")
    print(f"Repository: {snap.identity}   branch {snap.branch or '-'}   head {(snap.head or '-')[:12]}   worktree {snap.worktree_state}")
    print(f"Memory:     {settings.ledger_path}  ({ledger.count(snap.identity)} events; git-ignored by default)\n")
    statuses = installer.discover(manifest, settings.root)
    print(installer.render_plan(statuses))
    agents_present = [s for s in statuses if s.kind == "agent" and s.classification == installer.ALREADY_HAVE]
    print()
    if not agents_present:
        print("No agent CLI found. Install one with: agentterm install --apply --only codex")
    gaps = [s for s in statuses if s.classification == installer.REAL_GAP]
    if gaps:
        print("Required gaps: " + ", ".join(s.id for s in gaps) + "  ->  agentterm install --apply")
    print("Next: agentterm objective set \"...\"   then   agentterm run --agent <name> \"task\"")
    return 0


def _default_tools() -> list[dict[str, Any]]:
    import tomllib

    text = resources.files("agentterm").joinpath("data/default_manifest.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)["tool"]


def cmd_install(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    manifest = settings.manifest if settings.manifest.get("tool") else {"tool": _default_tools()}
    statuses = installer.discover(manifest, settings.root)
    print(installer.render_plan(statuses))
    chosen = [s for s in statuses if (s.id in args.only if args.only else
                                      s.classification == installer.REAL_GAP or (args.with_optional and s.classification == installer.OPTIONAL))
              and s.classification != installer.ALREADY_HAVE]
    if not chosen:
        print("\nNothing to install.")
        return 0
    print("\nPlanned actions:")
    for s in chosen:
        print(f"  {s.id}: {s.action}")
    if not args.apply:
        print("\nDry run. Re-run with --apply to execute these commands.")
        return 0
    if not args.yes:
        if not sys.stdin.isatty() or input("\nRun these commands? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Not approved; nothing was installed.")
            return contracts.EXIT_CODES["BLOCKED_PRECONDITION"]
    results = installer.apply(statuses, settings.root, include_optional=args.with_optional, only=args.only or None)
    for r in results:
        ledger.append(snap.identity, L.INSTALL, {"tool": r.id, "ok": r.ok, "detail": r.detail}, text=f"install {r.id}: {'ok' if r.ok else 'FAILED'} {r.detail}")
        print(f"{'ok  ' if r.ok else 'FAIL'} {r.id}: {r.detail}")
    return 0 if results and all(r.ok for r in results) else contracts.EXIT_CODES["FAILED_AFTER_EXECUTION"]


def cmd_objective(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    if args.action == "show":
        ev = ledger.objective(snap.identity)
        print(context.north_star_text(ev.body) if ev else "No objective set.")
        return 0
    if not args.text:
        raise Fail("objective set needs the objective text")
    body = {"objective": args.text, "proof": args.proof, "out_of_scope": args.out_of_scope, "stop": args.stop}
    ledger.append(snap.identity, L.OBJECTIVE, body, text=args.text)
    print("North Star recorded.\n" + context.north_star_text(body))
    return 0


def _simple_record(kind: str, label: str):
    def handler(args: argparse.Namespace) -> int:
        _, ledger, snap = _open(args)
        text = " ".join(args.text)
        ev = ledger.append(snap.identity, kind, {"text": text, "source": "human"}, text=text)
        print(f"{label} recorded ({ev.short_id}).")
        return 0
    return handler


def cmd_pin(args: argparse.Namespace) -> int:
    return _simple_record(L.PIN, "Pinned fact")(args)


def cmd_unpin(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    pins = [e for e in ledger.pins(snap.identity) if e.id.startswith(args.id)]
    if len(pins) != 1:
        raise Fail(f"{len(pins)} pins match {args.id!r}")
    ledger.append(snap.identity, L.UNPIN, {"pin_id": pins[0].id}, text=f"unpinned: {pins[0].text}")
    print("Unpinned (the original pin stays in the ledger).")
    return 0


def cmd_pins(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    for e in ledger.pins(snap.identity):
        print(f"{e.short_id}  {e.text}")
    return 0


def cmd_park(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    text = " ".join(args.text)
    body = {"text": text, "why": args.why, "urgency": args.urgency, "blocks_objective": False, "source": "human"}
    ev = ledger.append(snap.identity, L.PARKED, body, text=text)
    print(f"PARKED IDEA recorded ({ev.short_id}). It stays out of context until you activate it.")
    return 0


def cmd_parked(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    for e in ledger.parked(snap.identity):
        print(f"{e.short_id}  [{e.body.get('urgency') or '-'}] {e.text}")
    return 0


def cmd_unpark(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    ideas = [e for e in ledger.parked(snap.identity) if e.id.startswith(args.id)]
    if len(ideas) != 1:
        raise Fail(f"{len(ideas)} parked ideas match {args.id!r}")
    ledger.append(snap.identity, L.UNPARK, {"parked_id": ideas[0].id}, text=f"unparked: {ideas[0].text}")
    print("Unparked. Start a task for it with `agentterm run`.")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    text = " ".join(args.text) or "Objective complete."
    ledger.append(snap.identity, L.COMPLETE, {"text": text}, text=text)
    cp = brief.build_checkpoint(ledger, snap.identity, snap)
    ledger.append(snap.identity, L.CHECKPOINT, cp, text=f"checkpoint {cp['status']}; next: {cp['next_action']}")
    print("Marked complete; status STOP_COMPLETE.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    if not args.task:
        raise Fail("give the task text, e.g. agentterm run --agent codex \"fix the failing importer test\"")
    req = runner.RunRequest(
        task=" ".join(args.task), agent=args.agent or settings.default_agent, allowed=args.allow, forbidden=args.forbid,
        mutate=args.mutate, verify=args.verify, yes=args.yes, budget=args.budget, dry_run=args.dry_run,
        playbook=args.playbook, timeout=args.timeout,
    )
    try:
        result = runner.run_task(settings, ledger, req, confirm=_confirm, out=print)
    except playbooks.PlaybookError as exc:
        raise Fail(str(exc))
    if result.dry_run:
        return result.exit_code
    print(f"\n{result.outcome}  (exit {result.exit_code})  session {result.session_id}")
    for reason in result.reasons:
        print(f"  - {reason}")
    if result.changed_paths:
        print("Changed paths (observed via Git): " + ", ".join(result.changed_paths))
    for check in result.checks:
        print(f"  verify {check['id']}: {check['result']}")
    if result.response and args.show_response:
        print("\n--- agent response ---\n" + result.response)
    print(f"Handoff brief: {result.brief_path}")
    return result.exit_code


def cmd_review(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    base = args.base
    if not base:
        last = ledger.latest(snap.identity, L.OUTCOME)
        base = (last.body.get("result_packet", {}).get("repository", {}).get("starting_head") if last else None) or "HEAD"
    budget = args.budget or settings.budget_tokens
    diff = gitinfo.diff_text(settings.root, base=base, max_chars=int(budget * 4 * 0.4))
    if not diff.strip():
        raise Fail(f"no changes to review since {base[:12]}")
    req = runner.RunRequest(
        task=f"Independent review of the changes since {base[:12]}. Report defects, risks, missing tests and scope concerns. Do not modify any files.",
        agent=args.agent or settings.default_agent, mutate=False, budget=budget, timeout=args.timeout,
        extra_context={"Diff under review": "```diff\n" + diff + "\n```"},
    )
    result = runner.run_task(settings, ledger, req, out=print)
    print(f"\n{result.outcome}  session {result.session_id}")
    print("\n--- review ---\n" + result.response)
    return result.exit_code


def cmd_open(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    return runner.open_interactive(settings, ledger, args.agent, budget=args.budget)


def cmd_why(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    packs = ledger.events(snap.identity, kinds=[L.CONTEXT_PACK], session=args.session, limit=1, desc=True)
    if not packs:
        raise Fail("no context pack recorded yet; run a task first (or use `run --dry-run`)")
    pack = packs[0]
    print(f"Session {pack.session}  agent {pack.agent}  at {pack.ts}\n")
    print(context.explain(pack.body))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    for e in ledger.search(snap.identity, " ".join(args.query), limit=args.n):
        print(f"{e.short_id} {e.ts[:19]} {e.kind:<16} {e.text.splitlines()[0][:100] if e.text else ''}")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    events = ledger.events(snap.identity, kinds=args.kind or None, limit=args.n, desc=True)
    for e in reversed(events):
        print(f"{e.short_id} {e.ts[:19]} {e.agent or '-':<8} {e.kind:<16} {e.text.splitlines()[0][:90] if e.text else ''}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    print(tui.render_text(tui.build_view(ledger, snap.identity, snap, budget=settings.budget_tokens)))
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    cp = brief.build_checkpoint(ledger, snap.identity, snap)
    ledger.append(snap.identity, L.CHECKPOINT, cp, text=f"checkpoint {cp['status']}; next: {cp['next_action']}")
    path, note = brief.write_brief(settings.root, cp, publish=args.publish, force=args.force)
    if args.print:
        print(brief.render_markdown(cp))
    print(f"{path}: {note}")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    return _simple_record(L.NEXT, "Next approved action")(args)


def cmd_verify(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    result = ledger.verify()
    print(f"{result.checked} events checked: {'OK' if result.ok else 'FAILED'}")
    for p in result.problems[:20]:
        print("  " + p)
    return 0 if result.ok else contracts.EXIT_CODES["DIVERGENCE"]


def cmd_doctor(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    print(f"agentterm {__version__}   python {sys.version.split()[0]}   sqlite {sqlite3.sqlite_version}")
    probe = None
    try:
        probe = sqlite3.connect(":memory:")
        probe.execute("create virtual table t using fts5(x)")
        print("ok    sqlite FTS5 available")
    except sqlite3.Error:
        print("FAIL  sqlite FTS5 missing (retrieval will not work)")
        return 1
    finally:
        if probe is not None:
            probe.close()
    print(f"{'ok  ' if snap.is_git else 'warn'}  git repository: {snap.identity}")
    print(f"ok    manifest: {settings.manifest_path or 'none (built-in defaults)'}")
    for name in settings.agent_names():
        info = settings.adapter(name).doctor()
        if not info["available"]:
            print(f"--    agent {name}: not installed")
            continue
        flag = "warn" if info["missing_flags"] else "ok  "
        extra = f"  MISSING FLAGS {info['missing_flags']} (adapter may need updating)" if info["missing_flags"] else ""
        ro = "" if info["enforces_read_only"] else "  (cannot enforce read-only; scope check is the safety net)"
        print(f"{flag}  agent {name}: {info['version']}{extra}{ro}")
    res = ledger.verify()
    print(f"{'ok  ' if res.ok else 'FAIL'}  ledger: {res.checked} events, chain {'verified' if res.ok else 'BROKEN'}")
    return 0 if res.ok else 1


def _key(args: argparse.Namespace) -> bytes | None:
    if not args.key_env:
        return None
    value = os.environ.get(args.key_env)
    if not value:
        raise Fail(f"environment variable {args.key_env} is not set")
    return value.encode()


def cmd_export(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    try:
        header = bundle.export_bundle(ledger, snap.identity, args.path, key=_key(args))
    except bundle.BundleError as exc:
        raise Fail(str(exc))
    print(f"exported {header['count']} events to {args.path}" + (" (signed)" if header["hmac"] else " (unsigned)"))
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    try:
        imported, skipped = bundle.import_bundle(ledger, args.path, project=snap.identity, key=_key(args))
    except (bundle.BundleError, ValueError) as exc:
        raise Fail(str(exc))
    print(f"imported {imported} events ({skipped} already present)")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    _, ledger, snap = _open(args)
    html = report.render_report(ledger, snap.identity, title=args.title)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    settings, ledger, snap = _open(args)
    return tui.run(ledger, snap.identity, lambda: gitinfo.snapshot(settings.root), budget=settings.budget_tokens)


def cmd_playbooks(args: argparse.Namespace) -> int:
    if args.id:
        try:
            print(playbooks.render(playbooks.load(args.id)))
        except playbooks.PlaybookError as exc:
            raise Fail(str(exc))
        return 0
    for p in playbooks.list_playbooks():
        print(f"{p['id']:<18} v{p['version']}  {p['purpose']}")
    return 0


def cmd_platform_demo(args: argparse.Namespace) -> int:
    """Run the local-only signed sync/team/entitlement integration workflow."""
    import tempfile
    root = Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix="agentterm-platform-"))
    try:
        result = platform.integrated_local_flow(root)
    except platform.CryptoUnavailable as exc:
        raise Fail(str(exc))
    print(json.dumps({k: v for k, v in result.items() if k != "ciphertext"}, sort_keys=True))
    print(f"local platform evidence: {root}")
    return 0


def cmd_platform_health(args: argparse.Namespace) -> int:
    path = Path(args.root) / "sync.db"
    if not path.exists(): raise Fail(f"sync database not found: {path}")
    server = platform.LocalSyncServer(path, registry=platform.TrustRegistry())
    try:
        health = server.health()
    finally:
        server.close()
    print(json.dumps(health, sort_keys=True))
    return 0 if health["ok"] else 1


def cmd_staging_acceptance(args: argparse.Namespace) -> int:
    import tempfile
    root = Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix="agentterm-staging-"))
    try: result = platform.integrated_staging_flow(root)
    except PermissionError as exc: raise Fail("staging loopback bind unavailable on this host; run the host qualification command") from exc
    print(json.dumps(result, sort_keys=True)); print(f"staging evidence: {root}"); return 0 if all(result.values()) else 1


# --------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentterm", description="Install, run and remember for AI coding agents. No compaction: the terminal owns the memory.")
    p.add_argument("--version", action="version", version=f"agentterm {__version__}")
    p.add_argument("--manifest", help="path to agentterm.toml (default: <repo>/agentterm.toml)")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name: str, fn, help: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help)
        sp.set_defaults(func=fn)
        return sp

    sp = add("init", cmd_init, "read-only discovery of tools and the project; shows what is missing")
    sp.add_argument("--write-manifest", action="store_true", help="create agentterm.toml from the defaults")
    sp = add("install", cmd_install, "install missing tools (dry-run unless --apply)")
    sp.add_argument("--apply", action="store_true")
    sp.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    sp.add_argument("--with-optional", action="store_true")
    sp.add_argument("--only", nargs="+", default=[], metavar="ID")

    sp = add("objective", cmd_objective, "set or show the North Star (objective, proof, out of scope, stop boundary)")
    sp.add_argument("action", choices=["set", "show"])
    sp.add_argument("text", nargs="?")
    sp.add_argument("--proof")
    sp.add_argument("--out-of-scope", dest="out_of_scope")
    sp.add_argument("--stop")
    sp = add("pin", cmd_pin, "pin a fact that is injected into every session")
    sp.add_argument("text", nargs="+")
    sp = add("unpin", cmd_unpin, "stop injecting a pinned fact (history is kept)")
    sp.add_argument("id")
    add("pins", cmd_pins, "list pinned facts")
    sp = add("park", cmd_park, "park an out-of-scope idea (PARKED IDEA)")
    sp.add_argument("text", nargs="+")
    sp.add_argument("--why")
    sp.add_argument("--urgency", choices=["LOW", "MEDIUM", "HIGH"], default="LOW")
    add("parked", cmd_parked, "list parked ideas")
    sp = add("unpark", cmd_unpark, "activate a parked idea")
    sp.add_argument("id")
    sp = add("decide", _simple_record(L.DECISION, "Decision"), "record a binding decision")
    sp.add_argument("text", nargs="+")
    sp = add("failed", _simple_record(L.FAILED, "Failed approach"), "record a failed approach so it is not repeated")
    sp.add_argument("text", nargs="+")
    sp = add("note", _simple_record(L.NOTE, "Note"), "record a note")
    sp.add_argument("text", nargs="+")
    sp = add("next", cmd_next, "set the single next approved action")
    sp.add_argument("text", nargs="+")
    sp = add("complete", cmd_complete, "mark the objective complete (status STOP_COMPLETE)")
    sp.add_argument("text", nargs="*")

    sp = add("run", cmd_run, "run one governed task in a fresh session")
    sp.add_argument("task", nargs="*")
    sp.add_argument("--agent", help="codex, claude, or an agent from agentterm.toml")
    sp.add_argument("--mutate", action="store_true", help="allow file changes (needs --allow and approval)")
    sp.add_argument("--allow", action="append", default=[], metavar="PATH", help="allowed path or glob (repeatable)")
    sp.add_argument("--forbid", action="append", default=[], metavar="PATH", help="forbidden path or glob (repeatable)")
    sp.add_argument("--verify", action="append", default=[], metavar="CMD", help="command that must pass afterwards (repeatable)")
    sp.add_argument("--yes", action="store_true", help="approve the mutation without prompting")
    sp.add_argument("--budget", type=int, help="context token budget for this session")
    sp.add_argument("--playbook", help="engineering playbook id (see `agentterm playbooks`)")
    sp.add_argument("--timeout", type=int, default=3600)
    sp.add_argument("--dry-run", action="store_true", help="show the context and prompt; run and record nothing")
    sp.add_argument("--show-response", action="store_true")
    sp = add("review", cmd_review, "have an agent independently review the latest changes (read-only)")
    sp.add_argument("--agent")
    sp.add_argument("--base", help="git revision to diff against (default: HEAD before the last session)")
    sp.add_argument("--budget", type=int)
    sp.add_argument("--timeout", type=int, default=3600)
    sp = add("open", cmd_open, "launch an agent interactively with a fresh brief; changes are recorded afterwards")
    sp.add_argument("agent")
    sp.add_argument("--budget", type=int)

    sp = add("why", cmd_why, "show exactly what context was injected into a session, and why")
    sp.add_argument("--session")
    sp = add("search", cmd_search, "full-text search the project's memory")
    sp.add_argument("query", nargs="+")
    sp.add_argument("-n", type=int, default=10)
    sp = add("log", cmd_log, "recent events")
    sp.add_argument("-n", type=int, default=25)
    sp.add_argument("--kind", action="append")
    add("status", cmd_status, "one-screen status")
    sp = add("checkpoint", cmd_checkpoint, "generate the handoff checkpoint")
    sp.add_argument("--publish", action="store_true", help="also write CONTINUE_TOMORROW.md (never overwrites a hand-written one)")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--print", action="store_true")
    add("verify", cmd_verify, "verify the ledger's hash chains")
    add("doctor", cmd_doctor, "check the environment, adapters and ledger")
    sp = add("export", cmd_export, "export this project's memory as a verifiable bundle")
    sp.add_argument("path")
    sp.add_argument("--key-env", help="name of an environment variable holding a shared signing key")
    sp = add("import", cmd_import, "import a teammate's bundle (verified before anything is written)")
    sp.add_argument("path")
    sp.add_argument("--key-env")
    sp = add("report", cmd_report, "write a self-contained HTML evidence report")
    sp.add_argument("--out", default="agentterm-report.html")
    sp.add_argument("--title")
    add("tui", cmd_tui, "terminal dashboard")
    sp = add("playbooks", cmd_playbooks, "list or show engineering playbooks")
    sp.add_argument("id", nargs="?")
    sp = add("platform-demo", cmd_platform_demo, "exercise local signed sync, team authorization, revocation and entitlements")
    sp.add_argument("--root", help="local evidence directory (default: temporary directory)")
    sp = add("platform-health", cmd_platform_health, "check a local sync database integrity and schema")
    sp.add_argument("root", help="platform evidence directory containing sync.db")
    sp = add("staging-acceptance", cmd_staging_acceptance, "run the isolated local HTTP staging acceptance")
    sp.add_argument("--root", help="staging evidence directory (default: temporary directory)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (Fail, ConfigError) as exc:
        print(f"agentterm: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:  # e.g. missing import file: clean message, not a traceback
        print(f"agentterm: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
