"""Bounded, immutable student input library using canonical scientific parsers.

Admission validates structure and records original bytes; it never establishes
that imported energies are accurate or that conformers are physical minima.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
import uuid
import zipfile

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 512
KINDS = frozenset({"molecular", "conformer_pool", "periodic", "hessian", "telemetry", "spectroscopy", "physical_data", "native_result", "pseudopotential"})
MOLECULAR_SUFFIXES = frozenset({".xyz", ".mol", ".sdf", ".mol2", ".pdb"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if hasattr(value, "item"):
        return _jsonable(value.item())
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _unique_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON keys cannot define scientific inputs")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))


def _library(artifact_dir: Path) -> Path:
    from cochem.core.context import assert_writable_path
    root = Path(artifact_dir).expanduser().absolute()
    for component in [root, *root.parents]:
        if component.is_symlink():
            raise ValueError("Student artifact directories cannot traverse symbolic links")
    assert_writable_path(root)
    library = root / "InputLibrary"
    if library.is_symlink():
        raise ValueError("Student input library cannot be a symbolic link")
    library.mkdir(parents=True, exist_ok=True, mode=0o700)
    return library


def _inspect_binary(path: Path) -> dict:
    """Bound logical shapes and reject links/plugins before reading any array."""
    import numpy as np
    arrays = []
    total = 0
    if path.suffix.lower() == ".npz":
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= MAX_RECORDS or len({item.filename for item in entries}) != len(entries):
                raise ValueError("Array archive has an invalid/duplicate inventory")
            if sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES:
                raise ValueError("Array archive exceeds expanded data bounds")
            for item in entries:
                if not re.fullmatch(r"[A-Za-z0-9_.-]+\.npy", item.filename) or item.flag_bits & 1:
                    raise ValueError("Array archive must contain named, unencrypted NPY arrays only")
                if item.file_size > MAX_EXPANDED_BYTES or item.external_attr >> 16 & 0o170000 == 0o120000:
                    raise ValueError("Array member is too large or a symbolic link")
                with archive.open(item) as stream:
                    version = np.lib.format.read_magic(stream)
                    if version not in {(1, 0), (2, 0)}:
                        raise ValueError("Unsupported NPY header version")
                    reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                    shape, fortran_order, dtype = reader(stream)
                    if dtype.hasobject:
                        raise ValueError("Pickled object arrays cannot enter the student library")
                    size = math.prod(shape) * dtype.itemsize
                    if size > MAX_EXPANDED_BYTES:
                        raise ValueError("Array logical dimensions exceed data bounds")
                    if item.file_size != stream.tell() + size:
                        raise ValueError("NPY payload length does not match its declared shape")
                    total += size
                    arrays.append({"name": item.filename[:-4], "shape": list(shape), "dtype": str(dtype), "bytes": size})
    else:
        import h5py
        with h5py.File(path, "r", libver="latest", swmr=True) as archive:
            visited = set()
            def inspect(group, prefix=""):
                nonlocal total
                for name in group:
                    link = group.get(name, getlink=True)
                    if not isinstance(link, h5py.HardLink):
                        raise ValueError("Uploaded HDF5 cannot reference external or symbolic data")
                    item = group[name]
                    address = h5py.h5o.get_info(item.id).addr
                    if address in visited:
                        raise ValueError("Uploaded HDF5 aliases/cycles are ambiguous")
                    visited.add(address)
                    full = prefix + name
                    if isinstance(item, h5py.Group):
                        inspect(item, full + "/")
                        continue
                    if len(arrays) >= MAX_RECORDS or item.is_virtual or item.external:
                        raise ValueError("HDF5 inventory is too large or references external storage")
                    if item.dtype.hasobject:
                        raise ValueError("Variable-length/object HDF5 datasets require a separately bounded contract")
                    plist = item.id.get_create_plist()
                    for index in range(plist.get_nfilters()):
                        if plist.get_filter(index)[0] not in {1, 2, 3, 32000}:
                            raise ValueError("Uploaded HDF5 cannot load arbitrary filter plugins")
                    size = math.prod(item.shape) * item.dtype.itemsize
                    if size > MAX_EXPANDED_BYTES:
                        raise ValueError("HDF5 logical dimensions exceed data bounds")
                    total += size
                    arrays.append({"name": full, "shape": list(item.shape), "dtype": str(item.dtype), "bytes": size})
            inspect(archive)
    if total > MAX_EXPANDED_BYTES:
        raise ValueError("Combined logical scientific arrays exceed data bounds")
    return {"arrays": arrays, "expanded_bytes": total, "external_data_allowed": False, "pickle_allowed": False}


def _pool_energies(records: list[dict], producer: str | None, energy_unit: str | None) -> list[float]:
    if producer not in {"crest", "orca_goat", "declared"} or energy_unit not in {"hartree", "kcal/mol"}:
        raise ValueError("Conformer pools require an explicit producer declaration and energy unit")
    if producer in {"crest", "orca_goat"} and energy_unit != "hartree":
        raise ValueError("Native CREST/GOAT pool energies are Hartree")
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
    energies = []
    for record in records:
        comment = record.get("comment", "")
        if re.search(r"kcal|kJ|\beV\b", comment, re.I) and energy_unit == "hartree":
            raise ValueError("Pool comment conflicts with declared Hartree units")
        match = re.search(rf"\b(?:energy|E)\s*[:=]\s*({number})(?=\s|$)", comment, re.I)
        if producer == "declared":
            unit = re.search(r"\benergy_units?\s*=\s*[\"']?([^\s\"']+)", comment, re.I)
            if not match or not unit or unit.group(1).lower() != energy_unit:
                raise ValueError("Imported pool frames require explicitly labeled energies and matching units")
        elif match is None:
            match = re.match(rf"\s*({number})(?:\s|$)", comment)
        if match is None:
            raise ValueError("Every pool frame must contain its recorded energy")
        energy = float(match.group(1).replace("D", "E").replace("d", "e"))
        if not math.isfinite(energy):
            raise ValueError("Pool energies must be finite")
        energies.append(energy)
    return energies


def _parse(path: Path, kind: str, *, filename: str, producer=None, energy_unit=None) -> tuple[list[dict], dict]:
    suffix = path.suffix.lower()
    metadata = {}
    records = []
    if kind in {"molecular", "conformer_pool"}:
        from cochem_base.intake.structure_formats import parse_structure_text
        records = parse_structure_text(path.read_text(encoding="utf-8-sig", errors="strict"), suffix.lstrip("."))
        if not 1 <= len(records) <= MAX_RECORDS:
            raise ValueError("Molecular input exceeds bounded record inventory")
        if any(len(record["symbols"]) > 4096 for record in records):
            raise ValueError("Molecular record exceeds the atom admission limit")
        if kind == "conformer_pool":
            energies = _pool_energies(records, producer, energy_unit)
            for record, energy in zip(records, energies):
                record["imported_energy"] = energy
                record["imported_energy_unit"] = energy_unit
            metadata.update(producer_declaration=producer, energy_unit=energy_unit,
                            energy_accuracy_verified=False, stationary_minima_verified=False)
    elif kind == "periodic":
        from cochem_base.calc.periodic import parse_periodic_structure
        parsed = parse_periodic_structure(path.read_bytes(), format=suffix, filename=filename)
        metadata["validated_periodic_structure"] = parsed.model_dump(mode="json")
    elif kind in {"hessian", "physical_data", "telemetry"}:
        if suffix in {".h5", ".hdf5", ".npz"}:
            metadata.update(_inspect_binary(path))
        if kind == "hessian":
            from cochem_base.spectroscopy.artifacts import load_hessian_artifact
            parsed = load_hessian_artifact(path)
            metadata.update(symbols=list(parsed.symbols), coordinates_angstrom=parsed.coordinates_angstrom.tolist(),
                hessian_shape=list(parsed.hessian_hartree_bohr2.shape), hessian_unit="hartree/bohr^2", source=parsed.source,
                physical_force_field_verified=False, stationary_geometry_verified=False,
                scope="supplied_geometry_and_cartesian_hessian_structure_not_equilibrium_acceptance")
        elif kind == "telemetry":
            if suffix not in {".h5", ".hdf5"}:
                raise ValueError("Canonical telemetry requires an HDF5 trajectory store")
            import h5py
            from cochem_base.core_engine.scientific_telemetry import read_scientific_results
            with h5py.File(path, "r", libver="latest", swmr=True) as archive:
                if "trajectories" not in archive or not isinstance(archive["trajectories"], h5py.Group):
                    raise ValueError("Telemetry requires canonical measured trajectories")
                jobs = list(archive["trajectories"])
                if len(jobs) > MAX_RECORDS:
                    raise ValueError("Telemetry exceeds bounded trajectory inventory")
                for job in jobs:
                    group = archive["trajectories"][job]
                    required = {"committed_records", "coordinates_angstrom", "energy_hartree", "metadata_json",
                        "gradient_record_indices", "gradients_hartree_per_bohr"}
                    if not required.issubset(group):
                        raise ValueError("Telemetry is missing its canonical measured record datasets")
                    counter = group["committed_records"]
                    if counter.shape != () or counter.dtype.kind not in "iu":
                        raise ValueError("Telemetry committed count must be a scalar integer")
                    count = int(counter[()])
                    if count < 0 or any(len(group[key]) < count for key in ("coordinates_angstrom", "energy_hartree", "metadata_json")):
                        raise ValueError("Committed telemetry inventory is incomplete")
            measured = []
            for job in jobs:
                data = read_scientific_results(job, store_path=path)
                values = data["energy_hartree"]
                import numpy as np
                coordinates = np.asarray(data["coordinates_angstrom"], dtype=float)
                gradients = np.asarray(data["gradients_hartree_per_bohr"], dtype=float)
                indices = np.asarray(data["gradient_record_indices"])
                symbols = data["nuclides"]
                if (coordinates.shape != (len(values), len(symbols), 3) or not np.isfinite(coordinates).all()
                        or not all(math.isfinite(float(value)) for value in values)):
                    raise ValueError("Committed telemetry requires complete finite measured geometry and energy")
                if (gradients.shape != (len(indices), len(symbols), 3) or not np.isfinite(gradients).all()
                        or len(set(indices.tolist())) != len(indices) or np.any(indices < 0)):
                    raise ValueError("Telemetry gradients require unique committed indices and complete finite tensors")
                measured.append({"job_id": job, "committed_records": len(values), "symbols": data["nuclides"]})
            metadata["measured_trajectories"] = measured
        elif suffix not in {".npz", ".h5", ".hdf5"}:
            raise ValueError("Physical data admission requires a bounded numerical NPZ/HDF5 archive")
    elif kind == "pseudopotential":
        import xml.etree.ElementTree as ET
        from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
        text = path.read_text(encoding="utf-8", errors="strict")
        headers = re.findall(r"<PP_HEADER\b[^>]*?/>", text, re.S)
        if suffix != ".upf" or len(headers) != 1 or not re.search(r"<PP_PAW\b", text):
            raise ValueError("PAW input requires one UPF2 header and augmentation data")
        header = ET.fromstring(headers[0]).attrib
        symbol = header.get("element", "").strip()
        get_nuclide_mass(symbol)
        if header.get("pseudo_type", "").strip().upper() != "PAW" or header.get("is_paw", "").strip().upper() not in {"T", "TRUE", ".TRUE."}:
            raise ValueError("Pseudopotential must explicitly identify a PAW dataset")
        metadata.update(element=symbol, header=header, pseudo_type="PAW", native_execution_verified=False)
    elif kind == "spectroscopy":
        from cochem_base.spectroscopy.parser import SpectroscopyTelemetryParser
        parsed = SpectroscopyTelemetryParser().parse_file(path)
        metadata.update(measured_spectroscopy=parsed.model_dump(mode="json"),
            stationary_geometry_verified=False, physical_force_field_verified=False,
            scope="values_parsed_from_supplied_native_output_without_independent_stationarity_acceptance")
    elif kind == "native_result":
        if suffix == ".json":
            from cochem_base.interfaces.artifact_handoff import _inspect
            artifact_kind, details = _inspect(path)
            if artifact_kind != "calculation_result":
                raise ValueError("Native result JSON must meet the actual converged-result contract")
            metadata.update(details, source_engine_attestation_verified=False, energy_accuracy_verified=False,
                scope="imported_result_structure_and_original_integrity_not_independent_native_acceptance")
        elif suffix in {".out", ".log", ".txt"}:
            from cochem_base.diagnostics.log_parser import LogDiagnosticParser
            diagnostics = LogDiagnosticParser.parse_file(path)
            metadata.update(diagnostics=_jsonable(diagnostics.model_dump() if hasattr(diagnostics, "model_dump") else vars(diagnostics)),
                imported_native_output=True, energy_accuracy_verified=False,
                scope="original_native_output_and_diagnostics_not_accepted_calculation")
        else:
            raise ValueError("Native results require a supported output/log or converged result JSON")
    return _jsonable(records), _jsonable(metadata)


def ingest_uploaded_file(filename: str, raw: bytes, *, artifact_dir: Path, kind: str = "auto",
                         producer: str | None = None, energy_unit: str | None = None) -> dict:
    """Atomically retain one original and its verified canonical intake receipt."""
    if not isinstance(filename, str) or not 1 <= len(filename) <= 200 or Path(filename).name != filename or re.search(r"[\x00-\x1f/\\:]", filename):
        raise ValueError("Upload filename must be a plain safe basename")
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_FILE_BYTES or raw.startswith((b"MZ", b"\x7fELF")):
        raise ValueError("Upload must be bounded, nonempty scientific data bytes")
    suffix = Path(filename).suffix.lower()
    if kind == "auto":
        kind = ("molecular" if suffix in MOLECULAR_SUFFIXES else "periodic" if suffix == ".cif"
                else "hessian" if suffix == ".hess" else "pseudopotential" if suffix == ".upf"
                else "native_result" if suffix in {".out", ".log", ".txt"} else None)
        if suffix == ".json":
            data = _unique_json(raw.decode("utf-8-sig", errors="strict"))
            if isinstance(data, dict):
                schema = data.get("schema_version")
                kind = "periodic" if schema in {"cochem.periodic-structure.v1", "cochem.periodic-structure.validated.v1"} else "molecular" if data.get("schema_name") in {"qcschema_molecule", "qcschema_input", "qcschema_output"} or "symbols" in data else "native_result"
        if suffix in {".npz", ".h5", ".hdf5"}:
            kind = "physical_data"
    if kind not in KINDS:
        raise ValueError("Unsupported scientific input type or format")
    if kind in {"molecular", "conformer_pool"} and len(raw) > 8 * 1024 * 1024:
        raise ValueError("Molecular input exceeds the bounded text intake limit")
    library = _library(Path(artifact_dir))
    input_id = uuid.uuid4().hex
    temporary = Path(tempfile.mkdtemp(prefix=".incoming-", dir=library))
    destination = library / input_id
    try:
        original = temporary / ("original" + suffix)
        with original.open("wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        records, metadata = _parse(original, kind, filename=filename, producer=producer, energy_unit=energy_unit)
        digest = hashlib.sha256(raw).hexdigest()
        for index, record in enumerate(records):
            record.update(source_sha256=digest, source_filename=filename, record_index=index)
        receipt = {"schema_version": "cochem.student-input/1", "input_id": input_id,
            "kind": kind, "filename": filename, "sha256": digest, "size_bytes": len(raw),
            "path": str(destination / original.name), "records": records, "metadata": metadata,
            "validation_status": "canonical_structure_and_original_integrity_verified",
            "scientific_execution_performed": False}
        receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
        with (temporary / "receipt.json").open("wb") as output:
            output.write(_canonical(receipt))
            output.flush()
            os.fsync(output.fileno())
        original.chmod(0o400)
        (temporary / "receipt.json").chmod(0o400)
        os.replace(temporary, destination)
        if os.name == "posix":
            directory = os.open(library, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        return receipt
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _load_retained_input(folder: Path) -> dict:
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Student input receipt directories must be owned regular directories")
    receipt_path = folder / "receipt.json"
    if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size > MAX_EXPANDED_BYTES:
        raise ValueError("Student input receipt is absent, linked or oversized")
    receipt = _unique_json(receipt_path.read_text(encoding="utf-8"))
    if (not isinstance(receipt, dict) or receipt.get("schema_version") != "cochem.student-input/1"
            or receipt.get("input_id") != folder.name or receipt.get("kind") not in KINDS
            or receipt.get("scientific_execution_performed") is not False):
        raise ValueError("Student input receipt identity or schema is invalid")
    filename = receipt.get("filename")
    if not isinstance(filename, str) or Path(filename).name != filename or re.search(r"[\x00-\x1f/\\:]", filename):
        raise ValueError("Retained original filename is invalid")
    sealed = dict(receipt)
    claim = sealed.pop("receipt_sha256", None)
    if hashlib.sha256(_canonical(sealed)).hexdigest() != claim:
        raise ValueError("Student input receipt checksum mismatch")
    original = folder / ("original" + Path(filename).suffix.lower())
    if (receipt.get("path") != str(original) or original.is_symlink() or not original.is_file()
            or original.stat().st_size != receipt["size_bytes"] or original.stat().st_size > MAX_FILE_BYTES):
        raise ValueError("Student input original is absent, linked, changed or outside its owned directory")
    if hashlib.sha256(original.read_bytes()).hexdigest() != receipt["sha256"]:
        raise ValueError("Student input original checksum mismatch")
    parsed_records, parsed_metadata = _parse(original, receipt["kind"], filename=filename,
        producer=receipt["metadata"].get("producer_declaration"), energy_unit=receipt["metadata"].get("energy_unit"))
    for index, record in enumerate(parsed_records):
        record.update(source_sha256=receipt["sha256"], source_filename=filename, record_index=index)
    if len(parsed_records) != len(receipt["records"]):
        raise ValueError("Retained structure inventory disagrees with canonical parsing")
    critical = {"symbols", "elements", "coords", "charge", "multiplicity", "ghost_indices", "coordinates_unit",
        "source_coordinates_unit", "fragments", "fragment_charges", "fragment_multiplicities",
        "imported_energy", "imported_energy_unit", "source_sha256", "record_index"}
    for old, current in zip(receipt["records"], parsed_records, strict=True):
        if not isinstance(old, dict) or not {"symbols", "coords"}.issubset(old):
            raise ValueError("Retained molecular records lack their complete nuclear geometry")
        for key in critical.intersection(old):
            if key not in current or _canonical(old[key]) != _canonical(current[key]):
                raise ValueError("Retained metadata disagrees with canonical parsing of the original input")
        for key in ("nuclides", "mass_numbers"):
            identity = old.get("nuclear_identity", {})
            if key in identity and identity[key] != current.get("nuclear_identity", {}).get(key):
                raise ValueError("Retained isotope identity disagrees with original canonical parsing")
    if _canonical(parsed_records) == _canonical(receipt["records"]) and _canonical(parsed_metadata) == _canonical(receipt["metadata"]):
        return receipt
    # BASE updates may add derived display/qualification fields. The original
    # sealed record stays immutable; a new explicit revalidation envelope binds
    # current derived metadata to the same untouched original and receipt.
    current = dict(receipt, records=parsed_records, metadata=parsed_metadata)
    current.pop("receipt_sha256")
    current["source_receipt"] = {"path": str(receipt_path), "receipt_sha256": claim,
        "file_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    current["revalidation"] = {"schema_version": "cochem.student-input-revalidation/1",
        "original_bytes_verified": True, "original_critical_structure_verified": True,
        "derived_metadata_recomputed": True, "original_receipt_modified": False}
    current["receipt_sha256"] = hashlib.sha256(_canonical(current)).hexdigest()
    return current


def scan_ingested_inputs(artifact_dir: Path) -> dict:
    """Recover valid inputs independently, retaining explicit rejected originals."""
    library = _library(Path(artifact_dir))
    entries = sorted(item for item in library.iterdir() if re.fullmatch(r"[0-9a-f]{32}", item.name))
    if len(entries) > MAX_RECORDS:
        raise ValueError("Student input library exceeds bounded receipt inventory")
    accepted, rejected = [], []
    for folder in entries:
        try:
            accepted.append(_load_retained_input(folder))
        except (ValueError, OSError, KeyError, TypeError, UnicodeError) as error:
            rejected.append({"input_id": folder.name, "reason": str(error), "original_retained": True})
    return {"inputs": accepted, "rejections": rejected}


def list_ingested_inputs(artifact_dir: Path) -> list[dict]:
    """Strict service intake: any damaged original is a visible integrity error."""
    scanned = scan_ingested_inputs(artifact_dir)
    if scanned["rejections"]:
        raise ValueError("Invalid retained input: " + scanned["rejections"][0]["reason"])
    return scanned["inputs"]


def deduplicate_ingested_pools(input_ids: list[str], *, artifact_dir: Path,
                              charge: int | None = None, multiplicity: int | None = None,
                              comparison_protocol: str | None = None) -> dict:
    """Apply the canonical pool union while retaining every original observation."""
    from cochem_base.intake.conformer_engine import sieve_ingested_records
    if not input_ids or len(input_ids) != len(set(input_ids)):
        raise ValueError("Choose one or more distinct imported pool inputs")
    library = {item["input_id"]: item for item in list_ingested_inputs(artifact_dir)}
    records, sources = [], []
    for input_id in input_ids:
        receipt = library.get(input_id)
        if receipt is None or receipt["kind"] not in {"conformer_pool", "molecular"}:
            raise ValueError("Deduplication requires verified molecular or explicitly declared conformer pool inputs")
        for record in receipt["records"]:
            if record.get("requires_counterpoise_adapter"):
                raise ValueError("Ordinary conformer deduplication cannot admit ghost centers")
            records.append(record)
        sources.append({"input_id": input_id, "source_sha256": receipt["sha256"],
            "source_filename": receipt["filename"], "producer_declaration": receipt["metadata"].get("producer_declaration")})
    if len(records) > MAX_RECORDS:
        raise ValueError("Selected conformer pool exceeds bounded sieve inventory")
    result = sieve_ingested_records(records, charge=charge, multiplicity=multiplicity,
                                   comparison_protocol=comparison_protocol)
    result.update(input_count=result["count"], source_inputs=sources,
                  stationary_minima_verified=False, scientific_execution_performed=False)
    return result


def preview_ingested_input(input_id: str, *, artifact_dir: Path, limit: int = 500, dataset_limit: int = 100) -> list[dict]:
    """Preview bounded admitted arrays without inferring missing units/provenance."""
    receipts = {item["input_id"]: item for item in list_ingested_inputs(artifact_dir)}
    receipt = receipts.get(input_id)
    if receipt is None:
        raise ValueError("Choose a verified input from this student's library")
    return preview_scientific_archive(Path(receipt["path"]), limit=limit, dataset_limit=dataset_limit)


def preview_scientific_archive(path: Path, *, limit: int = 500, dataset_limit: int = 100) -> list[dict]:
    """Inspect an unchanged regular scientific archive under the intake bounds.

    Result provenance must be verified by the caller. This function validates
    storage safety and previews values; it does not qualify their science.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("Preview limit must be an integer from 1 to 500")
    if isinstance(dataset_limit, bool) or not isinstance(dataset_limit, int) or not 1 <= dataset_limit <= 100:
        raise ValueError("Dataset preview limit must be an integer from 1 to 100")
    path = Path(path).expanduser().absolute()
    if (any(component.is_symlink() for component in [path, *path.parents])
            or not path.is_file() or not 1 <= path.stat().st_size <= MAX_FILE_BYTES):
        raise ValueError("Scientific previews require a bounded regular file without symbolic links")
    with path.open("rb") as stream:
        original_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    if path.suffix.lower() in {".h5", ".hdf5"}:
        from cochem_base.spectroscopy.parser import read_hdf5_dataset_previews
        _inspect_binary(path)
        result = _jsonable(read_hdf5_dataset_previews(path, limit=limit)[:dataset_limit])
    elif path.suffix.lower() == ".npz":
        import numpy as np
        inventory = _inspect_binary(path)
        result = []
        with np.load(path, allow_pickle=False) as archive:
            for entry in inventory["arrays"][:dataset_limit]:
                array = archive[entry["name"]]
                shown = array.reshape(-1)[:limit]
                result.append({"name": entry["name"], "shape": list(array.shape), "dtype": str(array.dtype),
                    "units": "[MISSING DATA]", "source": "[MISSING DATA]", "shown": len(shown),
                    "total": int(array.size), "values": _jsonable(shown)})
    else:
        raise ValueError("Dataset previews require NPZ or HDF5 physical data")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != original_sha256:
            raise ValueError("Scientific archive changed during inspection")
    return result
