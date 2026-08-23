Cycle 3: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TORQ\.in-progress\prompt_task1_dockerfile.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, typeguard-4.6.0
collected 15 items

test_suite\test_cochem_fit_registry_manager.py ....FF                    [ 40%]
test_suite\test_dockerfile.py .........                                  [100%]

================================== FAILURES ===================================
___________________ test_base_hdf5_swmr_and_lustre_fallback ___________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8250/test_base_hdf5_swmr_and_lustre0')

    def test_base_hdf5_swmr_and_lustre_fallback(tmp_path: Path):
        """Verifies SWMR execution on standard FS and snapshot fallback on Lustre."""
        # Standard SWMR
        swmr_db = tmp_path / "swmr_base.h5"
        with open_state_tensor(swmr_db, mode="w", is_lustre=False) as f:
            f.create_dataset("tensor_a", data=np.arange(25))
    
>       with open_state_tensor(swmr_db, mode="r", is_lustre=False) as f:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_suite\test_cochem_fit_registry_manager.py:142: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\contextlib.py:141: in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

db_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8250/test_base_hdf5_swmr_and_lustre0/swmr_base.h5')
mode = 'r', is_lustre = False, timeout = None

    @contextmanager
    def open_state_tensor(
        db_path: Union[str, Path],
        mode: str = "r",
        is_lustre: Optional[bool] = None,
        timeout: Optional[float] = None,
    ) -> Generator[h5py.File, None, None]:
        """
        Context manager opening the HDF5 State Tensor database with filesystem-aware SWMR management.
    
        Behavior:
        1. Standard Local Filesystem:
           - Write Mode ('w', 'a', 'r+'): Opens with libver='latest', activates swmr_mode=True, flushes on exit.
           - Read Mode ('r'): Opens with libver='latest', swmr=True for non-blocking concurrent reading.
        2. HPC / Lustre Filesystem:
           - Disables SWMR (swmr=False) to avoid distributed lock failure / corruption.
           - Write Mode: Opens standard HDF5, writes, flushes dataset buffers, and triggers periodic
             metadata-safe atomic snapshots (shutil.copy2) on exit.
           - Read Mode: Opens standard HDF5 (or latest snapshot) safely with swmr=False.
    
        Args:
            db_path: Path to spectra_fit.h5 database.
            mode: HDF5 open mode ('r', 'r+', 'w', 'a', 'x').
            is_lustre: Optional override for Lustre detection.
            timeout: Optional timeout for atomic lock operations.
    
        Yields:
            h5py.File: Open HDF5 file handle.
    
        Raises:
            HDF5TensorError: If HDF5 initialization or SWMR activation fails.
        """
        p = Path(db_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        lustre_detected = is_lustre if is_lustre is not None else is_lustre_filesystem(p)
    
        h5_file: Optional[h5py.File] = None
        lock: Optional[Union[LustreMkdirLock, StandardFileLock]] = None
    
        try:
            # If write mode, acquire atomic lock
            is_write_mode = mode in ("w", "a", "r+", "x")
            if is_write_mode:
                lock = get_atomic_lock(p, is_lustre=lustre_detected, timeout=timeout)
                lock.acquire()
    
            if lustre_detected:
                # Lustre fallback: SWMR strictly disabled
                logger.debug("[open_state_tensor] Lustre detected. SWMR disabled for %s", p)
                if mode == "r" and not p.is_file():
                    raise FitRegistryMissingError(f"HDF5 database not found at {p}")
    
                try:
                    h5_file = h5py.File(str(p), mode=mode, libver="latest")
                except Exception as e:
                    raise HDF5TensorError(f"Failed to open HDF5 file on Lustre at {p} with mode '{mode}': {e}") from e
    
                yield h5_file
    
                if is_write_mode and h5_file is not None:
                    try:
                        h5_file.flush()
                    except Exception:
                        pass
    
            else:
                # Standard filesystem: SWMR enabled
                logger.debug("[open_state_tensor] Standard filesystem. SWMR active for %s", p)
                if mode == "r":
                    if not p.is_file():
>                       raise FitRegistryMissingError(f"HDF5 database not found at {p}")
E                       src.cochem_spycfit.core_engine.cochem_fit_registry_manager.FitRegistryMissingError: HDF5 database not found at C:\Users\ansac\AppData\Local\Temp\pytest-of-ansac\pytest-8250\test_base_hdf5_swmr_and_lustre0\swmr_base.h5

..\CoChem-SpycFit\src\cochem_spycfit\core_engine\cochem_fit_registry_manager.py:881: FitRegistryMissingError
__________________ test_base_fit_registry_manager_lifecycle ___________________

db_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8250/test_base_fit_registry_manager0/base_spycfit_reg_workspace/spectra_fit.h5')
mode = 'a', is_lustre = False, timeout = 10.0

    @contextmanager
    def open_state_tensor(
        db_path: Union[str, Path],
        mode: str = "r",
        is_lustre: Optional[bool] = None,
        timeout: Optional[float] = None,
    ) -> Generator[h5py.File, None, None]:
        """
        Context manager opening the HDF5 State Tensor database with filesystem-aware SWMR management.
    
        Behavior:
        1. Standard Local Filesystem:
           - Write Mode ('w', 'a', 'r+'): Opens with libver='latest', activates swmr_mode=True, flushes on exit.
           - Read Mode ('r'): Opens with libver='latest', swmr=True for non-blocking concurrent reading.
        2. HPC / Lustre Filesystem:
           - Disables SWMR (swmr=False) to avoid distributed lock failure / corruption.
           - Write Mode: Opens standard HDF5, writes, flushes dataset buffers, and triggers periodic
             metadata-safe atomic snapshots (shutil.copy2) on exit.
           - Read Mode: Opens standard HDF5 (or latest snapshot) safely with swmr=False.
    
        Args:
            db_path: Path to spectra_fit.h5 database.
            mode: HDF5 open mode ('r', 'r+', 'w', 'a', 'x').
            is_lustre: Optional override for Lustre detection.
            timeout: Optional timeout for atomic lock operations.
    
        Yields:
            h5py.File: Open HDF5 file handle.
    
        Raises:
            HDF5TensorError: If HDF5 initialization or SWMR activation fails.
        """
        p = Path(db_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        lustre_detected = is_lustre if is_lustre is not None else is_lustre_filesystem(p)
    
        h5_file: Optional[h5py.File] = None
        lock: Optional[Union[LustreMkdirLock, StandardFileLock]] = None
    
        try:
            # If write mode, acquire atomic lock
            is_write_mode = mode in ("w", "a", "r+", "x")
            if is_write_mode:
                lock = get_atomic_lock(p, is_lustre=lustre_detected, timeout=timeout)
                lock.acquire()
    
            if lustre_detected:
                # Lustre fallback: SWMR strictly disabled
                logger.debug("[open_state_tensor] Lustre detected. SWMR disabled for %s", p)
                if mode == "r" and not p.is_file():
                    raise FitRegistryMissingError(f"HDF5 database not found at {p}")
    
                try:
                    h5_file = h5py.File(str(p), mode=mode, libver="latest")
                except Exception as e:
                    raise HDF5TensorError(f"Failed to open HDF5 file on Lustre at {p} with mode '{mode}': {e}") from e
    
                yield h5_file
    
                if is_write_mode and h5_file is not None:
                    try:
                        h5_file.flush()
                    except Exception:
                        pass
    
            else:
                # Standard filesystem: SWMR enabled
                logger.debug("[open_state_tensor] Standard filesystem. SWMR active for %s", p)
                if mode == "r":
                    if not p.is_file():
                        raise FitRegistryMissingError(f"HDF5 database not found at {p}")
                    try:
                        h5_file = h5py.File(str(p), mode="r", libver="latest", swmr=True)
                    except Exception:
                        # Fallback to standard read if file was not created with SWMR
                        try:
                            h5_file = h5py.File(str(p), mode="r", libver="latest")
                        except Exception as e:
                            raise HDF5TensorError(f"Failed to open HDF5 SWMR file for reading at {p}: {e}") from e
    
                    yield h5_file
    
                else:
                    # Write / Append mode with SWMR
                    try:
>                       h5_file = h5py.File(str(p), mode=mode, libver="latest")
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

..\CoChem-SpycFit\src\cochem_spycfit\core_engine\cochem_fit_registry_manager.py:896: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Users\ansac\anaconda3\Lib\site-packages\h5py\_hl\files.py:566: in __init__
    fid = make_fid(name, mode, userblock_size, fapl, fcpl, swmr=swmr)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\site-packages\h5py\_hl\files.py:253: in make_fid
    fid = h5f.open(name, h5f.ACC_RDWR, fapl=fapl)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
h5py/_objects.pyx:54: in h5py._objects.with_phil.wrapper
    ???
h5py/_objects.pyx:55: in h5py._objects.with_phil.wrapper
    ???
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

>   ???
E   OSError: Unable to synchronously open file (file signature not found)

h5py/h5f.pyx:104: OSError

The above exception was the direct cause of the following exception:

base_test_env = {'db_h5': WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8250/test_base_fit_registry_manager0/b...sers/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8250/test_base_fit_registry_manager0/base_spycfit_reg_workspace')}

    def test_base_fit_registry_manager_lifecycle(base_test_env):
        """Verifies high-level FitRegistryManager transaction, parameter freezing, and tensor I/O."""
        mgr = FitRegistryManager(
            db_path=base_test_env["db_h5"],
            registry_json_path=base_test_env["reg_json"],
            force_lustre=False,
        )
    
        mgr.freeze_parameter("C", value=3200.45)
        state = mgr.get_fit_record()
        assert "C" in state.manual_locks
        assert state.parameters["C"].value == 3200.45
    
        mgr.update_ml_feedback(active=True, loss=0.12, assigned=8, unassigned=2, status="converged")
        state2 = mgr.get_fit_record()
        assert state2.ml_feedback.convergence_status == "converged"
        assert state2.ml_feedback.assigned_transitions_count == 8
    
        # Tensor persistence
        test_arr = np.linspace(0.0, 100.0, 128)
>       mgr.save_spectral_tensor("freq_grid", test_arr, metadata={"unit": "GHz"})

test_suite\test_cochem_fit_registry_manager.py:176: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
..\CoChem-SpycFit\src\cochem_spycfit\core_engine\cochem_fit_registry_manager.py:1275: in save_spectral_tensor
    with self.open_state_tensor(mode="a") as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
C:\Users\ansac\anaconda3\Lib\contextlib.py:141: in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

db_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8250/test_base_fit_registry_manager0/base_spycfit_reg_workspace/spectra_fit.h5')
mode = 'a', is_lustre = False, timeout = 10.0

    @contextmanager
    def open_state_tensor(
        db_path: Union[str, Path],
        mode: str = "r",
        is_lustre: Optional[bool] = None,
        timeout: Optional[float] = None,
    ) -> Generator[h5py.File, None, None]:
        """
        Context manager opening the HDF5 State Tensor database with filesystem-aware SWMR management.
    
        Behavior:
        1. Standard Local Filesystem:
           - Write Mode ('w', 'a', 'r+'): Opens with libver='latest', activates swmr_mode=True, flushes on exit.
           - Read Mode ('r'): Opens with libver='latest', swmr=True for non-blocking concurrent reading.
        2. HPC / Lustre Filesystem:
           - Disables SWMR (swmr=False) to avoid distributed lock failure / corruption.
           - Write Mode: Opens standard HDF5, writes, flushes dataset buffers, and triggers periodic
             metadata-safe atomic snapshots (shutil.copy2) on exit.
           - Read Mode: Opens standard HDF5 (or latest snapshot) safely with swmr=False.
    
        Args:
            db_path: Path to spectra_fit.h5 database.
            mode: HDF5 open mode ('r', 'r+', 'w', 'a', 'x').
            is_lustre: Optional override for Lustre detection.
            timeout: Optional timeout for atomic lock operations.
    
        Yields:
            h5py.File: Open HDF5 file handle.
    
        Raises:
            HDF5TensorError: If HDF5 initialization or SWMR activation fails.
        """
        p = Path(db_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        lustre_detected = is_lustre if is_lustre is not None else is_lustre_filesystem(p)
    
        h5_file: Optional[h5py.File] = None
        lock: Optional[Union[LustreMkdirLock, StandardFileLock]] = None
    
        try:
            # If write mode, acquire atomic lock
            is_write_mode = mode in ("w", "a", "r+", "x")
            if is_write_mode:
                lock = get_atomic_lock(p, is_lustre=lustre_detected, timeout=timeout)
                lock.acquire()
    
            if lustre_detected:
                # Lustre fallback: SWMR strictly disabled
                logger.debug("[open_state_tensor] Lustre detected. SWMR disabled for %s", p)
                if mode == "r" and not p.is_file():
                    raise FitRegistryMissingError(f"HDF5 database not found at {p}")
    
                try:
                    h5_file = h5py.File(str(p), mode=mode, libver="latest")
                except Exception as e:
                    raise HDF5TensorError(f"Failed to open HDF5 file on Lustre at {p} with mode '{mode}': {e}") from e
    
                yield h5_file
    
                if is_write_mode and h5_file is not None:
                    try:
                        h5_file.flush()
                    except Exception:
                        pass
    
            else:
                # Standard filesystem: SWMR enabled
                logger.debug("[open_state_tensor] Standard filesystem. SWMR active for %s", p)
                if mode == "r":
                    if not p.is_file():
                        raise FitRegistryMissingError(f"HDF5 database not found at {p}")
                    try:
                        h5_file = h5py.File(str(p), mode="r", libver="latest", swmr=True)
                    except Exception:
                        # Fallback to standard read if file was not created with SWMR
                        try:
                            h5_file = h5py.File(str(p), mode="r", libver="latest")
                        except Exception as e:
                            raise HDF5TensorError(f"Failed to open HDF5 SWMR file for reading at {p}: {e}") from e
    
                    yield h5_file
    
                else:
                    # Write / Append mode with SWMR
                    try:
                        h5_file = h5py.File(str(p), mode=mode, libver="latest")
                        # Activate SWMR mode if not already in SWMR mode
                        if not getattr(h5_file, "swmr_mode", False):
                            try:
                                h5_file.swmr_mode = True
                            except Exception as swmr_err:
                                logger.debug("[open_state_tensor] Notice on swmr_mode activation: %s", swmr_err)
                    except Exception as e:
>                       raise HDF5TensorError(f"Failed to initialize HDF5 SWMR file at {p} with mode '{mode}': {e}") from e
E                       src.cochem_spycfit.core_engine.cochem_fit_registry_manager.HDF5TensorError: Failed to initialize HDF5 SWMR file at C:\Users\ansac\AppData\Local\Temp\pytest-of-ansac\pytest-8250\test_base_fit_registry_manager0\base_spycfit_reg_workspace\spectra_fit.h5 with mode 'a': Unable to synchronously open file (file signature not found)

..\CoChem-SpycFit\src\cochem_spycfit\core_engine\cochem_fit_registry_manager.py:904: HDF5TensorError
=========================== short test summary info ===========================
FAILED test_suite/test_cochem_fit_registry_manager.py::test_base_hdf5_swmr_and_lustre_fallback
FAILED test_suite/test_cochem_fit_registry_manager.py::test_base_fit_registry_manager_lifecycle
======================== 2 failed, 13 passed in 0.60s =========================

Error: 