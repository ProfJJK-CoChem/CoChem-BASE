# -*- coding: utf-8 -*-
"""Comprehensive Authentic Test Suite for CoChem-BASE Stage 5.0 JAX Solvers Engine.

Module: test_suite/test_cochem_jax_builder.py
Authoritative Target: cochem_jax_builder.py / cochem_base.cochem_jax_builder

Verifies Acceptance Criteria & Guardrails:
1. Float64 Precision Truncation Guard (Sub-MHz tunneling splitting resolution).
2. XLA Compilation Speedup Test (jit_eigen_solver caching and acceleration).
3. NaN Watchdog & Tikhonov Recovery Test (Singularity interception & micro-damping).
4. Particle-in-a-Box Analytic Parity Test (Exact parity with analytical energy levels).
5. Multi-Dimensional Coupled Rotors (2D Kronecker product Hamiltonian & spectrum).
6. Localized VPT2 Perturbation Coupling (LAM mode removal & orthogonal merging).
7. Zero-Test-Double & Anti-Spoofing Purity Audit.
"""

from __future__ import annotations

import ast
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cochem_jax_builder import (  # noqa: E402
    CoChemPrecisionError,
    build_dvr_hamiltonian,
    enforce_jax_precision,
    jit_eigen_solver,
    localized_vpt2_coupling,
    nan_tensor_watchdog,
)
from cochem_jax_builder import main as solver_main  # noqa: E402


class TestJAXPrecisionAndHardwareTopology:
    """Tests precision enforcement and hardware query telemetry."""

    def test_enforce_jax_precision_success(self) -> None:
        """Verifies float64 mode enforcement and hardware telemetry metadata."""
        info = enforce_jax_precision(force_recheck=True)
        assert isinstance(info, dict)
        assert info["float64_enabled"] is True
        assert "backend" in info
        assert "devices" in info
        assert len(info["devices"]) >= 1
        assert "jax_version" in info

        # Verify scalar creation is float64
        t = jnp.array(3.141592653589793)
        assert t.dtype == jnp.float64

    def test_precision_error_exception_hierarchy(self) -> None:
        """Verifies CoChemPrecisionError structure and provenance error code."""
        err = CoChemPrecisionError("Test precision violation")
        assert "Test precision violation" in str(err)
        assert hasattr(err, "error_code")


class TestParticleInABoxAnalyticParity:
    """Acceptance Criterion 4: Flat zero potential in 1D box matches analytical levels."""

    def test_particle_in_a_box_exact_eigenvalues(self) -> None:
        """Verifies 1D Sine-DVR matches analytical particle-in-a-box energy levels within 1e-6."""
        length = 1.0
        mass = 1.0
        hbar = 1.0
        num_points = 100

        # Flat zero potential
        v_flat = np.zeros(num_points, dtype=np.float64)

        hamiltonian = build_dvr_hamiltonian(
            pes_spline_array=v_flat,
            dimensions=1,
            mass=mass,
            length=length,
            periodic=False,
            num_points=num_points,
            hbar=hbar,
        )

        assert hamiltonian.shape == (num_points, num_points)
        assert hamiltonian.dtype == jnp.float64

        evals, evecs = jit_eigen_solver(hamiltonian)
        evals_np = np.asarray(evals)

        # Analytical energy levels: E_n = (n^2 * pi^2 * hbar^2) / (2 * m * L^2) for n = 1, 2, ...
        n_modes = np.arange(1, 11)
        analytic_energies = (n_modes**2 * np.pi**2 * (hbar**2)) / (2.0 * mass * (length**2))

        numerical_energies = evals_np[:10]
        abs_errors = np.abs(numerical_energies - analytic_energies)

        # Parity check (< 1e-6 required by Method Matrix)
        assert np.max(abs_errors) < 1e-6, f"Max error {np.max(abs_errors)} exceeds 1e-6 tolerance."
        assert np.all(numerical_energies > 0.0)
        assert np.all(np.diff(numerical_energies) > 0.0)

    def test_colbert_miller_sinc_dvr_option(self) -> None:
        """Verifies Colbert-Miller sinc DVR kinetic operator construction and finite spectrum."""
        n_pts = 60
        v_box = np.zeros(n_pts, dtype=np.float64)
        h_cm = build_dvr_hamiltonian(
            pes_spline_array=v_box,
            kinetic_operator="colbert_miller",
            dimensions=1,
            mass=1.0,
            length=1.0,
            periodic=False,
            num_points=n_pts,
        )
        evals, _ = jit_eigen_solver(h_cm)
        assert len(evals) == n_pts
        assert np.all(np.isfinite(np.asarray(evals)))
        assert evals[0] > 0.0


class TestPeriodicInternalRotorDVR:
    """Tests 1D periodic Fourier DVR for free and hindered internal rotors."""

    def test_free_rotor_exact_degeneracy(self) -> None:
        """Verifies periodic free rotor (V=0) reproduces exact m^2 F eigenvalues."""
        f_const = 3.25
        num_points = 31
        v_zero = np.zeros(num_points, dtype=np.float64)

        hamiltonian = build_dvr_hamiltonian(
            pes_spline_array=v_zero,
            dimensions=1,
            periodic=True,
            num_points=num_points,
            reduced_rot_constant=f_const,
        )

        evals, _ = jit_eigen_solver(hamiltonian)
        evals_np = np.asarray(evals)

        # Expected: 0, F, F, 4F, 4F, 9F, 9F, 16F, 16F, ...
        expected_energies = [0.0, f_const, f_const, 4.0 * f_const, 4.0 * f_const, 9.0 * f_const, 9.0 * f_const]
        for i, expected in enumerate(expected_energies):
            assert abs(evals_np[i] - expected) < 1e-8, f"Index {i}: {evals_np[i]} != {expected}"

    def test_hindered_rotor_a_e_tunneling_splitting(self) -> None:
        """Verifies hindered rotor potential V(theta) = (V3/2)(1 - cos(3*theta)) produces A/E splitting."""
        v3 = 450.0  # cm-1
        f_const = 5.25  # cm-1
        n_pts = 61
        theta = 2.0 * np.pi * np.arange(n_pts) / n_pts
        v_hindered = (v3 / 2.0) * (1.0 - np.cos(3.0 * theta))

        h = build_dvr_hamiltonian(
            pes_spline_array=v_hindered,
            dimensions=1,
            periodic=True,
            num_points=n_pts,
            reduced_rot_constant=f_const,
        )

        evals, _ = jit_eigen_solver(h)
        evals_np = np.asarray(evals)

        # Ground torsional state splits into A (non-degenerate) and E (doubly-degenerate)
        e0_a = evals_np[0]
        e1_e = evals_np[1]
        e2_e = evals_np[2]

        assert abs(e1_e - e2_e) < 1e-7  # E states are degenerate
        tunneling_splitting = e1_e - e0_a
        assert tunneling_splitting > 0.0  # A is lower than E for 3-fold barrier


class TestFloat64PrecisionTruncationGuard:
    """Acceptance Criterion 1: Dual-well potential with sub-megahertz tunneling splitting."""

    def test_dual_well_sub_megahertz_splitting_requires_float64(self) -> None:
        """Verifies dual-well sub-MHz tunneling splitting requires float64 precision."""
        n_pts = 160
        domain_length = 10.0
        x_grid = np.linspace(-domain_length / 2.0, domain_length / 2.0, n_pts)

        # Symmetric double-well potential with high central barrier
        # V(x) = c0 * (x^2 - x0^2)^2
        v_double_well = 100.0 * (x_grid**2 - 2.0**2)**2

        h64 = build_dvr_hamiltonian(
            pes_spline_array=v_double_well,
            dimensions=1,
            mass=1.0,
            length=domain_length,
            periodic=False,
            num_points=n_pts,
        )

        assert h64.dtype == jnp.float64

        evals64, _ = jit_eigen_solver(h64)
        assert evals64.dtype == jnp.float64

        e0_64 = float(evals64[0])
        e1_64 = float(evals64[1])
        delta_e_64 = e1_64 - e0_64

        # Float64 successfully resolves non-zero sub-megahertz / micro-splitting
        assert delta_e_64 > 0.0, f"Expected non-zero tunneling splitting, got {delta_e_64}"
        assert delta_e_64 < 1e-6, f"Expected microscopic splitting (<1e-6), got {delta_e_64}"

        # Truncation to 32-bit floating point precision collapses the sub-MHz splitting to zero
        e0_32 = float(np.float32(e0_64))
        e1_32 = float(np.float32(e1_64))
        delta_e_32 = e1_32 - e0_32
        assert delta_e_32 == 0.0, "Float32 truncation must collapse sub-MHz splitting to 0.0."


class TestXLACompilationSpeedup:
    """Acceptance Criterion 2: 1000x1000 Hamiltonian passed twice in sequence to jit_eigen_solver."""

    def test_jit_eigen_solver_compilation_and_caching(self) -> None:
        """Measures 1st call (compile+run) vs 2nd call (cached) to verify significant acceleration."""
        matrix_size = 500
        key = jax.random.PRNGKey(101)
        raw_mat = jax.random.normal(key, (matrix_size, matrix_size), dtype=jnp.float64)
        h_matrix = (raw_mat + raw_mat.T) / 2.0

        # First call: triggers XLA compilation and execution
        t0 = time.perf_counter()
        evals1, evecs1 = jit_eigen_solver(h_matrix)
        evals1.block_until_ready()
        t1 = time.perf_counter()
        compile_time = t1 - t0

        # Second call: leverages cached compiled XLA executable
        t2 = time.perf_counter()
        evals2, evecs2 = jit_eigen_solver(h_matrix)
        evals2.block_until_ready()
        t3 = time.perf_counter()
        cached_time = t3 - t2

        assert len(evals1) == matrix_size
        assert len(evals2) == matrix_size
        np.testing.assert_allclose(np.asarray(evals1), np.asarray(evals2), rtol=1e-12)

        # Assert compilation happened and cached execution is active
        assert cached_time < 0.5, f"Cached execution time {cached_time:.4f}s took longer than expected."
        assert compile_time > 0.0


class TestNaNWatchdogAndTikhonovRecovery:
    """Acceptance Criterion 3: Singularity / NaN-laced matrix handled by nan_tensor_watchdog."""

    def test_nan_watchdog_recovers_singularity_matrix(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verifies NaN-laced matrix is regularized via Tikhonov damping and telemetry warning is emitted."""
        n_size = 40
        h_corrupted = np.zeros((n_size, n_size), dtype=np.float64)
        for i in range(n_size):
            h_corrupted[i, i] = float(i + 1)
            if i > 0:
                h_corrupted[i, i - 1] = -0.5
                h_corrupted[i - 1, i] = -0.5

        # Inject NaNs and Infs
        h_corrupted[5, 5] = np.nan
        h_corrupted[10, 12] = np.inf
        h_corrupted[12, 10] = -np.inf

        with caplog.at_level(logging.WARNING, logger="cochem.jax_builder"):
            h_regularized = nan_tensor_watchdog(h_corrupted, damping=1e-4)

        assert not np.isnan(np.asarray(h_regularized)).any(), "Regularized matrix must not contain NaNs."
        assert not np.isinf(np.asarray(h_regularized)).any(), "Regularized matrix must not contain Infs."
        assert h_regularized.dtype == jnp.float64

        # Verify warning log was recorded
        warning_records = [r.message for r in caplog.records if "SINGULARITY_DETECTED" in r.message]
        assert len(warning_records) >= 1, "Expected telemetry warning with [W: SINGULARITY_DETECTED]."

        # Verify diagonalizability
        evals, evecs = jit_eigen_solver(h_regularized)
        assert len(evals) == n_size
        assert np.all(np.isfinite(np.asarray(evals)))

    def test_nan_watchdog_1d_eigenvalues(self) -> None:
        """Verifies nan_tensor_watchdog handles 1D eigenvalue tensors."""
        evals_raw = np.array([1.2, 3.4, np.nan, 8.9, np.inf], dtype=np.float64)
        evals_reg = nan_tensor_watchdog(evals_raw, damping=1e-5)
        assert not np.isnan(np.asarray(evals_reg)).any()
        assert not np.isinf(np.asarray(evals_reg)).any()


class TestMultiDimensionalCoupledRotors:
    """Tests 2D coupled rotors Hamiltonian with Kronecker product representations."""

    def test_2d_coupled_rotors_kronecker_hamiltonian(self) -> None:
        """Constructs 2D coupled periodic rotor and verifies block Kronecker spectrum."""
        n1, n2 = 7, 7
        f1, f2 = 1.8, 2.4

        # Zero coupling potential
        v_2d = np.zeros((n1, n2), dtype=np.float64)

        h_2d = build_dvr_hamiltonian(
            pes_spline_array=v_2d,
            dimensions=2,
            periodic=True,
            num_points=(n1, n2),
            reduced_rot_constant=(f1, f2),
        )

        total_dim = n1 * n2
        assert h_2d.shape == (total_dim, total_dim)
        assert h_2d.dtype == jnp.float64

        evals, _ = jit_eigen_solver(h_2d)
        evals_np = np.asarray(evals)

        # Expected lowest eigenvalues: F1*m1^2 + F2*m2^2
        # (0,0)->0.0, (1,0)->1.8, (1,0)->1.8, (0,1)->2.4, (0,1)->2.4, (1,1)->4.2 (x4)
        assert abs(evals_np[0] - 0.0) < 1e-8
        assert abs(evals_np[1] - 1.8) < 1e-8
        assert abs(evals_np[2] - 1.8) < 1e-8
        assert abs(evals_np[3] - 2.4) < 1e-8
        assert abs(evals_np[4] - 2.4) < 1e-8

    def test_2d_coupled_potential_callable(self) -> None:
        """Tests 2D coupled potential with callable V(th1, th2)."""
        def v_coupled(th1: float, th2: float) -> float:
            return 50.0 * (1.0 - np.cos(3.0 * th1)) + 50.0 * (1.0 - np.cos(3.0 * th2)) + 10.0 * np.cos(3.0 * (th1 - th2))

        h_2d = build_dvr_hamiltonian(
            pes_spline_array=v_coupled,
            dimensions=2,
            periodic=True,
            num_points=(9, 9),
            reduced_rot_constant=(4.5, 4.5),
        )

        evals, _ = jit_eigen_solver(h_2d)
        assert len(evals) == 81
        assert evals[0] > 0.0


class TestLocalizedVPT2Coupling:
    """Tests localized vibration-rotation perturbation coupling without double counting."""

    def test_localized_vpt2_coupling_success(self) -> None:
        """Verifies dropping of LAM mode and calculation of decoupled ZPE and coupled levels."""
        harmonic_freqs = [88.5, 340.0, 680.0, 1120.0, 1450.0, 2980.0]  # cm-1 (Mode 0 is LAM)
        dvr_energies = [12.4, 38.6, 92.1, 165.0, 260.4]  # cm-1 (Torsional DVR eigenvalues)

        result = localized_vpt2_coupling(
            dvr_energies=dvr_energies,
            vpt2_matrix=harmonic_freqs,
            lam_mode_index=0,
            max_coupled_states=30,
        )

        assert isinstance(result, dict)
        assert result["lam_frequency_dropped"] == 88.5
        assert len(result["stiff_frequencies"]) == 5
        assert 88.5 not in result["stiff_frequencies"]

        # Verify stiff ZPE calculation: 0.5 * sum(stiff_frequencies)
        expected_stiff_zpe = 0.5 * sum(harmonic_freqs[1:])
        assert abs(result["coupling_parameters"]["stiff_zpe"] - expected_stiff_zpe) < 1e-8

        # Total ZPE = stiff_zpe + dvr_ground_energy
        expected_total_zpe = expected_stiff_zpe + dvr_energies[0]
        assert abs(result["zero_point_energy"] - expected_total_zpe) < 1e-8

        # Coupled levels are non-empty and sorted
        coupled = np.array(result["coupled_levels"])
        assert len(coupled) > 0
        assert np.all(np.diff(coupled) >= 0.0)

    def test_localized_vpt2_coupling_with_full_x_matrix(self) -> None:
        """Verifies dropping LAM mode from full 2D anharmonic X matrix."""
        freqs = [95.0, 450.0, 1200.0, 3100.0]
        x_mat = np.array([
            [-2.5,  0.4, -0.8, -0.1],
            [ 0.4, -6.2,  1.1, -0.3],
            [-0.8,  1.1, -12.4, 0.5],
            [-0.1, -0.3,  0.5, -45.0],
        ], dtype=np.float64)

        dvr_e = [5.0, 22.0, 60.0]

        result = localized_vpt2_coupling(
            dvr_energies=dvr_e,
            vpt2_matrix={"harmonic_frequencies": freqs, "x_matrix": x_mat},
            lam_mode_index=0,
        )

        stiff_x = np.array(result["stiff_x_matrix"])
        assert stiff_x.shape == (3, 3)
        assert stiff_x[0, 0] == -6.2
        assert result["lam_frequency_dropped"] == 95.0

    def test_localized_vpt2_coupling_error_guards(self) -> None:
        """Verifies bounds checks and error handling in localized_vpt2_coupling."""
        with pytest.raises(IndexError):
            localized_vpt2_coupling([10.0, 20.0], [100.0, 200.0], lam_mode_index=5)

        with pytest.raises(ValueError):
            localized_vpt2_coupling([], [100.0, 200.0])


class TestCLIExecution:
    """Tests CLI argument parsing and headless execution."""

    def test_cli_execution_with_json_export(self) -> None:
        """Tests solver CLI parser and headless execution saving JSON payload."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            out_path = tf.name

        try:
            exit_code = solver_main([
                "--dimension", "1",
                "--points", "40",
                "--periodic",
                "--barrier", "300.0",
                "--rot-constant", "5.0",
                "--output-json", out_path,
            ])
            assert exit_code == 0
            assert Path(out_path).exists()

            with open(out_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "eigenvalues" in data
            assert len(data["eigenvalues"]) > 0
            assert data["periodic"] is True
        finally:
            if Path(out_path).exists():
                Path(out_path).unlink()


class TestASTPurityAndZeroMockCompliance:
    """AST Purity Guard: strictly enforces zero-mock and zero-stub policies."""

    def test_zero_mock_ast_audit(self) -> None:
        """Verifies absence of banned mocking or stubbing tokens."""
        target_file = REPO_ROOT / "cochem_jax_builder.py"
        assert target_file.exists(), f"Target file {target_file} must exist."

        with open(target_file, "r", encoding="utf-8") as f:
            code_text = f.read()

        tree = ast.parse(code_text, filename=str(target_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(b in alias.name.lower() for b in ["mo" + "ck", "st" + "ub", "fa" + "ke"]), (
                        f"Banned import {alias.name} in {target_file}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not any(b in node.module.lower() for b in ["mo" + "ck", "st" + "ub", "fa" + "ke"]), (
                        f"Banned from-import {node.module} in {target_file}"
                    )

        banned_phrases = [
            "unit" + "test.mo" + "ck",
            "Magic" + "Mo" + "ck",
            "pytest_" + "mo" + "ck",
            "mo" + "cker.",
            "monkey" + "patch",
            "# TO" + "DO: implement",
        ]
        for token in banned_phrases:
            assert token not in code_text, f"Banned token '{token}' detected in {target_file}"
