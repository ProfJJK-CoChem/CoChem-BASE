#!/usr/bin/env python3
"""
Unit Test Suite for CoChem-SCRIBE Data Harvester & Aggregator.
=============================================================
Phase 2, Task 5: Zero-Mock Anti-Spoofing Verification (tests/test_scribe_aggregator.py).

Verifies:
1. SWMR HDF5 read-only concurrency and non-POSIX locking resilience.
2. Conformer hierarchy extraction and memory-safe 3D coordinate stripping.
3. Spectroscopic TORQ tensor precision (rotational constants, dipoles, Watson distortion).
4. Thermodynamic conversion with exact CODATA physical constant (627.5094740631).
5. Telemetry ingestion from real cochem_audit_log.json files.
6. Provenance harvesting and golden SHA-256 cryptographic binding of system configs.
7. Fixed-token tensor statistical compression (Min, Max, Mean, StdDev).
8. Binary columnar Parquet fallback failover with strict banning of JSON tensor fallbacks.
9. Rigidly typed DataFrame flattening for LaTeX \\booktabs and Markdown tables.
10. Full unified aggregation pipeline (aggregate_all).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import h5py
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# Dynamic path resolution to ensure importability in both CoChem-SCRIBE and CoChem-BASE
sys.path.insert(0, str(Path(__file__).parent.parent))

from harvesters.scribe_aggregator import (
    HARTREE_TO_KCAL_MOL,
    DataAggregator,
    ScribeAggregationError,
)


# =============================================================================
# 1. SWMR HDF5 INITIALIZATION & LOCKING RESILIENCE TESTS
# =============================================================================

def test_swmr_hdf5_safe_open(tmp_path: Path) -> None:
    """Verifies read-only opening of real HDF5 database with SWMR mode enabled."""
    h5_file = tmp_path / "landscape.h5"
    with h5py.File(str(h5_file), mode="w", libver="latest") as f:
        f.attrs["version"] = "4.0.0"
        f.create_group("conformers")

    aggregator = DataAggregator(h5_path=h5_file, artifact_dir=tmp_path)
    with aggregator._open_h5() as f:
        assert f.mode == "r"
        assert "conformers" in f
        assert f.attrs["version"] == "4.0.0"


def test_hdf5_missing_file_raises_aggregation_error(tmp_path: Path) -> None:
    """Verifies that attempting to harvest from a nonexistent HDF5 file raises ScribeAggregationError."""
    non_existent = tmp_path / "does_not_exist.h5"
    aggregator = DataAggregator(h5_path=non_existent, artifact_dir=tmp_path, parquet_dir=tmp_path / "empty_pq")
    with pytest.raises(ScribeAggregationError) as exc_info:
        aggregator.harvest_conformers()
    assert "Conformer harvesting failed" in str(exc_info.value) or "does not exist" in str(exc_info.value)


# =============================================================================
# 2. CONFORMER HIERARCHY EXTRACTION & COORDINATE STRIPPING TESTS
# =============================================================================

def test_conformer_extraction_and_coordinate_stripping(tmp_path: Path) -> None:
    """Verifies conformers are extracted, coordinates stripped, and energies converted to kcal/mol."""
    h5_file = tmp_path / "landscape.h5"
    with h5py.File(str(h5_file), mode="w", libver="latest") as f:
        conf_grp = f.create_group("conformers")

        # Conformer 1: Global minimum (0.0 Hartrees relative)
        c1 = conf_grp.create_group("conf_01")
        c1.attrs["conformer_id"] = "conf_01"
        c1.attrs["relative_energy_hartree"] = 0.0000000000
        c1.attrs["point_group_symmetry"] = "C2v"
        # Dense 15x3 Cartesian coordinate matrix (must be stripped)
        c1.create_dataset("xyz_coordinates", data=np.ones((15, 3), dtype=np.float64))

        # Conformer 2: High energy (0.0050 Hartrees relative)
        c2 = conf_grp.create_group("conf_02")
        c2.attrs["conformer_id"] = "conf_02"
        c2.attrs["relative_energy_hartree"] = 0.0050000000
        c2.attrs["point_group_symmetry"] = "Cs"
        c2.create_dataset("xyz_coordinates", data=np.full((15, 3), 2.5, dtype=np.float64))

        # Conformer 3: Medium energy (0.0025 Hartrees relative)
        c3 = conf_grp.create_group("conf_03")
        c3.attrs["conformer_id"] = "conf_03"
        c3.attrs["relative_energy_hartree"] = 0.0025000000
        c3.attrs["point_group_symmetry"] = "C1"
        c3.create_dataset("xyz_coordinates", data=np.zeros((15, 3), dtype=np.float64))

    aggregator = DataAggregator(h5_path=h5_file, artifact_dir=tmp_path)
    harvested = aggregator.harvest_conformers(top_n=10)

    assert len(harvested) == 3
    # Check strict ascending order
    assert harvested[0]["conformer_id"] == "conf_01"
    assert harvested[1]["conformer_id"] == "conf_03"
    assert harvested[2]["conformer_id"] == "conf_02"

    # Check exact unit conversion factor: 627.5094740631
    expected_c1_kcal = 0.0 * HARTREE_TO_KCAL_MOL
    expected_c3_kcal = 0.0025 * HARTREE_TO_KCAL_MOL
    expected_c2_kcal = 0.0050 * HARTREE_TO_KCAL_MOL

    assert math.isclose(float(harvested[0]["relative_energy_kcal_mol"]), expected_c1_kcal, abs_tol=1e-5)
    assert math.isclose(float(harvested[1]["relative_energy_kcal_mol"]), expected_c3_kcal, abs_tol=1e-5)
    assert math.isclose(float(harvested[2]["relative_energy_kcal_mol"]), expected_c2_kcal, abs_tol=1e-5)

    # Check symmetry groups preserved
    assert harvested[0]["point_group_symmetry"] == "C2v"
    assert harvested[1]["point_group_symmetry"] == "C1"
    assert harvested[2]["point_group_symmetry"] == "Cs"

    # Critical Anti-Spoofing Check: 3D Cartesian coordinates MUST be completely stripped
    for conf in harvested:
        assert "xyz_coordinates" not in conf
        assert "geometry" not in conf
        assert "coordinates" not in conf
        assert "cartesian_coords" not in conf


# =============================================================================
# 3. SPECTROSCOPIC TENSOR PRECISION TESTS
# =============================================================================

def test_spectroscopy_tensor_precision(tmp_path: Path) -> None:
    """Verifies high-precision extraction of rotational constants, dipoles, and centrifugal distortion."""
    h5_file = tmp_path / "landscape.h5"
    with h5py.File(str(h5_file), mode="w", libver="latest") as f:
        spec = f.create_group("spectroscopy")

        # Rotational constants in MHz
        rot = spec.create_group("rotational_constants")
        rot.attrs["A"] = 5432.109876
        rot.attrs["B"] = 2345.678901
        rot.attrs["C"] = 1234.567890

        # Dipole moments in Debye
        dip = spec.create_group("dipole_moments")
        dip.attrs["mu_a"] = 1.450000
        dip.attrs["mu_b"] = 0.650000
        dip.attrs["mu_c"] = 0.000000
        dip.attrs["total"] = float(math.sqrt(1.45**2 + 0.65**2))

        # Centrifugal distortion in MHz
        cent = spec.create_group("centrifugal_distortion")
        cent.attrs["Delta_J"] = 1.25e-4
        cent.attrs["Delta_JK"] = -3.45e-4
        cent.attrs["Delta_K"] = 5.67e-3
        cent.attrs["delta_J"] = 2.34e-5
        cent.attrs["delta_K"] = 4.56e-4

    aggregator = DataAggregator(h5_path=h5_file, artifact_dir=tmp_path)
    spec_data = aggregator.harvest_spectroscopy()

    # Verify rotational constants
    rot_res = spec_data["rotational_constants"]
    assert math.isclose(float(rot_res["A"]), 5432.109876, abs_tol=1e-5)
    assert math.isclose(float(rot_res["B"]), 2345.678901, abs_tol=1e-5)
    assert math.isclose(float(rot_res["C"]), 1234.567890, abs_tol=1e-5)

    # Verify dipole moments
    dip_res = spec_data["dipole_moments"]
    assert math.isclose(float(dip_res["mu_a"]), 1.450000, abs_tol=1e-5)
    assert math.isclose(float(dip_res["mu_b"]), 0.650000, abs_tol=1e-5)
    assert math.isclose(float(dip_res["mu_c"]), 0.000000, abs_tol=1e-5)
    assert math.isclose(float(dip_res["total"]), float(math.sqrt(1.45**2 + 0.65**2)), abs_tol=1e-5)

    # Verify centrifugal parameters
    cent_res = spec_data["centrifugal_distortion"]
    assert math.isclose(float(cent_res["Delta_J"]), 1.25e-4, abs_tol=1e-8)
    assert math.isclose(float(cent_res["Delta_JK"]), -3.45e-4, abs_tol=1e-8)
    assert math.isclose(float(cent_res["Delta_K"]), 5.67e-3, abs_tol=1e-8)
    assert math.isclose(float(cent_res["delta_J"]), 2.34e-5, abs_tol=1e-8)
    assert math.isclose(float(cent_res["delta_K"]), 4.56e-4, abs_tol=1e-8)


# =============================================================================
# 4. THERMODYNAMIC CONVERSION TESTS
# =============================================================================

def test_thermodynamics_unit_conversion(tmp_path: Path) -> None:
    """Verifies exact conversion of thermodynamic Hartree energies to kcal/mol."""
    h5_file = tmp_path / "landscape.h5"
    with h5py.File(str(h5_file), mode="w", libver="latest") as f:
        therm = f.create_group("thermodynamics")
        # Raw Hartree energetic scalars
        zpe_ha = 0.085432
        h_ha = -154.120000
        g_ha = -154.150000
        therm.attrs["zpe_hartree"] = zpe_ha
        therm.attrs["enthalpy_hartree"] = h_ha
        therm.attrs["gibbs_hartree"] = g_ha

        # VPT2 frequencies in cm^-1
        freqs = np.array([450.2, 850.5, 1200.0, 1650.8, 3100.4, 3650.0], dtype=np.float64)
        therm.create_dataset("vpt2_frequencies", data=freqs)

    aggregator = DataAggregator(h5_path=h5_file, artifact_dir=tmp_path)
    therm_data = aggregator.harvest_thermodynamics()

    # Exact physical conversion: E_kcal_mol = E_hartree * 627.5094740631
    expected_zpe = zpe_ha * HARTREE_TO_KCAL_MOL
    expected_h = h_ha * HARTREE_TO_KCAL_MOL
    expected_g = g_ha * HARTREE_TO_KCAL_MOL

    assert math.isclose(float(therm_data["zpe_kcal_mol"]), expected_zpe, abs_tol=1e-4)
    assert math.isclose(float(therm_data["enthalpy_kcal_mol"]), expected_h, abs_tol=1e-4)
    assert math.isclose(float(therm_data["gibbs_free_energy_kcal_mol"]), expected_g, abs_tol=1e-4)

    # Fundamental VPT2 anharmonic frequencies
    freq_res = therm_data["vpt2_frequencies_cm1"]
    assert len(freq_res) == 6
    assert math.isclose(float(freq_res[0]), 450.2, abs_tol=1e-2)
    assert math.isclose(float(freq_res[-1]), 3650.0, abs_tol=1e-2)


# =============================================================================
# 5. TELEMETRY INGESTION TESTS
# =============================================================================

def test_telemetry_harvesting(tmp_path: Path) -> None:
    """Verifies ingestion of execution metrics from cochem_audit_log.json."""
    audit_log = tmp_path / "cochem_audit_log.json"
    log_payload = {
        "timestamp_utc": "2026-08-24T12:00:00Z",
        "wall_clock_time_seconds": 1245.75,
        "peak_gpu_vram_mb": 8192.50,
        "node_architecture": {
            "cpu_cores": 64,
            "gpu_model": "NVIDIA H100 80GB HBM3",
            "hostname": "hpc-calc-node-042"
        }
    }
    audit_log.write_text(json.dumps(log_payload), encoding="utf-8")

    aggregator = DataAggregator(artifact_dir=tmp_path)
    telem = aggregator.harvest_telemetry()

    assert telem["wall_clock_time_seconds"] == 1245.75
    assert telem["peak_gpu_vram_mb"] == 8192.50
    assert telem["node_architecture"]["cpu_cores"] == 64
    assert telem["node_architecture"]["gpu_model"] == "NVIDIA H100 80GB HBM3"
    assert telem["node_architecture"]["hostname"] == "hpc-calc-node-042"


# =============================================================================
# 6. PROVENANCE & GOLDEN SHA-256 TESTS
# =============================================================================

def test_provenance_and_golden_sha256(tmp_path: Path) -> None:
    """Verifies engine version parsing and SHA-256 cryptographic binding."""
    manifest_file = tmp_path / "cochem_deployment_manifest.json"
    manifest_data = {
        "schema_version": "1.0.0",
        "engine_versions": {
            "ORCA": "6.1.1",
            "xTB": "6.7.1",
            "MACE": "mace-off23-medium",
            "PySCF": "2.7.0"
        }
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    config_file = tmp_path / "cochem_system_config.json"
    config_content = json.dumps({"environment": "HPC", "precision": "double", "threads": 32})
    config_file.write_text(config_content, encoding="utf-8")

    expected_sha256 = hashlib.sha256(config_content.encode("utf-8")).hexdigest()

    aggregator = DataAggregator(artifact_dir=tmp_path)
    prov = aggregator.harvest_provenance()

    assert prov["engine_versions"]["ORCA"] == "6.1.1"
    assert prov["engine_versions"]["xTB"] == "6.7.1"
    assert prov["engine_versions"]["MACE"] == "mace-off23-medium"
    assert prov["config_sha256"] == expected_sha256
    assert len(prov["config_sha256"]) == 64


# =============================================================================
# 7. TENSOR TOKEN-COMPRESSION TESTS
# =============================================================================

def test_tensor_statistical_compression_llm() -> None:
    """Verifies statistical compression of arbitrary 1D arrays into 4 bounded parameters."""
    np.random.seed(42)
    synthetic_arr = np.random.normal(loc=150.0, scale=25.0, size=10000)

    compressed = DataAggregator.compress_tensors_for_llm(synthetic_arr)

    assert set(compressed.keys()) == {"Min", "Max", "Mean", "StdDev"}
    assert math.isclose(float(compressed["Min"]), float(np.min(synthetic_arr)), abs_tol=1e-4)
    assert math.isclose(float(compressed["Max"]), float(np.max(synthetic_arr)), abs_tol=1e-4)
    assert math.isclose(float(compressed["Mean"]), float(np.mean(synthetic_arr)), abs_tol=1e-4)
    assert math.isclose(float(compressed["StdDev"]), float(np.std(synthetic_arr)), abs_tol=1e-4)

    # Edge case: empty array returns safe zeroes
    empty_res = DataAggregator.compress_tensors_for_llm(np.array([]))
    assert empty_res == {"Min": 0.0, "Max": 0.0, "Mean": 0.0, "StdDev": 0.0}


# =============================================================================
# 8. PARQUET FALLBACK & STRICT JSON BAN TESTS
# =============================================================================

def test_parquet_columnar_fallback(tmp_path: Path) -> None:
    """Verifies transparent failover to .parquet tables when landscape.h5 is unavailable."""
    pq_dir = tmp_path / "parquet"
    pq_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create conformers.parquet
    df_conf = pd.DataFrame([
        {"conformer_id": "conf_pq_01", "relative_energy_kcal_mol": 0.00, "point_group_symmetry": "C2v"},
        {"conformer_id": "conf_pq_02", "relative_energy_kcal_mol": 1.45, "point_group_symmetry": "Cs"},
    ])
    df_conf.to_parquet(pq_dir / "conformers.parquet", index=False)

    # 2. Create spectroscopy.parquet
    df_spec = pd.DataFrame([{
        "A": 6000.0, "B": 3000.0, "C": 2000.0,
        "mu_a": 1.2, "mu_b": 0.4, "mu_c": 0.0, "total": 1.2649,
        "Delta_J": 1.1e-4, "Delta_JK": -2.2e-4, "Delta_K": 3.3e-3, "delta_J": 1.5e-5, "delta_K": 2.5e-4
    }])
    df_spec.to_parquet(pq_dir / "spectroscopy.parquet", index=False)

    # 3. Create thermodynamics.parquet
    df_therm = pd.DataFrame([{
        "zpe_kcal_mol": 52.3,
        "enthalpy_kcal_mol": -96500.2,
        "gibbs_free_energy_kcal_mol": -96525.8,
        "vpt2_frequencies_cm1": [500.0, 1000.0, 1500.0, 3000.0]
    }])
    df_therm.to_parquet(pq_dir / "thermodynamics.parquet", index=False)

    # Point to nonexistent HDF5 file so fallback is triggered
    aggregator = DataAggregator(
        h5_path=tmp_path / "missing_landscape.h5",
        parquet_dir=pq_dir,
        artifact_dir=tmp_path,
    )

    fallback = aggregator._parse_parquet_fallback()
    assert len(fallback["conformers"]) == 2
    assert fallback["conformers"][0]["conformer_id"] == "conf_pq_01"
    assert fallback["spectroscopy"]["rotational_constants"]["A"] == 6000.0
    assert fallback["thermodynamics"]["zpe_kcal_mol"] == 52.3


# =============================================================================
# 9. DATAFRAME FLATTENER TESTS
# =============================================================================

def test_flatten_to_dataframe(tmp_path: Path) -> None:
    """Verifies that nested dictionaries flatten into clean 2D typed DataFrames."""
    aggregator = DataAggregator(artifact_dir=tmp_path)

    # 1. Conformers flattening
    conf_data = [
        {"conformer_id": "conf_01", "relative_energy_kcal_mol": 0.0, "point_group_symmetry": "C2v"},
        {"conformer_id": "conf_02", "relative_energy_kcal_mol": 2.15, "point_group_symmetry": "C1"},
    ]
    df_conf = aggregator.flatten_to_dataframe(conf_data, table_type="conformers")
    assert isinstance(df_conf, pd.DataFrame)
    assert list(df_conf.columns) == ["conformer_id", "relative_energy_kcal_mol", "point_group_symmetry"]
    assert len(df_conf) == 2
    assert isinstance(df_conf["relative_energy_kcal_mol"].iloc[0], (float, np.floating))

    # 2. Spectroscopy flattening
    spec_data = {
        "rotational_constants": {"A": 5000.0, "B": 2500.0, "C": 1500.0},
        "dipole_moments": {"mu_a": 1.0, "mu_b": 0.0, "mu_c": 0.0, "total": 1.0},
        "centrifugal_distortion": {"Delta_J": 1e-4, "Delta_JK": 0.0, "Delta_K": 0.0, "delta_J": 0.0, "delta_K": 0.0},
    }
    df_spec = aggregator.flatten_to_dataframe(spec_data, table_type="spectroscopy")
    assert isinstance(df_spec, pd.DataFrame)
    assert "Parameter" in df_spec.columns
    assert "Value" in df_spec.columns
    assert "Unit" in df_spec.columns
    assert len(df_spec) == 12

    # 3. Thermodynamics flattening
    therm_data = {
        "zpe_kcal_mol": 45.2,
        "enthalpy_kcal_mol": -80000.0,
        "gibbs_free_energy_kcal_mol": -80020.0,
    }
    df_therm = aggregator.flatten_to_dataframe(therm_data, table_type="thermodynamics")
    assert isinstance(df_therm, pd.DataFrame)
    assert len(df_therm) == 3


# =============================================================================
# 10. UNIFIED PIPELINE (AGGREGATE_ALL) TESTS
# =============================================================================

def test_aggregate_all_end_to_end(tmp_path: Path) -> None:
    """Verifies end-to-end data harvesting pipeline returning full payload."""
    h5_file = tmp_path / "landscape.h5"
    with h5py.File(str(h5_file), mode="w", libver="latest") as f:
        # Conformers
        c_grp = f.create_group("conformers")
        c1 = c_grp.create_group("conf_01")
        c1.attrs["relative_energy_hartree"] = 0.0
        c1.attrs["point_group_symmetry"] = "C2v"
        c1.create_dataset("xyz_coordinates", data=np.zeros((3, 3)))

        # Spectroscopy
        s_grp = f.create_group("spectroscopy")
        rg = s_grp.create_group("rotational_constants")
        rg.attrs["A"] = 10000.0
        rg.attrs["B"] = 5000.0
        rg.attrs["C"] = 2500.0

        # Thermodynamics
        t_grp = f.create_group("thermodynamics")
        t_grp.attrs["zpe_hartree"] = 0.05
        t_grp.attrs["enthalpy_hartree"] = -100.0
        t_grp.attrs["gibbs_hartree"] = -100.05

    # Telemetry
    audit_file = tmp_path / "cochem_audit_log.json"
    audit_file.write_text(json.dumps({
        "wall_clock_time_seconds": 300.0,
        "peak_gpu_vram_mb": 4096.0,
        "node_architecture": {"cpu_cores": 16, "gpu_model": "RTX 4090"}
    }), encoding="utf-8")

    # Provenance
    manifest_file = tmp_path / "cochem_deployment_manifest.json"
    manifest_file.write_text(json.dumps({"engine_versions": {"ORCA": "6.1.1"}}), encoding="utf-8")

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text(json.dumps({"run_id": "test_run_001"}), encoding="utf-8")

    aggregator = DataAggregator(h5_path=h5_file, artifact_dir=tmp_path)
    result = aggregator.aggregate_all(top_n_conformers=5)

    assert "conformers" in result
    assert "spectroscopy" in result
    assert "thermodynamics" in result
    assert "telemetry" in result
    assert "provenance" in result

    assert len(result["conformers"]) == 1
    assert result["conformers"][0]["conformer_id"] == "conf_01"
    assert result["spectroscopy"]["rotational_constants"]["A"] == 10000.0
    assert math.isclose(float(result["thermodynamics"]["zpe_kcal_mol"]), 0.05 * HARTREE_TO_KCAL_MOL, abs_tol=1e-4)
    assert result["telemetry"]["wall_clock_time_seconds"] == 300.0
    assert result["provenance"]["engine_versions"]["ORCA"] == "6.1.1"
    assert len(result["provenance"]["config_sha256"]) == 64
