"""Client-Side Preflight Geometry Validator & Autonomous Log Diagnostic Parser Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §4.4, §8B, §10.2, §16, Suggestion #126.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Instantaneous preflight validation of atomic clashes (< 0.8 A) raising PreflightValidationError.
2. Spin multiplicity parity and charge consistency checking against dynamic proton sum.
3. Spin contamination enforcement (< 10% deviation from ideal S(S+1)).
4. Mandatory empirical dispersion (D3/D4/VV10) check for non-covalent complexes (§4.4).
5. Autonomous failure pattern parsing and remediation synthesis from quantum logs (SCF, Grid, Optimizer, Memory).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cochem_base.analysis.log_diagnostics import (
    FailureCategory,
    QuantumLogDiagnosticParser,
)
from cochem_base.core_engine.preflight import (
    PreflightGeometryValidator,
    PreflightValidationError,
)


def test_preflight_steric_clash_detection():
    """Assert atomic clashes (r_ij = 0.5 A < 0.8 A) trigger immediate PreflightValidationError [M]."""
    # Clashing H2 coords at 0.50 A
    symbols = ["H", "H"]
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.50]], dtype=np.float64)

    with pytest.raises(PreflightValidationError, match="Severe steric clash detected"):
        PreflightGeometryValidator.validate(symbols, coords, charge=0, multiplicity=1)


def test_preflight_unbound_atom_detection():
    """Assert isolated atom separated by > 8.0 A triggers PreflightValidationError [M]."""
    symbols = ["O", "H", "H"]
    coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.96],
        [0.0, 0.0, 9.50],  # Detached hydrogen at 8.54 A from nearest neighbor
    ], dtype=np.float64)

    with pytest.raises(PreflightValidationError, match="Unbound atom detected"):
        PreflightGeometryValidator.validate(symbols, coords, charge=0, multiplicity=1)


def test_preflight_spin_multiplicity_and_parity():
    """Assert unphysical spin multiplicity violating electron parity is rejected [M]."""
    # Water: O (Z=8) + 2*H (Z=1) = 10 electrons (even). Multiplicity must be odd (1, 3, 5).
    symbols = ["O", "H", "H"]
    coords = np.array([
        [0.0, 0.0, 0.117],
        [0.0, 0.757, -0.469],
        [0.0, -0.757, -0.469],
    ], dtype=np.float64)

    # Valid singlet passes
    res = PreflightGeometryValidator.validate(symbols, coords, charge=0, multiplicity=1)
    assert res["valid"] is True

    # Doublet (M=2) for neutral water is unphysical
    with pytest.raises(PreflightValidationError, match="Spin multiplicity 2 is inconsistent"):
        PreflightGeometryValidator.validate(symbols, coords, charge=0, multiplicity=2)


def test_preflight_spin_contamination_threshold():
    """Assert spin contamination >= 10% from ideal S(S+1) triggers PreflightValidationError [M]."""
    # Triplet radical (S=1, ideal <S^2> = 1*(1+1) = 2.0)
    # Contaminated <S^2> = 2.25 -> 12.5% deviation (> 10% limit)
    symbols = ["O", "O"]
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.21]], dtype=np.float64)

    with pytest.raises(PreflightValidationError, match="Spin contamination exceeds 10.0% limit"):
        PreflightGeometryValidator.validate(
            symbols, coords, charge=0, multiplicity=3, computed_s2=2.25
        )

    # Clean triplet with <S^2> = 2.02 (1% deviation) passes
    res = PreflightGeometryValidator.validate(
        symbols, coords, charge=0, multiplicity=3, computed_s2=2.02
    )
    assert res["valid"] is True


def test_preflight_mandatory_dispersion_for_complexes():
    """Assert non-covalent complex missing empirical dispersion (D3/D4) is rejected [M]."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = np.array([
        [-1.464, -0.010, 0.000],
        [-0.505, -0.031, 0.000],
        [-1.782, 0.892, 0.000],
        [1.442, 0.010, 0.000],
        [1.798, -0.428, 0.762],
        [1.798, -0.428, -0.762],
    ], dtype=np.float64)

    # Missing dispersion flag
    with pytest.raises(PreflightValidationError, match="requires explicit empirical dispersion"):
        PreflightGeometryValidator.validate(
            symbols,
            coords,
            is_non_covalent=True,
            dft_keywords="! B3LYP def2-TZVP Opt",
        )

    # Deck with D3BJ passes
    res_d3 = PreflightGeometryValidator.validate(
        symbols,
        coords,
        is_non_covalent=True,
        dft_keywords="! B3LYP D3BJ def2-TZVP Opt",
    )
    assert res_d3["valid"] is True

    # Deck with D4 passes
    res_d4 = PreflightGeometryValidator.validate(
        symbols,
        coords,
        is_non_covalent=True,
        dft_keywords="! r2SCAN-3c D4 Opt",
    )
    assert res_d4["valid"] is True


def test_log_diagnostic_parser_scf_failure(tmp_path: Path):
    """Assert QuantumLogDiagnosticParser identifies SCF divergence and recommends remediation [M]."""
    orca_scf_log = """
    -------------------------
    ORCA SCF ITERATIONS
    -------------------------
    ITER       Energy         Delta-E        Max-DP
    001    -76.4321000000   0.0000000000   0.084123
    ...
    125    -76.4520000000   0.0000120000   0.004123
    *** SCF NOT CONVERGED AFTER 125 ITERATIONS ***
    Error: Maximum number of iterations reached without SCF convergence.
    """
    log_file = tmp_path / "orca_scf.out"
    log_file.write_text(orca_scf_log, encoding="utf-8")

    diag = QuantumLogDiagnosticParser.parse_file(log_file, engine="ORCA")
    assert diag["failure_detected"] is True
    assert diag["primary_failure"] == FailureCategory.SCF_NON_CONVERGENCE

    recs = " ".join(diag["recommended_directives"])
    assert "SlowConv" in recs or "MaxIter 300" in recs or "Shift" in recs
    assert "input_patch" in diag or "suggested_patch" in diag


def test_log_diagnostic_parser_grid_instability_and_optimizer_divergence():
    """Assert grid numerical instability and optimizer divergence produce actionable patches [M]."""
    grid_log = "Numerical instability in DFT grid integration: radial grid overflow."
    res_grid = QuantumLogDiagnosticParser.parse_log_text(grid_log)
    assert res_grid["failure_detected"] is True
    assert res_grid["primary_failure"] == FailureCategory.GRID_INSTABILITY
    assert "DefGrid3" in " ".join(res_grid["recommended_directives"])

    opt_log = "GEOMETRY OPTIMIZATION FAILED: gradient norm exploded, trust radius too small."
    res_opt = QuantumLogDiagnosticParser.parse_log_text(opt_log)
    assert res_opt["failure_detected"] is True
    assert res_opt["primary_failure"] == FailureCategory.OPTIMIZER_DIVERGENCE
    assert "InHess XTB2" in " ".join(res_opt["recommended_directives"]) or "Lindh" in " ".join(res_opt["recommended_directives"])
