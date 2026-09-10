# Task 2.2.1 Dispatch Specification: Survey Existing Method Matrix Specifications & Geometry/Calc Modules in CoChem-BASE

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.  
**Level 2 Task:** Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.  
**Specific Task to Execute:** `2.2.1 - Survey existing Method Matrix specifications and geometry/calc modules in CoChem-BASE`  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)  
**Canonical Dispatch File:** [`task2_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md)  
**Target Persistence Deliverable:** [`task2_2_1_method_matrix_and_module_survey.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole authoritative persona responsible for scoping, requirements engineering, work package definition, and RACI governance. Parent Level 2 explicitly tasks the council with: *"Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining."* In standard systems engineering practice, executing Task 2.2.1—surveying the authoritative baseline specifications (Method Matrix v4) and existing codebase implementation modules (`geometry/` and `calc/` in `CoChem-BASE`)—is the mandatory first step to establish an empirical, zero-mock scope definition.
2. **Strict Role Segregation & Governance Boundary:**  
   - Application coding is strictly reserved for `cochem-coder`. Assigning technical scoping and acceptance criteria formulation to `cochem-coder` would violate the fundamental governance invariant that an implementer must never define their own scope or write their own acceptance gates.
   - Physical test verification is strictly reserved for `cochem-tester`.
   - Architectural and quality audits are strictly reserved for `cochem-audit` and `adversary`.
   - Architectural reviews of proposals are handled by `cochem-improve`. While `cochem-improve` reviews architectural vectors against the Method Matrix, the authoritative formulation of formal project scope, WBS deliverables, RACI assignments, and acceptance criteria belongs exclusively to `cochem-sdp-manager`.
3. **Historical Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` authored all preceding WBS decompositions and governance scoping deliverables across Tasks 1 & 2:
   - Task 1.2.3: [`task1_2_3_prompt_audit_report.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task1_2_3_prompt_audit_report.md)
   - Task 1.3.1–1.3.4: [`task1_3_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_3_dispatch_prompt.md), [`task1_3_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_4_dispatch_prompt.md)
   - Task 1.5.2–1.5.3: [`task1_5_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_2_dispatch_prompt.md), [`task1_5_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_3_dispatch_prompt.md)
   - Task 2.1.3: [`task2_1_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_1_3_dispatch_prompt.md)
   - Task 2 Level 2 WBS: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md)
   Assigning Task 2.2.1 to `cochem-sdp-manager` maintains uninterrupted project management continuity and single-point RACI accountability.

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.2.1 - SURVEY EXISTING METHOD MATRIX SPECIFICATIONS AND GEOMETRY/CALC MODULES IN COCHEM-BASE]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery), IEEE 830-1998, SWEBOK v3/v4, and the CoChem Method Matrix v4 to structure engineering objectives into formal, actionable, zero-mock specifications, architecture surveys, and component-level microtasks.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.
- Level 2: Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.
- Specific Task to Execute:
  2.2.1 - Survey existing Method Matrix specifications and geometry/calc modules in CoChem-BASE.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any survey findings or technical scope definitions, you MUST use your filesystem inspection tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to read and inspect the local filesystem to gain complete empirical context:

1. Ingest Governing Method Matrix Specifications:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` (and `Method_Matrix/Method_Matrix_Hub.md`):
     * §4.4 & §QS-1: Mandatory Tight Stationary Point Convergence Thresholds:
       TolE <= 1.0e-7 Eh, TolMaxG <= 1.0e-5 a.u., TolRMSG <= 3.0e-6 a.u., TolRMSD <= 5.0e-5 Angstrom (or Bohr equivalents), TolMaxD <= 1.0e-4 Angstrom, MaxIter 200.
     * §8B.3: Methodological Bans on `Calc_Hess true` for geometry optimizations; mandatory injection of model Hessians (`InHess XTB2` or `Lindh`).
     * §9A, §9A.1, §9A.2, §9A.5: Recipe R1 (r2SCAN-3c with experimental/CCCBDB microwave monomer geometries) and Recipe R2 (wB97M-V/def2-QZVPP with CCSD(T)/CBS monomers) Frozen-Monomer Protocol (FMP) for non-covalent/van der Waals complexes (freeze monomer internal coordinates, optimize 6 intermolecular degrees of freedom).
     * §10.2–§10.3: Conservative analytical gradient evaluations, residual gradient parsing, and internal coordinate strain detection.

2. Ingest Existing CoChem-BASE Implementation Modules:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/fragment_partitioner.py` (Fragment clustering, covalent radii connectivity, monomer identification).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py` (Wilson internal coordinate constraint deck generation, `%geom Constraints` syntax).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/vdw_screener.py` (van der Waals complex screening).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py` (ORCA input deck builder, `%geom` block formatting, calculation presets).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py` (Output extraction, gradient parsing, geometry step evaluation).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_grid_convergence.py` (DEFGRID1 -> DEFGRID3 dynamic grid lifecycle).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py` (Calculation routing and execution management).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py` (Domain exception hierarchy).

3. Ingest Verification Requirements and Test Baselines:
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md` (Governing Verification Matrix: VR-02 Frozen Monomer Protocol and VR-04 Quintuple Stationary Block).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py` (Existing unit/integration tests for VR-02 and VR-04).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/geometry/test_fragment_partitioner_constraints.py` (Existing constraint tests).

4. Ingest Swarm Ledger & Planning Baselines:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Swarm execution ledger).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md` (Governing WBS architecture).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_1_3_dispatch_prompt.md` (Predecessor L3 decomposition).

You are STRICTLY FORBIDDEN from guessing file locations, hallucinating module contents, or synthesizing specifications without tool-based inspection. Gain full empirical context from these files first.

================================================================================
TECHNICAL SCOPE & DELIVERABLE STRUCTURE FOR TASK 2.2.1
================================================================================
You must author an exhaustive, production-grade architectural survey artifact: `task2_2_1_method_matrix_and_module_survey.md`.

The survey deliverable must incorporate the following comprehensive sections:

1. EXECUTIVE SUMMARY & SURVEY OBJECTIVES:
   - Harmonize Level 1 Task 2 and Level 2 Scope Definition.
   - Clarify the survey's purpose: establishing the baseline for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and model Hessian discipline.
   - SWEBOK v3/v4 Software Requirements and PMBOK 7th Edition compliance statement.

2. METHOD MATRIX v4 AUTHORITATIVE SPECIFICATION SURVEY:
   - Deep survey of Method Matrix requirements governing Task 2:
     * Recipe R1 (§9A, §9A.1, §9A.5): r2SCAN-3c composite DFT with experimental/CCCBDB microwave monomer geometries ($r_e^{\text{SE}}$). Freezes all intramolecular internal coordinates (bonds, angles, dihedrals); relaxes strictly the 6 intermolecular degrees of freedom.
     * Recipe R2 (§9A, §9A.2, §9A.5): wB97M-V/def2-QZVPP high-precision protocol with CCSD(T)/CBS monomers. Identical frozen internal coordinate constraints; provides sub-0.02 Å intermolecular geometry accuracy.
     * Quintuple Stationary Convergence Block (§4.4, §QS-1): Mandates all 5 thresholds (`TolE 1.0e-7`, `TolMaxG 1.0e-5`, `TolRMSG 3.0e-6`, `TolRMSD 5.0e-5`, `TolMaxD 1.0e-4`, `MaxIter 200`). Banning default ORCA loose presets without override.
     * Initial Model Hessian Discipline (§8B.3): Absolute ban on `Calc_Hess true` for optimizations; mandate `InHess XTB2` or `InHess Lindh`. Model Hessian chaining from Stage 1 (`.opt` / `.carthess`) forward to Stage 2.
     * Residual Gradient Parsing (§10.2–§10.3): Extract Cartesian and internal gradients; project onto frozen monomer coordinate subspace; compute $\|\mathbf{g}_{\text{residual}}\|_{\infty}$; raise geometric strain alert if $\|\mathbf{g}_{\text{residual}}\|_{\infty} > 1.0 \times 10^{-4}\text{ a.u.}$

3. COCHEM-BASE CODEBASE MODULE SURVEY & GAP ANALYSIS:
   - Detailed structural analysis of existing Python modules:
     * `src/cochem_base/geometry/fragment_partitioner.py`: Current capability vs required Recipe R1/R2 automated constraint generation. Identify missing Wilson B-matrix coordinate generators and frozen internal coordinate lock synthesis.
     * `src/cochem_base/geometry/constraints.py`: Existing constraint definitions vs ORCA `%geom Constraints` syntax requirements.
     * `src/cochem_base/calc/cochem_calc_input_generator.py`: Existing `%geom` generation vs mandatory quintuple block injection and model Hessian parameters.
     * `src/cochem_base/calc/cochem_calc_output_parser.py`: Existing parsing logic vs quintuple multi-threshold verification and residual gradient extraction from `.engrad` / `.out`.
     * `src/cochem_base/calc/cochem_grid_convergence.py`: Interaction with dynamic grid tightening (`DEFGRID1` -> `DEFGRID3`).
     * `src/cochem_base/exceptions.py`: Coverage of custom exceptions (`FrozenCoordinateDriftError`, `ForbiddenExactHessianError`, `ResidualStrainWarning`, `StationaryConvergenceFailureError`).
   - Detailed Gap Analysis Matrix: Feature / Requirement | Existing Module State | Gap Identified | Remediation Action.

4. TECHNICAL INTERFACE CONTRACTS & DATA MODELS BASELINE:
   - Define concrete data models and interfaces required for Level 2 deliverables:
     * `RecipeConstraintConfig`: Dataclass specifying recipe type (`R1` vs `R2`), monomer definitions, and frozen coordinate masks.
     * `QuintupleConvergenceCriteria`: Dataclass holding the 5 numerical thresholds.
     * `QuintupleConvergenceResult`: Dataclass holding actual evaluated values, boolean pass/fail per threshold, and overall convergence status.
     * `ResidualGradientSummary`: Dataclass holding $\|\mathbf{g}_{\text{residual}}\|_{\infty}$, RMS residual gradient, high-strain coordinate IDs, and strain warning flags.
     * `HessianChainingConfig`: Dataclass defining initial Hessian mode (`XTB2`, `Lindh`), predecessor Hessian source path, and fallback policies.

5. VERIFICATION REQUIREMENTS & ACCEPTANCE CRITERIA MAPPING (VR-02 & VR-04):
   - Formal mapping to SRS Chunk 17 Verification Matrix:
     * VR-02 Acceptance Metric: Monomer internal coordinate drift $\max |\Delta r_{\text{intra}}| < 1.0 \times 10^{-6}\text{ \AA}$ throughout the trajectory. Residual gradient $\|\mathbf{g}_{\text{residual}}\|_{\infty}$ parsed and logged.
     * VR-04 Acceptance Metric: Strict verification of all 5 stationary convergence criteria. Zero occurrences of `Calc_Hess true` in generated optimization decks. Demonstration of `InHess XTB2` or chained Hessian utilization.

6. SWARM RACI ASSIGNMENTS FOR LEVEL 2 DOWNSTREAM TASKS:
   - Unambiguous RACI matrix assigning responsible execution agents for implementation (`cochem-coder`), testing (`cochem-tester`), governance (`cochem-sdp-manager`), and audit (`cochem-audit` / `adversary`).

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL CODE / RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely emitting the survey findings to conversational chat or leaving results in ephemeral memory buffers.
You MUST invoke your `write_to_file` tool to persist the complete, unabridged survey document directly to physical disk at:

1. Primary Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md`

2. Swarm State Ledger Synchronization:
   Atomically update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` using `write_to_file` (Overwrite=true) recording:
   ```json
   {
     "anti_spoofing_compliance": true,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.2.1: Survey existing Method Matrix specifications and geometry/calc modules in CoChem-BASE",
     "wbs_level": "Level 2 / Task 2.2 Technical Scope Definition",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md"
     ],
     "sha256_checksum": "<SHA256_DIGEST>"
   }
   ```

================================================================================
CRITICAL DIRECTIVE 3: RETURN FINAL TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a comprehensive final text report in your final response.
Your report MUST begin with `[SDPM REPORT]` and conclude with a dedicated `[VERIFICATION & HANDOFF SUMMARY]` section detailing:
1. Execution status (`SUCCESS` or `FAILURE`).
2. Exact absolute and relative file paths modified or created on disk.
3. Physical byte count and line count of each generated artifact.
4. Cryptographic SHA-256 hash of each modified file.
5. High-level summary of survey findings, gap analysis, and RACI assignments.
6. Formal handoff gate notice for `cochem-audit` and `adversary` for asymmetric audit verification.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate mocks, stubs, dummy loops, and fake data structures.
- Do NOT use `NotImplementedError` or empty `pass` blocks as dead-end stubs.
- Do NOT use synthetic array generators (`np.zeros`, `np.ones`, `np.eye`) to fake state tensors or coordinate matrices.
- Do NOT use shortcut tag-appending (e.g., `[AUDITOR FIX REQUIRED]`); deliver complete, production-grade specifications.
- Strictly enforce dynamic Mendeleev retrieval (`from mendeleev import element`).
```
