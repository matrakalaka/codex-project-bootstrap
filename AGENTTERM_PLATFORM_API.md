# Local API and CLI

Python callers can use `TrustRegistry`, `create_device`, `SyncClient`,
`LocalSyncServer`, `TeamService`, and `EntitlementService` from
`agentterm.platform`. `integrated_local_flow(path)` exercises the complete
local identity, signing, encrypted sync, team invitation/revocation, and
entitlement flow.

The usable CLI entry point is:

```sh
agentterm platform-demo --root /tmp/agentterm-platform-demo
```

It creates only local development evidence. It does not contact a service or
modify a repository checkout.
