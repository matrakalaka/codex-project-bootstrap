# Bootstrap AgentTerm Core Architecture

AgentTerm is now a first-class project-session subsystem of Bootstrap, not an
optional discovery row. The integration boundary is
`scripts/agentterm_bootstrap.py`, exposed through `scripts/bootstrap_session.py`.

## Ownership

| Concern | Canonical owner | AgentTerm projection |
| --- | --- | --- |
| Canonical Bootstrap authority and source revision | `scripts/bootstrap_authority.py` | Authority revision and hashes are recorded in the session ledger |
| Project identity, Git HEAD, dirty paths | Bootstrap/AgentTerm Git facts at the lifecycle boundary | Task packets, approvals, results, checkpoints |
| Objective, decisions, approvals, execution, verification, failures | AgentTerm append-only ledger | `CONTINUE_TOMORROW` and session status |
| Human approval and protected scope | AgentTerm runner, constrained by Bootstrap task plan | Approval packet and result packet |
| Host operations | Bootstrap `host_exec_bridge.py` | Explicit audit receipt; never a free-form shell |
| Optional tools and MCP health | Bootstrap `tool_discovery.py` | Discovery context only; native interfaces remain unchanged |

Bootstrap authority is resolved before AgentTerm initialization. AgentTerm
cannot approve its own initialization, change authority, or authorize
publication.

## Runtime boundary

```text
canonical authority resolver
        -> AgentTermBootstrap.initialize
        -> AgentTermBootstrap.discover / plan
        -> AgentTermBootstrap.execute (approval gate)
        -> AgentTerm runner (adapter, Git scope, verification)
        -> ledger verification / checkpoint / resume
```

Initialization requires a verified immutable authority revision and hashes,
the correct Git project identity, and a passing AgentTerm executable health
check. Missing AgentTerm fails closed with `BLOCKED_PRECONDITION`.

The integration uses the pinned local AgentTerm source under
`vendor/agentterm`; it does not edit global Codex configuration or launch an
MCP server. AgentTerm's optional installer remains opt-in and is not invoked by
Bootstrap.
