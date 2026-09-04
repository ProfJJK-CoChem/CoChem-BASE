"""Authoritative Core Data Models & MolSSI QCSchema v1 Envelopes.

Defines QCResultsRecord (AtomicResult), MolecularTopology, PESPointRecord, and CalculationJobPayload
with explicit spatial coordinate envelopes, CODATA 2022 constants, deterministic UUIDv5 content hashing,
machine-readable SPDX licensing, and schema version migration contracts adhering to FAIR F2, I1, and R1.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Callable, ClassVar, Dict, List, Literal, Optional, Tuple, Type, TypeVar, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cochem_base.core.cochem_crypto import canonicalize_json
from cochem_base.core.exceptions import CoordinateShapeError, SchemaMigrationError
from cochem_base.core.glossary import CalculationFidelity
from cochem_base.core.licensing import validate_spdx_license

# Authoritative CODATA 2022 conversion factors
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_BOHR: float = 1.0 / BOHR_TO_ANGSTROM

# Authoritative CoChem Namespace UUID for deterministic UUIDv5 hashing
NAMESPACE_COCHEM: uuid.UUID = uuid.UUID("a6c4f69a-2d4e-4e68-912f-6e2101e4a682")

# Global schema version constant (FAIR F2, I1, R1)
CURRENT_CORE_SCHEMA_VERSION: int = 1

T = TypeVar("T", bound=BaseModel)
MigrationCallable = Callable[[Dict[str, Any]], Dict[str, Any]]
_MIGRATION_REGISTRY: Dict[Tuple[str, int], MigrationCallable] = {}


def register_migration(model_name: str, from_version: int) -> Callable[[MigrationCallable], MigrationCallable]:
    """Decorator registering a transformation function from a specific schema version to from_version + 1."""

    def decorator(func: MigrationCallable) -> MigrationCallable:
        _MIGRATION_REGISTRY[(model_name, from_version)] = func
        return func

    return decorator


def migrate_payload(payload: Dict[str, Any], target_model: Type[BaseModel]) -> Dict[str, Any]:
    """Migrates a raw dictionary payload sequentially up to target_model's current schema_version."""
    model_name = target_model.__name__
    current_version = payload.get("schema_version", 0)
    target_version = getattr(target_model, "CURRENT_VERSION", CURRENT_CORE_SCHEMA_VERSION)

    data = dict(payload)
    while current_version < target_version:
        key = (model_name, current_version)
        if key not in _MIGRATION_REGISTRY:
            raise SchemaMigrationError(
                f"No migration path registered for {model_name} from version {current_version} to {current_version + 1}.",
                details={"model": model_name, "from_version": current_version, "target_version": target_version},
            )
        data = _MIGRATION_REGISTRY[key](data)
        current_version = data.get("schema_version", current_version + 1)

    return data


class ThermodynamicsProvenance(BaseModel):
    """Provenance metadata for quasi-harmonic thermodynamic corrections and Boltzmann weighting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    damping_model: str = Field(
        default="grimme_quasi_rrho",
        description="Vibrational entropy damping model (e.g. grimme_quasi_rrho, truhlar_quasi_harmonic, harmonic).",
    )
    low_freq_cutoff_cm1: float = Field(
        default=100.0,
        description="Low-frequency cutoff/interpolation threshold in wavenumbers (cm^-1).",
    )
    temperature_k: float = Field(
        default=298.15,
        description="Thermodynamic temperature in Kelvin.",
    )
    pressure_atm: float = Field(
        default=1.0,
        description="Standard state pressure in atmospheres.",
    )
    rotor_cutoff_cm1: Optional[float] = Field(
        default=None,
        description="Free-rotor transition threshold if using Head-Gordon or multi-cutoff damping.",
    )
    provenance_tag: str = Field(
        default="[D]",
        description="Method Matrix provenance marker ([M] measured, [D] derived, [E] estimated).",
    )

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)


class QCResultsRecord(BaseModel):
    """MolSSI QCSchema v1 compliant AtomicResult record with backward-compatible accessors."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True, validate_assignment=True)

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_name: Literal["qcschema_output"] = "qcschema_output"
    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
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

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

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


# MolSSI QCSchema Aliases
AtomicResult = QCResultsRecord
QCSchemaOutput = QCResultsRecord


class MolecularTopology(BaseModel):
    """Molecular spatial coordinates standardized to flat 1D arrays or 2D coordinate lists with explicit unit tagging."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    symbols: List[str] = Field(..., description="Ordered IUPAC elemental symbols")
    coordinates: Optional[List[List[float]]] = Field(default=None, description="2D Cartesian coordinate list (N x 3)")
    geometry: Optional[List[float]] = Field(default=None, description="Flat 1D atomic Cartesian coordinates (size 3*N)")
    units: Literal["bohr", "angstrom"] = Field(default="bohr", description="Physical coordinate unit")
    molecular_charge: int = Field(default=0, description="Net molecular charge")
    spin_multiplicity: int = Field(default=1, description="Spin multiplicity (2S + 1)")

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

    @field_validator("coordinates", mode="after")
    @classmethod
    def validate_coordinates_shape(cls, v: Optional[List[List[float]]]) -> Optional[List[List[float]]]:
        if v is None:
            return v
        for idx, atom_coord in enumerate(v):
            if len(atom_coord) != 3:
                raise CoordinateShapeError(
                    f"Atom index {idx} has dimensionality {len(atom_coord)}; expected exactly 3 (x, y, z).",
                    details={"atom_index": idx, "actual_len": len(atom_coord), "expected_len": 3},
                )
        return v

    @model_validator(mode="before")
    @classmethod
    def _validate_and_flatten_coords(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        symbols = data.get("symbols", [])
        coords = data.get("coordinates")
        geom = data.get("geometry")

        if coords is not None:
            if isinstance(coords, np.ndarray):
                coords = coords.tolist()
                data["coordinates"] = coords
            # Only synthesize geometry if all coordinate rows have valid length 3
            if geom is None and isinstance(coords, list):
                if all(isinstance(c, (list, tuple)) and len(c) == 3 for c in coords):
                    flat = []
                    for pt in coords:
                        flat.extend([float(c) for c in pt])
                    data["geometry"] = flat
        elif geom is not None:
            if isinstance(geom, np.ndarray):
                geom = geom.flatten().tolist()
            elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
                flat = []
                for pt in geom:
                    flat.extend([float(c) for c in pt])
                geom = flat
            elif isinstance(geom, list):
                geom = [float(c) for c in geom]
            data["geometry"] = geom

            n_atoms = len(symbols)
            if n_atoms > 0 and len(geom) != 3 * n_atoms:
                raise CoordinateShapeError(
                    f"Geometry coordinate dimension mismatch: expected {3 * n_atoms} components for {n_atoms} atoms, got {len(geom)}",
                    details={"actual_len": len(geom), "expected_len": 3 * n_atoms},
                )
            if "coordinates" not in data and len(geom) % 3 == 0:
                data["coordinates"] = [
                    geom[3 * i : 3 * i + 3] for i in range(len(geom) // 3)
                ]

        return data

    def to_angstrom(self) -> MolecularTopology:
        """Convert coordinates to Angstroms using authoritative CODATA 2022 constant."""
        if self.units == "angstrom":
            return self
        converted_geom = (
            [float(c * BOHR_TO_ANGSTROM) for c in self.geometry]
            if self.geometry is not None
            else None
        )
        converted_coords = (
            [[float(c * BOHR_TO_ANGSTROM) for c in pt] for pt in self.coordinates]
            if self.coordinates is not None
            else None
        )
        return MolecularTopology(
            schema_version=self.schema_version,
            symbols=list(self.symbols),
            geometry=converted_geom,
            coordinates=converted_coords,
            units="angstrom",
            molecular_charge=self.molecular_charge,
            spin_multiplicity=self.spin_multiplicity,
        )

    def to_bohr(self) -> MolecularTopology:
        """Convert coordinates to Bohr using authoritative CODATA 2022 constant."""
        if self.units == "bohr":
            return self
        converted_geom = (
            [float(c * ANGSTROM_TO_BOHR) for c in self.geometry]
            if self.geometry is not None
            else None
        )
        converted_coords = (
            [[float(c * ANGSTROM_TO_BOHR) for c in pt] for pt in self.coordinates]
            if self.coordinates is not None
            else None
        )
        return MolecularTopology(
            schema_version=self.schema_version,
            symbols=list(self.symbols),
            geometry=converted_geom,
            coordinates=converted_coords,
            units="bohr",
            molecular_charge=self.molecular_charge,
            spin_multiplicity=self.spin_multiplicity,
        )


class PESPointRecord(BaseModel):
    """Point record representing a single potential energy surface evaluation with deterministic UUIDv5 [D]."""

    model_config = ConfigDict(extra="allow", validate_assignment=True, arbitrary_types_allowed=True)

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
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
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

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
            schema_version=self.schema_version,
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
            schema_version=self.schema_version,
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

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique job identifier")
    molecule: Dict[str, Any] = Field(default_factory=dict, description="Target molecular topology specifications")
    driver: Literal["energy", "gradient", "hessian", "properties"] = "energy"
    fidelity: Union[CalculationFidelity, str] = Field(
        default=CalculationFidelity.R_DFT,
        description="Canonical fidelity tier or custom specification",
    )
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Calculation keywords")
    license: str = Field(default="CC-BY-4.0", description="SPDX license identifier")

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

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
    "CURRENT_CORE_SCHEMA_VERSION",
    "register_migration",
    "migrate_payload",
    "ThermodynamicsProvenance",
    "QCResultsRecord",
    "AtomicResult",
    "QCSchemaOutput",
    "MolecularTopology",
    "PESPointRecord",
    "CalculationJobPayload",
]
