"""Portable original-ingestion/PAW data; never execute an uploaded input file."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import re
import shutil
import stat
import tempfile
import zipfile

from .student_request import canonical_json, safe_relative_path, strict_json

MAX_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_DATA_FILES = 64
FORMATS = {"xyz", "mol", "sdf", "mol2", "pdb", "qcschema", "json"}


def _source(record: dict, *, formats: set[str], maximum: int = 32 * 1024 * 1024) -> tuple[str, bytes]:
    if not isinstance(record, dict) or not {"filename", "format", "content"}.issubset(record):
        raise ValueError("Original ingestion requires filename, explicit format and unchanged bytes")
    name = record["filename"]
    if len(safe_relative_path(name).parts) != 1 or record["format"] not in formats:
        raise ValueError("Select an ordinary source filename and supported explicit format")
    contents = record["content"]
    if not isinstance(contents, bytes) or not 0 < len(contents) <= maximum:
        raise ValueError("Original ingestion content is empty or exceeds its bounded size")
    return name, contents


def build_data_bundle(intake: dict, *, kind: str, request_id: str, geometry_sha256: str) -> tuple[bytes, dict]:
    """Seal original source files and explicit selection; science is validated later."""
    files: dict[str, bytes] = {}
    if kind == "molecular_ingestion":
        filename, contents = _source(intake, formats=FORMATS)
        index = intake.get("record_index")
        if type(index) is not int or not 0 <= index < 512:
            raise ValueError("Explicitly select one molecular record; records are never silently discarded")
        extension = "json" if intake["format"] == "qcschema" else intake["format"]
        source_path = "source/original." + extension
        files[source_path] = contents
        receipt = {"kind": kind, "source": {"filename": filename, "format": intake["format"],
            "path": source_path, "sha256": hashlib.sha256(contents).hexdigest()}, "record_index": index}
    elif kind == "periodic_inputs":
        if not isinstance(intake, dict) or set(intake) != {"structure", "pseudopotentials"}:
            raise ValueError("Periodic inputs require their original structure and authenticated PAW files")
        filename, contents = _source(intake["structure"], formats={"cif", "json"}, maximum=8 * 1024 * 1024)
        source_path = "source/original." + intake["structure"]["format"]
        files[source_path] = contents
        potentials = intake["pseudopotentials"]
        if not isinstance(potentials, dict) or not 1 <= len(potentials) <= 20:
            raise ValueError("Provide one PAW file for each of at most twenty periodic elements")
        identities = {}
        for element, potential in potentials.items():
            if not isinstance(element, str) or not re.fullmatch(r"[A-Z][a-z]?", element):
                raise ValueError("PAW file assignments require canonical element symbols")
            if not isinstance(potential, dict) or not {"filename", "sha256", "content"}.issubset(potential):
                raise ValueError("Every PAW input needs its original filename, SHA-256 and bytes")
            name, data = _source({**potential, "format": "upf"}, formats={"upf"})
            digest = hashlib.sha256(data).hexdigest()
            if potential["sha256"] != digest:
                raise ValueError("The uploaded PAW file differs from its assigned SHA-256")
            path = "pseudopotentials/" + element + ".UPF"
            files[path] = data
            identities[element] = {"filename": name, "path": path, "sha256": digest}
        receipt = {"kind": kind, "structure": {"filename": filename, "format": intake["structure"]["format"],
            "path": source_path, "sha256": hashlib.sha256(contents).hexdigest()}, "pseudopotentials": identities}
    else:
        raise ValueError("Select molecular ingestion or periodic PAW input data")
    files["input-receipt.json"] = canonical_json(receipt)
    if len(files) > MAX_DATA_FILES or sum(map(len, files.values())) > MAX_EXPANDED_BYTES:
        raise ValueError("Original inputs exceed the bounded data inventory")
    manifest = {"schema_version": "cochem.student-data-bundle/1", "kind": kind, "request_id": request_id,
        "geometry_sha256": geometry_sha256, "files": {name: {"size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()}}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("manifest.json", canonical_json(manifest))
        for name, contents in sorted(files.items()):
            package.writestr(name, contents)
    contents = archive.getvalue()
    if len(contents) > MAX_COMPRESSED_BYTES:
        raise ValueError("Original input ZIP exceeds the 64 MiB transport limit")
    return contents, {"kind": kind, "bundle_sha256": hashlib.sha256(contents).hexdigest(),
        "bundle_size_bytes": len(contents), "geometry_sha256": geometry_sha256}


def extract_data_bundle(contents: bytes, destination: Path, *, request_id: str, geometry_sha256: str,
                        kind: str) -> dict:
    """Verify the complete bounded ZIP before exposing any original input file."""
    if not 0 < len(contents) <= MAX_COMPRESSED_BYTES:
        raise ValueError("The original input ZIP exceeds its bounded download limit")
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Input data needs a fresh worker-owned destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".student-input-", dir=destination.parent))
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            members = archive.infolist()
            if len(members) > MAX_DATA_FILES + 1 or sum(item.file_size for item in members) > MAX_EXPANDED_BYTES:
                raise ValueError("Original inputs exceed bounded expanded size/file count")
            seen = set()
            data = {}
            for item in members:
                name = item.filename
                safe_relative_path(name)
                mode = item.external_attr >> 16
                if (name in seen or item.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                        or item.flag_bits & 1 or item.file_size > max(item.compress_size, 1) * 1000):
                    raise ValueError("Data ZIPs reject duplicate paths, directories, links, encryption and excessive compression")
                seen.add(name)
                data[name] = archive.read(item)
        manifest = strict_json(data.pop("manifest.json"))
        if (set(manifest) != {"schema_version", "kind", "request_id", "geometry_sha256", "files"}
                or manifest["schema_version"] != "cochem.student-data-bundle/1"
                or manifest["kind"] != kind or manifest["request_id"] != request_id
                or manifest["geometry_sha256"] != geometry_sha256 or set(data) != set(manifest["files"])):
            raise ValueError("Original input manifest differs from the exact request/geometry/inventory")
        for name, contents in data.items():
            identity = {"size_bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
            if manifest["files"][name] != identity:
                raise ValueError("Original source input SHA-256 or size changed")
        receipt = strict_json(data["input-receipt.json"])
        if receipt.get("kind") != kind:
            raise ValueError("Original input receipt contradicts its sealed kind")
        for name, contents in data.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
            target.chmod(0o600)
        # Native normalization validates the receipt's precise scientific fields.
        staging.rename(destination)
        return {"path": str(destination), "receipt": receipt, "manifest": manifest,
                "manifest_sha256": hashlib.sha256(canonical_json(manifest)).hexdigest(),
                "scientific_validation_performed": False}
    finally:
        if staging.exists():
            shutil.rmtree(staging)
