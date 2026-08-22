"""
CoChem Orchestrator Package.
Provides multi-phase environment gatekeeping, initialization, and deployment pipeline.
"""

from __future__ import annotations

from orchestrator.cochem_setup_phase_1 import (
    DependencyManager,
    FilesystemAudit,
    KernelLimitsAudit,
    OSProfile,
    Phase1AuditReport,
    PhaseStatus,
    ToolchainItem,
    WSL9PMountError,
    audit_filesystem,
    audit_kernel_limits,
    audit_toolchains,
    interrogate_os,
    run_phase_1_audit,
)
from orchestrator.cochem_setup_phase_1 import (
    main as phase_1_main,
)
from orchestrator.cochem_setup_phase_2 import (
    CPUAudit,
    GPUDevice,
    GPUProfile,
    IEEE754PrecisionAudit,
    MemoryAudit,
    Phase2AuditError,
    Phase2AuditReport,
    audit_cpu,
    audit_gpus,
    audit_memory,
    parse_cgroup_cpu_quota,
    parse_cgroup_memory_limit,
    probe_amd_gpus,
    probe_intel_gpus,
    probe_nvidia_gpus,
    resolve_p2_registry_path,
    run_phase_2_audit,
    verify_ieee754_subnormal_precision,
)
from orchestrator.cochem_setup_phase_2 import (
    main as phase_2_main,
)

__all__ = [
    "CPUAudit",
    "DependencyManager",
    "FilesystemAudit",
    "GPUDevice",
    "GPUProfile",
    "IEEE754PrecisionAudit",
    "KernelLimitsAudit",
    "MemoryAudit",
    "OSProfile",
    "Phase1AuditReport",
    "Phase2AuditError",
    "Phase2AuditReport",
    "PhaseStatus",
    "ToolchainItem",
    "WSL9PMountError",
    "audit_cpu",
    "audit_filesystem",
    "audit_gpus",
    "audit_kernel_limits",
    "audit_memory",
    "audit_toolchains",
    "interrogate_os",
    "parse_cgroup_cpu_quota",
    "parse_cgroup_memory_limit",
    "phase_1_main",
    "phase_2_main",
    "probe_amd_gpus",
    "probe_intel_gpus",
    "probe_nvidia_gpus",
    "resolve_p2_registry_path",
    "run_phase_1_audit",
    "run_phase_2_audit",
    "verify_ieee754_subnormal_precision",
]

