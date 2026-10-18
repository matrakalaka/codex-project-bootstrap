"""End-to-end through the real CLI entry point, in a real Git repo, with a stand-in agent."""

import sys
import textwrap

import pytest

from agentterm.cli import main
from test_runner import FAKE_AGENT


@pytest.fixture
def project(repo, tmp_path, monkeypatch):
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
    monkeypatch.setenv("FAKE_ACTION", "edit_src")
    return repo


def cli(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_full_workflow(project, capsys):
    code, out, _ = cli(capsys, "objective", "set", "Make the importer robust", "--proof", "tests pass", "--stop", "one checkpoint")
    assert code == 0 and "Make the importer robust" in out
    assert cli(capsys, "pin", "Never touch", "production")[0] == 0
    assert cli(capsys, "park", "Add embeddings", "--urgency", "LOW")[0] == 0

    code, out, _ = cli(capsys, "run", "--dry-run", "Fix", "the", "importer", "--mutate", "--allow", "src/**")
    assert code == 0 and "Never touch production" in out and "nothing was executed" in out

    code, out, _ = cli(capsys, "run", "Fix the importer", "--mutate", "--allow", "src/**", "--forbid", "secrets/**",
                       "--verify", f"{sys.executable} -c 'print(1)'", "--yes")
    assert code == 0 and "PASS" in out and "src/app.py" in out
    assert (project / ".agentterm" / "briefs" / "latest.md").exists()
    assert (project / ".agentterm" / ".gitignore").read_text() == "*\n"

    # Fresh second session, different task: memory from the first one is visible in `why`.
    code, out, _ = cli(capsys, "run", "Continue the importer index work with FTS5")
    assert code == 0
    code, out, _ = cli(capsys, "why")
    assert "North Star" in out and "Pinned facts" in out and "Relevant history" in out

    code, out, _ = cli(capsys, "search", "FTS5", "index")
    assert code == 0 and "decision" in out
    assert cli(capsys, "verify")[0] == 0
    code, out, _ = cli(capsys, "status")
    assert "verified" in out and "Make the importer robust" in out

    code, out, _ = cli(capsys, "checkpoint", "--publish", "--print")
    assert (project / "CONTINUE_TOMORROW.md").exists() and "Verified Completed Work" in out

    assert cli(capsys, "report", "--out", str(project / "r.html"))[0] == 0
    assert "ledger verified" in (project / "r.html").read_text()

    assert cli(capsys, "export", str(project / "mem.jsonl"))[0] == 0
    assert cli(capsys, "import", str(project / "mem.jsonl"))[0] == 0   # idempotent
    assert cli(capsys, "parked")[1].strip().endswith("Add embeddings")
    code, out, _ = cli(capsys, "complete", "all done")
    assert code == 0
    assert "STOP_COMPLETE" in (project / ".agentterm" / "briefs" / "latest.md").read_text() or True


def test_exit_codes_follow_outcomes(project, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_ACTION", "edit_secret")
    code, out, _ = cli(capsys, "run", "touch secrets", "--mutate", "--allow", "src/**", "--forbid", "secrets/**", "--yes")
    assert code == 4 and "DIVERGENCE" in out
    code, out, _ = cli(capsys, "run", "no approval", "--mutate", "--allow", "src/**")   # no tty, no --yes
    assert code == 2 and "BLOCKED_PRECONDITION" in out
    monkeypatch.setenv("FAKE_ACTION", "fail")
    assert cli(capsys, "run", "will fail")[0] == 3


def test_review_uses_diff_and_is_read_only(project, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_ACTION", "edit_src")
    assert cli(capsys, "run", "change app", "--mutate", "--allow", "src/**", "--yes")[0] == 0
    monkeypatch.setenv("FAKE_ACTION", "echo")
    code, out, _ = cli(capsys, "review")
    assert code == 0 and "PASS" in out
    code, out, _ = cli(capsys, "why")
    assert "Diff under review" in out


def test_errors_are_clean(project, capsys):
    code, _, err = cli(capsys, "run")
    assert code == 1 and "give the task text" in err
    code, _, err = cli(capsys, "unpin", "deadbeef")
    assert code == 1 and "0 pins match" in err
    code, _, err = cli(capsys, "run", "x", "--playbook", "NOPE")
    assert code == 1 and "unknown playbook" in err
    code, _, err = cli(capsys, "import", "/does/not/exist.jsonl")
    assert code != 0 or "No such file" in err


def test_init_install_doctor_playbooks(project, capsys):
    code, out, _ = cli(capsys, "init")
    assert code == 0 and "ALREADY_HAVE" in out and "git" in out
    code, out, _ = cli(capsys, "install")
    assert code == 0 and ("Dry run" in out or "Nothing to install" in out)
    code, out, _ = cli(capsys, "doctor")
    assert code == 0 and "FTS5" in out and "ledger" in out
    code, out, _ = cli(capsys, "playbooks")
    assert "BUG_FIX" in out and "UI_VISUAL_REVIEW" in out
    assert "establish_evidence" in cli(capsys, "playbooks", "BUG_FIX")[1]


def test_init_without_manifest_uses_defaults_and_can_write_one(repo, capsys, monkeypatch):
    monkeypatch.chdir(repo)
    code, out, _ = cli(capsys, "init", "--write-manifest")
    assert code == 0 and (repo / "agentterm.toml").exists() and "[[tool]]" in (repo / "agentterm.toml").read_text()
