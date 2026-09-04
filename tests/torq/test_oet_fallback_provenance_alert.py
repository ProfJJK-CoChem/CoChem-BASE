"""Physical Zero-Mock Test Suite for OET Machine-Learning-to-Empirical Fallback Provenance & Alert Manifests.

Method Matrix Reference: Method Matrix v4 §10.8 (Active Learning & Fallback Provenance Auditing) [M].
Validates Suggestion #62:
- Atomic generation of <base>_EXT.fallback_alert.json in Ring 2 ephemeral scratch ($COCHEM_SCRATCH).
- Staging of alert copy in Ring 3 persistent artifacts ($COCHEM_ARTIFACTS).
- Zero writes to Ring 1 static repository code ($COCHEM_ROOT).
- Creation of <base>_EXT.uncertainty_marker containing provenance tag [E].
"""

from __future__ import annotations

import json
import os
import shutil
import pytest
from pathlib import Path

from cochem_base.schemas import OETFallbackAlertManifest
from Libraries.cochem_torq_oet_client import (
    OETClient,
    PhysicalOETFallbackCalculator,
)


def test_oet_fallback_provenance_and_alert_manifest(tmp_path: Path):
    """Assert atomic fallback manifest generation, uncertainty marker creation, and provenance tag [E]. [M]"""
    # 1. Tripartite storage ring isolation
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    repo_dir = tmp_path / "repo_root"

    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Set up environment
    os.environ["COCHEM_SCRATCH"] = str(scratch_dir)
    os.environ["COCHEM_ARTIFACTS"] = str(artifacts_dir)
    os.environ["COCHEM_ROOT"] = str(repo_dir)

    # Inactive socket address / port to simulate daemon disconnection
    dead_host = "127.0.0.1"
    dead_port = 59876

    client = OETClient(
        host=dead_host,
        port=dead_port,
        timeout=1.0,
        retries=1,
        allow_fallback=True,
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    # Authentic molecular geometry (water molecule H2O)
    symbols = ["O", "H", "H"]
    coords = [
        (0.000000, 0.000000, 0.117300),
        (0.000000, 0.757200, -0.469200),
        (0.000000, -0.757200, -0.469200),
    ]
    base_name = "water_dissoc"

    # Trigger force and energy calculation
    result = client.calculate_remote(
        symbols=symbols,
        coordinates=coords,
        charge=0,
        multiplicity=1,
        dograd=True,
        calculation_base=base_name,
    )

    assert result["status"] == "OK"
    assert result["fallback_active"] is True
    assert result["provenance_tag"] == "[E]"
    assert isinstance(result["energy_Eh"], float)
    assert len(result["gradient_Eh_bohr"]) == 9

    # Verify Ring 2 Scratch Alert Manifest
    scratch_alert = scratch_dir / f"{base_name}_EXT.fallback_alert.json"
    assert scratch_alert.is_file(), f"Missing scratch fallback alert: {scratch_alert}"

    # Verify Ring 3 Artifacts Staged Alert
    staged_alert = artifacts_dir / "alerts" / f"{base_name}_EXT.fallback_alert.json"
    assert staged_alert.is_file(), f"Missing staged artifact fallback alert: {staged_alert}"

    # Verify Ring 2 Uncertainty Marker
    uncertainty_marker = scratch_dir / f"{base_name}_EXT.uncertainty_marker"
    assert uncertainty_marker.is_file(), f"Missing uncertainty marker: {uncertainty_marker}"
    marker_content = uncertainty_marker.read_text(encoding="utf-8")
    assert "PROVENANCE_TAG: [E]" in marker_content
    assert base_name in marker_content

    # Ingest and validate JSON manifest using Pydantic v2 schema
    raw_manifest = json.loads(scratch_alert.read_text(encoding="utf-8"))
    manifest = OETFallbackAlertManifest.model_validate(raw_manifest)

    assert manifest.calculation_base == base_name
    assert manifest.provenance_tag == "[E]"
    assert manifest.fallback_calculator == "PhysicalOETFallbackCalculator"
    assert "SocketConnectionError" in manifest.trigger_event
    assert "platform" in manifest.host_telemetry

    # Verify zero files written to Ring 1 static repository
    repo_files = list(repo_dir.rglob("*"))
    assert len(repo_files) == 0, f"Air-gap violation! Files written to Ring 1 repo: {repo_files}"


def test_oet_fallback_with_unix_domain_socket(tmp_path: Path):
    """Assert fallback activates when targeting inactive Unix domain socket or missing socket file. [M]"""
    scratch_dir = tmp_path / "scratch2"
    artifacts_dir = tmp_path / "artifacts2"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    nonexistent_socket = tmp_path / "oet_daemon.sock"

    client = OETClient(
        socket_path=nonexistent_socket,
        timeout=0.5,
        retries=1,
        allow_fallback=True,
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    symbols = ["C", "H", "H", "H", "H"]
    coords = [
        (0.0, 0.0, 0.0),
        (0.629, 0.629, 0.629),
        (-0.629, -0.629, 0.629),
        (-0.629, 0.629, -0.629),
        (0.629, -0.629, -0.629),
    ]

    result = client.calculate_remote(
        symbols=symbols,
        coordinates=coords,
        calculation_base="methane",
    )

    assert result["fallback_active"] is True
    assert result["provenance_tag"] == "[E]"
    assert (scratch_dir / "methane_EXT.fallback_alert.json").is_file()
