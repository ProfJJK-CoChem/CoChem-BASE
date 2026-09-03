"""Dual-Locked Thread-Safe and Process-Safe HDF5 Persistence for CoChem-TORQ."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union
import filelock
import h5py
import numpy as np

from cochem.torq.errors import TorqPersistenceLockError
from cochem.torq.models.schemas import HDF5PersistenceConfig

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical


class HDF5TorqStorage:
    """Thread-safe and process-safe HDF5 storage persister for trajectories and observables [M].

    Guarantees concurrency isolation via dual-locking:
    1. Intra-process: threading.RLock()
    2. Inter-process: filelock.FileLock()
    """

    def __init__(
        self,
        config_or_path: Union[HDF5PersistenceConfig, Path, str],
        timeout: float = 30.0,
        compression: str = "gzip",
        compression_opts: int = 4,
    ) -> None:
        if isinstance(config_or_path, HDF5PersistenceConfig):
            self.path = Path(config_or_path.file_path).resolve()
            self.timeout = float(config_or_path.lock_timeout_seconds)
            self.compression = config_or_path.compression
            self.compression_opts = config_or_path.compression_opts
        else:
            self.path = Path(config_or_path).resolve()
            self.timeout = float(timeout)
            self.compression = str(compression)
            self.compression_opts = int(compression_opts)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

        # Concurrency dual locks [M]
        self._thread_lock = threading.RLock()
        self._file_lock = filelock.FileLock(
            str(self.lock_path), timeout=self.timeout
        )

    def _get_locks(self) -> Any:
        """Helper context manager to acquire dual locks safely [M]."""
        storage_self = self

        class _DualLockContext:

            def __enter__(self) -> None:
                storage_self._thread_lock.acquire()
                try:
                    storage_self._file_lock.acquire()
                except filelock.Timeout as e:
                    storage_self._thread_lock.release()
                    raise TorqPersistenceLockError(
                        f"Process filelock acquisition timed out on {storage_self.lock_path} after {storage_self.timeout}s: {str(e)}"
                    ) from e
                except Exception as e:
                    storage_self._thread_lock.release()
                    raise TorqPersistenceLockError(
                        f"Failed acquiring lock on {storage_self.lock_path}: {str(e)}"
                    ) from e

            def __exit__(
                self, exc_type: Any, exc_val: Any, exc_tb: Any
            ) -> None:
                try:
                    storage_self._file_lock.release()
                finally:
                    storage_self._thread_lock.release()

        return _DualLockContext()

    def _write_trajectory_datasets(
        self,
        grp: Any,
        coords_arr: np.ndarray,
        forces_arr: np.ndarray,
        energy_arr: np.ndarray,
        atomic_numbers: np.ndarray,
        monoisotopic_masses: np.ndarray,
        stress_arr: Optional[np.ndarray] = None,
        dipole_arr: Optional[np.ndarray] = None,
        pol_arr: Optional[np.ndarray] = None,
    ) -> None:
        """Helper to create chunked compressed datasets in an open HDF5 group [M]."""
        T, N, _ = coords_arr.shape

        grp.create_dataset(
            "coordinates",
            data=coords_arr,
            chunks=True,
            maxshape=(None, N, 3),
            compression=self.compression,
            compression_opts=self.compression_opts,
        )

        grp.create_dataset(
            "forces",
            data=forces_arr,
            chunks=True,
            maxshape=(None, N, 3),
            compression=self.compression,
            compression_opts=self.compression_opts,
        )

        grp.create_dataset(
            "energy",
            data=energy_arr,
            chunks=True,
            maxshape=(None,),
            compression=self.compression,
            compression_opts=self.compression_opts,
        )

        grp.create_dataset(
            "atomic_numbers",
            data=np.asarray(atomic_numbers, dtype=np.int32),
            chunks=True,
            compression=self.compression,
            compression_opts=self.compression_opts,
        )

        grp.create_dataset(
            "monoisotopic_masses",
            data=np.asarray(monoisotopic_masses, dtype=np.float64),
            chunks=True,
            compression=self.compression,
            compression_opts=self.compression_opts,
        )

        if stress_arr is not None:
            grp.create_dataset(
                "stress",
                data=stress_arr,
                chunks=True,
                maxshape=(None, 6),
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

        if dipole_arr is not None:
            grp.create_dataset(
                "dipole",
                data=dipole_arr,
                chunks=True,
                maxshape=(None, 3),
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

        if pol_arr is not None:
            grp.create_dataset(
                "polarizability",
                data=pol_arr,
                chunks=True,
                maxshape=(None, 3, 3),
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

    def save_trajectory(
        self,
        traj_id: str,
        coordinates: np.ndarray,
        forces: np.ndarray,
        energy: np.ndarray,
        atomic_numbers: np.ndarray,
        monoisotopic_masses: np.ndarray,
        stress: Optional[np.ndarray] = None,
        dipole: Optional[np.ndarray] = None,
        polarizability: Optional[np.ndarray] = None,
    ) -> None:
        """Save a complete trajectory with compressed chunked datasets [M]."""
        with self._get_locks():
            with h5py.File(str(self.path), "a") as h5:
                trajs_grp = h5.require_group("trajectories")
                if traj_id in trajs_grp:
                    del trajs_grp[traj_id]

                grp = trajs_grp.create_group(traj_id)

                coords_arr = np.asarray(coordinates, dtype=np.float64)
                if coords_arr.ndim == 2:
                    coords_arr = coords_arr[np.newaxis, ...]

                forces_arr = np.asarray(forces, dtype=np.float64)
                if forces_arr.ndim == 2:
                    forces_arr = forces_arr[np.newaxis, ...]

                energy_arr = np.asarray(energy, dtype=np.float64)
                if energy_arr.ndim == 0:
                    energy_arr = energy_arr[np.newaxis]

                stress_arr = None
                if stress is not None:
                    stress_arr = np.asarray(stress, dtype=np.float64)
                    if stress_arr.ndim == 1:
                        stress_arr = stress_arr[np.newaxis, ...]

                dipole_arr = None
                if dipole is not None:
                    dipole_arr = np.asarray(dipole, dtype=np.float64)
                    if dipole_arr.ndim == 1:
                        dipole_arr = dipole_arr[np.newaxis, ...]

                pol_arr = None
                if polarizability is not None:
                    pol_arr = np.asarray(polarizability, dtype=np.float64)
                    if pol_arr.ndim == 2:
                        pol_arr = pol_arr[np.newaxis, ...]

                self._write_trajectory_datasets(
                    grp=grp,
                    coords_arr=coords_arr,
                    forces_arr=forces_arr,
                    energy_arr=energy_arr,
                    atomic_numbers=atomic_numbers,
                    monoisotopic_masses=monoisotopic_masses,
                    stress_arr=stress_arr,
                    dipole_arr=dipole_arr,
                    pol_arr=pol_arr,
                )

    def append_frame(
        self,
        traj_id: str,
        coordinates: np.ndarray,
        forces: np.ndarray,
        energy: float,
        atomic_numbers: np.ndarray,
        monoisotopic_masses: np.ndarray,
        stress: Optional[np.ndarray] = None,
        dipole: Optional[np.ndarray] = None,
        polarizability: Optional[np.ndarray] = None,
    ) -> None:
        """Append a single trajectory frame to an existing or new trajectory [M]."""
        with self._get_locks():
            with h5py.File(str(self.path), "a") as h5:
                trajs_grp = h5.require_group("trajectories")
                if traj_id not in trajs_grp:
                    grp = trajs_grp.create_group(traj_id)

                    coords_arr = np.asarray(coordinates, dtype=np.float64)
                    if coords_arr.ndim == 2:
                        coords_arr = coords_arr[np.newaxis, ...]

                    forces_arr = np.asarray(forces, dtype=np.float64)
                    if forces_arr.ndim == 2:
                        forces_arr = forces_arr[np.newaxis, ...]

                    energy_arr = np.array([energy], dtype=np.float64)

                    stress_arr = None
                    if stress is not None:
                        stress_arr = np.asarray(stress, dtype=np.float64)
                        if stress_arr.ndim == 1:
                            stress_arr = stress_arr[np.newaxis, ...]

                    dipole_arr = None
                    if dipole is not None:
                        dipole_arr = np.asarray(dipole, dtype=np.float64)
                        if dipole_arr.ndim == 1:
                            dipole_arr = dipole_arr[np.newaxis, ...]

                    pol_arr = None
                    if polarizability is not None:
                        pol_arr = np.asarray(polarizability, dtype=np.float64)
                        if pol_arr.ndim == 2:
                            pol_arr = pol_arr[np.newaxis, ...]

                    self._write_trajectory_datasets(
                        grp=grp,
                        coords_arr=coords_arr,
                        forces_arr=forces_arr,
                        energy_arr=energy_arr,
                        atomic_numbers=atomic_numbers,
                        monoisotopic_masses=monoisotopic_masses,
                        stress_arr=stress_arr,
                        dipole_arr=dipole_arr,
                        pol_arr=pol_arr,
                    )
                    return

                grp = trajs_grp[traj_id]
                c_dset = grp["coordinates"]
                cur_t = c_dset.shape[0]
                new_t = cur_t + 1

                c_dset.resize((new_t, c_dset.shape[1], 3))
                c_dset[cur_t] = np.asarray(coordinates, dtype=np.float64)

                f_dset = grp["forces"]
                f_dset.resize((new_t, f_dset.shape[1], 3))
                f_dset[cur_t] = np.asarray(forces, dtype=np.float64)

                e_dset = grp["energy"]
                e_dset.resize((new_t,))
                e_dset[cur_t] = float(energy)

                if stress is not None and "stress" in grp:
                    s_dset = grp["stress"]
                    s_dset.resize((new_t, 6))
                    s_dset[cur_t] = np.asarray(stress, dtype=np.float64)

                if dipole is not None and "dipole" in grp:
                    d_dset = grp["dipole"]
                    d_dset.resize((new_t, 3))
                    d_dset[cur_t] = np.asarray(dipole, dtype=np.float64)

                if polarizability is not None and "polarizability" in grp:
                    p_dset = grp["polarizability"]
                    p_dset.resize((new_t, 3, 3))
                    p_dset[cur_t] = np.asarray(polarizability, dtype=np.float64)

    def load_trajectory(self, traj_id: str) -> Dict[str, np.ndarray]:
        """Load full trajectory datasets into memory as numpy arrays [M]."""
        with self._get_locks():
            with h5py.File(str(self.path), "r") as h5:
                if "trajectories" not in h5 or traj_id not in h5["trajectories"]:
                    raise KeyError(f"Trajectory '{traj_id}' not found in {self.path}")

                grp = h5["trajectories"][traj_id]
                result: Dict[str, np.ndarray] = {}
                for key in grp.keys():
                    result[key] = np.array(grp[key])
                return result

    def list_trajectories(self) -> List[str]:
        """List all trajectory identifiers currently stored in the file [M]."""
        with self._get_locks():
            if not self.path.exists():
                return []
            with h5py.File(str(self.path), "r") as h5:
                if "trajectories" not in h5:
                    return []
                return list(h5["trajectories"].keys())
