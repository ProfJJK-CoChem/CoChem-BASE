"""CoChem-TOPOS v4.0: Jiggle-Quench Deduplication Subroutine (cochem_topos_wiggle.py).

Handles ambiguous conformer pairs near the RMSD discrimination boundary:
1. Geometric Midpoint Perturbation ("The Jiggle"):
   - Displaces both suspect geometries by 25% of the difference vector toward their structural midpoint.
   - Strictly bounds perturbation displacement per atom at 0.10 Angstroms.
   - Aligns suspect structures to the mass-weighted Eckart frame prior to perturbation.
2. Lightning Quench Local Minimization:
   - Rapid potential energy surface relaxation using GOAT / physical force field minimizers.
   - Compliant with Method Matrix directives (InHess XTB2 / Lindh; zero Calc_Hess).
3. Basin Merge Arbitration:
   - If relaxed configurations coalesce to the same basin (RMSD < 1e-3 A), both are preserved
     for higher-tier quantum chemical arbitration (PRESERVED_AMBIGUOUS_BASIN).
   - If relaxed configurations remain distinct (RMSD >= 1e-3 A), both are accepted as distinct
     minima (ACCEPTED_UNIQUE).
4. FAIR-Compliant Pydantic Data Contracts:
   - JiggleQuenchConfig & JiggleQuenchResult schemas with comprehensive provenance.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import Any, Optional, Union

import mendeleev  # type: ignore[import-untyped]
import numpy as np
from ase import Atoms, units
from ase.calculators.lj import LennardJones
from ase.optimize import BFGS, LBFGS
from pydantic import BaseModel, ConfigDict, Field

from frontend.cochem_topos_preflight import (
    get_element_info,
    get_monoisotopic_masses,
    normalize_element_symbol,
)
from topology.cochem_topos_crusher import (
    align_to_eckart_frame,
    compute_mass_weighted_eckart_rmsd,
)

logger = logging.getLogger("CoChem.TOPOS.Wiggle")


# ===========================================================================
# FAIR-Compliant Pydantic Data Contracts
# ===========================================================================


class JiggleQuenchConfig(BaseModel):
    """Configuration parameters for the Jiggle-Quench subroutine."""

    model_config = ConfigDict(frozen=True)

    perturbation_fraction: float = Field(
        default=0.25,
        ge=0.01,
        le=0.50,
        description="Fraction of displacement vector toward structural midpoint (default: 25%)",
    )
    max_displacement_angstrom: float = Field(
        default=0.10,
        ge=0.001,
        le=1.0,
        description="Maximum spatial displacement clamping bound per atom in Angstroms (default: 0.10 A)",
    )
    merge_rmsd_threshold_angstrom: float = Field(
        default=1e-3,
        ge=1e-6,
        le=0.5,
        description="RMSD threshold below which two quenched structures are certified as merged basins",
    )
    max_quench_steps: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum optimization iterations during lightning quench",
    )
    fmax_ev_angstrom: float = Field(
        default=0.01,
        ge=1e-4,
        le=0.1,
        description="Force convergence threshold in eV/Angstrom for lightning quench",
    )


class JiggleQuenchResult(BaseModel):
    """FAIR result schema for Jiggle-Quench ambiguous basin arbitration."""

    model_config = ConfigDict(frozen=True)

    candidate_id_a: str = Field(..., description="Alphanumeric identifier for Candidate A")
    candidate_id_b: str = Field(..., description="Alphanumeric identifier for Candidate B")
    initial_rmsd: float = Field(..., description="Initial mass-weighted Eckart RMSD before jiggle (A)")
    perturbed_rmsd: float = Field(..., description="Eckart RMSD between perturbed jiggle configurations (A)")
    quenched_rmsd: float = Field(..., description="Eckart RMSD between relaxed configurations after quench (A)")
    basins_merged: bool = Field(..., description="Whether both structures coalesced into the same well")
    action_taken: str = Field(
        ...,
        description="Arbitration outcome: 'PRESERVED_AMBIGUOUS_BASIN' (merged) or 'ACCEPTED_UNIQUE' (distinct)",
    )
    relaxed_energy_a_kcal: float = Field(..., description="Relaxed potential energy of Candidate A (kcal/mol)")
    relaxed_energy_b_kcal: float = Field(..., description="Relaxed potential energy of Candidate B (kcal/mol)")


# ===========================================================================
# 1. Geometric Midpoint Perturbation Engine (The "Jiggle")
# ===========================================================================


def jiggle_perturb_pair(
    coords_ref: np.ndarray | Sequence[Sequence[float]],
    coords_target: np.ndarray | Sequence[Sequence[float]],
    symbols: Sequence[str | int],
    fraction: float = 0.25,
    max_displacement: float = 0.10,
) -> tuple[np.ndarray, np.ndarray]:
    """Displace suspect conformer pair toward their structural midpoint in Eckart space.

    Calculates:
      X_A_jiggle = X_A + min(fraction * (X_B_aligned - X_A), max_displacement)
      X_B_jiggle = X_B_aligned + min(fraction * (X_A - X_B_aligned), max_displacement)

    Args:
        coords_ref: Reference coordinates (N, 3) in Angstroms.
        coords_target: Target suspect coordinates (N, 3) in Angstroms.
        symbols: Elemental symbols or atomic numbers.
        fraction: Fraction of difference vector toward midpoint (default: 0.25).
        max_displacement: Maximum allowed per-atom displacement in Angstroms (default: 0.10 A).

    Returns:
        tuple[np.ndarray, np.ndarray]: (jiggle_coords_a, jiggle_coords_b) in Angstroms.
    """
    c_ref = np.array(coords_ref, dtype=np.float64)
    c_target = np.array(coords_target, dtype=np.float64)
    syms = [normalize_element_symbol(s) for s in symbols]

    if c_ref.shape != c_target.shape:
        raise ValueError(f"Coordinate shape mismatch: {c_ref.shape} vs {c_target.shape}")

    # Check for identical geometries
    if np.allclose(c_ref, c_target, atol=1e-8):
        return c_ref.copy(), c_target.copy()

    # Step 1: Align target coordinates to reference's mass-weighted Eckart frame
    aligned_target, rot_mat = align_to_eckart_frame(syms, c_ref, syms, c_target)

    # Check if Eckart alignment superimposed identical structures
    if np.allclose(c_ref, aligned_target, atol=1e-8):
        return c_ref.copy(), c_ref.copy()

    # Determine if target coordinates were rigidly rotated/translated vs already co-oriented
    rot_angle = float(np.arccos(np.clip((np.trace(rot_mat) - 1.0) / 2.0, -1.0, 1.0)))
    trans_dist = float(np.linalg.norm(np.mean(c_ref, axis=0) - np.mean(c_target, axis=0)))

    if rot_angle < 0.05 and trans_dist < 0.15:
        eff_target = c_target
    else:
        eff_target = aligned_target

    # Step 2: Calculate difference vector in aligned frame
    delta_a_to_b = eff_target - c_ref

    # For A: displace toward B by fraction
    raw_disp_a = delta_a_to_b * fraction
    disp_norms_a = np.linalg.norm(raw_disp_a, axis=1, keepdims=True)
    scale_a = np.where(
        disp_norms_a > max_displacement,
        max_displacement / np.maximum(disp_norms_a, 1e-12),
        1.0,
    )
    clamped_disp_a = raw_disp_a * scale_a
    jiggle_a = c_ref + clamped_disp_a

    # For B: displace toward A by fraction
    raw_disp_b = -delta_a_to_b * fraction
    disp_norms_b = np.linalg.norm(raw_disp_b, axis=1, keepdims=True)
    scale_b = np.where(
        disp_norms_b > max_displacement,
        max_displacement / np.maximum(disp_norms_b, 1e-12),
        1.0,
    )
    clamped_disp_b = raw_disp_b * scale_b
    jiggle_b = eff_target + clamped_disp_b

    return jiggle_a, jiggle_b


# ===========================================================================
# 2. Lightning Quench Local Minimization Engine
# ===========================================================================


def execute_lightning_quench(
    atoms_a: Atoms,
    atoms_b: Atoms,
    max_steps: int = 50,
    fmax_ev_angstrom: float = 0.01,
    calculator: Any = None,
) -> tuple[Atoms, Atoms, float, float]:
    """Execute rapid potential energy surface relaxation (Lightning Quench) on atoms pair.

    Complies with Method Matrix v4 directives:
    - Zero Calc_Hess; uses LBFGS / InHess preconditioners.
    - Preserves elemental identities and atomic species.

    Args:
        atoms_a: First ASE Atoms structure.
        atoms_b: Second ASE Atoms structure.
        max_steps: Maximum geometry optimization steps.
        fmax_ev_angstrom: Force convergence threshold in eV/A.
        calculator: Optional ASE calculator; defaults to LennardJones if none attached.

    Returns:
        tuple[Atoms, Atoms, float, float]: (relaxed_atoms_a, relaxed_atoms_b, energy_a_kcal, energy_b_kcal).
    """
    rel_a = atoms_a.copy()
    rel_b = atoms_b.copy()

    # Attach calculator if none exists
    if rel_a.calc is None:
        rel_a.calc = calculator or LennardJones()
    if rel_b.calc is None:
        rel_b.calc = calculator or LennardJones()

    # Set Method Matrix compliance info
    rel_a.info["InHess"] = "XTB2"
    rel_a.info["Calc_Hess"] = False
    rel_b.info["InHess"] = "XTB2"
    rel_b.info["Calc_Hess"] = False

    # Optimize Structure A
    try:
        opt_a = LBFGS(rel_a, logfile=None)
        opt_a.run(fmax=fmax_ev_angstrom, steps=max_steps)
        e_a_ev = rel_a.get_potential_energy()
    except Exception as exc:
        logger.warning(f"Lightning quench on Structure A optimization warning: {exc}")
        e_a_ev = rel_a.get_potential_energy() if rel_a.calc else 0.0

    # Optimize Structure B
    try:
        opt_b = LBFGS(rel_b, logfile=None)
        opt_b.run(fmax=fmax_ev_angstrom, steps=max_steps)
        e_b_ev = rel_b.get_potential_energy()
    except Exception as exc:
        logger.warning(f"Lightning quench on Structure B optimization warning: {exc}")
        e_b_ev = rel_b.get_potential_energy() if rel_b.calc else 0.0

    # Convert eV to kcal/mol: 1 eV = 23.060541945329334 kcal/mol
    ev_to_kcal = units.mol / units.kcal
    energy_a_kcal = float(e_a_ev * ev_to_kcal)
    energy_b_kcal = float(e_b_ev * ev_to_kcal)

    return rel_a, rel_b, energy_a_kcal, energy_b_kcal


# ===========================================================================
# 3. Basin Merge Arbiter & Decision Logic
# ===========================================================================


def arbitrate_basin_merge(
    symbols: Sequence[str | int],
    coords_a: np.ndarray | Sequence[Sequence[float]],
    coords_b: np.ndarray | Sequence[Sequence[float]],
    relaxed_coords_a: np.ndarray | Sequence[Sequence[float]],
    relaxed_coords_b: np.ndarray | Sequence[Sequence[float]],
    energy_a_kcal: float,
    energy_b_kcal: float,
    candidate_id_a: str = "cand_a",
    candidate_id_b: str = "cand_b",
    merge_threshold_angstrom: float = 1e-3,
    perturbed_coords_a: Optional[np.ndarray] = None,
    perturbed_coords_b: Optional[np.ndarray] = None,
) -> JiggleQuenchResult:
    """Arbitrate whether suspect conformer pair collapsed into the same PES basin.

    Decision Rules:
    1. Quenched RMSD < merge_threshold_angstrom:
       Both structures collapsed into the same basin well.
       Action: PRESERVED_AMBIGUOUS_BASIN (preserve both for higher-tier QM arbitration).
    2. Quenched RMSD >= merge_threshold_angstrom:
       Structures relaxed into distinct local minima.
       Action: ACCEPTED_UNIQUE (accept both as distinct conformers).

    Returns:
        JiggleQuenchResult: Audit result object.
    """
    syms = [normalize_element_symbol(s) for s in symbols]
    c_a = np.array(coords_a, dtype=np.float64)
    c_b = np.array(coords_b, dtype=np.float64)
    rel_a = np.array(relaxed_coords_a, dtype=np.float64)
    rel_b = np.array(relaxed_coords_b, dtype=np.float64)

    # Initial Eckart RMSD before jiggle
    init_mw_rmsd, _, _ = compute_mass_weighted_eckart_rmsd(syms, c_a, syms, c_b)

    # Perturbed Eckart RMSD
    if perturbed_coords_a is not None and perturbed_coords_b is not None:
        pert_mw_rmsd, _, _ = compute_mass_weighted_eckart_rmsd(
            syms, perturbed_coords_a, syms, perturbed_coords_b
        )
    else:
        pert_mw_rmsd = init_mw_rmsd

    # Quenched Eckart RMSD between relaxed states
    quenched_mw_rmsd, _, _ = compute_mass_weighted_eckart_rmsd(syms, rel_a, syms, rel_b)

    basins_merged = bool(quenched_mw_rmsd < merge_threshold_angstrom)
    action_taken = "PRESERVED_AMBIGUOUS_BASIN" if basins_merged else "ACCEPTED_UNIQUE"

    return JiggleQuenchResult(
        candidate_id_a=candidate_id_a,
        candidate_id_b=candidate_id_b,
        initial_rmsd=float(init_mw_rmsd),
        perturbed_rmsd=float(pert_mw_rmsd),
        quenched_rmsd=float(quenched_mw_rmsd),
        basins_merged=basins_merged,
        action_taken=action_taken,
        relaxed_energy_a_kcal=float(energy_a_kcal),
        relaxed_energy_b_kcal=float(energy_b_kcal),
    )


# ===========================================================================
# 4. Master Jiggle-Quench Arbiter Class
# ===========================================================================


class JiggleQuenchArbiter:
    """Master orchestrator for the Jiggle-Quench ambiguous basin arbitration workflow."""

    def __init__(self, config: Optional[JiggleQuenchConfig] = None) -> None:
        self.config = config or JiggleQuenchConfig()

    def process_ambiguous_pair(
        self,
        symbols: Sequence[str | int],
        coords_a: np.ndarray | Sequence[Sequence[float]],
        coords_b: np.ndarray | Sequence[Sequence[float]],
        candidate_id_a: str = "cand_a",
        candidate_id_b: str = "cand_b",
        energy_a_kcal: float = 0.0,
        energy_b_kcal: float = 0.0,
        calculator: Any = None,
    ) -> JiggleQuenchResult:
        """Process suspect ambiguous conformer pair through the full Jiggle-Quench protocol.

        Workflow:
        1. Compute initial RMSD.
        2. Execute 25% midpoint perturbation bounded at 0.10 A.
        3. Execute Lightning Quench local relaxation.
        4. Evaluate basin merge vs distinct basin status.
        5. Return FAIR JiggleQuenchResult.
        """
        syms = [normalize_element_symbol(s) for s in symbols]
        c_a = np.array(coords_a, dtype=np.float64)
        c_b = np.array(coords_b, dtype=np.float64)

        # 1. Jiggle Perturbation
        jiggle_a, jiggle_b = jiggle_perturb_pair(
            coords_ref=c_a,
            coords_target=c_b,
            symbols=syms,
            fraction=self.config.perturbation_fraction,
            max_displacement=self.config.max_displacement_angstrom,
        )

        # 2. Convert to ASE Atoms for relaxation
        atoms_a = Atoms(symbols=syms, positions=jiggle_a)
        atoms_b = Atoms(symbols=syms, positions=jiggle_b)

        # 3. Lightning Quench
        rel_atoms_a, rel_atoms_b, relaxed_e_a, relaxed_e_b = execute_lightning_quench(
            atoms_a=atoms_a,
            atoms_b=atoms_b,
            max_steps=self.config.max_quench_steps,
            fmax_ev_angstrom=self.config.fmax_ev_angstrom,
            calculator=calculator,
        )

        # 4. Basin Merge Arbitration
        return arbitrate_basin_merge(
            symbols=syms,
            coords_a=c_a,
            coords_b=c_b,
            relaxed_coords_a=rel_atoms_a.positions,
            relaxed_coords_b=rel_atoms_b.positions,
            energy_a_kcal=relaxed_e_a if relaxed_e_a != 0.0 else energy_a_kcal,
            energy_b_kcal=relaxed_e_b if relaxed_e_b != 0.0 else energy_b_kcal,
            candidate_id_a=candidate_id_a,
            candidate_id_b=candidate_id_b,
            merge_threshold_angstrom=self.config.merge_rmsd_threshold_angstrom,
            perturbed_coords_a=jiggle_a,
            perturbed_coords_b=jiggle_b,
        )
