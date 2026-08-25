#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 4.0 Scalar Relativistic & Spin-Orbit Corrections Engine.

Module: tests/test_cochem_bench_rel.py
Target Implementation: bench_engine.cochem_bench_rel

Authoritative Requirements & Standards:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_rel.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import pytest
from mendeleev import element

from bench_engine.cochem_bench_rel import (
    RelativisticHamiltonianInjector,
    X2CHandler,
    X2CDivergenceError,
    RelativisticExecutionError,
    SpinOrbitCoupler,
    DeltaRelExtractor,
    RelCorrectionResult,
    commit_rel_to_hdf5,
    read_rel_from_hdf5,
    run_rel_pipeline,
    HARTREE_TO_KCAL_MOL,
)
from bench_engine.cochem_bench_export import (
    CompositeAggregator,
    CompositeEnergyRecord,
)
from bench_engine.cochem_bench_cbs import (
    CBSExtrapolationResult,
    commit_cbs_to_hdf5,
)
from bench_engine.cochem_bench_cv import (
    CVCorrectionResult,
    commit_cv_to_hdf5,
)


# ==============================================================================
# Authentic Molecular Test Fixtures (Angstroms)
# ==============================================================================

# Water Molecule (Light elements: H, O - Z <= 8)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Bromobenzene (Heavy element: Br - Z = 35, Period 4)
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

# Dimethyl Selenide (Heavy element: Se - Z = 34)
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

# Methyl Radical (Open-shell doublet radical: CH3, Mult = 2)
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

ORCA_REL_STDOUT_BROMOBENZENE = """
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

ORCA_REL_DIVERGENCE_STDOUT = """
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

ORCA_SOC_RADICAL_STDOUT = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Relativistic Mode                     ... Exact Two-Component (X2C)
Spin-Orbit Coupling Operator          ... SOMF(1X) (Spin-Orbit Mean-Field)
Multiplicity                          ...    2 (Open-Shell Radical)

-------------------------------------------------------------------------------
SPIN-ORBIT COUPLING CALCULATION
-------------------------------------------------------------------------------
Two-component 2C-SOC expectation value ... -0.00284512 Eh
SOMF(1X) Energy Shift                 ... -0.00284512 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                           -39.754891230000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""


# ==============================================================================
# 1. RelativisticHamiltonianInjector Tests
# ==============================================================================

class TestRelativisticHamiltonianInjector:
    """Tests for relativistic Hamiltonian injection, basis set re-contraction, and heavy-element checks."""

    def test_map_relativistic_basis_set_def2_family(self) -> None:
        """Verifies mapping of Karlsruhe def2 basis sets to relativistically re-contracted X2C variants."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("def2-SVP") == "x2c-SVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVP") == "x2c-TZVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPP") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("def2-QZVPP") == "x2c-QZVPPall-s"

    def test_map_relativistic_basis_set_cc_family(self) -> None:
        """Verifies mapping of Dunning correlation-consistent basis sets to X2C variants."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("cc-pVDZ") == "cc-pVDZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVTZ") == "cc-pVTZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVQZ") == "cc-pVQZ-X2C"
        assert injector.map_relativistic_basis_set("aug-cc-pVTZ") == "aug-cc-pVTZ-X2C"

    def test_map_relativistic_basis_set_already_relativistic(self) -> None:
        """Verifies that pre-recontracted basis sets remain unchanged."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("x2c-TZVPPall-s") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("ano-rcc") == "ano-rcc"
        assert injector.map_relativistic_basis_set("cc-pVTZ-X2C") == "cc-pVTZ-X2C"

    def test_inspect_heavy_elements_light_molecule(self) -> None:
        """Verifies that light systems (e.g., H2O) are identified as not requiring relativistic corrections."""
        injector = RelativisticHamiltonianInjector()
        info = injector.inspect_heavy_elements(WATER_COORDS, relativistic_z_threshold=19)

        assert info["has_heavy_elements"] is False
        assert info["max_z"] == 8  # Oxygen Z=8
        assert len(info["heavy_elements"]) == 0

        # Verify mass retrieved from Mendeleev
        m_o = element("O").mass
        m_h = element("H").mass
        expected_mass = float(m_o + 2 * m_h)
        assert math.isclose(info["total_mass"], expected_mass, rel_tol=1e-5)

    def test_inspect_heavy_elements_heavy_molecule(self) -> None:
        """Verifies that 4th-period+ systems (Bromobenzene, Dimethyl Selenide) are identified as requiring X2C."""
        injector = RelativisticHamiltonianInjector()
        info_br = injector.inspect_heavy_elements(BROMOBENZENE_COORDS, relativistic_z_threshold=19)

        assert info_br["has_heavy_elements"] is True
        assert info_br["max_z"] == 35  # Bromine Z=35
        assert "Br" in info_br["heavy_elements"]

        info_se = injector.inspect_heavy_elements(DMSE_COORDS, relativistic_z_threshold=19)
        assert info_se["has_heavy_elements"] is True
        assert info_se["max_z"] == 34  # Selenium Z=34
        assert "Se" in info_se["heavy_elements"]

    def test_inject_relativistic_hamiltonian_orca_input(self) -> None:
        """Verifies modification of ORCA input text with X2C and re-contracted basis set."""
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

    def test_generate_input_decks(self) -> None:
        """Verifies dual input deck generation for baseline non-relativistic and relativistic jobs."""
        injector = RelativisticHamiltonianInjector()
        decks = injector.generate_input_decks(
            coords=BROMOBENZENE_COORDS,
            method="DLPNO-CCSD(T)",
            base_basis="def2-TZVPP",
            charge=0,
            mult=1,
            node_max_gb=16.0,
            nprocs=4,
        )

        assert "non_rel_input" in decks
        assert "rel_input" in decks
        assert "def2-TZVPP" in decks["non_rel_input"]
        assert "X2C" not in decks["non_rel_input"]

        assert "X2C" in decks["rel_input"]
        assert "x2c-TZVPPall-s" in decks["rel_input"]
        assert decks["has_heavy_elements"] is True


# ==============================================================================
# 2. X2CHandler Tests (Strict Zero-Fallback Policy)
# ==============================================================================

class TestX2CHandler:
    """Tests for X2C divergence detection, fail-fast mechanics, and strict prohibition of DKH2 fallback."""

    def test_detect_divergence_normal_output(self) -> None:
        """Verifies that normal converged output does not trigger divergence flag."""
        handler = X2CHandler()
        assert handler.detect_divergence(ORCA_REL_STDOUT_BROMOBENZENE) is False

    def test_detect_divergence_failure_output(self) -> None:
        """Verifies detection of SCF divergence and DIIS failure in X2C calculation."""
        handler = X2CHandler()
        assert handler.detect_divergence(ORCA_REL_DIVERGENCE_STDOUT) is True

    def test_validate_convergence_success(self) -> None:
        """Verifies extraction of final energy when calculation converges normally."""
        handler = X2CHandler()
        energy = handler.validate_convergence(ORCA_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(energy, -2826.68940125, rel_tol=1e-9)

    def test_validate_convergence_divergence_raises_exception(self) -> None:
        """Verifies that X2CDivergenceError is explicitly raised on divergence and bans DKH2 fallback."""
        handler = X2CHandler()
        with pytest.raises(X2CDivergenceError) as exc_info:
            handler.validate_convergence(ORCA_REL_DIVERGENCE_STDOUT)

        err_msg = str(exc_info.value)
        assert "diverge" in err_msg.lower() or "fail" in err_msg.lower()
        # Verify strict benchmark requirement: no fallback to DKH2
        assert "dkh2" in err_msg.lower() or "uniform" in err_msg.lower()


# ==============================================================================
# 3. SpinOrbitCoupler Tests
# ==============================================================================

class TestSpinOrbitCoupler:
    """Tests for open-shell radical detection and SOMF(1X) operator injection."""

    def test_is_open_shell(self) -> None:
        """Verifies open-shell radical state classification."""
        coupler = SpinOrbitCoupler()
        assert coupler.is_open_shell(mult=1, requires_uhf=False, is_radical=False) is False
        assert coupler.is_open_shell(mult=2, requires_uhf=False, is_radical=False) is True
        assert coupler.is_open_shell(mult=1, requires_uhf=True, is_radical=False) is True
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

    def test_derive_soc_correction_open_shell(self) -> None:
        """Verifies derivation of delta E_SOC for radical states."""
        coupler = SpinOrbitCoupler()
        e_rel = -39.75204611
        e_soc = -39.75489123
        delta_soc = coupler.derive_soc_correction(e_total_rel=e_rel, e_total_soc=e_soc)

        expected = float(e_soc - e_rel)
        assert math.isclose(delta_soc, expected, rel_tol=1e-7)

    def test_derive_soc_correction_closed_shell(self) -> None:
        """Verifies that closed-shell systems yield 0.0 delta E_SOC."""
        coupler = SpinOrbitCoupler()
        delta_soc = coupler.derive_soc_correction(e_total_rel=-2826.68940125, e_total_soc=None)
        assert delta_soc == 0.0


# ==============================================================================
# 4. DeltaRelExtractor Tests
# ==============================================================================

class TestDeltaRelExtractor:
    """Tests for parsing authentic ORCA outputs, computing Delta E_rel, and converting units."""

    def test_parse_final_energy_from_stdout(self) -> None:
        """Verifies extraction of FINAL SINGLE POINT ENERGY from authentic stdout."""
        extractor = DeltaRelExtractor()
        e_non_rel = extractor.parse_final_energy_from_stdout(ORCA_NON_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(e_non_rel, -2805.01248912, rel_tol=1e-9)

        e_rel = extractor.parse_final_energy_from_stdout(ORCA_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(e_rel, -2826.68940125, rel_tol=1e-9)

    def test_extract_delta_scalar_only(self) -> None:
        """Verifies relativistic shift derivation Delta E_rel = E_rel - E_non_rel in Hartree and kcal/mol."""
        extractor = DeltaRelExtractor()
        e_non_rel = -2805.01248912
        e_rel = -2826.68940125

        result = extractor.extract_delta(
            e_total_non_rel=e_non_rel,
            e_total_rel=e_rel,
            e_total_soc=None,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            method="DLPNO-CCSD(T)",
            has_heavy_elements=True,
            is_open_shell=False,
            node_id="bromobenzene_node",
        )

        expected_delta_hartree = float(e_rel - e_non_rel)
        expected_delta_kcal = float(expected_delta_hartree * HARTREE_TO_KCAL_MOL)

        assert math.isclose(result.delta_e_rel_hartree, expected_delta_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_rel_kcal_mol, expected_delta_kcal, rel_tol=1e-9)
        assert result.delta_e_soc_hartree == 0.0
        assert result.delta_e_soc_kcal_mol == 0.0
        assert math.isclose(result.delta_e_total_rel_hartree, expected_delta_hartree, rel_tol=1e-9)
        assert result.node_id == "bromobenzene_node"

    def test_extract_from_outputs(self) -> None:
        """Verifies end-to-end extraction directly from standard output strings."""
        extractor = DeltaRelExtractor()
        result = extractor.extract_from_outputs(
            stdout_non_rel=ORCA_NON_REL_STDOUT_BROMOBENZENE,
            stdout_rel=ORCA_REL_STDOUT_BROMOBENZENE,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            node_id="node_br_01",
        )

        assert result.node_id == "node_br_01"
        assert math.isclose(result.e_total_non_rel, -2805.01248912, rel_tol=1e-9)
        assert math.isclose(result.e_total_rel, -2826.68940125, rel_tol=1e-9)
        assert result.delta_e_rel_hartree < 0.0  # Relativistic energy is deeper/more negative


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Orchestration Tests
# ==============================================================================

class TestHDF5PersistenceAndPipeline:
    """Tests for writing and reading relativistic correction records in landscape.h5."""

    def test_commit_and_read_rel_hdf5(self, tmp_path: Path) -> None:
        """Verifies atomic write to landscape.h5 under rel_corrections and roundtrip read."""
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

        # Inspect HDF5 structure directly
        with h5py.File(h5_file, "r") as f:
            assert "rel_corrections" in f
            assert "node_test_01" in f["rel_corrections"]
            grp = f["rel_corrections"]["node_test_01"]

            assert "delta_e_rel_hartree" in grp
            assert "delta_e_rel_kcal_mol" in grp
            assert "delta_e_soc_hartree" in grp
            assert "delta_e_soc_kcal_mol" in grp
            assert grp.attrs["basis_set"] == "def2-TZVPP"
            assert grp.attrs["rel_basis_set"] == "x2c-TZVPPall-s"
            assert grp.attrs["hamiltonian"] == "X2C"
            assert bool(grp.attrs["has_heavy_elements"]) is True
            assert bool(grp.attrs["is_open_shell"]) is True

        # Read back via API
        data = read_rel_from_hdf5(h5_path=h5_file, node_id="node_test_01")
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)
        assert math.isclose(data["delta_e_soc_hartree"], result.delta_e_soc_hartree, rel_tol=1e-7)
        assert data["basis_set"] == "def2-TZVPP"
        assert data["rel_basis_set"] == "x2c-TZVPPall-s"

    def test_run_rel_pipeline(self, tmp_path: Path) -> None:
        """Verifies end-to-end run_rel_pipeline execution and persistence."""
        h5_file = tmp_path / "landscape.h5"

        result = run_rel_pipeline(
            coords=BROMOBENZENE_COORDS,
            e_total_non_rel=-2805.01248912,
            e_total_rel=-2826.68940125,
            base_basis="def2-TZVPP",
            method="DLPNO-CCSD(T)",
            node_id="bromobenzene_node",
            h5_path=h5_file,
        )

        assert isinstance(result, RelCorrectionResult)
        assert result.has_heavy_elements is True
        assert result.rel_basis_set == "x2c-TZVPPall-s"

        data = read_rel_from_hdf5(h5_path=h5_file, node_id="bromobenzene_node")
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)


# ==============================================================================
# 6. Full Composite Integration Test with Stage 5.0 Exporter
# ==============================================================================

class TestCompositeIntegration:
    """Verifies that Stage 4.0 outputs seamlessly integrate with Stage 5.0 CompositeAggregator."""

    def test_composite_aggregator_sweep_with_rel(self, tmp_path: Path) -> None:
        """Verifies that landscape.h5 containing Stage 2.0 CBS, Stage 3.0 CV, Stage 4.0 Rel, and ZPVE aggregates cleanly."""
        h5_file = tmp_path / "landscape.h5"
        node_id = "test_node_composite"

        # 1. Commit CBS limit (Stage 2.0)
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

        # 2. Commit CV correction (Stage 3.0)
        cv_res = CVCorrectionResult(
            e_total_fc=-76.427600,
            e_total_ae=-76.471200,
            delta_e_cv_hartree=-0.043600,
            delta_e_cv_kcal_mol=-27.3594,
            basis_set="aug-cc-pwCVQZ",
            node_id=node_id,
        )
        commit_cv_to_hdf5(h5_file, cv_res)

        # 3. Commit Relativistic correction (Stage 4.0)
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

        # 5. Sweep via CompositeAggregator (Stage 5.0)
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

        # Invariant: E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE
        expected_total = (
            -76.062400 + (-0.365200) + (-0.043600) + (-0.054500) + (-0.001000) + zpve_val
        )
        assert math.isclose(rec.e_total_hartree, expected_total, rel_tol=1e-7)
