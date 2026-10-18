from agentterm import gitinfo
from conftest import git


def test_normalize_remote_variants():
    forms = [
        "git@github.com:Example/Proj.git",
        "https://github.com/example/proj",
        "https://user:tok@github.com/Example/Proj.git/",
        "ssh://git@github.com/Example/Proj.git",
    ]
    assert {gitinfo.normalize_remote(f) for f in forms} == {"https://github.com/example/proj"}


def test_snapshot_clean_and_dirty(repo):
    snap = gitinfo.snapshot(repo)
    assert snap.is_git and snap.identity == "https://github.com/example/proj"
    assert snap.branch == "main" and snap.worktree_state == "CLEAN"
    (repo / "src" / "new.py").write_text("x = 1\n")
    (repo / ".agentterm").mkdir()
    (repo / ".agentterm" / "ledger.db").write_text("ignored")
    snap2 = gitinfo.snapshot(repo)
    assert snap2.dirty and snap2.dirty_paths == ("src/new.py",)


def test_non_git_directory(tmp_path):
    snap = gitinfo.snapshot(tmp_path)
    assert not snap.is_git and snap.identity.startswith("local:") and snap.head is None


def test_changed_paths_tracks_edit_create_revert_and_commit(repo):
    root = repo
    head0 = gitinfo.snapshot(root).head
    before = gitinfo.worktree_fingerprint(root)
    (root / "src" / "app.py").write_text("print('changed')\n")
    (root / "docs.md").write_text("new\n")
    after = gitinfo.worktree_fingerprint(root)
    assert gitinfo.changed_paths(root, before, after, head0, head0) == ["docs.md", "src/app.py"]
    # Reverting a dirty file back to clean is also a change relative to the dirty "before".
    git(root, "checkout", "--", "src/app.py")
    reverted = gitinfo.worktree_fingerprint(root)
    assert gitinfo.changed_paths(root, after, reverted, head0, head0) == ["src/app.py"]
    # Committing moves HEAD; the committed paths are still reported.
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "more")
    head1 = gitinfo.snapshot(root).head
    final = gitinfo.worktree_fingerprint(root)
    assert "docs.md" in gitinfo.changed_paths(root, before, final, head0, head1)
