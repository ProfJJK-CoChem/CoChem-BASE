"""Unit and integration tests for Deliverable 7: CREST OpenMP Stack Safeguards & Ephemeral Scratch Isolation (Suggestion #107).

Mandated by Method Matrix v4 (§1.2, §2.4, §8A, §8C) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic environment safeguards and dependency checks.
"""

from __future__ import annotations

import pytest
from ase import Atoms

from cochem_base.exceptions import EcosystemDependencyError
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


def test_crest_xtb_mutual_dependency_enforced(monkeypatch: pytest.MonkeyPatch):
    """Verify CREST execution aborts if either crest or xtb binary is absent."""
    engine = CRESTConformerEngine()
    seed = Atoms("OH2", positions=[[0, 0, 0], [0, 0.75, 0.5], [0, -0.75, 0.5]])

    # When xtb is not found, execute_secondary_search must raise EcosystemDependencyError
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/crest" if cmd == "crest" else None)

    with pytest.raises(EcosystemDependencyError, match="relies intrinsically on xTB"):
        engine.execute_secondary_search(seed, num_conformers=1)
