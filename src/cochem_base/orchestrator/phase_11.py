#!/usr/bin/env python3
"""CoChem Setup Phase 11: Legacy Memory Router & Adaptive Tiering (The OOM Shield Gatekeeper).

Legacy golden registry lock script referenced in SRS Document 2 Rectification Matrix;
superseded by orchestrator/cochem_setup_phase_11.py for bounded host and container memory discovery,
Linux cgroups v1 & v2 memory constraint parsing (/sys/fs/cgroup/memory.max & memory.limit_in_bytes),
HPC job memory limit detection (Slurm, PBS, LSF), flat OS/Jupyter safety buffer allocation (4-8 GB),
active calculation core division scaling (%maxcore), NUMA multi-tier RAM classification, multi-engine
target directive generation (ORCA, PySCF, xTB, Gaussian, CFOUR, MACE-Torch, OpenMPI), environment
variable injection generation, and transactional atomic persistence into the Golden Registry (p11.json).

Maintains full backward compatibility for legacy entrypoint invocations,
direct CLI execution, and re-exports canonical symbols from .cochem_setup_phase_11.
Compliant with Method Matrix v4, SRS Document 2 Part 2 (Section 3.11), SRS Document 5 (Section 4.2),
and CoChem User Manual v4.1.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure parent directory is in sys.path for robust standalone CLI execution
_module_dir = Path(__file__).resolve().parent
_repo_dir = _module_dir.parent
if str(_repo_dir) not in sys.path:
    sys.path.insert(0, str(_repo_dir))
if str(_module_dir) not in sys.path:
    sys.path.insert(0, str(_module_dir))

try:
    from .cochem_setup_phase_11 import (
        CGROUP_V1_UNLIMITED_THRESHOLD,
        DEFAULT_MAX_OS_RESERVE_MB,
        DEFAULT_MIN_OS_RESERVE_MB,
        CGroupLimitError,
        CGroupMemoryProfile,
        CGroupVersion,
        DependencyManager,
        EngineBudgetError,
        EngineMemoryBudget,
        EngineTarget,
        HostMemoryProfile,
        MemoryDiscoveryError,
        MemoryTier,
        MultiTierMemoryProfile,
        NUMABalanceStatus,
        NUMADiscoveryError,
        NumaNodeProfile,
        OOMShieldScalingProfile,
        Phase2AuditFindings,
        Phase11AuditError,
        Phase11AuditReport,
        PhaseStatus,
        _parse_memory_string_to_bytes,
        audit_host_memory,
        build_engine_memory_budgets,
        compute_oom_shield_scaling,
        compute_os_jupyter_reserve,
        detect_hpc_memory_limits,
        discover_numa_topology,
        find_repository_root,
        generate_environment_injection_dict,
        get_absolute_physical_ram,
        load_phase_2_audit_findings,
        parse_cgroup_memory_bounds,
        parse_proc_meminfo,
        resolve_p11_registry_path,
        run_phase_11_audit,
    )
    from .cochem_setup_phase_11 import (
        main as canonical_main,
    )
except ImportError:
    from cochem_setup_phase_11 import (  # type: ignore[no-redef, import-not-found]
        CGROUP_V1_UNLIMITED_THRESHOLD,
        DEFAULT_MAX_OS_RESERVE_MB,
        DEFAULT_MIN_OS_RESERVE_MB,
        CGroupLimitError,
        CGroupMemoryProfile,
        CGroupVersion,
        DependencyManager,
        EngineBudgetError,
        EngineMemoryBudget,
        EngineTarget,
        HostMemoryProfile,
        MemoryDiscoveryError,
        MemoryTier,
        MultiTierMemoryProfile,
        NUMABalanceStatus,
        NUMADiscoveryError,
        NumaNodeProfile,
        OOMShieldScalingProfile,
        Phase2AuditFindings,
        Phase11AuditError,
        Phase11AuditReport,
        PhaseStatus,
        _parse_memory_string_to_bytes,
        audit_host_memory,
        build_engine_memory_budgets,
        compute_oom_shield_scaling,
        compute_os_jupyter_reserve,
        detect_hpc_memory_limits,
        discover_numa_topology,
        find_repository_root,
        generate_environment_injection_dict,
        get_absolute_physical_ram,
        load_phase_2_audit_findings,
        parse_cgroup_memory_bounds,
        parse_proc_meminfo,
        resolve_p11_registry_path,
        run_phase_11_audit,
    )
    from cochem_setup_phase_11 import (  # type: ignore[no-redef, import-not-found]
        main as canonical_main,
    )

# =============================================================================
# LEGACY ALIAS COMPATIBILITY LAYER
# =============================================================================

run_phase_11 = run_phase_11_audit
run_audit = run_phase_11_audit
execute_phase_11 = run_phase_11_audit
execute_audit = run_phase_11_audit
phase_11_audit = run_phase_11_audit
audit_memory = audit_host_memory
audit_mem = audit_host_memory
audit_numa = discover_numa_topology
audit_cgroup = parse_cgroup_memory_bounds
audit_cgroups = parse_cgroup_memory_bounds
compute_reserve = compute_os_jupyter_reserve
compute_scaling = compute_oom_shield_scaling
build_budgets = build_engine_memory_budgets
generate_env_vars = generate_environment_injection_dict
generate_phase_11_env_vars = generate_environment_injection_dict
resolve_registry_path = resolve_p11_registry_path
get_physical_ram = get_absolute_physical_ram
load_p2_findings = load_phase_2_audit_findings
parse_meminfo = parse_proc_meminfo
main = canonical_main
phase_11_main = canonical_main


__all__ = [
    "CGROUP_V1_UNLIMITED_THRESHOLD",
    "CGroupLimitError",
    "CGroupMemoryProfile",
    "CGroupVersion",
    "DEFAULT_MAX_OS_RESERVE_MB",
    "DEFAULT_MIN_OS_RESERVE_MB",
    "DependencyManager",
    "EngineBudgetError",
    "EngineMemoryBudget",
    "EngineTarget",
    "HostMemoryProfile",
    "MemoryDiscoveryError",
    "MemoryTier",
    "MultiTierMemoryProfile",
    "NUMABalanceStatus",
    "NUMADiscoveryError",
    "NumaNodeProfile",
    "OOMShieldScalingProfile",
    "Phase11AuditError",
    "Phase11AuditReport",
    "Phase2AuditFindings",
    "PhaseStatus",
    "_parse_memory_string_to_bytes",
    "audit_cgroup",
    "audit_cgroups",
    "audit_host_memory",
    "audit_mem",
    "audit_memory",
    "audit_numa",
    "build_budgets",
    "build_engine_memory_budgets",
    "compute_oom_shield_scaling",
    "compute_os_jupyter_reserve",
    "compute_reserve",
    "compute_scaling",
    "detect_hpc_memory_limits",
    "discover_numa_topology",
    "execute_audit",
    "execute_phase_11",
    "find_repository_root",
    "generate_env_vars",
    "generate_environment_injection_dict",
    "generate_phase_11_env_vars",
    "get_absolute_physical_ram",
    "get_physical_ram",
    "load_p2_findings",
    "load_phase_2_audit_findings",
    "main",
    "parse_cgroup_memory_bounds",
    "parse_meminfo",
    "parse_proc_meminfo",
    "phase_11_audit",
    "phase_11_main",
    "resolve_p11_registry_path",
    "resolve_registry_path",
    "run_audit",
    "run_phase_11",
    "run_phase_11_audit",
]

if __name__ == "__main__":
    sys.exit(main())
