#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit Test Suite for CoChem Integration Grid Convergence & Rotational Invariance Analyzer.
Module: tests/test_cochem_grid_convergence.py
Target: calc/cochem_grid_convergence.py

Authoritative Standards:
- Method Matrix v4 §4.1, §4.4, §4.5 (Rigid-Rotor Observables & Inertia Tensors)
- Method Matrix v4 §16.1 (2) (Grid Non-Invariance Under Rotation & Soft-Mode Gates)
- Method Matrix v4 §16.2 & §16.3 (Convergence Gates & Rejection Triggers)
- Method Matrix v4 §19.2 (Grid & Threshold Sensitivity Quantification)
- Method Matrix v4 §21.3 Roadmap Item 5 (Grid-Convergence Line Item)
- Mendeleev Library Mandate (Dynamic Mass Retrieval)
- Zero-Mock & Anti-Spoofing Protocol v3
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import List

import h5py
import numpy as np
import pytest

from calc.cochem_grid_convergence import (
    CONV_MHZ_AMU_ANG2,
    GRID_DELTA_B_PCT_TOLERANCE,
    GRID_DELTA_R_TOLERANCE_ANGSTROM,
    GRID_ENERGY_TOLERANCE_EH,
    ROTATION_DELTA_B_PCT_TOLERANCE,
    ROTATION_ENERGY_TOLERANCE_EH,
    SOFT_MODE_FREQUENCY_THRESHOLD_CM1,
    SOFT_MODE_SHIFT_TOLERANCE_CM1,
    GridCalculationResult,
    GridConvergenceAnalyzer,
    GridConvergenceReport,
    GridConvergenceStep,
    GridRotationInvarianceResult,
    apply_rotation_to_coordinates,
    auto_partition_dimer,
    build_euler_rotation_matrix,
    compute_center_of_mass,
    compute_inertia_tensor,
    compute_inertial_defect,
    compute_intermolecular_distances,
    compute_planar_moments,
    compute_ray_kappa,
    compute_rotational_constants,
    diagonalize_inertia_tensor,
    execute_grid_convergence_benchmark,
    generate_orca_grid_study_input,
    get_canonical_reference_system,
    get_dynamic_atomic_mass,
    get_element_masses,
    main,
    parse_orca_output_for_grid_metrics,
    render_markdown_summary,
    save_report_to_hdf5,
    save_report_to_json,
)


class TestMendeleevDynamicMasses:
    """Verifies compliance with the Mendeleev Library Mandate."""

    def test_dynamic_mass_retrieval(self) -> None:
        h_mass = get_dynamic_atomic_mass("H")
        c_mass = get_dynamic_atomic_mass("C")
        o_mass = get_dynamic_atomic_mass("O")
        ar_mass = get_dynamic_atomic_mass("Ar")

        assert 1.007 < h_mass < 1.009
        assert 12.010 < c_mass < 12.012
        assert 15.998 < o_mass < 16.001
        assert 39.94 < ar_mass < 39.96

    def test_isotopic_mass_retrieval(self) -> None:
        d_mass = get_dynamic_atomic_mass("D")
        c13_mass = get_dynamic_atomic_mass("C", mass_number=13)
        assert 2.014 < d_mass < 2.015
        assert 13.003 < c13_mass < 13.004

    def test_element_masses_sequence(self) -> None:
        masses = get_element_masses(["H", "O", "H"])
        assert len(masses) == 3
        assert pytest.approx(masses[0], rel=1e-3) == 1.008
        assert pytest.approx(masses[1], rel=1e-3) == 15.999
        assert pytest.approx(masses[2], rel=1e-3) == 1.008


class TestRigidRotorSpectroscopyEngine:
    """Verifies rigid rotor physics, inertia tensors, and spectroscopic constants."""

    def test_center_of_mass_water(self) -> None:
        coords = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692]
        ])
        masses = np.array([15.9994, 1.008, 1.008])
        com = compute_center_of_mass(coords, masses)
        assert com.shape == (3,)
        assert abs(com[0]) < 1e-6
        assert abs(com[1]) < 1e-6
        assert abs(com[2]) < 0.1

    def test_inertia_tensor_and_constants_linear(self) -> None:
        # Linear CO2 along z-axis
        coords = np.array([
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.16],
            [0.0, 0.0, -1.16]
        ])
        masses = np.array([12.011, 15.9994, 15.9994])
        I_tensor = compute_inertia_tensor(coords, masses)
        principal_moments, _ = diagonalize_inertia_tensor(I_tensor)

        # In linear molecule, Ia ≈ 0, Ib = Ic
        assert principal_moments[0] < 1e-6
        assert pytest.approx(principal_moments[1], rel=1e-4) == principal_moments[2]

    def test_planar_moments_and_inertial_defect(self) -> None:
        # Planar water monomer
        coords = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692]
        ])
        masses = np.array([15.9994, 1.008, 1.008])
        I_tensor = compute_inertia_tensor(coords, masses)
        principal_moments, _ = diagonalize_inertia_tensor(I_tensor)
        Ia, Ib, Ic = principal_moments

        defect = compute_inertial_defect(Ia, Ib, Ic)
        Paa, Pbb, Pcc = compute_planar_moments(Ia, Ib, Ic)

        # Planar molecule in xy-plane has Delta ≈ 0 and Pcc ≈ 0
        assert abs(defect) < 1e-4
        assert abs(Pcc) < 1e-4

        A, B, C = compute_rotational_constants(principal_moments)
        assert A >= B >= C
        kappa = compute_ray_kappa(A, B, C)
        assert -1.0 <= kappa <= 1.0


class TestRotationalInvarianceEngine:
    """Verifies 3D Euler rotations and invariance checks (§16.1 (2))."""

    def test_euler_rotation_matrix_orthonormality(self) -> None:
        R = build_euler_rotation_matrix(45.0, 30.0, 60.0)
        assert R.shape == (3, 3)
        # Check R @ R.T == I
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
        assert np.allclose(np.linalg.det(R), 1.0, atol=1e-12)

    def test_coordinate_rotation_preserves_interatomic_distances(self) -> None:
        coords = np.array([
            [1.485, 0.0, -0.057],
            [1.882, 0.758, 0.421],
            [1.882, -0.758, 0.421],
            [-1.486, 0.0, 0.062],
            [-0.525, 0.0, -0.071],
            [-1.758, 0.0, 0.984]
        ])
        R = build_euler_rotation_matrix(30.0, 45.0, 60.0)
        rot_coords = apply_rotation_to_coordinates(coords, R, center_at_com=True)

        d_orig = np.linalg.norm(coords[0] - coords[3])
        d_rot = np.linalg.norm(rot_coords[0] - rot_coords[3])
        assert pytest.approx(d_orig, abs=1e-10) == d_rot


class TestIntermolecularPartitioning:
    """Verifies automatic dimer partitioning and distance calculations."""

    def test_auto_partition_water_dimer(self) -> None:
        coords = np.array([
            [ 1.485,  0.000, -0.057],
            [ 1.882,  0.758,  0.421],
            [ 1.882, -0.758,  0.421],
            [-1.486,  0.000,  0.062],
            [-0.525,  0.000, -0.071],
            [-1.758,  0.000,  0.984]
        ])
        elements = ["O", "H", "H", "O", "H", "H"]
        m1, m2 = auto_partition_dimer(elements, coords)
        assert len(m1) == 3
        assert len(m2) == 3
        assert set(m1 + m2) == set(range(6))

    def test_intermolecular_distances(self) -> None:
        coords = np.array([
            [ 1.485,  0.000, -0.057],
            [ 1.882,  0.758,  0.421],
            [ 1.882, -0.758,  0.421],
            [-1.486,  0.000,  0.062],
            [-0.525,  0.000, -0.071],
            [-1.758,  0.000,  0.984]
        ])
        masses = np.array(get_element_masses(["O", "H", "H", "O", "H", "H"]))
        r_min, r_cm, pair = compute_intermolecular_distances(coords, masses, [0, 1, 2], [3, 4, 5])

        assert 1.9 < r_min < 2.1
        assert 2.9 < r_cm < 3.1
        assert pair == (0, 4)  # O(donor acceptor) ... H contact


class TestOrcaIO:
    """Verifies ORCA input deck generation and output parsing."""

    def test_generate_orca_input_with_section44_block(self) -> None:
        coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        inp = generate_orca_grid_study_input(
            basin_id="test_basin",
            elements=["O", "H"],
            coords=coords,
            grid_keyword="DefGrid3",
            is_opt=True
        )
        assert "! wB97X-V def2-TZVPP def2/J RIJCOSX TightOpt DefGrid3 TightSCF NoSym" in inp
        assert "%geom" in inp
        assert "TolE 1e-7" in inp
        assert "TolMaxG 1e-5" in inp
        assert "InHess XTB2" in inp

    def test_parse_orca_output(self) -> None:
        mock_output = """
        FINAL SINGLE POINT ENERGY      -152.8846014000
        SCF CONVERGED AFTER 12 CYCLES
        MAX gradient      0.00000450
        RMS gradient      0.00000120
        -----------------------
        VIBRATIONAL FREQUENCIES
        -----------------------
           0:      0.00 cm**-1
           1:      0.00 cm**-1
           2:      0.00 cm**-1
           3:      0.00 cm**-1
           4:      0.00 cm**-1
           5:      0.00 cm**-1
           6:    142.50 cm**-1
           7:    165.20 cm**-1
        NORMAL MODES
        ---------------------------------
        CARTESIAN COORDINATES (ANGSTROEM)
        ---------------------------------
          O     1.4850200   0.0000000  -0.0571500
          H     1.8823500   0.7581200   0.4213500
          H     1.8823500  -0.7581200   0.4213500
          O    -1.4861200   0.0000000   0.0623800
          H    -0.5255400   0.0000000  -0.0717500
          H    -1.7580200   0.0000000   0.9840500
        ---------------------------------
        """
        metrics = parse_orca_output_for_grid_metrics(mock_output)
        assert metrics["energy_hartree"] == -152.8846014
        assert metrics["scf_converged"] is True
        assert metrics["max_gradient"] == 4.5e-6
        assert len(metrics["harmonic_frequencies"]) == 8
        assert metrics["optimized_coords"] is not None
        assert len(metrics["elements"]) == 6


class TestGridConvergenceEndToEnd:
    """Verifies end-to-end grid convergence benchmark execution across canonical systems."""

    @pytest.mark.parametrize("system_name", ["water_dimer", "co2_h2o", "ar_ketene"])
    def test_canonical_system_benchmarks(self, tmp_path: Path, system_name: str) -> None:
        report = execute_grid_convergence_benchmark(
            system_name=system_name,
            output_dir=tmp_path,
            test_rotation=True
        )

        assert isinstance(report, GridConvergenceReport)
        assert report.method_matrix_compliant is True
        assert len(report.convergence_steps) >= 2
        assert len(report.rotation_invariance_audits) == 2

        # Check target step (DEFGRID2 -> DEFGRID3)
        target_step = report.convergence_steps[-1]
        assert target_step.baseline_grid == "DEFGRID2"
        assert target_step.target_grid == "DEFGRID3"
        assert target_step.passed_energy_gate is True
        assert target_step.passed_geometry_gate is True
        assert target_step.passed_rotational_gate is True

        # Check rotation audits
        for rot in report.rotation_invariance_audits:
            assert rot.passed_rotational_invariance_gate is True

        # Verify artifacts exist on disk
        json_file = tmp_path / f"{report.complex_name}_grid_convergence.json"
        h5_file = tmp_path / f"{report.complex_name}_grid_convergence.h5"
        md_file = tmp_path / f"{report.complex_name}_grid_convergence.md"

        assert json_file.exists()
        assert h5_file.exists()
        assert md_file.exists()

        # Check JSON roundtrip
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["complex_name"] == report.complex_name
            assert data["method_matrix_compliant"] is True

        # Check HDF5 structure
        with h5py.File(h5_file, "r") as h5f:
            grp = h5f[f"grid_convergence/{report.complex_name}"]
            assert bool(grp.attrs["method_matrix_compliant"]) is True
            assert "DEFGRID3" in grp
            assert "coordinates" in grp["DEFGRID3"]
            assert "masses" in grp["DEFGRID3"]

        # Check Markdown content
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()
            assert "COMPLIANT" in md_text
            assert "DEFGRID3" in md_text

    def test_cli_execution(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        test_args = [
            "cochem_grid_convergence.py",
            "--system", "water_dimer",
            "--outdir", str(tmp_path),
            "--audit"
        ]
        monkeypatch.setattr("sys.argv", test_args)
        exit_code = main()
        assert exit_code == 0
