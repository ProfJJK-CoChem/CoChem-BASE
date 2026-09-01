"""
Unit test suite for CoChem Setup Phase 8: Network Port Allocation & Dynamic Gateway Binding Gatekeeper.
Strict Zero-Mock Mandate: Real socket creation, real OS port binding probes, real TCP/UDP conflict
resolution, real temporary directory persistence, real environment variable injection dictionaries,
and transactional atomic state persistence into the Golden Registry (p8.json).

SRS Document 2 Part 2 (Section 3.8), SRS Document 1 (Section 2), Method Matrix v4, and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import json
import platform
import socket
import tempfile
from pathlib import Path

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
    """Verify custom Phase 8 exception classes inherit from Phase8AuditError and RuntimeError."""
    err1 = Phase8AuditError("Phase 8 fatal error")
    assert isinstance(err1, RuntimeError)
    err2 = PortAllocationError("Port allocation error")
    assert isinstance(err2, Phase8AuditError)
    assert isinstance(err2, RuntimeError)
    err3 = SocketBindingError("Socket binding error")
    assert isinstance(err3, Phase8AuditError)
    assert isinstance(err3, RuntimeError)
    err4 = PortRangeExhaustedError("Port range exhausted")
    assert isinstance(err4, PortAllocationError)
    assert isinstance(err4, Phase8AuditError)
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


def test_construct_service_url_ipv6_bracket_formatting() -> None:
    """Test construct_service_url formats IPv6 hosts in RFC 3986 bracket notation."""
    url_ipv6_dock = construct_service_url(ProtocolType.TCP, GatewayServiceType.DOCK_REST_API, "::1", 8000)
    assert url_ipv6_dock == "http://[::1]:8000"

    url_ipv6_zmq = construct_service_url(ProtocolType.TCP, GatewayServiceType.GATEWAY_IPC_ZMQ, "::1", 5555)
    assert url_ipv6_zmq == "tcp://[::1]:5555"

    url_ipv6_telem = construct_service_url(ProtocolType.UDP, GatewayServiceType.TELEMETRY_STREAM, "::", 54321)
    assert url_ipv6_telem == "udp://[::]:54321"

    # If host is already bracketed, do not double-bracket
    url_already_bracketed = construct_service_url(ProtocolType.TCP, GatewayServiceType.DOCK_REST_API, "[::1]", 8000)
    assert url_already_bracketed == "http://[::1]:8000"


def test_run_phase_8_audit_out_of_range_port_graceful_failure() -> None:
    """Test run_phase_8_audit handles invalid/out-of-range port values gracefully without Pydantic crash."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        # Negative port number triggers error handling and must not raise ValidationError inside except block
        report_neg = run_phase_8_audit(
            output_dir=art_dir,
            dock_port=-1,
            bind_host="127.0.0.1",
        )
        assert report_neg.status == PhaseStatus.FAILED
        assert len(report_neg.errors) > 0
        assert report_neg.gateway_profile.dock_api.requested_port == 8000

        # Port number > 65535 triggers error handling and sanitizes to default port
        report_high = run_phase_8_audit(
            output_dir=art_dir,
            dock_port=70000,
            bind_host="127.0.0.1",
        )
        assert report_high.status == PhaseStatus.FAILED
        assert len(report_high.errors) > 0
        assert report_high.gateway_profile.dock_api.requested_port == 8000


def test_allocate_all_gateway_services_out_of_range_env_ports() -> None:
    """Test allocate_all_gateway_services ignores out-of-range port numbers in environment variables."""
    bad_env = {
        "COCHEM_DOCK_PORT": "-50",
        "COCHEM_GATEWAY_PORT": "99999",
        "COCHEM_UI_PORT": "0",
        "COCHEM_TELEMETRY_PORT": "65536",
        "COCHEM_BIND_HOST": "127.0.0.1",
    }
    profile = allocate_all_gateway_services(env=bad_env)
    assert profile.all_services_allocated is True
    assert profile.dock_api.requested_port == 8000
    assert profile.gateway_zmq.requested_port == 5555
    assert profile.ui_dashboard.requested_port == 8888
    assert profile.telemetry_stream.requested_port == 54321


