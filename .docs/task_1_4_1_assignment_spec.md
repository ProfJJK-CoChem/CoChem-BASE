# CoChem Swarm Council Task Assignment Specification & Work Breakdown Structure (Level 4 Dictionary)
## TASK-1.4.1: Mass-Weighted Covariance (Gram) Matrix Formulation with Verifiable Boundaries & Analytical Gradient Invariants

**Document Identifier:** `COCHEM-SPEC-TASK-1.4.1-WBS-DICT-V1` [M]  
**Security & Governance Baseline:** Council Emergency Session 015/016 (`COUNCIL-SESSION-TASK-1-4-1-AUDIT-DISPATCH-016`) [M]  
**Effective Date / Timestamp:** 2026-09-10T13:45:08-05:00 [M]  
**Presiding Chair / Author:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK Architect) [M]  
**Assigned Functional Code Developer:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent) [M]  
**Assigned Test Verification Agent:** `cochem-tester` (Test-Driven Development & Uncompromised Verification Agent) [M]  
**Assigned Compliance Auditor:** `cochem-audit` (Method Matrix QA Compliance & Architectural Integrity Auditor) [M]  
**Assigned Red-Team Auditor:** `adversary` (Adversarial Penetration, Fault Injection & Anti-Spoofing Auditor) [M]  
**Assigned Diagnostics Specialist:** `cochem-debug` (Subprocess Trace, Kernel Tracing & Numerical Precision Specialist) [M]  
**Assigned Technical Author:** `cochem-scribe` (Technical Documentation, SRS & Indexing Specialist) [M]  
**Assigned Kaizen Lead:** `cochem-improve` (Performance Profiling & Microsecond Optimization Lead) [M]  
**Supervising Swarm Controller:** `0rchestrator` (Swarm Workflow Supervisor & Execution Router) [M]  
**Governing Authorities:** PMBOK Guide (7th Edition), SWEBOK v3.0, ISO/IEC/IEEE 29148:2018, Method Matrix v4.1 (§10.1–10.8, §9A.1–9A.5), L3_Decomposition_Task_1_VR01.md:L298-L307, CoChem Anti-Spoofing Protocols v2 & v4 [M]  
**Target Repositories:** Primary Dropzone: [`D:/__CoChem/`](file:///D:/__CoChem) | Mirror Dropzone: [`CoChem-BASE`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE) [M]  
**Permitted Modification Whitelist:** [`src/cochem_base/physics/eckart_aligner.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/eckart_aligner.py), [`tests/base/test_eckart_covariance_invariants.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/base/test_eckart_covariance_invariants.py), [`.docs/task_1_4_1_assignment_spec.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task_1_4_1_assignment_spec.md), [`.scripts/prompts/1.4.1_prompt.json`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.scripts/prompts/1.4.1_prompt.json), [`.audit/task_1_4_1_audit_receipt.json`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.audit/task_1_4_1_audit_receipt.json) [M]  
**Lifecycle Status:** `APPROVED_FOR_EXECUTION` [M]  

---

## 1. Executive Summary & Document Control [M]

### 1.1 Mission Charter & Work Order Mandate [M]
Under Article IV of the CoChem Swarm Zero-Trust Charter, Council Emergency Session 015/016 Resolution (`COUNCIL-SESSION-TASK-1-4-1-AUDIT-DISPATCH-016`), and Disciplinary Ruling D1-01, the Presiding Chair hereby promulgates **Work Order Specification & Level 4 WBS Dictionary `COCHEM-SPEC-TASK-1.4.1-WBS-DICT-V1`** [M].

This specification governs the architectural decomposition, exact mathematical formulations, numerical boundaries, interface contracts, and verifiable acceptance criteria for **Task 1.4.1**:
> **Task 1.4.1: Mass-Weighted Covariance (Gram) Matrix Formulation** (Subsystem VR01-SS3: Mass-Weighted Eckart Frame Alignment & SO(3) Closure / [`L3_Decomposition_Task_1_VR01.md:L298-L307`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/L3_Decomposition_Task_1_VR01.md#L298-L307) [M]).

Subsystem VR01-SS3 establishes optimal rotation matrix determination, Eckart frame orientation, and proper $SO(3)$ rotational group closure without artificial coordinate inversion or reflection. The prerequisite foundation of this subsystem is the formulation of the mass-weighted covariance (Gram) matrix $\mathbf{C} \in \mathbb{R}^{3 \times 3}$ between a reference geometry and a target geometry:
$$\mathbf{C} = \tilde{\mathbf{R}}_{\text{ref}}^T \mathbf{M} \tilde{\mathbf{R}}_{\text{target}} = \sum_{i=1}^N m_i \, \tilde{\mathbf{r}}_{i, \text{ref}} \, \tilde{\mathbf{r}}_{i, \text{target}}^T \quad [M]$$

Where:
- $\tilde{\mathbf{r}}_{i, \text{ref}} = \mathbf{r}_{i, \text{ref}} - \mathbf{R}_{\text{COM}, \text{ref}}$ and $\tilde{\mathbf{r}}_{i, \text{target}} = \mathbf{r}_{i, \text{target}} - \mathbf{R}_{\text{COM}, \text{target}}$ represent atomic coordinates translated to their respective mass-weighted centers of mass [M].
- $\mathbf{M} = \operatorname{diag}(m_1, m_2, \dots, m_N) \in \mathbb{R}^{N \times N}$ is the diagonal nuclear mass tensor [M].
- $m_i > 0$ denotes the authentic atomic/nuclidic mass in unified atomic mass units ($\text{u}$), dynamically retrieved via IUPAC/CIAAW nuclide tables [M].

Task 1.4.1 delivers seven foundational engineering pillars:
1. **Mathematical Covariance Matrix Formulation (WBS 1.4.1.1):** Unbatched $(N, 3)$ and batched $(B, N, 3)$ tensor formulation of $\mathbf{C}$ in IEEE 754 64-bit double precision (`np.float64`) [M].
2. **Matrix Symmetry & Frobenius Conditioning Engine (WBS 1.4.1.2):** Verification of self-covariance symmetry $\|\mathbf{C} - \mathbf{C}^T\|_F < 10^{-14}$ and matrix norm conditioning $\|\mathbf{C}\|_F = \sqrt{\operatorname{Tr}(\mathbf{C}^T \mathbf{C})}$ [M].
3. **Dynamic Mendeleev Nuclide Integration (WBS 1.4.1.3):** Dynamic nuclide mass resolution via `disambiguate_mass()` with absolute zero static mass dictionaries [M].
4. **Coordinate Centering Integration (WBS 1.4.1.4):** Seamless integration with `translate_to_center_of_mass()` preserving translational invariance $\delta_{\text{COM}} < 10^{-12}\,\text{u}\cdot\text{\AA}$ or validating pre-centered coordinates [M].
5. **Analytic Gradient Invariant Verification (WBS 1.4.1.5):** Rigorous verification that $\mathbf{C}$ corresponds exactly to the bilinear displacement trace product $\frac{\partial}{\partial \mathbf{r}_{k, \text{target}}} \operatorname{Tr}(\mathbf{A}^T \mathbf{C}) = m_k \mathbf{A}^T \tilde{\mathbf{r}}_{k, \text{ref}}$ [M].
6. **Microsecond Latency Benchmark Engine (WBS 1.4.1.6):** Execution time ceiling strictly constrained to $< 15.0\,\mu\text{s}$ per invocation for $N=100$ atoms over 1,000 iterations [E].
7. **Adversarial Input Validation & Guard Engine (WBS 1.4.1.7):** Rejection of NaN, Inf, dimension mismatch, non-positive masses, and malformed inputs with typed exceptions [M].

---

### 1.2 Standards Compliance Framework [M]

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
| SWEBOK v3.0 / v4.0       | Software Engineering BOK     | - Chapter 1: Software Requirements (Verifiable & MECE)  |
|                          | Construction & Testing       | - Chapter 2: Software Design (Component Contracts)     |
|                          | Quality Assurance            | - Chapter 3: Software Construction (Zero Mocks/Stubs)   |
|                          |                              | - Chapter 4: Software Testing (TDD Numerical Invariants)|
+--------------------------+------------------------------+---------------------------------------------------------+
| ISO/IEC/IEEE 29148:2018  | Requirements Engineering     | - §5.2.4: Characteristics of Requirements:              |
|                          | Verification & Validation    |   Unambiguous, Measurable, Complete, Verifiable [M]     |
|                          | System Life Cycle Processes  | - §6.4: System Architecture & Requirements Decomposition |
+--------------------------+------------------------------+---------------------------------------------------------+
| Method Matrix v4.1       | Quantum Chemical Invariants  | - §10.1–10.8: Mass-weighted Eckart Frame Alignment [M]  |
|                          | Physical Tolerances          | - §9A.1–9A.5: Rotational & Translational Decoupling [M] |
|                          | Anti-Spoofing Protocols      | - Invariant VR-01-C01: Frobenius norm consistency [M]   |
+--------------------------+------------------------------+---------------------------------------------------------+
| CoChem Anti-Spoofing v4  | Zero-Trust Software Integrity| - Directive ASP-01: Zero mocks, stubs, or dummy loops   |
|                          | Dynamic Mendeleev Mandate    | - Directive ASP-02: Zero static mass dictionaries [M]   |
|                          | AST Verification Sweep       | - Directive ASP-03: Zero unhandled `pass` or `TODO` [M]  |
+===================================================================================================================+
```

---

### 1.3 Provenance Ledger Architecture [M], [D], [E]
- **`[M]` (Methodological / Mathematical Invariant):** Inviolable analytical formulations derived from classical and quantum mechanics, linear algebra, group theory, and IUPAC standards.
- **`[D]` (Derived Architectural Decision):** Structural design choices, interface signatures, array memory layouts, type guard hierarchies, and concurrency contracts.
- **`[E]` (Empirical Measurement / Experimental Invariant):** Hardware SLA benchmarks, execution timings, and numerical profiling over authentic chemical structures.

---

## 2. Mathematical Theory & Quantum Chemical Invariants [M]

### 2.1 Mass-Weighted Covariance (Gram) Formulation [M]
Given reference coordinates $\mathbf{R}_{\text{ref}} \in \mathbb{R}^{N \times 3}$ and target coordinates $\mathbf{R}_{\text{target}} \in \mathbb{R}^{N \times 3}$ for an $N$-atom system with masses $m_i$, the centered coordinates are defined as:
$$\tilde{\mathbf{r}}_{i, \text{ref}} = \mathbf{r}_{i, \text{ref}} - \frac{1}{\sum_{j} m_j} \sum_{j=1}^N m_j \mathbf{r}_{j, \text{ref}} \quad [M]$$
$$\tilde{\mathbf{r}}_{i, \text{target}} = \mathbf{r}_{i, \text{target}} - \frac{1}{\sum_{j} m_j} \sum_{j=1}^N m_j \mathbf{r}_{j, \text{target}} \quad [M]$$

The mass-weighted covariance matrix $\mathbf{C} \in \mathbb{R}^{3 \times 3}$ is defined as:
$$\mathbf{C} = \sum_{i=1}^N m_i \, \tilde{\mathbf{r}}_{i, \text{ref}} \, \tilde{\mathbf{r}}_{i, \text{target}}^T = \tilde{\mathbf{R}}_{\text{ref}}^T \mathbf{M} \tilde{\mathbf{R}}_{\text{target}} \quad [M]$$

In tensor index notation:
$$C_{\alpha \beta} = \sum_{i=1}^N m_i \, \tilde{r}_{i, \alpha}^{(\text{ref})} \, \tilde{r}_{i, \beta}^{(\text{target})}, \quad \alpha, \beta \in \{x, y, z\} \quad [M]$$

### 2.2 Matrix Symmetry Invariants [M]
1. **Self-Covariance Symmetry:** When $\mathbf{R}_{\text{target}} = \mathbf{R}_{\text{ref}}$, the covariance matrix $\mathbf{C}_{\text{self}}$ is identically symmetric and positive semi-definite:
   $$\mathbf{C}_{\text{self}} = \tilde{\mathbf{R}}_{\text{ref}}^T \mathbf{M} \tilde{\mathbf{R}}_{\text{ref}} = \mathbf{C}_{\text{self}}^T \quad [M]$$
   $$\|\mathbf{C}_{\text{self}} - \mathbf{C}_{\text{self}}^T\|_F \equiv 0 \quad (\text{tolerance: } < 10^{-14}) \quad [M]$$
2. **General Cross-Covariance Asymmetry:** When $\mathbf{R}_{\text{target}}$ is related to $\mathbf{R}_{\text{ref}}$ by a non-trivial spatial rotation $\mathbf{Q} \in SO(3)$ ($\mathbf{Q} \ne \mathbf{I}$), $\mathbf{C}$ is generally non-symmetric:
   $$\mathbf{C} = \tilde{\mathbf{R}}_{\text{ref}}^T \mathbf{M} (\tilde{\mathbf{R}}_{\text{ref}} \mathbf{Q}^T) = \mathbf{C}_{\text{self}} \mathbf{Q}^T \ne \mathbf{C}^T \quad (\text{for generic } \mathbf{Q}) \quad [M]$$

### 2.3 Frobenius Norm & Trace Invariant [M]
The Frobenius norm of the covariance matrix is defined as:
$$\|\mathbf{C}\|_F = \sqrt{\sum_{\alpha=1}^3 \sum_{\beta=1}^3 C_{\alpha \beta}^2} = \sqrt{\operatorname{Tr}(\mathbf{C}^T \mathbf{C})} \quad [M]$$

For self-covariance, the matrix trace satisfies the sum-of-squares relationship:
$$\operatorname{Tr}(\mathbf{C}_{\text{self}}) = \sum_{i=1}^N m_i \|\tilde{\mathbf{r}}_{i, \text{ref}}\|^2 \quad [M]$$

### 2.4 Analytic Gradient Correspondence to Bilinear Displacement Trace Product [M]
Consider the scalar objective function defined by contracting $\mathbf{C}$ with an arbitrary constant test matrix $\mathbf{A} \in \mathbb{R}^{3 \times 3}$:
$$\Phi(\mathbf{R}_{\text{target}}) = \operatorname{Tr}(\mathbf{A}^T \mathbf{C}) \quad [M]$$

Expanding $\mathbf{C}$:
$$\Phi = \operatorname{Tr}\left(\mathbf{A}^T \sum_{i=1}^N m_i \tilde{\mathbf{r}}_{i, \text{ref}} \tilde{\mathbf{r}}_{i, \text{target}}^T\right) = \sum_{i=1}^N m_i \tilde{\mathbf{r}}_{i, \text{target}}^T \mathbf{A}^T \tilde{\mathbf{r}}_{i, \text{ref}} \quad [M]$$

The analytic gradient with respect to the centered coordinate of atom $k$, $\tilde{\mathbf{r}}_{k, \text{target}}$, is:
$$\nabla_{\tilde{\mathbf{r}}_{k, \text{target}}} \Phi = m_k \mathbf{A}^T \tilde{\mathbf{r}}_{k, \text{ref}} \quad [M]$$

Taking into account the COM translation projection operator $\mathbf{P}_{\text{COM}} = \mathbf{I}_{N} - \frac{1}{M_{\text{total}}} \mathbf{1} \mathbf{m}^T$:
$$\frac{\partial \Phi}{\partial \mathbf{r}_{k, \text{target}}} = m_k \mathbf{A}^T \tilde{\mathbf{r}}_{k, \text{ref}} - \frac{m_k}{M_{\text{total}}} \sum_{j=1}^N m_j \mathbf{A}^T \tilde{\mathbf{r}}_{j, \text{ref}} = m_k \mathbf{A}^T \tilde{\mathbf{r}}_{k, \text{ref}} \quad [M]$$
since by definition $\sum_{j=1}^N m_j \tilde{\mathbf{r}}_{j, \text{ref}} \equiv \mathbf{0}$.

This mathematically proves that the analytic gradient of the trace product corresponds exactly to the bilinear displacement trace product, validating Acceptance Criteria L3_Decomposition_Task_1_VR01.md:L306-L307 [M].

---

## 3. Interface Contracts & Component Architecture [D]

### 3.1 Primary Interface Signatures [D]

```python
def compute_mass_weighted_covariance_matrix(
    coords_ref: np.ndarray,
    coords_target: np.ndarray,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    center: bool = True,
    tol: float = 1e-12,
) -> np.ndarray:
    """Compute the mass-weighted covariance (Gram) matrix between reference and target geometries. [M]"""
    ...

def compute_covariance_frobenius_norm(
    cov_matrix: np.ndarray,
) -> Union[float, np.ndarray]:
    """Compute the Frobenius norm ||C||_F = sqrt(Tr(C^T C)) of covariance matrix/batch. [M]"""
    ...

def check_covariance_symmetry(
    cov_matrix: np.ndarray,
    tol: float = 1e-12,
) -> Union[bool, np.ndarray]:
    """Verify matrix symmetry condition ||C - C^T||_F < tol. [M]"""
    ...
```

### 3.2 Dimensionality & Broadcasting Contracts [D]
- **Unbatched Inputs:** `coords_ref` is $(N, 3)$, `coords_target` is $(N, 3)$, `masses` is $(N,)$ -> returns `(3, 3)`.
- **Batched Target Inputs:** `coords_ref` is $(N, 3)$, `coords_target` is $(B, N, 3)$, `masses` is $(N,)$ -> returns `(B, 3, 3)`.
- **Batched Pairwise Inputs:** `coords_ref` is $(B, N, 3)$, `coords_target` is $(B, N, 3)$ -> returns `(B, 3, 3)`.
- **Data Type Enforcement:** Strict `np.float64` input casting and output return.

---

## 4. Level 4 Work Breakdown Structure (WBS Dictionary) [M]

```
+===================================================================================================================+
|                                    WBS LEVEL 4 WORK PACKAGE DICTIONARY - TASK 1.4.1                               |
+---------------+-------------------------------------------------+-------------+-------------------+---------------+
| WBS Element   | Work Package Title                              | Assigned    | Target Artifact   | Provenance    |
+---------------+-------------------------------------------------+-------------+-------------------+---------------+
| WBS 1.4.1.1   | Vectorized Mass-Weighted Covariance Formulator  | @cochem-coder| src/../aligner.py | [M]           |
| WBS 1.4.1.2   | Matrix Symmetry & Frobenius Conditioning Engine | @cochem-coder| src/../aligner.py | [M]           |
| WBS 1.4.1.3   | Dynamic Mendeleev Nuclide Mass Integration      | @cochem-coder| src/../aligner.py | [M]           |
| WBS 1.4.1.4   | Pre-Centering vs Automatic COM Translation      | @cochem-coder| src/../aligner.py | [M]           |
| WBS 1.4.1.5   | Analytic Gradient Bilinear Verification Suite   | cochem-tester| tests/../test_*.py| [M]           |
| WBS 1.4.1.6   | Microsecond Latency Performance SLA Benchmark   | cochem-tester| tests/../test_*.py| [E]           |
| WBS 1.4.1.7   | Adversarial Fuzzing, Nan/Inf & Mass Guards      | adversary   | tests/../test_*.py| [M]           |
+---------------+-------------------------------------------------+-------------+-------------------+---------------+
```

### 4.1 Detailed WBS Specifications [M]

#### WBS 1.4.1.1: Vectorized Mass-Weighted Covariance Formulator [M]
- **Target Function:** `compute_mass_weighted_covariance_matrix()` in `src/cochem_base/physics/eckart_aligner.py` [M].
- **Formulation:** Compute $\mathbf{C} = \tilde{\mathbf{R}}_{\text{ref}}^T \mathbf{M} \tilde{\mathbf{R}}_{\text{target}}$ using optimized BLAS matrix products (`np.einsum('...ik,...jk->...ij')` or `np.matmul`) [M].
- **Broadcasting:** Support unbatched $(N, 3)$ with batched $(B, N, 3)$ without extraneous memory copies [D].
- **Acceptance Criteria:** Output shape is $(3, 3)$ or $(B, 3, 3)$, dtype `np.float64` [M].

#### WBS 1.4.1.2: Matrix Symmetry & Frobenius Conditioning Engine [M]
- **Target Functions:** `compute_covariance_frobenius_norm()` and `check_covariance_symmetry()` in `src/cochem_base/physics/eckart_aligner.py` [M].
- **Formulation:** $\|\mathbf{C}\|_F = \sqrt{\sum C_{ij}^2}$, symmetry check evaluates $\|\mathbf{C} - \mathbf{C}^T\|_F < \text{tol}$ [M].
- **Acceptance Criteria:** Self-covariance passes symmetry check with $\text{tol} = 10^{-14}$; rotated geometries return `False` [M].

#### WBS 1.4.1.3: Dynamic Mendeleev Nuclide Mass Integration [M]
- **Integration:** Call `cochem_base.physics.nuclide_resolver.disambiguate_mass()` when `masses=None` and `symbols` provided [M].
- **Zero Static Dictionaries Mandate:** Zero hardcoded dictionaries containing element masses allowed [M].
- **Acceptance Criteria:** Correctly resolves isotopic masses for ${}^{18}\text{O}$, $\text{D}$, $\text{T}$ [M].

#### WBS 1.4.1.4: Pre-Centering vs Automatic COM Translation [M]
- **Behavior:** When `center=True` (default), invoke `translate_to_center_of_mass()`; when `center=False`, assume coordinates are already centered [M].
- **Acceptance Criteria:** Results for `center=True` and pre-centered coordinates with `center=False` agree to within machine precision ($< 10^{-14}$) [M].

#### WBS 1.4.1.5: Analytic Gradient Bilinear Verification Suite [M]
- **Target File:** `tests/base/test_eckart_covariance_invariants.py` [M].
- **Formulation:** Finite-difference gradient of $\operatorname{Tr}(\mathbf{A}^T \mathbf{C})$ matches analytical gradient $m_k \mathbf{A}^T \tilde{\mathbf{r}}_{k, \text{ref}}$ to within $10^{-7}$ relative error under central differences ($h = 10^{-5}$) [M].
- **Acceptance Criteria:** All finite difference comparisons pass across all atoms and Cartesian coordinates [M].

#### WBS 1.4.1.6: Microsecond Latency Performance SLA Benchmark [E]
- **Target Test:** `test_performance_microsecond_benchmark()` [E].
- **Specification:** System of $N=100$ atoms executed for 1,000 warm iterations measured via `time.perf_counter()` [E].
- **Acceptance Criteria:** Mean execution latency per call is strictly $< 15.0\,\mu\text{s}$ [E].

#### WBS 1.4.1.7: Adversarial Fuzzing, NaN/Inf & Mass Guards [M]
- **Target Guards:** Rejection of `np.nan`, `np.inf`, non-positive masses ($m \le 0$), empty arrays, and dimension mismatches [M].
- **Acceptance Criteria:** Explicit `ValueError` or `TypeError` raised; zero silent numerical corruptions [M].

---

## 5. Zero-Mock Test Suite & Authentic Physical Fixtures [M]

### 5.1 Authentic Chemical Fixtures Mandate [M]
All unit and regression tests must load authentic physical coordinate fixtures from `tests/data/`:
- `water.xyz`: Authentic water monomer ($C_{2v}$ geometry, $N=3$ atoms) [M].
- `water_dimer.xyz`: Authentic water dimer ($C_s$ geometry, $N=6$ atoms) [M].
- Isotopic variants: Authentic masses dynamically resolved for ${}^{18}\text{O}$ ($17.999160\,\text{u}$), $\text{D}$ ($2.014102\,\text{u}$), $\text{T}$ ($3.016049\,\text{u}$) [M].

### 5.2 Test Suite Execution Matrix [M]
The following 11 deterministic tests in `tests/base/test_eckart_covariance_invariants.py` govern acceptance:
1. `test_water_monomer_covariance_self_symmetry`: Symmetry, Frobenius norm, positive semi-definiteness on $\text{H}_2\text{O}$ [M].
2. `test_water_dimer_batch_covariance`: Batched tensor broadcasting on $(\text{H}_2\text{O})_2$ with Pythagorean rotation [M].
3. `test_analytic_gradient_bilinear_trace_product`: Exact correspondence between numerical and analytic gradients [M].
4. `test_dynamic_mendeleev_symbols_resolution`: Dynamic mass resolution for heavy and isotopic water [M].
5. `test_precentered_vs_uncentered_equivalence`: Bitwise equivalence between pre-centered and `center=True` modes [M].
6. `test_frobenius_norm_and_numerical_conditioning`: Sub-multiplicativity and scaling properties of $\|\mathbf{C}\|_F$ [M].
7. `test_performance_microsecond_benchmark`: SLA enforcement ($< 15.0\,\mu\text{s}$ per call for $N=100$) [E].
8. `test_adversarial_nan_inf_fuzzing`: Rejection of NaN/Inf in coordinates and masses [M].
9. `test_adversarial_dimensional_mismatch`: Rejection of mismatched coordinates and atom counts [M].
10. `test_negative_or_zero_mass_rejection`: Rejection of non-positive or empty mass arrays [M].
11. `test_covariance_symmetry_asymmetric_geometry`: Confirmation that rotated geometries yield non-symmetric $\mathbf{C}$ [M].

---

## 6. Anti-Spoofing & Method Matrix Compliance Verification [M]

### 6.1 Strict Zero-Mock & Anti-Tampering Mandates [M]
- **ASP-01 (Zero Mocks):** Zero use of `unittest.mock`, `MagicMock`, `patch`, or stub functions [M].
- **ASP-02 (Dynamic Mendeleev):** Zero hardcoded static mass dictionaries; dynamic retrieval via `disambiguate_mass()` [M].
- **ASP-03 (Banned Generators):** Zero use of `np.random`, `random`, synthetic loop generators, or list comprehension synthetic spoofing [M].
- **ASP-04 (Zero Amnesty Bypass):** Banned generators cannot be amnestied; `ci_tools/anti_spoof_linter.py` must enforce unconditional rejection [M].

---

## 7. Dual-Auditor Verification & Sign-off Gates [M]

```
+===================================================================================================================+
|                                    DUAL-AUDITOR ASYMMETRIC VERIFICATION MATRIX                                    |
+--------------------------+------------------------------------+---------------------------------------------------+
| Auditor Persona          | Verification Focus                 | Verification Criteria                             |
+--------------------------+------------------------------------+---------------------------------------------------+
| cochem-audit             | Static Architectural Integrity     | - AST compliance via anti_spoof_linter.py [M]     |
|                          | Method Matrix v4.1 Compliance      | - Zero static mass dictionaries [M]               |
|                          | Provenance Tagging Check           | - 100% bitwise parity Primary vs Mirror [M]       |
+--------------------------+------------------------------------+---------------------------------------------------+
| adversary                | Dynamic Red-Team Penetration       | - 11/11 tests pass in test_eckart_covariance [M]  |
|                          | Fault Injection & Fuzzing          | - Microsecond benchmark < 15.0 µs [E]             |
|                          | Anti-Tamper Checksum Verification  | - Cryptographic audit receipt signed [M]          |
+===================================================================================================================+
```

---

## 8. Ratification & Roll-Call Sign-off [M]

Promulgated under the authority of the Presiding Chair of the CoChem Agent Council:
- **`cochem-sdp-manager` (Presiding Chair / SDPM):** `RATIFIED_AND_PROMULGATED` [M]
- **Security Baseline:** Council Emergency Session 015/016 (`COUNCIL-SESSION-TASK-1-4-1-AUDIT-DISPATCH-016`) [M]
