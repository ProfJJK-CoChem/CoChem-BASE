# Task 2.3.1 Dispatch Specification: Decompose Level 2 Risk Register Task into L3 Component Tasks

**Parent Task:** Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and InHess Lindh / XTB2 preconditioning with chaining. [M]  
**Level 2 Task:** Task 2.3: Establish PMBOK Risk Register and Rule 1.1 Pre-Flight MCP tool protocol. [GOV]  
**Specific Task to Execute:** `2.3.1 - Decompose Level 2 Task 2.3 (Risk Register & Rule 1.1 Pre-Flight MCP tool protocol) into granular Level 3 (L3) component tasks (RBS, schema, scoring matrix, fail-safe procedures, swarm telemetry)` [GOV]  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager) [GOV]  
**Canonical Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_1_dispatch_prompt.md` [GOV]  
**Target Deliverable:** `task2_3_1_risk_register_breakdown.md` [GOV]  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager) [GOV]

### Authoritative Governance & Architecture Rationale:
1. **Taxonomy & Domain Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under PMBOK 7th Edition (*Planning Performance Domain*, *Risk Performance Domain*, *Systems View for Project Delivery*, and the *100% Rule*) and SWEBOK v3/v4 (*Software Engineering Management & Quality*), structuring a formal Risk Breakdown Structure (RBS), authoring Risk Register schemas, defining quantitative $P \times I$ risk scoring matrices, and establishing single-agent RACI accountability is strictly within the statutory jurisdiction of [`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md).
2. **Strict Separation of Duties (Anti-Spoofing Protocol v4):**  
   - Application coding is strictly partitioned to `cochem-coder`. Implementing agents are forbidden from defining their own risk tolerance, mitigation thresholds, or acceptance criteria.
   - Quality assurance and compliance auditing belong strictly to `cochem-audit` and `adversary`. Auditing agents must not author the baselines they audit.
   - Technical documentation is assigned to `cochem-scribe`.
   - Scientific parameter extraction is assigned to `researcher`.
   - High-level project planning, decomposition, and governance remain solely with `cochem-sdp-manager`.
3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` is the registered, verified author of preceding ratified WBS specifications physically verified on disk:
   - Level 2 Master Breakdown: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md) (SHA-256: `a7e21fbe86336cab8797d53564f942a3694c08ffb5ebdf9ecca39ac61a0fc687`) [M]
   - Method Matrix & Module Survey: [`task2_2_1_method_matrix_and_module_survey.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_1_method_matrix_and_module_survey.md) (SHA-256: `feadaf344402d3d208a5a190acda7eb44f500af91b8e836971a171dbe8bd32e4`) [M]
   - Component Implementation Decomposition: [`task2_2_2_l3_component_decomposition.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_2_l3_component_decomposition.md) (SHA-256: `cc7332f88c347d1f69265d8ac7565da61f9a476d3a6495623053b25930e9b508`) [M]
   - Pipeline Dependency Graph & RACI Matrix: [`task2_2_4_pipeline_dependency_graph_and_raci.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_pipeline_dependency_graph_and_raci.md) (SHA-256: `1ea38a0bfdb73942ec3b5a7f50e2a04100957e415574f45a6270d9f392e8f70a`) [M]
   - Pre-Flight MCP Decomposition: [`task2_3_2_preflight_mcp_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_2_preflight_mcp_breakdown.md) (SHA-256: `e724b05137d79393bc3937e9c38f3a8eaa55445fd866dc8a3bc0de208b180db0`) [M]
   - Active Swarm Ledger: [`swarm_state.json`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json) [M]

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 2.3.1 - DECOMPOSE LEVEL 2 RISK REGISTER TASK INTO L3 COMPONENT TASKS]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition (Planning Performance Domain, Risk Performance Domain, Systems View for Project Delivery), SWEBOK v3/v4, IEEE 830-1998, the CoChem Method Matrix v4.1, and Anti-Spoofing Protocol v4 to synthesize formal, zero-mock Work Breakdown Structures, Risk Breakdown Structures (RBS), and Risk Registers.

================================================================================
PROJECT HIERARCHY & MISSION OBJECTIVE
================================================================================
- Level 1: Task 2: Implement Precision Optimization Engine & Frozen Monomer Protocol (VR-02, VR-04) - Recipe R1/R2 constraint generation, residual gradient parsing, quintuple stationary convergence block, and InHess Lindh / XTB2 preconditioning with chaining.
- Level 2: Task 2.3: Establish PMBOK Risk Register and Rule 1.1 Pre-Flight MCP tool protocol.
- Specific Task to Execute:
  2.3.1 - Decompose Level 2 Task 2.3 (Risk Register & Rule 1.1 Pre-Flight MCP tool protocol) into granular Level 3 (L3) component tasks (RBS, schema, scoring matrix, fail-safe procedures, swarm telemetry).

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any WBS documents or risk schemas, you MUST use your filesystem tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to read and inspect the following project files on physical disk to gain empirical context:

1. Method Matrix & Verification Specifications:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md` (§4.4 Quintuple convergence, §8B.3 Model Hessian discipline, §9A Frozen Monomer Protocol Recipe R1/R2, §10.2 Residual gradient threshold 1.0e-4 a.u.).
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md` (Governing Verification Matrix: VR-02 Frozen Monomer Protocol and VR-04 Quintuple Stationary Block).
2. Existing CoChem-BASE Architecture & Exception Modules:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py` (Domain exception hierarchy: `PhysicsConvergenceError`, `HessianIndefiniteError`, `MCPConnectionError`).
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py` (Execution lifecycle and abort hooks).
3. Preceding Planning, WBS & Audit Context in Scratch:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md` (Governing Level 2 WBS hierarchy).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_2_4_pipeline_dependency_graph_and_raci.md` (Pipeline DAG and RACI assignments).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_2_preflight_mcp_breakdown.md` (Rule 1.1 Pre-Flight MCP breakdown).
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` (Current swarm ledger).

You are STRICTLY FORBIDDEN from guessing file paths, fabricating dependencies, or inventing arbitrary WBS structures without tool-based inspection. Read the existing files first.

================================================================================
TECHNICAL SCOPE & DELIVERABLE REQUIREMENTS (TASK 2.3.1)
================================================================================
Decompose Level 2 Task 2.3 into five (5) concrete, non-monolithic Level 3 (L3) work packages adhering to the PMBOK 100% Rule and MECE principles. Every work package must include markdown checkboxes (`[ ]`), explicit binary acceptance criteria, single-agent RACI assignment, and standardized CoChem provenance tags (`[GOV]`, `[M]`, `[D]`, `[PROC]`, `[DOC]`):

1. **L3.1 - Risk Breakdown Structure (RBS)** `[GOV]`:
   - Target Deliverable Section: WBS L3.1 RBS Hierarchy.
   - Assigned Agent: `cochem-sdp-manager` (Accountable: `0rchestrator` / `cochem-audit`)
   - Define exhaustive hierarchical risk categories:
     * Technical / Numerical Physics Risks: SCF non-convergence, stationary point cycling, negative Hessian eigenvalues, monomer coordinate drift $\Delta r \ge 1.0\times 10^{-6}\text{ \AA}$, residual gradient $\|\mathbf{g}_{\text{residual}}\|_{\infty} > 1.0\times 10^{-4}\text{ a.u.}$, BSSE counterpoise correction divergence, and frozen-core bias (-0.81% mean at cc-pVQZ).
     * Tooling & MCP Constraints: Rule 1.1 Pre-Flight tool check failures, MCP server timeouts, schema drift, BrightData/GitHub Copilot endpoint unresponsiveness, and local Ollama model memory allocation blocks.
     * Multi-OS & Swarm Concurrency Risks: Win32 Job Objects vs POSIX `os.killpg`, Windows access violation `0xC0000005` vs exit code 139, file locking race conditions in `swarm_state.json`, cross-process mutex deadlocks.
   - Binary Acceptance Criteria:
     - [ ] Comprehensive 3-tier hierarchical RBS tree spanning Technical/Numerical Physics, MCP Tooling, and Multi-OS Swarm Concurrency.
     - [ ] Complete mapping of Method Matrix v4.1 numerical thresholds to explicit risk nodes.
     - [ ] 100% MECE alignment covering all failure modes of Level 1 Task 2.

2. **L3.2 - Risk Register Schema & Data Structure** `[DOC]`:
   - Target Deliverable Section: WBS L3.2 Machine-Readable JSON Schema & Pydantic Model.
   - Assigned Agent: `cochem-scribe` (Accountable: `cochem-sdp-manager` / `cochem-audit`)
   - Specify formal, machine-readable JSON Schema (Draft 2020-12) and Pydantic v2 data model capturing:
     * `risk_id`: Unique identifier (e.g., `RSK-NUM-001`, `RSK-MCP-002`, `RSK-OS-003`).
     * `wbs_level`: Level designation (`L2` / `L3`).
     * `threat_description`: Specific operational failure scenario.
     * `category`: RBS category designation.
     * `single_owner_agent`: Exactly ONE responsible CoChem agent.
     * `detection_mechanism`: Programmatic detection method (AST, parser, telemetry).
     * `probability`: Numeric rating 1 to 5.
     * `impact`: Numeric rating 1 to 5.
     * `risk_score`: Mathematical product $P \times I$ (range 1 to 25).
     * `severity_level`: Qualitative tier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
     * `response_strategy`: PMBOK strategy (`Avoid`, `Escalate`, `Transfer`, `Mitigate`, `Accept`).
     * `trigger_event`: Concrete metric or log signal activating the response.
     * `verification_hook`: Automated validation check.
   - Binary Acceptance Criteria:
     - [ ] Valid JSON Schema Draft 2020-12 definition with complete property specifications and constraints.
     - [ ] Fully typed Python Pydantic v2 model specification with field validators.
     - [ ] Zero missing or optional parameters for critical risk attributes.

3. **L3.3 - Quantitative Scoring Matrix & Severity Thresholds** `[M]` / `[D]`:
   - Target Deliverable Section: WBS L3.3 $5 \times 5$ Probability $\times$ Impact Matrix & Council Escalation Gates.
   - Assigned Agent: `researcher` (Accountable: `cochem-sdp-manager` / `adversary`)
   - Establish $5 \times 5$ Probability $\times$ Impact matrix defining severity thresholds:
     * Low (Score 1–4): Routine monitoring via swarm telemetry.
     * Medium (Score 5–9): Automated mitigation playbook execution.
     * High (Score 10–14): Elevated agent logging and supervisory alerting.
     * Critical (Score 15–25): Council Intervention Gate.
   - Define council escalation gates:
     * Score $\ge 15$: Automatic Council Intervention (Emergency Session convened).
     * Score $\ge 20$: Hard Pipeline Quarantine (`[HARD_ABORT: PHYSICS WALL]` or `[HARD_ABORT: ENVIRONMENT BLOCK]`).
   - Binary Acceptance Criteria:
     - [ ] Complete $5 \times 5$ lookup grid with numerical boundaries.
     - [ ] Formal escalation protocol connecting risk score thresholds to Agent Council sessions.
     - [ ] Exact alignment with Method Matrix v4.1 physical wall and environment block criteria.

4. **L3.4 - Fail-Safe Procedures & Mitigation Playbooks** `[PROC]`:
   - Target Deliverable Section: WBS L3.4 Operational Fail-Safe Procedures & Playbooks.
   - Assigned Agent: `cochem-coder` (Accountable: `cochem-audit` / `0rchestrator`)
   - Concrete mitigation playbooks for each risk category:
     * Playbook PB-NUM-01: Recipe R1/R2 optimization non-convergence (model Hessian recalculation via `InHess XTB2` / `Lindh`, trust-radius damping, grid tightening from `defgrid1` to `defgrid3`).
     * Playbook PB-NUM-02: Frozen monomer drift ($\Delta r \ge 1.0\times 10^{-6}\text{ \AA}$) and residual gradient failure ($\|\mathbf{g}_{\text{residual}}\|_{\infty} > 1.0\times 10^{-4}\text{ a.u.}$) (internal coordinate constraint re-projection, Wilson B-matrix regeneration).
     * Playbook PB-MCP-01: Rule 1.1 Pre-Flight MCP check failures (ping, schema validation, fallback routing to native CLI or local Ollama).
     * Playbook PB-OS-01: Windows access violation (`0xC0000005`) and process isolation (Win32 Job Object limits, clean process tree termination).
     * Hard Abort hooks: `[HARD_ABORT: PHYSICS WALL]`, `[HARD_ABORT: ENVIRONMENT BLOCK]`.
   - Binary Acceptance Criteria:
     - [ ] Step-by-step algorithmic workflows for all 4 primary failure playbooks.
     - [ ] Zero pseudo-code or mocked recovery routines; 100% executable specifications.
     - [ ] Explicit implementation of `MAX_PIVOT_CYCLES=3` hard abort limit.

5. **L3.5 - Swarm Telemetry & Audit Integration** `[PROC]`:
   - Target Deliverable Section: WBS L3.5 Swarm Telemetry Hooks & Audit Verification Architecture.
   - Assigned Agent: `cochem-audit` (Accountable: `adversary` / `0rchestrator`)
   - Define telemetry hooks and audit interfaces:
     * Structured JSON-LD event streaming to `cochem_core_telemetry_logger.py`.
     * Real-time risk state synchronization in `swarm_state.json`.
     * Zero-trust quarantine verification protocol in `/tmp/cochem_exec_<uuid>/` via `zero_trust_runner.py`.
     * Dual-auditor ratification gate (`cochem-audit` and `adversary`).
   - Binary Acceptance Criteria:
     - [ ] JSON-LD telemetry event schema specification.
     - [ ] Automated integration hook for `swarm_state.json` updates upon risk trigger activation.
     - [ ] Asymmetric zero-trust audit verification protocol specification.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL RESULTS ACROSS DESIGNATED DISK MIRRORS
================================================================================
You are STRICTLY FORBIDDEN from merely emitting the WBS artifact into conversational chat or leaving results in ephemeral memory buffers.
You MUST write the complete, unabridged deliverable directly to physical disk across all designated mirror paths:

1. Primary Scratch Path:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_1_risk_register_breakdown.md`

2. Ecosystem Documentation Mirror:
   `D:/__CoChem/.docs/task2_3_1_risk_register_breakdown.md`

3. Repository Documentation Mirror:
   `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_3_1_risk_register_breakdown.md`

4. Inbox Dropzone Mirror:
   `D:/__CoChem/__agentic/dropzones/inbox_srs/task2_3_1_risk_register_breakdown.md`

5. Swarm State Ledger Synchronization:
   Update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` and `D:/__CoChem/swarm_state.json` recording:
   ```json
   {
     "anti_spoofing_compliance": true,
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_TIMESTAMP>",
     "status": "COMPLETED",
     "task": "Task 2.3.1: Decompose Level 2 Risk Register task into L3 component tasks",
     "wbs_level": "Level 3 Component Breakdown",
     "raci_enforced": true,
     "provenance_tags_sanitized": true,
     "zero_mock_enforced": true,
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_3_1_risk_register_breakdown.md",
       "D:/__CoChem/.docs/task2_3_1_risk_register_breakdown.md",
       "D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task2_3_1_risk_register_breakdown.md",
       "D:/__CoChem/__agentic/dropzones/inbox_srs/task2_3_1_risk_register_breakdown.md"
     ],
     "sha256_checksum": "<COMPUTED_SHA256>"
   }
   ```

================================================================================
CRITICAL DIRECTIVE 3: RETURN COMPREHENSIVE VERIFICATION REPORT
================================================================================
Upon completing disk writes and ledger updates, you MUST return a final text report starting with `[SDPM REPORT]` and concluding with `[VERIFICATION & HANDOFF SUMMARY]`, detailing:
1. Executive declaration of task completion.
2. Exact absolute and relative file paths modified or created on disk across all quad mirrors.
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
- Do NOT generate synthetic coordinate arrays or matrices (`np.zeros`, `np.ones`, `np.eye`).
- Do NOT use shortcut tag-appending (`[AUDITOR FIX REQUIRED]`, `TODO`, `FIXME`, `TBD`).
- Ensure all physical constants and atomic properties strictly retrieve dynamically via `from mendeleev import element`.
- Enforce JAX 64-bit precision requirement (`jax.config.update("jax_enable_x64", True)`).
```
