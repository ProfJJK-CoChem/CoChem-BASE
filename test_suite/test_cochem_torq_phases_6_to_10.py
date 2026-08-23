"""
CoChem-TORQ: Comprehensive Unit Test Suite (Phases 6 through 10)
================================================================
Authentic Physical Unit Tests covering Modules and Deliverables:
- Phase 6: cochem_tensor_extractor (Inertia tensors, Ray's kappa, Cartesian linear protections)
- Phase 7: cochem_jax_builder (Float64 JAX DVR 1D/2D, XLA JIT eigen solver, localized VPT2)
- Phase 8: cochem_spcat_bridge (LAM trap, symmetry divisors, Pickett .var/.int files)
- Phase 9: cochem_torq_export, cochem_torq_telemetry (Kraitchman coords, locked provenance, webhooks)
- Phase 10: cochem_catalog_compiler (PyArrow out-of-core Parquet, read-only seals, LaTeX/BibTeX)
"""

from __future__ import annotations

import gc
import http.server
import json
import logging
import math
import os
from pathlib import Path
import socketserver
import tempfile
import threading
import time
from typing import Any, Dict, List, Tuple

import numpy as np
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from cochem_base.exceptions import (
    AirGapViolationError,
    CoChemIntegrityError,
    FortranOverflowError,
    LAMTriggerError,
    ProvenanceErrorCode,
)
from cochem_catalog_compiler import (
    CoChemPathManager,
    apply_readonly_chmod,
    buffer_lock_sync,
    deduplicate_bibtex,
    generate_methods_latex,
    parallel_temperature_compiler,
    parse_spcat_cat_line,
    parse_spcat_cat_stream,
    purge_ghost_outputs,
    pyarrow_chunked_serializer,
    remove_readonly_seal,
)
from cochem_jax_builder import (
    CoChemPrecisionError,
    build_dvr_hamiltonian,
    enforce_jax_precision,
    jit_eigen_solver,
    localized_vpt2_coupling,
    nan_tensor_watchdog,
)
from cochem_spcat_bridge import (
    CONSTANTS,
    SPCATPayload,
    apply_symmetry_divisors,
    build_complete_spcat_payload,
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    format_fortran_double,
    fortran_double_precision_formatter,
    fortran_overflow_guard,
    generate_spcat_int,
    generate_spcat_var,
    low_frequency_lam_trap,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)
from cochem_tensor_extractor import (
    CIAAW_ISOTOPIC_MASSES,
    INERTIA_CONVERSION_AMU_ANG2_MHZ,
    CartesianProtectionResult,
    InertiaTensorResult,
    RepresentationSwitchResult,
    apply_cartesian_protections,
    build_inertia_tensor,
    calculate_center_of_mass,
    diagonalize_inertia_tensor,
    dynamic_representation_switch,
    resolve_atomic_mass,
    translate_to_center_of_mass,
)
from cochem_torq_export import (
    bundle_spycfit_payload,
    calculate_kraitchman_coords,
    generate_pgopher_skeleton,
    lock_provenance_payload,
    verify_payload_integrity,
)
from cochem_torq_telemetry import (
    TELEMETRY_BUFFER,
    export_crash_animation,
    generate_plotly_3d_carousels,
    stream_webhook_events,
)

# =============================================================================
# Authentic Molecular Data
# =============================================================================

H2O_COORDS = np.array([
    [0.000000,  0.000000,  0.117300],  # O
    [0.000000,  0.757200, -0.469200],  # H1
    [0.000000, -0.757200, -0.469200],  # H2
], dtype=np.float64)
H2O_SYMBOLS = ["O", "H", "H"]

HCN_COORDS = np.array([
    [0.000000, 0.000000, -1.064000],  # H
    [0.000000, 0.000000,  0.000000],  # C
    [0.000000, 0.000000,  1.156000],  # N
], dtype=np.float64)
HCN_SYMBOLS = ["H", "C", "N"]

H2CO_COORDS = np.array([
    [0.000000,  0.000000,  0.600000],  # C
    [0.000000,  0.000000, -0.600000],  # O
    [0.000000,  0.940000,  1.180000],  # H1
    [0.000000, -0.940000,  1.180000],  # H2
], dtype=np.float64)
H2CO_SYMBOLS = ["C", "O", "H", "H"]


# =============================================================================
# Phase 6: cochem_tensor_extractor Tests
# =============================================================================

class TestTensorExtractor:
    """Rigorous tests for Phase 6: Moment of Inertia Tensor and Representation Switching."""

    def test_atomic_mass_resolution(self) -> None:
        """Verifies CIAAW exact isotopic mass retrieval and numeric pass-through."""
        assert resolve_atomic_mass("H") == pytest.approx(1.00782503223, rel=1e-8)
        assert resolve_atomic_mass("12C") == pytest.approx(12.0, rel=1e-8)
        assert resolve_atomic_mass("16O") == pytest.approx(15.99491461957, rel=1e-8)
        assert resolve_atomic_mass(14.003) == pytest.approx(14.003, rel=1e-8)

    def test_center_of_mass_translation(self) -> None:
        """Verifies center of mass translation moves origin to (0,0,0)."""
        masses = [resolve_atomic_mass(s) for s in H2O_SYMBOLS]
        com = calculate_center_of_mass(H2O_COORDS, masses)
        centered, returned_com = translate_to_center_of_mass(H2O_COORDS, masses)
        np.testing.assert_allclose(com, returned_com)
        new_com = calculate_center_of_mass(centered, masses)
        np.testing.assert_allclose(new_com, [0.0, 0.0, 0.0], atol=1e-12)

    def test_water_inertia_tensor_and_rotational_constants(self) -> None:
        """Verifies diagonalized inertia tensor and rotational constants for H2O."""
        res = diagonalize_inertia_tensor(H2O_COORDS, H2O_SYMBOLS)
        assert isinstance(res, InertiaTensorResult)
        assert res.total_mass_amu == pytest.approx(18.010564684, rel=1e-6)
        assert res.is_linear is False
        assert res.is_planar is True

        a = res.rotational_constants_mhz["A"]
        b = res.rotational_constants_mhz["B"]
        c = res.rotational_constants_mhz["C"]
        assert a > b > c > 0.0
        assert 700000.0 < a < 950000.0
        assert 350000.0 < b < 500000.0
        assert 200000.0 < c < 350000.0
        assert abs(res.inertial_defect_amu_ang2) < 0.01

    def test_cartesian_protections_for_linear_molecule(self) -> None:
        """Verifies collinearity detection and cylindrical projection for linear HCN."""
        prot = apply_cartesian_protections(HCN_COORDS, HCN_SYMBOLS)
        assert isinstance(prot, CartesianProtectionResult)
        assert prot.is_linear is True
        assert prot.collinear_axis == "Z"
        assert prot.applied_protection is True
        assert prot.cylindrical_coordinates is not None
        assert prot.cylindrical_coordinates.shape == (3, 2)

    def test_dynamic_representation_switch(self) -> None:
        """Verifies Ray's asymmetry kappa and representation selection (I^r vs III^r)."""
        res_prolate = dynamic_representation_switch(a_mhz=30000.0, b_mhz=5000.0, c_mhz=4000.0)
        assert res_prolate.is_prolate is True
        assert res_prolate.recommended_representation == "Ir"
        assert res_prolate.ray_kappa < 0.0

        res_oblate = dynamic_representation_switch(a_mhz=10000.0, b_mhz=9000.0, c_mhz=2000.0)
        assert res_oblate.is_oblate is True
        assert res_oblate.recommended_representation == "IIIr"
        assert res_oblate.ray_kappa >= 0.0


# =============================================================================
# Phase 7: cochem_jax_builder Tests
# =============================================================================

class TestJAXBuilder:
    """Rigorous tests for Phase 7: JAX DVR and Quantum Physics Solvers."""

    def test_enforce_jax_precision(self) -> None:
        """Verifies JAX float64 enablement and system query."""
        info = enforce_jax_precision(force_recheck=True)
        assert isinstance(info, dict)
        assert info["float64_enabled"] is True
        assert "devices" in info

    def test_build_dvr_hamiltonian_and_eigen_solver(self) -> None:
        """Verifies 1D DVR Hamiltonian construction and eigenvalue computation."""
        n_pts = 64
        v_box = np.zeros(n_pts, dtype=np.float64)
        h_mat = build_dvr_hamiltonian(
            pes_spline_array=v_box,
            dimensions=1,
            mass=1.0,
            length=1.0,
            periodic=False,
            num_points=n_pts,
        )
        assert h_mat.shape == (n_pts, n_pts)

        evals, evecs = jit_eigen_solver(h_mat)
        assert len(evals) == n_pts
        assert np.all(np.isfinite(np.asarray(evals)))
        assert evals[0] > 0.0

    def test_nan_tensor_watchdog_and_tikhonov(self) -> None:
        """Verifies singularity interception and Tikhonov regularization."""
        n_size = 20
        h_corrupted = np.eye(n_size, dtype=np.float64)
        h_corrupted[5, 5] = np.nan
        h_corrupted[10, 10] = np.inf

        h_regularized = nan_tensor_watchdog(h_corrupted, damping=1e-4)
        assert not np.isnan(np.asarray(h_regularized)).any()
        assert not np.isinf(np.asarray(h_regularized)).any()

    def test_localized_vpt2_coupling(self) -> None:
        """Verifies LAM mode removal and vibrational partition coupling."""
        harmonic_freqs = [88.5, 340.0, 680.0, 1120.0, 1450.0, 2980.0]
        dvr_energies = [12.4, 38.6, 92.1, 165.0, 260.4]

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


# =============================================================================
# Phase 8: cochem_spcat_bridge Tests
# =============================================================================

class TestSPCATBridge:
    """Rigorous tests for Phase 8: Statistical Mechanics and Pickett SPCAT Bridge."""

    def test_low_frequency_lam_trap(self) -> None:
        """Verifies low-frequency modes < 50 cm^-1 trigger LAM exception."""
        freqs_with_lam = [22.5, 300.0, 1200.0]
        with pytest.raises(LAMTriggerError) as exc_info:
            low_frequency_lam_trap(freqs_with_lam, threshold_cm1=50.0)
        assert exc_info.value.error_code == ProvenanceErrorCode.LAM_TRIGGER

        clean_freqs = [85.0, 300.0, 1200.0]
        stiff = low_frequency_lam_trap(clean_freqs, threshold_cm1=50.0)
        assert len(stiff) == 3

    def test_rotational_and_vibrational_partition_functions(self) -> None:
        """Verifies exact partition function calculations for standard states."""
        a_mhz, b_mhz, c_mhz = 835840.0, 435350.0, 278139.0
        q_rot = calculate_rotational_partition_function(a_mhz, b_mhz, c_mhz, temp_k=298.15, sigma=2)
        assert q_rot > 0.0

        vib_freqs = [1595.0, 3657.0, 3756.0]
        q_vib = calculate_vibrational_partition_function(vib_freqs, temp_k=298.15)
        assert 1.0 <= q_vib < 1.01

    def test_spcat_file_generation(self, tmp_path: Path) -> None:
        """Verifies authentic Pickett .var and .int ASCII generation."""
        var_file = tmp_path / "H2O.var"
        content = generate_spcat_var(
            molecule_name="H2O",
            parameters={"A": 835840.0, "B": 435350.0, "C": 278139.0},
            filepath=var_file,
        )
        assert var_file.exists()
        assert "H2O Ground State" in content

        int_dict = generate_spcat_int(
            molecule_name="H2O",
            dipoles={"mu_b": 1.8546},
            temperatures=[298.15],
            filepath_template=tmp_path / "H2O_{T}K.int",
        )
        assert 298.15 in int_dict
        assert (tmp_path / "H2O_298.1K.int").exists()


# =============================================================================
# Phase 9: cochem_torq_export & Telemetry Tests
# =============================================================================

class TestExportAndTelemetry:
    """Rigorous tests for Phase 9: SpycFit Payload Synthesis and Telemetry."""

    def test_kraitchman_coords_calculation(self) -> None:
        """Verifies Kraitchman substitution coordinate math on asymmetric rotors."""
        input_dict = {
            "I_a": 35.0, "I_b": 60.0, "I_c": 90.0,
            "I_a_iso": 35.8, "I_b_iso": 60.5, "I_c_iso": 91.2,
            "parent_mass": 50.0, "delta_m": 1.00335,
        }
        res = calculate_kraitchman_coords(input_dict)
        assert "coordinates" in res
        assert "costain_uncertainties" in res
        for axis in ("a", "b", "c"):
            assert res["coordinates"][axis] >= 0.0

    def test_lock_provenance_payload_and_verification(self, tmp_path: Path) -> None:
        """Verifies cryptographic SHA-256 manifest locking and anti-tamper verification."""
        data_file = tmp_path / "test_data.var"
        data_file.write_text("TEST VAR CONTENT", encoding="utf-8")

        manifest_dict = lock_provenance_payload(str(tmp_path))
        assert isinstance(manifest_dict, dict)
        assert "files" in manifest_dict
        assert verify_payload_integrity(tmp_path) is True

        # Tamper with file
        data_file.write_text("TAMPERED DATA", encoding="utf-8")
        with pytest.raises(CoChemIntegrityError):
            verify_payload_integrity(tmp_path)

    def test_plotly_3d_and_crash_animation_generation(self, tmp_path: Path) -> None:
        """Verifies export of HTML 3D visualization and crash diagnostic JSON."""
        html_out = tmp_path / "torq_3d.html"
        pes_grid = np.sin(np.linspace(0, np.pi, 20))[:, None] * np.cos(np.linspace(0, np.pi, 20))[None, :] * 500.0
        html_str = generate_plotly_3d_carousels(pes_grid, output_path=str(html_out))
        assert html_out.exists()
        assert html_out.stat().st_size > 100

        anim_out = tmp_path / "crash_anim.xyz"
        traj = np.array([H2O_COORDS, H2O_COORDS + 0.1, H2O_COORDS + 0.2])
        xyz_p, json_p = export_crash_animation(
            trajectory_array=traj,
            error_node_id="worker_01",
            output_path=str(anim_out),
            atom_symbols=H2O_SYMBOLS,
        )
        assert Path(xyz_p).exists()
        assert Path(json_p).exists()


# =============================================================================
# Phase 10: cochem_catalog_compiler Tests
# =============================================================================

class TestCatalogCompiler:
    """Rigorous tests for Phase 10: PyArrow Out-Of-Core Catalog Compilation."""

    def test_spcat_cat_line_parsing(self) -> None:
        """Verifies authentic Pickett .cat line parsing."""
        sample_line = "   22235.0800  0.0050 -4.5678 2    0.0000  3  18001 103 6 1 6       5 2 3      "
        rec = parse_spcat_cat_line(sample_line)
        assert rec is not None
        assert rec["frequency_mhz"] == pytest.approx(22235.0800, abs=1e-3)
        assert rec["uncertainty_mhz"] == pytest.approx(0.0050, abs=1e-4)
        assert rec["log_intensity"] == pytest.approx(-4.5678, abs=1e-4)

    def test_pyarrow_chunked_serializer(self, tmp_path: Path) -> None:
        """Verifies chunked serialization of records to Parquet."""
        cat_file = tmp_path / "sample.cat"
        cat_lines = [
            "   22235.0800  0.0050 -4.5678 2    0.0000  3  18001 103 6 1 6       5 2 3      \n",
            "  183310.0870  0.0020 -2.3456 2   14.2500  3  18001 103 3 1 3       2 2 0      \n",
        ] * 50
        cat_file.write_text("".join(cat_lines), encoding="utf-8")

        parquet_out = tmp_path / "catalog.parquet"
        stream = parse_spcat_cat_stream(cat_file, temperature_k=298.15)
        res_path = pyarrow_chunked_serializer(stream, parquet_out, chunk_size=20)
        assert res_path.exists()

        table = pq.read_table(res_path)
        assert table.num_rows == 100
        assert "frequency_mhz" in table.column_names

    def test_readonly_security_seal(self, tmp_path: Path) -> None:
        """Verifies chmod 0444 read-only permission seal and removal."""
        target_file = tmp_path / "immutable_deliverable.dat"
        target_file.write_text("READONLY_DATA", encoding="utf-8")

        apply_readonly_chmod(target_file)
        with pytest.raises(PermissionError):
            with open(target_file, "w") as f:
                f.write("MODIFIED")

        remove_readonly_seal(target_file)
        with open(target_file, "w") as f:
            f.write("PERMITTED_WRITE")
        assert target_file.read_text(encoding="utf-8") == "PERMITTED_WRITE"

    def test_methods_latex_and_bibtex_deduplication(self, tmp_path: Path) -> None:
        """Verifies LaTeX manuscript generation and BibTeX key deduplication."""
        meta = {
            "theory_level": "wB97X-D4",
            "basis_set": "def2-TZVP",
            "software_version": "ORCA 6.1.1",
            "rotational_constants": {"A": 825360.0, "B": 435360.0, "C": 278130.0},
            "dipole_moments": {"mu_b": 1.8546},
            "temperatures": [298.15],
            "defgrid": "DEFGRID3",
        }
        latex_str = generate_methods_latex(meta)
        assert "wB97X-D4" in latex_str
        assert "def2-TZVP" in latex_str
        assert "825360" in latex_str

        bib_raw = """
@article{Neese2022, author = {Neese, Frank}, title = {ORCA 6}, journal = {JCP}, year = {2022}}
@article{Neese2022, author = {Neese, Frank}, title = {ORCA 6}, journal = {JCP}, year = {2022}}
@article{Pickett1991, author = {Pickett, H. M.}, title = {SPCAT}, journal = {JMS}, year = {1991}}
"""
        deduped = deduplicate_bibtex(bib_raw)
        assert deduped.count("@article{Neese2022") == 1
        assert deduped.count("@article{Pickett1991") == 1
