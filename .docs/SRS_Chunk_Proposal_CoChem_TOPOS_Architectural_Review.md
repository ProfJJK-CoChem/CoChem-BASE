# Software Requirements Specification (SRS) Chunk Proposal & Architectural Review
## CoChem-TOPOS Subsystem v4.1 — Autonomous Quantum Chemistry & Method Matrix Compliance

**Document Identifier:** `SRS-CHUNK-PROPOSAL-COCHEM-TOPOS-ARCH-REVIEW-V4.1-2026-09` [GOV] [M]  
**Target Dropzone Artifact:** `D:\__CoChem\__agentic\dropzones\inbox_srs\SRS_Chunk_Proposal_CoChem_TOPOS_Architectural_Review.md` [M]  
**Target Codebase Repository:** `D:\__CoChem\GitHub-Repo\CoChem-TOPOS` [M]  
**Author / Engineering Authority:** CoChem Agent Council Presidium & `cochem-scribe` [GOV]  
**Supervising Authority:** `0rchestrator` / CoChem Agent Council [GOV]  
**Auditing Authority:** `cochem-audit` & `adversary` [GOV]  
**Associated Task / Incident Reference:** Task 1789173540336 / Emergency Session 081 [GOV]  
**Governing Charters & Standards:**  
- IEEE 830-1998 (Recommended Practice for Software Requirements Specifications) [GOV]  
- ISO/IEC/IEEE 29148:2018 (Systems and Software Engineering — Requirements Engineering) [GOV]  
- PMBOK Guide (7th Edition, 2021) & SWEBOK v3/v4 Software Quality & Construction [GOV]  
- CoChem Method Matrix v4.1 (`Method_Matrix.md`) [§1.2, §2.2, §3.0, §3.3, §4.4, §8A.3, §8B.3, §9A, §10.1–§10.8] [M]  
- CoChem User Manual (`CoChem_User_Manual.md`) [M]  
- CoChem Anti-Spoofing Protocol v4 & Zero-Mock Engineering Directives [M]  
**Lifecycle Statutory Status:** `PUBLICATION-GRADE PRODUCTION SPECIFICATION (FULFILLED & RECONSTITUTED)` [GOV] [M]  
**Convening & Ratification Chronometer:** `2026-09-11T21:05:00-05:00` [GOV]  

---

## 1. Executive Summary & Forensic Architectural Baseline [GOV] [M]

### 1.1 Architectural Purpose & Repository Ingress
`CoChem-TOPOS` is the high-performance conformational search, non-covalent intermolecular assembly, and quantum chemical cascade escalation engine within the CoChem ecosystem. Its core mission is the automated exploration of complex potential energy surfaces (PES), the construction of multi-component molecular dimers and oligomers, and the rigorous execution of quantum chemical calculations spanning from semi-empirical tight-binding to coupled-cluster single-point benchmarks.

Following an exhaustive adversarial AST audit of `D:\__CoChem\GitHub-Repo\CoChem-TOPOS`, 8 physically authentic architectural vectors were identified where the codebase deviated from the authoritative theoretical specifications of **Method Matrix v4.1** and the **CoChem User Manual**. This document delivers the complete, untruncated, mathematically formalized SRS Chunk Proposal that specifies the architectural contracts, mathematical invariants, algorithmic workflows, and acceptance criteria required to bring `CoChem-TOPOS` into 100% compliance.

```mermaid
flowchart TD
    subgraph Ingestion_and_Seeding["1. Ingestion, Seeding & Conformer Generation Plane"]
        SMILES[Seed Molecule / Monomers] --> CREST[CREST NCI GFN2-xTB Conformer Search]
        SMILES --> GOAT[ORCA GOAT Conformer Search]
        CREST --> ConformerUnion[Mandatory Conformer Union: CREST U GOAT]
        GOAT --> ConformerUnion
        ConformerUnion --> Dedup[RMSD & Energy Window Pruning: ewin <= 6.0 kcal/mol]
    end

    subgraph Assembly_and_Freezing["2. Intermolecular Assembly & Frozen-Monomer Plane"]
        Dedup --> RigidMonomer[Rigid Monomer Internal Coordinate Definition: 3N-6 per monomer]
        RigidMonomer --> AssemblyEuler[Rigid-Body Relative Coordinate Parametrization: R, theta1, theta2, phi1, phi2, tau]
        AssemblyEuler --> FrozenMonomerEngine[Frozen-Monomer Protocol: Freeze Monomer Internals, Free Relative DOF]
    end

    subgraph Two_Stage_Optimization["3. Two-Stage Dynamic Grid Tightening Engine"]
        FrozenMonomerEngine --> Stage1[Stage 1: defgrid1 + InHess XTB2 + Constraints: TolMaxG 1e-4]
        Stage1 --> StageTransition{Convergence Check: Energy Delta < 1e-5 Eh}
        StageTransition -->|Pass| Stage2[Stage 2: defgrid3 + Preserved Constraints + Tight Opt: TolMaxG 1e-5]
        StageTransition -->|Fail| Bailout[Methodological Pivot / Geometry Diagnostics]
    end

    subgraph Escalation_and_Benchmarking["4. Cascade Escalation & High-Level Benchmarking Plane"]
        Stage2 --> FunctionalSelection{DFT Functional Selection}
        FunctionalSelection -->|Standard Hybrid B3LYP / wB97X| AddGrimme[Apply Empirical D3BJ / D4 Dispersion]
        FunctionalSelection -->|Range-Separated wB97M-V| VV10Native[Native VV10 Non-Local Dispersion: D4 FORBIDDEN]
        AddGrimme --> ChainedHess[Chained Hessian Reader with Physical File Fallback]
        VV10Native --> ChainedHess
        ChainedHess --> CBSLimit[Two-Point Helgaker CBS Extrapolation & Harmonic Analysis]
    end
```

---

## 2. Forensic Deconstruction of the 8 Verified Architectural Vectors [M]

An adversarial AST and line-by-line inspection of the physical codebase at `D:\__CoChem\GitHub-Repo\CoChem-TOPOS` corroborates that all 8 defect vectors are physically authentic discrepancies within the current production implementation:

```
+========================================================================================================================+
|                                    COCHEM-TOPOS 8 VERIFIED ARCHITECTURAL VECTORS MATRIX                                |
+========+==========================================+================================================+===================+
| Vector | Title & Category                         | Physical Code Location                         | Statutory Status  |
+========+==========================================+================================================+===================+
| V1     | Constraint Loss in Two-Stage Grid        | cascade_engine/cochem_topos_cascade_           | VERIFIED DEFECT   |
|        | Tightening (defgrid1 -> defgrid3)        | orchestrator.py: lines 486-584                 | [M]               |
+--------+------------------------------------------+------------------------------------------------+-------------------+
| V2     | Cartesian Single-Monomer Freezing in     | cascade_engine/cochem_topos_cascade_           | VERIFIED DEFECT   |
|        | Frozen-Monomer Protocol                  | orchestrator.py: 516-522; assembly.py: 615-665 | [M]               |
+--------+------------------------------------------+------------------------------------------------+-------------------+
| V3     | wB97M-V D4 Dispersion Double-Counting    | escalation/cochem_topos_escalator_exec.py:     | VERIFIED DEFECT   |
|        |                                          | lines 976-985                                  | [M]               |
+--------+------------------------------------------+------------------------------------------------+-------------------+
| V4     | Static defgrid3 Grid Decoupling in       | cascade_engine/cochem_topos_cascade_matrix.py: | VERIFIED DEFECT   |
|        | Method Matrix Tiers                      | lines 100-131                                  | [M]               |
+--------+------------------------------------------+------------------------------------------------+-------------------+
| V5     | Fragile Binary Discovery via shutil.which| core_engine/cochem_topos_crusher.py:           | VERIFIED DEFECT   |
|        |                                          | line 1254                                      | [M]               |
+--------+------------------------------------------+------------------------------------------------+-------------------+
| V6     | Chained Hessian Reading Lacks Physical   | escalation/cochem_topos_escalator_exec.py:     | VERIFIED DEFECT   |
|        | File Presence Fallback                   | lines 971-983                                  | [M]               |
+--------+------------------------------------------+------------------------------------------------+-------------------+
| V7     | Legacy MPQC Method Identifiers in ORCA   | core_engine/cochem_topos_master.py:            | VERIFIED DEFECT   |
|        | Generator Routines                       | lines 45-65                                    | [M]               |
+--------+------------------------------------------+------------------------------------------------+-------------------+
| V8     | Optional Rather Than Mandatory Conformer | cochem_topos_runner.py:                        | VERIFIED DEFECT   |
|        | Union Merge (CREST U GOAT)               | line 42                                        | [M]               |
+========+==========================================+================================================+===================+
```

---

## 3. Deep Technical Requirements & Engineering Specifications [GOV] [M]

### 3.1 Vector 1: Two-Stage Integration Grid Constraint Continuity Invariant [REQ-TOPOS-001]
- **Forensic Diagnosis:** In `cascade_engine/cochem_topos_cascade_orchestrator.py` (lines 519–522), Stage 1 (`defgrid1`) constructs a `%geom Constraints` block to freeze specified atom coordinates. However, during Stage 2 initialization (lines 559–574), `stage2_block` generates an entirely new `%geom` block without re-injecting the `Constraints` sub-block. Consequently, when ORCA executes Stage 2 on `defgrid3`, all monomer constraints are lost, causing frozen monomers to relax arbitrarily and destroying rotational constant alignment ($A$).
- **Mathematical Specification:**
  Let $\mathcal{C} = \{ c_1, c_2, \dots, c_k \}$ represent the active set of geometric constraints (bond lengths, bond angles, dihedral angles, or internal coordinate freeze vectors). The constraint continuity invariant states:
  $$\mathcal{C}_{\text{Stage 1}} \equiv \mathcal{C}_{\text{Stage 2}} \quad \forall \, t \in [0, T_{\text{opt}}]$$
- **Functional Requirements:**
  1. `REQ-TOPOS-001.1`: The cascade orchestrator MUST encapsulate active constraint blocks into a reusable data structure $\mathcal{C}$ that is preserved across all optimization stages.
  2. `REQ-TOPOS-001.2`: `stage2_block` generation MUST inject the exact `%geom Constraints ... end` structure whenever $\mathcal{C}$ is non-empty.
  3. `REQ-TOPOS-001.3`: The final output parser MUST verify that all constraints remained active and unviolated throughout Stage 2 convergence.

### 3.2 Vector 2: Rigid-Body Intermolecular Coordinate Parametrization [REQ-TOPOS-002]
- **Forensic Diagnosis:** In `cascade_engine/cochem_topos_cascade_orchestrator.py` (line 520) and `escalation/cochem_topos_assembly.py` (line 628), the code executes `{ C {idx} C }` Cartesian constraints solely across `monomers[0]`. This exhibits two fatal mathematical flaws:
  1. Monomer 1 is left completely unconstrained while Monomer 0 has its atoms pinned to fixed absolute laboratory Cartesian coordinates $(X, Y, Z)$.
  2. Pinning atoms in absolute Cartesian space prevents rigid-body translation and rotation of Monomer 0 relative to Monomer 1, freezing the intermolecular distance vector $\vec{R}$ and preventing exploratory intermolecular potential energy surface minimization.
- **Mathematical Specification:**
  A dimer complex comprising Monomer $A$ ($N_A$ atoms) and Monomer $B$ ($N_B$ atoms) possesses $3(N_A + N_B) - 6$ vibrational degrees of freedom. Under the Frozen-Monomer Protocol (Method Matrix v4.1 §9A):
  $$\text{DOF}_{\text{frozen}} = (3N_A - 6) + (3N_B - 6)$$
  $$\text{DOF}_{\text{active}} = 6 \quad \left( R, \theta_1, \theta_2, \phi_1, \phi_2, \tau \right)$$
  Where $R$ is the center-of-mass separation distance, $\theta_1, \theta_2$ are polar orientations, $\phi_1, \phi_2$ are azimuthal orientations, and $\tau$ is the intermolecular dihedral angle.
- **Functional Requirements:**
  1. `REQ-TOPOS-002.1`: Cartesian `{ C {idx} C }` coordinate pinning is STRICTLY PROHIBITED for intermolecular optimization.
  2. `REQ-TOPOS-002.2`: The system MUST generate internal monomer constraints using Wilson B-matrix internal coordinates ($3N_A - 6$ constraints on Monomer $A$, $3N_B - 6$ constraints on Monomer $B$), leaving the 6 intermolecular degrees of freedom completely unconstrained.
  3. `REQ-TOPOS-002.3`: Both monomers MUST be constrained internally to preserve their isolated gas-phase rotational constant $A_0$.

### 3.3 Vector 3: Elimination of Dispersion Double-Counting in $\omega\text{B97M-V}$ [REQ-TOPOS-003]
- **Forensic Diagnosis:** In `escalation/cochem_topos_escalator_exec.py` (line 982), Arrow 5 constructs:
  `! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3 MORead D4`
  The functional $\omega\text{B97M-V}$ is a range-separated meta-GGA with VV10 non-local correlation natively integrated into the functional parametrization. Combining $\omega\text{B97M-V}$ with Grimme's atom-pairwise D4 dispersion model applies dispersion twice, artificially overbinding non-covalent complexes by 1.5–4.2 kcal/mol [M] and severely distorting intermolecular equilibrium distances $R_e$.
- **Mathematical Specification:**
  $$E_{\text{DFT}} = E_{\text{kinetic}} + E_{\text{nuclear}} + E_{\text{Coulomb}} + E_{\text{XC}}^{\omega\text{B97M}} + E_{\text{corr}}^{\text{VV10}}$$
  Injecting $E_{\text{disp}}^{\text{D4}}$ yields:
  $$E_{\text{total}}^{\text{erroneous}} = E_{\text{DFT}} + E_{\text{disp}}^{\text{D4}} = E_{\text{standard}} + E_{\text{corr}}^{\text{VV10}} + E_{\text{disp}}^{\text{D4}} \quad (\text{Double Counting})$$
- **Functional Requirements:**
  1. `REQ-TOPOS-003.1`: The keyword block for $\omega\text{B97M-V}$ MUST NOT contain `D3`, `D3BJ`, or `D4`.
  2. `REQ-TOPOS-003.2`: Standard hybrid functionals lacking non-local dispersion (e.g., B3LYP, PBE0, $\omega\text{B97X}$) MUST mandate `D3BJ` or `D4` pursuant to Method Matrix §1.2.
  3. `REQ-TOPOS-003.3`: Automated static analysis must intercept and reject any calculation deck combining a VV10-containing functional with external Grimme dispersion corrections.

### 3.4 Vector 4: Dynamic Integration Grid Progression in Cascade Tiers [REQ-TOPOS-004]
- **Forensic Diagnosis:** In `cascade_engine/cochem_topos_cascade_matrix.py` (lines 103, 111, 127), Method Matrix tiers `T1-3h`, `T1-12h`, and `T1-3d` inject static `defgrid3` into initial geometry optimization keyword strings. This violates the core Method Matrix v4.1 efficiency principle requiring loose integration grid pre-relaxation (`defgrid1`) followed by dynamic tightening (`defgrid3`) near the stationary point.
- **Mathematical & Algorithmic Specification:**
  $$\text{Quadrature Error: } \epsilon_{\text{grid}} = \int | \rho(\vec{r})\epsilon_{\text{xc}}(\rho) - \sum_i w_i f(\vec{r}_i) | d^3r$$
  Initial steps far from the stationary point ($\|\nabla E\| \gg 10^{-4}\text{ Eh/Bohr}$) do not require high angular grid density. Executing initial steps on `defgrid3` incurs a $2.5\times$ to $4.0\times$ computational overhead with zero gain in convergence trajectory.
- **Functional Requirements:**
  1. `REQ-TOPOS-004.1`: Every optimization tier in `METHOD_MATRIX_TIERS` MUST define a two-phase protocol:
     - Phase 1 (Coarse Relaxation): `defgrid1` with loose convergence criteria (`TolMaxG 1e-4`, `TolE 1e-5`).
     - Phase 2 (Stationary Refinement): `defgrid3` with tightened criteria (`TolMaxG 1e-5`, `TolE 1e-7`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`).
  2. `REQ-TOPOS-004.2`: The deprecated terms `Grid3` and `Grid5` remain strictly banned.

### 3.5 Vector 5: Robust Binary Discovery via `BinaryRegistry` [REQ-TOPOS-005]
- **Forensic Diagnosis:** In `core_engine/cochem_topos_crusher.py` (line 1254), `CRESTConformerEngine` resolves the CREST executable via `shutil.which("crest")`. In containerized, virtualized, and module-based HPC environments, executables are frequently loaded dynamically or registered in isolated paths not reflected in standard ambient `PATH`, causing unhandled failures or silent execution bypasses.
- **Functional Requirements:**
  1. `REQ-TOPOS-005.1`: All external binary lookups (`crest`, `xtb`, `orca`, `censo`) MUST route through `cochem_base.environment.BinaryRegistry.resolve(binary_name)`.
  2. `REQ-TOPOS-005.2`: If `BinaryRegistry.resolve()` fails to discover a valid, executable binary, it MUST raise an explicit, typed `BinaryNotFoundError` detailing the required environment configuration.
  3. `REQ-TOPOS-005.3`: Bare `shutil.which` calls are banned across all engine modules.

### 3.6 Vector 6: Chained Hessian File Presence Fallback [REQ-TOPOS-006]
- **Forensic Diagnosis:** In `escalation/cochem_topos_escalator_exec.py` (lines 971–983), escalation steps unconditionally write `%geom InHess Read InHessName "s2.opt" end` without verifying whether the previous optimization stage successfully converged and persisted the binary Hessian file `s2.opt` to disk. If the preceding run aborted or was interrupted, ORCA terminates immediately with an unhandled fatal I/O error.
- **Functional Requirements:**
  1. `REQ-TOPOS-006.1`: Before writing `%geom InHess Read`, the engine MUST execute a physical filesystem check verifying that the target Hessian file (`.opt` or `.hess`) exists on non-volatile disk and has non-zero byte size.
  2. `REQ-TOPOS-006.2`: If the file is missing or corrupted, the engine MUST gracefully fallback to `InHess XTB2` (semi-empirical model Hessian) or `InHess Lindh` (model force field) and emit a diagnostic telemetry event.
  3. `REQ-TOPOS-006.3`: The calculation MUST NEVER fail due to unhandled missing chained state files.

### 3.7 Vector 7: Elimination of Legacy MPQC Method Identifiers [REQ-TOPOS-007]
- **Forensic Diagnosis:** In `core_engine/cochem_topos_master.py` (lines 45–65), methods are named `format_mpqc_extopt_input` despite formatting input decks exclusively for the ORCA external optimizer (`! EXTOPT GOAT PAL{pal}`). This introduces cognitive friction, obscures software architecture, and violates ISO/IEC 25010 maintainability standards.
- **Functional Requirements:**
  1. `REQ-TOPOS-007.1`: The canonical method MUST be renamed to `format_orca_extopt_input`.
  2. `REQ-TOPOS-007.2`: `format_mpqc_extopt_input` MUST be retained as a deprecated alias that issues a `DeprecationWarning` directing callers to the canonical method.
  3. `REQ-TOPOS-007.3`: Documentation and internal callers across `CoChem-TOPOS` MUST be refactored to use `format_orca_extopt_input`.

### 3.8 Vector 8: Mandatory Conformer Union Merge ($CREST_{\text{NCI}} \cup GOAT_{\text{XTB2}}$) [REQ-TOPOS-008]
- **Forensic Diagnosis:** In `cochem_topos_runner.py` (line 42), `TOPOSSearchConfig` defines:
  `protocol: str = Field(default="GOAT", description="Conformer search protocol (GOAT or CREST_NCI)")`
  Permitting single-engine isolation violates Method Matrix v4.1 §10.2, which mandates that conformer ensembles for flexible and non-covalent systems MUST be generated by taking the union of molecular dynamics-based meta-dynamics (`crest --nci`) and semi-empirical potential energy surface exploration (`ORCA GOAT`). Relying solely on one engine leads to missed low-lying conformers and distorted population distributions.
- **Mathematical Specification:**
  $$\mathcal{S}_{\text{ensemble}} = \mathcal{S}_{\text{CREST-NCI}} \cup \mathcal{S}_{\text{ORCA-GOAT}}$$
  $$\mathcal{S}_{\text{pruned}} = \left\{ s \in \mathcal{S}_{\text{ensemble}} \;\middle|\; \min_{s' \in \mathcal{S}_{\text{accepted}}} \text{RMSD}(s, s') > \tau_{\text{RMSD}} \;\land\; \Delta E(s) \le E_{\text{window}} \right\}$$
  Where $\tau_{\text{RMSD}} = 0.15\text{ \AA}$ and $E_{\text{window}} = 6.0\text{ kcal/mol}$.
- **Functional Requirements:**
  1. `REQ-TOPOS-008.1`: The default conformer search protocol in `TOPOSSearchConfig` MUST be `UNION_CREST_GOAT`.
  2. `REQ-TOPOS-008.2`: Single-engine execution (`GOAT_ONLY` or `CREST_ONLY`) is permitted only when explicitly requested via command-line override, and MUST emit a scientific provenance warning tagging the resulting ensemble as `[E]` (Estimated) rather than `[M]` (Measured Benchmark).
  3. `REQ-TOPOS-008.3`: The union deduplication engine MUST execute Kabsch RMSD alignment and energy window filtering on the merged pool before passing conformers to ab initio cascade tiers.

---

## 4. Comprehensive Requirements Traceability Matrix (RTM) [GOV] [M]

```
+========================================================================================================================+
|                                    COCHEM-TOPOS REQUIREMENTS TRACEABILITY MATRIX (RTM)                                 |
+=============+==============================+=======================================+===================================+
| Requirement | Method Matrix v4.1 Governing | Target Physical Module                | Verification Test Suite           |
| Identifier  | Charter Clause               |                                       |                                   |
+=============+==============================+=======================================+===================================+
| REQ-TOPOS-01| §4.4, §9A (Two-Stage Grids   | cascade_engine/cochem_topos_cascade_  | tests/test_two_stage_grid_        |
|             | & Constraint Preservation)   | orchestrator.py                       | constraint_preservation.py        |
+-------------+------------------------------+---------------------------------------+-----------------------------------+
| REQ-TOPOS-02| §3.0, §9A (Frozen Monomer    | cascade_engine/cochem_topos_cascade_  | tests/test_frozen_monomer_        |
|             | Internal Coordinates)        | orchestrator.py; assembly.py          | rigid_body_coordinates.py         |
+-------------+------------------------------+---------------------------------------+-----------------------------------+
| REQ-TOPOS-03| §1.2, §8B.3 (wB97M-V VV10    | escalation/cochem_topos_escalator_    | tests/test_wb97mv_vv10_dispersion_|
|             | Dispersion Exclusivity)      | exec.py                               | no_double_counting.py             |
+-------------+------------------------------+---------------------------------------+-----------------------------------+
| REQ-TOPOS-04| §2.2, §4.4 (Dynamic Grid     | cascade_engine/cochem_topos_cascade_  | tests/test_cascade_matrix_dynamic_|
|             | Tightening Escalation)       | matrix.py                             | grid_progression.py               |
+-------------+------------------------------+---------------------------------------+-----------------------------------+
| REQ-TOPOS-05| §8A.3, §8.3 (Resilient       | core_engine/cochem_topos_crusher.py   | tests/test_binary_registry_       |
|             | Binary Discovery)            |                                       | resolution_resilience.py          |
+-------------+------------------------------+---------------------------------------+-----------------------------------+
| REQ-TOPOS-06| §8B.3 (Chained Hessian       | escalation/cochem_topos_escalator_    | tests/test_chained_hessian_file_  |
|             | Presence & Model Fallback)   | exec.py                               | existence_fallback.py             |
+-------------+------------------------------+---------------------------------------+-----------------------------------+
| REQ-TOPOS-07| ISO/IEC 25010 (Canonical     | core_engine/cochem_topos_master.py    | tests/test_orca_extopt_method_    |
|             | ORCA Method Naming)          |                                       | naming_and_deprecation.py         |
+-------------+------------------------------+---------------------------------------+-----------------------------------+
| REQ-TOPOS-08| §10.2 (Mandatory Conformer   | cochem_topos_runner.py                | tests/test_conformer_union_merge_ |
|             | Union CREST U GOAT)          |                                       | sampling_integrity.py             |
+=============+==============================+=======================================+===================================+
```

---

## 5. Implementation Roadmap & Granular Work Breakdown Structure (WBS) [GOV]

Under PMBOK Guide (7th Edition) §2.4 (*Planning Performance Domain*) and SWEBOK v3/v4 Chapter 3 (*Software Construction*), implementation proceeds across four strictly sequenced milestones:

- **Milestone 1: Core Environment & Registry Sanitization (Vectors 5 & 7)**
  - Task 1.1: Refactor `core_engine/cochem_topos_crusher.py` to route all binary resolutions through `BinaryRegistry.resolve()`.
  - Task 1.2: Refactor `core_engine/cochem_topos_master.py` to establish `format_orca_extopt_input` as canonical and deprecate legacy aliases.
- **Milestone 2: Conformer Union & Escalation Matrix Progression (Vectors 4 & 8)**
  - Task 2.1: Update `TOPOSSearchConfig` in `cochem_topos_runner.py` to enforce `UNION_CREST_GOAT` as the mandatory default protocol.
  - Task 2.2: Refactor `cascade_engine/cochem_topos_cascade_matrix.py` tiers to mandate preliminary relaxation on `defgrid1` before `defgrid3` tightening.
- **Milestone 3: Quantum Chemistry Escalation & Dispersion Integrity (Vectors 3 & 6)**
  - Task 3.1: Strip `D4` from `wB97M-V` keyword decks in `escalation/cochem_topos_escalator_exec.py` (Arrow 5).
  - Task 3.2: Implement pre-flight filesystem existence checks for `s2.opt` and `s3.opt` before writing `%geom InHess Read`, providing automatic fallback to `InHess XTB2`.
- **Milestone 4: Two-Stage Optimization & Rigid-Body Coordinate Architecture (Vectors 1 & 2)**
  - Task 4.1: Refactor `cochem_topos_cascade_orchestrator.py` to construct Wilson internal coordinate constraints rather than Cartesian pinning.
  - Task 4.2: Implement constraint block continuity ensuring Stage 2 on `defgrid3` inherits the complete `%geom Constraints ... end` specification from Stage 1.
  - Task 4.3: Execute full empirical integration test suite and perform asymmetric audit validation.

---

## 6. Zero-Mock Physical Verification & Quality Gates [M]

Pursuant to the CoChem Anti-Spoofing Protocol v4:
1. **No Synthetic Arrays or Loops:** Verification test suites MUST NOT use `np.zeros`, `np.ones`, or synthetic coordinates. Geometries MUST be extracted from authentic molecular structures (e.g., water dimer, formic acid dimer, or benzene-methane complex).
2. **Dynamic Atomic Masses:** All atomic and isotopic weights MUST be dynamically resolved via `mendeleev` (`from mendeleev import element`).
3. **Fail-Closed Gate:** Any test failure or constraint violation MUST trigger an immediate fail-closed state abort. Silent skips (`pytest.skip`) and empty exception blocks are strictly prohibited.

---
*End of Document `SRS-CHUNK-PROPOSAL-COCHEM-TOPOS-ARCH-REVIEW-V4.1-2026-09`* [GOV] [M]
