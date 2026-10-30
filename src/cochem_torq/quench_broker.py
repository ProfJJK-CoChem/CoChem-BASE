"""Deprecated checkout alias for the BASE-owned implementation.

This compatibility module contains no scientific implementation and is excluded
from the BASE distribution. Import from cochem_base.intake.quench_broker.
"""
from cochem_base.intake.quench_broker import (
    QuenchMethodology, QuenchRequest, QuenchResponse, QuenchExecutionError, BinaryNotFoundError, IPCTrajectoryQuenchBroker,
)

__all__ = ['QuenchMethodology', 'QuenchRequest', 'QuenchResponse', 'QuenchExecutionError', 'BinaryNotFoundError', 'IPCTrajectoryQuenchBroker']
