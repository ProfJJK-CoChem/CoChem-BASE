"""Authoritative Core Data Models & MolSSI QCSchema v1 Envelopes.

Defines QCResultsRecord (AtomicResult), MolecularTopology, PESPointRecord, and CalculationJobPayload
with explicit spatial coordinate envelopes, CODATA 2022 constants, deterministic UUIDv5 content hashing,
and machine-readable SPDX licensing.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cochem_base.core.cochem_crypto import canonicalize_json
from cochem_base.core.glossary import CalculationFidelity
from cochem_base.core.licensing import validate_spdx_license

# Authoritative CODATA 2022 conversion factors
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_BOHR: float = 1.0 / BOHR_TO_ANGSTROM

# Authoritative CoChem Namespace UUID for deterministic UUIDv5 hashing
NAMESPACE_COCHEM: uuid.UUID = uuid.UUID("a6c4f69a-2d4e-4e68-912f-6e2101e4a682")


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
    license: str = Field(
        default="CC-BY-4.0",
        description="SPDX license identifier governing data reuse rights (FAIR R1.1)",
    )

    @field_validator("license")
    @classmethod
    def validate_license_spdx(cls, v: str) -> str:
        return validate_spdx_license(v)

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
                    geom = geom.flatten().tolist()
                elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
                    flat_geom = []
                    for pt in geom:
                        flat_geom.extend(pt)
                    geom = flat_geom
                mol["geometry"] = geom
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


class PESPointRecord(BaseModel):
    """Point record representing a single potential energy surface evaluation with deterministic UUIDv5 [D]."""

    model_config = ConfigDict(extra="allow", validate_assignment=True, arbitrary_types_allowed=True)

    point_id: str = Field(default="", description="Deterministic UUIDv5 content-addressable point identifier")
    method_id: str = Field(default="unknown", description="Registered method identifier")
    coordinates: List[float] = Field(default_factory=list, description="Flat 1D atomic coordinates (size 3*N)")
    symbols: List[str] = Field(default_factory=list, description="Ordered IUPAC elemental symbols")
    method: str = Field(default="unknown", description="Electronic structure method")
    basis: Optional[str] = Field(default=None, description="Primary basis set")
    energy: float = Field(default=0.0, description="Electronic energy in Hartrees")
    gradient: Optional[List[float]] = Field(None, description="Flat 1D gradient in Hartree/Bohr (size 3*N)")
    units: Literal["bohr", "angstrom"] = Field(default="bohr", description="Physical unit of spatial coordinates")
    converged: bool = Field(default=True, description="Whether SCF and geometry optimization converged")
    wall_s: float = Field(default=0.0, ge=0.0, description="Calculation wall clock time in seconds")
    provenance: Any = Field(default_factory=dict, description="Calculation provenance record")
    license: str = Field(default="CC-BY-4.0", description="SPDX license identifier")

    @classmethod
    def generate_point_id(
        cls,
        geometry: List[float],
        symbols: List[str],
        method: str,
        basis: Optional[str] = None,
    ) -> str:
        """Deterministically generate UUIDv5 point ID from canonical RFC 8785 JSON representation [D]."""
        normalized_payload = {
            "symbols": [str(s).upper() for s in symbols],
            "geometry": [round(float(c), 8) for c in geometry],
            "method": str(method).strip().lower(),
            "basis": (basis or "").strip().lower(),
        }
        canonical_bytes = canonicalize_json(normalized_payload)
        return str(uuid.uuid5(NAMESPACE_COCHEM, canonical_bytes.decode("utf-8")))

    @field_validator("license")
    @classmethod
    def validate_license_spdx(cls, v: str) -> str:
        return validate_spdx_license(v)

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coords_array(cls, v: Any) -> List[float]:
        if isinstance(v, np.ndarray):
            return [float(x) for x in v.flatten()]
        if isinstance(v, (list, tuple)):
            flat: List[float] = []
            for item in v:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend([float(x) for x in item])
                else:
                    flat.append(float(item))
            return flat
        raise ValueError(f"Invalid coordinate format: {type(v)}")

    @field_validator("gradient", mode="before")
    @classmethod
    def validate_grad_array(cls, v: Any) -> Optional[List[float]]:
        if v is None:
            return None
        if isinstance(v, np.ndarray):
            return [float(x) for x in v.flatten()]
        if isinstance(v, (list, tuple)):
            flat: List[float] = []
            for item in v:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend([float(x) for x in item])
                else:
                    flat.append(float(item))
            return flat
        raise ValueError(f"Invalid gradient format: {type(v)}")

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_default_point_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if "coordinates" not in data and "geometry" in data:
            data["coordinates"] = data["geometry"]
        elif "coordinates" in data and "geometry" not in data:
            data["geometry"] = data["coordinates"]

        coords = data.get("coordinates") or []
        if isinstance(coords, np.ndarray):
            coords = coords.flatten().tolist()
            data["coordinates"] = coords
        elif isinstance(coords, list) and coords and isinstance(coords[0], (list, tuple)):
            flat = []
            for item in coords:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend([float(x) for x in item])
                else:
                    flat.append(float(item))
            coords = flat
            data["coordinates"] = coords

        if not data.get("point_id"):
            syms = data.get("symbols") or []
            meth = data.get("method") or data.get("method_id") or "unknown"
            bas = data.get("basis") or ""
            data["point_id"] = cls.generate_point_id(
                geometry=coords,
                symbols=syms,
                method=meth,
                basis=bas,
            )

        if not data.get("method_id") and data.get("method"):
            data["method_id"] = data["method"]

        return data

    def to_angstrom(self) -> PESPointRecord:
        """Convert coordinates and gradients to Angstroms using authoritative CODATA 2022 constants."""
        if self.units == "angstrom":
            return self
        converted_coords = [float(c * BOHR_TO_ANGSTROM) for c in self.coordinates]
        converted_grad = (
            [float(g * ANGSTROM_TO_BOHR) for g in self.gradient]
            if self.gradient is not None
            else None
        )
        return PESPointRecord(
            point_id=self.point_id,
            method_id=self.method_id,
            coordinates=converted_coords,
            symbols=list(self.symbols),
            method=self.method,
            basis=self.basis,
            energy=self.energy,
            gradient=converted_grad,
            units="angstrom",
            converged=self.converged,
            wall_s=self.wall_s,
            provenance=copy.deepcopy(self.provenance),
            license=self.license,
        )

    def to_bohr(self) -> PESPointRecord:
        """Convert coordinates and gradients to Bohr using authoritative CODATA 2022 constants."""
        if self.units == "bohr":
            return self
        converted_coords = [float(c * ANGSTROM_TO_BOHR) for c in self.coordinates]
        converted_grad = (
            [float(g * BOHR_TO_ANGSTROM) for g in self.gradient]
            if self.gradient is not None
            else None
        )
        return PESPointRecord(
            point_id=self.point_id,
            method_id=self.method_id,
            coordinates=converted_coords,
            symbols=list(self.symbols),
            method=self.method,
            basis=self.basis,
            energy=self.energy,
            gradient=converted_grad,
            units="bohr",
            converged=self.converged,
            wall_s=self.wall_s,
            provenance=copy.deepcopy(self.provenance),
            license=self.license,
        )


class CalculationJobPayload(BaseModel):
    """Calculation job specification supporting Method Matrix v4 fidelity tiers [D]."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique job identifier")
    molecule: Dict[str, Any] = Field(default_factory=dict, description="Target molecular topology specifications")
    driver: Literal["energy", "gradient", "hessian", "properties"] = "energy"
    fidelity: Union[CalculationFidelity, str] = Field(
        default=CalculationFidelity.R_DFT,
        description="Canonical fidelity tier or custom specification",
    )
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Calculation keywords")
    license: str = Field(default="CC-BY-4.0", description="SPDX license identifier")

    @field_validator("fidelity", mode="before")
    @classmethod
    def validate_fidelity(cls, v: Any) -> Union[CalculationFidelity, str]:
        if isinstance(v, CalculationFidelity):
            return v
        if isinstance(v, str):
            clean = v.strip()
            for member in CalculationFidelity:
                if member.value.lower() == clean.lower() or member.name.lower() == clean.lower():
                    return member
            return clean
        raise ValueError(f"Invalid fidelity specification: {v}")

    @field_validator("license")
    @classmethod
    def validate_license_spdx(cls, v: str) -> str:
        return validate_spdx_license(v)


__all__ = [
    "BOHR_TO_ANGSTROM",
    "ANGSTROM_TO_BOHR",
    "NAMESPACE_COCHEM",
    "QCResultsRecord",
    "MolecularTopology",
    "PESPointRecord",
    "CalculationJobPayload",
]
