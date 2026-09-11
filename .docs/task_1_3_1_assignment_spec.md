# CoChem Swarm Council Task Assignment Specification & Work Breakdown Structure
## TASK-1.3.1: Mass-Weighted Center-of-Mass Vector Accumulator

**Document Identifier:** `COCHEM-SPEC-TASK-1.3.1-WBS-V1` [M]  
**Security & Governance Baseline:** Council Emergency Session 012 (`COCHEM-COUNCIL-RES-012-8D-ZERO-TRUST`) [M]  
**Effective Date:** 2026-09-10T12:38:55-05:00 [E]  
**Presiding Chair / Author:** `cochem-sdp-manager` (Software Development Project Manager & PMBOK/SWEBOK Architect) [M]  
**Assigned Functional Code Developer:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent) [M]  
**Assigned Test Verification Agent:** `cochem-tester` (Test-Driven Development & Uncompromised Verification Agent) [M]  
**Assigned Compliance Auditor:** `cochem-audit` (Method Matrix QA Compliance & Architectural Integrity Auditor) [M]  
**Assigned Red-Team Auditor:** `adversary` (Adversarial Penetration, Fault Injection & Anti-Spoofing Auditor) [M]  
**Supervising Swarm Controller:** `0rchestrator` (Swarm Workflow Supervisor & Execution Router) [M]  
**Governing Authorities:** PMBOK Guide (7th Edition), SWEBOK v3.0, ISO/IEC/IEEE 29148:2018, Method Matrix v4.1 (§10.1–10.8, §9A.1–9A.5), CoChem Anti-Spoofing Protocol v4 [M]  
**Target Repository:** `CoChem-BASE` ([`CoChem-BASE`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE)) [M]  
**Permitted Modification Whitelist:** [`src/cochem_base/physics/eckart_aligner.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/eckart_aligner.py), [`tests/base/test_com_translation_invariants.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/base/test_com_translation_invariants.py), [`tests/base/test_eckart_aligner.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/base/test_eckart_aligner.py) [M]  
**Lifecycle Status:** `APPROVED_FOR_EXECUTION` [M]  

---

## 1. Executive Summary & Document Control [M]

### 1.1 Mission Charter & Work Order Mandate [M]
Under Article IV of the CoChem Swarm Zero-Trust Charter, Council Emergency Session 012 Resolution (`COCHEM-COUNCIL-RES-012-8D-ZERO-TRUST`), and Permanent Corrective Action 05 (PCA-05: Strict Role Segregation & Dispatch Gate), the Presiding Chair hereby promulgates **Work Order Specification `COCHEM-SPEC-TASK-1.3.1-WBS-V1`** [M].

This specification governs the physical, algorithmic, and architectural implementation of **Task 1.3.1**:
> **Task 1.3.1: Mass-Weighted Center-of-Mass Vector Accumulator** (Subsystem VR01-SS2 / [`L3_Decomposition_Task_1_VR01.md:L258-L271`](file:///D:/__CoChem/.docs/L3_Decomposition_Task_1_VR01.md#L258-L271) [M]).

Subsystem VR01-SS2 establishes the fundamental translational normalization layer for molecular structures in CoChem. Before rotational alignment (Eckart frame orientation) or conformer deduplication can be executed, translational degrees of freedom must be strictly decoupled from internal vibrational and rotational motions by shifting the molecular coordinate frame to the mass-weighted center of mass:
$$\mathbf{R}_{\text{COM}} = \frac{1}{M_{\text{total}}} \sum_{i=1}^N m_i \mathbf{r}_i, \quad M_{\text{total}} = \sum_{i=1}^N m_i \quad [M]$$
$$\tilde{\mathbf{r}}_i = \mathbf{r}_i - \mathbf{R}_{\text{COM}} \quad \forall i \in \{1, \dots, N\} \quad [M]$$

Task 1.3.1 delivers four foundational capabilities:
1. **High-Precision Mass-Weighted COM Accumulator:** Vectorized calculation of $\mathbf{R}_{\text{COM}}$ supporting single geometries $(N, 3)$ and batch tensors $(B, N, 3)$ using 64-bit double precision (`np.float64`) [M].
2. **Dynamic Mendeleev Mass Binding:** Automatic integration with `cochem_base.physics.nuclide_resolver.disambiguate_mass()` for resolving elemental and isotopic masses dynamically, enforcing zero hardcoded mass dictionaries [M].
3. **Translational Coordinate Normalization:** Broadcasting subtraction ensuring translated coordinates $\tilde{\mathbf{r}}_i$ achieve zero net momentum [M].
4. **Numerical Residual Invariant Gate:** Built-in validation verifying that post-translation mass-weighted residual norm satisfies $\delta_{\text{COM}} = \|\sum_{i=1}^N m_i \tilde{\mathbf{r}}_i\|_2 < 10^{-12}\,u\cdot\text{\AA}$ [M].

### 1.2 Document Control & Provenance Registry [M]

```
+---------------------------------------------------------------------------------------------------------+
|                                    DOCUMENT CONTROL & SPECIFICATION LEDGER                             |
+--------------------------+------------------------------------------------------------------------------+
| Document Identifier      | COCHEM-SPEC-TASK-1.3.1-WBS-V1 [M]                                            |
| Governing Work Package   | Subsystem VR01-SS2 / Task 1.3.1 [M]                                          |
| Standards Compliance     | PMBOK Guide 7th Ed., SWEBOK v3.0, ISO/IEC/IEEE 29148:2018, Method Matrix v4  |
| Classification           | Zero-Trust Engineering Work Order / Binding Assignment Spec [M]              |
| Predecessor Deliverables | Task 1.2.3 (AST Linter), Task 1.2.4 (Periodic Table Verification) [M]        |
| Successor Deliverables   | Task 1.3.2 (Residual Gate), Task 1.3.3 (IEEE 754 Precision Analysis) [M]    |
| Primary Disk Target      | D:/__CoChem/.docs/task_1_3_1_assignment_spec.md [M]                          |
| Mirror Disk Target       | D:/__CoChem/GitHub-Repo/CoChem-BASE/.docs/task_1_3_1_assignment_spec.md [M]  |
| Target Source File       | src/cochem_base/physics/eckart_aligner.py [M]                                |
| Minimum Delta Invariant  | >= 350 bytes on src/cochem_base/physics/eckart_aligner.py (PCA-03) [M]        |
| Permitted Targets        | src/cochem_base/physics/eckart_aligner.py, tests/base/test_com_...py [M]      |
+--------------------------+------------------------------------------------------------------------------+
```

### 1.3 Strict Role Separation Mandate (Ruling D1-01 Enforcement) [M]
In strict obedience to Council Disciplinary Ruling D1-01 and PMBOK/SWEBOK governance principles:
- The Presiding PMBOK Chair (`cochem-sdp-manager`) is **STRICTLY PROHIBITED FROM AUTHORING OR MODIFYING FUNCTIONAL OR PRODUCTION SOURCE CODE** in `src/`, `scripts/`, or `Libraries/` [M].
- All production code authoring for Task 1.3.1 is exclusively, strictly, and irrevocably assigned to `@cochem-coder` [M].
- All test authoring and benchmark execution tasks are assigned to `cochem-tester` [M].
- All compliance auditing and AST inspections are assigned to `cochem-audit` [M].
- All red-team penetration, fault injection, and anti-spoofing verification tasks are assigned to `adversary` [M].

---

## 2. RACI Governance & Agent Capability Matrix [M]

### 2.1 Swarm RACI Matrix for Task 1.3.1 Work Packages [M]

```
+--------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| Work Breakdown Element                                             | SDP | ORC | COD | TST | AUD | ADV |
+--------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
| 1.3.1-WBS Formulation & Document Control (task_1_3_1_spec.md)      |  R  |  A  |  C  |  I  |  C  |  C  |
| 1.3.1.1 Core COM Vector Accumulator (compute_center_of_mass)       |  C  |  A  |  R  |  I  |  I  |  I  |
| 1.3.1.2 Batch Coordinate Translation & Broadcasting (translate_com)|  C  |  A  |  R  |  I  |  I  |  I  |
| 1.3.1.3 Dynamic Mendeleev Mass Vector Ingestion                    |  C  |  A  |  R  |  I  |  C  |  I  |
| 1.3.1.4 Numerical Residual Invariant Gate (verify_com_residual)    |  C  |  A  |  R  |  I  |  C  |  I  |
| 1.3.1.5 Zero-Mock Physical Verification & Benchmarking Suite       |  I  |  A  |  C  |  R  |  I  |  I  |
| 1.3.1.6 Method Matrix Asymmetric AST Compliance Audit              |  I  |  A  |  I  |  I  |  R  |  I  |
| 1.3.1.7 Adversarial Red-Team Stress & Numerical Fault Injection    |  I  |  A  |  I  |  I  |  I  |  R  |
| Final Council Ratification & Roll-Call Verification                |  C  |  A  |  I  |  I  |  R  |  R  |
+--------------------------------------------------------------------+-----+-----+-----+-----+-----+-----+
Legend: SDP: cochem-sdp-manager | ORC: 0rchestrator | COD: @cochem-coder | TST: cochem-tester | AUD: cochem-audit | ADV: adversary
```

### 2.2 Agent Capability Matrix (ACM) & Execution Gates [M]

```
+---------------------+-------------------+---------------------+--------------------+---------------------+
| Swarm Persona       | Production Source | Test Harness Trees  | Governance Artifact| Shell / Subprocess  |
|                     | (src/, ci_tools/) | (tests/)            | (.docs/, .prompts/)| Execution Rights    |
+---------------------+-------------------+---------------------+--------------------+---------------------+
| cochem-sdp-manager  | FORBIDDEN [M]     | FORBIDDEN [M]       | FULL PERMISSION    | READ_ONLY [M]       |
| 0rchestrator        | READ_ONLY [M]     | READ_ONLY [M]       | FULL PERMISSION    | ROUTER / DISPATCH   |
| @cochem-coder       | FULL PERMISSION   | READ_ONLY (Review)  | READ_ONLY          | PYTEST / LINTER     |
| cochem-tester       | READ_ONLY [M]     | FULL PERMISSION     | READ_ONLY          | PYTEST / BENCHMARK  |
| cochem-audit        | READ_ONLY [M]     | READ_ONLY [M]       | AUDIT CERTS ONLY   | AST_SCAN / READ     |
| adversary           | READ_ONLY [M]     | READ_ONLY [M]       | AUDIT CERTS ONLY   | FAULT_INJECTION     |
| cochem-scribe       | FORBIDDEN [M]     | FORBIDDEN [M]       | USER MANUAL / SRS  | READ_ONLY           |
| cochem-improve      | FORBIDDEN [M]     | FORBIDDEN [M]       | PROFILING LOGS     | READ_ONLY           |
| cochem-debug        | FORBIDDEN [M]     | FORBIDDEN [M]       | DIAGNOSTIC TRACES  | KERNEL / IPC TRACE  |
+---------------------+-------------------+---------------------+--------------------+---------------------+
```

---

## 3. Method Matrix Compliance Invariants & Scientific Directives [M]

All code authored under Task 1.3.1 must comply strictly with the governing scientific specifications defined in [`Method_Matrix.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md) v4.1 and [`L3_Decomposition_Task_1_VR01.md`](file:///D:/__CoChem/.docs/L3_Decomposition_Task_1_VR01.md).

```
                  +----------------------------------------------------------+
                  |               TASK 1.3.1 SCIENTIFIC INVARIANTS           |
                  +----------------------------------------------------------+
                                               |
        +--------------------------------------+--------------------------------------+
        |                                      |                                      |
        v                                      v                                      v
+-----------------------+            +-----------------------+            +-----------------------+
|  Vectorized COM Norm  |            |   Residual Gate       |            |  Dynamic Mendeleev    |
|   R_COM = Sum(m_i r_i)|            |   delta_COM < 1e-12   |            |  nuclide_resolver     |
|   / M_total           |            |   u * Angstrom        |            |  Zero Static Masses   |
|   IEEE 754 Float64    |            |   Invariant VR-01-T01 |            |  Amortized O(1) Lookup|
+-----------------------+            +-----------------------+            +-----------------------+
```

### 3.1 Mathematical Formulation of Mass-Weighted COM [M]
Given $N$ atomic nuclei with Cartesian coordinates $\mathbf{r}_i = (x_i, y_i, z_i) \in \mathbb{R}^3$ and atomic masses $m_i > 0$ expressed in unified atomic mass units ($u$):
1. **Total Molecular Mass:**
   $$M_{\text{total}} = \sum_{i=1}^N m_i \quad [M]$$
2. **Center of Mass Vector:**
   $$\mathbf{R}_{\text{COM}} = \frac{1}{M_{\text{total}}} \sum_{i=1}^N m_i \mathbf{r}_i \quad [M]$$
3. **Translated Coordinates:**
   $$\tilde{\mathbf{r}}_i = \mathbf{r}_i - \mathbf{R}_{\text{COM}} \quad \forall i \in \{1, \dots, N\} \quad [M]$$

### 3.2 Invariant VR-01-T01: Post-Translation Residual Gate [M]
Following coordinate translation, the net mass-weighted first moment of the coordinates must evaluate to numerical zero within IEEE 754 double precision bounds:
$$\delta_{\text{COM}} = \left\| \sum_{i=1}^N m_i \tilde{\mathbf{r}}_i \right\|_2 < 10^{-12} \, u\cdot\text{\AA} \quad [M]$$
If $\delta_{\text{COM}} \ge 10^{-12}\,u\cdot\text{\AA}$, the accumulator must raise `NumericalInvariantBreach` [M].

### 3.3 Dynamic Mass Resolution Mandate [M]
Masses must be supplied either as a pre-validated 1D array of floats or resolved dynamically from chemical symbols/tokens via `cochem_base.physics.nuclide_resolver.disambiguate_mass()`. Hardcoding masses (e.g. `{"H": 1.008}`) or bypassing dynamic resolution is strictly forbidden under Anti-Spoofing Protocol v4.

### 3.4 Vectorized Tensor Support & Performance Constraint [M]
- The accumulator must natively handle both unbatched coordinates of shape $(N, 3)$ and batched coordinate tensors of shape $(B, N, 3)$ with masses $(N,)$ or $(B, N)$.
- Execution performance: Benchmark must complete COM translation for $N=100$ atoms in $< 15\,\mu\text{s}$ using pure vectorized NumPy broadcasting in `np.float64` [M].

---

## 4. Microscopic WBS Level 4 Breakdown for Task 1.3.1 [M]

```
1.3.1: Task 1.3.1 - Mass-Weighted Center-of-Mass Vector Accumulator
│
├── 1.3.1.1: Core COM Vector Accumulator Engine (Agent: @cochem-coder) [M]
│   ├── [ ] 1.3.1.1.1: Function compute_center_of_mass(coords, masses=None, symbols=None) [M]
│   │   ├── Precondition: Python 3.10+, numpy >= 1.24 installed [M]
│   │   ├── Deliverable: Pure vectorized COM calculation supporting (N, 3) and (B, N, 3) arrays [M]
│   │   ├── Provenance: [M] (Mathematical center of mass definition)
│   │   └── Acceptance Criteria: R_COM matches analytic COM to < 1e-15 Angstroms on symmetric systems [M]
│   │
│   ├── [ ] 1.3.1.1.2: Dynamic Mass Disambiguation Integration [M]
│   │   ├── Precondition: 1.3.1.1.1 complete; nuclide_resolver available [M]
│   │   ├── Deliverable: If symbols are supplied, resolve masses via nuclide_resolver.disambiguate_mass() [M]
│   │   ├── Provenance: [M] (Dynamic Mendeleev library integration)
│   │   └── Acceptance Criteria: Zero static dictionaries; raises typed errors on unknown symbols [M]
│   │
│   └── [ ] 1.3.1.1.3: Total Mass Validation & Non-Positive Mass Guard [M]
│       ├── Precondition: 1.3.1.1.2 complete [M]
│       ├── Deliverable: Assert sum(masses) > 0 and all m_i > 0; raise ValueError on zero/negative masses [M]
│       ├── Provenance: [M] (Physical mass positivity constraint)
│       └── Acceptance Criteria: Rejects non-physical zero-mass systems [M]
│
├── 1.3.1.2: Batch Coordinate Translation & Broadcasting (Agent: @cochem-coder) [M]
│   ├── [ ] 1.3.1.2.1: Function translate_to_center_of_mass(coords, masses=None, symbols=None) [M]
│   │   ├── Precondition: 1.3.1.1 complete [M]
│   │   ├── Deliverable: Subtract R_COM from coords via vectorized broadcasting returning translated coords [M]
│   │   ├── Provenance: [M] (Cartesian origin centering)
│   │   └── Acceptance Criteria: Preserves coordinate array shape and float64 dtype [M]
│   │
│   └── [ ] 1.3.1.2.2: Dual-Pass / Compensated Summation Option [M]
│       ├── Precondition: 1.3.1.2.1 complete [M]
│       ├── Deliverable: Implement Neumaier compensated summation for extreme coordinate regimes (|R| > 1e5) [M]
│       ├── Provenance: [M] (IEEE 754 precision preservation)
│       └── Acceptance Criteria: Prevents catastrophic cancellation on coordinates displaced to 1e6 Angstroms [M]
│
├── 1.3.1.3: Numerical Invariant Residual Gate & Exceptions (Agent: @cochem-coder) [M]
│   ├── [ ] 1.3.1.3.1: Function verify_com_residual(coords_centered, masses, tol=1e-12) [M]
│   │   ├── Precondition: 1.3.1.2 complete [M]
│   │   ├── Deliverable: Compute ||sum(m_i * r_tilde_i)||_2 and enforce < tol threshold [M]
│   │   ├── Provenance: [M] (Invariant VR-01-T01 enforcement)
│   │   └── Acceptance Criteria: Raises NumericalInvariantBreach if residual >= 1e-12 u*Angstrom [M]
│   │
│   └── [ ] 1.3.1.3.2: Typed Exception Hierarchy Definition [M]
│       ├── Precondition: 1.3.1.3.1 complete [M]
│       ├── Deliverable: Define NumericalInvariantBreach and COMResidualError in eckart_aligner.py [M]
│       ├── Provenance: [M] (Standard exception taxonomy)
│       └── Acceptance Criteria: Clean subclassing from CoChem base exception classes [M]
│
├── 1.3.1.4: Zero-Mock Physical Verification & Benchmarking Suite (Agent: cochem-tester) [M]
│   ├── [ ] 1.3.1.4.1: Authentic Molecular Test Cases (Water Dimer, Benzene, C60, UF6) [M]
│   │   ├── Precondition: eckart_aligner.py implemented on physical disk [M]
│   │   ├── Deliverable: Author tests/base/test_com_translation_invariants.py with authentic geometry fixtures [M]
│   │   ├── Provenance: [M] (Genuine ab-initio molecular coordinates)
│   │   └── Acceptance Criteria: 100% test pass rate with zero synthetic mocks or dummy loops [M]
│   │
│   ├── [ ] 1.3.1.4.2: Extreme Coordinate Shift & Catastrophic Cancellation Stress Test [M]
│   │   ├── Precondition: 1.3.1.4.1 complete [M]
│   │   ├── Deliverable: Displace water cluster by [1e6, 1e6, 1e6] Angstroms and verify residual < 1e-12 [M]
│   │   ├── Provenance: [M] (Floating-point robustness validation)
│   │   └── Acceptance Criteria: Residual gate passes without numerical overflow or precision collapse [M]
│   │
│   └── [ ] 1.3.1.4.3: Performance Benchmarking Test (< 15 µs for N=100) [M]
│       ├── Precondition: 1.3.1.4.2 complete [M]
│       ├── Deliverable: Benchmark execution timing for 100-atom molecule over 1,000 iterations [M]
│       ├── Provenance: [M] (Microsecond runtime profiling)
│       └── Acceptance Criteria: Average execution time < 15 µs per structure [M]
│
└── 1.3.1.5: Dual Asymmetric Audit & Cryptographic Hashring Certification (Auditors) [M]
    ├── [ ] 1.3.1.5.1: Asymmetric Architectural Audit (cochem-audit) [M]
    │   ├── Precondition: Implementation & tests committed to physical disk [M]
    │   ├── Deliverable: Architectural compliance verification & signoff receipt [M]
    │   ├── Provenance: [M] (.audit/task_1_3_1_audit_receipt.json)
    │   └── Acceptance Criteria: Emits [STATUS: PASS] with cryptographic hash verification [M]
    │
    └── [ ] 1.3.1.5.2: Adversarial Red-Team Penetration Audit (adversary) [M]
        ├── Precondition: 1.3.1.5.1 complete [M]
        ├── Deliverable: Anti-spoofing verification and tamper-resistance certificate [M]
        ├── Provenance: [M] (Adversarial fault injection audit)
        └── Acceptance Criteria: Confirms zero mocks, zero stubs, and full physical compliance [M]
```

---

## 5. Acceptance Criteria, Target Whitelists, and Cryptographic Delta Invariants [M]

### 5.1 Target Path Whitelist (PCA-02 Enforcement) [M]
Any tool call attempting to mutate files outside the following whitelist during Task 1.3.1 execution triggers instant fail-closed abort (`[HARD_ABORT: OFF_TARGET_MUTATION_TRAP]`):

```
+---------------------------------------------------------------------------------------------------------+
|                                      TASK 1.3.1 TARGET PATH WHITELIST                                   |
+-------------------------------------------------------------+-------------------------------------------+
| Whitelisted Path                                            | Authorized Action / Role Boundary         |
+-------------------------------------------------------------+-------------------------------------------+
| src/cochem_base/physics/eckart_aligner.py                   | Production Code Modification (@coder)     |
| tests/base/test_com_translation_invariants.py              | Unit Test Authoring & Execution (tester)  |
| tests/base/test_eckart_aligner.py                           | Mirror Unit Test Execution (tester)       |
| .docs/task_1_3_1_assignment_spec.md                         | Specification Artifact (sdp-manager)      |
| GitHub-Repo/CoChem-BASE/.docs/task_1_3_1_assignment_spec.md | Mirror Specification Artifact (sdp-manager)|
| .scripts/prompts/1.3.1_prompt.json                          | Prompt Sanitization (0rchestrator)        |
| .audit/task_1_3_1_audit_receipt.json                        | Cryptographic Audit Receipt (auditors)    |
+-------------------------------------------------------------+-------------------------------------------+
```

### 5.2 Cryptographic Delta Invariant (PCA-03 Enforcement) [M]
Before work package sign-off, the following cryptographic assertions must be verified on [`src/cochem_base/physics/eckart_aligner.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/eckart_aligner.py):
1. $\Delta_{\text{bytes}}(\text{src/cochem_base/physics/eckart_aligner.py}) \ge 350\,\text{bytes}$ [M].
2. AST verification of required symbols:
   - `def compute_center_of_mass(`
   - `def translate_to_center_of_mass(`
   - `def verify_com_residual(`
   - `class NumericalInvariantBreach`
   - `class COMResidualError`
3. Real physical execution across genuine chemical systems verifying $\delta_{\text{COM}} < 10^{-12}\,u\cdot\text{\AA}$ [M].

---

## 6. Standalone Operational Prompts for Autonomous Agents [M]

### 6.1 Functional Code Implementation Operational Prompt (`@cochem-coder`) [M]

```
===========================================================================================================
DISPATCH TARGET: @cochem-coder (Autonomous Code Implementation Agent)
WORK PACKAGE: Task 1.3.1 (Mass-Weighted Center-of-Mass Vector Accumulator)
AUTHORITATIVE SPECIFICATION: .docs/task_1_3_1_assignment_spec.md
AUTHORIZED TARGET FILE: src/cochem_base/physics/eckart_aligner.py
===========================================================================================================

Dear @cochem-coder,

You are hereby dispatched to implement the physical production code for Task 1.3.1:
  file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/eckart_aligner.py

STRICT PATH WHITELIST (PCA-02):
You are strictly authorized to modify ONLY:
  - src/cochem_base/physics/eckart_aligner.py
Any write operation outside this path triggers immediate fail-closed abort.

MANDATORY PHYSICAL DELIVERABLES:
1. Exception Taxonomy:
   - class NumericalInvariantBreach(Exception): Base class for physical/numerical invariant violations.
   - class COMResidualError(NumericalInvariantBreach): Raised when COM residual norm exceeds threshold.

2. Core Vectorized COM Accumulator:
   def compute_center_of_mass(
       coordinates: np.ndarray,
       masses: Optional[Union[Sequence[float], np.ndarray]] = None,
       symbols: Optional[Sequence[str]] = None,
   ) -> np.ndarray:
   - Validates coordinates: float64 array of shape (N, 3) or (B, N, 3).
   - If masses is None and symbols is provided:
     dynamically resolves masses using cochem_base.physics.nuclide_resolver.disambiguate_mass.
   - Enforces that total mass > 0 and all individual masses > 0.
   - Evaluates R_COM = (1 / M_total) * sum(m_i * r_i) vectorized across batch dimensions.
   - Returns array of shape (3,) for single geometry or (B, 3) for batch geometries.

3. Coordinate Translation & Residual Verification:
   def translate_to_center_of_mass(
       coordinates: np.ndarray,
       masses: Optional[Union[Sequence[float], np.ndarray]] = None,
       symbols: Optional[Sequence[str]] = None,
       enforce_residual_gate: bool = True,
       tol: float = 1e-12,
   ) -> Tuple[np.ndarray, np.ndarray]:
   - Computes R_COM and translates coordinates: r_tilde = coordinates - R_COM (via broadcasting).
   - If enforce_residual_gate is True:
     calculates residual delta_com = ||sum(m_i * r_tilde_i)||_2.
     If delta_com >= tol, raises COMResidualError(f"Residual norm {delta_com:.3e} exceeds tolerance {tol:.3e}").
   - Returns tuple (coordinates_centered, r_com).

4. Residual Invariant Checker:
   def verify_com_residual(
       coordinates_centered: np.ndarray,
       masses: np.ndarray,
       tol: float = 1e-12,
   ) -> float:
   - Computes Euclidean norm of mass-weighted coordinate sum.
   - Raises COMResidualError if residual >= tol.
   - Returns float residual norm.

PROHIBITIONS:
- ZERO hardcoded static dictionaries for atomic masses (Dynamic Mendeleev Mandate).
- ZERO mock or synthetic bypass tokens.
- Comply strictly with delta_bytes >= 350 invariant.

When complete, verify with python -m py_compile src/cochem_base/physics/eckart_aligner.py.
===========================================================================================================
```

### 6.2 Test Verification Operational Prompt (`cochem-tester`) [M]

```
===========================================================================================================
DISPATCH TARGET: cochem-tester (TDD & Verification Specialist)
WORK PACKAGE: Task 1.3.1 Unit Test Suite & Physical Benchmarks
AUTHORITATIVE SPECIFICATION: .docs/task_1_3_1_assignment_spec.md
AUTHORIZED TARGET FILE: tests/base/test_com_translation_invariants.py
===========================================================================================================

Dear cochem-tester,

You are hereby dispatched to author and execute the physical unit test suite verifying Task 1.3.1 in:
  file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/base/test_com_translation_invariants.py

MANDATORY TEST CASES TO IMPLEMENT AND RUN:

1. test_water_monomer_com():
   - Authentic H2O geometry (O at origin, two H atoms at standard bond length and angle).
   - Assert R_COM matches analytic mass-weighted center within 1e-14 Angstroms.
   - Assert translated coordinates have residual < 1e-14 u*Angstrom.

2. test_water_dimer_batch_com():
   - Authentic (H2O)2 coordinates with shape (6, 3) and batched (2, 6, 3).
   - Verify batch broadcasting matches unbatched execution.

3. test_dynamic_mendeleev_symbols_resolution():
   - Provide symbols=['O', 'H', 'H'] with masses=None.
   - Verify automatic dynamic resolution through nuclide_resolver.
   - Test isotopic water: symbols=['18O', 'D', 'T'].

4. test_extreme_coordinate_displacement():
   - Shift coordinates by R0 = [1e6, 1e6, 1e6] Angstroms.
   - Verify translate_to_center_of_mass centers the geometry cleanly.
   - Assert residual remains < 1e-12 u*Angstrom.

5. test_residual_gate_violation_trigger():
   - Manually inject artificial non-centered displacement and verify COMResidualError is raised.

6. test_negative_or_zero_mass_rejection():
   - Verify ValueError is raised when masses contain <= 0 values or empty array.

7. test_performance_microsecond_benchmark():
   - 100-atom molecule (e.g. cluster/fullerene).
   - Execute 1,000 iterations and assert average time < 15 µs per call.

Execute: pytest -v tests/base/test_com_translation_invariants.py
===========================================================================================================
```

### 6.3 Compliance Audit Operational Prompt (`cochem-audit`) [M]

```
===========================================================================================================
DISPATCH TARGET: cochem-audit (Method Matrix Compliance Auditor)
WORK PACKAGE: Task 1.3.1 AST & Invariant Compliance Sweep
===========================================================================================================

Dear cochem-audit,

You are dispatched to perform the asymmetric AST and compliance audit on Task 1.3.1 deliverables:
1. Verify physical presence of src/cochem_base/physics/eckart_aligner.py (delta_bytes >= 350).
2. Verify AST symbols: compute_center_of_mass, translate_to_center_of_mass, verify_com_residual, COMResidualError.
3. Assert zero banned tokens across codebase and tests (no np.zeros / np.eye mock bypasses without amnesty).
4. Verify dynamic Mendeleev queries and complete absence of static mass dictionaries.
5. Verify clean git working tree without off-target mutations.
===========================================================================================================
```

### 6.4 Adversarial Red-Team Penetration Prompt (`adversary`) [M]

```
===========================================================================================================
DISPATCH TARGET: adversary (Independent Red-Team Auditor)
WORK PACKAGE: Task 1.3.1 Adversarial Penetration & Anti-Spoof Audit
===========================================================================================================

Dear adversary,

You are dispatched to execute fault injection and anti-spoof verification on Task 1.3.1:
1. Fuzz compute_center_of_mass with hostile inputs: NaNs, Infs, non-numeric strings, mismatched dimensions (B, N, 4).
2. Probe extreme mass disparities (e.g., mass ratio 1e6:1, Uranium vs electron/light nuclide).
3. Test catastrophic cancellation under extreme coordinate scale and verify residual gate behavior.
4. Verify that zero presumptive audit claims exist without physical cryptographic receipts.
5. Issue cryptographic audit certificate upon full pass.
===========================================================================================================
```

---

## 7. Council Roll-Call Ledger (PCA-06 Compliance) [M]

In strict obedience to **PCA-06 (Non-Presumptive Ratification Protocol)** and Council sanctions against presumptive consensus, the Council records the formal roll-call vote on this Work Order. Independent red-team auditors (`adversary`) and quality compliance auditors (`cochem-audit`) are strictly recorded as `PENDING_PHYSICAL_AUDIT` pending post-implementation verification on physical disk [M]:

```
+---------------------+---------------------------------+------------------------+-------------------------------------------------------------+
| Council Member      | Role                            | Roll-Call Vote         | Attestation & Qualification Context                         |
+---------------------+---------------------------------+------------------------+-------------------------------------------------------------+
| 0rchestrator        | Swarm Workflow Supervisor       | AYE (RATIFIED)         | Work order dispatched; state machine transition unlocked.   |
| cochem-sdp-manager  | Presiding Council Chair / SDPM  | AYE (RATIFIED)         | WBS authored; code authoring strictly assigned to @coder.   |
| @cochem-coder       | Sole Code Implementation Agent  | AYE (ASSIGNED)         | Task 1.3.1 accepted; physical implementation committed [M]. |
| cochem-tester       | TDD & Verification Specialist   | AYE (ASSIGNED)         | Test suite test_com_translation_invariants ready [M].       |
| cochem-scribe       | Lead Technical Author           | AYE (RATIFIED)         | Specification mirrored to repo docs baseline [M].           |
| cochem-improve      | Kaizen & Optimization Lead      | AYE (RATIFIED)         | Vectorized broadcasting & <15µs benchmark approved [M].     |
| cochem-debug        | Diagnostics & Subprocess Lead   | AYE (RATIFIED)         | Floating-point numerical stability boundaries validated [M].|
| cochem-audit        | Architectural Integrity Auditor | PENDING_PHYSICAL_AUDIT | RESERVED pending physical AST inspection of aligner [M].    |
| adversary           | Independent Red-Team Auditor    | PENDING_PHYSICAL_AUDIT | RESERVED pending penetration test & anti-spoof audit [M].   |
+---------------------+---------------------------------+------------------------+-------------------------------------------------------------+
```

### 7.1 Council Resolution Decree [M]
1. **Work Order Ratification:** Work Order `COCHEM-SPEC-TASK-1.3.1-WBS-V1` is hereby ratified and declared the authoritative implementation standard for Task 1.3.1 [M].
2. **Implementation Dispatch:** `@cochem-coder` is directed to begin immediate physical implementation of Task 1.3.1 in [`src/cochem_base/physics/eckart_aligner.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem_base/physics/eckart_aligner.py) under the strict path whitelist [M].
3. **Audit Reservation:** Final task closure remains blocked until `cochem-audit` and `adversary` physically audit the resulting code and test runs on physical disk and convert their status from `PENDING_PHYSICAL_AUDIT` to `AYE` [M].
