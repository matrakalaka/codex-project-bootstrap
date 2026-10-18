import pytest

from agentterm.canon import canonical_bytes
from agentterm.integration import BillingWebhookVerifier, HttpsSyncTransport, IntegrationError, OIDCValidator, RuntimeConfig
from agentterm.platform import CryptoProvider, integrated_staging_flow


def test_runtime_config_fails_closed_for_production_mutation_and_http():
    values = {"AGENTTERM_ENV": "production", "AGENTTERM_DATABASE": "/tmp/sync.db", "AGENTTERM_SYNC_URL": "http://sync"}
    with pytest.raises(IntegrationError): RuntimeConfig.from_env(values)
    values["AGENTTERM_SYNC_URL"] = "https://sync.example"
    values["AGENTTERM_ENABLE_PRODUCTION_GIT"] = "1"
    with pytest.raises(IntegrationError): RuntimeConfig.from_env(values)


def test_runtime_config_accepts_development_and_bounds_payload():
    config = RuntimeConfig.from_env({"AGENTTERM_DATABASE": "/tmp/sync.db", "AGENTTERM_SYNC_URL": "http://127.0.0.1:1"})
    assert config.environment == "development"
    with pytest.raises(IntegrationError): RuntimeConfig.from_env({"AGENTTERM_DATABASE": "/tmp/db", "AGENTTERM_SYNC_URL": "", "AGENTTERM_MAX_BODY": "999999999"})
    with pytest.raises(IntegrationError): RuntimeConfig.from_env({"AGENTTERM_DATABASE": "/tmp/db", "AGENTTERM_SYNC_URL": "", "AGENTTERM_MAX_BODY": "bad"})


def test_oidc_claim_validation_is_tenant_bound_and_expiry_checked():
    validator = OIDCValidator(issuer="https://issuer", audience="agentterm", clock=lambda: 1000)
    claims = {"iss": "https://issuer", "aud": ["agentterm"], "sub": "user-1", "exp": 1100, "nonce": "n", "organization_id": "org", "workspace_id": "ws", "project_id": "p"}
    assert validator.validate(claims, nonce="n").user_id == "user-1"
    with pytest.raises(IntegrationError): validator.validate({**claims, "exp": 1}, nonce="n")
    with pytest.raises(IntegrationError): validator.validate(claims, nonce="wrong")


def test_billing_webhook_signature_timestamp_and_replay():
    private, public = CryptoProvider.signing_key(); verifier = BillingWebhookVerifier(public, clock=lambda: 1000)
    event = {"id": "evt-1", "issued_at": 1000, "organization": "org", "event": "subscription.updated"}
    signature = CryptoProvider.sign(private, canonical_bytes(event))
    assert verifier.verify(event, signature)["id"] == "evt-1"
    with pytest.raises(IntegrationError): verifier.verify(event, signature)
    stale = {**event, "id": "evt-2", "issued_at": 0}
    with pytest.raises(IntegrationError): verifier.verify(stale, CryptoProvider.sign(private, canonical_bytes(stale)))


def test_https_transport_rejects_plaintext_and_missing_credentials():
    with pytest.raises(IntegrationError): HttpsSyncTransport("http://sync", "token")
    with pytest.raises(IntegrationError): HttpsSyncTransport("https://sync", "")
    with pytest.raises(IntegrationError): HttpsSyncTransport("https://sync", "token", max_body=0)


def test_staging_acceptance_uses_real_loopback_service(tmp_path):
    try:
        result = integrated_staging_flow(tmp_path)
    except PermissionError:
        pytest.skip("host sandbox denies loopback bind; staging requires normal host")
    assert all(result.values()) and result["objects"] == 5
