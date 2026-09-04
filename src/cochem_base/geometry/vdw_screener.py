"""Preflight intermolecular van der Waals distance verification module (vdw_screener.py).

Implements VanDerWaalsDistanceScreener adhering to Method Matrix v4 §9B.1-§9B.2
and the CoChem Mendeleev Mass/Radii Mandate.
"""

from __future__ import annotations

from typing import Sequence
import numpy as np
from mendeleev import element

from cochem_base.exceptions import IntermolecularTopologyError


class VanDerWaalsDistanceScreener:
    """Preflight screener validating intermolecular complex separations against physical vdW contact envelopes."""

    @staticmethod
    def get_vdw_radius(symbol: str) -> float:
        """Retrieve the van der Waals radius in Angstroms dynamically via Mendeleev.

        Falls back to Pyykkö covalent radius + 0.8 Å if vdW radius is undefined.
        """
        clean_sym = symbol.strip().capitalize()
        rad = element(clean_sym).vdw_radius
        if rad is None:
            cov = element(clean_sym).covalent_radius_pyykko or 100.0
            return (float(cov) / 100.0) + 0.8
        return float(rad) / 100.0  # Convert pm to Angstroms [M]

    @classmethod
    def validate_complex_separation(
        cls,
        coords_a: np.ndarray | Sequence[Sequence[float]],
        symbols_a: Sequence[str],
        coords_b: np.ndarray | Sequence[Sequence[float]],
        symbols_b: Sequence[str],
    ) -> tuple[bool, float, str]:
        """Calculates pairwise interatomic distance matrix between Fragment A and Fragment B.

        Asserts min distance falls within physical van der Waals binding contact window:
        R_min in [R_vdw_ij - 0.3 Å, R_vdw_ij + 0.8 Å] [M] (with standard hydrogen-bond
        penetration allowance down to R_vdw_ij - 0.95 Å for H...O/N/F pairs).

        Parameters
        ----------
        coords_a : array-like, shape (N_A, 3)
            Cartesian coordinates of Fragment A in Angstroms.
        symbols_a : sequence of str
            Element symbols of Fragment A.
        coords_b : array-like, shape (N_B, 3)
            Cartesian coordinates of Fragment B in Angstroms.
        symbols_b : sequence of str
            Element symbols of Fragment B.

        Returns
        -------
        tuple[bool, float, str]
            (is_valid, min_distance_angstrom, warning_or_info_message)

        Raises
        ------
        IntermolecularTopologyError
            If min distance < 1.0 Å (core penetration) or > 8.0 Å (dissociation).
        """
        ca = np.asarray(coords_a, dtype=np.float64)
        cb = np.asarray(coords_b, dtype=np.float64)
        sa = [s.strip().capitalize() for s in symbols_a]
        sb = [s.strip().capitalize() for s in symbols_b]

        if ca.ndim != 2 or ca.shape[1] != 3 or cb.ndim != 2 or cb.shape[1] != 3:
            raise ValueError("Coordinates must have shape (N, 3).")
        if len(ca) != len(sa) or len(cb) != len(sb):
            raise ValueError("Lengths of coordinates and symbols must match.")
        if len(ca) == 0 or len(cb) == 0:
            raise ValueError("Both fragments must contain at least one atom.")

        # Compute pairwise distance matrix (N_A, N_B)
        diff = ca[:, np.newaxis, :] - cb[np.newaxis, :, :]  # (N_A, N_B, 3)
        dist_matrix = np.linalg.norm(diff, axis=-1)  # (N_A, N_B)

        min_idx = np.unravel_index(np.argmin(dist_matrix), dist_matrix.shape)
        i_min, j_min = int(min_idx[0]), int(min_idx[1])
        min_dist = float(dist_matrix[i_min, j_min])

        # 1. Hard physical rejection criteria (§9B.2)
        if min_dist < 1.0:
            raise IntermolecularTopologyError(
                f"Severe steric core clash detected: R_min = {min_dist:.3f} Å < 1.0 Å"
            )
        if min_dist > 8.0:
            raise IntermolecularTopologyError(
                f"Fragments dissociated: R_min = {min_dist:.3f} Å > 8.0 Å"
            )

        # 2. Dynamic Mendeleev vdW contact window evaluation [M]
        sym_a = sa[i_min]
        sym_b = sb[j_min]
        r_vdw_a = cls.get_vdw_radius(sym_a)
        r_vdw_b = cls.get_vdw_radius(sym_b)
        r_vdw_ij = r_vdw_a + r_vdw_b

        # Hydrogen-bond penetration allowance for H...(O,N,F,Cl,S) pairs
        is_h_bond = (
            ("H" in (sym_a, sym_b))
            and any(s in ("O", "N", "F", "Cl", "S") for s in (sym_a, sym_b))
        )
        lower_delta = 0.95 if is_h_bond else 0.3
        lower_bound = r_vdw_ij - lower_delta  # [D]
        upper_bound = r_vdw_ij + 0.8  # [D]

        if lower_bound <= min_dist <= upper_bound:
            return True, min_dist, ""

        msg = (
            f"Warning: separation {min_dist:.3f} Å violates physical vdW contact window "
            f"[{lower_bound:.3f}, {upper_bound:.3f}] Å between {sym_a} and {sym_b}."
        )
        return False, min_dist, msg
