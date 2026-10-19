# AgentTerm production handoff

## Recommendation

**Local direction supersedes hosted direction: preserve the release candidate
and use AgentTerm as an opt-in local Bootstrap successor. Hosted deployment
work is frozen. GO for independent human security review; NO-GO for production
activation.**

The Phase 1 worktree engine and local platform services are implemented in the
existing development worktree. The local CLI demonstration is real and uses
temporary Git fixtures, encrypted signed envelopes, team authorization,
revocation, entitlements, conflict detection, and conservative recovery.

Provider-independent integration contracts are also implemented for strict
runtime configuration, OIDC claim validation, signed billing webhooks, and an
HTTPS-only sync transport. They are testable locally but are not evidence of a
live identity provider, billing account, hosted service, or deployment.

For the local product objective, see `AGENTTERM_BOOTSTRAP_TAKEOVER.md`. It is
the authoritative local-use decision: **READY FOR LOCAL OPT-IN TAKEOVER**.
Do not resume VPS, hosted OIDC, billing, Kubernetes, or public PostgreSQL work
unless a separate owner-approved objective reopens it.

The strongest remaining risks are the unreviewed production trust boundary,
unqualified real-provider and operational paths, and the shared bearer-token
service boundary. These are deployment and approval gates, not reasons to
discard the locally qualified candidate.

## Owner-authorized next actions

1. Run the root regression and AF_UNIX tests on a normal supported macOS host
   using the documented isolated environment.
2. Obtain independent approval for the cryptographic and mutation boundaries.
3. Select and approve OS keychain/KMS, authenticated transport, retention,
   billing, and incident-response designs.
4. Only after those approvals, create a separately authorized production
   qualification plan. Do not enable the current production adapter directly.

No publication, deployment, live billing, protected-repository mutation, or
launcher activation is authorized by this handoff.

## Final host evidence

The cross-thread SQLite defect and concurrent sequence-ordering defect were
fixed and host-qualified. The final isolated environment run completed 142
tests with zero failures and zero skips, including the loopback/AF_UNIX
selection and the optional PostgreSQL test. The exact requalification command
remains available for future candidate changes:

```sh
cd /Users/admin/codex-agentterm-phase1
PYTHONPATH=vendor/agentterm/src /Users/admin/ic8-stack-qualification/.venv/bin/pytest -q scripts/test_open_terminal_bridge.py vendor/agentterm/tests/test_platform.py -rs
```
