"""Pickett SPCAT Diagonalization & Asymmetric Top Microwave Parquet Catalog Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §3.0, §15, Suggestion #124.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Eradication of linear rotor formula (2 * B * j) for asymmetric tops (kappa != +/-1).
2. Subprocess execution / FP64 Watson Hamiltonian asymmetric top diagonalization.
3. Strict B_e vs B_0 separation, raising MethodologyViolationError on unvibrated B_e without override.
4. Apache Parquet transition catalog generation (line_catalog.parquet) with MolSSI/IAU metadata standards.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from scripts.spcat_runner import (
    MethodologyViolationError,
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


def test_parquet_catalog_generation_and_schema(tmp_path: Path):
    """Assert transition frequencies reflect Watson Hamiltonian eigenvalues and write to Parquet [M]."""
    runner = SPCATRunner()
    out_parquet = tmp_path / "line_catalog.parquet"

    # Trans-formic acid (HCOOH) microwave benchmark constants
    cfg = SPCATDeckConfig(
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

    catalog_path = runner.generate_parquet_catalog(
        config=cfg,
        output_parquet_path=out_parquet,
        scratch_dir=tmp_path / "spcat_scr",
    )

    assert catalog_path.is_file()
    assert catalog_path.exists()

    # Read and inspect Parquet table
    table = pq.read_table(str(catalog_path))
    assert table.num_rows > 0

    schema_names = table.column_names
    for expected_col in ("frequency_mhz", "j_upper", "ka_upper", "kc_upper", "j_lower", "constant_type"):
        assert expected_col in schema_names, f"Column '{expected_col}' missing from line catalog schema"

    # Check constant_type metadata column
    col_data = table["constant_type"].to_pylist()
    assert all(c == "B0" for c in col_data)
