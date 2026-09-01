"""Zero-Mock Production Test Suite for Dark Branch & Transition Filter (Stage 5.0 / 6.0 / 7.0).

Strictly adheres to:
- CoChem Method Matrix v4 (Sections 1.1, 1.2, 2.1, 3.0, 8C, 13.5, 13.6)
- Zero-Mock Anti-Spoofing Protocol: Real filesystem I/O, real physical arrays, real Pickett .cat files,
  real PyArrow Parquet files, real tmp_path directories.
- Mendeleev Mandate: Dynamic mass and element properties via mendeleev library.
- Complete, functional Python 3.10+ code with zero mocks, zero stubs, zero pass blocks.
"""

from __future__ import annotations

import math
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from mendeleev import element  # type: ignore[import-untyped]

from formatters.cochem_dark_branch_filter import (
    BranchType,
    DarkBranchFilter,
    DarkBranchFilterConfig,
    DipoleType,
    FilterRejectionReason,
    FilterStatistics,
    TransitionRecord,
    calculate_boltzmann_population,
    calculate_isotopic_molecular_weight,
    classify_asymmetric_dipole_type,
    classify_rotational_branch,
    filter_dark_branches,
    filter_parquet_catalog,
    filter_spcat_catalog,
    format_pickett_quantum_numbers,
    generate_dark_branch_report,
    main,
    parse_pickett_quantum_numbers,
)


# =============================================================================
# 1. Mendeleev Mandate & Physical Constants Tests
# =============================================================================

def test_mendeleev_integration_dynamic_weights() -> None:
    """Verifies dynamic atomic mass retrieval without hardcoded constants."""
    h_mass = float(element("H").atomic_weight)
    o_mass = float(element("O").atomic_weight)
    c_mass = float(element("C").atomic_weight)

    # Water H2O
    h2o_calc = calculate_isotopic_molecular_weight("H2O")
    expected_h2o = 2.0 * h_mass + o_mass
    assert math.isclose(h2o_calc, expected_h2o, rel_tol=1e-5)

    # Methane CH4
    ch4_calc = calculate_isotopic_molecular_weight("CH4")
    expected_ch4 = c_mass + 4.0 * h_mass
    assert math.isclose(ch4_calc, expected_ch4, rel_tol=1e-5)

    # Noble gas Ne and Ar (Method Matrix §2.1 rare-gas complexes)
    ne_mass = float(element("Ne").atomic_weight)
    assert math.isclose(calculate_isotopic_molecular_weight("Ne"), ne_mass, rel_tol=1e-5)
    ar_mass = float(element("Ar").atomic_weight)
    assert math.isclose(calculate_isotopic_molecular_weight("Ar"), ar_mass, rel_tol=1e-5)


# =============================================================================
# 2. Quantum Number Parsing & Branch Classification Tests
# =============================================================================

def test_quantum_number_parsing_and_formatting() -> None:
    """Tests parsing and fixed-width formatting of Pickett quantum numbers."""
    # Standard 2I2 fixed width
    j, ka, kc = parse_pickett_quantum_numbers(" 1 0 1")
    assert (j, ka, kc) == (1, 0, 1)

    j, ka, kc = parse_pickett_quantum_numbers("12 4 8")
    assert (j, ka, kc) == (12, 4, 8)

    # Whitespace token string
    j, ka, kc = parse_pickett_quantum_numbers("3  2  1")
    assert (j, ka, kc) == (3, 2, 1)

    # Two tokens
    j, ka, kc = parse_pickett_quantum_numbers("4 2")
    assert (j, ka, kc) == (4, 2, 0)

    # Empty string
    assert parse_pickett_quantum_numbers("") == (0, 0, 0)

    # Fixed width formatting
    fmt_str = format_pickett_quantum_numbers(1, 0, 1, width=12)
    assert fmt_str.startswith(" 1 0 1")
    assert len(fmt_str) == 12


def test_rotational_branch_classification() -> None:
    """Tests Delta J = J' - J'' branch classification (P, Q, R, O, S)."""
    assert classify_rotational_branch(0, 1) == BranchType.P_BRANCH  # Delta J = -1
    assert classify_rotational_branch(1, 1) == BranchType.Q_BRANCH  # Delta J =  0
    assert classify_rotational_branch(1, 0) == BranchType.R_BRANCH  # Delta J = +1
    assert classify_rotational_branch(0, 2) == BranchType.O_BRANCH  # Delta J = -2
    assert classify_rotational_branch(2, 0) == BranchType.S_BRANCH  # Delta J = +2
    assert classify_rotational_branch(5, 1) == BranchType.UNKNOWN


def test_asymmetric_dipole_selection_rules() -> None:
    """Tests a-, b-, c-type dipole selection rules for asymmetric rotors."""
    # a-type: Delta Ka even, Delta Kc odd
    # 1_01 <- 0_00: Delta J=1, Delta Ka=0 (even), Delta Kc=1 (odd)
    assert classify_asymmetric_dipole_type(1, 0, 1, 0, 0, 0) == DipoleType.A_TYPE
    # 2_11 <- 1_10: Delta J=1, Delta Ka=0 (even), Delta Kc=1 (odd)
    assert classify_asymmetric_dipole_type(2, 1, 1, 1, 1, 0) == DipoleType.A_TYPE

    # b-type: Delta Ka odd, Delta Kc odd
    # 1_11 <- 0_00: Delta J=1, Delta Ka=1 (odd), Delta Kc=1 (odd)
    assert classify_asymmetric_dipole_type(1, 1, 1, 0, 0, 0) == DipoleType.B_TYPE

    # c-type: Delta Ka odd, Delta Kc even
    # 1_10 <- 0_00: Delta J=1, Delta Ka=1 (odd), Delta Kc=0 (even)
    assert classify_asymmetric_dipole_type(1, 1, 0, 0, 0, 0) == DipoleType.C_TYPE

    # Forbidden: Delta Ka even, Delta Kc even (e.g. 1_00 <- 0_00)
    assert classify_asymmetric_dipole_type(1, 0, 0, 0, 0, 0) == DipoleType.FORBIDDEN
    # Forbidden: Delta J = 0 for J=0 -> J=0
    assert classify_asymmetric_dipole_type(0, 0, 0, 0, 0, 0) == DipoleType.FORBIDDEN


# =============================================================================
# 3. Physical Boltzmann Population Tests
# =============================================================================

def test_boltzmann_population_calculation() -> None:
    """Tests state population calculation at supersonic jet (2 K) and thermal (298 K) regimes."""
    # Ground state (E = 0 cm^-1)
    pop_ground = calculate_boltzmann_population(0.0, 2.0, degeneracy=1)
    assert math.isclose(pop_ground, 1.0, rel_tol=1e-6)

    # Excited state at 2.0 K (E = 5 cm^-1)
    pop_5cm = calculate_boltzmann_population(5.0, 2.0, degeneracy=1)
    assert 0.0 < pop_5cm < 1.0

    # Very high state frozen out at 2.0 K (E = 50 cm^-1)
    pop_50cm = calculate_boltzmann_population(50.0, 2.0, degeneracy=1)
    assert pop_50cm < 1e-10

    # Zero / negative temperature safety
    assert calculate_boltzmann_population(0.0, 0.0) == 1.0
    assert calculate_boltzmann_population(10.0, 0.0) == 0.0


# =============================================================================
# 4. Transition Evaluation & Filtering Engine Tests
# =============================================================================

def test_evaluate_transition_bright_and_dark() -> None:
    """Tests comprehensive criteria evaluation for single spectral records."""
    config = DarkBranchFilterConfig(
        min_frequency_mhz=2000.0,
        max_frequency_mhz=22000.0,
        min_log_intensity=-10.0,
        max_uncertainty_mhz=1.0,
        rotational_temperature_k=2.0,
        dipole_components=(1.5, 0.0, 0.0),  # Active mu_a, zero mu_b/mu_c
        min_dipole_debye=0.01,
    )
    filter_engine = DarkBranchFilter(config=config)

    # 1. Valid Bright a-type transition (1_01 <- 0_00 at 12000 MHz)
    bright_rec = TransitionRecord(
        frequency_mhz=12000.0,
        uncertainty_mhz=0.005,
        log_intensity=-4.5,
        degrees_of_freedom=2,
        lower_state_energy_cm1=0.0,
        upper_state_degeneracy=3,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 0 1",
        qn_lower=" 0 0 0",
    )
    res_bright = filter_engine.evaluate_transition(bright_rec)
    assert res_bright.is_bright is True
    assert res_bright.rejection_reason == FilterRejectionReason.PASSED
    assert res_bright.branch_type == BranchType.R_BRANCH
    assert res_bright.dipole_type == DipoleType.A_TYPE

    # 2. Dark: Out of band low (< 2 GHz)
    low_rec = TransitionRecord(
        frequency_mhz=1500.0,
        uncertainty_mhz=0.005,
        log_intensity=-4.5,
        degrees_of_freedom=2,
        lower_state_energy_cm1=0.0,
        upper_state_degeneracy=3,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 0 1",
        qn_lower=" 0 0 0",
    )
    res_low = filter_engine.evaluate_transition(low_rec)
    assert res_low.is_bright is False
    assert res_low.rejection_reason == FilterRejectionReason.OUT_OF_BAND

    # 3. Dark: Out of band high (> 22 GHz)
    high_rec = TransitionRecord(
        frequency_mhz=25000.0,
        uncertainty_mhz=0.005,
        log_intensity=-4.5,
        degrees_of_freedom=2,
        lower_state_energy_cm1=0.0,
        upper_state_degeneracy=3,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 0 1",
        qn_lower=" 0 0 0",
    )
    res_high = filter_engine.evaluate_transition(high_rec)
    assert res_high.is_bright is False
    assert res_high.rejection_reason == FilterRejectionReason.OUT_OF_BAND

    # 4. Dark: High uncertainty (> 1.0 MHz)
    err_rec = TransitionRecord(
        frequency_mhz=10000.0,
        uncertainty_mhz=2.5,
        log_intensity=-4.5,
        degrees_of_freedom=2,
        lower_state_energy_cm1=0.0,
        upper_state_degeneracy=3,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 0 1",
        qn_lower=" 0 0 0",
    )
    res_err = filter_engine.evaluate_transition(err_rec)
    assert res_err.is_bright is False
    assert res_err.rejection_reason == FilterRejectionReason.HIGH_UNCERTAINTY

    # 5. Dark: Low intensity (log10(I) < -10.0)
    int_rec = TransitionRecord(
        frequency_mhz=10000.0,
        uncertainty_mhz=0.01,
        log_intensity=-12.0,
        degrees_of_freedom=2,
        lower_state_energy_cm1=0.0,
        upper_state_degeneracy=3,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 0 1",
        qn_lower=" 0 0 0",
    )
    res_int = filter_engine.evaluate_transition(int_rec)
    assert res_int.is_bright is False
    assert res_int.rejection_reason == FilterRejectionReason.INTENSITY_BELOW_CUTOFF

    # 6. Dark: Inactive dipole type (b-type transition when mu_b = 0.0)
    b_rec = TransitionRecord(
        frequency_mhz=10000.0,
        uncertainty_mhz=0.01,
        log_intensity=-4.0,
        degrees_of_freedom=2,
        lower_state_energy_cm1=0.0,
        upper_state_degeneracy=3,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 1 1",  # b-type
        qn_lower=" 0 0 0",
    )
    res_b = filter_engine.evaluate_transition(b_rec)
    assert res_b.is_bright is False
    assert res_b.rejection_reason == FilterRejectionReason.ZERO_DIPOLE_COMPONENT

    # 7. Dark: Pauli forbidden (degeneracy <= 0)
    deg_rec = TransitionRecord(
        frequency_mhz=10000.0,
        uncertainty_mhz=0.01,
        log_intensity=-4.0,
        degrees_of_freedom=2,
        lower_state_energy_cm1=0.0,
        upper_state_degeneracy=0,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 0 1",
        qn_lower=" 0 0 0",
    )
    res_deg = filter_engine.evaluate_transition(deg_rec)
    assert res_deg.is_bright is False
    assert res_deg.rejection_reason == FilterRejectionReason.ZERO_NUCLEAR_SPIN_WEIGHT

    # 8. Dark: Frozen out lower state energy at 2.0 K (e.g. 50 cm^-1)
    elo_rec = TransitionRecord(
        frequency_mhz=10000.0,
        uncertainty_mhz=0.01,
        log_intensity=-4.0,
        degrees_of_freedom=2,
        lower_state_energy_cm1=50.0,
        upper_state_degeneracy=3,
        species_tag=1,
        qn_format=1404,
        qn_upper=" 1 0 1",
        qn_lower=" 0 0 0",
    )
    res_elo = filter_engine.evaluate_transition(elo_rec)
    assert res_elo.is_bright is False
    assert res_elo.rejection_reason == FilterRejectionReason.FROZEN_OUT_LOWER_STATE


# =============================================================================
# 5. Pickett .cat File I/O and Streaming Filtering Tests
# =============================================================================

def test_spcat_cat_file_filtering_real_io(tmp_path: pathlib.Path) -> None:
    """Tests physical Pickett .cat file parsing, dark branch filtering, and writing."""
    input_cat = tmp_path / "synthetic_spectrum.cat"
    output_cat = tmp_path / "filtered_spectrum.cat"

    # Write authentic Pickett SPCAT fixed width lines
    # Col widths: [F13.4, 2F8.4, I2, F10.4, I3, I7, I4, 6I2, 6I2]
    cat_content = (
        "  12045.2100  0.0020 -4.3210 2    0.0000  3      11404 1 0 1 0 0 0\n"  # Bright R-branch (a-type)
        "   1500.0000  0.0020 -4.3210 2    0.0000  3      11404 1 0 1 0 0 0\n"  # Dark: < 2000 MHz
        "  25000.0000  0.0020 -4.3210 2    0.0000  3      11404 1 0 1 0 0 0\n"  # Dark: > 22000 MHz
        "  18230.1500  0.0050 -5.1100 2    1.2000  5      11404 2 0 2 1 0 1\n"  # Bright R-branch (a-type)
        "  14500.0000  5.0000 -4.0000 2    0.0000  3      11404 1 0 1 0 0 0\n"  # Dark: high uncertainty
        "  16000.0000  0.0010-15.0000 2    0.0000  3      11404 1 0 1 0 0 0\n"  # Dark: log int < -10
        "  19000.0000  0.0010 -4.0000 2   85.0000  3      11404 1 0 1 0 0 0\n"  # Dark: frozen out E=85 cm^-1
    )
    input_cat.write_text(cat_content, encoding="utf-8")

    config = DarkBranchFilterConfig(
        min_frequency_mhz=2000.0,
        max_frequency_mhz=22000.0,
        min_log_intensity=-10.0,
        max_uncertainty_mhz=1.0,
        rotational_temperature_k=2.0,
    )
    bright_records, stats = filter_spcat_catalog(input_cat, output_cat, config=config)

    assert stats.total_evaluated == 7
    assert stats.bright_count == 2
    assert stats.dark_count == 5
    assert len(bright_records) == 2

    # Verify physical output file exists and is readable
    assert output_cat.exists()
    out_lines = output_cat.read_text(encoding="utf-8").strip().splitlines()
    assert len(out_lines) == 2
    assert "12045.2100" in out_lines[0]
    assert "18230.1500" in out_lines[1]


def test_fortran_overflow_guardrails() -> None:
    """Tests robust handling of Fortran overflow asterisks without crash."""
    config = DarkBranchFilterConfig()
    engine = DarkBranchFilter(config=config)

    overflow_line = "  **********  0.0020 -4.3210 2    0.0000  3      11404 1 0 1 0 0 0"
    rec = engine._parse_spcat_line_to_record(overflow_line, 1)
    assert rec is not None
    assert rec.is_bright is False
    assert rec.rejection_reason == FilterRejectionReason.FORTRAN_OVERFLOW


# =============================================================================
# 6. PyArrow Parquet Out-Of-Core Streaming Filter Tests
# =============================================================================

def test_pyarrow_table_and_parquet_streaming_filtering(tmp_path: pathlib.Path) -> None:
    """Tests PyArrow Table and streaming Parquet file filtering."""
    in_parquet = tmp_path / "spectral_catalog.parquet"
    out_parquet = tmp_path / "filtered_catalog.parquet"

    # Create PyArrow Table with test rows
    frequencies = [12000.0, 1500.0, 18000.0, 24000.0, 10000.0]
    uncertainties = [0.002, 0.002, 0.005, 0.002, 2.500]  # row 5 has high unc
    intensities = [-4.0, -4.0, -5.0, -4.0, -4.0]
    energies = [0.0, 0.0, 1.0, 0.0, 0.0]
    qn_u = [" 1 0 1", " 1 0 1", " 2 0 2", " 1 0 1", " 1 0 1"]
    qn_l = [" 0 0 0", " 0 0 0", " 1 0 1", " 0 0 0", " 0 0 0"]

    table = pa.Table.from_pydict(
        {
            "frequency_mhz": frequencies,
            "uncertainty_mhz": uncertainties,
            "log_intensity": intensities,
            "degrees_of_freedom": [2] * 5,
            "lower_state_energy_cm1": energies,
            "upper_state_degeneracy": [3] * 5,
            "species_tag": [1] * 5,
            "qn_format": [1404] * 5,
            "qn_upper": qn_u,
            "qn_lower": qn_l,
            "temperature_k": [2.0] * 5,
            "provenance_hash": ["sha256_mock_test"] * 5,
        }
    )

    pq.write_table(table, str(in_parquet))
    assert in_parquet.exists()

    config = DarkBranchFilterConfig(
        min_frequency_mhz=2000.0,
        max_frequency_mhz=22000.0,
        min_log_intensity=-10.0,
        max_uncertainty_mhz=1.0,
    )
    stats = filter_parquet_catalog(in_parquet, out_parquet, config=config, chunk_size=2)

    assert stats.total_evaluated == 5
    assert stats.bright_count == 2  # Row 0 (12000) and Row 2 (18000)
    assert stats.dark_count == 3

    assert out_parquet.exists()
    filtered_table = pq.read_table(str(out_parquet))
    assert filtered_table.num_rows == 2
    f_df = filtered_table.to_pandas()
    assert list(f_df["frequency_mhz"]) == [12000.0, 18000.0]


# =============================================================================
# 7. Pandas DataFrame & Conformer Ensemble Tests
# =============================================================================

def test_dataframe_filtering() -> None:
    """Tests Pandas DataFrame filtering helper."""
    df = pd.DataFrame([
        {"frequency_mhz": 12000.0, "uncertainty_mhz": 0.01, "log_intensity": -4.0, "qn_upper": " 1 0 1", "qn_lower": " 0 0 0"},
        {"frequency_mhz": 1500.0, "uncertainty_mhz": 0.01, "log_intensity": -4.0, "qn_upper": " 1 0 1", "qn_lower": " 0 0 0"},
    ])
    engine = DarkBranchFilter()
    filtered_df, stats = engine.filter_dataframe(df)

    assert len(filtered_df) == 1
    assert stats.total_evaluated == 2
    assert stats.bright_count == 1
    assert filtered_df.iloc[0]["frequency_mhz"] == 12000.0


def test_conformer_ensemble_filtering() -> None:
    """Tests conformer ensemble dark branch filtering (energy, population, dipole)."""
    conformers = [
        {"name": "conf_01", "relative_energy_kcal_mol": 0.0, "mu_a": 1.2, "mu_b": 0.4, "mu_c": 0.0},  # Bright
        {"name": "conf_02", "relative_energy_kcal_mol": 0.8, "mu_a": 0.9, "mu_b": 0.0, "mu_c": 0.3},  # Bright
        {"name": "conf_03", "relative_energy_kcal_mol": 15.0, "mu_a": 1.0, "mu_b": 0.0, "mu_c": 0.0},  # Dark: High energy > 12 kcal/mol
        {"name": "conf_04", "relative_energy_kcal_mol": 0.2, "mu_a": 0.0, "mu_b": 0.0, "mu_c": 0.0},  # Dark: Non-polar (dipole = 0)
    ]
    engine = DarkBranchFilter()
    bright_confs, summary = engine.filter_conformer_ensemble(conformers)

    assert summary["total_conformers"] == 4
    assert summary["bright_conformers_count"] == 2
    assert summary["dark_conformers_count"] == 2
    assert len(bright_confs) == 2
    assert bright_confs[0]["name"] == "conf_01"
    assert bright_confs[1]["name"] == "conf_02"


# =============================================================================
# 8. Report Generation (GFM & LaTeX) Tests
# =============================================================================

def test_report_generation(tmp_path: pathlib.Path) -> None:
    """Tests GFM Markdown and LaTeX table report synthesis."""
    stats = FilterStatistics(
        total_evaluated=100,
        bright_count=60,
        dark_count=40,
        rejection_counts={"OUT_OF_BAND": 25, "INTENSITY_BELOW_CUTOFF": 15},
        branch_counts={"R": 40, "Q": 20},
        dipole_counts={"a-type": 45, "b-type": 15},
        min_observed_frequency_mhz=2500.0,
        max_observed_frequency_mhz=21500.0,
        min_observed_log_intensity=-8.5,
        max_observed_log_intensity=-3.2,
        min_observed_energy_cm1=0.0,
        max_observed_energy_cm1=4.8,
        elapsed_seconds=0.015,
    )

    gfm_path = tmp_path / "filter_report.md"
    latex_path = tmp_path / "filter_report.tex"

    reports = generate_dark_branch_report(
        stats,
        output_markdown_path=gfm_path,
        output_latex_path=latex_path,
    )

    assert "### Dark Branch Filter Execution Summary" in reports["gfm"]
    assert "| `OUT_OF_BAND` | `25` | `25.00%` |" in reports["gfm"]
    assert gfm_path.exists()
    assert latex_path.exists()

    latex_content = latex_path.read_text(encoding="utf-8")
    assert r"\begin{table}" in latex_content
    assert r"Total Evaluated Lines & 100" in latex_content


# =============================================================================
# 9. CLI Execution Tests
# =============================================================================

def test_cli_execution_with_cat(tmp_path: pathlib.Path) -> None:
    """Tests CLI argument parsing and execution with real files."""
    in_cat = tmp_path / "test_cli.cat"
    out_cat = tmp_path / "test_cli_out.cat"
    rep_md = tmp_path / "test_cli_rep.md"

    in_cat.write_text(
        "  12000.0000  0.0020 -4.0000 2    0.0000  3      11404 1 0 1 0 0 0\n"
        "   1000.0000  0.0020 -4.0000 2    0.0000  3      11404 1 0 1 0 0 0\n",
        encoding="utf-8",
    )

    args = [
        "--input-cat", str(in_cat),
        "--output-cat", str(out_cat),
        "--report-gfm", str(rep_md),
        "--min-freq", "2000",
        "--max-freq", "22000",
    ]
    exit_code = main(args)
    assert exit_code == 0
    assert out_cat.exists()
    assert rep_md.exists()
