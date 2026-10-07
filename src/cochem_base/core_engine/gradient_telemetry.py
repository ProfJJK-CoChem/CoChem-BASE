"""Publish complete native ORCA gradient observations while stdout is growing.

ORCA's Cartesian-gradient protocol reports Eh/bohr in the axes of its immediately
preceding Cartesian coordinates. Printed precision is recorded, not promoted to
checkpoint precision. XYZ positions and gradient norms never become gradients.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Callable, Sequence

import numpy as np
from scipy.constants import physical_constants

from cochem_base.core_engine.scientific_telemetry import append_scientific_result
from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity
from cochem_base.physics.nuclide_resolver import get_element

BOHR_ANGSTROM = physical_constants["Bohr radius"][0] * 1e10


class GradientStreamError(ValueError):
    """A complete native observation cannot be associated with its geometry."""


def _number(value: str) -> float:
    number = float(value.replace("D", "E").replace("d", "e"))
    if not np.isfinite(number):
        raise GradientStreamError("Native geometry, energy and gradient must be finite")
    return number


class ORCAGradientStream:
    """Callable line observer; each published row binds native geometry and energy.

    ``nuclides`` carries submitted isotope identities into the canonical archive;
    ``elements`` validates the electronic identities printed by the engine. Raw
    selected sections are retained as a UTF-8/LF transcript, with independent
    section hashes and exact transcript byte offsets for each observation.
    """

    def __init__(self, job_id: str, elements: Sequence[str], *,
                 nuclides: Sequence[str] | None = None, store_path: str | Path | None = None,
                 metadata: dict[str, Any] | None = None, source_id: str,
                 source_path: str | Path | None = None,
                 on_record: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.job_id, self.elements = job_id, tuple(elements)
        identity = resolve_nuclear_identity(nuclides if nuclides is not None else self.elements)
        self.nuclides = identity.nuclides
        if not self.elements or len(self.nuclides) != len(self.elements):
            raise ValueError("Gradient stream requires matching electronic and isotope identities")
        if identity.elements != self.elements:
            raise ValueError("Gradient stream isotope labels must match the electronic elements")
        self.store_path, self.metadata = store_path, dict(metadata or {})
        self.source_id, self.source_path = source_id, Path(source_path) if source_path is not None else None
        if self.source_path is not None:
            self.source_path.parent.mkdir(parents=True, exist_ok=True)
            self.source_path.write_bytes(b"")
        self.on_record = on_record
        self.records: list[dict[str, Any]] = []
        self._state: str | None = None
        self._geometry_rows: list[list[float]] = []
        self._gradient_rows: list[list[float]] = []
        self._geometry_source, self._energy_source, self._gradient_source = [], [], []
        self._geometry: np.ndarray | None = None
        self._energy: float | None = None
        self._transcript_offset = 0
        self._finished = False

    @property
    def status(self) -> dict[str, Any]:
        return {"state": "stopped" if self._finished else "following",
                "gradient_records_published": len(self.records), "source_id": self.source_id,
                "source_path": str(self.source_path) if self.source_path else None}

    def __call__(self, line: str) -> None:
        text = line.rstrip("\r\n")
        if text.strip() == "CARTESIAN COORDINATES (A.U.)":
            if self._state == "gradient" and self._gradient_rows:
                raise GradientStreamError("ORCA replaced an incomplete Cartesian gradient")
            self._state, self._geometry_rows = "geometry", []
            self._geometry_source = [text]
            self._geometry, self._energy = None, None
            return
        if self._state == "geometry":
            self._geometry_source.append(text)
            fields = text.split()
            if fields and re.fullmatch(r"\d+", fields[0]):
                i = len(self._geometry_rows)
                if (len(fields) != 8 or i >= len(self.elements) or int(fields[0]) != i
                        or fields[1] != self.elements[i]
                        or _number(fields[2]) != int(get_element(self.elements[i]).atomic_number)):
                    raise GradientStreamError("ORCA geometry atom identities/order changed")
                self._geometry_rows.append([_number(v) for v in fields[-3:]])
                if len(self._geometry_rows) == len(self.elements):
                    self._geometry = np.asarray(self._geometry_rows) * BOHR_ANGSTROM
                    self._state = None
            elif self._geometry_rows:
                raise GradientStreamError("ORCA Cartesian geometry is incomplete")
            return
        energy = re.match(r"^\s*FINAL SINGLE POINT ENERGY\s+(\S+)\s*$", text)
        if energy is not None:
            self._energy, self._energy_source = _number(energy[1]), [text]
            return
        if text.strip() == "CARTESIAN GRADIENT":
            if self._geometry is None or self._energy is None:
                raise GradientStreamError("ORCA gradient requires its own preceding geometry and energy")
            self._state, self._gradient_rows = "gradient", []
            self._gradient_source = [text]
            return
        if self._state == "gradient":
            self._gradient_source.append(text)
            match = re.fullmatch(r"\s*(\d+)\s+(\S+)\s*:\s*(\S+)\s+(\S+)\s+(\S+)\s*", text)
            if match is not None:
                i = len(self._gradient_rows)
                if i >= len(self.elements) or int(match[1]) != i + 1 or match[2] != self.elements[i]:
                    raise GradientStreamError("ORCA Cartesian gradient atom identities/order changed")
                self._gradient_rows.append([_number(v) for v in match.groups()[2:]])
                if len(self._gradient_rows) == len(self.elements):
                    self._publish()
                    self._state = None
                    # A second gradient must supply its own complete geometry
                    # and energy; a stale preceding observation is not evidence.
                    self._geometry, self._energy = None, None
            elif self._gradient_rows:
                raise GradientStreamError("ORCA Cartesian gradient is incomplete")

    def _publish(self) -> None:
        sections = {name: ("\n".join(lines) + "\n").encode("utf-8") for name, lines in (
            ("coordinates", self._geometry_source), ("energy", self._energy_source),
            ("gradient", self._gradient_source))}
        raw = b"".join(sections.values())
        if self.source_path is not None:
            with self.source_path.open("ab") as output:
                output.write(raw)
                output.flush()
        gradients = np.asarray(self._gradient_rows)
        record = {"energy_hartree": self._energy, "coordinates_angstrom": self._geometry.tolist(),
                  "gradients_hartree_per_bohr": gradients.tolist(),
                  "max_gradient": float(np.max(np.abs(gradients))),
                  "rms_gradient": float(np.sqrt(np.mean(gradients**2))),
                  "evaluation_index": len(self.records)}
        source = {"source_id": self.source_id, "path": str(self.source_path) if self.source_path else None,
                  "format": "orca_stdout_cartesian_gradient", "record_kind": "measured_optimization_gradient_evaluation",
                  "evaluation_index": len(self.records), "record_sha256": hashlib.sha256(raw).hexdigest(),
                  "section_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sections.items()},
                  "byte_offset": self._transcript_offset, "byte_length": len(raw),
                  "source_serialization": "Selected complete stdout sections, UTF-8 with LF line endings",
                  "coordinates_unit": "bohr", "coordinates_print_resolution_bohr": 1e-6,
                  "gradient_unit": "hartree/bohr", "gradient_print_resolution_hartree_per_bohr": 1e-9,
                  "unit_authority": "ORCA native Cartesian-gradient protocol", "axes": "native Cartesian coordinates",
                  "native_to_record_rotation": np.eye(3).tolist(), "electronic_elements": list(self.elements),
                  "nuclides": list(self.nuclides), "convergence_status": "not_inferred_from_gradient"}
        for key in ("source_artifact_relative_path", "published_source_path"):
            if key in self.metadata:
                source[key] = self.metadata[key]
        archive = append_scientific_result(self.job_id, self.nuclides, self._geometry, self._energy,
            gradients=gradients, metadata={**self.metadata, "gradient_source": source}, store_path=self.store_path)
        record.update(source=source, archive_path=str(archive))
        self.records.append(record)
        self._transcript_offset += len(raw)
        if self.on_record is not None:
            self.on_record(dict(record))

    def finish(self, *, required: bool = True) -> dict[str, Any]:
        if self._state == "gradient":
            raise GradientStreamError("Producer stopped with an incomplete ORCA Cartesian gradient")
        if required and not self.records:
            raise GradientStreamError("Requested ORCA optimization produced no complete Cartesian gradients")
        self._finished = True
        return self.status
