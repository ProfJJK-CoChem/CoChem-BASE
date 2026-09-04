"""
CoChem Ecosystem Configuration and Integration Grid Policy.
Compliant with Method Matrix v4 §4.4 and Method Matrix v4 Table 2.
"""

from __future__ import annotations

from typing import Final


class GridPolicy:
    """Specifies and validates allowed DFT integration grids per execution phase.

    Method Matrix v4 §4.4 Directives:
    - Preliminary relaxation starts on loose integration grids ('defgrid1').
    - Upon loose convergence, dynamically tighten to 'defgrid3'.
    - Vibrational second derivatives ('! Freq') MUST execute exclusively on 'defgrid3'.
    """

    PHASE_PREOPT: Final[str] = "defgrid1"
    PHASE_FINALOPT: Final[str] = "defgrid3"
    PHASE_NUMFREQ: Final[str] = "defgrid3"

    @classmethod
    def validate_grid(cls, phase: str, grid: str) -> bool:
        """Validate if a specified grid is permitted for a given execution phase.

        Parameters
        ----------
        phase : str
            Execution phase: 'PHASE_PREOPT', 'PHASE_FINALOPT', 'PHASE_NUMFREQ' (or lower/mixed case).
        grid : str
            Requested integration grid (e.g. 'defgrid1', 'defgrid2', 'defgrid3').

        Returns
        -------
        bool
            True if grid is permitted, False otherwise.
        """
        p_clean = phase.strip().upper()
        g_clean = grid.strip().lower()

        if "PREOPT" in p_clean:
            # Preliminary relaxation accepts defgrid1, defgrid2, defgrid3
            return g_clean in ["defgrid1", "defgrid2", "defgrid3"]
        elif "FINALOPT" in p_clean:
            # Final optimization rejects defgrid1; requires defgrid2 or defgrid3
            return g_clean in ["defgrid2", "defgrid3"]
        elif "NUMFREQ" in p_clean or "FREQ" in p_clean:
            # Vibrational frequencies require defgrid3 exclusively
            return g_clean in ["defgrid3"]

        return False
