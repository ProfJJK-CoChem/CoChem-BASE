"""Bounded, data-only scientific inputs for the student Actions transport.

Integrity is distinct from scientific acceptance. Native R2 and Hessian
validators still have to verify the original outputs and geometry. No uploaded
file is imported, executed, or used as an executable/interpreter configuration.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import uuid
import zipfile

from .student_request import canonical_json, safe_relative_path, strict_json


SCHEMA = "cochem.scientific-input-bundle/1"
TRANSPORT_SCHEMA = "cochem.scientific-input-transport/1"
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_FILES = 512
MANIFEST_NAME = "scientific-input-manifest.json"
KINDS = {"r2_reference", "read_hessian"}
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_EXTENSIONS = {".xyz", ".out", ".log", ".json", ".hess", ".txt", ".dat"}


def _identity(request_id: str, geometry_sha256: str, kind: str, entrypoint: str) -> None:
    if not isinstance(request_id, str) or str(uuid.UUID(request_id)) != request_id:
        raise ValueError("Scientific inputs require the exact canonical request UUID")
    if not isinstance(geometry_sha256, str) or not _DIGEST.fullmatch(geometry_sha256):
        raise ValueError("Scientific inputs require the original calculation geometry SHA-256")
    if kind not in KINDS:
        raise ValueError("Select an R2 reference or READ Hessian input bundle")
    safe_relative_path(entrypoint)


def _file(name: str, contents: bytes) -> None:
    safe_relative_path(name)
    if any(character in name for character in '<>"|?*'):
        raise ValueError("Scientific data filenames must be valid across supported platforms")
    if PurePosixPath(name).suffix.lower() not in _EXTENSIONS:
        raise ValueError("Scientific input files must have an approved data-file extension")
    if not isinstance(contents, bytes) or not 0 < len(contents) <= MAX_FILE_BYTES:
        raise ValueError("Scientific input files must be nonempty and at most 16 MiB")
    if contents.startswith(b"\x7fELF") or contents[:2] == b"MZ":
        raise ValueError("Native executables are not scientific input data")


def _inventory(files: dict[str, bytes]) -> dict:
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError("A scientific bundle requires 1–512 data files")
    if MANIFEST_NAME in files:
        raise ValueError("The scientific input manifest name is reserved")
    total = 0
    identities = {}
    names = set()
    for name, contents in files.items():
        _file(name, contents)
        folded = name.casefold()
        if folded in names or any(folded.startswith(other + "/") or other.startswith(folded + "/") for other in names):
            raise ValueError("Scientific data filenames collide or contain a file as a parent")
        names.add(folded)
        total += len(contents)
        identities[name] = {"sha256": hashlib.sha256(contents).hexdigest(), "size_bytes": len(contents)}
    if total > MAX_EXPANDED_BYTES:
        raise ValueError("Expanded scientific input exceeds 64 MiB")
    return identities


def _read_zip(contents: bytes) -> dict[str, bytes]:
    if not isinstance(contents, bytes) or not 0 < len(contents) <= MAX_ZIP_BYTES:
        raise ValueError("The scientific input ZIP must be at most 16 MiB")
    result, total, names = {}, 0, set()
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            if len(archive.infolist()) > MAX_FILES + 1:
                raise ValueError("The scientific ZIP has too many entries")
            for item in archive.infolist():
                name = item.filename
                path = safe_relative_path(name.rstrip("/") if item.is_dir() else name)
                if str(path).casefold() in names:
                    raise ValueError("Duplicate or case-colliding scientific ZIP path")
                names.add(str(path).casefold())
                mode = item.external_attr >> 16
                if (item.flag_bits & 1 or stat.S_ISLNK(mode)
                        or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}):
                    raise ValueError("Scientific ZIP links, special files and encryption are prohibited")
                if item.is_dir():
                    continue
                if not 0 < item.file_size <= MAX_FILE_BYTES:
                    raise ValueError("Scientific ZIP contains an empty or oversized file")
                total += item.file_size
                if total > MAX_EXPANDED_BYTES:
                    raise ValueError("Expanded scientific input exceeds 64 MiB")
                with archive.open(item) as handle:
                    raw = handle.read(MAX_FILE_BYTES + 1)
                if len(raw) != item.file_size:
                    raise ValueError("Scientific ZIP length differs from its file inventory")
                _file(name, raw)
                result[name] = raw
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError("The scientific input is not a supported intact ZIP") from error
    return result


def _reference_names(files: dict[str, bytes], entrypoint: str) -> None:
    """Validate every portable R2 dependency, including nested CBS point outputs."""
    manifest = strict_json(files[entrypoint])
    if manifest.get("schema_version") != "cochem.r2-reference/1":
        raise ValueError("R2 input requires a genuine reference-manifest schema")
    monomers = manifest.get("monomers")
    if not isinstance(monomers, list) or len(monomers) != 2:
        raise ValueError("The R2 reference manifest must contain two monomers")

    def reference(record: dict) -> str:
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("Each R2 source reference requires only its path and SHA-256")
        name = record["path"]
        safe_relative_path(name)
        if (name not in files or not isinstance(record["sha256"], str)
                or hashlib.sha256(files[name]).hexdigest() != record["sha256"]):
            raise ValueError("R2 reference bytes are absent or differ from their recorded SHA-256")
        return name

    for monomer in monomers:
        if not isinstance(monomer, dict):
            raise ValueError("The R2 monomer must be an object")
        for field in ("geometry", "lower_cardinal_output", "upper_cardinal_output"):
            reference(monomer.get(field))
        evidence = monomer.get("geometry_optimization_evidence")
        if evidence is not None:
            name = reference(evidence)
            data = strict_json(files[name])
            if data.get("schema_version") != "cochem.bounded-cbs-reference/1":
                raise ValueError("The nested R2 geometry evidence schema is unsupported")
            points = data.get("evaluations")
            if not isinstance(points, list) or not 1 <= len(points) <= MAX_FILES:
                raise ValueError("Nested R2 geometry evidence requires bounded actual point records")
            for point in points:
                if not isinstance(point, dict) or not isinstance(point.get("basis_results"), dict):
                    raise ValueError("Each nested R2 point requires its basis output records")
                for basis in ("cc-pVTZ", "cc-pVQZ"):
                    record = point["basis_results"].get(basis)
                    if not isinstance(record, dict):
                        raise ValueError("Each nested R2 point requires both cardinal output files")
                    reference({"path": record.get("output_path"), "sha256": record.get("output_sha256")})


def build_bundle(files: dict[str, bytes], *, kind: str, entrypoint: str,
                 request_id: str, geometry_sha256: str) -> tuple[bytes, dict]:
    """Seal original data bytes to one request before the Git blob upload."""
    _identity(request_id, geometry_sha256, kind, entrypoint)
    inventory = _inventory(files)
    if entrypoint not in files:
        raise ValueError("The selected scientific entrypoint is absent")
    if kind == "r2_reference":
        _reference_names(files, entrypoint)
    elif not entrypoint.lower().endswith(".hess"):
        raise ValueError("READ input requires its native ORCA .hess entrypoint")
    manifest = {"schema_version": SCHEMA, "request_id": request_id,
                "geometry_sha256": geometry_sha256, "kind": kind,
                "entrypoint": entrypoint, "files": inventory}
    manifest_bytes = canonical_json(manifest)
    if sum(len(raw) for raw in files.values()) + len(manifest_bytes) > MAX_EXPANDED_BYTES:
        raise ValueError("The complete sealed scientific input exceeds 64 MiB expanded")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted({**files, MANIFEST_NAME: manifest_bytes}.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | 0o444) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    contents = buffer.getvalue()
    if len(contents) > MAX_ZIP_BYTES:
        raise ValueError("The sealed scientific input exceeds the 16 MiB ZIP limit")
    descriptor = {"schema_version": TRANSPORT_SCHEMA, "kind": kind, "entrypoint": entrypoint,
                  "bundle_sha256": hashlib.sha256(contents).hexdigest(),
                  "bundle_size_bytes": len(contents), "geometry_sha256": geometry_sha256}
    return contents, descriptor


def verify_bundle(contents: bytes, *, request_id: str, geometry_sha256: str,
                  kind: str, entrypoint: str) -> dict:
    """Check association and all bytes before creating any extracted file."""
    _identity(request_id, geometry_sha256, kind, entrypoint)
    files = _read_zip(contents)
    if MANIFEST_NAME not in files:
        raise ValueError("The sealed scientific input manifest is absent")
    raw = files.pop(MANIFEST_NAME)
    manifest = strict_json(raw)
    fields = {"schema_version", "request_id", "geometry_sha256", "kind", "entrypoint", "files"}
    if (set(manifest) != fields or manifest.get("schema_version") != SCHEMA
            or canonical_json(manifest) != raw):
        raise ValueError("Unsupported or noncanonical scientific input manifest")
    for name, expected in (("request_id", request_id), ("geometry_sha256", geometry_sha256),
                           ("kind", kind), ("entrypoint", entrypoint)):
        if manifest[name] != expected:
            raise ValueError("The scientific inputs belong to a different " + name)
    if manifest["files"] != _inventory(files) or entrypoint not in files:
        raise ValueError("Scientific input files differ from their sealed inventory")
    if kind == "r2_reference":
        _reference_names(files, entrypoint)
    elif not entrypoint.lower().endswith(".hess"):
        raise ValueError("READ input requires its native ORCA .hess entrypoint")
    return {"manifest": manifest, "manifest_sha256": hashlib.sha256(raw).hexdigest(), "files": files,
            "scientific_validation_performed": False}


def _write_files(files: dict[str, bytes], destination: Path) -> dict[str, Path]:
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Scientific input extraction requires a new owned directory")
    parent = destination.parent
    if not parent.is_dir() or parent.resolve() != parent:
        raise ValueError("Scientific input destination must have an existing nonsymlink parent")
    staging = Path(tempfile.mkdtemp(prefix=".scientific-inputs-", dir=parent))
    try:
        for name, raw in files.items():
            path = staging.joinpath(*safe_relative_path(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open("xb") as handle:
                handle.write(raw)
            path.chmod(0o444)
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {name: destination.joinpath(*PurePosixPath(name).parts) for name in files}


def extract_bundle(contents: bytes, destination: Path, *, request_id: str,
                   geometry_sha256: str, kind: str, entrypoint: str) -> dict:
    verified = verify_bundle(contents, request_id=request_id, geometry_sha256=geometry_sha256,
                             kind=kind, entrypoint=entrypoint)
    paths = _write_files(verified["files"], destination)
    return {**verified, "paths": paths, "entrypoint_path": paths[entrypoint]}


def _portable_r2(files: dict[str, bytes]) -> tuple[str, dict[str, bytes]]:
    candidates = []
    for name, raw in files.items():
        if name.lower().endswith(".json"):
            data = strict_json(raw)
            if data.get("schema_version") == "cochem.r2-reference/1":
                candidates.append((name, data))
    if len(candidates) != 1:
        raise ValueError("Upload one R2 manifest and all of its authentic source files in the ZIP")
    original_name, manifest = candidates[0]
    portable = dict(files)
    digest_names = {}
    for name, raw in files.items():
        digest_names.setdefault(hashlib.sha256(raw).hexdigest(), []).append(name)
    mappings = []

    def locate(record: dict) -> str:
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("R2 references require recorded original path and SHA-256")
        original = record["path"]
        digest = record["sha256"]
        if not isinstance(original, str) or not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError("The original R2 source identity is invalid")
        matches = digest_names.get(digest, [])
        if not matches:
            raise ValueError("Upload the raw source bytes for every R2 reference and nested output")
        # Equal digests imply equal retained bytes. Preserve the original path
        # and exact chosen uploaded name as data; never access an external path.
        name = original if original in matches else sorted(matches)[0]
        mappings.append({"original_path": original, "uploaded_path": name, "sha256": digest})
        return name

    monomers = manifest.get("monomers")
    if not isinstance(monomers, list) or len(monomers) != 2:
        raise ValueError("The R2 reference manifest must contain two monomers")
    for monomer in monomers:
        if not isinstance(monomer, dict):
            raise ValueError("The R2 monomer must be an object")
        for field in ("geometry", "lower_cardinal_output", "upper_cardinal_output"):
            record = monomer.get(field)
            record["path"] = locate(record)
        record = monomer.get("geometry_optimization_evidence")
        if record is not None:
            name = locate(record)
            evidence = strict_json(files[name])
            if evidence.get("schema_version") != "cochem.bounded-cbs-reference/1":
                raise ValueError("The nested R2 geometry evidence schema is unsupported")
            points = evidence.get("evaluations")
            if not isinstance(points, list) or not 1 <= len(points) <= MAX_FILES:
                raise ValueError("Nested R2 geometry evidence requires bounded actual point records")
            for point in points:
                if not isinstance(point, dict) or not isinstance(point.get("basis_results"), dict):
                    raise ValueError("Each nested R2 point requires its source output records")
                for basis in ("cc-pVTZ", "cc-pVQZ"):
                    output = point["basis_results"].get(basis)
                    if not isinstance(output, dict):
                        raise ValueError("Each nested R2 point requires both cardinal outputs")
                    output["output_path"] = locate({"path": output.get("output_path"), "sha256": output.get("output_sha256")})
            normalized = canonical_json(evidence)
            normalized_name = "portable-evidence-" + hashlib.sha256(normalized).hexdigest() + ".json"
            if normalized_name in portable and portable[normalized_name] != normalized:
                raise ValueError("Normalized R2 evidence conflicts with an uploaded file")
            portable[normalized_name] = normalized
            record.update(path=normalized_name, sha256=hashlib.sha256(normalized).hexdigest())
    normalized = canonical_json(manifest)
    entrypoint = "portable-r2-reference.json"
    if entrypoint in portable and portable[entrypoint] != normalized:
        raise ValueError("The portable R2 entrypoint conflicts with an uploaded file")
    portable[entrypoint] = normalized
    receipt = {"schema_version": "cochem.scientific-input-normalization/1", "kind": "r2_reference",
               "original_manifest": {"path": original_name, "sha256": hashlib.sha256(files[original_name]).hexdigest()},
               "portable_manifest": {"path": entrypoint, "sha256": hashlib.sha256(normalized).hexdigest()},
               "reference_path_mappings": mappings,
               "scope": "Only source paths and dependent JSON hashes were normalized; raw native output and geometry bytes are unchanged. Scientific provenance remains subject to native validation."}
    receipt_name = "scientific-input-normalization.json"
    if receipt_name in portable:
        raise ValueError("The normalization receipt filename is reserved")
    portable[receipt_name] = canonical_json(receipt)
    _inventory(portable)
    _reference_names(portable, entrypoint)
    return entrypoint, portable


def ingest_scientific_upload(kind: str, raw: bytes, filename: str, *,
                             geometry_xyz: str, destination: Path) -> dict:
    """Prepare GUI uploads without asking the student for filesystem paths.

    R2 ZIPs may contain native absolute path references. Their recorded hashes
    resolve only to uploaded bytes; originals remain unchanged for inspection.
    The GUI/worker must still invoke native chemistry and geometry validators.
    """
    if kind not in KINDS or not isinstance(geometry_xyz, str) or not geometry_xyz:
        raise ValueError("Scientific upload requires its kind and selected geometry")
    safe_relative_path(filename)
    if kind == "read_hessian":
        if not filename.lower().endswith(".hess"):
            raise ValueError("Upload the authentic ORCA .hess file for READ initialization")
        _file(filename, raw)
        entrypoint, files = "initial.hess", {"initial.hess": raw}
    else:
        if not filename.lower().endswith(".zip"):
            raise ValueError("Upload an R2 ZIP containing the manifest and all referenced native files")
        entrypoint, files = _portable_r2(_read_zip(raw))
    paths = _write_files(files, destination)
    return {"kind": kind, "entrypoint": entrypoint, "files": files,
            "entrypoint_path": paths[entrypoint], "geometry_sha256": hashlib.sha256(geometry_xyz.encode("utf-8")).hexdigest(),
            "input_scope": "Scientific input integrity and portable path linkage only; native method, geometry and provenance validation remains required.",
            "scientific_validation_performed": False}


def transform_read_hessian(source: Path, geometry_xyz: str, output: Path) -> dict:
    """Validate and covariantly move a real Hessian into BASE's deck frame.

    This transforms the supplied Cartesian derivative tensor; it generates no
    electronic derivatives. Original bytes stay unchanged. A native execution
    still has to verify ORCA accepts this initializer and converges its request.
    """
    import numpy as np
    from cochem.core.context import assert_writable_path
    from cochem_base.chain.chain import parse_orca_hessian
    from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    from cochem_base.physics.eckart_aligner import align_coordinates, verify_so3_closure
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact

    source = Path(source).absolute()
    output = Path(output).absolute()
    if (source.is_symlink() or not source.is_file() or source.suffix.lower() != ".hess"
            or not 0 < source.stat().st_size <= MAX_FILE_BYTES):
        raise ValueError("READ requires a bounded original native ORCA Hessian")
    if output.exists() or output.is_symlink() or output.suffix.lower() != ".hess":
        raise ValueError("The transformed Hessian must be a new owned .hess file")
    if not output.parent.is_dir() or output.parent.resolve() != output.parent:
        raise ValueError("The transformed Hessian needs an existing nonsymlink destination")
    assert_writable_path(output)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    identity = parse_geometry_identity(geometry_xyz)
    if not 1 <= len(identity.elements) <= 50:
        raise ValueError("Student READ initialization is bounded to 1–50 ordered atoms")
    original_coordinates = np.asarray(identity.coordinates_angstrom, dtype=float)
    artifact = load_hessian_artifact(source)
    if artifact.symbols != identity.elements:
        raise ValueError("The original Hessian atom identities/order differ from the selected geometry")
    geometry_error = float(np.max(np.abs(artifact.coordinates_angstrom - original_coordinates)))
    if geometry_error > 1e-8:
        raise ValueError("The original Hessian Cartesian frame differs from the selected geometry")
    deck_coordinates, rotation, rmsd = align_coordinates(
        original_coordinates, original_coordinates, masses=identity.masses_u)
    verify_so3_closure(rotation)
    # align_coordinates uses x_deck = U x_original for column Cartesian vectors.
    # Therefore the Hessian is H_deck = block(U) H_original block(U).T.
    block_rotation = np.kron(np.eye(len(identity.elements)), rotation)
    transformed = block_rotation @ artifact.hessian_hartree_bohr2 @ block_rotation.T
    if not np.isfinite(transformed).all() or not np.allclose(transformed, transformed.T, atol=1e-10, rtol=1e-8):
        raise ValueError("The transformed Cartesian Hessian is not finite and symmetric")
    eigen_error = float(np.max(np.abs(np.linalg.eigvalsh(transformed)
                                     - np.linalg.eigvalsh(artifact.hessian_hartree_bohr2))))
    if eigen_error > 1e-9 * max(1.0, float(np.max(np.abs(transformed)))):
        raise ValueError("Hessian covariance failed to preserve its Cartesian eigenvalues")
    dimension = len(transformed)
    lines = ["$orca_hessian_file", "$hessian", str(dimension)]
    for start in range(0, dimension, 5):
        columns = list(range(start, min(start + 5, dimension)))
        lines.append(" ".join(str(index) for index in columns))
        for row in range(dimension):
            lines.append(str(row) + " " + " ".join(format(float(transformed[row, column]), ".17g") for column in columns))
    lines += ["$atoms", str(len(identity.elements))]
    for element, mass, xyz in zip(identity.elements, identity.masses_u, deck_coordinates / BOHR_TO_ANGSTROM, strict=True):
        lines.append(element + " " + format(float(mass), ".17g") + " "
                     + " ".join(format(float(value), ".17g") for value in xyz))
    lines.append("$end")
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    try:
        with output.open("xb") as handle:
            handle.write(raw)
        output.chmod(0o444)
        parsed = parse_orca_hessian(output)
        if (parsed is None or not np.allclose(parsed["hessian"], transformed, atol=1e-13, rtol=1e-13)
                or [atom["symbol"] for atom in parsed["atoms"]] != list(identity.elements)
                or not np.allclose(np.asarray([atom["coords"] for atom in parsed["atoms"]]) * BOHR_TO_ANGSTROM,
                                   deck_coordinates, atol=1e-12, rtol=0)):
            raise ValueError("The transformed native Hessian did not round-trip its exact tensor and geometry")
        if hashlib.sha256(source.read_bytes()).hexdigest() != before:
            raise ValueError("The original Hessian changed during frame transformation")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    receipt = {"schema_version": "cochem.read-hessian-frame/1", "source_sha256": before,
               "source_path": str(source), "transformed_path": str(output),
               "transformed_sha256": hashlib.sha256(raw).hexdigest(),
               "geometry_sha256": hashlib.sha256(geometry_xyz.encode("utf-8")).hexdigest(),
               "ordered_elements": list(identity.elements), "nuclides": list(identity.nuclides),
               "masses_u": list(map(float, identity.masses_u)), "coordinate_unit": "angstrom",
               "hessian_unit": "hartree/bohr^2", "original_coordinates_angstrom": original_coordinates.tolist(),
               "deck_coordinates_angstrom": deck_coordinates.tolist(), "rotation": rotation.tolist(),
               "source_geometry_maximum_error_angstrom": geometry_error,
               "source_geometry_tolerance_angstrom": 1e-8, "alignment_rmsd_angstrom": float(rmsd),
               "cartesian_eigenvalue_maximum_error": eigen_error,
               "tensor_sha256": hashlib.sha256(np.asarray(transformed, dtype="<f8").tobytes()).hexdigest(),
               "deck_coordinates_sha256": hashlib.sha256(np.asarray(deck_coordinates, dtype="<f8").tobytes()).hexdigest(),
               "validation": "complete native $atoms and symmetric finite 3N-by-3N tensor; ordered geometry binding; proper rotation; tensor/eigenvalue/native-format round-trip; unchanged source bytes",
               "scientific_execution_performed": False,
               "scope": "Covariant transformation of supplied Cartesian derivatives into the mass-weighted BASE deck frame. This is not a new electronic Hessian or stationary-point acceptance."}
    return {"path": output, "receipt": receipt, "coordinates_angstrom": deck_coordinates,
            "hessian_hartree_bohr2": transformed}
