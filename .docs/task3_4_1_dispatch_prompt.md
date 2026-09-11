# Task 3.4.1 Dispatch Specification: Break Down L2 Task into Granular L3 Component-Level Implementation Tasks

**Document Identifier:** `COCHEM-DISPATCH-TASK3-4-1-SDPM-20260911` [M]  
**Audit Ratification ID:** `AUDIT-DISPATCH-PROMPT-3.4.1-20260910` (Official Verdict: PASS) [M]  
**Parent Task:** Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper ($\Delta \langle S^2 \rangle < 10\%$, singlet guard $|\langle S^2 \rangle| < 0.05$ a.u.), and Product B/M ontological disambiguation [M].  
**Level 2 Task:** Authored persistent WBS tracking artifact at `Task_List_Task3_WBS.md` with PMBOK-aligned risk register [M].  
**Specific Task to Execute:** `3.4.1 - Break down L2 task into granular L3 component-level implementation tasks` [M].  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager) [M].  
**Canonical Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_4_1_dispatch_prompt.md` [M].  
**Target Persistence Deliverables:**  
- Primary Deliverable: `C:/Users/ansac/.gemini/antigravity-cli/scratch/Task_List_Task3_WBS.md` [M]  
- Ecosystem Mirror: `D:/__CoChem/.docs/Task_List_Task3_WBS.md` [M]  
- Repository Mirror: `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task_List_Task3_WBS.md` [M]  
- Dropzone Mirror: `D:/__CoChem/__agentic/dropzones/inbox_srs/Task_List_Task3_WBS.md` [M]  
- Swarm State Ledger: `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (and `D:/__CoChem/swarm_state.json`) [M]  

---

## 1. Designated Execution Agent

**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Swarm Charter and Agent Council taxonomy, `cochem-sdp-manager` is the sole authoritative persona responsible for project planning, systems requirements decomposition, Work Breakdown Structure (WBS) baselining, scope management, and RACI governance. Breaking down the parent Level 2 task into granular, component-level Level 3 implementation tasks governed by the **PMBOK 100% Rule** and **MECE** principles is a core project management competency.
2. **Strict Separation of Duties (Zero-Trust Protocol v4):**  
   - Downstream implementers (`cochem-coder`, `ui`, `artist`) are strictly barred by Council governance from defining their own scopes, decomposing their own work packages, or accepting their own deliverables.
   - Independent verification agents (`cochem-audit`, `adversary`) evaluate compliance asymmetrically; allowing an auditor to author the work breakdown creates an immediate conflict of interest.
   - Technical writers (`cochem-scribe`) typeset manuals and documentation, but lack systems engineering authority over work package atomization and risk registers.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` has authored all preceding WBS baselines and decompositions across Tasks 1, 2, 3, and 5:
   - Task 1: `task1_level2_wbs_breakdown.md`
   - Task 2: `task2_level2_wbs_breakdown.md`
   - Task 3: `task3_level2_wbs_breakdown.md`
   - Task 5: `task5_level2_wbs_breakdown.md`
   Delegating Task 3.4.1 to `cochem-sdp-manager` ensures single-point RACI accountability, structural continuity, and compliance with the PMBOK 100% Rule.

---

## 2. Authoritative Operational Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 3.4.1 - BREAK DOWN L2 TASK INTO GRANULAR L3 COMPONENT-LEVEL IMPLEMENTATION TASKS]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery & Scope Management Domain), SWEBOK v3/v4 (Software Requirements Engineering, Software Design, Software Quality), and CoChem Method Matrix v4 to decompose Level 1 Task 3 into an authoritative, granular Level 3 Work Breakdown Structure (WBS) tracking artifact at `Task_List_Task3_WBS.md` with PMBOK-aligned risk register and single-accountability RACI mapping.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta <S^2> < 10%, singlet guard |<S^2>| < 0.05 a.u.), and Product B/M ontological disambiguation.
- Level 2: Authored persistent WBS tracking artifact at Task_List_Task3_WBS.md with PMBOK-aligned risk register.
- Specific Task to Execute:
  3.4.1 - Break down L2 task into granular L3 component-level implementation tasks.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any decomposition or writing any artifact, you MUST invoke your file inspection tools (view_file, grep_search, list_dir, find_by_name) to thoroughly inspect existing project files on the local filesystem:

1. Ingest Existing Task 3 WBS & Baseline Documents:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md` (Authoritative Level 2 baseline for Task 3 containing 5 Canonical Technical Tracks and 18 L3 microtasks L3-T3-01 to L3-T3-18).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task3_4_1_prompt_audit_report.md` (Official Audit Ratification Report, Doc ID: AUDIT-DISPATCH-PROMPT-3.4.1-20260910).
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md` (Governing SRS specification for VR-03 and VR-05).

2. Ingest Governing Method Matrix & Verification Requirements (VR-03 & VR-05):
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` (and `Method_Matrix_Hub.md`):
     * §2.5, §3.3, §4.4 (VR-03): Dynamic quadrature lifecycle (DEFGRID1 -> DEFGRID2 -> DEFGRID3), coupled grid-dependent SCF convergence gates (NormalSCF -> TightSCF -> VeryTightSCF), and rejection of coarse grids for numerical frequency, harmonic Hessian, and VPT2 calculations.
     * §2.8 (VR-05): Non-local functional dispersion vs empirical dispersion (VV10 vs D3/D4); fail-closed RedundantDispersionError on wB97M-V/B97M-V with empirical dispersion; mandatory 3-body Axilrod-Teller-Muto (ATM) dispersion for N_monomers >= 3.
     * §2.9 (VR-05): Singularity-protected spin gatekeeper: relative contamination percentage Delta <S^2> < 10% for S > 0; absolute singlet guard |<S^2>| < 0.05 a.u. for S = 0; fail-closed routing to Tier T9 (RO-DFT / CASSCF / NEVPT2).
     * §1.2, §2.2, §2.10: Ontological disambiguation of Product B (solid-state periodic materials, PAW pseudopotentials, Gamma-point) vs Provenance Tag [M] (methodological invariant) vs Product M (experimental measured benchmarks from CCCBDB / CP-FTMW).
     * Dynamic Mendeleev Mandate: Dynamic atomic/isotopic mass lookups via `from mendeleev import element` (strictly banning hardcoded mass tables).

3. Ingest Target Modules & Test Suites:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/mm/quadrature_manager.py` (if present or baseline)
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/analysis/electronic_sanitizer.py` (if present or baseline)
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py`

4. Ingest Active Swarm State Ledger:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Read current execution states, active dependencies, and completed artifacts).

You are STRICTLY FORBIDDEN from guessing file locations, hallucinating module signatures, or formulating task breakdowns without reading these physical files first.

================================================================================
TECHNICAL SCOPE & DECOMPOSITION SPECIFICATION
================================================================================
You must author a complete, publication-grade WBS tracking document:
`C:/Users/ansac/.gemini/antigravity-cli/scratch/Task_List_Task3_WBS.md`

Your artifact must strictly satisfy:

1. PMBOK 100% Rule & MECE Guarantee:
   - Decompose 100% of the scope of Level 1 Task 3 across the 5 Canonical Technical Tracks and Level 2 Persistence Meta-WBS (WBS 3.1–3.5) with zero orphan activities and zero extraneous scope.
   - Work packages must be mutually exclusive and collectively exhaustive.

2. Comprehensive L3 Microtask Specification:
   For every decomposed Level 3 implementation microtask (`L3-T3-01` through `L3-T3-18`, as well as subtasks under WBS 3.1 to 3.5), specify:
   - Unique WBS Task ID (e.g., `L3-T3-01`, `WBS-3.4.1`, etc.).
   - Actionable title and clear scope statement.
   - Interactive Markdown checkbox (`- [ ]`).
   - Single Responsible Agent (`R`) and Single Accountable Agent (`A`) under RACI rules. Strict single-accountability invariant: $A = 1$. Shared ownership tokens (e.g., `cochem-coder / cochem-tester`) are strictly forbidden.
   - Explicit input data contracts (source files, mathematical models, SRS sections).
   - Concrete output deliverables (exact file paths, classes, functions, test suites).
   - Quantitative acceptance criteria and verification gates (e.g. exit code 0, tolerance thresholds).
   - Method Matrix scientific provenance tags (`[M]`, `[D]`, `[E]`, `[GOV]`, `[DOC]`, `[PROC]`).

3. PMBOK 7th Edition Risk Register:
   Integrate a complete multi-environment risk register structured with:
   - Standard 5-part risk statements: *"Because of [Root Cause], [Risk Event] might occur, which would lead to [Qualitative Effect] and [Quantitative Consequence]."*
   - Probability ($P \in [0.1, 0.9]$) and Impact ($I \in [1, 5]$) ratings with Exposure Score ($P \times I$).
   - Standard PMBOK response strategy: Exactly one of **Avoid**, **Escalate**, **Transfer**, **Mitigate**, or **Accept**.
   - Quantifiable fallback triggers (e.g. non-convergence triggers, memory threshold triggers).
   - Single risk owner for every risk item.

4. Anti-Spoofing Directive v4 & Zero-Mock Invariants:
   - Zero test doubles, simulation stubs, or mock frameworks.
   - Zero placeholder tokens (`TODO: implement`, `NotImplementedError`, or empty templates).
   - Dynamic Mendeleev atomic mass retrieval (`from mendeleev import element`).
   - Real molecular coordinates ($\text{CO}_2\cdots\text{H}_2\text{O}$ from CCCBDB / NIST); zero synthetic arrays (`np.zeros`, `np.ones`).

================================================================================
CRITICAL DIRECTIVE 2: TOOL-BASED PHYSICAL DISK PERSISTENCE (NO CHAT-ONLY OUTPUT)
================================================================================
You are STRICTLY FORBIDDEN from outputting your deliverables solely into conversational chat context.
You MUST invoke the `write_to_file` tool to physically write the complete deliverable directly to disk:

1. Primary Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/Task_List_Task3_WBS.md`

2. Multi-Mirror Synchronization:
   Also write/mirror the artifact to:
   - `D:/__CoChem/.docs/Task_List_Task3_WBS.md`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task_List_Task3_WBS.md`
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/Task_List_Task3_WBS.md`

3. Swarm State Ledger Update:
   Update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (and `D:/__CoChem/swarm_state.json`) recording:
   - `agent_name`: "cochem-sdp-manager"
   - `status`: "COMPLETED"
   - `task`: "Task 3.4.1: Break down L2 task into granular L3 component-level implementation tasks"
   - `wbs_level`: "Level 3 / Task 3.4.1 Component-Level Breakdown"
   - `artifacts_produced`: Array containing the full paths to `Task_List_Task3_WBS.md` across mirrors
   - `anti_spoofing_compliance`: true
   - `timestamp`: Current ISO 8601 timestamp

================================================================================
CRITICAL DIRECTIVE 3: MANDATORY FORMAL FINAL REPORT
================================================================================
Conclude your execution with a formal `[SDPM REPORT]` containing:
1. The exact absolute and relative file paths modified or created on disk so the downstream auditor (`cochem-audit` / `adversary`) can immediately verify them.
2. A structured summary of the L3 tasks added, their assigned execution agents, and updated risk register items.
3. The single safest next action for the swarm.
```
