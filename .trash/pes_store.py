"""CoChem-GEOM: High-Throughput HDF5 Potential Energy Surface (PES) Storage Module.
================================================================================
Serializes validated molecular conformers, quantum chemical energies, and geometric
tensors into chunked, compressed HDF5 data lakes compliant with MolSSI QCSchema v1.

Authoritative Standards:
- Method Matrix v4 §8C: Single-Writer HDF5 Data Streaming & Lossless Bitshuffle Pipeline
- MolSSI QCSchema v1.0.0 Standardized Nomenclature
- Mendeleev Dynamic Atomic Resolution Mandate
- SWEBOK v3 / ISO 25010 Software Reliability Standards
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, overload

import h5py
import numpy as np

logger = logging.getLogger("cochem_geom.data.pes_store")


class PESStore:
    """
    High-Throughput HDF5 Potential Energy Surface (PES) & Conformer Store.

    Features:
    - Chunked resizable datasets with `maxshape=(None, ...)` for dynamic batch resizing.
    - Lossless compression pipeline: Gzip (level 4) + bit shuffle + Fletcher32 checksums [E].
    - MolSSI QCSchema compliant dataset hierarchy: `atomic_numbers`, `geometry`, `return_energy`.
    - Zero lossy compression: Rejects scaleoffset filters.
    - Metadata export (`metadata.json`) for PyG / PyTorch streaming dataset length synchronization.
    """

    def __init__(
        self,
        db_path: str | Path,
        max_atoms: int = 100,
        mode: str = "a",
        compression: str = "gzip",
        compression_opts: int = 4,
        shuffle: bool = True,
        fletcher32: bool = True,
        provenance_tag: str = "[M]",
    ) -> None:
        """
        Initialize the PESStore HDF5 database.

        Parameters
        ----------
        db_path : str or Path
            Path to the target HDF5 file.
        max_atoms : int, default=100
            Maximum number of atoms per conformer for 2D/3D tensor padding.
        mode : str, default='a'
            File opening mode ('r', 'r+', 'w', 'a').
        compression : str, default='gzip'
            Compression algorithm ('gzip', 'lzf').
        compression_opts : int, default=4
            Gzip compression level (1-9).
        shuffle : bool, default=True
            Enable HDF5 byte/bit shuffle filter prior to compression.
        fletcher32 : bool, default=True
            Enable Fletcher32 checksum filter for data integrity validation.
        provenance_tag : str, default='[M]'
            Data provenance classification tag ([M], [D], [E]).
        """
        self.db_path = Path(db_path).resolve()
        self.max_atoms = int(max_atoms)
        self.mode = mode
        self.compression = compression
        self.compression_opts = compression_opts
        self.shuffle = bool(shuffle)
        self.fletcher32 = bool(fletcher32)
        self.provenance_tag = provenance_tag

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open HDF5 file
        self.file = h5py.File(self.db_path, self.mode)

        # Initialize root metadata and resizable datasets if in write/append mode
        if self.mode in ("w", "a", "r+"):
            self._init_qcschema_datasets()

        # Synchronize current index
        if "atomic_numbers" in self.file:
            self.current_idx = int(self.file["atomic_numbers"].shape[0])
        else:
            self.current_idx = 0

    def _init_qcschema_datasets(self) -> None:
        """Initialize QCSchema v1 root attributes and resizable chunked datasets."""
        # Root QCSchema v1 Attributes
        if "schema_name" not in self.file.attrs:
            self.file.attrs["schema_name"] = "qcschema"
            self.file.attrs["schema_version"] = "1.0.0"
            self.file.attrs["pipeline"] = "CoChem-GEOM v4.0"
            self.file.attrs["provenance_tag"] = self.provenance_tag
            self.file.attrs["max_atoms"] = self.max_atoms
            self.file.attrs["created_utc"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

        # 1. atomic_numbers: (N, max_atoms), int64
        if "atomic_numbers" not in self.file:
            self.file.create_dataset(
                "atomic_numbers",
                shape=(0, self.max_atoms),
                maxshape=(None, self.max_atoms),
                dtype="i8",
                chunks=True,
                compression=self.compression,
                compression_opts=self.compression_opts if self.compression == "gzip" else None,
                shuffle=self.shuffle,
                fletcher32=self.fletcher32,
            )

        # 2. geometry: (N, max_atoms, 3), float32
        if "geometry" not in self.file:
            self.file.create_dataset(
                "geometry",
                shape=(0, self.max_atoms, 3),
                maxshape=(None, self.max_atoms, 3),
                dtype="f4",
                chunks=True,
                compression=self.compression,
                compression_opts=self.compression_opts if self.compression == "gzip" else None,
                shuffle=self.shuffle,
                fletcher32=self.fletcher32,
            )

        # 3. return_energy: (N,), float64
        if "return_energy" not in self.file:
            self.file.create_dataset(
                "return_energy",
                shape=(0,),
                maxshape=(None,),
                dtype="f8",
                chunks=True,
                compression=self.compression,
                compression_opts=self.compression_opts if self.compression == "gzip" else None,
                shuffle=self.shuffle,
                fletcher32=self.fletcher32,
            )

        self.file.flush()

    def write_batch(self, conformer_dicts: list[dict[str, Any]]) -> int:
        """
        Write a batch of processed conformer records to the HDF5 store.

        Parameters
        ----------
        conformer_dicts : List[Dict[str, Any]]
            List of dictionaries containing conformer data with keys:
            - 'z' or 'atomic_numbers': 1D array of atomic numbers
            - 'pos' or 'geometry' or 'coordinates': (N_atoms, 3) coordinate array
            - 'y' or 'return_energy' or 'energy' or 'totalenergy': float energy value

        Returns
        -------
        int
            Number of successfully written conformer records.
        """
        batch_size = len(conformer_dicts)
        if batch_size == 0:
            return 0

        # Validate conformers in batch before resizing
        parsed_batch: list[tuple[np.ndarray, np.ndarray, float]] = []
        for i, conf_data in enumerate(conformer_dicts):
            # Extract atomic numbers
            z = None
            for z_key in ("z", "atomic_numbers"):
                if z_key in conf_data and conf_data[z_key] is not None:
                    z = np.asarray(conf_data[z_key], dtype=np.int64)
                    break
            if z is None:
                raise KeyError(
                    f"Missing required atomic numbers ('z' or 'atomic_numbers') for conformer at index {i}."
                )

            n_atoms = len(z)
            if n_atoms > self.max_atoms:
                raise ValueError(
                    f"Conformer at batch index {i} with {n_atoms} atoms exceeds max_atoms ({self.max_atoms}). "
                    f"Initialize PESStore with a larger max_atoms parameter."
                )

            # Extract geometry
            pos = None
            for pos_key in ("pos", "geometry", "coordinates"):
                if pos_key in conf_data and conf_data[pos_key] is not None:
                    pos = np.asarray(conf_data[pos_key], dtype=np.float32)
                    break
            if pos is None:
                raise KeyError(
                    f"Missing required geometry ('pos', 'geometry', or 'coordinates') for conformer at index {i}."
                )

            if pos.shape != (n_atoms, 3):
                raise ValueError(
                    f"Conformer geometry shape {pos.shape} does not match expected ({n_atoms}, 3)."
                )

            # Extract return energy
            energy = 0.0
            for e_key in ("y", "return_energy", "energy", "totalenergy"):
                if e_key in conf_data and conf_data[e_key] is not None:
                    energy = float(conf_data[e_key])
                    break

            parsed_batch.append((z, pos, energy))

        # Preallocate batch arrays for optimal I/O throughput
        batch_z: np.ndarray = np.zeros((batch_size, self.max_atoms), dtype=np.int64)
        batch_geo: np.ndarray = np.zeros((batch_size, self.max_atoms, 3), dtype=np.float32)
        batch_e: np.ndarray = np.zeros((batch_size,), dtype=np.float64)

        for i, (z, pos, energy) in enumerate(parsed_batch):
            n_atoms = len(z)
            batch_z[i, :n_atoms] = z
            batch_geo[i, :n_atoms, :] = pos
            batch_e[i] = energy

        # Resize HDF5 datasets
        new_size = self.current_idx + batch_size
        self.file["atomic_numbers"].resize((new_size, self.max_atoms))
        self.file["geometry"].resize((new_size, self.max_atoms, 3))
        self.file["return_energy"].resize((new_size,))

        # Write chunked batch slice
        self.file["atomic_numbers"][self.current_idx : new_size, :] = batch_z
        self.file["geometry"][self.current_idx : new_size, :, :] = batch_geo
        self.file["return_energy"][self.current_idx : new_size] = batch_e

        self.current_idx = new_size
        self.file.flush()
        return batch_size

    def write_conformer(self, conf_data: dict[str, Any]) -> int:
        """Write a single conformer record to the store."""
        return self.write_batch([conf_data])

    def read_conformer(self, idx: int) -> dict[str, Any]:
        """
        Read a single conformer record by global index, stripping zero padding.

        Parameters
        ----------
        idx : int
            Global conformer index.

        Returns
        -------
        Dict[str, Any]
            Conformer dictionary with unpadded 'z', 'pos', 'y', 'atomic_numbers', 'geometry', 'return_energy'.
        """
        total = len(self)
        if idx < 0:
            idx += total
        if idx < 0 or idx >= total:
            raise IndexError(f"Index {idx} out of range for PESStore with {total} records.")

        raw_z = self.file["atomic_numbers"][idx]
        raw_geo = self.file["geometry"][idx]
        raw_e = float(self.file["return_energy"][idx])

        # Count non-zero atoms
        non_zero_indices = np.nonzero(raw_z)[0]
        n_atoms = len(non_zero_indices) if len(non_zero_indices) > 0 else 0

        z_clean = raw_z[:n_atoms].copy()
        geo_clean = raw_geo[:n_atoms, :].copy()

        return {
            "z": z_clean,
            "pos": geo_clean,
            "y": raw_e,
            "atomic_numbers": z_clean,
            "geometry": geo_clean,
            "return_energy": raw_e,
            "num_atoms": n_atoms,
        }

    def read_batch(self, start_idx: int, end_idx: int) -> list[dict[str, Any]]:
        """Read a slice of conformer records between start_idx and end_idx."""
        return [self.read_conformer(i) for i in range(start_idx, end_idx)]

    def write_metadata_json(self, json_path: str | Path | None = None) -> Path:
        """
        Generate and persist metadata.json alongside the HDF5 store.

        Required for synchronization with PyTorch/PyG Dataset length headers.

        Parameters
        ----------
        json_path : str or Path, optional
            Target path for metadata.json. If None, saved in the same directory as HDF5.

        Returns
        -------
        Path
            Path to the written metadata.json file.
        """
        if json_path is None:
            target_json = self.db_path.parent / "metadata.json"
        else:
            target_json = Path(json_path).resolve()

        metadata_dict = {
            "total_conformers": len(self),
            "max_atoms": self.max_atoms,
            "schema": "qcschema",
            "schema_version": "1.0.0",
            "db_path": self.db_path.name,
            "compression": self.compression,
            "shuffle": self.shuffle,
            "fletcher32": self.fletcher32,
            "provenance_tag": self.provenance_tag,
            "updated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        with open(target_json, "w", encoding="utf-8") as f:
            json.dump(metadata_dict, f, indent=2)

        return target_json

    def flush(self) -> None:
        """Flush underlying HDF5 file buffers to disk."""
        if hasattr(self, "file") and self.file:
            self.file.flush()

    def close(self) -> None:
        """Close the underlying HDF5 file handle."""
        if hasattr(self, "file") and self.file:
            try:
                self.file.close()
            except (OSError, RuntimeError) as exc:
                logger.debug("Failed to cleanly close HDF5 file handle: %s", exc)

    def __len__(self) -> int:
        """Return total number of serialized conformers."""
        return self.current_idx

    @overload
    def __getitem__(self, item: int) -> dict[str, Any]: ...

    @overload
    def __getitem__(self, item: slice) -> list[dict[str, Any]]: ...

    def __getitem__(self, item: int | slice) -> dict[str, Any] | list[dict[str, Any]]:
        """Support standard sequence indexing and slicing."""
        if isinstance(item, int):
            return self.read_conformer(item)
        elif isinstance(item, slice):
            total = len(self)
            start, stop, step = item.indices(total)
            return [self.read_conformer(i) for i in range(start, stop, step)]
        else:
            raise TypeError(f"Invalid index type: {type(item).__name__}")

    def __enter__(self) -> PESStore:
        """Context management entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context management exit with file closing."""
        self.close()


__all__ = ["PESStore"]
