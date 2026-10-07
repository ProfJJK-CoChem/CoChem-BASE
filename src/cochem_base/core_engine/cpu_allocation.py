"""Explicit CPU allocation units; observed silicon topology stays unchanged."""
from __future__ import annotations

from enum import Enum
import os
import platform
from typing import Mapping
from typing import Any


class CPUAllocationPolicy(str, Enum):
    PHYSICAL_CORES = "physical_cores"
    GITHUB_HOSTED_VCPUS = "github_hosted_vcpus"

    @property
    def budget_unit(self) -> str:
        return "virtual_cpu" if self is self.GITHUB_HOSTED_VCPUS else "physical_core"


def cpu_allocation_policy(environment: Mapping[str, str] | None = None) -> CPUAllocationPolicy:
    """Permit a hosted vCPU budget only for an explicitly selected hosted job.

    This selects the meaning of a process slot, not a CPU count. Affinity and
    kernel quota still bound capacity. Workstations, WSL, macOS and HPC retain
    the physical-core policy unless a separate supported policy is introduced.
    """
    env = os.environ if environment is None else environment
    policy = CPUAllocationPolicy(env.get("COCHEM_CPU_ALLOCATION_POLICY", "physical_cores"))
    if policy is CPUAllocationPolicy.GITHUB_HOSTED_VCPUS and (
        platform.system() != "Linux" or env.get("GITHUB_ACTIONS", "").lower() != "true"
        or env.get("RUNNER_ENVIRONMENT") != "github-hosted"
    ):
        raise ValueError("The github_hosted_vcpus allocation policy requires a GitHub-hosted Linux Actions job")
    return policy


def audited_cpu_capacity(hardware: Mapping[str, Any], execution: Mapping[str, Any] | None = None) -> tuple[int, str]:
    """Interpret an existing registry without converting vCPUs into silicon cores."""
    physical = int(hardware.get("physical_cpu_cores") or hardware.get("cpu_physical_cores") or 0)
    capacity = int(hardware.get("allocatable_compute_cores", physical))
    policy = CPUAllocationPolicy.PHYSICAL_CORES
    allocation = (execution or {}).get("cpu_allocation")
    if allocation is not None:
        policy = CPUAllocationPolicy(allocation["policy"])
        if allocation.get("budget_unit") != policy.budget_unit or allocation.get("allocatable_process_slots") != capacity:
            raise ValueError("Audited CPU allocation units or process slots contradict the hardware registry")
        if policy != cpu_allocation_policy():
            raise ValueError("The active CPU allocation policy differs from the audited registry; rerun Stage 0 for this environment")
    maximum = physical
    if policy is CPUAllocationPolicy.GITHUB_HOSTED_VCPUS:
        maximum = min(int(hardware.get("logical_cpu_cores") or 0), len(hardware.get("audited_cpu_ids") or []))
    if physical < 1 or not 1 <= capacity <= maximum:
        raise ValueError("CPU allocation exceeds the audited capacity for its recorded budget unit")
    return capacity, policy.budget_unit
