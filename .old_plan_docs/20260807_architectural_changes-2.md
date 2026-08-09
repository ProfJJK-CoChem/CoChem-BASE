# CoChem-BASE: Master Orchestration Architecture (Extended)
**Date:** 2026-08-07
**Target:** Integration of BENCH, KINETIC, LUMOS, NODE, PULSE, SHIFT

This document outlines the radical architectural changes required within `CoChem-BASE` to support the 6 extended modules. `BASE` is no longer a simple sequential router; it must evolve into a **Massively Distributed HPC Orchestrator**. It governs complex data dependencies, hardware constraints, and the ultra-rigorous physical principles detailed in `Improvements_MethMatrix-LAM-2.md`.

---

## 1. ZeroMQ Asynchronous Message Routing (via NODE)
**The Problem:** `BASE` traditionally executed `subprocess.run()` calls to local ORCA binaries. This architecture is incapable of handling massive multi-node workloads. If `BASE` blocks the main thread waiting for a 3-day CCSD(T) calculation, the Jupyter UI freezes.
**The Solution:**
- `BASE` must entirely relinquish local ORCA subprocess execution.
- All heavy quantum chemistry (DFT, CCSD, MACE, JAX) must be routed through `CoChem-NODE`.
- `BASE` will initialize a **ZeroMQ Asynchronous Message Broker**. It will send JSON payloads to NODE containing the molecular graph, the target module, and the time-tier limits.
- `BASE` will maintain a non-blocking listener in a background thread that ingests Slurm queue states (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) broadcasted back by NODE.

## 2. Expanded `cochem_state.h5` Schema (The Master Tensor)
**The Problem:** The extended modules generate massive amounts of multi-dimensional data. Passing this data between modules via `.txt` or `.json` files will cause severe I/O bottlenecks and RAM crashes (e.g., streaming 10,000 Wigner trajectories or 500 NTO cube files).
**The Solution:**
`BASE` must enforce a rigid, hierarchical Parallel HDF5 (pHDF5) schema capable of handling GPUDirect Storage:
- `/base/system_config`: Global configuration, charge, multiplicity, and Time-Tier matrix.
- `/topos/mace_ensemble`: Relaxed ground-state geometries and Hessian matrices.
- `/kinetic/aimd_trajectory`: A $T \times N \times 3$ tensor containing Nose-Hoover thermal trajectories.
- `/pulse/wigner_swarm`: A massive $M \times T \times N \times 3$ tensor tracking hundreds of concurrent FSSH trajectories.
- `/lumos/nto_cubes`: Memory-mapped scalar arrays holding electron/hole volumetric densities.
- `/shift/nmr_tensors`: $100 \times N \times 3 \times 3$ matrices containing the GIAO shieldings across the AIMD frames.

## 3. Dynamic Module Triggers & Chaining
**The Problem:** `BASE` must logically deduce *when* to call the extended modules based on the user's abstracted UI requests.
**The Solution:**
`BASE` must implement a deterministic routing tree:
- **Thermochemistry & CBS Request $\rightarrow$ BENCH:** If the user demands ultimate thermodynamic precision (Time-Tiers 7-10), BASE bypasses standard DFT and routes to BENCH for DLPNO-CCSD(T)-F12.
- **Reaction Pathway Request $\rightarrow$ KINETIC:** If multiple SMILES are provided (Reactants/Products), BASE triggers KINETIC's JAX-accelerated CI-NEB.
- **Spectroscopy (UV-Vis) Request $\rightarrow$ LUMOS:** Triggers Tamm-Dancoff TD-DFT or STEOM-CCSD depending on the Time-Tier.
- **Conical Intersection Flag $\rightarrow$ PULSE:** If LUMOS detects an $S_1 - S_0$ energy gap $<0.2$ eV during relaxation, BASE autonomously halts LUMOS and triggers PULSE for FSSH non-adiabatic wavepacket dynamics.
- **Spectroscopy (NMR) Request $\rightarrow$ SHIFT:** BASE triggers SHIFT, but must *first* autonomous chain KINETIC to generate a 298 K AIMD trajectory before calculating the 100+ GIAO tensors.

## 4. Hardware-Aware Routing Constraints
**The Problem:** Different modules require drastically different HPC architectures.
**The Solution:**
`BASE` must explicitly tag payloads sent to `NODE` with hardware requirements:
- **Tag `[CPU_FAT]`:** Enforced for `BENCH` (CCSD integrals) and `SHIFT` (GIAO). Requires nodes with >1TB RAM.
- **Tag `[GPU_MAX]`:** Enforced for `TOPOS` (MACE AI) and `KINETIC` (JAX CI-NEB). Requires A100/H100 NVLink nodes.
- **Tag `[CPU_DIST]`:** Enforced for `PULSE` (FSSH Swarm). Embarrassingly parallel, dispatched across hundreds of standard CPU nodes.

## 5. Expansion of the 10-Tier Temporal Matrix
**The Problem:** The extended physics (e.g., STEOM-CCSD) violates the temporal limits established for the core modules.
**The Solution:**
`BASE` must hard-code methodological cutoffs into the execution logic:
- **Tiers 1-4 (Minutes to Hours):** Semi-empirical (xTB), standard DFT (r2SCAN-3c), sTDA.
- **Tiers 5-7 (Hours to Days):** Double-hybrid DFT, RIJCOSX acceleration, TD-DFT, standard AIMD.
- **Tiers 8-10 (Days to Weeks):** DLPNO-CCSD(T)-F12 (BENCH), STEOM-CCSD (LUMOS), Wigner-sampled FSSH (PULSE).
`BASE` must actively intercept and downgrade user commands (e.g., throwing a UI Warning if the user requests STEOM-CCSD on Tier 3).

---
**Next Step for Implementation:** This document establishes the strict routing, triggering, and hardware allocation logic. The next required step is to generate the `20260807_workflow-2.md` document to chronologically trace a complete execution payload from the User UI, through the BASE orchestrator, out to the extended modules via NODE, and back into SCRIBE.


## 6. The GUI Presentation Tier (CoChem Studio)
**Update (2026-08-07):** The CoChem pipeline is no longer driven by the `Start-Here.ipynb` notebook. `CoChem-BASE` now natively hosts the `CoChem-Studio` Electron desktop application. The `.exe` acts as the master entry point, internally launching the BASE ZeroMQ router and replacing all Jupyter-based user interaction with a premium Glassmorphism React interface.
