# Task 3.3.1 Dispatch Specification: Execution Agent Selection & Formalization Prompt for Data Architecture & Schema Formalization Plane (L3.1.1 - L3.1.3)
## Ontological Disambiguation & Production Data Modeling: Product B (Parent-Anchored Microwave) vs Product M (Solid-State Materials)

**Document Identifier:** `COCHEM-DISPATCH-WBS-3.3.1-SDPM-20260910` [M]  
**Parent Task:** Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]  
**Level 2 Task:** Established technical roadmap for Product B (parent-anchored microwave) vs Product M (solid-state materials) ontological disambiguation. [GOV]  
**Specific Task to Execute:** `3.3.1 - Formalized L3 component tasks for Data Architecture & Schema Formalization Plane (L3.1.1 - L3.1.3)` [GOV] / [DOC]  
**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & Requirements Architect) [M]  
**Supervising Authority:** `0rchestrator` (CoChem Swarm Council Leader) [M]  
**Supervising & Asymmetric Auditing Agents:** `cochem-audit` (Autonomous QA & Standards Lead) and `adversary` (Zero-Trust Red-Team Lead) [M]  
**Governing Architectural Baselines:**  
- Master WBS: [`task3_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task3_level2_wbs_breakdown.md) (Council Session 041 Ratified Master Baseline, 42,193 B, 456 L, SHA-256: `48E92125C69DFD5E8F0D6C1A5473A31FFCA4472C5E4BC946B13EF30E74DDB97F`) [M]  
- L3 Component Decomposition: [`task3_2_1_vr03_vr05_l3_decomposition.md`](file:///D:/__CoChem/.docs/task3_2_1_vr03_vr05_l3_decomposition.md) (Task 3.2.1 Ratified Baseline, 57,685 B, 612 L, SHA-256: `EA73F8D91B9C4D4251AF9BCEDEDC8F9E5A79C103EB646915FB05A5EFD943D6BF`) [M]  
- Requirements Traceability Matrix: [`Task3_VR03_VR05_Traceability_Matrix.md`](file:///D:/__CoChem/.docs/Task3_VR03_VR05_Traceability_Matrix.md) (Council Session 044 Ratified Baseline, 44,762 B, 283 L, SHA-256: `0235C268731857DBB0B28763852F554D326E0A958241BCC7276B0E4EB9513559`) [M]  
- Preceding Dispatch: [`task3_2_2_dispatch_prompt.md`](file:///D:/__CoChem/.docs/task3_2_2_dispatch_prompt.md) (27,853 B, 311 L, SHA-256: `576EF0F74F2F1EC6EB9DE8E09D3E90382894D368C9F81FA37812165DC91DC6FF`) [M]  
**Governing Standards:** PMBOK Guide 7th Edition (Systems View for Project Delivery & 100% Rule), SWEBOK v3.0/v4.0 (Software Requirements & Quality Management), ISO/IEC/IEEE 29148:2018, IEEE 830-1998, Method Matrix v4.1, Anti-Spoofing Directive v4, Mendeleev Dynamic Mass Mandate, Disciplinary Rulings D1-01 & PCA-01 to PCA-19 [M]  
**Primary Scratch Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_3_1_dispatch_prompt.md` [GOV]  
**Conversation Artifact Mirror:** `C:/Users/ansac/.gemini/antigravity-cli/brain/6b7b9b3b-d7bd-42b9-9311-108a4584c9ce/task3_3_1_dispatch_prompt.md` [GOV]  
**Ecosystem Master Mirror:** `D:/__CoChem/.docs/task3_3_1_dispatch_prompt.md` [GOV]  
**Repository Mirror (Active HEAD):** `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_3_1_dispatch_prompt.md` [GOV]  
**Dropzone SRS Intake Mirror:** `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_3_1_dispatch_prompt.md` [GOV]  
**Lifecycle Status:** `APPROVED_FOR_BASELINE_EXECUTION` [M]  
**Timestamp:** `2026-09-10T23:35:00-05:00` [M]  

---

## 1. Execution Agent Selection & Architectural Justification

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & Requirements Architect) [M]

### Authoritative Justification Ledger:

1. **PMBOK 7th Edition & SWEBOK v3/v4 Scope & Requirements Authority:**  
   Under the CoChem Agent Council skill taxonomy ([`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md)), `cochem-sdp-manager` is the sole authoritative agent chartered with software requirements architecture, Work Breakdown Structure (WBS) decomposition, formalizing quantitative acceptance criteria, defining numerical invariants, assigning single-owner RACI roles, and establishing rigorous work package specifications under the **PMBOK 100% Rule** and **MECE (Mutually Exclusive, Collectively Exhaustive)** principles. Formalizing the three subordinate component tasks comprising Plane 1 (Data Architecture & Schema Formalization Plane) requires deep systems engineering governance to translate Method Matrix v4.1 physical requirements into unambiguous, type-safe software engineering contracts.

2. **Strict Separation of Duties & Zero-Trust Governance (Council Ruling D1-01 & PCA-01):**  
   Under CoChem Zero-Trust governance and Permanent Corrective Action 01 (`PCA-01`):
   - `cochem-sdp-manager` is the project manager and requirements architect chartered with establishing formal scopes, interface boundaries, and acceptance criteria.
   - `@cochem-coder` is the downstream production developer and is **strictly prohibited from defining its own project scope, creating its own acceptance criteria, or validating its own production deliverables** (an implementer cannot baseline its own requirements).
   - Independent verification testing is reserved strictly for `cochem-tester` via authentic pytest test suites in `tests/`.
   - Asymmetric compliance audits and red-team scrutiny are reserved strictly for `cochem-audit` and `adversary`.
   - Technical documentation typesetting is reserved for `cochem-scribe`.
   - Therefore, designating `cochem-sdp-manager` to execute Task 3.3.1 preserves absolute role independence, governance integrity, and prevents counterfeit compliance [M].

3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` authored and owns all preceding ratified WBS baseline specifications, requirements extractions, and traceability matrices across Tasks 1, 2, and 3:
   - Task 1 WBS Baseline: `task1_level2_wbs_breakdown.md`
   - Task 1 Traceability Matrix: `task1_5_3_dispatch_prompt.md`
   - Task 2 Survey & WBS: `task2_2_1_dispatch_prompt.md`, `task2_level2_wbs_breakdown.md`
   - Task 2 Component Decomposition: `task2_4_2_nine_granular_mece_level3_tasks.md`
   - Task 3 Level 2 Breakdown: `task3_level2_wbs_breakdown.md` (Ratified in Council Session 041)
   - Task 3 L3 Component Decomposition: `task3_2_1_vr03_vr05_l3_decomposition.md` (Ratified in Council Session 042)
   - Task 3 End-to-End Traceability Matrix: `Task3_VR03_VR05_Traceability_Matrix.md` (Ratified in Council Session 044)  
   Assigning Task 3.3.1 to `cochem-sdp-manager` maintains uninterrupted continuity, ensures exact Method Matrix alignment, and guarantees ledger coherence [M].

4. **Single-Accountable RACI Mapping for Plane 1 (L3.1.1 - L3.1.3):**  
   In strict compliance with the ratified WBS master matrix, the component tasks for Plane 1 are allocated as follows:
   - `L3.1.1`: Canonical Product Enumeration & Category Registry Formalization (`cochem-sdp-manager` [Accountable], `@cochem-coder` [Responsible for Downstream Code])
   - `L3.1.2`: Product B Data Schema & Parent Rotational Anchor Models (`cochem-sdp-manager` [Accountable], `@cochem-coder` [Responsible for Downstream Code])
   - `L3.1.3`: Product M Data Schema & Periodic Unit Cell Models (`cochem-sdp-manager` [Accountable], `@cochem-coder` [Responsible for Downstream Code])

---

## 2. Authoritative Implementation & Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 3.3.1 — FORMALIZED L3 COMPONENT TASKS FOR DATA ARCHITECTURE & SCHEMA FORMALIZATION PLANE (L3.1.1 - L3.1.3)]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You govern the formal systems engineering, WBS decomposition, and technical requirements architecture under PMBOK Guide 7th Edition (Systems View for Project Delivery, 100% Rule), SWEBOK v3/v4 (Requirements Engineering, Software Design, and Software Quality), ISO/IEC/IEEE 29148:2018, IEEE 830-1998, Method Matrix v4.1, and the CoChem Anti-Spoofing Protocol v4.

================================================================================
1. PROJECT HIERARCHY & SPECIFIC TASK ASSIGNMENT
================================================================================
- Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]
- Level 2: Established technical roadmap for Product B (parent-anchored microwave) vs Product M (solid-state materials) ontological disambiguation. [GOV]
- Specific Task to Execute:
  3.3.1 - Formalized L3 component tasks for Data Architecture & Schema Formalization Plane (L3.1.1 - L3.1.3). [GOV] / [DOC]

================================================================================
2. MANDATORY RULE 1: INGEST EXISTING PROJECT FILES VIA TOOLS (DO NOT GUESS)
================================================================================
Before compiling or formalizing any specifications, you MUST explicitly invoke your filesystem inspection tools (view_file, grep_search, list_dir, find_by_name) to inspect existing physical files on disk to establish full empirical context:

1. Method Matrix Baselines & Ontological Origins:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md (and Method_Matrix/Method_Matrix_Hub.md):
     * §1.2 & §3.2: Taxonomic classification of computational products.
     * §3.0 & §15.2: Definition of Product B (Parent-anchored microwave spectroscopy, Recipe R6, equilibrium scaling to experimental rotational constants A_0, B_0, C_0, calibrated shift uncertainty <= 0.06%, tight conformal search window +/- 0.05%).
     * Historical conflation note: User manual and legacy SRS documents historically assigned "Product B" to periodic solid-state calculations, which must now be permanently disambiguated as "Product M".
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/CoChem_User_Manual.md:
     * Inspect lines 22, 203-220 to locate the legacy "Product B: Materials and Solid State (Periodic, Plane-Wave)" definitions that require formal refactoring into Product M.
   - D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md:
     * Section 3 & Section 5: Architectural Workflow and Ontological Disambiguation.

2. Existing Codebase Domain Models & Exceptions:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py (CoChemError, GridSpecificationError, RedundantDispersionError, MissingDispersionError, SpinContaminationError).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/formatters/cochem_inertial_defect_validator.py (Ray's asymmetry parameter kappa, inertial defect Delta, planar moments).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/isotopes.py (Dynamic Mendeleev mass resolution mandate; strict ban on static mass dictionaries).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/validators/preflight.py (Preflight geometry and keyword validation).

3. Preceding Planning, Traceability & Audit Baselines:
   - D:/__CoChem/.docs/task3_level2_wbs_breakdown.md (Council Session 041 Ratified Master Baseline, SHA-256: 48E92125C69DFD5E8F0D6C1A5473A31FFCA4472C5E4BC946B13EF30E74DDB97F).
   - D:/__CoChem/.docs/task3_2_1_vr03_vr05_l3_decomposition.md (Council Session 042 Ratified Baseline, SHA-256: EA73F8D91B9C4D4251AF9BCEDEDC8F9E5A79C103EB646915FB05A5EFD943D6BF).
   - D:/__CoChem/.docs/Task3_VR03_VR05_Traceability_Matrix.md (Council Session 044 Ratified Baseline, SHA-256: 0235C268731857DBB0B28763852F554D326E0A958241BCC7276B0E4EB9513559).
   - D:/__CoChem/.docs/task3_2_2_dispatch_prompt.md (Council Session 043 Ratified Implementation Dispatch).
   - D:/__CoChem/swarm_state.json (Swarm State Ledger).

You are STRICTLY FORBIDDEN from assuming file paths, guessing parameter thresholds, or hallucinating data structures without reading the physical files on disk first.

================================================================================
3. TECHNICAL SCOPE & SPECIFICATION MANDATES FOR L3.1.1 - L3.1.3
================================================================================
You must formulate a publication-grade, fail-closed technical specification formalizing the three subordinate component tasks comprising Plane 1 (Data Architecture & Schema Formalization Plane). Each component task specification must satisfy the PMBOK 100% Rule and MECE principles, establishing:

--------------------------------------------------------------------------------
Task L3.1.1: Canonical Product Enumeration & Category Registry Formalization
--------------------------------------------------------------------------------
- Target Module: D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/models/product_ontology.py
- Assigned Implementing Agent: cochem-coder (downstream execution)
- Domain Scope:
  * Define immutable StrEnum classes ProductCategory and CalculationDomain with Pydantic v2 ConfigDict(frozen=True, extra="forbid").
  * ProductCategory members:
    - PRODUCT_A = "product_a" (De Novo Blind Microwave Prediction, 0.13% - 0.50% window) [M]
    - PRODUCT_B = "product_b" (Parent-Anchored Microwave Spectroscopy, <= 0.06% error, +/- 0.05% conformal search window) [M]
    - PRODUCT_C = "product_c" (Differential / Isotopologue Spectroscopy, sub-0.01% Delta B) [M]
    - PRODUCT_M = "product_m" (Solid-State Materials & Extended Systems: PBC, PAW, Plane-Wave) [M]
  * CalculationDomain members:
    - MOLECULAR_GAS_PHASE = "molecular_gas_phase"
    - PERIODIC_SOLID_STATE = "periodic_solid_state"
  * Formalize string aliases and serialization adapters for backwards compatibility with legacy strings ("Product B (Parent-Anchored Complex)" vs legacy "Product B: Materials").
  * Legacy normalizer remapping: if a legacy config requests "Product B: Materials", the normalizer must remap it to ProductCategory.PRODUCT_M while logging an explicit deprecation warning.
  * Specify fail-closed validation: strict rejection of ambiguous, unmapped, or conflated product strings with a custom DomainOntologyError.
  * Tag all requirements with Method Matrix provenance ([M], [D], [E]).

--------------------------------------------------------------------------------
Task L3.1.2: Product B Data Schema & Parent Rotational Anchor Models
--------------------------------------------------------------------------------
- Target Module: D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/models/product_b_models.py
- Assigned Implementing Agent: cochem-coder (downstream execution)
- Domain Scope:
  * Pydantic v2 data models: ParentRotationalAnchor and ProductBConfig.
  * Physical Invariants & Field Validations:
    - Experimental rotational constants A_0, B_0, C_0 in MHz must satisfy the strict asymmetric top ordering invariant:
      A_0 > B_0 > C_0 > 0 [D]
    - Relative experimental uncertainty: sigma_A, sigma_B, sigma_C in MHz (non-negative floats).
    - Reference parent structure: chemical formula, parent SMILES, 3D Cartesian coordinates in Angstroms, and literature DOI citation.
    - Ray's asymmetry parameter calculation:
      kappa = (2B - A - C) / (A - C), where kappa in [-1, 1] [D]
    - Topological invariance guard: evaluate trial conformer asymmetry against parent anchor:
      |kappa_trial - kappa_parent| <= 0.05 [D]
    - Conformal prediction search window: hardcoded default delta_window = 0.0005 (+/- 0.05%) [M].
    - Target calibrated shift uncertainty <= 0.06% [M].
  * Domain Boundary Mutual Exclusivity:
    - Pydantic model validator MUST fail closed and reject any payload embedding periodic parameters (pbc, lattice_vectors, kpoints, cutoff_energy).
  * Mendeleev Dynamic Mass Mandate:
    - All isotopic mass references must specify dynamic retrieval via `from mendeleev import element` [M].

--------------------------------------------------------------------------------
Task L3.1.3: Product M Data Schema & Periodic Unit Cell Models
--------------------------------------------------------------------------------
- Target Module: D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/models/product_m_models.py
- Assigned Implementing Agent: cochem-coder (downstream execution)
- Domain Scope:
  * Pydantic v2 data models: PeriodicUnitCell and ProductMConfig.
  * Crystallographic Invariants & Field Validations:
    - Direct space lattice vectors a, b, c in R^(3x3) in Angstroms.
    - Unit cell volume via scalar triple product:
      V_cell = |a . (b x c)| > 0 [D]
    - Fractional atomic coordinates s_i in [0, 1)^3.
    - Periodic boundary conditions: pbc: tuple[bool, bool, bool] = (True, True, True) [M].
    - Monkhorst-Pack reciprocal k-point mesh (k_x, k_y, k_z) enforcing minimum reciprocal density:
      rho_k = k_i / |b_i| >= 0.04 Angstrom^-1 [D]
    - Gamma-point invariant: gamma_only = True strictly forbidden unless V_cell > 2000 Angstrom^3 [M].
    - Plane-wave kinetic energy cutoff: E_cut >= 400 eV (or 1.3 x max(E_cut^PAW)) [M].
    - PAW pseudopotential metadata specification and convergence thresholds:
      * SCF energy convergence: Delta E_SCF <= 1.0e-6 eV [M]
      * Force convergence: ||F||_inf <= 0.01 eV/Angstrom [M]
      * Stress tensor convergence: stress <= 0.5 kbar [M]
      * Equilibrium lattice parameter tolerance: <= 0.01 Angstrom [M]
      * Bandgap convergence tolerance: <= 0.1 eV [M]
  * Domain Boundary Mutual Exclusivity:
    - Pydantic model validator MUST fail closed and reject any molecular gas-phase parameters (A, B, C rotational constants, Eckart frame orientation, inertial defect Delta).

--------------------------------------------------------------------------------
Mandatory Content Structure for Each L3 Formalization:
--------------------------------------------------------------------------------
For Each L3 Task (L3.1.1, L3.1.2, L3.1.3), Your Formalization Must Explicitly Document:
1. Work Package Unique Identifier & Descriptive Title.
2. Single Responsible Execution Agent (cochem-coder).
3. Primary Targeted Codebase File Path (in `src/cochem_base/models/`).
4. Exact Input Preconditions & Prerequisites.
5. Concrete Deliverables (classes, methods, Pydantic validators, exports).
6. Quantitative Acceptance Criteria, Mathematical Invariants, and Numerical Tolerances.
7. Explicit Provenance Tags ([M] Method Matrix, [D] Deterministic Derivation, [E] Empirical Benchmark).
8. Upstream Predecessors & Downstream Dependencies.
9. Verification Method & Test Suite Target (e.g., `tests/test_product_ontology.py` and `tests/test_chunk17_verification_suite.py`).

================================================================================
4. MANDATORY OPERATIONAL RULE 2: PHYSICAL DISK PERSISTENCE ACROSS MIRRORS
================================================================================
You are STRICTLY FORBIDDEN from presenting your work solely in conversational chat text or temporary memory buffers. You MUST invoke your `write_to_file` tool (with Overwrite=true) to persist your output directly to disk across all designated mirror locations:

1. Primary Scratch Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_3_1_data_architecture_schema_formalization.md`

2. Conversation Artifact Mirror:
   `C:/Users/ansac/.gemini/antigravity-cli/brain/6b7b9b3b-d7bd-42b9-9311-108a4584c9ce/task3_3_1_data_architecture_schema_formalization.md`

3. Repository Docs Mirror:
   `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task3_3_1_Product_BM_Data_Architecture_Plane.md`

4. Ecosystem Master Mirror:
   `D:/__CoChem/.docs/Task3_3_1_Product_BM_Data_Architecture_Plane.md`

5. Dropzone SRS Mirror:
   `D:/__CoChem/__agentic/dropzones/inbox_srs/Task3_3_1_Product_BM_Data_Architecture_Plane.md`

6. Swarm State Ledger Synchronization:
   Update `swarm_state.json` across all canonical mirrors (`scratch/`, `D:/__CoChem/`, `D:/__CoChem/GitHub-Repo/CoChem-BASE/`, and dropzones) recording:
   * task_id: "TASK-3-3-1-DATA-ARCHITECTURE-PLANE-FORMALIZATION"
   * task_hierarchy: "Level 1 Task 3 -> Level 2 Roadmap Product B vs M -> Level 3 Task 3.3.1"
   * agent_name: "cochem-sdp-manager"
   * status: "SUCCESS"
   * pmbok_100_percent_rule_enforced: true
   * mece_decomposition_guaranteed: true
   * raci_enforced: true
   * artifacts_produced: list of persisted file paths
   * byte_counts and line_counts
   * sha256_checksums: calculated via `Get-FileHash -Algorithm SHA256` using `run_command`
   * audit_status: "PENDING_ASYMMETRIC_AUDIT" (auditors: ["cochem-audit", "adversary"])

7. Anti-Spoofing Zero-Token Gate:
   Ensure the persisted markdown specifications contain zero unelaborated routines, zero empty return blocks, zero fake fixtures, and zero forbidden placeholder tokens:
   `mock`, `dummy`, `stub`, `fake`, `placeholder`, `sample`, `NotImplementedError`, `pass`, `TODO`, `TBD`, `FIXME`.

================================================================================
5. MANDATORY OPERATIONAL RULE 3: RETURN FINAL REPORT WITH INODE CHECKSUMS
================================================================================
Upon completing file creation, disk persistence, checksum calculation, and ledger synchronization, you MUST return a comprehensive final text report in your conversational response.
Your report MUST begin with `[SDPM REPORT]` and conclude with `[VERIFICATION & HANDOFF SUMMARY]` detailing:
1. High-level execution status (SUCCESS).
2. The EXACT physical file paths created or modified on disk.
3. Total line counts and physical byte sizes of all created/modified files on disk.
4. Exact computed SHA-256 cryptographic digest of each file.
5. Confirmation of zero literal banned keywords confirmed by automated static inspection.
6. Confirmation of dynamic Mendeleev mass retrieval enforcement throughout the schema specifications.
7. Verification that Asymmetric Council Sign-off remains pending (`- [ ] Pending independent Agent Council audit`).
8. Formal handoff routing for `cochem-audit` and `adversary` to execute the downstream asymmetric audit.
```

---

## 3. Downstream Swarm Handoff & Asymmetric Audit Protocol

Once `cochem-sdp-manager` completes formalization of this dispatch prompt and reports its created files and SHA-256 digests:
1. **Asymmetric Audit Routing:** As `0rchestrator`, natively spin up `cochem-audit` and `adversary` sequentially via `invoke_subagent` (prioritizing Antigravity quota over external API calls).
2. **Verification Criteria:** The auditors will inspect all formalized artifacts against the 10-point audit checklist:
   - Complete formalization of L3.1.1, L3.1.2, and L3.1.3 adhering to PMBOK 100% Rule and MECE principles.
   - Pydantic v2 data models with `ConfigDict(frozen=True, extra="forbid")`.
   - Asymmetric top rotational constant ordering ($A_0 > B_0 > C_0 > 0$) in MHz.
   - Ray's asymmetry parameter calculation ($\kappa \in [-1, 1]$) with topological guard ($|\Delta \kappa| \le 0.05$).
   - Direct space lattice vectors, scalar triple product cell volume ($V_{\text{cell}} > 0$), and Monkhorst-Pack reciprocal k-point mesh density ($\rho_k \ge 0.04\text{ \AA}^{-1}$).
   - Strict $\Gamma$-point invariant ($V_{\text{cell}} > 2000\text{ \AA}^3$ required for `gamma_only = True`).
   - Mutual exclusivity enforcement: strict validation preventing mixing of gas-phase and periodic parameters.
   - Dynamic Mendeleev atomic and isotopic mass retrieval mandate throughout.
   - Total eradication of mocks, stubs (`NotImplementedError`, empty `pass`), and synthetic fixtures.
   - Cryptographic byte-for-byte parity across all canonical mirror locations and `swarm_state.json`.

---

## 4. Document Control & Ledger Synchronization Table

| Field | Primary Scratch Specification | Conversation Artifact Record | Repository Mirror Record | Ecosystem Mirror Record | Dropzone Mirror Record |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Physical File Path** | `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_3_1_dispatch_prompt.md` | `C:/Users/ansac/.gemini/antigravity-cli/brain/6b7b9b3b-d7bd-42b9-9311-108a4584c9ce/task3_3_1_dispatch_prompt.md` | `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_3_1_dispatch_prompt.md` | `D:/__CoChem/.docs/task3_3_1_dispatch_prompt.md` | `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_3_1_dispatch_prompt.md` |
| **Authoring Agent** | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` |
| **Designated Execution Agent** | `cochem-sdp-manager` | `cochem-sdp-manager` | `cochem-sdp-manager` | `cochem-sdp-manager` | `cochem-sdp-manager` |
| **Supervising Authority** | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` |
| **Lifecycle Status** | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` |
| **Governing Standards** | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 |
