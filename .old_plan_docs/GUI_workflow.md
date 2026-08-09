# CoChem-Studio GUI Implementation Workflow
**Target Audience:** Autonomous Coder LLM Agent
**Objective:** Fully and faithfully implement the architecture defined in `GUI_architecture.md`.

## Workflow Overview
This workflow is an exhaustive, phase-by-phase instruction set designed to guide a Coder LLM through the complete implementation of the CoChem-Studio GUI. The architecture relies on **Modular Resilience**, meaning the core shell must be robust, and the 11 optional modules must be dynamically discovered and loaded.

**CRITICAL INSTRUCTION FOR CODER LLM:** Do NOT attempt to build the entire GUI in a single pass. You must complete, verify, and commit each Phase before proceeding to the next.

---

## Phase 1: Project Scaffolding & Environment Setup [x]
1. **Directory Structure:** Create the following Python package structures in `D:\GitHub-Repo\CoChem-BASE`:
   - `cochem_base/`
     - `gui/` (Contains main shell and core widgets)
     - `core/` (Hardware orchestration logic)
     - `plugins/` (Hook definitions and discovery logic)
2. **Dependencies:** Generate a `requirements.txt` or `pyproject.toml` including:
   - `PySide6` (for the core desktop GUI)
   - `pluggy` (for the plugin architecture)
   - `pydantic` (for data validation and the Correlation Matrix)
   - `pyqtgraph` (for high-performance plotting)
   - `pyvista` or `vtk` (for 3D molecular viewing)
3. **Verification:** Ensure the basic entry point `python -m cochem_base.gui.main` launches a blank PySide6 window.

---

## Phase 2: The Core Application Shell & Plugin Loader [x]
1. **Main Window (`main_window.py`):**
   - Implement a PySide6 `QMainWindow` with a central Tab Widget and a persistent Bottom Dock (for SCRIBE).
2. **Plugin Discovery Engine (`plugins/loader.py`):**
   - Implement a `pluggy` Hookspec or an `importlib` scanner that searches the Python environment for installed packages matching the prefix `cochem_*`.
   - Define the Core API Hooks:
     - `hookspec: def register_tabs(main_window)`
     - `hookspec: def register_3d_overlays(viewer)`
     - `hookspec: def register_menu_actions(menu_bar)`
3. **Verification:** Create a dummy plugin, install it, and verify that the Main Window dynamically loads a new tab from the dummy plugin.

---

## Phase 3: Core Modules Implementation (The Backbone) [x]
The Coder LLM must implement the 4 core modules that are *always* present.

### 3.1 CoChem-BASE (Hardware Orchestrator)
- Build the `Home Dashboard`.
- Implement PySide6 progress bars and CPU/GPU utilization monitors.
- **Data Model:** Implement the Correlation Matrix using Pydantic to ensure strict typing between computational stages.

### 3.2 CoChem-TOPOS (Combinatorial Engine)
- Build the `Structural Input & 3D Viewer Tab`.
- Embed the `pyvista` Qt interactor widget into the tab.
- Implement UI toggles for conformational searches.

### 3.3 CoChem-TORQ (Quantum Resonance)
- Build the `Physics Configuration Panel`.
- Implement interactive sliders that determine classical vs. quantum treatment thresholds.

### 3.4 CoChem-SCRIBE (Data Provenance)
- Build a persistent `QDockWidget` at the bottom of the screen.
- Implement a read-only logging console that asynchronously intercepts `stdout`/`stderr` from the background daemons.

---

## Phase 4: Optional Modules Integration (Dynamic Plugins)
For each optional module, the Coder LLM must navigate to its respective repository (e.g., `D:\GitHub-Repo\CoChem-SpycFit`), implement the PySide6 widgets, and expose them via the `hookimpl` endpoints defined in Phase 2.

**Implementation Batches:**
- **Batch A (Spectroscopy):** `SpycFit` (Interactive peak fitting), `LUMOS` (UV-Vis plots), `SHIFT` (NMR viewer), `PULSE` (Time-resolved animations), `MAGE` (GC-MS).
- **Batch B (Structure & Thermo):** `GEOM` (Precision overlays on the TOPOS 3D viewer), `KINETIC` (Reaction coordinate diagrams), `SCAN` (2D/3D PES contour plots).
- **Batch C (Advanced/AI):** `BENCH` (CBS extrapolation graphs), `NODE` (Cluster queues), `ORACLE` (Floating RAG chat window).

**Graceful Degradation Verification:**
- The LLM must write automated tests utilizing `unittest.mock` to simulate the absence of `cochem_spycfit` and verify that the application still boots successfully without crashing, instead rendering a "Module Missing" didactic tooltip.

---

## Phase 5: Enforcing the 300 GUI Suggestions (Academic & Scientific Polish)
Referencing Section 7 of `GUI_architecture.md`, the Coder LLM must perform an exhaustive pass across all 15 modules to inject the 300 specific directives:
1. **Academic Integrity & Citations:** Implement automated methodology citation generators (ACS style) triggered by the user's specific pathway choices. The LLM must write tests verifying that selecting "CCSD(T)" outputs the correct literature citation.
2. **Scientific Error Prevention (Pydantic validation):** Enforce strict physical bounds on all UI inputs (e.g., rejecting negative Kelvin, checking multiplicity vs. electron count).
3. **Didactic Mathematical Views:** Implement the "Didactic View" toggle in every module, which maps raw computational parameters back to their fundamental quantum mechanical equations via rendered LaTeX overlays.
4. **Visual Theoretical Validation:** Implement the required color-coding (e.g., Green for high-accuracy ab initio, Yellow for DFT, Red for semi-empirical/molecular mechanics) to visually guide the researcher towards scientifically valid conclusions.

---

## Phase 6: Method Pass-Through & Correlation Matrix Validation
1. **Data Provenance:** The LLM must implement the central `Method Matrix` schema.
2. **Pipeline Testing:** Write PyTest suites verifying that parameters generated in `TOPOS` (e.g., Z-Matrices) perfectly map into the inputs for `GEOM` and `TORQ`, and subsequently route accurately to `KINETIC` and `SpycFit` without data loss or theoretical mismatch.
3. **Hardware-Awareness Check:** Ensure that the hardware impact estimators correctly preempt execution if the selected basis set and molecular size exceed the node's available RAM.

---

## Phase 7: Final End-to-End State & Compliance Verification
1. **State Serialization:** Implement a `Save/Load Workspace` feature that serializes the entire GUI state to a JSON file.
2. **Integration Test:** 
   - Load a sample molecule.
   - Run it through the TOPOS -> GEOM -> KINETIC -> SpycFit pipeline via the GUI.
   - Verify that clicking a spectral peak in the SpycFit tab successfully triggers the hook to highlight the corresponding atoms in the TOPOS 3D viewer.
3. **Sign-off:** Generate `GUI_implementation_report.md` detailing the successful completion of the architecture and passing of all scientific validity unit tests.
