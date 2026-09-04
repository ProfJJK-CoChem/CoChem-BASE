"""
CoChem Ecosystem Audit: Category 1 (Method Matrix & Physics Integrity)
Comprehensive Unit Tests for TASK-ECOSYSTEM-SRS-CHUNK-01
Testing Phase 1, Phase 2, Phase 3, Phase 4, and Phase 5 requirements across:
- CoChem-BASE
- CoChem-TORQ
- CoChem-TOPOS
"""

import math
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest
import scipy.constants

# =============================================================================
# Phase 1: Base Architecture, Exceptions, Environment, Schemas, Constraints
# =============================================================================


def test_exception_hierarchy():
    """Verify ecosystem dependency and physics integrity exceptions."""
    from cochem_base.exceptions import (
        BinaryNotFoundError,
        EcosystemDependencyError,
        PhysicsIntegrityError,
        SpinContaminationError,
    )

    assert issubclass(EcosystemDependencyError, RuntimeError)
    assert issubclass(BinaryNotFoundError, EcosystemDependencyError)
    assert issubclass(SpinContaminationError, ValueError)
    assert issubclass(PhysicsIntegrityError, RuntimeError)

    err = BinaryNotFoundError("[MISSING DATA] crest executable not discovered in environment path")
    assert "[MISSING DATA]" in str(err)
    assert isinstance(err, EcosystemDependencyError)

    spin_err = SpinContaminationError("[ERR_SPIN_CONTAMINATION] 15.2% exceeds 10% threshold")
    assert "ERR_SPIN_CONTAMINATION" in str(spin_err)
    assert isinstance(spin_err, ValueError)


def test_binary_registry_and_path_registry(tmp_path, monkeypatch):
    """Verify BinaryRegistry.resolve and PathRegistry scratch/artifact directories."""
    from cochem_base.environment import BinaryRegistry, PathRegistry
    from cochem_base.exceptions import BinaryNotFoundError

    # Non-existent binary raises BinaryNotFoundError with [MISSING DATA]
    with pytest.raises(BinaryNotFoundError) as excinfo:
        BinaryRegistry.resolve("non_existent_binary_xyz_123")
    assert "[MISSING DATA]" in str(excinfo.value)
    assert "non_existent_binary_xyz_123" in str(excinfo.value)

    # Resolve via custom environment variable
    test_bin = tmp_path / "crest.exe"
    test_bin.write_text("#!/bin/sh\necho crest", encoding="utf-8")
    monkeypatch.setenv("COCHEM_CREST_BIN", str(test_bin))

    resolved = BinaryRegistry.resolve("crest")
    assert resolved == test_bin.resolve()

    # CFOUR_ROOT resolution
    cfour_root = tmp_path / "cfour_dir"
    cfour_bin_dir = cfour_root / "bin"
    cfour_bin_dir.mkdir(parents=True)
    test_xcfour = cfour_bin_dir / "xcfour.exe"
    test_xcfour.write_text("#!/bin/sh\necho xcfour", encoding="utf-8")
    monkeypatch.setenv("CFOUR_ROOT", str(cfour_root))

    resolved_cfour = BinaryRegistry.resolve("xcfour")
    assert resolved_cfour == test_xcfour.resolve()

    # PathRegistry artifacts and scratch dir
    artifacts_dir = PathRegistry.get_artifacts_dir()
    assert artifacts_dir.exists()
    assert artifacts_dir.is_dir()

    scratch_dir = PathRegistry.create_scratch_dir("test_run")
    assert scratch_dir.exists()
    assert scratch_dir.is_dir()
    assert "test_run" in scratch_dir.name


def test_schemas_gradient_payload_optional_hessian():
    """Verify GradientPayload supports optional hessian and rejects all-zero gradients."""
    from cochem_base.schemas import (
        ConformerEnsemblePayload,
        ConstraintPayload,
        GradientPayload,
        QuantumJobSpec,
    )

    # Valid payload with hessian=None (screening tier)
    gp = GradientPayload(
        energy=-76.4382,
        gradient=[[0.001, -0.002, 0.003], [-0.001, 0.002, -0.003]],
        hessian=None,
    )
    assert gp.hessian is None
    assert gp.energy == -76.4382

    # Anti-spoofing: all-zero non-empty gradient must be rejected
    with pytest.raises(ValueError):
        GradientPayload(
            energy=-76.4382,
            gradient=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
            hessian=None,
        )

    # QuantumJobSpec initialization
    spec = QuantumJobSpec(
        job_id="job_cp_01",
        symbols=["O", "H", "H"],
        coordinates=[[0.0, 0.0, 0.0], [0.0, 0.75, 0.58], [0.0, -0.75, 0.58]],
        job_type="CP_E_AB_AB",
    )
    assert spec.job_id == "job_cp_01"
    assert spec.job_type == "CP_E_AB_AB"

    # ConstraintPayload
    cp = ConstraintPayload(
        bonds=[(0, 1), (0, 2)],
        angles=[(1, 0, 2)],
        dihedrals=[],
    )
    assert len(cp.bonds) == 2
    assert len(cp.angles) == 1

    # ConformerEnsemblePayload
    cep = ConformerEnsemblePayload(
        ensemble_id="ens_01",
        origin_engine="UNION",
        conformers=[{"index": 0, "energy": -76.4}],
    )
    assert cep.origin_engine == "UNION"
    assert len(cep.conformers) == 1


def test_generate_frozen_monomer_constraints():
    """Verify generate_frozen_monomer_constraints freezes internal degrees of freedom
    for monomers A and B while placing zero constraints on intermolecular space.
    """
    import networkx as nx
    from cochem_base.geometry.constraints import generate_frozen_monomer_constraints

    # Water dimer graph:
    # Monomer A: atoms 0 (O), 1 (H), 2 (H). Edges: (0, 1), (0, 2)
    # Monomer B: atoms 3 (O), 4 (H), 5 (H). Edges: (3, 4), (3, 5)
    # Intermolecular H-bond between 1 and 3 (edge (1, 3))
    G = nx.Graph()
    G.add_edges_from([(0, 1), (0, 2), (3, 4), (3, 5), (1, 3)])

    atoms_a = [0, 1, 2]
    atoms_b = [3, 4, 5]

    constraints = generate_frozen_monomer_constraints(atoms_a, atoms_b, G)

    # Intramolecular bonds for A: (0, 1), (0, 2); for B: (3, 4), (3, 5)
    expected_bonds = {(0, 1), (0, 2), (3, 4), (3, 5)}
    actual_bonds = {tuple(sorted(b)) for b in constraints.bonds}
    assert actual_bonds == expected_bonds

    # Angle constraints: (1, 0, 2) for A; (4, 3, 5) for B
    assert len(constraints.angles) == 2
    # Ensure NO intermolecular bond constraint (1, 3) is included
    assert (1, 3) not in actual_bonds and (3, 1) not in actual_bonds

    # Dihedrals for this planar water dimer are empty
    assert len(constraints.dihedrals) == 0

    # Ensure zero atoms from A appear in combination with B in any constraint
    for u, v in constraints.bonds:
        assert (u in atoms_a and v in atoms_a) or (u in atoms_b and v in atoms_b)
    for i, j, k in constraints.angles:
        assert (i in atoms_a and j in atoms_a and k in atoms_a) or (
            i in atoms_b and j in atoms_b and k in atoms_b
        )


def test_grid_policy():
    """Verify GridPolicy dictates integration grids per execution phase."""
    from cochem_base.config import GridPolicy

    assert GridPolicy.PHASE_PREOPT == "defgrid1"
    assert GridPolicy.PHASE_FINALOPT == "defgrid3"
    assert GridPolicy.PHASE_NUMFREQ == "defgrid3"

    assert GridPolicy.validate_grid("PHASE_PREOPT", "defgrid1") is True
    assert GridPolicy.validate_grid("PHASE_PREOPT", "defgrid3") is True
    assert GridPolicy.validate_grid("PHASE_FINALOPT", "defgrid3") is True

    # defgrid1 is forbidden for final opt and frequencies
    assert GridPolicy.validate_grid("PHASE_FINALOPT", "defgrid1") is False
    assert GridPolicy.validate_grid("PHASE_NUMFREQ", "defgrid1") is False


def test_interfaces_abc():
    """Verify ElectronicStructureExecutor and ConformerGenerator abstract interfaces."""
    from cochem_base.interfaces import ConformerGenerator, ElectronicStructureExecutor

    # Cannot instantiate ABC directly
    with pytest.raises(TypeError):
        ElectronicStructureExecutor()  # type: ignore

    with pytest.raises(TypeError):
        ConformerGenerator()  # type: ignore


# =============================================================================
# Phase 2: Zero-Mock CREST, Constraints Formatting, Deck Linter
# =============================================================================


def test_zero_mock_crest_raises_binary_not_found(monkeypatch):
    """Verify CREST runner strictly raises BinaryNotFoundError when executable is absent
    and has deleted the physical fallback generator.
    """
    from cochem_base.exceptions import BinaryNotFoundError
    from Libraries.cochem_torq_crest import CrestRunner

    runner = CrestRunner()
    # Ensure crest binary is not found
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("COCHEM_CREST_BIN", raising=False)
    monkeypatch.delenv("CREST_PATH", raising=False)

    # Check that _generate_physical_fallback_ensemble is deleted
    assert not hasattr(runner, "_generate_physical_fallback_ensemble")

    with tempfile.NamedTemporaryFile("w", suffix=".xyz", delete=False) as f:
        f.write("3\nwater\nO 0.0 0.0 0.0\nH 0.0 0.75 0.58\nH 0.0 -0.75 0.58\n")
        f_name = f.name

    try:
        with pytest.raises(BinaryNotFoundError) as excinfo:
            runner.run_crest(f_name)
        assert "[MISSING DATA]" in str(excinfo.value)
    finally:
        if os.path.exists(f_name):
            os.remove(f_name)


def test_orca_constraint_block_frozen_monomer():
    """Verify ORCA %geom constraint block formatting using generate_frozen_monomer_constraints."""
    from Libraries.cochem_torq_constraints import (
        generate_orca_frozen_monomer_constraints_block,
    )

    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = [
        [0.0, 0.0, 0.0],
        [0.0, 0.75, 0.58],
        [0.0, -0.75, 0.58],
        [3.0, 0.0, 0.0],
        [3.0, 0.75, 0.58],
        [3.0, -0.75, 0.58],
    ]
    atoms_a = [0, 1, 2]
    atoms_b = [3, 4, 5]

    block = generate_orca_frozen_monomer_constraints_block(atoms_a, atoms_b, symbols, coords)

    assert "%geom" in block
    assert "TolMaxG 1e-5" in block
    assert "TolE 1e-7" in block
    assert "Constraints" in block
    assert "{ B " in block  # Distance constraint
    assert "{ A " in block  # Angle constraint
    assert "end" in block


def test_deck_sanitizer_calc_hess_true():
    """Verify deck sanitizer detects and excises 'Calc_Hess true' during ! Opt routines,
    substituting InHess XTB2 (or Lindh).
    """
    from Libraries.cochem_torq_compiler import sanitize_orca_deck

    dirty_deck = (
        "! B3LYP def2-TZVP Opt\n"
        "%geom\n"
        "  Calc_Hess true\n"
        "  TolMaxG 1e-5\n"
        "end\n"
        "* xyz 0 1\n"
        "O 0.0 0.0 0.0\n"
        "*\n"
    )

    clean_deck, excised = sanitize_orca_deck(dirty_deck)
    assert excised is True
    assert "Calc_Hess true" not in clean_deck
    assert "InHess XTB2" in clean_deck or "InHess Lindh" in clean_deck


def test_catalog_compiler_grid_validation():
    """Verify cochem_catalog_compiler allows defgrid1 for PHASE_PREOPT and enforces defgrid3 for FINALOPT."""
    from Libraries.cochem_catalog_compiler import validate_catalog_grid

    # Preopt allows defgrid1
    assert validate_catalog_grid("defgrid1", phase="PHASE_PREOPT") is True
    assert validate_catalog_grid("defgrid3", phase="PHASE_PREOPT") is True

    # Finalopt / NumFreq rejects defgrid1
    assert validate_catalog_grid("defgrid1", phase="PHASE_FINALOPT") is False
    assert validate_catalog_grid("defgrid3", phase="PHASE_FINALOPT") is True


# =============================================================================
# Phase 3: Discrete Counterpoise, Spin Contamination, CFOUR Bridge
# =============================================================================


def test_discrete_counterpoise_evaluation():
    """Verify discrete 3-point counterpoise interaction energy calculation:
    Delta E_CP = E_AB^{AB} - E_A^{AB} - E_B^{AB} [M].
    """
    from Libraries.cochem_torq_engine import calculate_discrete_counterpoise_energy

    # E_AB = -152.000 Ha, E_A = -76.002 Ha (with B ghosts), E_B = -75.996 Ha (with A ghosts)
    e_ab = -152.000
    e_a_ghost = -76.002
    e_b_ghost = -75.996

    # Delta E = -152.000 - (-76.002) - (-75.996) = -152.000 + 151.998 = -0.002 Ha
    delta_e_cp = calculate_discrete_counterpoise_energy(e_ab, e_a_ghost, e_b_ghost)
    assert pytest.approx(delta_e_cp, abs=1e-6) == -0.002


def test_spin_contamination_gate():
    """Verify spin contamination checks in cochem_torq_engine halt with SpinContaminationError."""
    from cochem_base.exceptions import SpinContaminationError
    from Libraries.cochem_torq_engine import validate_spin_contamination

    # Multiplicity 1 (singlet): Ideal <S^2> = 0.0. Threshold <= 0.10
    s_ideal, s_obs, dev = validate_spin_contamination(multiplicity=1, s_squared_observed=0.02)
    assert s_ideal == 0.0
    assert s_obs == 0.02

    # Singlet exceeding 0.10
    with pytest.raises(SpinContaminationError) as excinfo:
        validate_spin_contamination(multiplicity=1, s_squared_observed=0.15)
    assert "ERR_SPIN_CONTAMINATION" in str(excinfo.value)

    # Multiplicity 2 (doublet): S = 0.5, Ideal <S^2> = 0.75. 10% tolerance = [0.675, 0.825]
    validate_spin_contamination(multiplicity=2, s_squared_observed=0.76)

    # Doublet with 15% contamination
    with pytest.raises(SpinContaminationError) as excinfo:
        validate_spin_contamination(multiplicity=2, s_squared_observed=0.90)
    assert "ERR_SPIN_CONTAMINATION" in str(excinfo.value)


def test_torq_parser_s2_regex():
    """Verify regex matching <S^2> with arbitrary spacing and exponent syntax (** or ^)."""
    from Libraries.cochem_torq_parser import parse_spin_contamination_s2

    sample_outputs = [
        "Expectation value of <S**2> :   0.754123",
        "Expectation value of <S^2>  : 0.751000",
        "< S**2 > : 1.050",
        "<  S ^ 2  > :  0.0023",
    ]

    expected_vals = [0.754123, 0.751000, 1.050, 0.0023]

    for text, expected in zip(sample_outputs, expected_vals):
        val = parse_spin_contamination_s2(text)
        assert val is not None
        assert pytest.approx(val, abs=1e-6) == expected


def test_torq_cfour_executor_scratch_and_interface(monkeypatch):
    """Verify TorqCfourExecutor executes in isolated scratch directory and inherits from ElectronicStructureExecutor."""
    from cochem_base.exceptions import BinaryNotFoundError
    from cochem_base.interfaces import ElectronicStructureExecutor
    from Libraries.cochem_torq_cfour_bridge import TorqCfourExecutor

    assert issubclass(TorqCfourExecutor, ElectronicStructureExecutor)

    # Unconfigured environment raises BinaryNotFoundError
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("CFOUR_ROOT", raising=False)
    monkeypatch.delenv("CFOUR_PATH", raising=False)
    monkeypatch.delenv("COCHEM_CFOUR_BIN", raising=False)

    executor = TorqCfourExecutor()
    with pytest.raises(BinaryNotFoundError) as excinfo:
        executor.run_cfour_job(
            job_name="test_water",
            symbols=["O", "H", "H"],
            coordinates=[[0.0, 0.0, 0.0], [0.0, 0.75, 0.58], [0.0, -0.75, 0.58]],
        )
    assert "[MISSING DATA]" in str(excinfo.value)
    assert "xcfour" in str(excinfo.value)


# =============================================================================
# Phase 4: TOPOS Unit Normalization, Persistence, and Screening Hessians
# =============================================================================


def test_topos_unit_normalization_and_screening_hessians():
    """Verify unit normalization (eV -> Hartree via CODATA 2022) and hessian=None in screening tiers."""
    import scipy.constants
    from cascade_engine.cochem_topos_cascade_orchestrator import (
        CascadeConfig,
        CascadeOrchestrator,
    )

    ev_to_ha_factor = scipy.constants.value("Hartree energy in eV")
    assert pytest.approx(ev_to_ha_factor, rel=1e-7) == 27.211386245988

    # Ensure screening tiers (Tier 1-3) return hessian=None in GradientPayload
    from ase.build import molecule

    water = molecule("H2O")
    with tempfile.TemporaryDirectory() as tmpdir:
        config = CascadeConfig(artifact_dir=Path(tmpdir))
        orchestrator = CascadeOrchestrator(config)

        # Tier 1 execution
        res_t1 = orchestrator._execute_hand_topology(water)
        assert res_t1.hessian is None
        assert res_t1.energy != 0.0


# =============================================================================
# Phase 5: Conformer Union & Concurrency in TORQ Pipeline
# =============================================================================


def test_torq_pipeline_conformer_union_and_concurrency():
    """Verify Stage 3 conformer union (GOAT + CREST) and concurrency management."""
    from Libraries.cochem_torq_pipeline import (
        deduplicate_conformer_union,
        resolve_concurrency_device,
    )

    # Concurrency test: safe CPU fallback when CUDA is not present
    device = resolve_concurrency_device()
    assert str(device) in ["cpu", "cuda:0", "mps"]

    # Conformer deduplication test: two conformers with nearly identical rotational constants and RMSD
    conf1 = {
        "rotational_constants_mhz": (1000.0, 500.0, 333.3),
        "coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        "symbols": ["H", "H"],
        "energy_hartree": -1.15,
        "origin": "GOAT",
    }
    # delta B / B = |501 - 500| / 500 = 0.002 < 0.005 threshold
    conf2 = {
        "rotational_constants_mhz": (1001.0, 501.0, 333.5),
        "coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.01]],
        "symbols": ["H", "H"],
        "energy_hartree": -1.149,
        "origin": "CREST",
    }
    union_pool = [conf1, conf2]
    deduped = deduplicate_conformer_union(union_pool, delta_b_rel_threshold=0.005, rmsd_threshold=0.15)
    # Conf1 and Conf2 should be merged into 1 unique conformer (preferring lower energy)
    assert len(deduped) == 1
    assert deduped[0]["energy_hartree"] == -1.15
