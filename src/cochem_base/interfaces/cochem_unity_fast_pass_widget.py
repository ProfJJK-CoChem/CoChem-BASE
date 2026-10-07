"""Legacy fast-pass interface using BASE's actual validated calculation service."""
from __future__ import annotations

from pathlib import Path

from cochem_base.calc.calculation_service import CalculationMatrixConfig, run_calculation
from ui.voila_layout.cochem_gui import CoChemGUI

FastPassOptConfig = CalculationMatrixConfig


class FastPassWidget(CoChemGUI):
    """Open native molecular configuration and execution."""
    def __init__(self) -> None:
        super().__init__()
        self.state.active_view = "matrix"


def run_fast_pass_optimization(config_path: str | Path, **kwargs) -> dict:
    """Execute a canonical configuration through actual engine authority checks."""
    return run_calculation(config_path, **kwargs)


__all__ = ["FastPassWidget", "FastPassOptConfig", "run_fast_pass_optimization"]
