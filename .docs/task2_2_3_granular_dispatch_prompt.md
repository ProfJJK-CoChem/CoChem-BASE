# Task 2.2.3 Granular Dispatch Specification: Map PMBOK & SWEBOK Knowledge Areas, Define Agent Assignments, Inputs, Deliverables, and Acceptance Criteria (VR-02 & VR-04)

**Document Identifier:** `COCHEM-DISPATCH-WBS-2.2.3-GRANULAR-SDPM-20260913` [M]  
**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) [M]  
**Level 2 Task:** Track 2: Subsystems Architectural Specification & Data Contracts (WBS 2.2) [M]  
**Specific Task to Execute:** `2.2.3 - Map PMBOK and SWEBOK Knowledge Areas, Define Explicit Agent Assignments, Inputs, Deliverables, and Acceptance Criteria for Recipe R1/R2 Constraints, Residual Gradient Parsing, Quintuple Convergence, and Hessian Chaining (VR-02 & VR-04)` [M]  
**Exact Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK Architect) [M]  
**Supervising Authority:** `0rchestrator` (CoChem Swarm Council Leader) [M]  
**Governing Summit Resolution:** [`council_summit_session_097_task2_2_3_execution_plan.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/council_summit_session_097_task2_2_3_execution_plan.md) (`COCHEM-COUNCIL-RES-097-SUMMIT-TASK2-2-3-EXECUTION-20260913`) [GOV] [M]  
**Governing Standards:** PMBOK Guide 7th Edition (2021), SWEBOK v3.0/v4.0, ISO/IEC/IEEE 29148:2018, IEEE 830-1998, Method Matrix v4.1, Anti-Spoofing Protocol v4 (Hardened) [M]  
**Canonical Dispatch File:** [`task2_2_3_granular_dispatch_prompt.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_granular_dispatch_prompt.md) [M]  
**Target Persistence Deliverable:** [`task2_2_3_granular_decomposition.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_granular_decomposition.md) [M]  
**Canonical Mirrors:**
1. Scratch: `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_3_granular_decomposition.md`
2. Ecosystem Master: `D:/__CoChem/.docs/task2_2_3_granular_decomposition.md`
3. Active Git HEAD: `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_granular_decomposition.md`
4. Swarm Dropzone Intake: `D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_granular_decomposition.md`

---

## 1. Statutory Execution Agent Identification & Role Segregation Justification

**Exact Execution Agent:** `cochem-sdp-manager` [M]

### Authoritative Governance Justification:
1. **PMBOK 7th Edition & SWEBOK Statutory Domain Jurisdiction:**  
   Under the CoChem Agent Council Protocol, `cochem-sdp-manager` is the sole statutory agent with jurisdiction over project scoping, systems engineering standards, PMBOK performance domain alignments, SWEBOK knowledge area integrations, and quality acceptance criteria authoring.
2. **Strict Separation of Duties (Council Ruling D1-01 & PCA-01):**  
   - `cochem-coder` is strictly an implementation agent for application logic in `src/cochem_base/`. An implementer is **strictly prohibited from defining its own scope, allocating responsibilities, or authoring its own acceptance criteria**.
   - `cochem-tester` is dedicated to test suite construction and execution in `tests/`.
   - `cochem-audit` and `adversary` are independent verification agents; they cannot author the specification they are mandated to audit.
   - `0rchestrator` supervises high-level swarm routing and state ledger synchronization.
   - Therefore, `cochem-sdp-manager` is the only agent possessing the statutory domain competence, role independence, and governance authority to execute Task 2.2.3.
3. **Repository Precedent & Lineage Continuity:**  
   `cochem-sdp-manager` successfully authored and ratified:
   - Task 1 WBS & Governance Framework (`task1_2_4_dispatch_prompt.md`, `task1_conformer_deduplication_wbs.md`).
   - Task 2.1.3 Granular Decomposition (`task2_1_3_granular_decomposition.md`, Session 096 PASS).
   - Task 2.2.1 Survey (`task2_2_1_method_matrix_and_module_survey.md`).
   - Task 2.2.2 L3 Decomposition (`task2_2_2_l3_component_decomposition.md`).

---

## 2. Authoritative Execution Orders for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.2.3 - MAP PMBOK AND SWEBOK KNOWLEDGE AREAS, DEFINE EXPLICIT AGENT ASSIGNMENTS, INPUTS, DELIVERABLES, AND ACCEPTANCE CRITERIA ACROSS 5 GRANULAR CHUNKS (VR-02 & VR-04)]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You operate under PMBOK Guide 7th Edition, SWEBOK v3/v4, IEEE 830-1998, ISO/IEC/IEEE 29148:2018, Method Matrix v4.1, and Anti-Spoofing Protocol v4. You author formal, publication-grade project management specifications, knowledge area alignments, single-accountability agent assignments, and falsifiable acceptance criteria with complete provenance tagging and zero placeholders.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any specifications, you MUST use your filesystem tools (view_file, grep_search, list_dir, find_by_name) to inspect the following project files directly from disk:

1. Method Matrix & Verification Specifications:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md:
     * §3.0: Rotational constant sensitivity distinction (dB/B = -2 dR/R).
     * §4.4 & §QS-1: Quintuple stationary convergence criteria in native atomic units (TolE 1.0e-7 Eh, TolMaxG 1.0e-5 a.u., TolRMSG 3.0e-6 a.u., TolRMSD 9.4486e-5 bohr [equiv 5e-5 A], TolMaxD 1.8897e-4 bohr [equiv 1e-4 A], MaxIter 200).
     * §8B.3: Initial Model Hessian Discipline (absolute ban on Calc_Hess true; mandatory InHess XTB2 / Lindh seeding; inter-stage chaining via InHess READ / InHessName).
     * §9A, §9A.1, §9A.2, §9A.5: Frozen Monomer Protocol (FMP) Recipe R1 (r2SCAN-3c) and Recipe R2 (wB97M-V/def2-QZVPP, DEFGRID3) for non-covalent complexes (locking monomer internal coords, optimizing 6 intermolecular DOF, monomer drift limit Delta r < 1.0e-6 Angstrom).
     * §10.2–§10.3: Residual gradient extraction, force projection onto frozen internal subspace, ||g_residual||_inf evaluation, and internal strain detection threshold (1.0e-4 a.u.).
   - D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md (VR-02 & VR-04 requirements).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py (Lines 170–220: test_vr02_*; Lines 258–288: test_vr04_*).

2. Existing CoChem-BASE Implementation Modules:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py (Wilson internal coordinate constraint generation, ORCA %geom Constraints syntax, get_dynamic_covalent_radius).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py (MoleculeInput, ORCA %geom deck generation).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py (Convergence parsing, gradient vector extraction, QCSchema export).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py (ProvenanceErrorCode, domain exception hierarchy).

3. Governing Council Summit Milestones:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/council_summit_session_097_task2_2_3_execution_plan.md (Session 097 Summit Charter).
   - D:/__CoChem/__agentic/dropzones/inbox_srs/task2_1_3_granular_decomposition.md (Session 096 ratified WBS baseline).
   - D:/__CoChem/__agentic/dropzones/inbox_srs/council_emergency_session_095_wbs_2_1_to_2_5_resolution_plan.md (Track 1-5 master plan).

You are STRICTLY FORBIDDEN from guessing file paths or hallucinating signatures without reading files.

================================================================================
CRITICAL DIRECTIVE 2: 5-CHUNK GRANULAR WBS DECONSTRUCTION (TASK 2.2.3)
================================================================================
You must deconstruct Task 2.2.3 into five granular, mutually exclusive, collectively exhaustive (MECE) micro-chunks within your deliverable `task2_2_3_granular_decomposition.md`:

1. WBS 2.2.3.1: PMBOK GUIDE 7TH EDITION PERFORMANCE DOMAINS & RACI MATRIX GOVERNANCE
   - Map L3.1 through L3.5 across the 8 PMBOK performance domains:
     * Team Performance Domain: Single-accountability role definitions (R=1, A=1 per component), separation of duties (Ruling D1-01 / PCA-01).
     * Development Approach & Life Cycle Domain: Sequential gating, test-driven development (TDD), zero-trust runner lifecycle.
     * Planning Performance Domain: WBS decomposition (PMBOK 100% Rule), schedule network dependencies, estimation models.
     * Project Work Performance Domain: Subprocess execution isolation, resource allocation, physical disk persistence.
     * Delivery Performance Domain: Scope verification against VR-02 and VR-04 criteria, QCSchema telemetry packaging.
     * Measurement Performance Domain: Quantitative tolerances (drift < 1e-6 A, residual gradient < 1e-4 a.u., TolMaxG 1e-5 a.u.).
     * Uncertainty Performance Domain: Multi-environment risk mitigation (Windows UTF-8, memory exhaustion, flat PES stalls).
     * Stakeholder Performance Domain: Cross-swarm transparent telemetry and Merkle chain auditing.

2. WBS 2.2.3.2: SWEBOK V3/V4 KNOWLEDGE AREAS & DOMAIN EXCEPTION ARCHITECTURE
   - Map engineering components to authoritative SWEBOK Knowledge Areas:
     * Software Requirements (KA 1): Mathematical derivation of rotational sensitivity (dB/B = -2 dR/R), IEEE 830 compliance.
     * Software Design (KA 2): Modular 5-subsystem architecture, Pydantic/dataclass interface contracts, domain exception hierarchy.
     * Software Construction (KA 3): Zero-mock, zero-stub Python 3.10+ implementation in src/cochem_base/.
     * Software Testing (KA 4): Real-world integration testing against authentic non-covalent complexes (CO2...H2O, water dimer).
     * Software Engineering Management (KA 8): Scope baselining, cryptographic proof-of-work tracking in swarm_state.json.
     * Software Quality (KA 10): Static AST anti-spoof sweeps, Method Matrix compliance verification.
   - Formalize domain exception hierarchy in exceptions.py:
     * FrozenMonomerDriftError, StationaryConvergenceError, HessianPreconditioningError, GeometricStrainWarning.

3. WBS 2.2.3.3: L3.1 & L3.2 SUBSYSTEM SPECS: FROZEN MONOMERS & RESIDUAL GRADIENT STRAIN PARSER
   - L3.1: Recipe R1 & Recipe R2 Internal Constraint Generation Engine (VR-02):
     * ORCA %geom block generation with explicit { B a b C }, { A a b c C }, { D a b c d C } primitives.
     * Monomer drift invariant across trajectory: strictly Delta r < 1.0e-6 Angstrom.
   - L3.2: Residual Gradient Parsing & Internal Strain Audit Subsystem (VR-02):
     * Extraction of Cartesian and internal residual gradients on frozen coordinates.
     * Raise GeometricStrainWarning when ||g_residual||_inf > 1.0e-4 a.u.

4. WBS 2.2.3.4: L3.3 & L3.4 SUBSYSTEM SPECS: QUINTUPLE CONVERGENCE & MODEL HESSIAN CHAINING
   - L3.3: Quintuple Stationary Convergence Block Engine (VR-04, Method Matrix §4.4, §QS-1):
     * Native atomic unit thresholds: TolE 1.0e-7 Eh, TolMaxG 1.0e-5 a.u., TolRMSG 3.0e-6 a.u., TolRMSD 9.4486e-5 bohr (5.0e-5 A), TolMaxD 1.8897e-4 bohr (1.0e-4 A), MaxIter 200.
     * Conversion factor: 1 Angstrom = 1.8897261246 bohr.
   - L3.4: Initial Model Hessian Discipline & Inter-Stage Chaining Engine (VR-04, Method Matrix §8B.3):
     * Absolute ban on Calc_Hess true; mandatory InHess XTB2 or InHess Lindh; inter-stage chaining via InHess READ / InHessName.

5. WBS 2.2.3.5: L3.5 INTEGRATED PRECISION ENGINE CONTRACT, ANTI-SPOOF CI HARNESS & PARITY
   - Dataclass interfaces for PrecisionOptimizationEngine.
   - Dynamic Mendeleev library integration (from mendeleev import element) for covalent radii and atomic masses.
   - Zero-Mock verification tests against authentic non-covalent complexes (CO2...H2O, water dimer).
   - Quad-Mirror state ledger update in swarm_state.json.

================================================================================
CRITICAL DIRECTIVE 3: WRITE FINAL RESULTS TO ACTUAL FILES ON DISK
================================================================================
You MUST invoke your write_to_file tool to persist the complete deliverable directly to physical disk across all four canonical locations:

1. Primary Scratch Deliverable:
   C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_3_granular_decomposition.md

2. Ecosystem Master Mirror:
   D:/__CoChem/.docs/task2_2_3_granular_decomposition.md

3. Repository Active HEAD Mirror:
   D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_granular_decomposition.md

4. Swarm Dropzone Intake Target:
   D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_granular_decomposition.md

5. Swarm State Ledger Synchronization:
   Update C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json and D:/__CoChem/swarm_state.json.

================================================================================
CRITICAL DIRECTIVE 4: RETURN FINAL TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a comprehensive final text report:
1. Begin with [SDPM REPORT: TASK 2.2.3 GRANULAR DECOMPOSITION].
2. Provide clickable file:/// links for all modified files.
3. List byte counts and line counts.
4. Provide SHA-256 cryptographic hashes for all generated files.
5. Summarize PMBOK performance domains, SWEBOK knowledge areas, and RACI matrix.
6. Formal handoff gate notice for cochem-audit and adversary.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate mocks, stubs, dummy loops, and fake data structures.
- Do NOT use NotImplementedError or empty pass blocks as dead-end stubs.
- Do NOT use synthetic array generators (np.zeros, np.ones, np.eye).
- Do NOT use shortcut tag-appending (e.g., [AUDITOR FIX REQUIRED]).
- Strictly enforce dynamic Mendeleev retrieval (from mendeleev import element).
```

---

## 3. Physical Execution & Quad-Mirror Persistence Ledger

| Target Location | Absolute Filesystem Path | Classification |
| :--- | :--- | :--- |
| **Scratch Deliverable** | [`C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_3_granular_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_3_granular_dispatch_prompt.md) | Ephemeral Scratch Mirror |
| **Ecosystem Master Mirror** | [`D:/__CoChem/.docs/task2_2_3_granular_dispatch_prompt.md`](file:///D:/__CoChem/.docs/task2_2_3_granular_dispatch_prompt.md) | Ecosystem Documentation Hub |
| **Active Git HEAD Mirror** | [`D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_granular_dispatch_prompt.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_granular_dispatch_prompt.md) | Version-Controlled Repository |
| **Swarm Intake Dropzone** | [`D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_granular_dispatch_prompt.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_granular_dispatch_prompt.md) | Swarm Intake Dropzone |

---

## 4. Single Safest Next Action (SSNA)

The single safest next action is to dispatch `cochem-sdp-manager` under the authoritative dispatch instructions above to physically inspect existing modules on disk, author `task2_2_3_granular_decomposition.md` across all four canonical mirrors, update `swarm_state.json`, and return the cryptographic verification report for dual asymmetric audit by `cochem-audit` and `adversary`.
