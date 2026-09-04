"""Thread-Safe Persistence & SWMR Telemetry with Append-Only WAL (REQ-MOB-003 & REQ-MOB-004).

Implements single-writer/multiple-reader (SWMR) HDF5 storage with pre-allocated
chunked datasets, cross-process OS-level file locking via filelock.FileLock,
cryptographic SHA-256 state hashing, and crash recovery replay.
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
import h5py
import numpy as np


@dataclass
class WALRecord:
    """Immutable Write-Ahead Log entry with cryptographic hash chain."""
    lsn: int
    timestamp: float
    event_type: str
    payload: Dict[str, Any]
    prev_hash: str
    record_hash: str

    @classmethod
    def create(
        cls,
        lsn: int,
        event_type: str,
        payload: Dict[str, Any],
        prev_hash: str,
        timestamp: Optional[float] = None,
    ) -> WALRecord:
        ts = timestamp if timestamp is not None else time.time()
        serialized_payload = json.dumps(payload, sort_keys=True)
        hash_input = f"{lsn}:{ts:.6f}:{event_type}:{prev_hash}:{serialized_payload}"
        rec_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        return cls(
            lsn=lsn,
            timestamp=ts,
            event_type=event_type,
            payload=payload,
            prev_hash=prev_hash,
            record_hash=rec_hash,
        )

    def verify_hash(self) -> bool:
        """Verify the cryptographic SHA-256 digest of this record."""
        serialized_payload = json.dumps(self.payload, sort_keys=True)
        hash_input = f"{self.lsn}:{self.timestamp:.6f}:{self.event_type}:{self.prev_hash}:{serialized_payload}"
        expected = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        return expected == self.record_hash


class TelemetryWAL:
    """Append-only Write-Ahead Log secured with OS-level file locks and SHA-256 chaining."""

    GENESIS_HASH = "0" * 64

    def __init__(self, wal_path: Union[str, Path], lock_timeout: float = 10.0) -> None:
        self.wal_path = Path(wal_path).resolve()
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.wal_path.with_suffix(".lock")
        self.lock = filelock.FileLock(str(self.lock_path), timeout=lock_timeout)
        self._thread_lock = threading.RLock()
        self._last_lsn = 0
        self._last_hash = self.GENESIS_HASH
        self._initialize_state()

    def _initialize_state(self) -> None:
        """Scan existing WAL on disk to determine highest LSN and latest hash."""
        with self._thread_lock:
            with self.lock:
                if not self.wal_path.exists():
                    self.wal_path.touch(exist_ok=True)
                    return

                records = self._read_all_unlocked()
                if records:
                    self._last_lsn = records[-1].lsn
                    self._last_hash = records[-1].record_hash

    def append(self, event_type: str, payload: Dict[str, Any]) -> WALRecord:
        """Thread-safe and process-safe append to the WAL."""
        with self._thread_lock:
            with self.lock:
                # Re-sync in case another process appended
                records = self._read_all_unlocked()
                if records:
                    self._last_lsn = records[-1].lsn
                    self._last_hash = records[-1].record_hash
                else:
                    self._last_lsn = 0
                    self._last_hash = self.GENESIS_HASH

                next_lsn = self._last_lsn + 1
                record = WALRecord.create(
                    lsn=next_lsn,
                    event_type=event_type,
                    payload=payload,
                    prev_hash=self._last_hash,
                )

                line = json.dumps(asdict(record)) + "\n"
                with open(self.wal_path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())

                self._last_lsn = next_lsn
                self._last_hash = record.record_hash
                return record

    def read_records(self) -> List[WALRecord]:
        """Read all validated records from the WAL."""
        with self._thread_lock:
            with self.lock:
                return self._read_all_unlocked()

    def _read_all_unlocked(self) -> List[WALRecord]:
        if not self.wal_path.exists() or self.wal_path.stat().st_size == 0:
            return []

        records: List[WALRecord] = []
        expected_prev_hash = self.GENESIS_HASH

        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    data = json.loads(clean_line)
                    record = WALRecord(**data)
                    if not record.verify_hash():
                        raise ValueError(f"Corrupted record hash at line {line_idx}, LSN {record.lsn}")
                    if record.prev_hash != expected_prev_hash:
                        raise ValueError(
                            f"Broken hash chain at line {line_idx}, LSN {record.lsn}: "
                            f"expected {expected_prev_hash}, got {record.prev_hash}"
                        )
                    expected_prev_hash = record.record_hash
                    records.append(record)
                except json.JSONDecodeError:
                    # Incomplete or torn write at end of file
                    break


        return records

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Verify the full hash chain integrity of the WAL file."""
        try:
            records = self.read_records()
            return True, f"WAL valid with {len(records)} records."
        except Exception as exc:
            return False, str(exc)

    def compact_checkpoint(self, up_to_lsn: int, checkpoint_state: Dict[str, Any]) -> WALRecord:
        """Compact WAL by archiving or rewriting records after a verified checkpoint."""
        with self._thread_lock:
            with self.lock:
                records = self._read_all_unlocked()
                remaining = [r for r in records if r.lsn > up_to_lsn]

                # Create checkpoint record
                ckpt_record = WALRecord.create(
                    lsn=up_to_lsn + 1,
                    event_type="CHECKPOINT",
                    payload=checkpoint_state,
                    prev_hash=self.GENESIS_HASH,
                )

                # Rewrite WAL starting with checkpoint record followed by remaining records
                new_records = [ckpt_record]
                curr_prev_hash = ckpt_record.record_hash

                for r in remaining:
                    re_chained = WALRecord.create(
                        lsn=r.lsn,
                        event_type=r.event_type,
                        payload=r.payload,
                        prev_hash=curr_prev_hash,
                        timestamp=r.timestamp,
                    )
                    curr_prev_hash = re_chained.record_hash
                    new_records.append(re_chained)

                temp_path = self.wal_path.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    for rec in new_records:
                        f.write(json.dumps(asdict(rec)) + "\n")
                    f.flush()
                    os.fsync(f.fileno())

                os.replace(temp_path, self.wal_path)
                self._last_lsn = new_records[-1].lsn
                self._last_hash = new_records[-1].record_hash
                return ckpt_record


class SWMRHDF5Writer:
    """Thread-safe Single-Writer/Multiple-Reader (SWMR) HDF5 telemetry store."""

    def __init__(self, h5_path: Union[str, Path], enable_swmr: bool = True) -> None:
        self.h5_path = Path(h5_path).resolve()
        self.h5_path.parent.mkdir(parents=True, exist_ok=True)
        self.enable_swmr = enable_swmr
        self._lock = threading.RLock()
        self._h5_file: Optional[h5py.File] = None
        self._init_hdf5_schema()

    def _init_hdf5_schema(self) -> None:
        """Initialize HDF5 structure with chunked pre-allocated datasets."""
        with self._lock:
            mode = "a" if self.h5_path.exists() else "w"
            with h5py.File(self.h5_path, mode, libver="latest") as f:
                # Setup telemetry datasets
                if "coordinates" not in f:
                    f.create_dataset(
                        "coordinates",
                        shape=(0, 3),
                        maxshape=(None, 3),
                        chunks=(128, 3),
                        dtype="float64",
                    )
                if "energies" not in f:
                    f.create_dataset(
                        "energies",
                        shape=(0,),
                        maxshape=(None,),
                        chunks=(512,),
                        dtype="float64",
                    )
                if "atomic_masses" not in f:
                    f.create_dataset(
                        "atomic_masses",
                        shape=(0,),
                        maxshape=(None,),
                        chunks=(128,),
                        dtype="float64",
                    )
                if "timestamps" not in f:
                    f.create_dataset(
                        "timestamps",
                        shape=(0,),
                        maxshape=(None,),
                        chunks=(512,),
                        dtype="float64",
                    )
                if "provenance_hashes" not in f:
                    dt = h5py.string_dtype(encoding="utf-8")
                    f.create_dataset(
                        "provenance_hashes",
                        shape=(0,),
                        maxshape=(None,),
                        chunks=(64,),
                        dtype=dt,
                    )
                f.attrs["schema_version"] = "1.0.0"
                f.attrs["swmr_enabled"] = bool(self.enable_swmr)
                f.flush()

    def open(self) -> h5py.File:
        """Open HDF5 file in write mode and activate SWMR if configured."""
        with self._lock:
            if self._h5_file is None:
                self._h5_file = h5py.File(self.h5_path, "r+", libver="latest")
                if self.enable_swmr and not self._h5_file.swmr_mode:
                    try:
                        self._h5_file.swmr_mode = True
                    except (RuntimeError, OSError, ValueError) as _e:
                        # SWMR activation may fail on unsupported filesystems/drivers
                        logger.debug(f"Ignored exception: {_e}")
            return self._h5_file

    def close(self) -> None:
        """Flush and close the open HDF5 file."""
        with self._lock:
            if self._h5_file is not None:
                try:
                    self._h5_file.flush()
                    self._h5_file.close()
                except (RuntimeError, OSError, ValueError) as _e:
                    # Handle already closed or torn file descriptors
                    logger.debug(f"Ignored exception: {_e}")
                finally:
                    self._h5_file = None

    def append_telemetry(
        self,
        coords: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        masses: Optional[np.ndarray] = None,
        timestamp: Optional[float] = None,
        prov_hash: Optional[str] = None,
    ) -> None:
        """Append telemetry slice to chunked SWMR datasets and flush immediately."""
        with self._lock:
            f = self.open()
            ts = timestamp if timestamp is not None else time.time()

            if coords is not None:
                coords_arr = np.asarray(coords, dtype=np.float64)
                if coords_arr.ndim == 1:
                    coords_arr = coords_arr.reshape(1, -1)
                ds_coords = f["coordinates"]
                curr_len = ds_coords.shape[0]
                add_len = coords_arr.shape[0]
                ds_coords.resize((curr_len + add_len, 3))
                ds_coords[curr_len : curr_len + add_len] = coords_arr
                ds_coords.flush()

            if energy is not None:
                ds_energy = f["energies"]
                curr_len = ds_energy.shape[0]
                ds_energy.resize((curr_len + 1,))
                ds_energy[curr_len] = float(energy)
                ds_energy.flush()

            if masses is not None:
                masses_arr = np.asarray(masses, dtype=np.float64)
                ds_masses = f["atomic_masses"]
                curr_len = ds_masses.shape[0]
                add_len = masses_arr.shape[0]
                ds_masses.resize((curr_len + add_len,))
                ds_masses[curr_len : curr_len + add_len] = masses_arr
                ds_masses.flush()

            ds_ts = f["timestamps"]
            curr_ts_len = ds_ts.shape[0]
            ds_ts.resize((curr_ts_len + 1,))
            ds_ts[curr_ts_len] = float(ts)
            ds_ts.flush()

            if prov_hash is not None:
                ds_prov = f["provenance_hashes"]
                curr_prov_len = ds_prov.shape[0]
                ds_prov.resize((curr_prov_len + 1,))
                ds_prov[curr_prov_len] = str(prov_hash)
                ds_prov.flush()

            f.flush()

    def read_reader_mode(self) -> Dict[str, Any]:
        """Read current dataset contents in SWMR reader mode."""
        with h5py.File(self.h5_path, "r", libver="latest", swmr=self.enable_swmr) as f:
            return {
                "coordinates": f["coordinates"][:],
                "energies": f["energies"][:],
                "atomic_masses": f["atomic_masses"][:],
                "timestamps": f["timestamps"][:],
                "provenance_hashes": [
                    h.decode("utf-8") if isinstance(h, bytes) else str(h)
                    for h in f["provenance_hashes"][:]
                ],
            }

    def replay_wal(self, wal: TelemetryWAL) -> int:
        """Replay uncommitted WAL events into HDF5 datasets for crash recovery."""
        records = wal.read_records()
        replayed_count = 0
        for record in records:
            if record.event_type == "TELEMETRY_SAMPLE":
                coords = record.payload.get("coords")
                energy = record.payload.get("energy")
                masses = record.payload.get("masses")
                ts = record.timestamp
                prov_hash = record.record_hash
                self.append_telemetry(
                    coords=np.array(coords) if coords is not None else None,
                    energy=energy,
                    masses=np.array(masses) if masses is not None else None,
                    timestamp=ts,
                    prov_hash=prov_hash,
                )
                replayed_count += 1
        return replayed_count
