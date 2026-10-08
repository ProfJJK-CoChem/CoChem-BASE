"""
CoChem-BASE Spectroscopy Suite: Dynamic Mendeleev Mass-Weighted Hessian Engine.
Validating Suggestion #39 (Chunk 4).

Method Matrix v4 & Provenance Mandates:
- Dynamic Mendeleev Mass Mandate: All atomic/isotopic masses retrieved via mendeleev.
- Strict distinction between theoretical equilibrium B_e and ground-state observable B_0.
- Millisecond electronic Hessian invariance re-diagonalization (Method Matrix §6.10 & §8B.4).
- Provenance tags: [M] Measured/Calculated, [D] Derived Mathematical, [E] Estimated.
"""

from __future__ import annotations

import functools
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.constants import physical_constants, speed_of_light

from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2
from cochem_base.physics.isotopes import get_isotope_mass, parse_nuclide_token

# One conversion factor throughout the CoChem architecture.
ROTATIONAL_CONSTANT_CONVERSION_MHZ = C_ROT_MHZ_U_ANG2


@functools.lru_cache(maxsize=4096, typed=True)
def get_nuclide_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """Resolve an exact nuclide mass; bare symbols select the most abundant isotope.

    An isotope is required for elements without a natural abundance. Atomic-weight
    averages remain available through physics.isotopes.get_atomic_mass, but are
    not appropriate for a single isotopologue's spectrum.
    """
    clean_sym, parsed_number = parse_nuclide_token(symbol)
    if mass_number is not None and parsed_number is not None and mass_number != parsed_number:
        raise ValueError(f"Contradictory isotope specification: {symbol}, {mass_number}")
    number = parsed_number if mass_number is None else mass_number
    mass = get_isotope_mass(clean_sym, number)
    if not math.isfinite(mass) or mass <= 0:
        raise ValueError("Spectroscopic masses must be finite and strictly positive")
    return mass


def projected_harmonic_frequencies(
    hessian: np.ndarray, coordinates: np.ndarray, masses: np.ndarray,
) -> Tuple[List[float], int]:
    """Mass reweight a Cartesian Hessian in Eh/bohr² and remove rigid motion.

    SVD gives the orthogonal complement of the mass-weighted translation and
    rotation vectors. Linear molecules have five rigid modes, nonlinear ones six,
    and isolated atoms three. Negative frequencies denote imaginary modes; soft
    or unstable vibrational modes are never discarded by an eigenvalue cutoff.
    """
    n_atoms = len(masses)
    sqrt_mass = np.sqrt(masses)
    centered = coordinates - np.average(coordinates, axis=0, weights=masses)
    axes = np.eye(3)
    translations = [np.tile(axis, (n_atoms, 1)) * sqrt_mass[:, None] for axis in axes]
    rotations = [np.cross(axis, centered) * sqrt_mass[:, None] for axis in axes]
    rigid = np.column_stack([vector.ravel() for vector in translations + rotations])
    # Normalize nonzero columns so rank does not depend on translation/length units.
    lengths = np.linalg.norm(rigid, axis=0)
    rigid[:, lengths > 0] /= lengths[lengths > 0]
    basis, singular_values, _ = np.linalg.svd(rigid, full_matrices=True)
    rank = int(np.sum(singular_values > singular_values[0] * 1e-10))
    vibrational = basis[:, rank:]
    inverse_mass = np.repeat(1.0 / sqrt_mass, 3)
    weighted = hessian * np.outer(inverse_mass, inverse_mass)
    squared_frequencies = np.linalg.eigvalsh(vibrational.T @ weighted @ vibrational)
    hartree = physical_constants["Hartree energy"][0]
    bohr = physical_constants["Bohr radius"][0]
    amu = physical_constants["atomic mass constant"][0]
    conversion = math.sqrt(hartree / (amu * bohr ** 2)) / (2 * math.pi * speed_of_light * 100)
    frequencies = np.sign(squared_frequencies) * np.sqrt(np.abs(squared_frequencies)) * conversion
    return frequencies.tolist(), rank


@dataclass
class IsotopologueResult:
    """Authentic spectroscopic observables for an isotopologue. [M]"""

    symbols: List[str]
    masses: List[float]
    total_mass_amu: float
    center_of_mass: List[float]

    # Principal moments of inertia in amu * Angstrom^2
    I_a: float
    I_b: float
    I_c: float

    # Historical names: geometric rigid-rotor constants. They represent B_e
    # only when the source geometry's stationarity is independently verified.
    A_e_MHz: float
    B_e_MHz: float
    C_e_MHz: float

    # Vibrational corrections in MHz [D]
    delta_A_vib_MHz: Optional[float] = None
    delta_B_vib_MHz: Optional[float] = None
    delta_C_vib_MHz: Optional[float] = None

    # Physical Ground-State Effective Rotational Constants (Microwave Observable) in MHz [D]
    A_0_MHz: Optional[float] = None
    B_0_MHz: Optional[float] = None
    C_0_MHz: Optional[float] = None

    # Inertial defect Delta = I_c - I_a - I_b (amu * Angstrom^2) [D]
    inertial_defect_amu_A2: float = 0.0

    # Harmonic normal mode frequencies in cm^-1 [M]
    harmonic_frequencies_cm1: List[float] = field(default_factory=list)

    rigid_mode_count: int = 0
    vibrational_correction_source: Optional[str] = None
    equilibrium_geometry_verified: bool = False
    physical_hessian_verified: bool = False
    minimum_verified: bool = False
    scientific_accuracy_established: bool = False
    mass_convention: str = "Explicit isotopes use their dynamic nuclide mass; bare symbols select the most abundant isotope, not the atomic-weight average."
    rotational_constant_scope: str = "Rigid-geometry rotational constants; a stationary equilibrium geometry is not established."
    harmonic_frequency_scope: str = "No Cartesian tensor supplied."
    ground_state_constant_scope: str = "Missing: harmonic isotope reweighting alone does not establish anharmonic ground-state rotational constants."
    geometry_qualification: Dict = field(default_factory=dict)
    execution_walltime_ms: float = 0.0
    provenance_tags: Dict[str, str] = field(default_factory=lambda: {
        "A_e": "[M]", "B_e": "[M]", "C_e": "[M]",
        "inertial_defect": "[D]",
        "masses": "[M]"
    })


class IsotopologueSpectroscopyEngine:
    """High-speed mass-weighted Hessian re-diagonalization engine. [M]

    Exploits electronic Hessian invariance to compute isotopologue rotational constants,
    inertial defects, and harmonic modes without recalculating electronic structure.
    Ground-state rotational constants require independently calculated or measured
    vibrational corrections; a harmonic Hessian alone cannot supply VPT2 corrections.
    """

    def __init__(
        self,
        symbols: List[str],
        coordinates_angstrom: Union[np.ndarray, List[List[float]]],
        cartesian_hessian: Optional[np.ndarray] = None,
        *, hessian_qualification: Optional[Dict] = None,
    ) -> None:
        self.symbols = [str(s).strip() for s in symbols]
        self.coordinates = np.array(coordinates_angstrom, dtype=np.float64)
        self.cartesian_hessian = (
            np.array(cartesian_hessian, dtype=np.float64) if cartesian_hessian is not None else None
        )
        self.num_atoms = len(self.symbols)
        self.hessian_qualification = dict(hessian_qualification or {})
        if self.num_atoms == 0:
            raise ValueError("At least one atom is required")
        if self.coordinates.shape != (self.num_atoms, 3):
            raise ValueError(f"Coordinate shape {self.coordinates.shape} does not match atom count {self.num_atoms}")

        if not np.all(np.isfinite(self.coordinates)):
            raise ValueError("Coordinates must be finite")
        if self.cartesian_hessian is not None:
            if self.cartesian_hessian.shape != (3 * self.num_atoms, 3 * self.num_atoms):
                raise ValueError("Cartesian Hessian must have shape (3N, 3N)")
            if not np.all(np.isfinite(self.cartesian_hessian)):
                raise ValueError("Cartesian Hessian must be finite")
            if not np.allclose(self.cartesian_hessian, self.cartesian_hessian.T, rtol=1e-10, atol=1e-12):
                raise ValueError("Cartesian Hessian must be symmetric")

        # Pre-cache Mendeleev nuclide masses to guarantee sub-millisecond re-analysis
        for s in self.symbols:
            get_nuclide_mass(s)

    def compute_observables(
        self,
        isotopic_substitution: Optional[Dict[int, str]] = None,
        *,
        vibrational_corrections_mhz: Optional[Tuple[float, float, float]] = None,
        correction_source: Optional[str] = None,
    ) -> IsotopologueResult:
        """Re-diagonalizes moment of inertia and mass-weighted Hessian in milliseconds. [M]"""
        t0 = time.perf_counter()

        for index, replacement in (isotopic_substitution or {}).items():
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < self.num_atoms:
                raise ValueError(f"Invalid isotopic substitution index: {index}")
            original_element, _ = parse_nuclide_token(self.symbols[index])
            new_element, _ = parse_nuclide_token(replacement)
            if new_element != original_element:
                raise ValueError("Isotopic substitution cannot change the element or reuse its electronic Hessian")
        if vibrational_corrections_mhz is not None:
            corrections = np.asarray(vibrational_corrections_mhz, dtype=float)
            if corrections.shape != (3,) or not np.all(np.isfinite(corrections)):
                raise ValueError("Vibrational corrections must be three finite MHz values")
            if not isinstance(correction_source, str) or not correction_source.strip():
                raise ValueError("Vibrational corrections require a nonempty provenance source")

        # 1. Dynamic Mendeleev masses for target isotopologue
        active_symbols = list(self.symbols)
        masses: List[float] = []
        for i in range(self.num_atoms):
            if isotopic_substitution and i in isotopic_substitution:
                sub_sym = isotopic_substitution[i]
                mass = get_nuclide_mass(sub_sym)
                active_symbols[i] = sub_sym
            else:
                mass = get_nuclide_mass(active_symbols[i])
            masses.append(mass)

        mass_array = np.array(masses, dtype=np.float64)
        total_mass = float(np.sum(mass_array))

        # 2. Shift to isotopic center of mass
        com = np.sum(self.coordinates * mass_array[:, np.newaxis], axis=0) / total_mass
        shifted_coords = self.coordinates - com

        # 3. Principal moments of inertia tensor (amu * Angstrom^2)
        I_xx = float(sum(mass_array[i] * (shifted_coords[i, 1]**2 + shifted_coords[i, 2]**2) for i in range(self.num_atoms)))
        I_yy = float(sum(mass_array[i] * (shifted_coords[i, 0]**2 + shifted_coords[i, 2]**2) for i in range(self.num_atoms)))
        I_zz = float(sum(mass_array[i] * (shifted_coords[i, 0]**2 + shifted_coords[i, 1]**2) for i in range(self.num_atoms)))
        I_xy = float(-sum(mass_array[i] * shifted_coords[i, 0] * shifted_coords[i, 1] for i in range(self.num_atoms)))
        I_xz = float(-sum(mass_array[i] * shifted_coords[i, 0] * shifted_coords[i, 2] for i in range(self.num_atoms)))
        I_yz = float(-sum(mass_array[i] * shifted_coords[i, 1] * shifted_coords[i, 2] for i in range(self.num_atoms)))

        I_tensor = np.array([
            [I_xx, I_xy, I_xz],
            [I_xy, I_yy, I_yz],
            [I_xz, I_yz, I_zz],
        ], dtype=np.float64)

        evals, _ = np.linalg.eigh(I_tensor)
        # Order principal moments I_a <= I_b <= I_c
        sorted_evals = np.sort(evals)
        I_a, I_b, I_c = float(sorted_evals[0]), float(sorted_evals[1]), float(sorted_evals[2])

        # Geometric rotational constants. The metadata below qualifies whether
        # this fixed geometry has a verified Born-Oppenheimer stationary point.
        A_e = ROTATIONAL_CONSTANT_CONVERSION_MHZ / I_a if I_a > 1e-12 else math.inf
        B_e = ROTATIONAL_CONSTANT_CONVERSION_MHZ / I_b if I_b > 1e-12 else math.inf
        C_e = ROTATIONAL_CONSTANT_CONVERSION_MHZ / I_c if I_c > 1e-12 else math.inf

        # Inertial defect: Delta = I_c - I_a - I_b (amu * Angstrom^2) [D]
        inertial_defect = float(I_c - I_a - I_b)

        # A Cartesian harmonic Hessian is isotope invariant in the BO approximation.
        harmonic_freqs: List[float] = []
        rigid_count = 0
        if self.cartesian_hessian is not None:
            harmonic_freqs, rigid_count = projected_harmonic_frequencies(
                self.cartesian_hessian, self.coordinates, mass_array
            )

        # Anharmonic vibrational corrections cannot be inferred from harmonic
        # frequencies by fixed percentages. Preserve missing evidence explicitly.
        delta_A_vib = delta_B_vib = delta_C_vib = None
        A_0 = B_0 = C_0 = None
        provenance = {"A_e": "[M]", "B_e": "[M]", "C_e": "[M]",
                      "inertial_defect": "[D]", "masses": "[M]"}
        if vibrational_corrections_mhz is not None:
            delta_A_vib, delta_B_vib, delta_C_vib = map(float, corrections)
            A_0, B_0, C_0 = A_e + delta_A_vib, B_e + delta_B_vib, C_e + delta_C_vib
            provenance.update({"delta_B_vib": "supplied", "B_0": "[D]"})

        wall_ms = (time.perf_counter() - t0) * 1000.0

        physical_hessian = (self.cartesian_hessian is not None
                            and self.hessian_qualification.get("validation_kind") == "native-artifact-consistency"
                            and self.hessian_qualification.get("physical_hessian_verified") is True)
        equilibrium = physical_hessian and self.hessian_qualification.get("stationary_geometry_verified") is True
        minimum = equilibrium and bool(harmonic_freqs) and min(harmonic_freqs) > 0
        harmonic_scope = ("Isotope mass reweighting of the retained native physical force Hessian; fixed Born-Oppenheimer geometry, harmonic approximation, no new electronic calculation." if physical_hessian else
                          "Mass reweighting of a supplied Cartesian tensor. Physical force-Hessian origin and stationary geometry are not established; model/preconditioner eigenvalues are not validated molecular vibrations." if self.cartesian_hessian is not None else
                          "No Cartesian tensor supplied.")
        return IsotopologueResult(
            symbols=active_symbols,
            masses=masses,
            total_mass_amu=total_mass,
            center_of_mass=com.tolist(),
            I_a=I_a,
            I_b=I_b,
            I_c=I_c,
            A_e_MHz=A_e,
            B_e_MHz=B_e,
            C_e_MHz=C_e,
            delta_A_vib_MHz=delta_A_vib,
            delta_B_vib_MHz=delta_B_vib,
            delta_C_vib_MHz=delta_C_vib,
            A_0_MHz=A_0,
            B_0_MHz=B_0,
            C_0_MHz=C_0,
            inertial_defect_amu_A2=inertial_defect,
            harmonic_frequencies_cm1=harmonic_freqs,
            rigid_mode_count=rigid_count,
            vibrational_correction_source=correction_source if vibrational_corrections_mhz is not None else None,
            equilibrium_geometry_verified=equilibrium,
            physical_hessian_verified=physical_hessian,
            minimum_verified=minimum,
            rotational_constant_scope=("Born-Oppenheimer stationary-geometry rigid-rotor constants; isotopic masses change inertia, not the fixed electronic geometry. Experimental spectroscopic accuracy is not established." if equilibrium else
                                       "Rigid-geometry rotational constants; a stationary equilibrium geometry is not established."),
            harmonic_frequency_scope=harmonic_scope,
            ground_state_constant_scope=("Mathematical sum of rigid-geometry constants and independently supplied MHz corrections; the corrections' physical validity and applicability are not certified by harmonic reanalysis." if vibrational_corrections_mhz is not None else
                                         "Missing: harmonic isotope reweighting alone does not establish anharmonic ground-state rotational constants."),
            geometry_qualification=dict(self.hessian_qualification),
            provenance_tags=provenance,
            execution_walltime_ms=wall_ms,
        )
