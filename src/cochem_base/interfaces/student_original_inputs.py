"""Bind retained originals to a scientific request before native execution.

Shared by Actions and genuine scheduler allocations. This validates original
source identity and geometry; it never runs an uploaded file or claims science.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from . import student_request as contract


def _atomic_json(path: Path, value: dict) -> None:
    from cochem_base.core.cochem_core_registry_manager import atomic_write_json
    atomic_write_json(path, value)


def bind_original_inputs(request: dict, output: Path) -> dict | None:
    """Reparse actual originals and bind derived geometry/state before science."""
    if request["data_inputs"] is None:
        return request["calculation"]
    import numpy as np
    from cochem_base.calc.calculation_service import parse_run_geometry_identity
    bundle = contract.strict_json((output / "data-inputs.json").read_bytes())
    root = output / "data-inputs"
    receipt = bundle["receipt"]
    expected_files = {"input-receipt.json"}

    def source_bytes(record: dict) -> bytes:
        if not isinstance(record, dict) or set(record) != {"filename", "format", "path", "sha256"}:
            raise ValueError("Original structure receipt fields are invalid")
        contract.safe_relative_path(record["filename"])
        path = contract.safe_relative_path(record["path"])
        if len(path.parts) != 2 or path.parts[0] != "source":
            raise ValueError("Original structure must remain under its sealed source directory")
        expected_files.add(str(path))
        contents = (root / path).read_bytes()
        if hashlib.sha256(contents).hexdigest() != record["sha256"]:
            raise ValueError("Original source changed after sealed extraction")
        return contents

    raw = dict(request["calculation"]) if request["calculation"] is not None else None
    geometry = (raw["geometry"] if raw is not None else
                base64.b64decode(request["files"][request["provider"]["artifact"]]["content_base64"], validate=True).decode("utf-8-sig"))
    identity = parse_run_geometry_identity(geometry)
    if receipt.get("kind") == "molecular_ingestion":
        if set(receipt) != {"kind", "source", "record_index"}:
            raise ValueError("Molecular original-source selection receipt is invalid")
        from cochem_base.intake.structure_formats import parse_structure_text
        contents = source_bytes(receipt["source"])
        records = parse_structure_text(contents.decode("utf-8-sig"), receipt["source"]["format"])
        index = receipt["record_index"]
        if type(index) is not int or not 0 <= index < len(records):
            raise ValueError("The selected molecular record is absent; no first-record fallback is permitted")
        selected = records[index]
        if selected.get("ghost_indices"):
            raise ValueError("Original ghost centers require a dedicated counterpoise adapter; inspection alone does not authorize this calculation")
        if (tuple(selected["symbols"]) != identity.nuclides
                or not np.allclose(selected["coords"], identity.coordinates_angstrom, atol=1e-12, rtol=0)):
            raise ValueError("The derived calculation XYZ differs from the selected original molecular record")
        state = raw if raw is not None else request["provider"]["options"]
        if raw is None and request["provider"]["module"] == "topos" and request["provider"]["operation"] != "geometry_analysis":
            state = state["topos_request"]["molecule"]
        for field in ("charge", "multiplicity"):
            observed = selected.get(field)
            # Geometric inspection has no electronic calculation or invented
            # state. Preserve the encoded original without silently assigning
            # neutral/singlet defaults to an operation that does not use them.
            if observed is not None and field in state and state[field] != observed:
                raise ValueError("The requested electronic state contradicts the actual original molecular input")
        validation = {"kind": receipt["kind"], "source_sha256": receipt["source"]["sha256"],
            "source_filename": receipt["source"]["filename"], "source_format": receipt["source"]["format"],
            "record_count": len(records), "selected_record_index": index,
            "all_original_records_retained": True, "derived_geometry_bound": True,
            "nuclides": list(identity.nuclides), "coordinates_angstrom": [list(row) for row in identity.coordinates_angstrom],
            "source_charge": selected.get("charge"), "source_multiplicity": selected.get("multiplicity"),
            "nuclear_identity": identity.metadata, "scientific_execution_performed": False}
    elif receipt.get("kind") == "periodic_inputs":
        if raw is None or raw["engine"] != "qe" or set(receipt) != {"kind", "structure", "pseudopotentials"}:
            raise ValueError("Periodic original-source receipt is invalid")
        from cochem_base.calc.periodic import parse_periodic_structure
        from cochem_base.calc.periodic_execution import PeriodicCalculationConfig, _validate_inputs
        record = receipt["structure"]
        structure = parse_periodic_structure(source_bytes(record), format=record["format"], filename=record["filename"])
        periodic = dict(raw["periodic"])
        if (structure.elements != identity.elements
                or not np.allclose(structure.coordinates_angstrom, identity.coordinates_angstrom, atol=1e-12, rtol=0)
                or not np.allclose(structure.cell_angstrom, periodic["cell_angstrom"], atol=1e-12, rtol=0)
                or periodic.get("structure_provenance") != structure.source.model_dump(mode="json")):
            raise ValueError("Requested periodic geometry/cell/provenance differs from the actual original CIF/JSON")
        if set(receipt["pseudopotentials"]) != set(periodic["pseudopotentials"]):
            raise ValueError("Periodic PAW inventory differs from its exact requested species")
        bound = {}
        for element, potential in receipt["pseudopotentials"].items():
            if (not isinstance(potential, dict) or set(potential) != {"filename", "path", "sha256"}
                    or potential["path"] != "pseudopotentials/" + element + ".UPF"
                    or periodic["pseudopotentials"][element] != {"path": potential["path"], "sha256": potential["sha256"]}):
                raise ValueError("Periodic PAW file contradicts its portable path/hash binding")
            contract.safe_relative_path(potential["filename"])
            expected_files.add(potential["path"])
            bound[element] = {"path": str(root / potential["path"]), "sha256": potential["sha256"]}
        periodic["pseudopotentials"] = bound
        _validate_inputs(identity.elements, identity.coordinates_angstrom, PeriodicCalculationConfig.model_validate(periodic),
                         raw.get("charge", 0), raw.get("multiplicity", 1))
        raw["periodic"] = periodic
        validation = {"kind": receipt["kind"], "source_sha256": structure.source.source_sha256,
            "structure_sha256": structure.source.structure_sha256, "derived_geometry_bound": True,
            "pseudopotentials": receipt["pseudopotentials"], "PAW_headers_validated": True,
            "scientific_execution_performed": False, "accuracy_validated": False}
    else:
        raise ValueError("Unsupported original-ingestion kind")
    if set(bundle["manifest"]["files"]) != expected_files:
        raise ValueError("Original-ingestion bundle contains unrequested files")
    _atomic_json(output / "original-ingestion-validation.json", validation)
    return raw



__all__ = ["bind_original_inputs"]
