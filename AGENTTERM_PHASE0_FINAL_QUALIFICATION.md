# AgentTerm Phase 0 final qualification

Date: 2026-10-18  
Branch: `feature/agentterm-platform-phase0`  
Baseline: `819afb88e0ba2c38d87ce2439be155a14809754f`  
Qualification commit: pending; Git could not create the shared worktree
`index.lock` during closeout. The exact owner-authorized commit command is
provided in the final handoff.

## Objective and boundary

The objective was to qualify the additive Phase 0 security and protocol
foundations without beginning Phase 1 implementation. The protected release
at `/Users/admin/codex-bootstrap-rc` was read-only. No launcher activation,
publication, deployment, service, credential, device, ADB, port 15041, shell
profile, or global MCP configuration was touched.

No `AGENTS.md` exists in the worktree, its parent, `/Users/admin`, `/Users`,
or `/`. This is documented as an authority absence; no substitute contents
were invented. The requested roadmap is
`vendor/agentterm/docs/ROADMAP.md`. The protected audit was read from
`/Users/admin/codex-bootstrap-rc/ROADMAP_IMPLEMENTATION_AUDIT.md`.

Codebase Memory was checked, but only unrelated UltimateBoxManager and
Brainrot-Heist projects were indexed. It was therefore mis-scoped and not
used as authority, reconfigured, or reindexed.

## Implemented and reviewed

* `security.py`: canonical principals, trust validity/status, domain-separated
  Ed25519 signing, signed-envelope schema, content verification, replay guard,
  and key-store boundary.
* `authorization.py`: explicit grant matching, deny-by-default decisions, and
  verifiable hash-chained audit receipt records.
* `phase0_contracts.py`: data-only worktree lease, sync object, team
  membership, and entitlement contracts.
* Existing compatibility: `Ledger` now supports explicit context management
  and defensive close; `doctor` closes its SQLite FTS5 probe.
* Documentation: `vendor/agentterm/docs/PHASE0_SECURITY.md` records ownership,
  invariants, threat model, limitations, and promotion boundary.

## Exact verification

All runs used the existing isolated environment
`/Users/admin/ic8-stack-qualification/.venv`; no package was installed.

| Check | Result |
|---|---:|
| Focused Phase 0 tests | 6 passed, 0 failed, 0 skipped |
| Vendored AgentTerm pytest suite | 94 passed, 0 failed, 0 skipped |
| AgentTerm with `-W error::ResourceWarning` | 94 passed, 0 failed, 0 skipped |
| Bootstrap scripts/security suite | 74 passed, 0 failed, 4 skipped |
| Bootstrap continuity tests | 18 passed, 0 failed, 0 skipped |
| Python compilation | PASS |
| `git diff --check` | PASS |

The four Bootstrap skips are managed PTY tests blocked by this sandbox's
`AF_UNIX bind` restriction. They are not counted as passes. The exact
owner-authorized macOS command is recorded in
`BOOTSTRAP_SECURITY_REMEDIATION_20261018.md` and runs the four managed tests
plus the complete Bootstrap suite. The prior host evidence reported those
four as passing, but this qualification does not reclassify sandbox skips.

Compatibility evidence includes the complete AgentTerm CLI, ledger, bundle,
runner, contract, Git, report, installer, and lifecycle tests; the complete
Bootstrap lifecycle, authority, launcher, terminal-security, verification,
tool-discovery, and host-bridge suites; and continuity/recovery tests.

## Decision

**Phase 0: QUALIFIED AS AN ADDITIVE, NON-PRODUCTION FOUNDATION.**

**Phase 1: CONDITIONAL GO for design and fixture preparation; NO-GO for
operational worktree mutation or production qualification until independent
human security review signs off the Phase 0 protocol and the host PTY skips are
requalified.**

This is not a production-readiness claim. The pure-Python Ed25519 implementation
requires independent cryptographic review, the key-store interface needs a
reviewed OS-backed adapter, and authenticated encryption is intentionally not
implemented in Phase 0.
