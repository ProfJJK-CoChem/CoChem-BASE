# Architectural Survey: Method Matrix v4 Specifications & Geometry/Calculation Modules in CoChem-BASE (Task 2.2.1)
## Artifact: `task2_2_1_method_matrix_and_module_survey.md`

**Document Identifier:** `COCHEM-SURVEY-TASK2-2-1-2026` [M]  
**Document Version:** 2.0.0 (Comprehensive Technical Survey, 8-Module Empirical Audit & Baseline Gap Analysis) [M]  
**Work Breakdown Structure Package:** Level 2 Scope Definition / `WBS 2.2.1` [M]  
**Parent Work Order:** Level 1 Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) [M]  
**Governing Authority:** CoChem Agent Council / Method Matrix v4.1 / SRS Chunk 17 [M]  
**Designated Author Agent:** `cochem-sdp-manager` (Software Development Project Manager & SWEBOK Architect) [M]  
**Supervising Swarm Authority:** `0rchestrator` (Swarm Workflow Supervisor) [M]  
**Auditing Authorities:** `cochem-audit` (Static AST & QA Auditor) & `adversary` (Independent Hostile Red-Team Auditor) [M]  
**Governing Standards:** PMBOK Guide 7th Edition, IEEE 830-1998, ISO/IEC/IEEE 29148:2018, SWEBOK v3/v4, Anti-Spoofing Protocol v4 [M]  
**Primary Persistence Path:** [`C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md) [M]  
**Repository Mirror Path:** [`D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_1_method_matrix_and_module_survey.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_1_method_matrix_and_module_survey.md) [M]  
**Ecosystem Dropzone Path:** [`D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_1_method_matrix_and_module_survey.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_1_method_matrix_and_module_survey.md) [M]  
**Lifecycle Status:** `APPROVED_SURVEY_BASELINE` [M]  
**Timestamp:** `2026-09-10T17:45:00-05:00` [M]  

---

## Provenance Taxonomy Key
Every requirement, metric, derivation, data schema, and technical finding in this survey carries an explicit provenance tag in strict accordance with the CoChem Method Matrix v4.1 governance baseline [M]:
- **`[M]` (Methodological / Mandatory):** Invariant system requirement, architectural governance gate, fail-closed policy, or protocol mandate established by CoChem Agent Council rulings.
- **`[D]` (Deterministic / Domain Physics):** Mathematically derived relation, physical law, standard definition, literature theoretical benchmark, or formal data schema.
- **`[E]` (Empirical / Experimental):** Measured benchmark timing, experimental spectroscopic observation, wall-clock performance, or forensic audit finding.
- **`[PROC]` (Procedural / Workflow):** Standard operating procedure, dispatch protocol, lifecycle gate, or project management convention.

---

## 1. Executive Summary & Survey Objectives

### 1.1 Scope Harmonization: Level 1 Task 2 and Level 2 Breakdown
Level 1 Task 2 governs the implementation of the **High-Precision Geometry Optimization Engine and Frozen Monomer Protocol (FMP)** across the `CoChem-BASE` platform to satisfy **Verification Requirements VR-02 and VR-04** (SRS Chunk 17). 

At Level 2, the engineering requirements demand formal specification of:
1. **Recipe R1 and Recipe R2 internal coordinate constraint generation** to eliminate unphysical DFT covalent monomer distortion while relaxing strictly the 6 intermolecular degrees of freedom ($R, \theta_1, \theta_2, \phi, \tau$) [M].
2. **Residual gradient parsing on frozen monomer coordinates** ($\mathbf{g}_{\text{residual}} = \left. \nabla E \right|_{\text{frozen}}$) to detect and flag geometric strain between frozen monomer geometries and underlying DFT potential energy surfaces [M].
3. **Mandatory injection of the Quintuple Stationary Convergence Block** (`TolE 1e-7`, `TolMaxG 1e-5`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`, `MaxIter 200`), eliminating shallow potential energy surface trapping and false local minima [M].
4. **Initial model Hessian preconditioning discipline** (`InHess XTB2` or `InHess Lindh`) and **multi-stage Hessian chaining**, coupled with an absolute architectural ban on `Calc_Hess true` for optimizations [M].

### 1.2 Purpose of Specific Task 2.2.1
Task 2.2.1 conducts an exhaustive, tool-verified survey of:
1. The governing scientific and procedural mandates codified in **Method Matrix v4.1** (§4.4, §QS-1, §8B.3, §9A, §9A.1, §9A.2, §9A.5, §10.2–§10.3) and **SRS Chunk 17** [M].
2. The current implementation state of all eight relevant geometry, calculation, screening, routing, and exception modules in `src/cochem_base/` [M].
3. The empirical gap between existing codebase routines and the downstream implementation requirements of WBS 2.2 through 2.5 [M].
4. The concrete technical interface contracts and Pydantic data schemas required for fail-closed quantum chemistry workflows [M].

### 1.3 Standards Compliance Statement
This document is authored in strict compliance with:
- **PMBOK Guide 7th Edition:** Systems View for Project Delivery, Scope Management Domain (100% Rule), and Quality Management Domain [M].
- **SWEBOK v3/v4:** Software Requirements, Software Architecture & Design, and Software Construction [M].
- **IEEE 830-1998 / ISO/IEC/IEEE 29148:2018:** Software Requirements Specifications [M].
- **CoChem Anti-Spoofing Directive v4:** Total eradication of synthetic mocks (`unittest.mock`, `MagicMock`), dead-end stubs (`NotImplementedError`, bare `pass`), fake coordinate arrays (`np.zeros`, `np.ones`), and enforcement of dynamic mass/radii retrieval via `mendeleev` [M].

---

## 2. Method Matrix v4 Authoritative Specification Survey

### 2.1 The Error Propagation Sensitivity Law: $\mathrm{d}B/B = -2 \mathrm{d}R/R$ (§3.0, §9A.1)
For a weakly bound intermolecular dimer (such as $\text{CO}_2\cdots\text{H}_2\text{O}$), the principal moment of inertia perpendicular to the intermolecular vector is approximated by $I \approx \mu R^2$, where $\mu = \frac{m_A m_B}{m_A + m_B}$ is the reduced mass of the dimer and $R$ is the intermolecular separation [D]. The rotational constant $B$ in MHz is defined as:

$$B = \frac{\hbar}{4\pi I} = \frac{\hbar}{4\pi \mu R^2} \quad [\text{D}]$$

Taking the logarithmic derivative with respect to intermolecular distance $R$:

$$\ln B = \ln\left(\frac{\hbar}{4\pi\mu}\right) - 2 \ln R \implies \frac{\mathrm{d}B}{B} = -2 \frac{\mathrm{d}R}{R} \quad [\text{D}]$$

#### Quantitative Physical Implications:
- At an intermolecular separation of $R \approx 3.0\text{ \AA}$, a spatial displacement error of merely $\Delta R = 0.003\text{ \AA}$ ($3.0\text{ pm}$) generates a relative error in $B$ of:
  $$\left|\frac{\Delta B}{B}\right| = 2 \times \frac{0.003\text{ \AA}}{3.0\text{ \AA}} = 0.0020 = 0.20\% \quad [\text{D}]$$
  This immediately violates the Product C microwave spectral line matching gate ($\le 0.10\%$) [D].
- To achieve high-fidelity Product C microwave line matching ($\le 0.05\%$), the intermolecular distance must be converged to $\Delta R \le 0.00075\text{ \AA}$ ($0.75\text{ pm}$) [D].

### 2.2 The Force Constant Disparity Benchmark (§2.6, §9A.1)
Weak van der Waals and hydrogen-bonded complexes exhibit an extreme stiffness mismatch between intramolecular covalent bonds and intermolecular interaction modes [D]:
1. **Intramolecular Covalent Modes:** Harmonic force constants $k_{\text{cov}} \approx 5.0 - 10.0\text{ mdyn/\AA} = 0.32 - 0.64\text{ Eh/bohr}^2$; vibrational frequencies $\omega \approx 1000 - 3800\text{ cm}^{-1}$ [D].
2. **Intermolecular van der Waals Modes:** Harmonic force constants $k_{\text{vdW}} \approx 0.05 - 0.07\text{ mdyn/\AA} = 3.2 \times 10^{-3} - 4.5 \times 10^{-3}\text{ Eh/bohr}^2$; vibrational frequencies $\omega \approx 20 - 150\text{ cm}^{-1}$ [D].

#### Fraser Experimental Benchmark ($k = 0.069\text{ mdyn/\AA} = 4.4 \times 10^{-3}\text{ Eh/bohr}^2$ for $\text{H}_2\text{CO}\cdots\text{HCl}$) [E]:
- **Under Standard ORCA `!Opt` ($\mathrm{TolMaxG} = 3.0 \times 10^{-4}\text{ a.u.}$):**
  $$\Delta r \approx \frac{g}{k} = \frac{3.0 \times 10^{-4}\text{ a.u.}}{4.4 \times 10^{-3}\text{ a.u./bohr}} = 0.0682\text{ bohr} = 0.0361\text{ \AA} = 3.61\text{ pm} \quad [\text{D}]$$
  At $R = 3.5\text{ \AA}$, $\frac{\Delta B}{B} \approx 2 \times \frac{0.0361}{3.5} \approx 2.06\%$, completely destroying microwave spectral prediction [D].
- **Under `!VeryTightOpt` ($\mathrm{TolMaxG} = 3.0 \times 10^{-5}\text{ a.u.}$):**
  $$\Delta r \approx 0.0068\text{ bohr} = 0.0036\text{ \AA} \implies \frac{\Delta B}{B} \approx 0.21\% \quad [\text{D}]$$
  Still over double the Product C spectroscopic threshold ($0.10\%$) [D].
- **Under Method Matrix Quintuple Block ($\mathrm{TolMaxG} = 1.0 \times 10^{-5}\text{ a.u.}$):**
  $$\Delta r \le \frac{1.0 \times 10^{-5}}{4.4 \times 10^{-3}} = 0.00227\text{ bohr} = 0.0012\text{ \AA} = 0.12\text{ pm} \implies \frac{\Delta B}{B} \le 0.069\% \le 0.07\% \quad [\text{D}]$$
  Guarantees that the stationary point geometry lies within the microwave experimental error envelope [D].

### 2.3 The Frozen Monomer Protocol: Recipe R1 & Recipe R2 (§9A, §9A.1, §9A.2, §9A.5)
In standard unconstrained optimizations of weak complexes, density functional theory (DFT) methods waste $80\% - 90\%$ of their optimization steps distorting stiff covalent monomer bonds by $0.005 - 0.015\text{ \AA}$ while leaving the shallow intermolecular coordinate trapped in numerical quadrature noise [D].

In $\text{CO}_2\cdots\text{H}_2\text{O}$ at $R = 2.836\text{ \AA}$, an intermolecular positioning error of $\Delta R = 0.002\text{ \AA}$ produces the exact same shift in rotational constant $B$ as a $16.8\text{ m\AA}$ uniform monomer bond distortion—an error magnitude that no state-of-the-art ab initio calculation commits covalently ($\text{fc-CCSD(T)/cc-pVTZ}$ errors are $\le 3\text{ m\AA}$) [D].

Therefore, Method Matrix v4 mandates the Frozen Monomer Protocol (FMP):
- **Recipe R1 (High-Throughput Pre-Optimization & Screening) [M]:**
  1. Ingest authoritative experimental substitution geometries ($r_e^{\text{SE}}$ from microwave measurements or CCCBDB benchmarks) [D].
  2. Freeze all intramolecular internal coordinates (bonds, angles, dihedrals) via ORCA `%geom Constraints` blocks [M].
  3. Relax strictly the 6 intermolecular degrees of freedom ($R, \theta_1, \theta_2, \phi, \tau$) at the $\text{r}^2\text{SCAN-3c}$ composite DFT level [M].
  4. Never append external `D4` or `gCP` tokens because both corrections are natively parameterized inside the $\text{r}^2\text{SCAN-3c}$ composite model [M].
- **Recipe R2 (Production Spectroscopic Prediction) [M]:**
  1. Ingest high-accuracy monomer geometries computed at the canonical $\text{CCSD(T)/CBS}$ or $\text{fc-CCSD(T)/cc-pVTZ}$ level [D].
  2. Lock all monomer internal degrees of freedom via identical internal coordinate constraints [M].
  3. Relax the 6 intermolecular degrees of freedom at the $\omega\text{B97M-V/def2-QZVPP}$ level using `DEFGRID3` and counterpoise (CP) correction bracketing [M]. Provides sub-$0.02\text{ \AA}$ intermolecular geometry accuracy [M].
  4. Never add external `D4` to $\omega\text{B97M-V}$ because its non-local VV10 kernel already provides rigorous dispersion treatment (§9A.7) [M].

### 2.4 Quintuple Stationary Convergence Block (§4.4, §QS-1)
To ensure potential energy surface stationarity on flat non-covalent landscapes, all Product A and Product C geometry optimizations must inject the following tightened `%geom` convergence block [M]:

```orca
%geom
  TolE     1.0e-07   # Energy change convergence threshold (Eh) [M]
  TolRMSG  3.0e-06   # RMS gradient across active coordinates (Eh/bohr) [M]
  TolMaxG  1.0e-05   # Maximum force component on active coordinates (Eh/bohr) [M]
  TolRMSD  5.0e-05   # RMS displacement threshold in native atomic units (bohr) [M]
  TolMaxD  1.0e-04   # Maximum displacement threshold in native atomic units (bohr) [M]
  MaxIter  200       # Prevent premature step-count aborts on flat surfaces [M]
end
```

> [!CAUTION]
> **Dimensional Units Invariant:** ORCA `%geom` processes displacement tolerances (`TolMaxD`, `TolRMSD`) natively in **atomic units (Bohr)** ($1\text{ bohr} \approx 0.529177\text{ \AA}$). Specifying displacement tolerances in Ångströms introduces a $1.8897\times$ scaling distortion that invalidates stationary point certification [M].

### 2.5 Model Hessian Discipline: Absolute Ban on `Calc_Hess true` (§8B.3)
- **Wall-Clock Penalty:** Computing an exact analytical or numerical Hessian at the initial non-equilibrium geometry consumes $75\% - 85\%$ of the total job wall-clock time [D]. Because quasi-Newton optimizers (BFGS, GDIIS) immediately update and overwrite force constants with displacement vectors, this initial computational expenditure is entirely discarded [D].
- **Method Matrix Mandate:**
  1. `Calc_Hess true` is **strictly forbidden** for geometry optimizations and must raise `HessianSpecificationError` / `MethodologyViolationError` [M].
  2. All geometry optimizations must seed the initial Hessian using low-cost model force fields:
     - `InHess XTB2`: Semi-empirical GFN2-xTB model Hessian [M].
     - `InHess Lindh`: Lindh's empirical distance-dependent model force field [M].
  3. Multi-stage optimization pipelines (e.g., Recipe R1 $\to$ Recipe R2) must forward the converged Hessian from the previous stage via `InHessName "stage1.opt"` or `InHess READ` [M].

### 2.6 Conservative Analytical Gradients & Residual Gradient Parsing (§10.2–§10.3)
Because an experimental or $\text{CCSD(T)}$ monomer equilibrium geometry is not an exact stationary point on an approximate DFT exchange-correlation potential energy surface, a non-zero residual force acts on the frozen monomer atoms [D]:

$$\mathbf{g}_{\text{residual}} = \left. \nabla_{\mathbf{R}_{\text{internal}}} E_{\text{DFT}} \right|_{\text{frozen}} \in \mathbb{R}^{3N} \quad [\text{D}]$$

The optimization engine must parse and record the maximum residual gradient infinity norm:

$$\|\mathbf{g}_{\text{residual}}\|_{\infty} = \max_{k} |g_{\text{residual}, k}| \quad [\text{D}]$$

- If $\|\mathbf{g}_{\text{residual}}\|_{\infty} \le 1.0 \times 10^{-4}\text{ a.u.}$: The frozen monomer structure is in energetic harmony with the DFT functional, and the geometry is certified without caveat [M].
- If $\|\mathbf{g}_{\text{residual}}\|_{\infty} > 1.0 \times 10^{-4}\text{ a.u.}$: Significant geometric strain exists between the frozen monomer reference and the DFT functional. The system must issue a `GeometricStrainWarning` and record an explicit geometric strain caveat in output metadata and downstream QCSchema documents [M].

#### Sign and Unit Conversions (§10.3):
$$\text{input coordinates: \AA}, \quad \text{output energy: Eh}, \quad \text{output gradient: Eh/bohr}$$
Conversions from ASE $(\text{eV, eV/\AA})$:
$$E_{\text{Eh}} = E_{\text{eV}} / 27.211386245988$$
$$g_{\text{Eh}/a_0} = (-F_{\text{eV/\AA}}) \times 0.529177210903 / 27.211386245988$$
The negative sign flip is mandatory because molecular mechanics engines emit forces $\mathbf{F} = -\nabla E$ while quantum chemical optimizers require the energy gradient $\nabla E$ [D].

---

## 3. CoChem-BASE Codebase Module Survey & Gap Analysis

A rigorous, tool-based source code audit of all eight existing modules in `D:/__CoChem/GitHub-Repo/CoChem-BASE` reveals the current functional baseline and identifies critical architectural gaps:

### 3.1 Module 1: `src/cochem_base/geometry/fragment_partitioner.py` (194 lines, 8038 bytes)
- **Existing Capabilities:**
  * Implements `get_covalent_radius_angstrom` querying `mendeleev.element` [M].
  * Implements `detect_molecular_fragments` via BFS connectivity on covalent radii adjacency graphs [M].
  * Implements `validate_no_calc_hess` scanning for `(?i)calc_hess\s+true` and raising `MethodologyViolationError` [M].
  * Implements `generate_frozen_monomer_orca_block` generating `%geom` blocks with `TolMaxG 1e-5`, `TolRMSG 3e-6`, `TolMaxD 1e-4`, `TolRMSD 5e-5`, `TolE 1e-7`, `InHess XTB2`, and `{ B ... }`, `{ A ... }` constraints [M].
- **Identified Deficiencies & Gaps:**
  1. *Missing Proper Dihedrals:* `generate_frozen_monomer_orca_block` generates bonds and valence angles, but lacks proper dihedral `{ D i j k l C }` constraint generation for multi-atom monomers ($\ge 4$ atoms), leaving conformational torsional degrees of freedom unconstrained [M].
  2. *Missing `MaxIter 200`:* Lines 180–191 omit `MaxIter 200` in the emitted `%geom` block [M].
  3. *Unconnected to Typed Contracts:* Functions return raw strings instead of structured `FrozenConstraintPayload` or `RecipeConstraintConfig` models [M].
  4. *No Trajectory Drift Validator:* Does not validate trajectory coordinate drift [M].

### 3.2 Module 2: `src/cochem_base/geometry/constraints.py` (423 lines, 17422 bytes)
- **Existing Capabilities:**
  * Implements `FrozenConstraintPayload` (Pydantic model) with canonical sorting of bonds, angles, and proper dihedrals, and disjoint monomer validation [M].
  * Implements `get_dynamic_covalent_radius` with multi-tier Mendeleev resolution (Pyykkö $\to$ Cordero $\to$ default) [M].
  * Implements `build_molecular_graph_from_geometry` ensuring zero intermolecular edges [M].
  * Implements `generate_frozen_monomer_constraints` constructing all intramolecular bonds, angles, and proper dihedrals for Monomer A and B [M].
  * Implements `format_orca_frozen_monomer_constraints_block` generating `%geom` with `TolE 1e-7`, `TolRMSG 3e-6`, `TolMaxG 1e-5`, `TolRMSD 5e-5`, `TolMaxD 1e-4`, `MaxIter 200`, and `Constraints` [M].
  * Implements `validate_trajectory_monomer_drift` checking internal distances across frames and raising `TrajectoryDriftViolationError` if drift $\ge 1.0 \times 10^{-6}\text{ \AA}$ [M].
- **Identified Deficiencies & Gaps:**
  1. *Lack of Recipe R1 / Recipe R2 Scaffolding:* Lacks high-level helpers tying monomer library geometries ($r_e^{\text{SE}}$ vs $\text{CCSD(T)/CBS}$) to automated constraint deck compilation [M].
  2. *Decoupled from Input Generator:* `generate_orca_input` does not ingest `FrozenConstraintPayload` directly; it relies on an internal legacy routine `build_internal_coordinate_constraints` [M].

### 3.3 Module 3: `src/cochem_base/geometry/vdw_screener.py` (121 lines, 4783 bytes)
- **Existing Capabilities:**
  * Implements `VanDerWaalsDistanceScreener` with dynamic Mendeleev vdW radii retrieval [M].
  * Implements `validate_complex_separation` verifying that the minimum inter-fragment distance falls within the physical contact window $[R_{\text{vdw}} - 0.30\text{ \AA}, R_{\text{vdw}} + 0.80\text{ \AA}]$ with hydrogen-bonding penetration allowances [M].
  * Detects steric clashing ($R_{\min} < 1.0\text{ \AA}$) and unphysical dissociation ($R_{\min} > 8.0\text{ \AA}$), raising `IntermolecularTopologyError` [M].
- **Identified Deficiencies & Gaps:**
  1. *Preflight Only:* Operates exclusively on initial coordinates; does not track intermolecular separation during trajectory steps or post-optimization verification [M].
  2. *Lacks Integration with Recipe R1/R2 Pipelines:* Does not feed screening status forward to `MoleculeInput` or execution router [M].

### 3.4 Module 4: `src/cochem_base/calc/cochem_calc_input_generator.py` (406 lines, 16595 bytes)
- **Existing Capabilities:**
  * Implements `MoleculeInput` with automatic stripping of `Calc_Hess true` in `validate_method_matrix` [M].
  * Enforces `defgrid3` for frequency/Hessian tasks and transition metals [M].
  * Implements `generate_orca_input` injecting `%geom` with `TolE 1e-7`, `TolMaxG 1e-5`, `TolRMSG 3e-6`, `TolMaxD 1e-4`, `TolRMSD 5e-5`, `InHess XTB2`, and internal constraints [M].
  * Implements `validate_rotational_mode_stability` checking Rodrigues rotation invariance for modes $< 50\text{ cm}^{-1}$ [M].
- **Identified Deficiencies & Gaps (CRITICAL):**
  1. *Missing `MaxIter 200`:* `generate_orca_input` (lines 224–232) injects the 5 numerical thresholds and `InHess XTB2`, but **completely omits `MaxIter 200`** in the generated ORCA input deck! This causes flat van der Waals optimizations to abort prematurely at ORCA's default step limit and violates `test_vr04_quintuple_stationary_block_and_model_hessian` [M].
  2. *Legacy Constraint Generator:* Relies on `build_internal_coordinate_constraints` which takes a single flat list `frozen_monomer_indices` rather than separated monomer subsets (`atoms_a`, `atoms_b`), risking accidental intermolecular constraints if fragments touch [M].
  3. *No Chained Hessian Forwarding:* Lacks support for `InHess READ` or `InHessName "stage1.opt"` [M].
  4. *No Recipe R1 / R2 Presets:* Theory level is passed as an unstructured string without structured recipe orchestration [M].

### 3.5 Module 5: `src/cochem_base/calc/cochem_calc_output_parser.py` (202 lines, 8157 bytes)
- **Existing Capabilities:**
  * Implements `QuantumParser` verifying SCF convergence ($\Delta E < 1.0 \times 10^{-7}\text{ Eh}$), auxiliary basis saturation, and spin contamination ($\Delta \langle S^2 \rangle$) [M].
  * Implements QCSchema serialization and POSIX immutable locking (`chmod 0o444`) [M].
- **Identified Deficiencies & Gaps (CRITICAL BLOCKERS):**
  1. *Missing `OutputParser` Class Export:* The class is named `QuantumParser`. However, `tests/test_chunk17_verification_suite.py` line 46 imports `from cochem_base.calc.cochem_calc_output_parser import OutputParser`. This causes an immediate `ImportError` on test execution [M]!
  2. *Completely Missing `parse_residual_gradients`:* The module contains **zero logic** for parsing residual gradients from ORCA logs, `.engrad` files, or `.opt` trajectories [M].
  3. *Completely Missing Quintuple Stationary Point Convergence Verification:* Does not parse or verify the 5 stationary convergence criteria (`TolE`, `TolMaxG`, `TolRMSG`, `TolMaxD`, `TolRMSD`) from the ORCA optimization cycle blocks [M].
  4. *No Geometric Strain Warning Generation:* Does not evaluate $\|\mathbf{g}_{\text{residual}}\|_{\infty}$ against $1.0 \times 10^{-4}\text{ a.u.}$ or emit `GeometricStrainWarning` [M].

### 3.6 Module 6: `src/cochem_base/calc/cochem_grid_convergence.py` (1444 lines, 63405 bytes)
- **Existing Capabilities:**
  * Comprehensive implementation of grid convergence testing across `DEFGRID1`, `DEFGRID2`, `DEFGRID3` [M].
  * Implements dynamic mass retrieval via `mendeleev`, rigid-rotor moment of inertia evaluation, rotational constant conversion ($505379.0\text{ MHz}\cdot\text{amu}\cdot\text{\AA}^2$), and Ray's asymmetry parameter [M].
  * Validates rotational invariance under 45° Rodrigues rotation around $[1, 1, 1]/\sqrt{3}$ [M].
- **Identified Deficiencies & Gaps:**
  * Highly specialized for standalone grid sensitivity sweeps; needs seamless linkage with multi-stage Recipe R1 $\to$ Recipe R2 grid tightening workflows (`DEFGRID1` for screening $\to$ `DEFGRID3` for production optimization) [M].

### 3.7 Module 7: `src/cochem_base/calc/cochem_calc_execution_router.py` (394 lines, 16430 bytes)
- **Existing Capabilities:**
  * Routes calculations across Parsl multi-executor topologies (`cochem_anchor_cpu`, `cochem_scout_gpu`) and local subprocess execution [M].
  * Manages Ring 2 sandboxed execution scratch directories and task lifecycle [M].
  * Validates hardware capacities and config profiles [M].
- **Identified Deficiencies & Gaps:**
  1. *No FMP / Quintuple Route Awareness:* Router passes raw input decks without validating that intermolecular jobs carry required `%geom` constraints or chained Hessian references [M].
  2. *Missing Automated Hessian File Transport:* Does not automatically copy or link predecessor `.opt` / `.carthess` files across chained execution sandboxes [M].

### 3.8 Module 8: `src/cochem_base/exceptions.py` (1558 lines, 60379 bytes)
- **Existing Capabilities:**
  * Implements comprehensive exception hierarchy with `ProvenanceErrorCode` enum [M].
  * Implements `HessianSpecificationError` (line 588) with `INVALID_HESSIAN_STRATEGY` [M].
  * Implements `GeometryConvergenceError` (line 610) with `CONVERGENCE_FAILURE` [M].
  * Implements `TrajectoryDriftViolationError` (line 632) with `FROZEN_MONOMER_VIOLATION` [M].
  * Implements `GeometricStrainWarning` (line 1163) [M].
  * All classes registered in `_EXCEPTION_REGISTRY` and exported in `__all__` [M].
- **Identified Deficiencies & Gaps:**
  * Missing canonical semantic alias names referenced in downstream specification documents:
    - `ForbiddenExactHessianError` (alias of `HessianSpecificationError`) [M].
    - `StationaryConvergenceFailureError` (alias of `GeometryConvergenceError`) [M].
    - `FrozenCoordinateDriftError` (alias of `TrajectoryDriftViolationError`) [M].
    - `ResidualStrainWarning` (alias of `GeometricStrainWarning`) [M].

---

### 3.9 Detailed Gap Analysis Matrix

| Module | Feature / Requirement | Current Module State | Gap Identified | Severity | Remediation Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `cochem_calc_input_generator.py` | **Quintuple Block: `MaxIter 200`** | Injects 5 thresholds; omits `MaxIter 200` | `generate_orca_input` omits `MaxIter 200` | **HIGH** | Inject `MaxIter 200` into `cochem_calc_input_generator.py:geom_block_lines` |
| `cochem_calc_output_parser.py` | **Output Parser: Class Identity** | Defines `QuantumParser` | `test_chunk17` imports `OutputParser`; causes `ImportError` | **BLOCKER** | Export `OutputParser = QuantumParser` alias or unify class naming |
| `cochem_calc_output_parser.py` | **Residual Gradient Parsing** | Absent across entire module | `parse_residual_gradients` not implemented anywhere | **BLOCKER** | Implement `parse_residual_gradients` in `cochem_calc_output_parser.py` |
| `cochem_calc_output_parser.py` | **Quintuple Convergence Parser** | Only SCF convergence (`dE < 1e-7`) parsed | Geometry step criteria (`TolMaxG`, etc.) not parsed from logs | **HIGH** | Add multi-threshold geometry convergence parser extracting all 5 values |
| `cochem_calc_input_generator.py` | **Model Hessian Chaining** | Only static `InHess XTB2` injected | Lacks `InHess READ` / `InHessName` forwarding for multi-stage jobs | **MEDIUM** | Implement `HessianChainingConfig` and chained forwarding in input generator |
| `fragment_partitioner.py` | **Proper Dihedral Constraints** | Generates bonds and angles only | Monomers with $\ge 4$ atoms leave dihedrals unconstrained in partitioner | **MEDIUM** | Align `fragment_partitioner.py` to invoke `generate_frozen_monomer_constraints` |
| `fragment_partitioner.py` | **`MaxIter 200` in %geom block** | Injects 5 thresholds; omits `MaxIter 200` | Lines 180-191 omit `MaxIter 200` | **MEDIUM** | Add `MaxIter 200` to `generate_frozen_monomer_orca_block` |
| `constraints.py` | **Recipe R1 / R2 Scaffolding** | Manual keyword composition required | No dedicated high-level orchestrator for R1 ($r_e^{\text{SE}}$/r2SCAN-3c) and R2 (CCSD(T)/$\omega\text{B97M-V}$) | **MEDIUM** | Implement `RecipeConstraintConfig` and factory functions in `constraints.py` |
| `vdw_screener.py` | **Pipeline Integration** | Standalone preflight checks only | Does not validate post-optimization coordinates or chain status | **LOW** | Connect screener into optimization post-flight verification pipeline |
| `cochem_calc_execution_router.py` | **Chained Hessian File Transport** | Sandboxes scratch without Hessian copy | Predecessor `.opt` / `.hess` files not automatically staged | **MEDIUM** | Add Hessian staging handler in `ExecutionRouter` |
| `exceptions.py` | **Canonical Alias Exports** | Primary classes defined under base names | Canonical aliases (`ForbiddenExactHessianError`, etc.) not aliased | **LOW** | Export aliases in `exceptions.py` and `__all__` |

---

## 4. Technical Interface Contracts & Data Models Baseline

To satisfy SWEBOK v3/v4 Software Design principles and eliminate unstructured dictionaries, the following concrete data models are established as the engineering baseline for Level 2 deliverables:

### 4.1 `RecipeConstraintConfig` Data Model
Specifies the Frozen Monomer Protocol recipe type, authoritative monomer geometries, and atom partitioning:

```python
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Sequence, Union
from pydantic import BaseModel, Field, field_validator


class RecipeType(str, Enum):
    """Authoritative FMP recipe classification under Method Matrix v4 §9A."""
    R1 = "Recipe_R1"  # r2SCAN-3c with experimental/microwave re^SE monomers
    R2 = "Recipe_R2"  # wB97M-V/def2-QZVPP with CCSD(T)/CBS monomers


class RecipeConstraintConfig(BaseModel):
    """Configuration contract governing Recipe R1 and Recipe R2 optimization decks."""
    recipe_type: RecipeType = Field(
        ...,
        description="FMP recipe classification: Recipe_R1 or Recipe_R2 [M]."
    )
    monomer_a_indices: List[int] = Field(
        ...,
        min_length=1,
        description="0-based atom indices belonging to Monomer A [M]."
    )
    monomer_b_indices: List[int] = Field(
        ...,
        min_length=1,
        description="0-based atom indices belonging to Monomer B [M]."
    )
    monomer_a_source: str = Field(
        default="experimental_microwave_re_SE",
        description="Origin of Monomer A coordinates (e.g. CCCBDB, microwave re^SE, CCSD(T)/CBS) [D]."
    )
    monomer_b_source: str = Field(
        default="experimental_microwave_re_SE",
        description="Origin of Monomer B coordinates [D]."
    )
    freeze_intramolecular: bool = Field(
        default=True,
        description="Whether to generate internal coordinate constraints freezing both monomers [M]."
    )
    use_counterpoise: bool = Field(
        default=True,
        description="Whether to enable counterpoise (CP) correction bracketing in Recipe R2 [M]."
    )

    @field_validator("monomer_b_indices")
    @classmethod
    def validate_disjoint_subsets(cls, v: List[int], info) -> List[int]:
        """Assert Monomer A and Monomer B index sets are strictly disjoint."""
        a_indices = info.data.get("monomer_a_indices", [])
        set_a = set(a_indices)
        set_b = set(v)
        if not set_a.isdisjoint(set_b):
            overlap = set_a.intersection(set_b)
            raise ValueError(f"Monomer A and B must be strictly disjoint. Overlapping indices: {overlap} [M].")
        return v
```

### 4.2 `QuintupleConvergenceCriteria` Data Model
Holds the five mandatory numerical convergence thresholds:

```python
class QuintupleConvergenceCriteria(BaseModel):
    """Encapsulates the five stationary convergence thresholds mandated by Method Matrix v4 §4.4."""
    tol_e: float = Field(
        default=1.0e-07,
        description="Energy change threshold between steps in Hartree (Eh) [M]."
    )
    tol_rms_g: float = Field(
        default=3.0e-06,
        description="RMS gradient convergence threshold in Eh/bohr [M]."
    )
    tol_max_g: float = Field(
        default=1.0e-05,
        description="Maximum gradient convergence threshold in Eh/bohr [M]."
    )
    tol_rms_d: float = Field(
        default=5.0e-05,
        description="RMS coordinate displacement threshold in native atomic units (bohr) [M]."
    )
    tol_max_d: float = Field(
        default=1.0e-04,
        description="Maximum coordinate displacement threshold in native atomic units (bohr) [M]."
    )
    max_iter: int = Field(
        default=200,
        ge=50,
        le=1000,
        description="Maximum optimization step count [M]."
    )

    def to_orca_geom_block(self) -> List[str]:
        """Serializes thresholds into ORCA %geom directive lines."""
        return [
            f"  TolE {self.tol_e:.1e}".replace("e-0", "e-"),
            f"  TolMaxG {self.tol_max_g:.1e}".replace("e-0", "e-"),
            f"  TolRMSG {self.tol_rms_g:.1e}".replace("e-0", "e-"),
            f"  TolMaxD {self.tol_max_d:.1e}".replace("e-0", "e-"),
            f"  TolRMSD {self.tol_rms_d:.1e}".replace("e-0", "e-"),
            f"  MaxIter {self.max_iter}",
        ]
```

### 4.3 `QuintupleConvergenceResult` Data Model
Captures the evaluated convergence state parsed from quantum chemical optimization logs:

```python
class QuintupleConvergenceResult(BaseModel):
    """Detailed evaluation result of the 5 stationary convergence criteria from an optimization log."""
    energy_change: Optional[float] = Field(None, description="Actual final delta E (Eh) [M]")
    rms_gradient: Optional[float] = Field(None, description="Actual final RMS gradient (Eh/bohr) [M]")
    max_gradient: Optional[float] = Field(None, description="Actual final Max gradient (Eh/bohr) [M]")
    rms_displacement: Optional[float] = Field(None, description="Actual final RMS displacement (bohr) [M]")
    max_displacement: Optional[float] = Field(None, description="Actual final Max displacement (bohr) [M]")

    tol_e_converged: bool = Field(False, description="Whether delta E <= TolE [M]")
    tol_rms_g_converged: bool = Field(False, description="Whether RMS gradient <= TolRMSG [M]")
    tol_max_g_converged: bool = Field(False, description="Whether Max gradient <= TolMaxG [M]")
    tol_rms_d_converged: bool = Field(False, description="Whether RMS displacement <= TolRMSD [M]")
    tol_max_d_converged: bool = Field(False, description="Whether Max displacement <= TolMaxD [M]")

    all_criteria_met: bool = Field(False, description="True if and only if all 5 criteria converged [M]")
    step_count: int = Field(0, description="Total optimization cycles executed [M]")
```

### 4.4 `ResidualGradientSummary` Data Model
Encapsulates extracted residual gradients and geometric strain flags:

```python
class ResidualGradientSummary(BaseModel):
    """Telemetry contract storing parsed residual gradients on frozen monomer coordinates."""
    max_residual_gradient: float = Field(
        ...,
        description="Infinity norm ||g_residual||_inf across all frozen coordinates in Eh/bohr [D]."
    )
    rms_residual_gradient: Optional[float] = Field(
        default=None,
        description="RMS residual gradient across frozen coordinates in Eh/bohr [D]."
    )
    strain_threshold: float = Field(
        default=1.0e-04,
        description="Threshold in Eh/bohr above which geometric strain caveat is flagged [M]."
    )
    has_geometric_strain: bool = Field(
        ...,
        description="True if max_residual_gradient > strain_threshold [M]."
    )
    high_strain_atoms: List[int] = Field(
        default_factory=list,
        description="List of 0-based atom indices where |g_i| > strain_threshold [M]."
    )
```

### 4.5 `HessianChainingConfig` Data Model
Governs initial Hessian selection and multi-stage chaining:

```python
class HessianChainingConfig(BaseModel):
    """Configuration contract for initial model Hessian selection and multi-stage chaining."""
    mode: str = Field(
        default="XTB2",
        description="Initial Hessian mode: 'XTB2', 'Lindh', 'READ', or 'NAME' [M]."
    )
    predecessor_hessian_path: Optional[Path] = Field(
        default=None,
        description="Path to predecessor .opt or .hess file when mode is 'READ' or 'NAME' [M]."
    )
    allow_fallback_to_lindh: bool = Field(
        default=True,
        description="Whether to fall back to 'InHess Lindh' if xTB binary/license is unavailable [M]."
    )

    @field_validator("mode")
    @classmethod
    def reject_calc_hess(cls, v: str) -> str:
        """Reject any attempt to request exact initial Hessian calculation."""
        if "CALC_HESS" in v.upper():
            raise ValueError(
                "Exact Hessian calculation ('Calc_Hess true') is prohibited for optimizations (§8B.3) [M]."
            )
        return v
```

---

## 5. Verification Requirements & Acceptance Criteria Mapping (VR-02 & VR-04)

The deliverables designed in this survey map directly to the acceptance metrics defined in SRS Chunk 17 and tested in `test_chunk17_verification_suite.py`:

```
+====================================================================================================================+
|                              VERIFICATION REQUIREMENTS TRACEABILITY MATRIX                                         |
+========+============================+==============================+===============================================+
| Req ID | Target Requirement Scope   | Verification Method          | Exact Numerical Acceptance Threshold          |
+========+============================+==============================+===============================================+
| VR-02  | Frozen Monomer Protocol    | Integration Test             | Intramolecular monomer bond/angle drift       |
|        | (Recipe R1 & Recipe R2)    | (test_vr02_fmp_constraint_   | Delta r_max < 1.0e-6 Angstrom throughout run; |
|        | Internal Coordinate Locks  | generation_and_trajectory_   | Zero intermolecular constraints;              |
|        |                            | drift)                       | MaxIter 200 present in %geom [M].             |
+--------+----------------------------+------------------------------+-----------------------------------------------+
| VR-02  | Residual Gradient Parsing  | Output Parser Regression Test| Parse ||g_residual||_inf from .out / .engrad; |
|        | & Geometric Strain Alert   | (test_vr02_output_parser_    | max_g == 3.5e-4 a.u. verified;                |
|        |                            | residual_gradient_and_       | has_strain == True when > 1.0e-4 a.u. [M].    |
|        |                            | strain_caveat)               |                                               |
+--------+----------------------------+------------------------------+-----------------------------------------------+
| VR-04  | Quintuple Stationary Point | Syntax Deck & Parser Audit   | Strict injection of all 5 thresholds:         |
|        | Convergence Block          | (test_vr04_quintuple_        | TolE <= 1.0e-7 Eh, TolMaxG <= 1.0e-5 a.u.,    |
|        |                            | stationary_block_and_model_  | TolRMSG <= 3.0e-6 a.u., TolRMSD <= 5.0e-5 bohr|
|        |                            | hessian)                     | TolMaxD <= 1.0e-4 bohr, MaxIter 200 [M].      |
+--------+----------------------------+------------------------------+-----------------------------------------------+
| VR-04  | Model Hessian Discipline   | Syntax & Validator Audit     | Absolute ban on 'Calc_Hess true';             |
|        | & Chained Forwarding       | (test_vr04_quintuple_        | Auto-stripping by MoleculeInput validator;    |
|        |                            | stationary_block_and_model_  | InHess XTB2 or InHess Lindh injected [M].     |
|        |                            | hessian)                     |                                               |
+====================================================================================================================+
```

---

## 6. Swarm RACI Assignments for Downstream Level 2 Tasks

In strict accordance with PMBOK 7th Edition (Resource Management) and the CoChem Council Single-Accountability Rule (PCA-01), execution responsibilities for the downstream implementation microtasks are assigned unambiguously:

```
+============+===================================================================+-----+-----+-----+-----+-----+-----+
| WBS Task   | Microtask Title & Functional Component Scope                      | COD | TST | SDP | AUD | ADV | ORC |
+============+===================================================================+-----+-----+-----+-----+-----+-----+
| L3-T2-03   | Domain Exception Hierarchy Architecture (src/cochem_base/         |  R  |  I  |  C  |  C  |  I  |  A  |
|            | exceptions.py: alias exports, typed error registries)             |     |     |     |     |     |     |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-04   | Dynamic Wilson B-Matrix Internal Coordinate Construction          |  R  |  I  |  C  |  C  |  I  |  A  |
|            | (src/cochem_base/geometry/constraints.py: full proper dihedrals)  |     |     |     |     |     |     |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-05   | ORCA %geom Constraints Block Generator with MaxIter 200           |  R  |  I  |  C  |  C  |  I  |  A  |
|            | (cochem_calc_input_generator.py & constraints.py)                 |     |     |     |     |     |     |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-06   | Recipe R1 & Recipe R2 Orchestrated Scaffolding Functions          |  R  |  I  |  C  |  C  |  I  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-07   | Real-Time Trajectory Monomer Drift Validator (< 1.0e-6 Angstrom)  |  R  |  I  |  C  |  I  |  C  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-08   | Quintuple Stationary Convergence Parameter Injection (%geom)     |  R  |  I  |  C  |  C  |  I  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-09   | Automated Calc_Hess true Detection & Stripping Engine             |  R  |  I  |  C  |  I  |  C  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-10   | Semi-Empirical & Model Hessian Seeder (InHess XTB2 / Lindh)       |  R  |  I  |  C  |  C  |  I  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-11   | Chained Multi-Stage Optimization Hessian Forwarding Manager       |  R  |  I  |  C  |  C  |  I  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-12   | OutputParser Class Unification & Residual Gradient Parser         |  R  |  I  |  C  |  C  |  I  |  A  |
|            | (src/cochem_base/calc/cochem_calc_output_parser.py)               |     |     |     |     |     |     |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-13   | Maximum Residual Gradient ||g_res||_inf Extractor & Strain Alert  |  R  |  I  |  C  |  I  |  C  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-14   | QCSchema & Spectroscopic Telemetry JSON Serializer                |  R  |  I  |  C  |  C  |  I  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-15   | Authentic Zero-Mock Pytest Execution (VR-02 & VR-04 Suites)       |  I  |  R  |  C  |  C  |  C  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-16   | Windows UTF-8 Stream Hardening Verification (Zero CP1252 Crashes) |  I  |  R  |  C  |  C  |  I  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-17   | Static AST Anti-Spoof Linter Audit (strict=True, Zero Stubs)     |  I  |  I  |  C  |  R  |  C  |  A  |
+------------+-------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| L3-T2-18   | Asymmetric Red-Team Sign-Off & Atomic Swarm Ledger Sync           |  I  |  I  |  C  |  C  |  R  |  A  |
+============+===================================================================+-----+-----+-----+-----+-----+-----+
```

**Legend:**
- **COD:** `@cochem-coder` (Sole production code implementation agent)
- **TST:** `cochem-tester` (Pytest test suite execution and test verification specialist)
- **SDP:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK governance)
- **AUD:** `cochem-audit` (Static AST security and QA standards auditor)
- **ADV:** `adversary` (Independent zero-trust hostile red-team auditor)
- **ORC:** `0rchestrator` (Swarm workflow supervisor & final release authority)
- **R:** Responsible (Single accountable executor)
- **A:** Accountable (Final approval authority)
- **C:** Consulted (Subject matter input)
- **I:** Informed (Notified upon progress/completion)

---

## 7. Multi-Environment Risk Register & Mitigations

```
+==================================================================================================================================+
|                                     6-TIER RUNTIME ENVIRONMENT RISK REGISTER                                                     |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| ID  | Target Runtime    | Identified Environmental Failure Mode       | Likl. | Impact | Concrete Architectural Mitigation| Owner |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R01 | Local-Windows     | Windows CP1252 default encoding crash on    | High  | High   | Enforce sys.stdout.reconfigure  | TST   |
|     | (Win32 API)       | Unicode symbols (omega, Delta, Angstrom)    |       |        | (encoding='utf-8') at module init|       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R02 | Local-Linux       | Memory exhaustion during large DFT Hessian  | Low   | High   | Enforce InHess XTB2 model       | COD   |
|     | (POSIX / Ubuntu)  | calculations on multi-atom complexes        |       |        | preconditioning; ban Calc_Hess  |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R03 | Local-macOS       | Accelerate/Metal framework FP64 precision   | Med   | Med    | Enforce pure float64 NumPy and  | COD   |
|     | (ARM64 Apple M)   | emulation deviations in coordinate checks   |       |        | explicit double-precision BLAS  |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R04 | GitHub Codespaces | Ephemeral container rebuilds losing local   | Med   | Med    | Automated SQLite cache seeding  | TST   |
|     | (Cloud Dev Env)   | Mendeleev elemental database tables         |       |        | during container entrypoint     |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R05 | GitHub Actions CI | Flat potential energy surface step-count    | High  | High   | Inject MaxIter 200 into all     | COD   |
|     | (Virtual Machine) | aborts before reaching TolMaxG 1e-5         |       |        | ORCA %geom constraint blocks    |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R06 | High-Perf Cluster | Parallel MPI process deadlock during        | Low   | Crit   | Strict process runner air-gap   | ORC   |
|     | (SLURM / HPC)     | subprocess execution of ORCA binaries       |       |        | with explicit process timeouts  |       |
+==================================================================================================================================+
```

---

## 8. Document Control & Ledger Synchronization

| Field | Authoritative Specification Record | Primary Scratch Record | Repository Mirror Record |
| :--- | :--- | :--- | :--- |
| **Physical File Path** | `D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_1_method_matrix_and_module_survey.md` | `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md` | `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_1_method_matrix_and_module_survey.md` |
| **Authoring Agent** | `cochem-sdp-manager` | `cochem-sdp-manager` | `cochem-sdp-manager` |
| **Supervising Authority** | `0rchestrator` | `0rchestrator` | `0rchestrator` |
| **Governing Standards** | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 |
| **Lifecycle Status** | `APPROVED_SURVEY_BASELINE` | `APPROVED_SURVEY_BASELINE` | `APPROVED_SURVEY_BASELINE` |
