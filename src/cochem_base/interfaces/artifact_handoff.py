"""Integrity-checked BASE artifact snapshots for future module consumers."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Literal
import uuid

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .module_registry import ModuleCapability, canonical_module_id, get_module_capability


class ArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["geometry_xyz", "cartesian_hessian", "calculation_result", "periodic_structure"]
    filename: str
    source_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    metadata: dict[str, Any]


class ModuleHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["cochem.module-handoff/1"] = "cochem.module-handoff/1"
    handoff_id: str
    created_at: str
    module_id: str
    operation: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    status: Literal["pending_integration"] = "pending_integration"
    capability: ModuleCapability
    artifact: ArtifactReference
    options: dict[str, Any] = Field(default_factory=dict)
    scientific_execution_performed: Literal[False] = False
    validation_scope: Literal["artifact_structure_and_integrity"] = "artifact_structure_and_integrity"

    @model_validator(mode="after")
    def discovery_is_not_execution_authority(self) -> "ModuleHandoff":
        if self.module_id != self.capability.module_id or canonical_module_id(self.module_id) != self.module_id:
            raise ValueError("Handoff recipient metadata is inconsistent")
        if self.module_id != "base" and self.capability.status.value == "available":
            raise ValueError("A future-module discovery snapshot cannot claim verified availability")
        return self


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _inspect(path: Path) -> tuple[str, dict]:
    """Validate actual scientific structure; never infer missing observables."""
    suffix = path.suffix.lower()
    json_data = json.loads(path.read_text(encoding="utf-8")) if suffix == ".json" else None
    periodic_schema = json_data.get("schema_version") if isinstance(json_data, dict) else None
    if suffix == ".cif" or periodic_schema in {"cochem.periodic-structure.v1", "cochem.periodic-structure.validated.v1"}:
        from cochem_base.calc.periodic import ingest_periodic_structure, PeriodicStructure
        data = (PeriodicStructure.model_validate(json_data) if periodic_schema == "cochem.periodic-structure.validated.v1"
                else ingest_periodic_structure(path))
        return "periodic_structure", {"symbols": list(data.elements), "atom_count": len(data.elements),
            "canonical_coordinates_unit": "angstrom", "canonical_cell_unit": "angstrom", "pbc": list(data.pbc),
            "source_coordinate_system": data.source.input_coordinate_system,
            "source_coordinate_units": data.source.input_coordinate_units,
            "source_cell_units": data.source.input_cell_units,
            "structure_sha256": data.source.structure_sha256}
    if suffix in {".npz", ".h5", ".hdf5", ".hess"}:
        from cochem_base.spectroscopy.artifacts import load_hessian_artifact
        data = load_hessian_artifact(path)
        return "cartesian_hessian", {
            "symbols": list(data.symbols), "atom_count": len(data.symbols),
            "coordinates_unit": "angstrom", "hessian_unit": "hartree/bohr^2", "source": data.source,
        }
    if suffix == ".xyz":
        from cochem_base.calc.calculation_service import parse_run_geometry
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].strip().isdigit() or int(lines[0]) <= 0:
            raise ValueError("XYZ handoff requires an explicit positive atom count")
        symbols, coordinates = parse_run_geometry("\n".join(lines))
        if len(symbols) != int(lines[0]) or len(lines[2:]) != len(symbols):
            raise ValueError("XYZ handoff must contain exactly one complete geometry")
        if not np.isfinite(coordinates).all():
            raise ValueError("XYZ coordinates must be finite")
        return "geometry_xyz", {"symbols": symbols, "atom_count": len(symbols), "coordinates_unit": "angstrom"}
    if suffix == ".json":
        data = json_data
        if not isinstance(data, dict) or data.get("converged") is not True:
            raise ValueError("Result handoff requires explicit convergence evidence")
        energy = data.get("energy_hartree")
        if isinstance(energy, bool) or not isinstance(energy, (int, float)) or not np.isfinite(energy):
            raise ValueError("Result handoff requires a finite Hartree energy")
        if not isinstance(data.get("engine"), str) or not data["engine"].strip():
            raise ValueError("Result handoff requires its producer engine")
        return "calculation_result", {"engine": data["engine"], "energy_unit": "hartree",
                                       "scope": data.get("scope", "producer_scope_unspecified")}
    raise ValueError("Supported artifacts are a single XYZ geometry, geometry-bound Hessian (.npz/.h5/.hess), or converged calculation result JSON")


def prepare_module_handoff(module_id: str, artifact_path: str | Path, destination: str | Path,
                           *, operation: str, options: dict[str, Any] | None = None) -> ModuleHandoff:
    """Copy and validate one artifact, then publish its pending-consumer manifest.

    ``destination`` is a new package directory outside the source tree. This
    function never starts a downstream calculation or reports scientific success.
    """
    from cochem.core.context import assert_writable_path

    name = canonical_module_id(module_id)
    source = Path(artifact_path).expanduser().resolve(strict=True)
    target = Path(destination).expanduser().resolve()
    assert_writable_path(target)
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Handoff source must be a nonempty regular file")
    # Validate JSON options before creating any output or copying a large file.
    json.dumps(options or {}, allow_nan=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    try:
        # Read-only baseline data may not allow adjacent lock files. Check both
        # source and copied bytes, then validate the private snapshot itself.
        digest = _digest(source)
        copied = target / ("artifact" + source.suffix.lower())
        shutil.copyfile(source, copied)
        if _digest(source) != digest or _digest(copied) != digest:
            raise ValueError("Source changed while preparing the handoff")
        kind, details = _inspect(copied)
        reference = ArtifactReference(kind=kind, filename=copied.name, source_path=str(source),
                                      sha256=digest, size_bytes=copied.stat().st_size, metadata=details)
        handoff = ModuleHandoff(
            handoff_id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
            module_id=name, operation=operation, capability=get_module_capability(name),
            artifact=reference, options=options or {},
        )
        manifest = target / "handoff.json"
        temporary = target / "handoff.json.partial"
        temporary.write_text(handoff.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(manifest)
        return handoff
    except BaseException:
        # The directory was created exclusively by this invocation.
        shutil.rmtree(target)
        raise


def load_module_handoff(manifest_path: str | Path) -> ModuleHandoff:
    """Revalidate copied bytes and scientific structure at the receiving boundary."""
    path = Path(manifest_path).expanduser().resolve(strict=True)
    handoff = ModuleHandoff.model_validate_json(path.read_text(encoding="utf-8"))
    json.dumps(handoff.options, allow_nan=False)
    if canonical_module_id(handoff.module_id) != handoff.module_id or handoff.capability.module_id != handoff.module_id:
        raise ValueError("Handoff recipient metadata is inconsistent")
    artifact = (path.parent / handoff.artifact.filename).resolve(strict=True)
    if artifact.parent != path.parent or Path(handoff.artifact.filename).name != handoff.artifact.filename:
        raise ValueError("Handoff artifact must remain inside its package")
    if artifact.stat().st_size != handoff.artifact.size_bytes or _digest(artifact) != handoff.artifact.sha256:
        raise ValueError("Handoff artifact integrity verification failed")
    kind, details = _inspect(artifact)
    if kind != handoff.artifact.kind or details != handoff.artifact.metadata:
        raise ValueError("Handoff artifact metadata disagrees with its actual contents")
    return handoff
