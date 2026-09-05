"""CoChem-BASE: Test Dynamic Memory Contention Downscaling for Low-RAM Environments.

Compliant with Method Matrix §8A.1, §8A.4, Suggestion #77, #156, and Anti-Spoofing Directives.
Verifies Deliverable 6:
1. Dynamic host RAM downscaling on 16 GB systems without raising ContentionBudgetExceededError.
2. Dynamic host RAM downscaling on 8 GB systems (concurrency downscaled to 1 worker).
3. Dynamic host RAM downscaling on severely constrained (< 8 GB) environments with valid floors.
4. Default parameter execution with automatic psutil hardware probing.
5. Contention budget metrics (85% real efficiency, slowdown factor).
"""

from cochem_base.core_engine.cochem_core_parsl_executors import (
    ContentionBudget,
    calculate_contention_budget,
)


def test_contention_budget_scaling_16gb():
    """Verify that calculate_contention_budget succeeds on 16 GB systems."""
    budget = calculate_contention_budget(
        total_physical_cores=8,
        total_ram_gb=16.0,
        gpu_scout_workers=3,
        anchor_ranks=7,
    )

    assert isinstance(budget, ContentionBudget)
    assert budget.anchor_mem_per_worker_gb >= 4.0
    assert budget.scout_mem_per_worker_gb >= 1.5
    assert budget.gpu_scout_workers <= 2


def test_contention_budget_scaling_severely_constrained_8gb():
    """Verify minimum floors and single worker downscaling on 8 GB hosts."""
    budget = calculate_contention_budget(
        total_physical_cores=4,
        total_ram_gb=8.0,
        gpu_scout_workers=3,
        anchor_ranks=3,
    )

    assert isinstance(budget, ContentionBudget)
    assert budget.anchor_mem_per_worker_gb >= 4.0
    assert budget.scout_mem_per_worker_gb >= 1.5
    assert budget.gpu_scout_workers == 1


def test_contention_budget_scaling_sub_8gb():
    """Verify graceful handling of ultra-constrained memory environments (e.g. 4 GB)."""
    budget = calculate_contention_budget(
        total_physical_cores=2,
        total_ram_gb=4.0,
        gpu_scout_workers=2,
        anchor_ranks=2,
    )

    assert isinstance(budget, ContentionBudget)
    assert budget.anchor_mem_per_worker_gb >= 1.0
    assert budget.scout_mem_per_worker_gb >= 0.5
    assert budget.gpu_scout_workers == 1


def test_contention_budget_automatic_probing():
    """Verify calculate_contention_budget dynamically probes psutil when arguments are omitted."""
    budget = calculate_contention_budget()
    assert isinstance(budget, ContentionBudget)
    assert budget.total_host_ram_gb > 0.0
    assert budget.p_cores_anchor >= 1
    assert budget.real_parallelism_efficiency == 0.85
    assert budget.estimated_cpu_slowdown_factor >= 1.0
