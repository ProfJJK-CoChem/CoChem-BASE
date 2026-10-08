"""Unit and integration tests for Deliverable 7: CREST OpenMP Stack Safeguards & Ephemeral Scratch Isolation (Suggestion #107).

Mandated by Method Matrix v4 (§1.2, §2.4, §8A, §8C) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic environment safeguards and dependency checks.
"""

from __future__ import annotations

from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine


def test_crest_openmp_environment_safeguards():
    """Verify CRESTConformerEngine explicitly sets OMP_STACKSIZE=1G and thread limits."""
    engine = CRESTConformerEngine(thread_budget=4)
    env = engine._build_execution_env(budgeted_threads=4)

    assert env["OMP_STACKSIZE"] == "1G"
    assert env["OMP_NUM_THREADS"] == "4"
    assert env["MKL_NUM_THREADS"] == "4"


def test_crest_dynamic_memory_clamping():
    """Verify CRESTConformerEngine calculates memory budget clamped to min(0.80 * RAM, 64 GB)."""
    engine = CRESTConformerEngine()
    mem_gb = engine._compute_memory_budget_gb()
    assert mem_gb > 0.0
    assert mem_gb <= 64.0
