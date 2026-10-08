"""Local integrity checks; these tests do not qualify a GitHub transaction.

Receipts, integer IDs, project commits and HTTP byte strings below are explicitly
mathematical schema examples. They do not represent repositories, releases,
provider responses, engine observations or authorizations. The shipped reviewed
distribution descriptors are read unchanged. No provider is replaced or called.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from scripts import private_engine_assets as assets


def _mathematical_digest(label: str) -> str:
    return hashlib.sha256(("mathematical-schema-example:" + label).encode()).hexdigest()


def _mathematical_id(label: str) -> int:
    return int(_mathematical_digest(label)[:8], 16) + 1


def _mathematical_receipt(engine: str = "orca") -> dict[str, Any]:
    """Construct a schema example, without asserting any provider state."""
    raw = (assets.ROOT / "scripts" / f"{engine}-distribution.json").read_bytes()
    distribution = assets._json(raw)
    now = assets._utc_now()
    task = _mathematical_digest(engine + ":task")[:32]
    record: dict[str, Any] = {
        "schema_version": assets.SCHEMA,
        "task_id": task,
        "purpose": assets.PURPOSE,
        "engine": engine,
        "approved_distribution": distribution,
        "approved_distribution_sha256": assets._sha(assets.canonical_json(distribution)),
        "approved_descriptor_file_sha256": assets._sha(raw),
        "source": {
            "repository": distribution["repository"],
            "repository_id": _mathematical_id("source repository"),
            "release_tag": distribution["release_tag"],
            "release_id": _mathematical_id("source release"),
            "asset_id": _mathematical_id("source asset"),
            "asset_name": distribution["archive_name"],
            "size_bytes": 64,  # Mathematical byte-count domain; no archive is asserted.
            "sha256": distribution["sha256"],
            "version": distribution[f"{engine}_version"],
            "platform": distribution["platform"],
            "architecture": distribution["architecture"],
        },
        "destination": {
            "repository": "MathematicalSchema/ExampleProject",
            "repository_id": _mathematical_id("destination repository"),
            "owner_id": _mathematical_id("destination owner"),
            "release_tag": f"cochem-private-{task}",
            "release_id": _mathematical_id("destination release"),
            "asset_id": _mathematical_id("destination asset"),
            "asset_name": distribution["archive_name"],
            "size_bytes": 64,
            "sha256": distribution["sha256"],
        },
        "project": {
            "ref": "refs/heads/mathematical-schema",
            "source_sha": hashlib.sha1(b"mathematical-schema-project-commit").hexdigest(),
            "workflow_path": f".github/workflows/{engine}_provisioning.yml",
            "calculation": None,
        },
        "created_at": assets._iso(now - timedelta(minutes=1)),
        "expires_at": assets._iso(now + timedelta(hours=1)),
        "status": "ready",
    }
    _seal_intent(record)
    return record


def _seal_intent(record: dict[str, Any]) -> None:
    record["intent_sha256"] = assets._sha(assets._intent_bytes(record))


@pytest.mark.parametrize("engine", ["orca", "cfour"])
def test_unchanged_shipped_descriptor_and_canonical_receipt_contract(engine: str) -> None:
    record = _mathematical_receipt(engine)
    original = (assets.ROOT / "scripts" / f"{engine}-distribution.json").read_bytes()
    assert assets._distribution(engine, record["approved_distribution"]) == assets._json(original)
    raw = assets.canonical_json(record)
    assert assets.load_staging_receipt(raw, assets._sha(raw)) == record
    assert record["approved_descriptor_file_sha256"] == assets._sha(original)
    assert (assets.ROOT / "scripts" / f"{engine}-distribution.json").read_bytes() == original


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}'])
def test_duplicate_json_identity_is_rejected(raw: bytes) -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        assets._json(raw)


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_is_rejected(literal: str) -> None:
    with pytest.raises(ValueError, match="Nonfinite"):
        assets._json(('{"value":' + literal + "}").encode())


def test_retained_byte_pin_rejects_corruption_and_noncanonical_serialization() -> None:
    record = _mathematical_receipt()
    raw = assets.canonical_json(record)
    with pytest.raises(ValueError, match="independently retained digest"):
        assets.load_staging_receipt(raw + b" ", assets._sha(raw))
    pretty = json.dumps(record, indent=2).encode()
    with pytest.raises(ValueError, match="canonical"):
        assets.load_staging_receipt(pretty, assets._sha(pretty))


@pytest.mark.parametrize("allow_expired", [0, 1, None, "true"])
def test_historical_expiry_requires_actual_boolean(allow_expired: Any) -> None:
    raw = assets.canonical_json(_mathematical_receipt())
    with pytest.raises(ValueError, match="explicit boolean"):
        assets.load_staging_receipt(raw, assets._sha(raw), allow_expired=allow_expired)


def test_expired_access_rejected_but_exact_historical_receipt_remains_auditable() -> None:
    record = _mathematical_receipt()
    now = assets._utc_now()
    record["created_at"] = assets._iso(now - timedelta(hours=2))
    record["expires_at"] = assets._iso(now - timedelta(hours=1))
    _seal_intent(record)
    raw = assets.canonical_json(record)
    with pytest.raises(assets.PrivateAssetError, match="expired"):
        assets.load_staging_receipt(raw, assets._sha(raw))
    with pytest.raises(assets.PrivateAssetError, match="expired"):
        assets._asset_access_live(record)
    assert assets.load_staging_receipt(raw, assets._sha(raw), allow_expired=True) == record


@pytest.mark.parametrize("duration", [timedelta(0), timedelta(hours=25), timedelta(hours=-1)])
def test_access_lifetime_is_positive_and_at_most_twenty_four_hours(duration: timedelta) -> None:
    record = _mathematical_receipt()
    record["expires_at"] = assets._iso(assets._timestamp(record["created_at"]) + duration)
    _seal_intent(record)
    with pytest.raises((ValueError, assets.PrivateAssetError)):
        assets._receipt_shape(record, allow_expired=True)
    with pytest.raises(assets.PrivateAssetError):
        assets._asset_access_live(record)


def test_future_creation_is_rejected() -> None:
    record = _mathematical_receipt()
    now = assets._utc_now()
    record["created_at"] = assets._iso(now + timedelta(minutes=1))
    record["expires_at"] = assets._iso(now + timedelta(hours=1))
    _seal_intent(record)
    with pytest.raises(ValueError, match="lifetime"):
        assets._receipt_shape(record)


@pytest.mark.parametrize("value", [True, False, 0, -1, "1", 1.0])
def test_exact_positive_integer_identity_domain(value: Any) -> None:
    with pytest.raises(ValueError, match="positive integers"):
        assets._positive_id(value)


@pytest.mark.parametrize("value", ["0" * 64, "A" * 64, "a" * 63, "a" * 65, None])
def test_independent_sha_domain_rejects_unknown_zero_and_malformed(value: Any) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        assets._digest(value)


@pytest.mark.parametrize("status", [200, 201, 204, 404])
def test_mathematical_http_byte_status_parser_preserves_exact_body(status: int) -> None:
    body = b'{"mathematical_protocol_example":true}' if status != 204 else b""
    # Native gh uses LF for the status line and CRLF for printed headers.
    raw = f"HTTP/2.0 {status} Mathematical example\nX-Example: local\r\n\r\n".encode() + body
    assert assets._http_response(raw) == (status, body)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"404\r\n\r\n{}",
        b"HTTP/2.0 999 Example\r\n\r\n{}",
        b"HTTP/2.0 200 Example",
        b"HTTP/2.0 200\x00bad\r\n\r\n{}",
    ],
)
def test_missing_or_malformed_http_status_is_never_inferred(raw: bytes) -> None:
    with pytest.raises(assets.PrivateAssetError, match="unavailable or malformed"):
        assets._http_response(raw)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("source", "repository_id", 99),
        ("source", "release_id", 98),
        ("source", "asset_id", 97),
        ("project", "ref", "refs/heads/other-schema"),
        ("project", "source_sha", hashlib.sha1(b"other mathematical commit").hexdigest()),
        ("destination", "owner_id", 96),
        ("destination", "size_bytes", 65),
        ("", "approved_descriptor_file_sha256", _mathematical_digest("other raw descriptor")),
    ],
)
def test_full_intent_detects_each_changed_provenance_field(
    tmp_path: Path,
    section: str,
    field: str,
    value: Any,
) -> None:
    record = _mathematical_receipt()
    receipt_path = tmp_path / "mathematical-receipt.json"
    intent_path = Path(str(receipt_path) + ".intent.json")
    assets._write_private(intent_path, assets._intent_bytes(record), exclusive=True)
    journal = {"intent_sha256": record["intent_sha256"]}
    assets._verify_intent(receipt_path, record, journal)
    changed = copy.deepcopy(record)
    (changed[section] if section else changed)[field] = value
    with pytest.raises(ValueError, match="immutable digest"):
        assets._receipt_shape(changed)
    _seal_intent(changed)
    with pytest.raises(assets.PrivateAssetError, match="diverged"):
        assets._verify_intent(receipt_path, changed, {"intent_sha256": changed["intent_sha256"]})


def test_intent_survives_genuine_progress_fields_but_journal_must_bind_it(tmp_path: Path) -> None:
    record = _mathematical_receipt()
    receipt_path = tmp_path / "mathematical-receipt.json"
    raw = assets._intent_bytes(record)
    assets._write_private(Path(str(receipt_path) + ".intent.json"), raw, exclusive=True)
    record["destination"]["release_id"] += 1
    record["destination"]["asset_id"] += 1
    record["status"] = "preparing"
    assert assets._intent_bytes(record) == raw
    assets._verify_intent(receipt_path, record, {"intent_sha256": record["intent_sha256"]})
    with pytest.raises(assets.PrivateAssetError, match="diverged"):
        assets._verify_intent(
            receipt_path, record, {"intent_sha256": _mathematical_digest("other")}
        )


def test_exclusive_private_file_is_immutable_mode_six_hundred_and_hashed(tmp_path: Path) -> None:
    path = tmp_path / "private" / "mathematical-receipt.json"
    raw = assets.canonical_json(_mathematical_receipt())
    assets._write_private(path, raw, exclusive=True)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert assets._file_sha(path) == (assets._sha(raw), len(raw))
    with pytest.raises(FileExistsError):
        assets._write_private(path, b"changed", exclusive=True)
    assert path.read_bytes() == raw
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_atomic_private_journal_replacement_keeps_mode_and_no_temporary_files(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mathematical-journal.json"
    assets._write_private(path, b"old", exclusive=True)
    assets._write_private(path, b"new")
    assert path.read_bytes() == b"new"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(tmp_path.iterdir()) == [path]


def test_private_output_rejects_checkout_git_tree_and_symlink_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside the checkout"):
        assets._private_output(assets.ROOT / "mathematical-private-file")
    git_tree = tmp_path / "other-git-tree"
    (git_tree / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="inside Git"):
        assets._private_output(git_tree / "private-file")
    directory = tmp_path / "directory"
    directory.mkdir()
    link = tmp_path / "directory-link"
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        assets._private_output(link / "private-file")
    target = directory / "mathematical-file"
    target.write_bytes(b"local mathematical data")
    file_link = tmp_path / "file-link"
    file_link.symlink_to(target)
    with pytest.raises(ValueError, match="symlinks"):
        assets._write_private(file_link, b"changed")
    assert target.read_bytes() == b"local mathematical data"


def _mathematical_calculation() -> dict[str, Any]:
    return {
        "job_file": "jobs/mathematical-request.json",
        "input_sha256": _mathematical_digest("calculation bytes"),
        "cores": 2,
        "maxcore_mb": 512,
    }


@pytest.mark.parametrize("field", ["job_file", "input_sha256", "cores", "maxcore_mb"])
def test_calculation_bytes_path_and_resource_controls_are_in_immutable_intent(field: str) -> None:
    record = _mathematical_receipt()
    record["project"]["workflow_path"] = ".github/workflows/orca_calculation.yml"
    record["project"]["calculation"] = _mathematical_calculation()
    _seal_intent(record)
    assert assets._receipt_shape(record) == record
    changed = copy.deepcopy(record)
    replacements = {
        "job_file": "jobs/other-mathematical-request.json",
        "input_sha256": _mathematical_digest("other calculation bytes"),
        "cores": 1,
        "maxcore_mb": 256,
    }
    changed["project"]["calculation"][field] = replacements[field]
    with pytest.raises(ValueError, match="immutable digest"):
        assets._receipt_shape(changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_file", "../outside.json"),
        ("job_file", "/absolute.json"),
        ("input_sha256", "0" * 64),
        ("cores", True),
        ("cores", 3),
        ("maxcore_mb", False),
        ("maxcore_mb", 0),
        ("maxcore_mb", 1025),
    ],
)
def test_calculation_path_checksum_and_classroom_budget_are_strict(field: str, value: Any) -> None:
    calculation = _mathematical_calculation()
    calculation[field] = value
    with pytest.raises(ValueError):
        assets._calculation(".github/workflows/orca_calculation.yml", calculation)


def test_fixed_workflow_cannot_accept_arbitrary_calculation_and_calculation_cannot_omit_intent() -> (
    None
):
    with pytest.raises(ValueError, match="Fixed validation"):
        assets._calculation(".github/workflows/orca_provisioning.yml", _mathematical_calculation())
    with pytest.raises(ValueError, match="exact job bytes"):
        assets._calculation(".github/workflows/orca_calculation.yml", None)


def test_pure_run_identity_requires_exact_uuid_token_sha_and_workflow() -> None:
    record = _mathematical_receipt()
    identity = {
        "head_sha": record["project"]["source_sha"],
        "head_branch": record["project"]["ref"].removeprefix("refs/heads/"),
        "head_repository": {
            "id": record["destination"]["repository_id"],
            "full_name": record["destination"]["repository"],
        },
        "path": record["project"]["workflow_path"],
        "display_title": "Mathematical run identity " + record["task_id"],
    }
    assert assets._matches_run(identity, record)
    for field, value in (
        ("head_sha", hashlib.sha1(b"different mathematical commit").hexdigest()),
        ("head_branch", "other-mathematical-branch"),
        ("head_repository", {"id": 1, "full_name": record["destination"]["repository"]}),
        (
            "head_repository",
            {
                "id": record["destination"]["repository_id"],
                "full_name": "MathematicalSchema/Other",
            },
        ),
        ("path", ".github/workflows/other.yml"),
        ("display_title", "No mathematical task token"),
        ("display_title", "Longer hex identity 0" + record["task_id"] + "0"),
    ):
        changed = {**identity, field: value}
        assert not assets._matches_run(changed, record)


def test_actual_cli_help_and_missing_codespaces_context_make_no_provider_call(
    tmp_path: Path,
) -> None:
    environment = {"PATH": os.defpath, "PYTHONPATH": str(assets.ROOT), "LANG": "C"}
    command = [sys.executable, "-m", "scripts.private_engine_assets"]
    help_result = subprocess.run(
        [*command, "--help"],
        cwd=assets.ROOT,
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert help_result.returncode == 0
    assert b"stage" in help_result.stdout and b"cleanup" in help_result.stdout
    blocked = subprocess.run(
        [*command, "repair", "--receipt", str(tmp_path / "nonexistent-receipt")],
        cwd=assets.ROOT,
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert blocked.returncode == 1
    assert b"require the Codespaces interface" in blocked.stderr
    assert list(tmp_path.iterdir()) == []
