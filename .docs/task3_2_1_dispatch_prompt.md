# Task 3.2.1 Dispatch Specification: Decompose L2 Task for VR-03 and VR-05 into Granular Component-Level L3 Implementation Tasks

**Parent Task:** Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]  
**Level 2 Task:** Formalized acceptance criteria, numerical invariants, and provenance tags ([M], [D], [E]) for VR-03 and VR-05. [GOV]  
**Specific Task to Execute:** `3.2.1 - Decomposed L2 task for VR-03 and VR-05 into granular, component-level L3 implementation tasks` [GOV] / [DOC]  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK Architect) [M]  
**Primary Scratch Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_1_dispatch_prompt.md` [GOV]  
**Conversation Artifact Mirror:** `C:/Users/ansac/.gemini/antigravity-cli/brain/b4b46e1b-c954-4eb5-9c45-befe03b2010b/task3_2_1_dispatch_prompt.md` [GOV]  
**Ecosystem Master Mirror:** `D:/__CoChem/.docs/task3_2_1_dispatch_prompt.md` [GOV]  
**Repository Mirror:** `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_2_1_dispatch_prompt.md` [GOV]  
**Dropzone Inbox Mirror:** `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_2_1_dispatch_prompt.md` [GOV]  
**Target Persistence Deliverables:**  
- Primary WBS Decomposition Deliverable: `task3_2_1_vr03_vr05_l3_decomposition.md` (persisted across canonical mirrors) [M]  
- Swarm State Ledger: `swarm_state.json` [PROC]  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol and multi-agent skill taxonomy ([`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md)), `cochem-sdp-manager` is the sole authoritative agent chartered to execute Work Breakdown Structure (WBS) decomposition, formalize acceptance criteria, establish numerical invariants, assign single-owner RACI roles, and compile risk registers under the **PMBOK 100% Rule** and **MECE (Mutually Exclusive, Collectively Exhaustive)** principles.
2. **Strict Separation of Duties & Zero-Trust Governance:**  
   Task 3.2.1 defines requirements, acceptance criteria, and work package boundaries. Under CoChem Zero-Trust governance:
   - Functional implementation belongs strictly to `cochem-coder`. Coders are strictly forbidden from defining project scope or establishing their own acceptance criteria.
   - Independent physical test harness execution belongs exclusively to `cochem-tester`.
   - Asymmetric compliance audits and ratification sign-offs belong to `cochem-audit` and `adversary`.
   - Technical manual typesetting belongs to `cochem-scribe`, but formal PMBOK/SWEBOK WBS baselines and project lifecycle state updates belong strictly to `cochem-sdp-manager`.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` authored and owns all preceding ratified WBS baseline specifications across Tasks 1, 2, and 3:
   - Task 1 WBS Baseline: `task1_level2_wbs_breakdown.md`
   - Task 2 Survey & WBS: `task2_2_1_dispatch_prompt.md`, `task2_level2_wbs_breakdown.md`
   - Task 3 MECE Work Packages: `task3_1_2_dispatch_prompt.md`
   - Task 3 WBS Assembly & Checksumming: `task3_1_5_dispatch_prompt.md`, `task3_1_6_execution`  
   Assigning Task 3.2.1 to `cochem-sdp-manager` maintains role integrity, PMBOK compliance, and ledger continuity.

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 3.2.1 - DECOMPOSE L2 TASK FOR VR-03 AND VR-05 INTO GRANULAR, COMPONENT-LEVEL L3 IMPLEMENTATION TASKS]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery, 100% Rule), SWEBOK v3/v4 (Software Engineering Management, Software Quality, and Requirements Architecture), Method Matrix v4.1, and the CoChem Anti-Spoofing Protocol v4.

================================================================================
1. PROJECT HIERARCHY & SPECIFIC TASK ASSIGNMENT
================================================================================
- Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]
- Level 2: Formalized acceptance criteria, numerical invariants, and provenance tags ([M], [D], [E]) for VR-03 and VR-05. [GOV]
- Specific Task to Execute:
  3.2.1 - Decomposed L2 task for VR-03 and VR-05 into granular, component-level L3 implementation tasks. [GOV] / [DOC]

================================================================================
2. MANDATORY RULE 1: INGEST EXISTING PROJECT FILES VIA TOOLS (DO NOT GUESS)
================================================================================
Before generating, decomposing, or writing any specifications, you MUST use your filesystem inspection tools (view_file, grep_search, list_dir, find_by_name, run_command) to inspect existing project files on disk to establish full empirical context:

1. Method Matrix & Verification Specification Baselines:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md (and Method_Matrix/Method_Matrix_Hub.md):
     * §2.5 & §3.3: Dynamic Quadrature Lifecycle (DEFGRID1 -> DEFGRID2 -> DEFGRID3). Prohibition of deprecated Grid3/Grid5.
     * §2.5 & §4.4: Coupled Grid-SCF Invariant. Analytic Hessians, vibrational frequencies, and VPT2 force fields fail-closed on grids coarser than DEFGRID3 (GridSpecificationError / METHOD_MATRIX_VIOLATION_DEFGRID).
     * §2.8: Electronic Dispersion Sanitization. Eradication of double-counting: prohibit D3/D4/D3BJ on non-local VV10 functionals (wB97M-V, B97M-V) -> RedundantDispersionError. Standard hybrids on non-covalent complexes lacking dispersion -> MissingDispersionError. Trimers (N_monomers >= 3) mandate Axilrod-Teller-Muto (ATM) 3-body dispersion.
     * §2.9: Singularity-Guarded Spin Purity Gatekeeper. Singlet guard (|S| < 1.0e-7 => |<S^2>| < 0.05 a.u.). Open-shell guard (S > 0 => Delta <S^2> < 10.0%). Fail-closed with SpinContaminationError and escalation to Tier 9 (RO-DFT / CASSCF / NEVPT2).
   - D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md (Verification Requirements VR-03 and VR-05).

2. Existing Codebase Implementation Modules:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/mm/quadrature_manager.py
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_grid_convergence.py
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/analysis/electronic_sanitizer.py
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py

3. Preceding WBS and Swarm Planning Artifacts:
   - D:/__CoChem/.docs/task3_level2_wbs_breakdown.md
   - D:/__CoChem/.docs/task3_boundary_and_interface_manifest.md
   - D:/__CoChem/.docs/task3_1_1_dispatch_prompt.md
   - D:/__CoChem/.docs/task3_1_2_dispatch_prompt.md
   - D:/__CoChem/.docs/task3_1_5_dispatch_prompt.md
   - D:/__CoChem/swarm_state.json

You are STRICTLY FORBIDDEN from guessing module paths, hallucinating thresholds, or synthesizing tasks without reading the physical files first.

================================================================================
3. TECHNICAL SCOPE & DECOMPOSITION REQUIREMENTS (PMBOK & SWEBOK)
================================================================================
You must decompose Level 2 (VR-03 and VR-05) into a comprehensive set of granular, component-level Level 3 implementation tasks satisfying:

1. The PMBOK 100% Rule & MECE Principle:
   - Subdivide VR-03 (Quadrature & Invariants) and VR-05 (Dispersion Sanitizer & Spin Gatekeeper) into distinct, atomic work packages.
   - Every L3 task must have a unique identifier (e.g., L3.3.1 to L3.3.n or 3.2.1.1 to 3.2.1.n).
   - Single-Agent RACI: Every L3 task must have exactly one assigned responsible agent (e.g., cochem-coder, cochem-tester, cochem-audit, cochem-scribe; strictly NO dual or shared assignments).

2. Method Matrix Scientific Provenance & Invariants:
   - Every requirement, formula, and acceptance gate must be tagged with strict provenance:
     * [M] (Methodological / Mandatory)
     * [D] (Deterministic / Domain Physics)
     * [E] (Empirical / Experimental Benchmark)
     * [GOV] (Governance / Council Policy)
     * [PROC] (Procedural / Standard Execution)
   - Dynamic Mendeleev Mandate: Enforce that all atomic/isotopic mass references require dynamic retrieval via `from mendeleev import element` (hardcoding masses is strictly banned).
   - Singularity Guard Formulation: Explicitly formalize the piecewise evaluation for singlet vs open-shell spin contamination:
     * |S| < 1.0e-7: Delta <S^2>_abs = |<S^2>_obs| < 0.05 a.u. [D]
     * |S| >= 1.0e-7: Delta <S^2>_rel = (|<S^2>_obs - S(S+1)| / S(S+1)) * 100% < 10.0% [D]
   - Coupled Grid-SCF Invariant: Explicitly formalize fail-closed validation forbidding frequencies/Hessians on DEFGRID1/DEFGRID2.

3. Detailed Work Package Structure for Each L3 Task:
   - Task ID & Descriptive Title
   - Responsible Agent
   - Targeted Codebase Module / File Path
   - Exact Input Preconditions
   - Concrete Deliverable / Output Artifact
   - Formal Acceptance Criteria & Quantitative Thresholds
   - Provenance Tag ([M], [D], [E], [GOV], [PROC])
   - Dependent & Predecessor Tasks

================================================================================
4. MANDATORY RULE 2: WRITE FINAL RESULTS TO ACTUAL FILES ON DISK VIA TOOLS
================================================================================
You are STRICTLY FORBIDDEN from presenting your decomposition solely in conversational text.
You MUST invoke the `write_to_file` tool (with Overwrite=true) to persist your output directly to disk across all designated mirrors:

1. Primary WBS Decomposition Deliverable (`task3_2_1_vr03_vr05_l3_decomposition.md`):
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_1_vr03_vr05_l3_decomposition.md`
   - `C:/Users/ansac/.gemini/antigravity-cli/brain/b4b46e1b-c954-4eb5-9c45-befe03b2010b/task3_2_1_vr03_vr05_l3_decomposition.md`
   - `D:/__CoChem/.docs/task3_2_1_vr03_vr05_l3_decomposition.md`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_2_1_vr03_vr05_l3_decomposition.md`
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_2_1_vr03_vr05_l3_decomposition.md`

2. Swarm State Ledger Synchronization:
   - Read and update `D:/__CoChem/swarm_state.json` and its mirrors via `write_to_file` (Overwrite=true), recording:
     * task_hierarchy (Level 1, Level 2, Level 3 Task 3.2.1)
     * agent_name: "cochem-sdp-manager"
     * timestamp: <Current ISO 8601 Timestamp>
     * status: "SUCCESS"
     * pmbok_100_percent_rule_enforced: true
     * mece_decomposition_guaranteed: true
     * raci_enforced: true
     * artifacts_produced: list of persisted file paths
     * byte_count and line_count
     * sha256_checksum: calculated via Get-FileHash -Algorithm SHA256
     * audit status: "PENDING_ASYMMETRIC_AUDIT" (auditors: ["cochem-audit", "adversary"])

3. Zero Counterfeit Token Verification:
   - Run a static scan verifying zero simulation doubles, zero stubs, zero mocks, zero fake data, and zero unelaborated return routines.

================================================================================
5. MANDATORY RULE 3: RETURN FINAL TEXT REPORT DETAILING MODIFIED FILE PATHS
================================================================================
Upon completing file creation, disk writes, checksumming, and ledger updates, you MUST return a comprehensive final text report in your conversational response.
Your report MUST begin with `[SDPM REPORT]` and conclude with `[VERIFICATION & HANDOFF SUMMARY]` detailing:
1. High-level execution status (SUCCESS).
2. The EXACT physical file paths created or modified on disk across all canonical mirrors.
3. Total line counts and physical byte sizes of all created/modified files on disk.
4. Exact computed SHA-256 cryptographic digest of each file.
5. Verification of zero counterfeit tokens confirmed by automated static scan.
6. Confirmation of dynamic Mendeleev mass retrieval enforcement throughout the specification.
7. Verification that Asymmetric Sign-off remains pending (`- [ ] Pending independent Agent Council sign-off`).
8. Formal handoff routing for `cochem-audit` and `adversary` to conduct the downstream asymmetric audit.
```

---

## 3. Downstream Swarm Handoff & Asymmetric Audit Protocol

Once `cochem-sdp-manager` completes execution of this prompt and reports its modified files and SHA-256 digests:
1. **Asymmetric Audit Routing:** As `0rchestrator`, natively spin up `cochem-audit` and `adversary` via `invoke_subagent` (prioritizing Antigravity quota over external scripts).
2. **Verification Criteria:** The auditors will inspect `task3_2_1_vr03_vr05_l3_decomposition.md` across mirrors for:
   - Strict PMBOK 100% Rule coverage of VR-03 and VR-05.
   - Total eradication of mocked or placeholder tokens.
   - Compliance with the Mendeleev dynamic mass retrieval mandate.
   - Cryptographic byte-for-byte integrity against `swarm_state.json`.
