"""Physical Zero-Mock Test for Preflight Geometry Validator and Log Diagnostic Triage.

Validates Suggestion #47:
- Detection of unphysical spin multiplicity (e.g. unphysical triplet/doublet for water).
- Detection of steric overlaps (< 0.8 Å) and unbound fragments (> 8.0 Å).
- Mandatory empirical dispersion check (D3BJ/D4) for multi-fragment non-covalent complexes.
- Automated failure pattern parsing and remediation guidance from engine logs (SCF, basis, memory).
"""

import numpy as np
import pytest
from pathlib import Path

from cochem_base.exceptions import PreflightValidationError
from cochem_base.validators.preflight import PreflightGeometryValidator
from cochem_base.diagnostics.log_parser import LogDiagnosticParser


def test_preflight_validator_spin_multiplicity_and_parity():
    """Assert unphysical spin multiplicity raises PreflightValidationError."""
    # Water molecule: O + H + H = 8 + 1 + 1 = 10 electrons (even)
    symbols = ["O", "H", "H"]
    coords = np.array([
        [0.000, 0.000, 0.117],
        [0.000, 0.757, -0.469],
        [0.000, -0.757, -0.469]
    ], dtype=np.float64)

    # 1. Valid singlet ground-state water: M=1 (passes)
    assert PreflightGeometryValidator.validate(symbols, coords, charge=0, multiplicity=1) is True

    # 2. Parity violation: Doublet water M=2 (10 electrons cannot form doublet)
    with pytest.raises(PreflightValidationError, match="Spin multiplicity 2 is unphysical"):
        PreflightGeometryValidator.validate(symbols, coords, charge=0, multiplicity=2)

    # 3. Unphysical triplet water monomer: M=3
    with pytest.raises(PreflightValidationError, match="Spin multiplicity 3 is unphysical for neutral ground-state water"):
        PreflightGeometryValidator.validate(symbols, coords, charge=0, multiplicity=3)


def test_preflight_validator_steric_clash_and_unbound_fragment():
    """Assert steric overlaps (<0.8 A) and unbound fragments (>8.0 A) are rejected."""
    # Steric clash (distance 0.5 A)
    clashing_coords = np.array([
        [0.000, 0.000, 0.000],
        [0.000, 0.000, 0.500]
    ], dtype=np.float64)
    with pytest.raises(PreflightValidationError, match="Steric overlap detected"):
        PreflightGeometryValidator.validate(["H", "H"], clashing_coords, charge=0, multiplicity=1)

    # Unbound detached fragment (> 8.0 A)
    unbound_coords = np.array([
        [0.000, 0.000, 0.000],
        [0.000, 0.000, 10.500]
    ], dtype=np.float64)
    with pytest.raises(PreflightValidationError, match="Unbound fragment detected"):
        PreflightGeometryValidator.validate(["H", "H"], unbound_coords, charge=0, multiplicity=1)


def test_preflight_validator_dispersion_enforcement_for_complexes():
    """Assert non-covalent complex missing D3BJ or D4 raises PreflightValidationError."""
    # Water dimer (two disconnected H2O fragments at 2.91 A O...O separation)
    dimer_coords = np.array([
        [-1.464, -0.010, 0.000],
        [-0.505, -0.031, 0.000],
        [-1.782, 0.892, 0.000],
        [1.442, 0.010, 0.000],
        [1.798, -0.428, 0.762],
        [1.798, -0.428, -0.762]
    ], dtype=np.float64)
    dimer_symbols = ["O", "H", "H", "O", "H", "H"]

    # Missing dispersion: raise PreflightValidationError
    with pytest.raises(PreflightValidationError, match="Non-covalent complex missing mandatory empirical dispersion"):
        PreflightGeometryValidator.validate(
            dimer_symbols,
            dimer_coords,
            charge=0,
            multiplicity=1,
            dft_keywords=["B3LYP", "def2-TZVP"]  # Missing D3BJ or D4
        )

    # With D3BJ: passes
    assert PreflightGeometryValidator.validate(
        dimer_symbols,
        dimer_coords,
        charge=0,
        multiplicity=1,
        dft_keywords=["B3LYP", "D3BJ", "def2-TZVP"]
    ) is True

    # With D4: passes
    assert PreflightGeometryValidator.validate(
        dimer_symbols,
        dimer_coords,
        charge=0,
        multiplicity=1,
        dft_keywords="! r2SCAN-3c D4 def2-mTZVP"
    ) is True


def test_log_diagnostic_parser_scf_failure(tmp_path: Path):
    """Assert parser identifies SCF non-convergence and recommends SOSCF and MaxIter increases."""
    orca_scf_fail_log = """
    ----------------
    ORCA SCF ITERATIONS
    ----------------
    ITER       Energy         Delta-E        Max-DP      RMS-DP      [Eigenvalues]
    000    -76.0123456789   0.0000000000   0.084123    0.012345
    ...
    125    -76.0543210987   0.0000123456   0.004123    0.000845
    
    *** SCF NOT CONVERGED AFTER 125 ITERATIONS ***
    Error: The SCF has not converged. Terminating calculation.
    """
    log_file = tmp_path / "orca_scf_fail.out"
    log_file.write_text(orca_scf_fail_log, encoding="utf-8")

    result = LogDiagnosticParser.parse_file(log_file)
    assert result.is_failure is True
    assert result.failure_mode == "SCF_NON_CONVERGENCE"
    assert "SCF NOT CONVERGED" in result.matched_pattern

    recs_str = " ".join(result.recommendations)
    assert "MaxIter" in recs_str
    assert "SOSCF" in recs_str


def test_log_diagnostic_parser_basis_and_memory_failures():
    """Assert parser identifies basis set linear dependence and memory exhaustion."""
    basis_log = "Error: linear dependency detected in basis set: redundant basis functions found."
    res_basis = LogDiagnosticParser.parse_text(basis_log)
    assert res_basis.is_failure is True
    assert res_basis.failure_mode == "BASIS_LINEAR_DEPENDENCE"

    memory_log = "ORCA finished by error: Out of memory during integral transformation."
    res_mem = LogDiagnosticParser.parse_text(memory_log)
    assert res_mem.is_failure is True
    assert res_mem.failure_mode == "MEMORY_EXHAUSTION"
    assert "%maxcore" in " ".join(res_mem.recommendations)
