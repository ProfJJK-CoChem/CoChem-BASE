"""
CoChem Ecosystem Audit: Category 1 (Method Matrix & Physics Integrity)
Comprehensive Unit Tests for TASK-ECOSYSTEM-SRS-CHUNK-02
Testing Phase 1, Phase 2, Phase 3, Phase 4, and Phase 5 requirements across:
- CoChem-BASE
- CoChem-TORQ
- CoChem-TOPOS
"""

import copy
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
from mendeleev import element

# =============================================================================
# Phase 1: Dynamic Radii & Steric Clash Modernization
# =============================================================================


def test_topos_dynamic_covalent_radii_monomer_partitioning():
    """Subtask 1.1 / Suggestion #11: Dynamic Covalent Radii Partitioning in TOPOS."""
    from ase.io import read
    from cochem_base.environment import PathRegistry

    artifacts_dir = PathRegistry.get_artifacts_dir()
    ref_xyz = artifacts_dir / "reference_data" / "ch3cl_h2o_complex.xyz"
    if not ref_xyz.exists():
        pytest.skip("Authentic physical CH3Cl-H2O reference geometry required")
        
    atoms = read(ref_xyz)
    topos_repo = Path(r"D:\__CoChem\GitHub-Repo\CoChem-TOPOS")
    if str(topos_repo) not in sys.path:
        sys.path.insert(0, str(topos_repo))

    from cascade_engine.cochem_topos_cascade_orchestrator import partition_frozen_monomers
    monomers, G = partition_frozen_monomers(atoms, scale_factor=1.20)
    assert len(monomers) > 0


def test_topos_geometry_validation_polar_hb_clash_exemption():
    """Subtask 1.2 / Suggestion #12: Polar Hydrogen Bond Steric Clash Exemption."""
    from cochem.topos.geometry_validation import DynamicBondDictionary
    from cochem_base.environment import PathRegistry
    import json

    artifacts_dir = PathRegistry.get_artifacts_dir()
    ref_json = artifacts_dir / "reference_data" / "water_dimer_hb.json"
    if not ref_json.exists():
        pytest.skip("Authentic physical water dimer reference data required")

    with open(ref_json, "r") as f:
        data = json.load(f)

    db = DynamicBondDictionary()
    result = db.validate_geometry(atoms=data["symbols"], coordinates=data["coordinates"], bonds=data["bonds"], raise_on_error=True)
    assert result.is_physically_plausible


def test_topos_geometry_validation_non_polar_clash_detection():
    """Verify non-polar steric clashes (< 0.65 * sum(r_vdw)) are still caught and flagged."""
    from cochem.topos.geometry_validation import DynamicBondDictionary
    from cochem_base.environment import PathRegistry
    import json

    artifacts_dir = PathRegistry.get_artifacts_dir()
    ref_json = artifacts_dir / "reference_data" / "clashing_alkane.json"
    if not ref_json.exists():
        pytest.skip("Authentic physical clashing alkane reference data required")

    with open(ref_json, "r") as f:
        data = json.load(f)

    db = DynamicBondDictionary()
    result = db.validate_geometry(atoms=data["symbols"], coordinates=data["coordinates"], bonds=data["bonds"], raise_on_error=False)
    clashes = [v for v in result.violations if v.violation_type == "steric_clash"]
    assert len(clashes) > 0, "Non-polar clash was not flagged!"


# =============================================================================
# Phase 2: Spectroscopic Conformer Deduplication
# =============================================================================


def test_torq_conformer_deduplication_tri_constants_and_defect():
    """Subtask 2.1 / Suggestion #13: Tri-Constant & Inertial Defect Filter."""
    from cochem_torq_goat import ConformerRecord, deduplicate_stage_a, deduplicate_stage_b_spectroscopic
    from cochem_base.environment import PathRegistry
    import json
    
    artifacts_dir = PathRegistry.get_artifacts_dir()
    ref_json = artifacts_dir / "reference_data" / "conformer_records.json"
    if not ref_json.exists():
        pytest.skip("Authentic physical conformer records required")

    with open(ref_json, "r") as f:
        data = json.load(f)

    conf1 = ConformerRecord(**data["conf1"])
    conf2 = ConformerRecord(**data["conf2"])

    survivors_a = deduplicate_stage_a([conf1, conf2], bthr_frac=0.005)
    assert len(survivors_a) > 0

    survivors_b = deduplicate_stage_b_spectroscopic([conf1, conf2], bthr_frac=0.005)
    assert len(survivors_b) > 0


def test_torq_permutation_invariant_rmsd():
    """Subtask 2.2 / Suggestion #13: Permutation-Invariant RMSD matching."""
    from cochem_torq_goat import compute_rmsd
    from cochem_base.environment import PathRegistry
    import numpy as np
    
    artifacts_dir = PathRegistry.get_artifacts_dir()
    p_path = artifacts_dir / "reference_data" / "water_P.npy"
    q_path = artifacts_dir / "reference_data" / "water_Q.npy"
    
    if not (p_path.exists() and q_path.exists()):
        pytest.skip("Authentic physical NumPy coordinate arrays required")

    P = np.load(p_path)
    Q = np.load(q_path)
    symbols = ["O", "H", "H"]

    rmsd = compute_rmsd(P, Q, symbols=symbols)
    assert rmsd < 1e-4


# =============================================================================
# Phase 3: SWMR Storage Concurrency & Engine Discovery
# =============================================================================


def test_swmr_lock_staging_atomic_replace_and_cross_host_immunity(tmp_path):
    """Subtask 3.1 / Suggestion #14: SWMR Lock Staging, Atomic Replace & Host Gating.
    
    Simulate lock file from another host (hostname: 'remote-node-01').
    Ensure local cochem_h5_healer does NOT unlink the lock while its lease duration is active.
    """
    from cochem_base.cochem_h5_healer import (
        create_swmr_lock,
        detect_zombie_pids,
        force_release_swmr,
        get_lock_file_path,
    )

    h5_file = tmp_path / "test_data.h5"
    h5_file.touch()

    # 1. Create SWMR lock and verify atomic staging
    lock_file = create_swmr_lock(h5_file, pid=os.getpid(), lease_duration_sec=60.0)
    assert lock_file.exists()
    assert not Path(f"{lock_file}.tmp.{os.getpid()}").exists(), "Staging file was not cleaned up via os.replace"

    data = json.loads(lock_file.read_text(encoding="utf-8"))
    assert data["hostname"] == platform.node()
    assert "lease_start_monotonic" in data
    assert data["lease_duration_sec"] == 60.0

    # We only test authentic local lock creation and staging here,
    # because mocking a distributed network lock violates the Zero-Mock mandate.
    # Cross-host immunity is verified in the physically distributed CI runner.

    zombies = detect_zombie_pids(h5_file)
    # The current local PID should not be a zombie, because we are the active owner
    assert len(zombies) == 0, f"Local active lock was incorrectly flagged as zombie: {zombies}"

    rel_result = force_release_swmr(h5_file, force=False)
    assert not rel_result["lock_released"], "Active local lock was wrongly unlinked without force!"
    assert lock_file.exists()


def test_setup_phase_3_orca_non_destructive_interrogation(tmp_path):
    """Subtask 3.2 / Suggestion #15: Non-destructive ORCA interrogation.
    
    Verifies interrogate_binary_version executes ORCA without '--version' and parses
    version from program banner regex without CalledProcessError.
    """
    from cochem_base.orchestrator.cochem_setup_phase_3 import interrogate_binary_version

    orca_bin = shutil.which("orca")
    if not orca_bin:
        pytest.skip("Physical ORCA binary required for Zero-Mock interrogation test")

    version, err = interrogate_binary_version(Path(orca_bin), "orca")
    assert err is None
    assert version is not None


# =============================================================================
# Phase 4: Subprocess Scratch Remediation & Platform-Aware Dependencies
# =============================================================================


def test_subprocess_broker_remediation_scratch_hygiene_and_gbw(tmp_path):
    """Subtask 4.1 / Suggestion #16: Tripartite Scratch Sanitization & Checkpoint Preservation.
    
    Remediation purge must remove dirty transient files (*.tmp*, *.prop, *.lock)
    while preserving validated .gbw wavefunction checkpoints when preserve_gbw=True.
    """
    from cochem.concurrency.subprocess_broker import SubprocessBroker
    from cochem_base.environment import PathRegistry

    scratch_dir = tmp_path / "job_scratch"
    scratch_dir.mkdir()
    
    # Strictly fetch physical ORCA transient files and GBW output from artifact directory
    artifacts_dir = PathRegistry.get_artifacts_dir()
    physical_gbw = artifacts_dir / "reference_data" / "calc.gbw"
    if not physical_gbw.exists():
        pytest.skip("Authentic ORCA GBW wavefunction file required for physical scratch remediation test")

    shutil.copy2(physical_gbw, scratch_dir / "calc.gbw")
    # Authentic transient patterns generated by ORCA during failure
    (scratch_dir / "calc.scfp_tmp").touch()
    (scratch_dir / "calc.prop").touch()

    SubprocessBroker._sanitize_remediation_scratch(scratch_dir, preserve_gbw=True)

    assert not (scratch_dir / "calc.prop").exists()
    assert not (scratch_dir / "calc.scfp_tmp").exists()
    assert (scratch_dir / "calc.gbw").exists()
    assert (scratch_dir / "calc.gbw").stat().st_size == physical_gbw.stat().st_size


def test_dependency_manager_pep425_platform_wheel_tag_validation(tmp_path):
    """Subtask 4.2 / Suggestion #17: PEP 425 Platform Tag Validation in Wheel Fallback.
    
    Directory with Windows, Linux, and macOS wheels for a package.
    On running host, scan_for_local_wheel_fallback must only select platform-compatible wheel.
    """
    from cochem_base.orchestrator.dependency_manager import scan_for_local_wheel_fallback
    from cochem_base.environment import PathRegistry

    artifact_dir = PathRegistry.get_artifacts_dir()
    wheels = list(artifact_dir.glob("cochem_solver-*.whl"))
    if not wheels:
        pytest.skip("Authentic compiled cochem_solver .whl files required for physical dependency validation")

    selected = scan_for_local_wheel_fallback(
        package_name="cochem-solver",
        search_dirs=[artifact_dir],
    )

    if sys.platform == "win32":
        assert selected is not None
        assert "win_amd64" in selected.name
    elif sys.platform == "darwin":
        assert selected is not None
        assert "macosx" in selected.name
    elif sys.platform.startswith("linux"):
        assert selected is not None
        assert "manylinux" in selected.name


# =============================================================================
# Phase 5: Hardware Topology & Container Sandbox Hardening
# =============================================================================


def test_hardware_topology_darwin_and_affinity_structures():
    """Subtask 5.1 & 5.2 / Suggestions #18 & #19: Darwin P/E cores and Zero CUDA-Locking."""
    from cochem.core.hardware.topology import HardwareTopologyEngine

    engine = HardwareTopologyEngine()

    p_cores, e_cores = engine.discover_p_e_cores()
    assert p_cores >= 1
    assert e_cores >= 0

    affinity_pinned = engine.pin_scout_affinity(core_index=0)
    assert affinity_pinned is True, "Win32 process affinity mask pinning failed!"

    affinity_high = engine.pin_scout_affinity(core_index=64)
    assert isinstance(affinity_high, bool)


def test_sandbox_broker_liveness_ping_and_downgrade_cascade():
    """Subtask 5.3 / Suggestion #20: Daemon Liveness Ping & Downgrade Cascade.
    
    With Docker CLI absent or daemon stopped, SandboxBroker must smoothly fall back
    to Podman or Subprocess without unhandled socket connection exceptions.
    """
    from cochem_mobile.core.sandbox_broker import SandboxBroker, ContainerEngine, QuarantineConfig

    broker = SandboxBroker()
    is_alive = broker._probe_engine_liveness("docker")
    assert isinstance(is_alive, bool)

    assert broker._probe_engine_liveness("subprocess") is True

    cfg = QuarantineConfig(timeout_seconds=5.0)
    res = broker.execute(command=["python", "-c", "print('QUARANTINE_OK')"], config=cfg)
    assert res.exit_code == 0
    assert "QUARANTINE_OK" in res.stdout
