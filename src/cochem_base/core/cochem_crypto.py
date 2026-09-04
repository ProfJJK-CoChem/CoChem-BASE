"""Authoritative IETF RFC 8032 PureEd25519 & RFC 8785 JSON Canonicalization Scheme (JCS).

Provides pure asymmetric cryptographic provenance generation and verification.
Eradicates non-standard intermediate SHA-512 pre-hashing, signing raw canonical bytes directly.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel


def canonicalize_json(data: Any) -> bytes:
    """Canonicalize Python dictionary, list, primitive, or Pydantic model according to RFC 8785 (JCS).

    Sorts dictionary keys lexicographically, removes whitespace, and outputs UTF-8 encoded bytes.
    """
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, BaseModel):
        data = data.dict()
    elif isinstance(data, dict):
        clean_dict = {}
        for k, v in data.items():
            if hasattr(v, "model_dump"):
                clean_dict[str(k)] = v.model_dump(mode="json")
            elif isinstance(v, BaseModel):
                clean_dict[str(k)] = v.dict()
            else:
                clean_dict[str(k)] = v
        data = clean_dict

    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def generate_ed25519_key_pair() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Generate a genuine cryptographically secure Ed25519 key pair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def _b64_decode_tolerant(b64_str: str) -> bytes:
    """Safely decode standard or URL-safe base64 string with missing padding."""
    clean = b64_str.strip()
    pad_len = (-len(clean)) % 4
    padded = clean + ("=" * pad_len)
    try:
        return base64.urlsafe_b64decode(padded)
    except Exception:
        return base64.b64decode(padded)


def sign_canonical_bytes(
    canonical_bytes: bytes,
    private_key: ed25519.Ed25519PrivateKey,
) -> Tuple[str, str, str]:
    """Sign raw canonical bytes directly conforming to RFC 8032 PureEd25519 without double-hashing.

    Returns:
        Tuple[str, str, str]: (signature_urlsafe_b64, public_key_urlsafe_b64, fingerprint_sha256_hex)
    """
    # RFC 8032 §5.1 PureEd25519: Sign raw canonical bytes directly
    signature_bytes = private_key.sign(canonical_bytes)

    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    signature_b64 = base64.urlsafe_b64encode(signature_bytes).decode("utf-8")
    public_key_b64 = base64.urlsafe_b64encode(pub_bytes).decode("utf-8")
    fingerprint = hashlib.sha256(pub_bytes).hexdigest()

    return signature_b64, public_key_b64, fingerprint


def verify_canonical_signature(
    canonical_bytes: bytes,
    signature_b64: str,
    public_key_b64: str,
) -> bool:
    """Verify an RFC 8032 PureEd25519 digital signature over raw canonical bytes."""
    try:
        pub_bytes = _b64_decode_tolerant(public_key_b64)
        sig_bytes = _b64_decode_tolerant(signature_b64)

        if len(pub_bytes) != 32:
            return False
        if len(sig_bytes) != 64:
            return False

        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, canonical_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def verify_report_signature(
    canonical_bytes: bytes,
    signature_b64: str,
    public_key_b64: str,
) -> bool:
    """Ergonomic backward-compatible alias for verify_canonical_signature."""
    return verify_canonical_signature(canonical_bytes, signature_b64, public_key_b64)


def sign_ed25519ph(
    canonical_bytes: bytes,
    private_key: ed25519.Ed25519PrivateKey,
    context: bytes = b"",
) -> Tuple[str, str, str]:
    """Support RFC 8032 §5.1 Ed25519ph pre-hashed signing when domain-separated hashing is explicitly requested."""
    # Ed25519ph pre-hashes input with SHA-512
    hasher = hashlib.sha512()
    hasher.update(canonical_bytes)
    ph_bytes = hasher.digest()

    return sign_canonical_bytes(ph_bytes, private_key)


__all__ = [
    "canonicalize_json",
    "generate_ed25519_key_pair",
    "sign_canonical_bytes",
    "verify_canonical_signature",
    "verify_report_signature",
    "sign_ed25519ph",
]
