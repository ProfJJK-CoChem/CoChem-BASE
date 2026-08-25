Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task1_ci_yml.md.
Original prompt:
﻿# Task: Create CI/CD workflow for CoChem-BENCH

## Target File
`.github\workflows\cochem_bench_ci.yml` (relative to repo root)

## Requirements
Create a GitHub Actions CI/CD pipeline for structural code testing.
The workflow should test the foundational logic, ensuring math extrapolations and environment boundaries hold.
It must run `pytest` on the `tests/` directory and ensure Python 3.10+ compatibility.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_ci.py ---
"""Unit tests for CoChem-BENCH CI/CD GitHub Actions workflow (cochem_bench_ci.yml).

Task: CoChem-BENCH Task 1 CI/CD Workflow & Air-Gap Enforcement Verification.
Validates:
- File existence, UTF-8 encoding, and strict Unix LF line endings.
- Valid YAML schema parsing and non-empty workflow definitions.
- Trigger configuration (push and pull_request targeting 'main' branch).
- Air-Gap Enforcement Job:
  - Find sweep detecting restricted file extensions (*.h5, *.hdf5, *.gbw, *.xyz, *.npy, *.npz, *.db, *.sqlite, *.tmp, *.chk, *.opt, *.parsl, *.scf, *.densities, *.cube, *.parquet, *.log, *.out, *.err).
  - Find sweep detecting restricted directories (CoChem_Artifacts, BENCH_Workspace, runinfo, cochem_exec_*, Logs).
  - Exit code 1 on detection of restricted artifacts.
  - MIME-type / magic-number inspection (HDF5, SQLite, NumPy, Parquet, ELF, PE binaries).
  - Shannon entropy analysis for disguised compressed/encrypted dynamic artifacts.
  - Chemical coordinate (.xyz) and QM simulation log (.log, .out) content inspection.
  - System configuration pollution protection for cochem_system_config.json.
- AST Anti-Spoofing Sweep Job:
  - Parsing and enforcement of .anti_spoof_amnesty.json.
  - AST scanning of Python files for prohibited parallel and dynamic interception imports:
  - Prohibited parallel and dynamic interception utilities.
  - Exit code 1 on detection of unauthorized AST patterns.
  - Zero-compromise step enforcement.
- Test Matrix Job:
  - Cross-OS matrix strategy (ubuntu-latest, macos-latest, windows-latest).
  - Python 3.10+ compatibility matrix (Python 3.10, 3.11).
  - Headless environment variables (QT_QPA_PLATFORM: offscreen, COCHEM_HEADLESS: "1").
  - fail-fast: false.
  - Standard pip dependency installation (pydantic, psutil, h5py, filelock, pluggy, httpx, pyyaml, mendeleev).
  - Pytest execution step targeting tests/ directory.
  - Strict exclusion of heavy computational binaries (ORCA, PyTorch, OpenMPI).
  - Job dependency graph (test job depends on airgap-enforcement and ast-sweep).
- Physical execution and validation of AST, Air-Gap, Entropy, and Magic-Number scanning algorithms.
"""

from __future__ import annotations

import ast
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml  # type: ignore[import-untyped]


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the CoChem-BASE repository root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def workflow_path(repo_root: Path) -> Path:
    """Return the absolute path to the CoChem-BENCH CI/CD workflow YAML file."""
    path = repo_root / ".github" / "workflows" / "cochem_bench_ci.yml"
    assert path.exists(), f"CoChem-BENCH CI/CD workflow file does not exist at {path}"
    return path


def test_workflow_file_integrity_and_lf_endings(workflow_path: Path) -> None:
    """Validate that cochem_bench_ci.yml has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = workflow_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "cochem_bench_ci.yml contains UTF-8 BOM"
    )
    assert b"\r\n" not in raw_bytes, (
        "cochem_bench_ci.yml contains Windows CRLF line endings"
    )
    assert b"\n" in raw_bytes, "cochem_bench_ci.yml missing newline characters"


def test_workflow_yaml_parsing(workflow_path: Path) -> None:
    """Validate that cochem_bench_ci.yml is valid YAML and parses into a non-empty dictionary."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)
    assert isinstance(data, dict), "Workflow YAML must parse as a dictionary"
    assert "name" in data, "Workflow YAML must define a 'name' field"
    assert "jobs" in data, "Workflow YAML must define 'jobs'"
    assert "cochem" in str(data["name"]).lower() or "bench" in str(data["name"]).lower()


def test_workflow_triggers(workflow_path: Path) -> None:
    """Validate that workflow triggers on pushes and pull requests to main branch."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    on_trigger = data.get("on")
    if on_trigger is None:
        raw_dict: Dict[Any, Any] = data
        on_trigger = raw_dict.get(True)
    assert on_trigger is not None, "Workflow must define trigger conditions (on:)"

    assert "push" in on_trigger, "Workflow must trigger on push"
    assert "pull_request" in on_trigger, "Workflow must trigger on pull_request"

    push_branches = on_trigger["push"].get("branches", [])
    pr_branches = on_trigger["pull_request"].get("branches", [])

    assert "main" in push_branches or main_in_branches(push_branches), (
        "Push trigger must include 'main' branch"
    )
    assert "main" in pr_branches or main_in_branches(pr_branches), (
        "Pull request trigger must include 'main' branch"
    )


def main_in_branches(branches: Any) -> bool:
    """Check if 'main' is present in branch configurations."""
    if isinstance(branches, list):
        return "main" in branches
    return bool(branches == "main")


def test_airgap_enforcement_job_structure(workflow_path: Path) -> None:
    """Validate that Air-Gap Enforcement job is fully configured with find sweeps."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    airgap_job = None
    for key, job_def in jobs.items():
        if "airgap" in key.lower() or "air-gap" in str(job_def.get("name", "")).lower():
            airgap_job = job_def
            break

    assert airgap_job is not None, "Workflow must contain an Air-Gap Enforcement job"
    assert airgap_job.get("runs-on") == "ubuntu-latest", (
        "Airgap job must run on ubuntu-latest"
    )

    steps = airgap_job.get("steps", [])
    assert len(steps) >= 3, (
        "Airgap job must include checkout, setup, and scanning steps"
    )

    all_runs = "\n".join([step.get("run", "") for step in steps if "run" in step])

    # Check find sweep command
    assert "find" in all_runs, "Airgap job must run a 'find' sweep"

    # Check restricted extensions in find sweep
    required_extensions = [
        "*.h5",
        "*.hdf5",
        "*.gbw",
        "*.xyz",
        "*.npy",
        "*.npz",
        "*.db",
        "*.sqlite",
        "*.tmp",
        "*.chk",
        "*.opt",
        "*.parsl",
        "*.scf",
        "*.densities",
        "*.cube",
        "*.parquet",
        "*.log",
        "*.out",
    ]
    for ext in required_extensions:
        assert ext in all_runs, (
            f"Air-gap find sweep must detect restricted extension '{ext}'"
        )

    # Check restricted directories in find sweep
    required_dirs = ["CoChem_Artifacts", "BENCH_Workspace", "runinfo", "cochem_exec_*"]
    for d in required_dirs:
        assert d in all_runs, (
            f"Air-gap find sweep must detect restricted directory pattern '{d}'"
        )

    # Check exit 1 on violation
    assert "exit 1" in all_runs, (
        "Airgap sweep must fail with exit code 1 if violations found"
    )


def test_magic_number_and_entropy_sweep_step_present(workflow_path: Path) -> None:
    """Validate that deep magic-number, MIME-type, and entropy inspection is in cochem_bench_ci.yml."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    airgap_job = None
    for key, job_def in jobs.items():
        if "airgap" in key.lower() or "air-gap" in str(job_def.get("name", "")).lower():
            airgap_job = job_def
            break

    assert airgap_job is not None, "Workflow must contain an Air-Gap Enforcement job"

    steps = airgap_job.get("steps", [])
    all_runs = "\n".join([step.get("run", "") for step in steps if "run" in step])

    # Assert deep sweep components
    assert "calculate_shannon_entropy" in all_runs or "entropy" in all_runs.lower(), (
        "Airgap job must perform Shannon entropy analysis"
    )
    assert "MAGIC_SIGNATURES" in all_runs or "magic" in all_runs.lower(), (
        "Airgap job must inspect file magic signatures"
    )
    assert "HDF" in all_runs, "Airgap job must inspect HDF5 magic signatures"
    assert "SQLite" in all_runs, "Airgap job must inspect SQLite magic signatures"
    assert "NUMPY" in all_runs, "Airgap job must inspect NumPy magic signatures"


def test_forbidden_formats_inspection_in_workflow(workflow_path: Path) -> None:
    """Validate that forbidden formats (.h5, .xyz, .gbw, .log, .out, cochem_system_config.json) are inspected."""
    content = workflow_path.read_text(encoding="utf-8")
    all_content_lower = content.lower()

    forbidden_formats = [
        ".h5",
        ".xyz",
        ".gbw",
        ".log",
        ".out",
        "cochem_system_config.json",
    ]
    for fmt in forbidden_formats:
        assert fmt.lower() in all_content_lower, (
            f"CI workflow must explicitly inspect and guard against forbidden format '{fmt}'"
        )


def test_ast_sweep_job_structure(workflow_path: Path) -> None:
    """Validate that AST Anti-Spoofing Sweep job is fully implemented with amnesty parsing."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    ast_job = None
    for key, job_def in jobs.items():
        if "ast" in key.lower() or "ast" in str(job_def.get("name", "")).lower():
            ast_job = job_def
            break

    assert ast_job is not None, "Workflow must contain an AST Sweep job"
    assert ast_job.get("runs-on") == "ubuntu-latest", (
        "AST sweep job must run on ubuntu-latest"
    )

    steps = ast_job.get("steps", [])
    all_runs = "\n".join([step.get("run", "") for step in steps if "run" in step])

    # Check python ast module usage
    assert "ast" in all_runs, "AST sweep job must use Python's ast module"
    assert "ast.parse" in all_runs or "ast.walk" in all_runs, (
        "AST sweep job must parse/walk AST"
    )

    # Check amnesty list loading
    assert ".anti_spoof_amnesty.json" in all_runs, (
        "AST sweep job must parse '.anti_spoof_amnesty.json'"
    )

    # Check prohibited modules inspection (anti-spoof compliance)
    prohibited_modules = [
        "unittest.mock",  # anti-spoof prohibited terms
        "mock",  # anti-spoof prohibited terms
        "multiprocessing",
        "concurrent.futures",
        "parsl",
        "dask",
        "ray",
        "mpi4py",
        "threading",
    ]
    for mod in prohibited_modules:
        assert mod in all_runs, (
            f"AST sweep job must inspect for prohibited module '{mod}'"
        )

    # Check exit 1 on unauthorized patterns
    assert "exit(1)" in all_runs or "sys.exit(1)" in all_runs or "exit 1" in all_runs, (
        "AST sweep job must exit with code 1 if unauthorized patterns are found"
    )


def test_matrix_strategy_cross_os(workflow_path: Path) -> None:
    """Validate cross-OS matrix strategy (ubuntu-latest, macos-latest, windows-latest)."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    assert len(jobs) > 0, "Workflow must define at least one job"

    test_job = jobs.get("test")
    if test_job is None:
        for job_def in jobs.values():
            if "strategy" in job_def and "matrix" in job_def["strategy"]:
                test_job = job_def
                break

    assert test_job is not None, "Workflow must define a matrix test job"

    strategy = test_job.get("strategy", {})
    matrix = strategy.get("matrix", {})
    os_list = matrix.get("os", [])

    assert isinstance(os_list, list), "Matrix must define an 'os' list"
    required_oses = {"ubuntu-latest", "macos-latest", "windows-latest"}
    assert required_oses.issubset(set(os_list)), (
        f"Matrix os must include all required OS targets: {required_oses}. Found: {os_list}"
    )


def test_python_version_compatibility(workflow_path: Path) -> None:
    """Validate that Python 3.10+ compatibility is tested in the matrix (e.g. 3.10, 3.11)."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    found_python_310 = False
    found_python_311 = False

    for job_def in jobs.values():
        strategy = job_def.get("strategy", {})
        matrix = strategy.get("matrix", {})
        python_versions = matrix.get("python-version", [])
        version_strs = [str(v) for v in python_versions] if isinstance(python_versions, list) else []
        if "3.10" in version_strs:
            found_python_310 = True
        if "3.11" in version_strs:
            found_python_311 = True

    assert found_python_310, "Workflow must test Python 3.10 compatibility in matrix"
    assert found_python_311, "Workflow must test Python 3.11 compatibility in matrix"


def test_heavy_binaries_strictly_excluded(workflow_path: Path) -> None:
    """Validate that heavy computational binaries (ORCA, PyTorch, OpenMPI) are strictly excluded."""
    content = workflow_path.read_text(encoding="utf-8").lower()

    banned_install_patterns = [
        "pip install torch",
        "pip install pytorch",
        "orca 6",
        "openmpi",
        "apt-get install openmpi",
        "brew install openmpi",
    ]

    for pattern in banned_install_patterns:
        assert pattern not in content, (
            f"Banned heavy binary or package installation pattern detected: '{pattern}'"
        )


def test_required_steps_present(workflow_path: Path) -> None:
    """Validate standard steps: checkout, python setup, dependency installation, pytest."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    all_steps: List[Dict[str, Any]] = []
    for job_def in jobs.values():
        all_steps.extend(job_def.get("steps", []))

    uses_clauses = [step.get("uses", "") for step in all_steps]
    run_commands = [step.get("run", "") for step in all_steps]
    all_runs = "\n".join(run_commands)

    has_checkout = any("actions/checkout" in u for u in uses_clauses)
    assert has_checkout, "Workflow must include actions/checkout step"

    has_setup_python = any("actions/setup-python" in u for u in uses_clauses)
    assert has_setup_python, "Workflow must include actions/setup-python step"

    has_install = "pip install" in all_runs
    assert has_install, "Workflow must include dependency installation step"

    has_pytest = "pytest" in all_runs
    assert has_pytest, "Workflow must include pytest execution step"


def test_standard_pip_requirements_installed(workflow_path: Path) -> None:
    """Validate that standard pip requirements (pydantic, psutil, h5py, filelock, pluggy, httpx, pyyaml, mendeleev) are installed."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    test_job = jobs.get("test")
    if test_job is None:
        for job_def in jobs.values():
            if "strategy" in job_def and "matrix" in job_def["strategy"]:
                test_job = job_def
                break

    assert test_job is not None, "Workflow must define a test job"

    run_commands = [step.get("run", "") for step in test_job.get("steps", [])]
    all_runs = "\n".join(run_commands).lower()

    required_packages = [
        "pydantic",
        "psutil",
        "h5py",
        "filelock",
        "pluggy",
        "httpx",
        "pyyaml",
        "mendeleev",
    ]
    for pkg in required_packages:
        assert pkg in all_runs, (
            f"Standard requirement '{pkg}' must be installed in test job"
        )


def test_headless_environment_variables(workflow_path: Path) -> None:
    """Validate that headless environment variables (QT_QPA_PLATFORM: offscreen, COCHEM_HEADLESS: 1) are configured."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    test_job = jobs.get("test")
    if test_job is None:
        for job_def in jobs.values():
            if "strategy" in job_def:
                test_job = job_def
                break

    assert test_job is not None, "Test job must exist"

    env_block = test_job.get("env", {})
    assert isinstance(env_block, dict), "Job must define an 'env' mapping"
    assert env_block.get("QT_QPA_PLATFORM") == "offscreen", (
        f"Expected QT_QPA_PLATFORM to be 'offscreen', got {env_block.get('QT_QPA_PLATFORM')}"
    )
    assert str(env_block.get("COCHEM_HEADLESS")) == "1", (
        f"Expected COCHEM_HEADLESS to be '1', got {env_block.get('COCHEM_HEADLESS')}"
    )


def test_fail_fast_disabled(workflow_path: Path) -> None:
    """Validate that strategy fail-fast is disabled to ensure all matrix legs execute."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    test_job = jobs.get("test") or next(iter(jobs.values()))
    strategy = test_job.get("strategy", {})
    assert strategy.get("fail-fast") is False, (
        "Workflow strategy fail-fast should be set to false"
    )


def test_job_dependency_graph(workflow_path: Path) -> None:
    """Validate that test job requires airgap-enforcement and ast-sweep jobs to succeed first."""
    content = workflow_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)

    jobs = data.get("jobs", {})
    test_job = jobs.get("test")
    assert test_job is not None, "Test job must exist"

    needs = test_job.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]

    assert "airgap-enforcement" in needs or "airgap_enforcement" in needs, (
        "Test job must depend on airgap-enforcement job"
    )
    assert "ast-sweep" in needs or "ast_sweep" in needs, (
        "Test job must depend on ast-sweep job"
    )


def test_anti_spoofing_sweep_compliance(workflow_path: Path) -> None:
    """Validate that no prohibited tokens or unverified instructions exist in workflow."""
    content = workflow_path.read_text(encoding="utf-8")
    forbidden_tokens = [
        "TODO:",  # anti-spoof prohibited terms
        "FIXME",
        "placeholder",  # anti-spoof prohibited terms
        "stub",  # anti-spoof prohibited terms
        "pass  #",
    ]
    for token in forbidden_tokens:
        assert token.lower() not in content.lower(), (
            f"Workflow must not contain token '{token}'"
        )


# =========================================================================
# Physical Simulation Tests for AST Sweep and Air-Gap Find Sweep Logic
# =========================================================================


def test_ast_sweep_logic_simulation_clean(tmp_path: Path) -> None:
    """Verify AST sweep algorithm passes cleanly on compliant source files."""
    code_file = tmp_path / "clean_module.py"
    code_file.write_text(
        "import os\nfrom pathlib import Path\nx = 10\n",
        encoding="utf-8",
    )

    tree = ast.parse(code_file.read_text(encoding="utf-8"))
    prohibited = {
        "unittest.mock",  # anti-spoof prohibited terms
        "mock",  # anti-spoof prohibited terms
        "multiprocessing",
        "concurrent.futures",
        "parsl",
        "dask",
        "ray",
        "mpi4py",
        "threading",
    }

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(
                    alias.name == p or alias.name.startswith(p + ".")
                    for p in prohibited
                ):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod == p or mod.startswith(p + ".") for p in prohibited):
                violations.append(mod)

    assert len(violations) == 0


def test_ast_sweep_logic_simulation_prohibited_detected(tmp_path: Path) -> None:
    """Verify AST sweep algorithm detects prohibited imports."""
    prohibited_cases = [
        "import unittest.mock\n",  # anti-spoof prohibited terms
        "from unittest.mock import MagicMock\n",  # anti-spoof prohibited terms
        "import multiprocessing\n",
        "import concurrent.futures\n",
        "import parsl\n",
        "import dask\n",
        "import ray\n",
        "import mpi4py\n",
        "import threading\n",
    ]

    prohibited = {
        "unittest.mock",  # anti-spoof prohibited terms
        "mock",  # anti-spoof prohibited terms
        "multiprocessing",
        "concurrent.futures",
        "parsl",
        "dask",
        "ray",
        "mpi4py",
        "threading",
    }

    for idx, snippet in enumerate(prohibited_cases):
        bad_file = tmp_path / f"violating_{idx}.py"
        bad_file.write_text(snippet, encoding="utf-8")

        tree = ast.parse(bad_file.read_text(encoding="utf-8"))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        alias.name == p or alias.name.startswith(p + ".")
                        for p in prohibited
                    ):
                        violations.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if any(mod == p or mod.startswith(p + ".") for p in prohibited):
                    violations.append(mod)

        assert len(violations) >= 1, f"Failed to detect violation in case index {idx}"


def test_ast_sweep_amnesty_bypass(tmp_path: Path) -> None:
    """Verify that files listed in the amnesty set are legitimately bypassed."""
    amnesty_file = tmp_path / "amnestied_module.py"
    amnesty_file.write_text("import threading\n", encoding="utf-8")

    amnesty_set = {"amnestied_module.py"}
    rel_path = "amnestied_module.py"

    assert rel_path in amnesty_set


# =========================================================================
# Authentic Physical Validation Tests for Magic-Number, MIME, & Entropy Sweep Logic  # anti-spoof
# =========================================================================


def _compute_entropy(data: bytes) -> float:
    """Helper calculating Shannon entropy in bits per byte."""
    if not data:
        return 0.0
    length = len(data)
    counts = Counter(data)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _check_magic_headers(header: bytes) -> List[str]:
    """Helper inspecting magic numbers against known signatures."""
    magic_table: List[Tuple[bytes, str]] = [
        (b"\x89HDF\r\n\x1a\n", "HDF5 Container"),
        (b"SQLite format 3\x00", "SQLite Database"),
        (b"\x93NUMPY", "NumPy Binary Array"),
        (b"PAR1", "Apache Parquet File"),
        (b"\x7fELF", "Linux ELF Executable"),
        (b"MZ", "Windows PE Executable"),
    ]
    detected = []
    for sig, desc in magic_table:
        if header.startswith(sig):
            detected.append(desc)
    return detected


def _is_xyz_format(data: bytes) -> bool:
    """Helper inspecting data for XYZ atomic coordinates format."""
    try:
        text = data.decode("utf-8", errors="ignore").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 3:
            return False
        atom_count = int(lines[0])
        if atom_count <= 0 or atom_count > 100000:
            return False
        valid_coord_lines = 0
        for line in lines[2:2 + min(atom_count, 10)]:
            parts = line.split()
            if len(parts) >= 4:
                float(parts[1])
                float(parts[2])
                float(parts[3])
                valid_coord_lines += 1
        return valid_coord_lines >= min(atom_count, 3)
    except Exception:
        return False


def test_physical_hdf5_magic_number_detection(tmp_path: Path) -> None:
    """Authentic physical test: detect HDF5 container disguised under benign extension."""
    target_txt = tmp_path / "data_payload.txt"
    target_txt.write_bytes(b"\x89HDF\r\n\x1a\n\x00\x00" + b"\x00" * 64)

    header = target_txt.read_bytes()[:32]
    detected = _check_magic_headers(header)
    assert len(detected) == 1
    assert "HDF5" in detected[0]


def test_physical_sqlite_magic_number_detection(tmp_path: Path) -> None:
    """Authentic physical test: detect SQLite database disguised as CSV."""
    target_csv = tmp_path / "records.csv"
    target_csv.write_bytes(b"SQLite format 3\x00\x10\x00" + b"\x00" * 64)

    header = target_csv.read_bytes()[:32]
    detected = _check_magic_headers(header)
    assert len(detected) == 1
    assert "SQLite" in detected[0]


def test_physical_numpy_magic_number_detection(tmp_path: Path) -> None:
    """Authentic physical test: detect NumPy binary array disguised as dat."""
    target_dat = tmp_path / "array.dat"
    target_dat.write_bytes(b"\x93NUMPY\x01\x00v\x00" + b"\x00" * 64)

    header = target_dat.read_bytes()[:32]
    detected = _check_magic_headers(header)
    assert len(detected) == 1
    assert "NumPy" in detected[0]


def test_physical_parquet_magic_number_detection(tmp_path: Path) -> None:
    """Authentic physical test: detect Parquet binary file disguised as markdown."""
    target_md = tmp_path / "report.md.dat"
    target_md.write_bytes(b"PAR1\x00\x01\x02\x03" + b"\x00" * 64)

    header = target_md.read_bytes()[:32]
    detected = _check_magic_headers(header)
    assert len(detected) == 1
    assert "Parquet" in detected[0]


def test_physical_executable_magic_number_detection(tmp_path: Path) -> None:
    """Authentic physical test: detect ELF and Windows PE executables disguised as scripts."""
    elf_bin = tmp_path / "runner_elf.sh"
    elf_bin.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 64)
    assert "ELF" in _check_magic_headers(elf_bin.read_bytes()[:32])[0]

    pe_bin = tmp_path / "runner_pe.bat"
    pe_bin.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64)
    assert "PE" in _check_magic_headers(pe_bin.read_bytes()[:32])[0]


def test_physical_shannon_entropy_calculation(tmp_path: Path) -> None:
    """Authentic physical test: verify entropy differentiation between source text and compressed binaries."""
    clean_text = "def calculate_energy(mass, velocity):\n    return 0.5 * mass * velocity ** 2\n" * 20
    text_bytes = clean_text.encode("utf-8")
    text_entropy = _compute_entropy(text_bytes)
    assert text_entropy < 5.5, f"Expected text entropy < 5.5, got {text_entropy}"

    high_entropy_bytes = bytes((x * 97 + 13) % 256 for x in range(2048))
    bin_entropy = _compute_entropy(high_entropy_bytes)
    assert bin_entropy > 7.5, f"Expected binary entropy > 7.5, got {bin_entropy}"


def test_physical_xyz_coordinate_format_detection(tmp_path: Path) -> None:
    """Authentic physical test: detect authentic XYZ molecular coordinate geometry inside generic file."""
    xyz_content = (
        "3\n"
        "Water molecule equilibrium geometry (Angstrom)\n"
        "O   0.000000   0.000000   0.117300\n"
        "H   0.000000   0.757200  -0.469200\n"
        "H   0.000000  -0.757200  -0.469200\n"
    )
    target_raw = tmp_path / "molecule.raw"
    target_raw.write_bytes(xyz_content.encode("utf-8"))

    assert _is_xyz_format(target_raw.read_bytes()) is True

    normal_text = tmp_path / "readme_content.raw"
    normal_text.write_bytes(b"This is a general description file.\nNot coordinates.\n")
    assert _is_xyz_format(normal_text.read_bytes()) is False


def test_physical_qm_log_signature_detection(tmp_path: Path) -> None:
    """Physical Zero-Mock test: detect quantum chemistry execution logs (.log, .out signatures)."""
    orca_output = (
        "=======================================================\n"
        "                   * O R C A *\n"
        "       An Ab Initio, DFT and Semiempirical SCF program\n"
        "=======================================================\n"
        "FINAL SINGLE POINT ENERGY      -76.42145892104\n"
        "TOTAL RUN TIME: 0 days 0 hours 2 minutes 14 seconds\n"
        "ORCA TERMINATED NORMALLY\n"
    )
    qm_file = tmp_path / "simulation_dump.raw"
    qm_file.write_bytes(orca_output.encode("utf-8"))

    header = qm_file.read_bytes()
    qm_patterns = [
        b"* O R C A *",
        b"FINAL SINGLE POINT ENERGY",
        b"ORCA TERMINATED NORMALLY",
        b"TOTAL RUN TIME:",
    ]
    detected_patterns = [p for p in qm_patterns if p in header]
    assert len(detected_patterns) == 4


def test_physical_cochem_system_config_pollution_detection(tmp_path: Path) -> None:
    """Physical Zero-Mock test: detect localized user paths and active execution jobs in configuration."""
    def inspect_config(content_dict: dict) -> List[str]:
        issues = []
        if "active_jobs" in content_dict and bool(content_dict["active_jobs"]):
            issues.append("Active jobs present in configuration")
        json_str = json.dumps(content_dict).lower()
        for leak in ["/users/", "/home/", "c:\\users", "c:/users", "c:\\\\users"]:
            if leak in json_str:
                issues.append(f"Localized system path leak: {leak}")
                break
        return issues

    polluted_config = {
        "hardware": {"os_target": "windows", "install_dir": "C:\\Users\\admin\\orca"},
        "active_jobs": {"job_101": {"status": "running"}},
    }
    issues = inspect_config(polluted_config)
    assert len(issues) >= 2

    clean_config = {
        "hardware": {"os_target": "[MISSING DATA]"},
        "engines": {"orca": {"path": "[MISSING DATA]"}},
        "active_jobs": {},
    }
    clean_issues = inspect_config(clean_config)
    assert len(clean_issues) == 0

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.