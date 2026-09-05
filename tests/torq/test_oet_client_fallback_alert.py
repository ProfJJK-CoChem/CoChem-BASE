# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: OET Client Atomic Fallback Alerting & Uncertainty Marker Protocol.
Validates Suggestion #141 (Deliverable 1) under Method Matrix v4 §10.2, §10.5, §10.8 [M], [E].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from mendeleev import element

from scripts.oet_client import (
    OETClient,
    OETDaemonUnavailableError,
    write_xyz,
)


def test_oet_client_connection_failure_triggers_atomic_alert(tmp_path: Path) -> None:
    """Verify that OET daemon disconnect triggers atomic alert JSON and uncertainty marker with tag [E]."""
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Use authentic physical coordinates (water monomer / H2O)
    symbols = ["O", "H", "H"]
    coords = [(0.0, 0.0, 0.1173), (0.0, 0.7572, -0.4692), (0.0, -0.7572, -0.4692)]
    xyz_file = tmp_path / "water.xyz"
    write_xyz(xyz_file, symbols, coords, comment="Water monomer physical coordinate")

    # Connect to an invalid closed local port (59123) to induce genuine connection failure
    client = OETClient(
        host="127.0.0.1",
        port=59123,
        retries=1,
        retry_delay=0.01,
        timeout=1.0,
        allow_fallback=True,
        fail_on_fallback=False,
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    result = client.calculate_remote(
        symbols=symbols,
        coordinates=coords,
        charge=0,
        multiplicity=1,
        dograd=True,
        xyz_file=xyz_file,
        calculation_base="water",
    )

    assert result["status"] == "OK"
    assert result["fallback_active"] is True
    assert result["provenance_tag"] == "[E]"

    # Verify alert JSON in ephemeral scratch
    alert_file = scratch_dir / "water_EXT.fallback_alert.json"
    assert alert_file.exists(), f"Alert JSON file missing: {alert_file}"

    alert_data = json.loads(alert_file.read_text(encoding="utf-8"))
    assert alert_data["event"] == "OET_DAEMON_FALLBACK_TRIGGERED"
    assert alert_data["provenance_tag"] == "[E]"
    assert alert_data["active_fallback"] == "PhysicalOETFallbackCalculator"
    assert alert_data["investigator_action_required"] is True

    # Validate ISO-8601 timestamp
    ts = datetime.datetime.fromisoformat(alert_data["timestamp_utc"])
    assert ts.year >= 2026

    # Verify uncertainty marker file
    marker_file = scratch_dir / "water_EXT.uncertainty_marker"
    assert marker_file.exists(), f"Uncertainty marker file missing: {marker_file}"


def test_oet_client_strict_provenance_raises_daemon_unavailable(tmp_path: Path) -> None:
    """Verify that fail_on_fallback=True raises explicit OETDaemonUnavailableError upon disconnect."""
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    symbols = ["H", "H"]
    coords = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.7414)]
    xyz_file = tmp_path / "h2.xyz"
    write_xyz(xyz_file, symbols, coords, comment="H2 molecule")

    client = OETClient(
        host="127.0.0.1",
        port=59124,
        retries=1,
        retry_delay=0.01,
        timeout=1.0,
        fail_on_fallback=True,
        scratch_dir=scratch_dir,
    )

    with pytest.raises(OETDaemonUnavailableError) as exc_info:
        client.calculate_remote(
            symbols=symbols,
            coordinates=coords,
            charge=0,
            multiplicity=1,
            xyz_file=xyz_file,
            calculation_base="h2",
        )

    assert "offline" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()