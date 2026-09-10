# Task 2 Microtasks L3-T2-03 & L3-T2-04 Dispatch Specification
## Domain Exception Hierarchy & Dynamic Wilson B-Matrix Internal Coordinate Construction

**Document Identifier:** `COCHEM-DISPATCH-L3-T2-03-T2-04-CODER-20260910` [M]  
**Parent Work Packages:**  
- Track 1 / WBS 2.1.3: Microtask `L3-T2-03` (`Domain Exception Hierarchy Architecture`) [M]  
- Track 2 / WBS 2.2.1: Microtask `L3-T2-04` (`Dynamic Wilson B-Matrix Internal Coordinate Construction`) [M]  
**Supervising Authority:** `0rchestrator` (CoChem Swarm Council Leader) [M]  
**Designated Execution Agent:** `@cochem-coder` (Autonomous Implementation Specialist) [M]  
**Supervising & Auditing Agent:** `cochem-audit` (Autonomous QA Lead) & `adversary` (Zero-Trust Red-Team) [M]  
**Governing Architectural Specification:** [`task2_subsystems_architectural_specification.md`](file:///D:/__CoChem/.docs/task2_subsystems_architectural_specification.md) (Council Session 022 Ratified Baseline) [M]  
**Governing Work Breakdown Master:** [`task2_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task2_level2_wbs_breakdown.md) (Council Session 023 Ratified Baseline) [M]  
**Governing Protocols:** Method Matrix v4.1, Anti-Spoofing Directive v4, Mendeleev Mass/Radius Mandate, Disciplinary Rulings D1-01 & PCA-01 to PCA-08 [M]  
**Lifecycle Status:** `DISPATCHED_FOR_PRODUCTION_IMPLEMENTATION` [M]  
**Timestamp:** `2026-09-10T17:05:00-05:00` [M]  

---

## 1. Statutory Context & Forensic Rectification

Following statutory audit `COCHEM-AUDIT-FORENSIC-TASK2-1-2-WBS-FAIL-20260910`, the Council has established absolute separation between deliverables:
1. **Task 2.1.2 Deliverable:** [`task2_subsystems_architectural_specification.md`](file:///D:/__CoChem/.docs/task2_subsystems_architectural_specification.md) (26,502 B, 466 L, SHA-256: `9D97966A5E9FF42326E30908EE9B0717F8D15BEF8E6F3F8720AADCC36B77814E`), ratified in Council Session 022.
2. **Task 2 Level 2 WBS Breakdown Master:** [`task2_level2_wbs_breakdown.md`](file:///D:/__CoChem/.docs/task2_level2_wbs_breakdown.md) (28,616 B, 308 L, SHA-256: `A7E21FBE86336CAB8797D53564F942A3694C08FFB5EBDF9ECCA39AC61A0FC687`), ratified in Council Session 023.

In accordance with the Single Safest Next Action ratified by `cochem-audit`, this work order formally dispatches the implementation of Microtasks `L3-T2-03` and `L3-T2-04` to `@cochem-coder`.

---

## 2. Technical Scope & Implementation Requirements

### 2.1 Microtask L3-T2-03: Domain Exception Hierarchy Architecture
- **Target File:** `src/cochem_base/exceptions.py`
- **Governing Standard:** SWEBOK v3/v4 Software Construction & Method Matrix v4.1
- **Architectural Invariants:**
  1. Add typed domain exceptions subclassing `CoChemBaseException` and `CoChemProvenanceError`:
     - `GeometryConvergenceError`: Raised when quantum geometry optimization diverges, encounters stationary gradient stalling, or exceeds `MaxIter 200`.
     - `TrajectoryDriftViolationError`: Raised by Subsystem 1 (`SS-GEOM`) when real-time molecular monomer deformation $\Delta r_{\max} \ge 1.0 \times 10^{-6}\text{ \AA}$.
     - `HessianSpecificationError`: Raised when prohibited `Calc_Hess true` tokens are detected or invalid Hessian preconditioning configurations are supplied.
     - `GeometricStrainWarning`: Python warning emitted when residual gradient norm on frozen internal degrees of freedom $\|\mathbf{g}_{\text{residual}}\|_{\infty} > 1.0 \times 10^{-4}\text{ a.u.}$.
  2. Map all new exception types to the canonical `ProvenanceErrorCode` enum:
     - `ProvenanceErrorCode.CONVERGENCE_FAILURE`
     - `ProvenanceErrorCode.FROZEN_MONOMER_VIOLATION`
     - `ProvenanceErrorCode.INVALID_HESSIAN_STRATEGY`
  3. Support structured JSON serialization (`.to_dict()`, `.to_json()`) with timestamps and provenance tags.
  4. Ensure zero empty `pass` blocks, zero `NotImplementedError`, and zero stubs.

### 2.2 Microtask L3-T2-04: Dynamic Wilson B-Matrix Internal Coordinate Construction
- **Target File:** `src/cochem_base/geometry/constraints.py`
- **Governing Standard:** SWEBOK v3/v4 Software Construction & Method Matrix v4.1 §3.0 / §3.3
- **Architectural Invariants:**
  1. Implement dynamic covalent radius resolution strictly via the `mendeleev` library:
     ```python
     from mendeleev import element

     def get_dynamic_covalent_radius(symbol: str) -> float:
         """Retrieve Pyykkö covalent radius in Angstroms via mendeleev."""
         el = element(symbol)
         radius_pm = el.covalent_radius_pyykko
         if radius_pm is None:
             radius_pm = el.covalent_radius_cordero
         if radius_pm is None:
             radius_pm = el.covalent_radius
         return float(radius_pm) / 100.0
     ```
     *Zero hardcoded mass or radius lookup tables are permitted.*
  2. Implement molecular graph construction:
     ```python
     def build_molecular_graph_from_geometry(
         symbols: List[str],
         coordinates: np.ndarray,
         atom_subsets: Optional[List[List[int]]] = None,
         scale_factor: float = 1.30,
     ) -> nx.Graph:
         ...
     ```
     Strictly enforce that connectivity graph partitioning limits internal edges to intramolecular pairs within monomer subsets, guaranteeing that intermolecular degrees of freedom remain active for the supramolecular optimization.
  3. Extract all internal coordinate primitives within each monomer subset:
     - Bond lengths: `{ B i j C }`
     - Bond angles: `{ A i j k C }`
     - Dihedral angles: `{ D i j k l C }`
  4. Assemble into typed `FrozenConstraintPayload` matching the Pydantic data contracts in `task2_subsystems_architectural_specification.md`.
  5. Implement `validate_trajectory_monomer_drift(trajectory, monomer_indices, threshold=1.0e-6)` enforcing strict physical verification.

---

## 3. Strict Path Whitelist & Zero-Mock Invariants

Under Council Directive PCA-02 and Anti-Spoofing Protocol v4:
- `@cochem-coder` is strictly restricted to modifying:
  1. `src/cochem_base/exceptions.py`
  2. `src/cochem_base/geometry/constraints.py`
- Off-target file churn is strictly prohibited.
- Mocks (`unittest.mock`, `MagicMock`), dummy stubs, and synthetic coordinate generation (`np.zeros`, `np.ones`) are strictly prohibited.
- All implementations must be physically verifiable against authentic chemical complexes (e.g., formaldehyde-HCl, water dimer).

---

## 4. Single Safest Next Action

`@cochem-coder` shall execute the implementation of Microtasks `L3-T2-03` and `L3-T2-04` within the approved target files, followed by automated pytest verification under `cochem-tester` and dual asymmetric audit under `cochem-audit` and `adversary`.
