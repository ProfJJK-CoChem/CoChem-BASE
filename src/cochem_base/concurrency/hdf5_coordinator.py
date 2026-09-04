"""Two-Tier Thread-Safe and Process-Safe HDF5 Persistence Architecture.

Mandated by Method Matrix v4 §8C (Production HDF5 Store Architecture & Chunking) [M], [D].
Validates Suggestion #64:
- Tier 1 (In-Process): threading.RLock() serialization across worker threads.
- Tier 2 (Cross-Process): RWFileLock with exponential backoff.
- Atomic staging: workers write into $COCHEM_SCRATCH/chunks/chunk_<uuid>.h5.
- Central persistence coordinator merges staged chunks into $COCHEM_ARTIFACTS/campaign.h5
  under exclusive write lock with gzip+shuffle+fletcher32.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import h5py
import numpy as np

from cochem_base.concurrency.atomic_file_lock import RWFileLock
from cochem_base.schemas import HDF5PersistenceConfig

logger = logging.getLogger("cochem.concurrency.hdf5_coordinator")

_PROCESS_THREAD_LOCKS: Dict[str, threading.RLock] = {}
_PROCESS_THREAD_LOCKS_GUARD = threading.Lock()


def _get_thread_lock(path: Path) -> threading.RLock:
    norm_path = str(path.resolve())
    with _PROCESS_THREAD_LOCKS_GUARD:
        if norm_path not in _PROCESS_THREAD_LOCKS:
            _PROCESS_THREAD_LOCKS[norm_path] = threading.RLock()
        return _PROCESS_THREAD_LOCKS[norm_path]


@contextmanager
def locked_h5(
    path: Union[Path, str],
    mode: str = "r",
    config: Optional[HDF5PersistenceConfig] = None,
):
    """Two-tier thread-safe and process-safe HDF5 file opener.

    Serializes in-process threads with threading.RLock and cross-process workers with RWFileLock.
    """
    cfg = config or HDF5PersistenceConfig()
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    t_lock = _get_thread_lock(p)
    file_lock = RWFileLock(p, timeout=cfg.lock_timeout_seconds)
    timeout = cfg.lock_timeout_seconds

    if mode in ("w", "a", "r+", "w-", "x"):
        with file_lock.write_lock(timeout=timeout):
            with t_lock:
                with h5py.File(p, mode) as f:
                    yield f
    else:
        with file_lock.read_lock(timeout=timeout):
            with t_lock:
                with h5py.File(p, mode) as f:
                    yield f


class HDF5PersistenceCoordinator:
    """Centralized persistence coordinator implementing two-tier locking and chunk staging.

    Method Matrix Reference: Method Matrix v4 §8C (Production HDF5 Store Architecture & Chunking).
    Suggestion #64:
    - In-process threading.RLock
    - Cross-process RWFileLock with exponential backoff
    - Workers commit energy, gradient, and QCSchema records into isolated chunk containers in $COCHEM_SCRATCH/chunks/chunk_<uuid>.h5
    - Central coordinator merges staged chunks into primary store ($COCHEM_ARTIFACTS/campaign.h5) under exclusive write lock
    - Guarantees zero BlockingIOError / OSError: file already open for write during concurrent sweeps.
    """

    def __init__(
        self,
        campaign_path: Union[str, Path],
        config: Optional[HDF5PersistenceConfig] = None,
        complex_name: str = "",
        symbols: Sequence[str] = (),
    ) -> None:
        self.campaign_path = Path(campaign_path).resolve()
        self.config = config or HDF5PersistenceConfig()
        self.complex_name = complex_name
        self.symbols = list(symbols)
        self._init_campaign()

    def _init_campaign(self) -> None:
        with locked_h5(self.campaign_path, mode="a", config=self.config) as f:
            m = f.require_group("meta")
            if "schema_name" not in m.attrs:
                m.attrs["schema_name"] = "vdw_pes_campaign"
                m.attrs["schema_version"] = 1
                m.attrs["created_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                m.attrs["host"] = socket.gethostname()
                m.attrs["platform"] = platform.platform()
            if self.complex_name:
                m.attrs["complex"] = self.complex_name
            if self.symbols:
                m.attrs["symbols"] = json.dumps(self.symbols)
                m.attrs["n_atoms"] = len(self.symbols)

    @staticmethod
    def stage_chunk(
        scratch_dir: Union[str, Path],
        method_id: str,
        coords: Union[Sequence[Any], np.ndarray],
        energies: Union[Sequence[float], float, np.ndarray],
        *,
        chunk_id: Optional[str] = None,
        point_ids: Optional[Sequence[str]] = None,
        gradients: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: Optional[Union[Sequence[bool], bool, np.ndarray]] = None,
        wall_s: Optional[Union[Sequence[float], float, np.ndarray]] = None,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
        config: Optional[HDF5PersistenceConfig] = None,
    ) -> Path:
        """Atomically stage a single-point chunk into Ring 2 ephemeral scratch ($COCHEM_SCRATCH/chunks/chunk_<uuid>.h5)."""
        cfg = config or HDF5PersistenceConfig()
        chunks_dir = Path(scratch_dir).resolve() / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        cid = chunk_id or str(uuid.uuid4())
        chunk_path = chunks_dir / f"chunk_{cid}.h5"

        coords_arr = np.asarray(coords, dtype=np.float64)
        if coords_arr.ndim == 2:
            coords_arr = coords_arr[None, ...]
        npts, natm, spatial = coords_arr.shape
        energies_arr = np.atleast_1d(np.asarray(energies, dtype=np.float64))

        with locked_h5(chunk_path, mode="w", config=cfg) as f:
            grp = f.create_group(f"points/{method_id}")
            kw: Dict[str, Any] = {
                "chunks": (min(512, npts), natm, spatial),
                "compression": cfg.compression_filter,
                "compression_opts": cfg.compression_level,
                "shuffle": cfg.enable_shuffle,
            }
            grp.create_dataset("coordinates", data=coords_arr, **kw)

            ekw: Dict[str, Any] = {
                "chunks": (min(512, npts),),
                "compression": cfg.compression_filter,
                "compression_opts": cfg.compression_level,
                "shuffle": cfg.enable_shuffle,
                "fletcher32": cfg.enable_fletcher32,
            }
            grp.create_dataset("energy", data=energies_arr, **ekw)

            conv_arr = (
                np.ones(npts, dtype=bool)
                if converged is None
                else np.atleast_1d(np.asarray(converged, dtype=bool))
            )
            grp.create_dataset("converged", data=conv_arr)

            wall_arr = (
                np.zeros(npts, dtype=np.float64)
                if wall_s is None
                else np.atleast_1d(np.asarray(wall_s, dtype=np.float64))
            )
            grp.create_dataset("wall_s", data=wall_arr)

            pids = (
                list(point_ids)
                if point_ids is not None
                else [f"{method_id}:{cid}:{i}" for i in range(npts)]
            )
            dt_str = h5py.string_dtype(encoding="utf-8")
            grp.create_dataset("point_id", data=np.array(pids, dtype=object), dtype=dt_str)

            prov_str = json.dumps({
                "creator": creator,
                "version": version,
                "routine": routine,
                "host": socket.gethostname(),
                "platform": platform.platform(),
                "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            grp.create_dataset("provenance", data=np.array([prov_str] * npts, dtype=object), dtype=dt_str)

            if gradients is not None:
                g_arr = np.asarray(gradients, dtype=np.float64)
                if g_arr.ndim == 2:
                    g_arr = g_arr[None, ...]
                grp.create_dataset("gradient", data=g_arr, **kw)

        return chunk_path

    def merge_staged_chunks(
        self,
        scratch_dir: Optional[Union[str, Path]] = None,
        chunk_paths: Optional[Sequence[Union[str, Path]]] = None,
        purge: bool = True,
    ) -> int:
        """Central coordinator merges staged chunks into primary campaign.h5 under exclusive write lock."""
        targets: List[Path] = []
        if chunk_paths is not None:
            targets = [Path(p).resolve() for p in chunk_paths if Path(p).is_file()]
        elif scratch_dir is not None:
            chunks_dir = Path(scratch_dir).resolve() / "chunks"
            if chunks_dir.is_dir():
                targets = sorted(list(chunks_dir.glob("chunk_*.h5")))

        if not targets:
            return 0

        total_merged = 0
        with locked_h5(self.campaign_path, mode="a", config=self.config) as f:
            for s_path in targets:
                try:
                    with locked_h5(s_path, mode="r", config=self.config) as src:
                        if "points" not in src:
                            continue
                        for mid in src["points"]:
                            grp = src[f"points/{mid}"]
                            coords = grp["coordinates"][:]
                            energies = grp["energy"][:]
                            pids = [
                                s.decode("utf-8") if isinstance(s, bytes) else str(s)
                                for s in grp["point_id"][:]
                            ]
                            conv = grp["converged"][:]
                            wall = grp["wall_s"][:] if "wall_s" in grp else None
                            grads = grp["gradient"][:] if "gradient" in grp else None
                            prov = grp["provenance"][:] if "provenance" in grp else None

                            self._append_to_master(
                                f, mid, coords, energies, pids, conv, wall, grads, prov
                            )
                            total_merged += len(energies)
                except Exception as e:
                    logger.error(f"Error merging staged chunk {s_path}: {e}")
                    raise RuntimeError(f"Chunk merge failure on {s_path}") from e

        if purge:
            for p in targets:
                try:
                    p.unlink(missing_ok=True)
                except OSError as e:
                    logger.warning(f"Could not purge staged chunk {p}: {e}")

        return total_merged

    def _append_to_master(
        self,
        f: h5py.File,
        mid: str,
        coords: np.ndarray,
        energies: np.ndarray,
        pids: Sequence[str],
        conv: np.ndarray,
        wall: Optional[np.ndarray],
        grads: Optional[np.ndarray],
        prov: Optional[np.ndarray],
    ) -> None:
        npts, natm, spatial = coords.shape
        grp = f.require_group(f"points/{mid}")
        cfg = self.config
        dt_str = h5py.string_dtype(encoding="utf-8")

        def _get_or_create(name: str, shape_tail: tuple[int, ...], dtype: Any, checksum: bool = False):
            if name in grp:
                return grp[name]
            kw: Dict[str, Any] = {
                "shape": (0,) + shape_tail,
                "maxshape": (None,) + shape_tail,
                "dtype": dtype,
                "chunks": (512,) + shape_tail,
            }
            if dtype != dt_str:
                kw.update(
                    compression=cfg.compression_filter,
                    compression_opts=cfg.compression_level,
                    shuffle=cfg.enable_shuffle,
                )
                if checksum:
                    kw["fletcher32"] = cfg.enable_fletcher32
            return grp.create_dataset(name, **kw)

        def _append(ds: h5py.Dataset, block: np.ndarray) -> None:
            c = ds.shape[0]
            ds.resize(c + len(block), axis=0)
            ds[c:] = block

        ds_coords = _get_or_create("coordinates", (natm, spatial), np.float64)
        _append(ds_coords, coords)

        ds_energy = _get_or_create("energy", (), np.float64, checksum=True)
        _append(ds_energy, energies)

        ds_conv = _get_or_create("converged", (), np.bool_)
        _append(ds_conv, conv)

        if wall is not None:
            ds_wall = _get_or_create("wall_s", (), np.float64)
            _append(ds_wall, wall)

        ds_pids = _get_or_create("point_id", (), dt_str)
        _append(ds_pids, np.array(pids, dtype=object))

        if prov is not None:
            ds_prov = _get_or_create("provenance", (), dt_str)
            prov_clean = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in prov]
            _append(ds_prov, np.array(prov_clean, dtype=object))

        if grads is not None:
            ds_grad = _get_or_create("gradient", (natm, spatial), np.float64)
            _append(ds_grad, grads)
