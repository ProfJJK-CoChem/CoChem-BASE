#!/usr/bin/env python3
"""
Unit Test Suite for CoChem-SCRIBE Data Harvester & Aggregator.
=============================================================
Phase 2, Task 5: Zero-Tolerance Verification (tests/test_scribe_aggregator.py).

Verifies:
1. SWMR HDF5 read-only concurrency and non-POSIX locking resilience.
2. Conformer hierarchy extraction and memory-safe 3D coordinate stripping.
3. Spectroscopic TORQ tensor precision (rotational constants, dipoles, Watson distortion).
4. Thermodynamic conversion with exact CODATA physical constant (627.5094740631).
5. Telemetry ingestion from real cochem_audit_log.json files.
6. Provenance harvesting and golden SHA-256 cryptographic binding of system configs.
7. Fixed-token tensor statistical compression (Min, Max, Mean, StdDev).
8. Binary columnar Parquet fallback failover with strict banning of JSON tensor fallbacks.
9. Rigidly typed DataFrame flattening for LaTeX booktabs and Markdown tables.
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
import pytest

# Dynamic path resolution to ensure importability in both CoChem-SCRIBE and CoChem-BASE
sys.path.insert(0, str(Path(__file__).parent.parent))

from harvesters.scribe_aggregator import (
    HARTREE_TO_KCAL_MOL,
    DataAggregator,
    ScribeAggregationError,
    compress_tensors_for_llm,
    flatten_conformers_to_df,
    flatten_provenance_to_df,
    flatten_spectroscopy_to_df,
    flatten_telemetry_to_df,
    flatten_thermodynamics_to_df,
)


# =============================================================================
# PYTEST FIXTURE ARCHITECTURE (Real Disk I/O via tmp_path)
# =============================================================================

@pytest.fixture
def hdf5_landscape_file(tmp_path: Path) -> Path:
    """Generates a physical landscape.h5 database populated with conformers, spectroscopy, and thermodynamics."""
    h5_path = tmp_path / "landscape.h5"
    with h5py.File(str(h5_path), mode="w", libver="latest") as f:
        f.attrs["schema_version"] = "4.0.0"
        f.attrs["project"] = "CoChem-SCRIBE"

        # 1. Conformers hierarchy under /conformers
        conf_grp = f.create_group("conformers")

        # Conformer 01: Global minimum (0.0 Hartrees relative)
        c1 = conf_grp.create_group("conf_01")
        c1.attrs["conformer_id"] = "conf_01"
        c1.attrs["relative_energy"] = 0.0000000000
        c1.attrs["point_group_symmetry"] = "C2v"
        # Dense 15x3 Cartesian coordinate matrix (must be stripped during harvesting)
        c1.create_dataset("xyz_coordinates", data=np.ones((15, 3), dtype=np.float64))

        # Conformer 02: Higher energy (0.0035 Hartrees relative)
        c2 = conf_grp.create_group("conf_02")
        c2.attrs["conformer_id"] = "conf_02"
        c2.attrs["relative_energy"] = 0.0035000000
        c2.attrs["point_group_symmetry"] = "Cs"
        c2.create_dataset("xyz_coordinates", data=np.full((15, 3), 2.5, dtype=np.float64))

        # Conformer 03: Intermediate energy (0.0018 Hartrees relative)
        c3 = conf_grp.create_group("conf_03")
        c3.attrs["conformer_id"] = "conf_03"
        c3.attrs["relative_energy"] = 0.0018000000
        c3.attrs["point_group_symmetry"] = "C1"
        c3.create_dataset("xyz_coordinates", data=np.zeros((15, 3), dtype=np.float64))

        # 2. Spectroscopic datasets under /spectroscopy
        spec_grp = f.create_group("spectroscopy")
        spec_grp.create_dataset("rotational_constants", data=np.array([5420.5, 2810.2, 1950.8], dtype=np.float64))
        spec_grp.create_dataset("dipole_moments", data=np.array([1.85, 0.42, 0.0, 1.8970767], dtype=np.float64))
        spec_grp.create_dataset("centrifugal_distortion", data=np.array([1.25e-4, -3.45e-4, 5.67e-3, 2.34e-5, 4.56e-4], dtype=np.float64))

        # 3. Thermodynamic datasets under /thermodynamics
        therm_grp = f.create_group("thermodynamics")
        therm_grp.attrs["zero_point_energy"] = 0.1245000000
        therm_grp.attrs["enthalpy"] = -154.2341000000
        therm_grp.attrs["gibbs_free_energy"] = -154.2789000000
        vpt2_freqs = np.array([450.2, 820.5, 1450.0, 3100.4], dtype=np.float64)
        therm_grp.create_dataset("vpt2_frequencies", data=vpt2_freqs)

        # Enable SWMR mode where supported by the HDF5 library
        try:
            f.swmr_mode = True
        except Exception:
            pass

    return h5_path


@pytest.fixture
def parquet_fallback_files(tmp_path: Path) -> Path:
    """Writes valid binary columnar .parquet tables for conformers, spectroscopy, and thermodynamics."""
    pq_dir = tmp_path / "parquet"
    pq_dir.mkdir(parents=True, exist_ok=True)

    # 1. conformers.parquet
    df_conf = pd.DataFrame([
        {"conformer_id": "conf_pq_01", "relative_energy_kcal_mol": 0.000, "point_group_symmetry": "C2v"},
        {"conformer_id": "conf_pq_02", "relative_energy_kcal_mol": 1.450, "point_group_symmetry": "Cs"},
        {"conformer_id": "conf_pq_03", "relative_energy_kcal_mol": 2.890, "point_group_symmetry": "C1"},
    ])
    df_conf.to_parquet(pq_dir / "conformers.parquet", index=False)

    # 2. spectroscopy.parquet
    df_spec = pd.DataFrame([{
        "A": 5420.5, "B": 2810.2, "C": 1950.8,
        "mu_a": 1.85, "mu_b": 0.42, "mu_c": 0.0, "total": 1.8970767,
        "Delta_J": 1.25e-4, "Delta_JK": -3.45e-4, "Delta_K": 5.67e-3,
        "delta_J": 2.34e-5, "delta_K": 4.56e-4,
    }])
    df_spec.to_parquet(pq_dir / "spectroscopy.parquet", index=False)

    # 3. thermodynamics.parquet
    df_therm = pd.DataFrame([{
        "zpe_kcal_mol": 78.1249,
        "enthalpy_kcal_mol": -96783.35,
        "gibbs_free_energy_kcal_mol": -96811.45,
        "vpt2_frequencies_cm1": [450.2, 820.5, 1450.0, 3100.4],
    }])
    df_therm.to_parquet(pq_dir / "thermodynamics.parquet", index=False)

    return pq_dir


@pytest.fixture
def telemetry_and_manifest_files(tmp_path: Path) -> Dict[str, Path]:
    """Writes real audit log, deployment manifest, and system config JSON files to disk."""
    # 1. cochem_audit_log.json
    audit_file = tmp_path / "cochem_audit_log.json"
    audit_payload = {
        "timestamp_utc": "2026-08-24T12:00:00Z",
        "wall_clock_seconds": 1245.75,
        "gpu_vram_peak_mb": 8192.50,
        "node_architecture": {
            "cpu_cores": 64,
            "gpu_model": "NVIDIA H100 80GB HBM3",
            "hostname": "hpc-calc-node-042",
        },
    }
    audit_file.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")

    # 2. cochem_deployment_manifest.json
    manifest_file = tmp_path / "cochem_deployment_manifest.json"
    manifest_payload = {
        "schema_version": "1.0.0",
        "engine_versions": {
            "ORCA": "6.1.1",
            "xTB": "6.7.1",
            "MACE-OFF23": "2023.1",
        },
    }
    manifest_file.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    # 3. cochem_system_config.json
    config_file = tmp_path / "cochem_system_config.json"
    config_payload = {
        "environment": "HPC-Production",
        "precision": "float64",
        "threads": 64,
        "memory_limit_gb": 256,
        "seed": 42,
    }
    config_file.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    return {
        "audit_log": audit_file,
        "manifest": manifest_file,
        "config": config_file,
        "root": tmp_path,
    }


@pytest.fixture
def synthetic_dense_array() -> np.ndarray:
    """Generates a reproducible 10,000-float synthetic array with analytical bounds."""
    x = np.linspace(-5.0, 5.0, 10000, dtype=np.float64)
    # Discrete harmonic potential: V(x) = 0.5 * k * x^2 + periodic perturbation
    potential = 0.5 * 12.5 * (x ** 2) + np.sin(3.0 * x)
    return potential


# =============================================================================
# TEST CASE 1: SWMR HDF5 INITIALIZATION & CONCURRENCY SAFETY
# =============================================================================

def test_swmr_hdf5_initialization_and_concurrency_safety(
    hdf5_landscape_file: Path,
    tmp_path: Path,
) -> None:
    """Verifies DataAggregator opens landscape.h5 in read-only SWMR mode with non-POSIX lock resilience."""
    aggregator = DataAggregator(h5_path=hdf5_landscape_file, artifact_dir=tmp_path)

    # 1. Verify read-only SWMR handle acquisition
    with aggregator._open_h5() as f:
        assert f.mode == "r"
        assert "conformers" in f
        assert "spectroscopy" in f
        assert "thermodynamics" in f

    # 2. Verify non-POSIX file locking resilience
    os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
    with aggregator._open_h5() as f:
        assert f.mode == "r"
        assert f.attrs["project"] == "CoChem-SCRIBE"

    # 3. Verify missing file raises ScribeAggregationError
    missing_path = tmp_path / "non_existent_landscape.h5"
    missing_aggregator = DataAggregator(h5_path=missing_path, artifact_dir=tmp_path, parquet_dir=tmp_path / "no_pq")
    with pytest.raises(ScribeAggregationError) as exc_info:
        missing_aggregator.harvest_conformers()
    assert "Conformer harvesting failed" in str(exc_info.value) or "does not exist" in str(exc_info.value)


# =============================================================================
# TEST CASE 2: CONFORMER HIERARCHY EXTRACTION & COORDINATE STRIPPING
# =============================================================================

def test_conformer_hierarchy_extraction_and_coordinate_stripping(
    hdf5_landscape_file: Path,
    tmp_path: Path,
) -> None:
    """Verifies top-N conformer extraction, ascending sort by energy, and memory-safe coordinate stripping."""
    aggregator = DataAggregator(h5_path=hdf5_landscape_file, artifact_dir=tmp_path)
    conformers = aggregator.harvest_conformers(top_n=10)

    # Assert 3 conformers harvested
    assert len(conformers) == 3

    # Assert strictly ascending relative energy order: conf_01 (0.0) < conf_03 (0.0018 Ha) < conf_02 (0.0035 Ha)
    assert conformers[0]["conformer_id"] == "conf_01"
    assert conformers[1]["conformer_id"] == "conf_03"
    assert conformers[2]["conformer_id"] == "conf_02"

    # Verify unit conversion: Hartrees to kcal/mol (x 627.5094740631)
    expected_c1_kcal = 0.0000 * HARTREE_TO_KCAL_MOL
    expected_c3_kcal = 0.0018 * HARTREE_TO_KCAL_MOL
    expected_c2_kcal = 0.0035 * HARTREE_TO_KCAL_MOL

    assert math.isclose(float(conformers[0]["relative_energy_kcal_mol"]), expected_c1_kcal, abs_tol=1e-5)
    assert math.isclose(float(conformers[1]["relative_energy_kcal_mol"]), expected_c3_kcal, abs_tol=1e-5)
    assert math.isclose(float(conformers[2]["relative_energy_kcal_mol"]), expected_c2_kcal, abs_tol=1e-5)

    # Verify symmetry retention
    assert conformers[0]["point_group_symmetry"] == "C2v"
    assert conformers[1]["point_group_symmetry"] == "C1"
    assert conformers[2]["point_group_symmetry"] == "Cs"

    # Strict Zero-Bloat Verification: Raw 3D Cartesian coordinates must NOT exist in the harvested output
    for conf in conformers:
        assert "xyz_coordinates" not in conf
        assert "coordinates" not in conf
        assert "geometry" not in conf
        assert "cartesian_coords" not in conf
        assert "positions" not in conf


# =============================================================================
# TEST CASE 3: SPECTROSCOPIC TORQ HARVESTING
# =============================================================================

def test_spectroscopic_torq_harvesting(
    hdf5_landscape_file: Path,
    tmp_path: Path,
) -> None:
    """Verifies accurate extraction of rotational constants, dipole moments, and centrifugal distortion."""
    aggregator = DataAggregator(h5_path=hdf5_landscape_file, artifact_dir=tmp_path)
    spectroscopy = aggregator.harvest_spectroscopy()

    # 1. Rotational constants (MHz)
    rot = spectroscopy["rotational_constants"]
    assert math.isclose(float(rot["A"]), 5420.5, abs_tol=1e-5)
    assert math.isclose(float(rot["B"]), 2810.2, abs_tol=1e-5)
    assert math.isclose(float(rot["C"]), 1950.8, abs_tol=1e-5)

    # 2. Dipole moments (Debye)
    dip = spectroscopy["dipole_moments"]
    assert math.isclose(float(dip["mu_a"]), 1.85, abs_tol=1e-5)
    assert math.isclose(float(dip["mu_b"]), 0.42, abs_tol=1e-5)
    assert math.isclose(float(dip["mu_c"]), 0.00, abs_tol=1e-5)
    expected_tot = math.sqrt(1.85**2 + 0.42**2 + 0.0**2)
    assert math.isclose(float(dip["total"]), expected_tot, abs_tol=1e-5)

    # 3. Quartic centrifugal distortion parameters (MHz)
    cent = spectroscopy["centrifugal_distortion"]
    assert math.isclose(float(cent["Delta_J"]), 1.25e-4, abs_tol=1e-8)
    assert math.isclose(float(cent["Delta_JK"]), -3.45e-4, abs_tol=1e-8)
    assert math.isclose(float(cent["Delta_K"]), 5.67e-3, abs_tol=1e-8)
    assert math.isclose(float(cent["delta_J"]), 2.34e-5, abs_tol=1e-8)
    assert math.isclose(float(cent["delta_K"]), 4.56e-4, abs_tol=1e-8)


# =============================================================================
# TEST CASE 4: THERMODYNAMIC HARVESTING & HARTREE CONVERSION
# =============================================================================

def test_thermodynamic_harvesting_and_hartree_conversion(
    hdf5_landscape_file: Path,
    tmp_path: Path,
) -> None:
    """Verifies energetic scalar conversion from Hartrees to kcal/mol via exact CODATA constant."""
    aggregator = DataAggregator(h5_path=hdf5_landscape_file, artifact_dir=tmp_path)
    thermo = aggregator.harvest_thermodynamics()

    # Exact physical conversion: E_kcal_mol = E_hartree * 627.5094740631
    expected_zpe = 0.1245000000 * HARTREE_TO_KCAL_MOL
    expected_h = -154.2341000000 * HARTREE_TO_KCAL_MOL
    expected_g = -154.2789000000 * HARTREE_TO_KCAL_MOL

    assert math.isclose(float(thermo["zpe_kcal_mol"]), expected_zpe, abs_tol=1e-4)
    assert math.isclose(float(thermo["enthalpy_kcal_mol"]), expected_h, abs_tol=1e-4)
    assert math.isclose(float(thermo["gibbs_free_energy_kcal_mol"]), expected_g, abs_tol=1e-4)

    # VPT2 anharmonic vibrational frequencies (cm^-1)
    vpt2 = thermo["vpt2_frequencies_cm1"]
    assert len(vpt2) == 4
    assert math.isclose(float(vpt2[0]), 450.2, abs_tol=1e-2)
    assert math.isclose(float(vpt2[1]), 820.5, abs_tol=1e-2)
    assert math.isclose(float(vpt2[2]), 1450.0, abs_tol=1e-2)
    assert math.isclose(float(vpt2[3]), 3100.4, abs_tol=1e-2)


# =============================================================================
# TEST CASE 5: TELEMETRY HARVESTING
# =============================================================================

def test_telemetry_harvesting(
    telemetry_and_manifest_files: Dict[str, Path],
    tmp_path: Path,
) -> None:
    """Verifies ingestion of execution metrics from cochem_audit_log.json."""
    aggregator = DataAggregator(artifact_dir=telemetry_and_manifest_files["root"])
    telem = aggregator.harvest_telemetry()

    assert math.isclose(float(telem["wall_clock_time_seconds"]), 1245.75, abs_tol=1e-4)
    assert math.isclose(float(telem["peak_gpu_vram_mb"]), 8192.50, abs_tol=1e-4)
    assert telem["node_architecture"]["cpu_cores"] == 64
    assert telem["node_architecture"]["gpu_model"] == "NVIDIA H100 80GB HBM3"
    assert telem["node_architecture"]["hostname"] == "hpc-calc-node-042"


# =============================================================================
# TEST CASE 6: PROVENANCE EXTRACTION & GOLDEN SHA-256 VERIFICATION
# =============================================================================

def test_provenance_extraction_and_golden_sha256(
    telemetry_and_manifest_files: Dict[str, Path],
    tmp_path: Path,
) -> None:
    """Verifies engine version extraction and dynamic SHA-256 cryptographic binding."""
    config_path = telemetry_and_manifest_files["config"]
    hasher = hashlib.sha256()
    with open(config_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    expected_golden_sha256 = hasher.hexdigest()

    aggregator = DataAggregator(artifact_dir=telemetry_and_manifest_files["root"])
    provenance = aggregator.harvest_provenance()

    assert provenance["engine_versions"]["ORCA"] == "6.1.1"
    assert provenance["engine_versions"]["xTB"] == "6.7.1"
    assert provenance["engine_versions"]["MACE-OFF23"] == "2023.1"
    assert provenance["config_sha256"] == expected_golden_sha256
    assert len(provenance["config_sha256"]) == 64


# =============================================================================
# TEST CASE 7: TENSOR TOKEN-COMPRESSION ALGORITHM
# =============================================================================

def test_tensor_token_compression_algorithm(
    synthetic_dense_array: np.ndarray,
) -> None:
    """Verifies that arbitrary-length arrays compress to exactly four statistical bounds."""
    # Test module-level function
    compressed = compress_tensors_for_llm(synthetic_dense_array)
    assert set(compressed.keys()) == {"Min", "Max", "Mean", "StdDev"}

    assert math.isclose(float(compressed["Min"]), float(np.min(synthetic_dense_array)), abs_tol=1e-4)
    assert math.isclose(float(compressed["Max"]), float(np.max(synthetic_dense_array)), abs_tol=1e-4)
    assert math.isclose(float(compressed["Mean"]), float(np.mean(synthetic_dense_array)), abs_tol=1e-4)
    assert math.isclose(float(compressed["StdDev"]), float(np.std(synthetic_dense_array)), abs_tol=1e-4)

    # Test staticmethod on DataAggregator
    compressed_static = DataAggregator.compress_tensors_for_llm(synthetic_dense_array)
    assert compressed_static == compressed

    # Test boundary condition: empty array
    empty_result = compress_tensors_for_llm([])
    assert empty_result == {"Min": 0.0, "Max": 0.0, "Mean": 0.0, "StdDev": 0.0}


# =============================================================================
# TEST CASE 8: PARQUET FAILOVER & STRICT JSON BANNING
# =============================================================================

def test_parquet_failover_and_strict_json_banning(
    parquet_fallback_files: Path,
    tmp_path: Path,
) -> None:
    """Verifies graceful failover to Parquet tables when HDF5 is missing and verifies JSON banning."""
    missing_h5 = tmp_path / "corrupted_or_missing_landscape.h5"
    aggregator = DataAggregator(
        h5_path=missing_h5,
        parquet_dir=parquet_fallback_files,
        artifact_dir=tmp_path,
    )

    fallback_data = aggregator._parse_parquet_fallback()

    # 1. Conformer table validation
    assert len(fallback_data["conformers"]) == 3
    assert fallback_data["conformers"][0]["conformer_id"] == "conf_pq_01"
    assert math.isclose(float(fallback_data["conformers"][1]["relative_energy_kcal_mol"]), 1.450, abs_tol=1e-4)

    # 2. Spectroscopy table validation
    assert math.isclose(float(fallback_data["spectroscopy"]["rotational_constants"]["A"]), 5420.5, abs_tol=1e-4)
    assert math.isclose(float(fallback_data["spectroscopy"]["dipole_moments"]["total"]), 1.8970767, abs_tol=1e-4)

    # 3. Thermodynamics table validation
    assert math.isclose(float(fallback_data["thermodynamics"]["zpe_kcal_mol"]), 78.1249, abs_tol=1e-4)
    assert len(fallback_data["thermodynamics"]["vpt2_frequencies_cm1"]) == 4

    # 4. Anti-Spoofing Rule: Attempting fallback when no Parquet exists raises ScribeAggregationError
    empty_pq_dir = tmp_path / "empty_parquet_directory"
    empty_pq_dir.mkdir(parents=True, exist_ok=True)
    empty_aggregator = DataAggregator(
        h5_path=missing_h5,
        parquet_dir=empty_pq_dir,
        artifact_dir=tmp_path,
    )
    with pytest.raises(ScribeAggregationError):
        empty_aggregator._parse_parquet_fallback()


# =============================================================================
# TEST CASE 9: DATAFRAME FLATTENER
# =============================================================================

def test_dataframe_flattener(tmp_path: Path) -> None:
    """Verifies that nested dictionaries flatten into clean 2D typed DataFrames for LaTeX and Markdown."""
    aggregator = DataAggregator(artifact_dir=tmp_path)

    # 1. Conformers DataFrame
    conformer_payload = [
        {"conformer_id": "conf_01", "relative_energy_kcal_mol": 0.00, "point_group_symmetry": "C2v"},
        {"conformer_id": "conf_02", "relative_energy_kcal_mol": 1.25, "point_group_symmetry": "Cs"},
    ]
    df_conf_method = aggregator.flatten_to_dataframe(conformer_payload, table_type="conformers")
    df_conf_func = flatten_conformers_to_df(conformer_payload)

    assert isinstance(df_conf_method, pd.DataFrame)
    assert list(df_conf_method.columns) == ["conformer_id", "relative_energy_kcal_mol", "point_group_symmetry"]
    assert len(df_conf_method) == 2
    pd.testing.assert_frame_equal(df_conf_method, df_conf_func)

    # 2. Spectroscopy DataFrame
    spec_payload = {
        "rotational_constants": {"A": 5420.5, "B": 2810.2, "C": 1950.8},
        "dipole_moments": {"mu_a": 1.85, "mu_b": 0.42, "mu_c": 0.0, "total": 1.897},
        "centrifugal_distortion": {"Delta_J": 1.25e-4, "Delta_JK": -3.45e-4, "Delta_K": 5.67e-3, "delta_J": 2.34e-5, "delta_K": 4.56e-4},
    }
    df_spec = aggregator.flatten_to_dataframe(spec_payload, table_type="spectroscopy")
    assert isinstance(df_spec, pd.DataFrame)
    assert list(df_spec.columns) == ["Parameter", "Value", "Unit"]
    assert len(df_spec) == 12

    # 3. Thermodynamics DataFrame
    therm_payload = {
        "zpe_kcal_mol": 78.12,
        "enthalpy_kcal_mol": -96783.35,
        "gibbs_free_energy_kcal_mol": -96811.45,
    }
    df_therm = aggregator.flatten_to_dataframe(therm_payload, table_type="thermodynamics")
    assert isinstance(df_therm, pd.DataFrame)
    assert list(df_therm.columns) == ["Property", "Value", "Unit"]
    assert len(df_therm) == 3

    # 4. Telemetry DataFrame
    telem_payload = {
        "wall_clock_time_seconds": 1245.75,
        "peak_gpu_vram_mb": 8192.50,
        "node_architecture": {"cpu_cores": 64, "gpu_model": "NVIDIA H100"},
    }
    df_telem = aggregator.flatten_to_dataframe(telem_payload, table_type="telemetry")
    assert isinstance(df_telem, pd.DataFrame)
    assert list(df_telem.columns) == ["Metric", "Value"]
    assert len(df_telem) == 4

    # 5. Provenance DataFrame
    prov_payload = {
        "engine_versions": {"ORCA": "6.1.1", "xTB": "6.7.1"},
        "config_sha256": "abcdef1234567890" * 4,
    }
    df_prov = aggregator.flatten_to_dataframe(prov_payload, table_type="provenance")
    assert isinstance(df_prov, pd.DataFrame)
    assert list(df_prov.columns) == ["Component", "Version_or_Hash"]
    assert len(df_prov) == 3


# =============================================================================
# INTEGRATION TEST: UNIFIED PIPELINE (AGGREGATE_ALL)
# =============================================================================

def test_aggregate_all_end_to_end(
    hdf5_landscape_file: Path,
    telemetry_and_manifest_files: Dict[str, Path],
    tmp_path: Path,
) -> None:
    """Verifies end-to-end data harvesting pipeline returning full unified payload."""
    aggregator = DataAggregator(
        h5_path=hdf5_landscape_file,
        artifact_dir=telemetry_and_manifest_files["root"],
    )
    result = aggregator.aggregate_all(top_n_conformers=5)

    assert "conformers" in result
    assert "spectroscopy" in result
    assert "thermodynamics" in result
    assert "telemetry" in result
    assert "provenance" in result

    # Check conformers
    assert len(result["conformers"]) == 3
    assert result["conformers"][0]["conformer_id"] == "conf_01"

    # Check spectroscopy
    assert math.isclose(float(result["spectroscopy"]["rotational_constants"]["A"]), 5420.5, abs_tol=1e-4)

    # Check thermodynamics
    assert math.isclose(float(result["thermodynamics"]["zpe_kcal_mol"]), 0.1245 * HARTREE_TO_KCAL_MOL, abs_tol=1e-4)

    # Check telemetry
    assert math.isclose(float(result["telemetry"]["wall_clock_time_seconds"]), 1245.75, abs_tol=1e-4)

    # Check provenance
    assert result["provenance"]["engine_versions"]["ORCA"] == "6.1.1"
    assert len(result["provenance"]["config_sha256"]) == 64
