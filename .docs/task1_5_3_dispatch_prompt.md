# Task 1.5.3 Dispatch Specification: L3 Task Assignment, Provenance, & Acceptance Criteria Matrix

**Parent Task:** Level 1: Task 1: Implement Ingestion Plane & Physical Invariant Foundation (VR-01) - Dynamic Mendeleev mass queries, Eckart frame translation/rotation zeroing, and two-stage conformer deduplication with automorphism invariance.  
**Level 2 Task:** Formulate Risk Register and SWEBOK Quality & Traceability Matrix  
**Specific Task to Execute:** `1.5.3 - Specify explicit agent assignments, provenance tags ([M], [D]), inputs, deliverables, and acceptance criteria for all L3 tasks`  
**Exact Execution Agent:** `cochem-sdp-manager`  
**Canonical Dispatch File:** [`task1_5_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_3_dispatch_prompt.md)  
**Target Persistence Files:**  
- Primary Deliverable: [`task1_5_3_traceability_matrix.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_3_traceability_matrix.md)  
- Swarm State Ledger: [`swarm_state.json`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Justification:
1. **Taxonomy & Domain Authority:**  
   Under the CoChem Multi-Agent Architecture and skill taxonomy, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole authoritative agent responsible for Work Breakdown Structure (WBS) decomposition, Quality & Traceability Matrices, and swarm agent task assignments. Its foundational instructions mandate applying **PMBOK 2021 (7th Edition)** and **SWEBOK v3/v4** to establish formal, actionable project execution baselines.
2. **Separation of Concerns & Governance Boundary:**  
   Task 1.5.3 requires defining granular execution assignments, provenance tagging, interface contracts, and non-negotiable acceptance criteria for downstream agents. This is strictly a project management and systems engineering function. Delegating this to `cochem-coder` violates role boundaries (an implementer must not write their own acceptance criteria); delegating to `cochem-tester` or `cochem-audit` violates verification independence.
3. **Precedent Continuity:**  
   `cochem-sdp-manager` successfully established the preceding WBS baselines and microtask specifications for Task 1 (Tasks 1.2.2, 1.2.3, 1.3.1, 1.3.2, 1.3.3, 1.3.4, and 1.5.2). Assigning Task 1.5.3 to `cochem-sdp-manager` ensures single-point RACI accountability and flawless schema continuity.

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 1.5.3 - SPECIFY EXPLICIT AGENT ASSIGNMENTS, PROVENANCE TAGS ([M], [D]), INPUTS, DELIVERABLES, AND ACCEPTANCE CRITERIA FOR ALL L3 TASKS]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 2021 (7th Edition), IEEE 16085:2021, SWEBOK v3/v4, and ISO/IEC 25010 principles to construct formal, actionable, zero-mock quality assurance baselines, risk registers, and requirements traceability matrices (RTM).

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 1: Implement Ingestion Plane & Physical Invariant Foundation (VR-01) - Dynamic Mendeleev mass queries, Eckart frame translation/rotation zeroing, and two-stage conformer deduplication with automorphism invariance.
- Level 2: Formulate Risk Register and SWEBOK Quality & Traceability Matrix.
- Level 3 Target (Task 1.5.3):
  Specify explicit agent assignments, provenance tags ([M], [D]), inputs, deliverables, and acceptance criteria for all L3 tasks.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before authoring any task specification or matrix, you MUST invoke your file inspection tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to inspect the local filesystem and gain empirical context on Task 1's work package breakdown:

1. Ingest predecessor work package definitions and architectural specifications for Task 1 (VR-01):
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_3_dispatch_prompt.md` (Contains the definitive 17 L3 implementation microtasks across Tracks 1–5: L3-T1-01 through L3-T1-17)
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_4_dispatch_prompt.md` (Contains verifiable boundaries, mathematical tolerances, and WBS packaging)
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_2_dispatch_prompt.md` (Contains the compliance frameworks and quality models)
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task1_3_4_prompt_audit_report.md` (Adversary verification standards and acceptance gates)
2. Ingest the current swarm ledger to verify execution state and dependencies:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json`
3. Inspect authoritative standards and source guidance if accessible:
   - `D:/Gdrive/__agentic/.sources/PMBOK-2021.pdf`
   - `D:/Gdrive/__agentic/.sources/SWEBOKv3-published.pdf`
   - `D:/Gdrive/__agentic/.sources/Global_Agent_Index.md`

You are STRICTLY FORBIDDEN from hallucinating task boundaries, guessing work package codes, or omitting any of the 17 work packages defined in Task 1.

================================================================================
TECHNICAL SCOPE & MATRIX SPECIFICATION REQUIREMENTS (TASK 1.5.3)
================================================================================
You must specify the complete, unabridged Traceability & Assignment Matrix covering EXACTLY SEVENTEEN (17) L3 microtasks across the 5 technical tracks of Task 1 (VR-01):
- Track 1: Dynamic Mendeleev Mass Resolution & Nuclide Normalization (L3-T1-01 to L3-T1-05)
- Track 2: Mass-Weighted Center-of-Mass Invariant & Translation Zeroing (L3-T1-06 to L3-T1-07)
- Track 3: Eckart SO(3) Frame Rotation & Inversion Gate (L3-T1-08 to L3-T1-10)
- Track 4: Two-Stage Conformer Deduplication & Automorphism Sieve (L3-T1-11 to L3-T1-14)
- Track 5: Subsystem Packaging, Dataclass Typing, & Verification Harness (L3-T1-15 to L3-T1-17)

For EVERY SINGLE ONE of the 17 L3 microtasks, define and document:
1. Unique Task ID & Microtask Name (e.g., `L3-T1-01: Static Mass Dictionary Audit & Elimination`)
2. Explicit Single Execution Agent Assignment: Nominate the exact single execution agent from the CoChem swarm (e.g., `cochem-coder`, `cochem-tester`, `cochem-audit`, `cochem-sdp-manager`, `researcher`, `adversary`).
3. Supervising / Verifying Agent (e.g., `cochem-audit` or `adversary`).
4. Authoritative Provenance Tags: Assign explicit provenance tags according to CoChem standards:
   - [M]: Method Matrix (empirical benchmark / physical measurement)
   - [D]: Database/Derived mathematical relationship
   - [E]: Estimated theoretical projection
5. Input Specifications: Physical datasets, coordinate representations (.xyz, .mol, .sdf, .pdb), molecular constraints, upstream dataclass models, or upstream deliverables required before execution.
6. Concrete Deliverables: Exact file names, module paths, or test artifacts to be produced (e.g., `src/cochem_base/intake/isotopes.py`, `tests/test_dynamic_mendeleev.py`).
7. Strict Acceptance Criteria & Physical Invariant Tolerances:
   - Dynamic Mendeleev queries via `from mendeleev import element`; zero hardcoded mass tables; in-memory cache lookup $< 1\ \mu\text{s}$ [D].
   - Counterpoise ghost atoms (`Gh`, `Bq`, `X`) return exact $0.0\text{ u}$; non-physical symbols raise `InvalidNuclideSpecificationError` [D].
   - Center-of-mass translation momentum residual $\|\sum m_i \mathbf{r}'_i\|_2 < 1.0 \times 10^{-12}\text{ a.u.}$ in float64 [D].
   - Eckart angular momentum residual $\|\sum m_i (\mathbf{r}_i^0 \times \mathbf{r}'_i)\|_2 < 1.0 \times 10^{-10}\text{ a.u.}$ [D].
   - Proper rotation locking in $\mathrm{SO}(3)$: $\det(\mathbf{U}) = +1.000000 \pm 10^{-12}$; strict detection and fail-closed rejection of improper reflections $\det(\mathbf{U}) = -1.0$ via `ImproperRotationError` [D].
   - Stage 1 Weisfeiler-Lehman (1-WL $h=3$) graph automorphism hashing with $1.28 \times (r_i + r_j)$ covalent graph; Hungarian bipartite matching fallback when orbit permutations $> 720$ [D].
   - Stage 2 Horn quaternion Kabsch RMSD tolerance: $\tau_{\text{RMSD}} < 0.0800\text{ \AA}$ [M].
   - Rotational constant filter tolerance: $\max |\Delta B_i / B_i| \le 0.05\%$ [M].
   - Line-1 JAX 64-bit initialization: `JAX_ENABLE_X64=True` [D].
   - Zero-Mock Compliance: Zero stubs, zero `pass`, zero `NotImplementedError`, zero synthetic coordinates (`np.zeros`, `np.ones`, `np.eye`), path-scoped AST anti-spoof linter returncode 0.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL CODE / RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely printing your output to conversational chat or temporary memory buffers.
You MUST invoke your `write_to_file` tool to persist the complete, unabridged Traceability & Assignment Matrix directly to physical disk at:

1. Primary Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_3_traceability_matrix.md`

2. Swarm State Ledger Synchronization:
   Atomically update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` using `write_to_file` (Overwrite=true) recording:
   ```json
   {
     "anti_spoofing_compliance": true,
     "work_packages_count": 17,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 1.5.3: Specified explicit agent assignments, provenance tags ([M], [D]), inputs, deliverables, and acceptance criteria for all 17 L3 microtasks of Task 1 (VR-01)",
     "wbs_level": "Level 2 / Task 1.5 Quality, Risk & Traceability Matrix",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_3_traceability_matrix.md"
     ],
     "sha256_checksum": "<SHA256_DIGEST>"
   }
   ```

================================================================================
CRITICAL DIRECTIVE 3: RETURN FINAL TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a comprehensive final text report in your final terminal response.
Your report MUST begin with `[SDPM REPORT]` and MUST conclude with a dedicated `[VERIFICATION & HANDOFF SUMMARY]` section detailing:
1. Execution status (`SUCCESS` or `FAILURE`).
2. Exact absolute and relative file paths modified or created on disk.
3. Physical byte count and line count of each generated artifact.
4. Cryptographic SHA-256 hash of each modified file.
5. High-level summary of the assignments (verification of 17 work packages, agent breakdown, provenance tag distribution).
6. Formal handoff gate notice for `cochem-audit` and `adversary` for asymmetric audit verification.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate mocks, stubs, dummy loops, and fake data structures.
- Do NOT use `NotImplementedError` or empty `pass` blocks as dead-end stubs.
- Do NOT use synthetic array generators (`np.zeros`, `np.ones`, `np.eye`) to fake state tensors or coordinate matrices.
- Do NOT use shortcut tag-appending (e.g., `[AUDITOR FIX REQUIRED]`); deliver complete, production-grade specifications.
- Strictly enforce the dynamic Mendeleev retrieval invariant (`from mendeleev import element`).
```
