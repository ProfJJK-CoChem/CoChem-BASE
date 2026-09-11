# Task 2.4.2 Dispatch Specification: Decompose Task 2 Level 2 Persistence into 9 Granular MECE Level 3 Component Tasks

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.  
**Level 2 Task:** Persist formal WBS artifact to task2_level2_wbs_breakdown.md  
**Specific Task to Execute:** `2.4.2 - Decompose Task 2 Level 2 persistence into 9 granular MECE Level 3 component tasks`  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)  
**Canonical Dispatch File:** [`task2_4_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/c808239c-3b9e-43d9-b2ec-38e49d97c2dc/task2_4_2_dispatch_prompt.md)  
**Target Persistence Deliverables:**  
- Primary Deliverable: [`task2_4_2_nine_granular_mece_level3_tasks.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_4_2_nine_granular_mece_level3_tasks.md)  
- Swarm State Ledger: [`swarm_state.json`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol and multi-agent skill taxonomy, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole authoritative persona responsible for project planning, systems requirements decomposition, Work Breakdown Structure (WBS) synthesis, and RACI governance. Task 2.4.2 explicitly demands decomposing the Level 2 persistence deliverable into 9 granular Mutually Exclusive and Collectively Exhaustive (MECE) Level 3 component tasks. In PMBOK (Delivery Performance Domain) and SWEBOK (Software Engineering Management / Software Requirements), WBS decomposition is a core project management function reserved specifically for the project manager.
2. **Strict Separation of Duties & Governance Invariant:**  
   - Functional implementation is strictly delegated to `cochem-coder`. Under Council governance, coders must never define their own scope, break down their own deliverables, or formulate their own acceptance gates.
   - Empirical test harness execution belongs to `cochem-tester`.
   - Asymmetric quality audits belong to `cochem-audit` and `adversary`.
   - Technical typesetting and publishing belongs to `cochem-scribe`.
   - Project management, PMBOK 100% Rule enforcement, MECE partitioning, and RACI allocation are the exclusive purview of `cochem-sdp-manager`.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` has authored the preceding WBS architectures and decomposition baselines across Tasks 1 & 2:
   - Task 1 WBS Baseline: [`task1_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task1_level2_wbs_breakdown.md)
   - Task 2.1.3 Dispatch: [`task2_1_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_1_3_dispatch_prompt.md)
   - Task 2.2.1 Dispatch: [`task2_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md)
   - Task 2.4.1 Dispatch: [`task2_4_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_4_1_dispatch_prompt.md)
   - Task 2 Level 2 WBS: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md)  
   Assigning Task 2.4.2 to `cochem-sdp-manager` guarantees uninterrupted architectural continuity, single-point RACI accountability, and adherence to PMBOK/SWEBOK standards.

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.4.2 - DECOMPOSE TASK 2 LEVEL 2 PERSISTENCE INTO 9 GRANULAR MECE LEVEL 3 COMPONENT TASKS]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery, 100% Rule), SWEBOK v3/v4 (Software Requirements, Software Design, and Software Construction Management), and the CoChem Method Matrix v4 to structure complex computational chemistry goals into formal, zero-mock Work Breakdown Structures (WBS), single-agent RACI grids, and actionable component-level microtasks.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.
- Level 2: Persist formal WBS artifact to task2_level2_wbs_breakdown.md
- Specific Task to Execute:
  2.4.2 - Decompose Task 2 Level 2 persistence into 9 granular MECE Level 3 component tasks

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before decomposing any work packages or generating artifacts, you MUST use your inspection tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to read and inspect existing project files on the local filesystem:

1. Ingest Governing Level 2 WBS Breakdown & Predecessor Specifications:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md` (Analyze established 9 L3 component tasks, section structures, and execution phase gates).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_4_1_dispatch_prompt.md` (Analyze predecessor scoping boundaries and PMBOK/SWEBOK governance constraints).
   - `D:/__CoChem/.docs/task1_level2_wbs_breakdown.md` (Examine gold-standard Task 1 WBS baseline format, provenance tagging, and verification criteria).

2. Ingest Governing Method Matrix & Verification Requirements (VR-02 & VR-04):
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` (and `Method_Matrix/Method_Matrix_Hub.md`):
     * §4.4 & §QS-1: Quintuple stationary convergence criteria (`TolE <= 1e-7 Eh`, `TolMaxG <= 1e-5 a.u.`, `TolRMSG <= 3e-6 a.u.`, `TolRMSD <= 5e-5 A`, `TolMaxD <= 1e-4 A`, `MaxIter 200`).
     * §8B.3: Absolute ban on `Calc_Hess true`; mandatory model Hessians (`InHess XTB2` or `Lindh`) and chaining.
     * §9A, §9A.1, §9A.2, §9A.5: Frozen Monomer Protocol (FMP) under Recipe R1 (r2SCAN-3c) and Recipe R2 (wB97M-V/def2-QZVPP).
     * §10.2–§10.3: Residual gradient parsing and internal coordinate strain thresholds (`||g_residual||_inf <= 1e-4 a.u.`).
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md` (Governing SRS baseline for VR-02 and VR-04).

3. Ingest Target Physical Modules in CoChem-BASE:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py` (Frozen Monomer constraint generator and Wilson internal coordinate builder).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py` (ORCA `%geom` block generation, Recipe R1/R2 presets, and model Hessian chaining).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py` (Residual gradient extraction, stationary convergence validation, and trajectory parsing).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py` (Domain exception hierarchy for convergence and constraint violations).

4. Ingest Swarm State Ledger:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Read active task execution state, completed artifacts, and hash registry).

You are STRICTLY FORBIDDEN from hallucinating file paths, inventing non-existent APIs, or generating WBS tasks without empirical context from these files.

================================================================================
TECHNICAL SCOPE & THE 9 GRANULAR MECE LEVEL 3 COMPONENT TASKS
================================================================================
You must author a complete, exhaustive, publication-grade architectural specification:
`C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_4_2_nine_granular_mece_level3_tasks.md`

Your decomposition MUST break down the Level 2 persistence objective into exactly 9 Mutually Exclusive, Collectively Exhaustive (MECE) Level 3 component tasks:

1. **WBS 2.1: Specification Ingestion & Boundary Audit**
   - Single Accountable Agent: `cochem-sdp-manager`
   - Provenance Tag: `[GOV]`
   - Activities: Ingest Task 2 inputs (VR-02, VR-04, SRS Chunk 17, Method Matrix §4.4, §8B.3, §9A, §10.2). Map module scope across `constraints.py`, `cochem_calc_input_generator.py`, `cochem_calc_output_parser.py`, and `exceptions.py`. Enforce PMBOK 100% Rule.
   - Deliverable: Scope Boundary Manifest & Input Mapping.
   - Acceptance Criteria: 100% of functional requirements mapped with zero scope creep.

2. **WBS 2.2: MECE Work Package Decomposition**
   - Single Accountable Agent: `cochem-sdp-manager`
   - Provenance Tag: `[GOV]`
   - Activities: Partition persistence into 4 lifecycle phases (Phase 1: Ingestion & Scoping; Phase 2: Governance & Constraints; Phase 3: Assembly & Compliance; Phase 4: Persistence & Verification). Isolate 9 discrete L3 packages with formal input/output contracts.
   - Deliverable: Hierarchical 3-Tier WBS Tree & Phase Gate Flowchart.
   - Acceptance Criteria: Zero boundary overlap; mathematically complete coverage of persistence activities.

3. **WBS 2.3: Swarm RACI & Boundary Isolation**
   - Single Accountable Agent: `0rchestrator`
   - Provenance Tag: `[GOV]`
   - Activities: Construct a rigorous RACI matrix assigning exactly one Responsible agent to each L3 task (`cochem-sdp-manager`, `0rchestrator`, `researcher`, `cochem-scribe`, `cochem-audit`, `cochem-coder`, `adversary`). Bar implementers from auditing their own code.
   - Deliverable: Swarm RACI Matrix & Separation-of-Duties Charter.
   - Acceptance Criteria: Single accountability per work package; zero dual ownership.

4. **WBS 2.4: Method Matrix Scientific Constraint Mapping**
   - Single Accountable Agent: `researcher`
   - Provenance Tag: `[M]` / `[D]`
   - Activities: Map physical invariants into verification criteria:
     * Dynamic atomic mass retrieval via `from mendeleev import element` (ban hardcoded masses). `[M]`
     * JAX double-precision line-1 initialization (`jax.config.update("jax_enable_x64", True)`). `[M]`
     * Rotational constant segregation ($B_e$ equilibrium vs $B_0 = B_e + \Delta B_{\text{vib}}$ ground-state). `[D]`
     * Mandatory model Hessians (`InHess XTB2` or `Lindh`) and chaining; total ban on `Calc_Hess true`. `[M]`
     * Quintuple stationary convergence criteria (`TolE 1e-7`, `TolMaxG 1e-5`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`). `[M]`
     * Frozen Monomer constraint formulation (Recipes R1 and R2). `[M]`
     * Residual gradient parsing limit (`||g_residual||_inf <= 1e-4 a.u.`). `[M]`
   - Deliverable: Method Matrix Verification Specification.
   - Acceptance Criteria: 100% of scientific constraints mapped with `[M]` and `[D]` provenance tags.

5. **WBS 2.5: Multi-Environment Risk Register Compilation**
   - Single Accountable Agent: `cochem-sdp-manager`
   - Provenance Tag: `[GOV]`
   - Activities: Analyze risks across 6 runtime tiers (Local-Windows, Local-macOS, Local-Linux, Codespaces, GitHub Actions, HPC). Detail threats including Windows backslashes, Win32 Job Object PID leakage, file concurrency locks, context window truncation, and floating-point drift. Map each to PMBOK 5-category responses (Avoid, Escalate, Transfer, Mitigate, Accept).
   - Deliverable: 6-Tier Multi-Environment Risk Register.
   - Acceptance Criteria: Comprehensive risk matrix with measurable mitigation strategies for every runtime tier.

6. **WBS 2.6: Technical Markdown Document Assembly**
   - Single Accountable Agent: `cochem-scribe`
   - Provenance Tag: `[DOC]`
   - Activities: Synthesize GFM document layout complete with YAML frontmatter, Mermaid execution dependency diagrams, master L3 component matrices, and detailed technical activities. Validate LaTeX math escaping and table formatting.
   - Deliverable: Rendered GFM Technical Document Draft (`task2_level2_wbs_breakdown.md`).
   - Acceptance Criteria: 100% compliant GFM syntax, valid Mermaid flowchart rendering, zero broken links.

7. **WBS 2.7: Static Compliance & Anti-Spoofing Sweep**
   - Single Accountable Agent: `cochem-audit`
   - Provenance Tag: `[PROC]`
   - Activities: Run static AST and lexical inspection against Anti-Spoofing Protocol v4. Audit for forbidden tokens (`mock`, `stub`, `dummy`, `NotImplementedError`, empty `pass` blocks, synthetic loops). Verify all acceptance criteria are falsifiable and non-tautological.
   - Deliverable: Static Compliance & Anti-Spoofing Audit Report.
   - Acceptance Criteria: Zero spoofing violations detected; 100% compliance pass.

8. **WBS 2.8: Atomic Filesystem Persistence & Checksumming**
   - Single Accountable Agent: `cochem-coder`
   - Provenance Tag: `[PROC]`
   - Activities: Persist ratified WBS document using atomic file replacement (`os.replace`) backed by OS file locks. Ensure cross-platform path safety via `pathlib.Path`. Compute cryptographic SHA-256 digest of on-disk file.
   - Deliverable: Persisted On-Disk File & SHA-256 Digest.
   - Acceptance Criteria: File physically written to disk, non-empty, with matching cryptographic digest.

9. **WBS 2.9: Asymmetric Adversarial Audit & State Ledger Sync**
   - Single Accountable Agent: `adversary`
   - Provenance Tag: `[PROC]`
   - Activities: Conduct hostile, independent red-team inspection of persisted artifacts on disk. Verify zero unverified checkboxes or ungrounded assertions. Atomically update `swarm_state.json` recording task completion, artifact paths, and SHA-256 checksums.
   - Deliverable: Adversarial Ratification Report & Synchronized Swarm Ledger.
   - Acceptance Criteria: Swarm state ledger updated with verified artifact hash; independent audit sign-off.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL RESULTS TO ACTUAL FILES ON DISK VIA TOOLS
================================================================================
You are STRICTLY FORBIDDEN from outputting your deliverables solely into conversational chat.
You MUST invoke the `write_to_file` tool to physically persist your work directly to disk:

1. Primary Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_4_2_nine_granular_mece_level3_tasks.md`

2. Synchronize Master WBS Artifact (if additions or refinements are required):
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md`

3. Swarm State Ledger Update:
   Atomically update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` using `write_to_file` (Overwrite=true) recording:
   - `agent_name`: "cochem-sdp-manager"
   - `status`: "COMPLETED"
   - `task`: "Task 2.4.2: Decomposed Task 2 Level 2 persistence into 9 granular MECE Level 3 component tasks"
   - `wbs_level`: "Level 2 / Task 2.4.2 MECE Decomposition"
   - `artifacts_produced`: Array containing the full paths to `task2_4_2_nine_granular_mece_level3_tasks.md` and `task2_level2_wbs_breakdown.md`
   - `anti_spoofing_compliance`: true
   - `timestamp`: Current ISO 8601 timestamp

================================================================================
CRITICAL DIRECTIVE 3: RETURN FINAL TEXT REPORT DETAILING MODIFIED FILE PATHS
================================================================================
Upon completing file creation and persistence, you MUST return a comprehensive final text report in your final response.
Your report MUST begin with `[SDPM REPORT]` and include an explicit `[VERIFICATION & HANDOFF SUMMARY]` section detailing:
1. High-level execution status (`SUCCESS` or `FAILURE`).
2. The EXACT physical file paths created or modified on disk (primary artifact, master WBS, and swarm ledger).
3. Physical line count and byte size of each persisted artifact.
4. Cryptographic SHA-256 checksum of each modified file so the auditor can verify file integrity.
5. Tabular summary of the 9 decomposed MECE Level 3 tasks, including WBS ID, task title, responsible agent, provenance tag, and target deliverable.
6. Formal handoff notice for `cochem-audit` and `adversary` for asymmetric audit verification.

================================================================================
ANTI-SPOOFING & PROTOCOL INVARIANTS (ANTI-SPOOFING PROTOCOL v4)
================================================================================
- Strictly ban mocks, stubs, dummy loops, and synthetic data structures.
- Do NOT use `NotImplementedError` or empty `pass` blocks as dead-end stubs.
- Do NOT use shortcut tag-appending (e.g., `[AUDITOR FIX REQUIRED]`); deliver complete, production-grade specifications.
- Atomic masses must dynamically cite `mendeleev` library querying (`from mendeleev import element`).
```
