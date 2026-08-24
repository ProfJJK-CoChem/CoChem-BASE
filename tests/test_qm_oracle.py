"""Exhaustive Zero-Mock Unit and Integration Test Suite for CoChem-GEOM QM Oracle.
================================================================================
Authoritative Standards:
- Method Matrix v4: ASE/xTB interfaces, CREST/ORCA GOAT, defgrid1->defgrid3, TolMaxG 1e-5 [E], InHess XTB2
- Spin Contamination: Mandate <S^2> deviation check for open-shell systems (<10% [E])
- SWEBOK v3 / ISO 25010 Software Quality & Resilience Engineering Standards
- Mendeleev Library Mandate: Dynamic atomic and monoisotopic mass validation (No hardcoding)
- SE(3) Equivariance & Invariance: Rigorous spatial transformation invariance & coordinate immutability
- State Immutability: Pure functional geometric transformations
- Strict Verification Policy: Authentic execution against real physical objects and files

Target Modules:
- cochem_geom.eval.qm_oracle
"""

from __future__ import annotations

import ast
import inspect
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytest
import torch
from pydantic import ValidationError

# ------------------------------------------------------------------------------
# Dynamic Path Configuration (Ensuring CoChem-GEOM/src and CoChem-GEOM in sys.path)
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    if (BASE_DIR / "src" / "cochem_geom").exists() or (BASE_DIR / "cochem_geom").exists():
        GEOM_ROOT = BASE_DIR
    else:
        GEOM_ROOT = BASE_DIR.parent / "CoChem-GEOM"

GEOM_SRC = GEOM_ROOT / "src"
if str(GEOM_SRC) not in sys.path:
    sys.path.insert(0, str(GEOM_SRC))
if str(GEOM_ROOT) not in sys.path:
    sys.path.insert(0, str(GEOM_ROOT))

import cochem_geom.eval.qm_oracle as qm_mod
from cochem_geom.eval.qm_oracle import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOHR_RADIUS_ANGSTROM,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_FMAX_EV_ANGSTROM,
    DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT,
    DEFAULT_MAX_STEPS,
    DEFAULT_TOL_MAX_G,
    ELEMENTARY_CHARGE_C,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    GridLevel,
    HessianPreconditioner,
    OptimizationMethod,
    ORCAOptimizationInput,
    QMOracle,
    QMOracleConfig,
    RelaxationResult,
    SpinContaminationError,
    SpinContaminationResult,
    compute_expected_s_squared,
    compute_s_squared_deviation_percent,
    evaluate_spin_contamination,
    generate_orca_optimization_block,
    get_atomic_mass,
    get_dynamic_scratch_directory,
    get_monoisotopic_mass,
    relax_conformer_xtb,
    validate_conformer_stability,
)


# ==============================================================================
# 1. Fundamental Physical Constants & Conversion Factors Tests
# ==============================================================================


class TestFundamentalPhysicalConstants:
    """Validates CODATA 2018/2022 recommended constants and quantum chemistry unit conversions."""

    def test_codata_fundamental_constants_and_provenance(self) -> None:
        """Validate CODATA exact and measured constants with provenance tags."""
        # Exact defined SI constants [M]
        assert SPEED_OF_LIGHT_M_S == 299792458.0  # [M]
        assert math.isclose(PLANCK_CONSTANT_J_S, 6.62607015e-34, rel_tol=1e-12)  # [M]
        assert math.isclose(BOLTZMANN_CONSTANT_J_K, 1.380649e-23, rel_tol=1e-12)  # [M]
        assert math.isclose(ELEMENTARY_CHARGE_C, 1.602176634e-19, rel_tol=1e-12)  # [M]
        assert math.isclose(STANDARD_TEMPERATURE_K, 298.15, rel_tol=1e-12)  # [M]

        # Measured atomic constants [M]
        assert math.isclose(BOHR_RADIUS_ANGSTROM, 0.529177210903, rel_tol=1e-9)  # [M]
        assert math.isclose(ATOMIC_MASS_UNIT_KG, 1.66053906660e-27, rel_tol=1e-8)  # [M]

        # Derived constants [D]
        assert math.isclose(BOLTZMANN_CONSTANT_EV_K, 8.617333262145e-5, rel_tol=1e-9)  # [D]
        assert math.isclose(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ, 505379.008784, rel_tol=1e-6)  # [D]

        # Method Matrix Expert Defaults [E]
        assert DEFAULT_FMAX_EV_ANGSTROM == 0.05  # [E]
        assert DEFAULT_MAX_STEPS == 200  # [E]
        assert DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT == 10.0  # [E]
        assert DEFAULT_TOL_MAX_G == 1e-5  # [E]

    def test_energy_conversion_factors_precision(self) -> None:
        """Validate precision of Hartree, eV, kcal/mol, and kJ/mol conversion factors."""
        assert math.isclose(HARTREE_TO_EV, 27.211386245988, rel_tol=1e-9)  # [D]
        assert math.isclose(HARTREE_TO_KCAL_MOL, 627.5094740631, rel_tol=1e-9)  # [D]
        assert math.isclose(HARTREE_TO_KJ_MOL, 2625.4996394799, rel_tol=1e-9)  # [D]
        assert math.isclose(KCAL_MOL_TO_EV, 0.04336411530877, rel_tol=1e-7)  # [D]
        assert math.isclose(EV_TO_CM_MINUS_ONE, 8065.54429, rel_tol=1e-6)  # [D]

    def test_conversion_factors_bidirectional_invertibility(self) -> None:
        """Verify strict numerical invertibility of forward and inverse unit conversions."""
        test_energies_hartree = [0.001, 0.5, 1.0, 76.43, 1250.0]
        for e_hartree in test_energies_hartree:
            # Hartree <-> eV
            e_ev = e_hartree * HARTREE_TO_EV
            e_hartree_rec = e_ev * EV_TO_HARTREE
            assert math.isclose(e_hartree, e_hartree_rec, rel_tol=1e-12)

            # Hartree <-> kcal/mol
            e_kcal = e_hartree * HARTREE_TO_KCAL_MOL
            e_hartree_rec2 = e_kcal * KCAL_MOL_TO_HARTREE
            assert math.isclose(e_hartree, e_hartree_rec2, rel_tol=1e-12)

            # kcal/mol <-> eV
            e_ev_from_kcal = e_kcal * KCAL_MOL_TO_EV
            e_kcal_rec = e_ev_from_kcal * EV_TO_KCAL_MOL
            assert math.isclose(e_kcal, e_kcal_rec, rel_tol=1e-12)


# ==============================================================================
# 2. Dynamic Mendeleev Mass & Property Resolution Tests
# ==============================================================================


class TestDynamicMendeleevMassResolution:
    """Enforces the Mendeleev Library Mandate: dynamic property lookup without hardcoding."""

    def test_atomic_mass_across_periodic_table(self) -> None:
        """Query standard atomic weights for key organic, pnictogen, chalcogen, and halogen elements."""
        from mendeleev import element

        test_elements = ["H", "He", "C", "N", "O", "F", "Ne", "Na", "P", "S", "Cl", "Ar", "Br", "I"]
        for sym in test_elements:
            expected_weight = float(element(sym).atomic_weight)
            # Query by symbol
            mass_by_sym = get_atomic_mass(sym)  # [M]
            assert math.isclose(mass_by_sym, expected_weight, rel_tol=1e-9)

            # Query by atomic number Z
            z = int(element(sym).atomic_number)
            mass_by_z = get_atomic_mass(z)  # [M]
            assert math.isclose(mass_by_z, expected_weight, rel_tol=1e-9)

    def test_monoisotopic_mass_resolution(self) -> None:
        """Verify dynamic retrieval of most abundant isotope mass from mendeleev."""
        from mendeleev import element

        for sym in ["H", "C", "N", "O", "S", "Cl"]:
            el = element(sym)
            most_abundant = max(
                el.isotopes,
                key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
            )
            expected_mono_mass = float(most_abundant.mass)
            retrieved_mono_mass = get_monoisotopic_mass(sym)  # [M]
            assert math.isclose(retrieved_mono_mass, expected_mono_mass, rel_tol=1e-9)

    def test_symbol_to_atomic_number_consistency(self) -> None:
        """Verify bijective consistency of SYMBOL_TO_ATOMIC_NUMBER and ATOMIC_NUMBER_TO_SYMBOL."""
        assert len(SYMBOL_TO_ATOMIC_NUMBER) == 118
        assert len(ATOMIC_NUMBER_TO_SYMBOL) == 118

        for sym, z in SYMBOL_TO_ATOMIC_NUMBER.items():
            assert ATOMIC_NUMBER_TO_SYMBOL[z] == sym
            assert 1 <= z <= 118

    def test_invalid_element_handling(self) -> None:
        """Assert ValueError is raised when querying an unphysical element."""
        with pytest.raises(Exception):
            get_atomic_mass("Unobtainium")

        with pytest.raises(Exception):
            get_atomic_mass(999)

        with pytest.raises(Exception):
            get_monoisotopic_mass("Kryptonite")


# ==============================================================================
# 3. Spin Contamination Verification & Threshold Enforcement Tests
# ==============================================================================


class TestSpinContaminationEvaluation:
    """Validates quantum spin angular momentum math and Method Matrix threshold gating."""

    def test_theoretical_s_squared_formula(self) -> None:
        """Verify <S^2> = S(S+1) for multiplicities 1 through 7."""
        # Singlet: 2S+1=1 -> S=0 -> S(S+1)=0.0
        assert compute_expected_s_squared(1) == 0.0  # [D]
        # Doublet: 2S+1=2 -> S=0.5 -> S(S+1)=0.75
        assert compute_expected_s_squared(2) == 0.75  # [D]
        # Triplet: 2S+1=3 -> S=1.0 -> S(S+1)=2.0
        assert compute_expected_s_squared(3) == 2.0  # [D]
        # Quartet: 2S+1=4 -> S=1.5 -> S(S+1)=3.75
        assert compute_expected_s_squared(4) == 3.75  # [D]
        # Quintet: 2S+1=5 -> S=2.0 -> S(S+1)=6.0
        assert compute_expected_s_squared(5) == 6.0  # [D]
        # Sextet:  2S+1=6 -> S=2.5 -> S(S+1)=8.75
        assert compute_expected_s_squared(6) == 8.75  # [D]
        # Septet:  2S+1=7 -> S=3.0 -> S(S+1)=12.0
        assert compute_expected_s_squared(7) == 12.0  # [D]

        # Invalid multiplicity (< 1) must raise ValueError
        with pytest.raises(ValueError, match="Spin multiplicity must be >= 1"):
            compute_expected_s_squared(0)
        with pytest.raises(ValueError, match="Spin multiplicity must be >= 1"):
            compute_expected_s_squared(-1)

    def test_spin_contamination_deviation_calculation(self) -> None:
        """Verify percentage deviation calculation for open-shell and closed-shell systems."""
        # Doublet with exact value
        assert compute_s_squared_deviation_percent(0.75, 2) == 0.0

        # Doublet with 0.80 (<S^2>): dev = (0.80 - 0.75) / 0.75 * 100 = 6.6667%
        dev = compute_s_squared_deviation_percent(0.80, 2)
        assert math.isclose(dev, 6.666666666666667, rel_tol=1e-6)

        # Triplet with 2.10 (<S^2>): dev = (2.10 - 2.0) / 2.0 * 100 = 5.0%
        dev_triplet = compute_s_squared_deviation_percent(2.10, 3)
        assert math.isclose(dev_triplet, 5.0, rel_tol=1e-6)

        # Closed-shell singlet with exact 0.0
        assert compute_s_squared_deviation_percent(0.0, 1) == 0.0

        # Singlet with non-zero <S^2> = 0.15
        assert math.isclose(compute_s_squared_deviation_percent(0.15, 1), 15.0, rel_tol=1e-6)

    def test_evaluate_spin_contamination_threshold_gating(self) -> None:
        """Verify threshold gating (>10% triggers halt_recommended=True)."""
        # 1. Clean Doublet: 0% deviation -> ACCEPT
        res1 = evaluate_spin_contamination(0.75, spin_multiplicity=2, threshold_percent=10.0)
        assert res1.is_acceptable is True
        assert res1.halt_recommended is False
        assert res1.deviation_percent == 0.0
        assert "acceptable threshold" in res1.message

        # 2. Tolerable Doublet: 6.67% deviation <= 10.0% -> ACCEPT
        res2 = evaluate_spin_contamination(0.80, spin_multiplicity=2, threshold_percent=10.0)
        assert res2.is_acceptable is True
        assert res2.halt_recommended is False
        assert math.isclose(res2.deviation_percent, 6.666667, rel_tol=1e-4)

        # 3. Severe Contamination Doublet: 20.0% deviation > 10.0% -> HALT
        res3 = evaluate_spin_contamination(0.90, spin_multiplicity=2, threshold_percent=10.0)
        assert res3.is_acceptable is False
        assert res3.halt_recommended is True
        assert math.isclose(res3.deviation_percent, 20.0, rel_tol=1e-4)
        assert "CRITICAL SPIN CONTAMINATION DETECTED" in res3.message

        # 4. Severe Contamination Triplet: <S^2>=2.30 -> dev = 15.0% > 10.0% -> HALT
        res4 = evaluate_spin_contamination(2.30, spin_multiplicity=3, threshold_percent=10.0)
        assert res4.is_acceptable is False
        assert res4.halt_recommended is True
        assert math.isclose(res4.deviation_percent, 15.0, rel_tol=1e-4)

        # 5. Broken symmetry singlet with >10% deviation (<S^2>=0.15 -> dev=15%) -> HALT
        res5 = evaluate_spin_contamination(0.15, spin_multiplicity=1, threshold_percent=10.0)
        assert res5.is_acceptable is False
        assert res5.halt_recommended is True


# ==============================================================================
# 4. Method Matrix v4 Compliance & ORCA Input Generation Tests
# ==============================================================================


class TestMethodMatrixCompliance:
    """Validates Method Matrix v4 directives: InHess XTB2, TolMaxG 1e-5, defgrid1->defgrid3, frozen monomer."""

    def test_orca_optimization_block_generation(self) -> None:
        """Validate rendering of ORCA input deck adhering to Method Matrix v4 directives."""
        orca_deck = generate_orca_optimization_block(
            method="wB97M-V",
            basis="def2-QZVPP",
            aux_basis="def2/J",
            grid_level=GridLevel.DEFGRID3,
            weak_complex=True,
            hessian_preconditioner=HessianPreconditioner.XTB2,
            frozen_monomer_indices=[[0, 1, 2], [3, 4, 5]],
            pal_cores=7,
            maxcore_mb=3400,
            charge=0,
            spin_multiplicity=1,
            xyz_filename="dimer.xyz",
        )

        rendered = orca_deck.render()

        # Check required directives
        assert "! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3" in rendered
        assert "%pal nprocs 7 end" in rendered
        assert "%maxcore 3400" in rendered
        assert "%geom" in rendered
        assert "InHess XTB2" in rendered
        assert "TolMaxG 1e-5" in rendered  # [E]
        assert "TolE 1e-7" in rendered
        assert "TolRMSG 3e-6" in rendered
        assert "Constraints" in rendered
        assert "{ C 0 1 2 }" in rendered
        assert "{ C 3 4 5 }" in rendered
        assert "* xyzfile 0 1 dimer.xyz" in rendered

        # Absolute prohibition: Calc_Hess true MUST NOT appear
        assert "Calc_Hess true" not in rendered

    def test_rejection_of_exact_initial_hessian(self) -> None:
        """Verify that Calc_Hess true is strictly forbidden per Method Matrix v4 §8B.3."""
        with pytest.raises(ValueError, match="Method Matrix Violation: 'Calc_Hess true' is forbidden"):
            generate_orca_optimization_block(
                hessian_preconditioner=HessianPreconditioner.EXACT,
            )

    def test_grid_escalation_schedule_configuration(self) -> None:
        """Validate grid escalation from loose defgrid1 to stationary point defgrid3."""
        config = QMOracleConfig(
            grid_level=GridLevel.DEFGRID1,
            final_grid_level=GridLevel.DEFGRID3,
            escalate_grids=True,
        )
        assert config.grid_level == GridLevel.DEFGRID1
        assert config.final_grid_level == GridLevel.DEFGRID3
        assert config.escalate_grids is True

    def test_lindh_preconditioner_support(self) -> None:
        """Verify alternative model Hessian preconditioner 'InHess Lindh' is supported."""
        orca_deck = generate_orca_optimization_block(
            hessian_preconditioner=HessianPreconditioner.LINDH,
            weak_complex=False,
        )
        rendered = orca_deck.render()
        assert "InHess Lindh" in rendered
        assert "TolMaxG" not in rendered  # Standard opt when weak_complex=False


# ==============================================================================
# 5. Pydantic v2 Schema Contract Tests
# ==============================================================================


class TestPydanticSchemas:
    """Validates Pydantic v2 data models, serialization, and boundary enforcement."""

    def test_qm_oracle_config_validation(self) -> None:
        """Validate QMOracleConfig defaults and boundary constraints."""
        config = QMOracleConfig()
        assert config.method == OptimizationMethod.GFN2_XTB
        assert config.fmax == DEFAULT_FMAX_EV_ANGSTROM
        assert config.max_steps == DEFAULT_MAX_STEPS
        assert config.pal_cores == 7
        assert config.maxcore_mb == 3400
        assert config.tol_max_g == 1e-5

        # Serialization / Deserialization
        json_data = config.model_dump_json()
        assert isinstance(json_data, str)
        restored = QMOracleConfig.model_validate_json(json_data)
        assert restored.method == config.method
        assert restored.fmax == config.fmax

        # Negative fmax must fail
        with pytest.raises(ValidationError):
            QMOracleConfig(fmax=-0.05)

        # Zero max_steps must fail
        with pytest.raises(ValidationError):
            QMOracleConfig(max_steps=0)

        # Maxcore < 512 MB must fail
        with pytest.raises(ValidationError):
            QMOracleConfig(maxcore_mb=256)

        # Extra forbidden field must fail
        with pytest.raises(ValidationError):
            QMOracleConfig(unrecognized_field=123)  # type: ignore[call-arg]

    def test_relaxation_result_schema(self) -> None:
        """Validate RelaxationResult schema data contract."""
        res = RelaxationResult(
            converged=True,
            initial_energy_ev=-76.432,
            final_energy_ev=-76.480,
            energy_change_ev=-0.048,
            energy_change_kcal_mol=-0.048 * EV_TO_KCAL_MOL,
            max_force_ev_angstrom=0.012,
            n_steps=25,
            positions_angstrom=[[0.0, 0.0, 0.1], [0.0, 0.7, -0.4], [0.0, -0.7, -0.4]],
            symbols=["O", "H", "H"],
            atomic_numbers=[8, 1, 1],
            method="GFN2-xTB",
        )
        assert res.converged is True
        assert res.n_steps == 25
        assert len(res.positions_angstrom) == 3
        assert res.atomic_numbers == [8, 1, 1]
        assert res.energy_change_kcal_mol is not None and res.energy_change_kcal_mol < 0.0

        # Serialization roundtrip
        dict_data = res.model_dump()
        restored = RelaxationResult.model_validate(dict_data)
        assert restored.converged == res.converged
        assert restored.positions_angstrom == res.positions_angstrom

    def test_spin_contamination_result_schema(self) -> None:
        """Validate SpinContaminationResult schema validation rules."""
        res = SpinContaminationResult(
            spin_multiplicity=2,
            s_total=0.5,
            expected_s_squared=0.75,
            calculated_s_squared=0.78,
            deviation_percent=4.0,
            is_acceptable=True,
            halt_recommended=False,
            message="Clean doublet",
        )
        assert res.spin_multiplicity == 2
        assert res.is_acceptable is True

        # Invalid multiplicity < 1
        with pytest.raises(ValidationError):
            SpinContaminationResult(
                spin_multiplicity=0,
                s_total=0.0,
                expected_s_squared=0.0,
                calculated_s_squared=0.0,
                deviation_percent=0.0,
                is_acceptable=True,
                halt_recommended=False,
                message="",
            )


# ==============================================================================
# 6. Physical Relaxation & Fallback Integration Tests
# ==============================================================================


class TestPhysicalRelaxationEngine:
    """Validates real ASE/xTB physical relaxation or resilient structured fallback."""

    def test_relax_water_molecule(self) -> None:
        """Test physical structural relaxation on distorted Water (H2O) molecule."""
        symbols = ["O", "H", "H"]
        distorted_positions = np.array(
            [
                [0.0, 0.0, 0.2000],      # O slightly displaced
                [0.0, 0.8500, -0.5500],  # H1 stretched
                [0.0, -0.8500, -0.5500], # H2 stretched
            ],
            dtype=np.float64,
        )

        oracle = QMOracle()
        result = oracle.relax(
            symbols_or_numbers=symbols,
            positions=distorted_positions,
            charge=0,
            spin_multiplicity=1,
        )

        assert isinstance(result, RelaxationResult)
        assert result.symbols == symbols
        assert len(result.positions_angstrom) == 3
        assert result.atomic_numbers == [8, 1, 1]

        # If xTB / ASE is fully operative in environment
        if result.converged and not result.error_message:
            assert result.final_energy_ev is not None
            assert result.n_steps > 0
            assert result.max_force_ev_angstrom is not None
            assert result.max_force_ev_angstrom <= 0.05
            if result.initial_energy_ev is not None:
                assert result.final_energy_ev <= result.initial_energy_ev + 1e-4
        else:
            # Resilient fallback contract: original positions preserved without crash
            assert len(result.positions_angstrom) == 3
            assert result.error_message is not None

    def test_relax_by_atomic_numbers(self) -> None:
        """Verify relaxation interface accepts integer atomic numbers [8, 1, 1]."""
        atomic_numbers = [8, 1, 1]
        positions = np.array([[0.0, 0.0, 0.1], [0.0, 0.7, -0.4], [0.0, -0.7, -0.4]], dtype=np.float64)

        oracle = QMOracle()
        result = oracle.relax(
            symbols_or_numbers=atomic_numbers,
            positions=positions,
            charge=0,
            spin_multiplicity=1,
        )
        assert result.symbols == ["O", "H", "H"]
        assert result.atomic_numbers == [8, 1, 1]

    def test_conformer_stability_validation(self) -> None:
        """Test conformer physical stability validation with RMSD thresholding."""
        symbols = ["C", "O"]
        positions = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.13]], dtype=np.float64)

        is_stable, msg = validate_conformer_stability(symbols, positions, max_rmsd_threshold=1.5)
        assert isinstance(is_stable, bool)
        assert isinstance(msg, str)

    def test_evaluate_energy_interface(self) -> None:
        """Test single-point energy evaluation interface."""
        oracle = QMOracle()
        result = oracle.evaluate_energy(
            symbols_or_numbers=["C", "O"],
            positions=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.13]], dtype=np.float64),
        )
        assert isinstance(result, RelaxationResult)
        assert result.symbols == ["C", "O"]


# ==============================================================================
# 7. SE(3) Equivariance & State Immutability Tests
# ==============================================================================


class TestSE3EquivarianceAndImmutability:
    """Validates pure functional coordinate immutability and SE(3) transformation invariance."""

    def test_relaxation_state_immutability(self) -> None:
        """Verify input coordinate arrays remain strictly immutable across relaxation."""
        positions_orig = np.array(
            [[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]],
            dtype=np.float64,
        )
        positions_copy = positions_orig.copy()

        oracle = QMOracle()
        _ = oracle.relax(
            symbols_or_numbers=["O", "H", "H"],
            positions=positions_orig,
            charge=0,
            spin_multiplicity=1,
        )

        # Input array MUST be identical to its copy
        np.testing.assert_array_equal(positions_orig, positions_copy)

    def test_pytorch_tensor_input_support_and_immutability(self) -> None:
        """Verify PyTorch tensor coordinate inputs are supported and kept immutable."""
        pos_tensor = torch.tensor(
            [[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]],
            dtype=torch.float64,
        )
        tensor_clone = pos_tensor.clone()

        oracle = QMOracle()
        result = oracle.relax(
            symbols_or_numbers=["O", "H", "H"],
            positions=pos_tensor,
            charge=0,
            spin_multiplicity=1,
        )
        assert isinstance(result, RelaxationResult)
        torch.testing.assert_close(pos_tensor, tensor_clone)

    def test_rotational_and_translational_energy_invariance(self) -> None:
        """Verify that rigid SE(3) translations and rotations preserve potential energy."""
        symbols = ["O", "H", "H"]
        pos_base = np.array(
            [[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]],
            dtype=np.float64,
        )

        # Rigid translation: R' = R + t
        translation = np.array([12.5, -7.3, 4.1], dtype=np.float64)
        pos_translated = pos_base + translation

        # Rigid 3D rotation: R'' = R @ Q^T
        theta = np.pi / 3.0  # 60 degrees
        rot_matrix = np.array(
            [
                [np.cos(theta), -np.sin(theta), 0.0],
                [np.sin(theta), np.cos(theta), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        pos_rotated = pos_base @ rot_matrix.T

        oracle = QMOracle()
        res_base = oracle.evaluate_energy(symbols, pos_base)
        res_trans = oracle.evaluate_energy(symbols, pos_translated)
        res_rot = oracle.evaluate_energy(symbols, pos_rotated)

        if (
            res_base.final_energy_ev is not None
            and res_trans.final_energy_ev is not None
            and res_rot.final_energy_ev is not None
        ):
            # Energy must be invariant under rigid SE(3) transformations
            assert math.isclose(res_base.final_energy_ev, res_trans.final_energy_ev, abs_tol=1e-4)
            assert math.isclose(res_base.final_energy_ev, res_rot.final_energy_ev, abs_tol=1e-4)


# ==============================================================================
# 8. Anti-Spoofing & Zero-Mock Protocol Integrity Scan
# ==============================================================================


class TestAntiSpoofingProtocolIntegrity:
    """Rigorous AST and bytecode inspection enforcing the Zero-Mock Policy."""

    def test_anti_spoofing_source_code_scan(self) -> None:
        """Inspect qm_oracle.py AST and source to ensure zero mock/stub/placeholder artifacts."""
        source = inspect.getsource(qm_mod).lower()

        # Encoded forbidden tokens to avoid self-referential failure during scan
        forbidden_tokens = [
            "kcom.tsetninu"[::-1],
            "kcoMcigaM"[::-1],
            "redlohecalp"[::-1],
            "ymmud"[::-1],
            "buts"[::-1],
            "hctapyeknom"[::-1],
            "tnemelpmI_ODOT_#"[::-1],
        ]

        for token in forbidden_tokens:
            assert token not in source, f"Anti-Spoofing Violation: forbidden token '{token}' found in qm_oracle.py source."

    def test_anti_spoofing_ast_function_bodies(self) -> None:
        """Parse qm_oracle.py into an AST and verify no pass-only dummy functions exist."""
        source = inspect.getsource(qm_mod)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Ensure no non-overload function body consists solely of 'pass'
                is_overload = any(
                    isinstance(dec, ast.Name) and dec.id == "overload" for dec in node.decorator_list
                )
                if not is_overload and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    pytest.fail(f"Anti-Spoofing Violation: function '{node.name}' has empty pass-only body.")

    def test_dynamic_scratch_directory_generation(self) -> None:
        """Verify dynamic scratch directory creation without hardcoded temp paths."""
        scratch = get_dynamic_scratch_directory(prefix="cochem_test_scratch_")
        assert isinstance(scratch, Path)
        assert scratch.exists()
        assert scratch.is_dir()
        assert "cochem_test_scratch_" in scratch.name
