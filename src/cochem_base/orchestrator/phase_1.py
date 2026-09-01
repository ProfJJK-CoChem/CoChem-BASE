#!/usr/bin/env python3
"""CoChem Setup Phase 1: Legacy Environment Gatekeeper & Host OS Audit Script.

Legacy OS audit script referenced in SRS Document 2 Rectification Matrix;
superseded by orchestrator/cochem_setup_phase_1.py for host OS validation,
WSL2 9P mount trap detection, virtual memory/stack limits probing, and toolchain interrogation.
Maintains full backward compatibility for legacy entrypoint invocations,
direct CLI execution, and re-exports canonical symbols from .cochem_setup_phase_1.
Compliant with Method Matrix v4, SRS Document 2 Part 2, and SRS Document 5.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure parent directory is in sys.path for robust standalone CLI execution
_module_dir = Path(__file__).resolve().parent
_repo_dir = _module_dir.parent
if str(_repo_dir) not in sys.path:
    sys.path.insert(0, str(_repo_dir))
if str(_module_dir) not in sys.path:
    sys.path.insert(0, str(_module_dir))

try:
    from .cochem_setup_phase_1 import (
        DependencyManager,
        FilesystemAudit,
        KernelLimitsAudit,
        OSProfile,
        Phase1AuditError,
        Phase1AuditReport,
        PhaseStatus,
        ToolchainItem,
        WSL9PMountError,
        audit_filesystem,
        audit_kernel_limits,
        audit_toolchain_binary,
        audit_toolchains,
        check_wsl_9p_mount,
        interrogate_os,
        is_wsl_environment,
        parse_mount_table_entry,
        resolve_p1_registry_path,
        run_phase_1_audit,
    )
    from .cochem_setup_phase_1 import (
        main as canonical_main,
    )
except ImportError:
    from cochem_setup_phase_1 import (  # type: ignore[no-redef, import-not-found]
        DependencyManager,
        FilesystemAudit,
        KernelLimitsAudit,
        OSProfile,
        Phase1AuditError,
        Phase1AuditReport,
        PhaseStatus,
        ToolchainItem,
        WSL9PMountError,
        audit_filesystem,
        audit_kernel_limits,
        audit_toolchain_binary,
        audit_toolchains,
        check_wsl_9p_mount,
        interrogate_os,
        is_wsl_environment,
        parse_mount_table_entry,
        resolve_p1_registry_path,
        run_phase_1_audit,
    )
    from cochem_setup_phase_1 import (  # type: ignore[no-redef, import-not-found]
        main as canonical_main,
    )

# =============================================================================
# LEGACY ALIAS COMPATIBILITY LAYER
# =============================================================================

run_phase_1 = run_phase_1_audit
run_audit = run_phase_1_audit
execute_phase_1 = run_phase_1_audit
execute_audit = run_phase_1_audit
phase_1_audit = run_phase_1_audit
audit_os = interrogate_os
audit_fs = audit_filesystem
audit_tools = audit_toolchains
audit_kernel = audit_kernel_limits
main = canonical_main
phase_1_main = canonical_main


__all__ = [
    "DependencyManager",
    "FilesystemAudit",
    "KernelLimitsAudit",
    "OSProfile",
    "Phase1AuditError",
    "Phase1AuditReport",
    "PhaseStatus",
    "ToolchainItem",
    "WSL9PMountError",
    "audit_filesystem",
    "audit_fs",
    "audit_kernel",
    "audit_kernel_limits",
    "audit_os",
    "audit_toolchain_binary",
    "audit_toolchains",
    "audit_tools",
    "check_wsl_9p_mount",
    "execute_audit",
    "execute_phase_1",
    "interrogate_os",
    "is_wsl_environment",
    "main",
    "parse_mount_table_entry",
    "phase_1_audit",
    "phase_1_main",
    "resolve_p1_registry_path",
    "run_audit",
    "run_phase_1",
    "run_phase_1_audit",
]

if __name__ == "__main__":
    sys.exit(main())
