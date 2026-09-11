# Task 2.3.2 Dispatch Specification: Decompose L2 Rule 1.1 Pre-Flight MCP Protocol into L3 Component Tasks

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and InHess Lindh / XTB2 preconditioning with chaining. [M]  
**Level 2 Task:** Establish PMBOK Risk Register and Rule 1.1 Pre-Flight MCP tool protocol. [GOV]  
**Specific Task to Execute:** `2.3.2 - Decompose L2 Rule 1.1 Pre-Flight MCP protocol into L3 component tasks (registry inspector, intent matrix, gap RFC, declaration schema, preflight linter)` [GOV]  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager) [GOV]  
**Canonical Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_2_dispatch_prompt.md` [GOV]  
**Target Deliverable:** `task2_3_2_preflight_mcp_breakdown.md` [GOV]  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager) [GOV]

### Authoritative Governance & Architecture Rationale:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under PMBOK 7th Edition (*Scope Management Domain*, *Planning Performance Domain*, and the *100% Rule*) and SWEBOK v3/v4 (*Software Requirements & Engineering Management*), decomposing Level 2 architectural policies into granular Level 3 (L3) work packages, defining component boundaries, authoring data schemas, and assigning single-owner RACI accountability is the exclusive domain of [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md).
2. **Strict Separation of Duties (Anti-Spoofing Protocol v4):**  
   - Application coding is strictly partitioned to `cochem-coder`. Coder agents are forbidden from authoring their own work packages, schedule boundaries, or acceptance criteria.
   - Documentation and technical writing are isolated to `cochem-scribe`.
   - Physical execution and integration testing belong to `cochem-tester`.
   - Asymmetric verification is reserved strictly for `cochem-audit` and `adversary`.
   - Lifecycle orchestration belongs to `0rchestrator`, which delegates project planning and WBS synthesis to `cochem-sdp-manager`.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` is the verified author and owner of preceding ratified WBS specifications physically verified on disk:
   - Level 2 Master Breakdown: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md) (SHA-256: `a7e21fbe86336cab8797d53564f942a3694c08ffb5ebdf9ecca39ac61a0fc687`) [M]
   - Method Matrix & Module Survey: [`task2_2_1_method_matrix_and_module_survey.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md) (SHA-256: `feadaf344402d3d208a5a190acda7eb44f500af91b8e836971a171dbe8bd32e4`) [M]
   - Component Implementation Decomposition: [`task2_2_2_l3_component_decomposition.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_l3_component_decomposition.md) (SHA-256: `cc7332f88c347d1f69265d8ac7565da61f9a476d3a6495623053b25930e9b508`) [M]
   - Active Swarm Ledger: [`swarm_state.json`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json) [M]

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.3.2 - DECOMPOSE L2 RULE 1.1 PRE-FLIGHT MCP PROTOCOL INTO L3 COMPONENT TASKS]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Systems View for Project Delivery, Scope Management Domain), IEEE 830-1998, SWEBOK v3/v4, the CoChem Method Matrix v4, and Anti-Spoofing Protocol v4 to synthesize, structure, and persist formal Work Breakdown Structures (WBS).

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and InHess Lindh / XTB2 preconditioning with chaining.
- Level 2: Establish PMBOK Risk Register and Rule 1.1 Pre-Flight MCP tool protocol.
- Specific Task to Execute:
  2.3.2 - Decompose L2 Rule 1.1 Pre-Flight MCP protocol into L3 component tasks (registry inspector, intent matrix, gap RFC, declaration schema, preflight linter).

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any WBS specifications or schemas, you MUST inspect the following project files on physical disk using your filesystem inspection tools:

1. Canonical Governance & MCP Policy Directives:
   - Notice on Platform Protection Boundary: Files in `C:/Users/ansac/.gemini/config/rules/` (`user_global.md`, `mcp-auto-activation.md`, `cochem-anti-spoofing-v4.md`) are automatically injected into your context environment via system rules. If reading raw disk contents directly, be advised that native read calls against `config/rules/*` trigger platform boundary restrictions. Refer to the active rules already provided in your instructions.

2. Local MCP Server Manifests & Registries:
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/brightdata/` (`discover.json`, `scrape_as_markdown.json`, `scrape_batch.json`, `search_engine.json`, `search_engine_batch.json`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/cochem-kanban/` (`trigger_coding_workflow.json`, `trigger_improvement_workflow.json`, `trigger_presentation_upgrade.json`, `trigger_presentation_workflow.json`, `trigger_publishing_workflow.json`, `trigger_srs_workflow.json`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/consensus/` (`search.json`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/gemini-api-docs/` (`gemini_search_docs.json`, `gemini_get_doc.json`).
   - `C:/Users/ansac/.gemini/antigravity-cli/mcp/github-copilot/` (`copilot_generate.json`, `copilot_models.json`, `copilot_status.json`, `ollama_generate.json`, `ollama_models.json`, `smart_generate.json`).

3. Governing WBS Blueprints & Swarm State:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md` (Governing Level 2 WBS hierarchy).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Active swarm state ledger).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` (Physical invariants: Recipe R1/R2, quintuple convergence, InHess preconditioning).

Fabricating file paths, dependencies, or component structures without empirical inspection is strictly prohibited.

================================================================================
TECHNICAL SCOPE & DELIVERABLE REQUIREMENTS (TASK 2.3.2)
================================================================================
Decompose the Level 2 Rule 1.1 Pre-Flight MCP protocol into five (5) granular, non-monolithic Level 3 (L3) work packages adhering to the PMBOK 100% Rule and MECE principles.

Every work package must include:
- Markdown checkboxes (`[ ]`)
- Explicit, falsifiable binary acceptance criteria
- A single responsible CoChem execution agent (enforcing the Single-Owner RACI Invariant)
- Provenance tags (`[GOV]`, `[M]`, `[D]`, `[PROC]`, `[DOC]`)
- Concrete technical activities, input prerequisites, and target deliverables:

1. **L3.6 - Pre-Flight MCP Discovery & Registry Introspection Engine** `[D]`
   - Target Deliverable: `src/cochem/mcp/registry_inspector.py`
   - Assigned Agent: `cochem-coder` (Accountable: `cochem-audit` / `0rchestrator`)
   - Core Scope: Programmatic inspector that scans tool manifests in `C:\Users\ansac\.gemini\antigravity-cli\mcp\<serverName>\`, parses JSON schemas for arguments, types, and constraints, identifies Eager versus Lazy registration modes, and generates an atomic manifest record (`.cache/mcp_manifest.json`) verifying tool accessibility before task execution.
   - Binary Acceptance Criteria:
     - [ ] 100% typed Python 3.10+ using Pydantic v2 models for schema validation.
     - [ ] Zero unfulfilled function blocks or empty pass statements.
     - [ ] Programmatic discovery returns complete tool definitions across brightdata, cochem-kanban, consensus, gemini-api-docs, and github-copilot.
     - [ ] Atomic disk persistence to `.cache/mcp_manifest.json` with cryptographic SHA-256 digest validation.

2. **L3.7 - Intent-to-MCP Canonical Mapping & Suitability Matrix** `[GOV]` / `[D]`
   - Target Deliverable: `docs/architecture/mcp_intent_matrix.md`
   - Assigned Agent: `cochem-sdp-manager` (in consultation with `cochem-scribe`) (Accountable: `0rchestrator` / `cochem-audit`)
   - Core Scope: Canonical mapping matrix connecting operational intents to mandatory tools (e.g., refactoring $\rightarrow$ `cochem-kanban:trigger_improvement_workflow`; coding cycles $\rightarrow$ `cochem-kanban:trigger_coding_workflow`; local generation $\rightarrow$ `github-copilot:ollama_generate`). Establishes anti-bypass directives prohibiting custom execution daemons when canonical tools exist.
   - Binary Acceptance Criteria:
     - [ ] Exhaustive mapping across 11 primary agent intents to registered MCP tools.
     - [ ] Explicit prohibition of custom loop-based daemons and ad-hoc background scripts.
     - [ ] Falsifiable criteria for tool suitability and invocation boundaries.
     - [ ] Strict alignment with Method Matrix v4.1 and Anti-Spoofing Directive v4.

3. **L3.8 - Rule 1.2 MCP Gap Analysis & Tool Creation RFC Workflow** `[GOV]` / `[DOC]`
   - Target Deliverable: `templates/MCP_Tool_RFC_Template.md` and `docs/procedures/mcp_gap_resolution.md`
   - Assigned Agent: `cochem-sdp-manager` (Accountable: `adversary` / `0rchestrator`)
   - Core Scope: Formalize the 4-step MCP Gap Protocol mandated by Rule 1.2:
     - Step 1 (Exhaustion Analysis): Programmatic verification that existing servers lack the required operational capability.
     - Step 2 (RFC Formulation): Draft standardized RFC detailing Server Name, Tool Name, Schema, Argument constraints, and Isolation boundaries.
     - Step 3 (Plan Declaration): Embed the proposed tool design into the written pre-flight plan.
     - Step 4 (Mandatory Human User Approval Gate): Suspend automatic execution and require explicit human user confirmation via `ask_question` prior to implementation.
   - Binary Acceptance Criteria:
     - [ ] Formal RFC Markdown template covering Server Name, Tool Name, Schema, and Isolation boundaries.
     - [ ] Complete procedural specification detailing all 4 steps of the gap analysis lifecycle.
     - [ ] Hard gate halting automatic execution if human user approval is denied.
     - [ ] Zero unapproved automated tool creations permitted.

4. **L3.9 - Pre-Flight Written Plan Declaration Specification** `[DOC]`
   - Target Deliverable: `templates/Pre_Flight_Declaration_Template.md` and `schemas/preflight_declaration_schema.json`
   - Assigned Agent: `cochem-scribe` (Accountable: `cochem-sdp-manager` / `0rchestrator`)
   - Core Scope: Formal specification and schema for the mandatory `[PRE-FLIGHT MCP DECLARATION]` section required in every task plan:
     - Planned operational steps breakdown.
     - Target MCP server designations and tool names.
     - Parameter schema conformance.
     - Method Matrix justification.
     - Authentic parameter and physical path validation.
   - Binary Acceptance Criteria:
     - [ ] Machine-readable JSON Schema conforming to Draft 2020-12 meta-schema with zero syntax errors.
     - [ ] Human-readable Markdown template providing field-level instructions for pre-flight planning.
     - [ ] Validation rules requiring explicit MCP server and tool name declaration.
     - [ ] Mandatory physical path and Method Matrix invariant citations.

5. **L3.10 - Pre-Flight Gatekeeper & Compliance Verification Hook** `[PROC]`
   - Target Deliverable: `src/cochem/governance/preflight_linter.py`
   - Assigned Agent: `cochem-coder` (Accountable: `cochem-audit` / `0rchestrator`)
   - Core Scope: Static validation gatekeeper (AST and structured parser) executed prior to subagent dispatch. Validates:
     - Presence of `[PRE-FLIGHT MCP DECLARATION]` in the active plan.
     - Concordance between declared tools and the inspected registry.
     - Strict non-usage of obsolete external orchestration scripts.
     - Adherence to N>1 delegation boundaries (zero subagents invoked within loops).
     - Deterministic exit codes:
       - `0`: `PREFLIGHT_PASS`
       - `1`: `PREFLIGHT_FAIL_MISSING_DECLARATION`
       - `2`: `PREFLIGHT_FAIL_UNKNOWN_TOOL`
       - `3`: `PREFLIGHT_FAIL_UNAPPROVED_TOOL`
       - `4`: `PREFLIGHT_FAIL_LOOP_DELEGATION`
       - `5`: `PREFLIGHT_FAIL_DEPRECATED_SCRIPT`
       - `6`: `PREFLIGHT_FAIL_SYNTAX_ERROR`
   - Binary Acceptance Criteria:
     - [ ] 100% typed Python 3.10+ CLI application with deterministic exit codes 0 through 6.
     - [ ] AST parsing of subagent dispatches ensuring no subagent calls exist inside loops.
     - [ ] Automated detection and blocking of deprecated background runner scripts.
     - [ ] Zero unfulfilled code blocks, pass statements, or unhandled exceptions.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL RESULTS ACROSS DESIGNATED DISK MIRRORS
================================================================================
Emitting the WBS artifact solely into conversational output or ephemeral buffers is strictly prohibited.
You MUST write the complete, unabridged deliverable directly to physical disk across all designated mirror paths:

1. Primary Scratch Path:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_2_preflight_mcp_breakdown.md`

2. Repository Documentation Mirror:
   `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_3_2_preflight_mcp_breakdown.md`

3. Ecosystem Documentation Mirror:
   `D:/__CoChem/.docs/task2_3_2_preflight_mcp_breakdown.md`

4. Inbox Dropzone Mirror:
   `D:/__CoChem/__agentic/dropzones/inbox_srs/task2_3_2_preflight_mcp_breakdown.md`

5. Swarm State Ledger Synchronization:
   Update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` recording:
   ```json
   {
     "anti_spoofing_compliance": true,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.3.2: Decompose L2 Rule 1.1 Pre-Flight MCP protocol into L3 component tasks",
     "wbs_level": "Level 3 Component Breakdown",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "zero_fabrication_enforced": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_2_preflight_mcp_breakdown.md",
       "D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_3_2_preflight_mcp_breakdown.md",
       "D:/__CoChem/.docs/task2_3_2_preflight_mcp_breakdown.md",
       "D:/__CoChem/__agentic/dropzones/inbox_srs/task2_3_2_preflight_mcp_breakdown.md"
     ],
     "sha256_checksum": "<COMPUTED_SHA256>"
   }
   ```

================================================================================
CRITICAL DIRECTIVE 3: RETURN COMPREHENSIVE VERIFICATION REPORT
================================================================================
Upon completing disk writes and ledger updates, return a formal report starting with `[SDPM REPORT]` and concluding with `[VERIFICATION & HANDOFF SUMMARY]`, detailing:
1. Formal confirmation of task completion.
2. Exact absolute file paths written across all mirror locations.
3. Physical byte count and line count of each artifact.
4. Cryptographic SHA-256 hash for every written file.
5. Summary of the ratified L3 work packages, single-owner RACI assignments, and provenance tag distribution.
6. Confirmation that Zero-Fabrication mandates and dynamic Mendeleev atomic masses are 100% satisfied.
7. Formal handoff designation to `cochem-audit` and `adversary` for asymmetric zero-trust verification.

================================================================================
ZERO-FABRICATION & METHOD MATRIX MANDATES
================================================================================
- Strictly eradicate all non-functional routines, empty pass blocks, and synthetic test generators.
- Do NOT use unfulfilled parameter blocks, `NotImplementedError`, or shortcut flags.
- All isotopic masses and physical constants must resolve dynamically via `from mendeleev import element` in full compliance with Method Matrix v4 invariants.
```
