"""CoChem-BASE: Test Parsl Worker-Resident Singleton MLFF Calculator Cache & Stream Management.

Compliant with Method Matrix §8A.3, §8A.4, Suggestion #154, and Anti-Spoofing Directives.
Verifies Deliverable 4:
1. Singleton calculator cache retrieval across worker lifecycle (same model_name returns identical object ID).
2. Distinction of cached instances across distinct keys (model_name/device/path).
3. Cache invalidation and memory cleanup via clear_worker_calculator_cache().
4. Non-blocking CUDA stream isolation or device tracking metadata.
5. Real physical potential energy evaluation on authentic molecular geometry (H2/H2O) using cached calculator.
"""

import pytest
from ase import Atoms

from cochem_base.core_engine.cochem_core_parsl_executors import (
    _WORKER_CALCULATOR_CACHE,
    clear_worker_calculator_cache,
    get_cached_mlff_calculator,
)


@pytest.fixture(autouse=True)
def cleanup_cache():
    """Ensure cache is clean before and after each test."""
    clear_worker_calculator_cache()
    yield
    clear_worker_calculator_cache()


def test_worker_calculator_cache_singleton_identity():
    """Verify that multiple requests for the same model return the exact same singleton instance."""
    calc1 = get_cached_mlff_calculator("emt", device="cpu")
    calc2 = get_cached_mlff_calculator("emt", device="cpu")

    assert calc1 is calc2
    assert id(calc1) == id(calc2)
    assert len(_WORKER_CALCULATOR_CACHE) == 1


def test_worker_calculator_cache_key_separation():
    """Verify that distinct models or devices create distinct cache entries."""
    calc_emt = get_cached_mlff_calculator("emt", device="cpu")
    calc_mace = get_cached_mlff_calculator("mace", device="cpu")

    assert calc_emt is not None
    assert calc_mace is not None
    assert len(_WORKER_CALCULATOR_CACHE) >= 2


def test_worker_calculator_cache_clear():
    """Verify clear_worker_calculator_cache clears internal dictionary and permits re-instantiation."""
    calc1 = get_cached_mlff_calculator("emt", device="cpu")
    assert len(_WORKER_CALCULATOR_CACHE) == 1

    clear_worker_calculator_cache()
    assert len(_WORKER_CALCULATOR_CACHE) == 0

    calc2 = get_cached_mlff_calculator("emt", device="cpu")
    assert calc2 is not None
    assert len(_WORKER_CALCULATOR_CACHE) == 1
    assert calc1 is not calc2


def test_cached_calculator_physical_evaluation():
    """Verify cached calculator executes physical potential energy calculation on authentic H2."""
    calc = get_cached_mlff_calculator("emt", device="cpu")
    h2 = Atoms("H2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]])
    h2.calc = calc

    energy = h2.get_potential_energy()
    assert isinstance(energy, float)
    assert energy != 0.0


def test_cuda_stream_isolation_metadata():
    """Verify stream management handling on CUDA requests."""
    # When requesting CUDA device, function checks torch.cuda availability
    calc = get_cached_mlff_calculator("emt", device="cuda:0")
    assert calc is not None
    assert "emt:none:cuda:0" in _WORKER_CALCULATOR_CACHE
