#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 2.0 CBS Extrapolation Engine.

Module: tests/test_cochem_bench_cbs.py
Target Implementation: cochem_bench.bench_engine.cochem_bench_cbs

Tests:
1. Exact Parameter Matrix (ALPHA_BETA_MAP):
   - Validates all 10 authoritative pairs specified in Task 5 SRS.
   - Validates custom basis default beta values (beta=2.4 for 2/3, beta=3.0 for 3/4).
   - Validates mandatory explicit alpha override requirement for custom basis sets.
2. Energy Decomposition & ORCA Output Parser (parse_orca_energies):
   - Literal string parsing of "FINAL SINGLE POINT ENERGY" for E_total.
   - Literal string parsing of "Total Energy       :" from SCF block for E_SCF.
   - Native decoupling: E_corr = E_total - E_SCF.
   - Robust error raising (CBSParsingError) on corrupted or incomplete ORCA output.
3. HelgakerExtrapolator Mathematics:
   - Exponential decay two-point SCF extrapolation:
     E_SCF(inf) = (E_SCF(X)*exp(-alpha*sqrt(Y)) - E_SCF(Y)*exp(-alpha*sqrt(X))) /
                  (exp(-alpha*sqrt(Y)) - exp(-alpha*sqrt(X)))
   - Inverse power two-point correlation extrapolation:
     E_corr(inf) = (X^beta * E_corr(X) - Y^beta * E_corr(Y)) / (X^beta - Y^beta)
   - Extrapolation from total single point energies.
   - Direct end-to-end extrapolation from dual ORCA stdout streams.
4. ResidualFitAnalyzer:
   - Absolute variance calculation: Delta = |E_corr(inf) - E_corr(Y)|.
   - Exact CODATA Hartree-to-kcal/mol conversion (627.509474063 kcal/mol per Hartree).
   - Flagging logic: Delta > 10.0 kcal/mol flags CBS_HIGH_UNCERTAINTY; Delta <= 10.0 passes.
5. DualBasisDispatcher:
   - Dynamic %maxcore RAM calculation per MPI thread with host RAM headroom.
   - Dual-basis ORCA 6.1.1 input deck generation.
   - Atom coordinate validation and electronic property derivation via Mendeleev library.
   - Multiplicity and open-shell radical detection.
6. SlowConvInterceptor:
   - Standard output failure stream parsing for DIIS / SCF non-convergence.
   - Dynamic remediation injecting '! SlowConv SOSCF'.
   - Bounded retry tracking preventing infinite recursion.
7. HDF5 Persistence & Air-Gap Compliance:
   - FileLock protection with 120s timeout.
   - Atomic commitment of computed CBS limit to landscape.h5.
   - Dynamic resolution via COCHEM_ARTIFACTS_DIR.
   - Schema validation and roundtrip retrieval.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_cbs.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import List, Tuple

import pytest
from mendeleev import element

from cochem_bench.bench_engine.cochem_bench_cbs import (
    ALPHA_BETA_MAP,
    HARTREE_TO_KCAL_MOL,
    CBSExtrapolationResult,
    CBSParameterError,
    CBSParsingError,
    CBSSingularDenominatorError,
    DualBasisDispatcher,
    HelgakerExtrapolator,
    ResidualFitAnalyzer,
    SlowConvInterceptionResult,
    SlowConvInterceptor,
    commit_cbs_to_hdf5,
    parse_orca_energies,
    read_cbs_from_hdf5,
    resolve_hdf5_path,
    run_cbs_pipeline,
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
# Authentic ORCA Output Stream Fixtures
# ==============================================================================

ORCA_STDOUT_DEF2_TZVP: str = """
================================================================================
                                  * O R C A *
                  An Ab Initio, DFT and Semiempirical Electronic
                              Structure Program
================================================================================

----------------
TOTAL SCF ENERGY
----------------
Total Energy       :         -76.05710000 Eh

-------------------------------------------------------------------------------
                            COUPLED CLUSTER ITERATIONS
-------------------------------------------------------------------------------
E(CORR)(DLPNO-CCSD(T)) =       -0.27511948 Eh

-------------------------   --------------------
FINAL SINGLE POINT ENERGY       -76.332219480000
-------------------------   --------------------
****ORCA TERMINATED NORMALLY****
"""

ORCA_STDOUT_DEF2_QZVPP: str = """
================================================================================
                                  * O R C A *
================================================================================

----------------
TOTAL SCF ENERGY
----------------
Total Energy       :         -76.06480000 Eh

-------------------------------------------------------------------------------
                            COUPLED CLUSTER ITERATIONS
-------------------------------------------------------------------------------
E(CORR)(DLPNO-CCSD(T)) =       -0.28850000 Eh

-------------------------   --------------------
FINAL SINGLE POINT ENERGY       -76.353300000000
-------------------------   --------------------
****ORCA TERMINATED NORMALLY****
"""


# ==============================================================================
# 1. Parameter Matrix & ALPHA_BETA_MAP Tests
# ==============================================================================

def test_alpha_beta_map_exact_matrix() -> None:
    """Validate that ALPHA_BETA_MAP contains exact authoritative calibration parameters."""
    expected_map = {
        "cc-pv_dz_tz": {"alpha": 4.42, "beta": 2.46},
        "cc-pv_tz_qz": {"alpha": 5.46, "beta": 3.05},
        "pc-n_dz_tz": {"alpha": 7.02, "beta": 2.01},
        "pc-n_tz_qz": {"alpha": 9.78, "beta": 4.09},
        "def2_dz_tz": {"alpha": 10.39, "beta": 2.40},
        "def2_tz_qz": {"alpha": 7.88, "beta": 2.97},
        "ano-pv_dz_tz": {"alpha": 5.41, "beta": 2.43},
        "ano-pv_tz_qz": {"alpha": 4.48, "beta": 2.97},
        "saug-ano-pv_dz_tz": {"alpha": 5.48, "beta": 2.21},
        "saug-ano-pv_tz_qz": {"alpha": 4.18, "beta": 2.83},
    }

    assert len(ALPHA_BETA_MAP) == 10
    for key, values in expected_map.items():
        assert key in ALPHA_BETA_MAP, f"Missing key '{key}' in ALPHA_BETA_MAP"
        assert math.isclose(ALPHA_BETA_MAP[key]["alpha"], values["alpha"], abs_tol=1e-6)
        assert math.isclose(ALPHA_BETA_MAP[key]["beta"], values["beta"], abs_tol=1e-6)


def test_parameter_matrix_lookup_all_families() -> None:
    """Validate parameter resolution for all basis families in HelgakerExtrapolator."""
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
        assert math.isclose(alpha, exp_alpha, rel_tol=1e-4), f"Alpha mismatch for {bx}/{by}: {alpha} != {exp_alpha}"
        assert math.isclose(beta, exp_beta, rel_tol=1e-4), f"Beta mismatch for {bx}/{by}: {beta} != {exp_beta}"
        assert X == exp_X, f"X mismatch for {bx}: {X} != {exp_X}"
        assert Y == exp_Y, f"Y mismatch for {by}: {Y} != {exp_Y}"


def test_custom_basis_defaults_and_explicit_alpha_requirement() -> None:
    """Validate custom basis set rules: default beta (2.4 for 2/3, 3.0 for 3/4) & mandatory alpha override."""
    extrapolator = HelgakerExtrapolator()

    # 1. Custom basis 2/3 missing alpha must raise CBSParameterError
    with pytest.raises(CBSParameterError) as exc_info:
        extrapolator.lookup_parameters(basis_x="my_custom_dz", basis_y="my_custom_tz")
    assert "explicit alpha parameter override" in str(exc_info.value)
    assert "2.4" in str(exc_info.value)

    # 2. Custom basis 2/3 with explicit alpha should succeed with default beta = 2.4
    alpha, beta, X, Y = extrapolator.lookup_parameters(
        basis_x="my_custom_dz",
        basis_y="my_custom_tz",
        custom_alpha=5.50,
    )
    assert math.isclose(alpha, 5.50, abs_tol=1e-6)
    assert math.isclose(beta, 2.40, abs_tol=1e-6)
    assert X == 2
    assert Y == 3

    # 3. Custom basis 3/4 with explicit alpha should succeed with default beta = 3.0
    alpha, beta, X, Y = extrapolator.lookup_parameters(
        basis_x="my_custom_tz",
        basis_y="my_custom_qz",
        custom_alpha=6.20,
    )
    assert math.isclose(alpha, 6.20, abs_tol=1e-6)
    assert math.isclose(beta, 3.00, abs_tol=1e-6)
    assert X == 3
    assert Y == 4

    # 4. Custom basis with explicit beta override
    alpha, beta, X, Y = extrapolator.lookup_parameters(
        basis_x="my_custom_dz",
        basis_y="my_custom_tz",
        custom_alpha=5.50,
        custom_beta=2.85,
    )
    assert math.isclose(alpha, 5.50, abs_tol=1e-6)
    assert math.isclose(beta, 2.85, abs_tol=1e-6)


# ==============================================================================
# 2. Energy Decomposition & Output Parsing Tests
# ==============================================================================

def test_parse_orca_energies_nominal() -> None:
    """Validate literal parsing of 'FINAL SINGLE POINT ENERGY' and 'Total Energy       :'."""
    e_total, e_scf, e_corr = parse_orca_energies(ORCA_STDOUT_DEF2_TZVP)

    assert math.isclose(e_total, -76.33221948, abs_tol=1e-6)
    assert math.isclose(e_scf, -76.05710000, abs_tol=1e-6)
    expected_corr = -76.33221948 - (-76.05710000)
    assert math.isclose(e_corr, expected_corr, abs_tol=1e-6)
    assert e_corr < 0.0


def test_parse_orca_energies_missing_total_raises() -> None:
    """Validate that missing 'FINAL SINGLE POINT ENERGY' raises CBSParsingError."""
    truncated = """
    Total Energy       :         -76.05710000 Eh
    Calculation terminated.
    """
    with pytest.raises(CBSParsingError) as exc_info:
        parse_orca_energies(truncated)
    assert "FINAL SINGLE POINT ENERGY" in str(exc_info.value)


def test_parse_orca_energies_missing_scf_raises() -> None:
    """Validate that missing 'Total Energy       :' raises CBSParsingError."""
    truncated = """
    FINAL SINGLE POINT ENERGY       -76.332219480000
    Calculation terminated.
    """
    with pytest.raises(CBSParsingError) as exc_info:
        parse_orca_energies(truncated)
    assert "Total Energy" in str(exc_info.value)


def test_parse_orca_energies_empty_input_raises() -> None:
    """Validate that empty or invalid stdout text raises CBSParsingError."""
    with pytest.raises(CBSParsingError):
        parse_orca_energies("")


def test_extrapolate_from_orca_outputs() -> None:
    """Validate direct extrapolation from two authentic ORCA stdout outputs."""
    extrapolator = HelgakerExtrapolator()
    result = extrapolator.extrapolate_from_orca_outputs(
        stdout_x=ORCA_STDOUT_DEF2_TZVP,
        stdout_y=ORCA_STDOUT_DEF2_QZVPP,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
        node_id="water_c2v",
    )

    assert isinstance(result, CBSExtrapolationResult)
    assert result.e_scf_cbs < -76.0648
    assert result.e_corr_cbs < -0.2885
    assert math.isclose(result.e_total_cbs, result.e_scf_cbs + result.e_corr_cbs, abs_tol=1e-10)
    assert result.uncertainty_flag == "PASSED"
    assert result.metadata.get("e_scf_x") == -76.0571


# ==============================================================================
# 3. HelgakerExtrapolator Mathematics Tests
# ==============================================================================

def test_energy_decomposition_method() -> None:
    """Validate energy decomposition into SCF and correlation components."""
    extrapolator = HelgakerExtrapolator()
    e_total = -76.3322
    e_scf = -76.0571
    e_corr = extrapolator.decompose_correlation_energy(e_total, e_scf)
    assert math.isclose(e_corr, e_total - e_scf, abs_tol=1e-10)
    assert e_corr < 0.0


def test_scf_exponential_extrapolation_exact_math() -> None:
    """Validate exponential decay formula for Hartree-Fock SCF energy extrapolation.

    Formula:
      E_SCF(inf) = (E_SCF(X)*exp(-alpha*sqrt(Y)) - E_SCF(Y)*exp(-alpha*sqrt(X))) /
                   (exp(-alpha*sqrt(Y)) - exp(-alpha*sqrt(X)))
    """
    extrapolator = HelgakerExtrapolator()

    e_scf_x3 = -76.0571
    e_scf_x4 = -76.0648
    alpha = 7.88
    X, Y = 3, 4

    cbs_scf = extrapolator.extrapolate_scf(e_scf_x=e_scf_x3, e_scf_y=e_scf_x4, X=X, Y=Y, alpha=alpha)

    exp_x = math.exp(-alpha * math.sqrt(X))
    exp_y = math.exp(-alpha * math.sqrt(Y))
    expected_cbs_scf = (e_scf_x3 * exp_y - e_scf_x4 * exp_x) / (exp_y - exp_x)

    assert math.isclose(cbs_scf, expected_cbs_scf, rel_tol=1e-12)
    assert cbs_scf < e_scf_x4


def test_correlation_inverse_power_extrapolation_exact_math() -> None:
    """Validate Halkier/Neese inverse power formula for correlation energy extrapolation.

    Formula:
      E_corr(inf) = (X^beta * E_corr(X) - Y^beta * E_corr(Y)) / (X^beta - Y^beta)
    """
    extrapolator = HelgakerExtrapolator()

    e_corr_x3 = -0.2751
    e_corr_x4 = -0.2885
    beta = 2.97
    X, Y = 3, 4

    cbs_corr = extrapolator.extrapolate_correlation(e_corr_x=e_corr_x3, e_corr_y=e_corr_x4, X=X, Y=Y, beta=beta)

    x_beta = float(X) ** beta
    y_beta = float(Y) ** beta
    expected_cbs_corr = (x_beta * e_corr_x3 - y_beta * e_corr_x4) / (x_beta - y_beta)

    assert math.isclose(cbs_corr, expected_cbs_corr, rel_tol=1e-12)
    assert cbs_corr < e_corr_x4


def test_singular_denominator_error_handling() -> None:
    """Validate CBSSingularDenominatorError is raised when denominator is singular."""
    extrapolator = HelgakerExtrapolator()
    with pytest.raises(CBSSingularDenominatorError, match="Singular denominator"):
        extrapolator.extrapolate_scf(e_scf_x=-76.0, e_scf_y=-76.0, X=3, Y=3, alpha=7.88)

    with pytest.raises(CBSSingularDenominatorError, match="Singular denominator"):
        extrapolator.extrapolate_correlation(e_corr_x=-0.2, e_corr_y=-0.2, X=3, Y=3, beta=2.97)


def test_extrapolate_from_total() -> None:
    """Validate extrapolate_from_total calculates correlation and extrapolates."""
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


# ==============================================================================
# 4. ResidualFitAnalyzer Tests
# ==============================================================================

def test_residual_fit_analyzer_nominal_pass() -> None:
    """Validate ResidualFitAnalyzer passes when correlation variance Delta <= 10 kcal/mol."""
    analyzer = ResidualFitAnalyzer(threshold_kcal_mol=10.0)

    # Delta = |-0.2970 - (-0.2885)| = 0.0085 Hartree
    # In kcal/mol: 0.0085 * 627.509474063 = 5.3338 kcal/mol <= 10.0 kcal/mol -> PASSED
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

    # Delta = |-0.3200 - (-0.2885)| = 0.0315 Hartree
    # In kcal/mol: 0.0315 * 627.509474063 = 19.7665 kcal/mol > 10.0 kcal/mol -> HIGH UNCERTAINTY
    e_corr_cbs = -0.3200
    e_corr_y = -0.2885

    eval_result = analyzer.analyze(e_corr_cbs=e_corr_cbs, e_corr_y=e_corr_y)

    assert eval_result["is_flagged"] is True
    assert eval_result["flag"] == "CBS_HIGH_UNCERTAINTY"
    assert eval_result["variance_kcal_mol"] > 10.0
    assert "asymptotic regime" in eval_result["reason"].lower()


# ==============================================================================
# 5. DualBasisDispatcher Tests
# ==============================================================================

def test_dynamic_maxcore_ram_calculation() -> None:
    """Validate dynamic maxcore calculation per MPI thread prevents host RAM swap-death."""
    dispatcher = DualBasisDispatcher(node_max_gb=32.0, nprocs=8, ram_safety_fraction=0.75)
    maxcore_mb = dispatcher.calculate_maxcore_per_thread()

    # 32 GB * 1024 MB/GB * 0.75 / 8 = 3072 MB per thread
    expected_mb = int((32.0 * 1024.0 * 0.75) / 8)
    assert maxcore_mb == expected_mb
    assert maxcore_mb == 3072

    # Constrained node
    dispatcher_constrained = DualBasisDispatcher(node_max_gb=4.0, nprocs=8, ram_safety_fraction=0.75)
    maxcore_constrained = dispatcher_constrained.calculate_maxcore_per_thread()
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

    assert "! DLPNO-CCSD(T) def2-TZVP" in inp_x
    assert "TightSCF" in inp_x
    assert "DefGrid3" in inp_x
    assert "%maxcore" in inp_x
    assert "%pal nprocs 4 end" in inp_x
    assert "* xyz 0 1" in inp_x
    assert "0.11779" in inp_x

    assert "! DLPNO-CCSD(T) def2-QZVPP" in inp_y
    assert "TightSCF" in inp_y
    assert "%pal nprocs 4 end" in inp_y


def test_mendeleev_masses_and_electron_integration() -> None:
    """Validate dynamic element property retrieval via mendeleev library (Mendeleev Mandate)."""
    dispatcher = DualBasisDispatcher()
    mol_mass, total_electrons = dispatcher.get_molecular_properties(WATER_COORDS)

    expected_o_mass = float(element("O").mass)
    expected_h_mass = float(element("H").mass)
    expected_mol_mass = expected_o_mass + 2.0 * expected_h_mass

    assert math.isclose(mol_mass, expected_mol_mass, rel_tol=1e-5)
    assert total_electrons == 10


def test_open_shell_radical_detection() -> None:
    """Validate automatic detection of open-shell systems and UHF / unrestricted handling."""
    dispatcher = DualBasisDispatcher()
    is_open_shell, inferred_mult = dispatcher.detect_spin_state(OH_RADICAL_COORDS, charge=0)
    assert is_open_shell is True
    assert inferred_mult == 2

    deck = dispatcher.generate_input_deck(OH_RADICAL_COORDS, charge=0, mult=2)
    assert "* xyz 0 2" in deck["input_x"]


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
    assert "input_x" in deck
    assert "input_y" in deck
    file_x = tmp_path / "orca_def2-TZVP.inp"
    file_y = tmp_path / "orca_def2-QZVPP.inp"
    assert file_x.exists()
    assert file_y.exists()
    assert "! DLPNO-CCSD(T) def2-TZVP" in file_x.read_text(encoding="utf-8")
    assert "! DLPNO-CCSD(T) def2-QZVPP" in file_y.read_text(encoding="utf-8")


# ==============================================================================
# 6. SlowConvInterceptor Tests
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


# ==============================================================================
# 7. HDF5 Persistence & Pipeline Orchestration Tests
# ==============================================================================

def test_hdf5_cbs_persistence_with_filelock(tmp_path: Path) -> None:
    """Validate atomic serialization of computed CBS results to landscape.h5 with FileLock."""
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

    persisted_path = commit_cbs_to_hdf5(h5_path=h5_file, result=cbs_result, timeout=120.0)
    assert persisted_path.exists()

    # Read back and verify exact data integrity
    loaded_data = read_cbs_from_hdf5(h5_path=h5_file, node_id="water_c2v_node_01", timeout=120.0)
    assert math.isclose(loaded_data["e_scf_cbs"], -76.065231, abs_tol=1e-6)
    assert math.isclose(loaded_data["e_corr_cbs"], -0.297154, abs_tol=1e-6)
    assert math.isclose(loaded_data["e_total_cbs"], -76.362385, abs_tol=1e-6)
    assert loaded_data["uncertainty_flag"] == "PASSED"
    assert loaded_data["basis_x"] == "def2-TZVP"
    assert loaded_data["basis_y"] == "def2-QZVPP"


def test_hdf5_airgap_environment_resolution(tmp_path: Path) -> None:
    """Validate dynamic resolution of HDF5 workspace path via COCHEM_ARTIFACTS_DIR."""
    prev_env = os.environ.get("COCHEM_ARTIFACTS_DIR")
    artifacts_dir = tmp_path / "airgap_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    os.environ["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir)

    try:
        resolved = resolve_hdf5_path()
        expected = (artifacts_dir / "BENCH_Workspace" / "landscape.h5").resolve()
        assert resolved == expected

        # Relative path resolution within artifacts dir
        resolved_rel = resolve_hdf5_path(Path("custom_folder/my_landscape.h5"))
        expected_rel = (artifacts_dir / "custom_folder/my_landscape.h5").resolve()
        assert resolved_rel == expected_rel
    finally:
        if prev_env is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_env
        else:
            os.environ.pop("COCHEM_ARTIFACTS_DIR", None)


def test_read_cbs_from_hdf5_missing_file_raises(tmp_path: Path) -> None:
    """Validate read_cbs_from_hdf5 raises FileNotFoundError when target file is missing."""
    missing_file = tmp_path / "non_existent.h5"
    with pytest.raises(FileNotFoundError):
        read_cbs_from_hdf5(h5_path=missing_file, node_id="test_node")


def test_read_cbs_from_hdf5_missing_node_raises(tmp_path: Path) -> None:
    """Validate read_cbs_from_hdf5 raises KeyError when node_id is absent."""
    h5_file = tmp_path / "landscape.h5"
    cbs_result = CBSExtrapolationResult(
        e_scf_cbs=-76.06,
        e_corr_cbs=-0.29,
        e_total_cbs=-76.35,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
        alpha=7.88,
        beta=2.97,
        residual_variance_hartree=0.008,
        residual_variance_kcal_mol=5.0,
        uncertainty_flag="PASSED",
        node_id="node_present",
    )
    commit_cbs_to_hdf5(h5_path=h5_file, result=cbs_result)

    with pytest.raises(KeyError, match="node_missing"):
        read_cbs_from_hdf5(h5_path=h5_file, node_id="node_missing")


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
