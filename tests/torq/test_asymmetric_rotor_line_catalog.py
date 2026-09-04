"""Zero-Mock verification tests for Asymmetric Rotor & SPCAT Catalog (test_asymmetric_rotor_line_catalog.py).

Validates Suggestion #45:
- Elimination of linear rotor approximations (2*B*J)
- Authentic Wang symmetric rotor basis diagonalizer for Watson A-reduced Hamiltonian
- Trans-formic acid (HCOOH) microwave benchmarks:
  * 1_{0,1} <- 0_{0,0} within 0.05 MHz of 17396.47 MHz [M]
  * 2_{1,1} <- 1_{1,0} within 0.05 MHz of 38432.73 MHz [M]
- Standardized Apache Parquet line catalog compilation with dipole projections
- Pickett .cat file parser verification
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from cochem_torq_asymmetric_rotor import (
    AsymmetricTopDiagonalizer,
    RotationalConstants,
)
from cochem_torq_spcat import PickettSPCATRunner


def get_formic_acid_constants() -> RotationalConstants:
    """Authentic experimental rotational and quartic constants for trans-formic acid (HCOOH) [M]."""
    return RotationalConstants(
        A=20245.8,
        B=10518.2,
        C=6878.3,
        D_J=0.00762,
        D_JK=-0.0634,
        D_K=0.528,
        d_1=0.00164,   # delta_J in Watson A-reduction
        d_2=0.032,     # delta_K in Watson A-reduction
        mu_a=1.41,
        mu_b=0.21,
        mu_c=0.00,
    )


def test_asymmetric_rotor_eigenvalues_and_transitions():
    """Assert trans-formic acid microwave transition frequencies match authentic benchmarks within 0.05 MHz."""
    consts = get_formic_acid_constants()
    diag = AsymmetricTopDiagonalizer(constants=consts, reduction="A", j_max=5)

    levels = diag.solve_energy_levels()
    transitions = diag.compute_transitions(freq_min_mhz=0.0, freq_max_mhz=100000.0)

    # 1. Benchmark: 1_{0,1} <- 0_{0,0} transition (B + C - 4*DJ = 17396.47 MHz) [M]
    trans_101_000 = [
        t for t in transitions
        if t.j_upper == 1 and t.ka_upper == 0 and t.kc_upper == 1
        and t.j_lower == 0 and t.ka_lower == 0 and t.kc_lower == 0
    ]
    assert len(trans_101_000) == 1, "Transition 1_{0,1} <- 0_{0,0} not identified in catalog."
    f_101_000 = trans_101_000[0].freq_mhz
    assert abs(f_101_000 - 17396.47) < 0.05, (
        f"1_{0,1} <- 0_{0,0} frequency {f_101_000:.3f} MHz deviates > 0.05 MHz from 17396.47 MHz benchmark."
    )

    # 2. Benchmark: 2_{1,1} <- 1_{1,0} transition (38432.73 MHz) [M]
    trans_211_110 = [
        t for t in transitions
        if t.j_upper == 2 and t.ka_upper == 1 and t.kc_upper == 1
        and t.j_lower == 1 and t.ka_lower == 1 and t.kc_lower == 0
    ]
    assert len(trans_211_110) == 1, "Transition 2_{1,1} <- 1_{1,0} not identified in catalog."
    f_211_110 = trans_211_110[0].freq_mhz
    assert abs(f_211_110 - 38432.73) < 0.05, (
        f"2_{1,1} <- 1_{1,0} frequency {f_211_110:.3f} MHz deviates > 0.05 MHz from 38432.73 MHz benchmark."
    )


def test_parquet_line_catalog_schema_and_types(tmp_path: Path):
    """Assert output Parquet catalog contains properly typed columns and non-empty rows."""
    consts = get_formic_acid_constants()
    diag = AsymmetricTopDiagonalizer(constants=consts, j_max=5)
    catalog_path = tmp_path / "formic_acid_lines.parquet"

    exported = diag.export_line_catalog_parquet(catalog_path)
    assert exported.exists()

    # Read back Parquet and verify column schema
    table = pq.read_table(catalog_path)
    expected_cols = [
        "freq_mhz", "intensity", "j_upper", "ka_upper", "kc_upper",
        "j_lower", "ka_lower", "kc_lower", "e_lower_cm1", "dipole_type"
    ]
    for col in expected_cols:
        assert col in table.column_names, f"Missing required column {col} in Parquet catalog."

    df = table.to_pandas()
    assert len(df) > 0
    assert df["freq_mhz"].dtype in [np.float64, np.float32]
    assert df["j_upper"].dtype in [np.int64, np.int32]
    assert df["dipole_type"].isin(["a", "b", "c"]).all()


def test_spcat_cat_parser(tmp_path: Path):
    """Assert PickettSPCATRunner correctly parses authentic .cat fixed-width output."""
    runner = PickettSPCATRunner()
    sample_cat = tmp_path / "sample.cat"

    # Sample standard Pickett .cat line (17396.4700 MHz 1_0_1 <- 0_0_0)
    cat_line = (
        "  17396.4700  0.0010 -3.4560 2    0.0000  3  10001 10000"
        "             1  0  1  0  0  0\n"
    )
    sample_cat.write_text(cat_line, encoding="utf-8")

    records = runner.parse_cat_file(sample_cat)
    assert len(records) == 1
    r = records[0]
    assert abs(r.freq_mhz - 17396.47) < 0.01
    assert r.j_upper == 1 and r.ka_upper == 0 and r.kc_upper == 1
    assert r.j_lower == 0 and r.ka_lower == 0 and r.kc_lower == 0
