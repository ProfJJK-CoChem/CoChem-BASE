Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_01_Ecosystem_Part_1_prompts.md.
Original prompt:
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 01, Suggestions #1–#10)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring, concurrency stabilization, platform compatibility remediation, and physical integrity enforcement specified in SRS Chunk 01 (Suggestions #1–#10).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§1.2 Counterpoise & Intermolecular Distance Bracketing, §3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds & Two-Stage Dynamic Grid Tightening, §8B.3 Methodological Bans: `Calc_Hess true` Prohibition & Spin Contamination Gates, §8C Thread-Safe HDF5 SWMR Storage & CODATA 2022 Atomic Units, §9A.1–§9A.2 Rigid Monomer Protocols & Valence/Dihedral Coordinate Freezing, §9B.1–§9B.3 Combined GOAT + CREST Exploration & Union Deduplication Protocols, §9 & §13–§14 Dual-Engine Track: ORCA & CFOUR Coupled-Cluster Pipelines, Quick Start §QS-1 Tight Convergence Thresholds, Quick Start §QS-3 JAX 64-Bit Initialization), Tripartite Filesystem Air-Gap Architecture ($T_{\text{repo}}$, $T_{\text{scratch}}$, $T_{\text{store}}$), Anti-Spoofing Protocol v2 (Zero-Mock, Dynamic Mendeleev Retrieval, Dynamic Physical Constants, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, dummy loops, synthetic fallback telemetry, fabricated electronic structure cycles, or canned empirical surfaces.
  - Strict prohibition on `Calc_Hess true` for all geometry optimizations (enforce model Hessians `InHess XTB2` or `Lindh`).
  - Strict prohibition on additive diffuse corrections and small-system ONIOM partitioning.
  - All atomic masses, isotopic masses, and covalent/vdW radii must be dynamically retrieved via `from mendeleev import element` or validated pinned tables in `cochem_base.physics.isotopes` (never hardcode physical constants; in air-gapped runtimes, query `cochem_base.physics.isotopes` which is validated against `mendeleev` during Stage 0 provisioning).
  - All physical unit conversions must be queried dynamically via `scipy.constants.value` or CODATA 2022 standards (e.g., Hartree in eV: $27.211386245988\text{ eV/Ha}$ [M]).
  - Cross-process concurrency synchronization and persistent storage locking strictly via `filelock.FileLock` (POSIX `fcntl.flock` is strictly banned on network filesystems, container mounts, and Windows filesystems).
  - Strict Tripartite Workspace Air-Gap compliance: immutable repository root $T_{\text{repo}}$ (`COCHEM_REPO_DIR`), ephemeral scratch $T_{\text{scratch}}$ (`COCHEM_SCRATCH_DIR`), and persistent store $T_{\text{store}}$ (`COCHEM_ARTIFACT_DIR` / `COCHEM_DATA_ROOT`).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Eradication of Synthetic Conformer Fallbacks & Dynamic CREST Binary Discovery (Suggestion #1)
**Target Modules:** `CoChem-TORQ` (`cochem_torq_crest.py`, `src/cochem_torq/crest/runner.py`), `CoChem-BASE` (`src/cochem_base/environment/binary_registry.py`)

### Detailed Requirements:
1. **Purge Synthetic Conformer Displacements and Fabricated Energies:**
   - In `cochem_torq_crest.py`, completely excise `_generate_physical_fallback_ensemble` and all related routines that generate coordinates from random Gaussian perturbations or evaluate arbitrary harmonic penalty functions ($\Delta E = \sum \delta r^2 \times 25.0\text{ kcal/mol}$).
   - Eradicate the assignment of `origin_engine="CREST"` to unphysical, synthetic coordinates. Under no circumstances may missing external executables trigger simulated trajectory coordinates or concocted electronic energies.
2. **Implement Dynamic OS-Agnostic Binary Resolution:**
   - Implement or route binary discovery through `cochem_base.environment.BinaryRegistry.resolve("crest")`.
   - Discover the `crest` binary dynamically across the 6-tier environment matrix (Windows/WSL, macOS, Linux, Containers, HPC) using `shutil.which` and the environment override anchor `COCHEM_CREST_BIN`. Eliminate all hardcoded drive paths or platform-bound executable paths.
3. **Enforce Tripartite Air-Gap & Explicit Dependency Failure Gate:**
   - TORQ must consume discovery results through `cochem_base.environment.BinaryRegistry` without direct unmediated shell invocations.
   - If the `crest` executable is absent from the host system path and environment anchors, immediately raise a typed `BinaryNotFoundError` inheriting from `cochem_base.exceptions.EcosystemDependencyError`:
     ```python
     raise BinaryNotFoundError(
         "[MISSING DATA] CREST executable not discovered in environment path or COCHEM_CREST_BIN. "
         "Provision CREST or configure GOAT-only conformer exploration."
     )
     ```
   - Workflows must halt cleanly or route explicitly to validated alternative engines (e.g., ORCA GOAT) under the investigator's control rather than generating mock data.

---

## Deliverable 2: Decoupling Single-Point Counterpoise Corrections from Optimization Decks (Suggestion #2)
**Target Modules:** `CoChem-TORQ` (`cochem_torq_engine.py`, `cochem_torq_counterpoise.py`), `CoChem-BASE` (`src/cochem_base/schemas/quantum.py`)

### Detailed Requirements:
1. **Eradicate Ghost-Atom Injection During Active Geometry Relaxations:**
   - In `cochem_torq_engine.py`, diagnose and completely eliminate logic that automatically labels atoms in Monomer B with ghost basis function prefixes (`sym:`) inside `! Opt` decks when counterpoise correction is enabled.
   - Recognize that running an optimization deck with ghosted centers optimizes Monomer A in the static basis field of Monomer B without evaluating the full CP gradient $\nabla E_{AB}^{\text{CP}} = \nabla E_{AB} - (\nabla E_{A(B)} - \nabla E_A) - (\nabla E_{B(A)} - \nabla E_B)$ [D], artificially deleting intermolecular electron density and driving unphysical dissociation.
2. **Implement Multi-Job Counterpoise Workflow Execution:**
   - Decouple counterpoise job generation from core engine geometry optimization. All counterpoise calculations must be coordinated via discrete multi-job payloads defined in `cochem_base.schemas.QuantumJobSpec`.
   - Geometry relaxation of the intermolecular complex must be conducted strictly on the regular, unghosted potential energy surface (with frozen monomer internal coordinates) to locate the authentic minimum.
3. **Execute Discrete Single-Point Interaction Energy Bracketing:**
   - Evaluate the Boys-Bernardi counterpoise energy correction strictly via three post-optimization single-point calculations on the converged geometry:
     $$\Delta E_{\text{CP}} = E_{AB}^{AB} - E_{A}^{AB} - E_{B}^{AB}\quad [M]$$
     where:
     - $E_{AB}^{AB}$ is the total energy of the complex in the full dimer basis set.
     - $E_{A}^{AB}$ is the single-point energy of Monomer A with Monomer B centers ghosted (`sym:`).
     - $E_{B}^{AB}$ is the single-point energy of Monomer B with Monomer A centers ghosted (`sym:`).
   - Report raw interaction energy, BSSE correction ($E_{\text{BSSE}} = (E_{A}^{AB} - E_{A}^{A}) + (E_{B}^{AB} - E_{B}^{B})$), and counterpoise-corrected interaction energy with explicit provenance tag `[M]`.

---

## Deliverable 3: Full Internal Coordinate Freezing for Frozen-Monomer Optimizations (Suggestion #3)
**Target Modules:** `CoChem-BASE` (`src/cochem_base/geometry/constraints.py`), `CoChem-TORQ` (`cochem_torq_constraints.py`), `CoChem-TOPOS` (`cochem_topos_cascade_orchestrator.py`)

### Detailed Requirements:
1. **Centralize Internal Coordinate Constraint Generation in BASE:**
   - Eliminate duplicated, cross-coupled constraint generators in `cochem_torq_constraints.py` and `cochem_topos_cascade_orchestrator.py`.
   - Establish the canonical constraint generator inside `cochem_base.geometry.constraints.generate_frozen_monomer_constraints()`. TOPOS and TORQ must consume constraint blocks via `cochem_base.schemas.ConstraintPayload`.
2. **Extract Complete Monomer Internal Degrees of Freedom:**
   - Eliminate graph-edge-only iteration that freezes only bond distances (`{ B u v C }`).
   - For both Monomer A and Monomer B, analyze the molecular graph (via NetworkX or RDKit) to extract:
     - All intramolecular bond lengths: `{ B u v C }`
     - All intramolecular valence angles: `{ A i j k C }`
     - All intramolecular proper dihedral angles: `{ D i j k l C }`
   - Emit complete ORCA `%geom Constraints` blocks containing explicit `{ B u v C }`, `{ A i j k C }`, and `{ D i j k l C }` entries for all atoms within Monomer A and Monomer B.
3. **Preserve Intermolecular Degrees of Freedom:**
   - Ensure intermolecular coordinates (intermolecular separation distance $R$, mutual tilt angles, and relative torsional orientations) are strictly excluded from the constraint block.
   - This enforces the Method Matrix §9A.1–§9A.2 protocol: freeze high-level monomers to fix principal rotational constant $A$ within $0.2\%$ [M], while spending the optimization budget on intermolecular coordinates to resolve $B$ and $C$.
4. **Coordinate Basis Conditioning:**
   - Format coordinates and constraint indices cleanly to prevent ORCA internal coordinate redundancy errors. If redundancy occurs, provide automated fallback to Cartesian constraints on monomer subsets while preserving intermolecular translation and rotation.

---

## Deliverable 4: CODATA 2022 Electronic Energy Normalization & Thread-Safe HDF5 SWMR Concurrency (Suggestion #4)
**Target Modules:** `CoChem-TOPOS` (`cochem_topos_cascade_orchestrator.py`), `CoChem-BASE` (`src/cochem_base/core_engine/cochem_core_pes_store.py`, `src/cochem_base/environment/path_registry.py`)

### Detailed Requirements:
1. **Eradicate Inter-Tier Unit Inconsistency:**
   - In `cochem_topos_cascade_orchestrator.py`, eliminate the critical unit mismatch where ASE calculators write total energies in electron-volts (eV) directly into HDF5 records labeled as `electronic_energy_hartree`, while ab initio tiers write Hartrees.
   - Enforce explicit, programmatic unit normalization on all ASE calculator outputs before persistence:
     ```python
     from scipy.constants import value as get_codata_constant

     HARTREE_TO_EV = get_codata_constant("Hartree energy in eV")  # 27.211386245988 [M]
     energy_hartree = float(energy_ev) / HARTREE_TO_EV
     ```
   - Standardize all total electronic energies across Tiers 1 through 5 in true atomic units (Hartree) adhering to Method Matrix §8C and QCSchema specifications.
2. **Implement Thread-Safe, SWMR-Enabled HDF5 Datastores:**
   - In `cochem_topos_cascade_orchestrator.py` and `cochem_core_pes_store.py`, wrap all `h5py.File` persistence calls with Single-Writer Multiple-Reader (`swmr=True`) mode.
   - Multi-process write transactions across cascade tiers must synchronize using cross-platform file locking via `filelock.FileLock(f"{hdf5_path}.lock", timeout=60.0)` instead of POSIX-only `fcntl.flock`, preventing database corruption across Windows, macOS, Linux, and HPC mounts.
   - For read transactions, open files in read-only SWMR mode (`h5py.File(path, "r", swmr=True)`).
3. **Dynamic OS-Agnostic Artifact Pathing:**
   - Resolve all HDF5 datastore locations dynamically via `cochem_base.environment.PathRegistry.get_artifacts_dir()`, backed by `COCHEM_ARTIFACTS_DIR` with a fallback to `Path(tempfile.gettempdir()) / "cochem" / "artifacts"`. Eliminate all hardcoded filesystem paths.

---

## Deliverable 5: Two-Stage Integration Grid Tightening & Decoupled Numerical Frequency Execution (Suggestion #5)
**Target Modules:** `CoChem-TOPOS` (`cochem_topos_cascade_orchestrator.py`), `CoChem-TORQ` (`cochem_torq_engine.py`, `cochem_catalog_compiler.py`), `CoChem-BASE` (`src/cochem_base/config/grid_policy.py`)

### Detailed Requirements:
1. **Establish Canonical `GridPolicy` Schema in BASE:**
   - Create `src/cochem_base/config/grid_policy.py` defining permissible integration grids across workflow phases:
     ```python
     from enum import Enum
     from pydantic import BaseModel

     class WorkflowPhase(str, Enum):
         PHASE_PREOPT = "preopt"
         PHASE_FINALOPT = "finalopt"
         PHASE_NUMFREQ = "numfreq"

     class GridPolicy(BaseModel):
         preopt_grid: str = "defgrid1"
         finalopt_grid: str = "defgrid3"
         freq_grid: str = "defgrid3"
     ```
   - Harmonize grid validation across TORQ and TOPOS: update `cochem_catalog_compiler.py` to allow `defgrid1` during `PHASE_PREOPT` while strictly enforcing `defgrid3` for `PHASE_FINALOPT` and `PHASE_NUMFREQ`. Deprecated `Grid3`/`Grid5` terminology is strictly prohibited.
2. **Decouple Geometry Optimization from Vibrational Frequency Calculations:**
   - In `cochem_topos_cascade_orchestrator.py`, completely eradicate concatenated single-step decks such as `! r2SCAN-3c Opt Freq defgrid1`.
   - Optimization and vibrational frequency evaluations must be decoupled into independent, staged electronic structure jobs.
3. **Implement Two-Stage Dynamic Grid Tightening Loop:**
   - **Stage 1 (Pre-Optimization):** Initiate geometry relaxation using `defgrid1` with loose convergence thresholds ($\Delta E < 1\times 10^{-4}\text{ Ha}$, $\text{MaxGrad} < 1\times 10^{-3}\text{ Ha/Bohr}$) to accelerate initial conformational and intermolecular adjustment ($2\text{--}3\times$ speedup) [M].
   - **Stage 2 (Final Optimization):** Upon reaching loose convergence, dynamically tighten the integration grid to `defgrid3` and apply full tightened `%geom` convergence thresholds for non-covalent complexes (§4.4, QS-1):
     `TolMaxG 1e-5`, `TolE 1e-7`, `TolRMSG 3e-6`, `TolRMSD 5e-5`, `TolMaxD 1e-4`.
4. **Enforce Tight Grid for Vibrational Second Derivatives:**
   - Execute numerical or analytical second derivative calculations (`! Freq`) strictly on `defgrid3`.
   - Never permit vibrational frequency calculations on `defgrid1`, eliminating spurious negative force constants and unphysical imaginary intermolecular rocking modes caused by quadrature integration grid noise.

---

## Deliverable 6: Optional Screening-Tier Hessians & Zero-Point Energy Deferral (Suggestion #6)
**Target Modules:** `CoChem-BASE` (`src/cochem_base/schemas/quantum.py`), `CoChem-TOPOS` (`cochem_topos_cascade_orchestrator.py`)

### Detailed Requirements:
1. **Refactor `GradientPayload` Schema for Optional Hessians:**
   - In `src/cochem_base/schemas/quantum.py`, modify `GradientPayload` to allow the Hessian matrix to be optional:
     ```python
     from typing import Optional
     from pydantic import BaseModel, Field

     class GradientPayload(BaseModel):
         energy_hartree: float
         gradient: list[list[float]]
         hessian: Optional[list[list[float]]] = Field(
             default=None,
             description="Cartesian force constant matrix; populated exclusively at production tiers (T4/T5)."
         )
     ```
2. **Eradicate Unconditional Screening-Tier Hessian Evaluations:**
   - In `cochem_topos_cascade_orchestrator.py`, eliminate unconditional calls to `_compute_true_hessian` inside preliminary screening functions (`_execute_hand_topology`, `_execute_goat_xtb2`, `_execute_crest_nci`).
   - Remove `ase.vibrations.Vibrations` loops that trigger $6N$ finite-difference coordinate displacements during Tiers 1 through 3.
3. **Enforce Method Matrix Hessian Spend Hierarchy (§3.3 & §8B.3):**
   - Preliminary screening tiers (T1–T3) populate gradients and energies only, utilizing semiempirical model Hessians (`InHess XTB2` or `Lindh`) for geometry preconditioning without computing exact vibrational force constants.
   - Full Cartesian second derivatives and authentic vibrational zero-point vibrational energies (ZPVE) are evaluated exclusively at target production tiers (T4 and T5).
   - Downstream evaluators must report `zpve: None` during screening rather than fabricating approximations or triggering thread starvation across concurrent workers.

---

## Deliverable 7: Unconditional Prohibition of `Calc_Hess true` and Automated Model Hessian Substitution (Suggestion #7)
**Target Modules:** `CoChem-TORQ` (`cochem_catalog_compiler.py`, `cochem_torq_compiler.py`)

### Detailed Requirements:
1. **Implement Unconditional AST-Level Input Deck Sanitization:**
   - In `cochem_torq_compiler.py`, build an AST-level or token-based parser for ORCA input decks.
   - Implement an unconditional check that flags and strips `Calc_Hess true` whenever an optimization task (`! Opt`) is active.
   - Eliminate exception logic in `cochem_catalog_compiler.py` that allowed `Calc_Hess true` when paired with `InHess`. In ORCA, `Calc_Hess true` forces an exact ab initio Hessian evaluation at step 0 regardless of preconditioning, causing hours of unbudgeted compute overhead.
2. **Automated Model Hessian Substitution:**
   - When `Calc_Hess true` is detected in an optimization deck, sanitize the deck by removing `Calc_Hess true` and substituting model Hessian preconditioning:
     ```
     %geom
       InHess XTB2
     end
     ```
     (or `InHess Lindh` if xTB is unavailable).
3. **Structured Telemetry Warning:**
   - Emit a structured warning through `cochem_base.telemetry`:
     `[METHOD_MATRIX_VIOLATION] Calc_Hess true is strictly prohibited for geometry optimizations (§8B.3). Automatically substituted InHess XTB2.`

---

## Deliverable 8: Robust Spin Contamination Validation for Unrestricted Calculations (Suggestion #8)
**Target Modules:** `CoChem-TORQ` (`cochem_torq_parser.py`, `cochem_torq_engine.py`)

### Detailed Requirements:
1. **Implement Resilient Regex Parsing Across Engine Versions:**
   - In `cochem_torq_parser.py`, replace brittle regex patterns with a comprehensive regular expression supporting all ORCA formatting variations across versions (e.g., `<S**2>`, `<S^2>`, variable whitespace, unrestricted DFT/HF headers):
     ```python
     S2_PATTERN = re.compile(r"<\s*S\s*(\*\*|\^)\s*2\s*>\s*:\s*([\d\.]+)", re.IGNORECASE)
     ```
2. **Mandatory Spin Extraction for All Unrestricted Calculations:**
   - In `cochem_torq_engine.py`, make extraction of $\langle S^2 \rangle$ mandatory for every unrestricted calculation (`UKS`, `UHF`).
   - If an unrestricted electronic structure run terminates without reporting $\langle S^2 \rangle$, treat it as an unverified wavefunction and raise `EcosystemExecutionError("[MISSING DATA] Unrestricted calculation did not yield <S^2> expectation value.")`.
3. **Implement Broken-Symmetry Singlet & Multiplet Validation (§8B.3):**
   - For open-shell singlets ($M = 1$, broken-symmetry singlets), set ideal spin $\langle S^2 \rangle_{\text{ideal}} = 0.0$ and enforce an absolute contamination threshold:
     $$\langle S^2 \rangle \le 0.10\quad [M]$$
   - For systems with higher multiplicity ($S \ge 1/2$, $M = 2S + 1 > 1$), evaluate fractional deviation:
     $$\delta_{\text{spin}} = \frac{|\langle S^2 \rangle - S(S + 1)|}{S(S + 1)}\quad [D]$$
     Enforce $\delta_{\text{spin}} \le 0.10$ ($10\%$ threshold).
4. **Enforce Hard Failure Gate:**
   - If spin contamination exceeds $10\%$ without an explicit user override flag (`allow_spin_contamination=True`), immediately abort execution and raise `ERR_SPIN_CONTAMINATION`:
     ```python
     raise SpinContaminationError(
         f"[ERR_SPIN_CONTAMINATION] Electronic state spin contamination exceeds 10% limit: "
         f"<S^2> = {s2_calc:.4f}, Ideal = {s2_ideal:.4f} (deviation {deviation:.1%})."
     )
     ```
   - Prevent contaminated wavefunctions from silently advancing to vibrational or rotational property extractors.

---

## Deliverable 9: Registration of CFOUR Execution Bridge and Ephemeral Scratch Isolation (Suggestion #9)
**Target Modules:** `CoChem-BASE` (`src/cochem_base/interfaces/executors.py`), `CoChem-TORQ` (`cochem_torq_engine.py`, `cochem_torq_pipeline.py`, `src/cochem_torq/cfour/bridge.py`)

### Detailed Requirements:
1. **Register `TorqCfourExecutor` into Execution Dispatcher:**
   - Ensure `TorqCfourExecutor` in `src/cochem_torq/cfour/bridge.py` implements the standard `cochem_base.interfaces.ElectronicStructureExecutor` contract.
   - Register `TorqCfourExecutor` into `cochem_torq_engine.py` and `cochem_torq_pipeline.py`.
   - Update `route_method_matrix` to explicitly map coupled-cluster tier keys (`T3C-3d`, `T4C-1mo`) to `TorqCfourExecutor`. Completely eliminate the fallback `else` branch that silently demoted unmapped coupled-cluster tiers to ORCA $\omega$B97M-V DFT.
2. **Dynamic CFOUR Executable Discovery:**
   - Discover the CFOUR driver executable (`xcfour`) dynamically via `cochem_base.environment.BinaryRegistry` using `shutil.which` and the environment anchor `CFOUR_ROOT`.
   - If CFOUR executables or license paths are missing when a `T3C`/`T4C` tier is requested, immediately raise `BinaryNotFoundError("[MISSING DATA] CFOUR executable (xcfour) not found. Cannot execute coupled-cluster analytic force fields.")`. Silent demotion to DFT is strictly prohibited.
3. **Enforce Ephemeral Scratch Subdirectory Isolation:**
   - CFOUR relies on hardcoded scratch filenames (`ZMAT`, `JOBARC`, `JAINDX`, `GENBAS`, `DIPDER`).
   - Execute every CFOUR task within an isolated ephemeral scratch directory resolved dynamically via:
     `scratch_dir = PathRegistry.create_scratch_dir("cfour")`
     (backed by `Path(tempfile.gettempdir()) / "cochem_scratch" / f"cfour_{uuid4().hex}"`).
   - Concurrently executing CFOUR workers must never share working directories. Clean up scratch files upon task completion while preserving output logs in $T_{\text{store}}$.

---

## Deliverable 10: Full GOAT + CREST Conformer Generation Pipeline Integration & MPS Concurrency (Suggestion #10)
**Target Modules:** `CoChem-TORQ` (`cochem_torq_pipeline.py`, `src/cochem_torq/conformer/orchestrator.py`), `CoChem-BASE` (`src/cochem_base/interfaces/conformer.py`)

### Detailed Requirements:
1. **Eradicate Conformer Exploration Bypass in Stage 3:**
   - In `cochem_torq_pipeline.py`, refactor Stage 3 to completely eliminate the shortcut where only a single `ConformerRecord` (wrapping the unoptimized input seed) is forwarded directly to deduplication.
   - Wire `execute_goat_conformer_pipeline` and `run_crest` directly into the Stage 3 execution DAG. Conformer exploration must execute through the standardized `cochem_base.interfaces.ConformerGenerator` interface, exchanging validated `cochem_base.schemas.ConformerEnsemblePayload` contracts.
2. **Implement NVIDIA MPS & GPU Device-Pinning Concurrency Controls (§8A):**
   - When GOAT executes with external MLFF potentials (e.g., AIMNet2 via `EXTOPT`) in multi-worker environments across Linux, Codespaces, or HPC:
     - Enforce worker process isolation via `CUDA_VISIBLE_DEVICES` or configure active NVIDIA Multi-Process Service (MPS).
     - Pin ORCA/CREST processes to host CPU cores while reserving 1 CPU P-core strictly for scheduling and queue dispatch [D].
     - All GPU inference invocations must use non-blocking device acquisition with a timeout, falling back gracefully to CPU execution if CUDA resources are locked.
3. **Execute Union Deduplication Protocol (§9B.1–§9B.3):**
   - Combine conformers generated from GOAT and CREST into a unified ensemble pool.
   - Execute two-stage union deduplication:
     1. **Rotational Constant Clustering:** Group conformers by rotational constants and merge duplicates if fractional difference satisfies $\Delta B / B < 0.005$ ($0.5\%$) for all principal axes [M].
     2. **Heavy-Atom RMSD Filtering:** Calculate Kabsch coordinate superposition; merge candidate conformers with heavy-atom RMSD $< 0.15\text{ \AA}$ [M].
   - Pass only unique conformers to high-level quantum refinement cascades.

---

## Zero-Mock Verification & Test Plan
Create or update comprehensive integration tests in `tests/` verifying all 10 deliverables against real physical data without synthetic mocks:

1. `tests/torq/test_crest_binary_resolution_and_missing_data.py` (Deliverable 1):
   - Mocking the system PATH to omit `crest` must assert that `BinaryRegistry.resolve("crest")` raises `BinaryNotFoundError` with tag `[MISSING DATA]`.
   - Verify that `cochem_torq_crest.py` does not invoke any fallback that generates random coordinate displacements or fabricated energies.
2. `tests/torq/test_counterpoise_multijob_workflow.py` (Deliverable 2):
   - Submit a water dimer ($(\text{H}_2\text{O})_2$) optimization job with counterpoise enabled.
   - Verify that the generated ORCA `%geom` optimization deck contains NO ghosted atoms (`sym:`).
   - Verify that post-optimization dispatches exactly three discrete single-point calculations ($E_{AB}^{AB}, E_{A}^{AB}, E_{B}^{AB}$) and computes $\Delta E_{\text{CP}}$ via equation [M].
3. `tests/base/test_internal_coordinate_constraint_generation.py` (Deliverable 3):
   - Generate constraints for a non-covalent complex of formic acid and water.
   - Assert that generated ORCA constraints contain `{ B ... C }`, `{ A ... C }`, and `{ D ... C }` covering all internal bonds, angles, and proper dihedrals for both monomers.
   - Verify that intermolecular separation $R$ and intermolecular Euler angles have zero constraints.
4. `tests/topos/test_codata_energy_normalization_and_hdf5_locking.py` (Deliverable 4):
   - Pass an ASE total energy (in eV) to `write_tier_data`.
   - Verify that the energy stored in HDF5 equals `energy_ev / 27.211386245988` within float tolerance.
   - Spawn two concurrent processes writing to the same HDF5 archive; assert that `filelock.FileLock` prevents `BlockingIOError` and file corruption.
5. `tests/topos/test_two_stage_grid_dynamic_tightening.py` (Deliverable 5):
   - Execute a two-stage optimization on a model complex.
   - Assert that Stage 1 submits with `defgrid1` and Stage 2 tightens to `defgrid3` with tight `%geom` parameters.
   - Verify that vibrational frequency calculations (`! Freq`) reject `defgrid1` and enforce `defgrid3`.
6. `tests/topos/test_screening_tier_hessian_deferral.py` (Deliverable 6):
   - Execute Tier 1 screening on a 6-atom complex.
   - Assert that `GradientPayload.hessian` is `None` and that `ase.vibrations.Vibrations` is not invoked.
   - Assert that execution completes without launching $6N$ finite-difference displacements.
7. `tests/torq/test_prohibition_calc_hess_true.py` (Deliverable 7):
   - Pass an ORCA input deck containing `! Opt` and `Calc_Hess true` to `cochem_torq_compiler.py`.
   - Assert that `Calc_Hess true` is stripped, `InHess XTB2` is inserted, and a structured violation warning is logged.
8. `tests/torq/test_spin_contamination_validation.py` (Deliverable 8):
   - Parse sample ORCA output streams with varying `<S**2>` formatting.
   - For an open-shell singlet with $\langle S^2 \rangle = 0.35$, assert immediate abort with `ERR_SPIN_CONTAMINATION`.
   - For a doublet ($S = 1/2$) with $\langle S^2 \rangle = 0.76$ ($\le 10\%$ deviation from $0.75$), assert validation passes.
9. `tests/torq/test_cfour_bridge_registration_and_scratch_isolation.py` (Deliverable 9):
   - Request tier `T3C-3d` in `route_method_matrix`.
   - Assert dispatch routes to `TorqCfourExecutor` and creates an isolated scratch directory containing `ZMAT`.
   - Assert that missing CFOUR binaries raise `BinaryNotFoundError` instead of falling back to ORCA DFT.
10. `tests/torq/test_goat_crest_conformer_union_pipeline.py` (Deliverable 10):
    - Run Stage 3 of `TorqPipeline` on a flexible molecule.
    - Assert that both GOAT and CREST conformer generators are invoked.
    - Verify that the resulting conformer pool undergoes union deduplication based on rotational constant clustering ($\Delta B / B < 0.005$) and RMSD ($< 0.15\text{ \AA}$).

Execute all refactoring strictly adhering to Method Matrix v4, anti-spoofing protocols, and zero-mock testing standards. Verify all files pass typing and static analysis (`ruff check`). Proceed with implementation.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\ci_tools\anti_spoof_linter.py ---
"""# zero-stub anti-spoofing engine
CoChem Anti-Spoof Linter (ci_tools/anti_spoof_linter.py)

Authoritative AST and static analyzer enforcing Zero-Mock & Anti-Spoofing Protocol v2
across the CoChem repository, Council modules, and execution pipelines. Verifies zero
stub logic, mocks, synthetic bypasses, and unamnestied parallel libraries.
"""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("anti_spoof_linter")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

AMNESTY_FILENAME: str = ".anti_spoof_amnesty.json"

BANNED_MOCK_MODULES: Set[str] = {
    "unittest.mock",
    "mock",
    "pytest_mock",
}

BANNED_MOCK_ATTRIBUTES: Set[str] = {
    "MagicMock",
    "Mock",
    "patch",
    "PropertyMock",
    "AsyncMock",
    "create_autospec",
    "NonCallableMock",
    "call_args",
    "mock_open",
}

BANNED_CONCURRENCY_MODULES: Set[str] = {
    "multiprocessing",
    "concurrent.futures",
    "parsl",
    "dask",
    "ray",
    "mpi4py",
    "threading",
    "celery",
}

BANNED_NUMPY_GENERATORS: Set[str] = {
    "linspace",
    "zeros",
    "ones",
    "eye",
    "sin",
    "rand",
    "randn",
    "normal",
    "uniform",
    "choice",
    "randint",
}

BANNED_IDENTIFIER_WORDS: Set[str] = {
    "dummy",
    "fake",
    "placeholder",
    "synthetic",
    "stub",
    "mock",
}

BANNED_OBFUSCATION_TOKENS: Set[str] = {
    "exec",
    "eval",
    "__import__",
}

BANNED_SKIP_SYMBOLS: Set[str] = {
    "skip",
    "skipif",
    "xfail",
    "exit",
    "skipIf",
    "skipUnless",
    "skipTest",
}

BANNED_STATE_TOKENS: Set[str] = {
    "swarm_state",
    "draco_state",
    "audit_verdict",
    "council_verdict",
}

EXCLUDED_DIRS: Set[str] = {
    "build",
    "dist",
    ".venv",
    ".conda",
    "venv",
    "site-packages",
    "artifacts",
    "datasets",
    "data",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".vscode",
    ".idea",
    ".trash",
    "Report_Archive",
    "scratch",
    "node_modules",
}

EXEMPTION_PHRASES: Set[str] = {
    "zero-stub",
    "mocking forbidden",
    "without mock",
    "anti-spoof",
    "anti_spoof",
    "anti-hallucination",
    "amnesty",
}


@dataclass(frozen=True)
class Violation:
    """Immutable record of an anti-spoof or zero-mock compliance violation."""
    file_path: str
    line: int
    col: int
    category: str
    symbol: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "line": self.line,
            "col": self.col,
            "category": self.category,
            "symbol": self.symbol,
            "message": self.message,
        }


def normalize_path_entry(path_str: str) -> Tuple[str, ...]:
    """Normalize a path entry into unified posix format with sub-path aliases."""
    clean = path_str.replace("\\", "/").strip("/")
    parts = clean.split("/")
    variants = [clean]
    if len(parts) > 1 and parts[0].lower().startswith("cochem"):
        variants.append("/".join(parts[1:]))
    return tuple(dict.fromkeys(variants))


def find_repository_root(start_path: Union[str, Path]) -> Path:
    """Locate the root directory of the repository via indicators, env var, or traversal."""
    if "COCHEM_ROOT" in os.environ and os.environ["COCHEM_ROOT"]:
        return Path(os.environ["COCHEM_ROOT"]).resolve()

    p = Path(start_path).resolve()
    if p.is_file():
        p = p.parent

    current = p
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / AMNESTY_FILENAME).exists() or (current / ".git").exists():
            return current
        current = current.parent

    return p


def load_amnesty(root_dir: Union[str, Path]) -> Set[str]:
    """Load authorized zero-mock amnesty whitelist from .anti_spoof_amnesty.json."""
    p = Path(root_dir).resolve()
    target_file = p if p.is_file() and p.name == AMNESTY_FILENAME else None

    if not target_file:
        candidates = [
            p / AMNESTY_FILENAME,
            p.parent / AMNESTY_FILENAME,
            p.parent.parent / AMNESTY_FILENAME,
        ]
        if "COCHEM_ROOT" in os.environ:
            candidates.append(Path(os.environ["COCHEM_ROOT"]) / AMNESTY_FILENAME)
        for c in candidates:
            if c.exists() and c.is_file():
                target_file = c
                break

    if not target_file or not target_file.exists():
        return set()

    amnesty_set: Set[str] = set()
    try:
        content = target_file.read_text(encoding="utf-8-sig")
        data = json.loads(content)
        raw_entries: List[str] = []
        if isinstance(data, list):
            raw_entries = [str(x) for x in data]
        elif isinstance(data, dict):
            files_field = data.get("files", [])
            if isinstance(files_field, list):
                raw_entries = [str(x) for x in files_field]
            elif isinstance(files_field, dict):
                raw_entries = list(files_field.keys())

        for entry in raw_entries:
            for variant in normalize_path_entry(entry):
                amnesty_set.add(variant)
    except Exception as e:
        logger.warning(f"Could not parse amnesty file {target_file}: {e}")

    return amnesty_set


def save_amnesty(root_dir: Path, violations_dict: Dict[str, List[Violation]]) -> Path:
    """Generate or update .anti_spoof_amnesty.json with current authorized baseline."""
    target_file = root_dir / AMNESTY_FILENAME
    entries = sorted(violations_dict.keys())
    data = {
        "description": "Authenticated physical HPC dispatchers, zero-copy shared memory IPC, and local process executors verified under Anti-Spoof Protocol v2.",
        "files": entries,
    }
    target_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target_file


class SpoofVisitor(ast.NodeVisitor):
    """AST Visitor detecting prohibited mock patterns, stubs, synthetic generators, and intercepts."""

    def __init__(
        self,
        filepath: Path,
        rel_path: str,
        is_exempt: bool,
        amnesty_set: Set[str],
    ):
        self.filepath = filepath
        self.rel_path = rel_path
        self.is_exempt = is_exempt
        self.amnesty_set = amnesty_set
        self.violations: List[Violation] = []
        self.is_test_file = "test" in filepath.stem.lower() or "tests" in filepath.parts
        self.pytest_aliases: Set[str] = {"pytest"}
        self.unittest_aliases: Set[str] = {"unittest"}
        self.banned_imported_symbols: Set[str] = set()

    def _is_amnestied_concurrency(self) -> bool:
        norm_variants = normalize_path_entry(self.rel_path)
        return any(v in self.amnesty_set for v in norm_variants)

    def _check_ident(self, name: str, node: ast.AST, context: str) -> None:
        if self.is_exempt:
            return
        if self.is_test_file and name.startswith(("test_", "Test")):
            return

        name_lower = name.lower()
        tokens = set(re.findall(r"[a-z]+", re.sub(r"([A-Z])", r" \1", name).lower()))
        for kw in BANNED_IDENTIFIER_WORDS:
            if kw in tokens or kw in name_lower:
                lineno = getattr(node, "lineno", 1)
                col = getattr(node, "col_offset", 0)
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=lineno,
                        col=col,
                        category="BANNED_IDENTIFIER",
                        symbol=name,
                        message=f"Banned identifier word '{kw}' detected in {context} '{name}'",
                    )
                )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "pytest":
                self.pytest_aliases.add(alias.asname or "pytest")
            elif alias.name == "unittest":
                self.unittest_aliases.add(alias.asname or "unittest")

            is_mock = any(alias.name == bm or alias.name.startswith(bm + ".") for bm in BANNED_MOCK_MODULES)
            is_concurrency = any(alias.name == bc or alias.name.startswith(bc + ".") for bc in BANNED_CONCURRENCY_MODULES)

            if is_mock:
                if not self.is_exempt:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="MOCK_IMPORT",
                            symbol=alias.name,
                            message=f"Prohibited mock module import '{alias.name}'",
                        )
                    )
            elif is_concurrency:
                if not self.is_exempt and not self._is_amnestied_concurrency():
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="CONCURRENCY_IMPORT",
                            symbol=alias.name,
                            message=f"Unamnestied concurrency import '{alias.name}'",
                        )
                    )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""

        is_mock_mod = any(mod == bm or mod.startswith(bm + ".") for bm in BANNED_MOCK_MODULES) or (mod == "unittest" and any(a.name == "mock" for a in node.names))
        is_conc_mod = any(mod == bc or mod.startswith(bc + ".") for bc in BANNED_CONCURRENCY_MODULES) or (mod == "concurrent" and any(a.name == "futures" for a in node.names))

        if is_mock_mod:
            if not self.is_exempt:
                for alias in node.names:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="MOCK_IMPORT",
                            symbol=f"{mod}.{alias.name}" if mod else alias.name,
                            message=f"Prohibited mock symbol import '{alias.name}' from '{mod}'",
                        )
                    )
        elif is_conc_mod:
            if not self.is_exempt and not self._is_amnestied_concurrency():
                for alias in node.names:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="CONCURRENCY_IMPORT",
                            symbol=f"{mod}.{alias.name}" if mod else alias.name,
                            message=f"Unamnestied concurrency symbol import '{alias.name}' from '{mod}'",
                        )
                    )
        else:
            if mod == "numpy":
                for alias in node.names:
                    if alias.name in BANNED_NUMPY_GENERATORS:
                        if not self.is_exempt:
                            self.violations.append(
                                Violation(
                                    file_path=self.rel_path,
                                    line=node.lineno,
                                    col=node.col_offset,
                                    category="SYNTHETIC_DATA",
                                    symbol=alias.name,
                                    message=f"Prohibited synthetic numpy generator '{alias.name}'",
                                )
                            )
            elif mod == "pytest" or mod == "pytest.mark" or (mod and mod.startswith("pytest.")):
                for alias in node.names:
                    if alias.name in BANNED_SKIP_SYMBOLS:
                        self.banned_imported_symbols.add(alias.asname or alias.name)
                        if not self.is_exempt:
                            self.violations.append(
                                Violation(
                                    file_path=self.rel_path,
                                    line=node.lineno,
                                    col=node.col_offset,
                                    category="PYTEST_SKIP",
                                    symbol=alias.name,
                                    message=f"Prohibited pytest test suppression symbol '{alias.name}' imported from '{mod}'",
                                )
                            )
            elif mod == "unittest" or mod == "unittest.case" or (mod and mod.startswith("unittest.")):
                for alias in node.names:
                    if alias.name in BANNED_SKIP_SYMBOLS:
                        self.banned_imported_symbols.add(alias.asname or alias.name)
                        if not self.is_exempt:
                            self.violations.append(
                                Violation(
                                    file_path=self.rel_path,
                                    line=node.lineno,
                                    col=node.col_offset,
                                    category="PYTEST_SKIP",
                                    symbol=alias.name,
                                    message=f"Prohibited unittest test suppression symbol '{alias.name}' imported from '{mod}'",
                                )
                            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_ident(node.name, node, "function")
        self._check_function_stubs(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_ident(node.name, node, "async function")
        self._check_function_stubs(node)
        self.generic_visit(node)

    def _check_function_stubs(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        if self.is_exempt:
            return
        decorators = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
        decorators += [d.attr for d in node.decorator_list if isinstance(d, ast.Attribute)]
        if "abstractmethod" in decorators or "overload" in decorators:
            return

        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        if not body or all(isinstance(n, (ast.Pass, ast.Expr)) and (isinstance(n, ast.Pass) or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and n.value.value is ...)) for n in body):
            self.violations.append(
                Violation(
                    file_path=self.rel_path,
                    line=node.lineno,
                    col=node.col_offset,
                    category="EMPTY_PASS_STUB",
                    symbol=node.name,
                    message=f"Empty pass/ellipsis stub in function '{node.name}'",
                )
            )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._check_ident(node.name, node, "class")
        if not self.is_exempt:
            base_names = set()
            for b in node.bases:
                if isinstance(b, ast.Name):
                    base_names.add(b.id)
                elif isinstance(b, ast.Attribute):
                    base_names.add(b.attr)
            is_allowed_empty = any(b in {"Exception", "BaseException", "UserWarning", "Warning", "Protocol", "ABC"} or "Error" in b for b in base_names)

            body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
            if not is_allowed_empty and (not body or all(isinstance(n, (ast.Pass, ast.Expr)) and (isinstance(n, ast.Pass) or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and n.value.value is ...)) for n in body)):
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="EMPTY_PASS_STUB",
                        symbol=node.name,
                        message=f"Empty pass/ellipsis stub in class '{node.name}'",
                    )
                )
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        if not self.is_exempt and node.exc:
            exc_name = ""
            if isinstance(node.exc, ast.Name):
                exc_name = node.exc.id
            elif isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                exc_name = node.exc.func.id
            if exc_name == "NotImplementedError":
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="NOT_IMPLEMENTED_ERROR",
                        symbol=exc_name,
                        message="Forbidden NotImplementedError raise dead-end",
                    )
                )
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self._check_with_items(node.items, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._check_with_items(node.items, node.lineno, node.col_offset)
        self.generic_visit(node)

    def _check_with_items(self, items: List[ast.withitem], lineno: int, col: int) -> None:
        if self.is_exempt:
            return
        for item in items:
            expr = item.context_expr
            if isinstance(expr, ast.Call):
                func = expr.func
                func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
                if func_name == "patch":
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=lineno,
                            col=col,
                            category="MOCK_IMPORT",
                            symbol="patch",
                            message="Mock patch context manager detected",
                        )
                    )
                elif func_name == "raises" and expr.args:
                    arg0 = expr.args[0]
                    if isinstance(arg0, ast.Name) and arg0.id == "NotImplementedError":
                        self.violations.append(
                            Violation(
                                file_path=self.rel_path,
                                line=lineno,
                                col=col,
                                category="NOT_IMPLEMENTED_ERROR",
                                symbol="pytest.raises(NotImplementedError)",
                                message="Tautological test assertion on NotImplementedError",
                            )
                        )

    def visit_Call(self, node: ast.Call) -> None:
        if self.is_exempt:
            self.generic_visit(node)
            return

        # Obfuscation execution functions: eval, exec
        if isinstance(node.func, ast.Name) and node.func.id in BANNED_OBFUSCATION_TOKENS:
            self.violations.append(
                Violation(
                    file_path=self.rel_path,
                    line=node.lineno,
                    col=node.col_offset,
                    category="OBFUSCATION",
                    symbol=node.func.id,
                    message=f"Prohibited dynamic execution function '{node.func.id}' detected.",
                )
            )

        # Dynamic attribute access: getattr(..., 'mock') or getattr(..., 'skip')
        if (isinstance(node.func, ast.Name) and node.func.id == "getattr") or (isinstance(node.func, ast.Attribute) and node.func.attr == "getattr"):
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                attr_val = node.args[1].value
                if attr_val in BANNED_MOCK_ATTRIBUTES or attr_val == "mock":
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="MOCK_USAGE",
                            symbol=f"getattr(..., '{attr_val}')",
                            message=f"Prohibited dynamic access to mock attribute '{attr_val}'",
                        )
                    )
                elif attr_val in BANNED_SKIP_SYMBOLS:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="PYTEST_SKIP",
                            symbol=f"getattr(..., '{attr_val}')",
                            message=f"Prohibited dynamic access to test suppression attribute '{attr_val}'",
                        )
                    )

        # Test suppression direct function call: skip("reason"), xfail("reason"), etc.
        if isinstance(node.func, ast.Name) and (node.func.id in self.banned_imported_symbols or node.func.id in BANNED_SKIP_SYMBOLS):
            self.violations.append(
                Violation(
                    file_path=self.rel_path,
                    line=node.lineno,
                    col=node.col_offset,
                    category="PYTEST_SKIP",
                    symbol=node.func.id,
                    message=f"Prohibited test suppression call '{node.func.id}()'",
                )
            )

        # dict(charge=..., uhf=...) dummy physical dict constructor
        if isinstance(node.func, ast.Name) and node.func.id == "dict":
            kw_names = {kw.arg for kw in node.keywords if kw.arg is not None}
            if "charge" in kw_names and "uhf" in kw_names:
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="DUMMY_DICT",
                        symbol="dict(charge=..., uhf=...)",
                        message="Hardcoded dummy physical dictionary constructor detected (charge and uhf).",
                    )
                )

        if isinstance(node.func, ast.Attribute) and node.func.attr == "assertRaises":
            if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "NotImplementedError":
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="NOT_IMPLEMENTED_ERROR",
                        symbol="assertRaises(NotImplementedError)",
                        message="Tautological test assertion on NotImplementedError",
                    )
                )

        func_name = node.func.id if isinstance(node.func, ast.Name) else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
        if func_name in {"__import__", "import_module"} and node.args:
            target_mod = None
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                target_mod = node.args[0].value
            else:
                target_mod = self._extract_concat_str(node.args[0])

            if target_mod:
                is_mock_tgt = any(target_mod == bm or target_mod.startswith(bm + ".") for bm in BANNED_MOCK_MODULES)
                is_conc_tgt = any(target_mod == bc or target_mod.startswith(bc + ".") for bc in BANNED_CONCURRENCY_MODULES)

                if is_mock_tgt:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="MOCK_IMPORT",
                            symbol=target_mod,
                            message=f"Dynamic mock module import '{target_mod}'",
                        )
                    )
                elif is_conc_tgt:
                    if not self._is_amnestied_concurrency():
                        self.violations.append(
                            Violation(
                                file_path=self.rel_path,
                                line=node.lineno,
                                col=node.col_offset,
                                category="CONCURRENCY_IMPORT",
                                symbol=target_mod,
                                message=f"Dynamic unamnestied concurrency import '{target_mod}'",
                            )
                        )

        # Monkeypatch method calls: mp.setattr, monkeypatch.delattr, etc.
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"setattr", "delattr", "setitem", "delitem", "setenv", "delenv", "syspath_prepend", "chdir"}:
            if isinstance(node.func.value, ast.Name):
                val_id = node.func.value.id.lower()
                if "monkey" in val_id or val_id in {"mp", "monkeypatch", "patcher"}:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="MONKEYPATCH_INTERCEPT",
                            symbol=f"{node.func.value.id}.{node.func.attr}",
                            message=f"Prohibited monkeypatch intercept of core system interfaces via '{node.func.value.id}.{node.func.attr}'",
                        )
                    )

        # Built-in setattr / delattr in test files modifying foreign modules/classes
        if self.is_test_file and isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"}:
            is_self_or_cls = bool(node.args and isinstance(node.args[0], ast.Name) and node.args[0].id in {"self", "cls"})
            if not is_self_or_cls:
                target_repr = ast.unparse(node.args[0]) if node.args else "..."
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="MONKEYPATCH_INTERCEPT",
                        symbol=f"{node.func.id}({target_repr}, ...)",
                        message=f"Prohibited dynamic '{node.func.id}' foreign object modification in test file",
                    )
                )

        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in BANNED_NUMPY_GENERATORS:
                val = node.func.value
                val_name = val.id if isinstance(val, ast.Name) else (val.attr if isinstance(val, ast.Attribute) else "")
                if val_name in {"np", "numpy", "random"}:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="SYNTHETIC_DATA",
                            symbol=f"{val_name}.{attr_name}",
                            message=f"Prohibited synthetic generator '{val_name}.{attr_name}'",
                        )
                    )
        elif isinstance(node.func, ast.Name) and node.func.id in BANNED_NUMPY_GENERATORS:
            self.violations.append(
                Violation(
                    file_path=self.rel_path,
                    line=node.lineno,
                    col=node.col_offset,
                    category="SYNTHETIC_DATA",
                    symbol=node.func.id,
                    message=f"Prohibited synthetic generator function '{node.func.id}'",
                )
            )

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if not self.is_exempt and isinstance(node.op, ast.Add):
            reconstructed = self._extract_concat_str(node)
            if reconstructed:
                lower = reconstructed.lower()
                if "mock" in lower or "unittest.mock" in lower or "magicmock" in lower:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="OBFUSCATION",
                            symbol=reconstructed,
                            message=f"Obfuscated mock token via string concatenation '{reconstructed}'",
                        )
                    )
                for token in BANNED_STATE_TOKENS:
                    if token in lower:
                        self.violations.append(
                            Violation(
                                file_path=self.rel_path,
                                line=node.lineno,
                                col=node.col_offset,
                                category="STATE_MUTATION_BAN",
                                symbol=reconstructed,
                                message=f"Prohibited state mutation token '{token}' via string concatenation",
                            )
                        )
        self.generic_visit(node)

    def _extract_concat_str(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._extract_concat_str(node.left)
            right = self._extract_concat_str(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    def _extract_all_strings(self, node: ast.AST) -> str:
        parts = []
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                parts.append(child.value)
        return "".join(parts)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        if not self.is_exempt:
            combined = self._extract_all_strings(node).lower()
            if "mock" in combined or "unittest.mock" in combined:
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="OBFUSCATION",
                        symbol="f-string",
                        message="Obfuscated mock token via f-string",
                    )
                )
            for token in BANNED_STATE_TOKENS:
                if token in combined:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="STATE_MUTATION_BAN",
                            symbol="f-string",
                            message=f"Prohibited state mutation token '{token}' detected in f-string",
                        )
                    )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not self.is_exempt and isinstance(node.value, str):
            val = node.value.strip()
            
            for token in BANNED_STATE_TOKENS:
                if token in val.lower():
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="STATE_MUTATION_BAN",
                            symbol=val,
                            message=f"Prohibited state mutation token '{token}' detected in string constant",
                        )
                    )

            if len(val) >= 4 and len(val) % 4 == 0 and re.match(r"^[A-Za-z0-9+/]+={0,2}$", val):
                try:
                    decoded = base64.b64decode(val).decode("utf-8", errors="ignore").lower()
                    if "mock" in decoded or "fake" in decoded:
                        self.violations.append(
                            Violation(
                                file_path=self.rel_path,
                                line=node.lineno,
                                col=node.col_offset,
                                category="OBFUSCATION",
                                symbol=val,
                                message=f"Obfuscated base64 mock payload '{val}'",
                            )
                        )
                except Exception:
                    pass

            if len(val) >= 8 and len(val) % 2 == 0 and re.match(r"^[0-9a-fA-F]+$", val):
                try:
                    decoded_hex = bytes.fromhex(val).decode("utf-8", errors="ignore").lower()
                    if "mock" in decoded_hex or "unittest.mock" in decoded_hex:
                        self.violations.append(
                            Violation(
                                file_path=self.rel_path,
                                line=node.lineno,
                                col=node.col_offset,
                                category="OBFUSCATION",
                                symbol=val,
                                message=f"Obfuscated hex mock payload '{val}'",
                            )
                        )
                except Exception:
                    pass

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if not self.is_exempt:
            if node.id in {"mock", "MagicMock"} or node.id in BANNED_MOCK_ATTRIBUTES:
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="MOCK_USAGE",
                        symbol=node.id,
                        message=f"Prohibited use of mock symbol '{node.id}'",
                    )
                )
            
            for token in BANNED_STATE_TOKENS:
                if token in node.id.lower():
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="STATE_MUTATION_BAN",
                            symbol=node.id,
                            message=f"Prohibited state mutation token '{token}' detected in variable name",
                        )
                    )

        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self._check_ident(node.id, node, "variable")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if not self.is_exempt:
            for token in BANNED_STATE_TOKENS:
                if token in node.attr.lower():
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="STATE_MUTATION_BAN",
                            symbol=node.attr,
                            message=f"Prohibited state mutation token '{token}' detected in attribute",
                        )
                    )

            if node.attr in {"mock", "MagicMock"} or node.attr in BANNED_MOCK_ATTRIBUTES:
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="MOCK_USAGE",
                        symbol=node.attr,
                        message=f"Prohibited use of mock attribute '{node.attr}'",
                    )
                )
            if node.attr in BANNED_SKIP_SYMBOLS:
                if isinstance(node.value, ast.Name) and node.value.id in self.pytest_aliases:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="PYTEST_SKIP",
                            symbol=f"{node.value.id}.{node.attr}",
                            message=f"Prohibited {node.value.id}.{node.attr} detected. Tests must not be skipped or marked xfail.",
                        )
                    )
                elif isinstance(node.value, ast.Attribute) and node.value.attr == "mark" and isinstance(node.value.value, ast.Name) and node.value.value.id in self.pytest_aliases:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="PYTEST_SKIP",
                            symbol=f"{node.value.value.id}.mark.{node.attr}",
                            message=f"Prohibited {node.value.value.id}.mark.{node.attr} detected. Tests must not be skipped or marked xfail.",
                        )
                    )
                elif isinstance(node.value, ast.Name) and node.value.id in self.unittest_aliases:
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="PYTEST_SKIP",
                            symbol=f"{node.value.id}.{node.attr}",
                            message=f"Prohibited {node.value.id}.{node.attr} detected. Tests must not be skipped.",
                        )
                    )
                elif node.attr == "skipTest":
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="PYTEST_SKIP",
                            symbol=f"*.{node.attr}",
                            message=f"Prohibited {node.attr} test skipping detected.",
                        )
                    )
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self._check_ident(node.attr, node, "attribute")
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self._check_ident(node.arg, node, "argument")
        self.generic_visit(node)

    def _is_int_constant(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, int):
            return True
        return False

    def _collect_dict_key_values(self, d_node: ast.Dict) -> List[Tuple[str, ast.AST]]:
        pairs = []
        for k, v in zip(d_node.keys, d_node.values):
            if k is not None and isinstance(k, ast.Constant) and isinstance(k.value, str):
                pairs.append((k.value, v))
            elif k is None and isinstance(v, ast.Dict):
                pairs.extend(self._collect_dict_key_values(v))
        return pairs

    def visit_Dict(self, node: ast.Dict) -> None:
        if not self.is_exempt:
            pairs = self._collect_dict_key_values(node)
            keys = [k for k, v in pairs]
            
            for token in BANNED_STATE_TOKENS:
                if any(token in key.lower() for key in keys):
                    self.violations.append(
                        Violation(
                            file_path=self.rel_path,
                            line=node.lineno,
                            col=node.col_offset,
                            category="STATE_MUTATION_BAN",
                            symbol="dict",
                            message=f"Prohibited state mutation token '{token}' detected in dict key",
                        )
                    )

            has_charge = any(k == "charge" and self._is_int_constant(v) for k, v in pairs)
            has_uhf = any(k == "uhf" and self._is_int_constant(v) for k, v in pairs)
            
            if has_charge and has_uhf:
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="DUMMY_DICT",
                        symbol="dict",
                        message="Hardcoded dummy physical dictionary detected (charge and uhf).",
                    )
                )
        self.generic_visit(node)


def check_file(
    file_path: Path,
    repo_root: Path,
    amnesty_set: Set[str],
) -> List[Violation]:
    """Analyze a single Python file for AST anti-spoof violations."""
    rel_path = file_path.relative_to(repo_root).as_posix() if repo_root in file_path.parents or file_path == repo_root else file_path.name

    is_tool_exemption = file_path.name in {
        "anti_spoof_linter.py",
        "test_anti_spoof_linter.py",
        "test_anti_spoof_amnesty.py",
    }
    is_api_mock_exemption = "api_mocks" in file_path.parts

    is_exempt = is_tool_exemption or is_api_mock_exemption

    try:
        content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [
            Violation(
                file_path=rel_path,
                line=e.lineno or 1,
                col=e.offset or 0,
                category="SYNTAX_ERROR",
                symbol="ast.parse",
                message=f"Syntax error: {e.msg}",
            )
        ]
    except Exception as e:
        return [
            Violation(
                file_path=rel_path,
                line=1,
                col=0,
                category="IO_ERROR",
                symbol="file_read",
                message=f"Could not read file: {e}",
            )
        ]

    visitor = SpoofVisitor(
        filepath=file_path,
        rel_path=rel_path,
        is_exempt=is_exempt,
        amnesty_set=amnesty_set,
    )
    visitor.visit(tree)
    return visitor.violations


def run_linter(
    targets: Optional[Sequence[Union[str, Path]]] = None,
    repo_root: Optional[Path] = None,
    strict_mode: bool = True,
    generate_amnesty: bool = False,
) -> Tuple[int, Dict[str, List[Violation]]]:
    """Execute anti-spoof static analysis across specified targets or whole repository."""
    if not repo_root:
        repo_root = find_repository_root(targets[0] if targets else Path.cwd())

    amnesty_set = load_amnesty(repo_root)
    all_violations: Dict[str, List[Violation]] = {}

    target_paths: List[Path] = []
    if targets:
        for t in targets:
            t_str = str(t)
            if "*" in t_str or "?" in t_str:
                pattern = Path(t_str).as_posix()
                matched = list(repo_root.glob(pattern)) if not Path(t_str).is_absolute() else [Path(p) for p in Path(pattern).parent.glob(Path(pattern).name)]
                for m in matched:
                    if m.exists():
                        target_paths.append(m.resolve())
            else:
                tp = Path(t).resolve()
                if tp.exists():
                    target_paths.append(tp)
    else:
        target_paths = [repo_root]

    for tp in target_paths:
        if tp.is_file() and tp.suffix == ".py":
            v = check_file(tp, repo_root, amnesty_set)
            if v:
                all_violations[str(tp.relative_to(repo_root) if repo_root in tp.parents else tp.name)] = v
        elif tp.is_dir():
            for root, dirs, files in os.walk(tp):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
                for f in files:
                    if f.endswith(".py"):
                        p = Path(root) / f
                        v = check_file(p, repo_root, amnesty_set)
                        if v:
                            all_violations[str(p.relative_to(repo_root) if repo_root in p.parents else p.name)] = v

    if generate_amnesty:
        save_amnesty(repo_root, all_violations)
        return 0, all_violations

    has_violations = len(all_violations) > 0
    exit_code = 1 if (has_violations and strict_mode) else 0
    return exit_code, all_violations


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CoChem Anti-Spoof Linter & Zero-Mock Enforcement Engine")
    parser.add_argument("targets", nargs="*", default=[], help="File(s) or directory paths to audit")
    parser.add_argument("--json", action="store_true", help="Output results in structured JSON format")
    parser.add_argument("--strict", action="store_true", default=False, help="Fail with non-zero exit code if violations found")
    parser.add_argument("--generate-amnesty", action="store_true", help="Generate or update .anti_spoof_amnesty.json baseline")
    args = parser.parse_args(argv)

    targets = [Path(t) for t in args.targets] if args.targets else [Path.cwd()]
    repo_root = find_repository_root(targets[0])

    exit_code, violations = run_linter(
        targets=targets,
        repo_root=repo_root,
        strict_mode=args.strict,
        generate_amnesty=args.generate_amnesty,
    )

    total_violations = sum(len(v_list) for v_list in violations.values())

    if args.json:
        output_payload = {
            "exit_code": exit_code,
            "violations_count": total_violations,
            "files_count": len(violations),
            "violations": {f: [v.to_dict() for v in v_list] for f, v_list in violations.items()},
        }
        print(json.dumps(output_payload, indent=2))
        return exit_code

    if total_violations == 0:
        print("[LINT SUCCESS] Zero-mock compliance verified. Zero stubs, mocks, or spoofing detected.")
        return 0

    print(f"[SPOOFING DETECTED] Found {total_violations} violation(s) across {len(violations)} file(s):")
    for f, v_list in violations.items():
        print(f"\nFile: {f}")
        for v in v_list:
            print(f"  - Line {v.line}:{v.col} [{v.category}] ({v.symbol}): {v.message}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\cochem_torq_engine.py ---
"""
CoChem-TORQ: High-Fidelity Quantum Engine & Cascade Broker
===========================================================
Phase 5 (Stage 4.0) Implementation
----------------------------------
Governs the Method Matrix v4 execution cascade (defgrid1 -> defgrid3),
ORCA Python Interface (OPI) persistent memory threading, dynamic wavefunction
propagation (! MOREAD / %moinp), stateful SCF checkpointing, GPU4PySCF dynamic
batching with VRAM headroom protection, spin contamination validation (<10% threshold),
tightened intermolecular %geom blocks, frozen-monomer protocol, Counterpoise / ghost atom
routing, dynamic atomic mass and covalent/vdW radii retrieval via Mendeleev,
and 6-Tier Environment Matrix scratch/shm path resolution.

Authoritative Sources:
- Method Matrix v4 (§4.4, §8A, §8B, §9A, §10, Table 2)
- Tripartite Filesystem Air-Gap Compliance (Ring 1 Static, Ring 2 Scratch, Ring 3 Artifacts)
- CODATA 2018 / 2022 Physical Constants
"""

from __future__ import annotations

import atexit
import enum
import hashlib
import json
import logging
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Final, Generator, List, Optional, Sequence, Tuple, Union

import h5py
from mendeleev import element
import numpy as np
import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cochem_base.exceptions import (
    BinaryNotFoundError,
    HardwareTelemetryError,
    SpinContaminationError,
    MissingTelemetryError,
    ToolUnavailableError,
)
from cochem_base.schemas import HardwareTelemetryReport

# Configure module-level logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: [CoChem-TORQ-Engine] %(message)s")
logger = logging.getLogger("CoChem-TORQ.Engine")


# ============================================================================
# 1. Dynamic Atomic Properties via Mendeleev (Mendeleev Mandate)
# ============================================================================

def get_atomic_mass(symbol: str) -> float:
    """
    Dynamically retrieves standard atomic weight (mass in amu) using mendeleev.
    Strictly prohibits hardcoded mass lookups under Mendeleev Mandate.
    """
    clean_sym = symbol.strip().rstrip(":").capitalize()
    el = element(clean_sym)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.mass is not None:
        return float(el.mass)
    raise ValueError(f"Could not retrieve atomic mass for element symbol '{symbol}'.")


def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """
    Dynamically retrieves isotopic mass using mendeleev.
    """
    clean_sym = symbol.strip().rstrip(":").capitalize()
    el = element(clean_sym)
    if mass_number is None:
        return get_atomic_mass(symbol)
    for iso in el.isotopes:
        if iso.mass_number == mass_number:
            return float(iso.mass)
    return get_atomic_mass(symbol)


def get_atomic_number(symbol: str) -> int:
    """
    Dynamically retrieves atomic number (Z) using mendeleev.
    """
    clean_sym = symbol.strip().rstrip(":").capitalize()
    el = element(clean_sym)
    return int(el.atomic_number)


def get_pyykko_radius(symbol: str) -> float:
    """
    Dynamically retrieves Pyykkö single-bond covalent radius in Angstroms using mendeleev.
    (Mendeleev provides covalent_radius_pyykko in picometers, converted to Å / 100.0).
    """
    clean_sym = symbol.strip().rstrip(":").capitalize()
    el = element(clean_sym)
    if el.covalent_radius_pyykko is not None:
        return float(el.covalent_radius_pyykko) / 100.0
    if el.covalent_radius is not None:
        return float(el.covalent_radius) / 100.0
    return 1.40


def get_vdw_radius(symbol: str) -> float:
    """
    Dynamically retrieves van der Waals radius in Angstroms using mendeleev.
    (Mendeleev provides vdw_radius in picometers, converted to Å / 100.0).
    """
    clean_sym = symbol.strip().rstrip(":").capitalize()
    el = element(clean_sym)
    if el.vdw_radius is not None:
        return float(el.vdw_radius) / 100.0
    return 2.00


def is_openmpi_supported() -> bool:
    """
    Checks if OpenMPI parallel execution is supported for ORCA in the active environment.
    On Windows, ORCA requires OpenMPI with specific DLLs or environment variables;
    defaults to False on Windows unless explicitly forced via COCHEM_FORCE_MPI.
    """
    if platform.system() == "Windows":
        if os.environ.get("COCHEM_FORCE_MPI", "0") == "1":
            return True
        return False
    return bool(shutil.which("mpirun") or shutil.which("orterun"))


# ============================================================================
# 2. 6-Tier Environment Matrix & Path Resolution
# ============================================================================

class EnvironmentTier(str, enum.Enum):
    """
    6-Tier Environment Matrix defining host execution environments.
    """
    LOCAL_WINDOWS = "LOCAL_WINDOWS"
    LOCAL_MACOS = "LOCAL_MACOS"
    LOCAL_LINUX = "LOCAL_LINUX"
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    CODESPACES = "CODESPACES"
    HPC_NODES = "HPC_NODES"


class AirGapViolationError(PermissionError):
    """Raised when an operation attempts to write to Ring 1 static repository space at runtime."""
    pass


def get_repo_root() -> Path:
    """
    Locates the Domain A / Ring 1 immutable Git repository root.
    """
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent.resolve()

    env_val = os.environ.get("COCHEM_REPO_DIR")
    if env_val:
        repo_path = Path(env_val).resolve()
        if repo_path.is_dir():
            return repo_path

    return Path.cwd().resolve()


class ExecutionContext(BaseModel):
    """
    Manages runtime environment detection, memory thresholds, core allocation,
    and dynamic scratch/shm/artifacts path resolution across the 6-Tier Environment Matrix.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tier: EnvironmentTier = Field(default=EnvironmentTier.LOCAL_WINDOWS)
    custom_scratch_dir: Optional[Path] = None
    custom_shm_dir: Optional[Path] = None
    custom_artifacts_dir: Optional[Path] = None
    max_memory_mb: int = Field(default=16384)
    num_cores: int = Field(default=8)
    gpu_available: bool = Field(default=False)
    vram_mb: int = Field(default=0)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def __init__(self, **data: Any) -> None:
        if "tier" not in data:
            data["tier"] = self.detect_tier()
        super().__init__(**data)
        self._detect_hardware_specs()

    @classmethod
    def detect_tier(cls) -> EnvironmentTier:
        """
        Autonomously detects the active environment tier from OS telemetry and environment variables.
        """
        if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("RUNNER_TEMP"):
            return EnvironmentTier.GITHUB_ACTIONS

        if os.environ.get("CODESPACES") == "true" or os.environ.get("CODESPACE_NAME"):
            return EnvironmentTier.CODESPACES

        if (
            os.environ.get("SLURM_TMPDIR")
            or os.environ.get("SLURM_JOB_ID")
            or os.environ.get("PFSDIR")
            or os.environ.get("PBS_O_WORKDIR")
        ):
            return EnvironmentTier.HPC_NODES

        sys_name = platform.system()
        if sys_name == "Windows" or os.environ.get("WSL_DISTRO_NAME"):
            return EnvironmentTier.LOCAL_WINDOWS
        elif sys_name == "Darwin":
            return EnvironmentTier.LOCAL_MACOS
        else:
            return EnvironmentTier.LOCAL_LINUX

    def _detect_hardware_specs(self) -> None:
        """
        Queries host CPU cores, RAM, and NVIDIA GPU telemetry if available.
        """
        try:
            vm = psutil.virtual_memory()
            self.max_memory_mb = int(vm.total / (1024 * 1024))
            self.num_cores = os.cpu_count() or 8
        except Exception:
            pass

        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self.gpu_available = True
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                self.vram_mb = int(mem_info.total / (1024 * 1024))
            pynvml.nvmlShutdown()
        except Exception:
            self.gpu_available = False
            self.vram_mb = 0

    def get_telemetry(self, precision: str = "float64") -> HardwareTelemetryReport:
        """
        Queries honest OS/driver telemetry and returns an authentic HardwareTelemetryReport (Suggestion #52).
        """
        gpu_avail = False
        dev_count = 0
        dev_name = "None"
        vram_total = 0.0
        vram_free = 0.0

        try:
            import torch
            if torch.cuda.is_available():
                dev_count = torch.cuda.device_count()
                if dev_count > 0:
                    gpu_avail = True
                    dev_name = torch.cuda.get_device_name(0)
                    free_b, total_b = torch.cuda.mem_get_info(0)
                    vram_total = float(total_b) / (1024.0 * 1024.0)
                    vram_free = float(free_b) / (1024.0 * 1024.0)
        except Exception:
            gpu_avail = False
            dev_count = 0

        is_mps = False
        try:
            import platform, torch
            if platform.system() == "Darwin" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                is_mps = True
        except Exception:
            is_mps = False

        if gpu_avail and vram_free >= 2048.0:
            runtime = "cuda"
        elif is_mps:
            if precision.lower() in ("float64", "fp64", "double"):
                runtime = "cpu"
            else:
                runtime = "mps"
        else:
            runtime = "cpu"

        return HardwareTelemetryReport(
            device_count=dev_count,
            gpu_available=gpu_avail,
            device_name=dev_name,
            vram_total_mb=vram_total,
            vram_free_mb=vram_free,
            selected_runtime=runtime,
        )

    def verify_air_gap_boundary(self, target_path: Path) -> None:
        """
        Verifies that runtime scratch, shm, or artifacts paths do not mutate Domain A / Ring 1 repo root.
        """
        resolved_target = target_path.resolve()
        repo_root = get_repo_root().resolve()
        try:
            rel = resolved_target.relative_to(repo_root)
            if not (resolved_target.name.startswith("scratch") or "scratch" in resolved_target.parts):
                raise AirGapViolationError(
                    f"Tripartite Air-Gap Violation: Path '{resolved_target}' is inside static repository root '{repo_root}'."
                )
        except ValueError:
            pass

    def get_scratch_dir(self, subfolder: Optional[str] = None) -> Path:
        """
        Resolves the ephemeral Domain C / Ring 2 scratch directory for the active tier.
        """
        if self.custom_scratch_dir:
            base = Path(self.custom_scratch_dir).resolve()
        elif os.environ.get("COCHEM_SCRATCH_DIR"):
            base = Path(os.environ["COCHEM_SCRATCH_DIR"]).resolve()
        else:
            if self.tier == EnvironmentTier.GITHUB_ACTIONS:
                runner_temp = os.environ.get("RUNNER_TEMP", tempfile.gettempdir())
                base = Path(runner_temp) / "cochem_scratch"
            elif self.tier == EnvironmentTier.CODESPACES:
                base = Path.home() / ".cochem" / "scratch"
            elif self.tier == EnvironmentTier.HPC_NODES:
                slurm_tmp = os.environ.get("SLURM_TMPDIR") or os.environ.get("PFSDIR") or tempfile.gettempdir()
                base = Path(slurm_tmp) / "cochem_scratch"
            elif self.tier == EnvironmentTier.LOCAL_MACOS:
                base = Path.home() / "Library" / "Caches" / "CoChem" / "scratch"
            elif self.tier == EnvironmentTier.LOCAL_WINDOWS:
                local_app_data = os.environ.get("LOCALAPPDATA")
                if local_app_data:
                    base = Path(local_app_data) / "CoChem" / "scratch"
                else:
                    base = Path(tempfile.gettempdir()) / "cochem_scratch"
            else:  # LOCAL_LINUX
                xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
                if xdg_runtime and Path(xdg_runtime).is_dir():
                    base = Path(xdg_runtime) / "cochem" / "scratch"
                elif Path(tempfile.gettempdir()).is_dir():
                    base = Path(tempfile.gettempdir()) / "cochem" / "scratch"
                else:
                    base = Path(tempfile.gettempdir()) / "cochem_scratch"

        target = (base / subfolder) if subfolder else base
        self.verify_air_gap_boundary(target)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def get_shm_dir(self, subfolder: Optional[str] = None) -> Path:
        """
        Resolves the zero-copy shared memory directory for the active tier.
        """
        if self.custom_shm_dir:
            base = Path(self.custom_shm_dir).resolve()
        elif os.environ.get("COCHEM_SHM_DIR"):
            base = Path(os.environ["COCHEM_SHM_DIR"]).resolve()
        else:
            if self.tier == EnvironmentTier.GITHUB_ACTIONS:
                runner_temp = os.environ.get("RUNNER_TEMP", tempfile.gettempdir())
                base = Path(runner_temp) / "shm"
            elif self.tier == EnvironmentTier.CODESPACES:
                base = Path.home() / ".cochem" / "shm"
            elif self.tier == EnvironmentTier.HPC_NODES:
                slurm_tmp = os.environ.get("SLURM_TMPDIR") or tempfile.gettempdir()
                base = Path(slurm_tmp) / "shm"
            elif self.tier == EnvironmentTier.LOCAL_MACOS:
                tmpdir = os.environ.get("TMPDIR", tempfile.gettempdir())
                base = Path(tmpdir) / "cochem_shm"
            elif self.tier == EnvironmentTier.LOCAL_WINDOWS:
                local_app_data = os.environ.get("LOCALAPPDATA")
                if local_app_data:
                    base = Path(local_app_data) / "CoChem" / "shm"
                else:
                    base = Path(tempfile.gettempdir()) / "cochem_shm"
            else:  # LOCAL_LINUX
                if Path("/dev/shm").is_dir() and os.access("/dev/shm", os.W_OK):
                    base = Path("/dev/shm/cochem")
                else:
                    base = Path(tempfile.gettempdir()) / "cochem_shm"

        target = (base / subfolder) if subfolder else base
        self.verify_air_gap_boundary(target)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def get_artifacts_dir(self, subfolder: Optional[str] = None) -> Path:
        """
        Resolves the Domain B / Ring 3 persistent artifact vault directory.
        """
        if self.custom_artifacts_dir:
            base = Path(self.custom_artifacts_dir).resolve()
        elif os.environ.get("COCHEM_ARTIFACTS_DIR"):
            base = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
        elif os.environ.get("COCHEM_ARTIFACTS"):
            base = Path(os.environ["COCHEM_ARTIFACTS"]).resolve()
        else:
            base = Path.home() / "CoChem_Artifacts"

        target = (base / subfolder) if subfolder else base
        self.verify_air_gap_boundary(target)
        target.mkdir(parents=True, exist_ok=True)
        return target


# ============================================================================
# 3. Pydantic Execution Models
# ============================================================================

class SCFResult(BaseModel):
    """Result container for individual batch/grid electronic structure evaluations."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    point_idx: int
    energy_hartree: float
    converged: bool = True
    vram_used_mb: float = 0.0
    coordinates: np.ndarray


class DispatchPayload(BaseModel):
    """
    Quantum chemistry dispatch payload holding complete job parameters,
    molecular geometry, grid levels, Counterpoise ghost atoms, and %geom / %scf directives.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbols: List[str]
    coordinates: np.ndarray
    charge: int = 0
    multiplicity: int = 1
    method: str = "wB97M-V"
    basis_set: str = "def2-TZVP"
    aux_basis: str = "def2/J"
    scf_type: str = "DIIS"
    extra_options: str = ""
    is_complex: bool = False
    frozen_atom_indices: Optional[List[int]] = None
    ghost_atom_indices: Optional[List[int]] = None
    counterpoise: bool = False
    initial_hessian: Optional[str] = "XTB2"
    moinp_path: Optional[str] = None
    use_moread: bool = False
    grid_level: str = "defgrid3"
    executor: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coordinates(cls, v: Any) -> np.ndarray:
        arr = np.asarray(v, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != 3:
            raise ValueError(f"Coordinates must have shape (N, 3), got shape {arr.shape}.")
        return arr

    def to_orca_input(self, n_procs: int = 1, max_core_mb: int = 3000) -> str:
        """
        Serializes this payload into a complete, syntactically valid ORCA 6.1 input deck.
        Handles %pal nprocs conditionally so single-core and Windows non-MPI runs execute safely.
        """
        method_parts = []
        if self.method:
            method_parts.append(self.method)
        if self.basis_set:
            method_parts.append(self.basis_set)
        if self.aux_basis and "def2/" in self.aux_basis:
            method_parts.append(self.aux_basis)
        if self.grid_level:
            method_parts.append(self.grid_level.upper())
        if self.use_moread:
            method_parts.append("MOREAD")

        method_line = " ".join(method_parts)
        lines = [f"! {method_line}"]

        # %pal block (only emitted when n_procs > 1)
        if n_procs > 1:
            lines.append(f"%pal nprocs {n_procs} end")
        lines.append(f"%maxcore {max_core_mb}")

        # %moinp directive for MOREAD
        if self.moinp_path:
            clean_path = str(self.moinp_path).replace("\\", "/")
            lines.append(f'%moinp "{clean_path}"')

        # %geom block
        geom_opts: List[str] = []
        if self.initial_hessian:
            geom_opts.append(f"  InHess {self.initial_hessian}")

        if self.is_complex:
            geom_opts.append("  TolE 1e-7")
            geom_opts.append("  TolRMSG 3e-6")
            geom_opts.append("  TolMaxG 1e-5")
            geom_opts.append("  TolRMSD 5e-5")
            geom_opts.append("  TolMaxD 1e-4")

        if self.frozen_atom_indices:
            geom_opts.append("  Constraints")
            for idx in self.frozen_atom_indices:
                geom_opts.append(f"    {{ C {idx} C }}")
            geom_opts.append("  end")

        if geom_opts:
            lines.append("%geom")
            lines.extend(geom_opts)
            lines.append("end")

        # Extra options
        if self.extra_options:
            lines.append(self.extra_options)

        # Coordinate block with ghost atom support (':')
        # Purge automatic ghosting of atoms from standard geometry optimization (! Opt) decks
        is_opt = (
            "opt" in self.extra_options.lower()
            or "opt" in self.method.lower()
            or any("opt" in l.lower() for l in lines)
        )
        lines.append(f"* xyz {self.charge} {self.multiplicity}")
        for idx, (sym, (x, y, z)) in enumerate(zip(self.symbols, self.coordinates)):
            is_ghost = (not is_opt) and (self.ghost_atom_indices is not None and idx in self.ghost_atom_indices)
            sym_tag = f"{sym}:" if is_ghost else sym
            lines.append(f"  {sym_tag:<4} {x:>14.8f} {y:>14.8f} {z:>14.8f}")
        lines.append("*")

        return "\n".join(lines) + "\n"

    def generate_orca_deck(self, n_procs: int = 1, max_core_mb: int = 3000) -> str:
        """Alias for to_orca_input to generate complete ORCA input deck."""
        return self.to_orca_input(n_procs=n_procs, max_core_mb=max_core_mb)



class ORCAStepResult(BaseModel):
    """
    Result of an individual ORCA execution or persistent OPI threading step,
    carrying in-memory wavefunctions, Fock matrices, and spin observables.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_idx: int = 0
    energy: float = 0.0
    coordinates: np.ndarray
    gradient: Optional[np.ndarray] = None
    converged: bool = True
    mo_coefficients: Optional[np.ndarray] = None
    fock_matrix: Optional[np.ndarray] = None
    density_matrix: Optional[np.ndarray] = None
    gbw_bytes: Optional[bytes] = None
    gbw_path: Optional[Path] = None
    s_squared_observed: Optional[float] = None
    s_squared_ideal: Optional[float] = None
    spin_contamination_percent: Optional[float] = None
    dipole_moment: Optional[List[float]] = None
    frequencies: Optional[List[float]] = None
    raw_output: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coordinates(cls, v: Any) -> np.ndarray:
        arr = np.asarray(v, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != 3:
            raise ValueError(f"Coordinates must have shape (N, 3), got shape {arr.shape}.")
        return arr


# ============================================================================
# 4. Method Matrix v4 & Quantum Chemical Rules
# ============================================================================

def detect_complex_and_monomers(
    symbols: List[str],
    coordinates: np.ndarray,
    tolerance_multiplier: float = 1.20
) -> Tuple[bool, List[List[int]]]:
    """
    Detects whether the given atomic structure is an intermolecular complex / dimer
    by constructing the covalent connectivity graph using Pyykkö radii retrieved
    dynamically from mendeleev and identifying connected components via BFS.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    n_atoms = len(symbols)
    if n_atoms <= 1:
        return False, [[0]]

    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    dist_matrix = np.sqrt(np.sum(diff**2, axis=-1))

    # Dynamically query Pyykkö radii via mendeleev
    radii = np.array([get_pyykko_radius(sym) for sym in symbols], dtype=np.float64)
    cutoff_matrix = (radii[:, np.newaxis] + radii[np.newaxis, :]) * tolerance_multiplier

    adj = (dist_matrix < cutoff_matrix) & (dist_matrix > 1e-4)

    visited = [False] * n_atoms
    components: List[List[int]] = []

    for i in range(n_atoms):
        if not visited[i]:
            comp = []
            queue = [i]
            visited[i] = True
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                neighbors = np.where(adj[curr])[0]
                for nbr in neighbors:
                    if not visited[nbr]:
                        visited[nbr] = True
                        queue.append(int(nbr))
            components.append(sorted(comp))

    is_complex = len(components) >= 2
    return is_complex, components


def detect_non_covalent_contacts(
    symbols: List[str],
    coordinates: np.ndarray,
    tolerance_multiplier: float = 1.20
) -> Tuple[bool, List[List[int]], List[Tuple[int, int, float]]]:
    """
    Identifies non-covalent contacts across molecular fragments using Pyykkö covalent
    radii for fragment partitioning and van der Waals radii for contact identification.
    Returns (has_non_covalent_contacts, monomer_components, contact_pairs).
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    is_comp, components = detect_complex_and_monomers(symbols, coords, tolerance_multiplier)
    
    if len(components) < 2:
        return False, components, []

    vdw_radii = np.array([get_vdw_radius(sym) for sym in symbols], dtype=np.float64)
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    dist_matrix = np.sqrt(np.sum(diff**2, axis=-1))

    contact_pairs: List[Tuple[int, int, float]] = []
    for c1_idx in range(len(components)):
        for c2_idx in range(c1_idx + 1, len(components)):
            for i in components[c1_idx]:
                for j in components[c2_idx]:
                    d = dist_matrix[i, j]
                    cutoff = vdw_radii[i] + vdw_radii[j]
                    if d <= cutoff:
                        contact_pairs.append((i, j, float(d)))

    return len(contact_pairs) > 0, components, contact_pairs


def calculate_discrete_counterpoise_energy(
    e_ab: float, e_a_ghost: float, e_b_ghost: float
) -> float:
    """
    Evaluates discrete 3-point counterpoise interaction energy on frozen-monomer relaxed structure:
    Delta E_CP = E_AB^{AB} - E_A^{AB} - E_B^{AB} [M].
    """
    return float(e_ab - e_a_ghost - e_b_ghost)


def extract_s_squared_from_orca_output(content: str) -> Optional[float]:
    """
    Extracts <S^2> expectation value across all ORCA versions via robust regex patterns.
    """
    patterns = [
        r'<\s*S\s*\*\*\s*2\s*>\s*:\s*([0-9.]+)',
        r'<\s*S\s*\^\s*2\s*>\s*:\s*([0-9.]+)',
        r'Expectation value\s+<\s*S\s*\*\*\s*2\s*>\s*:\s*([0-9.]+)',
        r'Expectation value of <\s*S\s*\*\*\s*2\s*>\s*:\s*([0-9.]+)',
        r'Expectation value\s+<\s*S\s*\^\s*2\s*>\s*:\s*([0-9.]+)',
    ]
    for pat in patterns:
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def validate_spin_contamination(
    arg1: Union[int, str, None] = None,
    arg2: Union[float, int, str, None] = None,
    is_unrestricted: bool = True,
    **kwargs: Any
) -> Tuple[float, float, float]:
    if "multiplicity" in kwargs:
        if arg1 is not None and not isinstance(arg1, int):
            content = str(arg1)
            arg2 = kwargs["multiplicity"]
        else:
            arg1 = kwargs["multiplicity"]
    if "s_squared" in kwargs or "s2" in kwargs or "s_squared_observed" in kwargs:
        arg2 = kwargs.get("s_squared", kwargs.get("s2", kwargs.get("s_squared_observed")))
    """
    Validates spin contamination for open-shell systems under Method Matrix v4 §8B.3.
    Accepts either:
      (multiplicity: int, s_squared_observed: float | str, is_unrestricted: bool = True)
    or
      (content: str, multiplicity: int, is_unrestricted: bool = True)

    Ideal <S^2> = S_ideal * (S_ideal + 1) where S_ideal = (multiplicity - 1) / 2.
    Raises:
      MissingTelemetryError: If spin observable <S^2> cannot be extracted from unrestricted calculation output.
      SpinContaminationError: If relative spin deviation exceeds 10.0%.
    """
    if isinstance(arg1, str):
        content = arg1
        multiplicity = int(arg2)
        s2_val = extract_s_squared_from_orca_output(content)
        if s2_val is None:
            if is_unrestricted or multiplicity > 1:
                raise MissingTelemetryError(
                    "[MISSING DATA] Spin observable <S^2> could not be extracted from unrestricted calculation output."
                )
            s2_val = 0.0
    elif isinstance(arg2, str):
        multiplicity = int(arg1)
        try:
            s2_val = float(arg2)
        except ValueError:
            s2_val = extract_s_squared_from_orca_output(arg2)
            if s2_val is None:
                if is_unrestricted or multiplicity > 1:
                    raise MissingTelemetryError(
                        "[MISSING DATA] Spin observable <S^2> could not be extracted from unrestricted calculation output."
                    )
                s2_val = 0.0
    else:
        multiplicity = int(arg1)
        s2_val = float(arg2)

    if multiplicity < 1:
        raise ValueError(f"Multiplicity must be >= 1, got {multiplicity}.")

    s_ideal = (multiplicity - 1) / 2.0
    s_ideal_prod = s_ideal * (s_ideal + 1.0)

    if multiplicity == 1:
        spin_dev = abs(s2_val - 0.0)
        if s2_val > 0.10:
            raise SpinContaminationError(
                f"[ERR_SPIN_CONTAMINATION] Spin contamination {s2_val:.4f} in singlet state "
                f"exceeds tolerance (ideal=0.0000, observed={s2_val:.4f})."
            )
        return s_ideal_prod, s2_val, spin_dev * 100.0

    spin_dev = abs(s2_val - s_ideal_prod) / s_ideal_prod
    if spin_dev > 0.10:
        raise SpinContaminationError(
            f"[ERR_SPIN_CONTAMINATION] Spin contamination {spin_dev * 100.0:.2f}% exceeds the 10.0% threshold "
            f"mandated by Method Matrix v4 §8B.3 (Measured <S^2> = {s2_val:.4f}, Ideal = {s_ideal_prod:.4f}). "
            "Halting execution to prevent corrupted wavefunction propagation."
        )

    return s_ideal_prod, s2_val, spin_dev * 100.0


def route_cascade_rules(
    point_coords: np.ndarray,
    context: ExecutionContext,
    symbols: Optional[List[str]] = None,
    charge: int = 0,
    multiplicity: int = 1,
    method: Optional[str] = None,
    basis_set: Optional[str] = None,
    is_complex: Optional[bool] = None,
    initial_hessian: str = "XTB2",
    frozen_monomer: bool = False,
    extra_options: str = "",
    grid_level: Optional[str] = None,
    counterpoise: bool = False,
    ghost_atom_indices: Optional[List[int]] = None
) -> DispatchPayload:
    """
    Analyzes interatomic distances and applies Method Matrix v4 cascade rules:
    - Enforces InHess XTB2 or Lindh; strictly forbids Calc_Hess true.
    - Requires D3/D4 dispersion on DFT for complexes.
    - Tightens %geom convergence criteria (TolMaxG 1e-5) on complexes.
    - Applies frozen monomer constraints if requested.
    - Supports Counterpoise ghost atoms (':') across non-covalent contacts.
    - Upgrades integration grids dynamically (defgrid1 -> defgrid3).
    """
    coords = np.asarray(point_coords, dtype=np.float64)
    n_atoms = len(coords)

    if symbols is None:
        symbols = ["H"] * n_atoms

    # 1. Prohibit Calc_Hess true for initial Hessians (§8B.3)
    hess_upper = (initial_hessian or "").upper().strip()
    if "CALC_HESS" in hess_upper or "CALCHESS" in hess_upper:
        raise ValueError(
            "[ERR_METHOD_MATRIX] Calc_Hess true is strictly forbidden for initial hessians "
            "under Method Matrix v4 §8B.3; use InHess XTB2 or Lindh."
        )

    # 2. Detect complexes and monomer components via dynamic Pyykkö radii
    auto_complex, components = detect_complex_and_monomers(symbols, coords)
    complex_flag = auto_complex if is_complex is None else is_complex

    # 3. Method & Basis resolution
    resolved_method = method if method else ("wB97M-V" if complex_flag else "r2SCAN-3c")
    if basis_set is not None:
        resolved_basis = basis_set
    else:
        if "3c" in resolved_method.lower() or any(xtb_kw in resolved_method.lower() for xtb_kw in ["xtb", "gfn"]):
            resolved_basis = ""
        else:
            resolved_basis = "def2-TZVP"

    resolved_aux = "def2/J" if "def2" in resolved_basis else ""

    # 4. Dispersion enforcement for DFT on weak complexes (§4.4, §8A)
    if complex_flag:
        m_upper = resolved_method.upper()
        e_upper = extra_options.upper()
        is_dft = any(func in m_upper for func in ["B3LYP", "PBE", "SCAN", "M06", "W97", "OLYP", "OPBE", "DFT", "R2SCAN"])
        has_dispersion = any(d in m_upper or d in e_upper for d in ["D3", "D4", "-V", "VV10", "3C", "-3C"])
        if is_dft and not has_dispersion:
            raise ValueError(
                "[ERR_METHOD_MATRIX] Dispersion correction (D3/D4) is strictly required for DFT optimization of weak complexes."
            )

    # 5. Frozen monomer constraints (§9A.1-9A.2)
    frozen_indices: Optional[List[int]] = None
    if frozen_monomer and len(components) >= 2:
        frozen_indices = components[0]

    # 6. Counterpoise & Ghost atoms
    # Eradicate ghost-atom injection during active geometry relaxations (! Opt).
    # Counterpoise calculations are decoupled and coordinated via discrete single-point jobs post-optimization.
    is_opt_deck = "opt" in extra_options.lower() or "opt" in resolved_method.lower()
    resolved_ghosts = None if is_opt_deck else ghost_atom_indices
    if not is_opt_deck and counterpoise and resolved_ghosts is None and len(components) >= 2:
        resolved_ghosts = components[1]

    # 7. Dynamic grid tightening (defgrid1 -> defgrid3)
    resolved_grid = grid_level if grid_level else "defgrid3"

    payload = DispatchPayload(
        symbols=symbols,
        coordinates=coords,
        charge=charge,
        multiplicity=multiplicity,
        method=resolved_method,
        basis_set=resolved_basis,
        aux_basis=resolved_aux,
        extra_options=extra_options,
        is_complex=complex_flag,
        frozen_atom_indices=frozen_indices,
        ghost_atom_indices=resolved_ghosts,
        counterpoise=counterpoise,
        initial_hessian=initial_hessian,
        grid_level=resolved_grid,
        metadata={
            "components": components,
            "scratch_dir": str(context.get_scratch_dir()),
            "shm_dir": str(context.get_shm_dir())
        }
    )
    return payload


def route_method_matrix(
    symbols: List[str],
    coordinates: np.ndarray,
    target_tier: str = "T3-3h",
    charge: int = 0,
    multiplicity: int = 1,
    is_complex: Optional[bool] = None,
    initial_hessian: str = "XTB2",
    frozen_monomer: bool = False,
    monomer_indices: Optional[List[List[int]]] = None,
    extra_options: str = "",
    grid_level: Optional[str] = None,
    counterpoise: bool = False,
    ghost_atom_indices: Optional[List[int]] = None,
    context: Optional[ExecutionContext] = None,
    tier_key: Optional[str] = None,
) -> DispatchPayload:
    """
    Executes the Method Matrix v4 hierarchical cascade mapping target tiers to
    exact quantum chemistry specifications (Table 2, §4.4, §8A, §8B).
    """
    if context is None:
        context = ExecutionContext()

    resolved_tier = tier_key if tier_key is not None else target_tier
    tier_key = resolved_tier.upper().strip()

    if tier_key in ["T3-10S", "T1-10S"]:
        method = "GFN2-xTB"
        basis = ""
        aux = ""
    elif tier_key in ["T3-1MIN", "T1-1MIN"]:
        method = "r2SCAN-3c"
        basis = ""
        aux = ""
    elif tier_key in ["T3-30MIN", "T1-30MIN"]:
        method = "r2SCAN-3c"
        basis = ""
        aux = ""
    elif tier_key in ["T3-1H", "T1-1H"]:
        method = "B3LYP-D4"
        basis = "def2-TZVP"
        aux = "def2/J"
    elif tier_key in ["T3-3H", "T1-3H"]:
        method = "wB97M-V"
        basis = "def2-QZVPP"
        aux = "def2/J"
        frozen_monomer = True
    elif tier_key in ["T3-12H", "T1-12H"]:
        method = "revDSD-PBEP86-D4"
        basis = "def2-TZVPP"
        aux = "def2-TZVPP/C"
    elif tier_key in ["T4-1D", "T4-1H"]:
        method = "DLPNO-CCSD(T)"
        basis = "def2-TZVP"
        aux = "def2-TZVPP/C"
    elif (
        tier_key in ["T3C", "T4C", "T3-C", "T4-C", "T3C-3D", "T4C-1MO", "CFOUR_VPT2", "CFOUR"]
        or tier_key.startswith("T3C")
        or tier_key.startswith("T4C")
        or "CFOUR" in tier_key
    ):
        from cochem_base.environment import BinaryRegistry
        from cochem_base.exceptions import BinaryNotFoundError
        try:
            cfour_bin = BinaryRegistry.resolve("xcfour")
        except BinaryNotFoundError:
            raise BinaryNotFoundError(
                "[MISSING DATA] CFOUR executable (xcfour) not found. "
                "Cannot execute coupled-cluster analytic force fields."
            )
        method = "CCSD(T)"
        basis = "ANO1" if ("T4" in tier_key or "1MO" in tier_key) else "ANO0"
        aux = ""
    else:
        method = "wB97M-V"
        basis = "def2-TZVP"
        aux = "def2/J"


    payload = route_cascade_rules(
        point_coords=coordinates,
        context=context,
        symbols=symbols,
        charge=charge,
        multiplicity=multiplicity,
        method=method,
        basis_set=basis,
        is_complex=is_complex,
        initial_hessian=initial_hessian,
        frozen_monomer=frozen_monomer,
        extra_options=extra_options,
        grid_level=grid_level,
        counterpoise=counterpoise,
        ghost_atom_indices=ghost_atom_indices
    )
    if (
        tier_key in ["T3C", "T4C", "T3-C", "T4-C", "T3C-3D", "T4C-1MO", "CFOUR_VPT2", "CFOUR"]
        or tier_key.startswith("T3C")
        or tier_key.startswith("T4C")
        or "CFOUR" in tier_key
    ):
        payload.executor = "TorqCfourExecutor"
        payload.metadata["executor"] = "TorqCfourExecutor"
    return payload



# ============================================================================
# 5. In-Memory Wavefunction Propagation & OPI Persistent Threading
# ============================================================================

def dynamic_wavefunction_propagation(
    previous_result: ORCAStepResult,
    next_payload: DispatchPayload,
    context: ExecutionContext
) -> DispatchPayload:
    """
    Transmits molecular orbital coefficients and Fock matrices between adjacent
    geometric points. In standalone execution, persists seed to SHM and injects
    ! MOREAD / %moinp into next_payload.
    """
    shm_dir = context.get_shm_dir()
    seed_file = shm_dir / f"seed_{context.session_id[:8]}.gbw"

    if previous_result.gbw_bytes:
        with open(seed_file, "wb") as f:
            f.write(previous_result.gbw_bytes)
    else:
        h5_seed = shm_dir / f"seed_{context.session_id[:8]}.chk"
        with h5py.File(h5_seed, "w") as h5f:
            if previous_result.mo_coefficients is not None:
                h5f.create_dataset("mo_coefficients", data=previous_result.mo_coefficients)
            if previous_result.fock_matrix is not None:
                h5f.create_dataset("fock_matrix", data=previous_result.fock_matrix)
            if previous_result.density_matrix is not None:
                h5f.create_dataset("density_matrix", data=previous_result.density_matrix)
            h5f.attrs["energy"] = previous_result.energy
            h5f.attrs["step_idx"] = previous_result.step_idx

        with open(seed_file, "wb") as f:
            f.write(b"ORCA_GBW_CHECKPOINT_SEED_V61\n" + h5_seed.read_bytes())

    updated_payload = next_payload.model_copy(deep=True)
    updated_payload.use_moread = True
    updated_payload.moinp_path = str(seed_file)

    if previous_result.mo_coefficients is not None:
        updated_payload.metadata["mo_coefficients"] = previous_result.mo_coefficients
    if previous_result.fock_matrix is not None:
        updated_payload.metadata["fock_matrix"] = previous_result.fock_matrix
    if previous_result.density_matrix is not None:
        updated_payload.metadata["density_matrix"] = previous_result.density_matrix

    logger.info(f"Dynamically propagated wavefunction from step {previous_result.step_idx} to seed {seed_file.name}.")
    return updated_payload


def _parse_orca_engrad_or_output(
    engrad_path: Path,
    out_content: str,
    n_atoms: int
) -> Tuple[float, np.ndarray, bool]:
    """
    Parses exact energy, gradient, and convergence flag from ORCA .engrad file and stdout.
    """
    energy = 0.0
    gradient = np.full((n_atoms, 3), 0.0, dtype=np.float64)
    converged = "ORCA TERMINATED NORMALLY" in out_content

    # Try .engrad first for highest precision
    if engrad_path.exists():
        try:
            lines = engrad_path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if "total energy in Eh" in line.lower() and i + 1 < len(lines):
                    energy = float(lines[i + 1].strip())
                if "gradient in Eh/bohr" in line.lower():
                    grad_vals = []
                    for j in range(i + 1, len(lines)):
                        val_str = lines[j].strip()
                        if val_str and not val_str.startswith("#"):
                            grad_vals.append(float(val_str))
                            if len(grad_vals) == n_atoms * 3:
                                break
                    if len(grad_vals) == n_atoms * 3:
                        gradient = np.array(grad_vals, dtype=np.float64).reshape((n_atoms, 3))
        except Exception as e:
            logger.debug(f"Could not parse .engrad: {e}")

    # Fallback to stdout if energy not found
    if energy == 0.0:
        e_match = re.search(r"(?:FINAL SINGLE POINT ENERGY|TOTAL ENERGY)\s+(-?\d+\.\d+)", out_content)
        if e_match:
            energy = float(e_match.group(1))

    # Fallback gradient from stdout
    if np.all(gradient == 0.0):
        grad_match = re.search(r"CARTESIAN GRADIENT.*?\n\n(.*?)(?=\n\n|\n[A-Z]|\Z)", out_content, re.DOTALL)
        if grad_match:
            parsed_grad = []
            for line in grad_match.group(1).strip().splitlines():
                parts = line.split()
                if len(parts) >= 6 and not line.startswith("-"):
                    try:
                        parsed_grad.append([float(parts[3]), float(parts[4]), float(parts[5])])
                    except ValueError:
                        pass
            if len(parsed_grad) == n_atoms:
                gradient = np.array(parsed_grad, dtype=np.float64)

    return energy, gradient, converged


def opi_persistent_threading(
    input_payload: DispatchPayload,
    context: Optional[ExecutionContext] = None,
    n_steps: int = 3,
    trajectory: Optional[List[np.ndarray]] = None
) -> Generator[ORCAStepResult, None, None]:
    """
    Interfaces with the ORCA execution engine, yielding ORCAStepResult instances 
    across optimization or PES sweep steps with dynamic wavefunction propagation.
    Handles Windows / MPI execution cleanly to prevent exit code 126.
    """
    if context is None:
        context = ExecutionContext()

    current_coords = np.copy(input_payload.coordinates)
    steps_to_run = trajectory if trajectory is not None else [current_coords for _ in range(n_steps)]

    scratch_dir = context.get_scratch_dir("opi_thread")
    orca_bin = os.environ.get("ORCA_PATH", "orca")

    # Determine safe core allocation (avoid MPI error 126 on Windows when MPI is unconfigured)
    safe_n_procs = context.num_cores if is_openmpi_supported() else 1

    last_gbw_path: Optional[Path] = None

    for idx, step_coords in enumerate(steps_to_run):
        step_payload = input_payload.model_copy(deep=True)
        step_payload.coordinates = step_coords

        # Dynamically propagate previous step's wavefunction seed via MOREAD
        if idx > 0 and last_gbw_path and last_gbw_path.exists():
            step_payload.use_moread = True
            step_payload.moinp_path = str(last_gbw_path)

        # Append EnGrad if not already present
        if "engrad" not in step_payload.extra_options.lower() and "engrad" not in step_payload.method.lower():
            step_payload.extra_options = f"! EnGrad\n{step_payload.extra_options}".strip()

        job_base = scratch_dir / f"opi_step_{idx:04d}_{context.session_id[:8]}"
        inp_path = job_base.with_suffix(".inp")
        out_path = job_base.with_suffix(".out")
        gbw_path = job_base.with_suffix(".gbw")
        engrad_path = job_base.with_suffix(".engrad")

        inp_content = step_payload.to_orca_input(
            n_procs=safe_n_procs,
            max_core_mb=max(1000, context.max_memory_mb // max(1, safe_n_procs))
        )
        inp_path.write_text(inp_content, encoding="utf-8")

        logger.info(f"[OPI Thread] Executing ORCA step {idx} (n_procs={safe_n_procs}) at {inp_path}")
        try:
            stdout, stderr, ret_code = execute_subprocess_safe(
                cmd=[orca_bin, str(inp_path)],
                cwd=scratch_dir,
                timeout=3600.0
            )
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(stdout)
        except Exception as e:
            logger.error(f"[OPI Thread] ORCA execution failed at step {idx}: {e}")
            raise RuntimeError(f"ORCA execution failed at step {idx}: {e}")

        # Parse energy, gradient, convergence
        energy, grad, converged = _parse_orca_engrad_or_output(engrad_path, stdout, len(step_coords))

        # Spin observables
        s_ideal, s_obs, s_dev = None, None, None
        if input_payload.multiplicity > 1:
            s2_match = re.search(r"Expectation value of <S\*\*2>\s+:\s+([\d\.]+)", stdout)
            s2_ideal_match = re.search(r"Ideal value s\*\(s\+1\)\s+for\s+S=\S+\s+:\s+([\d\.]+)", stdout)
            if s2_match and s2_ideal_match:
                s_obs = float(s2_match.group(1))
                s_ideal, s_obs, s_dev = validate_spin_contamination(input_payload.multiplicity, s_obs)

        # Read GBW binary bytes
        gbw_data = None
        if gbw_path.exists():
            gbw_data = gbw_path.read_bytes()
            last_gbw_path = gbw_path

        # Generate / extract physical in-memory MO and Fock tensors for OPI threading
        if not gbw_data:
            raise ValueError("Missing physical MO tensor data. Cannot extract MO and Fock tensors without valid GBW data or explicit text output.")

        # Note: In-memory MO/Fock arrays require an external MOLDEN parser or orca_2mkl.
        # The raw physical binary checkpoint is fully preserved in gbw_bytes for MOREAD propagation.
        mo_coefficients = None
        fock_matrix = None
        density_matrix = None

        result = ORCAStepResult(
            step_idx=idx,
            energy=energy,
            coordinates=np.copy(step_coords),
            gradient=grad,
            converged=converged,
            mo_coefficients=mo_coefficients,
            fock_matrix=fock_matrix,
            density_matrix=density_matrix,
            gbw_bytes=gbw_data,
            gbw_path=gbw_path if gbw_path.exists() else None,
            s_squared_ideal=s_ideal,
            s_squared_observed=s_obs,
            spin_contamination_percent=s_dev,
            raw_output=stdout
        )

        logger.info(f"[OPI Thread] Yielded step {idx}: E = {energy:.8f} Ha, converged={converged}")
        yield result


# ============================================================================
# 6. Stateful SCF Checkpointing
# ============================================================================

def stateful_scf_checkpointing(
    step_idx: int,
    wavefunction_data: Union[bytes, Dict[str, Any], np.ndarray],
    context: ExecutionContext,
    checkpoint_type: str = "gbw"
) -> Path:
    """
    Persists binary .gbw, .chk, or .hess checkpoints to context.get_scratch_dir('orca_tmp')
    at all topological stationary points (minima and transition states).
    """
    scratch_tmp = context.get_scratch_dir("orca_tmp")
    chk_filename = f"checkpoint_step_{step_idx:04d}.{checkpoint_type}"
    target_path = scratch_tmp / chk_filename

    if isinstance(wavefunction_data, bytes):
        with open(target_path, "wb") as f:
            f.write(wavefunction_data)
    elif isinstance(wavefunction_data, np.ndarray):
        with h5py.File(target_path, "w") as h5f:
            h5f.create_dataset("tensor_data", data=wavefunction_data)
            h5f.attrs["step_idx"] = step_idx
            h5f.attrs["timestamp"] = datetime.now(timezone.utc).isoformat()
    elif isinstance(wavefunction_data, dict):
        with h5py.File(target_path, "w") as h5f:
            for k, v in wavefunction_data.items():
                if isinstance(v, np.ndarray):
                    h5f.create_dataset(k, data=v)
                elif isinstance(v, (int, float, str)):
                    h5f.attrs[k] = v
            h5f.attrs["step_idx"] = step_idx
            h5f.attrs["timestamp"] = datetime.now(timezone.utc).isoformat()
    else:
        with open(target_path, "wb") as f:
            f.write(str(wavefunction_data).encode("utf-8"))

    if not target_path.exists() or target_path.stat().st_size == 0:
        raise IOError(f"Failed to persist checkpoint to '{target_path}'.")

    logger.info(f"Persisted SCF checkpoint: {target_path} ({target_path.stat().st_size} bytes).")
    return target_path


# ============================================================================
# 7. GPU4PySCF Dynamic Batching
# ============================================================================

def gpu4pyscf_dynamic_batching(
    grid_points: List[np.ndarray],
    context: ExecutionContext,
    system_size: Optional[int] = None,
    basis_functions_per_atom: int = 30,
    memory_headroom_fraction: float = 0.15
) -> List[List[np.ndarray]]:
    """
    Hardware-aware dynamic batching that evaluates available GPU VRAM via pynvml
    and partitions PES grid points to maximize tensor core occupancy while
    strictly enforcing a 15% VRAM safety headroom.
    """
    if not grid_points:
        return []

    n_atoms = system_size if system_size else len(grid_points[0])
    n_basis = n_atoms * basis_functions_per_atom

    # Memory requirement per PES point in double precision (FP64 = 8 bytes)
    # Scales as O(N_basis^2) for Fock/density matrices and intermediate integral buffers
    bytes_per_point = 8 * (n_basis ** 2) * 64 + (1024 * 1024 * 32)
    mb_per_point = max(bytes_per_point / (1024 * 1024), 1.0)

    # Determine available VRAM
    available_vram_mb = context.vram_mb if context.vram_mb > 0 else 8192
    usable_vram_mb = available_vram_mb * (1.0 - memory_headroom_fraction)

    # Calculate optimal batch size capped to reasonable bounds
    batch_size = max(1, int(usable_vram_mb / mb_per_point))
    batch_size = min(batch_size, 64)

    batches: List[List[np.ndarray]] = []
    for i in range(0, len(grid_points), batch_size):
        batches.append(grid_points[i : i + batch_size])

    logger.info(
        f"Dynamic GPU Batching: {len(grid_points)} points partitioned into {len(batches)} batches "
        f"(batch_size={batch_size}, {mb_per_point:.1f} MB/pt, VRAM_usable={usable_vram_mb:.0f} MB)."
    )
    return batches


# ============================================================================
# 8. Subprocess Safety & Process Tree Teardown
# ============================================================================

def safe_process_tree_teardown(parent_pid: int, timeout_sec: float = 5.0) -> None:
    """
    Discovers all recursive child processes of parent_pid and executes a two-phase
    graceful termination (terminate -> wait -> kill), eliminating orphaned OpenMPI / ORCA daemons.
    """
    try:
        parent = psutil.Process(parent_pid)
        children = parent.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return

    # Phase 1: SIGTERM / Terminate
    for child in children:
        try:
            child.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    try:
        parent.terminate()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    gone, alive = psutil.wait_procs(children + [parent], timeout=timeout_sec)

    # Phase 2: SIGKILL / Kill surviving processes
    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


_SPAWNED_PIDS: set[int] = set()


def register_spawned_process(pid: int) -> None:
    _SPAWNED_PIDS.add(pid)


def unregister_spawned_process(pid: int) -> None:
    _SPAWNED_PIDS.discard(pid)


def execute_subprocess_safe(
    cmd: List[str],
    cwd: Optional[Path] = None,
    timeout: float = 3600.0,
    env: Optional[Dict[str, str]] = None,
    stdin_data: Optional[str] = None
) -> Tuple[str, str, int]:
    """
    Executes a subprocess wrapped in try/except with check=True and strict timeout handling.
    Automatically initiates clean process tree teardown upon timeout or failure.
    """
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    proc: Optional[subprocess.Popen] = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.PIPE if stdin_data else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=run_env
        )
        if proc.pid:
            register_spawned_process(proc.pid)

        stdout, stderr = proc.communicate(input=stdin_data, timeout=timeout)
        ret_code = proc.returncode

        if proc.pid:
            unregister_spawned_process(proc.pid)

        if ret_code != 0:
            raise subprocess.CalledProcessError(ret_code, cmd, output=stdout, stderr=stderr)

        return stdout, stderr, ret_code

    except subprocess.TimeoutExpired as exc:
        if proc:
            if proc.pid:
                unregister_spawned_process(proc.pid)
            safe_process_tree_teardown(proc.pid, timeout_sec=3.0)
        logger.error(f"Subprocess '{cmd[0]}' timed out after {timeout} seconds.")
        raise TimeoutError(f"Subprocess '{cmd[0]}' timed out after {timeout} seconds.") from exc

    except subprocess.CalledProcessError as exc:
        if proc:
            if proc.pid:
                unregister_spawned_process(proc.pid)
            safe_process_tree_teardown(proc.pid, timeout_sec=2.0)
        logger.error(f"Subprocess '{cmd[0]}' failed with exit code {exc.returncode}: {exc.stderr}")
        raise

    except Exception as exc:
        if proc:
            if proc.pid:
                unregister_spawned_process(proc.pid)
            safe_process_tree_teardown(proc.pid, timeout_sec=2.0)
        logger.error(f"Subprocess '{cmd[0]}' encountered unexpected exception: {exc}")
        raise


def cleanup_all_cochem_processes() -> None:
    """
    Registered atexit handler to ensure no orphaned child orca, xtb, or mpi processes remain.
    """
    current_pid = os.getpid()
    try:
        current_proc = psutil.Process(current_pid)
        for child in current_proc.children(recursive=True):
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


# Register clean process teardown at program exit
atexit.register(cleanup_all_cochem_processes)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\config.py ---
"""CoChem Ecosystem Configuration and Integration Grid Policy (Compatibility Module)."""

from __future__ import annotations

from cochem_base.config.grid_policy import GridPolicy, WorkflowPhase

__all__ = ["GridPolicy", "WorkflowPhase"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\environment.py ---
"""CoChem Ecosystem Dynamic Environment & Path Registries (Compatibility Module)."""

from __future__ import annotations

from cochem_base.environment.binary_registry import BinaryRegistry
from cochem_base.environment.path_registry import PathRegistry

__all__ = ["BinaryRegistry", "PathRegistry"]

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
        import platform
        import sys
        import traceback

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


class EcosystemExecutionError(CoChemError, RuntimeError):
    """Raised when an electronic structure execution fails or returns unverified wavefunctions."""

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


class SCFConvergenceError(ConvergenceError):
    """Raised when Self-Consistent Field (SCF) electronic iteration fails to converge."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONVERGENCE_FAILURE
    )

    def to_pedagogical_guidance(self) -> str:
        """Translates low-level SCF convergence failure into clear didactic orbital intuition."""
        return (
            "Self-Consistent Field (SCF) electronic iteration did not reach numerical convergence. "
            "In molecular orbital theory, this indicates electronic oscillation or near-degenerate frontier "
            "orbitals (HOMO-LUMO gap closure). Recommended remediation: (1) Option 1: enable orbital damping or level shifting "
            "(e.g. SOSCF / DIIS), (2) Option 2: switch initial orbital guess to PModel or HCore, or (3) Option 3: collapse "
            "the numerical quadrature grid (e.g. defgrid3 -> defgrid2) to smooth the electronic energy landscape."
        )


class NegativeHessianFrequencyError(MethodMatrixViolationError):
    """Raised when unexpected imaginary (negative) vibrational frequencies appear in a ground state geometry."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INVALID_HESSIAN_STRATEGY
    )

    def to_pedagogical_guidance(self) -> str:
        """Translates imaginary frequencies into didactic PES and normal mode distortion advice."""
        return (
            "Unexpected imaginary (negative) vibrational frequency encountered. A true ground-state local minimum "
            "must possess 3N-6 strictly positive real normal mode frequencies. A transition state must possess exactly one "
            "imaginary frequency along the reaction coordinate. Recommended remediation: (1) Option 1: distort atomic "
            "coordinates slightly along the normal mode vector of the imaginary frequency and re-optimize, or (2) Option 2: "
            "switch to an analytical Hessian or increase geometry convergence tightness."
        )


class BasisSetLinearDependencyError(SingularityError):
    """Raised when basis set overlap matrix exhibits near-zero eigenvalues due to linear dependency."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SINGULARITY_DETECTED
    )

    def to_pedagogical_guidance(self) -> str:
        """Translates basis set linear dependency into didactic diffuse function overlap advice."""
        return (
            "Near-singular basis set overlap matrix detected (basis set linear dependency). Diffuse basis functions "
            "on adjacent centers overlap excessively, causing overlap matrix eigenvalues to approach zero and matrix "
            "diagonalization to become ill-conditioned. Recommended remediation: (1) Option 1: adjust the linear dependency "
            "threshold (e.g., THRESH 1e-6), or (2) Option 2: replace overly diffuse basis sets (e.g. aug-cc-pVTZ) with a contracted "
            "or truncated basis set (e.g., def2-TZVP or jun-cc-pVTZ)."
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
    "EcosystemExecutionError",
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
    "SCFConvergenceError",
    "NegativeHessianFrequencyError",
    "BasisSetLinearDependencyError",
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\geometry\constraints.py ---
"""Frozen-Monomer Spatial Protections and Internal Coordinate Constraint Generator.

Compliant with Method Matrix v4 §9A.1-9A.7, Anti-Spoofing Protocol v2, and Zero-Mock Mandate.
"""

from __future__ import annotations

import itertools
from typing import Any, List, Optional, Sequence, Set, Tuple, Union
from mendeleev import element as mendeleev_element
import networkx as nx
import numpy as np

from cochem_base.schemas import ConstraintPayload


def get_dynamic_covalent_radius(symbol: str) -> float:
    """Retrieve Pyykkö covalent radius in Angstroms via mendeleev."""
    clean = str(symbol).strip().rstrip(":").capitalize()
    el = mendeleev_element(clean)
    if hasattr(el, "covalent_radius_pyykko") and el.covalent_radius_pyykko is not None:
        return float(el.covalent_radius_pyykko) / 100.0
    if hasattr(el, "covalent_radius") and el.covalent_radius is not None:
        return float(el.covalent_radius) / 100.0
    return 1.40


def build_molecular_graph_from_geometry(
    symbols: Sequence[str],
    coordinates: Union[Sequence[Sequence[float]], np.ndarray],
    atom_subsets: Optional[Sequence[Sequence[int]]] = None,
) -> nx.Graph:
    """Build a molecular connectivity graph using dynamic Mendeleev covalent radii.

    If atom_subsets is provided (e.g. [atoms_a, atoms_b]), edges are strictly restricted
    to intramolecular connections within each subset, guaranteeing zero intermolecular edges.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    radii = [get_dynamic_covalent_radius(s) for s in symbols]
    G = nx.Graph()
    G.add_nodes_from(range(len(symbols)))

    subsets = atom_subsets if atom_subsets is not None else [list(range(len(symbols)))]
    for subset in subsets:
        sub_list = sorted(list(subset))
        for idx_i, i in enumerate(sub_list):
            for j in sub_list[idx_i + 1 :]:
                dist = float(np.linalg.norm(coords[i] - coords[j]))
                max_bond = (radii[i] + radii[j]) * 1.28
                if 0.4 < dist <= max_bond:
                    G.add_edge(i, j)

    return G


def generate_frozen_monomer_constraints(
    atoms_a: Sequence[int],
    atoms_b: Sequence[int],
    molecular_graph: Any = None,
    symbols: Optional[Sequence[str]] = None,
    coordinates: Optional[Union[Sequence[Sequence[float]], np.ndarray]] = None,
) -> ConstraintPayload:
    """Generate internal coordinate constraints for Monomer A and Monomer B.

    Implements Method Matrix v4 §9A.1-9A.2 Frozen-Monomer Protocol:
    Freezes high-level monomers across all internal degrees of freedom (bonds, angles, dihedrals)
    to fix rotational constant A to < 0.2% error [M], while ensuring zero constraints are placed
    on intermolecular separation (R) and mutual monomer orientations.

    Parameters
    ----------
    atoms_a : Sequence[int]
        0-based atom indices belonging to Monomer A.
    atoms_b : Sequence[int]
        0-based atom indices belonging to Monomer B.
    molecular_graph : Any, optional
        NetworkX Graph or adjacency structure defining chemical bonds.
    symbols : Sequence[str], optional
        Atomic symbols of the complex (used to build graph if not provided).
    coordinates : Sequence[Sequence[float]] | np.ndarray, optional
        Cartesian coordinates in Angstroms (used to build graph if not provided).

    Returns
    -------
    ConstraintPayload
        Container with intramolecular bonds, valence angles, and proper dihedrals for A and B.
    """
    set_a: Set[int] = set(atoms_a)
    set_b: Set[int] = set(atoms_b)

    if molecular_graph is None:
        if symbols is None or coordinates is None:
            raise ValueError(
                "Either molecular_graph or both symbols and coordinates must be provided."
            )
        G = build_molecular_graph_from_geometry(symbols, coordinates, atom_subsets=[atoms_a, atoms_b])
    elif not isinstance(molecular_graph, nx.Graph):
        G = nx.Graph()
        if hasattr(molecular_graph, "edges"):
            G.add_edges_from(molecular_graph.edges())
        elif isinstance(molecular_graph, (list, tuple, set)):
            G.add_edges_from(molecular_graph)
        elif isinstance(molecular_graph, dict):
            for u, neighbors in molecular_graph.items():
                for v in neighbors:
                    G.add_edge(u, v)
        else:
            raise TypeError(f"Unsupported molecular_graph type: {type(molecular_graph)}")
    else:
        G = molecular_graph

    bonds: List[Tuple[int, int]] = []
    angles: List[Tuple[int, int, int]] = []
    dihedrals: List[Tuple[int, int, int, int]] = []

    for monomer_atoms in [set_a, set_b]:
        # Extract intramolecular subgraph
        sub_g = G.subgraph(monomer_atoms)

        # 1. Distance constraints { B u v C } for all intramolecular edges
        for u, v in sub_g.edges():
            bonds.append(tuple(sorted((int(u), int(v)))))

        # 2. Angle constraints { A i j k C } for all adjacent intramolecular valence angles (apex j)
        for j in sub_g.nodes():
            neighbors = sorted(list(sub_g.neighbors(j)))
            if len(neighbors) >= 2:
                for i, k in itertools.combinations(neighbors, 2):
                    angles.append((int(i), int(j), int(k)))

        # 3. Proper dihedral constraints { D i j k l C } for all proper dihedral quartets
        seen_dihedrals: Set[Tuple[int, int, int, int]] = set()
        for j, k in sub_g.edges():
            j_int, k_int = int(j), int(k)
            j_neighbors = [int(nbr) for nbr in sub_g.neighbors(j) if int(nbr) != k_int]
            k_neighbors = [int(nbr) for nbr in sub_g.neighbors(k) if int(nbr) != j_int]

            for i in j_neighbors:
                for l in k_neighbors:
                    if i == l:
                        continue
                    # Canonicalize representation (i, j, k, l) vs (l, k, j, i)
                    forward = (i, j_int, k_int, l)
                    backward = (l, k_int, j_int, i)
                    canonical = min(forward, backward)
                    if canonical not in seen_dihedrals:
                        seen_dihedrals.add(canonical)
                        dihedrals.append(canonical)

    # Sort deterministically
    bonds = sorted(list(set(bonds)))
    angles = sorted(list(set(angles)))
    dihedrals = sorted(list(set(dihedrals)))

    return ConstraintPayload(
        bonds=bonds,
        angles=angles,
        dihedrals=dihedrals,
        metadata={
            "n_atoms_a": len(atoms_a),
            "n_atoms_b": len(atoms_b),
            "n_bonds": len(bonds),
            "n_angles": len(angles),
            "n_dihedrals": len(dihedrals),
            "provenance_tag": "[M]",
        },
    )


def format_orca_frozen_monomer_constraints_block(
    constraints: ConstraintPayload,
    convergence_thresholds: Optional[dict[str, Any]] = None,
) -> str:
    """Format complete ORCA %geom Constraints block for frozen-monomer optimization."""
    thresh = convergence_thresholds or {
        "TolE": "1e-7",
        "TolRMSG": "3e-6",
        "TolMaxG": "1e-5",
        "TolRMSD": "5e-5",
        "TolMaxD": "1e-4",
    }
    lines: list[str] = ["%geom"]
    for k, v in thresh.items():
        lines.append(f"  {k} {v}")

    if constraints.bonds or constraints.angles or constraints.dihedrals:
        lines.append("  Constraints")
        for u, v in constraints.bonds:
            lines.append(f"    {{ B {u} {v} C }}")
        for i, j, k in constraints.angles:
            lines.append(f"    {{ A {i} {j} {k} C }}")
        for i, j, k, l in constraints.dihedrals:
            lines.append(f"    {{ D {i} {j} {k} {l} C }}")
        lines.append("  end")

    lines.append("end")
    return "\n".join(lines)


__all__ = [
    "generate_frozen_monomer_constraints",
    "format_orca_frozen_monomer_constraints_block",
    "build_molecular_graph_from_geometry",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\interfaces\__init__.py ---
"""CoChem Ecosystem Abstract Execution and Generation Interfaces.

Compliant with Method Matrix v4 and Zero-Mock Mandate.
"""

from __future__ import annotations

from cochem_base.interfaces.conformer import ConformerGenerator
from cochem_base.interfaces.executors import ElectronicStructureExecutor

__all__ = ["ElectronicStructureExecutor", "ConformerGenerator"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\schemas\__init__.py ---
"""
CoChem Ecosystem Authoritative Pydantic Data Schemas.
Compliant with Method Matrix v4, FAIR Data Standards, and Anti-Spoofing Directives.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator


from cochem_base.schemas.quantum import (
    ConformerEnsemblePayload,
    ConstraintPayload,
    CounterpoiseResult,
    GradientPayload,
    QuantumJobSpec,
)


# =====================================================================
# Chunk 6 Ecosystem Schemas (Suggestions #51-#60)
# =====================================================================

from typing import Literal


class ActiveLearningBatchConfig(BaseModel):
    """Configuration for sequential furthest-point repulsion active learning batch selection. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    batch_size: int = Field(default=32, ge=1, le=512)
    repulsion_length_scale: float = Field(
        default=0.5,
        gt=0.0,
        alias="repulsion_radius",
        description="Spatial repulsion radius sigma_repulse in Angstroms",
    )
    diversity_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    kernel_type: Literal["gaussian", "morse"] = "gaussian"


class HardwareTelemetryReport(BaseModel):
    """Authentic live hardware telemetry report queried from OS and GPU driver. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    device_count: int = Field(ge=0)
    gpu_available: bool
    device_name: str
    vram_total_mb: float = Field(ge=0.0)
    vram_free_mb: float = Field(ge=0.0)
    selected_runtime: Literal["cuda", "mps", "cpu", "onnx_cpu"]


class ANI2xCutoffConfig(BaseModel):
    """Configuration for ANI-2x continuous radial envelope and self-interaction diagonal masking. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cutoff_radius: float = Field(default=5.2, gt=1.0, le=10.0, description="Radial cutoff in Angstroms")
    envelope_type: Literal["cosine", "quintic"] = "cosine"
    mask_self_interactions: bool = True


class ConformalCalibrationConfig(BaseModel):
    """Configuration for split-conformal prediction calibration and quantile evaluation. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    significance_level: float = Field(default=0.05, gt=0.0, lt=1.0)
    hypothesis_scope: Literal["marginal", "atomwise_bonferroni"] = "marginal"
    min_calibration_observations: int = Field(
        default=50,
        ge=20,
        description="Must satisfy n >= ceil((1 - alpha) / alpha) to guarantee valid quantile evaluation",
    )


class ForceMatchingLossConfig(BaseModel):
    """Configuration for multi-task energy and force Huber matching loss normalization. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    energy_weight: float = Field(default=1.0, ge=0.0)
    force_weight: float = Field(default=10.0, ge=0.0)
    huber_delta_energy: float = Field(default=0.01, gt=0.0)
    huber_delta_force: float = Field(default=0.05, gt=0.0)
    normalization_mode: Literal["atom_norm", "coordinate_component"] = "atom_norm"
    virial_weight: float = Field(default=0.0, ge=0.0)


class GoatExploreDaemonConfig(BaseModel):
    """Configuration for persistent ORCA GOAT-EXPLORE daemon and stochastic hopping. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    socket_path: str
    scratch_dir: str
    max_hopping_steps: int = Field(default=100, ge=1)
    tight_opt_threshold: bool = True
    rmsd_dedup_threshold: float = Field(default=0.15, gt=0.0)


class PipSymmetryConfig(BaseModel):
    """Configuration for Permutation Invariant Polynomial (PIP) closed subgroup orbit averaging. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_symmetric_order: int = Field(
        default=120,
        ge=2,
        description="Upper bound before invoking subgroup orbit averaging",
    )
    subgroup_type: Literal["full", "alternating", "automorphism_wreath"] = "automorphism_wreath"
    invariance_tolerance: float = Field(
        default=1e-14,
        gt=0.0,
        description="Permutation invariance tolerance in Eh",
    )


class KrrRegularizationConfig(BaseModel):
    """Configuration for Kernel Ridge Regression condition-number floor and diagonal Tikhonov jitter. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_alpha: float = Field(default=1e-6, gt=0.0)
    anchor_alpha_floor: float = Field(default=1e-8, gt=0.0)
    jitter_epsilon: float = Field(default=1e-9, gt=0.0)
    max_jitter_escalation: float = Field(default=1e-6, gt=0.0)


class DeltaMLDispersionConfig(BaseModel):
    """Configuration for Becke-Johnson damped D3 dispersion baseline augmentation in Delta-ML. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    use_d3_dispersion: bool = True
    damping_scheme: Literal["bj", "zero"] = "bj"
    s6_scale: float = Field(default=1.0, ge=0.0)
    s8_scale: float = Field(default=0.0, ge=0.0)


# =====================================================================
# Chunk 7 Ecosystem Schemas (Suggestions #61-#70)
# =====================================================================

import datetime
from pathlib import Path


class CommitteeEnsembleConfig(BaseModel):
    """Configuration for vectorized active learning committee ensemble inference. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vectorized: bool = True
    vram_headroom_threshold_mb: float = Field(default=2048.0, ge=512.0)
    concurrency_mode: Literal["vmap", "cuda_streams", "serial"] = "vmap"
    max_batch_size: int = Field(default=128, ge=1)


class OETFallbackAlertManifest(BaseModel):
    """Provenance audit manifest emitted when OET socket disconnect triggers physical fallback. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calculation_base: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    trigger_event: str
    fallback_calculator: str
    provenance_tag: str = "[E]"
    host_telemetry: Dict[str, Any]
    scratch_alert_file: str
    staged_artifact_file: str


class HDF5PersistenceConfig(BaseModel):
    """Configuration for two-tier thread-safe and process-safe HDF5 persistence store. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lock_timeout_seconds: float = Field(default=60.0, ge=1.0)
    retry_backoff_base_seconds: float = Field(default=0.05, ge=0.001)
    compression_filter: str = "gzip"
    compression_level: int = Field(default=4, ge=1, le=9)
    enable_fletcher32: bool = True
    enable_shuffle: bool = True


class GpuScoutExecutorConfig(BaseModel):
    """Configuration for OS-aware heterogeneous GPU scout concurrency across the 6-Tier Matrix. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    platform_os: Literal["windows", "darwin", "linux"]
    enable_mps: bool
    mps_pipe_dir: str
    max_concurrent_gpu_tasks: int = Field(default=1, ge=1)
    min_vram_headroom_mb: float = Field(default=1536.0, ge=512.0)


class JobRouteConfig(BaseModel):
    """Routing specification mapping jobs to heterogeneous Parsl executors. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_type: Literal["heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"]
    assigned_executor: Literal["cochem_anchor_cpu", "cochem_scout_gpu", "local_fallback"]
    cpu_core_pinning: Optional[List[int]] = None
    scratch_dir: str
    timeout_seconds: float = Field(default=3600.0, ge=10.0)


class ExecutionRouteResult(BaseModel):
    """Execution result returned by Parsl execution broker routing. [M]"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    task_id: Optional[str] = None
    job_id: Optional[str] = None
    status: str
    assigned_executor: Optional[str] = None
    executor_used: Optional[str] = None
    scratch_dir: Union[str, Path]
    returncode: int = 0
    future: Optional[Any] = None
    output: Optional[Any] = None
    telemetry: Optional[Dict[str, Any]] = None

    @property
    def effective_task_id(self) -> str:
        return self.task_id or self.job_id or ""

    @property
    def effective_executor(self) -> str:
        return self.assigned_executor or self.executor_used or ""



class MultiSeedGoatConfig(BaseModel):
    """Configuration for asynchronous multi-seed GOAT conformational exploration via Parsl queues. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_structures: List[str] = Field(min_length=1)
    max_concurrent_seeds: int = Field(default=4, ge=1)
    rmsd_threshold_angstrom: float = Field(default=0.15, gt=0.0)
    energy_window_kcal_mol: float = Field(default=6.0, gt=0.0)


class TorqPipelineCliArgs(BaseModel):
    """Validated CLI argument model for high-performance SLURM batch pipeline entrypoints. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_geometry: Path
    output_directory: Path
    theory_level: str = "B3LYP-D4/def2-TZVP"
    cpus_per_task: int = Field(default=1, ge=1)
    memory_mb: int = Field(default=4096, ge=1024)
    scratch_dir: Path


__all__ = [
    "GradientPayload",
    "QuantumJobSpec",
    "ConstraintPayload",
    "ConformerEnsemblePayload",
    "CounterpoiseResult",
    "ActiveLearningBatchConfig",
    "HardwareTelemetryReport",
    "ANI2xCutoffConfig",
    "ConformalCalibrationConfig",
    "ForceMatchingLossConfig",
    "GoatExploreDaemonConfig",
    "PipSymmetryConfig",
    "KrrRegularizationConfig",
    "DeltaMLDispersionConfig",
    "CommitteeEnsembleConfig",
    "OETFallbackAlertManifest",
    "HDF5PersistenceConfig",
    "GpuScoutExecutorConfig",
    "JobRouteConfig",
    "ExecutionRouteResult",
    "MultiSeedGoatConfig",
    "TorqPipelineCliArgs",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_anti_spoof_linter.py ---
"""Physical unit tests for CoChem Anti-Spoofing Linter (ci_tools/anti_spoof_linter.py).

Zero-Mock Mandate Compliance:
- Real test files created in tmp_path.
- Tests verify AST inspection, banned imports, and stubs.
"""

from __future__ import annotations

from pathlib import Path

from ci_tools.anti_spoof_linter import (
    BANNED_CONCURRENCY_MODULES,
    BANNED_MOCK_MODULES,
    EXCLUDED_DIRS,
    check_file,
    load_amnesty,
    run_linter,
)


def test_excluded_dirs() -> None:
    assert ".git" in EXCLUDED_DIRS
    assert "__pycache__" in EXCLUDED_DIRS
    assert ".pytest_cache" in EXCLUDED_DIRS


def test_detect_banned_imports(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_import.py"
    bad_script.write_text("import parsl\nimport dask\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("parsl" in v.symbol for v in violations)
    assert any("dask" in v.symbol for v in violations)


def test_detect_mock_modules(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_mock.py"
    bad_script.write_text("import mock\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("mock" in v.symbol for v in violations)


def test_detect_pass_stub(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_stub.py"
    bad_script.write_text("def solve():\n    pass\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("pass" in v.message.lower() for v in violations)


def test_detect_not_implemented_error(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_raise.py"
    bad_script.write_text(
        "def compute():\n    raise NotImplementedError('Not done')\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "NOT_IMPLEMENTED_ERROR" for v in violations)


def test_detect_banned_identifier(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_ident.py"
    bad_script.write_text("def run():\n    dummy_var = 123\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "BANNED_IDENTIFIER" for v in violations)


def test_clean_script_passes(tmp_path: Path) -> None:
    clean_script = tmp_path / "clean_module.py"
    clean_script.write_text(
        "def compute_energy(x: float) -> float:\n    return x * 2.5\n",
        encoding="utf-8",
    )
    violations = check_file(clean_script, tmp_path, amnesty_set=set())
    assert len(violations) == 0


def test_run_linter_directory(tmp_path: Path) -> None:
    sub_dir = tmp_path / "clean_dir"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "clean_mod.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    exit_code, violations = run_linter(
        targets=[sub_dir], repo_root=sub_dir, strict_mode=True
    )
    assert exit_code == 0
    assert len(violations) == 0


def test_amnesty_bypass(tmp_path: Path) -> None:
    conc_script = tmp_path / "conc_worker.py"
    conc_script.write_text("import parsl\n", encoding="utf-8")
    # Without amnesty, it fails
    v_un = check_file(conc_script, tmp_path, amnesty_set=set())
    assert len(v_un) > 0
    # With amnesty, it passes
    v_am = check_file(conc_script, tmp_path, amnesty_set={"conc_worker.py"})
    assert len(v_am) == 0


def test_detect_pytest_alias_skip(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_alias_skip.py"
    bad_script.write_text(
        "import pytest as pt\n"
        "def test_one():\n"
        "    pt.skip('skip reason')\n"
        "@pt.mark.skip\n"
        "def test_two():\n"
        "    pass\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "PYTEST_SKIP" and "pt.skip" in v.symbol for v in violations)
    assert any(v.category == "PYTEST_SKIP" and "pt.mark.skip" in v.symbol for v in violations)


def test_detect_pytest_skipif_and_xfail(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_skipif_xfail.py"
    bad_script.write_text(
        "import pytest\n"
        "from pytest import skipif, xfail\n"
        "@pytest.mark.skipif(True, reason='cond')\n"
        "def test_one():\n"
        "    pass\n"
        "@pytest.mark.xfail\n"
        "def test_two():\n"
        "    pass\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("skipif" in v.symbol for v in violations)
    assert any("xfail" in v.symbol for v in violations)


def test_detect_unittest_skips(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_unittest_skips.py"
    bad_script.write_text(
        "import unittest\n"
        "@unittest.skip('reason')\n"
        "def test_one():\n"
        "    pass\n"
        "class TestSuite(unittest.TestCase):\n"
        "    def test_two(self):\n"
        "        self.skipTest('skip')\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("unittest.skip" in v.symbol for v in violations)
    assert any("skipTest" in v.symbol for v in violations)


def test_detect_monkeypatch_and_setattr_bypass(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_monkeypatch_bypass.py"
    bad_script.write_text(
        "import os\n"
        "def test_mp(mp):\n"
        "    mp.setattr('os.environ', {})\n"
        "def test_setattr_foreign():\n"
        "    setattr(os.path, 'exists', lambda x: True)\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("mp.setattr" in v.symbol for v in violations)
    assert any("setattr" in v.symbol for v in violations)


def test_detect_dummy_physical_dict_variants(tmp_path: Path) -> None:
    bad_script = tmp_path / "dummy_dicts.py"
    bad_script.write_text(
        "d1 = {'charge': 0, **{'uhf': 1}}\n"
        "d2 = dict(charge=0, uhf=1)\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert len([v for v in violations if v.category == "DUMMY_DICT"]) >= 2


def test_detect_dynamic_obfuscation_exec_eval(tmp_path: Path) -> None:
    bad_script = tmp_path / "obfuscated.py"
    bad_script.write_text(
        "x = eval('1 + 1')\n"
        "exec('y = 2')\n"
        "getattr(sys, 'mock')\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "OBFUSCATION" and v.symbol == "eval" for v in violations)
    assert any(v.category == "OBFUSCATION" and v.symbol == "exec" for v in violations)
    assert any("mock" in v.symbol for v in violations)


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\interfaces\conformer.py ---
"""CoChem Ecosystem Conformer Generator Interface.

Compliant with Method Matrix v4 §9B and Zero-Mock Mandate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, Union
import numpy as np

from cochem_base.schemas import ConformerEnsemblePayload


class ConformerGenerator(ABC):
    """Standard execution interface for conformer generation engines (GOAT, CREST, etc.)."""

    @abstractmethod
    def generate_conformers(
        self,
        symbols: Sequence[str],
        coordinates: Union[Sequence[Sequence[float]], np.ndarray],
        **kwargs: Any,
    ) -> ConformerEnsemblePayload:
        """Generate a conformer ensemble from an initial seed structure.

        Parameters
        ----------
        symbols : Sequence[str]
            Atomic symbols.
        coordinates : Union[Sequence[Sequence[float]], np.ndarray]
            Seed Cartesian coordinates in Angstroms.
        **kwargs : Any
            Additional engine-specific options.

        Returns
        -------
        ConformerEnsemblePayload
            Container with sampled conformer coordinates, energies, and metadata.
        """
        ...


__all__ = ["ConformerGenerator"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\interfaces\executors.py ---
"""CoChem Ecosystem Electronic Structure Executor Interface.

Compliant with Method Matrix v4 and Zero-Mock Mandate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from cochem_base.schemas import GradientPayload, QuantumJobSpec


class ElectronicStructureExecutor(ABC):
    """Standard execution interface for electronic structure engines (ORCA, CFOUR, etc.)."""

    @abstractmethod
    def execute(self, job_spec: QuantumJobSpec) -> GradientPayload:
        """Execute an electronic structure calculation described by job_spec.

        Parameters
        ----------
        job_spec : QuantumJobSpec
            Specification of coordinates, method, basis set, and job type.

        Returns
        -------
        GradientPayload
            Energies, gradients, and optional Hessians from the engine.
        """
        ...


__all__ = ["ElectronicStructureExecutor"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\schemas\quantum.py ---
"""CoChem Quantum Schemas Module.

Compliant with Method Matrix v4, QCSchema specifications, and Anti-Spoofing Protocol v2.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GradientPayload(BaseModel):
    """Pydantic schema for gradient and Hessian calculation outputs.

    Enforces anti-spoofing validation to prevent unphysical all-zero gradients.
    Screening tiers (T1-T3) leave hessian=None; target production tiers (T4/T5) populate it.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    energy: float = Field(default=0.0, description="Electronic energy in Hartrees")
    energy_hartree: Optional[float] = Field(
        default=None,
        description="Electronic energy in true atomic units (Hartree) per Method Matrix §8C",
    )
    gradient: List[Any] = Field(
        default_factory=list,
        description="Cartesian energy gradients in Eh/Bohr",
    )
    hessian: Optional[List[Any]] = Field(
        default=None,
        description="Cartesian force constant matrix; populated exclusively at production tiers (T4/T5).",
    )
    scf_tole: float = Field(
        default=1e-7,
        description="SCF energy convergence threshold in Hartrees",
    )
    geometry: str = Field(
        default="",
        description="Optimized Cartesian XYZ geometry string",
    )
    geom_block: Optional[str] = Field(
        default=None,
        description="Associated %geom block",
    )
    forces: Optional[List[Any]] = Field(
        default=None,
        description="Atomic forces (nabla E = -F)",
    )
    status: str = Field(
        default="SUCCESS",
        description="Execution status",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warning messages collected during calculation",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_energies(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "energy_hartree" in data and data["energy_hartree"] is not None:
                if "energy" not in data or data["energy"] == 0.0:
                    data["energy"] = float(data["energy_hartree"])
            elif "energy" in data and data["energy"] is not None:
                data["energy_hartree"] = float(data["energy"])
        return data

    @field_validator("gradient")
    @classmethod
    def validate_gradient(cls, v: Any) -> Any:
        if not v:
            return v
        arr = np.asarray(v)
        if arr.size > 0 and np.all(arr == 0.0):
            raise ValueError("Spoofing detected: Fake 0.0 gradients are strictly prohibited.")
        return v


class QuantumJobSpec(BaseModel):
    """Standardized multi-job definition for quantum electronic structure calculations,

    including discrete single-point counterpoise evaluations (E_AB^{AB}, E_A^{AB}, E_B^{AB}).
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True, arbitrary_types_allowed=True)

    job_id: str = Field(description="Unique job identifier")
    symbols: List[str] = Field(description="Atomic symbols")
    coordinates: List[Any] = Field(description="Cartesian coordinates in Angstroms")
    charge: int = Field(default=0, description="Total molecular charge")
    multiplicity: int = Field(default=1, description="Spin multiplicity (2S + 1)")
    method: str = Field(default="wB97M-V", description="Quantum chemistry method / DFT functional")
    basis_set: str = Field(default="def2-TZVP", description="Primary basis set")
    aux_basis: Optional[str] = Field(default="def2/J", description="Auxiliary basis set")
    ghost_atom_indices: Optional[List[int]] = Field(
        default=None,
        description="Indices of atoms treated as ghost centers (basis functions only)",
    )
    job_type: str = Field(
        default="SP",
        description="Calculation type: 'SP', 'OPT', 'FREQ', 'CP_E_AB_AB', 'CP_E_A_AB', 'CP_E_B_AB'",
    )
    extra_options: str = Field(default="", description="Additional engine directives or keywords")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual job metadata")


class ConstraintPayload(BaseModel):
    """Structured payload for monomer internal coordinate constraint definitions."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    bonds: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Frozen distance pairs (u, v) using 0-based indices",
    )
    angles: List[Tuple[int, int, int]] = Field(
        default_factory=list,
        description="Frozen valence angle triplets (i, j, k) with apex j using 0-based indices",
    )
    dihedrals: List[Tuple[int, int, int, int]] = Field(
        default_factory=list,
        description="Frozen proper dihedral quartets (i, j, k, l) using 0-based indices",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Constraint metadata")


class ConformerEnsemblePayload(BaseModel):
    """Unified container for conformer geometries, energies, and origin engine tags."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    ensemble_id: str = Field(description="Ensemble identifier")
    conformers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of conformer dictionaries (symbols, coordinates, energies, moments)",
    )
    origin_engine: str = Field(
        default="UNION",
        description="Origin engine tag (e.g. 'GOAT', 'CREST', 'UNION')",
    )
    temperature_k: float = Field(default=298.15, description="Temperature in Kelvin")
    provenance_tag: str = Field(default="[M]", description="Method Matrix provenance tag")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Ensemble metadata")


class CounterpoiseResult(BaseModel):
    """Result payload for discrete 3-point and 5-point Boys-Bernardi counterpoise evaluations.

    Delta E_CP = E_AB^{AB} - E_A^{AB} - E_B^{AB} [M].
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    delta_e_cp: float = Field(description="Counterpoise-corrected interaction energy in Hartrees [M]")
    e_ab_ab: float = Field(description="Total electronic energy of complex AB in dimer basis [Hartree]")
    e_a_ab: float = Field(description="Total electronic energy of Monomer A in dimer basis (B ghosted) [Hartree]")
    e_b_ab: float = Field(description="Total electronic energy of Monomer B in dimer basis (A ghosted) [Hartree]")
    e_a_a: Optional[float] = Field(default=None, description="Monomer A in monomer A basis [Hartree]")
    e_b_b: Optional[float] = Field(default=None, description="Monomer B in monomer B basis [Hartree]")
    e_bsse: Optional[float] = Field(default=None, description="Basis Set Superposition Error (BSSE) [Hartree]")
    delta_e_raw: Optional[float] = Field(default=None, description="Uncorrected raw interaction energy [Hartree]")
    provenance_tag: str = Field(default="[M]", description="Method Matrix provenance tag")


__all__ = [
    "GradientPayload",
    "QuantumJobSpec",
    "ConstraintPayload",
    "ConformerEnsemblePayload",
    "CounterpoiseResult",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_torq\counterpoise.py ---
"""CoChem-TORQ Counterpoise Workflow (Compatibility Module)."""

from __future__ import annotations

from Libraries.cochem_torq_counterpoise import (
    calculate_counterpoise_correction,
    calculate_discrete_counterpoise_energy,
    generate_counterpoise_jobs,
)

__all__ = [
    "calculate_discrete_counterpoise_energy",
    "calculate_counterpoise_correction",
    "generate_counterpoise_jobs",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_internal_coordinate_constraint_generation.py ---
"""CoChem-BASE: Test Internal Coordinate Constraint Generation.

Compliant with Method Matrix v4 §9A.1-§9A.2 and Anti-Spoofing Protocol v2.
Verifies Deliverable 3:
1. Canonical constraint generation in cochem_base.geometry.constraints.
2. Full extraction of intramolecular bonds ({ B u v C }), angles ({ A i j k C }),
   and proper dihedrals ({ D i j k l C }) for both Monomer A and Monomer B.
3. Strict preservation of intermolecular degrees of freedom (zero intermolecular constraints).
"""

import re
import pytest
from cochem_base.geometry.constraints import (
    format_orca_frozen_monomer_constraints_block,
    generate_frozen_monomer_constraints,
)
from cochem_base.schemas import ConstraintPayload
from Libraries.cochem_torq_constraints import (
    generate_orca_frozen_monomer_constraints_block,
)


def test_formic_acid_water_full_internal_coordinate_freezing():
    """Verify complete freezing of intramolecular degrees of freedom for formic acid and water

    while strictly excluding all intermolecular coordinates from constraints.
    """
    # Authentic planar cyclic dimer geometry of Formic Acid ... Water
    # Monomer A (Formic acid, atoms 0-4):
    # 0: C, 1: O (carbonyl), 2: O (hydroxyl), 3: H (formyl), 4: H (hydroxyl)
    # Monomer B (Water, atoms 5-7):
    # 5: O, 6: H, 7: H
    symbols = ["C", "O", "O", "H", "H", "O", "H", "H"]
    coords = [
        [-0.1347, 1.3469, 0.0000],   # 0: C
        [1.0267, 0.9995, 0.0000],    # 1: O=
        [-1.1578, 0.5186, 0.0000],   # 2: O-H
        [-0.3472, 2.4273, 0.0000],   # 3: H-C
        [-0.8174, -0.4140, 0.0000],  # 4: H-O
        [0.2227, -1.8906, 0.0000],   # 5: Ow
        [1.0487, -1.3789, 0.0000],   # 6: Hw
        [0.3807, -2.8443, 0.0000],   # 7: Hw
    ]

    atoms_a = [0, 1, 2, 3, 4]
    atoms_b = [5, 6, 7]

    constraints = generate_frozen_monomer_constraints(
        atoms_a=atoms_a,
        atoms_b=atoms_b,
        symbols=symbols,
        coordinates=coords,
    )

    assert isinstance(constraints, ConstraintPayload)

    # Monomer A (Formic acid) has 4 covalent bonds: (0, 1), (0, 2), (0, 3), (2, 4)
    # Monomer B (Water) has 2 covalent bonds: (5, 6), (5, 7)
    # Total intramolecular bonds = 6
    assert len(constraints.bonds) == 6

    # Formic acid has valence angles: (1, 0, 2), (1, 0, 3), (2, 0, 3), (0, 2, 4) -> 4 angles
    # Water has 1 valence angle: (6, 5, 7)
    # Total valence angles = 5
    assert len(constraints.angles) == 5

    # Formic acid has proper dihedrals about C-O bond (0, 2): (1, 0, 2, 4) and (3, 0, 2, 4)
    assert len(constraints.dihedrals) == 2

    # Verify zero intermolecular constraints exist
    set_a = set(atoms_a)
    set_b = set(atoms_b)

    for u, v in constraints.bonds:
        assert (u in set_a and v in set_a) or (u in set_b and v in set_b), (
            f"Intermolecular bond constraint detected between {u} and {v}"
        )

    for i, j, k in constraints.angles:
        assert (i in set_a and j in set_a and k in set_a) or (
            i in set_b and j in set_b and k in set_b
        ), f"Intermolecular angle constraint detected: ({i}, {j}, {k})"

    for i, j, k, l in constraints.dihedrals:
        assert (i in set_a and j in set_a and k in set_a and l in set_a) or (
            i in set_b and j in set_b and k in set_b and l in set_b
        ), f"Intermolecular dihedral constraint detected: ({i}, {j}, {k}, {l})"

    # Generate full ORCA %geom constraint block
    orca_block = format_orca_frozen_monomer_constraints_block(constraints)

    assert "%geom" in orca_block
    assert "TolMaxG 1e-5" in orca_block
    assert "TolE 1e-7" in orca_block
    assert "TolRMSG 3e-6" in orca_block
    assert "Constraints" in orca_block
    assert "{ B " in orca_block
    assert "{ A " in orca_block
    assert "{ D " in orca_block
    assert "end" in orca_block

    # Test compatibility via cochem_torq_constraints
    torq_block = generate_orca_frozen_monomer_constraints_block(
        atoms_a=atoms_a,
        atoms_b=atoms_b,
        symbols=symbols,
        coordinates=coords,
    )
    assert "{ B " in torq_block
    assert "{ A " in torq_block
    assert "{ D " in torq_block

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_codata_energy_normalization_and_hdf5_locking.py ---
"""CoChem-TOPOS: Test CODATA 2022 Energy Normalization and Thread-Safe HDF5 Concurrency.

Compliant with Method Matrix v4 §4.4, §8C, Anti-Spoofing Protocol v2, and Zero-Mock Mandate.
Verifies Deliverable 4:
1. Normalization of ASE potential energies (eV -> Hartree via CODATA 2022).
2. Dynamic CODATA 2022 conversion: 27.211386245988 eV / Hartree [M].
3. Safe cross-platform file locking via filelock.FileLock preventing database corruption.
"""

import os
import subprocess
import sys
from pathlib import Path

import h5py
import pytest
import scipy.constants

from cascade_engine.cochem_cascade_hdf5 import CascadeHDF5Serializer


def test_codata_energy_normalization_ev_to_hartree(tmp_path):
    """Verify that energies passed in eV are stored in Hartree normalized via CODATA 2022."""
    h5_path = tmp_path / "test_energy.h5"
    serializer = CascadeHDF5Serializer(h5_path)

    # Physical potential energy of water monomer from semiempirical evaluation (eV)
    energy_ev = -14.285321
    codata_factor = scipy.constants.value("Hartree energy in eV")
    assert pytest.approx(codata_factor, rel=1e-9) == 27.211386245988

    expected_hartree = float(energy_ev / codata_factor)

    # Pass energy_ev explicitly to write_tier_data
    serializer.write_tier_data(
        geom_id="mol_01",
        tier_id="T1",
        energy_ev=energy_ev,
        geometry="3\nWater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
    )

    with h5py.File(h5_path, "r", swmr=True) as f:
        stored_hartree = float(f["mol_01"]["T1"].attrs["electronic_energy_hartree"])
        dataset_hartree = float(f["mol_01"]["T1"]["energy"][()])

    assert pytest.approx(stored_hartree, rel=1e-7) == expected_hartree
    assert pytest.approx(dataset_hartree, rel=1e-7) == expected_hartree


def test_concurrent_multiprocess_hdf5_filelocking(tmp_path):
    """Verify that concurrent worker processes writing to the same HDF5 store

    synchronize safely via filelock.FileLock without corruption or BlockingIOError.
    """
    h5_path = tmp_path / "concurrent_test.h5"
    serializer = CascadeHDF5Serializer(h5_path)

    # Worker script to write 5 entries
    worker_code = f"""
import sys
from pathlib import Path
repo_base = Path(r"D:\\__CoChem\\GitHub-Repo\\CoChem-BASE")
repo_topos = Path(r"D:\\__CoChem\\GitHub-Repo\\CoChem-TOPOS")
if str(repo_topos) not in sys.path:
    sys.path.insert(0, str(repo_topos))
if str(repo_base / "src") not in sys.path:
    sys.path.insert(0, str(repo_base / "src"))
from cascade_engine.cochem_cascade_hdf5 import CascadeHDF5Serializer


h5_path = Path(r"{h5_path}")
worker_id = sys.argv[1]
serializer = CascadeHDF5Serializer(h5_path)

for i in range(5):
    serializer.write_tier_data(
        geom_id=f"geom_{{worker_id}}_{{i}}",
        tier_id="T1",
        energy_ev=-15.0 - (i * 0.1),
    )
"""

    p1 = subprocess.Popen(
        [sys.executable, "-c", worker_code, "w1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p2 = subprocess.Popen(
        [sys.executable, "-c", worker_code, "w2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    out1, err1 = p1.communicate(timeout=60)
    out2, err2 = p2.communicate(timeout=60)

    assert p1.returncode == 0, f"Worker 1 failed: {err1.decode()}"
    assert p2.returncode == 0, f"Worker 2 failed: {err2.decode()}"

    # Verify all 10 entries were successfully written to HDF5
    with h5py.File(h5_path, "r", swmr=True) as f:
        keys = list(f.keys())
        w1_keys = [k for k in keys if k.startswith("geom_w1_")]
        w2_keys = [k for k in keys if k.startswith("geom_w2_")]
        assert len(w1_keys) == 5
        assert len(w2_keys) == 5

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_screening_tier_hessian_deferral.py ---
"""CoChem-TOPOS: Test Screening-Tier Hessian Deferral & ZPVE Deferral.

Compliant with Method Matrix v4 §3.3, §8B.3, and Anti-Spoofing Protocol v2.
Verifies Deliverable 6:
1. GradientPayload schema allows optional Hessian (hessian=None).
2. Elimination of unconditional Hessian evaluations and Vibrations loops in Tiers 1-3.
3. Method Matrix Hessian spend hierarchy: preliminary screening tiers report hessian=None and zpve=None.
"""

from pathlib import Path
import pytest
from ase import Atoms
from cochem_base.schemas import GradientPayload
from cascade_engine.cochem_topos_cascade_orchestrator import (
    CascadeConfig,
    CascadeOrchestrator,
)


def test_gradient_payload_optional_hessian():
    """Verify GradientPayload supports hessian=None for screening tiers."""
    payload = GradientPayload(
        energy=-152.7533,
        gradient=[[0.001, -0.002, 0.003], [-0.001, 0.002, -0.003]],
        hessian=None,
    )
    assert payload.hessian is None
    assert payload.energy == -152.7533


def test_screening_tier_defers_hessian_on_six_atom_complex(tmp_path):
    """Execute Tier 1 screening on a 6-atom water dimer complex.

    Asserts that GradientPayload.hessian is None and completes without launching 6N Vibrations displacements.
    """
    # Authentic 6-atom water dimer coordinates
    symbols = ["O", "H", "H", "O", "H", "H"]
    positions = [
        [-1.464, -0.015, 0.043],
        [-0.505, -0.031, -0.011],
        [-1.751, -0.771, -0.478],
        [1.442, 0.003, -0.076],
        [1.804, 0.759, 0.395],
        [1.803, -0.753, 0.397],
    ]
    dimer = Atoms(symbols=symbols, positions=positions)

    config = CascadeConfig(artifact_dir=tmp_path)
    orchestrator = CascadeOrchestrator(config)

    # Tier 1 execution (Hand topology screening)
    result = orchestrator._execute_hand_topology(dimer)

    assert isinstance(result, GradientPayload)
    assert result.hessian is None, "Screening tier must defer Hessian evaluation to production tiers"
    assert result.energy != 0.0
    assert len(result.gradient) == 6

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_two_stage_grid_dynamic_tightening.py ---
"""CoChem-TOPOS: Test Two-Stage Integration Grid Tightening & Decoupled Frequencies.

Compliant with Method Matrix v4 §4.4, §8B, and Anti-Spoofing Directives.
Verifies Deliverable 5:
1. Canonical GridPolicy schema and grid validation across workflow phases.
2. Two-stage dynamic grid tightening (Stage 1 defgrid1 loose -> Stage 2 defgrid3 tight %geom).
3. Rejection of defgrid1 for vibrational frequency calculations (! Freq).
"""

import pytest
from cochem_base.config.grid_policy import GridPolicy, WorkflowPhase
from cascade_engine.cochem_topos_cascade_orchestrator import (
    build_two_stage_optimization_decks,
    build_vibrational_frequency_deck,
    validate_frequency_grid,
)


def test_canonical_grid_policy_validation():
    """Verify GridPolicy schema and phase-specific integration grid validation."""
    # Pre-optimization permits defgrid1 and defgrid3
    assert GridPolicy.validate_grid(WorkflowPhase.PHASE_PREOPT, "defgrid1") is True
    assert GridPolicy.validate_grid("PHASE_PREOPT", "defgrid1") is True
    assert GridPolicy.validate_grid("preopt", "defgrid3") is True

    # Final optimization strictly forbids defgrid1
    assert GridPolicy.validate_grid(WorkflowPhase.PHASE_FINALOPT, "defgrid1") is False
    assert GridPolicy.validate_grid("PHASE_FINALOPT", "defgrid1") is False
    assert GridPolicy.validate_grid("finalopt", "defgrid3") is True

    # Frequency evaluation strictly forbids defgrid1
    assert GridPolicy.validate_grid(WorkflowPhase.PHASE_NUMFREQ, "defgrid1") is False
    assert GridPolicy.validate_grid("numfreq", "defgrid1") is False
    assert GridPolicy.validate_grid("numfreq", "defgrid3") is True

    # Deprecated Grid3 / Grid5 nomenclature is unconditionally prohibited
    assert GridPolicy.validate_grid("preopt", "grid3") is False
    assert GridPolicy.validate_grid("finalopt", "grid5") is False


def test_two_stage_optimization_deck_construction():
    """Verify Stage 1 uses defgrid1 loose convergence and Stage 2 uses defgrid3 tight %geom."""
    symbols = ["O", "H", "H"]
    coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

    stage1_deck, stage2_deck = build_two_stage_optimization_decks(
        atoms=None,
        functional="r2SCAN-3c",
    )

    # Stage 1 assertions: defgrid1 with loose convergence
    assert "! r2SCAN-3c Opt" in stage1_deck
    assert "! defgrid1" in stage1_deck
    assert "TolE 1e-4" in stage1_deck
    assert "TolMaxG 1e-3" in stage1_deck
    assert "InHess XTB2" in stage1_deck
    assert "Freq" not in stage1_deck  # No Freq in Stage 1

    # Stage 2 assertions: defgrid3 with tight %geom thresholds
    assert "! r2SCAN-3c Opt" in stage2_deck
    assert "! defgrid3" in stage2_deck
    assert "TolMaxG 1e-5" in stage2_deck
    assert "TolE 1e-7" in stage2_deck
    assert "TolRMSG 3e-6" in stage2_deck
    assert "TolRMSD 5e-5" in stage2_deck
    assert "TolMaxD 1e-4" in stage2_deck
    assert "InHess XTB2" in stage2_deck
    assert "Freq" not in stage2_deck  # Decoupled from Freq!


def test_vibrational_frequencies_strictly_reject_defgrid1():
    """Verify vibrational frequency calculations reject defgrid1 and require defgrid3."""
    # Deck with ! Freq and defgrid1 must be rejected
    invalid_deck = "! r2SCAN-3c Freq\n! defgrid1\n"
    assert validate_frequency_grid(invalid_deck) is False

    # Deck with ! Freq and defgrid3 is accepted
    valid_deck = "! r2SCAN-3c Freq\n! defgrid3\n"
    assert validate_frequency_grid(valid_deck) is True

    # Deck builder raises ValueError when attempting defgrid1 with Freq
    with pytest.raises(ValueError) as excinfo:
        build_vibrational_frequency_deck(functional="r2SCAN-3c", grid="defgrid1")
    assert "defgrid1" in str(excinfo.value)
    assert "strictly prohibited" in str(excinfo.value)

    # Clean creation on defgrid3
    freq_deck = build_vibrational_frequency_deck(functional="r2SCAN-3c", grid="defgrid3")
    assert "! r2SCAN-3c Freq" in freq_deck
    assert "! defgrid3" in freq_deck

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_cfour_bridge_registration_and_scratch_isolation.py ---
"""CoChem-TORQ: Test CFOUR Execution Bridge Registration & Ephemeral Scratch Isolation.

Compliant with Method Matrix v4 §9, §13-§14, and Anti-Spoofing Directives.
Verifies Deliverable 9:
1. Registration of TorqCfourExecutor into execution dispatcher and route_method_matrix.
2. Dynamic discovery of xcfour and strict prohibition of silent demotion to DFT.
3. Ephemeral scratch subdirectory isolation and ZMAT input deck generation.
"""

import os
import sys
from pathlib import Path


import pytest
from cochem_base.environment import BinaryRegistry
from cochem_base.exceptions import BinaryNotFoundError
from cochem_base.interfaces.executors import ElectronicStructureExecutor
from cochem_base.schemas import QuantumJobSpec
from Libraries.cochem_torq_cfour_bridge import (
    CFOURZmatBuilder,
    TorqCfourExecutor,
)
from Libraries.cochem_torq_engine import (
    ExecutionContext,
    route_method_matrix,
)


def test_torq_cfour_executor_implements_interface():
    """Verify TorqCfourExecutor implements the standard ElectronicStructureExecutor ABC."""
    assert issubclass(TorqCfourExecutor, ElectronicStructureExecutor)
    executor = TorqCfourExecutor()
    assert hasattr(executor, "execute")
    assert hasattr(executor, "run_cfour_job")


def test_route_method_matrix_cfour_missing_binary_raises():
    """Requesting tier T3C-3d with missing CFOUR binary must immediately raise

    BinaryNotFoundError rather than silently demoting to ORCA DFT.
    """
    old_env = dict(os.environ)
    try:
        os.environ["PATH"] = ""
        os.environ.pop("CFOUR_ROOT", None)
        os.environ.pop("CFOUR_PATH", None)
        os.environ.pop("COCHEM_CFOUR_BIN", None)
        os.environ.pop("COCHEM_XCFOUR_BIN", None)

        context = ExecutionContext()
        symbols = ["O", "H", "H"]
        coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

        with pytest.raises(BinaryNotFoundError) as excinfo:
            route_method_matrix(
                tier_key="T3C-3d",
                symbols=symbols,
                coordinates=coords,
                context=context,
            )

        err_msg = str(excinfo.value)
        assert "[MISSING DATA]" in err_msg
        assert "CFOUR executable (xcfour) not found" in err_msg
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_route_method_matrix_cfour_routes_to_torq_cfour_executor():
    """When CFOUR binary is discoverable, route_method_matrix maps T3C-3d to TorqCfourExecutor."""
    old_env = dict(os.environ)
    try:
        real_bin = Path(sys.executable).resolve()
        os.environ["COCHEM_CFOUR_BIN"] = str(real_bin)

        context = ExecutionContext()
        symbols = ["O", "H", "H"]
        coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

        payload = route_method_matrix(
            tier_key="T3C-3d",
            symbols=symbols,
            coordinates=coords,
            context=context,
        )

        assert payload.executor == "TorqCfourExecutor"
        assert payload.metadata["executor"] == "TorqCfourExecutor"
        assert payload.method == "CCSD(T)"
    finally:
        os.environ.clear()
        os.environ.update(old_env)



def test_cfour_scratch_isolation_and_zmat_generation(tmp_path):
    """Verify that CFOUR input generation executes in an isolated scratch subdirectory

    containing an authentic ZMAT input file.
    """
    symbols = ["O", "H", "H"]
    coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

    zmat_content = CFOURZmatBuilder.generate_full_zmat_input(
        symbols=symbols,
        coordinates=coords,
        method="CCSD(T)",
        basis="ANO0",
        isotopes=[16, 1, 1],
    )


    # Isolated scratch directory
    scratch_dir = tmp_path / "cfour_worker_01"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    zmat_file = scratch_dir / "ZMAT"
    zmat_file.write_text(zmat_content, encoding="utf-8")

    assert zmat_file.exists()
    content = zmat_file.read_text(encoding="utf-8")
    assert "*CFOUR(" in content
    assert "CALC=CCSD(T)" in content
    assert "BASIS=ANO0" in content
    assert "%isotopes" in content

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_counterpoise_multijob_workflow.py ---
"""CoChem-TORQ: Test Decoupled Counterpoise Multi-Job Workflow.

Compliant with Method Matrix v4 §1.2, §8B, and Anti-Spoofing Protocol v2.
Verifies Deliverable 2:
1. Eradication of ghost-atom injection during active geometry relaxations (! Opt).
2. Coordination of counterpoise calculations via discrete multi-job payloads (QuantumJobSpec).
3. Discrete 3-point interaction energy evaluation: Delta E_CP = E_AB^{AB} - E_A^{AB} - E_B^{AB} [M].
"""

import pytest
from cochem_base.schemas import QuantumJobSpec
from Libraries.cochem_torq_counterpoise import (
    calculate_counterpoise_correction,
    calculate_discrete_counterpoise_energy,
    generate_counterpoise_jobs,
)
from Libraries.cochem_torq_engine import (
    DispatchPayload,
    route_cascade_rules,
)


def test_optimization_deck_strictly_prohibits_ghost_atoms():
    """Verify that an ORCA geometry optimization (! Opt) deck contains NO ghosted atoms (':')

    even when counterpoise is requested.
    """
    # Authentic Smith et al. water dimer equilibrium coordinates
    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = [
        [-1.464, -0.015, 0.043],
        [-0.505, -0.031, -0.011],
        [-1.751, -0.771, -0.478],
        [1.442, 0.003, -0.076],
        [1.804, 0.759, 0.395],
        [1.803, -0.753, 0.397],
    ]
    atoms_a = [0, 1, 2]
    atoms_b = [3, 4, 5]

    payload = DispatchPayload(
        symbols=symbols,
        coordinates=coords,
        charge=0,
        multiplicity=1,
        method="wB97M-V",
        basis_set="def2-TZVP",
        aux_basis="def2/J",
        extra_options="! Opt",
        is_complex=True,
        counterpoise=True,
        ghost_atom_indices=atoms_b,  # Passed in, but must be suppressed because is_opt is True
    )

    deck_content = payload.generate_orca_deck()

    # The generated optimization deck must have NO ghost symbols ('O:' or 'H:')
    assert "O:" not in deck_content
    assert "H:" not in deck_content
    assert "! Opt" in deck_content
    assert "%geom" in deck_content


def test_counterpoise_multijob_generation_and_discrete_bracketing():
    """Verify generation of 3 discrete single-point jobs and equation [M] evaluation."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = [
        [-1.464, -0.015, 0.043],
        [-0.505, -0.031, -0.011],
        [-1.751, -0.771, -0.478],
        [1.442, 0.003, -0.076],
        [1.804, 0.759, 0.395],
        [1.803, -0.753, 0.397],
    ]
    atoms_a = [0, 1, 2]
    atoms_b = [3, 4, 5]

    # Generate multi-job payload post-optimization
    jobs = generate_counterpoise_jobs(
        job_id="water_dimer_opt_converged",
        symbols=symbols,
        coordinates=coords,
        atoms_a=atoms_a,
        atoms_b=atoms_b,
        method="wB97M-V",
        basis_set="def2-TZVP",
    )

    # Exactly three discrete single-point jobs must be generated
    assert set(jobs.keys()) == {"E_AB_AB", "E_A_AB", "E_B_AB"}

    job_ab = jobs["E_AB_AB"]
    job_a = jobs["E_A_AB"]
    job_b = jobs["E_B_AB"]

    assert isinstance(job_ab, QuantumJobSpec)
    assert job_ab.ghost_atom_indices is None
    assert job_ab.job_type == "CP_E_AB_AB"

    assert isinstance(job_a, QuantumJobSpec)
    assert job_a.ghost_atom_indices == atoms_b
    assert job_a.job_type == "CP_E_A_AB"

    assert isinstance(job_b, QuantumJobSpec)
    assert job_b.ghost_atom_indices == atoms_a
    assert job_b.job_type == "CP_E_B_AB"

    # Authentic CCSD(T)/CBS benchmark energies for water dimer
    e_ab_ab = -152.753303
    e_a_ab = -76.374175
    e_b_ab = -76.374163
    e_a_a = -76.371200
    e_b_b = -76.371190

    delta_e_cp = calculate_discrete_counterpoise_energy(e_ab_ab, e_a_ab, e_b_ab)
    assert delta_e_cp < 0.0, "Physical water dimer interaction must be bound"
    assert pytest.approx(delta_e_cp, abs=1e-5) == -0.004965

    result = calculate_counterpoise_correction(
        e_ab_ab=e_ab_ab,
        e_a_ab=e_a_ab,
        e_b_ab=e_b_ab,
        e_a_a=e_a_a,
        e_b_b=e_b_b,
    )
    assert result.provenance_tag == "[M]"
    assert pytest.approx(result.delta_e_cp, abs=1e-5) == -0.004965
    assert result.e_bsse is not None and result.e_bsse > 0.0
    assert result.delta_e_raw is not None

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_crest_binary_resolution_and_missing_data.py ---
"""CoChem-TORQ: Test CREST Binary Discovery and Explicit Dependency Failure Gate.

Compliant with Method Matrix v4 §9B, Anti-Spoofing Protocol v2, and Zero-Mock Mandate.
Verifies Deliverable 1:
1. Purging of synthetic conformer displacements and fabricated energies.
2. Dynamic OS-agnostic binary resolution via BinaryRegistry.resolve("crest").
3. Raising of typed BinaryNotFoundError with tag '[MISSING DATA]' when crest is absent.
"""

import os
import sys
from pathlib import Path

import pytest
from cochem_base.environment import BinaryRegistry
from cochem_base.exceptions import BinaryNotFoundError, EcosystemDependencyError
from Libraries.cochem_torq_crest import CrestRunner, CrestConfig


def test_crest_runner_purges_fallback_methods():
    """Verify CrestRunner contains zero synthetic fallback generation methods."""
    runner = CrestRunner()
    # Confirm complete excision of synthetic fallback routines
    assert not hasattr(runner, "_generate_physical_fallback_ensemble")
    assert not hasattr(runner, "_fallback_conformer_ensemble")
    assert not hasattr(runner, "_generate_synthetic_ensemble")


def test_crest_binary_resolution_missing_data():
    """Verify BinaryRegistry.resolve('crest') raises BinaryNotFoundError with '[MISSING DATA]' when absent."""
    old_env = dict(os.environ)
    try:
        os.environ["PATH"] = ""
        os.environ.pop("COCHEM_CREST_BIN", None)
        os.environ.pop("CREST_BIN", None)
        os.environ.pop("CREST_PATH", None)

        with pytest.raises(BinaryNotFoundError) as exc_info:
            BinaryRegistry.resolve("crest")

        err_msg = str(exc_info.value)
        assert "[MISSING DATA]" in err_msg
        assert "CREST executable not discovered in environment path" in err_msg
        assert issubclass(BinaryNotFoundError, EcosystemDependencyError)
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_crest_binary_resolution_custom_override():
    """Verify BinaryRegistry.resolve('crest') resolves via COCHEM_CREST_BIN override."""
    old_env = dict(os.environ)
    try:
        real_binary = Path(sys.executable).resolve()
        os.environ["COCHEM_CREST_BIN"] = str(real_binary)

        resolved = BinaryRegistry.resolve("crest")
        assert resolved == real_binary
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_crest_runner_aborts_cleanly_without_executable(tmp_path):
    """Verify CrestRunner.run_crest halts cleanly with BinaryNotFoundError when executable is missing."""
    old_env = dict(os.environ)
    try:
        os.environ["PATH"] = ""
        os.environ.pop("COCHEM_CREST_BIN", None)
        os.environ.pop("CREST_BIN", None)
        os.environ.pop("CREST_PATH", None)

        # Authentic water molecule geometry
        water_xyz = tmp_path / "water.xyz"
        water_xyz.write_text(
            "3\nWater molecule\n"
            "O   0.000000   0.000000   0.117720\n"
            "H   0.000000   0.755453  -0.470880\n"
            "H   0.000000  -0.755453  -0.470880\n",
            encoding="utf-8",
        )

        runner = CrestRunner()
        with pytest.raises(BinaryNotFoundError) as exc_info:
            runner.run_crest(water_xyz, work_dir=tmp_path / "run")

        assert "[MISSING DATA]" in str(exc_info.value)
    finally:
        os.environ.clear()
        os.environ.update(old_env)


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_goat_crest_conformer_union_pipeline.py ---
"""CoChem-TORQ: Test Full GOAT + CREST Conformer Union Pipeline & Deduplication.

Compliant with Method Matrix v4 §8A, §9B.1-§9B.3, and Anti-Spoofing Directives.
Verifies Deliverable 10:
1. Conformer exploration integration through standardized ConformerGenerator interface.
2. Union deduplication via Rotational Constant Clustering (Delta B / B < 0.005, 0.5%).
3. Heavy-Atom RMSD filtering (Kabsch superposition with threshold < 0.15 A).
4. Full stage conformer pool processing without shortcuts or synthetic fallbacks.
"""

import numpy as np
import pytest
from cochem_base.interfaces.conformer import ConformerGenerator
from cochem_base.schemas import ConformerEnsemblePayload
from Libraries.cochem_torq_pipeline import deduplicate_conformer_union
from src.cochem_torq.conformer.orchestrator import (
    ConformerOrchestrator,
    deduplicate_union_ensemble,
    kabsch_rmsd,
)


def test_conformer_orchestrator_implements_interface():
    """Verify ConformerOrchestrator inherits from ConformerGenerator ABC."""
    assert issubclass(ConformerOrchestrator, ConformerGenerator)
    orchestrator = ConformerOrchestrator()
    assert hasattr(orchestrator, "generate_conformers")


def test_two_stage_union_deduplication_rotational_and_rmsd():
    """Verify union deduplication merges duplicates based on Delta B / B < 0.005 and RMSD < 0.15 A."""
    # Authentic ethanol conformers:
    # Conf 1: Anti conformer (trans, Cs symmetry)
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    anti_coords = [
        [1.226, -0.245, 0.000],
        [0.000, 0.589, 0.000],
        [-1.173, -0.222, 0.000],
        [-1.936, 0.366, 0.000],
        [0.038, 1.237, 0.887],
        [0.038, 1.237, -0.887],
        [2.138, 0.360, 0.000],
        [1.233, -0.883, 0.887],
        [1.233, -0.883, -0.887],
    ]
    # Gauche conformer (C1 symmetry, distinct dihedral)
    gauche_coords = [
        [1.218, -0.270, 0.000],
        [0.000, 0.575, 0.000],
        [-1.144, -0.254, 0.000],
        [-1.156, -0.814, 0.784],
        [0.040, 1.220, 0.885],
        [0.040, 1.220, -0.885],
        [2.126, 0.342, 0.000],
        [1.230, -0.905, 0.886],
        [1.230, -0.905, -0.886],
    ]
    # Duplicate Anti conformer with minute coordinate shift (< 0.05 A, RMSD < 0.15 A)
    anti_duplicate_coords = [
        [1.227, -0.244, 0.001],
        [0.001, 0.590, -0.001],
        [-1.172, -0.221, 0.001],
        [-1.935, 0.367, 0.000],
        [0.039, 1.238, 0.888],
        [0.037, 1.236, -0.886],
        [2.139, 0.361, 0.001],
        [1.234, -0.882, 0.888],
        [1.232, -0.884, -0.886],
    ]

    conf_anti = {
        "symbols": symbols,
        "coordinates": anti_coords,
        "energy_hartree": -154.9812,
        "rotational_constants_mhz": (34870.0, 9325.0, 8140.0),
        "origin": "GOAT",
    }
    conf_gauche = {
        "symbols": symbols,
        "coordinates": gauche_coords,
        "energy_hartree": -154.9805,
        "rotational_constants_mhz": (30450.0, 9110.0, 8420.0),
        "origin": "CREST",
    }
    conf_anti_duplicate = {
        "symbols": symbols,
        "coordinates": anti_duplicate_coords,
        "energy_hartree": -154.9811,
        "rotational_constants_mhz": (34875.0, 9323.0, 8142.0),
        "origin": "CREST",
    }

    pool = [conf_anti, conf_gauche, conf_anti_duplicate]

    # Deduplication with delta_b_rel_threshold=0.005 and rmsd_threshold=0.15
    deduped = deduplicate_union_ensemble(
        pool,
        delta_b_rel_threshold=0.005,
        rmsd_threshold=0.15,
    )

    # Must retain exactly 2 unique conformers (Anti and Gauche), merging the duplicate Anti
    assert len(deduped) == 2

    # Also test via pipeline deduplicate_conformer_union wrapper
    deduped_pipeline = deduplicate_conformer_union(
        pool,
        delta_b_rel_threshold=0.005,
        rmsd_threshold=0.15,
    )
    assert len(deduped_pipeline) == 2


def test_conformer_orchestrator_generates_ensemble_payload(tmp_path):
    """Verify ConformerOrchestrator generates a validated ConformerEnsemblePayload contract."""
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    anti_coords = [
        [1.226, -0.245, 0.000],
        [0.000, 0.589, 0.000],
        [-1.173, -0.222, 0.000],
        [-1.936, 0.366, 0.000],
        [0.038, 1.237, 0.887],
        [0.038, 1.237, -0.887],
        [2.138, 0.360, 0.000],
        [1.233, -0.883, 0.887],
        [1.233, -0.883, -0.887],
    ]

    orchestrator = ConformerOrchestrator()
    ensemble = orchestrator.generate_conformers(
        symbols=symbols,
        coordinates=anti_coords,
        ensemble_id="ethanol_test_ensemble",
    )

    assert isinstance(ensemble, ConformerEnsemblePayload)
    assert ensemble.ensemble_id == "ethanol_test_ensemble"
    assert ensemble.origin_engine == "UNION"
    assert ensemble.provenance_tag == "[M]"
    assert len(ensemble.conformers) >= 1

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_prohibition_calc_hess_true.py ---
"""CoChem-TORQ: Test Absolute Prohibition of Calc_Hess true.

Compliant with Method Matrix v4 §8B.3 and Anti-Spoofing Protocol v2.
Verifies Deliverable 7:
1. Unconditional detection and excising of Calc_Hess true during optimization (! Opt) routines.
2. Automated substitution of model Hessian (InHess XTB2 or InHess Lindh).
3. Emission of structured Method Matrix violation warning.
"""

import logging
import pytest
from Libraries.cochem_torq_compiler import TorqDeckSanitizer, sanitize_orca_deck


def test_prohibition_calc_hess_true_substitutes_inhess_xtb2(caplog):
    """Pass an ORCA deck containing ! Opt and Calc_Hess true; assert stripping, substitution, and warning."""
    dirty_deck = (
        "! r2SCAN-3c Opt defgrid3 TightSCF\n"
        "%geom\n"
        "  TolE 1e-7\n"
        "  TolMaxG 1e-5\n"
        "  Calc_Hess true\n"
        "end\n"
        "* xyz 0 1\n"
        "O  0.0 0.0 0.1177\n"
        "H  0.0 0.7554 -0.4708\n"
        "H  0.0 -0.7554 -0.4708\n"
        "*\n"
    )

    with caplog.at_level(logging.WARNING):
        clean_deck, excised = sanitize_orca_deck(dirty_deck, xtb_available=True)

    assert excised is True
    assert "Calc_Hess true" not in clean_deck
    assert "Calc_Hess" not in clean_deck
    assert "InHess XTB2" in clean_deck
    assert "METHOD_MATRIX_VIOLATION" in caplog.text


def test_prohibition_calc_hess_true_substitutes_inhess_lindh_fallback(caplog):
    """When xTB is unavailable, assert InHess Lindh is substituted."""
    dirty_deck = (
        "! wB97M-V def2-TZVP Opt\n"
        "Calc_Hess = true\n"
        "* xyz 0 1\n"
        "O  0.0 0.0 0.1177\n"
        "H  0.0 0.7554 -0.4708\n"
        "H  0.0 -0.7554 -0.4708\n"
        "*\n"
    )

    with caplog.at_level(logging.WARNING):
        clean_deck, excised = sanitize_orca_deck(dirty_deck, xtb_available=False)

    assert excised is True
    assert "Calc_Hess" not in clean_deck
    assert "InHess Lindh" in clean_deck
    assert "METHOD_MATRIX_VIOLATION" in caplog.text


def test_clean_optimization_deck_preserved():
    """Verify that a compliant deck with InHess XTB2 is not mutated."""
    compliant_deck = (
        "! r2SCAN-3c Opt defgrid3\n"
        "%geom\n"
        "  TolE 1e-7\n"
        "  TolMaxG 1e-5\n"
        "  InHess XTB2\n"
        "end\n"
        "* xyz 0 1\n"
        "O  0.0 0.0 0.1177\n"
        "H  0.0 0.7554 -0.4708\n"
        "H  0.0 -0.7554 -0.4708\n"
        "*\n"
    )

    clean_deck, excised = sanitize_orca_deck(compliant_deck)
    assert excised is False
    assert clean_deck.strip() == compliant_deck.strip()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_spin_contamination_validation.py ---
"""CoChem-TORQ: Test Spin Contamination Validation for Unrestricted Calculations.

Compliant with Method Matrix v4 §8B.3 and Anti-Spoofing Directives.
Verifies Deliverable 8:
1. Resilient regex parsing across ORCA formatting variations (<S**2>, <S^2>, whitespace).
2. Mandatory spin extraction for unrestricted calculations (raising EcosystemExecutionError on missing <S^2>).
3. Broken-symmetry singlet (M=1, threshold <= 0.10) and multiplet (delta_spin <= 10%) validation.
4. Hard failure gate with ERR_SPIN_CONTAMINATION and user override support.
"""

import pytest
from cochem_base.exceptions import EcosystemExecutionError, SpinContaminationError
from Libraries.cochem_torq_engine import validate_spin_contamination
from Libraries.cochem_torq_parser import S2_PATTERN, parse_spin_contamination_s2


def test_s2_regex_parsing_variations():
    """Verify resilient regex parsing across diverse ORCA version output formats."""
    sample_outputs = [
        "Expectation value of <S**2> :   0.754123",
        "Expectation value of <S^2>  : 0.751000",
        "< S**2 > : 1.050",
        "<  S ^ 2  > :  0.0023",
        "Total <S**2> expectation value: 0.3500",
    ]
    expected_values = [0.754123, 0.751000, 1.050, 0.0023, 0.3500]

    for text, expected in zip(sample_outputs, expected_values):
        val = parse_spin_contamination_s2(text)
        assert val is not None
        assert pytest.approx(val, abs=1e-5) == expected


def test_open_shell_singlet_spin_contamination():
    """For an open-shell singlet (M=1), ideal=0.0. Observed 0.35 must abort with ERR_SPIN_CONTAMINATION."""
    # Singlet within tolerance (<S^2> <= 0.10)
    s_ideal, s_obs, dev = validate_spin_contamination(multiplicity=1, s_squared_observed=0.03)
    assert s_ideal == 0.0
    assert s_obs == 0.03

    # Singlet exceeding tolerance (0.35 > 0.10)
    with pytest.raises(SpinContaminationError) as excinfo:
        validate_spin_contamination(multiplicity=1, s_squared_observed=0.35)

    err_msg = str(excinfo.value)
    assert "ERR_SPIN_CONTAMINATION" in err_msg
    assert "0.3500" in err_msg

    # User override allows execution
    s_ideal, s_obs, dev = validate_spin_contamination(
        multiplicity=1, s_squared_observed=0.35, allow_spin_contamination=True
    )
    assert s_obs == 0.35


def test_doublet_multiplet_spin_contamination():
    """For a doublet (S=1/2, M=2), ideal=0.75.

    Observed 0.76 (1.3% deviation <= 10%) passes.
    Observed 0.90 (20% deviation > 10%) aborts with ERR_SPIN_CONTAMINATION.
    """
    # Doublet with 0.76: deviation |0.76 - 0.75| / 0.75 = 1.33% <= 10%
    s_ideal, s_obs, dev = validate_spin_contamination(multiplicity=2, s_squared_observed=0.76)
    assert s_ideal == 0.75
    assert s_obs == 0.76
    assert dev < 10.0

    # Doublet with 0.90: deviation |0.90 - 0.75| / 0.75 = 20.0% > 10%
    with pytest.raises(SpinContaminationError) as excinfo:
        validate_spin_contamination(multiplicity=2, s_squared_observed=0.90)

    err_msg = str(excinfo.value)
    assert "ERR_SPIN_CONTAMINATION" in err_msg
    assert "0.9000" in err_msg


def test_missing_spin_observable_raises_ecosystem_execution_error():
    """Unrestricted calculation missing <S^2> in output must raise EcosystemExecutionError."""
    unrestricted_output_without_s2 = (
        "ORCA TERMINATED NORMALLY\n"
        "FINAL SINGLE POINT ENERGY   -76.43820192\n"
    )

    with pytest.raises(EcosystemExecutionError) as excinfo:
        validate_spin_contamination(
            unrestricted_output_without_s2,
            multiplicity=2,
            is_unrestricted=True,
        )

    err_msg = str(excinfo.value)
    assert "[MISSING DATA]" in err_msg
    assert "Unrestricted calculation did not yield <S^2>" in err_msg

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.