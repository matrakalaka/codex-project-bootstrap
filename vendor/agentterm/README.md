# agentterm

A governed memory and audit layer for AI coding agents (Codex, Claude Code, any CLI agent).
**The terminal owns the memory, not the model**, so no agent has to compact.

- **Append-only, hash-chained ledger** (SQLite + FTS5) of every prompt, response, decision, verification and outcome. Nothing is summarized away.
- **Fresh session every task.** Each run gets a small brief built from the North Star, pinned facts, task state and relevance-ranked history within a token budget. `agentterm why` shows exactly which events were injected.
- **Governed execution** (ported from `codex-project-bootstrap`): bounded task packet, human approval bound to repo HEAD, scope enforced from real Git changes, host-run verification, outcomes `PASS | BLOCKED_PRECONDITION | FAILED_AFTER_EXECUTION | DIVERGENCE`.
- **Agents are interchangeable.** Built in: Codex, Claude Code. Anything else via `[agents.<name>] command = [...]` in `agentterm.toml`.
- **Generated checkpoint** (`CONTINUE_TOMORROW.md`) validated against the live repo before resume; foreign-repo checkpoints are rejected.
- **Secrets are redacted** before anything enters the ledger.
- **Portable evidence:** `export` / `import` verifiable bundles, `report` HTML audit page, `tui` dashboard.

## Quickstart

```sh
pip install -e .            # Python 3.11+, no dependencies
cd your-repo
agentterm init              # read-only discovery of agents/tools
agentterm install --apply   # optional: install what is missing (dry-run by default)
agentterm objective set "Make the importer robust" --proof "tests pass" --stop "one checkpoint"
agentterm pin "Never touch the production database"
agentterm run "Fix CSV quoting" --agent codex --mutate --allow "src/**" --forbid "secrets/**" \
    --verify "pytest -q"    # asks for approval; --yes to skip the prompt
agentterm why               # what the agent was told, and why
agentterm status            # repo, ledger integrity, context budget
agentterm verify            # recompute the hash chains (exit 4 if tampered)
agentterm checkpoint --publish   # write CONTINUE_TOMORROW.md into the repo
```

Exit codes: `0` PASS, `2` BLOCKED_PRECONDITION, `3` FAILED_AFTER_EXECUTION, `4` DIVERGENCE, `1` usage error.

## How "no compaction" works

1. Every event is appended to `.agentterm/ledger.db` (repository-owned memory; git-ignored by default).
2. A session ends after one task. The next session starts clean with a brief assembled from the ledger, not replayed from a chat.
3. Pins and the North Star are always injected; everything else competes for the token budget by relevance. Failed approaches and parked ideas are carried so they are not repeated or acted on.
4. The model never grades itself: scope comes from Git, success comes from the verification commands you declare.

## Honest limits

- Scope violations are **detected after the fact** (and reported as DIVERGENCE with evidence). Prevention comes from the agent's own sandbox flags (`--sandbox`, `--permission-mode`), which the adapters set.
- Adapter flags track fast-moving CLIs; `agentterm doctor` re-checks them against the installed `--help`.
- The ledger is tamper-**evident**, not tamper-proof: someone with file access can rewrite it, and `verify` will show where. Anchor the chain head (in a bundle or checkpoint) to detect truncation.

See `docs/ROADMAP.md` for phases and monetization, `docs/FROM_BOOTSTRAP.md` for what was ported from your bootstrap repo.

## Phase 0 security foundations

The additive Phase 0 contracts are documented in `docs/PHASE0_SECURITY.md`.
They provide identity/trust records, domain-separated signed envelopes,
deny-by-default authorization, audit provenance, and data-only boundaries for
future worktree, sync, team, and entitlement implementations. They do not
activate Git mutation, network sync, billing, or deployment.
