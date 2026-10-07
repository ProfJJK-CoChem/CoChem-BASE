"""CoChem Grid Policy & Dynamic Integration Grid Tightening Module.

Compliant with Method Matrix v4 §4.4, §8B, and Anti-Spoofing Directives.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar, Literal, Union
from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    preopt_grid: Literal["defgrid1", "defgrid2", "defgrid3"] = "defgrid1"
    finalopt_grid: Literal["defgrid3"] = "defgrid3"
    freq_grid: Literal["defgrid3"] = "defgrid3"

    # Class-level phase aliases for direct attribute access
    PHASE_PREOPT: ClassVar[str] = "defgrid1"
    PHASE_FINALOPT: ClassVar[str] = "defgrid3"
    PHASE_NUMFREQ: ClassVar[str] = "defgrid3"

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
        if not isinstance(grid, str) or not isinstance(phase, str):
            return False
        clean_grid = grid.strip().lower()
        clean_phase = phase.value if isinstance(phase, WorkflowPhase) else phase.strip().lower()
        if clean_phase.startswith("phase_"):
            clean_phase = clean_phase[len("phase_"):]
        if clean_phase == "preopt":
            return clean_grid in {"defgrid1", "defgrid2", "defgrid3"}
        if clean_phase in {"finalopt", "numfreq"}:
            return clean_grid == "defgrid3"
        return False


__all__ = ["WorkflowPhase", "GridPolicy"]
