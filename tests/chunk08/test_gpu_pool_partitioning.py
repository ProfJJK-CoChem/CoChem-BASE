# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 6 (Suggestion #76):
Partitioned GPU Pools & VRAM Guardrails.
Verifies that large-basis PySCF jobs route to gpu_anchor_pyscf while MLFF jobs
route to gpu_scout_mlff.
"""

from __future__ import annotations

import pytest

from cochem_base.core_engine.hetero_config import (
    determine_gpu_executor_pool,
    route_task_by_theory_level,
)


def test_gpu_pool_partitioning_routing() -> None:
    """Verify that level-of-theory tags properly route to either

    gpu_scout_mlff (MPS pool) or gpu_anchor_pyscf (dedicated 22+ GB pool).
    """
    # Lightweight MLFF screening routes to gpu_scout_mlff
    assert determine_gpu_executor_pool("mace") == "gpu_scout_mlff"
    assert determine_gpu_executor_pool("MACE-OFF24m") == "gpu_scout_mlff"
    assert determine_gpu_executor_pool("aimnet2") == "gpu_scout_mlff"
    assert determine_gpu_executor_pool("mlff_screening") == "gpu_scout_mlff"
    assert route_task_by_theory_level({"theory_level": "mlff"}) == "gpu_scout_mlff"

    # Heavy electronic structure / large basis PySCF routes to gpu_anchor_pyscf
    assert determine_gpu_executor_pool("gpu4pyscf") == "gpu_anchor_pyscf"
    assert determine_gpu_executor_pool("pyscf_def2_tzvpp") == "gpu_anchor_pyscf"
    assert determine_gpu_executor_pool("def2-qzvpp") == "gpu_anchor_pyscf"
    assert determine_gpu_executor_pool("pyscf_large_dft") == "gpu_anchor_pyscf"
    assert route_task_by_theory_level({"theory_level": "gpu4pyscf", "basis": "def2-tzvpp"}) == "gpu_anchor_pyscf"
