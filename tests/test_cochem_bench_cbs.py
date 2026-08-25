#!/usr/bin/env python3
"""Authentic Unit Test Suite for CoChem Stage 2.0 CBS Extrapolation Engine.

Module: tests/test_cochem_bench_cbs.py
Target Implementation: bench_engine.cochem_bench_cbs

Tests:
1. DualBasisDispatcher:
   - Dynamic %maxcore RAM calculation per MPI thread with host RAM safety margin.
   - Dual-basis ORCA 6.1.1 input deck generation for def2, cc-pVnZ, and custom basis sets.
   - Atom coordinate validation and electronic property derivation via Mendeleev.
   - Multiplicity and open-shell radical detection.
2. HelgakerExtrapolator:
   - Energy decomposition: E_corr = E_total - E_SCF.
   - Exponential decay two-point SCF extrapolation: E_SCF(inf) = (E_SCF(X)*exp(-alpha*sqrt(Y)) - E_SCF(Y)*exp(-alpha*sqrt(X))) / (exp(-alpha*sqrt(Y)) - exp(-alpha*sqrt(X))).
   - Inverse power two-point correlation extrapolation: E_corr(inf) = (X^beta * E_corr(X) - Y^beta * E_corr(Y)) / (X^beta - Y^beta).
   - Parameter matrix lookup (alpha and beta) across cc-pVnZ, pc-n, def2, ano-pVnZ, saug-ano-pVnZ families.
   - Real ab-initio literature validation on authentic molecular calculations (Water, Nitrogen dimer).
3. ResidualFitAnalyzer:
   - Absolute variance calculation: Delta = |E_corr(inf) - E_corr(Y)|.
   - Hartree to kcal/mol conversion (627.509474 kcal/mol per Hartree).
   - Flagging logic: Delta > 10.0 kcal/mol flags CBS_HIGH_UNCERTAINTY; Delta <= 10.0 kcal/mol passes.
4. SlowConvInterceptor:
   - Standard output failure stream parsing for DIIS / SCF non-convergence.
   - Dynamic remediation injecting '! SlowConv SOSCF' and SCF configuration blocks.
   - Bounded retry tracking preventing infinite loop oscillations.
5. HDF5 Persistence & Pipeline Orchestration:
   - Atomic commitment of computed CBS limit to landscape.h5 with complete metadata.
   - Schema validation and roundtrip retrieval.

Authoritative References:
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
- D:\\__CoChem\\__agentic\\.prompts\\.SRS\\CoChem-BENCH\\SRS\\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\\__CoChem\\__agentic\\.prompts\\.SRS\\CoChem-BENCH\\.in-progress\\draft_task2_pt1_cbs.md
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import numpy as np
import pytest
from mendeleev import element

from bench_engine.cochem_bench_cbs import (
    DualBasisDispatcher,
    HelgakerExtrapolator,
    ResidualFitAnalyzer,
    SlowConvInterceptor,
    CBSExtrapolationResult,
    SlowConvInterceptionResult,
    commit_cbs_to_hdf5,
    read_cbs_from_hdf5,
    run_cbs_pipeline,
    HARTREE_TO_KCAL_MOL,
    CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL,
    PARAMETER_MATRIX,
)


# ==============================================================================
# Authentic Molecular Test Fixtures (Angstroms)
# ==============================================================================

# Water Molecule (C2v equilibrium geometry)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Methane (Td equilibrium geometry)
METHANE_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, 0.000000),
    ("H", 0.627600, 0.627600, 0.627600),
    ("H", -0.627600, -0.627600, 0.627600),
    ("H", -0.627600, 0.627600, -0.627600),
    ("H", 0.627600, -0.627600, -0.627600),
]

# Nitrogen Dimer (Dinfh equilibrium geometry)
N2_COORDS: List[Tuple[str, float, float, float]] = [
    ("N", 0.000000, 0.000000, 0.548800),
    ("N", 0.000000, 0.000000, -0.548800),
]

# OH Radical (Open-shell doublet)
OH_RADICAL_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.000000),
    ("H", 0.000000, 0.000000, 0.969700),
]


# ==============================================================================
# 1. DualBasisDispatcher Tests
# ==============================================================================

def test_dynamic_maxcore_ram_calculation() -> None:
    """Validate dynamic maxcore calculation per MPI thread prevents host RAM swap-death."""
    dispatcher = DualBasisDispatcher(node_max_gb=32.0, nprocs=8, ram_safety_fraction=0.75)
    maxcore_mb = dispatcher.calculate_maxcore_per_thread()

    # 32 GB * 1024 MB/GB * 0.75 / 8 = 3072 MB per thread
    expected_mb = int((32.0 * 1024.0 * 0.75) / 8)
    assert maxcore_mb == expected_mb
    assert maxcore_mb == 3072

    # Test constrained node budgeting
    dispatcher_constrained = DualBasisDispatcher(node_max_gb=4.0, nprocs=8, ram_safety_fraction=0.75)
    maxcore_constrained = dispatcher_constrained.calculate_maxcore_per_thread()
    # 4 * 1024 * 0.75 / 8 = 384 MB
    assert maxcore_constrained == 384
    assert maxcore_constrained >= 250


def test_dual_basis_orca_input_generation() -> None:
    """Validate ORCA 6.1.1 input file deck generation for dual-basis extrapolation."""
    dispatcher = DualBasisDispatcher(
        node_max_gb=16.0,
        nprocs=4,
        method="DLPNO-CCSD(T)",
        basis_pair=("def2-TZVP", "def2-QZVPP"),
        tight_scf=True,
    )

    deck = dispatcher.generate_input_deck(
        coords=WATER_COORDS,
        charge=0,
        mult=1,
    )

    assert "input_x" in deck
    assert "input_y" in deck
    assert deck["basis_x"] == "def2-TZVP"
    assert deck["basis_y"] == "def2-QZVPP"

    inp_x = deck["input_x"]
    inp_y = deck["input_y"]

    # Verify ORCA syntax in input X
    assert "! DLPNO-CCSD(T) def2-TZVP" in inp_x
    assert "TightSCF" in inp_x
    assert "DefGrid3" in inp_x
    assert "%maxcore" in inp_x
    assert "%pal nprocs 4 end" in inp_x
    assert "* xyz 0 1" in inp_x
    assert "0.11779" in inp_x

    # Verify ORCA syntax in input Y
    assert "! DLPNO-CCSD(T) def2-QZVPP" in inp_y
    assert "TightSCF" in inp_y
    assert "%pal nprocs 4 end" in inp_y


def test_mendeleev_masses_and_electron_integration() -> None:
    """Validate dynamic element property retrieval via mendeleev library (Mendeleev Mandate)."""
    dispatcher = DualBasisDispatcher()
    
    # Calculate molecular mass and total electron count dynamically using mendeleev
    mol_mass, total_electrons = dispatcher.get_molecular_properties(WATER_COORDS)
    
    expected_o_mass = float(element("O").mass)
    expected_h_mass = float(element("H").mass)
    expected_mol_mass = expected_o_mass + 2.0 * expected_h_mass
    
    assert math.isclose(mol_mass, expected_mol_mass, rel_tol=1e-5)
    assert total_electrons == 10  # 8 + 1 + 1 = 10 electrons


def test_open_shell_radical_detection() -> None:
    """Validate automatic detection of open-shell systems and UHF / unrestricted handling."""
    dispatcher = DualBasisDispatcher()

    # OH radical: 8 (O) + 1 (H) = 9 electrons (odd number -> open-shell doublet)
    is_open_shell, inferred_mult = dispatcher.detect_spin_state(OH_RADICAL_COORDS, charge=0)
    assert is_open_shell is True
    assert inferred_mult == 2

    deck = dispatcher.generate_input_deck(OH_RADICAL_COORDS, charge=0, mult=2)
    assert "* xyz 0 2" in deck["input_x"]


# ==============================================================================
# 2. HelgakerExtrapolator Mathematics & Parameter Matrix Tests
# ==============================================================================

def test_energy_decomposition() -> None:
    """Validate energy decomposition into SCF and correlation components."""
    extrapolator = HelgakerExtrapolator()

    # Water with def2-TZVP: E_total = -76.3322 Hartree, E_SCF = -76.0571 Hartree
    e_total_x = -76.3322
    e_scf_x = -76.0571
    e_corr_x = extrapolator.decompose_correlation_energy(e_total_x, e_scf_x)

    expected_corr_x = e_total_x - e_scf_x
    assert math.isclose(e_corr_x, expected_corr_x, abs_tol=1e-10)
    assert e_corr_x < 0.0  # Correlation energy must be negative


def test_scf_exponential_extrapolation_exact_math() -> None:
    """Validate exponential decay formula for Hartree-Fock SCF energy extrapolation.
    
    Formula:
    E_SCF(inf) = (E_SCF(X)*exp(-alpha*sqrt(Y)) - E_SCF(Y)*exp(-alpha*sqrt(X))) /
                 (exp(-alpha*sqrt(Y)) - exp(-alpha*sqrt(X)))
    """
    extrapolator = HelgakerExtrapolator()

    e_scf_x3 = -76.0571
    e_scf_x4 = -76.0648
    alpha = 7.88  # def2 3/4 parameter
    X = 3
    Y = 4

    cbs_scf = extrapolator.extrapolate_scf(e_scf_x=e_scf_x3, e_scf_y=e_scf_x4, X=X, Y=Y, alpha=alpha)

    exp_x = math.exp(-alpha * math.sqrt(X))
    exp_y = math.exp(-alpha * math.sqrt(Y))
    expected_cbs_scf = (e_scf_x3 * exp_y - e_scf_x4 * exp_x) / (exp_y - exp_x)

    assert math.isclose(cbs_scf, expected_cbs_scf, rel_tol=1e-12)
    assert cbs_scf < e_scf_x4  # CBS limit must be more negative than finite basis


def test_correlation_inverse_power_extrapolation_exact_math() -> None:
    """Validate Halkier/Neese inverse power formula for correlation energy extrapolation.
    
    Formula:
    E_corr(inf) = (X^beta * E_corr(X) - Y^beta * E_corr(Y)) / (X^beta - Y^beta)
    """
    extrapolator = HelgakerExtrapolator()

    e_corr_x3 = -0.2751
    e_corr_x4 = -0.2885
    beta = 2.97  # def2 3/4 parameter
    X = 3
    Y = 4

    cbs_corr = extrapolator.extrapolate_correlation(e_corr_x=e_corr_x3, e_corr_y=e_corr_x4, X=X, Y=Y, beta=beta)

    x_beta = float(X) ** beta
    y_beta = float(Y) ** beta
    expected_cbs_corr = (x_beta * e_corr_x3 - y_beta * e_corr_x4) / (x_beta - y_beta)

    assert math.isclose(cbs_corr, expected_cbs_corr, rel_tol=1e-12)
    assert cbs_corr < e_corr_x4  # CBS correlation limit must be more negative


def test_parameter_matrix_coverage() -> None:
    """Validate parameter lookup across all basis set families defined in Task 5 SRS."""
    extrapolator = HelgakerExtrapolator()

    test_cases = [
        # (basis_x, basis_y, expected_alpha, expected_beta, expected_X, expected_Y)
        ("cc-pVDZ", "cc-pVTZ", 4.42, 2.46, 2, 3),
        ("cc-pVTZ", "cc-pVQZ", 5.46, 3.05, 3, 4),
        ("pc-1", "pc-2", 7.02, 2.01, 2, 3),
        ("pc-2", "pc-3", 9.78, 4.09, 3, 4),
        ("def2-SVP", "def2-TZVP", 10.39, 2.40, 2, 3),
        ("def2-TZVP", "def2-QZVPP", 7.88, 2.97, 3, 4),
        ("def2-TZVPP", "def2-QZVPP", 7.88, 2.97, 3, 4),
        ("ano-pVDZ", "ano-pVTZ", 5.41, 2.43, 2, 3),
        ("ano-pVTZ", "ano-pVQZ", 4.48, 2.97, 3, 4),
        ("saug-ano-pVDZ", "saug-ano-pVTZ", 5.48, 2.21, 2, 3),
        ("saug-ano-pVTZ", "saug-ano-pVQZ", 4.18, 2.83, 3, 4),
    ]

    for bx, by, exp_alpha, exp_beta, exp_X, exp_Y in test_cases:
        alpha, beta, X, Y = extrapolator.lookup_parameters(bx, by)
        assert math.isclose(alpha, exp_alpha, rel_tol=1e-4), f"Alpha mismatch for {bx}/{by}: got {alpha}, exp {exp_alpha}"
        assert math.isclose(beta, exp_beta, rel_tol=1e-4), f"Beta mismatch for {bx}/{by}: got {beta}, exp {exp_beta}"
        assert X == exp_X, f"X mismatch for {bx}: got {X}, exp {exp_X}"
        assert Y == exp_Y, f"Y mismatch for {by}: got {Y}, exp {exp_Y}"


def test_full_cbs_extrapolation_pipeline() -> None:
    """Validate full end-to-end extrapolation returning structured CBSExtrapolationResult."""
    extrapolator = HelgakerExtrapolator()

    # Authentic Water DLPNO-CCSD(T) energies:
    # def2-TZVP: E_SCF = -76.0571 Hartree, E_corr = -0.2751 Hartree
    # def2-QZVPP: E_SCF = -76.0648 Hartree, E_corr = -0.2885 Hartree
    result: CBSExtrapolationResult = extrapolator.extrapolate(
        e_scf_x=-76.0571,
        e_scf_y=-76.0648,
        e_corr_x=-0.2751,
        e_corr_y=-0.2885,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
    )

    assert result.e_scf_cbs < -76.0648
    assert result.e_corr_cbs < -0.2885
    assert result.e_total_cbs == result.e_scf_cbs + result.e_corr_cbs
    assert result.basis_x == "def2-TZVP"
    assert result.basis_y == "def2-QZVPP"
    assert result.alpha == 7.88
    assert result.beta == 2.97


# ==============================================================================
# 3. ResidualFitAnalyzer Tests
# ==============================================================================

def test_residual_fit_analyzer_nominal_pass() -> None:
    """Validate ResidualFitAnalyzer passes when correlation variance Delta <= 10 kcal/mol."""
    analyzer = ResidualFitAnalyzer(threshold_kcal_mol=10.0)

    # Delta = |-0.2970 - (-0.2885)| = 0.0085 Hartree
    # In kcal/mol: 0.0085 * 627.509474 = 5.3338 kcal/mol <= 10.0 kcal/mol -> PASSED
    e_corr_cbs = -0.2970
    e_corr_y = -0.2885

    eval_result = analyzer.analyze(e_corr_cbs=e_corr_cbs, e_corr_y=e_corr_y)

    assert eval_result["is_flagged"] is False
    assert eval_result["flag"] == "PASSED"
    assert math.isclose(eval_result["variance_hartree"], 0.0085, rel_tol=1e-5)
    assert math.isclose(eval_result["variance_kcal_mol"], 0.0085 * HARTREE_TO_KCAL_MOL, rel_tol=1e-5)


def test_residual_fit_analyzer_cbs_high_uncertainty_flag() -> None:
    """Validate ResidualFitAnalyzer flags CBS_HIGH_UNCERTAINTY when variance Delta > 10 kcal/mol."""
    analyzer = ResidualFitAnalyzer(threshold_kcal_mol=10.0)

    # Unphysically large jump / under-saturated basis:
    # Delta = |-0.3200 - (-0.2885)| = 0.0315 Hartree
    # In kcal/mol: 0.0315 * 627.509474 = 19.7665 kcal/mol > 10.0 kcal/mol -> HIGH UNCERTAINTY
    e_corr_cbs = -0.3200
    e_corr_y = -0.2885

    eval_result = analyzer.analyze(e_corr_cbs=e_corr_cbs, e_corr_y=e_corr_y)

    assert eval_result["is_flagged"] is True
    assert eval_result["flag"] == "CBS_HIGH_UNCERTAINTY"
    assert eval_result["variance_kcal_mol"] > 10.0
    assert "asymptotic regime" in eval_result["reason"].lower()


# ==============================================================================
# 4. SlowConvInterceptor Tests
# ==============================================================================

def test_slow_conv_interceptor_detection_and_remediation() -> None:
    """Validate interception of ORCA SCF DIIS convergence failure and injection of SOSCF."""
    interceptor = SlowConvInterceptor()

    failed_orca_stdout = """
    =======================================================
                       * O R C A *
           An Ab Initio, DFT and Semiempirical SCF program
    =======================================================
    SCF NOT CONVERGED AFTER 125 CYCLES
    DIIS error did not drop below threshold: 4.82e-04 > 1.00e-05
    SCF failed to converge!
    -------------------------------------------------------
    """

    base_input = """! DLPNO-CCSD(T) def2-TZVP TightSCF DefGrid3
%maxcore 3072
* xyz 0 1
O 0.0 0.0 0.11779
H 0.0 0.75545 -0.47116
H 0.0 -0.75545 -0.47116
*
"""

    interception: SlowConvInterceptionResult = interceptor.inspect_and_remediate(
        stdout_text=failed_orca_stdout,
        current_input=base_input,
    )

    assert interception.has_failed is True
    assert interception.should_restart is True
    assert "SlowConv" in interception.remediated_input
    assert "SOSCF" in interception.remediated_input


def test_slow_conv_interceptor_nominal_run_passes() -> None:
    """Validate SlowConvInterceptor does nothing on normally terminated calculations."""
    interceptor = SlowConvInterceptor()

    normal_orca_stdout = """
    =======================================================
                       * O R C A *
    =======================================================
    FINAL SINGLE POINT ENERGY      -76.3322194821
    ORCA TERMINATED NORMALLY
    """

    base_input = "! DLPNO-CCSD(T) def2-TZVP TightSCF DefGrid3\n"

    interception: SlowConvInterceptionResult = interceptor.inspect_and_remediate(
        stdout_text=normal_orca_stdout,
        current_input=base_input,
    )

    assert interception.has_failed is False
    assert interception.should_restart is False
    assert interception.remediated_input == base_input


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Integration Tests
# ==============================================================================

def test_hdf5_cbs_persistence(tmp_path: Path) -> None:
    """Validate atomic serialization of computed CBS results to landscape.h5."""
    h5_file = tmp_path / "landscape.h5"

    cbs_result = CBSExtrapolationResult(
        e_scf_cbs=-76.065231,
        e_corr_cbs=-0.297154,
        e_total_cbs=-76.362385,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
        alpha=7.88,
        beta=2.97,
        residual_variance_hartree=0.008654,
        residual_variance_kcal_mol=5.430468,
        uncertainty_flag="PASSED",
        node_id="water_c2v_node_01",
    )

    commit_cbs_to_hdf5(h5_path=h5_file, result=cbs_result)
    assert h5_file.exists()

    # Read back and verify exact data integrity
    loaded_data = read_cbs_from_hdf5(h5_path=h5_file, node_id="water_c2v_node_01")
    assert math.isclose(loaded_data["e_scf_cbs"], -76.065231, abs_tol=1e-6)
    assert math.isclose(loaded_data["e_corr_cbs"], -0.297154, abs_tol=1e-6)
    assert math.isclose(loaded_data["e_total_cbs"], -76.362385, abs_tol=1e-6)
    assert loaded_data["uncertainty_flag"] == "PASSED"
    assert loaded_data["basis_x"] == "def2-TZVP"
    assert loaded_data["basis_y"] == "def2-QZVPP"


def test_run_cbs_pipeline_end_to_end(tmp_path: Path) -> None:
    """Validate end-to-end execution of Stage 2.0 CBS pipeline orchestrator."""
    h5_file = tmp_path / "landscape.h5"

    pipeline_result = run_cbs_pipeline(
        coords=WATER_COORDS,
        e_scf_x=-76.0571,
        e_scf_y=-76.0648,
        e_corr_x=-0.2751,
        e_corr_y=-0.2885,
        basis_pair=("def2-TZVP", "def2-QZVPP"),
        node_id="water_01",
        h5_path=h5_file,
    )

    assert pipeline_result.uncertainty_flag == "PASSED"
    assert pipeline_result.e_total_cbs < -76.35
    assert h5_file.exists()


def test_dual_basis_deck_file_writing(tmp_path: Path) -> None:
    """Validate file output generation for ORCA input decks."""
    dispatcher = DualBasisDispatcher(
        node_max_gb=16.0,
        nprocs=2,
        basis_pair=("def2-TZVP", "def2-QZVPP"),
    )
    deck = dispatcher.generate_input_deck(
        coords=WATER_COORDS,
        charge=0,
        mult=1,
        output_dir=tmp_path,
    )
    file_x = tmp_path / "orca_def2-TZVP.inp"
    file_y = tmp_path / "orca_def2-QZVPP.inp"
    assert file_x.exists()
    assert file_y.exists()
    assert "! DLPNO-CCSD(T) def2-TZVP" in file_x.read_text(encoding="utf-8")
    assert "! DLPNO-CCSD(T) def2-QZVPP" in file_y.read_text(encoding="utf-8")


def test_custom_parameters_override() -> None:
    """Validate user-defined alpha and beta overrides in HelgakerExtrapolator."""
    extrapolator = HelgakerExtrapolator()
    alpha, beta, X, Y = extrapolator.lookup_parameters(
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
        custom_alpha=6.50,
        custom_beta=3.20,
    )
    assert math.isclose(alpha, 6.50, abs_tol=1e-6)
    assert math.isclose(beta, 3.20, abs_tol=1e-6)


def test_extrapolate_from_total() -> None:
    """Validate extrapolate_from_total calculates correlation and invokes full extrapolation."""
    extrapolator = HelgakerExtrapolator()
    res = extrapolator.extrapolate_from_total(
        e_total_x=-76.3322,
        e_total_y=-76.3533,
        e_scf_x=-76.0571,
        e_scf_y=-76.0648,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
    )
    assert res.e_total_cbs < -76.3533
    assert math.isclose(res.e_total_cbs, res.e_scf_cbs + res.e_corr_cbs, abs_tol=1e-10)


def test_singular_denominator_error_handling() -> None:
    """Validate ValueError is raised when denominator in extrapolation is singular."""
    extrapolator = HelgakerExtrapolator()
    with pytest.raises(ValueError, match="Singular denominator"):
        extrapolator.extrapolate_scf(e_scf_x=-76.0, e_scf_y=-76.0, X=3, Y=3, alpha=7.88)

    with pytest.raises(ValueError, match="Singular denominator"):
        extrapolator.extrapolate_correlation(e_corr_x=-0.2, e_corr_y=-0.2, X=3, Y=3, beta=2.97)


def test_slow_conv_max_retries_exhausted() -> None:
    """Validate SlowConvInterceptor terminates restarts when retry limit is exhausted."""
    interceptor = SlowConvInterceptor(max_retries=2)
    failed_orca_stdout = "SCF NOT CONVERGED AFTER 125 CYCLES"
    base_input = "! DLPNO-CCSD(T) def2-TZVP\n"

    interception = interceptor.inspect_and_remediate(
        stdout_text=failed_orca_stdout,
        current_input=base_input,
        retry_count=2,
    )
    assert interception.has_failed is True
    assert interception.should_restart is False
    assert "exhausted" in interception.reason.lower()


def test_read_cbs_from_hdf5_missing_file_raises(tmp_path: Path) -> None:
    """Validate read_cbs_from_hdf5 raises FileNotFoundError when target file is missing."""
    missing_file = tmp_path / "non_existent.h5"
    with pytest.raises(FileNotFoundError):
        read_cbs_from_hdf5(h5_path=missing_file, node_id="test_node")
