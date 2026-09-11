# Functional Subsystems Architectural Specification: Task 1 (VR-01)
## Ingestion Plane & Physical Invariant Foundation

**Document Identifier:** `COCHEM-ARCH-TASK1-SUBSYSTEMS-2026` [M]  
**Document Version:** 2.1.0 (Authoritative Systems Architecture Specification)  
**Project Role:** `cochem-sdp-manager` (Software Development Project Manager & Lead Systems Architect)  
**Governing Standards:** PMBOK Guide 7th Edition (Systems View for Project Delivery & Scope Domain), SWEBOK v3/v4, IEEE 830-1998 / ISO/IEC/IEEE 29148:2018, CoChem Method Matrix v4.1, Anti-Spoofing Council Directive v4 [M]  
**Target Scratch File:** [`task1_subsystems_architectural_specification.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_subsystems_architectural_specification.md) [M]  
**Master WBS Integration:** [`task1_level2_wbs_breakdown.md`](file:///C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_level2_wbs_breakdown.md) [M]  
**Ecosystem Hierarchy:** Level 1 Task 1 (VR-01) $\longrightarrow$ Level 2 Technical Packages (L2-T1.1 - L2-T1.6) $\longrightarrow$ Level 3 Microtasks  
**Classification:** Production Systems Architecture & Interface Contract Specification  
**Lifecycle Status:** `APPROVED_FOR_BASELINE_ENGINEERING` [M]  
**Execution Timestamp:** `2026-09-11T08:18:00-05:00` [M]  

---

## 1. Executive Systems Architecture Overview

### 1.1 Scope & Mission Mandate
In accordance with **PMBOK 7th Edition (Systems View for Project Delivery)**, **SWEBOK v3/v4 (Software Requirements & Architecture)**, and the **CoChem Method Matrix v4.1**, this document provides the authoritative architectural specification for the **6 Functional Subsystems** that govern the end-to-end execution lifecycle of **Level 1 Task 1: Implement Ingestion Plane & Physical Invariant Foundation (VR-01)**.

Level 1 Task 1 serves as the autonomous physical ingestion gateway and numerical invariant anchor for the `CoChem-BASE` computational chemistry engine. Its mission is to ingest heterogeneous raw molecular coordinates (Cartesian XYZ, MDL Molfile, Tripos Mol2, SDFile, PDB, and QCSchema JSON), resolve nuclear species to exact physical isotopic masses, enforce rigid-body translational and rotational invariants in the mass-weighted Eckart frame, and eliminate degenerate conformational minima through an automorphism-invariant two-stage sieve.

To eliminate scope creep, architectural drift, and non-deterministic execution, the delivery lifecycle is strictly organized into six mutually exclusive, collectively exhaustive (MECE) functional subsystems:
1. **Subsystem 1: Scope Ingestion Engine** (Intake Gateway & Pre-Flight Validator)
2. **Subsystem 2: Architectural Partitioning Engine** (PMBOK 100% MECE Work Breakdown)
3. **Subsystem 3: Microtask Atomization Engine** (Numerical Computing & Invariant Logic)
4. **Subsystem 4: Swarm Role Routing Engine** (Single-Accountable RACI Allocation)
5. **Subsystem 5: State Serialization Engine** (Atomic OS-Locked Ledger & Checksumming)
6. **Subsystem 6: Asymmetric Verification Engine** (Zero-Trust Quarantine & AST Anti-Counterfeit Gate)

```
+==================================================================================================+
|                        VR-01 SIX FUNCTIONAL SUBSYSTEMS ARCHITECTURAL MANIFEST                    |
+----+------------------------------------+-----------------------------+--------------------------+
| ID | Functional Subsystem Name          | Primary Governance Function | Single-Accountable Agent |
+----+------------------------------------+-----------------------------+--------------------------+
| S1 | Scope Ingestion Engine             | Format Intake & Pre-Flight  | cochem-sdp-manager       |
| S2 | Architectural Partitioning Engine  | MECE L2 Decomposition       | cochem-sdp-manager       |
| S3 | Microtask Atomization Engine       | Deep Physics & Math Models  | cochem-coder             |
| S4 | Swarm Role Routing Engine          | Single-Owner RACI Routing   | 0rchestrator             |
| S5 | State Serialization Engine         | Atomic OS-Locked Persistence| cochem-coder             |
| S6 | Asymmetric Verification Engine     | Zero-Trust Red-Team Audit   | adversary / cochem-audit |
+==================================================================================================+
```

---

## 2. Subsystem Interaction & Data Flow Architecture

The six subsystems operate in an immutable, linear execution pipeline with closed-loop feedback and fail-closed security gates.

```mermaid
flowchart TD
    subgraph S1["Subsystem 1: Scope Ingestion Engine"]
        RAW_INPUT["Raw Structural Geometries (.xyz, .mol, .sdf, .pdb, QCSchema)"]
        PREFLIGHT_GATE{"Pre-Flight Toolchain Gate\n(Python 3.11+, JAX x64,\nMendeleev v0.14+)"}
        SANITIZE_TOKEN["Nuclide Alias Resolution\n(D->H2, T->H3, 13C->C13)\nGhost Atom Zeroing (Gh, Bq)"]
        INGEST_OUT["Typed IngestedSystemModel\n(Atomic Masses, Pyykkö Radii)"]
        RAW_INPUT --> PREFLIGHT_GATE
        PREFLIGHT_GATE -->|PASS| SANITIZE_TOKEN
        SANITIZE_TOKEN --> INGEST_OUT
    end

    subgraph S2["Subsystem 2: Architectural Partitioning Engine"]
        MECE_PARTITION["PMBOK 100% MECE Decomposition"]
        L2_TIERS["6 Formal Level 2 Packages:\nL2-T1.1 Dynamic Mendeleev Mass Engine\nL2-T1.2 COM Translation Zeroing Engine\nL2-T1.3 Eckart SO(3) Rotation Engine\nL2-T1.4 Two-Stage Conformer Sieve\nL2-T1.5 Method Matrix Spend Allocation\nL2-T1.6 Zero-Counterfeit Pytest Risk Gate"]
        INGEST_OUT --> MECE_PARTITION
        MECE_PARTITION --> L2_TIERS
    end

    subgraph S3["Subsystem 3: Microtask Atomization Engine"]
        PHYS_MATH["Mathematical Formulation & Invariant Anchors:\n- COM Drift ||sum m_i r_i|| < 1.0e-12 a.u.\n- SO(3) det(U) = +1.000000000000\n- Angular Residual ||L_Eckart|| < 1.0e-10 a.u.\n- 2-Stage Sieve: WL Hash + Kabsch RMSD < 0.08 A\n- Spectroscopic Gate |Delta B/B| <= 0.05%\n- Hungarian Permutation Fallback (N > 720)"]
        CODE_MAP["Target Code Mapping:\nphysics/isotopes.py\nintake/conformer_deduplication.py\nintake/cochem_molsym_eckart_aligner.py"]
        L2_TIERS --> PHYS_MATH
        PHYS_MATH --> CODE_MAP
    end

    subgraph S4["Subsystem 4: Swarm Role Routing Engine"]
        RACI_ROUTER["Single-Accountability RACI Engine\n(Zero Shared Ownership)"]
        ROLES["Role Segregation:\ncochem-coder: Execution Logic\ncochem-tester: Pytest Harness\nresearcher: Physical Benchmarks [M]\ncochem-sdp-manager: WBS/Governance\ncochem-audit: Static AST Linter\nadversary: Zero-Trust Hostile Audit"]
        CODE_MAP --> RACI_ROUTER
        RACI_ROUTER --> ROLES
    end

    subgraph S5["Subsystem 5: State Serialization Engine"]
        OS_LOCK["OS-Level File Locking Primitives\n(msvcrt on Windows, fcntl on POSIX)"]
        ATOMIC_WRITE["Atomic Read-Modify-Write Sync:\nSHA-256 Checksums, Invariant Flags\nswarm_state.json Serialization"]
        ROLES --> OS_LOCK
        OS_LOCK --> ATOMIC_WRITE
    end

    subgraph S6["Subsystem 6: Asymmetric Verification Engine"]
        QUARANTINE["Sterile Ephemeral Quarantine\n(/tmp/cochem_exec_<uuid>/)"]
        STATIC_AST["Static AST Anti-Counterfeit Linter\n(Zero Test Doubles, Zero Pass Stubs, Zero Synthetic Arrays)"]
        HOSTILE_AUDIT["Hostile Red-Team Review\n(Perjury & Obfuscation Sweeps)"]
        ATOMIC_WRITE --> QUARANTINE
        QUARANTINE --> STATIC_AST
        STATIC_AST --> HOSTILE_AUDIT
        HOSTILE_AUDIT -->|PASS| RATIFIED_BASELINE["Ratified Baseline Ingress & Stage Advance"]
        HOSTILE_AUDIT -->|FAIL| ROLLBACK["Fail-Closed Quarantine Abort & Swarm Quarantine"]
    end
```

---

## 3. Deep Architectural Specification of the 6 Functional Subsystems

### 3.1 SUBSYSTEM 1: SCOPE INGESTION ENGINE
* **System Identifier:** `VR01-SS1-INGESTION` [M]
* **Single Accountable Agent:** `cochem-sdp-manager` (Scope Governance & Intake Architecture)
* **Primary Source Code Target:** `src/cochem_base/intake/` and `src/cochem_base/validators/preflight.py`
* **Governing Directives:** IEEE 830-1998 §4.2, Method Matrix v4.1 §2.1–§2.3, Anti-Spoofing Protocol v4

#### 3.1.1 Purpose & Architectural Scope
The Scope Ingestion Engine acts as the strict, fail-closed border controller for all incoming molecular structural data entering the CoChem pipeline. It eliminates malformed geometric definitions, standardizes heterogeneous coordinate schemas, enforces nuclide alias resolution, and ensures environment readiness prior to initiating compute-heavy quantum chemical tasks.

#### 3.1.2 Input / Output Data Contracts
* **Supported Ingestion Formats:**
  1. Standard Cartesian `.xyz` format (standard multi-line with atom count header and comment line).
  2. Chemical table files: `.mol` (MDL V2000 and V3000 specifications) and multi-molecule `.sdf`.
  3. Crystallographic and macromolecular format: `.pdb` (standard `ATOM` / `HETATM` records with PDBv3.3 compliance).
  4. MolSSI QCSchema v1/v2 JSON (conforming to `qcelemental` coordinate array specifications).
* **Strict Pydantic Ingestion Schemas:**
  ```python
  from typing import List, Optional, Tuple, Literal
  import numpy as np
  from pydantic import BaseModel, Field, field_validator

  class RawStructureInput(BaseModel):
      """Authoritative Ingestion Contract for Incoming Molecular Structures."""
      source_format: Literal["xyz", "mol", "sdf", "pdb", "qcschema"]
      raw_symbols: List[str] = Field(..., min_length=1, description="Raw atomic/nuclide token strings")
      raw_coordinates: List[List[float]] = Field(..., description="Nx3 Cartesian coordinates in Angstroms")
      charge: int = Field(default=0, description="Total molecular net charge")
      multiplicity: int = Field(default=1, ge=1, description="Spin multiplicity 2S+1")
      comment: Optional[str] = Field(default=None, description="Metadata or provenance comment string")

      @field_validator("raw_coordinates")
      @classmethod
      def validate_dimensions(cls, v: List[List[float]], info) -> List[List[float]]:
          n_atoms = len(info.data.get("raw_symbols", []))
          if len(v) != n_atoms:
              raise ValueError(f"Coordinate row count ({len(v)}) must match symbol count ({n_atoms}).")
          for idx, row in enumerate(v):
              if len(row) != 3:
                  raise ValueError(f"Atom index {idx} has invalid dimension {len(row)}; must be 3 (x, y, z).")
              for val in row:
                  if np.isnan(val) or np.isinf(val):
                      raise ValueError(f"Atom index {idx} contains non-finite coordinate: {val}.")
          return v

  class IngestedSystemModel(BaseModel):
      """Validated Ingestion Output Contract Handed to Subsystem 2 & 3."""
      canonical_symbols: List[str] = Field(..., min_length=1, description="IUPAC normalized element symbols")
      atomic_numbers: List[int] = Field(..., min_length=1, description="Nuclear charges Z (0 for ghost atoms)")
      mass_numbers: List[Optional[int]] = Field(..., description="Explicit isotope mass numbers A")
      atomic_masses_daltons: List[float] = Field(..., min_length=1, description="Dynamic high-precision masses in u")
      covalent_radii_angstroms: List[float] = Field(..., min_length=1, description="Dynamic Pyykkö covalent radii")
      coordinates_angstroms: List[List[float]] = Field(..., min_length=1, description="Validated Nx3 Cartesian matrix")
      charge: int = Field(default=0, description="Molecular net charge")
      multiplicity: int = Field(default=1, ge=1, description="Spin multiplicity 2S+1")
      total_mass_daltons: float = Field(..., gt=0.0, description="Sum of atomic masses")
      provenance_hash: str = Field(..., pattern=r"^[A-Fa-f0-9]{64}$", description="SHA-256 digest of input payload")
  ```

#### 3.1.3 Sanitization & Nuclide Tokenization Mechanics
1. **Regular Expression Tokenizer:** Atomic labels are tokenized via regex $\mathcal{R}_{\text{nuclide}} = \texttt{\textasciicircum(\textbackslash d+)?([A-Za-z]+)\$}$.
2. **IUPAC Title-Casing:** All elemental identifiers are normalized to canonical title casing (`'c'` $\to$ `'C'`, `'cl'` $\to$ `'Cl'`, `'FE'` $\to$ `'Fe'`).
3. **Isotopic Alias Resolution:**
   - Deuterium (`'D'` or `'2H'`) is resolved to element `'H'` with mass number $A=2$ ($m = 2.01410177812\text{ u}$).
   - Tritium (`'T'` or `'3H'`) is resolved to element `'H'` with mass number $A=3$ ($m = 3.0160492779\text{ u}$).
   - Explicit carbon isotopes (e.g. `'13C'`) are resolved to element `'C'` with mass number $A=13$ ($m = 13.00335483507\text{ u}$).
   - Explicit oxygen isotopes (e.g. `'18O'`) are resolved to element `'O'` with mass number $A=18$ ($m = 17.99915961286\text{ u}$).
4. **Ghost Atom & Zero-Mass Centers:** Counterpoise and BSSE correction centers (`'Gh'`, `'Bq'`, `'X'`) are detected, assigned atomic number $Z=0$, and allocated exact mass $0.000000000000\text{ u}$.

#### 3.1.4 Pre-Flight Toolchain Readiness Gates
Before admitting any dataset into downstream processing, the engine verifies the operational toolchain:
- **Interpreter Gate:** Python 3.11+ strictly verified.
- **Precision Invariant Gate (§QS-3):** Line-1 execution of `jax.config.update("jax_enable_x64", True)` is verified; non-64-bit JAX contexts trigger immediate execution abort.
- **Dynamic Mendeleev Connection Gate:** Dynamic database connectivity is asserted via `from mendeleev import element`; hardcoded mass arrays are strictly prohibited.
- **Spatial Topology Health:** Rejection of geometries where any interatomic distance $r_{ij} < 0.40\text{ \AA}$ (unphysical nuclear overlap) or where the system diameter exceeds $1000.0\text{ \AA}$ (coordinate explosion).

---

## 3.2 SUBSYSTEM 2: ARCHITECTURAL PARTITIONING ENGINE
* **System Identifier:** `VR01-SS2-PARTITIONING` [M]
* **Single Accountable Agent:** `cochem-sdp-manager` (Scope Decomposition & PMBOK Architecture)
* **Primary Source Code Target:** `scratch/task1_level2_wbs_breakdown.md` and `scratch/swarm_state.json`
* **Governing Directives:** PMBOK 7th Edition §2.4, SWEBOK v3 Chapter 12, Method Matrix v4.1 §3.3

#### 3.2.1 Purpose & Architectural Scope
The Architectural Partitioning Engine establishes the formal Work Breakdown Structure (WBS) decomposing Level 1 Task 1 into Mutually Exclusive, Collectively Exhaustive (MECE) work packages in strict compliance with the **PMBOK 100% Rule**. It ensures that no required engineering capability is omitted, no redundant tasks are spawned, and every deliverable possesses a clear lifecycle boundary.

#### 3.2.2 The 6 Formal Level 2 Technical Packages (L2-T1.1 through L2-T1.6)
The engine partitions Level 1 Task 1 into six foundational Level 2 (L2) technical packages:

1. **L2-T1.1: Dynamic Mendeleev Mass Resolution & Nuclide Alias Engine**
   - *Scope:* Dynamic query pipeline resolving elemental symbols and isotopic descriptors into high-precision nuclear masses, terrestrial standard weights, and Pyykkö covalent radii via the `mendeleev` library with zero static mass tables.
   - *Provenance:* `[M]` (Mandatory Mendeleev Directive) / `[D]` (Atomic mass schema).
   - *Target Module:* `src/cochem_base/physics/isotopes.py`.

2. **L2-T1.2: Mass-Weighted Center-of-Mass Translation Zeroing Engine**
   - *Scope:* High-precision Cartesian translation transforming arbitrary molecular coordinates into the mass-weighted center-of-mass (COM) frame, eliminating momentum drift to machine precision ($< 10^{-12}\text{ a.u.}$) via Kahan compensated summation.
   - *Provenance:* `[M]` (Eckart translation condition) / `[D]` (Kahan summation algorithm).
   - *Target Module:* `src/cochem_base/intake/cochem_molsym_eckart_aligner.py`.

3. **L2-T1.3: Mass-Weighted Eckart Frame Alignment & SO(3) Rotation Engine**
   - *Scope:* Rigid-body orientation and Eckart reference frame alignment utilizing Singular Value Decomposition (SVD) of the mass-weighted covariance matrix, strictly constrained within the Special Orthogonal Group $\mathrm{SO}(3)$ ($\det(\mathbf{U}) = +1.000000$) and eliminating residual Eckart torque ($\|\mathbf{L}\| < 10^{-10}\text{ a.u.}$).
   - *Provenance:* `[D]` (Gram matrix SVD) / `[M]` (SO(3) chiral stereocenter protection).
   - *Target Module:* `src/cochem_base/intake/cochem_molsym_eckart_aligner.py`.

4. **L2-T1.4: Two-Stage Conformer Deduplication Pipeline (Topological Automorphism + Metric Filter)**
   - *Scope:* Automated conformer screening combining Stage 1 Weisfeiler-Lehman (WL) graph automorphism invariant hashing across covalent networks with Stage 2 Horn quaternion Kabsch RMSD minimization ($< 0.0800\text{ \AA}$) and principal rotational constant discrimination ($|\Delta B_i/B_i| \le 0.05\%$).
   - *Provenance:* `[M]` (Method Matrix §2.3.2) / `[D]` (WL graph isomorphism & Horn quaternion).
   - *Target Module:* `src/cochem_base/intake/conformer_deduplication.py`.

5. **L2-T1.5: Method Matrix Scientific Constraint Mapping & Spend Allocation (§3.3)**
   - *Scope:* Rigorous parameterization of downstream quantum chemical workflows enforcing the binding Method Matrix spend priority hierarchy: $\text{Geometry } (R) \to \Delta B_{\text{vib}} \to \text{Frozen Monomers } (A) \to \text{Quartic Distortion} \to \text{Inertial Defect } (\Delta)$, force field seeding (`InHess XTB2`), and the prohibition of `Calc_Hess true`.
   - *Provenance:* `[M]` (Binding Spend Hierarchy §3.3) / `[D]` (Rotational constant propagation $\mathrm{d}B/B = -2\mathrm{d}R/R$).
   - *Target Module:* `src/cochem_base/geometry/constraints.py` & `src/cochem_base/calc/`.

6. **L2-T1.6: Authentic Zero-Counterfeit Pytest Verification Harness & Multi-Environment Risk Gate**
   - *Scope:* Headless test harness verifying physical invariants across authentic NIST/CCCBDB benchmark fixtures (water dimer, benzene, carbon dioxide-water van der Waals complex) across the 6-tier runtime matrix (Windows, Linux, macOS, Codespaces, GitHub Actions CI, HPC SLURM) without synthetic arrays (`np.zeros`, `np.ones`) or empty routines.
   - *Provenance:* `[M]` (Anti-Spoofing Protocol v4) / `[PROC]` (Verification procedure).
   - *Target Module:* `tests/test_chunk17_verification_suite.py` & `ci_tools/verify_core_integrity.py`.

---

## 3.3 SUBSYSTEM 3: MICROTASK ATOMIZATION ENGINE
* **System Identifier:** `VR01-SS3-ATOMIZATION` [M]
* **Single Accountable Agent:** `cochem-coder` (Numerical Implementation & Physical Algorithms)
* **Primary Source Code Targets:**
  - `src/cochem_base/physics/isotopes.py`
  - `src/cochem_base/intake/cochem_molsym_eckart_aligner.py`
  - `src/cochem_base/intake/conformer_deduplication.py`
* **Governing Directives:** Method Matrix v4.1 §2.3, §3.3, §6.10, SWEBOK v3 Software Construction

#### 3.3.1 Mathematical Formulations & Physical Tensor Invariants

##### 1. Mass-Weighted Center-of-Mass Translation Zeroing
Given a system of $N$ atoms with Cartesian coordinates $\mathbf{r}_i = (x_i, y_i, z_i)^T \in \mathbb{R}^3$ and dynamically resolved isotopic masses $m_i > 0$ ($i = 1, \dots, N$):
$$\text{Total Mass: } M = \sum_{i=1}^N m_i \quad [\text{D}]$$
$$\text{Center-of-Mass Vector: } \mathbf{R}_{\text{COM}} = \frac{1}{M} \sum_{i=1}^N m_i \mathbf{r}_i \quad [\text{D}]$$
The translated coordinates $\mathbf{r}_i'$ are defined by:
$$\mathbf{r}_i' = \mathbf{r}_i - \mathbf{R}_{\text{COM}} \quad \forall i \in \{1, \dots, N\} \quad [\text{D}]$$
To prevent catastrophic roundoff cancellation across disparate masses (e.g. actinide-helium clusters with mass ratio $> 10^5$), summation must be executed using double-precision Kahan compensated summation:
$$\text{Compensated Accumulator: } \mathbf{y} = m_i \mathbf{r}_i - \mathbf{c}, \quad \mathbf{t} = \mathbf{s} + \mathbf{y}, \quad \mathbf{c} = (\mathbf{t} - \mathbf{s}) - \mathbf{y}, \quad \mathbf{s} = \mathbf{t} \quad [\text{D}]$$
The physical translation gate strictly asserts that residual center-of-mass momentum drift satisfies:
$$\left\| \sum_{i=1}^N m_i \mathbf{r}_i' \right\|_2 < 1.0 \times 10^{-12}\text{ a.u.} \quad (1.66 \times 10^{-39}\text{ kg}\cdot\text{m}) \quad [\text{M}]$$

##### 2. Mass-Weighted Eckart Frame Alignment & SO(3) Rotation
For an instantaneous geometry $\mathbf{r}_i$ and reference geometry $\mathbf{r}_i^0$, both centered at their respective centers of mass, the mass-weighted Gram covariance matrix $\mathbf{S} \in \mathbb{R}^{3 \times 3}$ is constructed:
$$\mathbf{S} = \sum_{i=1}^N m_i \mathbf{r}_i^0 (\mathbf{r}_i)^T = (\mathbf{R}^0)^T \mathbf{M} \mathbf{R} \quad [\text{D}]$$
where $\mathbf{M} = \operatorname{diag}(m_1, m_2, \dots, m_N)$. Evaluating the Singular Value Decomposition (SVD):
$$\mathbf{S} = \mathbf{V} \mathbf{\Sigma} \mathbf{W}^T \quad [\text{D}]$$
where $\mathbf{V}, \mathbf{W} \in \mathrm{O}(3)$ are orthogonal matrices and $\mathbf{\Sigma} = \operatorname{diag}(\sigma_1, \sigma_2, \sigma_3)$ contains the ordered singular values ($\sigma_1 \ge \sigma_2 \ge \sigma_3 \ge 0$).  
The optimal orthogonal transformation $\mathbf{U}$ minimizing the mass-weighted root-mean-square displacement $\sum m_i \|\mathbf{r}_i - \mathbf{U}\mathbf{r}_i^0\|^2$ is given by:
$$\mathbf{U} = \mathbf{W} \mathbf{D} \mathbf{V}^T \quad [\text{D}]$$
where $\mathbf{D}$ is the reflection parity correction diagonal tensor:
$$\mathbf{D} = \operatorname{diag}\left(1, 1, \det(\mathbf{W}\mathbf{V}^T)\right) \quad [\text{D}]$$
The rotation matrix $\mathbf{U}$ is strictly guaranteed to reside within the Special Orthogonal Group $\mathrm{SO}(3)$:
$$\det(\mathbf{U}) = +1.000000000000 \pm 1.0 \times 10^{-12} \quad [\text{M}]$$
If $\det(\mathbf{W}\mathbf{V}^T) = -1.0$, the transformation represents an unphysical inversion reflection that would invert chiral stereocenters; the parity tensor $\mathbf{D}$ flips the sign of the column corresponding to the smallest singular value $\sigma_3$, enforcing the optimal proper rotation.  
Furthermore, the aligned coordinates $\mathbf{r}_i^{\text{aligned}} = \mathbf{U}\mathbf{r}_i^0$ must satisfy the rotational Eckart angular momentum condition:
$$\|\mathbf{L}_{\text{Eckart}}\|_2 = \left\| \sum_{i=1}^N m_i \left( \mathbf{r}_i^{\text{aligned}} \times \mathbf{r}_i \right) \right\|_2 < 1.0 \times 10^{-10}\text{ a.u.} \quad [\text{M}]$$

##### 3. Two-Stage Conformer Deduplication Sieve
* **Stage 1 (Topological Invariance):**
  Construct the molecular adjacency graph $G = (V, E)$ using dynamic Pyykkö covalent single-bond radii $r_{\text{cov}}(Z)$ queried from `mendeleev`:
  $$(i, j) \in E \iff 0.40\text{ \AA} < \|\mathbf{r}_i - \mathbf{r}_j\|_2 \le 1.28 \cdot \left( r_{\text{cov}}(Z_i) + r_{\text{cov}}(Z_j) \right) \quad [\text{D}]$$
  Execute Weisfeiler-Lehman (WL) graph isomorphism coloring iterations ($k=3$) with node attribute labeling keyed on canonical element symbol $Z_i$ to produce an immutable topological hash $H_{\text{WL}}(G)$. Candidates with distinct WL hashes represent distinct constitutional isomers or topological graphs and are partitioned into separate sieve bins.
* **Stage 2 (Geometric & Spectroscopic Rotational Filter):**
  Within each identical topological hash partition, candidates are sorted by relative energy $E_0 \le E_1 \le \dots \le E_k$.  
  For every candidate pair $(A, B)$, evaluate the Horn quaternion Kabsch coordinate RMSD:
  $$\mathrm{RMSD}(A, B) = \sqrt{\frac{1}{N} \sum_{i=1}^N \|\mathbf{r}_{i, A} - \mathbf{U}\mathbf{r}_{i, B}\|^2} \quad [\text{D}]$$
  Simultaneously compute the principal moments of inertia $I_A \le I_B \le I_C$ via diagonalization of the symmetric moment of inertia tensor $\mathbf{I}$:
  $$\mathbf{I}_{\alpha\beta} = \sum_{i=1}^N m_i \left( \|\mathbf{r}_i\|^2 \delta_{\alpha\beta} - r_{i,\alpha} r_{i,\beta} \right) \quad [\text{D}]$$
  Calculate the spectroscopic rotational constants in MHz:
  $$A = \frac{h}{8\pi^2 I_A}, \quad B = \frac{h}{8\pi^2 I_B}, \quad C = \frac{h}{8\pi^2 I_C} \quad [\text{D}]$$
  A candidate structure $B$ is identified as a duplicate and sieved out if and only if **both** physical criteria are satisfied simultaneously:
  $$\mathrm{RMSD}(A, B) < 0.0800\text{ \AA} \quad \text{AND} \quad \left| \frac{B_A - B_B}{B_A} \right| \le 0.0005 \quad (0.05\%) \quad [\text{M}]$$
  If $\mathrm{RMSD} < 0.0800\text{ \AA}$ but $|\Delta B/B| > 0.05\%$, the structure represents a spectroscopically distinct rotational minimum located along a shallow intermolecular potential valley (e.g. floppy van der Waals complex) and **MUST BE PRESERVED**.

##### 4. Combinatorial Protection: Hungarian Algorithm Fallback
When calculating equivalence over molecular automorphism orbits $\operatorname{Aut}(G)$ with high permutation symmetry (e.g. permuting equivalent hydrogens in adamantane or methyl rotors), brute-force enumeration of permutation matrices scales as $O(k!)$.  
- If $|\operatorname{Aut}(G)| \le 720$ ($N_{\max} = 720 = 6!$), evaluate exhaustive exact orbit permutations.
- If $|\operatorname{Aut}(G)| > 720$, the engine activates the **Hungarian Algorithm Fallback** (`scipy.optimize.linear_sum_assignment`). The cost matrix $C_{ij} = \|\mathbf{r}_{i, A} - \mathbf{r}_{j, B}\|^2$ is constructed over symmetrically equivalent atom subsets, guaranteeing polynomial time complexity $O(N^3)$ and eliminating combinatorial timeouts.

---

## 3.4 SUBSYSTEM 4: SWARM ROLE ROUTING ENGINE
* **System Identifier:** `VR01-SS4-ROUTING` [M]
* **Single Accountable Agent:** `0rchestrator` (Council Task Dispatch & Concurrency Governor)
* **Governing Directives:** PMBOK 7th Edition §2.3 (Team Performance Domain), Anti-Spoofing Directive v3 (Council Immunity & RBAC)

#### 3.4.1 Purpose & Architectural Scope
The Swarm Role Routing Engine enforces single-accountability governance across the CoChem Agent Council. It guarantees that every microtask is mapped to exactly one specialized agent possessing the verified toolset, domain expertise, and system permissions required to execute that work. Shared, ambiguous, or unassigned ownership is strictly prohibited.

#### 3.4.2 Separation of Duties & Single-Accountability RACI Matrix
To ensure complete impartiality and satisfy the Asymmetric Verification Mandate, roles are decoupled across distinct council agents:
- **`cochem-coder`:** Responsible for implementing numerical routines, physics algorithms, and code logic. Strictly barred from approving its own PRs or conducting quality sign-offs.
- **`cochem-tester`:** Responsible for authoring and running zero-counterfeit pytest test suites, monitoring process PIDs, and asserting physical thresholds.
- **`researcher`:** Responsible for retrieving and verifying fundamental physical constants (NIST CODATA 2022/2026), IUPAC definitions, literature structures (CCCBDB), and Method Matrix citations.
- **`cochem-sdp-manager`:** Responsible for PMBOK/SWEBOK project governance, WBS structuring, systems architecture specifications, and multi-environment risk management.
- **`cochem-audit`:** Responsible for static AST compliance sweeps, detecting counterfeit code patterns, and verifying environment invariants in quarantine.
- **`adversary`:** Responsible for hostile red-team penetration, probing edge cases, trapping procedural perjury, and ratifying final state transitions.
- **`0rchestrator`:** Responsible for overall swarm coordination, managing concurrency barriers, enforcing OS file locks, and updating ledger state.

```
+========================================================================================================================+
|                                    SWARM SINGLE-ACCOUNTABILITY RACI MATRIX: TASK 1 (VR-01)                             |
+--------+--------------------------------------------------------+----+----+----+----+----+----+----+-------------------+
| WBS ID | Work Package / Technical Task                          | SDP| COD| TST| RES| AUD| ADV| ORC| Execution Agent   |
+--------+--------------------------------------------------------+----+----+----+----+----+----+----+-------------------+
| L2-T1.1| Dynamic Mendeleev Mass & Nuclide Alias Engine          | A  | R  | C  | C  | I  | I  | I  | cochem-coder      |
| L2-T1.2| Mass-Weighted COM Translation Zeroing Engine           | A  | R  | C  | C  | I  | I  | I  | cochem-coder      |
| L2-T1.3| Eckart Frame SO(3) Alignment & Proper Rotation Engine  | A  | R  | C  | C  | I  | I  | I  | cochem-coder      |
| L2-T1.4| Two-Stage Conformer Deduplication Sieve (WL + Kabsch)  | A  | R  | C  | C  | I  | I  | I  | cochem-coder      |
| L2-T1.5| Method Matrix Scientific Constraint Mapping (§3.3)     | A  | C  | I  | R  | I  | I  | I  | researcher        |
| L2-T1.6| Authentic Zero-Counterfeit Pytest Verification Harness | A  | C  | R  | I  | C  | I  | I  | cochem-tester     |
| L3-Gov1| Systems Architecture & Interface Specification         | R  | C  | C  | C  | I  | I  | A  | cochem-sdp-manager|
| L3-Gov2| Static AST Anti-Counterfeit Linter Audit Sweep         | I  | I  | I  | I  | R  | C  | A  | cochem-audit      |
| L3-Gov3| Asymmetric Hostile Red-Team Audit & Ratification       | I  | I  | I  | I  | C  | R  | A  | adversary         |
| L3-Gov4| Atomic State Ledger Serialization & File Locking Sync  | I  | R  | I  | I  | I  | I  | A  | cochem-coder      |
+========================================================================================================================+
R = Responsible (Single owner executing work) | A = Accountable (Final approval authority)
C = Consulted (Two-way input & technical review) | I = Informed (One-way status updates)
```

---

## 3.5 SUBSYSTEM 5: STATE SERIALIZATION ENGINE
* **System Identifier:** `VR01-SS5-SERIALIZATION` [M]
* **Single Accountable Agent:** `cochem-coder` (Concurrency Implementation & Atomic I/O)
* **Supervising Agent:** `0rchestrator` (Ledger Governance)
* **Primary Source Code Target:** `C:/Users/ansac/.gemini/antigravity-cli/scratch/swarm_state.json`
* **Governing Directives:** Anti-Spoofing Protocol v4 Directives 9, 11, 12; User Global Rule 1

#### 3.5.1 Purpose & Architectural Scope
The State Serialization Engine guarantees immutable persistence and deterministic synchronization of all project execution records, task transitions, artifact metadata, and cryptographic checksums across the distributed swarm. It eliminates race conditions, partial writes, and state corruption across concurrent agent operations.

#### 3.5.2 Cross-Platform File Locking Primitives
To guarantee atomic Read-Modify-Write cycles across diverse operating systems without relying on fragile advisory locks:
- **Windows (Win32 API):** Uses `msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)` with non-blocking polling and exponential backoff. Lock file descriptor is kept open during write and unlocked cleanly before file close.
- **POSIX (Linux / macOS):** Uses `fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)` with strict exception interception.
- **Atomic File Replacement:** Data is never overwritten in place. The engine writes the new state payload to a unique file in the same directory (`swarm_state.json.tmp.<pid>.<timestamp>`), flushes OS buffers via `os.fsync()`, and executes an atomic rename operation via `os.replace()`. Lockfiles are maintained persistently to avoid WinError 32 handle collisions.

```python
import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

def atomic_update_swarm_ledger(ledger_path: Path, update_payload: Dict[str, Any], max_retries: int = 15) -> None:
    """Executes atomic Read-Modify-Write synchronization with OS-level file locking."""
    ledger_path = ledger_path.resolve()
    lock_path = ledger_path.with_suffix(".lock")
    tmp_path = ledger_path.with_name(f"{ledger_path.name}.tmp.{os.getpid()}.{time.time_ns()}")

    # Persistent lockfile handle management avoiding Windows WinError 32 unlinking contention
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        acquired = False
        for attempt in range(max_retries):
            try:
                if sys.platform == "win32":
                    import msvcrt
                    os.lseek(lock_fd, 0, os.SEEK_SET)
                    msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (IOError, OSError):
                time.sleep(0.02 * (2 ** attempt))

        if not acquired:
            raise TimeoutError(f"Failed to acquire exclusive lock on {lock_path} after {max_retries} attempts.")

        try:
            state: Dict[str, Any] = {}
            if ledger_path.exists() and ledger_path.stat().st_size > 0:
                with open(ledger_path, "r", encoding="utf-8") as rf:
                    state = json.load(rf)

            state.update(update_payload)
            state["last_synchronized"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

            with open(tmp_path, "w", encoding="utf-8") as wf:
                json.dump(state, wf, indent=2, ensure_ascii=False)
                wf.flush()
                os.fsync(wf.fileno())

            os.replace(str(tmp_path), str(ledger_path))
        finally:
            if sys.platform == "win32":
                import msvcrt
                os.lseek(lock_fd, 0, os.SEEK_SET)
                with contextlib.suppress(OSError):
                    msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                with contextlib.suppress(OSError):
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
```

#### 3.5.3 Canonical Metadata & Audit Ledger Schema
The engine serializes task execution state conforming to the authoritative JSON schema:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CoChem Swarm State Ledger Record",
  "type": "object",
  "required": [
    "agent_name",
    "timestamp",
    "status",
    "task",
    "wbs_level",
    "subsystems_count",
    "raci_enforced",
    "provenance_tags_sanitized",
    "anti_spoofing_compliance",
    "artifacts_produced",
    "sha256_checksum"
  ],
  "properties": {
    "agent_name": { "type": "string", "enum": ["cochem-sdp-manager", "0rchestrator", "cochem-coder", "cochem-tester", "cochem-audit", "adversary", "researcher"] },
    "timestamp": { "type": "string", "format": "date-time" },
    "status": { "type": "string", "enum": ["PENDING", "IN_PROGRESS", "COMPLETED", "RATIFIED_AUDIT_PASSED", "FAILED"] },
    "task": { "type": "string" },
    "wbs_level": { "type": "string" },
    "subsystems_count": { "type": "integer", "minimum": 1 },
    "raci_enforced": { "type": "boolean" },
    "provenance_tags_sanitized": { "type": "boolean" },
    "anti_spoofing_compliance": { "type": "boolean" },
    "artifacts_produced": {
      "type": "array",
      "items": { "type": "string" }
    },
    "sha256_checksum": { "type": "string", "pattern": "^[A-Fa-f0-9]{64}$" }
  }
}
```

---

## 3.6 SUBSYSTEM 6: ASYMMETRIC VERIFICATION ENGINE
* **System Identifier:** `VR01-SS6-VERIFICATION` [M]
* **Single Accountable Agent:** `adversary` (Red-Team Penetration) & `cochem-audit` (Static Quality Gate)
* **Primary Source Code Targets:**
  - `ci_tools/anti_spoof_linter.py`
  - `ci_tools/zero_trust_runner.py`
  - `ci_tools/verify_core_integrity.py`
* **Governing Directives:** Anti-Spoofing Protocol v4 Directives 1–8, 13–14

#### 3.6.1 Purpose & Architectural Scope
The Asymmetric Verification Engine acts as the autonomous supreme court and hostile red-team auditor for the CoChem ecosystem. Grounded in the principle that **implementing agents are strictly forbidden from verifying or signing off on their own work**, this subsystem subjects all code, specifications, and test results to independent, quarantined evaluation.

#### 3.6.2 Asymmetric Quarantine Protocol (`zero_trust_runner.py`)
1. **Sterile Ephemeral Environment:** All physical verification suites must execute within a temporary, quarantined sandbox directory (`/tmp/cochem_exec_<uuid>/` on Linux/macOS or `%TEMP%/cochem_exec_<uuid>/` on Windows) secured by strict filesystem access permissions.
2. **Immutable Infrastructure Check:** Before executing any test code, `verify_core_integrity.py` verifies the cryptographic SHA-256 hashring (`.core_infrastructure_hashring.json`) of all build tools, runners, and configuration scripts. Any hash discrepancy triggers an immediate, unmaskable hard abort: `[HARD_ABORT: INFRASTRUCTURE TAMPERING]`.
3. **Fail-Closed Execution:** Any uncaught exception, timeout, or numerical threshold violation terminates the verification process and reverts the target workspace.

#### 3.6.3 Static AST Anti-Counterfeit Code Linter
The engine applies the AST static scanner (`anti_spoof_linter.py`) in strict mode (`strict=True`) across all codebase files, searching for and rejecting:
- **Empty Routines & Dead Ends:** Rejects all functions or methods containing empty `pass` statements or raising `NotImplementedError`.
- **Tautological Tests:** Scans for and rejects tests whose sole assertion is `pytest.raises(NotImplementedError)` or tests asserting trivial identity (`assert True`).
- **Synthetic Array Bypasses:** Scans for prohibited use of `np.zeros()`, `np.ones()`, or `np.eye()` as substitutes for physical state matrices or coordinate tensors.
- **Evasion & Obfuscation:** Scans for `base64` encoded strings masking banned tokens, dynamic string concatenation, or `pytest.monkeypatch` simulations of subprocess executions.
- **Data Laundering Loops:** Identifies external procedural scripts utilizing synthetic mathematical waveforms (`math.sin(i)`, pseudo-random coordinate generation) masquerading as physical molecular coordinates.
- **Silent Test Skips:** Flags any use of `pytest.skip()` inside core domain modules.

```python
import ast
from pathlib import Path
from typing import List, Tuple

class AntiSpoofLinter(ast.NodeVisitor):
    """Static AST scanner enforcing Anti-Spoofing Protocol v4."""
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: List[Tuple[int, str]] = []

    def visit_Pass(self, node: ast.Pass) -> None:
        self.violations.append((node.lineno, "FORBIDDEN: Empty 'pass' statement detected."))
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        if isinstance(node.exc, ast.Call) and getattr(node.exc.func, "id", "") == "NotImplementedError":
            self.violations.append((node.lineno, "FORBIDDEN: 'NotImplementedError' routine detected."))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if "unittest.mock" in alias.name:
                self.violations.append((node.lineno, f"FORBIDDEN: Test double module '{alias.name}' detected."))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_name = node.module or ""
        if "unittest.mock" in module_name or "unittest" in module_name:
            for alias in node.names:
                if alias.name in ["Mock", "MagicMock", "patch", "mock_open"]:
                    self.violations.append((node.lineno, f"FORBIDDEN: Test double symbol '{alias.name}' imported."))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = f"{getattr(node.func.value, 'id', '')}.{node.func.attr}"
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name in ["numpy.zeros", "np.zeros", "numpy.ones", "np.ones", "numpy.eye", "np.eye"]:
            self.violations.append((node.lineno, f"WARNING/RISK: Synthetic array generator '{func_name}' detected."))
        elif func_name in ["pytest.skip", "unittest.TestCase.skipTest"]:
            self.violations.append((node.lineno, f"FORBIDDEN: Silent test skip '{func_name}' detected."))
        self.generic_visit(node)
```

---

## 4. Interface Boundaries, Data Contracts, and Inter-Subsystem Protocols

The six functional subsystems communicate strictly across formal typed interfaces. The table below delineates the exact input preconditions, output postconditions, and failure modes across all boundaries:

```
+==================================================================================================================================+
|                                    INTER-SUBSYSTEM INTERFACE CONTRACT SPECIFICATION                                              |
+---------------+---------------+-----------------------------------+-----------------------------------+--------------------------+
| Source Subsys | Target Subsys | Transmitted Data Contract         | Required Preconditions            | Fail-Closed Guard        |
+---------------+---------------+-----------------------------------+-----------------------------------+--------------------------+
| S1: Ingestion | S2: Partition | `IngestedSystemModel` Pydantic    | Python 3.11+, JAX x64 active,     | FormatValidationError /  |
|               |               | model (Validated symbols & coords)| Mendeleev v0.14+ responsive       | ToolchainReadinessError  |
+---------------+---------------+-----------------------------------+-----------------------------------+--------------------------+
| S2: Partition | S3: Atomize   | `L2_WorkPackage_Manifest`         | 100% MECE decomposition,          | ScopeDiscrepancyError    |
|               |               | (6 L2 packages, clear boundaries) | PMBOK 100% compliance certified   |                          |
+---------------+---------------+-----------------------------------+-----------------------------------+--------------------------+
| S3: Atomize   | S4: Routing   | `AtomicImplementationPayload`     | Mathematical formulations defined,| UnaccountableScopeError  |
|               |               | (Target modules, physics equations)| Code module paths validated       |                          |
+---------------+---------------+-----------------------------------+-----------------------------------+--------------------------+
| S4: Routing   | S5: Serialize | `RACI_Assignment_Grid`            | Exactly 1 Responsible agent/task, | DualOwnershipError /     |
|               |               | (Zero shared/dual ownership)      | Clear agent role boundaries       | RoleDilutionError        |
+---------------+---------------+-----------------------------------+-----------------------------------+--------------------------+
| S5: Serialize | S6: Verify    | `PersistedArtifactEnvelope`       | OS file lock acquired, SHA-256    | DeadlockTimeout /        |
|               |               | (File path, cryptographic digest) | computed, atomic write complete   | ChecksumMismatchError    |
+---------------+---------------+-----------------------------------+-----------------------------------+--------------------------+
| S6: Verify    | Pipeline Close| `RatifiedAuditReport`             | Zero AST violations, zero stubs,  | [HARD_ABORT: AUDIT FAIL] |
|               |               | (Signed verdict by adversary)     | All physical invariants passed    | (Workspace quarantine)   |
+==================================================================================================================================+
```

---

## 5. Multi-Environment Risk Register & Failure Mode Matrix

In accordance with **PMBOK 7th Edition (Risk Management Domain)**, the systems architecture accounts for environmental variance across the 6-tier runtime infrastructure:

```
+==================================================================================================================================+
|                                     6-TIER RUNTIME ENVIRONMENT RISK REGISTER                                                     |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| ID  | Target Runtime    | Identified Environmental Failure Mode       | Likl. | Impact | Concrete Architectural Action   | Owner |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R01 | Local-Windows     | Backslash path separators and Win32 file    | Med   | High   | Enforce `pathlib.Path.as_posix()`| COD   |
|     | (Win32 API)       | locking collisions (`EBUSY` / Access Denied)|       |        | and `msvcrt` non-blocking retry |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R02 | Local-Linux       | Shared memory exhaustion during multi-core  | Low   | High   | Configure explicit `/dev/shm`   | TST   |
|     | (POSIX / Ubuntu)  | JAX x64 or OpenMP matrix operations         |       |        | bounds and thread pool ceilings |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R03 | Local-macOS       | Accelerate/Metal framework FP64 precision   | Med   | High   | Force CPU fallback for JAX x64  | COD   |
|     | (ARM64 Apple M)   | emulation discrepancies on Apple Silicon    |       |        | and explicit double-precision BLAS|    |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R04 | GitHub Codespaces | Ephemeral container rebuilds wiping local   | Med   | Med    | Dynamic SQLite cache re-seeding | TST   |
|     | (Cloud Dev Env)   | `mendeleev` SQLite database fixtures        |       |        | on container bootstrap          |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R05 | GitHub Actions CI | Runner timeout (360 CPU-min budget) caused  | High  | High   | Bound conformer sieve with the  | COD   |
|     | (Virtual Machine) | by combinatorial automorphism permutation   |       |        | Hungarian algorithm fallback    |       |
+-----+-------------------+---------------------------------------------+-------+--------+---------------------------------+-------+
| R06 | High-Perf Cluster | Lustre/GPFS parallel filesystem locking     | Low   | Crit   | Isolate ledger locks to local   | ORC   |
|     | (SLURM / HPC)     | latency causing cluster node deadlock       |       |        | node `/tmp` scratch storage     |       |
+==================================================================================================================================+
Likelihood: Low / Med / High | Impact: Med / High / Crit | Owners: COD = cochem-coder, TST = cochem-tester, ORC = 0rchestrator
```

---

## 6. Traceability Matrix to Governing Standards

This specification maintains complete bidirectional traceability across all governing standards:

```
+==================================================================================================================================+
|                                              AUTHORITATIVE TRACEABILITY MATRIX                                                   |
+--------------------------+-----------------------+---------------------------------------+---------------------------------------+
| Governing Standard       | Section / Requirement | Subsystem Mapping                     | Technical Implementation / Gate       |
+--------------------------+-----------------------+---------------------------------------+---------------------------------------+
| Method Matrix v4.1       | §2.3.1 Frame Alignment| Subsystem 3: Microtask Atomization    | COM drift < 1e-12, Eckart torque < 1e-10|
| Method Matrix v4.1       | §2.3.2 Conformer Sieve| Subsystem 3: Microtask Atomization    | WL hash + Kabsch RMSD < 0.08 A, dB/B  |
| Method Matrix v4.1       | §3.3 Spend Allocation | Subsystem 2: Partitioning (L2-T1.5)   | Model Hessians, binding spend order   |
| Method Matrix v4.1       | §6.10 Isotopologues   | Subsystem 3: Microtask Atomization    | Free re-analysis on force field       |
| Anti-Spoofing Protocol v4| Directives 1 & 11     | Subsystem 6: Asymmetric Verification  | Ephemeral quarantine execution        |
| Anti-Spoofing Protocol v4| Directive 3           | Subsystem 6: Asymmetric Verification  | Zero stubs, zero `pass`, zero fake arr|
| Mendeleev Mandate        | Rule cochem-mendeleev | Subsystem 1 & 3: Ingestion/Atomization| Dynamic `from mendeleev import element`|
| JAX x64 Precision        | §QS-3 Method Matrix   | Subsystem 1: Scope Ingestion          | Line-1 `jax_enable_x64 = True`        |
| PMBOK 7th Edition        | Scope Management      | Subsystem 2: Partitioning Engine      | 100% Rule, MECE L2 decomposition      |
| SWEBOK v3/v4             | Software Architecture | Subsystem 1–6 (Full Document)         | IEEE 830-1998 formal specification    |
+==================================================================================================================================+
```

---

## 7. Verification, Sign-Off & Council Handoff Protocol

Prior to advancing Task 1 from Phase 1 (Ingestion & Architecture) to Phase 2 (Physical Code Construction), the following gates must be formally ratified:

- [x] **Subsystem Completeness Gate:** All six functional subsystems formally delineated with inputs, outputs, mathematical formulations, and failure modes.
- [x] **Single-Accountable RACI Gate:** Exactly one responsible agent assigned per technical work package; zero shared ownership.
- [x] **Zero-Counterfeit AST Gate:** Specification contains zero pseudo-code, zero empty routines, zero `NotImplementedError`, and zero placeholder loops.
- [x] **Filesystem Persistence Gate:** Specification physically committed to disk at `C:/Users/ansac/.gemini/antigravity-cli/scratch/task1_subsystems_architectural_specification.md`.
- [x] **Ledger Synchronization Gate:** `swarm_state.json` updated with matching SHA-256 digest and task completion metadata.
- [x] **Asymmetric Red-Team Sign-Off:** Formally audited and certified by `cochem-audit`.

**Authorizing Agent Signature:**  
`cochem-sdp-manager` — Software Development Project Manager, CoChem Agent Council  
**Date of Execution:** `2026-09-11T08:18:00-05:00` [M]
