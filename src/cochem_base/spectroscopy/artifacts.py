"""Read geometry-bound Cartesian Hessians for electronic-cost-free isotope analysis."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np

from .isotopologue import IsotopologueSpectroscopyEngine


@dataclass(frozen=True)
class HessianArtifact:
    symbols: tuple[str, ...]
    coordinates_angstrom: np.ndarray
    hessian_hartree_bohr2: np.ndarray
    source: str
    sha256: str
    path: Path


def load_hessian_artifact(path: str | Path) -> HessianArtifact:
    """Load an ORCA .hess, or an explicitly unit-labelled .npz/.h5 bundle.

    Bundles contain ``symbols``, ``coordinates_angstrom``,
    ``hessian_hartree_bohr2`` and scalar ``source`` datasets. Geometry travels
    with the Hessian so a matrix from another geometry cannot be silently reused.
    Pickled NumPy objects and absent provenance are rejected.
    """
    from cochem_base.core.cochem_core_registry_manager import AtomicFileLock

    path = Path(path).expanduser().resolve(strict=True)
    with AtomicFileLock(str(path) + ".lock", timeout=10.0):
        return _load_locked_artifact(path)


def _load_locked_artifact(path: Path) -> HessianArtifact:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix.lower() == ".hess":
        from cochem_base.chain.chain import parse_orca_hessian
        from scipy.constants import physical_constants

        data = parse_orca_hessian(path)
        if data is None or not data["atoms"]:
            raise ValueError("ORCA Hessian must include its $atoms geometry block")
        symbols = tuple(atom["symbol"] for atom in data["atoms"])
        bohr_angstrom = physical_constants["Bohr radius"][0] * 1e10
        coordinates = np.asarray([atom["coords"] for atom in data["atoms"]]) * bohr_angstrom
        hessian = data["hessian"]
        source = f"ORCA Cartesian Hessian: {path.name}"
    else:
        required = ("symbols", "coordinates_angstrom", "hessian_hartree_bohr2", "source")
        if path.suffix.lower() == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                if not all(key in archive for key in required):
                    raise ValueError("Hessian bundle requires datasets: " + ", ".join(required))
                data = {key: archive[key] for key in required}
        elif path.suffix.lower() in {".h5", ".hdf5"}:
            import h5py

            with h5py.File(path, "r", libver="latest", swmr=True) as archive:
                if not all(key in archive for key in required):
                    raise ValueError("Hessian bundle requires datasets: " + ", ".join(required))
                data = {key: archive[key][()] for key in required}
        else:
            raise ValueError("Use an ORCA .hess file or a unit-labelled .npz/.h5 Hessian bundle")
        raw_symbols = np.asarray(data["symbols"])
        if raw_symbols.ndim != 1:
            raise ValueError("Hessian symbols must be a one-dimensional array")
        symbols = tuple(item.decode("utf-8") if isinstance(item, bytes) else str(item) for item in raw_symbols)
        coordinates = np.asarray(data["coordinates_angstrom"], dtype=float)
        hessian = np.asarray(data["hessian_hartree_bohr2"], dtype=float)
        raw_source = np.asarray(data["source"])
        if raw_source.ndim != 0:
            raise ValueError("Hessian source must be a scalar provenance description")
        source = raw_source.item()
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Hessian source provenance is required")
    # Canonical validator checks shape, symmetry, finite values and nuclide masses.
    IsotopologueSpectroscopyEngine(list(symbols), coordinates, hessian)
    coordinates.setflags(write=False)
    hessian.setflags(write=False)
    return HessianArtifact(symbols, coordinates, hessian, source, digest, path)
