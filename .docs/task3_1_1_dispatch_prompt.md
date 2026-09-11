# Task 3.1.1 Dispatch Specification: Elicit Level 1 Task 3 Architectural Scope (Interactive UI and Voila GUI Specifications)

**Parent Task:** Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]  
**Level 2 Task:** Decomposed Level 1 Task 3 into granular Level 2 technical tasks and Level 3 microtasks via `cochem-sdp-manager` [GOV]  
**Specific Task to Execute:** `3.1.1 - Elicited Level 1 Task 3 architectural scope (Interactive UI and Voila GUI Specifications) from SRS and Method Matrix v4` [GOV] / [DOC]  
**Exact Execution Agent:** `ui` (UI Design Expert & Frontend Specialist, operating in formal consultation with `cochem-sdp-manager`) [M]  
**Primary Scratch Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_1_1_dispatch_prompt.md` [GOV]  
**Conversation Artifact Mirror:** `C:/Users/ansac/.gemini/antigravity-cli/brain/c58ca7f2-f913-4075-ba12-d5dc106d716a/task3_1_1_dispatch_prompt.md` [GOV]  
**Ecosystem Master Mirror:** `D:/__CoChem/.docs/task3_1_1_dispatch_prompt.md` [GOV]  
**Repository Mirror:** `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_1_1_dispatch_prompt.md` [GOV]  
**Dropzone Inbox Mirror:** `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_1_1_dispatch_prompt.md` [GOV]  
**Target Persistence Deliverable:** `task3_boundary_and_interface_manifest.md` [DOC]  
**Swarm State Ledger:** `swarm_state.json` [PROC]  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `ui` (UI Design Expert & Frontend Specialist)

### Authoritative Governance & Architecture Rationale:
1. **Domain Authority & Persona Alignment:**  
   Under the CoChem Agent Council taxonomy and skill definition ([`agent-ui`](file:///C:/Users/ansac/.gemini/config/skills/agent-ui/SKILL.md)), `ui` is the designated specialist for evaluating, designing, and optimizing user interfaces, interactive notebooks, and data visualizers adhering to Jakob Nielsen’s 10 Usability Heuristics, Ben Shneiderman’s 8 Golden Rules, WCAG 2.1 AA standards (4.5:1 contrast, viridis/cividis color-blind palettes), and American Chemical Society (ACS) publication standards. Eliciting the architectural scope of the zero-code interaction tier—specifically the dual execution boundaries between the Jupyter Backend Shell (`Start_Here.ipynb`) and the code-blind Voila standalone GUI dashboard (`cochem_unity_installer_dashboard.py`)—requires domain-specific frontend design authority.
2. **Strict Separation of Concerns & PMBOK Governance:**  
   While `cochem-sdp-manager` manages overarching PMBOK 7th Edition scope decomposition and SWEBOK software requirements baselining, the specific technical elicitation of interactive widgets, DOM AST-stripping constraints (`--strip_sources=True`), real-time System Matrix HUD hardware telemetry, and anti-double-click orchestrator state latches belongs strictly to `ui`.  
   - `cochem-coder` is strictly forbidden from authoring its own interaction scope boundaries to prevent developer bias and counterfeit compliance.  
   - `artist` generates static vector/raster graphics, not interactive software interfaces.  
   - `cochem-audit` and `adversary` maintain asymmetric independence and must not author specifications they subsequently audit.
3. **Repository Precedent & Master WBS Harmony:**  
   In the master WBS baseline ([`task3_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md)), WBS Section 3 specifically ratifies `ui` as the responsible agent for Voila GUI dashboard microtask specifications (WBS 3.4) and the interactive presentation plane. Assigning Task 3.1.1 to `ui` enforces unbroken continuity across the UI specification lifecycle.

---

## 2. Authoritative Dispatch Prompt for `ui`

```markdown
[UI EXECUTION ORDER: TASK 3.1.1 - ELICIT LEVEL 1 TASK 3 ARCHITECTURAL SCOPE & INTERFACE MANIFEST]

You are `ui`, the UI Design Expert and Frontend Architect for the CoChem Agent Council. You evaluate, design, and optimize frontend interfaces, interactive dashboards, and scientific data visualizations strictly adhering to Jakob Nielsen's 10 Usability Heuristics, Ben Shneiderman's 8 Golden Rules, WCAG 2.1 AA accessibility standards, the CoChem Method Matrix v4, and the Anti-Spoofing Council Directive v4.

================================================================================
1. PROJECT HIERARCHY & SPECIFIC TASK ASSIGNMENT
================================================================================
- Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]
- Level 2: Decomposed Level 1 Task 3 into granular Level 2 technical tasks and Level 3 microtasks via cochem-sdp-manager. [GOV]
- Specific Task to Execute:
  3.1.1 - Elicited Level 1 Task 3 architectural scope (Interactive UI and Voila GUI Specifications) from SRS and Method Matrix v4. [DOC]

================================================================================
2. MANDATORY OPERATIONAL RULE 1: INGEST EXISTING PROJECT FILES VIA TOOLS
================================================================================
Before generating any scope analysis, interface contracts, or architectural diagrams, you MUST invoke your filesystem tools (view_file, grep_search, list_dir, find_by_name) to inspect existing physical files on disk and establish complete empirical context:

1. Ingest Existing Architectural & WBS Manifests:
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md (Authoritative Level 2 breakdown, WBS 3.1 to 3.15 matrix, and interface scope)
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_1_2_dispatch_prompt.md (Formulated MECE 5-tier Level 2 technical work packages)
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_level2_wbs_breakdown.md (Structural standards, provenance conventions)
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md (Method Matrix mapping, risk registers)
2. Ingest Existing Interface Implementations & Codebase State:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Task_List.md (Authoritative task hierarchy and subsystem descriptions)
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/mm/quadrature_manager.py (Dynamic quadrature lifecycle implementation)
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json (Current swarm ledger and active verification covenants)
3. Ingest Authoritative Agent Knowledge Sources:
   - D:/Gdrive/__agentic/.sources/Global_Agent_Index.md (System index)
   - D:/Gdrive/__agentic/.sources/CoChem_User_Manual.md (User interaction standards)

You are STRICTLY FORBIDDEN from guessing file locations, inventing arbitrary UI widgets without inspecting existing specifications, or hallucinating hardware profiling parameters. Read the physical codebase first.

================================================================================
3. TECHNICAL SCOPE & ARCHITECTURAL MANIFEST REQUIREMENTS
================================================================================
You must author a rigorous, production-grade architectural specification document titled `task3_boundary_and_interface_manifest.md` that comprehensively establishes the boundary and interface scope for Level 1 Task 3. The manifest must cover:

1. Executive Scope & Dual Execution Planes:
   - Complete architectural boundary delineation between:
     * Tier 1 (Backend Execution Shell): Jupyter `Start_Here.ipynb` running sequential `%run` cells without leaking subshell environments.
     * Tier 2 (Presentation Frontend): Voila standalone GUI dashboard (`cochem_unity_installer_dashboard.py`) enforcing code-blind AST-stripping.
2. Interface Contracts & Data Tier Integration:
   - Formal interface contracts connecting interactive UI widgets to Stage 0 setup scripts (`orchestrator/cochem_setup_phase_X.py`).
   - Dynamic registry bridge targeting `$COCH_ARTIFACTS/Registry/cochem_system_config.json` backed by Pydantic v2 schemas (`SystemConfigPayload`).
   - Platform-agnostic environment variable resolution (`$COCH_ARTIFACTS`, `$SCRATCH`, `$COCHEM_STATE_DIR`), strictly banning hardcoded `$HOME` or user directory strings.
3. UI Guardrails & State Management Architecture:
   - 6-tier runtime selection model: `Local-Windows (WSL)`, `Local-MacOS (OrbStack)`, `Local-Linux (Deb)`, `GitHub Codespaces`, `HPC`, `GitHub Actions`.
   - Topological prerequisite locking: immutable base dependencies (`CoChem-BASE`, `CoChem-MInt` locked to `disabled=True, value=True`), cascading dependency enabling, and SCRIBE LLM default-off guard.
   - Instant orchestrator immutability latch: anti-double-click guard disabling all interactive controls upon dispatch.
   - Non-blocking asynchronous telemetry dispatcher (`asyncio` / `ThreadPoolExecutor`) streaming stdout/stderr into a strictly bounded 1,000-line memory ring-buffer in `ipywidgets.Output()`.
4. Method Matrix v4 & Physical Invariants:
   - Dynamic Mendeleev atomic mass querying: all molecular mass and isotopic data must dynamically resolve via `from mendeleev import element`; hardcoded mass lookup tables are strictly forbidden.
   - JAX double precision invariant: line-1 enforcement of `jax.config.update("jax_enable_x64", True)`.
   - Rotational frequency unit conversions (MHz, GHz, kHz) and energy units (cm^-1, Hartrees, kcal/mol, eV, kJ/mol).
   - Jakob Nielsen's 10 Usability Heuristics & WCAG 2.1 AA accessibility compliance (4.5:1 contrast, viridis/cividis color palettes).
5. Comprehensive RACI Accountability & Traceability:
   - Single-owner RACI allocation across all 15 Level 3 work packages (`WBS 3.1` through `WBS 3.15`).
   - End-to-end traceability matrix linking SRS requirements to verification suites (`test_chunk17_verification_suite.py`, Draco UI suite).

================================================================================
4. MANDATORY OPERATIONAL RULE 2: PHYSICAL DISK PERSISTENCE
================================================================================
You are STRICTLY FORBIDDEN from merely emitting your specification to conversational stdout or ephemeral memory buffers.
You MUST invoke `write_to_file` to write the complete, unabridged deliverable directly to physical disk across all designated mirror locations:

1. Primary Scratch Path:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_boundary_and_interface_manifest.md`
2. Canonical Brain Mirror:
   `C:/Users/ansac/.gemini/antigravity-cli/brain/c58ca7f2-f913-4075-ba12-d5dc106d716a/task3_boundary_and_interface_manifest.md`
3. Ecosystem Master Documentation Mirror:
   `D:/__CoChem/.docs/task3_boundary_and_interface_manifest.md`
4. Repository Documentation Mirror:
   `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_boundary_and_interface_manifest.md`
5. Dropzone Inbox Mirror:
   `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_boundary_and_interface_manifest.md`

================================================================================
5. MANDATORY OPERATIONAL RULE 3: FINAL AUDIT TEXT REPORT WITH MODIFIED PATHS
================================================================================
Upon completing disk persistence, you MUST return a comprehensive final text report in your terminal response.
Your report MUST begin with `[UI ARCHITECTURE REPORT]` and conclude with a dedicated `[VERIFICATION & HANDOFF SUMMARY]` section detailing:
1. Formal confirmation of task completion status (`SUCCESS`).
2. Exact absolute and relative file paths modified or created on disk across all mirror tiers.
3. Physical byte count and line count of each generated artifact.
4. Cryptographic SHA-256 hash for every written file on disk.
5. Verification summary proving complete coverage of the dual execution planes, UI guardrails, and single-owner RACI mapping.
6. Formal handoff notice for `cochem-audit` and `adversary` for independent asymmetric verification.

================================================================================
6. ZERO-MOCK & ANTI-SPOOFING DIRECTIVES (PROTOCOL v4)
================================================================================
- Strictly eradicate all mocks, stubs, dummy loops, and fake data structures.
- Do NOT use `NotImplementedError` or empty `pass` blocks as dead-end stubs.
- Do NOT use synthetic array generators (`np.zeros`, `np.ones`, `np.eye`) to fake state tensors or coordinate matrices.
- Do NOT use shortcut tag-appending (e.g., `[AUDITOR FIX REQUIRED]`); deliver complete, production-grade specifications.
- Strictly enforce dynamic Mendeleev querying (`from mendeleev import element`).
```

---

## 3. Adversarial Pre-Flight Verification Matrix

| Evaluation Dimension | Required Invariant Standard | Operational Enforcement in Dispatch Prompt | Verification Status |
| :--- | :--- | :--- | :---: |
| **1. Exact Execution Agent Selection** | Unique single-owner designation (`ui`) with PMBOK/SWEBOK justification | Section 1 provides formal justification citing Jakob Nielsen heuristics, WCAG 2.1 AA, and WBS 3.4 alignment. | **PASS** |
| **2. Context Ingestion Directive (Rule 1)** | Explicit command to read existing project files on disk via tools before authoring | Section 2 explicitly commands `view_file`, `grep_search`, `list_dir`, `find_by_name` across 8 specific paths. | **PASS** |
| **3. Physical Disk Persistence (Rule 2)** | Explicit command to persist complete deliverables directly to disk via `write_to_file` | Section 4 explicitly mandates writing `task3_boundary_and_interface_manifest.md` across 5 mirror paths. | **PASS** |
| **4. Final Text Report (Rule 3)** | Structured report with exact paths, sizes, lines, SHA-256 hashes, and handoff notice | Section 5 explicitly mandates `[UI ARCHITECTURE REPORT]` + `[VERIFICATION & HANDOFF SUMMARY]`. | **PASS** |
| **5. Anti-Spoofing & Zero-Mock (Protocol v4)** | Eradication of mocks, stubs, dummy loops, `NotImplementedError`, and synthetic arrays | Section 6 codifies zero-mock constraints; bans synthetic data; mandates dynamic Mendeleev resolution. | **PASS** |
| **6. Method Matrix v4 Physical Invariants** | Dynamic mass queries, JAX 64-bit precision, spend hierarchy, and unit conversions | Section 3 mandates `from mendeleev import element`, `jax_enable_x64`, and spectroscopy unit conversions. | **PASS** |

---

## 4. Sequential Handoff Notice

The dispatch specification `task3_1_1_dispatch_prompt.md` is fully formulated and persisted across all repository and scratch mirrors. It is cleared for native execution and sequential adversarial audit by `adversary` and `cochem-audit`.
