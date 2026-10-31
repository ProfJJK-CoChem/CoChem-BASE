"""Bounded optional retained-file metadata; never execution authority or science."""
from __future__ import annotations

import hashlib
import os
import re
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from cochem_base.core.managed_files import (
    BoundDirectory,
    ManagedPathError,
    atomic_write_bytes,
    read_file_bytes,
)
from cochem_base.interfaces.student_request import canonical_json, safe_relative_path, strict_json

JSON_LIMIT = 2 * 1024 * 1024
MEMBER_LIMIT = 32 * 1024 * 1024
TOTAL_LIMIT = 256 * 1024 * 1024
MEMBER_COUNT_LIMIT = 16384
ZIP_LIMIT = 32 * 1024 * 1024
INDEX_LIMIT = 256
PREFIX = "cochem-local-files"
INVENTORY = PREFIX + "/inventory.json"
ENVELOPES = frozenset((INVENTORY, INVENTORY + ".sha256", "execution.json", "execution.json.sha256"))
EXCLUSIONS = ("shared-multi-job-telemetry-database", "engine-installations", "private-configuration")
SCOPE = "retained-native-files-and-submission-context"


LocalFilesError = ManagedPathError


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bounded(data: bytes, limit: int = JSON_LIMIT) -> bytes:
    if not isinstance(data, bytes) or not 0 < len(data) <= limit:
        raise LocalFilesError("Retained evidence is empty or exceeds its file limit")
    return data


@dataclass(frozen=True)
class InputSnapshot:
    """Immutable submission data, including an explicit known-source failure."""
    metadata_bytes: bytes
    files: tuple[tuple[str, bytes], ...]

    @classmethod
    def unavailable(cls, submitted_config: bytes, *, source_kind: str, code: str, message: str) -> "InputSnapshot":
        # This channel must remain available when the ordinary snapshot was
        # refused for size. Bind the bytes already read by the caller without
        # storing/serializing them into optional retained metadata.
        if not isinstance(submitted_config, bytes) or not submitted_config:
            raise LocalFilesError("Unavailable input context still needs the actual submitted bytes")
        if code not in {"INPUT_SOURCE_UNVERIFIED", "SELECTED_FRAME_UNVERIFIED",
                        "CONSTRUCTION_PROVENANCE_UNVERIFIED", "ASSEMBLED_SOURCE_CONTEXT_UNSUPPORTED"}:
            raise LocalFilesError("Choose a supported retained-input failure code")
        return cls(canonical_json({"schema_version": "cochem.local-input-context/1", "available": False,
            "submitted_config_sha256": digest(submitted_config), "source_kind": str(source_kind)[:80],
            "code": code, "message": str(message)[:400]}), ())


def build_input_snapshot(*, submitted_config: bytes, source_kind: str = "configuration_only",
                         source: dict | None = None, selected_frame: dict | None = None,
                         construction: dict | None = None) -> InputSnapshot:
    """Seal exact original/selected/submitted bytes, without granting authority.

    Source keys: filename, format, content(bytes). Selected-frame keys:
    record_index, geometry(bytes), receipt(bytes). Construction: receipt(bytes).
    Known GUI-source errors must use InputSnapshot.unavailable, never None.
    """
    config = strict_json(_bounded(submitted_config))
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    submitted = parse_geometry_identity(config["geometry"])
    if type(config.get("charge")) is not int or type(config.get("multiplicity")) is not int:
        raise LocalFilesError("Retained submitted electronic state must be explicit")
    metadata = {"schema_version": "cochem.local-input-context/1", "available": True,
        "submitted_config_sha256": digest(submitted_config), "source_kind": source_kind,
        "submitted_geometry_sha256": digest(config["geometry"].encode()),
        "submitted_state": {"charge": config["charge"], "multiplicity": config["multiplicity"]},
        "relationship": "no-selected-source-frame", "exclusions": []}
    files = [(PREFIX + "/inputs/submitted-config.json", submitted_config),
             (PREFIX + "/inputs/submitted-geometry.xyz", config["geometry"].encode())]
    if source_kind == "configuration_only":
        if any(value is not None for value in (source, selected_frame, construction)):
            raise LocalFilesError("Configuration-only context cannot hide supplied source metadata")
        metadata["exclusions"] = ["original-source-and-selection-provenance-not-supplied"]
    elif source_kind == "editor_geometry":
        if any(value is not None for value in (source, selected_frame, construction)):
            raise LocalFilesError("Editor context cannot discard an existing selected source")
        metadata["exclusions"] = ["no-original-upload-declared-for-editor-geometry"]
    elif source_kind in {"uploaded_record", "constructed_starting_geometry"}:
        if not isinstance(source, dict) or not isinstance(selected_frame, dict):
            raise LocalFilesError("Known input requires its actual original and selected frame")
        name, fmt = source["filename"], source["format"]
        if len(safe_relative_path(name).parts) != 1 or fmt not in {"xyz", "mol", "sdf", "mol2", "pdb", "json", "qcschema"}:
            raise LocalFilesError("Original input filename or explicit format is unsupported")
        raw = _bounded(source["content"], MEMBER_LIMIT)
        geometry = _bounded(selected_frame["geometry"])
        receipt_raw = _bounded(selected_frame["receipt"])
        receipt = strict_json(receipt_raw)
        index = selected_frame["record_index"]
        if (type(index) is not int or not 0 <= index < 512 or receipt.get("origin") != "canonical_ingestion"
                or receipt.get("source_sha256") != digest(raw) or receipt.get("source_frame") != index
                or receipt.get("sha256") != digest(geometry)):
            raise LocalFilesError("Selected-frame receipt is not bound to this original and canonical frame")
        frame = parse_geometry_identity(geometry.decode("utf-8"))
        from cochem_base.intake.structure_formats import parse_structure_text
        records = parse_structure_text(raw.decode("utf-8"), fmt)
        if index >= len(records):
            raise LocalFilesError("Selected original record is absent")
        record = records[index]
        labels = tuple(record.get("nuclides") or record["symbols"])
        coordinates = record.get("coordinates_angstrom", record.get("coords"))
        if hasattr(coordinates, "tolist"):
            coordinates = coordinates.tolist()
        actual = tuple(tuple(float(x) for x in row) for row in coordinates)
        if labels != frame.nuclides or actual != frame.coordinates_angstrom:
            raise LocalFilesError("Canonical selected frame differs from its original record")
        unchanged = frame.nuclides == submitted.nuclides and frame.coordinates_angstrom == submitted.coordinates_angstrom
        metadata.update(relationship="selected_frame_unchanged" if unchanged else "edited_after_selection",
            original={"filename": name, "format": fmt, "sha256": digest(raw)}, record_index=index,
            selected_frame_sha256=digest(geometry), selected_frame_receipt_sha256=digest(receipt_raw),
            source_encoded_state={"charge": record.get("charge"), "multiplicity": record.get("multiplicity")})
        extension = "json" if fmt == "qcschema" else fmt
        files.extend(((PREFIX + "/inputs/original." + extension, raw),
                      (PREFIX + "/inputs/selected-frame.xyz", geometry),
                      (PREFIX + "/inputs/selected-frame.json", receipt_raw)))
        if source_kind == "constructed_starting_geometry":
            if not isinstance(construction, dict):
                raise LocalFilesError("Known construction requires its actual retained receipt")
            construction_raw = _bounded(construction["receipt"])
            document = strict_json(construction_raw)
            if (document.get("schema_version") != "cochem.generated-starting-geometry/1"
                    or document.get("sha256") != digest(raw) or document.get("quantum_optimized") is not False):
                raise LocalFilesError("Construction provenance is not bound to the actual starting bytes")
            files.append((PREFIX + "/inputs/construction.json", construction_raw))
            metadata["construction_sha256"] = digest(construction_raw)
        elif construction is not None:
            raise LocalFilesError("Retain the known constructed-source kind explicitly")
    else:
        raise LocalFilesError("Unsupported input context; supply an explicit unavailable snapshot")
    return InputSnapshot(canonical_json(metadata), tuple(files))


def checked_root(root: Path) -> Path:
    path = Path(root).expanduser().absolute()
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_dir():
        raise LocalFilesError("Retained evidence must use an existing ordinary managed directory")
    return path


def verified_snapshot(snapshot: InputSnapshot, submitted_config: bytes) -> dict:
    """Recheck even a directly constructed data object; data is not authority."""
    if not isinstance(snapshot, InputSnapshot):
        raise LocalFilesError("Input context must be an immutable submitted snapshot")
    context = strict_json(_bounded(snapshot.metadata_bytes))
    if context.get("submitted_config_sha256") != digest(submitted_config):
        raise LocalFilesError("Retained source context belongs to another submitted request")
    if context.get("available") is False:
        if snapshot.files:
            raise LocalFilesError("Unavailable context cannot declare unverified source files")
        expected = InputSnapshot.unavailable(submitted_config, source_kind=context["source_kind"],
            code=context["code"], message=context["message"])
    else:
        files = dict(snapshot.files)
        if len(files) != len(snapshot.files):
            raise LocalFilesError("Duplicate submitted context members")
        kind = context["source_kind"]
        source = selected = construction = None
        if kind in {"uploaded_record", "constructed_starting_geometry"}:
            original = context["original"]
            extension = "json" if original["format"] == "qcschema" else original["format"]
            source = {"filename": original["filename"], "format": original["format"],
                      "content": files[PREFIX + "/inputs/original." + extension]}
            selected = {"record_index": context["record_index"],
                "geometry": files[PREFIX + "/inputs/selected-frame.xyz"],
                "receipt": files[PREFIX + "/inputs/selected-frame.json"]}
            if kind == "constructed_starting_geometry":
                construction = {"receipt": files[PREFIX + "/inputs/construction.json"]}
        expected = build_input_snapshot(submitted_config=submitted_config, source_kind=kind,
            source=source, selected_frame=selected, construction=construction)
    if snapshot != expected:
        raise LocalFilesError("Submitted context differs from its exact revalidated source bytes")
    return context


def read_member(root: Path, name: str, *, limit: int = MEMBER_LIMIT) -> bytes:
    """Apply archive confinement/caps to the shared descriptor-bound reader."""
    relative = safe_relative_path(name)
    root = checked_root(root)
    return read_file_bytes(root / relative, max_bytes=limit)


def sidecar(name: str, data: bytes) -> bytes:
    return f"{digest(data)}  {Path(name).name}\n".encode()


_ROOT_ROLES = {
    "matrix_config.validated.json": "validated-scientific-request", "ingress_alignment.json": "native-frame-provenance",
    "execution_authority.json": "recorded-execution-authority", "input.xyz": "native-input",
    "result.json": "final-electronic-result", "xtb.out": "native-output", "stderr.log": "native-diagnostics",
    "gradient": "native-gradient", "input.engrad": "native-gradient", "xtbopt.xyz": "final-geometry",
    "xtbopt.log": "optimization-trajectory", "optimization_evidence.json": "optimization-evidence",
    "optimization_evaluations.json": "optimization-history", "charges": "native-scientific-data",
    "wbo": "native-scientific-data", "energy": "native-scientific-data", "xtbrestart": "native-scientific-binary-data",
    "xtbtopo.mol": "native-topology", "process_stdout.log": "native-diagnostics", "process_stderr.log": "native-diagnostics",
}
_EVALUATION_ROLES = {key: value for key, value in _ROOT_ROLES.items() if key in {
    "input.xyz", "result.json", "xtb.out", "stderr.log", "gradient", "input.engrad", "charges", "wbo", "energy",
    "xtbrestart", "xtbtopo.mol", "process_stdout.log", "process_stderr.log"}}


def _role(name: str, evaluations: set[str], context_members: set[str]) -> str:
    if name.endswith(".sha256"):
        base = _role(name[:-7], evaluations, context_members)
        return "checksum" if base != "unknown" else "unknown"
    if name in context_members:
        return "submission-context"
    parts = name.split("/")
    if len(parts) == 1:
        return _ROOT_ROLES.get(name, "unknown")
    if len(parts) == 2 and parts[0] in evaluations:
        return _EVALUATION_ROLES.get(parts[1], "unknown")
    return "unknown"


def _write_pair(root: BoundDirectory, name: str, data: bytes) -> None:
    relative = safe_relative_path(name)
    with ExitStack() as stack:
        parent = root
        for component in relative.parts[:-1]:
            parent = stack.enter_context(parent.mkdir_child(component))
        atomic_write_bytes(parent.path, relative.name, data, expected_chain=parent.chain)
        atomic_write_bytes(parent.path, relative.name + ".sha256", sidecar(name, data), expected_chain=parent.chain)


def _read_staged(root: BoundDirectory, name: str, *, limit: int = MEMBER_LIMIT) -> tuple[bytes, int]:
    relative = safe_relative_path(name)
    with ExitStack() as stack:
        parent = root
        for component in relative.parts[:-1]:
            parent = stack.enter_context(parent.child(component))
        data = parent.read_file(relative.name, max_bytes=limit)
        mode = os.stat(relative.name, dir_fd=parent.fd, follow_symlinks=False).st_mode
        parent.verify()
        return data, mode


def finalize_publication(*, staging: Path, sandbox: Path, native_members: set[str],
                         receipt: dict, submitted_config: bytes, input_snapshot: InputSnapshot | None,
                         stage_binding: BoundDirectory, sandbox_binding: BoundDirectory) -> dict:
    """Add optional metadata to actual copied members, then the final envelope.

    The existing publisher has already generated native sidecars. Its native
    bytes/membership are preserved even when this new optional feature fails.
    """
    payload = dict(receipt)
    created_prefix = False
    try:
        if (payload.get("status") != "EXECUTION_VERIFIED" or payload.get("engine") != "xtb"
                or str(payload.get("method", "")).upper() != "GFN2-XTB"
                or payload.get("operation") not in {"single_point", "optimization"}
                or re.fullmatch(r"job_[a-f0-9]{32}", payload.get("run_id", "")) is None):
            raise LocalFilesError("Only accepted supported local GFN2 jobs can declare retained files")
        stage_binding.verify()
        try:
            os.stat(PREFIX, dir_fd=stage_binding.fd, follow_symlinks=False)
            prefix_exists = True
        except FileNotFoundError:
            prefix_exists = False
        if prefix_exists:
            raise LocalFilesError("Native output uses the reserved optional metadata path")
        snapshot = input_snapshot if input_snapshot is not None else build_input_snapshot(submitted_config=submitted_config)
        context = verified_snapshot(snapshot, submitted_config)
        if context.get("available") is not True:
            payload["retained_files"] = {"available": False, "code": context.get("code", "INPUT_SOURCE_UNVERIFIED"),
                "reason": context.get("message", "Known input provenance is unavailable")}
        else:
            expected_snapshot_files = dict(snapshot.files)
            if len(expected_snapshot_files) != len(snapshot.files):
                raise LocalFilesError("Duplicate input snapshot paths")
            context_members = {PREFIX + "/input-context.json"}
            for name, data in snapshot.files:
                if not name.startswith(PREFIX + "/inputs/") or name in ENVELOPES:
                    raise LocalFilesError("Snapshot has an unsafe producer-assigned path")
                safe_relative_path(name)
                _bounded(data, MEMBER_LIMIT)
            with stage_binding.mkdir_child(PREFIX, exist_ok=False):
                created_prefix = True
            for name, data in snapshot.files:
                _write_pair(stage_binding, name, data)
                context_members.add(name)
            _write_pair(stage_binding, PREFIX + "/input-context.json", snapshot.metadata_bytes)
            context_members |= {name + ".sha256" for name in tuple(context_members)}
            names = (set(native_members) | context_members) - ENVELOPES
            if len(names) > MEMBER_COUNT_LIMIT - 4 or len({name.casefold() for name in names}) != len(names):
                raise LocalFilesError("Retained inventory exceeds its member bound or has ambiguous names")
            evaluations = set()
            if payload["operation"] == "optimization":
                history, history_mode = _read_staged(stage_binding, "optimization_evaluations.json", limit=JSON_LIMIT)
                records = strict_json(b'{"evaluations":' + history + b'}')["evaluations"]
                if not isinstance(records, list):
                    raise LocalFilesError("Optimization history is not a measured evaluation list")
                for record in records:
                    directory = record.get("directory")
                    if not isinstance(directory, str) or re.fullmatch(r"evaluation-[0-9]{4}", directory) is None:
                        raise LocalFilesError("Optimization history has an unsafe evaluation directory")
                    evaluations.add(directory)
            files, total, reasons = {}, 0, []
            contents = {}
            for name in sorted(names):
                data, mode = _read_staged(stage_binding, name)
                contents[name] = data
                total += len(data)
                if total > TOTAL_LIMIT:
                    raise LocalFilesError("Retained files exceed the total byte limit")
                role = _role(name, evaluations, context_members)
                if role == "unknown":
                    reasons.append("Unknown retained artifact role: " + name)
                if data.startswith((b"\x7fELF", b"MZ")) or mode & 0o111:
                    reasons.append("Executable payload is not exportable: " + name)
                files[name] = {"size_bytes": len(data), "sha256": digest(data), "role": role}
            for name, data in contents.items():
                if name.endswith(".sha256"):
                    base = name[:-7]
                    if base not in contents or data != sidecar(base, contents[base]):
                        reasons.append("Published checksum relationship is inconsistent: " + name)
            inventory = {"schema_version": "cochem.local-native-inventory/1", "run_id": payload["run_id"],
                "operation": payload["operation"], "engine": "xtb", "method": payload["method"],
                "submitted_config_sha256": digest(submitted_config),
                "validated_config_sha256": files["matrix_config.validated.json"]["sha256"],
                "input_context_sha256": digest(snapshot.metadata_bytes), "scope": SCOPE,
                "excluded_scopes": list(EXCLUSIONS), "files": files,
                "export_available": not reasons, "unavailable_reasons": reasons}
            raw = _bounded(canonical_json(inventory))
            _write_pair(stage_binding, INVENTORY, raw)
            payload["retained_files"] = {"available": not reasons, "schema_version": inventory["schema_version"],
                "inventory_path": INVENTORY, "inventory_sha256": digest(raw), "scope": SCOPE,
                "excluded_scopes": list(EXCLUSIONS), "code": "UNKNOWN_OR_UNSAFE_MEMBERS" if reasons else "READY",
                "reason": "; ".join(reasons)[:400]}
    except Exception as error:
        # Deliberately narrow: only optional new metadata is contained here.
        # Normal native-copy/final-receipt/atomic-publish failures stay outside.
        payload["retained_files"] = {"available": False, "code": "RETAINED_FILES_UNAVAILABLE",
            "reason": f"{type(error).__name__}: {error}"[:400]}
        if created_prefix:
            # Partial metadata remains unclaimed; do not remove native files or
            # turn a cleanup failure into a rejected scientific calculation.
            payload["retained_files"]["partial_metadata_unclaimed"] = True
    raw = canonical_json(payload)
    atomic_write_bytes(sandbox_binding.path, "execution.json", raw, expected_chain=sandbox_binding.chain)
    _write_pair(stage_binding, "execution.json", raw)
    return payload
