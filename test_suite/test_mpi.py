"""MPI and Multi-Core Verification Suite for CoChem.

Provides runtime preflight checks for multi-core ORCA / OpenMPI execution,
as well as a comprehensive pytest suite to validate return contracts,
binary resolution, scratch isolation, error handling, and CLI/module execution.
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

# Ensure repository root is on sys.path for direct execution and isolated test runs
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from cochem_base.config_loader import (
    get_artifact_dir,
    get_scratch_dir,
    prepend_executable_directory,
)

try:
    import psutil
except ImportError:
    psutil = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-TestMPI")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


def cleanup_zombies() -> None:
    """Atexit handler to sweep any orphaned ORCA/MPI processes."""
    if psutil is None:
        return
    try:
        current_proc = psutil.Process()
        children = current_proc.children(recursive=True)
        for child in children:
            try:
                if child.is_running():
                    child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.Error) as e:
                logger.warning(f"Failed to terminate zombie process {child.pid}: {e}")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
        pass


atexit.register(cleanup_zombies)


ORCA_MPI_TEST_INPUT = """! HF STO-3G SP tightscf PAL2
* xyz 0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
*
"""


def run_multi_core_orca_test(
    orca_path: Optional[str] = None,
    mpi_path: Optional[str] = None,
) -> tuple[bool, str]:
    """Runs a simplified <1 second ORCA job using OpenMPI (2 cores).

    Returns:
        tuple[bool, str]: A tuple of (success_status, descriptive_message).
    """
    resolved_orca = orca_path if orca_path is not None else os.environ.get("ORCA_CMD", "orca")
    resolved_mpi = mpi_path if mpi_path is not None else os.environ.get("MPI_CMD")

    if not shutil.which(resolved_orca) and not Path(resolved_orca).is_file():
        return False, f"Error: ORCA binary not found at '{resolved_orca}'. Please check paths."

    if resolved_mpi and not shutil.which(resolved_mpi) and not Path(resolved_mpi).is_file():
        return False, f"Error: MPI binary not found at '{resolved_mpi}'. Please check paths."

    scratch_base = get_scratch_dir()

    execution_env = os.environ.copy()
    if resolved_mpi:
        mpi_executable = Path(resolved_mpi).expanduser()
        if mpi_executable.is_file():
            prepend_executable_directory(execution_env, mpi_executable)
        execution_env["MPI_CMD"] = str(resolved_mpi)

    if resolved_orca:
        orca_executable = Path(resolved_orca).expanduser()
        if orca_executable.is_file():
            prepend_executable_directory(execution_env, orca_executable)

    try:
        with tempfile.TemporaryDirectory(dir=str(scratch_base)) as tmpdir:
            inp_file = Path(tmpdir) / "test_job_mpi.inp"
            try:
                inp_file.write_text(ORCA_MPI_TEST_INPUT, encoding="utf-8")
            except OSError as e:
                return False, f"Error writing input file to scratch directory: {e}"

            cmd: List[str] = [resolved_orca, str(inp_file)]
            start = time.time()

            if safe_subprocess_run is not None:
                result = safe_subprocess_run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    timeout=15.0,
                    check=True,
                    env=execution_env,
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    timeout=15.0,
                    check=True,
                    env=execution_env,
                )

            stdout_text = result.stdout or ""
            end = time.time()

            if "ORCA TERMINATED NORMALLY" in stdout_text:
                return True, f"Success: ORCA multi-core (MPI) test passed in {end - start:.2f}s. [M]"
            else:
                return False, f"Error: ORCA MPI ran but failed to terminate normally. Check OpenMPI setup.\nOutput Snippet:\n{stdout_text[-500:]}"

    except subprocess.TimeoutExpired as e:
        return False, f"Error: ORCA execution timed out after 15.0s: {e}"
    except subprocess.CalledProcessError as e:
        stdout_snippet = e.stdout[-500:] if e.stdout else ""
        stderr_snippet = e.stderr[-500:] if e.stderr else ""
        return False, f"Error: ORCA execution failed with return code {e.returncode}.\nStdout: {stdout_snippet}\nStderr: {stderr_snippet}"
    except OSError as e:
        return False, f"Error: OS Level issue invoking ORCA: {e}"
    finally:
        cleanup_zombies()
        logger.debug("ORCA multi-core (MPI) execution finalized.")


# ==============================================================================
# Pytest Test Cases for MPI & Multi-Core Preflight Verification
# ==============================================================================


def test_run_multi_core_orca_test_return_contract() -> None:
    """Validate that run_multi_core_orca_test returns a (bool, str) tuple with non-empty message."""
    ok, msg = run_multi_core_orca_test()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_run_multi_core_orca_test_missing_orca_binary() -> None:
    """Validate that run_multi_core_orca_test reports missing ORCA binary correctly."""
    non_existent = "non_existent_orca_executable_xyz_987654"
    ok, msg = run_multi_core_orca_test(orca_path=non_existent)
    assert ok is False
    assert f"Error: ORCA binary not found at '{non_existent}'" in msg


def test_run_multi_core_orca_test_missing_mpi_binary() -> None:
    """Validate that run_multi_core_orca_test reports missing MPI binary when provided."""
    # Use existing sys.executable for orca_path so it passes the ORCA existence check
    valid_binary = sys.executable
    non_existent_mpi = "non_existent_mpi_binary_xyz_987654"
    ok, msg = run_multi_core_orca_test(orca_path=valid_binary, mpi_path=non_existent_mpi)
    assert ok is False
    assert f"Error: MPI binary not found at '{non_existent_mpi}'" in msg


def test_orca_mpi_input_content_specification() -> None:
    """Validate quantum chemistry Hamiltonian, basis set, and PAL2 specification in ORCA input."""
    assert "! HF STO-3G SP tightscf PAL2" in ORCA_MPI_TEST_INPUT
    assert "* xyz 0 1" in ORCA_MPI_TEST_INPUT
    assert "H 0.0 0.0 0.74" in ORCA_MPI_TEST_INPUT


def test_run_multi_core_orca_test_scratch_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that multi-core execution executes in an isolated scratch directory without polluting root."""
    custom_scratch = tmp_path / "test_mpi_scratch"
    custom_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_SCRATCH", str(custom_scratch))

    ok, msg = run_multi_core_orca_test()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    # Check that root scratch directory does not retain temporary input files directly
    assert not (custom_scratch / "test_job_mpi.inp").exists()


def test_run_multi_core_orca_test_provenance_tag_on_success() -> None:
    """Validate that a successful multi-core test emits the [M] (Measured) provenance tag per Method Matrix §12.5."""
    ok, msg = run_multi_core_orca_test()
    if ok:
        assert "[M]" in msg
        assert "[E]" not in msg
        assert "Success: ORCA multi-core (MPI) test passed in" in msg


def test_cleanup_zombies_execution() -> None:
    """Validate that cleanup_zombies executes safely without uncaught exceptions."""
    cleanup_zombies()


def test_test_mpi_direct_script_execution() -> None:
    """Validate direct CLI script execution via subprocess."""
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode in (0, 1)
    combined_output = result.stdout + result.stderr
    assert ("ORCA multi-core (MPI) test passed" in combined_output) or ("Error:" in combined_output) or ("Warning:" in combined_output)


def test_test_mpi_module_execution() -> None:
    """Validate module execution via python -m test_suite.test_mpi."""
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [sys.executable, "-m", "test_suite.test_mpi"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode in (0, 1)
    combined_output = result.stdout + result.stderr
    assert ("ORCA multi-core (MPI) test passed" in combined_output) or ("Error:" in combined_output) or ("Warning:" in combined_output)


def test_test_mpi_file_encoding_and_lf() -> None:
    """Validate UTF-8 encoding and strictly LF line endings in test_mpi.py."""
    target_file = Path(__file__).resolve()
    raw_bytes = target_file.read_bytes()
    assert b"\r\n" not in raw_bytes, "CRLF line endings detected in test_mpi.py!"
    content = raw_bytes.decode("utf-8")
    assert "run_multi_core_orca_test" in content
    assert "cleanup_zombies" in content


if __name__ == "__main__":
    success, message = run_multi_core_orca_test()
    if not success:
        logger.error(message)
        sys.exit(1)

    logger.info(message)
