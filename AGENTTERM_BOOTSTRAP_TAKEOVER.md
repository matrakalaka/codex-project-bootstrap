# AgentTerm local Bootstrap takeover

Date: 2026-10-19

## Objective

AgentTerm is the preferred local orchestration and memory layer for the
existing Codex Project Bootstrap workflow. Bootstrap remains the authority and
compatibility boundary: its projects, playbooks, Git conventions, commands,
and recovery paths remain usable. Hosted SaaS, public synchronization,
billing, OIDC, Kubernetes, and production PostgreSQL work are frozen and are
not prerequisites for local use.

## Compatibility matrix

| Bootstrap capability | Bootstrap implementation | AgentTerm implementation | Status and evidence |
|---|---|---|---|
| Authority loading and precedence | `GLOBAL_PROJECT_BOOTSTRAP.md`, `GLOBAL_ENGINEERING_STANDARD.md`, project authority, `scripts/bootstrap_authority.py` | `AgentTermBootstrap.initialize` binds authority revision and file hashes into `.agentterm/bootstrap-session.json` | **COMPATIBLE / VERIFIED** in the bridge fixture. Missing or mismatched authority fails closed. |
| Project discovery and identity | Git root, canonical remote, HEAD checks | `gitinfo.snapshot`, Bootstrap bridge identity binding | **COMPATIBLE / VERIFIED**; cross-project state is rejected. |
| Outcomes | `PASS`, `BLOCKED_PRECONDITION`, `FAILED_AFTER_EXECUTION`, `DIVERGENCE` | Same vocabulary and exit codes in `contracts.py`, `runner.py`, bridge | **COMPATIBLE / VERIFIED**. |
| Prompt/task packets | Bootstrap task and approval contracts | Versioned packets in `contracts.py`, fresh context in `context.py` | **COMPATIBLE / VERIFIED**. |
| Approval-before-edit | Bootstrap approval gate | `runner.run_task` requires explicit approval, exact HEAD, scope, and task binding | **COMPATIBLE / VERIFIED**; denied approval executes nothing. |
| Actual Git scope | Bootstrap mutation/scope rules | `gitinfo.changed_paths` plus `governance.scope_violations` | **COMPATIBLE / VERIFIED**; unauthorized fixture mutation returns `DIVERGENCE`. |
| Host verification | Bootstrap allowlisted bridge and command policy | `runner._run_check`, `AgentTermBootstrap.host_operation`, terminal bridge | **COMPATIBLE / VERIFIED**; unsafe/unresolved executables block. |
| `BUG_FIX` and other playbooks | `/prompts/BUG_FIX.md` and established playbooks | Fingerprinted packaged playbooks with procedural-only semantics | **COMPATIBLE / VERIFIED**; `BUG_FIX.v0.json` SHA256 matches the original ZIP. |
| Memory and continuity | `CONTINUE_TOMORROW.md`, handoff records | Hash-chained SQLite ledger, FTS5 retrieval, token-budgeted briefs, checkpoint validation | **IMPROVED / VERIFIED**. |
| Session lifecycle | Bootstrap session/continuation workflow | `session_start`, response, outcome, checkpoint, `resume`, `status`, `handoff` | **COMPATIBLE / VERIFIED** with real Codex bridge run. |
| Agent adapters | Codex/Claude/manual tooling | Built-in Codex, Claude, and generic adapters with `doctor` flag checks | **Codex LIVE VERIFIED**; Claude contract/doctor tested, live Claude execution not claimed. |
| Diagnostics | Bootstrap scripts and host checks | `agentterm doctor`, `verify`, `status`, `platform-health` | **COMPATIBLE / VERIFIED**. |
| Audit and handoff | Logs, reports, continuation files | Redacted hash chain, HTML report, export/import, generated checkpoint | **IMPROVED / VERIFIED**. |
| Worktree protection | Existing Bootstrap Git protections | Synthetic worktree manager and fail-closed production adapter | **COMPATIBLE / VERIFIED**; production Git mutation remains disabled. |

## Original MVP investigation

The original package exists at `/Users/admin/codex-project-bootstrap/agentterm.zip`.
Its SHA256 is:

```text
17b6784fe8a96e7667719131209fc44ecefd56010f69479ac1b6124690e5d500
```

The current `tests/test_runner.py` SHA256 is identical to the file in that
package. The current `BUG_FIX.v0.json` fingerprint is also identical. The
current source is an additive successor: it adds authorization, worktrees,
platform sync, Keychain, provider contracts, and the Bootstrap bridge; it does
not require replacing the original Bootstrap repository.

The test file itself documents that it was reconstructed after a historical
overwrite. Matching the packaged artifact proves consistency with the
available ZIP, not recovery of an earlier unpublished test history. That
remains a documented provenance limitation, not an observed current failure.

The current `pyproject.toml` differs from the ZIP only by the maintained
`cryptography` dependency and optional hosted `psycopg` extra. No global shell
configuration or protected repository was changed. Existing Bootstrap
repository changes (`README.md` and untracked `agentterm.zip`) were preserved
untouched.

## Real Codex evidence

`codex-cli 0.163.0` was available and executed in disposable Git repositories.

### Direct AgentTerm CLI

- `agentterm init --write-manifest` and `agentterm doctor`: PASS.
- Real `codex exec` created exactly `src/result.txt`.
- AgentTerm observed only that path through Git.
- Approval was required and granted for the exact scope.
- Host verification passed.
- The event chain recorded the response, outcome, checkpoint, and handoff.
- A follow-up context/status workflow verified continuity.

### Canonical Bootstrap bridge

- Fresh disposable repository initialized with verified Bootstrap authority
  revision/file hashes: PASS.
- Bootstrap `plan` with `BUG_FIX`: PASS.
- Real Codex mutation through `AgentTermBootstrap.execute`: PASS.
- Observed changed path: `src/bootstrap-result.txt` only.
- Host verification: PASS.
- `resume`: ledger verified, 15 events recovered.

An earlier bridge attempt used `/usr/bin/test`, which the runner correctly
classified as an unresolved non-regular executable and recorded as
`FAILED_AFTER_EXECUTION`; no unsafe bypass was introduced. A fresh clean
fixture then passed with the venv Python executable.

Unauthorized mutation and denied approval are covered by the disposable
fixture tests: **11 targeted tests passed**, including `DIVERGENCE`, no-op
approval denial, tamper detection, interrupted initialization, and recovery.

## Local everyday workflow

From an existing Git project:

```sh
export PYTHONPATH=/Users/admin/codex-agentterm-phase1/vendor/agentterm/src
python3 -m agentterm.cli init --write-manifest
python3 -m agentterm.cli doctor
python3 -m agentterm.cli objective set "Describe the project objective" \
  --proof "What will prove it" --stop "When to stop"
python3 -m agentterm.cli run --agent codex --mutate \
  --allow 'src/**' --forbid '.agentterm/**' \
  --verify 'python3 -c "print(\"verified\")"' \
  --playbook BUG_FIX "Describe one bounded task"
python3 -m agentterm.cli verify
python3 -m agentterm.cli status
python3 -m agentterm.cli checkpoint --publish
```

For Bootstrap-owned lifecycle control, use the existing
`scripts/bootstrap_session.py` entry point with a verified authority JSON;
Bootstrap remains the outer authority and AgentTerm remains the local
ledger/runner implementation. No hosted service is required.

## Reversible activation and rollback

Activation is per project and opt-in. It creates only `.agentterm/`, an
ignored repository-local ledger/checkpoint area, and optional
`agentterm.toml`. It does not modify global shell files, Codex configuration,
existing Bootstrap projects, Git history, or launcher defaults.

To roll back a project without deleting evidence, stop using AgentTerm and
move its local metadata aside after exporting or preserving it:

```sh
mv .agentterm .agentterm.disabled-$(date +%Y%m%d%H%M%S)
```

Then continue with the existing Bootstrap commands. Restore the directory to
resume AgentTerm. Never run this against a protected or active project without
owner authorization.

## Local qualification

- AgentTerm host suite: **142 passed, 0 failed, 0 skipped**.
- Bootstrap/security/continuity regression: **74 passed, 2 subtests passed**.
- Real direct Codex workflow: **PASS**.
- Real Bootstrap bridge Codex workflow: **PASS**.
- Unauthorized mutation/approval/recovery targeted tests: **11 passed**.
- Native Keychain, PostgreSQL, HTTPS, staging, packaging, and compilation:
  previously host-qualified and preserved.

## Readiness decision

**READY FOR LOCAL OPT-IN TAKEOVER.**

This means local per-project use is qualified and reversible. It does not
authorize changing global defaults, modifying protected repositories, enabling
production Git mutation, or resuming hosted infrastructure development.
