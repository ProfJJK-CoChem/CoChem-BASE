"""Data-only, hash-bound requests shared by the browser and hosted worker.

This module intentionally uses only the standard library: an untrusted request
is checked before downloading engines, building packages or importing providers.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import PurePosixPath
import re
import uuid

SCHEMA = "cochem.student-request/1"
MAX_PAYLOAD_BASE64_BYTES = 50 * 1024
MAX_FILE_BYTES = 24 * 1024
MAX_FILES = 16
MAX_ATOMS = 50
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def strict_json(contents: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate request field: {key}")
            result[key] = value
        return result

    def reject(value):
        raise ValueError(f"Nonfinite request value: {value}")

    result = json.loads(contents.decode("utf-8"), object_pairs_hook=unique,
                        parse_constant=reject)
    if not isinstance(result, dict):
        raise ValueError("A student request must be a JSON object")
    return result


def safe_relative_path(name: str) -> PurePosixPath:
    if (not isinstance(name, str) or not name or len(name) > 180 or "\\" in name
            or any(ord(char) < 32 for char in name) or ":" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Input paths must be ordinary relative filenames without traversal")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise ValueError("Absolute input paths are prohibited")
    reserved = {"CON", "PRN", "AUX", "NUL", *[f"COM{index}" for index in range(1, 10)],
                *[f"LPT{index}" for index in range(1, 10)]}
    if any(part.endswith((".", " ")) or part.split(".", 1)[0].upper() in reserved for part in path.parts):
        raise ValueError("Input paths cannot use reserved or ambiguous Windows filenames")
    return path


def validate_xyz(contents: bytes) -> None:
    """Validate a complete finite single-frame XYZ before expensive installation."""
    # Grammar ignores a Windows UTF-8 BOM; file identity always hashes the
    # unchanged original bytes, including that BOM.
    lines = contents.decode("utf-8-sig").splitlines()
    if not lines or not lines[0].strip().isdigit():
        raise ValueError("Upload a complete Avogadro XYZ with its atom-count and comment lines")
    count = int(lines[0].strip())
    if not 0 < count <= MAX_ATOMS or len(lines) != count + 2:
        raise ValueError("A hosted structure requires one complete XYZ of 1–50 atoms")
    for line in lines[2:]:
        fields = line.split()
        if (len(fields) != 4 or not re.fullmatch(r"(?:\d+)?[A-Z][a-z]?(?:-?\d+)?", fields[0])
                or not all(math.isfinite(float(value)) for value in fields[1:])):
            raise ValueError("Each XYZ atom requires an element/isotope and three finite coordinates")


def encode_request(request: dict) -> tuple[str, str]:
    validate_request(request)
    contents = canonical_json(request)
    encoded = base64.b64encode(contents).decode("ascii")
    if len(encoded) > MAX_PAYLOAD_BASE64_BYTES:
        raise ValueError("The structures and request exceed the 50 KiB hosted submission limit")
    return encoded, hashlib.sha256(contents).hexdigest()


def decode_request(encoded: str, expected_sha256: str) -> dict:
    if (not isinstance(encoded, str) or len(encoded) > MAX_PAYLOAD_BASE64_BYTES
            or not SHA_PATTERN.fullmatch(expected_sha256)):
        raise ValueError("Invalid or oversized hosted request")
    contents = base64.b64decode(encoded, validate=True)
    if hashlib.sha256(contents).hexdigest() != expected_sha256:
        raise ValueError("The submitted request SHA-256 differs from the uploaded bytes")
    request = strict_json(contents)
    if canonical_json(request) != contents:
        raise ValueError("Hosted requests must use the canonical JSON encoding")
    validate_request(request)
    return request


def validate_request(request: dict) -> dict:
    fields = {"schema_version", "request_id", "repository", "source_sha", "worker_source_sha", "submitted_at",
              "resources", "calculation", "provider", "capability_probe", "scientific_inputs", "t9_request", "files"}
    if set(request) != fields or request.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported student-request schema or fields")
    request_id = request["request_id"]
    if not isinstance(request_id, str) or str(uuid.UUID(request_id)) != request_id:
        raise ValueError("Request identity must be a canonical UUID")
    if not REPOSITORY_PATTERN.fullmatch(request["repository"]):
        raise ValueError("Select one GitHub owner/repository")
    if not COMMIT_PATTERN.fullmatch(request["source_sha"]):
        raise ValueError("Hosted execution requires an exact approved source commit")
    if not COMMIT_PATTERN.fullmatch(request["worker_source_sha"]):
        raise ValueError("Hosted execution requires an exact approved canonical BASE worker commit")
    if not isinstance(request["submitted_at"], str) or len(request["submitted_at"]) > 64:
        raise ValueError("Invalid submission timestamp")
    resources = request["resources"]
    if not isinstance(resources, dict) or set(resources) != {"cores", "maxcore_mb"}:
        raise ValueError("Specify only CPU count and memory per process")
    if type(resources["cores"]) is not int or resources["cores"] not in (1, 2):
        raise ValueError("Hosted jobs support one or two CPU processes")
    if type(resources["maxcore_mb"]) is not int or not 1 <= resources["maxcore_mb"] <= 1024:
        raise ValueError("Hosted memory must be 1–1024 MB per process")
    calculation, provider, probe = request["calculation"], request["provider"], request["capability_probe"]
    if sum(item is not None for item in (calculation, provider, probe)) != 1:
        raise ValueError("Submit exactly one calculation, reviewed module operation or engine-readiness check")
    if probe is not None:
        if (not isinstance(probe, dict) or set(probe) != {"engines"} or not isinstance(probe["engines"], list)
                or not probe["engines"] or len(probe["engines"]) != len(set(probe["engines"]))
                or any(engine not in {"orca", "cfour"} for engine in probe["engines"])):
            raise ValueError("A readiness check accepts only the optional ORCA and CFOUR engines")
    if calculation is not None:
        if not isinstance(calculation, dict) or calculation.get("engine") not in {"orca", "cfour", "xtb"}:
            raise ValueError("Select a connected ORCA, CFOUR or xTB calculation")
        timeout = calculation.get("timeout_seconds")
        if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 1800:
            raise ValueError("Hosted calculation time must be positive and no greater than 1800 seconds")
        if not isinstance(calculation.get("geometry"), str):
            raise ValueError("The calculation requires its complete geometry")
        validate_xyz(calculation["geometry"].encode("utf-8"))
    scientific = request["scientific_inputs"]
    if scientific is not None:
        if calculation is None or calculation["engine"] != "orca" or not isinstance(scientific, dict):
            raise ValueError("Uploaded reference/Hessian bundles require a connected ORCA request")
        if (set(scientific) != {"schema_version", "kind", "entrypoint", "bundle_sha256", "bundle_size_bytes",
                               "geometry_sha256", "blob_sha", "commit_sha", "branch", "path"}
                or scientific.get("schema_version") != "cochem.scientific-input-transport/1"
                or scientific.get("kind") not in {"r2_reference", "read_hessian"}
                or not COMMIT_PATTERN.fullmatch(scientific.get("blob_sha", ""))
                or not COMMIT_PATTERN.fullmatch(scientific.get("commit_sha", ""))
                or not SHA_PATTERN.fullmatch(scientific.get("bundle_sha256", ""))
                or scientific.get("path") != f".cochem/submissions/{request_id}/scientific-inputs.zip"
                or scientific.get("branch") != "cochem-input-" + request_id
                or type(scientific.get("bundle_size_bytes")) is not int
                or not 0 < scientific["bundle_size_bytes"] <= 16 * 1024 * 1024
                or scientific.get("geometry_sha256") != hashlib.sha256(calculation["geometry"].encode()).hexdigest()):
            raise ValueError("Scientific bundle provenance or bounded inventory is invalid")
        safe_relative_path(scientific.get("entrypoint"))
    recovery = request["t9_request"]
    if recovery is not None:
        if calculation is None or calculation["engine"] != "orca" or not isinstance(recovery, dict):
            raise ValueError("T9 recovery requires an ORCA calculation and explicit scientific active space")
        permitted = {"pyscf_version", "method", "basis", "active_electrons", "active_orbitals",
                     "active_space_rationale", "threads", "memory_mb", "timeout_seconds", "max_cycle"}
        if set(recovery) != permitted or recovery["method"] not in {"CASSCF", "NEVPT2"}:
            raise ValueError("Use the complete portable T9 scientific configuration without executable paths")
        orbitals = recovery["active_orbitals"]
        if (type(recovery["active_electrons"]) is not int or not isinstance(orbitals, list) or not orbitals
                or any(type(index) is not int or index < 0 for index in orbitals)
                or len(set(orbitals)) != len(orbitals)
                or not 1 <= recovery["active_electrons"] <= 2 * len(orbitals)
                or type(recovery["threads"]) is not int or not 1 <= recovery["threads"] <= resources["cores"]
                or type(recovery["memory_mb"]) is not int or not 64 <= recovery["memory_mb"] <= resources["cores"] * resources["maxcore_mb"]
                or type(recovery["max_cycle"]) is not int or not 1 <= recovery["max_cycle"] <= 1000
                or type(recovery["timeout_seconds"]) not in (int, float)
                or not math.isfinite(recovery["timeout_seconds"]) or not 0 < recovery["timeout_seconds"] <= 1800
                or recovery["timeout_seconds"] + calculation["timeout_seconds"] > 1800):
            raise ValueError("T9 active space or resource allocation is invalid")
        if any(not isinstance(recovery[key], str) or not recovery[key].strip() for key in ("pyscf_version", "basis", "active_space_rationale")):
            raise ValueError("T9 requires its version, basis and scientific active-space rationale")
    if provider is not None:
        if (not isinstance(provider, dict) or provider.get("schema_version") != "cochem.student-provider/1"
                or provider.get("module") not in {"topos", "torq"}
                or not isinstance(provider.get("operation"), str)):
            raise ValueError("Select a reviewed TOPOS or TORQ provider operation")
        safe_relative_path(provider.get("artifact"))
        if not SHA_PATTERN.fullmatch(provider.get("artifact_sha256", "")):
            raise ValueError("The provider input requires its SHA-256")
    files = request["files"]
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise ValueError("A request supports at most sixteen input files")
    if probe is not None and files:
        raise ValueError("An engine-readiness check does not accept scientific input files")
    for name, item in files.items():
        safe_relative_path(name)
        if (not isinstance(item, dict) or set(item) != {"content_base64", "sha256", "size_bytes"}
                or not SHA_PATTERN.fullmatch(item.get("sha256", ""))
                or type(item.get("size_bytes")) is not int
                or not 0 < item["size_bytes"] <= MAX_FILE_BYTES):
            raise ValueError("Invalid input-file inventory")
        contents = base64.b64decode(item["content_base64"], validate=True)
        if len(contents) != item["size_bytes"] or hashlib.sha256(contents).hexdigest() != item["sha256"]:
            raise ValueError(f"Uploaded file integrity failed: {name}")
        if name.lower().endswith(".xyz"):
            validate_xyz(contents)
    if provider is not None:
        item = files.get(provider["artifact"])
        if item is None or item["sha256"] != provider["artifact_sha256"]:
            raise ValueError("The selected provider structure is absent or has changed")
    return request


def requested_engine(request: dict) -> str:
    if request["calculation"] is not None:
        return request["calculation"]["engine"]
    provider = request["provider"]
    options = provider.get("options", {})
    science = options.get("topos_request", {}) if isinstance(options, dict) else {}
    engine = science.get("engine", "none") if isinstance(science, dict) else "none"
    if isinstance(engine, dict):
        engine = engine.get("name", engine.get("engine", "none"))
    if engine not in {"orca", "cfour", "xtb", "none"}:
        raise ValueError("The requested provider engine is not connected to the hosted worker")
    return engine
