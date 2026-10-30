"""Deprecated checkout alias for the BASE-owned implementation.

This compatibility module contains no scientific implementation and is excluded
from the BASE distribution. Import from cochem_base.intake.conformer_orchestrator.
"""
from cochem_base.intake.conformer_orchestrator import (
    kabsch_rmsd, deduplicate_union_ensemble, ConformerOrchestrator,
)

__all__ = ['kabsch_rmsd', 'deduplicate_union_ensemble', 'ConformerOrchestrator']
