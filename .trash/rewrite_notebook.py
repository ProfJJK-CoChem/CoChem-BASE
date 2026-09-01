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

