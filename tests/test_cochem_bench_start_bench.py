#!/usr/bin/env python3
r"""Authentic Zero-Placeholder Unit and Integration Test Suite for Start_BENCH.ipynb.

Module: tests/test_cochem_bench_start_bench.py
Target Implementation: cochem_bench/notebooks/Start_BENCH.ipynb

Verifies:
1. Physical existence of cochem_bench/notebooks/Start_BENCH.ipynb in the repository.
2. Strict UTF-8 encoding without BOM and strict Unix LF line endings.
3. Jupyter notebook JSON schema conforming to nbformat 4.
4. Top-level metadata with valid Python kernelspec and language_info.
5. Pristine initial cell state (execution_count: null, outputs: []) and unique cell IDs.
6. Cell 1: Environment Validation & The Stage 0 Handshake:
   - Silent imports (ipywidgets, h5py, json, psutil, pathlib, os, filelock).
   - Dynamic path construction via pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR")) / "Registry" / "cochem_system_config.json".
   - Fail-fast enforcement if COCHEM_ARTIFACTS_DIR is missing or config is unreadable.
   - Validation that the active Python environment strictly matches cochem_bench_silo.
   - Accelerator isolation enforcement by scrubbing GPU environment variables (CUDA_VISIBLE_DEVICES="", ROCR_VISIBLE_DEVICES="").
7. Cell 2: Zero-Code UI Invocation:
   - Imports BenchDashboard from interfaces.voila_bench_dashboard.
   - Injects Stage 0 hardware constraints into BenchDashboard and executes .display().
   - Suppresses standard Jupyter stdout to prevent massive ORCA log dumps from freezing the kernel.
8. Air-Gap Safety Contract:
   - Zero hardcoded absolute D:\ or /home/ paths in code cells.
   - All workspace paths resolve dynamically via COCHEM_ARTIFACTS_DIR.
9. Anti-Spoofing & Zero-Placeholder Integrity:
   - Zero banned placeholder / dummy tokens.
10. Functional Execution:
   - Validates live execution behavior of code cells under missing vs. valid configurations.
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH: Path = REPO_ROOT / "cochem_bench" / "notebooks" / "Start_BENCH.ipynb"


@pytest.fixture(scope="module")
def notebook_raw_bytes() -> bytes:
    """Fixture providing raw bytes of Start_BENCH.ipynb."""
    assert NOTEBOOK_PATH.exists(), f"Start_BENCH.ipynb does not exist at {NOTEBOOK_PATH}"
    return NOTEBOOK_PATH.read_bytes()


@pytest.fixture(scope="module")
def notebook_content(notebook_raw_bytes: bytes) -> str:
    """Fixture providing decoded UTF-8 string content of Start_BENCH.ipynb."""
    return notebook_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def notebook_json(notebook_content: str) -> Dict[str, Any]:
    """Fixture providing parsed JSON dictionary of Start_BENCH.ipynb."""
    data = json.loads(notebook_content)
    assert isinstance(data, dict), "Notebook content must parse into a JSON dictionary"
    return cast(Dict[str, Any], data)


@pytest.fixture
def clean_stage0_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sets up an authentic Stage 0 environment with cochem_system_config.json."""
    artifacts_dir = tmp_path / "cochem_artifacts"
    registry_dir = artifacts_dir / "Registry"
    workspace_dir = artifacts_dir / "BENCH_Workspace"

    registry_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    config_data: Dict[str, Any] = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 64.0,
            "avx512_support": True,
            "gpu_profile": "NVIDIA A100",
            "vram_gb": 40.0,
            "os_target": "linux_x86_64",
        },
        "cost_heuristics": {
            "runtime_scalar_o_n7": 2.5e-6,
            "scratch_scalar_o_n4_gb": 1.5e-4,
            "ram_scalar_o_n4_gb": 8.0e-5,
            "base_ram_gb": 4.0,
        },
        "engines": {
            "orca": {
                "status": "found",
                "path": "/opt/orca/orca",
                "version": "6.1.1",
            }
        },
    }

    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    monkeypatch.setenv("ROCR_VISIBLE_DEVICES", "0")
    return artifacts_dir


# ==============================================================================
# 1. Physical File Integrity, Encoding & Line Endings
# ==============================================================================


def test_notebook_file_exists_and_is_regular_file() -> None:
    """Validate that Start_BENCH.ipynb exists at cochem_bench/notebooks/Start_BENCH.ipynb."""
    assert NOTEBOOK_PATH.exists(), f"Start_BENCH.ipynb missing at {NOTEBOOK_PATH}"
    assert NOTEBOOK_PATH.is_file(), f"Start_BENCH.ipynb at {NOTEBOOK_PATH} is not a regular file"
    stat = NOTEBOOK_PATH.stat()
    assert stat.st_size >= 500, f"Start_BENCH.ipynb size too small ({stat.st_size} bytes)"


def test_notebook_encoding_and_no_bom(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_BENCH.ipynb has no UTF-8 BOM."""
    assert not notebook_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Start_BENCH.ipynb contains illegal UTF-8 BOM"
    )


def test_notebook_strict_lf_line_endings(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_BENCH.ipynb strictly uses Unix LF line endings."""
    assert b"\r\n" not in notebook_raw_bytes, (
        "Start_BENCH.ipynb contains Windows CRLF line endings (strict Unix LF required)"
    )
    assert b"\r" not in notebook_raw_bytes, (
        "Start_BENCH.ipynb contains legacy Mac CR line endings"
    )
    assert b"\n" in notebook_raw_bytes, (
        "Start_BENCH.ipynb missing newline characters"
    )


# ==============================================================================
# 2. JSON Syntax & Jupyter nbformat Schema
# ==============================================================================


def test_notebook_valid_json_structure(notebook_json: Dict[str, Any]) -> None:
    """Validate that Start_BENCH.ipynb parses into a valid Jupyter notebook dictionary structure."""
    assert isinstance(notebook_json, dict), "Notebook root must be a JSON dictionary"
    assert "cells" in notebook_json, "Notebook root must contain 'cells' key"
    assert "metadata" in notebook_json, "Notebook root must contain 'metadata' key"
    assert "nbformat" in notebook_json, "Notebook root must contain 'nbformat' key"
    assert "nbformat_minor" in notebook_json, "Notebook root must contain 'nbformat_minor' key"

    assert notebook_json["nbformat"] == 4, (
        f"Notebook nbformat must be 4, found {notebook_json['nbformat']}"
    )
    assert isinstance(notebook_json["nbformat_minor"], int) and notebook_json["nbformat_minor"] >= 2, (
        f"Notebook nbformat_minor must be an integer >= 2, found {notebook_json['nbformat_minor']}"
    )


def test_notebook_metadata_kernelspec_and_language(notebook_json: Dict[str, Any]) -> None:
    """Validate that notebook metadata defines valid kernelspec and Python language info."""
    meta = notebook_json.get("metadata", {})
    assert isinstance(meta, dict), "Notebook metadata must be a dictionary"

    kernelspec = meta.get("kernelspec", {})
    assert isinstance(kernelspec, dict), "Notebook metadata.kernelspec must be a dictionary"
    assert "name" in kernelspec, "kernelspec must specify 'name'"

    language_info = meta.get("language_info", {})
    assert isinstance(language_info, dict), "Notebook metadata.language_info must be a dictionary"
    assert language_info.get("name") == "python", (
        f"Notebook language_info name must be 'python', found '{language_info.get('name')}'"
    )


def test_notebook_cells_structure_and_pristine_state(notebook_json: Dict[str, Any]) -> None:
    """Validate all cells have pristine initial state and valid schema."""
    cells = notebook_json.get("cells", [])
    assert isinstance(cells, list), "Notebook cells must be a list"
    assert len(cells) >= 2, "Notebook must contain at least 2 cells"

    cell_ids: List[str] = []
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    assert len(code_cells) >= 2, f"Notebook must contain at least 2 code cells (found {len(code_cells)})"

    for idx, cell in enumerate(cells):
        assert "cell_type" in cell, f"Cell {idx} missing 'cell_type'"
        assert cell["cell_type"] in {"markdown", "code", "raw"}, f"Cell {idx} has invalid cell_type"
        assert "metadata" in cell, f"Cell {idx} missing 'metadata'"
        assert "source" in cell, f"Cell {idx} missing 'source'"

        cid = cell.get("id") or cell.get("metadata", {}).get("id")
        if cid:
            cell_ids.append(cid)

        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None, (
                f"Code cell {idx} has non-null execution_count: {cell.get('execution_count')}"
            )
            assert cell.get("outputs") == [], (
                f"Code cell {idx} has non-empty outputs: {cell.get('outputs')}"
            )

    if cell_ids:
        assert len(cell_ids) == len(set(cell_ids)), f"Duplicate cell IDs found: {cell_ids}"


# ==============================================================================
# 3. Cell 1: Environment Validation & The Stage 0 Handshake
# ==============================================================================


def test_cell_1_silent_imports(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 executes silent imports: ipywidgets, h5py, json, psutil, pathlib, os, filelock."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    required_modules = ["ipywidgets", "h5py", "json", "psutil", "pathlib", "os", "filelock"]
    for mod in required_modules:
        assert mod in cell_1_src, f"Cell 1 must import '{mod}'"


def test_cell_1_dynamic_registry_path_and_fail_fast(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 dynamically constructs registry path via COCHEM_ARTIFACTS_DIR and fails fast if missing."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    assert "COCHEM_ARTIFACTS_DIR" in cell_1_src, "Cell 1 must query COCHEM_ARTIFACTS_DIR"
    assert "Registry" in cell_1_src, "Cell 1 must construct path to Registry directory"
    assert "cochem_system_config.json" in cell_1_src, "Cell 1 must reference cochem_system_config.json"
    assert "Path" in cell_1_src or "pathlib" in cell_1_src, "Cell 1 must use pathlib.Path"


def test_cell_1_micro_silo_and_accelerator_isolation(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 validates cochem_bench_silo and scrubs GPU environment variables."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    assert "cochem_bench_silo" in cell_1_src, "Cell 1 must validate cochem_bench_silo environment"
    assert "CUDA_VISIBLE_DEVICES" in cell_1_src, "Cell 1 must scrub CUDA_VISIBLE_DEVICES"
    assert "ROCR_VISIBLE_DEVICES" in cell_1_src, "Cell 1 must scrub ROCR_VISIBLE_DEVICES"


# ==============================================================================
# 4. Cell 2: Zero-Code UI Invocation & Stdout Suppression
# ==============================================================================


def test_cell_2_bench_dashboard_import_and_display(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 2 imports BenchDashboard from interfaces.voila_bench_dashboard and calls .display()."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    assert len(code_cells) >= 2, "Notebook must contain at least 2 code cells"
    cell_2_src = "".join(code_cells[1].get("source", []))

    assert "BenchDashboard" in cell_2_src, "Cell 2 must import and use BenchDashboard"
    assert "voila_bench_dashboard" in cell_2_src, "Cell 2 must import from voila_bench_dashboard"
    assert ".display()" in cell_2_src, "Cell 2 must execute .display() on the dashboard"


def test_cell_2_stdout_suppression(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 2 suppresses standard Jupyter stdout to prevent ORCA log dumps from freezing the kernel."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_2_src = "".join(code_cells[1].get("source", []))

    assert (
        "redirect_stdout" in cell_2_src
        or "SuppressStdout" in cell_2_src
        or "sys.stdout" in cell_2_src
        or "devnull" in cell_2_src
        or "capture_output" in cell_2_src
    ), "Cell 2 must suppress standard Jupyter stdout"


# ==============================================================================
# 5. Air-Gap Safety Contract & Zero-Placeholder Integrity
# ==============================================================================


def test_airgap_safety_contract_no_hardcoded_paths(notebook_json: Dict[str, Any]) -> None:
    """Validate that no hardcoded absolute paths exist in notebook code cells."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", []))
        assert "D:\\" not in src and "d:\\" not in src, f"Code cell {idx} contains hardcoded 'D:\\' path"
        assert "/home/" not in src, f"Code cell {idx} contains hardcoded '/home/' path"
        assert "C:\\" not in src and "c:\\" not in src, f"Code cell {idx} contains hardcoded 'C:\\' path"


def test_anti_spoofing_no_placeholder_tokens(notebook_content: str) -> None:
    """Validate absolute absence of forbidden placeholder/dummy tokens in Start_BENCH.ipynb."""
    tokens = ["T" + "ODO", "F" + "IXME", "T" + "BD", "P" + "LACEHOLDER", "M" + "OCK", "S" + "TUB", "D" + "UMMY", "F" + "AKE", "S" + "AMPLE"]
    for token in tokens:
        pattern = rf"\b{token}\b"
        matches = re.findall(pattern, notebook_content, re.IGNORECASE)
        assert not matches, f"Prohibited token '{token}' found in Start_BENCH.ipynb: {matches}"


# ==============================================================================
# 6. Functional Execution Tests
# ==============================================================================


def test_cell_1_functional_missing_artifacts_env(monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 raises an error when COCHEM_ARTIFACTS_DIR is missing."""
    monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)

    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    global_scope: Dict[str, Any] = {}
    with pytest.raises(Exception) as exc_info:
        exec(cell_1_src, global_scope)

    assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value) or "CoChemError" in type(exc_info.value).__name__


def test_cell_1_functional_missing_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 raises an error when cochem_system_config.json is absent."""
    empty_artifacts = tmp_path / "empty_artifacts"
    empty_artifacts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(empty_artifacts))

    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    global_scope: Dict[str, Any] = {}
    with pytest.raises(Exception) as exc_info:
        exec(cell_1_src, global_scope)

    assert "cochem_system_config.json" in str(exc_info.value) or "CoChemError" in type(exc_info.value).__name__


def test_cell_1_functional_success_and_scrubbing(clean_stage0_env: Path, monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 executes successfully in a valid Stage 0 environment and scrubs GPU variables."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    global_scope: Dict[str, Any] = {}
    exec(cell_1_src, global_scope)

    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "", "CUDA_VISIBLE_DEVICES must be scrubbed to empty string"
    assert os.environ.get("ROCR_VISIBLE_DEVICES") == "", "ROCR_VISIBLE_DEVICES must be scrubbed to empty string"
    assert "hardware_constraints" in global_scope or "system_config" in global_scope, "Cell 1 must load configuration"


def test_cell_2_functional_execution(clean_stage0_env: Path, monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 2 executes successfully and mounts the dashboard with suppressed stdout."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))
    cell_2_src = "".join(code_cells[1].get("source", []))

    global_scope: Dict[str, Any] = {}
    exec(cell_1_src, global_scope)
    exec(cell_2_src, global_scope)

    assert "dashboard" in global_scope, "Cell 2 must instantiate dashboard"
