import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from bootstrap_authority import (
    AuthorityBlocked,
    CANONICAL_REPOSITORY,
    EXPECTED_FILES,
    EXPECTED_REVISION,
    _cached,
    _online,
    materialize,
    resolve,
)


ROOT = Path(__file__).parent.parent


class BootstrapAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.files = {
            name: (ROOT / name).read_bytes() for name in EXPECTED_FILES
        }
        self.git = Mock(return_value=f"{EXPECTED_REVISION}\trefs/heads/main")
        self.fetch = Mock(side_effect=lambda url: self.files[url.rsplit("/", 1)[-1]])

    def test_online_canonical_path_verifies_identity_revision_and_content(self):
        authority = _online(self.fetch, self.git)
        self.assertEqual(authority.source, "canonical_git")
        self.assertEqual(authority.repository, CANONICAL_REPOSITORY)
        self.assertEqual(authority.revision, EXPECTED_REVISION)

    def test_unavailable_network_uses_verified_cache(self):
        cache = Path("/verified/cache")
        calls = [0]

        def git(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise OSError("network unavailable")
            return CANONICAL_REPOSITORY if calls[0] == 2 else "present"

        show = Mock(side_effect=lambda revision, name, cwd: self.files[name])
        authority = resolve(cache, fetch=Mock(side_effect=OSError("network unavailable")), git=git, show=show)
        self.assertEqual(authority.source, "verified_cache")

    def test_stale_cache_is_rejected(self):
        git = Mock(side_effect=[OSError("network unavailable"), CANONICAL_REPOSITORY, subprocess.CalledProcessError(1, "git")])
        with self.assertRaises(AuthorityBlocked):
            resolve(Path("/stale/cache"), fetch=Mock(side_effect=OSError("network unavailable")), git=git)

    def test_divergent_cache_is_rejected(self):
        calls = [0]

        def git(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise OSError("network unavailable")
            return CANONICAL_REPOSITORY if calls[0] == 2 else "present"

        bad_show = Mock(side_effect=[b"divergent", self.files["PROJECT_NORTH_STAR.md"]])
        with self.assertRaises(AuthorityBlocked):
            resolve(Path("/divergent/cache"), fetch=Mock(side_effect=OSError("network unavailable")), git=git, show=lambda revision, name, cwd: bad_show())

    def test_arbitrary_local_copy_without_canonical_remote_is_rejected(self):
        git = Mock(side_effect=[OSError("network unavailable"), "https://example.invalid/not-canonical.git"])
        with self.assertRaises(AuthorityBlocked):
            resolve(Path("/arbitrary/copy"), fetch=Mock(side_effect=OSError("network unavailable")), git=git)

    def test_no_source_returns_canonical_blocked_stop(self):
        with self.assertRaises(AuthorityBlocked):
            resolve(fetch=Mock(side_effect=OSError("offline")), git=Mock(side_effect=OSError("offline")))

    def test_cache_resolution_is_read_only(self):
        cache = Path("/verified/cache")
        git = Mock(side_effect=[f"{EXPECTED_REVISION}\trefs/heads/main", CANONICAL_REPOSITORY, "present"])
        show = Mock(side_effect=lambda revision, name, cwd: self.files[name])
        resolve(cache, fetch=Mock(side_effect=OSError("network unavailable")), git=git, show=show)
        show.assert_any_call(EXPECTED_REVISION, "GLOBAL_PROJECT_BOOTSTRAP.md", cache)
        show.assert_any_call(EXPECTED_REVISION, "PROJECT_NORTH_STAR.md", cache)

    def test_verified_authority_can_be_materialized_for_codex(self):
        authority = _online(self.fetch, self.git)
        with tempfile.TemporaryDirectory() as directory:
            output = materialize(authority, Path(directory))
            self.assertEqual((output / "GLOBAL_PROJECT_BOOTSTRAP.md").read_bytes(), self.files["GLOBAL_PROJECT_BOOTSTRAP.md"])
            self.assertEqual((output / "PROJECT_NORTH_STAR.md").read_bytes(), self.files["PROJECT_NORTH_STAR.md"])


if __name__ == "__main__":
    unittest.main()
