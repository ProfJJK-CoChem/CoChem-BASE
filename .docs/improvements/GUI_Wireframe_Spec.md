# Voila No-Code GUI: Wireframe & UX Design Specification

## 1. Overview
This document outlines the UX design and structural wireframes for the CoChem Voila No-Code GUI, adhering to the requirements set forth in the `GUI_Architecture_Charter.md`, Jakob Nielsen's 10 Heuristics, WCAG 2.1 AA accessibility standards, and ACS Plotting standards. 

The GUI will be built using `ipywidgets` and deployed via `voila`, ensuring responsiveness across diverse environments (Codespaces, WSL, Linux HPC, Mac) and strictly following the Zero-Mock and Anti-Spoofing mandates.

## 2. Global Layout & Grid System
The core application will utilize `ipywidgets.AppLayout` or a structured combination of `VBox` and `HBox` to ensure responsive behavior and semantic structure.

### Layout Grid Composition
*   **Header (Appbar):** Global context and system status.
*   **Left Sidebar (Navigation):** Context switching and global tools.
*   **Center (Main Content Area):** The primary workspace, rendering active modules (Install Wizard or Matrix Configuration).
*   **Footer (Global Notifications):** A reserved, non-intrusive area for system messages and error handling.

---

## 3. Component Specifications

### 3.1 Appbar (Header)
**Purpose:** Provide immediate context and global state visibility.
**Widgets Used:** `HTML`, `HBox`
**Elements:**
*   **Brand/Title:** "CoChem No-Code Interface" (styled with clear contrast).
*   **State Indicator:** A dynamic status badge (e.g., `[System: Idle]`, `[System: Processing]`, `[Data: Loaded]`). This binds strictly to the `cochem_base.orchestrator` state.
*   **Environment Info:** Displays active environment (e.g., "HPC Tunnel", "WSL Local").

### 3.2 Sidebar (Navigation)
**Purpose:** Allow intuitive switching between distinct workflows.
**Widgets Used:** `ToggleButtons` (styled as a vertical menu) or a vertical `VBox` of `Button` widgets.
**Elements:**
*   **Menu Item 1:** "Seamless Install"
*   **Menu Item 2:** "No Code Matrix"
*   **Menu Item 3:** "Data Inspector (Ab-Initio)"
*   **Visual Design:** Active states will have high-contrast highlighting (WCAG 2.1 AA compliant). 

### 3.3 Main Content Area
**Purpose:** The primary interactive zone, changing based on Sidebar selection.
**Widgets Used:** `Output` widget containing dynamic `VBox` blocks, or an invisible `Tab` widget controlled by the Sidebar.

#### View A: "Seamless Install" Wizard
**Goal:** Guide the user through environment configuration, decision inputs for the setup pipeline, and real physical data ingestion.
*   **Layout:** A linear progression format (Stepper/Wizard) or vertical configuration stack.
*   **Widgets:** `Accordion`, `Dropdown` / `RadioButtons`, `Button`, and sequential `VBox` containers.
*   **Steps / Inputs:**
    1.  **Environment Validation:** Read-only outputs verifying existing paths and compute availability.
    2.  **Configuration Decisions (Pre-Install):**
        *   **License Mode:** `Dropdown` with options: `[ORCA]`, `[CFOUR]`, `[No License Only]`.
        *   **Calculation Environment:** `Dropdown` with options: `[Local]`, `[GitHub Actions]`, `[HPC]`.
        *   **Interaction Environment:** `Dropdown` with options: `[Local]`, `[GitHub Codespaces]`.
    3.  **Ab-Initio Data Ingestion:** File browser/path input. **Zero-Mock Enforcement:** UI blocks progression if valid `.h5` or `.npz` files are absent; never mocks success.
    4.  **Initialization:** "Commit/Install" button. Triggers the automated setup pipeline, piping calculations into the correct Anaconda silo environments.

#### View B: "No Code Matrix" (Calculational Configuration)
**Goal:** Interface for configuring and launching physical simulations mapped to the Method Matrix [M].
*   **Layout:** Grid-based configuration panel.
*   **Widgets:** `GridBox`, `Dropdown`, `FloatSlider`, `IntText`.
*   **Sections:**
    *   **Physical Parameters:** Input fields for theoretical projections (Strictly bounded by empirical models).
    *   **Method Matrix [M] Selection:** Dropdowns to select basis sets, exchange-correlation functionals, etc.
    *   **Execution Control:** "Run Simulation" button.
    *   **Live Output / ACS Plotting Area:** An `Output` widget reserved for `matplotlib` figures adhering to ACS plotting standards (e.g., proper axis labels, standard fonts, high-contrast lines).

### 3.4 Error Handling & Notification System
**Purpose:** Gracefully handle exceptions without breaking the grid, providing actionable feedback (Heuristic: Help users recognize, diagnose, and recover from errors).
**Widgets Used:** `HTML` block inside the Footer, or a dedicated fixed `Output` area at the top of the Main Content Area.
**Behavior:**
*   **Non-Blocking:** Errors (e.g., missing data, invalid physics parameters) will generate a styled HTML banner (`<div class="alert alert-danger">...</div>`) within the dedicated notification box.
*   **Traceability:** As per the Root Cause Resolution Mandate, errors will trace back to the data generator. The UI will output the exact log reference rather than masking it.
*   **Zero-Mock Compliance:** If data is missing, the UI will display `[MISSING DATA]`, and inputs will disable to prevent state corruption.

---

## 4. UI/UX Principles Applied
1.  **Match between system and real world:** Terminology explicitly aligns with CoChem physical models (Method Matrix, Ab-Initio).
2.  **User control and freedom:** Clear separation of configuration (Matrix) and setup (Install), with unambiguous state indicators.
3.  **Accessibility (WCAG 2.1 AA):** All text will maintain >4.5:1 contrast ratios. Interactive elements (buttons, sliders) will have defined `aria-label` equivalents using widget descriptions.
4.  **Scientific Rigor (ACS Standards):** Any generated plots in the Matrix View will enforce ACS standard formatting for immediate publication readiness.

## 5. Next Steps (Cycle 3)
*   Translate this specification into Python code (`ipywidgets`).
*   Implement `traitlets` for the MVC architecture.
*   Run the `anti_spoof_linter.py` on the resulting GUI code.
