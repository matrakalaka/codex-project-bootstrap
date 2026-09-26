import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from bootstrap_authority import (
    AuthorityBlocked,
    CANONICAL_REPOSITORY,
    REQUIRED_FILES,
    VERIFIED_FALLBACK_FILES,
    VERIFIED_FALLBACK_REVISION,
    _online,
    materialize,
    resolve,
)


ROOT = Path(__file__).parent.parent
CURRENT_REVISION = "a" * 40


class BootstrapAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.files = {name: (ROOT / name).read_bytes() for name in REQUIRED_FILES}

    def checkout_git(self, args, cwd=None):
        if args[:2] == ["remote", "get-url"]:
            return CANONICAL_REPOSITORY
        if args == ["rev-parse", "HEAD"]:
            return CURRENT_REVISION
        raise AssertionError(args)

    def test_online_git_snapshot_resolves_actual_immutable_revision(self):
        clone = Mock()
        show = Mock(side_effect=lambda revision, name, cwd: self.files[name])

        authority = _online(self.checkout_git, show, clone=clone)

        self.assertEqual(authority.source, "canonical_git")
        self.assertEqual(authority.repository, CANONICAL_REPOSITORY)
        self.assertEqual(authority.revision, CURRENT_REVISION)
        clone.assert_called_once()
        self.assertEqual([call.args[0] for call in show.call_args_list], ["HEAD", "HEAD"])

    def test_content_is_bound_to_revision_from_same_checkout(self):
        show = Mock(side_effect=lambda revision, name, cwd: self.files[name])
        authority = _online(self.checkout_git, show, clone=lambda destination: None)
        self.assertEqual(authority.files, {name: _sha(data) for name, data in self.files.items()})
        self.assertEqual(authority.revision, CURRENT_REVISION)

    def test_ref_movement_cannot_mix_content_revisions(self):
        revisions = iter(["b" * 40])

        def git(args, cwd=None):
            if args[:2] == ["remote", "get-url"]:
                return CANONICAL_REPOSITORY
            if args == ["rev-parse", "HEAD"]:
                return next(revisions)
            raise AssertionError(args)

        show = Mock(side_effect=lambda revision, name, cwd: self.files[name])
        authority = _online(git, show, clone=lambda destination: None)
        self.assertEqual(authority.revision, "b" * 40)
        show.assert_has_calls([unittest.mock.call("HEAD", name, unittest.mock.ANY) for name in REQUIRED_FILES])

    def test_missing_resolver_snapshot_blocks(self):
        def clone_missing(destination):
            raise subprocess.CalledProcessError(1, "git clone", stderr="resolver resource unavailable")

        with self.assertRaises(AuthorityBlocked):
            resolve(clone=clone_missing)

    def test_git_http_404_blocks_without_fallback(self):
        def clone_404(destination):
            raise subprocess.CalledProcessError(128, "git clone", stderr="HTTP 404 Not Found")

        with self.assertRaises(AuthorityBlocked) as context:
            resolve(clone=clone_404)
        self.assertIn("canonical_git", str(context.exception))

    def test_network_unavailable_uses_verified_fallback(self):
        calls = [0]

        def git(args, cwd=None):
            calls[0] += 1
            if args[:2] == ["remote", "get-url"]:
                return CANONICAL_REPOSITORY
            if args == ["rev-parse", "HEAD"]:
                return VERIFIED_FALLBACK_REVISION
            raise AssertionError(args)

        show = Mock(side_effect=lambda revision, name, cwd: self.files[name])
        authority = resolve(Path("/verified/cache"), clone=Mock(side_effect=OSError("offline")), git=git, show=show)
        self.assertEqual(authority.source, "verified_cache")
        self.assertEqual(authority.files, VERIFIED_FALLBACK_FILES)

    def test_network_unavailable_without_verifiable_fallback_blocks(self):
        with self.assertRaises(AuthorityBlocked):
            resolve(clone=Mock(side_effect=OSError("offline")), git=Mock(side_effect=OSError("offline")))

    def test_stale_cache_is_rejected(self):
        def git(args, cwd=None):
            if args[:2] == ["remote", "get-url"]:
                return CANONICAL_REPOSITORY
            if args == ["rev-parse", "HEAD"]:
                return "c" * 40
            raise AssertionError(args)

        with self.assertRaises(AuthorityBlocked):
            resolve(Path("/stale/cache"), clone=Mock(side_effect=OSError("offline")), git=git)

    def test_divergent_cache_is_rejected(self):
        def git(args, cwd=None):
            if args[:2] == ["remote", "get-url"]:
                return CANONICAL_REPOSITORY
            if args == ["rev-parse", "HEAD"]:
                return VERIFIED_FALLBACK_REVISION
            raise AssertionError(args)

        bad_show = Mock(side_effect=[b"divergent", self.files["PROJECT_NORTH_STAR.md"]])
        with self.assertRaises(AuthorityBlocked):
            resolve(Path("/divergent/cache"), clone=Mock(side_effect=OSError("offline")), git=git, show=bad_show)

    def test_arbitrary_local_copy_without_canonical_remote_is_rejected(self):
        git = Mock(side_effect=["https://example.invalid/not-canonical.git"])
        with self.assertRaises(AuthorityBlocked):
            resolve(Path("/arbitrary/copy"), clone=Mock(side_effect=OSError("offline")), git=git)

    def test_source_checkout_requires_canonical_identity(self):
        with self.assertRaises(AuthorityBlocked):
            resolve(source_dir=Path("/local/copy"), git=Mock(return_value="https://example.invalid/copy"))

    def test_materialize_is_caller_owned_and_read_only(self):
        show = Mock(side_effect=lambda revision, name, cwd: self.files[name])
        authority = _online(self.checkout_git, show, clone=lambda destination: None)
        with tempfile.TemporaryDirectory() as directory:
            output = materialize(authority, Path(directory))
            self.assertEqual((output / "GLOBAL_PROJECT_BOOTSTRAP.md").read_bytes(), self.files["GLOBAL_PROJECT_BOOTSTRAP.md"])


def _sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    unittest.main()
