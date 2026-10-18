# AgentTerm Phase 1 test report

Date: 2026-10-18
Baseline: `1ee3a1cd697d00da967b16c1f0232cff5cbd3097`
Branch: `feature/agentterm-worktree-phase1`

## Executed results

| Suite | Result | Evidence |
|---|---:|---|
| Phase 1 adversarial worktree tests | PASS (6) | `vendor/agentterm/tests/test_worktree_phase1.py` |
| Phase 0 security suite | PASS (100 total AgentTerm suite) | included in full AgentTerm run |
| Full AgentTerm regression | PASS (100) | `vendor/agentterm/tests` |
| Bootstrap/security/continuity regression | PASS (101), 4 AF_UNIX skips, 2 subtests passed | `scripts tests contracts` |
| Strict ResourceWarning AgentTerm regression | PASS (100) | `-W error::ResourceWarning` |
| Python compilation | PASS | `python3 -m compileall` |
| Git diff check | PASS | `git diff --check` |
| AF_UNIX host tests | SKIP (4), BLOCKED for qualification | sandbox denies AF_UNIX bind; managed PTY evidence remains unverified |

The Phase 1 suite uses only temporary disposable repositories. It proves
fail-closed production behavior, exact authorization, isolation from the source
checkout, metadata tamper rejection, lifecycle/approval binding, replay
rejection, unknown-directory preservation, and concurrent allocation.

The root regression reported 4 skips, all explicitly caused by the host
sandbox denying AF_UNIX bind. They are not reported as passes.

## Test gaps

The suite still needs a host-qualified AF_UNIX run, crash injection at each
atomic operation boundary, explicit dirty-source preservation coverage, lease
expiry behavior, and a larger matrix of malformed metadata. These are not
silently counted as passed.
