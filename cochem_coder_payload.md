Cycle 2: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc6_01_workspace_manager_prompt.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0
collected 30 items

test_suite\test_cochem_core_workspace_manager.py ..........EEEE......... [ 76%]
.......                                                                  [100%]

=================================== ERRORS ====================================
______ ERROR at setup of test_parsl_dag_workspace_scaffolding_core_tree _______

    @pytest.fixture
    def parsl_session() -> Generator[Any, None, None]:
        """Pytest fixture providing an initialized Parsl ThreadPoolExecutor environment.
    
        Ensures safe teardown and resource deallocation between test runs.
        """
>       import parsl
E       ModuleNotFoundError: No module named 'parsl'

test_suite\test_cochem_core_workspace_manager.py:69: ModuleNotFoundError
___ ERROR at setup of test_parsl_dag_workspace_scaffolding_additional_dirs ____

    @pytest.fixture
    def parsl_session() -> Generator[Any, None, None]:
        """Pytest fixture providing an initialized Parsl ThreadPoolExecutor environment.
    
        Ensures safe teardown and resource deallocation between test runs.
        """
>       import parsl
E       ModuleNotFoundError: No module named 'parsl'

test_suite\test_cochem_core_workspace_manager.py:69: ModuleNotFoundError
__________ ERROR at setup of test_parsl_dag_task_dependency_chaining __________

    @pytest.fixture
    def parsl_session() -> Generator[Any, None, None]:
        """Pytest fixture providing an initialized Parsl ThreadPoolExecutor environment.
    
        Ensures safe teardown and resource deallocation between test runs.
        """
>       import parsl
E       ModuleNotFoundError: No module named 'parsl'

test_suite\test_cochem_core_workspace_manager.py:69: ModuleNotFoundError
______ ERROR at setup of test_workspace_manager_scaffold_workspace_parsl ______

    @pytest.fixture
    def parsl_session() -> Generator[Any, None, None]:
        """Pytest fixture providing an initialized Parsl ThreadPoolExecutor environment.
    
        Ensures safe teardown and resource deallocation between test runs.
        """
>       import parsl
E       ModuleNotFoundError: No module named 'parsl'

test_suite\test_cochem_core_workspace_manager.py:69: ModuleNotFoundError
=========================== short test summary info ===========================
ERROR test_suite/test_cochem_core_workspace_manager.py::test_parsl_dag_workspace_scaffolding_core_tree
ERROR test_suite/test_cochem_core_workspace_manager.py::test_parsl_dag_workspace_scaffolding_additional_dirs
ERROR test_suite/test_cochem_core_workspace_manager.py::test_parsl_dag_task_dependency_chaining
ERROR test_suite/test_cochem_core_workspace_manager.py::test_workspace_manager_scaffold_workspace_parsl
======================== 26 passed, 4 errors in 0.90s =========================

Error: 