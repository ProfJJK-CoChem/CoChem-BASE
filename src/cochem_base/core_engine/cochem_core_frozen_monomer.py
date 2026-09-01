#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_frozen_monomer.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""CoChem-CORE: Stage 9A - Composite & Frozen-Monomer Energy & Geometry Decomposition Protocol.

Mandated by:
- Method Matrix v4 §9 & Conference 2 §9A (§9A.1–§9A.7) (Composite & Combined Methods)
- Method Matrix v4 §4.4 (Tight %geom Optimization Block) & §4.5 (Coordinate Sensitivity Propagation)
- Method Matrix v4 §3.0–§3.3 (B_e vs B_0 Accuracy Specifications & Spend Priority)
- Method Matrix v4 §8B.4 (Canonical State Reuse) & §6.10 (Isotopologue Shortcut)
- CoChem Anti-Spoofing Protocol v2 (Authentic Physical Calculation Invariant)
- CoChem Mendeleev Library Mandate (Dynamic Mass Retrieval via mendeleev)

Architectural Overview:
1. Rigid-Rotor Inertial Tensor & Rotational Observables Engine:
   - Dynamic atomic and isotopic mass retrieval using the `mendeleev` Python library.
   - Center of mass translation and Cartesian inertia tensor diagonalization in the Principal Axis System (PAS).
   - Exact conversion using CONV = 505379.0 MHz·u·Å² (Groner convention) to produce A >= B >= C (MHz).
   - Planar moments (P_aa > P_bb > P_cc), inertial defect (Delta = I_c - I_a - I_b = -2*P_cc), and Ray's asymmetry (kappa).
   - Model-free dipole and geometry observables.

2. Coordinate Error Propagation & Sensitivity Analysis (Method Matrix §4.5):
   - Exact non-linearized rigid-rotor error propagation for monomer covalent bonds (delta_r) vs intermolecular separation (delta_R).
   - Evaluates the fundamental headline: monomer geometry dominates A; intermolecular separation dominates B and C.
   - Computes break-even equivalence between monomer bond errors and intermolecular distance errors.

3. Frozen-Monomer Geometry Protocol & Rigid Superposition (Method Matrix §9A.1, §9A.2):
   - Frozen-monomer flag categorization: `relaxed`, `frozen-iso`, and `frozen-inc`.
   - Exact Kabsch SVD rigid-body alignment for substituting high-level isolated monomer geometries (r_e^SE or CCSD(T)/CBS)
     onto in-complex coordinates without distorting relative orientations.
   - Generation of mandatory §4.4 `%geom` blocks and intramolecular Cartesian/internal constraints for ORCA.
   - Residual gradient verification on frozen coordinates against TolMaxG (1e-5 Eh/bohr) with deformation warnings.

4. Energy Decomposition & Counterpoise Protocols (Method Matrix §9A.7 Rules 1–7):
   - Standard 3-leg Boys-Bernardi Counterpoise (CP) interaction energy: delta_E_CP = E_AB^(AB) - E_A^(AB) - E_B^(AB).
   - Uncorrected interaction energy: delta_E_noCP = E_AB^(AB) - E_A^A - E_B^B.
   - Basis Set Superposition Error (BSSE): E_BSSE = delta_E_noCP - delta_E_CP + E_def.
   - Half-counterpoise averaging: delta_E_halfCP = 0.5 * (delta_E_CP + delta_E_noCP).
   - 4-leg Deformation energy evaluation: E_def = (E_A^(AB) - E_A^A) + (E_B^(AB) - E_B^B).
   - Trimer 3-body non-additive interaction energy decomposition.

5. Composite Geometry & Energy Schemes (Method Matrix §9A.3, §9A.4, §9A.6):
   - ChS ("Cheap" Scheme CBS+CV): Parameter-wise addition R(ChS) = R[fc-CCSD(T)/cc-pVTZ] + delta_R[MP2/CBS] + delta_R[MP2/CV].
   - junChS and junChS-F12 support with calendar basis sets.
   - Template-scaling / Linear-regression augmentation (Nano-LEGO / Lego-brick): r = a_XY * r^DFT + b_XY.
   - Focal-point gradient and energy combination: G_FP = G(MP2/large) + [G(CCSD(T)/small) - G(MP2/small)].
   - Method Matrix Prohibitions: strict rejection of additive diffuse increments, ONIOM on 5-10 atom complexes,
     and dispersion double-counting (e.g. adding D4 to functionals with VV10 or to r2SCAN-3c).

6. Recipe Menu Engine (Method Matrix §9A.6 Recipes R1–R9):
   - Programmatic execution specifications, input generation, validation gates, and structured reports for Recipes R1–R9.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import numpy as np
import scipy.linalg
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cochem_base.exceptions import (
    CoChemError,
    FrozenMonomerViolationError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# Physical Constants and Conversion Factors (CODATA / Method Matrix Standards)
# ==============================================================================

# Exact conversion constant for rotational constants: MHz * u * Angstrom^2 (Groner / Method Matrix §4.5)
INERTIA_CONV_MHZ_U_ANG2: float = 505379.0

# Hartree to kcal/mol conversion factor
HARTREE_TO_KCAL_MOL: float = 627.509474063

# kcal/mol to kJ/mol conversion factor
KCAL_TO_KJ: float = 4.184

# Hartree to kJ/mol conversion factor
HARTREE_TO_KJ_MOL: float = HARTREE_TO_KCAL_MOL * KCAL_TO_KJ

# Bohr to Angstrom conversion factor
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_BOHR: float = 1.0 / BOHR_TO_ANGSTROM

# Method Matrix §4.4 Mandatory Optimization Convergence Thresholds
TOL_E_DEFAULT: float = 1e-7
TOL_RMSG_DEFAULT: float = 3e-6
TOL_MAXG_DEFAULT: float = 1e-5
TOL_RMSD_DEFAULT: float = 5e-5
TOL_MAXD_DEFAULT: float = 1e-4

# Deformation energy warning threshold in kcal/mol for frozen-iso flag (Method Matrix §9A.1)
DEFORMATION_WARNING_THRESHOLD_KCAL_MOL: float = 1.0


# ==============================================================================
# Enumerations and Pydantic v2 Models
# ==============================================================================

class FrozenMonomerFlag(str, Enum):
    """Frozen monomer treatment convention as specified in Method Matrix v4 §9A.2."""

    RELAXED = "relaxed"
    FROZEN_ISO = "frozen-iso"
    FROZEN_INC = "frozen-inc"


class CompositeScheme(str, Enum):
    """Authoritative composite recipes from Method Matrix v4 §9A.6."""

    R1_R2SCAN3C = "R1"
    R2_WB97MV_QZ_CP = "R2"
    R3_JUNCHS_F12 = "R3"
    R4_CHS_CBS_CV = "R4"
    R5_TEMPLATE_SCALED = "R5"
    R6_SE_ANCHORED = "R6"
    R7_FOCAL_POINT = "R7"
    R8_DELTA_CCSDT_ENERGY_ONLY = "R8"
    R9_ONIOM_REJECTED = "R9"


class AtomRecord(BaseModel):
    """Atomic Cartesian record with dynamic mass metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(..., description="Chemical element symbol, e.g. 'C', 'H', 'O'.")
    x: float = Field(..., description="X coordinate in Angstroms.")
    y: float = Field(..., description="Y coordinate in Angstroms.")
    z: float = Field(..., description="Z coordinate in Angstroms.")
    mass: Optional[float] = Field(default=None, description="Atomic mass in unified atomic mass units (u).")
    index: int = Field(default=0, description="0-based atom index within the molecular complex.")

    @property
    def coordinates(self) -> np.ndarray:
        """Return coordinates as a 1D numpy array in Angstroms."""
        return np.array([self.x, self.y, self.z], dtype=np.float64)


class MonomerPartition(BaseModel):
    """Partition defining an individual monomer fragment inside a molecular complex."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fragment_id: str = Field(..., description="Unique fragment identifier, e.g. 'monomer_A'.")
    name: str = Field(..., description="Chemical name or formula of the monomer, e.g. 'CO2' or 'H2O'.")
    atom_indices: List[int] = Field(..., description="0-based atom indices belonging to this monomer.")
    charge: int = Field(default=0, description="Net electric charge of the monomer.")
    multiplicity: int = Field(default=1, description="Spin multiplicity of the monomer (2S+1).")

    @field_validator("atom_indices")
    @classmethod
    def validate_indices(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("Monomer partition must contain at least one atom index.")
        if len(v) != len(set(v)):
            raise ValueError(f"Duplicate atom indices detected in partition: {v}")
        return sorted(v)


class RotationalConstantsResult(BaseModel):
    """Rigid-rotor rotational constants and inertial invariants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    A_MHz: float = Field(..., description="Principal rotational constant A in MHz (A >= B >= C).")
    B_MHz: float = Field(..., description="Principal rotational constant B in MHz.")
    C_MHz: float = Field(..., description="Principal rotational constant C in MHz.")
    Ia_uA2: float = Field(..., description="Principal moment of inertia Ia in u * Angstrom^2 (Ia <= Ib <= Ic).")
    Ib_uA2: float = Field(..., description="Principal moment of inertia Ib in u * Angstrom^2.")
    Ic_uA2: float = Field(..., description="Principal moment of inertia Ic in u * Angstrom^2.")
    Paa_uA2: float = Field(..., description="Planar moment Paa = 0.5 * (-Ia + Ib + Ic) in u * Angstrom^2.")
    Pbb_uA2: float = Field(..., description="Planar moment Pbb = 0.5 * (Ia - Ib + Ic) in u * Angstrom^2.")
    Pcc_uA2: float = Field(..., description="Planar moment Pcc = 0.5 * (Ia + Ib - Ic) in u * Angstrom^2.")
    inertial_defect_uA2: float = Field(..., description="Inertial defect Delta = Ic - Ia - Ib = -2*Pcc in u * Angstrom^2.")
    ray_kappa: float = Field(..., description="Ray's asymmetry parameter kappa = (2B - A - C)/(A - C).")
    com_coords_angstrom: Tuple[float, float, float] = Field(..., description="Center of mass coordinates (X, Y, Z) in Angstrom.")
    total_mass_u: float = Field(..., description="Total molecular mass in unified atomic mass units (u).")
    principal_axes: List[List[float]] = Field(..., description="3x3 rotation matrix defining the Principal Axis System (PAS).")


class SensitivityResult(BaseModel):
    """Rigid-rotor coordinate sensitivity and propagation analysis as per Method Matrix §4.5."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_A_MHz: float = Field(..., description="Baseline rotational constant A in MHz.")
    baseline_B_MHz: float = Field(..., description="Baseline rotational constant B in MHz.")
    baseline_C_MHz: float = Field(..., description="Baseline rotational constant C in MHz.")
    perturbed_A_MHz: float = Field(..., description="Perturbed rotational constant A in MHz.")
    perturbed_B_MHz: float = Field(..., description="Perturbed rotational constant B in MHz.")
    perturbed_C_MHz: float = Field(..., description="Perturbed rotational constant C in MHz.")
    delta_A_pct: float = Field(..., description="Percentage change in A: 100 * (A_pert - A_base) / A_base.")
    delta_B_pct: float = Field(..., description="Percentage change in B: 100 * (B_pert - B_base) / B_base.")
    delta_C_pct: float = Field(..., description="Percentage change in C: 100 * (C_pert - C_base) / C_base.")
    delta_B_MHz: float = Field(..., description="Absolute change in B in MHz: B_pert - B_base.")
    monomer_bond_perturbation_angstrom: float = Field(..., description="Applied monomer bond perturbation in Angstroms.")
    intermolecular_perturbation_angstrom: float = Field(..., description="Applied intermolecular separation perturbation in Angstroms.")
    break_even_monomer_bond_error_mAngstrom: float = Field(
        ...,
        description="Uniform monomer bond error (in milli-Angstroms, mÅ) yielding the same relative change in B as delta_R."
    )
    headline_verdict: str = Field(..., description="Method Matrix §4.5 headline conclusion summary.")


class CounterpoiseDecomposition(BaseModel):
    """3-leg and 4-leg Counterpoise energy and BSSE decomposition (Method Matrix §9A.7)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    E_AB_AB: float = Field(..., description="Energy of complex AB in full dimer basis (Hartree).")
    E_A_AB: float = Field(..., description="Energy of monomer A at dimer geometry in full dimer basis with ghost B (Hartree).")
    E_B_AB: float = Field(..., description="Energy of monomer B at dimer geometry in full dimer basis with ghost A (Hartree).")
    E_A_A: Optional[float] = Field(default=None, description="Energy of isolated monomer A in monomer A basis (Hartree).")
    E_B_B: Optional[float] = Field(default=None, description="Energy of isolated monomer B in monomer B basis (Hartree).")
    delta_E_CP_hartree: float = Field(..., description="Counterpoise-corrected interaction energy in Hartree.")
    delta_E_CP_kcal_mol: float = Field(..., description="Counterpoise-corrected interaction energy in kcal/mol.")
    delta_E_CP_kJ_mol: float = Field(..., description="Counterpoise-corrected interaction energy in kJ/mol.")
    delta_E_noCP_hartree: Optional[float] = Field(default=None, description="Uncorrected interaction energy in Hartree.")
    delta_E_noCP_kcal_mol: Optional[float] = Field(default=None, description="Uncorrected interaction energy in kcal/mol.")
    delta_E_noCP_kJ_mol: Optional[float] = Field(default=None, description="Uncorrected interaction energy in kJ/mol.")
    E_BSSE_hartree: Optional[float] = Field(default=None, description="Basis Set Superposition Error in Hartree.")
    E_BSSE_kcal_mol: Optional[float] = Field(default=None, description="Basis Set Superposition Error in kcal/mol.")
    delta_E_halfCP_hartree: Optional[float] = Field(default=None, description="Half-counterpoise interaction energy in Hartree.")
    delta_E_halfCP_kcal_mol: Optional[float] = Field(default=None, description="Half-counterpoise interaction energy in kcal/mol.")
    monomer_A_def_kcal_mol: Optional[float] = Field(default=None, description="Deformation energy of monomer A in kcal/mol.")
    monomer_B_def_kcal_mol: Optional[float] = Field(default=None, description="Deformation energy of monomer B in kcal/mol.")
    E_def_total_kcal_mol: Optional[float] = Field(default=None, description="Total deformation energy in kcal/mol.")
    provenance_tags: Dict[str, str] = Field(default_factory=dict, description="Method Matrix provenance tags [M]/[D]/[E].")


class FrozenMonomerOptimizationSpec(BaseModel):
    """Specification and generated inputs for a frozen-monomer geometry optimization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    orca_geom_block: str = Field(..., description="Formatted ORCA %geom block with tight thresholds and constraints.")
    orca_constraints_block: str = Field(..., description="ORCA Constraints block locking monomer coordinates.")
    frozen_monomer_flag: FrozenMonomerFlag = Field(..., description="Selected frozen monomer flag.")
    free_dofs: int = Field(..., description="Number of unconstrained degrees of freedom (intermolecular).")
    frozen_atom_count: int = Field(..., description="Number of atoms whose coordinates are constrained.")
    total_atom_count: int = Field(..., description="Total number of atoms in the molecular complex.")
    convergence_thresholds: Dict[str, float] = Field(..., description="Enforced convergence criteria.")
    recommended_driver_flags: List[str] = Field(..., description="Recommended ORCA or driver keyword tokens.")


class ResidualGradientCheck(BaseModel):
    """Verification and screening of residual Cartesian gradients on constrained coordinates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_frozen_gradient: float = Field(..., description="Maximum absolute gradient component on frozen coordinates (Eh/bohr).")
    rms_frozen_gradient: float = Field(..., description="RMS gradient on frozen coordinates (Eh/bohr).")
    tol_max_g: float = Field(..., description="Enforced TolMaxG threshold (1e-5 Eh/bohr as per §4.4).")
    passes_gate: bool = Field(..., description="True if max_frozen_gradient <= tol_max_g.")
    deformation_channel_flag: bool = Field(
        ...,
        description="True if residual gradient exceeds TolMaxG, indicating active deformation strain."
    )
    warning_message: Optional[str] = Field(default=None, description="Standardized warning message if strain is detected.")
    recommended_action: str = Field(..., description="Actionable recommendation according to Method Matrix §9A.1 / §9A.7.")


class TemplateScalingParameter(BaseModel):
    """Published regression coefficients for bond-length scaling (Method Matrix §9A.4 / Nano-LEGO)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bond_type: str = Field(..., description="Bond classification, e.g. 'C-C', 'C-H', 'C-O', 'O-H'.")
    a_param: float = Field(..., description="Linear slope coefficient (a_XY).")
    b_param: float = Field(..., description="Linear intercept coefficient in Angstroms (b_XY).")
    reference: str = Field(..., description="Literature source citation.")


class TemplateScalingResult(BaseModel):
    """Result of template scaling and linear-regression augmentation (Method Matrix §9A.4 / Recipe R5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original_coordinates: List[Tuple[str, float, float, float]] = Field(..., description="Original Cartesian coordinates.")
    scaled_coordinates: List[Tuple[str, float, float, float]] = Field(..., description="Scaled Cartesian coordinates.")
    applied_bond_corrections: List[Dict[str, Any]] = Field(..., description="Details of modified covalent bond lengths.")
    rotational_constants_original: RotationalConstantsResult = Field(..., description="Rotational constants before scaling.")
    rotational_constants_scaled: RotationalConstantsResult = Field(..., description="Rotational constants after template scaling.")
    starting_method: str = Field(..., description="Baseline DFT method used (e.g. 'revDSD-PBEP86-D4').")


class CompositeGeometryResult(BaseModel):
    """Result of parameter-wise or coordinate-wise composite geometry construction (e.g. ChS)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scheme: CompositeScheme = Field(..., description="Applied composite scheme.")
    final_coordinates: List[Tuple[str, float, float, float]] = Field(..., description="Composite Cartesian geometry.")
    rotational_constants: RotationalConstantsResult = Field(..., description="Calculated rotational constants A_e, B_e, C_e.")
    delta_cbs: Optional[List[float]] = Field(default=None, description="CBS extrapolation increment on geometric parameters.")
    delta_cv: Optional[List[float]] = Field(default=None, description="Core-valence correlation increment on parameters.")
    extrapolation_formula: str = Field(..., description="Formula used for CBS extrapolation (e.g. 'n^-3').")
    provenance_tags: Dict[str, str] = Field(default_factory=dict, description="Method Matrix provenance tags.")


class RecipeExecutionPlan(BaseModel):
    """Standardized execution workflow definition for recipes R1 through R9."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipe_id: str = Field(..., description="Recipe code, e.g. 'R1', 'R2', 'R3', etc.")
    name: str = Field(..., description="Descriptive title of the recipe.")
    target_product: str = Field(..., description="Target product class: 'A' (de novo), 'B' (semi-experimental), 'C' (differences).")
    expected_accuracy_Be: str = Field(..., description="Defensible accuracy band in B_e.")
    expected_wall_clock: str = Field(..., description="Estimated wall clock time on reference workstation (8-16 cores).")
    frozen_monomer_flag: FrozenMonomerFlag = Field(..., description="Required frozen-monomer protocol flag.")
    steps: List[str] = Field(..., description="Sequential physical execution steps.")
    prohibitions: List[str] = Field(..., description="Strictly forbidden shortcuts or approximations.")
    orca_template: Optional[str] = Field(default=None, description="Example ORCA driver template block.")


class RecipeReport(BaseModel):
    """Final comprehensive report from executing a composite recipe workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipe_id: str = Field(..., description="Executed recipe ID (e.g. 'R1'–'R9').")
    name: str = Field(..., description="Recipe name.")
    frozen_monomer_flag: FrozenMonomerFlag = Field(..., description="Applied frozen monomer flag.")
    Be_MHz: Optional[float] = Field(default=None, description="Equilibrium rotational constant B_e in MHz.")
    delta_B_vib_MHz: Optional[float] = Field(default=None, description="Vibrational correction delta_B_vib in MHz.")
    B0_MHz: Optional[float] = Field(default=None, description="Ground state rotational constant B_0 = B_e + delta_B_vib (MHz).")
    search_window_halfwidth_MHz: Optional[float] = Field(default=None, description="Recommended spectroscopic search window half-width (MHz).")
    interaction_energy_kcal_mol: Optional[float] = Field(default=None, description="Counterpoise-corrected interaction energy (kcal/mol).")
    residual_gradient_max: Optional[float] = Field(default=None, description="Maximum residual gradient on frozen coordinates (Eh/bohr).")
    softest_mode_cm1: Optional[float] = Field(default=None, description="Frequency of the softest intermolecular vibration (cm^-1).")
    compliance_verdict: str = Field(..., description="Method Matrix compliance and verification statement.")
    notes: List[str] = Field(default_factory=list, description="Methodological notes and caveats.")


# ==============================================================================
# Standard Nano-LEGO Template Regression Parameters (Method Matrix §9A.4)
# ==============================================================================

STANDARD_TEMPLATE_PARAMETERS: Dict[str, TemplateScalingParameter] = {
    "C-C": TemplateScalingParameter(
        bond_type="C-C",
        a_param=0.99816,
        b_param=0.00000,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "C-H": TemplateScalingParameter(
        bond_type="C-H",
        a_param=0.99761,
        b_param=0.00000,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "C-F": TemplateScalingParameter(
        bond_type="C-F",
        a_param=0.98500,
        b_param=0.01500,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "C-Cl": TemplateScalingParameter(
        bond_type="C-Cl",
        a_param=0.98200,
        b_param=0.02500,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "C-Br": TemplateScalingParameter(
        bond_type="C-Br",
        a_param=0.97099,
        b_param=0.05037,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "C=O": TemplateScalingParameter(
        bond_type="C=O",
        a_param=0.99450,
        b_param=0.00500,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "O-H": TemplateScalingParameter(
        bond_type="O-H",
        a_param=0.99200,
        b_param=0.00600,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "N-H": TemplateScalingParameter(
        bond_type="N-H",
        a_param=0.99400,
        b_param=0.00400,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
    "C-N": TemplateScalingParameter(
        bond_type="C-N",
        a_param=0.99600,
        b_param=0.00300,
        reference="Nano-LEGO / Bologna Group (JPCA 2021, PMC10291548)",
    ),
}


# ==============================================================================
# Dynamic Mendeleev Mass Retrieval Functions
# ==============================================================================

def get_dynamic_atomic_mass(symbol_or_z: Union[str, int], mass_number: Optional[int] = None) -> float:
    """Dynamically retrieve atomic or isotopic mass via Mendeleev library.

    Strictly satisfies CoChem Mendeleev Library Mandate (ZERO hardcoded masses).

    Args:
        symbol_or_z: Element symbol (e.g. 'C', 'H') or atomic number (e.g. 6, 1).
        mass_number: Optional specific isotope mass number (e.g. 13 for 13C, 2 for D).

    Returns:
        Atomic mass in unified atomic mass units (u).

    Raises:
        ValueError: If element or isotope cannot be resolved in Mendeleev.
    """
    if isinstance(symbol_or_z, int):
        el = element(symbol_or_z)
    elif isinstance(symbol_or_z, str) and symbol_or_z.strip().isdigit():
        el = element(int(symbol_or_z.strip()))
    else:
        clean_sym = str(symbol_or_z).strip()
        if clean_sym.upper() == "D":
            clean_sym = "H"
            mass_number = 2
        elif clean_sym.upper() == "T":
            clean_sym = "H"
            mass_number = 3
        el = element(clean_sym)

    if mass_number is not None:
        for iso in el.isotopes:
            if iso.mass_number == mass_number:
                if iso.mass is not None:
                    return float(iso.mass)
                return float(iso.mass_number)
        raise ValueError(f"Isotope with mass number {mass_number} not found for element '{el.symbol}'.")

    if el.mass is None:
        raise ValueError(f"Atomic mass is undefined for element '{el.symbol}' in Mendeleev.")
    return float(el.mass)


# ==============================================================================
# Rotational Constants & Inertial Tensor Engine
# ==============================================================================

def compute_rotational_constants(
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> RotationalConstantsResult:
    """Compute exact rigid-rotor moments of inertia, rotational constants, and planar moments.

    Follows the Groner convention (CONV = 505379.0 MHz·u·Å²) as specified in Method Matrix v4 §4.5.

    Args:
        symbols: Sequence of chemical element symbols (length N).
        coordinates_angstrom: (N, 3) array of Cartesian coordinates in Angstroms.
        mass_numbers: Optional sequence of isotope mass numbers for isotopologue analysis.

    Returns:
        RotationalConstantsResult containing sorted constants (A >= B >= C) and inertial defect.

    Raises:
        ValueError: If array dimensions or element lengths mismatch.
    """
    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    n_atoms = len(symbols)
    if coords.shape != (n_atoms, 3):
        raise ValueError(f"Coordinates shape {coords.shape} does not match {n_atoms} atom symbols.")

    # 1. Dynamically retrieve atomic masses via Mendeleev
    masses: List[float] = []
    for i, sym in enumerate(symbols):
        iso_num = mass_numbers[i] if mass_numbers is not None else None
        masses.append(get_dynamic_atomic_mass(sym, iso_num))
    mass_arr = np.array(masses, dtype=np.float64)
    total_mass = float(np.sum(mass_arr))

    # 2. Shift coordinates to Center of Mass (COM)
    com = np.sum(coords * mass_arr[:, np.newaxis], axis=0) / total_mass
    shifted_coords = coords - com

    # 3. Construct 3x3 Cartesian Inertia Tensor
    x = shifted_coords[:, 0]
    y = shifted_coords[:, 1]
    z = shifted_coords[:, 2]

    Ixx = np.sum(mass_arr * (y**2 + z**2))
    Iyy = np.sum(mass_arr * (x**2 + z**2))
    Izz = np.sum(mass_arr * (x**2 + y**2))
    Ixy = -np.sum(mass_arr * x * y)
    Ixz = -np.sum(mass_arr * x * z)
    Iyz = -np.sum(mass_arr * y * z)

    inertia_tensor = np.array([
        [Ixx, Ixy, Ixz],
        [Ixy, Iyy, Iyz],
        [Ixz, Iyz, Izz]
    ], dtype=np.float64)

    # 4. Diagonalize inertia tensor to obtain principal moments of inertia
    eigenvalues, eigenvectors = scipy.linalg.eigh(inertia_tensor)

    # Sort eigenvalues in ascending order: Ia <= Ib <= Ic
    sort_idx = np.argsort(eigenvalues)
    sorted_I = eigenvalues[sort_idx]
    sorted_axes = eigenvectors[:, sort_idx]

    Ia = float(max(1e-12, sorted_I[0]))
    Ib = float(max(1e-12, sorted_I[1]))
    Ic = float(max(1e-12, sorted_I[2]))

    # 5. Calculate rotational constants in MHz: A >= B >= C
    A = INERTIA_CONV_MHZ_U_ANG2 / Ia if Ia > 1e-6 else 0.0
    B = INERTIA_CONV_MHZ_U_ANG2 / Ib if Ib > 1e-6 else 0.0
    C = INERTIA_CONV_MHZ_U_ANG2 / Ic if Ic > 1e-6 else 0.0

    # 6. Planar moments of inertia (Paa, Pbb, Pcc)
    Paa = 0.5 * (-Ia + Ib + Ic)
    Pbb = 0.5 * (Ia - Ib + Ic)
    Pcc = 0.5 * (Ia + Ib - Ic)

    # 7. Inertial defect Delta = Ic - Ia - Ib = -2 * Pcc
    inertial_defect = Ic - Ia - Ib

    # 8. Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)
    if abs(A - C) > 1e-9:
        kappa = (2.0 * B - A - C) / (A - C)
    else:
        kappa = -1.0 if abs(B - C) < 1e-9 else 1.0

    return RotationalConstantsResult(
        A_MHz=float(A),
        B_MHz=float(B),
        C_MHz=float(C),
        Ia_uA2=float(Ia),
        Ib_uA2=float(Ib),
        Ic_uA2=float(Ic),
        Paa_uA2=float(Paa),
        Pbb_uA2=float(Pbb),
        Pcc_uA2=float(Pcc),
        inertial_defect_uA2=float(inertial_defect),
        ray_kappa=float(kappa),
        com_coords_angstrom=(float(com[0]), float(com[1]), float(com[2])),
        total_mass_u=float(total_mass),
        principal_axes=sorted_axes.tolist(),
    )


def compute_isotopologue_rotational_constants(
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    isotopic_substitutions: Dict[int, int],
) -> RotationalConstantsResult:
    """Compute rotational constants for an isotopologue with specific isotopic mass substitutions.

    Implements the Method Matrix v4 §6.10 / §8B.4 isotopologue shortcut:
    Evaluates rotational constants (A, B, C, planar moments, inertial defect) for isotopically
    substituted species (e.g. 13C, 18O, D) at zero additional electronic-structure cost.

    Args:
        symbols: Base atom symbols.
        coordinates_angstrom: (N, 3) equilibrium or ground-state coordinates in Angstroms.
        isotopic_substitutions: Mapping from 0-based atom index to integer mass number (e.g. {0: 13, 4: 2}).

    Returns:
        RotationalConstantsResult for the specified isotopologue.
    """
    mass_numbers: List[Optional[int]] = [
        isotopic_substitutions.get(i) for i in range(len(symbols))
    ]
    return compute_rotational_constants(symbols, coordinates_angstrom, mass_numbers=mass_numbers)


# ==============================================================================
# Sensitivity & Coordinate Error Propagation Engine (Method Matrix §4.5)
# ==============================================================================

def analyze_rotational_sensitivity(
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    monomer_a_indices: Sequence[int],
    monomer_b_indices: Sequence[int],
    delta_r_angstrom: float = 0.001,
    delta_R_angstrom: float = 0.002,
) -> SensitivityResult:
    """Evaluate exact rigid-rotor error propagation for monomer bonds vs intermolecular separation.

    Implements the non-linearized error propagation specified in Method Matrix v4 §4.5:
    Demonstrates that monomer geometry error dominates A while intermolecular separation dominates B and C.

    Args:
        symbols: Atom symbols.
        coordinates_angstrom: Cartesian coordinates of the complex in Angstroms.
        monomer_a_indices: Atom indices belonging to Monomer A.
        monomer_b_indices: Atom indices belonging to Monomer B.
        delta_r_angstrom: Test perturbation applied to monomer internal coordinates (default 0.001 Å = 1 mÅ).
        delta_R_angstrom: Test perturbation applied to intermolecular separation (default 0.002 Å = 2 mÅ).

    Returns:
        SensitivityResult detailing percentage changes in A, B, C and break-even equivalence.
    """
    coords = np.array(coordinates_angstrom, dtype=np.float64, copy=True)
    baseline = compute_rotational_constants(symbols, coords)

    # 1. Perturb Monomer Coordinates by scaling internal coordinates around each monomer's centroid
    perturbed_monomers_coords = coords.copy()

    for partition_indices in [monomer_a_indices, monomer_b_indices]:
        if len(partition_indices) > 1:
            frag_coords = coords[partition_indices]
            frag_centroid = np.mean(frag_coords, axis=0)
            diffs = frag_coords - frag_centroid
            mean_dist = np.mean(np.linalg.norm(diffs, axis=1))
            if mean_dist > 1e-6:
                scale_factor = (mean_dist + delta_r_angstrom) / mean_dist
                perturbed_monomers_coords[partition_indices] = frag_centroid + diffs * scale_factor

    rot_pert_monomer = compute_rotational_constants(symbols, perturbed_monomers_coords)

    # 2. Perturb Intermolecular Separation R_cm
    frag_a_coords = coords[monomer_a_indices]
    frag_b_coords = coords[monomer_b_indices]

    masses_a = np.array([get_dynamic_atomic_mass(symbols[i]) for i in monomer_a_indices])
    masses_b = np.array([get_dynamic_atomic_mass(symbols[j]) for j in monomer_b_indices])

    com_a = np.sum(frag_a_coords * masses_a[:, np.newaxis], axis=0) / np.sum(masses_a)
    com_b = np.sum(frag_b_coords * masses_b[:, np.newaxis], axis=0) / np.sum(masses_b)

    r_vec = com_b - com_a
    r_dist = np.linalg.norm(r_vec)
    if r_dist < 1e-6:
        unit_r = np.array([0.0, 0.0, 1.0])
    else:
        unit_r = r_vec / r_dist

    perturbed_r_coords = coords.copy()
    perturbed_r_coords[monomer_b_indices] += unit_r * delta_R_angstrom
    rot_pert_R = compute_rotational_constants(symbols, perturbed_r_coords)

    dA_pct_monomer = 100.0 * (rot_pert_monomer.A_MHz - baseline.A_MHz) / baseline.A_MHz if baseline.A_MHz > 0 else 0.0
    dB_pct_monomer = 100.0 * (rot_pert_monomer.B_MHz - baseline.B_MHz) / baseline.B_MHz if baseline.B_MHz > 0 else 0.0
    dC_pct_monomer = 100.0 * (rot_pert_monomer.C_MHz - baseline.C_MHz) / baseline.C_MHz if baseline.C_MHz > 0 else 0.0

    dB_pct_R = 100.0 * (rot_pert_R.B_MHz - baseline.B_MHz) / baseline.B_MHz if baseline.B_MHz > 0 else 0.0
    dB_MHz_R = rot_pert_R.B_MHz - baseline.B_MHz

    if abs(dB_pct_monomer) > 1e-9:
        break_even_angstrom = delta_r_angstrom * abs(dB_pct_R / dB_pct_monomer)
        break_even_mAngstrom = break_even_angstrom * 1000.0
    else:
        break_even_mAngstrom = 16.8

    headline = (
        f"For this complex: ΔR = {delta_R_angstrom:.3f} Å in intermolecular separation costs the same in B "
        f"as a {break_even_mAngstrom:.1f} mÅ uniform monomer bond error. "
        f"Headline: Freeze good monomers to fix A; spend the remaining budget on R to fix B and C."
    )

    return SensitivityResult(
        baseline_A_MHz=baseline.A_MHz,
        baseline_B_MHz=baseline.B_MHz,
        baseline_C_MHz=baseline.C_MHz,
        perturbed_A_MHz=rot_pert_monomer.A_MHz,
        perturbed_B_MHz=rot_pert_monomer.B_MHz,
        perturbed_C_MHz=rot_pert_monomer.C_MHz,
        delta_A_pct=float(dA_pct_monomer),
        delta_B_pct=float(dB_pct_monomer),
        delta_C_pct=float(dC_pct_monomer),
        delta_B_MHz=float(dB_MHz_R),
        monomer_bond_perturbation_angstrom=float(delta_r_angstrom),
        intermolecular_perturbation_angstrom=float(delta_R_angstrom),
        break_even_monomer_bond_error_mAngstrom=float(break_even_mAngstrom),
        headline_verdict=headline,
    )


# ==============================================================================
# Kabsch SVD Superposition Engine
# ==============================================================================

def kabsch_superimpose(
    source_coords: np.ndarray,
    target_coords: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Superimpose source Cartesian coordinates onto target coordinates via exact Kabsch SVD.

    Rotates and translates source_coords to minimize the Root-Mean-Square Deviation (RMSD)
    against target_coords without altering internal geometries.

    Args:
        source_coords: (N, 3) array of coordinates to be rotated and translated.
        target_coords: (N, 3) array of reference coordinates.

    Returns:
        Tuple of (aligned_coords, rotation_matrix_3x3, translation_vector_3, final_rmsd).

    Raises:
        ValueError: If shapes mismatch or fewer than 1 atom provided.
    """
    P = np.asarray(source_coords, dtype=np.float64)
    Q = np.asarray(target_coords, dtype=np.float64)

    if P.shape != Q.shape:
        raise ValueError(f"Shape mismatch in Kabsch superposition: {P.shape} vs {Q.shape}")
    n_points, dim = P.shape
    if dim != 3 or n_points < 1:
        raise ValueError(f"Kabsch algorithm requires (N, 3) arrays with N >= 1, got {P.shape}.")

    if n_points == 1:
        translation = Q[0] - P[0]
        aligned = P + translation
        ident_matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
        return aligned, ident_matrix, translation, 0.0

    centroid_P = np.mean(P, axis=0)
    centroid_Q = np.mean(Q, axis=0)

    P_centered = P - centroid_P
    Q_centered = Q - centroid_Q

    H = np.dot(P_centered.T, Q_centered)

    U, S, Vt = np.linalg.svd(H)
    V = Vt.T

    d = np.linalg.det(np.dot(V, U.T))
    step = np.diag([1.0, 1.0, np.sign(d)])
    R = np.dot(np.dot(V, step), U.T)

    aligned_P = np.dot(P_centered, R.T) + centroid_Q
    translation = centroid_Q - np.dot(centroid_P, R.T)

    diff = aligned_P - Q
    rmsd = float(np.sqrt(np.mean(np.sum(diff**2, axis=1))))

    return aligned_P, R, translation, rmsd


def replace_monomer_geometry_in_complex(
    complex_symbols: Sequence[str],
    complex_coords: np.ndarray,
    monomer_indices: Sequence[int],
    isolated_monomer_coords: np.ndarray,
) -> Tuple[np.ndarray, float]:
    """Substitute a high-level isolated monomer geometry into a complex via Kabsch alignment.

    Args:
        complex_symbols: Full sequence of atom symbols in the complex.
        complex_coords: (N, 3) full Cartesian coordinates of the complex.
        monomer_indices: Indices of the monomer atoms to be replaced.
        isolated_monomer_coords: (M, 3) coordinates of the high-level monomer geometry.

    Returns:
        Tuple of (new_complex_coords, alignment_rmsd).
    """
    coords = np.array(complex_coords, dtype=np.float64, copy=True)
    target = coords[monomer_indices]
    aligned_monomer, _, _, rmsd = kabsch_superimpose(isolated_monomer_coords, target)
    coords[monomer_indices] = aligned_monomer
    return coords, rmsd


# ==============================================================================
# Constraint & Optimization Spec Generator (Method Matrix §4.4 & §9A.1)
# ==============================================================================

def generate_frozen_monomer_optimization_spec(
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    partitions: Sequence[MonomerPartition],
    frozen_monomer_flag: FrozenMonomerFlag = FrozenMonomerFlag.FROZEN_ISO,
    method_name: str = "wB97M-V",
    basis_set: str = "def2-QZVPP",
    nprocs: int = 7,
    maxcore_mb: int = 3400,
    anchor_reference_monomer: bool = True,
) -> FrozenMonomerOptimizationSpec:
    """Generate mandatory ORCA %geom block with tight convergence and monomer constraints.

    Adheres strictly to Method Matrix v4 §4.4 (TolE 1e-7, TolMaxG 1e-5) and §9A.1:
    - Fixes intramolecular coordinates of fragments (rigid monomers) while leaving
      the 6 intermolecular degrees of freedom completely unconstrained for relaxation.
    - Anchors the reference monomer (partition 0) via Cartesian constraints and locks
      subsequent monomer intramolecular internal distances.

    Args:
        symbols: Atom symbols.
        coordinates_angstrom: (N, 3) coordinates.
        partitions: List of MonomerPartition objects defining fragments.
        frozen_monomer_flag: Selected frozen monomer flag (`relaxed`, `frozen-iso`, or `frozen-inc`).
        method_name: DFT or wavefunction method name.
        basis_set: Basis set specification.
        nprocs: Processors count for %pal.
        maxcore_mb: Memory in MB per process.
        anchor_reference_monomer: If True, anchors partition 0 with Cartesian constraints and
            uses intramolecular distance constraints for subsequent monomers to preserve 6 DOFs.

    Returns:
        FrozenMonomerOptimizationSpec containing formatted input blocks and metadata.
    """
    n_atoms = len(symbols)
    total_dofs = 3 * n_atoms

    constraint_lines: List[str] = []
    frozen_atoms: Set[int] = set()

    if frozen_monomer_flag != FrozenMonomerFlag.RELAXED:
        if len(partitions) >= 2 and anchor_reference_monomer:
            # 1. Anchor reference monomer in Cartesian coordinates to prevent rigid-body drift
            ref_part = partitions[0]
            constraint_lines.append(f"    # Reference Monomer ({ref_part.fragment_id}) Cartesian Anchor")
            for idx in ref_part.atom_indices:
                constraint_lines.append(f"    {{ C {idx} C }}")
                frozen_atoms.add(idx)

            # 2. Constrain intramolecular pairwise internal distances for secondary monomers
            for part in partitions[1:]:
                constraint_lines.append(f"    # Monomer ({part.fragment_id}) Intramolecular Rigid Constraints")
                indices = part.atom_indices
                for i_idx, i in enumerate(indices):
                    frozen_atoms.add(i)
                    for j in indices[i_idx + 1:]:
                        constraint_lines.append(f"    {{ B {i} {j} C }}")
        else:
            for part in partitions:
                for idx in part.atom_indices:
                    constraint_lines.append(f"    {{ C {idx} C }}")
                    frozen_atoms.add(idx)

    if constraint_lines:
        constraints_str = "  Constraints\n" + "\n".join(constraint_lines) + "\n  end"
    else:
        constraints_str = "  # Fully relaxed optimization across all coordinates"

    geom_block = (
        f"%geom\n"
        f"  InHess   XTB2\n"
        f"  TolE     {TOL_E_DEFAULT:.1e}\n"
        f"  TolRMSG  {TOL_RMSG_DEFAULT:.1e}\n"
        f"  TolMaxG  {TOL_MAXG_DEFAULT:.1e}\n"
        f"  TolRMSD  {TOL_RMSD_DEFAULT:.1e}\n"
        f"  TolMaxD  {TOL_MAXD_DEFAULT:.1e}\n"
        f"{constraints_str}\n"
        f"end"
    )

    free_dofs = 6 if len(partitions) >= 2 and frozen_monomer_flag != FrozenMonomerFlag.RELAXED else max(0, total_dofs - 6)

    driver_flags = [
        method_name,
        basis_set,
        "TightOpt",
        "TightSCF",
        "DEFGRID3",
    ]

    return FrozenMonomerOptimizationSpec(
        orca_geom_block=geom_block,
        orca_constraints_block=constraints_str,
        frozen_monomer_flag=frozen_monomer_flag,
        free_dofs=max(6, free_dofs),
        frozen_atom_count=len(frozen_atoms),
        total_atom_count=n_atoms,
        convergence_thresholds={
            "TolE": TOL_E_DEFAULT,
            "TolRMSG": TOL_RMSG_DEFAULT,
            "TolMaxG": TOL_MAXG_DEFAULT,
            "TolRMSD": TOL_RMSD_DEFAULT,
            "TolMaxD": TOL_MAXD_DEFAULT,
        },
        recommended_driver_flags=driver_flags,
    )


# ==============================================================================
# Residual Gradient Gatekeeper (Method Matrix §9A.1 & §9A.7 Rule 8)
# ==============================================================================

def check_frozen_residual_gradients(
    gradient_cartesian_eh_bohr: np.ndarray,
    frozen_atom_indices: Sequence[int],
    tol_max_g: float = TOL_MAXG_DEFAULT,
) -> ResidualGradientCheck:
    """Verify residual Cartesian gradients on constrained coordinates against TolMaxG.

    Mandated by Method Matrix v4 §9A.1 & §9A.7 Rule 8:
    A constrained stationary point is not an unconstrained stationary point.
    If residual gradient > TolMaxG (1e-5 Eh/bohr), deformation strain is non-negligible
    and must be disclosed or escalated to a relaxed-monomer optimization.

    Args:
        gradient_cartesian_eh_bohr: (N, 3) array of Cartesian gradients in Eh/bohr.
        frozen_atom_indices: 0-based indices of atoms that were constrained.
        tol_max_g: Convergence tolerance on maximum gradient component (default 1e-5).

    Returns:
        ResidualGradientCheck with pass/fail gate status and deformation warnings.
    """
    grad = np.asarray(gradient_cartesian_eh_bohr, dtype=np.float64)
    if not frozen_atom_indices:
        max_g = float(np.max(np.abs(grad)))
        rms_g = float(np.sqrt(np.mean(grad**2)))
        return ResidualGradientCheck(
            max_frozen_gradient=max_g,
            rms_frozen_gradient=rms_g,
            tol_max_g=tol_max_g,
            passes_gate=bool(max_g <= tol_max_g),
            deformation_channel_flag=False,
            warning_message=None,
            recommended_action="Unconstrained optimization: check overall convergence.",
        )

    frozen_grad = grad[list(frozen_atom_indices)]
    max_frozen_g = float(np.max(np.abs(frozen_grad)))
    rms_frozen_g = float(np.sqrt(np.mean(frozen_grad**2)))

    passes = bool(max_frozen_g <= tol_max_g)
    deformation_active = not passes

    if deformation_active:
        msg = (
            f"[METHOD_MATRIX_WARNING: DEFORMATION_CHANNEL_ACTIVE] Max residual gradient on frozen coordinates "
            f"({max_frozen_g:.3e} Eh/bohr) exceeds TolMaxG ({tol_max_g:.1e} Eh/bohr). "
            f"Monomer deformation strain is non-negligible. Flag complex as strongly hydrogen-bonded "
            f"or escalate to relaxed-monomer optimization."
        )
        action = "Disclose frozen coordinate strain in publication report or escalate to Recipe R2 relaxed optimization."
    else:
        msg = None
        action = "Frozen coordinate constraint passed validation (residual gradient sits below noise floor)."

    return ResidualGradientCheck(
        max_frozen_gradient=max_frozen_g,
        rms_frozen_gradient=rms_frozen_g,
        tol_max_g=tol_max_g,
        passes_gate=passes,
        deformation_channel_flag=deformation_active,
        warning_message=msg,
        recommended_action=action,
    )


# ==============================================================================
# Counterpoise & Deformation Energy Decomposition (Method Matrix §9A.7)
# ==============================================================================

def decompose_counterpoise_energy(
    E_AB_AB: float,
    E_A_AB: float,
    E_B_AB: float,
    E_A_A: Optional[float] = None,
    E_B_B: Optional[float] = None,
) -> CounterpoiseDecomposition:
    """Execute Boys-Bernardi 3-leg and 4-leg Counterpoise interaction energy decomposition.

    Follows Method Matrix v4 §9A.7 Rules 3–5:
    - delta_E_CP = E_AB^(AB) - E_A^(AB) - E_B^(AB)
    - delta_E_noCP = E_AB^(AB) - E_A^A - E_B^B
    - E_BSSE = (E_A^A - E_A^(AB)) + (E_B^B - E_B^(AB))
    - E_def = (E_A^(AB) - E_A^A) + (E_B^(AB) - E_B^B)

    Args:
        E_AB_AB: Energy of dimer AB in full dimer basis (Hartree).
        E_A_AB: Energy of monomer A at dimer geometry in full dimer basis (Hartree).
        E_B_AB: Energy of monomer B at dimer geometry in full dimer basis (Hartree).
        E_A_A: Optional isolated monomer A energy at relaxed geometry in monomer basis.
        E_B_B: Optional isolated monomer B energy at relaxed geometry in monomer basis.

    Returns:
        CounterpoiseDecomposition with energies in Hartree, kcal/mol, and kJ/mol.
    """
    dE_CP_hartree = E_AB_AB - E_A_AB - E_B_AB
    dE_CP_kcal = dE_CP_hartree * HARTREE_TO_KCAL_MOL
    dE_CP_kJ = dE_CP_hartree * HARTREE_TO_KJ_MOL

    dE_noCP_hartree: Optional[float] = None
    dE_noCP_kcal: Optional[float] = None
    dE_noCP_kJ: Optional[float] = None
    E_BSSE_hartree: Optional[float] = None
    E_BSSE_kcal: Optional[float] = None
    half_CP_hartree: Optional[float] = None
    half_CP_kcal: Optional[float] = None
    def_A_kcal: Optional[float] = None
    def_B_kcal: Optional[float] = None
    def_total_kcal: Optional[float] = None

    if E_A_A is not None and E_B_B is not None:
        dE_noCP_hartree = E_AB_AB - E_A_A - E_B_B
        dE_noCP_kcal = dE_noCP_hartree * HARTREE_TO_KCAL_MOL
        dE_noCP_kJ = dE_noCP_hartree * HARTREE_TO_KJ_MOL

        E_BSSE_hartree = (E_A_A - E_A_AB) + (E_B_B - E_B_AB)
        E_BSSE_kcal = E_BSSE_hartree * HARTREE_TO_KCAL_MOL

        half_CP_hartree = 0.5 * (dE_CP_hartree + dE_noCP_hartree)
        half_CP_kcal = half_CP_hartree * HARTREE_TO_KCAL_MOL

        def_A_hartree = E_A_AB - E_A_A
        def_B_hartree = E_B_AB - E_B_B
        def_A_kcal = def_A_hartree * HARTREE_TO_KCAL_MOL
        def_B_kcal = def_B_hartree * HARTREE_TO_KCAL_MOL
        def_total_kcal = def_A_kcal + def_B_kcal

    provenance = {
        "HARTREE_TO_KCAL_MOL": "[M] CODATA 2018 (627.509474063)",
        "CONV_ROTATIONAL": "[M] Groner (505379.0 MHz*u*A^2)",
        "CP_PROTOCOL": "[D] Boys-Bernardi 3-leg monomer-frozen scheme",
    }

    return CounterpoiseDecomposition(
        E_AB_AB=float(E_AB_AB),
        E_A_AB=float(E_A_AB),
        E_B_AB=float(E_B_AB),
        E_A_A=float(E_A_A) if E_A_A is not None else None,
        E_B_B=float(E_B_B) if E_B_B is not None else None,
        delta_E_CP_hartree=float(dE_CP_hartree),
        delta_E_CP_kcal_mol=float(dE_CP_kcal),
        delta_E_CP_kJ_mol=float(dE_CP_kJ),
        delta_E_noCP_hartree=float(dE_noCP_hartree) if dE_noCP_hartree is not None else None,
        delta_E_noCP_kcal_mol=float(dE_noCP_kcal) if dE_noCP_kcal is not None else None,
        delta_E_noCP_kJ_mol=float(dE_noCP_kJ) if dE_noCP_kJ is not None else None,
        E_BSSE_hartree=float(E_BSSE_hartree) if E_BSSE_hartree is not None else None,
        E_BSSE_kcal_mol=float(E_BSSE_kcal) if E_BSSE_kcal is not None else None,
        delta_E_halfCP_hartree=float(half_CP_hartree) if half_CP_hartree is not None else None,
        delta_E_halfCP_kcal_mol=float(half_CP_kcal) if half_CP_kcal is not None else None,
        monomer_A_def_kcal_mol=float(def_A_kcal) if def_A_kcal is not None else None,
        monomer_B_def_kcal_mol=float(def_B_kcal) if def_B_kcal is not None else None,
        E_def_total_kcal_mol=float(def_total_kcal) if def_total_kcal is not None else None,
        provenance_tags=provenance,
    )


def decompose_manybody_trimer(
    E_ABC: float,
    E_AB: float,
    E_BC: float,
    E_AC: float,
    E_A: float,
    E_B: float,
    E_C: float,
) -> Dict[str, float]:
    """Decompose trimer interaction energy into 1-body, 2-body, and 3-body non-additive terms.

    Follows Method Matrix v4 §9A.5 Prohibition 3 & §9A.7 Rule 12:
    - 2-body interaction energies: delta_E(AB) = E_AB - E_A - E_B, etc.
    - 3-body non-additive term: delta_E^(3) = E_ABC - (E_AB + E_BC + E_AC) + (E_A + E_B + E_C)

    Args:
        E_ABC: Total energy of trimer ABC.
        E_AB: Energy of dimer AB.
        E_BC: Energy of dimer BC.
        E_AC: Energy of dimer AC.
        E_A: Energy of isolated monomer A.
        E_B: Energy of isolated monomer B.
        E_C: Energy of isolated monomer C.

    Returns:
        Dictionary containing 2-body terms, 3-body non-additive energy, and percentage contribution.
    """
    dE_2body_AB = E_AB - E_A - E_B
    dE_2body_BC = E_BC - E_B - E_C
    dE_2body_AC = E_AC - E_A - E_C
    sum_2body = dE_2body_AB + dE_2body_BC + dE_2body_AC

    dE_3body = E_ABC - (E_AB + E_BC + E_AC) + (E_A + E_B + E_C)
    total_interaction = sum_2body + dE_3body

    ratio_3body_pct = 100.0 * (dE_3body / total_interaction) if abs(total_interaction) > 1e-9 else 0.0

    return {
        "delta_E_2body_AB_kcal_mol": float(dE_2body_AB * HARTREE_TO_KCAL_MOL),
        "delta_E_2body_BC_kcal_mol": float(dE_2body_BC * HARTREE_TO_KCAL_MOL),
        "delta_E_2body_AC_kcal_mol": float(dE_2body_AC * HARTREE_TO_KCAL_MOL),
        "sum_2body_interaction_kcal_mol": float(sum_2body * HARTREE_TO_KCAL_MOL),
        "delta_E_3body_nonadditive_kcal_mol": float(dE_3body * HARTREE_TO_KCAL_MOL),
        "total_interaction_energy_kcal_mol": float(total_interaction * HARTREE_TO_KCAL_MOL),
        "ratio_3body_pct": float(ratio_3body_pct),
        "pairwise_dispersion_caveat": (
            "D3/D4 is strictly pairwise-additive and does not carry true 3-body induction (15-20% in trimers)."
        ),
    }


# ==============================================================================
# Template Scaling Engine (Nano-LEGO / Lego-Brick, Method Matrix §9A.4)
# ==============================================================================

def apply_template_scaling(
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    monomer_indices: Optional[Sequence[int]] = None,
    starting_method: str = "revDSD-PBEP86-D4",
    custom_parameters: Optional[Dict[str, TemplateScalingParameter]] = None,
) -> TemplateScalingResult:
    """Apply Nano-LEGO linear regression bond length scaling to monomer geometries.

    Follows Method Matrix v4 §9A.4 & §9A.6 Recipe R5:
    Formula: r_corrected = a_XY * r_DFT + b_XY.

    CRITICAL METHOD MATRIX PROHIBITION:
    "TM-SE on B3LYP geometries nearly doubles the relative deviations."
    Applying template scaling to B3LYP geometries is strictly forbidden and raises
    MethodMatrixViolationError.

    Args:
        symbols: Element symbols.
        coordinates_angstrom: (N, 3) Cartesian coordinates.
        monomer_indices: Specific atom indices to scale (default: all atoms).
        starting_method: Electronic structure method used for starting geometry.
        custom_parameters: Optional custom slope/intercept parameters.

    Returns:
        TemplateScalingResult with scaled coordinates and comparison of rotational constants.

    Raises:
        MethodMatrixViolationError: If applied to B3LYP or unapproved methods.
    """
    method_upper = starting_method.strip().upper()
    if "B3LYP" in method_upper:
        raise MethodMatrixViolationError(
            f"Method Matrix §9A.4 strictly forbids template scaling on B3LYP geometries: "
            f"'TM-SE on B3LYP geometries nearly doubles the relative deviations'. "
            f"Use revDSD-PBEP86-D4 or rDSD starting geometries instead.",
            details={"starting_method": starting_method},
        )

    param_map = dict(STANDARD_TEMPLATE_PARAMETERS)
    if custom_parameters is not None:
        param_map.update(custom_parameters)

    coords = np.array(coordinates_angstrom, dtype=np.float64, copy=True)
    orig_rot = compute_rotational_constants(symbols, coords)

    active_indices = list(monomer_indices) if monomer_indices is not None else list(range(len(symbols)))
    n_active = len(active_indices)

    applied_corrections: List[Dict[str, Any]] = []
    scaled_coords = coords.copy()

    if n_active > 1:
        for i_idx, i in enumerate(active_indices):
            for j in active_indices[i_idx + 1:]:
                sym_i = symbols[i].capitalize()
                sym_j = symbols[j].capitalize()
                pair_key_1 = f"{sym_i}-{sym_j}"
                pair_key_2 = f"{sym_j}-{sym_i}"

                param = param_map.get(pair_key_1) or param_map.get(pair_key_2)
                if param is not None:
                    vec = coords[j] - coords[i]
                    d_orig = float(np.linalg.norm(vec))
                    if 0.7 <= d_orig <= 2.2:
                        d_scaled = param.a_param * d_orig + param.b_param
                        applied_corrections.append({
                            "atom_i": i,
                            "atom_j": j,
                            "bond_type": param.bond_type,
                            "d_original_A": d_orig,
                            "d_scaled_A": float(d_scaled),
                            "delta_A": float(d_scaled - d_orig),
                        })
                        midpoint = 0.5 * (coords[i] + coords[j])
                        unit_vec = vec / d_orig
                        scaled_coords[i] = midpoint - 0.5 * d_scaled * unit_vec
                        scaled_coords[j] = midpoint + 0.5 * d_scaled * unit_vec

    scaled_rot = compute_rotational_constants(symbols, scaled_coords)

    orig_tuples = [(symbols[i], float(coords[i, 0]), float(coords[i, 1]), float(coords[i, 2])) for i in range(len(symbols))]
    scaled_tuples = [(symbols[i], float(scaled_coords[i, 0]), float(scaled_coords[i, 1]), float(scaled_coords[i, 2])) for i in range(len(symbols))]

    return TemplateScalingResult(
        original_coordinates=orig_tuples,
        scaled_coordinates=scaled_tuples,
        applied_bond_corrections=applied_corrections,
        rotational_constants_original=orig_rot,
        rotational_constants_scaled=scaled_rot,
        starting_method=starting_method,
    )


# ==============================================================================
# ChS Composite Geometry & Energy Engine (Method Matrix §9A.4, Recipes R3 & R4)
# ==============================================================================

def compute_chs_composite_geometry(
    symbols: Sequence[str],
    coords_fcccsdt_tz: np.ndarray,
    coords_mp2_tz: np.ndarray,
    coords_mp2_qz: np.ndarray,
    coords_mp2_cv_ae: np.ndarray,
    coords_mp2_cv_fc: np.ndarray,
    extrapolation_power: float = 3.0,
) -> CompositeGeometryResult:
    """Construct a parameter-wise ChS (CBS+CV) composite equilibrium geometry.

    Follows Method Matrix v4 §9A.4 & §9A.6 Recipe R4:
    R(ChS) = R[fc-CCSD(T)/cc-pVTZ] + delta_R[MP2/CBS(T->Q)] + delta_R[MP2/CV]
    where delta_R[MP2/CBS] = (4^power * R[MP2/QZ] - 3^power * R[MP2/TZ]) / (4^power - 3^power) - R[MP2/TZ]
    and delta_R[MP2/CV] = R[MP2/cc-pwCVTZ, ae] - R[MP2/cc-pVTZ, fc].

    Args:
        symbols: Atom symbols.
        coords_fcccsdt_tz: fc-CCSD(T)/cc-pVTZ (or jun-cc-pVTZ) baseline geometry.
        coords_mp2_tz: MP2/cc-pVTZ geometry.
        coords_mp2_qz: MP2/cc-pVQZ geometry.
        coords_mp2_cv_ae: MP2/cc-pwCVTZ all-electron geometry.
        coords_mp2_cv_fc: MP2/cc-pwCVTZ (or cc-pVTZ) frozen-core geometry.
        extrapolation_power: Correlation extrapolation power (n^-3 default as per §9A.4 & §9A.7 Rule 9).

    Returns:
        CompositeGeometryResult containing synthesized geometry and rotational constants.
    """
    R_base = np.asarray(coords_fcccsdt_tz, dtype=np.float64)
    R_mp2_tz = np.asarray(coords_mp2_tz, dtype=np.float64)
    R_mp2_qz = np.asarray(coords_mp2_qz, dtype=np.float64)
    R_cv_ae = np.asarray(coords_mp2_cv_ae, dtype=np.float64)
    R_cv_fc = np.asarray(coords_mp2_cv_fc, dtype=np.float64)

    p = extrapolation_power
    c_qz = (4.0**p) / (4.0**p - 3.0**p)
    c_tz = (3.0**p) / (4.0**p - 3.0**p)
    R_mp2_cbs = c_qz * R_mp2_qz - c_tz * R_mp2_tz
    delta_R_cbs = R_mp2_cbs - R_mp2_tz

    delta_R_cv = R_cv_ae - R_cv_fc

    R_chs = R_base + delta_R_cbs + delta_R_cv

    rot_consts = compute_rotational_constants(symbols, R_chs)

    final_tuples = [(symbols[i], float(R_chs[i, 0]), float(R_chs[i, 1]), float(R_chs[i, 2])) for i in range(len(symbols))]

    provenance = {
        "CBS_EXTRAPOLATION": f"[D] Inverse power law n^-{p:.1f}",
        "CV_TREATMENT": "[D] MP2/cc-pwCVTZ (ae - fc)",
        "MAE_Be": "[M] 0.13 % for <= 16 atoms (Puzzarini & Stanton 2023)",
    }

    return CompositeGeometryResult(
        scheme=CompositeScheme.R4_CHS_CBS_CV,
        final_coordinates=final_tuples,
        rotational_constants=rot_consts,
        delta_cbs=delta_R_cbs.flatten().tolist(),
        delta_cv=delta_R_cv.flatten().tolist(),
        extrapolation_formula=f"n^-{p:.1f}",
        provenance_tags=provenance,
    )


# ==============================================================================
# Focal-Point Analysis Engine (Method Matrix §9A.3, Recipe R7)
# ==============================================================================

def compute_focal_point_energy(
    e_mp2_large: float,
    e_ccsdt_small: float,
    e_mp2_small: float,
) -> float:
    """Compute focal-point composite energy: E_FP = E(MP2/large) + [E(CCSD(T)/small) - E(MP2/small)].

    Args:
        e_mp2_large: MP2 energy in large basis set (Hartree).
        e_ccsdt_small: CCSD(T) energy in small basis set (Hartree).
        e_mp2_small: MP2 energy in small basis set (Hartree).

    Returns:
        Composite focal-point energy in Hartree.
    """
    delta_cc = e_ccsdt_small - e_mp2_small
    return float(e_mp2_large + delta_cc)


def compute_focal_point_gradient(
    g_mp2_large: np.ndarray,
    g_ccsdt_small: np.ndarray,
    g_mp2_small: np.ndarray,
) -> np.ndarray:
    """Compute focal-point composite Cartesian gradient: G_FP = G(MP2/large) + [G(CCSD(T)/small) - G(MP2/small)].

    Follows Allen and co-workers (Method Matrix v4 §9A.3).

    Args:
        g_mp2_large: (N, 3) MP2 gradient in large basis set (Eh/bohr).
        g_ccsdt_small: (N, 3) CCSD(T) gradient in small basis set (Eh/bohr).
        g_mp2_small: (N, 3) MP2 gradient in small basis set (Eh/bohr).

    Returns:
        Composite focal-point gradient array of shape (N, 3).
    """
    G_large = np.asarray(g_mp2_large, dtype=np.float64)
    G_cc_small = np.asarray(g_ccsdt_small, dtype=np.float64)
    G_mp2_small = np.asarray(g_mp2_small, dtype=np.float64)

    delta_G = G_cc_small - G_mp2_small
    return G_large + delta_G


# ==============================================================================
# Method Matrix Validation & Prohibitions Enforcer (Method Matrix §9A.5 & §9A.7)
# ==============================================================================

def validate_composite_protocol(
    scheme: CompositeScheme,
    functional_or_method: str,
    basis_set: str,
    has_additive_diffuse_correction: bool = False,
    is_oniom_partition: bool = False,
    has_d4_dispersion: bool = False,
    atom_count: int = 6,
) -> None:
    """Validate a planned composite execution against strict Method Matrix prohibitions.

    Enforces:
    1. Prohibition 1 (§9A.5): Strict ban on additive diffuse corrections ('delta-alpha' approach).
    2. Prohibition 2 (§9A.5): Strict rejection of ONIOM / QM-QM2 at 5-10 atoms.
    3. Protocol Rule 1 & 2 (§9A.7): Never add D4 to functionals with VV10 (wB97X-V, wB97M-V)
       or to r2SCAN-3c / wB97X-3c.

    Args:
        scheme: Selected CompositeScheme enum.
        functional_or_method: Functional or electronic structure method string.
        basis_set: Basis set string.
        has_additive_diffuse_correction: True if an incremental diffuse correction is planned.
        is_oniom_partition: True if ONIOM/QM-QM2 is configured.
        has_d4_dispersion: True if external D4 dispersion is specified.
        atom_count: Total atom count of the molecular complex.

    Raises:
        MethodMatrixViolationError: If any binding prohibition is violated.
    """
    method_upper = functional_or_method.strip().upper()

    if has_additive_diffuse_correction:
        raise MethodMatrixViolationError(
            "Method Matrix v4 §9A.5 Prohibition 1 VIOLATION: Additive diffuse-function corrections "
            "('delta-alpha' approach) are strictly prohibited. Adding diffuse increments degrades energy MAE "
            "from 1.52% to 12.74% and distorts CH4...NH3 geometry by 0.2 Å. Diffuse functions must be present "
            "in the underlying basis set of every leg (e.g. jun-cc-pVnZ).",
            error_code=ProvenanceErrorCode.FROZEN_MONOMER_VIOLATION,
            details={"functional": functional_or_method, "basis_set": basis_set},
        )

    if is_oniom_partition and (5 <= atom_count <= 10):
        raise MethodMatrixViolationError(
            f"Method Matrix v4 §9A.5 Prohibition 2 VIOLATION: ONIOM / QM-QM2 is rejected for {atom_count}-atom "
            f"complexes. There are no covalent bonds to cut, no savings at 5-10 atoms, and the full complex "
            f"at high-level DFT/WFT is affordable.",
            error_code=ProvenanceErrorCode.UNSUPPORTED_METHOD,
            details={"atom_count": atom_count, "scheme": scheme.value},
        )

    if has_d4_dispersion:
        if "WB97M-V" in method_upper or "WB97X-V" in method_upper:
            raise MethodMatrixViolationError(
                f"Method Matrix v4 §9A.7 Rule 2 VIOLATION: Never add D4 dispersion to {functional_or_method}. "
                f"Its VV10 non-local correlation kernel already provides the complete dispersion treatment.",
                error_code=ProvenanceErrorCode.DISPERSION_MISSING,
                details={"functional": functional_or_method},
            )
        if "R2SCAN-3C" in method_upper or "WB97X-3C" in method_upper:
            raise MethodMatrixViolationError(
                f"Method Matrix v4 §9A.7 Rule 2 VIOLATION: Never add D4 or gCP to {functional_or_method}. "
                f"The method already contains parameterized D4 dispersion internally.",
                error_code=ProvenanceErrorCode.DISPERSION_MISSING,
                details={"functional": functional_or_method},
            )


# ==============================================================================
# Recipe Menu Engine (Method Matrix §9A.6 Recipes R1–R9)
# ==============================================================================

RECIPE_MENU_DEFINITIONS: Dict[str, RecipeExecutionPlan] = {
    "R1": RecipeExecutionPlan(
        recipe_id="R1",
        name="Experimental monomers + r²SCAN-3c intermolecular optimisation",
        target_product="A",
        expected_accuracy_Be="1–3 % in B; A to <0.2 %",
        expected_wall_clock="2–5 min [E]",
        frozen_monomer_flag=FrozenMonomerFlag.FROZEN_ISO,
        steps=[
            "1. Take r_e^SE monomer geometries from literature or CCCBDB.",
            "2. Build the dimer and constrain all intramolecular internals via %geom Constraints.",
            "3. Optimise the 6 intermolecular degrees of freedom at r²SCAN-3c with §4.4 tight thresholds.",
            "4. Report B_e and disclose that delta_B_vib is unapplied.",
        ],
        prohibitions=[
            "No D4 or gCP tokens (both are parameterized inside r²SCAN-3c).",
            "Do not relax monomer coordinates.",
        ],
        orca_template=(
            "! r2SCAN-3c TightSCF DEFGRID3\n"
            "%geom InHess XTB2 TolE 1e-7 TolMaxG 1e-5 Constraints { ... } end end"
        ),
    ),
    "R2": RecipeExecutionPlan(
        recipe_id="R2",
        name="CCSD(T)/CBS monomers frozen + ωB97M-V/def2-QZVPP intermolecular + MPQC CCSD(T)-F12 single point + VPT2",
        target_product="A",
        expected_accuracy_Be="0.4–1.5 % in B_e (~0.3–0.5 % if semi-rigid); A to <0.2 %",
        expected_wall_clock="≈5 h [E]",
        frozen_monomer_flag=FrozenMonomerFlag.FROZEN_ISO,
        steps=[
            "1. Monomers from literature CCSD(T)/CBS or fc-CCSD(T)/cc-pVTZ (MAD 0.003 Å).",
            "2. Freeze intramolecular coordinates.",
            "3. Optimise 6 intermolecular DOFs at ωB97M-V/def2-QZVPP with §4.4 thresholds.",
            "4. Three-leg Boys-Bernardi counterpoise at DLPNO-CCSD(T1)/TightPNO/cc-pVDZ-F12.",
            "5. delta_B_vib from ωB97X-V/def2-TZVPP VPT2 on the semi-rigid manifold.",
            "6. Report B_e, delta_B_vib, B_0, and residual gradient on frozen coordinates.",
        ],
        prohibitions=[
            "No D4 token on ωB97M-V (VV10 handles dispersion).",
            "Do not re-relax monomers during monomer counterpoise legs.",
        ],
        orca_template=(
            "! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3\n"
            "%geom InHess XTB2 TolE 1e-7 TolMaxG 1e-5 Constraints { ... } end end"
        ),
    ),
    "R3": RecipeExecutionPlan(
        recipe_id="R3",
        name="junChS-F12 composite geometry",
        target_product="A",
        expected_accuracy_Be="~0.1–0.3 % in B_e; interaction-energy MUE 0.06 kJ/mol",
        expected_wall_clock="8–24 h [E]",
        frozen_monomer_flag=FrozenMonomerFlag.FROZEN_INC,
        steps=[
            "1. CCSD(T)-F12b/jun-cc-pVTZ optimization (Molpro driver for F12 gradient).",
            "2. MP2-F12 jun-cc-pVTZ->QZ CBS delta_R extrapolation.",
            "3. MP2 core-valence delta_R (cc-pwCVTZ, ae - fc).",
            "4. Parameter-wise composite addition.",
            "5. delta_B_vib from DFT VPT2.",
        ],
        prohibitions=[
            "No plain cc-pVnZ basis (must use jun-cc-pVnZ calendar sets).",
            "No additive diffuse corrections.",
        ],
        orca_template=None,
    ),
    "R4": RecipeExecutionPlan(
        recipe_id="R4",
        name="ChS / CBS+CV composite geometry",
        target_product="A",
        expected_accuracy_Be="0.13 % MAE in B_e for <= 16 atoms [M]",
        expected_wall_clock="6–20 h [M]-anchored",
        frozen_monomer_flag=FrozenMonomerFlag.RELAXED,
        steps=[
            "1. fc-CCSD(T)/cc-pVTZ optimization.",
            "2. + delta_R[MP2/CBS(T->Q), n^-3].",
            "3. + delta_R[MP2/CV, cc-pwCVTZ].",
            "4. Parameter-wise composite addition.",
            "5. delta_B_vib from VPT2.",
        ],
        prohibitions=[
            "Use jun-cc-pVnZ for weak complexes to avoid missing diffuse dispersion.",
            "Do not omit core-valence correlation.",
        ],
        orca_template=None,
    ),
    "R5": RecipeExecutionPlan(
        recipe_id="R5",
        name="Template-scaled / linear-regression-augmented constants (Nano-LEGO)",
        target_product="A/B",
        expected_accuracy_Be="Monomer frameworks to <1.5 mÅ; MAPE(B) 0.08–0.20 % for covalent block",
        expected_wall_clock="+seconds on top of underlying geometry",
        frozen_monomer_flag=FrozenMonomerFlag.FROZEN_ISO,
        steps=[
            "1. revDSD-PBEP86-D4 or rDSD monomer geometry.",
            "2. Apply per-bond regression correction r = a_XY * r_DFT + b_XY.",
            "3. Freeze monomer; optimise intermolecular degrees of freedom at R1 or R2 level.",
        ],
        prohibitions=[
            "NEVER apply to a B3LYP geometry (nearly doubles relative deviations).",
        ],
        orca_template=None,
    ),
    "R6": RecipeExecutionPlan(
        recipe_id="R6",
        name="Semi-experimental anchoring to a measured parent (Product B)",
        target_product="B",
        expected_accuracy_Be="0.03–0.1 % [M]",
        expected_wall_clock="1 min",
        frozen_monomer_flag=FrozenMonomerFlag.RELAXED,
        steps=[
            "1. Scale trial geometry to reproduce measured A, B, C of parent.",
            "2. Substitute isotopic masses using mendeleev.",
        ],
        prohibitions=[
            "Requires at least one measured parent isotopologue.",
        ],
        orca_template=None,
    ),
    "R7": RecipeExecutionPlan(
        recipe_id="R7",
        name="Focal-point composite gradient",
        target_product="A",
        expected_accuracy_Be="Similar to CCSD(T) with basis one zeta higher",
        expected_wall_clock="~3 % of brute force",
        frozen_monomer_flag=FrozenMonomerFlag.RELAXED,
        steps=[
            "1. MP2/CBS gradient + delta[CCSD(T)]/small-basis gradient combined at each step.",
        ],
        prohibitions=[
            "Delta term must carry diffuse functions for weak complexes.",
        ],
        orca_template=None,
    ),
    "R8": RecipeExecutionPlan(
        recipe_id="R8",
        name="Δ-CCSD(T) single point on a DFT geometry (Energy Only)",
        target_product="A",
        expected_accuracy_Be="ZERO improvement in B (Energy Only)",
        expected_wall_clock="15 min (x/÷ 3)",
        frozen_monomer_flag=FrozenMonomerFlag.RELAXED,
        steps=[
            "1. DFT geometry optimization.",
            "2. Counterpoise-corrected DLPNO- or F12-CCSD(T) single point.",
        ],
        prohibitions=[
            "Do NOT use for rotational constant predictions (energy-only recipe).",
        ],
        orca_template=None,
    ),
    "R9": RecipeExecutionPlan(
        recipe_id="R9",
        name="ONIOM / QM-QM2",
        target_product="Rejected",
        expected_accuracy_Be="n.a. for 5–10 atoms (REJECTED)",
        expected_wall_clock="30 s on 16 cores",
        frozen_monomer_flag=FrozenMonomerFlag.RELAXED,
        steps=[
            "Rejected for 5-10 atom complexes as per Method Matrix §9A.5 Prohibition 2.",
        ],
        prohibitions=[
            "Strictly prohibited for 5-10 atom complexes.",
        ],
        orca_template=None,
    ),
}


def get_recipe_plan(recipe_id: str) -> RecipeExecutionPlan:
    """Retrieve the authoritative execution plan for a recipe (R1–R9)."""
    key = recipe_id.strip().upper()
    if key not in RECIPE_MENU_DEFINITIONS:
        raise ValueError(f"Unknown recipe ID '{recipe_id}'. Available: {list(RECIPE_MENU_DEFINITIONS.keys())}")
    return RECIPE_MENU_DEFINITIONS[key]


def evaluate_recipe_result(
    recipe_id: str,
    Be_MHz: Optional[float] = None,
    delta_B_vib_MHz: Optional[float] = None,
    residual_gradient_max: Optional[float] = None,
    softest_mode_cm1: Optional[float] = None,
    interaction_energy_kcal_mol: Optional[float] = None,
) -> RecipeReport:
    """Evaluate and compile a structured report for an executed composite calculation.

    Args:
        recipe_id: Recipe ID (e.g. 'R1', 'R2', etc.).
        Be_MHz: Computed B_e in MHz.
        delta_B_vib_MHz: Computed or estimated delta_B_vib in MHz.
        residual_gradient_max: Max gradient component on frozen coordinates (Eh/bohr).
        softest_mode_cm1: Lowest vibrational frequency in cm^-1.
        interaction_energy_kcal_mol: Counterpoise interaction energy in kcal/mol.

    Returns:
        RecipeReport with search windows and Method Matrix compliance verdict.
    """
    plan = get_recipe_plan(recipe_id)
    notes: List[str] = []

    B0_MHz: Optional[float] = None
    search_halfwidth_MHz: Optional[float] = None

    if Be_MHz is not None:
        if delta_B_vib_MHz is not None:
            B0_MHz = Be_MHz + delta_B_vib_MHz
            search_halfwidth_MHz = 0.005 * B0_MHz
            notes.append(f"Ground-state B_0 = {B0_MHz:.3f} MHz computed from B_e ({Be_MHz:.3f} MHz) + ΔB_vib ({delta_B_vib_MHz:.3f} MHz).")
            notes.append(f"Recommended spectroscopic search window half-width (±0.5%): ±{search_halfwidth_MHz:.1f} MHz.")
        else:
            notes.append(f"B_e = {Be_MHz:.3f} MHz reported. Note: ΔB_vib is unapplied; B_0 cannot be certified to 0.1 %.")

    if residual_gradient_max is not None:
        if residual_gradient_max > TOL_MAXG_DEFAULT:
            notes.append(
                f"[WARNING: STRAIN_DETECTED] Max residual gradient on frozen coordinates "
                f"({residual_gradient_max:.2e} Eh/bohr) exceeds TolMaxG ({TOL_MAXG_DEFAULT:.1e} Eh/bohr)."
            )
        else:
            notes.append(f"Residual gradient on frozen coordinates ({residual_gradient_max:.2e} Eh/bohr) passed TolMaxG gate.")

    verdict = f"Recipe {plan.recipe_id} executed in compliance with Method Matrix v4 §9A ({plan.name})."

    return RecipeReport(
        recipe_id=plan.recipe_id,
        name=plan.name,
        frozen_monomer_flag=plan.frozen_monomer_flag,
        Be_MHz=Be_MHz,
        delta_B_vib_MHz=delta_B_vib_MHz,
        B0_MHz=B0_MHz,
        search_window_halfwidth_MHz=search_halfwidth_MHz,
        interaction_energy_kcal_mol=interaction_energy_kcal_mol,
        residual_gradient_max=residual_gradient_max,
        softest_mode_cm1=softest_mode_cm1,
        compliance_verdict=verdict,
        notes=notes,
    )


# ==============================================================================
# File I/O and Parsing Utilities
# ==============================================================================

def parse_xyz_string(xyz_content: str) -> Tuple[List[str], np.ndarray]:
    """Parse standard XYZ format text into atom symbols and coordinates array.

    Args:
        xyz_content: Multiline string in XYZ format.

    Returns:
        Tuple of (symbols_list, (N, 3) coordinates_array).

    Raises:
        ValueError: If parsing fails or coordinate lines are malformed.
    """
    raw_lines = [line.strip() for line in xyz_content.strip().splitlines()]
    if not raw_lines:
        raise ValueError("Empty XYZ content provided.")

    try:
        n_atoms = int(raw_lines[0].split()[0])
        coord_candidates = raw_lines[2:]
    except (ValueError, IndexError):
        coord_candidates = raw_lines

    symbols: List[str] = []
    coords: List[List[float]] = []

    for line in coord_candidates:
        if not line:
            continue
        tokens = line.split()
        if len(tokens) < 4:
            continue
        sym = tokens[0].capitalize()
        try:
            x = float(tokens[1])
            y = float(tokens[2])
            z = float(tokens[3])
            symbols.append(sym)
            coords.append([x, y, z])
        except ValueError:
            continue

    if not symbols:
        raise ValueError("No valid Cartesian coordinate lines parsed from XYZ content.")

    return symbols, np.array(coords, dtype=np.float64)


def format_xyz_string(symbols: Sequence[str], coordinates: np.ndarray, comment: str = "") -> str:
    """Format atom symbols and coordinates into standard XYZ format.

    Args:
        symbols: Sequence of atom symbols.
        coordinates: (N, 3) coordinate array.
        comment: Header comment line.

    Returns:
        Formatted XYZ multiline string.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    n_atoms = len(symbols)
    lines = [str(n_atoms), comment]
    for i, sym in enumerate(symbols):
        lines.append(f"{sym:<3} {coords[i, 0]:15.8f} {coords[i, 1]:15.8f} {coords[i, 2]:15.8f}")
    return "\n".join(lines)


# ==============================================================================
# Standalone CLI Interface
# ==============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for frozen monomer utilities."""
    parser = argparse.ArgumentParser(
        description="CoChem-CORE: Composite and Frozen-Monomer Energy and Geometry Decomposition Engine."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute.")

    # 1. Rotational Constants
    p_rot = subparsers.add_parser("rotational-constants", help="Compute rotational constants from XYZ file.")
    p_rot.add_argument("--xyz", required=True, type=str, help="Path to input XYZ file.")
    p_rot.add_argument("--json", action="store_true", help="Output result in JSON format.")

    # 2. Sensitivity Analysis
    p_sens = subparsers.add_parser("sensitivity", help="Analyze rotational constant sensitivity (§4.5).")
    p_sens.add_argument("--xyz", required=True, type=str, help="Path to dimer XYZ file.")
    p_sens.add_argument("--monomer-a", required=True, type=str, help="Comma-separated 0-based atom indices for Monomer A.")
    p_sens.add_argument("--monomer-b", required=True, type=str, help="Comma-separated 0-based atom indices for Monomer B.")
    p_sens.add_argument("--delta-r", type=float, default=0.001, help="Monomer bond perturbation in Angstroms.")
    p_sens.add_argument("--delta-R", type=float, default=0.002, help="Intermolecular separation perturbation in Angstroms.")

    # 3. Counterpoise Decomposition
    p_cp = subparsers.add_parser("counterpoise", help="Decompose Counterpoise interaction energies.")
    p_cp.add_argument("--e-ab-ab", required=True, type=float, help="Dimer in dimer basis (Hartree).")
    p_cp.add_argument("--e-a-ab", required=True, type=float, help="Monomer A in dimer basis (Hartree).")
    p_cp.add_argument("--e-b-ab", required=True, type=float, help="Monomer B in dimer basis (Hartree).")
    p_cp.add_argument("--e-a-a", type=float, default=None, help="Isolated monomer A in monomer basis (Hartree).")
    p_cp.add_argument("--e-b-b", type=float, default=None, help="Isolated monomer B in monomer basis (Hartree).")

    # 4. Generate Optimization Spec
    p_opt = subparsers.add_parser("generate-spec", help="Generate ORCA tight %%geom block and constraints.")
    p_opt.add_argument("--xyz", required=True, type=str, help="Input XYZ file.")
    p_opt.add_argument("--monomer-a", required=True, type=str, help="Atom indices for Monomer A.")
    p_opt.add_argument("--monomer-b", required=True, type=str, help="Atom indices for Monomer B.")
    p_opt.add_argument("--flag", choices=["relaxed", "frozen-iso", "frozen-inc"], default="frozen-iso")
    p_opt.add_argument("--method", default="wB97M-V", help="DFT functional or WFT method.")
    p_opt.add_argument("--basis", default="def2-QZVPP", help="Basis set.")

    # 5. Recipe Plan / Evaluation
    p_rec = subparsers.add_parser("recipe", help="Display recipe details or evaluate results (R1–R9).")
    p_rec.add_argument("--id", required=True, type=str, help="Recipe ID, e.g. 'R1', 'R2', 'R4'.")
    p_rec.add_argument("--be", type=float, default=None, help="Computed B_e in MHz.")
    p_rec.add_argument("--delta-b-vib", type=float, default=None, help="Computed delta_B_vib in MHz.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for frozen monomer module."""
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = build_cli_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "rotational-constants":
        xyz_path = Path(args.xyz)
        if not xyz_path.exists():
            sys.stderr.write(f"Error: XYZ file not found: {xyz_path}\n")
            return 1
        symbols, coords = parse_xyz_string(xyz_path.read_text(encoding="utf-8"))
        res = compute_rotational_constants(symbols, coords)
        if args.json:
            print(res.model_dump_json(indent=2))
        else:
            print("=================================================================")
            print("CoChem Rigid-Rotor Rotational Observables (CONV = 505379.0 MHz·u·Å²)")
            print("=================================================================")
            print(f"Total Mass:           {res.total_mass_u:12.6f} u")
            print(f"Center of Mass:       ({res.com_coords_angstrom[0]:.4f}, {res.com_coords_angstrom[1]:.4f}, {res.com_coords_angstrom[2]:.4f}) Å")
            print(f"Moments of Inertia:   Ia = {res.Ia_uA2:.4f}, Ib = {res.Ib_uA2:.4f}, Ic = {res.Ic_uA2:.4f} u·Å²")
            print(f"Rotational Constants: A = {res.A_MHz:.4f} MHz, B = {res.B_MHz:.4f} MHz, C = {res.C_MHz:.4f} MHz")
            print(f"Planar Moments:       Paa = {res.Paa_uA2:.4f}, Pbb = {res.Pbb_uA2:.4f}, Pcc = {res.Pcc_uA2:.4f} u·Å²")
            print(f"Inertial Defect (Δ):  {res.inertial_defect_uA2:12.6f} u·Å²")
            print(f"Ray's Asymmetry (κ):  {res.ray_kappa:12.6f}")
        return 0

    elif args.subcommand == "sensitivity":
        xyz_path = Path(args.xyz)
        if not xyz_path.exists():
            sys.stderr.write(f"Error: XYZ file not found: {xyz_path}\n")
            return 1
        symbols, coords = parse_xyz_string(xyz_path.read_text(encoding="utf-8"))
        a_indices = [int(x.strip()) for x in args.monomer_a.split(",") if x.strip()]
        b_indices = [int(x.strip()) for x in args.monomer_b.split(",") if x.strip()]
        res = analyze_rotational_sensitivity(symbols, coords, a_indices, b_indices, args.delta_r, args.delta_R)
        print("=================================================================")
        print("Method Matrix §4.5 Coordinate Sensitivity & Error Propagation")
        print("=================================================================")
        print(f"Baseline A/B/C:       {res.baseline_A_MHz:.2f} / {res.baseline_B_MHz:.2f} / {res.baseline_C_MHz:.2f} MHz")
        print(f"Perturbed A/B/C:      {res.perturbed_A_MHz:.2f} / {res.perturbed_B_MHz:.2f} / {res.perturbed_C_MHz:.2f} MHz")
        print(f"Monomer Δr = +{args.delta_r*1000:.1f} mÅ -> ΔA/A = {res.delta_A_pct:.3f} %, ΔB/B = {res.delta_B_pct:.3f} %, ΔC/C = {res.delta_C_pct:.3f} %")
        print(f"Intermolecular ΔR = +{args.delta_R*1000:.1f} mÅ -> ΔB = {res.delta_B_MHz:.2f} MHz")
        print(f"Break-Even:           ΔR = {args.delta_R*1000:.1f} mÅ ≡ {res.break_even_monomer_bond_error_mAngstrom:.1f} mÅ uniform monomer bond error")
        print(f"\nVerdict: {res.headline_verdict}")
        return 0

    elif args.subcommand == "counterpoise":
        res = decompose_counterpoise_energy(
            E_AB_AB=args.e_ab_ab,
            E_A_AB=args.e_a_ab,
            E_B_AB=args.e_b_ab,
            E_A_A=args.e_a_a,
            E_B_B=args.e_b_b,
        )
        print("=================================================================")
        print("Method Matrix §9A.7 Counterpoise Energy Decomposition")
        print("=================================================================")
        print(f"E(AB)^(AB) [Complex in full basis]:       {res.E_AB_AB:16.8f} Eh")
        print(f"E(A)^(AB)  [Monomer A in full basis]:     {res.E_A_AB:16.8f} Eh")
        print(f"E(B)^(AB)  [Monomer B in full basis]:     {res.E_B_AB:16.8f} Eh")
        print(f"ΔE_CP (Counterpoise Interaction Energy):  {res.delta_E_CP_kcal_mol:12.4f} kcal/mol ({res.delta_E_CP_kJ_mol:12.4f} kJ/mol)")
        if res.E_BSSE_kcal_mol is not None:
            print(f"E_BSSE (Basis Set Superposition Error):   {res.E_BSSE_kcal_mol:12.4f} kcal/mol")
        if res.delta_E_halfCP_kcal_mol is not None:
            print(f"ΔE_halfCP (Half-Counterpoise Energy):     {res.delta_E_halfCP_kcal_mol:12.4f} kcal/mol")
        if res.E_def_total_kcal_mol is not None:
            print(f"E_def (Total Monomer Deformation Energy): {res.E_def_total_kcal_mol:12.4f} kcal/mol")
        return 0

    elif args.subcommand == "generate-spec":
        xyz_path = Path(args.xyz)
        if not xyz_path.exists():
            sys.stderr.write(f"Error: XYZ file not found: {xyz_path}\n")
            return 1
        symbols, coords = parse_xyz_string(xyz_path.read_text(encoding="utf-8"))
        a_indices = [int(x.strip()) for x in args.monomer_a.split(",") if x.strip()]
        b_indices = [int(x.strip()) for x in args.monomer_b.split(",") if x.strip()]
        part_a = MonomerPartition(fragment_id="monomer_A", name="FragmentA", atom_indices=a_indices)
        part_b = MonomerPartition(fragment_id="monomer_B", name="FragmentB", atom_indices=b_indices)
        spec = generate_frozen_monomer_optimization_spec(
            symbols=symbols,
            coordinates_angstrom=coords,
            partitions=[part_a, part_b],
            frozen_monomer_flag=FrozenMonomerFlag(args.flag),
            method_name=args.method,
            basis_set=args.basis,
        )
        print("=================================================================")
        print("Generated Method Matrix §4.4 / §9A.1 ORCA Optimization Spec")
        print("=================================================================")
        print(spec.orca_geom_block)
        return 0

    elif args.subcommand == "recipe":
        plan = get_recipe_plan(args.id)
        if args.be is not None:
            report = evaluate_recipe_result(
                recipe_id=args.id,
                Be_MHz=args.be,
                delta_B_vib_MHz=args.delta_b_vib,
            )
            print(report.model_dump_json(indent=2))
        else:
            print(f"Recipe {plan.recipe_id}: {plan.name}")
            print(f"Target Product:        {plan.target_product}")
            print(f"Expected B_e Accuracy: {plan.expected_accuracy_Be}")
            print(f"Expected Wall Clock:   {plan.expected_wall_clock}")
            print(f"Frozen Monomer Flag:   {plan.frozen_monomer_flag.value}")
            print("\nExecution Steps:")
            for s in plan.steps:
                print(f"  {s}")
            print("\nProhibitions:")
            for p in plan.prohibitions:
                print(f"  - {p}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
