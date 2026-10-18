import pytest

from agentterm.billing import BillingAdapter, MockBillingProvider
from agentterm.integration import IntegrationError
from agentterm.oidc import OIDCClient, SyntheticOIDCProvider
from agentterm.platform import EntitlementService


def test_synthetic_oidc_pkce_signature_rotation_and_state():
    provider = SyntheticOIDCProvider(clock=lambda: 1000); client = OIDCClient(client_id="agentterm", redirect_uri="http://127.0.0.1/callback", discovery=provider.discovery, jwks=provider.jwks, clock=lambda: 1000)
    verifier = "verifier"; code, state = client.begin(state="state", nonce="nonce", verifier=verifier, claims={"sub": "user-1", "organization_id": "org", "workspace_id": "ws", "project_id": "p", "name": "Alice"}, provider=provider)
    assert client.exchange(code=code, state=state, expected_state="state", nonce="nonce", verifier=verifier, provider=provider).device_id == "user-1"
    code, _ = client.begin(state="state-2", nonce="nonce-2", verifier=verifier, claims={"sub": "user-1", "organization_id": "org", "workspace_id": "ws", "project_id": "p"}, provider=provider)
    with pytest.raises(IntegrationError): client.exchange(code=code, state="wrong", expected_state="state-2", nonce="nonce-2", verifier=verifier, provider=provider)
    provider.rotate_keys(); code, state = client.begin(state="state-3", nonce="nonce-3", verifier=verifier, claims={"sub": "user-1", "organization_id": "org", "workspace_id": "ws", "project_id": "p"}, provider=provider)
    assert client.exchange(code=code, state=state, expected_state="state-3", nonce="nonce-3", verifier=verifier, provider=provider).device_id == "user-1"


def test_billing_adapter_orders_events_and_is_idempotent():
    provider = MockBillingProvider(clock=lambda: 1000); entitlements = EntitlementService(); adapter = BillingAdapter(entitlements, provider.public, clock=lambda: 1000)
    event, signature = provider.event("evt-1", "org", "subscription.updated", sequence=2, plan="pro"); assert provider.deliver(adapter, event, signature)
    old, old_sig = provider.event("evt-0", "org", "subscription.canceled", sequence=1); assert not provider.deliver(adapter, old, old_sig)
    with pytest.raises(IntegrationError): provider.deliver(adapter, event, signature)
    failed, failed_sig = provider.event("evt-2", "org", "payment.failed", sequence=3); assert provider.deliver(adapter, failed, failed_sig); assert not entitlements.permit("org", "sync_objects")
