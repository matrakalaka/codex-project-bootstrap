import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "tester@example.com")
    git(root, "config", "user.name", "Tester")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('hi')\n")
    (root / "README.md").write_text("# proj\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    git(root, "remote", "add", "origin", "git@github.com:Example/Proj.git")
    return root


@pytest.fixture
def ledger(tmp_path):
    from agentterm.ledger import Ledger

    led = Ledger(tmp_path / "ledger.db")
    yield led
    led.close()
