"""Product B structure ingestion and provenance, independent of a materials solver."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any, Literal, Sequence
import warnings

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from cochem.core.cochem_constants import BOHR_TO_ANGSTROM
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass

Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Positions = tuple[tuple[float, float, float], ...]


def validate_periodic_cell(cell: Any) -> np.ndarray:
    array = np.asarray(cell, dtype=float)
    if array.shape != (3, 3) or not np.isfinite(array).all() or np.linalg.det(array) <= 1e-6 or np.linalg.cond(array) > 1e6:
        raise ValueError("Periodic cell must be finite, nondegenerate and right handed")
    return array


def validate_periodic_geometry(elements: Sequence[str], coordinates_angstrom: Any, cell_angstrom: Any) -> np.ndarray:
    cell = validate_periodic_cell(cell_angstrom)
    xyz = np.asarray(coordinates_angstrom, dtype=float)
    if not 1 <= len(elements) <= 256 or xyz.shape != (len(elements), 3) or not np.isfinite(xyz).all():
        raise ValueError("Periodic coordinates require 1--256 finite Cartesian atom positions")
    for symbol in elements:
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z][a-z]?", symbol) or symbol in {"D", "T"}:
            raise ValueError("Periodic atomic species must be explicit element symbols")
        get_nuclide_mass(symbol)
    fractional = xyz @ np.linalg.inv(cell)
    for index in range(len(elements)):
        delta = fractional[index + 1:] - fractional[index]
        if np.any(np.linalg.norm((delta - np.rint(delta)) @ cell, axis=1) < 1e-6):
            raise ValueError("Periodic atom positions coincide under a lattice translation")
    return xyz


def periodic_structure_digest(elements: Sequence[str], coordinates_angstrom: Any, cell_angstrom: Any, pbc: Any) -> str:
    content = {"elements": list(elements), "coordinates_angstrom": np.asarray(coordinates_angstrom, dtype=float).tolist(),
               "cell_angstrom": np.asarray(cell_angstrom, dtype=float).tolist(), "pbc": list(pbc)}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class PeriodicStructureProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_format: Literal["json", "cif"]
    source_filename: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    structure_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_coordinate_system: Literal["cartesian", "fractional"]
    input_coordinate_units: Literal["angstrom", "bohr", "dimensionless"]
    input_cell_units: Literal["angstrom", "bohr"]


class PeriodicStructureInput(BaseModel):
    """Explicit periodic JSON: lattice vectors are rows, no inferred units."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["cochem.periodic-structure.v1"]
    elements: tuple[str, ...]
    cell: Matrix3
    cell_units: Literal["angstrom", "bohr"]
    coordinate_system: Literal["cartesian", "fractional"]
    coordinate_units: Literal["angstrom", "bohr", "dimensionless"]
    positions: Positions
    pbc: tuple[StrictBool, StrictBool, StrictBool]
    occupancies: tuple[float, ...] | None = None

    @model_validator(mode="after")
    def validate_structure(self) -> "PeriodicStructureInput":
        if not all(self.pbc):
            raise ValueError("Product B bulk ingestion requires three periodic boundary conditions")
        if (self.coordinate_system == "fractional") != (self.coordinate_units == "dimensionless"):
            raise ValueError("Fractional coordinates require dimensionless units; Cartesian positions require angstrom or bohr")
        if self.occupancies is not None and (len(self.occupancies) != len(self.elements) or any(v != 1. for v in self.occupancies)):
            raise ValueError("Partial occupancy or disorder requires a separately specified ordered structure")
        cell, xyz = self.canonical_arrays()
        validate_periodic_geometry(self.elements, xyz, cell)
        return self

    def canonical_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        cell = np.asarray(self.cell) * (BOHR_TO_ANGSTROM if self.cell_units == "bohr" else 1.)
        positions = np.asarray(self.positions)
        if self.coordinate_system == "fractional":
            xyz = positions @ cell
        else:
            xyz = positions * (BOHR_TO_ANGSTROM if self.coordinate_units == "bohr" else 1.)
        return cell, xyz


class PeriodicStructure(BaseModel):
    """Validated Cartesian structure with preserved source evidence."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["cochem.periodic-structure.validated.v1"] = "cochem.periodic-structure.validated.v1"
    elements: tuple[str, ...]
    coordinates_angstrom: Positions
    cell_angstrom: Matrix3
    pbc: tuple[StrictBool, StrictBool, StrictBool]
    source: PeriodicStructureProvenance

    @model_validator(mode="after")
    def verify_structure(self) -> "PeriodicStructure":
        validate_periodic_geometry(self.elements, self.coordinates_angstrom, self.cell_angstrom)
        if not all(self.pbc):
            raise ValueError("Product B bulk ingestion requires three periodic boundary conditions")
        if periodic_structure_digest(self.elements, self.coordinates_angstrom, self.cell_angstrom, self.pbc) != self.source.structure_sha256:
            raise ValueError("Canonical structure contradicts its ingestion provenance digest")
        return self

    @property
    def coordinates_fractional(self) -> list[list[float]]:
        return (np.asarray(self.coordinates_angstrom) @ np.linalg.inv(np.asarray(self.cell_angstrom))).tolist()

    def to_calculation_config(self, periodic_settings: dict[str, Any]) -> dict[str, Any]:
        """Produce the existing native-service request; no result/accuracy is invented."""
        from cochem_base.calc.periodic_execution import PeriodicCalculationConfig

        if {"cell_angstrom", "pbc", "structure_provenance"} & periodic_settings.keys():
            raise ValueError("Calculation settings cannot overwrite the ingested periodic structure")
        periodic = PeriodicCalculationConfig.model_validate({**periodic_settings, "cell_angstrom": self.cell_angstrom,
            "pbc": self.pbc, "structure_provenance": self.source.model_dump(mode="json")})
        geometry = "\n".join(s + " " + " ".join(format(v, ".17g") for v in xyz)
                             for s, xyz in zip(self.elements, self.coordinates_angstrom))
        return {"engine": "qe", "product_class": "B", "method": "PBE", "basis_set": "PAW", "is_opt": False,
                "geometry": geometry, "periodic": periodic.model_dump(mode="json")}


def _parse_cif(content: bytes) -> PeriodicStructureInput:
    from ase.io.cif import parse_cif

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        blocks = list(parse_cif(io.BytesIO(content), reader="ase"))
        if len(blocks) != 1:
            raise ValueError("Periodic CIF ingestion requires exactly one unambiguous structure block")
        block = blocks[0]
        fractional_input = "_atom_site_fract_x" in block
        if fractional_input == ("_atom_site_cartn_x" in block):
            raise ValueError("CIF requires exactly one fractional or Cartesian coordinate representation")
        for tag in ("_atom_site_disorder_group", "_atom_site_disorder_assembly"):
            values = block.get(tag, [])
            if not isinstance(values, (tuple, list)):
                values = [values]
            if any(str(value).strip() not in {".", "0"} for value in values):
                raise ValueError("CIF disorder must be resolved into an explicit ordered structure")
        occupancies = block.get("_atom_site_occupancy", [])
        if any(not isinstance(value, (int, float)) or value != 1. for value in occupancies):
            raise ValueError("CIF partial/unknown occupancies cannot be silently assigned a species")
        # Check the supplied sites before symmetry expansion can merge duplicates.
        original = block.get_unsymmetrized_structure()
        validate_periodic_geometry(original.get_chemical_symbols(), original.positions, original.cell.array)
        atoms = block.get_atoms(store_tags=True, primitive_cell=False, fractional_occupancies=False)
    if atoms is None or not all(atoms.pbc):
        raise ValueError("CIF requires a complete periodic cell")
    return PeriodicStructureInput(schema_version="cochem.periodic-structure.v1", elements=atoms.get_chemical_symbols(),
        cell=atoms.cell.array.tolist(), cell_units="angstrom",
        coordinate_system="fractional" if fractional_input else "cartesian",
        coordinate_units="dimensionless" if fractional_input else "angstrom",
        positions=atoms.get_scaled_positions(wrap=False).tolist() if fractional_input else atoms.positions.tolist(), pbc=atoms.pbc.tolist())


def parse_periodic_structure(content: str | bytes, *, format: str, filename: str = "<memory>") -> PeriodicStructure:
    """Parse one explicit JSON/CIF structure; hash the actual original input bytes."""
    data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError("Periodic structure input must contain 1 byte to 8 MiB")
    kind = format.lower().lstrip(".")
    if kind == "json":
        def unique_keys(pairs: list) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"Ambiguous duplicate JSON key: {key}")
                result[key] = value
            return result
        raw = json.loads(data, object_pairs_hook=unique_keys)
        source = PeriodicStructureInput.model_validate(raw)
    elif kind == "cif":
        source = _parse_cif(data)
    else:
        raise ValueError("Periodic structure format must be explicit JSON or CIF")
    cell, xyz = source.canonical_arrays()
    provenance = PeriodicStructureProvenance(source_format=kind, source_filename=filename,
        source_sha256=hashlib.sha256(data).hexdigest(),
        structure_sha256=periodic_structure_digest(source.elements, xyz, cell, source.pbc),
        input_coordinate_system=source.coordinate_system, input_coordinate_units=source.coordinate_units,
        input_cell_units=source.cell_units)
    return PeriodicStructure(elements=source.elements, coordinates_angstrom=xyz.tolist(), cell_angstrom=cell.tolist(),
                             pbc=source.pbc, source=provenance)


def ingest_periodic_structure(path: str | Path) -> PeriodicStructure:
    source = Path(path).expanduser().resolve(strict=True)
    if source.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Periodic structure input exceeds 8 MiB")
    return parse_periodic_structure(source.read_bytes(), format=source.suffix, filename=source.name)
