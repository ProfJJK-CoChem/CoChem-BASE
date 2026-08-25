Cycle 2: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\10_scribe_citation_api.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, hydra-core-1.3.5, typeguard-4.6.0, zarr-3.3.0
collected 12 items / 17 errors

=================================== ERRORS ====================================
__________ ERROR collecting test_suite/test_cochem_setup_phase_11.py __________
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_setup_phase_11.py", line 393
E       scheduler, mem_bytes = detect_hpc_memory_limits()
E   IndentationError: unexpected indent
__________ ERROR collecting test_suite/test_cochem_setup_phase_5.py ___________
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_setup_phase_5.py", line 794
E       assert "998877" in res.name
E   IndentationError: unexpected indent
____ ERROR collecting test_suite/test_cochem_unity_installer_dashboard.py _____
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_unity_installer_dashboard.py", line 223
E       assert gui.interact_target is not None
E   IndentationError: unexpected indent
______________ ERROR collecting test_suite/test_headless_run.py _______________
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_headless_run.py", line 82
E       iface, calc = headless_run.get_interface_and_calc_env()
E       ^^^^^
E   IndentationError: expected an indented block after function definition on line 81
_______ ERROR collecting tests/test_cochem_unity_installer_dashboard.py _______
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_unity_installer_dashboard.py", line 275
E       assert gui.interact_target is not None
E   IndentationError: unexpected indent
___ ERROR collecting tests/test_matrix_dashboard_keep_codespaces_actions.py ___
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_keep_codespaces_actions.py", line 56
E       return codespaces_scratch
E   IndentationError: unexpected indent
_____ ERROR collecting tests/test_matrix_dashboard_keep_codespaces_hpc.py _____
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_keep_codespaces_hpc.py", line 57
E       return codespaces_scratch
E   IndentationError: unexpected indent
____ ERROR collecting tests/test_matrix_dashboard_keep_codespaces_linux.py ____
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_keep_codespaces_linux.py", line 56
E       return codespaces_scratch
E   IndentationError: unexpected indent
_____ ERROR collecting tests/test_matrix_dashboard_keep_codespaces_mac.py _____
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_keep_codespaces_mac.py", line 59
E       bin_dir = codespaces_scratch / "bin"
E   IndentationError: unexpected indent
_____ ERROR collecting tests/test_matrix_dashboard_keep_codespaces_wsl.py _____
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_keep_codespaces_wsl.py", line 56
E       return codespaces_scratch
E   IndentationError: unexpected indent
_______ ERROR collecting tests/test_matrix_dashboard_keep_linux_hpc.py ________
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_keep_linux_hpc.py", line 58
E       return hpc_scratch
E   IndentationError: unexpected indent
___ ERROR collecting tests/test_matrix_dashboard_new_codespaces_actions.py ____
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_new_codespaces_actions.py", line 58
E       return cs_actions_scratch
E   IndentationError: unexpected indent
_____ ERROR collecting tests/test_matrix_dashboard_new_codespaces_hpc.py ______
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_new_codespaces_hpc.py", line 31
E       monkeypatch.setenv("COCHEM_CALCULATION_OS", "hpc")
E       ^^^^^^^^^^^
E   IndentationError: expected an indented block after function definition on line 30
____ ERROR collecting tests/test_matrix_dashboard_new_codespaces_linux.py _____
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_new_codespaces_linux.py", line 32
E       artifact_dir = tmp_path / "CoChem_Artifacts"
E   IndentationError: unexpected indent
_____ ERROR collecting tests/test_matrix_dashboard_new_codespaces_mac.py ______
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_new_codespaces_mac.py", line 50
E       return cs_mac_scratch
E   IndentationError: unexpected indent
_____ ERROR collecting tests/test_matrix_dashboard_new_codespaces_wsl.py ______
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_new_codespaces_wsl.py", line 73
E       return cs_wsl_scratch
E   IndentationError: unexpected indent
________ ERROR collecting tests/test_matrix_dashboard_new_linux_hpc.py ________
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\python.py:498: in importtestmodule
    mod = import_path(
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\pathlib.py:587: in import_path
    importlib.import_module(module_name)
C:\Users\ansac\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<frozen importlib._bootstrap>:1387: in _gcd_import
    ???
<frozen importlib._bootstrap>:1360: in _find_and_load
    ???
<frozen importlib._bootstrap>:1331: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:935: in _load_unlocked
    ???
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:177: in exec_module
    source_stat, co = _rewrite_test(fn, self.config)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\_pytest\assertion\rewrite.py:357: in _rewrite_test
    tree = ast.parse(source, filename=strfn)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\ast.py:50: in parse
    return compile(source, filename, mode, flags,
E     File "D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_matrix_dashboard_new_linux_hpc.py", line 69
E       return hpc_scratch
E   IndentationError: unexpected indent
=========================== short test summary info ===========================
ERROR test_suite/test_cochem_setup_phase_11.py
ERROR test_suite/test_cochem_setup_phase_5.py
ERROR test_suite/test_cochem_unity_installer_dashboard.py
ERROR test_suite/test_headless_run.py
ERROR tests/test_cochem_unity_installer_dashboard.py
ERROR tests/test_matrix_dashboard_keep_codespaces_actions.py
ERROR tests/test_matrix_dashboard_keep_codespaces_hpc.py
ERROR tests/test_matrix_dashboard_keep_codespaces_linux.py
ERROR tests/test_matrix_dashboard_keep_codespaces_mac.py
ERROR tests/test_matrix_dashboard_keep_codespaces_wsl.py
ERROR tests/test_matrix_dashboard_keep_linux_hpc.py
ERROR tests/test_matrix_dashboard_new_codespaces_actions.py
ERROR tests/test_matrix_dashboard_new_codespaces_hpc.py
ERROR tests/test_matrix_dashboard_new_codespaces_linux.py
ERROR tests/test_matrix_dashboard_new_codespaces_mac.py
ERROR tests/test_matrix_dashboard_new_codespaces_wsl.py
ERROR tests/test_matrix_dashboard_new_linux_hpc.py
!!!!!!!!!!!!!!!!!! Interrupted: 17 errors during collection !!!!!!!!!!!!!!!!!!!
============================= 17 errors in 1.84s ==============================

Error: 