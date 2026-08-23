
from __future__ import annotations

import json
import math
from pathlib import Path

import jax.numpy as jnp
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import cochem_base.cochem_catalog_compiler as proxy10
import cochem_base.cochem_jax_builder as proxy7
import cochem_base.cochem_spcat_bridge as proxy8

# Proxy Modules
import cochem_base.cochem_tensor_extractor as proxy6
import cochem_base.cochem_torq_export as proxy9_export
import cochem_base.cochem_torq_telemetry as proxy9_telemetry
import cochem_catalog_compiler as phase10
import cochem_jax_builder as phase7
import cochem_spcat_bridge as phase8

# Target Modules
import cochem_tensor_extractor as phase6
import cochem_torq_export as phase9_export
import cochem_torq_telemetry as phase9_telemetry
from cochem_base.exceptions import (
    FortranOverflowError,
    KraitchmanZPVEWarning,
    LAMTriggerError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
    TelemetryNetworkExhaustedWarning,
)

# =============================================================================
# 1. Phase 6: Tensor Extraction Tests
# =============================================================================

class TestPhase6TensorExtractor:
    """Validates moment of inertia tensor extraction and representation switching."""

    def test_ciaaw_isotopic_masses_and_constants(self) -> None:
        """Verify exact CODATA 2022 constants and CIAAW isotopic masses."""
        assert phase6.PLANCK_H == 6.62607015e-34
        assert phase6.AMU_KG == 1.66053906660e-27
        assert phase6.SPEED_OF_LIGHT_CM_S == 29979245800.0
        assert abs(phase6.INERTIA_CONVERSION_AMU_ANG2_MHZ - 505379.008435) < 1e-3

        # CIAAW mass checks
        assert abs(phase6.resolve_atomic_mass("1H") - 1.00782503223) < 1e-8
        assert abs(phase6.resolve_atomic_mass("12C") - 12.0) < 1e-8
        assert abs(phase6.resolve_atomic_mass("16O") - 15.99491461957) < 1e-8
        assert abs(phase6.resolve_atomic_mass("35Cl") - 34.96885271) < 1e-8

    def test_center_of_mass_translation(self) -> None:
        """Verify center of mass calculation and translation."""
        coords = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ], dtype=np.float64)
        symbols = ["O", "H", "H"]
        masses = [phase6.resolve_atomic_mass(s) for s in symbols]

        centered, com = phase6.translate_to_center_of_mass(coords, masses)
        new_com = phase6.calculate_center_of_mass(centered, masses)
        assert np.allclose(new_com, [0.0, 0.0, 0.0], atol=1e-12)

    def test_h2o_inertia_tensor_and_rotational_constants(self) -> None:
        """Verify diagonalization on real water (H2O) geometry."""
        coords = np.array([
            [0.0, 0.0, 0.0],
            [0.0, 0.757, 0.586],
            [0.0, -0.757, 0.586],
        ], dtype=np.float64)
        symbols = ["O", "H", "H"]

        res = phase6.diagonalize_inertia_tensor(coords, symbols, unit="MHz")
        assert res.total_mass_amu > 18.0
        assert res.rotational_constants_mhz["A"] > res.rotational_constants_mhz["B"]
        assert res.rotational_constants_mhz["B"] > res.rotational_constants_mhz["C"]
        assert res.rotor_type in ("prolate_asymmetric", "oblate_asymmetric")
        assert abs(res.inertial_defect_amu_ang2) < 0.1
        assert res.is_planar is True
        assert res.is_linear is False

    def test_linear_rotor_cartesian_protection(self) -> None:
        """Verify near-180 deg linear rotor singularity protection and 2D cylindrical projection."""
        # Collinear CO2 along Z
        coords = np.array([
            [0.0, 0.0, -1.16],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.16],
        ], dtype=np.float64)
        symbols = ["O", "C", "O"]

        prot = phase6.apply_cartesian_protections(coords, symbols, angle_threshold_deg=175.0)
        assert prot.is_linear is True
        assert prot.collinear_axis == "Z"
        assert prot.cylindrical_coordinates is not None
        assert prot.cylindrical_coordinates.shape == (3, 2)

        res = phase6.diagonalize_inertia_tensor(coords, symbols)
        assert res.is_linear is True
        assert math.isinf(res.rotational_constants_mhz["A"])

    def test_dynamic_representation_switch_ray_kappa(self) -> None:
        """Verify Ray kappa analysis and representation switching (Ir <-> IIIr)."""
        # Prolate top (B ~ C, kappa ~ -1) -> Ir
        rep_pro = phase6.dynamic_representation_switch(10000.0, 5000.0, 4999.0)
        assert rep_pro.recommended_representation == "Ir"
        assert rep_pro.is_prolate is True
        assert rep_pro.is_oblate is False

        # Oblate top (A ~ B, kappa ~ +1) -> IIIr
        rep_ob = phase6.dynamic_representation_switch(10000.0, 9999.0, 5000.0)
        assert rep_ob.recommended_representation == "IIIr"
        assert rep_ob.is_prolate is False
        assert rep_ob.is_oblate is True

    def test_torq_tensor_extractor_class_and_dataframe(self) -> None:
        """Verify TorqTensorExtractor class and DataFrame export."""
        coords = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ])
        ext = phase6.TorqTensorExtractor(coords, symbols=["O", "H", "H"])
        df = ext.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert "A_MHz" in df.columns
        assert "inertial_defect" in df.columns
        assert "representation" in df.columns


# =============================================================================
# 2. Phase 7: Multi-Dimensional Physics & JAX Solvers Tests
# =============================================================================

class TestPhase7JAXSolvers:
    """Validates JAX float64 DVR solvers and localized VPT2 coupling."""

    def test_enforce_jax_precision_float64(self) -> None:
        """Verify JAX 64-bit precision enforcement."""
        hw = phase7.enforce_jax_precision(force_recheck=True)
        assert hw["float64_enabled"] is True
        t = jnp.array(1.0)
        assert t.dtype == jnp.float64

    def test_1d_particle_in_a_box_sine_dvr(self) -> None:
        """Verify 1D particle in a box Sine-DVR matches analytical eigenvalues."""
        n_pts = 80
        length = 1.0
        mass = 1.0
        hbar = 1.0

        v_zero = np.zeros(n_pts, dtype=np.float64)
        h = phase7.build_dvr_hamiltonian(
            pes_spline_array=v_zero,
            dimensions=1,
            mass=mass,
            length=length,
            periodic=False,
            num_points=n_pts,
            hbar=hbar,
        )
        evals, _ = phase7.jit_eigen_solver(h)
        evals_np = np.asarray(evals)

        # Analytical E_n = (n^2 * pi^2 * hbar^2) / (2 * m * L^2)
        n_vals = np.arange(1, 6)
        e_exact = (n_vals**2 * np.pi**2 * hbar**2) / (2.0 * mass * length**2)
        assert np.allclose(evals_np[:5], e_exact, rtol=1e-3)

    def test_1d_periodic_fourier_dvr_internal_rotor(self) -> None:
        """Verify 1D periodic Fourier-DVR for internal rotor with V3 barrier."""
        n_pts = 61
        v3 = 300.0  # cm-1
        f_const = 5.3  # cm-1

        th = 2.0 * np.pi * np.arange(n_pts) / n_pts
        v_grid = (v3 / 2.0) * (1.0 - np.cos(3.0 * th))

        h = phase7.build_dvr_hamiltonian(
            pes_spline_array=v_grid,
            dimensions=1,
            periodic=True,
            num_points=n_pts,
            reduced_rot_constant=f_const,
        )
        evals, evecs = phase7.jit_eigen_solver(h)
        evals_np = np.asarray(evals)

        assert len(evals_np) == n_pts
        assert evals_np[0] < evals_np[1]
        # Tunneling pairs should have degenerate / small splitting structure
        splitting = abs(evals_np[2] - evals_np[1])
        assert splitting < v3

    def test_2d_coupled_internal_rotors_kronecker(self) -> None:
        """Verify 2D coupled rotors direct product Hamiltonian via Kronecker product."""
        n1 = 15
        n2 = 15
        v_2d = np.zeros((n1, n2), dtype=np.float64)

        h_2d = phase7.build_dvr_hamiltonian(
            pes_spline_array=v_2d,
            dimensions=2,
            periodic=True,
            num_points=(n1, n2),
            reduced_rot_constant=(5.0, 5.0),
        )
        assert h_2d.shape == (n1 * n2, n1 * n2)
        evals, _ = phase7.jit_eigen_solver(h_2d)
        assert len(evals) == n1 * n2

    def test_nan_tensor_watchdog_tikhonov_recovery(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify NaN/Inf watchdog intercepts divergence and applies Tikhonov damping."""
        h_bad = np.array([
            [1.0, np.nan],
            [np.nan, 2.0],
        ])
        with caplog.at_level("WARNING", logger="cochem.jax_builder"):
            h_clean = phase7.nan_tensor_watchdog(h_bad, damping=1e-5)
        assert not np.isnan(np.asarray(h_clean)).any()
        assert not np.isinf(np.asarray(h_clean)).any()
        assert "SINGULARITY_DETECTED" in caplog.text

    def test_localized_vpt2_coupling_drops_lam(self) -> None:
        """Verify localized VPT2 coupling drops LAM harmonic mode to avoid double counting."""
        dvr_energies = np.array([0.0, 15.2, 45.8, 120.0])
        vpt2_dict = {
            "frequencies": [35.0, 1500.0, 3600.0],  # 35 cm-1 is LAM mode
            "x_matrix": np.zeros((3, 3)),
        }
        res = phase7.localized_vpt2_coupling(
            dvr_energies=dvr_energies,
            vpt2_matrix=vpt2_dict,
            lam_mode_index=0,
        )
        assert res["lam_frequency_dropped"] == 35.0
        assert len(res["stiff_frequencies"]) == 2
        assert res["num_stiff_modes"] == 2
        assert res["zero_point_energy"] > 0.0


# =============================================================================
# 3. Phase 8: Statistical Mechanics & SPCAT Bridge Tests
# =============================================================================

class TestPhase8SPCATBridge:
    """Validates statistical mechanics partition functions, MolSym, and Pickett formatting."""

    def test_low_frequency_lam_trap_triggers_and_passes(self) -> None:
        """Verify low-frequency LAM trap intercepts modes < 50 cm^-1 and allows stiff modes."""
        bad_freqs = [3500.0, 1500.0, 24.5]
        with pytest.raises(LAMTriggerError) as exc_info:
            phase8.low_frequency_lam_trap(bad_freqs, threshold_cm1=50.0)
        assert exc_info.value.error_code == ProvenanceErrorCode.LAM_TRIGGER

        good_freqs = [3500.0, 1500.0, 120.0]
        stiff = phase8.low_frequency_lam_trap(good_freqs, threshold_cm1=50.0)
        assert len(stiff) == 3

    def test_molsym_symmetry_divisors_and_double_counting_guardrail(self) -> None:
        """Verify MolSym point group detection and strict double-counting selection rule."""
        h2o_geom = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ])
        sym_res = phase8.apply_symmetry_divisors(
            geometry_array=h2o_geom,
            symbols=["O", "H", "H"],
            use_nuclear_spin=False,
        )
        assert sym_res.point_group in ("C2v", "C2")
        assert sym_res.sigma == 2
        assert sym_res.effective_divisor == 2.0

        # With nuclear spin applied, sigma divisor must be bypassed (effective_divisor = 1.0)
        sym_res_spin = phase8.apply_symmetry_divisors(
            geometry_array=h2o_geom,
            symbols=["O", "H", "H"],
            use_nuclear_spin=True,
        )
        assert sym_res_spin.effective_divisor == 1.0
        assert "EXACT_NUCLEAR_SPIN_APPLIED" in sym_res_spin.guardrail_status

    def test_partition_function_calculations(self) -> None:
        """Verify Q_rot and Q_vib calculations across temperature grid."""
        a, b, c = 825360.0, 435360.0, 278130.0
        q_rot_300 = phase8.calculate_rotational_partition_function(a, b, c, 300.0, sigma=2.0)
        assert q_rot_300 > 1.0

        q_vib_300 = phase8.calculate_vibrational_partition_function([1595.0, 3657.0, 3756.0], 300.0)
        assert q_vib_300 >= 1.0

    def test_fortran_double_precision_formatter_and_overflow_guard(self) -> None:
        """Verify Fortran scientific 'D' formatting and overflow exception trapping."""
        s = phase8.format_fortran_double(1.567e-5, compact=True)
        assert "D-05" in s or "D-5" in s

        # Overflow guard
        bad_val = 1e309
        with pytest.raises(FortranOverflowError):
            phase8.fortran_overflow_guard(bad_val)

    def test_spcat_var_and_int_file_generation(self) -> None:
        """Verify Pickett .var and .int ASCII generation."""
        params = {
            "A": 825360.0,
            "B": 435360.0,
            "C": 278130.0,
            "DJ": 1.567e-5,
        }
        var_str = phase8.generate_spcat_var(
            molecule_name="H2O",
            parameters=params,
        )
        assert "H2O" in var_str
        assert "10000" in var_str

        int_dict = phase8.generate_spcat_int(
            molecule_name="H2O",
            dipoles={"mu_b": 1.8546},
            temperatures=300.0,
        )
        assert 300.0 in int_dict
        assert "H2O" in int_dict[300.0]
        assert "300.00" in int_dict[300.0]

    def test_3tier_routing_protocol(self) -> None:
        """Verify 3-Tier Routing Protocol (MPQC Primary, ORCA Secondary, CFOUR Legacy)."""
        mpqc = {"energy_hartree": -76.432, "frequencies": [1600.0, 3700.0]}
        orca = {"energy_hartree": -76.400, "frequencies": [1590.0, 3680.0], "x_matrix": np.zeros((2, 2))}
        cfour = {"energy_hartree": -76.390}

        # MPQC primary for energy
        res1 = phase8.route_3tier_abinitio_payload(mpqc_data=mpqc, orca_data=orca, require_analytic_vpt2=False)
        assert res1.selected_tier == 1
        assert res1.primary_engine == "MPQC"

        # ORCA selected when analytic VPT2 is strictly required
        res2 = phase8.route_3tier_abinitio_payload(mpqc_data=mpqc, orca_data=orca, require_analytic_vpt2=True)
        assert res2.selected_tier == 2
        assert res2.primary_engine == "ORCA"

        # CFOUR fallback
        res3 = phase8.route_3tier_abinitio_payload(cfour_data=cfour)
        assert res3.selected_tier == 3
        assert res3.primary_engine == "CFOUR"


# =============================================================================
# 4. Phase 9: SpycFit Payload Synthesis & Telemetry Tests
# =============================================================================

class TestPhase9ExportAndTelemetry:
    """Validates Kraitchman coordinates, SpycFit bundle, Plotly 3D, and webhooks."""

    def test_kraitchman_substitution_coordinates(self) -> None:
        """Verify substitution coordinate r_s evaluation on asymmetric top."""
        tensor_dict = {
            "I_a": 35.0, "I_b": 60.0, "I_c": 90.0, "parent_mass": 50.0,
            "I_a_iso": 35.8, "I_b_iso": 60.5, "I_c_iso": 91.2, "delta_m": 1.00335,
        }
        res = phase9_export.calculate_kraitchman_coords(tensor_dict)
        assert "coordinates" in res
        for ax in ("a", "b", "c"):
            assert res["coordinates"][ax] >= 0.0
            assert res["costain_uncertainties"][f"delta_{ax}"] > 0.0

    def test_kraitchman_zpve_defect_clamping(self) -> None:
        """Verify ZPVE imaginary root clamping to 0.0000 A with KraitchmanZPVEWarning."""
        tensor_dict = {
            "I_a": 35.0, "I_b": 60.0, "I_c": 90.0, "parent_mass": 50.0,
            # Negative shift causing imaginary root for axis b and c
            "I_a_iso": 34.9, "I_b_iso": 60.0, "I_c_iso": 90.0, "delta_m": 1.00335,
        }
        with pytest.warns(KraitchmanZPVEWarning):
            res = phase9_export.calculate_kraitchman_coords(tensor_dict)
        assert res["coordinates"]["b"] == 0.0000
        assert res["zpve_defect_clamped"]["b"] is True

    def test_lock_provenance_payload_and_bundle(self, tmp_path: Path) -> None:
        """Verify deterministic provenance locking and .zip/.tar.zst payload bundling."""
        data_file = tmp_path / "spectral_constants.json"
        data_file.write_text(json.dumps({"A": 1000.0, "B": 500.0, "C": 250.0}), encoding="utf-8")

        manifest = phase9_export.lock_provenance_payload(str(tmp_path))
        assert "root_payload_hash" in manifest
        assert "files" in manifest
        assert "spectral_constants.json" in manifest["files"]

        # Bundle payload
        archive = phase9_export.bundle_spycfit_payload(str(tmp_path), output_dir=str(tmp_path))
        assert Path(archive).exists()

        # Integrity verification
        assert phase9_export.verify_payload_integrity(str(tmp_path)) is True

    def test_generate_plotly_3d_carousels(self) -> None:
        """Verify 2D/3D PES decimation and Plotly standalone HTML generation."""
        pes = np.sin(np.linspace(0, np.pi, 20))[:, None] * np.cos(np.linspace(0, np.pi, 20))[None, :]
        html = phase9_telemetry.generate_plotly_3d_carousels(pes, title="Test PES Surface")
        assert "<html" in html.lower()
        assert "plotly" in html.lower()

    def test_export_crash_animation_and_diagnostics(self, tmp_path: Path) -> None:
        """Verify Steric Shatter crash trajectory and JSON pathology report."""
        traj = np.zeros((5, 3, 3))
        # Final frame with steric clash (< 0.7 A)
        traj[-1, 0] = [0.0, 0.0, 0.0]
        traj[-1, 1] = [0.0, 0.0, 0.4]  # 0.4 A clash
        traj[-1, 2] = [1.5, 0.0, 0.0]

        xyz_p, json_p = phase9_telemetry.export_crash_animation(
            trajectory_array=traj,
            error_node_id="worker_node_42",
            output_path=str(tmp_path),
            atom_symbols=["C", "H", "O"],
        )
        assert Path(xyz_p).exists()
        assert Path(json_p).exists()

        diag = json.loads(Path(json_p).read_text(encoding="utf-8"))
        assert diag["steric_clash_detected"] is True
        assert diag["failure_type"] == "StericShatterCollision"

    def test_generate_pgopher_skeleton(self, tmp_path: Path) -> None:
        """Verify zero-RAM PGOPHER skeleton synthesis via Parquet metadata."""
        pq_path = tmp_path / "dummy.parquet"
        table = pa.Table.from_arrays([pa.array([100.0, 200.0])], names=["frequency_mhz"])
        pq.write_table(table, pq_path)

        json_path = tmp_path / "params.json"
        json_path.write_text(json.dumps({
            "molecule_name": "TestMol",
            "rotational_constants": {"A": 1000.0, "B": 500.0, "C": 250.0},
        }), encoding="utf-8")

        pgo_xml = phase9_export.generate_pgopher_skeleton(str(pq_path), str(json_path))
        assert "<PGOPHER" in pgo_xml
        assert "TestMol" in pgo_xml

    def test_stream_webhook_events_spooling(self, tmp_path: Path) -> None:
        """Verify non-blocking webhook event dispatch and spooling without crashing."""
        spool_f = tmp_path / "telemetry_spool.jsonl"
        with pytest.warns(TelemetryNetworkExhaustedWarning):
            success = phase9_telemetry.stream_webhook_events(
                status_payload={"status": "JOB_COMPLETE", "node_id": "test_node"},
                webhook_url="http://127.0.0.1:9999/dummy_webhook",
                timeout=2.0,
                max_retries=1,
                spool_file=str(spool_f),
            )
        assert success is False
        assert spool_f.exists()


# =============================================================================
# 5. Phase 10: FAIR Catalog Archiver Tests
# =============================================================================

class TestPhase10CatalogCompiler:
    """Validates PyArrow chunked parquet, AASTeX LaTeX, banned methods audit, and BibTeX."""

    def test_pyarrow_chunked_serializer_constant_memory(self, tmp_path: Path) -> None:
        """Verify O(1) constant RAM streaming PyArrow Parquet serializer."""
        def record_gen():
            for i in range(5000):
                yield {
                    "frequency_mhz": float(1000.0 + i),
                    "uncertainty_mhz": 0.01,
                    "log_intensity": -4.0,
                    "degrees_of_freedom": 2,
                    "lower_state_energy_cm1": float(i * 0.1),
                    "upper_state_degeneracy": 3,
                    "species_tag": 101,
                    "qn_format": 103,
                    "qn_upper": "1 0 1",
                    "qn_lower": "0 0 0",
                    "temperature_k": 300.0,
                    "provenance_hash": "sha256:test",
                }

        out_pq = tmp_path / "catalog_stream_test.parquet"
        final_pq = phase10.pyarrow_chunked_serializer(
            records_stream=record_gen(),
            output_parquet_path=out_pq,
            chunk_size=1000,
            compression="zstd",
        )
        assert final_pq.exists()
        meta = pq.read_metadata(final_pq)
        assert meta.num_rows == 5000

    def test_generate_methods_latex_aastex_compliance(self) -> None:
        """Verify AASTeX 6.3.1 and siunitx LaTeX computational methods generation."""
        meta = {
            "theory_level": "wB97X-D4",
            "basis_set": "def2-TZVP",
            "rotational_constants": {"A": 825360.0, "B": 435360.0, "C": 278130.0},
            "dipole_moments": {"mu_b": 1.8546},
            "temperatures": [300.0],
            "defgrid": "DEFGRID3",
        }
        tex = phase10.generate_methods_latex(meta, method_matrix_v4_check=True)
        assert r"\section{Computational Methods}" in tex
        assert r"\qty{825360.000}{\mega\hertz}" in tex
        assert "DEFGRID3" in tex

    def test_audit_banned_methods_rules(self) -> None:
        """Verify banned methods auditor rejects additive diffuse and unpreconditioned Hessian."""
        # 1. Banned additive diffuse
        bad_meta1 = {
            "theory_level": "B3LYP-D3BJ",
            "basis_set": "def2-TZVP",
            "additive_diffuse_correction": True,
        }
        with pytest.raises(MethodMatrixViolationError) as exc1:
            phase10.audit_banned_methods(bad_meta1, raise_on_violation=True)
        assert "BANNED_ADDITIVE_DIFFUSE" in str(exc1.value)

        # 2. Banned Calc_Hess true without preconditioning
        bad_meta2 = {
            "theory_level": "B3LYP-D3BJ",
            "basis_set": "def2-TZVP",
            "calc_hess_true": True,
            "hessian_preconditioned": False,
        }
        with pytest.raises(MethodMatrixViolationError) as exc2:
            phase10.audit_banned_methods(bad_meta2, raise_on_violation=True)
        assert "BANNED_UNPRECONDITIONED_HESSIAN" in str(exc2.value)

        # 3. Valid method with diffuse-in-base and InHess XTB2 preconditioning
        good_meta = {
            "theory_level": "wB97X-D4",
            "basis_set": "ma-def2-TZVPP",
            "keywords": "! wB97X-D4 ma-def2-TZVPP InHess XTB2",
            "is_non_covalent": True,
            "frozen_monomer": True,
            "counterpoise": True,
            "hessian_preconditioned": True,
        }
        res = phase10.audit_banned_methods(good_meta, raise_on_violation=True)
        assert res.passed is True
        assert res.is_frozen_monomer_verified is True
        assert res.is_bsse_counterpoise_verified is True
        assert res.is_valid_hessian_preconditioned is True

    def test_deduplicate_bibtex(self) -> None:
        """Verify BibTeX deduplication by cite key and normalized DOI."""
        raw_bib = """
@article{Pickett1991,
  author = {Pickett, Herbert M.},
  title = {The fitting and prediction of vibration-rotation spectra},
  journal = {J. Mol. Spectrosc.},
  year = {1991},
  doi = {10.1016/0022-2852(91)90124-S}
}

@article{pickett1991,
  author = {Pickett, H. M.},
  title = {Duplicate Key Entry},
  doi = {https://doi.org/10.1016/0022-2852(91)90124-S}
}

@article{Colbert1992,
  author = {Colbert, Daniel T. and Miller, William H.},
  title = {A novel discrete variable representation},
  journal = {J. Chem. Phys.},
  year = {1992},
  doi = {10.1063/1.462100}
}
"""
        dedup = phase10.deduplicate_bibtex(raw_bib)
        assert dedup.count("@article{Pickett1991") == 1
        assert dedup.count("Duplicate Key Entry") == 0
        assert dedup.count("@article{Colbert1992") == 1


# =============================================================================
# 6. Proxy Layer Integrity Tests
# =============================================================================

class TestProxyLayerIntegrity:
    """Verifies that all symbols are seamlessly re-exported from cochem_base package."""

    def test_cochem_base_tensor_extractor_proxy(self) -> None:
        """Verify cochem_base.cochem_tensor_extractor proxy symbols."""
        assert hasattr(proxy6, "diagonalize_inertia_tensor")
        assert hasattr(proxy6, "dynamic_representation_switch")
        assert hasattr(proxy6, "apply_cartesian_protections")
        assert hasattr(proxy6, "TorqTensorExtractor")
        assert proxy6.PLANCK_H == phase6.PLANCK_H

    def test_cochem_base_jax_builder_proxy(self) -> None:
        """Verify cochem_base.cochem_jax_builder proxy symbols."""
        assert hasattr(proxy7, "build_dvr_hamiltonian")
        assert hasattr(proxy7, "jit_eigen_solver")
        assert hasattr(proxy7, "nan_tensor_watchdog")
        assert hasattr(proxy7, "localized_vpt2_coupling")

    def test_cochem_base_spcat_bridge_proxy(self) -> None:
        """Verify cochem_base.cochem_spcat_bridge proxy symbols."""
        assert hasattr(proxy8, "low_frequency_lam_trap")
        assert hasattr(proxy8, "apply_symmetry_divisors")
        assert hasattr(proxy8, "vibrational_partition_coupling")
        assert hasattr(proxy8, "route_3tier_abinitio_payload")
        assert hasattr(proxy8, "ThreeTierRoutingResult")

    def test_cochem_base_torq_export_proxy(self) -> None:
        """Verify cochem_base.cochem_torq_export proxy symbols."""
        assert hasattr(proxy9_export, "calculate_kraitchman_coords")
        assert hasattr(proxy9_export, "lock_provenance_payload")
        assert hasattr(proxy9_export, "bundle_spycfit_payload")
        assert hasattr(proxy9_export, "generate_pgopher_skeleton")

    def test_cochem_base_torq_telemetry_proxy(self) -> None:
        """Verify cochem_base.cochem_torq_telemetry proxy symbols."""
        assert hasattr(proxy9_telemetry, "generate_plotly_3d_carousels")
        assert hasattr(proxy9_telemetry, "stream_webhook_events")
        assert hasattr(proxy9_telemetry, "export_crash_animation")

    def test_cochem_base_catalog_compiler_proxy(self) -> None:
        """Verify cochem_base.cochem_catalog_compiler proxy symbols."""
        assert hasattr(proxy10, "pyarrow_chunked_serializer")
        assert hasattr(proxy10, "generate_methods_latex")
        assert hasattr(proxy10, "audit_banned_methods")
        assert hasattr(proxy10, "deduplicate_bibtex")
        assert hasattr(proxy10, "apply_readonly_chmod")

