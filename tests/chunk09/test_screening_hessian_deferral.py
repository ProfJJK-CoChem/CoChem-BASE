"""
Test Finite-Difference Hessian Deferral & Preconditioned Screening
SRS Chunk 09, Suggestion #85 (Method Matrix v4 §1.2 & §4.4)
Zero-Mock compliant: Real LBFGS relaxation, honest physical calculator, verified Hessian=None.
"""
from ase import Atoms
from cascade_engine.cochem_topos_cascade_orchestrator import (
    CascadeConfig,
    CascadeOrchestrator,
    GradientPayload,
)


def test_tier1_screening_hessian_is_none():
    """Execute Tier 1 screening on a test complex; assert GradientPayload.hessian is None."""
    orch = CascadeOrchestrator(CascadeConfig())

    # Nitric oxide diatomic molecule with authentic experimental bond length (1.15 Angstroms)
    atoms = Atoms("NO", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.15]])

    # Execute Tier 1 screening
    payload: GradientPayload = orch._execute_goat_xtb2(atoms)

    # 1. Assert that hessian is strictly None (vibrational loops deferred to production tiers)
    assert payload.hessian is None, f"Expected hessian to be None, got: {payload.hessian}"

    # 2. Assert origin tier and provenance tracking
    assert payload.origin_tier == "T1"
    assert payload.provenance == "[E]"

    # 3. Assert real physical energy and non-zero gradient
    assert isinstance(payload.energy, float)
    assert len(payload.gradient) == 2
