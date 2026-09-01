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
import atexit
import logging

try:
    import psutil
except ImportError:
    psutil = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def sweep_zombies() -> None:
    if psutil is None:
        return
    for p in psutil.process_iter(['pid', 'status']):
        try:
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                p.wait(timeout=1)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied, KeyError):
            pass

atexit.register(sweep_zombies)

# =============================================================================
# 1. CUSTOM EXCEPTION HIERARCHY
# =============================================================================


class Phase8AuditError(RuntimeError):
    """Raised when critical Phase 8 network audit or gateway setup fails fatally."""


class PortAllocationError(Phase8AuditError):
    """Raised when dynamic network port allocation fails."""


class SocketBindingError(Phase8AuditError):
    """Raised when OS socket binding probe or conflict check fails."""


class PortRangeExhaustedError(PortAllocationError):
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
    Performs real OS socket binding probe with adaptive IPv4/IPv6 address family resolution.
    """
    if not (1 <= port <= 65535):
        return False

    sock_type = socket.SOCK_STREAM if protocol == ProtocolType.TCP else socket.SOCK_DGRAM
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, sock_type) as probe_sock:
            try:
                probe_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except (OSError, socket.error):
                pass
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
    Formats IPv6 host addresses in RFC 3986 bracket notation.
    """
    if service_type in (GatewayServiceType.DOCK_REST_API, GatewayServiceType.UI_DASHBOARD):
        scheme = "http"
    elif service_type == GatewayServiceType.GATEWAY_IPC_ZMQ:
        scheme = "tcp"
    elif service_type == GatewayServiceType.TELEMETRY_STREAM:
        scheme = "udp" if protocol == ProtocolType.UDP else "tcp"
    else:
        scheme = "http" if protocol == ProtocolType.TCP else "udp"

    formatted_host = f"[{host}]" if (":" in host and not host.startswith("[")) else host
    return f"{scheme}://{formatted_host}:{port}"


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
                val = int(target_env[key].strip())
                if 1 <= val <= 65535:
                    return val
                return None
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
                self.temp_path.replace(self.target_path)
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

        def sanitize_port(p: Optional[Any], default_port: int) -> int:
            if isinstance(p, int) and 1 <= p <= 65535:
                return p
            return default_port

        safe_dock = sanitize_port(dock_port, 8000)
        safe_zmq = sanitize_port(gateway_port, 5555)
        safe_ui = sanitize_port(ui_port, 8888)
        safe_telem = sanitize_port(telemetry_port, 54321)

        dock_unbound = PortBindingProfile(
            service=GatewayServiceType.DOCK_REST_API,
            protocol=ProtocolType.TCP,
            requested_port=safe_dock,
            allocated_port=safe_dock,
            bind_host=effective_host,
            is_bound_successfully=False,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
        )
        zmq_unbound = PortBindingProfile(
            service=GatewayServiceType.GATEWAY_IPC_ZMQ,
            protocol=ProtocolType.TCP,
            requested_port=safe_zmq,
            allocated_port=safe_zmq,
            bind_host=effective_host,
            is_bound_successfully=False,
            is_conflict_resolved=False,
            environment_variable="COCHEM_GATEWAY_PORT",
        )
        ui_unbound = PortBindingProfile(
            service=GatewayServiceType.UI_DASHBOARD,
            protocol=ProtocolType.TCP,
            requested_port=safe_ui,
            allocated_port=safe_ui,
            bind_host=effective_host,
            is_bound_successfully=False,
            is_conflict_resolved=False,
            environment_variable="COCHEM_UI_PORT",
        )
        telem_unbound = PortBindingProfile(
            service=GatewayServiceType.TELEMETRY_STREAM,
            protocol=ProtocolType.UDP,
            requested_port=safe_telem,
            allocated_port=safe_telem,
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
            logger.info(report.model_dump_json(indent=2))
        else:
            logger.info("=" * 75)
            logger.info("COCHEM SETUP PHASE 8: NETWORK PORT ALLOCATION & GATEWAY BINDING")
            logger.info("=" * 75)
            logger.info(f"Phase ID:          {report.phase_id}")
            logger.info(f"Status:            {report.status.value}")
            logger.info(f"Timestamp UTC:     {report.timestamp_utc}")
            logger.info(f"Artifact Path:     {report.artifact_path}")
            logger.info(f"Bind Host:         {report.gateway_profile.bind_host}")
            logger.info(f"Bind Policy:       {report.gateway_profile.bind_policy.value}")
            logger.info("-" * 75)
            logger.info("Service Port Allocations:")
            dock = report.gateway_profile.dock_api
            logger.info(
                f"  Dock REST API:    Port {dock.allocated_port} ({dock.protocol.value}) -> {dock.url} [Resolved: {dock.is_conflict_resolved}]"
            )
            zmq = report.gateway_profile.gateway_zmq
            logger.info(
                f"  Gateway IPC ZMQ:  Port {zmq.allocated_port} ({zmq.protocol.value}) -> {zmq.url} [Resolved: {zmq.is_conflict_resolved}]"
            )
            ui = report.gateway_profile.ui_dashboard
            logger.info(
                f"  UI Dashboard:     Port {ui.allocated_port} ({ui.protocol.value}) -> {ui.url} [Resolved: {ui.is_conflict_resolved}]"
            )
            telem = report.gateway_profile.telemetry_stream
            logger.info(
                f"  Telemetry Stream: Port {telem.allocated_port} ({telem.protocol.value}) -> {telem.url} [Resolved: {telem.is_conflict_resolved}]"
            )
            logger.info("-" * 75)
            logger.info(f"Injected Env Vars ({len(report.injected_env_vars)} total):")
            for k, v in report.injected_env_vars.items():
                logger.info(f"  {k} = {v}")
            logger.info("-" * 75)
            logger.info(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                logger.warning(f"  - {w}")
            logger.info(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                logger.error(f"  - {e}")
            logger.info("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        logger.error(f"\n[FATAL PHASE 8 ERROR]\n{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
