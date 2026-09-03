"""Unit tests for telemetry secret masking and dynamic credential provider.

Verifies stream-level scrubbing of API keys, private keys, auth headers, and URIs,
deterministic token formats, structured dict scrubbing, and memory zeroizing.
"""

from pathlib import Path

from src.cochem.telemetry.secret_masker import (
    DynamicCredentialProvider,
    EntropyType,
    TelemetrySecretMasker,
    compute_redaction_token,
)


def test_api_key_redaction() -> None:
    """Verify generic API keys and bearer tokens are redacted deterministically."""
    raw = "Client connection initiated with api_key = 'abcdef1234567890abcdef' for node"
    masked = TelemetrySecretMasker.mask_text(raw)

    assert "abcdef1234567890abcdef" not in masked
    assert "[REDACTED:API_KEY:" in masked
    token = compute_redaction_token(EntropyType.API_KEY, "abcdef1234567890abcdef")
    assert token in masked


def test_private_key_redaction() -> None:
    """Verify private key blocks are completely scrubbed."""
    key_pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1+examplePEMkeyPayloadData1234567890abcdef\n"
        "-----END RSA PRIVATE KEY-----"
    )
    raw = f"Loaded TLS credentials:\n{key_pem}\nReady for connection."
    masked = TelemetrySecretMasker.mask_text(raw)

    assert "BEGIN RSA PRIVATE KEY" not in masked
    assert "END RSA PRIVATE KEY" not in masked
    assert "[REDACTED:PRIVATE_KEY:" in masked


def test_auth_header_redaction() -> None:
    """Verify HTTP Authorization Bearer and Basic headers are scrubbed."""
    raw = "Outgoing request: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token to endpoint"
    masked = TelemetrySecretMasker.mask_text(raw)

    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token" not in masked
    assert "Authorization: Bearer [REDACTED:AUTH_HEADER:" in masked


def test_connection_uri_redaction() -> None:
    """Verify database connection credentials in URIs are masked."""
    raw = "Connected to postgresql://chem_user:super_secret_password_123@db.cluster.internal:5432/cochem"
    masked = TelemetrySecretMasker.mask_text(raw)

    assert "super_secret_password_123" not in masked
    assert "postgresql://chem_user:[REDACTED:CONNECTION_URI:" in masked
    assert "@db.cluster.internal:5432/cochem" in masked


def test_structured_record_masking() -> None:
    """Verify recursive dictionary and JSON payload masking."""
    payload = {
        "service": "qm_worker",
        "secret": "confidential_auth_token_9876543210",
        "metric": 42.5,
    }
    masked = TelemetrySecretMasker.mask_record(payload)
    assert isinstance(masked, dict)
    assert "confidential_auth_token_9876543210" not in str(masked["secret"])
    assert "[REDACTED:API_KEY:" in str(masked["secret"])
    assert masked["metric"] == 42.5


def test_dynamic_credential_provider_memory_zeroize(tmp_path: Path) -> None:
    """Verify credential rotation zeroizes evicted mutable character buffers in memory."""
    cred_file = tmp_path / "credentials.env"
    cred_file.write_text("API_TOKEN=super_secret_key_12345\n", encoding="utf-8")

    provider = DynamicCredentialProvider(cred_file)
    assert provider.get_credential("API_TOKEN") == "super_secret_key_12345"

    # Grab reference to allocated C-buffer
    old_buffer = provider._allocated_buffers["API_TOKEN"]
    raw_bytes_before = old_buffer.raw.rstrip(b"\x00")
    assert raw_bytes_before == b"super_secret_key_12345"

    # Rotate credentials
    provider.set_credentials({"API_TOKEN": "rotated_new_key_67890"})
    assert provider.get_credential("API_TOKEN") == "rotated_new_key_67890"

    # Verify evicted buffer was zeroized with ctypes.memset
    assert old_buffer.raw == b"\x00" * len(old_buffer.raw)

    # Clean shutdown wipes active memory
    new_buffer = provider._allocated_buffers["API_TOKEN"]
    provider.close()
    assert new_buffer.raw == b"\x00" * len(new_buffer.raw)
