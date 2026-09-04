Cycle 2: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_01_Ecosystem_Part_1_prompts.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0 -- C:\Users\ansac\anaconda3\python.exe
cachedir: .pytest_cache
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, hydra-core-1.3.5, typeguard-4.6.0, zarr-3.3.0
collecting ... collected 55 items

src/cochem_base/engines/test_scribe_engine.py::test_engine_inheritance_and_contract PASSED [  1%]
src/cochem_base/engines/test_scribe_engine.py::test_dry_run_engine_generation_and_streaming PASSED [  3%]
src/cochem_base/engines/test_scribe_engine.py::test_gemini_engine_airgap_and_permissions PASSED [  5%]
src/cochem_base/engines/test_scribe_engine.py::test_zero_mock_loopback_network_resilience_and_exponential_backoff PASSED [  7%]
src/cochem_base/engines/test_scribe_engine.py::test_local_llama_engine_path_resolution_and_hardware_precheck PASSED [  9%]
src/cochem_base/engines/test_scribe_engine.py::test_local_llama_engine_oom_kernel_trap PASSED [ 10%]
src/cochem_base/engines/test_scribe_engine.py::test_factory_router_hardware_and_flag_dispatch PASSED [ 12%]
src/cochem_base/engines/test_scribe_engine.py::test_fair_cost_and_token_telemetry_tracker PASSED [ 14%]
src/cochem_base/engines/test_scribe_engine.py::test_async_ui_wrapper_execution PASSED [ 16%]
src/cochem_base/engines/test_scribe_engine.py::test_cli_preflight_execution PASSED [ 18%]
src/cochem_base/engines/test_scribe_engine.py::test_anti_spoof_ast_compliance PASSED [ 20%]
src/cochem_base/engines/test_scribe_engine.py::test_async_generate_wrapper PASSED [ 21%]
src/cochem_base/engines/test_scribe_engine.py::test_local_llama_engine_hardware_and_oom_trap PASSED [ 23%]
src/cochem_base/engines/test_scribe_engine.py::test_factory_router_get_engine PASSED [ 25%]
src/cochem_base/engines/test_scribe_engine.py::test_telemetry_and_audit_logging PASSED [ 27%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_document_manager_initialization PASSED [ 29%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_latex_compilation_genuine_or_fallback PASSED [ 30%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_latex_error_trapping_invalid_syntax PASSED [ 32%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_cleanup_intermediate_files PASSED [ 34%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_manifest_generation_and_hashing PASSED [ 36%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_archive_creation_and_permission_lock PASSED [ 38%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_package_final_report_e2e PASSED [ 40%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_package_final_report_failed_latex_cleans_scratch_unconditionally PASSED [ 41%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_run_timestamp_directory_packaging PASSED [ 43%]
src/cochem_base/managers/test_scribe_doc_manager.py::test_genuine_compilation_task90 PASSED [ 45%]
tests/core/test_physics_integrity_part8.py::test_krr_chunked_prediction_numerical_parity_and_memory_cap PASSED [ 47%]
tests/core/test_physics_integrity_part8.py::test_pes_store_normalized_provenance_and_swmr PASSED [ 49%]
tests/core/test_physics_integrity_part8.py::test_cfour_streaming_parser_parity_and_low_memory PASSED [ 50%]
tests/test_cochem_mint.py::test_single_xyz_ingestion FAILED              [ 52%]
tests/test_cochem_mint.py::test_non_destructive_cartesian_indexing FAILED [ 54%]
tests/test_cochem_mint.py::test_sha256_provenance_and_caching FAILED     [ 56%]
tests/test_cochem_mint.py::test_mol_format_ingestion FAILED              [ 58%]
tests/test_cochem_mint.py::test_batch_directory_scanning FAILED          [ 60%]
tests/test_cochem_mint.py::test_io_fallback_scratch_resolution FAILED    [ 61%]
tests/test_cochem_mint.py::test_config_binding FAILED                    [ 63%]
tests/test_cochem_mint.py::test_malformed_and_edge_cases PASSED          [ 65%]
tests/test_cochem_mint.py::test_pydantic_payload_serialization FAILED    [ 67%]
tests/test_cochem_mint.py::test_co2_h2o_complex_ingestion FAILED         [ 69%]
tests/test_cochem_mint.py::test_benzene_planar_geometry_ingestion FAILED [ 70%]
tests/core/test_srs_chunk01_ecosystem.py::test_exception_hierarchy PASSED [ 72%]
tests/core/test_srs_chunk01_ecosystem.py::test_binary_registry_and_path_registry PASSED [ 74%]
tests/core/test_srs_chunk01_ecosystem.py::test_schemas_gradient_payload_optional_hessian PASSED [ 76%]
tests/core/test_srs_chunk01_ecosystem.py::test_generate_frozen_monomer_constraints PASSED [ 78%]
tests/core/test_srs_chunk01_ecosystem.py::test_grid_policy PASSED        [ 80%]
tests/core/test_srs_chunk01_ecosystem.py::test_interfaces_abc PASSED     [ 81%]
tests/core/test_srs_chunk01_ecosystem.py::test_zero_mock_crest_raises_binary_not_found PASSED [ 83%]
tests/core/test_srs_chunk01_ecosystem.py::test_orca_constraint_block_frozen_monomer PASSED [ 85%]
tests/core/test_srs_chunk01_ecosystem.py::test_deck_sanitizer_calc_hess_true PASSED [ 87%]
tests/core/test_srs_chunk01_ecosystem.py::test_catalog_compiler_grid_validation PASSED [ 89%]
tests/core/test_srs_chunk01_ecosystem.py::test_discrete_counterpoise_evaluation PASSED [ 90%]
tests/core/test_srs_chunk01_ecosystem.py::test_spin_contamination_gate PASSED [ 92%]
tests/core/test_srs_chunk01_ecosystem.py::test_torq_parser_s2_regex PASSED [ 94%]
tests/core/test_srs_chunk01_ecosystem.py::test_torq_cfour_executor_scratch_and_interface PASSED [ 96%]
tests/core/test_srs_chunk01_ecosystem.py::test_topos_unit_normalization_and_screening_hessians PASSED [ 98%]
tests/core/test_srs_chunk01_ecosystem.py::test_torq_pipeline_conformer_union_and_concurrency PASSED [100%]

================================== FAILURES ===================================
__________________________ test_single_xyz_ingestion __________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_single_xyz_ingestion0')

    def test_single_xyz_ingestion(tmp_path: Path) -> None:
        """Ingest H2O and CH4; verify atom count, symbols, coordinates, and exact
        mendeleev mono-isotopic masses (M_aux), nuclear charges (Z_aux), and radii.
        """
        # 1. Test Water (H2O)
        water_file = tmp_path / "water.xyz"
        water_file.write_text(WATER_XYZ, encoding="utf-8")
    
>       payload_h2o = _invoke_ingest_file(water_file)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:316: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

file_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_single_xyz_ingestion0/water.xyz')

    def _invoke_ingest_file(file_path: Path) -> Any:
        """Dispatches ingestion to the appropriate function in the MInt module."""
        mod = _load_mint_module()
    
        # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
        if hasattr(mod, "ingest_file"):
            return mod.ingest_file(file_path)
        elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
            return mod.ingest_xyz(file_path)
        elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
            return mod.ingest_mol(file_path)
    
        # Priority 2: IngestionEngine / CoChemMInt instance
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls()
                if hasattr(engine, "ingest_file"):
                    return engine.ingest_file(file_path)
                elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                    return engine.parse_xyz(file_path)
    
>       raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible ingestion entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:265: RuntimeError
___________________ test_non_destructive_cartesian_indexing ___________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_non_destructive_cartesian0')

    def test_non_destructive_cartesian_indexing(tmp_path: Path) -> None:
        """Ingest an intentionally unsorted molecule [H, C, O, H, H, C] and assert
        that the row index order in R, M_aux, and Z_aux PRESERVES the original input
        file order 100% (sorting by mass or distance from COM is strictly forbidden).
        """
        perm_file = tmp_path / "unsorted_permutation.xyz"
        perm_file.write_text(UNSORTED_PERMUTATION_XYZ, encoding="utf-8")
    
>       payload = _invoke_ingest_file(perm_file)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:387: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

file_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_non_destructive_cartesian0/unsorted_permutation.xyz')

    def _invoke_ingest_file(file_path: Path) -> Any:
        """Dispatches ingestion to the appropriate function in the MInt module."""
        mod = _load_mint_module()
    
        # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
        if hasattr(mod, "ingest_file"):
            return mod.ingest_file(file_path)
        elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
            return mod.ingest_xyz(file_path)
        elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
            return mod.ingest_mol(file_path)
    
        # Priority 2: IngestionEngine / CoChemMInt instance
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls()
                if hasattr(engine, "ingest_file"):
                    return engine.ingest_file(file_path)
                elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                    return engine.parse_xyz(file_path)
    
>       raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible ingestion entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:265: RuntimeError
_____________________ test_sha256_provenance_and_caching ______________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_sha256_provenance_and_cac0')

    def test_sha256_provenance_and_caching(tmp_path: Path) -> None:
        """Verify SHA-256 calculation matches hashlib.sha256 of file bytes, and
        verify duplicate detection and caching behaviors.
        """
        benzene_file = tmp_path / "benzene.xyz"
        raw_bytes = BENZENE_XYZ.encode("utf-8")
        benzene_file.write_bytes(raw_bytes)
    
        expected_hash = hashlib.sha256(raw_bytes).hexdigest()
    
>       payload1 = _invoke_ingest_file(benzene_file)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:444: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

file_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_sha256_provenance_and_cac0/benzene.xyz')

    def _invoke_ingest_file(file_path: Path) -> Any:
        """Dispatches ingestion to the appropriate function in the MInt module."""
        mod = _load_mint_module()
    
        # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
        if hasattr(mod, "ingest_file"):
            return mod.ingest_file(file_path)
        elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
            return mod.ingest_xyz(file_path)
        elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
            return mod.ingest_mol(file_path)
    
        # Priority 2: IngestionEngine / CoChemMInt instance
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls()
                if hasattr(engine, "ingest_file"):
                    return engine.ingest_file(file_path)
                elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                    return engine.parse_xyz(file_path)
    
>       raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible ingestion entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:265: RuntimeError
__________________________ test_mol_format_ingestion __________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_mol_format_ingestion0')

    def test_mol_format_ingestion(tmp_path: Path) -> None:
        """Ingest standard MOL/SDF format (V2000) and verify atom coordinates, symbols,
        and metadata parsing.
        """
        # 1. Water MOL
        water_mol_file = tmp_path / "water.mol"
        water_mol_file.write_text(WATER_MOL_V2000, encoding="utf-8")
    
>       payload_water = _invoke_ingest_file(water_mol_file)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:477: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

file_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_mol_format_ingestion0/water.mol')

    def _invoke_ingest_file(file_path: Path) -> Any:
        """Dispatches ingestion to the appropriate function in the MInt module."""
        mod = _load_mint_module()
    
        # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
        if hasattr(mod, "ingest_file"):
            return mod.ingest_file(file_path)
        elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
            return mod.ingest_xyz(file_path)
        elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
            return mod.ingest_mol(file_path)
    
        # Priority 2: IngestionEngine / CoChemMInt instance
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls()
                if hasattr(engine, "ingest_file"):
                    return engine.ingest_file(file_path)
                elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                    return engine.parse_xyz(file_path)
    
>       raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible ingestion entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:265: RuntimeError
________________________ test_batch_directory_scanning ________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_batch_directory_scanning0')

    def test_batch_directory_scanning(tmp_path: Path) -> None:
        """Create a directory with multiple .xyz and .mol files, scan with bounded
        ThreadPool/ProcessPool, verify all files are ingested and returned.
        """
        scan_dir = tmp_path / "batch_input"
        scan_dir.mkdir(parents=True, exist_ok=True)
    
        (scan_dir / "water.xyz").write_text(WATER_XYZ, encoding="utf-8")
        (scan_dir / "methane.xyz").write_text(METHANE_XYZ, encoding="utf-8")
        (scan_dir / "co2.xyz").write_text(CARBON_DIOXIDE_XYZ, encoding="utf-8")
        (scan_dir / "benzene.xyz").write_text(BENZENE_XYZ, encoding="utf-8")
        (scan_dir / "co2_water.xyz").write_text(CO2_H2O_COMPLEX_XYZ, encoding="utf-8")
        (scan_dir / "aspirin.mol").write_text(ASPIRIN_MOL_V2000, encoding="utf-8")
    
        # Non-molecular noise files
        (scan_dir / "notes.txt").write_text("Experimental notes for batch 001", encoding="utf-8")
        (scan_dir / "data.csv").write_text("id,val\n1,10.5", encoding="utf-8")
    
>       summary = _invoke_batch_scan(scan_dir, max_workers=4)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:520: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

target_dir = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_batch_directory_scanning0/batch_input')
max_workers = 4

    def _invoke_batch_scan(target_dir: Path, max_workers: int = 4) -> Any:
        """Dispatches batch directory scan."""
        mod = _load_mint_module()
    
        if hasattr(mod, "scan_batch_directory"):
            return mod.scan_batch_directory(target_dir, max_workers=max_workers)
        elif hasattr(mod, "batch_scan"):
            return mod.batch_scan(target_dir, max_workers=max_workers)
    
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls(max_workers=max_workers)
                if hasattr(engine, "scan_batch_directory"):
                    return engine.scan_batch_directory(target_dir)
                elif hasattr(engine, "process_batch"):
                    return engine.process_batch(target_dir)
    
>       raise RuntimeError("No compatible batch scan entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible batch scan entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:286: RuntimeError
_____________________ test_io_fallback_scratch_resolution _____________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_io_fallback_scratch_resol0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000210CF2B3CE0>

    def test_io_fallback_scratch_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify fallback logic prioritizing:
        1. $SCRATCH
        2. $SLURM_TMPDIR
        3. %TEMP% / $TMPDIR
        4. Local artifacts / default scratch
        """
        # Tier 1: $SCRATCH takes highest precedence
        scratch_tier1 = tmp_path / "hpc_scratch_t1"
        scratch_tier1.mkdir()
        monkeypatch.setenv("SCRATCH", str(scratch_tier1))
        monkeypatch.setenv("COCHEM_SCRATCH", str(scratch_tier1))
    
>       resolved_t1 = _invoke_resolve_scratch()
                      ^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:547: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

custom_path = None

    def _invoke_resolve_scratch(custom_path: Optional[Union[str, Path]] = None) -> Path:
        """Dispatches scratch directory resolution."""
        mod = _load_mint_module()
    
        if hasattr(mod, "resolve_io_scratch_directory"):
            return mod.resolve_io_scratch_directory(custom_path)
        elif hasattr(mod, "resolve_scratch_directory"):
            return mod.resolve_scratch_directory(custom_path)
        elif hasattr(mod, "get_scratch_dir"):
            return mod.get_scratch_dir(custom_path)
    
        from cochem_base.config_loader import get_scratch_dir
>       return get_scratch_dir(custom_path)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: get_scratch_dir() takes 0 positional arguments but 1 was given

tests\test_cochem_mint.py:301: TypeError
_____________________________ test_config_binding _____________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_config_binding0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000210CF2DE250>

    def test_config_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify integration with cochem_system_config.json and hardware profile."""
        custom_system_config = {
            "schema_version": "1.0.0",
            "hardware": {
                "physical_cpu_cores": 8,
                "logical_cpu_cores": 16,
                "ram_gb": 64.0,
                "avx512_support": True,
                "gpu_profile": "None",
                "vram_gb": 0.0,
                "subnormal_precision_trap": False,
                "os_target": "windows_x86_64"
            },
            "engines": {
                "orca": {"status": "missing", "path": None, "version": None, "hash": None},
                "mpirun": {"status": "missing", "path": None, "version": None, "hash": None},
                "xtb": {"status": "missing", "path": None, "version": None, "hash": None}
            },
            "silos": {
                "torq_silo_active": True,
                "gpu_silo_active": False
            },
            "hpc": {
                "scheduler": "local",
                "default_partition": "compute",
                "max_walltime_hours": 24
            },
            "active_jobs": {}
        }
    
        config_path = tmp_path / "cochem_system_config.json"
        config_path.write_text(json.dumps(custom_system_config, indent=2), encoding="utf-8")
        monkeypatch.setenv("COCHEM_CONFIG", str(config_path))
    
        mod = _load_mint_module()
        if hasattr(mod, "bind_system_config"):
            bound = mod.bind_system_config(config_path)
            assert bound is not None
        else:
            from cochem_base.config_loader import load_system_config
            cfg = load_system_config(config_path)
>           assert cfg.hardware.physical_cpu_cores == 8
                   ^^^^^^^^^^^^
E           AttributeError: 'dict' object has no attribute 'hardware'

tests\test_cochem_mint.py:612: AttributeError
_____________________ test_pydantic_payload_serialization _____________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_pydantic_payload_serializ0')

    def test_pydantic_payload_serialization(tmp_path: Path) -> None:
        """Verify MolecularGeometryPayload / MolecularGraph serializes and deserializes
        to/from JSON and dictionary cleanly without data loss.
        """
        co2_h2o_file = tmp_path / "co2_h2o.xyz"
        co2_h2o_file.write_text(CO2_H2O_COMPLEX_XYZ, encoding="utf-8")
    
>       payload = _invoke_ingest_file(co2_h2o_file)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:663: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

file_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_pydantic_payload_serializ0/co2_h2o.xyz')

    def _invoke_ingest_file(file_path: Path) -> Any:
        """Dispatches ingestion to the appropriate function in the MInt module."""
        mod = _load_mint_module()
    
        # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
        if hasattr(mod, "ingest_file"):
            return mod.ingest_file(file_path)
        elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
            return mod.ingest_xyz(file_path)
        elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
            return mod.ingest_mol(file_path)
    
        # Priority 2: IngestionEngine / CoChemMInt instance
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls()
                if hasattr(engine, "ingest_file"):
                    return engine.ingest_file(file_path)
                elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                    return engine.parse_xyz(file_path)
    
>       raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible ingestion entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:265: RuntimeError
_______________________ test_co2_h2o_complex_ingestion ________________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_co2_h2o_complex_ingestion0')

    def test_co2_h2o_complex_ingestion(tmp_path: Path) -> None:
        """Verify van der Waals complex CO2...H2O (6 atoms) is ingested with exact
        intermolecular separation R = 2.836 A preserved.
        """
        cpx_file = tmp_path / "co2_h2o_complex.xyz"
        cpx_file.write_text(CO2_H2O_COMPLEX_XYZ, encoding="utf-8")
    
>       payload = _invoke_ingest_file(cpx_file)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:694: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

file_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_co2_h2o_complex_ingestion0/co2_h2o_complex.xyz')

    def _invoke_ingest_file(file_path: Path) -> Any:
        """Dispatches ingestion to the appropriate function in the MInt module."""
        mod = _load_mint_module()
    
        # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
        if hasattr(mod, "ingest_file"):
            return mod.ingest_file(file_path)
        elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
            return mod.ingest_xyz(file_path)
        elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
            return mod.ingest_mol(file_path)
    
        # Priority 2: IngestionEngine / CoChemMInt instance
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls()
                if hasattr(engine, "ingest_file"):
                    return engine.ingest_file(file_path)
                elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                    return engine.parse_xyz(file_path)
    
>       raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible ingestion entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:265: RuntimeError
___________________ test_benzene_planar_geometry_ingestion ____________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_benzene_planar_geometry_i0')

    def test_benzene_planar_geometry_ingestion(tmp_path: Path) -> None:
        """Verify Benzene (12 atoms) planarity (z=0.0) is strictly preserved."""
        bz_file = tmp_path / "benzene.xyz"
        bz_file.write_text(BENZENE_XYZ, encoding="utf-8")
    
>       payload = _invoke_ingest_file(bz_file)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cochem_mint.py:722: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

file_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16672/test_benzene_planar_geometry_i0/benzene.xyz')

    def _invoke_ingest_file(file_path: Path) -> Any:
        """Dispatches ingestion to the appropriate function in the MInt module."""
        mod = _load_mint_module()
    
        # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
        if hasattr(mod, "ingest_file"):
            return mod.ingest_file(file_path)
        elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
            return mod.ingest_xyz(file_path)
        elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
            return mod.ingest_mol(file_path)
    
        # Priority 2: IngestionEngine / CoChemMInt instance
        for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
            if hasattr(mod, cls_name):
                engine_cls = getattr(mod, cls_name)
                engine = engine_cls()
                if hasattr(engine, "ingest_file"):
                    return engine.ingest_file(file_path)
                elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                    return engine.parse_xyz(file_path)
    
>       raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")
E       RuntimeError: No compatible ingestion entrypoint discovered in CoChem-MInt.

tests\test_cochem_mint.py:265: RuntimeError
=========================== short test summary info ===========================
FAILED tests/test_cochem_mint.py::test_single_xyz_ingestion - RuntimeError: N...
FAILED tests/test_cochem_mint.py::test_non_destructive_cartesian_indexing - R...
FAILED tests/test_cochem_mint.py::test_sha256_provenance_and_caching - Runtim...
FAILED tests/test_cochem_mint.py::test_mol_format_ingestion - RuntimeError: N...
FAILED tests/test_cochem_mint.py::test_batch_directory_scanning - RuntimeErro...
FAILED tests/test_cochem_mint.py::test_io_fallback_scratch_resolution - TypeE...
FAILED tests/test_cochem_mint.py::test_config_binding - AttributeError: 'dict...
FAILED tests/test_cochem_mint.py::test_pydantic_payload_serialization - Runti...
FAILED tests/test_cochem_mint.py::test_co2_h2o_complex_ingestion - RuntimeErr...
FAILED tests/test_cochem_mint.py::test_benzene_planar_geometry_ingestion - Ru...
======================= 10 failed, 45 passed in 14.09s ========================

Error: 