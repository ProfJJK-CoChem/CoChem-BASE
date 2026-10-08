"""
quadrature_manager.py - Dynamic Quadrature Grid Lifecycle & Coupled Grid-SCF Engine.
Method Matrix v4.1: §2.5, §3.3, §4.4, Verification Requirement VR-03.
Standard Compliance: IEEE 830-1998 / Method Matrix v4.1 Zero-Trust Directive.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Union

from cochem_base.exceptions import GridSpecificationError

logger = logging.getLogger(__name__)


class GridStage(int, Enum):
    """Three-stage dynamic quadrature grid lifecycle progression [M]."""
    STAGE_1 = 1  # Pre-Screening & Conformer Sweep (T1/T3)
    STAGE_2 = 2  # Intermediate Electronic Relaxation (T4)
    STAGE_3 = 3  # Spectroscopic Final Convergence, Hessian, VPT2 (T5/T7/T8)


@dataclass(frozen=True)
class GridSpec:
    """Specification and numerical parameters of a quadrature grid stage."""
    stage: GridStage
    grid_keyword: str
    lebedev_points: int
    angular_grid: int
    pruned: bool
    tol_max_g: float
    tol_e: float
    scf_setting: str
    scf_tol_e: float
    scf_thresh: float


STAGE_SPECS: Dict[GridStage, GridSpec] = {
    GridStage.STAGE_1: GridSpec(
        stage=GridStage.STAGE_1,
        grid_keyword="DEFGRID1",
        lebedev_points=110,
        angular_grid=2,
        pruned=True,
        # The proposal addition tightens Chunk 17's screening gate. Retain
        # Chunk 17's three grids, with measured max |g| <= 1e-4 before promotion.
        tol_max_g=1.0e-4,
        tol_e=1.0e-5,
        scf_setting="NormalSCF",
        scf_tol_e=1.0e-6,
        scf_thresh=1.0e-8,
    ),
    GridStage.STAGE_2: GridSpec(
        stage=GridStage.STAGE_2,
        grid_keyword="DEFGRID2",
        lebedev_points=302,
        angular_grid=4,
        pruned=True,
        tol_max_g=1.0e-4,
        tol_e=1.0e-6,
        scf_setting="TightSCF",
        scf_tol_e=1.0e-8,
        scf_thresh=1.0e-10,
    ),
    GridStage.STAGE_3: GridSpec(
        stage=GridStage.STAGE_3,
        grid_keyword="DEFGRID3",
        lebedev_points=590,
        angular_grid=6,
        pruned=False,
        tol_max_g=1.0e-5,
        tol_e=1.0e-7,
        scf_setting="VeryTightSCF",
        scf_tol_e=1.0e-8,
        scf_thresh=1.0e-11,
    ),
}


class QuadratureManager:
    """Manages the 3-stage dynamic grid lifecycle and enforces the Coupled Grid-SCF Invariant."""

    @staticmethod
    def get_stage_spec(stage: Union[int, GridStage]) -> GridSpec:
        """Retrieve authoritative specification for a given grid lifecycle stage."""
        try:
            if isinstance(stage, bool):
                raise ValueError
            stage_enum = GridStage(stage)
        except ValueError as exc:
            raise GridSpecificationError(f"Unknown quadrature stage: {stage!r}") from exc
        return STAGE_SPECS[stage_enum]

    @staticmethod
    def validate_coupled_grid_scf_invariant(
        grid_keyword: str,
        is_frequency_or_hessian: bool = False,
        is_vpt2: bool = False,
        scf_setting: Optional[str] = None,
    ) -> None:
        """Enforces the Coupled Grid-SCF Invariant (Method Matrix v4.1 §2.5, VR-03).

        Executing numerical frequencies, harmonic Hessians, or VPT2 calculations
        on grids coarser than DEFGRID3 raises GridSpecificationError [M].
        """
        clean_grid = grid_keyword.strip().upper()
        is_spectroscopic_task = is_frequency_or_hessian or is_vpt2
        if clean_grid not in {"DEFGRID1", "DEFGRID2", "DEFGRID3"}:
            raise GridSpecificationError(f"ORCA requires DEFGRID1, DEFGRID2 or DEFGRID3; got {grid_keyword!r}.")

        if is_spectroscopic_task:
            if clean_grid in {"DEFGRID1", "DEFGRID2"} or "GRID1" in clean_grid or "GRID2" in clean_grid:
                raise GridSpecificationError(
                    f"[METHOD_MATRIX_VIOLATION_DEFGRID] Spectroscopic task requested with coarse grid '{grid_keyword}'. "
                    f"Frequencies, Hessians, and VPT2 strictly require DEFGRID3 or finer [M]."
                )
            if clean_grid != "DEFGRID3":
                raise GridSpecificationError(
                    f"[METHOD_MATRIX_VIOLATION_DEFGRID] Unrecognized or coarse grid '{grid_keyword}' for spectroscopic task. "
                    f"DEFGRID3 is mandated by Method Matrix v4.1 §2.5 [M]."
                )

        # Stage 3 requires TightSCF or VeryTightSCF
        if clean_grid == "DEFGRID3" and scf_setting:
            clean_scf = scf_setting.strip().upper()
            if clean_scf not in {"TIGHTSCF", "VERYTIGHTSCF", "EXTREMESCF"}:
                raise GridSpecificationError(
                    f"[METHOD_MATRIX_VIOLATION_DEFGRID] DEFGRID3 requires TightSCF or VeryTightSCF, but got '{scf_setting}' [M]."
                )

    @staticmethod
    def determine_next_stage(
        current_stage: Union[int, GridStage],
        current_max_gradient: float,
        current_energy_change: float,
        intermolecular_rmsd: Optional[float] = None,
    ) -> GridStage:
        """Evaluates convergence checkpoints to determine if the grid should be tightened.

        Stage 1 -> Stage 2: max_g <= 1e-4 a.u. and |dE| <= 1e-5 Eh.
        Stage 2 -> Stage 3: max_g <= 1e-4 a.u., |dE| <= 1e-6 Eh, and intermolecular_rmsd < 0.05 A [M].
        """
        curr_enum = GridStage(current_stage)
        spec = STAGE_SPECS[curr_enum]
        if not math.isfinite(current_max_gradient) or current_max_gradient < 0:
            raise GridSpecificationError("Maximum gradient must be finite and nonnegative.")
        if not math.isfinite(current_energy_change):
            raise GridSpecificationError("Energy change must be finite.")
        if intermolecular_rmsd is not None and (
            not math.isfinite(intermolecular_rmsd) or intermolecular_rmsd < 0
        ):
            raise GridSpecificationError("Intermolecular RMSD must be finite and nonnegative.")

        # If current stage converged to its threshold, advance to the next stage
        if curr_enum == GridStage.STAGE_1:
            if current_max_gradient <= spec.tol_max_g and abs(current_energy_change) <= spec.tol_e:
                logger.info(f"Stage 1 converged (max_g={current_max_gradient:.2e}, dE={current_energy_change:.2e}). Advancing to Stage 2.")
                return GridStage.STAGE_2
            return GridStage.STAGE_1

        elif curr_enum == GridStage.STAGE_2:
            grad_energy_converged = (
                current_max_gradient <= spec.tol_max_g and abs(current_energy_change) <= spec.tol_e
            )
            rmsd_converged = intermolecular_rmsd is not None and intermolecular_rmsd < 0.05
            if grad_energy_converged and rmsd_converged:
                logger.info(
                    f"Stage 2 converged (max_g={current_max_gradient:.2e}, dE={current_energy_change:.2e}, "
                    f"rmsd={intermolecular_rmsd}). Advancing to Stage 3."
                )
                return GridStage.STAGE_3
            return GridStage.STAGE_2

        return GridStage.STAGE_3

    @staticmethod
    def get_orca_keywords_for_stage(stage: Union[int, GridStage], is_opt: bool = True) -> str:
        """Returns the recommended ORCA keyword string for the given stage."""
        spec = QuadratureManager.get_stage_spec(stage)
        keywords = [spec.grid_keyword, spec.scf_setting]
        if is_opt:
            keywords.append("Opt")
        return " ".join(keywords)


__all__ = [
    "GridStage",
    "GridSpec",
    "STAGE_SPECS",
    "QuadratureManager",
]
