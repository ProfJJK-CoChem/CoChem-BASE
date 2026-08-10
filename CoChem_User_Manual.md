# CoChem v4 Master User Manual
**Version 2026.4 — Method Matrix v4 Architecture & High-Resolution Spectroscopic Guidelines**

---

## Table of Contents

- [PREFACE: THE METHOD MATRIX V4 DISCIPLINE](#preface-the-method-matrix-v4-discipline)
  - [Foreword & Ecosystem Philosophy](#foreword--ecosystem-philosophy)
  - [Detailed Catalog of the 15 Core Modules](#detailed-catalog-of-the-15-core-modules)
  - [Inter-Module Data Flow & QCSchema Specification](#inter-module-data-flow--qcschema-specification)
  - [The Method Matrix v4 Standards & Provenance Discipline](#the-method-matrix-v4-standards--provenance-discipline)
  - [How to Cite CoChem & Automated Citation Generation](#how-to-cite-cochem--automated-citation-generation)
- [CHAPTER 1: QUICKSTART, METHOD MATRIX TIERING & SYSTEM ARCHITECTURE](#chapter-1-quickstart-method-matrix-tiering--system-architecture)
  - [1.1 The v4 Tier-Based Routing System & Wall-Clock Budgets](#11-the-v4-tier-based-routing-system--wall-clock-budgets)
  - [1.2 Product Classes A, B, C & Target Accuracy Definitions](#12-product-classes-a-b-c--target-accuracy-definitions)
  - [1.3 Method Matrix Routing Decision Tree](#13-method-matrix-routing-decision-tree)
  - [1.4 Hardware Routing & Modern GPU Acceleration Reality](#14-hardware-routing--modern-gpu-acceleration-reality)
  - [1.5 System Deployment Models, Licensing & Cloud Limits](#15-system-deployment-models-licensing--cloud-limits)
  - [1.6 CoChem-DOCK: Telemetry, WebSockets & Decimated Array Streaming](#16-cochem-dock-telemetry-websockets--decimated-array-streaming)
- [CHAPTER 2: MOLECULAR INGESTION, TRIAGE & PROVENANCE (CoChem-MInt)](#chapter-2-molecular-ingestion-triage--provenance-cochem-mint)
  - [2.1 The Unified Ingestion Dashboard & Input Parsing](#21-the-unified-ingestion-dashboard--input-parsing)
  - [2.2 Sandboxed Fast Triage & The Eckart Coordinate Frame](#22-sandboxed-fast-triage--the-eckart-coordinate-frame)
  - [2.3 Physics Variable Setup & Spend Priority Hierarchy](#23-physics-variable-setup--spend-priority-hierarchy)
  - [2.4 Provenance Initialization & Semantic Audit Ledger](#24-provenance-initialization--semantic-audit-ledger)
- [CHAPTER 3: TOPOLOGICAL DISCOVERY, DEDUPLICATION & PES (TOPOS, SCAN, TORQ)](#chapter-3-topological-discovery-deduplication--pes-topos-scan-torq)
  - [3.1 Conformer & Isomer Exploration (T1 Routing)](#31-conformer--isomer-exploration-t1-routing)
  - [3.2 Two-Stage Deduplication Protocol: GOAT Primary + CREST Cross-Check](#32-two-stage-deduplication-protocol-goat-primary--crest-cross-check)
  - [3.3 MLFF-GOAT Integration Recipe & Boundary Constraints](#33-mlff-goat-integration-recipe--boundary-constraints)
  - [3.4 Geometry Optimization Preconditioning & Initial Hessians](#34-geometry-optimization-preconditioning--initial-hessians)
  - [3.5 Torsional Discovery & Internal Rotor Mechanics (TORQ)](#35-torsional-discovery--internal-rotor-mechanics-torq)
  - [3.6 Persistent HDF5 Potential Energy Surface Store (`PESStore`)](#36-persistent-hdf5-potential-energy-surface-store-pesstore)
  - [3.7 Active Learning & Dynamic PES Refinement (SCAN)](#37-active-learning--dynamic-pes-refinement-scan)
- [CHAPTER 4: HIGH-PRECISION AB INITIO REFINEMENT (BENCH & CROWN)](#chapter-4-high-precision-ab-initio-refinement-bench--crown)
  - [4.1 Equilibrium ($B_e$) vs Ground-State ($B_0$) Rotational Constants](#41-equilibrium-b_e-vs-ground-state-b_0-rotational-constants)
  - [4.2 Intermolecular Geometry Convergence & Corrected `%geom` Block](#42-intermolecular-geometry-convergence--corrected-geom-block)
  - [4.3 Frozen-Monomer Composite Protocol](#43-frozen-monomer-composite-protocol)
  - [4.4 Basis Set Superposition Error (BSSE) Geometry Corrections](#44-basis-set-superposition-error-bsse-geometry-corrections)
  - [4.5 Frozen-Core Bias & Core-Valence Electron Correlation](#45-frozen-core-bias--core-valence-electron-correlation)
  - [4.6 Quantum Engine Track Division: ORCA vs CFOUR](#46-quantum-engine-track-division-orca-vs-cfour)
  - [4.7 Multireference Diagnostics & Macroscopic Thermal Ensembles](#47-multireference-diagnostics--macroscopic-thermal-ensembles)
- [CHAPTER 5: VIBRATIONAL AVERAGING, SECONDARY OBSERVABLES & FITTING (SpycFit & MUSE)](#chapter-5-vibrational-averaging-secondary-observables--fitting-spycfit--muse)
  - [5.1 Quantum Vibrational Averaging & Jensen's Inequality](#51-quantum-vibrational-averaging--jensens-inequality)
  - [5.2 Corrected Anharmonic VPT2 Displacement Counts](#52-corrected-anharmonic-vpt2-displacement-counts)
  - [5.3 Force-Field Recycling & Isotopologue Structural Fitting](#53-force-field-recycling--isotopologue-structural-fitting)
  - [5.4 Secondary Spectroscopic Observables](#54-secondary-spectroscopic-observables)
  - [5.5 Permutation-Inversion Molecular Symmetry Groups](#55-permutation-inversion-molecular-symmetry-groups)
  - [5.6 Modern JAX Spectroscopy Fitting Engine & Pickett Interoperability](#56-modern-jax-spectroscopy-fitting-engine--pickett-interoperability)
- [CHAPTER 6: CONCURRENCY, STATE-CHAINING, TELEMETRY & DISPATCH (TORQ, NODE, SCRIBE, ORACLE)](#chapter-6-concurrency-state-chaining-telemetry--dispatch-torq-node-scribe-oracle)
  - [6.1 Heterogeneous Concurrency & Scout-and-Anchor Pipeline](#61-heterogeneous-concurrency--scout-and-anchor-pipeline)
  - [6.2 State Reuse & Canonical 11-Arrow Chaining Pipeline](#62-state-reuse--canonical-11-arrow-chaining-pipeline)
  - [6.3 Remote SLURM Cluster Dispatch (CoChem-NODE)](#63-remote-slurm-cluster-dispatch-cochem-node)
  - [6.4 Localized Retrieval-Augmented RAG Diagnostics (CoChem-ORACLE)](#64-localized-retrieval-augmented-rag-diagnostics-cochem-oracle)
  - [6.5 Cryptographic FAIR Data Synthesis & QCSchema Logging (CoChem-SCRIBE)](#65-cryptographic-fair-data-synthesis--qcschema-logging-cochem-scribe)
- [CHAPTER 7: EDUCATIONAL & PEDAGOGICAL IMPLEMENTATIONS](#chapter-7-educational--pedagogical-implementations)
  - [7.1 Foundational Concept Training (CoChem-PLAY1 & PLAY2)](#71-foundational-concept-training-cochem-play1--play2)
  - [7.2 The Gamified Curriculum (Academic Elo Tiers)](#72-the-gamified-curriculum-academic-elo-tiers)
  - [7.3 Undergraduate Curriculum Mapping (CoChem-CURE)](#73-undergraduate-curriculum-mapping-cochem-cure)
  - [7.4 Capstone Grading & Telemetry (CoChem-LABS & EVAL)](#74-capstone-grading--telemetry-cochem-labs--eval)
  - [7.5 The Principal Investigator (PI) Draft Board](#75-the-principal-investigator-pi-draft-board)
  - [7.6 Teaching Tier Infrastructure Limits & Deployment](#76-teaching-tier-infrastructure-limits--deployment)
- [APPENDIX: METHOD MATRIX TIER TABLES & PARETO FRONTIER](#appendix-method-matrix-tier-tables--pareto-frontier)
  - [A.1 Summary Table of Method Matrix Tiers (T1–T10)](#a1-summary-table-of-method-matrix-tiers-t1t10)
  - [A.2 Pareto Frontier & Dominated Execution Pathways](#a2-pareto-frontier--dominated-execution-pathways)
  - [A.3 Silent Failure Modes & Rejection Triggers](#a3-silent-failure-modes--rejection-triggers)
  - [A.4 Standing Rules & Mandatory Discipline Checklist](#a4-standing-rules--mandatory-discipline-checklist)

---

# PREFACE: THE METHOD MATRIX V4 DISCIPLINE

### Foreword & Ecosystem Philosophy
Welcome to CoChem Version 2026.4.

High-resolution molecular spectroscopy demands an unprecedented level of computational precision. Assigning a complex broadband rotational spectrum obtained via Chirped-Pulse Fourier Transform Microwave (CP-FTMW) spectroscopy requires predicting rotational constants ($A_0, B_0, C_0$) to within fractions of a percent, accurately forecasting dipole moment components ($\mu_a, \mu_b, \mu_c$), and calculating nuclear quadrupole coupling tensors ($\chi_{\alpha\beta}$) or centrifugal distortion parameters.

Historically, computational chemistry pipelines have suffered from an arbitrary selection of theoretical methods—often mixing electronic structure algorithms, basis sets, and convergence thresholds without rigorous quantitative error propagation. A user might run a default geometry optimization using Density Functional Theory (DFT) with loose criteria, invert the resulting moments of inertia, and wonder why the predicted spectrum is offset by hundreds of megahertz from experimental lines.

The **CoChem Ecosystem** unifies molecular ingestion, topological discovery, high-level *ab initio* refinement, vibrational averaging, and spectroscopic line-fitting into a hardware-aware, mathematically validated framework. CoChem v4 incorporates the **20260809 Method Matrix Specification** [`§Preamble, §8.2–§8.4`], establishing an uncompromising standard of scientific defensibility over heuristic convenience.

The Prime Directive of CoChem v4 remains: **Scientific Defensibility over Heuristic Convenience.** Where legacy pipelines silently deleted structural isomers using arbitrary spatial cutoffs, CoChem deploys two-stage deduplication (`GOAT` + `CREST`) [`§9B.1`]. Where standard scripts crashed near 180° linear angle singularities, CoChem deploys Cartesian projection protections [`§2.3, §4.5`]. Every assumption is tagged with provenance metadata, and every deliverable is formatted for FAIR-compliant publication [`§12.5`, `§20.2`].

---

### Detailed Catalog of the 15 Core Modules
The CoChem v4 suite is composed of 15 decoupled, interoperable modules spanning ingestion, exploration, refinement, fitting, and telemetry [`§1.1, §1.2, §2.1`]:

```
+-----------------------------------------------------------------------------------+
|                           THE 15 CORE COCHEM V4 MODULES                           |
+----+---------------+-----------------------------------+--------------------------+
| #  | Module Name   | Primary Domain / Responsibility   | Core Technology / Engine |
+----+---------------+-----------------------------------+--------------------------+
| 1  | CoChem-UNITY  | Installation & GUI Dashboard      | React / FastAPI          |
| 2  | CoChem-MInt   | Ingestion, Sanitization & Triage  | RDKit / GFN2-xTB / UFF   |
| 3  | CoChem-TOPOS  | Global Conformer Discovery        | ORCA GOAT / CREST NCI    |
| 4  | CoChem-TORQ   | Hindered Internal Rotation        | 1D Relaxed Scans / Pitzer|
| 5  | CoChem-SCAN   | PES Mapping & Active Learning     | MACE-OFF / QBC Sampling  |
| 6  | CoChem-BENCH  | Ab Initio Thermochemical Limit    | junChS / DLPNO-CCSD(T)   |
| 7  | CoChem-CROWN  | Non-Covalent Dimer Composites     | Frozen-Monomer Protocol  |
| 8  | CoChem-SpycFit| Spectroscopic Fitting & Autodiff  | JAX / Pickett pyckett    |
| 9  | CoChem-MUSE   | Automated Mass Substitution       | Kraitchman / Costain r_m |
| 10 | CoChem-LUMOS  | Photophysics & Radical Cleavage   | EOM-CCSD / Spin Contam   |
| 11 | CoChem-KINETIC| Master Equation & VTST Rates      | Variational TST / LZ Hop |
| 12 | CoChem-PULSE  | Non-Adiabatic Dynamics            | Surface Hopping / Wigner |
| 13 | CoChem-NODE   | Remote HPC Workload Scheduling    | SLURM / OpenMPI          |
| 14 | CoChem-ORACLE | LLM Retrieval-Augmented RAG       | llama.cpp / ChromaDB     |
| 15 | CoChem-SCRIBE | Provenance & FAIR Export          | QCSchema / Jinja2 LaTeX  |
+----+---------------+-----------------------------------+--------------------------+
```

Each module maintains a dedicated execution scope and API contract:
1. **CoChem-UNITY**: Serves as the centralized launcher and configuration validator (`cochem_system_config.json`). Enforces Pydantic schema verification during startup [`§8.0, §12.6, §18`]. Maintains active configuration states for local and cloud environments.
2. **CoChem-MInt**: Sanitizes incoming molecular graphs, centers atomic coordinates on the Center of Mass, and aligns structures to the Eckart coordinate frame [`§2.3, §5.1`]. Detects bad valencies and prevents steric collisions.
3. **CoChem-TOPOS**: Orchestrates global conformer exploration via ORCA GOAT and CREST non-covalent searching, enforcing two-stage deduplication [`§9B.1`]. Merges structural candidates from multiple search engines.
4. **CoChem-TORQ**: Isolates flexible torsions, evaluates internal rotor reduced moments $F(\phi)$, and outputs 1D potential curves for $V_3/V_6$ barrier fitting [`§6.7`]. Evaluates effective moments of inertia along scanning trajectories.
5. **CoChem-SCAN**: Generates multi-dimensional potential energy surfaces, executing active-learning delta learning ($\Delta$-learning) with QBC uncertainty sampling [`§13.2`]. Refines high-dimensional surfaces with minimal electronic structure calls.
6. **CoChem-BENCH**: Executes gold-standard composite electronic structure calculations (junChS, CBS+CV, DLPNO-CCSD(T)) to deliver equilibrium geometries ($r_e$) and $B_e$ [`§13.3`]. Implements high-precision CBS extrapolations.
7. **CoChem-CROWN**: Constructs counterpoise-corrected composite calculations for weak van der Waals dimers using the Frozen-Monomer Composite Protocol [`§9A.4`]. Eliminates artificial covalent bond distortion.
8. **CoChem-SpycFit**: High-speed spectroscopic line fitter operating on JAX automatic differentiation, featuring out-of-core PyArrow Parquet transition logging [`§5.6`]. Calculates exact analytical Jacobians for Watson Hamiltonians.
9. **CoChem-MUSE**: Automated isotopologue generator managing mass-substitution calculations, Kraitchman coordinate transformations ($r_s$), and Costain mass scaling ($r_m^{(2)}$) [`§5.3`, `§5.6`]. Automates isotopic spectrum generation.
10. **CoChem-LUMOS**: Simulates radical photophysics, open-shell electronic transitions, spin contamination ($\langle S^2 \rangle$), and excited state decay vectors [`§14.5`]. Evaluates non-adiabatic state couplings.
11. **CoChem-KINETIC**: Solves the Master Equation for chemical reaction networks using Variational Transition State Theory (VTST) and Landau-Zener surface hop probabilities [`§5.8`]. Simulates complex chemical decay kinetics.
12. **CoChem-PULSE**: Propagates non-adiabatic molecular dynamics across multi-surface crossings using initial Wigner phase-space sampling [`§5.5`]. Generates quantum trajectory ensembles.
13. **CoChem-NODE**: Translates pipeline execution state into SLURM job submission scripts (`.sbatch`), managing core pinning and asynchronous job adoption [`§6.1`]. Monitors cluster node health and core allocation.
14. **CoChem-ORACLE**: Operates a local RAG agent backed by `llama.cpp` and a local ChromaDB vector vault for contextual quantum chemistry error diagnosis [`§6.2`, `§6.4`]. Provides offline diagnostic recommendations.
15. **CoChem-SCRIBE**: Formats output datasets into FAIR-compliant packages, generating QCSchema JSON, Jinja2 LaTeX methodology text, and BibTeX citation logs [`§6.3`, `§20.2`]. Produces publication-ready reporting packages.

### Inter-Module Data Flow & QCSchema Specification
The 15 modules communicate through explicit JSON-RPC and REST endpoints managed by the FastAPI server in UNITY. Inter-module data flow strictly follows the QCSchema standard (`qcjson`). When BENCH finishes a DLPNO-CCSD(T) single point, it emits a QCSchema `AtomicResult` object containing the total electronic energy, gradient array, and wave-function diagnostic scalars. SCRIBE listens on the event bus, writing `AtomicResult` objects directly into the active HDF5 store (`PESStore`) [`§8C.2`].

```json
{
  "schema_name": "qcschema_output",
  "schema_version": 1,
  "molecule": {
    "geometry": [0.0, 0.0, 0.0, 0.0, 0.0, 1.8],
    "symbols": ["O", "H"],
    "molecular_charge": 0,
    "molecular_multiplicity": 2
  },
  "driver": "energy",
  "model": {"method": "DLPNO-CCSD(T)", "basis": "def2-TZVPP"},
  "return_result": -75.38219482104,
  "success": true
}
```

---

### The Method Matrix v4 Standards & Provenance Discipline
To ensure absolute scientific rigor and eliminate unverified claims, CoChem v4 mandates a strict **Provenance Discipline** [`§12.5`]. Every quantitative value, error bound, benchmark accuracy, scaling metric, or hardware speedup cited within this manual and logged by the software engines must carry an explicit provenance tag:

1. **`[M]` — Measured**: Direct experimental measurement or authoritative benchmark dataset published in peer-reviewed literature (e.g., CCSD(T)/CBS benchmarks, NIST high-resolution spectroscopy, or physical hardware measurements).
2. **`[D]` — Derived**: Result obtained through exact mathematical deduction, closed-form equation, or formal scaling law from established physical constants or measured quantities (e.g., transformation of inertia tensors, analytical displacement counts, or linear scaling arithmetic).
3. **`[E]` — Estimated**: Expert estimate, heuristic extrapolation, or empirical rule-of-thumb based on domain knowledge.

#### Mandatory Provenance Enforcement Rule (Rule 7) [`§12.5`]
> **Standing Rule**: *No `[D]` (derived) or `[E]` (estimated) value may serve as the sole justification for a hardware exclusion rule, an architectural routing gate, or an accuracy guarantee.* Where a `[D]` or `[E]` tag is assigned, local measurement `[M]` is required before gating production execution.

This rule eliminates legacy fallacies where theoretical hardware limits were used to arbitrarily disable hardware features (such as excluding GPU acceleration based purely on theoretical peak double-precision floating-point operations).

---

### How to Cite CoChem & Automated Citation Generation
CoChem orchestrates multiple theoretical chemistry packages (including ORCA, CFOUR, PySCF, Psi4, xtb, MACE-OFF, AIMNet2, and JAX). Proper attribution to the underlying theoretical methods and software packages is mandatory [`§11.1`].

During execution, CoChem's telemetry module (`CoChem-SCRIBE`) automatically generates a BibTeX file (`cochem_references.bib`) customized to the exact execution path and algorithms invoked during your calculation.

```bibtex
@article{CoChem2026,
  author = {CoChem v4 Development Team},
  title = {The CoChem v4 Method Matrix Framework for High-Resolution Molecular Spectroscopy},
  journal = {Journal of Chemical Physics},
  year = {2026},
  volume = {164},
  pages = {084101},
  doi = {10.1063/5.cochem2026v4}
}
```

---

# CHAPTER 1: QUICKSTART, METHOD MATRIX TIERING & SYSTEM ARCHITECTURE

## 1.1 The v4 Tier-Based Routing System & Wall-Clock Budgets
CoChem v4 replaces all legacy unstructured pipelines with a 10-tier wall-clock budget matrix [`§Quick Start Card`, `§12.1`, `§13.1`]. Rather than specifying arbitrary computational flags, workflows are routed based on an explicit target wall-clock time limit across ten standard tiers:

$$\text{Budgets} \in \{ \mathbf{10s},\, \mathbf{1min},\, \mathbf{30min},\, \mathbf{1h},\, \mathbf{3h},\, \mathbf{12h},\, \mathbf{1d},\, \mathbf{3d},\, \mathbf{1w},\, \mathbf{1mo} \}$$

These wall-clock budgets govern ten distinct operational tiers ($T1$ through $T10$) [`§13`, `§14`]:
- **T1 (Conformer & Isomer Search)** [`§13.1`]: Global topological exploration, conformational sampling, and isomer deduplication.
- **T2 (Intermolecular Potential Surfaces & Active Learning)** [`§13.2`]: Mapping multi-dimensional potential energy surfaces (PES) via active-learning delta learning ($\Delta$-learning).
- **T3 (Equilibrium Geometry & $B_e$)** [`§13.3`]: Determination of the Born-Oppenheimer equilibrium geometry ($r_e$) and equilibrium rotational constants ($B_e$).
- **T4 (Vibrational Averaging & $B_0$)** [`§13.4`]: Computation of zero-point vibrational corrections ($\Delta B_{\text{vib}}$) to yield ground-state rotational constants ($B_0 = B_e + \Delta B_{\text{vib}}$).
- **T5 (Interaction Energies)** [`§13.5`]: Counterpoise-corrected binding energies ($D_0, D_e$) and thermochemical limits.
- **T6 (Secondary Spectroscopic Observables)** [`§14.1`]: Dipole moments, nuclear quadrupole coupling tensors ($\chi_{\alpha\beta}$), planar moments ($P_{\alpha\alpha}$), and inertial defects ($\Delta$).
- **T7 (Internal Rotation & Tunnelling)** [`§14.2`]: Hindered rotor barriers ($V_3, V_6$) and non-rigid inversion/tunnelling splittings.
- **T8 (Vibrational Spectra - IR/THz)** [`§14.3`]: Harmonic and anharmonic (VPT2) infrared frequencies and intensities.
- **T9 (Raman Spectra)** [`§14.4`]: Polarizability derivatives and Raman activity spectra.
- **T10 (NMR, UV-Vis & MS)** [`§14.5`]: Magnetic shielding tensors, electronic transitions, and mass spectrometry fragmentation.

### Comprehensive Specification of Operational Tiers (T1–T10)

#### Tier T1: Conformer & Isomer Search [`§13.1`]
Conformer exploration aims to locate all low-energy spatial arrangements within a target energy window $\Delta E \le 3.0\text{ kcal/mol}$.
- `T1-10s`: Hand-enumerated binding topologies (3–9 initial seeds) optimized via `! XTB2 TightOpt` [`§13.1`]. Designed for rapid interactive triage.
- `T1-1min`: ORCA GOAT fast stochastic search using `! GOAT XTB2 PAL8` [`§13.1`]. Provides initial topological sampling.
- `T1-30min`: MLFF-accelerated GOAT using `! GOAT-EXPLORE ExtOpt` backed by an active `oet_server` daemon [`§9B.4`, `§13.1`].
- `T1-1h`: CREST non-covalent search: `crest --nci --gfn2 --ewin 12 --nocross --noreftopo` [`§9B.2`, `§13.1`]. Guarantees non-covalent dimer protection.
- `T1-3h`: Multi-engine union merge $\rightarrow$ CREST screening $\rightarrow$ r²SCAN-3c re-optimization $\rightarrow$ CREGEN deduplication (`--bthr 0.001`) [`§9B.3`, `§13.1`].
- `T1-12h`: `! GOAT r2SCAN-3c` global search over leading isomeric basins [`§13.1`]. Highly reliable for complex organic systems.
- `T1-1d`: `! GOAT-ENTROPY XTB2` stochastic exploration + CREST conformational entropy evaluation [`§13.1`]. Includes thermal free energy bounds.
- `T1-3d`: High-level DFT re-optimization of Stage-B survivors using $\omega\text{B97X-V/def2-TZVPP}$ [`§13.1`]. Isolates subtle hydrogen-bonding isomers.
- `T1-1w`: Fine-tune MACE or AIMNet2 MLFF models on 100–500 DFT points and re-run GOAT+CREST [`§13.1`]. Retrains MLFF on local PES.
- `T1-1mo`: Exhaustive union search over multi-component macrocyclic or biomolecular complex landscapes [`§13.1`].

#### Tier T2: Intermolecular Potential Energy Surfaces & Active Learning [`§13.2`]
Potential surface generation constructs high-dimensional energy surfaces for variational nuclear motion solvers.
- `T2-1h`: 2D relaxed grid scan (960 points at $\omega\text{B97X-V/def2-TZVPP}$) [`§13.2`]. Maps major dissociation coordinates.
- `T2-12h`: Active learning $\Delta$-learning pipeline (2,000 DFT points + 300–800 CCSD(T)-F12 points yielding $\text{RMS} < 5\text{ cm}^{-1}$) [`§13.2`].
- `T2-1d`: Committee-uncertainty active learning sampling over 6D intermolecular space [`§13.2`]. Selects points with maximum variance.
- `T2-3d`: 3D rigid-monomer Discrete Variable Representation (DVR) via matrix-free Lanczos diagonalization [`§13.2`]. Computes bound state energies.
- `T2-1w`: Full 6D rigid-monomer variational nuclear motion treatment on $\Delta$-learned surface [`§13.2`].
- `T2-1mo`: Full-dimensional flexible-monomer surface generation ($9.1\text{ cm}^{-1}$ RMSE on water dimer) [`§13.2`]. Benchmark spectroscopic surface.

#### Tier T3: Equilibrium Geometry & $B_e$ [`§13.3`]
Equilibrium geometry optimization seeks the Born-Oppenheimer minimum ($r_e$).
- `T3O-1min` (Recipe R1): Frozen monomers + r²SCAN-3c intermolecular optimization [`§9A.4`, `§13.3`]. Extremely fast estimate.
- `T3O-3h` (Recipe R2): Frozen CCSD(T) monomers + $\omega\text{B97M-V/def2-QZVPP}$ + 3-leg CP + VPT2 ($B_e \pm 0.4\text{ to } 1.5\%$, $A < 0.2\%$) [`§9A.5`, `§13.3`].
- `T3O-12h` (Recipe R4 - junChS Composite): CBS+CV composite delivering $B_e \text{ MAE } = 0.13\%$ for $\le 16$ atom benchmark set [M]. **Best de novo accuracy-per-core-hour row in Method Matrix** [`§13.3`].
- `T3C-3h` / `T3C-12h` / `T3C-1d`: CFOUR CCSD(T) optimizations at cc-pVTZ ($0.90\%\text{ MAE}$), cc-pVQZ ($0.43\%\text{ MAE}$), and cc-pCVQZ all-electron ($0.164\%\text{ MAE}$) [`§13.3`].

#### Tier T4: Vibrational Averaging & Ground-State $B_0$ [`§13.4`]
Vibrational averaging computes zero-point corrections $\Delta B_{\text{vib}}$ to predict experimental ground-state rotational constants $B_0$.
- `T4O-1min` (Recipe R6 - Product B): Semi-experimental template scaling (scale theoretical geometry to experimental parent, substitute masses) $\rightarrow \mathbf{B_0 \pm 0.03\% \text{ to } 0.06\% \text{ [M]}}$ (highest accuracy cell in framework) [`§1.2`, `§13.4`].
- `T4O-30min`: Analytical DFT Hessian $\rightarrow \Delta B_{\text{vib}}$ ($\pm 0.1\%$ [D] of $B_0$ at 20% [E] force constant error) [`§13.4`].
- `T4O-1h`: DFT VPT2 anharmonic force field (49 analytic Hessians at $N=10$) $\rightarrow B_0 \pm 0.3\text{ to } 0.5\%$ semi-rigid [`§13.4`].
- `T4O-12h`: Mass-weighted isotopologue loop from single force field (`orca_vib` or CFOUR `ISOMASS` + `xjoda`) $\rightarrow \mathbf{6\text{x to } 15\text{x} \text{ compute savings [D]}}$ [`§6.10`, `§8B.4`, `§13.4`].
- `T4C-12h`: CFOUR `ANHARM=VPT2` at cc-pVTZ $\rightarrow$ fundamentals, $\alpha_i^B$, quartic and sextic centrifugal distortion ($3\text{ to } 4\%$ error on oxirane [M]) [`§13.4`].

---

## 1.2 Product Classes A, B, C & Target Accuracy Definitions
To prevent unrealistic expectations and optimize resource allocation, CoChem v4 categorizes all computational targets into three explicit **Product Classes** [`§1.1`–`§1.5`]:

```
+-----------------------------------------------------------------------------------+
|                            COCHEM V4 PRODUCT CLASSES                              |
+------------------+----------------------------------+-----------------------------+
| Product Class    | Prerequisite                     | Achievable $B_0$ Accuracy    |
+------------------+----------------------------------+-----------------------------+
| Class A (de novo)| Zero experimental data           | +/- 0.3 - 0.5% [D] (semi-rigid) |
|                  |                                  | +/- 1.0 - 2.0% [D] (floppy)     |
+------------------+----------------------------------+-----------------------------+
| Class B (Template| 1 measured parent isotopologue   | <= 0.1% (typically 0.03%    |
|   / Semi-exp)    | or structural analogue           |  to 0.06% [M])              |
+------------------+----------------------------------+-----------------------------+
| Class C (Diffs)  | Measured reference state         | 0.02% - 0.1% [M]             |
|                  | (Isotopologues, conformers, etc.)|                             |
+------------------+----------------------------------+-----------------------------+
```

### Class A: Absolute de novo Predictions [`§1.1`]
- **Preconditions**: No prior experimental microwave data exists for the target complex or its fragments.
- **Defensible Accuracy**: For rigid or semi-rigid organic molecules, high-level composite methods ($T3O\text{-}12h$ junChS) achieve **$\pm 0.3\%$ to $\pm 0.5\%$ accuracy in $B_0$** [`§1.1`, `§13.3`]. For weakly bound or floppy complexes, accuracy is limited to **$\pm 1.0\%$ to $\pm 2.0\%$** due to large-amplitude zero-point motion.
- **Spectroscopic Search Window**: At a center frequency of $12\text{ GHz}$, a $\pm 0.3\% \text{ to } \pm 2.0\%$ error corresponds to a broad search window of **$\pm 36\text{ MHz}$ to $\pm 240\text{ MHz}$**. Assignments require wide-band AUTOFIT pattern matching [`§1.3`].
- **Fundamental Rule**: *No quantum chemistry protocol can claim sub-0.1% de novo accuracy for absolute ground-state rotational constants $B_0$ of floppy van der Waals complexes* [`§1.1`]. Claiming sub-0.1% de novo accuracy is physically unviable because zero-point vibrational contributions ($\Delta B_{\text{vib}}$) carry intrinsic 10–20% [E] force-field uncertainties.

### Class B: Semi-Experimental & Template-Anchored Predictions [`§1.2`]
- **Preconditions**: Experimental rotational constants exist for at least one parent isotopologue or a closely related structural analogue.
- **Defensible Accuracy**: By anchoring the theoretical structure to the experimental parent constants and calculating only the differential shifts (mass substitution or structural modification), Class B achieves **$\le 0.1\%$ accuracy in $B_0$ (typically $0.03\%$ to $0.06\%$ [M])** [`§1.2`].
- **Spectroscopic Search Window**: At $12\text{ GHz}$, a $\pm 0.05\%$ error yields a narrow search window of **$\pm 4\text{ MHz}$ to $\pm 12\text{ MHz}$**, allowing immediate assignment.

### Class C: Differential Observables [`§1.4`]
- **Preconditions**: Reference measurements exist within the same operational system.
- **Defensible Accuracy**: Predicts isotopic shifts ($\Delta B = B_{\text{parent}} - B_{\text{iso}}$), conformer energy differences ($\Delta E$), vibrational satellite spacings, or inertial defects ($\Delta$) to within **$0.02\%$ to $0.1\%$** [`§1.4`].

---

## 1.3 Method Matrix Routing Decision Tree
The following decision tree governs workflow selection based on Product Class and available wall-clock budget [`§Quick Start Card`, `§8.5`]:

```
                    +---------------------------------------------------------+
   START  --------->|  Do you have a measured parent isotopologue, or a       |
                    |  structurally analogous measured complex?               |
                    +--------------------+------------------------------------+
                                         |                                    
                                   YES   |   NO                               
                                   +-----+-----+                              
                                   |           |                              
                                   v           v                              
                    +-------------------+     +-------------------------------+
                    |  PRODUCT B / C    |     |  PRODUCT A                    |
                    |  semi-exp /       |     |  absolute de novo             |
                    |  template-anchored|     |                               |
                    |  window: +/-0.05% [M] |     |  window: +/-0.3 - 0.5% [D] (rigid)|
                    |  = +/- 6 MHz [M]  |     |          +/-1.0 - 2.0% [D] (floppy)|
                    |    at 12 GHz      |     |  = +/-36 - 240 MHz [D] at 12 GHz  |
                    +---------+---------+     +---------------+---------------+
                              |                               |               
                              v                               v               
                    +-------------------+     +-------------------------------+
                    | Spend Budget On:  |     | Spend Budget On:              |
                    | 1. Delta B_vib    |     | 1. Geometry (Intermolecular R)|
                    | 2. Isotopic shifts|     | 2. Delta B_vib                |
                    | 3. Dipoles / NQCC |     | 3. Dipole Components          |
                    | Routing: T4O-1min |     | 4. NQCC Tensors               |
                    | (Recipe R6)       |     | Routing: T3O-12h junChS       |
                    +-------------------+     +-------------------------------+
```

---

## 1.4 Hardware Routing & Modern GPU Acceleration Reality
Legacy guidelines in computational chemistry (including CoChem v3) frequently contained an incorrect exclusion: claiming GPUs had "no legitimate role" in electronic structure calculations due to double-precision (FP64) performance limits. CoChem v4 completely overturns this exclusion based on quantitative hardware measurements [`§Preamble`].

### 1.4.1 The Physics of Electron Repulsion Integrals (ERIs) [`§8.2`]
The evaluation of two-electron Repulsion Integrals (ERIs) and density matrix contractions in modern quantum chemistry software (e.g., `gpu4pyscf`, `LibintX`, `Cuentos`) is **memory-bandwidth, register-file, and thread-occupancy bound**, rather than bound by raw FP64 FLOPS [`§8.2`].

Modern NVIDIA GPUs (such as the RTX 3090, RTX 4090, or A100/H100 GPUs) feature massive memory bandwidth ($936\text{ GB/s}$ to $>3.0\text{ TB/s}$ [M]) and thousands of concurrent execution threads. `gpu4pyscf` executes electronic structure algorithms in **full double precision (FP64)** with zero loss of numerical precision, achieving exact parity with CPU calculations [`§8.3`]:
- **Energy Deviation**: $< 10^{-11}\text{ Ha}$ vs CPU PySCF `[M]`.
- **Gradient Deviation**: $< 10^{-7}\text{ Ha/bohr}$ vs CPU PySCF `[M]`.
- **Hessian Deviation**: $< 10^{-6}\text{ Ha/bohr}^2$ vs CPU PySCF `[M]`.

### 1.4.2 System Size Crossover Analysis [`§8.2`]
GPU acceleration exhibits a distinct system-size crossover point driven by hardware occupancy. For small basis set counts, host-to-device kernel launch overhead dominates; for larger basis set counts, GPU parallelism delivers massive acceleration:

```
+-----------------------------------------------------------------------------------+
|                        GPU VS CPU PERFORMANCE CROSSOVER                           |
+------------------+-----------------------+-------------------+--------------------+
| System           | Basis Functions (N)   | RTX 3090 vs 8 P-Cores | A100 vs 32 Xeons  |
+------------------+-----------------------+-------------------+--------------------+
| Water Dimer      | ~ 118 (def2-TZVPP)    | 0.32x (CPU faster)| 0.18x (CPU faster) |
| Water Trimer     | ~ 177 (def2-TZVPP)    | 1.15x (GPU crossover) | 1.37x (GPU faster) |
| Water Decamer    | ~ 590 (def2-TZVPP)    | 6.40x (GPU faster)| 8.03x (GPU faster) |
+------------------+-----------------------+-------------------+--------------------+
```

- **Crossover Gate**: The GPU crossover threshold is quantitatively verified at **$N \approx 150\text{ to } 170$ basis functions against 32 CPU cores [M]** [`§8.2`, `§8.3`]. In strict compliance with Section 12.5 Standing Rule 7, derived estimates ($N \approx 50\text{ to } 90$ basis functions [D] against 8 CPU P-cores) may not serve as the sole gate for routing decisions [`§21.2`]. For 8 P-core workstation routing, direct empirical benchmark measurements [M] must be executed on the target host using the fair-comparison protocol [`§8.4`].
- **Routing Rule**: Workflows default to CPU execution for small systems ($N < 150$ basis functions) unless local measured benchmark data [M] demonstrates GPU speedup on the target hardware [`§8.4`, `§8.5`].

### 1.4.3 Multi-Process Service (MPS) & Concurrency Configuration [`§8.4`]
When executing high-throughput conformer searches (T1) or active-learning potential surface generation (T2) involving small molecular queries, running a single GPU job leaves $>80\%$ of GPU CUDA cores idle.
- CoChem v4 mandates the deployment of **NVIDIA Multi-Process Service (MPS)** [`§8.4`].
- MPS enables multiple client CPU processes to multiplex work onto a single GPU simultaneously.
- Host CPU launch overheads (such as Python thread creation and graph building in PyTorch or MACE) introduce a 57% [M] host-side bottleneck per worker [`§8.4`].
- **Optimal MPS Worker Ceiling**: The optimal GPU concurrency allocation is **2 to 4 workers per GPU**, backed by **1 dedicated CPU P-core per GPU worker** [`§8.4`].

```bash
# MANDATORY MPS DAEMON LAUNCH SCRIPT FOR SETUP 2 WORKSTATIONS (§8.4)
export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps
export CUDA_MPS_LOG_DIRECTORY=/tmp/nvidia-log
nvidia-cuda-mps-control -d

# Set active MPS worker thread allocation
echo "set_default_active_thread_percentage 25" | nvidia-cuda-mps-control
```

### 1.4.4 Fair-Comparison Benchmarking Protocol [`§8.3`]
When benchmarking GPU vs CPU electronic structure engines, all computational parameters must be strictly matched [`§8.3`]:
1. Functional: `B3LYP` (or identical functional).
2. Basis Set: `def2-TZVPP`.
3. Integration Grid: `DEFGRID3` (ORCA) vs `(99, 590)` radial/angular grid (`gpu4pyscf`).
4. SCF Convergence: Strict $10^{-9}\text{ Ha}$ energy tolerance.
5. Density Fitting: Explicit matching of resolution-of-the-identity (`RIJK` in ORCA vs `density_fit()` in `gpu4pyscf`).

---


### 1.4.5 Troubleshooting: Hardware Constraints & TiledArray
To prevent out-of-core swap thrashing on Setup 1 (64GB RAM / 2TB NVMe) workstations during massive MPQC tensor contractions, you must instruct the TiledArray memory governor.
- Set `TA_LIMIT_MEMORY=51GB` (80% of system memory) in `cochem_config.yaml`.
- Set `MAD_NUM_THREADS=8` to match typical Performance (P) core counts and prevent thread contention.

## 1.5 System Deployment Models, Licensing & Cloud Limits
CoChem v4 supports three primary hardware deployment models [`§1.2`, `§8.4b`, `§11`, `§19`]:


### 1.5.1 Deployment Models & Installation Paths
The CoChem v4 backend runs the Valeev Stack (MPQC, TiledArray, MADNESS, Libint).

- **Local/Codespaces:** Execute `docker pull ghcr.io/cochem/mpqc-valeev-backend:latest`
- **HPC (Slurm):** Execute `spack install mpqc +libint +madness`

1. **Model A: GitHub Codespaces & Cloud CI/CD** [`§8.4b`, `§19.1`]: Lightweight cloud container environment. Ideal for triage, didactic instruction, and analytical line fitting.
2. **Model B: Local DevContainer & Workstation (Setup 2)** [`§8.0`, `§8.1`]: Dedicated workstation equipped with an 8 P-core / 8 E-core CPU (e.g., Intel i7-13700K) and an NVIDIA RTX 3090/4090 GPU ($24\text{ GB}$ VRAM). Core pinning must restrict OpenMPI jobs to the 8 P-cores using `KMP_HW_SUBSET=8c:intel_core,1t` [`§8.0`].
3. **Model C: HPC Cluster (Setup 3)** [`§8.0`, `§8.4a`]: Multi-node SLURM cluster running parallel ORCA and CFOUR jobs across Infiniband interconnects.

### Step-by-Step Production SLURM Submission Script (`.sbatch`) [`§6.1`]
Below is a reference `.sbatch` script generated by `CoChem-NODE` for Setup 3 HPC execution:

```bash
#!/bin/bash
#SBATCH --job-name=cochem_v4_bench
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=1
#SBATCH --mem=32GB
#SBATCH --time=12:00:00
#SBATCH --partition=standard

module load orca/5.0.4
module load cfour/2.1
module load cuda/12.2

export OMP_NUM_THREADS=1
export KMP_HW_SUBSET=8c:intel_core,1t

cochem_exec --config production_junchs.json --input CO2_H2O.xyz
```

### 1.5.2 Cloud Infrastructure & Teaching Limits [`§8.4b`, `§19.1`]
When deploying CoChem in educational or GitHub Actions environments, strict infrastructure constraints apply [`§8.4b`]:
- **GitHub Actions Limits**: Maximum job execution time of **6 hours**, matrix cap of **256 jobs**, concurrency limit of **20 parallel jobs** (Free tier), and hardware runners constrained to **4 vCPUs and 16 GB RAM** [`§8.4b`].
- **ChemCompute Integration**: For university courses and student labs, CoChem integrates with **ChemCompute** [`§19.1`], providing free access to NSF-funded supercomputing resources (Expanse, Bridges-2, Delta) running Psi4 and PySCF, completely bypassing local browser and GitHub runner constraints.

### 1.5.3 Software Licensing & Redistribution Discipline [`§11.1`–`§11.3`]
- **ORCA Licensing**: The ORCA End User License Agreement (EULA) strictly forbids the redistribution of ORCA binaries within public Docker images, public GitHub Codespaces, or shared cloud containers [`§11.1`]. Public teaching containers must deploy open-source alternatives (PySCF, Psi4, xtb) [`§11.3`].
- **CFOUR Licensing**: CFOUR requires a signed institutional license agreement [`§11.2`].
- **Machine Learning Potentials**: Models such as MACE-OFF23 and OMOL are restricted to academic and non-commercial research [`§11.3`].

---

## 1.6 CoChem-DOCK: Telemetry, WebSockets & Decimated Array Streaming
High-throughput quantum chemistry calculations generate massive streams of stdout logging and dense numerical arrays. Streaming raw ORCA outputs into standard Jupyter Notebook cells causes browser DOM freezing and kernel crashes [`§1.4`].

### 1.6.1 Asynchronous WebSocket Architecture [`§18`, `§20.2`]
`CoChem-DOCK` decouples job execution from the user interface by spinning up a localized FastAPI WebSocket server and a React Single-Page Application (SPA) [`§18`]. Output logs are streamed asynchronously over WebSockets directly into dedicated virtualized log buffers using React `useRef` hooks to prevent layout thrashing [`§18`, `§20.2`].

### 1.6.2 Largest-Triangle-Three-Buckets (LTTB) Decimation [`§18`, `§8C.2`]
Simulating room-temperature rotational spectra or multi-dimensional potential energy surfaces produces datasets containing upwards of $10,000,000$ data points. Rendering $10^7$ coordinate pairs in browser WebGL canvases triggers instant Out-Of-Memory (OOM) tab crashes [`§18`].
- `CoChem-DOCK` passes raw spectral arrays through the **Largest-Triangle-Three-Buckets (LTTB)** decimation algorithm prior to WebSocket transmission [`§18`, `§8C.2`].
- LTTB downsamples $10^7$ points to exactly $5,000$ points while mathematically preserving peak maxima, absorption line shapes, and baseline noise features without deleting sharp spectroscopic signals.

$$\text{Area} = \frac{1}{2} \left| A_x (B_y - C_y) + B_x (C_y - A_y) + C_x (A_y - B_y) \right|$$

---

# CHAPTER 2: MOLECULAR INGESTION, TRIAGE & PROVENANCE (CoChem-MInt)

## 2.1 The Unified Ingestion Dashboard & Input Parsing
The **CoChem-MInt** (Molecular Ingestion & Triage) module acts as the strict entry gatekeeper for all chemical structures [`§2.1`]. MInt accepts input from two primary sources:
1. **Direct Identifier Ingestion**: SMILES strings, IUPAC names, or PubChem Compound Identifiers (CIDs) fetched via asynchronous `aiohttp` queries [`§2.2`].
2. **Coordinate File Uploads**: Structural files in `.xyz`, `.mol2`, `.pdb`, or `.cif` formats [`§2.3`].

### Asynchronous Ingestion & 3D WebGL Visualization
MInt integrates `py3Dmol` WebGL components directly within the UNITY dashboard. Users can inspect spatial conformers, check bond connectivity graphs, and verify isotopic labels prior to queueing high-tier calculations.

---

## 2.2 Sandboxed Fast Triage & The Eckart Coordinate Frame
Before invoking expensive quantum mechanical solvers, incoming geometries undergo structural sanitization and deterministic coordinate alignment [`§2.3`, `§2.4`].

### 2.2.1 Force-Field Preconditioning (GFN2-xTB / UFF) [`§2.4`]
Uploaded structures pass through a sandboxed minimization using GFN2-xTB or the Universal Force Field (UFF) to eliminate severe steric clashes, unphysical bond lengths ($< 0.8\text{ \AA}$), or overlapping atoms.

### 2.2.2 Center-of-Mass & Eckart Frame Standard Alignment [`§2.3`, `§5.1`]
To ensure structural determinism and prevent numerical noise during rotational constant evaluations:
1. The origin of the Cartesian coordinate system is shifted strictly to the molecular Center of Mass (COM):

$$\mathbf{r}_{\text{COM}} = \frac{\sum_{i=1}^N m_i \mathbf{r}_i}{\sum_{i=1}^N m_i}$$

2. The moment of inertia tensor $\mathbf{I}$ is constructed and diagonalized to establish the Principal Axis System (PAS), orienting the principal axes along $a, b, c$ such that $I_a \le I_b \le I_c$:

$$\mathbf{I}_{\alpha\beta} = \sum_{i=1}^N m_i \left( r_i^2 \delta_{\alpha\beta} - r_{i,\alpha} r_{i,\beta} \right)$$

3. Geometries are aligned to the standard **Eckart Frame** [`§2.3`, `§5.1`], ensuring that spatial RMSD checks during conformer deduplication are invariant to translational and rotational shifts:

$$\sum_{i=1}^N m_i \left( \mathbf{r}_i^0 \times \mathbf{r}_i \right) = \mathbf{0}$$

```python
# PYTHON ECKART FRAME TRANSFORMER (§2.3, §5.1)
import numpy as np

def align_to_eckart_frame(coords, masses, ref_coords):
    # 1. Center of Mass Shift
    com = np.sum(coords * masses[:, None], axis=0) / np.sum(masses)
    coords_centered = coords - com
    ref_com = np.sum(ref_coords * masses[:, None], axis=0) / np.sum(masses)
    ref_centered = ref_coords - ref_com
    
    # 2. Compute Eckart Cross-Correlation Matrix A
    A = np.dot((coords_centered * masses[:, None]).T, ref_centered)
    
    # 3. Singular Value Decomposition
    U, S, Vt = np.linalg.svd(A)
    R = np.dot(U, Vt)
    
    # Enforce right-handed coordinate system
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = np.dot(U, Vt)
        
    aligned_coords = np.dot(coords_centered, R)
    return aligned_coords
```

---

## 2.3 Physics Variable Setup & Spend Priority Hierarchy
During ingestion setup, the user specifies target physical observables. CoChem v4 enforces a strict **Spend Priority Hierarchy** [`§3.3`] to optimize computational expenditure:

```
+-----------------------------------------------------------------------------------+
|                        COCHEM V4 COMPUTE SPEND PRIORITY                           |
+------+----------------------------------------+-----------------------------------+
| Rank | Target Parameter                       | Optimization Strategy             |
+------+----------------------------------------+-----------------------------------+
| 1    | Intermolecular Geometry (R)            | Composite / Frozen Monomer        |
| 2    | Harmonic/Anharmonic Delta B_vib        | Low-cost DFT Hessian              |
| 3    | Monomer Core Geometries                | Freeze high-level CCSD(T) monomers |
| 4    | Quartic Centrifugal Distortion         | Extract free from harmonic Hessian|
| 5    | Inertial Defect & Planar Moments       | Extract free from geometry/Hessian|
| 6    | Dipole Moment Components (mu_a,b,c)    | Signed PAS evaluation             |
| 7    | Nuclear Quadrupole Coupling (chi)      | Core-polarized basis evaluation   |
| 8    | Internal Rotation Barriers (V_3)       | 1D Torsional Scan                 |
| 9    | Tunnelling Splittings                  | Path-integral / WKB estimate      |
| 10   | Binding Energy (D_0)                   | Post-assignment validation only   |
+------+----------------------------------------+-----------------------------------+
```

> **Key Rule**: *Compute budget must be expended on intermolecular geometry optimization and vibrational corrections BEFORE attempting high-level calculations of interaction energies ($D_0$) or hyper-fine coupling* [`§3.3`]. Intermolecular geometry errors dominate rotational constants.

---

## 2.4 Provenance Initialization & Semantic Audit Ledger
At the conclusion of ingestion, MInt generates `fit_provenance.json` [`§12.5`, `§20.2`]. This JSON ledger records:
- SHA-256 cryptographic hashes of all input coordinates.
- Active software versions (ORCA, CFOUR, PySCF, xtb).
- Exact CODATA physical constants (CODATA 2018 default: $\hbar = 1.054571817 \times 10^{-34}\text{ J}\cdot\text{s}$, $u = 1.66053906660 \times 10^{-27}\text{ kg}$).
- Mandatory `[M]`, `[D]`, and `[E]` provenance tags assigned to all baseline assumptions [`§12.5`].

```json
{
  "provenance_schema_version": "2026.4",
  "system_identifier": "CO2_H2O_dimer",
  "codata_version": "2018",
  "coordinate_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "product_class": "Class_A",
  "target_budget": "12h",
  "assigned_provenance_tags": {
    "intermolecular_distance_R": "[M]",
    "harmonic_vibrational_shift": "[D]",
    "estimated_tunnelling_barrier": "[E]"
  }
}
```

---

# CHAPTER 3: TOPOLOGICAL DISCOVERY, DEDUPLICATION & PES (TOPOS, SCAN, TORQ)

## 3.1 Conformer & Isomer Exploration (T1 Routing)
The **CoChem-TOPOS** module conducts global conformational searching across potential energy surfaces [`§9B`, `§13.1`]. T1 workflows route according to target wall-clock budgets:
- **`T1-10s`**: Hand-enumerated binding topologies (3–9 initial seeds) optimized via `! XTB2 TightOpt` [`§13.1`].
- **`T1-1min`**: `! GOAT XTB2 PAL8` stochastic exploration [`§13.1`].
- **`T1-30min`**: Machine Learning Force Field GOAT exploration using `! GOAT-EXPLORE ExtOpt` backed by an active `oet_server` daemon [`§9B.4`, `§13.1`].
- **`T1-1h`**: CREST non-covalent search: `crest --nci --gfn2 --ewin 12 --nocross --noreftopo` [`§9B.2`, `§13.1`].
- **`T1-3h`**: Multi-engine union merge $\rightarrow$ CREST screening $\rightarrow$ r²SCAN-3c refinement $\rightarrow$ CREGEN deduplication (`--bthr 0.001`) [`§9B.3`, `§13.1`].
- **`T1-12h`**: `! GOAT r2SCAN-3c` global search over leading isomeric basins [`§13.1`].

---

## 3.2 Two-Stage Deduplication Protocol: GOAT Primary + CREST Cross-Check
Legacy conformer search pipelines frequently relied on a single search engine (such as CREST alone). CoChem v4 incorporates a mandatory **Two-Stage Deduplication Protocol** [`§9B.1`–`§9B.3`]:

```
+-----------------------------------------------------------------------------------+
|                     TWO-STAGE CONFORMER DEDUPLICATION PROTOCOL                    |
+-----------------------------------------------------------------------------------+
| STAGE 1: PRIMARY EXPLORATION (ORCA GOAT)                                          |
| - Method: Stochastic uphill potential pushing (! GOAT XTB2 or r2SCAN-3c)          |
| - Performance: High basin-coverage reliability (F1 score = 0.93 [M])              |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| STAGE 2: SECONDARY CROSS-CHECK (CREST NCI)                                        |
| - Command: crest --nci --gfn2 --ewin 12 --nocross --noreftopo                     |
| - Mandatory Flags: --nocross (prevents cross-isomer corruption)                   |
|                    --noreftopo (disables rigid topology checks for weak complexes)|
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| STAGE 3: REFEREE DEDUPLICATION (CREGEN UNION)                                     |
| - Stage A (Coarse Triage): Engine defaults (RMSD 0.125 Å [E], dE 0.10 kcal/mol [E])       |
| - Stage B (Spectroscopic): crest --cregen --bthr 0.001 (0.1% [M] rotational shift)    |
+-----------------------------------------------------------------------------------+
```

### CREST Non-Covalent Binding Protection [`§9B.2`]
Running standard CREST iterative Metadynamics via Molecular Dynamics (iMTD-GC) without non-covalent interaction flags on weak van der Waals dimers causes severe force bias, pulling fragile complexes apart and causing dissociation within $4.2\text{ ps}$ [`§9B.2`].
- **Mandatory CREST Flags**: `crest --nci --gfn2 --nocross --noreftopo` [`§9B.2`].
- **`--noreftopo` Rationale**: Standard CREST assumes fixed covalent topology. For hydrogen-bonded or vdW complexes, hydrogen-bond rearrangement changes topological connectivity graphs. Disabling reference topology checks (`--noreftopo`) is required to discover true binding isomers.

---

## 3.3 MLFF-GOAT Integration Recipe & Boundary Constraints
CoChem v4 enables high-speed Machine Learning Force Field (MLFF) conformer discovery via ORCA's external optimizer interface (`!ExtOpt GOAT`) coupled to an active `oet_server` daemon [`§9B.4`, `§10.1`].

### 3.3.1 The ORCA External Tool Contract (`!ExtOpt`) & Sign-Flip Requirement [`§10.2`, `§10.3`]
When interfacing external MLFF models (such as MACE-OFF23 or AIMNet2) to ORCA via `!ExtOpt`, strict coordinate and gradient conversion rules apply [`§10.3`]:
1. **Coordinate File**: ORCA writes current Cartesian coordinates to `extinp.tmp` in Bohr.
2. **Force-to-Gradient Sign Flip**: ASE and PyTorch calculators evaluate atomic forces $\mathbf{F}_i = -\nabla_i E$ in units of $\text{eV/\AA}$. ORCA expects the energy $E$ (Hartrees) and gradients $\mathbf{g}_i = +\nabla_i E = -\mathbf{F}_i$ in units of $\text{Eh/bohr}$ written to `engrad` [`§10.3`].

$$\mathbf{g}_i \,(\text{Eh/bohr}) = -\mathbf{F}_i \,(\text{eV/\AA}) \times \left( \frac{1\text{ bohr}}{0.5291772109\text{ \AA}} \right) \times \left( \frac{1\text{ Eh}}{27.211386245\text{ eV}} \right)$$

```python
# PYTHON OET_SERVER DAEMON GRADIENT WRAPPER (§10.3)
import numpy as np

def process_orca_extopt(input_file="extinp.tmp", output_file="engrad"):
    # Read coordinates from ORCA (Bohr)
    coords_bohr = parse_extinp(input_file)
    coords_ang = coords_bohr * 0.5291772109
    
    # Evaluate MLFF energy and forces (eV, eV/A)
    energy_ev, forces_ev_ang = mlff_calculator.calculate(coords_ang)
    
    # Unit Conversions
    energy_hartree = energy_ev / 27.211386245
    # CRITICAL: SIGN FLIP (Gradient = - Force)
    grad_hartree_bohr = -forces_ev_ang * (0.5291772109 / 27.211386245)
    
    # Write engrad format for ORCA
    write_engrad(output_file, energy_hartree, grad_hartree_bohr)
```

> **CRITICAL WARNING**: *Failure to invert the sign ($\mathbf{g} = -\mathbf{F}$) causes the ORCA optimizer to interpret forces as positive gradients, driving the molecular structure UPHILL toward high-energy explosive dissociation* [`§10.3`].

### 3.3.2 Float32 Precision Traps & MLFF Limitations [`§9B.4`, `§10.5`]
- **Float32 Optimizer Noise**: Neural network potentials evaluated in single precision (Float32) carry numerical gradient noise at the $10^{-4}\text{ Eh/bohr}$ level [`§10.5`]. Geometry optimizations using `!ExtOpt` with Float32 MLFFs must specify loose SCF tolerances (`%scf TolE 1e-5 end`) and loose geometry bounds (`! TightOpt` will fail to converge due to gradient noise floor) [`§10.5`].
- **MLFF Accuracy Boundary**: Foundation MLFFs (MACE-OFF23, ANIK, AIMNet2) exhibit interaction energy errors of **$3.5\text{ to } 7.3\text{ kcal/mol}$ on non-covalent benchmark sets (S30L) [M]** [`§9B.4`].
- **Mandatory Role**: *MLFF-GOAT acts strictly as a high-speed topology ENUMERATOR, never as the final structural or energetic JUDGE* [`§9B.4`]. All MLFF-discovered conformers must undergo high-level DFT or composite *ab initio* re-optimization [`§9B.4`].

---

## 3.4 Geometry Optimization Preconditioning & Initial Hessians
Legacy user manuals recommended setting `Calc_Hess` in ORCA optimization blocks to compute an exact initial Hessian at step 0. CoChem v4 **strictly forbids `Calc_Hess`** for geometry optimizations [`§8B.3`].

### 3.4.1 Rationale for Eliminating Legacy `Calc_Hess` [`§8B.3`]
Computing an exact analytical initial Hessian at step 0 requires significant computational time (often equivalent to 10–30 single-point gradient evaluations). Benchmark evaluations across non-covalent complexes prove that exact initial Hessians do not accelerate quasi-Newton convergence compared to model Hessians [`§8B.3`]:

```
+-----------------------------------------------------------------------------------+
|               INITIAL HESSIAN CONVERGENCE STEPS BENCHMARK [M]                     |
+-----------------------------------+-----------------------+-----------------------+
| Test System                       | Exact Initial Hessian | InHess XTB2 / Lindh   |
+-----------------------------------+-----------------------+-----------------------+
| Water Dimer                       | 24 steps              | 22 steps              |
| Formic Acid Dimer                 | 21 steps              | 19 steps              |
| SO2 - Water Complex               | 110 steps             | 104 steps             |
| Pyridine - Water Dimer            | 120 steps             | 112 steps             |
+-----------------------------------+-----------------------+-----------------------+
```

### 3.4.2 Corrected Initial Hessian Guidance [`§8B.3`]
Initial Hessians should be generated using low-cost model approximations via `InHess XTB2` or `InHess Lindh` [`§8B.3`]:

```text
# CORRECTED COCHEM V4 OPTIMIZATION BLOCK
! r2SCAN-3c Opt
%geom
  InHess XTB2     # Model Hessian from GFN2-xTB (or InHess Lindh)
  TolE 1e-7
  TolRMSG 3e-6
  TolMaxG 1e-5
  TolRMSD 5e-5
  TolMaxD 1e-4
end
```

---

## 3.5 Torsional Discovery & Internal Rotor Mechanics (TORQ)
For molecules containing internal rotating groups (e.g., methyl $-\text{CH}_3$ tops or hydroxyl $-\text{OH}$ rotors), internal rotation violates harmonic oscillator approximations [`§6.7`, `§14.2`].

### 3.5.1 Reduced Moment of Inertia $F(\phi)$ [`§6.7`]
`CoChem-TORQ` performs 1D relaxed torsional scans along internal dihedral coordinates $\phi \in [0^\circ, 360^\circ]$ at $5^\circ$ increments. At each step, TORQ evaluates the geometry-dependent reduced moment of inertia $F(\phi)$ in $\text{cm}^{-1}$:

$$F(\phi) = \frac{\hbar}{8\pi^2 c I_r(\phi)}$$

where $I_r(\phi)$ is the effective internal rotation moment of inertia calculated using the Pitzer rigid-frame / relaxed-top formalism [`§6.7`]:

$$I_r(\phi) = I_\alpha \left[ 1 - \sum_{\beta} \frac{\lambda_\beta^2 I_\alpha}{I_\beta} \right]$$

### 3.5.2 Internal Rotation Barrier Caps [$M$] [`§14.2`]
Theoretical calculations of 3-fold internal rotation barriers ($V_3$) using DFT (e.g., $\omega\text{B97X-V}$) carry an intrinsic accuracy cap of **$\pm 14\%$ [M]** against experimental microwave torsional splittings [`§14.2`].

---

## 3.6 Persistent HDF5 Potential Energy Surface Store (`PESStore`)
CoChem v4 replaces temporary output text parsing with a persistent, centralized **HDF5 Potential Energy Surface Store** backed by the `PESStore` Python class [`§8C.1`–`§8C.3`].

```python
# PESStore ARCHITECTURE IMPLEMENTATION (§8C.2)
import h5py
import numpy as np
import json

class PESStore:
    """
    High-performance resizable HDF5 store for multi-dimensional PES campaigns.
    Uses h5py with chunking (512 points), gzip compression, and Fletcher32 checksums.
    """
    def __init__(self, filename="campaign.h5"):
        self.filename = filename
        self._init_db()

    def _init_db(self):
        with h5py.File(self.filename, 'a') as f:
            if 'molecules' not in f:
                f.create_dataset('molecules', shape=(0, 0, 3), maxshape=(None, None, 3),
                                 dtype='float64', chunks=(512, 10, 3), compression='gzip',
                                 compression_opts=4, fletcher32=True)
            if 'energies' not in f:
                f.create_dataset('energies', shape=(0,), maxshape=(None,),
                                 dtype='float64', chunks=(512,), compression='gzip',
                                 compression_opts=4, fletcher32=True)
            if 'gradients' not in f:
                f.create_dataset('gradients', shape=(0, 0, 3), maxshape=(None, None, 3),
                                 dtype='float64', chunks=(512, 10, 3), compression='gzip',
                                 compression_opts=4, fletcher32=True)

    def append_entry(self, coords, energy, grad):
        with h5py.File(self.filename, 'a') as f:
            m_ds = f['molecules']
            e_ds = f['energies']
            g_ds = f['gradients']
            
            idx = e_ds.shape[0]
            n_atoms = coords.shape[0]
            
            if m_ds.shape[1] < n_atoms:
                m_ds.resize((m_ds.shape[0], n_atoms, 3))
                g_ds.resize((g_ds.shape[0], n_atoms, 3))
                
            m_ds.resize((idx + 1, n_atoms, 3))
            e_ds.resize((idx + 1,))
            g_ds.resize((idx + 1, n_atoms, 3))
            
            m_ds[idx] = coords
            e_ds[idx] = energy
            g_ds[idx] = grad
```

### 3.6.1 HDF5 Storage Parameters [`§8C.2`]
- **Chunk Size**: Chunked in blocks of **512 geometry points** ($120\text{ KiB}$ chunk size) to optimize random I/O during active learning queries [`§8C.2`].
- **Compression & Integrity**: `gzip` level 4 compression combined with `shuffle` filtering and mandatory **`fletcher32` checksum validation** [`§8C.2`].
- **Lossy Compression Prohibited**: The HDF5 `scaleoffset` lossy filter is **strictly forbidden** for energy fields, as truncating energy mantissas introduces artificial noise into gradient numerical differentiation [`§8C.3`].

---

## 3.7 Active Learning & Dynamic PES Refinement (SCAN)
For high-dimensional potential surface mapping ($T2$ workflows), running uniform grid sampling is computationally intractable ($N_{\text{pts}} = k^d$). `CoChem-SCAN` deploys active learning via Query-By-Committee (QBC) uncertainty sampling [`§13.2`]:
1. A committee of 4 neural network potentials (MACE-OFF23 seeds) evaluates candidates from a pool of $2,000$ generated geometries.
2. Geometries exhibiting maximum committee energy variance $\sigma_E^2 > 0.05\text{ kcal/mol}$ are selected for high-level DFT / CCSD(T) evaluation.
3. Points are appended to `campaign.h5` and the model is fine-tuned, achieving a **20x to 100x reduction in required single-point calculations** [`§13.2`].

---

# CHAPTER 4: HIGH-PRECISION AB INITIO REFINEMENT (BENCH & CROWN)

## 4.1 Equilibrium ($B_e$) vs Ground-State ($B_0$) Rotational Constants
A primary source of confusion in spectroscopic modeling is the physical distinction between equilibrium rotational constants ($B_e$) and ground-state experimental rotational constants ($B_0$) [`§3.0`–`§3.2`].

### 4.1.1 Physical Definitions [`§3.0`]
- **$B_e$ (Born-Oppenheimer Equilibrium)**: Rotational constants calculated directly from the structural minimum of the electronic potential energy surface ($r_e$). $B_e$ represents a purely theoretical construct with no zero-point motion.
- **$B_0$ (Ground-State Vibrationally Averaged)**: The true physical observable measured in a microwave experiment. $B_0$ incorporates zero-point vibrational motion ($\Delta B_{\text{vib}}$):

$$B_0 = B_e + \Delta B_{\text{vib}} = B_e - \frac{1}{2} \sum_{i=1}^{3N-6} \alpha_i^B$$

where $\alpha_i^B$ are the vibration-rotation interaction constants derived from anharmonic force fields [`§3.0`].

### 4.1.2 Magnitude of Vibrational Corrections [`§3.1`]
Vibrational contributions $\Delta B_{\text{vib}}$ account for **$0.1\%$ to $0.7\%$ of the total rotational constant magnitude** [`§3.1`].
- For a rigid molecule ($B \approx 5,000\text{ MHz}$), $\Delta B_{\text{vib}}$ shifts the rotational constant by **$5\text{ to } 35\text{ MHz}$**.
- For a floppy van der Waals complex (such as $\text{CO}_2 \cdots \text{H}_2\text{O}$), zero-point elongation shifts $B_0$ by up to **$1.5\%$ to $2.0\%$** relative to $B_e$ [`§3.1`].

---

## 4.2 Intermolecular Geometry Convergence & Corrected `%geom` Block
Default geometry optimization thresholds in standard quantum chemistry packages (e.g., ORCA `!Opt`) are engineered for rigid covalent bonds. They are fundamentally inadequate for non-covalent complexes with soft intermolecular modes ($k \approx 0.05\text{ to } 0.1\text{ mdyn/\AA}$) [`§4.1`–`§4.4`].

### 4.2.1 Mechanics of Residual Gradient Error [`§4.4`]
Default ORCA `!Opt` specifies a maximum gradient convergence threshold of $\text{TolMaxG} = 3 \times 10^{-4}\text{ Eh/bohr}$.
For a weak intermolecular stretch mode with force constant $k = 0.069\text{ mdyn/\AA}$, a residual gradient of $3 \times 10^{-4}\text{ Eh/bohr}$ leaves an unconverged residual displacement $\Delta R$ [`§4.4`]:

$$\Delta R = \frac{F}{k} = \frac{3 \times 10^{-4}\text{ Eh/bohr}}{0.069\text{ mdyn/\AA}} \approx 0.036\text{ \AA} = 3.6\text{ pm}$$

Applying the rotational sensitivity relation $\frac{\Delta B}{B} = -2 \frac{\Delta R}{R}$ for a complex with $R = 3.0\text{ \AA}$ [`§4.1`]:

$$\frac{\Delta B}{B} = -2 \left( \frac{0.036\text{ \AA}}{3.0\text{ \AA}} \right) = -2.4\% \quad (\approx 120\text{ MHz error at } 5\text{ GHz!})$$

### 4.2.2 Corrected CoChem v4 `%geom` Block [`§4.4`]
To restrict geometry-induced rotational errors below $0.05\%$, CoChem v4 mandates tightening gradient and displacement thresholds by a factor of 30 relative to default `!Opt` [`§4.4`]:

```text
# MANDATORY COCHEM V4 INTERMOLECULAR GEOMETRY BLOCK (§4.4)
%geom
  TolE 1e-7      # Energy change < 1e-7 Hartree
  TolRMSG 3e-6      # RMS gradient < 3e-6 Eh/bohr
  TolMaxG 1e-5      # Max gradient < 1e-5 Eh/bohr (30x tighter than !Opt)
  TolRMSD 5e-5      # RMS displacement < 5e-5 bohr
  TolMaxD 1e-4      # Max displacement < 1e-4 bohr
end
```

---

## 4.3 Frozen-Monomer Composite Protocol
When calculating non-covalent complexes, high-level composite methods ($T3O\text{-}12h$ junChS) can be extremely expensive if all internal monomer degrees of freedom are fully optimized [`§9A.1`].

### 4.3.1 Sensitivity Arithmetic & Error Imbalance [`§9A.2`]
Consider the $\text{CO}_2 \cdots \text{H}_2\text{O}$ complex ($R = 2.836\text{ \AA}$).
- An error of $\Delta R = 0.002\text{ \AA}$ in the intermolecular separation produces $\frac{\Delta B}{B} = -0.135\%$ (a $-6.26\text{ MHz}$ error) [`§9A.2`].
- To produce an identical $-6.26\text{ MHz}$ rotational constant error via internal monomer bond length distortion would require a massive **$16.8\text{ m\AA}$ uniform error** across all covalent bonds [`§9A.2`].
- Modern electronic structure methods (such as fc-CCSD(T)/cc-pVTZ or r²SCAN-3c) never err by $16.8\text{ m\AA}$ on covalent bonds (typical covalent bond error is $< 0.6\text{ pm}$) [`§9A.2`].

### 4.3.2 Monomer Dominance Rule [`§9A.3`]
Covalent monomer geometry error dominates the $A$ rotational constant ($10\text{ m\AA}$ monomer bond error $\rightarrow -1.71\%$ error in $A$), while intermolecular distance $R$ dominates $B$ and $C$ ($0.020\text{ \AA}$ intermolecular error $\rightarrow -1.34\%$ error in $B$) [`§9A.3`].

### 4.3.3 Frozen-Monomer Protocol Execution [`§9A.4`]
CoChem v4 establishes the **Frozen-Monomer Composite Protocol** as the default for all weakly bound complexes [`§9A.4`]:
1. Optimize isolated monomers at high $ab initio$ levels (fc-CCSD(T)/cc-pwCVTZ or experimental $r_e^{\text{SE}}$ structures) to lock in covalent parameters and fix $A$.
2. Assemble the complex and freeze all internal monomer coordinates.
3. Optimize *only* the 6 intermolecular degrees of freedom (intermolecular separation $R$ and orientation angles) at the target composite level (e.g., $\omega\text{B97M-V/def2-QZVPP}$ or DLPNO-CCSD(T)).

---

## 4.4 Basis Set Superposition Error (BSSE) Geometry Corrections
In finite basis set calculations of complexes, monomer A artificially borrows basis functions from monomer B, creating an unphysical attractive force [`§4.7`].
- At the B3LYP/cc-pVTZ level without counterpoise correction, BSSE artificially shortens the intermolecular distance $R(\text{O}\cdots\text{O})$ in the water dimer by **$4.1\text{ pm}$** [`§4.7`].
- A $4.1\text{ pm}$ geometry error produces a **$2.8\%$ error in $B_0$** [`§4.7`].
- **Rule**: Counterpoise-corrected geometry optimization (`! CP`) or explicit CP-corrected composite schemes are mandatory when using non-augmented triple-zeta basis sets [`§4.7`].

$$E_{\text{interaction}}^{\text{CP}} = E_{AB}^{AB}(R_{AB}) - E_A^{AB}(R_{AB}) - E_B^{AB}(R_{AB})$$

---

## 4.5 Frozen-Core Bias & Core-Valence Electron Correlation
Valence-only frozen-core calculations (`fc-CCSD(T)`) ignore the correlation energy of deep 1s core electrons [`§4.8`].
- Frozen-core calculations using `fc-CCSD(T)/cc-pVQZ` carry a systematic **$-0.81\%$ mean bias [M]** in $B_e$ across organic benchmarks [`§4.8`].
- **Mandatory Constraint**: *No workflow may claim $\le 0.5\%$ accuracy in $B_e$ using frozen-core calculations without core-valence corrections* [`§4.8`].
- **Remediation**: Core-valence corrections must be added via additive core legs ($\Delta \text{CV} = E_{\text{all-electron}}(\text{cc-pCVTZ}) - E_{\text{frozen-core}}(\text{cc-pVTZ})$) or using full core-polarized basis sets (`cc-pwCVTZ`) [`§4.8`].

---

## 4.6 Quantum Engine Track Division: MPQC vs Legacy Alternates (ORCA & CFOUR)

```
+-----------------------------------------------------------------------------------+
|                        QUANTUM ENGINE CAPABILITY MATRIX (§9.1)                    |
+------------------------------------+-----------------------+----------------------+ 
| Feature / Capability               | ORCA Track            | CFOUR Track          |
+------------------------------------+-----------------------+----------------------+ 
| Conformer Search & GOAT            | YES (Native)          | NO                   |
| SCF Analytic Hessians (HF/DFT)     | YES                   | YES                  |
| Coupled-Cluster Analytic Hessians  | NO (SCF only)         | YES (CCSD(T) Exact)  |
| Anharmonic VPT2 Force Fields       | DFT / MP2 only        | Coupled-Cluster VPT2 |
| Centrifugal Distortion (Sextic)    | Numerical / Limited   | YES (Analytic)       |
| Spin-Rotation Tensors (C_alpha)    | Limited               | YES (Analytic)       |
| DBOC Corrections                   | Limited               | YES (Analytic)       |
+------------------------------------+-----------------------+----------------------+ 
```

### 36N² Computational Scaling Arithmetic [`§9.3`]
Why can ORCA not replace CFOUR for coupled-cluster VPT2 force fields?
Consider a 10-atom non-linear complex ($N=10$, $3N-6 = 24$ normal modes). Anharmonic VPT2 requires computing **$6N-11 = 49$ Hessians** at displaced geometries [`§5.2`, `§9.3`]:

1. **CFOUR Track**: Computes 49 analytical CCSD(T) Hessians directly using analytical second derivatives [`§9.3`].
2. **ORCA Track (DLPNO Numerical Differentiation)**: Because ORCA lacks analytical CCSD(T) Hessians, computing a single Hessian requires finite differences of gradients.
   - A numerical gradient requires $6N = 60$ single points.
   - A numerical Hessian from numerical gradients requires $60 \times 60 = 3,600$ single-point calculations.
   - Total single points for 49 Hessians: $49 \times 3,600 = \mathbf{176,400\text{ single-point DLPNO calculations!}}$ [`§9.3`].

$$\text{Ratio} = \frac{\text{ORCA Single Points}}{\text{CFOUR Hessians}} = (6N)^2 = 36 N^2 = \mathbf{3,600 \times \text{ cost ratio at } N=10} \, [\text{D}]$$

```text
# SAMPLE CFOUR ZMAT INPUT FILE FOR COUPLED-CLUSTER ANHARMICITY (§9.3)
Water Dimer CFOUR Anharmonic Force Field
O1
H2 1 R1
H3 1 R1 2 A1
O4 1 R2 2 A2 3 D1
H5 4 R3 1 A3 2 D2
H6 4 R3 1 A3 5 D3

R1=0.957
R2=2.912
R3=0.957
A1=104.5
A2=112.0
A3=104.5
D1=0.0
D2=120.0
D3=-120.0

*CFOUR(CALC=CCSD(T),BASIS=pV3Z,VIB=EXACT,ANHARM=VPT2,COORD=CARTESIAN)
```

> **Track Assignment Rule**: *CFOUR owns all coupled-cluster anharmonic force fields (VPT2), sextic centrifugal distortion, and spin-rotation tensors. ORCA owns conformer searching, DLPNO single points, and DFT-level VPT2* [`§9.1`–`§9.4`].

---

## 4.7 Multireference Diagnostics & Macroscopic Thermal Ensembles
- **$T_1 / D_1$ Diagnostics**: Single-reference coupled-cluster calculations parse the $T_1$ diagnostic [`§4.4`]. If $T_1 > 0.02$ (closed-shell) or $T_1 > 0.04$ (open-shell), the calculation is rejected due to static multireference correlation, triggering a fallback warning to CASSCF/NEVPT2 in PySCF [`§4.4`].
- **Boltzmann Population Synthesis**: Thermodynamic corrections derived from Hessians feed Boltzmann ensemble calculations at $T_{\text{sys}}$ (default $298.15\text{ K}$ or $2\text{ K}$ supersonic jet expansion), producing populated ensemble spectra [`§4.5`].

$$P_i = \frac{g_i \exp(-E_i / k_B T)}{\sum_j g_j \exp(-E_j / k_B T)}$$

---

# CHAPTER 5: VIBRATIONAL AVERAGING, SECONDARY OBSERVABLES & FITTING (SpycFit & MUSE)

## 5.1 Quantum Vibrational Averaging & Jensen's Inequality
Vibrational averaging of rotational constants requires computing the expectation value of the inverse moment of inertia tensor $\mathbf{I}^{-1}$ over the ground-state vibrational wavefunction $\psi_0$ [`§5.1`]:

$$\langle B \rangle_0 = \frac{\hbar}{8\pi^2 c} \left\langle \psi_0 \left| \mathbf{I}^{-1} \right| \psi_0 \right\rangle = \frac{\hbar}{8\pi^2 c} \left\langle \frac{1}{I} \right\rangle$$

### 5.1.1 Jensen's Inequality Formula & Systematic Bias [`§5.1`]
A frequent mathematical error in custom spectroscopy scripts is averaging the moments of inertia $I$ first and then inverting the average: $B_{\text{wrong}} = \frac{\hbar}{8\pi^2 c} \frac{1}{\langle I \rangle}$.
By **Jensen's Inequality** for convex functions ($f(x) = 1/x$ is strictly convex for $x > 0$) [`§5.1`]:

$$\left\langle \frac{1}{I} \right\rangle > \frac{1}{\langle I \rangle}$$

Inverting after averaging systematically **underestimates the true rotational constant** $B_0$ [`§5.1`]. Taylor expanding around the equilibrium moment $I_e$ yields the systematic bias magnitude:

$$\Delta B_{\text{bias}} = \left\langle \frac{1}{I} \right\rangle - \frac{1}{\langle I \rangle} \approx \frac{1}{I_e} \left( \frac{\sigma_I^2}{I_e^2} \right) \approx B_e \left( 3 \frac{\sigma_R^2}{R_0^2} \right)$$

For a soft van der Waals mode with vibrational amplitude variance $\sigma_R = 0.15\text{ \AA}$ at $R_0 = 3.0\text{ \AA}$ [`§5.1`]:

$$\frac{\Delta B_{\text{bias}}}{B_e} \approx 3 \left( \frac{0.15}{3.0} \right)^2 = 3 (0.05)^2 = \mathbf{0.63\% \text{ systematic underestimation bias}} \, [\text{D}]$$

At $B_e = 3,500\text{ MHz}$, this mathematical error introduces a **$22\text{ MHz}$ systematic error**—exceeding the entire $0.1\%$ Class B error target by a factor of 6! [`§5.1`].
- **Mandatory Rule**: *Vibrational averaging MUST evaluate the element-wise inverse inertia tensor expectation value $\left\langle \mathbf{I}^{-1} \right\rangle$ prior to scalar conversion* [`§5.1`].

---

## 5.2 Corrected Anharmonic VPT2 Displacement Counts
When executing Anharmonic Vibrational Perturbation Theory (VPT2) to compute $\Delta B_{\text{vib}}$ and cubic force fields, numerical differentiation requires finite displacements along normal coordinates [`§5.2`].

- **Corrected Formula**: For a non-linear molecule with $N$ atoms ($3N-6$ normal modes), the exact number of Hessian evaluations required for semi-diagonal cubic force field evaluation is [`§5.2`]:

$$n_{\text{Hess}}^{\text{VPT2}} = 2(3N-6) + 1 = \mathbf{6N - 11}$$

- For a 10-atom non-linear complex ($N=10$), $n_{\text{Hess}}^{\text{VPT2}} = 6(10) - 11 = \mathbf{49\text{ Hessians}}$ (not $6N+1 = 61$) [`§5.2`].
- **Resonance Deperturbation**: If VPT2 denominators encounter Fermi ($\omega_i \approx 2\omega_j$) or Coriolis ($\omega_i \approx \omega_j$) resonances, CoChem-SpycFit applies automated Darling-Dennison matrix deperturbation to prevent frequency explosions [`§5.1`].

---

## 5.3 Force-Field Recycling & Isotopologue Structural Fitting
Computing an anharmonic force field at the coupled-cluster level is computationally expensive. However, because electronic potential energy surfaces are invariant under isotopic substitution within the Born-Oppenheimer approximation, **a single force field can be recycled across all isotopologues at zero electronic-structure cost** [`§6.10`, `§8B.4`].

### 5.3.1 Force-Field Recycling Pipeline [`§8B.4`]
Once a master `.hess` file (ORCA) or `JOBARC` / `JA2FL` archive (CFOUR) is generated for the parent molecule:
1. Copy the Hessian matrix.
2. Substitute atomic masses $m_i \rightarrow m_i'$ for isotopic variants ($^{13}\text{C}, ^{18}\text{O}, \text{D}$).
3. Re-run mass-weighted transformation (`orca_vib` or CFOUR `ISOMASS` + `xjoda`).
4. **Computational Saving**: Yields full $B_0'$, centrifugal distortion, and $\Delta B_{\text{vib}}'$ constants for all isotopologues with **$6\text{x to } 15\text{x}$ compute savings [D]** [`§8B.4`].

### 5.3.2 Kraitchman Singularity Handling & Costain $r_m^{(2)}$ Fitting [`§2.4`, `§5.6`]
- **Kraitchman Singularity**: When an atom lies within $0.15\text{ \AA}$ of a principal inertial axis, Kraitchman substitution equations ($r_s$) yield imaginary coordinates due to noise in $\Delta I$ [`§2.4`]. CoChem flags axis proximity and falls back to Costain's empirical uncertainty bounds ($\delta r = 0.0015 / |r|\text{ \AA}$).
- **Costain-Laurie $r_m^{(2)}$ Scaling**: Structural inversion fits effective moments $I_0$ using mass-scaling parameters ($c, d$) to strip zero-point vibrational inflation, yielding equilibrium-equivalent geometries ($r_e^{\text{SE}}$) [`§5.6`].

---

## 5.4 Secondary Spectroscopic Observables

### 5.4.1 Dipole Moment Components ($\mu_a, \mu_b, \mu_c$) [`§6.1`]
Dipole moments must be evaluated in the Principal Axis System (PAS) with explicit signs retained [`§6.1`].
- **Dark Conformer Threshold**: Conformers with total dipole magnitude $|\mu| < 0.1\text{ Debye}$ are flagged as spectroscopic "dark conformers" [`§6.1`]. They are unobservable in CP-FTMW experiments regardless of thermodynamic stability.

### 5.4.2 Nuclear Quadrupole Coupling Tensors ($\chi_{\alpha\beta}$) [`§6.3`]
For nuclei with electric quadrupole moments ($I \ge 1$, e.g., $^{14}\text{N}, ^{35}\text{Cl}, ^{37}\text{Cl}, \text{D}$), quadrupole coupling constants $\chi_{\alpha\beta} = e Q q_{\alpha\beta} / h$ map electric field gradients (EFGs) $q_{\alpha\beta}$ [`§6.3`].
- **Basis Set Rule**: Deuterium quadrupole couplings $\chi(\text{D})$ require core-polarized basis sets with uncontracted diffuse $p$ and $d$ functions (e.g., `cc-pCVTZ`) to resolve small field gradients [`§6.3`].

---

## 5.5 Permutation-Inversion Molecular Symmetry Groups
For non-rigid molecules exhibiting internal rotation, inversion, or tunnelling (e.g., ammonia dimer or water cluster), traditional point-group symmetry fails [`§7`].
- CoChem v4 deploys **Longuet-Higgins Molecular Symmetry (MS) Groups** based on feasible permutation-inversions $E^*$ [`§7`].
- Point-group tools (such as `molsym`) are removed for non-rigid systems. Spin-statistical weights ($g_{ns}$) are calculated explicitly for SPCAT / Pickett integration [`§7`].

---

## 5.6 Modern JAX Spectroscopy Fitting Engine & Pickett Interoperability
`CoChem-SpycFit` ports Watson A- and S-reduced centrifugally distorted Hamiltonians into **JAX** [`§5.1`, `§18`].
- **Automatic Differentiation**: Autodiff computes analytical Jacobians $\mathbf{J}_{ij} = \frac{\partial \nu_i}{\partial p_j}$, accelerating Levenberg-Marquardt fitting without finite-difference gradient noise.
- **Pickett Interoperability (`pyckett`)**: Fully compatible with JPL / CDMS formats, exporting validated `.par` (parameter input), `.int` (intensity input), and `.cat` (spectral catalog output) files [`§18`].

```python
# PYTHON JAX SPYCFIT WATSON HAMILTONIAN SNIPPET (§18)
import jax
import jax.numpy as jnp

@jax.jit
def watson_a_reduced_energy(J, K, A, B, C, DJ, DJK, DK):
    # Rigid Rotor Base Energy
    E_rr = 0.5 * (B + C) * J * (J + 1) + (A - 0.5 * (B + C)) * (K ** 2)
    # Quartic Centrifugal Distortion Terms
    E_cd = - DJ * (J * (J + 1)) ** 2 - DJK * J * (J + 1) * (K ** 2) - DK * (K ** 4)
    return E_rr + E_cd

# Compute Analytical Jacobian via Autodiff
jacobian_fn = jax.jacobian(watson_a_reduced_energy, argnums=(2, 3, 4, 5, 6, 7))
```

---

# CHAPTER 6: CONCURRENCY, STATE-CHAINING, TELEMETRY & DISPATCH (TORQ, NODE, SCRIBE, ORACLE)

## 6.1 Heterogeneous Concurrency & Scout-and-Anchor Pipeline
High-throughput workflows often suffer from resource contention when CPU-bound electronic structure calculations and GPU-bound neural network potentials are co-scheduled [`§8A.1`].

```
+-----------------------------------------------------------------------------------+
|               HETEROGENEOUS SCOUT-AND-ANCHOR PIPELINE ARCHITECTURE (§8A.2)        |
+-----------------------------------------------------------------------------------+
| SCOUT STREAM (GPU-Bound / MPS)                                                    |
| - Engine: MLFF (MACE-OFF23 / AIMNet2) or gpu4pyscf                                 |
| - Allocation: 1 CPU P-Core + MPS GPU Worker (up to 3 concurrent scouts)           |
| - Role: Rapid PES exploration, gradient scanning, advisory topology generation    |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Async Parsl Channel)
+-----------------------------------------------------------------------------------+
| ANCHOR STREAM (CPU-Bound / ORCA & CFOUR)                                           |
| - Engine: ORCA DLPNO-CCSD(T) / CFOUR Analytic Hessians                            |
| - Allocation: 7 Dedicated CPU P-Cores (%maxcore 3000 MB per rank)                 |
| - Role: High-precision ab initio refinement, strict convergence verification     |
+-----------------------------------------------------------------------------------+
```

### 6.1.1 Contention Budget & Parsl Co-Scheduling [`§8A.3`]
- Executed via the Parsl workflow engine with isolated CPU thread pools [`§8A.3`].
- **Contention Limit**: Co-scheduling contention slowdown must not exceed **1.20x on the CPU stream** [`§8A.3`].
- **Speedup**: Delivers an overall **3.1x pipeline speedup [M]** compared to sequential execution [`§8A.3`].

### 6.1.2 Concurrency Integrity Guards (G1–G7) [`§8A.6`]
To ensure Scout optimizations do not corrupt Anchor scientific calculations, 7 integrity guards are enforced [`§8A.6`]:
- **G1**: Scout outputs are strictly advisory; all structures undergo final Anchor validation.
- **G2**: High-level Hessian verification on all converged minima.
- **G3**: Basin identity verification via structural RMSD ($< 0.25\text{ \AA}$).
- **G4**: Rank-inversion audit requiring Spearman correlation $\rho \ge 0.90$ across conformer energy rankings.
- **G5**: Uncertainty gate rejecting MLFF predictions with variance $\sigma_E^2 > 0.05\text{ kcal/mol}$.
- **G6**: Automated abort governor terminating Scout paths after 5 consecutive failures.
- **G7**: Deterministic audit trail logging all random seeds and Parsl execution IDs.

---

## 6.2 State Reuse & Canonical 11-Arrow Chaining Pipeline
The single most valuable computational asset in a spectroscopic pipeline is a converged geometry [`§8B.1`]. Reusing a converged geometry saves $600+$ single-point evaluations ($\approx 150\text{ hours}$ of compute time) [`§8B.1`].

```
+-----------------------------------------------------------------------------------+
|                  CANONICAL 11-ARROW STATE-CHAINING PIPELINE (§8B.2)               |
+-----------------------------------------------------------------------------------+
|  [Ingested XYZ] ----(1)---> [xTB / MLFF Triage] ----(2)---> [r2SCAN-3c Opt]       |
|                                                                    |              |
|                                                                   (3)             |
|                                                                    v              |
|  [DLPNO Single Point] <--(6)--- [junChS Composite] <--(5)--- [wB97M-V TightOpt]   |
|         |                                                          |              |
|        (7)                                                        (4)             |
|         v                                                          v              |
|  [PESStore HDF5]               [Isotopologue Mass Loop] <--(8)--- [Analytic Hess] |
|                                           |                        |              |
|                                          (9)                      (10)            |
|                                           v                        v              |
|                                    [VPT2 Delta B_vib]      [Centrifugal Dist]     |
|                                           |                        |              |
|                                          +-----------(11)----------+              |
|                                                       |                           |
|                                                       v                           |
|                                              [Pickett .par/.cat]                  |
+-----------------------------------------------------------------------------------+
```

### State Transfer Protection Rules (D1–D5) [`§8B.5`]
- **D1**: Non-stationary geometry transfer warning.
- **D2**: Hessian dimension mismatch rejection.
- **D3**: SCF electronic state basin change audit.
- **D4**: Counterpoise ghost-atom index mismatch check.
- **D5**: Atomic file overwrite protection locking binary archives.

---


## 6.3 Remote SLURM Cluster Dispatch (CoChem-NODE)
`CoChem-NODE` acts as the translation layer between the CoChem frontend and the MPQC backend. It translates `networkx` topologies into MPQC object-oriented JSON input formats. Crucially, when an F12 method is requested, NODE automatically appends the required Complementary Auxiliary Basis Sets (CABS) to the JSON payload.

`CoChem-NODE` translates UI configurations into SLURM `.sbatch` job directives [`§6.1`]. It parses core topology, allocates `%maxcore` memory targets, and wraps execution in OpenMPI tasks. NODE features a **Registry Healer** daemon that automatically adopts orphaned asynchronous SLURM jobs upon client reconnect [`§8A.6`].

---

## 6.4 Localized Retrieval-Augmented RAG Diagnostics (CoChem-ORACLE)
When quantum calculations fail, `CoChem-ORACLE` provides localized error diagnostics using a `llama.cpp` Large Language Model engine [`§6.2`].
- **VRAM Preemption**: ORACLE yields GPU VRAM (1–2 GB per worker [E]) whenever quantum calculations launch, falling back to CPU execution or sleeping [`§8A.4`].
- **ChromaDB RAG Vault**: ORACLE queries an offline ChromaDB SQLite vector store containing CoChem manual chunks, eliminating hallucinated diagnostic suggestions [`§6.4`].

---

## 6.5 Cryptographic FAIR Data Synthesis & QCSchema Logging (CoChem-SCRIBE)
`CoChem-SCRIBE` aggregates all calculation results into FAIR-compliant publication packages [`§6.3`].
- **Cryptographic Provenance**: Generates SHA-256 environment hashes locking Python dependencies, ORCA/CFOUR build versions, and CODATA constants [`§20.2`].
- **QCSchema Export**: Serializes structural, energy, and force outputs into standardized JSON QCSchema files [`§8C.2`, `§20.2`].
- **Automated LaTeX Tables**: Generates peer-review-ready `.tex` tables using `siunitx` and `booktabs` formatting [`§18`, `§20.2`].

---

# CHAPTER 7: EDUCATIONAL & PEDAGOGICAL IMPLEMENTATIONS

## 7.1 Foundational Concept Training (CoChem-PLAY1 & PLAY2)
Undergraduate organic chemistry often suffers from the "2D Paper Problem," where students struggle to map flat Lewis structures to 3D spatial reality.

### 7.1.1 RDKit Valency Engines & VSEPR Validation (ATOM)
In **PLAY1**, students are challenged to construct molecules.
- The backend securely utilizes RDKit to mathematically validate student inputs against strict VSEPR rules.
- The frontend utilizes WebAssembly (WASM) to actively intercept physically impossible geometries (e.g., a "Texas Carbon" with 5 bonds), providing immediate, Socratic feedback before allowing submission.

### 7.1.2 Macroscopic Phase Arena & Dipole Vectors (POLAR)
In **PLAY2**, the curriculum advances to intermolecular forces. Rather than asking students to memorize boiling points, the UI places 3D molecules into a "Macroscopic Arena." The backend dynamically calculates molecular dipole vectors ($\vec{\mu}$) and renders them in the WebGL viewer, forcing students to visually align electrostatic forces to predict boiling point trends.

---

## 7.2 The Gamified Curriculum (Academic Elo Tiers)
To prevent cognitive overload for undergraduate students interacting with the pipeline, **CoChem-PLAY** implements a gamified difficulty matrix known as the **Academic Elo Tier System**:
- **Tier 1 (Novice)**: Diatomic and simple straight-chain alkanes (rigid frameworks, no stereocenters).
- **Tier 2 (Apprentice)**: Single heteroatoms (alcohols, amines) introducing basic electronegativity vectors.
- **Tier 3 (Intermediate)**: Simple conjugated $\pi$-systems and rigid rings (benzene, cyclopentane).
- **Tier 4 (Advanced)**: Multi-functionalized systems requiring VSEPR integration and internal hydrogen bonding.
- **Tier 5 (Expert)**: Fluxional topologies, polycyclic frameworks, and transition metal complexes.

---

## 7.3 Undergraduate Curriculum Mapping (CoChem-CURE)
For upper-level physical chemistry courses, the pipeline implements a Course-Based Undergraduate Research Experience (CURE).

### 7.3.1 High-Energy Photolysis & Radical Trapping
Students design theoretical experiments to capture transient radical species. They generate starting geometries, invoke the LUMOS module to simulate photolytic cleavage, and utilize the SCAN module to locate thermodynamic trap states.

### 7.3.2 Abstract Syntax Tree (AST) Evasion Auditing
To prevent students from hardcoding answers into Jupyter Notebooks, the grading backend utilizes Python's `ast` (Abstract Syntax Tree) module. It mathematically parses code execution structures, verifying that quantum engine calls were actually executed. If a student bypasses the ORCA call and prints hardcoded strings, the submission is automatically flagged for Evasion.

```python
# AST EVASION AUDITOR CODE SNIPPET (§8A.5, §12.6)
import ast

class QuantumExecutionAuditor(ast.NodeVisitor):
    def __init__(self):
        self.found_orca_call = False
        
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in ['run_orca', 'execute_quantum']:
            self.found_orca_call = True
        self.generic_visit(node)
```

### 7.3.3 Advanced Plagiarism Traps: Temporal Collusion Detection
To combat sophisticated evasion in group environments, CoChem parses the underlying `.git` commit history of Codespace workspaces. The system analyzes commit timestamp deltas across student repositories. If Student A and Student B push topologically identical, highly complex workflow cells within 15 seconds of each other, the pipeline flags the submission as "Temporal Collusion" for PI review.

### 7.3.4 Individual Contribution Index (ICI) & Free-Rider Detection
CoChem-CURE integrates a Telemetry Auditor calculating the **Individual Contribution Index (ICI)**. It maps git commit authors to quantum engine execution logs. If the auditor detects that a specific user account in `group_manifest.json` triggered $< 10\%$ of computational workflows (a sub-30 ICI score), it flags that student as a simulated Free-Rider in `free_rider_flags.csv`.

---

## 7.4 Capstone Grading & Telemetry (CoChem-LABS & EVAL)
Grading complex Python workflows across a 100+ student roster requires automation that respects both FERPA privacy laws and academic integrity.

### 7.4.1 Automated Cryptographic Hashed Grader
When a student completes a CoChem-LABS module, the system packages final coordinates, script telemetry, and calculated answers into a `.cochem_submission.sha256` payload, preventing tampering between local student machines and Canvas LMS.

### 7.4.2 Research Aptitude Index (RAI) & Socratic Logarithmic Decay
The **CoChem-EVAL** system calculates the Research Aptitude Index (RAI). Students can request UI hints, but EVAL applies a **Logarithmic Decay Penalty** to the final score for every hint utilized. EVAL tracks 3D model rotation interactions, AST error recoveries, and execution efficiency, dumping finalized scores to standard LMS CSV files.

$$\text{RAI Score} = \text{BaseScore} \times \exp(-\lambda \cdot N_{\text{hints}})$$

---

## 7.5 The Principal Investigator (PI) Draft Board
The PI Dashboard provides instructors with a password-protected view rendering a ranked DataFrame (The "Draft Board") ordering students by their **Research Potential Index (RPI)**. Methodical students demonstrating strong problem recovery, low AST error rates, and active 3D visualization engagement rank highly, providing PIs with a data-driven recruitment pipeline.

---

## 7.6 Teaching Tier Infrastructure Limits & Deployment
When deploying CoChem educational modules across student cohorts, deployment configurations must comply with infrastructure constraints [`§8.4b`, `§11.1`–`§11.3`, `§19.1`]:
- **Cloud Infrastructure Limits**: Student GitHub Actions workflows are constrained to 6-hour runner caps and 20 concurrent job limits [`§8.4b`].
- **ORCA Licensing Restrictions**: ORCA binary redistribution in shared student container images is strictly prohibited [`§11.1`].
- **ChemCompute Integration**: Student labs should deploy open-source PySCF/Psi4/xtb engines locally or route through **ChemCompute** [`§19.1`] for zero-cost supercomputing access.

---

## Detailed Technical Annex for Chapter 1

The following technical specifications elaborate on the implementation details for Chapter 1 within the Method Matrix framework [`§1`].

### Annex 1.1: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.1 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.2: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.2 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.3: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.3 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.4: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.4 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.5: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.5 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.6: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.6 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.7: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.7 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.8: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.8 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.9: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.9 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.10: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.10 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.11: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.11 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.12: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.12 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.13: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.13 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 1.14: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 1.14 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

## Detailed Technical Annex for Chapter 2

The following technical specifications elaborate on the implementation details for Chapter 2 within the Method Matrix framework [`§2`].

### Annex 2.1: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.1 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.2: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.2 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.3: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.3 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.4: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.4 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.5: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.5 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.6: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.6 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.7: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.7 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.8: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.8 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.9: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.9 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.10: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.10 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.11: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.11 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.12: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.12 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.13: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.13 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 2.14: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 2.14 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

## Detailed Technical Annex for Chapter 3

The following technical specifications elaborate on the implementation details for Chapter 3 within the Method Matrix framework [`§3.0`].

### Annex 3.1: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.1 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.2: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.2 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.3: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.3 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.4: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.4 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.5: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.5 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.6: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.6 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.7: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.7 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.8: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.8 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.9: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.9 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.10: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.10 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.11: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.11 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.12: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.12 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.13: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.13 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 3.14: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 3.14 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

## Detailed Technical Annex for Chapter 4

The following technical specifications elaborate on the implementation details for Chapter 4 within the Method Matrix framework [`§4`].

### Annex 4.1: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.1 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.2: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.2 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.3: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.3 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.4: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.4 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.5: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.5 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.6: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.6 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.7: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.7 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.8: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.8 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.9: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.9 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.10: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.10 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.11: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.11 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.12: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.12 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.13: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.13 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 4.14: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 4.14 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

## Detailed Technical Annex for Chapter 5

The following technical specifications elaborate on the implementation details for Chapter 5 within the Method Matrix framework [`§5`].

### Annex 5.1: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.1 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.2: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.2 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.3: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.3 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.4: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.4 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.5: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.5 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.6: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.6 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.7: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.7 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.8: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.8 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.9: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.9 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.10: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.10 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.11: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.11 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.12: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.12 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.13: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.13 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 5.14: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 5.14 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

## Detailed Technical Annex for Chapter 6

The following technical specifications elaborate on the implementation details for Chapter 6 within the Method Matrix framework [`§6`].

### Annex 6.1: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.1 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.2: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.2 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.3: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.3 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.4: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.4 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.5: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.5 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.6: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.6 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.7: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.7 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.8: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.8 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.9: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.9 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.10: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.10 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.11: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.11 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.12: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.12 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.13: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.13 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 6.14: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 6.14 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

## Detailed Technical Annex for Chapter 7

The following technical specifications elaborate on the implementation details for Chapter 7 within the Method Matrix framework [`§7`].

### Annex 7.1: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.1 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.2: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.2 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.3: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.3 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.4: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.4 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.5: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.5 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.6: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.6 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.7: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.7 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.8: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.8 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.9: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.9 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.10: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.10 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.11: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.11 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.12: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.12 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.13: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.13 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

### Annex 7.14: Operational Protocol and Edge-Case Protections
This sub-annex governs protocol 7.14 across heterogeneous computational execution environments.
1. **Mathematical Foundation**: The physical model enforces variational energy conservation and momentum conservation across Cartesian space.
2. **Numerical Tolerance**: Convergence criteria mandate energy residual $\Delta E < 10^{-7}\text{ Ha}$ and RMS gradient $< 3 \times 10^{-6}\text{ Eh/bohr}$.
3. **Error Recovery**: In the event of non-convergence, the optimizer automatically switches step algorithms from BFGS to Rational Function Optimization (RFO).
4. **Provenance Metadata**: Execution timestamp, node host ID, compiler flags, and library hashes are logged to `fit_provenance.json` [`§12.5`].
5. **FAIR Data Serialization**: Output tensors are serialized to QCSchema JSON and HDF5 archives [`§8C.2`, `§20.2`].

# APPENDIX: METHOD MATRIX TIER TABLES & PARETO FRONTIER

## A.1 Summary Table of Method Matrix Tiers (T1–T10)

```
+-----------------------------------------------------------------------------------+
|                   SUMMARY OF METHOD MATRIX TIERS (T1 - T10)                       |
+------+----------------------+-----------------------+-----------------------------+
| Tier | Operational Domain   | Recommended Method    | Target Wall-Clock Budget    |
+------+----------------------+-----------------------+-----------------------------+
| T1   | Conformer Search     | GOAT r2SCAN-3c        | 10s, 1m, 30m, 1h, 3h, 12h   |
| T2   | PES Active Learning  | Delta-learning MLFF   | 1h, 12h, 1d, 3d, 1w         |
| T3   | Equilibrium Geom (Be)| junChS Composite      | 1m, 3h, 12h (Best de novo)  |
| T4   | Vibrational Avg (B0) | Product B Semi-exp R6 | 1m, 30m, 1h, 12h            |
| T5   | Interaction Energy   | CP-CCSD(T)/CBS        | 1h, 12h, 1d, 3d             |
| T6   | Secondary Obs        | PAS Dipoles / EFG     | 10s, 1m, 30m, 1h            |
| T7   | Internal Rotation    | 1D Relaxed Torsional  | 30m, 3h, 12h                |
| T8   | Vibrational (IR/THz) | Anharmonic VPT2       | 1h, 12h, 1d                 |
| T9   | Raman Spectra        | Polarizability Deriv  | 1h, 12h                     |
| T10  | NMR / UV-Vis / MS    | Shielding / TD-DFT    | 30m, 3h, 12h                |
+------+----------------------+-----------------------+-----------------------------+
```

## A.2 Pareto Frontier & Dominated Execution Pathways
CoChem v4 identifies optimal execution pathways along the Pareto frontier and explicitly flags **Dominated Pathways** that waste compute time without improving accuracy [`§15.1`–`§15.3`]:

```
+-----------------------------------------------------------------------------------+
|                        DOMINATED EXECUTION PATHWAYS (§15.1)                       |
+------------------------------------+-----------------------+----------------------+ 
| Dominated / Prohibited Pathway     | Superior Pareto Row   | Rationale            |
+------------------------------------+-----------------------+----------------------+ 
| DLPNO-CCSD(T) Geometry Opt (T3O-1d)| junChS Composite      | DLPNO Opt is 10x     |
|                                    | (T3O-12h)             | slower & has grid    |
|                                    |                       | noise in gradient    |
+------------------------------------+-----------------------+----------------------+ 
| Additive Diffuse Increment         | Diffuse-in-base basis | Additive diffuse     |
| (aug-cc-pVTZ correction)           | (jun-cc-pVTZ)         | degrades MAE from    |
|                                    |                       | 1.5% to 12.7%! [M]   |
+------------------------------------+-----------------------+----------------------+ 
| Unconstrained r2SCAN-3c Dimer Opt  | Frozen-Monomer Protocol| Unconstrained Opt    |
|                                    | (Recipe R1-R4)        | distorts internal    |
|                                    |                       | monomer bonds        |
+------------------------------------+-----------------------+----------------------+ 
```

## A.3 Silent Failure Modes & Rejection Triggers
To prevent unphysical calculations from completing unnoticed, CoChem v4 installs 6 mandatory **Silent Failure Rejection Triggers** [`§16`]:
1. **Gradient Noise Floor Trap**: Abort when Float32 MLFF gradient noise halts optimizer progress.
2. **BSSE Geometry Collapse**: Reject non-counterpoised triple-zeta dimer optimizations exhibiting $R$ contraction $> 3\text{ pm}$.
3. **Multireference $T_1$ Trap**: Reject single-reference coupled-cluster calculations with $T_1 > 0.02$.
4. **Jensen's Inequality Inversion Trap**: Intercept scripts attempting $\frac{1}{\langle I \rangle}$ rotational constant averaging.
5. **ORCA `!ExtOpt` Sign Trap**: Intercept positive force returns in external MLFF calculators.
6. **Kraitchman Axis Singularity Trap**: Intercept isotopologue fits with substituted atoms $< 0.15\text{ \AA}$ from principal axes.

## A.4 Standing Rules & Mandatory Discipline Checklist
Every CoChem v4 workflow must satisfy the mandatory discipline checklist [`§12.5`, `§22`]:
- [x] All accuracy claims carry explicit `[M]`, `[D]`, or `[E]` provenance tags [`§12.5`].
- [x] No `[D]` or `[E]` tag solely supports a hardware exclusion or gating rule (Rule 7) [`§12.5`].
- [x] Target wall-clock budget selected from 10 standard tiers [`§Quick Start Card`].
- [x] Product Class (A, B, C) declared prior to search window generation [`§1.1`].
- [x] Legacy `Calc_Hess` replaced with `InHess XTB2` or `Lindh` [`§8B.3`].
- [x] Weak complexes use Frozen-Monomer Composite Protocol [`§9A`].
- [x] Geometry optimizations specify corrected `%geom` block (TolMaxG 1e-5) [`§4.4`].
- [x] Coupled-cluster VPT2 routed to CFOUR track; GOAT & single points to ORCA [`§9.1`].
- [x] Conformer search deploys Two-Stage GOAT + CREST deduplication [`§9B.1`].
- [x] Vibrational averaging respects Jensen's inequality $\left\langle \mathbf{I}^{-1} \right\rangle$ [`§5.1`].
- [x] Chapter 7 educational modules (PLAY, CURE, LABS, EVAL) fully integrated.

---
**End of CoChem v4 Master User Manual.**