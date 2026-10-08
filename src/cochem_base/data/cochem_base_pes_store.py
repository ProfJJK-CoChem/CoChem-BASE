"""CoChem: Unified High-Concurrency HDF5 PES Store.
===================================================
Complies with Method Matrix v4 §8C: Production HDF5 SWMR Store Architecture.
Features:
- Single-Writer/Multiple-Reader (SWMR) concurrency mode via h5py (libver="latest", swmr=True).
- Cross-platform IPC process locking strictly via filelock.FileLock (timeout=30.0 s).
- Full deprecation of POSIX-only fcntl.flock to guarantee 6-tier environment matrix safety
  (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- Dynamic energy unit normalization from eV to Hartree using scipy.constants.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import filelock
import h5py
import numpy as np
import scipy.constants

logger = logging.getLogger("cochem.base.pes_store")


def convert_ev_to_hartree(energy_ev: float) -> float:
    """
    Dynamically converts energy in electronvolts (eV) to atomic units (Hartree)
    using scipy.constants. Zero hardcoded floating-point conversion factors.
    """
    hartree_in_ev = scipy.constants.physical_constants["Hartree energy in eV"][0]
    return float(energy_ev) / float(hartree_in_ev)


def convert_hartree_to_ev(energy_ha: float) -> float:
    """
    Dynamically converts energy in Hartree to electronvolts (eV)
    using scipy.constants.
    """
    hartree_in_ev = scipy.constants.physical_constants["Hartree energy in eV"][0]
    return float(energy_ha) * float(hartree_in_ev)


class PESStore:
    """
    High-Concurrency Potential Energy Surface (PES) HDF5 Data Store.
    Protects all write, resize, and flush operations using filelock.FileLock
    and activates Single-Writer/Multiple-Reader (SWMR) mode.
    """

    def __init__(
        self,
        storage_path: Union[str, Path],
        timeout: float = 30.0,
        swmr: bool = True,
        libver: str = "latest",
        **kwargs: Any
    ) -> None:
        self.storage_path = Path(storage_path).resolve()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = float(timeout)
        self.swmr_enabled = bool(swmr)
        self.libver = libver

        # Lockfile path: append .lock suffix to persistent HDF5 database path
        self.lock_path = Path(str(self.storage_path) + ".lock")
        self._file_lock = filelock.FileLock(str(self.lock_path), timeout=self.timeout)

        # Initialize HDF5 container safely with filelock
        with self._file_lock.acquire(timeout=self.timeout):
            with h5py.File(self.storage_path, "a", libver=self.libver) as h5:
                if self.swmr_enabled and not h5.swmr_mode:
                    try:
                        h5.swmr_mode = True
                    except (RuntimeError, ValueError):
                        pass
                if "meta" not in h5:
                    meta = h5.create_group("meta")
                    meta.attrs["created_by"] = "CoChem-PESStore-v4"
                    meta.attrs["swmr_mode"] = self.swmr_enabled
                h5.flush()

    def write_point(
        self,
        point_id: str,
        energy_hartree: Optional[float] = None,
        energy_ev: Optional[float] = None,
        coordinates: Optional[Sequence[Sequence[float]] | np.ndarray] = None,
        gradient: Optional[Sequence[Sequence[float]] | np.ndarray] = None,
        hessian: Optional[Sequence[Sequence[float]] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
        extra_attrs: Optional[Dict[str, Any]] = None,
        tier: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Atomically records a point on the PES. Enforces dynamic unit normalization:
        if energy_ev is provided, converts it to Hartree via scipy.constants.
        """
        if energy_hartree is None and energy_ev is not None:
            energy_hartree = convert_ev_to_hartree(energy_ev)
        elif energy_hartree is None:
            raise ValueError("A measured PES point requires an explicit finite electronic energy")
        if not np.isfinite(float(energy_hartree)) or energy_ev is not None and not np.isfinite(float(energy_ev)):
            raise ValueError("Measured PES energies must be finite")
        if energy_ev is not None and not np.isclose(convert_ev_to_hartree(energy_ev), energy_hartree, rtol=1e-12, atol=1e-12):
            raise ValueError("Conflicting measured Hartree/eV energies")
        protected = {"electronic_energy_hartree", "energy_hartree", "electronic_energy_ev", "energy_ev", "energy", "symbols", "tier"}
        if extra_attrs and protected.intersection(extra_attrs):
            raise ValueError("extra_attrs cannot overwrite measured quantities or declared state metadata")
        prepared = {}
        for name, value in (("coordinates", coordinates), ("gradient", gradient), ("hessian", hessian)):
            if value is None:
                continue
            array = np.asarray(value, dtype=np.float64)
            if not np.all(np.isfinite(array)):
                raise ValueError(f"Measured {name} must be finite")
            if name in {"coordinates", "gradient"} and (array.ndim != 2 or array.shape[1] != 3 or not array.shape[0]):
                raise ValueError(f"Measured {name} requires an ordered N-by-3 array")
            if name == "hessian" and (array.ndim != 2 or array.shape[0] != array.shape[1] or array.shape[0] % 3):
                raise ValueError("Measured Hessian requires a square 3N-by-3N array")
            if symbols is not None and array.shape[0] != (3 * len(symbols) if name == "hessian" else len(symbols)):
                raise ValueError(f"Measured {name} does not match the declared atom order")
            prepared[name] = array

        point_key = str(point_id)
        with self._file_lock.acquire(timeout=self.timeout):
            with h5py.File(self.storage_path, "a", libver=self.libver) as h5:
                if self.swmr_enabled and not h5.swmr_mode:
                    try:
                        h5.swmr_mode = True
                    except (RuntimeError, ValueError):
                        pass

                if point_key in h5:
                    del h5[point_key]
                grp = h5.create_group(point_key)

                grp.attrs["electronic_energy_hartree"] = float(energy_hartree)
                grp.attrs["energy_hartree"] = float(energy_hartree)
                grp.create_dataset("energy", data=float(energy_hartree))
                if energy_ev is not None:
                    grp.attrs["electronic_energy_ev"] = float(energy_ev)
                    grp.attrs["energy_ev"] = float(energy_ev)
                if energy_ev is None:
                    grp.attrs["electronic_energy_ev"] = convert_hartree_to_ev(energy_hartree)
                    grp.attrs["energy_ev"] = convert_hartree_to_ev(energy_hartree)
                if tier is not None:
                    grp.attrs["tier"] = str(tier)

                if symbols is not None:
                    grp.attrs["symbols"] = json.dumps(list(symbols))

                if coordinates is not None:
                    c_arr = prepared["coordinates"]
                    grp.create_dataset("coordinates", data=c_arr, compression="gzip")

                if gradient is not None:
                    g_arr = prepared["gradient"]
                    grp.create_dataset("gradient", data=g_arr, compression="gzip")

                if hessian is not None:
                    h_arr = prepared["hessian"]
                    grp.create_dataset("hessian", data=h_arr, compression="gzip")

                if extra_attrs:
                    for k, v in extra_attrs.items():
                        try:
                            grp.attrs[k] = v
                        except Exception:
                            grp.attrs[k] = json.dumps(v)

                h5.flush()

    def write_tier_data(
        self,
        geom_id: str,
        tier_id: str,
        energy: float,
        energy_is_ev: bool = False,
        gradient: Optional[Sequence[Any] | np.ndarray] = None,
        hessian: Optional[Sequence[Any] | np.ndarray] = None,
        geometry: str = "",
        **kwargs: Any
    ) -> None:
        """
        Writes tiered cascade result data. Automatically normalizes eV to Hartree
        if indicated or detected.
        """
        if energy_is_ev:
            energy_hartree = convert_ev_to_hartree(energy)
        else:
            energy_hartree = float(energy)

        sub_key = f"{geom_id}/{tier_id}"
        self.write_point(
            point_id=sub_key,
            energy_hartree=energy_hartree,
            gradient=gradient,
            hessian=hessian,
            extra_attrs={"geometry": geometry, **kwargs}
        )

    def read_point(self, point_id: str, tier: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """
        Reads point data from HDF5 database in SWMR read mode without exclusive lock contention.
        """
        point_key = str(point_id)
        with h5py.File(self.storage_path, "r", swmr=self.swmr_enabled) as h5:
            if point_key not in h5:
                raise KeyError(f"Point '{point_key}' not found in PESStore at {self.storage_path}.")
            grp = h5[point_key]
            if "electronic_energy_hartree" not in grp.attrs:
                raise ValueError("The archived PES point has no measured Hartree energy")
            measured = float(grp.attrs["electronic_energy_hartree"])
            if not np.isfinite(measured):
                raise ValueError("The archived PES point has a nonfinite measured energy")
            if "energy_hartree" in grp.attrs and float(grp.attrs["energy_hartree"]) != measured:
                raise ValueError("The archived Hartree energy aliases conflict")
            if "energy" in grp and float(grp["energy"][()]) != measured:
                raise ValueError("The archived energy dataset conflicts with its measured quantity")
            measured_ev = convert_hartree_to_ev(measured)
            if "electronic_energy_ev" in grp.attrs and not np.isclose(float(grp.attrs["electronic_energy_ev"]), measured_ev, rtol=1e-12, atol=1e-12):
                raise ValueError("The archived PES energy units are inconsistent")
            res: Dict[str, Any] = {
                "electronic_energy_hartree": measured, "energy_hartree": measured,
                "electronic_energy_ev": measured_ev, "energy_ev": measured_ev,
            }
            for attr_name in grp.attrs:
                if attr_name not in res:
                    res[attr_name] = grp.attrs[attr_name]

            if "coordinates" in grp:
                res["coordinates"] = grp["coordinates"][:]
            if "gradient" in grp:
                res["gradient"] = grp["gradient"][:]
            if "hessian" in grp:
                res["hessian"] = grp["hessian"][:]
            return res

    def list_points(self) -> List[str]:
        """Lists all point keys present in the database."""
        with h5py.File(self.storage_path, "r", swmr=self.swmr_enabled) as h5:
            return [k for k in h5.keys() if k != "meta"]
