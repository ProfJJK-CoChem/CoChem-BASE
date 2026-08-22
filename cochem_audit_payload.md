Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part2_05d_orchestrator_phase_8_prompt.md.
Original prompt:
﻿# CoChem-BASE Coding Prompt: cochem_setup_phase_8.py

## 1. Goal
Implement the file `cochem_setup_phase_8.py` based on the Software Requirements Specification (SRS) - CoChem-BASE (Document 2 Part 2).

## 2. Target Filepath
`D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_8.py`

## 3. Context & Ecosystem Role
Network Port Allocation

## 4. Deliverable Functions
Handles Network Port Allocation & Dynamic Gateway Binding (e.g. TCP 5555 / 8000).

## 5. Strict Constraints & Anti-Spoofing
- **Workspace Rules:** Strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.
- **No Mocks or Stubs:** Do NOT use placeholders, mock data, or stub logic (e.g., `pass`, `NotImplementedError`, or fake hardcoded values).
- **Fully Functional:** The code must be production-ready and fully implement the deliverables.
- **Error Handling:** Must degrade gracefully and handle errors according to the SRS without crashing silently.
- **Autonomy:** Do not delegate to the user. Execute the complete implementation.
- **Verification:** Ensure your code runs in the physical constraints as defined.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\__init__.py ---
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
from orchestrator.cochem_setup_phase_3 import (
    BinaryEngineItem,
    ContainerAudit,
    EngineStatus,
    EngineTrack,
    EngineTrackSummary,
    EnvironmentFingerprint,
    Phase3AuditError,
    Phase3AuditReport,
    audit_all_engines,
    audit_container_sifs,
    audit_single_binary,
    build_track_summaries,
    compute_environment_fingerprint,
    resolve_p3_registry_path,
    run_phase_3_audit,
)
from orchestrator.cochem_setup_phase_3 import (
    main as phase_3_main,
)
from orchestrator.cochem_setup_phase_4 import (
    DynamicVersionWalkingResult,
    DynamicVersionWalkStep,
    IPCSecurityAudit,
    ManifestFilterAudit,
    MendeleevMassRecord,
    Phase4AuditError,
    Phase4AuditReport,
    SiloAuditItem,
    SiloConfig,
    SiloProvisioningError,
    SiloStatus,
    SiloType,
    VersionWalkingError,
    audit_ipc_and_mps_security,
    audit_micro_silos,
    enforce_python_version,
    execute_dynamic_version_walking,
    filter_silos_by_manifest,
    get_default_silo_configs,
    get_native_memory_env_vars,
    get_native_stack_flags,
    get_silo_executable_path,
    inject_silo_stack_and_env_flags,
    load_deployment_manifest,
    provision_micro_silo,
    resolve_p4_registry_path,
    resolve_silo_base_directory,
    run_phase_4_audit,
    scan_local_fallback_binaries,
    verify_mendeleev_authority,
)
from orchestrator.cochem_setup_phase_4 import (
    main as phase_4_main,
)
from orchestrator.cochem_setup_phase_5 import (
    GPUDeviceVRAM,
    MPSControlError,
    MPSDaemonAudit,
    MPSStatus,
    Phase5AuditError,
    Phase5AuditReport,
    VRAMAllocationError,
    VRAMBudgetReport,
    build_pinned_memory_limit_string,
    calculate_vram_budget,
    configure_mps_device_limit,
    discover_mps_binaries,
    enforce_socket_directory_permissions,
    generate_mps_activation_scripts,
    get_current_username,
    inject_mps_environment_variables,
    probe_gpu_devices_vram,
    probe_mps_daemon_status,
    resolve_mps_log_directory,
    resolve_mps_pipe_directory,
    resolve_p5_registry_path,
    run_phase_5_audit,
    start_mps_daemon,
    stop_mps_daemon,
)
from orchestrator.cochem_setup_phase_5 import (
    main as phase_5_main,
)
from orchestrator.cochem_setup_phase_6 import (
    ArchiveSchemaAudit,
    DatabaseBackend,
    DatabaseProvisioningError,
    DiskQuotaError,
    HDF5FilterProfile,
    LockingVerificationError,
    Phase6AuditError,
    Phase6AuditReport,
    StorageMode,
    StoragePathProfile,
    SWMRRuntimeAudit,
    enforce_storage_permissions,
    probe_swmr_locking_capabilities,
    provision_archive_pes_db,
    provision_runtime_active_db,
    resolve_databases_directory,
    resolve_p6_registry_path,
    resolve_scratch_directory,
    run_phase_6_audit,
    verify_disk_quota,
)
from orchestrator.cochem_setup_phase_6 import (
    main as phase_6_main,
)
from orchestrator.cochem_setup_phase_7 import (
    HPCMemoryParseError,
    HPCMemoryProfile,
    HPCSchedulerType,
    HPCScratchAllocationError,
    HPCScratchProfile,
    HPCThreadAffinityProfile,
    HPCTopologyError,
    HPCTopologyProfile,
    Phase7AuditError,
    Phase7AuditReport,
    compute_thread_affinity_profile,
    detect_hpc_scheduler,
    generate_environment_injection_dict as generate_phase_7_env_vars,
    parse_hpc_memory_limit,
    parse_slurm_nodelist,
    parse_slurm_tasks_per_node,
    resolve_hpc_scratch_directory,
    resolve_p7_registry_path,
    run_phase_7_audit,
)
from orchestrator.cochem_setup_phase_7 import (
    main as phase_7_main,
)
from orchestrator.cochem_setup_phase_8 import (
    BindPolicy,
    GatewayConfigProfile,
    GatewayServiceType,
    Phase8AuditError,
    Phase8AuditReport,
    PortAllocationError,
    PortBindingProfile,
    PortRangeExhaustedError,
    ProtocolType,
    SocketBindingError,
    allocate_all_gateway_services,
    allocate_port,
    generate_environment_injection_dict as generate_phase_8_env_vars,
    probe_port_availability,
    resolve_p8_registry_path,
    run_phase_8_audit,
)
from orchestrator.cochem_setup_phase_8 import (
    main as phase_8_main,
)

__all__ = [
    "ArchiveSchemaAudit",
    "BinaryEngineItem",
    "CPUAudit",
    "ContainerAudit",
    "DatabaseBackend",
    "DatabaseProvisioningError",
    "DependencyManager",
    "DiskQuotaError",
    "DynamicVersionWalkStep",
    "DynamicVersionWalkingResult",
    "EngineStatus",
    "EngineTrack",
    "EngineTrackSummary",
    "EnvironmentFingerprint",
    "FilesystemAudit",
    "GPUDevice",
    "GPUDeviceVRAM",
    "GPUProfile",
    "HDF5FilterProfile",
    "HPCMemoryParseError",
    "HPCMemoryProfile",
    "HPCSchedulerType",
    "HPCScratchAllocationError",
    "HPCScratchProfile",
    "HPCThreadAffinityProfile",
    "HPCTopologyError",
    "HPCTopologyProfile",
    "IEEE754PrecisionAudit",
    "IPCSecurityAudit",
    "KernelLimitsAudit",
    "LockingVerificationError",
    "MPSControlError",
    "MPSDaemonAudit",
    "MPSStatus",
    "ManifestFilterAudit",
    "MemoryAudit",
    "MendeleevMassRecord",
    "OSProfile",
    "Phase1AuditReport",
    "Phase2AuditError",
    "Phase2AuditReport",
    "Phase3AuditError",
    "Phase3AuditReport",
    "Phase4AuditError",
    "Phase4AuditReport",
    "Phase5AuditError",
    "Phase5AuditReport",
    "Phase6AuditError",
    "Phase6AuditReport",
    "Phase7AuditError",
    "Phase7AuditReport",
    "PhaseStatus",
    "SiloAuditItem",
    "SiloConfig",
    "SiloProvisioningError",
    "SiloStatus",
    "SiloType",
    "StorageMode",
    "StoragePathProfile",
    "SWMRRuntimeAudit",
    "ToolchainItem",
    "VRAMAllocationError",
    "VRAMBudgetReport",
    "VersionWalkingError",
    "WSL9PMountError",
    "audit_all_engines",
    "audit_container_sifs",
    "audit_cpu",
    "audit_filesystem",
    "audit_gpus",
    "audit_ipc_and_mps_security",
    "audit_kernel_limits",
    "audit_memory",
    "audit_micro_silos",
    "audit_single_binary",
    "audit_toolchains",
    "build_pinned_memory_limit_string",
    "build_track_summaries",
    "calculate_vram_budget",
    "compute_environment_fingerprint",
    "compute_thread_affinity_profile",
    "configure_mps_device_limit",
    "detect_hpc_scheduler",
    "discover_mps_binaries",
    "enforce_python_version",
    "enforce_socket_directory_permissions",
    "enforce_storage_permissions",
    "execute_dynamic_version_walking",
    "filter_silos_by_manifest",
    "generate_environment_injection_dict",
    "generate_mps_activation_scripts",
    "get_current_username",
    "get_default_silo_configs",
    "get_native_memory_env_vars",
    "get_native_stack_flags",
    "get_silo_executable_path",
    "inject_mps_environment_variables",
    "inject_silo_stack_and_env_flags",
    "interrogate_os",
    "load_deployment_manifest",
    "parse_cgroup_cpu_quota",
    "parse_cgroup_memory_limit",
    "parse_hpc_memory_limit",
    "parse_slurm_nodelist",
    "parse_slurm_tasks_per_node",
    "phase_1_main",
    "phase_2_main",
    "phase_3_main",
    "phase_4_main",
    "phase_5_main",
    "phase_6_main",
    "phase_7_main",
    "probe_amd_gpus",
    "probe_gpu_devices_vram",
    "probe_intel_gpus",
    "probe_mps_daemon_status",
    "probe_nvidia_gpus",
    "probe_swmr_locking_capabilities",
    "provision_archive_pes_db",
    "provision_micro_silo",
    "provision_runtime_active_db",
    "resolve_databases_directory",
    "resolve_hpc_scratch_directory",
    "resolve_mps_log_directory",
    "resolve_mps_pipe_directory",
    "resolve_p2_registry_path",
    "resolve_p3_registry_path",
    "resolve_p4_registry_path",
    "resolve_p5_registry_path",
    "resolve_p6_registry_path",
    "resolve_p7_registry_path",
    "resolve_scratch_directory",
    "resolve_silo_base_directory",
    "run_phase_1_audit",
    "run_phase_2_audit",
    "run_phase_3_audit",
    "run_phase_4_audit",
    "run_phase_5_audit",
    "run_phase_6_audit",
    "run_phase_7_audit",
    "BindPolicy",
    "GatewayConfigProfile",
    "GatewayServiceType",
    "Phase8AuditError",
    "Phase8AuditReport",
    "PortAllocationError",
    "PortBindingProfile",
    "PortRangeExhaustedError",
    "ProtocolType",
    "SocketBindingError",
    "allocate_all_gateway_services",
    "allocate_port",
    "generate_phase_8_env_vars",
    "phase_8_main",
    "probe_port_availability",
    "resolve_p8_registry_path",
    "run_phase_8_audit",
    "scan_local_fallback_binaries",
    "start_mps_daemon",
    "stop_mps_daemon",
    "verify_disk_quota",
    "verify_ieee754_subnormal_precision",
    "verify_mendeleev_authority",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_8.py ---
"""
CoChem Setup Phase 8: Network Port Allocation & Dynamic Gateway Binding Gatekeeper.
Production-grade, zero-mock gatekeeping engine for network interface resolution,
OS port availability probing (TCP/UDP), conflict resolution and collision avoidance,
gateway configuration profiling (Dock REST API, Gateway IPC ZMQ, UI Dashboard, Telemetry Stream),
environment variable injection generation, and transactional atomic persistence into
the Golden Registry (p8.json).

SRS Document 2 Part 2 (Section 3.8), SRS Document 1 (Section 2), Method Matrix v4, and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# 1. CUSTOM EXCEPTION HIERARCHY
# =============================================================================


class Phase8AuditError(RuntimeError):
    """Raised when critical Phase 8 network audit or gateway setup fails fatally."""


class PortAllocationError(RuntimeError):
    """Raised when dynamic network port allocation fails."""


class SocketBindingError(RuntimeError):
    """Raised when OS socket binding probe or conflict check fails."""


class PortRangeExhaustedError(RuntimeError):
    """Raised when no available ports can be found in the specified range."""


# =============================================================================
# 2. ENUMERATIONS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class GatewayServiceType(str, Enum):
    """Supported CoChem Gateway service identifiers."""

    DOCK_REST_API = "DOCK_REST_API"
    GATEWAY_IPC_ZMQ = "GATEWAY_IPC_ZMQ"
    UI_DASHBOARD = "UI_DASHBOARD"
    TELEMETRY_STREAM = "TELEMETRY_STREAM"


class ProtocolType(str, Enum):
    """Transport layer protocol enumeration."""

    TCP = "TCP"
    UDP = "UDP"


class BindPolicy(str, Enum):
    """Network interface binding policy classification."""

    LOCALHOST_ONLY = "LOCALHOST_ONLY"
    ALL_INTERFACES = "ALL_INTERFACES"
    CUSTOM_IP = "CUSTOM_IP"


# =============================================================================
# 3. PYDANTIC V2 DATA MODELS
# =============================================================================


class PortBindingProfile(BaseModel):
    """Individual gateway service port binding profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    service: GatewayServiceType = Field(..., description="Gateway service type identifier")
    protocol: ProtocolType = Field(default=ProtocolType.TCP, description="Transport layer protocol")
    requested_port: int = Field(..., ge=1, le=65535, description="Initial requested port number")
    allocated_port: int = Field(..., ge=1, le=65535, description="Successfully allocated port number")
    bind_host: str = Field(default="127.0.0.1", description="Bound network interface host address")
    is_bound_successfully: bool = Field(default=True, description="Whether port probe was successful")
    is_conflict_resolved: bool = Field(default=False, description="Whether port conflict resolution was triggered")
    environment_variable: str = Field(..., description="Injected environment variable name")
    url: Optional[str] = Field(default=None, description="Constructed service connection endpoint URL")


class GatewayConfigProfile(BaseModel):
    """Aggregated gateway configuration and port allocation profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    bind_host: str = Field(default="127.0.0.1", description="Global gateway bind host address")
    bind_policy: BindPolicy = Field(default=BindPolicy.LOCALHOST_ONLY, description="Gateway interface binding policy")
    dock_api: PortBindingProfile = Field(..., description="Dock REST API service profile")
    gateway_zmq: PortBindingProfile = Field(..., description="Gateway IPC ZMQ service profile")
    ui_dashboard: PortBindingProfile = Field(..., description="UI Dashboard service profile")
    telemetry_stream: PortBindingProfile = Field(..., description="Telemetry Stream UDP service profile")
    all_services_allocated: bool = Field(default=True, description="Whether all 4 services are successfully allocated")
    total_services_bound: int = Field(default=4, description="Count of allocated gateway services")


class Phase8AuditReport(BaseModel):
    """Complete serialized audit report and Golden Registry record for Setup Phase 8."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(default="cochem_setup_phase_8", description="Setup phase identifier")
    status: PhaseStatus = Field(..., description="Overall execution status of Phase 8")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    artifact_path: str = Field(..., description="Absolute path to generated p8.json registry artifact")
    gateway_profile: GatewayConfigProfile = Field(..., description="Complete gateway configuration and port bindings")
    injected_env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Environment variable injection mapping"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal diagnostic warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal or recoverable error messages")


# =============================================================================
# 4. OS SOCKET PROBING & PORT ALLOCATION ENGINE
# =============================================================================


def probe_port_availability(
    port: int,
    host: str = "127.0.0.1",
    protocol: ProtocolType = ProtocolType.TCP,
    timeout: float = 1.0,
) -> bool:
    """
    Probe whether a network port is available for binding on the specified host and protocol.
    Performs real OS socket binding probe.
    """
    if not (1 <= port <= 65535):
        return False

    sock_type = socket.SOCK_STREAM if protocol == ProtocolType.TCP else socket.SOCK_DGRAM
    try:
        with socket.socket(socket.AF_INET, sock_type) as probe_sock:
            probe_sock.settimeout(timeout)
            probe_sock.bind((host, port))
            return True
    except (OSError, socket.error):
        return False


def allocate_port(
    preferred_port: int,
    port_range: Tuple[int, int] = (5000, 9000),
    host: str = "127.0.0.1",
    protocol: ProtocolType = ProtocolType.TCP,
    excluded_ports: Optional[Set[int]] = None,
) -> Tuple[int, bool]:
    """
    Allocate an available network port, attempting preferred_port first, scanning port_range on conflict.
    Returns (allocated_port, is_conflict_resolved).
    """
    excluded = excluded_ports if excluded_ports is not None else set()
    start_port, end_port = port_range

    if start_port > end_port:
        start_port, end_port = end_port, start_port

    if preferred_port not in excluded and probe_port_availability(preferred_port, host=host, protocol=protocol):
        return preferred_port, False

    candidates: List[int] = []
    if start_port <= preferred_port <= end_port:
        candidates = list(range(preferred_port + 1, end_port + 1)) + list(range(start_port, preferred_port))
    else:
        candidates = list(range(start_port, end_port + 1))

    for port in candidates:
        if port not in excluded and probe_port_availability(port, host=host, protocol=protocol):
            return port, True

    raise PortRangeExhaustedError(
        f"Unable to allocate {protocol.value} port on host '{host}'. Port range [{start_port}, {end_port}] exhausted."
    )


def resolve_bind_policy(host: str, allow_public_bind: bool = False) -> Tuple[str, BindPolicy]:
    """
    Resolve network host binding policy according to air-gap security constraints.
    """
    normalized_host = host.strip()
    if normalized_host in ("127.0.0.1", "localhost", "::1"):
        return normalized_host, BindPolicy.LOCALHOST_ONLY

    if not allow_public_bind:
        return "127.0.0.1", BindPolicy.LOCALHOST_ONLY

    if normalized_host in ("0.0.0.0", "::"):
        return normalized_host, BindPolicy.ALL_INTERFACES

    return normalized_host, BindPolicy.CUSTOM_IP


def construct_service_url(
    protocol: ProtocolType,
    service_type: GatewayServiceType,
    host: str,
    port: int,
) -> str:
    """
    Construct service endpoint connection URL based on protocol and service type.
    """
    if service_type in (GatewayServiceType.DOCK_REST_API, GatewayServiceType.UI_DASHBOARD):
        scheme = "http"
    elif service_type == GatewayServiceType.GATEWAY_IPC_ZMQ:
        scheme = "tcp"
    elif service_type == GatewayServiceType.TELEMETRY_STREAM:
        scheme = "udp" if protocol == ProtocolType.UDP else "tcp"
    else:
        scheme = "http" if protocol == ProtocolType.TCP else "udp"

    return f"{scheme}://{host}:{port}"


def allocate_all_gateway_services(
    bind_host: str = "127.0.0.1",
    dock_port: Optional[int] = None,
    gateway_port: Optional[int] = None,
    ui_port: Optional[int] = None,
    telemetry_port: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    allow_public_bind: bool = False,
    port_range: Tuple[int, int] = (5000, 60000),
    excluded_ports: Optional[Set[int]] = None,
) -> GatewayConfigProfile:
    """
    Allocate distinct ports for all four CoChem Gateway services with conflict resolution.
    """
    target_env = os.environ if env is None else env

    raw_host = bind_host
    if "COCHEM_BIND_HOST" in target_env and target_env["COCHEM_BIND_HOST"].strip() and bind_host == "127.0.0.1":
        raw_host = target_env["COCHEM_BIND_HOST"].strip()

    effective_host, bind_policy = resolve_bind_policy(raw_host, allow_public_bind=allow_public_bind)

    def parse_int_env(key: str) -> Optional[int]:
        if key in target_env and target_env[key].strip():
            try:
                return int(target_env[key].strip())
            except ValueError:
                return None
        return None

    req_dock = dock_port if dock_port is not None else (parse_int_env("COCHEM_DOCK_PORT") or 8000)
    req_gateway = (
        gateway_port
        if gateway_port is not None
        else (parse_int_env("COCHEM_GATEWAY_PORT") or parse_int_env("COCHEM_ZMQ_PORT") or 5555)
    )
    req_ui = ui_port if ui_port is not None else (parse_int_env("COCHEM_UI_PORT") or 8888)
    req_telem = telemetry_port if telemetry_port is not None else (parse_int_env("COCHEM_TELEMETRY_PORT") or 54321)

    allocated_tcp: Set[int] = set(excluded_ports) if excluded_ports else set()
    allocated_udp: Set[int] = set(excluded_ports) if excluded_ports else set()

    # 1. Dock REST API (TCP)
    dock_allocated, dock_resolved = allocate_port(
        preferred_port=req_dock,
        port_range=port_range,
        host=effective_host,
        protocol=ProtocolType.TCP,
        excluded_ports=allocated_tcp,
    )
    allocated_tcp.add(dock_allocated)
    dock_profile = PortBindingProfile(
        service=GatewayServiceType.DOCK_REST_API,
        protocol=ProtocolType.TCP,
        requested_port=req_dock,
        allocated_port=dock_allocated,
        bind_host=effective_host,
        is_bound_successfully=True,
        is_conflict_resolved=dock_resolved,
        environment_variable="COCHEM_DOCK_PORT",
        url=construct_service_url(ProtocolType.TCP, GatewayServiceType.DOCK_REST_API, effective_host, dock_allocated),
    )

    # 2. Gateway IPC ZMQ (TCP)
    zmq_allocated, zmq_resolved = allocate_port(
        preferred_port=req_gateway,
        port_range=port_range,
        host=effective_host,
        protocol=ProtocolType.TCP,
        excluded_ports=allocated_tcp,
    )
    allocated_tcp.add(zmq_allocated)
    zmq_profile = PortBindingProfile(
        service=GatewayServiceType.GATEWAY_IPC_ZMQ,
        protocol=ProtocolType.TCP,
        requested_port=req_gateway,
        allocated_port=zmq_allocated,
        bind_host=effective_host,
        is_bound_successfully=True,
        is_conflict_resolved=zmq_resolved,
        environment_variable="COCHEM_GATEWAY_PORT",
        url=construct_service_url(ProtocolType.TCP, GatewayServiceType.GATEWAY_IPC_ZMQ, effective_host, zmq_allocated),
    )

    # 3. UI Dashboard (TCP)
    ui_allocated, ui_resolved = allocate_port(
        preferred_port=req_ui,
        port_range=port_range,
        host=effective_host,
        protocol=ProtocolType.TCP,
        excluded_ports=allocated_tcp,
    )
    allocated_tcp.add(ui_allocated)
    ui_profile = PortBindingProfile(
        service=GatewayServiceType.UI_DASHBOARD,
        protocol=ProtocolType.TCP,
        requested_port=req_ui,
        allocated_port=ui_allocated,
        bind_host=effective_host,
        is_bound_successfully=True,
        is_conflict_resolved=ui_resolved,
        environment_variable="COCHEM_UI_PORT",
        url=construct_service_url(ProtocolType.TCP, GatewayServiceType.UI_DASHBOARD, effective_host, ui_allocated),
    )

    # 4. Telemetry Stream (UDP)
    telem_allocated, telem_resolved = allocate_port(
        preferred_port=req_telem,
        port_range=port_range,
        host=effective_host,
        protocol=ProtocolType.UDP,
        excluded_ports=allocated_udp,
    )
    allocated_udp.add(telem_allocated)
    telem_profile = PortBindingProfile(
        service=GatewayServiceType.TELEMETRY_STREAM,
        protocol=ProtocolType.UDP,
        requested_port=req_telem,
        allocated_port=telem_allocated,
        bind_host=effective_host,
        is_bound_successfully=True,
        is_conflict_resolved=telem_resolved,
        environment_variable="COCHEM_TELEMETRY_PORT",
        url=construct_service_url(ProtocolType.UDP, GatewayServiceType.TELEMETRY_STREAM, effective_host, telem_allocated),
    )

    return GatewayConfigProfile(
        bind_host=effective_host,
        bind_policy=bind_policy,
        dock_api=dock_profile,
        gateway_zmq=zmq_profile,
        ui_dashboard=ui_profile,
        telemetry_stream=telem_profile,
        all_services_allocated=True,
        total_services_bound=4,
    )


# =============================================================================
# 5. ENVIRONMENT INJECTION & REGISTRY PATH RESOLUTION
# =============================================================================


def generate_environment_injection_dict(gateway_config: GatewayConfigProfile) -> Dict[str, str]:
    """
    Generate the complete dictionary of environment variables injected for downstream subprocesses.
    """
    return {
        "COCHEM_BIND_HOST": gateway_config.bind_host,
        "COCHEM_DOCK_PORT": str(gateway_config.dock_api.allocated_port),
        "COCHEM_DOCK_URL": gateway_config.dock_api.url or "",
        "COCHEM_GATEWAY_PORT": str(gateway_config.gateway_zmq.allocated_port),
        "COCHEM_ZMQ_PORT": str(gateway_config.gateway_zmq.allocated_port),
        "COCHEM_GATEWAY_URL": gateway_config.gateway_zmq.url or "",
        "COCHEM_UI_PORT": str(gateway_config.ui_dashboard.allocated_port),
        "COCHEM_UI_URL": gateway_config.ui_dashboard.url or "",
        "COCHEM_TELEMETRY_PORT": str(gateway_config.telemetry_stream.allocated_port),
        "COCHEM_TELEMETRY_URL": gateway_config.telemetry_stream.url or "",
    }


def resolve_p8_registry_path(
    output_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Resolve the target filesystem path for the Phase 8 Golden Registry artifact (p8.json).
    """
    if output_dir is not None:
        base = Path(output_dir).resolve()
        if base.suffix == ".json" or base.name == "p8.json":
            return base
        return (base / "p8.json").resolve()

    target_env = os.environ if env is None else env

    if "COCHEM_REGISTRY_DIR" in target_env and target_env["COCHEM_REGISTRY_DIR"].strip():
        return (Path(target_env["COCHEM_REGISTRY_DIR"]) / "p8.json").resolve()

    if "COCHEM_ARTIFACT_DIR" in target_env and target_env["COCHEM_ARTIFACT_DIR"].strip():
        return (Path(target_env["COCHEM_ARTIFACT_DIR"]) / "Registry" / "p8.json").resolve()

    return (Path.home() / "CoChem_Artifacts" / "Registry" / "p8.json").resolve()


# =============================================================================
# 6. TRANSACTIONAL DEPENDENCY MANAGER
# =============================================================================


class DependencyManager:
    """
    Context manager providing transactional and idempotent atomic writing to the Golden Registry.
    Guarantees rollback and cleanup of intermediate temporary files upon unhandled exceptions.
    """

    def __init__(self, target_path: Union[str, Path]) -> None:
        self.target_path = Path(target_path).resolve()
        self.temp_path = Path(str(self.target_path) + f".tmp_{uuid.uuid4().hex[:8]}")
        self._committed = False

    def __enter__(self) -> DependencyManager:
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def write_payload(self, payload: Union[Dict[str, Any], BaseModel]) -> None:
        """Write JSON serialized payload to the temporary file."""
        with open(self.temp_path, "w", encoding="utf-8") as f:
            if isinstance(payload, BaseModel):
                f.write(payload.model_dump_json(indent=2))
            else:
                json.dump(payload, f, indent=2)
        self._committed = True

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None or not self._committed:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            return

        try:
            if self.temp_path.exists():
                if self.target_path.exists():
                    try:
                        self.target_path.unlink()
                    except Exception:
                        pass
                self.temp_path.rename(self.target_path)
        except Exception:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            raise


# =============================================================================
# 7. MASTER AUDIT ORCHESTRATOR
# =============================================================================


def run_phase_8_audit(
    output_dir: Optional[Union[str, Path]] = None,
    bind_host: str = "127.0.0.1",
    dock_port: Optional[int] = None,
    gateway_port: Optional[int] = None,
    ui_port: Optional[int] = None,
    telemetry_port: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    allow_public_bind: bool = False,
    port_range: Tuple[int, int] = (5000, 60000),
    dry_run: bool = False,
) -> Phase8AuditReport:
    """
    Execute the Stage 0 Setup Phase 8 Network Port Allocation & Dynamic Gateway Binding audit.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    target_env = os.environ if env is None else env
    warnings: List[str] = []
    errors: List[str] = []

    p8_path = resolve_p8_registry_path(output_dir=output_dir, env=target_env)

    try:
        gateway_profile = allocate_all_gateway_services(
            bind_host=bind_host,
            dock_port=dock_port,
            gateway_port=gateway_port,
            ui_port=ui_port,
            telemetry_port=telemetry_port,
            env=target_env,
            allow_public_bind=allow_public_bind,
            port_range=port_range,
        )
    except Exception as exc:
        errors.append(f"Gateway port allocation failed: {exc}")
        effective_host, bind_policy = resolve_bind_policy(bind_host, allow_public_bind=allow_public_bind)
        dock_unbound = PortBindingProfile(
            service=GatewayServiceType.DOCK_REST_API,
            protocol=ProtocolType.TCP,
            requested_port=dock_port or 8000,
            allocated_port=dock_port or 8000,
            bind_host=effective_host,
            is_bound_successfully=False,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
        )
        zmq_unbound = PortBindingProfile(
            service=GatewayServiceType.GATEWAY_IPC_ZMQ,
            protocol=ProtocolType.TCP,
            requested_port=gateway_port or 5555,
            allocated_port=gateway_port or 5555,
            bind_host=effective_host,
            is_bound_successfully=False,
            is_conflict_resolved=False,
            environment_variable="COCHEM_GATEWAY_PORT",
        )
        ui_unbound = PortBindingProfile(
            service=GatewayServiceType.UI_DASHBOARD,
            protocol=ProtocolType.TCP,
            requested_port=ui_port or 8888,
            allocated_port=ui_port or 8888,
            bind_host=effective_host,
            is_bound_successfully=False,
            is_conflict_resolved=False,
            environment_variable="COCHEM_UI_PORT",
        )
        telem_unbound = PortBindingProfile(
            service=GatewayServiceType.TELEMETRY_STREAM,
            protocol=ProtocolType.UDP,
            requested_port=telemetry_port or 54321,
            allocated_port=telemetry_port or 54321,
            bind_host=effective_host,
            is_bound_successfully=False,
            is_conflict_resolved=False,
            environment_variable="COCHEM_TELEMETRY_PORT",
        )
        gateway_profile = GatewayConfigProfile(
            bind_host=effective_host,
            bind_policy=bind_policy,
            dock_api=dock_unbound,
            gateway_zmq=zmq_unbound,
            ui_dashboard=ui_unbound,
            telemetry_stream=telem_unbound,
            all_services_allocated=False,
            total_services_bound=0,
        )

    if gateway_profile.dock_api.is_conflict_resolved:
        warnings.append(
            f"Dock REST API port conflict resolved: port {gateway_profile.dock_api.requested_port} -> {gateway_profile.dock_api.allocated_port}"
        )
    if gateway_profile.gateway_zmq.is_conflict_resolved:
        warnings.append(
            f"Gateway IPC ZMQ port conflict resolved: port {gateway_profile.gateway_zmq.requested_port} -> {gateway_profile.gateway_zmq.allocated_port}"
        )
    if gateway_profile.ui_dashboard.is_conflict_resolved:
        warnings.append(
            f"UI Dashboard port conflict resolved: port {gateway_profile.ui_dashboard.requested_port} -> {gateway_profile.ui_dashboard.allocated_port}"
        )
    if gateway_profile.telemetry_stream.is_conflict_resolved:
        warnings.append(
            f"Telemetry Stream port conflict resolved: port {gateway_profile.telemetry_stream.requested_port} -> {gateway_profile.telemetry_stream.allocated_port}"
        )

    injected_env = generate_environment_injection_dict(gateway_profile)

    if errors:
        status = PhaseStatus.FAILED
    elif not gateway_profile.all_services_allocated:
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    report = Phase8AuditReport(
        phase_id="cochem_setup_phase_8",
        status=status,
        timestamp_utc=timestamp,
        artifact_path=str(p8_path),
        gateway_profile=gateway_profile,
        injected_env_vars=injected_env,
        warnings=warnings,
        errors=errors,
    )

    if not dry_run and status != PhaseStatus.FAILED:
        with DependencyManager(p8_path) as dm:
            dm.write_payload(report)

    return report


# =============================================================================
# 8. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entrypoint for Stage 0 Setup Phase 8: Dynamic Gateway Binding & Port Allocation Gatekeeper.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 8: Dynamic Gateway Binding & Port Allocation Gatekeeper."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom directory path for Golden Registry artifact (p8.json)",
    )
    parser.add_argument(
        "--bind-host",
        "--host",
        type=str,
        default="127.0.0.1",
        help="Bind IP host address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--dock-port",
        type=int,
        default=None,
        help="Preferred port for Dock REST API service (default: 8000)",
    )
    parser.add_argument(
        "--gateway-port",
        "--zmq-port",
        type=int,
        default=None,
        help="Preferred port for Gateway IPC ZMQ service (default: 5555)",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=None,
        help="Preferred port for UI Dashboard service (default: 8888)",
    )
    parser.add_argument(
        "--telemetry-port",
        type=int,
        default=None,
        help="Preferred port for Telemetry Stream UDP service (default: 54321)",
    )
    parser.add_argument(
        "--allow-public-bind",
        action="store_true",
        help="Permit binding to 0.0.0.0 or external network interfaces",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate port allocation without writing to the physical registry",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_8_audit(
            output_dir=args.output_dir,
            bind_host=args.bind_host,
            dock_port=args.dock_port,
            gateway_port=args.gateway_port,
            ui_port=args.ui_port,
            telemetry_port=args.telemetry_port,
            allow_public_bind=args.allow_public_bind,
            dry_run=args.dry_run,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 75)
            print("COCHEM SETUP PHASE 8: NETWORK PORT ALLOCATION & GATEWAY BINDING")
            print("=" * 75)
            print(f"Phase ID:          {report.phase_id}")
            print(f"Status:            {report.status.value}")
            print(f"Timestamp UTC:     {report.timestamp_utc}")
            print(f"Artifact Path:     {report.artifact_path}")
            print(f"Bind Host:         {report.gateway_profile.bind_host}")
            print(f"Bind Policy:       {report.gateway_profile.bind_policy.value}")
            print("-" * 75)
            print("Service Port Allocations:")
            dock = report.gateway_profile.dock_api
            print(
                f"  Dock REST API:    Port {dock.allocated_port} ({dock.protocol.value}) -> {dock.url} [Resolved: {dock.is_conflict_resolved}]"
            )
            zmq = report.gateway_profile.gateway_zmq
            print(
                f"  Gateway IPC ZMQ:  Port {zmq.allocated_port} ({zmq.protocol.value}) -> {zmq.url} [Resolved: {zmq.is_conflict_resolved}]"
            )
            ui = report.gateway_profile.ui_dashboard
            print(
                f"  UI Dashboard:     Port {ui.allocated_port} ({ui.protocol.value}) -> {ui.url} [Resolved: {ui.is_conflict_resolved}]"
            )
            telem = report.gateway_profile.telemetry_stream
            print(
                f"  Telemetry Stream: Port {telem.allocated_port} ({telem.protocol.value}) -> {telem.url} [Resolved: {telem.is_conflict_resolved}]"
            )
            print("-" * 75)
            print(f"Injected Env Vars ({len(report.injected_env_vars)} total):")
            for k, v in report.injected_env_vars.items():
                print(f"  {k} = {v}")
            print("-" * 75)
            print(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"  - {w}")
            print(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                print(f"  - {e}")
            print("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        sys.stderr.write(f"\n[FATAL PHASE 8 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_setup_phase_8.py ---
"""
Unit test suite for CoChem Setup Phase 8: Network Port Allocation & Dynamic Gateway Binding Gatekeeper.
Strict Zero-Mock Mandate: Real socket creation, real OS port binding probes, real TCP/UDP conflict
resolution, real temporary directory persistence, real environment variable injection dictionaries,
and transactional atomic state persistence into the Golden Registry (p8.json).

SRS Document 2 Part 2 (Section 3.8), SRS Document 1 (Section 2), Method Matrix v4, and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_8 import (
    BindPolicy,
    DependencyManager,
    GatewayConfigProfile,
    GatewayServiceType,
    Phase8AuditError,
    Phase8AuditReport,
    PhaseStatus,
    PortAllocationError,
    PortBindingProfile,
    PortRangeExhaustedError,
    ProtocolType,
    SocketBindingError,
    allocate_all_gateway_services,
    allocate_port,
    construct_service_url,
    generate_environment_injection_dict,
    main,
    probe_port_availability,
    resolve_bind_policy,
    resolve_p8_registry_path,
    run_phase_8_audit,
)


def make_temp_dir() -> tempfile.TemporaryDirectory:
    """Create a temporary directory with Windows cleanup resilience."""
    if hasattr(tempfile.TemporaryDirectory, "_ignore_cleanup_errors") or platform.system() == "Windows":
        try:
            return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            pass
    return tempfile.TemporaryDirectory()


# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 8 exception classes inherit from RuntimeError."""
    err1 = Phase8AuditError("Phase 8 fatal error")
    assert isinstance(err1, RuntimeError)
    err2 = PortAllocationError("Port allocation error")
    assert isinstance(err2, RuntimeError)
    err3 = SocketBindingError("Socket binding error")
    assert isinstance(err3, RuntimeError)
    err4 = PortRangeExhaustedError("Port range exhausted")
    assert isinstance(err4, RuntimeError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_gateway_service_type_enum() -> None:
    """Verify GatewayServiceType enum values."""
    assert GatewayServiceType.DOCK_REST_API.value == "DOCK_REST_API"
    assert GatewayServiceType.GATEWAY_IPC_ZMQ.value == "GATEWAY_IPC_ZMQ"
    assert GatewayServiceType.UI_DASHBOARD.value == "UI_DASHBOARD"
    assert GatewayServiceType.TELEMETRY_STREAM.value == "TELEMETRY_STREAM"

    with pytest.raises(ValueError):
        GatewayServiceType("UNKNOWN_SERVICE")


def test_protocol_type_enum() -> None:
    """Verify ProtocolType enum values."""
    assert ProtocolType.TCP.value == "TCP"
    assert ProtocolType.UDP.value == "UDP"

    with pytest.raises(ValueError):
        ProtocolType("HTTP")


def test_bind_policy_enum() -> None:
    """Verify BindPolicy enum values."""
    assert BindPolicy.LOCALHOST_ONLY.value == "LOCALHOST_ONLY"
    assert BindPolicy.ALL_INTERFACES.value == "ALL_INTERFACES"
    assert BindPolicy.CUSTOM_IP.value == "CUSTOM_IP"


# =============================================================================
# 2. PYDANTIC V2 SCHEMA VALIDATION TESTS
# =============================================================================


def test_port_binding_profile_validation() -> None:
    """Test PortBindingProfile model validation, constraints, and extra field rejection."""
    profile = PortBindingProfile(
        service=GatewayServiceType.DOCK_REST_API,
        protocol=ProtocolType.TCP,
        requested_port=8000,
        allocated_port=8000,
        bind_host="127.0.0.1",
        is_bound_successfully=True,
        is_conflict_resolved=False,
        environment_variable="COCHEM_DOCK_PORT",
        url="http://127.0.0.1:8000",
    )
    assert profile.service == GatewayServiceType.DOCK_REST_API
    assert profile.allocated_port == 8000
    assert profile.bind_host == "127.0.0.1"
    assert profile.is_bound_successfully is True
    assert profile.url == "http://127.0.0.1:8000"

    # Port constraint tests (port must be between 1 and 65535)
    with pytest.raises(ValidationError):
        PortBindingProfile(
            service=GatewayServiceType.DOCK_REST_API,
            protocol=ProtocolType.TCP,
            requested_port=0,
            allocated_port=0,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
        )

    with pytest.raises(ValidationError):
        PortBindingProfile(
            service=GatewayServiceType.DOCK_REST_API,
            protocol=ProtocolType.TCP,
            requested_port=70000,
            allocated_port=70000,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        PortBindingProfile(
            service=GatewayServiceType.DOCK_REST_API,
            protocol=ProtocolType.TCP,
            requested_port=8000,
            allocated_port=8000,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
            unauthorized_key="bad",  # type: ignore[call-arg]
        )


def test_gateway_config_profile_validation() -> None:
    """Test GatewayConfigProfile validation and nested models."""
    dock = PortBindingProfile(
        service=GatewayServiceType.DOCK_REST_API,
        protocol=ProtocolType.TCP,
        requested_port=8000,
        allocated_port=8000,
        bind_host="127.0.0.1",
        is_bound_successfully=True,
        is_conflict_resolved=False,
        environment_variable="COCHEM_DOCK_PORT",
        url="http://127.0.0.1:8000",
    )
    zmq = PortBindingProfile(
        service=GatewayServiceType.GATEWAY_IPC_ZMQ,
        protocol=ProtocolType.TCP,
        requested_port=5555,
        allocated_port=5555,
        bind_host="127.0.0.1",
        is_bound_successfully=True,
        is_conflict_resolved=False,
        environment_variable="COCHEM_GATEWAY_PORT",
        url="tcp://127.0.0.1:5555",
    )
    ui = PortBindingProfile(
        service=GatewayServiceType.UI_DASHBOARD,
        protocol=ProtocolType.TCP,
        requested_port=8888,
        allocated_port=8888,
        bind_host="127.0.0.1",
        is_bound_successfully=True,
        is_conflict_resolved=False,
        environment_variable="COCHEM_UI_PORT",
        url="http://127.0.0.1:8888",
    )
    telem = PortBindingProfile(
        service=GatewayServiceType.TELEMETRY_STREAM,
        protocol=ProtocolType.UDP,
        requested_port=54321,
        allocated_port=54321,
        bind_host="127.0.0.1",
        is_bound_successfully=True,
        is_conflict_resolved=False,
        environment_variable="COCHEM_TELEMETRY_PORT",
        url="udp://127.0.0.1:54321",
    )
    gateway = GatewayConfigProfile(
        bind_host="127.0.0.1",
        bind_policy=BindPolicy.LOCALHOST_ONLY,
        dock_api=dock,
        gateway_zmq=zmq,
        ui_dashboard=ui,
        telemetry_stream=telem,
        all_services_allocated=True,
        total_services_bound=4,
    )
    assert gateway.bind_host == "127.0.0.1"
    assert gateway.total_services_bound == 4
    assert gateway.dock_api.allocated_port == 8000


def test_phase_8_audit_report_roundtrip_serialization() -> None:
    """Test Phase8AuditReport serialization and deserialization roundtrip."""
    with make_temp_dir() as tmpdir:
        art_path = Path(tmpdir) / "p8.json"
        dock = PortBindingProfile(
            service=GatewayServiceType.DOCK_REST_API,
            protocol=ProtocolType.TCP,
            requested_port=8000,
            allocated_port=8000,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
            url="http://127.0.0.1:8000",
        )
        zmq = PortBindingProfile(
            service=GatewayServiceType.GATEWAY_IPC_ZMQ,
            protocol=ProtocolType.TCP,
            requested_port=5555,
            allocated_port=5555,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_GATEWAY_PORT",
            url="tcp://127.0.0.1:5555",
        )
        ui = PortBindingProfile(
            service=GatewayServiceType.UI_DASHBOARD,
            protocol=ProtocolType.TCP,
            requested_port=8888,
            allocated_port=8888,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_UI_PORT",
            url="http://127.0.0.1:8888",
        )
        telem = PortBindingProfile(
            service=GatewayServiceType.TELEMETRY_STREAM,
            protocol=ProtocolType.UDP,
            requested_port=54321,
            allocated_port=54321,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_TELEMETRY_PORT",
            url="udp://127.0.0.1:54321",
        )
        gateway = GatewayConfigProfile(
            bind_host="127.0.0.1",
            bind_policy=BindPolicy.LOCALHOST_ONLY,
            dock_api=dock,
            gateway_zmq=zmq,
            ui_dashboard=ui,
            telemetry_stream=telem,
            all_services_allocated=True,
            total_services_bound=4,
        )
        report = Phase8AuditReport(
            phase_id="cochem_setup_phase_8",
            status=PhaseStatus.PASSED,
            timestamp_utc="2026-08-21T00:00:00Z",
            artifact_path=str(art_path),
            gateway_profile=gateway,
            injected_env_vars={"COCHEM_DOCK_PORT": "8000"},
            warnings=[],
            errors=[],
        )
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["phase_id"] == "cochem_setup_phase_8"
        assert parsed["status"] == "PASSED"
        assert parsed["gateway_profile"]["dock_api"]["allocated_port"] == 8000

        # Deserialization test
        restored = Phase8AuditReport.model_validate(parsed)
        assert restored.status == PhaseStatus.PASSED
        assert restored.gateway_profile.ui_dashboard.allocated_port == 8888


# =============================================================================
# 3. REAL OS SOCKET PROBING TESTS
# =============================================================================


def test_probe_port_availability_real_tcp_socket() -> None:
    """Test TCP port probing on free vs occupied real sockets."""
    # Find an open port first
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    # Free port should return True
    assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.TCP) is True

    # Now bind the port and keep it open
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as active_sock:
        active_sock.bind(("127.0.0.1", free_port))
        active_sock.listen(1)
        # Port is now occupied: probe must return False
        assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.TCP) is False

    # Once closed, port becomes available again
    assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.TCP) is True


def test_probe_port_availability_real_udp_socket() -> None:
    """Test UDP port probing on free vs occupied real sockets."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.UDP) is True

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as active_sock:
        active_sock.bind(("127.0.0.1", free_port))
        # Port is now occupied: probe must return False
        assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.UDP) is False

    assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.UDP) is True


# =============================================================================
# 4. PORT ALLOCATION & CONFLICT RESOLUTION TESTS
# =============================================================================


def test_allocate_port_preferred_available() -> None:
    """Test port allocation when preferred port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    allocated, resolved = allocate_port(
        preferred_port=free_port,
        port_range=(free_port, free_port + 10),
        host="127.0.0.1",
        protocol=ProtocolType.TCP,
    )
    assert allocated == free_port
    assert resolved is False


def test_allocate_port_conflict_resolution_with_active_socket() -> None:
    """Test port allocation sequentially scans when preferred port is actively occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
        s1.bind(("127.0.0.1", 0))
        base_port = s1.getsockname()[1]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.bind(("127.0.0.1", base_port))
        blocker.listen(1)

        # Allocate starting from base_port; should scan to base_port + 1 or higher
        allocated, resolved = allocate_port(
            preferred_port=base_port,
            port_range=(base_port, base_port + 20),
            host="127.0.0.1",
            protocol=ProtocolType.TCP,
        )
        assert allocated != base_port
        assert allocated > base_port
        assert resolved is True


def test_allocate_port_with_excluded_ports() -> None:
    """Test port allocation bypasses excluded ports."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    excluded = {free_port, free_port + 1}
    allocated, resolved = allocate_port(
        preferred_port=free_port,
        port_range=(free_port, free_port + 10),
        host="127.0.0.1",
        protocol=ProtocolType.TCP,
        excluded_ports=excluded,
    )
    assert allocated not in excluded
    assert resolved is True


def test_allocate_port_range_exhausted_error() -> None:
    """Test PortRangeExhaustedError when all ports in range are excluded or occupied."""
    with pytest.raises(PortRangeExhaustedError):
        allocate_port(
            preferred_port=8000,
            port_range=(8000, 8002),
            host="127.0.0.1",
            protocol=ProtocolType.TCP,
            excluded_ports={8000, 8001, 8002},
        )


# =============================================================================
# 5. GATEWAY SERVICES ALLOCATION TESTS
# =============================================================================


def test_allocate_all_gateway_services_defaults() -> None:
    """Test default gateway allocation across all 4 services."""
    profile = allocate_all_gateway_services(
        bind_host="127.0.0.1",
        allow_public_bind=False,
    )
    assert profile.bind_host == "127.0.0.1"
    assert profile.bind_policy == BindPolicy.LOCALHOST_ONLY
    assert profile.total_services_bound == 4
    assert profile.all_services_allocated is True

    # Check distinct ports for TCP services
    tcp_ports = {
        profile.dock_api.allocated_port,
        profile.gateway_zmq.allocated_port,
        profile.ui_dashboard.allocated_port,
    }
    assert len(tcp_ports) == 3


def test_allocate_all_gateway_services_env_overrides() -> None:
    """Test environment variable overrides for gateway services."""
    env = {
        "COCHEM_DOCK_PORT": "8020",
        "COCHEM_GATEWAY_PORT": "5570",
        "COCHEM_UI_PORT": "8910",
        "COCHEM_TELEMETRY_PORT": "54330",
        "COCHEM_BIND_HOST": "127.0.0.1",
    }
    profile = allocate_all_gateway_services(
        bind_host="127.0.0.1",
        env=env,
    )
    assert profile.dock_api.requested_port == 8020
    assert profile.gateway_zmq.requested_port == 5570
    assert profile.ui_dashboard.requested_port == 8910
    assert profile.telemetry_stream.requested_port == 54330


def test_allocate_all_gateway_services_collision_avoidance() -> None:
    """Test that requesting identical ports for different services forces conflict resolution."""
    profile = allocate_all_gateway_services(
        dock_port=8000,
        gateway_port=8000,  # Intentional collision with dock_port
        ui_port=8000,       # Intentional collision with dock_port
        telemetry_port=54321,
        bind_host="127.0.0.1",
    )
    tcp_ports = [
        profile.dock_api.allocated_port,
        profile.gateway_zmq.allocated_port,
        profile.ui_dashboard.allocated_port,
    ]
    # All allocated TCP ports must be unique
    assert len(set(tcp_ports)) == 3
    assert profile.gateway_zmq.is_conflict_resolved is True or profile.ui_dashboard.is_conflict_resolved is True


def test_allocate_all_gateway_services_public_bind_policy() -> None:
    """Test public 0.0.0.0 binding policy when allow_public_bind is True vs False."""
    # When allow_public_bind is False, binding to 0.0.0.0 must degrade or default to 127.0.0.1
    p_airgap = allocate_all_gateway_services(
        bind_host="0.0.0.0",
        allow_public_bind=False,
    )
    assert p_airgap.bind_host == "127.0.0.1"
    assert p_airgap.bind_policy == BindPolicy.LOCALHOST_ONLY

    # When allow_public_bind is True, binding to 0.0.0.0 is permitted
    p_public = allocate_all_gateway_services(
        bind_host="0.0.0.0",
        allow_public_bind=True,
    )
    assert p_public.bind_host == "0.0.0.0"
    assert p_public.bind_policy == BindPolicy.ALL_INTERFACES


# =============================================================================
# 6. ENVIRONMENT INJECTION & REGISTRY PATH RESOLUTION TESTS
# =============================================================================


def test_generate_environment_injection_dict() -> None:
    """Test generation of environment injection mapping dictionary."""
    profile = allocate_all_gateway_services(
        dock_port=8000,
        gateway_port=5555,
        ui_port=8888,
        telemetry_port=54321,
        bind_host="127.0.0.1",
    )
    injected = generate_environment_injection_dict(profile)
    assert "COCHEM_DOCK_PORT" in injected
    assert "COCHEM_GATEWAY_PORT" in injected
    assert "COCHEM_ZMQ_PORT" in injected
    assert "COCHEM_UI_PORT" in injected
    assert "COCHEM_TELEMETRY_PORT" in injected
    assert "COCHEM_BIND_HOST" in injected
    assert "COCHEM_DOCK_URL" in injected
    assert "COCHEM_GATEWAY_URL" in injected
    assert "COCHEM_UI_URL" in injected
    assert injected["COCHEM_BIND_HOST"] == "127.0.0.1"


def test_resolve_p8_registry_path_override() -> None:
    """Test resolving p8.json path with override parameter."""
    with make_temp_dir() as tmpdir:
        target = Path(tmpdir) / "custom_p8.json"
        resolved = resolve_p8_registry_path(output_dir=target)
        assert resolved == target.resolve()

        target_dir = Path(tmpdir) / "registry_sub"
        resolved_dir = resolve_p8_registry_path(output_dir=target_dir)
        assert resolved_dir == (target_dir / "p8.json").resolve()


def test_resolve_p8_registry_path_env_hierarchy() -> None:
    """Test resolving p8.json via environment variables."""
    with make_temp_dir() as tmpdir:
        env_reg = Path(tmpdir) / "reg_env"
        env1 = {"COCHEM_REGISTRY_DIR": str(env_reg)}
        resolved1 = resolve_p8_registry_path(env=env1)
        assert resolved1 == (env_reg / "p8.json").resolve()

        env_art = Path(tmpdir) / "art_env"
        env2 = {"COCHEM_ARTIFACT_DIR": str(env_art)}
        resolved2 = resolve_p8_registry_path(env=env2)
        assert resolved2 == (env_art / "Registry" / "p8.json").resolve()


# =============================================================================
# 7. DEPENDENCY MANAGER & TRANSACTIONAL ATOMIC WRITE TESTS
# =============================================================================


def test_dependency_manager_atomic_write_and_commit() -> None:
    """Test DependencyManager atomic writing and permissions hardening."""
    with make_temp_dir() as tmpdir:
        target_file = Path(tmpdir) / "Registry" / "p8.json"
        payload = {"phase": "phase_8", "status": "PASSED"}

        with DependencyManager(target_file) as dm:
            dm.write_payload(payload)

        assert target_file.exists()
        loaded = json.loads(target_file.read_text(encoding="utf-8"))
        assert loaded["phase"] == "phase_8"
        assert loaded["status"] == "PASSED"


def test_dependency_manager_rollback_on_exception() -> None:
    """Test DependencyManager safely cleans up temp files if an exception is raised."""
    with make_temp_dir() as tmpdir:
        target_file = Path(tmpdir) / "Registry" / "p8.json"

        with pytest.raises(ZeroDivisionError):
            with DependencyManager(target_file) as dm:
                dm.write_payload({"data": "incomplete"})
                _ = 1 / 0

        # Target file must not exist and no temporary files left behind
        assert not target_file.exists()
        remaining_files = list(Path(tmpdir).glob("**/*"))
        assert all(f.is_dir() for f in remaining_files)


# =============================================================================
# 8. MASTER AUDIT ORCHESTRATOR & CLI TESTS
# =============================================================================


def test_run_phase_8_audit_passed() -> None:
    """Test run_phase_8_audit end-to-end execution resulting in PASSED status."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        report = run_phase_8_audit(
            output_dir=art_dir,
            bind_host="127.0.0.1",
        )
        assert report.status == PhaseStatus.PASSED
        assert report.phase_id == "cochem_setup_phase_8"
        assert Path(report.artifact_path).exists()
        assert report.gateway_profile.total_services_bound == 4
        assert len(report.injected_env_vars) >= 6


def test_run_phase_8_audit_dry_run() -> None:
    """Test run_phase_8_audit with dry_run=True does not create artifacts on disk."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        report = run_phase_8_audit(
            output_dir=art_dir,
            bind_host="127.0.0.1",
            dry_run=True,
        )
        assert report.status == PhaseStatus.PASSED
        # In dry run, the file should not be physically written
        assert not Path(report.artifact_path).exists()


def test_run_phase_8_audit_custom_parameters() -> None:
    """Test run_phase_8_audit with custom port overrides."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        report = run_phase_8_audit(
            output_dir=art_dir,
            dock_port=8040,
            gateway_port=5590,
            ui_port=8900,
            telemetry_port=54340,
            bind_host="127.0.0.1",
        )
        assert report.status == PhaseStatus.PASSED
        assert report.gateway_profile.dock_api.allocated_port == 8040
        assert report.gateway_profile.gateway_zmq.allocated_port == 5590
        assert report.gateway_profile.ui_dashboard.allocated_port == 8900
        assert report.gateway_profile.telemetry_stream.allocated_port == 54340


def test_cli_main_success_and_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with argument passing and stdout."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--bind-host", "127.0.0.1"])
        assert ret == 0

        captured = capsys.readouterr()
        assert "PASSED" in captured.out or "Phase 8" in captured.out


def test_probe_port_availability_invalid_port_range() -> None:
    """Test probe_port_availability rejects invalid port numbers <= 0 or > 65535."""
    assert probe_port_availability(0) is False
    assert probe_port_availability(-1) is False
    assert probe_port_availability(65536) is False
    assert probe_port_availability(70000) is False


def test_allocate_port_inverted_range_and_preferred_out_of_range() -> None:
    """Test port allocation with inverted range and preferred_port outside the candidate range."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    # Inverted range: start > end
    allocated, _ = allocate_port(
        preferred_port=free_port,
        port_range=(free_port + 5, free_port),
        host="127.0.0.1",
        protocol=ProtocolType.TCP,
    )
    assert allocated == free_port

    # preferred_port outside range: candidate list built from range
    allocated2, resolved2 = allocate_port(
        preferred_port=100,  # outside range
        port_range=(free_port, free_port + 5),
        host="127.0.0.1",
        protocol=ProtocolType.TCP,
        excluded_ports={100},
    )
    assert free_port <= allocated2 <= free_port + 5
    assert resolved2 is True


def test_resolve_bind_policy_custom_ip_and_public_bind() -> None:
    """Test resolve_bind_policy with custom IP addresses and public interfaces."""
    # When allow_public_bind is True and host is custom IP
    host, policy = resolve_bind_policy("192.168.1.100", allow_public_bind=True)
    assert host == "192.168.1.100"
    assert policy == BindPolicy.CUSTOM_IP

    # When allow_public_bind is False and host is custom IP
    host_airgap, policy_airgap = resolve_bind_policy("192.168.1.100", allow_public_bind=False)
    assert host_airgap == "127.0.0.1"
    assert policy_airgap == BindPolicy.LOCALHOST_ONLY

    # When allow_public_bind is True and host is 0.0.0.0 or ::
    host_all, policy_all = resolve_bind_policy("::", allow_public_bind=True)
    assert host_all == "::"
    assert policy_all == BindPolicy.ALL_INTERFACES


def test_construct_service_url_edge_cases() -> None:
    """Test construct_service_url for different protocol and service type combinations."""
    url_dock = construct_service_url(ProtocolType.TCP, GatewayServiceType.DOCK_REST_API, "127.0.0.1", 8000)
    assert url_dock == "http://127.0.0.1:8000"

    url_zmq = construct_service_url(ProtocolType.TCP, GatewayServiceType.GATEWAY_IPC_ZMQ, "127.0.0.1", 5555)
    assert url_zmq == "tcp://127.0.0.1:5555"

    url_ui = construct_service_url(ProtocolType.TCP, GatewayServiceType.UI_DASHBOARD, "127.0.0.1", 8888)
    assert url_ui == "http://127.0.0.1:8888"

    url_telem_udp = construct_service_url(ProtocolType.UDP, GatewayServiceType.TELEMETRY_STREAM, "127.0.0.1", 54321)
    assert url_telem_udp == "udp://127.0.0.1:54321"

    url_telem_tcp = construct_service_url(ProtocolType.TCP, GatewayServiceType.TELEMETRY_STREAM, "127.0.0.1", 54321)
    assert url_telem_tcp == "tcp://127.0.0.1:54321"


def test_allocate_all_gateway_services_corrupted_env_ports() -> None:
    """Test allocate_all_gateway_services handles invalid non-integer environment variables gracefully."""
    bad_env = {
        "COCHEM_DOCK_PORT": "invalid_port",
        "COCHEM_GATEWAY_PORT": "not_an_int",
        "COCHEM_ZMQ_PORT": "bad_zmq",
        "COCHEM_UI_PORT": "none",
        "COCHEM_TELEMETRY_PORT": "err",
        "COCHEM_BIND_HOST": "127.0.0.1",
    }
    profile = allocate_all_gateway_services(env=bad_env)
    assert profile.all_services_allocated is True
    assert profile.dock_api.requested_port == 8000
    assert profile.gateway_zmq.requested_port == 5555
    assert profile.ui_dashboard.requested_port == 8888
    assert profile.telemetry_stream.requested_port == 54321


def test_resolve_p8_registry_path_default_home_fallback() -> None:
    """Test resolve_p8_registry_path falls back to user home directory when no env vars or args provided."""
    resolved = resolve_p8_registry_path(output_dir=None, env={})
    expected = (Path.home() / "CoChem_Artifacts" / "Registry" / "p8.json").resolve()
    assert resolved == expected


def test_run_phase_8_audit_conflict_warnings() -> None:
    """Test run_phase_8_audit records diagnostic warnings when port conflicts are resolved across all services."""
    # Occupy ports for dock and telemetry
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_dock, \
         socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s_telem:
        s_dock.bind(("127.0.0.1", 0))
        s_telem.bind(("127.0.0.1", 0))
        occ_dock = s_dock.getsockname()[1]
        occ_telem = s_telem.getsockname()[1]

        with make_temp_dir() as tmpdir:
            art_dir = Path(tmpdir) / "Registry"
            report = run_phase_8_audit(
                output_dir=art_dir,
                dock_port=occ_dock,
                gateway_port=occ_dock,  # collision
                ui_port=occ_dock,       # collision
                telemetry_port=occ_telem,
                bind_host="127.0.0.1",
            )
            assert report.status == PhaseStatus.PASSED
            assert len(report.warnings) >= 3


def test_cli_main_exception_failure(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint returns exit code 1 on fatal error."""
    # Passing an invalid host or argument that raises an exception or causes failure
    ret = main(["--output-dir", "NUL" if platform.system() == "Windows" else "/dev/null/bad", "--dock-port", "0", "--port-range", "0"]) if hasattr(main, "port_range") else main(["--bind-host", "127.0.0.1", "--dock-port", "-1"])
    assert ret == 1



def test_run_phase_8_audit_allocation_failure_branch() -> None:
    """Test run_phase_8_audit handles allocation failure, records errors, and returns FAILED status."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        # Specify an impossible port range (e.g. 0 to 0) which will fail port probing
        report = run_phase_8_audit(
            output_dir=art_dir,
            dock_port=0,
            port_range=(0, 0),
            bind_host="127.0.0.1",
        )
        assert report.status == PhaseStatus.FAILED
        assert len(report.errors) > 0
        assert report.gateway_profile.all_services_allocated is False
        assert report.gateway_profile.total_services_bound == 0
        # When failed, artifact should not be created
        assert not (art_dir / "p8.json").exists()


def test_cli_main_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with --json flag."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--bind-host", "127.0.0.1", "--json"])
        assert ret == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["phase_id"] == "cochem_setup_phase_8"
        assert data["status"] == "PASSED"
        assert "gateway_profile" in data


def test_cli_main_port_and_public_bind_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with custom port and public binding flags."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main([
            "--output-dir", out_dir,
            "--bind-host", "0.0.0.0",
            "--dock-port", "8015",
            "--gateway-port", "5565",
            "--ui-port", "8895",
            "--telemetry-port", "54335",
            "--allow-public-bind",
            "--dry-run",
        ])
        assert ret == 0

        captured = capsys.readouterr()
        assert "0.0.0.0" in captured.out
        assert "ALL_INTERFACES" in captured.out


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.