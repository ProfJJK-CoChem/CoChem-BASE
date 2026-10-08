"""Read geometry-bound Cartesian Hessians for electronic-cost-free isotope analysis."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path

import numpy as np

from .isotopologue import IsotopologueSpectroscopyEngine


def _supplied_qualification() -> dict:
    return {"schema_version": "cochem.hessian-qualification/1", "validation_kind": "structural-only",
            "physical_hessian_verified": False, "stationary_geometry_verified": False,
            "minimum_verified": False, "scientific_accuracy_established": False,
            "scope": "Supplied Cartesian tensor and geometry: dimensions, units, symmetry and nuclide masses are checked. Physical derivative origin and stationarity are not established; a model preconditioner is not a measured force Hessian."}


@dataclass(frozen=True)
class HessianArtifact:
    symbols: tuple[str, ...]
    coordinates_angstrom: np.ndarray
    hessian_hartree_bohr2: np.ndarray
    source: str
    sha256: str
    path: Path
    qualification: dict = field(default_factory=_supplied_qualification)


def load_hessian_artifact(path: str | Path, *, native_result_path: str | Path | None = None) -> HessianArtifact:
    """Load an ORCA .hess, or an explicitly unit-labelled .npz/.h5 bundle.

    Bundles contain ``symbols``, ``coordinates_angstrom``,
    ``hessian_hartree_bohr2`` and scalar ``source`` datasets. Geometry travels
    with the Hessian so a matrix from another geometry cannot be silently reused.
    Pickled NumPy objects and absent provenance are rejected.
    """
    from cochem_base.core.cochem_core_registry_manager import AtomicFileLock

    path = Path(path).expanduser().resolve(strict=True)
    with AtomicFileLock(str(path) + ".lock", timeout=10.0):
        artifact = _load_locked_artifact(path)
    # Qualification is optional and separate from admission: students may
    # inspect external tensors without their provenance becoming a native claim.
    candidates = ([Path(native_result_path).expanduser().resolve(strict=True)] if native_result_path else
                  [parent / "result.json" for parent in (path.parent, path.parent.parent, path.parent.parent.parent)])
    for result_path in candidates:
        if result_path.is_file():
            try:
                qualification = qualify_native_hessian(artifact, result_path)
            except (ValueError, OSError, KeyError, TypeError, IndexError):
                continue
            return replace(artifact, qualification=qualification)
    return artifact


def _load_locked_artifact(path: Path) -> HessianArtifact:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Hessian artifact exceeds the 64 MiB physical data bound")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix.lower() == ".hess":
        from cochem_base.chain.chain import parse_orca_hessian
        from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM

        data = parse_orca_hessian(path)
        if data is None or not data["atoms"]:
            raise ValueError("ORCA Hessian must include its $atoms geometry block")
        symbols = tuple(atom["symbol"] for atom in data["atoms"])
        coordinates = np.asarray([atom["coords"] for atom in data["atoms"]]) * BOHR_TO_ANGSTROM
        hessian = data["hessian"]
        source = f"ORCA Cartesian Hessian: {path.name}"
    else:
        required = ("symbols", "coordinates_angstrom", "hessian_hartree_bohr2", "source")
        if path.suffix.lower() == ".npz":
            # Inspect logical shapes before NumPy allocates from an uploaded
            # header; compressed byte size alone is not a memory bound.
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if not 1 <= len(entries) <= 128 or len({entry.filename for entry in entries}) != len(entries):
                    raise ValueError("Hessian bundle inventory must be bounded and unique")
                total = 0
                for entry in entries:
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.npy", entry.filename) or entry.flag_bits & 1:
                        raise ValueError("Hessian bundle entries must be ordinary unencrypted NPY arrays")
                    with archive.open(entry) as stream:
                        version = np.lib.format.read_magic(stream)
                        if version not in {(1, 0), (2, 0)}:
                            raise ValueError("Unsupported Hessian array header version")
                        reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                        shape, _, dtype = reader(stream)
                        size = math.prod(shape) * dtype.itemsize
                        total += size
                        if dtype.hasobject or size > 64 * 1024 * 1024 or total > 64 * 1024 * 1024 or entry.file_size != stream.tell() + size:
                            raise ValueError("Hessian arrays cannot be pickled, truncated or exceed logical memory bounds")
            with np.load(path, allow_pickle=False) as archive:
                if not all(key in archive for key in required):
                    raise ValueError("Hessian bundle requires datasets: " + ", ".join(required))
                data = {key: archive[key] for key in required}
        elif path.suffix.lower() in {".h5", ".hdf5"}:
            import h5py

            with h5py.File(path, "r", libver="latest", swmr=True) as archive:
                if not all(key in archive for key in required):
                    raise ValueError("Hessian bundle requires datasets: " + ", ".join(required))
                total = 0
                for key in required:
                    if not isinstance(archive.get(key, getlink=True), h5py.HardLink):
                        raise ValueError("Hessian datasets cannot follow external or soft HDF5 links")
                    item = archive[key]
                    if not isinstance(item, h5py.Dataset) or item.is_virtual or item.external or h5py.check_dtype(ref=item.dtype):
                        raise ValueError("Hessian arrays must be ordinary local HDF5 datasets")
                    total += item.size * item.dtype.itemsize
                    creation = item.id.get_create_plist()
                    if total > 64 * 1024 * 1024 or any(creation.get_filter(index)[0] not in {1, 2, 3, 6, 32000} for index in range(creation.get_nfilters())):
                        raise ValueError("Hessian arrays exceed logical memory bounds or require an external HDF5 filter")
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


def _receipt_file(base: Path, receipt: dict) -> Path:
    name = receipt.get("filename")
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Native derivative receipt requires a portable relative filename")
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Native derivative receipt leaves its retained artifact directory")
    path = base / relative
    if any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(base)):
        raise ValueError("Native derivative receipts must not follow symlinks")
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Native derivative artifact is missing or exceeds its bounded size")
    if hashlib.sha256(path.read_bytes()).hexdigest() != receipt.get("sha256"):
        raise ValueError("Native derivative checksum differs from the accepted result receipt")
    return path


def qualify_native_hessian(artifact: HessianArtifact, native_result_path: str | Path) -> dict:
    """Recheck retained ORCA/CFOUR derivative receipts and minimum conditions.

    This establishes internal native-artifact consistency, not experimental
    accuracy or an external signature. Original coordinates/tensor stay intact.
    A positive spectrum alone never establishes a stationary minimum.
    """
    from cochem_base.spectroscopy.isotopologue import projected_harmonic_frequencies
    from cochem_base.physics.isotopes import parse_nuclide_token

    result_path = Path(native_result_path).resolve(strict=True)
    if result_path.is_symlink() or result_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Native calculation result must be a bounded retained regular file")
    raw = result_path.read_bytes()
    result = json.loads(raw)
    json.dumps(result, allow_nan=False)
    engine = result.get("engine")
    if engine not in {"orca", "cfour"} or result.get("converged") is not True:
        raise ValueError("Physical Hessian qualification requires a converged native ORCA/CFOUR result")
    receipt = result.get("hessian_artifact")
    if not isinstance(receipt, dict) or receipt.get("unit") != "hartree/bohr^2":
        raise ValueError("The native result has no unit-labelled Cartesian Hessian receipt")
    # Published CFOUR results can live in a 'published' sibling of 'native'.
    # Search only three bounded ancestor roots containing the selected tensor.
    base = raw_path = None
    for candidate in (result_path.parent, result_path.parent.parent, result_path.parent.parent.parent):
        if not artifact.path.is_relative_to(candidate):
            continue
        try:
            candidate_raw = _receipt_file(candidate, receipt)
            bundle_receipt = result.get("hessian_bundle_artifact")
            if artifact.sha256 != receipt.get("sha256"):
                if not isinstance(bundle_receipt, dict) or _receipt_file(candidate, bundle_receipt) != artifact.path:
                    continue
            elif candidate_raw != artifact.path:
                continue
            base, raw_path = candidate, candidate_raw
            break
        except ValueError:
            continue
    if base is None or raw_path is None:
        raise ValueError("Selected Hessian is not bound to the retained native result")
    elements = [parse_nuclide_token(symbol)[0] for symbol in artifact.symbols]
    if elements != result.get("elements"):
        raise ValueError("Native Hessian atom identities/order differ from the result")
    coordinates = np.asarray(result.get("coordinates_angstrom"), dtype=float)
    if coordinates.shape != artifact.coordinates_angstrom.shape or not np.isfinite(coordinates).all():
        raise ValueError("The native result has no matching finite ordered geometry")
    native_center = artifact.coordinates_angstrom.mean(axis=0)
    target_center = coordinates.mean(axis=0)
    u, _, vt = np.linalg.svd((artifact.coordinates_angstrom - native_center).T @ (coordinates - target_center))
    rotation = u @ np.diag([1., 1., float(np.linalg.det(u @ vt))]) @ vt
    aligned = (artifact.coordinates_angstrom - native_center) @ rotation + target_center
    if not np.allclose(aligned, coordinates, atol=1e-7, rtol=0):
        raise ValueError("Native Hessian geometry differs from the accepted geometry beyond a proper rigid frame")
    masses = np.asarray(receipt.get("native_masses_u"), dtype=float)
    if masses.shape != (len(elements),) or not np.isfinite(masses).all() or np.any(masses <= 0):
        raise ValueError("Native Hessian requires its actual ordered vibrational masses")
    if engine == "orca":
        raw_artifact = _load_locked_artifact(raw_path)
        from cochem_base.chain.chain import parse_orca_hessian
        parsed = parse_orca_hessian(raw_path)
        if not np.array_equal(np.asarray([atom["mass"] for atom in parsed["atoms"]]), masses):
            raise ValueError("Native ORCA masses differ from the raw Hessian")
        if not np.array_equal(parsed["frequencies"], np.asarray(receipt.get("native_frequencies_cm1"))):
            raise ValueError("Native ORCA spectrum differs from the raw Hessian")
        if not np.array_equal(raw_artifact.hessian_hartree_bohr2, artifact.hessian_hartree_bohr2) or not np.array_equal(raw_artifact.coordinates_angstrom, artifact.coordinates_angstrom):
            raise ValueError("The selected bundle differs from the raw ORCA tensor or coordinate frame")
    else:
        tokens = raw_path.read_text(encoding="utf-8").split()
        dimension = 3 * len(elements)
        if len(tokens) != 2 + dimension * dimension or [int(t) for t in tokens[:2]] != [len(elements), dimension]:
            raise ValueError("Raw CFOUR FCMFINAL is not a complete Cartesian Hessian")
        tensor = np.asarray([float(t.replace("D", "E").replace("d", "e")) for t in tokens[2:]]).reshape(dimension, dimension)
        if not np.array_equal(tensor, artifact.hessian_hartree_bohr2):
            raise ValueError("The selected bundle differs from the raw CFOUR Cartesian Hessian")
        source = json.loads(artifact.source)
        if source.get("engine") != "cfour":
            raise ValueError("The CFOUR tensor bundle requires its native provenance")
        raw_artifacts = source.get("raw_artifacts", {})
        for name in ("ZMAT", "GRD", "FCMFINAL", "output.dat"):
            _receipt_file(base, raw_artifacts[name])
        from cochem_base.calc.cfour_execution import read_cfour_gradient, NUMBER
        gradient_data = read_cfour_gradient(_receipt_file(base, raw_artifacts["GRD"]), elements, coordinates)
        if not np.array_equal(np.asarray(gradient_data["native_coordinates_angstrom"]), artifact.coordinates_angstrom):
            raise ValueError("CFOUR Hessian geometry differs from its raw GRD frame")
        text = _receipt_file(base, raw_artifacts["output.dat"]).read_text(encoding="utf-8")
        mass_blocks = re.findall(r"masses used \(in AMU\) in vibrational analysis:\s*\n(.*?)Normal Coordinate Analysis", text, re.S)
        if len(mass_blocks) != 1 or not np.array_equal(np.asarray([float(t.replace("D", "E").replace("d", "e")) for t in mass_blocks[0].split()]), masses):
            raise ValueError("CFOUR ordered vibrational masses differ from the raw output")
        rows = re.findall(rf"^\s*\S+\s+({NUMBER})(i?)\s+{NUMBER}\s+(VIBRATION|ROTATION|TRANSLATION)\s*$", text, re.M)
        native_vibrations = sorted((-1 if imaginary else 1) * float(value.replace("D", "E").replace("d", "e"))
                                   for value, imaginary, kind in rows if kind == "VIBRATION")
        if (len(rows) != dimension or not np.array_equal(np.asarray(native_vibrations), np.asarray(receipt.get("native_vibrational_frequencies_cm1")))
                or not re.search(r"CPHF converged after\s+\d+\s+iterations", text)):
            raise ValueError("CFOUR raw output lacks the matching complete converged analytic Hessian spectrum")
    recalculated, rigid = projected_harmonic_frequencies(artifact.hessian_hartree_bohr2, artifact.coordinates_angstrom, masses)
    native_frequencies = np.asarray(receipt.get("native_vibrational_frequencies_cm1"), dtype=float)
    tolerance = receipt.get("native_spectrum_consistency_tolerance_cm1", receipt.get("frequency_consistency_tolerance_cm1"))
    if (isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance)
            or not 0 < tolerance <= (0.25 if engine == "cfour" else 0.2) or rigid != receipt.get("rigid_mode_count")
            or native_frequencies.shape != (3 * len(elements) - rigid,)
            or not np.isfinite(native_frequencies).all()
            or not np.allclose(np.sort(native_frequencies), recalculated, rtol=0, atol=tolerance)):
        raise ValueError("Retained native spectrum does not agree with the actual mass-weighted force Hessian")
    if "harmonic_frequencies_cm1" in result:
        selected_symbols = result.get("harmonic_nuclides", artifact.symbols)
        if [parse_nuclide_token(symbol)[0] for symbol in selected_symbols] != elements:
            raise ValueError("The reported isotopologue spectrum changes ordered nuclear identities")
        derived = IsotopologueSpectroscopyEngine(list(selected_symbols), artifact.coordinates_angstrom,
                                                artifact.hessian_hartree_bohr2).compute_observables()
        reported = np.asarray(result["harmonic_frequencies_cm1"], dtype=float)
        if reported.shape != (3 * len(elements) - rigid,) or not np.allclose(reported, derived.harmonic_frequencies_cm1, rtol=0, atol=1e-5):
            raise ValueError("Reported isotopologue frequencies differ from actual dynamic-mass Hessian reweighting")
    stationary = False
    maximum_gradient = None
    gradient_receipt = result.get("gradient_artifact")
    if result.get("optimization_performed") is True and isinstance(gradient_receipt, dict):
        gradient_path = _receipt_file(base, gradient_receipt)
        if gradient_receipt.get("unit") != "hartree/bohr":
            raise ValueError("The stationarity checkpoint requires explicit Hartree/bohr units")
        if engine == "orca":
            from cochem_base.calc.recipe_r2_execution import read_dimer_gradient
            energy, gradients = read_dimer_gradient(gradient_path, elements, coordinates)
            if not math.isclose(energy, float(result["energy_hartree"]), rel_tol=0, abs_tol=1e-8):
                raise ValueError("The native gradient energy differs from the accepted energy")
        else:
            from cochem_base.calc.cfour_execution import read_cfour_gradient
            gradients = np.asarray(read_cfour_gradient(gradient_path, elements, coordinates)["gradients_hartree_per_bohr"])
        if not np.allclose(gradients, np.asarray(result.get("gradients_hartree_per_bohr")), atol=1e-12, rtol=0):
            raise ValueError("Native gradient checkpoint differs from the retained gradient")
        maximum_gradient = float(np.max(np.linalg.norm(gradients, axis=1)))
        stationary = maximum_gradient <= 1e-5
    minimum = stationary and bool(len(recalculated)) and min(recalculated) > 0
    return {"schema_version": "cochem.hessian-qualification/1", "validation_kind": "native-artifact-consistency",
            "engine": engine, "physical_hessian_verified": True,
            "stationary_geometry_verified": stationary, "minimum_verified": minimum,
            "scientific_accuracy_established": False, "native_result_sha256": hashlib.sha256(raw).hexdigest(),
            "native_result_filename": result_path.name, "raw_hessian_sha256": receipt["sha256"],
            "maximum_atomic_gradient_hartree_per_bohr": maximum_gradient,
            "stationarity_tolerance_hartree_per_bohr": 1e-5,
            "scope": ("Retained native force-Hessian, mass and spectrum receipts agree. " +
                      ("The geometry is a stationary harmonic minimum within the declared gradient tolerance. " if minimum else
                       "A stationary harmonic minimum is not established. ") +
                      "This checks numerical/provenance consistency, not experimental accuracy; no anharmonic B0 correction is inferred.")}
