"""Synthetic OIDC provider/client for deterministic local staging tests."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable

from .canon import canonical_bytes
from .integration import IntegrationError, OIDCValidator
from .platform import CryptoProvider


def _encode(value: Any) -> str:
    return base64.urlsafe_b64encode(canonical_bytes(value)).rstrip(b"=").decode()


def _decode(value: str) -> Any:
    return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


@dataclass(frozen=True)
class Discovery:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


class SyntheticOIDCProvider:
    def __init__(self, issuer: str = "https://synthetic.example", clock: Callable[[], float] = time.time):
        self.issuer, self.clock, self._codes, self._keys = issuer.rstrip("/"), clock, {}, {}
        self.rotate_keys()

    def discovery(self) -> dict[str, str]:
        return {"issuer": self.issuer, "authorization_endpoint": self.issuer + "/authorize", "token_endpoint": self.issuer + "/token", "jwks_uri": self.issuer + "/jwks"}

    def jwks(self) -> dict[str, Any]:
        return {"keys": [{"kid": kid, "kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "x": public} for kid, (_, public) in self._keys.items()]}

    def rotate_keys(self) -> str:
        private, public = CryptoProvider.signing_key(); kid = "oidc-" + secrets.token_hex(8); self._keys[kid] = (private, base64.urlsafe_b64encode(public).rstrip(b"=").decode()); self._active = kid; return kid

    def authorize(self, *, client_id: str, redirect_uri: str, state: str, nonce: str, code_challenge: str, claims: dict[str, Any]) -> str:
        if not all(isinstance(value, str) and value for value in (client_id, redirect_uri, state, nonce, code_challenge)): raise IntegrationError("invalid OIDC authorization request")
        code = secrets.token_urlsafe(24); self._codes[code] = {"client_id": client_id, "redirect_uri": redirect_uri, "nonce": nonce, "challenge": code_challenge, "claims": claims, "expires": self.clock() + 120}; return code

    def token(self, *, code: str, client_id: str, redirect_uri: str, verifier: str) -> str:
        record = self._codes.pop(code, None)
        if not record or record["expires"] < self.clock() or record["client_id"] != client_id or record["redirect_uri"] != redirect_uri:
            raise IntegrationError("OIDC authorization code invalid or expired")
        if not secrets.compare_digest(record["challenge"], _challenge(verifier)): raise IntegrationError("OIDC PKCE verification failed")
        claims = dict(record["claims"]) | {"iss": self.issuer, "aud": client_id, "nonce": record["nonce"], "exp": self.clock() + 300}
        header = {"alg": "EdDSA", "kid": self._active, "typ": "JWT"}; payload = _encode(claims); signing = _encode(header) + "." + payload
        return signing + "." + base64.urlsafe_b64encode(CryptoProvider.sign(self._keys[self._active][0], signing.encode())).rstrip(b"=").decode()


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


class OIDCClient:
    def __init__(self, *, client_id: str, redirect_uri: str, discovery: Callable[[], dict[str, str]], jwks: Callable[[], dict[str, Any]], clock: Callable[[], float] = time.time):
        self.client_id, self.redirect_uri, self.discovery_loader, self.jwks_loader, self.clock = client_id, redirect_uri, discovery, jwks, clock; self.metadata = {}; self.keys = {}

    def refresh(self) -> None:
        self.metadata = self.discovery_loader()
        if not self.metadata.get("issuer") or not self.metadata.get("token_endpoint") or not self.metadata.get("jwks_uri"): raise IntegrationError("invalid OIDC discovery metadata")
        self.keys = {item["kid"]: item for item in self.jwks_loader().get("keys", [])}

    def begin(self, *, state: str, nonce: str, verifier: str, claims: dict[str, Any], provider: SyntheticOIDCProvider) -> tuple[str, str]:
        self.refresh(); code = provider.authorize(client_id=self.client_id, redirect_uri=self.redirect_uri, state=state, nonce=nonce, code_challenge=_challenge(verifier), claims=claims); return code, state

    def exchange(self, *, code: str, state: str, expected_state: str, nonce: str, verifier: str, provider: SyntheticOIDCProvider):
        if not secrets.compare_digest(state, expected_state): raise IntegrationError("OIDC state mismatch")
        token = provider.token(code=code, client_id=self.client_id, redirect_uri=self.redirect_uri, verifier=verifier); header_raw, payload_raw, sig_raw = token.split("."); header, claims = _decode(header_raw), _decode(payload_raw)
        key = self.keys.get(header.get("kid"))
        if not key: self.refresh(); key = self.keys.get(header.get("kid"))
        if not key: raise IntegrationError("OIDC signing key unavailable")
        public = base64.urlsafe_b64decode(key["x"] + "=" * (-len(key["x"]) % 4)); signature = base64.urlsafe_b64decode(sig_raw + "=" * (-len(sig_raw) % 4))
        if not CryptoProvider.verify(public, (header_raw + "." + payload_raw).encode(), signature): raise IntegrationError("OIDC signature invalid")
        return OIDCValidator(issuer=self.metadata["issuer"], audience=self.client_id, clock=self.clock).validate(claims, nonce=nonce)
