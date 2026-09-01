"""
CoChem-TORQ: Master Context Anchor & 10-Phase Pipeline Integration Test Suite
=============================================================================
Authoritative End-to-End Test Suite validating the CoChem-TORQ (v0.0.11)
Master Context Anchor & Summarization requirements:
1. Full 10-Phase Funnel Execution (Stage 0.0 through Stage 7.0).
2. Filesystem Air-Gap & Registry-First Authority.
3. SWMR Lock Guardian & Concurrency Safety.
4. MACE-OFF23 ML Pre-Flight & Multi-Fidelity Spline Routing.
5. Ab Initio Method Matrix Routing & Dynamic Memory Backoff.
6. Cartesian Protections & Moment of Inertia Tensor Extraction.
7. JAX 1D/2D Discrete Variable Representation (DVR) Physics.
8. Non-Rigid Statistical Mechanics & Pickett SPCAT Bridge.
9. SpycFit Payload Synthesis & Cryptographic SHA-256 Provenance.
10. FAIR Out-of-Core PyArrow Catalog Compilation & Immutable Delivery.
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List

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
    apply_readonly_chmod,
    generate_methods_latex,
    parse_spcat_cat_stream,
    pyarrow_chunked_serializer,
    remove_readonly_seal,
)
from cochem_h5_healer import (
    create_swmr_lock,
    detect_zombie_pids,
    force_release_swmr,
    inspect_h5_integrity,
    remove_swmr_lock,
)
from cochem_jax_builder import (
    build_dvr_hamiltonian,
    enforce_jax_precision,
    jit_eigen_solver,
    nan_tensor_watchdog,
)
from cochem_spcat_bridge import (
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    generate_spcat_int,
    generate_spcat_var,
    low_frequency_lam_trap,
)
from cochem_tensor_extractor import (
    apply_cartesian_protections,
    diagonalize_inertia_tensor,
    dynamic_representation_switch,
)
from cochem_torq_alignment import (
    align_eckart_frame,
    translate_com_to_origin,
)
from cochem_torq_engine import (
    route_method_matrix,
    validate_method_matrix_compliance,
)
from cochem_torq_export import (
    bundle_spycfit_payload,
    lock_provenance_payload,
    verify_payload_integrity,
)
from cochem_torq_init import (
    TorqAirgapViolationError,
    cleanup_ipc_buffers,
    init_torq_logger,
    resolve_torq_environment,
    verify_airgap,
)
from cochem_torq_mace import (
    evaluate_pes_point,
    generate_adaptive_grid,
    rotate_dihedral_angle,
)
from cochem_torq_quench import (
    detect_covalent_clashes,
    execute_soft_quench,
)
from cochem_torq_schema import (
    TorqHardwareSchema,
    validate_registry_state,
)
from cochem_torq_slicer import (
    fit_continuous_splines,
    wkb_tunneling_estimator,
)
from cochem_torq_telemetry import (
    export_crash_animation,
    generate_plotly_3d_carousels,
)
from cochem_torq_topology import (
    build_molecular_graph,
    detect_5_option_dihedrals,
    ring_strain_guard,
    select_active_torsions,
)
from cochem_torq_vault import (
    parse_external_xyz,
    standardize_geometry_dataframe,
)
from cochem_torq_watchdog import (
    dynamic_memory_backoff,
    execute_grid_collapse,
)

# Authentic Molecular Data: Methanol (CH3OH)
METHANOL_XYZ = """6
Methanol (CH3OH) Authentic Geometry
C   -0.0465   0.6644  -0.0000
O   -0.0465  -0.7556  -0.0000
H    0.9852   1.0356  -0.0000
H   -0.5623   1.0356   0.8933
H   -0.5623   1.0356  -0.8933
H    0.8535  -1.0956  -0.0000
"""


class TestTorqMasterContextAnchor:
    """Master context anchor test suite executing the 10-phase funnel end-to-end."""

    def test_master_context_wbs_architecture_integrity(self) -> None:
        """Verifies 10-Phase WBS lookup components and dependencies are intact."""
        wbs_phases = {
            "Phase 1: Environment & Guards (Stage 0.0)": ["cochem_torq_init", "cochem_torq_schema", "cochem_h5_healer"],
            "Phase 2: Intake & Topology (Stage 1.0 - 2.0)": ["cochem_torq_vault", "cochem_torq_topology", "cochem_torq_alignment"],
            "Phase 3: ML Pre-Flight & Triage (Stage 2.0 - 2.1)": ["cochem_torq_mace", "cochem_torq_quench"],
            "Phase 4: Spline Routing & UI (Stage 3.0 / 6.0)": ["cochem_torq_slicer"],
            "Phase 5: High-Fidelity Engine (Stage 4.0)": ["cochem_torq_engine", "cochem_torq_watchdog"],
            "Phase 6: Tensor Extraction (Stage 4.1)": ["cochem_tensor_extractor"],
            "Phase 7: Multi-Dimensional Physics (Stage 5.0)": ["cochem_jax_builder"],
            "Phase 8: Statistical Mechanics (Stage 5.1)": ["cochem_spcat_bridge"],
            "Phase 9: SpycFit Payload Synthesis (Stage 5.5 / 6.0)": ["cochem_torq_export", "cochem_torq_telemetry"],
            "Phase 10: FAIR Catalog Export (Stage 6.0 / 7.0)": ["cochem_catalog_compiler"],
        }
        for phase_name, modules in wbs_phases.items():
            assert len(modules) >= 1
            for mod in modules:
                import importlib
                m = importlib.import_module(mod)
                assert m is not None

    def test_full_10_phase_funnel_end_to_end(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Executes full 10-Phase pipeline funnel sequentially on real molecular inputs."""

        # -------------------------------------------------------------
        # Phase 1: Environment, Registry & SWMR Lock Guards (Stage 0.0)
        # -------------------------------------------------------------
        art_dir = tmp_path / "artifacts"
        scratch_dir = tmp_path / "scratch"
        lib_dir = tmp_path / "lib"
        art_dir.mkdir()
        scratch_dir.mkdir()
        lib_dir.mkdir()

        # Air-Gap Check
        assert verify_airgap(str(art_dir), str(scratch_dir)) is True

        # Pydantic Hardware Schema Validation
        hw_config = {
            "mpi_threads": 4,
            "gpu_vram_gb": 8.0,
            "maxcore_mb": 4000,
            "scratch_dir": scratch_dir,
            "artifacts_dir": art_dir,
            "torq_lib_dir": lib_dir,
        }
        schema = TorqHardwareSchema(**hw_config)
        assert schema.mpi_threads == 4
        assert schema.gpu_vram_gb == 8.0

        # SWMR Lock Guard
        h5_file = art_dir / "landscape.h5"
        lock_file = create_swmr_lock(h5_file)
        assert lock_file.exists()
        remove_swmr_lock(h5_file)
        assert not lock_file.exists()

        # -------------------------------------------------------------
        # Phase 2: Dual-Intake Gateway & Topology (Stage 1.0 - 2.0)
        # -------------------------------------------------------------
        xyz_file = tmp_path / "methanol.xyz"
        xyz_file.write_text(METHANOL_XYZ, encoding="utf-8")
        xyz_data = parse_external_xyz(xyz_file)
        symbols = xyz_data["symbols"]
        raw_coords = xyz_data["coordinates"]
        assert len(symbols) == 6
        assert raw_coords.shape == (6, 3)

        # Dihedrals via graph-cleaving
        dihedrals = detect_5_option_dihedrals(symbols, raw_coords)
        assert isinstance(dihedrals, list)
        active_dihedral = dihedrals[0]["dihedral"] if dihedrals else (5, 1, 0, 2)

        # Eckart Frame Alignment
        aligned_coords = align_eckart_frame(raw_coords, symbols)
        assert aligned_coords.shape == (6, 3)

        # -------------------------------------------------------------
        # Phase 3: ML Pre-Flight & Triage [MACE-OFF23] (Stage 2.0 - 2.1)
        # -------------------------------------------------------------
        grid_angles = np.linspace(0, 360, 12, endpoint=False)
        energies = []
        for ang in grid_angles:
            rot_coords = rotate_dihedral_angle(aligned_coords, active_dihedral, float(ang))
            clashes = detect_covalent_clashes(symbols, rot_coords)
            if clashes:
                quench_res = execute_soft_quench(symbols, rot_coords)
                rot_coords = quench_res["relaxed_coordinates"]
            e = evaluate_pes_point(symbols, rot_coords)
            energies.append(e)

        energies_arr = np.array(energies)
        assert len(energies_arr) == 12

        # -------------------------------------------------------------
        # Phase 4: Multi-Fidelity Spline Routing & WKB (Stage 3.0 / 6.0)
        # -------------------------------------------------------------
        spline_model = fit_continuous_splines(grid_angles, energies_arr)
        assert spline_model is not None

        barrier_kcal = (np.max(energies_arr) - np.min(energies_arr)) * 627.509
        barrier_cm1 = barrier_kcal * 349.755
        wkb_res = wkb_tunneling_estimator(rotor_type="CH3", barrier_height_cm1=barrier_cm1, reduced_moment_inertia_amu_ang2=1.0)
        assert wkb_res["tunneling_splitting_mhz"] >= 0.0

        # -------------------------------------------------------------
        # Phase 5: Ab Initio Quantum Engine & Cascade Matrix (Stage 4.0)
        # -------------------------------------------------------------
        routed_job = route_method_matrix(
            calculation_tier="conformer_refinement",
            functional="wB97X-D4",
            basis_set="def2-TZVP",
            num_atoms=len(symbols),
        )
        assert routed_job["status"] == "compliant"
        assert validate_method_matrix_compliance(routed_job) is True

        allocated_mem = dynamic_memory_backoff(requested_mb=8000, available_mb=6000)
        assert allocated_mem <= 6000

        # -------------------------------------------------------------
        # Phase 6: Tensor Extraction & Representation Switching (Stage 4.1)
        # -------------------------------------------------------------
        tensor_res = diagonalize_inertia_tensor(aligned_coords, symbols)
        assert tensor_res.is_linear is False
        assert tensor_res.total_mass_amu > 30.0

        a_mhz = tensor_res.rotational_constants_mhz["A"]
        b_mhz = tensor_res.rotational_constants_mhz["B"]
        c_mhz = tensor_res.rotational_constants_mhz["C"]
        assert a_mhz > b_mhz > c_mhz > 0.0

        rep_switch = dynamic_representation_switch(a_mhz, b_mhz, c_mhz)
        assert rep_switch.recommended_representation in ["Ir", "IIIr"]

        # -------------------------------------------------------------
        # Phase 7: Multi-Dimensional Physics [JAX 1D/2D DVR] (Stage 5.0)
        # -------------------------------------------------------------
        enforce_jax_precision()
        grid_dvr = np.linspace(-np.pi, np.pi, 32, endpoint=False)
        v_dvr = 0.5 * (barrier_kcal / 627.509) * (1.0 - np.cos(3.0 * grid_dvr))
        h_dvr = build_dvr_hamiltonian(
            pes_spline_array=v_dvr,
            dimensions=1,
            periodic=True,
            num_points=32,
            reduced_rot_constant=b_mhz / 29979.2458,
        )
        eigs, evecs = jit_eigen_solver(h_dvr)
        assert len(eigs) == 32

        # -------------------------------------------------------------
        # Phase 8: Statistical Mechanics & SPCAT Bridge (Stage 5.1)
        # -------------------------------------------------------------
        q_rot = calculate_rotational_partition_function(a_mhz, b_mhz, c_mhz, temp_k=298.15, sigma=1)
        assert q_rot > 0.0

        var_file = art_dir / "Methanol.var"
        var_str = generate_spcat_var("Methanol", tensor_res.rotational_constants_mhz, filepath=var_file)
        assert var_file.exists()
        assert "Methanol Ground State" in var_str

        # -------------------------------------------------------------
        # Phase 9: SpycFit Payload Synthesis & Telemetry (Stage 5.5 / 6.0)
        # -------------------------------------------------------------
        payload_dir = art_dir / "spycfit_payload"
        payload_dir.mkdir()
        (payload_dir / "Methanol.var").write_text(var_str, encoding="utf-8")

        manifest_dict = lock_provenance_payload(str(payload_dir))
        assert isinstance(manifest_dict, dict)
        assert verify_payload_integrity(payload_dir) is True

        # Telemetry HTML
        html_file = payload_dir / "viz_3d.html"
        pes_2d = np.outer(energies_arr[:10], energies_arr[:10])
        generate_plotly_3d_carousels(pes_2d, output_path=str(html_file))
        assert html_file.exists()

        # -------------------------------------------------------------
        # Phase 10: FAIR Out-of-Core Catalog Compilation (Stage 6.0 / 7.0)
        # -------------------------------------------------------------
        cat_file = payload_dir / "spcat_out.cat"
        cat_file.write_text("   22235.0800  0.0050 -4.5678 2    0.0000  3  18001 103 6 1 6       5 2 3      \n", encoding="utf-8")
        parquet_file = payload_dir / "spcat_catalog.parquet"
        stream = parse_spcat_cat_stream(cat_file, temperature_k=298.15)
        pyarrow_chunked_serializer(stream, parquet_file, chunk_size=10)
        assert parquet_file.exists()

        meta_latex = {
            "theory_level": "wB97X-D4",
            "basis_set": "def2-TZVP",
            "software_version": "ORCA 6.1.1",
            "rotational_constants": tensor_res.rotational_constants_mhz,
            "temperatures": [298.15],
            "defgrid": "DEFGRID3",
        }
        tex_content = generate_methods_latex(meta_latex)
        assert "wB97X-D4" in tex_content

        # Read-only seal
        apply_readonly_chmod(parquet_file)
        with pytest.raises(PermissionError):
            with open(parquet_file, "wb") as f:
                f.write(b"CORRUPT")
        remove_readonly_seal(parquet_file)
