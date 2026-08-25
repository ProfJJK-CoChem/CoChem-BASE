Cycle 3: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-GEOM\.in-progress\Task_19_data_geom_parser_py.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, hydra-core-1.3.5, typeguard-4.6.0, zarr-3.3.0
collected 274 items

test_suite\test_cochem_core_hdf5_manager.py ........s....s.......        [  7%]
test_suite\test_cochem_core_registry_manager.py ........................ [ 16%]
....s...                                                                 [ 19%]
test_suite\test_cochem_setup_phase_1.py ...........................sss.. [ 31%]
.........                                                                [ 34%]
test_suite\test_cochem_setup_phase_11.py sssssssssssssssssssssssssssssss [ 45%]
sssssssssssss                                                            [ 50%]
test_suite\test_cochem_setup_phase_5.py ssssssssssssssssssssssssssssssss [ 62%]
sssssssssssssssssssssss                                                  [ 70%]
test_suite\test_cochem_setup_phase_6.py .....................s..         [ 79%]
tests\test_cochem_core_registry_manager.py ......................s.      [ 87%]
tests\test_cochem_mint.py .....F.....                                    [ 91%]
tests\test_geom_parser.py ......................                         [100%]

================================== FAILURES ===================================
_____________________ test_io_fallback_scratch_resolution _____________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-10699/test_io_fallback_scratch_resol0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000247D6E59950>

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
    
        resolved_t1 = _invoke_resolve_scratch()
        assert resolved_t1.resolve() == scratch_tier1.resolve()
    
        # Tier 2: When $SCRATCH is absent, we skip SLURM_TMPDIR test here unless present physically
        monkeypatch.delenv("SCRATCH", raising=False)
        monkeypatch.delenv("COCHEM_SCRATCH", raising=False)
>       if os.environ.get("SLURM_TMPDIR"):
           ^^
E       NameError: name 'os' is not defined. Did you forget to import 'os'?

tests\test_cochem_mint.py:552: NameError
============================== warnings summary ===============================
C:\Users\ansac\anaconda3\Lib\site-packages\torch\jit\_script.py:1488
C:\Users\ansac\anaconda3\Lib\site-packages\torch\jit\_script.py:1488
  C:\Users\ansac\anaconda3\Lib\site-packages\torch\jit\_script.py:1488: DeprecationWarning: `torch.jit.script` is deprecated. Please switch to `torch.compile` or `torch.export`.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_cochem_mint.py::test_io_fallback_scratch_resolution - NameE...
=========== 1 failed, 166 passed, 107 skipped, 2 warnings in 30.38s ===========

Error: 