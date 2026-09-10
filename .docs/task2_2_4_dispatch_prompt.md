# Task 2.2.4 Dispatch Specification: Synthesize Pipeline Dependency Graph and RACI Matrix Adhering to Anti-Spoofing Protocol v4

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.  
**Level 2 Task:** Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.  
**Specific Task to Execute:** `2.2.4 - Synthesize pipeline dependency graph and RACI matrix adhering to Anti-Spoofing Protocol v4`  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)  
**Canonical Dispatch File:** [`task2_2_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_dispatch_prompt.md)  
**Target Deliverable:** [`task2_2_4_pipeline_dependency_graph_and_raci.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_pipeline_dependency_graph_and_raci.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole authoritative agent responsible for systems engineering governance, schedule network analysis, work package sequencing, and organizational responsibility matrices (RACI). Synthesizing a pipeline dependency graph (Activity Network Diagram / CPM Schedule Network) and a formal single-ownership RACI matrix falls squarely within PMBOK 7th Edition Project Delivery Principles ("Systems View for Project Delivery" and "Planning Performance Domain") and SWEBOK v3/v4 ("Software Engineering Management" and "Software Architecture").
2. **Strict Role Segregation & Separation of Duties:**  
   - Application coding is strictly partitioned to `cochem-coder`. Delegating schedule network design and RACI allocation to `cochem-coder` violates the core governance invariant: **an implementing coder must never assign responsibilities to peers, define verification boundaries, or establish governance gates**.
   - Technical writing for external documentation is isolated to `cochem-scribe`.
   - Physical execution and integration testing are reserved for `cochem-tester`.
   - Adversarial verification and compliance audits belong exclusively to `cochem-audit` and `adversary`.
   - Master lifecycle routing belongs to `0rchestrator`. Delegating the actual synthesis of the PMBOK-compliant dependency graph and RACI matrix to `cochem-sdp-manager` preserves architectural separation of duties.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` authored all preceding WBS decompositions, scoping frameworks, and RACI governance matrices across Tasks 1 & 2:
   - Task 1 WBS & RACI baselines: [`task1_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_5_dispatch_prompt.md), [`task1_3_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_3_dispatch_prompt.md).
   - Task 2 Level 2 WBS: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md).
   - Task 2.1.3 Decomposition: [`task2_1_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_1_3_dispatch_prompt.md).
   - Task 2.2.1 Survey: [`task2_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md).
   - Task 2.2.2 L3 Decomposition: [`task2_2_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_dispatch_prompt.md).
   Assigning Task 2.2.4 to `cochem-sdp-manager` ensures single-point RACI accountability and flawless continuity.

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.2.4 - SYNTHESIZE PIPELINE DEPENDENCY GRAPH AND RACI MATRIX ADHERING TO ANTI-SPOOFING PROTOCOL V4]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery), IEEE 830-1998, SWEBOK v3/v4, the CoChem Method Matrix v4, and the Anti-Spoofing Protocol v4 to construct formal pipeline dependency graphs, Critical Path Method (CPM) networks, and single-ownership RACI responsibility assignment matrices.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.
- Level 2: Define technical scope, agent assignments, inputs, deliverables, and acceptance criteria for Recipe R1/R2 constraints, residual gradient parsing, quintuple convergence, and Hessian chaining.
- Specific Task to Execute:
  2.2.4 - Synthesize pipeline dependency graph and RACI matrix adhering to Anti-Spoofing Protocol v4.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any dependency graphs, Mermaid flowcharts, or RACI allocations, you MUST use your filesystem tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to read and inspect the following project files to gain empirical context:

1. Method Matrix & Verification Specifications:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` (and `Method_Matrix/Method_Matrix_Hub.md`):
     * §4.4 & §QS-1: Quintuple stationary convergence criteria (TolE 1.0e-7 Eh, TolMaxG 1.0e-5 a.u., TolRMSG 3.0e-6 a.u., TolRMSD 5.0e-5 Angstrom, TolMaxD 1.0e-4 Angstrom, MaxIter 200).
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
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_dispatch_prompt.md` (Deconstructed L3.1 through L3.5 component specifications).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md` (Survey scope and baseline module inventory).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md` (Governing Level 2 WBS hierarchy).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Current swarm ledger).

You are STRICTLY FORBIDDEN from guessing file paths, fabricating dependencies, or inventing arbitrary RACI allocations without tool-based inspection. Read the files first.

================================================================================
TECHNICAL SCOPE & DELIVERABLE REQUIREMENTS (TASK 2.2.4)
================================================================================
Synthesize a comprehensive, production-grade Pipeline Dependency Graph and RACI Matrix that strictly adheres to the Anti-Spoofing Protocol v4. The deliverable must incorporate the following core components:

1. EXECUTIVE SUMMARY & GOVERNANCE FRAMEWORK:
   - Formally anchor the specification in PMBOK 7th Edition (Systems View for Project Delivery), SWEBOK v3/v4, IEEE 830-1998, CoChem Method Matrix v4, and Anti-Spoofing Protocol v4.
   - Establish the governance scope across Level 1 Task 2 and Level 2 packages, covering all component microtasks (L3.1 through L3.5), verification gates, and adversarial audit milestones.

2. COMPREHENSIVE PIPELINE DEPENDENCY GRAPH (MERMAID DAG):
   - Formulate a detailed Mermaid Directed Acyclic Graph (`flowchart TD` or `graph TD`) visualizing the end-to-end execution flow.
   - Partition into clear execution phases:
     * Phase 1: Ingestion & Baseline Scope (Tasks 2.1, 2.2.1, 2.2.2).
     * Phase 2: Domain Modeling & Foundation Contracts (Exceptions, Pydantic schemas, Dataclass models).
     * Phase 3: Component Implementation Sprints (L3.1 Recipe R1/R2 constraints, L3.2 Residual gradient parsing, L3.3 Quintuple stationary block, L3.4 Initial model Hessian discipline).
     * Phase 4: Integration Engine & Pipeline Router (L3.5 End-to-end orchestration in `cochem_calc_execution_router.py`).
     * Phase 5: Zero-Mock Physical Verification (`cochem-tester` executing against authentic non-covalent dimers).
     * Phase 6: Asymmetric Adversarial Audit Gate (`cochem-audit` & `adversary` zero-trust quarantine verification).
     * Phase 7: Council Ratification & Swarm State Ledger Synchronization.
   - Include clear data artifact handoffs and interface contracts between nodes.
   - Visually distinguish the Critical Path (CPM) using Mermaid classes/styling.

3. SCHEDULE NETWORK & PREDECESSOR/SUCCESSOR ANALYSIS (CPM TABLE):
   - Provide a formal CPM schedule table detailing:
     * Work Package ID (e.g., L3.1, L3.2, L3.3, L3.4, L3.5, V-GATE-1, AUDIT-GATE-1).
     * Work Package Name & Objective.
     * Immediate Predecessors.
     * Immediate Successors.
     * Execution Concurrency Eligibility (can it run in parallel?).
     * Critical Path Inclusion (Yes / No).
     * Handoff Interface / Produced Artifacts.

4. STRICT SINGLE-OWNERSHIP RACI MATRIX:
   - Construct an exhaustive RACI Matrix covering all 9 CoChem Agent Council roles:
     `cochem-sdp-manager`, `0rchestrator`, `cochem-coder`, `cochem-tester`, `cochem-audit`, `adversary`, `cochem-improve`, `cochem-scribe`, `researcher`.
   - Strictly enforce the **PMBOK Single-Point Accountability Rule**:
     * Exactly ONE Responsible ('R') agent per row. Dual-R ownership is strictly forbidden.
     * Exactly ONE Accountable ('A') agent per row (holding ultimate veto/governance power).
     * Consulted ('C') agents: Subject matter specialists providing technical/scientific inputs.
     * Informed ('I') agents: Downstream stakeholders kept updated on state changes.
   - Include rows for all L3 technical components (L3.1 to L3.5), preflight checks, CI sweeps, physical test executions, and adversarial audit milestones.

5. ANTI-SPOOFING PROTOCOL V4 & ZERO-MOCK GOVERNANCE INTEGRATION:
   - Explicitly document how the RACI allocations and dependency flow enforce the 14 directives of Anti-Spoofing Protocol v4:
     * Directive 1 (Asymmetric Verification): `cochem-coder` is strictly barred from verifying its own code. Verification must be executed by `cochem-tester` and audited by `cochem-audit` in quarantine (`/tmp/cochem_exec_<uuid>/`).
     * Directive 3 & 8 (Zero-Mock / Zero-Stub / Raw Logging): Ban on `NotImplementedError`, empty `pass`, `np.zeros`, `np.ones`, `np.eye`, or synthetic loop arrays. Mandate authentic physical fixtures ($\text{CO}_2\cdots\text{H}_2\text{O}$ dimer from CCCBDB/NIST).
     * Directive 7 (No Evasion Tactics): AST inspection forbidding string concatenation or monkeypatching to circumvent `Calc_Hess true` bans.
     * Directive 11 (Direct Modification Mandate): Ban on tag-appending shortcuts (`[AUDITOR FIX REQUIRED]`).
     * Mendeleev Library Mandate: All atomic/isotopic properties must be dynamically retrieved via `from mendeleev import element`.
     * Fail-Closed Error Handling: Immediate hard abort (`[HARD_ABORT: PHYSICS WALL]` or `[HARD_ABORT: ARCHITECTURE WALL]`) upon unresolvable physical deadlocks or 3 failed meta-pivots.

6. FALSIFIABLE ACCEPTANCE CRITERIA CHECKLIST:
   - Comprehensive checklist of binary, verifiable acceptance criteria for the dependency graph, RACI matrix, and downstream execution gates.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL CODE / RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely emitting the dependency graph and RACI matrix to conversational chat or leaving results in ephemeral memory buffers.
You MUST invoke your `write_to_file` tool to persist the complete, unabridged deliverable directly to physical disk at:

1. Primary Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_pipeline_dependency_graph_and_raci.md`

2. Swarm State Ledger Synchronization:
   Atomically update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` using `write_to_file` (`Overwrite=true`) recording:
   ```json
   {
     "anti_spoofing_compliance": true,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.2.4: Synthesize pipeline dependency graph and RACI matrix adhering to Anti-Spoofing Protocol v4",
     "wbs_level": "Level 2 / Task 2.2 Technical Scope Definition",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "zero_mock_enforced": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_pipeline_dependency_graph_and_raci.md"
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
5. Summary of the synthesized dependency graph, Critical Path (CPM) duration/milestones, and RACI ownership distribution across the 9 council roles.
6. Explicit confirmation that Anti-Spoofing Protocol v4, Zero-Mock mandates, and the Mendeleev dynamic mass mandate are 100% satisfied.
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
