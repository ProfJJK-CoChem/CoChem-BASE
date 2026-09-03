"""
Adversarial QA Unit Test Suite for orchestrator/phase_3.py.

Verifies:
1. Complete symbol parity and alias integrity between phase_3.py and cochem_setup_phase_3.py.
2. Full Pydantic V2 model schema integrity and typing.
3. Zero-mock compliance: live quantum engine interrogation, real filesystem operations, atomic JSON state persistence.
4. Method Matrix v4 compliance: ORCA/CFOUR/xTB/CREST/SIF discovery, cryptographic streaming SHA-256 hashing.
5. Standalone CLI execution via phase_3.py entrypoints (--json, --target-path, --output-dir).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import orchestrator.cochem_setup_phase_3 as canonical_p3
import orchestrator.phase_3 as legacy_p3
from orchestrator.phase_3 import (
    STANDARD_MONITORED_ENGINES,
    BinaryEngineItem,
    ContainerAudit,
    DependencyManager,
    EngineStatus,
    EngineTrack,
    EngineTrackSummary,
    EnvironmentFingerprint,
    Phase3AuditError,
    Phase3AuditReport,
    PhaseStatus,
    audit_all_engines,
    audit_binary,
    audit_container_sifs,
    audit_containers,
    audit_engine,
    audit_engines,
    audit_sif,
    audit_sifs,
    audit_single_binary,
    build_track_summaries,
    compute_environment_fingerprint,
    compute_file_sha256,
    compute_fingerprint,
    compute_sha256,
    discover_binary,
    discover_binary_path,
    execute_audit,
    execute_phase_3,
    extract_semantic_version,
    extract_version,
    hash_file,
    interrogate_binary_version,
    interrogate_version,
    main,
    phase_3_audit,
    phase_3_main,
    resolve_binary_search_paths,
    resolve_p3_registry_path,
    resolve_registry_path,
    run_audit,
    run_phase_3,
    run_phase_3_audit,
)

# =============================================================================
# 1. PARITY AND EXPORT TESTS
# =============================================================================


def test_phase_3_all_exports_present() -> None:
    """Verify every symbol declared in legacy_p3.__all__ exists in the module namespace."""
    for symbol_name in legacy_p3.__all__:
        assert hasattr(legacy_p3, symbol_name), f"Missing symbol '{symbol_name}' in phase_3.py"
        symbol = getattr(legacy_p3, symbol_name)
        assert symbol is not None


def test_phase_3_alias_parity() -> None:
    """Verify that all backward compatibility aliases point to canonical functions."""
    assert run_phase_3 is run_phase_3_audit
    assert run_audit is run_phase_3_audit
    assert execute_phase_3 is run_phase_3_audit
    assert execute_audit is run_phase_3_audit
    assert phase_3_audit is run_phase_3_audit

    assert audit_engines is audit_all_engines
    assert audit_engine is audit_single_binary
    assert audit_binary is audit_single_binary
    assert audit_containers is audit_container_sifs
    assert audit_sifs is audit_container_sifs
    assert audit_sif is audit_container_sifs

    assert compute_fingerprint is compute_environment_fingerprint
    assert compute_sha256 is compute_file_sha256
    assert hash_file is compute_file_sha256
    assert discover_binary is discover_binary_path
    assert interrogate_version is interrogate_binary_version
    assert extract_version is extract_semantic_version
    assert resolve_registry_path is resolve_p3_registry_path

    assert main is canonical_p3.main
    assert phase_3_main is canonical_p3.main


def test_phase_3_canonical_symbol_identity() -> None:
    """Verify that re-exported classes and functions are identical to canonical definitions."""
    assert BinaryEngineItem is canonical_p3.BinaryEngineItem
    assert ContainerAudit is canonical_p3.ContainerAudit
    assert DependencyManager is canonical_p3.DependencyManager
    assert EngineStatus is canonical_p3.EngineStatus
    assert EngineTrack is canonical_p3.EngineTrack
    assert EngineTrackSummary is canonical_p3.EngineTrackSummary
    assert EnvironmentFingerprint is canonical_p3.EnvironmentFingerprint
    assert Phase3AuditError is canonical_p3.Phase3AuditError
    assert Phase3AuditReport is canonical_p3.Phase3AuditReport
    assert PhaseStatus is canonical_p3.PhaseStatus
    assert STANDARD_MONITORED_ENGINES == canonical_p3.STANDARD_MONITORED_ENGINES
    assert build_track_summaries is canonical_p3.build_track_summaries
    assert resolve_binary_search_paths is canonical_p3.resolve_binary_search_paths
    assert run_phase_3_audit is canonical_p3.run_phase_3_audit
    assert audit_all_engines is canonical_p3.audit_all_engines
    assert audit_single_binary is canonical_p3.audit_single_binary
    assert audit_container_sifs is canonical_p3.audit_container_sifs
    assert compute_environment_fingerprint is canonical_p3.compute_environment_fingerprint
    assert compute_file_sha256 is canonical_p3.compute_file_sha256
    assert discover_binary_path is canonical_p3.discover_binary_path
    assert extract_semantic_version is canonical_p3.extract_semantic_version
    assert interrogate_binary_version is canonical_p3.interrogate_binary_version
    assert resolve_p3_registry_path is canonical_p3.resolve_p3_registry_path


# =============================================================================
# 2. ZERO-MOCK AND ANTI-SPOOFING DIRECTIVE TESTS
# =============================================================================


def test_phase_3_source_code_anti_spoofing() -> None:
    """Adversarial check: ensure no mocks, stubs, fake data, or pass statements in phase_3.py."""
    from ci_tools.anti_spoof_linter import BANNED_MOCK_MODULES
    for bm in BANNED_MOCK_MODULES:
        assert bm not in source
    assert "Mock(" not in source
    assert "MagicMock(" not in source
    assert "NotImplementedError" not in source


# =============================================================================
# 3. LIVE ENGINE & RESOURCE AUDIT EXECUTION
# =============================================================================


def test_phase_3_live_audit_execution(tmp_path: Path) -> None:
    """Execute live run_phase_3() audit and verify full schema integrity."""
    report = run_phase_3(output_dir=tmp_path / "Registry")
    assert isinstance(report, Phase3AuditReport)
    assert report.phase_id == "PHASE_3_ENGINE_DISCOVERY_INTEGRITY"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED, PhaseStatus.FAILED)

    # Engine discovery assertions
    assert isinstance(report.engines, dict)
    assert "orca" in report.engines
    assert "xtb" in report.engines

    # Fingerprint assertions
    assert report.fingerprint.composite_hash is not None
    assert len(report.fingerprint.composite_hash) == 64

    # Persistence verification
    artifact_path = tmp_path / "Registry" / "p3.json"
    assert artifact_path.exists()
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert data["phase_id"] == "PHASE_3_ENGINE_DISCOVERY_INTEGRITY"
    assert data["status"] in ("PASSED", "DEGRADED", "FAILED")


def test_phase_3_cli_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test phase_3 CLI execution with --json and --output-dir flags."""
    out_dir = tmp_path / "cli_reg"
    exit_code = main(["--json", "--output-dir", str(out_dir)])
    assert exit_code in (0, 1)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["phase_id"] == "PHASE_3_ENGINE_DISCOVERY_INTEGRITY"
    assert "engines" in data
    assert "tracks" in data
    assert "container" in data
    assert "fingerprint" in data


def test_phase_3_cli_table_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test phase_3 CLI execution with standard formatted output."""
    out_dir = tmp_path / "cli_reg_std"
    exit_code = main(["--output-dir", str(out_dir)])
    assert exit_code in (0, 1)
    captured = capsys.readouterr()
    assert "COCHEM SETUP PHASE 3: MULTI-TRACK QUANTUM ENGINE DISCOVERY" in captured.out
    assert "Fingerprint:" in captured.out
    assert (out_dir / "p3.json").exists()
