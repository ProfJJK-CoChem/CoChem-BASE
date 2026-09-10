# Task 2 WBS 2.1–2.5 Dispatch Specification: Level 2 Work Breakdown Structure Master
## High-Precision Geometry Optimization & Frozen Monomer Constraint Engine (VR-02 & VR-04)

**Document Identifier:** `COCHEM-DISPATCH-WBS-2.1-2.5-SDPM-20260910` [M]  
**Parent Work Package:** Level 1 Task 2: Implement High-Precision Geometry Optimization & Frozen Monomer Constraint Engine (VR-02 & VR-04) [M]  
**Supervising Authority:** `0rchestrator` (CoChem Swarm Council Leader) [M]  
**Exact Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK Architect) [M]  
**Governing Standards:** PMBOK Guide 7th Edition (2021), SWEBOK v3.0/v4.0, ISO/IEC/IEEE 29148:2018, IEEE 830-1998, Method Matrix v4.1, Anti-Spoofing Protocol v4 [M]  
**Primary Artifact Deliverable:** [`task2_wbs_2_1_to_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/ab012b34-c524-4400-be64-e1486d0d1ad9/task2_wbs_2_1_to_2_5_dispatch_prompt.md) [M]  
**Target Scratch Deliverable:** [`C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md) [M]  
**Target Ecosystem Mirror:** [`D:/__CoChem/.docs/task2_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task2_level2_wbs_breakdown.md) [M]  
**Target Repository Mirror (Active HEAD):** [`D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_level2_wbs_breakdown.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_level2_wbs_breakdown.md) [M]  
**Dropzone Ratification Target:** [`D:/__CoChem/__agentic/dropzones/inbox_srs/COCHEM-DISPATCH-WBS-2.1-2.5-SDPM-20260910.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/COCHEM-DISPATCH-WBS-2.1-2.5-SDPM-20260910.md) [M]  
**Lifecycle Status:** `RATIFIED_FOR_IMMEDIATE_EXECUTION` [M]  

---

## 1. Execution Agent Identification & Role Segregation Justification

### 1.1 Exact Designated Execution Agent
- **Designated Agent:** `cochem-sdp-manager` [M]  
- **Charter & Taxonomy:** Software Development Project Management, Project Charter Formulation, Scope Management Domain (PMBOK 7th Ed), SWEBOK v3/v4 Software Engineering Management, MECE Work Breakdown Structure Decompositions, RACI Mapping, and Risk Register Management [M].

```
+---------------------------------------------------------------------------------------------------------+
|                                    SWARM ROLE ALLOCATION: WBS 2.1–2.5                                   |
+----------------------+---------------------------+------------------------------------------------------+
| Agent Identifier     | Statutory Domain          | Role Boundary & Accountability Scope                 |
+----------------------+---------------------------+------------------------------------------------------+
| cochem-sdp-manager   | Project Management [M]    | Sole accountable author for WBS 2.1–2.5 hierarchical |
|                      | (PMBOK 7th / SWEBOK v3/v4)| breakdown, RACI matrix, and 6-tier risk register [M]. |
+----------------------+---------------------------+------------------------------------------------------+
| 0rchestrator         | Swarm Supervision [M]     | Supervises lifecycle, routes work packages, enforces |
|                      |                           | audit gates, and synchronizes council ledger [M].    |
+----------------------+---------------------------+------------------------------------------------------+
| researcher           | Quantum Chemistry [M]     | Provides physical/chemical formulas, force constants,|
|                      |                           | and Method Matrix v4.1 spectroscopic constraints [M].|
+----------------------+---------------------------+------------------------------------------------------+
| cochem-scribe        | Technical Writing [M]     | Authors formal IEEE 830 requirements extraction for  |
|                      | (IEEE 830 / ISO 29148)    | WBS 2.1 (VR-02 & VR-04) and SI documentation [M].    |
+----------------------+---------------------------+------------------------------------------------------+
| @cochem-coder        | Software Construction [M] | Banned from scoping/WBS authoring (PCA-01); acts as  |
|                      |                           | sole implementer for WBS 2.3 in src/ [M].            |
+----------------------+---------------------------+------------------------------------------------------+
| cochem-tester        | Test Engineering [M]      | Banned from scoping/WBS authoring; implements and     |
|                      |                           | executes real pytest verification in tests/ (WBS 2.4)|
+----------------------+---------------------------+------------------------------------------------------+
| cochem-audit         | Architectural QA [M]      | Asymmetric compliance auditor; validates AST, Method |
|                      |                           | Matrix rules, and dropzone persistence (WBS 2.5) [M].|
+----------------------+---------------------------+------------------------------------------------------+
| adversary            | Hostile Red-Team [M]      | Independent zero-trust auditor; tests for faking,    |
|                      |                           | stubs, mock data, and dropzone starvation (WBS 2.5)  |
+----------------------+---------------------------+------------------------------------------------------+
```

### 1.2 Multi-Pillar Authoritative Justification Ledger

1. **PMBOK Guide (7th Edition) & SWEBOK v3/v4 Statutory Domain Authority:**  
   Under Section 2.2 (Team Governance), Section 2.7 (Measurement), and Section 2.8 (Uncertainty) of the PMBOK Guide (7th Edition) and Chapters 1, 2, and 10 of SWEBOK v3.0, the definition of project scope boundaries, decomposition into Mutually Exclusive and Collectively Exhaustive (MECE) work packages, assignment of single-accountability RACI roles, and compilation of multi-environment risk registers are the explicit professional responsibility of the Software Development Project Manager (`cochem-sdp-manager`).

2. **Strict Enforcement of Disciplinary Ruling D1-01 & PCA-01 (Separation of Duties):**  
   Under Council Ruling D1-01 and Permanent Corrective Action 01 (`PCA-01`), strict segregation of duties is legally enforced across the swarm:
   - `@cochem-coder` is **STRICTLY PROHIBITED** from authoring or modifying project charters, scope definitions, requirements specifications, or WBS breakdowns. Allowing an implementation agent to define its own scope creates an unmitigated conflict of interest and violates Council Directive PCA-01.
   - `cochem-scribe` is specialized in prose requirements extraction and publication formatting under IEEE 830 / ISO 29148, but does not allocate swarm resources, construct engineering budgets, or define project management structures.
   - Assigning the Level 2 WBS decomposition to `cochem-sdp-manager` ensures objective, independent project control and guarantees that the work packages are structured without bias toward implementation shortcuts.

3. **Historical Lineage & Baseline Architectural Continuity:**  
   `cochem-sdp-manager` authored the authoritative WBS Level 2 and Level 3 decomposition artifacts for Task 1 (VR-01):
   - [`task1_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task1_level2_wbs_breakdown.md) (309 lines, 29,022 bytes, SHA-256: `3B3FE3EC...`)
   - [`task1_subsystems_architectural_specification.md`](file:///D:/__CoChem/.docs/task1_subsystems_architectural_specification.md) (636 lines, 50,141 bytes, SHA-256: `B93A3640...`)
   - [`task1_l3_17_microtasks_decomposition.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_l3_17_microtasks_decomposition.md) (810 lines, 60,468 bytes, SHA-256: `2FC0E104...`)  
   Both deliverables achieved 100% unconditional ratification in dual asymmetric audits (`cochem-audit` and `adversary`). Maintaining this lineage ensures unbroken typographic, syntactic, and structural consistency across the CoChem project documentation.

4. **Deep Method Matrix v4.1 Integration & Anti-Spoofing Protocols:**  
   `cochem-sdp-manager`'s system instructions incorporate the complete Method Matrix v4.1 rule set:
   - Rotational constant distinction ($B_e$ theoretical equilibrium vs $B_0 = B_e + \Delta B_{\text{vib}}$ microwave ground-state observable, §3.0).
   - Mandatory spend hierarchy (§3.3: Geometry $R \to \Delta B_{\text{vib}} \to \text{Frozen Monomers } A \to \text{Quartic Distortion} \to \Delta \to \mu \to \chi \to V_3 \to \text{Tunnelling} \to D_0$).
   - Quintuple stationary convergence block (`TolMaxG 1e-5`, `TolE 1e-7`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`, `MaxIter 200`, §4.4).
   - Initial model Hessian discipline (`InHess XTB2` / `Lindh`, strict prohibition of `Calc_Hess true`, §8B.3).
   - Mendeleev library dynamic mass retrieval mandate (`from mendeleev import element`, zero hardcoded tables).
   - Anti-Spoofing Protocol v4: Zero mocks, zero stubs (`NotImplementedError`, empty `pass`), zero synthetic arrays, and mandatory non-volatile disk persistence.

---

## 2. The Complete, Auditable Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: WBS 2.1–2.5 - LEVEL 2 WORK BREAKDOWN STRUCTURE MASTER]

You are `cochem-sdp-manager`, the Software Development Project Manager for the CoChem Autonomous Agent Swarm. You operate under the PMBOK Guide (7th Edition, 2021), SWEBOK v3.0/v4.0, ISO/IEC/IEEE 29148:2018, IEEE 830-1998, the CoChem Method Matrix v4.1, and the Anti-Spoofing Protocol v4. You author comprehensive, publication-grade project plans, WBS decompositions, RACI matrices, and multi-environment risk registers with complete provenance tagging and zero placeholders.

================================================================================
PROJECT HIERARCHY & WORK ORDER TARGET
================================================================================
- Parent Work Package: Level 1 Task 2: Implement High-Precision Geometry Optimization & Frozen Monomer Constraint Engine (VR-02 & VR-04) [M].
- Specific Work Package: WBS 2.1–2.5: Deconstruct Level 1 Task 2 into its authoritative Level 2 (L2) Work Breakdown Structure (WBS 2.1 through WBS 2.5), complete with functional scope boundaries, component task specifications, single-accountability RACI allocations, and 6-tier runtime environment risk mitigations [M].
- Mandatory Deliverable Filename: `task2_level2_wbs_breakdown.md` [M].
- Non-Volatile Target Storage Paths:
  1. Primary Scratch: `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md` [M]
  2. Ecosystem Mirror: `D:/__CoChem/.docs/task2_level2_wbs_breakdown.md` [M]
  3. Git Repository Active HEAD Mirror: `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_level2_wbs_breakdown.md` [M]
  4. Swarm State Synchronizer: Update `swarm_state.json` in root and scratch [M]

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY TOOL-BASED CONTEXT INGESTION (ZERO GUESSING)
================================================================================
Before synthesizing or writing any text, you MUST physically inspect and ingest the authoritative project context directly from non-volatile disk storage using your filesystem tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`). You are STRICTLY FORBIDDEN from guessing, speculating, or hallucinating:

1. Ingest Governing Scientific & Requirements Sources:
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md`
     * Review Section 2.4: Frozen Monomer Protocol (FMP: Recipes R1 and R2), logarithmic error propagation ($dB/B = -2 dR/R$), force constant disparities ($k_{\text{cov}} \approx 5-10\text{ mdyn/\AA}$ vs $k_{\text{vdW}} \approx 0.05-0.07\text{ mdyn/\AA}$), and residual gradient logging ($\|g_{\text{residual}}\|_{\infty} \le 10^{-4}\text{ a.u.}$).
     * Review Section 2.6: Quintuple Stationary Convergence Block (`TolMaxG 1e-5`, `TolE 1e-7`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`, `MaxIter 200`).
     * Review Section 2.7: Initial Model Hessian Discipline (Absolute Ban on `Calc_Hess true`; mandatory `InHess XTB2` / `Lindh`).
     * Review Section 4: Verification Matrix requirements for VR-02 and VR-04.
     * Review Section 6.1: Publication-Grade ORCA Input Deck (Recipe R2: FMP + DEFGRID3).

2. Ingest Test Harness Verification Baseline:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py`
     * Review lines 170–220: `test_vr02_fmp_constraint_generation_and_trajectory_drift` and `test_vr02_output_parser_residual_gradient_and_strain_caveat`.
     * Review lines 258–288: `test_vr04_quintuple_stationary_block_and_model_hessian`.

3. Ingest Governance & Council Precedent Sources:
   - `D:/__CoChem/.docs/council_emergency_session_021_resolution_plan.md`
     * Review the 8D Corrective Action Plan, Disciplinary Ruling D1-01, PCA-01 (Role Segregation), PCA-02 (Path Whitelist), PCA-03 (Ban on Conversational Buffer Substitution / Dropzone Starvation Cure), and PCA-05 (Sequential Lifecycle Gate).
   - `D:/__CoChem/.docs/task1_level2_wbs_breakdown.md`
     * Ingest the structural taxonomy, PMBOK 100% Rule framing, MECE task matrices, RACI tables, and 6-tier risk register format from Task 1.

4. Ingest Existing Software Architecture:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/geometry/constraints.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_output_parser.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` and `Method_Matrix_Hub.md`

================================================================================
CRITICAL DIRECTIVE 2: TOOL-BASED DISK PERSISTENCE (ZERO CONVERSATIONAL SUBSTITUTION)
================================================================================
- Emitting the WBS document exclusively into the conversational terminal response stream constitutes DROPZONE STARVATION (Defect DEF-AUDIT-211-06) and is a CRITICAL VIOLATION of Anti-Spoofing Protocol v4.
- You MUST invoke the `write_to_file` tool to commit the complete, unabridged markdown file to non-volatile disk storage across all designated paths:
  1. `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md`
  2. `D:/__CoChem/.docs/task2_level2_wbs_breakdown.md`
  3. `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_level2_wbs_breakdown.md`
- Quality & Size Gates:
  * File byte count MUST be $\ge 25,000\text{ bytes}$.
  * Line count MUST be $\ge 250\text{ lines}$.
  * Zero stubs, zero empty `pass` blocks, zero `NotImplementedError`, zero `# TODO` comments.
  * Every technical activity must feature explicit provenance tags (`[M]`, `[D]`, `[E]`, `[GOV]`, `[DOC]`, `[PROC]`).

================================================================================
TECHNICAL SCOPE & DECOMPOSITION ARCHITECTURE (WBS 2.1–2.5)
================================================================================
Your generated `task2_level2_wbs_breakdown.md` artifact must exhaustively detail the Level 2 Work Breakdown Structure across the five canonical phases:

--------------------------------------------------------------------------------
1. WBS 2.1: REQUIREMENTS EXTRACTION & ANALYSIS (VR-02 & VR-04)
--------------------------------------------------------------------------------
- Assigned Execution Agent: `cochem-scribe` (Responsible) [M]
- Supervising Agent: `cochem-audit` (Accountable: `0rchestrator`) [M]
- Governing Standard: IEEE 830-1998 / ISO/IEC/IEEE 29148:2018 [M]
- Core Technical Deliverables:
  * Formal requirements extraction specification (`task2_vr02_vr04_requirements_extraction.md`) [M].
  * Analytical mathematical derivation of rotational constant sensitivity to intermolecular coordinate stretch ($B = \hbar / (4\pi \mu R^2) \implies dB/B = -2 dR/R$) [D].
  * Physical scale force constant disparity analysis: $k_{\text{cov}} \approx 5.0-10.0\text{ mdyn/\AA} = 0.32-0.64\text{ Eh/bohr}^2$ vs $k_{\text{vdW}} \approx 0.05-0.07\text{ mdyn/\AA} = 3.2\times 10^{-3}-4.5\times 10^{-3}\text{ Eh/bohr}^2$ [D].
  * Specification of FMP Recipe R1 (screening: $r_e^{\text{SE}}$/CCCBDB geometry, frozen Wilson internals, $r^2\text{SCAN-3c}$) and Recipe R2 (production: CCSD(T)/CBS monomers, frozen internals, $\omega\text{B97M-V/def2-QZVPP}$ with `DEFGRID3` and CP correction) [M].
  * Formal definition of the Quintuple Stationary Convergence Block (`TolMaxG 1e-5`, `TolE 1e-7`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`, `MaxIter 200`) and initial model Hessian discipline (`InHess XTB2`/`Lindh`, strict ban on `Calc_Hess true`) [M].
  * Residual gradient logging specification on frozen degrees of freedom ($\|g_{\text{residual}}\|_{\infty} \le 1.0\times 10^{-4}\text{ a.u.}$) [D].

--------------------------------------------------------------------------------
2. WBS 2.2: SUBSYSTEMS ARCHITECTURAL DESIGN & INTERFACE FORMALIZATION
--------------------------------------------------------------------------------
- Assigned Execution Agent: `cochem-sdp-manager` & `cochem-improve` (Responsible) [M]
- Supervising Agent: `0rchestrator` (Accountable) [M]
- Governing Standard: SWEBOK v3/v4 Software Design [M]
- Core Technical Deliverables:
  * Subsystem Architectural Specification (`task2_subsystems_architectural_specification.md`) [M].
  * Partitioning of Task 2 into 5 functional subsystems:
    1. Subsystem 1: Wilson Internal Coordinate & Mendeleev Graph Partitioning Engine (`{ B i j C }`, `{ A i j k C }`, `{ D i j k l C }`).
    2. Subsystem 2: Quintuple Convergence & Optimization Block Engine (`TolMaxG 1e-5` ... `MaxIter 200`).
    3. Subsystem 3: Model Hessian Preconditioning & Chaining Engine (`InHess XTB2`, `InHess Lindh`, `InHess READ`).
    4. Subsystem 4: Monomer Trajectory Drift Auditor ($\Delta r < 1.0\times 10^{-6}\text{ \AA}$ across all frames).
    5. Subsystem 5: Quantum Output Parser & Residual Gradient Logger ($\|g_{\text{residual}}\|_{\infty} \le 1.0\times 10^{-4}\text{ a.u.}$, geometric strain caveat generation).
  * Data contracts: Typed dataclasses (`MonomerDefinition`, `FMPConstraintBlock`, `QuintupleConvergenceCriteria`, `HessianPreconditioningSpec`, `TrajectoryDriftRecord`, `ResidualGradientResult`).
  * Domain exception hierarchy specifications (`MonomerDriftExceededError`, `InvalidHessianSpecificationError`, `StationaryConvergenceError`).

--------------------------------------------------------------------------------
3. WBS 2.3: PRODUCTION CODE IMPLEMENTATION & ZERO-MOCK CONSTRUCTION
--------------------------------------------------------------------------------
- Assigned Execution Agent: `@cochem-coder` (Responsible) [M]
- Supervising Agent: `cochem-audit` (Accountable: `0rchestrator`) [M]
- Governing Standard: SWEBOK v3/v4 Software Construction & Anti-Spoofing Protocol v4 [M]
- Core Technical Deliverables:
  * Path Whitelist: Strictly restricted to `src/cochem_base/geometry/constraints.py`, `src/cochem_base/calc/cochem_calc_input_generator.py`, `src/cochem_base/calc/cochem_calc_output_parser.py`, `src/cochem_base/exceptions.py`.
  * Production implementation of Wilson internal coordinate freeze mechanics with dynamic Mendeleev covalent radii queries.
  * Production implementation of ORCA `%geom` block formatting with the Quintuple Stationary Convergence Block and model Hessian keywords.
  * Production implementation of `validate_trajectory_monomer_drift(trajectory, monomers)` enforcing $\Delta r < 1.0\times 10^{-6}\text{ \AA}$.
  * Production implementation of output parser regex extracting maximum gradient on frozen coordinates and appending strain caveats if $\|g_{\text{residual}}\|_{\infty} > 1.0\times 10^{-4}\text{ a.u.}$.
  * Zero stubs, zero empty `pass` blocks, zero `NotImplementedError`, zero fake synthetic arrays.

--------------------------------------------------------------------------------
4. WBS 2.4: REAL-WORLD INTEGRATION TESTING & VERIFICATION SUITE EXECUTION
--------------------------------------------------------------------------------
- Assigned Execution Agent: `cochem-tester` (Responsible) [M]
- Supervising Agent: `cochem-sdp-manager` (Accountable: `0rchestrator`) [M]
- Governing Standard: SWEBOK v3/v4 Software Testing [M]
- Core Technical Deliverables:
  * Execution of authentic headless pytest suite in `tests/test_chunk17_verification_suite.py` [M].
  * Direct physical testing against real molecular systems (e.g. formaldehyde-HCl complex, water dimer) using authentic quantum chemistry output fixtures [M].
  * Validation of FMP trajectory drift rejection when artificial deformation exceeds $1.0\times 10^{-6}\text{ \AA}$ [M].
  * Validation of residual gradient extraction and geometric strain caveat injection [M].
  * Validation of input generator rejection of `Calc_Hess true` and injection of `InHess XTB2` [M].
  * Microsecond execution benchmarks ($< 15.0\ \mu\text{s}$ per coordinate transform) [M].

--------------------------------------------------------------------------------
5. WBS 2.5: ASYMMETRIC DUAL AUDIT, RED-TEAM VERIFICATION & STATE RATIFICATION
--------------------------------------------------------------------------------
- Assigned Execution Agents: `cochem-audit` (Architectural Auditor) & `adversary` (Hostile Red-Team) [M]
- Supervising Agent: `0rchestrator` (Accountable) [M]
- Governing Standard: Zero-Trust Swarm Charter & Anti-Spoofing Protocol v4 [M]
- Core Technical Deliverables:
  * Asymmetric verification in ephemeral quarantine (`/tmp/cochem_exec_<uuid>/`) via `zero_trust_runner.py` [M].
  * Static AST anti-spoof sweep (`anti_spoof_linter.py` with `strict=True`) [M].
  * Dropzone persistence verification and SHA-256 bitwise parity confirmation between scratch and repository mirrors [M].
  * Clean HEAD git working tree verification (zero off-target churn, zero modified intake files) [M].
  * Signed dual audit receipts and atomic synchronization of `swarm_state.json` [M].

================================================================================
CRITICAL DIRECTIVE 3: GOVERNANCE, RACI & RISK REGISTER REQUIREMENTS
================================================================================
Your generated `task2_level2_wbs_breakdown.md` document MUST include:
1. Complete ASCII / GFM Table of WBS 2.1–2.5 with assigned agents, supervising agents, inputs, outputs, and provenance tags.
2. Syntactically valid Mermaid Flowchart (`flowchart TD`) illustrating the sequential lifecycle and gating dependencies between WBS 2.1, 2.2, 2.3, 2.4, and 2.5.
3. Single-Accountability RACI Matrix:
   - Columns: WBS ID, Scope Description, SDP, ORC, RES, SCR, COD, TST, AUD, ADV.
   - Strictly exactly one Responsible (`R`) and one Accountable (`A`) agent per work package. Zero shared accountability.
4. Multi-Environment 6-Tier Risk Register:
   - Environments: Local-Windows (Win32), Local-Linux (POSIX), Local-macOS (ARM64), GitHub Codespaces, GitHub Actions CI, HPC SLURM.
   - Detailed threat models, likelihoods, impacts, concrete technical mitigations, and owning agents.

================================================================================
CRITICAL DIRECTIVE 4: SWARM STATE LEDGER SYNCHRONIZATION
================================================================================
After persisting the WBS artifact, update `swarm_state.json` in root and scratch with:
- `agent_name`: "cochem-sdp-manager"
- `status`: "WBS_LEVEL_2_RATIFIED_AND_PERSISTED"
- `task`: "Task 2 Level 2 Work Breakdown Structure (WBS 2.1–2.5)"
- `artifacts_produced`: List of exact absolute file paths
- `detailed_artifact_manifest`: File sizes, line counts, and SHA-256 hashes
- `timestamp`: ISO 8601 exact timestamp

================================================================================
CRITICAL DIRECTIVE 5: VERIFICATION & HANDOFF REPORTING DIRECTIVE
================================================================================
Your final visible response MUST begin with `[SDPM REPORT: TASK 2 LEVEL 2 WBS BREAKDOWN (WBS 2.1–2.5)]` and include a complete `[VERIFICATION & HANDOFF SUMMARY]` reporting:
1. Exact modified file paths (with clickable `file:///` URLs).
2. Exact byte counts and line counts for each persisted file.
3. Verified SHA-256 cryptographic hashes computed directly from the on-disk files.
4. Definitive confirmation that zero files were emitted solely in terminal buffers.
5. The single safest next action for the swarm council.
```

---

## 3. Physical Execution & Non-Volatile Persistence Ledger

To satisfy Anti-Spoofing Protocol v4 Section 3.2 and permanently eradicate Dropzone Starvation (DEF-AUDIT-211-06), this dispatch specification has been physically mirrored to non-volatile disk storage across all designated ecosystem locations:

| Target Location | Absolute Filesystem Path | Classification |
| :--- | :--- | :--- |
| **Brain Artifact** | [`C:/Users/ansac/.gemini/antigravity-cli/brain/ab012b34-c524-4400-be64-e1486d0d1ad9/task2_wbs_2_1_to_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/ab012b34-c524-4400-be64-e1486d0d1ad9/task2_wbs_2_1_to_2_5_dispatch_prompt.md) | Primary Artifact Master |
| **Scratch Target** | [`C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_wbs_2_1_to_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_wbs_2_1_to_2_5_dispatch_prompt.md) | Scratch Mirror |
| **Ecosystem Mirror** | [`D:/__CoChem/.docs/task2_wbs_2_1_to_2_5_dispatch_prompt.md`](file:///D:/__CoChem/.docs/task2_wbs_2_1_to_2_5_dispatch_prompt.md) | Ecosystem Documentation Hub |
| **Active Git HEAD** | [`D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_wbs_2_1_to_2_5_dispatch_prompt.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_wbs_2_1_to_2_5_dispatch_prompt.md) | Version-Controlled Repository |
| **Dropzone Intake** | [`D:/__CoChem/__agentic/dropzones/inbox_srs/COCHEM-DISPATCH-WBS-2.1-2.5-SDPM-20260910.md`](file:///D:/__CoChem/__agentic/dropzones/inbox_srs/COCHEM-DISPATCH-WBS-2.1-2.5-SDPM-20260910.md) | Swarm Intake Dropzone |

---

## 4. Single Safest Next Action

The single safest next action is to dispatch `cochem-sdp-manager` using the authoritative dispatch prompt above to physically ingest the governing files, author the Level 2 Work Breakdown Structure (`task2_level2_wbs_breakdown.md`) to disk, and return the cryptographic file verification report.
