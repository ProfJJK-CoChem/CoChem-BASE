"""Publish measured scientific results to the canonical SWMR archive.

No energy, gradient, geometry or timing is inferred when an engine omitted it.
Readers use the committed row count so a crashed append is never a full result.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity
from cochem_base.core_engine.scientific_writer import scientific_writer_scope, scientific_reader_snapshot


def append_scientific_result(
    job_id: str, elements: Sequence[str], coordinates_angstrom: Any,
    energy_hartree: float, gradients: Any = None,
    metadata: dict[str, Any] | None = None, *,
    store_path: str | Path | None = None,
) -> Path:
    """Append real geometry/energy and optional Eh/bohr gradients under a job ID.

    The normal destination is the single ``complexes.h5`` selected by the core
    manager. ``store_path`` supports a caller's explicitly selected campaign store.
    Each metadata record is retained exactly; oversize documents are rejected.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", job_id):
        raise ValueError("Telemetry job ID must be a safe HDF5 component")
    symbols = list(elements)
    identity = resolve_nuclear_identity(symbols)
    symbols = list(identity.nuclides)
    masses = [get_nuclide_mass(symbol) for symbol in symbols]
    principal_masses = [get_nuclide_mass(symbol) for symbol in identity.elements]
    coordinates = np.asarray(coordinates_angstrom, dtype=float)
    if not symbols or coordinates.shape != (len(symbols), 3) or not np.isfinite(coordinates).all():
        raise ValueError("Telemetry requires finite N x 3 coordinates matching atom identities")
    energy = float(energy_hartree)
    if isinstance(energy_hartree, bool) or not np.isfinite(energy):
        raise ValueError("Telemetry requires a measured finite energy")
    gradient = None if gradients is None else np.asarray(gradients, dtype=float)
    if gradient is not None and (gradient.shape != coordinates.shape or not np.isfinite(gradient).all()):
        raise ValueError("Measured gradient must be a finite N x 3 array in Eh/bohr")
    provenance = json.dumps(metadata or {}, sort_keys=True, allow_nan=False).encode("utf-8")
    if len(provenance) > 65535:
        raise ValueError("Telemetry metadata exceeds the 65535-byte record limit")
    group_path = f"trajectories/{job_id}"
    topology = {
        "coordinates_angstrom": ((0, len(symbols), 3), (None, len(symbols), 3), (1, len(symbols), 3), np.float64),
        "energy_hartree": ((0,), (None,), (64,), np.float64),
        "metadata_json": ((0,), (None,), (1,), "S65536"),
        "gradient_record_indices": ((0,), (None,), (64,), np.int64),
        "gradients_hartree_per_bohr": ((0, len(symbols), 3), (None, len(symbols), 3), (1, len(symbols), 3), np.float64),
    }
    def initialize(manager):
        with manager.transaction("a") as archive:
            group = archive.require_group(group_path)
            if "symbols_json" in group.attrs:
                if json.loads(group.attrs["symbols_json"]) != symbols:
                    raise ValueError("Telemetry job atom identities/order cannot change between records")
            else:
                # Identity/topology are registered once, before activating the
                # writer. Active SWMR appends never create objects or attributes.
                group.attrs["symbols_json"] = json.dumps(symbols)
                group.attrs["elements_json"] = json.dumps(identity.elements)
                group.attrs["nuclear_identity_json"] = json.dumps(identity.metadata, sort_keys=True)
                group.attrs["selected_isotope_masses_u"] = masses
                group.attrs["principal_isotope_masses_u"] = principal_masses
            for name, (shape, maxshape, chunks, dtype) in topology.items():
                if name not in group:
                    group.create_dataset(name, shape=shape, maxshape=maxshape, chunks=chunks,
                                         dtype=dtype, compression="gzip", shuffle=True, fletcher32=True)
            if "committed_records" not in group:
                group.create_dataset("committed_records", data=np.int64(0))
            if "committed_gradients" not in group:
                committed = int(group["committed_records"][()])
                count = int(np.count_nonzero(group["gradient_record_indices"][:] < committed))
                if group["gradients_hartree_per_bohr"].shape[0] < count:
                    raise ValueError("Committed scientific gradients are incomplete")
                group.create_dataset("committed_gradients", data=np.int64(count))
            archive.flush()

    def append(manager, writer):
        group = writer[group_path]
        if json.loads(group.attrs["symbols_json"]) != symbols:
            raise ValueError("Telemetry job atom identities/order cannot change between records")
        committed = int(group["committed_records"][()])
        if committed < 0:
            raise ValueError("Scientific telemetry has a negative committed record count")
        # An interrupted prior append may leave uncommitted trailing buffers.
        for name in ("coordinates_angstrom", "energy_hartree", "metadata_json"):
            if len(group[name]) < committed:
                raise ValueError("Committed telemetry is incomplete")
            group[name].resize(committed, axis=0)
        published_gradients = int(group["committed_gradients"][()])
        if (published_gradients < 0 or group["gradient_record_indices"].shape[0] < published_gradients
                or group["gradients_hartree_per_bohr"].shape[0] < published_gradients):
            raise ValueError("Committed scientific gradient indices or observations are invalid")
        indices = group["gradient_record_indices"][:published_gradients]
        retained = int(np.count_nonzero(indices < committed))
        if (np.any(indices < 0) or np.any(np.diff(indices) <= 0)
                or group["gradients_hartree_per_bohr"].shape[0] < retained):
            raise ValueError("Committed scientific gradient indices or observations are invalid")
        for name in ("gradient_record_indices", "gradients_hartree_per_bohr"):
            group[name].resize(retained, axis=0)
        for name, values in (
            ("coordinates_angstrom", coordinates[None, :, :]),
            ("energy_hartree", np.asarray([energy])),
            ("metadata_json", np.asarray([provenance], dtype="S65536")),
        ):
            manager.append_swmr_chunk(name, values, group_path, writer)
        if gradient is not None:
            manager.append_swmr_chunk("gradients_hartree_per_bohr", gradient[None, :, :], group_path, writer)
            manager.append_swmr_chunk("gradient_record_indices", np.asarray([committed]), group_path, writer)
        # Publish the complete optional-gradient prefix before the record-count
        # commit. Readers cannot select newly resized but unwritten buffer rows.
        group["committed_gradients"][()] = retained + int(gradient is not None)
        group["committed_gradients"].flush()
        group["committed_records"][()] = committed + 1
        group["committed_records"].flush()
        writer.flush()
        return manager.h5_path

    # An enclosing native producer scope reuses its persistent writer. A
    # standalone caller gets an explicitly closed short session, never a handle
    # that survives until interpreter shutdown.
    with scientific_writer_scope(store_path=store_path) as store:
        return store.write(group_path, initialize, append)


def read_scientific_results(job_id: str, *, store_path: str | Path | None = None) -> dict[str, Any]:
    """Read only completely published records through the canonical SWMR reader."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", job_id):
        raise ValueError("Telemetry job ID must be a safe HDF5 component")
    with scientific_reader_snapshot(store_path=store_path):
        manager = CoChemHDF5Manager(h5_path=store_path)
        with manager.swmr_reader() as reader:
            group = reader[f"trajectories/{job_id}"]
            group["committed_records"].refresh()
            count = int(group["committed_records"][()])
            if count < 0:
                raise ValueError("Scientific telemetry has a negative committed record count")
            # Capture the commit boundary first, then refresh buffers. A later
            # commit may add rows but cannot change this snapshot's prefix.
            for dataset in group.values():
                dataset.refresh()
            if any(group[name].shape[0] < count for name in
                   ("coordinates_angstrom", "energy_hartree", "metadata_json")):
                raise ValueError("Committed telemetry is incomplete")
            gradient_count = (int(group["committed_gradients"][()]) if "committed_gradients" in group else
                              min(group["gradient_record_indices"].shape[0],
                                  group["gradients_hartree_per_bohr"].shape[0]))
            if (gradient_count < 0 or group["gradient_record_indices"].shape[0] < gradient_count
                    or group["gradients_hartree_per_bohr"].shape[0] < gradient_count):
                raise ValueError("Committed scientific gradients are incomplete")
            indices = group["gradient_record_indices"][:gradient_count]
            if np.any(indices < 0) or np.any(np.diff(indices) <= 0):
                raise ValueError("Committed scientific gradient indices are invalid")
            selected = (indices >= 0) & (indices < count)
            return {
                "elements": json.loads(group.attrs.get("elements_json", group.attrs["symbols_json"])),
                "nuclides": json.loads(group.attrs["symbols_json"]),
                "nuclear_identity": json.loads(group.attrs["nuclear_identity_json"]) if "nuclear_identity_json" in group.attrs else None,
                "selected_isotope_masses_u": group.attrs.get("selected_isotope_masses_u", group.attrs["principal_isotope_masses_u"]),
                "principal_isotope_masses_u": group.attrs["principal_isotope_masses_u"],
                "coordinates_angstrom": group["coordinates_angstrom"][:count],
                "energy_hartree": group["energy_hartree"][:count],
                "metadata": [json.loads(value.decode("utf-8")) for value in group["metadata_json"][:count]],
                "gradient_record_indices": indices[selected],
                "gradients_hartree_per_bohr": group["gradients_hartree_per_bohr"][:gradient_count][selected],
            }
