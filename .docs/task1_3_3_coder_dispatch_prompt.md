# Task 1.3.3 Dispatch Specification: `cochem-coder` Implementation of L2-T1.1 through L2-T1.4 Core Intake Algorithms

**Document Identifier:** `COCHEM-DISPATCH-TASK1-3-3-CODER-INTAKE-2026` [M]  
**Document Version:** 1.0.0 (Authoritative Council Dispatch Specification) [M]  
**Council Session:** `COUNCIL-SESSION-074` [GOV]  
**Session Alias:** `Council Session 074 - Dispatch and Execution of Task 1.3.3 Core Intake Algorithms` [GOV]  
**Resolution ID:** `COCHEM-COUNCIL-RES-074-TASK1-3-3-CODER-INTAKE-DISPATCH-RATIFIED-20260911` [GOV]  
**Parent Task Hierarchy:**  
- **Level 1:** Task 1: Implement Ingestion Plane & Physical Invariant Foundation (VR-01) — Dynamic Mendeleev mass queries, Eckart frame translation/rotation zeroing, and two-stage conformer deduplication with automorphism invariance [M].  
- **Level 2 Technical Packages Dispatched:**  
  - `L2-T1.1`: Dynamic Mendeleev Mass Resolution & Nuclide Alias Engine [M]  
  - `L2-T1.2`: Mass-Weighted Center-of-Mass Translation Zeroing Engine [M]  
  - `L2-T1.3`: Mass-Weighted Eckart Frame Alignment & SO(3) Rotation Engine [M]  
  - `L2-T1.4`: Two-Stage Conformer Deduplication Pipeline (Topological Automorphism + Metric Filter) [M]  
- **Specific Task Executed:** `1.3.3 - Implemented and verified L2-T1.1 through L2-T1.4 core intake algorithms with exact physical invariants and Hungarian fallback` [M]  
**Designated Execution Agent:** `cochem-coder` (Autonomous Implementation & Feature Construction Agent, CoChem Council) [M]  
**Supervising Swarm Authority:** `0rchestrator` (Council Presidium Leader & Execution Router) [M]  
**Primary Forensic Auditor:** `cochem-audit` (Autonomous QA, Code Standards & Architectural Compliance Agent) [M]  
**Independent Hostile Auditing Authority:** `adversary` (Hostile Red-Team Meta-Auditor & Counter-Forensic Verifier) [M]  
**Consulted Scientific Authority:** `researcher` (Physical Invariants, IUPAC Standards & Literature Benchmarks) [M]  
**Governing Charters:** Method Matrix v4.1 (§2.3, §3.3, §6.10), Anti-Spoofing Protocol v4 Directives 1–14, Mendeleev Library Mandate, PMBOK Guide 7th Edition, SWEBOK v3/v4 [M]  
**Target Source Modules:**  
- `src/cochem_base/physics/isotopes.py` (L2-T1.1) [M]  
- `src/cochem_base/intake/cochem_molsym_eckart_aligner.py` (L2-T1.2 & L2-T1.3) [M]  
- `src/cochem_base/intake/conformer_deduplication.py` (L2-T1.4) [M]  
- `tests/test_chunk17_verification_suite.py` (L2-T1.6 Verification Harness) [M]  
**Canonical Persistence Mirrors:**  
- `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_3_3_coder_dispatch_prompt.md` [M]  
- `D:/__CoChem/.docs/task1_3_3_coder_dispatch_prompt.md` [M]  
- `D:/__CoChem/__agentic/dropzones/inbox_srs/task1_3_3_coder_dispatch_prompt.md` [M]  
- `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task1_3_3_coder_dispatch_prompt.md` [M]  
**Timestamp:** `2026-09-11T09:18:00-05:00` [M]  

---

## 1. Executive Scope & RACI Segregation of Duties

Pursuant to **PMBOK Guide 7th Edition (§2.8 Delivery Performance Domain)**, **SWEBOK v3/v4 (Software Construction & Software Quality)**, and the **CoChem Method Matrix v4.1**, this document establishes the binding execution order dispatching **Task 1.3.3: Implementation of Core Intake Algorithms (L2-T1.1 through L2-T1.4)** to `cochem-coder`.

### 1.1 Single-Accountable RACI Allocation
In strict accordance with the Single Accountable Individual Principle and Council Anti-Spoofing Directives:
- **`cochem-coder` (R = Responsible):** Sole authoritative agent tasked with the algorithmic implementation, numerical refinement, and production code construction for L2-T1.1, L2-T1.2, L2-T1.3, and L2-T1.4.
- **`0rchestrator` (A = Accountable):** Presiding Council presidium governing workflow routing, concurrency barriers, state serialization, and final ratification.
- **`cochem-audit` (C/A = Auditor):** Autonomous static AST code standards enforcement, anti-spoofing linting (`ci_tools/anti_spoof_linter.py`), and compliance verification.
- **`adversary` (C/A = Red-Team):** Hostile zero-trust penetration testing, counter-forensic verification, and parity audits.
- **`researcher` (C = Consulted):** Physical constants provenance (NIST CODATA 2022/2026), IUPAC mass tables, and literature benchmark geometries.

```
+========================================================================================================================+
|                                  TASK 1.3.3 WORK PACKAGE RACI ALLOCATION MATRIX                                        |
+----------+-------------------------------------------------------------+-----+-----+-----+-----+-----+-----+----------+
| Package  | Technical Work Package Name                                 | COD | AUD | ADV | RES | SDP | ORC | Role     |
+----------+-------------------------------------------------------------+-----+-----+-----+-----+-----+-----+----------+
| L2-T1.1  | Dynamic Mendeleev Mass Resolution & Nuclide Alias Engine    |  R  |  C  |  I  |  C  |  I  |  A  | Execute  |
| L2-T1.2  | Mass-Weighted COM Translation Zeroing Engine                |  R  |  C  |  I  |  C  |  I  |  A  | Execute  |
| L2-T1.3  | Mass-Weighted Eckart Frame Alignment & SO(3) Rotation Engine|  R  |  C  |  I  |  C  |  I  |  A  | Execute  |
| L2-T1.4  | Two-Stage Conformer Deduplication Pipeline (WL + Hungarian) |  R  |  C  |  I  |  C  |  I  |  A  | Execute  |
| L3-Gov1  | Task 1.3.3 Authoritative Dispatch Specification             |  I  |  C  |  C  |  I  |  C  |  R/A| Dispatch |
| L3-Gov2  | Static AST Anti-Spoofing Compliance Audit                   |  I  |  R  |  C  |  I  |  I  |  A  | Audit    |
| L3-Gov3  | Hostile Zero-Trust Red-Team Verification Audit              |  I  |  C  |  R  |  I  |  I  |  A  | Audit    |
| L3-Gov4  | Atomic Swarm State Synchronization & Council Ratification   |  I  |  I  |  I  |  I  |  I  |  R/A| Ratify   |
+----------+-------------------------------------------------------------+-----+-----+-----+-----+-----+-----+----------+
R = Responsible (Single owner executing work) | A = Accountable (Presiding authority)
C = Consulted (Review and inputs)            | I = Informed (Status update notifications)
```

---

## 2. Technical Work Packages & Target Code Modules

### 2.1 Package L2-T1.1: Dynamic Mendeleev Mass Resolution & Nuclide Alias Engine
- **Target File:** `src/cochem_base/physics/isotopes.py` [M]
- **Governing Directives:** Mendeleev Library Mandate, Method Matrix v4.1 §6.10, Anti-Spoofing Protocol v4 Directive 3 [M].
- **Core Engineering Requirements:**
  1. Complete purge of static mass fallback dictionaries (`PINNED_STANDARD_ATOMIC_WEIGHTS`, `PINNED_ISOTOPIC_MASSES`, `ATOMIC_NUMBERS`). Zero static dictionaries permitted in module AST [M].
  2. Dynamic atomic weight retrieval via `from mendeleev import element` backed by thread-safe `@lru_cache` in-memory caching [M].
  3. Nuclide alias regex normalization: pre-processor tokenizing input strings (`"D"`, `"T"`, `"13C"`, `"18O"`, `"C-13"`) into canonical IUPAC symbol and mass number $A$ before database lookup, resolving Deuterium to $2.0141017778\text{ u}$ and Tritium to $3.0160492779\text{ u}$ [M][D].
  4. Counterpoise / BSSE ghost atom zero-mass protection: `"Gh"`, `"Bq"`, and `"X"` centers allocated exact atomic number $Z=0$ and mass $0.000000000000\text{ u}$ [M].
  5. Fail-closed error handling: strictly raises typed `ValueError` on unresolvable or malformed nuclides. Zero empty `except: pass` blocks permitted [M].

### 2.2 Package L2-T1.2: Mass-Weighted Center-of-Mass Translation Zeroing Engine
- **Target File:** `src/cochem_base/intake/cochem_molsym_eckart_aligner.py` [M]
- **Governing Directives:** Method Matrix v4.1 §2.3.1, SWEBOK v3 Software Construction [M].
- **Core Engineering Requirements:**
  1. High-precision center-of-mass translation in mass-weighted Cartesian coordinates: $\mathbf{r}'_i = \mathbf{r}_i - \mathbf{R}_{\text{COM}}$ [D].
  2. Center-of-mass position vector evaluated via double-precision Kahan compensated summation:
     $$\mathbf{R}_{\text{COM}} = \frac{1}{M} \sum_{i=1}^N m_i \mathbf{r}_i, \quad M = \sum_{i=1}^N m_i \quad [\text{D}]$$
  3. Non-negotiable physical invariant gate:
     $$\left\| \sum_{i=1}^N m_i \mathbf{r}'_i \right\|_2 < 1.0 \times 10^{-12}\text{ a.u.} \quad (1.66 \times 10^{-39}\text{ kg}\cdot\text{m}) \quad [\text{M}]$$

### 2.3 Package L2-T1.3: Mass-Weighted Eckart Frame Alignment & SO(3) Rotation Engine
- **Target File:** `src/cochem_base/intake/cochem_molsym_eckart_aligner.py` [M]
- **Governing Directives:** Method Matrix v4.1 §2.3.1, §10.1–§10.8 [M].
- **Core Engineering Requirements:**
  1. Construction of the mass-weighted Gram covariance matrix between instantaneous centered geometry $\mathbf{R}$ and reference centered geometry $\mathbf{R}^0$:
     $$\mathbf{S} = (\mathbf{R}^0)^T \mathbf{M} \mathbf{R} = \sum_{i=1}^N m_i \mathbf{r}^0_i (\mathbf{r}_i)^T \in \mathbb{R}^{3 \times 3} \quad [\text{D}]$$
  2. Singular Value Decomposition (SVD): $\mathbf{S} = \mathbf{V} \mathbf{\Sigma} \mathbf{W}^T$ [D].
  3. Optimal rotation matrix $\mathbf{U} = \mathbf{W} \mathbf{D} \mathbf{V}^T$ enforcing reflection parity correction:
     $$\mathbf{D} = \operatorname{diag}\left(1, 1, \det(\mathbf{W}\mathbf{V}^T)\right) \quad [\text{D}]$$
  4. Special Orthogonal Group $\mathrm{SO}(3)$ proper rotation lock:
     $$\det(\mathbf{U}) = +1.000000000000 \pm 1.0 \times 10^{-12} \quad [\text{M}]$$
  5. Rotational Eckart condition Coriolis decoupling residual torque assertion:
     $$\|\mathbf{L}_{\text{Eckart}}\|_2 = \left\| \sum_{i=1}^N m_i \left( (\mathbf{U}\mathbf{r}_i^0) \times \mathbf{r}_i \right) \right\|_2 < 1.0 \times 10^{-10}\text{ a.u.} \quad [\text{M}]$$

### 2.4 Package L2-T1.4: Two-Stage Conformer Deduplication Pipeline (Topological Automorphism + Metric Filter)
- **Target File:** `src/cochem_base/intake/conformer_deduplication.py` [M]
- **Governing Directives:** Method Matrix v4.1 §2.3.2, §3.3, Anti-Spoofing Protocol v4 Directives 3 & 8 [M].
- **Core Engineering Requirements:**
  1. **Stage 1 (Topological Invariance):** Covalent molecular graph construction $G=(V, E)$ using dynamic Pyykkö covalent single-bond radii queried from `mendeleev`:
     $$(i, j) \in E \iff 0.40\text{ \AA} < \|\mathbf{r}_i - \mathbf{r}_j\|_2 \le 1.28 \cdot \left( r_{\text{cov}}(Z_i) + r_{\text{cov}}(Z_j) \right) \quad [\text{D}]$$
     Weisfeiler-Lehman (1-WL, $k=3$) graph automorphism coloring iterations producing an immutable 128-bit hex digest $H_{\text{WL}}(G)$ [D].
  2. **Stage 2 (Geometric RMSD & Spectroscopic Rotational Filter):**
     - Horn quaternion Kabsch minimum coordinate RMSD: $\text{RMSD}(A, B) < 0.0800\text{ \AA}$ [M].
     - Principal moment of inertia tensor diagonalization ($\mathbf{I} \to I_A \le I_B \le I_C$) and spectroscopic rotational constant calculation in MHz ($A, B, C = h / (8\pi^2 I)$) [D].
     - Dual-condition duplicate collapse criteria:
       $$\text{Collapse as duplicate} \iff \mathrm{RMSD}(A, B) < 0.0800\text{ \AA} \quad \text{AND} \quad \left| \frac{B_A - B_B}{B_A} \right| \le 0.0005 \quad (0.05\%) \quad [\text{M}]$$
     - Shallow potential well preservation: candidates with $\mathrm{RMSD} < 0.0800\text{ \AA}$ but $|\Delta B/B| > 0.05\%$ are strictly preserved as spectroscopically distinct rotational states [M].
  3. **Combinatorial Protection: Hungarian Permutation Fallback:**
     - Automorphism orbit traversal evaluates exact permutations when $|\operatorname{Aut}(G)| \le 720$ ($6!$) [D].
     - When $|\operatorname{Aut}(G)| > 720$, the engine activates the **Hungarian Algorithm Fallback** (`scipy.optimize.linear_sum_assignment`) [M][D]. Pairwise Euclidean cost matrices $C_{uv} = \|\mathbf{r}_{u, A} - \mathbf{r}_{v, B}\|^2$ are constructed independently over symmetrically equivalent atom subsets, guaranteeing polynomial time complexity $O(N^3)$ and completely preventing combinatorial explosion [D].
  4. **Anti-Spoofing Synthetics Ban:** Zero calls to `np.zeros`, `np.ones`, or `np.eye`. All numerical arrays are physically allocated via `np.array([...])` or `np.asarray(...)` [M].

---

## 3. Physical Invariant Acceptance Gate Matrix

```
+==================================================================================================================================+
|                                    VR-01 CORE INTAKE ALGORITHMS PHYSICAL INVARIANT GATES                                         |
+---------+-----------------------------------+-----------------------------------+-----------------------+------------------------+
| WBS     | Physical Invariant Description    | Target Equation / Metric          | Strict Threshold      | Action on Failure      |
+---------+-----------------------------------+-----------------------------------+-----------------------+------------------------+
| L2-T1.1 | Dynamic Mendeleev Mass Retrieval  | m = element(sym).atomic_weight    | 0 static dictionaries | [HARD_ABORT: SPOOFING] |
| L2-T1.1 | Isotopic Alias Normalization      | D -> 2.0141018 u, 13C -> 13.00335 | Exact CIAAW/IUPAC mass| ValueError             |
| L2-T1.1 | Ghost Atom Zero-Mass Guard        | Gh, Bq, X -> mass = 0.00000000000 | Exactly 0.0 u (Z=0)   | ValueError             |
| L2-T1.2 | COM Translation Drift Zeroing     | ||sum m_i r'_i||_2 (Kahan accum.) | < 1.0e-12 a.u.        | COMDriftError          |
| L2-T1.3 | SO(3) Proper Rotation Closure     | det(U) = det(W D V^T)             | +1.000000 +- 1e-12    | ImproperRotationError  |
| L2-T1.3 | Rotational Eckart Vector Torque   | ||sum m_i (U r0 x r)||_2          | < 1.0e-10 a.u.        | EckartTorqueError      |
| L2-T1.4 | WL Graph Isomorphism Digest       | 1-WL (k=3, node_attr='element')   | 128-bit SHA-256 hex   | Stage 1 Partition      |
| L2-T1.4 | Horn Quaternion Kabsch RMSD       | min ||P - U Q|| / sqrt(N)         | < 0.0800 Angstrom     | Preserved if >= 0.08 A |
| L2-T1.4 | Spectroscopic Rotational Sieve    | |Delta B / B| = |B_A - B_B| / B_A | <= 0.0005 (0.05%)     | Preserved if > 0.05%   |
| L2-T1.4 | Hungarian Permutation Fallback    | linear_sum_assignment(cost)       | Active for |Aut|>720  | O(N^3) bounded runtime |
+==================================================================================================================================+
```

---

## 4. Authoritative Dispatch Order for `cochem-coder`

```markdown
[COCHEM-CODER EXECUTION ORDER: TASK 1.3.3 - CORE INTAKE ALGORITHMS (L2-T1.1 TO L2-T1.4)]

You are cochem-coder, the sole implementation authority for the CoChem Agent Council.
You are tasked with executing, verifying, and certifying the complete core intake algorithms for Task 1 (VR-01) across packages L2-T1.1 through L2-T1.4.

EXECUTION INSTRUCTIONS:
1. INGEST CONTEXT: Read Method Matrix v4.1 (§2.3, §3.3, §6.10, §10.1-10.8), task1_subsystems_architectural_specification.md, and existing target files.
2. VERIFY L2-T1.1 (Dynamic Masses): In `src/cochem_base/physics/isotopes.py`, assert 0 static dictionaries, dynamic Mendeleev queries, regex nuclide normalization, and ghost atom zeroing.
3. VERIFY L2-T1.2 & L2-T1.3 (COM & Eckart Alignment): In `src/cochem_base/intake/cochem_molsym_eckart_aligner.py`, assert Kahan COM drift < 1e-12 a.u., SO(3) det(U) = +1.000000, and Eckart torque < 1e-10 a.u.
4. IMPLEMENT & VERIFY L2-T1.4 (Conformer Deduplication): In `src/cochem_base/intake/conformer_deduplication.py`, implement `hungarian_assignment_rmsd` and `compute_automorphism_orbit_rmsd` with Hungarian fallback for permutations > 720. Wire into `ConformerDeduplicator.deduplicate`.
5. ZERO-MOCK MANDATE: Zero calls to `np.zeros`, `np.ones`, or `np.eye`. Zero `NotImplementedError`. Zero empty `pass`.
6. RUN TESTS: Execute `pytest -v tests/test_chunk17_verification_suite.py` and verify all tests pass physically.
7. LINT CODE: Execute `python ci_tools/anti_spoof_linter.py --strict` across all modified files and assert returncode 0.
8. HANDOFF: Hand off completed implementation to `cochem-audit` and `adversary` for asymmetric statutory auditing.
```

---

## 5. Verification, Audit & Quad-Mirror Persistence Handoff

Upon completing the algorithmic implementation and self-verification:
1. **Asymmetric Audit:** Deliverables are routed to `cochem-audit` for AST static verification and `adversary` for hostile red-team penetration testing.
2. **Quad-Mirror Parity:** The specification and audit receipts must be persisted across all 4 workspace tiers with 100.000% bitwise parity:
   - `C:/Users/ansac/.gemini/antigravity-cli/scratch/`
   - `D:/__CoChem/.docs/`
   - `D:/__CoChem/__agentic/dropzones/inbox_srs/`
   - `D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/`
3. **State Ledger Update:** Atomically update `swarm_state.json` via OS-locked file operations recording exact cryptographic digests and Council Session 074 resolution decrees.
4. **Git Index Staging:** Stage verified files into the `CoChem-BASE` git index with porcelain clean status.

**Authorizing Presidium Leader:**  
`0rchestrator` — CoChem Agent Council Presidium Router [M]  
**Designated Execution Agent:**  
`cochem-coder` — Autonomous Code Implementation Agent [M]  
**Ratification Status:** `DISPATCH_RATIFIED_FOR_IMPLEMENTATION` [GOV] [M]  
**Timestamp:** `2026-09-11T09:18:00-05:00` [M]
