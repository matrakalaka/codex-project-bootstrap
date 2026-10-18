# Roadmap

## Phase 1: personal use (built, MVP)
Ledger + FTS5 retrieval, fresh-session briefs with budget, Codex/Claude/generic adapters, governed run loop,
approval + scope + verification, checkpoint generation, redaction, `why`, `tui`, `report`, `export`/`import`, `init`/`install`/`doctor`.
Exit criterion: use it on your own repos (AM&G tools, Ultimate Box Manager) until the fresh-session loop beats raw Codex for multi-day tasks.

## Phase 2: audit layer (the part worth paying for)
- Asymmetric (Ed25519) bundle signing so third parties verify authenticity, not just integrity.
- Worktree isolation + one-command discard of DIVERGENCE changes.
- Policy file (`agentterm.policy.toml`): org-wide forbidden paths, required verification, required reviewer agent.
- Cross-agent review gate (Claude reviews Codex, must agree before PASS).
- CI mode: `agentterm verify` + `report` as a pipeline step; exit codes already map to pass/fail.
- MCP server registration from the manifest (currently checked, not written into agent configs).

## Phase 3: monetize (open-core)
- **Free, open source:** everything in Phase 1 and local Phase 2.
- **Pro ($15-30/mo/dev):** encrypted sync of project memory across machines; searchable history across repos (opt-in, separate from repo-owned memory).
- **Team ($X/seat):** shared project memory, hosted evidence dashboard, retention policies, SSO.
- **Enterprise:** audit export to SIEM, signed attestations for "an AI changed this code under these controls", on-prem.
Positioning: "the audit-and-memory layer for AI coding agents", not "a terminal".

## Risks
- Vendors are adding native memory/sessions; durable value is cross-agent neutrality plus governance/audit.
- Dev-tool revenue is slow; treat it as a bonus until real users exist.
- Adapter drift: keep `doctor` flag checks and a fake-agent test suite for every adapter.

## Next 3 actions
1. Run it on one real repo with Codex for a week; log friction.
2. Publish to GitHub (commands below in the README of this handoff) and write the 5-minute demo.
3. Build Phase 2 signing + policy file; ask 3 teams using agents on regulated code if they would pay.
