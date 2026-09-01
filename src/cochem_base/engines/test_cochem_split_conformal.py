#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Zero-Mock Unit and Integration Test Suite for CoChem Split-Conformal Prediction Engine.

Governed strictly by Method Matrix v4 (§17.5, §17.1-17.4, §12.5, §21, §3.1, §4),
the Zero-Mock Anti-Spoofing Protocol, FAIR Data Principles, and the Air-Gap Compliance Directive.

Validates the SplitConformalEngine, ConformalStratifier, authentic 22-system benchmark,
exact finite-sample quantile calculation, Leave-One-Out (LOO) empirical coverage guarantees,
Product A/B/C prediction intervals, and CLI functionality.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# Ensure repository root is on sys.path
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from engines.cochem_split_conformal import (  # noqa: E402
    CalibrationSample,
    ConformalStratifier,
    InsufficientSampleSizeError,
    MolecularRigidityClass,
    ObservableType,
    ProductClass,
    ProvenanceTag,
    SplitConformalEngine,
    build_authentic_benchmark_dataset,
    calculate_split_conformal_window,
    main,
)

# =============================================================================
# 1. AUTHENTIC BENCHMARK DATASET INTEGRITY TESTS (§17, §17.5)
# =============================================================================


def test_authentic_benchmark_dataset_integrity() -> None:
    """Verifies that the authentic benchmark dataset contains exactly 22 systems."""
    samples = build_authentic_benchmark_dataset()
    assert len(samples) == 22, f"Expected 22 benchmark systems, got {len(samples)}"

    # Check 6 diagnostic systems are present
    system_ids = {s.system_id for s in samples}
    assert "sys1_ar_ketene" in system_ids
    assert "sys2_ar_oxazole" in system_ids
    assert "sys3_h2co_hcl" in system_ids
    assert "sys4_water_dimer" in system_ids
    assert "sys5_nh3_hcooh" in system_ids
    assert "sys6_c6h6_hcn" in system_ids

    # Check 16-complex literature benchmark systems are present
    assert "bench1_oc_hcl" in system_ids
    assert "bench6_hf_dimer" in system_ids
    assert "bench11_ar_h2o" in system_ids
    assert "bench16_c2h4_hcl" in system_ids

    # Check all samples have positive physical constants and valid provenance
    for s in samples:
        assert s.calculated_val > 0.0, f"System {s.system_id} calculated value must be positive"
        assert s.experimental_val > 0.0, f"System {s.system_id} experimental value must be positive"
        assert s.provenance in {ProvenanceTag.MEASURED, ProvenanceTag.DERIVED}
        assert s.relative_residual >= 0.0


def test_benchmark_strata_distribution() -> None:
    """Verifies that the benchmark dataset contains exactly two strata (§17.5)."""
    samples = build_authentic_benchmark_dataset()
    semi_rigid = [s for s in samples if s.rigidity_class == MolecularRigidityClass.SEMI_RIGID]
    floppy = [s for s in samples if s.rigidity_class == MolecularRigidityClass.FLOPPY]

    assert len(semi_rigid) == 11, f"Expected 11 semi-rigid systems, got {len(semi_rigid)}"
    assert len(floppy) == 11, f"Expected 11 floppy systems, got {len(floppy)}"
    assert len(semi_rigid) + len(floppy) == 22


# =============================================================================
# 2. CONFORMAL STRATIFICATION TESTS
# =============================================================================


def test_conformal_stratifier_rare_gas() -> None:
    """Verifies that rare-gas van der Waals complexes are classified as FLOPPY."""
    assert ConformalStratifier.classify_system("Ar-H2O") == MolecularRigidityClass.FLOPPY
    assert ConformalStratifier.classify_system("Ne-benzene", symbols=["Ne", "C", "H"]) == MolecularRigidityClass.FLOPPY
    assert ConformalStratifier.classify_system("H2CCO-Ar") == MolecularRigidityClass.FLOPPY
    assert ConformalStratifier.classify_system("Kr_complex") == MolecularRigidityClass.FLOPPY


def test_conformal_stratifier_prototypes() -> None:
    """Verifies that known large-amplitude prototypes are classified as FLOPPY."""
    assert ConformalStratifier.classify_system("water_dimer") == MolecularRigidityClass.FLOPPY
    assert ConformalStratifier.classify_system("(HF)2") == MolecularRigidityClass.FLOPPY
    assert ConformalStratifier.classify_system("(HCl)2") == MolecularRigidityClass.FLOPPY
    assert ConformalStratifier.classify_system("CH4-H2O") == MolecularRigidityClass.FLOPPY


def test_conformal_stratifier_semi_rigid() -> None:
    """Verifies that directional H-bonds and rigid dimers are classified as SEMI_RIGID."""
    assert ConformalStratifier.classify_system("OC-HCl") == MolecularRigidityClass.SEMI_RIGID
    assert ConformalStratifier.classify_system("HCN-HF") == MolecularRigidityClass.SEMI_RIGID
    assert ConformalStratifier.classify_system("CO2-H2O") == MolecularRigidityClass.SEMI_RIGID
    assert ConformalStratifier.classify_system("H2O-HF") == MolecularRigidityClass.SEMI_RIGID


def test_conformal_stratifier_physical_thresholds() -> None:
    """Verifies physical threshold gating for soft modes, force constants, and barriers."""
    # Soft mode < 80 cm^-1 -> Floppy
    assert ConformalStratifier.classify_system("Custom_Dimer", softest_mode_cm1=45.0) == MolecularRigidityClass.FLOPPY
    # Soft mode >= 80 cm^-1 and rigid -> Semi-rigid
    assert ConformalStratifier.classify_system("Custom_Dimer", softest_mode_cm1=120.0) == MolecularRigidityClass.SEMI_RIGID

    # Low force constant k_sigma < 0.05 mdyn/A -> Floppy
    assert ConformalStratifier.classify_system("Dimer_B", force_constant_mdyn_ang=0.02) == MolecularRigidityClass.FLOPPY
    # Force constant >= 0.05 mdyn/A -> Semi-rigid
    assert ConformalStratifier.classify_system("Dimer_B", force_constant_mdyn_ang=0.08) == MolecularRigidityClass.SEMI_RIGID


# =============================================================================
# 3. MATHEMATICAL QUANTILE & ORDER STATISTIC TESTS (§17.5)
# =============================================================================


def test_compute_conformal_quantile_exact_formula() -> None:
    """Verifies the exact order statistic formula k = ceil((1 - alpha) * (n + 1))."""
    scores = [0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009, 0.010]
    # n = 10, alpha = 0.10: k = ceil(0.90 * 11) = ceil(9.9) = 10
    q_hat, k = SplitConformalEngine.compute_conformal_quantile(scores, alpha=0.10)
    assert k == 10
    assert q_hat == 0.010

    # 22-system benchmark at 90% confidence
    # n = 22, alpha = 0.10: k = ceil(0.90 * 23) = ceil(20.7) = 21 (§17.5 point 3)
    synth_scores = [i * 0.001 for i in range(1, 23)]  # 1 to 22
    q_hat_22, k_22 = SplitConformalEngine.compute_conformal_quantile(synth_scores, alpha=0.10)
    assert k_22 == 21
    assert q_hat_22 == synth_scores[20]  # 21st order statistic (index 20)


def test_compute_conformal_quantile_invalid_args() -> None:
    """Verifies error handling for empty scores or invalid alpha values."""
    with pytest.raises(InsufficientSampleSizeError):
        SplitConformalEngine.compute_conformal_quantile([], alpha=0.10)

    with pytest.raises(ValueError, match="Alpha must be in"):
        SplitConformalEngine.compute_conformal_quantile([0.01, 0.02], alpha=1.5)

    with pytest.raises(ValueError, match="Alpha must be in"):
        SplitConformalEngine.compute_conformal_quantile([0.01, 0.02], alpha=-0.1)


# =============================================================================
# 4. SPLIT CONFORMAL CALIBRATION TESTS (§17.5)
# =============================================================================


def test_split_conformal_engine_calibration() -> None:
    """Verifies calibration across semi-rigid, floppy, and combined strata."""
    engine = SplitConformalEngine()
    summary = engine.calibrate_all(alpha=0.10)

    assert summary.benchmark_system_count == 22
    assert summary.semi_rigid_summary.sample_count_n == 11
    assert summary.floppy_summary.sample_count_n == 11
    assert summary.combined_summary.sample_count_n == 22

    # Semi-rigid calibrated quantile should be in the 0.3 - 0.5% band (§3.1, §17.5)
    sr_q90_pct = summary.semi_rigid_summary.conformal_half_width_pct
    assert 0.30 <= sr_q90_pct <= 0.60, f"Semi-rigid 90% half-width {sr_q90_pct:.3f}% outside expected band"

    # Floppy calibrated quantile should be in the 1.0 - 2.0% band (§3.1, §17.5)
    fl_q90_pct = summary.floppy_summary.conformal_half_width_pct
    assert 1.00 <= fl_q90_pct <= 2.20, f"Floppy 90% half-width {fl_q90_pct:.3f}% outside expected band"


def test_exclusion_rule_enforcement() -> None:
    """Verifies that systems with theoretical priors are filtered out (§17 exclusion rule)."""
    samples = build_authentic_benchmark_dataset()
    # Add a contaminated test sample with theoretical prior
    tainted_sample = CalibrationSample(
        system_id="tainted_sys",
        system_name="Theoretical Prior System",
        formula="XYZ",
        rigidity_class=MolecularRigidityClass.SEMI_RIGID,
        observable=ObservableType.ROTATIONAL_A0,
        calculated_val=42000.0,
        experimental_val=42000.0,
        has_theoretical_prior=True,  # Tainted!
    )
    samples.append(tainted_sample)

    engine = SplitConformalEngine(calibration_samples=samples)
    assert engine.total_sample_count == 22  # Tainted sample excluded!
    assert "tainted_sys" not in [s.system_id for s in engine.get_samples_by_stratum(MolecularRigidityClass.COMBINED)]


# =============================================================================
# 5. PREDICTION INTERVAL EMISSION & PRODUCT CLASSES (§3, §17.5)
# =============================================================================


def test_predict_interval_product_a_semi_rigid() -> None:
    """Verifies Product A prediction interval for semi-rigid systems."""
    engine = SplitConformalEngine()
    interval = engine.predict_interval(
        centre_val=12000.0,
        rigidity_class=MolecularRigidityClass.SEMI_RIGID,
        product_class=ProductClass.PRODUCT_A,
        alpha=0.10,
    )

    assert interval.centre_val == 12000.0
    assert interval.lower_bound < interval.centre_val < interval.upper_bound
    assert interval.half_width_val == pytest.approx(interval.centre_val * interval.conformal_quantile_qhat, rel=1e-5)
    # At 12 GHz and ~0.48%, half-width should be ~57.6 MHz
    assert 40.0 <= interval.half_width_val <= 70.0
    assert interval.provenance == ProvenanceTag.DERIVED
    assert interval.is_coverage_guaranteed is True


def test_predict_interval_product_a_floppy() -> None:
    """Verifies Product A prediction interval for floppy systems."""
    engine = SplitConformalEngine()
    interval = engine.predict_interval(
        centre_val=12000.0,
        rigidity_class=MolecularRigidityClass.FLOPPY,
        product_class=ProductClass.PRODUCT_A,
        alpha=0.10,
    )

    assert interval.centre_val == 12000.0
    # At 12 GHz and ~1.75%, half-width should be ~210 MHz
    assert 150.0 <= interval.half_width_val <= 260.0


def test_predict_interval_product_b() -> None:
    """Verifies Product B (measured parent) search window collapses to 0.05%."""
    engine = SplitConformalEngine()
    interval = engine.predict_interval(
        centre_val=12000.0,
        product_class=ProductClass.PRODUCT_B,
    )

    assert interval.product_class == ProductClass.PRODUCT_B
    assert interval.conformal_quantile_qhat == 0.0005  # 0.05%
    assert interval.half_width_val == pytest.approx(6.0, rel=1e-5)  # 0.05% of 12 GHz = 6.0 MHz
    assert interval.half_width_pct == 0.05
    assert interval.provenance == ProvenanceTag.MEASURED


# =============================================================================
# 6. LEAVE-ONE-OUT (LOO) EMPIRICAL COVERAGE VALIDATION
# =============================================================================


def test_leave_one_out_coverage_validation() -> None:
    """Verifies that empirical coverage satisfies the finite-sample guarantee (>= 90%)."""
    engine = SplitConformalEngine()
    cv = engine.evaluate_leave_one_out_coverage(alpha=0.10, stratum=MolecularRigidityClass.COMBINED)

    assert cv.total_evaluations == 22
    assert cv.nominal_coverage_rate == 0.90
    assert cv.empirical_coverage_rate >= 0.90, f"Empirical coverage {cv.empirical_coverage_rate * 100:.1f}% below 90%"
    assert cv.passes_validity_gate is True


# =============================================================================
# 7. CONVENIENCE FUNCTIONAL INTERFACE
# =============================================================================


def test_calculate_split_conformal_window_helper() -> None:
    """Verifies calculate_split_conformal_window integration helper."""
    centre, hw_mhz, hw_pct, q_hat = calculate_split_conformal_window(
        centre_freq_mhz=12000.0,
        product_class="A",
        rigidity="semi-rigid",
        confidence_level=0.90,
    )
    assert centre == 12000.0
    assert 40.0 <= hw_mhz <= 70.0
    assert 0.30 <= hw_pct <= 0.60
    assert q_hat == pytest.approx(hw_pct / 100.0, rel=1e-5)

    # Product B helper test
    centre_b, hw_mhz_b, hw_pct_b, q_hat_b = calculate_split_conformal_window(
        centre_freq_mhz=12000.0,
        product_class="B",
    )
    assert centre_b == 12000.0
    assert hw_mhz_b == 6.0
    assert hw_pct_b == 0.05


# =============================================================================
# 8. CLI HARNESS & EXPORT TESTS
# =============================================================================


def test_cli_execution_calibrate_and_predict(tmp_path: pathlib.Path) -> None:
    """Verifies CLI execution with --calibrate, --predict, and --export-json."""
    export_file = tmp_path / "calibration_summary.json"
    exit_code = main([
        "--calibrate",
        "--predict",
        "--freq", "12000.0",
        "--rigidity", "semi-rigid",
        "--product", "A",
        "--verify-coverage",
        "--export-json", str(export_file),
    ])
    assert exit_code == 0
    assert export_file.exists()
    assert export_file.stat().st_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
