"""Incrementally publish complete, measured external-engine XYZ frames.

Native xTB ``xtbopt.log`` and ORCA ``*_trj.xyz`` protocol energies are Hartree
and coordinates are Angstrom. Generic/extxyz input requires an explicit energy
unit in its comment or in the caller's configuration. No missing energy,
gradient, convergence decision, or simulation time is synthesized.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import os
import re
from pathlib import Path
import threading
from typing import Any, Callable, Sequence

import numpy as np
from scipy.constants import physical_constants

from cochem_base.core_engine.scientific_telemetry import append_scientific_result, read_scientific_results


class TrajectoryFormatError(ValueError):
    """A complete source frame violates the declared scientific data format."""


class IncompleteTrajectoryError(TrajectoryFormatError):
    """The producer stopped with an unfinished XYZ frame."""


_ENERGY = re.compile(r"(?:^|\s)(?:energy|E)\s*(?::|=|\s)\s*(\S+)", re.IGNORECASE)
_EV_PER_HARTREE = physical_constants["Hartree energy in eV"][0]


def _field(comment: str, name: str) -> str | None:
    match = re.search(r"(?:^|\s)" + name + r'''\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+))''', comment, re.IGNORECASE)
    return next((item for item in match.groups() if item is not None), None) if match else None


def _energy_unit(value: str) -> str:
    normalized = value.strip().lower().rstrip(".,;")
    if normalized in {"eh", "ha", "hartree", "hartrees", "au", "a.u"}:
        return "hartree"
    if normalized == "ev":
        return "eV"
    raise TrajectoryFormatError(f"Unsupported or ambiguous energy unit: {value!r}")


@dataclass(frozen=True)
class XYZTrajectoryFrame:
    elements: tuple[str, ...]
    coordinates_angstrom: np.ndarray
    energy_hartree: float
    source_energy: float
    source_energy_unit: str
    unit_authority: str
    comment: str


def parse_xyz_frame(
    data: bytes | str, *, elements: Sequence[str], source_format: str,
    energy_unit: str | None = None,
) -> XYZTrajectoryFrame:
    """Parse one complete frame; the format name is a declaration, not detection."""
    if source_format not in {"xtb", "orca", "extxyz"}:
        raise ValueError("source_format must be xtb, orca, or extxyz")
    try:
        lines = (data.decode("utf-8", errors="strict") if isinstance(data, bytes) else data).splitlines()
        count = int(lines[0].strip())
    except (UnicodeError, ValueError, IndexError) as error:
        raise TrajectoryFormatError("XYZ atom count or UTF-8 encoding is invalid") from error
    expected = tuple(elements)
    if count != len(expected) or count < 1 or len(lines) != count + 2:
        raise TrajectoryFormatError("XYZ frame size must match the declared atom identities")
    comment = lines[1]
    match = _ENERGY.search(comment)
    if not match:
        raise TrajectoryFormatError("XYZ frame contains no explicitly labeled measured energy")
    try:
        source_energy = float(match.group(1).strip('"\'').replace("D", "E").replace("d", "e"))
    except ValueError as error:
        raise TrajectoryFormatError("XYZ energy is not a complete numeric value") from error
    if not np.isfinite(source_energy):
        raise TrajectoryFormatError("XYZ energy must be finite")

    declared = _field(comment, r"energy_units?")
    # Also accept a unit immediately following the labeled scalar, e.g. E=-1 Eh.
    suffix = comment[match.end():].strip().split()
    if declared is None and suffix:
        candidate = suffix[0]
        if candidate.lower().rstrip(".,;") in {"eh", "ha", "hartree", "hartrees", "au", "a.u", "ev"}:
            declared = candidate
    explicit = _energy_unit(energy_unit) if energy_unit is not None else None
    comment_unit = _energy_unit(declared) if declared is not None else None
    if explicit and comment_unit and explicit != comment_unit:
        raise TrajectoryFormatError("Caller and trajectory comment disagree about energy units")
    if source_format in {"xtb", "orca"}:
        signature = (re.search(r"\bxtb\s*:", comment, re.IGNORECASE) if source_format == "xtb"
                     else re.search(r"\bORCA(?:-job)?\b", comment, re.IGNORECASE))
        if (comment_unit or explicit) not in {None, "hartree"}:
            raise TrajectoryFormatError("Native xTB/ORCA trajectory energy must be Hartree")
        if not signature and not (comment_unit or explicit):
            raise TrajectoryFormatError("Missing native engine signature or explicit Hartree unit")
        unit = "hartree"
        authority = "comment" if comment_unit else "caller" if explicit else f"{source_format}_native_protocol"
    else:
        unit = comment_unit or explicit
        if unit is None:
            raise TrajectoryFormatError("Generic XYZ energy requires explicit energy_unit=Hartree or energy_unit=eV")
        authority = "comment" if comment_unit else "caller"
    length_unit = _field(comment, r"(?:coordinates?|positions?|length)_units?")
    if length_unit is not None and length_unit.strip().lower() not in {"angstrom", "angstroms", "a", "å"}:
        raise TrajectoryFormatError("XYZ coordinates must explicitly be in Angstrom when a length unit is declared")

    species_column, position_columns, columns = 0, (1, 2, 3), 4
    properties = _field(comment, "Properties")
    if properties is not None:
        fields = properties.split(":")
        if len(fields) % 3:
            raise TrajectoryFormatError("Invalid extxyz Properties descriptor")
        species_column, position_columns, columns = None, None, 0
        try:
            for start in range(0, len(fields), 3):
                name, kind, width_text = fields[start:start + 3]
                width = int(width_text)
                if width < 1:
                    raise ValueError("Property width must be positive")
                if name in {"species", "element"}:
                    if kind != "S" or width != 1 or species_column is not None:
                        raise ValueError("Invalid or repeated species property")
                    species_column = columns
                elif name in {"pos", "positions"}:
                    if kind != "R" or width != 3 or position_columns is not None:
                        raise ValueError("Invalid or repeated position property")
                    position_columns = tuple(range(columns, columns + 3))
                columns += width
        except ValueError as error:
            raise TrajectoryFormatError("Invalid extxyz Properties schema") from error
        if species_column is None or position_columns is None:
            raise TrajectoryFormatError("extxyz Properties must identify species and Cartesian positions")
    observed, coordinates = [], []
    for line in lines[2:]:
        values = line.split()
        if len(values) != columns:
            raise TrajectoryFormatError("XYZ coordinate row has an incorrect number of columns")
        observed.append(values[species_column])
        try:
            coordinates.append([float(values[index].replace("D", "E").replace("d", "e")) for index in position_columns])
        except ValueError as error:
            raise TrajectoryFormatError("XYZ coordinates must be numeric") from error
    array = np.asarray(coordinates, dtype=np.float64)
    if tuple(observed) != expected:
        raise TrajectoryFormatError("XYZ atom identities/order changed")
    if not np.all(np.isfinite(array)):
        raise TrajectoryFormatError("XYZ coordinates must be finite")
    converted = source_energy / _EV_PER_HARTREE if unit == "eV" else source_energy
    return XYZTrajectoryFrame(expected, array, converted, source_energy, unit, authority, comment)


class XYZTrajectoryFollower:
    """Follow a growing XYZ file while an external engine runs.

    ``poll_once`` is also usable without a thread. The context manager starts a
    single publisher and drains on exit. ``error_event`` and ``on_error`` allow
    a process broker to cancel promptly. An existing engine exception is never
    replaced by a telemetry exception; the latter remains in ``status``.
    """

    def __init__(
        self, path: str | Path, job_id: str, elements: Sequence[str], *,
        source_format: str, store_path: str | Path | None = None,
        energy_unit: str | None = None, metadata: dict[str, Any] | None = None,
        source_id: str | None = None, poll_interval: float = 0.1,
        on_error: Callable[[BaseException], None] | None = None,
        required: bool = False, strict_final: bool = True,
        join_timeout: float = 15.0, max_pending_bytes: int = 32 * 1024 * 1024,
    ) -> None:
        if source_format not in {"xtb", "orca", "extxyz"}:
            raise ValueError("source_format must be xtb, orca, or extxyz")
        if not elements or poll_interval <= 0 or join_timeout <= 0 or max_pending_bytes < 1:
            raise ValueError("Follower requires atoms and positive polling/resource bounds")
        self.path = Path(path).resolve()
        self.job_id, self.elements = job_id, tuple(elements)
        self.source_format, self.store_path = source_format, store_path
        self.energy_unit = energy_unit
        self.metadata = dict(metadata or {})
        self.source_id = source_id or str(self.path)
        self.poll_interval, self.join_timeout = float(poll_interval), float(join_timeout)
        self.on_error, self.required, self.strict_final = on_error, required, strict_final
        self.max_pending_bytes = int(max_pending_bytes)
        self.error_event = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._poll_lock, self._status_lock = threading.Lock(), threading.Lock()
        self._error: BaseException | None = None
        self._status: dict[str, Any] = {
            "state": "created", "source_path": str(self.path), "source_format": source_format,
            "source_id": self.source_id, "frames_seen": 0, "frames_published": 0,
            "duplicates_skipped": 0, "pending_bytes": 0, "file_generations": 0,
            "source_found": False, "error": None, "callback_error": None,
        }
        self._buffer, self._offset, self._buffer_offset = b"", 0, 0
        self._identity: tuple[int, int] | None = None
        self._last_mtime_ns: int | None = None
        self._last_size: int | None = None
        self._prefix, self._last_window = b"", b""
        self._frame_index = 0
        self._occurrences: Counter[str] = Counter()
        self._seen: set[tuple[str, int]] = set()
        self._resume_loaded = False

    @property
    def status(self) -> dict[str, Any]:
        with self._status_lock:
            return dict(self._status)

    def _update(self, **values: Any) -> None:
        with self._status_lock:
            self._status.update(values)

    def _record_error(self, error: BaseException) -> None:
        if self._error is not None:
            return
        self._error = error
        self._update(state="error", error=f"{type(error).__name__}: {error}", pending_bytes=len(self._buffer), source_byte_offset=self._buffer_offset)
        self.error_event.set()
        if self.on_error is not None:
            try:
                self.on_error(error)
            except BaseException as callback_error:
                self._update(callback_error=f"{type(callback_error).__name__}: {callback_error}")

    def _load_resume_records(self) -> None:
        if self._resume_loaded:
            return
        try:
            existing = read_scientific_results(self.job_id, store_path=self.store_path)
        except FileNotFoundError:
            existing = {"metadata": []}
        except KeyError:
            # An absent job is normal; missing datasets in an existing job
            # are archive corruption and must not reset deduplication state.
            from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager

            manager = CoChemHDF5Manager(h5_path=self.store_path)
            with manager.swmr_reader() as reader:
                if f"trajectories/{self.job_id}" in reader:
                    raise
            existing = {"metadata": []}
        for record in existing["metadata"]:
            source = record.get("trajectory_source", {})
            if source.get("source_id") == self.source_id and source.get("format") == self.source_format:
                digest, occurrence = source.get("frame_sha256"), source.get("frame_occurrence")
                if isinstance(digest, str) and isinstance(occurrence, int):
                    self._seen.add((digest, occurrence))
        self._resume_loaded = True

    def _read_appended(self) -> None:
        try:
            stream = self.path.open("rb")
        except FileNotFoundError:
            return
        with stream:
            stat = os.fstat(stream.fileno())
            identity = (stat.st_dev, stat.st_ino)
            changed = self._identity is not None and (identity != self._identity or stat.st_size < self._offset)
            if self._last_mtime_ns is not None and stat.st_mtime_ns != self._last_mtime_ns and stat.st_size == self._last_size:
                changed = True
            if not changed and self._prefix:
                changed = stream.read(len(self._prefix)) != self._prefix
            if not changed and self._last_window and stat.st_size >= self._offset:
                stream.seek(self._offset - len(self._last_window))
                changed = stream.read(len(self._last_window)) != self._last_window
            if self._identity is None or changed:
                self._buffer, self._offset, self._buffer_offset = b"", 0, 0
                self._frame_index = 0
                self._occurrences.clear()
                self._update(file_generations=self.status["file_generations"] + 1)
            self._identity = identity
            self._last_mtime_ns, self._last_size = stat.st_mtime_ns, stat.st_size
            stream.seek(self._offset)
            chunk = stream.read(self.max_pending_bytes + 1)
            self._offset += len(chunk)
            self._buffer += chunk
            stream.seek(0)
            self._prefix = stream.read(min(256, self._offset))
            stream.seek(max(0, self._offset - 256))
            self._last_window = stream.read(min(256, self._offset))
        self._update(source_found=True)

    def _publish_complete_frames(self) -> int:
        published = 0
        while self._buffer:
            first_end = self._buffer.find(b"\n")
            if first_end < 0:
                break
            header = self._buffer[:first_end].strip()
            if not header:
                self._buffer = self._buffer[first_end + 1:]
                self._buffer_offset += first_end + 1
                continue
            try:
                count = int(header)
            except ValueError as error:
                raise TrajectoryFormatError("Invalid incremental XYZ atom-count line") from error
            if count != len(self.elements):
                raise TrajectoryFormatError("Incremental XYZ atom count changed")
            end = first_end
            for _ in range(count + 1):
                end = self._buffer.find(b"\n", end + 1)
                if end < 0:
                    break
            if end < 0:
                break
            raw = self._buffer[:end + 1]
            frame = parse_xyz_frame(raw, elements=self.elements, source_format=self.source_format, energy_unit=self.energy_unit)
            digest = hashlib.sha256(raw).hexdigest()
            occurrence = self._occurrences[digest] + 1
            token = (digest, occurrence)
            if token not in self._seen:
                provenance = dict(self.metadata)
                provenance["trajectory_source"] = {
                    "source_id": self.source_id, "path": str(self.path), "format": self.source_format,
                    "frame_index": self._frame_index, "byte_offset": self._buffer_offset,
                    "file_generation": self.status["file_generations"],
                    "frame_sha256": digest, "frame_occurrence": occurrence,
                    "source_energy": frame.source_energy, "source_energy_unit": frame.source_energy_unit,
                    "energy_unit_authority": frame.unit_authority, "coordinates_unit": "angstrom",
                    "comment": frame.comment, "record_kind": "measured_optimization_trajectory_frame",
                    "convergence_status": "not_reported_by_xyz", "gradient_status": "not_available_from_xyz",
                }
                archive = append_scientific_result(
                    self.job_id, frame.elements, frame.coordinates_angstrom, frame.energy_hartree,
                    metadata=provenance, store_path=self.store_path,
                )
                self._seen.add(token)
                published += 1
                self._update(frames_published=self.status["frames_published"] + 1, archive_path=str(archive))
            else:
                self._update(duplicates_skipped=self.status["duplicates_skipped"] + 1)
            self._occurrences[digest] = occurrence
            self._frame_index += 1
            self._buffer = self._buffer[end + 1:]
            self._buffer_offset += end + 1
            self._update(frames_seen=self.status["frames_seen"] + 1)
        if len(self._buffer) > self.max_pending_bytes:
            raise TrajectoryFormatError("Incomplete XYZ frame exceeds the pending-buffer limit")
        self._update(pending_bytes=len(self._buffer))
        return published

    def poll_once(self) -> int:
        """Publish newly complete frames once, raising parser/publication errors."""
        with self._poll_lock:
            if self._error is not None:
                raise self._error
            try:
                self._load_resume_records()
                self._read_appended()
                return self._publish_complete_frames()
            except BaseException as error:
                self._record_error(error)
                raise

    def _finish(self) -> None:
        self.poll_once()
        # A large pre-existing trajectory can exceed one bounded read. Drain
        # all remaining source bytes after the producer has stopped.
        while self.path.is_file() and self._offset < self.path.stat().st_size:
            previous_offset = self._offset
            self.poll_once()
            if self._offset == previous_offset:
                break
        if self.required and not self.status["source_found"]:
            raise FileNotFoundError(f"Required engine trajectory was not produced: {self.path}")
        if self._buffer.strip() and self.strict_final:
            raise IncompleteTrajectoryError(f"Producer stopped with {len(self._buffer)} unfinished XYZ bytes")
        self._update(state="stopped_incomplete" if self._buffer.strip() else "stopped" if self.status["source_found"] else "missing")

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self.poll_once()
                self._stop.wait(self.poll_interval)
            self._finish()
        except BaseException as error:
            self._record_error(error)

    def start(self) -> XYZTrajectoryFollower:
        if self._thread is not None:
            raise RuntimeError("A trajectory follower can only be started once")
        self._update(state="following")
        self._thread = threading.Thread(target=self._run, name=f"trajectory-{self.job_id}", daemon=True)
        self._thread.start()
        return self

    def stop(self, *, raise_errors: bool = True) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(self.join_timeout)
            if self._thread.is_alive():
                self._record_error(TimeoutError("Trajectory publisher did not stop within its bounded join timeout"))
        elif self._error is None:
            try:
                self._finish()
            except BaseException as error:
                self._record_error(error)
        if raise_errors and self._error is not None:
            raise self._error
        return self.status

    def __enter__(self) -> XYZTrajectoryFollower:
        return self.start()

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        self.stop(raise_errors=exc_type is None)
        if exc_value is not None and self._error is not None and hasattr(exc_value, "add_note"):
            exc_value.add_note(f"Trajectory telemetry also failed: {self.status['error']}")
        return False
