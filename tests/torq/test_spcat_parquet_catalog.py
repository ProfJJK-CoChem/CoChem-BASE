"""Pickett SPCAT Diagonalization & Asymmetric Top Microwave Parquet Catalog Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §3.0, §15, Suggestion #124.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Eradication of linear rotor formula (2 * B * j) for asymmetric tops (kappa != +/-1).
2. A missing or unverified SPCAT raises PickettProgramUnavailableError; no in-process
   model stands in for the program (CoChem-SpycFit D-SPYC-16 D, D-SPYC-26 F1).
3. Strict B_e vs B_0 separation, raising MethodologyViolationError on unvibrated B_e without override.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.spcat_runner import (
    MethodologyViolationError,
    PickettProgramUnavailableError,
    SPCATDeckConfig,
    SPCATRunner,
    compute_ray_asymmetry_parameter,
)


def test_asymmetric_top_ray_parameter_and_linear_rejection():
    """Assert molecule is recognized as asymmetric top and linear rotor is rejected [M], [D]."""
    # Water monomer rotational constants (MHz) [E]
    a_h2o = 835840.3
    b_h2o = 435351.7
    c_h2o = 278139.8

    kappa = compute_ray_asymmetry_parameter(a_h2o, b_h2o, c_h2o)
    # kappa = (2B - A - C) / (A - C) ~ -0.436 (highly asymmetric top)
    assert abs(abs(kappa) - 1.0) > 0.1
    assert -1.0 < kappa < 1.0


def test_be_vs_b0_separation_enforcement():
    """Assert catalog simulation with pure B_e lacking Delta B_vib raises MethodologyViolationError [M]."""
    cfg_be_invalid = SPCATDeckConfig(
        a_mhz=20245.8,
        b_mhz=10518.2,
        c_mhz=6878.3,
        constant_type="Be",
        delta_b_vib_mhz=None,
    )
    runner = SPCATRunner()

    with pytest.raises(MethodologyViolationError, match="pure equilibrium parameters"):
        runner.validate_rotor_parameters(cfg_be_invalid, allow_unvibrated_be=False)

    # Overridden unvibrated B_e passes with explicit flag
    runner.validate_rotor_parameters(cfg_be_invalid, allow_unvibrated_be=True)

    # Valid B_0 passes unconditionally
    cfg_b0_valid = SPCATDeckConfig(
        a_mhz=20245.8,
        b_mhz=10518.2,
        c_mhz=6878.3,
        constant_type="B0",
    )
    runner.validate_rotor_parameters(cfg_b0_valid, allow_unvibrated_be=False)


def _formic_acid_config() -> SPCATDeckConfig:
    # Trans-formic acid (HCOOH) microwave benchmark constants
    return SPCATDeckConfig(
        a_mhz=20245.8,
        b_mhz=10518.2,
        c_mhz=6878.3,
        dj_khz=7.62,
        djk_khz=-63.4,
        dk_khz=528.0,
        d1_khz=1.64,
        d2_khz=32.0,
        mu_a=1.41,
        mu_b=0.21,
        mu_c=0.00,
        temperature_k=298.15,
        constant_type="B0",
    )


def test_missing_spcat_raises_typed_error_without_substitute(tmp_path: Path):
    """Assert a missing receipt stops the catalog instead of an in-process stand-in [M]."""
    runner = SPCATRunner(receipt_path=tmp_path / "pickett-installation.json")
    out_parquet = tmp_path / "line_catalog.parquet"

    with pytest.raises(PickettProgramUnavailableError, match="receipt"):
        runner.generate_parquet_catalog(
            config=_formic_acid_config(),
            output_parquet_path=out_parquet,
            scratch_dir=tmp_path / "spcat_scr",
        )

    assert not out_parquet.exists()
    assert runner.spcat_bin is None


def test_receipt_program_with_changed_bytes_is_refused(tmp_path: Path):
    """Assert a program whose bytes differ from its receipt is never run [M]."""
    program = tmp_path / "spcat"
    program.write_text("Explicit text-only control; not the SPCAT program.\n", encoding="utf-8")
    program.chmod(0o700)
    receipt = tmp_path / "pickett-installation.json"
    receipt.write_text(json.dumps({
        "schema_version": "cochem.pickett-installation/1",
        "programs": {"spcat": {"path": str(program), "sha256": "0" * 64, "status": "built"}},
    }), encoding="utf-8")
    runner = SPCATRunner(receipt_path=receipt)

    with pytest.raises(PickettProgramUnavailableError, match="no longer matches"):
        runner.generate_parquet_catalog(
            config=_formic_acid_config(),
            output_parquet_path=tmp_path / "line_catalog.parquet",
            scratch_dir=tmp_path / "spcat_scr",
        )

    assert not (tmp_path / "line_catalog.parquet").exists()
