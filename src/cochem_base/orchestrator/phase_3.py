#!/usr/bin/env python3
"""CoChem Setup Phase 3: Legacy Multi-Track Quantum Engine Discovery & Integrity Hashing.

Legacy quantum discovery script referenced in SRS Document 2 Rectification Matrix;
superseded by orchestrator/cochem_setup_phase_3.py for multi-track quantum chemistry and semi-empirical
binary discovery (ORCA, CFOUR, xTB, CREST, PySCF/GPU), cryptographic streaming SHA-256 hashing,
subprocess version interrogation, container SIF air-gap validation, deterministic path-independent
environment fingerprinting, and transactional atomic state persistence into the Golden Registry (p3.json).

Maintains full backward compatibility for legacy entrypoint invocations,
direct CLI execution, and re-exports canonical symbols from .cochem_setup_phase_3.
Compliant with Method Matrix v4, SRS Document 2 Part 2 (Section 3.3), SRS Document 5 (Section 2.3),
and SRS Document 10.
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
    from .cochem_setup_phase_3 import (
        STANDARD_MONITORED_ENGINES,
        BinaryEngineItem,
        ContainerAudit,
        DependencyManager,
        EngineStatus,
        EngineTrack,
        EngineTrackSummary,
        EnvironmentFingerprint,
        Phase3AuditError,
        Phase3AuditReport,
        PhaseStatus,
        audit_all_engines,
        audit_container_sifs,
        audit_single_binary,
        build_track_summaries,
        compute_environment_fingerprint,
        compute_file_sha256,
        discover_binary_path,
        extract_semantic_version,
        interrogate_binary_version,
        resolve_binary_search_paths,
        resolve_p3_registry_path,
        run_phase_3_audit,
    )
    from .cochem_setup_phase_3 import (
        main as canonical_main,
    )
except ImportError:
    from cochem_setup_phase_3 import (  # type: ignore[no-redef, import-not-found]
        STANDARD_MONITORED_ENGINES,
        BinaryEngineItem,
        ContainerAudit,
        DependencyManager,
        EngineStatus,
        EngineTrack,
        EngineTrackSummary,
        EnvironmentFingerprint,
        Phase3AuditError,
        Phase3AuditReport,
        PhaseStatus,
        audit_all_engines,
        audit_container_sifs,
        audit_single_binary,
        build_track_summaries,
        compute_environment_fingerprint,
        compute_file_sha256,
        discover_binary_path,
        extract_semantic_version,
        interrogate_binary_version,
        resolve_binary_search_paths,
        resolve_p3_registry_path,
        run_phase_3_audit,
    )
    from cochem_setup_phase_3 import (  # type: ignore[no-redef, import-not-found]
        main as canonical_main,
    )

# =============================================================================
# LEGACY ALIAS COMPATIBILITY LAYER
# =============================================================================

run_phase_3 = run_phase_3_audit
run_audit = run_phase_3_audit
execute_phase_3 = run_phase_3_audit
execute_audit = run_phase_3_audit
phase_3_audit = run_phase_3_audit

audit_engines = audit_all_engines
audit_engine = audit_single_binary
audit_binary = audit_single_binary
audit_containers = audit_container_sifs
audit_sifs = audit_container_sifs
audit_sif = audit_container_sifs

compute_fingerprint = compute_environment_fingerprint
compute_sha256 = compute_file_sha256
hash_file = compute_file_sha256
discover_binary = discover_binary_path
interrogate_version = interrogate_binary_version
extract_version = extract_semantic_version
resolve_registry_path = resolve_p3_registry_path

main = canonical_main
phase_3_main = canonical_main


__all__ = [
    "BinaryEngineItem",
    "ContainerAudit",
    "DependencyManager",
    "EngineStatus",
    "EngineTrack",
    "EngineTrackSummary",
    "EnvironmentFingerprint",
    "Phase3AuditError",
    "Phase3AuditReport",
    "PhaseStatus",
    "STANDARD_MONITORED_ENGINES",
    "audit_all_engines",
    "audit_binary",
    "audit_container_sifs",
    "audit_containers",
    "audit_engine",
    "audit_engines",
    "audit_sif",
    "audit_sifs",
    "audit_single_binary",
    "build_track_summaries",
    "compute_environment_fingerprint",
    "compute_file_sha256",
    "compute_fingerprint",
    "compute_sha256",
    "discover_binary",
    "discover_binary_path",
    "execute_audit",
    "execute_phase_3",
    "extract_semantic_version",
    "extract_version",
    "hash_file",
    "interrogate_binary_version",
    "interrogate_version",
    "main",
    "phase_3_audit",
    "phase_3_main",
    "resolve_binary_search_paths",
    "resolve_p3_registry_path",
    "resolve_registry_path",
    "run_audit",
    "run_phase_3",
    "run_phase_3_audit",
]

if __name__ == "__main__":
    sys.exit(main())
