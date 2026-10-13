"""Recoverable input-list choices, kept separately from original scientific data."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

SCHEMA = "cochem.student-input-selection/1"
MAX_CHOICES = 1024


def _state_path(artifact_dir: Path) -> Path:
    from .student_ingestion import _library
    path = _library(artifact_dir) / "selection-state.json"
    if path.is_symlink() or path.with_name(path.name + ".lock").is_symlink():
        raise ValueError("Saved removed input choices cannot use symbolic links")
    return path


def read_input_visibility(artifact_dir: Path) -> dict:
    """Read a complete atomic list; damaged saved choices never reset silently."""
    from .student_ingestion import _unique_json
    path = _state_path(artifact_dir)
    if not path.exists():
        return {"schema_version": SCHEMA, "inputs": [], "geometries": [], "attachments": []}
    try:
        if not path.is_file() or path.stat().st_size > 128 * 1024:
            raise ValueError("The saved list is not a bounded regular file")
        state = _unique_json(path.read_text(encoding="utf-8"))
        if (not isinstance(state, dict) or set(state) not in ({"schema_version", "inputs", "geometries"},
                {"schema_version", "inputs", "geometries", "attachments"})
                or state["schema_version"] != SCHEMA):
            raise ValueError("The saved list format is invalid")
        for category in ("inputs", "geometries"):
            values = state[category]
            if (not isinstance(values, list) or len(values) > MAX_CHOICES
                    or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value) for value in values)
                    or len(set(values)) != len(values)):
                raise ValueError("The saved list contains invalid or repeated identifiers")
        attachments = state.setdefault("attachments", [])
        if (not isinstance(attachments, list) or len(attachments) > 2
                or any(not isinstance(item, str) or item not in {"r2_reference", "read_hessian"} for item in attachments)
                or len(set(attachments)) != len(attachments)):
            raise ValueError("The saved attachment choices are invalid")
        return state
    except (ValueError, OSError, UnicodeError) as error:
        raise ValueError("Could not read the saved removed input choices. Original files are unchanged: " + str(error)) from error


def set_attachment_visibility(artifact_dir: Path, kind: str, *, hidden: bool) -> dict:
    """Remember cleared optional attachments so earlier uploads do not return."""
    from cochem_base.core.cochem_core_registry_manager import AtomicFileLock, atomic_write_json
    if not isinstance(kind, str) or kind not in {"r2_reference", "read_hessian"} or type(hidden) is not bool:
        raise ValueError("Choose the R2 reference or starting Hessian attachment")
    path = _state_path(artifact_dir)
    with AtomicFileLock(str(path) + ".lock", timeout=10.0):
        state = read_input_visibility(artifact_dir)
        selected = set(state["attachments"])
        if hidden:
            selected.add(kind)
        else:
            selected.discard(kind)
        state["attachments"] = sorted(selected)
        atomic_write_json(path, state)
        return state


def set_input_visibility(artifact_dir: Path, category: str, input_id: str, *, hidden: bool) -> dict:
    """Atomically remove or restore one list entry without changing its files."""
    from cochem_base.core.cochem_core_registry_manager import AtomicFileLock, atomic_write_json
    if not isinstance(category, str) or category not in {"inputs", "geometries"} or type(hidden) is not bool:
        raise ValueError("Choose an input or geometry to remove or restore")
    if not isinstance(input_id, str) or not re.fullmatch(r"[0-9a-f]{32}", input_id):
        raise ValueError("Select an existing input from the list")
    path = _state_path(artifact_dir)
    folder = path.parent / input_id if category == "inputs" else path.parent.parent / "StudentInputs" / input_id
    manifest = folder / ("receipt.json" if category == "inputs" else "input-manifest.json")
    if (folder.is_symlink() or folder.parent.is_symlink() or not folder.is_dir()
            or manifest.is_symlink() or not manifest.is_file()):
        raise ValueError("The original input record could not be found; no list choices were changed")
    if not hidden:
        from .student_ingestion import _load_retained_input, _unique_json
        if category == "inputs":
            _load_retained_input(folder)
        else:
            if manifest.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("The geometry record is too large to restore")
            record = _unique_json(manifest.read_text(encoding="utf-8"))
            original = Path(record["path"])
            if (record.get("id") != input_id or original.parent != folder or original.is_symlink()
                    or not original.is_file() or original.stat().st_size > 2 * 1024 * 1024
                    or hashlib.sha256(original.read_bytes()).hexdigest() != record.get("sha256")):
                raise ValueError("The original geometry has changed and cannot be restored")
    with AtomicFileLock(str(path) + ".lock", timeout=10.0):
        state = read_input_visibility(artifact_dir)
        selected = set(state[category])
        if hidden:
            selected.add(input_id)
        else:
            selected.discard(input_id)
        if len(selected) > MAX_CHOICES:
            raise ValueError("The removed input list is full; restore an entry before removing another")
        state[category] = sorted(selected)
        atomic_write_json(path, state)
        return state


def geometry_dependencies(record: dict) -> tuple[str | None, tuple[str, ...]]:
    """Validate source references before using them to filter saved choices."""
    source = record.get("source_input_id")
    if source is not None and (not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{32}", source)):
        raise ValueError("The saved geometry has an invalid original input reference")
    monomers = record.get("monomer_sources", [])
    if not isinstance(monomers, list) or len(monomers) > MAX_CHOICES:
        raise ValueError("The saved geometry has an invalid monomer source list")
    identities = []
    for monomer in monomers:
        if (not isinstance(monomer, dict) or not isinstance(monomer.get("id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", monomer["id"])):
            raise ValueError("The saved geometry has an invalid monomer source reference")
        identities.append(monomer["id"])
    return source, tuple(identities)


def partition_geometry_choices(records: dict[str, dict], state: dict) -> tuple[dict, dict]:
    """Hide explicit removals and assemblies derived from removed source inputs."""
    hidden = set(state["geometries"])
    hidden_sources = set(state["inputs"])
    dependencies = {key: geometry_dependencies(record) for key, record in records.items()}
    changed = True
    while changed:
        before = len(hidden)
        for key, (source, monomers) in dependencies.items():
            if source in hidden_sources or any(monomer in hidden for monomer in monomers):
                hidden.add(key)
        changed = len(hidden) != before
    return ({key: value for key, value in records.items() if key not in hidden},
            {key: value for key, value in records.items() if key in hidden})
