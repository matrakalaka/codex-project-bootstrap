import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agentterm_bootstrap import AgentTermBootstrap, LifecycleBlocked


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = {
    "revision": "a" * 40,
    "files": {"GLOBAL_PROJECT_BOOTSTRAP.md": "sha256:bootstrap", "PROJECT_NORTH_STAR.md": "sha256:north-star"},
}


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def make_project(root: Path) -> None:
    git(root, "init", "-q")
    (root / "src").mkdir()
    (root / "src" / "result.txt").write_text("before\n", encoding="utf-8")
    git(root, "add", ".")
    subprocess.run(["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Bootstrap Test", "commit", "-qm", "init"], cwd=root, check=True)


def make_agentterm_health(path: Path) -> Path:
    path.write_text("#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'agentterm 0.1.0'; else echo 'governed agentterm'; fi\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def make_fake_agent(project: Path) -> Path:
    script = project / "fake_agent.py"
    script.write_text(
        "import pathlib, sys\n"
        "pathlib.Path('src/result.txt').write_text('after\\n')\n"
        "print('## Session Report')\n"
        "print('COMPLETED: synthetic change')\n",
        encoding="utf-8",
    )
    (project / "agentterm.toml").write_text(
        "[agents.fake]\n"
        f"command = [{sys.executable!r}, {str(script)!r}]\n"
        "stdin = true\n",
        encoding="utf-8",
    )
    return script


class AgentTermBootstrapLifecycleTests(unittest.TestCase):
    def bridge(self, health: Path) -> AgentTermBootstrap:
        return AgentTermBootstrap(ROOT, agentterm_command=str(health))

    def test_complete_lifecycle_and_fresh_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            make_fake_agent(project)
            health = make_agentterm_health(project / "agentterm-health")
            bridge = self.bridge(health)

            state = bridge.initialize(project, AUTHORITY)
            self.assertEqual(state.status, "READY")
            plan = bridge.plan(project, objective="perform synthetic change", agent="fake", mutate=True,
                               allowed=["src/**"], forbidden=["secrets/**"], verify=["test -f src/result.txt"],
                               playbook="BUG_FIX")
            self.assertEqual(plan["approval_state"], "PENDING")
            report = bridge.execute(project, objective="perform synthetic change", agent="fake", mutate=True,
                                    allowed=["src/**"], forbidden=["secrets/**"],
                                    verify=["test -f src/result.txt"], confirm=lambda _: True,
                                    playbook="BUG_FIX")
            self.assertEqual(report.outcome, "PASS")
            self.assertEqual(report.changed_paths, ["src/result.txt"])
            resumed = AgentTermBootstrap(ROOT, agentterm_command=str(health)).resume(project)
            self.assertTrue(resumed["ledger_verified"])
            self.assertGreaterEqual(resumed["events"], 8)
            self.assertTrue((project / ".agentterm" / "briefs" / "latest.md").exists())

    def test_denied_approval_executes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            make_fake_agent(project)
            health = make_agentterm_health(project / "agentterm-health")
            bridge = self.bridge(health)
            bridge.initialize(project, AUTHORITY)
            bridge.plan(project, objective="must be denied", agent="fake", mutate=True,
                        allowed=["src/**"], forbidden=[], verify=[])
            report = bridge.execute(project, objective="must be denied", agent="fake", mutate=True,
                                    allowed=["src/**"], forbidden=[], verify=[], confirm=lambda _: False)
            self.assertEqual(report.outcome, "BLOCKED_PRECONDITION")
            self.assertEqual((project / "src" / "result.txt").read_text(), "before\n")

    def test_authority_and_executable_are_real_preconditions(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            with self.assertRaises(LifecycleBlocked):
                AgentTermBootstrap(ROOT, agentterm_command="/not/installed/agentterm").initialize(project, AUTHORITY)
            with self.assertRaises(LifecycleBlocked):
                self.bridge(make_agentterm_health(project / "agentterm-health")).initialize(project, {"revision": "short", "files": {}})

    def test_cross_project_resume_and_corrupt_ledger_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first"
            second = Path(directory) / "second"
            first.mkdir(); second.mkdir()
            make_project(first); make_project(second); make_fake_agent(first)
            health = make_agentterm_health(first / "agentterm-health")
            bridge = self.bridge(health)
            bridge.initialize(first, AUTHORITY)
            shutil.copy2(first / ".agentterm" / "bootstrap-session.json", second / ".agentterm" / "bootstrap-session.json") if (second / ".agentterm").exists() else None
            if not (second / ".agentterm").exists():
                (second / ".agentterm").mkdir()
                shutil.copy2(first / ".agentterm" / "bootstrap-session.json", second / ".agentterm" / "bootstrap-session.json")
            with self.assertRaises(LifecycleBlocked):
                bridge.resume(second)

            db = first / ".agentterm" / "ledger.db"
            connection = sqlite3.connect(db)
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute("UPDATE events SET text='tampered' WHERE rowid=1")
            connection.commit(); connection.close()
            with self.assertRaises(LifecycleBlocked):
                bridge.resume(first)

    def test_host_operations_use_existing_fail_closed_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            health = make_agentterm_health(project / "agentterm-health")
            bridge = self.bridge(health)
            bridge.initialize(project, AUTHORITY)
            denied = bridge.host_operation(project, operation="fixture_echo", approved=False)
            self.assertEqual(denied["outcome"], "BLOCKED_PRECONDITION")
            approved = bridge.host_operation(project, operation="fixture_echo", approved=True)
            self.assertEqual(approved["outcome"], "BLOCKED_PRECONDITION")
            os.environ["CODEX_BOOTSTRAP_HOST_EXECUTION"] = "1"
            try:
                approved = bridge.host_operation(project, operation="fixture_echo", approved=True)
            finally:
                os.environ.pop("CODEX_BOOTSTRAP_HOST_EXECUTION", None)
            self.assertEqual(approved["outcome"], "PASS")
            self.assertIn("command_preview", approved)

    def test_head_drift_after_plan_requires_replanning(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            make_project(project)
            make_fake_agent(project)
            health = make_agentterm_health(project / "agentterm-health")
            bridge = self.bridge(health)
            bridge.initialize(project, AUTHORITY)
            bridge.plan(project, objective="planned task", agent="fake", mutate=True,
                        allowed=["src/**"], forbidden=[], verify=[])
            (project / "src" / "result.txt").write_text("new committed baseline\n", encoding="utf-8")
            git(project, "add", "src/result.txt")
            subprocess.run(["git", "-c", "user.email=test@example.invalid", "-c", "user.name=Bootstrap Test",
                            "commit", "-qm", "baseline drift"], cwd=project, check=True)
            with self.assertRaises(LifecycleBlocked):
                bridge.execute(project, objective="planned task", agent="fake", mutate=True,
                               allowed=["src/**"], forbidden=[], verify=[], confirm=lambda _: True)

    def test_canonical_cli_entrypoint_initializes_status_verifies_and_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            make_project(project)
            health = make_agentterm_health(project / "agentterm-health")
            authority_path = Path(directory) / "authority.json"
            authority_path.write_text(json.dumps(AUTHORITY), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts" / "bootstrap_session.py"),
                       "--bootstrap-root", str(ROOT), "--project-root", str(project),
                       "--agentterm", str(health)]
            for action in (("init", "--authority-json", str(authority_path)), ("status",), ("verify",), ("handoff",)):
                result = subprocess.run(command + list(action), capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
