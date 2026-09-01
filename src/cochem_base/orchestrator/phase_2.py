#!/usr/bin/env python3
"""CoChem Setup Phase 2: Legacy Hardware Profiler & Resource Gatekeeper Script.

Legacy hardware profiler script referenced in SRS Document 2 Rectification Matrix;
superseded by orchestrator/cochem_setup_phase_2.py for production-grade memory hierarchy auditing,
Linux cgroups v1 & v2 container resource constraints parsing, multi-core CPU topology interrogation,
heterogeneous GPU discovery (NVIDIA, AMD, Intel), IEEE-754 subnormal floating-point precision verification,
and transactional atomic state persistence into the Golden Registry (p2.json).

Maintains full backward compatibility for legacy entrypoint invocations,
direct CLI execution, and re-exports canonical symbols from .cochem_setup_phase_2.
Compliant with Method Matrix v4, SRS Document 2 Part 2, and SRS Document 5.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure parent directory is in sys.path for robust standalone CLI execution
_module_dir = Path(__file__).resolve().parent
_repo_dir = _module_dir.parent
if str(_repo_dir) not in sys.path:
    sys.path.insert(0, str(_repo_dir))
if str(_module_dir) not in sys.path:
    sys.path.insert(0, str(_module_dir))

try:
    from .cochem_setup_phase_2 import (
        CGROUP_V1_UNLIMITED_THRESHOLD,
        CPUAudit,
        DependencyManager,
        GPUDevice,
        GPUProfile,
        IEEE754PrecisionAudit,
        MemoryAudit,
        Phase2AuditError,
        Phase2AuditReport,
        PhaseStatus,
        _find_cgroup_candidate_files,
        audit_cpu,
        audit_gpus,
        audit_memory,
        get_absolute_physical_ram,
        parse_cgroup_cpu_quota,
        parse_cgroup_memory_limit,
        probe_amd_gpus,
        probe_intel_gpus,
        probe_nvidia_gpus,
        resolve_p2_registry_path,
        run_phase_2_audit,
        verify_ieee754_subnormal_precision,
    )
    from .cochem_setup_phase_2 import (
        main as canonical_main,
    )
except ImportError:
    from cochem_setup_phase_2 import (  # type: ignore[no-redef, import-not-found]
        CGROUP_V1_UNLIMITED_THRESHOLD,
        CPUAudit,
        DependencyManager,
        GPUDevice,
        GPUProfile,
        IEEE754PrecisionAudit,
        MemoryAudit,
        Phase2AuditError,
        Phase2AuditReport,
        PhaseStatus,
        _find_cgroup_candidate_files,
        audit_cpu,
        audit_gpus,
        audit_memory,
        get_absolute_physical_ram,
        parse_cgroup_cpu_quota,
        parse_cgroup_memory_limit,
        probe_amd_gpus,
        probe_intel_gpus,
        probe_nvidia_gpus,
        resolve_p2_registry_path,
        run_phase_2_audit,
        verify_ieee754_subnormal_precision,
    )
    from cochem_setup_phase_2 import (  # type: ignore[no-redef, import-not-found]
        main as canonical_main,
    )

# =============================================================================
# LEGACY ALIAS COMPATIBILITY LAYER
# =============================================================================

run_phase_2 = run_phase_2_audit
run_audit = run_phase_2_audit
execute_phase_2 = run_phase_2_audit
execute_audit = run_phase_2_audit
phase_2_audit = run_phase_2_audit
audit_hardware = run_phase_2_audit
audit_mem = audit_memory
audit_cpus = audit_cpu
audit_gpu = audit_gpus
audit_precision = verify_ieee754_subnormal_precision
verify_precision = verify_ieee754_subnormal_precision
resolve_registry_path = resolve_p2_registry_path
get_physical_ram = get_absolute_physical_ram
main = canonical_main
phase_2_main = canonical_main


__all__ = [
    "CGROUP_V1_UNLIMITED_THRESHOLD",
    "CPUAudit",
    "DependencyManager",
    "GPUDevice",
    "GPUProfile",
    "IEEE754PrecisionAudit",
    "MemoryAudit",
    "Phase2AuditError",
    "Phase2AuditReport",
    "PhaseStatus",
    "_find_cgroup_candidate_files",
    "audit_cpu",
    "audit_cpus",
    "audit_gpu",
    "audit_gpus",
    "audit_hardware",
    "audit_mem",
    "audit_memory",
    "audit_precision",
    "execute_audit",
    "execute_phase_2",
    "get_absolute_physical_ram",
    "get_physical_ram",
    "main",
    "parse_cgroup_cpu_quota",
    "parse_cgroup_memory_limit",
    "phase_2_audit",
    "phase_2_main",
    "probe_amd_gpus",
    "probe_intel_gpus",
    "probe_nvidia_gpus",
    "resolve_p2_registry_path",
    "resolve_registry_path",
    "run_audit",
    "run_phase_2",
    "run_phase_2_audit",
    "verify_ieee754_subnormal_precision",
    "verify_precision",
]

if __name__ == "__main__":
    sys.exit(main())
