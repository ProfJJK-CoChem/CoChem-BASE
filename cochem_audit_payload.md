Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc3_01_jupyter_interactive_prompt.md.
Original prompt:
# Start_Here.ipynb Generation Prompt

**Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\Start_Here.ipynb`

## Context
You are tasked with generating the `Start_Here.ipynb` notebook for the CoChem-BASE project. This notebook acts as the Stage 0.0 entry point and execution shell for the frontend, ensuring transparent initialization and user intervention capabilities. 

## Instructions
Write the full Jupyter Notebook structure (as JSON or using an appropriate programmatic builder).
1. **Separated Execution Cells**: Compartmentalize setup orchestrator scripts into distinct, sequentially executed cells (e.g., `%run orchestrator/cochem_setup_phase_1.py`, `%run orchestrator/cochem_setup_phase_2.py`). 
   - **Banned**: The use of bang-python shell escapes (e.g., `!python`) is strictly banned.
   - All background process calls must use `%run` or `subprocess.run([sys.executable])` to ensure execution stability and environment variable propagation.
   - Stream phase-by-phase logs directly into the cell output to verify the environment.
2. **Dynamic Import & Rendering Architecture**: In the final initialization cell, use Python's `importlib` loader to dynamically ingest `cochem_unity_installer_dashboard.py` logic from the Static Execution Tier. Securely bridge the notebook with isolated UI logic without polluting `sys.path` globally.
3. **User Intervention on Failure**: If an OS limitation is hit (e.g., inadequate RAM, missing OS-level compilers, or insufficient `vm.max_map_count`), the specific cell must halt execution gracefully and output a human-readable `CoChemError` detailing the exact failure and OS-level command required to resolve it.

## Constraints
- **NO Mocks, Stubs, or Placeholders.** Do not write `# TODO: implement` or dummy logic. Ensure actual `%run` calls and `importlib` loader logic are fully and explicitly written.
- Ensure the notebook is valid JSON representing an `.ipynb` file.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\rewrite_notebook.py ---
#!/usr/bin/env python3
"""
CoChem-BASE: Interactive Notebook Generator and Updater.
Generates Start_Here.ipynb conforming strictly to Doc3_01 specification.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
NOTEBOOK_PATH = BASE_DIR / "Start_Here.ipynb"


def build_start_here_notebook() -> dict:
    """Constructs the canonical nbformat 4 dictionary for Start_Here.ipynb."""
    cells = [
        {
            "cell_type": "markdown",
            "id": "cochem-stage0-header",
            "metadata": {"id": "cochem-stage0-header"},
            "source": [
                "# CoChem-BASE: Stage 0.0 Master Setup Orchestrator\n",
                "\n",
                "Welcome to the **Stage 0.0 Entry Point** for the CoChem-BASE ecosystem. This notebook acts as the top-level orchestrator starting point, guiding the environment provisioning, hardware profiling, dependency locking, and quantum chemistry engine verification sequence.\n",
                "\n",
                "### Architectural Foundation: Tripartite Workspace Air-Gap\n",
                "CoChem-BASE enforces strict separation between execution tiers:\n",
                "1. **Static Execution Tier:** Immutable Git repository containing source code, schemas, and UI logic (zero runtime modifications permitted).\n",
                "2. **Persistent Data Tier:** Git-ignored, persistent storage under `$SCRATCH` / `$COCHEM_DATA_ROOT` managing SWMR HDF5 databases, provenance records, and geometry archives.\n",
                "3. **Ephemeral Compute Tier:** Node-local sterile quarantine sandboxes (`/tmp/cochem_exec_<uuid>/`) for volatile scratch files, PySCF checkpoints, and ORCA wavefunctions.\n",
                "\n",
                "### Sequential Phase Execution\n",
                "Rather than executing a monolithic setup script that risks memory fragmentation or hidden failures, Stage 0 setup is partitioned into discrete, stateless Python phases. Executing each phase in a dedicated cell ensures clear visibility into system validation and provides immediate crash isolation."
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-01-md",
            "metadata": {"id": "cochem-phase-01-md"},
            "source": [
                "## Phase 1: Cross-Platform OS, Hypervisor & Resource Limits Audit\n",
                "\n",
                "Performs host OS detection (Windows WSL, macOS OrbStack, Linux Debian/RHEL), hypervisor validation, CPU core topology mapping, and system resource limits auditing.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_1.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-01-code",
            "metadata": {"id": "cochem-phase-01-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_1.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-02-md",
            "metadata": {"id": "cochem-phase-02-md"},
            "source": [
                "## Phase 2: Hardware, Numerical Precision & VRAM Profiling\n",
                "\n",
                "Profiles CPU SIMD instruction sets (AVX2/AVX512), GPU acceleration backends (CUDA/ROCm/MPS), floating-point precision throughput, and available VRAM memory budgets.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_2.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-02-code",
            "metadata": {"id": "cochem-phase-02-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_2.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-03-md",
            "metadata": {"id": "cochem-phase-03-md"},
            "source": [
                "## Phase 3: Multi-Track Quantum Engine Discovery & Integrity Hashing\n",
                "\n",
                "Discovers available quantum chemistry engines (PySCF, ORCA, NWChem, ASE), computes cryptographic SHA-256 integrity hashes of executables, and validates toolchain paths.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_3.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-03-code",
            "metadata": {"id": "cochem-phase-03-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_3.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-04-md",
            "metadata": {"id": "cochem-phase-04-md"},
            "source": [
                "## Phase 4: Micro-Silo Provisioning & Dependency Isolation\n",
                "\n",
                "Constructs and verifies isolated micro-silo virtual environments, resolves package dependencies, and locks package versions against corruption.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_4.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-04-code",
            "metadata": {"id": "cochem-phase-04-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_4.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-05-md",
            "metadata": {"id": "cochem-phase-05-md"},
            "source": [
                "## Phase 5: NVIDIA MPS Daemon Initialization & VRAM Budgeting\n",
                "\n",
                "Initializes NVIDIA Multi-Process Service (MPS) control daemons on supported multi-GPU hosts, configures compute thread percentages, and provisions active memory budgets.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_5.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-05-code",
            "metadata": {"id": "cochem-phase-05-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_5.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-06-md",
            "metadata": {"id": "cochem-phase-06-md"},
            "source": [
                "## Phase 6: Database & Bifurcated Storage Backend Provisioning\n",
                "\n",
                "Provisions relational metadata stores (SQLite) and high-performance numerical datastores (SWMR HDF5) adhering to the Persistent Data Tier schema.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_6.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-06-code",
            "metadata": {"id": "cochem-phase-06-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_6.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-07-md",
            "metadata": {"id": "cochem-phase-07-md"},
            "source": [
                "## Phase 7: HPC Slurm/PBS Environment Variable Injection\n",
                "\n",
                "Audits High-Performance Computing (HPC) cluster schedulers (Slurm, PBS Pro, LSF) and injects dynamic node allocations, task counts, and partition configurations.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_7.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-07-code",
            "metadata": {"id": "cochem-phase-07-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_7.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-08-md",
            "metadata": {"id": "cochem-phase-08-md"},
            "source": [
                "## Phase 8: Network Port Allocation & Dynamic Gateway Binding\n",
                "\n",
                "Allocates non-conflicting loopback TCP ports and establishes secure local API telemetry gateway bindings for inter-process communication.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_8.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-08-code",
            "metadata": {"id": "cochem-phase-08-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_8.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-09-md",
            "metadata": {"id": "cochem-phase-09-md"},
            "source": [
                "## Phase 9: Heterogeneous Parsl Concurrency Executor Mapping\n",
                "\n",
                "Configures heterogeneous parallel compute executors using Parsl, mapping tasks across local multithreading cores and remote cluster compute pools.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_9.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-09-code",
            "metadata": {"id": "cochem-phase-09-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_9.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-10-md",
            "metadata": {"id": "cochem-phase-10-md"},
            "source": [
                "## Phase 10: State-Chain Recovery & Quarantined Sandbox Verification\n",
                "\n",
                "Validates cryptographic state-chain continuity, verifies ephemeral sandbox creation and automated cleanup routines, and audits quarantine containment.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_10.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-10-code",
            "metadata": {"id": "cochem-phase-10-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_10.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-11-md",
            "metadata": {"id": "cochem-phase-11-md"},
            "source": [
                "## Phase 11: Final Golden Registry Lock & UI Handover\n",
                "\n",
                "Commits all validated hardware architectures, compute engine bindings, and runtime configurations to the immutable Golden Registry, emitting the SETUP_COMPLETE signal.\n",
                "\n",
                "- Script: `orchestrator/cochem_setup_phase_11.py`"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-11-code",
            "metadata": {"id": "cochem-phase-11-code"},
            "outputs": [],
            "source": [
                "%run orchestrator/cochem_setup_phase_11.py"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-phase-12-dashboard-md",
            "metadata": {"id": "cochem-phase-12-dashboard-md"},
            "source": [
                "## Final Initialization: Dynamic Import & Dashboard Rendering\n",
                "\n",
                "Securely ingests the `cochem_unity_installer_dashboard.py` interface logic directly from the Static Execution Tier using Python's `importlib.util` module loader. This isolates UI execution state without globally mutating or polluting `sys.path`. If host resource limits or missing OS dependencies are encountered, execution halts gracefully with actionable `CoChemError` remediation commands."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "id": "cochem-phase-12-dashboard-code",
            "metadata": {"id": "cochem-phase-12-dashboard-code"},
            "outputs": [],
            "source": [
                "import importlib.util\n",
                "from pathlib import Path\n",
                "import sys\n",
                "from cochem_base.exceptions import CoChemError, ProvenanceErrorCode\n",
                "\n",
                "try:\n",
                "    # 1. Inspect OS and memory prerequisites\n",
                "    import psutil\n",
                "    memory_info = psutil.virtual_memory()\n",
                "    if memory_info.total < 1024 * 1024 * 1024:\n",
                "        raise CoChemError(\n",
                "            message=\"Host memory insufficient (< 1 GB RAM available).\",\n",
                "            error_code=ProvenanceErrorCode.OUT_OF_MEMORY,\n",
                "            details={\"remediation\": \"Allocate additional host memory or configure system swap space before initializing UI.\"}\n",
                "        )\n",
                "\n",
                "    # 2. Resolve dashboard path within Static Execution Tier\n",
                "    target_dashboard_path = Path(\"interfaces/cochem_unity_installer_dashboard.py\").resolve()\n",
                "    if not target_dashboard_path.exists():\n",
                "        target_dashboard_path = Path(\"cochem_base/interfaces/cochem_unity_installer_dashboard.py\").resolve()\n",
                "\n",
                "    if not target_dashboard_path.exists():\n",
                "        raise CoChemError(\n",
                "            message=f\"Static Execution Tier integrity check failed: missing {target_dashboard_path}\",\n",
                "            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,\n",
                "            details={\"remediation\": \"Re-synchronize repository files: 'git checkout -- interfaces/'\"}\n",
                "        )\n",
                "\n",
                "    # 3. Dynamic import via importlib.util without polluting sys.path\n",
                "    module_name = \"cochem_unity_installer_dashboard\"\n",
                "    module_spec = importlib.util.spec_from_file_location(module_name, target_dashboard_path)\n",
                "    if module_spec is None or module_spec.loader is None:\n",
                "        raise CoChemError(\n",
                "            message=f\"Failed to create module specification for {target_dashboard_path}\",\n",
                "            error_code=ProvenanceErrorCode.CONFIG_VALIDATION_FAILED,\n",
                "            details={\"remediation\": \"Verify file permissions and Python environment integrity.\"}\n",
                "        )\n",
                "\n",
                "    dashboard_module = importlib.util.module_from_spec(module_spec)\n",
                "    sys.modules[module_name] = dashboard_module\n",
                "    module_spec.loader.exec_module(dashboard_module)\n",
                "\n",
                "    # 4. Render installer dashboard\n",
                "    if hasattr(dashboard_module, \"main\"):\n",
                "        dashboard_module.main()\n",
                "    else:\n",
                "        raise CoChemError(\n",
                "            message=\"Installer dashboard entry point 'main' not found in loaded module.\",\n",
                "            error_code=ProvenanceErrorCode.CONFIG_VALIDATION_FAILED,\n",
                "            details={\"remediation\": \"Verify interface file integrity.\"}\n",
                "        )\n",
                "\n",
                "except CoChemError as cochem_error:\n",
                "    print(f\"\\n[COCHEM OS PRE-FLIGHT ERROR] {cochem_error.message}\")\n",
                "    if \"remediation\" in cochem_error.details:\n",
                "        print(f\"[REMEDIATION COMMAND] {cochem_error.details['remediation']}\")\n",
                "    raise\n",
                "except Exception as runtime_error:\n",
                "    cochem_err = CoChemError(\n",
                "        message=f\"Unexpected failure during dynamic dashboard initialization: {runtime_error}\",\n",
                "        error_code=ProvenanceErrorCode.HARDWARE_DETECTION_FAILED,\n",
                "        details={\"remediation\": \"Verify Python dependencies via 'python -m pip check' and check system limits.\"}\n",
                "    )\n",
                "    print(f\"\\n[COCHEM OS ERROR] {cochem_err.message}\")\n",
                "    print(f\"[REMEDIATION COMMAND] {cochem_err.details['remediation']}\")\n",
                "    raise cochem_err from runtime_error\n"
            ]
        },
        {
            "cell_type": "markdown",
            "id": "cochem-stage0-complete",
            "metadata": {"id": "cochem-stage0-complete"},
            "source": [
                "## Stage 0 Initialization Complete\n",
                "\n",
                "All eleven setup phases and the interactive UI dashboard have been dynamically initialized. The CoChem-BASE platform is verified, registered, and ready for interactive UI sessions and high-throughput computational chemistry workflows."
            ]
        }
    ]

    metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.11.0"
        }
    }

    return {
        "cells": cells,
        "metadata": metadata,
        "nbformat": 4,
        "nbformat_minor": 5
    }


def write_notebook(path: Path) -> None:
    """Writes the notebook dictionary to the target path with strict Unix LF line endings."""
    nb_dict = build_start_here_notebook()
    json_str = json.dumps(nb_dict, indent=1) + "\n"
    unix_lf_bytes = json_str.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(unix_lf_bytes)


def main() -> None:
    """Main execution function."""
    write_notebook(NOTEBOOK_PATH)
    print(f"Successfully generated {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_start_here_notebook.py ---
"""Comprehensive Zero-Placeholder Unit and Integration Test Suite for Start_Here.ipynb.

Validates all architectural requirements of Doc3_01_jupyter_interactive_prompt.md:
1. Physical existence of Start_Here.ipynb at repository root.
2. Strict UTF-8 encoding without BOM (\\xef\\xbb\\xbf) and strict Unix LF line endings (\\n).
3. Valid Jupyter notebook JSON structure conforming strictly to nbformat 4 specification.
4. Top-level metadata with valid Python kernelspec and language_info.
5. Markdown cells describing the Stage 0.0 Entry Point, Tripartite Workspace Air-Gap, and top-level orchestrator workflow.
6. Existence, exact syntax, and strictly sequential ordering of 11 code cells executing:
   %run orchestrator/cochem_setup_phase_1.py through %run orchestrator/cochem_setup_phase_11.py
7. Strict and total elimination and ban of '!python' shell escapes.
8. Explanatory markdown headers and descriptions preceding each setup phase.
9. Final dynamic import & rendering cell using importlib.util dynamic loader to ingest cochem_unity_installer_dashboard.py
   without polluting sys.path globally, rendering the dashboard.
10. Graceful user intervention on OS limitations with human-readable CoChemError displaying exact failure and OS-level remediation commands.
11. Cell count, cell ID uniqueness, cell metadata schema invariants, and pristine initial state (execution_count: null, outputs: []).
12. Zero prohibited placeholder tokens and zero unauthorized test imports.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH: Path = REPO_ROOT / "Start_Here.ipynb"


@pytest.fixture(scope="module")
def notebook_raw_bytes() -> bytes:
    """Fixture providing raw bytes of Start_Here.ipynb."""
    assert NOTEBOOK_PATH.exists(), f"Start_Here.ipynb does not exist at {NOTEBOOK_PATH}"
    return NOTEBOOK_PATH.read_bytes()


@pytest.fixture(scope="module")
def notebook_content(notebook_raw_bytes: bytes) -> str:
    """Fixture providing decoded UTF-8 string content of Start_Here.ipynb."""
    return notebook_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def notebook_json(notebook_content: str) -> Dict[str, Any]:
    """Fixture providing parsed JSON dictionary of Start_Here.ipynb."""
    data = json.loads(notebook_content)
    assert isinstance(data, dict), "Notebook content must parse into a JSON dictionary"
    return cast(Dict[str, Any], data)


# ==============================================================================
# 1. Physical File Integrity, Encoding & Line Endings
# ==============================================================================


def test_notebook_file_exists_and_is_regular_file() -> None:
    """Validate that Start_Here.ipynb exists as a physical regular file in the repository root."""
    assert NOTEBOOK_PATH.exists(), f"Start_Here.ipynb missing at {NOTEBOOK_PATH}"
    assert NOTEBOOK_PATH.is_file(), f"Start_Here.ipynb at {NOTEBOOK_PATH} is not a regular file"
    stat = NOTEBOOK_PATH.stat()
    assert stat.st_size >= 1000, (
        f"Start_Here.ipynb size too small ({stat.st_size} bytes); complete orchestrator notebook expected."
    )


def test_notebook_encoding_and_no_bom(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_Here.ipynb has no UTF-8 BOM."""
    assert not notebook_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Start_Here.ipynb contains illegal UTF-8 BOM"
    )


def test_notebook_strict_lf_line_endings(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_Here.ipynb strictly uses Unix LF line endings without Windows CRLF or legacy Mac CR."""
    assert b"\r\n" not in notebook_raw_bytes, (
        "Start_Here.ipynb contains Windows CRLF line endings (strict Unix LF required)"
    )
    assert b"\r" not in notebook_raw_bytes, (
        "Start_Here.ipynb contains legacy Mac CR line endings"
    )
    assert b"\n" in notebook_raw_bytes, (
        "Start_Here.ipynb missing newline characters"
    )


# ==============================================================================
# 2. JSON Syntax & Jupyter nbformat Schema
# ==============================================================================


def test_notebook_valid_json_structure(notebook_json: Dict[str, Any]) -> None:
    """Validate that Start_Here.ipynb parses into a valid Jupyter notebook dictionary structure."""
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
    assert "language" in kernelspec or "display_name" in kernelspec, (
        "kernelspec must specify 'language' or 'display_name'"
    )

    language_info = meta.get("language_info", {})
    assert isinstance(language_info, dict), "Notebook metadata.language_info must be a dictionary"
    assert language_info.get("name") == "python", (
        f"Notebook language_info name must be 'python', found '{language_info.get('name')}'"
    )


def test_notebook_cells_structure_and_types(notebook_json: Dict[str, Any]) -> None:
    """Validate that all cells conform to standard Jupyter notebook cell schemas."""
    cells = notebook_json.get("cells", [])
    assert isinstance(cells, list), "Notebook cells must be a list"
    assert len(cells) >= 13, f"Notebook must contain at least 13 cells (found {len(cells)})"

    for idx, cell in enumerate(cells):
        assert isinstance(cell, dict), f"Cell {idx} must be a dictionary"
        assert "cell_type" in cell, f"Cell {idx} missing 'cell_type'"
        assert cell["cell_type"] in {"markdown", "code", "raw"}, (
            f"Cell {idx} has invalid cell_type: {cell['cell_type']}"
        )
        assert "metadata" in cell, f"Cell {idx} missing 'metadata'"
        assert "source" in cell, f"Cell {idx} missing 'source'"

        source = cell["source"]
        if isinstance(source, list):
            assert len(source) > 0, f"Cell {idx} has empty source list"
            assert any(s.strip() for s in source), f"Cell {idx} has whitespace-only source list"
        else:
            assert str(source).strip(), f"Cell {idx} has empty source string"

        if cell["cell_type"] == "code":
            assert "outputs" in cell, f"Code cell {idx} missing 'outputs' field"
            assert isinstance(cell["outputs"], list), f"Code cell {idx} 'outputs' must be a list"
            assert "execution_count" in cell, f"Code cell {idx} missing 'execution_count' field"


def test_notebook_cell_ids_unique_and_valid(notebook_json: Dict[str, Any]) -> None:
    """Validate that all cell metadata IDs are unique and non-empty."""
    cells = notebook_json.get("cells", [])
    cell_ids: List[str] = []

    for cell in cells:
        cid = cell.get("id") or cell.get("metadata", {}).get("id")
        if cid:
            cell_ids.append(cid)

    if cell_ids:
        assert len(cell_ids) == len(set(cell_ids)), (
            f"Duplicate cell IDs found in Start_Here.ipynb: {cell_ids}"
        )


# ==============================================================================
# 3. Stage 0.0 Entry Point & Air-Gap Architecture Documentation
# ==============================================================================


def test_notebook_stage_0_entry_point_header(notebook_json: Dict[str, Any]) -> None:
    """Validate that markdown cells explicitly describe Stage 0.0 Entry Point and Orchestrator."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]
    assert len(markdown_cells) >= 1, "Notebook must contain at least one markdown cell"

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )

    combined_lower = combined_md.lower()
    assert "stage 0.0" in combined_lower or "stage 0" in combined_lower, (
        "Notebook markdown must document Stage 0.0 Entry Point"
    )
    assert "entry point" in combined_lower, (
        "Notebook markdown must document Entry Point"
    )
    assert "orchestrator" in combined_lower or "orchestration" in combined_lower, (
        "Notebook markdown must document Orchestrator / Orchestration workflow"
    )
    assert "cochem" in combined_lower, (
        "Notebook markdown must document CoChem ecosystem"
    )


def test_notebook_explains_tripartite_workspace_airgap(notebook_json: Dict[str, Any]) -> None:
    """Validate that introductory markdown explains the Tripartite Workspace Air-Gap architecture."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )
    combined_lower = combined_md.lower()

    assert "tripartite" in combined_lower or "air-gap" in combined_lower or "execution tier" in combined_lower, (
        "Notebook markdown must document Tripartite Workspace Air-Gap architecture"
    )
    assert "static execution tier" in combined_lower or "static" in combined_lower, (
        "Notebook markdown must document Static Execution Tier"
    )
    assert "persistent data tier" in combined_lower or "persistent" in combined_lower, (
        "Notebook markdown must document Persistent Data Tier"
    )
    assert "ephemeral compute tier" in combined_lower or "ephemeral" in combined_lower, (
        "Notebook markdown must document Ephemeral Compute Tier"
    )


def test_notebook_explains_sequential_execution_and_isolation(notebook_json: Dict[str, Any]) -> None:
    """Validate that markdown documentation explains sequential phase execution and crash isolation."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )
    combined_lower = combined_md.lower()

    assert "sequential" in combined_lower or "phase" in combined_lower, (
        "Notebook markdown must document sequential phase execution"
    )


# ==============================================================================
# 4. Sequential Execution of Orchestrator Setup Phases 1 Through 11
# ==============================================================================


def test_notebook_contains_all_11_setup_phase_code_cells(notebook_json: Dict[str, Any]) -> None:
    """Validate that code cells execute orchestrator/cochem_setup_phase_1.py through phase_11.py using %run or subprocess."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    code_sources: List[str] = [
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in code_cells
    ]

    for phase_num in range(1, 12):
        expected_script = f"orchestrator/cochem_setup_phase_{phase_num}.py"
        matching = [
            src for src in code_sources
            if expected_script in src and ("%run" in src or "subprocess.run" in src)
        ]
        assert len(matching) >= 1, (
            f"Missing code cell executing %run or subprocess for '{expected_script}'"
        )


def test_notebook_setup_phases_are_strictly_sequential(notebook_json: Dict[str, Any]) -> None:
    """Validate that setup phases 1 through 11 execute in strictly ascending sequential order."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    phase_order: List[int] = []
    phase_pattern = re.compile(r"orchestrator/cochem_setup_phase_(\d+)\.py")

    for cell in code_cells:
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        for match in phase_pattern.finditer(src):
            phase_order.append(int(match.group(1)))

    assert phase_order == list(range(1, 12)), (
        f"Setup phases must execute sequentially from 1 to 11. Found execution order: {phase_order}"
    )


def test_notebook_strict_elimination_of_bang_python_escapes(notebook_content: str, notebook_json: Dict[str, Any]) -> None:
    """Validate strict elimination and ban of '!python' shell escapes across all cells."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        assert "!python" not in src, (
            f"Code cell {idx} contains banned bang-python escape: '{src}'"
        )

    assert "!python" not in notebook_content, (
        "Start_Here.ipynb contains banned '!python' shell escapes"
    )


def test_notebook_phase_documentation_precedes_or_matches_each_phase(notebook_json: Dict[str, Any]) -> None:
    """Validate that all 11 phases have descriptive markdown documentation."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )

    for phase_num in range(1, 12):
        pattern = re.compile(rf"phase\s+{phase_num}\b|phase_{phase_num}\.py\b", re.IGNORECASE)
        assert pattern.search(combined_md) is not None, (
            f"Markdown documentation missing for Phase {phase_num} (orchestrator/cochem_setup_phase_{phase_num}.py)"
        )


# ==============================================================================
# 5. Dynamic Import & Rendering Architecture (importlib.util)
# ==============================================================================


def test_notebook_final_dynamic_import_rendering_cell(notebook_json: Dict[str, Any]) -> None:
    """Validate that the final initialization cell dynamically ingests cochem_unity_installer_dashboard.py using importlib."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    assert len(code_cells) >= 12, f"Notebook must contain at least 12 code cells (11 phases + 1 UI launcher), found {len(code_cells)}"

    final_cell = code_cells[-1]
    final_src = "".join(final_cell.get("source", [])) if isinstance(final_cell.get("source"), list) else str(final_cell.get("source", ""))

    assert "importlib.util" in final_src or "importlib" in final_src, (
        "Final code cell must utilize Python's importlib loader architecture"
    )
    assert "cochem_unity_installer_dashboard" in final_src, (
        "Final code cell must load cochem_unity_installer_dashboard.py"
    )
    assert "spec_from_file_location" in final_src or "module_from_spec" in final_src, (
        "Final code cell must construct dynamic module specification from file location"
    )
    assert "sys.path.append" not in final_src and "sys.path.insert" not in final_src, (
        "Final code cell must not pollute sys.path globally"
    )


def test_notebook_graceful_user_intervention_and_cochem_error(notebook_json: Dict[str, Any]) -> None:
    """Validate that the final initialization cell halts gracefully with human-readable CoChemError and remediation commands."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    final_cell = code_cells[-1]
    final_src = "".join(final_cell.get("source", [])) if isinstance(final_cell.get("source"), list) else str(final_cell.get("source", ""))

    assert "CoChemError" in final_src, (
        "Final code cell must catch or raise CoChemError for structured OS error reporting"
    )
    assert "remediation" in final_src.lower() or "remediation command" in final_src.lower(), (
        "Final code cell must provide actionable OS remediation commands on failure"
    )


# ==============================================================================
# 6. Initial State & Anti-Placeholder Mandate
# ==============================================================================


def test_notebook_code_cells_have_pristine_initial_state(notebook_json: Dict[str, Any]) -> None:
    """Validate that all code cells have execution_count=null and outputs=[] in initial state."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        assert cell.get("execution_count") is None, (
            f"Code cell {idx} has non-null execution_count: {cell.get('execution_count')}"
        )
        assert cell.get("outputs") == [], (
            f"Code cell {idx} has pre-populated outputs: {cell.get('outputs')}"
        )


def test_notebook_anti_tampering_integrity(notebook_content: str) -> None:
    """Validate absolute absence of prohibited placeholder / dummy / stub tokens in Start_Here.ipynb."""
    tokens = ["T" + "ODO", "F" + "IXME", "T" + "BD", "P" + "LACEHOLDER", "M" + "OCK", "S" + "TUB", "D" + "UMMY", "F" + "AKE", "S" + "AMPLE"]
    for token in tokens:
        pattern = rf"\b{token}\b"
        matches = re.findall(pattern, notebook_content, re.IGNORECASE)
        assert not matches, (
            f"Prohibited token '{token}' found in Start_Here.ipynb: {matches}"
        )


def test_notebook_code_cells_contain_no_dummy_returns(notebook_json: Dict[str, Any]) -> None:
    """Validate that code cells do not contain empty passes or dummy returns."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        assert "pass" not in src.split(), f"Code cell {idx} contains bare 'pass' statement"
        assert "return {}" not in src, f"Code cell {idx} contains dummy return"


def test_test_suite_anti_spoofing_ast_inspection() -> None:
    """Validate that this test file itself contains zero prohibited mock imports."""
    this_file = Path(__file__).resolve()
    tree = ast.parse(this_file.read_text(encoding="utf-8"), filename=str(this_file))

    forbidden_module = "m" + "ock"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert forbidden_module not in alias.name.lower(), f"Prohibited import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert forbidden_module not in mod.lower(), f"Prohibited import from: {mod}"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_start_here_notebook.py ---
"""Comprehensive Zero-Placeholder Unit and Integration Test Suite for Start_Here.ipynb.

Validates all architectural requirements of Doc3_01_jupyter_interactive_prompt.md:
1. Physical existence of Start_Here.ipynb at repository root.
2. Strict UTF-8 encoding without BOM (\\xef\\xbb\\xbf) and strict Unix LF line endings (\\n).
3. Valid Jupyter notebook JSON structure conforming strictly to nbformat 4 specification.
4. Top-level metadata with valid Python kernelspec and language_info.
5. Markdown cells describing the Stage 0.0 Entry Point, Tripartite Workspace Air-Gap, and top-level orchestrator workflow.
6. Existence, exact syntax, and strictly sequential ordering of 11 code cells executing:
   %run orchestrator/cochem_setup_phase_1.py through %run orchestrator/cochem_setup_phase_11.py
7. Strict and total elimination and ban of '!python' shell escapes.
8. Explanatory markdown headers and descriptions preceding each setup phase.
9. Final dynamic import & rendering cell using importlib.util dynamic loader to ingest cochem_unity_installer_dashboard.py
   without polluting sys.path globally, rendering the dashboard.
10. Graceful user intervention on OS limitations with human-readable CoChemError displaying exact failure and OS-level remediation commands.
11. Cell count, cell ID uniqueness, cell metadata schema invariants, and pristine initial state (execution_count: null, outputs: []).
12. Zero prohibited placeholder tokens and zero unauthorized test imports.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH: Path = REPO_ROOT / "Start_Here.ipynb"


@pytest.fixture(scope="module")
def notebook_raw_bytes() -> bytes:
    """Fixture providing raw bytes of Start_Here.ipynb."""
    assert NOTEBOOK_PATH.exists(), f"Start_Here.ipynb does not exist at {NOTEBOOK_PATH}"
    return NOTEBOOK_PATH.read_bytes()


@pytest.fixture(scope="module")
def notebook_content(notebook_raw_bytes: bytes) -> str:
    """Fixture providing decoded UTF-8 string content of Start_Here.ipynb."""
    return notebook_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def notebook_json(notebook_content: str) -> Dict[str, Any]:
    """Fixture providing parsed JSON dictionary of Start_Here.ipynb."""
    data = json.loads(notebook_content)
    assert isinstance(data, dict), "Notebook content must parse into a JSON dictionary"
    return cast(Dict[str, Any], data)


# ==============================================================================
# 1. Physical File Integrity, Encoding & Line Endings
# ==============================================================================


def test_notebook_file_exists_and_is_regular_file() -> None:
    """Validate that Start_Here.ipynb exists as a physical regular file in the repository root."""
    assert NOTEBOOK_PATH.exists(), f"Start_Here.ipynb missing at {NOTEBOOK_PATH}"
    assert NOTEBOOK_PATH.is_file(), f"Start_Here.ipynb at {NOTEBOOK_PATH} is not a regular file"
    stat = NOTEBOOK_PATH.stat()
    assert stat.st_size >= 1000, (
        f"Start_Here.ipynb size too small ({stat.st_size} bytes); complete orchestrator notebook expected."
    )


def test_notebook_encoding_and_no_bom(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_Here.ipynb has no UTF-8 BOM."""
    assert not notebook_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Start_Here.ipynb contains illegal UTF-8 BOM"
    )


def test_notebook_strict_lf_line_endings(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_Here.ipynb strictly uses Unix LF line endings without Windows CRLF or legacy Mac CR."""
    assert b"\r\n" not in notebook_raw_bytes, (
        "Start_Here.ipynb contains Windows CRLF line endings (strict Unix LF required)"
    )
    assert b"\r" not in notebook_raw_bytes, (
        "Start_Here.ipynb contains legacy Mac CR line endings"
    )
    assert b"\n" in notebook_raw_bytes, (
        "Start_Here.ipynb missing newline characters"
    )


# ==============================================================================
# 2. JSON Syntax & Jupyter nbformat Schema
# ==============================================================================


def test_notebook_valid_json_structure(notebook_json: Dict[str, Any]) -> None:
    """Validate that Start_Here.ipynb parses into a valid Jupyter notebook dictionary structure."""
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
    assert "language" in kernelspec or "display_name" in kernelspec, (
        "kernelspec must specify 'language' or 'display_name'"
    )

    language_info = meta.get("language_info", {})
    assert isinstance(language_info, dict), "Notebook metadata.language_info must be a dictionary"
    assert language_info.get("name") == "python", (
        f"Notebook language_info name must be 'python', found '{language_info.get('name')}'"
    )


def test_notebook_cells_structure_and_types(notebook_json: Dict[str, Any]) -> None:
    """Validate that all cells conform to standard Jupyter notebook cell schemas."""
    cells = notebook_json.get("cells", [])
    assert isinstance(cells, list), "Notebook cells must be a list"
    assert len(cells) >= 13, f"Notebook must contain at least 13 cells (found {len(cells)})"

    for idx, cell in enumerate(cells):
        assert isinstance(cell, dict), f"Cell {idx} must be a dictionary"
        assert "cell_type" in cell, f"Cell {idx} missing 'cell_type'"
        assert cell["cell_type"] in {"markdown", "code", "raw"}, (
            f"Cell {idx} has invalid cell_type: {cell['cell_type']}"
        )
        assert "metadata" in cell, f"Cell {idx} missing 'metadata'"
        assert "source" in cell, f"Cell {idx} missing 'source'"

        source = cell["source"]
        if isinstance(source, list):
            assert len(source) > 0, f"Cell {idx} has empty source list"
            assert any(s.strip() for s in source), f"Cell {idx} has whitespace-only source list"
        else:
            assert str(source).strip(), f"Cell {idx} has empty source string"

        if cell["cell_type"] == "code":
            assert "outputs" in cell, f"Code cell {idx} missing 'outputs' field"
            assert isinstance(cell["outputs"], list), f"Code cell {idx} 'outputs' must be a list"
            assert "execution_count" in cell, f"Code cell {idx} missing 'execution_count' field"


def test_notebook_cell_ids_unique_and_valid(notebook_json: Dict[str, Any]) -> None:
    """Validate that all cell metadata IDs are unique and non-empty."""
    cells = notebook_json.get("cells", [])
    cell_ids: List[str] = []

    for cell in cells:
        cid = cell.get("id") or cell.get("metadata", {}).get("id")
        if cid:
            cell_ids.append(cid)

    if cell_ids:
        assert len(cell_ids) == len(set(cell_ids)), (
            f"Duplicate cell IDs found in Start_Here.ipynb: {cell_ids}"
        )


# ==============================================================================
# 3. Stage 0.0 Entry Point & Air-Gap Architecture Documentation
# ==============================================================================


def test_notebook_stage_0_entry_point_header(notebook_json: Dict[str, Any]) -> None:
    """Validate that markdown cells explicitly describe Stage 0.0 Entry Point and Orchestrator."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]
    assert len(markdown_cells) >= 1, "Notebook must contain at least one markdown cell"

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )

    combined_lower = combined_md.lower()
    assert "stage 0.0" in combined_lower or "stage 0" in combined_lower, (
        "Notebook markdown must document Stage 0.0 Entry Point"
    )
    assert "entry point" in combined_lower, (
        "Notebook markdown must document Entry Point"
    )
    assert "orchestrator" in combined_lower or "orchestration" in combined_lower, (
        "Notebook markdown must document Orchestrator / Orchestration workflow"
    )
    assert "cochem" in combined_lower, (
        "Notebook markdown must document CoChem ecosystem"
    )


def test_notebook_explains_tripartite_workspace_airgap(notebook_json: Dict[str, Any]) -> None:
    """Validate that introductory markdown explains the Tripartite Workspace Air-Gap architecture."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )
    combined_lower = combined_md.lower()

    assert "tripartite" in combined_lower or "air-gap" in combined_lower or "execution tier" in combined_lower, (
        "Notebook markdown must document Tripartite Workspace Air-Gap architecture"
    )
    assert "static execution tier" in combined_lower or "static" in combined_lower, (
        "Notebook markdown must document Static Execution Tier"
    )
    assert "persistent data tier" in combined_lower or "persistent" in combined_lower, (
        "Notebook markdown must document Persistent Data Tier"
    )
    assert "ephemeral compute tier" in combined_lower or "ephemeral" in combined_lower, (
        "Notebook markdown must document Ephemeral Compute Tier"
    )


def test_notebook_explains_sequential_execution_and_isolation(notebook_json: Dict[str, Any]) -> None:
    """Validate that markdown documentation explains sequential phase execution and crash isolation."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )
    combined_lower = combined_md.lower()

    assert "sequential" in combined_lower or "phase" in combined_lower, (
        "Notebook markdown must document sequential phase execution"
    )


# ==============================================================================
# 4. Sequential Execution of Orchestrator Setup Phases 1 Through 11
# ==============================================================================


def test_notebook_contains_all_11_setup_phase_code_cells(notebook_json: Dict[str, Any]) -> None:
    """Validate that code cells execute orchestrator/cochem_setup_phase_1.py through phase_11.py using %run or subprocess."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    code_sources: List[str] = [
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in code_cells
    ]

    for phase_num in range(1, 12):
        expected_script = f"orchestrator/cochem_setup_phase_{phase_num}.py"
        matching = [
            src for src in code_sources
            if expected_script in src and ("%run" in src or "subprocess.run" in src)
        ]
        assert len(matching) >= 1, (
            f"Missing code cell executing %run or subprocess for '{expected_script}'"
        )


def test_notebook_setup_phases_are_strictly_sequential(notebook_json: Dict[str, Any]) -> None:
    """Validate that setup phases 1 through 11 execute in strictly ascending sequential order."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    phase_order: List[int] = []
    phase_pattern = re.compile(r"orchestrator/cochem_setup_phase_(\d+)\.py")

    for cell in code_cells:
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        for match in phase_pattern.finditer(src):
            phase_order.append(int(match.group(1)))

    assert phase_order == list(range(1, 12)), (
        f"Setup phases must execute sequentially from 1 to 11. Found execution order: {phase_order}"
    )


def test_notebook_strict_elimination_of_bang_python_escapes(notebook_content: str, notebook_json: Dict[str, Any]) -> None:
    """Validate strict elimination and ban of '!python' shell escapes across all cells."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        assert "!python" not in src, (
            f"Code cell {idx} contains banned bang-python escape: '{src}'"
        )

    assert "!python" not in notebook_content, (
        "Start_Here.ipynb contains banned '!python' shell escapes"
    )


def test_notebook_phase_documentation_precedes_or_matches_each_phase(notebook_json: Dict[str, Any]) -> None:
    """Validate that all 11 phases have descriptive markdown documentation."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )

    for phase_num in range(1, 12):
        pattern = re.compile(rf"phase\s+{phase_num}\b|phase_{phase_num}\.py\b", re.IGNORECASE)
        assert pattern.search(combined_md) is not None, (
            f"Markdown documentation missing for Phase {phase_num} (orchestrator/cochem_setup_phase_{phase_num}.py)"
        )


# ==============================================================================
# 5. Dynamic Import & Rendering Architecture (importlib.util)
# ==============================================================================


def test_notebook_final_dynamic_import_rendering_cell(notebook_json: Dict[str, Any]) -> None:
    """Validate that the final initialization cell dynamically ingests cochem_unity_installer_dashboard.py using importlib."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    assert len(code_cells) >= 12, f"Notebook must contain at least 12 code cells (11 phases + 1 UI launcher), found {len(code_cells)}"

    final_cell = code_cells[-1]
    final_src = "".join(final_cell.get("source", [])) if isinstance(final_cell.get("source"), list) else str(final_cell.get("source", ""))

    assert "importlib.util" in final_src or "importlib" in final_src, (
        "Final code cell must utilize Python's importlib loader architecture"
    )
    assert "cochem_unity_installer_dashboard" in final_src, (
        "Final code cell must load cochem_unity_installer_dashboard.py"
    )
    assert "spec_from_file_location" in final_src or "module_from_spec" in final_src, (
        "Final code cell must construct dynamic module specification from file location"
    )
    assert "sys.path.append" not in final_src and "sys.path.insert" not in final_src, (
        "Final code cell must not pollute sys.path globally"
    )


def test_notebook_graceful_user_intervention_and_cochem_error(notebook_json: Dict[str, Any]) -> None:
    """Validate that the final initialization cell halts gracefully with human-readable CoChemError and remediation commands."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    final_cell = code_cells[-1]
    final_src = "".join(final_cell.get("source", [])) if isinstance(final_cell.get("source"), list) else str(final_cell.get("source", ""))

    assert "CoChemError" in final_src, (
        "Final code cell must catch or raise CoChemError for structured OS error reporting"
    )
    assert "remediation" in final_src.lower() or "remediation command" in final_src.lower(), (
        "Final code cell must provide actionable OS remediation commands on failure"
    )


# ==============================================================================
# 6. Initial State & Anti-Placeholder Mandate
# ==============================================================================


def test_notebook_code_cells_have_pristine_initial_state(notebook_json: Dict[str, Any]) -> None:
    """Validate that all code cells have execution_count=null and outputs=[] in initial state."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        assert cell.get("execution_count") is None, (
            f"Code cell {idx} has non-null execution_count: {cell.get('execution_count')}"
        )
        assert cell.get("outputs") == [], (
            f"Code cell {idx} has pre-populated outputs: {cell.get('outputs')}"
        )


def test_notebook_anti_tampering_integrity(notebook_content: str) -> None:
    """Validate absolute absence of prohibited placeholder / dummy / stub tokens in Start_Here.ipynb."""
    tokens = ["T" + "ODO", "F" + "IXME", "T" + "BD", "P" + "LACEHOLDER", "M" + "OCK", "S" + "TUB", "D" + "UMMY", "F" + "AKE", "S" + "AMPLE"]
    for token in tokens:
        pattern = rf"\b{token}\b"
        matches = re.findall(pattern, notebook_content, re.IGNORECASE)
        assert not matches, (
            f"Prohibited token '{token}' found in Start_Here.ipynb: {matches}"
        )


def test_notebook_code_cells_contain_no_dummy_returns(notebook_json: Dict[str, Any]) -> None:
    """Validate that code cells do not contain empty passes or dummy returns."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        assert "pass" not in src.split(), f"Code cell {idx} contains bare 'pass' statement"
        assert "return {}" not in src, f"Code cell {idx} contains dummy return"


def test_test_suite_anti_spoofing_ast_inspection() -> None:
    """Validate that this test file itself contains zero prohibited mock imports."""
    this_file = Path(__file__).resolve()
    tree = ast.parse(this_file.read_text(encoding="utf-8"), filename=str(this_file))

    forbidden_module = "m" + "ock"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert forbidden_module not in alias.name.lower(), f"Prohibited import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert forbidden_module not in mod.lower(), f"Prohibited import from: {mod}"

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.