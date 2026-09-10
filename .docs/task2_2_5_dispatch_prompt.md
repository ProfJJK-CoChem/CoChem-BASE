# Task 2.2.5 Dispatch Specification: Persist Ratified WBS Specification Artifact

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.  
**Level 2 Task:** Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.  
**Specific Task to Execute:** `2.2.5 - Persist ratified WBS specification artifact`  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)  
**Canonical Dispatch File:** [`task2_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/e878ae64-3244-44a6-8c2d-86dbb206e268/task2_2_5_dispatch_prompt.md)  
**Target Deliverable:** [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole authoritative agent responsible for systems engineering governance, scope reconciliation (PMBOK 100% Rule), Work Breakdown Structure (WBS) synthesis, and baseline artifact ratification. Assembling, formatting, verifying, and persisting the comprehensive Level 2 WBS specification for Level 1 Task 2 (*Precision Optimization Engine & Frozen Monomer Protocol*) falls strictly within the project management, software lifecycle, and requirements engineering domains.
2. **Strict Role Segregation & Separation of Duties:**  
   - Application coding is strictly partitioned to `cochem-coder`. Delegating WBS specification authoring or ratification to `cochem-coder` violates the core governance invariant: **an implementing coder must never define their own work packages, schedule boundaries, or acceptance criteria**.
   - Technical writing for user-facing documentation and manuscripts is reserved for `cochem-scribe`.
   - Physical execution and integration testing belong to `cochem-tester`.
   - Independent verification and asymmetric auditing belong strictly to `cochem-audit` and `adversary`.
   - Lifecycle orchestration is held by `0rchestrator`, which delegates the project planning and WBS artifact generation to `cochem-sdp-manager`.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` is the registered author and owner of all ratified Level 2 WBS specifications across the ecosystem, including:
   - Task 1 WBS & RACI specifications: [`task1_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_5_dispatch_prompt.md) and [`task1_3_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_3_dispatch_prompt.md)
   - Task 2 Survey, Decomposition & RACI: [`task2_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md), [`task2_2_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_dispatch_prompt.md), and [`task2_2_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_dispatch_prompt.md)
   - Task 3 WBS Breakdown: [`task3_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md)
   - Task 5 WBS Breakdown: [`task5_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md)
   - Swarm State Ledger: [`swarm_state.json`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json)

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.2.5 - PERSIST RATIFIED WBS SPECIFICATION ARTIFACT]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery), IEEE 830-1998, SWEBOK v3/v4, the CoChem Method Matrix v4, and Anti-Spoofing Protocol v4 to synthesize, format, ratify, and persist formal, zero-mock Work Breakdown Structure (WBS) artifacts.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.
- Level 2: Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.
- Specific Task to Execute:
  2.2.5 - Persist ratified WBS specification artifact.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing or persisting any WBS documents or schemas, you MUST use your filesystem tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to read and inspect the following project files to gain empirical context:

1. Method Matrix & Verification Specifications:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` (and `Method_Matrix_Hub.md`):
     * §4.4 & §QS-1: Quintuple stationary convergence criteria (`TolE 1.0e-7 Eh`, `TolMaxG 1.0e-5 a.u.`, `TolRMSG 3.0e-6 a.u.`, `TolRMSD 5.0e-5 Angstrom`, `TolMaxD 1.0e-4 Angstrom`, `MaxIter 200`).
     * §8B.3: Initial Model Hessian Discipline (strict ban on `Calc_Hess true`; mandatory `InHess XTB2` or `Lindh`; inter-stage Hessian chaining via `InHess READ`).
     * §9A, §9A.1, §9A.2, §9A.5: Frozen Monomer Protocol (FMP) Recipe R1 (r2SCAN-3c) and Recipe R2 (wB97M-V/def2-QZVPP) for non-covalent complexes (locking monomer internal coords, optimizing 6 intermolecular DOF, monomer drift limit Delta r < 1.0e-6 Angstrom).
     * §10.2–§10.3: Residual gradient extraction, force projection onto frozen internal subspace, ||g_residual||_inf evaluation, and internal strain detection threshold (1.0e-4 a.u.).
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md` (Governing Verification Matrix: VR-02 Frozen Monomer Protocol and VR-04 Quintuple Stationary Block).

2. Existing CoChem-BASE Implementation & Verification Modules:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/fragment_partitioner.py` (Monomer identification, covalent radii connectivity).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py` (Wilson internal coordinate constraint generation, ORCA %geom Constraints syntax).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py` (ORCA %geom deck generation, calculation schemas).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py` (Convergence parsing, gradient vector extraction).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py` (Execution orchestration, pipeline lifecycle).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py` (Domain exception hierarchy).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py` (Existing unit/integration tests for VR-02 and VR-04).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/anti_spoof_linter.py` (AST static anti-spoofing checker).

3. Preceding Planning, WBS & Audit Context in Scratch:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_dispatch_prompt.md` (Pipeline dependency DAG and RACI matrix specification).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_dispatch_prompt.md` (Deconstructed L3.1 through L3.5 component specifications).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md` (Survey scope and baseline module inventory).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md` & `task5_level2_wbs_breakdown.md` (Ratified structural blueprints).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Current swarm execution ledger).

You are STRICTLY FORBIDDEN from guessing file paths, fabricating dependencies, or inventing arbitrary WBS structures without tool-based inspection. Read the existing files first.

================================================================================
TECHNICAL SCOPE & DELIVERABLE REQUIREMENTS (TASK 2.2.5)
================================================================================
Synthesize and assemble the comprehensive, authoritative, production-grade Level 2 Work Breakdown Structure (WBS) artifact for Level 1 Task 2. Consolidate the technical scope, L3 microtask specifications, falsifiable acceptance criteria, Critical Path Method (CPM) dependency network, single-ownership RACI matrix, multi-environment risk register, and Method Matrix v4 physical constraints.

The persisted document MUST contain the following complete sections:

1. DOCUMENT FRONTMATTER & EXECUTIVE SCOPE:
   - Complete metadata header: Document Version 2.0.0 (Ratified Release), Project Role (`cochem-sdp-manager`), Governing Standards (PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4, Anti-Spoofing Protocol v4), Canonical File paths.
   - Formal Scope Reconciliation & Harmonization satisfying the PMBOK 100% Rule. Explicitly ground the scope in Task 2 engineering:
     * Recipe R1 (`r2SCAN-3c`) & Recipe R2 (`wB97M-V/def2-QZVPP`) Wilson internal coordinate constraint generation (VR-02).
     * Residual gradient parsing, projection onto frozen monomer subspace, $\|\mathbf{g}_{\text{residual}}\|_{\infty}$ evaluation, and internal strain detection ($\le 10^{-4}\text{ a.u.}$) (VR-02).
     * Quintuple stationary block convergence verification (`TolE 1e-7`, `TolMaxG 1e-5`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`, `MaxIter 200`) (VR-04).
     * Initial Model Hessian Discipline (`InHess XTB2` / `InHess Lindh`), absolute ban on `Calc_Hess true`, and stage-to-stage Hessian chaining via `InHess READ` (VR-02, VR-04).

2. DEPENDENCY & EXECUTION FLOWCHART (MERMAID DAG):
   - Fully formatted, syntactically valid Mermaid Directed Acyclic Graph (`flowchart TD`) covering:
     * Phase 1: Ingestion & Baseline Scope (Tasks 2.1, 2.2.1, 2.2.2).
     * Phase 2: Domain Modeling & Foundation Contracts (`exceptions.py`, Pydantic/Dataclass contracts).
     * Phase 3: Component Implementation Sprints (L3.1 Recipe R1/R2 constraints, L3.2 Residual gradient parsing, L3.3 Quintuple stationary block, L3.4 Initial model Hessian discipline).
     * Phase 4: Integration Engine & Pipeline Router (`cochem_calc_execution_router.py`).
     * Phase 5: Zero-Mock Physical Verification (`cochem-tester` with authentic non-covalent dimer fixtures like $\text{CO}_2\cdots\text{H}_2\text{O}$).
     * Phase 6: Asymmetric Adversarial Audit Gate (`cochem-audit` and `adversary` in sterile quarantine).
     * Phase 7: Council Ratification & Swarm State Ledger Synchronization.

3. GRANULAR L3 COMPONENT IMPLEMENTATION TASK MATRIX:
   - Comprehensive GitHub Flavored Markdown (GFM) table containing:
     * WBS ID (e.g., L3.1 through L3.5, plus governance, verification, and audit packages).
     * Component Task Name & Objective.
     * Single Responsible Agent (RACI Single Ownership Rule: exactly ONE agent per task).
     * Immediate Dependencies.
     * Provenance Tag (`[M]` for empirical benchmarks, `[D]` for derived mathematics, `[GOV]` for governance, `[PROC]` for procedures, `[DOC]` for documentation).
     * Target Deliverable & Destination Filepath.

4. DEEP TECHNICAL SPECIFICATION OF L3 IMPLEMENTATION TASKS:
   - Exhaustive specification for each work package detailing:
     * WBS Code, Single Accountable Agent, Provenance Tag, Predecessors.
     * Scope Boundary & Purpose.
     * Concrete Technical Activities (exact function signatures, input schemas, validation logic, mathematical thresholds).
     * Target Deliverables.
     * Binary, Falsifiable Acceptance Criteria.

5. METHOD MATRIX v4 SCIENTIFIC CONSTRAINT MAPPING:
   - Explicit mapping of Method Matrix §4.4, §8B.3, §9A, §10.2, §QS-1, and §QS-3.
   - Dynamic atomic mass resolution mandate (`from mendeleev import element`).
   - Double-precision initialization mandate (`jax.config.update("jax_enable_x64", True)`).

6. MULTI-ENVIRONMENT RISK REGISTER & MITIGATION STRATEGY:
   - Full 6-tier runtime environment risk matrix (Local-Windows, Local-Linux, Local-macOS, Codespaces, GitHub Actions CI, HPC SLURM/Lustre).
   - Analysis of platform traps (Win32 Job Objects vs POSIX `os.killpg`, path separators, CRLF vs LF, memory bounds, file locking).
   - Actionable mitigation strategies (Avoid, Escalate, Transfer, Mitigate, Accept).

7. EXECUTION VERIFICATION PROTOCOL & CHECKLIST:
   - Checkboxes for MECE validation, Single-Agent RACI, Provenance sanitation, Zero counterfeit logic, Filesystem confirmation, and Asymmetric sign-off gate (`- [ ] **Asymmetric Sign-off:** Pending independent Agent Council sign-off.`).

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL CODE / RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely emitting the WBS artifact into conversational chat or leaving results in ephemeral memory buffers.
You MUST invoke your `write_to_file` tool to persist the complete, unabridged deliverable directly to physical disk at:

1. Primary Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md`

2. Swarm State Ledger Synchronization:
   Atomically update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` using `write_to_file` (`Overwrite=true`) recording:
   ```json
   {
     "anti_spoofing_compliance": true,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.2.5: Persist ratified WBS specification artifact",
     "wbs_level": "Level 2 / Task 2 Level 2 WBS Breakdown",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "zero_mock_enforced": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md"
     ],
     "sha256_checksum": "<COMPUTED_SHA256>"
   }
   ```

================================================================================
CRITICAL DIRECTIVE 3: RETURN FINAL TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk writes and ledger updates, you MUST return a final text report starting with `[SDPM REPORT]` and concluding with `[VERIFICATION & HANDOFF SUMMARY]`. The report must explicitly detail:
1. Executive declaration of task completion.
2. Exact absolute and relative file paths modified or created on disk so the auditor can immediately locate and verify them.
3. Physical byte count and line count of each generated artifact.
4. Cryptographic SHA-256 hash of each modified file.
5. Summary of the ratified WBS hierarchy, total L3 work packages decomposed, and RACI ownership distribution across the council roles.
6. Explicit confirmation that Anti-Spoofing Protocol v4, Zero-Mock mandates, and the Mendeleev dynamic mass mandate are 100% satisfied with zero stubs or placeholders.
7. Formal handoff gate notice designating `cochem-audit` and `adversary` to initiate the asymmetric audit.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate all mocks, stubs, dummy loops, and synthetic data placeholders.
- Do NOT use `NotImplementedError` or empty `pass` blocks.
- Do NOT generate synthetic coordinate arrays or matrices (`np.zeros`, `np.ones`, `np.eye`).
- Do NOT use shortcut tag-appending (`[AUDITOR FIX REQUIRED]`).
- Ensure all physical constants and atomic properties strictly retrieve dynamically via `mendeleev`.
```
