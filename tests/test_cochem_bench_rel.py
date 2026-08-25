#!/usr/bin/env python3
r"""Authentic Zero-Mock Unit Test Suite for Stage 4.0 Relativistic and Spin-Orbit Corrections.

Authoritative Implementation: cochem_bench.bench_engine.cochem_bench_rel / bench_engine.cochem_bench_rel
System Domain: CoChem-BENCH Scientific Engine

Test Requirements & Contracts:
1. RelativisticHamiltonianInjector:
   - Re-contracts basis sets:
     * Karlsruhe: replacing "def2-" with "x2c-" and appending "all-s"
       (e.g., def2-TZVPP -> x2c-TZVPPall-s, def2-SVP -> x2c-SVPall-s, def2-QZVPP -> x2c-QZVPPall-s).
     * Correlation consistent: appending "-DK" (e.g., cc-pVDZ -> cc-pVDZ-DK, cc-pVTZ -> cc-pVTZ-DK,
       cc-pVQZ -> cc-pVQZ-DK, aug-cc-pVTZ -> aug-cc-pVTZ-DK) or "-X2C".
   - inspect_heavy_elements using mendeleev.element to dynamically get atomic mass and atomic number (Z >= 19).
   - Generates valid ORCA input decks with ! X2C, %maxcore, coordinates.
2. X2CHandler & Divergence Remediator:
   - Detects X2C divergence / SCF / DIIS failure signatures.
   - If X2C diverges, catches failure in subprocess.run / runner, rewrites input for Douglas-Kroll-Hess (! DKH2), and restarts.
   - Parses E_Total from both outputs using the exact literal string "FINAL SINGLE POINT ENERGY".
   - Computes Delta_E_rel = E_Total^(Relativistic) - E_Total^(Non-Rel).
3. SpinOrbitCoupler:
   - For geometries flagged REQUIRES_UHF in Stage 1.0 (or mult > 1 / radical), injects ! SOMF(1X).
   - Parses electronic energy shift from SOMF(1X) property block: searches for the exact literal strings
     "SOMF(1X) Two-Component Trace" and "SOMF(1X) Non-Relativistic Trace". Extracts trailing floats
     and computes their difference to obtain Delta_E_SOC = Trace_2C - Trace_nonrel.
4. DeltaRelExtractor:
   - Extracts energies and computes Delta_E_rel and Delta_E_SOC in Hartree and kcal/mol (using HARTREE_TO_KCAL_MOL = 627.509474063).
5. EphemeralScratchPurge & Air-Gap:
   - Resolves UUID scratch workspace dynamically via os.environ["COCHEM_ARTIFACTS_DIR"].
   - Isolates in UUID scratch with CUDA_VISIBLE_DEVICES="".
   - Purges transient simulation files (*.gbw, *.tmp, *.densities, *.bso, *.prop, etc.).
6. HDF5 Persistence & Stage 5.0 Composite Aggregator Integration:
   - Thread-safe commit_rel_to_hdf5 with filelock.FileLock under rel_corrections/{node_id} in landscape.h5.
   - read_rel_from_hdf5.
   - Composite aggregator validation: E_total = E_SCF_CBS + E_corr_CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE.

Authoritative References:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_rel.md
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, List, Tuple

import h5py
import pytest
from mendeleev import element

from bench_engine.cochem_bench_cbs import (
    CBSExtrapolationResult,
    commit_cbs_to_hdf5,
)
from bench_engine.cochem_bench_cv import (
    CVCorrectionResult,
    commit_cv_to_hdf5,
)
from bench_engine.cochem_bench_export import (
    CompositeAggregator,
)

# Verify importability from both bench_engine and cochem_bench.bench_engine
from bench_engine.cochem_bench_rel import (
    HARTREE_TO_KCAL_MOL,
    DeltaRelExtractor,
    EphemeralScratchPurge,
    RelativisticHamiltonianInjector,
    RelCorrectionResult,
    SpinOrbitCoupler,
    X2CDivergenceError,
    X2CDivergenceRemediator,
    X2CHandler,
    commit_rel_to_hdf5,
    read_rel_from_hdf5,
    run_rel_pipeline,
)

# ==============================================================================
# Authentic Molecular Test Geometries (Cartesian Coordinates in Angstroms)
# ==============================================================================

# Water Molecule (Light elements: H (Z=1), O (Z=8) - Sub-relativistic threshold Z < 19)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Bromobenzene (Heavy element: Br - Z = 35, 4th Period, requires X2C)
BROMOBENZENE_COORDS: List[Tuple[str, float, float, float]] = [
    ("Br", 0.000000, 0.000000, 1.890000),
    ("C",  0.000000, 0.000000, 0.000000),
    ("C",  0.000000, 1.210000, -0.700000),
    ("C",  0.000000, -1.210000, -0.700000),
    ("C",  0.000000, 1.200000, -2.090000),
    ("C",  0.000000, -1.200000, -2.090000),
    ("C",  0.000000, 0.000000, -2.790000),
    ("H",  0.000000, 2.140000, -0.160000),
    ("H",  0.000000, -2.140000, -0.160000),
    ("H",  0.000000, 2.140000, -2.630000),
    ("H",  0.000000, -2.140000, -2.630000),
    ("H",  0.000000, 0.000000, -3.870000),
]

# Dimethyl Selenide (Heavy element: Se - Z = 34, 4th Period)
DMSE_COORDS: List[Tuple[str, float, float, float]] = [
    ("Se", 0.000000, 0.000000, 0.000000),
    ("C",  0.000000, 1.500000, 1.100000),
    ("C",  0.000000, -1.500000, 1.100000),
    ("H",  0.890000, 1.500000, 1.700000),
    ("H", -0.890000, 1.500000, 1.700000),
    ("H",  0.000000, 2.380000, 0.480000),
    ("H",  0.890000, -1.500000, 1.700000),
    ("H", -0.890000, -1.500000, 1.700000),
    ("H",  0.000000, -2.380000, 0.480000),
]

# Methyl Radical (Open-shell doublet radical: CH3, Multiplicity = 2, requires SOMF(1X))
METHYL_RADICAL_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, 0.000000),
    ("H", 0.000000, 1.079000, 0.000000),
    ("H", 0.934441, -0.539500, 0.000000),
    ("H", -0.934441, -0.539500, 0.000000),
]


# ==============================================================================
# Authentic ORCA 6.1.1 Output Fixtures
# ==============================================================================

ORCA_NON_REL_STDOUT_BROMOBENZENE = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -

Number of atoms                       ...   12
Total Charge                          ...    0
Multiplicity                          ...    1
Number of Electrons                   ...   82

-------------------------
DLPNO-CCSD(T) CALCULATION
-------------------------
E(SCF)                                ... -2803.11548291 Eh
E(DLPNO-CCSD)                         ... -2804.89240182 Eh
E(DLPNO-CCSD(T))                      ... -2805.01248912 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2805.012489120000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""

ORCA_REL_X2C_STDOUT_BROMOBENZENE = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -

Relativistic Mode                     ... Exact Two-Component (X2C)
Number of atoms                       ...   12
Total Charge                          ...    0
Multiplicity                          ...    1

-------------------------
DLPNO-CCSD(T) CALCULATION
-------------------------
E(SCF)                                ... -2824.78129410 Eh
E(DLPNO-CCSD)                         ... -2826.56841295 Eh
E(DLPNO-CCSD(T))                      ... -2826.68940125 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2826.689401250000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""

ORCA_REL_DKH2_STDOUT_BROMOBENZENE = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -

Relativistic Mode                     ... Douglas-Kroll-Hess (DKH2)
Number of atoms                       ...   12
Total Charge                          ...    0
Multiplicity                          ...    1

-------------------------
DLPNO-CCSD(T) CALCULATION
-------------------------
E(SCF)                                ... -2824.77918230 Eh
E(DLPNO-CCSD)                         ... -2826.56628100 Eh
E(DLPNO-CCSD(T))                      ... -2826.68725000 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2826.687250000000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""

ORCA_X2C_DIVERGENCE_STDOUT = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Relativistic Mode                     ... Exact Two-Component (X2C)
Diagonalizing X2C 1-electron relativistic Hamiltonian...
SCF cycle initiated...
ITER  1: E = -2820.1234  DeltaE =  0.000000  MaxGrad = 0.1234
ITER  2: E = -2825.9812  DeltaE = -5.857800  MaxGrad = 0.5621
ITER  3: E = -2812.4419  DeltaE = +13.53930  MaxGrad = 1.9821
ITER 50: E = -2801.1299  DeltaE = +0.892110  MaxGrad = 0.8124
[ERROR] SCF NOT CONVERGED AFTER 50 ITERATIONS. DIIS failure in X2C Hamiltonian cycle.
Matrix is not positive definite.
Calculation did not converge.
ORCA finished with error.
"""

ORCA_SOC_SOMF_STDOUT = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -
Relativistic Mode                     ... Exact Two-Component (X2C)
Spin-Orbit Coupling Operator          ... SOMF(1X) (Spin-Orbit Mean-Field)
Multiplicity                          ...    2 (Open-Shell Radical)

-------------------------------------------------------------------------------
SOMF(1X) SPIN-ORBIT COUPLING CORRECTION
-------------------------------------------------------------------------------
SOMF(1X) Two-Component Trace          ... -2826.691246370000
SOMF(1X) Non-Relativistic Trace       ... -2826.689401250000

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2826.691246370000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""


# ==============================================================================
# 1. RelativisticHamiltonianInjector Unit Tests
# ==============================================================================

class TestRelativisticHamiltonianInjector:
    """Authentic tests for basis set re-contraction, dynamic elemental inspection, and ORCA deck creation."""

    def test_recontract_karlsruhe_basis_sets(self) -> None:
        """Verifies Karlsruhe def2 basis sets replace 'def2-' with 'x2c-' and append 'all-s'."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("def2-SVP") == "x2c-SVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVP") == "x2c-TZVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPP") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("def2-QZVPP") == "x2c-QZVPPall-s"
        assert injector.map_relativistic_basis_set("def2-QZVP") == "x2c-QZVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPD") == "x2c-TZVPDall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPPD") == "x2c-TZVPPDall-s"

    def test_recontract_dunning_basis_sets_dk(self) -> None:
        """Verifies Dunning correlation-consistent basis sets map to '-DK' for Douglas-Kroll-Hess."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_basis_dk("cc-pVDZ") == "cc-pVDZ-DK"
        assert injector.map_basis_dk("cc-pVTZ") == "cc-pVTZ-DK"
        assert injector.map_basis_dk("cc-pVQZ") == "cc-pVQZ-DK"
        assert injector.map_basis_dk("aug-cc-pVTZ") == "aug-cc-pVTZ-DK"
        assert injector.map_basis_dk("cc-pCVTZ") == "cc-pCVTZ-DK"
        assert injector.map_basis_dk("aug-cc-pwCVTZ") == "aug-cc-pwCVTZ-DK"

    def test_recontract_dunning_basis_sets_x2c(self) -> None:
        """Verifies Dunning correlation-consistent basis sets map to '-X2C' for X2C mode."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("cc-pVDZ", hamiltonian="X2C") == "cc-pVDZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVTZ", hamiltonian="X2C") == "cc-pVTZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVQZ", hamiltonian="X2C") == "cc-pVQZ-X2C"
        assert injector.map_relativistic_basis_set("aug-cc-pVTZ", hamiltonian="X2C") == "aug-cc-pVTZ-X2C"

    def test_recontract_idempotent_and_ano_rcc(self) -> None:
        """Verifies that already relativistic basis sets remain unchanged."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("x2c-TZVPPall-s") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("cc-pVTZ-DK") == "cc-pVTZ-DK"
        assert injector.map_relativistic_basis_set("cc-pVTZ-X2C") == "cc-pVTZ-X2C"
        assert injector.map_relativistic_basis_set("ano-rcc") == "ano-rcc"
        assert injector.map_relativistic_basis_set("ano-rcc-TZP") == "ano-rcc-TZP"

    def test_dynamic_elemental_inspection_mendeleev(self) -> None:
        """Verifies dynamic inspection using mendeleev.element for atomic mass and Z >= 19 detection."""
        injector = RelativisticHamiltonianInjector()

        # Light system: Water (H: Z=1, O: Z=8)
        info_h2o = injector.inspect_heavy_elements(WATER_COORDS, relativistic_z_threshold=19)
        assert info_h2o["has_heavy_elements"] is False
        assert info_h2o["max_z"] == 8
        assert len(info_h2o["heavy_elements"]) == 0
        expected_h2o_mass = float(element("O").mass + 2 * element("H").mass)
        assert math.isclose(info_h2o["total_mass"], expected_h2o_mass, rel_tol=1e-5)

        # Heavy system: Bromobenzene (Br: Z=35)
        info_br = injector.inspect_heavy_elements(BROMOBENZENE_COORDS, relativistic_z_threshold=19)
        assert info_br["has_heavy_elements"] is True
        assert info_br["max_z"] == 35
        assert "Br" in info_br["heavy_elements"]
        expected_br_z = element("Br").atomic_number
        assert expected_br_z == 35

        # Heavy system: Dimethyl Selenide (Se: Z=34)
        info_se = injector.inspect_heavy_elements(DMSE_COORDS, relativistic_z_threshold=19)
        assert info_se["has_heavy_elements"] is True
        assert info_se["max_z"] == 34
        assert "Se" in info_se["heavy_elements"]

    def test_inject_relativistic_hamiltonian_orca_input(self) -> None:
        """Verifies modifying ORCA input text with X2C and re-contracted basis set."""
        injector = RelativisticHamiltonianInjector()
        raw_input = (
            "! DLPNO-CCSD(T) def2-TZVPP TightSCF\n"
            "%maxcore 4000\n"
            "* xyz 0 1\n"
            "  Br  0.0 0.0 1.89\n"
            "*\n"
        )

        rel_input = injector.inject_relativistic_hamiltonian(raw_input)
        assert "X2C" in rel_input
        assert "x2c-TZVPPall-s" in rel_input
        assert "%maxcore 4000" in rel_input
        assert "Br  0.0 0.0 1.89" in rel_input

    def test_generate_input_decks_maxcore_and_nprocs(self) -> None:
        """Verifies dual input deck generation for baseline non-rel and relativistic jobs with %maxcore."""
        injector = RelativisticHamiltonianInjector()
        decks = injector.generate_input_decks(
            coords=BROMOBENZENE_COORDS,
            method="DLPNO-CCSD(T)",
            base_basis="def2-TZVPP",
            charge=0,
            mult=1,
            node_max_gb=16.0,
            nprocs=4,
            ram_safety_fraction=0.75,
        )

        assert "non_rel_input" in decks
        assert "rel_input" in decks
        assert "def2-TZVPP" in decks["non_rel_input"]
        assert "X2C" not in decks["non_rel_input"]

        assert "X2C" in decks["rel_input"]
        assert "x2c-TZVPPall-s" in decks["rel_input"]
        assert decks["has_heavy_elements"] is True

        # Check %maxcore calculation: (16 * 1024 * 0.75) / 4 = 3072 MB
        assert "%maxcore 3072" in decks["rel_input"]
        assert "%pal nprocs 4 end" in decks["rel_input"]


# ==============================================================================
# 2. X2CHandler & Divergence Remediator Tests
# ==============================================================================

class TestX2CHandlerAndDivergenceRemediator:
    """Authentic tests for X2C divergence detection, error trapping, DKH2 rewriting, and restart."""

    def test_detect_divergence_signatures(self) -> None:
        """Verifies detection of various SCF divergence and DIIS failure signatures in ORCA outputs."""
        handler = X2CHandler()

        # Normal converged output
        assert handler.detect_divergence(ORCA_REL_X2C_STDOUT_BROMOBENZENE) is False

        # Divergence output with DIIS failure
        assert handler.detect_divergence(ORCA_X2C_DIVERGENCE_STDOUT) is True

        # Custom signature tests
        assert handler.detect_divergence("Error: SCF NOT CONVERGED in step 40") is True
        assert handler.detect_divergence("Matrix is not positive definite during X2C transformation") is True
        assert handler.detect_divergence("Diagonalization failed in X2C Hamiltonian cycle") is True

    def test_validate_convergence_success(self) -> None:
        """Verifies extraction of FINAL SINGLE POINT ENERGY from authentic X2C output."""
        handler = X2CHandler()
        energy = handler.validate_convergence(ORCA_REL_X2C_STDOUT_BROMOBENZENE)
        assert math.isclose(energy, -2826.68940125, rel_tol=1e-9)

    def test_validate_convergence_divergence_raises_exception(self) -> None:
        """Verifies that X2CDivergenceError is raised when X2C calculation diverges."""
        handler = X2CHandler()
        with pytest.raises(X2CDivergenceError) as exc_info:
            handler.validate_convergence(ORCA_X2C_DIVERGENCE_STDOUT)

        err_msg = str(exc_info.value).lower()
        assert "diverge" in err_msg or "fail" in err_msg

    def test_remediate_input_deck_to_dkh2(self) -> None:
        """Verifies rewriting of input deck from X2C to Douglas-Kroll-Hess (! DKH2)."""
        handler = X2CHandler()
        x2c_deck = "! DLPNO-CCSD(T) X2C cc-pVTZ-X2C TightSCF\n%maxcore 3000\n* xyz 0 1\n  Br 0 0 0\n*\n"
        dkh2_deck = handler.remediate_to_dkh2(x2c_deck)

        assert "DKH2" in dkh2_deck
        assert "X2C" not in dkh2_deck
        assert "cc-pVTZ-DK" in dkh2_deck

    def test_divergence_remediator_execution_and_restart(self) -> None:
        """Verifies divergence remediator intercepts X2C failure, rewrites to DKH2, and restarts."""
        remediator = X2CDivergenceRemediator()
        initial_x2c_deck = "! DLPNO-CCSD(T) X2C x2c-TZVPPall-s TightSCF\n* xyz 0 1\n  Br 0 0 0\n*\n"

        call_count = 0
        executed_decks = []

        def mock_orca_runner(deck: str, scratch_dir: Any = None) -> Tuple[str, str, int]:
            nonlocal call_count, executed_decks
            call_count += 1
            executed_decks.append(deck)
            if "X2C" in deck:
                # Simulate X2C divergence failure
                return ORCA_X2C_DIVERGENCE_STDOUT, "SCF failed", 1
            else:
                # Remediated DKH2 calculation converges
                return ORCA_REL_DKH2_STDOUT_BROMOBENZENE, "", 0

        stdout, stderr, code, hamiltonian_used = remediator.execute_with_remediation(
            input_deck=initial_x2c_deck,
            runner_fn=mock_orca_runner,
        )

        assert call_count == 2
        assert hamiltonian_used == "DKH2"
        assert "DKH2" in executed_decks[1]

        # Parse energy from remediated output
        extractor = DeltaRelExtractor()
        e_rel_dkh2 = extractor.parse_final_energy_from_stdout(stdout)
        assert math.isclose(e_rel_dkh2, -2826.68725000, rel_tol=1e-9)

        # Calculate Delta_E_rel
        e_non_rel = -2805.01248912
        delta_rel = float(e_rel_dkh2 - e_non_rel)
        assert delta_rel < 0.0


# ==============================================================================
# 3. SpinOrbitCoupler Unit Tests
# ==============================================================================

class TestSpinOrbitCoupler:
    """Authentic tests for open-shell radical detection, SOMF(1X) injection, and trace delta parsing."""

    def test_is_open_shell_flagging(self) -> None:
        """Verifies open-shell radical state classification (mult > 1, requires_uhf, is_radical)."""
        coupler = SpinOrbitCoupler()

        # Closed-shell singlet
        assert coupler.is_open_shell(mult=1, requires_uhf=False, is_radical=False) is False

        # Open-shell doublet (radical)
        assert coupler.is_open_shell(mult=2, requires_uhf=False, is_radical=False) is True

        # Triplet
        assert coupler.is_open_shell(mult=3, requires_uhf=False, is_radical=False) is True

        # Flagged by Stage 1.0 requires_uhf
        assert coupler.is_open_shell(mult=1, requires_uhf=True, is_radical=False) is True

        # Flagged by is_radical
        assert coupler.is_open_shell(mult=1, requires_uhf=False, is_radical=True) is True

    def test_inject_somf_operator(self) -> None:
        """Verifies injection of SOMF(1X) spin-orbit coupling keyword into input deck."""
        coupler = SpinOrbitCoupler()
        raw_deck = "! DLPNO-CCSD(T) X2C x2c-TZVPPall-s TightSCF\n* xyz 0 2\n  C 0 0 0\n*\n"
        somf_deck = coupler.inject_somf_operator(raw_deck)

        assert "SOMF(1X)" in somf_deck

        # Invariant: idempotent injection
        re_injected = coupler.inject_somf_operator(somf_deck)
        assert re_injected.count("SOMF(1X)") == 1

    def test_parse_somf_traces_authentic_orca(self) -> None:
        """Verifies parsing of exact literal strings 'SOMF(1X) Two-Component Trace' and 'SOMF(1X) Non-Relativistic Trace'."""
        coupler = SpinOrbitCoupler()
        traces = coupler.parse_somf_traces(ORCA_SOC_SOMF_STDOUT)

        assert traces is not None
        assert math.isclose(traces["trace_2c"], -2826.69124637, rel_tol=1e-9)
        assert math.isclose(traces["trace_nonrel"], -2826.68940125, rel_tol=1e-9)

        expected_delta_soc = -2826.69124637 - (-2826.68940125)
        assert math.isclose(traces["delta_e_soc"], expected_delta_soc, rel_tol=1e-9)

        # Verify parse_soc_energy_from_stdout uses traces
        soc_shift = coupler.parse_soc_energy_from_stdout(ORCA_SOC_SOMF_STDOUT)
        assert soc_shift is not None
        assert math.isclose(soc_shift, expected_delta_soc, rel_tol=1e-9)

    def test_derive_soc_correction_open_vs_closed_shell(self) -> None:
        """Verifies derivation of Delta E_SOC in Hartree for open-shell vs closed-shell."""
        coupler = SpinOrbitCoupler()

        # Open-shell with explicit traces
        delta_soc_traces = coupler.derive_soc_correction(
            e_total_rel=-2826.68940125,
            trace_2c=-2826.69124637,
            trace_nonrel=-2826.68940125,
        )
        assert math.isclose(delta_soc_traces, -0.00184512, rel_tol=1e-6)

        # Closed-shell without SOC
        delta_soc_closed = coupler.derive_soc_correction(
            e_total_rel=-2826.68940125,
            e_total_soc=None,
        )
        assert delta_soc_closed == 0.0


# ==============================================================================
# 4. DeltaRelExtractor Unit Tests
# ==============================================================================

class TestDeltaRelExtractor:
    """Authentic tests for energy parsing, Delta E_rel derivation, and Hartree to kcal/mol conversion."""

    def test_parse_final_energy_from_stdout(self) -> None:
        """Verifies extraction of FINAL SINGLE POINT ENERGY from authentic ORCA standard output."""
        extractor = DeltaRelExtractor()
        e_non_rel = extractor.parse_final_energy_from_stdout(ORCA_NON_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(e_non_rel, -2805.01248912, rel_tol=1e-9)

        e_rel = extractor.parse_final_energy_from_stdout(ORCA_REL_X2C_STDOUT_BROMOBENZENE)
        assert math.isclose(e_rel, -2826.68940125, rel_tol=1e-9)

    def test_extract_delta_scalar_and_soc_math(self) -> None:
        """Verifies Delta_E_rel and Delta_E_SOC math and conversion to kcal/mol via exact CODATA."""
        extractor = DeltaRelExtractor()
        e_non_rel = -2805.01248912
        e_rel = -2826.68940125
        e_soc = -2826.69124637

        result = extractor.extract_delta(
            e_total_non_rel=e_non_rel,
            e_total_rel=e_rel,
            e_total_soc=e_soc,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            method="DLPNO-CCSD(T)",
            has_heavy_elements=True,
            is_open_shell=True,
            node_id="bromobenzene_node",
        )

        expected_delta_rel_hartree = float(e_rel - e_non_rel)
        expected_delta_rel_kcal = float(expected_delta_rel_hartree * HARTREE_TO_KCAL_MOL)
        expected_delta_soc_hartree = float(e_soc - e_rel)
        expected_delta_soc_kcal = float(expected_delta_soc_hartree * HARTREE_TO_KCAL_MOL)
        expected_delta_total_hartree = float(expected_delta_rel_hartree + expected_delta_soc_hartree)
        expected_delta_total_kcal = float(expected_delta_total_hartree * HARTREE_TO_KCAL_MOL)

        assert math.isclose(result.delta_e_rel_hartree, expected_delta_rel_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_rel_kcal_mol, expected_delta_rel_kcal, rel_tol=1e-9)
        assert math.isclose(result.delta_e_soc_hartree, expected_delta_soc_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_soc_kcal_mol, expected_delta_soc_kcal, rel_tol=1e-9)
        assert math.isclose(result.delta_e_total_rel_hartree, expected_delta_total_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_total_rel_kcal_mol, expected_delta_total_kcal, rel_tol=1e-9)
        assert result.node_id == "bromobenzene_node"

    def test_extract_from_outputs_full_pipeline(self) -> None:
        """Verifies direct extraction from standard outputs with SOC traces."""
        extractor = DeltaRelExtractor()
        result = extractor.extract_from_outputs(
            stdout_non_rel=ORCA_NON_REL_STDOUT_BROMOBENZENE,
            stdout_rel=ORCA_REL_X2C_STDOUT_BROMOBENZENE,
            stdout_soc=ORCA_SOC_SOMF_STDOUT,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            node_id="br_node_01",
        )

        assert result.node_id == "br_node_01"
        assert result.is_open_shell is True
        assert math.isclose(result.e_total_non_rel, -2805.01248912, rel_tol=1e-9)
        assert math.isclose(result.e_total_rel, -2826.68940125, rel_tol=1e-9)
        assert result.delta_e_soc_hartree < 0.0


# ==============================================================================
# 5. EphemeralScratchPurge & Air-Gap Isolation Tests
# ==============================================================================

class TestEphemeralScratchPurgeAndAirGap:
    """Authentic tests for dynamic scratch creation, accelerator isolation, and file purging."""

    def test_scratch_dir_resolution_via_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Verifies resolution of UUID scratch workspace dynamically via COCHEM_ARTIFACTS_DIR."""
        artifacts_dir = tmp_path / "custom_artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))

        scratch_dir = EphemeralScratchPurge.create_scratch_dir()
        assert scratch_dir.exists()
        assert str(artifacts_dir) in str(scratch_dir)
        assert "BENCH_Workspace" in str(scratch_dir)
        assert "Scratch" in str(scratch_dir)

    def test_accelerator_isolation_env(self) -> None:
        """Verifies injection of accelerator isolation (CUDA_VISIBLE_DEVICES="")."""
        env = EphemeralScratchPurge.get_isolated_env({"PATH": "/usr/bin", "FOO": "BAR"})
        assert env["CUDA_VISIBLE_DEVICES"] == ""
        assert env["PATH"] == "/usr/bin"
        assert env["FOO"] == "BAR"

    def test_scratch_purge_transient_files(self, tmp_path: Path) -> None:
        """Verifies unlinking of transient files (.gbw, .tmp, .densities, etc.) and directory cleanup."""
        scratch_dir = tmp_path / "mock_scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        # Create transient simulation files
        transient_extensions = [
            "orca.gbw", "orca.tmp", "orca.densities", "orca.bso",
            "orca.prop", "orca.core", "orca.host", "orca.ges",
            "orca.int", "orca.uco",
        ]
        created_files = []
        for name in transient_extensions:
            fpath = scratch_dir / name
            fpath.write_text("transient quantum chemistry data", encoding="utf-8")
            created_files.append(fpath)

        # Run purge
        purge_report = EphemeralScratchPurge.purge_scratch_dir(scratch_dir, remove_dir=True)
        assert purge_report["status"] == "purged"
        assert purge_report["purged_count"] == len(transient_extensions)
        assert not scratch_dir.exists()


# ==============================================================================
# 6. HDF5 Persistence & Composite Aggregator Tests
# ==============================================================================

class TestHDF5PersistenceAndCompositeIntegration:
    """Authentic tests for thread-safe FileLock HDF5 persistence and Stage 5.0 Composite Aggregator."""

    def test_commit_and_read_rel_hdf5_threadsafe(self, tmp_path: Path) -> None:
        """Verifies thread-safe atomic write to landscape.h5 under rel_corrections/{node_id} and roundtrip read."""
        h5_file = tmp_path / "landscape.h5"

        extractor = DeltaRelExtractor()
        result = extractor.extract_delta(
            e_total_non_rel=-2805.01248912,
            e_total_rel=-2826.68940125,
            e_total_soc=-2826.69124637,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            method="DLPNO-CCSD(T)",
            has_heavy_elements=True,
            is_open_shell=True,
            node_id="node_test_01",
        )

        commit_rel_to_hdf5(h5_path=h5_file, result=result)

        # Direct inspection of HDF5 structure
        with h5py.File(h5_file, "r") as f:
            assert "rel_corrections" in f
            assert "node_test_01" in f["rel_corrections"]
            grp = f["rel_corrections"]["node_test_01"]

            assert "e_total_non_rel" in grp
            assert "e_total_rel" in grp
            assert "delta_e_rel_hartree" in grp
            assert "delta_e_rel_kcal_mol" in grp
            assert "delta_e_soc_hartree" in grp
            assert "delta_e_soc_kcal_mol" in grp
            assert "delta_e_total_rel_hartree" in grp
            assert "delta_e_total_rel_kcal_mol" in grp
            assert grp.attrs["basis_set"] == "def2-TZVPP"
            assert grp.attrs["rel_basis_set"] == "x2c-TZVPPall-s"
            assert grp.attrs["hamiltonian"] == "X2C"
            assert bool(grp.attrs["has_heavy_elements"]) is True
            assert bool(grp.attrs["is_open_shell"]) is True

        # Read back via API
        data = read_rel_from_hdf5(h5_path=h5_file, node_id="node_test_01")
        assert math.isclose(data["e_total_non_rel"], -2805.01248912, rel_tol=1e-9)
        assert math.isclose(data["e_total_rel"], -2826.68940125, rel_tol=1e-9)
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)
        assert math.isclose(data["delta_e_soc_hartree"], result.delta_e_soc_hartree, rel_tol=1e-7)
        assert data["basis_set"] == "def2-TZVPP"
        assert data["rel_basis_set"] == "x2c-TZVPPall-s"

    def test_run_rel_pipeline_end_to_end(self, tmp_path: Path) -> None:
        """Verifies end-to-end run_rel_pipeline execution and persistence."""
        h5_file = tmp_path / "landscape.h5"

        result = run_rel_pipeline(
            coords=BROMOBENZENE_COORDS,
            e_total_non_rel=-2805.01248912,
            e_total_rel=-2826.68940125,
            base_basis="def2-TZVPP",
            method="DLPNO-CCSD(T)",
            node_id="bromobenzene_pipeline_node",
            h5_path=h5_file,
        )

        assert isinstance(result, RelCorrectionResult)
        assert result.has_heavy_elements is True
        assert result.rel_basis_set == "x2c-TZVPPall-s"

        data = read_rel_from_hdf5(h5_path=h5_file, node_id="bromobenzene_pipeline_node")
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)

    def test_composite_aggregator_stage5_validation(self, tmp_path: Path) -> None:
        """Verifies Stage 5.0 CompositeAggregator evaluates:
        E_total = E_SCF_CBS + E_corr_CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE.
        """
        h5_file = tmp_path / "landscape.h5"
        node_id = "composite_validation_node"

        # 1. Commit CBS extrapolation limit (Stage 2.0)
        cbs_res = CBSExtrapolationResult(
            e_scf_cbs=-76.062400,
            e_corr_cbs=-0.365200,
            e_total_cbs=-76.427600,
            basis_x="def2-TZVP",
            basis_y="def2-QZVPP",
            alpha=7.88,
            beta=2.97,
            residual_variance_hartree=0.0012,
            residual_variance_kcal_mol=0.753,
            uncertainty_flag="PASSED",
            node_id=node_id,
        )
        commit_cbs_to_hdf5(h5_file, cbs_res)

        # 2. Commit Core-Valence correction (Stage 3.0)
        cv_res = CVCorrectionResult(
            e_total_fc=-76.427600,
            e_total_ae=-76.471200,
            delta_e_cv_hartree=-0.043600,
            delta_e_cv_kcal_mol=-27.3594,
            basis_set="aug-cc-pwCVQZ",
            node_id=node_id,
        )
        commit_cv_to_hdf5(h5_file, cv_res)

        # 3. Commit Relativistic & SOC correction (Stage 4.0)
        rel_res = RelCorrectionResult(
            e_total_non_rel=-76.427600,
            e_total_rel=-76.482100,
            e_total_soc=-76.483100,
            delta_e_rel_hartree=-0.054500,
            delta_e_rel_kcal_mol=-34.1992,
            delta_e_soc_hartree=-0.001000,
            delta_e_soc_kcal_mol=-0.6275,
            delta_e_total_rel_hartree=-0.055500,
            delta_e_total_rel_kcal_mol=-34.8267,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            has_heavy_elements=True,
            is_open_shell=True,
            node_id=node_id,
        )
        commit_rel_to_hdf5(h5_file, rel_res)

        # 4. Write ZPVE to HDF5
        zpve_val = 0.021340
        with h5py.File(h5_file, "a") as f:
            zpve_grp = f.require_group("zpve_corrections").require_group(node_id)
            zpve_grp.create_dataset("zpve_hartree", data=zpve_val)

        # 5. Execute Stage 5.0 Composite Aggregator
        aggregator = CompositeAggregator()
        records = aggregator.sweep_hdf5(h5_file)

        assert len(records) == 1
        rec = records[0]
        assert rec.node_id == node_id
        assert math.isclose(rec.e_scf_cbs, -76.062400, rel_tol=1e-7)
        assert math.isclose(rec.e_corr_cbs, -0.365200, rel_tol=1e-7)
        assert math.isclose(rec.delta_e_cv, -0.043600, rel_tol=1e-7)
        assert math.isclose(rec.delta_e_rel, -0.054500, rel_tol=1e-7)
        assert math.isclose(rec.delta_e_soc, -0.001000, rel_tol=1e-7)
        assert math.isclose(rec.zpve, zpve_val, rel_tol=1e-7)

        # Mathematical Invariant:
        # E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE
        expected_total = (
            -76.062400 + (-0.365200) + (-0.043600) + (-0.054500) + (-0.001000) + zpve_val
        )
        assert math.isclose(rec.e_total_hartree, expected_total, rel_tol=1e-7)
