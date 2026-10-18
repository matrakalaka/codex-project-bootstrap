import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from agentterm.authorization import Grant
from agentterm.security import Principal
from agentterm.worktree import (AuthorizationError, IntegrityError, ProductionGitAdapter,
                                State, SyntheticGitAdapter, WorktreeError, WorktreeManager,
                                run_in_worktree)


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def fixture_repo(tmp_path):
    root = tmp_path / "fixture"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "fixture@example.com")
    _git(root, "config", "user.name", "Fixture")
    (root / "tracked.txt").write_text("base\n")
    _git(root, "add", "."); _git(root, "commit", "-q", "-m", "base")
    return root


def manager(tmp_path, fixture_repo):
    actor = Principal("org", "ws", "project", "device", "user")
    grants = [Grant(actor, "worktree.create", "repository", grant_id="create"),
              Grant(actor, "worktree.merge", "wt", grant_id="merge"),
              Grant(actor, "worktree.discard", "wt", grant_id="discard")]
    return WorktreeManager(tmp_path / "app", adapter=SyntheticGitAdapter(fixture_repo),
                           protected_roots=[fixture_repo]), actor, grants


def test_fail_closed_production_adapter(tmp_path, fixture_repo):
    m = WorktreeManager(tmp_path / "app", protected_roots=[])
    actor = Principal("o", "w", "p", "d")
    with pytest.raises(WorktreeError):
        m.create(fixture_repo, task_id="t", owner=actor, grants=[Grant(actor, "worktree.create", "repository")])
    with pytest.raises(WorktreeError):
        ProductionGitAdapter().discard(fixture_repo, tmp_path / "x")


def test_create_isolation_and_state_authentication(tmp_path, fixture_repo):
    m, actor, grants = manager(tmp_path, fixture_repo)
    with pytest.raises(AuthorizationError):
        m.create(fixture_repo, task_id="t", owner=actor, grants=[])
    record = m.create(fixture_repo, task_id="t", owner=actor, grants=grants)
    grants = grants + [Grant(actor, "worktree.discard", record.worktree_id, grant_id="discard-specific")]
    status = m.status(record.worktree_id)
    assert status["state"] == "ACTIVE" and status["branch"].startswith("agentterm/")
    archive = m.archive(record.worktree_id, m.worktrees_root / "archive-copy")
    assert archive.exists() and (archive / "tracked.txt").exists()
    assert record.state is State.ACTIVE and record.repository.root == str(fixture_repo)
    (fixture_repo / "original.txt").write_text("must remain absent from agent\n")
    (record_path := __import__("pathlib").Path(record.path) / "agent.txt").write_text("agent\n")
    assert not (fixture_repo / "agent.txt").exists()
    assert run_in_worktree(record, ["sh", "-c", "printf process > process.txt"]).returncode == 0
    assert (record_path.parent / "process.txt").exists()
    metadata = m._record_path(record.worktree_id)
    data = json.loads(metadata.read_text()); data["path"] = str(fixture_repo); metadata.write_text(json.dumps(data))
    with pytest.raises(IntegrityError): m.get(record.worktree_id)


def test_lifecycle_approval_binding_merge_and_replay(tmp_path, fixture_repo):
    m, actor, grants = manager(tmp_path, fixture_repo)
    record = m.create(fixture_repo, task_id="t", owner=actor, grants=grants)
    grants = grants + [Grant(actor, "worktree.merge", record.worktree_id, grant_id="merge-specific")]
    work = __import__("pathlib").Path(record.path)
    (work / "change.txt").write_text("change\n")
    _git(work, "add", "."); _git(work, "commit", "-q", "-m", "agent change")
    m.transition(record.worktree_id, State.READY_FOR_REVIEW)
    assert m.preview_merge(record.worktree_id, "main")
    approval = m.approve(record.worktree_id, operation="merge", actor=actor, grants=grants,
                          target_ref="main", review_digest="sha256:" + "a" * 64)
    merged = m.merge(approval)
    assert merged.state is State.MERGED and (fixture_repo / "change.txt").read_text() == "change\n"
    with pytest.raises(WorktreeError): m.merge(approval)


def test_discard_requires_explicit_approval_and_preserves_unknown(tmp_path, fixture_repo):
    m, actor, grants = manager(tmp_path, fixture_repo)
    record = m.create(fixture_repo, task_id="t", owner=actor, grants=grants)
    grants = grants + [Grant(actor, "worktree.discard", record.worktree_id, grant_id="discard-specific")]
    unknown = m.worktrees_root / "user-created"
    unknown.mkdir(); (unknown / "data").write_text("keep")
    with pytest.raises(AuthorizationError):
        m.approve(record.worktree_id, operation="discard", actor=actor, grants=[])
    approval = m.approve(record.worktree_id, operation="discard", actor=actor, grants=grants)
    discarded = m.discard(approval)
    assert discarded.state is State.DISCARDED and unknown.exists()
    assert any(item.state is State.BLOCKED for item in m.recover())


def test_concurrent_allocation_gets_distinct_owned_worktrees(tmp_path, fixture_repo):
    m, actor, grants = manager(tmp_path, fixture_repo)
    def allocate(i):
        return m.create(fixture_repo, task_id=f"task-{i}", owner=actor, grants=grants).worktree_id
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(allocate, range(4)))
    assert len(ids) == len(set(ids)) == 4
    assert all(m.get(item).state is State.ACTIVE for item in ids)


def test_path_escape_and_invalid_transition_are_rejected(tmp_path, fixture_repo):
    m, actor, grants = manager(tmp_path, fixture_repo)
    record = m.create(fixture_repo, task_id="t", owner=actor, grants=grants)
    with pytest.raises(WorktreeError): m.transition(record.worktree_id, State.MERGED)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(WorktreeError): m._path_safe(outside)
    link = m.worktrees_root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(WorktreeError): m._path_safe(link / "nested")
