"""Authoritative Core Data Models & MolSSI QCSchema v1 Envelopes.

Defines QCResultsRecord (AtomicResult) and MolecularTopology with explicit
spatial coordinate dimensional envelopes, CODATA 2022 constants, and backward-compatible accessors.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Literal, Optional, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Authoritative CODATA 2022 conversion factors
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_BOHR: float = 1.0 / BOHR_TO_ANGSTROM


class QCResultsRecord(BaseModel):
    """MolSSI QCSchema v1 compliant AtomicResult record with backward-compatible accessors."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True, validate_assignment=True)

    schema_name: Literal["qcschema_output"] = "qcschema_output"
    schema_version: int = 1
    molecule: Dict[str, Any] = Field(default_factory=dict, description="Nested molecular topology specifications")
    driver: Literal["energy", "gradient", "hessian", "properties"] = "energy"
    model: Dict[str, Any] = Field(default_factory=lambda: {"method": "unknown", "basis": None})
    return_result: Union[float, List[float], List[List[float]]] = 0.0
    properties: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_validate_qcschema(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Convenience conversion for top-level symbols and geometry
        if "molecule" not in data or not data["molecule"]:
            mol: Dict[str, Any] = {}
            if "symbols" in data:
                mol["symbols"] = list(data.pop("symbols"))
            if "geometry" in data:
                geom = data.pop("geometry")
                if isinstance(geom, np.ndarray):
                    geom = geom.flatten().tolist()
                elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
                    flat_geom = []
                    for pt in geom:
                        flat_geom.extend(pt)
                    geom = flat_geom
                mol["geometry"] = geom
            if "molecular_charge" in data:
                mol["molecular_charge"] = data.pop("molecular_charge")
            if "molecular_multiplicity" in data:
                mol["molecular_multiplicity"] = data.pop("molecular_multiplicity")
            data["molecule"] = mol
        else:
            mol = dict(data["molecule"])
            if "geometry" in mol:
                geom = mol["geometry"]
                if isinstance(geom, np.ndarray):
                    mol["geometry"] = geom.flatten().tolist()
                elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
                    flat_geom = []
                    for pt in geom:
                        flat_geom.extend(pt)
                    mol["geometry"] = flat_geom
            data["molecule"] = mol

        # Format return_result if given as NumPy array
        if "return_result" in data:
            res = data["return_result"]
            if isinstance(res, np.ndarray):
                if res.ndim == 1:
                    data["return_result"] = res.tolist()
                elif res.ndim == 0:
                    data["return_result"] = float(res)
                else:
                    data["return_result"] = res.tolist()

        # Handle backward-compatible energy_hartree kwarg
        if "energy_hartree" in data and "return_result" not in data:
            e = float(data.pop("energy_hartree"))
            data["return_result"] = e
            if "properties" not in data:
                data["properties"] = {}
            data["properties"]["return_energy"] = e

        return data

    @property
    def energy_hartree(self) -> Optional[float]:
        """Backward-compatible property returning total electronic energy in Hartree."""
        if "return_energy" in self.properties:
            return float(self.properties["return_energy"])
        if self.driver == "energy" and isinstance(self.return_result, (int, float)):
            return float(self.return_result)
        return None

    @property
    def gradient_bohr(self) -> Optional[List[float]]:
        """Backward-compatible property returning Cartesian nuclear gradient in Hartree/Bohr."""
        if self.driver == "gradient":
            if isinstance(self.return_result, list):
                if self.return_result and isinstance(self.return_result[0], list):
                    flat_grad: List[float] = []
                    for row in self.return_result:  # type: ignore[union-attr]
                        flat_grad.extend([float(x) for x in row])
                    return flat_grad
                return [float(x) for x in self.return_result]  # type: ignore[union-attr]
        if "return_gradient" in self.properties:
            grad = self.properties["return_gradient"]
            if isinstance(grad, list):
                return [float(x) for x in grad]
        return None

    @property
    def hessian(self) -> Optional[Union[List[float], List[List[float]]]]:
        """Backward-compatible property returning Cartesian nuclear Hessian."""
        if self.driver == "hessian":
            if isinstance(self.return_result, list):
                return self.return_result
        if "return_hessian" in self.properties:
            h = self.properties["return_hessian"]
            if isinstance(h, list):
                return h
        return None


class MolecularTopology(BaseModel):
    """Molecular spatial coordinates standardized to flat 1D arrays with explicit unit tagging."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    symbols: List[str] = Field(..., description="Ordered IUPAC elemental symbols")
    geometry: List[float] = Field(..., description="Flat 1D atomic Cartesian coordinates (size 3*N)")
    units: Literal["bohr", "angstrom"] = Field(default="bohr", description="Physical coordinate unit")

    @model_validator(mode="before")
    @classmethod
    def _validate_and_flatten_coords(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        symbols = data.get("symbols", [])
        geom = data.get("geometry", [])

        # Flatten 2D coordinate arrays if provided
        if isinstance(geom, np.ndarray):
            geom = geom.flatten().tolist()
        elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
            flat = []
            for pt in geom:
                flat.extend([float(c) for c in pt])
            geom = flat
        elif isinstance(geom, list):
            geom = [float(c) for c in geom]

        n_atoms = len(symbols)
        if n_atoms > 0 and len(geom) != 3 * n_atoms:
            raise ValueError(
                f"Geometry coordinate dimension mismatch: expected {3 * n_atoms} components for {n_atoms} atoms, got {len(geom)}"
            )

        data["geometry"] = geom
        return data

    def to_angstrom(self) -> MolecularTopology:
        """Convert coordinates to Angstroms using authoritative CODATA 2022 constant."""
        if self.units == "angstrom":
            return self
        converted = [float(c * BOHR_TO_ANGSTROM) for c in self.geometry]
        return MolecularTopology(
            symbols=list(self.symbols),
            geometry=converted,
            units="angstrom",
        )

    def to_bohr(self) -> MolecularTopology:
        """Convert coordinates to Bohr using authoritative CODATA 2022 constant."""
        if self.units == "bohr":
            return self
        converted = [float(c * ANGSTROM_TO_BOHR) for c in self.geometry]
        return MolecularTopology(
            symbols=list(self.symbols),
            geometry=converted,
            units="bohr",
        )
