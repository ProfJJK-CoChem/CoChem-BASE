Cycle 3: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TORQ\.in-progress\Perfected_Task 10 Multi-Dimensional Physics & JAX Solvers (Stage 5.0).md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, typeguard-4.6.0
collected 39 items

tests\test_antigravity_signin_linux_hpc.py ....                          [ 10%]
tests\test_matrix_dashboard_new_codespaces_actions.py .                  [ 12%]
tests\test_matrix_dashboard_new_codespaces_hpc.py .                      [ 15%]
tests\test_matrix_dashboard_new_codespaces_linux.py .                    [ 17%]
tests\test_matrix_dashboard_new_codespaces_mac.py .                      [ 20%]
tests\test_ui_cell_3_keep_setup_integration.py ..                        [ 25%]
test_suite\test_cochem_jax_builder.py .................                  [ 69%]
test_suite\test_cochem_topos_quench.py ...........F                      [100%]

================================== FAILURES ===================================
________________________ test_airgap_and_file_hygiene _________________________

    def test_airgap_and_file_hygiene() -> None:
        """Verify strict UTF-8 LF encoding, zero BOM, and zero hardcoded path leaks."""
        target_files = [
            Path(TOPOS_REPO_ROOT) / "mechanics" / "cochem_topos_quench.py",
            Path(BASE_REPO_ROOT) / "cochem_base" / "interfaces" / "cochem_topos_quench.py",
            Path(BASE_REPO_ROOT) / "cochem_base" / "mechanics" / "cochem_topos_quench.py",
            Path(__file__).resolve(),
        ]
    
        for p in target_files:
            if not p.exists():
                continue
            raw_bytes = p.read_bytes()
            # Assert Zero BOM
            assert not raw_bytes.startswith(b"\xef\xbb\xbf"), f"BOM detected in {p.name}"
    
            # Assert Unix LF newlines
>           assert b"\r\n" not in raw_bytes, f"CRLF detected in {p.name}; must use Unix LF."
E           AssertionError: CRLF detected in cochem_topos_quench.py; must use Unix LF.
E           assert b'\r\n' not in b'"""\r\nCoChem-TOPOS: Stage 2.1 - Lightning PES Quench Subsystem\r\nImplements CUDAGraphOptimizerWrapper, SoftQuenchG...GeometryRecord directly."""\r\n        return self.quench(structure=record, config=config, geom_id=record.geom_id)\r\n'

test_suite\test_cochem_topos_quench.py:571: AssertionError
=========================== short test summary info ===========================
FAILED test_suite/test_cochem_topos_quench.py::test_airgap_and_file_hygiene
======================== 1 failed, 38 passed in 26.06s ========================

Error: 