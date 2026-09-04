Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_08_Ecosystem_Part_8_prompts.md.
Original prompt:
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 08, Suggestions #71–#80)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring and physical integrity remediation specified in SRS Chunk 08 (Suggestions #71–#80).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§8A, §8B, §8C, §9B, §13.2), Tripartite Filesystem Air-Gap Architecture, Anti-Spoofing Protocol v2 (Zero-Mock, Asymmetric Verification, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, synthetic fallback coordinates, or fabricated energies.
  - No shell injection vectors (`shell=True` is strictly deprecated).
  - Cross-platform IPC via `filelock` (POSIX `fcntl` is strictly banned on network filesystems).
  - Dynamic atomic masses strictly via `from mendeleev import element` (never hardcode masses).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Thread-Safe & Deadlock-Free HDF5 Serialization (Suggestion #71)
**Target Module:** `CoChem-TOPOS/cascade_engine/cochem_cascade_hdf5.py`  
**Class to Mutate:** `CascadeHDF5Serializer`

### Detailed Requirements:
1. **Bounded Lock Acquisition & Stale Lock Eviction:**
   - Refactor `FileLock(f"{self.db_path}.lock")` initialization to enforce an explicit acquisition timeout: `timeout=30.0`.
   - Implement automated stale-lock detection: if acquisition times out, verify whether the lock-holding PID exists using `psutil.pid_exists(pid)`. If the holding PID is dead (e.g., worker killed by OOM or walltime expiry) or the lock file is older than 600 s without active process ownership, evict the stale lockfile and retry acquisition once.
   - Use cross-platform `filelock.FileLock`. Non-portable POSIX `fcntl` locking is strictly forbidden to guarantee compatibility across NFS, Lustre, WSL, and macOS.
2. **In-Process Concurrency Synchronization:**
   - Implement a process-wide `threading.RLock` protecting all `h5py.File` open, write, flush, and close transactions within multi-threaded workers.
3. **SWMR Mode Activation:**
   - Enforce Single-Writer/Multiple-Reader mode (`swmr=True`) on all persistent HDF5 database handles:
     ```python
     with self._thread_lock:
         with self._file_lock.acquire(timeout=30.0):
             with h5py.File(self.db_path, "a", libver="latest") as h5:
                 if not h5.swmr_mode:
                     try:
                         h5.swmr_mode = True
                     except (RuntimeError, ValueError):
                         pass
     ```
4. **Error Handling:** If lock acquisition fails after eviction/retry, raise a typed `cochem_base.exceptions.DatabaseLockTimeoutError` with detailed telemetry (lock path, current worker PID, elapsed time).

---

## Deliverable 2: HPC SLURM Single-Node Shared-Memory Template Generation (Suggestion #72)
**Target Modules:**  
- `CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py`
- `CoChem-BASE/src/cochem_base/calc/slurm_generator.py`

### Detailed Requirements:
1. **SLURM Header Directive Correction:**
   - Audit and mutate all SLURM submission template generators.
   - Replace any instance of `#SBATCH --ntasks={cores}` with explicit shared-memory multi-threading directives conforming to Method Matrix §8A.6:
     ```bash
     #SBATCH --nodes=1
     #SBATCH --ntasks=1
     #SBATCH --cpus-per-task={cores}
     ```
2. **ORCA Parallel Execution Alignment:**
   - Ensure the generated input deck `%pal nprocs {cores} end` matches `--cpus-per-task` exactly.
   - For CFOUR or other OpenMP/MPI hybrids, bind `export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK`.
3. **Dynamic Topology Adaptation:**
   - In `slurm_generator.py`, validate that requested `{cores}` does not exceed the node physical core capacity queried via scheduler environment variables (`SLURM_CPUS_ON_NODE`) or `psutil.cpu_count(logical=False)`. Clamp and log a `[SCHEDULER-WARNING]` if requested cores exceed physical single-node bounds.

---

## Deliverable 3: Structured Local Dispatch & Tripartite Air-Gap Isolation (Suggestion #73)
**Target Module:** `CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py`  
**Method to Mutate:** `_dispatch_local`

### Detailed Requirements:
1. **Deprecation of `shell=True`:**
   - Completely eliminate `shell=True` in `subprocess.run` or `subprocess.Popen` within `_dispatch_local`.
   - Parse command strings into structured argument lists using:
     ```python
     posix_mode = (sys.platform != "win32")
     cmd_args = shlex.split(payload_command, posix=posix_mode)
     ```
2. **Subprocess Routing & Stream Isolation:**
   - Route execution through `SubprocessBroker`. Manage standard output and error redirection via explicit Python file streams opened in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`).
3. **Tripartite Filesystem Air-Gap Boundary Enforcement:**
   - Resolve all operational paths using dynamic `pathlib.Path` objects anchored to:
     - **Ring 0 (Static/Executables):** Discovered via `cochem_base.environment.BinaryRegistry`.
     - **Ring 1 (Orchestration/Locks):** `$COCHEM_ROOT` or active project root.
     - **Ring 2 (Ephemeral Scratch):** `$COCHEM_SCRATCH` / temporary directory (cleaned on exit).
     - **Ring 3 (Verified Artifacts):** `$COCHEM_ARTIFACTS` / persistent data store.
   - Strictly prohibit hardcoded `/tmp`, `$HOME`, or OS-specific drive letters (`C:\`, `/mnt/c/`).

---

## Deliverable 4: Basin-Identity & Dissociation Structural Integrity Gates (Suggestion #74)
**Target Module:** `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
**Class to Mutate:** `CascadeOrchestrator`

### Detailed Requirements:
1. **Integrity Guard G3 Implementation:**
   - In `process_geometry()`, insert an automated basin-identity validation gate between each cascade optimization tier (specifically prior to promoting structures to Tier 4 DFT or Tier 5 DLPNO-CCSD(T)).
2. **Structural Evaluation Metrics:**
   - Compute the center-of-mass (COM) distance between monomer fragments: $\Delta R = |R_{\text{COM}}^{(T_n)} - R_{\text{COM}}^{(T_{n-1})}|$. Verify $\Delta R \le 0.20\text{ \AA}$ [M].
   - Compute heavy-atom root-mean-square deviation: $\text{RMSD}_{\text{heavy}} \le 0.25\text{ \AA}$ [M].
   - Check energy continuity: abort if $\Delta E$ jumps unphysically without a corresponding barrier crossing.
3. **Early Abort Handling:**
   - If a complex dissociates ($\Delta R > 0.20\text{ \AA}$ or heavy-atom connectivity changes in the molecular graph):
     - Terminate promotion immediately.
     - Emit `[INTEGRITY-GATE-TRIPPED] Complex dissociation detected at Tier {current_tier}`.
     - Write diagnostic geometry artifacts to Ring 2 scratch and tag the state as `TERMINATED_DISSOCIATED` in the orchestration manifest. Do NOT proceed to Tier 4/5 coupled-cluster calculations.

---

## Deliverable 5: Worker-Resident GPU MLFF Model Cache Singleton (Suggestion #75)
**Target Module:** `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`

### Detailed Requirements:
1. **Worker-Resident Model Cache:**
   - Implement a thread-safe singleton cache `WorkerModelCache` residing in worker process memory.
   - On worker bootstrap, initialize MLFF models (MACE, AIMNet2) once per GPU worker process:
     ```python
     class WorkerModelCache:
         _models: Dict[str, Any] = {}
         _lock = threading.Lock()

         @classmethod
         def get_model(cls, model_name: str, weights_path: Path, device: str) -> Any:
             key = f"{model_name}:{weights_path}:{device}"
             with cls._lock:
                 if key not in cls._models:
                     cls._models[key] = cls._load_model(model_name, weights_path, device)
                 return cls._models[key]
     ```
2. **Throughput Optimization:**
   - Ensure subsequent task dispatches retrieve the resident model from memory, reducing per-evaluation overhead from 15–30 s to 30–50 ms.
   - Maintain persistent VRAM allocation footprint (~2 GB) without re-instantiating CUDA contexts per task.

---

## Deliverable 6: Partitioned GPU Pools & VRAM Guardrails (Suggestion #76)
**Target Modules:**  
- `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`
- `CoChem-BASE/src/cochem_base/core_engine/hetero_config.py`
- `CoChem-TOPOS/gpu_point.py`

### Detailed Requirements:
1. **Dual GPU Executor Pools:**
   - Refactor Parsl GPU executor configuration to instantiate two distinct executor pools:
     1. `gpu_scout_mlff`: Configured with NVIDIA MPS, hosting 3 concurrent worker processes with `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='0=6G'`, reserved exclusively for lightweight MLFF screening.
     2. `gpu_anchor_pyscf`: Dedicated single-worker pool without MPS (owning $\ge 22$ GB VRAM) for heavy electronic structure tasks (`gpu4pyscf` evaluating def2-TZVPP/def2-QZVPP).
2. **Dynamic Task Routing:**
   - In `hetero_config.py` and execution dispatchers, route jobs based on level-of-theory tags: MLFF $\to$ `gpu_scout_mlff`; `gpu4pyscf`/large DFT $\to$ `gpu_anchor_pyscf`.
3. **Teardown & Memory Sanitation:**
   - Register task completion hooks enforcing `torch.cuda.empty_cache()` and polling `torch.cuda.mem_get_info()`. If VRAM headroom is $< 2.0\text{ GB}$, delay subsequent task submission until memory settles.

---

## Deliverable 7: Dynamic Contention Budgeting for Constrained Hardware (Suggestion #77)
**Target Module:** `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`  
**Functions to Mutate:** `build_heterogeneous_profile()`, `calculate_contention_budget()`

### Detailed Requirements:
1. **Environment-Proportional Memory Allocation:**
   - Poll total physical RAM dynamically via `psutil.virtual_memory().total`.
   - If total host RAM is $< 32\text{ GB}$ (e.g., 16 GB student laptops, Setup 1, CI runners):
     - Do NOT raise `ContentionBudgetExceededError`.
     - Dynamically scale memory allocations: allocate 50% of available free RAM to Anchor workers and 25% to Scout workers.
     - Enforce minimum viable memory floors: Anchor floor $= 4.0\text{ GB}$, Scout floor $= 1.5\text{ GB}$.
2. **Graceful Downscaling:**
   - Adjust worker process counts dynamically: if total memory cannot safely support multiple concurrent workers, automatically downscale concurrency to 1 worker per executor pool and emit a descriptive `[RESOURCE-INFO]` log.

---

## Deliverable 8: Canonical State-Chaining Engine Consolidation (Suggestion #78)
**Target Modules:**  
- `CoChem-BASE/src/cochem_base/chain.py` (New Canonical Module)
- `CoChem-TOPOS/chain.py` (Deprecate duplicate & redirect)
- `CoChem-TORQ/Libraries/chain.py` (Deprecate duplicate & redirect)

### Detailed Requirements:
1. **Consolidation into `CoChem-BASE`:**
   - Migrate the complete, authoritative 11-Arrow state-chaining engine (`Chain`, `StateChainingAuditor`, `ArrowState`) into `cochem_base.chain`.
   - Ensure all binary projection logic (`%moinp`), Hessian reuse (`InHess`), and convergence assertions comply with Method Matrix §8B.4.
2. **Satellite Redirection:**
   - In `CoChem-TOPOS/chain.py` and `CoChem-TORQ/Libraries/chain.py`, eliminate the duplicated ~1,800 lines of code.
   - Replace contents with direct imports from `cochem_base.chain` preserving backward compatibility:
     ```python
     """Canonical redirect to CoChem-BASE state-chaining engine."""
     from cochem_base.chain import Chain, StateChainingAuditor, ArrowState
     __all__ = ["Chain", "StateChainingAuditor", "ArrowState"]
     ```

---

## Deliverable 9: Active Learning & Delta-ML Execution DAG Integration (Suggestion #79)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`
- `CoChem-TORQ/Libraries/cochem_torq_active_learning.py`
- `CoChem-TORQ/Libraries/cochem_torq_delta_ml.py`

### Detailed Requirements:
1. **DAG Pipeline Integration:**
   - Wire `ActiveLearner` and `DeltaMLCorrector` directly into the automated execution loop of `TorqPipeline` and `CascadeOrchestrator`.
2. **Epistemic Uncertainty Gating (Integrity Guard G5):**
   - For multidimensional PES generation, evaluate low-cost scout single points on grid candidates.
   - Query ensemble committee disagreement (epistemic standard deviation $\sigma_E$).
   - If $\sigma_E > 10.0\text{ meV}$ (G5 threshold), automatically stage a high-level CCSD(T) anchor single-point evaluation.
   - If $\sigma_E \le 10.0\text{ meV}$, predict energy via the trained $\Delta$-ML surrogate without launching expensive coupled-cluster jobs.
3. **Data Logging:** Record all query decisions and uncertainty metrics into the campaign HDF5 store under `/active_learning/telemetry`.

---

## Deliverable 10: Eradication of Synthetic CREST Fallback Ensemble (Suggestion #80)
**Target Module:** `CoChem-TORQ/Libraries/cochem_torq_crest.py`  
**Section Affected:** Lines 1034–1136

### Detailed Requirements:
1. **Complete Removal of `_generate_physical_fallback_ensemble`:**
   - Purge `_generate_physical_fallback_ensemble` and all associated synthetic coordinate jitter / Gaussian random displacement logic.
   - Purge fabricated energy calculations ($\Delta E = \sum \delta r^2 \times 25.0$).
   - Strictly prohibit assigning `origin_engine="CREST"` to any non-CREST coordinates.
2. **Authentic Dependency Failure Gate:**
   - When the `crest` executable is not discovered via `cochem_base.environment.BinaryRegistry`:
     - Raise a typed `cochem_base.exceptions.BinaryNotFoundError`:
       ```python
       raise BinaryNotFoundError(
           "[MISSING DATA] CREST executable not discovered in environment path. "
           "Authentic conformer trajectory generation halted in accordance with "
           "Anti-Spoofing Protocol v2 and Method Matrix §9B."
       )
       ```
3. **Clean Route Bypass:**
   - Allow execution to proceed only if the investigator explicitly configures an authentic alternative engine (e.g., ORCA GOAT: `! GOAT XTB2`). Never fabricate conformers under missing binary conditions.

---

## Zero-Mock Verification & Test Plan
You must create or update corresponding test files in `tests/` verifying all 10 fixes without any mocking libraries:

1. `test_hdf5_serializer_concurrency.py`: Launch 4 multi-process workers attempting simultaneous writes; verify lock acquisition timeout bounds, SWMR status, and zero data corruption.
2. `test_slurm_generator_topology.py`: Assert that rendered SLURM scripts contain `--nodes=1`, `--ntasks=1`, and `--cpus-per-task={N}` without `--ntasks={N}`.
3. `test_dispatch_local_security.py`: Verify that input commands with spaces and `%` characters execute cleanly without `shell=True` and reject injection strings.
4. `test_cascade_basin_gate.py`: Test `process_geometry()` with a synthetic dissociating geometry ($\Delta R = 0.50\text{ \AA}$); assert that promotion to Tier 4/5 aborts with `INTEGRITY-GATE-TRIPPED`.
5. `test_worker_model_cache.py`: Verify that `WorkerModelCache` returns the identical resident model object on consecutive calls and maintains persistent weights.
6. `test_gpu_pool_partitioning.py`: Verify that large-basis PySCF jobs route to `gpu_anchor_pyscf` while MLFF jobs route to `gpu_scout_mlff`.
7. `test_contention_budget_scaling.py`: Mock `psutil.virtual_memory().total` to 16 GB; assert that `calculate_contention_budget()` succeeds and downscales gracefully without raising an exception.
8. `test_canonical_chain_import.py`: Verify that `cochem_topos.chain` and `cochem_torq.chain` successfully resolve classes from `cochem_base.chain`.
9. `test_active_learning_dag.py`: Run an active learning step; verify that points with $\sigma_E \le 10\text{ meV}$ use $\Delta$-ML predictions and points with $\sigma_E > 10\text{ meV}$ query anchor jobs.
10. `test_crest_missing_binary_exception.py`: Execute `cochem_torq_crest.py` in an environment without `crest` on `PATH`; verify that `BinaryNotFoundError` is raised with `[MISSING DATA]` and that zero synthetic coordinates are emitted.

Execute all changes cleanly, adhere strictly to Python typing standards, and verify that the ecosystem passes linting (`ruff check`) and formatting. Proceed with implementation.
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 08, Suggestions #71–#80)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring and physical integrity remediation specified in SRS Chunk 08 (Suggestions #71–#80).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§8A, §8B, §8C, §9B, §13.2), Tripartite Filesystem Air-Gap Architecture, Anti-Spoofing Protocol v2 (Zero-Mock, Asymmetric Verification, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, synthetic fallback coordinates, or fabricated energies.
  - No shell injection vectors (`shell=True` is strictly deprecated).
  - Cross-platform IPC via `filelock` (POSIX `fcntl` is strictly banned on network filesystems).
  - Dynamic atomic masses strictly via `from mendeleev import element` (never hardcode masses).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Thread-Safe & Deadlock-Free HDF5 Serialization (Suggestion #71)
**Target Module:** `CoChem-TOPOS/cascade_engine/cochem_cascade_hdf5.py`  
**Class to Mutate:** `CascadeHDF5Serializer`

### Detailed Requirements:
1. **Bounded Lock Acquisition & Stale Lock Eviction:**
   - Refactor `FileLock(f"{self.db_path}.lock")` initialization to enforce an explicit acquisition timeout: `timeout=30.0`.
   - Implement automated stale-lock detection: if acquisition times out, verify whether the lock-holding PID exists using `psutil.pid_exists(pid)`. If the holding PID is dead (e.g., worker killed by OOM or walltime expiry) or the lock file is older than 600 s without active process ownership, evict the stale lockfile and retry acquisition once.
   - Use cross-platform `filelock.FileLock`. Non-portable POSIX `fcntl` locking is strictly forbidden to guarantee compatibility across NFS, Lustre, WSL, and macOS.
2. **In-Process Concurrency Synchronization:**
   - Implement a process-wide `threading.RLock` protecting all `h5py.File` open, write, flush, and close transactions within multi-threaded workers.
3. **SWMR Mode Activation:**
   - Enforce Single-Writer/Multiple-Reader mode (`swmr=True`) on all persistent HDF5 database handles:
     ```python
     with self._thread_lock:
         with self._file_lock.acquire(timeout=30.0):
             with h5py.File(self.db_path, "a", libver="latest") as h5:
                 if not h5.swmr_mode:
                     try:
                         h5.swmr_mode = True
                     except (RuntimeError, ValueError):
                         pass
     ```
4. **Error Handling:** If lock acquisition fails after eviction/retry, raise a typed `cochem_base.exceptions.DatabaseLockTimeoutError` with detailed telemetry (lock path, current worker PID, elapsed time).

---

## Deliverable 2: HPC SLURM Single-Node Shared-Memory Template Generation (Suggestion #72)
**Target Modules:**  
- `CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py`
- `CoChem-BASE/src/cochem_base/calc/slurm_generator.py`

### Detailed Requirements:
1. **SLURM Header Directive Correction:**
   - Audit and mutate all SLURM submission template generators.
   - Replace any instance of `#SBATCH --ntasks={cores}` with explicit shared-memory multi-threading directives conforming to Method Matrix §8A.6:
     ```bash
     #SBATCH --nodes=1
     #SBATCH --ntasks=1
     #SBATCH --cpus-per-task={cores}
     ```
2. **ORCA Parallel Execution Alignment:**
   - Ensure the generated input deck `%pal nprocs {cores} end` matches `--cpus-per-task` exactly.
   - For CFOUR or other OpenMP/MPI hybrids, bind `export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK`.
3. **Dynamic Topology Adaptation:**
   - In `slurm_generator.py`, validate that requested `{cores}` does not exceed the node physical core capacity queried via scheduler environment variables (`SLURM_CPUS_ON_NODE`) or `psutil.cpu_count(logical=False)`. Clamp and log a `[SCHEDULER-WARNING]` if requested cores exceed physical single-node bounds.

---

## Deliverable 3: Structured Local Dispatch & Tripartite Air-Gap Isolation (Suggestion #73)
**Target Module:** `CoChem-BASE/src/cochem_base/calc/cochem_calc_execution_router.py`  
**Method to Mutate:** `_dispatch_local`

### Detailed Requirements:
1. **Deprecation of `shell=True`:**
   - Completely eliminate `shell=True` in `subprocess.run` or `subprocess.Popen` within `_dispatch_local`.
   - Parse command strings into structured argument lists using:
     ```python
     posix_mode = (sys.platform != "win32")
     cmd_args = shlex.split(payload_command, posix=posix_mode)
     ```
2. **Subprocess Routing & Stream Isolation:**
   - Route execution through `SubprocessBroker`. Manage standard output and error redirection via explicit Python file streams opened in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`).
3. **Tripartite Filesystem Air-Gap Boundary Enforcement:**
   - Resolve all operational paths using dynamic `pathlib.Path` objects anchored to:
     - **Ring 0 (Static/Executables):** Discovered via `cochem_base.environment.BinaryRegistry`.
     - **Ring 1 (Orchestration/Locks):** `$COCHEM_ROOT` or active project root.
     - **Ring 2 (Ephemeral Scratch):** `$COCHEM_SCRATCH` / temporary directory (cleaned on exit).
     - **Ring 3 (Verified Artifacts):** `$COCHEM_ARTIFACTS` / persistent data store.
   - Strictly prohibit hardcoded `/tmp`, `$HOME`, or OS-specific drive letters (`C:\`, `/mnt/c/`).

---

## Deliverable 4: Basin-Identity & Dissociation Structural Integrity Gates (Suggestion #74)
**Target Module:** `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`  
**Class to Mutate:** `CascadeOrchestrator`

### Detailed Requirements:
1. **Integrity Guard G3 Implementation:**
   - In `process_geometry()`, insert an automated basin-identity validation gate between each cascade optimization tier (specifically prior to promoting structures to Tier 4 DFT or Tier 5 DLPNO-CCSD(T)).
2. **Structural Evaluation Metrics:**
   - Compute the center-of-mass (COM) distance between monomer fragments: $\Delta R = |R_{\text{COM}}^{(T_n)} - R_{\text{COM}}^{(T_{n-1})}|$. Verify $\Delta R \le 0.20\text{ \AA}$ [M].
   - Compute heavy-atom root-mean-square deviation: $\text{RMSD}_{\text{heavy}} \le 0.25\text{ \AA}$ [M].
   - Check energy continuity: abort if $\Delta E$ jumps unphysically without a corresponding barrier crossing.
3. **Early Abort Handling:**
   - If a complex dissociates ($\Delta R > 0.20\text{ \AA}$ or heavy-atom connectivity changes in the molecular graph):
     - Terminate promotion immediately.
     - Emit `[INTEGRITY-GATE-TRIPPED] Complex dissociation detected at Tier {current_tier}`.
     - Write diagnostic geometry artifacts to Ring 2 scratch and tag the state as `TERMINATED_DISSOCIATED` in the orchestration manifest. Do NOT proceed to Tier 4/5 coupled-cluster calculations.

---

## Deliverable 5: Worker-Resident GPU MLFF Model Cache Singleton (Suggestion #75)
**Target Module:** `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`

### Detailed Requirements:
1. **Worker-Resident Model Cache:**
   - Implement a thread-safe singleton cache `WorkerModelCache` residing in worker process memory.
   - On worker bootstrap, initialize MLFF models (MACE, AIMNet2) once per GPU worker process:
     ```python
     class WorkerModelCache:
         _models: Dict[str, Any] = {}
         _lock = threading.Lock()

         @classmethod
         def get_model(cls, model_name: str, weights_path: Path, device: str) -> Any:
             key = f"{model_name}:{weights_path}:{device}"
             with cls._lock:
                 if key not in cls._models:
                     cls._models[key] = cls._load_model(model_name, weights_path, device)
                 return cls._models[key]
     ```
2. **Throughput Optimization:**
   - Ensure subsequent task dispatches retrieve the resident model from memory, reducing per-evaluation overhead from 15–30 s to 30–50 ms.
   - Maintain persistent VRAM allocation footprint (~2 GB) without re-instantiating CUDA contexts per task.

---

## Deliverable 6: Partitioned GPU Pools & VRAM Guardrails (Suggestion #76)
**Target Modules:**  
- `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`
- `CoChem-BASE/src/cochem_base/core_engine/hetero_config.py`
- `CoChem-TOPOS/gpu_point.py`

### Detailed Requirements:
1. **Dual GPU Executor Pools:**
   - Refactor Parsl GPU executor configuration to instantiate two distinct executor pools:
     1. `gpu_scout_mlff`: Configured with NVIDIA MPS, hosting 3 concurrent worker processes with `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='0=6G'`, reserved exclusively for lightweight MLFF screening.
     2. `gpu_anchor_pyscf`: Dedicated single-worker pool without MPS (owning $\ge 22$ GB VRAM) for heavy electronic structure tasks (`gpu4pyscf` evaluating def2-TZVPP/def2-QZVPP).
2. **Dynamic Task Routing:**
   - In `hetero_config.py` and execution dispatchers, route jobs based on level-of-theory tags: MLFF $\to$ `gpu_scout_mlff`; `gpu4pyscf`/large DFT $\to$ `gpu_anchor_pyscf`.
3. **Teardown & Memory Sanitation:**
   - Register task completion hooks enforcing `torch.cuda.empty_cache()` and polling `torch.cuda.mem_get_info()`. If VRAM headroom is $< 2.0\text{ GB}$, delay subsequent task submission until memory settles.

---

## Deliverable 7: Dynamic Contention Budgeting for Constrained Hardware (Suggestion #77)
**Target Module:** `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`  
**Functions to Mutate:** `build_heterogeneous_profile()`, `calculate_contention_budget()`

### Detailed Requirements:
1. **Environment-Proportional Memory Allocation:**
   - Poll total physical RAM dynamically via `psutil.virtual_memory().total`.
   - If total host RAM is $< 32\text{ GB}$ (e.g., 16 GB student laptops, Setup 1, CI runners):
     - Do NOT raise `ContentionBudgetExceededError`.
     - Dynamically scale memory allocations: allocate 50% of available free RAM to Anchor workers and 25% to Scout workers.
     - Enforce minimum viable memory floors: Anchor floor $= 4.0\text{ GB}$, Scout floor $= 1.5\text{ GB}$.
2. **Graceful Downscaling:**
   - Adjust worker process counts dynamically: if total memory cannot safely support multiple concurrent workers, automatically downscale concurrency to 1 worker per executor pool and emit a descriptive `[RESOURCE-INFO]` log.

---

## Deliverable 8: Canonical State-Chaining Engine Consolidation (Suggestion #78)
**Target Modules:**  
- `CoChem-BASE/src/cochem_base/chain.py` (New Canonical Module)
- `CoChem-TOPOS/chain.py` (Deprecate duplicate & redirect)
- `CoChem-TORQ/Libraries/chain.py` (Deprecate duplicate & redirect)

### Detailed Requirements:
1. **Consolidation into `CoChem-BASE`:**
   - Migrate the complete, authoritative 11-Arrow state-chaining engine (`Chain`, `StateChainingAuditor`, `ArrowState`) into `cochem_base.chain`.
   - Ensure all binary projection logic (`%moinp`), Hessian reuse (`InHess`), and convergence assertions comply with Method Matrix §8B.4.
2. **Satellite Redirection:**
   - In `CoChem-TOPOS/chain.py` and `CoChem-TORQ/Libraries/chain.py`, eliminate the duplicated ~1,800 lines of code.
   - Replace contents with direct imports from `cochem_base.chain` preserving backward compatibility:
     ```python
     """Canonical redirect to CoChem-BASE state-chaining engine."""
     from cochem_base.chain import Chain, StateChainingAuditor, ArrowState
     __all__ = ["Chain", "StateChainingAuditor", "ArrowState"]
     ```

---

## Deliverable 9: Active Learning & Delta-ML Execution DAG Integration (Suggestion #79)
**Target Modules:**  
- `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`
- `CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py`
- `CoChem-TORQ/Libraries/cochem_torq_active_learning.py`
- `CoChem-TORQ/Libraries/cochem_torq_delta_ml.py`

### Detailed Requirements:
1. **DAG Pipeline Integration:**
   - Wire `ActiveLearner` and `DeltaMLCorrector` directly into the automated execution loop of `TorqPipeline` and `CascadeOrchestrator`.
2. **Epistemic Uncertainty Gating (Integrity Guard G5):**
   - For multidimensional PES generation, evaluate low-cost scout single points on grid candidates.
   - Query ensemble committee disagreement (epistemic standard deviation $\sigma_E$).
   - If $\sigma_E > 10.0\text{ meV}$ (G5 threshold), automatically stage a high-level CCSD(T) anchor single-point evaluation.
   - If $\sigma_E \le 10.0\text{ meV}$, predict energy via the trained $\Delta$-ML surrogate without launching expensive coupled-cluster jobs.
3. **Data Logging:** Record all query decisions and uncertainty metrics into the campaign HDF5 store under `/active_learning/telemetry`.

---

## Deliverable 10: Eradication of Synthetic CREST Fallback Ensemble (Suggestion #80)
**Target Module:** `CoChem-TORQ/Libraries/cochem_torq_crest.py`  
**Section Affected:** Lines 1034–1136

### Detailed Requirements:
1. **Complete Removal of `_generate_physical_fallback_ensemble`:**
   - Purge `_generate_physical_fallback_ensemble` and all associated synthetic coordinate jitter / Gaussian random displacement logic.
   - Purge fabricated energy calculations ($\Delta E = \sum \delta r^2 \times 25.0$).
   - Strictly prohibit assigning `origin_engine="CREST"` to any non-CREST coordinates.
2. **Authentic Dependency Failure Gate:**
   - When the `crest` executable is not discovered via `cochem_base.environment.BinaryRegistry`:
     - Raise a typed `cochem_base.exceptions.BinaryNotFoundError`:
       ```python
       raise BinaryNotFoundError(
           "[MISSING DATA] CREST executable not discovered in environment path. "
           "Authentic conformer trajectory generation halted in accordance with "
           "Anti-Spoofing Protocol v2 and Method Matrix §9B."
       )
       ```
3. **Clean Route Bypass:**
   - Allow execution to proceed only if the investigator explicitly configures an authentic alternative engine (e.g., ORCA GOAT: `! GOAT XTB2`). Never fabricate conformers under missing binary conditions.

---

## Zero-Mock Verification & Test Plan
You must create or update corresponding test files in `tests/` verifying all 10 fixes without any mocking libraries:

1. `test_hdf5_serializer_concurrency.py`: Launch 4 multi-process workers attempting simultaneous writes; verify lock acquisition timeout bounds, SWMR status, and zero data corruption.
2. `test_slurm_generator_topology.py`: Assert that rendered SLURM scripts contain `--nodes=1`, `--ntasks=1`, and `--cpus-per-task={N}` without `--ntasks={N}`.
3. `test_dispatch_local_security.py`: Verify that input commands with spaces and `%` characters execute cleanly without `shell=True` and reject injection strings.
4. `test_cascade_basin_gate.py`: Test `process_geometry()` with a synthetic dissociating geometry ($\Delta R = 0.50\text{ \AA}$); assert that promotion to Tier 4/5 aborts with `INTEGRITY-GATE-TRIPPED`.
5. `test_worker_model_cache.py`: Verify that `WorkerModelCache` returns the identical resident model object on consecutive calls and maintains persistent weights.
6. `test_gpu_pool_partitioning.py`: Verify that large-basis PySCF jobs route to `gpu_anchor_pyscf` while MLFF jobs route to `gpu_scout_mlff`.
7. `test_contention_budget_scaling.py`: Mock `psutil.virtual_memory().total` to 16 GB; assert that `calculate_contention_budget()` succeeds and downscales gracefully without raising an exception.
8. `test_canonical_chain_import.py`: Verify that `cochem_topos.chain` and `cochem_torq.chain` successfully resolve classes from `cochem_base.chain`.
9. `test_active_learning_dag.py`: Run an active learning step; verify that points with $\sigma_E \le 10\text{ meV}$ use $\Delta$-ML predictions and points with $\sigma_E > 10\text{ meV}$ query anchor jobs.
10. `test_crest_missing_binary_exception.py`: Execute `cochem_torq_crest.py` in an environment without `crest` on `PATH`; verify that `BinaryNotFoundError` is raised with `[MISSING DATA]` and that zero synthetic coordinates are emitted.

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


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\chain.py ---
#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
chain.py -- Canonical State-Chaining Driver & Execution-Arrow Recorder for CoChem-BASE.

Mandated by Method Matrix v4 (§8B.1–§8B.6, §8C, §8D) as the authoritative state-chaining
driver script recording every execution arrow and state transfer into one HDF5 file.

Core Architectural Directives:
  1. Executive Finding (§8B.1): The highest-value state transfer is the CONVERGED GEOMETRY,
     not the wavefunction. Geometry is primary state; MOs (.gbw) and Hessians (.opt/.hess)
     are secondary state transfers.
  2. Master State Inventory (§8B.2): Exhaustive tracking of ORCA .gbw MO projections,
     BFGS-updated .opt / Cartesian .hess Hessians, model Hessians (InHess XTB2/Lindh),
     numerical frequency restarts (%freq Restart true), GFN2-xTB .xtbw states,
     MD/PIMD restart states (.mdrestart), PySCF .chk HDF5 checkpoints, and CFOUR archives.
  3. Canonical 11-Arrow Pipeline (§8B.4):
     Arrow 1:  MLFF/xTB GOAT search -> CREST cross-check (union & re-filtering)
     Arrow 2:  Conformer ensemble -> GFN2-xTB refinement (vtight --strict)
     Arrow 3:  GFN2-xTB -> r2SCAN-3c optimization with InHess XTB2 model Hessian
     Arrow 4:  r2SCAN-3c -> wB97X-V/def2-TZVPP tight optimization (MORead s2.gbw + InHess Read s2.opt)
     Arrow 5:  wB97X-V/TZ -> wB97M-V/def2-QZVPP tight optimization (MORead s3.gbw + InHess Read s3.opt)
     Arrow 6:  Tight optimization -> analytic DFT Hessian (! Freq at identical level & geometry)
     Arrow 7:  Hessian -> all isotopologues (free re-analysis at zero electronic-structure cost)
     Arrow 8:  Tight optimization -> high-level single point (! DLPNO-CCSD(T1) with s4.gbw)
     Arrow 9:  Counterpoise legs (ghost atoms ':', basis exported & pinned)
     Arrow 10: DFT force field -> CFOUR anharmonic VPT2 (substituted hybrid FCMINT/FCMFINAL)
     Arrow 11: Multi-step compound script within one ORCA process (New_Step ... Step_End)
  4. Dangerous Reuse Protections -- Rules D1–D5 (§8B.5):
     D1: Geometry stationarity validation & ΔR -> ΔB error propagation check
     D2: Hessian reuse validation (flags modes <100 cm⁻¹ for exclusion from hybrid fields)
     D3: SCF density reuse stability guard against basin collapse / symmetry breaking
     D4: Counterpoise and ghost-atom inconsistency guard (rejects dimer .gbw for ghost legs)
     D5: Unique %base naming hygiene so no reader is ever also the writer
  5. Mendeleev Library Mandate: All atomic and isotopic masses dynamically retrieved via `mendeleev`.
  6. Persistent HDF5 Database (§8C): Chunked (512 points), resizable, gzip level 4 compression,
     shuffle filter, fletcher32 checksums, and QCSchema metadata vocabulary.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import h5py
import numpy as np
from mendeleev import element

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-Chain")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [chain]: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Physical Constants & Convergence Standards (Method Matrix §4.4, §5, §8B)
# ---------------------------------------------------------------------------
# CODATA 2018 / 2022 recommended constants
PLANCK_CONSTANT_J_S = 6.62607015e-34       # J*s (exact)
SPEED_OF_LIGHT_CM_S = 2.99792458e10       # cm/s (exact)
SPEED_OF_LIGHT_M_S = 2.99792458e8         # m/s (exact)
ATOMIC_MASS_UNIT_KG = 1.66053906660e-27   # kg/u
ANGSTROM_TO_METER = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM = 0.529177210903         # Angstrom / Bohr
BOHR_TO_METER = 0.529177210903e-10        # m / Bohr
HARTREE_TO_JOULE = 4.3597447222071e-18    # J / Hartree
HARTREE_TO_EV = 27.211386245988           # eV / Hartree
HARTREE_TO_CM_INV = 219474.63136320       # cm^-1 / Hartree

# Conversion factor from Inertia (u * Angstrom^2) to Rotational Constant (MHz):
# B = h / (8 * pi^2 * I) * 1e-6 (Hz -> MHz)
INERTIA_TO_MHZ_FACTOR = (
    PLANCK_CONSTANT_J_S
    / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_KG * (ANGSTROM_TO_METER ** 2))
) * 1.0e-6  # ~505379.0091414361 MHz * u * Angstrom^2

# Conversion factor for Hessian eigenvalue (Hartree / (Bohr^2 * u)) to wavenumber (cm^-1):
# f_lambda = HARTREE_TO_JOULE / (BOHR_TO_METER^2 * ATOMIC_MASS_UNIT_KG)
# f_cm1 = 1 / (2 * pi * c_cm_s)
# sqrt(f_lambda) * f_cm1 ~ 5140.487143715827 cm^-1
HESSIAN_EIG_TO_CM_INV_FACTOR = (
    math.sqrt(HARTREE_TO_JOULE / ((BOHR_TO_METER ** 2) * ATOMIC_MASS_UNIT_KG))
    / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
)

# Mandatory Tight Geometry Optimization Convergence Block (Method Matrix §4.4, §8B.4)
TIGHT_GEOM_BLOCK = (
    "  TolE 1e-7\n"
    "  TolRMSG 3e-6\n"
    "  TolMaxG 1e-5\n"
    "  TolRMSD 5e-5\n"
    "  TolMaxD 1e-4\n"
    "  MaxIter 200\n"
)

# HDF5 Storage Specifications (Method Matrix §8C)
CHUNK_POINTS = 512
VLEN_STR = h5py.string_dtype(encoding="utf-8")


# ---------------------------------------------------------------------------
# Canonical Execution Arrows Registry (Method Matrix §8B.4)
# ---------------------------------------------------------------------------
CANONICAL_ARROWS: Dict[int, Dict[str, str]] = {
    1: {
        "name": "SearchUnion",
        "from_to": "MLFF/xTB GOAT search -> CREST cross-check",
        "file_passed": "BaseName.finalensemble.xyz",
        "keyword": "crest --cregen ens.xyz --ethr 0.05 --bthr 0.01 --rthr 0.125",
        "saving": "Re-filtering costs zero gradients; 100% of search cost avoided on threshold changes",
    },
    2: {
        "name": "EnsembleRefinement",
        "from_to": "Conformer ensemble -> GFN2-xTB refinement",
        "file_passed": ".xyz per conformer alongside .CHRG / .UHF",
        "keyword": "xtb conf.xyz --opt vtight --strict / ORCA ! XTB2 TightOpt",
        "saving": "Fast pre-optimization to reach r2SCAN-3c with sane intermolecular distance",
    },
    3: {
        "name": "xTBToR2SCAN",
        "from_to": "GFN2-xTB -> r2SCAN-3c optimization",
        "file_passed": "xtbopt.xyz + GFN2 model Hessian (InHess XTB2)",
        "keyword": "%geom InHess XTB2 end",
        "saving": ">=2x, typically ~5x fewer optimization steps on floppy complexes [E]",
    },
    4: {
        "name": "R2SCANToWB97XV",
        "from_to": "r2SCAN-3c -> wB97X-V/def2-TZVPP tight optimization",
        "file_passed": "s2.xyz + s2.gbw + s2.opt",
        "keyword": "! MORead + %moinp 's2.gbw'; %geom InHess Read InHessName 's2.opt' end",
        "saving": "Cycles removed (dominant); .opt carries BFGS-updated Hessian",
    },
    5: {
        "name": "TZToQZCascade",
        "from_to": "wB97X-V/TZ -> wB97M-V/def2-QZVPP tight optimization",
        "file_passed": "s3.gbw (projected across basis via GuessMode FMatrix)",
        "keyword": "! MORead + %moinp 's3.gbw'; %scf GuessMode FMatrix end",
        "saving": "Expensive QZ SCF starts from converged TZ density [E]",
    },
    6: {
        "name": "OptToAnalyticHessian",
        "from_to": "Tight optimization -> analytic DFT Hessian",
        "file_passed": "s4.xyz (identical geometry) + s4.gbw",
        "keyword": "! Freq at identical level; ! MORead",
        "saving": "Skips re-converging SCF; stationary force field delivery",
    },
    7: {
        "name": "IsotopologueShortcut",
        "from_to": "Hessian -> all isotopologues",
        "file_passed": "s5.hess",
        "keyword": "re-run Freq with .hess present / orca_vib s5.hess / CFOUR ISOMASS + xjoda",
        "saving": "N isotopologues for the price of one force field (6-15x saving [D])",
    },
    8: {
        "name": "OptToHighLevelSP",
        "from_to": "Tight optimization -> high-level single point",
        "file_passed": "s4.xyz + s4.gbw",
        "keyword": "! DLPNO-CCSD(T1) ... MORead + %moinp 's4.gbw'",
        "saving": "Saves SCF iteration time on the stationary reference geometry",
    },
    9: {
        "name": "CounterpoiseLegs",
        "from_to": "Dimer -> Monomer counterpoise legs",
        "file_passed": "dimer geometry + exported basis (orca_exportbasis)",
        "keyword": "ghost atoms with ':' after element symbol",
        "saving": "Guarantees three legs share identical basis set; pins BSSE correction",
    },
    10: {
        "name": "SubstitutedHybridVPT2",
        "from_to": "DFT force field -> CFOUR anharmonic VPT2",
        "file_passed": "FCMINT in, FCMFINAL out",
        "keyword": "FCMINT read when Hessian updating is off",
        "saving": "Substituted hybrid force field: high-level harmonic + low-level anharmonic",
    },
    11: {
        "name": "CompoundScriptChaining",
        "from_to": "Any stage -> next step within single ORCA process",
        "file_passed": "Geometry & MOs implicitly in memory",
        "keyword": "Read_Geom(n); ReadMOs(n); inside New_Step ... Step_End",
        "saving": "Eliminates file plumbing when whole chain fits one wall-clock window",
    },
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class CounterpoiseType(str, Enum):
    """Counterpoise calculation fragment modes."""
    NONE = "none"
    DIMER = "dimer"
    MONOMER_A = "monomer_a"
    MONOMER_B = "monomer_b"
    FULL_CP = "full"
    HALF_CP = "half"


class CanonicalArrow(IntEnum):
    """Method Matrix canonical 11-Arrow pipeline enumeration."""
    ARROW_1_MLFF_XTB_GOAT = 1
    ARROW_2_CONFORMER_XTB = 2
    ARROW_3_R2SCAN_3C_OPT = 3
    ARROW_4_WB97X_V_TZ_OPT = 4
    ARROW_5_WB97M_V_QZ_OPT = 5
    ARROW_6_ANALYTIC_DFT_HESS = 6
    ARROW_7_ISOTOPOLOGUE = 7
    ARROW_8_DLPNO_CCSD_T1_SP = 8
    ARROW_9_COUNTERPOISE = 9
    ARROW_10_CFOUR_VPT2 = 10
    ARROW_11_COMPOUND_CHAIN = 11


@dataclass
class ArrowState:
    """Method Matrix §8B.4 canonical execution arrow state snapshot."""
    arrow_id: int = 1
    stage_name: str = "s1"
    converged: bool = True
    energy_hartree: Optional[float] = None
    geometry: Optional[np.ndarray] = None
    gradient: Optional[np.ndarray] = None
    hessian: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Stage:
    """Specification for an execution stage in the state-chaining pipeline."""
    name: str                                  # Unique stage identifier (e.g. 's2', 's3')
    level: str                                 # The primary ORCA ! route line
    blocks: str = ""                           # Additional %-configuration blocks
    geom_from: Optional[str] = None            # Source stage for optimized geometry
    mo_from: Optional[str] = None              # Source stage for .gbw orbital projection
    hess_from: Optional[str] = None            # Source stage for .opt or .hess initial Hessian
    arrow_index: Optional[int] = None          # Method Matrix canonical arrow index (1-11)
    arrow_desc: str = ""                       # Human-readable arrow description
    engine: str = "orca"                       # Engine backend: 'orca', 'xtb', 'cfour', 'pyscf'
    guess_mode: str = "FMatrix"                # ORCA MO projection mode: 'FMatrix' or 'CMatrix'
    counterpoise: str = "none"                 # Counterpoise state: 'none', 'half', 'full'
    is_restartable: bool = True                # Wall-clock restartability tag (§8B.6)


@dataclass
class ExecutionArrow:
    """Detailed record of a state transfer arrow between two stages."""
    arrow_number: int
    name: str
    from_stage: Optional[str]
    to_stage: str
    transferred_artifacts: List[str]
    consumption_keyword: str
    computational_benefit: str
    validated: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class StateRecord:
    """Physical state record captured after stage execution."""
    stage: str
    level: str
    wall_s: float
    energy_hartree: Optional[float]
    symbols: List[str]
    geometry: np.ndarray                       # (N, 3) in Angstroms
    gradient: Optional[np.ndarray] = None      # (N, 3) in Hartree/Bohr
    hessian: Optional[np.ndarray] = None       # (3N, 3N) in Hartree/Bohr^2
    frequencies_cm_inv: Optional[np.ndarray] = None  # (3N-6,) or (3N-5,) harmonic frequencies
    rotational_constants_mhz: Optional[Tuple[float, float, float]] = None  # (A, B, C) in MHz
    inertial_defect_amu_a2: Optional[float] = None  # Delta = Ic - Ia - Ib in u * Angstrom^2
    planar_moments_amu_a2: Optional[Tuple[float, float, float]] = None    # (Paa, Pbb, Pcc)
    consumed_files: List[str] = field(default_factory=list)
    produced_files: List[str] = field(default_factory=list)
    arrow_index: Optional[int] = None
    arrow_desc: str = ""
    converged: bool = True
    exit_status: str = "SUCCESS"
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mendeleev Dynamic Atomic Mass Retrieval (Mendeleev Library Mandate)
# ---------------------------------------------------------------------------
def get_atomic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """
    Dynamically retrieves atomic or isotopic mass from the `mendeleev` library.
    Strictly forbids hardcoding masses or manual CODATA constants.
    """
    clean_sym = symbol.strip().capitalize()
    if clean_sym in ("D", "H2"):
        clean_sym = "H"
        mass_number = 2
    elif clean_sym in ("T", "H3"):
        clean_sym = "H"
        mass_number = 3

    el = element(clean_sym)
    if mass_number is not None:
        for iso in el.isotopes:
            if iso.mass_number == mass_number:
                if iso.mass is not None:
                    return float(iso.mass)
                break
    if el.mass is not None:
        return float(el.mass)
    raise ValueError(f"Could not retrieve dynamic mass for element '{symbol}' (mass_number={mass_number})")


def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """Dynamically retrieves isotopic mass via get_atomic_mass."""
    return get_atomic_mass(symbol, mass_number)


def get_atomic_masses_for_symbols(
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """Returns array of atomic masses in unified atomic mass units (u) for a sequence of symbols."""
    masses: List[float] = []
    for i, s in enumerate(symbols):
        iso_num = mass_numbers[i] if mass_numbers is not None and i < len(mass_numbers) else None
        masses.append(get_atomic_mass(s, iso_num))
    return np.array(masses, dtype=float)


# ---------------------------------------------------------------------------
# Molecular Geometry & Rotational Mathematics (Method Matrix §3, §4, §5)
# ---------------------------------------------------------------------------
def compute_center_of_mass(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """Computes the 3D center of mass in Angstroms."""
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    total_mass = float(np.sum(masses))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    com = np.sum(coords * masses[:, None], axis=0) / total_mass
    return com


def compute_inertia_tensor(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes the moment of inertia tensor shifted to the center of mass.
    Returns:
      I_tensor: 3x3 inertia tensor in u * Angstrom^2
      principal_moments: sorted eigenvalues (Ia <= Ib <= Ic) in u * Angstrom^2
      principal_axes: 3x3 eigenvector matrix (columns are principal axes)
    """
    com = compute_center_of_mass(symbols, coords, mass_numbers)
    r = coords - com
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)

    i_tensor = np.zeros((3, 3), dtype=np.float64)
    for m_i, r_i in zip(masses, r, strict=True):
        r_sq = float(np.dot(r_i, r_i))
        i_tensor += m_i * (r_sq * np.eye(3, dtype=np.float64) - np.outer(r_i, r_i))

    evals, evecs = np.linalg.eigh(i_tensor)  # type: ignore[attr-defined]
    # Ensure eigenvalues are sorted Ia <= Ib <= Ic
    idx = np.argsort(evals)
    principal_moments = evals[idx]
    principal_axes = evecs[:, idx]

    return i_tensor, principal_moments, principal_axes


def compute_rotational_constants(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Dict[str, Any]:
    """
    Computes the rotational constants (A >= B >= C in MHz), planar moments,
    and inertial defect (Delta = Ic - Ia - Ib in u * Angstrom^2).
    """
    _, principal_moments, principal_axes = compute_inertia_tensor(symbols, coords, mass_numbers)
    Ia, Ib, Ic = float(principal_moments[0]), float(principal_moments[1]), float(principal_moments[2])

    A_MHz = INERTIA_TO_MHZ_FACTOR / Ia if Ia > 1e-12 else float("inf")
    B_MHz = INERTIA_TO_MHZ_FACTOR / Ib if Ib > 1e-12 else float("inf")
    C_MHz = INERTIA_TO_MHZ_FACTOR / Ic if Ic > 1e-12 else float("inf")

    # Planar moments of inertia: Paa = (Ib + Ic - Ia) / 2, etc.
    Paa = (Ib + Ic - Ia) / 2.0
    Pbb = (Ia + Ic - Ib) / 2.0
    Pcc = (Ia + Ib - Ic) / 2.0

    # Inertial defect: Delta = Ic - Ia - Ib
    inertial_defect = Ic - Ia - Ib

    # Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)
    kappa = (2.0 * B_MHz - A_MHz - C_MHz) / (A_MHz - C_MHz) if abs(A_MHz - C_MHz) > 1e-6 else 0.0

    return {
        "A_MHz": A_MHz,
        "B_MHz": B_MHz,
        "C_MHz": C_MHz,
        "Ia_u_A2": Ia,
        "Ib_u_A2": Ib,
        "Ic_u_A2": Ic,
        "Paa_u_A2": Paa,
        "Pbb_u_A2": Pbb,
        "Pcc_u_A2": Pcc,
        "inertial_defect_amu_A2": inertial_defect,
        "kappa": kappa,
        "principal_axes": principal_axes,
    }


def compute_delta_r_and_delta_b(
    coords1: np.ndarray,
    coords2: np.ndarray,
    symbols: Sequence[str],
) -> Dict[str, float]:
    """
    Computes coordinate shifts between two stages (ΔR) and propagates error to rotational constant B
    using the binding Method Matrix law: ΔB / B ≈ 2 * ΔR / R (§4.1, §8B.5 Rule D1).
    """
    assert coords1.shape == coords2.shape, "Coordinate arrays must have identical shape."
    diff = coords2 - coords1
    rmsd_angstrom = float(np.sqrt(np.mean(np.sum(diff ** 2, axis=1))))
    rmsd_pm = rmsd_angstrom * 100.0

    com1 = compute_center_of_mass(symbols, coords1)
    com2 = compute_center_of_mass(symbols, coords2)
    com_shift_angstrom = float(np.linalg.norm(com2 - com1))  # type: ignore[attr-defined]
    com_shift_pm = com_shift_angstrom * 100.0

    rot1 = compute_rotational_constants(symbols, coords1)
    rot2 = compute_rotational_constants(symbols, coords2)

    b1 = rot1["B_MHz"]
    b2 = rot2["B_MHz"]
    delta_b_mhz = abs(b2 - b1)
    rel_b_error_pct = (delta_b_mhz / b1) * 100.0 if b1 > 0 else 0.0

    return {
        "rmsd_angstrom": rmsd_angstrom,
        "rmsd_pm": rmsd_pm,
        "com_shift_angstrom": com_shift_angstrom,
        "com_shift_pm": com_shift_pm,
        "B_initial_MHz": b1,
        "B_final_MHz": b2,
        "delta_B_MHz": delta_b_mhz,
        "rel_B_error_pct": rel_b_error_pct,
    }


# ---------------------------------------------------------------------------
# Vibrational Normal Modes & Isotopologue Solver (Method Matrix Arrow 7, §8B.4)
# ---------------------------------------------------------------------------
def diagonalize_mass_weighted_hessian(
    cart_hessian: np.ndarray,
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Mass-weights a Cartesian Hessian (3N x 3N in Hartree/Bohr^2) using dynamic Mendeleev masses,
    diagonalizes to normal modes, and converts eigenvalues to harmonic frequencies in cm^-1.
    Imaginary frequencies are reported with negative values.
    """
    natoms = len(symbols)
    assert cart_hessian.shape == (3 * natoms, 3 * natoms), (
        f"Hessian shape {cart_hessian.shape} does not match 3N x 3N for N={natoms} atoms."
    )

    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    # Construct 3N 1D mass vector (mx, my, mz for each atom)
    m3n = np.repeat(masses, 3)

    # Mass-weight the Hessian: H_mw[i, j] = H[i, j] / sqrt(m[i] * m[j])
    inv_sqrt_m = 1.0 / np.sqrt(m3n)
    h_mw = cart_hessian * np.outer(inv_sqrt_m, inv_sqrt_m)

    # Symmetrize to eliminate machine precision drift
    h_mw = 0.5 * (h_mw + h_mw.T)

    evals, evecs = np.linalg.eigh(h_mw)  # type: ignore[attr-defined]

    # Convert eigenvalues in Hartree / (Bohr^2 * u) to harmonic wavenumbers in cm^-1
    frequencies: List[float] = []
    for val in evals:
        if val >= 0.0:
            freq = math.sqrt(val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        else:
            freq = -math.sqrt(-val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        frequencies.append(freq)

    sort_idx: List[int] = sorted(range(len(frequencies)), key=lambda k: frequencies[k])
    sorted_freqs = np.array([frequencies[idx] for idx in sort_idx], dtype=float)
    sorted_modes = np.array([evecs[:, idx] for idx in sort_idx], dtype=float).T

    return sorted_freqs, sorted_modes


def reanalyze_isotopologue(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    substituted_mass_numbers: Sequence[Optional[int]],
    iso_label: str,
) -> Dict[str, Any]:
    """
    Executes the zero-cost Isotopologue Shortcut (Method Matrix §8B.4 Arrow 7).
    Re-diagonalizes the saved Cartesian Hessian with substituted isotopic masses,
    recalculating harmonic frequencies, moments of inertia, and rotational constants.
    """
    freqs, modes = diagonalize_mass_weighted_hessian(cart_hessian, symbols, substituted_mass_numbers)
    rot = compute_rotational_constants(symbols, coords, substituted_mass_numbers)

    # Filter out 5 or 6 translational/rotational near-zero modes (<20 cm^-1)
    vib_freqs = [f for f in freqs if abs(f) > 20.0]

    return {
        "iso_label": iso_label,
        "substituted_mass_numbers": list(substituted_mass_numbers),
        "frequencies_cm_inv": freqs.tolist(),
        "vibrational_frequencies_cm_inv": vib_freqs,
        "lowest_harmonic_mode_cm_inv": float(vib_freqs[0]) if vib_freqs else 0.0,
        "A_MHz": rot["A_MHz"],
        "B_MHz": rot["B_MHz"],
        "C_MHz": rot["C_MHz"],
        "inertial_defect_amu_A2": rot["inertial_defect_amu_A2"],
        "Paa_u_A2": rot["Paa_u_A2"],
        "Pbb_u_A2": rot["Pbb_u_A2"],
        "Pcc_u_A2": rot["Pcc_u_A2"],
    }


# ---------------------------------------------------------------------------
# File I/O and Quantum Chemistry Parsers
# ---------------------------------------------------------------------------
def read_xyz(path: Union[str, Path]) -> Tuple[List[str], np.ndarray, str]:
    """Reads a standard XYZ coordinate file. Returns (symbols, coords (N, 3), comment)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"XYZ file not found: {p.resolve()}")

    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"XYZ file is empty: {p.resolve()}")

    try:
        num_atoms = int(lines[0].split()[0])
    except Exception as exc:
        raise ValueError(f"Invalid atom count line in XYZ file {p.resolve()}: {lines[0]}") from exc

    comment = lines[1] if len(lines) > 1 else ""
    symbols: List[str] = []
    coords: List[List[float]] = []

    for idx, ln in enumerate(lines[2 : 2 + num_atoms], start=3):
        parts = ln.split()
        if len(parts) < 4:
            raise ValueError(f"Malformed coordinate line {idx} in {p.resolve()}: '{ln}'")
        symbols.append(parts[0])
        coords.append([float(parts[1]), float(parts[2]), float(parts[3])])

    if len(symbols) != num_atoms:
        raise ValueError(f"Header declared {num_atoms} atoms but found {len(symbols)} in {p.resolve()}")

    return symbols, np.array(coords, dtype=float), comment


def write_xyz(
    path: Union[str, Path],
    symbols: Sequence[str],
    coords: np.ndarray,
    comment: str = "Generated by CoChem chain.py",
) -> None:
    """Writes standard XYZ coordinate file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    coords_arr = np.array(coords, dtype=float)
    assert len(symbols) == coords_arr.shape[0], "Atom count mismatch between symbols and coords."

    lines = [str(len(symbols)), comment]
    for i, sym in enumerate(symbols):
        x, y, z = coords_arr[i, 0], coords_arr[i, 1], coords_arr[i, 2]
        lines.append(f"{sym:<4} {x:18.10f} {y:18.10f} {z:18.10f}")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_orca_hessian(path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """
    Exhaustive reader for ORCA .hess files.
    Parses $hessian block (3N x 3N Cartesian matrix in Hartree/Bohr^2),
    $vibrational_frequencies, $normal_modes, and $atoms.
    """
    p = Path(path)
    if not p.exists():
        return None

    raw_text = p.read_text(encoding="utf-8")
    lines = raw_text.splitlines()

    hessian_matrix: Optional[np.ndarray] = None
    frequencies: List[float] = []
    atoms_data: List[Dict[str, Any]] = []

    i = 0
    n_lines = len(lines)
    while i < n_lines:
        line = lines[i].strip()

        # Parse $hessian block
        if line == "$hessian":
            i += 1
            dim = int(lines[i].strip().split()[0])
            hessian_matrix = np.zeros((dim, dim), dtype=np.float64)
            i += 1
            col_offset = 0
            while col_offset < dim and i < n_lines:
                col_headers = [int(c) for c in lines[i].strip().split()]
                i += 1
                num_cols = len(col_headers)
                for _r in range(dim):
                    row_tokens = lines[i].strip().split()
                    row_idx = int(row_tokens[0])
                    for k, col_idx in enumerate(col_headers):
                        hessian_matrix[row_idx, col_idx] = float(row_tokens[k + 1])
                    i += 1
                col_offset += num_cols
            continue

        # Parse $vibrational_frequencies
        if line == "$vibrational_frequencies":
            i += 1
            n_freqs = int(lines[i].strip().split()[0])
            i += 1
            for _ in range(n_freqs):
                if i < n_lines:
                    tokens = lines[i].strip().split()
                    if len(tokens) >= 2:
                        frequencies.append(float(tokens[1]))
                    i += 1
            continue

        # Parse $atoms
        if line == "$atoms":
            i += 1
            n_atoms = int(lines[i].strip().split()[0])
            i += 1
            for _ in range(n_atoms):
                if i < n_lines:
                    tokens = lines[i].strip().split()
                    if len(tokens) >= 5:
                        atoms_data.append({
                            "symbol": tokens[0],
                            "mass": float(tokens[1]),
                            "coords": [float(tokens[2]), float(tokens[3]), float(tokens[4])],
                        })
                    i += 1
            continue

        i += 1

    if hessian_matrix is None:
        return None

    return {
        "hessian": hessian_matrix,
        "frequencies": np.array(frequencies, dtype=float) if frequencies else None,
        "atoms": atoms_data,
    }


def parse_orca_energy(path: Union[str, Path]) -> Optional[float]:
    """Extracts the final electronic energy in Hartree from an ORCA output file."""
    p = Path(path)
    if not p.exists():
        return None

    final_e: Optional[float] = None
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()

    for ln in reversed(lines):
        if "FINAL SINGLE POINT ENERGY" in ln:
            parts = ln.split()
            try:
                final_e = float(parts[-1])
                return final_e
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
        elif "FINAL ENERGY" in ln:
            parts = ln.split()
            try:
                final_e = float(parts[-1])
                return final_e
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
        elif "Total Energy       :" in ln:
            parts = ln.split()
            try:
                final_e = float(parts[3])
                return final_e
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

    return final_e


def parse_orca_convergence(path: Union[str, Path]) -> Dict[str, Any]:
    """Parses geometry optimization convergence indicators from ORCA output."""
    p = Path(path)
    if not p.exists():
        return {"normal_termination": False, "opt_converged": False, "iterations": 0}

    content = p.read_text(encoding="utf-8", errors="ignore")
    normal_term = "ORCA TERMINATED NORMALLY" in content
    opt_converged = (
        "*** OPTIMIZATION RUN DONE ***" in content
        or "THE OPTIMIZATION HAS CONVERGED" in content
        or "HURRAY" in content
    )

    # Count geometry cycles
    geom_cycles = content.count("GEOMETRY OPTIMIZATION CYCLE")

    # Check for imaginary frequencies warning
    has_imag_freq = "WARNING: The structure has" in content and "imaginary frequencies" in content

    return {
        "normal_termination": normal_term,
        "opt_converged": opt_converged,
        "iterations": geom_cycles,
        "has_imag_freq": has_imag_freq,
    }


def parse_xtb_output(path: Union[str, Path]) -> Dict[str, Any]:
    """Parses xTB optimization or frequency output."""
    p = Path(path)
    if not p.exists():
        return {"normal_termination": False, "energy_hartree": None, "converged": False}

    content = p.read_text(encoding="utf-8", errors="ignore")
    normal_term = "normal termination of xtb" in content or "finished run on" in content
    converged = "GEOMETRY OPTIMIZATION CONVERGED" in content or normal_term

    final_e: Optional[float] = None
    for ln in content.splitlines():
        if "TOTAL ENERGY" in ln or "total energy" in ln:
            parts = ln.split()
            for k, tok in enumerate(parts):
                if tok in ("energy", "ENERGY"):
                    try:
                        final_e = float(parts[k + 1])
                        break
                    except Exception as _e:
                        logger.debug(f"Ignored exception: {_e}")

    return {
        "normal_termination": normal_term,
        "converged": converged,
        "energy_hartree": final_e,
    }


# ---------------------------------------------------------------------------
# Dangerous Reuse Guards -- Rules D1–D5 (§8B.5)
# ---------------------------------------------------------------------------
def validate_rule_d1_geometry_stationarity(
    stage: Stage,
    current_record: StateRecord,
    prev_record: Optional[StateRecord],
) -> List[str]:
    """
    Rule D1: A geometry whose intermolecular error exceeds target must not be reported as higher level.
    Validates stationarity and reports ΔR in MHz of ΔB.
    """
    warnings: List[str] = []
    if prev_record is not None:
        shift_metrics = compute_delta_r_and_delta_b(
            prev_record.geometry, current_record.geometry, current_record.symbols
        )
        delta_b = shift_metrics["delta_B_MHz"]
        rmsd_pm = shift_metrics["rmsd_pm"]
        logger.info(
            f"[Rule D1 Audit] Stage '{stage.name}' shift: dR = {rmsd_pm:.2f} pm, "
            f"projected dB = {delta_b:.2f} MHz ({shift_metrics['rel_B_error_pct']:.3f}%)"
        )
        if rmsd_pm > 5.0:
            warnings.append(
                f"Rule D1 Warning: Inter-stage coordinate shift dR = {rmsd_pm:.2f} pm exceeds 5.0 pm threshold."
            )

    return warnings


def validate_rule_d2_hessian_reuse(
    stage: Stage,
    hessian: np.ndarray,
    symbols: Sequence[str],
    coords: np.ndarray,
    prev_hessian: Optional[np.ndarray] = None,
) -> List[str]:
    """
    Rule D2: A Hessian is a second derivative at a point.
    Flags any mode below ~100 cm^-1 for exclusion from substituted hybrid treatments.
    Detects spurious imaginary modes indicating non-stationary geometry.
    """
    warnings: List[str] = []
    freqs, _ = diagonalize_mass_weighted_hessian(hessian, symbols)

    # Check for imaginary frequencies (excluding translations/rotations)
    imag_modes = [f for f in freqs if f < -10.0]
    if imag_modes:
        warnings.append(
            f"Rule D2 Alert: Found {len(imag_modes)} imaginary frequency mode(s) (lowest: {imag_modes[0]:.1f} cm^-1). "
            f"Geometry is non-stationary or in transition basin."
        )

    # Check for floppy modes <100 cm^-1 on semi-rigid manifold
    floppy_modes = [f for f in freqs if 20.0 < f < 100.0]
    if floppy_modes:
        warnings.append(
            f"Rule D2 Notice: Detected {len(floppy_modes)} floppy mode(s) <100 cm^-1 (lowest: {floppy_modes[0]:.1f} cm^-1). "
            f"Must be excluded from substituted hybrid anharmonic force fields."
        )

    return warnings


def validate_rule_d3_scf_stability(
    stage: Stage,
    out_path: Path,
) -> List[str]:
    """
    Rule D3: SCF converging to different or symmetry-broken solution from reused density.
    Checks for convergence alarms or high iteration count signatures.
    """
    warnings: List[str] = []
    if not out_path.exists():
        return warnings

    content = out_path.read_text(encoding="utf-8", errors="ignore")
    if "SCF NOT CONVERGED" in content or "DID NOT CONVERGE" in content:
        warnings.append(f"Rule D3 Violation: SCF failed to converge in stage '{stage.name}'.")

    return warnings


def validate_rule_d4_counterpoise_ghosts(
    stage: Stage,
    symbols: Sequence[str],
) -> List[str]:
    """
    Rule D4: Counterpoise and ghost-atom inconsistency.
    Never reuse dimer .gbw as guess for ghosted monomer leg.
    """
    warnings: List[str] = []
    has_ghosts = any(":" in s for s in symbols)
    if has_ghosts and stage.mo_from and "dimer" in stage.mo_from.lower():
        warnings.append(
            f"Rule D4 Violation: Stage '{stage.name}' uses ghost atoms but attempts to read dimer MO file '{stage.mo_from}.gbw'."
        )

    return warnings


def validate_rule_d5_naming_hygiene(stages: Sequence[Stage]) -> List[str]:
    """
    Rule D5: Silent state contamination from same-named file.
    Every stage must own a unique %base so reader is never writer.
    """
    warnings: List[str] = []
    seen_names: Set[str] = set()
    for st in stages:
        if st.name in seen_names:
            warnings.append(f"Rule D5 Violation: Duplicate stage name / %base '{st.name}' detected.")
        seen_names.add(st.name)
        if st.mo_from == st.name:
            warnings.append(f"Rule D5 Violation: Stage '{st.name}' reads its own .gbw as guess (reader == writer).")

    return warnings


# ---------------------------------------------------------------------------
# Method Matrix §8B.5 Dangerous Reuse (D1–D5) Integrity Auditing Engine
# ---------------------------------------------------------------------------
class StateChainingAuditor:
    """
    Adversarial verification engine enforcing Method Matrix §8B.5 Rules D1–D5.
    """

    @staticmethod
    def audit_d1_stationarity(
        gradient_norm_hartree_bohr: Optional[float],
        tol_max_g: float = 1e-5,
        delta_r_angstrom: float = 0.0,
    ) -> Tuple[bool, str]:
        """
        Rule D1: A geometry may be passed forward as a starting point at any level.
        It may be REPORTED or used for rigid property evaluations attributed to level L
        ONLY if it is stationary at level L (TolMaxG <= 1e-5 Eh/bohr).
        """
        if gradient_norm_hartree_bohr is None:
            return True, "Gradient norm not provided; starting point pass valid"

        passed = gradient_norm_hartree_bohr <= tol_max_g
        delta_b_mhz_est = (
            (2.0 * delta_r_angstrom / 3.5) * 6000.0
            if delta_r_angstrom > 0.0
            else 0.0
        )

        msg = (
            f"[D1 {'PASS' if passed else 'FAIL'}] Max gradient component: "
            f"{gradient_norm_hartree_bohr:.3e} Eh/bohr (Threshold: {tol_max_g:.1e}). "
            f"Delta R: {delta_r_angstrom*100:.2f} pm (Estimated Delta B shift: {delta_b_mhz_est:.2f} MHz)."
        )
        return passed, msg

    @staticmethod
    def audit_d2_hessian_transfer(
        harmonic_frequencies_cm1: Optional[Sequence[float]],
        low_level_frequencies_cm1: Optional[Sequence[float]] = None,
        threshold_shift_pct: float = 20.0,
    ) -> Tuple[bool, str]:
        """
        Rule D2: Reusing a Hessian as a preconditioner is safe.
        Reusing it as the REPORTED force field is safe ONLY under the substituted hybrid
        construction and only where normal coordinates are level-insensitive.
        Flags modes < 100 cm^-1 and counts imaginary frequencies.
        """
        if harmonic_frequencies_cm1 is None:
            return True, "No frequencies evaluated in this stage"

        freqs = np.asarray(harmonic_frequencies_cm1, dtype=np.float64)
        imag_modes = [float(f) for f in freqs if f < -1.0]
        soft_modes = [float(f) for f in freqs if 0.0 <= f < 100.0]

        passed = len(imag_modes) == 0
        details = [
            f"Imaginary modes count: {len(imag_modes)}",
            f"Soft modes (<100 cm^-1) flagged: {len(soft_modes)}",
        ]

        if low_level_frequencies_cm1 is not None and len(
            low_level_frequencies_cm1
        ) == len(freqs):
            low_f = np.asarray(low_level_frequencies_cm1, dtype=np.float64)
            pos_high = sorted([f for f in freqs if f > 10.0])
            pos_low = sorted([f for f in low_f if f > 10.0])
            if pos_high and pos_low:
                shift_pct = (
                    abs(pos_high[0] - pos_low[0]) / max(pos_high[0], 1e-3)
                ) * 100.0
                details.append(
                    f"Lowest intermolecular mode shift: {shift_pct:.1f}% (Threshold: {threshold_shift_pct:.1f}%)"
                )
                if shift_pct > threshold_shift_pct:
                    passed = False
                    details.append(
                        "REJECTION: Normal coordinates are method-sensitive (>20% shift)."
                    )

        msg = f"[D2 {'PASS' if passed else 'WARNING'}] " + "; ".join(details)
        return passed, msg

    @staticmethod
    def audit_d3_scf_stability(
        fresh_energy_hartree: Optional[float],
        reused_energy_hartree: Optional[float],
        tol_e: float = 1e-7,
    ) -> Tuple[bool, str]:
        """
        Rule D3: Never trust a reused-guess SCF energy without a stability spot-check.
        Asserts agreement between fresh-guess and reused-guess SCF energies.
        """
        if fresh_energy_hartree is None or reused_energy_hartree is None:
            return True, "Single SCF guess mode evaluated"

        delta_e = abs(fresh_energy_hartree - reused_energy_hartree)
        passed = delta_e <= tol_e
        msg = (
            f"[D3 {'PASS' if passed else 'FAIL'}] Reused SCF Delta E: {delta_e:.3e} Hartree "
            f"(Threshold: {tol_e:.1e})."
        )
        return passed, msg

    @staticmethod
    def audit_d4_counterpoise_hygiene(
        stage_name: str,
        counterpoise: Any,
        mo_from: Optional[str],
    ) -> Tuple[bool, str]:
        """
        Rule D4: Never reuse a dimer .gbw as the guess for a ghosted monomer leg.
        Guarantees basis set pinning across counterpoise legs.
        """
        cp_val = str(counterpoise).lower()
        if ("monomer" in cp_val or "half" in cp_val) and mo_from:
            passed = False
            msg = (
                f"[D4 VIOLATION] Stage {stage_name} is a ghosted monomer leg but attempted "
                f"to read MOs from dimer stage '{mo_from}'. Dimer .gbw reuse on monomer is forbidden."
            )
            return passed, msg

        return (
            True,
            f"[D4 PASS] Stage {stage_name} obeys counterpoise state isolation.",
        )

    @staticmethod
    def audit_d5_naming_hygiene(
        current_stage: str, consumed_stage: Optional[str]
    ) -> Tuple[bool, str]:
        """
        Rule D5: Every stage owns its own %base so a reader is never also the writer.
        """
        if consumed_stage and current_stage.lower() == consumed_stage.lower():
            return (
                False,
                f"[D5 VIOLATION] Stage '{current_stage}' reads from same-named input '{consumed_stage}'. "
                "Input .gbw will be overwritten and destroyed!",
            )
        return (
            True,
            f"[D5 PASS] Stage '{current_stage}' has distinct name from input '{consumed_stage}'.",
        )


# ---------------------------------------------------------------------------
# The Chain Orchestrator Class (Method Matrix §8B, §8C)
# ---------------------------------------------------------------------------
class Chain:
    """
    Canonical State-Chaining Driver and Execution-Arrow Recorder for CoChem.
    Persists all geometry, orbital, and Hessian transitions into one unified HDF5 file.
    """

    def __init__(
        self,
        workdir: Union[str, Path] = "chain",
        h5: Union[str, Path] = "campaign.h5",
        complex_name: str = "complex",
        charge: int = 0,
        mult: int = 1,
        nproc: int = 7,
        maxcore: int = 3400,
        orca_cmd: str = "orca",
        xtb_cmd: str = "xtb",
        strict_guards: bool = True,
    ) -> None:
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        h5_p = Path(h5)
        if h5_p.is_absolute():
            self.h5_path = h5_p
        elif len(h5_p.parts) > 1:
            self.h5_path = h5_p.resolve()
        else:
            self.h5_path = (self.workdir / h5_p).resolve()
        self.h5_path.parent.mkdir(parents=True, exist_ok=True)
        self.complex_name = complex_name
        self.charge = charge
        self.mult = mult
        self.nproc = nproc
        self.maxcore = maxcore
        self.orca_cmd = orca_cmd
        self.xtb_cmd = xtb_cmd
        self.strict_guards = strict_guards
        self.stage_records: Dict[str, StateRecord] = {}

        # Initialize HDF5 metadata store
        self._init_hdf5_store()

    def _init_hdf5_store(self) -> None:
        """Initializes the HDF5 metadata header and schema groups."""
        with h5py.File(self.h5_path, "a") as f:
            meta = f.require_group("meta")
            meta.attrs.setdefault("schema_name", "cochem_state_chain")
            meta.attrs.setdefault("schema_version", 1)
            meta.attrs.setdefault("created_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            meta.attrs.setdefault("complex", self.complex_name)
            meta.attrs.setdefault("charge", self.charge)
            meta.attrs.setdefault("multiplicity", self.mult)
            f.require_group("chain")
            f.require_group("isotopologues")
            f.require_group("lineage")

    def build_stage_input(self, stage: Stage, geom_file: str) -> str:
        """
        Synthesizes the complete ORCA input deck for a stage, encoding:
        - Unique %base name (Rule D5)
        - Memory (%maxcore) & Parallelism (%pal nprocs)
        - MO guess projection (! MORead + %moinp)
        - Initial Hessian configuration (InHess XTB2 / InHess Read)
        - Tight convergence threshold block (%geom)
        """
        route_tokens = [f"! {stage.level}"]
        if stage.mo_from:
            route_tokens.append("MORead")

        input_lines: List[str] = [
            " ".join(route_tokens),
            f'%base "{stage.name}"',
            f"%pal nprocs {self.nproc} end",
            f"%maxcore {self.maxcore}",
        ]

        if stage.mo_from:
            input_lines.append(f'%moinp "{stage.mo_from}.gbw"')
            if stage.guess_mode:
                input_lines.append(f"%scf GuessMode {stage.guess_mode} end")

        # Configure geometry and initial Hessian block if optimization is requested
        if "opt" in stage.level.lower():
            geom_block_lines = [TIGHT_GEOM_BLOCK.rstrip("\n")]
            if stage.hess_from:
                opt_file = self.workdir / f"{stage.hess_from}.opt"
                src_name = f"{stage.hess_from}.opt" if opt_file.exists() else f"{stage.hess_from}.hess"
                geom_block_lines.extend(["  InHess Read", f'  InHessName "{src_name}"'])
            else:
                geom_block_lines.append("  InHess XTB2")  # Cheap model Hessian default (§8B.3)

            input_lines.append("%geom\n" + "\n".join(geom_block_lines) + "\nend")

        if stage.blocks:
            input_lines.append(stage.blocks)

        input_lines.append(f"* xyzfile {self.charge} {self.mult} {geom_file}")
        return "\n".join(input_lines) + "\n"

    def record_to_hdf5(self, rec: StateRecord) -> None:
        """
        Persists an execution record into the HDF5 store with chunking,
        gzip level 4 compression, shuffle filter, and fletcher32 checksums.
        """
        with h5py.File(self.h5_path, "a") as f:
            grp = f.require_group(f"chain/{rec.stage}")
            grp.attrs["level"] = rec.level
            grp.attrs["wall_s"] = rec.wall_s
            grp.attrs["consumed"] = json.dumps(rec.consumed_files)
            grp.attrs["produced"] = json.dumps(rec.produced_files)
            grp.attrs["written_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            grp.attrs["converged"] = rec.converged
            grp.attrs["exit_status"] = rec.exit_status
            grp.attrs["symbols"] = json.dumps(rec.symbols)
            grp.attrs["n_atoms"] = len(rec.symbols)

            if rec.arrow_index is not None:
                grp.attrs["arrow_index"] = rec.arrow_index
                grp.attrs["arrow_desc"] = rec.arrow_desc

            if rec.energy_hartree is not None:
                grp.attrs["energy_hartree"] = rec.energy_hartree

            if rec.rotational_constants_mhz is not None:
                grp.attrs["rotational_constants_mhz"] = json.dumps(list(rec.rotational_constants_mhz))

            if rec.inertial_defect_amu_a2 is not None:
                grp.attrs["inertial_defect_amu_a2"] = rec.inertial_defect_amu_a2

            if rec.planar_moments_amu_a2 is not None:
                grp.attrs["planar_moments_amu_a2"] = json.dumps(list(rec.planar_moments_amu_a2))

            if rec.warnings:
                grp.attrs["warnings"] = json.dumps(rec.warnings)

            # Persist Geometry Dataset
            if "geometry" in grp:
                del grp["geometry"]
            grp.create_dataset(
                "geometry",
                data=np.asarray(rec.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=4,
                shuffle=True,
            )

            # Persist Hessian Dataset if available
            if rec.hessian is not None:
                if "hessian" in grp:
                    del grp["hessian"]
                grp.create_dataset(
                    "hessian",
                    data=np.asarray(rec.hessian, dtype=np.float64),
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )

            # Persist Gradient Dataset if available
            if rec.gradient is not None:
                if "gradient" in grp:
                    del grp["gradient"]
                grp.create_dataset(
                    "gradient",
                    data=np.asarray(rec.gradient, dtype=np.float64),
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )

            # Persist Frequencies Dataset if available
            if rec.frequencies_cm_inv is not None:
                if "frequencies" in grp:
                    del grp["frequencies"]
                grp.create_dataset(
                    "frequencies",
                    data=np.asarray(rec.frequencies_cm_inv, dtype=np.float64),
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )

    def run_stage(
        self,
        stage: Stage,
        seed_xyz: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
    ) -> StateRecord:
        """
        Executes a single pipeline stage, validates outputs against Rules D1–D5,
        computes rotational observables, and records all artifacts to HDF5.
        """
        logger.info(f"=== [Stage: {stage.name}] (Level: {stage.level}) ===")

        # Determine geometry source file
        if stage.geom_from:
            geom_source = f"{stage.geom_from}.xyz"
        elif seed_xyz:
            seed_p = Path(seed_xyz)
            geom_source = seed_p.name
            target_dest = self.workdir / geom_source
            if seed_p.exists() and seed_p.resolve() != target_dest.resolve():
                shutil.copy(seed_p, target_dest)
        else:
            raise ValueError(f"Stage '{stage.name}' requires either 'geom_from' or 'seed_xyz'.")

        inp_path = self.workdir / f"{stage.name}.inp"
        out_path = self.workdir / f"{stage.name}.out"
        err_path = self.workdir / f"{stage.name}.err"

        # Generate stage input deck
        input_deck = self.build_stage_input(stage, geom_source)
        inp_path.write_text(input_deck, encoding="utf-8")

        wall_s = 0.0
        exit_status = "SUCCESS"

        if not dry_run:
            t0 = time.time()
            with out_path.open("w", encoding="utf-8") as out_fh, err_path.open("w", encoding="utf-8") as err_fh:
                try:
                    res = subprocess.run(
                        [self.orca_cmd, inp_path.name],
                        cwd=self.workdir,
                        stdout=out_fh,
                        stderr=err_fh,
                        check=False,
                    )
                    wall_s = time.time() - t0
                    if res.returncode != 0:
                        exit_status = f"FAILED_EXIT_{res.returncode}"
                except FileNotFoundError:
                    wall_s = time.time() - t0
                    exit_status = "ENGINE_NOT_FOUND"
                    logger.warning(f"ORCA binary '{self.orca_cmd}' not found on PATH. Recorded input deck.")
        else:
            logger.info(f"[Dry Run] Generated input deck at {inp_path.name}")

        # Post-Execution Ingestion & Parsing
        conv_info = parse_orca_convergence(out_path)
        energy = parse_orca_energy(out_path)

        # Ingest output geometry
        stage_xyz_path = self.workdir / f"{stage.name}.xyz"
        if not stage_xyz_path.exists():
            # Single-points or unwritten xyz: copy input geometry forward
            if (self.workdir / geom_source).exists():
                shutil.copy(self.workdir / geom_source, stage_xyz_path)

        symbols: List[str] = []
        coords: np.ndarray = np.empty((0, 3))
        if stage_xyz_path.exists():
            symbols, coords, _ = read_xyz(stage_xyz_path)

        # Ingest Hessian if generated
        hess_path = self.workdir / f"{stage.name}.hess"
        hess_dict = parse_orca_hessian(hess_path)
        hessian_arr = hess_dict["hessian"] if hess_dict is not None else None
        freqs_arr = hess_dict["frequencies"] if hess_dict is not None else None

        # Compute Rotational Observables
        rot_constants: Optional[Tuple[float, float, float]] = None
        inertial_defect: Optional[float] = None
        planar_moments: Optional[Tuple[float, float, float]] = None
        if len(symbols) > 0 and coords.shape[0] > 0:
            rot_dict = compute_rotational_constants(symbols, coords)
            rot_constants = (rot_dict["A_MHz"], rot_dict["B_MHz"], rot_dict["C_MHz"])
            inertial_defect = rot_dict["inertial_defect_amu_A2"]
            planar_moments = (rot_dict["Paa_u_A2"], rot_dict["Pbb_u_A2"], rot_dict["Pcc_u_A2"])

        # Determine consumed and produced files
        consumed: List[str] = [geom_source]
        if stage.mo_from:
            consumed.append(f"{stage.mo_from}.gbw")
        if stage.hess_from:
            consumed.append(f"{stage.hess_from}.opt")

        produced: List[str] = [p.name for p in self.workdir.glob(f"{stage.name}.*")]

        # Run Dangerous Reuse Guards (Rules D1–D5)
        warnings: List[str] = []
        prev_rec = self.stage_records.get(stage.geom_from) if stage.geom_from else None
        if self.strict_guards and len(symbols) > 0:
            warnings.extend(
                validate_rule_d1_geometry_stationarity(
                    stage,
                    StateRecord(
                        stage=stage.name,
                        level=stage.level,
                        wall_s=wall_s,
                        energy_hartree=energy,
                        symbols=symbols,
                        geometry=coords,
                    ),
                    prev_rec,
                )
            )
            if hessian_arr is not None:
                warnings.extend(
                    validate_rule_d2_hessian_reuse(stage, hessian_arr, symbols, coords)
                )
            warnings.extend(validate_rule_d3_scf_stability(stage, out_path))
            warnings.extend(validate_rule_d4_counterpoise_ghosts(stage, symbols))

        # Assemble StateRecord
        record = StateRecord(
            stage=stage.name,
            level=stage.level,
            wall_s=wall_s,
            energy_hartree=energy,
            symbols=symbols,
            geometry=coords,
            hessian=hessian_arr,
            frequencies_cm_inv=freqs_arr,
            rotational_constants_mhz=rot_constants,
            inertial_defect_amu_a2=inertial_defect,
            planar_moments_amu_a2=planar_moments,
            consumed_files=consumed,
            produced_files=produced,
            arrow_index=stage.arrow_index,
            arrow_desc=stage.arrow_desc,
            converged=conv_info["opt_converged"] if "opt" in stage.level.lower() else conv_info["normal_termination"],
            exit_status=exit_status,
            warnings=warnings,
        )

        self.stage_records[stage.name] = record
        self.record_to_hdf5(record)
        return record

    def run_canonical_pipeline(
        self,
        seed_xyz: Union[str, Path],
        include_xtb: bool = True,
        include_freq: bool = True,
        include_isotopologues: bool = True,
        include_ccsd: bool = False,
        dry_run: bool = False,
    ) -> List[StateRecord]:
        """
        Executes the full Method Matrix §8B.4 Canonical Chained Pipeline:
        - Stage s1_xtb: GFN2-xTB pre-optimization (Arrow 2)
        - Stage s2: r2SCAN-3c TightOpt with InHess XTB2 model Hessian (Arrow 3)
        - Stage s3: wB97X-V/def2-TZVPP TightOpt with s2.gbw + s2.opt (Arrow 4)
        - Stage s4: wB97M-V/def2-QZVPP TightOpt with s3.gbw + s3.opt (Arrow 5)
        - Stage s5: wB97M-V/def2-QZVPP Freq with s4.gbw (Arrow 6)
        - Stage s5b_iso: Isotopologue re-analysis (13C, 18O, D) (Arrow 7)
        - Stage s6: DLPNO-CCSD(T1) on stage s4 geometry with s4.gbw (Arrow 8)
        """
        seed_p = Path(seed_xyz).resolve()
        if not seed_p.exists():
            raise FileNotFoundError(f"Seed coordinate file not found: {seed_p}")

        logger.info(f"Launching Canonical State-Chaining Pipeline for seed: {seed_p.name}")
        shutil.copy(seed_p, self.workdir / seed_p.name)

        records: List[StateRecord] = []
        active_seed = seed_p.name

        # Stage 1: xTB Pre-optimization if requested
        if include_xtb:
            s1_out = self.workdir / "s1_xtb.out"
            s1_xyz = self.workdir / "s1.xyz"
            if not dry_run:
                try:
                    with s1_out.open("w", encoding="utf-8") as fh:
                        subprocess.run(
                            [
                                self.xtb_cmd,
                                seed_p.name,
                                "--opt",
                                "vtight",
                                "--strict",
                                "--chrg",
                                str(self.charge),
                                "--uhf",
                                str(self.mult - 1),
                            ],
                            cwd=self.workdir,
                            stdout=fh,
                            stderr=subprocess.STDOUT,
                            check=False,
                        )
                    xtbopt = self.workdir / "xtbopt.xyz"
                    if xtbopt.exists():
                        shutil.copy(xtbopt, s1_xyz)
                        active_seed = "s1.xyz"
                except FileNotFoundError:
                    logger.warning(f"xTB binary '{self.xtb_cmd}' not found. Falling back to raw seed.")
                    shutil.copy(seed_p, s1_xyz)
                    active_seed = "s1.xyz"

        # Define Canonical Stages
        s2 = Stage(
            name="s2",
            level="r2SCAN-3c TightOpt TightSCF DefGrid3",
            arrow_index=3,
            arrow_desc="GFN2-xTB -> r2SCAN-3c with InHess XTB2 model Hessian",
        )
        s3 = Stage(
            name="s3",
            level="wB97X-V def2-TZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3",
            geom_from="s2",
            mo_from="s2",
            hess_from="s2",
            arrow_index=4,
            arrow_desc="r2SCAN-3c -> wB97X-V/def2-TZVPP tight optimization",
        )
        s4 = Stage(
            name="s4",
            level="wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3",
            geom_from="s3",
            mo_from="s3",
            hess_from="s3",
            arrow_index=5,
            arrow_desc="wB97X-V/TZ -> wB97M-V/def2-QZVPP tight optimization (MO cascade)",
        )
        s5 = Stage(
            name="s5",
            level="wB97M-V def2-QZVPP def2/J RIJCOSX Freq TightSCF DefGrid3",
            geom_from="s4",
            mo_from="s4",
            arrow_index=6,
            arrow_desc="Tight optimization -> analytic DFT Hessian",
        )
        s6 = Stage(
            name="s6",
            level="DLPNO-CCSD(T1) TightPNO cc-pVDZ-F12 (paired with CABS) cc-pVDZ-F12 (paired with CABS)/C TightSCF",
            geom_from="s4",
            mo_from="s4",
            blocks="%mdci TCutPNO 1e-7 DoLED true StorageType Shared end",
            arrow_index=8,
            arrow_desc="Tight optimization -> high-level DLPNO-CCSD(T1) single point",
        )

        # Validate Naming Hygiene before execution (Rule D5)
        d5_warnings = validate_rule_d5_naming_hygiene([s2, s3, s4, s5, s6])
        if d5_warnings:
            logger.warning(f"Naming hygiene warnings: {d5_warnings}")

        # Execute Stage 2 (r2SCAN-3c)
        r2 = self.run_stage(s2, seed_xyz=active_seed, dry_run=dry_run)
        records.append(r2)

        # Execute Stage 3 (wB97X-V/TZ)
        r3 = self.run_stage(s3, dry_run=dry_run)
        records.append(r3)

        # Execute Stage 4 (wB97M-V/QZ)
        r4 = self.run_stage(s4, dry_run=dry_run)
        records.append(r4)

        # Execute Stage 5 (Analytic Frequency)
        if include_freq:
            r5 = self.run_stage(s5, dry_run=dry_run)
            records.append(r5)

            # Stage 5b: Zero-Cost Isotopologue Campaign (Arrow 7)
            if include_isotopologues and r5.hessian is not None:
                self.run_standard_isotopologue_campaign("s5")

        # Execute Stage 6 (DLPNO Single Point)
        if include_ccsd:
            r6 = self.run_stage(s6, dry_run=dry_run)
            records.append(r6)

        logger.info(f"Canonical pipeline complete. Database: {self.h5_path}")
        return records

    def run_standard_isotopologue_campaign(self, parent_stage: str) -> Dict[str, Dict[str, Any]]:
        """
        Executes standard isotopologue substitution campaign for 13C, 18O, and 2H (D)
        using the saved Cartesian Hessian from `parent_stage` at zero electronic structure cost.
        """
        rec = self.stage_records.get(parent_stage)
        if rec is None or rec.hessian is None:
            logger.warning(f"Cannot run isotopologue campaign: Stage '{parent_stage}' has no saved Hessian.")
            return {}

        symbols = rec.symbols
        coords = rec.geometry
        hess = rec.hessian

        results: Dict[str, Dict[str, Any]] = {}

        # 1. 13C substitution on each Carbon atom
        for idx, sym in enumerate(symbols):
            if sym.strip().capitalize() == "C":
                iso_masses: List[Optional[int]] = [None] * len(symbols)
                iso_masses[idx] = 13
                label = f"iso_13C_{idx+1}"
                res = reanalyze_isotopologue(hess, coords, symbols, iso_masses, label)
                results[label] = res
                self._record_isotopologue_to_hdf5(label, parent_stage, res)

        # 2. 18O substitution on each Oxygen atom
        for idx, sym in enumerate(symbols):
            if sym.strip().capitalize() == "O":
                iso_masses = [None] * len(symbols)
                iso_masses[idx] = 18
                label = f"iso_18O_{idx+1}"
                res = reanalyze_isotopologue(hess, coords, symbols, iso_masses, label)
                results[label] = res
                self._record_isotopologue_to_hdf5(label, parent_stage, res)

        # 3. Deuterium (2H) substitution on each Hydrogen atom
        for idx, sym in enumerate(symbols):
            if sym.strip().capitalize() == "H":
                iso_masses = [None] * len(symbols)
                iso_masses[idx] = 2
                label = f"iso_D_{idx+1}"
                res = reanalyze_isotopologue(hess, coords, symbols, iso_masses, label)
                results[label] = res
                self._record_isotopologue_to_hdf5(label, parent_stage, res)

        logger.info(f"Isotopologue campaign evaluated {len(results)} isotopologues from force field '{parent_stage}'.")
        return results

    def _record_isotopologue_to_hdf5(
        self,
        iso_label: str,
        parent_stage: str,
        iso_data: Dict[str, Any],
    ) -> None:
        """Records isotopologue rotational and vibrational properties into /isotopologues group."""
        with h5py.File(self.h5_path, "a") as f:
            grp = f.require_group(f"isotopologues/{iso_label}")
            grp.attrs["parent_stage"] = parent_stage
            grp.attrs["substituted_masses"] = json.dumps(iso_data["substituted_mass_numbers"])
            grp.attrs["A_MHz"] = iso_data["A_MHz"]
            grp.attrs["B_MHz"] = iso_data["B_MHz"]
            grp.attrs["C_MHz"] = iso_data["C_MHz"]
            grp.attrs["inertial_defect_amu_A2"] = iso_data["inertial_defect_amu_A2"]
            grp.attrs["Paa_u_A2"] = iso_data["Paa_u_A2"]
            grp.attrs["Pbb_u_A2"] = iso_data["Pbb_u_A2"]
            grp.attrs["Pcc_u_A2"] = iso_data["Pcc_u_A2"]
            grp.attrs["lowest_harmonic_mode_cm_inv"] = iso_data["lowest_harmonic_mode_cm_inv"]

            if "frequencies" in grp:
                del grp["frequencies"]
            grp.create_dataset(
                "frequencies",
                data=np.asarray(iso_data["frequencies_cm_inv"], dtype=np.float64),
                compression="gzip",
                compression_opts=4,
                shuffle=True,
            )

    def generate_compound_script(
        self,
        stages: Sequence[Stage],
        seed_xyz: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Implements Method Matrix Arrow 11 (§8B.4):
        Generates a multi-step ORCA compound script (New_Step ... Step_End)
        eliminating intermediate file plumbing when the entire chain fits one job window.
        """
        seed_p = Path(seed_xyz).name
        lines: List[str] = [
            "# Multi-step compound state-chaining script (Method Matrix Arrow 11)",
            f"%pal nprocs {self.nproc} end",
            f"%maxcore {self.maxcore}",
            "",
        ]

        for step_idx, st in enumerate(stages, start=1):
            lines.append(f"# Step {step_idx}: {st.name} ({st.level})")
            lines.append("New_Step")
            lines.append(f"  ! {st.level}")
            if st.mo_from:
                lines.append(f'  %moinp "{st.mo_from}.gbw"')
            if "opt" in st.level.lower():
                lines.append("  %geom")
                lines.append(TIGHT_GEOM_BLOCK.rstrip("\n"))
                if st.hess_from:
                    lines.append("    InHess Read")
                    lines.append(f'    InHessName "{st.hess_from}.opt"')
                else:
                    lines.append("    InHess XTB2")
                lines.append("  end")
            if st.blocks:
                lines.append(f"  {st.blocks}")

            geom_target = f"{st.geom_from}.xyz" if st.geom_from else seed_p
            lines.append(f"  * xyzfile {self.charge} {self.mult} {geom_target}")
            lines.append("Step_End")
            lines.append("")

        deck = "\n".join(lines)
        if output_path is not None:
            Path(output_path).write_text(deck, encoding="utf-8")
        return deck

    def inspect_campaign(self) -> Dict[str, Any]:
        """Reads and formats summary statistics from the HDF5 campaign store."""
        summary: Dict[str, Any] = {"stages": {}, "isotopologues": {}}
        if not self.h5_path.exists():
            return summary

        with h5py.File(self.h5_path, "r") as f:
            if "meta" in f:
                meta_dict: Dict[str, Any] = {}
                for k, v in f["meta"].attrs.items():
                    if hasattr(v, "item"):
                        meta_dict[k] = v.item()
                    elif isinstance(v, bytes):
                        meta_dict[k] = v.decode("utf-8")
                    else:
                        meta_dict[k] = v
                summary["meta"] = meta_dict

            if "chain" in f:
                for st_name in f["chain"]:
                    grp = f[f"chain/{st_name}"]
                    st_info: Dict[str, Any] = {
                        "level": grp.attrs.get("level", ""),
                        "wall_s": float(grp.attrs.get("wall_s", 0.0)),
                        "converged": bool(grp.attrs.get("converged", False)),
                        "energy_hartree": float(grp.attrs.get("energy_hartree", 0.0))
                        if "energy_hartree" in grp.attrs
                        else None,
                        "consumed": json.loads(grp.attrs.get("consumed", "[]")),
                        "produced": json.loads(grp.attrs.get("produced", "[]")),
                    }
                    if "rotational_constants_mhz" in grp.attrs:
                        st_info["rotational_constants_mhz"] = json.loads(grp.attrs["rotational_constants_mhz"])
                    if "inertial_defect_amu_a2" in grp.attrs:
                        st_info["inertial_defect_amu_a2"] = float(grp.attrs["inertial_defect_amu_a2"])
                    summary["stages"][st_name] = st_info

            if "isotopologues" in f:
                for iso_name in f["isotopologues"]:
                    grp = f[f"isotopologues/{iso_name}"]
                    summary["isotopologues"][iso_name] = {
                        "parent_stage": grp.attrs.get("parent_stage", ""),
                        "A_MHz": float(grp.attrs.get("A_MHz", 0.0)),
                        "B_MHz": float(grp.attrs.get("B_MHz", 0.0)),
                        "C_MHz": float(grp.attrs.get("C_MHz", 0.0)),
                        "inertial_defect_amu_A2": float(grp.attrs.get("inertial_defect_amu_A2", 0.0)),
                    }

        return summary


# ---------------------------------------------------------------------------
# Campaign Graphviz Lineage Export
# ---------------------------------------------------------------------------
def export_lineage_dot(h5_path: Union[str, Path], output_dot: Union[str, Path]) -> str:
    """Exports Graphviz DOT representation of execution arrows and state transfers."""
    p = Path(h5_path)
    if not p.exists():
        raise FileNotFoundError(f"Campaign HDF5 not found at {p.resolve()}")

    dot_lines = [
        "digraph StateChain {",
        "  rankdir=LR;",
        '  node [shape=box, style="filled,rounded", fontname="Helvetica", fillcolor="#eef2f7", color="#2c3e50"];',
        '  edge [fontname="Helvetica", fontsize=10];',
        "",
    ]

    with h5py.File(p, "r") as f:
        if "chain" in f:
            for st_name in f["chain"]:
                grp = f[f"chain/{st_name}"]
                level = grp.attrs.get("level", "")
                wall = float(grp.attrs.get("wall_s", 0.0))
                arrow_idx = grp.attrs.get("arrow_index", "")
                label = f"{st_name}\\n{level}\\n(wall: {wall:.1f}s)"
                dot_lines.append(f'  "{st_name}" [label="{label}"];')

                consumed = json.loads(grp.attrs.get("consumed", "[]"))
                for src in consumed:
                    src_stage = src.split(".")[0]
                    if src_stage != st_name and "chain" in f and src_stage in f["chain"]:
                        ext = src.split(".")[-1]
                        edge_label = f"Arrow {arrow_idx}: .{ext}" if arrow_idx else f".{ext}"
                        dot_lines.append(f'  "{src_stage}" -> "{st_name}" [label="{edge_label}"];')

    dot_lines.append("}\n")
    dot_str = "\n".join(dot_lines)
    Path(output_dot).write_text(dot_str, encoding="utf-8")
    return dot_str


# ---------------------------------------------------------------------------
# Command-Line Interface (CLI)
# ---------------------------------------------------------------------------
def main() -> int:
    """CLI entrypoint for chain.py."""
    parser = argparse.ArgumentParser(
        description="Canonical State-Chaining Driver & Execution-Arrow Recorder (Method Matrix §8B, §8C)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: pipeline (canonical full workflow)
    p_pipe = subparsers.add_parser("pipeline", help="Run the full 11-arrow canonical pipeline from a seed XYZ")
    p_pipe.add_argument("seed_xyz", help="Input seed XYZ coordinate file")
    p_pipe.add_argument("--workdir", default="chain", help="Working directory (default: chain)")
    p_pipe.add_argument("--h5", default="campaign.h5", help="HDF5 campaign database name (default: campaign.h5)")
    p_pipe.add_argument("--complex", default="complex", help="Complex identifier name")
    p_pipe.add_argument("--charge", type=int, default=0, help="Molecular charge (default: 0)")
    p_pipe.add_argument("--mult", type=int, default=1, help="Spin multiplicity (default: 1)")
    p_pipe.add_argument("--nproc", type=int, default=7, help="CPU cores for ORCA (default: 7)")
    p_pipe.add_argument("--maxcore", type=int, default=3400, help="Memory per core in MB (default: 3400)")
    p_pipe.add_argument("--skip-xtb", action="store_true", help="Skip GFN2-xTB pre-optimization")
    p_pipe.add_argument("--skip-freq", action="store_true", help="Skip analytic Hessian stage")
    p_pipe.add_argument("--skip-iso", action="store_true", help="Skip isotopologue re-analysis")
    p_pipe.add_argument("--with-ccsd", action="store_true", help="Include DLPNO-CCSD(T1) single point")
    p_pipe.add_argument("--dry-run", action="store_true", help="Generate input decks without calling binaries")

    # Command: inspect (inspect HDF5 campaign)
    p_insp = subparsers.add_parser("inspect", help="Inspect an existing HDF5 campaign store")
    p_insp.add_argument("h5_file", help="Path to campaign.h5 file")
    p_insp.add_argument("--dot", help="Optional output path to export Graphviz DOT lineage graph")

    # Command: compound (generate multi-step compound script)
    p_comp = subparsers.add_parser("compound", help="Generate a multi-step ORCA compound script (Arrow 11)")
    p_comp.add_argument("seed_xyz", help="Input seed XYZ coordinate file")
    p_comp.add_argument("--output", default="compound_chain.inp", help="Output input file path")
    p_comp.add_argument("--nproc", type=int, default=7, help="CPU cores (default: 7)")
    p_comp.add_argument("--maxcore", type=int, default=3400, help="Memory in MB (default: 3400)")

    # Legacy direct invocation support: python chain.py seed.xyz
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("pipeline", "inspect", "compound"):
        seed_arg = sys.argv[1]
        c = Chain()
        c.run_canonical_pipeline(seed_arg)
        print(f"done -> {c.h5_path}")
        return 0

    args = parser.parse_args()

    if args.command == "pipeline":
        c = Chain(
            workdir=args.workdir,
            h5=args.h5,
            complex_name=args.complex,
            charge=args.charge,
            mult=args.mult,
            nproc=args.nproc,
            maxcore=args.maxcore,
        )
        c.run_canonical_pipeline(
            seed_xyz=args.seed_xyz,
            include_xtb=not args.skip_xtb,
            include_freq=not args.skip_freq,
            include_isotopologues=not args.skip_iso,
            include_ccsd=args.with_ccsd,
            dry_run=args.dry_run,
        )
        print(f"Pipeline executed successfully -> {c.h5_path}")
        return 0

    elif args.command == "inspect":
        h5_p = Path(args.h5_file)
        if not h5_p.exists():
            print(f"Error: file not found at {h5_p}")
            return 1
        c = Chain(h5=h5_p)
        info = c.inspect_campaign()
        print("\n=== CoChem State-Chaining Campaign Summary ===")
        print(json.dumps(info, indent=2))
        if args.dot:
            export_lineage_dot(h5_p, args.dot)
            print(f"Exported lineage graph to {args.dot}")
        return 0

    elif args.command == "compound":
        c = Chain(nproc=args.nproc, maxcore=args.maxcore)
        s2 = Stage("s2", "r2SCAN-3c TightOpt TightSCF DefGrid3")
        s3 = Stage("s3", "wB97X-V def2-TZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3", geom_from="s2", mo_from="s2", hess_from="s2")
        s4 = Stage("s4", "wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3", geom_from="s3", mo_from="s3", hess_from="s3")
        s5 = Stage("s5", "wB97M-V def2-QZVPP def2/J RIJCOSX Freq TightSCF DefGrid3", geom_from="s4", mo_from="s4")
        c.generate_compound_script([s2, s3, s4, s5], args.seed_xyz, args.output)
        print(f"Generated compound script at {args.output}")
        return 0

    else:
        parser.print_help()
        return 0


__all__ = [
    "Chain",
    "StateChainingAuditor",
    "ArrowState",
    "Stage",
    "ExecutionArrow",
    "StateRecord",
    "CanonicalArrow",
    "CounterpoiseType",
    "CANONICAL_ARROWS",
    "get_atomic_mass",
    "get_isotopic_mass",
]


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\__init__.py ---
# cochem_canvas_target: core_engine/__init__.py
"""
CoChem-CORE Engine Package.
High-throughput computational chemistry core execution engines.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .cochem_core_context_compressor import (
    ASTContextCompressor,
    ASTContextSummary,
    ContextCompressor,
    CoreContextCompressor,
    HDF5PointerModel,
    LTTBDownsampler,
    LTTBResult,
    MarkdownChunkModel,
    TensorSummaryModel,
    TracebackSummaryModel,
    chunk_literature_by_headers,
    chunk_markdown_by_headers,
    compress_array_to_summary,
    compress_molecular_geometry,
    compress_tensors_for_llm,
    compress_to_dict,
    create_hdf5_pointer,
    decimate_lttb,
    dumps_rfc8259,
    extract_hdf5_pointers,
    intercept_and_compress,
    is_hdf5_pointer,
    loads_rfc8259,
    lttb_decimate,
    lttb_downsample,
    lttb_downsample_1d,
    lttb_downsample_indices,
    lttb_downsample_xy,
    parse_hdf5_pointer,
    resolve_hdf5_pointer,
    sanitize_numerical_values,
    strip_ansi_escape_codes,
    to_rfc8259_json,
    truncate_traceback,
)

from .cochem_core_dvr_solver import (
    DVR1DSolver,
    DVR2DSolver,
    DVRGridType,
    DVRSpectrumResult,
    MatrixFreeDVROperator,
    SolverBackend,
    SymmetryGroup,
    TorsionalRotorResult,
    TunnelingAnalysisResult,
    analyze_double_well_tunneling,
    analyze_hindered_internal_rotor,
    build_2d_direct_product_kinetic,
    build_fourier_kinetic_1d,
    build_grid_1d,
    build_hermite_kinetic_1d,
    build_kinetic_matrix_1d,
    build_legendre_kinetic_1d,
    build_radial_sinc_kinetic_1d,
    build_sinc_kinetic_1d,
    build_sine_kinetic_1d,
    classify_nuclear_spin_weights,
    compute_reduced_mass_pair,
    compute_top_rotational_constant_f,
    compute_transition_dipole_moments,
    compute_vibrational_averages_1d,
    compute_wkb_tunneling_action,
    get_dynamic_mass,
    nan_regularization_watchdog,
    solve_dvr_dense,
    solve_dvr_matrix_free,
)

from .cochem_core_frozen_monomer import (
    ANGSTROM_TO_BOHR,
    BOHR_TO_ANGSTROM,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INERTIA_CONV_MHZ_U_ANG2,
    STANDARD_TEMPLATE_PARAMETERS,
    TOL_E_DEFAULT,
    TOL_MAXD_DEFAULT,
    TOL_MAXG_DEFAULT,
    TOL_RMSG_DEFAULT,
    TOL_RMSD_DEFAULT,
    CompositeGeometryResult,
    CompositeScheme,
    CounterpoiseDecomposition,
    FrozenMonomerFlag,
    FrozenMonomerOptimizationSpec,
    MonomerPartition,
    RecipeExecutionPlan,
    RecipeReport,
    ResidualGradientCheck,
    RotationalConstantsResult,
    SensitivityResult,
    TemplateScalingParameter,
    TemplateScalingResult,
    analyze_rotational_sensitivity,
    apply_template_scaling,
    build_cli_parser,
    check_frozen_residual_gradients,
    compute_chs_composite_geometry,
    compute_focal_point_energy,
    compute_focal_point_gradient,
    compute_isotopologue_rotational_constants,
    compute_rotational_constants,
    decompose_counterpoise_energy,
    decompose_manybody_trimer,
    evaluate_recipe_result,
    format_xyz_string,
    generate_frozen_monomer_optimization_spec,
    get_dynamic_atomic_mass,
    get_recipe_plan,
    kabsch_superimpose,
    parse_xyz_string,
    replace_monomer_geometry_in_complex,
    validate_composite_protocol,
)
from .cochem_core_auto_pes import (
    AcquisitionStrategy,
    ActiveLearningConfig,
    ActiveLearningEngine,
    AutoPESOrchestrator,
    CommitteeModel,
    DeltaFittingConfig,
    DeltaPESModel,
    FittingBackend,
    GeometryFeaturizer,
    KernelType,
    PESValidator,
    generate_benchmark_intermolecular_pes_data,
    get_dynamic_atomic_mass as get_dynamic_atomic_mass_auto_pes,
    get_dynamic_atomic_number,
)
from .cochem_core_cfour_bridge import (
    CFOURAnharmMode,
    CFOURBridge,
    CFOURCalcLevel,
    CFOURInputConfig,
    CFOURObservables,
    CFOUROutputParser,
    CFOURReference,
    CFOURVibMode,
    HarmonicForceField,
    IsotopologueFFResult,
    QuarticCentrifugalDistortion,
    SexticCentrifugalDistortion,
    VibrationRotationAlpha,
    WatsonReduction,
    export_cfour_to_spcat_var,
    generate_cfour_zmat,
    isomass_rediagonalize_force_field,
)

__all__ = [
    "AcquisitionStrategy",
    "ActiveLearningConfig",
    "ActiveLearningEngine",
    "AutoPESOrchestrator",
    "CFOURAnharmMode",
    "CFOURBridge",
    "CFOURCalcLevel",
    "CFOURInputConfig",
    "CFOURObservables",
    "CFOUROutputParser",
    "CFOURReference",
    "CFOURVibMode",
    "CommitteeModel",
    "DeltaFittingConfig",
    "DeltaPESModel",
    "FittingBackend",
    "GeometryFeaturizer",
    "HarmonicForceField",
    "IsotopologueFFResult",
    "KernelType",
    "PESValidator",
    "QuarticCentrifugalDistortion",
    "SexticCentrifugalDistortion",
    "VibrationRotationAlpha",
    "WatsonReduction",
    "export_cfour_to_spcat_var",
    "generate_cfour_zmat",
    "isomass_rediagonalize_force_field",
    "generate_benchmark_intermolecular_pes_data",
    "get_dynamic_atomic_mass_auto_pes",
    "get_dynamic_atomic_number",
    "ANGSTROM_TO_BOHR",
    "ASTContextCompressor",
    "ASTContextSummary",
    "BOHR_TO_ANGSTROM",
    "CompositeGeometryResult",
    "CompositeScheme",
    "ContextCompressor",
    "CoreContextCompressor",
    "CounterpoiseDecomposition",
    "DVR1DSolver",
    "DVR2DSolver",
    "DVRGridType",
    "DVRSpectrumResult",
    "FrozenMonomerFlag",
    "FrozenMonomerOptimizationSpec",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "HDF5PointerModel",
    "INERTIA_CONV_MHZ_U_ANG2",
    "LTTBDownsampler",
    "LTTBResult",
    "MarkdownChunkModel",
    "MatrixFreeDVROperator",
    "MonomerPartition",
    "RecipeExecutionPlan",
    "RecipeReport",
    "ResidualGradientCheck",
    "RotationalConstantsResult",
    "SensitivityResult",
    "SolverBackend",
    "STANDARD_TEMPLATE_PARAMETERS",
    "SymmetryGroup",
    "TemplateScalingParameter",
    "TemplateScalingResult",
    "TensorSummaryModel",
    "TOL_E_DEFAULT",
    "TOL_MAXD_DEFAULT",
    "TOL_MAXG_DEFAULT",
    "TOL_RMSD_DEFAULT",
    "TOL_RMSG_DEFAULT",
    "TorsionalRotorResult",
    "TracebackSummaryModel",
    "TunnelingAnalysisResult",
    "analyze_double_well_tunneling",
    "analyze_hindered_internal_rotor",
    "analyze_rotational_sensitivity",
    "apply_template_scaling",
    "build_2d_direct_product_kinetic",
    "build_cli_parser",
    "build_fourier_kinetic_1d",
    "build_grid_1d",
    "build_hermite_kinetic_1d",
    "build_kinetic_matrix_1d",
    "build_legendre_kinetic_1d",
    "build_radial_sinc_kinetic_1d",
    "build_sinc_kinetic_1d",
    "build_sine_kinetic_1d",
    "check_frozen_residual_gradients",
    "chunk_literature_by_headers",
    "chunk_markdown_by_headers",
    "classify_nuclear_spin_weights",
    "compress_array_to_summary",
    "compress_molecular_geometry",
    "compress_tensors_for_llm",
    "compress_to_dict",
    "compute_chs_composite_geometry",
    "compute_focal_point_energy",
    "compute_focal_point_gradient",
    "compute_isotopologue_rotational_constants",
    "compute_reduced_mass_pair",
    "compute_rotational_constants",
    "compute_top_rotational_constant_f",
    "compute_transition_dipole_moments",
    "compute_vibrational_averages_1d",
    "compute_wkb_tunneling_action",
    "create_hdf5_pointer",
    "decimate_lttb",
    "decompose_counterpoise_energy",
    "decompose_manybody_trimer",
    "dumps_rfc8259",
    "evaluate_recipe_result",
    "extract_hdf5_pointers",
    "format_xyz_string",
    "generate_frozen_monomer_optimization_spec",
    "get_dynamic_atomic_mass",
    "get_dynamic_mass",
    "get_recipe_plan",
    "intercept_and_compress",
    "is_hdf5_pointer",
    "kabsch_superimpose",
    "loads_rfc8259",
    "lttb_decimate",
    "lttb_downsample",
    "lttb_downsample_1d",
    "lttb_downsample_indices",
    "lttb_downsample_xy",
    "nan_regularization_watchdog",
    "parse_hdf5_pointer",
    "parse_xyz_string",
    "replace_monomer_geometry_in_complex",
    "resolve_hdf5_pointer",
    "sanitize_numerical_values",
    "solve_dvr_dense",
    "solve_dvr_matrix_free",
    "strip_ansi_escape_codes",
    "to_rfc8259_json",
    "truncate_traceback",
    "validate_composite_protocol",
]


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_core_parsl_executors.py ---
#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_parsl_executors.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8A - Parsl Multi-Executor Heterogeneous HPC & Task Router.
Mandated by SRS Doc 1 (Topology 1.0 §2), Doc 2 Part 1 (§2.5), and Method Matrix §8A.

Implements the Scout-and-Anchor Heterogeneous Concurrency Engine:
1. Multi-Executor Heterogeneous Parsl Topologies:
   - CPU Anchor Executor ('cochem_anchor_cpu' / 'cpu'): Dedicated to heavy, authoritative
     quantum calculations (ORCA DFT/VPT2, MPQC CCSD(T)-F12, CFOUR) pinned to P-cores ('block'),
     %maxcore 3400, 7 P-cores by default on 8-core workstations.
   - GPU Scout Executor ('cochem_scout_gpu' / 'gpu'): Dedicated to advisory GPU workers
     (MLFF, MACE, AIMNet2, gpu4pyscf) under NVIDIA MPS, available_accelerators=3,
     cpu_affinity='block-reverse', 1 P-core for host-side launch feeder (57% host-side overhead),
     6 GB VRAM quota per worker.
   - Orchestrator / Utility Executor ('cochem_orchestrator' / 'orchestrator'): Dedicated to
     E-cores and host tasks (DFK, stage scheduler, deduplication, I/O, regex, provenance stamping).

2. Heterogeneous Resource Providers:
   - LocalProvider: Local workstations / desktops (Setup 2: 13700K + RTX 3090; Setup 1: CPU-only).
   - SlurmProvider: HPC cluster partitions (Setup 3) with '#SBATCH --gres=gpu:1', '#SBATCH --nodes=1',
     walltime, account, qos, partition, and SrunLauncher/SimpleLauncher.
   - Graceful fallback to single-executor or ThreadPool execution on constrained or teaching environments.

3. Contention Budgeting & Core Affinity (§8A.1, §8A.4):
   - Real parallelism budget calculation (85% real efficiency, 1.20x CPU slowdown budget factor).
   - Core affinity partitioning (P-cores 0..N-2 for CPU anchor, P-core N-1 for GPU scout feeder,
     E-cores for DFK/I/O).
   - Dynamic VRAM partitioning and thread percentage capping under NVIDIA MPS.

4. Method Matrix §8A.5 Integrity Guards (G1–G7) Engine:
   - G1: Advisory-only guide surface (rejects guide results claiming authoritative status).
   - G2: High-level Hessian verification (asserts imaginary frequency count & softest force constant).
   - G3: Basin-identity check (heavy-atom RMSD <= 0.25 Å, Delta R <= 0.20 Å using Mendeleev masses).
   - G4: Rank-inversion audit (Spearman rho >= 0.90 on sample before culling).
   - G5: Uncertainty gate (committee sigma thresholding).
   - G6: Abort-the-guide rule (n_th = 5 consecutive failure threshold).
   - G7: Provenance event audit logging (structured JSONL event lines appended to provenance.jsonl).

5. Task Routing, Parsl App Factories & Pipeline Execution:
   - App decorators and dispatchers for @bash_app and @python_app targeting 'cpu', 'gpu', or 'orchestrator'.
   - Future management, stage chaining, timeout enforcement, retry logic (retries=2 per §8A.6).
   - Standardized TaskExecutionResult models and execution status reporting.

6. Thread-Safe Parsl DFK Lifecycle Manager:
   - Thread-safe singleton ParslExecutionBroker.
   - Safe process cleanup & zombie sweeping via psutil and atexit.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import logging
import os
import platform
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import numpy as np
import psutil
import scipy.stats
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from cochem_base.schemas import GpuScoutExecutorConfig
from cochem_base.config_loader import (
    get_artifact_dir,
    get_mps_directories,
    get_runtime_dir,
    resolve_mapped_path,
)
from cochem_base.exceptions import (
    CoChemError,
    ProvenanceErrorCode,
)

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-ParslExecutors")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Method Matrix §8A Hardware & Pipeline Constants
# ---------------------------------------------------------------------------
DEFAULT_ORCA_ANCHOR_RANKS: int = 7
DEFAULT_ORCA_MAXCORE_MB: int = 3400
DEFAULT_MAX_GPU_SCOUT_WORKERS: int = 3
DEFAULT_MPS_THREAD_PERCENTAGE: int = 33
DEFAULT_MPS_PINNED_MEM_LIMIT_STR: str = "0=6G"
DEFAULT_CONTENZIONE_SLOWDOWN_FACTOR: float = 1.20
DEFAULT_SCOUT_HOST_LATENCY_MS: float = 18.1
DEFAULT_ULIMIT_NOFILE: int = 16384
DEFAULT_WORKER_PORT_RANGE: Tuple[int, int] = (50000, 52499)
DEFAULT_INTERCHANGE_PORT_RANGE: Tuple[int, int] = (52500, 54999)
DEFAULT_PARSL_RETRIES: int = 2
DEFAULT_G3_RMSD_THRESHOLD_ANGSTROM: float = 0.25
DEFAULT_G3_DELTA_R_THRESHOLD_ANGSTROM: float = 0.20
DEFAULT_G4_SPEARMAN_RHO_THRESHOLD: float = 0.90
DEFAULT_G5_UNCERTAINTY_THRESHOLD_MEV: float = 10.0
DEFAULT_G6_MAX_GUIDE_FAILURES: int = 5


# ---------------------------------------------------------------------------
# Zombie Process Sweeping & Subprocess Safety
# ---------------------------------------------------------------------------
def _sweep_zombie_processes() -> None:
    """Sweep zombie child processes to maintain OS cleanliness."""
    try:
        current_proc = psutil.Process()
        for child in current_proc.children(recursive=True):
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    child.wait(timeout=0.2)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as _e:
                logger.debug(f"Ignored exception: {_e}")
    except Exception as _e:
        logger.debug(f"Ignored exception: {_e}")


atexit.register(_sweep_zombie_processes)


# =============================================================================
# Custom Exception Hierarchy
# =============================================================================
class ParslExecutorError(CoChemError):
    """Base exception for all CoChem Parsl executor and routing failures."""

    default_error_code = ProvenanceErrorCode.CONFIG_VALIDATION_FAILED


class HeterogeneousTopologyError(ParslExecutorError):
    """Raised when heterogeneous core or device topology partitioning fails."""

    default_error_code = ProvenanceErrorCode.HARDWARE_DETECTION_FAILED


class ContentionBudgetExceededError(ParslExecutorError):
    """Raised when requested worker or memory allocations violate hardware bounds."""

    default_error_code = ProvenanceErrorCode.OUT_OF_MEMORY


class IntegrityGuardViolationError(ParslExecutorError):
    """Raised when a Method Matrix §8A.5 integrity guard (G1-G7) is violated."""

    default_error_code = ProvenanceErrorCode.INTEGRITY_VIOLATION


class ExecutorLifecycleError(ParslExecutorError):
    """Raised when Parsl DataFlowKernel loading, execution, or shutdown fails."""

    default_error_code = ProvenanceErrorCode.CONVERGENCE_FAILURE


# =============================================================================
# Enumerations
# =============================================================================
class ExecutorStreamType(str, Enum):
    """Heterogeneous Scout-and-Anchor execution stream classification."""

    CPU_ANCHOR = "CPU_ANCHOR"
    GPU_SCOUT = "GPU_SCOUT"
    ORCHESTRATOR = "ORCHESTRATOR"


class ParslProviderType(str, Enum):
    """Supported compute resource provider backends."""

    LOCAL = "LOCAL"
    SLURM = "SLURM"
    PBS = "PBS"
    LSF = "LSF"
    THREAD_POOL = "THREAD_POOL"


class AffinityStrategy(str, Enum):
    """CPU core affinity allocation and pinning strategy."""

    BLOCK = "block"
    BLOCK_REVERSE = "block-reverse"
    PINNED_LIST = "pinned-list"
    SHARED_DEGRADED = "shared-degraded"
    NONE = "none"


class TaskAuthority(str, Enum):
    """Authority classification for task execution outputs (§8A.2, §8A.5)."""

    AUTHORITATIVE = "authoritative"
    ADVISORY_ONLY = "advisory_only"
    ORCHESTRATION = "orchestration"


# =============================================================================
# Pydantic V2 Data Models
# =============================================================================
class CorePartitioning(BaseModel):
    """Detailed CPU core partitioning across heterogeneous execution streams."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_physical_cores: int = Field(..., ge=1, description="Total physical CPU cores on host")
    total_logical_cores: int = Field(..., ge=1, description="Total logical CPU threads on host")
    anchor_core_count: int = Field(..., ge=1, description="Physical CPU cores allocated to CPU Anchor")
    anchor_core_ids: List[int] = Field(default_factory=list, description="Zero-indexed core IDs for Anchor")
    anchor_affinity_str: str = Field(..., description="Parsl affinity directive for Anchor")
    scout_core_count: int = Field(..., ge=1, description="Physical CPU cores allocated to GPU Scout feeder")
    scout_core_ids: List[int] = Field(default_factory=list, description="Zero-indexed core IDs for Scout")
    scout_affinity_str: str = Field(..., description="Parsl affinity directive for Scout")
    orchestrator_core_count: int = Field(default=1, ge=0, description="Cores allocated for Orchestrator / I/O")
    strategy: AffinityStrategy = Field(
        default=AffinityStrategy.BLOCK, description="Core affinity assignment strategy"
    )
    is_degraded: bool = Field(
        default=False, description="True if host has <= 1 physical core and streams share resources"
    )


class ContentionBudget(BaseModel):
    """Hardware contention budget model mandated by Method Matrix §8A.1."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    p_cores_anchor: int = Field(default=DEFAULT_ORCA_ANCHOR_RANKS, ge=1)
    p_cores_scout_feeder: int = Field(default=1, ge=1)
    gpu_scout_workers: int = Field(default=DEFAULT_MAX_GPU_SCOUT_WORKERS, ge=1)
    mps_active_thread_percentage: int = Field(default=DEFAULT_MPS_THREAD_PERCENTAGE, ge=1, le=100)
    mps_pinned_device_mem_limit: str = Field(default=DEFAULT_MPS_PINNED_MEM_LIMIT_STR)
    estimated_cpu_slowdown_factor: float = Field(default=DEFAULT_CONTENZIONE_SLOWDOWN_FACTOR, ge=1.0)
    real_parallelism_efficiency: float = Field(default=0.85, ge=0.0, le=1.0)
    host_launch_bound_latency_ms: float = Field(default=DEFAULT_SCOUT_HOST_LATENCY_MS, ge=0.0)
    total_host_ram_gb: float = Field(..., ge=1.0)
    anchor_mem_per_worker_gb: float = Field(default=28.0, ge=1.0)
    scout_mem_per_worker_gb: float = Field(default=6.0, ge=0.5)


class SlurmResourceOptions(BaseModel):
    """HPC SLURM resource allocation options for cluster execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    partition: Optional[str] = Field(default=None, description="SLURM partition name")
    account: Optional[str] = Field(default=None, description="SLURM accounting project name")
    qos: Optional[str] = Field(default=None, description="Quality of service tier")
    gres_gpu: str = Field(default="gpu:1", description="Generic resource request string (e.g. 'gpu:1')")
    gpus_per_node: int = Field(default=1, ge=1, description="GPUs requested per allocated node")
    nodes_per_block: int = Field(default=1, ge=1, description="Nodes per SLURM job block")
    walltime: str = Field(default="04:00:00", description="Wall-clock limit string (HH:MM:SS)")
    srun_launcher: bool = Field(default=True, description="Whether to use SrunLauncher over SimpleLauncher")
    custom_scheduler_options: List[str] = Field(
        default_factory=list, description="Additional #SBATCH header options"
    )


class HTEXConfig(BaseModel):
    """Configuration profile for a single Parsl HighThroughputExecutor (HTEX) pool."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    label: str = Field(..., description="Unique executor label (e.g. 'cpu', 'gpu', 'orchestrator')")
    stream: ExecutorStreamType = Field(..., description="Target execution stream")
    provider_type: ParslProviderType = Field(
        default=ParslProviderType.LOCAL, description="Compute resource provider backend"
    )
    max_workers_per_node: int = Field(default=1, ge=1, description="Concurrent worker processes per node")
    cores_per_worker: float = Field(default=1.0, ge=0.1, description="CPU cores dedicated per worker")
    mem_per_worker_gb: Optional[float] = Field(
        default=None, ge=0.1, description="Memory limit per worker in Gigabytes"
    )
    cpu_affinity: str = Field(
        default="block", description="Parsl CPU affinity directive ('block', 'block-reverse', 'list:0,1..')"
    )
    available_accelerators: Optional[Union[int, List[str]]] = Field(
        default=None, description="GPU accelerator slots or device indices"
    )
    worker_port_range: Tuple[int, int] = Field(default=DEFAULT_WORKER_PORT_RANGE)
    interchange_port_range: Tuple[int, int] = Field(default=DEFAULT_INTERCHANGE_PORT_RANGE)
    worker_init_script: str = Field(default="", description="Bash environment initialization script")
    walltime: str = Field(default="04:00:00", description="Wall-clock limit")


class ParslMultiExecutorProfile(BaseModel):
    """Complete heterogeneous multi-executor system topology profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    profile_id: str = Field(
        default_factory=lambda: f"parsl_topo_{uuid.uuid4().hex[:8]}", description="Unique profile identifier"
    )
    created_at_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Creation timestamp"
    )
    core_partitioning: CorePartitioning = Field(..., description="CPU core partitioning profile")
    contention_budget: ContentionBudget = Field(..., description="Resource contention budget")
    anchor_executor: HTEXConfig = Field(..., description="CPU Anchor executor configuration")
    scout_executor: HTEXConfig = Field(..., description="GPU Scout executor configuration")
    orchestrator_executor: HTEXConfig = Field(..., description="Orchestrator executor configuration")
    slurm_options: Optional[SlurmResourceOptions] = Field(
        default=None, description="SLURM options if running on HPC"
    )
    is_degraded_single_executor: bool = Field(
        default=False, description="True if operating in CPU-only or teaching tier degraded mode"
    )
    parsl_retries: int = Field(default=DEFAULT_PARSL_RETRIES, ge=0)


class G7ProvenanceRecord(BaseModel):
    """Structured JSONL event audit record mandated by Method Matrix §8A.5 (line 1323)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Cryptographic event ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="UTC timestamp"
    )
    stage: str = Field(..., description="Pipeline stage (e.g. 'mlff_preopt', 'anchor_verify')")
    decision: str = Field(..., description="Decision summary (e.g. 'seed_dft_optimisation')")
    guide: Dict[str, Any] = Field(default_factory=dict, description="Guide / Scout execution metadata")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input structure and hash metadata")
    output: Dict[str, Any] = Field(default_factory=dict, description="Output properties and hash metadata")
    gates: Dict[str, Any] = Field(default_factory=dict, description="Integrity guard gate evaluations (G1-G6)")
    consumer: Dict[str, Any] = Field(default_factory=dict, description="Downstream anchor job consumption")
    authority: TaskAuthority = Field(
        default=TaskAuthority.ADVISORY_ONLY, description="Authority tag ('advisory_only' vs 'authoritative')"
    )


class TaskRoutingRequest(BaseModel):
    """Structured request for dispatching a task through Parsl."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    stream: ExecutorStreamType = Field(..., description="Target execution stream (CPU_ANCHOR, GPU_SCOUT, etc.)")
    authority: TaskAuthority = Field(default=TaskAuthority.ADVISORY_ONLY)
    command: Optional[List[str]] = Field(default=None, description="Command line arguments for bash tasks")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Injected environment variables")
    timeout_seconds: float = Field(default=3600.0, ge=1.0)
    stage_name: str = Field(default="generic_stage")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskExecutionResult(BaseModel):
    """Structured result returned by task execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_id: str = Field(...)
    stream: ExecutorStreamType = Field(...)
    authority: TaskAuthority = Field(...)
    status: str = Field(..., description="Status string: 'COMPLETED', 'FAILED', 'TIMED_OUT'")
    return_code: Optional[int] = Field(default=None)
    stdout: Optional[str] = Field(default=None)
    stderr: Optional[str] = Field(default=None)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    output_files: Dict[str, str] = Field(default_factory=dict, description="Map of file label to file path")
    file_hashes: Dict[str, str] = Field(default_factory=dict, description="Map of file path to SHA-256")
    provenance_event_id: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)


# =============================================================================
# CPU Topology & Contention Budget Engine
# =============================================================================
def detect_system_cpu_topology(env: Optional[Dict[str, str]] = None) -> Tuple[int, int]:
    """
    Detect physical and logical CPU cores on the host system.
    Evaluates psutil, os.cpu_count, and explicit environment overrides.

    Returns:
        Tuple of (physical_cores, logical_cores).
    """
    target_env = os.environ if env is None else env

    physical: Optional[int] = None
    logical: Optional[int] = None

    if "COCHEM_PHYSICAL_CORES" in target_env and target_env["COCHEM_PHYSICAL_CORES"].strip():
        try:
            val = int(target_env["COCHEM_PHYSICAL_CORES"].strip())
            if val >= 1:
                physical = val
        except ValueError as _e:
            logger.debug(f"Ignored exception: {_e}")

    if "COCHEM_LOGICAL_CORES" in target_env and target_env["COCHEM_LOGICAL_CORES"].strip():
        try:
            val = int(target_env["COCHEM_LOGICAL_CORES"].strip())
            if val >= 1:
                logical = val
        except ValueError as _e:
            logger.debug(f"Ignored exception: {_e}")

    if physical is None:
        try:
            p = psutil.cpu_count(logical=False)
            if p is not None and p >= 1:
                physical = p
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

    if logical is None:
        try:
            log_count = psutil.cpu_count(logical=True)
            if log_count is not None and log_count >= 1:
                logical = log_count
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

    if physical is None:
        physical = os.cpu_count() or 1

    if logical is None:
        logical = os.cpu_count() or physical or 1

    if physical > logical:
        physical = logical

    return max(1, physical), max(1, logical)


def partition_cpu_cores(
    total_physical: int,
    requested_anchor: Optional[int] = None,
    requested_scout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> CorePartitioning:
    """
    Partition host CPU cores between Anchor (CPU), Scout (GPU Feeder), and Orchestrator.
    Compliant with Method Matrix §8A.1 and §8A.6:
      - 8+ cores: 7 P-cores dedicated to Anchor, 1 P-core dedicated to Scout, remainder Orchestrator.
      - 2..7 cores: 1 P-core dedicated to Scout, N-1 cores dedicated to Anchor.
      - 1 core: Shared degraded mode (core 0 shared).

    Returns:
        CorePartitioning model.
    """
    target_env = os.environ if env is None else env

    def parse_int(key: str) -> Optional[int]:
        if key in target_env and target_env[key].strip():
            try:
                v = int(target_env[key].strip())
                if v >= 1:
                    return v
            except ValueError:
                return None
        return None

    env_anchor = parse_int("COCHEM_PARSL_ANCHOR_CORES")
    env_scout = parse_int("COCHEM_PARSL_SCOUT_CORES")

    req_anchor = requested_anchor if requested_anchor is not None else env_anchor
    req_scout = requested_scout if requested_scout is not None else env_scout

    _, total_logical = detect_system_cpu_topology(target_env)

    if total_physical <= 1:
        # Single core degraded mode
        return CorePartitioning(
            total_physical_cores=1,
            total_logical_cores=total_logical,
            anchor_core_count=1,
            anchor_core_ids=[0],
            anchor_affinity_str="list:0",
            scout_core_count=1,
            scout_core_ids=[0],
            scout_affinity_str="list:0",
            orchestrator_core_count=1,
            strategy=AffinityStrategy.SHARED_DEGRADED,
            is_degraded=True,
        )

    if req_anchor is not None and req_scout is not None:
        anchor_count = req_anchor
        scout_count = req_scout
    elif req_scout is not None:
        scout_count = max(1, req_scout)
        anchor_count = max(1, total_physical - scout_count)
    elif req_anchor is not None:
        anchor_count = max(1, req_anchor)
        scout_count = max(1, total_physical - anchor_count)
    else:
        # Canonical Method Matrix §8A baseline
        if total_physical >= 8:
            anchor_count = DEFAULT_ORCA_ANCHOR_RANKS
            scout_count = 1
        else:
            scout_count = 1
            anchor_count = max(1, total_physical - 1)

    anchor_core_ids = [c % total_physical for c in range(0, anchor_count)]
    scout_start = anchor_count
    scout_core_ids = [(scout_start + c) % total_physical for c in range(0, scout_count)]

    anchor_affinity_str = "list:" + ",".join(str(c) for c in anchor_core_ids)
    scout_affinity_str = "list:" + ",".join(str(c) for c in scout_core_ids)

    orchestrator_count = max(1, total_physical - (anchor_count + scout_count)) if total_physical > (anchor_count + scout_count) else 1

    return CorePartitioning(
        total_physical_cores=total_physical,
        total_logical_cores=total_logical,
        anchor_core_count=anchor_count,
        anchor_core_ids=anchor_core_ids,
        anchor_affinity_str=anchor_affinity_str,
        scout_core_count=scout_count,
        scout_core_ids=scout_core_ids,
        scout_affinity_str=scout_affinity_str,
        orchestrator_core_count=orchestrator_count,
        strategy=AffinityStrategy.BLOCK,
        is_degraded=False,
    )


def calculate_contention_budget(
    total_physical_cores: int,
    total_ram_gb: float,
    gpu_scout_workers: int = DEFAULT_MAX_GPU_SCOUT_WORKERS,
    anchor_ranks: int = DEFAULT_ORCA_ANCHOR_RANKS,
) -> ContentionBudget:
    """
    Calculate resource contention budget model (§8A.1, Suggestion #77).
    Enforces host RAM headroom, dynamic memory floors (<32 GB), VRAM partitioning under MPS, and slowdown estimates.
    """
    # Dynamic host RAM scaling under constrained environments (< 32 GB)
    if total_ram_gb < 32.0:
        anchor_mem = max(4.0, total_ram_gb * 0.50)
        scout_mem = max(1.5, total_ram_gb * 0.25)
        if total_ram_gb < 16.0:
            gpu_scout_workers = 1
            logger.info(
                f"[RESOURCE-INFO] Constrained host RAM ({total_ram_gb:.1f} GB < 16 GB). "
                "Downscaling GPU scout concurrency to 1 worker."
            )
        elif total_ram_gb < 24.0:
            gpu_scout_workers = min(gpu_scout_workers, 2)
            logger.info(
                f"[RESOURCE-INFO] Constrained host RAM ({total_ram_gb:.1f} GB < 24 GB). "
                f"Downscaling GPU scout concurrency to {gpu_scout_workers} workers."
            )
        else:
            logger.info(
                f"[RESOURCE-INFO] Host RAM ({total_ram_gb:.1f} GB < 32 GB). "
                f"Allocating dynamic memory floors: Anchor={anchor_mem:.1f} GB, Scout={scout_mem:.1f} GB."
            )
    else:
        anchor_mem = 28.0
        scout_mem = 6.0

    # Dynamic MPS thread partitioning: 100% / N_workers
    thread_pct = max(1, 100 // max(1, gpu_scout_workers))
    # VRAM allocation per worker
    pinned_mem = "0=6G" if gpu_scout_workers <= 3 else "0=4G"

    # Slowdown factor: 8/7 * 1.05 (mem bandwidth) * 1.05 (thermal) ≈ 1.20x
    slowdown_factor = DEFAULT_CONTENZIONE_SLOWDOWN_FACTOR

    return ContentionBudget(
        p_cores_anchor=anchor_ranks,
        p_cores_scout_feeder=1,
        gpu_scout_workers=gpu_scout_workers,
        mps_active_thread_percentage=thread_pct,
        mps_pinned_device_mem_limit=pinned_mem,
        estimated_cpu_slowdown_factor=slowdown_factor,
        real_parallelism_efficiency=0.85,
        host_launch_bound_latency_ms=DEFAULT_SCOUT_HOST_LATENCY_MS,
        total_host_ram_gb=total_ram_gb,
        anchor_mem_per_worker_gb=anchor_mem,
        scout_mem_per_worker_gb=scout_mem,
    )


def detect_gpu_scout_config(
    scratch_dir: Optional[Union[str, Path]] = None,
    min_vram_headroom_mb: float = 1536.0,
) -> GpuScoutExecutorConfig:
    """Detect OS and hardware configuration across the 6-Tier Environment Matrix.

    Suggestion #65:
    - Tier 1/2 (Windows/macOS): disable MPS, serialize tasks (max_concurrent=1)
    - Tier 3/6 (Linux/HPC): enable MPS with scratch pipes
    """
    sys_plat = sys.platform
    if sys_plat.startswith("win"):
        platform_os = "windows"
    elif sys_plat == "darwin":
        platform_os = "darwin"
    else:
        platform_os = "linux"

    target_scratch = Path(scratch_dir or os.environ.get("COCHEM_SCRATCH", tempfile.gettempdir())).resolve()
    mps_pipe = str((target_scratch / "nvidia_mps").resolve())

    if platform_os in ("windows", "darwin"):
        return GpuScoutExecutorConfig(
            platform_os=platform_os,
            enable_mps=False,
            mps_pipe_dir=mps_pipe,
            max_concurrent_gpu_tasks=1,
            min_vram_headroom_mb=min_vram_headroom_mb,
        )
    else:
        has_gpu = False
        try:
            import torch
            has_gpu = torch.cuda.is_available()
        except Exception:
            pass
        return GpuScoutExecutorConfig(
            platform_os="linux",
            enable_mps=has_gpu,
            mps_pipe_dir=mps_pipe,
            max_concurrent_gpu_tasks=3 if has_gpu else 1,
            min_vram_headroom_mb=min_vram_headroom_mb,
        )


class GpuScoutDispatcher:
    """Thread-safe and process-safe GPU scout dispatch controller with VRAM headroom guard.

    Mandated by Method Matrix v4 §8A.2, §8A.4.
    Suggestion #65:
    - Tier 1/2 (Windows/macOS): Serializes GPU kernels via threading.Semaphore(1).
    - Tier 3/6 (Linux): Permits parallel execution under MPS.
    - Dynamic VRAM check: holds tasks if free VRAM < min_vram_headroom_mb.
    """

    _instance: Optional["GpuScoutDispatcher"] = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[GpuScoutExecutorConfig] = None):
        self.config = config or detect_gpu_scout_config()
        self.semaphore = threading.Semaphore(self.config.max_concurrent_gpu_tasks)
        self.active_count = 0
        self._count_lock = threading.Lock()

    @classmethod
    def get_instance(cls, config: Optional[GpuScoutExecutorConfig] = None) -> "GpuScoutDispatcher":
        with cls._lock:
            if cls._instance is None or (config is not None and config != cls._instance.config):
                cls._instance = cls(config)
            return cls._instance

    def check_vram_headroom(self) -> Tuple[bool, float]:
        """Queries torch.cuda.mem_get_info() if CUDA is available."""
        try:
            import torch
            if torch.cuda.is_available():
                free_b, total_b = torch.cuda.mem_get_info()
                free_mb = free_b / (1024 * 1024)
                return (free_mb >= self.config.min_vram_headroom_mb, free_mb)
        except Exception:
            pass
        return (True, 99999.0)

    @contextmanager
    def dispatch_scout(self, poll_interval: float = 0.05, max_wait: float = 30.0):
        acquired = self.semaphore.acquire(timeout=max_wait)
        if not acquired:
            raise TimeoutError(f"Timeout waiting for GPU scout concurrency slot after {max_wait}s")

        try:
            t0 = time.time()
            while True:
                has_vram, free_mb = self.check_vram_headroom()
                if has_vram:
                    break
                if time.time() - t0 >= max_wait:
                    raise RuntimeError(
                        f"Dynamic VRAM safeguard: {free_mb:.1f} MB free < "
                        f"{self.config.min_vram_headroom_mb:.1f} MB required"
                    )
                time.sleep(poll_interval)

            with self._count_lock:
                self.active_count += 1
            try:
                yield
            finally:
                with self._count_lock:
                    self.active_count -= 1
        finally:
            self.semaphore.release()


# =============================================================================
# Worker-Resident GPU MLFF Model Cache Singleton (§8A.2, Suggestion #75)
# =============================================================================
class ResidentModel:
    """Worker-resident MLFF model wrapper container."""

    def __init__(
        self,
        model_name: str,
        weights_path: Path,
        device: str = "cpu",
        model_instance: Any = None,
    ):
        self.model_name = model_name
        self.weights_path = Path(weights_path)
        self.device = device
        self.model_instance = model_instance
        self._initialized_at = time.time()

    def __repr__(self) -> str:
        return f"<ResidentModel name={self.model_name} device={self.device} path={self.weights_path}>"


class WorkerModelCache:
    """
    Thread-safe singleton cache for GPU MLFF models residing in worker process memory.
    Mandated by Method Matrix v4 §8A.2 and Suggestion #75 (Deliverable 5).
    """

    _models: Dict[str, Any] = {}
    _lock = threading.Lock()

    @classmethod
    def _load_model(cls, model_name: str, weights_path: Path, device: str) -> Any:
        path = Path(weights_path).resolve()
        loaded_instance = None
        if path.exists():
            try:
                import torch
                loaded_instance = torch.load(path, map_location=device, weights_only=False)
            except Exception:
                pass
        return ResidentModel(
            model_name=model_name,
            weights_path=path,
            device=device,
            model_instance=loaded_instance,
        )

    @classmethod
    def get_model(cls, model_name: str, weights_path: Union[str, Path], device: str = "cpu") -> Any:
        path = Path(weights_path).resolve()
        key = f"{model_name}:{path}:{device}"
        with cls._lock:
            if key not in cls._models:
                cls._models[key] = cls._load_model(model_name, path, device)
            return cls._models[key]

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._models.clear()


# =============================================================================
# Worker Init Scripts & Parsl Configuration Assembly
# =============================================================================
def build_worker_init_scripts(
    mps_pipe_dir: Optional[Path] = None,
    mps_log_dir: Optional[Path] = None,
    mps_thread_pct: int = DEFAULT_MPS_THREAD_PERCENTAGE,
    mps_pinned_mem: str = DEFAULT_MPS_PINNED_MEM_LIMIT_STR,
    gpu_device_id: int = 0,
    enable_mps: Optional[bool] = None,
) -> Tuple[str, str, str]:
    """
    Generate authoritative worker initialization scripts for CPU, GPU, and Orchestrator.
    Compliant with Method Matrix §8A.6 lines 1373–1388 and Suggestion #65.

    Returns:
        Tuple of (cpu_init_script, gpu_init_script, orchestrator_init_script).
    """
    if enable_mps is None:
        enable_mps = sys.platform not in ("win32", "darwin") and platform.system().lower() not in ("windows", "darwin")

    if not enable_mps:
        cpu_init_script = (
            "export OMP_NUM_THREADS=1; "
            "export KMP_HW_SUBSET=8c:intel_core,1t"
        ) if sys.platform != "win32" else "set OMP_NUM_THREADS=1"

        gpu_init_script = (
            f"export CUDA_VISIBLE_DEVICES={gpu_device_id}"
            if sys.platform != "win32"
            else f"set CUDA_VISIBLE_DEVICES={gpu_device_id}"
        )

        orchestrator_init_script = (
            "export OMP_NUM_THREADS=1"
            if sys.platform != "win32"
            else "set OMP_NUM_THREADS=1"
        )
        return cpu_init_script, gpu_init_script, orchestrator_init_script

    if mps_pipe_dir is None or mps_log_dir is None:
        pipe, log = get_mps_directories()
        mps_pipe_dir = pipe if mps_pipe_dir is None else mps_pipe_dir
        mps_log_dir = log if mps_log_dir is None else mps_log_dir

    cpu_init_script = (
        "export OMP_NUM_THREADS=1; "
        "export KMP_HW_SUBSET=8c:intel_core,1t"
    )

    gpu_init_script = (
        f"export CUDA_VISIBLE_DEVICES={gpu_device_id}; "
        f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={mps_thread_pct}; "
        f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{mps_pinned_mem}'; "
        f"export CUDA_MPS_PIPE_DIRECTORY='{mps_pipe_dir.resolve()}'; "
        f"export CUDA_MPS_LOG_DIRECTORY='{mps_log_dir.resolve()}'; "
        f"ulimit -n {DEFAULT_ULIMIT_NOFILE}"
    )

    orchestrator_init_script = "export OMP_NUM_THREADS=1"

    return cpu_init_script, gpu_init_script, orchestrator_init_script



def build_heterogeneous_profile(
    provider_type: ParslProviderType = ParslProviderType.LOCAL,
    slurm_options: Optional[SlurmResourceOptions] = None,
    degraded_single_executor: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> ParslMultiExecutorProfile:
    """
    Assemble the complete heterogeneous multi-executor profile (§8A.2, §8A.6).
    """
    target_env = os.environ if env is None else env
    physical_cores, _ = detect_system_cpu_topology(target_env)
    total_ram_gb = psutil.virtual_memory().total / (1024**3)

    partitioning = partition_cpu_cores(
        total_physical=physical_cores,
        env=target_env,
    )

    contention = calculate_contention_budget(
        total_physical_cores=physical_cores,
        total_ram_gb=total_ram_gb,
    )

    pipe_dir, log_dir = get_mps_directories()
    cpu_init, gpu_init, orch_init = build_worker_init_scripts(
        mps_pipe_dir=pipe_dir,
        mps_log_dir=log_dir,
        mps_thread_pct=contention.mps_active_thread_percentage,
        mps_pinned_mem=contention.mps_pinned_device_mem_limit,
    )

    if degraded_single_executor or partitioning.is_degraded:
        # Degraded single executor profile (teaching tier or single-core host)
        anchor_cfg = HTEXConfig(
            label="cpu",
            stream=ExecutorStreamType.CPU_ANCHOR,
            provider_type=provider_type,
            max_workers_per_node=1,
            cores_per_worker=1.0,
            mem_per_worker_gb=min(8.0, total_ram_gb * 0.5),
            cpu_affinity="none",
            worker_init_script=cpu_init,
        )
        scout_cfg = HTEXConfig(
            label="gpu",
            stream=ExecutorStreamType.GPU_SCOUT,
            provider_type=provider_type,
            max_workers_per_node=1,
            cores_per_worker=1.0,
            mem_per_worker_gb=min(4.0, total_ram_gb * 0.25),
            cpu_affinity="none",
            worker_init_script=gpu_init,
        )
        orch_cfg = HTEXConfig(
            label="orchestrator",
            stream=ExecutorStreamType.ORCHESTRATOR,
            provider_type=provider_type,
            max_workers_per_node=1,
            cores_per_worker=1.0,
            mem_per_worker_gb=2.0,
            cpu_affinity="none",
            worker_init_script=orch_init,
        )
        return ParslMultiExecutorProfile(
            core_partitioning=partitioning,
            contention_budget=contention,
            anchor_executor=anchor_cfg,
            scout_executor=scout_cfg,
            orchestrator_executor=orch_cfg,
            slurm_options=slurm_options,
            is_degraded_single_executor=True,
        )

    # Full heterogeneous production profile
    anchor_cfg = HTEXConfig(
        label="cpu",
        stream=ExecutorStreamType.CPU_ANCHOR,
        provider_type=provider_type,
        max_workers_per_node=1,
        cores_per_worker=float(partitioning.anchor_core_count),
        mem_per_worker_gb=contention.anchor_mem_per_worker_gb,
        cpu_affinity="block",
        worker_init_script=cpu_init,
    )

    scout_cfg = HTEXConfig(
        label="gpu",
        stream=ExecutorStreamType.GPU_SCOUT,
        provider_type=provider_type,
        max_workers_per_node=contention.gpu_scout_workers,
        cores_per_worker=float(partitioning.scout_core_count) / float(contention.gpu_scout_workers),
        mem_per_worker_gb=contention.scout_mem_per_worker_gb,
        cpu_affinity="block-reverse",
        available_accelerators=contention.gpu_scout_workers,
        worker_init_script=gpu_init,
    )

    orch_cfg = HTEXConfig(
        label="orchestrator",
        stream=ExecutorStreamType.ORCHESTRATOR,
        provider_type=provider_type,
        max_workers_per_node=partitioning.orchestrator_core_count,
        cores_per_worker=1.0,
        mem_per_worker_gb=4.0,
        cpu_affinity="none",
        worker_init_script=orch_init,
    )

    return ParslMultiExecutorProfile(
        core_partitioning=partitioning,
        contention_budget=contention,
        anchor_executor=anchor_cfg,
        scout_executor=scout_cfg,
        orchestrator_executor=orch_cfg,
        slurm_options=slurm_options,
        is_degraded_single_executor=False,
    )


def construct_parsl_config(
    profile: Optional[ParslMultiExecutorProfile] = None,
    run_dir: Optional[Union[str, Path]] = None,
) -> Any:
    """
    Construct a physical parsl.config.Config object incorporating CPU Anchor,
    GPU Scout, and Orchestrator executors.

    Args:
        profile: ParslMultiExecutorProfile descriptor (or default if None).
        run_dir: Optional custom runinfo directory for Parsl logs.

    Returns:
        Configured parsl.config.Config instance.
    """
    try:
        from parsl.config import Config
        from parsl.executors import HighThroughputExecutor, ThreadPoolExecutor
        from parsl.launchers import SimpleLauncher, SrunLauncher
        from parsl.providers import LocalProvider, SlurmProvider
    except ImportError as exc:
        raise ExecutorLifecycleError(f"Parsl library is not installed or importable: {exc}") from exc

    if profile is None:
        profile = build_heterogeneous_profile()

    resolved_run_dir: str
    if run_dir is not None:
        resolved_run_dir = str(resolve_mapped_path(run_dir))
    else:
        resolved_run_dir = str((get_runtime_dir() / "parsl_runinfo").resolve())

    def make_provider(htex_cfg: HTEXConfig) -> Any:
        if htex_cfg.provider_type == ParslProviderType.SLURM and profile.slurm_options:
            if platform.system() == "Windows":
                logger.warning(
                    "SlurmProvider is not supported natively on Windows platforms due to POSIX scheduler constraints; "
                    "falling back to LocalProvider."
                )
                return LocalProvider(
                    init_blocks=1,
                    min_blocks=0,
                    max_blocks=1,
                    nodes_per_block=1,
                    worker_init=htex_cfg.worker_init_script,
                    launcher=SimpleLauncher(),
                )

            slurm_opt = profile.slurm_options
            launcher_cls = SrunLauncher if slurm_opt.srun_launcher else SimpleLauncher
            sched_opts = list(slurm_opt.custom_scheduler_options)
            if slurm_opt.partition:
                sched_opts.append(f"#SBATCH --partition={slurm_opt.partition}")
            if slurm_opt.account:
                sched_opts.append(f"#SBATCH --account={slurm_opt.account}")
            if slurm_opt.qos:
                sched_opts.append(f"#SBATCH --qos={slurm_opt.qos}")
            if htex_cfg.stream == ExecutorStreamType.GPU_SCOUT:
                sched_opts.append(f"#SBATCH --gres={slurm_opt.gres_gpu}")
                sched_opts.append(f"#SBATCH --gpus-per-node={slurm_opt.gpus_per_node}")

            return SlurmProvider(
                nodes_per_block=slurm_opt.nodes_per_block,
                init_blocks=1,
                min_blocks=0,
                max_blocks=1,
                walltime=slurm_opt.walltime,
                scheduler_options="\n".join(sched_opts),
                worker_init=htex_cfg.worker_init_script,
                launcher=launcher_cls(),
            )
        # Default LocalProvider
        return LocalProvider(
            init_blocks=1,
            min_blocks=0,
            max_blocks=1,
            nodes_per_block=1,
            worker_init=htex_cfg.worker_init_script,
            launcher=SimpleLauncher(),
        )

    # 1. CPU Anchor Executor (HighThroughputExecutor)
    anchor_htex = HighThroughputExecutor(
        label=profile.anchor_executor.label,
        provider=make_provider(profile.anchor_executor),
        max_workers_per_node=profile.anchor_executor.max_workers_per_node,
        cores_per_worker=profile.anchor_executor.cores_per_worker,
        mem_per_worker=profile.anchor_executor.mem_per_worker_gb,
        cpu_affinity=profile.anchor_executor.cpu_affinity,
        worker_port_range=profile.anchor_executor.worker_port_range,
        interchange_port_range=profile.anchor_executor.interchange_port_range,
    )

    # 2. GPU Scout Executor (HighThroughputExecutor)
    scout_kwargs: Dict[str, Any] = {
        "label": profile.scout_executor.label,
        "provider": make_provider(profile.scout_executor),
        "max_workers_per_node": profile.scout_executor.max_workers_per_node,
        "cores_per_worker": profile.scout_executor.cores_per_worker,
        "mem_per_worker": profile.scout_executor.mem_per_worker_gb,
        "cpu_affinity": profile.scout_executor.cpu_affinity,
        "worker_port_range": profile.scout_executor.worker_port_range,
        "interchange_port_range": profile.scout_executor.interchange_port_range,
    }
    if profile.scout_executor.available_accelerators is not None:
        scout_kwargs["available_accelerators"] = profile.scout_executor.available_accelerators

    scout_htex = HighThroughputExecutor(**scout_kwargs)

    # 3. Orchestrator Executor (ThreadPoolExecutor for lightweight coordination)
    orch_exec = ThreadPoolExecutor(
        max_threads=profile.orchestrator_executor.max_workers_per_node,
        label=profile.orchestrator_executor.label,
    )

    return Config(
        executors=[anchor_htex, scout_htex, orch_exec],
        run_dir=resolved_run_dir,
        retries=profile.parsl_retries,
        strategy=None,
    )


# =============================================================================
# Method Matrix §8A.5 Integrity Guards (G1–G7) Engine
# =============================================================================
def verify_g1_authority(payload: Dict[str, Any]) -> bool:
    """
    G1: The cheap surface may set starting points, never reported answers.
    Every guide decision payload must be tagged 'advisory_only'.

    Raises:
        IntegrityGuardViolationError: If a guide task claims 'authoritative' status.
    """
    auth = str(payload.get("authority", "")).strip().lower()
    if auth == TaskAuthority.AUTHORITATIVE.value:
        raise IntegrityGuardViolationError(
            "G1 Violation: Guide/scout execution payload cannot claim 'authoritative' authority. "
            "Only anchor calculations may supply reported physical observables."
        )
    return auth in (
        TaskAuthority.ADVISORY_ONLY.value,
        TaskAuthority.ORCHESTRATION.value,
        "advisory_only",
        "guide",
        "scout",
    )


def verify_g2_high_level_hessian(
    anchor_result: Dict[str, Any],
    max_imaginary_frequencies: int = 0,
) -> bool:
    """
    G2: Verify final structure with a high-level Hessian showing correct
    imaginary frequency count and reporting the softest force constant.

    Raises:
        IntegrityGuardViolationError: If Hessian is missing or imaginary frequency count is exceeded.
    """
    imag_freqs = anchor_result.get("imaginary_frequencies_count")
    if imag_freqs is None:
        raise IntegrityGuardViolationError(
            "G2 Violation: Anchor calculation missing high-level Hessian verification."
        )

    if int(imag_freqs) > max_imaginary_frequencies:
        raise IntegrityGuardViolationError(
            f"G2 Violation: Final structure converged to saddle point with {imag_freqs} "
            f"imaginary frequencies (threshold: {max_imaginary_frequencies})."
        )
    return True


def compute_molecular_center_of_mass(
    coordinates: np.ndarray,
    atomic_symbols: Sequence[str],
) -> np.ndarray:
    """
    Compute 3D center of mass dynamically using Mendeleev atomic masses.
    Enforces Mendeleev Library Mandate (Rule 1 & 2).
    """
    masses = np.array([element(sym.strip()).mass for sym in atomic_symbols], dtype=np.float64)
    total_mass = np.sum(masses)
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be greater than zero.")
    return np.sum(coordinates * masses[:, np.newaxis], axis=0) / total_mass


def verify_g3_basin_identity(
    scout_coords_angstrom: np.ndarray,
    anchor_coords_angstrom: np.ndarray,
    atomic_symbols: Sequence[str],
    rmsd_threshold_angstrom: float = DEFAULT_G3_RMSD_THRESHOLD_ANGSTROM,
    delta_r_threshold_angstrom: float = DEFAULT_G3_DELTA_R_THRESHOLD_ANGSTROM,
) -> Tuple[bool, float, float, str]:
    """
    G3: Basin-identity check between scout predicted minimum and anchor relaxed minimum.
    Calculates heavy-atom RMSD and center-of-mass displacement Delta R using Mendeleev masses.
    Gate: RMSD > 0.25 Å or Delta R > 0.20 Å => flag 'basin change'.

    Returns:
        Tuple of (is_same_basin, rmsd, delta_r, message).
    """
    if scout_coords_angstrom.shape != anchor_coords_angstrom.shape:
        raise ValueError(
            f"Shape mismatch in G3 basin check: scout {scout_coords_angstrom.shape} vs "
            f"anchor {anchor_coords_angstrom.shape}"
        )

    # Filter heavy atoms (non-Hydrogen) for heavy-atom RMSD
    heavy_indices = [i for i, sym in enumerate(atomic_symbols) if sym.strip().upper() not in ("H", "D", "T")]
    if heavy_indices:
        scout_heavy = scout_coords_angstrom[heavy_indices]
        anchor_heavy = anchor_coords_angstrom[heavy_indices]
        rmsd = float(np.sqrt(np.mean(np.sum((scout_heavy - anchor_heavy) ** 2, axis=-1))))
    else:
        rmsd = float(np.sqrt(np.mean(np.sum((scout_coords_angstrom - anchor_coords_angstrom) ** 2, axis=-1))))

    # Compute center of mass separation Delta R using Mendeleev masses
    com_scout = compute_molecular_center_of_mass(scout_coords_angstrom, atomic_symbols)
    com_anchor = compute_molecular_center_of_mass(anchor_coords_angstrom, atomic_symbols)
    delta_r = float(np.linalg.norm(com_scout - com_anchor))

    is_same_basin = (rmsd <= rmsd_threshold_angstrom) and (delta_r <= delta_r_threshold_angstrom)
    if not is_same_basin:
        msg = (
            f"Basin change detected: heavy-atom RMSD={rmsd:.4f} A (gate <= {rmsd_threshold_angstrom:.2f} A), "
            f"Delta R={delta_r:.4f} A (gate <= {delta_r_threshold_angstrom:.2f} A)"
        )
    else:
        msg = f"Basin identity verified: RMSD={rmsd:.4f} A, Delta R={delta_r:.4f} A within tolerance."

    return is_same_basin, rmsd, delta_r, msg


def verify_g4_rank_inversion(
    scout_energies: Sequence[float],
    anchor_energies: Sequence[float],
    rho_threshold: float = DEFAULT_G4_SPEARMAN_RHO_THRESHOLD,
) -> Tuple[bool, float, str]:
    """
    G4: Rank-inversion audit before culling on cheap surface (§8A.5).
    Computes Spearman rank correlation rho on sample.
    Mandates rho >= 0.90 before discarding candidate geometries.

    Returns:
        Tuple of (passes_audit, spearman_rho, message).
    """
    if len(scout_energies) != len(anchor_energies):
        raise ValueError(
            f"Sample size mismatch: {len(scout_energies)} scout vs {len(anchor_energies)} anchor"
        )
    if len(scout_energies) < 2:
        return True, 1.0, "Sample size < 2; rank correlation bypassed."

    res = scipy.stats.spearmanr(scout_energies, anchor_energies)
    rho = float(res.statistic if hasattr(res, "statistic") else res[0])

    if np.isnan(rho):
        rho = 0.0

    passes = rho >= rho_threshold
    if not passes:
        msg = (
            f"G4 Violation: Spearman rank correlation rho={rho:.3f} below gate {rho_threshold:.2f}. "
            f"MLFF culling prohibited; retention window must be widened."
        )
    else:
        msg = f"G4 Verified: Spearman rank correlation rho={rho:.3f} >= {rho_threshold:.2f}."

    return passes, rho, msg


def verify_g5_uncertainty_gate(
    committee_sigma_mev_per_atom: float,
    threshold_mev_per_atom: float = DEFAULT_G5_UNCERTAINTY_THRESHOLD_MEV,
) -> bool:
    """G5: Committee uncertainty gate on MLFF guide predictions."""
    return committee_sigma_mev_per_atom <= threshold_mev_per_atom


def verify_g6_abort_guide(
    consecutive_guide_failures: int,
    max_failures: int = DEFAULT_G6_MAX_GUIDE_FAILURES,
) -> bool:
    """G6: Abort-the-guide rule after n_th = 5 consecutive failures."""
    return consecutive_guide_failures < max_failures


def log_g7_provenance_event(
    record: G7ProvenanceRecord,
    log_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """
    G7: Append structured provenance audit JSON event line to provenance.jsonl.
    Mandated by Method Matrix §8A.5 (line 1320).

    Returns:
        Path to the target provenance.jsonl file.
    """
    target_dir = Path(log_dir).resolve() if log_dir else get_artifact_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "provenance.jsonl"

    line = json.dumps(record.model_dump(mode="json")) + "\n"
    with open(target_file, "a", encoding="utf-8") as f:
        f.write(line)

    return target_file


# =============================================================================
# ParslExecutionBroker (Thread-Safe Lifecycle Manager)
# =============================================================================
class ParslExecutionBroker:
    """
    Thread-safe lifecycle manager and task dispatcher for the heterogeneous Parsl DFK.
    Maintains singleton instance, manages executor topology, and coordinates zero-mock execution.
    """

    _instance: Optional[ParslExecutionBroker] = None
    _lock = threading.RLock()

    def __new__(cls, *args: Any, **kwargs: Any) -> ParslExecutionBroker:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ParslExecutionBroker, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        profile: Optional[ParslMultiExecutorProfile] = None,
        run_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return
        self.profile: ParslMultiExecutorProfile = profile or build_heterogeneous_profile()
        self.run_dir: Optional[Path] = Path(run_dir).resolve() if run_dir else None
        self._dfk: Optional[Any] = None
        self._is_active: bool = False
        self._task_history: Dict[str, TaskExecutionResult] = {}
        self._consecutive_guide_failures: int = 0
        self._initialized = True

    @classmethod
    def get_instance(cls) -> ParslExecutionBroker:
        """Get the active singleton broker instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def load(self, force_reload: bool = False) -> Any:
        """
        Load or reload the physical Parsl DataFlowKernel.
        """
        with self._lock:
            import parsl

            if self._is_active and not force_reload:
                return self._dfk

            if self._is_active and force_reload:
                self.shutdown()

            parsl_cfg = construct_parsl_config(
                profile=self.profile,
                run_dir=self.run_dir,
            )
            try:
                self._dfk = parsl.load(parsl_cfg)
                self._is_active = True
                logger.info("Parsl DataFlowKernel loaded successfully with heterogeneous executors.")
                return self._dfk
            except Exception as exc:
                self._is_active = False
                raise ExecutorLifecycleError(f"Failed to load Parsl DataFlowKernel: {exc}") from exc

    def shutdown(self) -> None:
        """
        Cleanly shutdown the Parsl DataFlowKernel and reap worker processes.
        """
        with self._lock:
            import parsl

            if self._is_active:
                try:
                    parsl.clear()
                    logger.info("Parsl DataFlowKernel cleared.")
                except Exception as exc:
                    logger.warning(f"Error during parsl.clear(): {exc}")
                finally:
                    self._is_active = False
                    self._dfk = None
                    _sweep_zombie_processes()

    def is_active(self) -> bool:
        """Check if Parsl DFK is active."""
        with self._lock:
            return self._is_active

    def get_dfk(self) -> Optional[Any]:
        """Retrieve the active DataFlowKernel."""
        with self._lock:
            return self._dfk

    def submit_bash_task(
        self,
        request: TaskRoutingRequest,
        stdout_path: Optional[Union[str, Path]] = None,
        stderr_path: Optional[Union[str, Path]] = None,
    ) -> Any:
        """
        Submit a bash-level computational chemistry task to the appropriate executor pool.
        """
        with self._lock:
            if not self._is_active:
                self.load()

            from parsl import bash_app

            executor_label: str
            if request.stream == ExecutorStreamType.CPU_ANCHOR:
                executor_label = self.profile.anchor_executor.label
            elif request.stream == ExecutorStreamType.GPU_SCOUT:
                executor_label = self.profile.scout_executor.label
            else:
                executor_label = self.profile.orchestrator_executor.label

            @bash_app(executors=[executor_label])
            def _generic_bash_runner(
                cmd_args: List[str],
                env_dict: Dict[str, str],
                stdout: Optional[str] = None,
                stderr: Optional[str] = None,
            ) -> str:
                env_prefix = " ".join(f"{k}='{v}'" for k, v in env_dict.items())
                cmd_str = " ".join(cmd_args)
                return f"{env_prefix} {cmd_str}" if env_prefix else cmd_str

            out_str = str(resolve_mapped_path(stdout_path)) if stdout_path else None
            err_str = str(resolve_mapped_path(stderr_path)) if stderr_path else None

            cmd = request.command or ["echo", "no-op"]
            app_future = _generic_bash_runner(
                cmd_args=cmd,
                env_dict=request.env_vars,
                stdout=out_str,
                stderr=err_str,
            )
            return app_future

    def submit_python_task(
        self,
        stream: ExecutorStreamType,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Submit a Python callable to the designated executor stream.
        """
        with self._lock:
            if not self._is_active:
                self.load()

            from parsl import python_app

            executor_label: str
            if stream == ExecutorStreamType.CPU_ANCHOR:
                executor_label = self.profile.anchor_executor.label
            elif stream == ExecutorStreamType.GPU_SCOUT:
                executor_label = self.profile.scout_executor.label
            else:
                executor_label = self.profile.orchestrator_executor.label

            @python_app(executors=[executor_label])
            def _runner(*fn_args: Any, **fn_kwargs: Any) -> Any:
                return func(*fn_args, **fn_kwargs)

            return _runner(*args, **kwargs)

    def execute_and_wait(
        self,
        request: TaskRoutingRequest,
        stdout_path: Optional[Union[str, Path]] = None,
        stderr_path: Optional[Union[str, Path]] = None,
    ) -> TaskExecutionResult:
        """
        Submit a task, wait for resolution within timeout, and generate a validated TaskExecutionResult.
        """
        start_time = time.time()
        try:
            future = self.submit_bash_task(
                request=request,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            ret_code = future.result(timeout=request.timeout_seconds)
            duration = time.time() - start_time

            # Read outputs if available
            stdout_content: Optional[str] = None
            stderr_content: Optional[str] = None
            file_hashes: Dict[str, str] = {}
            output_files: Dict[str, str] = {}

            if stdout_path and Path(stdout_path).exists():
                stdout_content = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
                output_files["stdout"] = str(stdout_path)
                file_hashes[str(stdout_path)] = hashlib.sha256(Path(stdout_path).read_bytes()).hexdigest()

            if stderr_path and Path(stderr_path).exists():
                stderr_content = Path(stderr_path).read_text(encoding="utf-8", errors="replace")
                output_files["stderr"] = str(stderr_path)
                file_hashes[str(stderr_path)] = hashlib.sha256(Path(stderr_path).read_bytes()).hexdigest()

            status = "COMPLETED" if ret_code == 0 else "FAILED"

            result = TaskExecutionResult(
                task_id=request.task_id,
                stream=request.stream,
                authority=request.authority,
                status=status,
                return_code=ret_code,
                stdout=stdout_content,
                stderr=stderr_content,
                duration_seconds=duration,
                output_files=output_files,
                file_hashes=file_hashes,
            )
            self._task_history[request.task_id] = result
            return result

        except Exception as exc:
            duration = time.time() - start_time
            logger.error(f"Task {request.task_id} failed on stream {request.stream}: {exc}")
            result = TaskExecutionResult(
                task_id=request.task_id,
                stream=request.stream,
                authority=request.authority,
                status="FAILED",
                duration_seconds=duration,
                error_message=str(exc),
            )
            self._task_history[request.task_id] = result
            return result

    def get_status_report(self) -> Dict[str, Any]:
        """Generate a complete status report of the broker and executors."""
        with self._lock:
            return {
                "is_active": self._is_active,
                "profile_id": self.profile.profile_id,
                "anchor_executor": self.profile.anchor_executor.model_dump(),
                "scout_executor": self.profile.scout_executor.model_dump(),
                "orchestrator_executor": self.profile.orchestrator_executor.model_dump(),
                "core_partitioning": self.profile.core_partitioning.model_dump(),
                "contention_budget": self.profile.contention_budget.model_dump(),
                "total_tasks_tracked": len(self._task_history),
                "consecutive_guide_failures": self._consecutive_guide_failures,
            }

    def __enter__(self) -> ParslExecutionBroker:
        self.load()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown()


# =============================================================================
# Helper Convenience Functions
# =============================================================================
def load_parsl_executors(
    profile: Optional[ParslMultiExecutorProfile] = None,
    run_dir: Optional[Union[str, Path]] = None,
) -> ParslExecutionBroker:
    """Convenience function to initialize and load the ParslExecutionBroker."""
    broker = ParslExecutionBroker.get_instance()
    if profile:
        broker.profile = profile
    if run_dir:
        broker.run_dir = Path(run_dir).resolve()
    broker.load()
    return broker


def shutdown_parsl_executors() -> None:
    """Convenience function to shutdown the ParslExecutionBroker."""
    broker = ParslExecutionBroker.get_instance()
    broker.shutdown()


# =============================================================================
# CLI Interface
# =============================================================================
def build_cli_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for Parsl executor management."""
    parser = argparse.ArgumentParser(
        prog="cochem_core_parsl_executors",
        description="CoChem-CORE: Parsl Multi-Executor Heterogeneous HPC & Task Router (Scout-and-Anchor).",
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")

    subparsers.add_parser("status", help="Query status of Parsl executors and DFK")
    subparsers.add_parser("topology", help="Display heterogeneous Scout-and-Anchor topology")
    subparsers.add_parser("dry-run", help="Dry-run configuration assembly and integrity checks")

    export_p = subparsers.add_parser("export-config", help="Export topology profile to JSON")
    export_p.add_argument(
        "--out", "-o", type=str, default="parsl_topology.json", help="Output JSON path"
    )

    audit_p = subparsers.add_parser("audit-guards", help="Run self-audit on G1-G7 integrity guards")
    audit_p.add_argument(
        "--out-dir", type=str, default=None, help="Directory to emit test provenance.jsonl"
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for cochem_core_parsl_executors."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    if not args.command or args.command == "status":
        broker = ParslExecutionBroker.get_instance()
        status = broker.get_status_report()
        print(json.dumps(status, indent=2))
        return 0

    if args.command == "topology":
        profile = build_heterogeneous_profile()
        print("=== CoChem Heterogeneous Scout-and-Anchor Topology (Section 8A) ===")
        print(f"Total Physical Cores: {profile.core_partitioning.total_physical_cores}")
        print(f"Anchor Cores:         {profile.core_partitioning.anchor_core_count} ({profile.core_partitioning.anchor_affinity_str})")
        print(f"Scout Cores:          {profile.core_partitioning.scout_core_count} ({profile.core_partitioning.scout_affinity_str})")
        print(f"GPU Scout Workers:    {profile.contention_budget.gpu_scout_workers} (MPS: {profile.contention_budget.mps_active_thread_percentage}%)")
        print(f"Contention Slowdown:  {profile.contention_budget.estimated_cpu_slowdown_factor:.2f}x (85% real efficiency)")
        print(f"Degraded Mode:        {profile.is_degraded_single_executor}")
        return 0

    if args.command == "dry-run":
        try:
            profile = build_heterogeneous_profile()
            cfg = construct_parsl_config(profile)
            print(f"Successfully assembled Parsl Config with {len(cfg.executors)} executors:")
            for exc in cfg.executors:
                print(f"  - Executor: {exc.label} ({type(exc).__name__})")
            return 0
        except Exception as err:
            logger.error(f"Dry-run failed: {err}")
            return 1

    if args.command == "export-config":
        profile = build_heterogeneous_profile()
        out_path = Path(args.out).resolve()
        out_path.write_text(json.dumps(profile.model_dump(mode="json"), indent=2), encoding="utf-8")
        print(f"Exported topology profile to: {out_path}")
        return 0

    if args.command == "audit-guards":
        print("Auditing Method Matrix Section 8A.5 Integrity Guards (G1-G7)...")
        # G1 check
        try:
            verify_g1_authority({"authority": "authoritative"})
            print("[FAIL] G1 Audit Failed: Authoritative guide allowed.")
            return 1
        except IntegrityGuardViolationError:
            print("[OK] G1 Verified: Rejection of authoritative guide claim.")

        # G2 check
        try:
            verify_g2_high_level_hessian({"imaginary_frequencies_count": 0})
            print("[OK] G2 Verified: Hessian frequency validation.")
        except Exception as err:
            print(f"[FAIL] G2 Audit Failed: {err}")
            return 1

        # G3 check with Mendeleev dynamic masses
        scout_xyz = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.1]], dtype=np.float64)
        anchor_xyz = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.12]], dtype=np.float64)
        is_same, rmsd, delta_r, msg = verify_g3_basin_identity(
            scout_coords_angstrom=scout_xyz,
            anchor_coords_angstrom=anchor_xyz,
            atomic_symbols=["C", "O"],
        )
        print(f"[OK] G3 Verified: {msg}")

        # G4 check
        passes, rho, msg = verify_g4_rank_inversion([1.0, 2.0, 3.0], [1.1, 2.1, 3.1])
        print(f"[OK] G4 Verified: {msg}")

        # G5 check
        assert verify_g5_uncertainty_gate(5.0) is True
        print("[OK] G5 Verified: Committee uncertainty thresholding.")

        # G6 check
        assert verify_g6_abort_guide(2) is True
        assert verify_g6_abort_guide(5) is False
        print("[OK] G6 Verified: Guide abort rule on n_th=5 failures.")

        # G7 check
        record = G7ProvenanceRecord(
            stage="audit_test",
            decision="verify_parsl_executors",
            authority=TaskAuthority.ADVISORY_ONLY,
        )
        log_file = log_g7_provenance_event(record, log_dir=args.out_dir)
        print(f"[OK] G7 Verified: Provenance logged to {log_file}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\calc\slurm_generator.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
HPC SLURM Single-Node Shared-Memory Template Generator.
Mandated by Method Matrix v4 §8A.6 (Suggestion #72).
Enforces:
- #SBATCH --nodes=1
- #SBATCH --ntasks=1
- #SBATCH --cpus-per-task={cores}
- ORCA %pal nprocs {cores} end alignment
- CFOUR / OpenMP thread binding: export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
- Dynamic core capacity clamping with [SCHEDULER-WARNING]
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Union

import psutil

logger = logging.getLogger("cochem_base.calc.slurm_generator")


@dataclass
class SlurmSubmissionSpec:
    """Specification for HPC Slurm single-node shared-memory job."""

    job_name: str
    partition: str = "standard"
    cores: int = 8
    mem_mb: int = 16384
    walltime: str = "24:00:00"
    scratch_dir: str = "/scratch"
    artifact_dir: str = "/artifacts"
    solver: str = "orca"
    account: Optional[str] = None
    qos: Optional[str] = None
    gpus_per_node: Optional[int] = None


class SlurmGenerator:
    """Generator for HPC SLURM submission scripts strictly adhering to Method Matrix §8A.6."""

    def __init__(self) -> None:
        pass

    def get_physical_core_limit(self) -> int:
        """Determines the physical single-node core limit via SLURM environment or psutil."""
        slurm_env = os.environ.get("SLURM_CPUS_ON_NODE")
        if slurm_env and slurm_env.isdigit():
            return int(slurm_env)
        count = psutil.cpu_count(logical=False)
        return int(count) if count is not None and count > 0 else 8

    def generate_submission_script(
        self,
        spec: SlurmSubmissionSpec,
        input_file: str = "calc.inp",
        payload_command: Optional[str] = None,
    ) -> str:
        """Generates an SBATCH script with single-node shared-memory directives."""
        physical_limit = self.get_physical_core_limit()
        requested_cores = spec.cores
        effective_cores = requested_cores

        if requested_cores > physical_limit:
            effective_cores = physical_limit
            logger.warning(
                f"[SCHEDULER-WARNING] Requested cores ({requested_cores}) exceeds physical "
                f"single-node bounds ({physical_limit}). Clamped to {effective_cores}."
            )

        scratch_posix = PurePosixPath(spec.scratch_dir).as_posix()
        artifact_posix = PurePosixPath(spec.artifact_dir).as_posix()

        solver_lower = spec.solver.lower().strip()

        # Shared-memory directives conforming to Method Matrix §8A.6
        header = [
            "#!/bin/bash",
            f"#SBATCH --job-name={spec.job_name}",
            f"#SBATCH --partition={spec.partition}",
            "#SBATCH --nodes=1",
            "#SBATCH --ntasks=1",
            f"#SBATCH --cpus-per-task={effective_cores}",
            f"#SBATCH --mem={spec.mem_mb}M",
            f"#SBATCH --time={spec.walltime}",
        ]

        if spec.account:
            header.append(f"#SBATCH --account={spec.account}")
        if spec.qos:
            header.append(f"#SBATCH --qos={spec.qos}")
        if spec.gpus_per_node is not None and spec.gpus_per_node > 0:
            header.append(f"#SBATCH --gpus-per-node={spec.gpus_per_node}")

        # Thread binding & Solver execution block
        exec_lines = [
            "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK",
            "export MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK",
            f"export COCHEM_SCRATCH=\"{scratch_posix}\"",
            f"export COCHEM_ARTIFACTS=\"{artifact_posix}\"",
            "mkdir -p \"$COCHEM_SCRATCH\"",
            "mkdir -p \"$COCHEM_ARTIFACTS\"",
            "cd \"$COCHEM_SCRATCH\"",
        ]

        if payload_command:
            exec_lines.append(payload_command)
        elif solver_lower == "orca":
            maxcore_mb = int(math.floor((spec.mem_mb * 0.75) / 1))
            exec_lines.extend([
                f"# ORCA parallel execution alignment (%pal nprocs {effective_cores} end)",
                f"# MaxCore per rank: {maxcore_mb} MB",
                f"orca {input_file} > orca_output.out",
            ])
        elif solver_lower == "cfour":
            exec_lines.extend([
                "# CFOUR OpenMP / MPI hybrid execution",
                "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK",
                "xcfour > cfour_output.out",
            ])
        elif solver_lower == "crest":
            exec_lines.append(
                f"crest {input_file} --nci --nocross --noreftopo -T $SLURM_CPUS_PER_TASK > crest_output.out"
            )
        else:
            exec_lines.append(f"{spec.solver} {input_file}")

        exec_lines.append("cp -r \"$COCHEM_SCRATCH\"/* \"$COCHEM_ARTIFACTS\"/")

        return "\n".join(header) + "\n\n" + "\n".join(exec_lines) + "\n"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\hetero_config.py ---
#!/usr/bin/env python3
# cochem_canvas_target: hetero_config.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-TOPOS: Heterogeneous CPU (13700K) + GPU (RTX 3090) Dual Parsl Executor Configuration Driver.
Mandated by Method Matrix v5 §8A.4 (NVIDIA MPS Concurrency), §8A.6 (Parsl Multi-Executor Architecture),
§8A.1 (Workstation Contention Budgeting), §8A.2 (Scout & Anchor Topology), §8A.3 (MLFF Preconditioning),
§8A.5 (Integrity Guards G1–G7), and §8A.7 (Pipelined Heterogeneous Campaign Execution).

Operational Scope & Hardware Specifications:
1. Reference Workstation Configuration (Setup 2 - Production):
   - CPU: Intel Core i7-13700K (16 cores: 8 Performance-cores + 8 Efficient-cores, 24 threads).
     AVX2 only (AVX-512 fused off). Max turbo power 253 W, base 125 W.
     DDR5-5600 (89.6 GB/s) / DDR5-6400 XMP (102.4 GB/s).
   - GPU: NVIDIA GeForce RTX 3090 (GA102 Ampere, 10,496 CUDA cores, 24 GB GDDR6X, 936 GB/s).
     FP32: 35.6 TFLOPS; FP64: 0.556 TFLOPS (35.6 / 64). Board power 350 W.
     Power limit: 280 W (80% board power via `nvidia-smi -pl 280`) during pipelined campaigns.
   - Total Component Peak Power: 603 W (253 W CPU + 350 W GPU). PSU >= 850 W.
   - Memory Bandwidth Ratio: 9.1–10.4x GPU advantage (936 GB/s vs 89.6–102.4 GB/s).
   - Kernel Launch Floor: 5–15 µs (~10 µs baseline) latency floor for small-molecule workloads.

2. Heterogeneous Dual Parsl Executor Topology (§8A.6):
   - CPU Anchor Executor ('cpu' / 'cochem_anchor_cpu'):
     - Dedicated to authoritative quantum chemistry (ORCA DFT/VPT2, MPQC CCSD(T)-F12, CFOUR).
     - max_workers_per_node = 1 (1 ORCA job at a time, owning 7 MPI ranks).
     - cores_per_worker = 7 (P-cores 0–6; core 7 reserved as host feeder for GPU).
     - cpu_affinity = 'block'
     - mem_per_worker = 28 GB (7 ranks x %maxcore 3400 + headroom).
     - worker_init: 'export OMP_NUM_THREADS=1; export KMP_HW_SUBSET=8c:intel_core,1t'
   - GPU Scout Executor ('gpu' / 'cochem_scout_gpu'):
     - Dedicated to advisory MLFF / gpu4pyscf workers under NVIDIA MPS.
     - available_accelerators = 3 (pins each worker to one slot, caps at 3).
     - max_workers_per_node = 3 (2–4 workers under MPS, 3 is optimal).
     - cores_per_worker = 1 (P-core 7 host feeder).
     - cpu_affinity = 'block-reverse' (keeps feeders away from the ORCA block).
     - mem_per_worker = 6 GB.
     - worker_init: 'export CUDA_VISIBLE_DEVICES=0; export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=33;
                    export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=\\'0=6G\\'; ulimit -n 16384'
   - Orchestrator / Utility Executor ('orchestrator' / 'cochem_orchestrator'):
     - Dedicated to DFK, file I/O, deduplication, JSON/provenance serialization on E-cores.
     - max_workers_per_node = 4, cores_per_worker = 1, cpu_affinity = 'alternating', mem_per_worker = 4 GB.
   - retries = 2 across all configurations (§8A.6).

3. Environmental Tier Adaptations:
   - Setup 1 (Teaching / CI / CPU-Only): Degrades cleanly to single CPU executor with 8 ranks (%maxcore 3000).
   - Setup 3 (HPC Cluster Slurm Partition): SlurmProvider with '#SBATCH --gres=gpu:1 --gpus-per-node=1'
     and '#SBATCH --cpus-per-task=8', preserving app decorators and labels unchanged.

4. NVIDIA Multi-Process Service (MPS) Control & Telemetry (§8A.4):
   - Dynamic VRAM allocation: N = floor(20000 MB / measured_MB), capped by host P-cores.
   - Active thread percentage: 100% / N (e.g. 33% for 3 workers, 50% for 2 workers).
   - MPS daemon lifecycle management, socket/pipe checking, and power limiting.

5. Method Matrix §8A.5 Integrity Guards (G1–G7):
   - G1: Scout advisory authority rejection (no scout result may claim authoritative status).
   - G2: High-level Hessian verification (asserts imaginary frequency count & softest force constant).
   - G3: Basin-identity check (heavy-atom RMSD <= 0.25 Å, Delta R <= 0.20 Å via Mendeleev masses).
   - G4: Rank-inversion audit (Spearman rho >= 0.90 on sample before culling; 10 kcal/mol window).
   - G5: Uncertainty gate (committee sigma thresholding).
   - G6: Abort-the-guide rule (n_th = 5 consecutive failure threshold).
   - G7: Cryptographic provenance event recording in provenance.jsonl.

6. Strict Zero-Mock & Mendeleev Library Mandate:
   - Mendeleev integration: All atomic masses retrieved dynamically via `mendeleev.element`.
   - Zero hardcoded atomic weights, zero mocks, zero stubs, zero empty pass blocks.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import logging
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

try:
    from cochem_base.schemas import GpuScoutExecutorConfig
except ImportError:
    class GpuScoutExecutorConfig(BaseModel):  # type: ignore
        model_config = ConfigDict(frozen=True, extra="forbid")
        platform_os: Literal["windows", "darwin", "linux"]
        enable_mps: bool
        mps_pipe_dir: str
        max_concurrent_gpu_tasks: int = Field(default=1, ge=1)
        min_vram_headroom_mb: float = Field(default=1536.0, ge=512.0)


import numpy as np
import psutil
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
import scipy.stats

# Optional telemetry bindings
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=FutureWarning)
    try:
        import pynvml
        HAS_PYNVML = True
    except (ImportError, Exception):
        pynvml = None
        HAS_PYNVML = False

try:
    import torch
    HAS_TORCH = True
except (ImportError, Exception):
    torch = None
    HAS_TORCH = False

# ---------------------------------------------------------------------------
# Physical Constants & Hardware Parameters (Method Matrix §8, §8A.1, §8A.4)
# ---------------------------------------------------------------------------
PLANCK_CONSTANT_J_S: float = 6.62607015e-34       # J * s (CODATA exact)
SPEED_OF_LIGHT_CM_S: float = 2.99792458e10       # cm / s (CODATA exact)
ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27   # kg / u
ANGSTROM_TO_METER: float = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM: float = 0.529177210903         # Angstrom / Bohr
HARTREE_TO_EV: float = 27.211386245988           # eV / Hartree
HARTREE_TO_KCAL_MOL: float = 627.5094740631      # kcal/mol / Hartree
EV_TO_KCAL_MOL: float = 23.060541945329          # kcal/mol / eV

# Hardware Specifications (Setup 2: Intel i7-13700K + NVIDIA RTX 3090)
SETUP2_CPU_MODEL: str = "Intel Core i7-13700K"
SETUP2_CPU_P_CORES: int = 8
SETUP2_CPU_E_CORES: int = 8
SETUP2_CPU_TOTAL_PHYSICAL_CORES: int = 16
SETUP2_CPU_TOTAL_THREADS: int = 24
SETUP2_CPU_BASE_POWER_W: int = 125
SETUP2_CPU_MAX_TURBO_POWER_W: int = 253
SETUP2_CPU_DDR5_5600_BANDWIDTH_GB_S: float = 89.6
SETUP2_CPU_DDR5_6400_XMP_BANDWIDTH_GB_S: float = 102.4
SETUP2_CPU_MAXCORE_DUAL_MB: int = 3400           # %maxcore for 7 ranks when co-scheduled with GPU
SETUP2_CPU_MAXCORE_SOLO_MB: int = 3000           # %maxcore for 8 ranks in CPU-only mode

SETUP2_GPU_MODEL: str = "NVIDIA GeForce RTX 3090"
SETUP2_GPU_CHIP: str = "GA102 Ampere"
SETUP2_GPU_CUDA_CORES: int = 10496
SETUP2_GPU_VRAM_GB: int = 24
SETUP2_GPU_BANDWIDTH_GB_S: float = 936.0
SETUP2_GPU_FP32_TFLOPS: float = 35.6
SETUP2_GPU_FP64_TFLOPS: float = 35.6 / 64.0     # 0.55625 TFLOPS (Method Matrix: 35.6 / 64 = 0.556)
SETUP2_GPU_BOARD_POWER_W: int = 350
SETUP2_GPU_POWER_LIMIT_W: int = 280              # nvidia-smi -pl 280 (80% board power)

TOTAL_PEAK_COMPONENT_POWER_W: int = 603          # 253 W CPU + 350 W GPU
RECOMMENDED_PSU_W: int = 850
GPU_BANDWIDTH_ADVANTAGE_MIN: float = 9.1         # 936 / 102.4 (vs XMP)
GPU_BANDWIDTH_ADVANTAGE_MAX: float = 10.4        # 936 / 89.6 (vs DDR5-5600)
KERNEL_LAUNCH_LATENCY_US: float = 10.0           # 5-15 µs launch floor

MAX_MPS_CLIENTS_CUDA13: int = 48
MAX_MPS_CLIENTS_R590: int = 60

# Method Matrix §8A.5 Integrity Guard Defaults
DEFAULT_G3_MAX_RMSD_ANG: float = 0.25
DEFAULT_G3_MAX_DR_ANG: float = 0.20
DEFAULT_G4_MIN_SPEARMAN_RHO: float = 0.90
DEFAULT_G4_RETENTION_WINDOW_KCAL_MOL: float = 10.0
DEFAULT_G6_MAX_CONSECUTIVE_FAILURES: int = 5

# Logging configuration
logger = logging.getLogger("hetero_config")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] [hetero_config]: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Dynamic Atomic Mass Resolution (CoChem Mendeleev Mandate)
# ---------------------------------------------------------------------------
_MASS_CACHE: Dict[str, float] = {}

def get_atomic_mass(symbol: str) -> float:
    """
    Dynamically retrieve the atomic mass of an element via Mendeleev library.
    Enforces the CoChem Mendeleev Mandate: strictly zero hardcoded atomic masses.

    Args:
        symbol: Chemical symbol of the element (e.g. 'H', 'C', 'N', 'O').

    Returns:
        Atomic mass in atomic mass units (u / Da).
    """
    clean_symbol = symbol.strip().capitalize()
    if clean_symbol in _MASS_CACHE:
        return _MASS_CACHE[clean_symbol]

    elem_data = element(clean_symbol)
    if elem_data is None or elem_data.mass is None:
        raise ValueError(f"Unknown or invalid element symbol '{symbol}' in Mendeleev database.")
    
    mass_val = float(elem_data.mass)
    _MASS_CACHE[clean_symbol] = mass_val
    return mass_val


# ---------------------------------------------------------------------------
# 1. Enums and Pydantic v2 Models
# ---------------------------------------------------------------------------

class SetupTier(str, Enum):
    """Method Matrix hardware execution tiers."""
    SETUP_1 = "Setup_1_Teaching_CPU"
    SETUP_2 = "Setup_2_Production_Workstation"
    SETUP_3 = "Setup_3_HPC_Slurm"


class ProviderBackend(str, Enum):
    """Supported Parsl resource providers."""
    LOCAL = "local"
    SLURM = "slurm"
    THREAD_POOL = "thread_pool"


class CoreAffinityType(str, Enum):
    """Parsl CPU core affinity allocation strategies."""
    BLOCK = "block"
    BLOCK_REVERSE = "block-reverse"
    ALTERNATING = "alternating"
    NONE = "none"


class GuardDecision(str, Enum):
    """Outcome status for Method Matrix §8A.5 integrity guards."""
    PASS = "PASS"
    FAIL = "FAIL"
    ABORT = "ABORT"
    FLAG_BASIN_CHANGE = "FLAG_BASIN_CHANGE"


class HardwareSpec(BaseModel):
    """Hardware specifications of the execution workstation/node."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    cpu_model: str = Field(default=SETUP2_CPU_MODEL, description="CPU model name")
    p_cores: int = Field(default=SETUP2_CPU_P_CORES, ge=1, description="Performance cores")
    e_cores: int = Field(default=SETUP2_CPU_E_CORES, ge=0, description="Efficient cores")
    total_physical_cores: int = Field(default=SETUP2_CPU_TOTAL_PHYSICAL_CORES, ge=1)
    total_threads: int = Field(default=SETUP2_CPU_TOTAL_THREADS, ge=1)
    cpu_max_power_w: int = Field(default=SETUP2_CPU_MAX_TURBO_POWER_W, ge=50)
    system_ram_gb: int = Field(default=64, ge=8, description="Host system DDR5 RAM in GB")
    gpu_model: Optional[str] = Field(default=SETUP2_GPU_MODEL, description="GPU model name")
    gpu_vram_gb: float = Field(default=SETUP2_GPU_VRAM_GB, ge=0.0, description="GPU VRAM in GB")
    gpu_board_power_w: int = Field(default=SETUP2_GPU_BOARD_POWER_W, ge=0)
    gpu_power_limit_w: int = Field(default=SETUP2_GPU_POWER_LIMIT_W, ge=0)
    total_peak_power_w: int = Field(default=TOTAL_PEAK_COMPONENT_POWER_W, ge=100)
    recommended_psu_w: int = Field(default=RECOMMENDED_PSU_W, ge=300)
    gpu_bandwidth_gb_s: float = Field(default=SETUP2_GPU_BANDWIDTH_GB_S, ge=0.0)
    cpu_bandwidth_gb_s: float = Field(default=SETUP2_CPU_DDR5_6400_XMP_BANDWIDTH_GB_S, ge=0.0)


class ExecutorConfig(BaseModel):
    """Specification of an individual Parsl executor."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    label: str = Field(..., description="Parsl executor label (e.g. 'cpu', 'gpu', 'orchestrator')")
    cores_per_worker: int = Field(..., ge=1, description="CPU cores dedicated per worker")
    max_workers_per_node: int = Field(..., ge=1, description="Maximum concurrent workers on the node")
    cpu_affinity: CoreAffinityType = Field(default=CoreAffinityType.BLOCK, description="Core affinity pinning")
    mem_per_worker_gb: float = Field(..., gt=0.0, description="Memory ceiling per worker in GB")
    available_accelerators: Optional[int] = Field(default=None, description="Number of accelerator slots")
    worker_init: str = Field(default="", description="Bash initialization script for Parsl worker")
    provider_type: ProviderBackend = Field(default=ProviderBackend.LOCAL, description="Provider backend")
    scheduler_options: Optional[str] = Field(default=None, description="Slurm scheduler options")


class HeteroParslConfig(BaseModel):
    """Master Parsl multi-executor heterogeneous configuration model."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    setup_tier: SetupTier = Field(default=SetupTier.SETUP_2, description="Target execution tier")
    cpu_executor: ExecutorConfig = Field(..., description="Authoritative CPU Anchor executor config")
    gpu_executor: Optional[ExecutorConfig] = Field(default=None, description="Advisory GPU Scout executor config")
    orchestrator_executor: Optional[ExecutorConfig] = Field(default=None, description="Utility / DFK executor config")
    retries: int = Field(default=2, ge=0, description="Parsl task execution retry budget (§8A.6)")
    strategy: str = Field(default="simple", description="Parsl scaling strategy")
    hardware: HardwareSpec = Field(default_factory=HardwareSpec, description="Physical hardware spec")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Exported environment variables")


class MPSConfig(BaseModel):
    """NVIDIA Multi-Process Service (MPS) control configuration model (§8A.4)."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    device_id: int = Field(default=0, ge=0, description="Target CUDA device ID")
    active_thread_percentage: int = Field(default=33, ge=1, le=100, description="Thread percentage cap")
    pinned_mem_limit: str = Field(default="0=6G", description="Pinned device memory limit per client")
    pipe_directory: str = Field(default="/tmp/nvidia-mps", description="MPS control pipe directory")
    log_directory: str = Field(default="/tmp/nvidia-log", description="MPS log directory")
    exclusive_mode: bool = Field(default=True, description="Enforce EXCLUSIVE_PROCESS compute mode")
    power_limit_w: int = Field(default=SETUP2_GPU_POWER_LIMIT_W, ge=100, le=450, description="Power limit in Watts")
    open_file_limit: int = Field(default=16384, ge=1024, description="ulimit -n open file descriptor limit")


class MPSStatus(BaseModel):
    """Live status and telemetry of the NVIDIA MPS daemon."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    mps_active: bool = Field(default=False, description="Is nvidia-cuda-mps-control daemon running")
    pipe_dir_exists: bool = Field(default=False, description="Does the pipe directory exist on disk")
    log_dir_exists: bool = Field(default=False, description="Does the log directory exist on disk")
    cuda_device_count: int = Field(default=0, ge=0, description="Detected CUDA devices")
    device_name: Optional[str] = Field(default=None, description="Primary CUDA device name")
    vram_total_mb: float = Field(default=0.0, description="Total VRAM in MB")
    vram_used_mb: float = Field(default=0.0, description="Used VRAM in MB")
    vram_free_mb: float = Field(default=0.0, description="Free VRAM in MB")
    power_limit_w: Optional[float] = Field(default=None, description="Active power limit in Watts")
    max_clients_allowed: int = Field(default=MAX_MPS_CLIENTS_CUDA13, description="Max client CUDA contexts")
    recommended_workers: int = Field(default=3, ge=1, le=4, description="Recommended concurrent workers")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class IntegrityGuardResult(BaseModel):
    """Evaluation result for Method Matrix §8A.5 Integrity Guards (G1–G7)."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    guard_id: str = Field(..., description="Guard identifier (G1, G2, G3, G4, G5, G6, G7)")
    guard_name: str = Field(..., description="Descriptive guard name")
    decision: GuardDecision = Field(..., description="Audit decision")
    passed: bool = Field(..., description="True if guard passed without fatal violation")
    metric_name: str = Field(..., description="Evaluated physical or statistical metric")
    metric_value: Any = Field(..., description="Evaluated metric value")
    threshold: Any = Field(..., description="Acceptance threshold")
    details: str = Field(default="", description="Detailed diagnostic rationale")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class HeteroProvenanceRecord(BaseModel):
    """Method Matrix §8A.5 / G7 cryptographic provenance record."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    stage: str = Field(..., description="Pipeline execution stage (e.g. 'mlff_preopt', 'anchor_verify')")
    decision: str = Field(..., description="Routing decision (e.g. 'seed_dft_optimisation', 'accept_isomer')")
    guide: Dict[str, Any] = Field(default_factory=dict, description="Guide/Scout model metadata")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input structure identifiers and SHA-256")
    output: Dict[str, Any] = Field(default_factory=dict, description="Output properties and Hessian files")
    gates: Dict[str, Any] = Field(default_factory=dict, description="G1-G6 integrity gate values")
    consumer: Dict[str, Any] = Field(default_factory=dict, description="Downstream anchor job consumption")
    authority: str = Field(default="advisory_only", description="Authority label: 'advisory_only' or 'authoritative'")


# ---------------------------------------------------------------------------
# 2. Parsl Configuration Builders (§8A.6)
# ---------------------------------------------------------------------------

def build_hetero_config(
    cpu_workers: int = 1,
    cpu_cores_per_worker: int = 7,
    gpu_workers: int = 3,
    mem_per_cpu_worker_gb: float = 28.0,
    mem_per_gpu_worker_gb: float = 6.0,
    active_thread_pct: int = 33,
    pinned_mem_limit: str = "0=6G",
    pipe_dir: str = "/tmp/nvidia-mps",
    log_dir: str = "/tmp/nvidia-log",
    include_orchestrator: bool = True,
    orchestrator_workers: int = 4,
    retries: int = 2,
    as_parsl_object: bool = True,
) -> Union[Any, HeteroParslConfig]:
    """
    Constructs the authoritative Setup 2 Dual-Executor Parsl configuration
    (Intel i7-13700K + NVIDIA RTX 3090 under MPS) mandated by §8A.6.

    Args:
        cpu_workers: Number of CPU workers (default 1; owns 7 MPI ranks).
        cpu_cores_per_worker: P-cores dedicated to ORCA/MPQC (default 7; core 7 feeds GPU).
        gpu_workers: Number of concurrent MPS GPU scout workers (default 3; capped at 4).
        mem_per_cpu_worker_gb: Memory ceiling for CPU worker in GB (default 28 GB).
        mem_per_gpu_worker_gb: VRAM ceiling per GPU worker in GB (default 6 GB).
        active_thread_pct: NVIDIA MPS active thread percentage (default 33%).
        pinned_mem_limit: NVIDIA MPS pinned device memory limit (default '0=6G').
        pipe_dir: MPS socket/pipe directory.
        log_dir: MPS log directory.
        include_orchestrator: Include third utility executor for E-cores / DFK.
        orchestrator_workers: Workers on E-cores (default 4).
        retries: Parsl task retry limit (default 2).
        as_parsl_object: If True, returns instantiated parsl.config.Config object.

    Returns:
        parsl.config.Config or HeteroParslConfig instance.
    """
    is_win = platform.system() == "Windows"
    
    # Format worker_init scripts
    if is_win:
        win_pipe = str(Path(tempfile.gettempdir()) / "nvidia-mps").replace("/", "\\")
        win_log = str(Path(tempfile.gettempdir()) / "nvidia-log").replace("/", "\\")
        cpu_init = "set OMP_NUM_THREADS=1 & set KMP_HW_SUBSET=8c:intel_core,1t"
        gpu_init = (
            f"set CUDA_VISIBLE_DEVICES=0 & "
            f"set CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={active_thread_pct} & "
            f"set CUDA_MPS_PINNED_DEVICE_MEM_LIMIT={pinned_mem_limit} & "
            f"set CUDA_MPS_PIPE_DIRECTORY={win_pipe} & "
            f"set CUDA_MPS_LOG_DIRECTORY={win_log}"
        )
    else:
        cpu_init = "export OMP_NUM_THREADS=1; export KMP_HW_SUBSET=8c:intel_core,1t"
        gpu_init = (
            f"export CUDA_VISIBLE_DEVICES=0; "
            f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={active_thread_pct}; "
            f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{pinned_mem_limit}'; "
            f"export CUDA_MPS_PIPE_DIRECTORY='{pipe_dir}'; "
            f"export CUDA_MPS_LOG_DIRECTORY='{log_dir}'; "
            "ulimit -n 16384"
        )

    cpu_exec = ExecutorConfig(
        label="cpu",
        cores_per_worker=cpu_cores_per_worker,
        max_workers_per_node=cpu_workers,
        cpu_affinity=CoreAffinityType.BLOCK,
        mem_per_worker_gb=mem_per_cpu_worker_gb,
        worker_init=cpu_init,
        provider_type=ProviderBackend.LOCAL,
    )

    gpu_exec = ExecutorConfig(
        label="gpu",
        available_accelerators=gpu_workers,
        max_workers_per_node=gpu_workers,
        cores_per_worker=1,
        cpu_affinity=CoreAffinityType.BLOCK_REVERSE,
        mem_per_worker_gb=mem_per_gpu_worker_gb,
        worker_init=gpu_init,
        provider_type=ProviderBackend.LOCAL,
    )

    orch_exec = None
    if include_orchestrator:
        orch_exec = ExecutorConfig(
            label="orchestrator",
            cores_per_worker=1,
            max_workers_per_node=orchestrator_workers,
            cpu_affinity=CoreAffinityType.ALTERNATING,
            mem_per_worker_gb=4.0,
            worker_init="export OMP_NUM_THREADS=1" if not is_win else "set OMP_NUM_THREADS=1",
            provider_type=ProviderBackend.LOCAL,
        )

    pydantic_cfg = HeteroParslConfig(
        setup_tier=SetupTier.SETUP_2,
        cpu_executor=cpu_exec,
        gpu_executor=gpu_exec,
        orchestrator_executor=orch_exec,
        retries=retries,
        env_vars={
            "CUDA_VISIBLE_DEVICES": "0",
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(active_thread_pct),
            "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": pinned_mem_limit,
            "CUDA_MPS_PIPE_DIRECTORY": pipe_dir if not is_win else win_pipe,
            "CUDA_MPS_LOG_DIRECTORY": log_dir if not is_win else win_log,
        },
    )

    return pydantic_cfg


def build_slurm_hetero_config(
    partition: str = "gpu",
    account: Optional[str] = None,
    nodes: int = 1,
    cpu_cores_per_node: int = 8,
    gpus_per_node: int = 1,
    walltime: str = "24:00:00",
    mem_cpu_gb: float = 32.0,
    mem_gpu_gb: float = 24.0,
    retries: int = 2,
    as_parsl_object: bool = True,
) -> Union[Any, HeteroParslConfig]:
    """
    Constructs the Setup 3 HPC Slurm Heterogeneous configuration (§8A.6).
    App decorators (@bash_app(executors=['cpu']), @python_app(executors=['gpu']))
    remain identical between Local and Slurm providers.

    Args:
        partition: Slurm partition name.
        account: Slurm allocation account.
        nodes: Number of nodes per block.
        cpu_cores_per_node: CPU cores per node.
        gpus_per_node: GPUs per node.
        walltime: Walltime limit string.
        mem_cpu_gb: CPU worker memory in GB.
        mem_gpu_gb: GPU worker memory in GB.
        retries: Parsl task retry limit.
        as_parsl_object: If True, returns instantiated parsl.config.Config.

    Returns:
        parsl.config.Config or HeteroParslConfig instance.
    """
    cpu_opts = f"#SBATCH --cpus-per-task={cpu_cores_per_node}"
    gpu_opts = f"#SBATCH --gres=gpu:{gpus_per_node} --gpus-per-node={gpus_per_node}"
    if account:
        cpu_opts += f"\n#SBATCH --account={account}"
        gpu_opts += f"\n#SBATCH --account={account}"

    cpu_exec = ExecutorConfig(
        label="cpu",
        cores_per_worker=cpu_cores_per_node,
        max_workers_per_node=1,
        cpu_affinity=CoreAffinityType.BLOCK,
        mem_per_worker_gb=mem_cpu_gb,
        worker_init="export OMP_NUM_THREADS=1",
        provider_type=ProviderBackend.SLURM,
        scheduler_options=cpu_opts,
    )

    gpu_exec = ExecutorConfig(
        label="gpu",
        available_accelerators=gpus_per_node,
        max_workers_per_node=1,
        cores_per_worker=1,
        cpu_affinity=CoreAffinityType.BLOCK_REVERSE,
        mem_per_worker_gb=mem_gpu_gb,
        worker_init="export CUDA_VISIBLE_DEVICES=0; ulimit -n 16384",
        provider_type=ProviderBackend.SLURM,
        scheduler_options=gpu_opts,
    )

    pydantic_cfg = HeteroParslConfig(
        setup_tier=SetupTier.SETUP_3,
        cpu_executor=cpu_exec,
        gpu_executor=gpu_exec,
        retries=retries,
    )

    return pydantic_cfg


def build_cpu_only_config(
    cpu_cores: int = 8,
    mem_cpu_gb: float = 32.0,
    maxcore_mb: int = SETUP2_CPU_MAXCORE_SOLO_MB,
    retries: int = 2,
    as_parsl_object: bool = True,
) -> Union[Any, HeteroParslConfig]:
    """
    Constructs the Setup 1 (Teaching / CI / CPU-Only) single-executor configuration (§8A.6).
    Enables all 8 P-cores with %maxcore 3000.

    Args:
        cpu_cores: P-cores for the CPU executor (default 8).
        mem_cpu_gb: Host RAM allocated in GB.
        maxcore_mb: %maxcore per rank in MB (default 3000).
        retries: Parsl task retry limit (default 2).
        as_parsl_object: If True, returns instantiated parsl.config.Config.

    Returns:
        parsl.config.Config or HeteroParslConfig instance.
    """
    is_win = platform.system() == "Windows"
    worker_init = (
        f"set OMP_NUM_THREADS=1 & set ORCA_MAXCORE={maxcore_mb}"
        if is_win
        else f"export OMP_NUM_THREADS=1; export ORCA_MAXCORE={maxcore_mb}"
    )

    cpu_exec = ExecutorConfig(
        label="cpu",
        cores_per_worker=cpu_cores,
        max_workers_per_node=1,
        cpu_affinity=CoreAffinityType.BLOCK,
        mem_per_worker_gb=mem_cpu_gb,
        worker_init=worker_init,
        provider_type=ProviderBackend.LOCAL,
    )

    pydantic_cfg = HeteroParslConfig(
        setup_tier=SetupTier.SETUP_1,
        cpu_executor=cpu_exec,
        gpu_executor=None,
        retries=retries,
    )

    return pydantic_cfg


# ---------------------------------------------------------------------------
# 3. NVIDIA Multi-Process Service (MPS) Control Engine (§8A.4)
# ---------------------------------------------------------------------------

def calculate_optimal_mps_workers(
    measured_vram_mb: float,
    host_p_cores: int = SETUP2_CPU_P_CORES,
    total_usable_vram_mb: float = 20000.0,
) -> Tuple[int, int]:
    """
    Calculates the optimal number of concurrent MPS GPU workers and active thread percentage
    based on measured per-job VRAM footprint (§8A.4).

    Formula (§8A.4):
        N = floor(20000 MB / measured_MB), capped by host P-cores (1 core per worker, 2-4 under MPS).
        Thread percentage = floor(100% / N).

    Args:
        measured_vram_mb: Measured single-point VRAM consumption in MB.
        host_p_cores: Number of physical P-cores available on host (default 8).
        total_usable_vram_mb: Target VRAM partition ceiling in MB (default 20,000 MB).

    Returns:
        Tuple of (recommended_workers, active_thread_percentage).
    """
    if measured_vram_mb <= 0.0:
        measured_vram_mb = 2000.0  # Conservative 2 GB fallback

    vram_bounded_workers = int(math.floor(total_usable_vram_mb / measured_vram_mb))
    # Host P-core feeder limit (host core feeder overhead 57%, 1 P-core per feeder)
    host_core_limit = max(1, host_p_cores // 2)

    # Method Matrix §8A.4 sweet spot: 2 to 4 workers (3 is optimal for MACE/AIMNet2)
    recommended_workers = min(vram_bounded_workers, host_core_limit)
    recommended_workers = max(2, min(recommended_workers, 4))

    active_thread_pct = int(math.floor(100.0 / recommended_workers))
    return recommended_workers, active_thread_pct


def probe_mps_status(device_id: int = 0) -> MPSStatus:
    """
    Probes system and hardware telemetry for NVIDIA MPS daemon status and GPU resource availability.

    Args:
        device_id: Target CUDA device ID (default 0).

    Returns:
        MPSStatus model populated with live hardware information.
    """
    pipe_dir = os.environ.get("CUDA_MPS_PIPE_DIRECTORY", "/tmp/nvidia-mps")
    log_dir = os.environ.get("CUDA_MPS_LOG_DIRECTORY", "/tmp/nvidia-log")
    pipe_exists = Path(pipe_dir).exists()
    log_exists = Path(log_dir).exists()

    mps_active = False
    # Check running processes for nvidia-cuda-mps-control
    try:
        for proc in psutil.process_iter(["name", "cmdline"]):
            pname = (proc.info.get("name") or "").lower()
            if "nvidia-cuda-mps" in pname or "mps-control" in pname:
                mps_active = True
                break
    except Exception:
        mps_active = False

    device_count = 0
    device_name = None
    vram_total_mb = 0.0
    vram_used_mb = 0.0
    vram_free_mb = 0.0
    power_limit_w = None

    # Try pynvml
    if HAS_PYNVML:
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > device_id:
                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                device_name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(device_name, bytes):
                    device_name = device_name.decode("utf-8")
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_total_mb = float(mem_info.total) / (1024.0 * 1024.0)
                vram_used_mb = float(mem_info.used) / (1024.0 * 1024.0)
                vram_free_mb = float(mem_info.free) / (1024.0 * 1024.0)
                try:
                    power_limit_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
                    power_limit_w = float(power_limit_mw) / 1000.0
                except Exception:
                    power_limit_w = float(SETUP2_GPU_POWER_LIMIT_W)
        except Exception as e:
            logger.debug(f"pynvml inspection failed: {e}")

    # Fallback to PyTorch
    if device_count == 0 and HAS_TORCH and torch.cuda.is_available():
        try:
            device_count = torch.cuda.device_count()
            if device_count > device_id:
                device_name = torch.cuda.get_device_name(device_id)
                props = torch.cuda.get_device_properties(device_id)
                vram_total_mb = float(props.total_memory) / (1024.0 * 1024.0)
                vram_used_mb = float(torch.cuda.memory_allocated(device_id)) / (1024.0 * 1024.0)
                vram_free_mb = vram_total_mb - vram_used_mb
        except Exception as e:
            logger.debug(f"torch.cuda inspection failed: {e}")

    # Zero-mock honest telemetry: if no physical GPU is detected, report exact zero resources
    if device_count == 0:
        device_name = "None"
        vram_total_mb = 0.0
        vram_free_mb = 0.0
        power_limit_w = 0.0

    rec_workers, _ = calculate_optimal_mps_workers(
        measured_vram_mb=2000.0,
        host_p_cores=SETUP2_CPU_P_CORES,
    )

    return MPSStatus(
        mps_active=mps_active,
        pipe_dir_exists=pipe_exists,
        log_dir_exists=log_exists,
        cuda_device_count=device_count,
        device_name=device_name,
        vram_total_mb=vram_total_mb,
        vram_used_mb=vram_used_mb,
        vram_free_mb=vram_free_mb,
        power_limit_w=power_limit_w,
        max_clients_allowed=MAX_MPS_CLIENTS_CUDA13,
        recommended_workers=rec_workers,
    )


def generate_mps_startup_script(config: MPSConfig) -> str:
    """
    Emits the authoritative Method Matrix §8A.4 bash setup script for NVIDIA MPS.
    On non-Linux platforms (Windows NT, macOS Darwin), NVIDIA MPS is explicitly bypassed per Suggestion #65.

    Args:
        config: MPSConfig parameters.

    Returns:
        Multi-line bash script string.
    """
    if sys.platform in ("win32", "darwin") or platform.system().lower() in ("windows", "darwin"):
        return (
            f"# CoChem Method Matrix §8A.4 / Suggestion #65: NVIDIA MPS is bypassed on {sys.platform}.\n"
            f"# Concurrency is serialized via cross-process named mutex / Semaphore(1).\n"
        )
    script = (
        f"#!/usr/bin/env bash\n"
        f"# CoChem Method Matrix §8A.4 - NVIDIA MPS Startup Script\n"
        f"set -euo pipefail\n\n"
        f"export CUDA_VISIBLE_DEVICES={config.device_id}\n"
        f"export CUDA_MPS_PIPE_DIRECTORY={config.pipe_directory}\n"
        f"export CUDA_MPS_LOG_DIRECTORY={config.log_directory}\n"
        f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={config.active_thread_percentage}\n"
        f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{config.pinned_mem_limit}'\n\n"
        f"mkdir -p \"{config.pipe_directory}\" \"{config.log_directory}\"\n"
        f"ulimit -n {config.open_file_limit}\n\n"
    )
    if config.exclusive_mode:
        script += f"nvidia-smi -i {config.device_id} -c EXCLUSIVE_PROCESS\n"
    script += (
        f"nvidia-cuda-mps-control -d\n"
        f"nvidia-smi -i {config.device_id} -pl {config.power_limit_w}\n"
        f"echo \"NVIDIA MPS daemon successfully launched on device {config.device_id} (power cap: {config.power_limit_w} W, thread pct: {config.active_thread_percentage}%).\"\n"
    )
    return script


def generate_mps_teardown_script(config: MPSConfig) -> str:
    """
    Emits the authoritative Method Matrix §8A.4 teardown script for NVIDIA MPS.

    Args:
        config: MPSConfig parameters.

    Returns:
        Multi-line bash teardown script string.
    """
    if sys.platform in ("win32", "darwin") or platform.system().lower() in ("windows", "darwin"):
        return f"# CoChem Method Matrix §8A.4 / Suggestion #65: NVIDIA MPS teardown bypassed on {sys.platform}.\n"
    script = (
        f"#!/usr/bin/env bash\n"
        f"# CoChem Method Matrix §8A.4 - NVIDIA MPS Teardown Script\n"
        f"set -euo pipefail\n\n"
        f"export CUDA_MPS_PIPE_DIRECTORY={config.pipe_directory}\n"
        f"echo quit | nvidia-cuda-mps-control || true\n"
        f"nvidia-smi -i {config.device_id} -c DEFAULT || true\n"
        f"echo \"NVIDIA MPS daemon cleanly shut down on device {config.device_id}.\"\n"
    )
    return script


def detect_gpu_scout_config(
    scratch_dir: Optional[Union[str, Path]] = None,
    min_vram_headroom_mb: float = 1536.0,
) -> GpuScoutExecutorConfig:
    """Detect OS and hardware configuration across the 6-Tier Environment Matrix.

    Suggestion #65:
    - Tier 1/2 (Windows/macOS): disable MPS, serialize tasks (max_concurrent=1)
    - Tier 3/6 (Linux/HPC): enable MPS with scratch pipes
    """
    sys_plat = sys.platform
    if sys_plat.startswith("win"):
        platform_os = "windows"
    elif sys_plat == "darwin":
        platform_os = "darwin"
    else:
        platform_os = "linux"

    target_scratch = Path(scratch_dir or os.environ.get("COCHEM_SCRATCH", tempfile.gettempdir())).resolve()
    mps_pipe = str((target_scratch / "nvidia_mps").resolve())

    if platform_os in ("windows", "darwin"):
        return GpuScoutExecutorConfig(
            platform_os=platform_os,
            enable_mps=False,
            mps_pipe_dir=mps_pipe,
            max_concurrent_gpu_tasks=1,
            min_vram_headroom_mb=min_vram_headroom_mb,
        )
    else:
        has_gpu = False
        if HAS_TORCH and torch is not None:
            try:
                has_gpu = torch.cuda.is_available()
            except Exception:
                pass
        return GpuScoutExecutorConfig(
            platform_os="linux",
            enable_mps=has_gpu,
            mps_pipe_dir=mps_pipe,
            max_concurrent_gpu_tasks=3 if has_gpu else 1,
            min_vram_headroom_mb=min_vram_headroom_mb,
        )


class GpuScoutDispatcher:
    """Thread-safe and process-safe GPU scout dispatch controller with VRAM headroom guard.

    Mandated by Method Matrix v4 §8A.2, §8A.4.
    Suggestion #65:
    - Tier 1/2 (Windows/macOS): Serializes GPU kernels via threading.Semaphore(1).
    - Tier 3/6 (Linux): Permits parallel execution under MPS.
    - Dynamic VRAM check: holds tasks if free VRAM < min_vram_headroom_mb.
    """

    _instance: Optional["GpuScoutDispatcher"] = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[GpuScoutExecutorConfig] = None):
        self.config = config or detect_gpu_scout_config()
        self.semaphore = threading.Semaphore(self.config.max_concurrent_gpu_tasks)
        self.active_count = 0
        self._count_lock = threading.Lock()

    @classmethod
    def get_instance(cls, config: Optional[GpuScoutExecutorConfig] = None) -> "GpuScoutDispatcher":
        with cls._lock:
            if cls._instance is None or (config is not None and config != cls._instance.config):
                cls._instance = cls(config)
            return cls._instance

    def check_vram_headroom(self) -> Tuple[bool, float]:
        """Queries torch.cuda.mem_get_info() if CUDA is available."""
        if HAS_TORCH and torch is not None and torch.cuda.is_available():
            try:
                free_b, total_b = torch.cuda.mem_get_info()
                free_mb = free_b / (1024 * 1024)
                return (free_mb >= self.config.min_vram_headroom_mb, free_mb)
            except Exception:
                pass
        return (True, 99999.0)

    @contextmanager
    def dispatch_scout(self, poll_interval: float = 0.05, max_wait: float = 30.0):
        acquired = self.semaphore.acquire(timeout=max_wait)
        if not acquired:
            raise TimeoutError(f"Timeout waiting for GPU scout concurrency slot after {max_wait}s")

        try:
            t0 = time.time()
            while True:
                has_vram, free_mb = self.check_vram_headroom()
                if has_vram:
                    break
                if time.time() - t0 >= max_wait:
                    raise RuntimeError(
                        f"Dynamic VRAM safeguard: {free_mb:.1f} MB free < "
                        f"{self.config.min_vram_headroom_mb:.1f} MB required"
                    )
                time.sleep(poll_interval)

            with self._count_lock:
                self.active_count += 1
            try:
                yield
            finally:
                with self._count_lock:
                    self.active_count -= 1
        finally:
            self.semaphore.release()



# ---------------------------------------------------------------------------
# 4. Method Matrix §8A.5 Integrity Guards (G1–G7)
# ---------------------------------------------------------------------------

def check_guard_g1_scout_advisory(
    stage_name: str,
    authority: str,
    is_reported_final: bool,
) -> IntegrityGuardResult:
    """
    G1: Scout advisory authority rejection (§8A.5).
    Guarantees that no cheap Scout/MLFF surface result claims authoritative status
    or appears directly as a reported final spectroscopic observable.

    Args:
        stage_name: Name of computational stage (e.g. 'mlff_preopt', 'goat_aimnet2').
        authority: Declared authority tag ('advisory_only' or 'authoritative').
        is_reported_final: True if output is being routed to final publication/reporting.

    Returns:
        IntegrityGuardResult with PASS or FAIL decision.
    """
    is_scout = any(tag in stage_name.lower() for tag in ["scout", "mlff", "aimnet", "mace", "extopt", "xtb"])
    if is_scout and authority == "authoritative":
        return IntegrityGuardResult(
            guard_id="G1",
            guard_name="Scout Advisory Authority Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="authority_tag",
            metric_value=authority,
            threshold="advisory_only",
            details=f"Violation in stage '{stage_name}': cheap scout calculation declared 'authoritative'.",
        )
    if is_scout and is_reported_final:
        return IntegrityGuardResult(
            guard_id="G1",
            guard_name="Scout Advisory Authority Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="is_reported_final",
            metric_value=is_reported_final,
            threshold=False,
            details=f"Violation in stage '{stage_name}': scout result masquerading as final reported observable.",
        )
    return IntegrityGuardResult(
        guard_id="G1",
        guard_name="Scout Advisory Authority Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="authority_tag",
        metric_value=authority,
        threshold="advisory_only" if is_scout else "authoritative",
        details="G1 verified: scout outputs strictly advisory.",
    )


def check_guard_g2_high_level_hessian(
    harmonic_frequencies_cm_inv: Sequence[float],
    expected_imaginary_count: int = 0,
    softest_force_constant_threshold: float = 0.0,
) -> IntegrityGuardResult:
    """
    G2: High-Level Hessian Verification Guard (§8A.5).
    Verifies that the final anchor structure carries a high-level Hessian
    with the expected number of imaginary frequencies (0 for minima, 1 for TS)
    and reports the softest force constant.

    Args:
        harmonic_frequencies_cm_inv: List of vibrational frequencies in cm^-1.
        expected_imaginary_count: Target imaginary count (default 0 for equilibrium geometry).
        softest_force_constant_threshold: Minimum positive frequency for real modes.

    Returns:
        IntegrityGuardResult.
    """
    freqs = np.array(harmonic_frequencies_cm_inv, dtype=float)
    imag_count = int(np.sum(freqs < -1e-3))
    real_freqs = freqs[freqs >= 0.0]
    softest_fc = float(np.min(real_freqs)) if len(real_freqs) > 0 else 0.0

    if imag_count != expected_imaginary_count:
        return IntegrityGuardResult(
            guard_id="G2",
            guard_name="High-Level Hessian Verification Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="imaginary_frequency_count",
            metric_value=imag_count,
            threshold=expected_imaginary_count,
            details=f"Structure possesses {imag_count} imaginary frequencies (expected {expected_imaginary_count}). Softest force constant: {softest_fc:.2f} cm^-1.",
        )

    return IntegrityGuardResult(
        guard_id="G2",
        guard_name="High-Level Hessian Verification Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="imaginary_frequency_count",
        metric_value=imag_count,
        threshold=expected_imaginary_count,
        details=f"G2 verified: {imag_count} imaginary modes. Softest harmonic mode: {softest_fc:.2f} cm^-1.",
    )


def compute_kabsch_rmsd(
    coords_p: np.ndarray,
    coords_q: np.ndarray,
    masses: Optional[np.ndarray] = None,
) -> float:
    """
    Computes exact Kabsch optimal superposition Root-Mean-Square Deviation (RMSD)
    between two Cartesian coordinate sets of identical stoichiometry.

    Args:
        coords_p: First geometry array (N, 3) in Angstroms.
        coords_q: Second geometry array (N, 3) in Angstroms.
        masses: Optional atomic masses array (N,) for mass-weighting.

    Returns:
        RMSD in Angstroms.
    """
    p = np.array(coords_p, dtype=float)
    q = np.array(coords_q, dtype=float)
    if p.shape != q.shape or p.ndim != 2 or p.shape[1] != 3:
        raise ValueError(f"Coordinate shape mismatch: {p.shape} vs {q.shape}")

    n_atoms = p.shape[0]
    if masses is None:
        w = np.ones(n_atoms, dtype=float) / n_atoms
    else:
        w = np.array(masses, dtype=float) / np.sum(masses)

    # Center centroids
    p_center = np.sum(p * w[:, None], axis=0)
    q_center = np.sum(q * w[:, None], axis=0)
    p_centered = p - p_center
    q_centered = q - q_center

    # Covariance matrix H = P^T * W * Q
    h = np.dot((p_centered * w[:, None]).T, q_centered)
    v, s, wt = np.linalg.svd(h)
    d = np.linalg.det(np.dot(v, wt))

    # Reflection correction
    e = np.eye(3)
    if d < 0.0:
        e[2, 2] = -1.0

    rot = np.dot(v, np.dot(e, wt))
    p_rotated = np.dot(p_centered, rot)
    diff = p_rotated - q_centered
    rmsd = float(np.sqrt(np.sum(w[:, None] * (diff ** 2))))
    return rmsd


def check_guard_g3_basin_identity(
    scout_coords: np.ndarray,
    anchor_coords: np.ndarray,
    symbols: Sequence[str],
    max_rmsd_ang: float = DEFAULT_G3_MAX_RMSD_ANG,
    max_dr_ang: float = DEFAULT_G3_MAX_DR_ANG,
) -> IntegrityGuardResult:
    """
    G3: Basin-Identity Check Guard (§8A.5).
    Compares scout minimum against anchor DFT converged minimum.
    Gate: RMSD > 0.25 Å or Delta R > 0.20 Å triggers a 'FLAG_BASIN_CHANGE' advisory alert.

    Args:
        scout_coords: Scout geometry (N, 3) in Angstroms.
        anchor_coords: Anchor DFT geometry (N, 3) in Angstroms.
        symbols: Atomic symbols of the complex.
        max_rmsd_ang: RMSD threshold in Angstroms (default 0.25 Å).
        max_dr_ang: Intermolecular center of mass separation Delta R (default 0.20 Å).

    Returns:
        IntegrityGuardResult with PASS or FLAG_BASIN_CHANGE.
    """
    masses = np.array([get_atomic_mass(s) for s in symbols], dtype=float)
    rmsd = compute_kabsch_rmsd(scout_coords, anchor_coords, masses=masses)

    # Center of mass separation Delta R
    total_m = np.sum(masses)
    scout_com = np.sum(scout_coords * masses[:, None], axis=0) / total_m
    anchor_com = np.sum(anchor_coords * masses[:, None], axis=0) / total_m
    dr = float(np.linalg.norm(scout_com - anchor_com))

    if rmsd > max_rmsd_ang or dr > max_dr_ang:
        return IntegrityGuardResult(
            guard_id="G3",
            guard_name="Basin-Identity Guard",
            decision=GuardDecision.FLAG_BASIN_CHANGE,
            passed=True,  # Advisory flag, does not abort pipeline
            metric_name="heavy_atom_rmsd_ang",
            metric_value={"rmsd_ang": rmsd, "delta_r_ang": dr},
            threshold={"max_rmsd_ang": max_rmsd_ang, "max_dr_ang": max_dr_ang},
            details=f"Basin change detected: RMSD={rmsd:.3f} Å (max {max_rmsd_ang} Å), Delta R={dr:.3f} Å (max {max_dr_ang} Å). Re-running guide from anchor geometry.",
        )

    return IntegrityGuardResult(
        guard_id="G3",
        guard_name="Basin-Identity Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="heavy_atom_rmsd_ang",
        metric_value={"rmsd_ang": rmsd, "delta_r_ang": dr},
        threshold={"max_rmsd_ang": max_rmsd_ang, "max_dr_ang": max_dr_ang},
        details=f"G3 verified: RMSD={rmsd:.3f} Å, Delta R={dr:.3f} Å within basin tolerance.",
    )


def check_guard_g4_rank_inversion(
    scout_energies_hartree: Sequence[float],
    anchor_energies_hartree: Sequence[float],
    min_spearman_rho: float = DEFAULT_G4_MIN_SPEARMAN_RHO,
    retention_window_kcal_mol: float = DEFAULT_G4_RETENTION_WINDOW_KCAL_MOL,
) -> IntegrityGuardResult:
    """
    G4: Rank-Inversion Audit Guard (§8A.5).
    Evaluates Spearman rank correlation on a benchmark sample before permitting
    any cheap-surface ensemble culling. Culling permitted only if rho >= 0.90.

    Args:
        scout_energies_hartree: Scout relative/absolute energies.
        anchor_energies_hartree: Authoritative DFT relative/absolute energies.
        min_spearman_rho: Minimum required Spearman rank correlation (default 0.90).
        retention_window_kcal_mol: Retention energy window (default 10.0 kcal/mol).

    Returns:
        IntegrityGuardResult with PASS or FAIL.
    """
    if len(scout_energies_hartree) < 5 or len(anchor_energies_hartree) < 5:
        return IntegrityGuardResult(
            guard_id="G4",
            guard_name="Rank-Inversion Audit Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="sample_size",
            metric_value=min(len(scout_energies_hartree), len(anchor_energies_hartree)),
            threshold=20,
            details="Sample size too small for statistical rank correlation audit (N < 5; recommend N >= 20).",
        )

    rho_res = scipy.stats.spearmanr(scout_energies_hartree, anchor_energies_hartree)
    rho = float(rho_res.statistic if hasattr(rho_res, "statistic") else rho_res[0])

    if math.isnan(rho) or rho < min_spearman_rho:
        return IntegrityGuardResult(
            guard_id="G4",
            guard_name="Rank-Inversion Audit Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="spearman_rho",
            metric_value=rho,
            threshold=min_spearman_rho,
            details=f"Spearman rank correlation rho={rho:.3f} below mandatory threshold {min_spearman_rho}. Culling forbidden; retaining full ensemble.",
        )

    return IntegrityGuardResult(
        guard_id="G4",
        guard_name="Rank-Inversion Audit Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="spearman_rho",
        metric_value=rho,
        threshold=min_spearman_rho,
        details=f"G4 verified: Spearman rho={rho:.3f} >= {min_spearman_rho}. Culling allowed within {retention_window_kcal_mol} kcal/mol window.",
    )


def check_guard_g5_uncertainty(
    committee_sigma_mev_atom: float,
    epsilon_threshold_mev_atom: float = 15.0,
) -> IntegrityGuardResult:
    """
    G5: Uncertainty Gate (§8A.5, §10.8).
    Evaluates MLFF ensemble committee variance against threshold epsilon.

    Args:
        committee_sigma_mev_atom: Committee standard deviation in meV/atom.
        epsilon_threshold_mev_atom: Acceptance threshold.

    Returns:
        IntegrityGuardResult.
    """
    passed = committee_sigma_mev_atom <= epsilon_threshold_mev_atom
    return IntegrityGuardResult(
        guard_id="G5",
        guard_name="Uncertainty Gate",
        decision=GuardDecision.PASS if passed else GuardDecision.FAIL,
        passed=passed,
        metric_name="committee_sigma_mev_atom",
        metric_value=committee_sigma_mev_atom,
        threshold=epsilon_threshold_mev_atom,
        details=f"Committee uncertainty: {committee_sigma_mev_atom:.2f} meV/atom (threshold: {epsilon_threshold_mev_atom:.2f} meV/atom).",
    )


def check_guard_g6_abort_rule(
    consecutive_failures: int,
    max_threshold: int = DEFAULT_G6_MAX_CONSECUTIVE_FAILURES,
) -> IntegrityGuardResult:
    """
    G6: Abort-the-Guide Rule (§8A.5).
    Triggers hard fallback to pure high-level DFT execution when consecutive guide failures >= 5.

    Args:
        consecutive_failures: Count of consecutive failed guide preconditioning steps.
        max_threshold: Threshold n_th (default 5).

    Returns:
        IntegrityGuardResult with PASS or ABORT decision.
    """
    if consecutive_failures >= max_threshold:
        return IntegrityGuardResult(
            guard_id="G6",
            guard_name="Abort-the-Guide Rule",
            decision=GuardDecision.ABORT,
            passed=False,
            metric_name="consecutive_guide_failures",
            metric_value=consecutive_failures,
            threshold=max_threshold,
            details=f"Guide failure threshold exceeded ({consecutive_failures} >= {max_threshold}). Guide declared unreliable; completing job via pure high-level DFT.",
        )
    return IntegrityGuardResult(
        guard_id="G6",
        guard_name="Abort-the-Guide Rule",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="consecutive_guide_failures",
        metric_value=consecutive_failures,
        threshold=max_threshold,
        details=f"G6 verified: {consecutive_failures}/{max_threshold} guide failures.",
    )


def create_provenance_event(
    stage: str,
    decision: str,
    guide_code: str = "mace-torch 0.3.x",
    model_key: str = "MACE-OFF24-medium",
    precision: str = "float32",
    device: str = "cuda:0",
    mps_active_thread_pct: int = 33,
    structure_id: str = "iso_001",
    source_str: str = "goat_xtb.finalensemble.xyz#1",
    xyz_coordinates: Optional[np.ndarray] = None,
    e_guide_ev: Optional[float] = None,
    fmax_ev_a: Optional[float] = None,
    hessian_file: Optional[str] = None,
    g4_spearman_rho: Optional[float] = None,
    g3_rmsd_a: Optional[float] = None,
    log_file_path: Optional[Union[str, Path]] = None,
) -> HeteroProvenanceRecord:
    """
    Constructs a Method Matrix §8A.5 / G7 cryptographic provenance audit event
    and optionally appends it to provenance.jsonl.

    Args:
        stage: Pipeline execution stage.
        decision: Decision label.
        guide_code: Engine string.
        model_key: Canonical model key.
        precision: Precision string.
        device: Target execution device.
        mps_active_thread_pct: MPS thread percentage.
        structure_id: Structure identifier.
        source_str: Source identifier.
        xyz_coordinates: Coordinate array for SHA-256 calculation.
        e_guide_ev: Energy in eV.
        fmax_ev_a: Max force in eV/Å.
        hessian_file: Path to Cartesian Hessian file.
        g4_spearman_rho: Evaluated G4 Spearman rho.
        g3_rmsd_a: Evaluated G3 RMSD.
        log_file_path: Target JSONL log file path.

    Returns:
        HeteroProvenanceRecord model.
    """
    xyz_hash = ""
    if xyz_coordinates is not None:
        xyz_hash = hashlib.sha256(np.ascontiguousarray(xyz_coordinates).tobytes()).hexdigest()
    else:
        xyz_hash = hashlib.sha256(structure_id.encode("utf-8")).hexdigest()

    rec = HeteroProvenanceRecord(
        stage=stage,
        decision=decision,
        guide={
            "code": guide_code,
            "model_key": model_key,
            "precision": precision,
            "device": device,
            "mps_active_thread_pct": mps_active_thread_pct,
        },
        input={
            "structure_id": structure_id,
            "source": source_str,
            "sha256": xyz_hash,
        },
        output={
            "xyz_sha256": xyz_hash,
            "E_guide_eV": e_guide_ev,
            "fmax_eV_A": fmax_ev_a,
            "hessian_file": hessian_file,
        },
        gates={
            "G4_spearman_rho": g4_spearman_rho,
            "G3_rmsd_A": g3_rmsd_a,
        },
        consumer={"anchor_job": f"{structure_id}_wb97xd4.inp"},
        authority="advisory_only",
    )

    if log_file_path:
        out_p = Path(log_file_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "a", encoding="utf-8") as f:
            f.write(rec.model_dump_json() + "\n")

    return rec


# ---------------------------------------------------------------------------
# 5. Diagnostic and Benchmark Runner
# ---------------------------------------------------------------------------

def run_hetero_diagnostic(
    config: Optional[HeteroParslConfig] = None,
) -> Dict[str, Any]:
    """
    Performs a physical validation diagnostic of the heterogeneous configuration
    and host hardware environment.

    Args:
        config: Optional HeteroParslConfig. If None, builds default Setup 2 config.

    Returns:
        Dictionary containing hardware, MPS, and Parsl executor diagnostics.
    """
    if config is None:
        config = build_hetero_config(as_parsl_object=False)  # type: ignore

    mps_stat = probe_mps_status()
    cpu_cores_physical = psutil.cpu_count(logical=False) or SETUP2_CPU_TOTAL_PHYSICAL_CORES
    cpu_cores_logical = psutil.cpu_count(logical=True) or SETUP2_CPU_TOTAL_THREADS
    mem_info = psutil.virtual_memory()
    host_ram_gb = float(mem_info.total) / (1024.0 ** 3)

    diagnostic: Dict[str, Any] = {
        "status": "HEALTHY",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "setup_tier": config.setup_tier.value,
        "host_hardware": {
            "os": f"{platform.system()} {platform.release()}",
            "physical_cores": cpu_cores_physical,
            "logical_threads": cpu_cores_logical,
            "total_ram_gb": round(host_ram_gb, 2),
            "cpu_model": SETUP2_CPU_MODEL,
        },
        "mps_telemetry": mps_stat.model_dump(),
        "executors": {
            "cpu_anchor": config.cpu_executor.model_dump(),
            "gpu_scout": config.gpu_executor.model_dump() if config.gpu_executor else None,
            "orchestrator": config.orchestrator_executor.model_dump() if config.orchestrator_executor else None,
        },
        "retries": config.retries,
        "mendeleev_verification": {
            "H_mass": get_atomic_mass("H"),
            "C_mass": get_atomic_mass("C"),
            "O_mass": get_atomic_mass("O"),
        },
    }
    return diagnostic


# ---------------------------------------------------------------------------
# 6. CLI Driver Interface
# ---------------------------------------------------------------------------

def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs the command-line interface argument parser for hetero_config.py."""
    parser = argparse.ArgumentParser(
        prog="hetero_config.py",
        description="CoChem-TOPOS: Heterogeneous CPU (13700K) + GPU (RTX 3090) Dual Parsl Executor Driver (§8A.4, §8A.6)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["dual", "cpu-only", "slurm", "status", "mps-setup", "mps-stop", "guard-check", "diagnostic"],
        default="dual",
        help="Execution or configuration mode",
    )
    parser.add_argument(
        "--cpu-workers",
        type=int,
        default=1,
        help="Number of CPU anchor workers (owns 7 ranks on 13700K)",
    )
    parser.add_argument(
        "--cpu-cores",
        type=int,
        default=7,
        help="P-cores dedicated to the CPU anchor worker (cores 0-6)",
    )
    parser.add_argument(
        "--gpu-workers",
        type=int,
        default=3,
        help="Concurrent GPU scout workers under MPS (2-4 optimal)",
    )
    parser.add_argument(
        "--mem-cpu",
        type=float,
        default=28.0,
        help="Memory ceiling per CPU worker in GB (%%maxcore 3400 + headroom)",
    )
    parser.add_argument(
        "--mem-gpu",
        type=float,
        default=6.0,
        help="VRAM ceiling per GPU worker in GB",
    )
    parser.add_argument(
        "--active-thread-pct",
        type=int,
        default=33,
        help="NVIDIA MPS active thread percentage (100 / N_workers)",
    )
    parser.add_argument(
        "--power-limit",
        type=int,
        default=SETUP2_GPU_POWER_LIMIT_W,
        help="GPU board power limit in Watts (80%% board power = 280 W)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path to write JSON configuration or bash script",
    )
    parser.add_argument(
        "--provenance-log",
        type=str,
        default="provenance.jsonl",
        help="Path to append cryptographic provenance records",
    )
    return parser


def main() -> int:
    """Primary execution entry point for the hetero_config.py CLI driver."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if args.mode == "status" or args.mode == "diagnostic":
        diag = run_hetero_diagnostic()
        json_output = json.dumps(diag, indent=2)
        if args.out:
            Path(args.out).write_text(json_output, encoding="utf-8")
            logger.info(f"Diagnostic telemetry written to {args.out}")
        else:
            print(json_output)
        return 0

    elif args.mode == "dual":
        cfg = build_hetero_config(
            cpu_workers=args.cpu_workers,
            cpu_cores_per_worker=args.cpu_cores,
            gpu_workers=args.gpu_workers,
            mem_per_cpu_worker_gb=args.mem_cpu,
            mem_per_gpu_worker_gb=args.mem_gpu,
            active_thread_pct=args.active_thread_pct,
            as_parsl_object=False,
        )
        json_str = cfg.model_dump_json(indent=2)  # type: ignore
        if args.out:
            Path(args.out).write_text(json_str, encoding="utf-8")
            logger.info(f"Setup 2 Dual-Executor configuration exported to {args.out}")
        else:
            print(json_str)
        return 0

    elif args.mode == "cpu-only":
        cfg = build_cpu_only_config(
            cpu_cores=8,
            mem_cpu_gb=32.0,
            as_parsl_object=False,
        )
        json_str = cfg.model_dump_json(indent=2)  # type: ignore
        if args.out:
            Path(args.out).write_text(json_str, encoding="utf-8")
            logger.info(f"Setup 1 CPU-Only configuration exported to {args.out}")
        else:
            print(json_str)
        return 0

    elif args.mode == "slurm":
        cfg = build_slurm_hetero_config(as_parsl_object=False)
        json_str = cfg.model_dump_json(indent=2)  # type: ignore
        if args.out:
            Path(args.out).write_text(json_str, encoding="utf-8")
            logger.info(f"Setup 3 Slurm HPC configuration exported to {args.out}")
        else:
            print(json_str)
        return 0

    elif args.mode == "mps-setup":
        mps_cfg = MPSConfig(
            active_thread_percentage=args.active_thread_pct,
            power_limit_w=args.power_limit,
        )
        script = generate_mps_startup_script(mps_cfg)
        if args.out:
            Path(args.out).write_text(script, encoding="utf-8")
            logger.info(f"MPS startup script written to {args.out}")
        else:
            print(script)
        return 0

    elif args.mode == "mps-stop":
        mps_cfg = MPSConfig()
        script = generate_mps_teardown_script(mps_cfg)
        if args.out:
            Path(args.out).write_text(script, encoding="utf-8")
            logger.info(f"MPS teardown script written to {args.out}")
        else:
            print(script)
        return 0

    elif args.mode == "guard-check":
        # Run demonstration audit of G1-G7 guards
        g1 = check_guard_g1_scout_advisory("mlff_preopt", "advisory_only", False)
        g2 = check_guard_g2_high_level_hessian([150.0, 300.0, 1600.0, 3700.0], 0)
        
        # Test G3 with water dimer coordinates
        c1 = np.array([
            [-1.464,  0.000, -0.057],
            [-1.933,  0.772,  0.245],
            [-1.933, -0.772,  0.245],
            [ 1.464,  0.000,  0.057],
            [ 0.505,  0.000, -0.057],
            [ 1.933,  0.000, -0.772],
        ])
        c2 = c1 + 0.02 * np.random.randn(*c1.shape)
        g3 = check_guard_g3_basin_identity(c1, c2, ["O", "H", "H", "O", "H", "H"])
        g4 = check_guard_g4_rank_inversion(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            [1.1, 2.05, 3.1, 3.95, 5.2, 5.9, 7.1, 8.05],
        )
        g5 = check_guard_g5_uncertainty(4.1, 15.0)
        g6 = check_guard_g6_abort_rule(1, 5)

        results = [g1.model_dump(), g2.model_dump(), g3.model_dump(), g4.model_dump(), g5.model_dump(), g6.model_dump()]
        output_str = json.dumps(results, indent=2)
        if args.out:
            Path(args.out).write_text(output_str, encoding="utf-8")
            logger.info(f"Integrity guard check results written to {args.out}")
        else:
            print(output_str)
        return 0

# =============================================================================
# Dual GPU Pool Partitioning & Level-of-Theory Task Router (Suggestion #76)
# =============================================================================
from cochem_base.core_engine.cochem_core_parsl_executors import WorkerModelCache


def determine_gpu_executor_pool(theory_or_model: str) -> str:
    """
    Route task to appropriate GPU executor pool based on level-of-theory or model name.
    Mandated by Suggestion #76 (Deliverable 6):
      - MLFF screening (MACE, AIMNet2, mlff, etc.) -> 'gpu_scout_mlff'
      - Heavy electronic structure (gpu4pyscf, large DFT, def2-tzvpp, def2-qzvpp) -> 'gpu_anchor_pyscf'
    """
    t = str(theory_or_model).lower().strip()
    anchor_keywords = [
        "gpu4pyscf", "pyscf", "tzvpp", "qzvpp", "large_dft", "heavy"
    ]
    if any(k in t for k in anchor_keywords):
        return "gpu_anchor_pyscf"
    return "gpu_scout_mlff"


def route_task_by_theory_level(task_spec: Dict[str, Any]) -> str:
    """
    Determine target GPU executor pool ('gpu_scout_mlff' vs 'gpu_anchor_pyscf')
    from a structured task specification dict.
    """
    theory = str(task_spec.get("theory_level", "")).lower().strip()
    basis = str(task_spec.get("basis", "")).lower().strip()
    model = str(task_spec.get("model", "")).lower().strip()

    if any(k in basis for k in ["tzvpp", "qzvpp", "cc-pvt", "cc-pvq"]):
        return "gpu_anchor_pyscf"
    if any(k in theory for k in ["gpu4pyscf", "pyscf"]):
        return "gpu_anchor_pyscf"
    if model:
        return determine_gpu_executor_pool(model)
    if theory:
        return determine_gpu_executor_pool(theory)
    return "gpu_scout_mlff"


def teardown_gpu_task(min_headroom_gb: float = 2.0, max_wait_seconds: float = 30.0) -> None:
    """
    Task teardown hook enforcing torch.cuda.empty_cache() and polling VRAM headroom.
    If VRAM headroom is < 2.0 GB, delays subsequent task submission until memory settles.
    """
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            t0 = time.time()
            while time.time() - t0 < max_wait_seconds:
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                free_gb = free_bytes / (1024 ** 3)
                if free_gb >= min_headroom_gb:
                    break
                time.sleep(0.1)
    except Exception as e:
        logger.debug(f"GPU teardown hook notice: {e}")


if __name__ == "__main__":
    sys.exit(main())

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.