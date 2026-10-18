# Bootstrap AgentTerm Memory Contract

The repository-owned AgentTerm SQLite ledger at `.agentterm/ledger.db` is the
canonical session evidence store after Bootstrap authority has been resolved.
It is append-only at the database layer, hash-chained per origin, redacted on
write, and independently verifiable. The chain is tamper-evident, not
tamper-proof; filesystem access and truncation remain separate risks.

Bootstrap authority files, project authority, and the North Star remain higher
authority than ledger projections. `bootstrap-session.json`, generated briefs,
status output, and `CONTINUE_TOMORROW.md` are projections and must not replace
the resolver or source authority.

The lifecycle records initialization, task plans, AgentTerm task/assessment
packets, approvals, prompts, responses, decisions, failures, verification
results, outcomes, session ends, and checkpoints. Every mutation result carries
repository identity, starting/ending HEAD, changed paths, verification
evidence, receipt, risks, and next action.

AgentTerm reconstructs bounded context from the ledger using the North Star,
pinned facts, scope, task, playbook, last checkpoint, and relevance-ranked
history. A checkpoint is accepted only for the same project identity; stale
HEAD information is visible and rejected where required.

No cross-project ledger import or resume is implicit. A foreign session state,
foreign checkpoint, unsupported schema, or broken chain is
`BLOCKED_PRECONDITION`. Unavailable Codebase Memory remains `UNKNOWN` or
`NOT_RUN`; local AgentTerm continuity never authorizes changes prohibited by
Bootstrap authority.
