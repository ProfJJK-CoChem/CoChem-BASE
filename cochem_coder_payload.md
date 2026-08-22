Cycle 2: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part2_05d_orchestrator_phase_8_prompt.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0
collected 27 items

test_suite\test_cochem_setup_phase_8.py ..F.FFFFFFFFF.FFFFFFF..FFFF      [100%]

================================== FAILURES ===================================
_______________________ test_gateway_service_type_enum ________________________

    def test_gateway_service_type_enum() -> None:
        """Verify GatewayServiceType enum values."""
>       assert GatewayServiceType.DOCK_REST_API.value == "DOCK_REST_API"
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'GatewayServiceType' has no attribute 'DOCK_REST_API'

test_suite\test_cochem_setup_phase_8.py:87: AttributeError
____________________________ test_bind_policy_enum ____________________________

    def test_bind_policy_enum() -> None:
        """Verify BindPolicy enum values."""
        assert BindPolicy.LOCALHOST_ONLY.value == "LOCALHOST_ONLY"
        assert BindPolicy.ALL_INTERFACES.value == "ALL_INTERFACES"
>       assert BindPolicy.CUSTOM_IP.value == "CUSTOM_IP"
               ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'BindPolicy' has no attribute 'CUSTOM_IP'. Did you mean: 'CUSTOM'?

test_suite\test_cochem_setup_phase_8.py:109: AttributeError
____________________ test_port_binding_profile_validation _____________________

    def test_port_binding_profile_validation() -> None:
        """Test PortBindingProfile model validation, constraints, and extra field rejection."""
        profile = PortBindingProfile(
>           service=GatewayServiceType.DOCK_REST_API,
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            protocol=ProtocolType.TCP,
            requested_port=8000,
            allocated_port=8000,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
            url="http://127.0.0.1:8000",
        )
E       AttributeError: type object 'GatewayServiceType' has no attribute 'DOCK_REST_API'

test_suite\test_cochem_setup_phase_8.py:120: AttributeError
___________________ test_gateway_config_profile_validation ____________________

    def test_gateway_config_profile_validation() -> None:
        """Test GatewayConfigProfile validation and nested models."""
        dock = PortBindingProfile(
>           service=GatewayServiceType.DOCK_REST_API,
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            protocol=ProtocolType.TCP,
            requested_port=8000,
            allocated_port=8000,
            bind_host="127.0.0.1",
            is_bound_successfully=True,
            is_conflict_resolved=False,
            environment_variable="COCHEM_DOCK_PORT",
            url="http://127.0.0.1:8000",
        )
E       AttributeError: type object 'GatewayServiceType' has no attribute 'DOCK_REST_API'

test_suite\test_cochem_setup_phase_8.py:179: AttributeError
______________ test_phase_8_audit_report_roundtrip_serialization ______________

    def test_phase_8_audit_report_roundtrip_serialization() -> None:
        """Test Phase8AuditReport serialization and deserialization roundtrip."""
        with make_temp_dir() as tmpdir:
            art_path = Path(tmpdir) / "p8.json"
            dock = PortBindingProfile(
>               service=GatewayServiceType.DOCK_REST_API,
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                protocol=ProtocolType.TCP,
                requested_port=8000,
                allocated_port=8000,
                bind_host="127.0.0.1",
                is_bound_successfully=True,
                is_conflict_resolved=False,
                environment_variable="COCHEM_DOCK_PORT",
                url="http://127.0.0.1:8000",
            )
E           AttributeError: type object 'GatewayServiceType' has no attribute 'DOCK_REST_API'

test_suite\test_cochem_setup_phase_8.py:242: AttributeError
________________ test_probe_port_availability_real_tcp_socket _________________

    def test_probe_port_availability_real_tcp_socket() -> None:
        """Test TCP port probing on free vs occupied real sockets."""
        # Find an open port first
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
    
        # Free port should return True
>       assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.TCP) is True
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: probe_port_availability() got multiple values for argument 'host'

test_suite\test_cochem_setup_phase_8.py:330: TypeError
________________ test_probe_port_availability_real_udp_socket _________________

    def test_probe_port_availability_real_udp_socket() -> None:
        """Test UDP port probing on free vs occupied real sockets."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
    
>       assert probe_port_availability(free_port, host="127.0.0.1", protocol=ProtocolType.UDP) is True
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: probe_port_availability() got multiple values for argument 'host'

test_suite\test_cochem_setup_phase_8.py:349: TypeError
___________________ test_allocate_port_preferred_available ____________________

    def test_allocate_port_preferred_available() -> None:
        """Test port allocation when preferred port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
    
>       allocated, resolved = allocate_port(
        ^^^^^^^^^^^^^^^^^^^
            preferred_port=free_port,
            port_range=(free_port, free_port + 10),
            host="127.0.0.1",
            protocol=ProtocolType.TCP,
        )
E       TypeError: cannot unpack non-iterable int object

test_suite\test_cochem_setup_phase_8.py:370: TypeError
__________ test_allocate_port_conflict_resolution_with_active_socket __________

    def test_allocate_port_conflict_resolution_with_active_socket() -> None:
        """Test port allocation sequentially scans when preferred port is actively occupied."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
            s1.bind(("127.0.0.1", 0))
            base_port = s1.getsockname()[1]
    
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.bind(("127.0.0.1", base_port))
            blocker.listen(1)
    
            # Allocate starting from base_port; should scan to base_port + 1 or higher
>           allocated, resolved = allocate_port(
            ^^^^^^^^^^^^^^^^^^^
                preferred_port=base_port,
                port_range=(base_port, base_port + 20),
                host="127.0.0.1",
                protocol=ProtocolType.TCP,
            )
E           TypeError: cannot unpack non-iterable int object

test_suite\test_cochem_setup_phase_8.py:391: TypeError
___________________ test_allocate_port_with_excluded_ports ____________________

    def test_allocate_port_with_excluded_ports() -> None:
        """Test port allocation bypasses excluded ports."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
    
        excluded = {free_port, free_port + 1}
>       allocated, resolved = allocate_port(
        ^^^^^^^^^^^^^^^^^^^
            preferred_port=free_port,
            port_range=(free_port, free_port + 10),
            host="127.0.0.1",
            protocol=ProtocolType.TCP,
            excluded_ports=excluded,
        )
E       TypeError: cannot unpack non-iterable int object

test_suite\test_cochem_setup_phase_8.py:409: TypeError
_________________ test_allocate_all_gateway_services_defaults _________________

    def test_allocate_all_gateway_services_defaults() -> None:
        """Test default gateway allocation across all 4 services."""
>       profile = allocate_all_gateway_services(
            bind_host="127.0.0.1",
            allow_public_bind=False,
        )
E       TypeError: allocate_all_gateway_services() got an unexpected keyword argument 'bind_host'. Did you mean 'base_host'?

test_suite\test_cochem_setup_phase_8.py:439: TypeError
______________ test_allocate_all_gateway_services_env_overrides _______________

    def test_allocate_all_gateway_services_env_overrides() -> None:
        """Test environment variable overrides for gateway services."""
        env = {
            "COCHEM_DOCK_PORT": "8020",
            "COCHEM_GATEWAY_PORT": "5570",
            "COCHEM_UI_PORT": "8910",
            "COCHEM_TELEMETRY_PORT": "54330",
            "COCHEM_BIND_HOST": "127.0.0.1",
        }
>       profile = allocate_all_gateway_services(
            bind_host="127.0.0.1",
            env=env,
        )
E       TypeError: allocate_all_gateway_services() got an unexpected keyword argument 'bind_host'. Did you mean 'base_host'?

test_suite\test_cochem_setup_phase_8.py:466: TypeError
___________ test_allocate_all_gateway_services_collision_avoidance ____________

    def test_allocate_all_gateway_services_collision_avoidance() -> None:
        """Test that requesting identical ports for different services forces conflict resolution."""
>       profile = allocate_all_gateway_services(
            dock_port=8000,
            gateway_port=8000,  # Intentional collision with dock_port
            ui_port=8000,       # Intentional collision with dock_port
            telemetry_port=54321,
            bind_host="127.0.0.1",
        )
E       TypeError: allocate_all_gateway_services() got an unexpected keyword argument 'dock_port'

test_suite\test_cochem_setup_phase_8.py:478: TypeError
____________ test_allocate_all_gateway_services_public_bind_policy ____________

    def test_allocate_all_gateway_services_public_bind_policy() -> None:
        """Test public 0.0.0.0 binding policy when allow_public_bind is True vs False."""
        # When allow_public_bind is False, binding to 0.0.0.0 must degrade or default to 127.0.0.1
>       p_airgap = allocate_all_gateway_services(
            bind_host="0.0.0.0",
            allow_public_bind=False,
        )
E       TypeError: allocate_all_gateway_services() got an unexpected keyword argument 'bind_host'. Did you mean 'base_host'?

test_suite\test_cochem_setup_phase_8.py:498: TypeError
__________________ test_generate_environment_injection_dict ___________________

    def test_generate_environment_injection_dict() -> None:
        """Test generation of environment injection mapping dictionary."""
>       profile = allocate_all_gateway_services(
            dock_port=8000,
            gateway_port=5555,
            ui_port=8888,
            telemetry_port=54321,
            bind_host="127.0.0.1",
        )
E       TypeError: allocate_all_gateway_services() got an unexpected keyword argument 'dock_port'

test_suite\test_cochem_setup_phase_8.py:521: TypeError
___________________ test_resolve_p8_registry_path_override ____________________

    def test_resolve_p8_registry_path_override() -> None:
        """Test resolving p8.json path with override parameter."""
        with make_temp_dir() as tmpdir:
            target = Path(tmpdir) / "custom_p8.json"
            resolved = resolve_p8_registry_path(output_dir=target)
>           assert resolved == target.resolve()
E           AssertionError: assert WindowsPath('C:/Users/ansac/AppData/Local/Temp/tmp_gynx8qt/custom_p8.json/p8.json') == WindowsPath('C:/Users/ansac/AppData/Local/Temp/tmp_gynx8qt/custom_p8.json')
E            +  where WindowsPath('C:/Users/ansac/AppData/Local/Temp/tmp_gynx8qt/custom_p8.json') = resolve()
E            +    where resolve = WindowsPath('C:/Users/ansac/AppData/Local/Temp/tmp_gynx8qt/custom_p8.json').resolve

test_suite\test_cochem_setup_phase_8.py:546: AssertionError
_________________ test_resolve_p8_registry_path_env_hierarchy _________________

    def test_resolve_p8_registry_path_env_hierarchy() -> None:
        """Test resolving p8.json via environment variables."""
        with make_temp_dir() as tmpdir:
            env_reg = Path(tmpdir) / "reg_env"
            env1 = {"COCHEM_REGISTRY_DIR": str(env_reg)}
>           resolved1 = resolve_p8_registry_path(env=env1)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           TypeError: resolve_p8_registry_path() got an unexpected keyword argument 'env'

test_suite\test_cochem_setup_phase_8.py:558: TypeError
________________________ test_run_phase_8_audit_passed ________________________

    def test_run_phase_8_audit_passed() -> None:
        """Test run_phase_8_audit end-to-end execution resulting in PASSED status."""
        with make_temp_dir() as tmpdir:
            art_dir = Path(tmpdir) / "Registry"
>           report = run_phase_8_audit(
                output_dir=art_dir,
                bind_host="127.0.0.1",
            )
E           TypeError: run_phase_8_audit() got an unexpected keyword argument 'bind_host'. Did you mean 'base_host'?

test_suite\test_cochem_setup_phase_8.py:612: TypeError
_______________________ test_run_phase_8_audit_dry_run ________________________

    def test_run_phase_8_audit_dry_run() -> None:
        """Test run_phase_8_audit with dry_run=True does not create artifacts on disk."""
        with make_temp_dir() as tmpdir:
            art_dir = Path(tmpdir) / "Registry"
>           report = run_phase_8_audit(
                output_dir=art_dir,
                bind_host="127.0.0.1",
                dry_run=True,
            )
E           TypeError: run_phase_8_audit() got an unexpected keyword argument 'bind_host'. Did you mean 'base_host'?

test_suite\test_cochem_setup_phase_8.py:627: TypeError
__________________ test_run_phase_8_audit_custom_parameters ___________________

    def test_run_phase_8_audit_custom_parameters() -> None:
        """Test run_phase_8_audit with custom port overrides."""
        with make_temp_dir() as tmpdir:
            art_dir = Path(tmpdir) / "Registry"
>           report = run_phase_8_audit(
                output_dir=art_dir,
                dock_port=8040,
                gateway_port=5590,
                ui_port=8900,
                telemetry_port=54340,
                bind_host="127.0.0.1",
            )
E           TypeError: run_phase_8_audit() got an unexpected keyword argument 'dock_port'

test_suite\test_cochem_setup_phase_8.py:641: TypeError
_______________________ test_cli_main_success_and_help ________________________

capsys = <_pytest.capture.CaptureFixture object at 0x00000159BD1D3A10>

    def test_cli_main_success_and_help(capsys: pytest.CaptureFixture[str]) -> None:
        """Test main CLI entrypoint with argument passing and stdout."""
        with make_temp_dir() as tmpdir:
            out_dir = str(Path(tmpdir) / "Registry")
>           ret = main(["--output-dir", out_dir, "--bind-host", "127.0.0.1"])
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_cochem_setup_phase_8.py:660: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
orchestrator\cochem_setup_phase_8.py:642: in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\argparse.py:1902: in parse_args
    self.error(msg)
C:\Users\ansac\anaconda3\Lib\argparse.py:2658: in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = ArgumentParser(prog='pytest', usage=None, description='CoChem Setup Phase 8: Network Port Allocation & Gateway Gatekeeper.', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
status = 2
message = 'pytest: error: unrecognized arguments: --bind-host 127.0.0.1\n'

    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, _sys.stderr)
>       _sys.exit(status)
E       SystemExit: 2

C:\Users\ansac\anaconda3\Lib\argparse.py:2645: SystemExit
---------------------------- Captured stderr call -----------------------------
usage: pytest [-h] [--output-dir OUTPUT_DIR] [--host HOST]
              [--allow-public-bind] [--dock-port DOCK_PORT]
              [--studio-port STUDIO_PORT] [--hpc-bridge-port HPC_BRIDGE_PORT]
              [--telemetry-port TELEMETRY_PORT] [--swarm-port SWARM_PORT]
              [--dry-run] [--json]
pytest: error: unrecognized arguments: --bind-host 127.0.0.1
=========================== short test summary info ===========================
FAILED test_suite/test_cochem_setup_phase_8.py::test_gateway_service_type_enum
FAILED test_suite/test_cochem_setup_phase_8.py::test_bind_policy_enum - Attri...
FAILED test_suite/test_cochem_setup_phase_8.py::test_port_binding_profile_validation
FAILED test_suite/test_cochem_setup_phase_8.py::test_gateway_config_profile_validation
FAILED test_suite/test_cochem_setup_phase_8.py::test_phase_8_audit_report_roundtrip_serialization
FAILED test_suite/test_cochem_setup_phase_8.py::test_probe_port_availability_real_tcp_socket
FAILED test_suite/test_cochem_setup_phase_8.py::test_probe_port_availability_real_udp_socket
FAILED test_suite/test_cochem_setup_phase_8.py::test_allocate_port_preferred_available
FAILED test_suite/test_cochem_setup_phase_8.py::test_allocate_port_conflict_resolution_with_active_socket
FAILED test_suite/test_cochem_setup_phase_8.py::test_allocate_port_with_excluded_ports
FAILED test_suite/test_cochem_setup_phase_8.py::test_allocate_all_gateway_services_defaults
FAILED test_suite/test_cochem_setup_phase_8.py::test_allocate_all_gateway_services_env_overrides
FAILED test_suite/test_cochem_setup_phase_8.py::test_allocate_all_gateway_services_collision_avoidance
FAILED test_suite/test_cochem_setup_phase_8.py::test_allocate_all_gateway_services_public_bind_policy
FAILED test_suite/test_cochem_setup_phase_8.py::test_generate_environment_injection_dict
FAILED test_suite/test_cochem_setup_phase_8.py::test_resolve_p8_registry_path_override
FAILED test_suite/test_cochem_setup_phase_8.py::test_resolve_p8_registry_path_env_hierarchy
FAILED test_suite/test_cochem_setup_phase_8.py::test_run_phase_8_audit_passed
FAILED test_suite/test_cochem_setup_phase_8.py::test_run_phase_8_audit_dry_run
FAILED test_suite/test_cochem_setup_phase_8.py::test_run_phase_8_audit_custom_parameters
FAILED test_suite/test_cochem_setup_phase_8.py::test_cli_main_success_and_help
======================== 21 failed, 6 passed in 0.54s =========================

Error: 