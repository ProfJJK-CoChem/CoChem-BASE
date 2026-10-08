#!/usr/bin/env python3
"""Run TORQ's installed rigid-geometry analysis in its isolated environment.

This is a file exchange adapter, not an optimizer or an electronic-structure
engine. Invoke it with the module environment's Python and ``-I``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

_SYMBOL = re.compile(r"(?:[1-9][0-9]{0,2})?[A-Z][a-z]?\Z")
_MAX_ATOMS = 2000
_MAX_INPUT_BYTES = 2_000_000


def read_xyz(path: Path) -> tuple[list[str], list[list[float]], str]:
    """Read one complete Cartesian XYZ geometry, with coordinates in angstrom."""
    if not path.is_file():
        raise ValueError("The input artifact must be a regular XYZ file.")
    if path.stat().st_size > _MAX_INPUT_BYTES:
        raise ValueError("The XYZ artifact exceeds the 2 MB input limit.")
    raw = path.read_bytes()
    lines = raw.decode("utf-8-sig").splitlines()
    if len(lines) < 3 or not re.fullmatch(r"[1-9][0-9]*", lines[0].strip()):
        raise ValueError("XYZ must start with a positive atom count and a comment line.")
    count = int(lines[0].strip())
    if count < 2 or count > _MAX_ATOMS:
        raise ValueError(f"Rigid-rotor analysis requires 2 to {_MAX_ATOMS} atoms.")
    if len(lines) < count + 2 or any(line.strip() for line in lines[count + 2 :]):
        raise ValueError("XYZ must contain exactly the declared number of atom rows.")
    symbols: list[str] = []
    coordinates: list[list[float]] = []
    for number, line in enumerate(lines[2 : count + 2], start=3):
        fields = line.split()
        if len(fields) != 4 or not _SYMBOL.fullmatch(fields[0]):
            raise ValueError(f"Invalid XYZ atom row {number}; expected symbol and three coordinates.")
        try:
            position = [float(value) for value in fields[1:]]
        except ValueError as exc:
            raise ValueError(f"Invalid numeric coordinate on XYZ row {number}.") from exc
        if not all(math.isfinite(value) for value in position):
            raise ValueError(f"Nonfinite coordinate on XYZ row {number}.")
        symbols.append(fields[0])
        coordinates.append(position)
    for index, position in enumerate(coordinates):
        for previous in coordinates[:index]:
            if math.dist(position, previous) < 1e-8:
                raise ValueError("Two atoms occupy the same position; rigid-rotor input is invalid.")
    return symbols, coordinates, hashlib.sha256(raw).hexdigest()


def _publish_json(path: Path, payload: dict[str, Any]) -> None:
    """Publish a complete strict JSON file atomically, without overwriting one."""
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".torq-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # An atomic link fails if the destination already exists, including a
        # dangling symlink. It cannot replace an artifact created concurrently.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def analyze(artifact: Path) -> dict[str, Any]:
    symbols, positions, digest = read_xyz(artifact)
    import Libraries.cochem_torq_alignment as provider
    import mendeleev
    import numpy as np
    from scipy.constants import atomic_mass, h

    geometry = np.asarray(positions, dtype=np.float64)
    native = provider.EckartAligner.align_molecule(
        symbols,
        geometry,
        metadata={"input_sha256": digest, "coordinate_unit": "angstrom"},
    )
    result = native.to_dict()
    masses = np.asarray(result["exact_masses"], dtype=np.float64)
    aligned = np.asarray(result["aligned_geometry"], dtype=np.float64)
    rotation = np.asarray(result["rotation_matrix"], dtype=np.float64)
    center = np.asarray(result["com_vector"], dtype=np.float64)
    moments = np.asarray(result["principal_moments"], dtype=np.float64)
    if (
        result["symbols"] != symbols
        or masses.shape != (len(symbols),)
        or not np.isfinite(masses).all()
        or not (masses > 0).all()
        or aligned.shape != geometry.shape
        or not np.isfinite(aligned).all()
        or rotation.shape != (3, 3)
        or not np.isfinite(rotation).all()
        or center.shape != (3,)
        or not np.isfinite(center).all()
        or moments.shape != (3,)
        or not np.isfinite(moments).all()
        or (moments < -1e-9).any()
    ):
        raise ValueError("TORQ returned invalid geometry, masses, or principal-axis data.")
    isotope_masses: dict[str, float] = {}
    for symbol, observed_mass in zip(symbols, masses, strict=True):
        if symbol not in isotope_masses:
            normalized = {"D": "2H", "T": "3H"}.get(symbol, symbol)
            match = re.fullmatch(r"([0-9]*)([A-Z][a-z]?)", normalized)
            assert match is not None
            mass_number, element_symbol = match.groups()
            isotopes = mendeleev.element(element_symbol).isotopes
            if mass_number:
                candidates = [item for item in isotopes if item.mass_number == int(mass_number)]
            else:
                candidates = [item for item in isotopes if item.abundance is not None and item.abundance > 0]
                candidates.sort(key=lambda item: (item.abundance, item.mass_number), reverse=True)
            if not candidates or candidates[0].mass is None:
                raise ValueError(f"An explicitly documented isotope is required for {symbol}.")
            isotope_masses[symbol] = float(candidates[0].mass)
        if not math.isclose(float(observed_mass), isotope_masses[symbol], rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f"TORQ returned a mass inconsistent with the requested isotope {symbol}.")
    if not np.allclose(rotation @ rotation.T, np.eye(3), rtol=0, atol=1e-10):
        raise ValueError("TORQ returned a nonorthogonal frame transformation.")
    if not math.isclose(float(np.linalg.det(rotation)), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("TORQ returned a frame that is not right-handed.")
    roundtrip_error = float(np.max(np.abs(aligned @ rotation + center - geometry)))
    if roundtrip_error > 1e-9:
        raise ValueError("TORQ's frame transformation did not preserve the input geometry.")
    if not np.allclose(center, np.average(geometry, axis=0, weights=masses), rtol=0, atol=1e-9):
        raise ValueError("TORQ returned an inconsistent center of mass.")
    distance_error = 0.0
    for index in range(len(symbols)):
        before = np.linalg.norm(geometry[index + 1 :] - geometry[index], axis=1)
        after = np.linalg.norm(aligned[index + 1 :] - aligned[index], axis=1)
        if before.size:
            distance_error = max(distance_error, float(np.max(np.abs(before - after))))
    if distance_error > 1e-9:
        raise ValueError("TORQ's alignment changed interatomic distances.")
    centered = geometry - center
    inertia = sum(
        mass * (np.dot(position, position) * np.eye(3) - np.outer(position, position))
        for mass, position in zip(masses, centered, strict=True)
    )
    independent_moments = np.linalg.eigvalsh(inertia)
    if not np.allclose(moments, independent_moments, rtol=1e-10, atol=1e-9):
        raise ValueError("TORQ's principal moments do not reproduce the supplied mass geometry.")
    if float(np.max(moments)) < 1e-10:
        raise ValueError("All principal inertias are below the provider's numerical rotor threshold.")

    # A linear molecule has no finite rotational constant about its zero-inertia
    # axis. Preserve that absence explicitly; all other nonfinite data fail.
    undefined: list[dict[str, Any]] = []
    for field, unit in (
        ("rotational_constants_mhz", "MHz"),
        ("rotational_constants_ghz", "GHz"),
        ("rotational_constants_cm1", "cm^-1"),
    ):
        values = list(result[field])
        if len(values) != 3:
            raise ValueError("TORQ returned an invalid rotational-constant vector.")
        for axis, value in enumerate(values):
            if not math.isfinite(value):
                if value != math.inf or not -1e-9 <= moments[axis] < 1e-10:
                    raise ValueError("TORQ returned an unexpected nonfinite rotational constant.")
                values[axis] = None
                undefined.append({"field": field, "axis": "ABC"[axis], "unit": unit,
                                  "reason": "No finite rigid-rotor constant for an axis with principal "
                                            "inertia below TORQ's 1e-10 Da angstrom^2 threshold."})
            elif value <= 0:
                raise ValueError("TORQ returned a nonpositive rotational constant.")
        result[field] = values
    a_value, _, c_value = result["rotational_constants_mhz"]
    if a_value is not None and c_value is not None and abs(a_value - c_value) < 1e-10:
        result["ray_kappa"] = None
        undefined.append({"field": "ray_kappa", "reason": "Ray's asymmetry parameter has a zero "
                          "denominator for a spherical top (A = B = C)."})
    prefactor_mhz = h / (8 * np.pi**2 * atomic_mass * 1e-20) / 1e6
    for axis, value in enumerate(result["rotational_constants_mhz"]):
        if value is not None and not math.isclose(
            value, float(prefactor_mhz / independent_moments[axis]), rel_tol=1e-10, abs_tol=1e-7
        ):
            raise ValueError("TORQ's rotational constants fail the independent inertia/unit check.")
    payload = {
        "schema_version": "cochem.module-operation/1",
        "module_id": "torq",
        "operation": "geometry_analysis",
        "status": "succeeded",
        "input_sha256": digest,
        "input_coordinate_unit": "angstrom",
        "scope": "Rigid-geometry center of mass, principal inertia, principal-axis (Eckart) "
                 "alignment and rotor properties of the supplied geometry. No optimization, "
                 "electronic energy, vibrational correction, or measured spectral constants.",
        "provider_file": str(Path(provider.__file__).resolve()),
        "provider_distribution": "CoChem-TORQ",
        "provider_version": importlib.metadata.version("CoChem-TORQ"),
        "mass_database": {"name": "mendeleev", "version": importlib.metadata.version("mendeleev"),
                          "selection": "Explicit isotopes when supplied; otherwise most abundant isotope."},
        "validation": {"coordinate_roundtrip_max_error_angstrom": roundtrip_error,
                       "pair_distance_max_error_angstrom": distance_error,
                       "independent_inertia_and_mhz_check": "passed"},
        "undefined_observables": undefined,
        "result": result,
    }
    json.dumps(payload, allow_nan=False)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise FileExistsError("The requested result artifact already exists.")
        _publish_json(args.output, analyze(args.artifact))
    except (ImportError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"TORQ geometry analysis failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
