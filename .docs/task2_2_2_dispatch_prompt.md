# Task 2.2.2 Dispatch Specification: Deconstruct L2 Scope into Granular L3 Component Implementation Tasks (L3.1 through L3.5)

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.  
**Level 2 Task:** Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.  
**Specific Task to Execute:** `2.2.2 - Deconstruct L2 scope into granular L3 component implementation tasks (L3.1 through L3.5)`  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)  
**Canonical Dispatch File:** [`task2_2_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_dispatch_prompt.md)  
**Target Deliverable:** [`task2_2_2_l3_component_decomposition.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_l3_component_decomposition.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole authoritative agent responsible for scoping, requirements engineering, work package definition, and RACI governance. Parent Level 2 explicitly tasks the council with: *"Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining."* Task 2.2.2 requires deconstructing this L2 scope into granular, component-level Level 3 (L3) work packages (L3.1 through L3.5).
2. **Strict Role Segregation & Governance Boundaries:**  
   - Application coding is strictly reserved for `cochem-coder`. Assigning technical scoping, architectural work breakdown, and acceptance criteria formulation to `cochem-coder` violates the core governance invariant: **an implementer must never define their own scope, work package boundaries, or acceptance gates**.
   - Technical documentation and user manuals are reserved for `cochem-scribe`.
   - Physical test verification is strictly reserved for `cochem-tester`.
   - Independent verification is reserved for `cochem-audit` and `adversary`.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` authored all preceding WBS decompositions and governance scoping deliverables across Tasks 1 & 2:
   - Task 1 WBS & L3 decompositions: [`task1_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_5_dispatch_prompt.md), [`task1_3_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_3_dispatch_prompt.md)
   - Task 2 Level 2 WBS: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md)
   - Task 2.1.3 Decomposition: [`task2_1_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_1_3_dispatch_prompt.md)
   - Task 2.2.1 Baseline Survey: [`task2_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md)
   Assigning Task 2.2.2 to `cochem-sdp-manager` maintains unbroken project management continuity and single-point RACI accountability.

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.2.2 - DECONSTRUCT L2 SCOPE INTO GRANULAR L3 COMPONENT IMPLEMENTATION TASKS (L3.1 THROUGH L3.5)]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery), IEEE 830-1998, SWEBOK v3/v4, and the CoChem Method Matrix v4 to structure complex engineering objectives into formal, actionable, zero-mock Work Breakdown Structures (WBS) and component-level microtasks.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.
- Level 2: Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.
- Specific Task to Execute:
  2.2.2 - Deconstruct L2 scope into granular L3 component implementation tasks (L3.1 through L3.5).

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any task specifications, signatures, or WBS structures, you MUST use your filesystem tools (view_file, grep_search, list_dir, find_by_name) to read and inspect the following project files to gain empirical context:

1. Method Matrix & Verification Specifications:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md (and Method_Matrix/Method_Matrix_Hub.md):
     * §4.4 & §QS-1: Quintuple stationary convergence thresholds (TolE 1e-7 Eh, TolMaxG 1e-5 a.u., TolRMSG 3e-6 a.u., TolRMSD 5e-5 Angstrom, TolMaxD 1e-4 Angstrom, MaxIter 200).
     * §8B.3: Absolute ban on Calc_Hess true during optimization; mandatory model Hessians (InHess XTB2 or InHess Lindh); inter-stage Hessian chaining.
     * §9A, §9A.1, §9A.2, §9A.5: Recipe R1 (r2SCAN-3c) and Recipe R2 (wB97M-V/def2-QZVPP) Frozen Monomer Protocol (FMP) for non-covalent complexes (freeze monomer internal coordinates, optimize 6 intermolecular degrees of freedom).
     * §10.2–§10.3: Analytical gradient parsing, residual gradient projection, ||g_residual||_inf evaluation, internal strain detection.
   - D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md (Verification Requirements VR-02 and VR-04).

2. Existing CoChem-BASE Implementation Modules:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/fragment_partitioner.py (Monomer identification, covalent radii connectivity).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py (Wilson internal coordinate constraint generation, ORCA %geom Constraints syntax).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py (ORCA %geom deck generation, calculation schemas).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py (Convergence parsing, gradient vector extraction).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py (Execution orchestration, pipeline lifecycle).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py (Domain exception hierarchy).

3. Existing Planning & WBS Context in Scratch:
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md (Governing WBS structure and schema conventions).
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md (Survey scope and architectural findings).
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json (Current swarm execution ledger).

You are STRICTLY FORBIDDEN from guessing file paths, inventing arbitrary signatures without inspecting existing modules, or synthesizing specifications without tool-based inspection. Read the files first.

================================================================================
TECHNICAL SCOPE: COMPONENT DECONSTRUCTION (L3.1 THROUGH L3.5)
================================================================================
Deconstruct the Level 2 scope into exactly five granular, Mutually Exclusive, Collectively Exhaustive (MECE) L3 component implementation tasks:

- L3.1: Recipe R1 & Recipe R2 Internal Constraint Generation Engine (VR-02)
  * Scope: Wilson internal coordinate deck generation for Recipe R1 (r2SCAN-3c) and Recipe R2 (wB97M-V/def2-QZVPP).
  * Monomer coordinate locking: freeze all intramolecular bonds, angles, and dihedrals; relax strictly the 6 intermolecular degrees of freedom.
  * Invariant: monomer coordinate drift tolerance max |Delta r_intra| < 1.0e-6 Angstrom throughout the optimization trajectory.
  * Synthesis of ORCA %geom Constraints ... end syntax blocks.

- L3.2: Residual Gradient Parsing & Internal Strain Audit Subsystem (VR-02)
  * Scope: Extraction and projection of Cartesian and internal gradients from quantum calculation output files (.engrad, .out).
  * Projection onto frozen monomer coordinate subspace to isolate residual forces.
  * Quantitative metric: infinity norm of residual gradient ||g_residual||_inf.
  * Fail-closed trigger: raise ResidualStrainWarning or error when ||g_residual||_inf > 1.0e-4 a.u.

- L3.3: Quintuple Stationary Convergence Block Engine (VR-04, Method Matrix §4.4, §QS-1)
  * Scope: Enforcement of tightened ORCA %geom stationary point convergence criteria for non-covalent complexes:
    - TolE: 1.0e-7 Eh
    - TolMaxG: 1.0e-5 a.u.
    - TolRMSG: 3.0e-6 a.u.
    - TolRMSD: 5.0e-5 Angstrom (or Bohr equivalent)
    - TolMaxD: 1.0e-4 Angstrom
    - MaxIter: 200 iterations
  * Fail-closed validation logic rejecting false/premature convergence and forbidding loose default convergence presets.

- L3.4: Initial Model Hessian Discipline & Inter-Stage Chaining Engine (VR-04, Method Matrix §8B.3)
  * Scope: Strict interception and prohibition of exact initial Hessian calculations (Calc_Hess true is strictly banned).
  * Automated configuration of model Hessians: InHess XTB2 (GFN2-xTB) or InHess Lindh.
  * Inter-stage approximate Hessian chaining: carrying forward updated Hessians (.opt / .carthess) from pre-optimization stages into tight refinement stages.

- L3.5: Integrated Precision Optimization Execution Engine, Dataclass Contracts & Anti-Spoofing CI Harness (VR-02, VR-04)
  * Scope: End-to-end orchestration uniting L3.1 through L3.4 into cochem_calc_execution_router.py.
  * Strongly typed Pydantic v2 / dataclass schemas (RecipeConstraintConfig, QuintupleConvergenceCriteria, QuintupleConvergenceResult, ResidualGradientSummary, HessianChainingConfig).
  * Integration with CoChem domain exceptions (FrozenCoordinateDriftError, ForbiddenExactHessianError, ResidualStrainWarning, StationaryConvergenceFailureError).
  * Zero-mock test suite specifications using authentic non-covalent dimers (e.g., CO2...H2O, H2O...H2O) with genuine physical tensors.

================================================================================
MANDATORY SPECIFICATION SCHEMA FOR EACH L3 TASK (L3.1 THROUGH L3.5)
================================================================================
For EACH of the five tasks (L3.1 through L3.5), you MUST provide a complete specification block containing:
1. Unique Task Identifier: Hierarchical ID (e.g., L3.1, L3.2, L3.3, L3.4, L3.5).
2. Work Package Title & Objective: Concise, unambiguous engineering objective.
3. Single Responsible Swarm Agent (RACI 'R'): Exactly one accountable implementation agent (e.g., cochem-coder). Dual ownership is strictly forbidden.
4. Supervising / Auditing Agent (RACI 'A'): Designated auditor (e.g., cochem-audit and adversary).
5. Method Matrix Provenance Tag: Explicit classification ([M] for empirical benchmarks, [D] for derived mathematical formulas, [GOV] for project governance, [PROC] for procedures).
6. Input Prerequisites & Ingested Artifacts: Specific predecessor files, data models, or configuration objects required.
7. Fully Typed Python Signatures: Complete class, method, and function signatures with typed parameters, type hints, return types, and Pydantic/dataclass schema definitions.
8. Physical Constraints & Numerical Thresholds: Exact numerical constants, tolerances, and units (e.g., 1.0e-6 Angstrom, 1.0e-4 a.u., 1.0e-7 Eh).
9. Fail-Closed Error Handling Protocols: Specific custom exception classes to raise upon violation.
10. Target Deliverable Code Artifacts: Exact physical file paths to create or modify in CoChem-BASE (e.g., src/cochem_base/geometry/..., src/cochem_base/calc/...).
11. Zero-Mock Test Specifications: Pytest suite definitions, genuine physical molecular fixtures, and assertions required to pass the anti_spoof_linter.py static sweep.
12. Falsifiable Acceptance Criteria: Measurable binary pass/fail conditions.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL CODE / RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely emitting the decomposition to conversational chat or leaving results in ephemeral memory buffers.
You MUST invoke your write_to_file tool to persist the complete, unabridged decomposition artifact directly to physical disk at:

1. Primary Deliverable:
   C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_l3_component_decomposition.md

2. Swarm State Ledger Synchronization:
   Atomically update C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json using write_to_file (Overwrite=true) recording:
   {
     "anti_spoofing_compliance": true,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.2.2: Deconstruct L2 scope into granular L3 component implementation tasks (L3.1 through L3.5)",
     "wbs_level": "Level 2 / Task 2.2 Technical Scope Definition",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_l3_component_decomposition.md"
     ],
     "sha256_checksum": "<SHA256_DIGEST>"
   }

================================================================================
CRITICAL DIRECTIVE 3: RETURN FINAL TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a comprehensive final text report in your response.
Your report MUST begin with [SDPM REPORT] and conclude with a dedicated [VERIFICATION & HANDOFF SUMMARY] section detailing:
1. Execution status (SUCCESS or FAILURE).
2. Exact absolute and relative file paths modified or created on disk.
3. Physical byte count and line count of each generated artifact.
4. Cryptographic SHA-256 hash of each modified file.
5. Summary of the five decomposed L3 tasks (L3.1 through L3.5), single-agent RACI assignments, and provenance tag distribution.
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
