"""# zero-stub anti-spoofing engine
CoChem-GEOM Engine & Pickett Pydantic v2 Schemas (schemas.py)
--------------------------------------------------------------
Strict Pydantic v2 typed BaseModel data models for Pickett spectroscopy parameters,
quantum chemistry input decks, optimization convergence thresholds, frozen-monomer
configurations, coordinate transformations, and execution telemetry.

Complies with Method Matrix v4, SWEBOK v3, and CoChem-GEOM WBS Task 3.3.3.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple, Union, cast

import numpy as np
from numpy.typing import NDArray
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class SchemaValidationError(ValueError):
    """Raised when structured data payload violates physics or schema constraints."""
    pass


class InvalidHessianStrategyError(ValueError):
    """Raised when an unapproved Hessian strategy (e.g. Calc_Hess true) is specified."""
    pass


class DispersionMissingError(ValueError):
    """Raised when DFT optimization of weak complexes lacks mandatory D3/D4 dispersion."""
    pass


class MalformedPickettPayloadError(ValueError):
    """Raised when Pickett spectroscopy payload contains invalid columns or data."""
    pass


class UnphysicalQuantumNumberError(ValueError):
    """Raised when quantum numbers violate angular momentum or parity rules."""
    pass


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TaskType(str, Enum):
    """Quantum chemistry and fitting workflow task types."""
    ENERGY = "ENERGY"
    GRADIENT = "GRADIENT"
    HESSIAN = "HESSIAN"
    OPT = "OPT"
    TIGHT_OPT = "TIGHT_OPT"
    OPT_FREQ = "OPT_FREQ"
    VPT2 = "VPT2"
    SCAN = "SCAN"
    CONSTRAINED_OPT = "CONSTRAINED_OPT"
    FROZEN_MONOMER_OPT = "FROZEN_MONOMER_OPT"
    ISOTOPOLOGUE_RECYCLE = "ISOTOPOLOGUE_RECYCLE"
    PICKETT_FIT = "PICKETT_FIT"
    SPECTRAL_PREDICTION = "SPECTRAL_PREDICTION"


class EngineType(str, Enum):
    """Supported quantum chemistry and computational engines."""
    ORCA = "ORCA"
    CFOUR = "CFOUR"
    XTB = "XTB"
    MPQC = "MPQC"
    PYSCF = "PYSCF"
    GAUSSIAN = "GAUSSIAN"
    MOLPRO = "MOLPRO"
    SPFIT = "SPFIT"
    SPCAT = "SPCAT"


class CalculationType(str, Enum):
    """Quantum chemistry calculation tasks (alias for TaskType)."""
    ENERGY = "ENERGY"
    GRADIENT = "GRADIENT"
    HESSIAN = "HESSIAN"
    OPT = "OPT"
    TIGHT_OPT = "TIGHT_OPT"
    OPT_FREQ = "OPT_FREQ"
    VPT2 = "VPT2"
    SCAN = "SCAN"
    CONSTRAINED_OPT = "CONSTRAINED_OPT"
    FROZEN_MONOMER_OPT = "FROZEN_MONOMER_OPT"


class HessianPreconditioner(str, Enum):
    """Initial model Hessian preconditioning strategies per Method Matrix v4 §8B.3."""
    XTB2 = "XTB2"
    LINDH = "LINDH"
    ALMLOF = "ALMLOF"
    READ = "READ"
    EXACT = "EXACT"
    NONE = "NONE"


ModelHessianType = HessianPreconditioner


class IntegrationGrid(str, Enum):
    """Integration grid fidelity levels for DFT methods per Method Matrix v4 §4.4."""
    DEFGRID1 = "DEFGRID1"
    DEFGRID2 = "DEFGRID2"
    DEFGRID3 = "DEFGRID3"
    AUTO = "AUTO"


class DispersionType(str, Enum):
    """Empirical dispersion corrections for DFT per Method Matrix v4 §4.2."""
    D3BJ = "D3BJ"
    D4 = "D4"
    D3ZERO = "D3ZERO"
    NONE = "NONE"


DispersionCorrection = DispersionType


class PickettReduction(str, Enum):
    """Pickett Hamiltonian reduction standard."""
    A = "A"
    S = "S"


class PickettRepresentation(str, Enum):
    """Pickett principal axis representation."""
    Ir = "Ir"
    IIr = "IIr"
    IIIr = "IIIr"
    Il = "Il"
    IIl = "IIl"
    IIIl = "IIIl"


class CoordinateType(str, Enum):
    """Coordinate system representations."""
    REDUNDANT = "redundant"
    CARTESIAN = "cartesian"
    INTERNAL = "internal"
    DLC = "dlc"
    FROZEN_MONOMER = "frozen_monomer"


class StructuralModel(str, Enum):
    """Molecular structure coordinate representation models."""
    R0 = "r0"
    RS = "rs"
    RZ = "rz"
    RM = "rm"
    RE_SE = "re_se"
    EQUILIBRIUM = "equilibrium"


class ProvenanceTag(str, Enum):
    """Scientific provenance categorization tags per Method Matrix v4 §15."""
    METHOD = "[M]"
    DATA = "[D]"
    ERROR = "[E]"
    MODEL = "[M]"
    DERIVED = "[D]"
    ESTIMATED = "[E]"
    MEASURED = "[M]"


ProvenanceTagType = ProvenanceTag


# ---------------------------------------------------------------------------
# Base Schema Configuration
# ---------------------------------------------------------------------------

class CoChemBaseModel(BaseModel):
    """Base schema enforcing Pydantic v2 strict configuration, serialization, and validation."""
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    def to_json(self, indent: int = 2) -> str:
        """Serialize schema to formatted JSON string."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> Any:
        """Parse schema from JSON string with strict validation."""
        return cls.model_validate_json(json_str)


CoChemBaseSchema = CoChemBaseModel


# ---------------------------------------------------------------------------
# Molecular Structure & Atom Coordinate Schemas
# ---------------------------------------------------------------------------

VALID_ELEMENTS: Set[str] = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "D", "T"
}

from mendeleev import element

class DynamicMassDict(dict):
    """Dynamically retrieves atomic and isotopic masses via mendeleev on demand."""
    def __getitem__(self, sym: str) -> float:
        return self.get_mass(sym)
        
    def __contains__(self, sym: object) -> bool:
        if not isinstance(sym, str):
            return False
        try:
            self.get_mass(sym)
            return True
        except Exception:
            return False
            
    def get(self, sym: str, default: Any = 12.0) -> Any:
        try:
            return self.get_mass(sym)
        except Exception:
            return default

    @staticmethod
    def get_mass(sym: str) -> float:
        clean_sym = sym.strip().capitalize()
        if clean_sym in ('D', '2H', 'H2'):
            el = element('H')
            for iso in el.isotopes:
                if iso.mass_number == 2 and iso.mass is not None:
                    return float(iso.mass)
        if clean_sym in ('T', '3H', 'H3'):
            el = element('H')
            for iso in el.isotopes:
                if iso.mass_number == 3 and iso.mass is not None:
                    return float(iso.mass)
        iso_match = re.match(r'^(\d+)([A-Za-z]+)$', clean_sym)
        if iso_match:
            iso_num = int(iso_match.group(1))
            sym_name = iso_match.group(2).capitalize()
            el = element(sym_name)
            for iso in el.isotopes:
                if iso.mass_number == iso_num and iso.mass is not None:
                    return float(iso.mass)
            if el.mass is not None:
                return float(el.mass)
        el = element(clean_sym)
        if el.mass is not None:
            return float(el.mass)
        raise ValueError(f"Could not retrieve dynamic mass for element '{sym}'")

STANDARD_ATOMIC_MASSES: Dict[str, float] = DynamicMassDict()


class AtomCoordinate(CoChemBaseModel):
    """Cartesian coordinate for a single atom."""
    symbol: str = Field(alias="element", default="H", description="Chemical element symbol or isotope notation")
    x: float = Field(description="X coordinate in Angstroms")
    y: float = Field(description="Y coordinate in Angstroms")
    z: float = Field(description="Z coordinate in Angstroms")
    mass: Optional[float] = Field(alias="mass_amu", default=None, ge=0.0, description="Atomic mass in amu")
    atom_index: Optional[int] = Field(default=None, ge=0, description="0-indexed atom position in molecule")

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_element_symbol(cls, v: Any) -> str:
        clean = str(v).strip()
        elem_match = re.search(r"([A-Z][a-z]?|D|T)$", clean)
        if not elem_match or elem_match.group(1) not in VALID_ELEMENTS:
            raise SchemaValidationError(f"Invalid chemical element symbol: '{v}'. Must be a valid element.")
        return clean

    @model_validator(mode="after")
    def populate_mass_if_missing(self) -> "AtomCoordinate":
        if self.mass is None:
            mass_val = STANDARD_ATOMIC_MASSES.get(self.symbol, None)
            if mass_val is None:
                elem_core = re.search(r"([A-Z][a-z]?|D|T)$", self.symbol)
                key = elem_core.group(1) if elem_core else self.symbol
                mass_val = STANDARD_ATOMIC_MASSES.get(key, 12.0)
            object.__setattr__(self, "mass", mass_val)
        return self

    @property
    def element(self) -> str:
        return self.symbol

    @property
    def mass_amu(self) -> Optional[float]:
        return self.mass

    def to_tuple(self) -> Tuple[str, float, float, float]:
        return (self.symbol, self.x, self.y, self.z)


class MolecularGeometry(CoChemBaseModel):
    """Complete molecular structure definition with atomic coordinates."""
    species_id: str = Field(alias="name", default="molecule", description="Identifier for chemical species")
    atoms: List[AtomCoordinate] = Field(default_factory=list, description="Ordered list of atom coordinates")
    charge: int = Field(default=0, description="Total molecular charge")
    multiplicity: int = Field(alias="spin_multiplicity", default=1, ge=1, description="Spin multiplicity (2S + 1)")
    point_group: Optional[str] = Field(default=None, description="Symmetry point group (e.g. C2v, Cs, C1)")
    is_weak_complex: bool = Field(default=False, description="True if structure is a weak non-covalent complex")
    comment: Optional[str] = Field(default=None, description="Optional metadata description")
    provenance_tag: Optional[str] = Field(default="[M]", description="Scientific provenance tag")

    @property
    def name(self) -> str:
        return self.species_id

    @property
    def spin_multiplicity(self) -> int:
        return self.multiplicity

    @property
    def num_atoms(self) -> int:
        return len(self.atoms)

    @property
    def total_mass(self) -> float:
        return sum((atom.mass or 0.0) for atom in self.atoms)

    def atomic_masses(self) -> List[float]:
        return [(atom.mass or 0.0) for atom in self.atoms]

    def coordinates_array(self) -> NDArray[np.float64]:
        return np.array([[atom.x, atom.y, atom.z] for atom in self.atoms], dtype=np.float64)

    @property
    def coordinates_matrix(self) -> List[List[float]]:
        return [[atom.x, atom.y, atom.z] for atom in self.atoms]

    @property
    def elements(self) -> List[str]:
        return [atom.symbol for atom in self.atoms]

    def to_xyz_string(self) -> str:
        lines = [str(len(self.atoms)), f"{self.species_id} {self.comment or ''}".strip()]
        for atom in self.atoms:
            lines.append(f"{atom.symbol:<4} {atom.x:14.8f} {atom.y:14.8f} {atom.z:14.8f}")
        return "\n".join(lines)

    @classmethod
    def from_xyz_string(cls, xyz_str: str, species_id: str = "molecule") -> "MolecularGeometry":
        lines = [line.strip() for line in xyz_str.strip().splitlines() if line.strip()]
        if len(lines) < 3:
            raise SchemaValidationError("XYZ payload must contain atom count, comment line, and >= 1 atom lines.")
        try:
            num_atoms = int(lines[0])
        except ValueError as err:
            raise SchemaValidationError(f"Invalid XYZ atom count header: '{lines[0]}'") from err

        comment = lines[1]
        atom_list: List[AtomCoordinate] = []
        for idx, line in enumerate(lines[2 : 2 + num_atoms]):
            parts = line.split()
            if len(parts) < 4:
                raise SchemaValidationError(f"Malformed XYZ atom coordinate line {idx + 3}: '{line}'")
            elem = parts[0]
            try:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            except ValueError as err:
                raise SchemaValidationError(f"Non-numeric coordinates on line {idx + 3}: '{line}'") from err
            atom_list.append(AtomCoordinate(element=elem, x=x, y=y, z=z, atom_index=idx))

        return cls(name=species_id, atoms=atom_list, comment=comment)


MolecularStructure = MolecularGeometry


# ---------------------------------------------------------------------------
# Pickett Spectroscopy Schemas
# ---------------------------------------------------------------------------

class PickettQuantumNumbers(CoChemBaseModel):
    """Quantum numbers for an asymmetric rotor state or transition."""
    j_upper: int = Field(ge=0, description="Upper state total angular momentum J' (>= 0)")
    ka_upper: int = Field(ge=0, description="Upper state prolate projection Ka' (0 <= Ka <= J)")
    kc_upper: int = Field(ge=0, description="Upper state oblate projection Kc' (0 <= Kc <= J)")
    j_lower: int = Field(default=0, ge=0, description="Lower state total angular momentum J'' (>= 0)")
    ka_lower: int = Field(default=0, ge=0, description="Lower state prolate projection Ka'' (0 <= Ka <= J)")
    kc_lower: int = Field(default=0, ge=0, description="Lower state oblate projection Kc'' (0 <= Kc <= J)")
    v: Optional[int] = Field(default=0, ge=0, description="Vibrational state index")
    f: Optional[float] = Field(default=None, ge=0.0, description="Total angular momentum F")
    f1: Optional[float] = Field(default=None, ge=0.0, description="Intermediate coupling F1")

    @model_validator(mode="before")
    @classmethod
    def pre_populate_qn(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "j" in data and "j_upper" not in data:
                data["j_upper"] = data["j"]
            if "ka" in data and "ka_upper" not in data:
                data["ka_upper"] = data["ka"]
            if "kc" in data and "kc_upper" not in data:
                data["kc_upper"] = data["kc"]
        return data

    @model_validator(mode="after")
    def validate_quantum_bounds(self) -> "PickettQuantumNumbers":
        if self.ka_upper > self.j_upper:
            raise UnphysicalQuantumNumberError(
                f"Unphysical Ka'={self.ka_upper} exceeds J'={self.j_upper}. Invariant: Ka <= J."
            )
        if self.kc_upper > self.j_upper:
            raise UnphysicalQuantumNumberError(
                f"Unphysical Kc'={self.kc_upper} exceeds J'={self.j_upper}. Invariant: Kc <= J."
            )
        if self.ka_upper + self.kc_upper < self.j_upper or self.ka_upper + self.kc_upper > self.j_upper + 1:
            raise UnphysicalQuantumNumberError(
                f"Asymmetric rotor parity rule violated for upper state: J'={self.j_upper}, "
                f"Ka'={self.ka_upper}, Kc'={self.kc_upper}. Invariant: Ka + Kc in {{J, J+1}}."
            )

        if self.j_lower > 0 or self.ka_lower > 0 or self.kc_lower > 0:
            if self.ka_lower > self.j_lower:
                raise UnphysicalQuantumNumberError(
                    f"Unphysical Ka''={self.ka_lower} exceeds J''={self.j_lower}. Invariant: Ka <= J."
                )
            if self.kc_lower > self.j_lower:
                raise UnphysicalQuantumNumberError(
                    f"Unphysical Kc''={self.kc_lower} exceeds J''={self.j_lower}. Invariant: Kc <= J."
                )
            if self.ka_lower + self.kc_lower < self.j_lower or self.ka_lower + self.kc_lower > self.j_lower + 1:
                raise UnphysicalQuantumNumberError(
                    f"Asymmetric rotor parity rule violated for lower state: J''={self.j_lower}, "
                    f"Ka''={self.ka_lower}, Kc''={self.kc_lower}. Invariant: Ka + Kc in {{J, J+1}}."
                )
            delta_j = abs(self.j_upper - self.j_lower)
            if delta_j > 1:
                raise UnphysicalQuantumNumberError(
                    f"Electric dipole selection rule violated: |Delta J| = |{self.j_upper} - {self.j_lower}| = {delta_j} > 1."
                )
        return self

    @property
    def j(self) -> int:
        return self.j_upper

    @property
    def ka(self) -> int:
        return self.ka_upper

    @property
    def kc(self) -> int:
        return self.kc_upper


class PickettTransition(CoChemBaseModel):
    """Experimental or calculated rotational transition between two asymmetric rotor states."""
    species_id: str = Field(description="Isotopologue or chemical species identifier")
    quantum_numbers: Optional[PickettQuantumNumbers] = Field(
        default=None, description="Structured upper/lower state quantum numbers"
    )
    j_upper: Optional[int] = Field(default=None, ge=0)
    ka_upper: Optional[int] = Field(default=None, ge=0)
    kc_upper: Optional[int] = Field(default=None, ge=0)
    j_lower: Optional[int] = Field(default=None, ge=0)
    ka_lower: Optional[int] = Field(default=None, ge=0)
    kc_lower: Optional[int] = Field(default=None, ge=0)
    frequency_mhz: float = Field(gt=0.0, description="Observed transition frequency in MHz")
    uncertainty_mhz: float = Field(default=0.01, gt=0.0, description="Measurement uncertainty in MHz")
    calc_frequency_mhz: Optional[float] = Field(default=None, description="Calculated transition frequency in MHz")
    residual_mhz: Optional[float] = Field(default=None, description="Observed minus calculated residual in MHz")
    weight: float = Field(default=1.0, ge=0.0, description="Statistical weight in fitting")
    blend_group: Optional[int] = Field(default=None, description="Identifier for blended line groups")
    provenance_tag: Optional[str] = Field(default="[E]", description="Data provenance tag: [E] or [D]")
    source_file: Optional[str] = Field(default=None, description="Original source .lin or experimental file")

    @model_validator(mode="before")
    @classmethod
    def sync_quantum_numbers_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            qn = data.get("quantum_numbers")
            if isinstance(qn, dict):
                data.setdefault("j_upper", qn.get("j_upper"))
                data.setdefault("ka_upper", qn.get("ka_upper"))
                data.setdefault("kc_upper", qn.get("kc_upper"))
                data.setdefault("j_lower", qn.get("j_lower"))
                data.setdefault("ka_lower", qn.get("ka_lower"))
                data.setdefault("kc_lower", qn.get("kc_lower"))
            elif "j_upper" in data and qn is None:
                data["quantum_numbers"] = {
                    "j_upper": data.get("j_upper", 0),
                    "ka_upper": data.get("ka_upper", 0),
                    "kc_upper": data.get("kc_upper", 0),
                    "j_lower": data.get("j_lower", 0),
                    "ka_lower": data.get("ka_lower", 0),
                    "kc_lower": data.get("kc_lower", 0),
                }
        return data

    @model_validator(mode="after")
    def validate_transition(self) -> "PickettTransition":
        if self.quantum_numbers is not None:
            object.__setattr__(self, "j_upper", self.quantum_numbers.j_upper)
            object.__setattr__(self, "ka_upper", self.quantum_numbers.ka_upper)
            object.__setattr__(self, "kc_upper", self.quantum_numbers.kc_upper)
            object.__setattr__(self, "j_lower", self.quantum_numbers.j_lower)
            object.__setattr__(self, "ka_lower", self.quantum_numbers.ka_lower)
            object.__setattr__(self, "kc_lower", self.quantum_numbers.kc_lower)

        if self.j_upper is not None and self.j_lower is not None:
            delta_j = abs(self.j_upper - self.j_lower)
            if delta_j > 1:
                raise UnphysicalQuantumNumberError(
                    f"Electric dipole selection rule violated: |Delta J| = |{self.j_upper} - {self.j_lower}| = {delta_j} > 1."
                )

        if self.calc_frequency_mhz is not None and self.residual_mhz is None:
            object.__setattr__(self, "residual_mhz", self.frequency_mhz - self.calc_frequency_mhz)
        return self

    def format_pickett_lin_line(self) -> str:
        ju = self.j_upper or 0
        kau = self.ka_upper or 0
        kcu = self.kc_upper or 0
        jl = self.j_lower or 0
        kal = self.ka_lower or 0
        kcl = self.kc_lower or 0
        return f"{ju:3d}{kau:3d}{kcu:3d}{jl:3d}{kal:3d}{kcl:3d}  {self.frequency_mhz:15.4f}  {self.uncertainty_mhz:8.4f}"


class PickettRotationalConstants(CoChemBaseModel):
    """Primary principal rotational constants A, B, C and Ray's asymmetry parameter."""
    A_mhz: float = Field(gt=0.0, description="Rotational constant A in MHz")
    B_mhz: float = Field(gt=0.0, description="Rotational constant B in MHz")
    C_mhz: float = Field(gt=0.0, description="Rotational constant C in MHz")
    A_err_mhz: Optional[float] = Field(alias="u_A_mhz", default=0.0, ge=0.0, description="Standard error on A in MHz")
    B_err_mhz: Optional[float] = Field(alias="u_B_mhz", default=0.0, ge=0.0, description="Standard error on B in MHz")
    C_err_mhz: Optional[float] = Field(alias="u_C_mhz", default=0.0, ge=0.0, description="Standard error on C in MHz")
    provenance_tag: Optional[str] = Field(default="[E]", description="Provenance tag: [M], [D], [E]")

    @property
    def u_A_mhz(self) -> Optional[float]:
        return self.A_err_mhz

    @property
    def u_B_mhz(self) -> Optional[float]:
        return self.B_err_mhz

    @property
    def u_C_mhz(self) -> Optional[float]:
        return self.C_err_mhz

    @model_validator(mode="after")
    def validate_rotational_hierarchy(self) -> "PickettRotationalConstants":
        if not (self.A_mhz >= self.B_mhz >= self.C_mhz > 0):
            raise SchemaValidationError(
                f"Rotational constant hierarchy violated: A={self.A_mhz}, B={self.B_mhz}, C={self.C_mhz}. "
                f"Physical ordering mandates A >= B >= C > 0."
            )
        return self

    @property
    def ray_asymmetry_parameter(self) -> float:
        diff = self.A_mhz - self.C_mhz
        if abs(diff) < 1e-12:
            return 0.0
        return (2.0 * self.B_mhz - self.A_mhz - self.C_mhz) / diff


class PickettCentrifugalDistortion(CoChemBaseModel):
    """Centrifugal distortion parameters in Watson A or S reduction."""
    DJ_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion DJ in kHz")
    DJK_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion DJK in kHz")
    DK_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion DK in kHz")
    dJ_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion dJ in kHz")
    dK_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion dK in kHz")
    HJ_hz: Optional[float] = Field(default=None, description="Sextic centrifugal distortion HJ in Hz")
    HJK_hz: Optional[float] = Field(default=None, description="Sextic centrifugal distortion HJK in Hz")
    HKJ_hz: Optional[float] = Field(default=None, description="Sextic centrifugal distortion HKJ in Hz")
    HK_hz: Optional[float] = Field(default=None, description="Sextic centrifugal distortion HK in Hz")
    hJ_hz: Optional[float] = Field(default=None, description="Sextic centrifugal distortion hJ in Hz")
    hJK_hz: Optional[float] = Field(default=None, description="Sextic centrifugal distortion hJK in Hz")
    hK_hz: Optional[float] = Field(default=None, description="Sextic centrifugal distortion hK in Hz")


class PickettQuadrupoleTensor(CoChemBaseModel):
    """Nuclear quadrupole coupling tensor (e.g. 14N, 35Cl, 37Cl, 79Br, 81Br, 127I)."""
    nucleus: str = Field(default="14N", description="Target quadrupolar nucleus")
    chi_aa_mhz: float = Field(description="Quadrupole coupling component chi_aa in MHz")
    chi_bb_mhz: float = Field(description="Quadrupole coupling component chi_bb in MHz")
    chi_cc_mhz: float = Field(description="Quadrupole coupling component chi_cc in MHz")
    chi_ab_mhz: Optional[float] = Field(default=None, description="Off-diagonal quadrupole coupling chi_ab in MHz")
    chi_bc_mhz: Optional[float] = Field(default=None, description="Off-diagonal quadrupole coupling chi_bc in MHz")
    chi_ac_mhz: Optional[float] = Field(default=None, description="Off-diagonal quadrupole coupling chi_ac in MHz")

    @model_validator(mode="after")
    def validate_traceless(self) -> "PickettQuadrupoleTensor":
        trace = self.chi_aa_mhz + self.chi_bb_mhz + self.chi_cc_mhz
        if abs(trace) > 1e-3:
            raise SchemaValidationError(
                f"Traceless Laplace condition violated for quadrupole tensor: Tr(chi) = {trace:.6f} MHz != 0."
            )
        return self

    @property
    def eta(self) -> float:
        if abs(self.chi_aa_mhz) < 1e-12:
            return 0.0
        return (self.chi_bb_mhz - self.chi_cc_mhz) / self.chi_aa_mhz


class PickettDipoleComponents(CoChemBaseModel):
    """Electric dipole moment components in the Principal Axis System (PAS)."""
    mu_a_debye: float = Field(default=0.0, description="Dipole moment component mu_a in Debye")
    mu_b_debye: float = Field(default=0.0, description="Dipole moment component mu_b in Debye")
    mu_c_debye: float = Field(default=0.0, description="Dipole moment component mu_c in Debye")
    mu_total_debye: Optional[float] = Field(alias="total_debye", default=None, ge=0.0, description="Total dipole norm")

    @model_validator(mode="after")
    def compute_total_norm(self) -> "PickettDipoleComponents":
        calc_tot = math.sqrt(self.mu_a_debye ** 2 + self.mu_b_debye ** 2 + self.mu_c_debye ** 2)
        if self.mu_total_debye is None:
            object.__setattr__(self, "mu_total_debye", calc_tot)
        return self

    @property
    def total_debye(self) -> float:
        return self.mu_total_debye or math.sqrt(self.mu_a_debye ** 2 + self.mu_b_debye ** 2 + self.mu_c_debye ** 2)


class PickettParameter(CoChemBaseModel):
    """Single spectroscopic parameter in a Pickett SPFIT/SPCAT effective Hamiltonian."""
    param_id: int = Field(
        description="Pickett integer parameter code (e.g. 10000 for A, 20000 for B, 30000 for C, 200 for DJ)"
    )
    name: str = Field(description="Canonical parameter identifier (e.g. A, B, C, DJ, DJK, DK, dJ, dK, chi_aa)")
    value: float = Field(description="Parameter value (typically in MHz or MHz*cm)")
    uncertainty: float = Field(default=0.0, ge=0.0, description="Estimated standard uncertainty (1-sigma) in MHz")
    fit_flag: int = Field(default=1, description="1 to float during least-squares fit, 0 to hold fixed")
    fixed: bool = Field(default=False, description="True if parameter is fixed")
    unit: str = Field(default="MHz", description="Physical unit of parameter")
    description: Optional[str] = Field(default=None, description="Human-readable description of constant")
    species_id: Optional[str] = Field(default=None, description="Associated isotopologue species ID")

    def format_pickett_line(self) -> str:
        return f"{self.param_id:>10d}  {self.value:18.8E}  {self.uncertainty:14.6E}"


class PickettDeckSchema(CoChemBaseModel):
    """Complete Pickett SPFIT/SPCAT parameter deck and transition dataset."""
    title: str = Field(default="CoChem-GEOM Spectroscopic Fit", description="Title line for .par deck")
    species_id: str = Field(default="molecule", description="Target molecule or isotopologue species ID")
    reduction: PickettReduction | str = Field(default=PickettReduction.A, description="Watson reduction: A or S")
    representation: PickettRepresentation | str = Field(
        default=PickettRepresentation.Ir, description="Principal axis representation: Ir, IIr, IIIr, etc."
    )
    n_params: int = Field(default=0, ge=0, description="Number of parameters")
    n_lines: int = Field(default=0, ge=0, description="Number of fitted lines")
    max_j: Optional[int] = Field(default=None, ge=0, description="Maximum J state")
    parameters: List[PickettParameter] = Field(default_factory=list, description="Spectroscopic parameters")
    transitions: List[PickettTransition] = Field(default_factory=list, description="Assigned transition lines")
    rotational_constants: Optional[PickettRotationalConstants] = Field(
        default=None, description="Ingested rotational constants A, B, C"
    )
    temperature_k: float = Field(default=298.15, gt=0.0, description="Rotational temperature in Kelvin")
    spfit_chi_squared: Optional[float] = Field(default=None, ge=0.0, description="Reduced chi-squared")
    spfit_rms_mhz: Optional[float] = Field(default=None, ge=0.0, description="Root-mean-square residual in MHz")
    provenance_tag: Optional[str] = Field(default="[E]", description="Provenance annotation")

    def format_par_text(self) -> str:
        lines = [
            f"{self.title} [{self.species_id}]",
            f" {len(self.parameters):d}  {len(self.transitions):d}   0   0   0   0   0   0   0   0",
            f" 1.0  0.0  0.0  0.0  0.0",
        ]
        for param in self.parameters:
            lines.append(param.format_pickett_line())
        return "\n".join(lines) + "\n"

    def format_lin_text(self) -> str:
        lines = []
        for trans in self.transitions:
            lines.append(trans.format_pickett_lin_line())
        return "\n".join(lines) + "\n"


PickettDeck = PickettDeckSchema


class InertialParameters(CoChemBaseModel):
    """Inertial moments, planar moments, and defect kinematics."""
    I_a_amu_a2: float = Field(alias="I_a_amu_ang2", gt=0.0, description="Moment of inertia Ia in amu*Angstrom^2")
    I_b_amu_a2: float = Field(alias="I_b_amu_ang2", gt=0.0, description="Moment of inertia Ib in amu*Angstrom^2")
    I_c_amu_a2: float = Field(alias="I_c_amu_ang2", gt=0.0, description="Moment of inertia Ic in amu*Angstrom^2")
    inertial_defect_amu_a2: float = Field(alias="inertial_defect_amu_ang2", description="Inertial defect Delta in amu*Angstrom^2")
    P_aa_amu_a2: Optional[float] = Field(default=None, description="Planar moment Paa in amu*Angstrom^2")
    P_bb_amu_a2: Optional[float] = Field(default=None, description="Planar moment Pbb in amu*Angstrom^2")
    P_cc_amu_a2: Optional[float] = Field(default=None, description="Planar moment Pcc in amu*Angstrom^2")
    planar_moments_amu_ang2: Optional[Tuple[float, float, float]] = Field(default=None)
    A_mhz: Optional[float] = Field(default=None, gt=0.0)
    B_mhz: Optional[float] = Field(default=None, gt=0.0)
    C_mhz: Optional[float] = Field(default=None, gt=0.0)
    kappa: float = Field(default=0.0, description="Ray's asymmetry parameter kappa")

    @property
    def I_a_amu_ang2(self) -> float:
        return self.I_a_amu_a2

    @property
    def I_b_amu_ang2(self) -> float:
        return self.I_b_amu_a2

    @property
    def I_c_amu_ang2(self) -> float:
        return self.I_c_amu_a2

    @property
    def inertial_defect_amu_ang2(self) -> float:
        return self.inertial_defect_amu_a2

    @model_validator(mode="after")
    def validate_inertial_hierarchy(self) -> "InertialParameters":
        if not (0 < self.I_a_amu_a2 <= self.I_b_amu_a2 <= self.I_c_amu_a2):
            raise SchemaValidationError(
                f"Principal moment of inertia hierarchy violated: Ia={self.I_a_amu_a2}, "
                f"Ib={self.I_b_amu_a2}, Ic={self.I_c_amu_a2}. Must be 0 < Ia <= Ib <= Ic."
            )
        if self.P_aa_amu_a2 is None:
            object.__setattr__(self, "P_aa_amu_a2", 0.5 * (-self.I_a_amu_a2 + self.I_b_amu_a2 + self.I_c_amu_a2))
        if self.P_bb_amu_a2 is None:
            object.__setattr__(self, "P_bb_amu_a2", 0.5 * (self.I_a_amu_a2 - self.I_b_amu_a2 + self.I_c_amu_a2))
        if self.P_cc_amu_a2 is None:
            object.__setattr__(self, "P_cc_amu_a2", 0.5 * (self.I_a_amu_a2 + self.I_b_amu_a2 - self.I_c_amu_a2))
        return self


class SpectroscopicConstants(CoChemBaseModel):
    """Complete, verified spectroscopic constant table."""
    species_id: str = Field(description="Identifier for molecule or isotopologue")
    A_mhz: float = Field(gt=0.0, description="Rotational constant A in MHz")
    B_mhz: float = Field(gt=0.0, description="Rotational constant B in MHz")
    C_mhz: float = Field(gt=0.0, description="Rotational constant C in MHz")
    A_err_mhz: Optional[float] = Field(default=None, ge=0.0, description="Standard error on A in MHz")
    B_err_mhz: Optional[float] = Field(default=None, ge=0.0, description="Standard error on B in MHz")
    C_err_mhz: Optional[float] = Field(default=None, ge=0.0, description="Standard error on C in MHz")
    DJ_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion DJ in kHz")
    DJK_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion DJK in kHz")
    DK_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion DK in kHz")
    dJ_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion dJ in kHz")
    dK_khz: Optional[float] = Field(default=None, description="Quartic centrifugal distortion dK in kHz")
    chi_aa_mhz: Optional[float] = Field(default=None, description="14N quadrupole coupling component chi_aa in MHz")
    chi_bb_mhz: Optional[float] = Field(default=None, description="14N quadrupole coupling component chi_bb in MHz")
    chi_cc_mhz: Optional[float] = Field(default=None, description="14N quadrupole coupling component chi_cc in MHz")
    chi_ab_mhz: Optional[float] = Field(default=None, description="Off-diagonal quadrupole coupling chi_ab in MHz")
    chi_bc_mhz: Optional[float] = Field(default=None, description="Off-diagonal quadrupole coupling chi_bc in MHz")
    chi_ac_mhz: Optional[float] = Field(default=None, description="Off-diagonal quadrupole coupling chi_ac in MHz")
    dipole_a_debye: Optional[float] = Field(default=None, description="Dipole moment component mu_a in Debye")
    dipole_b_debye: Optional[float] = Field(default=None, description="Dipole moment component mu_b in Debye")
    dipole_c_debye: Optional[float] = Field(default=None, description="Dipole moment component mu_c in Debye")
    dipole_total_debye: Optional[float] = Field(default=None, ge=0.0, description="Total dipole moment in Debye")
    kappa: Optional[float] = Field(default=None, description="Ray's asymmetry parameter kappa = (2B - A - C)/(A - C)")
    inertial_defect_amu_a2: Optional[float] = Field(
        default=None, description="Inertial defect Delta = Ic - Ia - Ib in amu*Angstrom^2"
    )
    P_aa_amu_a2: Optional[float] = Field(default=None, description="Planar moment P_aa in amu*Angstrom^2")
    P_bb_amu_a2: Optional[float] = Field(default=None, description="Planar moment P_bb in amu*Angstrom^2")
    P_cc_amu_a2: Optional[float] = Field(default=None, description="Planar moment P_cc in amu*Angstrom^2")
    is_isotopologue: bool = Field(default=False, description="True if non-parent isotopologue")
    abundance_pct: float = Field(default=100.0, ge=0.0, le=100.0, description="Natural isotopic abundance percentage")

    @model_validator(mode="after")
    def validate_rotational_hierarchy(self) -> "SpectroscopicConstants":
        if not (self.A_mhz >= self.B_mhz >= self.C_mhz > 0):
            raise SchemaValidationError(
                f"Rotational constant hierarchy violated: A={self.A_mhz}, B={self.B_mhz}, C={self.C_mhz}. "
                f"Physical ordering mandates A >= B >= C > 0."
            )
        if self.kappa is None and (self.A_mhz - self.C_mhz) > 1e-9:
            object.__setattr__(self, "kappa", (2.0 * self.B_mhz - self.A_mhz - self.C_mhz) / (self.A_mhz - self.C_mhz))
        return self


# ---------------------------------------------------------------------------
# Optimization Settings & Convergence Criteria Schemas
# ---------------------------------------------------------------------------

class ConvergenceThresholds(CoChemBaseModel):
    """Method Matrix v4 tightened geometry optimization convergence thresholds (§4.4, §8B)."""
    tol_e: float = Field(default=1e-7, gt=0.0, description="Energy change convergence threshold in Hartree")
    tol_maxg: float = Field(alias="tol_max_g", default=1e-5, gt=0.0, description="Max gradient threshold in Hartree/Bohr")
    tol_rmsg: float = Field(alias="tol_rms_g", default=3e-6, gt=0.0, description="RMS gradient threshold in Hartree/Bohr")
    tol_maxd: float = Field(alias="tol_max_d", default=1e-4, gt=0.0, description="Max displacement threshold in Bohr")
    tol_rmsd: float = Field(alias="tol_rms_d", default=5e-5, gt=0.0, description="RMS displacement threshold in Bohr")
    tight_mode: bool = Field(default=True, description="Tightened convergence enforcement")

    @property
    def tol_max_g(self) -> float:
        return self.tol_maxg

    @property
    def tol_rms_g(self) -> float:
        return self.tol_rmsg

    @property
    def tol_max_d(self) -> float:
        return self.tol_maxd

    @property
    def tol_rms_d(self) -> float:
        return self.tol_rmsd

    @model_validator(mode="after")
    def validate_convergence_hierarchy(self) -> "ConvergenceThresholds":
        if self.tol_maxg < self.tol_rmsg:
            raise SchemaValidationError(
                f"Convergence gradient threshold violation: tol_maxg ({self.tol_maxg}) < tol_rmsg ({self.tol_rmsg})."
            )
        if self.tol_maxd < self.tol_rmsd:
            raise SchemaValidationError(
                f"Convergence displacement threshold violation: tol_maxd ({self.tol_maxd}) < tol_rmsd ({self.tol_rmsd})."
            )
        return self

    def format_orca_geom_block(self) -> str:
        return (
            f"  TolE    {self.tol_e:.1E}\n"
            f"  TolRMSG {self.tol_rmsg:.1E}\n"
            f"  TolMaxG {self.tol_maxg:.1E}\n"
            f"  TolRMSD {self.tol_rmsd:.1E}\n"
            f"  TolMaxD {self.tol_maxd:.1E}"
        )


ConvergenceCriteria = ConvergenceThresholds


class FrozenMonomerSettings(CoChemBaseModel):
    """Frozen-Monomer Protocol parameters for weak intermolecular complex optimizations (§9A.1)."""
    enabled: bool = Field(default=True, description="Whether Frozen-Monomer Protocol is active")
    fragment_indices: List[List[int]] = Field(
        default_factory=list, description="Disjoint atom index sets for each monomer"
    )
    frozen_monomer_coordinates: Optional[List[int]] = Field(
        default=None, description="Frozen internal coordinate indices"
    )
    monomer_a_indices: List[int] = Field(default_factory=list, description="0-indexed atom indices in monomer A")
    monomer_b_indices: List[int] = Field(default_factory=list, description="0-indexed atom indices in monomer B")
    intermolecular_r_angstrom: Optional[float] = Field(default=None, gt=0.0, description="Intermolecular distance R (Ang)")
    intermolecular_theta_deg: Optional[float] = Field(default=None, ge=0.0, le=180.0, description="Angle theta (deg)")
    intermolecular_phi_deg: Optional[float] = Field(default=None, ge=-180.0, le=360.0, description="Angle phi (deg)")
    intermolecular_tau1_deg: Optional[float] = Field(default=None, ge=-180.0, le=360.0, description="Dihedral tau1 (deg)")
    intermolecular_tau2_deg: Optional[float] = Field(default=None, ge=-180.0, le=360.0, description="Dihedral tau2 (deg)")
    intermolecular_tau3_deg: Optional[float] = Field(default=None, ge=-180.0, le=360.0, description="Dihedral tau3 (deg)")
    freeze_intramolecular_internals: bool = Field(
        default=True, description="Lock intramolecular monomer internal coordinates at equilibrium"
    )
    residual_gradient_tolerance: float = Field(
        default=1e-5, gt=0.0, description="Projected residual gradient tolerance on frozen coordinates"
    )

    @model_validator(mode="after")
    def validate_disjoint_fragments(self) -> "FrozenMonomerSettings":
        if self.fragment_indices:
            seen_indices: Set[int] = set()
            for frag in self.fragment_indices:
                for idx in frag:
                    if idx in seen_indices:
                        raise SchemaValidationError(
                            f"Overlapping fragment index {idx} in FrozenMonomerSettings: {self.fragment_indices}"
                        )
                    seen_indices.add(idx)
        return self


class BoundsAutotuningSettings(CoChemBaseModel):
    """Automated dynamic parameter bounds tuning settings for nonlinear fitting."""
    enabled: bool = Field(default=True, description="Enable automatic parameter bound expansion")
    bond_max_scale: float = Field(
        alias="max_bond_stretch_factor", default=1.3, gt=1.0, description="Max allowed bond stretch scale"
    )
    bond_min_scale: float = Field(
        alias="min_bond_compress_factor", default=0.7, gt=0.0, description="Min allowed bond compression scale"
    )
    min_angle_deg: float = Field(default=20.0, ge=0.0, description="Minimum allowed valence angle")
    max_angle_deg: float = Field(default=175.0, le=180.0, description="Maximum allowed valence angle")
    min_absolute_bond_angstrom: Optional[float] = Field(default=0.5, gt=0.0)
    max_absolute_bond_angstrom: Optional[float] = Field(default=5.0, gt=0.0)

    @property
    def max_bond_stretch_factor(self) -> float:
        return self.bond_max_scale

    @property
    def min_bond_compress_factor(self) -> float:
        return self.bond_min_scale

    @model_validator(mode="after")
    def validate_bond_range(self) -> "BoundsAutotuningSettings":
        if (
            self.min_absolute_bond_angstrom is not None
            and self.max_absolute_bond_angstrom is not None
            and self.min_absolute_bond_angstrom >= self.max_absolute_bond_angstrom
        ):
            raise SchemaValidationError(
                f"Invalid bond bounds: min ({self.min_absolute_bond_angstrom}) >= max ({self.max_absolute_bond_angstrom})."
            )
        return self


class MultiSeedOptimizationSettings(CoChemBaseModel):
    """Multi-seed stochastic and deterministic optimizer settings."""
    num_seeds: int = Field(default=50, ge=1, description="Number of random starting seeds")
    random_seed: Optional[int] = Field(default=42, description="Random number generator seed")
    perturbation_scale_angstrom: float = Field(default=0.1, gt=0.0, description="Coordinate perturbation magnitude")
    trust_radius_bohr: float = Field(default=0.3, gt=0.0, description="Initial trust radius in Bohr")
    svd_condition_threshold: float = Field(default=1e5, gt=1.0, description="SVD fallback threshold")


class OptimizationSettings(CoChemBaseModel):
    """Full optimization configuration payload governing structural relaxation."""
    max_iterations: int = Field(default=100, ge=1, le=10000, description="Maximum geometry optimization iterations")
    optimizer_algorithm: str = Field(default="TRF", description="Optimizer algorithm: TRF, RFO, BFGS, L-BFGS, SVD")
    coordinate_system: CoordinateType = Field(
        default=CoordinateType.REDUNDANT, description="Coordinate system for internal optimization"
    )
    structural_model: StructuralModel = Field(
        default=StructuralModel.EQUILIBRIUM, description="Structural estimation target (r0, rs, rz, rm, re_se)"
    )
    convergence: ConvergenceThresholds = Field(
        default_factory=ConvergenceThresholds, description="Convergence criteria metrics"
    )
    inhess: str = Field(
        alias="model_hessian", default="XTB2", description="Initial model Hessian preconditioning: XTB2, Lindh, Almlöf"
    )
    grid_ladder: List[IntegrationGrid] = Field(
        default=[IntegrationGrid.DEFGRID1, IntegrationGrid.DEFGRID3],
        description="Two-stage loose-to-tight numerical integration grid sequence",
    )
    is_weak_complex: bool = Field(default=False, description="Flag indicating non-covalent or weakly bound system")
    frozen_monomer: FrozenMonomerSettings = Field(
        default_factory=FrozenMonomerSettings, description="Frozen-Monomer Protocol settings"
    )
    bounds_tuning: BoundsAutotuningSettings = Field(
        default_factory=BoundsAutotuningSettings, description="Bounds autotuning configuration"
    )
    multi_seed: MultiSeedOptimizationSettings = Field(
        default_factory=MultiSeedOptimizationSettings, description="Multi-seed fitting configuration"
    )
    enforce_inertial_defect_gate: bool = Field(
        default=True, description="Reject candidate geometry if sign(Delta_calc) != sign(Delta_exp)"
    )
    enforce_planar_hierarchy_gate: bool = Field(
        default=True, description="Reject candidate geometry if planar moment ordering Paa > Pbb > Pcc is violated"
    )

    @field_validator("inhess", mode="before")
    @classmethod
    def reject_calc_hess_true(cls, v: Any) -> str:
        val_str = v.value if isinstance(v, HessianPreconditioner) else str(v).strip()
        clean = val_str.upper()
        if "CALC_HESS TRUE" in clean or "CALC_HESS=TRUE" in clean or clean == "EXACT":
            raise InvalidHessianStrategyError(
                "Method Matrix v4 §8B.3 Violation: Calc_Hess true / EXACT initial Hessians are strictly prohibited "
                "in geometry optimizations. Use XTB2 or Lindh."
            )
        return val_str

    @property
    def model_hessian(self) -> HessianPreconditioner:
        try:
            return HessianPreconditioner(self.inhess.upper())
        except ValueError:
            return HessianPreconditioner.XTB2


OptimizationConfig = OptimizationSettings


# ---------------------------------------------------------------------------
# Quantum Chemistry Input Deck Schemas
# ---------------------------------------------------------------------------

class CartesianConstraint(CoChemBaseModel):
    """Cartesian coordinate freeze constraint for an individual atom."""
    atom_index: int = Field(ge=0, description="0-indexed atom number to constrain")
    freeze_x: bool = Field(default=True, description="Freeze X Cartesian coordinate")
    freeze_y: bool = Field(default=True, description="Freeze Y Cartesian coordinate")
    freeze_z: bool = Field(default=True, description="Freeze Z Cartesian coordinate")

    def format_orca(self) -> str:
        return f"{{ C {self.atom_index:d} C }}"


class InternalConstraint(CoChemBaseModel):
    """Internal coordinate (bond, angle, dihedral) constraint."""
    constraint_type: Literal["BOND", "ANGLE", "DIHEDRAL"] = Field(description="Type of internal coordinate")
    atoms: List[int] = Field(description="Ordered list of 0-indexed atom numbers")
    target_value: Optional[float] = Field(default=None, description="Target value (Angstroms or degrees)")
    is_frozen: bool = Field(default=True, description="Whether internal coordinate is fixed")

    @model_validator(mode="after")
    def validate_atom_count(self) -> "InternalConstraint":
        expected = {"BOND": 2, "ANGLE": 3, "DIHEDRAL": 4}[self.constraint_type]
        if len(self.atoms) != expected:
            raise SchemaValidationError(
                f"{self.constraint_type} constraint requires exactly {expected} atom indices, got {len(self.atoms)}."
            )
        if len(set(self.atoms)) != len(self.atoms):
            raise SchemaValidationError(f"Duplicate atom indices in internal constraint: {self.atoms}.")
        return self

    def format_orca(self) -> str:
        letter = {"BOND": "B", "ANGLE": "A", "DIHEDRAL": "D"}[self.constraint_type]
        atom_str = " ".join(str(idx) for idx in self.atoms)
        if self.target_value is not None:
            return f"{{ {letter} {atom_str} {self.target_value:.6f} C }}"
        return f"{{ {letter} {atom_str} C }}"


class ORCAInputDeckSchema(CoChemBaseModel):
    """Complete ORCA 6.x calculation input deck specification adhering to Method Matrix v4."""
    method: str = Field(default="wB97X-V", description="Electronic structure method")
    basis: str = Field(default="def2-TZVP", description="Primary basis set")
    aux_basis: Optional[str] = Field(default=None, description="Auxiliary basis set")
    task_type: TaskType = Field(alias="task", default=TaskType.OPT, description="Calculation mode: opt, freq, sp, vpt2")
    charge: int = Field(default=0, description="Total molecular charge")
    multiplicity: int = Field(alias="mult", default=1, ge=1, description="Spin multiplicity")
    geometry: Optional[MolecularGeometry] = Field(default=None, description="Molecular geometry")
    raw_coordinates: Optional[str] = Field(alias="geometry_xyz", default=None, description="Raw coordinate block")
    inhess: str = Field(
        alias="model_hessian", default="XTB2", description="Model Hessian: XTB2, Lindh, Almlöf"
    )
    grid: IntegrationGrid | str = Field(default=IntegrationGrid.DEFGRID2, description="DFT numerical integration grid")
    dispersion: DispersionType | str = Field(default=DispersionType.NONE, description="Empirical dispersion model")
    tight_opt: bool = Field(default=False, description="Enable ! TightOpt in ORCA")
    is_weak_complex: bool = Field(default=False, description="Flag indicating weak non-covalent complex")
    nprocs: int = Field(default=4, ge=1, description="Parallel threads")
    maxcore_mb: int = Field(default=4000, ge=256, description="Memory per core in MB")
    cartesian_constraints: List[CartesianConstraint] = Field(default_factory=list, description="Cartesian constraints")
    internal_constraints: List[InternalConstraint] = Field(default_factory=list, description="Internal constraints")
    convergence: Optional[ConvergenceThresholds] = Field(default=None, description="Convergence criteria")
    extra_keywords: List[str] = Field(default_factory=list, description="Additional simple input keywords")
    extra_blocks: Dict[str, str] = Field(default_factory=dict, description="Additional structured block inputs")

    @field_validator("task_type", mode="before")
    @classmethod
    def validate_task_type(cls, v: Any) -> TaskType:
        if isinstance(v, TaskType):
            return v
        val_str = str(v).strip().upper()
        mapping = {
            "OPT": TaskType.OPT,
            "TIGHT_OPT": TaskType.TIGHT_OPT,
            "FREQ": TaskType.HESSIAN,
            "HESSIAN": TaskType.HESSIAN,
            "VPT2": TaskType.VPT2,
            "SP": TaskType.ENERGY,
            "ENERGY": TaskType.ENERGY,
            "GRADIENT": TaskType.GRADIENT,
            "CONSTRAINED_OPT": TaskType.CONSTRAINED_OPT,
            "FROZEN_MONOMER_OPT": TaskType.FROZEN_MONOMER_OPT,
        }
        return mapping.get(val_str, TaskType.OPT)

    @field_validator("inhess", mode="before")
    @classmethod
    def validate_inhess(cls, v: Any) -> str:
        val_str = v.value if isinstance(v, HessianPreconditioner) else str(v).strip()
        clean = val_str.upper()
        if "CALC_HESS TRUE" in clean or "CALC_HESS=TRUE" in clean or clean == "EXACT":
            raise InvalidHessianStrategyError(
                "Method Matrix v4 §8B.3 Violation: Calc_Hess true / EXACT initial Hessians are strictly prohibited "
                "in geometry optimizations. Use XTB2 or Lindh."
            )
        return val_str

    @property
    def model_hessian(self) -> HessianPreconditioner:
        try:
            return HessianPreconditioner(self.inhess.upper())
        except ValueError:
            return HessianPreconditioner.XTB2

    @model_validator(mode="after")
    def validate_method_matrix_rules(self) -> "ORCAInputDeckSchema":
        all_kw_str = " ".join(self.extra_keywords).lower()
        if "calc_hess true" in all_kw_str or "calc_hess=true" in all_kw_str:
            raise InvalidHessianStrategyError(
                "Method Matrix v4 §8B.3 Violation: Calc_Hess true detected in extra_keywords."
            )

        method_upper = self.method.upper()
        is_standard_dft = any(dft in method_upper for dft in ("B3LYP", "PBE", "M06", "BP86", "TPSS", "BLYP"))
        has_embedded_disp = any(disp in method_upper for disp in ("-V", "-3C", "-D3", "-D4", "D3BJ", "D4"))
        disp_val = self.dispersion.value if isinstance(self.dispersion, DispersionType) else str(self.dispersion)

        if is_standard_dft and self.is_weak_complex and not has_embedded_disp:
            if disp_val.upper() in ("NONE", ""):
                raise DispersionMissingError(
                    f"Method Matrix v4 §4.2 Mandate: DFT functional '{self.method}' for weak complexes requires explicit "
                    f"empirical dispersion (D3BJ or D4)."
                )

        for kw in self.extra_keywords:
            if kw.upper() in ("GRID3", "GRID5"):
                raise SchemaValidationError(
                    f"Method Matrix v4 §4.4 Violation: Deprecated '{kw}' keyword forbidden. Use DEFGRID1, DEFGRID2, or DEFGRID3."
                )

        return self

    def format_deck_string(self) -> str:
        kw_list = ["!"]
        kw_list.append(self.method)
        kw_list.append(self.basis)
        if self.aux_basis:
            kw_list.append(self.aux_basis)

        if self.task_type in (TaskType.OPT, TaskType.CONSTRAINED_OPT, TaskType.FROZEN_MONOMER_OPT):
            kw_list.append("TightOpt" if self.tight_opt else "Opt")
        elif self.task_type == TaskType.TIGHT_OPT:
            kw_list.append("TightOpt")
        elif self.task_type == TaskType.HESSIAN:
            kw_list.append("Freq")
        elif self.task_type == TaskType.VPT2:
            kw_list.append("AnFreq")

        grid_str = self.grid.value if isinstance(self.grid, IntegrationGrid) else str(self.grid)
        if grid_str.upper() != "AUTO":
            kw_list.append(grid_str)

        disp_str = self.dispersion.value if isinstance(self.dispersion, DispersionType) else str(self.dispersion)
        if disp_str.upper() != "NONE":
            kw_list.append(disp_str)

        for kw in self.extra_keywords:
            kw_list.append(kw)

        deck_lines = [" ".join(kw_list)]

        if self.nprocs > 1:
            deck_lines.append(f"%pal nprocs {self.nprocs:d} end")

        deck_lines.append(f"%maxcore {self.maxcore_mb:d}")

        geom_lines = ["%geom"]
        if self.inhess.upper() in ("XTB2", "LINDH", "ALMLOF"):
            geom_lines.append(f"  InHess {self.inhess}")

        if self.convergence:
            geom_lines.append(self.convergence.format_orca_geom_block())

        if self.cartesian_constraints or self.internal_constraints:
            geom_lines.append("  Constraints")
            for c_cart in self.cartesian_constraints:
                geom_lines.append(f"    {c_cart.format_orca()}")
            for c_int in self.internal_constraints:
                geom_lines.append(f"    {c_int.format_orca()}")
            geom_lines.append("  end")

        geom_lines.append("end")
        deck_lines.append("\n".join(geom_lines))

        for block_name, block_content in self.extra_blocks.items():
            deck_lines.append(f"%{block_name}\n{block_content}\nend")

        deck_lines.append(f"* xyz {self.charge:d} {self.multiplicity:d}")
        if self.geometry:
            for atom in self.geometry.atoms:
                deck_lines.append(f"  {atom.symbol:<4} {atom.x:14.8f} {atom.y:14.8f} {atom.z:14.8f}")
        elif self.raw_coordinates:
            deck_lines.append(self.raw_coordinates.strip())
        deck_lines.append("*")

        return "\n".join(deck_lines) + "\n"


QCDeck = ORCAInputDeckSchema


class CFOURInputDeckSchema(CoChemBaseModel):
    """CFOUR ZMAT input deck schema for analytic CCSD(T) second derivatives and sextic distortion."""
    method: str = Field(default="CCSD(T)", description="Correlated electronic structure method")
    basis: str = Field(default="ANO1", description="Basis set")
    geometry: Optional[MolecularGeometry] = Field(default=None, description="Molecular structure")
    geometry_zmat: Optional[str] = Field(default=None, description="ZMAT geometry specification text")
    charge: int = Field(default=0, description="Molecular charge")
    multiplicity: int = Field(alias="mult", default=1, ge=1, description="Spin multiplicity")
    derivative_order: int = Field(default=2, ge=0, le=2, description="Analytic derivative order (2 for Hessians)")
    title: str = Field(default="CFOUR Analytic Hessian Calculation", description="Job title header")
    vpt2: bool = Field(default=True, description="Perform VPT2 calculation")
    sextic_distortion: bool = Field(default=True, description="Compute sextic centrifugal distortion constants")
    fd_irrep: bool = Field(default=True, description="Enable FD_IRREP displacement acceleration")
    memory_kw: int = Field(default=500000000, ge=1000000, description="CFOUR MEMORY_SIZE in 8-byte words")

    def format_zmat_string(self) -> str:
        lines = [self.title]
        if self.geometry:
            for atom in self.geometry.atoms:
                lines.append(f"{atom.symbol:<4} {atom.x:14.8f} {atom.y:14.8f} {atom.z:14.8f}")
        elif self.geometry_zmat:
            lines.append(self.geometry_zmat.strip())
        lines.append("")
        lines.append(f"*CFOUR(CALC={self.method}")
        lines.append(f"BASIS={self.basis}")
        lines.append(f"CHARGE={self.charge:d},MULTIPLICITY={self.multiplicity:d}")
        lines.append(f"DERIV_LEV={self.derivative_order:d},VIBRATION={'VPT2' if self.vpt2 else 'EXACT'}")
        if self.fd_irrep:
            lines.append("FD_IRREP=TRUE")
        if self.sextic_distortion:
            lines.append("ANHARMONIC=SEXTIC")
        lines.append(f"MEMORY_SIZE={self.memory_kw:d})")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Scientific Provenance & Execution Result Schemas
# ---------------------------------------------------------------------------

class QuantumCalculationResult(CoChemBaseModel):
    """Complete execution result payload from a quantum chemistry run."""
    success: bool = Field(default=True, description="True if geometry / SCF converged without errors")
    engine: EngineType | str = Field(default=EngineType.ORCA, description="Executed engine name")
    task_type: TaskType | str = Field(
        default=TaskType.OPT, description="Executed task type"
    )
    method: Optional[str] = Field(default=None, description="Electronic structure method used")
    basis: Optional[str] = Field(default=None, description="Basis set used")
    energy_hartree: Optional[float] = Field(
        default=None, description="Final electronic energy in Hartree"
    )
    nuclear_repulsion_hartree: Optional[float] = Field(default=None, description="Nuclear repulsion energy in Hartree")
    zero_point_energy_hartree: Optional[float] = Field(default=None, description="Zero-point vibrational energy in Hartree")
    converged: bool = Field(
        default=True, description="True if calculation converged"
    )
    final_geometry: Optional[MolecularGeometry] = Field(default=None, description="Converged equilibrium structure")
    rotational_constants_mhz: Optional[PickettRotationalConstants | SpectroscopicConstants | Dict[str, Any]] = Field(
        alias="spectroscopic_constants", default=None, description="Calculated equilibrium rotational constants"
    )
    harmonic_frequencies_cm1: List[float] = Field(default_factory=list, description="Harmonic vibrational frequencies")
    total_steps: int = Field(default=0, ge=0, description="Total optimization steps")
    elapsed_seconds: float = Field(alias="wall_time_seconds", default=0.0, ge=0.0, description="Elapsed wall time in seconds")
    t1_diagnostic: Optional[float] = Field(default=None, description="Coupled-cluster T1 diagnostic (T1 <= 0.02)")
    d1_diagnostic: Optional[float] = Field(default=None, description="Coupled-cluster D1 diagnostic (D1 <= 0.05)")
    spin_contamination_pct: Optional[float] = Field(
        default=None, description="Open-shell <S^2> deviation percentage (< 10%)"
    )
    input_sha256: Optional[str] = Field(default=None, description="SHA-256 hash of input deck")
    output_sha256: Optional[str] = Field(default=None, description="SHA-256 hash of output log")
    provenance_tag: Optional[str] = Field(default="[M]", description="Scientific provenance tag")
    warnings: List[str] = Field(default_factory=list, description="Warning messages emitted during run")

    @model_validator(mode="before")
    @classmethod
    def pre_populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "calculation_type" in data and "task_type" not in data:
                data["task_type"] = data["calculation_type"]
            if "final_energy_hartree" in data:
                data["energy_hartree"] = data.pop("final_energy_hartree")
            elif "electronic_energy_hartree" in data and "energy_hartree" not in data:
                data["energy_hartree"] = data["electronic_energy_hartree"]
            if "convergence_achieved" in data and "converged" not in data:
                data["converged"] = data["convergence_achieved"]
            if "wall_time_seconds" in data and "elapsed_seconds" not in data:
                data["elapsed_seconds"] = data["wall_time_seconds"]
        return data

    @property
    def calculation_type(self) -> Any:
        return self.task_type

    @property
    def final_energy_hartree(self) -> Optional[float]:
        return self.energy_hartree

    @property
    def convergence_achieved(self) -> bool:
        return self.converged

    @property
    def electronic_energy_hartree(self) -> Optional[float]:
        return self.energy_hartree

    @property
    def wall_time_seconds(self) -> float:
        return self.elapsed_seconds

    @property
    def spectroscopic_constants(self) -> Any:
        return self.rotational_constants_mhz


EngineOptimizationResult = QuantumCalculationResult


class ChainedStateSchema(CoChemBaseModel):
    """Schema representing coordinate and wavefunction state transfer across pipeline rungs."""
    state_id: str = Field(default="state-001", description="Unique UUID for pipeline state snapshot")
    species_id: str = Field(default="molecule", description="Target species ID")
    source_stage: str = Field(alias="source_tier", default="GFN2-xTB", description="Stage generating state")
    target_stage: str = Field(alias="target_tier", default="r2SCAN-3c", description="Next stage receiving state")
    source_engine: Optional[str] = Field(default="XTB", description="Engine producing state")
    target_engine: Optional[str] = Field(default="ORCA", description="Engine consuming state")
    coordinates_angstrom: List[List[float]] = Field(default_factory=list, description="Atomic coordinates")
    elements: List[str] = Field(default_factory=list, description="Element symbols")
    charge: int = Field(default=0, description="Charge")
    multiplicity: int = Field(default=1, ge=1, description="Spin multiplicity")
    energy_hartree: float = Field(alias="total_energy_hartree", default=0.0, description="Electronic energy in Hartree")
    gradient_norm: Optional[float] = Field(default=1e-5, description="RMS gradient norm at convergence")
    geometry_sha256: Optional[str] = Field(default=None, description="SHA-256 hash of coordinate geometry")
    hessian_available: bool = Field(default=False, description="Whether full Hessian matrix is available for transfer")
    gbw_file_path: Optional[str] = Field(default=None, description="Path to ORCA wavefunction file (.gbw)")
    timestamp_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def source_tier(self) -> str:
        return self.source_stage

    @property
    def target_tier(self) -> str:
        return self.target_stage

    @property
    def total_energy_hartree(self) -> float:
        return self.energy_hartree


class SpycFitPayloadModel(CoChemBaseModel):
    """CoChem-SpycFit inter-agent spectroscopic parameter payload."""
    species_id: str = Field(description="Target species identifier")
    rotational_constants: PickettRotationalConstants = Field(description="Ingested rotational constants A, B, C")
    centrifugal_distortion: Optional[PickettCentrifugalDistortion] = Field(
        default=None, description="Quartic and sextic centrifugal distortion"
    )
    quadrupole_tensors: List[PickettQuadrupoleTensor] = Field(
        default_factory=list, description="Quadrupole coupling tensors for active nuclei"
    )
    dipole_components: Optional[PickettDipoleComponents] = Field(
        default=None, description="Permanent electric dipole moment in PAS"
    )
    transitions: List[PickettTransition] = Field(
        default_factory=list, description="Assigned experimental frequency transitions"
    )
    provenance: Optional[ProvenanceTag] = Field(default=ProvenanceTag.DATA, description="Data provenance tag")
    raw_source_file: Optional[str] = Field(default=None, description="Source Pickett .par or .lin file name")


class ProvenanceRecord(CoChemBaseModel):
    """Structured scientific provenance record for audit and FAIR reporting (§15)."""
    tag_type: ProvenanceTag = Field(
        default=ProvenanceTag.METHOD, description="Tag taxonomy: [M] Method, [D] Data, [E] Error"
    )
    author_or_agent: str = Field(default="CoChem-GEOM", description="Agent or module that generated the record")
    timestamp_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of computation in ISO 8601 format",
    )
    software_version: str = Field(default="CoChem-GEOM v4.0", description="Software engine version")
    codata_version: str = Field(default="CODATA 2026", description="Physical constants ledger standard")
    input_deck_sha256: Optional[str] = Field(default=None, description="SHA-256 hash of input deck")
    output_log_sha256: Optional[str] = Field(default=None, description="SHA-256 hash of output calculation log")
    wavefunction_sha256: Optional[str] = Field(default=None, description="SHA-256 hash of wavefunction binary (.gbw)")
    notes: Optional[str] = Field(default=None, description="Descriptive notes or theoretical rationale")

    def to_provenance_tag(self) -> str:
        return f"{self.tag_type.value} {self.software_version} ({self.codata_version}) [{self.timestamp_iso}]"


# ---------------------------------------------------------------------------
# Dynamic System Configuration Schema
# ---------------------------------------------------------------------------

class SystemConfigSchema(CoChemBaseModel):
    """Pydantic v2 schema for dynamic cochem_system_config.json configuration (§14)."""
    schema_version: str = Field(default="4.0.0", description="Configuration schema version")
    nprocs: int = Field(default=4, ge=1, description="Default parallel worker threads")
    maxcore: int = Field(default=4000, ge=256, description="Default memory per core in MB")
    artifacts_dir: str = Field(
        default_factory=lambda: os.environ.get("COCHEM_ARTIFACTS")
        or os.environ.get("COCHEM_ARTIFACT_DIR")
        or str(Path.home() / ".artifacts" / "cochem"),
        description="Dynamic path to artifacts directory",
    )
    workspace_dir: Optional[str] = Field(default=None, description="Root directory of active workspace")
    scratch_dir: Optional[str] = Field(
        default_factory=lambda: os.environ.get("COCHEM_SCRATCH") or str(Path.home() / ".cochem" / "scratch"),
        description="Dynamic path to scratch directory",
    )
    orca_executable: Optional[str] = Field(default="orca", description="Path or command for ORCA quantum binary")
    cfour_executable: Optional[str] = Field(default="cfour", description="Path or command for CFOUR quantum binary")
    xtb_executable: Optional[str] = Field(default="xtb", description="Path or command for xTB quantum binary")
    pyscf_executable: Optional[str] = Field(default="pyscf", description="Path or command for PySCF quantum binary")
    crest_executable: Optional[str] = Field(default="crest", description="Path or command for CREST conformer engine")
    goat_executable: Optional[str] = Field(default="goat", description="Path or command for GOAT conformer engine")
    spfit_executable: Optional[str] = Field(default="spfit", description="Path or command for Pickett SPFIT executable")
    spcat_executable: Optional[str] = Field(default="spcat", description="Path or command for Pickett SPCAT executable")
    hardware: Dict[str, Any] = Field(default_factory=dict, description="Hardware resource profiles")
    engines: Dict[str, Any] = Field(default_factory=dict, description="Engine binary specifications")
    hpc: Dict[str, Any] = Field(default_factory=dict, description="HPC cluster and walltime configs")

    def resolve_artifacts_path(self) -> Path:
        return Path(self.artifacts_dir).resolve()

    def resolve_workspace_path(self) -> Path:
        if self.workspace_dir:
            return Path(self.workspace_dir).resolve()
        return Path.cwd().resolve()

    def get_engine_path(self, engine_name: str) -> Optional[str]:
        """Retrieve binary path for a configured computational engine."""
        eng = self.engines.get(engine_name.lower())
        if isinstance(eng, dict):
            return eng.get("path")
        attr_name = f"{engine_name.lower()}_executable"
        return getattr(self, attr_name, None)

    def get_walltime_budget(self, tier: str) -> str:
        """Retrieve Method Matrix walltime budget string (e.g. '00:00:10' for 'T1-10s')."""
        budgets = self.hpc.get("walltime_budgets", {})
        return str(budgets.get(tier, "01:00:00"))

    @classmethod
    def load_system_config(cls, config_path: Optional[Union[str, Path]] = None) -> "SystemConfigSchema":
        from cochem_geom.engine.paths import load_system_config
        return cast("SystemConfigSchema", load_system_config(config_path))

    @classmethod
    def load_from_json(cls, json_str: str) -> "SystemConfigSchema":
        return cls.model_validate_json(json_str)

    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> "SystemConfigSchema":
        p = Path(file_path).resolve()
        return cls.model_validate_json(p.read_text(encoding="utf-8"))
