# Task 5.1.2 Dispatch Specification: Work Breakdown Structure (WBS) & MECE Component-Level L3 Task Decomposition

**Parent Task:** Level 1: Task 5: Execute End-to-End System Integration, Verification Suite & Sequential Adversarial Council Audit - Comprehensive VR-01 to VR-06 regression testing, Recipe R2 benchmark calculation, and final audit ratification prior to git commit.  
**Level 2 Task:** Formulated Level 2 technical tasks (5.1 through 5.5) with granular Level 3 sub-tasks, agent assignments, target filepaths, and physical acceptance thresholds.  
**Specific Task to Execute:** `5.1.2 - Decomposed Level 2 task into 19 granular L3 component implementation tasks across tracks 5.1 to 5.5 (cochem-sdp-manager)`  
**Exact Execution Agent:** `cochem-sdp-manager`  
**Canonical Dispatch File:** [`task5_1_2_dispatch_prompt.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/task5_1_2_dispatch_prompt.md)  
**Primary Scratch Dispatch File:** [`task5_1_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_1_2_dispatch_prompt.md)  
**Target Persistence File:** [`task5_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task5_level2_wbs_breakdown.md)  
**Scratch Mirror Target:** [`task5_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md)  
*(Software Development Project Manager & PMBOK/SWEBOK Architect, CoChem Agent Council)*

### Authoritative Justification & Role Segregation:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol, Multi-Agent Council taxonomy, and IEEE 830-1998 / PMBOK standards, `cochem-sdp-manager` is the sole authoritative agent tasked with authoring formal Work Breakdown Structures (WBS), establishing single-owner RACI matrices, enforcing the PMBOK 100% Rule, guaranteeing MECE (Mutually Exclusive, Collectively Exhaustive) task partitioning, compiling multi-environment risk registers, and synchronizing swarm state ledgers.
2. **Structural Pairing with `cochem-scribe`:**  
   In the CoChem Work Breakdown Structure hierarchy (formalized in `raw_task_list.json` and mirrored in preceding tasks across Chunk 17), scientific scope definition and research feasibility elicitation (Task X.1.1) is authored by `cochem-scribe`, while subsequent Work Breakdown Structure (WBS) decomposition and PMBOK project management work packages (Task X.1.2) are executed by `cochem-sdp-manager`. This is explicitly codified in `task5_scope_and_research_feasibility_analysis.md` §8 (Line 330):  
   `* Task 5.1.2: Decompose Level 2 task into 19 granular L3 component implementation tasks across tracks 5.1 to 5.5 (cochem-sdp-manager).`
3. **Anti-Spoofing Protocol v4 Independence Mandate:**  
   Implementation agents ([`cochem-coder`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-coder/SKILL.md)) and test execution agents ([`cochem-tester`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-tester/SKILL.md)) are strictly barred from authoring the governing WBS, work packages, or acceptance criteria they are tasked with fulfilling. This separation of duties eliminates structural bias, self-certification conflicts of interest, and counterfeit compliance. Independent QA agents ([`cochem-audit`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-audit/SKILL.md), [`adversary`](file:///C:/Users/ansac/.gemini/config/skills/agent-adversary/SKILL.md)) are reserved for asymmetric adversarial verification.
4. **Precedent & Swarm Continuity:**  
   This assignment directly follows the ratified precedent established in Task 1.1.2 (`1.1.2_prompt.json`), Task 2.2.1–2.2.2 (`task2_2_2_dispatch_prompt.md`), and Task 3.1.2–3.1.6 (`task3_1_2_dispatch_prompt.md`, `task3_level2_wbs_breakdown.md`), where `cochem-sdp-manager` was designated to author the authoritative WBS baselines and risk registers.

---

## 2. Authoritative Dispatch Prompt

```markdown
[SDPM EXECUTION ORDER: TASK 5.1.2 - WORK BREAKDOWN STRUCTURE (WBS) & LEVEL 3 DECOMPOSITION ACROSS TRACKS 5.1 TO 5.5]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery, 100% Rule), SWEBOK v3/v4 (Software Engineering Management, Software Quality, and Requirements Architecture), Method Matrix v4.1, and the CoChem Anti-Spoofing Protocol v4.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 5: Execute End-to-End System Integration, Verification Suite & Sequential Adversarial Council Audit - Comprehensive VR-01 to VR-06 regression testing, Recipe R2 benchmark calculation, and final audit ratification prior to git commit.
- Level 2: Formulated Level 2 technical tasks (5.1 through 5.5) with granular Level 3 sub-tasks, agent assignments, target filepaths, and physical acceptance thresholds.
- Specific Task to Execute:
  5.1.2 - Decomposed Level 2 task into 19 granular L3 component implementation tasks across tracks 5.1 to 5.5.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before generating, decomposing, or authoring any WBS specifications, you MUST use your filesystem inspection tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to inspect the existing project files on disk to establish complete empirical context:

1. Scope and Feasibility Baseline:
   - `D:/__CoChem/.docs/task5_scope_and_research_feasibility_analysis.md`
   (Read Pillar 1 Scope Decomposition Phases A-D, Pillar 2 Physics Invariants VR-01 to VR-06, Pillar 3 Recipe R2 Blueprint, and Pillar 4 Multi-Environment Risk Register & Ephemeral Quarantine Protocol).

2. Authoritative SRS Specification:
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md`
   (Read Section 1 Forensic Audit & §8D Framework, Section 2 Method Matrix v4.1 Physics, Section 4 Verification Requirements VR-01 through VR-06, and Section 5 Pipeline Architecture).

3. Method Matrix Physics Baseline:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md`
   (Inspect Section 3.0 B_e vs B_0 rotational constant distinction, Section 3.3 mandatory spend priority hierarchy, Section 4.4 tight convergence thresholds, Section 8B.3 ban on Calc_Hess true, Section 9A Recipe R1/R2 van der Waals complex protocols).

4. Governing Task Registers & Existing WBS Baselines:
   - `D:/__CoChem/__agentic/.scripts/raw_task_list.json`
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md`
   - `D:/__CoChem/.docs/Task_List_Task3_WBS.md`
   - `D:/__CoChem/__agentic/swarm_state.json`

5. Verification Suites & Core Modules:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/anti_spoof_linter.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/verify_core_integrity.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/process_runner.py`

You are STRICTLY FORBIDDEN from guessing file structures, fabricating work package IDs, or inventing theoretical tolerances. Extract all requirements directly from disk.

================================================================================
TECHNICAL SCOPE: GRANULAR LEVEL 3 COMPONENT DECOMPOSITION (TASK 5.1.2)
================================================================================
You must author and persist an exhaustive, production-grade Work Breakdown Structure (WBS) artifact that systematically decomposes Level 2 into 19 granular Level 3 component implementation tasks satisfying:

1. THE PMBOK 100% RULE & MECE STRUCTURAL GUARANTEE:
   - Subdivide Level 1 Task 5 into 5 technical tracks containing exactly 19 mutually exclusive and collectively exhaustive (MECE) Level 3 work packages:
     * Track 5.1: Pre-Integration Hardening & Audit Remediation (Tasks 5.1.1 to 5.1.4)
       - 5.1.1: Product Classification Ontology Disambiguation (`Product B` vs `Product M`) -> `cochem-coder` [M]
       - 5.1.2: Chained Hessian Parameterization in ORCA Deck Generator (`InHess READ` / `InHessName`) -> `cochem-coder` [M]
       - 5.1.3: Symmetry Automorphism Invariance in Conformer Sieve (graph automorphisms + Kabsch RMSD < 0.08 A) -> `cochem-coder` [M]
       - 5.1.4: Subprocess & LF Hash Assertion Hardening in Legacy Tests (UTF-8 stream decoding, CRLF normalization) -> `cochem-coder` [PROC]
     * Track 5.2: Comprehensive Regression Suite & AST Security Audit (Tasks 5.2.1 to 5.2.4)
       - 5.2.1: Static AST Anti-Spoof Linter Scan Across All Files (`strict=True`) -> `cochem-audit` [PROC]
       - 5.2.2: Air-Gapped Test Runner Execution of Verification Suite (`test_chunk17_verification_suite.py`) -> `cochem-tester` [PROC]
       - 5.2.3: Physical Invariant & Tolerance Gating (VR-01 to VR-06) -> `cochem-tester` [M] / [D]
       - 5.2.4: Core Infrastructure and Environment Integrity Gating (`verify_core_integrity.py`) -> `cochem-tester` [PROC]
     * Track 5.3: Authentic Recipe R2 Benchmark Calculation (Tasks 5.3.1 to 5.3.4)
       - 5.3.1: NIST/CCCBDB Monomer Ingestion & Wilson Constraints (CO2...H2O complex) -> `cochem-coder` [M] / [D]
       - 5.3.2: Publication-Grade ORCA Recipe R2 Deck Generation (wB97M-V/def2-QZVPP, DEFGRID3, InHess XTB2, TightSCF, quintuple convergence) -> `cochem-coder` [M]
       - 5.3.3: Air-Gapped Subprocess Dispatch & PID Telemetry Logging -> `cochem-tester` [PROC]
       - 5.3.4: Residual Gradient Parsing (||g_residual||_inf <= 1.0e-4 a.u.) & Rotational Constant Extraction (A_0, B_0, C_0) -> `cochem-tester` [M] / [D]
     * Track 5.4: Sequential Adversarial Swarm Council Audit (Tasks 5.4.1 to 5.4.4)
       - 5.4.1: Sequential Persona Dispatch & Stage Machine Handshake -> `0rchestrator` [GOV]
       - 5.4.2: Asymmetric Quarantine Verification via zero_trust_runner.py (/tmp/cochem_exec_<uuid>/) -> `cochem-audit` [PROC]
       - 5.4.3: Red-Team Anti-Spoofing Penetration & Token Weaponization -> `adversary` [PROC]
       - 5.4.4: Council Deliberation & Final Ratification Report Generation -> `cochem-sdp-manager` [DOC] / [GOV]
     * Track 5.5: Cryptographic Integrity Gating & Git Ingress (Tasks 5.5.1 to 5.5.3)
       - 5.5.1: Path-Scoped Pre/Post Cryptographic Hash Gate Execution (`path_scoped_hash_gate.py`) -> `cochem-audit` [PROC]
       - 5.5.2: Working Tree Cleanliness & Anti-Diversion File Audit (`git status --porcelain`) -> `cochem-audit` [PROC]
       - 5.5.3: Git Staging, Attestation Tagging & Council Signed Commit -> `0rchestrator` [GOV]

2. SINGLE-AGENT RACI ACCOUNTABILITY:
   - Assign exactly one accountable agent persona to each of the 19 work packages (strictly NO shared or dual assignments).

3. METHOD MATRIX SCIENTIFIC PROVENANCE & INVARIANTS:
   - Tag every work package, formula, and acceptance gate with strict provenance:
     * `[M]` (Method Matrix empirical benchmark)
     * `[D]` (Derived mathematical / physical relationship)
     * `[E]` (Estimated theoretical projection)
     * `[PROC]` (Verification procedure)
     * `[GOV]` (Governance / Council policy)

4. MULTI-ENVIRONMENT RISK REGISTER:
   - Formalize RSK-CHUNK17-01 through RSK-CHUNK17-06 with explicit triggers, probabilities, impacts, and fail-closed mitigations:
     * RSK-CHUNK17-01: Windows CP1252 charmap encoding crash on stdout streaming.
     * RSK-CHUNK17-02: Cryptographic hash drift due to CRLF vs LF line endings.
     * RSK-CHUNK17-03: Rotamer false negatives caused by permutation symmetry automorphisms.
     * RSK-CHUNK17-04: Hessian chaining failure or Calc_Hess true regression.
     * RSK-CHUNK17-05: Coupled Grid-SCF convergence divergence on fine grids.
     * RSK-CHUNK17-06: Asymmetric quarantine file leak or privilege escalation.

5. VERIFICATION & ACCEPTANCE THRESHOLDS:
   - Document explicit mathematical pass/fail criteria for each task (e.g., Eckart translation ||sum m_i r_i|| < 1.0e-12 a.u., SO(3) det(U) = +1.0, Kabsch RMSD < 0.08 A, rotational constant variance |Delta B/B| <= 0.05%, quintuple convergence tolerances TolE 1e-7 / TolMaxG 1e-5 / TolRMSG 3e-6 / TolRMSD 5e-5 / TolMaxD 1e-4 / MaxIter 200, residual gradient ||g_residual||_inf <= 1.0e-4 a.u.).

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL RESULTS TO ACTUAL FILES ON DISK VIA TOOLS
================================================================================
You are STRICTLY FORBIDDEN from merely emitting conversational markdown to standard output or markdown reply buffers.
You MUST use your filesystem authoring tools (`write_to_file`) to persist the complete, unabridged WBS specification directly to physical disk at:
- Primary Canonical Deliverable:
  `D:/__CoChem/.docs/task5_level2_wbs_breakdown.md`
- Scratch Mirror Target:
  `C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md`
- Repository Mirror Target:
  `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task5_level2_wbs_breakdown.md`
- Dropzone Inbox Mirror Target:
  `D:/__CoChem/__agentic/dropzones/inbox_srs/task5_level2_wbs_breakdown.md`
- Swarm State Synchronization:
  Atomically update `D:/__CoChem/__agentic/swarm_state.json` and mirror to `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` recording:
  ```json
  {
    "agent_name": "cochem-sdp-manager",
    "timestamp": "<CURRENT_ISO8601_TIMESTAMP>",
    "status": "COMPLETED",
    "task": "Task 5.1.2: Decomposed Level 2 task into 19 granular L3 component implementation tasks across tracks 5.1 to 5.5",
    "wbs_level": "Level 2 WBS Decomposition",
    "tracks_count": 5,
    "tasks_count": 19,
    "pmbok_100_percent_rule": true,
    "mece_decomposition_guaranteed": true,
    "single_agent_raci_enforced": true,
    "provenance_tags_enforced": true,
    "anti_spoofing_compliance": true,
    "artifacts_produced": [
      "D:/__CoChem/.docs/task5_level2_wbs_breakdown.md",
      "C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md",
      "D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task5_level2_wbs_breakdown.md",
      "D:/__CoChem/__agentic/dropzones/inbox_srs/task5_level2_wbs_breakdown.md"
    ],
    "sha256_checksum": "<COMPUTED_SHA256>"
  }
  ```

================================================================================
CRITICAL DIRECTIVE 3: FINAL AUDIT TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a structured final text report in your terminal response.
Your report MUST start with `[SDPM REPORT]` and MUST conclude with a dedicated `[VERIFICATION & HANDOFF SUMMARY]` section detailing:
1. Verdict status (`SUCCESS` or `FAILURE`).
2. Exact absolute and relative file paths modified or created on disk.
3. Physical byte count and line count of each modified file.
4. Cryptographic SHA-256 hash of each modified file.
5. Executive summary of the 19 granular L3 work packages across tracks 5.1 to 5.5.
6. Formal handoff notice for `cochem-audit` and `adversary` for asymmetric verification.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate mocks, stubs, dummy loops, and fake data structures.
- Do NOT use `NotImplementedError` or empty `pass` blocks as dead-end stubs.
- Do NOT use synthetic array generators (`np.zeros`, `np.ones`, `np.eye`) to fake state tensors or coordinate matrices.
- Do NOT use shortcut tag-appending (e.g., `[AUDITOR FIX REQUIRED]`); deliver complete, production-grade architectural specifications.
- All atomic and isotopic masses MUST be dynamically retrieved via `from mendeleev import element`.
- Leave the asymmetric verification checkbox unchecked: `[ ] Asymmetric Verification Sign-Off: cochem-audit and adversary`.
```

---

## 3. Pre-Flight Verification & Ledger Synchronization

- **Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)
- **JSON Prompt Target:** [`D:\__CoChem\__agentic\.scripts\prompts\5.1.2_prompt.json`](file:///D:/__CoChem/__agentic/.scripts/prompts/5.1.2_prompt.json)
- **Canonical Dispatch Mirror:** [`D:\__CoChem\__agentic\dropzones\inbox_srs\task5_1_2_dispatch_prompt.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/task5_1_2_dispatch_prompt.md)
- **Scratch Dispatch Mirror:** [`C:\Users\ansac\.gemini\antigravity-cli\scratch\task5_1_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_1_2_dispatch_prompt.md)
- **Governance Alignment:** PMBOK 7th Edition, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing Protocol v4.
- **Audit Mandate:** Ready for sequential asymmetric audit by `cochem-audit` and `adversary`.
