"""
CoChem-GEOM: Peptide Secondary Structure and Dihedral Mapping Module
-------------------------------------------------------------------
Provides physical Ramachandran backbone analysis for peptides and proteins.
Computes phi, psi, and omega dihedral angles with circular/directional statistics,
handles geometric singularities strictly, classifies secondary structure regions,
evaluates cis/trans peptide isomerization, and writes to HDF5 archives without exception swallowing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final, Sequence
import h5py
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_REGIONS: Final[dict[str, dict[str, tuple[float, float]]]] = {
    "alpha_helix": {"phi": (-180.0, 0.0), "psi": (-100.0, 45.0)},
    "beta_sheet": {"phi": (-180.0, -45.0), "psi": (45.0, 180.0)},
    "left_handed_helix": {"phi": (0.0, 180.0), "psi": (0.0, 100.0)},
    "coil/turn": {"phi": (-180.0, 180.0), "psi": (-180.0, 180.0)},
}


class BackboneAnalysisResult(BaseModel):
    """Pydantic model representing complete backbone dihedral and secondary structure evaluation."""

    classification: str = Field(
        ...,
        description="Assigned secondary structure (alpha_helix, beta_sheet, left_handed_helix, coil/turn, or unknown)",
    )
    avg_phi: float = Field(..., description="Circular mean of phi dihedral angles in degrees (-180.0 to 180.0)")
    avg_psi: float = Field(..., description="Circular mean of psi dihedral angles in degrees (-180.0 to 180.0)")
    phis: list[float] = Field(default_factory=list, description="Extracted phi dihedral angles in degrees")
    psis: list[float] = Field(default_factory=list, description="Extracted psi dihedral angles in degrees")
    omegas: list[float] = Field(default_factory=list, description="Extracted omega dihedral angles in degrees")
    omega_isomers: list[str] = Field(default_factory=list, description="Cis/Trans classification for each omega angle")
    is_all_trans: bool = Field(default=True, description="Whether all omega peptide bonds adopt the trans conformation")


class PeptideMapper:
    """Evaluates peptide backbone geometries, secondary structures, and Ramachandran dihedrals."""

    def __init__(self, regions: dict[str, dict[str, tuple[float, float]]] | None = None) -> None:
        """Initialize PeptideMapper with secondary structure region definitions."""
        if regions is not None:
            self.regions = dict(regions)
        else:
            self.regions = dict(DEFAULT_REGIONS)

    def _compute_dihedral(
        self,
        p0: np.ndarray,
        p1: np.ndarray,
        p2: np.ndarray,
        p3: np.ndarray,
    ) -> float:
        """Compute the dihedral angle between four points in degrees [-180.0, 180.0].

        Raises:
            ValueError: If central bond length is zero/near-zero or if points are collinear.
        """
        b0 = -1.0 * (p1 - p0)
        b1 = p2 - p1
        b2 = p3 - p2

        b1_norm = float(np.linalg.norm(b1))
        if b1_norm < 1e-8:
            raise ValueError(
                f"Degenerate geometry: central bond length norm ({b1_norm:.2e}) < 1e-8. "
                "Dihedral angle is mathematically undefined."
            )
        b1_unit = b1 / b1_norm

        v = b0 - np.dot(b0, b1_unit) * b1_unit
        w = b2 - np.dot(b2, b1_unit) * b1_unit

        v_norm = float(np.linalg.norm(v))
        w_norm = float(np.linalg.norm(w))

        if v_norm < 1e-8 or w_norm < 1e-8:
            raise ValueError(
                f"Collinear geometry: projection norm (v={v_norm:.2e}, w={w_norm:.2e}) < 1e-8. "
                "Dihedral angle is mathematically undefined."
            )

        x = np.dot(v, w)
        y = np.dot(np.cross(b1_unit, v), w)
        return float(np.degrees(np.arctan2(y, x)))

    def _circular_mean(self, angles: Sequence[float]) -> float:
        """Compute directional / circular mean of periodic angles in degrees [-180.0, 180.0]."""
        if not angles:
            return 0.0
        rads = np.radians(np.asarray(angles, dtype=float))
        sin_sum = float(np.sum(np.sin(rads)))
        cos_sum = float(np.sum(np.cos(rads)))
        if np.hypot(sin_sum, cos_sum) < 1e-12:
            return 0.0
        mean_rad = np.arctan2(sin_sum, cos_sum)
        return float(np.degrees(mean_rad))

    def _classify(self, phi: float, psi: float) -> str:
        """Classify secondary structure using self.regions dictionary."""
        for region_name, bounds in self.regions.items():
            if region_name == "coil/turn":
                continue
            phi_min, phi_max = bounds["phi"]
            psi_min, psi_max = bounds["psi"]
            if (phi_min <= phi <= phi_max) and (psi_min <= psi <= psi_max):
                return region_name
        return "coil/turn"

    @staticmethod
    def classify_omega(omega: float) -> str:
        """Classify peptide bond omega dihedral as 'trans' or 'cis' (|omega| >= 90 deg -> trans)."""
        return "trans" if abs(omega) >= 90.0 else "cis"

    def analyze_backbone(
        self,
        geometry: np.ndarray,
        h5_filepath: str | Path | None = None,
    ) -> BackboneAnalysisResult:
        """Perform comprehensive backbone dihedral analysis returning a BackboneAnalysisResult model."""
        geom = np.asarray(geometry, dtype=float)

        if not np.all(np.isfinite(geom)):
            raise ValueError("Geometry contains non-finite values.")
        if geom.ndim != 2 or geom.shape[1] != 3:
            raise ValueError(f"Geometry must have shape (N, 3), got {geom.shape}.")

        n_atoms = len(geom)
        phis: list[float] = []
        psis: list[float] = []
        omegas: list[float] = []

        # Standard backbone ordering: N_0, CA_0, C_0, N_1, CA_1, C_1...
        num_residues = n_atoms // 3
        for i in range(num_residues):
            # phi_i: C(3i-1) - N(3i) - CA(3i+1) - C(3i+2)
            if i > 0 and 3 * i + 2 < n_atoms:
                phis.append(self._compute_dihedral(geom[3 * i - 1], geom[3 * i], geom[3 * i + 1], geom[3 * i + 2]))

            # psi_i: N(3i) - CA(3i+1) - C(3i+2) - N(3i+3)
            if 3 * i + 3 < n_atoms:
                psis.append(self._compute_dihedral(geom[3 * i], geom[3 * i + 1], geom[3 * i + 2], geom[3 * i + 3]))

            # omega_i: CA(3i+1) - C(3i+2) - N(3i+3) - CA(3i+4)
            if 3 * i + 4 < n_atoms:
                omegas.append(self._compute_dihedral(geom[3 * i + 1], geom[3 * i + 2], geom[3 * i + 3], geom[3 * i + 4]))

        # Secondary structure classification requires both phi and psi dihedrals
        if not phis or not psis:
            classification = "unknown"
            avg_phi = self._circular_mean(phis) if phis else 0.0
            avg_psi = self._circular_mean(psis) if psis else 0.0
        else:
            avg_phi = self._circular_mean(phis)
            avg_psi = self._circular_mean(psis)
            classification = self._classify(avg_phi, avg_psi)

        omega_isomers = [self.classify_omega(w) for w in omegas]
        is_all_trans = all(iso == "trans" for iso in omega_isomers) if omega_isomers else True

        if h5_filepath is not None:
            p = Path(h5_filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            with h5py.File(p, "a") as f:
                f.attrs["secondary_structure"] = classification
                f.attrs["avg_phi"] = avg_phi
                f.attrs["avg_psi"] = avg_psi
                f.attrs["is_all_trans"] = is_all_trans
                if "backbone" in f:
                    del f["backbone"]
                grp = f.create_group("backbone")
                grp.create_dataset("phis", data=np.array(phis, dtype=float))
                grp.create_dataset("psis", data=np.array(psis, dtype=float))
                grp.create_dataset("omegas", data=np.array(omegas, dtype=float))
                if omega_isomers:
                    grp.create_dataset("omega_isomers", data=np.array(omega_isomers, dtype="S8"))

        return BackboneAnalysisResult(
            classification=classification,
            avg_phi=avg_phi,
            avg_psi=avg_psi,
            phis=phis,
            psis=psis,
            omegas=omegas,
            omega_isomers=omega_isomers,
            is_all_trans=is_all_trans,
        )

    def evaluate_backbone(
        self,
        geometry: np.ndarray,
        h5_filepath: str | Path | None = None,
    ) -> tuple[str, float, float]:
        """Evaluate backbone secondary structure, returning (classification, avg_phi, avg_psi)."""
        result = self.analyze_backbone(geometry=geometry, h5_filepath=h5_filepath)
        return result.classification, result.avg_phi, result.avg_psi
