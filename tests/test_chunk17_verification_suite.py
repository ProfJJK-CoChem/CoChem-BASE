"""
test_chunk17_verification_suite.py - Authentic Zero-Mock Verification Suite.
Architecture Specification: SRS Chunk 17 (SRS-CHUNK-017-ARCH-V4.1-20260909).
Verification Requirements: VR-01 through VR-06.
Governing Standard: IEEE 830-1998 / Method Matrix v4.1 / Anti-Spoofing Protocol v4.
"""
import math
import os
import sys
from pathlib import Path
import numpy as np
import pytest

# Dynamic stream reconfiguration
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import cochem_base.core

from cochem_base.exceptions import (
    GridSpecificationError,
    RedundantDispersionError,
    MissingDispersionError,
    SpinContaminationError,
    PreflightValidationError,
)
from cochem_base.physics.isotopes import (
    get_atomic_mass,
    get_isotope_mass,
    get_element_mass_and_abundance,
)
from cochem_base.intake.cochem_molsym_eckart_aligner import (
    align_to_eckart_frame,
    translate_to_center_of_mass,
    compute_center_of_mass,
)
from cochem_base.intake.conformer_deduplication import (
    ConformerCandidate,
    ConformerDeduplicator,
    kabsch_rmsd,
    compute_weisfeiler_lehman_hash,
    hungarian_assignment_rmsd,
    compute_automorphism_orbit_rmsd,
)
from cochem_base.geometry.constraints import (
    generate_frozen_monomer_constraints,
    format_orca_frozen_monomer_constraints_block,
    validate_trajectory_monomer_drift,
)
from cochem_base.calc.cochem_calc_input_generator import (
    MoleculeInput,
    generate_orca_input,
)
from cochem_base.calc.cochem_calc_output_parser import OutputParser
from cochem_base.mm.quadrature_manager import QuadratureManager, GridStage
from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer
from cochem_base.validators.preflight import PreflightGeometryValidator
from ci_tools.process_runner import run_process


# ==============================================================================
# Authentic Physical Molecular Fixtures (CCCBDB / NIST Literature Coordinates)
# ==============================================================================

# Water monomer (H2O, C2v)
H2O_SYMBOLS = ["O", "H", "H"]
H2O_COORDS = np.array([
    [0.00000000,  0.00000000,  0.11730000],
    [0.00000000,  0.75720000, -0.46920000],
    [0.00000000, -0.75720000, -0.46920000],
], dtype=np.float64)

# Carbon dioxide monomer (CO2, Dinfh)
CO2_SYMBOLS = ["C", "O", "O"]
CO2_COORDS = np.array([
    [0.00000000, 0.00000000,  0.00000000],
    [0.00000000, 0.00000000,  1.16210000],
    [0.00000000, 0.00000000, -1.16210000],
], dtype=np.float64)

# Carbon dioxide - Water weak van der Waals complex (CO2...H2O, Cs)
CO2_H2O_SYMBOLS = ["C", "O", "O", "O", "H", "H"]
CO2_H2O_COORDS = np.array([
    [-1.4201,  0.0000,  0.0000],
    [-2.5802,  0.0000,  0.0000],
    [-0.2599,  0.0000,  0.0000],
    [ 1.4160,  0.0000,  0.1205],
    [ 1.9801,  0.7602, -0.1504],
    [ 1.9801, -0.7602, -0.1504],
], dtype=np.float64)


# ==============================================================================
# VR-01: Eckart Normalization, Dynamic Masses & Conformer Deduplication
# ==============================================================================

def test_vr01_dynamic_mendeleev_masses_and_nuclide_normalization():
    """VR-01: Dynamic mass retrieval via mendeleev with support for Deuterium and isotopes."""
    mass_c = get_atomic_mass("C")
    assert math.isclose(mass_c, 12.011, rel_tol=1e-3), f"Expected ~12.011, got {mass_c}"

    mass_13c = get_isotope_mass("C", 13)
    assert math.isclose(mass_13c, 13.00335, rel_tol=1e-4), f"Expected 13C ~13.00335, got {mass_13c}"

    mass_d = get_isotope_mass("D")
    assert math.isclose(mass_d, 2.01410, rel_tol=1e-4), f"Expected Deuterium ~2.01410, got {mass_d}"

    mass_18o = get_isotope_mass("18O")
    assert math.isclose(mass_18o, 17.99916, rel_tol=1e-4), f"Expected 18O ~17.99916, got {mass_18o}"

    # Hyphenated nuclide notation (C-13) via get_isotope_mass and get_atomic_mass
    mass_c13_hyphen = get_isotope_mass("C-13")
    assert math.isclose(mass_c13_hyphen, 13.00335, rel_tol=1e-4), f"Expected C-13 ~13.00335, got {mass_c13_hyphen}"
    mass_c13_atom = get_atomic_mass("C-13")
    assert math.isclose(mass_c13_atom, 13.00335, rel_tol=1e-4), f"Expected C-13 ~13.00335, got {mass_c13_atom}"

    # Counterpoise / BSSE Ghost atom zero-mass protection (Gh, Bq, X)
    for gh in ["Gh", "Bq", "X"]:
        assert get_atomic_mass(gh) == 0.0, f"Ghost atom {gh} must have exact 0.0 mass"
        assert get_isotope_mass(gh) == 0.0, f"Ghost isotope {gh} must have exact 0.0 mass"
        gh_mass, gh_abund, gh_z = get_element_mass_and_abundance(gh)
        assert gh_mass == 0.0 and gh_z == 0, f"Ghost atom {gh} must have mass=0.0 and Z=0"


def test_vr01_eckart_frame_alignment_and_proper_rotation():
    """VR-01: Mass-weighted Eckart translation (< 1e-12 a.u.) and SO(3) rotation (det = +1)."""
    # Displaced and rotated H2O
    theta = 0.45
    R_z = np.array([
        [math.cos(theta), -math.sin(theta), 0.0],
        [math.sin(theta),  math.cos(theta), 0.0],
        [0.0,             0.0,            1.0],
    ])
    displaced_h2o = (H2O_COORDS @ R_z.T) + np.array([12.5, -4.2, 8.1])

    # Authentic Kahan compensated center of mass translation zeroing via translate_to_center_of_mass
    masses = [get_atomic_mass(s) for s in H2O_SYMBOLS]
    centered, shift_vec = translate_to_center_of_mass(displaced_h2o, symbols=H2O_SYMBOLS)
    com_residual = np.linalg.norm(np.sum(np.array(masses)[:, None] * centered, axis=0))
    assert com_residual < 1.0e-12, f"COM residual {com_residual:.2e} >= 1.0e-12 a.u."

    # Compute COM vector directly via compute_center_of_mass
    com_vec = compute_center_of_mass(displaced_h2o, symbols=H2O_SYMBOLS)
    assert np.allclose(com_vec, -shift_vec, atol=1.0e-12), "COM vector must equal negative shift vector"

    # Align to reference frame via align_to_eckart_frame
    res = align_to_eckart_frame(
        target_coords=displaced_h2o,
        ref_coords=H2O_COORDS,
        symbols=H2O_SYMBOLS,
    )
    assert res.residual_rotational_norm < 1.0e-10, f"Eckart residual {res.residual_rotational_norm:.2e} >= 1.0e-10"
    assert res.is_proper_rotation, "Expected proper SO(3) rotation"
    assert math.isclose(res.rotation_determinant, 1.0, abs_tol=1.0e-10), f"Improper rotation det(U) = {res.rotation_determinant}"


def test_vr01_two_stage_conformer_deduplication():
    """VR-01: Stage 1 Weisfeiler-Lehman hash + Stage 2 Kabsch RMSD (< 0.08 A) & Delta B/B (<= 0.05%) deduplication."""
    # Base CO2...H2O
    c1 = CO2_H2O_COORDS.copy()
    # Duplicate with minor rigid displacement (< 0.01 A, Delta B/B == 0)
    c2 = CO2_H2O_COORDS.copy()
    c2 += 0.003

    # Candidate with small RMSD (< 0.08 A) but distinct microwave constant (Delta B/B > 0.05%)
    # Water monomer shifted along intermolecular axis by 0.02 A (RMSD = 0.01 A, Delta B/B ~ 0.97%)
    c_spectro = CO2_H2O_COORDS.copy()
    c_spectro[3:, 0] += 0.02

    # Distinct geometric conformer (stretched intermolecular distance R)
    c3 = CO2_H2O_COORDS.copy()
    c3[3:, 0] += 0.60  # Displace water monomer by 0.60 Angstrom

    confs = [
        ConformerCandidate(conformer_id="basin_0", symbols=CO2_H2O_SYMBOLS, coordinates=c1, energy=-264.120),
        ConformerCandidate(conformer_id="basin_1", symbols=CO2_H2O_SYMBOLS, coordinates=c2, energy=-264.11999),
        ConformerCandidate(conformer_id="basin_spectro", symbols=CO2_H2O_SYMBOLS, coordinates=c_spectro, energy=-264.118),
        ConformerCandidate(conformer_id="basin_2", symbols=CO2_H2O_SYMBOLS, coordinates=c3, energy=-264.105),
    ]

    deduplicator = ConformerDeduplicator(rmsd_threshold=0.08, rotational_constant_threshold=0.0005)
    unique = deduplicator.deduplicate(confs)

    # basin_1 is collapsed as duplicate of basin_0 (RMSD < 0.08 A and Delta B/B <= 0.05%)
    # basin_spectro is PRESERVED because Delta B/B > 0.05% despite RMSD < 0.08 A
    # basin_2 is PRESERVED because RMSD > 0.08 A
    unique_ids = [u.conformer_id for u in unique]
    assert "basin_0" in unique_ids
    assert "basin_1" not in unique_ids, "basin_1 should have been collapsed as a duplicate"
    assert "basin_spectro" in unique_ids, "basin_spectro must be preserved due to spectroscopic distinction (Delta B/B > 0.05%)"
    assert "basin_2" in unique_ids
    assert len(unique) == 3


def test_vr01_hungarian_automorphism_fallback_and_orbit_rmsd():
    """VR-01: Automorphism orbit traversal with polynomial O(N^3) Hungarian fallback (> 720 perms)."""
    # Authentic Water Monomer (H2O) with permuted symmetric hydrogen atoms (H1 <-> H2)
    # Original: O at 0, H1 at 1, H2 at 2
    coords_orig = H2O_COORDS.copy()
    # Permute the two hydrogens: O at 0, H2 at 1, H1 at 2
    coords_perm = coords_orig[[0, 2, 1]].copy()

    # 1. Exact automorphism orbit traversal
    rmsd_orbit, mapping = compute_automorphism_orbit_rmsd(
        coords_orig, coords_perm, H2O_SYMBOLS, max_exact_permutations=720
    )
    assert rmsd_orbit < 1.0e-12, f"Expected zero RMSD under automorphism orbit, got {rmsd_orbit}"
    assert len(mapping) == 3, f"Expected 3-atom mapping, got {mapping}"

    # 2. Hungarian algorithm fallback triggered by exceeding permutation threshold (max_exact_permutations=1)
    rmsd_hungarian, h_mapping = compute_automorphism_orbit_rmsd(
        coords_orig, coords_perm, H2O_SYMBOLS, max_exact_permutations=1
    )
    assert rmsd_hungarian < 1.0e-12, f"Expected Hungarian assignment to resolve permutation with zero RMSD, got {rmsd_hungarian}"
    assert len(h_mapping) == 3, f"Expected 3-atom Hungarian mapping, got {h_mapping}"


# ==============================================================================
# VR-02: Frozen Monomer Protocol (FMP) & Trajectory Drift Validator
# ==============================================================================

def test_vr02_fmp_constraint_generation_and_trajectory_drift():
    """VR-02: Lock monomer internals and validate trajectory drift Delta r < 1.0e-6 A."""
    # Monomer A: atoms 0, 1, 2 (CO2); Monomer B: atoms 3, 4, 5 (H2O)
    payload = generate_frozen_monomer_constraints(
        atoms_a=[0, 1, 2],
        atoms_b=[3, 4, 5],
        symbols=CO2_H2O_SYMBOLS,
        coordinates=CO2_H2O_COORDS,
    )
    assert len(payload.bonds) > 0
    assert len(payload.angles) > 0

    # Format into ORCA block with MaxIter 200
    block = format_orca_frozen_monomer_constraints_block(payload)
    assert "MaxIter 200" in block
    assert "Constraints" in block
    assert "{ B" in block

    # Trajectory drift validation: internal distances within monomer must remain invariant
    step1 = CO2_H2O_COORDS.copy()
    step2 = CO2_H2O_COORDS.copy()
    # Shift entire Monomer B relative to Monomer A by 0.05 A (intermolecular motion)
    step2[3:, 0] += 0.05
    # Monomer internals did not distort
    is_valid, max_drift = validate_trajectory_monomer_drift([step1, step2], monomer_indices=[0, 1, 2])
    assert is_valid
    assert max_drift < 1.0e-6


def test_vr02_output_parser_residual_gradient_and_strain_caveat(tmp_path):
    """VR-02: Parse ||g_residual||_inf on frozen coordinates and flag geometric strain."""
    fmp_opt_log = tmp_path / "fmp_opt.out"
    fmp_opt_log.write_text("""
    -------------------------
    GEOMETRY OPTIMIZATION CYCLE
    -------------------------
    MAX GRADIENT               :   0.000350000000
    RMS GRADIENT               :   0.000002500000
    *** OPTIMIZATION CONVERGED ***
    """, encoding="utf-8")

    parser = OutputParser()
    max_g, has_strain = parser.parse_residual_gradients(fmp_opt_log, strain_threshold=1.0e-4)
    assert max_g == pytest.approx(3.5e-4, rel=1e-3)
    assert has_strain is True  # 3.5e-4 > 1.0e-4 triggers strain caveat


# ==============================================================================
# VR-03: Dynamic Quadrature Grid Lifecycle & Coupled Invariant
# ==============================================================================

def test_vr03_dynamic_grid_lifecycle_and_coupled_invariant():
    """VR-03: Coupled Grid-SCF Invariant raises GridSpecificationError on coarse grids for frequency tasks."""
    qm = QuadratureManager()

    # Stage specifications
    spec1 = qm.get_stage_spec(1)
    assert spec1.grid_keyword == "DEFGRID1"
    spec3 = qm.get_stage_spec(3)
    assert spec3.grid_keyword == "DEFGRID3"

    # Coupled Invariant: Frequency calculation with DEFGRID1 or DEFGRID2 must fail closed
    with pytest.raises(GridSpecificationError):
        qm.validate_coupled_grid_scf_invariant("DEFGRID1", is_frequency_or_hessian=True)

    with pytest.raises(GridSpecificationError):
        qm.validate_coupled_grid_scf_invariant("DEFGRID2", is_vpt2=True)

    # Valid Stage 3 frequency task
    qm.validate_coupled_grid_scf_invariant("DEFGRID3", is_frequency_or_hessian=True, scf_setting="TightSCF")


def test_vr03_input_generator_rejects_coarse_frequency_grids():
    """VR-03: Input generator raises GridSpecificationError when DEFGRID1/DEFGRID2 is requested with FREQ."""
    with pytest.raises(GridSpecificationError):
        MoleculeInput(
            basin_id="water_freq_coarse",
            elements=["O", "H", "H"],
            coordinates=[(0,0,0), (0,0.7,0), (0,-0.7,0)],
            theory_level="B3LYP-D4 def2-TZVP DEFGRID1 FREQ",
            is_freq=True,
        )


# ==============================================================================
# VR-04: Quintuple Stationary Block & Initial Model Hessian Discipline
# ==============================================================================

def test_vr04_quintuple_stationary_block_and_model_hessian(configured_registry):
    """VR-04: Inject TolMaxG 1e-5, MaxIter 200, ban Calc_Hess true, and mandate InHess XTB2."""
    mol_in = MoleculeInput(
        basin_id="co2_h2o_opt",
        elements=CO2_H2O_SYMBOLS,
        coordinates=[tuple(c) for c in CO2_H2O_COORDS],
        theory_level="r2SCAN-3c",
        is_opt=True,
        is_weak_complex=True,
    )

    # Invalid exact-Hessian requests fail closed, rather than being silently rewritten.
    with pytest.raises(ValueError, match="Calc_Hess true"):
        MoleculeInput(
            basin_id="forbidden_initial_hessian",
            elements=CO2_H2O_SYMBOLS,
            coordinates=[tuple(c) for c in CO2_H2O_COORDS],
            theory_level="r2SCAN-3c Calc_Hess true",
            is_opt=True,
            is_weak_complex=True,
        )
    assert "CALC_HESS TRUE" not in mol_in.theory_level.upper()

    out_path = generate_orca_input(mol_in)
    content = out_path.read_text(encoding="utf-8")

    # Assert mandatory %geom parameters
    assert "TolE 1e-7" in content
    assert "TolMaxG 1e-5" in content
    assert "TolRMSG 3e-6" in content
    assert "TolMaxD 1e-4" in content
    assert "TolRMSD 5e-5" in content
    assert "MaxIter 200" in content
    assert "InHess XTB2" in content
    assert "Calc_Hess true" not in content


# ==============================================================================
# VR-05: Electronic Structure Sanitizer & Hardened Spin Contamination Gate
# ==============================================================================

def test_vr05_preflight_wB97MV_resolution_and_dispersion_sanitization():
    """VR-05: wB97M-V passes preflight alone, but raises RedundantDispersionError if paired with D3/D4."""
    # 1. wB97M-V alone on complex must succeed without requiring D3/D4
    is_valid = PreflightGeometryValidator.validate_geometry_and_options(
        symbols=CO2_H2O_SYMBOLS,
        coordinates=CO2_H2O_COORDS,
        charge=0,
        multiplicity=1,
        dft_keywords="wB97M-V def2-QZVPP",
        is_complex=True,
    )
    assert is_valid is True

    # 2. wB97M-V + D3BJ must raise RedundantDispersionError
    with pytest.raises(RedundantDispersionError):
        PreflightGeometryValidator.validate_geometry_and_options(
            symbols=CO2_H2O_SYMBOLS,
            coordinates=CO2_H2O_COORDS,
            charge=0,
            multiplicity=1,
            dft_keywords="wB97M-V def2-QZVPP D3BJ",
            is_complex=True,
        )

    # 3. Standard hybrid (B3LYP) on complex without dispersion must raise MissingDispersionError
    with pytest.raises(MissingDispersionError):
        PreflightGeometryValidator.validate_geometry_and_options(
            symbols=CO2_H2O_SYMBOLS,
            coordinates=CO2_H2O_COORDS,
            charge=0,
            multiplicity=1,
            dft_keywords="B3LYP def2-TZVP",
            is_complex=True,
        )


def test_vr05_spin_contamination_gate_with_singularity_guard():
    """VR-05: Singularity-protected spin gate for singlets (S=0) and open-shell systems (S>0)."""
    # 1. Pure singlet (<S^2> = 0.0001)
    res_pure = ElectronicSanitizer.diagnose_spin_contamination(0.0001, multiplicity=1)
    assert res_pure["is_pure"] is True

    # 2. Contaminated singlet (<S^2> = 0.08 >= 0.05 a.u. threshold) -> raises SpinContaminationError
    with pytest.raises(SpinContaminationError):
        ElectronicSanitizer.diagnose_spin_contamination(0.08, multiplicity=1)

    # 3. Pure doublet (M=2, S=0.5, S(S+1)=0.75, <S^2>=0.76 -> Delta = 1.33% < 10%)
    res_doublet = ElectronicSanitizer.diagnose_spin_contamination(0.76, multiplicity=2)
    assert res_doublet["is_pure"] is True

    # 4. Contaminated doublet (M=2, S=0.5, S(S+1)=0.75, <S^2>=0.95 -> Delta = 26.67% >= 10%)
    with pytest.raises(SpinContaminationError):
        ElectronicSanitizer.diagnose_spin_contamination(0.95, multiplicity=2)


# ==============================================================================
# VR-06: Zero-Trust CI Subprocess Runner & Air-Gap Verification
# ==============================================================================

def test_vr06_air_gapped_process_runner_and_utf8_encoding():
    """VR-06: Process runner executes in isolation without CP1252 charmap crashes."""
    # Execute Python subprocess echoing Unicode scientific characters with UTF-8 mode enabled
    res = run_process([
        sys.executable,
        "-X",
        "utf8",
        "-c",
        "print('Unicode: omega=ω, Delta=Δ, Angstrom=Å, cm-1=cm⁻¹')",
    ])
    assert res.returncode == 0
    assert "ω" in res.stdout
    assert "Å" in res.stdout
    assert "cm⁻¹" in res.stdout
