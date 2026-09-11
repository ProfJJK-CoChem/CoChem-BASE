# Task 5.1.1 Dispatch Specification: Scope & Research Feasibility Analysis

**Parent Task:** Level 1: Task 5: Execute End-to-End System Integration, Verification Suite & Sequential Adversarial Council Audit - Comprehensive VR-01 to VR-06 regression testing, Recipe R2 benchmark calculation, and final audit ratification prior to git commit.  
**Level 2 Task:** Analyzed Level 1 Task 5 scope and research feasibility context for Chunk 17 Method Matrix v4.1 implementation.  
**Specific Task to Execute:** `5.1.1 - Analyzed Level 1 Task 5 scope and research feasibility context for Chunk 17 Method Matrix v4.1 implementation`  
**Exact Execution Agent:** `cochem-scribe`  
**Canonical Dispatch File:** [`task5_1_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_1_1_dispatch_prompt.md)  
**Target Persistence File:** [`task5_scope_and_research_feasibility_analysis.md`](file:///D:/__CoChem/.docs/task5_scope_and_research_feasibility_analysis.md)  
**Scratch Mirror Target:** [`task5_scope_and_research_feasibility_analysis.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_scope_and_research_feasibility_analysis.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** [`cochem-scribe`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-scribe/SKILL.md)  
*(Lead Technical Writing, Documentation, and Specification Analysis Agent, CoChem Agent Council)*

### Authoritative Justification & Role Segregation:
1. **Taxonomy & Domain Authority:**  
   Under the CoChem Agent Council Protocol, Multi-Agent Council taxonomy, and IEEE 830-1998 standards, `cochem-scribe` is the sole authoritative agent tasked with authoring publication-grade, FAIR-compliant technical specifications, scientific requirement analyses, and research feasibility analyses. It specializes in rigorous synthesis of quantum chemistry equations, Method Matrix constraints, error propagation dynamics, and formal verification frameworks.
2. **Structural Pairing with `cochem-sdp-manager`:**  
   In the CoChem Work Breakdown Structure hierarchy (established in `raw_task_list.json` and mirrored in `task1_level2_wbs_breakdown.md` and `task5_level2_wbs_breakdown.md`), technical specification and research feasibility elicitation (Task X.1.1) is authored by `cochem-scribe`, while subsequent Work Breakdown Structure (WBS) decomposition and PMBOK project management work packages (Task X.1.2) are executed by `cochem-sdp-manager`.
3. **Anti-Spoofing Protocol v4 Independence Mandate:**  
   Code implementation agents ([`cochem-coder`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-coder/SKILL.md)) and test execution agents ([`cochem-tester`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-tester/SKILL.md)) are strictly barred from authoring the governing scope and feasibility baseline they are tasked with implementing and testing. This segregation of duties eliminates structural bias and prevents counterfeit compliance. Independent QA agents ([`cochem-audit`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-audit/SKILL.md), [`adversary`](file:///C:/Users/ansac/.gemini/config/skills/agent-adversary/SKILL.md)) are reserved for asymmetric adversarial verification.
4. **Precedent Alignment:**  
   This assignment directly follows the ratified precedent established in Task 1.1.1 (`1.1.1_prompt.json`), where `cochem-scribe` was designated to author the comprehensive research context and SRS Chunk 17 analysis (`task1_vr01_research_and_srs_analysis.md`).

---

## 2. Authoritative Dispatch Prompt

```markdown
[SCRIBE EXECUTION ORDER: TASK 5.1.1 - SCOPE AND RESEARCH FEASIBILITY ANALYSIS FOR CHUNK 17 METHOD MATRIX v4.1]

You are cochem-scribe, the Lead Technical Writing, Documentation, and Specification Analysis Agent of the CoChem Agent Council. You author publication-grade, FAIR-compliant scientific documentation, technical specifications, and mathematical feasibility analyses strictly adhering to the CoChem Method Matrix v4.1, IEEE 830-1998, PMBOK 7th Edition (Scope Management Domain), and CoChem Anti-Spoofing Protocol v4.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 5: Execute End-to-End System Integration, Verification Suite & Sequential Adversarial Council Audit - Comprehensive VR-01 to VR-06 regression testing, Recipe R2 benchmark calculation, and final audit ratification prior to git commit.
- Level 2: Analyzed Level 1 Task 5 scope and research feasibility context for Chunk 17 Method Matrix v4.1 implementation.
- Specific Task to Execute:
  5.1.1 - Analyzed Level 1 Task 5 scope and research feasibility context for Chunk 17 Method Matrix v4.1 implementation.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before authoring any analysis or specifications, you MUST use your file inspection tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to read and inspect the existing project files, specifications, and source modules on disk to gain complete empirical context:

1. Authoritative SRS Specification:
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md`
   (Read Section 1 Forensic Audit & §8D Framework, Section 2 Method Matrix v4.1 Physics, Section 4 Verification Requirements VR-01 through VR-06, and Section 5 Pipeline Architecture).

2. Governing Work Breakdown Structures & Council Covenants:
   - `C:/Users/ansac/.gemini/antigravity-cli/brain/5174bed6-a1a8-4536-855d-ada266bf6109/WBS_Level_1_Tasks_Chunk_17.md`
   (Read the Executive Summary, 7 Binding Council Covenants, WBS 1.0-8.0, and Sequential Execution Schedule).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md`
   (Read the Level 2 Breakdown for Task 5, 19 L3 work packages, and the 5.1-5.5 technical tracks).

3. Method Matrix Physics Baseline:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md`
   (Inspect Section 3.0 B_e vs B_0 rotational constant distinction, Section 3.3 mandatory spend priority hierarchy, Section 4.4 tight convergence thresholds, Section 8B.3 ban on Calc_Hess true, Section 9A Recipe R1/R2 van der Waals complex protocols).

4. Existing Core Implementations & Verification Suites:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py`
   (Read all 11 test methods implementing VR-01 through VR-06 regression testing).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py`
   (Read Recipe R2 %geom constraint injection, quintuple convergence block, and dynamic DEFGRID3 generation).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py`
   (Read residual gradient ||g_residual|| extraction and piecewise singlet singularity-protected spin gate).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/ci_tools/process_runner.py` & `ci_tools/verify_core_integrity.py`
   (Read air-gapped process runner with UTF-8 stream handling and LF-normalized cryptographic hashring).

5. Swarm State Ledger & Task Registry:
   - `D:/__CoChem/__agentic/swarm_state.json`
   - `D:/__CoChem/__agentic/.scripts/raw_task_list.json`

You are STRICTLY FORBIDDEN from guessing file structures, fabricating data schemas, or inventing theoretical tolerances. Extract all facts directly from disk.

================================================================================
TECHNICAL SCOPE: COMPREHENSIVE SCOPE & FEASIBILITY ANALYSIS (TASK 5.1.1)
================================================================================
You must author an exhaustive, publication-grade technical analysis report that systematically resolves and documents the four structural pillars of Level 1 Task 5:

1. PILLAR 1: SCOPE DECOMPOSITION OF LEVEL 1 TASK 5
   - Scope Boundary & Acceptance Gates: Define the operational boundaries of Task 5 across its four subordinate phases:
     * Phase A: Pre-Integration Hardening & Legacy Audit Remediation (Product B vs M ontology, chained Hessian parameterization, symmetry automorphism invariance in conformer deduplication, and legacy subprocess/LF hash assertion hardening).
     * Phase B: Comprehensive VR-01 to VR-06 Verification Suite & AST Security Audit (air-gapped execution of test_chunk17_verification_suite.py, static AST anti_spoof_linter.py scan under strict=True, and verify_core_integrity.py hashring gating).
     * Phase C: Authentic Recipe R2 Benchmark Calculation (CO2...H2O van der Waals complex, Wilson constraints on CCCBDB/NIST monomers, wB97M-V/def2-QZVPP, DEFGRID3, TightSCF, InHess XTB2, MaxIter 200, and residual gradient ||g_residual|| <= 1.0e-4 a.u.).
     * Phase D: Sequential Adversarial Swarm Council Audit (linear 4-stage handoff: cochem-coder -> cochem-tester -> cochem-audit -> adversary; asymmetric execution in /tmp/cochem_exec_<uuid>/; final ratification and signed git commit).

2. PILLAR 2: RESEARCH FEASIBILITY & DOMAIN PHYSICS CONTEXT (CHUNK 17 METHOD MATRIX v4.1)
   - Physical Invariant Feasibility Analysis: Analyze the mathematical and physical viability of every governing verification requirement:
     * VR-01: Mass-weighted Eckart translation zeroing (||sum m_i r_i|| < 1.0e-12 a.u.) and SO(3) proper rotation (det(U) = +1.0). Automorphism-invariant conformer deduplication combining Weisfeiler-Lehman topological hashing with Kabsch RMSD (< 0.08 A) and rotational constant variance (|Delta B/B| <= 0.05%). Dynamic Mendeleev mass queries with regex nuclide normalization ('D' -> 'H' mass 2, '13C' -> 'C' mass 13).
     * VR-02 & VR-04: Frozen Monomer Protocol (FMP) error propagation physics (dB/B = -2 dR/R). Justify freezing covalent monomer internals to isolate gradient budgets to intermolecular separation R. Model Hessian discipline (prohibiting Calc_Hess true; mandating InHess XTB2 or Lindh). Quintuple stationary convergence tolerances (TolE 1e-7, TolMaxG 1e-5, TolRMSG 3e-6, TolRMSD 5e-5, TolMaxD 1e-4, MaxIter 200).
     * VR-03: Dynamic quadrature grid lifecycle (DEFGRID1 -> DEFGRID2 -> DEFGRID3). Formalize the Coupled Grid-SCF Invariant and fail-closed GridSpecificationError on coarse-grid Hessians or VPT2 frequencies.
     * VR-05: Electronic structure sanitization: preflight validation of native non-local dispersion (wB97M-V), interception of redundant dispersion (wB97M-V + D3/D4 -> RedundantDispersionError), uncorrected hybrid interception (MissingDispersionError), Axilrod-Teller-Muto (ATM) 3-body dispersion on trimers, and piecewise singlet singularity-protected spin contamination gate (relative Delta<S^2> < 10% or singlet |<S^2>| < 0.05 a.u. triggering fail-closed routing to Tier T9 CASSCF/NEVPT2).
     * VR-06: Zero-trust CI execution substrate: air-gapped process runner, universal UTF-8 stream reconfiguration eliminating Windows CP1252 charmap aborts, AST anti-spoof linter defaulting to strict=True, and LF-normalized cryptographic hashring synchronization.
   - Rotational Constant Provenance Distinction: Explicitly establish and enforce the distinction between theoretical equilibrium rotational constants (A_e, B_e, C_e) and experimental ground-state microwave observables (A_0, B_0, C_0 = B_e + Delta B_vib).

3. PILLAR 3: RECIPE R2 BENCHMARK COMPUTATIONAL BLUEPRINT
   - System Selection: Carbon dioxide - water dimer (CO2...H2O), C_2v / C_s planar/T-shaped van der Waals complex.
   - Monomer Ingestion: CCCBDB / NIST experimental microwave monomer geometries: CO2 (r_CO = 1.1600 A, theta = 180.0 deg); H2O (r_OH = 0.9578 A, theta_HOH = 104.5 deg).
   - Wilson Internal Constraint Specification: Generate explicit ORCA %geom Constraints block locking internal coordinates while leaving intermolecular separation R and dimer angles fully unconstrained.
   - Input Deck Blueprint: Complete ORCA 6 input deck including ! wB97M-V def2-QZVPP DEFGRID3 TightSCF, %geom block with quintuple tolerances + MaxIter 200 + InHess XTB2, and Cartesian coordinate block.
   - Output Parsing Blueprint: Specification for extracting ||g_residual||_inf and asserting ||g_residual||_inf <= 1.0e-4 a.u., evaluating geometric strain caveats, and computing principal rotational constants.

4. PILLAR 4: MULTI-ENVIRONMENT FEASIBILITY & SEQUENTIAL AUDIT RISK REGISTER
   - Cross-Platform Feasibility: Assess execution across Windows Win32 (UTF-8 console and filelock), macOS OrbStack, Linux Debian, GitHub Actions CI, and HPC SLURM environments.
   - Sequential Audit Quarantine: Formalize the asymmetric handoff protocol into ephemeral /tmp/cochem_exec_<uuid>/ managed exclusively by zero_trust_runner.py.
   - Provenance Tagging: Attribute strict provenance tags ([M] for Method Matrix mandatory, [D] for Domain physics / derived, [E] for Empirical) to every equation, threshold, and operational rule.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL RESULTS TO ACTUAL FILES ON DISK VIA TOOLS
================================================================================
You are STRICTLY FORBIDDEN from merely emitting conversational markdown to standard output or markdown reply buffers.
You MUST use your filesystem authoring tools (`write_to_file`) to persist the complete, professional, unabridged technical specification directly to physical disk at:
- Primary Canonical Deliverable:
  `D:/__CoChem/.docs/task5_scope_and_research_feasibility_analysis.md`
- Scratch Mirror Target:
  `C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_scope_and_research_feasibility_analysis.md`
- Swarm State Synchronization:
  Atomically update `D:/__CoChem/__agentic/swarm_state.json` and mirror to `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` recording:
  ```json
  {
    "agent_name": "cochem-scribe",
    "timestamp": "<CURRENT_ISO8601_TIMESTAMP>",
    "status": "COMPLETED",
    "task": "Task 5.1.1: Analyzed Level 1 Task 5 scope and research feasibility context for Chunk 17 Method Matrix v4.1 implementation",
    "wbs_level": "Level 3 Technical Feasibility Analysis",
    "provenance_tags_enforced": true,
    "anti_spoofing_compliance": true,
    "artifacts_produced": [
      "D:/__CoChem/.docs/task5_scope_and_research_feasibility_analysis.md",
      "C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_scope_and_research_feasibility_analysis.md"
    ],
    "sha256_checksum": "<COMPUTED_SHA256>"
  }
  ```

================================================================================
CRITICAL DIRECTIVE 3: FINAL AUDIT TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a structured final text report in your terminal response.
Your report MUST start with `[SCRIBE REPORT]` and MUST conclude with a dedicated `[VERIFICATION & HANDOFF SUMMARY]` section detailing:
1. Verdict status (`SUCCESS` or `FAILURE`).
2. Exact absolute and relative file paths modified or created on disk.
3. Physical byte count and line count of each modified file.
4. Cryptographic SHA-256 hash of each modified file.
5. Executive summary of the 4 structural pillars of the Task 5 scope and research feasibility analysis.
6. Formal handoff notice for `cochem-sdp-manager`, `cochem-audit`, and `adversary` for WBS decomposition and asymmetric verification.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate mocks, stubs, dummy loops, and fake data structures.
- Do NOT use `NotImplementedError` or empty `pass` blocks as dead-end stubs.
- Do NOT use synthetic array generators (`np.zeros`, `np.ones`, `np.eye`) to fake state tensors or coordinate matrices.
- Do NOT use shortcut tag-appending (e.g., `[AUDITOR FIX REQUIRED]`); deliver complete, production-grade architectural specifications.
- All atomic and isotopic masses MUST be dynamically retrieved via `from mendeleev import element`.
```

---

## 3. Pre-Flight Verification & Ledger Synchronization

- **Execution Agent:** `cochem-scribe` (Lead Technical Writing & Specification Analysis)
- **JSON Prompt Target:** [`d:\__CoChem\__agentic\.scripts\prompts\5.1.1_prompt.json`](file:///d:/__CoChem/__agentic/.scripts/prompts/5.1.1_prompt.json)
- **Scratch Target:** [`task5_1_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_1_1_dispatch_prompt.md)
- **Governance Alignment:** Method Matrix v4.1, IEEE 830-1998, PMBOK 7th Edition, Anti-Spoofing Protocol v4.
- **Audit Mandate:** Ready for sequential asymmetric audit by `cochem-audit` and `adversary`.
