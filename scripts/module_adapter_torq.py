#!/usr/bin/env python3
"""Run TORQ's installed rigid-geometry analysis in its isolated environment.

This is a file exchange adapter, not an optimizer or an electronic-structure
engine. Invoke it with the module environment's Python and ``-I``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import importlib
import inspect
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

_SYMBOL = re.compile(r"(?:[1-9][0-9]{0,2}[A-Z][a-z]?|[A-Z][a-z]?(?:-?[1-9][0-9]{0,2})?)\Z")
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
        label = fields[0]
        suffix = re.fullmatch(r"([A-Z][a-z]?)-?([1-9][0-9]{0,2})", label)
        symbols.append(suffix.group(2) + suffix.group(1) if suffix else {"D": "2H", "T": "3H"}.get(label, label))
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
    a_value, b_value, c_value = result["rotational_constants_mhz"]
    if a_value is not None and c_value is not None and a_value == c_value:
        result["ray_kappa"] = None
        undefined.append({"field": "ray_kappa", "reason": "Ray's asymmetry parameter has a zero "
                          "denominator for a spherical top (A = B = C)."})
    elif a_value is not None and b_value is not None and c_value is not None:
        expected_kappa = (b_value - c_value) / (a_value - c_value) - (a_value - b_value) / (a_value - c_value)
        if (not isinstance(result.get("ray_kappa"), (int, float))
                or not math.isfinite(result["ray_kappa"])
                or not math.isclose(result["ray_kappa"], expected_kappa, rel_tol=1e-10, abs_tol=1e-10)):
            raise ValueError("TORQ's Ray parameter does not reproduce the finite observed rotational constants.")
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




_EXTENSION_OPERATIONS = {"nbo_analysis", "wiberg_nao"}


def _extension_provider() -> tuple[dict, Any, Path] | None:
    """Admit only the installed distribution's versioned scientific entry point."""
    distribution = importlib.metadata.distribution("CoChem-TORQ")
    entries = [entry for entry in distribution.entry_points if entry.group == "cochem.modules" and entry.name == "torq"]
    if not entries:
        return None
    if len(entries) != 1:
        raise ValueError("TORQ has ambiguous scientific provider entry points.")
    entry = entries[0]
    if not entry.module.startswith("cochem_torq."):
        raise ValueError("TORQ provider must live in its installed scientific namespace.")
    metadata = entry.load()()
    if not isinstance(metadata, dict) or metadata.get("scientific_api_version") != "cochem.module-provider/1":
        return None  # Current upstream discovery-only metadata is not execution authority.
    if metadata.get("module_id") != "torq" or metadata.get("integration_contract") != "cochem.module-handoff/1":
        raise ValueError("TORQ scientific provider declares an incompatible integration contract.")
    operations = metadata.get("operations")
    if not isinstance(operations, list) or any(not isinstance(item, str) for item in operations) or len(set(operations)) != len(operations):
        raise ValueError("TORQ scientific operations must be an exact unique list.")
    handler = metadata.get("execute_handoff")
    if isinstance(handler, str):
        if not re.fullmatch(r"cochem_torq(?:\.[A-Za-z_][A-Za-z0-9_]*)+:[A-Za-z_][A-Za-z0-9_]*", handler):
            raise ValueError("TORQ scientific handler must be a qualified callable in its own namespace.")
        module_name, name = handler.split(":")
        handler = getattr(importlib.import_module(module_name), name)
    if not inspect.isfunction(handler) or not handler.__module__.startswith("cochem_torq."):
        raise ValueError("TORQ scientific handler is not an installed TORQ function.")
    signature = inspect.signature(handler)
    for name in ("handoff_path", "output_directory", "registry"):
        if name not in signature.parameters:
            raise ValueError("TORQ scientific handler must accept handoff_path, output_directory and registry.")
    source_name = inspect.getsourcefile(handler)
    if not source_name:
        raise ValueError("TORQ scientific handler has no auditable installed source file.")
    if Path(source_name).is_symlink():
        raise ValueError("TORQ scientific handler source cannot be a symlink.")
    source = Path(source_name).resolve(strict=True)
    distribution_root = Path(distribution.locate_file("")).resolve()
    if not source.is_relative_to(distribution_root) or source.is_symlink():
        raise ValueError("TORQ scientific handler is outside its installed distribution.")
    known_files = {Path(distribution.locate_file(item)).resolve() for item in distribution.files or []}
    if source not in known_files:
        raise ValueError("TORQ scientific handler is absent from the installed wheel record.")
    science = metadata.get("scientific_apis", {})
    for operation in _EXTENSION_OPERATIONS.intersection(operations):
        definition = science.get(operation, {})
        if type(definition.get("available")) is not bool:
            raise ValueError("TORQ must explicitly observe scientific operation availability.")
        dependencies = definition.get("required_engines")
        supported = definition.get("supported_engines")
        if (not isinstance(dependencies, list) or any(item not in {"orca", "cfour", "pyscf", "nbo"} for item in dependencies)
                or not isinstance(supported, list) or not supported or any(item not in {"orca", "pyscf"} for item in supported)):
            raise ValueError("TORQ must declare actual required runtimes and supported execution engines.")
        if not isinstance(definition.get("scope"), str) or not definition["scope"].strip():
            raise ValueError("TORQ scientific operation requires an explicit physical scope.")
        if definition["available"]:
            receipts = definition.get("runtime_receipts")
            if not isinstance(receipts, dict):
                raise ValueError("Available TORQ scientific operations require actual runtime receipts.")
            for dependency in dependencies:
                receipt = receipts.get(dependency, {})
                if receipt.get("available") is not True or not isinstance(receipt.get("version"), str) or not receipt["version"].strip():
                    raise ValueError(f"TORQ did not verify the required {dependency} runtime.")
                filename = receipt.get("executable_path") if dependency in {"orca", "cfour", "nbo"} else receipt.get("module_file")
                runtime = Path(filename or "")
                if runtime.is_symlink() or not runtime.is_file():
                    raise ValueError(f"TORQ's required {dependency} runtime is absent or is not a regular observed file.")
                if dependency in {"orca", "cfour", "nbo"} and not os.access(runtime, os.X_OK):
                    raise ValueError(f"TORQ's required {dependency} runtime is not executable.")
                with runtime.open("rb") as stream:
                    actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
                if receipt.get("sha256") != actual_hash:
                    raise ValueError(f"TORQ's required {dependency} runtime differs from its actual source receipt.")
    return metadata, handler, source

def capabilities() -> dict[str, Any]:
    """Observe actual installed APIs rather than treating installation as science."""
    import Libraries.cochem_torq_alignment as alignment
    provider_file = Path(alignment.__file__).resolve()
    operations = ["geometry_analysis"]
    science = {"geometry_analysis": {"available": True, "scope": "Geometry and equilibrium rigid-rotor analysis"}}
    sources = [{"path": str(provider_file), "sha256": hashlib.sha256(provider_file.read_bytes()).hexdigest()}]
    try:
        from cochem_torq.engines import pyscf_backend
        engine = pyscf_backend.PySCFBackend.probe()
        definition = pyscf_backend.PySCFBackend.capabilities()
        file = Path(pyscf_backend.__file__).resolve()
        sources.append({"path": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
        if engine.get("available") and callable(getattr(pyscf_backend.PySCFBackend, "evaluate", None)):
            operations.extend(["research_scan", "wiberg_lowdin"])
        science["research_scan"] = {"available": "research_scan" in operations,
            "engine": engine, "definition": definition,
            "scope": "Measured rigid-fragment mass-COM separation scan; no counterpoise or automatic accuracy claim."}
    except (ImportError, AttributeError, OSError) as exc:
        science["research_scan"] = {"available": False, "reason": f"The reviewed TORQ native scan API is unavailable: {exc}"}
    science["wiberg_lowdin"] = {"available": "wiberg_lowdin" in operations,
        "scope": "Wiberg indices in the Löwdin orthogonalized AO basis from the authenticated real restricted SCF checkpoint; not NAO indices or NBO."}
    extension = _extension_provider()
    for name in ("nbo_analysis", "wiberg_nao"):
        if extension is not None and name in extension[0]["operations"]:
            definition = extension[0]["scientific_apis"][name]
            science[name] = definition
            if definition["available"]:
                operations.append(name)
        else:
            science[name] = {"available": False,
                "reason": "The installed TORQ API does not expose a versioned, executable native producer of this named analysis. "
                          "Authentic retained analysis can be displayed through BASE; Mayer indices are not Wiberg or NBO."}
    if extension is not None:
        source = extension[2]
        sources.append({"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    return {"schema_version": "cochem.module-capabilities/1", "module_id": "torq",
            "operations": operations, "provider_file": str(provider_file),
            "provider_sha256": hashlib.sha256(provider_file.read_bytes()).hexdigest(),
            "provider_distribution": "CoChem-TORQ", "provider_version": importlib.metadata.version("CoChem-TORQ"),
            "integration_contract": "cochem.module-handoff/1",
            "scientific_api_version": extension[0]["scientific_api_version"] if extension else None, "scientific_apis": science,
            "provider_sources": sources}


def _load_handoff(path: Path) -> tuple[dict, Path, list[str], list[list[float]]]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("The handoff must be a bounded retained JSON file.")
    record = json.loads(path.read_bytes())
    json.dumps(record, allow_nan=False)
    if (record.get("schema_version") != "cochem.module-handoff/1" or record.get("module_id") != "torq"
            or record.get("operation") not in {"research_scan", "wiberg_lowdin", "nbo_analysis", "wiberg_nao"} or record.get("scientific_execution_performed") is not False):
        raise ValueError("Unsupported TORQ research handoff.")
    reference = record.get("artifact", {})
    filename = reference.get("filename", "")
    if Path(filename).name != filename or reference.get("kind") != "geometry_xyz":
        raise ValueError("TORQ scans require an immutable XYZ handoff.")
    artifact = path.parent / filename
    if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size != reference.get("size_bytes"):
        raise ValueError("The handoff geometry is absent or has changed.")
    symbols, positions, digest = read_xyz(artifact)
    if digest != reference.get("sha256"):
        raise ValueError("The handoff geometry checksum has changed.")
    return record, artifact, symbols, positions


def _scan_options(options: dict, atom_count: int) -> dict:
    allowed = {"method", "charge", "multiplicity", "fragments", "distances_angstrom", "cores", "memory_mb"}
    if not isinstance(options, dict) or set(options) - allowed or not 2 <= atom_count <= 50:
        raise ValueError("Unsupported or oversized scan request.")
    method = options.get("method")
    if (not isinstance(method, dict) or set(method) != {"name", "basis"}
            or method["name"] not in {"hf", "pbe-d4", "b3lyp-d4", "mp2"}
            or not isinstance(method["basis"], str) or re.fullmatch(r"[A-Za-z0-9+*(),_. -]{1,100}", method["basis"]) is None):
        raise ValueError("Choose an explicit supported scan method and basis.")
    if type(options.get("charge")) is not int or abs(options["charge"]) > 4 or type(options.get("multiplicity")) is not int or options["multiplicity"] != 1:
        raise ValueError("The bounded scan requires an integer charge and closed-shell singlet state.")
    fragments = options.get("fragments")
    if not isinstance(fragments, list) or len(fragments) != 2 or any(not isinstance(part, list) or not part for part in fragments):
        raise ValueError("Two complete, nonempty fragments are required.")
    indices = [index for part in fragments for index in part]
    if any(type(index) is not int for index in indices) or sorted(indices) != list(range(atom_count)):
        raise ValueError("Each atom must appear in exactly one fragment.")
    distances = options.get("distances_angstrom")
    if (not isinstance(distances, list) or not 1 <= len(distances) <= 20
            or any(isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not .2 <= value <= 100 for value in distances)
            or len(set(distances)) != len(distances)):
        raise ValueError("Choose 1–20 distinct finite mass-COM separations between 0.2 and 100 angstrom.")
    cores, memory = options.get("cores", 1), options.get("memory_mb", 1500)
    if type(cores) is not int or not 1 <= cores <= 2 or type(memory) is not int or not 256 <= memory <= 2048:
        raise ValueError("The bounded scan permits 1–2 cores and 256–2048 MiB total memory.")
    return {**options, "cores": cores, "memory_mb": memory}


def research_scan(handoff_path: Path, directory: Path) -> dict[str, Any]:
    """Run authentic provider evaluations at rigid translated fragment geometries."""
    record, artifact, symbols, positions = _load_handoff(handoff_path)
    options = _scan_options(record["options"], len(symbols))
    from cochem_torq.engines import pyscf_backend as provider
    from mendeleev import element
    from scipy.constants import physical_constants
    import numpy as np

    if "research_scan" not in capabilities()["operations"]:
        raise ValueError("The installed TORQ native scan producer is not available.")
    masses, elements = [], []
    for symbol in symbols:
        normalized = {"D": "2H", "T": "3H"}.get(symbol, symbol)
        match = re.fullmatch(r"([0-9]*)([A-Z][a-z]?)", normalized)
        if match is None:
            raise ValueError("Unsupported nuclear identity.")
        number, label = match.groups()
        nucleus = element(label)
        elements.append(label)
        if number:
            isotope = next((item for item in nucleus.isotopes if item.mass_number == int(number)), None)
            if isotope is None or isotope.mass is None:
                raise ValueError("The requested physical isotope lacks a measured mass.")
            masses.append(float(isotope.mass))
        else:
            masses.append(float(nucleus.atomic_weight))
    masses = np.asarray(masses)
    geometry = np.asarray(positions)
    a, b = options["fragments"]
    center_a = np.average(geometry[a], axis=0, weights=masses[a])
    center_b = np.average(geometry[b], axis=0, weights=masses[b])
    vector = center_b - center_a
    initial = float(np.linalg.norm(vector))
    if initial < 1e-8:
        raise ValueError("Fragment mass centers coincide; a separation direction is required.")
    direction = vector / initial
    conversion = 1e-10 / physical_constants["Bohr radius"][0]
    planned = []
    for distance in options["distances_angstrom"]:
        shifted = geometry.copy()
        shifted[b] += (distance - initial) * direction
        pair = np.linalg.norm(shifted[:, None] - shifted[None, :], axis=2)
        np.fill_diagonal(pair, np.inf)
        if np.min(pair) < .1:
            raise ValueError("The scan places nuclei less than 0.1 angstrom apart.")
        planned.append((float(distance), shifted))
    points = []
    provider_path = Path(provider.__file__).resolve()
    def snapshot() -> dict[str, Any]:
        published_points = list(points) + [
            {"coordinate_angstrom": distance, "geometry_angstrom": shifted.tolist(), "status": "not_run",
             "energy_hartree": None, "reason": "This planned point has no completed native evaluation."}
            for distance, shifted in planned[len(points):]]
        status = "completed" if all(point["status"] == "computed" for point in published_points) else "partial"
        return {"schema_version": "cochem.module-operation/1", "module_id": "torq", "operation": "research_scan",
                "input_sha256": record["artifact"]["sha256"], "status": status,
                "provider_file": str(provider_path), "provider_sha256": hashlib.sha256(provider_path.read_bytes()).hexdigest(),
                "provider_distribution": "CoChem-TORQ", "provider_version": importlib.metadata.version("CoChem-TORQ"),
                "scope": "Actual native electronic energies along a rigid two-fragment mass-COM separation coordinate; "
                         "intramolecular geometries and orientation remain fixed. No relaxation, counterpoise, barrier/minimum "
                         "verification or universal chemical-accuracy claim.",
                "result": {"schema_version": "cochem.torq-rigid-scan/1", "points": published_points, "elements": elements,
                           "nuclides": symbols, "method": options["method"], "fragments": options["fragments"],
                           "electronic_state": {"charge": options["charge"], "multiplicity": 1},
                           "initial_mass_com_separation_angstrom": initial, "masses_u": masses.tolist(),
                           "mass_source": "dynamic_mendeleev_explicit_isotope_else_standard_atomic_weight",
                           "resources": {"cores": options["cores"], "memory_mb": options["memory_mb"]}}}
    for index, (distance, shifted) in enumerate(planned):
        point_directory = directory / f"scan-point-{index:03d}"
        request = {"molecule": {"symbols": symbols, "geometry_bohr": (shifted * conversion).tolist(),
                   "charge": options["charge"], "multiplicity": 1}, "method": options["method"], "properties": ["energy"],
                   "settings": {"threads": options["cores"], "memory_mb": options["memory_mb"], "check_stability": True}}
        try:
            native = provider.PySCFBackend().evaluate(request, point_directory)
            energy = native.get("energy_hartree")
            if native.get("status") != "complete" or isinstance(energy, bool) or not isinstance(energy, (float, int)) or not math.isfinite(energy):
                raise ValueError(f"Native TORQ calculation did not complete: {native.get('errors')}")
            result_path = point_directory / "result.json"
            points.append({"coordinate_angstrom": distance, "geometry_angstrom": shifted.tolist(), "status": "computed",
                "energy_hartree": energy, "result_path": str(result_path.relative_to(directory)),
                "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                "native_manifest_path": str(Path(native["manifest_path"]).relative_to(directory)),
                "native_manifest_sha256": native["manifest_sha256"], "engine_version": native["engine_version"]})
        except (ValueError, RuntimeError) as exc:
            points.append({"coordinate_angstrom": distance, "geometry_angstrom": shifted.tolist(),
                           "status": "failed", "energy_hartree": None, "reason": str(exc)})
        _publish_json(directory / f"scan-progress-{index:03d}.json", snapshot())
    return snapshot()


def wiberg_lowdin(handoff_path: Path, directory: Path) -> dict[str, Any]:
    """Compute named Löwdin-AO Wiberg indices from real density/overlap matrices."""
    record, _, symbols, positions = _load_handoff(handoff_path)
    options = record["options"]
    if not isinstance(options, dict) or set(options) - {"method", "charge", "multiplicity", "cores", "memory_mb"}:
        raise ValueError("Unsupported Wiberg analysis option.")
    # Reuse the exact checked model/state/resource contract without permitting
    # scan geometry fields in this independent operation.
    checked = _scan_options({**options, "fragments": [[0], list(range(1, len(symbols)))], "distances_angstrom": [1.]}, len(symbols))
    if checked["method"]["name"] == "mp2":
        raise ValueError("A correlated MP2 density is not available in the retained restricted SCF checkpoint.")
    from cochem_torq.engines import pyscf_backend as provider
    from cochem_torq.engines.diagnostics import verify_native_artifacts
    from pyscf import lib
    from scipy.constants import physical_constants
    import numpy as np

    conversion = 1e-10 / physical_constants["Bohr radius"][0]
    native = provider.PySCFBackend().evaluate({"molecule": {"symbols": symbols,
        "geometry_bohr": (np.asarray(positions) * conversion).tolist(), "charge": checked["charge"], "multiplicity": 1},
        "method": checked["method"], "properties": ["energy"],
        "settings": {"threads": checked["cores"], "memory_mb": checked["memory_mb"], "check_stability": True}}, directory / "native-electronic")
    if native.get("status") != "complete" or native.get("scf", {}).get("converged") is not True or native.get("stability", {}).get("status") != "stable":
        raise ValueError("Wiberg analysis requires a real converged and stable restricted SCF calculation.")
    native_directory = verify_native_artifacts(native)
    checkpoint = native_directory / "wavefunction.chk"
    molecule = lib.chkfile.load_mol(str(checkpoint))
    scf = lib.chkfile.load(str(checkpoint), "scf")
    coefficients, occupations = np.asarray(scf["mo_coeff"]), np.asarray(scf["mo_occ"])
    if (coefficients.shape != (molecule.nao_nr(), len(occupations)) or not np.isfinite(coefficients).all()
            or not np.isfinite(occupations).all() or not np.isin(occupations, [0., 2.]).all()
            or abs(float(np.sum(occupations)) - molecule.nelectron) > 1e-8 or molecule.spin != 0
            or not np.allclose(molecule.atom_coords(unit="Bohr"), native["geometry_bohr"], atol=1e-10, rtol=0)
            or abs(float(scf["e_tot"]) - native["scf"]["energy_hartree"]) > 1e-8):
        raise ValueError("The native checkpoint differs from its retained restricted density identity, energy or geometry.")
    overlap = molecule.intor_symmetric("int1e_ovlp")
    eigenvalues, eigenvectors = np.linalg.eigh(overlap)
    if not np.isfinite(eigenvalues).all() or np.min(eigenvalues) <= 1e-10:
        raise ValueError("Löwdin analysis requires a positive, numerically independent AO overlap basis.")
    square_root = (eigenvectors * np.sqrt(eigenvalues)) @ eigenvectors.T
    density_ao = (coefficients * occupations) @ coefficients.T
    density_lowdin = square_root @ density_ao @ square_root
    if (not np.isfinite(density_lowdin).all() or not np.allclose(density_lowdin, density_lowdin.T, atol=1e-10, rtol=0)
            or abs(float(np.trace(density_lowdin)) - molecule.nelectron) > 1e-7):
        raise ValueError("The orthogonalized real density failed electron-count or symmetry validation.")
    slices = molecule.aoslice_by_atom()
    bonds, populations, charges = [], [], []
    for i, (_, _, begin, end) in enumerate(slices):
        population = float(np.trace(density_lowdin[begin:end, begin:end]))
        populations.append(population)
        charges.append(float(molecule.atom_charge(i)) - population)
        for j in range(i + 1, len(slices)):
            other_begin, other_end = slices[j][2:]
            value = float(np.sum(density_lowdin[begin:end, other_begin:other_end] ** 2))
            bonds.append({"atom_i": i, "atom_j": j, "value": value})
    if abs(math.fsum(charges) - checked["charge"]) > 1e-7:
        raise ValueError("The Löwdin atomic charges do not conserve the requested total charge.")
    matrices = directory / "lowdin-density-overlap.npz"
    np.savez(matrices, density_ao=density_ao, overlap_ao=overlap, density_lowdin=density_lowdin)
    analysis = {"schema_version": "cochem.wiberg-lowdin/1", "analysis_kind": "wiberg_lowdin",
        "atoms": symbols, "coordinates_angstrom": positions, "bonds": bonds,
        "charges_e": charges, "populations_e": populations, "method": checked["method"],
        "electronic_state": {"charge": checked["charge"], "multiplicity": 1},
        "definition": "W_AB = sum_(mu in A,nu in B) (P_Lowdin[mu,nu])^2; P_Lowdin = S^(1/2) P_AO S^(1/2), spin-summed restricted density.",
        "scope": "Löwdin orthogonalized AO Wiberg indices and charges. These are not NAO-basis Wiberg indices or Natural Bond Orbital analysis.",
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "native_manifest_sha256": native["manifest_sha256"],
        "matrix_sha256": hashlib.sha256(matrices.read_bytes()).hexdigest(),
        "validation": {"electron_count": int(molecule.nelectron), "density_trace": float(np.trace(density_lowdin)),
                       "charge_sum": math.fsum(charges), "minimum_overlap_eigenvalue": float(np.min(eigenvalues))}}
    analysis_path = directory / "bond-analysis.json"
    _publish_json(analysis_path, analysis)
    provider_path = Path(provider.__file__).resolve()
    return {"schema_version": "cochem.module-operation/1", "module_id": "torq", "operation": "wiberg_lowdin",
        "status": "completed", "input_sha256": record["artifact"]["sha256"], "provider_file": str(provider_path),
        "provider_sha256": hashlib.sha256(provider_path.read_bytes()).hexdigest(),
        "scope": analysis["scope"], "result": {**analysis, "analysis_path": analysis_path.name,
        "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest()}}


def execute_extension(handoff_path: Path, directory: Path, registry: Path | None) -> dict[str, Any]:
    """Delegate compatible future science only to the actual installed provider."""
    record, _, _, _ = _load_handoff(handoff_path)
    operation = record["operation"]
    provider = _extension_provider()
    if provider is None or operation not in capabilities()["operations"]:
        raise ValueError("The installed TORQ provider does not currently support this scientific operation.")
    metadata, handler, source = provider
    options = record["options"]
    allowed = {"engine", "method", "charge", "multiplicity", "cores", "memory_mb"}
    if not isinstance(options, dict) or set(options) != allowed:
        raise ValueError("Provide explicit engine, method, basis, state and resource fields for the analysis.")
    definition = metadata["scientific_apis"][operation]
    if options["engine"] not in definition["supported_engines"]:
        raise ValueError("The installed provider does not support this selected scientific engine.")
    if (not isinstance(options["method"], dict) or set(options["method"]) != {"name", "basis"}
            or any(not isinstance(value, str) or not value.strip() or len(value) > 100
                   or any(ord(character) < 32 or ord(character) == 127 for character in value)
                   for value in options["method"].values())
            or type(options["charge"]) is not int or abs(options["charge"]) > 4
            or type(options["multiplicity"]) is not int or not 1 <= options["multiplicity"] <= 5
            or type(options["cores"]) is not int or not 1 <= options["cores"] <= 2
            or type(options["memory_mb"]) is not int or not 256 <= options["memory_mb"] <= 2048):
        raise ValueError("Unsupported analysis state, method definition or classroom resource request.")
    # The receiving provider owns exact model/state/runtime qualification, including
    # the separate NBO executable and licence when its declared operation needs it.
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    payload = handler(handoff_path=handoff_path, output_directory=directory, registry=registry)
    json.dumps(payload, allow_nan=False)
    if (not isinstance(payload, dict) or payload.get("schema_version") != "cochem.module-operation/1"
            or payload.get("module_id") != "torq" or payload.get("operation") != operation
            or payload.get("input_sha256") != record["artifact"]["sha256"]
            or Path(payload.get("provider_file", "")).resolve() != source
            or payload.get("provider_sha256") != digest
            or hashlib.sha256(source.read_bytes()).hexdigest() != digest):
        raise ValueError("The TORQ scientific operation receipt differs from its verified provider or input.")
    if _load_handoff(handoff_path)[0] != record:
        raise ValueError("The scientific handoff changed during TORQ execution.")
    return payload

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--artifact", type=Path)
    mode.add_argument("--handoff", type=Path)
    mode.add_argument("--capabilities", action="store_true")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise FileExistsError("The requested result artifact already exists.")
        if args.capabilities:
            payload = capabilities()
        elif args.handoff:
            operation = json.loads(args.handoff.read_bytes()).get("operation")
            if operation in _EXTENSION_OPERATIONS:
                payload = execute_extension(args.handoff, args.output.parent.resolve(), args.registry)
            elif operation == "wiberg_lowdin":
                payload = wiberg_lowdin(args.handoff, args.output.parent.resolve())
            else:
                payload = research_scan(args.handoff, args.output.parent.resolve())
        else:
            payload = analyze(args.artifact)
        _publish_json(args.output, payload)
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"TORQ operation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
