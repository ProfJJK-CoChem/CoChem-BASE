# Task 3.3.3 Dispatch Specification: Execution Agent Selection & Formalization Prompt for Execution Engine & HPC Workflow Router Decoupling Plane (L3.3.1 - L3.3.3)
## Ontological Disambiguation & Production Execution Architecture: Product B (Molecular Gas-Phase / ORCA / Desktop-HPC) vs Product M (Periodic Solid-State / VASP / Quantum ESPRESSO / Slurm-MPI)

**Document Identifier:** `COCHEM-DISPATCH-WBS-3.3.3-SDPM-20260911` [M]  
**Parent Task:** Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]  
**Level 2 Task:** Established technical roadmap for Product B (parent-anchored microwave) vs Product M (solid-state materials) ontological disambiguation. [GOV]  
**Specific Task to Execute:** `3.3.3 - Formalized L3 component tasks for Execution Engine & HPC Workflow Router Decoupling Plane (L3.3.1 - L3.3.3)` [GOV] / [DOC]  
**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & Requirements Architect) [M]  
**Supervising Authority:** `0rchestrator` (CoChem Swarm Council Leader) [M]  
**Supervising & Asymmetric Auditing Agents:** `cochem-audit` (Autonomous QA & Standards Lead) and `adversary` (Zero-Trust Red-Team Lead) [M]  
**Governing Architectural Baselines:**  
- Master WBS: [`task3_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task3_level2_wbs_breakdown.md) (Council Session 041 Ratified Master Baseline, 42,193 B, 456 L, SHA-256: `48E92125C69DFD5E8F0D6C1A5473A31FFCA4472C5E4BC946B13EF30E74DDB97F`) [M]  
- L3 Component Decomposition: [`task3_2_1_vr03_vr05_l3_decomposition.md`](file:///D:/__CoChem/.docs/task3_2_1_vr03_vr05_l3_decomposition.md) (Task 3.2.1 Ratified Baseline, 57,685 B, 612 L, SHA-256: `EA73F8D91B9C4D4251AF9BCEDEDC8F9E5A79C103EB646915FB05A5EFD943D6BF`) [M]  
- Requirements Traceability Matrix: [`Task3_VR03_VR05_Traceability_Matrix.md`](file:///D:/__CoChem/.docs/Task3_VR03_VR05_Traceability_Matrix.md) (Council Session 044 Ratified Baseline, 44,762 B, 283 L, SHA-256: `0235C268731857DBB0B28763852F554D326E0A958241BCC7276B0E4EB9513559`) [M]  
- Preceding Dispatch: [`task3_3_1_dispatch_prompt.md`](file:///D:/__CoChem/.docs/task3_3_1_dispatch_prompt.md) (Council Session 045 Ratified Baseline, 25,317 B, 279 L, SHA-256: `B47280F2E87DABDE81902541FCFD81937966C95F484CA9C1DC35FF7E2590DA32`) [M]  
**Governing Standards:** PMBOK Guide 7th Edition (Systems View for Project Delivery & 100% Rule), SWEBOK v3.0/v4.0 (Software Construction, Requirements & Quality), ISO/IEC/IEEE 29148:2018, IEEE 830-1998, Method Matrix v4.1, Anti-Spoofing Directive v4, Mendeleev Dynamic Mass Mandate, Disciplinary Rulings D1-01 & PCA-01 to PCA-19 [M]  
**Primary Scratch Dispatch File:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_3_3_dispatch_prompt.md` [GOV]  
**Conversation Artifact Mirror:** `C:/Users/ansac/.gemini/antigravity-cli/brain/db89ca53-89e4-40c6-b191-be4bcfbf55e5/task3_3_3_dispatch_prompt.md` [GOV]  
**Ecosystem Master Mirror:** `D:/__CoChem/.docs/task3_3_3_dispatch_prompt.md` [GOV]  
**Repository Mirror (Active HEAD):** `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_3_3_dispatch_prompt.md` [GOV]  
**Dropzone SRS Intake Mirror:** `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_3_3_dispatch_prompt.md` [GOV]  
**Lifecycle Status:** `APPROVED_FOR_BASELINE_EXECUTION` [M]  
**Timestamp:** `2026-09-11T00:05:00-05:00` [M]  

---

## 1. Execution Agent Selection & Architectural Justification

**Designated Execution Agent:** `cochem-sdp-manager` (Software Development Project Manager & Requirements Architect) [M]

### Authoritative Justification Ledger:

1. **PMBOK 7th Edition & SWEBOK v3/v4 Scope & Requirements Authority:**  
   Under the CoChem Agent Council skill taxonomy ([`cochem-sdp-manager`](file:///C:/Users/ansac/.gemini/config/skills/agent-cochem-sdp-manager/SKILL.md)), `cochem-sdp-manager` is the sole authoritative agent chartered with software requirements architecture, Work Breakdown Structure (WBS) decomposition, formalizing quantitative acceptance criteria, defining numerical and execution invariants, assigning single-owner RACI roles, and establishing rigorous work package specifications under the **PMBOK 100% Rule** and **MECE (Mutually Exclusive, Collectively Exhaustive)** principles. Formalizing the three subordinate component tasks comprising Plane 3 (Execution Engine & HPC Workflow Router Decoupling Plane) requires deep systems engineering governance to translate Method Matrix v4.1 execution topology and HPC scheduler contracts into unambiguous, type-safe software engineering interfaces.

2. **Strict Separation of Duties & Zero-Trust Governance (Council Ruling D1-01 & PCA-01):**  
   Under CoChem Zero-Trust governance and Permanent Corrective Action 01 (`PCA-01`):
   - `cochem-sdp-manager` is the project manager and requirements architect chartered with establishing formal scopes, execution boundaries, and acceptance criteria.
   - `@cochem-coder` is the downstream production developer and is **strictly prohibited from defining its own project scope, creating its own acceptance criteria, or validating its own production deliverables** (an implementer cannot baseline its own requirements).
   - Independent verification testing is reserved strictly for `cochem-tester` via authentic pytest test suites in `tests/`.
   - Asymmetric compliance audits and red-team scrutiny are reserved strictly for `cochem-audit` and `adversary`.
   - Technical documentation typesetting is reserved for `cochem-scribe`.
   - Therefore, designating `cochem-sdp-manager` to execute Task 3.3.3 preserves absolute role independence, governance integrity, and prevents counterfeit compliance [M].

3. **Repository Precedent & Swarm Continuity:**  
   `cochem-sdp-manager` authored and owns all preceding ratified WBS baseline specifications, requirements extractions, and traceability matrices across Tasks 1, 2, and 3:
   - Task 1 WBS Baseline: `task1_level2_wbs_breakdown.md`
   - Task 1 Traceability Matrix: `task1_5_3_dispatch_prompt.md`
   - Task 2 Survey & WBS: `task2_2_1_dispatch_prompt.md`, `task2_level2_wbs_breakdown.md`
   - Task 2 Component Decomposition: `task2_4_2_nine_granular_mece_level3_tasks.md`
   - Task 3 Level 2 Breakdown: `task3_level2_wbs_breakdown.md` (Ratified in Council Session 041)
   - Task 3 L3 Component Decomposition: `task3_2_1_vr03_vr05_l3_decomposition.md` (Ratified in Council Session 042)
   - Task 3 End-to-End Traceability Matrix: `Task3_VR03_VR05_Traceability_Matrix.md` (Ratified in Council Session 044)
   - Task 3.3.1 Data Architecture & Schema Formalization: `task3_3_1_dispatch_prompt.md` (Ratified in Council Session 045)  
   Assigning Task 3.3.3 to `cochem-sdp-manager` maintains uninterrupted continuity, ensures exact Method Matrix alignment, and guarantees ledger coherence [M].

4. **Single-Accountable RACI Mapping for Plane 3 (L3.3.1 - L3.3.3):**  
   In strict compliance with the ratified WBS master matrix, the component tasks for Plane 3 are allocated as follows:
   - `L3.3.1`: Quantum Chemistry Backend Execution Engine Decoupling (`cochem-sdp-manager` [Accountable], `@cochem-coder` [Responsible for Downstream Code])
   - `L3.3.2`: Solid-State Periodic Execution Engine Decoupling (`cochem-sdp-manager` [Accountable], `@cochem-coder` [Responsible for Downstream Code])
   - `L3.3.3`: HPC Workflow Router & Execution Isolation Plane (`cochem-sdp-manager` [Accountable], `@cochem-coder` [Responsible for Downstream Code])

---

## 2. Authoritative Implementation & Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 3.3.3 — FORMALIZED L3 COMPONENT TASKS FOR EXECUTION ENGINE & HPC WORKFLOW ROUTER DECOUPLING PLANE (L3.3.1 - L3.3.3)]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You govern the formal systems engineering, WBS decomposition, and technical requirements architecture under PMBOK Guide 7th Edition (Systems View for Project Delivery, 100% Rule), SWEBOK v3/v4 (Requirements Engineering, Software Design, and Software Quality), ISO/IEC/IEEE 29148:2018, IEEE 830-1998, Method Matrix v4.1, and the CoChem Anti-Spoofing Protocol v4.

================================================================================
1. PROJECT HIERARCHY & SPECIFIC TASK ASSIGNMENT
================================================================================
- Level 1: Task 3: Implement Dynamic Quadrature Lifecycle & Electronic Sanitization Plane (VR-03, VR-05) - DEFGRID1-3 progression with Coupled Grid-SCF Invariant, dispersion sanitization (VV10 vs D3/D4), spin purity gatekeeper (Delta S^2 < 10%), and Product B/M ontological disambiguation. [M]
- Level 2: Established technical roadmap for Product B (parent-anchored microwave) vs Product M (solid-state materials) ontological disambiguation. [GOV]
- Specific Task to Execute:
  3.3.3 - Formalized L3 component tasks for Execution Engine & HPC Workflow Router Decoupling Plane (L3.3.1 - L3.3.3). [GOV] / [DOC]

================================================================================
2. MANDATORY RULE 1: INGEST EXISTING PROJECT FILES VIA TOOLS (DO NOT GUESS)
================================================================================
Before compiling or formalizing any specifications, you MUST explicitly invoke your filesystem inspection tools (view_file, grep_search, list_dir, find_by_name) to inspect existing physical files on disk to establish full empirical context:

1. Method Matrix Baselines & Execution Topology Governance:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md (and Method_Matrix/Method_Matrix_Hub.md):
     * §1.2 & §3.2: Product B (parent-anchored microwave spectroscopy, Recipe R6, equilibrium scaling to experimental rotational constants A_0, B_0, C_0, calibrated shift uncertainty <= 0.06%, tight conformal search window +/- 0.05%).
     * §2.2: Product M (solid-state materials, plane-wave pseudopotentials, reciprocal space k-point grid evaluations, unit cell volume V_cell > 0, plane-wave cutoffs E_cut >= 400 eV).
     * §8.2 & §8.3: Hardware Crossover & Compute Efficiency (CPU vs GPU crossover boundary at 50-90 basis functions; ORCA CPU-only execution invariant; NVIDIA MPS concurrency ceilings).
     * §8A.2: Scout-and-Anchor Topology (rapid conformal scanning vs deep single-point anchor optimizations).
     * §8A.6: Parsl Multi-Executor Architecture (isolated scratch directories, CPU core pinning, OpenMP threads, Slurm cluster bindings).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/CoChem_User_Manual.md:
     * Inspect lines 203-220 (Product M materials, bandgap <= 0.1 eV, lattice <= 0.01 Angstrom, stress tensor, PAW pseudopotentials).
   - D:/__CoChem/__agentic/dropzones/inbox_srs/SRS_Chunk_17.md:
     * Section 3 & Section 5: Architectural Workflow and Ontological Disambiguation.

2. Existing Codebase Execution Routers & Calculators:
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py (ExecutionRouter, Parsl multi-executor topologies, JobRouteConfig, ExecutionRouteResult).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/calc/cochem_calc_input_generator.py (ORCA deck generation, keyword composition).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/exceptions.py (CoChemError, GridSpecificationError, RedundantDispersionError, MissingDispersionError, SpinContaminationError).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/isotopes.py (Dynamic Mendeleev mass resolution mandate; strict ban on static mass dictionaries).
   - D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/validators/preflight.py (Preflight geometry and keyword validation).

3. Preceding Planning, Traceability & Audit Baselines:
   - D:/__CoChem/.docs/task3_level2_wbs_breakdown.md (Council Session 041 Ratified Master Baseline, SHA-256: 48E92125C69DFD5E8F0D6C1A5473A31FFCA4472C5E4BC946B13EF30E74DDB97F).
   - D:/__CoChem/.docs/task3_2_1_vr03_vr05_l3_decomposition.md (Council Session 042 Ratified Baseline, SHA-256: EA73F8D91B9C4D4251AF9BCEDEDC8F9E5A79C103EB646915FB05A5EFD943D6BF).
   - D:/__CoChem/.docs/Task3_VR03_VR05_Traceability_Matrix.md (Council Session 044 Ratified Baseline, SHA-256: 0235C268731857DBB0B28763852F554D326E0A958241BCC7276B0E4EB9513559).
   - D:/__CoChem/.docs/task3_3_1_dispatch_prompt.md (Council Session 045 Ratified Dispatch Baseline, SHA-256: B47280F2E87DABDE81902541FCFD81937966C95F484CA9C1DC35FF7E2590DA32).
   - D:/__CoChem/swarm_state.json (Swarm State Ledger).

You are STRICTLY FORBIDDEN from assuming file paths, guessing parameter thresholds, or hallucinating data structures without reading the physical files on disk first.

================================================================================
3. TECHNICAL SCOPE & SPECIFICATION MANDATES FOR L3.3.1 - L3.3.3
================================================================================
You must formulate a publication-grade, fail-closed technical specification formalizing the three subordinate component tasks comprising Plane 3 (Execution Engine & HPC Workflow Router Decoupling Plane). Each component task specification must satisfy the PMBOK 100% Rule and MECE principles, establishing:

--------------------------------------------------------------------------------
Task L3.3.1: Quantum Chemistry Backend Execution Engine Decoupling
--------------------------------------------------------------------------------
- Target Module: D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/executors/quantum_chemistry_engine.py
- Assigned Implementing Agent: @cochem-coder (downstream execution)
- Domain Scope:
  * Class: `QuantumChemistryEngine` with complete Python 3.10+ typing (`from __future__ import annotations`).
  * Target Quantum Chemistry Backends: ORCA 5.0/6.0, CFOUR, CREST, and CENSO.
  * Architectural Execution Invariants:
    - Dedicated to isolated molecular gas-phase simulations (Product B, Product A, Product C).
    - Single-node Symmetric Multiprocessing (SMP) parallelization strictly configured via `%pal nprocs N end` (bounded by physical host cores: 1 <= nprocs <= os.cpu_count()).
    - Method Matrix §8.2 CPU-Bound Invariant: ORCA is strictly CPU-only. The engine MUST reject any attempt to inject GPU acceleration or CUDA device parameters into ORCA execution decks.
    - Memory Management: Rigorously calculate per-core memory allocation `%maxcore M` (in MB) where M = floor((total_physical_ram_mb * 0.80) / nprocs), preventing out-of-memory (OOM) kernel crashes.
    - Ephemeral Sandbox Isolation: Execute all calculation subprocesses inside a sterile, isolated scratch directory (`$COCHEM_SCRATCH/task_<uuid>/` or `pathlib.Path.home() / ".cochem" / "scratch" / f"task_{uuid4().hex}"`).
    - Subprocess Safety & Zombie Reaping: Wrap all external process executions in `subprocess.Popen` / `subprocess.run` supervised by `psutil` monitors, enforcing wall-clock timeouts, strict exit code evaluation, and automated cleanup handlers.
    - Fail-Closed Error Wrapping: Catch engine aborts, SCF divergence, or disk-full errors, wrapping them in typed domain exceptions (`QuantumExecutionError`, `ORCAExecutionError`).
  * Domain Boundary Mutual Exclusivity:
    - Validator MUST fail closed and reject any job payload containing periodic parameters (`pbc`, `lattice_vectors`, `kpoints`, `cutoff_energy`, multi-node MPI configurations) with `OntologicalCollisionError`.
  * Mendeleev Dynamic Mass Mandate:
    - Ingest Cartesian coordinates and compute inertial frames strictly utilizing dynamic atomic masses retrieved via `from mendeleev import element` [M].

--------------------------------------------------------------------------------
Task L3.3.2: Solid-State Periodic Execution Engine Decoupling
--------------------------------------------------------------------------------
- Target Module: D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/executors/materials_execution_engine.py
- Assigned Implementing Agent: @cochem-coder (downstream execution)
- Domain Scope:
  * Class: `MaterialsExecutionEngine` with complete Python 3.10+ typing.
  * Target Solid-State Materials Backends: VASP (`vasp_std`), Quantum ESPRESSO (`pw.x`), CP2K.
  * Architectural Execution Invariants:
    - Dedicated to periodic extended systems and solid-state materials (Product M).
    - Multi-Node Distributed-Memory MPI Parallelization: Support execution via Message Passing Interface (`mpirun -np N vasp_std` or `srun pw.x`).
    - HPC Workload Scheduler Integration: Automated generation of standardized SLURM submission scripts (`sbatch`):
      * `#SBATCH --job-name=cochem_mat_<id>`
      * `#SBATCH --nodes=N` (N >= 1)
      * `#SBATCH --ntasks-per-node=M`
      * `#SBATCH --cpus-per-task=C`
      * `#SBATCH --time=HH:MM:SS`
      * `#SBATCH --partition=compute`
    - Reciprocal Space k-Point Parallelization: Partition reciprocal grid points evenly across MPI communicator ranks to maximize parallel efficiency.
    - High-Throughput Checkpointing & Scratch tmpfs: Manage checkpoint files (`WAVECAR`, `CHGCAR`, `.save/` directories) in cluster node-local high-speed scratch storage (`/tmp` or `$TMPDIR`), staging final observables back to the central repository.
    - Fail-Closed Error Handling: Monitor job status via `squeue` / `sacct`, handle node preemption, convergence stalling, and MPI rank failure, wrapping faults in typed domain exceptions (`MaterialsExecutionError`, `SLURMSubmissionError`, `MPIExecutionError`).
  * Domain Boundary Mutual Exclusivity:
    - Validator MUST fail closed and reject any molecular gas-phase parameters (rotational constants $A_0, B_0, C_0$, Eckart frame orientation, planar moments, inertial defect $\Delta$) with `OntologicalCollisionError`.

--------------------------------------------------------------------------------
Task L3.3.3: HPC Workflow Router & Execution Isolation Plane
--------------------------------------------------------------------------------
- Target Module: D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/executors/hpc_workflow_router.py
- Assigned Implementing Agent: @cochem-coder (downstream execution)
- Domain Scope:
  * Class: `HpcWorkflowRouter` (refactoring and cleanly decoupling `cochem_calc_execution_router.py`).
  * Strict Air-Gap Workflow Routing:
    - Inspect incoming calculation request schema:
      * If `category in {ProductCategory.PRODUCT_B, ProductCategory.PRODUCT_A, ProductCategory.PRODUCT_C}` and `domain == CalculationDomain.MOLECULAR_GAS_PHASE`:
        Route exclusively to `QuantumChemistryEngine`. Disallow distributed multi-node SLURM submission unless explicitly configured for single-node SMP embarrassingly parallel conformer sweeps.
      * If `category == ProductCategory.PRODUCT_M` and `domain == CalculationDomain.PERIODIC_SOLID_STATE`:
        Route exclusively to `MaterialsExecutionEngine`. Forbid un-accelerated local single-threaded execution if system size exceeds single-node capacity.
    - Domain Collision Interceptor:
      * If a payload exhibits ontological mixing (e.g. periodic boundary conditions submitted to ORCA, or gas-phase microwave conformer submitted to VASP plane-wave engine), immediately intercept and raise `OntologicalRoutingCollisionError` with detailed diagnostic payload before launching any external subprocess.
  * Hardware Crossover & Resource Attribution Governance:
    - Adhere strictly to Method Matrix §8.2, §8.3, §8A.4:
      * Systems with <= 50–90 basis functions route to CPU anchor pools; MLFF rapid scans route to GPU scout pools.
      * Require explicit resource attribution metadata attached to all dispatched jobs (process ID, node hostname, allocated memory, CPU mask, execution start/end timestamps).
    - Asymmetric Sterile Quarantine Support:
      * Enable routing of verification jobs into `/tmp/cochem_exec_<uuid>/` quarantine directories for zero-trust validation by `cochem-audit`.

--------------------------------------------------------------------------------
Mandatory Content Structure for Each L3 Formalization:
--------------------------------------------------------------------------------
For Each L3 Task (L3.3.1, L3.3.2, L3.3.3), Your Formalization Must Explicitly Document:
1. Work Package Unique Identifier & Descriptive Title.
2. Single Responsible Execution Agent (@cochem-coder).
3. Primary Targeted Codebase File Path (in `src/cochem_base/executors/`).
4. Exact Input Preconditions & Prerequisites.
5. Concrete Deliverables (classes, methods, Pydantic schemas, exception classes, exports).
6. Quantitative Acceptance Criteria, Mathematical Invariants, and Numerical Tolerances.
7. Explicit Provenance Tags ([M] Method Matrix, [D] Deterministic Derivation, [E] Empirical Benchmark).
8. Upstream Predecessors & Downstream Dependencies.
9. Verification Method & Test Suite Target (e.g., `tests/test_hpc_workflow_router.py` and `tests/test_quantum_materials_executors.py`).

================================================================================
4. MANDATORY OPERATIONAL RULE 2: PHYSICAL DISK PERSISTENCE ACROSS MIRRORS
================================================================================
You are STRICTLY FORBIDDEN from presenting your work solely in conversational chat text or temporary memory buffers. You MUST invoke your `write_to_file` tool (with Overwrite=true) to persist your output directly to disk across all designated mirror locations:

1. Primary Scratch Deliverable:
   `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_3_3_execution_engine_hpc_router_plane.md`

2. Conversation Artifact Mirror:
   `C:/Users/ansac/.gemini/antigravity-cli/brain/db89ca53-89e4-40c6-b191-be4bcfbf55e5/task3_3_3_execution_engine_hpc_router_plane.md`

3. Repository Docs Mirror:
   `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/Task3_3_3_Execution_Engine_HPC_Router_Plane.md`

4. Ecosystem Master Mirror:
   `D:/__CoChem/.docs/Task3_3_3_Execution_Engine_HPC_Router_Plane.md`

5. Dropzone SRS Mirror:
   `D:/__CoChem/__agentic/dropzones/inbox_srs/Task3_3_3_Execution_Engine_HPC_Router_Plane.md`

6. Swarm State Ledger Synchronization:
   Update `swarm_state.json` across all canonical mirrors (`scratch/`, `D:/__CoChem/`, `D:/__CoChem/GitHub-Repo/CoChem-BASE/`, and dropzones) recording:
   * task_id: "TASK-3-3-3-EXECUTION-ENGINE-HPC-ROUTER-DECOUPLING-PLANE"
   * task_hierarchy: "Level 1 Task 3 -> Level 2 Roadmap Product B vs M -> Level 3 Task 3.3.3"
   * agent_name: "cochem-sdp-manager"
   * status: "SUCCESS"
   * pmbok_100_percent_rule_enforced: true
   * mece_decomposition_guaranteed: true
   * raci_enforced: true
   * artifacts_produced: list of persisted file paths
   * byte_counts and line_counts
   * sha256_checksums: calculated via `Get-FileHash -Algorithm SHA256` using `run_command`
   * audit_status: "PENDING_ASYMMETRIC_AUDIT" (auditors: ["cochem-audit", "adversary"])

7. Anti-Spoofing Zero-Token Gate:
   Ensure the persisted markdown specifications contain zero unelaborated routines, zero empty return blocks, zero fake fixtures, and zero forbidden placeholder tokens:
   `mock`, `dummy`, `stub`, `fake`, `placeholder`, `sample`, `NotImplementedError`, `pass`, `TODO`, `TBD`, `FIXME`.

================================================================================
5. MANDATORY OPERATIONAL RULE 3: RETURN FINAL REPORT WITH INODE CHECKSUMS
================================================================================
Upon completing file creation, disk persistence, checksum calculation, and ledger synchronization, you MUST return a comprehensive final text report in your conversational response.
Your report MUST begin with `[SDPM REPORT]` and conclude with `[VERIFICATION & HANDOFF SUMMARY]` detailing:
1. High-level execution status (SUCCESS).
2. The EXACT physical file paths created or modified on disk.
3. Total line counts and physical byte sizes of all created/modified files on disk.
4. Exact computed SHA-256 cryptographic digest of each file.
5. Confirmation of zero literal banned keywords confirmed by automated static inspection.
6. Confirmation of dynamic Mendeleev mass retrieval enforcement throughout the schema specifications.
7. Verification that Asymmetric Council Sign-off remains pending (`- [ ] Pending independent Agent Council audit`).
8. Formal handoff routing for `cochem-audit` and `adversary` to execute the downstream asymmetric audit.
```

---

## 3. Downstream Swarm Handoff & Asymmetric Audit Protocol

Once `cochem-sdp-manager` completes formalization of this dispatch prompt and reports its created files and SHA-256 digests:
1. **Asymmetric Audit Routing:** As `0rchestrator`, natively spin up `cochem-audit` and `adversary` sequentially via `invoke_subagent` (prioritizing Antigravity quota over external API calls).
2. **Verification Criteria:** The auditors will inspect all formalized artifacts against the 10-point audit checklist:
   - Complete formalization of L3.3.1, L3.3.2, and L3.3.3 adhering to PMBOK 100% Rule and MECE principles.
   - Decoupled `QuantumChemistryEngine` enforcing single-node SMP, CPU-bound invariants, memory bounds, and sterile scratch directories.
   - Decoupled `MaterialsExecutionEngine` enforcing multi-node distributed MPI, SLURM batch job integration, k-point partitioning, and checkpoint handling.
   - `HpcWorkflowRouter` enforcing strict air-gapped domain isolation and hardware crossover boundaries.
   - Fail-closed domain boundary mutual exclusivity between molecular gas-phase and periodic solid-state regimes.
   - Dynamic Mendeleev atomic and isotopic mass retrieval mandate throughout.
   - Total eradication of mocks, stubs (`NotImplementedError`, empty `pass`), and synthetic fixtures.
   - Cryptographic byte-for-byte parity across all canonical mirror locations and `swarm_state.json`.

---

## 4. Document Control & Ledger Synchronization Table

| Field | Primary Scratch Specification | Conversation Artifact Record | Repository Mirror Record | Ecosystem Mirror Record | Dropzone Mirror Record |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Physical File Path** | `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_3_3_dispatch_prompt.md` | `C:/Users/ansac/.gemini/antigravity-cli/brain/db89ca53-89e4-40c6-b191-be4bcfbf55e5/task3_3_3_dispatch_prompt.md` | `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task3_3_3_dispatch_prompt.md` | `D:/__CoChem/.docs/task3_3_3_dispatch_prompt.md` | `D:/__CoChem/__agentic/dropzones/inbox_srs/task3_3_3_dispatch_prompt.md` |
| **Authoring Agent** | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` |
| **Designated Execution Agent** | `cochem-sdp-manager` | `cochem-sdp-manager` | `cochem-sdp-manager` | `cochem-sdp-manager` | `cochem-sdp-manager` |
| **Supervising Authority** | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` | `0rchestrator` |
| **Lifecycle Status** | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` | `APPROVED_FOR_BASELINE_EXECUTION` |
| **Governing Standards** | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 | PMBOK 7th Ed, SWEBOK v3/v4, Method Matrix v4.1, Anti-Spoofing v4 |
