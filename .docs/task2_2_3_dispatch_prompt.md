# Task 2.2.3 Dispatch Specification: Map PMBOK & SWEBOK Knowledge Areas, Define Agent Assignments, Inputs, Deliverables, and Acceptance Criteria (VR-02 & VR-04)

**Document Identifier:** `COCHEM-DISPATCH-WBS-2.2.3-SDPM-20260910` [M]  
**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining. [M]  
**Level 2 Task:** Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining. [M]  
**Specific Task to Execute:** `2.2.3 - Map PMBOK and SWEBOK Knowledge Areas, Define Explicit Agent Assignments, Inputs, Deliverables, and Acceptance Criteria for Recipe R1/R2 Constraints, Residual Gradient Parsing, Quintuple Convergence, and Hessian Chaining (VR-02 & VR-04)` [M]  
**Exact Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK Architect) [M]  
**Supervising Authority:** `0rchestrator` (CoChem Swarm Council Leader) [M]  
**Governing Standards:** PMBOK Guide 7th Edition (2021), SWEBOK v3.0/v4.0, ISO/IEC/IEEE 29148:2018, IEEE 830-1998, Method Matrix v4.1, Anti-Spoofing Protocol v4 [M]  
**Canonical Dispatch File:** [`task2_2_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/dbb1943c-043e-475c-9a3e-7270b5e0ce2e/task2_2_3_dispatch_prompt.md) [M]  
**Target Persistence Deliverable:** [`task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md`](file:///D:/__CoChem/.docs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md) [M]  
**Target Scratch Mirror:** [`task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md) [M]  
**Target Repository Mirror (Active HEAD):** [`task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md) [M]  
**Dropzone Intake Target:** [`task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md) [M]  
**Lifecycle Status:** `APPROVED_FOR_IMMEDIATE_DISPATCH` [M]  

---

## 1. Execution Agent Selection & Authoritative Justification

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & SWEBOK Architect) [M]

### Authoritative Justification Ledger:

1. **PMBOK 7th Edition & SWEBOK v3/v4 Statutory Domain Authority:**  
   Under the CoChem Agent Council Protocol, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole statutory agent holding formal authority over project scoping, systems engineering standards, PMBOK 7th Edition knowledge/performance domain alignment, SWEBOK v3/v4 software engineering discipline integration, and quality acceptance gate definition. In the sequential deconstruction of Level 2 (*"Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining"*):
   - **Task 2.2.1** established the empirical survey of Method Matrix specifications and existing codebase modules (`task2_2_1_method_matrix_and_module_survey.md`) [M].
   - **Task 2.2.2** deconstructed the scope into five granular L3 component implementation microtasks (`task2_2_2_l3_component_decomposition.md`) [M].
   - **Task 2.2.3** synthesizes the authoritative PMBOK & SWEBOK mapping, formalizes single-point RACI responsibility allocations, and establishes falsifiable, zero-mock acceptance criteria across all L3 work packages (`task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md`) [M].

2. **Strict Role Segregation & Separation of Duties (Council Ruling D1-01 & PCA-01):**  
   - `@cochem-coder` is strictly an implementation agent for application logic in `src/cochem_base/`. Under Permanent Corrective Action 01 (`PCA-01`) and Disciplinary Ruling D1-01, an implementing coder is **strictly prohibited from defining its own scope, allocating responsibilities, establishing governance gates, or authoring acceptance criteria**. Allowing an implementer to author its own acceptance criteria creates a fundamental conflict of interest and violates zero-trust governance [M].
   - `cochem-tester` is strictly dedicated to test harness construction and pytest execution in `tests/` [M].
   - `cochem-scribe` is specialized in publication typesetting and user-facing manuals [M].
   - `cochem-audit` and `adversary` are independent asymmetric auditing agents; they cannot author the specification they are mandated to audit [M].
   - `0rchestrator` supervises high-level swarm lifecycle routing and state ledger synchronization [M].
   - Therefore, `cochem-sdp-manager` is the only agent possessing the statutory domain competence, role independence, and governance authority to execute Task 2.2.3 [M].

3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` authored all preceding ratified WBS, scoping, and governance deliverables across the CoChem ecosystem:
   - Task 1 WBS & Governance: [`task1_2_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_4_dispatch_prompt.md), [`task1_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_5_dispatch_prompt.md), [`task1_3_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_3_dispatch_prompt.md), [`task1_5_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_2_dispatch_prompt.md).
   - Task 2 Survey & Decomposition: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md), [`task2_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md), [`task2_2_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_dispatch_prompt.md), [`task2_2_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_dispatch_prompt.md), [`task2_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_5_dispatch_prompt.md).
   - Task 3 & Task 5 Baselines: [`task3_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md), [`task5_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_2_1_dispatch_prompt.md), [`task5_2_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_2_2_dispatch_prompt.md), [`task5_2_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_2_3_dispatch_prompt.md).
   Assigning Task 2.2.3 to `cochem-sdp-manager` ensures single-point RACI accountability and unbroken schema continuity across the project lifecycle [M].

4. **Deep Method Matrix v4.1 & Anti-Spoofing Protocol v4 Integration:**  
   `cochem-sdp-manager` incorporates the complete Method Matrix v4.1 rule set into all work package definitions:
   - Rotational constant sensitivity distinction ($dB/B = -2 dR/R$, §3.0) [D].
   - Quintuple stationary convergence block (`TolMaxG 1e-5`, `TolE 1e-7`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`, `MaxIter 200`, §4.4) [M].
   - Model Hessian preconditioning (`InHess XTB2` / `InHess Lindh`) and strict ban on `Calc_Hess true` (§8B.3) [M].
   - Frozen Monomer Protocol (FMP) Recipe R1 ($\text{r}^2\text{SCAN-3c}$) and Recipe R2 ($\omega\text{B97M-V/def2-QZVPP}$, `DEFGRID3`) with intramolecular drift tolerance $\Delta r < 1.0\times 10^{-6}\text{ \AA}$ (§9A.1–9A.5) [M].
   - Residual gradient logging ($\|\mathbf{g}_{\text{residual}}\|_{\infty} \le 1.0\times 10^{-4}\text{ a.u.}$) and strain caveat injection (§10.2–10.3) [D].
   - Mendeleev library dynamic mass retrieval mandate (`from mendeleev import element`, zero hardcoded tables) [M].
   - Anti-Spoofing Protocol v4: Zero mocks, zero stubs (`NotImplementedError`, empty `pass`), zero synthetic arrays, and mandatory non-volatile disk persistence [M].

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.2.3 - MAP PMBOK AND SWEBOK KNOWLEDGE AREAS, DEFINE EXPLICIT AGENT ASSIGNMENTS, INPUTS, DELIVERABLES, AND ACCEPTANCE CRITERIA FOR TASK 2 (VR-02 & VR-04)]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You operate under the PMBOK Guide 7th Edition (Systems View for Project Delivery), SWEBOK v3.0/v4.0, IEEE 830-1998, ISO/IEC/IEEE 29148:2018, the CoChem Method Matrix v4.1, and the Anti-Spoofing Protocol v4. You author formal, publication-grade project management specifications, knowledge area alignments, single-accountability agent assignments, and falsifiable acceptance criteria with complete provenance tagging and zero placeholders.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining. [M]
- Level 2: Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining. [M]
- Specific Task to Execute:
  2.2.3 - Map PMBOK and SWEBOK Knowledge Areas, Define Explicit Agent Assignments, Inputs, Deliverables, and Acceptance Criteria for Recipe R1/R2 Constraints, Residual Gradient Parsing, Quintuple Convergence, and Hessian Chaining (VR-02 & VR-04). [M]

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any mappings, task specifications, or acceptance criteria, you MUST use your filesystem tools (view_file, grep_search, list_dir, find_by_name) to read and inspect the following project files directly from disk to gain complete empirical context:

1. Method Matrix & Verification Specifications:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md (and Method_Matrix/Method_Matrix_Hub.md):
     * §4.4 & §QS-1: Quintuple stationary convergence criteria (TolE 1.0e-7 Eh, TolMaxG 1.0e-5 a.u., TolRMSG 3.0e-6 a.u., TolRMSD 5.0e-5 Angstrom, TolMaxD 1.0e-4 Angstrom, MaxIter 200).
     * §8B.3: Initial Model Hessian Discipline (absolute ban on Calc_Hess true; mandatory InHess XTB2 or Lindh; inter-stage Hessian chaining via InHess READ / InHessName).
     * §9A, §9A.1, §9A.2, §9A.5: Frozen Monomer Protocol (FMP) Recipe R1 (r2SCAN-3c) and Recipe R2 (wB97M-V/def2-QZVPP, DEFGRID3) for non-covalent complexes (locking monomer internal coords, optimizing 6 intermolecular DOF, monomer drift limit Delta r < 1.0e-6 Angstrom).
     * §10.2–§10.3: Residual gradient extraction, force projection onto frozen internal subspace, ||g_residual||_inf evaluation, and internal strain detection threshold (1.0e-4 a.u.).
   - D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md (Governing Verification Matrix: VR-02 Frozen Monomer Protocol and VR-04 Quintuple Stationary Block).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py (Lines 170–220: test_vr02_*; Lines 258–288: test_vr04_*).

2. Existing CoChem-BASE Implementation Modules:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/fragment_partitioner.py (Monomer identification, covalent radii connectivity).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py (Wilson internal coordinate constraint generation, ORCA %geom Constraints syntax).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py (ORCA %geom deck generation, calculation schemas).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py (Convergence parsing, gradient vector extraction).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py (Execution orchestration, pipeline lifecycle).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py (Domain exception hierarchy).

3. Preceding Planning, Survey & Decomposition Deliverables:
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md (Governing WBS architecture).
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md (Baseline survey findings).
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_l3_component_decomposition.md (Deconstructed L3.1 through L3.5 component specifications).
   - D:/__CoChem/__agentic/dropzones/inbox_srs/council_emergency_session_027_resolution_plan.md (Council governance baseline).
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json (Current swarm execution ledger).

You are STRICTLY FORBIDDEN from guessing file paths, hallucinating signatures without inspecting existing modules, or synthesizing acceptance criteria without tool-based inspection. Read the files first.

================================================================================
TECHNICAL SCOPE & DELIVERABLE REQUIREMENTS (TASK 2.2.3)
================================================================================
You must author an exhaustive, publication-grade architectural specification: `task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md`.

The deliverable must incorporate the following comprehensive sections:

1. EXECUTIVE SCOPE & GOVERNANCE FOUNDATIONS:
   - Harmonize Level 1 Task 2 and Level 2 Scope Definition under PMBOK Guide 7th Edition and SWEBOK v3/v4.
   - Establish the governance scope across the five L3 engineering components:
     * L3.1: Recipe R1 & Recipe R2 Internal Constraint Generation Engine (VR-02)
     * L3.2: Residual Gradient Parsing & Internal Strain Audit Subsystem (VR-02)
     * L3.3: Quintuple Stationary Convergence Block Engine (VR-04, Method Matrix §4.4, §QS-1)
     * L3.4: Initial Model Hessian Discipline & Inter-Stage Chaining Engine (VR-04, Method Matrix §8B.3)
     * L3.5: Integrated Precision Optimization Execution Engine, Dataclass Contracts & Anti-Spoofing CI Harness (VR-02, VR-04)

2. PMBOK GUIDE 7TH EDITION PERFORMANCE DOMAINS MAPPING:
   - Map Task 2 engineering activities to the PMBOK 7th Edition Performance Domains:
     * Team Performance Domain: Single-accountability role definitions, separation of duties (Ruling D1-01), RACI boundaries.
     * Development Approach & Life Cycle Domain: Sequential gating, test-driven development (TDD), zero-trust runner lifecycle.
     * Planning Performance Domain: WBS decomposition (PMBOK 100% Rule), schedule network dependencies, estimation models.
     * Project Work Performance Domain: Subprocess execution isolation, resource allocation, physical disk persistence.
     * Delivery Performance Domain: Scope verification against VR-02 and VR-04 criteria, QCSchema telemetry packaging.
     * Measurement Performance Domain: Quantitative tolerances (drift < 1e-6 A, residual gradient < 1e-4 a.u., TolMaxG 1e-5).
     * Uncertainty Performance Domain: Multi-environment risk mitigation (Windows UTF-8, memory exhaustion, flat PES stalls).

3. SWEBOK V3/V4 KNOWLEDGE AREAS (KA) INTEGRATION:
   - Map each engineering component to authoritative SWEBOK Knowledge Areas:
     * Software Requirements (KA 1): Mathematical derivation of rotational sensitivity (dB/B = -2 dR/R), IEEE 830 compliance.
     * Software Design (KA 2): Modular 5-subsystem architecture, Pydantic/dataclass interface contracts, domain exception hierarchy.
     * Software Construction (KA 3): Zero-mock, zero-stub Python 3.10+ implementation in src/cochem_base/.
     * Software Testing (KA 4): Real-world integration testing against authentic non-covalent complexes (CO2...H2O, water dimer).
     * Software Engineering Management (KA 8): Scope baselining, cryptographic proof-of-work tracking in swarm_state.json.
     * Software Quality (KA 10): Static AST anti-spoofing sweeps, Method Matrix compliance verification.

4. EXPLICIT SINGLE-ACCOUNTABILITY SWARM AGENT ASSIGNMENTS:
   - Provide an explicit assignment ledger for each of the five L3 components:
     * Exactly ONE Responsible ('R') agent per component (e.g., @cochem-coder for construction, cochem-tester for test execution).
     * Exactly ONE Accountable ('A') agent per component holding ultimate governance and sign-off authority.
     * Explicit Consulted ('C') agents (domain specialists: researcher for quantum chemistry, cochem-improve for optimization).
     * Explicit Informed ('I') agents (stakeholders: 0rchestrator, cochem-scribe).
   - Reaffirm Disciplinary Ruling D1-01: Prohibit non-coder agents from writing production code in src/cochem_base/.

5. INPUT PREREQUISITES & INGESTED ARTIFACTS PER L3 COMPONENT:
   - Define exact input data structures, configuration models, and predecessor artifacts required before each L3 task can execute.
   - Specify required domain models (e.g., MoleculeInput, MonomerDefinition, RecipeConstraintConfig).

6. SPECIFIC DELIVERABLES & TARGET FILEPATHS:
   - Explicitly list target production code files in src/cochem_base/ (constraints.py, cochem_calc_input_generator.py, etc.).
   - Explicitly list target test files in tests/ (test_chunk17_verification_suite.py, etc.).
   - Explicitly list target governance and documentation files in .docs/ and scratch/.

7. FALSIFIABLE ACCEPTANCE CRITERIA & NUMERICAL THRESHOLDS:
   - Formulate binary, falsifiable pass/fail acceptance criteria for each L3 component:
     * Criterion 1 (Constraint Generation): ORCA %geom block generated with explicit { B a b C }, { A a b c C }, { D a b c d C } primitives; intramolecular drift across trajectory strictly Delta r < 1.0e-6 Angstrom.
     * Criterion 2 (Residual Gradients): Output parser extracts Cartesian/internal residual gradients on frozen coordinates; raises warning/error when ||g_residual||_inf > 1.0e-4 a.u.
     * Criterion 3 (Quintuple Convergence): Input generator injects TolE 1.0e-7, TolMaxG 1.0e-5, TolRMSG 3.0e-6, TolRMSD 5.0e-5, TolMaxD 1.0e-4, MaxIter 200 into all Product A/C ORCA decks; rejects loose defaults.
     * Criterion 4 (Model Hessian Discipline): Input validator detects and strips Calc_Hess true; injects InHess XTB2 or InHess Lindh; enables inter-stage chaining via InHess READ.
     * Criterion 5 (Zero-Mock & Mendeleev): 100% dynamic mass queries (from mendeleev import element); 0 NotImplementedError; 0 empty pass blocks; 0 synthetic coordinate arrays (np.zeros, np.ones).

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely emitting the specification to conversational chat or leaving results in ephemeral memory buffers.
You MUST invoke your write_to_file tool to persist the complete, unabridged deliverable directly to physical disk across the canonical locations:

1. Primary Scratch Deliverable:
   C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md

2. Ecosystem Master Mirror:
   D:/__CoChem/.docs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md

3. Repository Active HEAD Mirror:
   D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md

4. Swarm Dropzone Intake Target:
   D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md

5. Swarm State Ledger Synchronization:
   Atomically update C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json and D:/__CoChem/swarm_state.json using write_to_file (Overwrite=true) recording:
   {
     "anti_spoofing_compliance": true,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.2.3: Map PMBOK and SWEBOK Knowledge Areas, Define Explicit Agent Assignments, Inputs, Deliverables, and Acceptance Criteria for Recipe R1/R2 Constraints, Residual Gradient Parsing, Quintuple Convergence, and Hessian Chaining (VR-02 & VR-04)",
     "wbs_level": "Level 2 / Task 2.2 Technical Scope Definition",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "zero_mock_enforced": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md",
       "D:/__CoChem/.docs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md",
       "D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md",
       "D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md"
     ],
     "sha256_checksum": "<COMPUTED_SHA256>"
   }

================================================================================
CRITICAL DIRECTIVE 3: RETURN FINAL TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a comprehensive final text report in your response.
Your report MUST begin with [SDPM REPORT] and conclude with a dedicated [VERIFICATION & HANDOFF SUMMARY] section detailing:
1. Execution status (SUCCESS or FAILURE).
2. Exact absolute and relative file paths modified or created on disk with clickable file:/// URLs.
3. Physical byte count and line count of each generated artifact.
4. Cryptographic SHA-256 hash of each modified file.
5. Summary of the PMBOK performance domain mappings, SWEBOK knowledge areas, single-agent RACI assignments, and provenance tag distribution.
6. Formal handoff gate notice for cochem-audit and adversary for asymmetric audit verification.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate mocks, stubs, dummy loops, and fake data structures.
- Do NOT use NotImplementedError or empty pass blocks as dead-end stubs.
- Do NOT use synthetic array generators (np.zeros, np.ones, np.eye) to fake tensors or coordinates.
- Do NOT use shortcut tag-appending (e.g., [AUDITOR FIX REQUIRED]); deliver complete, production-grade specifications.
- Strictly enforce dynamic Mendeleev retrieval (from mendeleev import element).
```

---

## 3. Physical Execution & Quad-Mirror Persistence Ledger

To satisfy Anti-Spoofing Protocol v4 Section 3.2 and permanently eliminate Dropzone Starvation (DEF-AUDIT-211-06), this dispatch specification has been physically persisted across all four canonical ecosystem mirror locations:

| Target Location | Absolute Filesystem Path | Classification |
| :--- | :--- | :--- |
| **Primary Brain Target** | [`C:/Users/ansac/.gemini/antigravity-cli/brain/dbb1943c-043e-475c-9a3e-7270b5e0ce2e/task2_2_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/dbb1943c-043e-475c-9a3e-7270b5e0ce2e/task2_2_3_dispatch_prompt.md) | Primary Artifact Master |
| **Ecosystem Master Mirror** | [`D:/__CoChem/.docs/task2_2_3_dispatch_prompt.md`](file:///D:/__CoChem/.docs/task2_2_3_dispatch_prompt.md) | Ecosystem Documentation Hub |
| **Active Git HEAD Mirror** | [`D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_dispatch_prompt.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_2_3_dispatch_prompt.md) | Version-Controlled Repository |
| **Swarm Intake Dropzone** | [`D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_dispatch_prompt.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/task2_2_3_dispatch_prompt.md) | Swarm Intake Dropzone |

---

## 4. Single Safest Next Action (SSNA)

The single safest next action is to dispatch `cochem-sdp-manager` using the authoritative dispatch prompt above to physically ingest the governing files, author the PMBOK/SWEBOK mapping and acceptance criteria specification (`task2_2_3_pmbok_swebok_mapping_and_acceptance_criteria.md`) to disk, synchronize the swarm state ledger, and return the cryptographic file verification report.
