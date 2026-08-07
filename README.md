# **CoChem-BASE**

**The Unified Core Execution, Ingestion, and Telemetry Platform for CoChem**

`CoChem-BASE` serves as the central orchestration framework and configuration engine for the CoChem ecosystem. It replaces the legacy `CoChem-CORE` and `CoChem-SYNAP` architectures, unifying system setup, configuration compilers, molecular ingestion, calculation routing, and visualization dashboards into a single, cohesive repository.

---

## **🏗️ Repository Layout & Architecture**

Unlike the previous decoupled core libraries, `CoChem-BASE` consolidates all critical base-layer operations into organized namespaces:

### **1. Core Engine (`core_engine/`)**
* **[cochem_core_workspace_manager.py](file:///d:/GitHub-Repo/CoChem-BASE/core_engine/cochem_core_workspace_manager.py)**: Manages directory structure setup and air-gap directories verification.
* **[cochem_core_registry_manager.py](file:///d:/GitHub-Repo/CoChem-BASE/core_engine/cochem_core_registry_manager.py)**: Authoritative state registry manager reading/writing `cochem_system_config.json`.
* **[cochem_core_registry_schema.py](file:///d:/GitHub-Repo/CoChem-BASE/core_engine/cochem_core_registry_schema.py)**: Pydantic schemas validating system configuration parameters.
* **[cochem_core_subprocess_broker.py](file:///d:/GitHub-Repo/CoChem-BASE/core_engine/cochem_core_subprocess_broker.py)**: Safe process executor with memory limits, OOM monitoring, and automatic cleanups.
* **[cochem_core_telemetry_logger.py](file:///d:/GitHub-Repo/CoChem-BASE/core_engine/cochem_core_telemetry_logger.py)**: Logs calculation metrics, process diagnostics, and system parameters.
* **[cochem_core_scheduler.py](file:///d:/GitHub-Repo/CoChem-BASE/core_engine/cochem_core_scheduler.py)** & **[cochem_core_job_manager.py](file:///d:/GitHub-Repo/CoChem-BASE/core_engine/cochem_core_job_manager.py)**: Queues and manages execution lifecycles of active calculation jobs.

### **2. Calculation Routing (`calc/`)**
* **[cochem_calc_input_generator.py](file:///d:/GitHub-Repo/CoChem-BASE/calc/cochem_calc_input_generator.py)**: Generates ORCA quantum chemistry input files with customized route cards.
* **[cochem_calc_execution_router.py](file:///d:/GitHub-Repo/CoChem-BASE/calc/cochem_calc_execution_router.py)**: Coordinates execution routes based on hardware profiles (WSL vs. Native Linux vs. HPC).
* **[cochem_calc_output_parser.py](file:///d:/GitHub-Repo/CoChem-BASE/calc/cochem_calc_output_parser.py)**: Extracts final energies, coordinates, and convergence logs from quantum calculations output files.

### **3. Ingestion Backend (`intake/`)**
* **[cochem_mint_ingestor.py](file:///d:/GitHub-Repo/CoChem-BASE/intake/cochem_mint_ingestor.py)**: Queries NIH Cactus structure databases, sanitizes SMILES structures, and builds 3D coordinates using RDKit force fields.
* **[cochem_stage2_ingestor.py](file:///d:/GitHub-Repo/CoChem-BASE/intake/cochem_stage2_ingestor.py)**: Parses raw `.xyz` files and validates atomic structures.

### **4. Visual Interfaces & Telemetry (`interfaces/`)**
* **[cochem_unity_installer_dashboard.py](file:///d:/GitHub-Repo/CoChem-BASE/interfaces/cochem_unity_installer_dashboard.py)**: Jupyter `ipywidgets` dashboard for ecosystem component installations.
* **[cochem_dock_main.py](file:///d:/GitHub-Repo/CoChem-BASE/interfaces/cochem_dock_main.py)**: FastAPI WebSocket server streaming stdout logs to Web UI controls.
* **[cochem_unity_fast_pass_widget.py](file:///d:/GitHub-Repo/CoChem-BASE/interfaces/cochem_unity_fast_pass_widget.py)**: Quick form widgets for triggering localized computations.

### **5. Installation Bootstrapping (`setup/`)**
* **[cochem_setup_orchestrator.py](file:///d:/GitHub-Repo/CoChem-BASE/setup/cochem_setup_orchestrator.py)**: Primary dual-matrix environment mapper executing OS-native configuration scripts.
* **[calc_wsl.py](file:///d:/GitHub-Repo/CoChem-BASE/setup/calc_wsl.py)** & **[interact_wsl.py](file:///d:/GitHub-Repo/CoChem-BASE/setup/interact_wsl.py)**: Handles WSL2 specific environment provisionings and dependencies resolution.
* **[calc_hpc.py](file:///d:/GitHub-Repo/CoChem-BASE/setup/calc_hpc.py)**: Configures remote cluster SLURM scripts and configurations.

---

## **⚠️ The Filesystem Air-Gap Policy**

To guarantee security and version control hygiene when handling massive output datasets (.gbw, .tmp files), `CoChem-BASE` enforces a strict air-gap boundary:
1. **Static Execution Tier (`d:/GitHub-Repo/CoChem-BASE/` or equivalent clone directory)**: Contains purely static Python source codes, configuration schemas, and notebooks. It remains write-protected during core computations.
2. **Dynamic Artifact Tier (`$HOME/CoChem_Artifacts/`)**: Designated read-write folder holding the central `cochem_system_config.json` registry, `landscape.h5` databases, and execution logs.

---

## **🚀 Quickstart & Bootstrapping**

To initialize the `CoChem-BASE` platform and establish the environment registries:

1. Launch your Jupyter server and open **[Start_Here.ipynb](file:///d:/GitHub-Repo/CoChem-BASE/Start_Here.ipynb)**.
2. Execute the initialization cells to display the `CoChem-UNITY` installation dashboard.
3. Select your target environment layout (e.g., local native Linux, Windows + WSL2, or remote HPC) and click **Run Setup Orchestrator**.

Alternatively, run the setup directly via terminal:
```bash
python3 setup/cochem_setup_orchestrator.py
```

---

## **🤝 Downstream Integrations**
Highly decoupled research sub-modules (such as `CoChem-TOPOS` for conformational discovery, `CoChem-TORQ` for rotational fits, and `CoChem-MAGE` for GC-MS analysis) query the registry compiled by `CoChem-BASE` to resolve path constants and dispatch tasks via the subprocess broker.