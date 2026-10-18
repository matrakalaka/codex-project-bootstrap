"""Provider-independent production integration contracts.

These adapters are deliberately transport/provider neutral. They validate the
security boundary locally, but do not provision accounts, contact providers,
or silently downgrade to development behavior.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .canon import canonical_bytes
from .platform import CryptoProvider, SyncTransportError
from .security import Principal


class IntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    database: str
    sync_url: str
    max_body: int = 1 << 20
    production_git_mutation: bool = False
    keychain_required: bool = True

    @classmethod
    def from_env(cls, values: dict[str, str]) -> "RuntimeConfig":
        try:
            max_body = int(values.get("AGENTTERM_MAX_BODY", str(1 << 20)))
        except (TypeError, ValueError) as exc:
            raise IntegrationError("sync body limit is not an integer") from exc
        config = cls(environment=values.get("AGENTTERM_ENV", "development"), database=values.get("AGENTTERM_DATABASE", ""), sync_url=values.get("AGENTTERM_SYNC_URL", ""), max_body=max_body, production_git_mutation=values.get("AGENTTERM_ENABLE_PRODUCTION_GIT", "0") == "1", keychain_required=values.get("AGENTTERM_REQUIRE_KEYCHAIN", "1") == "1")
        config.validate()
        return config

    def validate(self) -> None:
        if self.environment not in {"development", "staging", "production"}:
            raise IntegrationError("invalid runtime environment")
        if not self.database or not self.database.startswith("/"):
            raise IntegrationError("database path must be absolute")
        parsed = urllib.parse.urlparse(self.sync_url)
        if self.environment == "development":
            if parsed.scheme not in {"", "http", "https"}:
                raise IntegrationError("invalid development sync URL")
        elif parsed.scheme != "https":
            raise IntegrationError("staging and production sync require HTTPS")
        if self.max_body <= 0 or self.max_body > 8 * (1 << 20):
            raise IntegrationError("sync body limit is outside safe bounds")
        if self.environment == "production" and self.production_git_mutation:
            raise IntegrationError("production Git mutation requires independent activation")
        if self.environment == "production" and not self.keychain_required:
            raise IntegrationError("production requires OS-backed key storage")


class OIDCValidator:
    """Validate claims after a provider-independent signature layer."""
    def __init__(self, *, issuer: str, audience: str, clock: Callable[[], float] = time.time, leeway: int = 30):
        if not issuer or not audience: raise IntegrationError("OIDC issuer and audience are required")
        self.issuer, self.audience, self.clock, self.leeway = issuer, audience, clock, leeway

    def validate(self, claims: dict[str, Any], *, nonce: str | None = None) -> Principal:
        if claims.get("iss") != self.issuer: raise IntegrationError("OIDC issuer mismatch")
        audiences = claims.get("aud")
        if self.audience not in (audiences if isinstance(audiences, list) else [audiences]):
            raise IntegrationError("OIDC audience mismatch")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject: raise IntegrationError("OIDC subject missing")
        try: expires = float(claims["exp"])
        except (KeyError, TypeError, ValueError) as exc: raise IntegrationError("OIDC expiration missing") from exc
        if expires + self.leeway < self.clock(): raise IntegrationError("OIDC assertion expired")
        if nonce is not None and claims.get("nonce") != nonce: raise IntegrationError("OIDC nonce mismatch")
        org, workspace, project = (claims.get(name) for name in ("organization_id", "workspace_id", "project_id"))
        if not all(isinstance(item, str) and item for item in (org, workspace, project)):
            raise IntegrationError("OIDC tenant claims missing")
        return Principal(org, workspace, project, subject, str(claims.get("name", subject)))


class BillingWebhookVerifier:
    """Verify signed billing events and reject timestamp/replay abuse."""
    def __init__(self, public_key: bytes, *, clock: Callable[[], float] = time.time, max_age: int = 300):
        self.public_key, self.clock, self.max_age, self._seen = public_key, clock, max_age, set()

    def verify(self, event: dict[str, Any], signature: bytes) -> dict[str, Any]:
        event_id, issued = event.get("id"), event.get("issued_at")
        if not isinstance(event_id, str) or not event_id or event_id in self._seen:
            raise IntegrationError("billing event replay or missing ID")
        try: issued = float(issued)
        except (TypeError, ValueError) as exc: raise IntegrationError("billing event timestamp invalid") from exc
        if abs(self.clock() - issued) > self.max_age: raise IntegrationError("billing event outside replay window")
        if not CryptoProvider.verify(self.public_key, canonical_bytes(event), signature):
            raise IntegrationError("billing event signature invalid")
        self._seen.add(event_id)
        return event


class HttpsSyncTransport:
    """Production transport contract; TLS verification cannot be disabled."""
    def __init__(self, base_url: str, bearer_token: str, *, max_body: int = 1 << 20, opener: Any = urllib.request.urlopen):
        parsed = urllib.parse.urlparse(base_url.rstrip("/"))
        if parsed.scheme != "https" or not parsed.netloc: raise IntegrationError("sync transport requires an HTTPS URL")
        if not bearer_token: raise IntegrationError("sync transport token is required")
        if max_body <= 0 or max_body > 8 * (1 << 20): raise IntegrationError("sync body limit is outside safe bounds")
        self.base_url, self.bearer_token, self.max_body, self.opener = base_url.rstrip("/"), bearer_token, max_body, opener
        self.ssl_context = ssl.create_default_context()

    def _request(self, method: str, path: str, payload: bytes | None = None) -> dict[str, Any]:
        if payload is not None and len(payload) > self.max_body: raise IntegrationError("sync payload exceeds configured limit")
        request = urllib.request.Request(self.base_url + path, data=payload, method=method, headers={"Authorization": "Bearer " + self.bearer_token, "Content-Type": "application/json"})
        try:
            with self.opener(request, context=self.ssl_context, timeout=10) as response:
                raw = response.read(self.max_body + 1)
                if len(raw) > self.max_body: raise IntegrationError("sync response exceeds configured limit")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise SyncTransportError("HTTPS sync request rejected", status=exc.code, code="remote_error") from exc

    def upload(self, envelope: Any) -> None:
        from dataclasses import asdict
        self._request("POST", "/v1/upload", canonical_bytes(asdict(envelope)))

    def pull(self, device: Any, project: str, after: int = 0) -> list[Any]:
        from .platform import SyncEnvelope
        query = urllib.parse.urlencode({"device": device.device_id, "project": project, "after": after})
        return [SyncEnvelope(**item) for item in self._request("GET", "/v1/pull?" + query)["envelopes"]]
