"""Known local calculation records and exact-member downloads, not ZIP import.

The managed index is local bookkeeping, not a signature against an OS account
that can replace every file. Registration is only the live-completion seam;
checksums do not grant execution authority or accept uploaded calculations.
"""
from __future__ import annotations

import io
import os
import re
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from cochem_base.calc.local_publication import (
    ENVELOPES,
    EXCLUSIONS,
    INDEX_LIMIT,
    INVENTORY,
    JSON_LIMIT,
    MEMBER_COUNT_LIMIT,
    PREFIX,
    SCOPE,
    TOTAL_LIMIT,
    ZIP_LIMIT,
    LocalFilesError,
    checked_root,
    digest,
    read_member,
    sidecar,
)
from cochem_base.core.managed_files import DirectoryChain, atomic_write_bytes, open_directory_chain

from .student_request import canonical_json, safe_relative_path, strict_json

INDEX_LOCK_WAIT_SECONDS = 10.0


@dataclass(frozen=True)
class SavedLocalCalculation:
    record_id: str
    label: str
    scope: str
    exclusions: tuple[str, ...]
    available: bool = True
    notice: str = ""


@dataclass(frozen=True)
class VerifiedSavedLocalCalculation:
    record_id: str
    label: str
    results_directory: Path
    receipt_bytes: bytes
    observation_bytes: bytes
    configuration_bytes: bytes
    native_result_bytes: bytes
    input_context_bytes: bytes

    @property
    def execution_receipt(self) -> dict:
        return strict_json(self.receipt_bytes)

    @property
    def observation(self) -> dict:
        return strict_json(self.observation_bytes)

    @property
    def configuration(self) -> dict:
        return strict_json(self.configuration_bytes)

    @property
    def native_result(self) -> dict:
        return strict_json(self.native_result_bytes)

    @property
    def input_context(self) -> dict:
        return strict_json(self.input_context_bytes)


@dataclass(frozen=True)
class RetainedFilesArchive:
    content: bytes
    sha256: str
    filename: str
    member_count: int
    scope: str
    exclusions: tuple[str, ...]


def _record_id(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"job_[a-f0-9]{32}", value) is None:
        raise LocalFilesError("Choose an exact known local calculation record")
    return value


def _bind_observation_sources(observation: dict, contents: dict[str, bytes], directory: Path) -> None:
    """Bind adapter rereads to the exact earlier archive/native byte snapshot."""
    sources = observation.get("provenance_sources")
    if not isinstance(sources, list) or not sources:
        raise LocalFilesError("Completed observation lacks its exact retained provenance")
    allowed = {str(directory / name): digest(data) for name, data in contents.items()}
    for source in [observation.get("source"), *sources]:
        if (not isinstance(source, dict) or source.get("path") not in allowed
                or source.get("sha256") != allowed[source["path"]]):
            raise LocalFilesError("Completed observation provenance differs from the validated retained byte snapshot")


def _bind_record_execution(record: dict, contents: dict[str, bytes]) -> None:
    """Bind the FINAL byte snapshot, not only an earlier receipt path read."""
    if digest(contents["execution.json"]) != record["receipt_sha256"]:
        raise LocalFilesError("Saved execution envelope changed between validation phases")


def _atomic_file(directory: Path, name: str, data: bytes, *, immutable: bool = False,
                 expected_chain: DirectoryChain | None = None) -> None:
    """Domain filename confinement around shared owned descriptor mutation."""
    if len(safe_relative_path(name).parts) != 1:
        raise LocalFilesError("Managed record filename must have one component")
    atomic_write_bytes(directory, name, data, immutable=immutable, expected_chain=expected_chain)


class LocalCalculationStore:
    """A fixed app-managed root, never a student-entered download path."""

    def __init__(self, artifact_root: Path):
        self.root = checked_root(artifact_root)
        # Keep runtime/output evidence outside the source checkout, including
        # direct API clients. The context is not a caller-granted capability.
        from cochem.core.context import assert_writable_path
        from cochem_base.calc.calculation_service import REPO_ROOT
        if self.root == REPO_ROOT or self.root.is_relative_to(REPO_ROOT):
            raise LocalFilesError("Local calculation records must remain outside program source")
        assert_writable_path(self.root)
        self.directory = self.root / "LocalCalculations"
        with open_directory_chain(self.root) as root_binding:
            self._root_chain = root_binding.chain
        self._directory_chain = None
        self._records_chain = None

    def _prepare_store(self) -> None:
        with open_directory_chain(self.root, expected_chain=self._root_chain) as root_binding:
            with root_binding.mkdir_child("LocalCalculations") as directory:
                if self._directory_chain is not None and directory.chain != self._directory_chain:
                    raise LocalFilesError("Saved-calculation directory identity changed")
                self._directory_chain = directory.chain
                with directory.mkdir_child("records") as records:
                    if self._records_chain is not None and records.chain != self._records_chain:
                        raise LocalFilesError("Saved-record directory identity changed")
                    self._records_chain = records.chain

    @contextmanager
    def _index_lock(self):
        try:
            import fcntl
        except ImportError as error:
            raise LocalFilesError("Safe saved-calculation admission is unavailable on this runtime") from error
        self._prepare_store()
        with open_directory_chain(self.directory, expected_chain=self._directory_chain) as directory:
            descriptor = directory.open_file("index.lock", os.O_RDWR | os.O_CREAT)
            try:
                identity = os.fstat(descriptor)
                deadline = time.monotonic() + INDEX_LOCK_WAIT_SECONDS
                while True:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise LocalFilesError("Saved-calculation history is busy. Retry saving after the other operation finishes; this calculation remains usable") from None
                        directory.verify()
                        time.sleep(min(.05, remaining))
                directory.verify()
                current = os.stat("index.lock", dir_fd=directory.fd, follow_symlinks=False)
                if (identity.st_dev, identity.st_ino) != (current.st_dev, current.st_ino):
                    raise LocalFilesError("Saved-calculation lock changed during admission")
                yield
                directory.verify()
                current = os.stat("index.lock", dir_fd=directory.fd, follow_symlinks=False)
                if (identity.st_dev, identity.st_ino) != (current.st_dev, current.st_ino):
                    raise LocalFilesError("Saved-calculation lock changed before release")
            finally:
                # Closing this actual descriptor releases only our lock; never
                # unlink a replaced lock path or remove another owner's file.
                os.close(descriptor)

    def _index(self) -> dict:
        if not self.directory.exists() and not self.directory.is_symlink():
            return {"schema_version": "cochem.local-calculation-index/1", "records": {}, "order": []}
        checked_root(self.directory)
        target = self.directory / "index.json"
        if not target.exists() and not target.is_symlink():
            return {"schema_version": "cochem.local-calculation-index/1", "records": {}, "order": []}
        index = strict_json(read_member(self.directory, "index.json", limit=JSON_LIMIT))
        if (set(index) != {"schema_version", "records", "order"} or index["schema_version"] != "cochem.local-calculation-index/1"
                or not isinstance(index["records"], dict) or len(index["records"]) > INDEX_LIMIT
                or not isinstance(index["order"], list) or any(not isinstance(value, str) for value in index["order"])
                or len(index["order"]) != len(set(index["order"])) or set(index["order"]) != set(index["records"])):
            raise LocalFilesError("Saved-calculation index is invalid; existing calculations are unchanged")
        for identifier, entry in index["records"].items():
            _record_id(identifier)
            if (not isinstance(entry, dict) or set(entry) != {"path", "sha256"}
                    or entry["path"] != "records/" + identifier + ".json"
                    or not isinstance(entry["sha256"], str) or re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]) is None):
                raise LocalFilesError("Saved-calculation index entry is invalid")
        return index

    def _location(self, directory: Path) -> tuple[Path, str]:
        directory = checked_root(directory)
        try:
            relative = directory.relative_to(self.root).as_posix()
        except ValueError as error:
            raise LocalFilesError("Saved local results must belong to the managed artifact root") from error
        if re.fullmatch(r"GUI/run_[a-f0-9]{32}/Results", relative) is None:
            raise LocalFilesError("Only the exact managed GUI calculation directory is supported")
        return directory, relative

    def _validate_completed(self, supplied: dict, directory: Path) -> tuple[dict, dict, dict[str, bytes]]:
        directory, relative = self._location(directory)
        raw = read_member(directory, "execution.json", limit=JSON_LIMIT)
        receipt = strict_json(raw)
        if canonical_json(receipt) != canonical_json(supplied):
            raise LocalFilesError("Actual completion receipt differs from its published native envelope")
        if (receipt.get("status") != "EXECUTION_VERIFIED" or receipt.get("dry_run") is not False
                or receipt.get("engine") != "xtb" or str(receipt.get("method", "")).upper() != "GFN2-XTB"
                or receipt.get("operation") not in {"single_point", "optimization"}
                or receipt.get("output_dir") != str(directory)
                or receipt.get("config_file") != str(directory.parent / "matrix_config.json")):
            raise LocalFilesError("Retained files require the exact supported local completion")
        _record_id(receipt.get("run_id"))
        metadata = receipt.get("retained_files")
        if (not isinstance(metadata, dict) or metadata.get("available") is not True
                or metadata.get("inventory_path") != INVENTORY
                or metadata.get("schema_version") != "cochem.local-native-inventory/1"
                or metadata.get("scope") != SCOPE or metadata.get("excluded_scopes") != list(EXCLUSIONS)):
            reason = metadata.get("reason", "No producer-bound retained-file inventory") if isinstance(metadata, dict) else "No producer-bound retained-file inventory"
            raise LocalFilesError("Retained-file export/history unavailable: " + str(reason))
        inventory_raw = read_member(directory, INVENTORY, limit=JSON_LIMIT)
        if digest(inventory_raw) != metadata.get("inventory_sha256"):
            raise LocalFilesError("Published native inventory hash changed")
        inventory = strict_json(inventory_raw)
        fields = {"schema_version", "run_id", "operation", "engine", "method", "submitted_config_sha256",
            "validated_config_sha256", "input_context_sha256", "scope", "excluded_scopes", "files",
            "export_available", "unavailable_reasons"}
        if (set(inventory) != fields or inventory["schema_version"] != metadata["schema_version"]
                or any(inventory[key] != receipt[key] for key in ("run_id", "operation", "engine", "method"))
                or inventory["scope"] != SCOPE or inventory["excluded_scopes"] != list(EXCLUSIONS)
                or inventory["export_available"] is not True or inventory["unavailable_reasons"] != []
                or not isinstance(inventory["files"], dict) or not 1 <= len(inventory["files"]) <= MEMBER_COUNT_LIMIT - 4):
            raise LocalFilesError("Native inventory does not describe this actual supported publication")
        names = set(inventory["files"])
        if names & ENVELOPES or len({name.casefold() for name in names}) != len(names):
            raise LocalFilesError("Native inventory has recursive or ambiguous members")
        contents, total = {}, 0
        for name, identity in inventory["files"].items():
            safe_relative_path(name)
            if (not isinstance(identity, dict) or set(identity) != {"size_bytes", "sha256", "role"}
                    or type(identity["size_bytes"]) is not int or identity["role"] == "unknown"):
                raise LocalFilesError("Native inventory has an unsupported member identity or role")
            data = read_member(directory, name)
            total += len(data)
            if total > TOTAL_LIMIT or identity["size_bytes"] != len(data) or identity["sha256"] != digest(data):
                raise LocalFilesError("Native inventory member size/hash changed")
            contents[name] = data
        for name in ENVELOPES:
            contents[name] = read_member(directory, name, limit=JSON_LIMIT)
        for name, data in contents.items():
            if name.endswith(".sha256") and (name[:-7] not in contents or data != sidecar(name[:-7], contents[name[:-7]])):
                raise LocalFilesError("Published checksum/envelope relationship changed")
        context_name = PREFIX + "/input-context.json"
        submitted_name = PREFIX + "/inputs/submitted-config.json"
        if (digest(contents[context_name]) != inventory["input_context_sha256"]
                or digest(contents[submitted_name]) != inventory["submitted_config_sha256"]
                or digest(contents["matrix_config.validated.json"]) != inventory["validated_config_sha256"]):
            raise LocalFilesError("Actual submission/context bindings differ from the native inventory")
        context = strict_json(contents[context_name])
        if context.get("available") is not True or context.get("submitted_config_sha256") != inventory["submitted_config_sha256"]:
            raise LocalFilesError("Known original/source context is unavailable")
        from cochem_base.interfaces.student_reports import (
            observation_from_completed_local_calculation,
        )
        observation = observation_from_completed_local_calculation(receipt, results_directory=directory)
        _bind_observation_sources(observation, contents, directory)
        if observation["energy_hartree"] != strict_json(contents["result.json"])["energy_hartree"]:
            raise LocalFilesError("Completed observation energy differs from the validated retained result bytes")
        if observation["minimum_verified"] is not False:
            raise LocalFilesError("Retained electronic results cannot acquire minimum qualification")
        return inventory, observation, contents

    def _read_record(self, identifier: str, entry: dict, ordinal: int) -> tuple[dict, bytes]:
        raw = read_member(self.directory, entry["path"], limit=JSON_LIMIT)
        if digest(raw) != entry["sha256"]:
            raise LocalFilesError("Saved local record checksum changed")
        record = strict_json(raw)
        if (set(record) != {"schema_version", "record_id", "results_relative", "receipt_sha256", "inventory_sha256",
                            "input_context_sha256", "label", "scope", "exclusions"}
                or record["schema_version"] != "cochem.saved-local-calculation/1" or record["record_id"] != identifier
                or record["scope"] != SCOPE or not isinstance(record["exclusions"], list)
                or any(not isinstance(value, str) for value in record["exclusions"])
                or record["exclusions"][:len(EXCLUSIONS)] != list(EXCLUSIONS)
                or not isinstance(record["results_relative"], str)
                or re.fullmatch(r"GUI/run_[a-f0-9]{32}/Results", record["results_relative"]) is None
                or any(not isinstance(record[field], str) or re.fullmatch(r"[a-f0-9]{64}", record[field]) is None
                       for field in ("receipt_sha256", "inventory_sha256", "input_context_sha256"))
                or not isinstance(record["label"], str)
                or record["label"] not in {
                    f"Saved calculation {ordinal} · GFN2-xTB · Energy at supplied geometry",
                    f"Saved calculation {ordinal} · GFN2-xTB · Geometry optimization"}):
            raise LocalFilesError("Saved local record identity is invalid")
        return record, raw

    @staticmethod
    def _summary(record: dict) -> SavedLocalCalculation:
        return SavedLocalCalculation(record["record_id"], record["label"], record["scope"], tuple(record["exclusions"]))

    def register_completed(self, execution_receipt: dict, *, results_directory: Path) -> SavedLocalCalculation:
        """Only the validated actual live completion, never import-by-directory."""
        directory, relative = self._location(results_directory)
        inventory, observation, contents = self._validate_completed(execution_receipt, directory)
        identifier = _record_id(execution_receipt["run_id"])
        context = strict_json(contents[PREFIX + "/input-context.json"])
        exclusions = list(EXCLUSIONS) + list(context.get("exclusions", []))
        record = {"schema_version": "cochem.saved-local-calculation/1", "record_id": identifier,
            "results_relative": relative, "receipt_sha256": digest(contents["execution.json"]),
            "inventory_sha256": digest(contents[INVENTORY]), "input_context_sha256": inventory["input_context_sha256"],
            "scope": SCOPE, "exclusions": exclusions}
        with self._index_lock():
            index = self._index()
            if identifier in index["records"]:
                ordinal = index["order"].index(identifier) + 1
                previous, previous_raw = self._read_record(identifier, index["records"][identifier], ordinal)
                record["label"] = previous["label"]
                raw = canonical_json(record)
                if previous_raw != raw:
                    raise LocalFilesError("Saved run identity is already bound to different evidence")
                return self._summary(previous)
            if len(index["records"]) >= INDEX_LIMIT:
                raise LocalFilesError("Saved-calculation history is full (256 records); no records were evicted and this calculation remains usable")
            task = "Energy at supplied geometry" if execution_receipt["operation"] == "single_point" else "Geometry optimization"
            record["label"] = f"Saved calculation {len(index['records']) + 1} · GFN2-xTB · {task}"
            raw = canonical_json(record)
            path = "records/" + identifier + ".json"
            orphan = self.directory / path
            if orphan.exists() or orphan.is_symlink():
                if read_member(self.directory, path, limit=JSON_LIMIT) != raw:
                    raise LocalFilesError("An unindexed record is not the same explicitly revalidated live completion")
            else:
                _atomic_file(self.directory / "records", identifier + ".json", raw, immutable=True, expected_chain=self._records_chain)
            index["records"][identifier] = {"path": path, "sha256": digest(raw)}
            index["order"].append(identifier)
            _atomic_file(self.directory, "index.json", canonical_json(index), expected_chain=self._directory_chain)
        return self._summary(record)

    def list_saved(self) -> tuple[SavedLocalCalculation, ...]:
        index = self._index()
        summaries = []
        for ordinal, identifier in enumerate(index["order"], 1):
            entry = index["records"][identifier]
            try:
                record, raw = self._read_record(identifier, entry, ordinal)
                summaries.append(self._summary(record))
            except (ValueError, OSError, KeyError) as error:
                summaries.append(SavedLocalCalculation(identifier, f"Saved calculation {ordinal} — unavailable",
                    SCOPE, EXCLUSIONS, available=False, notice=identifier + ": " + str(error)))
        return tuple(summaries)

    def _known(self, identifier: str) -> tuple[dict, bytes, dict, dict[str, bytes], Path]:
        identifier = _record_id(identifier)
        index = self._index()
        if identifier not in index["records"]:
            raise LocalFilesError("This calculation is not a registered local record; arbitrary files/ZIPs cannot be reopened as executed")
        record, raw = self._read_record(identifier, index["records"][identifier], index["order"].index(identifier) + 1)
        directory, relative = self._location(self.root / safe_relative_path(record["results_relative"]))
        receipt_raw = read_member(directory, "execution.json", limit=JSON_LIMIT)
        if digest(receipt_raw) != record["receipt_sha256"]:
            raise LocalFilesError("Saved execution receipt changed")
        receipt = strict_json(receipt_raw)
        inventory, observation, contents = self._validate_completed(receipt, directory)
        _bind_record_execution(record, contents)
        context = strict_json(contents[PREFIX + "/input-context.json"])
        task = "Energy at supplied geometry" if receipt["operation"] == "single_point" else "Geometry optimization"
        ordinal = index["order"].index(identifier) + 1
        if (record["exclusions"] != list(EXCLUSIONS) + list(context.get("exclusions", []))
                or record["label"] != f"Saved calculation {ordinal} · GFN2-xTB · {task}"):
            raise LocalFilesError("Saved label or file scope differs from its actual recorded operation/context")
        if (receipt["run_id"] != identifier or digest(contents[INVENTORY]) != record["inventory_sha256"]
                or inventory["input_context_sha256"] != record["input_context_sha256"]):
            raise LocalFilesError("Saved record and publication identities disagree")
        return record, raw, observation, contents, directory

    def reopen_saved(self, record_id: str) -> VerifiedSavedLocalCalculation:
        record, raw, observation, contents, directory = self._known(record_id)
        return VerifiedSavedLocalCalculation(record_id, record["label"], directory, contents["execution.json"], canonical_json(observation),
            contents["matrix_config.validated.json"], contents["result.json"], contents[PREFIX + "/input-context.json"])

    def retained_files_zip(self, record_id: str) -> RetainedFilesArchive:
        record, raw, observation, contents, directory = self._known(record_id)
        members = {"native/" + name: data for name, data in contents.items()}
        members["saved-local-record.json"] = raw
        if len(members) + 1 > MEMBER_COUNT_LIMIT or sum(map(len, members.values())) > TOTAL_LIMIT:
            raise LocalFilesError("Retained-file archive exceeds its bounded transport inventory; native files remain unchanged")
        manifest = {"schema_version": "cochem.retained-local-files/1", "record_id": record_id,
            "scope": SCOPE, "excluded_scopes": record["exclusions"],
            "execution_sha256": record["receipt_sha256"], "inventory_sha256": record["inventory_sha256"],
            "files": {name: {"size_bytes": len(data), "sha256": digest(data)} for name, data in members.items()}}
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
            package.writestr("manifest.json", canonical_json(manifest))
            for name, data in sorted(members.items()):
                safe_relative_path(name)
                info = zipfile.ZipInfo(name)
                info.external_attr = 0o100600 << 16
                package.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
                if archive.tell() > ZIP_LIMIT:
                    raise LocalFilesError("Retained-file ZIP exceeds the 32 MiB browser bound; no native files were dropped")
        data = archive.getvalue()
        if len(data) > ZIP_LIMIT:
            raise LocalFilesError("Retained-file ZIP exceeds the 32 MiB browser bound")
        return RetainedFilesArchive(data, digest(data), "cochem-retained-" + record_id + ".zip", len(members) + 1,
            SCOPE, tuple(record["exclusions"]))
