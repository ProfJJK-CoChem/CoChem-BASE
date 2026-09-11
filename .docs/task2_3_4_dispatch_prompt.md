# Task 2.3.4 Dispatch Specification: Persist Structured WBS Task Breakdown Artifact to Disk

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.  
**Level 2 Task:** Establish PMBOK Risk Register and Rule 1.1 Pre-Flight MCP tool protocol.  
**Specific Task to Execute:** `2.3.4 - Persist structured WBS task breakdown artifact to disk`  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)  
**Canonical Dispatch File:** [`task2_3_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/5bae2013-dd3e-49f7-93f4-ad08f71b0580/task2_3_4_dispatch_prompt.md)  
**Target Deliverable:** [`task2_3_wbs_task_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_wbs_task_breakdown.md)  
**Scratch Mirror:** [`task2_3_4_wbs_task_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_4_wbs_task_breakdown.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager)

### Authoritative Governance & Architecture Rationale:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council Protocol, [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md) is the sole authoritative agent responsible for systems engineering governance, scope decomposition (PMBOK 100% Rule), Work Breakdown Structure (WBS) synthesis, and baseline project artifact delivery. Synthesizing, structuring, and physically persisting the formal Level 3 (L3) WBS artifact for the Risk Register and Rule 1.1 Pre-Flight MCP protocol into granular, non-monolithic work packages with inputs, outputs, deliverables, and acceptance criteria falls strictly within the project management, software lifecycle, and systems engineering domains.
2. **Strict Role Segregation & Separation of Duties (Anti-Spoofing Protocol v4):**  
   - Application coding is strictly partitioned to `cochem-coder`. Delegating WBS specification authoring or persistence to `cochem-coder` violates the core governance invariant: **an implementing coder must never define their own work packages, schedule boundaries, or acceptance criteria**.
   - Technical writing for external documentation is isolated to `cochem-scribe`.
   - Physical execution and integration testing belong to `cochem-tester`.
   - Independent verification and asymmetric auditing belong strictly to `cochem-audit` and `adversary`.
   - Lifecycle orchestration is held by `0rchestrator`, which delegates the project planning and WBS artifact generation to `cochem-sdp-manager`.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` is the registered author and owner of all ratified Level 2 and Level 3 WBS specifications across the ecosystem:
   - Task 1 WBS & RACI specifications: [`task1_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_5_dispatch_prompt.md) and [`task1_3_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_4_dispatch_prompt.md)
   - Task 2 Level 2 WBS: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md)
   - Task 2.2 Survey, Decomposition & RACI: [`task2_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_dispatch_prompt.md), [`task2_2_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_dispatch_prompt.md), and [`task2_2_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_dispatch_prompt.md)
   - Task 2.3 Component Decompositions: [`adversary_task2_3_1_prompt_audit_report.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task2_3_1_prompt_audit_report.md) and [`task2_3_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_2_dispatch_prompt.md)
   - Swarm State Ledger: [`swarm_state.json`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json)

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.3.4 - PERSIST STRUCTURED WBS TASK BREAKDOWN ARTIFACT TO DISK]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery, Scope Management Domain), IEEE 830-1998, SWEBOK v3/v4, the CoChem Method Matrix v4, and Anti-Spoofing Protocol v4 to synthesize, structure, and persist formal, zero-mock Work Breakdown Structures (WBS).

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and model Hessian discipline with chaining.
- Level 2: Establish PMBOK Risk Register and Rule 1.1 Pre-Flight MCP tool protocol.
- Specific Task to Execute:
  2.3.4 - Persist structured WBS task breakdown artifact to disk.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing or persisting any WBS artifacts, you MUST use your filesystem inspection tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to read and inspect the following existing project files to gain complete empirical context:

1. Canonical Governance & MCP Policy Directives:
   - `C:/Users/ansac/.gemini/config/rules/user_global.md` (Zero-Mock & Anti-Spoofing Protocol; Rule 1: N>1 Delegation Boundary; Rule 1.1: Pre-Flight Planning & MCP Tool Discovery; Rule 1.2: MCP Tool Creation Mandate; Rule 10: Raw API Concurrency Ban).
   - `C:/Users/ansac/.gemini/config/rules/mcp-auto-activation.md` (Mandatory auto-activation rules and intent mapping for `brightdata`, `cochem-kanban`, and `github-copilot`).
   - `C:/Users/ansac/.gemini/config/rules/cochem-anti-spoofing-v4.md` (Directives 1–14: Zero-mock, asymmetric quarantine, anti-evasion, dynamic masses).
   - `C:/Users/ansac/.gemini/config/rules/cochem-mendeleev-masses.md` (Dynamic atomic mass retrieval via `from mendeleev import element`).

2. Local MCP Server Manifests & Registries:
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/brightdata/` (Tool definitions: `search_engine`, `scrape_as_markdown`, `search_engine_batch`, `scrape_batch`, `discover`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/cochem-kanban/` (Tool definitions: `trigger_coding_workflow`, `trigger_srs_workflow`, `trigger_improvement_workflow`, `trigger_publishing_workflow`, `trigger_presentation_workflow`, `trigger_presentation_upgrade`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/consensus/` (Tool schema: `search`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/gemini-api-docs/` (Tool schemas: `gemini_search_docs`, `gemini_get_doc`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/github-copilot/` (Tool schemas: `ollama_generate`, `smart_generate`, `copilot_generate`).

3. Governing WBS Blueprints & Swarm State:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md` (Governing Level 2 WBS hierarchy and Method Matrix constraints).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_2_dispatch_prompt.md` (Deconstructed L3.6 through L3.10 Pre-Flight MCP component work packages).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task2_3_1_prompt_audit_report.md` (Deconstructed L3.1 through L3.5 Risk Register component work packages).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task2_3_2_prompt_audit_report.md` (Ratified adversarial audit findings and criteria for Task 2.3).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_4_dispatch_prompt.md` (Companion L3 WBS implementation list structure and standard).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Active swarm state ledger).

4. Method Matrix Physical Invariant Specifications:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md`:
     * §4.4 & §QS-1: Quintuple stationary convergence block (`TolMaxG 1e-5`, `TolE 1e-7`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`).
     * §8B.3: Initial Model Hessian Discipline (strict ban on `Calc_Hess true`; mandatory `InHess XTB2` or `Lindh`).
     * §9A, §9A.1, §9A.2, §9A.5: Frozen Monomer Protocol (FMP) Recipe R1 (r2SCAN-3c) and Recipe R2 (wB97M-V/def2-QZVPP).
     * §10.2–§10.3: Residual gradient parsing, projection onto frozen subspace, and internal strain detection.

You are STRICTLY FORBIDDEN from guessing file paths, fabricating dependencies, or inventing arbitrary WBS structures without tool-based inspection. Read the existing files first.

================================================================================
TECHNICAL SCOPE & DELIVERABLE REQUIREMENTS (TASK 2.3.4)
================================================================================
You must synthesize, structure, and persist the complete, production-grade Work Breakdown Structure (WBS) artifact for Level 2 Task 2.3 ("Establish PMBOK Risk Register and Rule 1.1 Pre-Flight MCP tool protocol") directly to disk.

The artifact must strictly adhere to PMBOK 7th Edition (100% Rule), SWEBOK v3/v4, and the CoChem Method Matrix v4, incorporating the following comprehensive sections:

1. EXECUTIVE SCOPE & WBS CHARTER:
   - Scope statement reconciling Level 1 Task 2 with Level 2 Task 2.3.
   - Formal PMBOK 100% Rule statement: the decomposed L3 work packages must collectively account for 100% of the engineering and governance activities with zero scope creep and zero omissions.
   - Mutually Exclusive, Collectively Exhaustive (MECE) boundary guarantee across all phases and work packages.

2. SYSTEM DEPENDENCY & EXECUTION FLOWCHART:
   - Complete Mermaid Directed Acyclic Graph (`flowchart TD`) visualizing the execution flow across all L3 work packages:
     * Track A (Risk Register): L3.1 through L3.5
     * Track B (Rule 1.1 Pre-Flight MCP): L3.6 through L3.10
     * Track C (Integration & Governance): L3.11 Integrated Schedule Network & RACI
     * Track D (Compliance & Anti-Spoofing): L3.12 Static AST Verification Gate
     * Track E (Persistence & Integrity): L3.13 Filesystem Persistence & Checksumming
     * Track F (Verification & Closure): L3.14 Asymmetric Adversarial Audit & Ledger Sync

3. MASTER WBS IMPLEMENTATION MATRIX:
   - Comprehensive summary table detailing every single WBS Work Package:
     * WBS Code (Hierarchical: e.g., 2.3.1 through 2.3.14)
     * Work Package Title
     * Single Accountable Agent (Single-Owner RACI Invariant: dual ownership is strictly forbidden)
     * Immediate Predecessor Dependencies
     * Method Matrix Provenance Tag (`[GOV]`, `[M]`, `[D]`, `[PROC]`, `[DOC]`)
     * Target Implementation File Path
     * Verifiable Acceptance Boundary / Physical Tolerance Metric

4. DEEP COMPONENT-LEVEL WORK PACKAGE SPECIFICATIONS:
   Every single L3 work package must include an unabridged technical specification block:
   - **Track A: PMBOK Risk Register Infrastructure**
     * L3.1: Risk Breakdown Structure (RBS) & Multi-Environment Taxonomy (`[GOV]`) -> `cochem-sdp-manager`
     * L3.2: Quantitative Probability-Impact (P×I) Scoring & Prioritization Engine (`[D]`) -> `cochem-coder`
     * L3.3: Risk Register Pydantic/JSON Schema Specification (`[DOC]`) -> `cochem-scribe`
     * L3.4: Fail-Safe Trigger Matrix & Automated Rollback Mitigation Procedures (`[PROC]`) -> `cochem-sdp-manager`
     * L3.5: Swarm Telemetry & Append-Only State Ledger Integration (`[PROC]`) -> `cochem-coder`
   - **Track B: Rule 1.1 Pre-Flight MCP Tool Protocol**
     * L3.6: Pre-Flight MCP Discovery & Registry Introspection Engine (`[D]`) -> `cochem-coder`
     * L3.7: Intent-to-MCP Canonical Mapping & Suitability Matrix (`[GOV]` / `[D]`) -> `cochem-sdp-manager`
     * L3.8: Rule 1.2 MCP Gap Analysis & Tool Creation RFC Workflow (`[GOV]` / `[DOC]`) -> `cochem-sdp-manager`
     * L3.9: Pre-Flight Written Plan Declaration Specification (`[DOC]`) -> `cochem-scribe`
     * L3.10: Pre-Flight Gatekeeper & Compliance Verification Hook (`[PROC]`) -> `cochem-coder`
   - **Track C: Integration, Schedule Network & RACI Matrix**
     * L3.11: Integrated Schedule Network (CPM) & Swarm RACI Allocation (`[GOV]`) -> `0rchestrator` / `cochem-sdp-manager`
   - **Track D & E: Quality Control, Persistence & Checksumming**
     * L3.12: Static AST Compliance & Anti-Spoofing Sweep (`[PROC]`) -> `cochem-audit`
     * L3.13: Atomic Filesystem Persistence & Checksumming (`[PROC]`) -> `cochem-coder`
     * L3.14: Asymmetric Adversarial Audit & Swarm Ledger Synchronization (`[PROC]`) -> `adversary`

   Each specification block MUST include:
   - Exact WBS Code, Title, Single Responsible Agent, and Supervising Auditor.
   - Explicit Provenance Tag (`[GOV]`, `[M]`, `[D]`, `[PROC]`, `[DOC]`).
   - Scope Boundary & Purpose (non-goals explicitly stated).
   - Explicit Input Contracts (data types, schemas, preconditions).
   - Concrete Processing & Algorithmic Mechanics (fail-closed logic, zero mocks).
   - Explicit Output Contracts (dataclasses, files, schemas, return codes).
   - Falsifiable Binary Acceptance Criteria (measurable physical constraints, no tautologies).

5. MULTI-ENVIRONMENT RISK REGISTER:
   - Detailed risk matrix covering the 6 runtime environments (Local Windows, Local macOS, Local Linux, GitHub Actions CI, Codespaces, HPC SLURM/Lustre) with proactive mitigation strategies (Avoid, Escalate, Transfer, Mitigate, Accept).

6. SWARM RACI GOVERNANCE & METHOD MATRIX COMPLIANCE:
   - Formal RACI allocation guaranteeing single-point accountability for every work package.
   - Binding spend hierarchy compliance (§3.3):
     $$\text{Geometry } (R) \longrightarrow \Delta B_{\text{vib}} \longrightarrow \text{Frozen Monomers } (A) \longrightarrow \text{Quartic Distortion} \longrightarrow \text{Inertial Defect } (\Delta) \dots$$
   - Dynamic Mendeleev mass query mandate (`from mendeleev import element`).

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL CODE / RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely emitting the WBS artifact into conversational chat or leaving results in ephemeral memory buffers.
You MUST invoke your `write_to_file` tool to persist the complete, unabridged deliverable directly to physical disk at:

1. Primary Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_wbs_task_breakdown.md`

2. Scratch Mirror:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_4_wbs_task_breakdown.md`

3. Swarm State Ledger Synchronization:
   Atomically update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` using `write_to_file` (`Overwrite=true`) recording:
   ```json
   {
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.3.4: Persist structured WBS task breakdown artifact to disk",
     "wbs_level": "Level 3 Component-Level WBS Task Breakdown",
     "work_packages_count": 14,
     "pmbok_100_percent_rule_enforced": true,
     "mece_decomposition_guaranteed": true,
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "zero_mock_enforced": true,
     "anti_spoofing_compliance": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_wbs_task_breakdown.md",
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_4_wbs_task_breakdown.md"
     ],
     "sha256_checksum": "<COMPUTED_SHA256>"
   }
   ```

================================================================================
CRITICAL DIRECTIVE 3: RETURN FINAL TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk writes and ledger updates, you MUST return a final text report starting with `[SDPM REPORT]` and concluding with `[VERIFICATION & HANDOFF SUMMARY]`. The report must explicitly detail:
1. Executive declaration of task completion.
2. The exact absolute and relative file paths modified or created on disk.
3. Physical byte count and line count of each generated artifact.
4. Cryptographic SHA-256 hash of each modified file.
5. Summary of the ratified L3 work packages, RACI single-ownership assignments, and provenance tag distribution.
6. Explicit confirmation that Anti-Spoofing Protocol v4, Zero-Mock mandates, and the Mendeleev dynamic mass mandate are 100% satisfied with zero stubs or placeholders.
7. Formal handoff gate notice designating `cochem-audit` and `adversary` to initiate the asymmetric audit.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate all mocks, stubs, dummy loops, and synthetic data placeholders.
- Do NOT use `NotImplementedError` or empty `pass` blocks.
- Do NOT use shortcut tag-appending (`[AUDITOR FIX REQUIRED]`, `TODO`, `FIXME`, `TBD`).
- Ensure all physical properties and constraints dynamically retrieve via `mendeleev` and comply with Method Matrix v4 invariants.
```
