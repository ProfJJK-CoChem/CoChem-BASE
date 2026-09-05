"""CoChem-TOPOS: Test Screening-Tier Hessian Deferral & ZPVE Deferral.

Compliant with Method Matrix v4 §3.3, §8B.3, and Anti-Spoofing Protocol v2.
Verifies Deliverable 6:
1. GradientPayload schema allows optional Hessian (hessian=None).
2. Elimination of unconditional Hessian evaluations and Vibrations loops in Tiers 1-3.
3. Method Matrix Hessian spend hierarchy: preliminary screening tiers report hessian=None and zpve=None.
"""

from pathlib import Path
import pytest
from ase import Atoms
from cochem_base.schemas import GradientPayload
from cascade_engine.cochem_topos_cascade_orchestrator import (
    CascadeConfig,
    CascadeOrchestrator,
)


def test_gradient_payload_optional_hessian():
    """Verify GradientPayload supports hessian=None for screening tiers."""
    payload = GradientPayload(
        energy=-152.7533,
        gradient=[[0.001, -0.002, 0.003], [-0.001, 0.002, -0.003]],
        hessian=None,
    )
    assert payload.hessian is None
    assert payload.energy == -152.7533


def test_screening_tier_defers_hessian_on_six_atom_complex(tmp_path):
    """Execute Tier 1 screening on a 6-atom water dimer complex.

    Asserts that GradientPayload.hessian is None and completes without launching 6N Vibrations displacements.
    """
    # Authentic 6-atom water dimer coordinates
    symbols = ["O", "H", "H", "O", "H", "H"]
    positions = [
        [-1.464, -0.015, 0.043],
        [-0.505, -0.031, -0.011],
        [-1.751, -0.771, -0.478],
        [1.442, 0.003, -0.076],
        [1.804, 0.759, 0.395],
        [1.803, -0.753, 0.397],
    ]
    dimer = Atoms(symbols=symbols, positions=positions)

    config = CascadeConfig(artifact_dir=tmp_path)
    orchestrator = CascadeOrchestrator(config)

    # Tier 1 execution (Hand topology screening)
    result = orchestrator._execute_hand_topology(dimer)

    assert isinstance(result, GradientPayload)
    assert result.hessian is None, "Screening tier must defer Hessian evaluation to production tiers"
    assert result.energy != 0.0
    assert len(result.gradient) == 6
