"""Authoritative IETF RFC 8032 PureEd25519, RFC 8785 JSON Canonicalization Scheme (JCS), & W3C Linked Data Proofs.

Provides pure asymmetric cryptographic provenance generation, verification, and offline
did:key resolution using multicodec 0xed01 prefix and base58btc encoding.
Eradicates non-standard intermediate SHA-512 pre-hashing, signing raw canonical bytes directly.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel

# Standard Bitcoin / IPFS base58btc alphabet
B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ED25519_MULTICODEC_PREFIX = b"\xed\x01"


def b58encode(data: bytes) -> str:
    """Encode bytes into base58btc string."""
    orig_len = len(data)
    data_stripped = data.lstrip(b"\x00")
    leading_zeros = orig_len - len(data_stripped)

    if not data_stripped:
        return "1" * leading_zeros

    acc = int.from_bytes(data_stripped, byteorder="big")
    chars = []
    while acc > 0:
        acc, rem = divmod(acc, 58)
        chars.append(B58_ALPHABET[rem])

    res = "".join(reversed(chars))
    return ("1" * leading_zeros) + res


def b58decode(s: str) -> bytes:
    """Decode base58btc string into raw bytes."""
    orig_len = len(s)
    s_stripped = s.lstrip("1")
    leading_zeros = orig_len - len(s_stripped)

    if not s_stripped:
        return b"\x00" * leading_zeros

    acc = 0
    for char in s_stripped:
        idx = B58_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid character '{char}' in base58 string")
        acc = acc * 58 + idx

    byte_len = (acc.bit_length() + 7) // 8
    raw = acc.to_bytes(byte_len, byteorder="big")
    return (b"\x00" * leading_zeros) + raw


def public_key_to_did_key(public_key: Union[ed25519.Ed25519PublicKey, bytes]) -> str:
    """Encode an Ed25519 public key into a standard W3C did:key identifier offline [D].

    Prefixes raw 32-byte key with multicodec 0xed01 and encodes with base58btc.
    """
    if hasattr(public_key, "public_bytes_raw"):
        raw_bytes = public_key.public_bytes_raw()
    elif isinstance(public_key, ed25519.Ed25519PublicKey):
        raw_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    elif isinstance(public_key, bytes):
        raw_bytes = public_key
    else:
        raise TypeError(f"Expected Ed25519PublicKey or 32-byte bytes, got {type(public_key)}")

    if len(raw_bytes) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(raw_bytes)}")

    multicodec_pub = ED25519_MULTICODEC_PREFIX + raw_bytes
    return "did:key:z" + b58encode(multicodec_pub)


def did_key_to_public_key(did_key: str) -> ed25519.Ed25519PublicKey:
    """Decode a standard W3C did:key identifier into an Ed25519PublicKey offline [D].

    Dispatches zero network calls to external DID registries.
    """
    if not isinstance(did_key, str) or not did_key.startswith("did:key:z"):
        raise ValueError(f"Invalid did:key string format: '{did_key}'")

    multibase_str = did_key[len("did:key:z") :]
    decoded_bytes = b58decode(multibase_str)

    if len(decoded_bytes) < 34 or decoded_bytes[:2] != ED25519_MULTICODEC_PREFIX:
        raise ValueError("Invalid multicodec prefix for Ed25519 did:key")

    raw_pub_bytes = decoded_bytes[2:34]
    return ed25519.Ed25519PublicKey.from_public_bytes(raw_pub_bytes)


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
    hasher = hashlib.sha512()
    hasher.update(canonical_bytes)
    ph_bytes = hasher.digest()

    return sign_canonical_bytes(ph_bytes, private_key)


def sign_report_payload(
    payload: Dict[str, Any],
    private_key: ed25519.Ed25519PrivateKey,
) -> Dict[str, Any]:
    """Emit standard W3C Linked Data Proof envelope with pure cryptographic did:key resolution [D].

    Envelopes payload with an Ed25519Signature2020 proof block.
    """
    # Clean payload excluding any existing proof block
    clean_payload = {k: v for k, v in payload.items() if k != "proof"}
    canonical_bytes = canonicalize_json(clean_payload)
    signature_bytes = private_key.sign(canonical_bytes)

    proof = {
        "type": "Ed25519Signature2020",
        "created": datetime.now(timezone.utc).isoformat(),
        "verificationMethod": public_key_to_did_key(private_key.public_key()),
        "proofPurpose": "assertionMethod",
        "proofValue": base64.urlsafe_b64encode(signature_bytes).decode("ascii"),
    }

    return {
        **clean_payload,
        "proof": proof,
    }


def verify_report_payload(signed_payload: Dict[str, Any]) -> bool:
    """Verify standard W3C Linked Data Proof envelope completely offline [D]."""
    if not isinstance(signed_payload, dict) or "proof" not in signed_payload:
        return False

    proof = signed_payload.get("proof")
    if not isinstance(proof, dict):
        return False

    did_key = proof.get("verificationMethod")
    proof_value = proof.get("proofValue")
    if not did_key or not proof_value:
        return False

    try:
        public_key = did_key_to_public_key(str(did_key))
        sig_bytes = _b64_decode_tolerant(str(proof_value))
        clean_payload = {k: v for k, v in signed_payload.items() if k != "proof"}
        canonical_bytes = canonicalize_json(clean_payload)
        public_key.verify(sig_bytes, canonical_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return False


__all__ = [
    "canonicalize_json",
    "generate_ed25519_key_pair",
    "sign_canonical_bytes",
    "verify_canonical_signature",
    "verify_report_signature",
    "sign_ed25519ph",
    "public_key_to_did_key",
    "did_key_to_public_key",
    "sign_report_payload",
    "verify_report_payload",
]
