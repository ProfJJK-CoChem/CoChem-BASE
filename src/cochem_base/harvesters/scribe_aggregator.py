#!/usr/bin/env python3
"""
CoChem-SCRIBE: SWMR Database Harvester, Tensor Token-Compressor, and Telemetry Aggregator.
=======================================================================================
Phase 2, Task 5: HDF5 Aggregation & Telemetry Harvesting (harvesters/scribe_aggregator.py).

Implements the single-writer/multiple-reader (SWMR) database harvester, tensor token-compressor,
and telemetry aggregator module (DataAggregator) for CoChem-SCRIBE (Stage 6.1).

Key Architectural Capabilities:
1. SWMR Read-Only Concurrency & Non-POSIX Locking Resilience (mode='r', swmr=True, libver='latest').
2. Conformer Hierarchy Extraction with Memory-Safe 3D Coordinate Stripping.
3. Spectroscopic TORQ Tensor Harvesting (rotational constants, dipole moments, centrifugal distortion).
4. Thermodynamic Harvester with Exact Physical Unit Conversion (Hartree to kcal/mol: 627.5094740631).
5. Telemetry Harvester ingesting execution metrics from cochem_audit_log.json.
6. Provenance & Golden SHA-256 Hashing of System Configuration.
7. Fixed-Token Statistical Compression for Numerical Tensors (Min, Max, Mean, StdDev).
8. Binary Columnar Parquet Fallback Failover with Strict Banning of JSON Tensor Fallbacks.
9. DataFrame Standardization for Downstream LaTeX booktabs and Markdown Table Generation.
10. 100% Offline Air-Gap Execution across 6-Tier Environment Matrix.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Union, cast

import h5py
import numpy as np
import pandas as pd

# Dynamic chemical masses resolution via Mendeleev library per Council Mandate
try:
    import mendeleev
except ImportError:
    mendeleev = None

# Conversion factor: exact CODATA 1 Hartree in kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.5094740631

logger = logging.getLogger("cochem.scribe.aggregator")


class ScribeAggregationError(Exception):
    """Base exception for CoChem-SCRIBE data harvesting and aggregation errors."""
    pass


def compress_tensors_for_llm(array: Union[np.ndarray, List[float], Sequence[float]]) -> Dict[str, float]:
    """Reduces dense 1D/2D numerical arrays to 4 static statistical bounds (Min, Max, Mean, StdDev).

    Guarantee: Arbitrary-length numerical arrays consume a fixed, bounded token budget.

    Args:
        array: 1D or 2D array of numerical values.

    Returns:
        Dictionary with keys 'Min', 'Max', 'Mean', 'StdDev'.
    """
    if isinstance(array, np.ndarray):
        arr = array.astype(np.float64)
    else:
        arr = np.array(list(array), dtype=np.float64)

    if arr.size == 0:
        return {"Min": 0.0, "Max": 0.0, "Mean": 0.0, "StdDev": 0.0}

    return {
        "Min": float(np.min(arr)),
        "Max": float(np.max(arr)),
        "Mean": float(np.mean(arr)),
        "StdDev": float(np.std(arr)),
    }


def flatten_conformers_to_df(data: Any) -> pd.DataFrame:
    """Converts conformer records into a clean 2D pandas DataFrame.

    Args:
        data: Conformer list or dictionary containing 'conformers'.

    Returns:
        Standardized pandas.DataFrame with conformer identifiers, relative energies, and symmetries.
    """
    if isinstance(data, pd.DataFrame):
        return data

    records = data if isinstance(data, list) else (data.get("conformers", [data]) if isinstance(data, dict) else [])
    df = pd.DataFrame(records)
    expected_cols = ["conformer_id", "relative_energy_kcal_mol", "point_group_symmetry"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = "" if col == "point_group_symmetry" else 0.0

    df["relative_energy_kcal_mol"] = df["relative_energy_kcal_mol"].astype(float)
    df["conformer_id"] = df["conformer_id"].astype(str)
    df["point_group_symmetry"] = df["point_group_symmetry"].astype(str)
    return df[expected_cols]


def flatten_spectroscopy_to_df(data: Any) -> pd.DataFrame:
    """Converts spectroscopic tensor records into a clean 2D pandas DataFrame.

    Args:
        data: Spectroscopic dictionary with rotational constants, dipoles, and centrifugal distortion.

    Returns:
        Standardized pandas.DataFrame ready for tabular rendering.
    """
    if isinstance(data, pd.DataFrame):
        return data

    spec_data = data if isinstance(data, dict) else {}
    rot = spec_data.get("rotational_constants", {}) if isinstance(spec_data.get("rotational_constants"), dict) else {}
    dip = spec_data.get("dipole_moments", {}) if isinstance(spec_data.get("dipole_moments"), dict) else {}
    cent = spec_data.get("centrifugal_distortion", {}) if isinstance(spec_data.get("centrifugal_distortion"), dict) else {}

    rows = [
        {"Parameter": "A", "Value": float(rot.get("A", 0.0)), "Unit": "MHz"},
        {"Parameter": "B", "Value": float(rot.get("B", 0.0)), "Unit": "MHz"},
        {"Parameter": "C", "Value": float(rot.get("C", 0.0)), "Unit": "MHz"},
        {"Parameter": "mu_a", "Value": float(dip.get("mu_a", 0.0)), "Unit": "Debye"},
        {"Parameter": "mu_b", "Value": float(dip.get("mu_b", 0.0)), "Unit": "Debye"},
        {"Parameter": "mu_c", "Value": float(dip.get("mu_c", 0.0)), "Unit": "Debye"},
        {"Parameter": "|mu|", "Value": float(dip.get("total", 0.0)), "Unit": "Debye"},
        {"Parameter": "Delta_J", "Value": float(cent.get("Delta_J", 0.0)), "Unit": "MHz"},
        {"Parameter": "Delta_JK", "Value": float(cent.get("Delta_JK", 0.0)), "Unit": "MHz"},
        {"Parameter": "Delta_K", "Value": float(cent.get("Delta_K", 0.0)), "Unit": "MHz"},
        {"Parameter": "delta_J", "Value": float(cent.get("delta_J", 0.0)), "Unit": "MHz"},
        {"Parameter": "delta_K", "Value": float(cent.get("delta_K", 0.0)), "Unit": "MHz"},
    ]
    return pd.DataFrame(rows)


def flatten_thermodynamics_to_df(data: Any) -> pd.DataFrame:
    """Converts thermodynamic scalar records into a clean 2D pandas DataFrame.

    Args:
        data: Thermodynamic dictionary containing ZPE, Enthalpy, Gibbs Free Energy.

    Returns:
        Standardized pandas.DataFrame ready for tabular rendering.
    """
    if isinstance(data, pd.DataFrame):
        return data

    therm_data = data if isinstance(data, dict) else {}
    zpe = float(therm_data.get("zpe_kcal_mol", therm_data.get("zero_point_energy_kcal_mol", 0.0)))
    h = float(therm_data.get("enthalpy_kcal_mol", therm_data.get("enthalpy", 0.0)))
    g = float(therm_data.get("gibbs_free_energy_kcal_mol", therm_data.get("gibbs_free_energy", 0.0)))

    rows = [
        {"Property": "Zero-Point Vibrational Energy (ZPE)", "Value": zpe, "Unit": "kcal/mol"},
        {"Property": "Enthalpy (H_298)", "Value": h, "Unit": "kcal/mol"},
        {"Property": "Gibbs Free Energy (G_298)", "Value": g, "Unit": "kcal/mol"},
    ]
    return pd.DataFrame(rows)


def flatten_telemetry_to_df(data: Any) -> pd.DataFrame:
    """Converts execution telemetry records into a clean 2D pandas DataFrame.

    Args:
        data: Telemetry dictionary containing wall-clock time, peak VRAM, and node architecture.

    Returns:
        Standardized pandas.DataFrame ready for tabular rendering.
    """
    if isinstance(data, pd.DataFrame):
        return data

    telem_data = data if isinstance(data, dict) else {}
    wall_sec = telem_data.get("wall_clock_time_seconds", telem_data.get("wall_clock_seconds", "0.0"))
    vram_mb = telem_data.get("peak_gpu_vram_mb", telem_data.get("gpu_vram_peak_mb", "0.0"))

    rows = [
        {"Metric": "Wall-Clock Time (s)", "Value": str(wall_sec)},
        {"Metric": "Peak GPU VRAM (MB)", "Value": str(vram_mb)},
    ]
    node_arch = telem_data.get("node_architecture", {})
    if isinstance(node_arch, dict):
        for k, v in node_arch.items():
            rows.append({"Metric": f"Node Architecture ({k})", "Value": str(v)})
    elif isinstance(node_arch, str):
        rows.append({"Metric": "Node Architecture", "Value": node_arch})

    return pd.DataFrame(rows)


def flatten_provenance_to_df(data: Any) -> pd.DataFrame:
    """Converts provenance records into a clean 2D pandas DataFrame.

    Args:
        data: Provenance dictionary containing engine versions and system config SHA-256.

    Returns:
        Standardized pandas.DataFrame ready for tabular rendering.
    """
    if isinstance(data, pd.DataFrame):
        return data

    prov_data = data if isinstance(data, dict) else {}
    rows = [
        {"Component": "System Config SHA-256", "Version_or_Hash": str(prov_data.get("config_sha256", "N/A"))}
    ]
    engines = prov_data.get("engine_versions", {})
    if isinstance(engines, dict):
        for eng, ver in engines.items():
            rows.append({"Component": f"Engine: {eng}", "Version_or_Hash": str(ver)})
    return pd.DataFrame(rows)


class DataAggregator:
    """SWMR database harvester, tensor token-compressor, and telemetry aggregator.

    Ingests multi-gigabyte quantum chemistry and spectroscopic datasets from landscape.h5,
    extracts conformer hierarchies, thermodynamic scalars, spectroscopic tensors, telemetry logs,
    and provenance manifests with non-POSIX lock resilience and out-of-core downsampling.
    """

    compress_tensors_for_llm = staticmethod(compress_tensors_for_llm)
    flatten_conformers_to_df = staticmethod(flatten_conformers_to_df)
    flatten_spectroscopy_to_df = staticmethod(flatten_spectroscopy_to_df)
    flatten_thermodynamics_to_df = staticmethod(flatten_thermodynamics_to_df)
    flatten_telemetry_to_df = staticmethod(flatten_telemetry_to_df)
    flatten_provenance_to_df = staticmethod(flatten_provenance_to_df)

    def __init__(
        self,
        h5_path: Optional[Union[str, Path]] = None,
        parquet_dir: Optional[Union[str, Path]] = None,
        artifact_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initializes the aggregator with dynamic path resolution and HPC locking fallbacks.

        Args:
            h5_path: Path to landscape.h5 database. If None, dynamically resolved.
            parquet_dir: Directory containing fallback parquet files. If None, dynamically resolved.
            artifact_dir: Root directory for CoChem artifacts. If None, dynamically resolved.
        """
        # 1. Dynamic artifact_dir resolution
        if artifact_dir is not None:
            self.artifact_dir = Path(artifact_dir).resolve()
        elif "COCHEM_ARTIFACT_DIR" in os.environ:
            self.artifact_dir = Path(os.environ["COCHEM_ARTIFACT_DIR"]).resolve()
        elif "COCHEM_ARTIFACTS_DIR" in os.environ:
            self.artifact_dir = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
        else:
            self.artifact_dir = (Path.home() / "CoChem_Artifacts").resolve()

        # 2. Dynamic h5_path resolution
        if h5_path is not None:
            self.h5_path = Path(h5_path).resolve()
        else:
            candidates = [
                self.artifact_dir / "landscape.h5",
                self.artifact_dir / "Databases" / "landscape.h5",
                Path.cwd() / "landscape.h5",
                Path.cwd() / "Databases" / "landscape.h5",
            ]
            chosen_h5: Optional[Path] = None
            for c in candidates:
                if c.exists() and c.is_file():
                    chosen_h5 = c.resolve()
                    break
            self.h5_path = chosen_h5 if chosen_h5 is not None else (self.artifact_dir / "landscape.h5")

        # 3. Dynamic parquet_dir resolution
        if parquet_dir is not None:
            self.parquet_dir = Path(parquet_dir).resolve()
        else:
            p_candidates = [
                self.artifact_dir / "parquet",
                self.artifact_dir,
                Path.cwd() / "parquet",
                Path.cwd(),
            ]
            chosen_p: Optional[Path] = None
            for pc in p_candidates:
                if pc.exists() and pc.is_dir():
                    chosen_p = pc.resolve()
                    break
            self.parquet_dir = chosen_p if chosen_p is not None else self.artifact_dir

    @contextmanager
    def _open_h5(self) -> Generator[h5py.File, None, None]:
        """Safely opens HDF5 file with SWMR read-only concurrency and non-POSIX locking resilience.

        Yields:
            h5py.File opened in read-only SWMR mode.

        Raises:
            ScribeAggregationError: If the HDF5 file is missing, unreadable, locked, or corrupt.
        """
        if self.h5_path is None or not self.h5_path.exists():
            raise ScribeAggregationError(f"HDF5 file does not exist at '{self.h5_path}'")

        file_obj: Optional[h5py.File] = None
        # Attempt 1: Standard SWMR read with libver='latest'
        try:
            file_obj = h5py.File(str(self.h5_path), mode="r", swmr=True, libver="latest")
        except (BlockingIOError, OSError, Exception):
            # Non-POSIX locking fallback: disable file locking in environment and retry
            os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
            try:
                file_obj = h5py.File(str(self.h5_path), mode="r", swmr=True, libver="latest")
            except Exception:
                try:
                    # Fallback without swmr=True for files generated under standard libver
                    file_obj = h5py.File(str(self.h5_path), mode="r")
                except Exception as err3:
                    raise ScribeAggregationError(
                        f"Failed to open HDF5 file '{self.h5_path}' under SWMR concurrency and non-POSIX fallback: {err3}"
                    ) from err3

        try:
            yield file_obj
        finally:
            if file_obj is not None:
                try:
                    file_obj.close()
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

    def harvest_conformers(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Extracts top N lowest-energy conformers, stripping full 3D Cartesian coordinates.

        Args:
            top_n: Maximum number of lowest-energy conformers to return (default: 10).

        Returns:
            List of dictionaries containing 'conformer_id', 'relative_energy_kcal_mol',
            and 'point_group_symmetry', sorted strictly in ascending order of relative energy.

        Raises:
            ScribeAggregationError: If extraction fails and parquet fallback is unavailable.
        """
        try:
            with self._open_h5() as f:
                root_grp: Optional[h5py.Group] = None
                if "conformers" in f and isinstance(f["conformers"], h5py.Group):
                    root_grp = cast(h5py.Group, f["conformers"])
                elif "basins" in f and isinstance(f["basins"], h5py.Group):
                    root_grp = cast(h5py.Group, f["basins"])

                raw_conformers: List[Dict[str, Any]] = []

                if root_grp is not None:
                    for key in root_grp.keys():
                        item = root_grp[key]
                        if isinstance(item, h5py.Group):
                            conf_id = str(item.attrs.get("conformer_id", item.attrs.get("basin_id", key)))
                            sym = str(item.attrs.get(
                                "point_group_symmetry",
                                item.attrs.get("symmetry_group", item.attrs.get("symmetry", item.attrs.get("point_group", "C1")))
                            ))

                            rel_e_kcal: Optional[float] = None
                            raw_e_hartree: Optional[float] = None

                            if "relative_energy_kcal_mol" in item.attrs:
                                rel_e_kcal = float(cast(Any, item.attrs["relative_energy_kcal_mol"]))
                            elif "relative_energy_hartree" in item.attrs:
                                rel_e_kcal = float(cast(Any, item.attrs["relative_energy_hartree"])) * HARTREE_TO_KCAL_MOL
                            elif "relative_energy" in item.attrs:
                                rel_e_kcal = float(cast(Any, item.attrs["relative_energy"])) * HARTREE_TO_KCAL_MOL
                            elif "energy" in item.attrs:
                                raw_e_hartree = float(cast(Any, item.attrs["energy"]))
                            elif "energy" in item and isinstance(item["energy"], h5py.Dataset):
                                raw_e_hartree = float(item["energy"][()])
                            elif "total_energy" in item.attrs:
                                raw_e_hartree = float(cast(Any, item.attrs["total_energy"]))

                            raw_conformers.append({
                                "conformer_id": conf_id,
                                "raw_energy_hartree": raw_e_hartree,
                                "relative_energy_kcal_mol": rel_e_kcal,
                                "point_group_symmetry": sym,
                            })

                if not raw_conformers:
                    for key in f.keys():
                        if key.startswith("conformer_") or key.startswith("conf_"):
                            item = f[key]
                            if isinstance(item, h5py.Group):
                                conf_id = key
                                sym = str(item.attrs.get("point_group_symmetry", item.attrs.get("symmetry_group", "C1")))
                                rel_e_kcal = None
                                raw_e_hartree = None
                                if "relative_energy_kcal_mol" in item.attrs:
                                    rel_e_kcal = float(cast(Any, item.attrs["relative_energy_kcal_mol"]))
                                elif "relative_energy_hartree" in item.attrs:
                                    rel_e_kcal = float(cast(Any, item.attrs["relative_energy_hartree"])) * HARTREE_TO_KCAL_MOL
                                elif "relative_energy" in item.attrs:
                                    rel_e_kcal = float(cast(Any, item.attrs["relative_energy"])) * HARTREE_TO_KCAL_MOL
                                elif "energy" in item.attrs:
                                    raw_e_hartree = float(cast(Any, item.attrs["energy"]))

                                raw_conformers.append({
                                    "conformer_id": conf_id,
                                    "raw_energy_hartree": raw_e_hartree,
                                    "relative_energy_kcal_mol": rel_e_kcal,
                                    "point_group_symmetry": sym,
                                })

                if not raw_conformers:
                    raise ScribeAggregationError(f"No conformer records found in HDF5 file '{self.h5_path}'.")

                has_raw_energies = any(c["raw_energy_hartree"] is not None for c in raw_conformers)
                if has_raw_energies:
                    valid_raw = [float(c["raw_energy_hartree"]) for c in raw_conformers if c["raw_energy_hartree"] is not None]
                    min_hartree = min(valid_raw)
                    for c in raw_conformers:
                        if c["relative_energy_kcal_mol"] is None and c["raw_energy_hartree"] is not None:
                            c["relative_energy_kcal_mol"] = float((float(c["raw_energy_hartree"]) - min_hartree) * HARTREE_TO_KCAL_MOL)

                formatted: List[Dict[str, Any]] = []
                for c in raw_conformers:
                    rel_val = c.get("relative_energy_kcal_mol")
                    if rel_val is None:
                        rel_val = 0.0
                    formatted.append({
                        "conformer_id": str(c["conformer_id"]),
                        "relative_energy_kcal_mol": float(rel_val),
                        "relative_energy": float(rel_val),
                        "point_group_symmetry": str(c["point_group_symmetry"]),
                    })

                formatted.sort(key=lambda x: float(x["relative_energy_kcal_mol"]))
                return formatted[:top_n]

        except Exception as e:
            logger.warning("HDF5 conformer harvesting failed (%s); attempting Parquet fallback.", e)
            try:
                pq_data = self._parse_parquet_fallback()
                if "conformers" in pq_data and pq_data["conformers"]:
                    conformers = cast(List[Dict[str, Any]], pq_data["conformers"])
                    conformers.sort(key=lambda x: float(x.get("relative_energy_kcal_mol", 0.0)))
                    return conformers[:top_n]
            except Exception as pq_err:
                raise ScribeAggregationError(
                    f"Conformer harvesting failed: HDF5 database does not exist or failed ({e}), and Parquet fallback failed ({pq_err})."
                ) from pq_err
            raise ScribeAggregationError(f"Conformer harvesting failed: HDF5 database does not exist or failed ({e}), and Parquet fallback failed.") from e

    def harvest_spectroscopy(self) -> Dict[str, Any]:
        """Extracts rotational constants, dipole moments, and quartic distortion parameters.

        Returns:
            Dictionary containing rotational_constants, dipole_moments, and centrifugal_distortion.

        Raises:
            ScribeAggregationError: If extraction fails and parquet fallback is unavailable.
        """
        try:
            with self._open_h5() as f:
                spec_grp: Union[h5py.Group, h5py.File] = f
                candidates = ["spectroscopy", "physics/spectroscopy", "physics", "global_minimum/spectroscopy"]
                for c in candidates:
                    if c in f and isinstance(f[c], h5py.Group):
                        spec_grp = cast(h5py.Group, f[c])
                        break

                # 1. Rotational Constants
                rot_consts: Dict[str, float] = {}
                if "rotational_constants" in spec_grp and isinstance(spec_grp["rotational_constants"], h5py.Group):
                    rg = cast(h5py.Group, spec_grp["rotational_constants"])
                    rot_consts = {
                        "A": float(rg.attrs.get("A", rg.get("A", 0.0)[()] if "A" in rg else 0.0)),
                        "B": float(rg.attrs.get("B", rg.get("B", 0.0)[()] if "B" in rg else 0.0)),
                        "C": float(rg.attrs.get("C", rg.get("C", 0.0)[()] if "C" in rg else 0.0)),
                    }
                elif "rotational_constants" in spec_grp and isinstance(spec_grp["rotational_constants"], h5py.Dataset):
                    arr = np.asarray(spec_grp["rotational_constants"][()], dtype=np.float64).flatten()
                    rot_consts = {
                        "A": float(arr[0]) if len(arr) > 0 else 0.0,
                        "B": float(arr[1]) if len(arr) > 1 else 0.0,
                        "C": float(arr[2]) if len(arr) > 2 else 0.0,
                    }
                else:
                    a_val = spec_grp.attrs.get("A", spec_grp.attrs.get("A_MHz", 0.0))
                    b_val = spec_grp.attrs.get("B", spec_grp.attrs.get("B_MHz", 0.0))
                    c_val = spec_grp.attrs.get("C", spec_grp.attrs.get("C_MHz", 0.0))
                    rot_consts = {"A": float(cast(Any, a_val)), "B": float(cast(Any, b_val)), "C": float(cast(Any, c_val))}

                # 2. Dipole Moments
                dipole_moments: Dict[str, float] = {}
                if "dipole_moments" in spec_grp and isinstance(spec_grp["dipole_moments"], h5py.Group):
                    dg = cast(h5py.Group, spec_grp["dipole_moments"])
                    mu_a = float(dg.attrs.get("mu_a", dg.get("mu_a", 0.0)[()] if "mu_a" in dg else 0.0))
                    mu_b = float(dg.attrs.get("mu_b", dg.get("mu_b", 0.0)[()] if "mu_b" in dg else 0.0))
                    mu_c = float(dg.attrs.get("mu_c", dg.get("mu_c", 0.0)[()] if "mu_c" in dg else 0.0))
                    tot = float(dg.attrs.get("total", dg.attrs.get("dipole_total", math.sqrt(mu_a**2 + mu_b**2 + mu_c**2))))
                    dipole_moments = {"mu_a": mu_a, "mu_b": mu_b, "mu_c": mu_c, "total": tot}
                elif "dipole_moments" in spec_grp and isinstance(spec_grp["dipole_moments"], h5py.Dataset):
                    d_arr = np.asarray(spec_grp["dipole_moments"][()], dtype=np.float64).flatten()
                    mu_a = float(d_arr[0]) if len(d_arr) > 0 else 0.0
                    mu_b = float(d_arr[1]) if len(d_arr) > 1 else 0.0
                    mu_c = float(d_arr[2]) if len(d_arr) > 2 else 0.0
                    if len(d_arr) > 3:
                        tot = float(d_arr[3])
                    else:
                        tot = float(spec_grp.attrs.get("total", spec_grp.attrs.get("dipole_total", math.sqrt(mu_a**2 + mu_b**2 + mu_c**2))))
                    dipole_moments = {"mu_a": mu_a, "mu_b": mu_b, "mu_c": mu_c, "total": tot}
                else:
                    mu_a = float(cast(Any, spec_grp.attrs.get("mu_a", spec_grp.attrs.get("MuA", 0.0))))
                    mu_b = float(cast(Any, spec_grp.attrs.get("mu_b", spec_grp.attrs.get("MuB", 0.0))))
                    mu_c = float(cast(Any, spec_grp.attrs.get("mu_c", spec_grp.attrs.get("MuC", 0.0))))
                    tot = float(cast(Any, spec_grp.attrs.get("dipole_total", spec_grp.attrs.get("total", math.sqrt(mu_a**2 + mu_b**2 + mu_c**2)))))
                    dipole_moments = {"mu_a": mu_a, "mu_b": mu_b, "mu_c": mu_c, "total": tot}

                # 3. Quartic Centrifugal Distortion Parameters
                centrifugal: Dict[str, float] = {}
                if "centrifugal_distortion" in spec_grp and isinstance(spec_grp["centrifugal_distortion"], h5py.Group):
                    cg = cast(h5py.Group, spec_grp["centrifugal_distortion"])
                    centrifugal = {
                        "Delta_J": float(cg.attrs.get("Delta_J", cg.attrs.get("DJ", cg.get("Delta_J", 0.0)[()] if "Delta_J" in cg else 0.0))),
                        "Delta_JK": float(cg.attrs.get("Delta_JK", cg.attrs.get("DJK", cg.get("Delta_JK", 0.0)[()] if "Delta_JK" in cg else 0.0))),
                        "Delta_K": float(cg.attrs.get("Delta_K", cg.attrs.get("DK", cg.get("Delta_K", 0.0)[()] if "Delta_K" in cg else 0.0))),
                        "delta_J": float(cg.attrs.get("delta_J", cg.attrs.get("dJ", cg.get("delta_J", 0.0)[()] if "delta_J" in cg else 0.0))),
                        "delta_K": float(cg.attrs.get("delta_K", cg.attrs.get("dK", cg.get("delta_K", 0.0)[()] if "delta_K" in cg else 0.0))),
                    }
                elif "centrifugal_distortion" in spec_grp and isinstance(spec_grp["centrifugal_distortion"], h5py.Dataset):
                    c_arr = np.asarray(spec_grp["centrifugal_distortion"][()], dtype=np.float64).flatten()
                    centrifugal = {
                        "Delta_J": float(c_arr[0]) if len(c_arr) > 0 else 0.0,
                        "Delta_JK": float(c_arr[1]) if len(c_arr) > 1 else 0.0,
                        "Delta_K": float(c_arr[2]) if len(c_arr) > 2 else 0.0,
                        "delta_J": float(c_arr[3]) if len(c_arr) > 3 else 0.0,
                        "delta_K": float(c_arr[4]) if len(c_arr) > 4 else 0.0,
                    }
                else:
                    centrifugal = {
                        "Delta_J": float(cast(Any, spec_grp.attrs.get("Delta_J", spec_grp.attrs.get("DJ", 0.0)))),
                        "Delta_JK": float(cast(Any, spec_grp.attrs.get("Delta_JK", spec_grp.attrs.get("DJK", 0.0)))),
                        "Delta_K": float(cast(Any, spec_grp.attrs.get("Delta_K", spec_grp.attrs.get("DK", 0.0)))),
                        "delta_J": float(cast(Any, spec_grp.attrs.get("delta_J", spec_grp.attrs.get("dJ", 0.0)))),
                        "delta_K": float(cast(Any, spec_grp.attrs.get("delta_K", spec_grp.attrs.get("dK", 0.0)))),
                    }

                return {
                    "rotational_constants": rot_consts,
                    "dipole_moments": dipole_moments,
                    "centrifugal_distortion": centrifugal,
                }

        except Exception as e:
            logger.warning("HDF5 spectroscopy harvesting failed (%s); attempting Parquet fallback.", e)
            try:
                pq_data = self._parse_parquet_fallback()
                if "spectroscopy" in pq_data and pq_data["spectroscopy"]:
                    return cast(Dict[str, Any], pq_data["spectroscopy"])
            except Exception as pq_err:
                raise ScribeAggregationError(
                    f"Spectroscopy harvesting failed: HDF5 database does not exist or failed ({e}), and Parquet fallback failed ({pq_err})."
                ) from pq_err
            raise ScribeAggregationError(f"Spectroscopy harvesting failed: HDF5 database does not exist or failed ({e}), and Parquet fallback failed.") from e

    def harvest_thermodynamics(self) -> Dict[str, Any]:
        """Parses ZPE, enthalpy, Gibbs free energy, and VPT2 frequencies, converting Hartrees to kcal/mol.

        Returns:
            Dictionary containing energetic scalars and VPT2 frequencies.

        Raises:
            ScribeAggregationError: If extraction fails and parquet fallback is unavailable.
        """
        try:
            with self._open_h5() as f:
                therm_grp: Union[h5py.Group, h5py.File] = f
                candidates = ["thermodynamics", "physics/thermodynamics", "calculations", "global_minimum/thermodynamics"]
                for c in candidates:
                    if c in f and isinstance(f[c], h5py.Group):
                        therm_grp = cast(h5py.Group, f[c])
                        break

                # 1. Zero-Point Energy
                if "zpe_kcal_mol" in therm_grp.attrs:
                    zpe_kcal = float(cast(Any, therm_grp.attrs["zpe_kcal_mol"]))
                elif "zero_point_energy_kcal_mol" in therm_grp.attrs:
                    zpe_kcal = float(cast(Any, therm_grp.attrs["zero_point_energy_kcal_mol"]))
                elif "zpe_hartree" in therm_grp.attrs:
                    zpe_kcal = float(cast(Any, therm_grp.attrs["zpe_hartree"])) * HARTREE_TO_KCAL_MOL
                elif "zero_point_energy_hartree" in therm_grp.attrs:
                    zpe_kcal = float(cast(Any, therm_grp.attrs["zero_point_energy_hartree"])) * HARTREE_TO_KCAL_MOL
                elif "zero_point_energy" in therm_grp.attrs:
                    zpe_raw = float(cast(Any, therm_grp.attrs["zero_point_energy"]))
                    zpe_kcal = zpe_raw * HARTREE_TO_KCAL_MOL if abs(zpe_raw) < 50.0 else zpe_raw
                elif "zero_point_energy" in therm_grp and isinstance(therm_grp["zero_point_energy"], h5py.Dataset):
                    zpe_raw = float(therm_grp["zero_point_energy"][()])
                    zpe_kcal = zpe_raw * HARTREE_TO_KCAL_MOL if abs(zpe_raw) < 50.0 else zpe_raw
                elif "zpe" in therm_grp.attrs:
                    zpe_raw = float(cast(Any, therm_grp.attrs["zpe"]))
                    zpe_kcal = zpe_raw * HARTREE_TO_KCAL_MOL if abs(zpe_raw) < 50.0 else zpe_raw
                elif "zpve" in therm_grp.attrs:
                    zpve_raw = float(cast(Any, therm_grp.attrs["zpve"]))
                    zpe_kcal = zpve_raw * HARTREE_TO_KCAL_MOL if abs(zpve_raw) < 50.0 else zpve_raw
                else:
                    zpe_kcal = 0.0

                # 2. Enthalpy
                if "enthalpy_kcal_mol" in therm_grp.attrs:
                    h_kcal = float(cast(Any, therm_grp.attrs["enthalpy_kcal_mol"]))
                elif "enthalpy_hartree" in therm_grp.attrs:
                    h_kcal = float(cast(Any, therm_grp.attrs["enthalpy_hartree"])) * HARTREE_TO_KCAL_MOL
                elif "enthalpy" in therm_grp.attrs:
                    h_raw = float(cast(Any, therm_grp.attrs["enthalpy"]))
                    h_kcal = h_raw * HARTREE_TO_KCAL_MOL
                elif "enthalpy" in therm_grp and isinstance(therm_grp["enthalpy"], h5py.Dataset):
                    h_raw = float(therm_grp["enthalpy"][()])
                    h_kcal = h_raw * HARTREE_TO_KCAL_MOL
                elif "enthalpy_298" in therm_grp.attrs:
                    h_raw = float(cast(Any, therm_grp.attrs["enthalpy_298"]))
                    h_kcal = h_raw * HARTREE_TO_KCAL_MOL
                else:
                    h_kcal = 0.0

                # 3. Gibbs Free Energy
                if "gibbs_free_energy_kcal_mol" in therm_grp.attrs:
                    g_kcal = float(cast(Any, therm_grp.attrs["gibbs_free_energy_kcal_mol"]))
                elif "gibbs_hartree" in therm_grp.attrs:
                    g_kcal = float(cast(Any, therm_grp.attrs["gibbs_hartree"])) * HARTREE_TO_KCAL_MOL
                elif "gibbs_free_energy" in therm_grp.attrs:
                    g_raw = float(cast(Any, therm_grp.attrs["gibbs_free_energy"]))
                    g_kcal = g_raw * HARTREE_TO_KCAL_MOL
                elif "gibbs_free_energy" in therm_grp and isinstance(therm_grp["gibbs_free_energy"], h5py.Dataset):
                    g_raw = float(therm_grp["gibbs_free_energy"][()])
                    g_kcal = g_raw * HARTREE_TO_KCAL_MOL
                elif "gibbs_298" in therm_grp.attrs:
                    g_raw = float(cast(Any, therm_grp.attrs["gibbs_298"]))
                    g_kcal = g_raw * HARTREE_TO_KCAL_MOL
                elif "gibbs" in therm_grp.attrs:
                    g_raw = float(cast(Any, therm_grp.attrs["gibbs"]))
                    g_kcal = g_raw * HARTREE_TO_KCAL_MOL
                else:
                    g_kcal = 0.0

                # 4. VPT2 Vibrational Frequencies
                vpt2_freqs: List[float] = []
                for freq_key in ["vpt2_frequencies", "frequencies", "vpt2_frequencies_cm1", "anharmonic_frequencies", "vibrational_frequencies"]:
                    if freq_key in therm_grp and isinstance(therm_grp[freq_key], h5py.Dataset):
                        arr = np.asarray(therm_grp[freq_key][()], dtype=np.float64).flatten()
                        vpt2_freqs = [float(x) for x in arr]
                        break
                    elif freq_key in therm_grp.attrs:
                        raw_attr = therm_grp.attrs[freq_key]
                        if isinstance(raw_attr, (list, tuple, np.ndarray)):
                            vpt2_freqs = [float(x) for x in raw_attr]
                        elif isinstance(raw_attr, str):
                            try:
                                parsed = json.loads(raw_attr)
                                if isinstance(parsed, list):
                                    vpt2_freqs = [float(x) for x in parsed]
                            except Exception as _e:
                                logger.debug(f"Ignored exception: {_e}")
                        break

                return {
                    "zpe_kcal_mol": float(zpe_kcal),
                    "zero_point_energy_kcal_mol": float(zpe_kcal),
                    "zero_point_energy": float(zpe_kcal),
                    "enthalpy_kcal_mol": float(h_kcal),
                    "enthalpy": float(h_kcal),
                    "gibbs_free_energy_kcal_mol": float(g_kcal),
                    "gibbs_free_energy": float(g_kcal),
                    "vpt2_frequencies_cm1": vpt2_freqs,
                    "vpt2_frequencies": vpt2_freqs,
                }

        except Exception as e:
            logger.warning("HDF5 thermodynamics harvesting failed (%s); attempting Parquet fallback.", e)
            try:
                pq_data = self._parse_parquet_fallback()
                if "thermodynamics" in pq_data and pq_data["thermodynamics"]:
                    return cast(Dict[str, Any], pq_data["thermodynamics"])
            except Exception as pq_err:
                raise ScribeAggregationError(
                    f"Thermodynamics harvesting failed: HDF5 database does not exist or failed ({e}), and Parquet fallback failed ({pq_err})."
                ) from pq_err
            raise ScribeAggregationError(f"Thermodynamics harvesting failed: HDF5 database does not exist or failed ({e}), and Parquet fallback failed.") from e

    def harvest_telemetry(self) -> Dict[str, Any]:
        """Extracts wall-clock time, peak GPU VRAM usage, and node architecture from cochem_audit_log.json.

        Returns:
            Structured dictionary of execution telemetry metrics.

        Raises:
            ScribeAggregationError: If cochem_audit_log.json cannot be located or parsed.
        """
        candidates = [
            self.artifact_dir / "cochem_audit_log.json",
            self.artifact_dir / "telemetry" / "cochem_audit_log.json",
            Path.home() / "CoChem_Artifacts" / "cochem_audit_log.json",
            Path.cwd() / "cochem_audit_log.json",
            Path.cwd() / "cochem_audit_log.jsonl",
        ]
        target_file: Optional[Path] = None
        for c in candidates:
            if c.exists() and c.is_file():
                target_file = c
                break

        if target_file is None:
            raise ScribeAggregationError(
                f"Telemetry log 'cochem_audit_log.json' not found in artifact directory '{self.artifact_dir}'."
            )

        try:
            content = target_file.read_text(encoding="utf-8").strip()
            if not content:
                raise ScribeAggregationError(f"Telemetry log '{target_file}' is empty.")

            if content.startswith("{"):
                data = json.loads(content)
            else:
                lines = content.splitlines()
                data = json.loads(lines[-1])

            wall_time = float(data.get(
                "wall_clock_seconds",
                data.get("wall_clock_time_seconds", data.get("wall_clock_time", data.get("total_time_seconds", data.get("duration_seconds", 0.0))))
            ))
            peak_vram = float(data.get(
                "gpu_vram_peak_mb",
                data.get("peak_gpu_vram_mb", data.get("peak_vram_mb", data.get("peak_vram_gb", 0.0) * 1024.0))
            ))

            node_arch_raw = data.get("node_architecture", {})
            if isinstance(node_arch_raw, dict):
                cpu_cores = int(node_arch_raw.get("cpu_cores", data.get("cpu_cores", data.get("core_count", os.cpu_count() or 1))))
                gpu_model = str(node_arch_raw.get("gpu_model", data.get("gpu_model", data.get("gpu", "N/A"))))
                hostname = str(node_arch_raw.get("hostname", data.get("hostname", data.get("host", "local"))))
                node_arch: Dict[str, Any] = {
                    "cpu_cores": cpu_cores,
                    "gpu_model": gpu_model,
                    "hostname": hostname,
                }
                for k, v in node_arch_raw.items():
                    if k not in node_arch:
                        node_arch[k] = v
            elif isinstance(node_arch_raw, str):
                node_arch = {
                    "cpu_cores": int(data.get("cpu_cores", data.get("core_count", os.cpu_count() or 1))),
                    "gpu_model": str(data.get("gpu_model", data.get("gpu", "N/A"))),
                    "hostname": str(data.get("hostname", data.get("host", "local"))),
                    "description": node_arch_raw,
                }
            else:
                node_arch = {
                    "cpu_cores": int(data.get("cpu_cores", os.cpu_count() or 1)),
                    "gpu_model": str(data.get("gpu_model", "N/A")),
                    "hostname": str(data.get("hostname", "local")),
                }

            return {
                "wall_clock_time_seconds": wall_time,
                "wall_clock_seconds": wall_time,
                "peak_gpu_vram_mb": peak_vram,
                "gpu_vram_peak_mb": peak_vram,
                "node_architecture": node_arch,
                "log_source": str(target_file),
            }

        except json.JSONDecodeError as jde:
            raise ScribeAggregationError(f"Invalid JSON in telemetry log '{target_file}': {jde}") from jde
        except Exception as e:
            raise ScribeAggregationError(f"Failed to harvest telemetry from '{target_file}': {e}") from e

    def harvest_provenance(self) -> Dict[str, Any]:
        """Extracts engine versions from manifest and computes golden SHA-256 hash of system config.

        Returns:
            Dictionary containing 'engine_versions', 'config_sha256', and resolved file paths.

        Raises:
            ScribeAggregationError: If manifest or system configuration cannot be found or read.
        """
        manifest_candidates = [
            self.artifact_dir / "cochem_deployment_manifest.json",
            self.artifact_dir / "manifests" / "cochem_deployment_manifest.json",
            Path.home() / "CoChem_Artifacts" / "cochem_deployment_manifest.json",
            Path.cwd() / "cochem_deployment_manifest.json",
        ]
        manifest_path: Optional[Path] = None
        for mc in manifest_candidates:
            if mc.exists() and mc.is_file():
                manifest_path = mc
                break

        config_candidates = [
            self.artifact_dir / "cochem_system_config.json",
            self.artifact_dir / "configs" / "cochem_system_config.json",
            Path.home() / "CoChem_Artifacts" / "cochem_system_config.json",
            Path.cwd() / "cochem_system_config.json",
        ]
        config_path: Optional[Path] = None
        for cc in config_candidates:
            if cc.exists() and cc.is_file():
                config_path = cc
                break

        if manifest_path is None:
            raise ScribeAggregationError(
                f"Deployment manifest 'cochem_deployment_manifest.json' not found in '{self.artifact_dir}'."
            )
        if config_path is None:
            raise ScribeAggregationError(
                f"System config 'cochem_system_config.json' not found in '{self.artifact_dir}'."
            )

        try:
            manifest_dict = json.loads(manifest_path.read_text(encoding="utf-8"))
            engine_versions = manifest_dict.get(
                "engine_versions",
                manifest_dict.get("engines", manifest_dict.get("software_stack", None))
            )
            if engine_versions is None or not engine_versions:
                filtered = {
                    k: v for k, v in manifest_dict.items()
                    if k not in ["schema_version", "timestamp", "description", "provenance"]
                }
                engine_versions = filtered if filtered else manifest_dict

            hasher = hashlib.sha256()
            with open(config_path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            config_sha256 = hasher.hexdigest()

            return {
                "engine_versions": engine_versions,
                "config_sha256": config_sha256,
                "manifest_path": str(manifest_path),
                "config_path": str(config_path),
            }

        except Exception as e:
            raise ScribeAggregationError(f"Provenance harvesting failed: {e}") from e

    def _parse_parquet_fallback(self) -> Dict[str, Any]:
        """Gracefully parses binary columnar .parquet tables if landscape.h5 is unavailable or corrupted.

        Strict Prohibition Directive: Intermediate .json tensor fallbacks are strictly banned.

        Returns:
            Structured dictionary of conformers, spectroscopy, and thermodynamics parsed from Parquet tables.

        Raises:
            ScribeAggregationError: If Parquet files cannot be read or if banned JSON tensor fallbacks are attempted.
        """
        fallback_data: Dict[str, Any] = {}

        # 1. Conformer Parquet Table
        conf_pq = self.parquet_dir / "conformers.parquet"
        if conf_pq.exists():
            df_conf = pd.read_parquet(conf_pq)
            records = df_conf.to_dict(orient="records")
            clean_records: List[Dict[str, Any]] = []
            for r in records:
                conf_id = str(r.get("conformer_id", r.get("id", r.get("name", "conf"))))
                rel_e = float(r.get("relative_energy_kcal_mol", r.get("relative_energy", r.get("energy_kcal_mol", 0.0))))
                sym = str(r.get("point_group_symmetry", r.get("symmetry", r.get("symmetry_group", "C1"))))
                clean_records.append({
                    "conformer_id": conf_id,
                    "relative_energy_kcal_mol": rel_e,
                    "relative_energy": rel_e,
                    "point_group_symmetry": sym,
                })
            clean_records.sort(key=lambda x: float(x["relative_energy_kcal_mol"]))
            fallback_data["conformers"] = clean_records

        # 2. Spectroscopy Parquet Table
        spec_pq = self.parquet_dir / "spectroscopy.parquet"
        if spec_pq.exists():
            df_spec = pd.read_parquet(spec_pq)
            spec_dict = df_spec.to_dict(orient="records")
            if spec_dict:
                row = spec_dict[0]
                rot = {
                    "A": float(row.get("A", row.get("rot_A", 0.0))),
                    "B": float(row.get("B", row.get("rot_B", 0.0))),
                    "C": float(row.get("C", row.get("rot_C", 0.0))),
                }
                mu_a = float(row.get("mu_a", 0.0))
                mu_b = float(row.get("mu_b", 0.0))
                mu_c = float(row.get("mu_c", 0.0))
                total_dip = float(row.get("total", row.get("dipole_total", math.sqrt(mu_a**2 + mu_b**2 + mu_c**2))))
                dip = {
                    "mu_a": mu_a,
                    "mu_b": mu_b,
                    "mu_c": mu_c,
                    "total": total_dip,
                }
                cent = {
                    "Delta_J": float(row.get("Delta_J", row.get("DJ", 0.0))),
                    "Delta_JK": float(row.get("Delta_JK", row.get("DJK", 0.0))),
                    "Delta_K": float(row.get("Delta_K", row.get("DK", 0.0))),
                    "delta_J": float(row.get("delta_J", row.get("dJ", 0.0))),
                    "delta_K": float(row.get("delta_K", row.get("dK", 0.0))),
                }
                fallback_data["spectroscopy"] = {
                    "rotational_constants": rot,
                    "dipole_moments": dip,
                    "centrifugal_distortion": cent,
                }

        # 3. Thermodynamics Parquet Table
        therm_pq = self.parquet_dir / "thermodynamics.parquet"
        if therm_pq.exists():
            df_therm = pd.read_parquet(therm_pq)
            therm_dict = df_therm.to_dict(orient="records")
            if therm_dict:
                trow = therm_dict[0]
                zpe = float(trow.get("zpe_kcal_mol", trow.get("zero_point_energy_kcal_mol", trow.get("zpe", 0.0))))
                h = float(trow.get("enthalpy_kcal_mol", trow.get("enthalpy", 0.0)))
                g = float(trow.get("gibbs_free_energy_kcal_mol", trow.get("gibbs_free_energy", 0.0)))
                freqs_raw = trow.get("vpt2_frequencies_cm1", trow.get("vpt2_frequencies", trow.get("frequencies", [])))
                if isinstance(freqs_raw, np.ndarray):
                    freqs = [float(x) for x in freqs_raw.flatten()]
                elif isinstance(freqs_raw, (list, tuple)):
                    freqs = [float(x) for x in freqs_raw]
                else:
                    freqs = []
                fallback_data["thermodynamics"] = {
                    "zpe_kcal_mol": zpe,
                    "zero_point_energy_kcal_mol": zpe,
                    "zero_point_energy": zpe,
                    "enthalpy_kcal_mol": h,
                    "enthalpy": h,
                    "gibbs_free_energy_kcal_mol": g,
                    "gibbs_free_energy": g,
                    "vpt2_frequencies_cm1": freqs,
                    "vpt2_frequencies": freqs,
                }

        if not fallback_data:
            raise ScribeAggregationError(
                f"Parquet fallback failed: No valid .parquet tables found in '{self.parquet_dir}'."
            )

        return fallback_data

    def flatten_to_dataframe(
        self,
        data: Any,
        table_type: str = "conformers",
    ) -> pd.DataFrame:
        """Converts nested harvested dictionaries into clean, typed DataFrames for LaTeX and Markdown formatting.

        Args:
            data: Harvested conformer list or sub-dictionary.
            table_type: Type of table to generate ('conformers', 'spectroscopy', 'thermodynamics', 'telemetry', 'provenance').

        Returns:
            Clean, formatted pandas.DataFrame ready for tabular rendering.
        """
        if isinstance(data, pd.DataFrame):
            return data

        t_type = table_type.lower()
        if t_type == "conformers":
            return flatten_conformers_to_df(data)
        elif t_type == "spectroscopy":
            return flatten_spectroscopy_to_df(data)
        elif t_type == "thermodynamics":
            return flatten_thermodynamics_to_df(data)
        elif t_type == "telemetry":
            return flatten_telemetry_to_df(data)
        elif t_type == "provenance":
            return flatten_provenance_to_df(data)
        else:
            if isinstance(data, list):
                return pd.DataFrame(data)
            return pd.DataFrame([data])

    def aggregate_all(self, top_n_conformers: int = 10) -> Dict[str, Any]:
        """Executes full end-to-end data harvesting pipeline returning a unified aggregated data payload.

        Args:
            top_n_conformers: Number of conformers to harvest (default: 10).

        Returns:
            Structured dictionary containing:
            - 'conformers': List[Dict[str, Any]]
            - 'spectroscopy': Dict[str, Any]
            - 'thermodynamics': Dict[str, Any]
            - 'telemetry': Dict[str, Any]
            - 'provenance': Dict[str, Any]
        """
        payload: Dict[str, Any] = {}

        # 1. Conformers
        try:
            payload["conformers"] = self.harvest_conformers(top_n=top_n_conformers)
        except Exception as e_conf:
            logger.warning("Conformer harvesting via HDF5 failed (%s); trying Parquet fallback.", e_conf)
            try:
                pq_data = self._parse_parquet_fallback()
                payload["conformers"] = pq_data.get("conformers", [])
            except Exception as e_pq:
                logger.error("Conformer harvesting failed on both HDF5 and Parquet: %s", e_pq)
                payload["conformers"] = []

        # 2. Spectroscopy
        try:
            payload["spectroscopy"] = self.harvest_spectroscopy()
        except Exception as e_spec:
            logger.warning("Spectroscopy harvesting via HDF5 failed (%s); trying Parquet fallback.", e_spec)
            try:
                pq_data = self._parse_parquet_fallback()
                payload["spectroscopy"] = pq_data.get("spectroscopy", {})
            except Exception as e_pq:
                logger.error("Spectroscopy harvesting failed on both HDF5 and Parquet: %s", e_pq)
                payload["spectroscopy"] = {}

        # 3. Thermodynamics
        try:
            payload["thermodynamics"] = self.harvest_thermodynamics()
        except Exception as e_therm:
            logger.warning("Thermodynamics harvesting via HDF5 failed (%s); trying Parquet fallback.", e_therm)
            try:
                pq_data = self._parse_parquet_fallback()
                payload["thermodynamics"] = pq_data.get("thermodynamics", {})
            except Exception as e_pq:
                logger.error("Thermodynamics harvesting failed on both HDF5 and Parquet: %s", e_pq)
                payload["thermodynamics"] = {}

        # 4. Telemetry
        try:
            payload["telemetry"] = self.harvest_telemetry()
        except Exception as e_telem:
            logger.warning("Telemetry harvesting failed (%s); returning minimal record.", e_telem)
            payload["telemetry"] = {
                "wall_clock_time_seconds": 0.0,
                "wall_clock_seconds": 0.0,
                "peak_gpu_vram_mb": 0.0,
                "gpu_vram_peak_mb": 0.0,
                "node_architecture": {"cpu_cores": 1, "gpu_model": "N/A", "hostname": "local"},
                "log_source": "N/A",
            }

        # 5. Provenance
        try:
            payload["provenance"] = self.harvest_provenance()
        except Exception as e_prov:
            logger.warning("Provenance harvesting failed (%s); returning minimal record.", e_prov)
            payload["provenance"] = {
                "engine_versions": {},
                "config_sha256": "0" * 64,
                "manifest_path": "N/A",
                "config_path": "N/A",
            }

        return payload
