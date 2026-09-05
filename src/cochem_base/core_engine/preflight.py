"""Preflight Geometry & Computational Parameter Validator (Method Matrix v4 §4.4, §8B, §10.2).

Performs instantaneous sanity checks prior to quantum calculation dispatch:
1. Interatomic distance matrix (steric clashes < 0.8 A, unbound fragments > 8.0 A).
2. Spin multiplicity and charge consistency with total electron count.
3. Spin state expectation (<S^2> deviation < 10% from ideal S(S+1)).
4. Mandatory empirical dispersion (D3/D4/VV10) for non-covalent complexes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

try:
    from mendeleev import element
    HAS_MENDELEEV = True
except ImportError:
    HAS_MENDELEEV = False

from cochem_base.physics.isotopes import get_element_mass_and_abundance


class PreflightValidationError(ValueError):
    """Raised when coordinates or parameters violate physical or methodological constraints."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.details = details or {}


def get_atomic_number(symbol: str) -> int:
    """Dynamically resolves atomic number Z via mendeleev or pinned isotopes."""
    s = symbol.strip().capitalize()
    if HAS_MENDELEEV:
        try:
            elem = element(s)
            if elem.atomic_number is not None:
                return int(elem.atomic_number)
        except Exception:
            pass
    # Fallback to offline pinned table
    _, _, z = get_element_mass_and_abundance(s)
    return z


class PreflightGeometryValidator:
    """Instantaneous client-side sanity validator for molecular coordinates and quantum decks."""

    CLASH_THRESHOLD_ANGSTROM: float = 0.80
    UNBOUND_THRESHOLD_ANGSTROM: float = 8.00
    MAX_SPIN_CONTAMINATION_RATIO: float = 0.10

    DISPERSION_IDENTIFIERS: Tuple[str, ...] = (
        "d3",
        "d4",
        "vv10",
        "nl",
        "d3bj",
        "d3zero",
        "-3c",
        "wb97x-d",
        "wb97x-d3",
        "b97-3c",
        "r2scan-3c",
    )

    @classmethod
    def validate(
        cls,
        symbols: Sequence[str],
        coordinates: np.ndarray | Sequence[Sequence[float]],
        charge: int = 0,
        multiplicity: int = 1,
        is_non_covalent: bool = False,
        dft_keywords: str = "",
        allow_unbound: bool = False,
        computed_s2: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Validate geometries and job parameters against physical and methodological constraints.

        Parameters
        ----------
        symbols : Sequence[str]
            Atomic element symbols.
        coordinates : array-like of shape (N, 3)
            Cartesian coordinates in Angstroms.
        charge : int, default=0
            Net molecular charge.
        multiplicity : int, default=1
            Spin multiplicity 2S + 1.
        is_non_covalent : bool, default=False
            Whether the system is a non-covalent or bimolecular complex.
        dft_keywords : str, default=""
            Calculation input keywords string (e.g., ORCA command line).
        allow_unbound : bool, default=False
            Whether to permit separated or unbound fragments > 8.0 A.
        computed_s2 : float, optional
            Computed <S^2> expectation value to test for spin contamination.

        Returns
        -------
        Dict[str, Any]
            Detailed validation diagnostic report.
        """
        n_atoms = len(symbols)
        if n_atoms == 0:
            raise PreflightValidationError("Molecular system contains zero atoms.")

        coords = np.asarray(coordinates, dtype=np.float64)
        if coords.shape != (n_atoms, 3):
            raise PreflightValidationError(
                f"Coordinates shape mismatch: expected ({n_atoms}, 3), got {coords.shape}."
            )

        # 1. Pairwise Interatomic Distance Matrix
        diffs = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        dist_matrix = np.linalg.norm(diffs, axis=-1)

        min_distance = float("inf")
        clash_pair: Optional[Tuple[int, int, float]] = None

        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                d = float(dist_matrix[i, j])
                if d < min_distance:
                    min_distance = d
                if d < cls.CLASH_THRESHOLD_ANGSTROM:
                    clash_pair = (i, j, d)
                    break
            if clash_pair is not None:
                break

        if clash_pair is not None:
            i, j, d = clash_pair
            raise PreflightValidationError(
                f"Severe steric clash detected between atom {i} ({symbols[i]}) and atom {j} ({symbols[j]}): "
                f"distance r = {d:.4f} A < threshold {cls.CLASH_THRESHOLD_ANGSTROM:.2f} A.",
                details={"atom_i": i, "atom_j": j, "distance": d, "threshold": cls.CLASH_THRESHOLD_ANGSTROM},
            )

        # Check for unbound isolated atoms (nearest neighbor > 8.0 A)
        max_nearest_neighbor = 0.0
        if n_atoms > 1 and not allow_unbound:
            for i in range(n_atoms):
                other_dists = [dist_matrix[i, j] for j in range(n_atoms) if j != i]
                nearest = min(other_dists)
                if nearest > max_nearest_neighbor:
                    max_nearest_neighbor = nearest
                if nearest > cls.UNBOUND_THRESHOLD_ANGSTROM:
                    raise PreflightValidationError(
                        f"Unbound atom detected: atom {i} ({symbols[i]}) has nearest neighbor at "
                        f"{nearest:.4f} A > threshold {cls.UNBOUND_THRESHOLD_ANGSTROM:.2f} A.",
                        details={"atom_index": i, "nearest_distance": nearest, "threshold": cls.UNBOUND_THRESHOLD_ANGSTROM},
                    )

        # 2. Spin Multiplicity & Charge Consistency
        z_values = [get_atomic_number(s) for s in symbols]
        total_protons = sum(z_values)
        total_electrons = total_protons - charge

        if total_electrons <= 0:
            raise PreflightValidationError(
                f"Unphysical total electron count N_e = {total_electrons} (protons={total_protons}, charge={charge})."
            )

        # Parity check: (N_e % 2) != (multiplicity % 2)
        # Even N_e requires odd multiplicity (1, 3, 5); Odd N_e requires even multiplicity (2, 4, 6)
        if (total_electrons % 2) == (multiplicity % 2):
            expected = "odd (singlet, triplet, ...)" if (total_electrons % 2 == 0) else "even (doublet, quartet, ...)"
            raise PreflightValidationError(
                f"Spin multiplicity {multiplicity} is inconsistent with total electron count N_e = {total_electrons}. "
                f"Expected an {expected} multiplicity for net charge {charge}.",
                details={"total_electrons": total_electrons, "charge": charge, "multiplicity": multiplicity},
            )

        # 3. Spin State Expectation & Spin Contamination
        s_quantum = (multiplicity - 1) / 2.0
        ideal_s2 = s_quantum * (s_quantum + 1.0)
        spin_deviation: Optional[float] = None

        if computed_s2 is not None:
            if s_quantum > 0:
                spin_deviation = abs(computed_s2 - ideal_s2) / ideal_s2
                if spin_deviation >= cls.MAX_SPIN_CONTAMINATION_RATIO:
                    raise PreflightValidationError(
                        f"Spin contamination exceeds {cls.MAX_SPIN_CONTAMINATION_RATIO * 100:.1f}% limit: "
                        f"computed <S^2> = {computed_s2:.4f}, ideal = {ideal_s2:.4f}, "
                        f"deviation = {spin_deviation * 100:.2f}%.",
                        details={"computed_s2": computed_s2, "ideal_s2": ideal_s2, "deviation": spin_deviation},
                    )
            else:
                # Singlet: ideal <S^2> = 0.0
                spin_deviation = abs(computed_s2)
                if spin_deviation > 0.05:
                    raise PreflightValidationError(
                        f"Singlet spin contamination detected: computed <S^2> = {computed_s2:.4f} > 0.05.",
                        details={"computed_s2": computed_s2, "ideal_s2": 0.0},
                    )

        # 4. Mandatory Empirical Dispersion Check for Non-Covalent Complexes (§4.4)
        if is_non_covalent and dft_keywords:
            kw_lower = dft_keywords.lower()
            has_dispersion = any(ident in kw_lower for ident in cls.DISPERSION_IDENTIFIERS)
            if not has_dispersion:
                raise PreflightValidationError(
                    "Non-covalent complex calculation requires explicit empirical dispersion (D3, D4, or VV10) "
                    "per Method Matrix v4 §4.4. Calculation deck lacks dispersion keywords.",
                    details={"dft_keywords": dft_keywords, "required": cls.DISPERSION_IDENTIFIERS},
                )

        return {
            "valid": True,
            "atom_count": n_atoms,
            "total_electrons": total_electrons,
            "charge": charge,
            "multiplicity": multiplicity,
            "min_distance_angstrom": min_distance,
            "max_nearest_neighbor_angstrom": max_nearest_neighbor,
            "ideal_s2": ideal_s2,
            "spin_deviation": spin_deviation,
        }
