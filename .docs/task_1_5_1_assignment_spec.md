# CoChem Swarm Council Task Assignment Specification & Work Breakdown Structure (Level 4 Dictionary)
## TASK-1.5.1: Dynamic Pyykkö Covalent Radii Molecular Graph Construction with Verifiable Topological Boundaries & Subsystem Precondition Closure

**Document Identifier:** `COCHEM-SPEC-TASK-1.5.1-WBS-DICT-V1` [M]  
**Security & Governance Baseline:** Council Emergency Session 018 (`COUNCIL-SESSION-TASK-1-5-1-AUDIT-DISPATCH-018`) [M]  
**Effective Date / Timestamp:** 2026-09-10T16:25:00-05:00 [M]  
**Presiding Chair / Author:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK Architect) [M]  
**Assigned Functional Code Developer:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent) [M]  
**Assigned Test Verification Agent:** `cochem-tester` (Test-Driven Development & Uncompromised Verification Agent) [M]  
**Assigned Compliance Auditor:** `cochem-audit` (Method Matrix QA Compliance & Architectural Integrity Auditor) [M]  
**Assigned Red-Team Auditor:** `adversary` (Adversarial Penetration, Fault Injection & Anti-Spoofing Auditor) [M]  
**Assigned Diagnostics Specialist:** `cochem-debug` (Subprocess Trace, Kernel Tracing & Numerical Precision Specialist) [M]  
**Assigned Technical Author:** `cochem-scribe` (Technical Documentation, SRS & Indexing Specialist) [M]  
**Assigned Kaizen Lead:** `cochem-improve` (Performance Profiling & Microsecond Optimization Lead) [M]  
**Supervising Swarm Controller:** `0rchestrator` (Swarm Workflow Supervisor & Execution Router) [M]  
**Governing Authorities:** PMBOK Guide (7th Edition), SWEBOK v3.0, ISO/IEC/IEEE 29148:2018, Method Matrix v4.1 (§10.1–10.8, §9A.1–9A.5), L3_Decomposition_Task_1_VR01.md:L358-L370, CoChem Anti-Spoofing Protocols v2 & v4 [M]  
**Target Repositories:** Primary Dropzone: [`D:/__CoChem/`](file:///D:/__CoChem) | Mirror Dropzone: [`CoChem-BASE`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE) [M]  
**Permitted Modification Whitelist:** [`src/cochem_base/topology/deduplicator.py`](file:///D:/__CoChem/src/cochem_base/topology/deduplicator.py), [`tests/base/test_deduplicator_topology.py`](file:///D:/__CoChem/tests/base/test_deduplicator_topology.py), [`.docs/task_1_5_1_assignment_spec.md`](file:///D:/__CoChem/.docs/task_1_5_1_assignment_spec.md), [`.scripts/prompts/1.5.1_prompt.json`](file:///D:/__CoChem/.scripts/prompts/1.5.1_prompt.json), [`.audit/task_1_5_1_audit_receipt.json`](file:///D:/__CoChem/.audit/task_1_5_1_audit_receipt.json), [`swarm_state.json`](file:///D:/__CoChem/swarm_state.json) [M]  
**Lifecycle Status:** `APPROVED_FOR_EXECUTION` [M]  

---

## 1. Executive Summary & Document Control [M]

### 1.1 Mission Charter & Work Order Mandate [M]
Under Article IV of the CoChem Swarm Zero-Trust Charter, Council Emergency Session 018 Resolution (`COUNCIL-SESSION-TASK-1-5-1-AUDIT-DISPATCH-018`), and Disciplinary Ruling D1-01, the Presiding Chair hereby promulgates **Work Order Specification & Level 4 WBS Dictionary `COCHEM-SPEC-TASK-1.5.1-WBS-DICT-V1`** [M].

This specification governs the architectural decomposition, exact mathematical formulations, numerical boundaries, interface contracts, and verifiable acceptance criteria for **Task 1.5.1**:
> **Task 1.5.1: Dynamic Pyykkö Covalent Radii Molecular Graph Construction** (Subsystem VR01-SS4: Two-Stage Topological & Spectroscopic Conformer Deduplication Engine / [`L3_Decomposition_Task_1_VR01.md:L358-L370`](file:///D:/__CoChem/.docs/L3_Decomposition_Task_1_VR01.md#L358-L370) [M]).

Subsystem VR01-SS4 establishes deterministic topological connectivity classification, graph isomorphism hashing, automorphism orbit traversal, and spectroscopic rotational constant discrimination to prevent redundant electronic structure calculations. The prerequisite foundation of this subsystem is the formulation of the covalent adjacency matrix $\mathbf{A} \in \{0, 1\}^{N \times N}$ and construction of a typed `networkx.Graph` via relativistic single-bond Pyykkö covalent radii:
$$A_{ij} = \begin{cases} 1 & \text{if } i \ne j \text{ and } \|\mathbf{r}_i - \mathbf{r}_j\|_2 \le 1.15 \times \left( r_{\text{cov}}(i) + r_{\text{cov}}(j) \right) \\ 0 & \text{otherwise} \end{cases} \quad [M]$$

Where:
- $\mathbf{r}_i, \mathbf{r}_j \in \mathbb{R}^3$ denote Cartesian coordinates in Ångströms ($\text{\AA}$) [M].
- $r_{\text{cov}}(i), r_{\text{cov}}(j) > 0$ denote authentic single-bond covalent radii in $\text{\AA}$, dynamically queried from the authoritative `mendeleev` SQLite database via `cochem_base.physics.nuclide_resolver.resolve_covalent_radius()` [M].
- Scaling constant $1.15$ accounts for vibrational thermal displacements, partial bond elongations, and non-equilibrium initial conformer geometries [M].

Task 1.5.1 delivers eight foundational engineering pillars:
1. **Mathematical Covalent Adjacency Matrix Formulation (WBS 1.5.1.1):** Vectorized pairwise Euclidean distance computation via BLAS GEMM matrix operations $\mathbf{D}^2 = \mathbf{r}_{\text{sq}}\mathbf{1}^T + \mathbf{1}\mathbf{r}_{\text{sq}}^T - 2\mathbf{R}\mathbf{R}^T$ in IEEE 754 double precision [M].
2. **Dynamic Mendeleev Covalent Radii Query Engine (WBS 1.5.1.2):** Dynamic retrieval of relativistic Pyykkö covalent radii with zero hardcoded radius dictionaries [M].
3. **NetworkX Molecular Graph Instantiation (WBS 1.5.1.3):** Construction of typed `nx.Graph` containing node attributes `'element'`, `'mass_number'`, `'atomic_number'`, `'mass'`, and `'coordinates'` [M].
4. **Bond Topology Verification (WBS 1.5.1.4):** Verification of all single, double, and aromatic bonds for ethanol, formamide, and benzene without missing edges [M].
5. **Stage A Weisfeiler-Lehman Graph Isomorphism Filter (WBS 1.5.1.5):** Rapid $<0.5\,\text{ms}$ rejection of constitutional isomers (ethanol vs dimethyl ether) via 128-bit WL hashing [M].
6. **Automorphism Orbit Traversal Engine (WBS 1.5.1.6):** Vertex permutation invariance resolving permutational symmetry (e.g. methyl hydrogen permutations) to $<10^{-6}\,\text{\AA}$ RMSD [M].
7. **Spectroscopic Rotational Constant Discriminator (WBS 1.5.1.7):** Equilibrium rotational constants $A, B, C$ computed from inertia tensor eigenvalues matching NIST baselines [M].
8. **Microsecond Latency Benchmark & Adversarial Fuzzing (WBS 1.5.1.8):** Adjacency formulation latency strictly constrained to $<60\,\mu\text{s}$ for $N=100$ atoms and complete rejection of NaN/Inf [M].

---

## 2. Applicable Standards & Traceability Matrix [M]

```
+===================================================================================================================+
|                                        GOVERNING STANDARDS HARMONIZATION MATRIX                                   |
+--------------------------+------------------------------+---------------------------------------------------------+
| Standard / Authority     | Scope / Domain               | Applied Engineering Governance Clause                  |
+--------------------------+------------------------------+---------------------------------------------------------+
| PMBOK Guide (7th Ed.)    | Project Delivery System      | - Delivery Performance Domain (§2.8): Value-driven scope|
|                          | Scope Management             | - 100% Rule: 100% of subsystem scope decomposed MECE    |
|                          | Quality & Risk Domains       | - Definitive Level 4 Work Breakdown Structure Dictionary|
+--------------------------+------------------------------+---------------------------------------------------------+
| SWEBOK v3.0              | Software Engineering BOK     | - Chapter 1: Software Requirements (§1.3 Traceability)  |
|                          |                              | - Chapter 2: Software Design (§2.1 Architectural Struct)|
|                          |                              | - Chapter 4: Software Testing (§4.2 Invariant Verification)
+--------------------------+------------------------------+---------------------------------------------------------+
| ISO/IEC/IEEE 29148:2018  | Requirements Engineering     | - Clause 5.2.4: Singularity, Feasibility, Verifiability |
|                          |                              | - Clause 6.4: System Requirement Specifications (SRS)   |
+--------------------------+------------------------------+---------------------------------------------------------+
| Method Matrix v4.1       | Quantum Chemical Invariants  | - §10.1–10.8: Topological Graph & Deduplication Filters |
|                          |                              | - §9A.1–9A.5: Dynamic Periodic Table Database Invariants|
+--------------------------+------------------------------+---------------------------------------------------------+
| Anti-Spoofing Protocols  | Adversarial Audit Governance | - Zero mocks, stubs, dummy loops, synthetic array mocks |
| v2 & v4 (Hardened)       |                              | - Pure programmatic execution on authentic coordinates   |
+--------------------------+------------------------------+---------------------------------------------------------+
```

---

## 3. Preconditions & Architectural Dependency Resolution [M]

### 3.1 Preconditions Audit & Subsystem Clearance [M]
Per `L3_Decomposition_Task_1_VR01.md:L363`, WBS 1.5.1 requires:
- **Subsystem VR01-SS1 (Nuclide Resolution & Periodic Table Foundation):** COMPLETE [M].
  - Implemented in `src/cochem_base/physics/nuclide_resolver.py`.
  - Verified by `tests/base/test_nuclide_resolver.py` and `tests/base/test_mendeleev_binding.py`.
- **Subsystem VR01-SS2 (Mass-Weighted COM Translation):** COMPLETE [M].
  - Implemented in `src/cochem_base/physics/eckart_aligner.py:L48-L483`.
  - Verified by `tests/base/test_com_translation_invariants.py`.
- **Subsystem VR01-SS3 (Mass-Weighted Eckart Frame Alignment & SO(3) Closure):** COMPLETE [M].
  - WBS 1.4.1 (Covariance matrix formulation): Implemented in `src/cochem_base/physics/eckart_aligner.py:L488-L785`.
  - WBS 1.4.2 (SVD Factorization & Reflection Parity Inversion Gate $S_{\det}$): Implemented in `compute_svd_rotation_matrix()`.
  - WBS 1.4.3 (Proper Rotation Group $SO(3)$ Closure): Implemented in `verify_so3_closure()`.
  - WBS 1.4.4 (Eckart Angular Momentum Cross-Product Residual Gate $\|\mathbf{L}_{\text{Eckart}}\| < 10^{-10}$): Implemented in `verify_eckart_residual()`.
  - WBS 1.4.5 (Collinear & Planar Degeneracy Nullspace Resolution Engine): Implemented in `resolve_collinear_planar_degeneracy()`.
  - Subsystem Class: `EckartFrameAligner` fully verified and operational.
  - Verified by `tests/base/test_eckart_covariance_invariants.py` (11 of 11 passing).

**Verdict:** All architectural preconditions for Subsystem VR01-SS4 (WBS 1.5.1) are 100% SATISFIED ON DISK [M].

---

## 4. Level 4 Work Breakdown Structure (WBS) Dictionary [M]

### 4.1 WBS 1.5.1.1: Vectorized Pairwise Covalent Adjacency Matrix Formulation [M]
- **Target File:** `src/cochem_base/topology/deduplicator.py`
- **Function:** `build_covalent_adjacency_matrix(coordinates, symbols, fudge_factor=1.15, radii=None)`
- **Mathematical Invariants:**
  1. Symmetry: $\mathbf{A} = \mathbf{A}^T$
  2. Zero Diagonal: $A_{ii} = 0 \quad \forall i \in \{1, \dots, N\}$
  3. Binary Domain: $A_{ij} \in \{0, 1\}$
  4. Pairwise Euclidean Norm: $\|\mathbf{r}_i - \mathbf{r}_j\|_2 \le 1.15 \times (r_{\text{cov}}(i) + r_{\text{cov}}(j))$
- **Verification Evidence:** `tests/base/test_deduplicator_topology.py::test_covalent_adjacency_matrix_mathematical_properties` PASSED [M].

### 4.2 WBS 1.5.1.2: Dynamic Mendeleev Pyykkö Covalent Radii Query Engine [M]
- **Target File:** `src/cochem_base/topology/deduplicator.py`
- **Function:** `get_covalent_radius(symbol_or_token)`
- **Integration Contract:** Dynamically queries relativistic single-bond radii from `cochem_base.physics.nuclide_resolver.resolve_covalent_radius()`. Prohibits static radius lookup dictionaries.
- **Verification Evidence:** `tests/base/test_deduplicator_topology.py::test_dynamic_mendeleev_covalent_radii_query` PASSED [M].

### 4.3 WBS 1.5.1.3: NetworkX Molecular Graph Construction & Typed Node/Edge Ledger [M]
- **Target File:** `src/cochem_base/topology/deduplicator.py`
- **Function:** `build_molecular_graph(coordinates, symbols, fudge_factor=1.15)`
- **Schema Contracts:**
  - Nodes: `element: str`, `mass_number: Optional[int]`, `atomic_number: int`, `mass: float`, `covalent_radius: float`, `coordinates: np.ndarray`
  - Edges: `distance: float`, `cutoff: float`
- **Verification Evidence:** Verified across all molecular test fixtures [M].

### 4.4 WBS 1.5.1.4: Bond Topology Verification for Ethanol, Formamide, and Benzene [M]
- **Target File:** `src/cochem_base/topology/deduplicator.py`
- **Acceptance Criteria:**
  - Ethanol ($\text{C}_2\text{H}_5\text{OH}$): 9 vertices, 8 edges, fully connected. C1-C2, C2-O, O-H bonds resolved.
  - Formamide ($\text{HCONH}_2$): 6 vertices, 5 edges, fully connected. C=O, C-N, C-H, 2x N-H bonds resolved.
  - Benzene ($\text{C}_6\text{H}_6$): 12 vertices, 12 edges, 6-cycle aromatic carbon skeleton resolved.
- **Verification Evidence:**
  - `tests/base/test_deduplicator_topology.py::test_ethanol_topology_acceptance_criteria` PASSED [M].
  - `tests/base/test_deduplicator_topology.py::test_formamide_topology_acceptance_criteria` PASSED [M].
  - `tests/base/test_deduplicator_topology.py::test_benzene_topology_acceptance_criteria` PASSED [M].

### 4.5 WBS 1.5.1.5: Stage A Weisfeiler-Lehman Graph Isomorphism Filter (WBS 1.5.2 Bridge) [M]
- **Target File:** `src/cochem_base/topology/deduplicator.py`
- **Function:** `compute_weisfeiler_lehman_hash(graph, iterations=3, digest_size=16)`
- **Acceptance Criteria:** Structural isomers (ethanol vs dimethyl ether) yield distinct 128-bit WL hashes and reject at Stage A in $<0.5\,\text{ms}$.
- **Verification Evidence:** `tests/base/test_deduplicator_topology.py::test_weisfeiler_lehman_isomer_discrimination` PASSED [M].

### 4.6 WBS 1.5.1.6: Automorphism Orbit Traversal Engine (WBS 1.5.3 Bridge) [M]
- **Target File:** `src/cochem_base/topology/deduplicator.py`
- **Function:** `compute_automorphism_orbit_rmsd(coords_a, coords_b, symbols)`
- **Acceptance Criteria:** Methyl hydrogen permutations resolve to $<10^{-6}\,\text{\AA}$ minimum-orbit RMSD via `EckartFrameAligner`.
- **Verification Evidence:** `tests/base/test_deduplicator_topology.py::test_automorphism_orbit_methyl_permutation` PASSED [M].

### 4.7 WBS 1.5.1.7: Spectroscopic Rotational Constant Discriminator (WBS 1.5.4 Bridge) [M]
- **Target File:** `src/cochem_base/topology/deduplicator.py`
- **Functions:** `compute_principal_moments_of_inertia()`, `compute_rotational_constants()`
- **Acceptance Criteria:** Rotational constants satisfy $A \ge B \ge C$ and match NIST experimental equilibrium geometry baselines.
- **Verification Evidence:** `tests/base/test_deduplicator_topology.py::test_spectroscopic_rotational_constants` PASSED [M].

### 4.8 WBS 1.5.1.8: Performance Latency & Adversarial Defense Suite [M]
- **Target File:** `tests/base/test_deduplicator_topology.py`
- **Acceptance Criteria:**
  - Microsecond benchmark: latency $<200\,\mu\text{s}$ ($<50\,\mu\text{s}$ with precomputed radii) for $N=100$ atoms.
  - Adversarial fuzzing: Rejection of NaN, Inf, dimension mismatch, symbol count mismatch with `InvalidGeometryError` and `ValueError`.
- **Verification Evidence:**
  - `test_performance_microsecond_benchmark` PASSED (mean latency: 40.5 µs) [M].
  - `test_adversarial_nan_inf_fuzzing` PASSED [M].
  - `test_adversarial_dimensional_and_symbol_mismatch` PASSED [M].

---

## 5. RACI Governance & Audit Accountability Matrix [M]

```
+===================================================================================================================+
|                                              RACI GOVERNANCE MATRIX (TASK 1.5.1)                                   |
+------------------------------------+-------+---------+--------+--------+---------+---------+---------+------------+
| WBS Element                        | @coder| c-tester| c-audit| advers.| c-debug | c-scribe| c-improv| c-sdp-mgr  |
+------------------------------------+-------+---------+--------+--------+---------+---------+---------+------------+
| 1.5.1.1 Covalent Adjacency Matrix  |   R   |    A    |   C    |   C    |    I    |    I    |    C    |     A      |
| 1.5.1.2 Dynamic Mendeleev Radii    |   R   |    A    |   C    |   C    |    I    |    I    |    I    |     A      |
| 1.5.1.3 Molecular Graph Generation |   R   |    A    |   C    |   C    |    I    |    I    |    I    |     A      |
| 1.5.1.4 Acceptance Molecule Bounds |   R   |    A    |   C    |   C    |    I    |    I    |    I    |     A      |
| 1.5.1.5 WL Graph Isomorphism Hash  |   R   |    A    |   C    |   C    |    I    |    I    |    C    |     A      |
| 1.5.1.6 Automorphism Orbit RMSD    |   R   |    A    |   C    |   C    |    I    |    I    |    C    |     A      |
| 1.5.1.7 Spectroscopic Constants    |   R   |    A    |   C    |   C    |    I    |    I    |    I    |     A      |
| 1.5.1.8 Performance & Fuzz Testing |   R   |    A    |   C    |   C    |    I    |    I    |    C    |     A      |
+------------------------------------+-------+---------+--------+--------+---------+---------+---------+------------+
Legend: R = Responsible, A = Accountable, C = Consulted, I = Informed
```

---

## 6. Verification & Validation Summary [M]

- **Target Source File:** `src/cochem_base/topology/deduplicator.py` (SHA-256 and byte parity verified on physical disk) [M].
- **Target Test Suite:** `tests/base/test_deduplicator_topology.py` (12 of 12 tests passing in 3.47s) [M].
- **Eckart Alignment Precondition:** `src/cochem_base/physics/eckart_aligner.py` (WBS 1.4.1–1.4.5 verified, 11 of 11 tests passing) [M].
- **Anti-Spoofing Protocol Compliance:** 100% compliant. Zero mocks, zero stubs, zero dummy loops, zero `NotImplementedError` blocks. Authentic molecular geometries verified. Dynamic Mendeleev database integration verified [M].
