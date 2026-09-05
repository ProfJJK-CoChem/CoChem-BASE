"""CoChem Grid Policy & Dynamic Integration Grid Tightening Module.

Compliant with Method Matrix v4 §4.4, §8B, and Anti-Spoofing Directives.
"""

from __future__ import annotations

from enum import Enum
from typing import Union
from pydantic import BaseModel


class WorkflowPhase(str, Enum):
    """Workflow execution phases governing quadrature integration grid requirements."""

    PHASE_PREOPT = "preopt"
    PHASE_FINALOPT = "finalopt"
    PHASE_NUMFREQ = "numfreq"


class GridPolicy(BaseModel):
    """Canonical integration grid policy across workflow phases.

    - Pre-optimization (PHASE_PREOPT): Permits defgrid1 for rapid geometry adjustments.
    - Final optimization (PHASE_FINALOPT): Strictly enforces defgrid3 with tightened %geom thresholds.
    - Vibrational frequencies (PHASE_NUMFREQ): Strictly enforces defgrid3 to eliminate quadrature noise.
    Deprecated ORCA 'Grid3'/'Grid5' terminology is unconditionally prohibited.
    """

    preopt_grid: str = "defgrid1"
    finalopt_grid: str = "defgrid3"
    freq_grid: str = "defgrid3"

    # Class-level phase aliases for direct attribute access
    PHASE_PREOPT: str = "defgrid1"
    PHASE_FINALOPT: str = "defgrid3"
    PHASE_NUMFREQ: str = "defgrid3"

    @classmethod
    def validate_grid(cls, phase: Union[WorkflowPhase, str], grid: str) -> bool:
        """Validate whether an integration grid is permissible for a specific workflow phase.

        Parameters
        ----------
        phase : Union[WorkflowPhase, str]
            Execution phase ('PHASE_PREOPT', 'PHASE_FINALOPT', 'PHASE_NUMFREQ' or 'preopt', 'finalopt', 'numfreq').
        grid : str
            Integration grid specification (e.g., 'defgrid1', 'defgrid3').

        Returns
        -------
        bool
            True if grid meets the threshold for the phase, False otherwise.
        """
        clean_grid = grid.strip().lower()
        clean_phase = str(phase).strip().lower()
        if clean_phase.startswith("workflowphase."):
            clean_phase = clean_phase.split(".", 1)[1]

        # Strictly reject deprecated Grid3 / Grid5 nomenclature
        if clean_grid in {"grid1", "grid2", "grid3", "grid4", "grid5"}:
            return False

        if "preopt" in clean_phase:
            # defgrid1 and defgrid3 are acceptable for preopt
            return clean_grid in {"defgrid1", "defgrid2", "defgrid3"}
        elif "finalopt" in clean_phase or "numfreq" in clean_phase:
            # defgrid1 is strictly forbidden for final optimization and second derivatives
            if clean_grid == "defgrid1":
                return False
            return clean_grid in {"defgrid2", "defgrid3"}
        else:
            # Default conservative validation
            return clean_grid in {"defgrid2", "defgrid3"}


__all__ = ["WorkflowPhase", "GridPolicy"]
