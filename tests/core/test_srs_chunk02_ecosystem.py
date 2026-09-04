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
    """Subtask 1.1 / Suggestion #11: Dynamic Covalent Radii Partitioning in TOPOS.
    
    Verifies that C-Cl, C-Br, and C-S bonds are NOT severed under dynamic covalent radii scaling:
    d_ij < (r_cov,i + r_cov,j) * 1.20 [D], whereas inter-monomer contacts segment into discrete subgraphs.
    """
    import networkx as nx
    from ase import Atoms

    # Test complex 1: CH3Cl ... H2O (chlorinated complex)
    # C-Cl bond is ~1.78 A. Dynamic covalent radii: C=0.75 A, Cl=1.02 A -> sum=1.77 A * 1.20 = 2.124 A.
    # Legacy cutoff=1.6 A would sever C-Cl! Dynamic radii must preserve C-Cl.
    symbols = ["C", "H", "H", "H", "Cl", "O", "H", "H"]
    positions = [
        [0.000, 0.000, 0.000],   # C
        [0.000, 1.020, 0.350],   # H
        [0.880, -0.510, 0.350],  # H
        [-0.880, -0.510, 0.350], # H
        [0.000, 0.000, 1.780],   # Cl (d_C-Cl = 1.78 A)
        [0.000, 0.000, 4.500],   # O (water monomer separated at 4.5 A)
        [0.000, 0.760, 5.080],   # H
        [0.000, -0.760, 5.080],  # H
    ]
    atoms = Atoms(symbols=symbols, positions=positions)

    topos_repo = Path(r"D:\__CoChem\GitHub-Repo\CoChem-TOPOS")
    if str(topos_repo) not in sys.path:
        sys.path.insert(0, str(topos_repo))

    from cascade_engine.cochem_topos_cascade_orchestrator import partition_frozen_monomers

    monomers, G = partition_frozen_monomers(atoms, scale_factor=1.20)

    # Verify C (0) is connected to Cl (4)
    assert G.has_edge(0, 4), "C-Cl bond was severed! Dynamic covalent radii scaling failed."
    # Verify CH3Cl and H2O are separated into 2 distinct monomers
    assert len(monomers) == 2, f"Expected 2 monomers (CH3Cl and H2O), got {len(monomers)}"
    assert {0, 1, 2, 3, 4} in monomers
    assert {5, 6, 7} in monomers


def test_topos_geometry_validation_polar_hb_clash_exemption():
    """Subtask 1.2 / Suggestion #12: Polar Hydrogen Bond Steric Clash Exemption.
    
    Water dimer (H2O)2 with R(O...H) approx 1.70 A must pass validate_steric_contacts
    without raising GeometricPlausibilityError (threshold_HB = 0.50 * sum(r_vdw) [M]).
    """
    from cochem.topos.geometry_validation import DynamicBondDictionary

    db = DynamicBondDictionary()

    # Water dimer: donor O(0)-H(1)...O(3)-H(4),H(5)
    # O0 at [0,0,0], H1 at [0, 0, 0.96] pointing towards O3 at [0, 0, 2.66]
    # d(H1 ... O3) = 1.70 A.
    # r_vdw(H)=1.10 A, r_vdw(O)=1.52 A -> sum = 2.62 A.
    # Non-polar threshold = 0.65 * 2.62 = 1.703 A (would clash!).
    # Polar HB threshold = 0.50 * 2.62 = 1.310 A (clears cleanly!).
    atoms = ["O", "H", "H", "O", "H", "H"]
    coords = [
        [0.000, 0.000, 0.000],  # O0
        [0.000, 0.000, 0.960],  # H1 (polar H pointing to O3)
        [0.929, 0.000, -0.240], # H2 (104.5 deg angle)
        [0.000, 0.000, 2.660],  # O3 (acceptor, d(H1-O3) = 1.70 A)
        [0.759, 0.000, 3.248],  # H4 (104.5 deg angle)
        [-0.759, 0.000, 3.248], # H5
    ]
    bonds = [
        (0, 1, 1.0),
        (0, 2, 1.0),
        (3, 4, 1.0),
        (3, 5, 1.0),
    ]

    result = db.validate_geometry(atoms=atoms, coordinates=coords, bonds=bonds, raise_on_error=True)
    assert result.is_physically_plausible
    clash_violations = [v for v in result.violations if v.violation_type == "steric_clash"]
    assert len(clash_violations) == 0, f"Hydrogen bond incorrectly flagged as clash: {clash_violations}"

    if hasattr(db, "validate_steric_contacts"):
        steric_clashes = db.validate_steric_contacts(atoms=atoms, coordinates=coords, bonds=bonds)
        assert len(steric_clashes) == 0


def test_topos_geometry_validation_non_polar_clash_detection():
    """Verify non-polar steric clashes (< 0.65 * sum(r_vdw)) are still caught and flagged."""
    from cochem.topos.geometry_validation import DynamicBondDictionary

    db = DynamicBondDictionary()
    atoms = ["C", "H", "H", "H", "H", "C", "H", "H", "H", "H"]
    coords = [
        [0.000, 0.000, 0.000],
        [0.630, 0.630, 0.630],
        [-0.630, -0.630, 0.630],
        [-0.630, 0.630, -0.630],
        [0.630, -0.630, -0.630],
        [1.700, 0.000, 0.000],
        [2.330, 0.630, 0.630],
        [1.070, -0.630, 0.630],
        [1.070, 0.630, -0.630],
        [2.330, -0.630, -0.630],
    ]
    bonds = [
        (0, 1, 1.0), (0, 2, 1.0), (0, 3, 1.0), (0, 4, 1.0),
        (5, 6, 1.0), (5, 7, 1.0), (5, 8, 1.0), (5, 9, 1.0),
    ]
    result = db.validate_geometry(atoms=atoms, coordinates=coords, bonds=bonds, raise_on_error=False)
    clashes = [v for v in result.violations if v.violation_type == "steric_clash"]
    assert len(clashes) > 0, "Non-polar C...C clash was not flagged!"


# =============================================================================
# Phase 2: Spectroscopic Conformer Deduplication
# =============================================================================


def test_torq_conformer_deduplication_tri_constants_and_defect():
    """Subtask 2.1 / Suggestion #13: Tri-Constant & Inertial Defect Filter.
    
    Conformer pairs with identical B but distinct A, C, or inertial defect Delta
    must both be retained in the ensemble (not conflated as duplicates).
    """
    from cochem_torq_goat import ConformerRecord, deduplicate_stage_a, deduplicate_stage_b_spectroscopic

    coords1 = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    coords2 = [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    conf1 = ConformerRecord(
        index=0,
        symbols=["O", "H", "H"],
        coordinates=coords1,
        energy_kcal_rel=0.01,
        rotational_constants_mhz=(8500.0, 3000.0, 2000.0),
        inertial_defect_u_a2=0.05,
    )
    conf2 = ConformerRecord(
        index=1,
        symbols=["O", "H", "H"],
        coordinates=coords2,
        energy_kcal_rel=0.02,
        rotational_constants_mhz=(9200.0, 3000.0, 2000.0),
        inertial_defect_u_a2=0.25,
    )

    survivors_a = deduplicate_stage_a([conf1, conf2], bthr_frac=0.005)
    assert len(survivors_a) == 2, f"Stage A dropped distinct conformer! survivors: {len(survivors_a)}"

    survivors_b = deduplicate_stage_b_spectroscopic([conf1, conf2], bthr_frac=0.005)
    assert len(survivors_b) == 2, f"Stage B dropped distinct conformer! survivors: {len(survivors_b)}"


def test_torq_permutation_invariant_rmsd():
    """Subtask 2.2 / Suggestion #13: Permutation-Invariant RMSD matching.
    
    Structures identical up to atom permutation must be recognized as duplicates with RMSD = 0.0 A.
    """
    from cochem_torq_goat import compute_rmsd

    P = np.array([
        [0.000, 0.000, 0.117],   # O
        [0.000, 0.757, -0.469],  # H1
        [0.000, -0.757, -0.469], # H2
    ])
    Q = np.array([
        [0.000, 0.000, 0.117],   # O
        [0.000, -0.757, -0.469], # H2 (swapped!)
        [0.000, 0.757, -0.469],  # H1 (swapped!)
    ])
    symbols = ["O", "H", "H"]

    rmsd = compute_rmsd(P, Q, symbols=symbols)
    assert rmsd < 1e-4, f"Permutation-invariant RMSD failed: expected ~0.0, got {rmsd:.6f} A"


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

    # 2. Simulate lock from another host
    remote_payload = {
        "h5_file": str(h5_file),
        "pid": 9999999,
        "hostname": "remote-node-01",
        "timestamp_utc": time.time(),
        "lease_start_monotonic": time.monotonic(),
        "lease_duration_sec": 60.0,
        "mode": "SWMR_WRITE",
    }
    lock_file.write_text(json.dumps(remote_payload), encoding="utf-8")

    zombies = detect_zombie_pids(h5_file)
    assert len(zombies) == 0, f"Remote lock with active lease was incorrectly flagged as zombie: {zombies}"

    rel_result = force_release_swmr(h5_file, force=False)
    assert not rel_result["lock_released"], "Active remote lease was unlinked!"
    assert lock_file.exists()

    # 3. Simulate expired remote lease
    expired_payload = dict(remote_payload)
    expired_payload["timestamp_utc"] = time.time() - 120.0
    expired_payload["lease_start_monotonic"] = time.monotonic() - 120.0
    expired_payload["lease_duration_sec"] = 60.0
    lock_file.write_text(json.dumps(expired_payload), encoding="utf-8")

    zombies_expired = detect_zombie_pids(h5_file)
    assert len(zombies_expired) > 0, "Expired remote lease was not classified as stale!"


def test_setup_phase_3_orca_non_destructive_interrogation(tmp_path):
    """Subtask 3.2 / Suggestion #15: Non-destructive ORCA interrogation.
    
    Verifies interrogate_binary_version executes ORCA without '--version' and parses
    version from program banner regex without CalledProcessError.
    """
    from cochem_base.orchestrator.cochem_setup_phase_3 import interrogate_binary_version

    if sys.platform == "win32":
        mock_orca = tmp_path / "orca.bat"
        mock_orca.write_text(
            "@echo off\necho *************************************************************\n"
            "echo *                       O   R   C   A                       *\n"
            "echo * Program Version 6.0.0 - RELEASE                          *\n"
            "echo *************************************************************\n"
            "exit /b 1\n",
            encoding="utf-8",
        )
    else:
        mock_orca = tmp_path / "orca"
        mock_orca.write_text(
            "#!/bin/sh\n"
            "echo '*************************************************************'\n"
            "echo '*                       O   R   C   A                       *'\n"
            "echo '* Program Version 6.0.0 - RELEASE                          *'\n"
            "echo '*************************************************************'\n"
            "exit 1\n",
            encoding="utf-8",
        )
        mock_orca.chmod(0o755)

    version, err = interrogate_binary_version(mock_orca, "orca")
    assert version == "6.0.0", f"Expected version 6.0.0, got '{version}', err: {err}"
    assert err is None


# =============================================================================
# Phase 4: Subprocess Scratch Remediation & Platform-Aware Dependencies
# =============================================================================


def test_subprocess_broker_remediation_scratch_hygiene_and_gbw(tmp_path):
    """Subtask 4.1 / Suggestion #16: Tripartite Scratch Sanitization & Checkpoint Preservation.
    
    Remediation purge must remove dirty transient files (*.tmp*, *.prop, *.lock)
    while preserving validated .gbw wavefunction checkpoints when preserve_gbw=True.
    """
    from cochem.concurrency.subprocess_broker import SubprocessBroker

    scratch_dir = tmp_path / "job_scratch"
    scratch_dir.mkdir()

    (scratch_dir / "calc.tmp.123").write_text("transient tmp", encoding="utf-8")
    (scratch_dir / "calc.prop").write_text("transient prop", encoding="utf-8")
    (scratch_dir / "calc.scfp_tmp").write_text("transient scfp", encoding="utf-8")
    (scratch_dir / "calc.lock").write_text("transient lock", encoding="utf-8")
    gbw_file = scratch_dir / "calc.gbw"
    gbw_file.write_bytes(b"AUTHENTIC_ORCA_GBW_WAVEFUNCTION_STATE")

    SubprocessBroker._sanitize_remediation_scratch(scratch_dir, preserve_gbw=True)

    assert not (scratch_dir / "calc.tmp.123").exists()
    assert not (scratch_dir / "calc.prop").exists()
    assert not (scratch_dir / "calc.scfp_tmp").exists()
    assert not (scratch_dir / "calc.lock").exists()
    assert gbw_file.exists()
    assert gbw_file.read_bytes() == b"AUTHENTIC_ORCA_GBW_WAVEFUNCTION_STATE"


def test_dependency_manager_pep425_platform_wheel_tag_validation(tmp_path):
    """Subtask 4.2 / Suggestion #17: PEP 425 Platform Tag Validation in Wheel Fallback.
    
    Directory with Windows, Linux, and macOS wheels for a package.
    On running host, scan_for_local_wheel_fallback must only select platform-compatible wheel.
    """
    from cochem_base.orchestrator.dependency_manager import scan_for_local_wheel_fallback

    py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    win_wheel = tmp_path / f"cochem_solver-1.0.0-{py_tag}-{py_tag}-win_amd64.whl"
    linux_wheel = tmp_path / f"cochem_solver-1.0.0-{py_tag}-{py_tag}-manylinux2014_x86_64.whl"
    mac_wheel = tmp_path / f"cochem_solver-1.0.0-{py_tag}-{py_tag}-macosx_11_0_arm64.whl"

    win_wheel.touch()
    linux_wheel.touch()
    mac_wheel.touch()

    selected = scan_for_local_wheel_fallback(
        package_name="cochem-solver",
        search_dirs=[tmp_path],
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
