Cycle 10: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc1_08_start_here_notebook_prompt.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0
collected 1872 items

test_fix_exceptions.py .............                                     [  0%]
test_fix_prints.py ...............                                       [  1%]
test_fix_scripts.py ..............                                       [  2%]
test_fix_scripts2.py ................                                    [  3%]
test_suite\test_adversarial_hashing.py ................................. [  4%]
...                                                                      [  5%]
test_suite\test_agent_artist_spec.py ...FF                               [  5%]
test_suite\test_agent_audit_spec.py .F.FF                                [  5%]
test_suite\test_agent_coder_spec.py .F.FF                                [  5%]
test_suite\test_agent_debug_spec.py ....F                                [  6%]
test_suite\test_agent_educator_spec.py .F.FF                             [  6%]
test_suite\test_agent_helper_spec.py ...F.                               [  6%]
test_suite\test_agent_improve_spec.py .....                              [  6%]
test_suite\test_agent_orchestrator_spec.py .F.FFF                        [  7%]
test_suite\test_agent_researcher_spec.py .....                           [  7%]
test_suite\test_agent_scribe_spec.py .....                               [  7%]
test_suite\test_agent_sdp_manager_spec.py ...FF                          [  8%]
test_suite\test_agent_teacher_spec.py .F.F.                              [  8%]
test_suite\test_agent_tester_spec.py ...F.                               [  8%]
test_suite\test_airgap_trap.py ..................                        [  9%]
test_suite\test_anti_spoof_amnesty.py ..........                         [ 10%]
test_suite\test_atomic_data.py ...F.............                         [ 10%]
test_suite\test_auto_version_bump.py ................................    [ 12%]
test_suite\test_ci_cd_workflow.py ............................           [ 14%]
test_suite\test_citations_generator.py .............                     [ 14%]
test_suite\test_cochem_core_job_manager.py FFFFFFFFFFFFFFF               [ 15%]
test_suite\test_cochem_core_registry_manager.py .............            [ 16%]
test_suite\test_cochem_core_registry_schema.py ......................... [ 17%]
                                                                         [ 17%]
test_suite\test_cochem_core_subprocess_broker.py .........FFFFFFFF       [ 18%]
test_suite\test_cochem_core_telemetry_logger.py ..F..........            [ 19%]
test_suite\test_cochem_core_workspace_manager.py .FFFFFF                 [ 19%]
test_suite\test_cochem_dock_main.py F........F........                   [ 20%]
test_suite\test_cochem_dock_visuals_api.py F.F......FFFF....F.F.F        [ 21%]
test_suite\test_cochem_mint_ingestor.py ......FF..F.........             [ 22%]
test_suite\test_cochem_unity_installer_dashboard.py ............         [ 23%]
test_suite\test_core_registry_schema.py ...........                      [ 24%]
test_suite\test_deployment_manifest.py ....................              [ 25%]
test_suite\test_fast_pass_widget.py ......................               [ 26%]
test_suite\test_fix_exceptions.py .................                      [ 27%]
test_suite\test_fix_prints.py ...............                            [ 28%]
test_suite\test_fix_scripts.py ..............                            [ 28%]
test_suite\test_fix_scripts2.py ................                         [ 29%]
test_suite\test_forensic_check.py .F.........F                           [ 30%]
test_suite\test_gitignore_comprehensive.py ............................. [ 31%]
.................................                                        [ 33%]
test_suite\test_headless_run.py ......................                   [ 34%]
test_suite\test_hpc_dispatcher.py ...........                            [ 35%]
test_suite\test_interfaces_init.py ..FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.F    [ 37%]
test_suite\test_math_assertions.py F..........                           [ 37%]
test_suite\test_math_autograd.py F.......F.F..                           [ 38%]
test_suite\test_math_c_bindings.py F.FF.FFFFFFFF                         [ 39%]
test_suite\test_math_geometry.py F.....FFFFF.............                [ 40%]
test_suite\test_math_init.py F.FF.........F.....                         [ 41%]
test_suite\test_molecule_definition.py ..............                    [ 42%]
test_suite\test_plugins_init.py F.FFFFFFF.FFF                            [ 42%]
test_suite\test_plugins_internal.py F.F.........                         [ 43%]
test_suite\test_plugins_loader.py F.F...............                     [ 44%]
test_suite\test_pre_commit_config.py ........                            [ 44%]
test_suite\test_protonation_states.py ...................                [ 45%]
test_suite\test_provenance_hashing.py ...                                [ 46%]
test_suite\test_pyproject_toml.py .............                          [ 46%]
test_suite\test_readme.py ...............                                [ 47%]
test_suite\test_requirements_txt.py .................................... [ 49%]
......                                                                   [ 49%]
test_suite\test_run_tests.py FF......F.                                  [ 50%]
test_suite\test_sentinel_briefing_spec.py .F..                           [ 50%]
test_suite\test_sentinel_handoff_spec.py ...FFFFFFFFF.                   [ 51%]
test_suite\test_sequence_parsing.py ...............                      [ 52%]
test_suite\test_silo_setup_pass2.py F                                    [ 52%]
test_suite\test_start_here_notebook.py ..................                [ 53%]
test_suite\test_teamwork_preview_auditor_1_audit_spec.py ..FFF.FF        [ 53%]
test_suite\test_teamwork_preview_auditor_1_briefing_spec.py .F.F         [ 53%]
test_suite\test_teamwork_preview_auditor_1_dispatch_spec.py .FFF         [ 53%]
test_suite\test_thermo_constants.py F........F...                        [ 54%]
test_suite\test_topology.py ...........                                  [ 55%]
test_suite\test_torq_gui.py ..............F.F......                      [ 56%]
test_suite\test_web_matrices.py F.FFFFFFFFFFFFFFF.FFFFFFFFFFFFFFFFFFFFFF [ 58%]
FFFFFFFFFFF                                                              [ 59%]
test_suite\test_web_streaming.py .......................F...             [ 60%]
tests\test_airgap_trap.py ..................                             [ 61%]
tests\test_airgap_unit.py ............                                   [ 62%]
tests\test_antigravity_ask_codespaces_hpc.py ..                          [ 62%]
tests\test_antigravity_signin_codespaces_hpc.py ....                     [ 62%]
tests\test_artist_refactor.py ....FFFFF                                  [ 63%]
tests\test_briefing_refactor.py ....F...                                 [ 63%]
tests\test_ci_cd_workflow.py ............................                [ 64%]
tests\test_citations.py ..                                               [ 65%]
tests\test_cochem_audit_refactor.py ....FFF                              [ 65%]
tests\test_cochem_coder_refactor.py ....FFFFFFF                          [ 66%]
tests\test_cochem_debug_refactor.py .........                            [ 66%]
tests\test_cochem_dock_visuals_api.py ...................                [ 67%]
tests\test_cochem_helper_refactor.py .....FF...F.                        [ 68%]
tests\test_cochem_improve_refactor.py ........                           [ 68%]
tests\test_cochem_scribe_refactor.py ......F.F.FF                        [ 69%]
tests\test_cochem_tester_refactor.py ..........                          [ 69%]
tests\test_config_loader_comprehensive.py .............................. [ 71%]
.......................                                                  [ 72%]
tests\test_deployment_manifest.py ....................                   [ 73%]
tests\test_dispatch_refactor.py ....FFFFFFF                              [ 74%]
tests\test_e2e_local_unit.py ..................FF...F......F.....FFFF..F [ 76%]
....                                                                     [ 76%]
tests\test_educator_refactor.py .....FFFFF.F                             [ 77%]
tests\test_exceptions.py ............................................... [ 79%]
...................                                                      [ 80%]
tests\test_gate_status_refactor.py ...............                       [ 81%]
tests\test_gc_sweep_unit.py ...................                          [ 82%]
tests\test_generate_blueprint.py ...............                         [ 83%]
tests\test_gitignore.py ................................................ [ 86%]
.......                                                                  [ 86%]
tests\test_handoff_refactor.py ...FFFFFFFFF                              [ 87%]
tests\test_matrix_dashboard_keep_codespaces_actions.py .                 [ 87%]
tests\test_matrix_dashboard_keep_codespaces_hpc.py .                     [ 87%]
tests\test_matrix_dashboard_new_codespaces_actions.py .                  [ 87%]
tests\test_matrix_dashboard_new_codespaces_hpc.py .                      [ 87%]
tests\test_method_matrix_refactor.py E.EFE.E.EFEFE.E.EFE.                [ 88%]
tests\test_old_plan_method_matrix.py EEEEEEEEEEEE                        [ 89%]
tests\test_original_request_refactor.py ........                         [ 89%]
tests\test_path_sanitization_comprehensive.py ................           [ 90%]
tests\test_pre_commit_config.py ........                                 [ 90%]
tests\test_progress_refactor.py .....FFFF.F....                          [ 91%]
tests\test_project_refactor.py ...FFFFFFFFF                              [ 92%]
tests\test_provenance_hashing.py .................                       [ 93%]
tests\test_pyproject_toml.py .............                               [ 93%]
tests\test_readme.py ...............                                     [ 94%]
tests\test_requirements_txt.py ......................................... [ 96%]
.                                                                        [ 96%]
tests\test_sentinel_handoff_refactor.py ...FFFFFFFFF.                    [ 97%]
tests\test_silo_setup_keep_codespaces_hpc.py .                           [ 97%]
tests\test_silo_setup_new_codespaces_hpc.py .                            [ 97%]
tests\test_start_here_notebook.py ..................                     [ 98%]
tests\test_teacher_refactor.py ....FFF..                                 [ 99%]
tests\test_teamwork_preview_auditor_handoff_refactor.py ...FFFF.FFFFF    [ 99%]
tests\test_ui_cell_3_keep_setup.py ..                                    [ 99%]
tests\test_ui_cell_3_keep_setup_integration.py ..                        [100%]

=================================== ERRORS ====================================
_______ ERROR at setup of test_file_exists_and_non_empty[target_file0] ________

request = <SubRequest 'target_file' for <Function test_file_exists_and_non_empty[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
__________ ERROR at setup of test_unix_lf_line_endings[target_file0] __________

request = <SubRequest 'target_file' for <Function test_unix_lf_line_endings[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
__________ ERROR at setup of test_utf8_encoding_no_bom[target_file0] __________

request = <SubRequest 'target_file' for <Function test_utf8_encoding_no_bom[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
________ ERROR at setup of test_zero_personal_path_leaks[target_file0] ________

request = <SubRequest 'target_file' for <Function test_zero_personal_path_leaks[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
_____ ERROR at setup of test_no_hardcoded_linux_user_paths[target_file0] ______

request = <SubRequest 'target_file' for <Function test_no_hardcoded_linux_user_paths[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
________ ERROR at setup of test_canonical_tokens_present[target_file0] ________

request = <SubRequest 'target_file' for <Function test_canonical_tokens_present[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
__ ERROR at setup of test_clean_markdown_no_raw_directive_xml[target_file0] ___

request = <SubRequest 'target_file' for <Function test_clean_markdown_no_raw_directive_xml[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
___________ ERROR at setup of test_code_fence_balance[target_file0] ___________

request = <SubRequest 'target_file' for <Function test_code_fence_balance[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
________ ERROR at setup of test_primary_sections_present[target_file0] ________

request = <SubRequest 'target_file' for <Function test_primary_sections_present[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
_ ERROR at setup of test_provenance_and_method_matrix_invariants[target_file0] _

request = <SubRequest 'target_file' for <Function test_provenance_and_method_matrix_invariants[target_file0]>>

    @pytest.fixture(params=[
        Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
        get_base_root() / "Method_Matrix.md",
    ])
    def target_file(request: pytest.FixtureRequest) -> Path:
        target: Path = request.param
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20260810_docs/Copy of Method_Matrix.md').exists

tests\test_method_matrix_refactor.py:28: AssertionError
______________ ERROR at setup of test_file_exists_and_non_empty _______________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_________________ ERROR at setup of test_unix_lf_line_endings _________________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_________________ ERROR at setup of test_utf8_encoding_no_bom _________________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_______________ ERROR at setup of test_zero_personal_path_leaks _______________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
____________ ERROR at setup of test_no_hardcoded_linux_user_paths _____________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_______________ ERROR at setup of test_canonical_tokens_present _______________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_________ ERROR at setup of test_clean_markdown_no_raw_directive_xml __________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
__________________ ERROR at setup of test_code_fence_balance __________________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_______________ ERROR at setup of test_primary_sections_present _______________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_______ ERROR at setup of test_all_ten_domain_tables_present_and_valid ________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
_______ ERROR at setup of test_provenance_and_method_matrix_invariants ________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
__________ ERROR at setup of test_works_cited_citations_hyperlinked ___________

    @pytest.fixture
    def method_matrix_file() -> Path:
        """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
        target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
>       assert target.exists(), f"Target file does not exist at {target}"
E       AssertionError: Target file does not exist at D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('D:/__CoChem/GitHub-Repo/.old_plan_docs/20360805 Method Matrix .md').exists

tests\test_old_plan_method_matrix.py:23: AssertionError
================================== FAILURES ===================================
___________________ test_artist_mandatory_sections_present ____________________

artist_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/artist.agent.md')

    def test_artist_mandatory_sections_present(artist_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in artist.agent.md."""
        content = artist_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Native Image Generation",
            "## 2. External Prompt Crafting",
            "## 3. Negative Prompting",
            "## 4. Vector Graphics Preference",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# WHAT I DO NOT DO",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in artist.agent.md: {section}"
E           AssertionError: Missing required section in artist.agent.md: ## 2. External Prompt Crafting
E           assert '## 2. External Prompt Crafting' in "---\nname: artist\ndescription: Visual media agent. Generates images via native tools and crafts prompts for external...ication layouts (that is `ui`'s role).\n* Do not write backend computational code (that is `cochem-coder`'s role).\n\n"

test_suite\test_agent_artist_spec.py:94: AssertionError
____________________ test_artist_anti_spoofing_invariants _____________________

artist_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/artist.agent.md')

    def test_artist_anti_spoofing_invariants(artist_path: Path) -> None:
        """Validate that artist.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
        content = artist_path.read_text(encoding="utf-8")
    
        assert "generate_image" in content
        assert "SVG" in content or "svg" in content
        assert "PDF" in content or "pdf" in content
>       assert "MAX_META_PIVOT=3" in content
E       assert 'MAX_META_PIVOT=3' in "---\nname: artist\ndescription: Visual media agent. Generates images via native tools and crafts prompts for external...ication layouts (that is `ui`'s role).\n* Do not write backend computational code (that is `cochem-coder`'s role).\n\n"

test_suite\test_agent_artist_spec.py:104: AssertionError
_____________________ test_audit_yaml_frontmatter_schema ______________________

audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_audit_yaml_frontmatter_schema(audit_path: Path) -> None:
        """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
        content = audit_path.read_text(encoding="utf-8")
        match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert match is not None, "YAML frontmatter is missing or improperly delimited"
    
        fm = yaml.safe_load(match.group(1))
        assert isinstance(fm, dict), "Frontmatter must parse as a dictionary"
    
        required_keys = [
            "name",
            "description",
            "argument-hint",
            "enable_write_tools",
            "enable_subagent_tools",
            "enable_mcp_tools",
        ]
        for key in required_keys:
>           assert key in fm, f"Missing required frontmatter key: {key}"
E           AssertionError: Missing required frontmatter key: enable_subagent_tools
E           assert 'enable_subagent_tools' in {'argument-hint': 'a Python script to audit and refactor', 'description': 'Autonomous Quality Assurance, Code Standards, and Architectural Compliance agent.', 'enable_mcp_tools': True, 'enable_write_tools': True, ...}

test_suite\test_agent_audit_spec.py:47: AssertionError
____________________ test_audit_mandatory_sections_present ____________________

audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_audit_mandatory_sections_present(audit_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in cochem-audit.agent.md."""
        content = audit_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Registry Consistency & Air-Gap Enforcement",
            "## 2. Rigorous Typing & Linting",
            "## 3. Graceful Failure & Subprocess Safety",
            "## 4. Method Matrix Compliance",
            "## 5. Provenance & Integrity",
            "## 6. Root Cause Resolution (Anti-Band-Aid) Mandate",
            "# SWARM STATE MANAGEMENT PROTOCOL",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# WHAT I DO NOT DO",
            "# BEHAVIOR BOUNDARIES",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "<ROOT_CAUSE_MANDATE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in cochem-audit.agent.md: {section}"
E           AssertionError: Missing required section in cochem-audit.agent.md: ## 6. Root Cause Resolution (Anti-Band-Aid) Mandate
E           assert '## 6. Root Cause Resolution (Anti-Band-Aid) Mandate' in '---\nname: cochem-audit\ndescription: Autonomous Quality Assurance, Code Standards, and Architectural Compliance agen...` (max 3 bullets).\n2. Output the fully refactored, 100% complete Python script within a single `python` code block.\n'

test_suite\test_agent_audit_spec.py:105: AssertionError
_____________________ test_audit_anti_spoofing_invariants _____________________

audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_audit_anti_spoofing_invariants(audit_path: Path) -> None:
        """Validate that cochem-audit.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
        content = audit_path.read_text(encoding="utf-8")
    
>       assert "zero_trust_runner.py" in content
E       AssertionError: assert 'zero_trust_runner.py' in '---\nname: cochem-audit\ndescription: Autonomous Quality Assurance, Code Standards, and Architectural Compliance agen...` (max 3 bullets).\n2. Output the fully refactored, 100% complete Python script within a single `python` code block.\n'

test_suite\test_agent_audit_spec.py:112: AssertionError
_____________________ test_coder_yaml_frontmatter_schema ______________________

coder_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_coder_yaml_frontmatter_schema(coder_path: Path) -> None:
        """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
        content = coder_path.read_text(encoding="utf-8")
        match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert match is not None, "YAML frontmatter is missing or improperly delimited"
    
        fm = yaml.safe_load(match.group(1))
        assert isinstance(fm, dict), "Frontmatter must parse as a dictionary"
    
        required_keys = [
            "name",
            "description",
            "argument-hint",
            "enable_write_tools",
            "enable_subagent_tools",
            "enable_mcp_tools",
        ]
        for key in required_keys:
>           assert key in fm, f"Missing required frontmatter key: {key}"
E           AssertionError: Missing required frontmatter key: enable_subagent_tools
E           assert 'enable_subagent_tools' in {'argument-hint': 'a bug traceback to fix or a specific feature segment to implement', 'description': 'Autonomous iter...eature building agent. Strictly follows the Method Matrix.', 'enable_mcp_tools': True, 'enable_write_tools': True, ...}

test_suite\test_agent_coder_spec.py:47: AssertionError
____________________ test_coder_mandatory_sections_present ____________________

coder_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_coder_mandatory_sections_present(coder_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in cochem-coder.agent.md."""
        content = coder_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Method Matrix Execution & Quantum Chemistry Invariants",
            "## 2. Hardware & Workflow Efficiency",
            "## 3. Local Hardware Offloading & MCP Tool Utilization",
            "## 4. Sane Defaults, Cross-Platform Portability & Error Prevention",
            "## 5. The 20-Cycle Pivot Protocol & Immutability",
            "## 6. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in cochem-coder.agent.md: {section}"
E           AssertionError: Missing required section in cochem-coder.agent.md: ## 1. Method Matrix Execution & Quantum Chemistry Invariants
E           assert '## 1. Method Matrix Execution & Quantum Chemistry Invariants' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.'

test_suite\test_agent_coder_spec.py:98: AssertionError
_____________________ test_coder_anti_spoofing_invariants _____________________

coder_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_coder_anti_spoofing_invariants(coder_path: Path) -> None:
        """Validate that cochem-coder.agent.md incorporates critical anti-spoofing and zero-simulation protocols."""
        content = coder_path.read_text(encoding="utf-8")
    
>       assert "NEVER disable, delete, or comment out" in content or "NEVER disable/comment out" in content
E       AssertionError: assert ('NEVER disable, delete, or comment out' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.' or 'NEVER disable/comment out' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.')

test_suite\test_agent_coder_spec.py:105: AssertionError
_____________________ test_debug_anti_spoofing_invariants _____________________

debug_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-debug.agent.md')

    def test_debug_anti_spoofing_invariants(debug_path: Path) -> None:
        """Validate that cochem-debug.agent.md incorporates critical anti-spoofing and zero-simulation protocols."""
        content = debug_path.read_text(encoding="utf-8")
    
>       assert "NEVER disable, delete, or comment out" in content or "NEVER disable/comment out" in content
E       AssertionError: assert ('NEVER disable, delete, or comment out' in '---\nname: cochem-debug\ndescription: Developer troubleshooting agent. Isolates failures, performs diagnostic triage,...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n' or 'NEVER disable/comment out' in '---\nname: cochem-debug\ndescription: Developer troubleshooting agent. Isolates failures, performs diagnostic triage,...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n')

test_suite\test_agent_debug_spec.py:112: AssertionError
____________________ test_educator_yaml_frontmatter_schema ____________________

educator_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_educator_yaml_frontmatter_schema(educator_path: Path) -> None:
        """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
        content = educator_path.read_text(encoding="utf-8")
        match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert match is not None, "YAML frontmatter is missing or improperly delimited"
    
        fm = yaml.safe_load(match.group(1))
        assert isinstance(fm, dict), "Frontmatter must parse as a dictionary"
    
        required_keys = [
            "name",
            "description",
            "argument-hint",
            "enable_write_tools",
            "enable_subagent_tools",
            "enable_mcp_tools",
        ]
        for key in required_keys:
>           assert key in fm, f"Missing required frontmatter key: {key}"
E           AssertionError: Missing required frontmatter key: enable_subagent_tools
E           assert 'enable_subagent_tools' in {'argument-hint': 'Course planning, rubric creation, or assignment generation', 'description': 'Backend pedagogical ag...anning, and didactic Educational Experience & Scaffolding.', 'enable_mcp_tools': True, 'enable_write_tools': True, ...}

test_suite\test_agent_educator_spec.py:47: AssertionError
__________________ test_educator_mandatory_sections_present ___________________

educator_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_educator_mandatory_sections_present(educator_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in educator.agent.md."""
        content = educator_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Scientific Inquiry Frameworks (CER & SPARK)",
            "## 2. Bloom's Taxonomy Cognitive Escalation & Standards Alignment",
            "## 3. Friction by Design, Productive Struggle & Misconception Traps",
            "## 4. Automated Grading, Rubrics & AST Code Provenance Auditing",
            "## 5. Multidisciplinary STEM Didactics & Macroscopic-Microscopic Bridging",
            "## 6. Method Matrix v4 Compliance in Educational Artifacts",
            "## 7. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "<ROOT_CAUSE_MANDATE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in educator.agent.md: {section}"
E           AssertionError: Missing required section in educator.agent.md: ## 1. Scientific Inquiry Frameworks (CER & SPARK)
E           assert '## 1. Scientific Inquiry Frameworks (CER & SPARK)' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

test_suite\test_agent_educator_spec.py:106: AssertionError
___________________ test_educator_anti_spoofing_invariants ____________________

educator_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_educator_anti_spoofing_invariants(educator_path: Path) -> None:
        """Validate that educator.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
        content = educator_path.read_text(encoding="utf-8")
    
>       assert "zero_trust_runner.py" in content
E       AssertionError: assert 'zero_trust_runner.py' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

test_suite\test_agent_educator_spec.py:113: AssertionError
___________________ test_helper_mandatory_sections_present ____________________

helper_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-helper.agent.md')

    def test_helper_mandatory_sections_present(helper_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in cochem-helper.agent.md."""
        content = helper_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Method Matrix Enforcement & Quantum Chemistry Invariants",
            "## 2. Automating Rote Work & Pipeline Scaffolding",
            "## 3. Human-Readable Error Translations (User-Facing Triage)",
            "## 4. Publication Support & SI Package Standardization",
            "## 5. Local Hardware Offloading & MCP Tool Utilization",
            "## 6. Sane Defaults, Safe File Handling & Environment Portability",
            "## 7. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in cochem-helper.agent.md: {section}"
E           AssertionError: Missing required section in cochem-helper.agent.md: ## 1. Method Matrix Enforcement & Quantum Chemistry Invariants
E           assert '## 1. Method Matrix Enforcement & Quantum Chemistry Invariants' in '---\nname: cochem-helper\ndescription: Outward-facing assistant for CoChem users. Guides researchers through workflow...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

test_suite\test_agent_helper_spec.py:98: AssertionError
__________________ test_orchestrator_yaml_frontmatter_schema __________________

orchestrator_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/0rchestrator.agent.md')

    def test_orchestrator_yaml_frontmatter_schema(orchestrator_path: Path) -> None:
        """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
        content = orchestrator_path.read_text(encoding="utf-8")
        match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert match is not None, "YAML frontmatter is missing or improperly delimited"
    
        fm = yaml.safe_load(match.group(1))
        assert isinstance(fm, dict), "Frontmatter must parse as a dictionary"
    
        required_keys = [
            "name",
            "description",
            "argument-hint",
            "version",
            "domain",
            "routes_to",
            "enable_write_tools",
            "enable_subagent_tools",
            "enable_mcp_tools",
        ]
        for key in required_keys:
>           assert key in fm, f"Missing required frontmatter key: {key}"
E           AssertionError: Missing required frontmatter key: version
E           assert 'version' in {'argument-hint': 'A user goal or complex task to plan and orchestrate', 'description': 'Master orchestrator for all a...trix budgets, maintains state, and initiates the swarm.', 'enable_mcp_tools': True, 'enable_subagent_tools': True, ...}

test_suite\test_agent_orchestrator_spec.py:51: AssertionError
________________ test_orchestrator_mandatory_sections_present _________________

orchestrator_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/0rchestrator.agent.md')

    def test_orchestrator_mandatory_sections_present(orchestrator_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in 0rchestrator.agent.md."""
        content = orchestrator_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# 0RCHESTRATOR GLOBAL PROTOCOL",
            "# CORE DIRECTIVES & WORKFLOW ENGINE",
            "## 1. Deep Granularity & Work Breakdown Structure (WBS) Mandate",
            "## 2. The Vanguard Swarm Initialization",
            "## 3. Simple Task Short-Circuit",
            "## 4. Mandatory Task List Initialization & State Management",
            "## 5. Method Matrix v4 Tier Routing",
            "# SWARM TAXONOMY & SPECIALIST ROLES",
            "# PROACTIVE MCP AUTO-ACTIVATION MATRIX",
            "# SWARM STATE MANAGEMENT PROTOCOL",
            "# GLOBAL SWARM ANTI-HALLUCINATION & ZERO-MOCK DIRECTIVES",
            "# ANTI-SPOOFING PROTOCOL",
            "# SWARM ARCHITECTURE & DISTRIBUTED EXECUTION PROTOCOLS",
            "# SWARM AUTONOMY & HEADLESS EXECUTION MANDATE",
            "# THE \"EDIT-FIRST\" IN-PLACE MODIFICATION MANDATE",
            "# ADVERSARIAL AUDIT & 10-CYCLE DEBATE MANDATE",
            "# MANDATORY SUBAGENT GARBAGE COLLECTION",
            "# CONTEXT-AWARE CONFLICT RESOLUTION",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in 0rchestrator.agent.md: {section}"
E           AssertionError: Missing required section in 0rchestrator.agent.md: # 0RCHESTRATOR GLOBAL PROTOCOL
E           assert '# 0RCHESTRATOR GLOBAL PROTOCOL' in '---\nname: 0rchestrator\ndescription: Master orchestrator for all agent swarm tasks. Calls the vanguard agents (sdp_m...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

test_suite\test_agent_orchestrator_spec.py:105: AssertionError
_________________ test_orchestrator_anti_spoofing_invariants __________________

orchestrator_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/0rchestrator.agent.md')

    def test_orchestrator_anti_spoofing_invariants(orchestrator_path: Path) -> None:
        """Validate that 0rchestrator.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
        content = orchestrator_path.read_text(encoding="utf-8")
    
>       assert "zero_trust_runner.py" in content
E       AssertionError: assert 'zero_trust_runner.py' in '---\nname: 0rchestrator\ndescription: Master orchestrator for all agent swarm tasks. Calls the vanguard agents (sdp_m...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

test_suite\test_agent_orchestrator_spec.py:112: AssertionError
____________ test_orchestrator_briefing_encoding_and_sanitization _____________

    def test_orchestrator_briefing_encoding_and_sanitization() -> None:
        """Validate that .agents/orchestrator/BRIEFING.md is clean, properly encoded, and leak-free."""
        agents_dir = get_agents_dir()
        briefing_path = agents_dir / "orchestrator" / "BRIEFING.md"
        assert briefing_path.exists(), f"BRIEFING.md does not exist at {briefing_path}"
    
        raw_bytes = briefing_path.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "BRIEFING.md contains UTF-8 BOM"
        assert b"\r\n" not in raw_bytes, "BRIEFING.md contains Windows CRLF line endings"
    
        content = briefing_path.read_text(encoding="utf-8")
        patterns = leak_patterns()
    
        leaks = []
        for line_idx, line in enumerate(content.splitlines(), start=1):
            for pattern, label in patterns:
                if pattern.search(line):
                    leaks.append((line_idx, label, line.strip()))
    
        assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in BRIEFING.md: {leaks}"
        assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in BRIEFING.md"
        assert "<USER_HOME>" in content, "Expected <USER_HOME> placeholder token in BRIEFING.md"
>       assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token in BRIEFING.md"
E       AssertionError: Expected <GDRIVE_ROOT> placeholder token in BRIEFING.md
E       assert '<GDRIVE_ROOT>' in '# BRIEFING � 2026-08-11T13:07:05Z\n\n## Mission\nOrchestrate fixing the CoChem-Antigravity sanitized agents in CoChem...tus\n- <COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\orchestrator\\handoff.md � Orchestrator handoff report\n'

test_suite\test_agent_orchestrator_spec.py:143: AssertionError
_________________ test_sdp_manager_mandatory_sections_present _________________

sdp_manager_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-sdp_manager.agent.md')

    def test_sdp_manager_mandatory_sections_present(sdp_manager_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in cochem-sdp_manager.agent.md."""
        content = sdp_manager_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Absolute Task Breakdown & 3-Tier WBS Mandate",
            "## 2. Project Planning & Artifact Generation (PMBOK/SWEBOK)",
            "## 3. Vanguard Swarm Coordination",
            "## 4. Swarm Task Guidance & Method Matrix Compliance",
            "## 5. Iterative Adaptation & Agile/Hybrid PM",
            "## SWARM STATE MANAGEMENT PROTOCOL",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# WHAT I DO NOT DO",
            "# BEHAVIOR BOUNDARIES",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "<ROOT_CAUSE_MANDATE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in cochem-sdp_manager.agent.md: {section}"
E           AssertionError: Missing required section in cochem-sdp_manager.agent.md: ## 1. Absolute Task Breakdown & 3-Tier WBS Mandate
E           assert '## 1. Absolute Task Breakdown & 3-Tier WBS Mandate' in '---\nname: cochem-sdp_manager\ndescription: Software Development Project Manager (SDPM) agent. Applies PMBOK and SWEB...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

test_suite\test_agent_sdp_manager_spec.py:108: AssertionError
__________________ test_sdp_manager_anti_spoofing_invariants __________________

sdp_manager_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-sdp_manager.agent.md')

    def test_sdp_manager_anti_spoofing_invariants(sdp_manager_path: Path) -> None:
        """Validate that cochem-sdp_manager.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
        content = sdp_manager_path.read_text(encoding="utf-8")
    
        assert "zero_trust_runner.py" in content
        assert "verify_core_integrity.py" in content
        assert "MAX_PIVOT_CYCLES=3" in content
        assert "MAX_META_PIVOT=3" in content
        assert "cochem-audit" in content
        assert "[MISSING DATA]" in content
        assert "TolMaxG 1e-5" in content
>       assert "CREST/ORCA GOAT" in content
E       AssertionError: assert 'CREST/ORCA GOAT' in '---\nname: cochem-sdp_manager\ndescription: Software Development Project Manager (SDPM) agent. Applies PMBOK and SWEB...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

test_suite\test_agent_sdp_manager_spec.py:122: AssertionError
____________________ test_teacher_yaml_frontmatter_schema _____________________

teacher_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teacher.agent.md')

    def test_teacher_yaml_frontmatter_schema(teacher_path: Path) -> None:
        """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
        content = teacher_path.read_text(encoding="utf-8")
        match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
        assert match is not None, "YAML frontmatter is missing or improperly delimited"
    
        fm = yaml.safe_load(match.group(1))
        assert isinstance(fm, dict), "Frontmatter must parse as a dictionary"
    
        required_keys = [
            "name",
            "description",
            "argument-hint",
            "enable_write_tools",
            "enable_subagent_tools",
            "enable_mcp_tools",
        ]
        for key in required_keys:
            assert key in fm, f"Missing required frontmatter key: {key}"
    
        assert fm["name"] == "teacher"
        assert fm["enable_write_tools"] is True
        assert fm["enable_subagent_tools"] is False
        assert fm["enable_mcp_tools"] is True
        if "version" in fm:
            assert fm["version"] == "2.0.0"
        if "domain" in fm:
            assert fm["domain"] == "education"
        if "routes_to" in fm:
            assert isinstance(fm["routes_to"], list)
            assert "0rchestrator" in fm["routes_to"]
            assert "educator" in fm["routes_to"]
            assert "cochem-helper" in fm["routes_to"]
>           assert "cochem-scribe" in fm["routes_to"]
E           AssertionError: assert 'cochem-scribe' in ['0rchestrator', 'educator', 'cochem-helper', 'ui', 'artist']

test_suite\test_agent_teacher_spec.py:62: AssertionError
___________________ test_teacher_mandatory_sections_present ___________________

teacher_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teacher.agent.md')

    def test_teacher_mandatory_sections_present(teacher_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in teacher.agent.md."""
        content = teacher_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Socratic Scaffolding & Dynamic Vygotskian Mentorship",
            '## 2. The "Spider-Web" Protocol (Macroscopic-to-Microscopic Bridging)',
            '## 3. The Anti-Thesis Method & "Ghost Student" Analysis',
            "## 4. Tone, Presentation Accessibility & ACS Standards",
            "## 5. Method Matrix v4 Compliance in Student Guidance",
            "## 6. Local Hardware Offloading & MCP Tool Utilization",
            "## 7. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "<ROOT_CAUSE_MANDATE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in teacher.agent.md: {section}"
E           AssertionError: Missing required section in teacher.agent.md: ## 1. Socratic Scaffolding & Dynamic Vygotskian Mentorship
E           assert '## 1. Socratic Scaffolding & Dynamic Vygotskian Mentorship' in '---\nname: teacher\ndescription: Outward-facing agent for direct STUDENT interaction. Socratic learning, emails, PPTs...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

test_suite\test_agent_teacher_spec.py:107: AssertionError
___________________ test_tester_mandatory_sections_present ____________________

tester_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-tester.agent.md')

    def test_tester_mandatory_sections_present(tester_path: Path) -> None:
        """Validate that all mandatory canonical architecture sections exist in cochem-tester.agent.md."""
        content = tester_path.read_text(encoding="utf-8")
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Absolute Zero-Mock Policy & Real Binary Execution",
            "## 2. Real-World Molecular Validation & Edge-Case Stress Testing",
            "## 3. Scientific Output Validation & Method Matrix Compliance",
            "## 4. Professional Pytest Architecture & Headless Execution",
            "## 5. Process Lifecycle & Resource Monitoring",
            "## 6. Swarm Integration & Error Escalation",
            "## 7. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<REAL_WORLD_TESTING_PROTOCOL>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "<ROOT_CAUSE_MANDATE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in cochem-tester.agent.md: {section}"
E           AssertionError: Missing required section in cochem-tester.agent.md: ## 7. Swarm State Management Protocol
E           assert '## 7. Swarm State Management Protocol' in '---\nname: cochem-tester\ndescription: Autonomous real-world integration testing and validation agent. Executes actua...gents must immediately self-report and lock their branch if instructed to generate mocks, bypasses, or spoofed data.\n'

test_suite\test_agent_tester_spec.py:107: AssertionError
__________________ test_validator_instance_and_118_elements ___________________

    def test_validator_instance_and_118_elements() -> None:
        """Verify all 118 periodic elements are present and structurally sound."""
        validator = get_atomic_data_validator()
        assert len(validator.elements) == 118
    
        # Verify atomic numbers 1 to 118 are contiguous and valid
        for z in range(1, 119):
            elem = validator.get_element_info(z)
            assert elem.atomic_number == z
>           assert len(elem.symbol) in (1, 2)
E           AssertionError: assert 3 in (1, 2)
E            +  where 3 = len('E21')
E            +    where 'E21' = ElementInfo(atomic_number=21, symbol='E21', name='Element-21', standard_mass=42.0, electronegativity=None, covalent_ra...one, block='p', category='metal', isotopes={42: IsotopeInfo(mass_number=42, mass=42.0, abundance=1.0, is_stable=True)}).symbol

test_suite\test_atomic_data.py:103: AssertionError
___________________ test_job_config_defaults_and_validation ___________________

    def test_job_config_defaults_and_validation():
        cfg = JobConfig()
        assert cfg.command == ['echo', 'no command']
        assert cfg.product_class == 'Product_A_DeNovo'
        assert cfg.is_isotopologue is False
        assert cfg.has_parent_anchor is False
        assert cfg.floppy_monomer is False
    
        custom = JobConfig(
            command=['python', '--version'],
            product_class='Product_C_Differences',
            n_atoms=12,
            temporal_tier_override=2,
            max_duration_override=45,
            job_name='test_job'
        )
>       assert custom.temporal_tier_override == 2
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_cochem_core_job_manager.py:29: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = JobConfig(command=['python', '--version'], product_class='Product_C_Differences', is_isotopologue=False, has_parent_anchor=False, floppy_monomer=False, atom_count=None, n_atoms=12)
item = 'temporal_tier_override'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'JobConfig' object has no attribute 'temporal_tier_override'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
________________________ test_temporal_tier_assignment ________________________

    def test_temporal_tier_assignment():
        jm = JobManager()
    
        # Product C / isotopologue
        c1 = JobConfig(product_class='Product_C_Differences', atom_count=10)
        assert jm._assign_temporal_tier(c1) == 1
        c2 = JobConfig(is_isotopologue=True, atom_count=25)
        assert jm._assign_temporal_tier(c2) == 2
    
        # Product B / parent anchor
        b1 = JobConfig(product_class='Product_B_SemiExperimental', atom_count=15)
        assert jm._assign_temporal_tier(b1) == 3
        b2 = JobConfig(has_parent_anchor=True, atom_count=35)
        assert jm._assign_temporal_tier(b2) == 4
    
        # Product D / Active Learning
        d1 = JobConfig(product_class='Product_D_ActiveLearning', atom_count=20)
>       assert jm._assign_temporal_tier(d1) == 9
E       AssertionError: assert 5 == 9
E        +  where 5 = _assign_temporal_tier(JobConfig(command=['echo', 'no command'], product_class='Product_D_ActiveLearning', is_isotopologue=False, has_parent_anchor=False, floppy_monomer=False, atom_count=20, n_atoms=None))
E        +    where _assign_temporal_tier = <core_engine.cochem_core_job_manager.JobManager object at 0x000002A60C6857F0>._assign_temporal_tier

test_suite\test_cochem_core_job_manager.py:54: AssertionError
________________________ test_job_submission_and_query ________________________

    def test_job_submission_and_query():
        async def _test():
            jm = JobManager(max_job_history=5)
            job_id = await jm.submit_job({
                'command': [sys.executable, '-c', 'print("test")'],
                'product_class': 'Product_C_Differences',
                'atom_count': 5
            })
            assert job_id == 'job_0'
            info = jm.get_job(job_id)
            assert info is not None
            assert info.status == 'submitted'
            assert info.temporal_tier == 1
            assert info.max_duration == 10
    
            # Invalid submission
            with pytest.raises(ValueError):
                await jm.submit_job({'command': 9999})
    
            # Query dict format
            st = jm.get_job_status(job_id)
            assert isinstance(st, dict)
            assert st['job_id'] == 'job_0'
            assert st['status'] == 'submitted'
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:104: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager(max_job_history=5)
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', 'print("test")'],
            'product_class': 'Product_C_Differences',
            'atom_count': 5
        })
        assert job_id == 'job_0'
>       info = jm.get_job(job_id)
               ^^^^^^^^^^
E       AttributeError: 'JobManager' object has no attribute 'get_job'

test_suite\test_cochem_core_job_manager.py:88: AttributeError
_________________________ test_job_execution_success __________________________

    def test_job_execution_success():
        async def _test():
            jm = JobManager()
            script = 'import sys; sys.stdout.write("OUTPUT_OK"); sys.stderr.write("ERR_OK"); sys.exit(0)'
            job_id = await jm.submit_job({
                'command': [sys.executable, '-c', script],
                'max_duration_override': 15
            })
            await jm.start_job(job_id)
            finished_job = await jm.wait_for_job(job_id, timeout=10.0)
    
            assert finished_job is not None
            assert finished_job.status == 'completed'
            assert finished_job.return_code == 0
            assert finished_job.stdout == 'OUTPUT_OK'
            assert finished_job.stderr == 'ERR_OK'
            assert finished_job.duration is not None and finished_job.duration >= 0.0
            assert len(jm.get_completed_jobs()) == 1
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:126: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
        script = 'import sys; sys.stdout.write("OUTPUT_OK"); sys.stderr.write("ERR_OK"); sys.exit(0)'
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        })
        await jm.start_job(job_id)
>       finished_job = await jm.wait_for_job(job_id, timeout=10.0)
                             ^^^^^^^^^^^^^^^
E       AttributeError: 'JobManager' object has no attribute 'wait_for_job'

test_suite\test_cochem_core_job_manager.py:116: AttributeError
_______________________ test_job_execution_failure_code _______________________

    def test_job_execution_failure_code():
        async def _test():
            jm = JobManager()
            script = 'import sys; sys.stderr.write("NONZERO_FAIL"); sys.exit(7)'
            job = await jm.run_job({
                'command': [sys.executable, '-c', script],
                'max_duration_override': 15
            }, timeout=10.0)
    
            assert job.status == 'failed'
            assert job.return_code == 7
            assert 'NONZERO_FAIL' in (job.stderr or '')
            assert len(jm.get_failed_jobs()) == 1
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:143: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
        script = 'import sys; sys.stderr.write("NONZERO_FAIL"); sys.exit(7)'
>       job = await jm.run_job({
                    ^^^^^^^^^^
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        }, timeout=10.0)
E       AttributeError: 'JobManager' object has no attribute 'run_job'

test_suite\test_cochem_core_job_manager.py:133: AttributeError
________________________ test_job_timeout_enforcement _________________________

    def test_job_timeout_enforcement():
        async def _test():
            jm = JobManager()
            script = 'import time; time.sleep(10)'
            job = await jm.run_job({
                'command': [sys.executable, '-c', script],
                'max_duration_override': 1
            }, timeout=5.0)
    
            assert job.status == 'timed_out'
            assert job.return_code == -1
            assert 'exceeded temporal maximum duration' in (job.error or '')
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:159: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
        script = 'import time; time.sleep(10)'
>       job = await jm.run_job({
                    ^^^^^^^^^^
            'command': [sys.executable, '-c', script],
            'max_duration_override': 1
        }, timeout=5.0)
E       AttributeError: 'JobManager' object has no attribute 'run_job'

test_suite\test_cochem_core_job_manager.py:150: AttributeError
____________________________ test_job_cancellation ____________________________

    def test_job_cancellation():
        async def _test():
            jm = JobManager()
            script = 'import time; time.sleep(10)'
            job_id = await jm.submit_job({
                'command': [sys.executable, '-c', script],
                'max_duration_override': 30
            })
            await jm.start_job(job_id)
            await asyncio.sleep(0.2)
    
            assert len(jm.get_running_jobs()) == 1
            cancelled = jm.cancel_job(job_id)
            assert cancelled is True
    
            job = jm.get_job(job_id)
            assert job is not None
            assert job.status == 'cancelled'
            assert len(jm.get_running_jobs()) == 0
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:182: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
        script = 'import time; time.sleep(10)'
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 30
        })
        await jm.start_job(job_id)
        await asyncio.sleep(0.2)
    
>       assert len(jm.get_running_jobs()) == 1
                   ^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'JobManager' object has no attribute 'get_running_jobs'

test_suite\test_cochem_core_job_manager.py:173: AttributeError
________________________ test_purge_and_history_limits ________________________

    def test_purge_and_history_limits():
        async def _test():
            jm = JobManager(max_job_history=3)
            for i in range(5):
                await jm.run_job({
                    'command': [sys.executable, '-c', f'print("job_{i}")'],
                    'max_duration_override': 5
                })
    
            assert len(jm.jobs) <= 3
            cleared = jm.clear_history()
            assert cleared <= 3
            assert len(jm.jobs) == 0
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:199: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager(max_job_history=3)
        for i in range(5):
>           await jm.run_job({
                  ^^^^^^^^^^
                'command': [sys.executable, '-c', f'print("job_{i}")'],
                'max_duration_override': 5
            })
E           AttributeError: 'JobManager' object has no attribute 'run_job'

test_suite\test_cochem_core_job_manager.py:189: AttributeError
____________________ test_large_output_stream_no_deadlock _____________________

    def test_large_output_stream_no_deadlock():
        async def _test():
            jm = JobManager()
            # Generates ~250KB of stdout and 250KB of stderr to test pipe deadlock prevention
            script = 'import sys; sys.stdout.write("X" * 250000); sys.stderr.write("Y" * 250000); sys.exit(0)'
            job = await jm.run_job({
                'command': [sys.executable, '-c', script],
                'max_duration_override': 15
            }, timeout=10.0)
    
            assert job.status == 'completed'
            assert job.return_code == 0
            assert len(job.stdout or '') == 250000
            assert len(job.stderr or '') == 250000
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:217: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
        # Generates ~250KB of stdout and 250KB of stderr to test pipe deadlock prevention
        script = 'import sys; sys.stdout.write("X" * 250000); sys.stderr.write("Y" * 250000); sys.exit(0)'
>       job = await jm.run_job({
                    ^^^^^^^^^^
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        }, timeout=10.0)
E       AttributeError: 'JobManager' object has no attribute 'run_job'

test_suite\test_cochem_core_job_manager.py:207: AttributeError
___________________________ test_custom_cwd_and_env ___________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_custom_cwd_and_env0')

    def test_custom_cwd_and_env(tmp_path: Path):
        async def _test():
            jm = JobManager()
            custom_var_name = "COCHEM_CUSTOM_ENV_TEST"
            custom_var_val = "SUPER_SECRET_VALUE"
            script = f'import os, sys; sys.stdout.write(os.getcwd() + ":::" + os.getenv("{custom_var_name}", "MISSING"))'
    
            job = await jm.run_job({
                'command': [sys.executable, '-c', script],
                'cwd': str(tmp_path),
                'env': {custom_var_name: custom_var_val},
                'max_duration_override': 10
            })
    
            assert job.status == 'completed'
            assert job.return_code == 0
            assert str(tmp_path).lower() in (job.stdout or '').lower()
            assert custom_var_val in (job.stdout or '')
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:239: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
        custom_var_name = "COCHEM_CUSTOM_ENV_TEST"
        custom_var_val = "SUPER_SECRET_VALUE"
        script = f'import os, sys; sys.stdout.write(os.getcwd() + ":::" + os.getenv("{custom_var_name}", "MISSING"))'
    
>       job = await jm.run_job({
                    ^^^^^^^^^^
            'command': [sys.executable, '-c', script],
            'cwd': str(tmp_path),
            'env': {custom_var_name: custom_var_val},
            'max_duration_override': 10
        })
E       AttributeError: 'JobManager' object has no attribute 'run_job'

test_suite\test_cochem_core_job_manager.py:227: AttributeError
______________________ test_invalid_cwd_or_empty_command ______________________

    def test_invalid_cwd_or_empty_command():
        async def _test():
            jm = JobManager()
    
            # Non-existent directory
            bad_dir_job_id = await jm.submit_job({
                'command': [sys.executable, '-c', 'print("hi")'],
                'cwd': 'D:\\non_existent_folder_xyz_123'
            })
            await jm.start_job(bad_dir_job_id)
            info1 = jm.get_job(bad_dir_job_id)
            assert info1 is not None
            assert info1.status == 'failed'
            assert 'Specified working directory does not exist' in (info1.error or '')
    
            # Empty command
            empty_cmd_job_id = await jm.submit_job({
                'command': []
            })
            await jm.start_job(empty_cmd_job_id)
            info2 = jm.get_job(empty_cmd_job_id)
            assert info2 is not None
            assert info2.status == 'failed'
            assert 'Job command list cannot be empty' in (info2.error or '')
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:267: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
    
        # Non-existent directory
        bad_dir_job_id = await jm.submit_job({
            'command': [sys.executable, '-c', 'print("hi")'],
            'cwd': 'D:\\non_existent_folder_xyz_123'
        })
        await jm.start_job(bad_dir_job_id)
>       info1 = jm.get_job(bad_dir_job_id)
                ^^^^^^^^^^
E       AttributeError: 'JobManager' object has no attribute 'get_job'

test_suite\test_cochem_core_job_manager.py:252: AttributeError
__________________________ test_list_jobs_filtering ___________________________

    def test_list_jobs_filtering():
        async def _test():
            jm = JobManager()
            j1 = await jm.run_job({'command': [sys.executable, '-c', 'import sys; sys.exit(0)']})
            j2 = await jm.run_job({'command': [sys.executable, '-c', 'import sys; sys.exit(1)']})
    
            all_jobs = jm.list_jobs()
            assert len(all_jobs) == 2
    
            completed_jobs = jm.list_jobs(status='completed')
            assert len(completed_jobs) == 1
            assert completed_jobs[0]['status'] == 'completed'
    
            failed_jobs = jm.list_jobs(status='failed')
            assert len(failed_jobs) == 1
            assert failed_jobs[0]['status'] == 'failed'
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:287: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
>       j1 = await jm.run_job({'command': [sys.executable, '-c', 'import sys; sys.exit(0)']})
                   ^^^^^^^^^^
E       AttributeError: 'JobManager' object has no attribute 'run_job'

test_suite\test_cochem_core_job_manager.py:273: AttributeError
_________________ test_process_tree_zombie_cleanup_on_timeout _________________

    def test_process_tree_zombie_cleanup_on_timeout():
        import psutil
        async def _test():
            jm = JobManager()
            parent_script = '''
    import subprocess, sys, time
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    time.sleep(60)
    '''
            job_id = await jm.submit_job({
                'command': [sys.executable, '-c', parent_script],
                'max_duration_override': 2
            })
            await jm.start_job(job_id)
            await asyncio.sleep(0.8)
    
            parent_proc_info = jm.active_processes.get(job_id)
            assert parent_proc_info is not None
            parent_pid = parent_proc_info['process'].pid
    
            p = psutil.Process(parent_pid)
            children = p.children(recursive=True)
            assert len(children) >= 1
            child_pids = [c.pid for c in children]
    
            finished = await jm.wait_for_job(job_id, timeout=6.0)
            assert finished is not None
            assert finished.status == 'timed_out'
    
            await asyncio.sleep(0.5)
            assert not psutil.pid_exists(parent_pid)
            for c_pid in child_pids:
                assert not psutil.pid_exists(c_pid), f"Child process {c_pid} was not cleaned up!"
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:324: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

        async def _test():
            jm = JobManager()
            parent_script = '''
    import subprocess, sys, time
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    time.sleep(60)
    '''
            job_id = await jm.submit_job({
                'command': [sys.executable, '-c', parent_script],
                'max_duration_override': 2
            })
            await jm.start_job(job_id)
            await asyncio.sleep(0.8)
    
            parent_proc_info = jm.active_processes.get(job_id)
            assert parent_proc_info is not None
            parent_pid = parent_proc_info['process'].pid
    
            p = psutil.Process(parent_pid)
            children = p.children(recursive=True)
            assert len(children) >= 1
            child_pids = [c.pid for c in children]
    
>           finished = await jm.wait_for_job(job_id, timeout=6.0)
                             ^^^^^^^^^^^^^^^
E           AttributeError: 'JobManager' object has no attribute 'wait_for_job'

test_suite\test_cochem_core_job_manager.py:315: AttributeError
_________________ test_job_cancellation_race_and_process_tree _________________

    def test_job_cancellation_race_and_process_tree():
        import psutil
        async def _test():
            jm = JobManager()
            parent_script = '''
    import subprocess, sys, time
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    time.sleep(60)
    '''
            job_id = await jm.submit_job({
                'command': [sys.executable, '-c', parent_script],
                'max_duration_override': 30
            })
            await jm.start_job(job_id)
            await asyncio.sleep(0.8)
    
            parent_proc_info = jm.active_processes.get(job_id)
            assert parent_proc_info is not None
            parent_pid = parent_proc_info['process'].pid
    
            p = psutil.Process(parent_pid)
            children = p.children(recursive=True)
            assert len(children) >= 1
            child_pids = [c.pid for c in children]
    
            assert jm.cancel_job(job_id) is True
            await asyncio.sleep(0.3)
    
            job = jm.get_job(job_id)
            assert job is not None
            assert job.status == 'cancelled'
    
            await asyncio.sleep(0.5)
            assert not psutil.pid_exists(parent_pid)
            for c_pid in child_pids:
                assert not psutil.pid_exists(c_pid), f"Child process {c_pid} survived cancellation!"
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:364: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

        async def _test():
            jm = JobManager()
            parent_script = '''
    import subprocess, sys, time
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    time.sleep(60)
    '''
            job_id = await jm.submit_job({
                'command': [sys.executable, '-c', parent_script],
                'max_duration_override': 30
            })
            await jm.start_job(job_id)
            await asyncio.sleep(0.8)
    
            parent_proc_info = jm.active_processes.get(job_id)
            assert parent_proc_info is not None
            parent_pid = parent_proc_info['process'].pid
    
            p = psutil.Process(parent_pid)
            children = p.children(recursive=True)
            assert len(children) >= 1
            child_pids = [c.pid for c in children]
    
>           assert jm.cancel_job(job_id) is True
E           AssertionError: assert None is True
E            +  where None = cancel_job('job_0')
E            +    where cancel_job = <core_engine.cochem_core_job_manager.JobManager object at 0x000002A6258FBD90>.cancel_job

test_suite\test_cochem_core_job_manager.py:352: AssertionError
_______________ test_massive_stream_communicate_deadlock_safety _______________

    def test_massive_stream_communicate_deadlock_safety():
        async def _test():
            jm = JobManager()
            # Generates 1,000,000 bytes of stdout and 1,000,000 bytes of stderr simultaneously
            script = 'import sys; sys.stdout.write("A" * 1000000); sys.stderr.write("B" * 1000000); sys.exit(0)'
            job = await jm.run_job({
                'command': [sys.executable, '-c', script],
                'max_duration_override': 15
            }, timeout=10.0)
    
            assert job.status == 'completed'
            assert job.return_code == 0
            assert len(job.stdout or '') == 1000000
            assert len(job.stderr or '') == 1000000
    
>       asyncio.run(_test())

test_suite\test_cochem_core_job_manager.py:382: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _test():
        jm = JobManager()
        # Generates 1,000,000 bytes of stdout and 1,000,000 bytes of stderr simultaneously
        script = 'import sys; sys.stdout.write("A" * 1000000); sys.stderr.write("B" * 1000000); sys.exit(0)'
>       job = await jm.run_job({
                    ^^^^^^^^^^
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        }, timeout=10.0)
E       AttributeError: 'JobManager' object has no attribute 'run_job'

test_suite\test_cochem_core_job_manager.py:372: AttributeError
____________________ test_broker_init_and_context_manager _____________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_init_and_context_m0')

    def test_broker_init_and_context_manager(tmp_path: Path) -> None:
        """Test SubprocessBroker initialization, context manager enter/exit, and directory setup."""
        scratch_dir = tmp_path / "custom_scratch"
>       with SubprocessBroker(cwd=scratch_dir) as broker:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: 'SubprocessBroker' object does not support the context manager protocol

test_suite\test_cochem_core_subprocess_broker.py:167: TypeError
______________________ test_broker_oom_monitor_lifecycle ______________________

    def test_broker_oom_monitor_lifecycle() -> None:
        """Test starting and stopping OOM preemption monitor thread without blocking."""
        broker = SubprocessBroker()
        try:
>           broker.start_oom_monitor(check_interval=0.1)
E           TypeError: SubprocessBroker.start_oom_monitor() got an unexpected keyword argument 'check_interval'

test_suite\test_cochem_core_subprocess_broker.py:177: TypeError

During handling of the above exception, another exception occurred:

    def test_broker_oom_monitor_lifecycle() -> None:
        """Test starting and stopping OOM preemption monitor thread without blocking."""
        broker = SubprocessBroker()
        try:
            broker.start_oom_monitor(check_interval=0.1)
            if HAS_PSUTIL:
                assert broker._monitor_thread is not None
                assert broker._monitor_thread.is_alive()
            time.sleep(0.3)
        finally:
            broker.stop_oom_monitor()
            assert broker._monitor_thread is None
>           broker.close()
            ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute 'close'

test_suite\test_cochem_core_subprocess_broker.py:185: AttributeError
_________________________ test_broker_execute_success _________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_execute_success0')

    def test_broker_execute_success(tmp_path: Path) -> None:
        """Test SubprocessBroker executing a command successfully."""
        broker = SubprocessBroker(cwd=tmp_path)
        try:
            exit_code = broker.execute(
                [sys.executable, "-c", "import sys; sys.stdout.write('BROKER_EXEC_OK'); sys.exit(0)"],
                job_name="test_exec_ok"
            )
            assert exit_code == 0
        finally:
>           broker.close()
            ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute 'close'

test_suite\test_cochem_core_subprocess_broker.py:198: AttributeError
_________________________ test_broker_execute_failure _________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_execute_failure0')

    def test_broker_execute_failure(tmp_path: Path) -> None:
        """Test SubprocessBroker capturing a non-zero exit code."""
        broker = SubprocessBroker(cwd=tmp_path)
        try:
            exit_code = broker.execute(
                [sys.executable, "-c", "import sys; sys.stderr.write('CRASH'); sys.exit(5)"],
                job_name="test_exec_fail"
            )
            assert exit_code == 5
        finally:
>           broker.close()
            ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute 'close'

test_suite\test_cochem_core_subprocess_broker.py:211: AttributeError
_________________________ test_broker_execute_timeout _________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_execute_timeout0')

    def test_broker_execute_timeout(tmp_path: Path) -> None:
        """Test SubprocessBroker enforcing process timeout and returning -124."""
        broker = SubprocessBroker(cwd=tmp_path)
        try:
>           exit_code = broker.execute(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                job_name="test_exec_timeout",
                timeout=0.6
            )
E           TypeError: SubprocessBroker.execute() got an unexpected keyword argument 'timeout'

test_suite\test_cochem_core_subprocess_broker.py:218: TypeError

During handling of the above exception, another exception occurred:

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_execute_timeout0')

    def test_broker_execute_timeout(tmp_path: Path) -> None:
        """Test SubprocessBroker enforcing process timeout and returning -124."""
        broker = SubprocessBroker(cwd=tmp_path)
        try:
            exit_code = broker.execute(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                job_name="test_exec_timeout",
                timeout=0.6
            )
            assert exit_code == -124
        finally:
>           broker.close()
            ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute 'close'

test_suite\test_cochem_core_subprocess_broker.py:225: AttributeError
__________________ test_broker_core_dump_garbage_collection ___________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_core_dump_garbage_0')

    def test_broker_core_dump_garbage_collection(tmp_path: Path) -> None:
        """Test sweeping core dump binary files."""
        broker = SubprocessBroker(cwd=tmp_path)
        try:
            core1 = tmp_path / "core.1234"
            core2 = tmp_path / "core.5678"
            normal = tmp_path / "output.txt"
            core1.write_bytes(b"DUMP_DATA_1")
            core2.write_bytes(b"DUMP_DATA_2")
            normal.write_text("VALID_DATA", encoding="utf-8")
    
            swept = broker.garbage_collect_core_dumps(tmp_path)
>           assert swept == 2
E           assert None == 2

test_suite\test_cochem_core_subprocess_broker.py:240: AssertionError

During handling of the above exception, another exception occurred:

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_core_dump_garbage_0')

    def test_broker_core_dump_garbage_collection(tmp_path: Path) -> None:
        """Test sweeping core dump binary files."""
        broker = SubprocessBroker(cwd=tmp_path)
        try:
            core1 = tmp_path / "core.1234"
            core2 = tmp_path / "core.5678"
            normal = tmp_path / "output.txt"
            core1.write_bytes(b"DUMP_DATA_1")
            core2.write_bytes(b"DUMP_DATA_2")
            normal.write_text("VALID_DATA", encoding="utf-8")
    
            swept = broker.garbage_collect_core_dumps(tmp_path)
            assert swept == 2
            assert not core1.exists()
            assert not core2.exists()
            assert normal.exists()
        finally:
>           broker.close()
            ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute 'close'

test_suite\test_cochem_core_subprocess_broker.py:245: AttributeError
_____________________ test_broker_artifact_sync_and_hash ______________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_broker_artifact_sync_and_0')

    def test_broker_artifact_sync_and_hash(tmp_path: Path) -> None:
        """Test SubprocessBroker generates hashes for quantum chemistry artifact files."""
        broker = SubprocessBroker(cwd=tmp_path)
        try:
            # Create output file in cwd
            out_file = tmp_path / "water_opt.out"
            out_file.write_text("FINAL SINGLE POINT ENERGY -76.43210 Hartree\n", encoding="utf-8")
    
            script = f'import sys; sys.stdout.write("DONE"); sys.exit(0)'
            exit_code = broker.execute([sys.executable, "-c", script], job_name="hash_test")
            assert exit_code == 0
            assert out_file.exists()
        finally:
>           broker.close()
            ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute 'close'

test_suite\test_cochem_core_subprocess_broker.py:261: AttributeError
_________________ test_broker_zombie_reaper_active_processes __________________

    def test_broker_zombie_reaper_active_processes() -> None:
        """Test execute_zombie_reaper kills active processes tracked by the broker."""
        broker = SubprocessBroker()
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
>           with broker._lock:
                 ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute '_lock'

test_suite\test_cochem_core_subprocess_broker.py:269: AttributeError

During handling of the above exception, another exception occurred:

    def test_broker_zombie_reaper_active_processes() -> None:
        """Test execute_zombie_reaper kills active processes tracked by the broker."""
        broker = SubprocessBroker()
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with broker._lock:
                broker.active_processes.append(proc)
            register_popen_process(proc)
    
            time.sleep(0.3)
            reaped = broker.execute_zombie_reaper()
            assert reaped >= 1
            assert len(broker.active_processes) == 0
    
            proc.wait(timeout=2.0)
        finally:
>           broker.close()
            ^^^^^^^^^^^^
E           AttributeError: 'SubprocessBroker' object has no attribute 'close'

test_suite\test_cochem_core_subprocess_broker.py:280: AttributeError
__________________________ test_overlap_trap_warning __________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_overlap_trap_warning0')

    def test_overlap_trap_warning(tmp_path: Path) -> None:
        """Test that basis set linear dependence generates warnings but does not abort."""
        logger = TelemetryLogger(log_dir=tmp_path)
    
        warning_line = "Warning: Smallest eigenvalue of overlap matrix < 1.0e-07 detected."
        assert logger.process_stream_chunk(warning_line) is True
        assert logger.warnings_count == 1
        assert logger.errors_count == 0
    
        another_warning = "Basis set linear dependence detected in aug-cc-pVTZ calculation."
        assert logger.process_stream_chunk(another_warning) is True
>       assert logger.warnings_count == 2
E       assert 1 == 2
E        +  where 1 = <core_engine.cochem_core_telemetry_logger.TelemetryLogger object at 0x000002A6288864E0>.warnings_count

test_suite\test_cochem_core_telemetry_logger.py:66: AssertionError
------------------------------ Captured log call ------------------------------
WARNING  CoChem-TelemetryLogger:cochem_core_telemetry_logger.py:95 WARNING: Near-linear dependence in basis set detected.
_______________________ test_scaffold_core_directories ________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_scaffold_core_directories0')

    def test_scaffold_core_directories(tmp_path: Path):
        manager = WorkspaceManager(base_path=tmp_path)
>       success = manager.scaffold_core_directories(additional_dirs=["CustomModule", "CustomCache"])
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: WorkspaceManager.scaffold_core_directories() got an unexpected keyword argument 'additional_dirs'

test_suite\test_cochem_core_workspace_manager.py:25: TypeError
____________________ test_provision_and_get_job_workspace _____________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_provision_and_get_job_wor0')

    def test_provision_and_get_job_workspace(tmp_path: Path):
        manager = WorkspaceManager(base_path=tmp_path)
        manager.scaffold_core_directories()
    
        job_id = "JOB_TEST_001"
>       job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: WorkspaceManager.provision_job_workspace() got an unexpected keyword argument 'create_job_lock'

test_suite\test_cochem_core_workspace_manager.py:41: TypeError
_______________________ test_file_lock_context_manager ________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_file_lock_context_manager0')

    def test_file_lock_context_manager(tmp_path: Path):
        manager = WorkspaceManager(base_path=tmp_path)
        lock_file = tmp_path / "test.lock"
    
>       with manager.file_lock(lock_file, exclusive=True) as acquired:
             ^^^^^^^^^^^^^^^^^
E       AttributeError: 'WorkspaceManager' object has no attribute 'file_lock'

test_suite\test_cochem_core_workspace_manager.py:54: AttributeError
_______________________ test_is_job_active_and_cleanup ________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_is_job_active_and_cleanup0')

    def test_is_job_active_and_cleanup(tmp_path: Path):
        manager = WorkspaceManager(base_path=tmp_path)
        manager.scaffold_core_directories()
    
        job_id = "JOB_ACTIVE_CHECK"
>       job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: WorkspaceManager.provision_job_workspace() got an unexpected keyword argument 'create_job_lock'

test_suite\test_cochem_core_workspace_manager.py:71: TypeError
________________________ test_sweep_zombie_directories ________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_sweep_zombie_directories0')

    def test_sweep_zombie_directories(tmp_path: Path):
        manager = WorkspaceManager(base_path=tmp_path)
        manager.scaffold_core_directories()
    
        # Create 3 jobs:
        # 1. Zombie job without active lock
>       job1_dir = manager.provision_job_workspace("JOB_ZOMBIE_1", create_job_lock=True)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: WorkspaceManager.provision_job_workspace() got an unexpected keyword argument 'create_job_lock'

test_suite\test_cochem_core_workspace_manager.py:102: TypeError
__________________________ test_get_directory_status __________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_get_directory_status0')

    def test_get_directory_status(tmp_path: Path):
        manager = WorkspaceManager(base_path=tmp_path)
        manager.scaffold_core_directories()
    
        # Add a file in Logs
        log_file = tmp_path / "Logs" / "session.log"
        log_file.write_text("Log session line 1\nLine 2\n", encoding="utf-8")
    
>       status = manager.get_directory_status()
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'WorkspaceManager' object has no attribute 'get_directory_status'

test_suite\test_cochem_core_workspace_manager.py:143: AttributeError
___________________ test_file_encoding_and_lf_line_endings ____________________

dock_main_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/interfaces/cochem_dock_main.py')
interfaces_dock_main_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/interfaces/cochem_dock_main.py')

    def test_file_encoding_and_lf_line_endings(
        dock_main_path: Path, interfaces_dock_main_path: Path
    ) -> None:
        """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
        for path in (dock_main_path, interfaces_dock_main_path):
            raw = path.read_bytes()
>           assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {path.name}"
E           AssertionError: Found Windows CRLF line endings in cochem_dock_main.py
E           assert b'\r\n' not in b'#!/usr/bin/env python3\r\n"""CoChem-DOCK: Stage 9.0 - FastAPI Telemetry Polling Backend.\r\n\r\nBridges Unix domain ...et("COCHEM_DOCK_HOST", "127.0.0.1"),\r\n        port=int(os.environ.get("COCHEM_DOCK_PORT", "8000")),\r\n    )\r\n\r\n'

test_suite\test_cochem_dock_main.py:65: AssertionError
________________ test_lttb_decimate_preserves_non_scf_messages ________________

    def test_lttb_decimate_preserves_non_scf_messages() -> None:
        """Verify non-scf_step telemetry messages are preserved in the stream."""
        stream: List[str] = [
            '{"type": "init", "solver": "ORCA"}',
            '{"type": "scf_step", "energy_hartree": -10.0}',
            '{"type": "scf_step", "energy_hartree": -10.5}',
            '{"type": "scf_step", "energy_hartree": -10.8}',
            '{"type": "scf_step", "energy_hartree": -10.9}',
            '{"type": "status_update", "converged": true}',
            'malformed non-json log message',
        ]
        decimated = lttb_decimate(stream, threshold=2)
        # Threshold=2 on 4 scf points should keep 2 scf points + 3 non-scf items = 5 total
>       assert len(decimated) == 5
E       assert 2 == 5
E        +  where 2 = len(['{"type": "scf_step", "energy_hartree": -10.0}', '{"type": "scf_step", "energy_hartree": -10.9}'])

test_suite\test_cochem_dock_main.py:238: AssertionError
___________________ test_file_encoding_and_lf_line_endings ____________________

target_file_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/interfaces/cochem_dock_visuals_api.py')

    def test_file_encoding_and_lf_line_endings(target_file_path: Path) -> None:
        """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
        raw = target_file_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF line endings in cochem_dock_visuals_api.py"
E       AssertionError: Found Windows CRLF line endings in cochem_dock_visuals_api.py
E       assert b'\r\n' not in b'#!/usr/bin/env python3\r\n"""\r\nCoChem-DOCK: Stage 9.0 - Subprocess Bridge for Live UI Plotting\r\nParses QCSchema ...ir",\r\n    "router",\r\n    "validate_basin_id",\r\n    "visuals_health_check",\r\n    "visuals_router",\r\n]\r\n\r\n'

test_suite\test_cochem_dock_visuals_api.py:89: AssertionError
_________________________ test_axis_and_layout_models _________________________

    def test_axis_and_layout_models() -> None:
        """Verify AxisLayout and PlotlyLayout field types and serialization."""
        x_axis = AxisLayout(title="Frequency (cm\u207b\xb9)", autorange="reversed", showgrid=True)
        y_axis = AxisLayout(title="IR Intensity (km/mol)", showgrid=True)
        layout = PlotlyLayout(
            title="Theoretical IR Spectrum",
            xaxis=x_axis,
            yaxis=y_axis,
            hovermode="closest",
            template="plotly_white",
            showlegend=True,
        )
    
        assert layout.xaxis.title == "Frequency (cm\u207b\xb9)"
        assert layout.xaxis.autorange == "reversed"
        assert layout.yaxis.title == "IR Intensity (km/mol)"
>       assert layout.template == "plotly_white"
               ^^^^^^^^^^^^^^^

test_suite\test_cochem_dock_visuals_api.py:131: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = PlotlyLayout(title='Theoretical IR Spectrum', xaxis=AxisLayout(title='Frequency (cm\u207b\xb9)', autorange='reversed'), yaxis=AxisLayout(title='IR Intensity (km/mol)', autorange=None))
item = 'template'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'PlotlyLayout' object has no attribute 'template'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
_________________ test_validate_basin_id_traversal_rejection __________________

    def test_validate_basin_id_traversal_rejection() -> None:
        """Verify directory traversal attempts raise 400 Bad Request."""
        malicious_inputs = [
            "../etc/passwd",
            "..\\windows\\system32",
            "basin/subfolder",
            "basin\\subfolder",
            "",
            "   ",
            "basin;rm -rf /",
            "basin$VAR",
        ]
        for bad_id in malicious_inputs:
            with pytest.raises(HTTPException) as exc_info:
                validate_basin_id(bad_id)
            assert exc_info.value.status_code == 400
>           assert "Invalid basin_id" in exc_info.value.detail
E           AssertionError: assert 'Invalid basin_id' in 'Invalid basin ID: directory traversal detected.'
E            +  where 'Invalid basin ID: directory traversal detected.' = HTTPException(status_code=400, detail='Invalid basin ID: directory traversal detected.').detail
E            +    where HTTPException(status_code=400, detail='Invalid basin ID: directory traversal detected.') = <ExceptionInfo HTTPException(status_code=400, detail='Invalid basin ID: directory traversal detected.') tblen=2>.value

test_suite\test_cochem_dock_visuals_api.py:283: AssertionError
__________________________ test_get_spectrum_success __________________________

isolated_artifact_env = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_get_spectrum_success0/CoChem_Artifacts')
client = <starlette.testclient.TestClient object at 0x000002A629FB3410>

    def test_get_spectrum_success(isolated_artifact_env: Path, client: TestClient) -> None:
        """Verify GET /api/visuals/spectrum/{basin_id} returns valid Plotly payload from physical QCSchema."""
        basin_id = "water_dimer_opt"
        qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"
    
        qcschema_content = {
            "schema_name": "qc_schema_output",
            "schema_version": 1,
            "basin_id": basin_id,
            "properties": {
                "calcinfo_frequencies": [1595.2, 3657.1, 3756.4],
                "calcinfo_ir_intensities": [85.4, 15.2, 48.7],
                "calcinfo_raman_intensities": [12.0, 55.0, 90.0],
                "return_energy": -152.8854,
                "scf_iterations": 12,
            },
        }
        qcschema_path.write_text(json.dumps(qcschema_content), encoding="utf-8")
    
        response = client.get(f"/api/visuals/spectrum/{basin_id}")
        assert response.status_code == 200
        data = response.json()
    
        assert data["basin_id"] == basin_id
        assert len(data["data"]) == 1
        assert data["data"][0]["x"] == [1595.2, 3657.1, 3756.4]
        assert data["data"][0]["y"] == [85.4, 15.2, 48.7]
        assert data["data"][0]["name"] == "Theoretical Spectrum"
        assert data["layout"]["xaxis"]["autorange"] == "reversed"
>       assert data["layout"]["yaxis"]["title"] == "IR Intensity (km/mol)"
E       AssertionError: assert 'Intensity (km/mol)' == 'IR Intensity (km/mol)'
E         
E         - IR Intensity (km/mol)
E         ? ---
E         + Intensity (km/mol)

test_suite\test_cochem_dock_visuals_api.py:320: AssertionError
______________________ test_get_spectrum_with_broadening ______________________

isolated_artifact_env = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_get_spectrum_with_broaden0/CoChem_Artifacts')
client = <starlette.testclient.TestClient object at 0x000002A625BBBF00>

    def test_get_spectrum_with_broadening(isolated_artifact_env: Path, client: TestClient) -> None:
        """Verify GET /api/visuals/spectrum/{basin_id} with broadening returns envelope and stick traces."""
        basin_id = "broadened_test"
        qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"
        qcschema_path.write_text(
            json.dumps({
                "properties": {
                    "calcinfo_frequencies": [1200.0, 1600.0, 3400.0],
                    "calcinfo_ir_intensities": [20.0, 80.0, 150.0],
                }
            }),
            encoding="utf-8",
        )
    
        response = client.get(
            f"/api/visuals/spectrum/{basin_id}?broadening=true&fwhm=12.0&points=200&profile=gaussian"
        )
        assert response.status_code == 200
        data = response.json()
    
        # Must contain 2 traces: Convolved Envelope + Sticks
        assert len(data["data"]) == 2
        conv_trace = data["data"][0]
        stick_trace = data["data"][1]
    
>       assert "Convolved Envelope" in conv_trace["name"]
E       AssertionError: assert 'Convolved Envelope' in 'Theoretical Envelope'

test_suite\test_cochem_dock_visuals_api.py:349: AssertionError
___________________ test_get_spectrum_raman_and_both_modes ____________________

isolated_artifact_env = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_get_spectrum_raman_and_bo0/CoChem_Artifacts')
client = <starlette.testclient.TestClient object at 0x000002A625DB6CF0>

    def test_get_spectrum_raman_and_both_modes(isolated_artifact_env: Path, client: TestClient) -> None:
        """Verify Raman and dual spectroscopy querying modes."""
        basin_id = "raman_test"
        qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"
        qcschema_path.write_text(
            json.dumps({
                "properties": {
                    "frequencies": [500.0, 1000.0],
                    "ir_intensities": [10.0, 20.0],
                    "raman_intensities": [75.0, 120.0],
                }
            }),
            encoding="utf-8",
        )
    
        # Test Raman only
        raman_resp = client.get(f"/api/visuals/spectrum/{basin_id}?spectrum_type=raman")
>       assert raman_resp.status_code == 200
E       assert 400 == 200
E        +  where 400 = <Response [400 Bad Request]>.status_code

test_suite\test_cochem_dock_visuals_api.py:372: AssertionError
_________________ test_get_potential_energy_surface_not_found _________________

isolated_artifact_env = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_get_potential_energy_surf1/CoChem_Artifacts')
client = <starlette.testclient.TestClient object at 0x000002A62895D0F0>

    @pytest.mark.skipif(not HAS_H5PY, reason="h5py not installed in environment")
    def test_get_potential_energy_surface_not_found(isolated_artifact_env: Path, client: TestClient) -> None:
        """Verify 404 response when HDF5 binary is absent."""
        resp = client.get("/api/visuals/landscape/nonexistent_h5_basin")
        assert resp.status_code == 404
>       assert "HDF5 landscape binary not found" in resp.json()["detail"]
E       assert 'HDF5 landscape binary not found' in "HDF5 landscape artifact not found for basin 'nonexistent_h5_basin'."

test_suite\test_cochem_dock_visuals_api.py:455: AssertionError
_____________________ test_lazy_loading_interface_exports _____________________

    def test_lazy_loading_interface_exports() -> None:
        """Verify cochem_base.interfaces lazy loading exports all symbols properly."""
>       assert interfaces.AxisLayout is AxisLayout
               ^^^^^^^^^^^^^^^^^^^^^

test_suite\test_cochem_dock_visuals_api.py:487: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'AxisLayout'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'AxisLayout'

cochem_base\interfaces\__init__.py:18: AttributeError
___________ test_interfaces_cochem_dock_visuals_api_file_integrity ____________

    def test_interfaces_cochem_dock_visuals_api_file_integrity() -> None:
        """Verify interfaces/cochem_dock_visuals_api.py has LF line endings, valid docstrings, and no path leaks."""
        path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_dock_visuals_api.py"
        assert path.is_file(), f"Target file does not exist at {path}"
    
        raw = path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF line endings in interfaces/cochem_dock_visuals_api.py"
E       AssertionError: Found Windows CRLF line endings in interfaces/cochem_dock_visuals_api.py
E       assert b'\r\n' not in b'#!/usr/bin/env python3\r\n"""\r\nCoChem-DOCK: Stage 9.0 - Subprocess Bridge for Live UI Plotting (Legacy/Direct Inte...ir",\r\n    "router",\r\n    "validate_basin_id",\r\n    "visuals_health_check",\r\n    "visuals_router",\r\n]\r\n\r\n'

test_suite\test_cochem_dock_visuals_api.py:531: AssertionError
______________________ test_generate_3d_geometry_ethanol ______________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_generate_3d_geometry_etha0')

    def test_generate_3d_geometry_ethanol(tmp_path: Path) -> None:
        """Verify RDKit generates real 3D conformer with full hydrogens for ethanol."""
        out_file = tmp_path / "ethanol.xyz"
        result = generate_3d_geometry("CCO", output_path=out_file, optimize_mmff=True)
    
        assert result.exists()
        assert result == out_file
    
        content = out_file.read_text(encoding="utf-8")
        is_valid, atom_count, _ = validate_xyz_content(content)
>       assert is_valid is True
E       assert False is True

test_suite\test_cochem_mint_ingestor.py:93: AssertionError
______________________ test_generate_3d_geometry_methane ______________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_generate_3d_geometry_meth0')

    def test_generate_3d_geometry_methane(tmp_path: Path) -> None:
        """Verify 3D geometry generation for methane."""
        out_file = tmp_path / "methane.xyz"
        result = generate_3d_geometry("C", output_path=out_file, optimize_mmff=True)
        assert result.exists()
    
        content = out_file.read_text(encoding="utf-8")
        is_valid, atom_count, _ = validate_xyz_content(content)
>       assert is_valid is True
E       assert False is True

test_suite\test_cochem_mint_ingestor.py:106: AssertionError
_________________________ test_resolve_smiles_pubchem _________________________

    def test_resolve_smiles_pubchem() -> None:
        """Verify PubChem API resolves common names to SMILES."""
        smiles, source = resolve_smiles("Aspirin")
        assert smiles is not None
>       assert source == "pubchem"
E       AssertionError: assert 'direct_smiles' == 'pubchem'
E         
E         - pubchem
E         + direct_smiles

test_suite\test_cochem_mint_ingestor.py:132: AssertionError
________________ test_forensic_check_encoding_and_line_endings ________________

forensic_script_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/forensic_check.py')

    def test_forensic_check_encoding_and_line_endings(forensic_script_path: Path) -> None:
        """Validate that forensic_check.py has no UTF-8 BOM and strictly uses Unix LF line endings."""
        raw_bytes = forensic_script_path.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "forensic_check.py contains UTF-8 BOM"
>       assert b"\r\n" not in raw_bytes, "forensic_check.py contains Windows CRLF line endings"
E       AssertionError: forensic_check.py contains Windows CRLF line endings
E       assert b'\r\n' not in b'"""Forensic validation and adversarial audit suite for agent metadata and artifacts.\r\n\r\nAudits template content ...))\r\n\r\n    return 0 if report.is_clean else 1\r\n\r\n\r\nif __name__ == "__main__":\r\n    sys.exit(main())\r\n\r\n'

test_suite\test_forensic_check.py:52: AssertionError
________________________________ test_main_cli ________________________________

capsys = <_pytest.capture.CaptureFixture object at 0x000002A625DF8250>

    def test_main_cli(capsys: pytest.CaptureFixture[str]) -> None:
        """Test main CLI entrypoint with JSON output."""
        exit_code = main(["--json"])
>       assert exit_code == 0
E       assert 1 == 0

test_suite\test_forensic_check.py:224: AssertionError
---------------------------- Captured stdout call -----------------------------
{
  "timestamp": "2026-08-21T22:08:13.704132+00:00",
  "content_match": {
    "source_count": 0,
    "target_count": 0,
    "passed_count": 0,
    "failed_count": 0,
    "missing_count": 0,
    "is_clean": true,
    "details": [
      {
        "file_name": "<ALL>",
        "status": "SKIPPED",
        "message": "Source template directory does not exist: C:\\Users\\ansac\\.gemini\\config\\agents"
      }
    ]
  },
  "agent_leak_scan": {
    "files_scanned": 15,
    "leak_count": 0,
    "is_clean": true,
    "leaks": []
  },
  "subdirectory_leak_scan": {
    "files_scanned": 61,
    "leak_count": 81,
    "is_clean": false,
    "leaks": [
      {
        "file_rel_path": "orchestrator\\handoff.md",
        "line_number": 24,
        "line_content": "| **R1. Overwrite Existing Agents**: Copy fixed agent files from `C:\\Users\\ansac\\.gemini\\config\\agents` and overwrite files in `CoChem-BASE/.agents` | **PASSED** | Reviewer 1, Reviewer 2, Challenger 2, and Forensic Auditor confirmed 100% 1:1 character parity modulo sanitization tags across all 15 `.agent.md` files |",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "orchestrator\\handoff.md",
        "line_number": 25,
        "line_content": "| **R2. Sanitize Absolute Paths**: Replace `C:\\Users\\ansac` with `<USER_HOME>`, `D:\\Gdrive\\__CoChem` with `<COCHEM_WORKSPACE>`, and `D:\\Gdrive` with `<GDRIVE_ROOT>` | **PASSED** | All personal absolute path references replaced across all 15 `.agent.md` files and metadata markdown files |",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "orchestrator\\handoff.md",
        "line_number": 26,
        "line_content": "| **Search Criterion 1**: `C:\\Users\\ansac` search inside `CoChem-BASE/.agents` returns 0 results | **PASSED** | Powershell & ripgrep recursive search across all files in `.agents` returned **0 matches** (verified by Worker 1, Challenger 1, Reviewer 2, Auditor 1) |",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "orchestrator\\PROJECT.md",
        "line_number": 5,
        "line_content": "- Source Directory: `C:\\Users\\ansac\\.gemini\\config\\agents`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "orchestrator\\PROJECT.md",
        "line_number": 8,
        "line_content": "- `C:\\Users\\ansac` / `C:/Users/ansac` -> `<USER_HOME>`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "orchestrator\\PROJECT.md",
        "line_number": 8,
        "line_content": "- `C:\\Users\\ansac` / `C:/Users/ansac` -> `<USER_HOME>`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "orchestrator\\PROJECT.md",
        "line_number": 17,
        "line_content": "| 2 | Agent Config Path Sanitization | Sanitize all absolute personal paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`) in `.agent.md` files | M1 | Survey |",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "orchestrator\\PROJECT.md",
        "line_number": 19,
        "line_content": "| 4 | Verification & Audit | Verify file match, path sanitization, and 0 search hits for `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` via Reviewers, Challengers, and Forensic Auditor | M2 | Survey |",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "sentinel\\handoff.md",
        "line_number": 7,
        "line_content": "1. Project Orchestrator dispatched and coordinated 9 subagent workers/explorers/reviewers to overwrite files and sanitize absolute paths (`C:\\Users\\ansac` -> `<USER_HOME>`, `D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "sentinel\\handoff.md",
        "line_number": 21,
        "line_content": "- Search for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\BRIEFING.md",
        "line_number": 40,
        "line_content": "- **Hypotheses tested**: Checked for username `ansac`, user home `C:\\Users\\ansac`, workspace `D:\\Gdrive\\__CoChem`, drive letters `C:`, `D:`, URL-encoded `%3A`, `%61%6e%73%61%63`, backslash escaped paths.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\challenge.md",
        "line_number": 25,
        "line_content": "### 2. User Home Path Leak Test (`C:\\Users\\ansac`, `c:/users/ansac`)",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\challenge.md",
        "line_number": 25,
        "line_content": "### 2. User Home Path Leak Test (`C:\\Users\\ansac`, `c:/users/ansac`)",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\challenge.md",
        "line_number": 50,
        "line_content": "- **Verification Method**: Programmatic line-by-line file comparison between source agent templates in `C:\\Users\\ansac\\.gemini\\config\\agents` and `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\DISPATCH.md",
        "line_number": 10,
        "line_content": "- Case-insensitive variants of `C:\\Users\\ansac`, `c:/users/ansac`, `ansac`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\DISPATCH.md",
        "line_number": 10,
        "line_content": "- Case-insensitive variants of `C:\\Users\\ansac`, `c:/users/ansac`, `ansac`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\handoff.md",
        "line_number": 8,
        "line_content": "- `pwsh -File test_diff_against_source.ps1`: Line-by-line comparison between `C:\\Users\\ansac\\.gemini\\config\\agents` and `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\handoff.md",
        "line_number": 31,
        "line_content": "2. `pwsh -File test_diff_against_source.ps1`: Confirms 0 diffs against source templates in `C:\\Users\\ansac\\.gemini\\config\\agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_1\\test_diff_against_source.ps1",
        "line_number": 1,
        "line_content": "$sourceDir = 'C:\\Users\\ansac\\.gemini\\config\\agents'",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\BRIEFING.md",
        "line_number": 4,
        "line_content": "Empirically verify all 15 `.agent.md` files in `.agents` directory against template source files in `C:\\Users\\ansac\\.gemini\\config\\agents` with exact variable replacement, running verification scripts to check for zero unauthorized modifications or dropped sections.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\BRIEFING.md",
        "line_number": 25,
        "line_content": "- **Source templates**: `C:\\Users\\ansac\\.gemini\\config\\agents`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\BRIEFING.md",
        "line_number": 26,
        "line_content": "- **Replacements**: `<USER_HOME>` -> `C:\\Users\\ansac`, `<COCHEM_WORKSPACE>` -> `D:\\Gdrive\\__CoChem`, `<GDRIVE_ROOT>` -> `D:\\Gdrive`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\BRIEFING.md",
        "line_number": 29,
        "line_content": "- **Hypotheses tested**: Verified text identity between 15 target agent files and source templates after replacing `<USER_HOME>` with `C:\\Users\\ansac`, `<COCHEM_WORKSPACE>` with `D:\\Gdrive\\__CoChem`, and `<GDRIVE_ROOT>` with `D:\\Gdrive`. Checked for residual personal path leaks and dropped sections.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\challenge.md",
        "line_number": 8,
        "line_content": "All 15 `.agent.md` files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` have been empirically verified against their source template counterparts in `C:\\Users\\ansac\\.gemini\\config\\agents`. After variable expansion (`<USER_HOME>` -> `C:\\Users\\ansac`, `<COCHEM_WORKSPACE>` -> `D:\\Gdrive\\__CoChem`, `<GDRIVE_ROOT>` -> `D:\\Gdrive`), all 15 files are 100% character-level identical to the source configurations, with zero unauthorized modifications, zero dropped sections, and 100% path sanitization compliance.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\challenge.md",
        "line_number": 14,
        "line_content": "2. `full_empirical_matrix.py`: Evaluated target variable expansion (`<USER_HOME>` -> `C:\\Users\\ansac`, `<COCHEM_WORKSPACE>` -> `D:\\Gdrive\\__CoChem`, `<GDRIVE_ROOT>` -> `D:\\Gdrive`) vs source, and source path sanitization (`D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`, `C:\\Users\\ansac` -> `<USER_HOME>`) vs target.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\challenge.md",
        "line_number": 16,
        "line_content": "3. `check_sanitization.py`: Performed case-insensitive regex search for residual personal absolute paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\challenge.md",
        "line_number": 22,
        "line_content": "- **Assumption challenged**: Whether template replacement `<USER_HOME>` -> `C:\\Users\\ansac`, `<COCHEM_WORKSPACE>` -> `D:\\Gdrive\\__CoChem`, and `<GDRIVE_ROOT>` -> `D:\\Gdrive` preserves exact text symmetry between source and target files.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\challenge.md",
        "line_number": 35,
        "line_content": "- **Attack scenario**: Hardcoded paths like `C:\\Users\\ansac` or `D:\\Gdrive\\` in target agent files cause failures when executed in different user environments or CI/CD pipelines.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\challenge.md",
        "line_number": 36,
        "line_content": "- **Stress Test Result**: `check_sanitization.py` scanned all 15 target files for `C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, and `D:\\Gdrive`. 0 occurrences found.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\DISPATCH.md",
        "line_number": 9,
        "line_content": "2. Empirically verify that every single one of the 15 `.agent.md` files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` is identical to its counterpart in `C:\\Users\\ansac\\.gemini\\config\\agents` after replacing `<USER_HOME>` with `C:\\Users\\ansac`, `<COCHEM_WORKSPACE>` with `D:\\Gdrive\\__CoChem`, and `<GDRIVE_ROOT>` with `D:\\Gdrive`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\handoff.md",
        "line_number": 5,
        "line_content": "- Source directory inspected: `C:\\Users\\ansac\\.gemini\\config\\agents`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\handoff.md",
        "line_number": 7,
        "line_content": "- Test 2: Expanded target agent files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` (`<COCHEM_WORKSPACE>` -> `D:\\Gdrive\\__CoChem`, `<GDRIVE_ROOT>` -> `D:\\Gdrive`, `<USER_HOME>` -> `C:\\Users\\ansac`) compared against `C:\\Users\\ansac\\.gemini\\config\\agents`. Output: `Test 2 Total Matches: 15 / 15`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\handoff.md",
        "line_number": 8,
        "line_content": "- Test 3: Sanitized source files in `C:\\Users\\ansac\\.gemini\\config\\agents` (`D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`, `C:\\Users\\ansac` -> `<USER_HOME>`) compared against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`. Output: `Test 3 Total Matches: 15 / 15`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\handoff.md",
        "line_number": 10,
        "line_content": "- Case-insensitive search across all 15 target `.agent.md` files for residual strings `C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, and `D:\\Gdrive`. Output: `SANIZATION RESULT: PASS \u2014 Zero personal/absolute paths found in any of the 15 .agent.md files!`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\handoff.md",
        "line_number": 13,
        "line_content": "- **Step 1 (Observation 1)**: All 15 required `.agent.md` files (`0rchestrator`, `artist`, `cochem-audit`, `cochem-coder`, `cochem-debug`, `cochem-helper`, `cochem-improve`, `cochem-scribe`, `cochem-sdp_manager`, `cochem-tester`, `educator`, `researcher`, `teacher`, `ui`, `web_mcp`) exist in both `C:\\Users\\ansac\\.gemini\\config\\agents` and `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\handoff.md",
        "line_number": 14,
        "line_content": "- **Step 2 (Observation 2)**: Variable expansion on target files maps `<COCHEM_WORKSPACE>`, `<GDRIVE_ROOT>`, and `<USER_HOME>` to their corresponding system values (`D:\\Gdrive\\__CoChem`, `D:\\Gdrive`, `C:\\Users\\ansac`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\verification_results.txt",
        "line_number": 2,
        "line_content": "Source Directory: C:\\Users\\ansac\\.gemini\\config\\agents",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_challenger_2\\verification_results.txt",
        "line_number": 5,
        "line_content": "'<USER_HOME>' -> 'C:\\Users\\ansac'",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\BRIEFING.md",
        "line_number": 4,
        "line_content": "Review and stress-test the 15 agent files in D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents against source files in C:\\Users\\ansac\\.gemini\\config\\agents, verifying path sanitization and zero residual absolute paths.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\BRIEFING.md",
        "line_number": 25,
        "line_content": "- **Source comparison**: `C:\\Users\\ansac\\.gemini\\config\\agents`",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\BRIEFING.md",
        "line_number": 35,
        "line_content": "- **Hypotheses tested**: Case sensitivity variations (`c:/users/ansac`, `C:\\Users\\ansac`), slash combinations, YAML header schema validation",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\BRIEFING.md",
        "line_number": 35,
        "line_content": "- **Hypotheses tested**: Case sensitivity variations (`c:/users/ansac`, `C:\\Users\\ansac`), slash combinations, YAML header schema validation",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\DISPATCH.md",
        "line_number": 9,
        "line_content": "2. Inspect the 15 `.agent.md` files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` and compare them against source files in `C:\\Users\\ansac\\.gemini\\config\\agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\DISPATCH.md",
        "line_number": 10,
        "line_content": "3. Verify Acceptance Criteria 1: Confirm that all 15 agent files match the fixed code from `C:\\Users\\ansac\\.gemini\\config\\agents` with path sanitization applied.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\DISPATCH.md",
        "line_number": 11,
        "line_content": "4. Verify Acceptance Criteria 2: Search recursively for `C:\\Users\\ansac` (and variations) inside `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` and confirm 0 results.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\handoff.md",
        "line_number": 15,
        "line_content": "- Source directory `C:\\Users\\ansac\\.gemini\\config\\agents` contains 15 `.agent.md` files:",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\handoff.md",
        "line_number": 20,
        "line_content": "- Executed Python script comparing sanitized source files (`C:\\Users\\ansac` -> `<USER_HOME>`, `D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`) against target files line-by-line using `difflib`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\handoff.md",
        "line_number": 34,
        "line_content": "1. **Observation 1 & 2** establish that all 15 target agent configuration files in `CoChem-BASE\\.agents` accurately reflect the updated, fixed code from `C:\\Users\\ansac\\.gemini\\config\\agents`, fulfilling Requirement R1 and Acceptance Criteria AC1.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\handoff.md",
        "line_number": 35,
        "line_content": "2. **Observation 3** proves that no absolute personal paths (`C:\\Users\\ansac` or `D:\\Gdrive\\__CoChem`) remain in the 15 agent configuration files, fulfilling Requirement R2 and Acceptance Criteria AC2 & AC3.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\handoff.md",
        "line_number": 51,
        "line_content": "The 15 `.agent.md` files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` match the fixed source configuration templates from `C:\\Users\\ansac\\.gemini\\config\\agents` with path sanitization applied, and zero residual personal paths exist.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\handoff.md",
        "line_number": 63,
        "line_content": "source_dir = r'C:\\Users\\ansac\\.gemini\\config\\agents'",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\review.md",
        "line_number": 13,
        "line_content": "All 15 agent configuration files in `CoChem-BASE\\.agents` have been successfully updated to match the fixed configuration templates from `C:\\Users\\ansac\\.gemini\\config\\agents` with 100% fidelity, and all absolute personal directory paths have been completely scrubbed and replaced with environment placeholders (`<USER_HOME>`, `<COCHEM_WORKSPACE>`, `<GDRIVE_ROOT>`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\review.md",
        "line_number": 27,
        "line_content": "- **Claim**: All 15 target `.agent.md` files match the source configuration files from `C:\\Users\\ansac\\.gemini\\config\\agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\review.md",
        "line_number": 32,
        "line_content": "- **Claim**: Zero occurrences of `C:\\Users\\ansac` (or case/slash variants) remain in the 15 agent files.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\review.md",
        "line_number": 49,
        "line_content": "- **Case Sensitivity & Slashes**: Tested `c:/users/ansac`, `C:\\Users\\ansac`, `C:\\\\Users\\\\ansac`, `D:\\Gdrive\\__CoChem`, `d:/gdrive/__cochem`. No residual paths found.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\review.md",
        "line_number": 49,
        "line_content": "- **Case Sensitivity & Slashes**: Tested `c:/users/ansac`, `C:\\Users\\ansac`, `C:\\\\Users\\\\ansac`, `D:\\Gdrive\\__CoChem`, `d:/gdrive/__cochem`. No residual paths found.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_1\\review.md",
        "line_number": 49,
        "line_content": "- **Case Sensitivity & Slashes**: Tested `c:/users/ansac`, `C:\\Users\\ansac`, `C:\\\\Users\\\\ansac`, `D:\\Gdrive\\__CoChem`, `d:/gdrive/__cochem`. No residual paths found.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\BRIEFING.md",
        "line_number": 17,
        "line_content": "- Perform independent search for unsanitized personal user paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\BRIEFING.md",
        "line_number": 39,
        "line_content": "- Verified whether `.agent.md` files match sanitized config templates from `C:\\Users\\ansac\\.gemini\\config\\agents`. (Result: PASS, 15/15 match 100%)",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\DISPATCH.md",
        "line_number": 11,
        "line_content": "3. Perform independent searches across all files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` for any instances of personal user paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\handoff.md",
        "line_number": 30,
        "line_content": "- Independent regex search for `C:\\Users\\ansac`, `C:/Users/ansac`, `D:\\Gdrive\\__CoChem`, `D:/Gdrive/__CoChem`, `D:\\Gdrive`, `D:/Gdrive` across all 15 `.agent.md` files yielded 0 matches.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\handoff.md",
        "line_number": 30,
        "line_content": "- Independent regex search for `C:\\Users\\ansac`, `C:/Users/ansac`, `D:\\Gdrive\\__CoChem`, `D:/Gdrive/__CoChem`, `D:\\Gdrive`, `D:/Gdrive` across all 15 `.agent.md` files yielded 0 matches.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\handoff.md",
        "line_number": 34,
        "line_content": "- Comparison of each `.agent.md` file against sanitized source templates in `C:\\Users\\ansac\\.gemini\\config\\agents` showed a 100% exact match across all 15 files.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\handoff.md",
        "line_number": 42,
        "line_content": "3. **Step 3**: The prompt required performing independent searches across files for personal user paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`) and validating sanitization to `<USER_HOME>`, `<COCHEM_WORKSPACE>`, and `<GDRIVE_ROOT>`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\handoff.md",
        "line_number": 44,
        "line_content": "5. **Step 5**: Executing a 1-to-1 comparison between the files in `CoChem-BASE/.agents` and the templates in `C:\\Users\\ansac\\.gemini\\config\\agents` confirmed that all files were correctly overwritten with the latest fixed code and sanitized.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\handoff.md",
        "line_number": 73,
        "line_content": "- Any occurrence of `C:\\Users\\ansac` or `D:\\Gdrive` in any `.agent.md` file.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\review.md",
        "line_number": 9,
        "line_content": "2. All 15 agent files match 100% identically with the fixed source templates from `C:\\Users\\ansac\\.gemini\\config\\agents` after path sanitization.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\review.md",
        "line_number": 10,
        "line_content": "3. Personal user paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`) have been completely scrubbed from all 15 agent configuration files and sanitized to `<USER_HOME>`, `<COCHEM_WORKSPACE>`, and `<GDRIVE_ROOT>`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "teamwork_preview_reviewer_2\\review.md",
        "line_number": 23,
        "line_content": "| 5 | Zero personal path leaks in `.agent.md` files | Regex search for `C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive` | PASS (0 matches) |",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\audit_report.md",
        "line_number": 17,
        "line_content": "- File Parity: 15 of 15 target `.agent.md` files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` match fixed source files from `C:\\Users\\ansac\\.gemini\\config\\agents` 100% EXPLICITLY (0 line diffs modulo path replacement tags `<USER_HOME>`, `<COCHEM_WORKSPACE>`, and `<GDRIVE_ROOT>`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\audit_report.md",
        "line_number": 18,
        "line_content": "- Search Criterion 1 (`C:\\Users\\ansac`): 0 matches across all 15 deliverable `.agent.md` files and root request file.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\BRIEFING.md",
        "line_number": 38,
        "line_content": "- Verified 0 personal path leaks (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`) inside any deliverable agent file (`.agent.md`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\DISPATCH.md",
        "line_number": 13,
        "line_content": "- Verify files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` match fixed source code from `C:\\Users\\ansac\\.gemini\\config\\agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\DISPATCH.md",
        "line_number": 14,
        "line_content": "- Verify search for `C:\\Users\\ansac` inside `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` returns 0 results.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\handoff.md",
        "line_number": 26,
        "line_content": "- Executed independent Python unified diff script comparing source templates in `C:\\Users\\ansac\\.gemini\\config\\agents` against target files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\handoff.md",
        "line_number": 28,
        "line_content": "- Executed independent Python regex search for personal paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`) inside all deliverable `.agent.md` configuration files.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\handoff.md",
        "line_number": 38,
        "line_content": "- R1 (Overwrite Existing Agents) is PASSED: All 15 agent files match fixed source code from `C:\\Users\\ansac\\.gemini\\config\\agents`.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\handoff.md",
        "line_number": 39,
        "line_content": "- R2 (Sanitize Absolute Paths) is PASSED: All personal user paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`) have been sanitized to standard placeholder tags (`<USER_HOME>`, `<COCHEM_WORKSPACE>`, `<GDRIVE_ROOT>`).",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\handoff.md",
        "line_number": 40,
        "line_content": "- Search Criterion 1 (`C:\\Users\\ansac` search) is PASSED with 0 matches in deliverable `.agent.md` files.",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\handoff.md",
        "line_number": 65,
        "line_content": "python -c \"import os, difflib; s_dir=r'C:\\Users\\ansac\\.gemini\\config\\agents'; t_dir=r'D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents'; print([f for f in os.listdir(s_dir) if f.endswith('.agent.md') if open(os.path.join(t_dir, f)).read() != open(os.path.join(s_dir, f)).read().replace(r'C:\\Users\\ansac', '<USER_HOME>').replace(r'D:\\Gdrive\\__CoChem', '<COCHEM_WORKSPACE>').replace(r'D:\\Gdrive', '<GDRIVE_ROOT>')])\"",
        "placeholder": "<USER_HOME>"
      },
      {
        "file_rel_path": "victory_auditor\\handoff.md",
        "line_number": 71,
        "line_content": "python -c \"import os; t_dir=r'D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents'; print([(f, p) for f in os.listdir(t_dir) if f.endswith('.agent.md') for p in ['C:\\\\Users\\\\ansac', 'D:\\\\Gdrive\\\\__CoChem'] if p.lower() in open(os.path.join(t_dir, f)).read().lower()])\"",
        "placeholder": "<USER_HOME>"
      }
    ]
  },
  "worker_integrity": {
    "workers_checked": 8,
    "clean_workers": 8,
    "is_clean": true,
    "details": [
      {
        "worker_name": "teamwork_preview_challenger_1",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      },
      {
        "worker_name": "teamwork_preview_challenger_2",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      },
      {
        "worker_name": "teamwork_preview_explorer_survey_1",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      },
      {
        "worker_name": "teamwork_preview_explorer_survey_2",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      },
      {
        "worker_name": "teamwork_preview_explorer_survey_3",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      },
      {
        "worker_name": "teamwork_preview_reviewer_1",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      },
      {
        "worker_name": "teamwork_preview_reviewer_2",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      },
      {
        "worker_name": "teamwork_preview_worker_m1",
        "is_clean": true,
        "mock_violations": [],
        "missing_required_files": []
      }
    ]
  },
  "is_clean": false
}
__________________ test_docstring_and_architectural_overview __________________

interfaces_init_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/interfaces/__init__.py')

    def test_docstring_and_architectural_overview(interfaces_init_path: Path) -> None:
        """Verify comprehensive architectural docstring is present on the module."""
        doc = interfaces.__doc__
>       assert doc is not None and len(doc) > 100
E       AssertionError: assert ('Lazy exports for optional browser interface components.' is not None and 55 > 100)
E        +  where 55 = len('Lazy exports for optional browser interface components.')

test_suite\test_interfaces_init.py:52: AssertionError
_______________________ test_module_all_exports_present _______________________

    def test_module_all_exports_present() -> None:
        """Verify __all__ is a sorted list of non-empty public symbols."""
        assert hasattr(interfaces, "__all__")
        assert isinstance(interfaces.__all__, list)
>       assert interfaces.__all__ == sorted(interfaces.__all__)
E       AssertionError: assert ['WebSparsity...'WebGLPacket'] == ['WebGLPacket...arsityMatrix']
E         
E         At index 0 diff: 'WebSparsityMatrix' != 'WebGLPacket'
E         Use -v to get more diff

test_suite\test_interfaces_init.py:63: AssertionError
___________ test_lazy_attribute_resolution[BrowserSparsityPayload] ____________

symbol_name = 'BrowserSparsityPayload'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'BrowserSparsityPayload'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'BrowserSparsityPayload'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_lazy_attribute_resolution[MatrixElement] ________________

symbol_name = 'MatrixElement'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'MatrixElement'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'MatrixElement'

cochem_base\interfaces\__init__.py:18: AttributeError
_____________ test_lazy_attribute_resolution[SparsityDimensions] ______________

symbol_name = 'SparsityDimensions'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'SparsityDimensions'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'SparsityDimensions'

cochem_base\interfaces\__init__.py:18: AttributeError
______________ test_lazy_attribute_resolution[WebSparsityMatrix] ______________

symbol_name = 'WebSparsityMatrix'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
        attr = getattr(interfaces, symbol_name)
        assert attr is not None
        # Verify cached in module dictionary
>       assert symbol_name in interfaces.__dict__
E       AssertionError: assert 'WebSparsityMatrix' in {'Any': typing.Any, '__all__': ['WebSparsityMatrix', 'WebGLStreamer', 'WebGLPacket'], '__builtins__': {'ArithmeticErro...ched__': 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\cochem_base\\interfaces\\__pycache__\\__init__.cpython-313.pyc', ...}
E        +  where {'Any': typing.Any, '__all__': ['WebSparsityMatrix', 'WebGLStreamer', 'WebGLPacket'], '__builtins__': {'ArithmeticErro...ched__': 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\cochem_base\\interfaces\\__pycache__\\__init__.cpython-313.pyc', ...} = interfaces.__dict__

test_suite\test_interfaces_init.py:135: AssertionError
_________________ test_lazy_attribute_resolution[WebGLPacket] _________________

symbol_name = 'WebGLPacket'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
        attr = getattr(interfaces, symbol_name)
        assert attr is not None
        # Verify cached in module dictionary
>       assert symbol_name in interfaces.__dict__
E       AssertionError: assert 'WebGLPacket' in {'Any': typing.Any, '__all__': ['WebSparsityMatrix', 'WebGLStreamer', 'WebGLPacket'], '__builtins__': {'ArithmeticErro...ched__': 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\cochem_base\\interfaces\\__pycache__\\__init__.cpython-313.pyc', ...}
E        +  where {'Any': typing.Any, '__all__': ['WebSparsityMatrix', 'WebGLStreamer', 'WebGLPacket'], '__builtins__': {'ArithmeticErro...ched__': 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\cochem_base\\interfaces\\__pycache__\\__init__.cpython-313.pyc', ...} = interfaces.__dict__

test_suite\test_interfaces_init.py:135: AssertionError
________________ test_lazy_attribute_resolution[WebGLStreamer] ________________

symbol_name = 'WebGLStreamer'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
        attr = getattr(interfaces, symbol_name)
        assert attr is not None
        # Verify cached in module dictionary
>       assert symbol_name in interfaces.__dict__
E       AssertionError: assert 'WebGLStreamer' in {'Any': typing.Any, '__all__': ['WebSparsityMatrix', 'WebGLStreamer', 'WebGLPacket'], '__builtins__': {'ArithmeticErro...ched__': 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\cochem_base\\interfaces\\__pycache__\\__init__.cpython-313.pyc', ...}
E        +  where {'Any': typing.Any, '__all__': ['WebSparsityMatrix', 'WebGLStreamer', 'WebGLPacket'], '__builtins__': {'ArithmeticErro...ched__': 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\cochem_base\\interfaces\\__pycache__\\__init__.cpython-313.pyc', ...} = interfaces.__dict__

test_suite\test_interfaces_init.py:135: AssertionError
_______________ test_lazy_attribute_resolution[TelemetryEvent] ________________

symbol_name = 'TelemetryEvent'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'TelemetryEvent'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'TelemetryEvent'

cochem_base\interfaces\__init__.py:18: AttributeError
_____________________ test_lazy_attribute_resolution[app] _____________________

symbol_name = 'app'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'app'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'app'

cochem_base\interfaces\__init__.py:18: AttributeError
__________________ test_lazy_attribute_resolution[dock_app] ___________________

symbol_name = 'dock_app'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'dock_app'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'dock_app'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_lazy_attribute_resolution[health_check] _________________

symbol_name = 'health_check'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'health_check'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'health_check'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_lazy_attribute_resolution[lttb_decimate] ________________

symbol_name = 'lttb_decimate'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'lttb_decimate'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'lttb_decimate'

cochem_base\interfaces\__init__.py:18: AttributeError
_____________ test_lazy_attribute_resolution[websocket_telemetry] _____________

symbol_name = 'websocket_telemetry'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'websocket_telemetry'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'websocket_telemetry'

cochem_base\interfaces\__init__.py:18: AttributeError
_________________ test_lazy_attribute_resolution[AxisLayout] __________________

symbol_name = 'AxisLayout'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'AxisLayout'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'AxisLayout'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_lazy_attribute_resolution[PlotlyLayout] _________________

symbol_name = 'PlotlyLayout'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'PlotlyLayout'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'PlotlyLayout'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_lazy_attribute_resolution[PlotlyPayload] ________________

symbol_name = 'PlotlyPayload'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'PlotlyPayload'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'PlotlyPayload'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_lazy_attribute_resolution[ScatterTrace] _________________

symbol_name = 'ScatterTrace'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'ScatterTrace'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'ScatterTrace'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_lazy_attribute_resolution[get_spectrum] _________________

symbol_name = 'get_spectrum'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'get_spectrum'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'get_spectrum'

cochem_base\interfaces\__init__.py:18: AttributeError
___________________ test_lazy_attribute_resolution[router] ____________________

symbol_name = 'router'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'router'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'router'

cochem_base\interfaces\__init__.py:18: AttributeError
_______________ test_lazy_attribute_resolution[visuals_router] ________________

symbol_name = 'visuals_router'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'visuals_router'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'visuals_router'

cochem_base\interfaces\__init__.py:18: AttributeError
_______________ test_lazy_attribute_resolution[FastPassWidget] ________________

symbol_name = 'FastPassWidget'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'FastPassWidget'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'FastPassWidget'

cochem_base\interfaces\__init__.py:18: AttributeError
__________________ test_lazy_attribute_resolution[HAS_3DMOL] __________________

symbol_name = 'HAS_3DMOL'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'HAS_3DMOL'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'HAS_3DMOL'

cochem_base\interfaces\__init__.py:18: AttributeError
_______________ test_lazy_attribute_resolution[PubChemProperty] _______________

symbol_name = 'PubChemProperty'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'PubChemProperty'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'PubChemProperty'

cochem_base\interfaces\__init__.py:18: AttributeError
____________ test_lazy_attribute_resolution[PubChemPropertyTable] _____________

symbol_name = 'PubChemPropertyTable'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'PubChemPropertyTable'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'PubChemPropertyTable'

cochem_base\interfaces\__init__.py:18: AttributeError
_______________ test_lazy_attribute_resolution[PubChemResponse] _______________

symbol_name = 'PubChemResponse'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'PubChemResponse'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'PubChemResponse'

cochem_base\interfaces\__init__.py:18: AttributeError
_____________ test_lazy_attribute_resolution[DeploymentManifest] ______________

symbol_name = 'DeploymentManifest'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'DeploymentManifest'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'DeploymentManifest'

cochem_base\interfaces\__init__.py:18: AttributeError
_____________ test_lazy_attribute_resolution[ECOSYSTEM_REGISTRY] ______________

symbol_name = 'ECOSYSTEM_REGISTRY'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'ECOSYSTEM_REGISTRY'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'ECOSYSTEM_REGISTRY'

cochem_base\interfaces\__init__.py:18: AttributeError
______________ test_lazy_attribute_resolution[SynapInstallerGUI] ______________

symbol_name = 'SynapInstallerGUI'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "BrowserSparsityPayload",
            "MatrixElement",
            "SparsityDimensions",
            "WebSparsityMatrix",
            "WebGLPacket",
            "WebGLStreamer",
            "TelemetryEvent",
            "app",
            "dock_app",
            "health_check",
            "lttb_decimate",
            "websocket_telemetry",
            "AxisLayout",
            "PlotlyLayout",
            "PlotlyPayload",
            "ScatterTrace",
            "get_spectrum",
            "router",
            "visuals_router",
            "FastPassWidget",
            "HAS_3DMOL",
            "PubChemProperty",
            "PubChemPropertyTable",
            "PubChemResponse",
            "DeploymentManifest",
            "ECOSYSTEM_REGISTRY",
            "SynapInstallerGUI",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(interfaces, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'SynapInstallerGUI'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'SynapInstallerGUI'

cochem_base\interfaces\__init__.py:18: AttributeError
______________________ test_aliased_exports_equivalence _______________________

    def test_aliased_exports_equivalence() -> None:
        """Verify alias exports resolve to identical underlying objects."""
>       assert interfaces.dock_app is interfaces.app
               ^^^^^^^^^^^^^^^^^^^

test_suite\test_interfaces_init.py:140: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'dock_app'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'dock_app'

cochem_base\interfaces\__init__.py:18: AttributeError
________________ test_dir_reflection_contains_all_and_globals _________________

    def test_dir_reflection_contains_all_and_globals() -> None:
        """Verify __dir__() lists all public exports and module globals."""
        dir_symbols = dir(interfaces)
        for sym in interfaces.__all__:
            assert sym in dir_symbols, f"Symbol '{sym}' missing from dir(interfaces)"
>       assert "__all__" in dir_symbols
E       AssertionError: assert '__all__' in ['WebGLPacket', 'WebGLStreamer', 'WebSparsityMatrix']

test_suite\test_interfaces_init.py:156: AssertionError
________________ test_assertions_file_encoding_and_lf_endings _________________

assertions_source_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/math/assertions.py')

    def test_assertions_file_encoding_and_lf_endings(assertions_source_path: Path) -> None:
        """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
        raw = assertions_source_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/assertions.py"
E       AssertionError: Found Windows CRLF (\r\n) line endings in math/assertions.py
E       assert b'\r\n' not in b'"""Floating-point numerical assertion utilities and continuous variable wrappers.\r\n\r\nIntercepts exact floating-p... "DEFAULT_RTOL",\r\n    "MachineEpsilonWarning",\r\n    "SimulationTensor",\r\n    "assert_allclose_eps",\r\n]\r\n\r\n'

test_suite\test_math_assertions.py:34: AssertionError
_________________ test_autograd_file_encoding_and_lf_endings __________________

autograd_source_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/math/autograd.py')

    def test_autograd_file_encoding_and_lf_endings(autograd_source_path: Path) -> None:
        """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
        raw = autograd_source_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/autograd.py"
E       AssertionError: Found Windows CRLF (\r\n) line endings in math/autograd.py
E       assert b'\r\n' not in b'"""Physical Electrostatics and Dual-Number Forward-Mode Automatic Differentiation Engine.\r\n\r\nImplements Coulomb ...n    "coulomb_gradient",\r\n    "coulomb_potential",\r\n    "dual_gradient",\r\n    "numerical_gradient",\r\n]\r\n\r\n'

test_suite\test_math_autograd.py:42: AssertionError
____________________ test_coulomb_field_and_force_wrappers ____________________

    def test_coulomb_field_and_force_wrappers() -> None:
        """Verify high-level coulomb_field and coulomb_force convenience functions."""
        q = ELEMENTARY_CHARGE
        ex, ey, ez = coulomb_field(q, dx=1e-9, dy=0.0, dz=0.0)
        assert ex > 0.0
        assert ey == 0.0
        assert ez == 0.0
    
        pos1 = (0.0, 0.0, 0.0)
        pos2 = (1e-9, 0.0, 0.0)
        fx, fy, fz = coulomb_force(q, q, pos1=pos1, pos2=pos2)
>       assert fx > 0.0
E       assert -2.3070775523517024e-10 > 0.0

test_suite\test_math_autograd.py:160: AssertionError
______________ test_dual_number_powers_and_elementary_functions _______________

    def test_dual_number_powers_and_elementary_functions() -> None:
        """Verify DualNumber powers, sqrt, exp, log, sin, and cos derivatives."""
        # Power rule: d/dx (x^3) at x=2 -> 3 * 2^2 = 12
        x = DualNumber(2.0, 1.0)
        p = x**3
        assert p.real == 8.0
        assert p.dual == 12.0
    
        # Power rule at zero real part
        z = DualNumber(0.0, 1.0)
        pz = z**2
        assert pz.real == 0.0
        assert pz.dual == 0.0
    
>       with pytest.raises(ValueError, match="Derivative undefined for non-positive power at zero"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE <class 'ValueError'>

test_suite\test_math_autograd.py:242: Failed
________________ test_c_bindings_file_encoding_and_lf_endings _________________

c_bindings_source_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/math/c_bindings.py')

    def test_c_bindings_file_encoding_and_lf_endings(c_bindings_source_path: Path) -> None:
        """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
        raw = c_bindings_source_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/c_bindings.py"
E       AssertionError: Found Windows CRLF (\r\n) line endings in math/c_bindings.py
E       assert b'\r\n' not in b'import ctypes\r\nfrom typing import Any\r\n\r\n\r\nclass SafeCBuffer:\r\n    """\r\n    A robust ctypes wrapper repr...ernel integration.\r\n        """\r\n        return ctypes.cast(self._buffer, ctypes.POINTER(ctypes.c_double))\r\n\r\n'

test_suite\test_math_c_bindings.py:32: AssertionError
_______________ test_safe_c_buffer_instantiation_and_properties _______________

    def test_safe_c_buffer_instantiation_and_properties() -> None:
        """Verify memory buffer initialization, size, itemsize, byte_size, and ctypes type."""
        buf = SafeCBuffer(10)
        assert buf.size == 10
>       assert len(buf) == 10
               ^^^^^^^^
E       TypeError: object of type 'SafeCBuffer' has no len()

test_suite\test_math_c_bindings.py:54: TypeError
_________________ test_safe_c_buffer_invalid_size_validation __________________

    def test_safe_c_buffer_invalid_size_validation() -> None:
        """Verify non-positive and non-integer buffer size allocations raise appropriate exceptions."""
        with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
            SafeCBuffer(0)
    
        with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
            SafeCBuffer(-5)
    
        with pytest.raises(TypeError, match="Buffer size must be an integer"):
>           SafeCBuffer(3.14)  # type: ignore[arg-type]
            ^^^^^^^^^^^^^^^^^

test_suite\test_math_c_bindings.py:69: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.math.c_bindings.SafeCBuffer object at 0x000002A62611B820>
size = 3.14

    def __init__(self, size: int) -> None:
        if size <= 0:
            raise ValueError("Buffer size must be strictly positive.")
        self.size: int = size
>       self._buffer: Any = (ctypes.c_double * size)()
                             ^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: can't multiply sequence by non-int of type 'float'

cochem_base\math\c_bindings.py:14: TypeError

During handling of the above exception, another exception occurred:

    def test_safe_c_buffer_invalid_size_validation() -> None:
        """Verify non-positive and non-integer buffer size allocations raise appropriate exceptions."""
        with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
            SafeCBuffer(0)
    
        with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
            SafeCBuffer(-5)
    
>       with pytest.raises(TypeError, match="Buffer size must be an integer"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: Regex pattern did not match.
E        Regex: 'Buffer size must be an integer'
E        Input: "can't multiply sequence by non-int of type 'float'"

test_suite\test_math_c_bindings.py:68: AssertionError
_________________ test_safe_c_buffer_pointer_and_ctypes_array _________________

    def test_safe_c_buffer_pointer_and_ctypes_array() -> None:
        """Verify raw pointer export and direct ctypes array access."""
        buf = SafeCBuffer(3)
        buf.write(0, 100.5)
        buf.write(1, 200.5)
        buf.write(2, 300.5)
    
        ptr = buf.get_raw_pointer()
        assert bool(ptr)
        assert ptr[0] == 100.5
        assert ptr[1] == 200.5
        assert ptr[2] == 300.5
    
>       ctypes_arr = buf.as_ctypes()
                     ^^^^^^^^^^^^^
E       AttributeError: 'SafeCBuffer' object has no attribute 'as_ctypes'

test_suite\test_math_c_bindings.py:116: AttributeError
______________ test_safe_c_buffer_sequence_protocol_and_indexing ______________

    def test_safe_c_buffer_sequence_protocol_and_indexing() -> None:
        """Verify indexing with positive and negative integer offsets and slicing."""
        buf = SafeCBuffer(5)
        for i in range(5):
>           buf[i] = float(i * 10)
            ^^^^^^
E           TypeError: 'SafeCBuffer' object does not support item assignment

test_suite\test_math_c_bindings.py:125: TypeError
________________ test_safe_c_buffer_slice_and_item_assignment _________________

    def test_safe_c_buffer_slice_and_item_assignment() -> None:
        """Verify slice assignment, size validation, and type checking."""
        buf = SafeCBuffer(5)
>       buf[:] = [1.0, 2.0, 3.0, 4.0, 5.0]
        ^^^^^^
E       TypeError: 'SafeCBuffer' object does not support item assignment

test_suite\test_math_c_bindings.py:157: TypeError
_____________ test_safe_c_buffer_iteration_reversed_and_contains ______________

    def test_safe_c_buffer_iteration_reversed_and_contains() -> None:
        """Verify iter, reversed, and in operators."""
        buf = SafeCBuffer(3)
>       buf[:] = [10.0, 20.0, 30.0]
        ^^^^^^
E       TypeError: 'SafeCBuffer' object does not support item assignment

test_suite\test_math_c_bindings.py:187: TypeError
_________________ test_safe_c_buffer_numpy_zero_copy_and_copy _________________

    def test_safe_c_buffer_numpy_zero_copy_and_copy() -> None:
        """Verify zero-copy view mutations and independent copy array isolation."""
        buf = SafeCBuffer(3)
>       buf[:] = [1.0, 2.0, 3.0]
        ^^^^^^
E       TypeError: 'SafeCBuffer' object does not support item assignment

test_suite\test_math_c_bindings.py:200: TypeError
_______________ test_safe_c_buffer_from_numpy_and_from_iterable _______________

    def test_safe_c_buffer_from_numpy_and_from_iterable() -> None:
        """Verify factory classmethods from_numpy and from_iterable."""
        arr = np.array([3.14, 2.71, 1.41])
>       buf_np = SafeCBuffer.from_numpy(arr)
                 ^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'SafeCBuffer' has no attribute 'from_numpy'

test_suite\test_math_c_bindings.py:222: AttributeError
_____________________ test_safe_c_buffer_fill_clear_copy ______________________

    def test_safe_c_buffer_fill_clear_copy() -> None:
        """Verify fill, clear (memset), and deep copy memory operations."""
        buf = SafeCBuffer(4)
>       buf.fill(7.77)
        ^^^^^^^^
E       AttributeError: 'SafeCBuffer' object has no attribute 'fill'

test_suite\test_math_c_bindings.py:248: AttributeError
_______________ test_safe_c_buffer_representations_and_equality _______________

    def test_safe_c_buffer_representations_and_equality() -> None:
        """Verify __repr__, __str__, and __eq__ comparisons."""
        buf = SafeCBuffer(3)
>       buf[:] = [1.0, 2.0, 3.0]
        ^^^^^^
E       TypeError: 'SafeCBuffer' object does not support item assignment

test_suite\test_math_c_bindings.py:266: TypeError
_________________ test_geometry_file_encoding_and_lf_endings __________________

geometry_source_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/math/geometry.py')

    def test_geometry_file_encoding_and_lf_endings(geometry_source_path: Path) -> None:
        """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
        raw = geometry_source_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/geometry.py"
E       AssertionError: Found Windows CRLF (\r\n) line endings in math/geometry.py
E       assert b'\r\n' not in b'"""Cartesian geometry, 3D Point algebra, and BoundingBox spatial structures.\r\n\r\nImplements CartesianPositivity-0... "dihedral_angle",\r\n    "euclidean_distance",\r\n    "manhattan_distance",\r\n    "radius_of_gyration",\r\n]\r\n\r\n'

test_suite\test_math_geometry.py:41: AssertionError
______________________ test_point_equality_and_closeness ______________________

    def test_point_equality_and_closeness() -> None:
        """Verify Point equality against Point, tuples, lists, NumPy arrays, and tolerances."""
        p = Point(1.0, 2.0, 3.0)
        assert p == Point(1.0, 2.0, 3.0)
        assert p == (1.0, 2.0, 3.0)
        assert p == [1.0, 2.0, 3.0]
>       assert p == np.array([1.0, 2.0, 3.0])
E       assert Point(x=1.0, y=2.0, z=3.0) == array([1., 2., 3.])
E         
E         Use -v to get more diff

test_suite\test_math_geometry.py:187: AssertionError
________________________ test_point_geometric_metrics _________________________

    def test_point_geometric_metrics() -> None:
        """Verify distance_to, squared_distance_to, manhattan_distance_to, chebyshev_distance_to."""
        p1 = Point(0.0, 0.0, 0.0)
        p2 = Point(1.0, 2.0, 2.0)
    
        # Euclidean: sqrt(1^2 + 2^2 + 2^2) = sqrt(9) = 3
        assert math.isclose(p1.distance_to(p2), 3.0)
>       assert math.isclose(p1.squared_distance_to(p2), 9.0)
                            ^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'Point' object has no attribute 'squared_distance_to'

test_suite\test_math_geometry.py:204: AttributeError
_____________________ test_point_dot_cross_midpoint_angle _____________________

    def test_point_dot_cross_midpoint_angle() -> None:
        """Verify dot product, cross product, midpoint, and vector angle computations."""
        vx = Point(1.0, 0.0, 0.0)
        vy = Point(0.0, 1.0, 0.0)
        vz = Point(0.0, 0.0, 1.0)
    
        # Dot product: orthogonal = 0
        assert vx.dot(vy) == 0.0
        assert vx.dot(vx) == 1.0
    
        # Cross product: X � Y = Z
        assert vx.cross(vy) == vz
        assert vy.cross(vz) == vx
        assert vz.cross(vx) == vy
    
        # Midpoint
>       mid = vx.midpoint(vy)
              ^^^^^^^^^^^
E       AttributeError: 'Point' object has no attribute 'midpoint'

test_suite\test_math_geometry.py:239: AttributeError
_________________________ test_point_transformations __________________________

    def test_point_transformations() -> None:
        """Verify Point translate and scale methods."""
        p = Point(1.0, 2.0, 3.0)
>       assert p.translate(10.0, -5.0, 2.0) == Point(11.0, -3.0, 5.0)
               ^^^^^^^^^^^
E       AttributeError: 'Point' object has no attribute 'translate'

test_suite\test_math_geometry.py:257: AttributeError
____________ test_bounding_box_valid_instantiation_and_properties _____________

    def test_bounding_box_valid_instantiation_and_properties() -> None:
        """Verify valid BoundingBox dimensions, center, volume, surface area, and corners."""
        bbox = BoundingBox(
            min_point=Point(0.0, 0.0, 0.0),
            max_point=Point(2.0, 4.0, 6.0),
        )
        assert bbox.dimensions == (2.0, 4.0, 6.0)
>       assert bbox.dx == 2.0
               ^^^^^^^

test_suite\test_math_geometry.py:273: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = BoundingBox(min_point=Point(x=0.0, y=0.0, z=0.0), max_point=Point(x=2.0, y=4.0, z=6.0))
item = 'dx'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'BoundingBox' object has no attribute 'dx'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
___________________ test_file_encoding_and_lf_line_endings ____________________

math_init_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/math/__init__.py')

    def test_file_encoding_and_lf_line_endings(math_init_path: Path) -> None:
        """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
        raw = math_init_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in math/__init__.py"
E       AssertionError: Found Windows CRLF (

E         ) line endings in math/__init__.py
E       assert b'\r\n' not in b'from .assertions import MachineEpsilonWarning, SimulationTensor\r\nfrom .autograd import SingularityError, coulomb_g...  "coulomb_potential",\r\n    "coulomb_gradient",\r\n    "SafeCBuffer",\r\n    "BoundingBox",\r\n    "Point",\r\n]\r\n'

test_suite\test_math_init.py:35: AssertionError
__________________ test_docstring_and_architectural_overview __________________

math_init_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/math/__init__.py')

    def test_docstring_and_architectural_overview(math_init_path: Path) -> None:
        """Verify comprehensive architectural docstring is present on the module."""
        doc = cochem_math.__doc__
>       assert doc is not None and len(doc) > 100
E       assert (None is not None)

test_suite\test_math_init.py:59: AssertionError
_______________________ test_module_all_exports_present _______________________

    def test_module_all_exports_present() -> None:
        """Verify __all__ is a sorted list of non-empty public symbols."""
        assert hasattr(cochem_math, "__all__")
        assert isinstance(cochem_math.__all__, list)
>       assert cochem_math.__all__ == sorted(cochem_math.__all__)
E       AssertionError: assert ['MachineEpsi...CBuffer', ...] == ['BoundingBox...tyError', ...]
E         
E         At index 0 diff: 'MachineEpsilonWarning' != 'BoundingBox'
E         Use -v to get more diff

test_suite\test_math_init.py:70: AssertionError
________________ test_dir_reflection_contains_all_and_globals _________________

    def test_dir_reflection_contains_all_and_globals() -> None:
        """Verify __dir__() lists all public exports and module globals."""
        dir_symbols = dir(cochem_math)
        for sym in cochem_math.__all__:
            assert sym in dir_symbols, f"Symbol '{sym}' missing from dir(cochem_math)"
        assert "__all__" in dir_symbols
>       assert "__getattr__" in dir_symbols
E       AssertionError: assert '__getattr__' in ['BoundingBox', 'MachineEpsilonWarning', 'Point', 'SafeCBuffer', 'SimulationTensor', 'SingularityError', ...]

test_suite\test_math_init.py:121: AssertionError
___________________ test_file_encoding_and_lf_line_endings ____________________

plugins_init_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/plugins/__init__.py')

    def test_file_encoding_and_lf_line_endings(plugins_init_path: Path) -> None:
        """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
        raw = plugins_init_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in plugins/__init__.py"
E       AssertionError: Found Windows CRLF (

E         ) line endings in plugins/__init__.py
E       assert b'\r\n' not in b'"""CoChem-BASE plugins and hooks package."""\r\n'

test_suite\test_plugins_init.py:43: AssertionError
__________________ test_docstring_and_architectural_overview __________________

plugins_init_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/plugins/__init__.py')

    def test_docstring_and_architectural_overview(plugins_init_path: Path) -> None:
        """Verify comprehensive architectural docstring is present on the module."""
        doc = plugins.__doc__
>       assert doc is not None and len(doc) > 100
E       AssertionError: assert ('CoChem-BASE plugins and hooks package.' is not None and 38 > 100)
E        +  where 38 = len('CoChem-BASE plugins and hooks package.')

test_suite\test_plugins_init.py:67: AssertionError
_______________________ test_module_all_exports_present _______________________

    def test_module_all_exports_present() -> None:
        """Verify __all__ is a sorted list of non-empty public symbols."""
>       assert hasattr(plugins, "__all__")
E       AssertionError: assert False
E        +  where False = hasattr(plugins, '__all__')

test_suite\test_plugins_init.py:77: AssertionError
______________ test_lazy_attribute_resolution[CoChemStudioSpecs] ______________

symbol_name = 'CoChemStudioSpecs'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "CoChemStudioSpecs",
            "CorePlugin",
            "get_plugin_manager",
            "hookimpl",
            "hookspec",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(plugins, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute 'CoChemStudioSpecs'

test_suite\test_plugins_init.py:105: AttributeError
_________________ test_lazy_attribute_resolution[CorePlugin] __________________

symbol_name = 'CorePlugin'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "CoChemStudioSpecs",
            "CorePlugin",
            "get_plugin_manager",
            "hookimpl",
            "hookspec",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(plugins, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute 'CorePlugin'

test_suite\test_plugins_init.py:105: AttributeError
_____________ test_lazy_attribute_resolution[get_plugin_manager] ______________

symbol_name = 'get_plugin_manager'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "CoChemStudioSpecs",
            "CorePlugin",
            "get_plugin_manager",
            "hookimpl",
            "hookspec",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(plugins, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute 'get_plugin_manager'

test_suite\test_plugins_init.py:105: AttributeError
__________________ test_lazy_attribute_resolution[hookimpl] ___________________

symbol_name = 'hookimpl'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "CoChemStudioSpecs",
            "CorePlugin",
            "get_plugin_manager",
            "hookimpl",
            "hookspec",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(plugins, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute 'hookimpl'

test_suite\test_plugins_init.py:105: AttributeError
__________________ test_lazy_attribute_resolution[hookspec] ___________________

symbol_name = 'hookspec'

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "CoChemStudioSpecs",
            "CorePlugin",
            "get_plugin_manager",
            "hookimpl",
            "hookspec",
        ],
    )
    def test_lazy_attribute_resolution(symbol_name: str) -> None:
        """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
>       attr = getattr(plugins, symbol_name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute 'hookspec'

test_suite\test_plugins_init.py:105: AttributeError
________________ test_dir_reflection_contains_all_and_globals _________________

    def test_dir_reflection_contains_all_and_globals() -> None:
        """Verify __dir__() lists all public exports and module globals."""
        dir_symbols = dir(plugins)
>       for sym in plugins.__all__:
                   ^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute '__all__'. Did you mean: '__file__'?

test_suite\test_plugins_init.py:121: AttributeError
___________________ test_plugin_manager_lifecycle_and_hooks ___________________

    def test_plugin_manager_lifecycle_and_hooks() -> None:
        """Verify get_plugin_manager configures pluggy with CoChemStudioSpecs."""
>       pm = plugins.get_plugin_manager()
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute 'get_plugin_manager'

test_suite\test_plugins_init.py:130: AttributeError
________________________ test_core_plugin_registration ________________________

qapp = <PySide6.QtWidgets.QApplication(0x2a6294aff60) at 0x000002A62891B900>

    def test_core_plugin_registration(qapp: QApplication) -> None:
        """Verify CorePlugin tab registration hook registers standard backbone tabs."""
>       plugin = plugins.CorePlugin()
                 ^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'cochem_base.plugins' has no attribute 'CorePlugin'

test_suite\test_plugins_init.py:149: AttributeError
_______________ test_internal_file_encoding_and_lf_line_endings _______________

internal_py_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/plugins/internal.py')

    def test_internal_file_encoding_and_lf_line_endings(internal_py_path: Path) -> None:
        """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
        raw = internal_py_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in plugins/internal.py"
E       AssertionError: Found Windows CRLF (\r\n) line endings in plugins/internal.py
E       assert b'\r\n' not in b'"""CorePlugin internal plugin module for CoChem-Studio backbone UI components.\r\n\r\nRegisters the primary core bac...n    "CORE_TAB_TITLES",\r\n    "CORE_TAB_TOPOS_TITLE",\r\n    "CORE_TAB_TORQ_TITLE",\r\n    "CorePlugin",\r\n]\r\n\r\n'

test_suite\test_plugins_internal.py:61: AssertionError
________________ test_internal_docstrings_and_module_overview _________________

    def test_internal_docstrings_and_module_overview() -> None:
        """Verify comprehensive architectural docstrings on module, class, and methods."""
        # Module docstring
        mod_doc = internal_mod.__doc__
        assert mod_doc is not None and len(mod_doc) > 50
        assert "CorePlugin" in mod_doc
        assert "BASE - Hardware Orchestrator" in mod_doc
        assert "TOPOS - Combinatorial Engine" in mod_doc
        assert "TORQ - Quantum Resonance" in mod_doc
    
        # Class docstring
        class_doc = CorePlugin.__doc__
        assert class_doc is not None and len(class_doc) > 20
        assert "backbone" in class_doc.lower() or "plugin" in class_doc.lower()
    
        # Method docstring
        method_doc = CorePlugin.register_tabs.__doc__
        assert method_doc is not None and len(method_doc) > 20
>       assert "main_window" in method_doc
E       AssertionError: assert 'main_window' in 'Register core backbone tabs to the MainWindow tab container.'

test_suite\test_plugins_internal.py:105: AssertionError
________________ test_loader_file_encoding_and_lf_line_endings ________________

loader_py_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/plugins/loader.py')

    def test_loader_file_encoding_and_lf_line_endings(loader_py_path: Path) -> None:
        """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
        raw = loader_py_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in plugins/loader.py"
E       AssertionError: Found Windows CRLF (

E         ) line endings in plugins/loader.py
E       assert b'\r\n' not in b'"""Plugin loader and hook specification engine for CoChem Studio (cochem_studio).\r\n\r\nManages pluggy-based plugin...,\r\n    "hookimpl",\r\n    "hookspec",\r\n    "inject_plugin_path",\r\n    "resolve_spycfit_plugin_dir",\r\n]\r\n\r\n'

test_suite\test_plugins_loader.py:56: AssertionError
_________________ test_loader_docstrings_and_module_overview __________________

    def test_loader_docstrings_and_module_overview() -> None:
        """Verify comprehensive architectural docstrings on module, class, and functions."""
        # Module docstring
        mod_doc = loader_mod.__doc__
        assert mod_doc is not None and len(mod_doc) > 100
>       assert "CoChemStudioSpecs" in mod_doc
E       AssertionError: assert 'CoChemStudioSpecs' in 'Plugin loader and hook specification engine for CoChem Studio (cochem_studio).\n\nManages pluggy-based plugin lifecyc...ions like CoChem-SpycFit.\nFunctions include get_plugin_manager, resolve_spycfit_plugin_dir, and inject_plugin_path.\n'

test_suite\test_plugins_loader.py:87: AssertionError
________________ test_run_tests_file_integrity_and_lf_endings _________________

target_file_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/test_suite/run_tests.py')

    def test_run_tests_file_integrity_and_lf_endings(target_file_path: Path) -> None:
        """Validate that run_tests.py uses UTF-8 encoding and strictly LF line endings."""
        raw_bytes = target_file_path.read_bytes()
>       assert b"\r\n" not in raw_bytes, "CRLF line endings detected in run_tests.py!"
E       AssertionError: CRLF line endings detected in run_tests.py!
E       assert b'\r\n' not in b'import json\r\nimport logging\r\nimport os\r\nimport atexit\r\nfrom pathlib import Path\r\nfrom typing import Any, D...r\n        logger.error(f"Fatal error running preflight checks: {e}")\r\n        import sys\r\n        sys.exit(1)\r\n'

test_suite\test_run_tests.py:37: AssertionError
______________________ test_test_result_model_validation ______________________

    def test_test_result_model_validation() -> None:
        """Validate TestResult Pydantic schema serialization and attributes."""
        res_pass = TestResult(status=True, message="All checks passed successfully.")
        assert res_pass.status is True
        assert res_pass.message == "All checks passed successfully."
>       assert res_pass.provenance_error_code is None
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_run_tests.py:49: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = TestResult(status=True, message='All checks passed successfully.')
item = 'provenance_error_code'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'TestResult' object has no attribute 'provenance_error_code'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
___________________ test_direct_script_subprocess_execution ___________________

    def test_direct_script_subprocess_execution() -> None:
        """Validate direct CLI execution of run_tests.py via subprocess."""
        script_path = Path(__file__).resolve().parent / "run_tests.py"
        repo_root = script_path.parent.parent
>       result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )

test_suite\test_run_tests.py:144: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

input = None, capture_output = True, timeout = 15, check = True
popenargs = (['C:\\Users\\ansac\\anaconda3\\python.exe', 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\test_suite\\run_tests.py'],)
kwargs = {'cwd': 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE', 'stderr': -1, 'stdout': -1, 'text': True}
process = <Popen: returncode: 1 args: ['C:\\Users\\ansac\\anaconda3\\python.exe', 'D:\...>
stdout = ''
stderr = 'Traceback (most recent call last):\n  File "D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\test_suite\\run_tests.py", line 1...\n    from cochem_base.config_loader import resolve_executable\nModuleNotFoundError: No module named \'cochem_base\'\n'
retcode = 1

    def run(*popenargs,
            input=None, capture_output=False, timeout=None, check=False, **kwargs):
        """Run command with arguments and return a CompletedProcess instance.
    
        The returned instance will have attributes args, returncode, stdout and
        stderr. By default, stdout and stderr are not captured, and those attributes
        will be None. Pass stdout=PIPE and/or stderr=PIPE in order to capture them,
        or pass capture_output=True to capture both.
    
        If check is True and the exit code was non-zero, it raises a
        CalledProcessError. The CalledProcessError object will have the return code
        in the returncode attribute, and output & stderr attributes if those streams
        were captured.
    
        If timeout (seconds) is given and the process takes too long,
         a TimeoutExpired exception will be raised.
    
        There is an optional argument "input", allowing you to
        pass bytes or a string to the subprocess's stdin.  If you use this argument
        you may not also use the Popen constructor's "stdin" argument, as
        it will be used internally.
    
        By default, all communication is in bytes, and therefore any "input" should
        be bytes, and the stdout and stderr will be bytes. If in text mode, any
        "input" should be a string, and stdout and stderr will be strings decoded
        according to locale encoding, or by "encoding" if set. Text mode is
        triggered by setting any of text, encoding, errors or universal_newlines.
    
        The other arguments are the same as for the Popen constructor.
        """
        if input is not None:
            if kwargs.get('stdin') is not None:
                raise ValueError('stdin and input arguments may not both be used.')
            kwargs['stdin'] = PIPE
    
        if capture_output:
            if kwargs.get('stdout') is not None or kwargs.get('stderr') is not None:
                raise ValueError('stdout and stderr arguments may not be used '
                                 'with capture_output.')
            kwargs['stdout'] = PIPE
            kwargs['stderr'] = PIPE
    
        with Popen(*popenargs, **kwargs) as process:
            try:
                stdout, stderr = process.communicate(input, timeout=timeout)
            except TimeoutExpired as exc:
                process.kill()
                if _mswindows:
                    # Windows accumulates the output in a single blocking
                    # read() call run on child threads, with the timeout
                    # being done in a join() on those threads.  communicate()
                    # _after_ kill() is required to collect that and add it
                    # to the exception.
                    exc.stdout, exc.stderr = process.communicate()
                else:
                    # POSIX _communicate already populated the output so
                    # far into the TimeoutExpired exception.
                    process.wait()
                raise
            except:  # Including KeyboardInterrupt, communicate handled that.
                process.kill()
                # We don't call process.wait() as .__exit__ does that for us.
                raise
            retcode = process.poll()
            if check and retcode:
>               raise CalledProcessError(retcode, process.args,
                                         output=stdout, stderr=stderr)
E               subprocess.CalledProcessError: Command '['C:\\Users\\ansac\\anaconda3\\python.exe', 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\test_suite\\run_tests.py']' returned non-zero exit status 1.

C:\Users\ansac\anaconda3\Lib\subprocess.py:577: CalledProcessError
____________ test_sentinel_briefing_path_sanitization_and_no_leaks ____________

sentinel_briefing_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/BRIEFING.md')

    def test_sentinel_briefing_path_sanitization_and_no_leaks(sentinel_briefing_path: Path) -> None:
        """Validate that sentinel/BRIEFING.md contains zero personal path leaks and uses standard tokens."""
        content = sentinel_briefing_path.read_text(encoding="utf-8")
        leaks = find_path_leaks(content)
        assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in sentinel/BRIEFING.md: {leaks}"
    
        assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in BRIEFING.md"
        assert "<USER_HOME>" in content, "Expected <USER_HOME> placeholder token in BRIEFING.md"
>       assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token in BRIEFING.md"
E       AssertionError: Expected <GDRIVE_ROOT> placeholder token in BRIEFING.md
E       assert '<GDRIVE_ROOT>' in '# BRIEFING � 2026-08-11T18:00:45Z\n\n## Mission\nFix CoChem-Antigravity sanitized agents by overwriting with fixed co...tifact Index\n- <COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\ORIGINAL_REQUEST.md � Original request record\n'

test_suite\test_sentinel_briefing_spec.py:34: AssertionError
_______________ test_sentinel_handoff_zero_personal_path_leaks ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_zero_personal_path_leaks(target_file: Path) -> None:
        """Verify zero personal/machine path leakage across the entire document."""
        content = target_file.read_text(encoding="utf-8")
        leaks = find_path_leaks(content)
>       assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
E       AssertionError: Detected 2 path leak(s): [(7, '<USER_HOME>', '1. Project Orchestrator dispatched and coordinated 9 subagent workers/explorers/reviewers to overwrite files and sanitize absolute paths (`C:\\Users\\ansac` -> `<USER_HOME>`, `D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`).'), (21, '<USER_HOME>', '- Search for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.')]
E       assert 2 == 0
E        +  where 2 = len([(7, '<USER_HOME>', '1. Project Orchestrator dispatched and coordinated 9 subagent workers/explorers/reviewers to over...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.')])

test_suite\test_sentinel_handoff_spec.py:59: AssertionError
_______________ test_sentinel_handoff_canonical_tokens_present ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized."""
        content = target_file.read_text(encoding="utf-8")
        for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
>           assert token in content, f"Missing canonical token: {token}"
E           AssertionError: Missing canonical token: <COCHEM_ROOT>
E           assert '<COCHEM_ROOT>' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

test_suite\test_sentinel_handoff_spec.py:66: AssertionError
______________ test_sentinel_handoff_canonical_sections_present _______________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections are present in sentinel/handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Mission Directives & Sentinel Swarm Oversight",
            "## 4. Milestone Lifecycle & Multi-Phase Victory Audit Verification",
            "## 5. Subagent Swarm Roster, Gate Consensus & 15-Agent Inventory",
            "## 6. Acceptance Criteria, Quality Gates & Method Matrix Verification",
            "## 7. Key Oversight Artifacts, Cleanup Actions & Final Sign-off Protocol",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Document Control, Metadata & Classification
E           assert '## 1. Document Control, Metadata & Classification' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

test_suite\test_sentinel_handoff_spec.py:84: AssertionError
_______________ test_sentinel_handoff_identity_and_audit_fields _______________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_identity_and_audit_fields(target_file: Path) -> None:
        """Verify Sentinel identity, Orchestrator ID, and Victory Auditor fields."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "sentinel" in content
E       AssertionError: assert 'sentinel' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

test_suite\test_sentinel_handoff_spec.py:91: AssertionError
____________ test_sentinel_handoff_15_agent_inventory_completeness ____________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_15_agent_inventory_completeness(target_file: Path) -> None:
        """Verify all 15 agents are documented in the handoff inventory."""
        content = target_file.read_text(encoding="utf-8")
    
        expected_agents = [
            "0rchestrator.agent.md",
            "artist.agent.md",
            "cochem-audit.agent.md",
            "cochem-coder.agent.md",
            "cochem-debug.agent.md",
            "cochem-helper.agent.md",
            "cochem-improve.agent.md",
            "cochem-scribe.agent.md",
            "cochem-sdp_manager.agent.md",
            "cochem-tester.agent.md",
            "educator.agent.md",
            "researcher.agent.md",
            "teacher.agent.md",
            "ui.agent.md",
            "web_mcp.agent.md",
        ]
    
        for agent in expected_agents:
>           assert agent in content, f"Missing agent reference in inventory: {agent}"
E           AssertionError: Missing agent reference in inventory: 0rchestrator.agent.md
E           assert '0rchestrator.agent.md' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

test_suite\test_sentinel_handoff_spec.py:121: AssertionError
__________________ test_sentinel_handoff_directives_coverage __________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_directives_coverage(target_file: Path) -> None:
        """Verify all directives DIR-01 through DIR-05 are registered in sentinel handoff."""
        content = target_file.read_text(encoding="utf-8")
    
        for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
>           assert dir_tag in content, f"Missing directive registration: {dir_tag}"
E           AssertionError: Missing directive registration: DIR-01
E           assert 'DIR-01' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

test_suite\test_sentinel_handoff_spec.py:129: AssertionError
_________________ test_sentinel_handoff_mermaid_syntax_blocks _________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_mermaid_syntax_blocks(target_file: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed in sentinel/handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 2 Mermaid diagrams, found 0
E       assert 0 >= 2
E        +  where 0 = len([])

test_suite\test_sentinel_handoff_spec.py:137: AssertionError
________ test_sentinel_handoff_method_matrix_and_zero_mock_invariants _________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_method_matrix_and_zero_mock_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules and Zero-Mock invariants are specified."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "defgrid1" in content and "defgrid3" in content
E       AssertionError: assert ('defgrid1' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n')

test_suite\test_sentinel_handoff_spec.py:148: AssertionError
____________ test_sentinel_handoff_oversight_artifacts_referenced _____________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_oversight_artifacts_referenced(target_file: Path) -> None:
        """Verify all key sentinel oversight artifacts are referenced."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "ORIGINAL_REQUEST.md" in content
E       AssertionError: assert 'ORIGINAL_REQUEST.md' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

test_suite\test_sentinel_handoff_spec.py:160: AssertionError
_______________________ test_new_install_default_paths ________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_new_install_default_paths0')

    def test_new_install_default_paths(tmp_path: Path):
        """
        Test [UI Cell 3 - Silo Setup] Test "New Install" -> "Default paths execution"
        Executes the equivalent logic of clicking "New Install" -> "Create & Provision"
        using default paths (via env vars mapped to tmp_path for safety).
        """
        # 1. Setup default paths (mapping to tmp_path to be a real physical structure but safe)
        os.environ['COCHEM_ARTIFACT_DIR'] = str(tmp_path / 'CoChem_Artifacts')
        target_path = resolve_artifact_path(os.environ['COCHEM_ARTIFACT_DIR'])
    
        conda_exe = resolve_conda_executable(required=False)
        if conda_exe:
            os.environ['COCHEM_CONDA_EXE'] = str(conda_exe)
    
        silo_path = target_path / 'Silos'
    
        # Simulate UI Cell 3 "Create & Provision" logic
        if silo_path.exists():
            shutil.rmtree(silo_path, ignore_errors=True)
        silo_path.mkdir(parents=True, exist_ok=True)
    
        # Instead of setup_cochem_base() which creates ipywidgets,
        # we call the actual backend provision_silo function to execute the logic.
        success, env_dir, already_provisioned = provision_silo(str(target_path))
    
>       assert success is True, "Silo provisioning failed."
E       AssertionError: Silo provisioning failed.
E       assert False is True

test_suite\test_silo_setup_pass2.py:40: AssertionError
______________ test_auditor_audit_path_sanitization_and_no_leaks ______________

auditor_audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/audit.md')

    def test_auditor_audit_path_sanitization_and_no_leaks(auditor_audit_path: Path) -> None:
        """Validate that teamwork_preview_auditor_1/audit.md contains zero personal path leaks and uses standard tokens."""
        content = auditor_audit_path.read_text(encoding="utf-8")
        leaks = find_path_leaks(content)
>       assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in teamwork_preview_auditor_1/audit.md: {leaks}"
E       AssertionError: Detected 9 path leak(s) in teamwork_preview_auditor_1/audit.md: [(17, '<USER_HOME>', '1. **Authenticity**: All 15 target `.agent.md` files were genuinely overwritten with the fixed agent configuration files from `C:\\Users\\ansac\\.gemini\\config\\agents`. No mocked code, fake placeholders, or dummy implementations were present.'), (18, '<USER_HOME>', '2. **Regex Execution**: Path sanitization transformations were fully executed on disk. All 15 target files match the source files 100% identically modulo the designated path replacements (`C:\\Users\\ansac` -> `<USER_HOME>`, `D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`).'), (19, '<USER_HOME>', '3. **Path Leak Scan**: Search across all 15 `.agent.md` files for personal user paths (`ansac`, `C:\\Users\\ansac`, `C:/Users/ansac`, `D:\\Gdrive\\__CoChem`, `D:/Gdrive/__CoChem`, `D:\\Gdrive`, `D:/Gdrive`) returned **EXACTLY 0 LEAKS**.'), (20, '<USER_HOME>', "4. **Subdirectory Metadata Audit**: Agent metadata subdirectories contain test scripts (`.py`, `.ps1`) and audit reports (`review.md`, `challenge.md`, `handoff.md`, `progress.md`) created by previous review agents. These files contain test regex patterns (e.g. `re.compile(r'C:\\\\Users\\\\ansac')`) and working directory logs necessary for audit verification, but no target `.agent.md` file contains any un-sanitized paths."), (32, '<USER_HOME>', '| Phase 2.1 | **Target Agent Path Leak Scan** | **PASS** | 0 occurrences of `ansac`, `C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, or `D:\\Gdrive` across all 15 target agent files. |'), (42, '<USER_HOME>', 'The following 15 agent configuration files were audited and verified to match source templates in `C:\\Users\\ansac\\.gemini\\config\\agents` 100% after path replacement:'), (90, '<USER_HOME>', 'Patterns tested: ansac, C:\\Users\\ansac, D:\\Gdrive\\__CoChem, D:\\Gdrive'), (96, '<USER_HOME>', 'Comparing source file `C:\\Users\\ansac\\.gemini\\config\\agents\\0rchestrator.agent.md` vs target `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents\\0rchestrator.agent.md`:'), (99, '<USER_HOME>', '--- C:\\Users\\ansac\\.gemini\\config\\agents\\0rchestrator.agent.md')]
E       assert 9 == 0
E        +  where 9 = len([(17, '<USER_HOME>', '1. **Authenticity**: All 15 target `.agent.md` files were genuinely overwritten with the fixed a... verified to match source templates in `C:\\Users\\ansac\\.gemini\\config\\agents` 100% after path replacement:'), ...])

test_suite\test_teamwork_preview_auditor_1_audit_spec.py:47: AssertionError
________________ test_auditor_audit_mandatory_sections_present ________________

auditor_audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/audit.md')

    def test_auditor_audit_mandatory_sections_present(auditor_audit_path: Path) -> None:
        """Validate that all mandatory canonical forensic sections exist in teamwork_preview_auditor_1/audit.md."""
        content = auditor_audit_path.read_text(encoding="utf-8")
        required_sections = [
            "# Forensic Integrity Audit Report",
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Executive Summary & Verification Scope",
            "## 4. Multi-Phase Forensic Audit Results & Parity Matrix",
            "## 5. Empirical Evidence Chain & Zero-Mock Proofs",
            "## 6. Quantum Chemistry Method Matrix v4 & Anti-Spoof Invariants",
            "## 7. Verification Logs, Final Verdict & Swarm Directorate Sign-off",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in teamwork_preview_auditor_1/audit.md: {section}"
E           AssertionError: Missing required section in teamwork_preview_auditor_1/audit.md: # Forensic Integrity Audit Report
E           assert '# Forensic Integrity Audit Report' in '# Forensic Audit Report � CoChem-Antigravity Agent Sanitization\n\n**Work Product**: `D:\\Gdrive\\__CoChem\\GitHub-Re...tions, facade implementations, hardcoded mock results, or path leaks were found in the 15 agent configuration files.\n'

test_suite\test_teamwork_preview_auditor_1_audit_spec.py:71: AssertionError
________________ test_auditor_audit_identity_and_audit_fields _________________

auditor_audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/audit.md')

    def test_auditor_audit_identity_and_audit_fields(auditor_audit_path: Path) -> None:
        """Validate that teamwork_preview_auditor_1/audit.md has correct identity, parent, and audit verdict."""
        content = auditor_audit_path.read_text(encoding="utf-8")
        assert "teamwork_preview_auditor_1" in content
>       assert "39f39eb0-6bb9-4f9a-b544-6a701d124d30" in content
E       AssertionError: assert '39f39eb0-6bb9-4f9a-b544-6a701d124d30' in '# Forensic Audit Report � CoChem-Antigravity Agent Sanitization\n\n**Work Product**: `D:\\Gdrive\\__CoChem\\GitHub-Re...tions, facade implementations, hardcoded mock results, or path leaks were found in the 15 agent configuration files.\n'

test_suite\test_teamwork_preview_auditor_1_audit_spec.py:78: AssertionError
_________________ test_auditor_audit_mermaid_diagrams_present _________________

auditor_audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/audit.md')

    def test_auditor_audit_mermaid_diagrams_present(auditor_audit_path: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed in teamwork_preview_auditor_1/audit.md."""
        content = auditor_audit_path.read_text(encoding="utf-8")
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 1, f"Expected at least 1 Mermaid diagram, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 1 Mermaid diagram, found 0
E       assert 0 >= 1
E        +  where 0 = len([])

test_suite\test_teamwork_preview_auditor_1_audit_spec.py:112: AssertionError
__________ test_auditor_audit_method_matrix_and_zero_mock_invariants __________

auditor_audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/audit.md')

    def test_auditor_audit_method_matrix_and_zero_mock_invariants(auditor_audit_path: Path) -> None:
        """Verify Method Matrix rules and Zero-Mock invariants are specified in audit.md."""
        content = auditor_audit_path.read_text(encoding="utf-8")
>       assert "defgrid1" in content and "defgrid3" in content
E       AssertionError: assert ('defgrid1' in '# Forensic Audit Report � CoChem-Antigravity Agent Sanitization\n\n**Work Product**: `D:\\Gdrive\\__CoChem\\GitHub-Re...tions, facade implementations, hardcoded mock results, or path leaks were found in the 15 agent configuration files.\n')

test_suite\test_teamwork_preview_auditor_1_audit_spec.py:122: AssertionError
____________ test_auditor_briefing_path_sanitization_and_no_leaks _____________

auditor_briefing_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/BRIEFING.md')

    def test_auditor_briefing_path_sanitization_and_no_leaks(auditor_briefing_path: Path) -> None:
        """Validate that teamwork_preview_auditor_1/BRIEFING.md contains zero personal path leaks and uses standard tokens."""
        content = auditor_briefing_path.read_text(encoding="utf-8")
        leaks = find_path_leaks(content)
        assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in teamwork_preview_auditor_1/BRIEFING.md: {leaks}"
    
>       assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in BRIEFING.md"
E       AssertionError: Expected <COCHEM_WORKSPACE> placeholder token in BRIEFING.md
E       assert '<COCHEM_WORKSPACE>' in '# BRIEFING � 2026-08-11T18:06:50Z\n\n## Mission\nConduct a forensic integrity audit on the work product in `.agents` ... � Detailed Forensic Audit Report\n- handoff.md � 5-Component Handoff Report\n- progress.md � Audit progress tracker\n'

test_suite\test_teamwork_preview_auditor_1_briefing_spec.py:32: AssertionError
_______________ test_auditor_briefing_identity_and_audit_fields _______________

auditor_briefing_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/BRIEFING.md')

    def test_auditor_briefing_identity_and_audit_fields(auditor_briefing_path: Path) -> None:
        """Validate that teamwork_preview_auditor_1/BRIEFING.md has correct identity, parent, and audit verdict."""
        content = auditor_briefing_path.read_text(encoding="utf-8")
        assert "Archetype" in content and "forensic_auditor" in content
        assert "39f39eb0-6bb9-4f9a-b544-6a701d124d30" in content
        assert "CLEAN" in content
>       assert "<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\teamwork_preview_auditor_1" in content
E       AssertionError: assert '<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\teamwork_preview_auditor_1' in '# BRIEFING � 2026-08-11T18:06:50Z\n\n## Mission\nConduct a forensic integrity audit on the work product in `.agents` ... � Detailed Forensic Audit Report\n- handoff.md � 5-Component Handoff Report\n- progress.md � Audit progress tracker\n'

test_suite\test_teamwork_preview_auditor_1_briefing_spec.py:61: AssertionError
____________ test_auditor_dispatch_path_sanitization_and_no_leaks _____________

auditor_dispatch_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/DISPATCH.md')

    def test_auditor_dispatch_path_sanitization_and_no_leaks(auditor_dispatch_path: Path) -> None:
        """Validate that teamwork_preview_auditor_1/DISPATCH.md contains zero personal path leaks and uses standard tokens."""
        content = auditor_dispatch_path.read_text(encoding="utf-8")
        leaks = find_path_leaks(content)
        assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in teamwork_preview_auditor_1/DISPATCH.md: {leaks}"
    
>       assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in DISPATCH.md"
E       AssertionError: Expected <COCHEM_WORKSPACE> placeholder token in DISPATCH.md
E       assert '<COCHEM_WORKSPACE>' in '## 2026-08-11T18:04:23Z\nYou are a Forensic Auditor agent.\nYour working directory: D:\\Gdrive\\__CoChem\\GitHub-Repo...r `INTEGRITY VIOLATION`.\n6. Send a message back to the orchestrator with your verdict and handoff report reference.\n'

test_suite\test_teamwork_preview_auditor_1_dispatch_spec.py:31: AssertionError
______________ test_auditor_dispatch_mandatory_sections_present _______________

auditor_dispatch_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/DISPATCH.md')

    def test_auditor_dispatch_mandatory_sections_present(auditor_dispatch_path: Path) -> None:
        """Validate that all mandatory canonical dispatch directives exist in teamwork_preview_auditor_1/DISPATCH.md."""
        content = auditor_dispatch_path.read_text(encoding="utf-8")
        required_sections = [
            "## 2026-08-11T18:04:23Z",
            "<USER_REQUEST>",
            "You are a Forensic Auditor agent.",
            "Your working directory:",
            "Original Request path:",
            "Instructions:",
            "Check for integrity violations:",
            "audit.md",
            "handoff.md",
            "CLEAN",
            "INTEGRITY VIOLATION",
            "</USER_REQUEST>",
        ]
        for section in required_sections:
>           assert section in content, f"Missing required section in teamwork_preview_auditor_1/DISPATCH.md: {section}"
E           AssertionError: Missing required section in teamwork_preview_auditor_1/DISPATCH.md: <USER_REQUEST>
E           assert '<USER_REQUEST>' in '## 2026-08-11T18:04:23Z\nYou are a Forensic Auditor agent.\nYour working directory: D:\\Gdrive\\__CoChem\\GitHub-Repo...r `INTEGRITY VIOLATION`.\n6. Send a message back to the orchestrator with your verdict and handoff report reference.\n'

test_suite\test_teamwork_preview_auditor_1_dispatch_spec.py:54: AssertionError
________________ test_auditor_dispatch_working_dir_and_targets ________________

auditor_dispatch_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/DISPATCH.md')

    def test_auditor_dispatch_working_dir_and_targets(auditor_dispatch_path: Path) -> None:
        """Validate working directory and target paths in teamwork_preview_auditor_1/DISPATCH.md."""
        content = auditor_dispatch_path.read_text(encoding="utf-8")
>       assert "<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\teamwork_preview_auditor_1" in content
E       AssertionError: assert '<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\teamwork_preview_auditor_1' in '## 2026-08-11T18:04:23Z\nYou are a Forensic Auditor agent.\nYour working directory: D:\\Gdrive\\__CoChem\\GitHub-Repo...r `INTEGRITY VIOLATION`.\n6. Send a message back to the orchestrator with your verdict and handoff report reference.\n'

test_suite\test_teamwork_preview_auditor_1_dispatch_spec.py:60: AssertionError
___________________ test_file_encoding_and_lf_line_endings ____________________

thermo_constants_file_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/io/thermo_constants.py')

    def test_file_encoding_and_lf_line_endings(thermo_constants_file_path: Path) -> None:
        """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
        raw = thermo_constants_file_path.read_bytes()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in thermo_constants.py"
E       AssertionError: Found Windows CRLF (\r\n) line endings in thermo_constants.py
E       assert b'\r\n' not in b'"""Thermodynamic and physical constants, unit converters, and equation of state solvers.\r\n\r\nImplements CODATA 20...o_bar",\r\n    "pascal_to_psi",\r\n    "pascal_to_torr",\r\n    "psi_to_pascal",\r\n    "torr_to_pascal",\r\n]\r\n\r\n'

test_suite\test_thermo_constants.py:127: AssertionError
_______________________ test_thermodynamic_calculations _______________________

    def test_thermodynamic_calculations() -> None:
        """Verify Gibbs free energy, equilibrium constant, and Arrhenius rate kinetics."""
        # Gibbs Free Energy: dG = dH - T * dS
        dH = -50000.0  # -50 kJ/mol (exothermic)
        dS = -100.0   # -100 J/(mol*K)
        T = 298.15    # K
        dG = calculate_gibbs_free_energy(enthalpy_j_mol=dH, entropy_j_mol_k=dS, temperature_k=T)
        assert math.isclose(dG, -50000.0 - 298.15 * (-100.0), rel_tol=1e-9)
        assert dG < 0.0  # Spontaneous
    
        # Equilibrium constant: K = exp(-dG / RT)
        K = calculate_equilibrium_constant(delta_g_j_mol=dG, temperature_k=T)
        expected_k = math.exp(-dG / (MOLAR_GAS_CONSTANT_R * T))
        assert math.isclose(K, expected_k, rel_tol=1e-9)
    
        # Delta G from K: dG = -RT ln(K)
        dG_recovered = calculate_delta_g_from_k(equilibrium_constant_k=K, temperature_k=T)
        assert math.isclose(dG_recovered, dG, rel_tol=1e-9)
    
        # Arrhenius equation: k = A * exp(-E_a / RT)
        A = 1e13  # frequency factor (s^-1)
        E_a = 50000.0  # 50 kJ/mol activation energy
        k_rate = calculate_arrhenius_rate_constant(pre_exponential_a=A, activation_energy_j_mol=E_a, temperature_k=T)
        expected_k_rate = A * math.exp(-E_a / (MOLAR_GAS_CONSTANT_R * T))
        assert math.isclose(k_rate, expected_k_rate, rel_tol=1e-9)
    
        # Thermal energy RT
        rt_kj = calculate_thermal_energy_rt(298.15, unit="kJ/mol")
        assert math.isclose(rt_kj, (8.31446261815324 * 298.15) / 1000.0, rel_tol=1e-9)
    
        rt_kcal = calculate_thermal_energy_rt(298.15, unit="kcal/mol")
        assert math.isclose(rt_kcal, rt_kj / 4.184, rel_tol=1e-9)
    
        rt_ev = calculate_thermal_energy_rt(298.15, unit="eV")
>       assert math.isclose(rt_ev, 0.02569, rel_tol=1e-3)  # ~25.7 meV at room temp
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       assert False
E        +  where False = <built-in function isclose>(4.2663531367018136e-26, 0.02569, rel_tol=0.001)
E        +    where <built-in function isclose> = math.isclose

test_suite\test_thermo_constants.py:334: AssertionError
____________ TestTorqWorkerExecution.test_torq_worker_cancellation ____________

self = <test_suite.test_torq_gui.TestTorqWorkerExecution object at 0x000002A62448DA90>

    def test_torq_worker_cancellation(self) -> None:
        """Verify TorqWorker handles cancellation cleanly and stops progression."""
        cfg = TorqOptimizationConfig(max_cycles=100)
        worker = TorqWorker(config=cfg, step_delay_ms=0)
    
        step_events: list[dict[str, Any]] = []
        worker.step_completed.connect(lambda d: step_events.append(d))
    
        # Request cancellation immediately
        worker.request_stop()
        assert worker.is_cancelled() is True
    
        worker.run()
    
        # Step 0 is emitted during initialization, then loop immediately halts on step 1
>       assert len(step_events) == 1
E       AssertionError: assert 17 == 1
E        +  where 17 = len([{'delta_e_kcal': 0.0, 'energy_hartree': -154.28, 'grid_level': 'defgrid1', 'is_converged': False, ...}, {'delta_e_kca..., {'delta_e_kcal': -0.7446, 'energy_hartree': -154.2914404, 'grid_level': 'defgrid1', 'is_converged': False, ...}, ...])

test_suite\test_torq_gui.py:391: AssertionError
_____ TestTorqTabWidget.test_torq_tab_didactic_toggle_and_topic_selection _____

self = <test_suite.test_torq_gui.TestTorqTabWidget object at 0x000002A62448DD10>
qapp = <PySide6.QtWidgets.QApplication(0x2a6294aff60) at 0x000002A62891B900>

    def test_torq_tab_didactic_toggle_and_topic_selection(self, qapp: QApplication) -> None:
        """Verify didactic math view visibility toggle and topic change rendering."""
        tab = TorqTab()
        assert tab.lbl_didactic.isHidden() is True
    
        tab.toggle_didactic()
        assert tab.lbl_didactic.isHidden() is False
    
        tab.toggle_didactic()
>       assert tab.lbl_didactic.isHidden() is True
E       assert False is True
E        +  where False = <built-in method isHidden of PySide6.QtWidgets.QLabel object at 0x000002A6262B5400>()
E        +    where <built-in method isHidden of PySide6.QtWidgets.QLabel object at 0x000002A6262B5400> = <PySide6.QtWidgets.QLabel(0x2a672778550) at 0x000002A6262B5400>.isHidden
E        +      where <PySide6.QtWidgets.QLabel(0x2a672778550) at 0x000002A6262B5400> = <cochem_base.gui.torq.TorqTab(0x2a6724e5fb0) at 0x000002A6262A77C0>.lbl_didactic

test_suite\test_torq_gui.py:427: AssertionError
___________________ test_file_encoding_and_lf_line_endings ____________________

target_file_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/cochem_base/interfaces/web_matrices.py')
target_test_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/test_suite/test_web_matrices.py')

    def test_file_encoding_and_lf_line_endings(target_file_path: Path, target_test_path: Path) -> None:
        """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
        for file_path in [target_file_path, target_test_path]:
            raw = file_path.read_bytes()
>           assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {file_path.name}"
E           AssertionError: Found Windows CRLF line endings in web_matrices.py
E           assert b'\r\n' not in b'"""\r\nWeb Matrices Module.\r\n\r\nThis module handles the serialization and validation of sparse matrices\r\nfor We...()).decode(\'ascii\'),\r\n            vals_b64=base64.b64encode(vals_arr.tobytes()).decode(\'ascii\')\r\n        )\r\n'

test_suite\test_web_matrices.py:53: AssertionError
___________________________ test_module_all_exports ___________________________

    def test_module_all_exports() -> None:
        """Verify __all__ contains all required classes."""
        import cochem_base.interfaces.web_matrices as wm
    
        expected = ["BrowserSparsityPayload", "MatrixElement", "SparsityDimensions", "WebSparsityMatrix"]
>       assert hasattr(wm, "__all__")
E       AssertionError: assert False
E        +  where False = hasattr(<module 'cochem_base.interfaces.web_matrices' from 'D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\cochem_base\\interfaces\\web_matrices.py'>, '__all__')

test_suite\test_web_matrices.py:80: AssertionError
___________________ test_interfaces_package_lazy_resolution ___________________

    def test_interfaces_package_lazy_resolution() -> None:
        """Verify interfaces package exposes web_matrices symbols via PEP 562."""
        assert interfaces.WebSparsityMatrix is WebSparsityMatrix
>       assert interfaces.BrowserSparsityPayload is BrowserSparsityPayload
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:89: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

name = 'BrowserSparsityPayload'

    def __getattr__(name: str) -> Any:
        if name == "WebSparsityMatrix":
            from .web_matrices import WebSparsityMatrix
            return WebSparsityMatrix
        if name == "WebGLStreamer":
            from .web_streaming import WebGLStreamer
            return WebGLStreamer
        if name == "WebGLPacket":
            from .web_streaming import WebGLPacket
            return WebGLPacket
>       raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
E       AttributeError: module 'cochem_base.interfaces' has no attribute 'BrowserSparsityPayload'

cochem_base\interfaces\__init__.py:18: AttributeError
_______________________ test_sparsity_dimensions_model ________________________

    def test_sparsity_dimensions_model() -> None:
        """Validate SparsityDimensions Pydantic model behavior."""
        dims = SparsityDimensions(rows=10, cols=20)
        assert dims.rows == 10
        assert dims.cols == 20
>       assert dims.total_elements == 200
               ^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:104: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = SparsityDimensions(rows=10, cols=20), item = 'total_elements'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'SparsityDimensions' object has no attribute 'total_elements'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
__________________________ test_matrix_element_model __________________________

    def test_matrix_element_model() -> None:
        """Validate MatrixElement Pydantic model behavior."""
        elem = MatrixElement(row=3, col=4, value=12.75)
        assert elem.row == 3
        assert elem.col == 4
        assert elem.value == 12.75
>       assert elem.coord == (3, 4)
               ^^^^^^^^^^

test_suite\test_web_matrices.py:137: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = MatrixElement(row=3, col=4, value=12.75), item = 'coord'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'MatrixElement' object has no attribute 'coord'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
_____________________ test_browser_sparsity_payload_model _____________________

    def test_browser_sparsity_payload_model() -> None:
        """Validate BrowserSparsityPayload model and base64 operations."""
        dims = SparsityDimensions(rows=4, cols=4)
        payload = BrowserSparsityPayload(
            version="BrowserSparsity-004",
            dimensions=dims,
            rows_b64="",
            cols_b64="",
            vals_b64="",
        )
        assert payload.version == "BrowserSparsity-004"
        assert payload.dimensions.rows == 4
        assert payload.dimensions.cols == 4
    
        # Empty payload decoding
>       r_arr, c_arr, v_arr = payload.decode_coo()
                              ^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:168: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = BrowserSparsityPayload(version='BrowserSparsity-004', dimensions=SparsityDimensions(rows=4, cols=4), rows_b64='', cols_b64='', vals_b64='')
item = 'decode_coo'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'BrowserSparsityPayload' object has no attribute 'decode_coo'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
___________________________ test_matrix_init_empty ____________________________

    def test_matrix_init_empty() -> None:
        """Verify basic matrix construction without initial data."""
        mat = WebSparsityMatrix(rows=5, cols=10)
        assert mat.rows == 5
        assert mat.cols == 10
>       assert mat.shape == (5, 10)
               ^^^^^^^^^
E       AttributeError: 'WebSparsityMatrix' object has no attribute 'shape'

test_suite\test_web_matrices.py:194: AttributeError
_____________________ test_matrix_init_with_dict_elements _____________________

    def test_matrix_init_with_dict_elements() -> None:
        """Verify matrix construction with dictionary elements."""
        data = [
            {"row": 0, "col": 1, "value": 2.5},
            {"row": 3, "col": 4, "value": -1.25},
        ]
        mat = WebSparsityMatrix(rows=5, cols=5, data=data)
>       assert mat.nnz == 2
               ^^^^^^^
E       AttributeError: 'WebSparsityMatrix' object has no attribute 'nnz'

test_suite\test_web_matrices.py:209: AttributeError
_______________ test_matrix_init_with_matrix_element_instances ________________

    def test_matrix_init_with_matrix_element_instances() -> None:
        """Verify matrix construction with MatrixElement instances."""
        data = [
            MatrixElement(row=1, col=2, value=3.14),
            MatrixElement(row=2, col=3, value=2.718),
        ]
>       mat = WebSparsityMatrix(rows=4, cols=4, data=data)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:222: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A622FB5E50>
rows = 4, cols = 4
data = [MatrixElement(row=1, col=2, value=3.14), MatrixElement(row=2, col=3, value=2.718)]

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not MatrixElement

cochem_base\interfaces\web_matrices.py:51: TypeError
________________________ test_matrix_init_with_tuples _________________________

    def test_matrix_init_with_tuples() -> None:
        """Verify matrix construction with 3-tuples (row, col, value)."""
        data = [(0, 0, 1.0), (1, 1, 2.0), (2, 2, 3.0)]
>       mat = WebSparsityMatrix(rows=3, cols=3, data=data)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:231: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A622EDD950>
rows = 3, cols = 3, data = [(0, 0, 1.0), (1, 1, 2.0), (2, 2, 3.0)]

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not tuple

cochem_base\interfaces\web_matrices.py:51: TypeError
________________________ test_matrix_init_invalid_data ________________________

    def test_matrix_init_invalid_data() -> None:
        """Verify matrix construction raises ValueError on invalid data items."""
        with pytest.raises(ValueError, match="Unsupported element data format"):
>           WebSparsityMatrix(rows=3, cols=3, data=["invalid_string"])  # type: ignore[list-item]
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:241: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A62A278550>
rows = 3, cols = 3, data = ['invalid_string']

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not str

cochem_base\interfaces\web_matrices.py:51: TypeError
____________________ test_matrix_init_negative_dimensions _____________________

    def test_matrix_init_negative_dimensions() -> None:
        """Verify matrix construction raises ValueError for negative dimensions."""
>       with pytest.raises(ValueError, match="Matrix dimensions must be non-negative"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE <class 'ValueError'>

test_suite\test_web_matrices.py:249: Failed
___________________________ test_from_dense_factory ___________________________

    def test_from_dense_factory() -> None:
        """Verify construction from 2D dense numpy array and nested lists."""
        dense_arr = np.array([
            [1.0, 0.0, 0.0],
            [0.0, -4.5, 0.0],
            [0.0, 0.0, 9.2],
        ], dtype=np.float32)
    
>       mat = WebSparsityMatrix.from_dense(dense_arr)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'from_dense'

test_suite\test_web_matrices.py:263: AttributeError
____________________________ test_from_coo_factory ____________________________

    def test_from_coo_factory() -> None:
        """Verify construction from coordinate sequences."""
        rows = [0, 1, 2]
        cols = [2, 1, 0]
        vals = [7.5, 8.5, 9.5]
    
        # Inferred shape
>       mat = WebSparsityMatrix.from_coo(rows, cols, vals)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'from_coo'

test_suite\test_web_matrices.py:291: AttributeError
___________________________ test_from_dict_factory ____________________________

    def test_from_dict_factory() -> None:
        """Verify construction from dictionary representations."""
        d = {
            "rows": 4,
            "cols": 6,
            "elements": [
                {"row": 1, "col": 2, "value": 5.0},
                {"row": 3, "col": 5, "value": -3.0},
            ],
        }
>       mat = WebSparsityMatrix.from_dict(d)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'from_dict'

test_suite\test_web_matrices.py:323: AttributeError
____________________________ test_identity_factory ____________________________

    def test_identity_factory() -> None:
        """Verify diagonal identity matrix generation."""
>       eye = WebSparsityMatrix.identity(4)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'identity'

test_suite\test_web_matrices.py:336: AttributeError
________________ test_bounds_validation_get_and_remove_element ________________

    def test_bounds_validation_get_and_remove_element() -> None:
        """Verify get_element and remove_element bounds checks."""
        mat = WebSparsityMatrix(rows=2, cols=2)
        with pytest.raises(ValueError, match="Index out of bounds"):
>           mat.get_element(2, 0)
            ^^^^^^^^^^^^^^^
E           AttributeError: 'WebSparsityMatrix' object has no attribute 'get_element'. Did you mean: 'add_element'?

test_suite\test_web_matrices.py:383: AttributeError
___________________ test_bounds_validation_dunder_indexing ____________________

    def test_bounds_validation_dunder_indexing() -> None:
        """Verify __getitem__, __setitem__, and __delitem__ bounds checks."""
        mat = WebSparsityMatrix(rows=2, cols=2)
    
        with pytest.raises(ValueError, match="Index out of bounds"):
>           _ = mat[2, 0]
                ^^^^^^^^^
E           TypeError: 'WebSparsityMatrix' object is not subscriptable

test_suite\test_web_matrices.py:394: TypeError
_____________________ test_type_error_on_invalid_key_type _____________________

    def test_type_error_on_invalid_key_type() -> None:
        """Verify TypeError when non-2-tuple is provided for indexing."""
        mat = WebSparsityMatrix(rows=3, cols=3)
    
        with pytest.raises(TypeError, match="Index must be a 2-tuple"):
>           _ = mat[0]  # type: ignore[index]
                ^^^^^^
E           TypeError: 'WebSparsityMatrix' object is not subscriptable

test_suite\test_web_matrices.py:408: TypeError

During handling of the above exception, another exception occurred:

    def test_type_error_on_invalid_key_type() -> None:
        """Verify TypeError when non-2-tuple is provided for indexing."""
        mat = WebSparsityMatrix(rows=3, cols=3)
    
>       with pytest.raises(TypeError, match="Index must be a 2-tuple"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: Regex pattern did not match.
E        Regex: 'Index must be a 2-tuple'
E        Input: "'WebSparsityMatrix' object is not subscriptable"

test_suite\test_web_matrices.py:407: AssertionError
______________________ test_dunder_indexing_and_defaults ______________________

    def test_dunder_indexing_and_defaults() -> None:
        """Verify __getitem__ returns stored value or 0.0 default for in-bounds coordinates."""
        mat = WebSparsityMatrix(rows=4, cols=4)
>       mat[1, 2] = 42.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:425: TypeError
____________________________ test_dunder_deletion _____________________________

    def test_dunder_deletion() -> None:
        """Verify __delitem__ removes stored element and raises KeyError for unstored."""
        mat = WebSparsityMatrix(rows=3, cols=3)
>       mat[1, 1] = 10.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:434: TypeError
____________________________ test_dunder_contains _____________________________

    def test_dunder_contains() -> None:
        """Verify __contains__ returns True for stored elements, False otherwise."""
        mat = WebSparsityMatrix(rows=3, cols=3)
>       mat[0, 2] = 7.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:451: TypeError
__________________________ test_dunder_iter_and_len ___________________________

    def test_dunder_iter_and_len() -> None:
        """Verify __iter__ yields sorted elements and __len__ matches nnz."""
        mat = WebSparsityMatrix(rows=3, cols=3)
>       mat[2, 1] = 3.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:462: TypeError
______________________________ test_dunder_repr _______________________________

    def test_dunder_repr() -> None:
        """Verify __repr__ provides clear human-readable structure."""
        mat = WebSparsityMatrix(rows=5, cols=8)
>       mat[1, 1] = 3.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:476: TypeError
_______________________________ test_dunder_eq ________________________________

    def test_dunder_eq() -> None:
        """Verify __eq__ comparison between matrices."""
        mat1 = WebSparsityMatrix(rows=3, cols=3)
>       mat1[0, 1] = 5.0
        ^^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:483: TypeError
____________________ test_density_and_is_empty_properties _____________________

    def test_density_and_is_empty_properties() -> None:
        """Verify density calculation and is_empty property."""
        # 0x0 matrix
        zero_mat = WebSparsityMatrix(0, 0)
>       assert zero_mat.density == 0.0
               ^^^^^^^^^^^^^^^^
E       AttributeError: 'WebSparsityMatrix' object has no attribute 'density'

test_suite\test_web_matrices.py:516: AttributeError
_________________________ test_get_and_remove_element _________________________

    def test_get_and_remove_element() -> None:
        """Verify get_element and remove_element behaviors."""
        mat = WebSparsityMatrix(rows=3, cols=3)
>       mat[1, 1] = 42.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:533: TypeError
______________________________ test_prune_zeros _______________________________

    def test_prune_zeros() -> None:
        """Verify prune_zeros removes entries near or equal to zero."""
        mat = WebSparsityMatrix(rows=4, cols=4)
>       mat[0, 0] = 0.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:551: TypeError
_________________________________ test_clear __________________________________

    def test_clear() -> None:
        """Verify clear empties the matrix."""
>       mat = WebSparsityMatrix.identity(5)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'identity'

test_suite\test_web_matrices.py:570: AttributeError
__________________________ test_to_dense_round_trip ___________________________

    def test_to_dense_round_trip() -> None:
        """Verify to_dense accurate conversion to 2D numpy array."""
        dense_expected = np.array([
            [0.0, 1.5, 0.0],
            [0.0, 0.0, -2.5],
            [3.0, 0.0, 0.0],
        ], dtype=np.float32)
    
>       mat = WebSparsityMatrix.from_dense(dense_expected)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'from_dense'

test_suite\test_web_matrices.py:586: AttributeError
_____________________________ test_to_dict_export _____________________________

    def test_to_dict_export() -> None:
        """Verify to_dict produces valid dictionary export."""
        mat = WebSparsityMatrix(rows=2, cols=3)
>       mat[0, 1] = 4.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:596: TypeError
_________________ test_binary_packing_types_and_little_endian _________________

    def test_binary_packing_types_and_little_endian() -> None:
        """Verify to_coo_arrays produces strictly little-endian '<i4' and '<f4' arrays."""
        mat = WebSparsityMatrix(rows=5, cols=5)
>       mat[0, 1] = 10.5
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:621: TypeError
______________________ test_browser_sparsity_round_trip _______________________

    def test_browser_sparsity_round_trip() -> None:
        """Verify full round-trip serialization and deserialization via BrowserSparsityPayload."""
        mat = WebSparsityMatrix(rows=10, cols=12)
        # Populate a set of distinct values
        test_entries = [
            (0, 0, 1.0),
            (0, 5, 2.5),
            (2, 3, -4.75),
            (9, 11, 100.125),
        ]
        for r, c, v in test_entries:
>           mat[r, c] = v
            ^^^^^^^^^
E           TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:646: TypeError
___________________ test_from_browser_format_json_and_dict ____________________

    def test_from_browser_format_json_and_dict() -> None:
        """Verify from_browser_format accepts dict and JSON string inputs."""
>       mat = WebSparsityMatrix.identity(3, value=4.0)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'identity'

test_suite\test_web_matrices.py:671: AttributeError
______________________ test_decode_coo_corrupted_base64 _______________________

    def test_decode_coo_corrupted_base64() -> None:
        """Verify decode_coo raises ValueError on invalid base64 encoding."""
        dims = SparsityDimensions(rows=5, cols=5)
        payload = BrowserSparsityPayload(
            version="BrowserSparsity-004",
            dimensions=dims,
            rows_b64="!!!NOT_BASE64!!!",
            cols_b64="",
            vals_b64="",
        )
        with pytest.raises(ValueError, match="Failed to decode base64 sparsity payload"):
>           payload.decode_coo()
            ^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:705: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = BrowserSparsityPayload(version='BrowserSparsity-004', dimensions=SparsityDimensions(rows=5, cols=5), rows_b64='!!!NOT_BASE64!!!', cols_b64='', vals_b64='')
item = 'decode_coo'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'BrowserSparsityPayload' object has no attribute 'decode_coo'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
______________________ test_decode_coo_misaligned_bytes _______________________

    def test_decode_coo_misaligned_bytes() -> None:
        """Verify decode_coo raises ValueError when byte buffer length is not a multiple of 4."""
        dims = SparsityDimensions(rows=5, cols=5)
        bad_bytes_b64 = base64.b64encode(b"\x01\x02\x03\x04\x05").decode("ascii")
        valid_bytes_b64 = base64.b64encode(np.array([0], dtype="<i4").tobytes()).decode("ascii")
    
        # Misaligned rows
        payload_row = BrowserSparsityPayload(
            version="BrowserSparsity-004",
            dimensions=dims,
            rows_b64=bad_bytes_b64,
            cols_b64=valid_bytes_b64,
            vals_b64=valid_bytes_b64,
        )
        with pytest.raises(ValueError, match=r"Row buffer byte length \(5\) is not a multiple of 4"):
>           payload_row.decode_coo()
            ^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:723: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = BrowserSparsityPayload(version='BrowserSparsity-004', dimensions=SparsityDimensions(rows=5, cols=5), rows_b64='AQIDBAU=', cols_b64='AAAAAA==', vals_b64='AAAAAA==')
item = 'decode_coo'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'BrowserSparsityPayload' object has no attribute 'decode_coo'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
__________________ test_decode_coo_mismatched_array_lengths ___________________

    def test_decode_coo_mismatched_array_lengths() -> None:
        """Verify decode_coo raises ValueError when row, col, and val lengths mismatch."""
        dims = SparsityDimensions(rows=5, cols=5)
        rows_bytes = np.array([0, 1], dtype="<i4").tobytes()
        cols_bytes = np.array([0], dtype="<i4").tobytes()
        vals_bytes = np.array([1.0, 2.0], dtype="<f4").tobytes()
    
        payload = BrowserSparsityPayload(
            version="BrowserSparsity-004",
            dimensions=dims,
            rows_b64=base64.b64encode(rows_bytes).decode("ascii"),
            cols_b64=base64.b64encode(cols_bytes).decode("ascii"),
            vals_b64=base64.b64encode(vals_bytes).decode("ascii"),
        )
    
        with pytest.raises(ValueError, match="Mismatched COO array lengths: rows=2, cols=1, vals=2"):
>           payload.decode_coo()
            ^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:764: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = BrowserSparsityPayload(version='BrowserSparsity-004', dimensions=SparsityDimensions(rows=5, cols=5), rows_b64='AAAAAAEAAAA=', cols_b64='AAAAAA==', vals_b64='AACAPwAAAEA=')
item = 'decode_coo'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'BrowserSparsityPayload' object has no attribute 'decode_coo'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
____________________ test_matrix_addition_and_subtraction _____________________

    def test_matrix_addition_and_subtraction() -> None:
        """Verify elementwise addition and subtraction between sparse matrices."""
>       A = WebSparsityMatrix(3, 3, data=[(0, 0, 2.0), (1, 2, 3.0)])
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:774: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A622EDD950>
rows = 3, cols = 3, data = [(0, 0, 2.0), (1, 2, 3.0)]

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not tuple

cochem_base\interfaces\web_matrices.py:51: TypeError
___________________ test_scalar_multiplication_and_division ___________________

    def test_scalar_multiplication_and_division() -> None:
        """Verify scalar multiplication, division, negation, and in-place scaling."""
>       A = WebSparsityMatrix(3, 3, data=[(0, 1, 4.0), (2, 2, -8.0)])
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:804: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A622EDDA90>
rows = 3, cols = 3, data = [(0, 1, 4.0), (2, 2, -8.0)]

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not tuple

cochem_base\interfaces\web_matrices.py:51: TypeError
_________________________ test_matrix_multiplication __________________________

    def test_matrix_multiplication() -> None:
        """Verify matrix-matrix multiplication (sparse @ sparse), matrix-vector, and matrix-dense."""
>       A = WebSparsityMatrix(2, 3, data=[(0, 0, 1.0), (0, 1, 2.0), (1, 1, 3.0), (1, 2, 4.0)])
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:836: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A622FB5E50>
rows = 2, cols = 3, data = [(0, 0, 1.0), (0, 1, 2.0), (1, 1, 3.0), (1, 2, 4.0)]

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not tuple

cochem_base\interfaces\web_matrices.py:51: TypeError
_______________ test_matrix_trace_diagonal_symmetric_bandwidth ________________

    def test_matrix_trace_diagonal_symmetric_bandwidth() -> None:
        """Verify trace, diagonal extraction, is_symmetric, and bandwidth calculation."""
        mat = WebSparsityMatrix(4, 4)
>       mat[0, 0] = 1.0
        ^^^^^^^^^
E       TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:870: TypeError
______________________________ test_matrix_norms ______________________________

    def test_matrix_norms() -> None:
        """Verify Frobenius norm, 1-norm, and infinity-norm."""
>       mat = WebSparsityMatrix(2, 2, data=[(0, 0, 3.0), (0, 1, -4.0), (1, 1, 5.0)])
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:897: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A62A2787D0>
rows = 2, cols = 2, data = [(0, 0, 3.0), (0, 1, -4.0), (1, 1, 5.0)]

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not tuple

cochem_base\interfaces\web_matrices.py:51: TypeError
________________ test_matrix_slicing_retrieval_and_assignment _________________

    def test_matrix_slicing_retrieval_and_assignment() -> None:
        """Verify slicing access matrix[r_slice, c_slice] and slice assignments."""
        mat = WebSparsityMatrix(5, 5)
        for i in range(5):
            for j in range(5):
                if (i + j) % 2 == 0:
>                   mat[i, j] = float(i * 10 + j)
                    ^^^^^^^^^
E                   TypeError: 'WebSparsityMatrix' object does not support item assignment

test_suite\test_web_matrices.py:920: TypeError
________________________ test_csr_and_csc_conversions _________________________

    def test_csr_and_csc_conversions() -> None:
        """Verify CSR and CSC array extraction and reconstruction."""
        dense = np.array([
            [1.0, 0.0, 2.0],
            [0.0, 3.0, 0.0],
            [4.0, 5.0, 6.0],
        ], dtype=np.float32)
    
>       mat = WebSparsityMatrix.from_dense(dense)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'from_dense'

test_suite\test_web_matrices.py:951: AttributeError
___________________________ test_kronecker_product ____________________________

    def test_kronecker_product() -> None:
        """Verify Kronecker product A \u2297 B."""
>       A = WebSparsityMatrix.identity(2)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'identity'

test_suite\test_web_matrices.py:982: AttributeError
__________________________ test_block_diag_assembly ___________________________

    def test_block_diag_assembly() -> None:
        """Verify assembling multiple matrices along the block diagonal."""
>       A = WebSparsityMatrix.identity(2, value=5.0)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'identity'

test_suite\test_web_matrices.py:1008: AttributeError
_______________________ test_random_and_diag_generators _______________________

    def test_random_and_diag_generators() -> None:
        """Verify random sparse matrix and diagonal vector constructors."""
>       diag_mat = WebSparsityMatrix.diag([10.0, 0.0, 20.0, 30.0])
                   ^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'diag'

test_suite\test_web_matrices.py:1030: AttributeError
_______________________ test_matrix_chunking_for_webgl ________________________

    def test_matrix_chunking_for_webgl() -> None:
        """Verify matrix partitioning into tile chunks."""
>       mat = WebSparsityMatrix.identity(6, value=1.0)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'WebSparsityMatrix' has no attribute 'identity'

test_suite\test_web_matrices.py:1051: AttributeError
________________________ test_transformations_and_json ________________________

    def test_transformations_and_json() -> None:
        """Verify clip, threshold, apply, and JSON serialization."""
>       mat = WebSparsityMatrix(3, 3, data=[(0, 0, 1.5), (1, 1, -5.0), (2, 2, 10.0)])
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_matrices.py:1066: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <cochem_base.interfaces.web_matrices.WebSparsityMatrix object at 0x000002A628337C50>
rows = 3, cols = 3, data = [(0, 0, 1.5), (1, 1, -5.0), (2, 2, 10.0)]

    def __init__(self, rows: int, cols: int, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rows: int = rows
        self.cols: int = cols
        self.data_dict: Dict[Tuple[int, int], float] = {}
        if data is not None:
            for d in data:
                # Enforce structural validation using Pydantic to prevent KeyError/ValueError
>               element = MatrixElement(**d)
                          ^^^^^^^^^^^^^^^^^^
E               TypeError: cochem_base.interfaces.web_matrices.MatrixElement() argument after ** must be a mapping, not tuple

cochem_base\interfaces\web_matrices.py:51: TypeError
____________________ test_physical_stream_sparsity_payload ____________________

    def test_physical_stream_sparsity_payload() -> None:
        """Test streaming sparse matrix payloads (BrowserSparsityPayload and WebSparsityMatrix)."""
        server = LocalLoopbackServer()
        server.start()
    
        try:
            # Create real WebSparsityMatrix
            matrix = WebSparsityMatrix(rows=3, cols=3)
            matrix.add_element(0, 0, 1.5)
            matrix.add_element(1, 2, 3.7)
    
            streamer = WebGLStreamer(host=server.host, port=server.port, timeout=2.0)
            streamer.connect()
    
            # Stream via matrix instance
            bytes_sent1 = streamer.stream_sparsity_payload(matrix)
            assert bytes_sent1 > 0
    
            # Stream via BrowserSparsityPayload
            payload_obj = matrix.to_browser_format()
            bytes_sent2 = streamer.stream_sparsity_payload(payload_obj)
            assert bytes_sent2 > 0
    
            time.sleep(0.1)
            assert len(server.received_frames) == 2
    
            # Verify received sparsity format
            packet1 = WebGLPacket.from_json_bytes(server.received_frames[0])
            assert packet1.metadata["content_type"] == "sparsity"
            reconstructed_payload = BrowserSparsityPayload.model_validate(packet1.payload)
>           reconstructed_mat = reconstructed_payload.to_matrix()
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_web_streaming.py:475: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = BrowserSparsityPayload(version='BrowserSparsity-004', dimensions=SparsityDimensions(rows=3, cols=3), rows_b64='AAAAAAEAAAA=', cols_b64='AAAAAAIAAAA=', vals_b64='AADAP83MbEA=')
item = 'to_matrix'

    def __getattr__(self, item: str) -> Any:
        private_attributes = object.__getattribute__(self, '__private_attributes__')
        if item in private_attributes:
            attribute = private_attributes[item]
            if hasattr(attribute, '__get__'):
                return attribute.__get__(self, type(self))  # type: ignore
    
            try:
                # Note: self.__pydantic_private__ cannot be None if self.__private_attributes__ has items
                return self.__pydantic_private__[item]  # type: ignore
            except KeyError as exc:
                raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}') from exc
        else:
            # `__pydantic_extra__` can fail to be set if the model is not yet fully initialized.
            # See `BaseModel.__repr_args__` for more details
            try:
                pydantic_extra = object.__getattribute__(self, '__pydantic_extra__')
            except AttributeError:
                pydantic_extra = None
    
            if pydantic_extra and item in pydantic_extra:
                return pydantic_extra[item]
            else:
                if hasattr(self.__class__, item):
                    return super().__getattribute__(item)  # Raises AttributeError if appropriate
                else:
                    # this is the current error
>                   raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E                   AttributeError: 'BrowserSparsityPayload' object has no attribute 'to_matrix'

C:\Users\ansac\anaconda3\Lib\site-packages\pydantic\main.py:1042: AttributeError
_______________________ test_yaml_frontmatter_validity ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/artist.agent.md')

    def test_yaml_frontmatter_validity(target_file: Path) -> None:
        """Verify valid YAML frontmatter and required schema attributes."""
        content = target_file.read_text(encoding="utf-8")
        assert content.startswith("---"), "Document must start with YAML frontmatter delimiter (---)"
        parts = content.split("---", 2)
        assert len(parts) >= 3, "Frontmatter must be enclosed between '---' delimiters"
    
        fm_raw = parts[1].strip()
        data = yaml.safe_load(fm_raw)
        assert isinstance(data, dict), "Frontmatter must parse into a dictionary"
    
        assert data.get("name") == "artist", f"Expected name 'artist', got {data.get('name')}"
        assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
        assert "argument-hint" in data, "Missing argument-hint in frontmatter"
>       assert data.get("version") == "2.0.0"
E       AssertionError: assert None == '2.0.0'
E        +  where None = <built-in method get of dict object at 0x000002A6265B0480>('version')
E        +    where <built-in method get of dict object at 0x000002A6265B0480> = {'argument-hint': 'A description of the image, diagram, or video required for the project', 'description': 'Visual med...s, mandating vector graphics and Method Matrix compliance.', 'enable_mcp_tools': True, 'enable_write_tools': True, ...}.get

tests\test_artist_refactor.py:82: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/artist.agent.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections and core directives are present."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Native Image Generation",
            "## 2. External Prompt Crafting",
            "## 3. Negative Prompting",
            "## 4. Vector Graphics Preference",
            "## 5. Local Hardware Offloading & MCP Tool Utilization",
            "## 6. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# WHAT I DO NOT DO",
            "# BEHAVIOR BOUNDARIES",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 2. External Prompt Crafting
E           assert '## 2. External Prompt Crafting' in "---\nname: artist\ndescription: Visual media agent. Generates images via native tools and crafts prompts for external...ication layouts (that is `ui`'s role).\n* Do not write backend computational code (that is `cochem-coder`'s role).\n\n"

tests\test_artist_refactor.py:120: AssertionError
___________________ test_artist_core_directives_invariants ____________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/artist.agent.md')

    def test_artist_core_directives_invariants(target_file: Path) -> None:
        """Verify native image generation, negative prompting, ACS specs, and vector preference."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "generate_image" in content
>       assert "AspectRatio" in content
E       assert 'AspectRatio' in "---\nname: artist\ndescription: Visual media agent. Generates images via native tools and crafts prompts for external...ication layouts (that is `ui`'s role).\n* Do not write backend computational code (that is `cochem-coder`'s role).\n\n"

tests\test_artist_refactor.py:128: AssertionError
________________________ test_mcp_hardware_offloading _________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/artist.agent.md')

    def test_mcp_hardware_offloading(target_file: Path) -> None:
        """Verify local hardware offloading via MCP tools."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "github-copilot" in content
E       assert 'github-copilot' in "---\nname: artist\ndescription: Visual media agent. Generates images via native tools and crafts prompts for external...ication layouts (that is `ui`'s role).\n* Do not write backend computational code (that is `cochem-coder`'s role).\n\n"

tests\test_artist_refactor.py:145: AssertionError
________________________ test_anti_spoofing_directives ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/artist.agent.md')

    def test_anti_spoofing_directives(target_file: Path) -> None:
        """Verify anti-spoofing and zero-mock requirements."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "MAX_META_PIVOT=3" in content
E       assert 'MAX_META_PIVOT=3' in "---\nname: artist\ndescription: Visual media agent. Generates images via native tools and crafts prompts for external...ication layouts (that is `ui`'s role).\n* Do not write backend computational code (that is `cochem-coder`'s role).\n\n"

tests\test_artist_refactor.py:153: AssertionError
___________________ test_briefing_canonical_tokens_present ____________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/BRIEFING.md')

    def test_briefing_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized in BRIEFING.md."""
        content = target_file.read_text(encoding="utf-8")
        for token in ["<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
>           assert token in content, f"Missing canonical token in BRIEFING.md: {token}"
E           AssertionError: Missing canonical token in BRIEFING.md: <GDRIVE_ROOT>
E           assert '<GDRIVE_ROOT>' in '# BRIEFING � 2026-08-11T13:07:05Z\n\n## Mission\nOrchestrate fixing the CoChem-Antigravity sanitized agents in CoChem...tus\n- <COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\orchestrator\\handoff.md � Orchestrator handoff report\n'

tests\test_briefing_refactor.py:63: AssertionError
_______________________ test_yaml_frontmatter_validity ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_yaml_frontmatter_validity(target_file: Path) -> None:
        """Verify valid YAML frontmatter and required schema attributes."""
        content = target_file.read_text(encoding="utf-8")
        assert content.startswith("---"), "Document must start with YAML frontmatter delimiter (---)"
        parts = content.split("---", 2)
        assert len(parts) >= 3, "Frontmatter must be enclosed between '---' delimiters"
    
        fm_raw = parts[1].strip()
        data = yaml.safe_load(fm_raw)
        assert isinstance(data, dict), "Frontmatter must parse into a dictionary"
    
        assert data.get("name") == "cochem-audit", f"Expected name 'cochem-audit', got {data.get('name')}"
        assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
        assert "argument-hint" in data, "Missing argument-hint in frontmatter"
>       assert data.get("version") == "2.0.0"
E       AssertionError: assert None == '2.0.0'
E        +  where None = <built-in method get of dict object at 0x000002A62A3515C0>('version')
E        +    where <built-in method get of dict object at 0x000002A62A3515C0> = {'argument-hint': 'a Python script to audit and refactor', 'description': 'Autonomous Quality Assurance, Code Standards, and Architectural Compliance agent.', 'enable_mcp_tools': True, 'enable_write_tools': True, ...}.get

tests\test_cochem_audit_refactor.py:80: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections and core directives are present."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Registry Consistency & Air-Gap Enforcement",
            "## 2. Rigorous Typing & Linting",
            "## 3. Graceful Failure & Subprocess Safety",
            "## 4. Method Matrix Compliance",
            "## 5. Provenance & Integrity",
            "## 6. Root Cause Resolution (Anti-Band-Aid) Mandate",
            "# SWARM STATE MANAGEMENT PROTOCOL",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# WHAT I DO NOT DO",
            "# BEHAVIOR BOUNDARIES",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "<ROOT_CAUSE_MANDATE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 6. Root Cause Resolution (Anti-Band-Aid) Mandate
E           assert '## 6. Root Cause Resolution (Anti-Band-Aid) Mandate' in '---\nname: cochem-audit\ndescription: Autonomous Quality Assurance, Code Standards, and Architectural Compliance agen...` (max 3 bullets).\n2. Output the fully refactored, 100% complete Python script within a single `python` code block.\n'

tests\test_cochem_audit_refactor.py:118: AssertionError
___________________ test_anti_spoofing_and_audit_directives ___________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_anti_spoofing_and_audit_directives(target_file: Path) -> None:
        """Verify anti-spoofing and zero-mock requirements in cochem-audit."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "zero_trust_runner.py" in content
E       AssertionError: assert 'zero_trust_runner.py' in '---\nname: cochem-audit\ndescription: Autonomous Quality Assurance, Code Standards, and Architectural Compliance agen...` (max 3 bullets).\n2. Output the fully refactored, 100% complete Python script within a single `python` code block.\n'

tests\test_cochem_audit_refactor.py:125: AssertionError
_______________________ test_yaml_frontmatter_validity ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_yaml_frontmatter_validity(target_file: Path) -> None:
        """Verify valid YAML frontmatter and required schema attributes."""
        content = target_file.read_text(encoding="utf-8")
        assert content.startswith("---"), "Document must start with YAML frontmatter delimiter (---)"
        parts = content.split("---", 2)
        assert len(parts) >= 3, "Frontmatter must be enclosed between '---' delimiters"
    
        fm_raw = parts[1].strip()
        data = yaml.safe_load(fm_raw)
        assert isinstance(data, dict), "Frontmatter must parse into a dictionary"
    
        assert data.get("name") == "cochem-coder", f"Expected name 'cochem-coder', got {data.get('name')}"
        assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
        assert "argument-hint" in data, "Missing argument-hint in frontmatter"
>       assert data.get("version") == "2.0.0"
E       AssertionError: assert None == '2.0.0'
E        +  where None = <built-in method get of dict object at 0x000002A62A396B40>('version')
E        +    where <built-in method get of dict object at 0x000002A62A396B40> = {'argument-hint': 'a bug traceback to fix or a specific feature segment to implement', 'description': 'Autonomous iter...eature building agent. Strictly follows the Method Matrix.', 'enable_mcp_tools': True, 'enable_write_tools': True, ...}.get

tests\test_cochem_coder_refactor.py:80: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections and core directives are present."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Method Matrix Execution & Quantum Chemistry Invariants",
            "## 2. Hardware & Workflow Efficiency",
            "## 3. Local Hardware Offloading & MCP Tool Utilization",
            "## 4. Sane Defaults, Cross-Platform Portability & Error Prevention",
            "## 5. The 20-Cycle Pivot Protocol & Immutability",
            "## 6. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Method Matrix Execution & Quantum Chemistry Invariants
E           assert '## 1. Method Matrix Execution & Quantum Chemistry Invariants' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.'

tests\test_cochem_coder_refactor.py:111: AssertionError
________________________ test_method_matrix_invariants ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_method_matrix_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "CREST/ORCA GOAT" in content
E       AssertionError: assert 'CREST/ORCA GOAT' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.'

tests\test_cochem_coder_refactor.py:118: AssertionError
____________________ test_hardware_and_workflow_efficiency ____________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_hardware_and_workflow_efficiency(target_file: Path) -> None:
        """Verify hardware-aware routing, SWMR, RAM disk, and memoization rules."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "MACE" in content
        assert "CCSD(T)" in content
        assert "concurrent.futures" in content
        assert "%TEMP%" in content or "/dev/shm" in content
        assert "SWMR" in content
        assert ".gbw" in content
>       assert "@lru_cache" in content
E       AssertionError: assert '@lru_cache' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.'

tests\test_cochem_coder_refactor.py:139: AssertionError
________________________ test_mcp_hardware_offloading _________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_mcp_hardware_offloading(target_file: Path) -> None:
        """Verify local hardware offloading via MCP tools."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "github-copilot" in content
E       AssertionError: assert 'github-copilot' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.'

tests\test_cochem_coder_refactor.py:147: AssertionError
______________________ test_heading_hierarchy_integrity _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_heading_hierarchy_integrity(target_file: Path) -> None:
        """Verify heading hierarchy and ensure no raw XML tag pollution or malformed headers."""
        content = target_file.read_text(encoding="utf-8")
    
        # Ensure no raw XML tags lingering
        assert "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>" not in content
        assert "<SWARM_AUTONOMY_MANDATE>" not in content
        assert "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>" not in content
        assert "<ADVERSARIAL_AUDIT_DIRECTIVE>" not in content
    
        lines = content.splitlines()
        current_level = 0
        for lineno, line in enumerate(lines, 1):
            if line.startswith("#"):
                heading_hashes = len(line) - len(line.lstrip("#"))
                heading_text = line.lstrip("#").strip()
                if heading_hashes == 1 and current_level >= 2:
>                   assert heading_text in [
                        "IDENTITY AND ROLE",
                        "AUTHORITATIVE KNOWLEDGE SOURCES",
                        "CORE DIRECTIVES",
                        "GLOBAL SWARM PROTOCOLS",
                        "OUTPUT FORMAT",
                        "BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
                    ], f"Improper H1 header inside section at line {lineno}: {line}"
E                   AssertionError: Improper H1 header inside section at line 24: # METHOD MATRIX COMPLIANCE
E                   assert 'METHOD MATRIX COMPLIANCE' in ['IDENTITY AND ROLE', 'AUTHORITATIVE KNOWLEDGE SOURCES', 'CORE DIRECTIVES', 'GLOBAL SWARM PROTOCOLS', 'OUTPUT FORMAT', 'BEHAVIOR BOUNDARIES & WHAT I DO NOT DO']

tests\test_cochem_coder_refactor.py:168: AssertionError
______________________ test_behavior_boundaries_defined _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-coder.agent.md')

    def test_behavior_boundaries_defined(target_file: Path) -> None:
        """Verify clear behavior boundaries, routing, and safe recycling."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "cochem-debug" in content
        assert "cochem-tester" in content
        assert "cochem-improve" in content
        assert "cochem-audit" in content
>       assert ".trash" in content
E       AssertionError: assert '.trash' in '---\nname: cochem-coder\ndescription: Autonomous iterative implementation and feature building agent. Strictly follow...m-tester).\n* Do not make high-level architectural trade-offs without consulting cochem-improve and the Method Matrix.'

tests\test_cochem_coder_refactor.py:187: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-helper.agent.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections and core directives are present."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Method Matrix Enforcement & Quantum Chemistry Invariants",
            "## 2. Automating Rote Work & Pipeline Scaffolding",
            "## 3. Human-Readable Error Translations (User-Facing Triage)",
            "## 4. Publication Support & SI Package Standardization",
            "## 5. Local Hardware Offloading & MCP Tool Utilization",
            "## 6. Sane Defaults, Safe File Handling & Environment Portability",
            "## 7. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Method Matrix Enforcement & Quantum Chemistry Invariants
E           assert '## 1. Method Matrix Enforcement & Quantum Chemistry Invariants' in '---\nname: cochem-helper\ndescription: Outward-facing assistant for CoChem users. Guides researchers through workflow...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

tests\test_cochem_helper_refactor.py:115: AssertionError
________________________ test_method_matrix_invariants ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-helper.agent.md')

    def test_method_matrix_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "CREST/ORCA GOAT" in content
E       AssertionError: assert 'CREST/ORCA GOAT' in '---\nname: cochem-helper\ndescription: Outward-facing assistant for CoChem users. Guides researchers through workflow...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

tests\test_cochem_helper_refactor.py:122: AssertionError
______________________ test_heading_hierarchy_integrity _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-helper.agent.md')

    def test_heading_hierarchy_integrity(target_file: Path) -> None:
        """Verify heading hierarchy and ensure no raw XML tag pollution or malformed headers."""
        content = target_file.read_text(encoding="utf-8")
    
        # Ensure no raw XML tags lingering
>       assert "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>" not in content
E       AssertionError: assert '<GLOBAL_SWA..._DIRECTIVES>' not in '---\nname: ...==========\n'
E         
E         '<GLOBAL_SWARM_ANTI...INATION_DIRECTIVES>' is contained here:
E           he user.
E           
E           <GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>
E           ## 1. Banned terms: mock, example, stub, dummy, placeholder, fake, sample, # TODO: implement, unittest.mock, MagicMock.
E           - IF ANY parameter is missing, output [MISSING DATA] and report the reason. Do NOT silently halt....
E         
E         ...Full output truncated (62 lines hidden), use '-vv' to show

tests\test_cochem_helper_refactor.py:168: AssertionError
____________ test_method_matrix_provenance_and_quantum_invariants _____________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-scribe.agent.md')

    def test_method_matrix_provenance_and_quantum_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance tags."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "CREST/ORCA GOAT" in content
E       AssertionError: assert 'CREST/ORCA GOAT' in '---\nname: cochem-scribe\ndescription: Autonomous Technical Writing and Documentation agent for compiling FAIR-compli...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

tests\test_cochem_scribe_refactor.py:123: AssertionError
_______________ test_latex_mermaid_and_si_unit_standardization ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-scribe.agent.md')

    def test_latex_mermaid_and_si_unit_standardization(target_file: Path) -> None:
        """Verify LaTeX math formatting, mermaid diagram rules, and SI unit standards."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "mermaid" in content
        assert "LaTeX" in content or "latex" in content
        assert "kcal/mol" in content
>       assert "Angstrom" in content
E       AssertionError: assert 'Angstrom' in '---\nname: cochem-scribe\ndescription: Autonomous Technical Writing and Documentation agent for compiling FAIR-compli...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

tests\test_cochem_scribe_refactor.py:152: AssertionError
______________________ test_heading_hierarchy_integrity _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-scribe.agent.md')

    def test_heading_hierarchy_integrity(target_file: Path) -> None:
        """Verify heading hierarchy and ensure no raw XML tag pollution or malformed headers."""
        content = target_file.read_text(encoding="utf-8")
    
        # Ensure no raw XML tags lingering
>       assert "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>" not in content
E       AssertionError: assert '<GLOBAL_SWA..._DIRECTIVES>' not in '---\nname: ...==========\n'
E         
E         '<GLOBAL_SWARM_ANTI...INATION_DIRECTIVES>' is contained here:
E           pointer.
E           
E           <GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>
E           ## 1. Banned terms: mock, example, stub, dummy, placeholder, fake, sample, # TODO: implement, unittest.mock, MagicMock.
E           - IF ANY parameter is missing, output [MISSING DATA] and report the reason. Do NOT silently halt....
E         
E         ...Full output truncated (46 lines hidden), use '-vv' to show

tests\test_cochem_scribe_refactor.py:169: AssertionError
______________________ test_behavior_boundaries_defined _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-scribe.agent.md')

    def test_behavior_boundaries_defined(target_file: Path) -> None:
        """Verify clear behavior boundaries, routing, and safe recycling."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "cochem-coder" in content
        assert "cochem-debug" in content
        assert "cochem-improve" in content
        assert "cochem-audit" in content
>       assert "cochem-tester" in content
E       AssertionError: assert 'cochem-tester' in '---\nname: cochem-scribe\ndescription: Autonomous Technical Writing and Documentation agent for compiling FAIR-compli...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

tests\test_cochem_scribe_refactor.py:200: AssertionError
________________________ test_canonical_tokens_present ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/DISPATCH.md')

    def test_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized."""
        content = target_file.read_text(encoding="utf-8")
        for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
>           assert token in content, f"Missing canonical token: {token}"
E           AssertionError: Missing canonical token: <COCHEM_ROOT>
E           assert '<COCHEM_ROOT>' in '## 2026-08-11T18:01:08Z\nYou are the Project Orchestrator for fixing the CoChem-Antigravity sanitized agents.\nYour w...e process.\nWhen all work and verification is complete, claim victory and send a completion message to the Sentinel.\n'

tests\test_dispatch_refactor.py:70: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/DISPATCH.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections are present in DISPATCH.md."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Mission Objectives & Directive Scopes",
            "## 4. Agent Configuration Inventory (15 Specialized Agents)",
            "## 5. Swarm Delegation & Execution Lifecycle",
            "## 6. Acceptance Criteria & Verification Matrix",
            "## 7. State Tracking, Consensus Gates & Handoff Protocol",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Document Control, Metadata & Classification
E           assert '## 1. Document Control, Metadata & Classification' in '## 2026-08-11T18:01:08Z\nYou are the Project Orchestrator for fixing the CoChem-Antigravity sanitized agents.\nYour w...e process.\nWhen all work and verification is complete, claim victory and send a completion message to the Sentinel.\n'

tests\test_dispatch_refactor.py:88: AssertionError
______________________ test_agent_inventory_completeness ______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/DISPATCH.md')

    def test_agent_inventory_completeness(target_file: Path) -> None:
        """Verify all 15 agents are documented in the specification inventory."""
        content = target_file.read_text(encoding="utf-8")
    
        expected_agents = [
            "0rchestrator.agent.md",
            "artist.agent.md",
            "cochem-audit.agent.md",
            "cochem-coder.agent.md",
            "cochem-debug.agent.md",
            "cochem-helper.agent.md",
            "cochem-improve.agent.md",
            "cochem-scribe.agent.md",
            "cochem-sdp_manager.agent.md",
            "cochem-tester.agent.md",
            "educator.agent.md",
            "researcher.agent.md",
            "teacher.agent.md",
            "ui.agent.md",
            "web_mcp.agent.md",
        ]
    
        for agent in expected_agents:
>           assert agent in content, f"Missing agent reference in inventory: {agent}"
E           AssertionError: Missing agent reference in inventory: 0rchestrator.agent.md
E           assert '0rchestrator.agent.md' in '## 2026-08-11T18:01:08Z\nYou are the Project Orchestrator for fixing the CoChem-Antigravity sanitized agents.\nYour w...e process.\nWhen all work and verification is complete, claim victory and send a completion message to the Sentinel.\n'

tests\test_dispatch_refactor.py:114: AssertionError
__________________________ test_directives_coverage ___________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/DISPATCH.md')

    def test_directives_coverage(target_file: Path) -> None:
        """Verify all directives DIR-01 through DIR-05 are registered."""
        content = target_file.read_text(encoding="utf-8")
    
        for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
>           assert dir_tag in content, f"Missing directive registration: {dir_tag}"
E           AssertionError: Missing directive registration: DIR-01
E           assert 'DIR-01' in '## 2026-08-11T18:01:08Z\nYou are the Project Orchestrator for fixing the CoChem-Antigravity sanitized agents.\nYour w...e process.\nWhen all work and verification is complete, claim victory and send a completion message to the Sentinel.\n'

tests\test_dispatch_refactor.py:122: AssertionError
_________________________ test_mermaid_syntax_blocks __________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/DISPATCH.md')

    def test_mermaid_syntax_blocks(target_file: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed."""
        content = target_file.read_text(encoding="utf-8")
    
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 2 Mermaid diagrams, found 0
E       assert 0 >= 2
E        +  where 0 = len([])

tests\test_dispatch_refactor.py:130: AssertionError
_________________ test_method_matrix_and_zero_mock_invariants _________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/DISPATCH.md')

    def test_method_matrix_and_zero_mock_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules and Zero-Mock invariants are specified in acceptance criteria."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "defgrid1" in content and "defgrid3" in content
E       AssertionError: assert ('defgrid1' in '## 2026-08-11T18:01:08Z\nYou are the Project Orchestrator for fixing the CoChem-Antigravity sanitized agents.\nYour w...e process.\nWhen all work and verification is complete, claim victory and send a completion message to the Sentinel.\n')

tests\test_dispatch_refactor.py:141: AssertionError
_______________________ test_state_artifacts_referenced _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/DISPATCH.md')

    def test_state_artifacts_referenced(target_file: Path) -> None:
        """Verify all orchestrator state tracking artifacts are referenced."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "progress.md" in content
>       assert "PROJECT.md" in content
E       AssertionError: assert 'PROJECT.md' in '## 2026-08-11T18:01:08Z\nYou are the Project Orchestrator for fixing the CoChem-Antigravity sanitized agents.\nYour w...e process.\nWhen all work and verification is complete, claim victory and send a completion message to the Sentinel.\n'

tests\test_dispatch_refactor.py:154: AssertionError
___________ TestRegistryManagerAndAtomicData.test_get_all_isotopes ____________

self = <test_e2e_local_unit.TestRegistryManagerAndAtomicData object at 0x000002A625830050>

    def test_get_all_isotopes(self) -> None:
        isotopes_o = RegistryManager.get_all_isotopes("O")
        assert isinstance(isotopes_o, list)
        assert len(isotopes_o) >= 3  # 16O, 17O, 18O
>       symbols = {iso["symbol"] for iso in isotopes_o}
                   ^^^^^^^^^^^^^
E       KeyError: 'symbol'

tests\test_e2e_local_unit.py:313: KeyError
______ TestRegistryManagerAndAtomicData.test_embedded_basis_set_archival ______

self = <test_e2e_local_unit.TestRegistryManagerAndAtomicData object at 0x000002A625830180>
tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_embedded_basis_set_archiv1')

        def test_embedded_basis_set_archival(self, tmp_path: Path) -> None:
            reg_file = str(tmp_path / "registry.h5")
            rm = RegistryManager(registry_path=reg_file)
    
            basis_content = """! def2-SVP for H, O
    # Authentically embedded orbital basis definitions
    H: 2s1p -> [2s, 1p]
    O: 5s3p1d -> [3s, 2p, 1d]
    """
            rm.embed_basis_set_archive(
                h5_path=reg_file,
                basis_file_path=basis_content,
                label="def2-SVP",
                is_content=True,
            )
    
>           assert rm.has_embedded_basis_set("def2-SVP", h5_path=reg_file) is True
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           TypeError: RegistryManager.has_embedded_basis_set() got an unexpected keyword argument 'h5_path'

tests\test_e2e_local_unit.py:332: TypeError
________ TestRegistryManagerAndAtomicData.test_legacy_schema_migration ________

self = <test_e2e_local_unit.TestRegistryManagerAndAtomicData object at 0x000002A625775350>
tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_legacy_schema_migration1')

    def test_legacy_schema_migration(self, tmp_path: Path) -> None:
        reg_file = str(tmp_path / "legacy_registry.h5")
        with h5py.File(reg_file, "w") as h5:
            h5.attrs["version"] = "1.0.0"
            h5.create_group("jobs")
    
        rm = RegistryManager(registry_path=reg_file)
        report = rm.migrate_legacy_schema()
>       assert report["current_version"] == "4.0.0"
E       AssertionError: assert '1.0.0' == '4.0.0'
E         
E         - 4.0.0
E         ? ^
E         + 1.0.0
E         ? ^

tests\test_e2e_local_unit.py:428: AssertionError
_______ TestMolecularModelingWaterDimer.test_water_dimer_xyz_roundtrip ________

self = <test_e2e_local_unit.TestMolecularModelingWaterDimer object at 0x000002A6257DA690>
water_dimer = Molecule(name='Water_Dimer_Cs', atoms=6)
tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_water_dimer_xyz_roundtrip0')

    def test_water_dimer_xyz_roundtrip(self, water_dimer: Molecule, tmp_path: Path) -> None:
>       xyz_str = water_dimer.to_xyz(comment="Cs Water Dimer Equilibrium")
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: Molecule.to_xyz() got an unexpected keyword argument 'comment'

tests\test_e2e_local_unit.py:506: TypeError
_ TestExecutionRouterAndJobManagerLifecycle.test_job_manager_temporal_tier_assignment _

self = <test_e2e_local_unit.TestExecutionRouterAndJobManagerLifecycle object at 0x000002A6257256D0>

    def test_job_manager_temporal_tier_assignment(self) -> None:
        jm = JobManager()
    
        # Product A / De Novo (Water dimer: 6 atoms -> Tier 4 / T1-1h)
        cfg_dimer = JobConfig(product_class="Product_A_DeNovo", n_atoms=6)
        tier_dimer = jm._assign_temporal_tier(cfg_dimer)
        assert tier_dimer == 4
    
        # Product C / Differences (6 atoms -> Tier 1 / T1-10s)
        cfg_class_c = JobConfig(product_class="Product_C_Differences", n_atoms=6)
        tier_c = jm._assign_temporal_tier(cfg_class_c)
        assert tier_c == 1
    
        # Product B / SemiExperimental (6 atoms -> Tier 3 / T1-30min)
        cfg_class_b = JobConfig(product_class="Product_B_SemiExperimental", n_atoms=6)
        tier_b = jm._assign_temporal_tier(cfg_class_b)
        assert tier_b == 3
    
        # Product D / Active Learning (6 atoms -> Tier 9 / T4-1w)
        cfg_class_d = JobConfig(product_class="Product_D_ActiveLearning", n_atoms=6)
        tier_d = jm._assign_temporal_tier(cfg_class_d)
>       assert tier_d == 9
E       assert 4 == 9

tests\test_e2e_local_unit.py:673: AssertionError
_ TestExecutionRouterAndJobManagerLifecycle.test_job_manager_real_job_execution _

self = <test_e2e_local_unit.TestExecutionRouterAndJobManagerLifecycle object at 0x000002A625830770>

    def test_job_manager_real_job_execution(self) -> None:
        async def _run() -> None:
            jm = JobManager()
            cmd = [sys.executable, "-c", "import math; print(f'MW_SQRT={math.sqrt(36.03):.4f}')"]
            cfg = JobConfig(command=cmd, product_class="Product_A_DeNovo", n_atoms=6)
    
            job_info = await jm.run_job(cfg, timeout=15.0)
            assert job_info.status == "completed"
            assert job_info.return_code == 0
            assert job_info.stdout is not None
            assert "MW_SQRT=6.0025" in job_info.stdout
            assert job_info.duration is not None
            assert job_info.duration >= 0.0
    
>       asyncio.run(_run())

tests\test_e2e_local_unit.py:693: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _run() -> None:
        jm = JobManager()
        cmd = [sys.executable, "-c", "import math; print(f'MW_SQRT={math.sqrt(36.03):.4f}')"]
        cfg = JobConfig(command=cmd, product_class="Product_A_DeNovo", n_atoms=6)
    
>       job_info = await jm.run_job(cfg, timeout=15.0)
                         ^^^^^^^^^^
E       AttributeError: 'JobManager' object has no attribute 'run_job'

tests\test_e2e_local_unit.py:685: AttributeError
___ TestExecutionRouterAndJobManagerLifecycle.test_job_manager_cancellation ___

self = <test_e2e_local_unit.TestExecutionRouterAndJobManagerLifecycle object at 0x000002A6258308A0>

    def test_job_manager_cancellation(self) -> None:
        async def _run() -> None:
            jm = JobManager()
            # Command that would sleep for 60 seconds
            cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
            cfg = JobConfig(command=cmd, product_class="Product_A_DeNovo", n_atoms=6)
    
            job_id = await jm.submit_job(cfg)
            await jm.start_job(job_id)
            await asyncio.sleep(0.1)  # Brief yield to let process spawn
    
            cancelled = jm.cancel_job(job_id)
            assert cancelled is True
            job_info = jm.get_job(job_id)
            assert job_info is not None
            assert job_info.status == "cancelled"
    
>       asyncio.run(_run())

tests\test_e2e_local_unit.py:712: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
tests\test_e2e_local_unit.py:702: in _run
    job_id = await jm.submit_job(cfg)
             ^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <core_engine.cochem_core_job_manager.JobManager object at 0x000002A6281BAC10>
job_config_dict = JobConfig(command=['C:\\Users\\ansac\\anaconda3\\python.exe', '-c', 'import time; time.sleep(60)'], product_class='Product_A_DeNovo', is_isotopologue=False, has_parent_anchor=False, floppy_monomer=False, atom_count=None, n_atoms=6)

    async def submit_job(self, job_config_dict: Dict[str, Any]) -> str:
        """Submit a new job to the system with temporal tier assignment."""
        try:
>           job_config = JobConfig(**job_config_dict)
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           TypeError: core_engine.cochem_core_job_manager.JobConfig() argument after ** must be a mapping, not JobConfig

core_engine\cochem_core_job_manager.py:99: TypeError
_ TestExecutionRouterAndJobManagerLifecycle.test_job_manager_purge_and_history _

self = <test_e2e_local_unit.TestExecutionRouterAndJobManagerLifecycle object at 0x000002A62576C050>

    def test_job_manager_purge_and_history(self) -> None:
        async def _run() -> None:
            jm = JobManager(max_job_history=5)
            for i in range(4):
                cfg = JobConfig(command=[sys.executable, "-c", f"print({i})"])
                await jm.run_job(cfg, timeout=5.0)
    
            completed = jm.get_completed_jobs()
            assert len(completed) == 4
    
            purged = jm.purge_completed_jobs(max_age_seconds=0.0)
            assert purged == 4
            assert len(jm.get_completed_jobs()) == 0
    
>       asyncio.run(_run())

tests\test_e2e_local_unit.py:728: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:195: in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\runners.py:118: in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\asyncio\base_events.py:725: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    async def _run() -> None:
        jm = JobManager(max_job_history=5)
        for i in range(4):
            cfg = JobConfig(command=[sys.executable, "-c", f"print({i})"])
>           await jm.run_job(cfg, timeout=5.0)
                  ^^^^^^^^^^
E           AttributeError: 'JobManager' object has no attribute 'run_job'

tests\test_e2e_local_unit.py:719: AttributeError
____ TestQuantumParserAndHDF5State.test_quantum_parser_spin_contamination _____

self = <test_e2e_local_unit.TestQuantumParserAndHDF5State object at 0x000002A625830B00>
converged_orca_log = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_quantum_parser_spin_conta0/water_dimer_job.out')
tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-6230/test_quantum_parser_spin_conta0')

    def test_quantum_parser_spin_contamination(self, converged_orca_log: Path, tmp_path: Path) -> None:
        parser = QuantumParser(artifact_dir=str(tmp_path))
>       spin_ok = parser.check_spin_contamination(converged_orca_log)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'QuantumParser' object has no attribute 'check_spin_contamination'

tests\test_e2e_local_unit.py:783: AttributeError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections and core directives are present."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Scientific Inquiry Frameworks (CER & SPARK)",
            "## 2. Bloom's Taxonomy Cognitive Escalation & Standards Alignment",
            "## 3. Friction by Design, Productive Struggle & Misconception Traps",
            "## 4. Automated Grading, Rubrics & AST Code Provenance Auditing",
            "## 5. Multidisciplinary STEM Didactics & Macroscopic-Microscopic Bridging",
            "## 6. Method Matrix v4 Compliance in Educational Artifacts",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Scientific Inquiry Frameworks (CER & SPARK)
E           assert '## 1. Scientific Inquiry Frameworks (CER & SPARK)' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

tests\test_educator_refactor.py:106: AssertionError
____________________ test_pedagogical_frameworks_mandates _____________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_pedagogical_frameworks_mandates(target_file: Path) -> None:
        """Verify CER, SPARK, ZPD, Bloom's Taxonomy levels, and standards alignment."""
        content = target_file.read_text(encoding="utf-8")
    
        # CER & SPARK
>       assert "CER Framework" in content
E       AssertionError: assert 'CER Framework' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

tests\test_educator_refactor.py:114: AssertionError
______________________ test_friction_and_misconceptions _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_friction_and_misconceptions(target_file: Path) -> None:
        """Verify productive struggle, misconception traps, and fading scaffolding."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "Productive Struggle" in content
E       AssertionError: assert 'Productive Struggle' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

tests\test_educator_refactor.py:145: AssertionError
___________________ test_automated_grading_and_ast_auditing ___________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_automated_grading_and_ast_auditing(target_file: Path) -> None:
        """Verify AST code provenance auditing, double-blind grading, and RAI penalty matrix."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "AST" in content
        assert "Abstract Syntax Tree" in content
>       assert "Double-Blind" in content
E       AssertionError: assert 'Double-Blind' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

tests\test_educator_refactor.py:157: AssertionError
________________________ test_method_matrix_invariants ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_method_matrix_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "CREST/ORCA GOAT" in content
E       AssertionError: assert 'CREST/ORCA GOAT' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n'

tests\test_educator_refactor.py:165: AssertionError
______________________ test_behavior_boundaries_defined _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/educator.agent.md')

    def test_behavior_boundaries_defined(target_file: Path) -> None:
        """Verify clear behavior boundaries, backend-only role, and prohibitions."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "BACKEND" in content or "backend" in content
        assert "teacher" in content
>       assert "cochem-coder" in content or "cochem-tester" in content
E       AssertionError: assert ('cochem-coder' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n' or 'cochem-tester' in '---\nname: educator\ndescription: Backend pedagogical agent responsible for student grading, assignment creation, cou...each substantive response with the single safest next action for the user or the next smallest segment to implement.\n')

tests\test_educator_refactor.py:210: AssertionError
________________________ test_zero_personal_path_leaks ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_zero_personal_path_leaks(target_file: Path) -> None:
        """Verify zero personal/machine path leakage across the entire document."""
        with open(target_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
        leaks = []
        patterns = leak_patterns()
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))
    
>       assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
E       AssertionError: Detected 3 path leak(s): [(24, '<USER_HOME>', '| **R1. Overwrite Existing Agents**: Copy fixed agent files from `C:\\Users\\ansac\\.gemini\\config\\agents` and overwrite files in `CoChem-BASE/.agents` | **PASSED** | Reviewer 1, Reviewer 2, Challenger 2, and Forensic Auditor confirmed 100% 1:1 character parity modulo sanitization tags across all 15 `.agent.md` files |'), (25, '<USER_HOME>', '| **R2. Sanitize Absolute Paths**: Replace `C:\\Users\\ansac` with `<USER_HOME>`, `D:\\Gdrive\\__CoChem` with `<COCHEM_WORKSPACE>`, and `D:\\Gdrive` with `<GDRIVE_ROOT>` | **PASSED** | All personal absolute path references replaced across all 15 `.agent.md` files and metadata markdown files |'), (26, '<USER_HOME>', '| **Search Criterion 1**: `C:\\Users\\ansac` search inside `CoChem-BASE/.agents` returns 0 results | **PASSED** | Powershell & ripgrep recursive search across all files in `.agents` returned **0 matches** (verified by Worker 1, Challenger 1, Reviewer 2, Auditor 1) |')]
E       assert 3 == 0
E        +  where 3 = len([(24, '<USER_HOME>', '| **R1. Overwrite Existing Agents**: Copy fixed agent files from `C:\\Users\\ansac\\.gemini\\con...h across all files in `.agents` returned **0 matches** (verified by Worker 1, Challenger 1, Reviewer 2, Auditor 1) |')])

tests\test_handoff_refactor.py:66: AssertionError
________________________ test_canonical_tokens_present ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized."""
        content = target_file.read_text(encoding="utf-8")
        for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
>           assert token in content, f"Missing canonical token: {token}"
E           AssertionError: Missing canonical token: <COCHEM_ROOT>
E           assert '<COCHEM_ROOT>' in '# Orchestrator Handoff & Completion Report\n\n**Project**: CoChem-BASE Agent Configuration Fix & Path Sanitization  \...ently verified with unanimous consensus across all review, challenge, and audit roles. No remaining work is pending.\n'

tests\test_handoff_refactor.py:73: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections are present in handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Mission Objectives & Directive Scopes",
            "## 4. Milestone Lifecycle & Swarm Execution Verification",
            "## 5. Active Subagents, Multi-Agent Consensus Gates & Team Roster",
            "## 6. Acceptance Criteria, Quality Gates & Method Matrix Verification",
            "## 7. Key Orchestration Artifacts & Handoff Sign-off Protocol",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Document Control, Metadata & Classification
E           assert '## 1. Document Control, Metadata & Classification' in '# Orchestrator Handoff & Completion Report\n\n**Project**: CoChem-BASE Agent Configuration Fix & Path Sanitization  \...ently verified with unanimous consensus across all review, challenge, and audit roles. No remaining work is pending.\n'

tests\test_handoff_refactor.py:91: AssertionError
______________________ test_agent_inventory_completeness ______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_agent_inventory_completeness(target_file: Path) -> None:
        """Verify all 15 agents are documented in the handoff inventory."""
        content = target_file.read_text(encoding="utf-8")
    
        expected_agents = [
            "0rchestrator.agent.md",
            "artist.agent.md",
            "cochem-audit.agent.md",
            "cochem-coder.agent.md",
            "cochem-debug.agent.md",
            "cochem-helper.agent.md",
            "cochem-improve.agent.md",
            "cochem-scribe.agent.md",
            "cochem-sdp_manager.agent.md",
            "cochem-tester.agent.md",
            "educator.agent.md",
            "researcher.agent.md",
            "teacher.agent.md",
            "ui.agent.md",
            "web_mcp.agent.md",
        ]
    
        for agent in expected_agents:
>           assert agent in content, f"Missing agent reference in inventory: {agent}"
E           AssertionError: Missing agent reference in inventory: 0rchestrator.agent.md
E           assert '0rchestrator.agent.md' in '# Orchestrator Handoff & Completion Report\n\n**Project**: CoChem-BASE Agent Configuration Fix & Path Sanitization  \...ently verified with unanimous consensus across all review, challenge, and audit roles. No remaining work is pending.\n'

tests\test_handoff_refactor.py:117: AssertionError
__________________________ test_directives_coverage ___________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_directives_coverage(target_file: Path) -> None:
        """Verify all directives DIR-01 through DIR-05 are registered in handoff report."""
        content = target_file.read_text(encoding="utf-8")
    
        for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
>           assert dir_tag in content, f"Missing directive registration: {dir_tag}"
E           AssertionError: Missing directive registration: DIR-01
E           assert 'DIR-01' in '# Orchestrator Handoff & Completion Report\n\n**Project**: CoChem-BASE Agent Configuration Fix & Path Sanitization  \...ently verified with unanimous consensus across all review, challenge, and audit roles. No remaining work is pending.\n'

tests\test_handoff_refactor.py:125: AssertionError
_________________________ test_mermaid_syntax_blocks __________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_mermaid_syntax_blocks(target_file: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed in handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 2 Mermaid diagrams, found 0
E       assert 0 >= 2
E        +  where 0 = len([])

tests\test_handoff_refactor.py:133: AssertionError
_________________ test_method_matrix_and_zero_mock_invariants _________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_method_matrix_and_zero_mock_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules and Zero-Mock invariants are specified in handoff verification."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "defgrid1" in content and "defgrid3" in content
E       AssertionError: assert ('defgrid1' in '# Orchestrator Handoff & Completion Report\n\n**Project**: CoChem-BASE Agent Configuration Fix & Path Sanitization  \...ently verified with unanimous consensus across all review, challenge, and audit roles. No remaining work is pending.\n')

tests\test_handoff_refactor.py:144: AssertionError
_______________________ test_state_artifacts_referenced _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_state_artifacts_referenced(target_file: Path) -> None:
        """Verify all orchestrator state tracking artifacts are referenced in handoff."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "progress.md" in content
        assert "PROJECT.md" in content
        assert "GATE_STATUS.md" in content
>       assert "handoff.md" in content
E       AssertionError: assert 'handoff.md' in '# Orchestrator Handoff & Completion Report\n\n**Project**: CoChem-BASE Agent Configuration Fix & Path Sanitization  \...ently verified with unanimous consensus across all review, challenge, and audit roles. No remaining work is pending.\n'

tests\test_handoff_refactor.py:159: AssertionError
__________________________ test_milestones_coverage ___________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/handoff.md')

    def test_milestones_coverage(target_file: Path) -> None:
        """Verify milestones M1 through M6 are accounted for."""
        content = target_file.read_text(encoding="utf-8")
    
        for m in ["M1", "M2", "M3", "M4", "M5", "M6"]:
>           assert m in content, f"Missing milestone {m} in handoff.md"
E           AssertionError: Missing milestone M1 in handoff.md
E           assert 'M1' in '# Orchestrator Handoff & Completion Report\n\n**Project**: CoChem-BASE Agent Configuration Fix & Path Sanitization  \...ently verified with unanimous consensus across all review, challenge, and audit roles. No remaining work is pending.\n'

tests\test_handoff_refactor.py:170: AssertionError
___________________ test_unix_lf_line_endings[target_file1] ___________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md')

    def test_unix_lf_line_endings(target_file: Path) -> None:
        """Verify strictly Unix LF line endings (\n) and no Windows CRLF (\r\n)."""
        with open(target_file, "rb") as f:
            raw = f.read()
>       assert b"\r\n" not in raw, f"Found Windows CRLF (\r\n) line endings in {target_file.name}"
E       AssertionError: Found Windows CRLF (

E         ) line endings in Method_Matrix.md
E       assert b'\r\n' not in b'# Computational Prediction of Spectroscopic Observables for van der Waals Complexes\r\n\r\n**PI/Developer:** Dr. Jos...hip.org/content/qt7297t9vf/qt7297t9vf_noSplash_ae27d0ce06218f8fa9b5e5ef1289d1d8.pdf) \xe2\x80\x94 escholarship.org\r\n'

tests\test_method_matrix_refactor.py:42: AssertionError
______________ test_no_hardcoded_linux_user_paths[target_file1] _______________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md')

    def test_no_hardcoded_linux_user_paths(target_file: Path) -> None:
        """Verify that no un-sanitized /home/user paths exist in the document."""
        content = target_file.read_text(encoding="utf-8")
        hardcoded = re.findall(r"/home/\w+/[^\s`\(\)\"\'<>]+", content)
>       assert len(hardcoded) == 0, f"Detected hardcoded Linux user paths: {hardcoded}"
E       AssertionError: Detected hardcoded Linux user paths: ['/home/user/bin/oet-aimnet2/oet_client', '/home/user/bin/oet-aimnet2/oet_client']
E       assert 2 == 0
E        +  where 2 = len(['/home/user/bin/oet-aimnet2/oet_client', '/home/user/bin/oet-aimnet2/oet_client'])

tests\test_method_matrix_refactor.py:68: AssertionError
_________________ test_canonical_tokens_present[target_file1] _________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md')

    def test_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized."""
        content = target_file.read_text(encoding="utf-8")
>       assert "<USER_HOME>" in content, "Missing canonical <USER_HOME> token"
E       AssertionError: Missing canonical <USER_HOME> token
E       assert '<USER_HOME>' in '# Computational Prediction of Spectroscopic Observables for van der Waals Complexes\n\n**PI/Developer:** Dr. Joshua J...s://escholarship.org/content/qt7297t9vf/qt7297t9vf_noSplash_ae27d0ce06218f8fa9b5e5ef1289d1d8.pdf) � escholarship.org\n'

tests\test_method_matrix_refactor.py:74: AssertionError
_________________ test_primary_sections_present[target_file1] _________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md')

    def test_primary_sections_present(target_file: Path) -> None:
        """Verify all canonical primary numbered sections are present."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "# Computational Prediction of Spectroscopic Observables for van der Waals Complexes",
            "## Changes in this revision",
            "## The one-page decision card",
            "## Quick start",
            "## 1. The three products and the routing question",
            "## 2. Scope, system class and vocabulary",
            "## 3. Required accuracy specification",
            "## 4. Error propagation: the geometry",
            "## 5. Corrected working equations, counts and constants",
            "## 6. Observables the previous versions underweighted",
            "## 7. Nuclear spin statistics and permutation-inversion symmetry",
            "## 8. Hardware, and the routing decision procedure",
            "## 8A. Concurrency and the scout-and-anchor heterogeneous pipeline",
            "## 8B. Job chaining and state reuse",
            "## 8C. The HDF5 PES store",
            "## 8D. Analytical Hessian CC Mandate: 3-Tier Routing Protocol",
            "## 9. Codes and acquisition: the MPQC track and Legacy/Proprietary Alternates (ORCA & CFOUR)",
            "## 9A. Composite and combined methods",
            "## 9B. Conformer and isomer search: GOAT, CREST, and the union",
            "## 10. The ORCA external-tool contract, implemented",
            "## 11. Software licensing",
            "## 12. How to read the tier tables",
            "## 13. Tables 1�5: search, surface, geometry, averaging, energetics",
            "## 14. Tables 6�10: secondary observables, large-amplitude motion, and the non-microwave regimes",
            "## 15. The Pareto frontier, dominated rows, and the two use cases",
            "## 16. Failure modes and mandatory guards",
            "## 17. Validation protocol: the six-system working set",
            "## 18. Deliverable specification",
            "## 19. The teaching tier, corrected",
            "## 20. Reproducibility and provenance",
            "## 21. Hard limits, and the development roadmap",
            "## 22. Conference record and provenance of this revision",
            "## Appendix A. Large-amplitude-motion integrations, retained from v3",
            "## 23. References",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section in {target_file.name}: {sec}"
E           AssertionError: Missing required section in Method_Matrix.md: ## 8D. Analytical Hessian CC Mandate: 3-Tier Routing Protocol
E           assert '## 8D. Analytical Hessian CC Mandate: 3-Tier Routing Protocol' in '# Computational Prediction of Spectroscopic Observables for van der Waals Complexes\n\n**PI/Developer:** Dr. Joshua J...s://escholarship.org/content/qt7297t9vf/qt7297t9vf_noSplash_ae27d0ce06218f8fa9b5e5ef1289d1d8.pdf) � escholarship.org\n'

tests\test_method_matrix_refactor.py:140: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/progress.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections are present in progress.md."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Mission Directives & Multi-Directive Execution Status",
            "## 4. Multi-Stage Milestone Quality Gates & Iteration Progress",
            "## 5. Specialized Agent Configuration Inventory (15 Agents) & Task Assignments",
            "## 6. Acceptance Criteria, Quality Gates & Method Matrix Verification",
            "## 7. Chronological Swarm Event Log & Audit Trail",
            "## 8. Orchestrator State Manifest Index & Official Gate Seal",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section in progress.md: {sec}"
E           AssertionError: Missing required section in progress.md: ## 1. Document Control, Metadata & Classification
E           assert '## 1. Document Control, Metadata & Classification' in '# Swarm Execution Progress Tracker � Iteration 1\n\n## 1. Document Control, Metadata & Provenance\n- **Document Title...m-BASE\\.agents\\orchestrator\\progress.md` | This execution progress tracker & WBS checklist | **ACTIVE** | `[M]` |\n'

tests\test_progress_refactor.py:87: AssertionError
______________________ test_agent_inventory_completeness ______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/progress.md')

    def test_agent_inventory_completeness(target_file: Path) -> None:
        """Verify all 15 agents are documented in the progress inventory."""
        content = target_file.read_text(encoding="utf-8")
    
        expected_agents = [
            "0rchestrator.agent.md",
            "artist.agent.md",
            "cochem-audit.agent.md",
            "cochem-coder.agent.md",
            "cochem-debug.agent.md",
            "cochem-helper.agent.md",
            "cochem-improve.agent.md",
            "cochem-scribe.agent.md",
            "cochem-sdp_manager.agent.md",
            "cochem-tester.agent.md",
            "educator.agent.md",
            "researcher.agent.md",
            "teacher.agent.md",
            "ui.agent.md",
            "web_mcp.agent.md",
        ]
    
        for agent in expected_agents:
>           assert agent in content, f"Missing agent reference in inventory: {agent}"
E           AssertionError: Missing agent reference in inventory: 0rchestrator.agent.md
E           assert '0rchestrator.agent.md' in '# Swarm Execution Progress Tracker � Iteration 1\n\n## 1. Document Control, Metadata & Provenance\n- **Document Title...m-BASE\\.agents\\orchestrator\\progress.md` | This execution progress tracker & WBS checklist | **ACTIVE** | `[M]` |\n'

tests\test_progress_refactor.py:113: AssertionError
__________________________ test_directives_coverage ___________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/progress.md')

    def test_directives_coverage(target_file: Path) -> None:
        """Verify all directives DIR-01 through DIR-05 are registered in progress report."""
        content = target_file.read_text(encoding="utf-8")
    
        for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
>           assert dir_tag in content, f"Missing directive registration: {dir_tag}"
E           AssertionError: Missing directive registration: DIR-01
E           assert 'DIR-01' in '# Swarm Execution Progress Tracker � Iteration 1\n\n## 1. Document Control, Metadata & Provenance\n- **Document Title...m-BASE\\.agents\\orchestrator\\progress.md` | This execution progress tracker & WBS checklist | **ACTIVE** | `[M]` |\n'

tests\test_progress_refactor.py:121: AssertionError
_________________________ test_mermaid_syntax_blocks __________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/progress.md')

    def test_mermaid_syntax_blocks(target_file: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed in progress.md."""
        content = target_file.read_text(encoding="utf-8")
    
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 2 Mermaid diagrams, found 1
E       assert 1 >= 2
E        +  where 1 = len(['gantt\n    title Swarm Execution Lifecycle (M1 to M6)\n    dateFormat  YYYY-MM-DD\n    section Survey & Inventory Ba...onsensus Gate & Sign-off Seal\n    Phase 5 (M6) Multi-Agent Quorum Voting & Handoff :done, m6, 2026-08-11, 2026-08-11'])

tests\test_progress_refactor.py:129: AssertionError
_______________________ test_state_artifacts_referenced _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/progress.md')

    def test_state_artifacts_referenced(target_file: Path) -> None:
        """Verify all orchestrator state tracking artifacts are referenced in progress.md."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "progress.md" in content
        assert "PROJECT.md" in content
        assert "GATE_STATUS.md" in content
        assert "handoff.md" in content
        assert "BRIEFING.md" in content
        assert "DISPATCH.md" in content
>       assert "ORIGINAL_REQUEST.md" in content
E       AssertionError: assert 'ORIGINAL_REQUEST.md' in '# Swarm Execution Progress Tracker � Iteration 1\n\n## 1. Document Control, Metadata & Provenance\n- **Document Title...m-BASE\\.agents\\orchestrator\\progress.md` | This execution progress tracker & WBS checklist | **ACTIVE** | `[M]` |\n'

tests\test_progress_refactor.py:158: AssertionError
________________________ test_zero_personal_path_leaks ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_zero_personal_path_leaks(target_file: Path) -> None:
        """Verify zero personal/machine path leakage across the entire document."""
        with open(target_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
        leaks = []
        patterns = leak_patterns()
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))
    
>       assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
E       AssertionError: Detected 5 path leak(s): [(5, '<USER_HOME>', '- Source Directory: `C:\\Users\\ansac\\.gemini\\config\\agents`'), (8, '<USER_HOME>', '- `C:\\Users\\ansac` / `C:/Users/ansac` -> `<USER_HOME>`'), (8, '<USER_HOME>', '- `C:\\Users\\ansac` / `C:/Users/ansac` -> `<USER_HOME>`'), (17, '<USER_HOME>', '| 2 | Agent Config Path Sanitization | Sanitize all absolute personal paths (`C:\\Users\\ansac`, `D:\\Gdrive\\__CoChem`, `D:\\Gdrive`) in `.agent.md` files | M1 | Survey |'), (19, '<USER_HOME>', '| 4 | Verification & Audit | Verify file match, path sanitization, and 0 search hits for `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` via Reviewers, Challengers, and Forensic Auditor | M2 | Survey |')]
E       assert 5 == 0
E        +  where 5 = len([(5, '<USER_HOME>', '- Source Directory: `C:\\Users\\ansac\\.gemini\\config\\agents`'), (8, '<USER_HOME>', '- `C:\\Use...s for `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` via Reviewers, Challengers, and Forensic Auditor | M2 | Survey |')])

tests\test_project_refactor.py:66: AssertionError
________________________ test_canonical_tokens_present ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized."""
        content = target_file.read_text(encoding="utf-8")
        for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
>           assert token in content, f"Missing canonical token: {token}"
E           AssertionError: Missing canonical token: <COCHEM_ROOT>
E           assert '<COCHEM_ROOT>' in '# Project: CoChem-BASE Agent Configuration Fix & Sanitization\n\n## Architecture\n- Target Directory: `D:\\Gdrive\\__...xecute read-only checks and verification commands against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.\n'

tests\test_project_refactor.py:73: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections are present in PROJECT.md."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Mission Objectives & Directive Scopes",
            "## 4. Deep Granularity & Hierarchical Work Breakdown Structure (WBS)",
            "## 5. Agent Configuration Inventory & RACI Matrix",
            "## 6. Acceptance Criteria & Method Matrix Quality Gates",
            "## 7. State Tracking, Consensus Gates & Handoff Protocol",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Document Control, Metadata & Classification
E           assert '## 1. Document Control, Metadata & Classification' in '# Project: CoChem-BASE Agent Configuration Fix & Sanitization\n\n## Architecture\n- Target Directory: `D:\\Gdrive\\__...xecute read-only checks and verification commands against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.\n'

tests\test_project_refactor.py:91: AssertionError
______________________ test_agent_inventory_completeness ______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_agent_inventory_completeness(target_file: Path) -> None:
        """Verify all 15 agents are documented in the specification inventory."""
        content = target_file.read_text(encoding="utf-8")
    
        expected_agents = [
            "0rchestrator.agent.md",
            "artist.agent.md",
            "cochem-audit.agent.md",
            "cochem-coder.agent.md",
            "cochem-debug.agent.md",
            "cochem-helper.agent.md",
            "cochem-improve.agent.md",
            "cochem-scribe.agent.md",
            "cochem-sdp_manager.agent.md",
            "cochem-tester.agent.md",
            "educator.agent.md",
            "researcher.agent.md",
            "teacher.agent.md",
            "ui.agent.md",
            "web_mcp.agent.md",
        ]
    
        for agent in expected_agents:
>           assert agent in content, f"Missing agent reference in inventory: {agent}"
E           AssertionError: Missing agent reference in inventory: 0rchestrator.agent.md
E           assert '0rchestrator.agent.md' in '# Project: CoChem-BASE Agent Configuration Fix & Sanitization\n\n## Architecture\n- Target Directory: `D:\\Gdrive\\__...xecute read-only checks and verification commands against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.\n'

tests\test_project_refactor.py:117: AssertionError
__________________________ test_directives_coverage ___________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_directives_coverage(target_file: Path) -> None:
        """Verify all directives DIR-01 through DIR-05 are registered."""
        content = target_file.read_text(encoding="utf-8")
    
        for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
>           assert dir_tag in content, f"Missing directive registration: {dir_tag}"
E           AssertionError: Missing directive registration: DIR-01
E           assert 'DIR-01' in '# Project: CoChem-BASE Agent Configuration Fix & Sanitization\n\n## Architecture\n- Target Directory: `D:\\Gdrive\\__...xecute read-only checks and verification commands against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.\n'

tests\test_project_refactor.py:125: AssertionError
_________________________ test_mermaid_syntax_blocks __________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_mermaid_syntax_blocks(target_file: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed."""
        content = target_file.read_text(encoding="utf-8")
    
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 2 Mermaid diagrams, found 0
E       assert 0 >= 2
E        +  where 0 = len([])

tests\test_project_refactor.py:133: AssertionError
_________________ test_method_matrix_and_zero_mock_invariants _________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_method_matrix_and_zero_mock_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules and Zero-Mock invariants are specified in acceptance criteria."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "defgrid1" in content and "defgrid3" in content
E       AssertionError: assert ('defgrid1' in '# Project: CoChem-BASE Agent Configuration Fix & Sanitization\n\n## Architecture\n- Target Directory: `D:\\Gdrive\\__...xecute read-only checks and verification commands against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.\n')

tests\test_project_refactor.py:144: AssertionError
_______________________ test_state_artifacts_referenced _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_state_artifacts_referenced(target_file: Path) -> None:
        """Verify all orchestrator state tracking artifacts are referenced."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "progress.md" in content
E       AssertionError: assert 'progress.md' in '# Project: CoChem-BASE Agent Configuration Fix & Sanitization\n\n## Architecture\n- Target Directory: `D:\\Gdrive\\__...xecute read-only checks and verification commands against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.\n'

tests\test_project_refactor.py:156: AssertionError
_________________________ test_wbs_granularity_depth __________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/orchestrator/PROJECT.md')

    def test_wbs_granularity_depth(target_file: Path) -> None:
        """Verify that WBS defines at least 3 levels of granularity (Milestone/Task -> Sub-task -> Sub-sub-task)."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "Task" in content
E       AssertionError: assert 'Task' in '# Project: CoChem-BASE Agent Configuration Fix & Sanitization\n\n## Architecture\n- Target Directory: `D:\\Gdrive\\__...xecute read-only checks and verification commands against `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents`.\n'

tests\test_project_refactor.py:168: AssertionError
_______________ test_sentinel_handoff_zero_personal_path_leaks ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_zero_personal_path_leaks(target_file: Path) -> None:
        """Verify zero personal/machine path leakage across the entire document."""
        content = target_file.read_text(encoding="utf-8")
        leaks = find_path_leaks(content)
>       assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
E       AssertionError: Detected 2 path leak(s): [(7, '<USER_HOME>', '1. Project Orchestrator dispatched and coordinated 9 subagent workers/explorers/reviewers to overwrite files and sanitize absolute paths (`C:\\Users\\ansac` -> `<USER_HOME>`, `D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`).'), (21, '<USER_HOME>', '- Search for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.')]
E       assert 2 == 0
E        +  where 2 = len([(7, '<USER_HOME>', '1. Project Orchestrator dispatched and coordinated 9 subagent workers/explorers/reviewers to over...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.')])

tests\test_sentinel_handoff_refactor.py:59: AssertionError
_______________ test_sentinel_handoff_canonical_tokens_present ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized."""
        content = target_file.read_text(encoding="utf-8")
        for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
>           assert token in content, f"Missing canonical token: {token}"
E           AssertionError: Missing canonical token: <COCHEM_ROOT>
E           assert '<COCHEM_ROOT>' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

tests\test_sentinel_handoff_refactor.py:66: AssertionError
______________ test_sentinel_handoff_canonical_sections_present _______________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections are present in sentinel/handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Mission Directives & Sentinel Swarm Oversight",
            "## 4. Milestone Lifecycle & Multi-Phase Victory Audit Verification",
            "## 5. Subagent Swarm Roster, Gate Consensus & 15-Agent Inventory",
            "## 6. Acceptance Criteria, Quality Gates & Method Matrix Verification",
            "## 7. Key Oversight Artifacts, Cleanup Actions & Final Sign-off Protocol",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Document Control, Metadata & Classification
E           assert '## 1. Document Control, Metadata & Classification' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

tests\test_sentinel_handoff_refactor.py:84: AssertionError
_______________ test_sentinel_handoff_identity_and_audit_fields _______________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_identity_and_audit_fields(target_file: Path) -> None:
        """Verify Sentinel identity, Orchestrator ID, and Victory Auditor fields."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "sentinel" in content
E       AssertionError: assert 'sentinel' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

tests\test_sentinel_handoff_refactor.py:91: AssertionError
____________ test_sentinel_handoff_15_agent_inventory_completeness ____________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_15_agent_inventory_completeness(target_file: Path) -> None:
        """Verify all 15 agents are documented in the handoff inventory."""
        content = target_file.read_text(encoding="utf-8")
    
        expected_agents = [
            "0rchestrator.agent.md",
            "artist.agent.md",
            "cochem-audit.agent.md",
            "cochem-coder.agent.md",
            "cochem-debug.agent.md",
            "cochem-helper.agent.md",
            "cochem-improve.agent.md",
            "cochem-scribe.agent.md",
            "cochem-sdp_manager.agent.md",
            "cochem-tester.agent.md",
            "educator.agent.md",
            "researcher.agent.md",
            "teacher.agent.md",
            "ui.agent.md",
            "web_mcp.agent.md",
        ]
    
        for agent in expected_agents:
>           assert agent in content, f"Missing agent reference in inventory: {agent}"
E           AssertionError: Missing agent reference in inventory: 0rchestrator.agent.md
E           assert '0rchestrator.agent.md' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

tests\test_sentinel_handoff_refactor.py:121: AssertionError
__________________ test_sentinel_handoff_directives_coverage __________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_directives_coverage(target_file: Path) -> None:
        """Verify all directives DIR-01 through DIR-05 are registered in sentinel handoff."""
        content = target_file.read_text(encoding="utf-8")
    
        for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
>           assert dir_tag in content, f"Missing directive registration: {dir_tag}"
E           AssertionError: Missing directive registration: DIR-01
E           assert 'DIR-01' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

tests\test_sentinel_handoff_refactor.py:129: AssertionError
_________________ test_sentinel_handoff_mermaid_syntax_blocks _________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_mermaid_syntax_blocks(target_file: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed in sentinel/handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 2 Mermaid diagrams, found 0
E       assert 0 >= 2
E        +  where 0 = len([])

tests\test_sentinel_handoff_refactor.py:137: AssertionError
________ test_sentinel_handoff_method_matrix_and_zero_mock_invariants _________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_method_matrix_and_zero_mock_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules and Zero-Mock invariants are specified."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "defgrid1" in content and "defgrid3" in content
E       AssertionError: assert ('defgrid1' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n')

tests\test_sentinel_handoff_refactor.py:148: AssertionError
____________ test_sentinel_handoff_oversight_artifacts_referenced _____________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/sentinel/handoff.md')

    def test_sentinel_handoff_oversight_artifacts_referenced(target_file: Path) -> None:
        """Verify all key sentinel oversight artifacts are referenced."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "ORIGINAL_REQUEST.md" in content
E       AssertionError: assert 'ORIGINAL_REQUEST.md' in '# Handoff Report � Project Sentinel Final Completion\n\n## Observation\nAll 15 CoChem-Antigravity agent configuration...ch for personal paths `C:\\Users\\ansac` and `D:\\Gdrive\\__CoChem` returned 0 results across `CoChem-BASE/.agents`.\n'

tests\test_sentinel_handoff_refactor.py:160: AssertionError
_______________________ test_yaml_frontmatter_validity ________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teacher.agent.md')

    def test_yaml_frontmatter_validity(target_file: Path) -> None:
        """Verify valid YAML frontmatter and required schema attributes."""
        content = target_file.read_text(encoding="utf-8")
        assert content.startswith("---"), "Document must start with YAML frontmatter delimiter (---)"
        parts = content.split("---", 2)
        assert len(parts) >= 3, "Frontmatter must be enclosed between '---' delimiters"
    
        fm_raw = parts[1].strip()
        data = yaml.safe_load(fm_raw)
        assert isinstance(data, dict), "Frontmatter must parse into a dictionary"
    
        assert data.get("name") == "teacher", f"Expected name 'teacher', got {data.get('name')}"
        assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
        assert "argument-hint" in data, "Missing argument-hint in frontmatter"
        assert data.get("version") == "2.0.0"
        assert data.get("domain") == "education"
        assert isinstance(data.get("routes_to"), list)
        assert "0rchestrator" in data["routes_to"]
        assert "educator" in data["routes_to"]
        assert "cochem-helper" in data["routes_to"]
>       assert "cochem-scribe" in data["routes_to"]
E       AssertionError: assert 'cochem-scribe' in ['0rchestrator', 'educator', 'cochem-helper', 'ui', 'artist']

tests\test_teacher_refactor.py:88: AssertionError
_______________________ test_canonical_sections_present _______________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teacher.agent.md')

    def test_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections and core directives are present."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "# IDENTITY AND ROLE",
            "# AUTHORITATIVE KNOWLEDGE SOURCES",
            "# CORE DIRECTIVES",
            "## 1. Socratic Scaffolding & Dynamic Vygotskian Mentorship",
            '## 2. The "Spider-Web" Protocol (Macroscopic-to-Microscopic Bridging)',
            '## 3. The Anti-Thesis Method & "Ghost Student" Analysis',
            "## 4. Tone, Presentation Accessibility & ACS Standards",
            "## 5. Method Matrix v4 Compliance in Student Guidance",
            "## 6. Local Hardware Offloading & MCP Tool Utilization",
            "## 7. Swarm State Management Protocol",
            "# GLOBAL SWARM PROTOCOLS",
            "# OUTPUT FORMAT",
            "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
            "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
            "<SWARM_AUTONOMY_MANDATE>",
            "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
            "<ADVERSARIAL_AUDIT_DIRECTIVE>",
            "<ROOT_CAUSE_MANDATE>",
            "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Socratic Scaffolding & Dynamic Vygotskian Mentorship
E           assert '## 1. Socratic Scaffolding & Dynamic Vygotskian Mentorship' in '---\nname: teacher\ndescription: Outward-facing agent for direct STUDENT interaction. Socratic learning, emails, PPTs...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

tests\test_teacher_refactor.py:122: AssertionError
___________________ test_teacher_core_directives_invariants ___________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teacher.agent.md')

    def test_teacher_core_directives_invariants(target_file: Path) -> None:
        """Verify Socratic mentorship, Spider-Web protocol, Anti-Thesis method, and ACS specs."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "Zone of Proximal Development" in content or "ZPD" in content
        assert "Research Aptitude Index" in content or "RAI" in content
        assert "Spider-Web" in content
        assert "Ghost Student" in content
>       assert "Okabe-Ito" in content
E       AssertionError: assert 'Okabe-Ito' in '---\nname: teacher\ndescription: Outward-facing agent for direct STUDENT interaction. Socratic learning, emails, PPTs...to generate mocks, bypasses, or spoofed data.\n# ===================================================================\n'

tests\test_teacher_refactor.py:133: AssertionError
________________ test_auditor_handoff_zero_personal_path_leaks ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_zero_personal_path_leaks(target_file: Path) -> None:
        """Verify zero personal/machine path leakage across the entire document."""
        content = target_file.read_text(encoding="utf-8")
        leaks = find_path_leaks(content)
>       assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
E       AssertionError: Detected 6 path leak(s): [(15, '<USER_HOME>', '   - Source directory `C:\\Users\\ansac\\.gemini\\config\\agents` contains 15 `.agent.md` files:'), (21, '<USER_HOME>', '     - `C:\\Users\\ansac` or `C:/Users/ansac` -> `<USER_HOME>`'), (43, '<USER_HOME>', '   - Scanned all 15 `.agent.md` files for regex patterns: `ansac`, `C:\\Users\\ansac`, `C:/Users/ansac`, `D:\\Gdrive\\__CoChem`, `D:/Gdrive/__CoChem`, `D:\\Gdrive`, `D:/Gdrive`.'), (48, '<USER_HOME>', "   - Observed that 34 metadata files (test scripts like `check_agents.py`, `inspect_leaks.py`, `verify_15_agents.py`, and audit logs like `review.md`, `challenge.md`, `handoff.md`, `progress.md`) contain string literals of user paths. These exist solely as test regex strings (e.g. `re.compile(r'C:\\\\Users\\\\ansac')`) and working directory logs created during review agent execution."), (57, '<USER_HOME>', '1. **Step 1 (Verification of Overwrite & Authenticity)**: Observation #1 and Observation #2 establish that all 15 `.agent.md` files in `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE\\.agents` were genuinely overwritten using the source files from `C:\\Users\\ansac\\.gemini\\config\\agents`. The 100% exact match modulo sanitization proves no files were skipped, mocked, or altered with dummy content.'), (58, '<USER_HOME>', '2. **Step 2 (Verification of Path Transformations)**: Observation #2 and Observation #3 prove that regex path replacements were actually executed on disk, scrubbing personal paths (`C:\\Users\\ansac` -> `<USER_HOME>`, `D:\\Gdrive\\__CoChem` -> `<COCHEM_WORKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`), resulting in zero personal path leaks across all 15 target agent files.')]
E       assert 6 == 0
E        +  where 6 = len([(15, '<USER_HOME>', '   - Source directory `C:\\Users\\ansac\\.gemini\\config\\agents` contains 15 `.agent.md` files:...RKSPACE>`, `D:\\Gdrive` -> `<GDRIVE_ROOT>`), resulting in zero personal path leaks across all 15 target agent files.')])

tests\test_teamwork_preview_auditor_handoff_refactor.py:59: AssertionError
________________ test_auditor_handoff_canonical_tokens_present ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_canonical_tokens_present(target_file: Path) -> None:
        """Verify standard path tokens are utilized."""
        content = target_file.read_text(encoding="utf-8")
        for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
>           assert token in content, f"Missing canonical token: {token}"
E           AssertionError: Missing canonical token: <COCHEM_ROOT>
E           assert '<COCHEM_ROOT>' in '# Handoff Report � Forensic Integrity Audit\n\n**Working Directory**: `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE... Name, Length"\n   ```\n   *Expected Output*: 15 files listed with non-zero lengths matching sanitized source files.\n'

tests\test_teamwork_preview_auditor_handoff_refactor.py:66: AssertionError
_______________ test_auditor_handoff_canonical_sections_present _______________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_canonical_sections_present(target_file: Path) -> None:
        """Verify all mandatory sections are present in handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        required_sections = [
            "## 1. Document Control, Metadata & Classification",
            "## 2. Path Token Abstraction & Sanitization Mapping",
            "## 3. Mission Objectives & Directive Scopes",
            "## 4. Milestone Lifecycle & Swarm Execution Verification",
            "## 5. Active Subagents, Multi-Agent Consensus Gates & Team Roster",
            "## 6. Acceptance Criteria, Quality Gates & Method Matrix Verification",
            "## 7. Key Orchestration Artifacts & Handoff Sign-off Protocol",
        ]
    
        for sec in required_sections:
>           assert sec in content, f"Missing required section: {sec}"
E           AssertionError: Missing required section: ## 1. Document Control, Metadata & Classification
E           assert '## 1. Document Control, Metadata & Classification' in '# Handoff Report � Forensic Integrity Audit\n\n**Working Directory**: `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE... Name, Length"\n   ```\n   *Expected Output*: 15 files listed with non-zero lengths matching sanitized source files.\n'

tests\test_teamwork_preview_auditor_handoff_refactor.py:84: AssertionError
_______________ test_auditor_handoff_identity_and_audit_fields ________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_identity_and_audit_fields(target_file: Path) -> None:
        """Verify auditor identity and verdict fields."""
        content = target_file.read_text(encoding="utf-8")
    
        assert "teamwork_preview_auditor_1" in content
        assert "39f39eb0-6bb9-4f9a-b544-6a701d124d30" in content
        assert "CLEAN" in content
>       assert "COCHEM-HANDOFF-AUDITOR-TP1-v5.1" in content
E       assert 'COCHEM-HANDOFF-AUDITOR-TP1-v5.1' in '# Handoff Report � Forensic Integrity Audit\n\n**Working Directory**: `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE... Name, Length"\n   ```\n   *Expected Output*: 15 files listed with non-zero lengths matching sanitized source files.\n'

tests\test_teamwork_preview_auditor_handoff_refactor.py:94: AssertionError
__________________ test_auditor_handoff_directives_coverage ___________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_directives_coverage(target_file: Path) -> None:
        """Verify all directives DIR-01 through DIR-05 are registered in handoff."""
        content = target_file.read_text(encoding="utf-8")
    
        for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
>           assert dir_tag in content, f"Missing directive registration: {dir_tag}"
E           AssertionError: Missing directive registration: DIR-01
E           assert 'DIR-01' in '# Handoff Report � Forensic Integrity Audit\n\n**Working Directory**: `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE... Name, Length"\n   ```\n   *Expected Output*: 15 files listed with non-zero lengths matching sanitized source files.\n'

tests\test_teamwork_preview_auditor_handoff_refactor.py:128: AssertionError
_________________ test_auditor_handoff_mermaid_syntax_blocks __________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_mermaid_syntax_blocks(target_file: Path) -> None:
        """Verify that Mermaid diagram blocks are well-formed in handoff.md."""
        content = target_file.read_text(encoding="utf-8")
    
        mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
>       assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
E       AssertionError: Expected at least 2 Mermaid diagrams, found 0
E       assert 0 >= 2
E        +  where 0 = len([])

tests\test_teamwork_preview_auditor_handoff_refactor.py:136: AssertionError
_________ test_auditor_handoff_method_matrix_and_zero_mock_invariants _________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_method_matrix_and_zero_mock_invariants(target_file: Path) -> None:
        """Verify Method Matrix rules and Zero-Mock invariants are specified."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "defgrid1" in content and "defgrid3" in content
E       assert ('defgrid1' in '# Handoff Report � Forensic Integrity Audit\n\n**Working Directory**: `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE... Name, Length"\n   ```\n   *Expected Output*: 15 files listed with non-zero lengths matching sanitized source files.\n')

tests\test_teamwork_preview_auditor_handoff_refactor.py:147: AssertionError
_____________ test_auditor_handoff_oversight_artifacts_referenced _____________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_oversight_artifacts_referenced(target_file: Path) -> None:
        """Verify all key oversight artifacts are referenced."""
        content = target_file.read_text(encoding="utf-8")
    
>       assert "ORIGINAL_REQUEST.md" in content
E       assert 'ORIGINAL_REQUEST.md' in '# Handoff Report � Forensic Integrity Audit\n\n**Working Directory**: `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE... Name, Length"\n   ```\n   *Expected Output*: 15 files listed with non-zero lengths matching sanitized source files.\n'

tests\test_teamwork_preview_auditor_handoff_refactor.py:159: AssertionError
__________________ test_auditor_handoff_milestones_coverage ___________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/teamwork_preview_auditor_1/handoff.md')

    def test_auditor_handoff_milestones_coverage(target_file: Path) -> None:
        """Verify milestones M1 through M6 are accounted for."""
        content = target_file.read_text(encoding="utf-8")
    
        for m in ["M1", "M2", "M3", "M4", "M5", "M6"]:
>           assert m in content, f"Missing milestone {m} in handoff.md"
E           AssertionError: Missing milestone M1 in handoff.md
E           assert 'M1' in '# Handoff Report � Forensic Integrity Audit\n\n**Working Directory**: `D:\\Gdrive\\__CoChem\\GitHub-Repo\\CoChem-BASE... Name, Length"\n   ```\n   *Expected Output*: 15 files listed with non-zero lengths matching sanitized source files.\n'

tests\test_teamwork_preview_auditor_handoff_refactor.py:175: AssertionError
============================== warnings summary ===============================
test_suite\run_tests.py:24
  D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\run_tests.py:24: PytestCollectionWarning: cannot collect test class 'TestResult' because it has a __init__ constructor (from: test_suite/test_run_tests.py)
    class TestResult(BaseModel):

test_suite/test_cochem_mint_ingestor.py: 1 warning
test_suite/test_cochem_unity_installer_dashboard.py: 6 warnings
test_suite/test_fast_pass_widget.py: 16 warnings
tests/test_matrix_dashboard_keep_codespaces_actions.py: 1 warning
tests/test_matrix_dashboard_keep_codespaces_hpc.py: 1 warning
tests/test_matrix_dashboard_new_codespaces_actions.py: 1 warning
  C:\Users\ansac\anaconda3\Lib\site-packages\traitlets\traitlets.py:1385: DeprecationWarning: Passing unrecognized arguments to super(Layout).__init__(overflow_y='auto').
  object.__init__() takes exactly one argument (the instance to initialize)
  This is deprecated in traitlets 4.2.This error will be raised in a future release of traitlets.
    warn(

test_suite/test_cochem_unity_installer_dashboard.py::test_synap_installer_gui_initialization
test_suite/test_cochem_unity_installer_dashboard.py::test_git_hash_resolution
test_suite/test_cochem_unity_installer_dashboard.py::test_has_staged_orca_archive
test_suite/test_cochem_unity_installer_dashboard.py::test_extract_upload_entries_and_stage_orca
test_suite/test_cochem_unity_installer_dashboard.py::test_verify_host_orca_path_nonexistent
test_suite/test_cochem_unity_installer_dashboard.py::test_pure_python_deployment_airgap_zip
tests/test_matrix_dashboard_keep_codespaces_actions.py::test_matrix_dashboard_keep_codespaces_actions
tests/test_matrix_dashboard_keep_codespaces_hpc.py::test_matrix_dashboard_keep_codespaces_hpc
tests/test_matrix_dashboard_new_codespaces_actions.py::test_matrix_dashboard_new_codespaces_actions
  C:\Users\ansac\anaconda3\Lib\site-packages\traitlets\traitlets.py:1385: DeprecationWarning: Passing unrecognized arguments to super(Layout).__init__(overflow_y='auto', background_color='#f1f5f9').
  object.__init__() takes exactly one argument (the instance to initialize)
  This is deprecated in traitlets 4.2.This error will be raised in a future release of traitlets.
    warn(

test_suite/test_cochem_unity_installer_dashboard.py::test_synap_installer_gui_initialization
test_suite/test_cochem_unity_installer_dashboard.py::test_git_hash_resolution
test_suite/test_cochem_unity_installer_dashboard.py::test_has_staged_orca_archive
test_suite/test_cochem_unity_installer_dashboard.py::test_extract_upload_entries_and_stage_orca
test_suite/test_cochem_unity_installer_dashboard.py::test_verify_host_orca_path_nonexistent
test_suite/test_cochem_unity_installer_dashboard.py::test_pure_python_deployment_airgap_zip
tests/test_matrix_dashboard_keep_codespaces_actions.py::test_matrix_dashboard_keep_codespaces_actions
tests/test_matrix_dashboard_keep_codespaces_hpc.py::test_matrix_dashboard_keep_codespaces_hpc
tests/test_matrix_dashboard_new_codespaces_actions.py::test_matrix_dashboard_new_codespaces_actions
  C:\Users\ansac\anaconda3\Lib\site-packages\traitlets\traitlets.py:1385: DeprecationWarning: Passing unrecognized arguments to super(Layout).__init__(border_radius='5px').
  object.__init__() takes exactly one argument (the instance to initialize)
  This is deprecated in traitlets 4.2.This error will be raised in a future release of traitlets.
    warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED test_suite/test_agent_artist_spec.py::test_artist_mandatory_sections_present
FAILED test_suite/test_agent_artist_spec.py::test_artist_anti_spoofing_invariants
FAILED test_suite/test_agent_audit_spec.py::test_audit_yaml_frontmatter_schema
FAILED test_suite/test_agent_audit_spec.py::test_audit_mandatory_sections_present
FAILED test_suite/test_agent_audit_spec.py::test_audit_anti_spoofing_invariants
FAILED test_suite/test_agent_coder_spec.py::test_coder_yaml_frontmatter_schema
FAILED test_suite/test_agent_coder_spec.py::test_coder_mandatory_sections_present
FAILED test_suite/test_agent_coder_spec.py::test_coder_anti_spoofing_invariants
FAILED test_suite/test_agent_debug_spec.py::test_debug_anti_spoofing_invariants
FAILED test_suite/test_agent_educator_spec.py::test_educator_yaml_frontmatter_schema
FAILED test_suite/test_agent_educator_spec.py::test_educator_mandatory_sections_present
FAILED test_suite/test_agent_educator_spec.py::test_educator_anti_spoofing_invariants
FAILED test_suite/test_agent_helper_spec.py::test_helper_mandatory_sections_present
FAILED test_suite/test_agent_orchestrator_spec.py::test_orchestrator_yaml_frontmatter_schema
FAILED test_suite/test_agent_orchestrator_spec.py::test_orchestrator_mandatory_sections_present
FAILED test_suite/test_agent_orchestrator_spec.py::test_orchestrator_anti_spoofing_invariants
FAILED test_suite/test_agent_orchestrator_spec.py::test_orchestrator_briefing_encoding_and_sanitization
FAILED test_suite/test_agent_sdp_manager_spec.py::test_sdp_manager_mandatory_sections_present
FAILED test_suite/test_agent_sdp_manager_spec.py::test_sdp_manager_anti_spoofing_invariants
FAILED test_suite/test_agent_teacher_spec.py::test_teacher_yaml_frontmatter_schema
FAILED test_suite/test_agent_teacher_spec.py::test_teacher_mandatory_sections_present
FAILED test_suite/test_agent_tester_spec.py::test_tester_mandatory_sections_present
FAILED test_suite/test_atomic_data.py::test_validator_instance_and_118_elements
FAILED test_suite/test_cochem_core_job_manager.py::test_job_config_defaults_and_validation
FAILED test_suite/test_cochem_core_job_manager.py::test_temporal_tier_assignment
FAILED test_suite/test_cochem_core_job_manager.py::test_job_submission_and_query
FAILED test_suite/test_cochem_core_job_manager.py::test_job_execution_success
FAILED test_suite/test_cochem_core_job_manager.py::test_job_execution_failure_code
FAILED test_suite/test_cochem_core_job_manager.py::test_job_timeout_enforcement
FAILED test_suite/test_cochem_core_job_manager.py::test_job_cancellation - At...
FAILED test_suite/test_cochem_core_job_manager.py::test_purge_and_history_limits
FAILED test_suite/test_cochem_core_job_manager.py::test_large_output_stream_no_deadlock
FAILED test_suite/test_cochem_core_job_manager.py::test_custom_cwd_and_env - ...
FAILED test_suite/test_cochem_core_job_manager.py::test_invalid_cwd_or_empty_command
FAILED test_suite/test_cochem_core_job_manager.py::test_list_jobs_filtering
FAILED test_suite/test_cochem_core_job_manager.py::test_process_tree_zombie_cleanup_on_timeout
FAILED test_suite/test_cochem_core_job_manager.py::test_job_cancellation_race_and_process_tree
FAILED test_suite/test_cochem_core_job_manager.py::test_massive_stream_communicate_deadlock_safety
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_init_and_context_manager
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_oom_monitor_lifecycle
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_execute_success
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_execute_failure
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_execute_timeout
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_core_dump_garbage_collection
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_artifact_sync_and_hash
FAILED test_suite/test_cochem_core_subprocess_broker.py::test_broker_zombie_reaper_active_processes
FAILED test_suite/test_cochem_core_telemetry_logger.py::test_overlap_trap_warning
FAILED test_suite/test_cochem_core_workspace_manager.py::test_scaffold_core_directories
FAILED test_suite/test_cochem_core_workspace_manager.py::test_provision_and_get_job_workspace
FAILED test_suite/test_cochem_core_workspace_manager.py::test_file_lock_context_manager
FAILED test_suite/test_cochem_core_workspace_manager.py::test_is_job_active_and_cleanup
FAILED test_suite/test_cochem_core_workspace_manager.py::test_sweep_zombie_directories
FAILED test_suite/test_cochem_core_workspace_manager.py::test_get_directory_status
FAILED test_suite/test_cochem_dock_main.py::test_file_encoding_and_lf_line_endings
FAILED test_suite/test_cochem_dock_main.py::test_lttb_decimate_preserves_non_scf_messages
FAILED test_suite/test_cochem_dock_visuals_api.py::test_file_encoding_and_lf_line_endings
FAILED test_suite/test_cochem_dock_visuals_api.py::test_axis_and_layout_models
FAILED test_suite/test_cochem_dock_visuals_api.py::test_validate_basin_id_traversal_rejection
FAILED test_suite/test_cochem_dock_visuals_api.py::test_get_spectrum_success
FAILED test_suite/test_cochem_dock_visuals_api.py::test_get_spectrum_with_broadening
FAILED test_suite/test_cochem_dock_visuals_api.py::test_get_spectrum_raman_and_both_modes
FAILED test_suite/test_cochem_dock_visuals_api.py::test_get_potential_energy_surface_not_found
FAILED test_suite/test_cochem_dock_visuals_api.py::test_lazy_loading_interface_exports
FAILED test_suite/test_cochem_dock_visuals_api.py::test_interfaces_cochem_dock_visuals_api_file_integrity
FAILED test_suite/test_cochem_mint_ingestor.py::test_generate_3d_geometry_ethanol
FAILED test_suite/test_cochem_mint_ingestor.py::test_generate_3d_geometry_methane
FAILED test_suite/test_cochem_mint_ingestor.py::test_resolve_smiles_pubchem
FAILED test_suite/test_forensic_check.py::test_forensic_check_encoding_and_line_endings
FAILED test_suite/test_forensic_check.py::test_main_cli - assert 1 == 0
FAILED test_suite/test_interfaces_init.py::test_docstring_and_architectural_overview
FAILED test_suite/test_interfaces_init.py::test_module_all_exports_present - ...
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[BrowserSparsityPayload]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[MatrixElement]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[SparsityDimensions]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[WebSparsityMatrix]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[WebGLPacket]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[WebGLStreamer]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[TelemetryEvent]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[app]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[dock_app]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[health_check]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[lttb_decimate]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[websocket_telemetry]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[AxisLayout]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[PlotlyLayout]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[PlotlyPayload]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[ScatterTrace]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[get_spectrum]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[router]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[visuals_router]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[FastPassWidget]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[HAS_3DMOL]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[PubChemProperty]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[PubChemPropertyTable]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[PubChemResponse]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[DeploymentManifest]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[ECOSYSTEM_REGISTRY]
FAILED test_suite/test_interfaces_init.py::test_lazy_attribute_resolution[SynapInstallerGUI]
FAILED test_suite/test_interfaces_init.py::test_aliased_exports_equivalence
FAILED test_suite/test_interfaces_init.py::test_dir_reflection_contains_all_and_globals
FAILED test_suite/test_math_assertions.py::test_assertions_file_encoding_and_lf_endings
FAILED test_suite/test_math_autograd.py::test_autograd_file_encoding_and_lf_endings
FAILED test_suite/test_math_autograd.py::test_coulomb_field_and_force_wrappers
FAILED test_suite/test_math_autograd.py::test_dual_number_powers_and_elementary_functions
FAILED test_suite/test_math_c_bindings.py::test_c_bindings_file_encoding_and_lf_endings
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_instantiation_and_properties
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_invalid_size_validation
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_pointer_and_ctypes_array
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_sequence_protocol_and_indexing
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_slice_and_item_assignment
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_iteration_reversed_and_contains
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_numpy_zero_copy_and_copy
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_from_numpy_and_from_iterable
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_fill_clear_copy
FAILED test_suite/test_math_c_bindings.py::test_safe_c_buffer_representations_and_equality
FAILED test_suite/test_math_geometry.py::test_geometry_file_encoding_and_lf_endings
FAILED test_suite/test_math_geometry.py::test_point_equality_and_closeness - ...
FAILED test_suite/test_math_geometry.py::test_point_geometric_metrics - Attri...
FAILED test_suite/test_math_geometry.py::test_point_dot_cross_midpoint_angle
FAILED test_suite/test_math_geometry.py::test_point_transformations - Attribu...
FAILED test_suite/test_math_geometry.py::test_bounding_box_valid_instantiation_and_properties
FAILED test_suite/test_math_init.py::test_file_encoding_and_lf_line_endings
FAILED test_suite/test_math_init.py::test_docstring_and_architectural_overview
FAILED test_suite/test_math_init.py::test_module_all_exports_present - Assert...
FAILED test_suite/test_math_init.py::test_dir_reflection_contains_all_and_globals
FAILED test_suite/test_plugins_init.py::test_file_encoding_and_lf_line_endings
FAILED test_suite/test_plugins_init.py::test_docstring_and_architectural_overview
FAILED test_suite/test_plugins_init.py::test_module_all_exports_present - Ass...
FAILED test_suite/test_plugins_init.py::test_lazy_attribute_resolution[CoChemStudioSpecs]
FAILED test_suite/test_plugins_init.py::test_lazy_attribute_resolution[CorePlugin]
FAILED test_suite/test_plugins_init.py::test_lazy_attribute_resolution[get_plugin_manager]
FAILED test_suite/test_plugins_init.py::test_lazy_attribute_resolution[hookimpl]
FAILED test_suite/test_plugins_init.py::test_lazy_attribute_resolution[hookspec]
FAILED test_suite/test_plugins_init.py::test_dir_reflection_contains_all_and_globals
FAILED test_suite/test_plugins_init.py::test_plugin_manager_lifecycle_and_hooks
FAILED test_suite/test_plugins_init.py::test_core_plugin_registration - Attri...
FAILED test_suite/test_plugins_internal.py::test_internal_file_encoding_and_lf_line_endings
FAILED test_suite/test_plugins_internal.py::test_internal_docstrings_and_module_overview
FAILED test_suite/test_plugins_loader.py::test_loader_file_encoding_and_lf_line_endings
FAILED test_suite/test_plugins_loader.py::test_loader_docstrings_and_module_overview
FAILED test_suite/test_run_tests.py::test_run_tests_file_integrity_and_lf_endings
FAILED test_suite/test_run_tests.py::test_test_result_model_validation - Attr...
FAILED test_suite/test_run_tests.py::test_direct_script_subprocess_execution
FAILED test_suite/test_sentinel_briefing_spec.py::test_sentinel_briefing_path_sanitization_and_no_leaks
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_zero_personal_path_leaks
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_canonical_tokens_present
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_canonical_sections_present
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_identity_and_audit_fields
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_15_agent_inventory_completeness
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_directives_coverage
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_mermaid_syntax_blocks
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_method_matrix_and_zero_mock_invariants
FAILED test_suite/test_sentinel_handoff_spec.py::test_sentinel_handoff_oversight_artifacts_referenced
FAILED test_suite/test_silo_setup_pass2.py::test_new_install_default_paths - ...
FAILED test_suite/test_teamwork_preview_auditor_1_audit_spec.py::test_auditor_audit_path_sanitization_and_no_leaks
FAILED test_suite/test_teamwork_preview_auditor_1_audit_spec.py::test_auditor_audit_mandatory_sections_present
FAILED test_suite/test_teamwork_preview_auditor_1_audit_spec.py::test_auditor_audit_identity_and_audit_fields
FAILED test_suite/test_teamwork_preview_auditor_1_audit_spec.py::test_auditor_audit_mermaid_diagrams_present
FAILED test_suite/test_teamwork_preview_auditor_1_audit_spec.py::test_auditor_audit_method_matrix_and_zero_mock_invariants
FAILED test_suite/test_teamwork_preview_auditor_1_briefing_spec.py::test_auditor_briefing_path_sanitization_and_no_leaks
FAILED test_suite/test_teamwork_preview_auditor_1_briefing_spec.py::test_auditor_briefing_identity_and_audit_fields
FAILED test_suite/test_teamwork_preview_auditor_1_dispatch_spec.py::test_auditor_dispatch_path_sanitization_and_no_leaks
FAILED test_suite/test_teamwork_preview_auditor_1_dispatch_spec.py::test_auditor_dispatch_mandatory_sections_present
FAILED test_suite/test_teamwork_preview_auditor_1_dispatch_spec.py::test_auditor_dispatch_working_dir_and_targets
FAILED test_suite/test_thermo_constants.py::test_file_encoding_and_lf_line_endings
FAILED test_suite/test_thermo_constants.py::test_thermodynamic_calculations
FAILED test_suite/test_torq_gui.py::TestTorqWorkerExecution::test_torq_worker_cancellation
FAILED test_suite/test_torq_gui.py::TestTorqTabWidget::test_torq_tab_didactic_toggle_and_topic_selection
FAILED test_suite/test_web_matrices.py::test_file_encoding_and_lf_line_endings
FAILED test_suite/test_web_matrices.py::test_module_all_exports - AssertionEr...
FAILED test_suite/test_web_matrices.py::test_interfaces_package_lazy_resolution
FAILED test_suite/test_web_matrices.py::test_sparsity_dimensions_model - Attr...
FAILED test_suite/test_web_matrices.py::test_matrix_element_model - Attribute...
FAILED test_suite/test_web_matrices.py::test_browser_sparsity_payload_model
FAILED test_suite/test_web_matrices.py::test_matrix_init_empty - AttributeErr...
FAILED test_suite/test_web_matrices.py::test_matrix_init_with_dict_elements
FAILED test_suite/test_web_matrices.py::test_matrix_init_with_matrix_element_instances
FAILED test_suite/test_web_matrices.py::test_matrix_init_with_tuples - TypeEr...
FAILED test_suite/test_web_matrices.py::test_matrix_init_invalid_data - TypeE...
FAILED test_suite/test_web_matrices.py::test_matrix_init_negative_dimensions
FAILED test_suite/test_web_matrices.py::test_from_dense_factory - AttributeEr...
FAILED test_suite/test_web_matrices.py::test_from_coo_factory - AttributeErro...
FAILED test_suite/test_web_matrices.py::test_from_dict_factory - AttributeErr...
FAILED test_suite/test_web_matrices.py::test_identity_factory - AttributeErro...
FAILED test_suite/test_web_matrices.py::test_bounds_validation_get_and_remove_element
FAILED test_suite/test_web_matrices.py::test_bounds_validation_dunder_indexing
FAILED test_suite/test_web_matrices.py::test_type_error_on_invalid_key_type
FAILED test_suite/test_web_matrices.py::test_dunder_indexing_and_defaults - T...
FAILED test_suite/test_web_matrices.py::test_dunder_deletion - TypeError: 'We...
FAILED test_suite/test_web_matrices.py::test_dunder_contains - TypeError: 'We...
FAILED test_suite/test_web_matrices.py::test_dunder_iter_and_len - TypeError:...
FAILED test_suite/test_web_matrices.py::test_dunder_repr - TypeError: 'WebSpa...
FAILED test_suite/test_web_matrices.py::test_dunder_eq - TypeError: 'WebSpars...
FAILED test_suite/test_web_matrices.py::test_density_and_is_empty_properties
FAILED test_suite/test_web_matrices.py::test_get_and_remove_element - TypeErr...
FAILED test_suite/test_web_matrices.py::test_prune_zeros - TypeError: 'WebSpa...
FAILED test_suite/test_web_matrices.py::test_clear - AttributeError: type obj...
FAILED test_suite/test_web_matrices.py::test_to_dense_round_trip - AttributeE...
FAILED test_suite/test_web_matrices.py::test_to_dict_export - TypeError: 'Web...
FAILED test_suite/test_web_matrices.py::test_binary_packing_types_and_little_endian
FAILED test_suite/test_web_matrices.py::test_browser_sparsity_round_trip - Ty...
FAILED test_suite/test_web_matrices.py::test_from_browser_format_json_and_dict
FAILED test_suite/test_web_matrices.py::test_decode_coo_corrupted_base64 - At...
FAILED test_suite/test_web_matrices.py::test_decode_coo_misaligned_bytes - At...
FAILED test_suite/test_web_matrices.py::test_decode_coo_mismatched_array_lengths
FAILED test_suite/test_web_matrices.py::test_matrix_addition_and_subtraction
FAILED test_suite/test_web_matrices.py::test_scalar_multiplication_and_division
FAILED test_suite/test_web_matrices.py::test_matrix_multiplication - TypeErro...
FAILED test_suite/test_web_matrices.py::test_matrix_trace_diagonal_symmetric_bandwidth
FAILED test_suite/test_web_matrices.py::test_matrix_norms - TypeError: cochem...
FAILED test_suite/test_web_matrices.py::test_matrix_slicing_retrieval_and_assignment
FAILED test_suite/test_web_matrices.py::test_csr_and_csc_conversions - Attrib...
FAILED test_suite/test_web_matrices.py::test_kronecker_product - AttributeErr...
FAILED test_suite/test_web_matrices.py::test_block_diag_assembly - AttributeE...
FAILED test_suite/test_web_matrices.py::test_random_and_diag_generators - Att...
FAILED test_suite/test_web_matrices.py::test_matrix_chunking_for_webgl - Attr...
FAILED test_suite/test_web_matrices.py::test_transformations_and_json - TypeE...
FAILED test_suite/test_web_streaming.py::test_physical_stream_sparsity_payload
FAILED tests/test_artist_refactor.py::test_yaml_frontmatter_validity - Assert...
FAILED tests/test_artist_refactor.py::test_canonical_sections_present - Asser...
FAILED tests/test_artist_refactor.py::test_artist_core_directives_invariants
FAILED tests/test_artist_refactor.py::test_mcp_hardware_offloading - assert '...
FAILED tests/test_artist_refactor.py::test_anti_spoofing_directives - assert ...
FAILED tests/test_briefing_refactor.py::test_briefing_canonical_tokens_present
FAILED tests/test_cochem_audit_refactor.py::test_yaml_frontmatter_validity - ...
FAILED tests/test_cochem_audit_refactor.py::test_canonical_sections_present
FAILED tests/test_cochem_audit_refactor.py::test_anti_spoofing_and_audit_directives
FAILED tests/test_cochem_coder_refactor.py::test_yaml_frontmatter_validity - ...
FAILED tests/test_cochem_coder_refactor.py::test_canonical_sections_present
FAILED tests/test_cochem_coder_refactor.py::test_method_matrix_invariants - A...
FAILED tests/test_cochem_coder_refactor.py::test_hardware_and_workflow_efficiency
FAILED tests/test_cochem_coder_refactor.py::test_mcp_hardware_offloading - As...
FAILED tests/test_cochem_coder_refactor.py::test_heading_hierarchy_integrity
FAILED tests/test_cochem_coder_refactor.py::test_behavior_boundaries_defined
FAILED tests/test_cochem_helper_refactor.py::test_canonical_sections_present
FAILED tests/test_cochem_helper_refactor.py::test_method_matrix_invariants - ...
FAILED tests/test_cochem_helper_refactor.py::test_heading_hierarchy_integrity
FAILED tests/test_cochem_scribe_refactor.py::test_method_matrix_provenance_and_quantum_invariants
FAILED tests/test_cochem_scribe_refactor.py::test_latex_mermaid_and_si_unit_standardization
FAILED tests/test_cochem_scribe_refactor.py::test_heading_hierarchy_integrity
FAILED tests/test_cochem_scribe_refactor.py::test_behavior_boundaries_defined
FAILED tests/test_dispatch_refactor.py::test_canonical_tokens_present - Asser...
FAILED tests/test_dispatch_refactor.py::test_canonical_sections_present - Ass...
FAILED tests/test_dispatch_refactor.py::test_agent_inventory_completeness - A...
FAILED tests/test_dispatch_refactor.py::test_directives_coverage - AssertionE...
FAILED tests/test_dispatch_refactor.py::test_mermaid_syntax_blocks - Assertio...
FAILED tests/test_dispatch_refactor.py::test_method_matrix_and_zero_mock_invariants
FAILED tests/test_dispatch_refactor.py::test_state_artifacts_referenced - Ass...
FAILED tests/test_e2e_local_unit.py::TestRegistryManagerAndAtomicData::test_get_all_isotopes
FAILED tests/test_e2e_local_unit.py::TestRegistryManagerAndAtomicData::test_embedded_basis_set_archival
FAILED tests/test_e2e_local_unit.py::TestRegistryManagerAndAtomicData::test_legacy_schema_migration
FAILED tests/test_e2e_local_unit.py::TestMolecularModelingWaterDimer::test_water_dimer_xyz_roundtrip
FAILED tests/test_e2e_local_unit.py::TestExecutionRouterAndJobManagerLifecycle::test_job_manager_temporal_tier_assignment
FAILED tests/test_e2e_local_unit.py::TestExecutionRouterAndJobManagerLifecycle::test_job_manager_real_job_execution
FAILED tests/test_e2e_local_unit.py::TestExecutionRouterAndJobManagerLifecycle::test_job_manager_cancellation
FAILED tests/test_e2e_local_unit.py::TestExecutionRouterAndJobManagerLifecycle::test_job_manager_purge_and_history
FAILED tests/test_e2e_local_unit.py::TestQuantumParserAndHDF5State::test_quantum_parser_spin_contamination
FAILED tests/test_educator_refactor.py::test_canonical_sections_present - Ass...
FAILED tests/test_educator_refactor.py::test_pedagogical_frameworks_mandates
FAILED tests/test_educator_refactor.py::test_friction_and_misconceptions - As...
FAILED tests/test_educator_refactor.py::test_automated_grading_and_ast_auditing
FAILED tests/test_educator_refactor.py::test_method_matrix_invariants - Asser...
FAILED tests/test_educator_refactor.py::test_behavior_boundaries_defined - As...
FAILED tests/test_handoff_refactor.py::test_zero_personal_path_leaks - Assert...
FAILED tests/test_handoff_refactor.py::test_canonical_tokens_present - Assert...
FAILED tests/test_handoff_refactor.py::test_canonical_sections_present - Asse...
FAILED tests/test_handoff_refactor.py::test_agent_inventory_completeness - As...
FAILED tests/test_handoff_refactor.py::test_directives_coverage - AssertionEr...
FAILED tests/test_handoff_refactor.py::test_mermaid_syntax_blocks - Assertion...
FAILED tests/test_handoff_refactor.py::test_method_matrix_and_zero_mock_invariants
FAILED tests/test_handoff_refactor.py::test_state_artifacts_referenced - Asse...
FAILED tests/test_handoff_refactor.py::test_milestones_coverage - AssertionEr...
FAILED tests/test_method_matrix_refactor.py::test_unix_lf_line_endings[target_file1]
FAILED tests/test_method_matrix_refactor.py::test_no_hardcoded_linux_user_paths[target_file1]
FAILED tests/test_method_matrix_refactor.py::test_canonical_tokens_present[target_file1]
FAILED tests/test_method_matrix_refactor.py::test_primary_sections_present[target_file1]
FAILED tests/test_progress_refactor.py::test_canonical_sections_present - Ass...
FAILED tests/test_progress_refactor.py::test_agent_inventory_completeness - A...
FAILED tests/test_progress_refactor.py::test_directives_coverage - AssertionE...
FAILED tests/test_progress_refactor.py::test_mermaid_syntax_blocks - Assertio...
FAILED tests/test_progress_refactor.py::test_state_artifacts_referenced - Ass...
FAILED tests/test_project_refactor.py::test_zero_personal_path_leaks - Assert...
FAILED tests/test_project_refactor.py::test_canonical_tokens_present - Assert...
FAILED tests/test_project_refactor.py::test_canonical_sections_present - Asse...
FAILED tests/test_project_refactor.py::test_agent_inventory_completeness - As...
FAILED tests/test_project_refactor.py::test_directives_coverage - AssertionEr...
FAILED tests/test_project_refactor.py::test_mermaid_syntax_blocks - Assertion...
FAILED tests/test_project_refactor.py::test_method_matrix_and_zero_mock_invariants
FAILED tests/test_project_refactor.py::test_state_artifacts_referenced - Asse...
FAILED tests/test_project_refactor.py::test_wbs_granularity_depth - Assertion...
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_zero_personal_path_leaks
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_canonical_tokens_present
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_canonical_sections_present
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_identity_and_audit_fields
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_15_agent_inventory_completeness
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_directives_coverage
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_mermaid_syntax_blocks
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_method_matrix_and_zero_mock_invariants
FAILED tests/test_sentinel_handoff_refactor.py::test_sentinel_handoff_oversight_artifacts_referenced
FAILED tests/test_teacher_refactor.py::test_yaml_frontmatter_validity - Asser...
FAILED tests/test_teacher_refactor.py::test_canonical_sections_present - Asse...
FAILED tests/test_teacher_refactor.py::test_teacher_core_directives_invariants
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_zero_personal_path_leaks
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_canonical_tokens_present
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_canonical_sections_present
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_identity_and_audit_fields
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_directives_coverage
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_mermaid_syntax_blocks
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_method_matrix_and_zero_mock_invariants
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_oversight_artifacts_referenced
FAILED tests/test_teamwork_preview_auditor_handoff_refactor.py::test_auditor_handoff_milestones_coverage
ERROR tests/test_method_matrix_refactor.py::test_file_exists_and_non_empty[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_unix_lf_line_endings[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_utf8_encoding_no_bom[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_zero_personal_path_leaks[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_no_hardcoded_linux_user_paths[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_canonical_tokens_present[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_clean_markdown_no_raw_directive_xml[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_code_fence_balance[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_primary_sections_present[target_file0]
ERROR tests/test_method_matrix_refactor.py::test_provenance_and_method_matrix_invariants[target_file0]
ERROR tests/test_old_plan_method_matrix.py::test_file_exists_and_non_empty - ...
ERROR tests/test_old_plan_method_matrix.py::test_unix_lf_line_endings - Asser...
ERROR tests/test_old_plan_method_matrix.py::test_utf8_encoding_no_bom - Asser...
ERROR tests/test_old_plan_method_matrix.py::test_zero_personal_path_leaks - A...
ERROR tests/test_old_plan_method_matrix.py::test_no_hardcoded_linux_user_paths
ERROR tests/test_old_plan_method_matrix.py::test_canonical_tokens_present - A...
ERROR tests/test_old_plan_method_matrix.py::test_clean_markdown_no_raw_directive_xml
ERROR tests/test_old_plan_method_matrix.py::test_code_fence_balance - Asserti...
ERROR tests/test_old_plan_method_matrix.py::test_primary_sections_present - A...
ERROR tests/test_old_plan_method_matrix.py::test_all_ten_domain_tables_present_and_valid
ERROR tests/test_old_plan_method_matrix.py::test_provenance_and_method_matrix_invariants
ERROR tests/test_old_plan_method_matrix.py::test_works_cited_citations_hyperlinked
==== 311 failed, 1539 passed, 45 warnings, 22 errors in 351.39s (0:05:51) =====

Error: 