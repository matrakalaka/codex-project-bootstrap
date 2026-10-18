# What came from codex-project-bootstrap

| Bootstrap idea | In agentterm |
|---|---|
| Outcomes PASS / BLOCKED_PRECONDITION / FAILED_AFTER_EXECUTION / DIVERGENCE | Same vocabulary, same exit-code mapping (0/2/3/4) |
| `task_packet.v0`, `human_approval.v0`, `result_packet.v0`, `bootstrap_assessment.v0` | Emitted as real packets (`contracts.py`), canonical-JSON + sha256 compatible |
| Human approval gate before mutation | Approval packet bound to repo identity and HEAD before any mutating run |
| North Star (objective, proof, out of scope, stop boundary) + anti-drift | `agentterm objective`; injected at the top of every brief |
| PARKED IDEA mechanism | `agentterm park` / `parked` / `unpark`; agent-reported ideas are recorded as parked |
| Versioned playbooks with fingerprints | `playbooks/` (BUG_FIX copied unchanged, fingerprint-identical; UI_VISUAL_REVIEW) |
| CONTINUE_TOMORROW checkpoint with staleness / foreign-repo rejection | Generated from the ledger, validated before resume |
| One task, one session, one verified checkpoint | The run loop |
| Tools are advisory; classify ALREADY_HAVE / REAL_GAP | `agentterm init` / `install` |

## Enhancements over the prose standard

- Everything above is **executable and tested**, not instructions an agent may skip.
- Evidence is a **hash-chained ledger**, so audit trails are tamper-evident and exportable.
- Scope is **observed from Git** (including agent-made commits and pre-existing dirty work), not self-reported.
- Memory is **retrieved by relevance within a token budget** instead of a hand-maintained file.

## Parked ideas (not built)

- Cross-agent review pass that must agree before PASS.
- RepoGuard adapter: submit result packets to RepoGuard for admission/evidence.
- Git-worktree isolation so DIVERGENCE can be discarded without touching the main tree.
