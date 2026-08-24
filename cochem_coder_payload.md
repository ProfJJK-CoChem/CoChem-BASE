Cycle 2: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_test_cochem_scribe_master.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, typeguard-4.6.0, zarr-3.3.0
collected 30 items / 1 error

=================================== ERRORS ====================================
_____________ ERROR collecting core/test_cochem_scribe_master.py ______________
import file mismatch:
imported module 'test_cochem_scribe_master' has this __file__ attribute:
  D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_scribe_master.py
which is not the same as the test file we want to collect:
  D:\__CoChem\GitHub-Repo\CoChem-BASE\core\test_cochem_scribe_master.py
HINT: remove __pycache__ / .pyc files and/or use a unique basename for your test file modules
=========================== short test summary info ===========================
ERROR core/test_cochem_scribe_master.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 1.43s ===============================

Error: 