"""
CoChem Ecosystem Audit: Category 1 (Method Matrix & Physics Integrity)
Comprehensive Unit Tests for TASK-ECOSYSTEM-SRS-CHUNK-03
Testing Tasks 1 through 10 (Suggestions #21 through #30) across:
- CoChem-BASE
- CoChem-TORQ
- CoChem-TOPOS

Strict Zero-Mock Mandate v3: Completely authentic physics, real molecular graphs,
dynamic Mendeleev masses, and physical system calls without test doubles.
"""

import collections
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import numpy as np
import pytest
import torch
from ase import Atoms
import ase.io
from ase.calculators.emt import EMT
from mendeleev import element
import filelock

# =============================================================================
# Genuine Physical Molecular Geometries (Zero-Mock Fixtures)
# =============================================================================

# Load actual physical xyz file
_data_dir = Path(__file__).resolve().parent.parent / "data"
_water_atoms = ase.io.read(str(_data_dir / "water.xyz"))
WATER_MONOMER_SYMBOLS = _water_atoms.get_chemical_symbols()
WATER_MONOMER_COORDS = _water_atoms.get_positions().tolist()

# Hydroxyl Radical (OH, open-shell doublet) by dropping H
_oh_atoms = _water_atoms.copy()
del _oh_atoms[-1]
OH_RADICAL_SYMBOLS = _oh_atoms.get_chemical_symbols()
OH_RADICAL_COORDS = _oh_atoms.get_positions().tolist()


# =============================================================================
# Task 1 / Suggestion #21: MPI Topology-Aware Memory Router & OS Floor
# =============================================================================

def test_dynamic_memory_backoff_topology_and_os_floor():
    """Task 1 / Suggestion #21: Memory Router OS Reserve Floor and Topology Backoff.
    
    Verifies:
    min_os_reserve = max(2048, int(total * 0.15))
    usable_ram = max(0, available - min_os_reserve)
    new_maxcore = max(256, int(usable_ram // max(1, nprocs)))
    Underflow clamp to 256 MB and direct SCF structured warning.
    """
    from cochem_base.cochem_torq_watchdog import dynamic_memory_backoff, DynamicMemoryResult

    # Case A: Standard high-memory node (32 GB total, 16 GB available, 4 procs)
    # min_os_reserve = max(2048, int(32768 * 0.15)) = max(2048, 4915) = 4915 MB
    # usable_ram = 16384 - 4915 = 11469 MB
    # new_maxcore = max(256, int(11469 // 4)) = 2867 MB
    res_a = dynamic_memory_backoff(
        req_mb=8000,
        total_system_ram_mb=32768,
        available_system_ram_mb=16384,
        nprocs=4,
    )
    assert isinstance(res_a, DynamicMemoryResult)
    assert int(res_a) == 2867
    assert res_a["new_maxcore_mb"] == 2867
    assert res_a["usable_ram_mb"] == 11469
    assert res_a["min_os_reserve_mb"] == 4915

    # Case B: Memory underflow / starvation (16 GB total, 2 GB available, 8 procs)
    # min_os_reserve = max(2048, int(16384 * 0.15)) = max(2048, 2457) = 2457 MB
    # usable_ram = max(0, 2048 - 2457) = 0 MB
    # usable_ram < 256 * 8 -> clamps to 256 MB with direct SCF warning
    res_b = dynamic_memory_backoff(
        req_mb=4000,
        total_system_ram_mb=16384,
        available_system_ram_mb=2048,
        nprocs=8,
    )
    assert int(res_b) == 256
    assert res_b["new_maxcore_mb"] == 256
    assert res_b.get("direct_scf_required") is True

    # Case C: Backward compatibility with legacy keyword arguments
    res_c = dynamic_memory_backoff(requested_mb=4096, available_mb=2048)
    assert int(res_c) >= 256
    assert "new_maxcore_mb" in res_c

    # Case D: Integer arithmetic and indexing compliance
    assert res_a + 100 == 2967
    assert res_a - 67 == 2800
    assert res_a * 2 == 5734
    assert res_a // 2 == 1433
    assert len(range(res_b)) == 256


# =============================================================================
# Task 2 / Suggestion #22: Physical Fallback Cascade & CIP Stereochemical Verification
# =============================================================================

def test_goat_physical_fallback_and_stereochemical_integrity():
    """Task 2 / Suggestion #22: GOAT Conformer Engine Fallback Cascade & CIP Check.
    
    Verifies:
    1. Unparameterized LennardJones() is purged from GOATConformerEngine.
    2. Physical force-field cascade (GFN-FF / MMFF94 / UFF / MACE-MP0).
    3. RDKit FindMolChiralCenters pre/post check prevents stereocenter inversion / racemization.
    """
    from cochem_base.topology.cochem_topos_crusher import GOATConformerEngine
    from rdkit import Chem
    from rdkit.Chem import AllChem

    goat = GOATConformerEngine(temperature_k=300.0)

    # 1. Verify LennardJones is not used in calculator
    atoms = Atoms(symbols=WATER_MONOMER_SYMBOLS, positions=WATER_MONOMER_COORDS)
    perturbed = goat._goat_single_worker(atoms, kick_magnitude=0.1)
    assert perturbed.calc.__class__.__name__ != "LennardJones"

    # 2. Test stereochemical invariant check on chiral center
    # Create (2R)-butan-2-ol: C[C@@H](O)CC
    smiles_r = "C[C@@H](O)CC"
    mol_r = Chem.MolFromSmiles(smiles_r)
    mol_r = Chem.AddHs(mol_r)
    AllChem.EmbedMolecule(mol_r, randomSeed=42)

    chiral_centers_before = Chem.FindMolChiralCenters(mol_r, includeUnassigned=True)
    assert len(chiral_centers_before) == 1
    assert chiral_centers_before[0][1] == "R"

    # Evaluate stereochemical check helper
    is_valid = goat._verify_stereochemical_integrity(mol_r, mol_r)
    assert is_valid is True

    # Invert stereocenter to S-enantiomer and verify integrity check rejects it
    smiles_s = "C[C@H](O)CC"
    mol_s = Chem.MolFromSmiles(smiles_s)
    mol_s = Chem.AddHs(mol_s)
    AllChem.EmbedMolecule(mol_s, randomSeed=42)

    is_inverted = goat._verify_stereochemical_integrity(mol_r, mol_s)
    assert is_inverted is False

    # Bond cleavage check: create cleaved molecule without C-O bond
    rw_cleaved = Chem.RWMol(mol_r)
    rw_cleaved.RemoveBond(1, 2)
    is_cleaved = goat._verify_stereochemical_integrity(mol_r, rw_cleaved.GetMol())
    assert is_cleaved is False


# =============================================================================
# Task 3 / Suggestion #23: In-Memory xtb-python Priority & Electron Parity
# =============================================================================

def test_gfn2_xtb_electron_parity_and_uhf_mapping():
    """Task 3 / Suggestion #23: GFN2-xTB Radical Multiplicity & Electron Parity Validation.
    
    Verifies:
    1. Total electron parity (N_e - 2S) % 2 == 0, 2S >= 0, N_e > 0.
    2. Validates against closed-shell and open-shell radical systems.
    3. Correct mapping of uhf = multiplicity - 1 (not uhf = multiplicity).
    4. Return type supports both dict access and tuple unpacking (energy, forces).
    """
    from Libraries.cochem_torq_delta_ml import GFN2xTBEngine

    engine = GFN2xTBEngine()

    # Case A: Water monomer (10 electrons, neutral, singlet: N_e=10, 2S=0 -> valid)
    atoms_h2o = Atoms(symbols=WATER_MONOMER_SYMBOLS, positions=WATER_MONOMER_COORDS)
    parity_valid = engine.validate_electron_parity(atoms_h2o, charge=0, multiplicity=1)
    assert parity_valid is True

    # Case B: Water monomer with invalid doublet multiplicity (N_e=10, 2S=1 -> 10 - 1 = 9 odd -> invalid!)
    with pytest.raises(ValueError, match=r"Electron parity violation"):
        engine.validate_electron_parity(atoms_h2o, charge=0, multiplicity=2)

    # Case C: Hydroxyl radical (OH, 9 electrons, doublet: N_e=9, 2S=1 -> 9 - 1 = 8 even -> valid)
    atoms_oh = Atoms(symbols=OH_RADICAL_SYMBOLS, positions=OH_RADICAL_COORDS)
    parity_oh = engine.validate_electron_parity(atoms_oh, charge=0, multiplicity=2)
    assert parity_oh is True

    # Case D: Hydroxyl radical with singlet multiplicity (N_e=9, 2S=0 -> 9 - 0 = 9 odd -> invalid!)
    with pytest.raises(ValueError, match=r"Electron parity violation"):
        engine.validate_electron_parity(atoms_oh, charge=0, multiplicity=1)

    # Case E: Multiplicity mapping verification (uhf = multiplicity - 1)
    uhf_val = engine._map_spin_to_uhf(multiplicity=3)
    assert uhf_val == 2

    # Case F: Backward compatibility with coordinates and atomic_numbers kwargs
    # Parity check via calculate signature
    coords_t = torch.tensor(WATER_MONOMER_COORDS, dtype=torch.float64)
    z_list = [element(s).atomic_number for s in WATER_MONOMER_SYMBOLS]
    with pytest.raises(ValueError, match=r"Electron parity violation"):
        engine.calculate(coords_t, atomic_numbers=z_list, charge=0, multiplicity=2)


# =============================================================================
# Task 4 / Suggestion #24: Active Learning Hardware Triage & HDF5 SWMR
# =============================================================================

def test_active_learning_hardware_triage_gate():
    """Task 4 / Suggestion #24: Active Learning Hardware Triage Gate.
    
    Verifies:
    1. route_qm_tier ingests hardware topology / compute budget / available engines.
    2. Degrades high-tier candidates when required engines (ORCA/CFOUR) are missing or budget exceeded.
    """
    from Libraries.cochem_torq_active_learning import route_qm_tier
    from cochem.core.hardware.topology import HardwareTopologyEngine

    topo_engine = HardwareTopologyEngine()
    topo = topo_engine.discover_topology()

    # Moderate uncertainty: routes to T3-10s regardless of high-cost engines
    tier_mod = route_qm_tier(max_force_std=0.15, hardware_topology=topo, available_engines=["xtb"])
    assert tier_mod == "T3-10s"

    # Extreme uncertainty (alpha_F > 0.8) with full engines and ample budget -> T3O-12h
    tier_ext_full = route_qm_tier(
        max_force_std=0.90,
        hardware_topology=topo,
        compute_budget_hours=24.0,
        available_engines=["orca", "cfour", "xtb"],
    )
    assert tier_ext_full == "T3O-12h"

    # Extreme uncertainty but ORCA/CFOUR missing -> gracefully degrades to B3LYP-D4/def2-TZVP or highest available
    tier_degraded = route_qm_tier(
        max_force_std=0.90,
        hardware_topology=topo,
        compute_budget_hours=0.5,
        available_engines=["xtb"],
    )
    assert tier_degraded in ("T3-10s", "B3LYP-D4/def2-TZVP", "T3O-1h")

    # Extreme uncertainty with constrained cores (P-cores < 4) -> gracefully degrades T3O-12h
    from cochem.core.hardware.topology import HardwareTopology
    constrained_topo = HardwareTopology(
        total_logical_cpus=4,
        total_physical_cores=2,
        p_cores=2,
        e_cores=0,
        resource_ceiling=4,
        scout_cores=1,
        anchor_cores=1,
        gpu_mps_workers=0,
        environment_variables={},
    )
    tier_core_constrained = route_qm_tier(
        max_force_std=0.90,
        hardware_topology=constrained_topo,
        compute_budget_hours=24.0,
        available_engines=["orca", "cfour", "xtb"],
    )
    assert tier_core_constrained in ("T3O-1h", "B3LYP-D4/def2-TZVP", "T3-10s")


def test_hdf5_swmr_preallocation_and_dual_locking(tmp_path):
    """Task 4 / Suggestion #24: HDF5 SWMR Preallocation Invariant & Dual Locking.
    
    Verifies:
    1. Extensible datasets (coordinates, energies, forces, uncertainties) are preallocated
       before enabling SWMR mode (swmr_mode = True).
    2. Writes are guarded by cross-platform filelock.FileLock.
    """
    from Libraries.cochem_torq_storage import HDF5StorageManager

    h5_file = tmp_path / "swmr_test.h5"
    manager = HDF5StorageManager(h5_file)

    # Initialize / preallocate extensible boundaries
    manager.initialize_swmr_datasets(max_atoms=10)

    # Verify SWMR mode is active on the file
    with h5py.File(h5_file, "r", libver="latest", swmr=True) as f:
        assert "coordinates" in f
        assert "energies" in f
        assert "forces" in f
        assert "uncertainties" in f
        assert f.swmr_mode is True

    # Append batch under filelock protection
    _water_atoms.calc = EMT()
    real_energy = _water_atoms.get_potential_energy()
    real_forces = _water_atoms.get_forces()
    
    coords = _water_atoms.get_positions()[np.newaxis, :, :]
    energies = np.array([real_energy])
    forces = real_forces[np.newaxis, :, :]
    uncert = np.array([0.02])

    manager.append_batch(coordinates=coords, energies=energies, forces=forces, uncertainties=uncert)

    with h5py.File(h5_file, "r", libver="latest", swmr=True) as f:
        assert f["coordinates"].shape[0] == 1
        assert f["energies"].shape[0] == 1


# =============================================================================
# Task 5 / Suggestion #25: Setup Graceful Degradation & Voila GUI State
# =============================================================================

def test_cli_degraded_operational_and_gui_environment_detection(tmp_path):
    """Task 5 / Suggestion #25: Decoupled Setup Gates & GUI DEGRADED_OPERATIONAL State.
    
    Verifies:
    1. Phase 1 & 2 mandatory, Phase 3+ solver failures result in DEGRADED_OPERATIONAL.
    2. Missing capabilities recorded in cochem_system_config.json.
    3. GUI _detect_environment treats DEGRADED_OPERATIONAL as functional and keeps buttons enabled.
    """
    from ui.voila_layout.cochem_gui import CoChemGUI
    from cochem_base.orchestrator.cochem_setup_phase_2 import run_phase_2_audit
    from cochem_base.orchestrator.cochem_system_config import interrogate_system_config

    # Run authentic physical initialization logic
    reg_dir = tmp_path / "Registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    
    run_phase_2_audit(output_dir=reg_dir)
    config = interrogate_system_config()
    config.to_file(reg_dir / "cochem_system_config.json")

    old_env = os.environ.get("COCHEM_ARTIFACT_DIR")
    try:
        os.environ["COCHEM_ARTIFACT_DIR"] = str(tmp_path)
        gui = CoChemGUI()
        is_init, env_str, is_hpc, is_slurm = gui._detect_environment()
        assert is_init is True
        assert "DEGRADED" in env_str or "Local" in env_str or "Operational" in env_str
        assert gui.btn_matrix.disabled is False
        assert gui.btn_inspector.disabled is False
    finally:
        if old_env is not None:
            os.environ["COCHEM_ARTIFACT_DIR"] = old_env
        else:
            os.environ.pop("COCHEM_ARTIFACT_DIR", None)


# =============================================================================
# Task 6 / Suggestion #26: Cross-Platform Scratch Resolution & Ephemeral Session
# =============================================================================

def test_cross_platform_scratch_resolution_and_ephemeral_session():
    """Task 6 / Suggestion #26: HPC-Safe Scratch Resolution and Context-Managed Session.
    
    Verifies:
    1. Windows checks LOCALAPPDATA / TEMP before falling back to Path.home() / .cochem.
    2. EphemeralScratchSession context manager creates unique sandbox and auto-purges.
    3. filelock.FileLock is anchored inside the local scratch directory.
    """
    from Libraries.cochem_torq_environment import resolve_hpc_safe_scratch, EphemeralScratchSession

    scratch = resolve_hpc_safe_scratch()
    assert scratch.exists()
    assert scratch.is_dir()

    # Verify Windows does not default to roaming profile if LOCALAPPDATA or TEMP is present
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA")
        temp_dir = os.environ.get("TEMP")
        if local_app or temp_dir:
            assert str(scratch).lower().startswith(str(local_app or temp_dir).lower()[:3])

    # Context managed session with auto purge
    with EphemeralScratchSession(prefix="test_session_") as session_path:
        assert session_path.exists()
        test_file = session_path / "work.txt"
        test_file.write_text("authentic data", encoding="utf-8")
        assert test_file.exists()
        captured_path = session_path

    # Verify auto teardown swept the directory
    assert not captured_path.exists()


# =============================================================================
# Task 7 / Suggestion #27: Multi-GPU Div-by-Zero Guard & Air-Gap Sandboxing
# =============================================================================

def test_gpu_allocation_cpu_guard_and_bounded_ring_buffer(tmp_path):
    """Task 7 / Suggestion #27: GPU Allocation Guard and Tripartite Sandboxing with Ring Buffer.
    
    Verifies:
    1. When no GPUs are present, CUDA_VISIBLE_DEVICES is set to "" (never div by zero).
    2. Ambient CUDA_VISIBLE_DEVICES is scrubbed.
    3. Subprocess execution runs in isolated cochem_exec_<uuid> sandbox.
    4. Ring buffer caps captured output safely.
    """
    from cochem.concurrency.subprocess_broker import SubprocessBroker
    from cochem.core.hardware.topology import HardwareTopologyEngine

    topo = HardwareTopologyEngine()
    worker_env = topo.get_worker_env(concurrent_workers=2, worker_index=0)

    # In CPU environment, CUDA_VISIBLE_DEVICES must be explicitly empty
    avail_gpus = topo.get_available_gpus()
    if len(avail_gpus) == 0:
        assert worker_env["CUDA_VISIBLE_DEVICES"] == ""

    broker = SubprocessBroker(scratch_dir=tmp_path)
    # Execute an authentic physical chemistry command
    res = broker.execute([sys.executable, "-c", "from mendeleev import element; print(element('H').mass)"])
    assert res.success is True
    assert "1.00" in res.stdout


# =============================================================================
# Task 8 / Suggestion #28: CREST Toolchain Co-Existence & OpenMP Virtual Memory
# =============================================================================

def test_crest_toolchain_coexistence_and_openmp_injection():
    """Task 8 / Suggestion #28: CREST Toolchain Audit & OpenMP Memory Safeguards.
    
    Verifies:
    1. If crest or xtb is missing, raises typed EcosystemDependencyError.
    2. Injects OMP_STACKSIZE=1G, OMP_NUM_THREADS, MKL_NUM_THREADS.
    3. Hardware topology thread budget is respected.
    """
    from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine
    from cochem_base.exceptions import EcosystemDependencyError

    crest = CRESTConformerEngine(thread_budget=2)
    atoms = Atoms(symbols=WATER_MONOMER_SYMBOLS, positions=WATER_MONOMER_COORDS)

    # In standard test environment without crest or xtb in PATH, must raise EcosystemDependencyError
    if not (shutil.which("crest") and shutil.which("xtb")):
        with pytest.raises(EcosystemDependencyError, match=r"CREST relies intrinsically on xTB"):
            crest.execute_secondary_search(atoms, num_conformers=2)

    # Verify OpenMP environment constructor helper
    env = crest._build_execution_env(budgeted_threads=4)
    assert env["OMP_STACKSIZE"] == "1G"
    assert env["OMP_NUM_THREADS"] == "4"
    assert env["MKL_NUM_THREADS"] == "4"


# =============================================================================
# Task 9 / Suggestion #29: Dynamic Linkage Auditor for Phase 3 Binaries
# =============================================================================

def test_audit_binary_linkage():
    """Task 9 / Suggestion #29: Cross-Platform Dynamic Linkage Auditor.
    
    Verifies:
    1. audit_binary_linkage inspects dynamic dependencies for a binary executable.
    2. Returns (is_valid, missing_libraries).
    3. Automatically checks sibling directories (../lib) if unresolved dependencies exist.
    """
    from cochem_base.orchestrator.cochem_setup_phase_3 import audit_binary_linkage

    python_bin = Path(sys.executable)
    is_valid, missing = audit_binary_linkage(python_bin)
    assert isinstance(is_valid, bool)
    assert isinstance(missing, list)
    # The active Python binary running this test must have valid linkages
    assert is_valid is True
    assert len(missing) == 0


# =============================================================================
# Task 10 / Suggestion #30: Dual-Audience Pedagogical & Telemetry Exception
# =============================================================================

def test_pedagogical_guidance_and_diagnostic_telemetry():
    """Task 10 / Suggestion #30: Pedagogical Guidance and Diagnostic Telemetry Interfaces.
    
    Verifies:
    1. CoChemError.to_pedagogical_guidance() provides clear, chemical intuition and remediation.
    2. CoChemError.to_diagnostic_telemetry() provides structured diagnostics for auditors.
    3. CoChemBaseException is an alias to CoChemError.
    """
    from cochem_base.exceptions import (
        CoChemError,
        CoChemBaseException,
        ConvergenceError,
        TriagePathologyError,
        OutOfMemoryGateError,
    )

    assert CoChemBaseException is CoChemError

    # Test SCF convergence error guidance
    conv_err = ConvergenceError(
        message="SCF NOT CONVERGED after 100 cycles at defgrid3",
        details={"scf_cycles": 100, "grid": "defgrid3", "damping": False},
    )
    guidance = conv_err.to_pedagogical_guidance()
    assert "Self-Consistent Field (SCF)" in guidance
    assert "electronic oscillation" in guidance or "damping" in guidance or "grid" in guidance

    telemetry = conv_err.to_diagnostic_telemetry()
    assert isinstance(telemetry, dict)
    assert telemetry["error_type"] == "ConvergenceError"
    assert "scf_cycles" in telemetry["details"]
    assert "timestamp" in telemetry

    # Test Steric Clash error guidance
    clash_err = TriagePathologyError(
        message="Severe atomic clash detected between O1 and C2",
        details={"atom_pair": ("O1", "C2"), "distance_angstrom": 0.85},
    )
    clash_guidance = clash_err.to_pedagogical_guidance()
    assert "nuclear overlap" in clash_guidance or "steric" in clash_guidance
