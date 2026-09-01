# [SDPM REPORT] Voila No-Code GUI Implementation - Cycle 1: Architectural Summit

## 1. Project Charter & Scope Statement
**Project Name:** CoChem Voila No-Code GUI
**Objective:** To implement a robust, reactive, browser-based graphical user interface for the CoChem simulation environment using Jupyter `ipywidgets` and `voila`.
**Scope:**
This project covers the architectural design, state management implementation, cross-environment compatibility assurance, and deployment of a zero-mock, physics-grounded GUI. The GUI will allow researchers to interact with CoChem models without writing code, adhering strictly to the Method Matrix [M] and avoiding all spoofed or synthetic data generation.

## 2. State Management Model
The architecture will employ a strict Model-View-Controller (MVC) pattern utilizing `traitlets` for reactive UI binding within `ipywidgets`.
- **Model:** Represents the physical state and empirical benchmarks (Derived mathematical relationships [D], Empirical theoretical projections [E]). Strictly bounded by the Anti-Spoofing Directive; no `np.zeros` or dummy loops. State must be loaded from ab-initio output files or genuine physical states.
- **View:** `ipywidgets` components structurally observing `traitlets` from the Model.
- **Controller:** Manages interactions and orchestrates the transition of states based on user inputs. **State management safely references native `cochem_base.orchestrator` logging through direct module imports, strictly avoiding any brittle subprocess execution or stdout-scraping workarounds.**

## 3. Cross-Environment Compatibility Matrix
The Voila GUI must function seamlessly across the following environments:

| Environment | Supported | Deployment Strategy |
| :--- | :--- | :--- |
| **Codespaces** | Yes | Port forwarding for Voila server (default port 8866) |
| **WSL (Windows)** | Yes | Localhost binding, accessible via Windows browser |
| **Linux HPC** | Yes | JupyterHub integration or SSH tunneling with explicit port forwarding (`ssh -N -f -L 8866:localhost:8866 user@hpc_node`) to securely expose the GUI |
| **Mac (macOS)** | Yes | Native local execution and browser rendering |

## 4. Work Breakdown Structure (WBS) & Task Lists
- [ ] **Task 1.1:** Finalize and approve this GUI Architecture Charter. (Assigned: `cochem-sdp-manager`, `cochem-audit`)
- [ ] **Task 1.2:** Initialize the MVC directory structure within the CoChem repository. (Assigned: `cochem-coder`)
- [ ] **Task 1.3:** Implement the base `traitlets` Model class with strict physical data validation. (Assigned: `cochem-coder`)
- [ ] **Task 1.4:** Construct the root View container using `ipywidgets`. (Assigned: `cochem-coder`)
- [ ] **Task 1.5:** Write integration tests loading `.h5` / `.npz` ab-initio data to verify Model-View binding without synthetic data. (Assigned: `cochem-tester`)
- [ ] **Task 1.6:** Asymmetric Verification of the state management pipeline in a sterile environment. (Assigned: `cochem-audit`)

## 5. Risk Register
| Risk ID | Description | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **R1** | Spawning parallel Voila instances leads to Agent Bomb timeouts. | High | **Avoid**: Strictly limit GUI initialization to single-threaded or managed async environments. |
| **R2** | Developers inject mock data for UI testing. | Critical | **Mitigate**: Enforce `anti_spoof_linter.py` in CI/CD. Native subagent audits for every UI component merge. |
| **R3** | Port conflicts across different deployment environments (e.g., WSL vs Mac). | Medium | **Transfer / Mitigate**: Implement dynamic port allocation with configurable defaults. |

## 6. Compliance Procedures
- All UI state must strictly reflect the underlying physics state (Anti-Spoofing Directive).
- No hardcoded 'placeholder' values in the view layer. Missing data must be explicitly reported as `[MISSING DATA]`.
- Asymmetric Verification (`cochem-audit`) is required before finalizing the GUI components.
- Root Cause Resolution Mandate: Any UI crashes must be traced to the data generator, not masked with broad `try/except` in the View layer.
