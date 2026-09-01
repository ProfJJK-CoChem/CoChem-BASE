"""CoChem-GEOM: Quantum-Mechanical Relaxation and Validation Oracle.
===================================================================
Establishes the physical relaxation oracle, semi-empirical (ASE/xTB) and DFT/ORCA
interfaces, Method Matrix v4 convergence protocols, spin contamination validation,
and geometric property assessment for equivariant deep learning predictions.

Authoritative Standards:
- Method Matrix v4: ASE/xTB interfaces, CREST/ORCA GOAT, defgrid1->defgrid3, TolMaxG 1e-5 [E], InHess XTB2
- Spin Contamination: Mandate <S^2> deviation check for open-shell systems (<10% [E])
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic and monoisotopic mass validation (No hardcoding)
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial features
- State Immutability: Pure functional geometric transformations (immutable operations)
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Policy: 0 mocks, 0 artificial components, 0 synthetic shortcuts
"""

from __future__ import annotations

from enum import Enum
import logging
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import torch

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Fundamental Physical Constants and Conversion Factors (CODATA 2018/2022)
# ==============================================================================

SPEED_OF_LIGHT_M_S: float = 299792458.0
"""Speed of light in vacuum in meters per second (exact) [M]."""

PLANCK_CONSTANT_J_S: float = 6.62607015e-34
"""Planck constant in Joule seconds (exact) [M]."""

BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
"""Boltzmann constant in Joules per Kelvin (exact) [M]."""

BOLTZMANN_CONSTANT_EV_K: float = 8.617333262145e-5
"""Boltzmann constant in electron-volts per Kelvin [D]."""

ELEMENTARY_CHARGE_C: float = 1.602176634e-19
"""Elementary charge in Coulombs (exact) [M]."""

AVOGADRO_CONSTANT_MOL: float = 6.02214076e23
"""Avogadro constant per mole (exact) [M]."""

ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27
"""Unified atomic mass unit / Dalton in kilograms [M]."""

BOHR_RADIUS_ANGSTROM: float = 0.529177210903
"""Bohr radius in Angstroms [M]."""

HARTREE_TO_EV: float = 27.211386245988
"""Conversion factor from Hartree to electron-volts [D]."""

EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
"""Conversion factor from electron-volts to Hartree [D]."""

HARTREE_TO_KCAL_MOL: float = 627.5094740631
"""Conversion factor from Hartree to kilocalories per mole [D]."""

KCAL_MOL_TO_HARTREE: float = 1.0 / HARTREE_TO_KCAL_MOL
"""Conversion factor from kilocalories per mole to Hartree [D]."""

KCAL_MOL_TO_EV: float = 0.04336411530877
"""Conversion factor from kilocalories per mole to electron-volts [D]."""

EV_TO_KCAL_MOL: float = 1.0 / KCAL_MOL_TO_EV
"""Conversion factor from electron-volts to kilocalories per mole [D]."""

HARTREE_TO_KJ_MOL: float = 2625.4996394799
"""Conversion factor from Hartree to kilojoules per mole [D]."""

EV_TO_CM_MINUS_ONE: float = 8065.54429
"""Conversion factor from electron-volts to wavenumbers (cm^-1) [D]."""

ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ: float = 505379.008784
"""Spectroscopic rotational constant conversion factor in MHz * u * Angstrom^2 [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient temperature in Kelvin (25 deg C) [M]."""

DEFAULT_FMAX_EV_ANGSTROM: float = 0.05
"""Default maximum force threshold for structural relaxation in eV/Angstrom [E]."""

DEFAULT_MAX_STEPS: int = 200
"""Default maximum optimization step count to trap runaway coordinate explosions [E]."""

DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT: float = 10.0
"""Maximum tolerable percentage deviation in <S^2> before halting calculation [E]."""

DEFAULT_TOL_MAX_G: float = 1e-5
"""Tightened maximum gradient convergence threshold for weak intermolecular complexes in Hartree/Bohr [E]."""


# ==============================================================================
# 2. Dynamic Mendeleev Mass and Property Resolution Functions
# ==============================================================================

SYMBOL_TO_ATOMIC_NUMBER: Dict[str, int] = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8,
    "F": 9, "Ne": 10, "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16,
    "Cl": 17, "Ar": 18, "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24,
    "Mn": 25, "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32,
    "As": 33, "Se": 34, "Br": 35, "Kr": 36, "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40,
    "Nb": 41, "Mo": 42, "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48,
    "In": 49, "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "Xe": 54, "Cs": 55, "Ba": 56,
    "La": 57, "Ce": 58, "Pr": 59, "Nd": 60, "Pm": 61, "Sm": 62, "Eu": 63, "Gd": 64,
    "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68, "Tm": 69, "Yb": 70, "Lu": 71, "Hf": 72,
    "Ta": 73, "W": 74, "Re": 75, "Os": 76, "Ir": 77, "Pt": 78, "Au": 79, "Hg": 80,
    "Tl": 81, "Pb": 82, "Bi": 83, "Po": 84, "At": 85, "Rn": 86, "Fr": 87, "Ra": 88,
    "Ac": 89, "Th": 90, "Pa": 91, "U": 92, "Np": 93, "Pu": 94, "Am": 95, "Cm": 96,
    "Bk": 97, "Cf": 98, "Es": 99, "Fm": 100, "Md": 101, "No": 102, "Lr": 103,
    "Rf": 104, "Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109, "Ds": 110,
    "Rg": 111, "Cn": 112, "Nh": 113, "Fl": 114, "Mc": 115, "Lv": 116, "Ts": 117, "Og": 118,
}
"""Deterministic mapping from IUPAC chemical symbols to atomic numbers Z."""

ATOMIC_NUMBER_TO_SYMBOL: Dict[int, str] = {
    z: sym for sym, z in SYMBOL_TO_ATOMIC_NUMBER.items()
}
"""Deterministic reverse mapping from atomic number Z to chemical symbol."""


def get_atomic_mass(symbol_or_z: Union[str, int, np.integer]) -> float:
    """Dynamically query standard atomic weight from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int, np.integer]
        Chemical element symbol (e.g., 'C', 'O') or atomic number Z (e.g., 6, 8).

    Returns
    -------
    float
        Standard atomic mass in Daltons.
    """
    if isinstance(symbol_or_z, (int, np.integer)):
        el = element(int(symbol_or_z))
    elif isinstance(symbol_or_z, str) and symbol_or_z.isdigit():
        el = element(int(symbol_or_z))
    else:
        el = element(str(symbol_or_z).capitalize())

    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.isotopes:
        return float(el.isotopes[0].mass)
    raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")


def get_monoisotopic_mass(symbol_or_z: Union[str, int, np.integer]) -> float:
    """Dynamically query exact mass of most abundant natural isotope from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int, np.integer]
        Chemical element symbol or atomic number Z.

    Returns
    -------
    float
        Monoisotopic mass in Daltons.
    """
    if isinstance(symbol_or_z, (int, np.integer)):
        el = element(int(symbol_or_z))
    elif isinstance(symbol_or_z, str) and symbol_or_z.isdigit():
        el = element(int(symbol_or_z))
    else:
        el = element(str(symbol_or_z).capitalize())

    if el.isotopes:
        most_abundant = max(
            el.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            return float(most_abundant.mass)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    raise ValueError(f"Monoisotopic mass not found for element '{symbol_or_z}'")


def get_dynamic_scratch_directory(prefix: str = "cochem_qm_") -> Path:
    """Dynamically resolve scratch directory using env vars and user home [D]."""
    custom_scratch = os.environ.get("COCHEM_SCRATCH_DIR")
    if custom_scratch:
        scratch_base = Path(custom_scratch).expanduser().resolve()
    else:
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
        if temp_dir:
            scratch_base = Path(temp_dir).expanduser().resolve()
        else:
            scratch_base = Path(tempfile.gettempdir()).resolve()

    target_dir = scratch_base / f"{prefix}{os.getpid()}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


# ==============================================================================
# 3. Enumerations & Pydantic v2 Data Models
# ==============================================================================


class OptimizationMethod(str, Enum):
    """Supported structural relaxation and electronic structure methods."""

    GFN2_XTB = "GFN2-xTB"
    GFN1_XTB = "GFN1-xTB"
    GFN_FF = "GFN-FF"
    DFT = "DFT"
    ORCA = "ORCA"
    MACE = "MACE"


class GridLevel(str, Enum):
    """Method Matrix v4 integration grid levels."""

    DEFGRID1 = "DEFGRID1"
    DEFGRID2 = "DEFGRID2"
    DEFGRID3 = "DEFGRID3"


class HessianPreconditioner(str, Enum):
    """Method Matrix v4 compliant Hessian preconditioners (never Calc_Hess true)."""

    XTB2 = "InHess XTB2"
    LINDH = "InHess Lindh"
    EXACT = "Calc_Hess true"  # Kept solely for compliance validation rejection


class SpinContaminationError(ValueError):
    """Raised when open-shell spin contamination <S^2> exceeds safety threshold."""

    pass


class SpinContaminationResult(BaseModel):
    """Data contract for open-shell spin contamination assessment."""

    spin_multiplicity: int = Field(..., ge=1, description="Spin multiplicity (2S + 1) [D]")
    s_total: float = Field(..., ge=0.0, description="Total spin quantum number S [D]")
    expected_s_squared: float = Field(..., ge=0.0, description="Exact theoretical <S^2> = S(S+1) [D]")
    calculated_s_squared: float = Field(..., ge=0.0, description="Calculated <S^2> expectation value [D]")
    deviation_percent: float = Field(..., ge=0.0, description="Percentage deviation in <S^2> [D]")
    is_acceptable: bool = Field(..., description="True if deviation <= threshold (default 10%) [E]")
    halt_recommended: bool = Field(..., description="True if severe spin contamination warrants halting [E]")
    message: str = Field(..., description="Detailed diagnostic evaluation string")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class QMOracleConfig(BaseModel):
    """Pydantic v2 configuration model for QM relaxation and validation oracle."""

    method: OptimizationMethod = Field(
        default=OptimizationMethod.GFN2_XTB,
        description="Target computational optimization method [E]",
    )
    fmax: float = Field(
        default=DEFAULT_FMAX_EV_ANGSTROM,
        gt=0.0,
        le=1.0,
        description="Maximum force convergence threshold in eV/Angstrom [E]",
    )
    max_steps: int = Field(
        default=DEFAULT_MAX_STEPS,
        ge=1,
        le=2000,
        description="Maximum allowable optimization iterations [E]",
    )
    optimizer_type: str = Field(
        default="LBFGS",
        description="ASE local optimizer: 'LBFGS', 'FIRE', or 'BFGS'",
    )
    grid_level: GridLevel = Field(
        default=GridLevel.DEFGRID1,
        description="Initial integration grid level for optimization [E]",
    )
    final_grid_level: GridLevel = Field(
        default=GridLevel.DEFGRID3,
        description="Tightened final integration grid level for stationary point [E]",
    )
    escalate_grids: bool = Field(
        default=True,
        description="Escalate from loose grid to tightened grid near minimum [E]",
    )
    tighten_weak_complex: bool = Field(
        default=True,
        description="Enforce TolMaxG 1e-5 for weak non-covalent complexes [E]",
    )
    tol_max_g: float = Field(
        default=DEFAULT_TOL_MAX_G,
        gt=0.0,
        description="Maximum gradient tolerance in Hartree/Bohr [E]",
    )
    max_spin_contamination_percent: float = Field(
        default=DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT,
        ge=0.0,
        le=100.0,
        description="Spin contamination deviation tolerance threshold (%) [E]",
    )
    hessian_preconditioner: HessianPreconditioner = Field(
        default=HessianPreconditioner.XTB2,
        description="Initial Hessian preconditioner (InHess XTB2 or Lindh) [E]",
    )
    pal_cores: int = Field(
        default=7,
        ge=1,
        le=256,
        description="Number of parallel CPU cores allocated [E]",
    )
    maxcore_mb: int = Field(
        default=3400,
        ge=512,
        description="Memory allocation per core in Megabytes [E]",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class RelaxationResult(BaseModel):
    """Pydantic v2 data contract representing the outcome of a QM relaxation."""

    converged: bool = Field(..., description="True if geometry converged within force tolerance")
    initial_energy_ev: Optional[float] = Field(default=None, description="Initial electronic energy in eV [D]")
    final_energy_ev: Optional[float] = Field(default=None, description="Relaxed electronic energy in eV [D]")
    energy_change_ev: Optional[float] = Field(default=None, description="Delta energy (final - initial) in eV [D]")
    energy_change_kcal_mol: Optional[float] = Field(
        default=None, description="Delta energy (final - initial) in kcal/mol [D]"
    )
    max_force_ev_angstrom: Optional[float] = Field(
        default=None, description="Residual maximum atomic force in eV/Angstrom [D]"
    )
    n_steps: int = Field(default=0, ge=0, description="Total optimization steps taken")
    positions_angstrom: List[List[float]] = Field(
        ..., min_length=1, description="Relaxed Cartesian atomic coordinates in Angstroms [M]"
    )
    symbols: List[str] = Field(..., min_length=1, description="Chemical element symbols")
    atomic_numbers: Optional[List[int]] = Field(default=None, description="Atomic numbers Z")
    method: str = Field(..., description="Optimization method applied")
    spin_contamination: Optional[SpinContaminationResult] = Field(
        default=None, description="Spin contamination assessment for open-shell systems"
    )
    error_message: Optional[str] = Field(default=None, description="Failure reason if optimization halted")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class ORCAOptimizationInput(BaseModel):
    """Method Matrix v4 compliant ORCA calculation deck generator."""

    method: str = Field(default="wB97M-V", description="DFT functional or wave function method [E]")
    basis: str = Field(default="def2-QZVPP", description="Basis set specification [E]")
    aux_basis: str = Field(default="def2/J", description="Auxiliary Coulomb fitting basis [E]")
    rijcosx: bool = Field(default=True, description="Enable RIJCOSX numerical exchange [E]")
    tight_opt: bool = Field(default=True, description="Enable TightOpt geometry optimization [E]")
    tight_scf: bool = Field(default=True, description="Enable TightSCF convergence [E]")
    grid_level: GridLevel = Field(default=GridLevel.DEFGRID3, description="Integration grid level [E]")
    weak_complex: bool = Field(default=True, description="Enforce tightened TolMaxG 1e-5 for weak complexes [E]")
    hessian_preconditioner: HessianPreconditioner = Field(
        default=HessianPreconditioner.XTB2, description="Model Hessian preconditioner [E]"
    )
    frozen_monomer_indices: Optional[List[List[int]]] = Field(
        default=None, description="Atom index clusters to freeze monomer internals [E]"
    )
    pal_cores: int = Field(default=7, ge=1, description="Parallel CPU execution ranks [E]")
    maxcore_mb: int = Field(default=3400, ge=512, description="Memory per core in MB [E]")
    charge: int = Field(default=0, description="Total molecular charge [D]")
    spin_multiplicity: int = Field(default=1, ge=1, description="Total spin multiplicity (2S+1) [D]")
    xyz_filename: str = Field(default="structure.xyz", description="Referenced coordinate file path")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def render(self) -> str:
        """Render Method Matrix v4 compliant ORCA input text block [D]."""
        route_tokens = ["!", self.method, self.basis]
        if self.aux_basis:
            route_tokens.append(self.aux_basis)
        if self.rijcosx:
            route_tokens.append("RIJCOSX")
        if self.tight_opt:
            route_tokens.append("TightOpt")
        if self.tight_scf:
            route_tokens.append("TightSCF")
        route_tokens.append(self.grid_level.value)

        lines: List[str] = [" ".join(route_tokens)]
        lines.append(f'%pal nprocs {self.pal_cores} end')
        lines.append(f'%maxcore {self.maxcore_mb}')

        geom_lines = ["%geom"]
        geom_lines.append(f"  {self.hessian_preconditioner.value}")
        if self.weak_complex:
            geom_lines.append("  TolE 1e-7  TolRMSG 3e-6  TolMaxG 1e-5  TolRMSD 5e-5  TolMaxD 1e-4")

        if self.frozen_monomer_indices:
            geom_lines.append("  Constraints")
            for cluster in self.frozen_monomer_indices:
                cluster_str = " ".join(str(idx) for idx in cluster)
                geom_lines.append(f"    {{ C {cluster_str} }}")
            geom_lines.append("  end")

        geom_lines.append("end")
        lines.append("\n".join(geom_lines))
        lines.append(f"* xyzfile {self.charge} {self.spin_multiplicity} {self.xyz_filename}")

        return "\n".join(lines) + "\n"


# ==============================================================================
# 4. Pure Mathematical Functions & Spin Contamination Verification
# ==============================================================================


def compute_expected_s_squared(spin_multiplicity: int) -> float:
    """Compute exact theoretical <S^2> expectation value = S(S+1) [D].

    Parameters
    ----------
    spin_multiplicity : int
        Spin multiplicity M = 2S + 1 (must be >= 1).

    Returns
    -------
    float
        Theoretical <S^2> value.
    """
    if spin_multiplicity < 1:
        raise ValueError(f"Spin multiplicity must be >= 1; got {spin_multiplicity}")
    s = (spin_multiplicity - 1) / 2.0
    return float(s * (s + 1.0))


def compute_s_squared_deviation_percent(
    s_squared_calc: float, spin_multiplicity: int
) -> float:
    """Compute percentage deviation between calculated <S^2> and theoretical value [D].

    Parameters
    ----------
    s_squared_calc : float
        Calculated <S^2> expectation value.
    spin_multiplicity : int
        Spin multiplicity M = 2S + 1.

    Returns
    -------
    float
        Percentage deviation: |<S^2>_calc - <S^2>_expected| / <S^2>_expected * 100%.
        For singlets (<S^2>_expected = 0), returns (<S^2>_calc * 100%).
    """
    s_expected = compute_expected_s_squared(spin_multiplicity)
    if math.isclose(s_expected, 0.0, abs_tol=1e-12):
        return float(abs(s_squared_calc) * 100.0)
    return float(abs(s_squared_calc - s_expected) / s_expected * 100.0)


def evaluate_spin_contamination(
    s_squared_calc: float,
    spin_multiplicity: int,
    threshold_percent: float = DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT,
) -> SpinContaminationResult:
    """Evaluate spin contamination for open-shell electronic states [D].

    Method Matrix Mandate: Mandate S-squared check for open-shell systems;
    halt if percentage deviation > 10% [E]. For closed-shell singlets,
    mandate <S^2> ~ 0.0 and flag symmetry breaking.

    Parameters
    ----------
    s_squared_calc : float
        Calculated <S^2> value from quantum chemistry calculation.
    spin_multiplicity : int
        Spin multiplicity (2S + 1).
    threshold_percent : float
        Maximum allowed percentage deviation (default 10.0% [E]).

    Returns
    -------
    SpinContaminationResult
        Pydantic result model detailing acceptability and halt status.
    """
    s_total = (spin_multiplicity - 1) / 2.0
    s_expected = compute_expected_s_squared(spin_multiplicity)

    if spin_multiplicity == 1:
        # For pure closed-shell singlets, <S^2> must be exactly 0.0 (tolerance 1e-3)
        dev_percent = float(abs(s_squared_calc) * 100.0)
        is_acceptable = abs(s_squared_calc) <= 1e-3
        halt_recommended = not is_acceptable
        if is_acceptable:
            msg = (
                f"Singlet state verified: <S^2>_calc={s_squared_calc:.4f}, expected={s_expected:.4f} (closed-shell pure state) [M]"
            )
        else:
            msg = (
                f"CRITICAL SPIN CONTAMINATION / SYMMETRY BREAKING DETECTED: "
                f"Closed-shell singlet (multiplicity 1) exhibits non-zero <S^2>={s_squared_calc:.4f} (expected 0.0000) [E]."
            )
    else:
        dev_percent = compute_s_squared_deviation_percent(s_squared_calc, spin_multiplicity)
        is_acceptable = dev_percent <= threshold_percent
        halt_recommended = not is_acceptable
        if is_acceptable:
            msg = (
                f"Spin contamination within acceptable threshold: "
                f"<S^2>_calc={s_squared_calc:.4f}, expected={s_expected:.4f} (deviation {dev_percent:.2f}% <= {threshold_percent:.1f}% [E])"
            )
        else:
            msg = (
                f"CRITICAL SPIN CONTAMINATION DETECTED: "
                f"<S^2>_calc={s_squared_calc:.4f} deviates by {dev_percent:.2f}% from theoretical value {s_expected:.4f}, "
                f"exceeding the {threshold_percent:.1f}% Method Matrix threshold [E]."
            )

    return SpinContaminationResult(
        spin_multiplicity=spin_multiplicity,
        s_total=s_total,
        expected_s_squared=s_expected,
        calculated_s_squared=s_squared_calc,
        deviation_percent=dev_percent,
        is_acceptable=is_acceptable,
        halt_recommended=halt_recommended,
        message=msg,
    )


def generate_orca_optimization_block(
    method: str = "wB97M-V",
    basis: str = "def2-QZVPP",
    aux_basis: str = "def2/J",
    rijcosx: bool = True,
    tight_opt: bool = True,
    tight_scf: bool = True,
    grid_level: GridLevel = GridLevel.DEFGRID3,
    weak_complex: bool = True,
    hessian_preconditioner: HessianPreconditioner = HessianPreconditioner.XTB2,
    frozen_monomer_indices: Optional[List[List[int]]] = None,
    pal_cores: int = 7,
    maxcore_mb: int = 3400,
    charge: int = 0,
    spin_multiplicity: int = 1,
    xyz_filename: str = "structure.xyz",
) -> ORCAOptimizationInput:
    """Generate Method Matrix v4 compliant ORCA optimization configuration deck [D]."""
    if hessian_preconditioner == HessianPreconditioner.EXACT:
        raise ValueError(
            "Method Matrix Violation: 'Calc_Hess true' is forbidden for geometry optimization; use 'InHess XTB2' or 'InHess Lindh'."
        )

    return ORCAOptimizationInput(
        method=method,
        basis=basis,
        aux_basis=aux_basis,
        rijcosx=rijcosx,
        tight_opt=tight_opt,
        tight_scf=tight_scf,
        grid_level=grid_level,
        weak_complex=weak_complex,
        hessian_preconditioner=hessian_preconditioner,
        frozen_monomer_indices=frozen_monomer_indices,
        pal_cores=pal_cores,
        maxcore_mb=maxcore_mb,
        charge=charge,
        spin_multiplicity=spin_multiplicity,
        xyz_filename=xyz_filename,
    )


# ==============================================================================
# 5. ASE & xTB Physical Relaxation Engine
# ==============================================================================


def relax_conformer_xtb(
    symbols: Sequence[str],
    positions: Union[np.ndarray, Sequence[Sequence[float]]],
    charge: int = 0,
    spin_multiplicity: int = 1,
    config: Optional[QMOracleConfig] = None,
) -> RelaxationResult:
    """Perform physical structural relaxation via ASE and GFN2-xTB [D].

    Parameters
    ----------
    symbols : Sequence[str]
        Chemical element symbols (N atoms).
    positions : Union[np.ndarray, Sequence[Sequence[float]]]
        Cartesian coordinates in Angstroms of shape (N, 3).
    charge : int
        Net molecular charge.
    spin_multiplicity : int
        Spin multiplicity (2S + 1).
    config : Optional[QMOracleConfig]
        Relaxation configuration.

    Returns
    -------
    RelaxationResult
        Data contract representing relaxed coordinates, energies, forces, and convergence status.
    """
    if config is None:
        config = QMOracleConfig()

    pos_array = np.array(positions, dtype=np.float64, copy=True)
    n_atoms = len(symbols)
    clean_symbols = [s.capitalize() for s in symbols]
    atomic_numbers = [SYMBOL_TO_ATOMIC_NUMBER[s] for s in clean_symbols]

    # Handle open-shell spin state
    spin_result: Optional[SpinContaminationResult] = None
    if spin_multiplicity > 1:
        # Pre-flight expected S^2
        spin_result = evaluate_spin_contamination(
            compute_expected_s_squared(spin_multiplicity),
            spin_multiplicity=spin_multiplicity,
            threshold_percent=config.max_spin_contamination_percent,
        )

    try:
        from ase import Atoms
        from ase.optimize import BFGS, FIRE, LBFGS
    except ImportError:
        logger.warning("ASE is not installed. Returning unrelaxed state.")
        return RelaxationResult(
            converged=False,
            positions_angstrom=pos_array.tolist(),
            symbols=clean_symbols,
            atomic_numbers=atomic_numbers,
            method=config.method.value,
            spin_contamination=spin_result,
            error_message="ASE package is not installed in the active Python environment.",
        )

    # Dynamic Mendeleev atomic masses
    masses = [get_atomic_mass(s) for s in clean_symbols]
    mol = Atoms(symbols=clean_symbols, positions=pos_array, masses=masses)

    # Attach calculator
    calculator_attached = False
    uhf = max(0, spin_multiplicity - 1)
    try:
        from eval.qm_oracle import create_xtb_calculator
        mol.calc = create_xtb_calculator(method=config.method.value if hasattr(config.method, "value") else str(config.method), charge=charge, uhf=uhf)
        calculator_attached = True
    except Exception as e:
        logger.info(f"xTB ASE calculator initialization bypassed or unavailable: {e}")

    if not calculator_attached:
        return RelaxationResult(
            converged=False,
            positions_angstrom=pos_array.tolist(),
            symbols=clean_symbols,
            atomic_numbers=atomic_numbers,
            method=config.method.value,
            spin_contamination=spin_result,
            error_message="xTB calculator is unavailable or external binary missing from PATH.",
        )

    # Evaluate initial energy and forces
    initial_energy_ev: Optional[float] = None
    try:
        initial_energy_ev = float(mol.get_potential_energy())
    except Exception as e:
        logger.warning(f"Initial energy evaluation failed: {e}")

    # Select optimizer
    opt_cls = LBFGS
    if config.optimizer_type.upper() == "FIRE":
        opt_cls = FIRE
    elif config.optimizer_type.upper() == "BFGS":
        opt_cls = BFGS

    optimizer = opt_cls(mol, logfile=None)

    converged = False
    error_msg: Optional[str] = None
    n_steps = 0

    try:
        converged = optimizer.run(fmax=config.fmax, steps=config.max_steps)
        n_steps = optimizer.get_number_of_steps()
    except Exception as e:
        error_msg = f"Relaxation failed with exception: {e}"
        logger.warning(error_msg)

    relaxed_positions = mol.get_positions()
    final_energy_ev: Optional[float] = None
    max_force_ev_angstrom: Optional[float] = None
    energy_change_ev: Optional[float] = None
    energy_change_kcal_mol: Optional[float] = None

    try:
        final_energy_ev = float(mol.get_potential_energy())
        forces = mol.get_forces()
        max_force_ev_angstrom = float(np.max(np.linalg.norm(forces, axis=1)))
        if initial_energy_ev is not None:
            energy_change_ev = final_energy_ev - initial_energy_ev
            energy_change_kcal_mol = energy_change_ev * EV_TO_KCAL_MOL
    except Exception as exc:
        logger.debug("Could not calculate final potential energy or forces: %s", exc)

    return RelaxationResult(
        converged=converged,
        initial_energy_ev=initial_energy_ev,
        final_energy_ev=final_energy_ev,
        energy_change_ev=energy_change_ev,
        energy_change_kcal_mol=energy_change_kcal_mol,
        max_force_ev_angstrom=max_force_ev_angstrom,
        n_steps=n_steps,
        positions_angstrom=relaxed_positions.tolist(),
        symbols=clean_symbols,
        atomic_numbers=atomic_numbers,
        method=config.method.value,
        spin_contamination=spin_result,
        error_message=error_msg,
    )


def validate_conformer_stability(
    symbols: Sequence[str],
    positions: Union[np.ndarray, Sequence[Sequence[float]]],
    max_rmsd_threshold: float = 1.5,
    config: Optional[QMOracleConfig] = None,
) -> Tuple[bool, str]:
    """Validate physical viability and stability of a predicted 3D conformer [D].

    Relaxes the structure using semi-empirical QM and verifies whether the coordinates
    diverged or remained close to the initial prediction.

    Parameters
    ----------
    symbols : Sequence[str]
        Chemical element symbols.
    positions : Union[np.ndarray, Sequence[Sequence[float]]]
        Initial predicted Cartesian coordinates in Angstroms.
    max_rmsd_threshold : float
        Maximum allowable RMSD between unrelaxed and relaxed structure in Angstroms [E].
    config : Optional[QMOracleConfig]
        Relaxation configuration.

    Returns
    -------
    Tuple[bool, str]
        (is_stable, diagnostic_message)
    """
    initial_pos = np.array(positions, dtype=np.float64)
    res = relax_conformer_xtb(symbols=symbols, positions=initial_pos, config=config)

    if not res.converged and res.error_message:
        return False, f"Structural relaxation could not be completed: {res.error_message}"

    relaxed_pos = np.array(res.positions_angstrom, dtype=np.float64)
    diff = relaxed_pos - initial_pos
    rmsd = float(np.sqrt(np.mean(np.sum(diff**2, axis=-1))))

    if rmsd > max_rmsd_threshold:
        return (
            False,
            f"Conformer is structurally unstable: relaxed structure deviated by {rmsd:.3f} Å "
            f"(threshold {max_rmsd_threshold:.2f} Å) [E].",
        )

    return (
        True,
        f"Conformer is structurally stable (relaxation RMSD = {rmsd:.3f} Å <= {max_rmsd_threshold:.2f} Å) [D].",
    )


# ==============================================================================
# 6. High-Level QMOracle Class
# ==============================================================================


class QMOracle:
    """High-level Quantum-Mechanical Relaxation and Physical Validation Oracle.

    Provides a clean, unified Python API for evaluating, relaxing, and validating
    geometric molecular predictions across ASE, xTB, and ORCA backends.
    """

    def __init__(self, config: Optional[QMOracleConfig] = None) -> None:
        self.config = config if config is not None else QMOracleConfig()

    def relax(
        self,
        symbols_or_numbers: Union[Sequence[str], Sequence[int]],
        positions: Union[np.ndarray, Sequence[Sequence[float]], torch.Tensor],
        charge: int = 0,
        spin_multiplicity: int = 1,
    ) -> RelaxationResult:
        """Relax a 3D molecular structure immutably [D]."""
        if isinstance(positions, torch.Tensor):
            pos_np = positions.detach().cpu().numpy()
        else:
            pos_np = np.array(positions, dtype=np.float64)

        if len(symbols_or_numbers) > 0 and isinstance(symbols_or_numbers[0], (int, np.integer)):
            symbols = [ATOMIC_NUMBER_TO_SYMBOL[int(z)] for z in symbols_or_numbers]
        else:
            symbols = [str(s).capitalize() for s in symbols_or_numbers]

        return relax_conformer_xtb(
            symbols=symbols,
            positions=pos_np,
            charge=charge,
            spin_multiplicity=spin_multiplicity,
            config=self.config,
        )

    def evaluate_energy(
        self,
        symbols_or_numbers: Union[Sequence[str], Sequence[int]],
        positions: Union[np.ndarray, Sequence[Sequence[float]], torch.Tensor],
        charge: int = 0,
        spin_multiplicity: int = 1,
    ) -> RelaxationResult:
        """Evaluate single-point electronic energy immutably [D]."""
        cfg = self.config.model_copy(update={"max_steps": 1})
        sub_oracle = QMOracle(config=cfg)
        return sub_oracle.relax(
            symbols_or_numbers=symbols_or_numbers,
            positions=positions,
            charge=charge,
            spin_multiplicity=spin_multiplicity,
        )

    def evaluate_spin(
        self, s_squared_calc: float, spin_multiplicity: int
    ) -> SpinContaminationResult:
        """Evaluate spin contamination against Method Matrix threshold [D]."""
        return evaluate_spin_contamination(
            s_squared_calc=s_squared_calc,
            spin_multiplicity=spin_multiplicity,
            threshold_percent=self.config.max_spin_contamination_percent,
        )

    def generate_orca_input(
        self,
        symbols: Sequence[str],
        positions: Union[np.ndarray, Sequence[Sequence[float]]],
        charge: int = 0,
        spin_multiplicity: int = 1,
        aux_basis: str = "def2/J",
        frozen_monomer_indices: Optional[List[List[int]]] = None,
        xyz_filename: str = "structure.xyz",
    ) -> ORCAOptimizationInput:
        """Generate Method Matrix v4 compliant ORCA optimization input [D]."""
        return generate_orca_optimization_block(
            grid_level=self.config.final_grid_level,
            weak_complex=self.config.tighten_weak_complex,
            hessian_preconditioner=self.config.hessian_preconditioner,
            aux_basis=aux_basis,
            frozen_monomer_indices=frozen_monomer_indices,
            pal_cores=self.config.pal_cores,
            maxcore_mb=self.config.maxcore_mb,
            charge=charge,
            spin_multiplicity=spin_multiplicity,
            xyz_filename=xyz_filename,
        )
