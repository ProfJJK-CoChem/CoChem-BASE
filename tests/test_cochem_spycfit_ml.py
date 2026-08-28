# -*- coding: utf-8 -*-
"""Zero-Mock Unit and Integration Tests for CoChem-SpycFit ML Upgrade.

Validates:
- Schema definitions, resource boundaries, and dynamic Mendeleev masses (FR-3.1)
- Tripartite workspace air-gap configuration (Tier 1/2/3 separation)
- Pure JAX autodiff Hamiltonian, rigid rotor frequencies, and analytical Jacobians (FR-3.1.1)
- Gaussian Process active learning regressor with [TORQ] / [ML] tagging (FR-3.2.1-3)
- Dual-engine JAX vs SPFIT parity verification with 0.1 kHz threshold (FR-3.1.3)
- Smart scan information gain scoring & resolvability clustering filter (FR-3.3.1-4)
- Thread-safe SWMR HDF5 storage with FileLock IPC and zombie lock recovery
- DAG state commits, time-travel pointer swapping, and history traversal (FR-3.5.1-3)
- CoChem-BASE proxy integrations
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest
from mendeleev import element

from cochem_spycfit_ml_engine import (
    GaussianProcessSpectralRegressor,
    apply_resolvability_filter,
    calculate_information_gain,
    compute_analytical_jacobian,
    compute_rigid_rotor_frequencies,
    discover_hardware_hierarchy,
    evaluate_dual_engine_parity,
    rank_scan_windows,
)
from cochem_spycfit_ml_schema import (
    DynamicIsotopeRecord,
    FitStateCommitSchema,
    HardwareResourceLimits,
    HardwareTier,
    ProvenanceLedgerEntry,
    SpycFitMLConfig,
    TripartiteWorkspaceConfig,
)
from cochem_spycfit_ml_storage import (
    DAGCommitManager,
    EphemeralSandbox,
    SpycFitHDF5Storage,
    recover_zombie_locks,
)

# ==============================================================================
# Authentic Molecular Spectroscopic Constants (Water, SO2, Formaldehyde)
# ==============================================================================

# Water (H2O) - Asymmetric Top
H2O_A_MHZ = 835840.0
H2O_B_MHZ = 435350.0
H2O_C_MHZ = 278140.0
H2O_DIPOLE_B_DEBYE = 1.854

# Sulfur Dioxide (SO2) - Asymmetric Top
SO2_A_MHZ = 60778.5
SO2_B_MHZ = 10318.0
SO2_C_MHZ = 8799.8
SO2_DIPOLE_B_DEBYE = 1.63

# Formaldehyde (H2CO) - Prolate Near-Symmetric Top
H2CO_A_MHZ = 281970.6
H2CO_B_MHZ = 38833.9
H2CO_C_MHZ = 34004.2
H2CO_DIPOLE_A_DEBYE = 2.33

# Authentic rotational transitions: (J', Ka', Kc', J'', Ka'', Kc'')
AUTHENTIC_TRANSITIONS: List[Tuple[int, int, int, int, int, int]] = [
    (1, 0, 1, 0, 0, 0),  # 1_01 <- 0_00
    (1, 1, 1, 0, 0, 0),  # 1_11 <- 0_00
    (1, 1, 0, 1, 0, 1),  # 1_10 <- 1_01
    (2, 0, 2, 1, 0, 1),  # 2_02 <- 1_01
    (2, 1, 1, 1, 1, 0),  # 2_11 <- 1_10
]


# ==============================================================================
# 1. Schema & Mendeleev Dynamic Mass Tests
# ==============================================================================

class TestSpycFitMLSchema:
    """Test Pydantic v2 schemas and Mendeleev dynamic mass lookups."""

    def test_hardware_tier_enum(self) -> None:
        """Verify HardwareTier members."""
        assert HardwareTier.GPU == "GPU"
        assert HardwareTier.TPU == "TPU"
        assert HardwareTier.CPU == "CPU"
        assert HardwareTier.MPS == "MPS"

    def test_hardware_resource_limits(self) -> None:
        """Verify HardwareResourceLimits defaults and bounds."""
        limits = HardwareResourceLimits(
            mpi_threads=8,
            max_vram_gb=12.0,
            allowed_devices=["gpu:0", "cpu"],
            timeout_seconds=120.0,
            max_ram_gb=32.0,
        )
        assert limits.mpi_threads == 8
        assert limits.max_vram_gb == 12.0
        assert "gpu:0" in limits.allowed_devices
        assert limits.timeout_seconds == 120.0
        assert limits.max_ram_gb == 32.0

    def test_tripartite_workspace_config_resolution(self, tmp_path: Path) -> None:
        """Verify TripartiteWorkspaceConfig path resolution and environment override."""
        t1 = tmp_path / "repo_root"
        t2 = tmp_path / "artifacts_root"
        t3 = tmp_path / "scratch_root"
        t1.mkdir()
        t2.mkdir()
        t3.mkdir()

        config = TripartiteWorkspaceConfig(
            tier1_repo_root=t1,
            tier2_artifacts_root=t2,
            tier3_scratch_root=t3,
        )
        assert config.tier1_repo_root == t1.resolve()
        assert config.tier2_artifacts_root == t2.resolve()
        assert config.tier3_scratch_root == t3.resolve()

        # Test environment variable resolution
        os.environ["COCHEM_SRC"] = str(t1)
        os.environ["COCHEM_ARTIFACTS"] = str(t2)
        os.environ["COCHEM_STATE"] = str(t3)
        try:
            env_config = TripartiteWorkspaceConfig.resolve_from_environment()
            assert env_config.tier1_repo_root == t1.resolve()
            assert env_config.tier2_artifacts_root == t2.resolve()
            assert env_config.tier3_scratch_root == t3.resolve()
        finally:
            os.environ.pop("COCHEM_SRC", None)
            os.environ.pop("COCHEM_ARTIFACTS", None)
            os.environ.pop("COCHEM_STATE", None)

    def test_dynamic_isotope_record_mendeleev(self) -> None:
        """Verify dynamic atomic and isotopic masses via Mendeleev library."""
        # Carbon dynamic lookup
        c_rec = DynamicIsotopeRecord.from_mendeleev("C")
        c_expected = float(element("C").mass)
        assert c_rec.symbol == "C"
        assert c_rec.mass_number is None
        assert abs(c_rec.exact_mass_amu - c_expected) < 1e-6

        # Hydrogen dynamic lookup
        h_rec = DynamicIsotopeRecord.from_mendeleev("H")
        h_expected = float(element("H").mass)
        assert h_rec.symbol == "H"
        assert abs(h_rec.exact_mass_amu - h_expected) < 1e-6

        # C-13 isotope lookup
        c13_rec = DynamicIsotopeRecord.from_mendeleev("C", mass_number=13)
        assert c13_rec.mass_number == 13
        assert c13_rec.exact_mass_amu > 12.5

        # Molecular mass calculation: H2O
        h2o_mass = DynamicIsotopeRecord.calculate_molecular_mass([("H", 2), ("O", 1)])
        expected_h2o = 2 * float(element("H").mass) + float(element("O").mass)
        assert abs(h2o_mass - expected_h2o) < 1e-6

        # Molecular mass calculation: SO2
        so2_mass = DynamicIsotopeRecord.calculate_molecular_mass([("S", 1), ("O", 2)])
        expected_so2 = float(element("S").mass) + 2 * float(element("O").mass)
        assert abs(so2_mass - expected_so2) < 1e-6

    def test_fit_state_commit_schema_hash_and_immutability(self) -> None:
        """Verify FitStateCommitSchema canonical SHA-256 hash auto-generation and frozen behavior."""
        state = FitStateCommitSchema(
            parent_id=None,
            rotational_constants_mhz={"A": SO2_A_MHZ, "B": SO2_B_MHZ, "C": SO2_C_MHZ},
            dipole_moments_debye={"mu_b": SO2_DIPOLE_B_DEBYE},
            assigned_transitions=[
                {"transition": "1_01-0_00", "obs_freq_mhz": 19117.8, "residual_mhz": 0.012}
            ],
            chi_squared=0.000144,
            rms_residual_mhz=0.012,
            provenance_git_hash="cochem-test-commit-001",
        )
        assert len(state.state_id) == 64
        assert state.state_id == state.compute_state_hash()

        # Ensure immutability (frozen config)
        with pytest.raises((TypeError, ValueError)):
            state.chi_squared = 1.0  # type: ignore[misc]

    def test_provenance_ledger_entry(self) -> None:
        """Verify ProvenanceLedgerEntry validation."""
        entry = ProvenanceLedgerEntry(
            entry_id="audit-log-001",
            action="COMMIT",
            fit_state_id="a" * 64,
            actor="CoChem-CODER",
            checksum_sha256="b" * 64,
            metadata={"cycle": 1, "module": "spycfit_ml"},
        )
        assert entry.entry_id == "audit-log-001"
        assert entry.action == "COMMIT"
        assert entry.metadata["cycle"] == 1

    def test_spycfit_ml_config_defaults(self) -> None:
        """Verify SpycFitMLConfig master schema defaults."""
        cfg = SpycFitMLConfig()
        assert cfg.gp_alpha == 1e-4
        assert cfg.parity_warning_threshold_khz == 0.1
        assert cfg.instrument_resolution_mhz == 0.05
        assert cfg.scan_window_size_mhz == 500.0


# ==============================================================================
# 2. JAX Physics Engine & Autodiff Jacobians Tests
# ==============================================================================

class TestSpycFitMLEngine:
    """Test JAX Autodiff Hamiltonian, Jacobians, and Hardware Discovery."""

    def test_discover_hardware_hierarchy(self) -> None:
        """Verify dynamic hardware hierarchy report."""
        hw = discover_hardware_hierarchy()
        assert "primary_device" in hw
        assert "available_devices" in hw
        assert "backend" in hw
        assert hw["x64_enabled"] is True
        assert isinstance(hw["available_devices"], list)
        assert len(hw["available_devices"]) > 0

    def test_compute_rigid_rotor_frequencies_water(self) -> None:
        """Verify rigid rotor frequency calculations for authentic H2O constants."""
        freqs = compute_rigid_rotor_frequencies(
            H2O_A_MHZ, H2O_B_MHZ, H2O_C_MHZ, AUTHENTIC_TRANSITIONS
        )
        assert isinstance(freqs, np.ndarray)
        assert freqs.shape == (len(AUTHENTIC_TRANSITIONS),)
        assert np.all(freqs > 0.0)

        # 1_01 <- 0_00 for H2O: E(1_01) - E(0_00) = (B + C) - 0 = 435350 + 278140 = 713490 MHz
        expected_1_01_freq = H2O_B_MHZ + H2O_C_MHZ
        assert abs(freqs[0] - expected_1_01_freq) < 1e-3

    def test_compute_rigid_rotor_frequencies_so2(self) -> None:
        """Verify rigid rotor frequency calculations for authentic SO2 constants."""
        freqs = compute_rigid_rotor_frequencies(
            SO2_A_MHZ, SO2_B_MHZ, SO2_C_MHZ, AUTHENTIC_TRANSITIONS
        )
        assert isinstance(freqs, np.ndarray)
        assert freqs.shape == (len(AUTHENTIC_TRANSITIONS),)
        assert np.all(freqs > 0.0)

        # 1_01 <- 0_00 for SO2: (B + C) = 10318.0 + 8799.8 = 19117.8 MHz
        expected_so2_1_01 = SO2_B_MHZ + SO2_C_MHZ
        assert abs(freqs[0] - expected_so2_1_01) < 1e-3

    def test_compute_analytical_jacobian(self) -> None:
        """Verify JAX autodiff analytical Jacobian computation d(nu)/d(A, B, C)."""
        jac = compute_analytical_jacobian(
            SO2_A_MHZ, SO2_B_MHZ, SO2_C_MHZ, AUTHENTIC_TRANSITIONS
        )
        assert isinstance(jac, np.ndarray)
        assert jac.shape == (len(AUTHENTIC_TRANSITIONS), 3)

        # For 1_01 <- 0_00: frequency = B + C, so d(nu)/dA = 0, d(nu)/dB = 1, d(nu)/dC = 1
        assert abs(jac[0, 0] - 0.0) < 1e-5
        assert abs(jac[0, 1] - 1.0) < 1e-5
        assert abs(jac[0, 2] - 1.0) < 1e-5

        # For 1_10 <- 1_01: E(1_10) - E(1_01) = (A + B) - (B + C) = A - C
        # d(nu)/dA = 1, d(nu)/dB = 0, d(nu)/dC = -1
        assert abs(jac[2, 0] - 1.0) < 1e-5
        assert abs(jac[2, 1] - 0.0) < 1e-5
        assert abs(jac[2, 2] - (-1.0)) < 1e-5


# ==============================================================================
# 3. Gaussian Process Regressor & Active Learning Tests
# ==============================================================================

class TestGaussianProcessSpectralRegressor:
    """Test GP active learning regressor for O-C residual shifts."""

    @pytest.fixture
    def authentic_training_dataset(self) -> List[Dict[str, Any]]:
        """Construct realistic training transitions with authentic quantum numbers."""
        return [
            {
                "j_prime": 1, "ka_prime": 0, "kc_prime": 1,
                "j_double_prime": 0, "ka_double_prime": 0, "kc_double_prime": 0,
                "mu_a": 0.0, "mu_b": SO2_DIPOLE_B_DEBYE, "mu_c": 0.0,
                "lower_energy_cm": 0.0, "calc_freq_mhz": 19117.80, "residual_mhz": 0.015,
            },
            {
                "j_prime": 1, "ka_prime": 1, "kc_prime": 1,
                "j_double_prime": 0, "ka_double_prime": 0, "kc_double_prime": 0,
                "mu_a": 0.0, "mu_b": SO2_DIPOLE_B_DEBYE, "mu_c": 0.0,
                "lower_energy_cm": 0.0, "calc_freq_mhz": 69578.30, "residual_mhz": 0.022,
            },
            {
                "j_prime": 1, "ka_prime": 1, "kc_prime": 0,
                "j_double_prime": 1, "ka_double_prime": 0, "kc_double_prime": 1,
                "mu_a": 0.0, "mu_b": SO2_DIPOLE_B_DEBYE, "mu_c": 0.0,
                "lower_energy_cm": 0.637, "calc_freq_mhz": 51978.70, "residual_mhz": 0.018,
            },
            {
                "j_prime": 2, "ka_prime": 0, "kc_prime": 2,
                "j_double_prime": 1, "ka_double_prime": 0, "kc_double_prime": 1,
                "mu_a": 0.0, "mu_b": SO2_DIPOLE_B_DEBYE, "mu_c": 0.0,
                "lower_energy_cm": 0.637, "calc_freq_mhz": 38166.40, "residual_mhz": 0.025,
            },
            {
                "j_prime": 2, "ka_prime": 1, "kc_prime": 1,
                "j_double_prime": 1, "ka_double_prime": 1, "kc_double_prime": 0,
                "mu_a": 0.0, "mu_b": SO2_DIPOLE_B_DEBYE, "mu_c": 0.0,
                "lower_energy_cm": 2.371, "calc_freq_mhz": 43555.20, "residual_mhz": 0.030,
            },
        ]

    def test_gp_feature_extraction(self, authentic_training_dataset: List[Dict[str, Any]]) -> None:
        """Verify feature extraction dimensions and structure."""
        features = GaussianProcessSpectralRegressor.extract_features(authentic_training_dataset)
        assert features.shape == (len(authentic_training_dataset), 10)
        assert np.all(np.isfinite(features))

    def test_gp_fit_and_predict(self, authentic_training_dataset: List[Dict[str, Any]]) -> None:
        """Verify GP training and prediction of O-C residual shifts."""
        gp = GaussianProcessSpectralRegressor(alpha=1e-4)
        assert not gp.is_fitted

        gp.fit(authentic_training_dataset)
        assert gp.is_fitted

        query = [
            {
                "j_prime": 2, "ka_prime": 0, "kc_prime": 2,
                "j_double_prime": 1, "ka_double_prime": 0, "kc_double_prime": 1,
                "mu_a": 0.0, "mu_b": SO2_DIPOLE_B_DEBYE, "mu_c": 0.0,
                "lower_energy_cm": 0.637, "calc_freq_mhz": 38166.40,
            }
        ]
        shifts, uncertainties = gp.predict_shift(query)
        assert shifts.shape == (1,)
        assert uncertainties.shape == (1,)
        assert np.isfinite(shifts[0])
        assert uncertainties[0] >= 0.0

    def test_gp_tag_predictions(self, authentic_training_dataset: List[Dict[str, Any]]) -> None:
        """Verify [TORQ] vs [ML] tagging based on active learning state."""
        gp = GaussianProcessSpectralRegressor(alpha=1e-4)
        query = [
            {
                "j_prime": 1, "ka_prime": 0, "kc_prime": 1,
                "j_double_prime": 0, "ka_double_prime": 0, "kc_double_prime": 0,
                "mu_a": 0.0, "mu_b": SO2_DIPOLE_B_DEBYE, "mu_c": 0.0,
                "lower_energy_cm": 0.0, "calc_freq_mhz": 19117.80,
            }
        ]

        # Prior to fitting: tagged as [TORQ]
        untrained_tags = gp.tag_predictions(query, ab_initio=True)
        assert untrained_tags[0]["tag"] == "[TORQ]"
        assert untrained_tags[0]["ml_corrected_freq_mhz"] == 19117.80

        # After fitting: tagged as [ML]
        gp.fit(authentic_training_dataset)
        trained_tags = gp.tag_predictions(query, ab_initio=False)
        assert trained_tags[0]["tag"] == "[ML]"
        assert "ml_shift_mhz" in trained_tags[0]
        assert "uncertainty_mhz" in trained_tags[0]
        assert trained_tags[0]["uncertainty_mhz"] >= 0.0


# ==============================================================================
# 4. Dual-Engine Parity Bridge Tests
# ==============================================================================

class TestDualEngineParityBridge:
    """Test Dual-Engine JAX vs SPFIT parity verification."""

    def test_parity_passed_within_tolerance(self) -> None:
        """Verify parity check passes when delta <= 0.1 kHz."""
        jax_consts = {"A": 60778.50001, "B": 10318.00002, "C": 8799.80001}
        spfit_consts = {"A": 60778.50005, "B": 10318.00001, "C": 8799.80003}

        result = evaluate_dual_engine_parity(jax_consts, spfit_consts, threshold_khz=0.1)
        assert result["parity_passed"] is True
        assert result["parity_warning"] is False
        assert result["max_delta_khz"] <= 0.1

    def test_parity_warning_triggered_exceeding_threshold(self) -> None:
        """Verify yellow parity warning is raised when delta > 0.1 kHz."""
        jax_consts = {"A": 60778.50020, "B": 10318.00000, "C": 8799.80000}
        spfit_consts = {"A": 60778.50000, "B": 10318.00000, "C": 8799.80000}
        # Delta on A is 0.00020 MHz = 0.20 kHz > 0.1 kHz threshold

        result = evaluate_dual_engine_parity(jax_consts, spfit_consts, threshold_khz=0.1)
        assert result["parity_passed"] is False
        assert result["parity_warning"] is True
        assert abs(result["max_delta_khz"] - 0.20) < 1e-4
        assert result["deltas_khz"]["A"] > 0.1


# ==============================================================================
# 5. Smart Scan Navigator & Resolvability Filter Tests
# ==============================================================================

class TestSmartScanNavigator:
    """Test Information Gain scoring, resolvability filtering, and chunked scan ranking."""

    def test_information_gain_calculation(self) -> None:
        """Verify Information Gain scoring from authentic covariance and Jacobian."""
        # Authentic 3x3 covariance matrix for (A, B, C) in (MHz)^2
        cov = np.array([
            [1.2e-4, 3.4e-6, 1.1e-6],
            [3.4e-6, 8.5e-5, 2.3e-6],
            [1.1e-6, 2.3e-6, 6.2e-5],
        ], dtype=np.float64)

        jac = compute_analytical_jacobian(
            SO2_A_MHZ, SO2_B_MHZ, SO2_C_MHZ, AUTHENTIC_TRANSITIONS
        )
        info_gain = calculate_information_gain(cov, jac)
        assert isinstance(info_gain, np.ndarray)
        assert info_gain.shape == (len(AUTHENTIC_TRANSITIONS),)
        assert np.all(info_gain > 0.0)

    def test_resolvability_filter(self) -> None:
        """Verify penalization of clustered spectroscopic lines."""
        # Frequencies: 19117.80 and 19117.83 are separated by 0.03 MHz < 2*0.05 = 0.1 MHz
        # Line 51978.70 is well isolated (> 1000 MHz away)
        freqs = np.array([19117.80, 19117.83, 51978.70], dtype=np.float64)
        intensities = np.array([1.0, 0.9, 0.8], dtype=np.float64)

        weights = apply_resolvability_filter(freqs, intensities, instrument_resolution_mhz=0.05)
        assert weights.shape == (3,)
        # Clustered lines should have weight < 1.0
        assert weights[0] < 1.0
        assert weights[1] < 1.0
        # Isolated line should have full weight 1.0
        assert weights[2] == 1.0

    def test_rank_scan_windows(self) -> None:
        """Verify hardware-aware chunked scan ranking by aggregated Information Gain."""
        candidates = [
            {"transition": "1_01-0_00", "freq_mhz": 19117.8},
            {"transition": "2_02-1_01", "freq_mhz": 38166.4},
            {"transition": "2_11-1_10", "freq_mhz": 43555.2},
            {"transition": "1_10-1_01", "freq_mhz": 51978.7},
            {"transition": "1_11-0_00", "freq_mhz": 69578.3},
        ]
        cov = np.array([
            [1.2e-4, 3.4e-6, 1.1e-6],
            [3.4e-6, 8.5e-5, 2.3e-6],
            [1.1e-6, 2.3e-6, 6.2e-5],
        ], dtype=np.float64)
        jac = compute_analytical_jacobian(
            SO2_A_MHZ, SO2_B_MHZ, SO2_C_MHZ, AUTHENTIC_TRANSITIONS
        )

        windows = rank_scan_windows(candidates, cov, jac, window_size_mhz=20000.0)
        assert len(windows) > 0
        assert "start_freq_mhz" in windows[0]
        assert "end_freq_mhz" in windows[0]
        assert "total_info_gain" in windows[0]
        # Sorted descending by total_info_gain
        for i in range(len(windows) - 1):
            assert windows[i]["total_info_gain"] >= windows[i + 1]["total_info_gain"]


# ==============================================================================
# 6. Thread-Safe HDF5 Storage & Sandbox Tests
# ==============================================================================

class TestSpycFitHDF5StorageAndSandbox:
    """Test SWMR HDF5 persistence, FileLock concurrency, and ephemeral sandboxes."""

    def test_ephemeral_sandbox_lifecycle(self, tmp_path: Path) -> None:
        """Verify Tier 3 ephemeral sandbox automatic cleanup."""
        scratch_base = tmp_path / "scratch_base"
        scratch_base.mkdir()

        created_path = None
        with EphemeralSandbox(base_scratch_dir=scratch_base) as sandbox:
            created_path = sandbox.path
            assert created_path is not None
            assert created_path.exists()

            # Create test scratch file
            scratch_file = sandbox.create_scratch_file("test.inp", "SPFIT INPUT TEST")
            assert scratch_file.exists()
            assert scratch_file.read_text(encoding="utf-8") == "SPFIT INPUT TEST"

        # After context exit, sandbox directory must be purged
        assert created_path is not None
        assert not created_path.exists()

    def test_recover_zombie_locks(self, tmp_path: Path) -> None:
        """Verify recovery of stale/orphaned sidecar lock files."""
        lock_file = tmp_path / "test_store.h5.lock"
        # Write dead PID and old timestamp into lock file
        lock_file.write_text("999999:0.0", encoding="utf-8")
        assert lock_file.exists()

        recovered = recover_zombie_locks(lock_file, max_stale_seconds=1.0)
        assert recovered is True
        assert not lock_file.exists()

    def test_hdf5_swmr_state_persistence_and_retrieval(self, tmp_path: Path) -> None:
        """Verify thread-safe HDF5 state writing and reading."""
        h5_path = tmp_path / "spycfit_artifacts.h5"
        storage = SpycFitHDF5Storage(timeout_seconds=5.0)
        storage.initialize_store(h5_path)

        state = FitStateCommitSchema(
            parent_id=None,
            rotational_constants_mhz={"A": SO2_A_MHZ, "B": SO2_B_MHZ, "C": SO2_C_MHZ},
            dipole_moments_debye={"mu_b": SO2_DIPOLE_B_DEBYE},
            assigned_transitions=[
                {"transition": "1_01-0_00", "obs_freq_mhz": 19117.8, "residual_mhz": 0.012}
            ],
            chi_squared=0.000144,
            rms_residual_mhz=0.012,
            provenance_git_hash="cochem-test-commit-002",
        )

        storage.write_fit_state(state, h5_path)
        states = storage.list_states(h5_path)
        assert state.state_id in states

        loaded_state = storage.read_fit_state(state.state_id, h5_path)
        assert loaded_state.state_id == state.state_id
        assert loaded_state.rotational_constants_mhz["A"] == SO2_A_MHZ
        assert loaded_state.chi_squared == 0.000144

    def test_hdf5_tensor_dataset_persistence(self, tmp_path: Path) -> None:
        """Verify numerical tensor dataset persistence and metadata retrieval."""
        h5_path = tmp_path / "tensor_artifacts.h5"
        storage = SpycFitHDF5Storage(timeout_seconds=5.0)
        storage.initialize_store(h5_path)

        # Authentic spectroscopic frequency array
        freq_tensor = np.array([19117.8, 38166.4, 43555.2, 51978.7, 69578.3], dtype=np.float64)
        storage.write_tensor_dataset(
            "so2_frequencies",
            freq_tensor,
            h5_path,
            metadata={"molecule": "SO2", "unit": "MHz"},
        )

        read_tensor = storage.read_tensor_dataset("so2_frequencies", h5_path)
        assert np.allclose(read_tensor, freq_tensor)


# ==============================================================================
# 7. DAG Commit Manager & Time-Travel Reversion Tests
# ==============================================================================

class TestDAGCommitManager:
    """Test DAG branching history, commits, and pointer swapping time-travel."""

    def test_dag_commit_and_lineage_history(self, tmp_path: Path) -> None:
        """Verify multi-generation DAG commits and lineage traversal."""
        h5_path = tmp_path / "dag_registry.h5"
        storage = SpycFitHDF5Storage(timeout_seconds=5.0)
        storage.initialize_store(h5_path)
        dag = DAGCommitManager(storage, h5_path)

        # Root Commit (State 0)
        state_root = FitStateCommitSchema(
            parent_id=None,
            rotational_constants_mhz={"A": 60700.0, "B": 10300.0, "C": 8700.0},
            chi_squared=0.05,
            rms_residual_mhz=0.5,
        )
        root_id = dag.commit(state_root)
        assert dag.current_head_id == root_id

        # Generation 1 Commit
        state_gen1 = FitStateCommitSchema(
            parent_id=root_id,
            rotational_constants_mhz={"A": 60750.0, "B": 10310.0, "C": 8750.0},
            chi_squared=0.01,
            rms_residual_mhz=0.1,
        )
        gen1_id = dag.commit(state_gen1)
        assert dag.current_head_id == gen1_id

        # Generation 2 Commit (Refined)
        state_gen2 = FitStateCommitSchema(
            parent_id=gen1_id,
            rotational_constants_mhz={"A": SO2_A_MHZ, "B": SO2_B_MHZ, "C": SO2_C_MHZ},
            chi_squared=0.0001,
            rms_residual_mhz=0.01,
        )
        gen2_id = dag.commit(state_gen2)
        assert dag.current_head_id == gen2_id

        # Traverse history from Head (Gen2 -> Gen1 -> Root)
        history = dag.get_history()
        assert len(history) == 3
        assert history[0].state_id == gen2_id
        assert history[1].state_id == gen1_id
        assert history[2].state_id == root_id

    def test_dag_time_travel_reversion(self, tmp_path: Path) -> None:
        """Verify non-destructive pointer swapping time-travel back to earlier state."""
        h5_path = tmp_path / "dag_timetravel.h5"
        storage = SpycFitHDF5Storage(timeout_seconds=5.0)
        storage.initialize_store(h5_path)
        dag = DAGCommitManager(storage, h5_path)

        state_0 = FitStateCommitSchema(
            parent_id=None,
            rotational_constants_mhz={"A": 60000.0, "B": 10000.0, "C": 8000.0},
            chi_squared=1.0,
        )
        s0_id = dag.commit(state_0)

        state_1 = FitStateCommitSchema(
            parent_id=s0_id,
            rotational_constants_mhz={"A": 60500.0, "B": 10200.0, "C": 8500.0},
            chi_squared=0.5,
        )
        s1_id = dag.commit(state_1)
        assert dag.current_head_id == s1_id

        # Time-travel revert back to state_0
        reverted = dag.revert_to(s0_id)
        assert dag.current_head_id == s0_id
        assert reverted.state_id == s0_id
        assert reverted.rotational_constants_mhz["A"] == 60000.0


# ==============================================================================
# 8. CoChem-BASE Package Proxies Integration Tests
# ==============================================================================

class TestCoChemBaseProxyIntegration:
    """Verify CoChem-BASE package proxies and __getattr__ resolution."""

    def test_cochem_base_submodule_proxy_imports(self) -> None:
        """Verify proxy imports directly from cochem_base package."""
        import cochem_base.cochem_spycfit_ml_engine as proxy_engine
        import cochem_base.cochem_spycfit_ml_schema as proxy_schema
        import cochem_base.cochem_spycfit_ml_storage as proxy_storage

        assert hasattr(proxy_schema, "FitStateCommitSchema")
        assert hasattr(proxy_schema, "DynamicIsotopeRecord")
        assert hasattr(proxy_engine, "GaussianProcessSpectralRegressor")
        assert hasattr(proxy_engine, "compute_analytical_jacobian")
        assert hasattr(proxy_storage, "SpycFitHDF5Storage")
        assert hasattr(proxy_storage, "DAGCommitManager")

    def test_cochem_base_getattr_resolution(self) -> None:
        """Verify dynamic getattr resolution from cochem_base top-level module."""
        import cochem_base

        mod_schema = cochem_base.__getattr__("cochem_spycfit_ml_schema")
        mod_engine = cochem_base.__getattr__("cochem_spycfit_ml_engine")
        mod_storage = cochem_base.__getattr__("cochem_spycfit_ml_storage")

        assert mod_schema is not None
        assert mod_engine is not None
        assert mod_storage is not None
