# CoChem-BASE: Master GUI Integration & Jupyter Deprecation
**Date:** 2026-08-07

This document formally details the integration of the CoChem GUI (now renamed to **CoChem Studio**) natively into the `CoChem-BASE` module, and the deprecation of the legacy Jupyter notebook entry point.

## 1. Directory Restructuring
The previously isolated `CoChem-GUI` repository has been fully absorbed into `CoChem-BASE` under the directory:
`/CoChem-BASE/CoChem-Studio/`

This ensures that the presentation tier (the React UI) and the orchestration tier (FastAPI/ZeroMQ) share the exact same repository lifecycle and continuous integration pipeline.

## 2. Deprecation of `Start-Here.ipynb`
Historically, users initiated the CoChem pipeline by opening `Start-Here.ipynb` and executing sequential Python cells. 
This notebook is hereby **deprecated** as the primary user interface.
* **New Status:** The Jupyter notebook is now classified as a "Legacy Debugging Interface", strictly reserved for developers testing low-level ZeroMQ payloads without booting the full GUI.
* **New Master Entry Point:** Users must now execute the compiled `CoChem_Studio.exe` (the Electron wrapper).

## 3. How the `.exe` Replaces the Notebook
The `Start-Here.ipynb` notebook previously handled two things: defining the workflow and triggering `BASE`.
The `CoChem_Studio.exe` replaces this via the following architecture:
1. **Background Bootstrapping:** When the student launches the `.exe`, the `python_bundler.js` within Electron silently spawns the local `BASE` FastAPI server in the background.
2. **Visual Workflow Construction:** Instead of typing Python dictionaries in Jupyter, the student uses the `VisualNodeEditor` or the conversational UI in the React frontend.
3. **Payload Dispatch:** When the student clicks "Execute", the React frontend sends an HTTP POST to the local FastAPI server, which in turn acts exactly like the old Jupyter cell—dispatching the HDF5 tensor via ZeroMQ to the `NODE` cluster.
