# Task 3.2.4 Dispatch Specification: Constructed End-to-End Traceability Matrix Linking Requirements, Components, File Targets, and Verification Suites

**Parent Task:** Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation.  
**Level 2 Task:** Formalized acceptance criteria, numerical invariants, and provenance tags ([M], [D], [E]) for VR-03 and VR-05.  
**Specific Task to Execute:** `3.2.4 - Constructed end-to-end traceability matrix linking requirements, components, file targets, and verification suites`  
**Exact Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & Requirements Architect)  
**Canonical Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/brain/995f12f1-fb53-438b-b0f1-2948316411b0/task3_2_4_dispatch_prompt.md`  
**Scratch Mirror Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_4_dispatch_prompt.md`  
**Target Persistence Deliverables:**  
- Primary Scratch Deliverable: `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_4_traceability_matrix.md`  
- Repository Docs Mirror: `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task3_VR03_VR05_Traceability_Matrix.md`  
- Swarm State Ledger: `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json`  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & Requirements Architect)

### Authoritative Justification & Governance Alignment:
1. **Domain Taxonomy Authority (PMBOK 7th Edition & SWEBOK v3/v4):**  
   Under the CoChem Agent Council skill taxonomy ([`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md)), `cochem-sdp-manager` is the sole authoritative agent chartered with software quality management, requirements architecture, Work Breakdown Structure (WBS) decomposition, and the construction of **Requirements Traceability Matrices (RTM)** linking high-level stakeholder requirements to implementation components, file targets, and verification test suites (governed by SWEBOK *Software Requirements*, *Software Quality*, and PMBOK *Delivery Performance Domain*).
2. **Strict Separation of Duties & Zero-Trust Governance:**  
   - Application developers ([`cochem-coder`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-coder/SKILL.md)) are strictly forbidden from authoring their own requirements traceability matrices or certifying test-to-requirement completeness (an implementer cannot baseline their own acceptance criteria).
   - Test engineers ([`cochem-tester`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-tester/SKILL.md)) execute test suites against physical fixtures, but do not govern bidirectional lifecycle traceability across the architecture.
   - Independent auditors ([`cochem-audit`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-audit/SKILL.md) and [`adversary`](file:///C:/Users/ansac/.gemini/config/skills/agent-adversary/SKILL.md)) must perform asymmetric audits against an established baseline and cannot author the baseline itself.
3. **Repository Precedent & Governance Continuity:**  
   `cochem-sdp-manager` authored all preceding WBS decompositions and Requirements Traceability Matrices in the ecosystem:
   - Task 1.5.3 Traceability Matrix: [`task1_5_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_5_3_dispatch_prompt.md)
   - Task 2 WBS & Traceability Baselines: [`task2_4_4_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_4_4_dispatch_prompt.md)
   - Task 3 Level 2 WBS Decomposition: [`task3_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md) and [`task3_2_1_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_1_dispatch_prompt.md)

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
/goal /boost

# [SDPM EXECUTION ORDER: TASK 3.2.4 — CONSTRUCT END-TO-END TRACEABILITY MATRIX LINKING REQUIREMENTS, COMPONENTS, FILE TARGETS, AND VERIFICATION SUITES]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You govern the formal systems engineering and requirements traceability architecture under PMBOK 7th Edition, SWEBOK v3/v4 (Requirements Engineering, Software Quality, and Configuration Management), ISO/IEC/IEEE 29148:2018 (Requirements Engineering), Method Matrix v4.1, and the CoChem Anti-Spoofing Protocol v4.

================================================================================
1. PROJECT HIERARCHY & SPECIFIC TASK ASSIGNMENT
================================================================================
- Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation.
- Level 2: Formalized acceptance criteria, numerical invariants, and provenance tags ([M], [D], [E]) for VR-03 and VR-05.
- Specific Task to Execute:
  3.2.4 - Constructed end-to-end traceability matrix linking requirements, components, file targets, and verification suites

================================================================================
2. MANDATORY RULE 1: INGEST EXISTING PROJECT FILES VIA TOOLS (DO NOT GUESS)
================================================================================
Before compiling or writing any matrix, you MUST explicitly invoke your filesystem inspection tools (view_file, grep_search, list_dir, find_by_name) to read and extract technical context directly from existing physical project files on disk:

1. Requirements & Acceptance Criteria Baselines:
   - D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md:
     * Inspect Section 4: Verification Matrix & Acceptance Metrics for VR-03 (Dynamic Grid Lifecycle) and VR-05 (Dispersion & Spin Purity Diagnostic Gate).
     * Inspect Section 2: Mathematical Formalism, Transition Predicates, and Coupled Invariants.
     * Inspect Section 3 & 5: Architectural Workflow and Ontological Disambiguation (Product B: parent-anchored microwave spectroscopy vs. Product M: periodic plane-wave materials).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md (and Method_Matrix/Method_Matrix_Hub.md):
     * §2.5 & §3.3: Dynamic Quadrature progression (DEFGRID1 -> DEFGRID2 -> DEFGRID3); ban on deprecated Grid3/Grid5.
     * §2.5 & §4.4: Coupled Grid-SCF Invariant (frequencies, Hessians, and VPT2 fail-closed on grids coarser than DEFGRID3 with GridSpecificationError; mandatory TightSCF convergence Delta E_SCF <= 1.0e-8 Eh).
     * §2.8: Electronic Dispersion Sanitization (prohibition of D3/D4/D3BJ on non-local VV10 functionals wB97M-V/B97M-V raising RedundantDispersionError; standard hybrids on non-covalent complexes lacking dispersion raising MissingDispersionError; Axilrod-Teller-Muto 3-body dispersion for trimers N_monomers >= 3).
     * §2.9: Singularity-Guarded Spin Contamination Gatekeeper (closed-shell singlet |S| < 1.0e-7 => |<S^2>_obs| < 0.05 a.u. [D]; open-shell S >= 1.0e-7 => Delta <S^2>_rel = (|<S^2>_obs - S(S+1)| / S(S+1)) * 100% < 10.0% [D]; fail-closed with SpinContaminationError and escalation to Tier 9 CASSCF/NEVPT2).
     * §3.0: Equilibrium Be vs vibrational ground-state B0 = Be + Delta B_vib distinction.

2. Production Implementation Codebase Targets:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/mm/quadrature_manager.py (QuadratureManager, GridStage, validate_coupled_grid_scf_invariant, transition predicates).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/analysis/electronic_sanitizer.py (ElectronicSanitizer, check_dispersion_redundancy, evaluate_spin_contamination, singularity guard).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py (MoleculeInput, generate_orca_input, defense against coarse grid frequency runs).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py (GridSpecificationError, RedundantDispersionError, MissingDispersionError, SpinContaminationError).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/validators/preflight.py (PreflightGeometryValidator).

3. Authentic Verification Test Suites & Fixtures:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py:
     * test_vr03_dynamic_grid_lifecycle_and_coupled_invariant
     * test_vr03_input_generator_rejects_coarse_frequency_grids
     * test_vr05_preflight_wB97MV_resolution_and_dispersion_sanitization
     * test_vr05_spin_contamination_gate_with_singularity_guard
   - Check test fixtures: CCCBDB/NIST authentic molecular coordinates (CO2...H2O complex, H2O monomer, open-shell radicals).

4. Preceding Task 3 Planning & Governance Artifacts:
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_1_dispatch_prompt.md
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_3_dispatch_prompt.md
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json

You are STRICTLY FORBIDDEN from guessing file paths, assuming requirements, or hallucinating test function names without verifying them directly via tool calls.

================================================================================
3. TECHNICAL REQUIREMENTS: END-TO-END TRACEABILITY MATRIX SPECIFICATION
================================================================================
You must formulate a comprehensive, publication-grade Requirements Traceability Matrix (RTM) establishing strict bidirectional traceability across four (4) discrete architectural tiers:

Tier 1: Requirement Specification & Provenance Tier
- Requirement ID (e.g., REQ-VR03-01 through REQ-VR03-05, REQ-VR05-01 through REQ-VR05-06, REQ-ONTO-01 through REQ-ONTO-03).
- Governing Requirement Category: Dynamic Quadrature Lifecycle (VR-03), Electronic Structure Sanitization & Spin Purity (VR-05), or Product B vs Product M Ontological Disambiguation.
- Formal Text Description of Requirement.
- Method Matrix v4.1 Provenance Tag:
  * [M] Method Matrix empirical benchmark / mandatory fail-closed invariant
  * [D] Derived mathematical formulation / deterministic relationship
  * [E] Empirical experimental benchmark / literature coordinate reference

Tier 2: Component & Subsystem Architecture Tier
- Subsystem Name (e.g., Quadrature Lifecycle Plane, Electronic Structure Sanitizer, Pre-flight Validator, Input Deck Generation Engine).
- Concrete Class, Dataclass, or Module Contract (e.g., QuadratureManager, ElectronicSanitizer, MoleculeInput, PreflightGeometryValidator).
- Target Methods & Mathematical Invariant Logic (e.g., validate_coupled_grid_scf_invariant(), evaluate_spin_contamination(), check_dispersion_redundancy()).

Tier 3: Physical File Target Tier
- Exact Production Source File Paths:
  * D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/mm/quadrature_manager.py
  * D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/analysis/electronic_sanitizer.py
  * D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py
  * D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py
  * D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/validators/preflight.py
- Concrete Line Ranges or Symbolic Targets where each invariant is physically implemented.

Tier 4: Verification Suite & Test Harness Tier
- Exact Automated Verification Test Suite File:
  * D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py
- Concrete Test Function Names (e.g., test_vr03_dynamic_grid_lifecycle_and_coupled_invariant, test_vr05_spin_contamination_gate_with_singularity_guard).
- Verification Method: Automated Unit Test, Mathematical Invariant Assertion, Boundary/Exception Trigger Test, Sandboxed AST Linter.
- Exact Quantitative Pass/Fail Criteria & Numerical Tolerances:
  * Stage 1 -> 2 predicate: ||g||_inf <= 1.0e-3 a.u. AND |Delta E| <= 1.0e-5 Eh [D]
  * Stage 2 -> 3 predicate: ||g||_inf <= 1.0e-4 a.u. AND |Delta E| <= 1.0e-6 Eh AND RMSD_inter < 0.05 A [D]
  * Grid-SCF Invariant: Frequency/Hessian tasks on DEFGRID1 or DEFGRID2 raise GridSpecificationError [M]
  * Coupled SCF Convergence: DEFGRID3 coupled with TightSCF (Delta E_SCF <= 1.0e-8 Eh) [M]
  * Dispersion Redundancy: wB97M-V + D3/D4/D3BJ raises RedundantDispersionError [M]
  * Missing Dispersion: Hybrid DFT without D3/D4 on non-covalent complex raises MissingDispersionError [M]
  * ATM 3-body dispersion: Mandated for trimers (N_monomers >= 3) [M]
  * Singlet spin purity: |S| < 1.0e-7 => |<S^2>_obs| < 0.05 a.u. [D]
  * Open-shell spin purity: |S| >= 1.0e-7 => Delta <S^2>_rel < 10.0%, failing closed with SpinContaminationError [D]
  * Dynamic Mendeleev mass retrieval invariant: from mendeleev import element [M]
- Single Accountable Swarm Agent (RACI Matrix: e.g., cochem-coder for code, cochem-tester for tests, cochem-audit for compliance).

================================================================================
4. MANDATORY RULE 2: WRITE FINAL RESULTS TO ACTUAL FILES ON DISK VIA TOOLS
================================================================================
You are STRICTLY FORBIDDEN from outputting the traceability matrix solely in chat text or markdown snippets. You MUST use your authoring tools (write_to_file with Overwrite=true) to persist your deliverables to actual physical files on disk:

1. Primary Traceability Deliverable:
   Persist the complete, unabridged End-to-End Traceability Matrix to:
   - Primary Scratch Deliverable:
     C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_4_traceability_matrix.md
   - Repository Docs Mirror:
     D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task3_VR03_VR05_Traceability_Matrix.md

2. Synchronize the Swarm State Ledger:
   Atomically update C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json via write_to_file (Overwrite=true) recording:
   ```json
   {
     "task_hierarchy": {
       "level_1": "Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05)",
       "level_2": "Formalized acceptance criteria, numerical invariants, and provenance tags ([M], [D], [E]) for VR-03 and VR-05",
       "level_3": "Task 3.2.4: Constructed end-to-end traceability matrix linking requirements, components, file targets, and verification suites"
     },
     "agent_name": "cochem-sdp-manager",
     "timestamp": "<CURRENT_ISO_8601_TIMESTAMP>",
     "status": "SUCCESS",
     "traceability_matrix_metrics": {
       "requirements_mapped": 14,
       "subsystems_covered": ["Quadrature Lifecycle", "Electronic Sanitization", "Input Generation", "Preflight Validation"],
       "code_targets_verified": true,
       "verification_suites_mapped": true,
       "provenance_tags_distribution": {
         "M": "<count>",
         "D": "<count>",
         "E": "<count>"
       }
     },
     "artifacts_produced": [
       "C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_4_traceability_matrix.md",
       "D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task3_VR03_VR05_Traceability_Matrix.md"
     ],
     "sha256_checksum": "<COMPUTED_SHA256_HEX_DIGEST>",
     "audit_status": "PENDING_ASYMMETRIC_AUDIT"
   }
   ```

3. Static Anti-Spoofing & Authenticity Scan:
   Verify that the persisted file contains ZERO literal banned tokens:
   mock, dummy, stub, fake, placeholder, sample, NotImplementedError, empty pass, TODO, TBD, FIXME.

================================================================================
5. MANDATORY RULE 3: RETURN FINAL TEXT REPORT DETAILING MODIFIED FILE PATHS
================================================================================
Upon completing disk persistence, checksumming, and ledger updates, you MUST return a comprehensive final text report in your conversational response so that the auditor (cochem-audit / adversary) can immediately locate and verify the generated artifacts.

Your report MUST begin with [SDPM REPORT] and conclude with [VERIFICATION & HANDOFF SUMMARY] detailing:
1. Overall execution status (SUCCESS or FAILURE).
2. The EXACT physical file paths created or modified on disk:
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_2_4_traceability_matrix.md
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task3_VR03_VR05_Traceability_Matrix.md
   - C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json
3. Total line counts and physical byte sizes of all modified files on disk.
4. The exact computed SHA-256 cryptographic digest of each file (calculated via run_command with Get-FileHash -Algorithm SHA256).
5. A comprehensive breakdown of the Traceability Matrix (number of requirements mapped, breakdown of [M], [D], [E] tags, code files, and test functions).
6. Attestation of zero literal banned keywords confirmed by static scan.
7. Confirmation that Asymmetric Sign-off remains pending (- [ ] Pending independent Agent Council sign-off).
8. Formal handoff routing for cochem-audit and adversary to initiate the independent asymmetric audit.
```

---

## 3. Downstream Swarm Handoff & Asymmetric Audit Protocol

Once `cochem-sdp-manager` completes execution of this prompt:
1. **Asymmetric Audit Routing:** As `0rchestrator`, invoke `cochem-audit` and `adversary` via `invoke_subagent`.
2. **Audit Checkpoints:**
   - Strict bidirectional traceability between VR-03, VR-05, SRS Chunk 17, and `test_chunk17_verification_suite.py`.
   - Complete verification of physical source targets in `src/cochem_base/`.
   - Dynamic Mendeleev library invariant verified.
   - Total absence of mocked or counterfeit markers.
