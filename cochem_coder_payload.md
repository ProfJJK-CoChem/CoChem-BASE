Cycle 3: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SpycFit-ML\.in-progress\00_GLOBAL_SYSTEM_PROMPT.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0 -- C:\Users\ansac\anaconda3\python.exe
cachedir: .pytest_cache
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, hydra-core-1.3.5, typeguard-4.6.0, zarr-3.3.0
collecting ... collected 142 items

test_suite/test_calc_wsl.py::test_verify_wsl_kernel_env_vars PASSED      [  0%]
test_suite/test_calc_wsl.py::test_verify_wsl_kernel_platform_release PASSED [  1%]
test_suite/test_calc_wsl.py::test_verify_wsl_kernel_platform_version PASSED [  2%]
test_suite/test_calc_wsl.py::test_verify_wsl_kernel_not_wsl PASSED       [  2%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[mpirun (Open MPI) 4.1.2\nReport bugs to...-4.1.2] PASSED [  3%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[mpirun (Open MPI) 4.1.6\n-4.1.6] PASSED [  4%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[mpirun (Open MPI) v4.1.2\n-4.1.2] PASSED [  4%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[Open MPI: 4.1.2\n-4.1.2] PASSED [  5%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[Open MPI 4.1.2a1\n-4.1.2] PASSED [  6%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[mpirun (Open MPI) 5.0.3\n-5.0.3] PASSED [  7%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[v4.1.2\n-4.1.2] PASSED [  7%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[v4.1\n-4.1] PASSED [  8%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_formats[mpirun 4.1.2\n-4.1.2] PASSED [  9%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_parse_failure PASSED [  9%]
test_suite/test_calc_wsl.py::test_check_openmpi_version_subprocess_errors PASSED [ 10%]
test_suite/test_calc_wsl.py::test_provision_openmpi_found PASSED         [ 11%]
test_suite/test_calc_wsl.py::test_provision_openmpi_install_flow PASSED  [ 11%]
test_suite/test_calc_wsl.py::test_available_executable PASSED            [ 12%]
test_suite/test_calc_wsl.py::test_safe_extract_zip_valid_and_invalid PASSED [ 13%]
test_suite/test_calc_wsl.py::test_safe_extract_tar_with_relative_symlinks_and_hardlinks PASSED [ 14%]
test_suite/test_calc_wsl.py::test_safe_extract_tar_rejects_unsafe_symlinks PASSED [ 14%]
test_suite/test_calc_wsl.py::test_safe_extract_tar_rejects_absolute_symlinks PASSED [ 15%]
test_suite/test_calc_wsl.py::test_safe_extract_tar_rejects_unsafe_hardlinks PASSED [ 16%]
test_suite/test_calc_wsl.py::test_locate_orca_with_tar_archives[orca-6.1.1.tar.gz-w:gz] PASSED [ 16%]
test_suite/test_calc_wsl.py::test_locate_orca_with_tar_archives[ORCA-6.1.1.tar.bz2-w:bz2] PASSED [ 17%]
test_suite/test_calc_wsl.py::test_locate_orca_with_tar_archives[orca-6.1.1.tar.xz-w:xz] PASSED [ 18%]
test_suite/test_calc_wsl.py::test_locate_orca_with_tar_archives[orca-6.1.1.tar-w:] PASSED [ 19%]
test_suite/test_calc_wsl.py::test_locate_orca_with_tar_archives[orca-6.1.1.tgz-w:gz] PASSED [ 19%]
test_suite/test_calc_wsl.py::test_locate_orca_with_zip_archive PASSED    [ 20%]
test_suite/test_calc_wsl.py::test_provision_orca_missing_raises PASSED   [ 21%]
test_suite/test_calc_wsl.py::test_register_calculation_state_full_remediation PASSED [ 21%]
test_suite/test_calc_wsl.py::test_register_calculation_state_flexible_signatures PASSED [ 22%]
test_suite/test_calc_wsl.py::test_register_calculation_state_with_enginepaths_model PASSED [ 23%]
test_suite/test_calc_wsl.py::test_verify_wsl_kernel_uname PASSED         [ 23%]
test_suite/test_calc_wsl.py::test_verify_wsl_kernel_proc_file PASSED     [ 24%]
test_suite/test_calc_wsl.py::test_register_calculation_state_none_silo_and_hpc PASSED [ 25%]
test_suite/test_calc_wsl.py::test_cli_help_flag_handling PASSED          [ 26%]
test_suite/test_calc_wsl.py::test_run_calculation_setup_non_wsl_guard PASSED [ 26%]
test_suite/test_calc_wsl.py::test_cleanup_zombies_shielding PASSED       [ 27%]
test_suite/test_calc_wsl.py::test_calc_wsl_all_exports PASSED            [ 28%]
test_suite/test_ci_airgap_sweep.py::test_script_exists_and_lf_endings PASSED [ 28%]
test_suite/test_ci_airgap_sweep.py::test_shannon_entropy_calculation PASSED [ 29%]
test_suite/test_ci_airgap_sweep.py::test_restricted_extensions_detection PASSED [ 30%]
test_suite/test_ci_airgap_sweep.py::test_magic_number_detection PASSED   [ 30%]
test_suite/test_ci_airgap_sweep.py::test_qm_log_signatures_detection PASSED [ 31%]
test_suite/test_ci_airgap_sweep.py::test_xyz_coordinate_payload_detection PASSED [ 32%]
test_suite/test_ci_airgap_sweep.py::test_config_pollution_detection PASSED [ 33%]
test_suite/test_ci_airgap_sweep.py::test_clean_workspace_scan PASSED     [ 33%]
test_suite/test_ci_airgap_sweep.py::test_disguised_binary_detection_in_sweep PASSED [ 34%]
test_suite/test_ci_airgap_sweep.py::test_high_entropy_detection_in_sweep PASSED [ 35%]
test_suite/test_ci_airgap_sweep.py::test_cli_execution_clean PASSED      [ 35%]
test_suite/test_ci_airgap_sweep.py::test_cli_execution_violation PASSED  [ 36%]
test_suite/test_ci_airgap_sweep.py::test_cli_json_output PASSED          [ 37%]
test_suite/test_ci_airgap_sweep.py::test_default_entropy_threshold_constant PASSED [ 38%]
test_suite/test_ci_airgap_sweep.py::test_format_airgap_report PASSED     [ 38%]
test_suite/test_ci_airgap_sweep.py::test_restricted_directory_detection PASSED [ 39%]
test_suite/test_ci_airgap_sweep.py::test_invalid_repo_paths PASSED       [ 40%]
test_suite/test_cli_audit.py::TestCliParser::test_parser_creation PASSED [ 40%]
test_suite/test_cli_audit.py::TestCliParser::test_subcommand_presence PASSED [ 41%]
test_suite/test_cli_audit.py::TestCliParser::test_version_action PASSED  [ 42%]
test_suite/test_cli_audit.py::TestCliParser::test_no_args_returns_zero PASSED [ 42%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[1] PASSED [ 43%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[2] PASSED [ 44%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[3] PASSED [ 45%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[4] PASSED [ 45%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[5] PASSED [ 46%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[6] PASSED [ 47%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[7] PASSED [ 47%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[8] PASSED [ 48%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[9] PASSED [ 49%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[10] PASSED [ 50%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_load_all_valid_phases[11] PASSED [ 50%]
test_suite/test_cli_audit.py::TestCliPhaseLoading::test_invalid_phase_number PASSED [ 51%]
test_suite/test_cli_audit.py::TestCliPhaseExecution::test_execute_phase_1_dry_run PASSED [ 52%]
test_suite/test_cli_audit.py::TestCliPhaseExecution::test_execute_phase_2_dry_run PASSED [ 52%]
test_suite/test_cli_audit.py::TestCliPhaseExecution::test_execute_phase_3_dry_run PASSED [ 53%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_audit_json PASSED [ 54%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_status_json PASSED [ 54%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_mass_valid_element PASSED [ 55%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_mass_valid_isotope PASSED [ 56%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_mass_invalid_symbol PASSED [ 57%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_phase_direct PASSED [ 57%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_setup_subset_dry_run PASSED [ 58%]
test_suite/test_cli_audit.py::TestCliSubcommands::test_action_clean_json PASSED [ 59%]
test_suite/test_cli_audit.py::TestPackageExportParity::test_module_exports PASSED [ 59%]
test_suite/test_cochem_setup_phase_X.py::test_phase_status_enum_values PASSED [ 60%]
test_suite/test_cochem_setup_phase_X.py::test_silo_type_and_status_enums PASSED [ 61%]
test_suite/test_cochem_setup_phase_X.py::test_silo_config_valid PASSED   [ 61%]
test_suite/test_cochem_setup_phase_X.py::test_silo_config_invalid_name PASSED [ 62%]
test_suite/test_cochem_setup_phase_X.py::test_silo_config_invalid_python_version PASSED [ 63%]
test_suite/test_cochem_setup_phase_X.py::test_mendeleev_mass_record_valid PASSED [ 64%]
test_suite/test_cochem_setup_phase_X.py::test_mendeleev_mass_record_invalid_atomic_number PASSED [ 64%]
test_suite/test_cochem_setup_phase_X.py::test_dependency_manager_atomic_write_json PASSED [ 65%]
test_suite/test_cochem_setup_phase_X.py::test_dependency_manager_rollback_on_exception PASSED [ 66%]
test_suite/test_cochem_setup_phase_X.py::test_interrogate_host_os_live PASSED [ 66%]
test_suite/test_cochem_setup_phase_X.py::test_audit_wsl_mount_traps_live PASSED [ 67%]
test_suite/test_cochem_setup_phase_X.py::test_resolve_silo_base_directory_custom PASSED [ 68%]
test_suite/test_cochem_setup_phase_X.py::test_resolve_pX_registry_path_custom PASSED [ 69%]
test_suite/test_cochem_setup_phase_X.py::test_verify_mendeleev_authority_live PASSED [ 69%]
test_suite/test_cochem_setup_phase_X.py::test_execute_dynamic_version_walking_live PASSED [ 70%]
test_suite/test_cochem_setup_phase_X.py::test_get_native_stack_flags_and_env_vars PASSED [ 71%]
test_suite/test_cochem_setup_phase_X.py::test_inject_silo_stack_and_env_flags PASSED [ 71%]
test_suite/test_cochem_setup_phase_X.py::test_provision_micro_silo_dry_run PASSED [ 72%]
test_suite/test_cochem_setup_phase_X.py::test_phase_x_driver_execution_dry_run PASSED [ 73%]
test_suite/test_cochem_setup_phase_X.py::test_run_phase_x_audit_callable_with_persistence PASSED [ 73%]
test_suite/test_cochem_setup_phase_X.py::test_main_cli_dry_run_and_json PASSED [ 74%]
test_suite/test_main_window.py::test_main_window_file_encoding_and_lf_line_endings FAILED [ 75%]
test_suite/test_main_window.py::test_main_window_zero_personal_path_leaks PASSED [ 76%]
test_suite/test_main_window.py::test_main_window_docstrings_and_module_overview FAILED [ 76%]
test_suite/test_main_window.py::test_main_window_exports_and_all FAILED  [ 77%]
test_suite/test_main_window.py::test_workspace_state_validation PASSED   [ 78%]
test_suite/test_main_window.py::test_main_window_initialization PASSED   [ 78%]
test_suite/test_main_window.py::test_main_window_programmatic_serialization_and_deserialization FAILED [ 79%]
test_suite/test_main_window.py::test_main_window_deserialization_error_handling FAILED [ 80%]
test_suite/test_main_window.py::test_main_window_close_event_resource_cleanup FAILED [ 80%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLSchema::test_hardware_tier_enum PASSED [ 81%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLSchema::test_hardware_resource_limits PASSED [ 82%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLSchema::test_tripartite_workspace_config_resolution PASSED [ 83%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLSchema::test_dynamic_isotope_record_mendeleev PASSED [ 83%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLSchema::test_fit_state_commit_schema_hash_and_immutability PASSED [ 84%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLSchema::test_provenance_ledger_entry PASSED [ 85%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLSchema::test_spycfit_ml_config_defaults PASSED [ 85%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLEngine::test_discover_hardware_hierarchy PASSED [ 86%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLEngine::test_compute_rigid_rotor_frequencies_water PASSED [ 87%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLEngine::test_compute_rigid_rotor_frequencies_so2 PASSED [ 88%]
tests/test_cochem_spycfit_ml.py::TestSpycFitMLEngine::test_compute_analytical_jacobian PASSED [ 88%]
tests/test_cochem_spycfit_ml.py::TestGaussianProcessSpectralRegressor::test_gp_feature_extraction PASSED [ 89%]
tests/test_cochem_spycfit_ml.py::TestGaussianProcessSpectralRegressor::test_gp_fit_and_predict PASSED [ 90%]
tests/test_cochem_spycfit_ml.py::TestGaussianProcessSpectralRegressor::test_gp_tag_predictions PASSED [ 90%]
tests/test_cochem_spycfit_ml.py::TestDualEngineParityBridge::test_parity_passed_within_tolerance PASSED [ 91%]
tests/test_cochem_spycfit_ml.py::TestDualEngineParityBridge::test_parity_warning_triggered_exceeding_threshold PASSED [ 92%]
tests/test_cochem_spycfit_ml.py::TestSmartScanNavigator::test_information_gain_calculation PASSED [ 92%]
tests/test_cochem_spycfit_ml.py::TestSmartScanNavigator::test_resolvability_filter PASSED [ 93%]
tests/test_cochem_spycfit_ml.py::TestSmartScanNavigator::test_rank_scan_windows PASSED [ 94%]
tests/test_cochem_spycfit_ml.py::TestSpycFitHDF5StorageAndSandbox::test_ephemeral_sandbox_lifecycle PASSED [ 95%]
tests/test_cochem_spycfit_ml.py::TestSpycFitHDF5StorageAndSandbox::test_recover_zombie_locks PASSED [ 95%]
tests/test_cochem_spycfit_ml.py::TestSpycFitHDF5StorageAndSandbox::test_hdf5_swmr_state_persistence_and_retrieval PASSED [ 96%]
tests/test_cochem_spycfit_ml.py::TestSpycFitHDF5StorageAndSandbox::test_hdf5_tensor_dataset_persistence PASSED [ 97%]
tests/test_cochem_spycfit_ml.py::TestDAGCommitManager::test_dag_commit_and_lineage_history PASSED [ 97%]
tests/test_cochem_spycfit_ml.py::TestDAGCommitManager::test_dag_time_travel_reversion PASSED [ 98%]
tests/test_cochem_spycfit_ml.py::TestCoChemBaseProxyIntegration::test_cochem_base_submodule_proxy_imports PASSED [ 99%]
tests/test_cochem_spycfit_ml.py::TestCoChemBaseProxyIntegration::test_cochem_base_getattr_resolution PASSED [100%]

================================== FAILURES ===================================
_____________ test_main_window_file_encoding_and_lf_line_endings ______________

main_window_py_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/gui/main_window.py')

    def test_main_window_file_encoding_and_lf_line_endings(main_window_py_path: Path) -> None:
        """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
        raw = main_window_py_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in gui/main_window.py"
E       AssertionError: Found Windows CRLF (\r\n) line endings in gui/main_window.py
E       assert b'\r\n' not in b'import json\r\n\r\nfrom pydantic import BaseModel, ValidationError\r\nfrom PySide6.QtCore import Qt\r\nfrom PySide6.QtGui import QAction\r\nfrom PySide6.QtWidgets import QFileDialog, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget\r\n\r\nfrom cochem_base.config_loader import get_artifact_dir\r\nfrom cochem_base.gui.scribe import ScribeDock\r\nfrom cochem_base.plugins.internal import CorePlugin\r\nfrom cochem_base.plugins.loader import get_plugin_manager\r\n\r\n\r\nclass WorkspaceState(BaseModel):\r\n    version: str\r\n    cochem_base: str\r\n    tabs: list[str]\r\n    active_tab_index: int\r\n\r\n\r\nclass MainWindow(QMainWindow):\r\n    def __init__(self) -> None:\r\n        super().__init__()\r\n        self.setWindowTitle("CoChem-Studio")\r\n        self.resize(1024, 768)\r\n\r\n        self.setup_menu()\r\n\r\n        # Central Tab Widget\r\n        self.tabs = QTabWidget()\r\n        self.setCentralWidget(self.tabs)\r\n\r\n        # Bottom Dock for SCRIBE (Logging Console)\r\n        self.scribe_dock = ScribeDock(self)\r\n        self.addDockWidget(Qt.BottomDockWidgetArea, self.scribe_dock)  # type: ignore\r\n\r\n        # Initialize plugin manager\r\n        self.p...OSError: {e}")\r\n\r\n    def deserialize_state(self) -> None:\r\n        workspace_dir = get_artifact_dir() / "Workspaces"\r\n        workspace_dir.mkdir(parents=True, exist_ok=True)\r\n        file_path, _ = QFileDialog.getOpenFileName(self, "Load Workspace", str(workspace_dir), "JSON Files (*.json)")\r\n        if file_path:\r\n            try:\r\n                with open(file_path, "r", encoding="utf-8") as f:\r\n                    data = json.load(f)\r\n                \r\n                state = WorkspaceState(**data)\r\n                \r\n                if 0 <= state.active_tab_index < self.tabs.count():\r\n                    self.tabs.setCurrentIndex(state.active_tab_index)\r\n                \r\n                self.scribe_dock.log(f"Workspace loaded from {file_path}")\r\n            except OSError as e:\r\n                self.scribe_dock.log(f"Failed to load workspace: OSError: {e}")\r\n            except json.JSONDecodeError as e:\r\n                self.scribe_dock.log(f"Failed to load workspace: JSON Decode Error: {e}")\r\n            except ValidationError as e:\r\n                self.scribe_dock.log(f"Failed to load workspace: Invalid State Format: {e}")\r\n'

test_suite\test_main_window.py:64: AssertionError
_______________ test_main_window_docstrings_and_module_overview _______________

    def test_main_window_docstrings_and_module_overview() -> None:
        """Verify comprehensive architectural docstrings on module, classes, and methods."""
        # Module docstring
        mod_doc = main_window_mod.__doc__
>       assert mod_doc is not None and len(mod_doc) > 50
E       assert (None is not None)

test_suite\test_main_window.py:94: AssertionError
______________________ test_main_window_exports_and_all _______________________

    def test_main_window_exports_and_all() -> None:
        """Verify __all__ is complete and accurately reflects public symbols."""
>       assert hasattr(main_window_mod, "__all__")
E       AssertionError: assert False
E        +  where False = hasattr(main_window_mod, '__all__')

test_suite\test_main_window.py:117: AssertionError
_______ test_main_window_programmatic_serialization_and_deserialization _______

qapp = <PySide6.QtWidgets.QApplication(0x2b6dbbffee0) at 0x000002B6E2FEAE80>
tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-12800/test_main_window_programmatic_0')

    def test_main_window_programmatic_serialization_and_deserialization(
        qapp: QApplication, tmp_path: Path
    ) -> None:
        """Verify serialize_state and deserialize_state with explicit file_path bypass QFileDialog."""
        window = MainWindow()
        target_json = tmp_path / "saved_workspace.json"
    
        try:
            # Set active tab to TORQ (index 2)
            window.tabs.setCurrentIndex(2)
            assert window.tabs.currentIndex() == 2
    
            # 1. Programmatic serialization
>           saved_path = window.serialize_state(file_path=target_json)
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           TypeError: MainWindow.serialize_state() got an unexpected keyword argument 'file_path'

test_suite\test_main_window.py:205: TypeError
_______________ test_main_window_deserialization_error_handling _______________

qapp = <PySide6.QtWidgets.QApplication(0x2b6dbbffee0) at 0x000002B6E2FEAE80>
tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-12800/test_main_window_deserializati0')

    def test_main_window_deserialization_error_handling(
        qapp: QApplication, tmp_path: Path
    ) -> None:
        """Verify deserialize_state handles missing, invalid JSON, and bad schema files gracefully."""
        window = MainWindow()
        try:
            # 1. Non-existent file
            missing_file = tmp_path / "non_existent.json"
>           assert window.deserialize_state(file_path=missing_file) is None
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           TypeError: MainWindow.deserialize_state() got an unexpected keyword argument 'file_path'

test_suite\test_main_window.py:249: TypeError
________________ test_main_window_close_event_resource_cleanup ________________

qapp = <PySide6.QtWidgets.QApplication(0x2b6dbbffee0) at 0x000002B6E2FEAE80>

    def test_main_window_close_event_resource_cleanup(qapp: QApplication) -> None:
        """Verify closeEvent invokes cleanup/close on child tabs and restores sys streams."""
        orig_stdout = sys.__stdout__
        orig_stderr = sys.__stderr__
    
        window = MainWindow()
    
        # Add custom tracking tab
        tracker_tab = CleanupTrackingTab()
        window.tabs.addTab(tracker_tab, "Tracking Tab")
    
        # Verify Scribe redirected sys.stdout
        assert isinstance(sys.stdout, OutputStream)
        assert isinstance(sys.stderr, OutputStream)
    
        # Trigger window closure
        close_event = QCloseEvent()
        window.closeEvent(close_event)
    
        # Verify tracking tab cleanup was called
>       assert tracker_tab.cleanup_called is True
E       assert False is True
E        +  where False = <test_suite.test_main_window.CleanupTrackingTab(0x2b6ddf65cf0) at 0x000002B6DED0C3C0>.cleanup_called

test_suite\test_main_window.py:305: AssertionError
=========================== short test summary info ===========================
FAILED test_suite/test_main_window.py::test_main_window_file_encoding_and_lf_line_endings
FAILED test_suite/test_main_window.py::test_main_window_docstrings_and_module_overview
FAILED test_suite/test_main_window.py::test_main_window_exports_and_all - Ass...
FAILED test_suite/test_main_window.py::test_main_window_programmatic_serialization_and_deserialization
FAILED test_suite/test_main_window.py::test_main_window_deserialization_error_handling
FAILED test_suite/test_main_window.py::test_main_window_close_event_resource_cleanup
======================= 6 failed, 136 passed in 14.90s ========================

Error: 