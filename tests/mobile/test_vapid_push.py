"""
Physical unit tests for Zero-Trust Web Push & Air-Gap Compliance (RFC 8291 & RFC 8292).

Invariants:
- Real Cryptography: Genuine NIST P-256 ECDH, HKDF-SHA256, and AES-128-GCM roundtrip.
- Zero-Trust Payload Sanitization: Strict rejection of SMILES, coordinates, paths, and tracebacks.
- Tripartite Air-Gap Enforcement: Prohibits SaaS relays and restricts public endpoints in air-gap mode.
"""

from __future__ import annotations

import json
import os
import time

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from mendeleev import element

from cochem.telemetry.exceptions import (
    AirGapPushBlockedError,
    PayloadSanitizationViolationError,
)
from cochem.telemetry.push import (
    VAPIDPushEngine,
    b64url_decode,
    b64url_encode,
    sanitize_push_payload,
)
from cochem.telemetry.schemas import (
    PushJobStatus,
    PushNotificationPayload,
    PushSubscriptionEndpoint,
    VAPIDSubscriptionKeys,
)


class TestVAPIDPushEngine:
    """Test suite for RFC 8291 / RFC 8292 Web Push engine and Air-Gap enforcement."""

    def test_dynamic_mendeleev_invariants(self) -> None:
        """Verify dynamic Mendeleev invariants are operational without hardcoding."""
        gold = element("Au")
        assert gold.atomic_number == 79
        assert float(gold.atomic_weight) > 196.0

        platinum = element("Pt")
        assert platinum.atomic_number == 78
        assert float(platinum.atomic_weight) > 195.0

    def test_key_pair_generation_and_loading(self) -> None:
        """Verify NIST P-256 VAPID key generation and base64url serialization."""
        priv_b64, pub_b64 = VAPIDPushEngine.generate_key_pair()
        assert isinstance(priv_b64, str)
        assert isinstance(pub_b64, str)

        pub_bytes = b64url_decode(pub_b64)
        assert len(pub_bytes) == 65
        assert pub_bytes[0] == 4  # Uncompressed point prefix

        # Initialize engine from generated keys
        engine = VAPIDPushEngine(public_key_b64=pub_b64, claim_email="admin@cochem.test")
        assert engine.public_key_b64 == pub_b64
        assert engine.claim_email == "admin@cochem.test"

    def test_rfc_8292_vapid_jwt_signing_and_verification(self) -> None:
        """Verify RFC 8292 ES256 JWT authorization header generation and cryptographic signature."""
        engine = VAPIDPushEngine(claim_email="dev@cochem.local")
        endpoint_url = "http://localhost:8080/push/v1/sub-12345"

        headers = engine.create_vapid_auth_header(endpoint_url)
        assert "Authorization" in headers
        auth_header = headers["Authorization"]
        assert auth_header.startswith("vapid t=")
        assert ", k=" in auth_header

        # Parse token and key from header
        parts = auth_header.split(", ")
        jwt_token = parts[0].replace("vapid t=", "").strip()
        pub_key_b64 = parts[1].replace("k=", "").strip()

        assert pub_key_b64 == engine.public_key_b64

        # Dissect JWT
        jwt_segments = jwt_token.split(".")
        assert len(jwt_segments) == 3
        hdr_b64, pld_b64, sig_b64 = jwt_segments

        # Verify Header
        hdr = json.loads(b64url_decode(hdr_b64).decode("utf-8"))
        assert hdr == {"typ": "JWT", "alg": "ES256"}

        # Verify Payload Claims
        pld = json.loads(b64url_decode(pld_b64).decode("utf-8"))
        assert pld["aud"] == "http://localhost:8080"
        assert pld["sub"] == "mailto:dev@cochem.local"
        assert pld["exp"] > int(time.time())

        # Cryptographically verify the ES256 signature using the public key
        pub_bytes = b64url_decode(pub_key_b64)
        pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub_bytes)

        sig_bytes = b64url_decode(sig_b64)
        assert len(sig_bytes) == 64
        r = int.from_bytes(sig_bytes[:32], "big")
        s = int.from_bytes(sig_bytes[32:], "big")
        der_signature = utils.encode_dss_signature(r, s)

        signing_input = f"{hdr_b64}.{pld_b64}".encode("ascii")
        # If verification fails, cryptography raises InvalidSignature
        pub_key.verify(der_signature, signing_input, ec.ECDSA(hashes.SHA256()))

    def test_rfc_8291_aes128gcm_encryption_decryption_roundtrip(self) -> None:
        """Physical test verifying RFC 8291 encryption and decryption roundtrip."""
        # 1. Simulate client generating P-256 key pair and 16-byte auth secret
        client_priv = ec.generate_private_key(ec.SECP256R1())
        client_pub = client_priv.public_key()
        client_pub_bytes = client_pub.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        client_pub_b64 = b64url_encode(client_pub_bytes)
        auth_secret_bytes = os.urandom(16)
        client_auth_b64 = b64url_encode(auth_secret_bytes)

        # 2. Server encrypts payload
        engine = VAPIDPushEngine()
        raw_plaintext = json.dumps(
            {
                "job_id": "cochem-calc-007",
                "status": "COMPLETED",
                "timestamp": "2026-09-01T12:00:00Z",
                "duration_seconds": 12.34,
                "exit_code": 0,
                "summary": "Geometry optimization converged successfully in 4 iterations.",
            }
        ).encode("utf-8")

        encrypted_body = engine.encrypt_payload(
            payload_bytes=raw_plaintext,
            client_public_key_b64=client_pub_b64,
            client_auth_b64=client_auth_b64,
        )

        # Check encrypted body binary header
        assert len(encrypted_body) > 86  # 86 bytes header + ciphertext + tag
        salt = encrypted_body[:16]
        assert len(salt) == 16
        rs = int.from_bytes(encrypted_body[16:20], "big")
        assert rs == 4096
        idlen = encrypted_body[20]
        assert idlen == 65

        # 3. Client decrypts payload
        decrypted_bytes = VAPIDPushEngine.decrypt_payload(
            encrypted_body=encrypted_body,
            client_private_key=client_priv,
            client_auth_b64=client_auth_b64,
        )

        assert decrypted_bytes == raw_plaintext
        parsed_payload = json.loads(decrypted_bytes.decode("utf-8"))
        assert parsed_payload["job_id"] == "cochem-calc-007"
        assert parsed_payload["status"] == "COMPLETED"

    def test_payload_sanitization_clean_payload_passes(self) -> None:
        """Verify sanitized operational metadata passes validation."""
        clean_payload = PushNotificationPayload(
            job_id="job-uuid-12345",
            status=PushJobStatus.COMPLETED,
            timestamp="2026-09-01T10:00:00Z",
            duration_seconds=45.2,
            exit_code=0,
            summary="Calculation finished normally. 42 cycles completed.",
        )
        validated = sanitize_push_payload(clean_payload)
        assert validated.job_id == "job-uuid-12345"
        assert validated.status == PushJobStatus.COMPLETED

    def test_payload_sanitization_rejects_smiles_and_inchi(self) -> None:
        """Verify chemical structures (SMILES, InChI) are strictly rejected."""
        # SMILES in summary
        with pytest.raises(PayloadSanitizationViolationError):
            sanitize_push_payload(
                {
                    "job_id": "job-123",
                    "status": "COMPLETED",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "duration_seconds": 10.0,
                    "exit_code": 0,
                    "summary": "Completed calculation for molecule CC(=O)Oc1ccccc1C(=O)O",
                }
            )

        # InChI in summary
        with pytest.raises(PayloadSanitizationViolationError):
            sanitize_push_payload(
                {
                    "job_id": "job-123",
                    "status": "COMPLETED",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "duration_seconds": 10.0,
                    "exit_code": 0,
                    "summary": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3 processed",
                }
            )

    def test_payload_sanitization_rejects_coordinates(self) -> None:
        """Verify molecular XYZ coordinate blocks are strictly rejected."""
        xyz_block = "C   0.000000   1.234567  -0.543210\nO   1.123456  -0.234567   0.000000"
        with pytest.raises(PayloadSanitizationViolationError):
            sanitize_push_payload(
                {
                    "job_id": "job-123",
                    "status": "COMPLETED",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "duration_seconds": 10.0,
                    "exit_code": 0,
                    "summary": f"Atoms:\n{xyz_block}",
                }
            )

    def test_payload_sanitization_rejects_internal_paths_and_tracebacks(self) -> None:
        """Verify filesystem paths and unredacted tracebacks are strictly rejected."""
        # Filesystem path
        with pytest.raises(PayloadSanitizationViolationError):
            sanitize_push_payload(
                {
                    "job_id": "job-123",
                    "status": "FAILED",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "duration_seconds": 5.0,
                    "exit_code": 1,
                    "summary": "Log written to /home/user/.cochem/data/out.log",
                }
            )

        # Python traceback
        with pytest.raises(PayloadSanitizationViolationError):
            sanitize_push_payload(
                {
                    "job_id": "job-123",
                    "status": "FAILED",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "duration_seconds": 5.0,
                    "exit_code": 1,
                    "summary": 'Traceback (most recent call last):\nFile "run.py", line 10',
                }
            )

        # ORCA banner snippet
        with pytest.raises(PayloadSanitizationViolationError):
            sanitize_push_payload(
                {
                    "job_id": "job-123",
                    "status": "COMPLETED",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "duration_seconds": 100.0,
                    "exit_code": 0,
                    "summary": "* O R C A * quantum chemistry completed",
                }
            )

    def test_prohibited_saas_relays_blocked(self) -> None:
        """Verify third-party SaaS relays are blocked unconditionally."""
        engine = VAPIDPushEngine()

        saas_endpoints = [
            "https://api.telegram.org/bot12345/sendMessage",
            "https://discord.com/api/webhooks/123/xyz",
            "https://api.pushover.net/1/messages.json",
            "https://fcm.googleapis.com/fcm/send",
            "https://hooks.slack.com/services/T00/B00/X00",
        ]

        for ep in saas_endpoints:
            with pytest.raises(AirGapPushBlockedError) as exc_info:
                engine.create_vapid_auth_header(ep)
            assert "strictly prohibited" in str(exc_info.value) or "blocked" in str(exc_info.value)

    def test_airgap_mode_blocks_external_allows_local(self) -> None:
        """Verify Air-Gap mode blocks external push endpoints and allows local endpoints."""
        orig_airgap = os.environ.get("COCHEM_AIRGAP_MODE")
        try:
            os.environ["COCHEM_AIRGAP_MODE"] = "1"
            engine = VAPIDPushEngine()

            # External push endpoint should be blocked in air-gap mode
            with pytest.raises(AirGapPushBlockedError) as exc_info:
                engine.create_vapid_auth_header("https://push.services.mozilla.com/v1/sub-999")
            assert "blocked under Tripartite Air-Gap Mode" in str(exc_info.value)

            # Local endpoints should succeed
            local_headers = engine.create_vapid_auth_header("http://localhost:8000/push/notify")
            assert "Authorization" in local_headers

            ip_headers = engine.create_vapid_auth_header("http://127.0.0.1:9090/push/notify")
            assert "Authorization" in ip_headers

            lan_headers = engine.create_vapid_auth_header("https://orchestrator.local:8443/push")
            assert "Authorization" in lan_headers
        finally:
            if orig_airgap is not None:
                os.environ["COCHEM_AIRGAP_MODE"] = orig_airgap
            elif "COCHEM_AIRGAP_MODE" in os.environ:
                del os.environ["COCHEM_AIRGAP_MODE"]

    def test_prepare_push_dispatch_full_flow(self) -> None:
        """Verify prepare_push_dispatch orchestrates sanitization, encryption, and headers."""
        priv_b64, pub_b64 = VAPIDPushEngine.generate_key_pair()
        engine = VAPIDPushEngine(public_key_b64=pub_b64)

        # Create client key pair
        client_priv = ec.generate_private_key(ec.SECP256R1())
        client_pub = client_priv.public_key()
        client_pub_b64 = b64url_encode(
            client_pub.public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        )
        client_auth_b64 = b64url_encode(os.urandom(16))

        endpoint = PushSubscriptionEndpoint(
            endpoint="http://localhost:8080/api/push/sub-123",
            keys=VAPIDSubscriptionKeys(p256dh=client_pub_b64, auth=client_auth_b64),
        )

        payload = PushNotificationPayload(
            job_id="calc-uuid-987",
            status=PushJobStatus.COMPLETED,
            timestamp="2026-09-01T15:30:00Z",
            duration_seconds=120.5,
            exit_code=0,
            summary="DFT job completed successfully with 0 errors.",
        )

        dispatch = engine.prepare_push_dispatch(endpoint, payload, ttl=120)
        assert dispatch["endpoint"] == "http://localhost:8080/api/push/sub-123"
        assert "Authorization" in dispatch["headers"]
        assert dispatch["headers"]["Content-Encoding"] == "aes128gcm"
        assert dispatch["headers"]["TTL"] == "120"
        assert isinstance(dispatch["body"], bytes)

        # Decrypt with client keys
        decrypted = VAPIDPushEngine.decrypt_payload(
            encrypted_body=dispatch["body"],
            client_private_key=client_priv,
            client_auth_b64=client_auth_b64,
        )
        decrypted_obj = json.loads(decrypted.decode("utf-8"))
        assert decrypted_obj["job_id"] == "calc-uuid-987"
        assert decrypted_obj["status"] == "COMPLETED"
