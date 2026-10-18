"""Runner tests: the governed session loop, driven by a scripted stand-in agent.

NOTE: this file is a RECONSTRUCTION. The original test_runner.py (16 tests) was
accidentally overwritten on 2026-10-17; the test names below come from pytest's
saved node ids and the bodies were rewritten against src/agentterm/runner.py.
`FAKE_AGENT` is imported by test_cli_e2e.py, so its FAKE_ACTION contract
(edit_src / edit_secret / fail / echo, plus commit / leak / report) must be kept.
"""

import json
import subprocess
import sys
import textwrap

import pytest

from agentterm import contracts, gitinfo, playbooks
from agentterm import ledger as L
from agentterm.config import load_settings
from agentterm.runner import RunRequest, parse_session_report, run_task

FAKE_AGENT = textwrap.dedent('''
    import os, pathlib, subprocess, sys

    prompt = sys.stdin.read()
    action = os.environ.get("FAKE_ACTION", "echo")
    root = pathlib.Path.cwd()


    def report(*lines):
        print("\\n## Session Report")
        for line in lines:
            print(line)


    if action == "edit_src":
        (root / "src" / "app.py").write_text("print('changed by agent')\\n")
        print("edited src/app.py")
        report("DECISION: use SQLite FTS5 for the importer index", "COMPLETED: changed app.py", "NEXT: add tests")
    elif action == "report":
        print("analysis only")
        report("DECISION: keep the importer streaming", "FAILED APPROACH: regex CSV parser", "PARKED IDEA: swap the CSV parser",
               "NEXT: add tests")
    elif action == "edit_secret":
        (root / "secrets").mkdir(exist_ok=True)
        (root / "secrets" / "key.txt").write_text("leak\\n")
        print("touched secrets")
    elif action == "commit":
        (root / "src" / "app.py").write_text("print('committed by agent')\\n")
        subprocess.run(["git", "add", "src"], check=True)
        subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=agent", "commit", "-qm", "agent commit"], check=True)
        print("committed")
    elif action == "leak":
        print("here is a key: sk-" + "A1b2C3d4E5" * 4)
        print("password = hunter2hunter2")
    elif action == "fail":
        print("something went wrong", file=sys.stderr)
        sys.exit(3)
    else:
        print("ok, read-only analysis done")
''')


@pytest.fixture
def env(repo, tmp_path, monkeypatch):
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE_AGENT)
    (repo / "agentterm.toml").write_text(textwrap.dedent(f'''
        [project]
        default_agent = "fake"
        [memory]
        budget_tokens = 3000
        [agents.fake]
        command = ["{sys.executable}", "{script}"]
        stdin = true
    '''))
    monkeypatch.chdir(repo)
    settings = load_settings(repo)
    settings.ensure_home()
    ledger = L.Ledger(settings.ledger_path)
    yield settings, ledger, repo
    ledger.close()


def go(env, task="Fix the importer", action="echo", monkeypatch=None, **kw):
    settings, ledger, _ = env
    if monkeypatch is not None:
        monkeypatch.setenv("FAKE_ACTION", action)
    kw.setdefault("agent", "fake")
    return run_task(settings, ledger, RunRequest(task=task, **kw), out=lambda s: None)


def kinds(ledger):
    return [e.kind for e in ledger.events()]


PASS_CHECK = f"{sys.executable} -c 'print(1)'"
FAIL_CHECK = f"{sys.executable} -c 'import sys; sys.exit(1)'"


def test_parse_session_report_rules():
    text = textwrap.dedent('''
        chatter
        ## Session Report
        DECISION: use sqlite
        - FAILED APPROACH: regex parser
        * parked idea: add embeddings
        COMPLETED: <what you finished>
        NEXT:
        next: write tests
        unrelated: ignored
    ''')
    got = parse_session_report(text)
    assert (L.DECISION, "use sqlite") in got
    assert (L.FAILED, "regex parser") in got
    assert (L.PARKED, "add embeddings") in got
    assert (L.NEXT, "write tests") in got
    assert not any(v.startswith("<") for _, v in got)          # unfilled template placeholder
    assert parse_session_report("DECISION: no section header") == []


def test_read_only_pass_records_everything(env, monkeypatch):
    _, ledger, _ = env
    report = go(env, monkeypatch=monkeypatch)
    assert report.outcome == "PASS" and report.exit_code == 0 and report.changed_paths == []
    k = kinds(ledger)
    for expected in (L.SESSION_START, L.TASK, L.ASSESSMENT, L.CONTEXT_PACK, L.PROMPT, L.RESPONSE, L.OUTCOME,
                     L.SESSION_END, L.CHECKPOINT):
        assert expected in k
    assert ledger.verify().ok
    assert contracts.validate("result", report.result_packet) == []
    assert (env[2] / ".agentterm" / "briefs" / "latest.md").exists()


def test_mutation_pass_with_approval_scope_and_verification(env, monkeypatch):
    _, ledger, _ = env
    report = go(env, "Change the app", "edit_src", monkeypatch, mutate=True, allowed=["src/**"],
                forbidden=["secrets/**"], verify=[PASS_CHECK], yes=True)
    assert report.outcome == "PASS", report.reasons
    assert report.changed_paths == ["src/app.py"]
    assert L.APPROVAL in kinds(ledger)
    approval = ledger.latest(report.result_packet["repository"]["identity"], L.APPROVAL).body["packet"]
    assert contracts.validate("approval", approval) == []
    assert report.result_packet["verification"]["result"] == "PASS"
    # agent-reported items are recorded; completion is only an unverified claim
    assert any(e.body.get("text") == "changed app.py" for e in ledger.events(kinds=[L.CLAIM]))
    assert any(e.body.get("text") == "use SQLite FTS5 for the importer index" for e in ledger.events(kinds=[L.DECISION]))


def test_confirm_callback_is_the_approval(env, monkeypatch):
    settings, ledger, repo = env
    seen = []
    monkeypatch.setenv("FAKE_ACTION", "edit_src")
    req = RunRequest(task="Change app", agent="fake", mutate=True, allowed=["src/**"], verify=[PASS_CHECK])
    declined = run_task(settings, ledger, req, confirm=lambda s: seen.append(s) or False, out=lambda s: None)
    assert declined.outcome == "BLOCKED_PRECONDITION" and "approval not granted" in " ".join(declined.reasons)
    assert "Approval required" in seen[0] and "src/**" in seen[0]
    assert (repo / "src" / "app.py").read_text() == "print('hi')\n"          # agent never ran
    approved = run_task(settings, ledger, req, confirm=lambda s: True, out=lambda s: None)
    assert approved.outcome == "PASS", approved.reasons


def test_blocked_preconditions_never_execute_the_agent(env, monkeypatch):
    _, ledger, repo = env
    r = go(env, "x", "edit_src", monkeypatch, mutate=True, yes=True)                       # no --allow
    assert r.outcome == "BLOCKED_PRECONDITION" and r.exit_code == 2
    assert any("explicit --allow" in x for x in r.reasons)
    r = go(env, "x", "edit_src", monkeypatch, agent="no-such-agent")
    assert r.outcome == "BLOCKED_PRECONDITION" and any("unknown agent" in x for x in r.reasons)
    assert (repo / "src" / "app.py").read_text() == "print('hi')\n"
    assert L.RESPONSE not in kinds(ledger)


def test_overlapping_allowed_and_forbidden_is_blocked_before_running(env, monkeypatch):
    _, ledger, repo = env
    r = go(env, "x", "edit_src", monkeypatch, mutate=True, allowed=["src/**"], forbidden=["src/secret"], yes=True)
    assert r.outcome == "BLOCKED_PRECONDITION"
    assert any("collide" in x for x in r.reasons)
    assert L.RESPONSE not in kinds(ledger)


def test_forbidden_path_is_divergence(env, monkeypatch):
    r = go(env, "touch secrets", "edit_secret", monkeypatch, mutate=True, allowed=["src/**"],
           forbidden=["secrets/**"], yes=True)
    assert r.outcome == "DIVERGENCE" and r.exit_code == 4
    assert [v.path for v in r.violations] == ["secrets/key.txt"]
    assert (env[2] / "secrets" / "key.txt").exists()          # evidence is preserved, nothing reverted


def test_write_in_read_only_is_divergence(env, monkeypatch):
    r = go(env, "just look", "edit_src", monkeypatch)
    assert r.outcome == "DIVERGENCE" and r.changed_paths == ["src/app.py"]


def test_agent_failure_and_verification_failure(env, monkeypatch):
    r = go(env, "x", "fail", monkeypatch)
    assert r.outcome == "FAILED_AFTER_EXECUTION" and r.exit_code == 3
    assert any("exited with code 3" in x for x in r.reasons)
    r = go(env, "x", "edit_src", monkeypatch, mutate=True, allowed=["src/**"], verify=[FAIL_CHECK], yes=True)
    assert r.outcome == "FAILED_AFTER_EXECUTION"
    assert any("verification failed" in x for x in r.reasons)
    assert r.result_packet["verification"]["result"] == "FAIL"


def test_agent_commits_are_seen(env, monkeypatch):
    _, _, repo = env
    before = gitinfo.snapshot(repo).head
    r = go(env, "commit it", "commit", monkeypatch, mutate=True, allowed=["src/**"], verify=[PASS_CHECK], yes=True)
    assert r.outcome == "PASS", r.reasons
    assert r.changed_paths == ["src/app.py"]
    rp = r.result_packet["repository"]
    assert rp["starting_head"] == before and rp["ending_head"] != before


def test_preexisting_dirty_work_is_not_attributed(env, monkeypatch):
    _, _, repo = env
    (repo / "README.md").write_text("# user is mid-edit\n")
    r = go(env, "change app", "edit_src", monkeypatch, mutate=True, allowed=["src/**"], verify=[PASS_CHECK], yes=True)
    assert r.outcome == "PASS", r.reasons
    assert "README.md" not in r.changed_paths
    assert any("pre-existing dirty" in x for x in r.result_packet["unresolved_risks"])


def test_dry_run_changes_nothing(env, monkeypatch):
    _, ledger, repo = env
    r = go(env, "change app", "edit_src", monkeypatch, mutate=True, allowed=["src/**"], dry_run=True)
    assert r.dry_run and r.outcome == "PASS" and r.pack is not None
    assert ledger.count() == 0
    assert (repo / "src" / "app.py").read_text() == "print('hi')\n"


def test_memory_carries_into_the_next_fresh_session(env, monkeypatch):
    go(env, "Analyse the importer", "report", monkeypatch)
    second = go(env, "Continue the importer work", "echo", monkeypatch)
    rendered = second.pack.render()
    assert "keep the importer streaming" in rendered           # decision from session 1
    assert "regex CSV parser" in rendered                      # failed approach is never repeated
    assert "swap the CSV parser" in rendered                   # parked idea is carried but not scoped in
    assert second.pack.used <= second.pack.budget


def test_secrets_never_reach_the_ledger(env, monkeypatch):
    _, ledger, _ = env
    go(env, "leak test", "leak", monkeypatch)
    dump = json.dumps([e.as_dict() for e in ledger.events()])
    assert "A1b2C3d4E5" not in dump and "hunter2hunter2" not in dump
    assert "REDACTED" in dump


def test_playbook_is_bound_into_task_and_result(env, monkeypatch):
    book = playbooks.load("BUG_FIX")
    r = go(env, "fix a bug", "echo", monkeypatch, playbook="BUG_FIX")
    assert r.outcome == "PASS"
    assert r.task_packet["playbook"]["fingerprint"] == book["fingerprint"]
    assert r.result_packet["playbook"]["fingerprint"] == book["fingerprint"]
    assert "establish_evidence" in r.pack.render()


def test_foreign_checkpoint_is_rejected(env, monkeypatch):
    settings, ledger, repo = env
    snap = gitinfo.snapshot(repo)
    from agentterm import brief
    cp = brief.build_checkpoint(ledger, snap.identity, snap)
    cp["repository_identity"] = "https://example.test/someone/else"
    ledger.append(snap.identity, L.CHECKPOINT, cp)
    r = go(env, "x", "edit_src", monkeypatch, mutate=True, allowed=["src/**"], yes=True)
    assert r.outcome == "BLOCKED_PRECONDITION"
    assert any("Rejected" in x for x in r.reasons)
    assert (repo / "src" / "app.py").read_text() == "print('hi')\n"
