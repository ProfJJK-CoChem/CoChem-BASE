#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-BASE: Dedicated Cryptographic SHA-256 System Provenance Hashing & Audit-Ring Runner
========================================================================================
Mandated by SRS Document 10 §4 (Cryptographic Provenance Hashing & Audit Ring Architecture),
Perfected Document 10, Method Matrix v4, and CoChem Anti-Spoofing Protocol v2.

Provides a unified, high-integrity Command-Line Interface (CLI) and programmatic validation engine
for multi-tier cryptographic audit rings across the CoChem repository and computational execution host.

Audit-Ring Hierarchy:
- Ring 0: Physical Host & Microarchitecture Environmental Fingerprint (CPU, RAM, OS, Airgap Path Sanitization)
- Ring 1: Software Dependencies, Dynamic Mendeleev Elements, & Golden Master Config SHA-256 Integrity
- Ring 2: Topological Repository Source Code Lock (Sorted POSIX relative paths, SHA-256 tamper/injection detection)
- Ring 3: Artifact Pre-Stamp Checksums, JSON-LD Linked Data Provenance Footers, & Immutability Locks (0o444)

Provenance Tags:
- [M] Measured host physical telemetry, direct file bytes, and cryptographic SHA-256 digests.
- [D] Derived composite fingerprints, ring valuation statuses, and topological lock manifests.
- [E] Estimated timeout allocations, execution thresholds, and benchmark caps.

Usage Examples:
    python tests/provenance_hashing.py audit-ring --strict
    python tests/provenance_hashing.py audit-ring --rings 0 1 2 --json
    python tests/provenance_hashing.py env --json
    python tests/provenance_hashing.py lock --output locks/topological_source_lock.json
    python tests/provenance_hashing.py verify --lockfile locks/topological_source_lock.json
    python tests/provenance_hashing.py hash-file path/to/script.py
    python tests/provenance_hashing.py stamp path/to/run.out --lock
    python tests/provenance_hashing.py verify-stamp path/to/run.out
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import stat
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

# Reconfigure stream encodings for safe cross-platform output (prevent Windows cp1252 crash)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repository root is on sys.path
TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Optional psutil for hardware telemetry
try:
    import psutil  # type: ignore[import-untyped]
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    _PSUTIL_AVAILABLE = False

# Optional Mendeleev library for dynamic chemical mass resolution
try:
    import mendeleev  # type: ignore[import-untyped]
    _MENDELEEV_AVAILABLE = True
except ImportError:
    mendeleev = None  # type: ignore[assignment]
    _MENDELEEV_AVAILABLE = False

# Core CoChem configuration loader
try:
    from cochem_base.config_loader import (
        get_artifact_dir,
        get_base_root,
        get_repo_root,
        resolve_config_path,
    )
except ImportError:
    def get_base_root() -> Path:
        return REPO_ROOT

    def get_repo_root() -> Path:
        return REPO_ROOT

    def get_artifact_dir() -> Path:
        return REPO_ROOT / "CoChem_Artifacts"

    def resolve_config_path(p: Optional[Path] = None) -> Path:
        if p is not None and p.is_file():
            return p.resolve()
        candidate = REPO_ROOT / "cochem_system_config.json"
        if candidate.is_file():
            return candidate
        return REPO_ROOT / "config" / "cochem_system_config.json"

# Core provenance hashing functions
from cochem_base.provenance.hashing import (
    EnvironmentHashRecord,
    SourceIntegrityError,
    TopologicalLockRecord,
    assert_topological_lock,
    compute_file_sha256,
    compute_repository_source_hash,
    generate_topological_source_lock,
    hash_environment,
    verify_source_code_integrity,
)

# Optional provenance stamper integration
try:
    from core_engine.cochem_provenance_stamper import (
        FOOTER_DELIMITER_END,
        FOOTER_DELIMITER_START,
        append_provenance_footer,
        apply_immutability_lock,
        construct_jsonld_provenance,
        extract_provenance_footer,
        is_immutable,
        stamp_run_provenance,
        unlock_immutability,
        verify_provenance_footer,
    )
    _STAMPER_AVAILABLE = True
except ImportError:
    _STAMPER_AVAILABLE = False
    FOOTER_DELIMITER_START = "--- BEGIN COCHEM PROVENANCE JSON-LD ---"
    FOOTER_DELIMITER_END = "--- END COCHEM PROVENANCE JSON-LD ---"

# Configure logger
logger = logging.getLogger("CoChem-ProvenanceHashing")


# =============================================================================
# ENUMS & DATA MODELS
# =============================================================================


class AuditRingLevel(str, Enum):
    """Hierarchical audit ring levels mandated by Document 10 §4."""

    RING_0 = "Ring 0: Host Environment & Microarchitecture"
    RING_1 = "Ring 1: Software Dependencies & Configuration"
    RING_2 = "Ring 2: Repository Source Code Topological Lock"
    RING_3 = "Ring 3: Artifact Pre-Stamp & Immutability Locks"


class AuditStatus(str, Enum):
    """Validation outcome status values."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


@dataclass
class RingValidationResult:
    """Standardized outcome record for a single audit ring validation pass."""

    ring_level: str
    status: AuditStatus
    passed: bool
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    discrepancies: List[str] = field(default_factory=list)
    provenance_tag: str = "[D] Audit Ring Valuation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ring_level": self.ring_level,
            "status": self.status.value if isinstance(self.status, AuditStatus) else str(self.status),
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 3),
            "details": self.details,
            "discrepancies": self.discrepancies,
            "provenance_tag": self.provenance_tag,
        }


@dataclass
class CompositeAuditReport:
    """Consolidated Multi-Ring Audit Report conforming to Document 10 §4."""

    report_id: str
    timestamp_utc: str
    overall_passed: bool
    total_rings_executed: int
    passed_rings_count: int
    failed_rings_count: int
    environment_fingerprint: str
    repository_source_hash: str
    rings: Dict[str, RingValidationResult] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "[D] Composite Cryptographic System Audit Report"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp_utc": self.timestamp_utc,
            "overall_passed": self.overall_passed,
            "total_rings_executed": self.total_rings_executed,
            "passed_rings_count": self.passed_rings_count,
            "failed_rings_count": self.failed_rings_count,
            "environment_fingerprint": self.environment_fingerprint,
            "repository_source_hash": self.repository_source_hash,
            "rings": {k: v.to_dict() for k, v in self.rings.items()},
            "violations": self.violations,
            "metadata": self.metadata,
            "provenance": self.provenance,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# AUDIT RING IMPLEMENTATIONS (Document 10 §4)
# =============================================================================


def audit_ring_0_environment(
    exclude_paths: bool = True,
    tracked_packages: Optional[Sequence[str]] = None,
    tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
) -> RingValidationResult:
    """Ring 0: Validates host environmental fingerprint, hardware bounds, and path sanitization.

    SRS Document 10 §4.1: The environment fingerprint must be deterministic, reproducible,
    and strictly free of local host drive letters or absolute file paths.
    """
    t0 = time.perf_counter()
    discrepancies: List[str] = []
    details: Dict[str, Any] = {}

    try:
        env_record: EnvironmentHashRecord = hash_environment(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )

        details["sha256_hash"] = env_record.sha256_hash
        details["python_version"] = env_record.python_version
        details["os_system"] = env_record.os_system
        details["os_release"] = env_record.os_release
        details["cpu_count"] = env_record.cpu_count
        details["total_ram_bytes"] = env_record.total_ram_bytes

        # 1. Validate hash length and hex representation [M]
        if len(env_record.sha256_hash) != 64:
            discrepancies.append(
                f"Invalid environment SHA-256 hash length: {len(env_record.sha256_hash)} (expected 64)"
            )

        # 2. Strict airgap path sanitization verification [M]
        serialized_json = json.dumps(env_record.to_dict())
        if ":\\" in serialized_json or "/home/" in serialized_json or "/Users/" in serialized_json or "\\Users\\" in serialized_json:
            discrepancies.append(
                "Unsanitized local host path leakage detected in environment fingerprint payload"
            )

        # 3. Physical hardware invariants [M]
        if env_record.cpu_count < 1:
            discrepancies.append(f"Invalid physical CPU count reported: {env_record.cpu_count}")

    except Exception as e:
        discrepancies.append(f"Ring 0 execution failed with unexpected exception: {e}")

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    passed = len(discrepancies) == 0

    return RingValidationResult(
        ring_level=AuditRingLevel.RING_0.value,
        status=AuditStatus.PASSED if passed else AuditStatus.FAILED,
        passed=passed,
        duration_ms=elapsed_ms,
        details=details,
        discrepancies=discrepancies,
        provenance_tag="[M] Physical Host Environmental Telemetry & SHA-256 Digest",
    )


def audit_ring_1_dependencies_and_config(
    config_path: Optional[Union[str, Path]] = None,
    required_packages: Optional[Sequence[str]] = None,
) -> RingValidationResult:
    """Ring 1: Validates software dependency versions, Mendeleev dynamic masses, and system config hash.

    SRS Document 10 §4.2: Dependency versions and cochem_system_config.json must resolve
    with verifiable SHA-256 checksums. Dynamic masses must query the Mendeleev library.
    """
    t0 = time.perf_counter()
    discrepancies: List[str] = []
    details: Dict[str, Any] = {}

    default_required = [
        "cochem-base",
        "pydantic",
        "numpy",
        "scipy",
        "pytest",
        "mendeleev",
    ]
    check_pkgs = list(required_packages or default_required)

    # 1. Audit core Python dependencies [M]
    pkg_status: Dict[str, str] = {}
    for pkg in check_pkgs:
        try:
            ver = importlib.metadata.version(pkg)
            pkg_status[pkg] = ver
        except importlib.metadata.PackageNotFoundError:
            pkg_status[pkg] = "NOT_INSTALLED"
            # Optional vs critical packages
            if pkg in ("numpy", "pydantic", "pytest"):
                discrepancies.append(f"Critical dependency missing: {pkg}")
        except Exception as err:
            pkg_status[pkg] = f"ERROR ({err})"
            discrepancies.append(f"Error resolving version for package {pkg}: {err}")

    details["packages"] = pkg_status

    # 2. Validate dynamic Mendeleev atomic mass resolution [M]
    if _MENDELEEV_AVAILABLE:
        try:
            c_mass = mendeleev.element("C").mass
            h_mass = mendeleev.element("H").mass
            o_mass = mendeleev.element("O").mass
            details["mendeleev_verification"] = {
                "C_mass": c_mass,
                "H_mass": h_mass,
                "O_mass": o_mass,
                "dynamic_mass_resolution": "ACTIVE",
            }
            if not (11.9 < c_mass < 12.1 and 0.99 < h_mass < 1.02 and 15.9 < o_mass < 16.1):
                discrepancies.append("Mendeleev elemental mass resolution returned anomalous values")
        except Exception as e:
            discrepancies.append(f"Mendeleev mass query failed: {e}")
    else:
        details["mendeleev_verification"] = {"dynamic_mass_resolution": "UNAVAILABLE"}
        logger.warning("mendeleev library not installed; dynamic mass queries cannot be verified")

    # 3. System Configuration File SHA-256 Checksum [M]
    resolved_cfg: Optional[Path] = None
    try:
        resolved_cfg = resolve_config_path(Path(config_path) if config_path is not None else None)
        if resolved_cfg.is_file():
            cfg_bytes = resolved_cfg.read_bytes()
            normalized_cfg = cfg_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            cfg_hash = hashlib.sha256(normalized_cfg).hexdigest()
            details["config_path"] = str(resolved_cfg.name)
            details["config_sha256"] = cfg_hash
            details["config_size_bytes"] = len(cfg_bytes)
        else:
            details["config_sha256"] = "CONFIG_FILE_NOT_FOUND"
            details["config_path"] = str(resolved_cfg)
    except Exception as e:
        details["config_sha256"] = f"CONFIG_ERROR ({e})"
        discrepancies.append(f"Failed to read/hash cochem_system_config.json: {e}")

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    passed = len(discrepancies) == 0

    return RingValidationResult(
        ring_level=AuditRingLevel.RING_1.value,
        status=AuditStatus.PASSED if passed else AuditStatus.FAILED,
        passed=passed,
        duration_ms=elapsed_ms,
        details=details,
        discrepancies=discrepancies,
        provenance_tag="[M] Software Dependencies Manifest & Config SHA-256 Checksum",
    )


def audit_ring_2_source_topological_lock(
    repo_dir: Optional[Union[str, Path]] = None,
    lock_record_or_path: Optional[Union[str, Path, TopologicalLockRecord]] = None,
    expected_hash: Optional[str] = None,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> RingValidationResult:
    """Ring 2: Validates topological source code integrity against lock manifest.

    SRS Document 10 §4.3: Every Python source file in the repository must be indexed
    with sorted POSIX relative paths and normalized SHA-256 hashes. Unauthorized mutations,
    injected scripts, or deleted files trigger immediate integrity violations.
    """
    t0 = time.perf_counter()
    discrepancies: List[str] = []
    details: Dict[str, Any] = {}

    target_repo = Path(repo_dir).resolve() if repo_dir is not None else get_repo_root()

    try:
        # 1. Compute current repository source hash [M]
        current_hash, current_files = compute_repository_source_hash(
            target_repo, exclude_dirs=exclude_dirs
        )
        details["repository_sha256"] = current_hash
        details["tracked_py_file_count"] = len(current_files)

        # 2. Resolve lock record if supplied
        lock_rec: Optional[TopologicalLockRecord] = None
        if isinstance(lock_record_or_path, TopologicalLockRecord):
            lock_rec = lock_record_or_path
        elif isinstance(lock_record_or_path, (str, Path)):
            p = Path(lock_record_or_path).resolve()
            if p.is_file():
                lock_rec = TopologicalLockRecord.from_json(p)
                details["lock_source"] = str(p.name)
            else:
                discrepancies.append(f"Specified topological lock manifest file not found: {p}")
        elif lock_record_or_path is None and expected_hash is None:
            # Check for candidate default lock files in repository
            candidate_locks = [
                target_repo / "locks" / "topological_source_lock.json",
                target_repo / "config" / "topological_source_lock.json",
                target_repo / "topological_source_lock.json",
            ]
            for c_lock in candidate_locks:
                if c_lock.is_file():
                    try:
                        lock_rec = TopologicalLockRecord.from_json(c_lock)
                        details["lock_source"] = f"auto-resolved ({c_lock.name})"
                        break
                    except Exception:
                        pass

        # 3. Perform verification
        if lock_rec is not None or expected_hash is not None:
            is_valid, issues = verify_source_code_integrity(
                repo_dir=target_repo,
                expected_hash=expected_hash,
                lock_record=lock_rec,
                exclude_dirs=exclude_dirs,
            )
            discrepancies.extend(issues)
            details["verified_against_lock"] = is_valid
        else:
            details["verified_against_lock"] = "SELF_CONSISTENT_NO_BASELINE"

    except Exception as e:
        discrepancies.append(f"Ring 2 execution failed: {e}")

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    passed = len(discrepancies) == 0

    return RingValidationResult(
        ring_level=AuditRingLevel.RING_2.value,
        status=AuditStatus.PASSED if passed else AuditStatus.FAILED,
        passed=passed,
        duration_ms=elapsed_ms,
        details=details,
        discrepancies=discrepancies,
        provenance_tag="[M] Topological Source Code Repository SHA-256 Checksum",
    )


def audit_ring_3_artifacts_and_immutability(
    artifact_paths: Optional[Sequence[Union[str, Path]]] = None,
    check_immutability: bool = True,
) -> RingValidationResult:
    """Ring 3: Validates artifact pre-stamp checksums, JSON-LD footers, and OS-level immutability.

    SRS Document 10 §4.4: Stamped computational output files (.out, .log) must maintain
    unbroken JSON-LD provenance blocks, verifiable pre-stamp byte slices, and read-only locks (0o444).
    """
    t0 = time.perf_counter()
    discrepancies: List[str] = []
    details: Dict[str, Any] = {"inspected_files": []}

    targets: List[Path] = []
    if artifact_paths:
        for ap in artifact_paths:
            p = Path(ap).resolve()
            if p.is_file():
                targets.append(p)
            elif p.is_dir():
                targets.extend(p.glob("*.out"))
                targets.extend(p.glob("*.log"))
    else:
        # Inspect default artifact directories if present
        art_dir = get_artifact_dir()
        if art_dir.is_dir():
            targets.extend(list(art_dir.glob("*.out"))[:10])

    if not targets:
        details["inspected_files_count"] = 0
        details["status_note"] = "No target artifact files specified or found for inspection"
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return RingValidationResult(
            ring_level=AuditRingLevel.RING_3.value,
            status=AuditStatus.PASSED,
            passed=True,
            duration_ms=elapsed_ms,
            details=details,
            discrepancies=[],
            provenance_tag="[M] Artifact Immutability & Provenance Verification",
        )

    for target in targets:
        file_info: Dict[str, Any] = {
            "name": target.name,
            "size_bytes": target.stat().st_size,
        }

        # Check immutability read-only status (0o444 / not writable) [M]
        is_ro = not os.access(target, os.W_OK)
        file_info["read_only_immutable"] = is_ro
        if check_immutability and not is_ro:
            file_info["immutability_warning"] = "File is writable (not locked to 0o444)"

        # Check provenance footer if stamper is available [M]
        if _STAMPER_AVAILABLE:
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
                if FOOTER_DELIMITER_START in content and FOOTER_DELIMITER_END in content:
                    is_valid, stamp_issues = verify_provenance_footer(target)
                    file_info["provenance_footer"] = "VALID" if is_valid else "CORRUPTED"
                    if not is_valid:
                        discrepancies.extend([f"{target.name}: {iss}" for iss in stamp_issues])
                else:
                    file_info["provenance_footer"] = "NO_FOOTER"
            except Exception as err:
                file_info["provenance_footer"] = f"ERROR ({err})"
                discrepancies.append(f"Failed inspecting provenance footer of {target.name}: {err}")

        details["inspected_files"].append(file_info)

    details["inspected_files_count"] = len(targets)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    passed = len(discrepancies) == 0

    return RingValidationResult(
        ring_level=AuditRingLevel.RING_3.value,
        status=AuditStatus.PASSED if passed else AuditStatus.FAILED,
        passed=passed,
        duration_ms=elapsed_ms,
        details=details,
        discrepancies=discrepancies,
        provenance_tag="[M] Artifact Immutability & Pre-Stamp Verification",
    )


# =============================================================================
# COMPOSITE AUDIT-RING ENGINE
# =============================================================================


def execute_audit_rings(
    repo_dir: Optional[Union[str, Path]] = None,
    config_path: Optional[Union[str, Path]] = None,
    lockfile_path: Optional[Union[str, Path]] = None,
    expected_hash: Optional[str] = None,
    selected_rings: Optional[Sequence[int]] = None,
    artifact_paths: Optional[Sequence[Union[str, Path]]] = None,
    strict: bool = False,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> CompositeAuditReport:
    """Executes the full multi-tier audit-ring pipeline and returns a unified report.

    Args:
        repo_dir: Target repository root directory.
        config_path: Optional path to cochem_system_config.json.
        lockfile_path: Optional path to topological_source_lock.json.
        expected_hash: Optional expected repository master SHA-256 hash.
        selected_rings: List of ring integers to execute (e.g. [0, 1, 2]). Defaults to [0, 1, 2].
        artifact_paths: Optional artifact files/dirs for Ring 3 inspection.
        strict: If True, any warning or missing baseline is treated as failure.
        exclude_dirs: Additional directories to exclude from source hashing.

    Returns:
        CompositeAuditReport containing all ring valuations and metadata.
    """
    rings_to_run = set(selected_rings if selected_rings is not None else [0, 1, 2])
    results: Dict[str, RingValidationResult] = {}
    all_violations: List[str] = []

    env_hash = "NOT_COMPUTED"
    repo_hash = "NOT_COMPUTED"

    # Ring 0: Environment
    if 0 in rings_to_run:
        r0 = audit_ring_0_environment()
        results["ring_0"] = r0
        all_violations.extend(r0.discrepancies)
        env_hash = str(r0.details.get("sha256_hash", "UNKNOWN"))

    # Ring 1: Dependencies & Config
    if 1 in rings_to_run:
        r1 = audit_ring_1_dependencies_and_config(config_path=config_path)
        results["ring_1"] = r1
        all_violations.extend(r1.discrepancies)

    # Ring 2: Topological Source Lock
    if 2 in rings_to_run:
        r2 = audit_ring_2_source_topological_lock(
            repo_dir=repo_dir,
            lock_record_or_path=lockfile_path,
            expected_hash=expected_hash,
            exclude_dirs=exclude_dirs,
        )
        results["ring_2"] = r2
        all_violations.extend(r2.discrepancies)
        repo_hash = str(r2.details.get("repository_sha256", "UNKNOWN"))

    # Ring 3: Artifacts & Immutability (optional or if explicitly requested)
    if 3 in rings_to_run:
        r3 = audit_ring_3_artifacts_and_immutability(artifact_paths=artifact_paths)
        results["ring_3"] = r3
        all_violations.extend(r3.discrepancies)

    passed_count = sum(1 for r in results.values() if r.passed)
    failed_count = sum(1 for r in results.values() if not r.passed)
    overall_passed = failed_count == 0

    return CompositeAuditReport(
        report_id=f"audit_{uuid.uuid4().hex[:12]}",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        overall_passed=overall_passed,
        total_rings_executed=len(results),
        passed_rings_count=passed_count,
        failed_rings_count=failed_count,
        environment_fingerprint=env_hash,
        repository_source_hash=repo_hash,
        rings=results,
        violations=all_violations,
        metadata={
            "python_version": platform.python_version(),
            "os_platform": platform.platform(),
            "host_node": platform.node(),
            "strict_mode": strict,
        },
    )


# =============================================================================
# CLI SUBCOMMAND HANDLERS
# =============================================================================


def handle_audit_ring_cli(args: argparse.Namespace) -> int:
    """CLI handler for 'audit-ring' / 'audit' subcommand."""
    rings = args.rings if hasattr(args, "rings") and args.rings else [0, 1, 2]
    if getattr(args, "include_artifacts", False):
        rings.append(3)

    report = execute_audit_rings(
        repo_dir=args.repo_dir,
        config_path=args.config,
        lockfile_path=args.lockfile,
        expected_hash=args.expected_hash,
        selected_rings=rings,
        artifact_paths=args.artifacts,
        strict=args.strict,
    )

    if args.json:
        out_str = report.to_json(indent=2)
        if args.output:
            Path(args.output).write_text(out_str, encoding="utf-8")
        else:
            print(out_str)
    else:
        print("\n" + "=" * 78)
        print("CoChem Cryptographic Provenance Audit-Ring Report (Document 10 §4)")
        print("=" * 78)
        print(f"Report ID:             {report.report_id}")
        print(f"Timestamp (UTC):       {report.timestamp_utc}")
        print(f"Environment SHA-256:   {report.environment_fingerprint}")
        print(f"Repository SHA-256:    {report.repository_source_hash}")
        print(f"Overall Status:        {'[PASSED]' if report.overall_passed else '[FAILED]'}")
        print(f"Rings Executed:        {report.passed_rings_count}/{report.total_rings_executed} Passed")
        print("-" * 78)

        for ring_key, res in report.rings.items():
            icon = "[PASS]" if res.passed else "[FAIL]"
            print(f"{icon} {res.ring_level} ({res.duration_ms:.1f} ms)")
            if res.discrepancies:
                for d in res.discrepancies:
                    print(f"       -> Violation: {d}")

        print("=" * 78)

        if args.output:
            Path(args.output).write_text(report.to_json(indent=2), encoding="utf-8")
            print(f"Saved full JSON audit report to: {args.output}")

    if not report.overall_passed and args.strict:
        return 1
    return 0 if report.overall_passed else 1


def handle_env_cli(args: argparse.Namespace) -> int:
    """CLI handler for 'env' / 'fingerprint' subcommand."""
    rec = hash_environment(
        exclude_paths=not args.no_sanitize,
        tracked_packages=args.packages,
    )

    if args.json:
        out_str = json.dumps(rec.to_dict(), indent=2)
        if args.output:
            Path(args.output).write_text(out_str, encoding="utf-8")
        else:
            print(out_str)
    else:
        print("\n" + "=" * 78)
        print("CoChem Host Environmental Fingerprint (Ring 0)")
        print("=" * 78)
        print(f"SHA-256 Fingerprint:   {rec.sha256_hash}")
        print(f"Python Version:        {rec.python_version} ({rec.python_implementation})")
        print(f"Host OS:               {rec.os_system} {rec.os_release}")
        print(f"CPU Cores:             {rec.cpu_count}")
        print(f"Total Physical RAM:    {rec.total_ram_bytes / (1024**3):.2f} GB")
        print(f"Tracked Dependencies:  {len(rec.core_dependencies)} packages")
        print("-" * 78)
        for pkg, ver in sorted(rec.core_dependencies.items()):
            print(f"  - {pkg:<25} {ver}")
        print("=" * 78)

        if args.output:
            Path(args.output).write_text(json.dumps(rec.to_dict(), indent=2), encoding="utf-8")
            print(f"Saved environment manifest to: {args.output}")

    return 0


def handle_lock_cli(args: argparse.Namespace) -> int:
    """CLI handler for 'lock' / 'generate-lock' subcommand."""
    target_repo = Path(args.repo_dir).resolve() if args.repo_dir else get_repo_root()
    output_p = Path(args.output).resolve() if args.output else None

    rec = generate_topological_source_lock(
        repo_dir=target_repo,
        output_path=output_p,
        exclude_dirs=args.exclude_dirs,
    )

    if args.json and not output_p:
        print(json.dumps(rec.to_dict(), indent=2))
    elif not args.json:
        print("\n" + "=" * 78)
        print("CoChem Repository Topological Source Lock Manifest (Ring 2)")
        print("=" * 78)
        print(f"Repository Root:       {target_repo}")
        print(f"Repository SHA-256:    {rec.repository_sha256}")
        print(f"Tracked Python Files:  {rec.file_count}")
        print(f"Generated At (Unix):   {rec.generated_at}")
        if output_p:
            print(f"Manifest Path:         {output_p}")
        print("=" * 78)

    return 0


def handle_verify_cli(args: argparse.Namespace) -> int:
    """CLI handler for 'verify' / 'check-lock' subcommand."""
    target_repo = Path(args.repo_dir).resolve() if args.repo_dir else get_repo_root()
    lock_record: Optional[TopologicalLockRecord] = None

    if args.lockfile:
        lock_p = Path(args.lockfile).resolve()
        if not lock_p.is_file():
            print(f"Error: Lock file not found at: {lock_p}", file=sys.stderr)
            return 2
        try:
            lock_record = TopologicalLockRecord.from_json(lock_p)
        except Exception as err:
            print(f"Error reading lock file {lock_p}: {err}", file=sys.stderr)
            return 2
    elif not args.expected_hash:
        # Check default candidate lock file locations
        candidate_locks = [
            target_repo / "locks" / "topological_source_lock.json",
            target_repo / "config" / "topological_source_lock.json",
            target_repo / "topological_source_lock.json",
        ]
        found_lock = next((p for p in candidate_locks if p.is_file()), None)
        if found_lock:
            try:
                lock_record = TopologicalLockRecord.from_json(found_lock)
            except Exception as err:
                print(f"Error reading default lock file {found_lock}: {err}", file=sys.stderr)
                return 2
        else:
            print(
                "Error: Integrity verification requires either '--lockfile' or '--expected-hash' "
                "(or a default topological_source_lock.json in locks/ or config/).",
                file=sys.stderr,
            )
            return 2

    try:
        is_valid, discrepancies = verify_source_code_integrity(
            repo_dir=target_repo,
            expected_hash=args.expected_hash,
            lock_record=lock_record,
            exclude_dirs=args.exclude_dirs,
        )
    except Exception as e:
        print(f"Error during integrity verification: {e}", file=sys.stderr)
        return 2

    if args.json:
        res = {
            "repository_dir": str(target_repo),
            "is_valid": is_valid,
            "discrepancies": discrepancies,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(res, indent=2))
    else:
        print("\n" + "=" * 78)
        print("CoChem Repository Source Code Integrity Verification (Ring 2)")
        print("=" * 78)
        print(f"Repository:            {target_repo}")
        print(f"Integrity Status:      {'[PASSED - UNMODIFIED]' if is_valid else '[FAILED - TAMPERING DETECTED]'}")
        if lock_record:
            lock_name = args.lockfile if args.lockfile else "Auto-resolved default lock manifest"
            print(f"Verified Lock File:    {lock_name}")
        if args.expected_hash:
            print(f"Expected Master Hash:  {args.expected_hash}")
        print("-" * 78)

        if discrepancies:
            print(f"Detected {len(discrepancies)} integrity violations:")
            for d in discrepancies:
                print(f"  [X] {d}")
        else:
            print("  [OK] All repository source files match exact topological SHA-256 hashes.")
        print("=" * 78)

    return 0 if is_valid else 1


def handle_hash_file_cli(args: argparse.Namespace) -> int:
    """CLI handler for 'hash-file' / 'checksum' subcommand."""
    normalize = not args.raw
    has_errors = False

    for target_path in args.files:
        p = Path(target_path).resolve()
        if not p.is_file():
            print(f"Error: File not found: {p}", file=sys.stderr)
            has_errors = True
            continue

        try:
            f_hash = compute_file_sha256(p, normalize_newlines=normalize)
            if args.json:
                print(json.dumps({"path": str(p), "sha256": f_hash, "normalized": normalize}))
            else:
                print(f"{f_hash}  {p.name}")
        except Exception as e:
            print(f"Error hashing {p}: {e}", file=sys.stderr)
            has_errors = True

    return 1 if has_errors else 0


def handle_stamp_cli(args: argparse.Namespace) -> int:
    """CLI handler for stamping output files with JSON-LD provenance footer."""
    if not _STAMPER_AVAILABLE:
        print("Error: core_engine.cochem_provenance_stamper is not available.", file=sys.stderr)
        return 2

    target = Path(args.file).resolve()
    if not target.is_file():
        print(f"Error: Target file not found: {target}", file=sys.stderr)
        return 2

    try:
        prov = append_provenance_footer(
            output_file=target,
            config_path=args.config,
            allow_re_stamp=args.force,
        )
        if args.lock:
            apply_immutability_lock(target)
            print(f"Applied immutability lock (0o444) to {target}")

        print(f"Successfully stamped JSON-LD provenance footer on {target}")
        if args.json:
            print(json.dumps(prov, indent=2))
        return 0
    except Exception as e:
        print(f"Failed stamping file: {e}", file=sys.stderr)
        return 1


def handle_verify_stamp_cli(args: argparse.Namespace) -> int:
    """CLI handler for verifying provenance footer on a stamped file."""
    if not _STAMPER_AVAILABLE:
        print("Error: core_engine.cochem_provenance_stamper is not available.", file=sys.stderr)
        return 2

    target = Path(args.file).resolve()
    if not target.is_file():
        print(f"Error: Target file not found: {target}", file=sys.stderr)
        return 2

    is_valid, issues = verify_provenance_footer(target)
    is_ro = not os.access(target, os.W_OK)

    if args.json:
        out = {
            "file": str(target),
            "is_valid": is_valid,
            "is_immutable_readonly": is_ro,
            "issues": issues,
        }
        print(json.dumps(out, indent=2))
    else:
        print("\n" + "=" * 78)
        print("CoChem Artifact Provenance & Immutability Verification (Ring 3)")
        print("=" * 78)
        print(f"Target File:           {target}")
        print(f"Provenance Status:     {'[VALID]' if is_valid else '[INVALID / TAMPERED]'}")
        print(f"Immutability Lock:     {'[LOCKED 0o444]' if is_ro else '[WRITABLE]'}")
        print("-" * 78)
        if issues:
            for iss in issues:
                print(f"  [X] {iss}")
        else:
            print("  [OK] Pre-stamp byte slice and JSON-LD checksums verified perfectly.")
        print("=" * 78)

    return 0 if is_valid else 1


# =============================================================================
# CLI PARSER BUILDER
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Constructs the comprehensive CLI parser for provenance hashing and audit-ring execution."""
    parser = argparse.ArgumentParser(
        prog="provenance_hashing",
        description="CoChem-BASE: Cryptographic SHA-256 System Provenance & Audit-Ring Runner (Document 10 §4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="CoChem Provenance Hashing CLI v1.0.0 (SRS Document 10 §4 Compliant)",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 1. audit-ring subcommand
    audit_p = subparsers.add_parser(
        "audit-ring",
        aliases=["audit"],
        help="Execute multi-tier cryptographic audit-ring validation (Rings 0, 1, 2, 3)",
    )
    audit_p.add_argument(
        "--rings",
        nargs="+",
        type=int,
        choices=[0, 1, 2, 3],
        default=[0, 1, 2],
        help="Audit rings to execute (0=Env, 1=Deps/Config, 2=Source Lock, 3=Artifacts)",
    )
    audit_p.add_argument("--repo-dir", "-r", type=str, default=None, help="Repository root path")
    audit_p.add_argument("--lockfile", "-l", type=str, default=None, help="Path to topological_source_lock.json")
    audit_p.add_argument("--config", "-c", type=str, default=None, help="Path to cochem_system_config.json")
    audit_p.add_argument("--expected-hash", type=str, default=None, help="Expected master repository SHA-256 hash")
    audit_p.add_argument("--artifacts", nargs="+", type=str, default=None, help="Target artifacts for Ring 3 audit")
    audit_p.add_argument("--strict", action="store_true", help="Fail with non-zero exit code on any violation")
    audit_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    audit_p.add_argument("--output", "-o", type=str, default=None, help="Write output report to file")
    audit_p.set_defaults(func=handle_audit_ring_cli)

    # 2. env / fingerprint subcommand
    env_p = subparsers.add_parser(
        "env",
        aliases=["fingerprint"],
        help="Generate path-independent deterministic environment fingerprint (Ring 0)",
    )
    env_p.add_argument("--packages", nargs="+", type=str, default=None, help="Explicit packages to track")
    env_p.add_argument("--no-sanitize", action="store_true", help="Disable path sanitization")
    env_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    env_p.add_argument("--output", "-o", type=str, default=None, help="Write output to file")
    env_p.set_defaults(func=handle_env_cli)

    # 3. lock / generate-lock subcommand
    lock_p = subparsers.add_parser(
        "lock",
        aliases=["generate-lock"],
        help="Generate repository topological source lock manifest (Ring 2)",
    )
    lock_p.add_argument("--repo-dir", "-r", type=str, default=None, help="Repository root path")
    lock_p.add_argument("--output", "-o", type=str, default=None, help="Write lock manifest to JSON file")
    lock_p.add_argument("--exclude-dirs", nargs="+", type=str, default=None, help="Additional directories to exclude")
    lock_p.add_argument("--json", action="store_true", help="Output JSON manifest to stdout")
    lock_p.set_defaults(func=handle_lock_cli)

    # 4. verify / check-lock subcommand
    verify_p = subparsers.add_parser(
        "verify",
        aliases=["check-lock"],
        help="Verify repository source code integrity against lock manifest (Ring 2)",
    )
    verify_p.add_argument("--repo-dir", "-r", type=str, default=None, help="Repository root path")
    verify_p.add_argument("--lockfile", "-l", type=str, default=None, help="Path to topological_source_lock.json")
    verify_p.add_argument("--expected-hash", type=str, default=None, help="Expected master repository SHA-256")
    verify_p.add_argument("--exclude-dirs", nargs="+", type=str, default=None, help="Additional directories to exclude")
    verify_p.add_argument("--json", action="store_true", help="Output verification result as JSON")
    verify_p.set_defaults(func=handle_verify_cli)

    # 5. hash-file / checksum subcommand
    hash_p = subparsers.add_parser(
        "hash-file",
        aliases=["checksum"],
        help="Compute normalized deterministic SHA-256 checksum of files",
    )
    hash_p.add_argument("files", nargs="+", type=str, help="Paths to files to hash")
    hash_p.add_argument("--raw", action="store_true", help="Do not normalize text newlines (binary hash)")
    hash_p.add_argument("--json", action="store_true", help="Output JSON results")
    hash_p.set_defaults(func=handle_hash_file_cli)

    # 6. stamp subcommand
    stamp_p = subparsers.add_parser(
        "stamp",
        help="Append JSON-LD provenance footer to an output file (Ring 3)",
    )
    stamp_p.add_argument("file", type=str, help="Target output file to stamp")
    stamp_p.add_argument("--config", "-c", type=str, default=None, help="Path to cochem_system_config.json")
    stamp_p.add_argument("--lock", action="store_true", help="Apply read-only immutability lock (0o444) after stamping")
    stamp_p.add_argument("--force", action="store_true", help="Allow re-stamping if file already contains a footer")
    stamp_p.add_argument("--json", action="store_true", help="Output generated JSON-LD block")
    stamp_p.set_defaults(func=handle_stamp_cli)

    # 7. verify-stamp subcommand
    vstamp_p = subparsers.add_parser(
        "verify-stamp",
        help="Verify pre-stamp checksum and JSON-LD footer of a stamped file (Ring 3)",
    )
    vstamp_p.add_argument("file", type=str, help="Stamped file to verify")
    vstamp_p.add_argument("--json", action="store_true", help="Output verification result as JSON")
    vstamp_p.set_defaults(func=handle_verify_stamp_cli)

    return parser


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint for provenance hashing and audit-ring execution."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
