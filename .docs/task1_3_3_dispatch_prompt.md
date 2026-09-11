# Task 1.3.3 Dispatch Specification: 17 L3 Implementation Microtasks Decomposition

**Parent Task:** Level 1: Task 1: Implement Ingestion Plane & Physical Invariant Foundation (VR-01) - Dynamic Mendeleev mass queries, Eckart frame translation/rotation zeroing, and two-stage conformer deduplication with automorphism invariance.  
**Level 2 Task:** Decompose Level 1 task into granular Level 2 technical tasks and Level 3 microtasks  
**Specific Task to Execute:** `1.3.3 - Decomposed the L2 task into 17 highly specific, component-level L3 implementation microtasks with explicit contracts, assigned agents, and anti-spoofing verification criteria`  
**Exact Execution Agent:** `cochem-sdp-manager`  
**Canonical Dispatch File:** [`task1_3_3_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/brain/9f4957f6-5462-4722-bf15-c860d758111e/task1_3_3_dispatch_prompt.md)  
**Target Persistence File:** [`task1_l3_17_microtasks_decomposition.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_l3_17_microtasks_decomposition.md)  

---

## 1. Execution Agent Selection

**Designated Execution Agent:** `cochem-sdp-manager`

### Authoritative Justification:
1. **Taxonomy & Domain Authority:**  
   Under the CoChem Agent Council Protocol and Multi-Agent taxonomy, `cochem-sdp-manager` (Software Development Project Manager) is the sole authoritative agent tasked with applying PMBOK 7th Edition (Systems View for Project Delivery) and SWEBOK v3 (Software Requirements and Software Architecture) principles. It translates high-level engineering mandates into structured systems architecture, Work Breakdown Structures (WBS), and granular L3 implementation microtasks.
2. **Microtask Decomposition & RACI Role:**  
   Task 1.3.3 explicitly requires decomposing Level 2 technical tasks into 17 highly specific, component-level L3 implementation microtasks with explicit contracts, assigned agents, mathematical tolerances, and anti-spoofing verification criteria. Establishing work package boundaries, single-accountable RACI assignments, and verification thresholds is a core project planning and systems engineering responsibility—strictly segregated from application code authoring (`cochem-coder`), test execution (`cochem-tester`), or red-team audits (`adversary` / `cochem-audit`).
3. **Historical Ledger Parity:**  
   `cochem-sdp-manager` authored all preceding ratified WBS breakdown deliverables in the project repository:
   - Task 1.2.5: [`task1_2_5_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_5_dispatch_prompt.md)
   - Task 1.3.1: Predecessor scope analysis verified in [`adversary_task1_3_1_prompt_audit_report.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task1_3_1_prompt_audit_report.md)
   - Task 1.3.2: [`task1_3_2_dispatch_prompt.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_2_dispatch_prompt.md)
   - Task 2 WBS: [`task2_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md)
   - Task 3 WBS: [`task3_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md)
   - Task 5 WBS: [`task5_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md)  
   Assigning Task 1.3.3 to `cochem-sdp-manager` guarantees architectural continuity, single-agent accountability, and PMBOK 100% / MECE compliance.

---

## 2. Authoritative Dispatch Prompt for `cochem-sdp-manager`

```markdown
[SDPM EXECUTION ORDER: TASK 1.3.3 - 17 L3 IMPLEMENTATION MICROTASKS DECOMPOSITION]

You are cochem-sdp-manager, the Software Development Project Manager for the CoChem Agent Council. You apply PMBOK 7th Edition and SWEBOK v3 principles to structure engineering objectives into formal, actionable, zero-mock Work Breakdown Structures (WBS) and component-level microtasks.

================================================================================
PROJECT HIERARCHY & TASK ASSIGNMENT
================================================================================
- Level 1: Task 1: Implement Ingestion Plane & Physical Invariant Foundation (VR-01) - Dynamic Mendeleev mass queries, Eckart frame translation/rotation zeroing, and two-stage conformer deduplication with automorphism invariance.
- Level 2: Decompose Level 1 task into granular Level 2 technical tasks and Level 3 microtasks.
- Specific Task to Execute:
  1.3.3 - Decomposed the L2 task into 17 highly specific, component-level L3 implementation microtasks with explicit contracts, assigned agents, and anti-spoofing verification criteria.

================================================================================
CRITICAL DIRECTIVE 1: MANDATORY CONTEXT INGESTION VIA TOOLS (DO NOT GUESS)
================================================================================
Before synthesizing any decomposition or microtasks, you MUST use your file inspection tools (`view_file`, `grep_search`, `list_dir`, `find_by_name`) to inspect the local filesystem and establish complete empirical context:
1. Examine existing ratified WBS breakdown artifacts for structural standards, schema definitions, and formatting conventions:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task2_level2_wbs_breakdown.md`
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task3_level2_wbs_breakdown.md`
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task5_level2_wbs_breakdown.md`
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_2_dispatch_prompt.md`
2. Inspect the current swarm ledger to verify completed tasks and pending dependencies:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json`
3. Inspect preceding audit reports and specifications for Task 1:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/adversary_task1_3_1_prompt_audit_report.md`
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_2_5_dispatch_prompt.md`
4. Inspect existing domain implementation files if accessible:
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/isotopes.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/intake/conformer_deduplication.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/intake/cochem_molsym_eckart_aligner.py`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_chunk17_verification_suite.py`

You are STRICTLY FORBIDDEN from guessing file structures, hallucinating frontmatter, or fabricating data models. Gain full empirical context from these files first.

================================================================================
TECHNICAL SCOPE: THE 17 COMPONENT-LEVEL L3 MICROTASKS OF VR-01
================================================================================
You must decompose Level 1 Task 1 (VR-01) into exactly seventeen (17) highly specific, component-level L3 implementation microtasks. Each microtask must specify:
1. Unique Task ID (e.g., `L3-T1-01` through `L3-T1-17`)
2. Microtask Title & Purpose
3. Single Accountable Assigned Execution Agent (e.g., `cochem-coder`, `cochem-tester`, `cochem-sdp-manager`, `researcher`, `cochem-audit`, `adversary`)
4. Supervising / Verifying Agent
5. Explicit Input Contracts (predecessor outputs, mathematical formulations, domain constraints)
6. Explicit Processing & Implementation Mechanics (algorithms, tensor dimensions, equations, fail-closed handling)
7. Explicit Output Contracts (dataclass models, persistent file artifacts, typed exceptions)
8. Mathematical & Physical Invariant Tolerances (e.g., $\|\sum m_i \mathbf{r}'_i\| < 10^{-12}\text{ a.u.}$, $\det(\mathbf{U}) = +1.0$, $\Delta B_{\text{max}}/B \le 0.05\%$)
9. Anti-Spoofing Verification Criteria (zero stubs, zero `NotImplementedError`, zero `pass`, zero synthetic arrays `np.zeros`/`np.ones`, path-scoped AST linter commands)

The 17 microtasks must span the 5 foundational technical tracks of Task 1 (VR-01):

--- TRACK 1: DYNAMIC MENDELEEV MASS RESOLUTION & NUCLIDE NORMALIZATION (L3-T1-01 TO L3-T1-05) ---
- L3-T1-01: Static Mass Dictionary Audit & Elimination
  * Purpose: Static AST sweep identifying and purging all hardcoded mass dictionaries (`PINNED_STANDARD_ATOMIC_WEIGHTS`, `PINNED_ISOTOPIC_MASSES`, float assignments) from `isotopes.py`.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Anti-Spoofing: AST scanner verifies zero static mass dictionaries or constant tables exist; fails closed if any float table remains.

- L3-T1-02: Dynamic IUPAC Standard Atomic Weight Query Engine
  * Purpose: Implement `get_atomic_mass(symbol)` dynamically fetching standard atomic weights via `from mendeleev import element`.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Invariant: Dynamically retrieves IUPAC standard atomic weights (e.g., C: 12.011 u, O: 15.999 u). Zero hardcoded floats.

- L3-T1-03: Nuclide Alias Parsing & Regex Normalization Engine
  * Purpose: Implement regex pre-processor resolving nuclide aliases (`"D"`, `"T"`, `"13C"`, `"18O"`, `"C-13"`) into IUPAC element symbol and integer mass number before querying `mendeleev`, preventing fatal `KeyError` exceptions.
  * Assigned Agent: `cochem-coder` | Supervising: `adversary`
  * Invariant: Deuterium ($^2\text{H}$) returns $2.0141017778\text{ u}$; $^{13}\text{C}$ returns $13.0033548352\text{ u}$.

- L3-T1-04: Counterpoise Ghost Atom Zero-Mass Guard
  * Purpose: Intercept BSSE counterpoise ghost symbols (`"Gh"`, `"Bq"`, `"X"`, case-insensitive) in `get_atomic_mass()` and return exact $0.0\text{ u}$ without crashing or issuing external database queries.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Invariant: Ghost symbols return exact float $0.0$; non-physical non-ghost symbols raise `InvalidNuclideSpecificationError`.

- L3-T1-05: Thread-Safe In-Memory Mass Cache Architecture
  * Purpose: Implement a thread-safe in-memory cache (`_MASS_CACHE: Dict[Tuple[str, Optional[int]], float]`) to eliminate SQLite query latency overhead ($2.5-5.0\text{ ms}$ reduced to $< 1\ \mu\text{s}$ per lookup).
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-sdp-manager`
  * Invariant: Cache is strictly read-only after dynamic population; retrieval latency $< 1\ \mu\text{s}$.

--- TRACK 2: MASS-WEIGHTED CENTER-OF-MASS INVARIANT & TRANSLATION ZEROING (L3-T1-06 TO L3-T1-07) ---
- L3-T1-06: Center-of-Mass Coordinate Calculation & Translation Shift Operator
  * Purpose: Compute mass-weighted center of mass $\mathbf{R}_{\text{COM}} = \sum m_i \mathbf{r}_i / \sum m_i$ and apply the Cartesian translation shift $\mathbf{r}'_i = \mathbf{r}_i - \mathbf{R}_{\text{COM}}$.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Invariant: Net momentum drift satisfies $\|\sum m_i \mathbf{r}'_i\|_2 < 1.0 \times 10^{-12}\text{ a.u.}$ executed in IEEE 754 float64 precision.

- L3-T1-07: Center-of-Mass Invariant Precision Validator & Float64 Accumulator
  * Purpose: Implement numerical assertion gate validating float64 accumulation and enforcing strict tolerance checks on translated geometries.
  * Assigned Agent: `cochem-coder` | Supervising: `adversary`
  * Invariant: Fail-closed assertion: raises `EckartAlignmentError` if $\|\sum m_i \mathbf{r}'_i\| \ge 1.0 \times 10^{-12}\text{ a.u.}$; rejects synthetic zero-padding.

--- TRACK 3: MASS-WEIGHTED ECKART FRAME ALIGNMENT & SO(3) ROTATION (L3-T1-08 TO L3-T1-11) ---
- L3-T1-08: Reference Geometry Mass-Weighted Covariance (Gram) Matrix Accumulator
  * Purpose: Accumulate the mass-weighted covariance Gram matrix $\mathbf{F} = \sum m_i \mathbf{r}_i (\mathbf{r}_i^0)^T = \mathbf{R}^T \mathbf{M} \mathbf{R}^0 \in \mathbb{R}^{3 \times 3}$.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Invariant: Full double-precision matrix accumulation using dynamic masses; handles planar and linear geometries without rank deficiency crashes.

- L3-T1-09: Singular Value Decomposition (SVD) Gram Matrix Factorization
  * Purpose: Perform SVD factorization $\mathbf{F} = \mathbf{V} \mathbf{\Sigma} \mathbf{W}^T$ to extract orthogonal basis components $\mathbf{V}, \mathbf{W} \in \mathrm{O}(3)$.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Invariant: Singular values ordered $\sigma_1 \ge \sigma_2 \ge \sigma_3 \ge 0$; numerically stable on ill-conditioned configurations.

- L3-T1-10: Proper $\mathrm{SO}(3)$ Rotation Enforcement & Reflection Inversion Gate
  * Purpose: Construct the proper rotation matrix $\mathbf{U} = \mathbf{V} \operatorname{diag}(1, 1, \det(\mathbf{V}\mathbf{W}^T)) \mathbf{W}^T$ to eliminate unphysical mirror reflections ($\det = -1.0$).
  * Assigned Agent: `cochem-coder` | Supervising: `adversary`
  * Invariant: Mathematical acceptance gate asserts $\det(\mathbf{U}) = +1.000000 \pm 10^{-12}$ and $\mathbf{U}^T \mathbf{U} = \mathbf{I}_3$; raises `ImproperRotationError` on improper operations.

- L3-T1-11: Rotational Eckart Vector Condition & Coriolis Decoupling Residual Auditor
  * Purpose: Evaluate the rotational Eckart vector condition $\mathcal{E}_{\text{rot}} = \sum m_i (\mathbf{r}_i^0 \times \mathbf{r}_i)$ to guarantee decoupling of vibrational and rotational degrees of freedom.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Invariant: Residual angular momentum norm $\|\mathcal{E}_{\text{rot}}\|_2 < 1.0 \times 10^{-10}\text{ a.u.}$; decoupling Coriolis torque amplification.

--- TRACK 4: TWO-STAGE CONFORMER DEDUPLICATION PIPELINE (L3-T1-12 TO L3-T1-16) ---
- L3-T1-12: Active Thermodynamic Energy Window Pre-Filter
  * Purpose: Implement active thermodynamic candidate pruning filtering out conformers with $\Delta E = E_{\text{cand}} - E_{\text{global\_min}} > 12.0\text{ kcal/mol}$ prior to topological or geometric sieving.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-sdp-manager`
  * Invariant: High-energy unphysical structures are discarded immediately; zero wasted compute in graph or Kabsch analysis.

- L3-T1-13: Stage 1 Covalent Bond Graph Construction (1.28 Radii Multiplier Baseline)
  * Purpose: Build the molecular connectivity graph $G = (V, E)$ using covalent radii sums scaled by the standardized $1.28$ multiplier ($d(i, j) \le 1.28 \times (r_{\text{cov}}(i) + r_{\text{cov}}(j))$).
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-audit`
  * Invariant: Strict adjacency generation; documents $1.25$ strict variant for high-strain rings; rejects heuristic arbitrary cutoffs.

- L3-T1-14: Stage 1 Weisfeiler-Lehman (WL) 3-Iteration Graph Automorphism Hasher
  * Purpose: Implement 1-WL color refinement across $h=3$ iterations to produce canonical topological hash digest $H_{\text{WL}}(G)$ invariant to atomic indexing permutations.
  * Assigned Agent: `cochem-coder` | Supervising: `adversary`
  * Invariant: If $H_{\text{WL}}(G_1) \neq H_{\text{WL}}(G_2)$, structures are distinct constitutional isomers/topologies and bypass geometric sieving.

- L3-T1-15: Stage 2 Horn Quaternion Kabsch RMSD Superposition Filter
  * Purpose: Compute minimum Cartesian RMSD using the $4 \times 4$ key matrix $\mathbf{K}$ and optimal rotation quaternion $\mathbf{q}^*$.
  * Assigned Agent: `cochem-coder` | Supervising: `cochem-tester`
  * Invariant: Spatial clustering cutoff $\tau_{\text{RMSD}} = 0.0800\text{ \AA}$; rigorously superimposes geometries without reflection artifacts.

- L3-T1-16: Tri-Axial Spectroscopic Degeneracy Sieve ($\Delta B_{\text{max}}/B \le 0.05\%$) & Combinatorial Limiter
  * Purpose: Evaluate relative rotational constant deviations across all three axes ($\max(|A_1-A_2|/\bar{A}, |B_1-B_2|/\bar{B}, |C_1-C_2|/\bar{C}) \le 0.05\%$) with Hungarian matching fallback (`linear_sum_assignment`) when orbit permutations $> 720$.
  * Assigned Agent: `cochem-coder` | Supervising: `adversary`
  * Invariant: Dual-collapse condition ($\text{RMSD} < 0.08\text{ \AA} \land \Delta B_{\text{max}}/B \le 0.05\%$); preserves distinct van der Waals isomers with shearing; protects against $N!$ factorial explosion.

--- TRACK 5: DATA CONTRACTS, ZERO-MOCK VERIFICATION & STATE INTEGRATION (L3-T1-17) ---
- L3-T1-17: Domain Exception Hierarchy, Typed Dataclass Models & Authentic Pytest Verification Matrix
  * Purpose: Implement typed exception hierarchy (`EckartAlignmentError`, `ImproperRotationError`, `InvalidNuclideSpecificationError` in `cochem_base.exceptions`), backwards-compatible `EckartAlignmentResult` and `ConformerCandidate` dataclasses, authentic multi-system pytest suite (`test_chunk17_verification_suite.py` with real $\text{H}_2\text{O}$, $\text{CO}_2\cdots\text{H}_2\text{O}$, and isotopologues), and path-scoped AST anti-spoof linter execution.
  * Assigned Agent: `cochem-coder` (Models/Exceptions), `cochem-tester` (Pytest Suite), `cochem-audit` / `adversary` (Asymmetric Audit) | Supervising: `0rchestrator`
  * Invariant: 100% tests execute against physical molecules; zero synthetic arrays (`np.zeros`, `np.ones`); AST anti-spoof linter verifies 0 stubs and 0 violations.

================================================================================
CRITICAL DIRECTIVE 2: WRITE FINAL CODE / RESULTS TO ACTUAL FILES ON DISK
================================================================================
You are STRICTLY FORBIDDEN from merely outputting the decomposition into conversational standard output or markdown reply buffers.
You MUST use your filesystem authoring tools (`write_to_file`) to persist the complete, professional, unabridged L3 microtask specification directly to physical disk at:
- Target Deliverable: `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_l3_17_microtasks_decomposition.md`
- Master WBS Integration: Update `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_level2_wbs_breakdown.md`
- Swarm Ledger Update: Atomically update `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json` with the canonical metadata schema:
  ```json
  {
    "agent_name": "cochem-sdp-manager",
    "timestamp": "<CURRENT_TIMESTAMP>",
    "status": "COMPLETED",
    "task": "Task 1.3.3: Decomposed L2 task into 17 highly specific, component-level L3 implementation microtasks with explicit contracts, assigned agents, and anti-spoofing verification criteria",
    "wbs_level": "L3 Component-Level Microtask Breakdown",
    "microtasks_count": 17,
    "raci_enforced": true,
    "provenance_tags_sanitized": true,
    "anti_spoofing_compliance": true,
    "artifacts_produced": [
      "C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_l3_17_microtasks_decomposition.md",
      "C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_level2_wbs_breakdown.md"
    ],
    "sha256_checksum": "<SHA256_DIGEST>"
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
5. High-level summary of the 17 component-level microtasks, their input/output contracts, and their assigned execution agents.
6. Formal handoff notice for `cochem-audit` and `adversary` for independent asymmetric verification.

================================================================================
ANTI-SPOOFING & ZERO-MOCK MANDATE (ANTI-SPOOFING DIRECTIVE v4)
================================================================================
- Strictly eradicate mocks, stubs, dummy loops, and fake data structures.
- Do NOT use `NotImplementedError` or empty `pass` blocks as dead-end stubs.
- Do NOT use synthetic array generators (`np.zeros`, `np.ones`, `np.eye`) to fake state tensors or coordinate matrices.
- Do NOT use shortcut tag-appending (e.g., `[AUDITOR FIX REQUIRED]`); deliver complete, production-grade microtask specifications.
```
