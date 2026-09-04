Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_09_Ecosystem_Part_9_prompts.md.
Original prompt:
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 09, Suggestions #81–#90)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring and physical integrity remediation specified in SRS Chunk 09 (Suggestions #81–#90).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§1.2, §3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds, §8A.4 NVIDIA MPS Daemon Lifecycle, §8B.3 Methodological Bans, §8C Production HDF5 SWMR Store Architecture, §9A.1–§9A.2 Frozen-Monomer Protocol R2, §9B.1–§9B.3 Conformer Exploration Protocol, §13–§14 Dual-Track ORCA/CFOUR Architecture), Tripartite Filesystem Air-Gap Architecture, Anti-Spoofing Protocol v2 (Zero-Mock, Dynamic Mendeleev Retrieval, Dynamic Physical Constants, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, synthetic fallback coordinates, or fabricated energies.
  - Strict prohibition on `Calc_Hess true` for all geometry optimizations (enforce `InHess XTB2` or `Lindh`).
  - Strict prohibition on unconstrained counterpoise PES optimization; enforce the Frozen-Monomer Protocol (Recipe R2) along intermolecular coordinate $R$.
  - All atomic masses, isotopic masses, and covalent radii must be dynamically retrieved via `from mendeleev import element` (never hardcode constants).
  - All physical constants must be queried dynamically via `scipy.constants.physical_constants` or `ase.units` (e.g., `scipy.constants.physical_constants['Hartree energy in eV'][0]`).
  - Cross-platform IPC and persistent storage locking strictly via `filelock.FileLock` (POSIX `fcntl.flock` is strictly banned on network and Windows filesystems).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Counterpoise Multi-Job Decoupling & Frozen-Monomer Protocol (Suggestion #81)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_engine.py`  
- `CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py`

### Detailed Requirements:
1. **Purge Ghost Centers from Routine Optimization Decks:**
   - Eliminate automated ghosting (`sym:`) of Monomer B atoms in standard geometry optimization (`! Opt`) decks.
   - Forbid unconstrained counterpoise (CP) potential energy surface optimizations on weakly bound complexes to prevent unphysical dissociation caused by gradient noise and flat PES drift.
2. **Decoupled Boys–Bernardi Interaction Energy Evaluation:**
   - Refactor counterpoise energy corrections into discrete, explicit multi-job evaluations:
     $$E_{\text{int}}^{\text{CP}} = E_{AB}^{AB} - E_A^{AB} - E_B^{AB}$$
     where superscript $AB$ denotes the full complex basis set (utilizing ghost basis centers for the partner monomer during isolated single points), or compile native ORCA `%compound` multi-step scripts.
3. **Frozen-Monomer Optimization (Recipe R2):**
   - When counterpoise distance bracketing or complex geometry optimization is requested, enforce the Frozen-Monomer Protocol (Recipe R2): keep Monomer A and Monomer B internally rigid while optimizing exclusively along the intermolecular distance coordinate $R$.
4. **Tripartite Storage Air-Gap Compliance:**
   - Execute all intermediate monomer and ghost wavefunctions within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`), preserving complete isolation from Ring 1 static repository code and committing only finalized CP-corrected interaction energies and converged geometries to Ring 3 persistent storage (`$COCHEM_ARTIFACTS`).

---

## Deliverable 2: Cartesian Locking for Frozen-Monomer Alignment (Suggestion #82)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_constraints.py`  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`

### Detailed Requirements:
1. **Elimination of Incomplete Distance and Over-Complete Angle Constraints:**
   - Deprecate constraint generation that relies solely on pairwise interatomic distances (`{ B u v C }`), which permits internal valence angles and dihedrals to relax and corrupts the principal rotational constant $A$.
   - Deprecate naive generation of internal angle and dihedral constraint matrices that trigger singular Wilson B-matrix inversions during redundant coordinate transformations.
2. **Automated Fragment Identification & Cartesian Coordinate Freezing:**
   - Implement an automated fragment partitioner in `cochem_torq_constraints.py` that assigns atoms into discrete monomer sub-graphs.
   - For any monomer designated as frozen under Method Matrix v4 §9A.1–§9A.2 ("Freeze high-level monomers to fix $A$; spend the remaining budget on $R$ to fix $B$ and $C$"), emit explicit Cartesian constraints in the ORCA `%geom Constraints` block:
     ```text
     %geom
       Constraints
         { C 0 C }
         { C 1 C }
         ...
         { C k C }
       end
     end
     ```
     where indices $0 \dots k$ span all atoms of the frozen monomer.
3. **Physical Verification:**
   - Ensure that during intermolecular relaxation, the principal rotational constant $A$ of the isolated monomer is preserved within $< 0.2\%$ deviation [M] without inducing coordinate singularity crashes.

---

## Deliverable 3: Energy Unit Normalization & SWMR HDF5 Storage Concurrency (Suggestion #83)
**Target Modules:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
- `CoChem-BASE/Libraries/cochem_base_pes_store.py` (and `cochem_base/data/cochem_base_pes_store.py`)

### Detailed Requirements:
1. **Dynamic Atomic Unit Normalization:**
   - Audit `write_tier_data()` in `cochem_topos_cascade_orchestrator.py`.
   - Prohibit storing raw ASE `atoms.get_potential_energy()` values (electronvolts) under the attribute `electronic_energy_hartree`.
   - Dynamically convert all electronic energies to atomic units (hartrees) using `scipy.constants`:
     ```python
     import scipy.constants

     hartree_in_ev = scipy.constants.physical_constants['Hartree energy in eV'][0]
     energy_hartree = float(energy_ev) / float(hartree_in_ev)
     ```
   - Zero hardcoded floating-point conversion factors (e.g., no raw `27.211386`).
2. **SWMR Mode & Cross-Platform IPC Locking:**
   - In `PESStore` (`cochem_base_pes_store.py`), protect all write, resize, and flush operations using cross-platform `filelock.FileLock` with an explicit timeout (`timeout=30.0`), deprecating POSIX-only `fcntl.flock`.
   - Initialize persistent HDF5 database handles with `libver="latest"` and activate Single-Writer/Multiple-Reader (`swmr=True`) mode:
     ```python
     with self._file_lock.acquire(timeout=30.0):
         with h5py.File(self.storage_path, "a", libver="latest") as h5:
             if not h5.swmr_mode:
                 try:
                     h5.swmr_mode = True
                 except (RuntimeError, ValueError):
                     pass
             # perform atomic dataset append/mutation
             h5.flush()
     ```
3. **6-Tier Environment Matrix Validation:**
   - Verify that file locking and SWMR persistence execute reliably without write-contention crashes on Windows (WSL), macOS (OrbStack), Linux Debian, Codespaces, GitHub Actions, and cluster NFS filesystems.

---

## Deliverable 4: Two-Stage Loose-to-Tight Optimization & Quadrature Grid Scheduling (Suggestion #84)
**Target Modules:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
- `CoChem-TORQ/Libraries/cochem_catalog_compiler.py`

### Detailed Requirements:
1. **Decoupled State Reuse Optimization Pipeline:**
   - In `cochem_topos_cascade_orchestrator.py`, separate preliminary geometry relaxation from final optimization and vibrational frequency calculations into a two-pass `State-in` / `State-out` pipeline.
   - **Pass 1 (Preliminary Relaxation):** Execute optimization with loose numerical quadrature integration grids (`defgrid1`) to accelerate initial coordinate descent.
   - **Pass 2 (Tightening & Frequencies):** Pass the converged Pass 1 geometry via `State-in` into a tight-grid deck specifying `defgrid3`. Perform final re-relaxation and execute numerical/analytic second derivatives (`Freq`) strictly on `defgrid3`.
2. **Compiler Gate Grid Rule Relaxation:**
   - Update `cochem_catalog_compiler.py` to allow `defgrid1` strictly when the stage configuration is tagged with `preliminary_opt=True`.
   - Enforce that any job deck requesting `Freq` or final production optimization (`production_opt=True`) strictly rejects `defgrid1` and requires `defgrid3`.
3. **Physical Error Elimination:**
   - Verify that loose grid noise is completely eliminated from final vibrational analyses, resolving spurious imaginary rocking frequencies on weak intermolecular potential energy surfaces.

---

## Deliverable 5: Finite-Difference Hessian Deferral & Preconditioned Screening (Suggestion #85)
**Target Module:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`

### Detailed Requirements:
1. **Schema Refactoring for Optional Hessians:**
   - In `cochem_topos_cascade_orchestrator.py`, mutate the Pydantic schema `GradientPayload`:
     ```python
     class GradientPayload(BaseModel):
         energy: float
         gradient: List[List[float]]
         hessian: Optional[List[List[float]]] = None
         origin_tier: str
         provenance: str = "[E]"
     ```
2. **Screening Tier Deferral:**
   - In `_execute_hand_topology`, `_execute_goat_xtb2`, and `_execute_crest_nci`, eliminate unconditional calls to `_compute_true_hessian` (`ase.vibrations.Vibrations`).
   - For all screening tiers (Tier 1 through Tier 3), set `hessian = None` and precondition optimization steps using model Hessians (`InHess XTB2` or `Lindh`).
3. **Production Tier Enforcement:**
   - Evaluate exact vibrational Hessians strictly at designated target production tiers (Tier 4 DFT or Tier 5 Coupled-Cluster).
   - Log throughput improvements tagged with provenance tag `[E]` (demonstrating 10–50× screening speedup on 5-to-10 atom complexes).

---

## Deliverable 6: Unconditional Rejection of `Calc_Hess true` (Suggestion #86)
**Target Module:**  
- `CoChem-TORQ/Libraries/cochem_catalog_compiler.py`

### Detailed Requirements:
1. **Unconditional Compiler Rejection:**
   - Audit `validate_orca_deck()` in `cochem_catalog_compiler.py`.
   - Remove any conditional bypasses that permitted `Calc_Hess true` when `InHess` or preconditioning metadata was present.
   - Enforce an unconditional regex/string validation check that raises `MethodMatrixViolationError`:
     ```python
     if re.search(r'\bcalc_hess\s+true\b', deck_content, re.IGNORECASE):
         raise MethodMatrixViolationError(
             "[METHOD-MATRIX-VIOLATION] 'Calc_Hess true' is strictly prohibited for geometry "
             "optimizations under Method Matrix v4 §8B.3. Model Hessians ('InHess XTB2' or 'Lindh') "
             "must be used to prevent massive ab initio Hessian computational overhead."
         )
     ```
2. **Air-Gap Ingestion Gate:**
   - Enforce this validation at the input ingestion boundary before any calculation is dispatched across local runners, containerized workers, or HPC SLURM queues.

---

## Deliverable 7: Strict Open-Shell Spin Contamination Halting Gate (Suggestion #87)
**Target Module:**  
- `CoChem-TORQ/Libraries/cochem_torq_engine.py`

### Detailed Requirements:
1. **Robust ORCA Telemetry Extraction:**
   - In `validate_spin_contamination()`, expand regular expression parsers to capture all variations of ORCA output across versions:
     - `re.search(r'<\s*S\s*\*\*\s*2\s*>\s*:\s*([0-9.]+)', content, re.IGNORECASE)`
     - `re.search(r'<\s*S\s*\^\s*2\s*>\s*:\s*([0-9.]+)', content, re.IGNORECASE)`
     - `re.search(r'Expectation value <S\*\*2>\s*:\s*([0-9.]+)', content, re.IGNORECASE)`
2. **Mandatory Telemetry Assertion:**
   - For all unrestricted calculations (`UKS`, `UHF`), if the expectation value $\langle S^2 \rangle$ cannot be extracted from the output, raise:
     ```python
     raise MissingTelemetryError("[MISSING DATA] Spin observable <S^2> could not be extracted from unrestricted calculation output.")
     ```
3. **10% Threshold Abort Gate:**
   - Compute relative spin contamination against the theoretical ideal $S_{\text{ideal}}(S_{\text{ideal}} + 1)$:
     ```python
     s_ideal_prod = s_ideal * (s_ideal + 1.0)
     spin_dev = abs(s2_val - s_ideal_prod) / s_ideal_prod
     if spin_dev > 0.10:
         raise SpinContaminationError(
             f"[ERR_SPIN_CONTAMINATION] Spin contamination {spin_dev * 100.0:.2f}% exceeds the 10.0% threshold "
             f"mandated by Method Matrix v4 §8B.3 (Measured <S^2> = {s2_val:.4f}, Ideal = {s_ideal_prod:.4f}). "
             "Halting execution to prevent corrupted wavefunction propagation."
         )
     ```

---

## Deliverable 8: Dual-Engine CFOUR Execution Routing & CCSD(T) Integration (Suggestion #88)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`  
- `CoChem-TORQ/Libraries/cochem_torq_engine.py`  
- `CoChem-TORQ/Libraries/cochem_torq_cfour_bridge.py`

### Detailed Requirements:
1. **Dispatcher Integration:**
   - Wire `TorqCfourExecutor` from `cochem_torq_cfour_bridge.py` directly into `cochem_torq_pipeline.py` and `cochem_torq_engine.py`.
   - Update `route_method_matrix()` to explicitly map coupled-cluster tiers (`T3C-3d`, `T4C-1mo`, `CFOUR_VPT2`) to the CFOUR executor rather than falling back through `else` branches to ORCA DFT (`wB97M-V`).
2. **Environment & License Verification:**
   - Prior to executing CFOUR jobs, verify that the `GENBAS` path exists and `CFOUR_NUM_CORES` is set.
   - Verify that the `xcfour` executable exists in `PATH` via `cochem_base.environment.BinaryRegistry`.
3. **Strict Abort on Missing Dependency (Anti-Demotion Mandate):**
   - If CFOUR binaries or licensing are unavailable in the host environment (e.g., standard CI runners), strictly prohibit falling back to DFT.
   - Halt execution cleanly by raising a typed `ToolUnavailableError` with status code `ERR_TOOL_UNAVAILABLE`:
     ```python
     raise ToolUnavailableError(
         "[ERR_TOOL_UNAVAILABLE] CFOUR binary or GENBAS library is not configured in the active environment. "
         "Silent demotion to DFT is strictly prohibited under Method Matrix v4 §9 and §13-§14."
     )
     ```

---

## Deliverable 9: Automated GOAT + CREST Union Conformer Exploration (Suggestion #89)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`

### Detailed Requirements:
1. **End-to-End Conformer Search Integration:**
   - In Stage 3 of `TorqPipeline` (`cochem_torq_pipeline.py`), eliminate the single-geometry passthrough stub.
   - Wire `execute_goat_conformer_pipeline()` and `run_crest(flags="--nci --nocross --noreftopo")` to generate an exhaustive conformer pool.
   - Merge conformer candidate lists into a single union ensemble and execute structural deduplication (using rotational constant differences $\Delta B / B > 0.002$ and RMSD filtering) prior to dispatching high-level quantum refinement.
2. **NVIDIA MPS Health Verification & Device Sandboxing:**
   - Before launching concurrent MLFF/GPU conformer screening passes, query NVIDIA MPS daemon health:
     - Verify active daemon process via `psutil`.
     - Check named pipe sockets in Ring 2 scratch (`$COCHEM_SCRATCH/nvidia_mps`).
   - Isolate worker tasks by injecting specific `CUDA_VISIBLE_DEVICES` masks to prevent CUDA context serialization and latency thrashing.
   - For non-GPU tiers (Codespaces, standard CI runners), route exploration seamlessly through CPU-optimized xTB binaries.

---

## Deliverable 10: Dynamic Mendeleev Covalent Bond Perception & Partitioning (Suggestion #90)
**Target Modules:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
- `CoChem-BASE/src/cochem_base/chemistry/cochem_chemistry_topology.py`

### Detailed Requirements:
1. **Elimination of Fixed Geometric Cutoffs:**
   - Remove all hardcoded bonding cutoffs (e.g., `cutoff=1.6` in `neighbor_list('ij', atoms, cutoff=1.6)`) that incorrectly partition halogenated, sulfurous, or organometallic complexes (e.g., C–Cl = 1.77 Å, C–Br = 1.94 Å, S–S = 2.05 Å).
2. **Dynamic Mendeleev Covalent Radii Retrieval:**
   - Implement dynamic covalent neighbor detection using Pyykkö covalent radii queried from `mendeleev`:
     ```python
     from mendeleev import element

     def get_covalent_radius(symbol: str) -> float:
         el = element(symbol)
         # Pyykkö single bond covalent radius in Angstroms
         rad = el.covalent_radius_pyykko
         if rad is None:
             rad = el.covalent_radius
         return float(rad) / 100.0 if rad > 10.0 else float(rad)
     ```
   - Connect two atoms $i$ and $j$ if their interatomic Cartesian distance satisfies:
     $$d_{ij} \le 1.20 \times (r_{\text{cov}, i} + r_{\text{cov}, j})$$
3. **In-Memory Caching:**
   - Cache atomic covalent radii in an in-memory dictionary upon module initialization to guarantee zero filesystem, network, or database latency during high-throughput neighbor list evaluations.
4. **Monomer Fragment Preservation:**
   - Verify that chlorinated, brominated, and sulfur-containing monomers are recognized as single, connected topological components, ensuring proper assignment of Cartesian constraints during frozen-monomer optimization.

---

## Zero-Mock Verification & Test Plan
You must create or update corresponding test files in `tests/` verifying all 10 fixes without any mocking libraries or synthetic bypasses:

1. `tests/torq/test_counterpoise_frozen_monomer.py`:
   - Verify that counterpoise decks do not place ghost basis functions into unconstrained `! Opt` jobs.
   - Assert that interaction energy evaluation correctly computes $E_{AB}^{AB} - E_A^{AB} - E_B^{AB}$.
2. `tests/torq/test_frozen_monomer_cartesian_constraints.py`:
   - Generate an ORCA `%geom` input deck for a water–dimer complex with Monomer A frozen.
   - Assert that all atoms of Monomer A are assigned `{ C i C }` Cartesian constraints and that zero internal angle/dihedral constraints are emitted.
3. `tests/topos/test_energy_unit_normalization_swmr.py`:
   - Pass ASE energy output in eV (e.g., $-100.0\text{ eV}$) into `write_tier_data()`.
   - Assert that the value committed to HDF5 equals $-100.0 / \text{Hartree\_in\_eV}$ hartrees.
   - Launch concurrent worker writes against `PESStore` and assert zero write contention errors with `swmr=True`.
4. `tests/topos/test_two_stage_grid_scheduling.py`:
   - Verify that Stage 1 optimization input contains `defgrid1` and `preliminary_opt=True`.
   - Verify that Stage 2 frequency input strictly contains `defgrid3` and `production_opt=True`.
   - Assert that `cochem_catalog_compiler.py` rejects `defgrid1` when `production_opt=True`.
5. `tests/topos/test_screening_hessian_deferral.py`:
   - Execute Tier 1 screening on a test complex; assert that `GradientPayload.hessian` is `None` and that finite-difference vibrational loops are bypassed.
6. `tests/torq/test_catalog_compiler_calc_hess_rejection.py`:
   - Pass input decks containing `Calc_Hess true` with and without `InHess XTB2` to `cochem_catalog_compiler.py`.
   - Assert that `MethodMatrixViolationError` is raised unconditionally in all cases.
7. `tests/torq/test_spin_contamination_abort.py`:
   - Feed ORCA output with $\langle S^2 \rangle = 1.15$ for a doublet system ($S_{\text{ideal}} = 0.5$, ideal $S(S+1) = 0.75$; contamination $= 53.3\%$).
   - Assert that execution aborts with `SpinContaminationError` and error code `ERR_SPIN_CONTAMINATION`.
   - Feed clean output ($\langle S^2 \rangle = 0.76$; contamination $= 1.3\%$) and assert execution completes successfully.
8. `tests/torq/test_cfour_dual_engine_routing.py`:
   - Request tier `T3C-3d`. Verify that execution routes to `TorqCfourExecutor`.
   - In an environment without `GENBAS` or CFOUR binaries, assert that `ToolUnavailableError` (`ERR_TOOL_UNAVAILABLE`) is raised and that silent fallback to ORCA DFT is blocked.
9. `tests/torq/test_goat_crest_union_pipeline.py`:
   - Execute Stage 3 of `TorqPipeline` on a multi-conformer organic molecule.
   - Verify that both GOAT and CREST routines are invoked and that candidate conformers are merged and deduplicated.
10. `tests/topos/test_mendeleev_covalent_partitioning.py`:
    - Construct an atomic system containing 1,2-dichloroethane and dimethyl disulfide.
    - Run fragment partitioning; assert that dynamic Pyykkö covalent neighbor lists identify each as a single connected molecule without false fragmentation.

Execute all changes cleanly, adhere strictly to Python typing standards, and verify that the ecosystem passes linting (`ruff check`) and formatting. Proceed with implementation.
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 09, Suggestions #81–#90)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring and physical integrity remediation specified in SRS Chunk 09 (Suggestions #81–#90).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§1.2, §3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds, §8A.4 NVIDIA MPS Daemon Lifecycle, §8B.3 Methodological Bans, §8C Production HDF5 SWMR Store Architecture, §9A.1–§9A.2 Frozen-Monomer Protocol R2, §9B.1–§9B.3 Conformer Exploration Protocol, §13–§14 Dual-Track ORCA/CFOUR Architecture), Tripartite Filesystem Air-Gap Architecture, Anti-Spoofing Protocol v2 (Zero-Mock, Dynamic Mendeleev Retrieval, Dynamic Physical Constants, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, synthetic fallback coordinates, or fabricated energies.
  - Strict prohibition on `Calc_Hess true` for all geometry optimizations (enforce `InHess XTB2` or `Lindh`).
  - Strict prohibition on unconstrained counterpoise PES optimization; enforce the Frozen-Monomer Protocol (Recipe R2) along intermolecular coordinate $R$.
  - All atomic masses, isotopic masses, and covalent radii must be dynamically retrieved via `from mendeleev import element` (never hardcode constants).
  - All physical constants must be queried dynamically via `scipy.constants.physical_constants` or `ase.units` (e.g., `scipy.constants.physical_constants['Hartree energy in eV'][0]`).
  - Cross-platform IPC and persistent storage locking strictly via `filelock.FileLock` (POSIX `fcntl.flock` is strictly banned on network and Windows filesystems).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Counterpoise Multi-Job Decoupling & Frozen-Monomer Protocol (Suggestion #81)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_engine.py`  
- `CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py`

### Detailed Requirements:
1. **Purge Ghost Centers from Routine Optimization Decks:**
   - Eliminate automated ghosting (`sym:`) of Monomer B atoms in standard geometry optimization (`! Opt`) decks.
   - Forbid unconstrained counterpoise (CP) potential energy surface optimizations on weakly bound complexes to prevent unphysical dissociation caused by gradient noise and flat PES drift.
2. **Decoupled Boys–Bernardi Interaction Energy Evaluation:**
   - Refactor counterpoise energy corrections into discrete, explicit multi-job evaluations:
     $$E_{\text{int}}^{\text{CP}} = E_{AB}^{AB} - E_A^{AB} - E_B^{AB}$$
     where superscript $AB$ denotes the full complex basis set (utilizing ghost basis centers for the partner monomer during isolated single points), or compile native ORCA `%compound` multi-step scripts.
3. **Frozen-Monomer Optimization (Recipe R2):**
   - When counterpoise distance bracketing or complex geometry optimization is requested, enforce the Frozen-Monomer Protocol (Recipe R2): keep Monomer A and Monomer B internally rigid while optimizing exclusively along the intermolecular distance coordinate $R$.
4. **Tripartite Storage Air-Gap Compliance:**
   - Execute all intermediate monomer and ghost wavefunctions within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`), preserving complete isolation from Ring 1 static repository code and committing only finalized CP-corrected interaction energies and converged geometries to Ring 3 persistent storage (`$COCHEM_ARTIFACTS`).

---

## Deliverable 2: Cartesian Locking for Frozen-Monomer Alignment (Suggestion #82)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_constraints.py`  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`

### Detailed Requirements:
1. **Elimination of Incomplete Distance and Over-Complete Angle Constraints:**
   - Deprecate constraint generation that relies solely on pairwise interatomic distances (`{ B u v C }`), which permits internal valence angles and dihedrals to relax and corrupts the principal rotational constant $A$.
   - Deprecate naive generation of internal angle and dihedral constraint matrices that trigger singular Wilson B-matrix inversions during redundant coordinate transformations.
2. **Automated Fragment Identification & Cartesian Coordinate Freezing:**
   - Implement an automated fragment partitioner in `cochem_torq_constraints.py` that assigns atoms into discrete monomer sub-graphs.
   - For any monomer designated as frozen under Method Matrix v4 §9A.1–§9A.2 ("Freeze high-level monomers to fix $A$; spend the remaining budget on $R$ to fix $B$ and $C$"), emit explicit Cartesian constraints in the ORCA `%geom Constraints` block:
     ```text
     %geom
       Constraints
         { C 0 C }
         { C 1 C }
         ...
         { C k C }
       end
     end
     ```
     where indices $0 \dots k$ span all atoms of the frozen monomer.
3. **Physical Verification:**
   - Ensure that during intermolecular relaxation, the principal rotational constant $A$ of the isolated monomer is preserved within $< 0.2\%$ deviation [M] without inducing coordinate singularity crashes.

---

## Deliverable 3: Energy Unit Normalization & SWMR HDF5 Storage Concurrency (Suggestion #83)
**Target Modules:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
- `CoChem-BASE/Libraries/cochem_base_pes_store.py` (and `cochem_base/data/cochem_base_pes_store.py`)

### Detailed Requirements:
1. **Dynamic Atomic Unit Normalization:**
   - Audit `write_tier_data()` in `cochem_topos_cascade_orchestrator.py`.
   - Prohibit storing raw ASE `atoms.get_potential_energy()` values (electronvolts) under the attribute `electronic_energy_hartree`.
   - Dynamically convert all electronic energies to atomic units (hartrees) using `scipy.constants`:
     ```python
     import scipy.constants

     hartree_in_ev = scipy.constants.physical_constants['Hartree energy in eV'][0]
     energy_hartree = float(energy_ev) / float(hartree_in_ev)
     ```
   - Zero hardcoded floating-point conversion factors (e.g., no raw `27.211386`).
2. **SWMR Mode & Cross-Platform IPC Locking:**
   - In `PESStore` (`cochem_base_pes_store.py`), protect all write, resize, and flush operations using cross-platform `filelock.FileLock` with an explicit timeout (`timeout=30.0`), deprecating POSIX-only `fcntl.flock`.
   - Initialize persistent HDF5 database handles with `libver="latest"` and activate Single-Writer/Multiple-Reader (`swmr=True`) mode:
     ```python
     with self._file_lock.acquire(timeout=30.0):
         with h5py.File(self.storage_path, "a", libver="latest") as h5:
             if not h5.swmr_mode:
                 try:
                     h5.swmr_mode = True
                 except (RuntimeError, ValueError):
                     pass
             # perform atomic dataset append/mutation
             h5.flush()
     ```
3. **6-Tier Environment Matrix Validation:**
   - Verify that file locking and SWMR persistence execute reliably without write-contention crashes on Windows (WSL), macOS (OrbStack), Linux Debian, Codespaces, GitHub Actions, and cluster NFS filesystems.

---

## Deliverable 4: Two-Stage Loose-to-Tight Optimization & Quadrature Grid Scheduling (Suggestion #84)
**Target Modules:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
- `CoChem-TORQ/Libraries/cochem_catalog_compiler.py`

### Detailed Requirements:
1. **Decoupled State Reuse Optimization Pipeline:**
   - In `cochem_topos_cascade_orchestrator.py`, separate preliminary geometry relaxation from final optimization and vibrational frequency calculations into a two-pass `State-in` / `State-out` pipeline.
   - **Pass 1 (Preliminary Relaxation):** Execute optimization with loose numerical quadrature integration grids (`defgrid1`) to accelerate initial coordinate descent.
   - **Pass 2 (Tightening & Frequencies):** Pass the converged Pass 1 geometry via `State-in` into a tight-grid deck specifying `defgrid3`. Perform final re-relaxation and execute numerical/analytic second derivatives (`Freq`) strictly on `defgrid3`.
2. **Compiler Gate Grid Rule Relaxation:**
   - Update `cochem_catalog_compiler.py` to allow `defgrid1` strictly when the stage configuration is tagged with `preliminary_opt=True`.
   - Enforce that any job deck requesting `Freq` or final production optimization (`production_opt=True`) strictly rejects `defgrid1` and requires `defgrid3`.
3. **Physical Error Elimination:**
   - Verify that loose grid noise is completely eliminated from final vibrational analyses, resolving spurious imaginary rocking frequencies on weak intermolecular potential energy surfaces.

---

## Deliverable 5: Finite-Difference Hessian Deferral & Preconditioned Screening (Suggestion #85)
**Target Module:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`

### Detailed Requirements:
1. **Schema Refactoring for Optional Hessians:**
   - In `cochem_topos_cascade_orchestrator.py`, mutate the Pydantic schema `GradientPayload`:
     ```python
     class GradientPayload(BaseModel):
         energy: float
         gradient: List[List[float]]
         hessian: Optional[List[List[float]]] = None
         origin_tier: str
         provenance: str = "[E]"
     ```
2. **Screening Tier Deferral:**
   - In `_execute_hand_topology`, `_execute_goat_xtb2`, and `_execute_crest_nci`, eliminate unconditional calls to `_compute_true_hessian` (`ase.vibrations.Vibrations`).
   - For all screening tiers (Tier 1 through Tier 3), set `hessian = None` and precondition optimization steps using model Hessians (`InHess XTB2` or `Lindh`).
3. **Production Tier Enforcement:**
   - Evaluate exact vibrational Hessians strictly at designated target production tiers (Tier 4 DFT or Tier 5 Coupled-Cluster).
   - Log throughput improvements tagged with provenance tag `[E]` (demonstrating 10–50× screening speedup on 5-to-10 atom complexes).

---

## Deliverable 6: Unconditional Rejection of `Calc_Hess true` (Suggestion #86)
**Target Module:**  
- `CoChem-TORQ/Libraries/cochem_catalog_compiler.py`

### Detailed Requirements:
1. **Unconditional Compiler Rejection:**
   - Audit `validate_orca_deck()` in `cochem_catalog_compiler.py`.
   - Remove any conditional bypasses that permitted `Calc_Hess true` when `InHess` or preconditioning metadata was present.
   - Enforce an unconditional regex/string validation check that raises `MethodMatrixViolationError`:
     ```python
     if re.search(r'\bcalc_hess\s+true\b', deck_content, re.IGNORECASE):
         raise MethodMatrixViolationError(
             "[METHOD-MATRIX-VIOLATION] 'Calc_Hess true' is strictly prohibited for geometry "
             "optimizations under Method Matrix v4 §8B.3. Model Hessians ('InHess XTB2' or 'Lindh') "
             "must be used to prevent massive ab initio Hessian computational overhead."
         )
     ```
2. **Air-Gap Ingestion Gate:**
   - Enforce this validation at the input ingestion boundary before any calculation is dispatched across local runners, containerized workers, or HPC SLURM queues.

---

## Deliverable 7: Strict Open-Shell Spin Contamination Halting Gate (Suggestion #87)
**Target Module:**  
- `CoChem-TORQ/Libraries/cochem_torq_engine.py`

### Detailed Requirements:
1. **Robust ORCA Telemetry Extraction:**
   - In `validate_spin_contamination()`, expand regular expression parsers to capture all variations of ORCA output across versions:
     - `re.search(r'<\s*S\s*\*\*\s*2\s*>\s*:\s*([0-9.]+)', content, re.IGNORECASE)`
     - `re.search(r'<\s*S\s*\^\s*2\s*>\s*:\s*([0-9.]+)', content, re.IGNORECASE)`
     - `re.search(r'Expectation value <S\*\*2>\s*:\s*([0-9.]+)', content, re.IGNORECASE)`
2. **Mandatory Telemetry Assertion:**
   - For all unrestricted calculations (`UKS`, `UHF`), if the expectation value $\langle S^2 \rangle$ cannot be extracted from the output, raise:
     ```python
     raise MissingTelemetryError("[MISSING DATA] Spin observable <S^2> could not be extracted from unrestricted calculation output.")
     ```
3. **10% Threshold Abort Gate:**
   - Compute relative spin contamination against the theoretical ideal $S_{\text{ideal}}(S_{\text{ideal}} + 1)$:
     ```python
     s_ideal_prod = s_ideal * (s_ideal + 1.0)
     spin_dev = abs(s2_val - s_ideal_prod) / s_ideal_prod
     if spin_dev > 0.10:
         raise SpinContaminationError(
             f"[ERR_SPIN_CONTAMINATION] Spin contamination {spin_dev * 100.0:.2f}% exceeds the 10.0% threshold "
             f"mandated by Method Matrix v4 §8B.3 (Measured <S^2> = {s2_val:.4f}, Ideal = {s_ideal_prod:.4f}). "
             "Halting execution to prevent corrupted wavefunction propagation."
         )
     ```

---

## Deliverable 8: Dual-Engine CFOUR Execution Routing & CCSD(T) Integration (Suggestion #88)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`  
- `CoChem-TORQ/Libraries/cochem_torq_engine.py`  
- `CoChem-TORQ/Libraries/cochem_torq_cfour_bridge.py`

### Detailed Requirements:
1. **Dispatcher Integration:**
   - Wire `TorqCfourExecutor` from `cochem_torq_cfour_bridge.py` directly into `cochem_torq_pipeline.py` and `cochem_torq_engine.py`.
   - Update `route_method_matrix()` to explicitly map coupled-cluster tiers (`T3C-3d`, `T4C-1mo`, `CFOUR_VPT2`) to the CFOUR executor rather than falling back through `else` branches to ORCA DFT (`wB97M-V`).
2. **Environment & License Verification:**
   - Prior to executing CFOUR jobs, verify that the `GENBAS` path exists and `CFOUR_NUM_CORES` is set.
   - Verify that the `xcfour` executable exists in `PATH` via `cochem_base.environment.BinaryRegistry`.
3. **Strict Abort on Missing Dependency (Anti-Demotion Mandate):**
   - If CFOUR binaries or licensing are unavailable in the host environment (e.g., standard CI runners), strictly prohibit falling back to DFT.
   - Halt execution cleanly by raising a typed `ToolUnavailableError` with status code `ERR_TOOL_UNAVAILABLE`:
     ```python
     raise ToolUnavailableError(
         "[ERR_TOOL_UNAVAILABLE] CFOUR binary or GENBAS library is not configured in the active environment. "
         "Silent demotion to DFT is strictly prohibited under Method Matrix v4 §9 and §13-§14."
     )
     ```

---

## Deliverable 9: Automated GOAT + CREST Union Conformer Exploration (Suggestion #89)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`

### Detailed Requirements:
1. **End-to-End Conformer Search Integration:**
   - In Stage 3 of `TorqPipeline` (`cochem_torq_pipeline.py`), eliminate the single-geometry passthrough stub.
   - Wire `execute_goat_conformer_pipeline()` and `run_crest(flags="--nci --nocross --noreftopo")` to generate an exhaustive conformer pool.
   - Merge conformer candidate lists into a single union ensemble and execute structural deduplication (using rotational constant differences $\Delta B / B > 0.002$ and RMSD filtering) prior to dispatching high-level quantum refinement.
2. **NVIDIA MPS Health Verification & Device Sandboxing:**
   - Before launching concurrent MLFF/GPU conformer screening passes, query NVIDIA MPS daemon health:
     - Verify active daemon process via `psutil`.
     - Check named pipe sockets in Ring 2 scratch (`$COCHEM_SCRATCH/nvidia_mps`).
   - Isolate worker tasks by injecting specific `CUDA_VISIBLE_DEVICES` masks to prevent CUDA context serialization and latency thrashing.
   - For non-GPU tiers (Codespaces, standard CI runners), route exploration seamlessly through CPU-optimized xTB binaries.

---

## Deliverable 10: Dynamic Mendeleev Covalent Bond Perception & Partitioning (Suggestion #90)
**Target Modules:**  
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
- `CoChem-BASE/src/cochem_base/chemistry/cochem_chemistry_topology.py`

### Detailed Requirements:
1. **Elimination of Fixed Geometric Cutoffs:**
   - Remove all hardcoded bonding cutoffs (e.g., `cutoff=1.6` in `neighbor_list('ij', atoms, cutoff=1.6)`) that incorrectly partition halogenated, sulfurous, or organometallic complexes (e.g., C–Cl = 1.77 Å, C–Br = 1.94 Å, S–S = 2.05 Å).
2. **Dynamic Mendeleev Covalent Radii Retrieval:**
   - Implement dynamic covalent neighbor detection using Pyykkö covalent radii queried from `mendeleev`:
     ```python
     from mendeleev import element

     def get_covalent_radius(symbol: str) -> float:
         el = element(symbol)
         # Pyykkö single bond covalent radius in Angstroms
         rad = el.covalent_radius_pyykko
         if rad is None:
             rad = el.covalent_radius
         return float(rad) / 100.0 if rad > 10.0 else float(rad)
     ```
   - Connect two atoms $i$ and $j$ if their interatomic Cartesian distance satisfies:
     $$d_{ij} \le 1.20 \times (r_{\text{cov}, i} + r_{\text{cov}, j})$$
3. **In-Memory Caching:**
   - Cache atomic covalent radii in an in-memory dictionary upon module initialization to guarantee zero filesystem, network, or database latency during high-throughput neighbor list evaluations.
4. **Monomer Fragment Preservation:**
   - Verify that chlorinated, brominated, and sulfur-containing monomers are recognized as single, connected topological components, ensuring proper assignment of Cartesian constraints during frozen-monomer optimization.

---

## Zero-Mock Verification & Test Plan
You must create or update corresponding test files in `tests/` verifying all 10 fixes without any mocking libraries or synthetic bypasses:

1. `tests/torq/test_counterpoise_frozen_monomer.py`:
   - Verify that counterpoise decks do not place ghost basis functions into unconstrained `! Opt` jobs.
   - Assert that interaction energy evaluation correctly computes $E_{AB}^{AB} - E_A^{AB} - E_B^{AB}$.
2. `tests/torq/test_frozen_monomer_cartesian_constraints.py`:
   - Generate an ORCA `%geom` input deck for a water–dimer complex with Monomer A frozen.
   - Assert that all atoms of Monomer A are assigned `{ C i C }` Cartesian constraints and that zero internal angle/dihedral constraints are emitted.
3. `tests/topos/test_energy_unit_normalization_swmr.py`:
   - Pass ASE energy output in eV (e.g., $-100.0\text{ eV}$) into `write_tier_data()`.
   - Assert that the value committed to HDF5 equals $-100.0 / \text{Hartree\_in\_eV}$ hartrees.
   - Launch concurrent worker writes against `PESStore` and assert zero write contention errors with `swmr=True`.
4. `tests/topos/test_two_stage_grid_scheduling.py`:
   - Verify that Stage 1 optimization input contains `defgrid1` and `preliminary_opt=True`.
   - Verify that Stage 2 frequency input strictly contains `defgrid3` and `production_opt=True`.
   - Assert that `cochem_catalog_compiler.py` rejects `defgrid1` when `production_opt=True`.
5. `tests/topos/test_screening_hessian_deferral.py`:
   - Execute Tier 1 screening on a test complex; assert that `GradientPayload.hessian` is `None` and that finite-difference vibrational loops are bypassed.
6. `tests/torq/test_catalog_compiler_calc_hess_rejection.py`:
   - Pass input decks containing `Calc_Hess true` with and without `InHess XTB2` to `cochem_catalog_compiler.py`.
   - Assert that `MethodMatrixViolationError` is raised unconditionally in all cases.
7. `tests/torq/test_spin_contamination_abort.py`:
   - Feed ORCA output with $\langle S^2 \rangle = 1.15$ for a doublet system ($S_{\text{ideal}} = 0.5$, ideal $S(S+1) = 0.75$; contamination $= 53.3\%$).
   - Assert that execution aborts with `SpinContaminationError` and error code `ERR_SPIN_CONTAMINATION`.
   - Feed clean output ($\langle S^2 \rangle = 0.76$; contamination $= 1.3\%$) and assert execution completes successfully.
8. `tests/torq/test_cfour_dual_engine_routing.py`:
   - Request tier `T3C-3d`. Verify that execution routes to `TorqCfourExecutor`.
   - In an environment without `GENBAS` or CFOUR binaries, assert that `ToolUnavailableError` (`ERR_TOOL_UNAVAILABLE`) is raised and that silent fallback to ORCA DFT is blocked.
9. `tests/torq/test_goat_crest_union_pipeline.py`:
   - Execute Stage 3 of `TorqPipeline` on a multi-conformer organic molecule.
   - Verify that both GOAT and CREST routines are invoked and that candidate conformers are merged and deduplicated.
10. `tests/topos/test_mendeleev_covalent_partitioning.py`:
    - Construct an atomic system containing 1,2-dichloroethane and dimethyl disulfide.
    - Run fragment partitioning; assert that dynamic Pyykkö covalent neighbor lists identify each as a single connected molecule without false fragmentation.

Execute all changes cleanly, adhere strictly to Python typing standards, and verify that the ecosystem passes linting (`ruff check`) and formatting. Proceed with implementation.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\calc\cochem_calc_execution_router.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Core Execution Router for the CoChem pipeline.
Mandated by Method Matrix v4 §8A.6 (Parsl Multi-Executor Architecture) and §8A.2 (Scout-and-Anchor Topology) [M].
Validates Suggestion #66:
- Elimination of bypassed execution paths by integrating ParslExecutionBroker.
- Workload mapping: heavy QM -> cochem_anchor_cpu with CPU core pinning and OpenMP binding.
- Rapid scans / MLFF -> cochem_scout_gpu.
- Task sandboxing in Ring 2 ephemeral scratch ($COCHEM_SCRATCH/task_<uuid>/).
- Pydantic v2 JobRouteConfig and ExecutionRouteResult contracts.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem_base.config_loader import (
    load_system_config_dict,
    resolve_config_path,
    resolve_executable,
)
from cochem_base.schemas import ExecutionRouteResult, JobRouteConfig

logger = logging.getLogger(__name__)

try:
    import parsl
    from parsl import python_app
    HAS_PARSL = True
except ImportError:
    HAS_PARSL = False
    parsl = None  # type: ignore


class ExecutionRouter:
    """
    Unified Execution Router for the CoChem pipeline.
    Routes computational jobs to Parsl multi-executor topologies (cochem_anchor_cpu, cochem_scout_gpu)
    or remote HPC schedulers (sbatch) with isolated scratch sandboxes.
    """

    def __init__(
        self,
        registry_path: Optional[Union[str, Path]] = None,
        broker: Optional[Any] = None,
        dfk: Optional[Any] = None,
    ) -> None:
        """Initializes the router with Golden Registry and optional Parsl broker/DFK."""
        if registry_path:
            self.registry_path = resolve_config_path(Path(registry_path))
        else:
            self.registry_path = resolve_config_path()

        self.registry = self._load_registry()
        self.broker = broker
        self.dfk = dfk

    def _load_registry(self) -> Dict[str, Any]:
        """Reads the hardware and routing rules."""
        try:
            return load_system_config_dict(self.registry_path)
        except Exception as e:
            logger.error(f"Failed to parse registry at {self.registry_path}: {e}. Defaulting to safe fallback.")
            return {"execution": {"default_engine": "subprocess"}, "engines": {}}

    def resolve_execution_path(self, target_engine: str) -> str:
        """Determines the path for the incoming computational payload."""
        exec_config = self.registry.get("execution") or {}
        engines_config = self.registry.get("engines") or {}

        default_path = exec_config.get("default_engine", "subprocess")

        if target_engine in engines_config:
            engine_info = engines_config[target_engine]
            engine_status = (
                engine_info.get("status", "unknown")
                if isinstance(engine_info, dict)
                else getattr(engine_info, "status", "unknown")
            )
            if engine_status not in ("ready", "found"):
                logger.warning(f"Engine '{target_engine}' status is '{engine_status}'. Proceeding with caution.")
        else:
            logger.warning(f"Engine '{target_engine}' not found in registry. Using default path.")

        return str(default_path)

    def route_job(
        self,
        target_engine_or_type: Optional[str] = None,
        payload_command: Optional[Union[str, List[str]]] = None,
        cwd: Optional[Union[str, Path]] = None,
        *,
        job_type: Optional[str] = None,
        route_config: Optional[JobRouteConfig] = None,
        cpu_core_pinning: Optional[List[int]] = None,
        scratch_dir: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 3600.0,
        job_name: str = "cochem_job",
        **kwargs: Any,
    ) -> ExecutionRouteResult:
        """
        Primary execution dispatch entrypoint conforming to Method Matrix §8A.2, §8A.6.
        Dispatches computational jobs to Parsl heterogeneous pools with sandbox isolation.
        """
        # Determine job type
        effective_job_type = job_type
        if effective_job_type is None and target_engine_or_type is not None:
            if target_engine_or_type in ("heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"):
                effective_job_type = target_engine_or_type
            elif "scan" in target_engine_or_type.lower() or "scout" in target_engine_or_type.lower() or "mlff" in target_engine_or_type.lower():
                effective_job_type = "fast_potential_scan"
            elif "opt" in target_engine_or_type.lower() or "heavy" in target_engine_or_type.lower() or "orca" in target_engine_or_type.lower():
                effective_job_type = "heavy_qm_opt"
            elif "freq" in target_engine_or_type.lower() or "hess" in target_engine_or_type.lower():
                effective_job_type = "frequency"
            else:
                effective_job_type = "single_point"
        elif effective_job_type is None:
            effective_job_type = "heavy_qm_opt"

        # Determine scratch root
        scratch_env = (
            os.environ.get("COCHEM_SCRATCH")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TEMP")
        )
        base_scratch = Path(scratch_dir or cwd or scratch_env or tempfile.gettempdir()).resolve()
        base_scratch.mkdir(parents=True, exist_ok=True)

        task_id = uuid.uuid4().hex
        task_scratch = base_scratch / f"task_{task_id}"
        task_scratch.mkdir(parents=True, exist_ok=True)

        # Build JobRouteConfig if not explicitly supplied
        if route_config is None:
            if effective_job_type in ("heavy_qm_opt", "frequency"):
                assigned_exec = "cochem_anchor_cpu"
            elif effective_job_type in ("fast_potential_scan",):
                assigned_exec = "cochem_scout_gpu"
            else:
                assigned_exec = "cochem_anchor_cpu"

            route_config = JobRouteConfig(
                job_type=effective_job_type,  # type: ignore
                assigned_executor=assigned_exec,  # type: ignore
                cpu_core_pinning=cpu_core_pinning,
                scratch_dir=str(task_scratch),
                timeout_seconds=timeout,
            )

        # Environment configuration and CPU core pinning
        task_env = os.environ.copy()
        if env:
            task_env.update(env)

        if route_config.assigned_executor == "cochem_anchor_cpu":
            if route_config.cpu_core_pinning:
                pins = ",".join(str(p) for p in route_config.cpu_core_pinning)
                task_env["KMP_AFFINITY"] = f"explicit,proclist=[{pins}],granularity=fine"
                task_env["OMP_NUM_THREADS"] = str(len(route_config.cpu_core_pinning))
                task_env["MKL_NUM_THREADS"] = str(len(route_config.cpu_core_pinning))
            else:
                task_env.setdefault("OMP_NUM_THREADS", "1")

        # Command determination
        cmd = payload_command or kwargs.get("command") or [sys.executable, "-c", "print('cochem-task-complete')"]

        # Check if active Parsl DFK exists
        active_dfk = self.dfk
        if active_dfk is None and self.broker is not None and hasattr(self.broker, "get_dfk"):
            active_dfk = self.broker.get_dfk()
        if active_dfk is None and HAS_PARSL:
            try:
                active_dfk = parsl.dfk()
            except Exception:
                active_dfk = None

        if active_dfk is not None:
            executors_in_dfk = list(active_dfk.executors.keys())
            target_executor = route_config.assigned_executor
            if target_executor not in executors_in_dfk and len(executors_in_dfk) > 0:
                logger.warning(
                    f"Executor '{target_executor}' not found in Parsl DFK executors {executors_in_dfk}. Routing to '{executors_in_dfk[0]}'"
                )
                target_executor = executors_in_dfk[0]

            @python_app(executors=[target_executor])
            def _parsl_task_runner(cmd_to_run: Union[str, List[str]], work_dir: str, env_vars: Dict[str, str], t_sec: float) -> int:
                from cochem.concurrency.subprocess_broker import SubprocessBroker
                b = SubprocessBroker(cwd=work_dir, env=env_vars, timeout_seconds=t_sec)
                r = b.execute(cmd_to_run)
                return r.returncode

            future = _parsl_task_runner(cmd, str(task_scratch), task_env, route_config.timeout_seconds)
            return ExecutionRouteResult(
                task_id=task_id,
                assigned_executor=route_config.assigned_executor,
                scratch_dir=task_scratch,
                status="SUBMITTED",
                returncode=0,
                future=future,
                output=None,
            )
        else:
            # Fallback to direct SubprocessBroker execution in scratch sandbox
            broker = SubprocessBroker(cwd=task_scratch, env=task_env, timeout_seconds=route_config.timeout_seconds)
            res = broker.execute(cmd)
            return ExecutionRouteResult(
                task_id=task_id,
                assigned_executor=route_config.assigned_executor,
                scratch_dir=task_scratch,
                status="COMPLETED" if res.success else "FAILED",
                returncode=res.returncode,
                future=None,
                output=res.stdout,
            )

    def _dispatch_local(
        self,
        payload_command: Union[str, List[str]],
        cwd: Union[str, Path],
        env: Optional[Dict[str, str]] = None,
        timeout: float = 300.0,
    ) -> int:
        """Deliverable 3 (Suggestion #73): Structured Local Dispatch & Tripartite Air-Gap Isolation.

        Eliminates shell=True, parses structured argument lists via shlex.split,
        routes execution through SubprocessBroker with stream redirection in Ring 2 scratch,
        and enforces Tripartite air-gap boundary rules.
        """
        import shlex
        import shutil

        # Tripartite Air-Gap Resolution (Ring 2 Scratch)
        scratch_root_env = (
            os.environ.get("COCHEM_SCRATCH")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TEMP")
        )
        base_scratch = Path(scratch_root_env or cwd or tempfile.gettempdir()).resolve()
        base_scratch.mkdir(parents=True, exist_ok=True)

        task_id = uuid.uuid4().hex
        task_scratch = base_scratch / f"task_{task_id}"
        task_scratch.mkdir(parents=True, exist_ok=True)

        # Parse command into structured arguments without shell=True
        posix_mode = (sys.platform != "win32")
        if isinstance(payload_command, str):
            cmd_args = shlex.split(payload_command, posix=posix_mode)
            if not posix_mode:
                cmd_args = [
                    a[1:-1] if (len(a) >= 2 and a.startswith('"') and a.endswith('"')) else a
                    for a in cmd_args
                ]
        else:
            cmd_args = list(payload_command)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        # Stream isolation: stdout and stderr directed to explicit streams in Ring 2 scratch
        stdout_path = task_scratch / f"task_{task_id}.out"
        stderr_path = task_scratch / f"task_{task_id}.err"
        flat_stdout = base_scratch / f"task_{task_id}.out"

        try:
            with open(stdout_path, "w", encoding="utf-8") as out_f, open(stderr_path, "w", encoding="utf-8") as err_f:
                proc = subprocess.run(
                    cmd_args,
                    shell=False,
                    cwd=str(task_scratch),
                    env=merged_env,
                    stdout=out_f,
                    stderr=err_f,
                    timeout=timeout,
                    check=False,
                )
                try:
                    if stdout_path.exists():
                        shutil.copy2(stdout_path, flat_stdout)
                except Exception:
                    pass
                return proc.returncode
        except subprocess.TimeoutExpired:
            logger.error(f"Local dispatch timed out after {timeout}s: {cmd_args}")
            return -124
        except Exception as e:
            logger.error(f"Local dispatch failed: {e}")
            return -1

    def _dispatch_hpc(
        self,
        payload_command: str,
        job_name: str,
        cwd: str,
        cores: int = 4,
        mem_mb: int = 8192,
        wall_time: str = "24:00:00",
    ) -> str:
        """Stage 1.2: HPC Dispatch conforming to Method Matrix §8A.6 (Suggestion #72).

        Single-Node Shared-Memory Template Generation without #SBATCH --ntasks={cores}.
        """
        from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec

        spec = SlurmSubmissionSpec(
            job_name=job_name,
            partition="standard",
            cores=cores,
            mem_mb=mem_mb,
            walltime=wall_time,
            scratch_dir=str(cwd),
            artifact_dir=str(cwd),
            solver="orca",
        )
        generator = SlurmGenerator()
        rendered_script = generator.generate_submission_script(
            spec,
            payload_command=payload_command,
        )

        target_sbatch = Path(cwd) / f"{job_name}_submit.sbatch"
        sbatch = resolve_executable(env_var="SBATCH_CMD", candidates=("sbatch",))
        try:
            target_sbatch.write_text(rendered_script, encoding="utf-8")
            logger.info(f"Generated SLURM script: {target_sbatch}")
            result = subprocess.run([sbatch, str(target_sbatch)], capture_output=True, text=True, cwd=cwd, timeout=60.0, check=True)
            stdout = result.stdout.strip() if result.stdout else ""
            parts = stdout.split()
            return parts[-1] if parts else "UNKNOWN_ID"
        except FileNotFoundError:
            logger.error("'sbatch' command not found. Are you on an HPC cluster?")
            return "HPC_NOT_AVAILABLE"
        except Exception as e:
            logger.error(f"SLURM submission failed: {e}")
            return "SUBMISSION_FAILED"

    def evaluate_counterpoise_interaction(
        self,
        e_ab: float,
        e_a_ghost: float,
        e_b_ghost: float,
    ) -> float:
        """
        Evaluates decoupled Boys-Bernardi interaction energy via compute_counterpoise_interaction_energy:
            E_int^CP = E_AB^{AB} - E_A^{AB} - E_B^{AB}
        """
        return compute_counterpoise_interaction_energy(e_ab, e_a_ghost, e_b_ghost)


def compute_counterpoise_interaction_energy(
    e_ab: float,
    e_a_ghost: float,
    e_b_ghost: float,
) -> float:
    """
    Computes decoupled Boys-Bernardi counterpoise-corrected interaction energy
    under Method Matrix v4 §9A.1-9A.2 (Suggestion #81):
        E_int^CP = E_AB^{AB} - E_A^{AB} - E_B^{AB}
    where E_AB^{AB} is complex energy, E_A^{AB} is monomer A with ghost B,
    and E_B^{AB} is monomer B with ghost A.
    """
    return float(e_ab - e_a_ghost - e_b_ghost)


def validate_counterpoise_request(
    is_opt: bool,
    has_frozen_constraints: bool,
    is_complex: bool = True,
) -> None:
    """
    Validates counterpoise optimization constraints under Method Matrix v4 §9A.1-9A.2.
    Unconstrained counterpoise PES optimization on weakly bound complexes is strictly
    prohibited to prevent unphysical dissociation caused by gradient noise and flat PES drift.
    """
    if is_complex and is_opt and not has_frozen_constraints:
        raise ValueError(
            "[ERR_METHOD_MATRIX] Unconstrained counterpoise geometry optimization is strictly prohibited. "
            "Enforce Frozen-Monomer Protocol (Recipe R2) with Cartesian locking on Monomer A."
        )


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_calc_execution_router.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Core Execution Router for the CoChem pipeline.
Mandated by Method Matrix v4 §8A.6 (Parsl Multi-Executor Architecture) and §8A.2 (Scout-and-Anchor Topology) [M].
Validates Suggestion #66:
- Elimination of bypassed execution paths by integrating ParslExecutionBroker.
- Workload mapping: heavy QM -> cochem_anchor_cpu with CPU core pinning and OpenMP binding.
- Rapid scans / MLFF -> cochem_scout_gpu.
- Task sandboxing in Ring 2 ephemeral scratch ($COCHEM_SCRATCH/task_<uuid>/).
- Pydantic v2 JobRouteConfig and ExecutionRouteResult contracts.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cochem_base.config_loader import (
    get_artifact_dir,
    load_system_config_dict,
    resolve_config_path,
    resolve_executable,
    resolve_mapped_path,
)
from cochem_base.schemas import ExecutionRouteResult, JobRouteConfig
from cochem.concurrency.subprocess_broker import SubprocessBroker

logger = logging.getLogger(__name__)

try:
    import parsl
    from parsl import python_app, bash_app
    HAS_PARSL = True
except ImportError:
    HAS_PARSL = False
    parsl = None  # type: ignore


class ExecutionRouter:
    """
    Unified Execution Router for the CoChem pipeline.
    Routes computational jobs to Parsl multi-executor topologies (cochem_anchor_cpu, cochem_scout_gpu)
    or remote HPC schedulers (sbatch) with isolated scratch sandboxes.
    """

    def __init__(
        self,
        registry_path: Optional[Union[str, Path]] = None,
        broker: Optional[Any] = None,
        dfk: Optional[Any] = None,
    ) -> None:
        """Initializes the router with Golden Registry and optional Parsl broker/DFK."""
        if registry_path:
            self.registry_path = resolve_config_path(Path(registry_path))
        else:
            self.registry_path = resolve_config_path()

        self.registry = self._load_registry()
        self.broker = broker
        self.dfk = dfk

    def _load_registry(self) -> Dict[str, Any]:
        """Reads the hardware and routing rules."""
        try:
            return load_system_config_dict(self.registry_path)
        except Exception as e:
            logger.error(f"Failed to parse registry at {self.registry_path}: {e}. Defaulting to safe fallback.")
            return {"execution": {"default_engine": "subprocess"}, "engines": {}}

    def resolve_execution_path(self, target_engine: str) -> str:
        """Determines the path for the incoming computational payload."""
        exec_config = self.registry.get("execution") or {}
        engines_config = self.registry.get("engines") or {}

        default_path = exec_config.get("default_engine", "subprocess")

        if target_engine in engines_config:
            engine_info = engines_config[target_engine]
            engine_status = (
                engine_info.get("status", "unknown")
                if isinstance(engine_info, dict)
                else getattr(engine_info, "status", "unknown")
            )
            if engine_status not in ("ready", "found"):
                logger.warning(f"Engine '{target_engine}' status is '{engine_status}'. Proceeding with caution.")
        else:
            logger.warning(f"Engine '{target_engine}' not found in registry. Using default path.")

        return str(default_path)

    def route_job(
        self,
        target_engine_or_type: Optional[str] = None,
        payload_command: Optional[Union[str, List[str]]] = None,
        cwd: Optional[Union[str, Path]] = None,
        *,
        job_type: Optional[str] = None,
        route_config: Optional[JobRouteConfig] = None,
        cpu_core_pinning: Optional[List[int]] = None,
        scratch_dir: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 3600.0,
        job_name: str = "cochem_job",
        **kwargs: Any,
    ) -> ExecutionRouteResult:
        """
        Primary execution dispatch entrypoint conforming to Method Matrix §8A.2, §8A.6.
        Dispatches computational jobs to Parsl heterogeneous pools with sandbox isolation.
        """
        # Determine job type
        effective_job_type = job_type
        if effective_job_type is None and target_engine_or_type is not None:
            if target_engine_or_type in ("heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"):
                effective_job_type = target_engine_or_type
            elif "scan" in target_engine_or_type.lower() or "scout" in target_engine_or_type.lower() or "mlff" in target_engine_or_type.lower():
                effective_job_type = "fast_potential_scan"
            elif "opt" in target_engine_or_type.lower() or "heavy" in target_engine_or_type.lower() or "orca" in target_engine_or_type.lower():
                effective_job_type = "heavy_qm_opt"
            elif "freq" in target_engine_or_type.lower() or "hess" in target_engine_or_type.lower():
                effective_job_type = "frequency"
            else:
                effective_job_type = "single_point"
        elif effective_job_type is None:
            effective_job_type = "heavy_qm_opt"

        # Determine scratch root
        scratch_env = (
            os.environ.get("COCHEM_SCRATCH")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TEMP")
        )
        base_scratch = Path(scratch_dir or cwd or scratch_env or tempfile.gettempdir()).resolve()
        base_scratch.mkdir(parents=True, exist_ok=True)

        task_id = uuid.uuid4().hex
        task_scratch = base_scratch / f"task_{task_id}"
        task_scratch.mkdir(parents=True, exist_ok=True)

        # Build JobRouteConfig if not explicitly supplied
        if route_config is None:
            if effective_job_type in ("heavy_qm_opt", "frequency"):
                assigned_exec = "cochem_anchor_cpu"
            elif effective_job_type in ("fast_potential_scan",):
                assigned_exec = "cochem_scout_gpu"
            else:
                assigned_exec = "cochem_anchor_cpu"

            route_config = JobRouteConfig(
                job_type=effective_job_type,  # type: ignore
                assigned_executor=assigned_exec,  # type: ignore
                cpu_core_pinning=cpu_core_pinning,
                scratch_dir=str(task_scratch),
                timeout_seconds=timeout,
            )

        # Environment configuration and CPU core pinning
        task_env = os.environ.copy()
        if env:
            task_env.update(env)

        if route_config.assigned_executor == "cochem_anchor_cpu":
            if route_config.cpu_core_pinning:
                pins = ",".join(str(p) for p in route_config.cpu_core_pinning)
                task_env["KMP_AFFINITY"] = f"explicit,proclist=[{pins}],granularity=fine"
                task_env["OMP_NUM_THREADS"] = str(len(route_config.cpu_core_pinning))
                task_env["MKL_NUM_THREADS"] = str(len(route_config.cpu_core_pinning))
            else:
                task_env.setdefault("OMP_NUM_THREADS", "1")

        # Command determination
        cmd = payload_command or kwargs.get("command") or [sys.executable, "-c", "print('cochem-task-complete')"]

        # Check if active Parsl DFK exists
        active_dfk = self.dfk
        if active_dfk is None and self.broker is not None and hasattr(self.broker, "get_dfk"):
            active_dfk = self.broker.get_dfk()
        if active_dfk is None and HAS_PARSL:
            try:
                active_dfk = parsl.dfk()
            except Exception:
                active_dfk = None

        if active_dfk is not None:
            executors_in_dfk = list(active_dfk.executors.keys())
            target_executor = route_config.assigned_executor
            if target_executor not in executors_in_dfk and len(executors_in_dfk) > 0:
                logger.warning(
                    f"Executor '{target_executor}' not found in Parsl DFK executors {executors_in_dfk}. Routing to '{executors_in_dfk[0]}'"
                )
                target_executor = executors_in_dfk[0]

            @python_app(executors=[target_executor])
            def _parsl_task_runner(cmd_to_run: Union[str, List[str]], work_dir: str, env_vars: Dict[str, str], t_sec: float) -> int:
                from cochem.concurrency.subprocess_broker import SubprocessBroker
                b = SubprocessBroker(cwd=work_dir, env=env_vars, timeout_seconds=t_sec)
                r = b.execute(cmd_to_run)
                return r.returncode

            future = _parsl_task_runner(cmd, str(task_scratch), task_env, route_config.timeout_seconds)
            return ExecutionRouteResult(
                task_id=task_id,
                assigned_executor=route_config.assigned_executor,
                scratch_dir=task_scratch,
                status="SUBMITTED",
                returncode=0,
                future=future,
                output=None,
            )
        else:
            # Fallback to direct SubprocessBroker execution in scratch sandbox
            broker = SubprocessBroker(cwd=task_scratch, env=task_env, timeout_seconds=route_config.timeout_seconds)
            res = broker.execute(cmd)
            return ExecutionRouteResult(
                task_id=task_id,
                assigned_executor=route_config.assigned_executor,
                scratch_dir=task_scratch,
                status="COMPLETED" if res.success else "FAILED",
                returncode=res.returncode,
                future=None,
                output=res.stdout,
            )

    def _dispatch_local(
        self,
        payload_command: Union[str, List[str]],
        cwd: Union[str, Path],
        env: Optional[Dict[str, str]] = None,
        timeout: float = 300.0,
    ) -> int:
        """Deliverable 3 (Suggestion #73): Structured Local Dispatch & Tripartite Air-Gap Isolation.

        Eliminates shell=True, parses structured argument lists via shlex.split,
        routes execution through SubprocessBroker with stream redirection in Ring 2 scratch,
        and enforces Tripartite air-gap boundary rules.
        """
        import shlex
        import shutil

        # Tripartite Air-Gap Resolution (Ring 2 Scratch)
        scratch_root_env = (
            os.environ.get("COCHEM_SCRATCH")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TEMP")
        )
        base_scratch = Path(scratch_root_env or cwd or tempfile.gettempdir()).resolve()
        base_scratch.mkdir(parents=True, exist_ok=True)

        task_id = uuid.uuid4().hex
        task_scratch = base_scratch / f"task_{task_id}"
        task_scratch.mkdir(parents=True, exist_ok=True)

        # Parse command into structured arguments without shell=True
        posix_mode = (sys.platform != "win32")
        if isinstance(payload_command, str):
            cmd_args = shlex.split(payload_command, posix=posix_mode)
            if not posix_mode:
                cmd_args = [
                    a[1:-1] if (len(a) >= 2 and a.startswith('"') and a.endswith('"')) else a
                    for a in cmd_args
                ]
        else:
            cmd_args = list(payload_command)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        # Stream isolation: stdout and stderr directed to explicit streams in Ring 2 scratch
        stdout_path = task_scratch / f"task_{task_id}.out"
        stderr_path = task_scratch / f"task_{task_id}.err"
        flat_stdout = base_scratch / f"task_{task_id}.out"

        try:
            with open(stdout_path, "w", encoding="utf-8") as out_f, open(stderr_path, "w", encoding="utf-8") as err_f:
                proc = subprocess.run(
                    cmd_args,
                    shell=False,
                    cwd=str(task_scratch),
                    env=merged_env,
                    stdout=out_f,
                    stderr=err_f,
                    timeout=timeout,
                    check=False,
                )
                try:
                    if stdout_path.exists():
                        shutil.copy2(stdout_path, flat_stdout)
                except Exception:
                    pass
                return proc.returncode
        except subprocess.TimeoutExpired:
            logger.error(f"Local dispatch timed out after {timeout}s: {cmd_args}")
            return -124
        except Exception as e:
            logger.error(f"Local dispatch failed: {e}")
            return -1

    def _dispatch_hpc(
        self,
        payload_command: str,
        job_name: str,
        cwd: str,
        cores: int = 4,
        mem_mb: int = 8192,
        wall_time: str = "24:00:00",
    ) -> str:
        """Stage 1.2: HPC Dispatch conforming to Method Matrix §8A.6 (Suggestion #72).

        Single-Node Shared-Memory Template Generation without #SBATCH --ntasks={cores}.
        """
        from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec

        spec = SlurmSubmissionSpec(
            job_name=job_name,
            partition="standard",
            cores=cores,
            mem_mb=mem_mb,
            walltime=wall_time,
            scratch_dir=str(cwd),
            artifact_dir=str(cwd),
            solver="orca",
        )
        generator = SlurmGenerator()
        rendered_script = generator.generate_submission_script(
            spec,
            payload_command=payload_command,
        )

        target_sbatch = Path(cwd) / f"{job_name}_submit.sbatch"
        sbatch = resolve_executable(env_var="SBATCH_CMD", candidates=("sbatch",))
        try:
            target_sbatch.write_text(rendered_script, encoding="utf-8")
            logger.info(f"Generated SLURM script: {target_sbatch}")
            result = subprocess.run([sbatch, str(target_sbatch)], capture_output=True, text=True, cwd=cwd, timeout=60.0, check=True)
            stdout = result.stdout.strip() if result.stdout else ""
            parts = stdout.split()
            return parts[-1] if parts else "UNKNOWN_ID"
        except FileNotFoundError:
            logger.error("'sbatch' command not found. Are you on an HPC cluster?")
            return "HPC_NOT_AVAILABLE"
        except Exception as e:
            logger.error(f"SLURM submission failed: {e}")
            return "SUBMISSION_FAILED"

    def evaluate_counterpoise_interaction(
        self,
        e_ab: float,
        e_a_ghost: float,
        e_b_ghost: float,
    ) -> float:
        """
        Evaluates decoupled Boys-Bernardi interaction energy via compute_counterpoise_interaction_energy:
            E_int^CP = E_AB^{AB} - E_A^{AB} - E_B^{AB}
        """
        return compute_counterpoise_interaction_energy(e_ab, e_a_ghost, e_b_ghost)


def compute_counterpoise_interaction_energy(
    e_ab: float,
    e_a_ghost: float,
    e_b_ghost: float,
) -> float:
    """
    Computes decoupled Boys-Bernardi counterpoise-corrected interaction energy
    under Method Matrix v4 §9A.1-9A.2 (Suggestion #81):
        E_int^CP = E_AB^{AB} - E_A^{AB} - E_B^{AB}
    where E_AB^{AB} is complex energy, E_A^{AB} is monomer A with ghost B,
    and E_B^{AB} is monomer B with ghost A.
    """
    return float(e_ab - e_a_ghost - e_b_ghost)


def validate_counterpoise_request(
    is_opt: bool,
    has_frozen_constraints: bool,
    is_complex: bool = True,
) -> None:
    """
    Validates counterpoise optimization constraints under Method Matrix v4 §9A.1-9A.2.
    Unconstrained counterpoise PES optimization on weakly bound complexes is strictly
    prohibited to prevent unphysical dissociation caused by gradient noise and flat PES drift.
    """
    if is_complex and is_opt and not has_frozen_constraints:
        raise ValueError(
            "[ERR_METHOD_MATRIX] Unconstrained counterpoise geometry optimization is strictly prohibited. "
            "Enforce Frozen-Monomer Protocol (Recipe R2) with Cartesian locking on Monomer A."
        )


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\exceptions.py ---
"""Ecosystem-wide exception and warning definitions for CoChem.

Provides hierarchical error types, standardized error codes, structured
metadata payload serialization, polymorphic deserialization registries,
pickle support for multiprocessing, and exception wrapper utilities compliant
with CoChem Method Matrix standards.
"""

from __future__ import annotations

import asyncio
import functools
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)


class ProvenanceErrorCode(str, Enum):
    """Standardized error codes for CoChem provenance, engine, and infrastructure errors."""

    # Method Matrix & Provenance
    METHOD_MATRIX_VIOLATION_DEFGRID = "METHOD_MATRIX_VIOLATION_DEFGRID"
    EXCEPTION_DEFLECTION_BLOCKED = "EXCEPTION_DEFLECTION_BLOCKED"
    MISSING_DATA = "MISSING_DATA"
    SPIN_CONTAMINATION_EXCEEDED = "SPIN_CONTAMINATION_EXCEEDED"
    UNSUPPORTED_METHOD = "UNSUPPORTED_METHOD"
    DISPERSION_MISSING = "DISPERSION_MISSING"
    INVALID_HESSIAN_STRATEGY = "INVALID_HESSIAN_STRATEGY"
    FROZEN_MONOMER_VIOLATION = "FROZEN_MONOMER_VIOLATION"
    PATHOLOGY_CLASH = "PATHOLOGY_CLASH"
    TRIAGE_OVERRIDE_SPIN = "TRIAGE_OVERRIDE_SPIN"
    AUTOFIT_LIMIT_EXCEEDED = "AUTOFIT_LIMIT_EXCEEDED"
    EVALUATION_TIMEOUT = "EVALUATION_TIMEOUT"
    QCSCHEMA_VALIDATION_FAILED = "QCSCHEMA_VALIDATION_FAILED"
    BSSE_CORRECTION_FAILED = "BSSE_CORRECTION_FAILED"

    # Infrastructure & Security
    HDF5_SWMR_LOCK_TIMEOUT = "HDF5_SWMR_LOCK_TIMEOUT"
    REGISTRY_LOCK_TIMEOUT = "REGISTRY_LOCK_TIMEOUT"
    INTEGRITY_VIOLATION = "INTEGRITY_VIOLATION"
    CONFIG_VALIDATION_FAILED = "CONFIG_VALIDATION_FAILED"
    PATH_TRAVERSAL_DETECTED = "PATH_TRAVERSAL_DETECTED"
    TELEMETRY_FAILURE = "TELEMETRY_FAILURE"
    DISK_QUOTA_EXCEEDED = "DISK_QUOTA_EXCEEDED"
    ERR_TOOL_UNAVAILABLE = "ERR_TOOL_UNAVAILABLE"
    ERR_SPIN_CONTAMINATION = "ERR_SPIN_CONTAMINATION"

    # Engine & Math
    CONVERGENCE_FAILURE = "CONVERGENCE_FAILURE"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    HARDWARE_DETECTION_FAILED = "HARDWARE_DETECTION_FAILED"
    SINGULARITY_DETECTED = "SINGULARITY_DETECTED"
    PRECISION_VIOLATION = "PRECISION_VIOLATION"
    LAM_TRIGGER = "LAM_TRIGGER"
    FORTRAN_OVERFLOW = "FORTRAN_OVERFLOW"
    SPCAT_BRIDGE_ERROR = "SPCAT_BRIDGE_ERROR"
    AIRGAP_VIOLATION = "AIRGAP_VIOLATION"

    @classmethod
    def from_str(cls, code: Union[str, ProvenanceErrorCode]) -> ProvenanceErrorCode:
        """Convert a string or enum instance into a ProvenanceErrorCode.

        Args:
            code: String error code or existing ProvenanceErrorCode instance.

        Returns:
            The matching ProvenanceErrorCode enum instance.

        Raises:
            ValueError: If the code does not match any valid ProvenanceErrorCode.
        """
        if isinstance(code, cls):
            return code
        if isinstance(code, str):
            cleaned = code.strip()
            try:
                return cls(cleaned)
            except ValueError:
                try:
                    return cls[cleaned.upper()]
                except KeyError:
                    raise ValueError(f"Unknown ProvenanceErrorCode: {code!r}") from None
        raise ValueError(f"Expected str or ProvenanceErrorCode, got {type(code).__name__}: {code!r}")

    @classmethod
    def has_code(cls, code: Union[str, Any]) -> bool:
        """Check if a given string or object corresponds to a valid ProvenanceErrorCode.

        Args:
            code: String or object to check.

        Returns:
            True if code matches a known ProvenanceErrorCode value or name, False otherwise.
        """
        if isinstance(code, cls):
            return True
        if isinstance(code, str):
            cleaned = code.strip()
            if cleaned in cls._value2member_map_:
                return True
            if cleaned.upper() in cls.__members__:
                return True
        return False


def format_error_message(
    error_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Format a standardized CoChem error message string.

    Args:
        error_code: Optional ProvenanceErrorCode enum or string code.
        message: Descriptive error message text.
        details: Optional dictionary containing contextual metadata.

    Returns:
        Formatted error message string, e.g. '[E: CODE] Message (details: k=v)'.
    """
    code_str: Optional[str] = None
    if error_code is not None:
        code_str = error_code.value if isinstance(error_code, ProvenanceErrorCode) else str(error_code).strip()

    prefix = f"[E: {code_str}] " if code_str else ""
    base = f"{prefix}{message}"
    if details:
        details_str = ", ".join(f"{k}={v!r}" for k, v in sorted(details.items()))
        return f"{base} (details: {details_str})"
    return base


def format_warning_message(
    warning_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Format a standardized CoChem warning message string.

    Args:
        warning_code: Optional ProvenanceErrorCode enum or string code.
        message: Descriptive warning message text.
        details: Optional dictionary containing contextual metadata.

    Returns:
        Formatted warning message string, e.g. '[W: CODE] Message (details: k=v)'.
    """
    code_str: Optional[str] = None
    if warning_code is not None:
        code_str = warning_code.value if isinstance(warning_code, ProvenanceErrorCode) else str(warning_code).strip()

    prefix = f"[W: {code_str}] " if code_str else ""
    base = f"{prefix}{message}"
    if details:
        details_str = ", ".join(f"{k}={v!r}" for k, v in sorted(details.items()))
        return f"{base} (details: {details_str})"
    return base


def _reconstruct_cochem_error(
    cls: Type[CoChemError],
    message: str,
    error_code: Optional[Union[ProvenanceErrorCode, str]],
    details: Optional[Dict[str, Any]],
    timestamp: Optional[str],
) -> CoChemError:
    """Helper function to reconstruct a CoChemError instance during unpickling.

    Args:
        cls: The CoChemError subclass to instantiate.
        message: The original unformatted error message.
        error_code: Optional error code.
        details: Optional details dictionary.
        timestamp: Optional ISO 8601 UTC timestamp string.

    Returns:
        Reconstructed CoChemError (or subclass) instance.
    """
    return cls(
        message=message,
        error_code=error_code,
        details=details,
        timestamp=timestamp,
    )


# Polymorphic exception registry for deserialization
_EXCEPTION_REGISTRY: Dict[str, Type[CoChemError]] = {}


class CoChemError(Exception):
    """Root exception for all CoChem ecosystem errors.

    Attributes:
        message: Human-readable error description.
        error_code: Optional ProvenanceErrorCode or string identifier.
        details: Supplementary structured metadata key-value pairs.
        timestamp: ISO 8601 UTC timestamp of error creation.
        formatted_message: Fully formatted message including code prefix and details.
    """

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register all subclasses dynamically for polymorphic deserialization."""
        super().__init_subclass__(**kwargs)
        _EXCEPTION_REGISTRY[cls.__name__] = cls

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[ProvenanceErrorCode, str]] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        self.message: str = str(message)

        raw_code = error_code if error_code is not None else self.default_error_code
        if isinstance(raw_code, str):
            try:
                self.error_code: Optional[Union[ProvenanceErrorCode, str]] = ProvenanceErrorCode(raw_code)
            except ValueError:
                self.error_code = raw_code
        elif isinstance(raw_code, ProvenanceErrorCode):
            self.error_code = raw_code
        else:
            self.error_code = None

        self.details: Dict[str, Any] = dict(details) if details is not None else {}
        self.timestamp: str = timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat()
        self.formatted_message: str = format_error_message(self.error_code, self.message, self.details)
        super().__init__(self.formatted_message)

    def __str__(self) -> str:
        return self.formatted_message

    def __repr__(self) -> str:
        parts = [repr(self.message)]
        if self.error_code is not None:
            parts.append(f"error_code={self.error_code!r}")
        if self.details:
            parts.append(f"details={self.details!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize exception attributes into a structured dictionary.

        Returns:
            Dictionary containing error_type, error_code, message, details, and timestamp.
        """
        code_val = self.error_code.value if isinstance(self.error_code, ProvenanceErrorCode) else self.error_code
        return {
            "error_type": self.__class__.__name__,
            "error_code": code_val,
            "message": self.message,
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CoChemError:
        """Deserialize a structured dictionary into a CoChemError or appropriate subclass.

        Polymorphically instantiates the target subclass if registered in _EXCEPTION_REGISTRY.

        Args:
            data: Dictionary containing error_type, error_code, message, details, and optional timestamp.

        Returns:
            Instantiated CoChemError (or subclass) instance.
        """
        error_type = data.get("error_type")
        target_cls: Type[CoChemError] = cls
        if error_type and error_type in _EXCEPTION_REGISTRY:
            target_cls = _EXCEPTION_REGISTRY[error_type]
        elif cls is CoChemError and error_type:
            target_cls = CoChemError

        message = str(data.get("message", ""))
        error_code = data.get("error_code")
        details = data.get("details")
        timestamp = data.get("timestamp")

        return target_cls(
            message=message,
            error_code=error_code,
            details=details if isinstance(details, dict) else None,
            timestamp=timestamp if isinstance(timestamp, str) else None,
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize exception attributes into a JSON string.

        Args:
            indent: Optional indentation level for pretty-printing.

        Returns:
            JSON string representation of the exception payload.
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> CoChemError:
        """Deserialize a JSON string into a CoChemError or appropriate subclass.

        Args:
            json_str: JSON formatted string containing serialized error payload.

        Returns:
            Deserialized CoChemError (or subclass) instance.

        Raises:
            ValueError: If the JSON payload is not a valid dictionary object.
        """
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        return cls.from_dict(data)

    def to_pedagogical_guidance(self) -> str:
        """Translates low-level quantum chemical failure signatures into clear, didactic chemical intuition.

        Provides actionable remediation advice tailored for undergraduate students and novice researchers.
        """
        msg_upper = self.message.upper()
        code_str = str(self.error_code).upper() if self.error_code is not None else ""
        cls_name = self.__class__.__name__

        # 1. SCF Convergence Failure
        if "CONVERGENCE" in cls_name or "SCF" in msg_upper or "CONVERG" in msg_upper:
            return (
                "Self-Consistent Field (SCF) electronic iteration did not reach numerical convergence. "
                "In molecular orbital theory, this indicates electronic oscillation or near-degenerate frontier "
                "orbitals (HOMO-LUMO gap closure). Recommended remediation: (1) enable orbital damping or level shifting "
                "(e.g. SOSCF / DIIS), (2) switch initial orbital guess to PModel or HCore, or (3) collapse the numerical "
                "quadrature grid (e.g. defgrid3 -> defgrid2) to smooth the electronic energy landscape."
            )

        # 2. Severe Atomic Clash / Nuclear Overlap
        if "CLASH" in msg_upper or "OVERLAP" in msg_upper or "PATHOLOGY" in code_str or "PATHOLOGY" in cls_name:
            return (
                "Severe atomic clash / unphysical nuclear overlap detected. According to the Pauli exclusion principle, "
                "interpenetrating electron clouds experience steep repulsive Coulombic and exchange forces, causing the "
                "potential energy surface to diverge. Recommended remediation: (1) inspect the 3D molecular geometry for "
                "overlapping atoms (d < 0.65 * sum of vdW radii), (2) pre-relax coordinates using a force-field (GFN-FF or "
                "MMFF94) prior to ab-initio calculation, or (3) verify bond topology."
            )

        # 3. Basis Set Linear Dependency / Singularity
        if "SINGULAR" in msg_upper or "LINEAR DEPENDENCY" in msg_upper or "SINGULARITY" in cls_name:
            return (
                "Near-singular basis set overlap matrix detected (basis set linear dependency). Diffuse basis functions "
                "on adjacent centers overlap excessively, causing overlap matrix eigenvalues to approach zero and matrix "
                "diagonalization to become ill-conditioned. Recommended remediation: (1) adjust the linear dependency "
                "threshold (e.g., THRESH 1e-6), or (2) replace overly diffuse basis sets (e.g. aug-cc-pVTZ) with a contracted "
                "or truncated set (e.g., def2-TZVP or jun-cc-pVTZ)."
            )

        # 4. Negative / Imaginary Vibrational Frequencies
        if "NEGATIVE" in msg_upper or "IMAGINARY" in msg_upper or "HESSIAN" in cls_name or "LAM" in cls_name:
            return (
                "Unexpected imaginary (negative) vibrational frequency encountered. A true ground-state local minimum "
                "must possess 3N-6 strictly positive real normal mode frequencies. A transition state must possess exactly one "
                "imaginary frequency along the reaction coordinate. Recommended remediation: (1) distort the atomic coordinates "
                "slightly along the normal mode vector of the imaginary frequency and re-optimize, or (2) switch to an analytical Hessian."
            )

        # 5. Out of Memory (OOM)
        if "MEMORY" in msg_upper or "OOM" in msg_upper or "ALLOCAT" in msg_upper or "OUTOFMEMORY" in cls_name:
            return (
                "Memory allocation threshold exceeded (%maxcore threshold). High-order electron correlation methods "
                "(MP2, CCSD(T)) and four-center two-electron integral storage scale steeply with basis functions (O(N^4) to O(N^7)). "
                "Recommended remediation: (1) transition integral evaluation to direct SCF (disk-based or on-the-fly), "
                "(2) reduce the number of parallel MPI processes to allocate more RAM per core, or (3) use Resolution-of-Identity (RI/DF)."
            )

        # Generic didactic fallback
        details_summary = f" (Context: {self.details})" if self.details else ""
        return (
            f"Computational failure in {cls_name}: {self.message}{details_summary}. "
            "Please check calculation parameters, hardware resources, and input geometry plausibility."
        )

    def to_diagnostic_telemetry(self) -> Dict[str, Any]:
        """Formats full system telemetry into a structured dictionary for PIs, auditors, and bug reports."""
        import traceback
        import sys
        import platform

        code_val = self.error_code.value if isinstance(self.error_code, ProvenanceErrorCode) else self.error_code

        telemetry: Dict[str, Any] = {
            "error_type": self.__class__.__name__,
            "error_code": code_val,
            "message": self.message,
            "details": dict(self.details),
            "timestamp": self.timestamp,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": sys.version.split()[0],
            },
        }

        try:
            import psutil
            proc = psutil.Process()
            mem_info = proc.memory_info()
            telemetry["process_telemetry"] = {
                "pid": proc.pid,
                "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                "vms_mb": round(mem_info.vms / (1024 * 1024), 2),
            }
        except Exception:
            pass

        if self.__traceback__ is not None:
            telemetry["stack_trace"] = "".join(traceback.format_tb(self.__traceback__))
        elif sys.exc_info()[2] is not None:
            telemetry["stack_trace"] = "".join(traceback.format_tb(sys.exc_info()[2]))
        else:
            telemetry["stack_trace"] = None

        return telemetry

    def __reduce__(self) -> Tuple[Any, Tuple[Any, ...]]:
        """Pickle serialization helper for multiprocessing compatibility.

        Preserves class identity, message, error_code, details, and timestamp
        across process boundaries without redundant formatting prefixes.

        Returns:
            Tuple of (reconstructor_callable, args_tuple).
        """
        return (
            _reconstruct_cochem_error,
            (
                self.__class__,
                self.message,
                self.error_code,
                self.details,
                self.timestamp,
            ),
        )


# Register base error in registry
_EXCEPTION_REGISTRY["CoChemError"] = CoChemError

# Backwards compatibility aliases
CoChemBaseError = CoChemError
_EXCEPTION_REGISTRY["CoChemBaseError"] = CoChemError

CoChemBaseException = CoChemError
_EXCEPTION_REGISTRY["CoChemBaseException"] = CoChemError


# =====================================================================
# Provenance & Method Matrix Exceptions
# =====================================================================

class ProvenanceError(CoChemError):
    """Base error for provenance tracking and Method Matrix compliance violations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = None


class MethodMatrixViolationError(ProvenanceError):
    """Raised when a calculation violates Method Matrix standards (e.g. DEFGRID, unsupported functionals)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID
    )


MethodologyViolationError = MethodMatrixViolationError
_EXCEPTION_REGISTRY["MethodologyViolationError"] = MethodMatrixViolationError


class ExceptionDeflectionBlockedError(ProvenanceError):
    """Raised when an attempt to deflect or silently suppress an exception is detected and blocked."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.EXCEPTION_DEFLECTION_BLOCKED
    )


class AntiSpoofingViolationError(ProvenanceError):
    """Raised when audit trail or telemetry spoofing / tampering is detected."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INTEGRITY_VIOLATION
    )


class MissingDataError(ProvenanceError, KeyError):
    """Raised when required provenance, basis set, or calculation dataset is missing."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = ProvenanceErrorCode.MISSING_DATA


class FrozenMonomerViolationError(MethodMatrixViolationError):
    """Raised when frozen monomer constraints or coordinates are improperly modified."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.FROZEN_MONOMER_VIOLATION
    )


class UnsupportedMethodError(MethodMatrixViolationError):
    """Raised when an unsupported quantum chemistry method, functional, or basis set is requested."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.UNSUPPORTED_METHOD
    )


class TriagePathologyError(ProvenanceError):
    """Raised when automated triage encounters geometric pathology or severe steric clashes."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.PATHOLOGY_CLASH
    )


class BSSECorrectionError(MethodMatrixViolationError):
    """Raised when counterpoise or basis set superposition error (BSSE) correction fails or is inconsistent."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.BSSE_CORRECTION_FAILED
    )


class IntermolecularTopologyError(CoChemError, ValueError):
    """Raised when intermolecular complex geometries violate physical topology bounds (e.g. core clashes or dissociation)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.PATHOLOGY_CLASH
    )


class PreflightValidationError(CoChemError, ValueError):
    """Raised when client-side preflight validation fails (e.g. steric clashes, spin parity, missing dispersion)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONFIG_VALIDATION_FAILED
    )


class QuantumEngineCrashError(CoChemError, RuntimeError):
    """Raised when an underlying quantum chemistry calculation engine crashes or exits abnormally."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONVERGENCE_FAILURE
    )


# =====================================================================
# Ecosystem Dependency & Physics Integrity Exceptions
# =====================================================================

class EcosystemDependencyError(CoChemError, RuntimeError):
    """Raised when an ecosystem dependency, executable, or required external package is missing."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.MISSING_DATA
    )


class BinaryNotFoundError(EcosystemDependencyError):
    """Raised when an external executable cannot be located in the environment path."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.MISSING_DATA
    )


class PhysicsIntegrityError(CoChemError, RuntimeError):
    """Raised when a calculation violates physical integrity, method matrix, or conservation laws."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INTEGRITY_VIOLATION
    )


# =====================================================================
# Infrastructure & Storage Exceptions
# =====================================================================

class HDF5LockTimeoutError(CoChemError, TimeoutError):
    """Raised when acquiring an HDF5 SWMR file lock times out."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT
    )


class DatabaseLockTimeoutError(HDF5LockTimeoutError):
    """Raised when acquiring an HDF5 database lock times out after eviction and retries."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT
    )


class RegistryLockError(CoChemError, TimeoutError):
    """Raised when registry lock acquisition or release times out or fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.REGISTRY_LOCK_TIMEOUT
    )


class SecurityIntegrityError(CoChemError, PermissionError):
    """Raised for security and integrity validation failures (e.g. checksum mismatch, unauthorized access)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INTEGRITY_VIOLATION
    )


class ConfigError(CoChemError, ValueError):
    """Raised when configuration loading, schema validation, or parsing fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONFIG_VALIDATION_FAILED
    )


class PathTraversalError(SecurityIntegrityError):
    """Raised when path traversal attacks or directory escape attempts are detected."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
    )


class TelemetryTransportError(CoChemError, ConnectionError):
    """Raised when telemetry transport fails to send/receive metric packets or socket fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.TELEMETRY_FAILURE
    )


class QCSchemaValidationError(ConfigError):
    """Raised when QCSchema input/output topology, molecule, or wave function fails validation."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.QCSCHEMA_VALIDATION_FAILED
    )


class DiskQuotaError(CoChemError, OSError):
    """Raised when available disk space in Scratch or workspace is below the required threshold."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.DISK_QUOTA_EXCEEDED
    )

    def __init__(
        self,
        message: Optional[Union[str, float]] = None,
        error_code: Optional[Union[ProvenanceErrorCode, str]] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        *,
        required_gb: Optional[float] = None,
        available_gb: Optional[float] = None,
        path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> None:
        merged_details: Dict[str, Any] = dict(details) if details is not None else {}

        if isinstance(message, (int, float)) and required_gb is None:
            required_gb = float(message)
            msg_val = None
        else:
            msg_val = str(message) if message is not None else None

        req = required_gb if required_gb is not None else merged_details.get("required_gb", 50.0)
        avail = available_gb if available_gb is not None else merged_details.get("available_gb", 0.0)
        p = path if path is not None else merged_details.get("path")

        self.required_gb: float = float(req) if req is not None else 50.0
        self.available_gb: float = float(avail) if avail is not None else 0.0
        self.path: Optional[Union[str, Path]] = Path(p) if isinstance(p, (str, Path)) else None

        merged_details["required_gb"] = self.required_gb
        merged_details["available_gb"] = self.available_gb
        if self.path is not None:
            merged_details["path"] = str(self.path)

        if msg_val is None:
            p_str = str(self.path) if self.path is not None else "workspace"
            msg = (
                f"Insufficient scratch disk quota at {p_str}: "
                f"required {self.required_gb:.2f} GB, available {self.available_gb:.2f} GB"
            )
        else:
            msg = msg_val

        super().__init__(
            message=msg,
            error_code=error_code if error_code is not None else self.default_error_code,
            details=merged_details,
            timestamp=timestamp,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["required_gb"] = self.required_gb
        d["available_gb"] = self.available_gb
        d["path"] = str(self.path) if self.path is not None else None
        return d


# =====================================================================
# Engine & Math Exceptions
# =====================================================================

class ConvergenceError(CoChemError, RuntimeError):
    """Raised when SCF, geometry optimization, or numerical convergence fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONVERGENCE_FAILURE
    )


class SpinContaminationError(CoChemError, ValueError):
    """Raised when <S^2> spin contamination exceeds allowed thresholds for open-shell calculations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SPIN_CONTAMINATION_EXCEEDED
    )


class DispersionMissingError(MethodMatrixViolationError):
    """Raised when required dispersion correction (e.g. D3BJ, D4) is omitted in DFT calculations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.DISPERSION_MISSING
    )


class InvalidHessianStrategyError(CoChemError, ValueError):
    """Raised when an invalid Hessian strategy is specified for frequency or transition state calculations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INVALID_HESSIAN_STRATEGY
    )


class SingularityError(CoChemError, ValueError):
    """Raised when numerical matrix singularity or ill-conditioned linear algebra operations occur."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SINGULARITY_DETECTED
    )


class OutOfMemoryGateError(CoChemError, MemoryError):
    """Raised when pre-flight memory gating predicts insufficient RAM/VRAM for a calculation."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.OUT_OF_MEMORY
    )


class HardwareDetectionError(CoChemError, RuntimeError):
    """Raised when CPU/GPU/accelerator hardware topology detection fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.HARDWARE_DETECTION_FAILED
    )


class DispatcherError(CoChemError, RuntimeError):
    """Raised when calculation engine dispatch, executable resolution, or job execution fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.UNSUPPORTED_METHOD
    )


class CoChemPrecisionError(ProvenanceError):
    """Raised when JAX or numerical float precision is violated (e.g. non-float64 execution or precision downgrade)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.PRECISION_VIOLATION
    )


class LAMTriggerError(CoChemError):
    """Raised when a fundamental vibrational frequency is below 50 cm^-1, triggering Phase 7 DVR solvers."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.LAM_TRIGGER
    )


class FortranOverflowError(CoChemError, ValueError):
    """Raised when a parameter value exceeds Double Precision limits (|val| > 1e308) for SPCAT."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.FORTRAN_OVERFLOW
    )


class SPCATBridgeError(CoChemError):
    """Raised when SPCAT formatting, parameter validation, or .var/.int file generation fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SPCAT_BRIDGE_ERROR
    )


class AirGapViolationError(CoChemError, PermissionError):
    """Raised when runtime code attempts to write scratch/log artifacts into Ring 1 static repository."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.AIRGAP_VIOLATION
    )


class CoChemIntegrityError(SecurityIntegrityError):
    """Raised when cryptographic hash verification fails or payload bytes have been tampered with."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INTEGRITY_VIOLATION
    )


class KraitchmanSingularityError(SingularityError):
    """Raised when Kraitchman substitution coordinate calculation encounters an unhandled singularity."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SINGULARITY_DETECTED
    )


class HardwareTelemetryError(HardwareDetectionError):
    """Raised when hardware telemetry query, driver detection, or runtime dispatching fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.HARDWARE_DETECTION_FAILED
    )


class ConformalCalibrationError(ConfigError):
    """Raised when conformal prediction calibration fails due to sample size or coverage criteria."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONFIG_VALIDATION_FAILED
    )


class GoatDaemonExecutionError(ConvergenceError):
    """Raised when ORCA GOAT-EXPLORE daemon execution, socket binding, or hopping fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONVERGENCE_FAILURE
    )


class SymmetryInvarianceError(PhysicsIntegrityError):
    """Raised when molecular permutation-inversion symmetry or energy invariance is violated."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INTEGRITY_VIOLATION
    )


class NumericalConditioningError(SingularityError):
    """Raised when KRR Gram matrix conditioning or Cholesky decomposition fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SINGULARITY_DETECTED
    )


class DispersionIntegrationError(MethodMatrixViolationError):
    """Raised when D3/D4 dispersion correction integration or conservative force evaluation fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.DISPERSION_MISSING
    )


# =====================================================================
# Warnings
# =====================================================================

class CoChemWarning(UserWarning):
    """Base warning category for the CoChem ecosystem."""

    pass


class KraitchmanZPVEWarning(CoChemWarning):
    """Issued when Kraitchman calculation encounters an imaginary radicand due to ZPVE shifts."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TelemetryNetworkExhaustedWarning(CoChemWarning):
    """Issued when webhook telemetry retries are exhausted and payloads are spooled to disk."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class MethodMatrixWarning(CoChemWarning):
    """Issued when a calculation configuration deviates from Method Matrix recommendations but is non-fatal."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ConvergenceWarning(CoChemWarning):
    """Issued when numerical convergence is slow, oscillatory, or near the threshold limit."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class CoChemDeprecationWarning(CoChemWarning, DeprecationWarning):
    """Issued when deprecated features, APIs, or legacy configuration options are accessed."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class HardwareWarning(CoChemWarning):
    """Issued when hardware topology, memory headroom, or acceleration features are degraded."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class SecurityWarning(CoChemWarning):
    """Issued for non-fatal security boundary, path sanitization, or permission concerns."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


# =====================================================================
# Utilities, Boundaries, and Decorators
# =====================================================================

def wrap_exception(
    exc: BaseException,
    target_cls: Type[CoChemError] = CoChemError,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> CoChemError:
    """Wrap an existing exception into a CoChemError subclass, chaining cause and preserving context.

    Args:
        exc: The original exception to wrap.
        target_cls: The destination CoChemError subclass (defaults to CoChemError).
        default_code: Fallback error code if the original exception does not have one.
        message: Optional custom message override. If None, inherits str(exc).
        details: Optional additional metadata dictionary to merge.

    Returns:
        An instance of target_cls chained to exc via __cause__.
    """
    if isinstance(exc, target_cls) and message is None and default_code is None and details is None:
        return exc

    extracted_code = getattr(exc, "error_code", default_code)
    extracted_details: Dict[str, Any] = {}
    exc_details = getattr(exc, "details", None)
    if isinstance(exc_details, dict):
        extracted_details.update(exc_details)
    if details:
        extracted_details.update(details)

    msg = message if message is not None else str(exc)
    code = default_code if default_code is not None else extracted_code

    wrapped = target_cls(
        message=msg,
        error_code=code,
        details=extracted_details if extracted_details else None,
    )
    wrapped.__cause__ = exc
    return wrapped


@contextmanager
def cochem_error_boundary(
    target_cls: Type[CoChemError] = CoChemError,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
) -> Iterator[None]:
    """Context manager boundary that catches exceptions and wraps them into CoChemError.

    Args:
        target_cls: Target CoChemError subclass to wrap into.
        default_code: Fallback error code if the original exception lacks one.
        message: Optional custom message override.
        details: Optional additional metadata dictionary to attach.
        reraise: If True, raises the wrapped exception; if False, suppresses it.
        exclude: Optional exception class or tuple of classes to exclude from wrapping.

    Yields:
        None

    Raises:
        CoChemError: The wrapped exception if reraise is True and an exception was caught.
    """
    try:
        yield
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            raise
        if exclude is not None and isinstance(exc, exclude):
            raise
        wrapped = wrap_exception(
            exc=exc,
            target_cls=target_cls,
            default_code=default_code,
            message=message,
            details=details,
        )
        if reraise:
            raise wrapped from exc


F = TypeVar("F", bound=Callable[..., Any])


@overload
def cochem_error_handler(
    target_cls_or_fn: Type[CoChemError],
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
    *,
    target_cls: Optional[Type[CoChemError]] = None,
) -> Callable[[F], F]:
    ...


@overload
def cochem_error_handler(
    target_cls_or_fn: None = None,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
    *,
    target_cls: Optional[Type[CoChemError]] = None,
) -> Callable[[F], F]:
    ...


@overload
def cochem_error_handler(
    target_cls_or_fn: F,
) -> F:
    ...


def cochem_error_handler(
    target_cls_or_fn: Optional[Union[Type[CoChemError], Callable[..., Any]]] = None,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
    *,
    target_cls: Optional[Type[CoChemError]] = None,
) -> Any:
    """Decorator to wrap function executions inside a CoChem error boundary.

    Supports both synchronous functions and asynchronous coroutine functions.
    Can be used with or without arguments:
        @cochem_error_handler
        def my_func(): ...

        @cochem_error_handler(target_cls=ConvergenceError)
        def my_func(): ...

        @cochem_error_handler(ConvergenceError)
        def my_func(): ...

        @cochem_error_handler(reraise=False)
        def my_func(): ...

    Args:
        target_cls_or_fn: Target CoChemError subclass to wrap into, or decorated function if bare decorator.
        default_code: Fallback error code if an unhandled exception is raised.
        message: Optional custom error message override.
        details: Optional additional structured metadata to attach.
        reraise: If True (default), re-raises wrapped CoChemError; if False, returns None on failure.
        exclude: Optional exception class or tuple of classes to bypass wrapping.
        target_cls: Keyword-only alias for target CoChemError subclass.

    Returns:
        Decorated function or decorator callable.
    """
    if callable(target_cls_or_fn) and not (
        isinstance(target_cls_or_fn, type) and issubclass(target_cls_or_fn, CoChemError)
    ):
        # Bare decorator usage: @cochem_error_handler
        bare_fn = cast(Callable[..., Any], target_cls_or_fn)
        effective_target_cls: Type[CoChemError] = target_cls or CoChemError

        if asyncio.iscoroutinefunction(bare_fn):

            @functools.wraps(bare_fn)
            async def async_bare_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_target_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return await bare_fn(*args, **kwargs)

            return cast(Any, async_bare_wrapper)
        else:

            @functools.wraps(bare_fn)
            def sync_bare_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_target_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return bare_fn(*args, **kwargs)

            return cast(Any, sync_bare_wrapper)

    if target_cls is not None:
        effective_cls = target_cls
    elif isinstance(target_cls_or_fn, type) and issubclass(target_cls_or_fn, CoChemError):
        effective_cls = target_cls_or_fn
    else:
        effective_cls = CoChemError

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


# =====================================================================
# Chunk 7 Ecosystem Exceptions (Suggestions #61-#70)
# =====================================================================

class ElectronicStructureEngineError(CoChemError):
    """Base exception for quantum engine failures."""

    default_code = ProvenanceErrorCode.CONVERGENCE_FAILURE


class ConvergenceFailureError(ElectronicStructureEngineError):
    """Raised when SCF or Geometry Optimization fails to converge."""

    default_code = ProvenanceErrorCode.CONVERGENCE_FAILURE


class MissingBinaryError(ElectronicStructureEngineError):
    """Raised when a required quantum chemistry binary is absent."""

    default_code = ProvenanceErrorCode.HARDWARE_DETECTION_FAILED


class OETDaemonConnectionError(CoChemError):
    """Raised when communication with persistent OET server daemon fails."""

    default_code = ProvenanceErrorCode.TELEMETRY_FAILURE


class ToolUnavailableError(CoChemError):
    """Raised when a required external computational binary or library (e.g. CFOUR or GENBAS) is missing."""

    default_code = ProvenanceErrorCode.ERR_TOOL_UNAVAILABLE


class MissingTelemetryError(CoChemError):
    """Raised when required computational telemetry (such as <S^2>) is missing from calculation output."""

    default_code = ProvenanceErrorCode.MISSING_DATA


_EXCEPTION_REGISTRY["ToolUnavailableError"] = ToolUnavailableError
_EXCEPTION_REGISTRY["MissingTelemetryError"] = MissingTelemetryError


__all__ = [
    # Registries
    "_EXCEPTION_REGISTRY",
    # Error Codes
    "ProvenanceErrorCode",
    # Root Exceptions
    "CoChemError",
    "CoChemBaseError",
    "CoChemBaseException",
    # Provenance & Method Matrix Exceptions
    "ProvenanceError",
    "MethodMatrixViolationError",
    "ExceptionDeflectionBlockedError",
    "AntiSpoofingViolationError",
    "MissingDataError",
    "FrozenMonomerViolationError",
    "UnsupportedMethodError",
    "TriagePathologyError",
    "BSSECorrectionError",
    "IntermolecularTopologyError",
    "PreflightValidationError",
    "QuantumEngineCrashError",
    # Ecosystem Dependency & Physics Integrity Exceptions
    "EcosystemDependencyError",
    "BinaryNotFoundError",
    "PhysicsIntegrityError",
    # Infrastructure & Storage Exceptions
    "HDF5LockTimeoutError",
    "DatabaseLockTimeoutError",
    "RegistryLockError",
    "SecurityIntegrityError",
    "ConfigError",
    "PathTraversalError",
    "TelemetryTransportError",
    "QCSchemaValidationError",
    "DiskQuotaError",
    # Engine & Math Exceptions
    "ConvergenceError",
    "SpinContaminationError",
    "DispersionMissingError",
    "InvalidHessianStrategyError",
    "SingularityError",
    "OutOfMemoryGateError",
    "HardwareDetectionError",
    "DispatcherError",
    "CoChemPrecisionError",
    "LAMTriggerError",
    "FortranOverflowError",
    "SPCATBridgeError",
    "AirGapViolationError",
    "CoChemIntegrityError",
    "KraitchmanSingularityError",
    "HardwareTelemetryError",
    "ConformalCalibrationError",
    "GoatDaemonExecutionError",
    "SymmetryInvarianceError",
    "NumericalConditioningError",
    "DispersionIntegrationError",
    "ElectronicStructureEngineError",
    "ConvergenceFailureError",
    "MissingBinaryError",
    "OETDaemonConnectionError",
    "ToolUnavailableError",
    "MissingTelemetryError",
    # Warnings
    "CoChemWarning",
    "KraitchmanZPVEWarning",
    "TelemetryNetworkExhaustedWarning",
    "MethodMatrixWarning",
    "ConvergenceWarning",
    "CoChemDeprecationWarning",
    "HardwareWarning",
    "SecurityWarning",
    # Utilities, Boundaries, Decorators, and Serialization Helpers
    "format_error_message",
    "format_warning_message",
    "wrap_exception",
    "cochem_error_boundary",
    "cochem_error_handler",
    "_reconstruct_cochem_error",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_base_pes_store.py ---
"""CoChem: Unified High-Concurrency HDF5 PES Store.
===================================================
Complies with Method Matrix v4 §8C: Production HDF5 SWMR Store Architecture.
Features:
- Single-Writer/Multiple-Reader (SWMR) concurrency mode via h5py (libver="latest", swmr=True).
- Cross-platform IPC process locking strictly via filelock.FileLock (timeout=30.0 s).
- Full deprecation of POSIX-only fcntl.flock to guarantee 6-tier environment matrix safety
  (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- Dynamic energy unit normalization from eV to Hartree using scipy.constants.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import filelock
import h5py
import numpy as np
import scipy.constants

logger = logging.getLogger("cochem.base.pes_store")


def convert_ev_to_hartree(energy_ev: float) -> float:
    """
    Dynamically converts energy in electronvolts (eV) to atomic units (Hartree)
    using scipy.constants. Zero hardcoded floating-point conversion factors.
    """
    hartree_in_ev = scipy.constants.physical_constants["Hartree energy in eV"][0]
    return float(energy_ev) / float(hartree_in_ev)


def convert_hartree_to_ev(energy_ha: float) -> float:
    """
    Dynamically converts energy in Hartree to electronvolts (eV)
    using scipy.constants.
    """
    hartree_in_ev = scipy.constants.physical_constants["Hartree energy in eV"][0]
    return float(energy_ha) * float(hartree_in_ev)


class PESStore:
    """
    High-Concurrency Potential Energy Surface (PES) HDF5 Data Store.
    Protects all write, resize, and flush operations using filelock.FileLock
    and activates Single-Writer/Multiple-Reader (SWMR) mode.
    """

    def __init__(
        self,
        storage_path: Union[str, Path],
        timeout: float = 30.0,
        swmr: bool = True,
        libver: str = "latest",
        **kwargs: Any
    ) -> None:
        self.storage_path = Path(storage_path).resolve()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = float(timeout)
        self.swmr_enabled = bool(swmr)
        self.libver = libver

        # Lockfile path: append .lock suffix to persistent HDF5 database path
        self.lock_path = Path(str(self.storage_path) + ".lock")
        self._file_lock = filelock.FileLock(str(self.lock_path), timeout=self.timeout)

        # Initialize HDF5 container safely with filelock
        with self._file_lock.acquire(timeout=self.timeout):
            with h5py.File(self.storage_path, "a", libver=self.libver) as h5:
                if self.swmr_enabled and not h5.swmr_mode:
                    try:
                        h5.swmr_mode = True
                    except (RuntimeError, ValueError):
                        pass
                if "meta" not in h5:
                    meta = h5.create_group("meta")
                    meta.attrs["created_by"] = "CoChem-PESStore-v4"
                    meta.attrs["swmr_mode"] = self.swmr_enabled
                h5.flush()

    def write_point(
        self,
        point_id: str,
        energy_hartree: Optional[float] = None,
        energy_ev: Optional[float] = None,
        coordinates: Optional[Sequence[Sequence[float]] | np.ndarray] = None,
        gradient: Optional[Sequence[Sequence[float]] | np.ndarray] = None,
        hessian: Optional[Sequence[Sequence[float]] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
        extra_attrs: Optional[Dict[str, Any]] = None,
        tier: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Atomically records a point on the PES. Enforces dynamic unit normalization:
        if energy_ev is provided, converts it to Hartree via scipy.constants.
        """
        if energy_hartree is None and energy_ev is not None:
            energy_hartree = convert_ev_to_hartree(energy_ev)
        elif energy_hartree is None:
            energy_hartree = 0.0

        point_key = str(point_id)
        with self._file_lock.acquire(timeout=self.timeout):
            with h5py.File(self.storage_path, "a", libver=self.libver) as h5:
                if self.swmr_enabled and not h5.swmr_mode:
                    try:
                        h5.swmr_mode = True
                    except (RuntimeError, ValueError):
                        pass

                if point_key in h5:
                    del h5[point_key]
                grp = h5.create_group(point_key)

                grp.attrs["electronic_energy_hartree"] = float(energy_hartree)
                grp.attrs["energy_hartree"] = float(energy_hartree)
                grp.create_dataset("energy", data=float(energy_hartree))
                if energy_ev is not None:
                    grp.attrs["electronic_energy_ev"] = float(energy_ev)
                    grp.attrs["energy_ev"] = float(energy_ev)
                if tier is not None:
                    grp.attrs["tier"] = str(tier)
                else:
                    grp.attrs["electronic_energy_ev"] = convert_hartree_to_ev(energy_hartree)

                if symbols is not None:
                    grp.attrs["symbols"] = json.dumps(list(symbols))

                if coordinates is not None:
                    c_arr = np.asarray(coordinates, dtype=np.float64)
                    grp.create_dataset("coordinates", data=c_arr, compression="gzip")

                if gradient is not None:
                    g_arr = np.asarray(gradient, dtype=np.float64)
                    grp.create_dataset("gradient", data=g_arr, compression="gzip")

                if hessian is not None:
                    h_arr = np.asarray(hessian, dtype=np.float64)
                    grp.create_dataset("hessian", data=h_arr, compression="gzip")

                if extra_attrs:
                    for k, v in extra_attrs.items():
                        try:
                            grp.attrs[k] = v
                        except Exception:
                            grp.attrs[k] = json.dumps(v)

                h5.flush()

    def write_tier_data(
        self,
        geom_id: str,
        tier_id: str,
        energy: float,
        energy_is_ev: bool = False,
        gradient: Optional[Sequence[Any] | np.ndarray] = None,
        hessian: Optional[Sequence[Any] | np.ndarray] = None,
        geometry: str = "",
        **kwargs: Any
    ) -> None:
        """
        Writes tiered cascade result data. Automatically normalizes eV to Hartree
        if indicated or detected.
        """
        if energy_is_ev:
            energy_hartree = convert_ev_to_hartree(energy)
        else:
            energy_hartree = float(energy)

        sub_key = f"{geom_id}/{tier_id}"
        self.write_point(
            point_id=sub_key,
            energy_hartree=energy_hartree,
            gradient=gradient,
            hessian=hessian,
            extra_attrs={"geometry": geometry, **kwargs}
        )

    def read_point(self, point_id: str, tier: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """
        Reads point data from HDF5 database in SWMR read mode without exclusive lock contention.
        """
        point_key = str(point_id)
        with h5py.File(self.storage_path, "r", swmr=self.swmr_enabled) as h5:
            if point_key not in h5:
                raise KeyError(f"Point '{point_key}' not found in PESStore at {self.storage_path}.")
            grp = h5[point_key]
            res: Dict[str, Any] = {
                "electronic_energy_hartree": float(grp.attrs.get("electronic_energy_hartree", 0.0)),
                "energy_hartree": float(grp.attrs.get("electronic_energy_hartree", 0.0)),
                "electronic_energy_ev": float(grp.attrs.get("electronic_energy_ev", 0.0)),
                "energy_ev": float(grp.attrs.get("electronic_energy_ev", 0.0)),
            }
            for attr_name in grp.attrs:
                if attr_name not in res:
                    res[attr_name] = grp.attrs[attr_name]

            if "coordinates" in grp:
                res["coordinates"] = grp["coordinates"][:]
            if "gradient" in grp:
                res["gradient"] = grp["gradient"][:]
            if "hessian" in grp:
                res["hessian"] = grp["hessian"][:]
            return res

    def list_points(self) -> List[str]:
        """Lists all point keys present in the database."""
        with h5py.File(self.storage_path, "r", swmr=self.swmr_enabled) as h5:
            return [k for k in h5.keys() if k != "meta"]

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.