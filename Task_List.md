# CoChem-GEOM Work Breakdown Structure (WBS) & Task List

**Project Target**: Task 06: Quantum-Mechanical Structural Relaxation & Validation Oracle (`src/cochem_geom/eval/qm_oracle.py`)  
**Specification References**:  
- `Task_06_eval_qm_oracle_py.md` (CoChem-GEOM SRS Task 6 Prompt)
- `SRS Document 8 Evaluation Metrics & Alignment.txt`
- [`Method_Matrix.md`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/Method_Matrix.md) (Method Matrix v4: ORCA/CREST GOAT, defgrid1->defgrid3, TolMaxG 1e-5, InHess XTB2/Lindh, Spin Contamination <S^2> < 10%)
- Mendeleev Library Mandate (Dynamic mass & property resolution via `mendeleev`)
**Target Code Artifact**: [`src/cochem_geom/eval/qm_oracle.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-GEOM/src/cochem_geom/eval/qm_oracle.py)  
**Target Test Artifact**: [`tests/test_qm_oracle.py`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/test_qm_oracle.py)  
**Configuration & Registry**: [`pytest.ini`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/pytest.ini), [`swarm_state.json`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/swarm_state.json)  
**Governance Framework**: PMBOK Guide 7th Edition & SWEBOK v3 (Software Construction, Testing, SCM)  
**Core Mandates**: Strict Zero-Mock Mandate, Dynamic Mendeleev Mass Resolution, Geometric Equivariance/Invariance Separation, State Immutability, Dynamic Path Resolution, Explicit Provenance Tags (`[M]`, `[D]`, `[E]`).

---

## 1. PROJECT CHARTER & ARCHITECTURAL BASELINE

### 1.1 Executive Summary & Strategic Objective
The `qm_oracle.py` module delivers a physical validation and relaxation oracle for geometric deep learning predictions in CoChem-GEOM. Neural networks predicting 3D molecular conformations can output unphysical atomic clashes or distorted valencies that evade naive geometric loss metrics. `qm_oracle.py` provides high-performance, robust, and physically grounded interfaces to the Atomic Simulation Environment (ASE), semi-empirical quantum engines (xTB / GFN2-xTB, GFN-FF), and density functional / wave-function theory engines (ORCA, PySCF, CREST).

### 1.2 Core Architectural Requirements & Scope Inclusions

#### A. ASE & xTB Relaxation Engine
1. **Dynamic ASE Integration**: Construct `ase.Atoms` dynamically using masses retrieved from `mendeleev`.
2. **xTB Optimization**: Wrap `xtb.ase.calculator.XTB` with GFN2-xTB, GFN1-xTB, and GFN-FF parameters.
3. **Adaptive Convergence**: Implement multi-stage optimization (LBFGS, FIRE, BFGS) with force threshold `fmax=0.05` eV/Å `[E]` and step ceilings to trap runaway coordinate explosions.
4. **Fallback & Robustness**: Resilient exception handling with graceful diagnostics if external quantum binaries or calculators are unavailable.

#### B. Method Matrix v4 Compliance
1. **Integration Grid Escalation**: Define grid profiles escalating from loose (`defgrid1`) to tightened (`defgrid3`) near stationary points.
2. **Tight Gradient Convergence**: Enforce `TolMaxG 1e-5 [E]` for weakly bound non-covalent complexes.
3. **Hessian Preconditioning**: Enforce model Hessian preconditioning (`InHess XTB2` or `Lindh`) and forbid `Calc_Hess true`.
4. **Spin Contamination Verification**: Implement `<S^2>` deviation check for open-shell systems:
   $$\text{Deviation} = \frac{|\langle S^2 \rangle_{\text{calc}} - S(S+1)|}{S(S+1)} \times 100\%$$
   Halt or flag if deviation exceeds $10\%$ `[E]`.
5. **Frozen-Monomer Protocol**: Support coordinate masking to freeze monomer internal degrees of freedom while relaxing intermolecular separation $R$.

#### C. Geometric Invariance & State Immutability
1. **Separation of Concerns**: Strictly preserve separation between non-spatial invariant node features and spatial coordinates.
2. **Immutable Operations**: Ensure all coordinate updates and transformations return fresh tensors/arrays (`pos = pos + update`).

#### D. Dynamic Path & Resource Management
1. **Dynamic Lookups**: Resolve all scratch and configuration paths via `pathlib.Path.home()` and environment variables (`COCHEM_SCRATCH_DIR`, `TEMP`, `TMP`).
2. **Zero Hardcoded Paths**: No hardcoded drive letters or static user home directories.

---

## 2. WORK BREAKDOWN STRUCTURE (WBS) & DETAILED TASK LIST

### Phase 1: Requirements Deconstruction & Architectural Design
- [x] **Task 1.1: Requirements & SCM Baseline Deconstruction** (Agent: `cochem-sdp-manager`)
  - [x] Sub-task 1.1.1: Detail ASE/xTB interface mechanics and force convergence parameters.
  - [x] Sub-task 1.1.2: Specify Method Matrix v4 compliance (grids, InHess XTB2, TolMaxG 1e-5, <S^2> < 10%).
  - [x] Sub-task 1.1.3: Specify Mendeleev dynamic mass resolution and provenance tagging.
- [x] **Task 1.2: Architectural Design & Interface Definition** (Agent: `cochem-coder`)
  - [x] Sub-task 1.2.1: Design `QMOracleConfig`, `RelaxationResult`, and `SpinContaminationResult` Pydantic v2 data models.
  - [x] Sub-task 1.2.2: Design `QMOracle` core class with `relax_structure_xtb()`, `evaluate_spin_contamination()`, `build_orca_optimization_input()`, and `validate_conformer_stability()`.

### Phase 2: Pre-Implementation TDD Test Suite (Red Phase)
- [x] **Task 2.1: Author Physical Test Suite in `tests/test_qm_oracle.py`** (Agent: `cochem-tester`)
  - [x] Sub-task 2.1.1: Implement physical constants, unit conversions, and Mendeleev mass tests.
  - [x] Sub-task 2.1.2: Implement Pydantic schema validation tests (`QMOracleConfig`, `RelaxationResult`, `SpinContaminationResult`).
  - [x] Sub-task 2.1.3: Implement `<S^2>` spin contamination mathematical and threshold assertion tests.
  - [x] Sub-task 2.1.4: Implement Method Matrix ORCA/xTB `%geom` block generation tests (`InHess XTB2`, `defgrid1`->`defgrid3`, `TolMaxG 1e-5`).
  - [x] Sub-task 2.1.5: Implement structural relaxation validation tests with ASE/xTB fallback handling.
  - [x] Sub-task 2.1.6: Implement SE(3) equivariance and state immutability preservation tests.
  - [x] Sub-task 2.1.7: Implement Anti-Spoofing AST and zero-mock source code verification.
- [x] **Task 2.2: Configure `pytest.ini`** (Agent: `cochem-tester`)
  - [x] Sub-task 2.2.1: Restrict `testpaths = tests/test_qm_oracle.py` in `CoChem-BASE` and `CoChem-GEOM`.

### Phase 3: Physical Implementation in `src/cochem_geom/eval/qm_oracle.py`
- [x] **Task 3.1: Data Models & Physical Constants** (Agent: `cochem-coder`)
  - [x] Sub-task 3.1.1: Define CODATA conversion factors (`HARTREE_TO_EV`, `EV_TO_HARTREE`, `BOHR_TO_ANGSTROM`, `HARTREE_TO_KCAL_MOL`, etc.) with provenance tags.
  - [x] Sub-task 3.1.2: Implement `QMOracleConfig`, `RelaxationResult`, `SpinContaminationResult`, and `OptimizationMethod` Pydantic models.
- [x] **Task 3.2: Spin Contamination & Method Matrix Logic** (Agent: `cochem-coder`)
  - [x] Sub-task 3.2.1: Implement `compute_expected_s_squared(multiplicity)` and `evaluate_spin_contamination(s_squared_calc, multiplicity, threshold_percent=10.0)`.
  - [x] Sub-task 3.2.2: Implement `generate_orca_opt_block(method, basis, grid_level, weak_complex, frozen_indices)` complying with Method Matrix v4.
- [x] **Task 3.3: ASE & xTB Relaxation Core** (Agent: `cochem-coder`)
  - [x] Sub-task 3.3.1: Implement `relax_conformer_xtb()` and `QMOracle.relax()` using dynamic `mendeleev` masses and ASE.
  - [x] Sub-task 3.3.2: Implement `evaluate_conformer_energy()` and `validate_conformer_ensemble()`.
- [x] **Task 3.4: Packaging & Cross-Repository Sync** (Agent: `cochem-coder`)
  - [x] Sub-task 3.4.1: Ensure `src/cochem_geom/eval/__init__.py` properly exports all symbols.
  - [x] Sub-task 3.4.2: Mirror artifacts to `CoChem-GEOM` and `CoChem-BASE`.

### Phase 4: Test Suite Execution & Verification
- [x] **Task 4.1: Pytest Execution** (Agent: `cochem-tester`)
  - [x] Sub-task 4.1.1: Execute `pytest -v tests/test_qm_oracle.py` asserting 100% pass rate with zero mocks.
- [x] **Task 4.2: Static Verification** (Agent: `cochem-tester`)
  - [x] Sub-task 4.2.1: Verify static typing, linting, and AST cleanliness.

### Phase 5: Adversarial Audit & Signoff
- [x] **Task 5.1: Zero-Mock & Quality Audit** (Agent: `cochem-audit`)
  - [x] Sub-task 5.1.1: Perform AST scan confirming zero mock/stub usages.
  - [x] Sub-task 5.1.2: Verify Method Matrix v4 compliance.
- [x] **Task 5.2: Adversarial Audit & Swarm State Signoff** (Agent: `adversary`)
  - [x] Sub-task 5.2.1: Verify Anti-Spoofing Directive v2.
  - [x] Sub-task 5.2.2: Update `swarm_state.json` with `SUCCESS`.
