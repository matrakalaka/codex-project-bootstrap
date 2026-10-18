"""Phase 0 security primitives and versioned cryptographic contracts.

This module deliberately has no network, filesystem, or process side effects.
It owns canonical identities, trust records, Ed25519 signatures, and the
signed/encrypted-envelope contract used by later sync and team layers.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Protocol

from .canon import canonical_bytes, canonical_hash, utc_now

SCHEMA = "agentterm.security.v0"
DOMAIN = b"agentterm/signature/v0\0"


class SecurityError(ValueError):
    pass


def _b(value: bytes | str) -> bytes:
    return value if isinstance(value, bytes) else bytes.fromhex(value)


def _time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise SecurityError("invalid timestamp") from exc


# RFC 8032 Ed25519, kept here to avoid an unreviewed runtime dependency.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    x = pow((y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q), (_Q + 3) // 8, _Q)
    if (x * x - (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q)) % _Q:
        x = (x * _I) % _Q
    return x if x & 1 == 0 else _Q - x


_B = (_xrecover(4 * pow(5, _Q - 2, _Q)) , 4 * pow(5, _Q - 2, _Q) % _Q)


def _add(P: tuple[int, int], Q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = P; x2, y2 = Q
    z = pow(1 + _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    return ((x1 * y2 + x2 * y1) * z % _Q,
            (y1 * y2 + x1 * x2) * pow(1 - _D * x1 * x2 * y1 * y2, _Q - 2, _Q) % _Q)


def _scalarmult(P: tuple[int, int], e: int) -> tuple[int, int]:
    if e == 0: return (0, 1)
    return _add(_scalarmult(_add(P, P), e // 2), P) if e & 1 else _scalarmult(_add(P, P), e // 2)


def _encode(P: tuple[int, int]) -> bytes:
    x, y = P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decode(data: bytes) -> tuple[int, int]:
    if len(data) != 32: raise SecurityError("Ed25519 public key must be 32 bytes")
    n = int.from_bytes(data, "little"); y = n & ((1 << 255) - 1)
    if y >= _Q: raise SecurityError("invalid Ed25519 point")
    x = _xrecover(y)
    if (x & 1) != (n >> 255): x = _Q - x
    return x, y


def public_key(seed: bytes) -> bytes:
    if len(seed) != 32: raise SecurityError("Ed25519 seed must be 32 bytes")
    h = hashlib.sha512(seed).digest(); a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8; a |= 1 << 254
    return _encode(_scalarmult(_B, a))


def sign(seed: bytes, message: bytes) -> bytes:
    if len(seed) != 32: raise SecurityError("Ed25519 seed must be 32 bytes")
    h = hashlib.sha512(seed).digest(); a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8; a |= 1 << 254
    A = _encode(_scalarmult(_B, a)); r = int.from_bytes(hashlib.sha512(h[32:] + DOMAIN + message).digest(), "little") % _L
    R = _encode(_scalarmult(_B, r)); k = int.from_bytes(hashlib.sha512(R + A + DOMAIN + message).digest(), "little") % _L
    return R + ((r + k * a) % _L).to_bytes(32, "little")


def verify(key: bytes, message: bytes, signature: bytes) -> bool:
    try:
        if len(signature) != 64: return False
        A = _decode(key); R = _decode(signature[:32]); s = int.from_bytes(signature[32:], "little")
        if s >= _L: return False
        k = int.from_bytes(hashlib.sha512(signature[:32] + key + DOMAIN + message).digest(), "little") % _L
        return _encode(_scalarmult(_B, s)) == _encode(_add(R, _scalarmult(A, k)))
    except (SecurityError, ValueError, OverflowError):
        return False


@dataclass(frozen=True)
class Principal:
    organization_id: str
    workspace_id: str
    project_id: str
    device_id: str
    user_id: str | None = None

    def __post_init__(self) -> None:
        values = (self.organization_id, self.workspace_id, self.project_id, self.device_id)
        if any(not isinstance(value, str) or not value or any(ch.isspace() for ch in value) for value in values):
            raise SecurityError("principal identifiers must be non-empty and whitespace-free")

    def as_dict(self) -> dict[str, str]:
        result = {"organization_id": self.organization_id, "workspace_id": self.workspace_id,
                  "project_id": self.project_id, "device_id": self.device_id}
        if self.user_id is not None: result["user_id"] = self.user_id
        return result


@dataclass(frozen=True)
class TrustRecord:
    key_id: str
    owner: Principal
    public_key: str
    status: str = "active"
    not_before: str = "1970-01-01T00:00:00Z"
    not_after: str | None = None
    predecessor: str | None = None
    revoked_at: str | None = None

    def usable(self, at: str | None = None) -> bool:
        if self.status != "active": return False
        point = _time(at or utc_now())
        return point >= _time(self.not_before) and (self.not_after is None or point <= _time(self.not_after))


class KeyStore(Protocol):
    def get_private_seed(self, key_id: str) -> bytes: ...


class MemoryKeyStore:
    """Test/key-agent adapter; production adapters must use an OS secure store."""
    def __init__(self) -> None: self._keys: dict[str, bytes] = {}
    def put(self, key_id: str, seed: bytes) -> None:
        if len(seed) != 32: raise SecurityError("private seed must be 32 bytes")
        self._keys[key_id] = bytes(seed)
    def get_private_seed(self, key_id: str) -> bytes:
        try: return self._keys[key_id]
        except KeyError as exc: raise SecurityError("private key is unavailable") from exc


def generate_seed() -> bytes:
    return secrets.token_bytes(32)


@dataclass(frozen=True)
class SignedEnvelope:
    object_id: str
    object_type: str
    principal: Principal
    key_id: str
    created_at: str
    expires_at: str | None
    sequence: int
    content_digest: str
    predecessor_digest: str | None
    ciphertext: str | None
    algorithm: str
    signature: str
    schema_version: str = SCHEMA

    def unsigned(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "object_id": self.object_id,
                "object_type": self.object_type, "principal": self.principal.as_dict(),
                "key_id": self.key_id, "created_at": self.created_at, "expires_at": self.expires_at,
                "sequence": self.sequence, "content_digest": self.content_digest,
                "predecessor_digest": self.predecessor_digest, "ciphertext": self.ciphertext,
                "algorithm": self.algorithm}

    def signing_bytes(self) -> bytes: return canonical_bytes(self.unsigned())

    def verify(self, trust: TrustRecord, *, at: str | None = None, expected_project: str | None = None) -> None:
        if self.schema_version != SCHEMA: raise SecurityError("unsupported envelope schema")
        if self.algorithm not in {"Ed25519", "opaque-ciphertext-v0"}: raise SecurityError("unsupported envelope algorithm")
        if trust.key_id != self.key_id or trust.owner != self.principal or trust.status != "active" or not trust.usable(at): raise SecurityError("untrusted, misbound, or expired key")
        if expected_project is not None and self.principal.project_id != expected_project: raise SecurityError("wrong project")
        if self.expires_at and _time(at or utc_now()) > _time(self.expires_at): raise SecurityError("expired envelope")
        try:
            public = bytes.fromhex(trust.public_key)
            signature = bytes.fromhex(self.signature)
        except ValueError as exc:
            raise SecurityError("malformed key or signature encoding") from exc
        if not verify(public, self.signing_bytes(), signature): raise SecurityError("invalid signature")

    def verify_content(self, content: bytes) -> None:
        if "sha256:" + hashlib.sha256(content).hexdigest() != self.content_digest:
            raise SecurityError("content digest does not match envelope")

    @classmethod
    def create(cls, *, object_id: str, object_type: str, principal: Principal, key_id: str,
               seed: bytes, content: bytes, sequence: int, ciphertext: bytes | None = None,
               expires_at: str | None = None, predecessor_digest: str | None = None,
               created_at: str | None = None) -> "SignedEnvelope":
        if sequence < 0: raise SecurityError("sequence must be non-negative")
        value = cls(object_id, object_type, principal, key_id, created_at or utc_now(), expires_at,
                    sequence, "sha256:" + hashlib.sha256(content).hexdigest(),
                    predecessor_digest, ciphertext.hex() if ciphertext is not None else None,
                    "opaque-ciphertext-v0" if ciphertext is not None else "Ed25519", "")
        return replace(value, signature=sign(seed, value.signing_bytes()).hex())


def envelope_digest(envelope: SignedEnvelope) -> str:
    return canonical_hash(envelope.unsigned() | {"signature": envelope.signature})


class ReplayGuard:
    """Process-local replay/idempotency guard; durable sync state belongs later."""
    def __init__(self) -> None:
        self._objects: set[str] = set()
        self._sequence: dict[tuple[str, str], int] = {}

    def accept(self, envelope: SignedEnvelope) -> None:
        digest = envelope_digest(envelope)
        if digest in self._objects or envelope.object_id in self._objects:
            raise SecurityError("replayed envelope")
        key = (envelope.principal.project_id, envelope.principal.device_id)
        previous = self._sequence.get(key, -1)
        if envelope.sequence <= previous:
            raise SecurityError("replayed or out-of-order sequence")
        self._objects.add(digest); self._objects.add(envelope.object_id); self._sequence[key] = envelope.sequence
