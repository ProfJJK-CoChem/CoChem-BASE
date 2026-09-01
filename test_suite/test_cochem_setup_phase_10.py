"""
Unit test suite for CoChem Setup Phase 10: MolSym Intake, Theoretical Eckart Frame Alignment,
State-Chain Recovery & Ephemeral Quarantined Sandbox Verifier.
Strict Zero-Mock Mandate: Real MolSym isolated silo audit, real Center of Mass translation
with ghost atom (BSSE Gh, Bq, X) zero-mass protections, real Moment of Inertia tensor construction
and diagonalization, NIST CODATA 2022/2026 rotational constants (MHz, GHz, cm^-1), Ray's asymmetry
parameter kappa, planar moments, rotor top classification, real mass-weighted Eckart frame alignment
(translational and rotational Eckart residual norms <= 1e-12), real ephemeral sandbox scaffolding,
real 10 MB unbuffered storage IOPS benchmark, real ORCA (.gbw), PySCF (.chk), and xTB (.xtbw)
checkpoint validation, real state-chain continuity verification across p1.json through p9.json,
real environment variable injection mappings, and transactional atomic state persistence into p10.json.

SRS Document 2 Part 2 (Section 3.10), Method Matrix v4 (§8A-8C), SRS Document 1 (Section 2),
SRS Document 5 (Section 1-4), SRS Document 6 (Section 1-3), SRS Document 7 (Section 2),
and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import tempfile
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_10 import (
    CheckpointFormat,
    CheckpointStatus,
    CheckpointValidationError,
    CheckpointValidationReport,
    DependencyManager,
    EckartAlignmentError,
    EckartAlignmentResult,
    EckartVerificationItem,
    EckartVerificationReport,
    EckartVerificationStatus,
    EphemeralSandboxError,
    EphemeralSandboxProfile,
    InertiaTensorError,
    InertiaTensorResult,
    IOPSBenchmarkError,
    IOPSBenchmarkProfile,
    IOPSBenchmarkStatus,
    MolSymSiloError,
    MolSymSiloProfile,
    MolSymSiloStatus,
    Phase10AuditError,
    Phase10AuditReport,
    PhaseStatus,
    RotorTopType,
    StateChainRecoveryError,
    StateChainRecoveryProfile,
    _generate_3d_rotation_matrix,
    align_to_eckart_frame,
    align_to_principal_axes,
    audit_or_provision_molsym_silo,
    audit_state_chain_recovery,
    cleanup_ephemeral_sandbox,
    compute_center_of_mass,
    compute_file_sha256,
    compute_moment_of_inertia_tensor,
    diagonalize_inertia_tensor,
    generate_environment_injection_dict,
    get_physical_mass,
    is_ghost_symbol,
    main,
    resolve_sandbox_base_directory,
    run_phase_10_audit,
    run_theoretical_eckart_benchmarks,
    run_unbuffered_iops_benchmark,
    scaffold_ephemeral_sandbox,
    scan_and_validate_checkpoints,
    translate_to_center_of_mass,
    validate_orca_gbw_checkpoint,
    validate_pyscf_chk_checkpoint,
    validate_xtb_xtbw_checkpoint,
)

try:
    import h5py
    _HAS_H5PY = True
except ImportError:
    h5py = None  # type: ignore
    _HAS_H5PY = False


def make_temp_dir() -> tempfile.TemporaryDirectory:
    """Create a temporary directory with Windows cleanup resilience."""
    if hasattr(tempfile.TemporaryDirectory, "_ignore_cleanup_errors") or platform.system() == "Windows":
        try:
            return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            pass
    return tempfile.TemporaryDirectory()


# =============================================================================
# Authentic Molecular Test Structures
# =============================================================================

# 1. Water (H2O) - Planar asymmetric top (C2v)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.000000,  0.000000,  0.117300],
    [0.000000,  0.757200, -0.469200],
    [0.000000, -0.757200, -0.469200],
], dtype=np.float64)

# 2. Carbon Dioxide (CO2) - Linear molecule (Dinfh)
CO2_SYMBOLS = ["C", "O", "O"]
CO2_COORDS = np.array([
    [0.000000, 0.000000,  0.000000],
    [0.000000, 0.000000,  1.160000],
    [0.000000, 0.000000, -1.160000],
], dtype=np.float64)

# 3. Methane (CH4) - Spherical top (Td)
CH4_SYMBOLS = ["C", "H", "H", "H", "H"]
CH4_COORDS = np.array([
    [ 0.000000,  0.000000,  0.000000],
    [ 0.629118,  0.629118,  0.629118],
    [-0.629118, -0.629118,  0.629118],
    [ 0.629118, -0.629118, -0.629118],
    [-0.629118,  0.629118, -0.629118],
], dtype=np.float64)

# 4. Benzene (C6H6) - Planar oblate symmetric top (D6h)
BENZENE_SYMBOLS = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
BENZENE_COORDS = np.array([
    [ 0.000000,  1.397000, 0.000000],
    [ 1.209838,  0.698500, 0.000000],
    [ 1.209838, -0.698500, 0.000000],
    [ 0.000000, -1.397000, 0.000000],
    [-1.209838, -0.698500, 0.000000],
    [-1.209838,  0.698500, 0.000000],
    [ 0.000000,  2.481000, 0.000000],
    [ 2.148608,  1.240500, 0.000000],
    [ 2.148608, -1.240500, 0.000000],
    [ 0.000000, -2.481000, 0.000000],
    [-2.148608, -1.240500, 0.000000],
    [-2.148608,  1.240500, 0.000000],
], dtype=np.float64)

# 5. Methyl Chloride (CH3Cl) - Prolate symmetric top (C3v)
CH3CL_SYMBOLS = ["C", "Cl", "H", "H", "H"]
CH3CL_COORDS = np.array([
    [0.000000,  0.000000, -1.100000],
    [0.000000,  0.000000,  0.680000],
    [0.000000,  1.030000, -1.450000],
    [0.892000, -0.515000, -1.450000],
    [-0.892000, -0.515000, -1.450000],
], dtype=np.float64)

# 6. Water Dimer BSSE Complex
WATER_DIMER_SYMBOLS = ["GhO", "GhH", "GhH", "O", "H", "H"]
WATER_DIMER_COORDS = np.array([
    [-1.487000,  0.018000, -0.098000],
    [-0.518000,  0.063000, -0.013000],
    [-1.802000, -0.738000,  0.404000],
    [ 1.428000, -0.003000,  0.076000],
    [ 1.758000,  0.771000, -0.380000],
    [ 1.777000, -0.760000, -0.392000],
], dtype=np.float64)


# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 10 exception classes inherit from Phase10AuditError and RuntimeError."""
    err1 = Phase10AuditError("Phase 10 fatal error")
    assert isinstance(err1, RuntimeError)

    err2 = EphemeralSandboxError("Ephemeral sandbox error")
    assert isinstance(err2, Phase10AuditError)

    err3 = IOPSBenchmarkError("IOPS benchmark error")
    assert isinstance(err3, Phase10AuditError)

    err4 = CheckpointValidationError("Checkpoint validation error")
    assert isinstance(err4, Phase10AuditError)

    err5 = StateChainRecoveryError("State-chain recovery error")
    assert isinstance(err5, Phase10AuditError)

    err6 = MolSymSiloError("MolSym silo error")
    assert isinstance(err6, Phase10AuditError)

    err7 = EckartAlignmentError("Eckart alignment error")
    assert isinstance(err7, Phase10AuditError)

    err8 = InertiaTensorError("Inertia tensor error")
    assert isinstance(err8, Phase10AuditError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"


def test_molsym_and_eckart_enums() -> None:
    """Verify MolSymSiloStatus, EckartVerificationStatus, and RotorTopType enum values."""
    assert MolSymSiloStatus.AVAILABLE.value == "AVAILABLE"
    assert MolSymSiloStatus.PROVISIONED.value == "PROVISIONED"
    assert MolSymSiloStatus.DEGRADED.value == "DEGRADED"
    assert MolSymSiloStatus.NOT_FOUND.value == "NOT_FOUND"

    assert EckartVerificationStatus.VERIFIED.value == "VERIFIED"
    assert EckartVerificationStatus.FAILED.value == "FAILED"

    assert RotorTopType.SPHERICAL.value == "spherical"
    assert RotorTopType.SYMMETRIC_PROLATE.value == "symmetric_prolate"
    assert RotorTopType.SYMMETRIC_OBLATE.value == "symmetric_oblate"
    assert RotorTopType.ASYMMETRIC.value == "asymmetric"
    assert RotorTopType.LINEAR.value == "linear"
    assert RotorTopType.ATOM.value == "atom"


# =============================================================================
# 2. PYDANTIC V2 MODEL VALIDATION TESTS
# =============================================================================


def test_molsym_silo_profile_model() -> None:
    """Verify MolSymSiloProfile validation and serialization."""
    prof = MolSymSiloProfile(
        silo_path="/opt/cochem/silos/molsym",
        is_installed=True,
        silo_status=MolSymSiloStatus.AVAILABLE,
        version="1.2.0",
        location="/opt/cochem/silos/molsym/molsym",
        has_symtext=True,
        has_find_point_group=True,
        notes="Verified operational",
    )
    assert prof.is_installed is True
    assert prof.has_symtext is True

    dump = prof.model_dump()
    assert dump["silo_status"] == "AVAILABLE"

    with pytest.raises(ValidationError):
        MolSymSiloProfile(
            is_installed=True,
            silo_status=MolSymSiloStatus.AVAILABLE,
            unauthorized_field="forbidden",  # type: ignore
        )


def test_inertia_tensor_result_model() -> None:
    """Verify InertiaTensorResult validation and serialization."""
    res = InertiaTensorResult(
        eigenvalues_amu_angstrom2=(1.0, 2.0, 3.0),
        rotational_constants_mhz=(500000.0, 250000.0, 166666.7),
        rotational_constants_ghz=(500.0, 250.0, 166.7),
        rotational_constants_cm1=(16.8, 8.4, 5.6),
        inertial_defect=0.0,
        rays_kappa=0.0,
        planar_moments=(2.0, 1.0, 0.0),
        top_type=RotorTopType.ASYMMETRIC,
        rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        aligned_coords=[[0.0, 0.0, 0.0]],
        inertia_tensor=[[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]],
    )
    assert res.top_type == RotorTopType.ASYMMETRIC
    assert res.inertial_defect == 0.0

    raw_json = res.model_dump_json()
    reloaded = InertiaTensorResult.model_validate_json(raw_json)
    assert reloaded.top_type == RotorTopType.ASYMMETRIC


def test_eckart_alignment_models() -> None:
    """Verify EckartAlignmentResult, EckartVerificationItem, and EckartVerificationReport models."""
    align_res = EckartAlignmentResult(
        aligned_coords=[[0.0, 0.0, 0.0]],
        rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        rmsd=0.0,
        residual_rotational_norm=1e-15,
        translational_residual_norm=1e-15,
        rotation_determinant=1.0,
    )
    assert align_res.rmsd == 0.0
    assert align_res.rotation_determinant == 1.0

    item = EckartVerificationItem(
        benchmark_name="H2O_Test",
        status=EckartVerificationStatus.VERIFIED,
        n_atoms=3,
        has_ghost_atoms=False,
        translational_residual_norm=1e-15,
        rotational_residual_norm=1e-15,
        rotation_determinant=1.0,
        rmsd=1e-15,
        top_type=RotorTopType.ASYMMETRIC,
        is_verified=True,
    )
    assert item.is_verified is True

    rep = EckartVerificationReport(
        total_benchmarks=1,
        passed_benchmarks=1,
        failed_benchmarks=0,
        overall_status=EckartVerificationStatus.VERIFIED,
        max_translational_residual=1e-15,
        max_rotational_residual=1e-15,
        items=[item],
    )
    assert rep.overall_status == EckartVerificationStatus.VERIFIED


def test_phase_10_audit_report_model() -> None:
    """Verify Phase10AuditReport complete model serialization with alignment fields."""
    sb = EphemeralSandboxProfile(
        sandbox_path="/tmp/cochem_exec_123",
        sandbox_uuid="123",
        base_directory="/tmp",
        is_created=True,
        is_writable=True,
        is_isolated=True,
        permissions_octal="0o700",
        cleanup_verified=True,
        active_pid=os.getpid(),
    )
    iops = IOPSBenchmarkProfile(
        target_directory="/tmp/cochem_exec_123",
        file_size_bytes=10485760,
        block_size_bytes=65536,
        total_blocks=160,
        write_duration_seconds=0.05,
        write_throughput_mb_s=200.0,
        write_iops=3200.0,
        read_duration_seconds=0.04,
        read_throughput_mb_s=250.0,
        read_iops=4000.0,
        sync_latency_ms=1.0,
        status=IOPSBenchmarkStatus.OPTIMAL,
        is_unbuffered=True,
        is_performance_sufficient=True,
    )
    chk = CheckpointValidationReport(
        scanned_count=0,
        valid_count=0,
        corrupt_count=0,
        resumable_checkpoints=[],
        validation_enabled=True,
    )
    sc = StateChainRecoveryProfile(
        registry_directory="/Registry",
        verified_phases=["p1", "p2"],
        missing_phases=[],
        chain_intact=True,
        recoverable_jobs=[],
        orphaned_sandboxes=[],
    )
    ms = MolSymSiloProfile(
        silo_path=None,
        is_installed=True,
        silo_status=MolSymSiloStatus.AVAILABLE,
        version="1.0.0",
        location="/env/molsym",
        has_symtext=True,
        has_find_point_group=True,
        notes="OK",
    )
    ev = EckartVerificationReport(
        total_benchmarks=1,
        passed_benchmarks=1,
        failed_benchmarks=0,
        overall_status=EckartVerificationStatus.VERIFIED,
        max_translational_residual=1e-15,
        max_rotational_residual=1e-15,
        items=[],
    )

    report = Phase10AuditReport(
        phase_id="cochem_setup_phase_10",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-22T00:00:00Z",
        artifact_path="/Registry/p10.json",
        sandbox_profile=sb,
        iops_profile=iops,
        checkpoint_report=chk,
        state_chain_profile=sc,
        molsym_silo_profile=ms,
        eckart_verification_report=ev,
        alignment_engine_ready=True,
        injected_env_vars={"COCHEM_ALIGNMENT_ENGINE_READY": "1"},
        warnings=[],
        errors=[],
    )
    assert report.alignment_engine_ready is True
    assert report.status == PhaseStatus.PASSED

    raw_json = report.model_dump_json(indent=2)
    parsed = json.loads(raw_json)
    assert parsed["alignment_engine_ready"] is True
    assert parsed["molsym_silo_profile"]["silo_status"] == "AVAILABLE"


# =============================================================================
# 3. MOLSYM ISOLATED SILO ENGINE TESTS
# =============================================================================


def test_audit_or_provision_molsym_silo() -> None:
    """Test MolSym silo discovery and inspection."""
    profile = audit_or_provision_molsym_silo()
    assert isinstance(profile, MolSymSiloProfile)
    assert profile.silo_status in (
        MolSymSiloStatus.AVAILABLE,
        MolSymSiloStatus.PROVISIONED,
        MolSymSiloStatus.DEGRADED,
        MolSymSiloStatus.NOT_FOUND,
    )
    if profile.is_installed:
        assert profile.has_symtext is True
        assert profile.has_find_point_group is True


def test_audit_or_provision_molsym_silo_custom_path() -> None:
    """Test MolSym silo audit with custom directory path."""
    with make_temp_dir() as td:
        silo_dir = Path(td) / "custom_molsym_silo"
        silo_dir.mkdir()

        profile = audit_or_provision_molsym_silo(silo_path=silo_dir)
        assert isinstance(profile, MolSymSiloProfile)


# =============================================================================
# 4. THEORETICAL CENTER OF MASS & GHOST ATOM TESTS
# =============================================================================


def test_is_ghost_symbol() -> None:
    """Verify recognition of ghost atom symbols and physical elements."""
    assert is_ghost_symbol("Gh") is True
    assert is_ghost_symbol("gh") is True
    assert is_ghost_symbol("GhO") is True
    assert is_ghost_symbol("Gh_C") is True
    assert is_ghost_symbol("Bq") is True
    assert is_ghost_symbol("bq") is True
    assert is_ghost_symbol("X") is True
    assert is_ghost_symbol("x_N") is True
    assert is_ghost_symbol("x-O") is True

    # Physical element Xenon must NEVER be classified as ghost
    assert is_ghost_symbol("Xe") is False
    assert is_ghost_symbol("xe") is False
    assert is_ghost_symbol("XE") is False
    assert is_ghost_symbol("C") is False
    assert is_ghost_symbol("H") is False
    assert is_ghost_symbol("O") is False


def test_get_physical_mass() -> None:
    """Verify standard atomic weights and zero ghost mass."""
    assert get_physical_mass("H") == pytest.approx(1.008, rel=1e-2)
    assert get_physical_mass("C") == pytest.approx(12.011, rel=1e-2)
    assert get_physical_mass("N") == pytest.approx(14.007, rel=1e-2)
    assert get_physical_mass("O") == pytest.approx(15.999, rel=1e-2)
    assert get_physical_mass("Xe") == pytest.approx(131.293, rel=1e-2)

    assert get_physical_mass("Gh") == 0.0
    assert get_physical_mass("GhO") == 0.0
    assert get_physical_mass("Bq") == 0.0
    assert get_physical_mass("X") == 0.0

    with pytest.raises(ValueError):
        get_physical_mass("InvalidElementSymbolXYZ")


def test_center_of_mass_translation_water() -> None:
    """Verify exact Center of Mass translation for Water with residual sum(m_i * r'_i) < 1e-14."""
    masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
    offset = np.array([42.123, -88.654, 105.789], dtype=np.float64)
    shifted_coords = WATER_COORDS + offset

    com = compute_center_of_mass(shifted_coords, masses=masses)
    np.testing.assert_allclose(com, np.sum(shifted_coords * masses[:, None], axis=0) / np.sum(masses), atol=1e-14)

    translated_coords, shift_vec = translate_to_center_of_mass(shifted_coords, masses=masses)

    # Center of mass of translated coordinates must be (0, 0, 0)
    new_com = compute_center_of_mass(translated_coords, masses=masses)
    np.testing.assert_allclose(new_com, [0.0, 0.0, 0.0], atol=1e-14)

    # Mass-weighted sum must be zero
    mass_sum = np.sum(masses[:, None] * translated_coords, axis=0)
    np.testing.assert_allclose(mass_sum, [0.0, 0.0, 0.0], atol=1e-14)

    # Pairwise distances must be identically preserved
    d_orig = np.linalg.norm(shifted_coords[:, None, :] - shifted_coords[None, :, :], axis=-1)
    d_trans = np.linalg.norm(translated_coords[:, None, :] - translated_coords[None, :, :], axis=-1)
    np.testing.assert_allclose(d_trans, d_orig, atol=1e-14)


def test_ghost_atom_bsse_protection() -> None:
    """Verify ghost atoms (mass=0.0) do not shift Center of Mass in BSSE complex."""
    # Water Dimer with Monomer A ghosted
    ghost_symbols = ["GhO", "GhH", "GhH", "O", "H", "H"]
    com_dimer = compute_center_of_mass(WATER_DIMER_COORDS, symbols=ghost_symbols)

    # Monomer B COM alone
    monomer_b_coords = WATER_DIMER_COORDS[3:6]
    monomer_b_symbols = ["O", "H", "H"]
    com_monomer_b = compute_center_of_mass(monomer_b_coords, symbols=monomer_b_symbols)

    np.testing.assert_allclose(com_dimer, com_monomer_b, atol=1e-14)

    trans_coords, _ = translate_to_center_of_mass(WATER_DIMER_COORDS, symbols=ghost_symbols)
    trans_monomer_b_com = compute_center_of_mass(trans_coords[3:6], symbols=monomer_b_symbols)
    np.testing.assert_allclose(trans_monomer_b_com, [0.0, 0.0, 0.0], atol=1e-14)


# =============================================================================
# 5. MOMENT OF INERTIA & ROTATIONAL CONSTANTS TESTS
# =============================================================================


def test_moment_of_inertia_tensor_and_diagonalization() -> None:
    """Verify 3x3 symmetric inertia tensor construction and diagonalization."""
    masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
    translated_coords, _ = translate_to_center_of_mass(WATER_COORDS, masses=masses)

    I_tensor = compute_moment_of_inertia_tensor(translated_coords, masses)
    np.testing.assert_allclose(I_tensor, I_tensor.T, atol=1e-15)

    eigvals, V = diagonalize_inertia_tensor(I_tensor)
    assert eigvals[0] <= eigvals[1] <= eigvals[2]
    np.testing.assert_allclose(np.linalg.det(V), 1.0, atol=1e-12)


def test_rotational_constants_and_top_classification() -> None:
    """Verify CODATA conversion and rotor top classification across diverse molecules."""
    # 1. Water (Planar Asymmetric Top)
    masses_water = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
    res_water = align_to_principal_axes(WATER_COORDS, masses=masses_water)
    assert res_water.top_type == RotorTopType.ASYMMETRIC
    np.testing.assert_allclose(res_water.inertial_defect, 0.0, atol=1e-10)
    assert -1.0 < res_water.rays_kappa < 1.0
    assert res_water.rotational_constants_mhz[0] is not None
    assert res_water.rotational_constants_mhz[0] > res_water.rotational_constants_mhz[1]

    # 2. Carbon Dioxide (Linear Molecule Singularity)
    masses_co2 = np.array([get_physical_mass(s) for s in CO2_SYMBOLS], dtype=np.float64)
    res_co2 = align_to_principal_axes(CO2_COORDS, masses=masses_co2)
    assert res_co2.top_type == RotorTopType.LINEAR
    assert math.isinf(res_co2.rotational_constants_mhz[0]) or res_co2.rotational_constants_mhz[0] is None
    np.testing.assert_allclose(res_co2.rays_kappa, -1.0, atol=1e-4)

    # 3. Methane (Spherical Top)
    masses_ch4 = np.array([get_physical_mass(s) for s in CH4_SYMBOLS], dtype=np.float64)
    res_ch4 = align_to_principal_axes(CH4_COORDS, masses=masses_ch4)
    assert res_ch4.top_type == RotorTopType.SPHERICAL
    np.testing.assert_allclose(res_ch4.eigenvalues_amu_angstrom2[0], res_ch4.eigenvalues_amu_angstrom2[1], rtol=1e-4)
    np.testing.assert_allclose(res_ch4.eigenvalues_amu_angstrom2[1], res_ch4.eigenvalues_amu_angstrom2[2], rtol=1e-4)

    # 4. Benzene (Oblate Symmetric Top)
    masses_c6h6 = np.array([get_physical_mass(s) for s in BENZENE_SYMBOLS], dtype=np.float64)
    res_c6h6 = align_to_principal_axes(BENZENE_COORDS, masses=masses_c6h6)
    assert res_c6h6.top_type == RotorTopType.SYMMETRIC_OBLATE
    np.testing.assert_allclose(res_c6h6.inertial_defect, 0.0, atol=1e-10)
    np.testing.assert_allclose(res_c6h6.rays_kappa, 1.0, atol=1e-4)

    # 5. Methyl Chloride (Prolate Symmetric Top)
    masses_ch3cl = np.array([get_physical_mass(s) for s in CH3CL_SYMBOLS], dtype=np.float64)
    res_ch3cl = align_to_principal_axes(CH3CL_COORDS, masses=masses_ch3cl)
    assert res_ch3cl.top_type == RotorTopType.SYMMETRIC_PROLATE
    np.testing.assert_allclose(res_ch3cl.rays_kappa, -1.0, atol=1e-4)


# =============================================================================
# 6. ECKART FRAME ALIGNMENT & THEORETICAL BENCHMARK TESTS
# =============================================================================


def test_eckart_alignment_water_rigid_rotation() -> None:
    """Verify Eckart alignment on rigidly rotated Water with residual norms < 1e-12."""
    masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
    ref_coords = WATER_COORDS.copy()

    R_rand = _generate_3d_rotation_matrix(0.85, 1.42, 2.77)
    t_rand = np.array([-15.2, 33.7, -9.4], dtype=np.float64)
    target_coords = ref_coords @ R_rand.T + t_rand

    res = align_to_eckart_frame(target_coords, ref_coords, masses=masses)

    assert res.rmsd < 1e-12
    assert res.translational_residual_norm < 1e-12
    assert res.residual_rotational_norm < 1e-12
    np.testing.assert_allclose(res.rotation_determinant, 1.0, atol=1e-12)


def test_eckart_alignment_perturbed_water() -> None:
    """Verify Eckart alignment on deformed Water conformation satisfying Eckart conditions."""
    masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
    ref_coords = WATER_COORDS.copy()

    perturbed = WATER_COORDS.copy()
    perturbed[1, 1] += 0.05
    perturbed[2, 1] -= 0.03
    perturbed[1, 2] += 0.02

    R_rand = _generate_3d_rotation_matrix(1.1, 0.7, 1.9)
    target_coords = perturbed @ R_rand.T + np.array([10.0, -10.0, 5.0])

    res = align_to_eckart_frame(target_coords, ref_coords, masses=masses)

    assert res.translational_residual_norm < 1e-12
    assert res.residual_rotational_norm < 1e-12
    np.testing.assert_allclose(res.rotation_determinant, 1.0, atol=1e-12)

    # Internal pairwise distances preserved
    d_target = np.linalg.norm(target_coords[:, None, :] - target_coords[None, :, :], axis=-1)
    d_aligned = np.linalg.norm(np.array(res.aligned_coords)[:, None, :] - np.array(res.aligned_coords)[None, :, :], axis=-1)
    np.testing.assert_allclose(d_aligned, d_target, atol=1e-12)


def test_eckart_svd_reflection_protection() -> None:
    """Verify proper rotation enforcement det(U) = +1.0 even under improper reflection."""
    masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
    ref_coords = WATER_COORDS.copy()

    reflected_target = ref_coords.copy()
    reflected_target[:, 0] = -reflected_target[:, 0]

    res = align_to_eckart_frame(reflected_target, ref_coords, masses=masses)
    np.testing.assert_allclose(res.rotation_determinant, 1.0, atol=1e-12)


def test_run_theoretical_eckart_benchmarks_suite() -> None:
    """Verify execution of full theoretical Eckart benchmark suite."""
    report = run_theoretical_eckart_benchmarks(tolerance=1e-12)
    assert report.total_benchmarks >= 5
    assert report.passed_benchmarks == report.total_benchmarks
    assert report.failed_benchmarks == 0
    assert report.overall_status == EckartVerificationStatus.VERIFIED
    assert report.max_translational_residual < 1e-12
    assert report.max_rotational_residual < 1e-12


# =============================================================================
# 7. EPHEMERAL SANDBOX ENGINE TESTS
# =============================================================================


def test_resolve_sandbox_base_directory() -> None:
    """Test resolution of sandbox base directory under various environments."""
    with make_temp_dir() as td:
        resolved = resolve_sandbox_base_directory(custom_dir=td)
        assert resolved == Path(td).resolve()

        env = {"COCHEM_SANDBOX_BASE": td}
        resolved_env = resolve_sandbox_base_directory(env=env)
        assert resolved_env == Path(td).resolve()

        resolved_def = resolve_sandbox_base_directory()
        assert resolved_def.exists()


def test_scaffold_ephemeral_sandbox_and_cleanup() -> None:
    """Test real scaffolding of ephemeral sandbox with isolation sentinel and cleanup."""
    with make_temp_dir() as td:
        custom_uuid = "test_uuid_abcdef12"
        profile = scaffold_ephemeral_sandbox(base_dir=td, custom_uuid=custom_uuid)

        assert profile.is_created is True
        assert profile.is_writable is True
        assert profile.is_isolated is True
        assert profile.sandbox_uuid == custom_uuid
        assert Path(profile.sandbox_path).exists()
        assert profile.active_pid == os.getpid()

        test_file = Path(profile.sandbox_path) / "test_calc.inp"
        test_file.write_text("! B3LYP def2-SVP Opt\n* xyz 0 1\nO 0.0 0.0 0.0\n*\n", encoding="utf-8")
        assert test_file.exists()

        cleaned = cleanup_ephemeral_sandbox(profile.sandbox_path)
        assert cleaned is True
        assert not Path(profile.sandbox_path).exists()
        assert cleanup_ephemeral_sandbox(profile.sandbox_path) is True


# =============================================================================
# 8. 10 MB UNBUFFERED IOPS BENCHMARK TESTS
# =============================================================================


def test_run_unbuffered_iops_benchmark() -> None:
    """Test executing real unbuffered IOPS benchmark in temporary directory."""
    with make_temp_dir() as td:
        prof = run_unbuffered_iops_benchmark(target_dir=td, file_size_mb=2.0, block_size_kb=64)

        assert prof.file_size_bytes == 2 * 1024 * 1024
        assert prof.block_size_bytes == 64 * 1024
        assert prof.total_blocks == 32
        assert prof.write_duration_seconds > 0.0
        assert prof.write_throughput_mb_s > 0.0
        assert prof.write_iops > 0.0
        assert prof.read_duration_seconds > 0.0
        assert prof.read_throughput_mb_s > 0.0
        assert prof.read_iops > 0.0
        assert prof.sync_latency_ms >= 0.0
        assert prof.is_unbuffered is True
        assert prof.status in (
            IOPSBenchmarkStatus.OPTIMAL,
            IOPSBenchmarkStatus.ACCEPTABLE,
            IOPSBenchmarkStatus.DEGRADED,
        )


# =============================================================================
# 9. QUANTUM CHECKPOINT VALIDATION TESTS
# =============================================================================


def test_compute_file_sha256() -> None:
    """Test cryptographic SHA-256 calculation."""
    with make_temp_dir() as td:
        f_path = Path(td) / "sample.bin"
        payload = b"ORCA_BINARY_WAVEFUNCTION_COEFFICIENTS_2026"
        f_path.write_bytes(payload)

        expected = hashlib.sha256(payload).hexdigest()
        actual = compute_file_sha256(f_path)
        assert actual == expected


def test_validate_orca_gbw_checkpoint() -> None:
    """Test validation of real ORCA .gbw binary checkpoint file."""
    with make_temp_dir() as td:
        valid_gbw = Path(td) / "water_opt.gbw"
        gbw_data = b"ORCA-GBW-BINARY-V6.1.1\x00\x01" + b"\x00" * 200
        valid_gbw.write_bytes(gbw_data)

        item_valid = validate_orca_gbw_checkpoint(valid_gbw)
        assert item_valid.format == CheckpointFormat.ORCA_GBW
        assert item_valid.status == CheckpointStatus.VALID
        assert item_valid.is_resumable is True
        assert item_valid.size_bytes == len(gbw_data)

        trunc_gbw = Path(td) / "empty.gbw"
        trunc_gbw.write_bytes(b"")
        item_trunc = validate_orca_gbw_checkpoint(trunc_gbw)
        assert item_trunc.status == CheckpointStatus.TRUNCATED


def test_validate_pyscf_chk_checkpoint() -> None:
    """Test validation of real PySCF .chk HDF5 checkpoint file."""
    with make_temp_dir() as td:
        chk_path = Path(td) / "pyscf_mol.chk"

        if _HAS_H5PY and h5py is not None:
            with h5py.File(str(chk_path), "w") as h5:
                scf_grp = h5.create_group("scf")
                scf_grp.create_dataset("e_tot", data=-76.4215)
                h5.create_group("mol")

            item = validate_pyscf_chk_checkpoint(chk_path)
            assert item.format == CheckpointFormat.PYSCF_CHK
            assert item.status == CheckpointStatus.VALID
            assert item.is_resumable is True
        else:
            chk_path.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 100)
            item = validate_pyscf_chk_checkpoint(chk_path)
            assert item.format == CheckpointFormat.PYSCF_CHK
            assert item.status == CheckpointStatus.VALID


def test_validate_xtb_xtbw_checkpoint() -> None:
    """Test validation of xTB restart file (.xtbw)."""
    with make_temp_dir() as td:
        xtbw_path = Path(td) / "xtb_restart.xtbw"
        xtbw_path.write_bytes(b"XTB-RESTART-CHARGES-MULTIPOLE\x00\x01\x02\x03")

        item = validate_xtb_xtbw_checkpoint(xtbw_path)
        assert item.format == CheckpointFormat.XTB_XTBW
        assert item.status == CheckpointStatus.VALID
        assert item.is_resumable is True


def test_scan_and_validate_checkpoints() -> None:
    """Test directory scanning and aggregate reporting."""
    with make_temp_dir() as td:
        d1 = Path(td) / "dir1"
        d1.mkdir()
        (d1 / "job1.gbw").write_bytes(b"ORCA_BINARY_DATA_" + b"\x00" * 100)
        (d1 / "job2_corrupt.gbw").write_bytes(b"")

        report = scan_and_validate_checkpoints([d1])
        assert report.scanned_count == 2
        assert report.valid_count == 1
        assert report.corrupt_count == 1


# =============================================================================
# 10. STATE-CHAIN CONTINUITY & RECOVERY TESTS
# =============================================================================


def test_audit_state_chain_recovery_all_present() -> None:
    """Test state-chain recovery when all previous phases p1-p9 exist."""
    with make_temp_dir() as td:
        reg_dir = Path(td) / "Registry"
        reg_dir.mkdir()

        for i in range(1, 10):
            p_file = reg_dir / f"p{i}.json"
            p_file.write_text(json.dumps({"phase_id": f"cochem_setup_phase_{i}", "status": "PASSED"}), encoding="utf-8")

        s_base = Path(td) / "sandboxes"
        s_base.mkdir()
        orphaned = s_base / "cochem_exec_interrupted_job"
        orphaned.mkdir()
        (orphaned / "resume.gbw").write_bytes(b"ORCA_BINARY_RESTART_" + b"\x00" * 100)

        sc = audit_state_chain_recovery(registry_dir=reg_dir, sandbox_base_dir=s_base)

        assert sc.chain_intact is True
        assert len(sc.verified_phases) == 9
        assert len(sc.missing_phases) == 0
        assert len(sc.orphaned_sandboxes) == 1
        assert len(sc.recoverable_jobs) == 1


# =============================================================================
# 11. ENVIRONMENT INJECTION & DEPENDENCY MANAGER TESTS
# =============================================================================


def test_generate_environment_injection_dict() -> None:
    """Test environment variable injection generation with MolSym and Eckart flags."""
    sb = EphemeralSandboxProfile(
        sandbox_path="/tmp/cochem_exec_xyz",
        sandbox_uuid="xyz",
        base_directory="/tmp",
        is_created=True,
        is_writable=True,
        is_isolated=True,
        permissions_octal="0o700",
        cleanup_verified=True,
        active_pid=os.getpid(),
    )
    iops = IOPSBenchmarkProfile(
        target_directory="/tmp/cochem_exec_xyz",
        file_size_bytes=10485760,
        block_size_bytes=65536,
        total_blocks=160,
        write_duration_seconds=0.05,
        write_throughput_mb_s=200.0,
        write_iops=3200.0,
        read_duration_seconds=0.04,
        read_throughput_mb_s=250.0,
        read_iops=4000.0,
        sync_latency_ms=1.0,
        status=IOPSBenchmarkStatus.OPTIMAL,
        is_unbuffered=True,
        is_performance_sufficient=True,
    )
    chk = CheckpointValidationReport(
        scanned_count=2,
        valid_count=2,
        corrupt_count=0,
        resumable_checkpoints=[],
        validation_enabled=True,
    )
    sc = StateChainRecoveryProfile(
        registry_directory="/Registry",
        verified_phases=["p1", "p2"],
        missing_phases=[],
        chain_intact=True,
        recoverable_jobs=[],
        orphaned_sandboxes=[],
    )
    ms = MolSymSiloProfile(
        silo_path=None,
        is_installed=True,
        silo_status=MolSymSiloStatus.AVAILABLE,
        version="1.0",
        location="/loc",
        has_symtext=True,
        has_find_point_group=True,
        notes="OK",
    )
    ev = EckartVerificationReport(
        total_benchmarks=5,
        passed_benchmarks=5,
        failed_benchmarks=0,
        overall_status=EckartVerificationStatus.VERIFIED,
        max_translational_residual=1e-15,
        max_rotational_residual=1e-15,
        items=[],
    )

    env_vars = generate_environment_injection_dict(sb, iops, chk, sc, ms, ev, alignment_ready=True)
    assert env_vars["COCHEM_EPHEMERAL_SANDBOX"] == "/tmp/cochem_exec_xyz"
    assert env_vars["COCHEM_MOLSYM_SILO_STATUS"] == "AVAILABLE"
    assert env_vars["COCHEM_ECKART_VERIFICATION_STATUS"] == "VERIFIED"
    assert env_vars["COCHEM_ALIGNMENT_ENGINE_READY"] == "1"
    assert env_vars["COCHEM_PHASE_10_STATUS"] == "PASSED"


def test_dependency_manager_atomic_and_rollback() -> None:
    """Test transactional atomic write and rollback behavior of DependencyManager."""
    with make_temp_dir() as td:
        target_file = Path(td) / "p10.json"

        with DependencyManager(target_file) as dm:
            dm.write_payload({"phase_id": "cochem_setup_phase_10", "status": "PASSED"})

        assert target_file.exists()
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["status"] == "PASSED"

        target_file2 = Path(td) / "p10_fail.json"
        try:
            with DependencyManager(target_file2) as dm2:
                dm2.write_payload({"status": "SHOULD_NOT_EXIST"})
                raise RuntimeError("Simulated unhandled failure")
        except RuntimeError:
            pass

        assert not target_file2.exists()


# =============================================================================
# 12. MASTER AUDIT ORCHESTRATOR & CLI TESTS
# =============================================================================


def test_run_phase_10_audit_full_flow() -> None:
    """Test master run_phase_10_audit execution in dry_run and write modes."""
    with make_temp_dir() as td:
        reg_dir = Path(td) / "Registry"
        reg_dir.mkdir()
        sb_dir = Path(td) / "sandboxes"
        sb_dir.mkdir()

        for i in range(1, 10):
            (reg_dir / f"p{i}.json").write_text(json.dumps({"status": "PASSED"}), encoding="utf-8")

        report_dry = run_phase_10_audit(
            output_dir=reg_dir,
            sandbox_base_dir=sb_dir,
            skip_iops=False,
            benchmark_size_mb=1.0,
            registry_dir=reg_dir,
            dry_run=True,
        )
        assert report_dry.phase_id == "cochem_setup_phase_10"
        assert report_dry.alignment_engine_ready is True
        assert not (reg_dir / "p10.json").exists()

        report_live = run_phase_10_audit(
            output_dir=reg_dir,
            sandbox_base_dir=sb_dir,
            skip_iops=False,
            benchmark_size_mb=1.0,
            registry_dir=reg_dir,
            dry_run=False,
        )
        assert report_live.alignment_engine_ready is True
        assert (reg_dir / "p10.json").exists()

        with open(reg_dir / "p10.json", "r", encoding="utf-8") as f:
            persisted = json.load(f)
            assert persisted["phase_id"] == "cochem_setup_phase_10"
            assert persisted["alignment_engine_ready"] is True


def test_main_cli_execution() -> None:
    """Test main CLI entrypoint with various flag permutations."""
    with make_temp_dir() as td:
        exit_code = main(["--dry-run", "--json", "--skip-iops", "--output-dir", td])
        assert exit_code == 0

        exit_code2 = main(["--dry-run", "--skip-iops", "--output-dir", td, "--sandbox-dir", td, "--skip-eckart"])
        assert exit_code2 == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
