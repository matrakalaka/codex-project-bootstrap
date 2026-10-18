# Local entitlements and metering

The local billing model separates subscription state from authorization. Plans
define device, seat, and sync-object limits. Usage is metered before an
operation is accepted; revoked or expired subscriptions deny the feature.
Plan changes are deterministic and auditable through caller-owned service
state.

No payment information, processor, charge, webhook, or production billing
account is used. Seat integration with the team service and a durable billing
ledger remain activation work.
