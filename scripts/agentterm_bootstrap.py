#!/usr/bin/env python3
"""First-class Bootstrap lifecycle integration for AgentTerm.

Bootstrap owns authority resolution and the outer lifecycle. AgentTerm owns the
repository-scoped event ledger, context reconstruction, governed agent run, Git
scope observation, verification records, and generated continuity projection.
This module is deliberately a thin boundary: it never edits global Codex
configuration and it fails closed when authority, identity, or AgentTerm is
unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


SCHEMA = "bootstrap_agentterm_session.v1"
OUTCOMES = {"PASS", "BLOCKED_PRECONDITION", "FAILED_AFTER_EXECUTION", "DIVERGENCE"}


class LifecycleBlocked(RuntimeError):
    """A lifecycle precondition is not satisfied; no task execution occurred."""


@dataclass(frozen=True)
class SessionState:
    schema_version: str
    session_id: str
    project_root: str
    project_identity: str
    authority_revision: str
    authority_files: dict[str, str]
    status: str
    task_id: str | None = None
    planned_agent: str | None = None
    planned_packet: dict[str, Any] | None = None
    last_run_session: str | None = None
    last_outcome: str | None = None
    last_receipt: str | None = None

    @classmethod
    def load(cls, path: Path) -> "SessionState":
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            if body.get("schema_version") != SCHEMA:
                raise LifecycleBlocked("unsupported AgentTerm Bootstrap session schema")
            body.setdefault("planned_agent", None)
            body.setdefault("planned_packet", None)
            body.setdefault("last_run_session", None)
            body.setdefault("last_outcome", None)
            body.setdefault("last_receipt", None)
            return cls(**body)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise LifecycleBlocked(f"invalid AgentTerm Bootstrap session: {exc}") from exc


def _git(args: Sequence[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _project_identity(root: Path) -> tuple[Path, str, str | None]:
    try:
        actual = Path(_git(["rev-parse", "--show-toplevel"], root)).resolve()
        _git(["rev-parse", "--is-inside-work-tree"], actual)
        try:
            identity = _normalize_remote(_git(["remote", "get-url", "origin"], actual))
            if identity.endswith(".git"):
                identity = identity[:-4]
        except subprocess.CalledProcessError:
            identity = "local:" + hashlib.sha1(str(actual).encode()).hexdigest()[:12]
        head = _git(["rev-parse", "HEAD"], actual)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LifecycleBlocked(f"project is not a usable Git repository: {exc}") from exc
    return actual, identity or f"local:{_git(['rev-parse', 'HEAD'], actual)[:12]}", head


def _normalize_remote(value: str) -> str:
    value = value.strip()
    scp = re.match(r"^[\w.\-]+@([\w.\-]+):(.+)$", value)
    if scp:
        value = f"https://{scp.group(1)}/{scp.group(2)}"
    else:
        url = re.match(r"^\w+://(?:[^@/]+@)?([^/]+)/(.+)$", value)
        if url:
            value = f"https://{url.group(1)}/{url.group(2)}"
    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value.lower()


def _load_agentterm(source_root: Path | None = None) -> dict[str, Any]:
    """Load AgentTerm only from a verified local source or an installed package."""
    candidates: list[Path] = []
    if source_root:
        candidates.append(source_root / "src")
    env_source = os.environ.get("CODEX_BOOTSTRAP_AGENTTERM_SOURCE")
    if env_source:
        candidates.append(Path(env_source).expanduser().resolve() / "src")
    for candidate in candidates:
        if (candidate / "agentterm").is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
    try:
        return {
            "config": importlib.import_module("agentterm.config"),
            "gitinfo": importlib.import_module("agentterm.gitinfo"),
            "ledger": importlib.import_module("agentterm.ledger"),
            "runner": importlib.import_module("agentterm.runner"),
            "brief": importlib.import_module("agentterm.brief"),
            "contracts": importlib.import_module("agentterm.contracts"),
        }
    except ImportError as exc:
        raise LifecycleBlocked("AgentTerm package is unavailable; install the pinned local source") from exc


def _probe_executable(command: str | None) -> str:
    executable = command or shutil.which("agentterm")
    if not executable:
        raise LifecycleBlocked("AgentTerm executable is unavailable")
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5, check=False)
        help_result = subprocess.run([executable, "--help"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LifecycleBlocked(f"AgentTerm executable health check failed: {exc}") from exc
    if version.returncode != 0 or not version.stdout.strip() or help_result.returncode != 0:
        raise LifecycleBlocked("AgentTerm executable did not pass version/help health checks")
    return version.stdout.strip().splitlines()[0]


def _authority(authority: dict[str, Any]) -> tuple[str, dict[str, str]]:
    revision = authority.get("revision")
    files = authority.get("files")
    if not isinstance(revision, str) or len(revision) != 40:
        raise LifecycleBlocked("verified Bootstrap authority revision is required")
    if not isinstance(files, dict) or not files or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
        raise LifecycleBlocked("verified Bootstrap authority file hashes are required")
    return revision, dict(files)


def _state_path(root: Path) -> Path:
    return root / ".agentterm" / "bootstrap-session.json"


class AgentTermBootstrap:
    """Lifecycle facade used by canonical Bootstrap entry points and tests."""

    def __init__(self, bootstrap_root: Path, *, agentterm_command: str | None = None):
        self.bootstrap_root = bootstrap_root.resolve()
        self.agentterm_command = agentterm_command
        self.modules: dict[str, Any] | None = None

    def initialize(self, project_root: Path, authority: dict[str, Any]) -> SessionState:
        root, identity, head = _project_identity(project_root.resolve())
        revision, files = _authority(authority)
        version = _probe_executable(self.agentterm_command)
        self.modules = _load_agentterm(self.bootstrap_root / "vendor" / "agentterm")
        settings = self.modules["config"].load_settings(root)
        settings.ensure_home()
        existing_path = _state_path(root)
        if existing_path.exists():
            existing = SessionState.load(existing_path)
            if existing.project_root != str(root) or existing.project_identity != identity:
                raise LifecycleBlocked("existing AgentTerm session belongs to a different project")
            if existing.authority_revision != revision or existing.authority_files != files:
                raise LifecycleBlocked("existing AgentTerm session was initialized under different Bootstrap authority")
            return existing
        ledger = self.modules["ledger"].Ledger(settings.ledger_path)
        session_id = f"bootstrap-session-{uuid.uuid4().hex[:12]}"
        ledger.append(identity, "session_start", {
            "bootstrap_session": True,
            "agentterm_version": version,
            "authority_revision": revision,
            "starting_head": head,
        }, session=session_id, agent="bootstrap", text="Bootstrap AgentTerm session initialized")
        ledger.close()
        state = SessionState(SCHEMA, session_id, str(root), identity, revision, files, "READY")
        existing_path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return state

    def _open(self, project_root: Path) -> tuple[SessionState, Any, Any, Any]:
        root, identity, _ = _project_identity(project_root.resolve())
        state = SessionState.load(_state_path(root))
        if state.project_root != str(root) or state.project_identity != identity:
            raise LifecycleBlocked("AgentTerm session belongs to a different project")
        self.modules = self.modules or _load_agentterm(self.bootstrap_root / "vendor" / "agentterm")
        settings = self.modules["config"].load_settings(root)
        ledger = self.modules["ledger"].Ledger(settings.ledger_path)
        return state, settings, ledger, self.modules

    def discover(self, project_root: Path, tool_root: Path | None = None) -> dict[str, Any]:
        discovery = importlib.import_module("tool_discovery")
        return discovery.discover(tool_root)

    def host_operation(self, project_root: Path, *, operation: str, approved: bool,
                       authorization: str = "OWNER_APPROVED") -> dict[str, Any]:
        """Use only the existing allowlisted Bootstrap bridge; never a free-form shell."""
        state, _, ledger, _ = self._open(project_root)
        try:
            scripts_dir = str(self.bootstrap_root / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            bridge = importlib.import_module("host_exec_bridge")
            audit = Path(state.project_root) / ".agentterm" / "host-audit.jsonl"
            return bridge.execute({"operation": operation, "target": state.project_root,
                                   "authorization": authorization}, audit_path=audit,
                                  approved=approved, env=dict(os.environ))
        finally:
            ledger.close()

    def terminal_open(self, project_root: Path, *, mode: str = "managed", approved: bool = False,
                      command: str = "") -> dict[str, Any]:
        """Open one explicitly selected managed PTY or native Terminal.app tab."""
        state, _, ledger, _ = self._open(project_root)
        try:
            scripts_dir = str(self.bootstrap_root / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            bridge = importlib.import_module("open_terminal_bridge")
            try:
                result = bridge.open_session(Path(state.project_root), mode=mode, approved=approved, command=command)
            except Exception as exc:
                ledger.append(state.project_identity, "terminal_session", {
                    "action": "open", "mode": mode, "approved": approved,
                    "outcome": "BLOCKED_PRECONDITION", "reason": str(exc),
                }, session=state.session_id, agent="bootstrap", text="terminal session open blocked")
                raise
            ledger.append(state.project_identity, "terminal_session", {
                "action": "open", "session_id": result["session_id"], "mode": mode,
                "approved": approved, "output_capture": result.get("output_capture", False),
            }, session=state.session_id, agent="bootstrap", text=f"terminal session opened: {result['session_id']}")
            return result
        finally:
            ledger.close()

    def terminal_submit(self, project_root: Path, *, session_id: str, text: str,
                        approved: bool = False, timeout: float = 10) -> dict[str, Any]:
        """Submit reviewed input only to the selected managed session."""
        state, _, ledger, _ = self._open(project_root)
        try:
            scripts_dir = str(self.bootstrap_root / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            bridge = importlib.import_module("open_terminal_bridge")
            try:
                result = bridge.submit(Path(state.project_root), session_id, text, approved=approved, timeout=timeout)
            except Exception as exc:
                ledger.append(state.project_identity, "terminal_command", {
                    "action": "submit", "session_id": session_id, "approved": approved,
                    "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "outcome": "BLOCKED_PRECONDITION", "reason": str(exc),
                }, session=state.session_id, agent="bootstrap", text=f"terminal command blocked: {session_id}")
                raise
            ledger.append(state.project_identity, "terminal_command", {
                "action": "submit", "session_id": session_id, "approved": approved,
                "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "outcome": result.get("outcome"), "returncode": result.get("returncode"),
            }, session=state.session_id, agent="bootstrap", text=f"terminal command {result.get('outcome')}: {session_id}")
            return result
        finally:
            ledger.close()

    def terminal_close(self, project_root: Path, *, session_id: str, approved: bool = False) -> dict[str, Any]:
        """Close only the selected session and record the lifecycle event."""
        state, _, ledger, _ = self._open(project_root)
        try:
            scripts_dir = str(self.bootstrap_root / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            bridge = importlib.import_module("open_terminal_bridge")
            try:
                result = bridge.close_session(Path(state.project_root), session_id, approved=approved)
            except Exception as exc:
                ledger.append(state.project_identity, "terminal_session", {
                    "action": "close", "session_id": session_id, "approved": approved,
                    "outcome": "BLOCKED_PRECONDITION", "reason": str(exc),
                }, session=state.session_id, agent="bootstrap", text=f"terminal session close blocked: {session_id}")
                raise
            ledger.append(state.project_identity, "terminal_session", {
                "action": "close", "session_id": session_id, "approved": approved,
                "outcome": result.get("outcome"),
            }, session=state.session_id, agent="bootstrap", text=f"terminal session closed: {session_id}")
            return result
        finally:
            ledger.close()

    def plan(self, project_root: Path, *, objective: str, agent: str, mutate: bool,
             allowed: list[str], forbidden: list[str], verify: list[str], playbook: str | None = None) -> dict[str, Any]:
        state, settings, ledger, modules = self._open(project_root)
        try:
            snap = modules["gitinfo"].snapshot(settings.root)
            adapter = settings.adapter(agent)
            if adapter is None:
                raise LifecycleBlocked(f"unknown agent {agent!r}")
            health = adapter.doctor()
            if not health.get("available"):
                raise LifecycleBlocked(f"agent {agent!r} is not installed")
            if health.get("missing_flags"):
                raise LifecycleBlocked(f"agent {agent!r} is incompatible; missing flags: {', '.join(health['missing_flags'])}")
            if mutate and (not snap.head or not allowed):
                raise LifecycleBlocked("mutating plans require a committed HEAD and explicit allowed paths")
            packet = modules["contracts"].make_task_packet(
                objective=objective, repository_locator=snap.root, expected_identity=snap.identity,
                expected_head=snap.head, allowed=allowed if mutate else [], forbidden=forbidden,
                mutation_allowed=mutate, verification=[{"id": x, "description": f"run {x}"} for x in verify],
                origin_label="codex-project-bootstrap", playbook=None,
            )
            if playbook:
                packet["requested_playbook"] = playbook
            errors = modules["contracts"].validate("task", packet)
            if errors:
                raise LifecycleBlocked("invalid task plan: " + "; ".join(errors))
            ledger.append(state.project_identity, "bootstrap_plan", {"packet": packet, "agent": agent}, session=state.session_id, agent="bootstrap", text=objective)
            updated = SessionState(**{**asdict(state), "status": "PLANNED", "task_id": packet["task_id"],
                                      "planned_agent": agent, "planned_packet": packet})
            _state_path(Path(state.project_root)).write_text(json.dumps(asdict(updated), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return packet
        finally:
            ledger.close()

    def execute(self, project_root: Path, *, objective: str, agent: str, mutate: bool,
                allowed: list[str], forbidden: list[str], verify: list[str],
                confirm: Callable[[str], bool] | None = None, playbook: str | None = None) -> Any:
        state, settings, ledger, modules = self._open(project_root)
        try:
            planned = state.planned_packet
            if planned is None or state.planned_agent != agent:
                raise LifecycleBlocked("a matching Bootstrap task plan is required before execution")
            planned_scope = planned["scope"]
            requested_scope = {"allowed_paths": allowed if mutate else [], "forbidden_paths": forbidden}
            if (planned["objective"] != objective or planned["mutation_allowed"] != mutate or
                    planned_scope != requested_scope or
                    [item["id"] for item in planned["required_verification"]] != verify or
                    planned.get("requested_playbook") != playbook):
                raise LifecycleBlocked("execution request does not match the persisted task plan")
            current = modules["gitinfo"].snapshot(settings.root)
            if planned["target"].get("expected_head") != current.head:
                raise LifecycleBlocked("repository HEAD changed after planning; re-plan is required")
            request = modules["runner"].RunRequest(
                task=objective, agent=agent, mutate=mutate, allowed=allowed, forbidden=forbidden,
                verify=verify, yes=False, playbook=playbook,
                task_id=planned["task_id"], correlation_id=planned["correlation_id"],
            )
            report = modules["runner"].run_task(settings, ledger, request, confirm=confirm, out=lambda _: None)
            outcome = report.outcome
            if outcome not in OUTCOMES:
                raise LifecycleBlocked(f"AgentTerm returned unknown outcome {outcome!r}")
            updated = SessionState(**{**asdict(state), "status": outcome, "task_id": (report.task_packet or {}).get("task_id"),
                                      "last_run_session": report.session_id,
                                      "last_outcome": outcome,
                                      "last_receipt": (report.result_packet or {}).get("receipt_id")})
            _state_path(Path(state.project_root)).write_text(json.dumps(asdict(updated), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return report
        finally:
            ledger.close()

    def resume(self, project_root: Path) -> dict[str, Any]:
        state, settings, ledger, modules = self._open(project_root)
        try:
            integrity = ledger.verify(state.project_identity)
            if not integrity.ok:
                raise LifecycleBlocked("AgentTerm ledger verification failed: " + "; ".join(integrity.problems[:3]))
            snap = modules["gitinfo"].snapshot(settings.root)
            checkpoint = ledger.latest(state.project_identity, modules["ledger"].CHECKPOINT)
            findings = modules["brief"].validate_checkpoint(checkpoint.body, snap) if checkpoint else []
            if any(f.severity == "reject" for f in findings):
                raise LifecycleBlocked("continuity checkpoint rejected: " + "; ".join(f.message for f in findings))
            return {"state": asdict(state), "ledger_verified": True, "events": ledger.count(state.project_identity),
                    "checkpoint": checkpoint.body if checkpoint else None,
                    "findings": [asdict(f) for f in findings]}
        finally:
            ledger.close()

    def status(self, project_root: Path) -> dict[str, Any]:
        state, settings, ledger, modules = self._open(project_root)
        try:
            integrity = ledger.verify(state.project_identity)
            approvals = ledger.events(state.project_identity, kinds=[modules["ledger"].APPROVAL], limit=10, desc=True)
            outcomes = ledger.events(state.project_identity, kinds=[modules["ledger"].OUTCOME], limit=5, desc=True)
            return {"state": asdict(state), "ledger_verified": integrity.ok, "events": ledger.count(state.project_identity),
                    "approvals": [e.body.get("packet", {}) for e in approvals],
                    "outcomes": [e.body.get("outcome") for e in outcomes],
                    "ledger_problems": integrity.problems}
        finally:
            ledger.close()

    def handoff(self, project_root: Path) -> Path:
        state, settings, ledger, modules = self._open(project_root)
        try:
            snap = modules["gitinfo"].snapshot(settings.root)
            cp = modules["brief"].build_checkpoint(ledger, state.project_identity, snap)
            ledger.append(state.project_identity, modules["ledger"].CHECKPOINT, cp, session=state.session_id, agent="bootstrap",
                          text=f"checkpoint {cp['status']}; next: {cp['next_action']}")
            path, _ = modules["brief"].write_brief(settings.root, cp)
            return path
        finally:
            ledger.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--agentterm", help="exact AgentTerm executable; defaults to PATH")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--authority-json", type=Path, required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("objective")
    plan.add_argument("--agent", default="codex")
    plan.add_argument("--mutate", action="store_true")
    plan.add_argument("--allow", action="append", default=[])
    plan.add_argument("--forbid", action="append", default=[])
    plan.add_argument("--verify", action="append", default=[])
    plan.add_argument("--playbook")
    execute = sub.add_parser("execute")
    execute.add_argument("objective")
    execute.add_argument("--agent", default="codex")
    execute.add_argument("--mutate", action="store_true")
    execute.add_argument("--allow", action="append", default=[])
    execute.add_argument("--forbid", action="append", default=[])
    execute.add_argument("--verify", action="append", default=[])
    execute.add_argument("--playbook")
    sub.add_parser("resume")
    sub.add_parser("status")
    sub.add_parser("verify")
    sub.add_parser("handoff")
    terminal_open = sub.add_parser("terminal-open")
    terminal_open.add_argument("--mode", choices=("managed", "native"), default="managed")
    terminal_open.add_argument("--startup-command", dest="startup_command", default="")
    terminal_open.add_argument("--approve", action="store_true")
    terminal_submit = sub.add_parser("terminal-submit")
    terminal_submit.add_argument("session_id")
    terminal_submit.add_argument("--text", required=True)
    terminal_submit.add_argument("--timeout", type=float, default=10)
    terminal_submit.add_argument("--approve", action="store_true")
    terminal_close = sub.add_parser("terminal-close")
    terminal_close.add_argument("session_id")
    terminal_close.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    bridge = AgentTermBootstrap(args.bootstrap_root, agentterm_command=args.agentterm)
    try:
        if args.command == "init":
            result: Any = bridge.initialize(args.project_root, json.loads(args.authority_json.read_text(encoding="utf-8")))
        elif args.command == "plan":
            result = bridge.plan(args.project_root, objective=args.objective, agent=args.agent, mutate=args.mutate,
                                 allowed=args.allow, forbidden=args.forbid, verify=args.verify, playbook=args.playbook)
        elif args.command == "execute":
            result = bridge.execute(args.project_root, objective=args.objective, agent=args.agent, mutate=args.mutate,
                                    allowed=args.allow, forbidden=args.forbid, verify=args.verify, playbook=args.playbook,
                                    confirm=lambda summary: input(summary + "\nApprove? [y/N] ").strip().lower() in {"y", "yes"})
            result = {"outcome": result.outcome, "session_id": result.session_id, "reasons": result.reasons,
                      "changed_paths": result.changed_paths, "checks": result.checks}
        elif args.command == "resume":
            result = bridge.resume(args.project_root)
        elif args.command == "status":
            result = bridge.status(args.project_root)
        elif args.command == "verify":
            resumed = bridge.resume(args.project_root)
            result = {"ledger_verified": resumed["ledger_verified"], "events": resumed["events"],
                      "findings": resumed["findings"]}
        elif args.command == "terminal-open":
            result = bridge.terminal_open(args.project_root, mode=args.mode, approved=args.approve, command=args.startup_command)
        elif args.command == "terminal-submit":
            result = bridge.terminal_submit(args.project_root, session_id=args.session_id, text=args.text,
                                            approved=args.approve, timeout=args.timeout)
        elif args.command == "terminal-close":
            result = bridge.terminal_close(args.project_root, session_id=args.session_id, approved=args.approve)
        else:
            result = {"handoff": str(bridge.handoff(args.project_root))}
        print(json.dumps(result if isinstance(result, dict) else asdict(result), indent=2, sort_keys=True, default=str))
        return 0
    except (LifecycleBlocked, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"outcome": "BLOCKED_PRECONDITION", "reason": str(exc), "stop": True}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
