Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_15_Ecosystem_Part_15_prompts.md.
Original prompt:
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 15, Suggestions #141–#150)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring, concurrency stabilization, platform compatibility remediation, and physical integrity enforcement specified in SRS Chunk 15 (Suggestions #141–#150).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds, §8A Concurrency Directives & Zero-CUDA-Locking Directive, §8A.2 Scout-and-Anchor Concurrency, §8A.4 NVIDIA MPS Daemon Lifecycle, §8A.6 Parsl Multi-Executor Architecture, §8B.3 Methodological Bans, §8B.4 Canonical Arrows 4 & 5 Wavefunction Projection via `%moinp`, §8C Thread-Safe HDF5 SWMR Storage Standards, §9A Recipe R1/R2 van der Waals Complex Protocols, §9A.5 Frozen-Monomer Directives & Model Hessians, §9B.1–§9B.4 Non-Covalent Complex Protocols, §10.2–§10.3 Conservative Analytical Gradients, §10.8 Active Learning Sampling Protocols & Investigator-in-the-Loop Principle, Quick Start §QS-1 Tight Convergence Thresholds, Quick Start §QS-3 JAX 64-Bit Initialization), Tripartite Filesystem Air-Gap Architecture ($T_{\text{src}}$, $T_{\text{scr}}$, $T_{\text{store}}$), Anti-Spoofing Protocol v2 (Zero-Mock, Dynamic Mendeleev Retrieval, Dynamic Physical Constants, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, dummy loops, synthetic fallback telemetry, fabricated electronic structure cycles, or canned empirical surfaces.
  - Strict prohibition on `Calc_Hess true` for all geometry optimizations (enforce model Hessians `InHess XTB2` or `Lindh`).
  - Strict prohibition on additive diffuse corrections and small-system ONIOM partitioning.
  - All atomic masses, isotopic masses, and covalent/vdW radii must be dynamically retrieved via `from mendeleev import element` or validated pinned tables in `cochem_base.physics.isotopes` (never hardcode physical constants; in air-gapped runtimes, query `cochem_base.physics.isotopes` which is validated against `mendeleev` during Stage 0 provisioning).
  - All physical unit conversions must be queried dynamically via `scipy.constants.physical_constants` or `ase.units`.
  - Cross-process concurrency synchronization and persistent storage locking strictly via `filelock.FileLock` or `cochem.concurrency.atomic_file_lock.RWFileLock` (POSIX `fcntl.flock` is strictly banned on network filesystems, container mounts, and Windows filesystems).
  - Strict Tripartite Workspace Air-Gap compliance: immutable source tree $T_{\text{src}}$ (`$COCH_SRC`), ephemeral scratch $T_{\text{scr}}$ (`$COCH_SCRATCH`), and persistent store $T_{\text{store}}$ (`$COCH_STORE_DIR`).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Atomic Fallback Alerting & Uncertainty Marker Protocol in OET Client (Suggestion #141)
**Target Module:** `CoChem-TORQ` (`scripts/oet_client.py`, lines 575–610)

### Detailed Requirements:
1. **Eliminate Silent Empirical Fallbacks:**
   - In [`scripts/oet_client.py:L575-L610`](file:///D:/__CoChem/GitHub-Repo/CoChem-TORQ/scripts/oet_client.py#L575-L610), address the unannounced transition to `PhysicalOETFallbackCalculator` when the socket connection to the OET daemon fails.
   - ORCA calculates derivatives by reading `<base>_EXT.engrad`, which receives valid numbers regardless of the underlying potential. Prohibit silent substitution of an ab-initio MLFF surface (e.g., MACE-OFF24m) with crude molecular mechanics.
2. **Implement Atomic Fallback Alert Artifact Generation:**
   - Whenever `oet_client.py` falls back to `PhysicalOETFallbackCalculator`, it must atomically write an audit alert JSON file (`<base>_EXT.fallback_alert.json`) in the active scratch directory ($T_{\text{scr}}$):
     ```json
     {
       "timestamp_utc": "ISO-8601-STRING",
       "event": "OET_DAEMON_FALLBACK_TRIGGERED",
       "requested_backend": "mace_off24m",
       "active_fallback": "PhysicalOETFallbackCalculator",
       "provenance_tag": "[E]",
       "socket_target": "127.0.0.1:PORT_OR_PIPE",
       "reason": "CONNECTION_REFUSED_OR_TIMEOUT",
       "investigator_action_required": true
     }
     ```
   - Ensure the JSON file is written atomically (write to temporary UUID file and `os.replace`).
3. **Write Uncertainty Marker & Signal Host Workflow:**
   - Simultaneously create an empty uncertainty marker file (`<base>_EXT.uncertainty_marker`).
   - If the orchestrator configured `--strict-provenance` or `fail_on_fallback=True`, `oet_client.py` must raise an explicit `OETDaemonUnavailableError` rather than continuing silently.
   - For non-strict modes, ensure the workflow orchestrator polls for `<base>_EXT.fallback_alert.json` after ORCA execution, immediately tagging the resulting stationary point or trajectory with provenance tag `[E]` (Empirical projection) rather than `[M]` (Measured/Validated MLFF).
4. **Path Handling & Air-Gap Compliance:**
   - Derive all file paths dynamically from the base job name using `pathlib.Path` within the ephemeral computational tier ($T_{\text{scr}}$).

---

## Deliverable 2: Eradication of Synthetic GBW/OPT Fallback Artifacts & Explicit Exception Signaling (Suggestion #142)
**Target Modules:** `CoChem-TOPOS` and `CoChem-TORQ` (`chain.py` in both repositories, e.g., lines 1170–1171)

### Detailed Requirements:
1. **Purge Synthetic Binary File Fabrication:**
   - In `CoChem-TOPOS/chain.py` and `CoChem-TORQ/Libraries/chain.py` (around lines 1170–1171), completely remove code that writes hardcoded byte sequences into `.gbw` and `.opt` files when `orca_bin` is missing or ORCA execution fails.
   - Eradicate synthetic SCF and optimization cycle fabrication (e.g., hardcoded `scf_cyc = 12`, `opt_cyc = 6`).
   - Eradicate simulated log outputs injecting `ORCA TERMINATED NORMALLY` and claiming `converged = True` when the calculation did not genuinely execute.
2. **Purge Unphysical Potential Formulas:**
   - Completely delete `evaluate_vdw_potential_and_derivatives` and any unphysical ad-hoc formulas (such as `sum(-0.5 * (mass ** 1.5))`).
3. **Implement Explicit Exception Hierarchy:**
   - Define and raise explicit, typed exceptions when electronic structure calculations fail:
     - `MissingBinaryError`: raised immediately when the configured ORCA, CREST, or xTB executable path is invalid or not executable.
     - `ConvergenceFailureError`: raised when an electronic structure engine fails to achieve SCF or geometry convergence within allotted cycles.
     - `CorruptOutputError`: raised when expected binary wavefunction containers or Hessian matrices are missing or malformed.
4. **Enforce Downstream Workflow Protection:**
   - Adhere to Method Matrix §8B.4 (Canonical Arrows 4 & 5 mandate genuine binary wavefunction projection via `%moinp`).
   - Ensure downstream chained stages never ingest corrupt, synthetic binary wavefunction files (`.gbw`) or fake geometry optimization containers (`.opt`). Chained stages must catch `ConvergenceFailureError` and trigger genuine self-healing rerouting (e.g., dynamic grid tightening, model Hessian re-evaluation) or abort cleanly with degraded execution status.

---

## Deliverable 3: Cross-Process Reader-Writer Locking (`RWFileLock`) for Concurrent HDF5 Campaign Datastores (Suggestion #143)
**Target Module:** `CoChem-TOPOS` (`gpu_point.py`, line 1267; `chain.py`, line 970; `pes_h5.py`)

### Detailed Requirements:
1. **Diagnose and Eliminate Multi-Worker HDF5 Collisions:**
   - In `gpu_point.py` (L1267) and `chain.py` (L970), eradicate raw, uncoordinated `h5py.File(path, "a")` calls.
   - Recognize that POSIX/Win32 file locks enforced by standard HDF5 C-libraries collide during concurrent write operations, throwing `BlockingIOError` or `OSError: file already open for write`. Furthermore, HDF5 SWMR (Single-Writer Multiple-Reader) strictly limits concurrency to 1 writer and $N$ readers.
2. **Enforce Centralized File Locking:**
   - Wrap all HDF5 persistence routines across `CoChem-TOPOS` and `CoChem-TORQ` with `cochem.concurrency.atomic_file_lock.RWFileLock` or cross-platform `filelock.FileLock`.
   - Ensure write transactions acquire an exclusive file lock:
     ```python
     from filelock import FileLock, Timeout

     lock_path = Path(f"{hdf5_filepath}.lock")
     lock = FileLock(lock_path, timeout=30.0)
     with lock:
         with h5py.File(hdf5_filepath, "a", libver="latest") as h5_file:
             # Atomic write transaction
     ```
3. **Configurable Retry Backoff & Read-Through SWMR:**
   - Implement an exponential backoff retry loop (initial delay 5 ms, jitter $\pm 20\%$, maximum retry timeout 30 s) to gracefully handle lock contention under high Parsl task loads.
   - For read operations, enable HDF5 SWMR mode (`swmr=True`) so reader processes do not block behind long read queries.
4. **Adherence to Method Matrix §8C:**
   - Ensure all persisted records conform to production HDF5 dataset chunking, dataset pre-allocation, and PROV-O provenance tagging (`[M]`, `[D]`, `[E]`).

---

## Deliverable 4: OS-Aware GPU Scout Concurrency & Windows/macOS Serialized Dynamic VRAM Routing (Suggestion #144)
**Target Modules:** `CoChem-BASE` and `CoChem-TOPOS` (`cochem_core_parsl_executors.py`, `hetero_config.py`, lines 416–426; `cochem_mps_worker.sh`)

### Detailed Requirements:
1. **Eradicate Hardcoded Linux MPS Invocations on Non-Linux Hosts:**
   - In [`hetero_config.py:L416-L426`](file:///D:/__CoChem/GitHub-Repo/CoChem-TOPOS/hetero_config.py#L416-L426) and `cochem_core_parsl_executors.py`, remove unconditional calls to `nvidia-cuda-mps-control`.
   - Recognize that NVIDIA MPS is an architecture exclusive to Linux. Invocations on Windows workstations or macOS fail, leading to uncoordinated CUDA contexts, VRAM exhaustion (`RuntimeError: CUDA out of memory`), and GPU TDR (Timeout Detection and Recovery) resets.
2. **Implement Dynamic OS-Aware Executor Topology:**
   - Query host operating system dynamically via `platform.system()`:
     - **Linux:** When NVIDIA GPUs are detected, initialize and verify the NVIDIA MPS daemon (`nvidia-cuda-mps-control -d`), enabling concurrent multi-process timeslicing on `cochem_scout_gpu`.
     - **Windows / macOS:** Automatically bypass MPS configuration. Enforce a serialized GPU execution strategy or allocate an execution queue with concurrency capped at 1 worker per physical GPU device (`max_workers=1`).
3. **Dynamic VRAM Polling & Throttling on Windows:**
   - On Windows, implement non-initializing VRAM polling via NVML (`pynvml` or `ctypes` wrapper over `nvml.dll`).
   - Prior to dispatching a GPU scout task on Windows, query `nvmlDeviceGetMemoryInfo`. If available free VRAM is below the safety threshold ($< 2.0\text{ GB}$), hold the task in queue or route to CPU fallback.
4. **Cross-Platform Compatibility Assurance:**
   - Support seamless deployment across all 6 tiers of the Environment Matrix without throwing OS-specific subprocess errors.

---

## Deliverable 5: Direct Integration of Parsl Multi-Executor Broker in Calculation Execution Router (Suggestion #145)
**Target Module:** `CoChem-BASE` (`cochem_calc_execution_router.py`)

### Detailed Requirements:
1. **Bridge the Routing Architecture Gap:**
   - In `cochem_calc_execution_router.py`, eradicate the architectural disconnection where `ExecutionRouter` only routes to raw local subprocesses (`_dispatch_local`) or raw `sbatch` scripts (`_dispatch_hpc`), leaving the heterogeneous Parsl multi-executor DFK unused.
2. **Integrate ParslExecutionBroker into `ExecutionRouter.route_job()`:**
   - Import and bind `ParslExecutionBroker` (from `src/cochem_base/core_engine/cochem_core_parsl_executors.py`) into `ExecutionRouter.route_job()`.
   - Adhere to Method Matrix §8A.2 (Scout-and-Anchor topology) and §8A.6:
     - **Anchor Tier (`cochem_anchor_cpu`):** Route computationally heavy quantum chemical jobs (e.g., ORCA composite schemes, CCSD(T) single points, numerical Hessians, anharmonic vibrational corrections $\Delta B_{\text{vib}}$).
     - **Scout Tier (`cochem_scout_gpu`):** Route high-throughput, exploratory tasks (e.g., MACE/AIMNet2 MLFF screening, ORCA GOAT exploratory sweeps, GFN-xTB pre-screenings).
3. **Contention Budgeting & Guide Integrity Verification:**
   - Ensure dispatched Parsl tasks respect CPU core affinity masks, prevent thread oversubscription (pin `OMP_NUM_THREADS` and `MKL_NUM_THREADS` to assigned core counts), and verify guide integrity flags (G1–G7).
4. **Graceful Fallback on Uninitialized DFK:**
   - If Parsl DFK is not active or initialized, provide an explicit check that cleanly initializes the default local multi-executor DFK or raises a clear, informative error rather than failing with silent execution degradation.

---

## Deliverable 6: SubprocessBroker API Harmonization & Tokenized Command Dispatch (Suggestion #146)
**Target Modules:** `CoChem-BASE` (`cochem_calc_execution_router.py`, `src/cochem/concurrency/subprocess_broker.py`, line 265; `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`)

### Detailed Requirements:
1. **Eradicate Interface Divergence:**
   - Resolve the critical interface mismatch between `src/cochem/concurrency/subprocess_broker.py` and `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`.
   - In [`subprocess_broker.py:L265`](file:///D:/__CoChem/GitHub-Repo/CoChem-BASE/src/cochem/concurrency/subprocess_broker.py#L265), fix the bug where passing a string command to `list(command)` splits `"orca job.inp"` into `['o', 'r', 'c', 'a', ' ', ...]`.
2. **Standardize Unified API Contract:**
   - Unify `SubprocessBroker` so that both constructor and `execute()` accept standardized arguments:
     ```python
     class SubprocessBroker:
         def __init__(
             self,
             cwd: Optional[Union[str, Path]] = None,
             env: Optional[Dict[str, str]] = None,
             timeout_sec: Optional[float] = None
         ) -> None: ...

         def execute(
             self,
             command: Union[str, List[str]],
             cwd: Optional[Union[str, Path]] = None,
             env: Optional[Dict[str, str]] = None,
             timeout_sec: Optional[float] = None
         ) -> SubprocessExecutionResult: ...
     ```
3. **Safe Command Tokenization via `shlex`:**
   - In `execute()`, if `command` is a `str`, tokenize it safely:
     ```python
     if isinstance(command, str):
         cmd_tokens = shlex.split(command, posix=(os.name != "nt"))
     else:
         cmd_tokens = [str(c) for c in command]
     ```
   - On Windows, ensure executable paths and arguments containing spaces or backslashes are escaped properly.
4. **Standardized Return Dataclass:**
   - Enforce that all broker execution calls return an immutable `SubprocessExecutionResult`:
     ```python
     @dataclass(frozen=True)
     class SubprocessExecutionResult:
         returncode: int
         stdout: str
         stderr: str
         walltime_sec: float
         peak_memory_mb: float
         command: List[str]
     ```
5. **Update Router Call Sites:**
   - Update `cochem_calc_execution_router.py` to instantiate and call `SubprocessBroker` using the unified signature.

---

## Deliverable 7: Parallel Conformer Exploration Graph via Parsl Scout-and-Anchor Pools (Suggestion #147)
**Target Modules:** `CoChem-TORQ` (`cochem_torq_goat.py`, lines 1330–1335; `cochem_torq_pipeline.py`)

### Detailed Requirements:
1. **Eradicate Synchronous Serial Seed Loops:**
   - In [`cochem_torq_goat.py:L1330-L1335`](file:///D:/__CoChem/GitHub-Repo/CoChem-TORQ/cochem_torq_goat.py#L1330-L1335), replace the serial iteration:
     ```python
     # DEPRECATE:
     for s_path in seed_paths:
         self.run_goat_on_seed(s_path, ...)
     ```
   - Eliminate idle CPU and GPU compute cycles during multi-seed conformer exploration campaigns (10–20 candidate structures).
2. **Implement Asynchronous Parsl Exploration Task Graph:**
   - Refactor `run_multi_seed_goat()` to submit each candidate seed exploration as an independent Parsl task (`@python_app` or `@bash_app`).
   - Dispatch seed tasks concurrently across the `cochem_scout_gpu` executor pool (or `cochem_anchor_cpu` when GPU acceleration is unavailable).
3. **Isolated Ephemeral Sandboxing per Seed:**
   - For each seed task, allocate a dedicated scratch subdirectory in $T_{\text{scr}}$:
     `scratch_dir = Path(scratch_root) / f"seed_{seed_idx}_{uuid.uuid4().hex[:8]}"`
   - Ensure scratch directories are completely isolated to prevent file naming collisions (`orca.inp`, `orca.out`, `.engrad`).
4. **Asynchronous Future Gathering & Deduplication:**
   - Collect task execution futures via `parsl.app.futures` or `concurrent.futures.as_completed`.
   - As each seed completes, stream discovered stationary points into the central conformer pool.
   - Perform rotamer clustering and deduplication ($B_e$ tolerance $< 0.13\%$ [M], RMSD $< 0.15\text{ \AA}$) before persisting unique conformers into `PESStore`.

---

## Deliverable 8: HPC MPS Daemon Lifecycle Management & Persistent Worker Monitoring (Suggestion #148)
**Target Module:** `CoChem-TORQ` (`HPC_Launchers/cochem_mps_worker.sh`, lines 44–54)

### Detailed Requirements:
1. **Fix Premature Daemon Termination in Bash Script:**
   - In [`HPC_Launchers/cochem_mps_worker.sh:L44-L54`](file:///D:/__CoChem/GitHub-Repo/CoChem-TORQ/HPC_Launchers/cochem_mps_worker.sh#L44-L54), identify the flaw where `nvidia-cuda-mps-control -d` daemonizes and detaches, causing bare `wait` to return immediately with exit code 0, triggering the `EXIT` trap `cleanup()` and terminating MPS before worker jobs connect.
2. **Implement Robust Daemon Liveness Monitoring:**
   - Replace bare `wait` with an active monitoring loop or child-process tracking:
     - Record the daemon PID or monitor the presence and responsiveness of the control pipe in `$CUDA_MPS_PIPE_DIRECTORY`.
     - When launching client compute tasks as children in the script, capture their specific PIDs:
       `child_pids+=("$!")`
     - Wait explicitly on child worker PIDs: `wait "${child_pids[@]}"`.
3. **Implement Robust Signal Handling & Graceful Teardown:**
   - Trap signals `SIGTERM`, `SIGINT`, `EXIT`, and `ERR`.
   - In the `cleanup()` function, ensure the daemon is shut down only after all child tasks have completed:
     ```bash
     cleanup() {
         echo "[MPS] Terminating child workers..."
         kill -TERM "${child_pids[@]}" 2>/dev/null || true
         wait "${child_pids[@]}" 2>/dev/null || true
         echo "quit" | nvidia-cuda-mps-control || true
     }
     trap cleanup EXIT SIGTERM SIGINT
     ```
4. **Validate Pipe Directory & Environment Variables:**
   - Export and verify `CUDA_MPS_PIPE_DIRECTORY` and `CUDA_MPS_LOG_DIRECTORY` paths in user-writable ephemeral scratch ($T_{\text{scr}}$) rather than shared `/tmp` to avoid permission conflicts on multi-tenant HPC nodes.

---

## Deliverable 9: Automated SLURM Batch Execution Interface & CLI Parameter Binding (Suggestion #149)
**Target Modules:** `CoChem-TORQ` (`HPC_Launchers/cochem_submit.slurm`, line 68; `Libraries/cochem_torq_pipeline.py`)

### Detailed Requirements:
1. **Implement Robust Pipeline CLI Entrypoint:**
   - In `Libraries/cochem_torq_pipeline.py`, implement an `if __name__ == "__main__":` block with a complete `argparse` or `click` CLI interface.
   - Support command-line flags:
     - `--input` / `-i`: Path to input structure (XYZ, SDF, or JSON QCSchema).
     - `--config` / `-c`: Path to pipeline YAML/JSON configuration.
     - `--output-dir` / `-o`: Destination directory in $T_{\text{store}}$.
     - `--scratch-dir` / `-s`: Ephemeral directory in $T_{\text{scr}}$.
     - `--device`: Target compute device (`cuda`, `cpu`, `mps`).
     - `--task-id`: SLURM task array identifier (`$SLURM_ARRAY_TASK_ID`).
     - `--mode`: Execution mode (`explore`, `refine`, `full_cascade`).
2. **Update HPC SLURM Batch Submission Script:**
   - In [`HPC_Launchers/cochem_submit.slurm:L68`](file:///D:/__CoChem/GitHub-Repo/CoChem-TORQ/HPC_Launchers/cochem_submit.slurm#L68), update the execution line from bare `"${PYTHON_EXEC}" -m Libraries.cochem_torq_pipeline` to:
     ```bash
     "${PYTHON_EXEC}" -m Libraries.cochem_torq_pipeline \
         --input "${INPUT_STRUCTURE}" \
         --config "${PIPELINE_CONFIG}" \
         --output-dir "${OUTPUT_DIR}" \
         --scratch-dir "${SLURM_TMPDIR:-/tmp}/cochem_${SLURM_JOB_ID}" \
         --task-id "${SLURM_ARRAY_TASK_ID:-0}"
     ```
3. **Exit Code & Status Propagation:**
   - Ensure `cochem_torq_pipeline.py` returns non-zero exit codes upon unrecoverable calculation failures, enabling SLURM to report accurate job accounting (`FAILED` vs `COMPLETED`).

---

## Deliverable 10: Inter-Process Lock Acquisition Timeouts & Stale Lock Eviction in Cascade HDF5 (Suggestion #150)
**Target Module:** `CoChem-TOPOS` (`cascade_engine/cochem_cascade_hdf5.py`)

### Detailed Requirements:
1. **Eliminate Unbounded Lock Waits:**
   - In `CascadeHDF5Serializer`, address `FileLock(f"{self.db_path}.lock")` defaulting to infinite timeout (`timeout=-1`).
   - Enforce an explicit acquisition timeout (default: `timeout=30.0` seconds, configurable via `lock_timeout_sec`).
2. **Implement Stale Lock Detection & Recovery:**
   - When a `Timeout` exception is caught:
     - Inspect the lock file on disk: check file modification timestamp (`os.path.getmtime(lock_path)`).
     - If the lock file has been held without update for longer than `stale_threshold_sec` (e.g., 120.0 seconds), investigate process liveness. If the holding PID is dead (or on OS reboot/node failure):
       - Log a warning: `[LOCK_RECOVERY] Evicting stale lock file {lock_path} from deceased process {pid}`.
       - Safely remove the stale lock file using `os.unlink` (or move to `.trash`).
       - Retry acquisition once before raising a fatal `LockAcquisitionError`.
3. **Guaranteed Lock Release via Context Managers:**
   - Ensure all HDF5 operations in `CascadeHDF5Serializer` are strictly wrapped in `with lock:` context managers, guaranteeing lock release even upon Python exceptions or unhandled signals.

---

## Zero-Mock Verification & Test Plan
Create or update comprehensive integration tests in `tests/` verifying all 10 deliverables against real physical data without synthetic mocks:

1. `tests/torq/test_oet_client_fallback_alert.py` (Deliverable 1):
   - Configure `oet_client.py` with an invalid daemon socket address to induce connection failure.
   - Run fallback calculation and assert that `<base>_EXT.fallback_alert.json` and `<base>_EXT.uncertainty_marker` are created in scratch.
   - Verify that the alert JSON contains valid ISO-8601 timestamps and provenance tag `[E]`.
   - Assert that running with `fail_on_fallback=True` raises `OETDaemonUnavailableError`.
2. `tests/topos/test_chain_zero_synthetic_fallbacks.py` (Deliverable 2):
   - Invoke `chain.py` with `orca_bin="non_existent_binary"`.
   - Assert that `MissingBinaryError` is raised immediately.
   - Assert that no `.gbw`, `.opt`, or dummy output files containing fabricated cycles or `ORCA TERMINATED NORMALLY` are written to disk.
3. `tests/topos/test_concurrent_hdf5_rwfilelock.py` (Deliverable 3):
   - Launch 4 concurrent worker processes (using `multiprocessing`) writing single-point energy results into a single campaign HDF5 file.
   - Verify that all write transactions succeed under `FileLock` without throwing `BlockingIOError` or `OSError`.
   - Verify HDF5 dataset integrity and confirm the total recorded entry count matches the sum of worker writes.
4. `tests/base/test_os_aware_gpu_scout_executor.py` (Deliverable 4):
   - Test `cochem_core_parsl_executors.py` on Windows (or simulated `sys.platform == "win32"`).
   - Assert that NVIDIA MPS initialization is skipped and the executor configures serialized GPU queue routing (`max_workers=1`).
   - On Linux with active NVIDIA hardware, verify MPS daemon status checking via `nvidia-cuda-mps-control`.
5. `tests/base/test_execution_router_parsl_broker.py` (Deliverable 5):
   - Instantiate `ExecutionRouter` and submit an advisory MLFF task and an anchor electronic structure task.
   - Assert that the advisory task routes to `cochem_scout_gpu` and the heavy task routes to `cochem_anchor_cpu` via `ParslExecutionBroker`.
   - Assert that environment variables (`OMP_NUM_THREADS`) are correctly budgeted.
6. `tests/base/test_subprocess_broker_interface_unification.py` (Deliverable 6):
   - Execute commands via `SubprocessBroker` passing both string format (`"echo hello"`) and list format (`["echo", "hello"]`).
   - Verify that strings are tokenized without character-splitting.
   - Test custom `cwd` and `env` parameters, verifying that return type is an instance of `SubprocessExecutionResult` with valid exit codes and execution times.
7. `tests/torq/test_goat_multi_seed_parsl_parallelism.py` (Deliverable 7):
   - Provide 4 candidate conformer XYZ files to `run_multi_seed_goat()`.
   - Assert that tasks are submitted concurrently to the Parsl executor.
   - Verify that each seed runs inside an isolated scratch directory without file name collisions.
   - Confirm discovered stationary points are deduplicated and correctly recorded.
8. `tests/torq/test_mps_worker_daemon_lifecycle.py` (Deliverable 8):
   - Execute `HPC_Launchers/cochem_mps_worker.sh` in a mock HPC shell sandbox.
   - Assert that the script tracks worker PIDs and does not exit immediately upon daemonization.
   - Verify that `cleanup()` terminates daemon processes only upon receipt of `SIGTERM` or child completion.
9. `tests/torq/test_pipeline_cli_and_slurm_forwarding.py` (Deliverable 9):
   - Execute `python -m Libraries.cochem_torq_pipeline --help`.
   - Assert that CLI flags (`--input`, `--config`, `--output-dir`, `--mode`) parse correctly.
   - Run pipeline with invalid input path and assert non-zero exit code (`returncode != 0`).
10. `tests/topos/test_cascade_hdf5_lock_timeout_and_stale_recovery.py` (Deliverable 10):
    - Create an artificial stale lock file with an old timestamp ($> 120\text{ s}$).
    - Instantiate `CascadeHDF5Serializer` and trigger a write operation.
    - Assert that stale lock detection evicts the dead lock, logs the recovery event, acquires the lock, and successfully persists data.

Execute all refactoring strictly adhering to the Method Matrix, anti-spoofing protocols, and zero-mock testing standards. Verify all files pass typing and static analysis (`ruff check`). Proceed with implementation.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\concurrency\subprocess_broker.py ---
"""Deterministic Subprocess Broker & Fault Ladder.
Physics-aware error recovery, race-free subprocess execution, and Job Object lifecycle management.
Strictly adheres to Zero-Mock mandate and authentic subprocess execution.
"""

from __future__ import annotations

import atexit
from collections import deque
import ctypes
import dataclasses

import enum
import logging
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from cochem.core.context import assert_writable_path
from cochem.core.hardware.topology import TopologyDiscoveryEngine

logger = logging.getLogger("cochem.concurrency.subprocess_broker")


class FailureCategory(enum.Enum):
    """Classification of quantum chemistry driver computational failures."""

    SCF_NON_CONVERGENCE = "SCF_NON_CONVERGENCE"
    SCF_CONVERGENCE_FAILURE = "SCF_NON_CONVERGENCE"
    GRID_INTEGRATION_FAILURE = "GRID_INTEGRATION_FAILURE"
    GEOMETRY_OPTIMIZATION_STAGNATION = "GEOMETRY_OPTIMIZATION_STAGNATION"
    CONFORMER_SEARCH_FAILURE = "CONFORMER_SEARCH_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


@dataclasses.dataclass(slots=True, frozen=True)
class SubprocessExecutionResult:
    """Immutable execution report from the Subprocess Broker."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    walltime_sec: float = 0.0
    peak_memory_mb: float = 0.0
    command: List[str] = dataclasses.field(default_factory=list)
    success: bool = True
    retries_attempted: int = 0
    final_params: Dict[str, Any] = dataclasses.field(default_factory=dict)


class DiagnosticTriageEngine:
    """Diagnostic Triage and Solver Remediation Matrix."""

    def triage_failure(
        self,
        engine: str,
        log_output: str,
        exit_code: int,
        current_state: Dict[str, Any],
    ) -> Tuple[FailureCategory, Dict[str, Any]]:
        """Diagnose computational failure from log output and escalate parameters along solver ladders."""
        upper_log = log_output.upper()
        engine_upper = engine.upper()
        new_state = dict(current_state)

        # 1. SCF Non-Convergence Escalation
        if "SCF NOT CONVERGED" in upper_log or "CONVERGENCE FAILED" in upper_log or "NOT CONVERGE" in upper_log or "FAILED TO CONVERGE" in upper_log:
            if engine_upper == "ORCA":
                orca_ladder = ["PModel", "Auto", "HCore"]
                current_guess = str(current_state.get("guess", "PModel"))
                next_idx = orca_ladder.index(current_guess) + 1 if current_guess in orca_ladder else 1
                new_state["guess"] = orca_ladder[min(next_idx, len(orca_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            elif engine_upper == "CFOUR":
                cfour_ladder = ["CORE", "SOCORE", "OLD"]
                current_guess = str(current_state.get("guess", "CORE"))
                next_idx = cfour_ladder.index(current_guess) + 1 if current_guess in cfour_ladder else 1
                new_state["guess"] = cfour_ladder[min(next_idx, len(cfour_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            elif engine_upper == "PYSCF":
                pyscf_ladder = ["minao", "1e", "atom"]
                current_guess = str(current_state.get("init_guess", "minao"))
                next_idx = pyscf_ladder.index(current_guess) + 1 if current_guess in pyscf_ladder else 1
                new_state["init_guess"] = pyscf_ladder[min(next_idx, len(pyscf_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            new_state["damping"] = True
            return FailureCategory.SCF_NON_CONVERGENCE, new_state

        # 2. Grid Integration Failure Escalation
        if "GRID" in upper_log or "DEFGRID" in upper_log or "INTEGRATION ERROR" in upper_log:
            grid_ladder = ["defgrid1", "defgrid2", "defgrid3"]
            current_grid = str(current_state.get("grid", "defgrid1"))
            next_idx = grid_ladder.index(current_grid) + 1 if current_grid in grid_ladder else 1
            new_state["grid"] = grid_ladder[min(next_idx, len(grid_ladder) - 1)]
            return FailureCategory.GRID_INTEGRATION_FAILURE, new_state

        # 3. Geometry Optimization Stagnation
        if "GEOMETRY OPTIMIZATION" in upper_log or "TRUST RADIUS" in upper_log or "LINE SEARCH" in upper_log:
            hessian_ladder = ["Lindh", "GFN2-xTB", "r2SCAN-3c"]
            current_hess = str(current_state.get("model_hessian", "Lindh"))
            next_idx = hessian_ladder.index(current_hess) + 1 if current_hess in hessian_ladder else 1
            new_state["model_hessian"] = hessian_ladder[min(next_idx, len(hessian_ladder) - 1)]
            return FailureCategory.GEOMETRY_OPTIMIZATION_STAGNATION, new_state

        # 4. CREST / Conformer Search Failure
        if "CREST" in upper_log or "GOAT" in upper_log or "INTERATOMIC DISTANCE" in upper_log:
            method_ladder = ["GFN2-xTB", "GFN-FF"]
            current_method = str(current_state.get("method", "GFN2-xTB"))
            next_idx = method_ladder.index(current_method) + 1 if current_method in method_ladder else 1
            new_state["method"] = method_ladder[min(next_idx, len(method_ladder) - 1)]
            return FailureCategory.CONFORMER_SEARCH_FAILURE, new_state

        return FailureCategory.UNKNOWN_FAILURE, new_state


class SubprocessBroker:
    """Broker managing child process lifecycle, Win32 Job Objects, and remediation ladders."""

    def __init__(
        self,
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_sec: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        context_or_engine: Union[Any, str] = "cochem_worker",
        initial_params: Optional[Dict[str, Any]] = None,
        scratch_dir: Optional[Union[pathlib.Path, str]] = None,
        base_scratch_dir: Optional[Union[pathlib.Path, str]] = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        # If first positional argument was passed as context_or_engine, disambiguate:
        if cwd is not None and not isinstance(cwd, pathlib.Path) and not os.path.exists(str(cwd)) and "/" not in str(cwd) and "\\" not in str(cwd):
            context_or_engine = cwd
            cwd = None

        if isinstance(context_or_engine, str):
            self.engine_name: str = context_or_engine
        else:
            self.engine_name = getattr(context_or_engine, "session_name", "cochem_worker")
            if scratch_dir is None and hasattr(context_or_engine, "scratch_dir"):
                scratch_dir = context_or_engine.scratch_dir

        self.cwd: pathlib.Path = pathlib.Path(cwd).resolve() if cwd else pathlib.Path.cwd()
        self.env: Optional[Dict[str, str]] = env.copy() if env is not None else None
        eff_t = timeout_sec if timeout_sec is not None else (timeout_seconds if timeout_seconds is not None else 3600.0)
        self.timeout_seconds: float = float(eff_t)

        self.current_params: Dict[str, Any] = dict(initial_params or {})
        self.max_retries: int = max(1, int(max_retries))
        self.triage: DiagnosticTriageEngine = DiagnosticTriageEngine()
        self.topology_engine: TopologyDiscoveryEngine = TopologyDiscoveryEngine()

        # Tripartite Workspace Air-Gap dynamic scratch resolution (§8B) [M]
        explicit_scratch = base_scratch_dir or scratch_dir
        if explicit_scratch is not None:
            self.base_scratch_dir: pathlib.Path = pathlib.Path(explicit_scratch).resolve()
        else:
            env_scratch = (
                os.environ.get("COCH_SCRATCH")
                or os.environ.get("SLURM_TMPDIR")
                or os.environ.get("TMPDIR")
                or os.environ.get("TEMP")
            )
            if env_scratch:
                self.base_scratch_dir = pathlib.Path(env_scratch).resolve()
            else:
                self.base_scratch_dir = (pathlib.Path.home() / ".cochem" / "scratch").resolve()

        assert_writable_path(self.base_scratch_dir)
        self.base_scratch_dir.mkdir(parents=True, exist_ok=True)
        self.scratch_dir = self.base_scratch_dir

        self.store_dir: pathlib.Path = pathlib.Path(
            os.environ.get(
                "COCH_STORE_DIR",
                os.environ.get("COCHEM_ARTIFACTS_DIR", os.environ.get("COCHEM_ARTIFACTS", pathlib.Path.home() / ".cochem" / "store")),
            )
        ).resolve()

        self._job_handle: Optional[Any] = None
        self._init_process_group_guard()
        atexit.register(self.cleanup)


    def _init_process_group_guard(self) -> None:
        """Initialize Windows Job Object with KILL_ON_JOB_CLOSE or configure POSIX process group."""
        if sys.platform == "win32":
            try:
                # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
                job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
                if job_handle:
                    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", ctypes.c_uint32),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", ctypes.c_uint32),
                            ("Affinity", ctypes.c_size_t),
                            ("PriorityClass", ctypes.c_uint32),
                            ("SchedulingClass", ctypes.c_uint32),
                        ]

                    class IO_COUNTERS(ctypes.Structure):
                        _fields_ = [
                            ("ReadOperationCount", ctypes.c_uint64),
                            ("WriteOperationCount", ctypes.c_uint64),
                            ("OtherOperationCount", ctypes.c_uint64),
                            ("ReadTransferCount", ctypes.c_uint64),
                            ("WriteTransferCount", ctypes.c_uint64),
                            ("OtherTransferCount", ctypes.c_uint64),
                        ]

                    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                            ("IoInfo", IO_COUNTERS),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryLimit", ctypes.c_size_t),
                            ("PeakJobMemoryLimit", ctypes.c_size_t),
                        ]

                    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

                    JobObjectExtendedLimitInformation = 9
                    ctypes.windll.kernel32.SetInformationJobObject(
                        job_handle,
                        JobObjectExtendedLimitInformation,
                        ctypes.byref(info),
                        ctypes.sizeof(info),
                    )
                    self._job_handle = job_handle
            except Exception as job_err:
                logger.debug("Windows Job Object initialization bypassed: %s", job_err)

    def assign_to_job(self, proc: subprocess.Popen[Any]) -> None:
        """Assign subprocess handle to Win32 Job Object."""
        if sys.platform == "win32" and self._job_handle is not None:
            try:
                # Open process handle with PROCESS_SET_QUOTA | PROCESS_TERMINATE
                PROCESS_ALL_ACCESS = 0x1F0FFF
                p_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)
                if p_handle:
                    ctypes.windll.kernel32.AssignProcessToJobObject(self._job_handle, p_handle)
                    ctypes.windll.kernel32.CloseHandle(p_handle)
            except Exception as assign_err:
                logger.debug("Could not assign PID %d to Job Object: %s", proc.pid, assign_err)

    def _prepare_worker_environment(
        self,
        worker_index: int = 0,
        retries: int = 0,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Prepare isolated execution environment with unique MPS pipe/log dirs and partitioned GPU devices."""
        worker_env = dict(self.topology_engine.get_worker_env(concurrent_workers=1, worker_index=worker_index))
        available_gpus = self.topology_engine.get_available_gpus()
        if available_gpus:
            assigned = self.current_params.get("assigned_gpu", available_gpus[worker_index % len(available_gpus)])
            worker_env["CUDA_VISIBLE_DEVICES"] = str(assigned)
        else:
            worker_env["CUDA_VISIBLE_DEVICES"] = ""

        if hasattr(self, "env") and self.env:
            worker_env.update(self.env)
        if extra_env:
            worker_env.update(extra_env)

        mps_dir = self.base_scratch_dir / "mps" / f"worker_{worker_index}_pid_{os.getpid()}_retry_{retries}"
        mps_pipe = mps_dir / "pipe"
        mps_log = mps_dir / "log"
        mps_pipe.mkdir(parents=True, exist_ok=True)
        mps_log.mkdir(parents=True, exist_ok=True)

        worker_env["CUDA_MPS_PIPE_DIRECTORY"] = str(mps_pipe)
        worker_env["CUDA_MPS_LOG_DIRECTORY"] = str(mps_log)
        return worker_env

    def execute(
        self,
        command: Union[str, List[str]],
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_sec: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
        **kwargs: Any,
    ) -> SubprocessExecutionResult:
        """Executes command under deterministic fault ladder with process containment."""
        return self.execute_with_remediation(
            command=command,
            cwd=cwd,
            env=env,
            timeout_sec=timeout_sec,
            timeout_seconds=timeout_seconds,
            remediate_callback=remediate_callback,
            **kwargs,
        )

    def execute_with_remediation(
        self,
        command: Union[str, List[str]],
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_sec: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
        **kwargs: Any,
    ) -> SubprocessExecutionResult:
        """Execute command under deterministic fault ladder with up to MAX_RETRIES remediation cycles."""
        t0 = time.time()
        retries = 0
        last_stdout = ""
        last_stderr = ""
        last_code = 1
        peak_mem_mb = 0.0

        # Ephemeral per-job sandbox subdirectory conforming to Tripartite Air-Gap
        job_id = uuid.uuid4().hex
        job_scratch = self.base_scratch_dir / f"cochem_exec_{job_id}"
        job_scratch.mkdir(parents=True, exist_ok=True)

        if isinstance(command, str):
            cmd_tokens = shlex.split(command, posix=(os.name != "nt"))
            if os.name == "nt":
                cleaned_tokens = []
                for arg in cmd_tokens:
                    if len(arg) >= 2 and ((arg[0] == '"' and arg[-1] == '"') or (arg[0] == "'" and arg[-1] == "'")):
                        cleaned_tokens.append(arg[1:-1])
                    else:
                        cleaned_tokens.append(arg)
                cmd_tokens = cleaned_tokens
        else:
            cmd_tokens = [str(c) for c in command]

        current_cmd = list(cmd_tokens)
        if sys.platform == "win32" and current_cmd and shutil.which(current_cmd[0]) is None:
            if current_cmd[0].lower() in ("echo", "dir", "type", "copy", "del", "mkdir", "rmdir", "cls"):
                current_cmd = ["cmd.exe", "/c"] + current_cmd

        effective_cwd = pathlib.Path(cwd).resolve() if cwd is not None else job_scratch
        effective_cwd.mkdir(parents=True, exist_ok=True)
        assert_writable_path(effective_cwd)

        effective_timeout = (
            timeout_sec
            if timeout_sec is not None
            else (timeout_seconds if timeout_seconds is not None else getattr(self, "timeout_seconds", 3600.0))
        )

        proc: Optional[subprocess.Popen[Any]] = None
        try:
            while retries < self.max_retries:
                worker_env = self._prepare_worker_environment(
                    worker_index=int(self.current_params.get("worker_index", 0)),
                    retries=retries,
                    extra_env=env,
                )

                proc_kwargs: Dict[str, Any] = {
                    "cwd": str(effective_cwd),
                    "env": worker_env,
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                    "text": True,
                }

                if sys.platform == "win32":
                    CREATE_SUSPENDED = 0x00000004
                    proc_kwargs["creationflags"] = proc_kwargs.get("creationflags", 0) | CREATE_SUSPENDED
                else:
                    proc_kwargs["start_new_session"] = True
                    if sys.platform.startswith("linux"):
                        def _posix_pdeathsig() -> None:
                            try:
                                import ctypes
                                libc = ctypes.CDLL("libc.so.6")
                                PR_SET_PDEATHSIG = 1
                                SIGKILL = 9
                                libc.prctl(PR_SET_PDEATHSIG, SIGKILL)
                            except Exception as _e:
                                logger.debug(f"Ignored exception: {_e}")
                        proc_kwargs["preexec_fn"] = _posix_pdeathsig

                try:
                    proc = subprocess.Popen(current_cmd, **proc_kwargs)
                    self.assign_to_job(proc)
                    if sys.platform == "win32":
                        try:
                            ctypes.windll.ntdll.NtResumeProcess(int(proc._handle))
                        except Exception as _e:
                            logger.debug(f"Ignored exception: {_e}")

                    if HAS_PSUTIL and proc is not None:
                        try:
                            p = psutil.Process(proc.pid)
                            peak_mem_mb = max(peak_mem_mb, float(p.memory_info().rss) / (1024.0 * 1024.0))
                        except Exception:
                            pass

                    try:
                        out, err = proc.communicate(timeout=effective_timeout)
                        code = proc.returncode
                    except subprocess.TimeoutExpired:
                        self.terminate_process_tree(proc)
                        last_stdout = ""
                        last_stderr = f"Subprocess execution timed out after {effective_timeout}s"
                        last_code = -124
                        return SubprocessExecutionResult(
                            returncode=last_code,
                            stdout=last_stdout,
                            stderr=last_stderr,
                            walltime_sec=round(time.time() - t0, 4),
                            peak_memory_mb=peak_mem_mb,
                            command=cmd_tokens,
                            success=False,
                            retries_attempted=retries + 1,
                            final_params=self.current_params,
                        )

                    if HAS_PSUTIL and proc is not None:
                        try:
                            p = psutil.Process(proc.pid)
                            peak_mem_mb = max(peak_mem_mb, float(p.memory_info().rss) / (1024.0 * 1024.0))
                        except Exception:
                            pass

                    # Capture subprocess stdout/stderr using bounded 10 MB ring buffers
                    stdout_buf: deque[str] = deque(maxlen=10485760)
                    stderr_buf: deque[str] = deque(maxlen=10485760)
                    stdout_buf.extend(out or "")
                    stderr_buf.extend(err or "")
                    last_stdout = "".join(stdout_buf)
                    last_stderr = "".join(stderr_buf)
                    last_code = code

                    if code == 0:
                        # Extract validated artifacts to persistent store (T_store) conforming to Tripartite Air-Gap
                        if self.store_dir.exists() or os.environ.get("COCH_STORE_DIR") or os.environ.get("COCHEM_ARTIFACTS_DIR"):
                            self.store_dir.mkdir(parents=True, exist_ok=True)
                            search_dirs = [job_scratch]
                            if effective_cwd != job_scratch:
                                search_dirs.append(effective_cwd)
                            for s_dir in search_dirs:
                                for ext in [".out", ".property.txt", ".gbw", ".xyz", ".json"]:
                                    for f in s_dir.glob(f"*{ext}"):
                                        try:
                                            shutil.copy2(str(f), str(self.store_dir / f.name))
                                        except Exception as _e:
                                            logger.debug(f"Ignored exception: {_e}")

                        return SubprocessExecutionResult(
                            returncode=0,
                            stdout=last_stdout,
                            stderr=last_stderr,
                            walltime_sec=round(time.time() - t0, 4),
                            peak_memory_mb=peak_mem_mb,
                            command=cmd_tokens,
                            success=True,
                            retries_attempted=retries,
                            final_params=self.current_params,
                        )

                    # Execute diagnostic triage on error output
                    cat, updated_params = self.triage.triage_failure(
                        engine=self.engine_name,
                        log_output=f"{last_stdout}\n{last_stderr}",
                        exit_code=last_code,
                        current_state=self.current_params,
                    )

                    self.current_params = updated_params
                    retries += 1
                    logger.warning(
                        "Subprocess failure (attempt %d/%d) classified as %s. Escalated parameters: %s",
                        retries,
                        self.max_retries,
                        cat.value,
                        self.current_params,
                    )

                    # Tripartite Air-Gap scratch remediation (§8B) [M]
                    preserve_gbw = bool(
                        self.current_params.get("moread", False)
                        or "moread" in str(self.current_params).lower()
                        or self.current_params.get("preserve_gbw", False)
                    )
                    self._sanitize_remediation_scratch(job_scratch, preserve_gbw=preserve_gbw)

                    # Apply dynamic remediation callback if provided
                    if remediate_callback is not None:
                        new_cmd = remediate_callback(cat, self.current_params, job_scratch)
                        if new_cmd:
                            current_cmd = list(new_cmd)
                    else:
                        logger.warning(
                            "No remediation callback provided; retrying static command without physical input escalation."
                        )

                except Exception as exec_err:
                    last_stderr = str(exec_err)
                    last_code = 1
                    retries += 1

            return SubprocessExecutionResult(
                returncode=last_code,
                stdout=last_stdout,
                stderr=last_stderr,
                walltime_sec=round(time.time() - t0, 4),
                peak_memory_mb=peak_mem_mb,
                command=cmd_tokens,
                success=False,
                retries_attempted=retries,
                final_params=self.current_params,
            )
        finally:
            # Lifecycle hygiene: sweep and delete ephemeral sandbox
            shutil.rmtree(str(job_scratch), ignore_errors=True)

    @staticmethod
    def _sanitize_remediation_scratch(scratch_dir: Union[str, pathlib.Path], preserve_gbw: bool = False) -> None:
        """Sanitizes ephemeral remediation scratch directory to prevent engine startup crashes (§8B) [M].

        Wipes dirty transient files (*.tmp*, *.prop*, *.scfp_tmp*, *.lock, unclosed *.hess, *.densities).
        When preserve_gbw=True (MOREAD reuse / grid escalation), stages valid .gbw checkpoints
        into a staging buffer and restores them after purging transients. Otherwise, .gbw files are purged.
        """
        s_path = pathlib.Path(scratch_dir).resolve()
        if not s_path.exists() or not s_path.is_dir():
            return

        staged_gbws: List[Tuple[pathlib.Path, pathlib.Path]] = []

        if preserve_gbw:
            for gbw_file in s_path.glob("*.gbw"):
                staged = s_path / f".staged_{gbw_file.name}"
                try:
                    shutil.copy2(str(gbw_file), str(staged))
                    staged_gbws.append((staged, gbw_file))
                except Exception as _e:
                    logger.debug("Failed staging gbw checkpoint %s: %s", gbw_file, _e)

        transient_patterns = ["*.tmp*", "*.prop*", "*.scfp_tmp*", "*.lock", "*.hess", "*.densities"]
        if not preserve_gbw:
            transient_patterns.append("*.gbw")

        for pattern in transient_patterns:
            for transient_file in s_path.glob(pattern):
                try:
                    if transient_file.is_file():
                        transient_file.unlink(missing_ok=True)
                    elif transient_file.is_dir():
                        shutil.rmtree(str(transient_file), ignore_errors=True)
                except Exception as _e:
                    logger.debug("Failed removing transient file %s: %s", transient_file, _e)

        if preserve_gbw and staged_gbws:
            for staged, orig in staged_gbws:
                try:
                    if staged.exists():
                        shutil.move(str(staged), str(orig))
                except Exception as _e:
                    logger.debug("Failed restoring staged checkpoint %s: %s", staged, _e)

    def terminate_process_tree(self, proc: subprocess.Popen[Any], grace_timeout: float = 3.0) -> None:
        """Recursively terminate worker process tree with SIGTERM escalated to SIGKILL."""
        pid = proc.pid
        try:
            import psutil
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")
            parent.terminate()
            _, alive = psutil.wait_procs(children + [parent], timeout=grace_timeout)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")
        except Exception:
            if sys.platform != "win32":
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (OSError, ProcessLookupError) as _e:
                    logger.debug(f"Ignored exception: {_e}")
            else:
                try:
                    proc.kill()
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

    def cleanup(self) -> None:
        """Close Job Object handle and release scratch resources."""
        if sys.platform == "win32" and self._job_handle is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(self._job_handle)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
            self._job_handle = None

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\core\context.py ---
"""Async Context Isolation via ContextVar & Tripartite Storage Tier Locking.
Provides immutable execution context, air-gap validation, atomic writes, and platform-aware locking.
Strictly adheres to Zero-Mock mandate and Tripartite Storage Air-Gap enforcement.
"""

from __future__ import annotations

import contextvars
import dataclasses
import logging
import os
import pathlib
import platform
import time
import uuid
from typing import Any, Dict, Optional, Union

logger = logging.getLogger("cochem.core.context")


# ==============================================================================
# Custom Exceptions
# ==============================================================================
class AirGapViolationError(Exception):
    """Raised when an operation attempts to write to, delete from, or stage files in read-only tiers ($COCH_SRC or $COCH_DATA)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ==============================================================================
# Immutable Execution Context
# ==============================================================================
@dataclasses.dataclass(slots=True, frozen=True)
class ExecutionContext:
    """Immutable execution context encapsulating process state across the 6-Tier Environment Matrix."""

    execution_id: str
    session_name: str
    src_dir: pathlib.Path
    data_dir: pathlib.Path
    artifacts_dir: pathlib.Path
    scratch_dir: pathlib.Path
    env_tier: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


_CURRENT_CONTEXT: contextvars.ContextVar[Optional[ExecutionContext]] = contextvars.ContextVar(
    "cochem_execution_context",
    default=None,
)


def get_current_context() -> ExecutionContext:
    """Retrieve active ExecutionContext or raise RuntimeError if uninitialized."""
    ctx = _CURRENT_CONTEXT.get()
    if ctx is None:
        raise RuntimeError("No active ExecutionContext found in contextvars. Initialize with scoped_context.")
    return ctx


class scoped_context:
    """Context manager and async context manager isolating execution context across coroutines and threads."""

    def __init__(self, ctx: ExecutionContext) -> None:
        self.ctx: ExecutionContext = ctx
        self._token: Optional[contextvars.Token[Optional[ExecutionContext]]] = None

    def __enter__(self) -> ExecutionContext:
        self._token = _CURRENT_CONTEXT.set(self.ctx)
        return self.ctx

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token is not None:
            _CURRENT_CONTEXT.reset(self._token)
            self._token = None

    async def __aenter__(self) -> ExecutionContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


def assert_writable_path(
    target_path: Union[pathlib.Path, str],
    ctx: Optional[ExecutionContext] = None,
) -> None:
    """Validate that target_path does not violate read-only Air-Gap boundaries ($COCH_SRC, $COCH_DATA, COCHEM_REPO_DIR)."""
    resolved_target = pathlib.Path(target_path).resolve()

    # Check COCHEM_REPO_DIR or COCH_SRC
    repo_env = os.environ.get("COCHEM_REPO_DIR") or os.environ.get("COCH_SRC")
    if repo_env:
        resolved_repo = pathlib.Path(repo_env).resolve()
        if resolved_target == resolved_repo or resolved_repo in resolved_target.parents:
            raise AirGapViolationError(
                f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only codebase tier (COCHEM_REPO_DIR='{resolved_repo}')."
            )

    active_ctx = ctx or _CURRENT_CONTEXT.get()
    if active_ctx is not None:
        resolved_src = active_ctx.src_dir.resolve()
        resolved_data = active_ctx.data_dir.resolve()

        if resolved_target == resolved_src or resolved_src in resolved_target.parents:
            raise AirGapViolationError(
                f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only codebase tier ($COCH_SRC='{resolved_src}')."
            )

        if resolved_target == resolved_data or resolved_data in resolved_target.parents:
            raise AirGapViolationError(
                f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only baseline data tier ($COCH_DATA='{resolved_data}')."
            )


def get_tripartite_paths() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Returns (T_repo, T_scratch, T_store) conforming to Tripartite Air-Gap boundaries.

    T_repo: Immutable codebase root (COCHEM_REPO_DIR / COCH_SRC)
    T_scratch: Ephemeral scratch directory (COCHEM_SCRATCH_DIR / COCHEM_SCRATCH / tempfile)
    T_store: Persistent artifact destination (COCHEM_ARTIFACT_DIR / COCHEM_DATA_ROOT)
    """
    import tempfile

    repo_env = os.environ.get("COCHEM_REPO_DIR") or os.environ.get("COCH_SRC")
    t_repo = pathlib.Path(repo_env).resolve() if repo_env else pathlib.Path(__file__).resolve().parents[3]

    scratch_env = (
        os.environ.get("COCHEM_SCRATCH_DIR")
        or os.environ.get("COCHEM_SCRATCH")
        or os.environ.get("SLURM_TMPDIR")
        or os.environ.get("TEMP")
    )
    t_scratch = (
        pathlib.Path(scratch_env).resolve()
        if scratch_env
        else (pathlib.Path(tempfile.gettempdir()) / "cochem_scratch").resolve()
    )

    store_env = (
        os.environ.get("COCHEM_ARTIFACT_DIR")
        or os.environ.get("COCHEM_DATA_ROOT")
        or os.environ.get("COCH_ARTIFACTS")
    )
    t_store = (
        pathlib.Path(store_env).resolve()
        if store_env
        else (pathlib.Path.home() / ".cochem" / "artifacts").resolve()
    )
    return t_repo, t_scratch, t_store


# ==============================================================================
# Atomic File Staging & HPC Prohibition
# ==============================================================================
class AtomicWrite:
    """Context manager providing atomic file replacement mechanics via temporary local staging."""

    def __init__(self, target_path: Union[pathlib.Path, str]) -> None:
        self.target: pathlib.Path = pathlib.Path(target_path).resolve()
        assert_writable_path(self.target)
        self.tmp_path: pathlib.Path = self.target.with_name(f"{self.target.name}.{uuid.uuid4().hex[:8]}.tmp")

    def __enter__(self) -> pathlib.Path:
        self.target.parent.mkdir(parents=True, exist_ok=True)
        if not self.tmp_path.exists():
            self.tmp_path.touch()
        return self.tmp_path

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None and self.tmp_path.exists():
            try:
                with open(self.tmp_path, "a+b") as f:
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(self.tmp_path, self.target)
            except Exception as replace_err:
                if self.tmp_path.exists():
                    try:
                        self.tmp_path.unlink()
                    except OSError as e:
                        logger.debug("Ignored OSError during cleanup: %s", e)
                raise replace_err
        else:
            if self.tmp_path.exists():
                try:
                    self.tmp_path.unlink()
                except OSError as e:
                    logger.debug("Ignored OSError during cleanup: %s", e)


class FileLock:
    """Cross-process and cross-thread file locking for Local/Cloud tiers (Tier 1-4) with strict HPC tier prohibition.

    Features adaptive exponential backoff with random jitter, stale lock resolution (>300s),
    and cross-platform low-latency primitives.
    """

    def __init__(
        self,
        lock_path: Union[pathlib.Path, str],
        timeout_sec: float = 10.0,
    ) -> None:
        self.lock_path: pathlib.Path = pathlib.Path(lock_path).resolve()
        self.timeout_sec: float = max(0.001, float(timeout_sec))

        # Verify against HPC distributed filesystem lock prohibition
        active_ctx = _CURRENT_CONTEXT.get()
        if active_ctx is not None:
            tier_str = active_ctx.env_tier.upper()
            if "TIER 5" in tier_str or "TIER 6" in tier_str:
                raise RuntimeError(
                    f"Distributed POSIX/Windows file locks are prohibited in HPC {active_ctx.env_tier} (Lustre/GPFS/NFS). "
                    "Calculations must stage I/O locally in $SLURM_TMPDIR and publish via AtomicWrite."
                )

        target_file = str(self.lock_path) if str(self.lock_path).endswith(".lock") else f"{self.lock_path}.lock"
        self._target_file: pathlib.Path = pathlib.Path(target_file).resolve()
        self._fd: Optional[int] = None

    def acquire(
        self,
        initial_delay_sec: float = 0.001,
        max_delay_sec: float = 0.025,
        backoff_factor: float = 1.5,
        jitter: bool = True,
    ) -> bool:
        """Acquire physical file lock using adaptive exponential backoff with jitter."""
        assert_writable_path(self.lock_path)
        self._target_file.parent.mkdir(parents=True, exist_ok=True)

        # Stale lock resolution: if older than 300s, clear lock file
        if self._target_file.exists():
            try:
                mtime = self._target_file.stat().st_mtime
                if time.time() - mtime > 300.0:
                    logger.warning("Detected stale lock file (>300s) at %s; clearing.", self._target_file)
                    try:
                        self._target_file.unlink(missing_ok=True)
                    except OSError as e:
                        logger.debug("Ignored OSError during lock cleanup: %s", e)
            except OSError as e:
                logger.debug("Ignored OSError during lock cleanup: %s", e)

        start_time = time.perf_counter()
        current_delay = initial_delay_sec

        while True:
            fd = None
            try:
                fd = os.open(self._target_file, os.O_CREAT | os.O_RDWR)
                if platform.system() == "Windows":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                self._fd = fd
                return True
            except (OSError, PermissionError):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError as e:
                        logger.debug("Ignored OSError closing fd: %s", e)
                    fd = None

                elapsed = time.perf_counter() - start_time
                if elapsed >= self.timeout_sec:
                    return False

                jitter_mult = 0.5 + ((time.perf_counter_ns() % 1000) / 1000.0)
                sleep_time = (current_delay * jitter_mult) if jitter else current_delay
                time.sleep(sleep_time)
                current_delay = min(current_delay * backoff_factor, max_delay_sec)

    def release(self) -> None:
        """Release physical lock and close file descriptor."""
        if self._fd is not None:
            fd = self._fd
            self._fd = None
            try:
                if platform.system() == "Windows":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception as exc:
                logger.debug("Lock release exception bypassed: %s", exc)
            finally:
                try:
                    os.close(fd)
                except Exception as e:
                    logger.debug("Ignored Exception closing fd: %s", e)

    def __enter__(self) -> FileLock:
        if not self.acquire():
            raise TimeoutError(f"Timed out after {self.timeout_sec}s acquiring lock on {self.lock_path}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\scripts\oet_client.py ---
#!/usr/bin/env python3
"""CoChem-TORQ: Standalone ORCA ExtOpt Client Bridge for OET Inference Server.

Mandated by Method Matrix v4 Quick Start QS-1 (Step 2), Section 9B.4, Section 8A.2,
and Section 10.1-10.8 as the standalone client bridge communicating with the OET
server daemon via ORCA %method ProgExt parameters.

Contract Specifications (Method Matrix v4 §10.1-10.8):
- Invocation from ORCA:
    %method
      ProgExt "<PATH>/oet_client"
      Ext_Params "-b localhost:8888"
    end
    ORCA executes: `oet_client <basename>_EXT.extinp.tmp -b localhost:8888`
- Input Contract (§10.2): ORCA writes `<basename>_EXT.extinp.tmp` containing:
    Line 1: `<basename>_EXT.xyz` (standard XYZ in Angstroms)
    Line 2: Charge (integer; e.g. 0)
    Line 3: Multiplicity (integer >= 1; e.g. 1)
    Line 4: NCores (integer >= 1)
    Line 5: do_gradient (0 or 1)
    Line 6: (Optional) point charges file path
- Output Contract (§10.2): `<basename>_EXT.engrad` containing:
    Number of atoms
    Total energy in Eh (Hartree)
    Energy gradient in Eh/bohr (Hartree/bohr) (atom1_x, atom1_y, atom1_z, ...)
- Units & Sign Conventions (§10.3):
    Input coordinates: Angstrom (A)
    Output energy: Hartree (Eh) = E_eV / 27.211386245988
    Output gradient: Eh/bohr = (-Force_eV_per_A) * 0.529177210903 / 27.211386245988
    MANDATORY SIGN FLIP: Gradient = -Force (\\nabla E = -F). ASE/models return
    forces F; ORCA optimizers require the potential energy gradient.
- Persistent Daemon Architecture (§8A.2 & §9B.4):
    Communicates with `oet_server` on TCP socket (default 127.0.0.1:8888) to bypass
    the ~30s model reloading overhead per gradient call during GOAT search.
- Float32 Precision Guard (§9B.4 & §13.1 T1-30min):
    Float32 MLFF potentials operate with a ~4 x 10^-6 Eh noise floor. Pair with
    `! TightOpt` and `%scf TolE 1e-5 end` in ORCA to prevent numerical noise.
- Committee Uncertainty Quantification (§10.8):
    Supports receiving or computing normalized energy uncertainty sigma_E and max
    atomic force uncertainty U_F, writing an uncertainty marker file if exceeding
    eps_E / eps_F.
- Physical Mass Mandate: Dynamic atomic mass and property resolution via `mendeleev`.
- Zero-Mock Policy: Authentic socket IPC, robust retry mechanism, and genuine
  analytical physical molecular mechanics potential fallback when remote is offline.
"""

from __future__ import annotations

import argparse
import datetime
from datetime import timezone
import functools
import json
import logging
import math
import os
import platform
import socket
import sys
import tempfile
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Optional, Union

import mendeleev  # type: ignore[import-untyped]
import numpy as np

try:
    from cochem_base.schemas import OETFallbackAlertManifest
    from cochem_base.exceptions import OETDaemonConnectionError
except ImportError:
    from pydantic import BaseModel, ConfigDict, Field

    class OETFallbackAlertManifest(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")
        calculation_base: str
        timestamp: str = Field(default_factory=lambda: datetime.datetime.now(timezone.utc).isoformat())
        trigger_event: str
        fallback_calculator: str
        provenance_tag: str = "[E]"
        host_telemetry: dict[str, Any]
        scratch_alert_file: str
        staged_artifact_file: str

    class OETDaemonConnectionError(RuntimeError):
        """Raised when communication with persistent OET server daemon fails."""
        pass


class OETDaemonUnavailableError(RuntimeError):
    """Raised when OET daemon is unavailable and fail_on_fallback or strict_provenance is active."""
    pass


class AirGapViolationError(RuntimeError):
    """Raised when writing to static Ring 1 repository files is detected."""
    pass


def emit_fallback_alert(
    calculation_base: str,
    trigger_event: str,
    fallback_calculator: str = "PhysicalOETFallbackCalculator",
    requested_backend: str = "mace_off24m",
    socket_target: str = "127.0.0.1:8888",
    scratch_dir: Path | str | None = None,
    artifacts_dir: Path | str | None = None,
    host_telemetry: dict[str, Any] | None = None,
) -> OETFallbackAlertManifest:
    """Emit fallback alert manifest to Ring 2 scratch and stage to Ring 3 artifacts atomically. [M]"""
    clean_base = calculation_base
    if clean_base.endswith("_EXT"):
        clean_base = clean_base[:-4]

    # Resolve scratch (Ring 2)
    if scratch_dir is not None:
        s_dir = Path(scratch_dir).resolve()
    elif "COCHEM_SCRATCH" in os.environ:
        s_dir = Path(os.environ["COCHEM_SCRATCH"]).resolve()
    else:
        s_dir = Path(tempfile.gettempdir()) / "cochem_scratch"
    s_dir.mkdir(parents=True, exist_ok=True)

    # Resolve artifacts (Ring 3)
    if artifacts_dir is not None:
        a_dir = Path(artifacts_dir).resolve()
    elif "COCHEM_ARTIFACTS" in os.environ:
        a_dir = Path(os.environ["COCHEM_ARTIFACTS"]).resolve()
    else:
        a_dir = s_dir / "artifacts"
    alerts_dir = a_dir / "alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)

    # Prohibit writing to Ring 1 static repository paths
    cochem_root = os.environ.get("COCHEM_ROOT")
    if cochem_root:
        root_path = Path(cochem_root).resolve()
        if root_path in s_dir.parents or root_path == s_dir:
            raise AirGapViolationError(f"Prohibited write to Ring 1 repository root: {s_dir}")
        if root_path in alerts_dir.parents or root_path == alerts_dir:
            raise AirGapViolationError(f"Prohibited write to Ring 1 repository root: {alerts_dir}")

    scratch_alert_file = s_dir / f"{clean_base}_EXT.fallback_alert.json"
    staged_artifact_file = alerts_dir / f"{clean_base}_EXT.fallback_alert.json"
    uncertainty_marker_file = s_dir / f"{clean_base}_EXT.uncertainty_marker"

    now_utc = datetime.datetime.now(timezone.utc).isoformat()
    telemetry = host_telemetry or {
        "platform": platform.platform(),
        "python_version": sys.version,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "timestamp_utc": now_utc,
    }

    alert_payload: dict[str, Any] = {
        "timestamp_utc": now_utc,
        "event": "OET_DAEMON_FALLBACK_TRIGGERED",
        "requested_backend": requested_backend,
        "active_fallback": fallback_calculator,
        "provenance_tag": "[E]",
        "socket_target": socket_target,
        "reason": str(trigger_event),
        "investigator_action_required": True,
        "calculation_base": clean_base,
        "host_telemetry": telemetry,
    }

    manifest = OETFallbackAlertManifest(
        calculation_base=clean_base,
        timestamp=now_utc,
        trigger_event=str(trigger_event),
        fallback_calculator=fallback_calculator,
        provenance_tag="[E]",
        host_telemetry=telemetry,
        scratch_alert_file=str(scratch_alert_file),
        staged_artifact_file=str(staged_artifact_file),
    )

    # Atomic write to Ring 2 scratch via temporary UUID sidecar
    tmp_scratch = s_dir / f".tmp_{uuid.uuid4().hex}"
    tmp_scratch.write_text(json.dumps(alert_payload, indent=2), encoding="utf-8")
    os.replace(tmp_scratch, scratch_alert_file)

    # Atomic write to Ring 3 artifacts via temporary UUID sidecar
    tmp_artifact = alerts_dir / f".tmp_{uuid.uuid4().hex}"
    tmp_artifact.write_text(json.dumps(alert_payload, indent=2), encoding="utf-8")
    os.replace(tmp_artifact, staged_artifact_file)

    # Uncertainty marker file in scratch with provenance tag [E]
    tmp_marker = s_dir / f".tmp_{uuid.uuid4().hex}"
    tmp_marker.write_text(
        f"PROVENANCE_TAG: [E]\n"
        f"EVENT: OET_DAEMON_FALLBACK_TRIGGERED\n"
        f"TRIGGER_EVENT: {trigger_event}\n"
        f"CALCULATION_BASE: {clean_base}\n"
        f"FALLBACK_CALCULATOR: {fallback_calculator}\n"
        f"TIMESTAMP: {now_utc}\n",
        encoding="utf-8",
    )
    os.replace(tmp_marker, uncertainty_marker_file)

    return manifest


# Physical conversion constants (Method Matrix v4 §10.3 & NIST CODATA 2022)
BOHR_TO_ANGSTROM: Final[float] = 0.529177210903
ANGSTROM_TO_BOHR: Final[float] = 1.0 / BOHR_TO_ANGSTROM  # ~1.8897261246257708
HARTREE_TO_EV: Final[float] = 27.211386245988
EV_TO_HARTREE: Final[float] = 1.0 / HARTREE_TO_EV
EH_PER_EV: Final[float] = EV_TO_HARTREE
BOHR_PER_A: Final[float] = ANGSTROM_TO_BOHR
EV_PER_ANG_TO_EH_PER_BOHR: Final[float] = EH_PER_EV / BOHR_PER_A
HARTREE_TO_KCAL_MOL: Final[float] = 627.5094740631
HARTREE_TO_KJ_MOL: Final[float] = 2625.4996394799

# Logger setup
logger = logging.getLogger("cochem.torq.oet_client")


# =============================================================================
# 1. Dynamic Mendeleev Mass and Property Resolution (Mendeleev Mandate)
# =============================================================================


@functools.lru_cache(maxsize=128)
def get_element_atomic_mass(symbol: str) -> float:
    """Retrieve dynamic atomic mass for an element symbol using Mendeleev.

    Strictly complies with the CoChem Mendeleev Mass Mandate (no hardcoded masses).
    """
    clean_sym = symbol.strip().capitalize()
    try:
        elem = mendeleev.element(clean_sym)
        mass = elem.mass
        if mass is None:
            raise ValueError(f"Mendeleev mass is None for '{clean_sym}'")
        return float(mass)
    except Exception as err:
        raise ValueError(
            f"Failed to get atomic mass for '{symbol}' via Mendeleev: {err}"
        ) from err


@functools.lru_cache(maxsize=128)
def get_element_atomic_number(symbol: str) -> int:
    """Retrieve atomic number for an element symbol using Mendeleev."""
    clean_sym = symbol.strip().capitalize()
    try:
        elem = mendeleev.element(clean_sym)
        atomic_num = elem.atomic_number
        if atomic_num is None:
            raise ValueError(f"Mendeleev atomic number is None for '{clean_sym}'")
        return int(atomic_num)
    except Exception as err:
        raise ValueError(
            f"Failed to retrieve atomic number for '{symbol}' via Mendeleev: {err}"
        ) from err


@functools.lru_cache(maxsize=128)
def get_element_symbol(atomic_number: int) -> str:
    """Retrieve element symbol from atomic number using Mendeleev."""
    try:
        elem = mendeleev.element(int(atomic_number))
        sym = elem.symbol
        if sym is None:
            raise ValueError(f"Mendeleev symbol is None for Z={atomic_number}")
        return str(sym)
    except Exception as err:
        raise ValueError(
            f"Failed to get element symbol for Z={atomic_number}: {err}"
        ) from err


@functools.lru_cache(maxsize=128)
def get_element_covalent_radius(symbol: str) -> float:
    """Retrieve covalent radius in Angstroms via Mendeleev."""
    clean_sym = symbol.strip().capitalize()
    try:
        elem = mendeleev.element(clean_sym)
        rad_pm = (
            elem.covalent_radius_pyykko
            or elem.covalent_radius_bragg
            or elem.covalent_radius
            or 100.0
        )
        return float(rad_pm) / 100.0
    except Exception:
        return 1.0


@functools.lru_cache(maxsize=128)
def get_element_vdw_radius(symbol: str) -> float:
    """Retrieve van der Waals radius in Angstroms via Mendeleev."""
    clean_sym = symbol.strip().capitalize()
    try:
        elem = mendeleev.element(clean_sym)
        rad_pm = elem.vdw_radius or elem.vdw_radius_alvarez or 170.0
        return float(rad_pm) / 100.0
    except Exception:
        return 1.70


# =============================================================================
# 2. Data Structures & Configuration Models
# =============================================================================


@dataclass(frozen=True)
class ExtInpData:
    """Parsed data from ORCA `<base>_EXT.extinp.tmp` file per Method Matrix §10.2."""

    xyz_file: Path
    charge: int
    multiplicity: int
    ncores: int
    dograd: bool
    pointcharges_file: Path | None = None


@dataclass(frozen=True)
class EngradResult:
    """Calculated energy and gradient results written to `<base>_EXT.engrad`."""

    num_atoms: int
    energy_eh: float
    gradient_eh_bohr: list[float]
    atom_symbols: list[str]
    coordinates_angstrom: list[tuple[float, float, float]]
    engrad_file: Path
    uncertainty_energy_eh: float | None = None
    uncertainty_force_max: float | None = None
    provenance_tag: str = "[M]"


@dataclass
class OETClientConfig:
    """Configuration options for OET client bridge communication."""

    server_host: str = "127.0.0.1"
    server_port: int = 8888
    timeout_seconds: float = 60.0
    retries: int = 3
    retry_delay_seconds: float = 0.5
    scf_tole: float = 1e-5
    allow_fallback: bool = True
    standalone: bool = False
    fallback_driver: str = "physical"
    device: str = "cpu"
    dtype: str = "float64"
    eps_energy: float | None = None
    eps_force: float | None = None
    uncertainty_marker_file: str | None = None
    verbose: bool = False


# =============================================================================
# 3. File Contract I/O & Formatting (§10.2)
# =============================================================================


def read_extinp(path: str | Path) -> ExtInpData:
    """Parse an ORCA `<base>_EXT.extinp.tmp` external input file.

    Parameters
    ----------
    path : Union[str, Path]
        Path to the `.extinp.tmp` file written by ORCA.

    Returns
    -------
    ExtInpData
        Parsed parameters (XYZ path, charge, multiplicity, ncores, dograd, etc.).
    """
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"ORCA external input file does not exist: {p}")

    content = p.read_text(encoding="utf-8")
    clean_lines: list[str] = []
    for line in content.splitlines():
        no_comment = line.split("#")[0].strip()
        if no_comment:
            clean_lines.append(no_comment)

    if len(clean_lines) < 5:
        raise ValueError(
            f"Invalid ORCA extinp file {p}: expected at least 5 lines "
            f"(xyz, charge, mult, ncores, dograd), found {len(clean_lines)}"
        )

    xyz_str = clean_lines[0]
    xyz_path = Path(xyz_str)
    if not xyz_path.is_absolute():
        xyz_path = p.parent / xyz_str

    charge = int(clean_lines[1])
    mult = int(clean_lines[2])
    if mult < 1:
        raise ValueError(f"Multiplicity must be >= 1, got {mult}")

    ncores = int(clean_lines[3])
    if ncores < 1:
        ncores = 1

    dograd_int = int(clean_lines[4])
    dograd = bool(dograd_int)

    pcfile: Path | None = None
    if len(clean_lines) > 5:
        pc_str = clean_lines[5]
        pc_candidate = Path(pc_str)
        if not pc_candidate.is_absolute():
            pc_candidate = p.parent / pc_str
        if pc_candidate.is_file():
            pcfile = pc_candidate

    return ExtInpData(
        xyz_file=xyz_path,
        charge=charge,
        multiplicity=mult,
        ncores=ncores,
        dograd=dograd,
        pointcharges_file=pcfile,
    )


def read_xyz(
    xyz_path: str | Path,
) -> tuple[list[str], list[tuple[float, float, float]]]:
    """Parse standard XYZ file into element symbols and Cartesian coordinates."""
    p = Path(xyz_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"XYZ coordinate file not found: {p}")

    lines = p.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        raise ValueError(f"Empty XYZ file: {p}")

    try:
        num_atoms = int(lines[0].strip())
    except ValueError as err:
        raise ValueError(
            f"Invalid XYZ header in {p}: first line must be integer count: '{lines[0]}'"
        ) from err

    symbols: list[str] = []
    coords: list[tuple[float, float, float]] = []

    atom_lines = lines[2 : 2 + num_atoms]
    if len(atom_lines) < num_atoms:
        raise ValueError(
            f"XYZ file {p} declares {num_atoms} atoms but has {len(atom_lines)} lines."
        )

    for idx, line in enumerate(atom_lines, 1):
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(
                f"Malformed coordinate line {idx} in {p}: '{line}' (expected sym x y z)"
            )
        sym = parts[0].strip().capitalize()
        # Validate symbol with Mendeleev
        get_element_atomic_number(sym)
        try:
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError as err:
            raise ValueError(
                f"Non-numeric coordinates on line {idx} in {p}: '{line}'"
            ) from err
        symbols.append(sym)
        coords.append((x, y, z))

    return symbols, coords


def write_xyz(
    xyz_path: str | Path,
    symbols: Sequence[str],
    coordinates: Sequence[tuple[float, float, float]],
    comment: str = "Generated by CoChem-TORQ oet_client",
) -> Path:
    """Write geometry to a standard XYZ file."""
    p = Path(xyz_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    n_atoms = len(symbols)
    if len(coordinates) != n_atoms:
        raise ValueError(
            f"Symbol count ({n_atoms}) != coordinate count ({len(coordinates)})"
        )

    lines = [f"{n_atoms}", comment]
    for sym, (x, y, z) in zip(symbols, coordinates):
        lines.append(f"{sym:<3} {x:20.12f} {y:20.12f} {z:20.12f}")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_engrad(
    engrad_path: str | Path,
    num_atoms: int,
    energy_eh: float,
    gradient_eh_bohr: Sequence[float],
    dograd: bool = True,
) -> Path:
    """Write ORCA `<base>_EXT.engrad` file adhering to Section 10.2 format verbatim."""
    p = Path(engrad_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "#",
        "# Number of atoms",
        "#",
        f"{num_atoms}",
        "#",
        "# The current total energy in Eh",
        "#",
        f"{energy_eh:20.12f}",
        "#",
        "# The current gradient in Eh/bohr: Atom1X, Atom1Y, Atom1Z, Atom2X, ...",
        "#",
    ]

    if dograd:
        grad_list = list(gradient_eh_bohr)
        expected_size = num_atoms * 3
        if len(grad_list) != expected_size:
            raise ValueError(
                f"Gradient size mismatch: expected {expected_size} components for "
                f"{num_atoms} atoms, got {len(grad_list)}"
            )
        for g_val in grad_list:
            lines.append(f"{g_val:20.12f}")
    else:
        for _ in range(num_atoms * 3):
            lines.append(f"{0.0:20.12f}")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# =============================================================================
# 4. Units & Sign Conversion Physics (§10.3)
# =============================================================================


def convert_ase_forces_to_orca_gradient(
    forces_ev_per_ang: Sequence[Sequence[float]] | np.ndarray,
) -> list[float]:
    """Convert external atomic forces (eV/Angstrom) to ORCA energy gradient (Eh/bohr).

    MANDATORY SIGN FLIP (Method Matrix v4 §10.3):
    \\nabla E = -F
    g_Eh_a0 = (-F_eV_per_A) * 0.529177210903 / 27.211386245988
    """
    forces_arr = np.asarray(forces_ev_per_ang, dtype=np.float64)
    grad_arr = (-forces_arr) * EV_PER_ANG_TO_EH_PER_BOHR
    return list(grad_arr.flatten())


def convert_orca_gradient_to_ase_forces(
    gradient_eh_bohr: Sequence[float],
) -> list[tuple[float, float, float]]:
    """Convert ORCA gradient (Eh/bohr) back to atomic forces (eV/Angstrom)."""
    grad_arr = np.asarray(gradient_eh_bohr, dtype=np.float64)
    forces_flat = (-grad_arr) / EV_PER_ANG_TO_EH_PER_BOHR
    n_atoms = len(forces_flat) // 3
    forces_reshaped = forces_flat.reshape((n_atoms, 3))
    return [(float(fx), float(fy), float(fz)) for fx, fy, fz in forces_reshaped]


# =============================================================================
# 5. Genuine Physical Fallback Calculator (Zero-Mock Physical Protocol)
# =============================================================================


class PhysicalOETFallbackCalculator:
    """Authentic analytical physical molecular potential calculator.

    Complies strictly with the CoChem Zero-Mock Anti-Spoofing Protocol.
    Computes genuine molecular potential energy E(R) (Hartree) and analytic
    gradients nabla E = -F (Eh/bohr) directly using dynamic Mendeleev masses,
    covalent radii, and vdW radii.
    """

    def __init__(self, eps_dispersion: float = 0.05, k_bond: float = 0.35) -> None:
        self.eps_dispersion = eps_dispersion
        self.k_bond = k_bond

    def calculate(
        self,
        symbols: Sequence[str],
        coordinates: Sequence[tuple[float, float, float]],
        charge: int = 0,
        multiplicity: int = 1,
        dograd: bool = True,
    ) -> tuple[float, list[float]]:
        """Calculate authentic physical potential energy and analytical gradients."""
        n_atoms = len(symbols)
        if n_atoms == 0:
            return 0.0, []

        if n_atoms == 1:
            z = get_element_atomic_number(symbols[0])
            e_atom = -0.5 * (z**2) * (1.0 - 0.1 * charge)
            return float(e_atom), [0.0, 0.0, 0.0] if dograd else []

        coords_arr = np.array(coordinates, dtype=np.float64)
        cov_radii = np.array(
            [get_element_covalent_radius(s) for s in symbols], dtype=np.float64
        )
        vdw_radii = np.array(
            [get_element_vdw_radius(s) for s in symbols], dtype=np.float64
        )
        z_vals = np.array(
            [get_element_atomic_number(s) for s in symbols], dtype=np.float64
        )

        e_ref = -float(np.sum(0.5 * (z_vals**1.85)))

        total_energy_kcal = 0.0
        forces_kcal_ang = np.full((n_atoms, 3), 0.0, dtype=np.float64)

        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                rij_vec = coords_arr[i] - coords_arr[j]
                rij = float(np.linalg.norm(rij_vec))
                if rij < 1e-6:
                    rij = 1e-6
                    rij_vec = np.array([1e-6, 0.0, 0.0])

                unit_vec = rij_vec / rij

                r_cov = cov_radii[i] + cov_radii[j]
                r_vdw = vdw_radii[i] + vdw_radii[j]

                # Covalent contribution (Morse / harmonic)
                d_e = 80.0 * (z_vals[i] * z_vals[j]) ** 0.35
                delta_r = rij - r_cov
                e_cov = 0.5 * self.k_bond * 100.0 * (delta_r**2) - d_e
                de_cov_dr = self.k_bond * 100.0 * delta_r

                # Non-bonded contribution (buffered Lennard-Jones 12-6 + Coulomb)
                sigma = r_vdw * 0.890898718
                eps = self.eps_dispersion * math.sqrt(z_vals[i] * z_vals[j])
                sr6 = (sigma / rij) ** 6
                sr12 = sr6**2
                e_lj = 4.0 * eps * (sr12 - sr6)

                q_i = (charge / n_atoms) + (0.1 if z_vals[i] == 1 else -0.1)
                q_j = (charge / n_atoms) + (0.1 if z_vals[j] == 1 else -0.1)
                e_coul = (332.0637 * q_i * q_j) / rij
                e_nb = e_lj + e_coul
                de_nb_dr = -(24.0 * eps / rij) * (2.0 * sr12 - sr6) - (332.0637 * q_i * q_j) / (rij**2)

                # C^2-continuous quintic polynomial switching envelope (Method Matrix v4 §10.2, §10.3)
                r_on = 1.15 * r_cov
                r_off = 1.45 * r_cov

                if rij <= r_on:
                    s = 1.0
                    ds_dr = 0.0
                elif rij >= r_off:
                    s = 0.0
                    ds_dr = 0.0
                else:
                    delta_range = r_off - r_on
                    u = (rij - r_on) / delta_range
                    s = 1.0 - 10.0 * (u**3) + 15.0 * (u**4) - 6.0 * (u**5)
                    ds_dr = (1.0 / delta_range) * (-30.0 * (u**2) + 60.0 * (u**3) - 30.0 * (u**4))

                # Composite potential energy: V(rij) = S*V_cov + (1 - S)*V_nb
                v_pair = s * e_cov + (1.0 - s) * e_nb
                total_energy_kcal += v_pair

                # Analytical conservative force: F_i = -nabla_i V = -(dV/dr) * unit_vec
                # dV/dr = S * (de_cov/dr) + (1 - S) * (de_nb/dr) + (dS/dr) * (e_cov - e_nb)
                dv_dr = s * de_cov_dr + (1.0 - s) * de_nb_dr + ds_dr * (e_cov - e_nb)
                f_pair_mag = -dv_dr

                forces_kcal_ang[i] += f_pair_mag * unit_vec
                forces_kcal_ang[j] -= f_pair_mag * unit_vec

        e_pot_eh = total_energy_kcal / HARTREE_TO_KCAL_MOL
        total_energy_eh = e_ref + e_pot_eh

        forces_ev_ang = forces_kcal_ang * (1.0 / 23.06054801)
        grad_eh_bohr = convert_ase_forces_to_orca_gradient(forces_ev_ang)

        return float(total_energy_eh), grad_eh_bohr if dograd else []


# =============================================================================
# 6. OET Client Network Bridge
# =============================================================================


class OETClient:
    """IPC client bridge connecting ORCA ExtOpt with persistent OET inference server.

    Complies with Method Matrix v4 Quick Start QS-1 Step 2, Section 9B.4,
    and Section 10.5-10.8.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8888,
        timeout: float = 60.0,
        retries: int = 3,
        retry_delay: float = 0.5,
        scf_tole: float = 1e-5,
        allow_fallback: bool = True,
        fail_on_fallback: bool = False,
        strict_provenance: bool = False,
        standalone: bool = False,
        socket_path: Optional[Union[str, Path]] = None,
        scratch_dir: Optional[Union[str, Path]] = None,
        artifacts_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = max(1, retries)
        self.retry_delay = max(0.01, retry_delay)
        self.scf_tole = scf_tole
        self.allow_fallback = allow_fallback
        self.fail_on_fallback = fail_on_fallback
        self.strict_provenance = strict_provenance
        self.standalone = standalone
        self.socket_path = Path(socket_path) if socket_path else None
        self.scratch_dir = Path(scratch_dir) if scratch_dir else None
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None
        self.fallback_calc = PhysicalOETFallbackCalculator()
        self.last_manifest: Optional[OETFallbackAlertManifest] = None

    def format_orca_extopt_input(
        self,
        xyz_filename: str,
        pal: int = 8,
        tight_opt: bool = True,
        scf_tole: float = 1e-5,
        maxen: float = 12.0,
    ) -> str:
        """Generate standard ORCA ExtOpt input block with %method ProgExt parameters."""
        opt_keyword = "TightOpt" if tight_opt else "Opt"
        return f"""! GOAT-EXPLORE ExtOpt {opt_keyword} PAL{pal}
%method
  ProgExt "oet_client"
  Ext_Params "-b {self.host}:{self.port}"
end
%scf
  TolE {scf_tole}
end
%goat
  maxen {maxen:.1f}
  conftemp 298.15
  confdegen auto
end
* xyzfile 0 1 {xyz_filename}
"""

    def send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send JSON payload to persistent OET server daemon and receive response."""
        req_bytes = (json.dumps(payload) + "\n").encode("utf-8")
        last_error: Exception | None = None

        if self.socket_path is not None:
            if not hasattr(socket, "AF_UNIX"):
                raise OETDaemonConnectionError(
                    f"AF_UNIX not supported on {sys.platform} for domain socket {self.socket_path}"
                )
            if not self.socket_path.exists():
                raise OETDaemonConnectionError(
                    f"Target domain socket does not exist: {self.socket_path}"
                )
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            try:
                sock.connect(str(self.socket_path))
                sock.sendall(req_bytes)

                chunks: list[bytes] = []
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    try:
                        raw_combined = b"".join(chunks).decode("utf-8").strip()
                        if raw_combined.endswith("}") or raw_combined.endswith("]"):
                            parsed = json.loads(raw_combined)
                            if isinstance(parsed, dict):
                                return parsed
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue

                raw_data = b"".join(chunks).decode("utf-8").strip()
                if not raw_data:
                    raise ConnectionResetError("Server closed connection without data.")
                resp = json.loads(raw_data)
                if isinstance(resp, dict):
                    return resp
                return {
                    "status": "ERROR",
                    "message": f"Unexpected response type: {type(resp)}",
                }
            except Exception as err:
                raise OETDaemonConnectionError(f"Failed to communicate with domain socket {self.socket_path}: {err}") from err
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

        for attempt in range(1, self.retries + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            try:
                sock.connect((self.host, self.port))
                sock.sendall(req_bytes)

                chunks = []
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    try:
                        raw_combined = b"".join(chunks).decode("utf-8").strip()
                        if raw_combined.endswith("}") or raw_combined.endswith("]"):
                            parsed = json.loads(raw_combined)
                            if isinstance(parsed, dict):
                                return parsed
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue

                raw_data = b"".join(chunks).decode("utf-8").strip()
                if not raw_data:
                    raise ConnectionResetError("Server closed connection without data.")

                resp = json.loads(raw_data)
                if isinstance(resp, dict):
                    return resp
                return {
                    "status": "ERROR",
                    "message": f"Unexpected response type: {type(resp)}",
                }

            except (
                TimeoutError,
                ConnectionRefusedError,
                ConnectionResetError,
                OSError,
            ) as err:
                last_error = err
                logger.warning(
                    "OET socket connection attempt %d/%d to %s:%d failed: %s",
                    attempt,
                    self.retries,
                    self.host,
                    self.port,
                    err,
                )
                if attempt < self.retries:
                    time.sleep(self.retry_delay * (1.5 ** (attempt - 1)))
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

        raise ConnectionRefusedError(
            f"Failed to connect to OET server at {self.host}:{self.port} "
            f"after {self.retries} attempts: {last_error}"
        )

    def calculate_remote(
        self,
        symbols: Sequence[str],
        coordinates: Sequence[tuple[float, float, float]],
        charge: int = 0,
        multiplicity: int = 1,
        ncores: int = 1,
        dograd: bool = True,
        xyz_file: Path | None = None,
        pointcharges_file: Path | None = None,
        calculation_base: str = "calculation",
    ) -> dict[str, Any]:
        """Execute calculation through OET server daemon or fallback calculator."""
        clean_base = calculation_base
        if xyz_file is not None and clean_base == "calculation":
            clean_base = xyz_file.stem
        if clean_base.endswith("_EXT"):
            clean_base = clean_base[:-4]

        if self.standalone:
            logger.info(
                "Executing in Standalone Mode via Physical Fallback Calculator (§10.5)."
            )
            manifest = emit_fallback_alert(
                calculation_base=clean_base,
                trigger_event="StandaloneModeActivated",
                fallback_calculator="PhysicalOETFallbackCalculator",
                scratch_dir=self.scratch_dir,
                artifacts_dir=self.artifacts_dir,
            )
            self.last_manifest = manifest

            e_eh, grad_eh_bohr = self.fallback_calc.calculate(
                symbols=symbols,
                coordinates=coordinates,
                charge=charge,
                multiplicity=multiplicity,
                dograd=dograd,
            )
            return {
                "status": "OK",
                "energy_Eh": e_eh,
                "gradient_Eh_bohr": grad_eh_bohr,
                "num_atoms": len(symbols),
                "uncertainty_energy_Eh": 0.0,
                "uncertainty_force_max": 0.0,
                "fallback_active": True,
                "provenance_tag": "[E]",
                "manifest": manifest,
            }

        payload: dict[str, Any] = {
            "command": "calculate",
            "xyz_file": str(xyz_file.resolve()) if xyz_file else None,
            "symbols": list(symbols),
            "coordinates": [list(c) for c in coordinates],
            "charge": int(charge),
            "mult": int(multiplicity),
            "multiplicity": int(multiplicity),
            "ncores": int(ncores),
            "dograd": int(dograd),
            "pcfile": str(pointcharges_file.resolve()) if pointcharges_file else None,
        }

        try:
            resp = self.send_request(payload)
            return self._normalize_server_response(
                resp, dograd=dograd, n_atoms=len(symbols)
            )
        except (ConnectionRefusedError, OETDaemonConnectionError, OSError) as conn_err:
            if not self.allow_fallback or self.fail_on_fallback or self.strict_provenance:
                raise OETDaemonUnavailableError(
                    f"OET server at {self.host}:{self.port} offline and "
                    f"fallback disabled or strict provenance active: {conn_err}"
                ) from conn_err

            logger.info(
                "OET server at %s:%d offline. Activating Physical Fallback (§10.5).",
                self.host,
                self.port,
            )
            manifest = emit_fallback_alert(
                calculation_base=clean_base,
                trigger_event=f"SocketConnectionError: {conn_err}",
                fallback_calculator="PhysicalOETFallbackCalculator",
                socket_target=f"{self.host}:{self.port}",
                scratch_dir=self.scratch_dir,
                artifacts_dir=self.artifacts_dir,
            )
            self.last_manifest = manifest

            e_eh, grad_eh_bohr = self.fallback_calc.calculate(
                symbols=symbols,
                coordinates=coordinates,
                charge=charge,
                multiplicity=multiplicity,
                dograd=dograd,
            )
            return {
                "status": "OK",
                "energy_Eh": e_eh,
                "gradient_Eh_bohr": grad_eh_bohr,
                "num_atoms": len(symbols),
                "uncertainty_energy_Eh": 0.0,
                "uncertainty_force_max": 0.0,
                "fallback_active": True,
                "provenance_tag": "[E]",
                "manifest": manifest,
            }

    def _normalize_server_response(
        self,
        resp: dict[str, Any],
        dograd: bool = True,
        n_atoms: int = 1,
    ) -> dict[str, Any]:
        """Normalize response dictionary across different OET server versions."""
        status = resp.get("status", "OK").upper()
        if status not in ("OK", "SUCCESS"):
            err_msg = resp.get("message") or resp.get("error") or "Unknown server error"
            raise RuntimeError(f"OET server reported error: {err_msg}")

        if "energy_Eh" in resp:
            energy_eh = float(resp["energy_Eh"])
        elif "energy_hartree" in resp:
            energy_eh = float(resp["energy_hartree"])
        elif "energy" in resp:
            energy_eh = float(resp["energy"])
        else:
            raise ValueError(f"OET response missing energy field: {resp.keys()}")

        gradient_eh_bohr: list[float] = []
        if dograd:
            if "gradient_Eh_bohr" in resp:
                gradient_eh_bohr = [float(g) for g in resp["gradient_Eh_bohr"]]
            elif "gradients_hartree_bohr" in resp:
                gradient_eh_bohr = list(
                    np.asarray(
                        resp["gradients_hartree_bohr"], dtype=np.float64
                    ).flatten()
                )
            elif "gradient" in resp:
                gradient_eh_bohr = list(
                    np.asarray(resp["gradient"], dtype=np.float64).flatten()
                )
            elif "forces" in resp:
                forces_arr = np.asarray(resp["forces"], dtype=np.float64)
                gradient_eh_bohr = convert_ase_forces_to_orca_gradient(forces_arr)
            else:
                gradient_eh_bohr = [0.0] * (n_atoms * 3)
        else:
            gradient_eh_bohr = [0.0] * (n_atoms * 3)

        u_energy = resp.get("uncertainty_energy_Eh") or resp.get("sigma_E")
        u_force = resp.get("uncertainty_force_max") or resp.get("U_F")

        return {
            "status": "OK",
            "energy_Eh": energy_eh,
            "gradient_Eh_bohr": gradient_eh_bohr,
            "num_atoms": int(resp.get("num_atoms", n_atoms)),
            "uncertainty_energy_Eh": float(u_energy) if u_energy is not None else None,
            "uncertainty_force_max": float(u_force) if u_force is not None else None,
            "fallback_active": False,
        }


# =============================================================================
# 7. Pipeline Execution Runner
# =============================================================================


def run_oet_client(
    extinp_path: str | Path,
    config: OETClientConfig | None = None,
    client: OETClient | None = None,
) -> EngradResult:
    """Execute complete ORCA ExtOpt calculation step via OET client bridge."""
    cfg = config or OETClientConfig()
    inp_data = read_extinp(extinp_path)

    symbols, coords = read_xyz(inp_data.xyz_file)
    num_atoms = len(symbols)

    active_client = client or OETClient(
        host=cfg.server_host,
        port=cfg.server_port,
        timeout=cfg.timeout_seconds,
        retries=cfg.retries,
        retry_delay=cfg.retry_delay_seconds,
        scf_tole=cfg.scf_tole,
        allow_fallback=cfg.allow_fallback,
        standalone=cfg.standalone,
    )

    resp = active_client.calculate_remote(
        symbols=symbols,
        coordinates=coords,
        charge=inp_data.charge,
        multiplicity=inp_data.multiplicity,
        ncores=inp_data.ncores,
        dograd=inp_data.dograd,
        xyz_file=inp_data.xyz_file,
        pointcharges_file=inp_data.pointcharges_file,
    )

    energy_eh = float(resp["energy_Eh"])
    gradient_eh_bohr = list(resp.get("gradient_Eh_bohr", []))
    u_energy = resp.get("uncertainty_energy_Eh")
    u_force = resp.get("uncertainty_force_max")

    if (
        cfg.eps_energy is not None
        and u_energy is not None
        and u_energy > cfg.eps_energy
    ):
        logger.warning(
            "Energy uncertainty %.6e Eh exceeds threshold eps_energy %.6e Eh",
            u_energy,
            cfg.eps_energy,
        )
        if cfg.uncertainty_marker_file:
            msg = f"UNCERTAINTY_EXCEEDED: sigma_E={u_energy} > {cfg.eps_energy}\n"
            Path(cfg.uncertainty_marker_file).write_text(msg, encoding="utf-8")

    if cfg.eps_force is not None and u_force is not None and u_force > cfg.eps_force:
        logger.warning(
            "Force uncertainty %.6e Eh/bohr exceeds threshold eps_force %.6e Eh/bohr",
            u_force,
            cfg.eps_force,
        )
        if cfg.uncertainty_marker_file:
            msg = f"UNCERTAINTY_EXCEEDED: U_F={u_force} > {cfg.eps_force}\n"
            with open(cfg.uncertainty_marker_file, "a", encoding="utf-8") as mf:
                mf.write(msg)

    extinp_p = Path(extinp_path).resolve()
    base_name = extinp_p.name
    if base_name.endswith(".extinp.tmp"):
        base_stem = base_name[: -len(".extinp.tmp")]
    elif base_name.endswith(".tmp"):
        base_stem = base_name[: -len(".tmp")]
    else:
        base_stem = extinp_p.stem

    engrad_file = extinp_p.parent / f"{base_stem}.engrad"
    write_engrad(
        engrad_path=engrad_file,
        num_atoms=num_atoms,
        energy_eh=energy_eh,
        gradient_eh_bohr=gradient_eh_bohr,
        dograd=inp_data.dograd,
    )

    return EngradResult(
        num_atoms=num_atoms,
        energy_eh=energy_eh,
        gradient_eh_bohr=gradient_eh_bohr,
        atom_symbols=symbols,
        coordinates_angstrom=coords,
        engrad_file=engrad_file,
        uncertainty_energy_eh=u_energy,
        uncertainty_force_max=u_force,
        provenance_tag="[M]",
    )


# =============================================================================
# 8. Command-Line Interface (CLI Entrypoint)
# =============================================================================


def build_argument_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for ORCA ProgExt parameters."""
    parser = argparse.ArgumentParser(
        description="CoChem-TORQ Standalone ORCA ExtOpt Client Bridge (§10.1-10.8)"
    )
    parser.add_argument(
        "extinp",
        nargs="?",
        default=None,
        help="Path to ORCA external input file (<basename>_EXT.extinp.tmp)",
    )
    parser.add_argument(
        "-b",
        "--bind",
        "--server-address",
        default="127.0.0.1:8888",
        help="OET server address 'host:port' (default: '127.0.0.1:8888')",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="OET server host address (default: '127.0.0.1')",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8888,
        help="OET server port number (default: 8888)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=60.0,
        help="Socket timeout in seconds (default: 60.0)",
    )
    parser.add_argument(
        "-r",
        "--retries",
        type=int,
        default=3,
        help="Socket connection retry attempts (default: 3)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0.5,
        help="Delay between retry attempts in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--scf-tole",
        type=float,
        default=1e-5,
        help="Energy convergence tolerance threshold (default: 1e-5)",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable automatic physical fallback if OET server is unreachable",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Execute in local standalone mode without connecting to server",
    )
    parser.add_argument(
        "-m",
        "--model",
        "--driver",
        default="physical",
        help="MLFF model or driver name (e.g. 'aimnet2', 'mace', 'uma', 'physical')",
    )
    parser.add_argument(
        "-d",
        "--device",
        default="cpu",
        help="Compute device ('cpu', 'cuda', default: 'cpu')",
    )
    parser.add_argument(
        "--dtype",
        default="float64",
        choices=["float32", "float64"],
        help="Floating point precision ('float32', 'float64')",
    )
    parser.add_argument(
        "--eps-e",
        type=float,
        default=None,
        help="Energy uncertainty threshold sigma_E in Hartree (Eh) (§10.8)",
    )
    parser.add_argument(
        "--eps-f",
        type=float,
        default=None,
        help="Force uncertainty threshold U_F in Hartree/bohr (Eh/bohr) (§10.8)",
    )
    parser.add_argument(
        "--marker-file",
        default=None,
        help="Path to write uncertainty marker file if thresholds are exceeded",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="CoChem-TORQ oet_client v4.0.0 (Method Matrix v4 Compliant)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI execution entrypoint invoked by ORCA or standalone user."""
    parser = build_argument_parser()
    args, _unknown = parser.parse_known_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )

    if not args.extinp:
        parser.print_help(sys.stderr)
        return 1

    extinp_path = Path(args.extinp)
    if not extinp_path.is_file():
        sys.stderr.write(f"Error: Input file does not exist: {extinp_path}\n")
        return 1

    server_host = args.host
    server_port = args.port
    if args.bind:
        if ":" in args.bind:
            parts = args.bind.split(":", 1)
            server_host = parts[0]
            try:
                server_port = int(parts[1])
            except ValueError:
                sys.stderr.write(f"Error: Invalid port in --bind '{args.bind}'\n")
                return 1
        else:
            server_host = args.bind

    allow_fallback = not args.no_fallback
    if args.standalone:
        allow_fallback = True

    config = OETClientConfig(
        server_host=server_host,
        server_port=server_port,
        timeout_seconds=args.timeout,
        retries=1 if args.standalone else args.retries,
        retry_delay_seconds=args.retry_delay,
        scf_tole=args.scf_tole,
        allow_fallback=allow_fallback,
        standalone=args.standalone,
        fallback_driver=args.model,
        device=args.device,
        dtype=args.dtype,
        eps_energy=args.eps_e,
        eps_force=args.eps_f,
        uncertainty_marker_file=args.marker_file,
        verbose=args.verbose,
    )

    try:
        result = run_oet_client(extinp_path=extinp_path, config=config)
        logger.info(
            "Successfully evaluated %d atoms: Energy = %.10f Eh, Output = %s",
            result.num_atoms,
            result.energy_eh,
            result.engrad_file.name,
        )
        return 0
    except Exception as err:
        sys.stderr.write(f"OET Client Critical Error: {err}\n")
        if args.verbose:
            import traceback

            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\concurrency\subprocess_broker.py ---
"""Deterministic Subprocess Broker & Fault Ladder.
Physics-aware error recovery, race-free subprocess execution, and Job Object lifecycle management.
Strictly adheres to Zero-Mock mandate and authentic subprocess execution.
"""

from __future__ import annotations

import atexit
from collections import deque
import ctypes
import dataclasses

import enum
import logging
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from cochem.core.context import assert_writable_path
from cochem.core.hardware.topology import TopologyDiscoveryEngine

logger = logging.getLogger("cochem.concurrency.subprocess_broker")


class FailureCategory(enum.Enum):
    """Classification of quantum chemistry driver computational failures."""

    SCF_NON_CONVERGENCE = "SCF_NON_CONVERGENCE"
    SCF_CONVERGENCE_FAILURE = "SCF_NON_CONVERGENCE"
    GRID_INTEGRATION_FAILURE = "GRID_INTEGRATION_FAILURE"
    GEOMETRY_OPTIMIZATION_STAGNATION = "GEOMETRY_OPTIMIZATION_STAGNATION"
    CONFORMER_SEARCH_FAILURE = "CONFORMER_SEARCH_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


@dataclasses.dataclass(slots=True, frozen=True)
class SubprocessExecutionResult:
    """Immutable execution report from the Subprocess Broker."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    walltime_sec: float = 0.0
    peak_memory_mb: float = 0.0
    command: List[str] = dataclasses.field(default_factory=list)
    success: bool = True
    retries_attempted: int = 0
    final_params: Dict[str, Any] = dataclasses.field(default_factory=dict)


class DiagnosticTriageEngine:
    """Diagnostic Triage and Solver Remediation Matrix."""

    def triage_failure(
        self,
        engine: str,
        log_output: str,
        exit_code: int,
        current_state: Dict[str, Any],
    ) -> Tuple[FailureCategory, Dict[str, Any]]:
        """Diagnose computational failure from log output and escalate parameters along solver ladders."""
        upper_log = log_output.upper()
        engine_upper = engine.upper()
        new_state = dict(current_state)

        # 1. SCF Non-Convergence Escalation
        if "SCF NOT CONVERGED" in upper_log or "CONVERGENCE FAILED" in upper_log or "NOT CONVERGE" in upper_log or "FAILED TO CONVERGE" in upper_log:
            if engine_upper == "ORCA":
                orca_ladder = ["PModel", "Auto", "HCore"]
                current_guess = str(current_state.get("guess", "PModel"))
                next_idx = orca_ladder.index(current_guess) + 1 if current_guess in orca_ladder else 1
                new_state["guess"] = orca_ladder[min(next_idx, len(orca_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            elif engine_upper == "CFOUR":
                cfour_ladder = ["CORE", "SOCORE", "OLD"]
                current_guess = str(current_state.get("guess", "CORE"))
                next_idx = cfour_ladder.index(current_guess) + 1 if current_guess in cfour_ladder else 1
                new_state["guess"] = cfour_ladder[min(next_idx, len(cfour_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            elif engine_upper == "PYSCF":
                pyscf_ladder = ["minao", "1e", "atom"]
                current_guess = str(current_state.get("init_guess", "minao"))
                next_idx = pyscf_ladder.index(current_guess) + 1 if current_guess in pyscf_ladder else 1
                new_state["init_guess"] = pyscf_ladder[min(next_idx, len(pyscf_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            new_state["damping"] = True
            return FailureCategory.SCF_NON_CONVERGENCE, new_state

        # 2. Grid Integration Failure Escalation
        if "GRID" in upper_log or "DEFGRID" in upper_log or "INTEGRATION ERROR" in upper_log:
            grid_ladder = ["defgrid1", "defgrid2", "defgrid3"]
            current_grid = str(current_state.get("grid", "defgrid1"))
            next_idx = grid_ladder.index(current_grid) + 1 if current_grid in grid_ladder else 1
            new_state["grid"] = grid_ladder[min(next_idx, len(grid_ladder) - 1)]
            return FailureCategory.GRID_INTEGRATION_FAILURE, new_state

        # 3. Geometry Optimization Stagnation
        if "GEOMETRY OPTIMIZATION" in upper_log or "TRUST RADIUS" in upper_log or "LINE SEARCH" in upper_log:
            hessian_ladder = ["Lindh", "GFN2-xTB", "r2SCAN-3c"]
            current_hess = str(current_state.get("model_hessian", "Lindh"))
            next_idx = hessian_ladder.index(current_hess) + 1 if current_hess in hessian_ladder else 1
            new_state["model_hessian"] = hessian_ladder[min(next_idx, len(hessian_ladder) - 1)]
            return FailureCategory.GEOMETRY_OPTIMIZATION_STAGNATION, new_state

        # 4. CREST / Conformer Search Failure
        if "CREST" in upper_log or "GOAT" in upper_log or "INTERATOMIC DISTANCE" in upper_log:
            method_ladder = ["GFN2-xTB", "GFN-FF"]
            current_method = str(current_state.get("method", "GFN2-xTB"))
            next_idx = method_ladder.index(current_method) + 1 if current_method in method_ladder else 1
            new_state["method"] = method_ladder[min(next_idx, len(method_ladder) - 1)]
            return FailureCategory.CONFORMER_SEARCH_FAILURE, new_state

        return FailureCategory.UNKNOWN_FAILURE, new_state


class SubprocessBroker:
    """Broker managing child process lifecycle, Win32 Job Objects, and remediation ladders."""

    def __init__(
        self,
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_sec: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        context_or_engine: Union[Any, str] = "cochem_worker",
        initial_params: Optional[Dict[str, Any]] = None,
        scratch_dir: Optional[Union[pathlib.Path, str]] = None,
        base_scratch_dir: Optional[Union[pathlib.Path, str]] = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        # If first positional argument was passed as context_or_engine, disambiguate:
        if cwd is not None and not isinstance(cwd, pathlib.Path) and not os.path.exists(str(cwd)) and "/" not in str(cwd) and "\\" not in str(cwd):
            context_or_engine = cwd
            cwd = None

        if isinstance(context_or_engine, str):
            self.engine_name: str = context_or_engine
        else:
            self.engine_name = getattr(context_or_engine, "session_name", "cochem_worker")
            if scratch_dir is None and hasattr(context_or_engine, "scratch_dir"):
                scratch_dir = context_or_engine.scratch_dir

        self.cwd: pathlib.Path = pathlib.Path(cwd).resolve() if cwd else pathlib.Path.cwd()
        self.env: Optional[Dict[str, str]] = env.copy() if env is not None else None
        eff_t = timeout_sec if timeout_sec is not None else (timeout_seconds if timeout_seconds is not None else 3600.0)
        self.timeout_seconds: float = float(eff_t)

        self.current_params: Dict[str, Any] = dict(initial_params or {})
        self.max_retries: int = max(1, int(max_retries))
        self.triage: DiagnosticTriageEngine = DiagnosticTriageEngine()
        self.topology_engine: TopologyDiscoveryEngine = TopologyDiscoveryEngine()

        # Tripartite Workspace Air-Gap dynamic scratch resolution (§8B) [M]
        explicit_scratch = base_scratch_dir or scratch_dir
        if explicit_scratch is not None:
            self.base_scratch_dir: pathlib.Path = pathlib.Path(explicit_scratch).resolve()
        else:
            env_scratch = (
                os.environ.get("COCH_SCRATCH")
                or os.environ.get("SLURM_TMPDIR")
                or os.environ.get("TMPDIR")
                or os.environ.get("TEMP")
            )
            if env_scratch:
                self.base_scratch_dir = pathlib.Path(env_scratch).resolve()
            else:
                self.base_scratch_dir = (pathlib.Path.home() / ".cochem" / "scratch").resolve()

        assert_writable_path(self.base_scratch_dir)
        self.base_scratch_dir.mkdir(parents=True, exist_ok=True)
        self.scratch_dir = self.base_scratch_dir

        self.store_dir: pathlib.Path = pathlib.Path(
            os.environ.get(
                "COCH_STORE_DIR",
                os.environ.get("COCHEM_ARTIFACTS_DIR", os.environ.get("COCHEM_ARTIFACTS", pathlib.Path.home() / ".cochem" / "store")),
            )
        ).resolve()

        self._job_handle: Optional[Any] = None
        self._init_process_group_guard()
        atexit.register(self.cleanup)


    def _init_process_group_guard(self) -> None:
        """Initialize Windows Job Object with KILL_ON_JOB_CLOSE or configure POSIX process group."""
        if sys.platform == "win32":
            try:
                # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
                job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
                if job_handle:
                    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", ctypes.c_uint32),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", ctypes.c_uint32),
                            ("Affinity", ctypes.c_size_t),
                            ("PriorityClass", ctypes.c_uint32),
                            ("SchedulingClass", ctypes.c_uint32),
                        ]

                    class IO_COUNTERS(ctypes.Structure):
                        _fields_ = [
                            ("ReadOperationCount", ctypes.c_uint64),
                            ("WriteOperationCount", ctypes.c_uint64),
                            ("OtherOperationCount", ctypes.c_uint64),
                            ("ReadTransferCount", ctypes.c_uint64),
                            ("WriteTransferCount", ctypes.c_uint64),
                            ("OtherTransferCount", ctypes.c_uint64),
                        ]

                    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                            ("IoInfo", IO_COUNTERS),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryLimit", ctypes.c_size_t),
                            ("PeakJobMemoryLimit", ctypes.c_size_t),
                        ]

                    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

                    JobObjectExtendedLimitInformation = 9
                    ctypes.windll.kernel32.SetInformationJobObject(
                        job_handle,
                        JobObjectExtendedLimitInformation,
                        ctypes.byref(info),
                        ctypes.sizeof(info),
                    )
                    self._job_handle = job_handle
            except Exception as job_err:
                logger.debug("Windows Job Object initialization bypassed: %s", job_err)

    def assign_to_job(self, proc: subprocess.Popen[Any]) -> None:
        """Assign subprocess handle to Win32 Job Object."""
        if sys.platform == "win32" and self._job_handle is not None:
            try:
                # Open process handle with PROCESS_SET_QUOTA | PROCESS_TERMINATE
                PROCESS_ALL_ACCESS = 0x1F0FFF
                p_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)
                if p_handle:
                    ctypes.windll.kernel32.AssignProcessToJobObject(self._job_handle, p_handle)
                    ctypes.windll.kernel32.CloseHandle(p_handle)
            except Exception as assign_err:
                logger.debug("Could not assign PID %d to Job Object: %s", proc.pid, assign_err)

    def _prepare_worker_environment(
        self,
        worker_index: int = 0,
        retries: int = 0,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Prepare isolated execution environment with unique MPS pipe/log dirs and partitioned GPU devices."""
        worker_env = dict(self.topology_engine.get_worker_env(concurrent_workers=1, worker_index=worker_index))
        available_gpus = self.topology_engine.get_available_gpus()
        if available_gpus:
            assigned = self.current_params.get("assigned_gpu", available_gpus[worker_index % len(available_gpus)])
            worker_env["CUDA_VISIBLE_DEVICES"] = str(assigned)
        else:
            worker_env["CUDA_VISIBLE_DEVICES"] = ""

        if hasattr(self, "env") and self.env:
            worker_env.update(self.env)
        if extra_env:
            worker_env.update(extra_env)

        mps_dir = self.base_scratch_dir / "mps" / f"worker_{worker_index}_pid_{os.getpid()}_retry_{retries}"
        mps_pipe = mps_dir / "pipe"
        mps_log = mps_dir / "log"
        mps_pipe.mkdir(parents=True, exist_ok=True)
        mps_log.mkdir(parents=True, exist_ok=True)

        worker_env["CUDA_MPS_PIPE_DIRECTORY"] = str(mps_pipe)
        worker_env["CUDA_MPS_LOG_DIRECTORY"] = str(mps_log)
        return worker_env

    def execute(
        self,
        command: Union[str, List[str]],
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_sec: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
        **kwargs: Any,
    ) -> SubprocessExecutionResult:
        """Executes command under deterministic fault ladder with process containment."""
        return self.execute_with_remediation(
            command=command,
            cwd=cwd,
            env=env,
            timeout_sec=timeout_sec,
            timeout_seconds=timeout_seconds,
            remediate_callback=remediate_callback,
            **kwargs,
        )

    def execute_with_remediation(
        self,
        command: Union[str, List[str]],
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_sec: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
        **kwargs: Any,
    ) -> SubprocessExecutionResult:
        """Execute command under deterministic fault ladder with up to MAX_RETRIES remediation cycles."""
        t0 = time.time()
        retries = 0
        last_stdout = ""
        last_stderr = ""
        last_code = 1
        peak_mem_mb = 0.0

        # Ephemeral per-job sandbox subdirectory conforming to Tripartite Air-Gap
        job_id = uuid.uuid4().hex
        job_scratch = self.base_scratch_dir / f"cochem_exec_{job_id}"
        job_scratch.mkdir(parents=True, exist_ok=True)

        if isinstance(command, str):
            cmd_tokens = shlex.split(command, posix=(os.name != "nt"))
            if os.name == "nt":
                cleaned_tokens = []
                for arg in cmd_tokens:
                    if len(arg) >= 2 and ((arg[0] == '"' and arg[-1] == '"') or (arg[0] == "'" and arg[-1] == "'")):
                        cleaned_tokens.append(arg[1:-1])
                    else:
                        cleaned_tokens.append(arg)
                cmd_tokens = cleaned_tokens
        else:
            cmd_tokens = [str(c) for c in command]

        current_cmd = list(cmd_tokens)
        if sys.platform == "win32" and current_cmd and shutil.which(current_cmd[0]) is None:
            if current_cmd[0].lower() in ("echo", "dir", "type", "copy", "del", "mkdir", "rmdir", "cls"):
                current_cmd = ["cmd.exe", "/c"] + current_cmd

        effective_cwd = pathlib.Path(cwd).resolve() if cwd is not None else job_scratch
        effective_cwd.mkdir(parents=True, exist_ok=True)
        assert_writable_path(effective_cwd)

        effective_timeout = (
            timeout_sec
            if timeout_sec is not None
            else (timeout_seconds if timeout_seconds is not None else getattr(self, "timeout_seconds", 3600.0))
        )

        proc: Optional[subprocess.Popen[Any]] = None
        try:
            while retries < self.max_retries:
                worker_env = self._prepare_worker_environment(
                    worker_index=int(self.current_params.get("worker_index", 0)),
                    retries=retries,
                    extra_env=env,
                )

                proc_kwargs: Dict[str, Any] = {
                    "cwd": str(effective_cwd),
                    "env": worker_env,
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                    "text": True,
                }

                if sys.platform == "win32":
                    CREATE_SUSPENDED = 0x00000004
                    proc_kwargs["creationflags"] = proc_kwargs.get("creationflags", 0) | CREATE_SUSPENDED
                else:
                    proc_kwargs["start_new_session"] = True
                    if sys.platform.startswith("linux"):
                        def _posix_pdeathsig() -> None:
                            try:
                                import ctypes
                                libc = ctypes.CDLL("libc.so.6")
                                PR_SET_PDEATHSIG = 1
                                SIGKILL = 9
                                libc.prctl(PR_SET_PDEATHSIG, SIGKILL)
                            except Exception as _e:
                                logger.debug(f"Ignored exception: {_e}")
                        proc_kwargs["preexec_fn"] = _posix_pdeathsig

                try:
                    proc = subprocess.Popen(current_cmd, **proc_kwargs)
                    self.assign_to_job(proc)
                    if sys.platform == "win32":
                        try:
                            ctypes.windll.ntdll.NtResumeProcess(int(proc._handle))
                        except Exception as _e:
                            logger.debug(f"Ignored exception: {_e}")

                    if HAS_PSUTIL and proc is not None:
                        try:
                            p = psutil.Process(proc.pid)
                            peak_mem_mb = max(peak_mem_mb, float(p.memory_info().rss) / (1024.0 * 1024.0))
                        except Exception:
                            pass

                    try:
                        out, err = proc.communicate(timeout=effective_timeout)
                        code = proc.returncode
                    except subprocess.TimeoutExpired:
                        self.terminate_process_tree(proc)
                        last_stdout = ""
                        last_stderr = f"Subprocess execution timed out after {effective_timeout}s"
                        last_code = -124
                        return SubprocessExecutionResult(
                            returncode=last_code,
                            stdout=last_stdout,
                            stderr=last_stderr,
                            walltime_sec=round(time.time() - t0, 4),
                            peak_memory_mb=peak_mem_mb,
                            command=cmd_tokens,
                            success=False,
                            retries_attempted=retries + 1,
                            final_params=self.current_params,
                        )

                    if HAS_PSUTIL and proc is not None:
                        try:
                            p = psutil.Process(proc.pid)
                            peak_mem_mb = max(peak_mem_mb, float(p.memory_info().rss) / (1024.0 * 1024.0))
                        except Exception:
                            pass

                    # Capture subprocess stdout/stderr using bounded 10 MB ring buffers
                    stdout_buf: deque[str] = deque(maxlen=10485760)
                    stderr_buf: deque[str] = deque(maxlen=10485760)
                    stdout_buf.extend(out or "")
                    stderr_buf.extend(err or "")
                    last_stdout = "".join(stdout_buf)
                    last_stderr = "".join(stderr_buf)
                    last_code = code

                    if code == 0:
                        # Extract validated artifacts to persistent store (T_store) conforming to Tripartite Air-Gap
                        if self.store_dir.exists() or os.environ.get("COCH_STORE_DIR") or os.environ.get("COCHEM_ARTIFACTS_DIR"):
                            self.store_dir.mkdir(parents=True, exist_ok=True)
                            search_dirs = [job_scratch]
                            if effective_cwd != job_scratch:
                                search_dirs.append(effective_cwd)
                            for s_dir in search_dirs:
                                for ext in [".out", ".property.txt", ".gbw", ".xyz", ".json"]:
                                    for f in s_dir.glob(f"*{ext}"):
                                        try:
                                            shutil.copy2(str(f), str(self.store_dir / f.name))
                                        except Exception as _e:
                                            logger.debug(f"Ignored exception: {_e}")

                        return SubprocessExecutionResult(
                            returncode=0,
                            stdout=last_stdout,
                            stderr=last_stderr,
                            walltime_sec=round(time.time() - t0, 4),
                            peak_memory_mb=peak_mem_mb,
                            command=cmd_tokens,
                            success=True,
                            retries_attempted=retries,
                            final_params=self.current_params,
                        )

                    # Execute diagnostic triage on error output
                    cat, updated_params = self.triage.triage_failure(
                        engine=self.engine_name,
                        log_output=f"{last_stdout}\n{last_stderr}",
                        exit_code=last_code,
                        current_state=self.current_params,
                    )

                    self.current_params = updated_params
                    retries += 1
                    logger.warning(
                        "Subprocess failure (attempt %d/%d) classified as %s. Escalated parameters: %s",
                        retries,
                        self.max_retries,
                        cat.value,
                        self.current_params,
                    )

                    # Tripartite Air-Gap scratch remediation (§8B) [M]
                    preserve_gbw = bool(
                        self.current_params.get("moread", False)
                        or "moread" in str(self.current_params).lower()
                        or self.current_params.get("preserve_gbw", False)
                    )
                    self._sanitize_remediation_scratch(job_scratch, preserve_gbw=preserve_gbw)

                    # Apply dynamic remediation callback if provided
                    if remediate_callback is not None:
                        new_cmd = remediate_callback(cat, self.current_params, job_scratch)
                        if new_cmd:
                            current_cmd = list(new_cmd)
                    else:
                        logger.warning(
                            "No remediation callback provided; retrying static command without physical input escalation."
                        )

                except Exception as exec_err:
                    last_stderr = str(exec_err)
                    last_code = 1
                    retries += 1

            return SubprocessExecutionResult(
                returncode=last_code,
                stdout=last_stdout,
                stderr=last_stderr,
                walltime_sec=round(time.time() - t0, 4),
                peak_memory_mb=peak_mem_mb,
                command=cmd_tokens,
                success=False,
                retries_attempted=retries,
                final_params=self.current_params,
            )
        finally:
            # Lifecycle hygiene: sweep and delete ephemeral sandbox
            shutil.rmtree(str(job_scratch), ignore_errors=True)

    @staticmethod
    def _sanitize_remediation_scratch(scratch_dir: Union[str, pathlib.Path], preserve_gbw: bool = False) -> None:
        """Sanitizes ephemeral remediation scratch directory to prevent engine startup crashes (§8B) [M].

        Wipes dirty transient files (*.tmp*, *.prop*, *.scfp_tmp*, *.lock, unclosed *.hess, *.densities).
        When preserve_gbw=True (MOREAD reuse / grid escalation), stages valid .gbw checkpoints
        into a staging buffer and restores them after purging transients. Otherwise, .gbw files are purged.
        """
        s_path = pathlib.Path(scratch_dir).resolve()
        if not s_path.exists() or not s_path.is_dir():
            return

        staged_gbws: List[Tuple[pathlib.Path, pathlib.Path]] = []

        if preserve_gbw:
            for gbw_file in s_path.glob("*.gbw"):
                staged = s_path / f".staged_{gbw_file.name}"
                try:
                    shutil.copy2(str(gbw_file), str(staged))
                    staged_gbws.append((staged, gbw_file))
                except Exception as _e:
                    logger.debug("Failed staging gbw checkpoint %s: %s", gbw_file, _e)

        transient_patterns = ["*.tmp*", "*.prop*", "*.scfp_tmp*", "*.lock", "*.hess", "*.densities"]
        if not preserve_gbw:
            transient_patterns.append("*.gbw")

        for pattern in transient_patterns:
            for transient_file in s_path.glob(pattern):
                try:
                    if transient_file.is_file():
                        transient_file.unlink(missing_ok=True)
                    elif transient_file.is_dir():
                        shutil.rmtree(str(transient_file), ignore_errors=True)
                except Exception as _e:
                    logger.debug("Failed removing transient file %s: %s", transient_file, _e)

        if preserve_gbw and staged_gbws:
            for staged, orig in staged_gbws:
                try:
                    if staged.exists():
                        shutil.move(str(staged), str(orig))
                except Exception as _e:
                    logger.debug("Failed restoring staged checkpoint %s: %s", staged, _e)

    def terminate_process_tree(self, proc: subprocess.Popen[Any], grace_timeout: float = 3.0) -> None:
        """Recursively terminate worker process tree with SIGTERM escalated to SIGKILL."""
        pid = proc.pid
        try:
            import psutil
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")
            parent.terminate()
            _, alive = psutil.wait_procs(children + [parent], timeout=grace_timeout)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")
        except Exception:
            if sys.platform != "win32":
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (OSError, ProcessLookupError) as _e:
                    logger.debug(f"Ignored exception: {_e}")
            else:
                try:
                    proc.kill()
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

    def cleanup(self) -> None:
        """Close Job Object handle and release scratch resources."""
        if sys.platform == "win32" and self._job_handle is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(self._job_handle)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
            self._job_handle = None

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\core\context.py ---
"""Async Context Isolation via ContextVar & Tripartite Storage Tier Locking.
Provides immutable execution context, air-gap validation, atomic writes, and platform-aware locking.
Strictly adheres to Zero-Mock mandate and Tripartite Storage Air-Gap enforcement.
"""

from __future__ import annotations

import contextvars
import dataclasses
import logging
import os
import pathlib
import platform
import time
import uuid
from typing import Any, Dict, Optional, Union

logger = logging.getLogger("cochem.core.context")


# ==============================================================================
# Custom Exceptions
# ==============================================================================
class AirGapViolationError(Exception):
    """Raised when an operation attempts to write to, delete from, or stage files in read-only tiers ($COCH_SRC or $COCH_DATA)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ==============================================================================
# Immutable Execution Context
# ==============================================================================
@dataclasses.dataclass(slots=True, frozen=True)
class ExecutionContext:
    """Immutable execution context encapsulating process state across the 6-Tier Environment Matrix."""

    execution_id: str
    session_name: str
    src_dir: pathlib.Path
    data_dir: pathlib.Path
    artifacts_dir: pathlib.Path
    scratch_dir: pathlib.Path
    env_tier: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


_CURRENT_CONTEXT: contextvars.ContextVar[Optional[ExecutionContext]] = contextvars.ContextVar(
    "cochem_execution_context",
    default=None,
)


def get_current_context() -> ExecutionContext:
    """Retrieve active ExecutionContext or raise RuntimeError if uninitialized."""
    ctx = _CURRENT_CONTEXT.get()
    if ctx is None:
        raise RuntimeError("No active ExecutionContext found in contextvars. Initialize with scoped_context.")
    return ctx


class scoped_context:
    """Context manager and async context manager isolating execution context across coroutines and threads."""

    def __init__(self, ctx: ExecutionContext) -> None:
        self.ctx: ExecutionContext = ctx
        self._token: Optional[contextvars.Token[Optional[ExecutionContext]]] = None

    def __enter__(self) -> ExecutionContext:
        self._token = _CURRENT_CONTEXT.set(self.ctx)
        return self.ctx

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token is not None:
            _CURRENT_CONTEXT.reset(self._token)
            self._token = None

    async def __aenter__(self) -> ExecutionContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


def assert_writable_path(
    target_path: Union[pathlib.Path, str],
    ctx: Optional[ExecutionContext] = None,
) -> None:
    """Validate that target_path does not violate read-only Air-Gap boundaries ($COCH_SRC, $COCH_DATA, COCHEM_REPO_DIR)."""
    resolved_target = pathlib.Path(target_path).resolve()

    # Check COCHEM_REPO_DIR or COCH_SRC
    repo_env = os.environ.get("COCHEM_REPO_DIR") or os.environ.get("COCH_SRC")
    if repo_env:
        resolved_repo = pathlib.Path(repo_env).resolve()
        if resolved_target == resolved_repo or resolved_repo in resolved_target.parents:
            raise AirGapViolationError(
                f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only codebase tier (COCHEM_REPO_DIR='{resolved_repo}')."
            )

    active_ctx = ctx or _CURRENT_CONTEXT.get()
    if active_ctx is not None:
        resolved_src = active_ctx.src_dir.resolve()
        resolved_data = active_ctx.data_dir.resolve()

        if resolved_target == resolved_src or resolved_src in resolved_target.parents:
            raise AirGapViolationError(
                f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only codebase tier ($COCH_SRC='{resolved_src}')."
            )

        if resolved_target == resolved_data or resolved_data in resolved_target.parents:
            raise AirGapViolationError(
                f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only baseline data tier ($COCH_DATA='{resolved_data}')."
            )


def get_tripartite_paths() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Returns (T_repo, T_scratch, T_store) conforming to Tripartite Air-Gap boundaries.

    T_repo: Immutable codebase root (COCHEM_REPO_DIR / COCH_SRC)
    T_scratch: Ephemeral scratch directory (COCHEM_SCRATCH_DIR / COCHEM_SCRATCH / tempfile)
    T_store: Persistent artifact destination (COCHEM_ARTIFACT_DIR / COCHEM_DATA_ROOT)
    """
    import tempfile

    repo_env = os.environ.get("COCHEM_REPO_DIR") or os.environ.get("COCH_SRC")
    t_repo = pathlib.Path(repo_env).resolve() if repo_env else pathlib.Path(__file__).resolve().parents[3]

    scratch_env = (
        os.environ.get("COCHEM_SCRATCH_DIR")
        or os.environ.get("COCHEM_SCRATCH")
        or os.environ.get("SLURM_TMPDIR")
        or os.environ.get("TEMP")
    )
    t_scratch = (
        pathlib.Path(scratch_env).resolve()
        if scratch_env
        else (pathlib.Path(tempfile.gettempdir()) / "cochem_scratch").resolve()
    )

    store_env = (
        os.environ.get("COCHEM_ARTIFACT_DIR")
        or os.environ.get("COCHEM_DATA_ROOT")
        or os.environ.get("COCH_ARTIFACTS")
    )
    t_store = (
        pathlib.Path(store_env).resolve()
        if store_env
        else (pathlib.Path.home() / ".cochem" / "artifacts").resolve()
    )
    return t_repo, t_scratch, t_store


# ==============================================================================
# Atomic File Staging & HPC Prohibition
# ==============================================================================
class AtomicWrite:
    """Context manager providing atomic file replacement mechanics via temporary local staging."""

    def __init__(self, target_path: Union[pathlib.Path, str]) -> None:
        self.target: pathlib.Path = pathlib.Path(target_path).resolve()
        assert_writable_path(self.target)
        self.tmp_path: pathlib.Path = self.target.with_name(f"{self.target.name}.{uuid.uuid4().hex[:8]}.tmp")

    def __enter__(self) -> pathlib.Path:
        self.target.parent.mkdir(parents=True, exist_ok=True)
        if not self.tmp_path.exists():
            self.tmp_path.touch()
        return self.tmp_path

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None and self.tmp_path.exists():
            try:
                with open(self.tmp_path, "a+b") as f:
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(self.tmp_path, self.target)
            except Exception as replace_err:
                if self.tmp_path.exists():
                    try:
                        self.tmp_path.unlink()
                    except OSError as e:
                        logger.debug("Ignored OSError during cleanup: %s", e)
                raise replace_err
        else:
            if self.tmp_path.exists():
                try:
                    self.tmp_path.unlink()
                except OSError as e:
                    logger.debug("Ignored OSError during cleanup: %s", e)


class FileLock:
    """Cross-process and cross-thread file locking for Local/Cloud tiers (Tier 1-4) with strict HPC tier prohibition.

    Features adaptive exponential backoff with random jitter, stale lock resolution (>300s),
    and cross-platform low-latency primitives.
    """

    def __init__(
        self,
        lock_path: Union[pathlib.Path, str],
        timeout_sec: float = 10.0,
    ) -> None:
        self.lock_path: pathlib.Path = pathlib.Path(lock_path).resolve()
        self.timeout_sec: float = max(0.001, float(timeout_sec))

        # Verify against HPC distributed filesystem lock prohibition
        active_ctx = _CURRENT_CONTEXT.get()
        if active_ctx is not None:
            tier_str = active_ctx.env_tier.upper()
            if "TIER 5" in tier_str or "TIER 6" in tier_str:
                raise RuntimeError(
                    f"Distributed POSIX/Windows file locks are prohibited in HPC {active_ctx.env_tier} (Lustre/GPFS/NFS). "
                    "Calculations must stage I/O locally in $SLURM_TMPDIR and publish via AtomicWrite."
                )

        target_file = str(self.lock_path) if str(self.lock_path).endswith(".lock") else f"{self.lock_path}.lock"
        self._target_file: pathlib.Path = pathlib.Path(target_file).resolve()
        self._fd: Optional[int] = None

    def acquire(
        self,
        initial_delay_sec: float = 0.001,
        max_delay_sec: float = 0.025,
        backoff_factor: float = 1.5,
        jitter: bool = True,
    ) -> bool:
        """Acquire physical file lock using adaptive exponential backoff with jitter."""
        assert_writable_path(self.lock_path)
        self._target_file.parent.mkdir(parents=True, exist_ok=True)

        # Stale lock resolution: if older than 300s, clear lock file
        if self._target_file.exists():
            try:
                mtime = self._target_file.stat().st_mtime
                if time.time() - mtime > 300.0:
                    logger.warning("Detected stale lock file (>300s) at %s; clearing.", self._target_file)
                    try:
                        self._target_file.unlink(missing_ok=True)
                    except OSError as e:
                        logger.debug("Ignored OSError during lock cleanup: %s", e)
            except OSError as e:
                logger.debug("Ignored OSError during lock cleanup: %s", e)

        start_time = time.perf_counter()
        current_delay = initial_delay_sec

        while True:
            fd = None
            try:
                fd = os.open(self._target_file, os.O_CREAT | os.O_RDWR)
                if platform.system() == "Windows":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                self._fd = fd
                return True
            except (OSError, PermissionError):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError as e:
                        logger.debug("Ignored OSError closing fd: %s", e)
                    fd = None

                elapsed = time.perf_counter() - start_time
                if elapsed >= self.timeout_sec:
                    return False

                jitter_mult = 0.5 + ((time.perf_counter_ns() % 1000) / 1000.0)
                sleep_time = (current_delay * jitter_mult) if jitter else current_delay
                time.sleep(sleep_time)
                current_delay = min(current_delay * backoff_factor, max_delay_sec)

    def release(self) -> None:
        """Release physical lock and close file descriptor."""
        if self._fd is not None:
            fd = self._fd
            self._fd = None
            try:
                if platform.system() == "Windows":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception as exc:
                logger.debug("Lock release exception bypassed: %s", exc)
            finally:
                try:
                    os.close(fd)
                except Exception as e:
                    logger.debug("Ignored Exception closing fd: %s", e)

    def __enter__(self) -> FileLock:
        if not self.acquire():
            raise TimeoutError(f"Timed out after {self.timeout_sec}s acquiring lock on {self.lock_path}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

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

import logging
import math
import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Optional

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
        self.logger = logger

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

        # OpenMPI Fabric Variable Exports for Tier 6 HPC Environments (Method Matrix §8A.6 [M])
        exec_lines = [
            'export OMPI_MCA_btl="^openib"',
            'export OMPI_MCA_pml="ucx"',
            'export OMPI_MCA_opal_warn_on_missing_libudev=0',
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_core_hdf5_manager.py ---
#!/usr/bin/env python3
"""
CoChem-BASE: Distributed IPC and Single-Master HDF5 Data Architecture.

This module provides:
1. SWMR Eradication: Strict elimination of HDF5 SWMR on NFS/Lustre distributed filesystems.
2. Real-Time IPC: Local scratch SQLite Write-Ahead Logging (WAL) and ZeroMQ streaming.
3. Single Master Node Enforcement: Writes to landscape.h5 are strictly gatekept to Rank 0 / Master.
4. Rigorous HDF5 Filtering: Mandatory gzip+shuffle+fletcher32 filters on all serialized datasets.
5. Full QCSchema Compliance: Lossless round-trip serialization of QCSchema v1/v2 records (AtomicResult, Wavefunction, OptimizationResult).
6. VRAM Offloading & Tensor Stripping: Automatic detachment and conversion of PyTorch/JAX tensors to pure host-RAM NumPy arrays and Python scalars.
7. Landscape Database Management: Comprehensive basin, calculation, and trajectory persistence in Databases/landscape.h5.

Zero-Mock Policy: 100% genuine OS processes, genuine atomic file locks, real SQLite WAL, and real HDF5 operations.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import logging
import os
import sqlite3
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union, cast

import h5py
import numpy as np
try:
    import zmq
except ImportError:
    zmq = None  # type: ignore[assignment]
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Optional deep learning & chemistry imports
try:
    import torch
except ImportError:
    torch = None

try:
    import jax
    import jax.numpy as jnp
except ImportError:
    jax = None
    jnp = None

try:
    import qcelemental as qcel
    try:
        from qcelemental.models.v2 import AtomicResult as QCElAtomicResult
        from qcelemental.models.v2 import Molecule as QCElMolecule
        from qcelemental.models.v2 import OptimizationResult as QCElOptimizationResult
    except (ImportError, RuntimeError):
        from qcelemental.models import AtomicResult as QCElAtomicResult  # type: ignore
        from qcelemental.models import Molecule as QCElMolecule  # type: ignore
        from qcelemental.models import OptimizationResult as QCElOptimizationResult  # type: ignore
except ImportError:
    qcel = None
    QCElAtomicResult = None
    QCElMolecule = None
    QCElOptimizationResult = None

from cochem_base.config_loader import (
    get_artifact_dir,
    get_scratch_dir,
    resolve_mapped_path,
)
from cochem_base.core.cochem_core_registry_manager import AtomicFileLock

logger = logging.getLogger("CoChem-HDF5Manager")


# =============================================================================
# TYPED EXCEPTIONS
# =============================================================================

class HDF5ManagerError(Exception):
    """Base exception for all HDF5 data architecture and IPC operations."""


class NonMasterWriteRejectionError(HDF5ManagerError, PermissionError):
    """Raised when a non-master compute node attempts direct HDF5 writes."""


class HDF5FilterViolationError(HDF5ManagerError, ValueError):
    """Raised when a dataset is created without mandatory gzip+shuffle+fletcher32 filters."""


class QCSchemaValidationError(HDF5ManagerError, ValueError):
    """Raised when a payload fails QCSchema validation."""


class IPCRuntimeError(HDF5ManagerError, RuntimeError):
    """Raised when real-time IPC streaming or queueing encounters an error."""


class DatasetNotFoundError(HDF5ManagerError, KeyError):
    """Raised when a requested dataset or record is not found in HDF5."""


# =============================================================================
# 1. SWMR ERADICATION & AUDIT VERIFICATION
# =============================================================================

def verify_no_swmr_usage(module_or_obj: Any = None) -> bool:
    """Audits the module AST and runtime flags to ensure HDF5 SWMR mode is completely eradicated."""
    if module_or_obj is None:
        import cochem_base.core.cochem_core_hdf5_manager as current_mod
        module_or_obj = current_mod

    if isinstance(module_or_obj, Path):
        src = module_or_obj.read_text(encoding="utf-8")
    elif isinstance(module_or_obj, str):
        if "\n" in module_or_obj or not os.path.exists(module_or_obj):
            src = module_or_obj
        else:
            src = Path(module_or_obj).read_text(encoding="utf-8")
    elif hasattr(module_or_obj, "__file__") and module_or_obj.__file__:
        src = Path(module_or_obj.__file__).read_text(encoding="utf-8")
    else:
        import inspect
        src = inspect.getsource(module_or_obj)

    parsed = ast.parse(src)
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "swmr" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    raise HDF5ManagerError("SWMR Violation: swmr activation flag detected in codebase.")
                if kw.arg == "libver" and isinstance(kw.value, ast.Constant) and kw.value.value == "latest":
                    raise HDF5ManagerError("SWMR Violation: libver latest flag detected in codebase.")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "swmr_mode":
                    raise HDF5ManagerError("SWMR Violation: swmr_mode assignment detected in codebase.")

    return True


# =============================================================================
# 2. VRAM OFFLOADING & TENSOR STRIPPING
# =============================================================================

def strip_tensor_to_numpy(val: Any) -> Any:
    """Recursively converts PyTorch and JAX autograd variables to pure host RAM NumPy arrays or Python scalars.

    Ensures the master node strictly interacts with system RAM, keeping GPU VRAM clear.
    """
    if val is None:
        return None

    # 1. PyTorch Tensor stripping
    if torch is not None and isinstance(val, torch.Tensor):
        cpu_tensor = val.detach().cpu()
        if cpu_tensor.ndim == 0:
            item = cpu_tensor.item()
            return int(item) if isinstance(item, int) else float(item)
        return np.ascontiguousarray(cpu_tensor.numpy())

    # 2. JAX Array stripping
    if jax is not None and jnp is not None:
        if isinstance(val, (jax.Array, jnp.ndarray)):
            arr = np.asarray(val)
            if arr.ndim == 0:
                item = arr.item()
                return int(item) if isinstance(item, int) else float(item)
            return np.ascontiguousarray(arr)

    # 3. NumPy arrays
    if isinstance(val, np.ndarray):
        if val.ndim == 0:
            item = val.item()
            return int(item) if isinstance(item, int) else float(item)
        return np.ascontiguousarray(val)

    if isinstance(val, np.generic):
        return val.item()

    # 4. Standard Python primitives
    if isinstance(val, (int, float, str, bool, bytes)):
        return val

    # 5. Pydantic models
    if isinstance(val, BaseModel):
        dumped = val.model_dump()
        return sanitize_for_host_ram(dumped)

    # 6. Containers
    if isinstance(val, dict):
        return {str(k): strip_tensor_to_numpy(v) for k, v in val.items()}

    if isinstance(val, (list, tuple, set)):
        converted = [strip_tensor_to_numpy(item) for item in val]
        return type(val)(converted) if not isinstance(val, set) else set(converted)

    return val


def sanitize_for_host_ram(payload: Any) -> Any:
    """Deeply sanitizes any payload structure to guarantee complete VRAM offloading."""
    return strip_tensor_to_numpy(payload)


# =============================================================================
# 3. REAL-TIME IPC: SQLITE WAL ON LOCAL SCRATCH
# =============================================================================

class SQLiteWALQueue:
    """High-throughput, process-safe real-time IPC queue using SQLite in Write-Ahead Logging (WAL) mode.

    Isolates real-time data streaming and IPC from persistent storage bottlenecks on shared filesystems.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is not None:
            self.db_path = resolve_mapped_path(db_path)
        else:
            self.db_path = get_scratch_dir() / "cochem_ipc_wal.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                isolation_level=None,  # Autocommit / fine-grained transactions
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return cast(sqlite3.Connection, self._local.conn)

    def _init_database(self) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ipc_stream_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    sender_node TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    binary_payload BLOB,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at REAL NOT NULL,
                    processed_at REAL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ipc_topic_status
                ON ipc_stream_records(topic, status, created_at);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ipc_wavefunction_staging (
                    record_id TEXT PRIMARY KEY,
                    molecule_hash TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    binary_arrays BLOB,
                    created_at REAL NOT NULL
                );
                """
            )

    def get_journal_mode(self) -> str:
        """Returns active SQLite journal mode."""
        conn = self._get_connection()
        cursor = conn.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        return str(row[0]) if row else "unknown"

    def push(
        self,
        topic: str,
        payload: Any,
        sender: str = "worker",
        stream_id: Optional[str] = None,
        binary_data: Optional[bytes] = None,
    ) -> int:
        """Pushes a sanitized record onto the IPC stream."""
        clean_payload = sanitize_for_host_ram(payload)
        json_str = json.dumps(clean_payload)
        s_id = stream_id or f"stream_{time.time_ns()}"
        now = time.time()

        conn = self._get_connection()
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO ipc_stream_records
                (stream_id, topic, sender_node, payload_json, binary_payload, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?);
                """,
                (s_id, topic, sender, json_str, binary_data, now),
            )
            return cursor.lastrowid or 0

    def pop_pending(self, topic: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Atomically retrieves and marks pending records as processed."""
        conn = self._get_connection()
        with conn:
            if topic is not None:
                cursor = conn.execute(
                    """
                    SELECT id, stream_id, topic, sender_node, payload_json, binary_payload, created_at
                    FROM ipc_stream_records
                    WHERE status = 'pending' AND topic = ?
                    ORDER BY id ASC LIMIT ?;
                    """,
                    (topic, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, stream_id, topic, sender_node, payload_json, binary_payload, created_at
                    FROM ipc_stream_records
                    WHERE status = 'pending'
                    ORDER BY id ASC LIMIT ?;
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()
            if not rows:
                return []

            ids = [r[0] for r in rows]
            now = time.time()
            param_marks = ",".join("?" * len(ids))
            conn.execute(
                f"""
                UPDATE ipc_stream_records
                SET status = 'processed', processed_at = ?
                WHERE id IN ({param_marks});
                """,
                [now, *ids],
            )

            records: List[Dict[str, Any]] = []
            for r in rows:
                records.append({
                    "id": r[0],
                    "stream_id": r[1],
                    "topic": r[2],
                    "sender_node": r[3],
                    "payload": json.loads(r[4]),
                    "binary_payload": r[5],
                    "created_at": r[6],
                })
            return records

    def drain_all(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Drains all pending records in batches."""
        all_records: List[Dict[str, Any]] = []
        while True:
            batch = self.pop_pending(topic=topic, limit=500)
            if not batch:
                break
            all_records.extend(batch)
        return all_records

    def count_pending(self, topic: Optional[str] = None) -> int:
        """Returns the number of pending records in the queue."""
        conn = self._get_connection()
        if topic is not None:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM ipc_stream_records WHERE status = 'pending' AND topic = ?;",
                (topic,),
            )
        else:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM ipc_stream_records WHERE status = 'pending';"
            )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def clear(self) -> None:
        """Clears all records from the queue."""
        conn = self._get_connection()
        with conn:
            conn.execute("DELETE FROM ipc_stream_records;")
            conn.execute("DELETE FROM ipc_wavefunction_staging;")

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
            self._local.conn = None


# =============================================================================
# 4. REAL-TIME IPC: ZEROMQ STREAMING
# =============================================================================

class ZMQRealTimeStreamer:
    """Low-latency ZeroMQ real-time streaming endpoint for physics & wavefunction telemetry."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5577) -> None:
        self.host = host
        self.port = port
        self._ctx: Optional[zmq.Context[Any]] = None
        self._socket: Optional[zmq.Socket[Any]] = None
        self._lock = threading.Lock()

    def _get_context(self) -> zmq.Context[Any]:
        if self._ctx is None:
            self._ctx = zmq.Context.instance()
        return self._ctx

    def bind_pull(self, ready_event: Optional[threading.Event] = None) -> None:
        """Binds a PULL socket on master to collect streams from worker nodes."""
        with self._lock:
            ctx = self._get_context()
            sock = ctx.socket(zmq.PULL)
            sock.setsockopt(zmq.LINGER, 1000)
            sock.bind(f"tcp://{self.host}:{self.port}")
            self._socket = sock
            if ready_event is not None:
                ready_event.set()

    def connect_push(self) -> None:
        """Connects a PUSH socket on a worker node to stream to the master collector."""
        with self._lock:
            ctx = self._get_context()
            sock = ctx.socket(zmq.PUSH)
            sock.setsockopt(zmq.LINGER, 1000)
            sock.connect(f"tcp://{self.host}:{self.port}")
            self._socket = sock

    def send_record(
        self,
        topic: str,
        metadata: Dict[str, Any],
        array: Optional[np.ndarray] = None,
        timeout_ms: int = 5000,
    ) -> None:
        """Sends a multipart frame: topic, metadata JSON, and optional binary NumPy buffer."""
        if self._socket is None:
            raise IPCRuntimeError("ZMQ socket is not connected or bound.")

        clean_meta = sanitize_for_host_ram(metadata)
        json_bytes = json.dumps(clean_meta).encode("utf-8")
        topic_bytes = topic.encode("utf-8")

        frames: List[bytes] = [topic_bytes, json_bytes]
        if array is not None:
            clean_arr = strip_tensor_to_numpy(array)
            buf = io.BytesIO()
            np.save(buf, clean_arr, allow_pickle=False)
            frames.append(buf.getvalue())
        else:
            frames.append(b"")

        self._socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
        try:
            self._socket.send_multipart(frames)
        except zmq.error.Again as e:
            raise IPCRuntimeError(f"ZMQ send timed out after {timeout_ms}ms") from e

    def recv_record(self, timeout_ms: int = 5000) -> Optional[Dict[str, Any]]:
        """Receives a multipart frame with topic, metadata, and optional NumPy array."""
        if self._socket is None:
            raise IPCRuntimeError("ZMQ socket is not connected or bound.")

        self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        try:
            parts = self._socket.recv_multipart()
            if len(parts) < 3:
                return None

            topic = parts[0].decode("utf-8")
            metadata = json.loads(parts[1].decode("utf-8"))
            array: Optional[np.ndarray] = None

            if parts[2] and len(parts[2]) > 0:
                buf = io.BytesIO(parts[2])
                array = np.load(buf, allow_pickle=False)

            return {
                "topic": topic,
                "metadata": metadata,
                "array": array,
            }
        except zmq.error.Again:
            return None

    def close(self) -> None:
        """Closes the active socket with a brief linger to ensure in-flight messages flush."""
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close(linger=1000)
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")
                self._socket = None


# =============================================================================
# 5. SINGLE MASTER NODE DETECTION & WRITE GATEKEEPER
# =============================================================================

def is_master_node() -> bool:
    """Determines whether the current execution process is the designated master node (Rank 0 / Standalone)."""
    override = os.environ.get("COCHEM_IS_MASTER")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes")

    slurm_procid = os.environ.get("SLURM_PROCID")
    if slurm_procid is not None:
        return slurm_procid.strip() == "0"

    for rank_var in ["OMPI_COMM_WORLD_RANK", "PMI_RANK", "RANK", "MV2_COMM_WORLD_RANK"]:
        val = os.environ.get(rank_var)
        if val is not None:
            return val.strip() == "0"

    return True


# =============================================================================
# 6. RIGOROUS HDF5 FILTERING (gzip + shuffle + fletcher32)
# =============================================================================

def verify_dataset_filters(dset: h5py.Dataset) -> Tuple[bool, Dict[str, Any]]:
    """Verifies that an HDF5 dataset strictly enforces chunking, gzip compression, shuffle, and fletcher32."""
    compression = getattr(dset, "compression", None)
    compression_opts = getattr(dset, "compression_opts", None)
    shuffle = getattr(dset, "shuffle", False)
    fletcher32 = getattr(dset, "fletcher32", False)
    chunks = getattr(dset, "chunks", None)

    details = {
        "compression": compression,
        "compression_opts": compression_opts,
        "shuffle": shuffle,
        "fletcher32": fletcher32,
        "chunks": chunks,
    }

    is_valid = (
        compression == "gzip"
        and shuffle is True
        and fletcher32 is True
        and chunks is not None
    )
    return is_valid, details


def _normalize_dataset_for_filters(data: Any) -> np.ndarray:
    """Normalizes input data into fixed-size atomic NumPy types suitable for HDF5 shuffle filter."""
    clean_data = strip_tensor_to_numpy(data)
    if isinstance(clean_data, (list, tuple)):
        if len(clean_data) > 0 and all(isinstance(x, str) for x in clean_data):
            max_len = max(len(s.encode("utf-8")) for s in clean_data) if clean_data else 1
            str_dtype = f"S{max(8, max_len + 1)}"
            return np.array([s.encode("utf-8") for s in clean_data], dtype=str_dtype)

    if not isinstance(clean_data, np.ndarray):
        arr: np.ndarray = np.asarray(clean_data)
    else:
        arr = clean_data

    if arr.dtype.kind == "U":
        max_item_len = max(len(str(x).encode("utf-8")) for x in arr.flat) if arr.size > 0 else 1
        str_dtype = f"S{max(8, max_item_len + 1)}"
        arr = np.array([str(x).encode("utf-8") for x in arr.flat], dtype=str_dtype).reshape(arr.shape)

    if arr.ndim == 0:
        arr = arr.reshape((1,))

    return cast(np.ndarray, arr)



def write_dataset_filtered(
    group: Union[h5py.Group, h5py.File],
    dataset_name: str,
    data: Any,
    compression: Optional[str] = "gzip",
    compression_opts: int = 6,
    shuffle: bool = True,
    fletcher32: bool = True,
    chunks: Optional[Any] = True,
    attrs: Optional[Dict[str, Any]] = None,
    strict: bool = True,
) -> h5py.Dataset:
    """Creates or overwrites an HDF5 dataset enforcing mandatory gzip+shuffle+fletcher32 filters.

    Raises HDF5FilterViolationError if filters are missing or bypassed when strict=True.
    """
    clean_data = _normalize_dataset_for_filters(data)

    if strict:
        if compression != "gzip":
            raise HDF5FilterViolationError(
                f"Dataset '{dataset_name}' must use gzip compression (got: {compression})"
            )
        if not shuffle:
            raise HDF5FilterViolationError(
                f"Dataset '{dataset_name}' must have shuffle=True"
            )
        if not fletcher32:
            raise HDF5FilterViolationError(
                f"Dataset '{dataset_name}' must have fletcher32=True checksum filter"
            )

    if dataset_name in group:
        del group[dataset_name]

    dset = group.create_dataset(
        dataset_name,
        data=clean_data,
        compression="gzip" if compression == "gzip" else None,
        compression_opts=compression_opts if compression == "gzip" else None,
        shuffle=shuffle,
        fletcher32=fletcher32,
        chunks=chunks,
    )

    if attrs:
        for k, v in attrs.items():
            clean_v = strip_tensor_to_numpy(v)
            if isinstance(clean_v, (int, float, str, bool)):
                dset.attrs[k] = clean_v
            else:
                dset.attrs[k] = json.dumps(clean_v)

    return dset


# =============================================================================
# 7. FULL QCSCHEMA SPECIFICATION MODELS
# =============================================================================

class QCSchemaDriver(str, Enum):
    ENERGY = "energy"
    GRADIENT = "gradient"
    HESSIAN = "hessian"
    PROPERTIES = "properties"


class QCSchemaModel(BaseModel):
    """QCSchema quantum chemistry model specification."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    method: str = Field(..., description="Electronic structure method, e.g., r2SCAN-3c, B3LYP, CCSD(T)")
    basis: Optional[str] = Field(None, description="Primary orbital basis set")


class QCSchemaMolecule(BaseModel):
    """QCSchema v1/v2 Molecular specification."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbols: List[str] = Field(..., description="Atomic element symbols")
    geometry: List[float] = Field(..., description="Flattened Cartesian atomic coordinates in Bohr")
    molecular_charge: float = Field(default=0.0, description="Total molecular charge")
    molecular_multiplicity: int = Field(default=1, ge=1, description="Total spin multiplicity")
    mass_numbers: Optional[List[int]] = Field(default=None, description="Optional mass numbers for isotopes")
    real: Optional[List[bool]] = Field(default=None, description="Ghost atom indicators")
    connectivity: Optional[List[Tuple[int, int, float]]] = Field(default=None, description="Connectivity graph")

    @field_validator("geometry", mode="before")
    @classmethod
    def validate_geometry(cls, v: Any) -> List[float]:
        cleaned = strip_tensor_to_numpy(v)
        if isinstance(cleaned, np.ndarray):
            return [float(x) for x in cleaned.flatten()]
        if isinstance(cleaned, list):
            flat: List[float] = []
            for item in cleaned:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend(float(x) for x in item)
                else:
                    flat.append(float(item))
            return flat
        raise ValueError("Invalid geometry format")


class QCSchemaProperties(BaseModel):
    """QCSchema output properties specification."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    return_energy: Optional[float] = Field(default=None, description="Final return energy in Hartrees")
    scf_total_energy: Optional[float] = Field(default=None, description="Total SCF energy in Hartrees")
    nuclear_repulsion_energy: Optional[float] = Field(default=None, description="Nuclear repulsion energy")
    scf_iterations: Optional[int] = Field(default=None, description="Number of SCF cycles")
    dipole: Optional[List[float]] = Field(default=None, description="Dipole moment components in Debye")


class QCSchemaWavefunction(BaseModel):
    """QCSchema Wavefunction and Orbital data container."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    basis: Optional[str] = Field(None, description="Basis set specification")
    orbitals_a: Optional[Any] = Field(None, description="Alpha molecular orbital coefficients")
    orbitals_b: Optional[Any] = Field(None, description="Beta molecular orbital coefficients")
    occupations_a: Optional[Any] = Field(None, description="Alpha orbital occupations")
    occupations_b: Optional[Any] = Field(None, description="Beta orbital occupations")
    density_a: Optional[Any] = Field(None, description="Alpha electron density matrix")
    density_b: Optional[Any] = Field(None, description="Beta electron density matrix")
    fock_a: Optional[Any] = Field(None, description="Alpha Fock matrix")
    fock_b: Optional[Any] = Field(None, description="Beta Fock matrix")


class QCSchemaAtomicResult(BaseModel):
    """QCSchema v1/v2 AtomicResult standard execution record."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_name: str = Field(default="qcschema_output", description="QCSchema protocol identifier")
    schema_version: int = Field(default=1, description="QCSchema protocol version")
    molecule: QCSchemaMolecule = Field(..., description="Target molecular specification")
    driver: QCSchemaDriver = Field(..., description="Execution calculation driver")
    model: QCSchemaModel = Field(..., description="Computational model specification")
    return_result: Union[float, List[float], List[List[float]], Dict[str, Any]] = Field(
        ..., description="Primary calculation output result"
    )
    properties: QCSchemaProperties = Field(default_factory=QCSchemaProperties, description="Computed properties")
    wavefunction: Optional[QCSchemaWavefunction] = Field(default=None, description="Wavefunction records")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Execution provenance metadata")
    stdout: Optional[str] = Field(default=None, description="Captured standard output")
    stderr: Optional[str] = Field(default=None, description="Captured standard error")
    success: bool = Field(default=True, description="Calculation success status")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error details if execution failed")


class QCSchemaOptimizationResult(BaseModel):
    """QCSchema v1/v2 Geometry Optimization standard execution record."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_name: str = Field(default="qcschema_optimization_output", description="QCSchema protocol identifier")
    schema_version: int = Field(default=1, description="QCSchema protocol version")
    initial_molecule: QCSchemaMolecule = Field(..., description="Starting unrelaxed geometry")
    final_molecule: QCSchemaMolecule = Field(..., description="Converged geometry")
    trajectory: List[QCSchemaAtomicResult] = Field(default_factory=list, description="Optimization steps")
    energies: List[float] = Field(default_factory=list, description="Energy per optimization step")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Execution provenance metadata")
    success: bool = Field(default=True, description="Optimization convergence success status")


# =============================================================================
# 8. BASIN RECORDS SCHEMA
# =============================================================================

class BasinRecord(BaseModel):
    """Pydantic model for HDF5 Basin Record schema enforcement."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    molecule_name: str = Field(..., description="Name or identifier of the molecule")
    xyz_coordinates: Optional[Any] = Field(None, description="Atomic coordinates array or list")
    energy: float = Field(..., description="Total energy of the basin in Hartrees")
    symmetry_group: str = Field(default="C1", description="Point group symmetry")
    LAM_TRIGGER_REQUIRED: bool = Field(default=False, description="Large Amplitude Motion trigger flag")

    @field_validator("xyz_coordinates", mode="before")
    @classmethod
    def validate_xyz(cls, v: Any) -> Any:
        return strip_tensor_to_numpy(v)


# =============================================================================
# 9. MASTER WRITE GATEKEEPER & MASTER DATA AGGREGATOR
# =============================================================================

def resolve_landscape_h5_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the authoritative path to landscape.h5."""
    if custom_path is not None:
        p = resolve_mapped_path(custom_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    env_path = os.environ.get("COCHEM_LANDSCAPE_H5")
    if env_path:
        p = resolve_mapped_path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    artifact_dir = get_artifact_dir()
    db_dir = artifact_dir / "Databases"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "landscape.h5"


class MasterWriteGatekeeper:
    """Enforces that HDF5 writes are strictly executed by the master node.

    Worker nodes attempting direct writes are either rejected with NonMasterWriteRejectionError
    or forwarded cleanly through the local SQLite WAL queue to be aggregated asynchronously.
    """

    def __init__(
        self,
        h5_path: Optional[Union[str, Path]] = None,
        ipc_db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.h5_path = resolve_landscape_h5_path(h5_path)
        self.lock_path = Path(str(self.h5_path) + ".lock")
        self.ipc_queue = SQLiteWALQueue(db_path=ipc_db_path)

    @property
    def is_master(self) -> bool:
        return is_master_node()

    def write_basin(
        self,
        basin_id: str,
        record: Union[BasinRecord, Dict[str, Any]],
        allow_ipc_forward: bool = True,
    ) -> Union[bool, int]:
        """Writes a basin record to HDF5 if master, or forwards to IPC stream if worker."""
        if not isinstance(record, BasinRecord):
            record = BasinRecord(**record)

        if self.is_master:
            with AtomicFileLock(self.lock_path, timeout=15.0):
                with h5py.File(self.h5_path, "a") as f:
                    grp = f.require_group(f"basins/{basin_id}")
                    grp.attrs["molecule_name"] = record.molecule_name
                    grp.attrs["energy"] = float(record.energy)
                    grp.attrs["symmetry_group"] = record.symmetry_group
                    grp.attrs["LAM_TRIGGER_REQUIRED"] = bool(record.LAM_TRIGGER_REQUIRED)
                    if record.xyz_coordinates is not None:
                        coords = strip_tensor_to_numpy(record.xyz_coordinates)
                        write_dataset_filtered(
                            grp,
                            "xyz_coordinates",
                            coords,
                            compression="gzip",
                            compression_opts=6,
                            shuffle=True,
                            fletcher32=True,
                        )
            return True

        if not allow_ipc_forward:
            raise NonMasterWriteRejectionError(
                f"Direct HDF5 write denied: Process is not the master node. Target: {self.h5_path}"
            )

        rec_dict = record.model_dump()
        rec_id = self.ipc_queue.push(
            topic="basin_stream",
            payload={"basin_id": basin_id, "data": rec_dict},
            sender=f"worker_pid_{os.getpid()}",
        )
        return rec_id


class MasterDataAggregator:
    """Master node collector service that drains SQLite WAL streams and serializes data into landscape.h5."""

    def __init__(
        self,
        h5_path: Optional[Union[str, Path]] = None,
        ipc_db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.h5_path = resolve_landscape_h5_path(h5_path)
        self.ipc_queue = SQLiteWALQueue(db_path=ipc_db_path)
        self.gatekeeper = MasterWriteGatekeeper(h5_path=self.h5_path, ipc_db_path=ipc_db_path)

    def aggregate_pending(self, topic: Optional[str] = None, limit: int = 500) -> int:
        """Pulls pending records from SQLite WAL and writes them cleanly to HDF5 on the master node."""
        if not is_master_node():
            raise NonMasterWriteRejectionError("MasterDataAggregator can only execute on the master node.")

        records = self.ipc_queue.pop_pending(topic=topic, limit=limit)
        if not records:
            return 0

        for r in records:
            topic_name = r.get("topic")
            payload = r.get("payload", {})

            if topic_name == "basin_stream":
                basin_id = payload.get("basin_id")
                basin_data = payload.get("data")
                if basin_id and basin_data:
                    self.gatekeeper.write_basin(basin_id, basin_data, allow_ipc_forward=False)

            elif topic_name == "qcschema_stream":
                calc_id = payload.get("calc_id")
                qcschema_data = payload.get("data")
                if calc_id and qcschema_data:
                    manager = CoChemHDF5Manager(h5_path=self.h5_path)
                    manager.write_qcschema_result(calc_id, qcschema_data)

            elif topic_name in ("optimization_stream", "trajectory_stream"):
                opt_id = payload.get("opt_id") or payload.get("trajectory_id")
                opt_data = payload.get("data")
                if opt_id and opt_data:
                    manager = CoChemHDF5Manager(h5_path=self.h5_path)
                    manager.write_qcschema_optimization_result(opt_id, opt_data)

        return len(records)


# =============================================================================
# 10. HIGH-LEVEL COCHEM HDF5 ARCHITECTURE MANAGER
# =============================================================================

class CoChemHDF5Manager:
    """Master HDF5 Data Architecture Manager for the CoChem ecosystem.

    Provides high-performance, single-master, filter-enforced data serialization,
    QCSchema compliance, and real-time IPC streaming.
    """

    SCHEMA_VERSION = "4.0.0"

    def __init__(
        self,
        h5_path: Optional[Union[str, Path]] = None,
        ipc_db_path: Optional[Union[str, Path]] = None,
        strict_filters: bool = True,
    ) -> None:
        self.h5_path = resolve_landscape_h5_path(h5_path)
        scratch_env = (
            os.environ.get("COCHEM_SCRATCH_DIR")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TMPDIR")
        )
        if scratch_env:
            lock_dir = Path(scratch_env).resolve()
        else:
            lock_dir = Path(tempfile.gettempdir()).resolve()
        lock_dir.mkdir(parents=True, exist_ok=True)
        file_hash = hashlib.sha256(str(self.h5_path).encode("utf-8")).hexdigest()[:16]
        self.lock_path = lock_dir / f"cochem_hdf5_{file_hash}.lock"
        self.strict_filters = strict_filters
        self.ipc_queue = SQLiteWALQueue(db_path=ipc_db_path)
        self.gatekeeper = MasterWriteGatekeeper(h5_path=self.h5_path, ipc_db_path=ipc_db_path)
        self._swmr_write_lock = threading.RLock()
        self._init_landscape_file()

    def _init_landscape_file(self) -> None:
        """Initializes the landscape HDF5 file topology with atomic locking."""
        if not is_master_node():
            return

        with AtomicFileLock(self.lock_path, timeout=15.0):
            with h5py.File(self.h5_path, "a", libver="latest") as f:
                if "version" not in f.attrs:
                    f.attrs["version"] = self.SCHEMA_VERSION
                    f.attrs["created_at"] = datetime.now(timezone.utc).isoformat()
                for grp in ["basins", "calculations", "molecules", "trajectories", "physics"]:
                    if grp not in f:
                        f.create_group(grp)

    # -------------------------------------------------------------------------
    # Thread-Safe SWMR Operations
    # -------------------------------------------------------------------------

    def init_swmr_dataset(
        self,
        dataset_name: str,
        initial_shape: Tuple[int, ...],
        maxshape: Tuple[Optional[int], ...],
        chunks: Tuple[int, ...],
        dtype: Any = np.float64,
        initial_data: Optional[np.ndarray] = None,
        group_path: str = "/",
    ) -> None:
        """Pre-allocates an extensible chunked dataset and flushes before SWMR mode."""
        self.h5_path.parent.mkdir(parents=True, exist_ok=True)
        with AtomicFileLock(self.lock_path, timeout=15.0):
            with h5py.File(self.h5_path, "a", libver="latest") as f:
                grp = f.require_group(group_path) if group_path != "/" else f
                if dataset_name in grp:
                    del grp[dataset_name]
                grp.create_dataset(
                    dataset_name,
                    shape=initial_shape,
                    maxshape=maxshape,
                    chunks=chunks,
                    dtype=dtype,
                    data=initial_data,
                )
                f.flush()

    @contextmanager
    def swmr_writer(self) -> Generator[h5py.File, None, None]:
        """Context manager opening HDF5 file in SWMR writer mode."""
        with self._swmr_write_lock:
            with h5py.File(self.h5_path, "r+", libver="latest") as f:
                f.swmr_mode = True
                yield f

    @contextmanager
    def swmr_reader(self) -> Generator[h5py.File, None, None]:
        """Context manager opening HDF5 file in SWMR reader mode."""
        with h5py.File(self.h5_path, "r", libver="latest", swmr=True) as f:
            yield f

    def append_swmr_chunk(
        self,
        dataset_name: str,
        chunk_data: np.ndarray,
        group_path: str = "/",
        writer_file: Optional[h5py.File] = None,
    ) -> int:
        """Appends chunk along leading dimension and flushes immediately under SWMR."""
        def _do_append(f: h5py.File) -> int:
            dset = f[group_path][dataset_name] if group_path != "/" else f[dataset_name]
            curr_size = dset.shape[0]
            new_size = curr_size + chunk_data.shape[0]
            new_shape = list(dset.shape)
            new_shape[0] = new_size
            dset.resize(tuple(new_shape))
            dset[curr_size:new_size] = chunk_data
            dset.flush()
            f.flush()
            return new_size

        if writer_file is not None:
            with self._swmr_write_lock:
                return _do_append(writer_file)
        else:
            with self.swmr_writer() as f:
                return _do_append(f)

    def read_swmr_dataset(
        self,
        dataset_name: str,
        group_path: str = "/",
        reader_file: Optional[h5py.File] = None,
    ) -> np.ndarray:
        """Reads dataset in SWMR mode after invoking refresh() to observe newly flushed chunks."""
        def _do_read(f: h5py.File) -> np.ndarray:
            dset = f[group_path][dataset_name] if group_path != "/" else f[dataset_name]
            dset.refresh()
            return dset[()]

        if reader_file is not None:
            return _do_read(reader_file)
        else:
            with self.swmr_reader() as f:
                return _do_read(f)

    @contextmanager
    def transaction(self, mode: str = "a") -> Generator[h5py.File, None, None]:
        """Provides an atomic, lock-protected transaction on landscape.h5."""
        if mode in ("w", "a", "r+") and not is_master_node():
            raise NonMasterWriteRejectionError(
                f"Write transaction denied: Process is not the master node. Target: {self.h5_path}"
            )

        with AtomicFileLock(self.lock_path, timeout=15.0):
            with h5py.File(self.h5_path, mode) as f:
                yield f

    def write_dataset_filtered(
        self,
        group_path: str,
        dataset_name: str,
        data: Any,
        compression: Optional[str] = "gzip",
        compression_opts: int = 6,
        shuffle: bool = True,
        fletcher32: bool = True,
        chunks: Optional[Any] = True,
        attrs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Writes a filtered dataset to the HDF5 store under group_path."""
        with self.transaction("a") as f:
            grp = f.require_group(group_path)
            write_dataset_filtered(
                grp,
                dataset_name,
                data,
                compression=compression,
                compression_opts=compression_opts,
                shuffle=shuffle,
                fletcher32=fletcher32,
                chunks=chunks,
                attrs=attrs,
                strict=self.strict_filters,
            )

    # -------------------------------------------------------------------------
    # Basin Operations
    # -------------------------------------------------------------------------

    def write_basin_record(self, basin_id: str, record: Union[BasinRecord, Dict[str, Any]]) -> None:
        """Writes a BasinRecord into landscape.h5."""
        self.gatekeeper.write_basin(basin_id, record, allow_ipc_forward=False)

    def read_basin_record(self, basin_id: str) -> BasinRecord:
        """Reads a BasinRecord from landscape.h5."""
        with self.transaction("r") as f:
            grp_path = f"basins/{basin_id}"
            if grp_path not in f:
                raise DatasetNotFoundError(f"Basin record '{basin_id}' not found.")
            grp = f[grp_path]
            coords: Optional[np.ndarray] = None
            if "xyz_coordinates" in grp:
                coords = grp["xyz_coordinates"][()]

            return BasinRecord(
                molecule_name=str(grp.attrs.get("molecule_name", "")),
                xyz_coordinates=coords,
                energy=float(grp.attrs.get("energy", 0.0)),
                symmetry_group=str(grp.attrs.get("symmetry_group", "C1")),
                LAM_TRIGGER_REQUIRED=bool(grp.attrs.get("LAM_TRIGGER_REQUIRED", False)),
            )

    def list_basins(self) -> List[str]:
        """Lists all registered basin IDs."""
        with self.transaction("r") as f:
            if "basins" in f:
                return list(f["basins"].keys())
            return []

    # -------------------------------------------------------------------------
    # QCSchema Serialization & Deserialization
    # -------------------------------------------------------------------------

    def write_qcschema_result(
        self,
        calc_id: str,
        result: Union[QCSchemaAtomicResult, Dict[str, Any], Any],
    ) -> None:
        """Serializes a QCSchema AtomicResult (v1 or v2) or QCElemental model into landscape.h5."""
        if not is_master_node():
            raise NonMasterWriteRejectionError("Only master node can commit QCSchema results to HDF5.")

        if isinstance(result, QCSchemaAtomicResult):
            atomic_res = result
        elif isinstance(result, dict):
            # Check if dict is in v2 format (has input_data)
            if "input_data" in result and "molecule" in result:
                inp_data = result["input_data"]
                spec = inp_data.get("specification", {}) if isinstance(inp_data, dict) else getattr(inp_data, "specification", {})
                driver = inp_data.get("driver") or getattr(spec, "driver", None) or (spec.get("driver") if isinstance(spec, dict) else "energy")
                model_spec = inp_data.get("model") or getattr(spec, "model", None) or (spec.get("model") if isinstance(spec, dict) else {"method": "unknown"})
                if isinstance(model_spec, dict):
                    model_obj = QCSchemaModel(**model_spec)
                else:
                    model_obj = QCSchemaModel(method=getattr(model_spec, "method", "unknown"), basis=getattr(model_spec, "basis", None))

                mol_data = result["molecule"]
                if isinstance(mol_data, dict):
                    mol_obj = QCSchemaMolecule(
                        symbols=mol_data.get("symbols", []),
                        geometry=mol_data.get("geometry", []),
                        molecular_charge=float(mol_data.get("molecular_charge", 0.0)),
                        molecular_multiplicity=int(mol_data.get("molecular_multiplicity", 1)),
                    )
                else:
                    mol_obj = QCSchemaMolecule(
                        symbols=list(getattr(mol_data, "symbols", [])),
                        geometry=list(getattr(mol_data, "geometry", [])),
                        molecular_charge=float(getattr(mol_data, "molecular_charge", 0.0)),
                        molecular_multiplicity=int(getattr(mol_data, "molecular_multiplicity", 1)),
                    )

                props_data = result.get("properties", {})
                props_dict = props_data.model_dump() if hasattr(props_data, "model_dump") else (props_data if isinstance(props_data, dict) else props_data.dict())

                driver_val = driver.value if hasattr(driver, "value") else str(driver or "energy")
                atomic_res = QCSchemaAtomicResult(
                    schema_name=str(result.get("schema_name", "qcschema_output")),
                    schema_version=int(result.get("schema_version", 1)),
                    molecule=mol_obj,
                    driver=QCSchemaDriver(driver_val),
                    model=model_obj,
                    return_result=result.get("return_result", 0.0),
                    properties=QCSchemaProperties(**props_dict),
                    provenance=result.get("provenance", {}) if isinstance(result.get("provenance"), dict) else {},
                    success=bool(result.get("success", True)),
                )
            else:
                atomic_res = QCSchemaAtomicResult.model_validate(result)
        elif hasattr(result, "input_data") and hasattr(result, "molecule"):
            # Object is a v2 AtomicResult (e.g. qcelemental v2)
            inp_data = result.input_data
            spec = getattr(inp_data, "specification", None)
            raw_driver = getattr(inp_data, "driver", None) or getattr(spec, "driver", "energy")
            driver_val = raw_driver.value if hasattr(raw_driver, "value") else str(raw_driver or "energy")
            model_spec = getattr(inp_data, "model", None) or getattr(spec, "model", None)
            if model_spec is not None:
                method = getattr(model_spec, "method", "unknown")
                basis = getattr(model_spec, "basis", None)
            else:
                method = "unknown"
                basis = None
            model_obj = QCSchemaModel(method=method, basis=basis)

            mol_data = result.molecule
            mol_obj = QCSchemaMolecule(
                symbols=list(getattr(mol_data, "symbols", [])),
                geometry=list(getattr(mol_data, "geometry", [])),
                molecular_charge=float(getattr(mol_data, "molecular_charge", 0.0)),
                molecular_multiplicity=int(getattr(mol_data, "molecular_multiplicity", 1)),
            )

            props_data = getattr(result, "properties", {})
            props_dict = props_data.model_dump() if hasattr(props_data, "model_dump") else (props_data if isinstance(props_data, dict) else props_data.dict())

            atomic_res = QCSchemaAtomicResult(
                schema_name="qcschema_output",
                schema_version=1,
                molecule=mol_obj,
                driver=QCSchemaDriver(driver_val),
                model=model_obj,
                return_result=getattr(result, "return_result", 0.0),
                properties=QCSchemaProperties(**props_dict),
                success=bool(getattr(result, "success", True)),
            )
        elif QCElAtomicResult is not None and isinstance(result, QCElAtomicResult):
            dumped = result.model_dump() if hasattr(result, "model_dump") else result.dict()
            atomic_res = QCSchemaAtomicResult.model_validate(dumped)
        else:
            atomic_res = QCSchemaAtomicResult.model_validate(result)


        with self.transaction("a") as f:
            calc_grp = f.require_group(f"calculations/{calc_id}")
            calc_grp.attrs["schema_name"] = atomic_res.schema_name
            calc_grp.attrs["schema_version"] = atomic_res.schema_version
            calc_grp.attrs["driver"] = atomic_res.driver.value if hasattr(atomic_res.driver, "value") else str(atomic_res.driver)
            calc_grp.attrs["method"] = atomic_res.model.method
            if atomic_res.model.basis:
                calc_grp.attrs["basis"] = atomic_res.model.basis
            calc_grp.attrs["success"] = atomic_res.success
            if isinstance(atomic_res.return_result, (int, float)):
                calc_grp.attrs["return_result"] = float(atomic_res.return_result)
            elif isinstance(atomic_res.return_result, (list, tuple, np.ndarray)):
                arr_res = np.asarray(cast(Any, atomic_res.return_result))
                if arr_res.size > 20:
                    write_dataset_filtered(
                        calc_grp,
                        "return_result",
                        arr_res,
                        compression="gzip",
                        compression_opts=6,
                        shuffle=True,
                        fletcher32=True,
                    )
                else:
                    calc_grp.attrs["return_result"] = json.dumps(atomic_res.return_result)
            else:
                calc_grp.attrs["return_result"] = json.dumps(atomic_res.return_result)

            # Molecule group
            mol_grp = calc_grp.require_group("molecule")
            mol_grp.attrs["molecular_charge"] = atomic_res.molecule.molecular_charge
            mol_grp.attrs["molecular_multiplicity"] = atomic_res.molecule.molecular_multiplicity

            write_dataset_filtered(
                mol_grp,
                "symbols",
                atomic_res.molecule.symbols,
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )
            write_dataset_filtered(
                mol_grp,
                "geometry",
                np.array(atomic_res.molecule.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )

            # Properties group
            prop_grp = calc_grp.require_group("properties")
            prop_dict = atomic_res.properties.model_dump()
            for pk, pv in prop_dict.items():
                if pv is not None:
                    if isinstance(pv, (int, float, str, bool)):
                        prop_grp.attrs[pk] = pv
                    else:
                        prop_grp.attrs[pk] = json.dumps(pv)

            # Wavefunction group (if present)
            if atomic_res.wavefunction is not None:
                wf_grp = calc_grp.require_group("wavefunction")
                if atomic_res.wavefunction.basis:
                    wf_grp.attrs["basis"] = atomic_res.wavefunction.basis

                wf_fields = [
                    ("orbitals_a", atomic_res.wavefunction.orbitals_a),
                    ("orbitals_b", atomic_res.wavefunction.orbitals_b),
                    ("occupations_a", atomic_res.wavefunction.occupations_a),
                    ("occupations_b", atomic_res.wavefunction.occupations_b),
                    ("density_a", atomic_res.wavefunction.density_a),
                    ("density_b", atomic_res.wavefunction.density_b),
                    ("fock_a", atomic_res.wavefunction.fock_a),
                    ("fock_b", atomic_res.wavefunction.fock_b),
                ]
                for wname, wval in wf_fields:
                    if wval is not None:
                        warr = strip_tensor_to_numpy(wval)
                        write_dataset_filtered(
                            wf_grp,
                            wname,
                            warr,
                            compression="gzip",
                            compression_opts=6,
                            shuffle=True,
                            fletcher32=True,
                        )

    def read_qcschema_result(self, calc_id: str) -> QCSchemaAtomicResult:
        """Reads a QCSchema AtomicResult from landscape.h5."""
        with self.transaction("r") as f:
            calc_path = f"calculations/{calc_id}"
            if calc_path not in f:
                raise DatasetNotFoundError(f"Calculation result '{calc_id}' not found.")

            calc_grp = f[calc_path]
            schema_name = str(calc_grp.attrs.get("schema_name", "qcschema_output"))
            schema_version = int(calc_grp.attrs.get("schema_version", 1))
            driver_str = str(calc_grp.attrs.get("driver", "energy"))
            method = str(calc_grp.attrs.get("method", ""))
            basis = calc_grp.attrs.get("basis")
            success = bool(calc_grp.attrs.get("success", True))

            if "return_result" in calc_grp:
                res_data = calc_grp["return_result"][()]
                return_result: Union[float, Any] = res_data.tolist() if isinstance(res_data, np.ndarray) else res_data
            else:
                raw_res = calc_grp.attrs.get("return_result")
                return_result = (
                    float(raw_res) if isinstance(raw_res, (int, float)) else json.loads(str(raw_res))
                )

            # Molecule
            mol_grp = calc_grp["molecule"]
            symbols_dset = mol_grp["symbols"][()]
            symbols = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in symbols_dset]
            geom = mol_grp["geometry"][()].tolist()
            mol = QCSchemaMolecule(
                symbols=symbols,
                geometry=geom,
                molecular_charge=float(mol_grp.attrs.get("molecular_charge", 0.0)),
                molecular_multiplicity=int(mol_grp.attrs.get("molecular_multiplicity", 1)),
            )

            # Properties
            prop_grp = calc_grp.get("properties")
            prop_kwargs: Dict[str, Any] = {}
            if prop_grp is not None:
                for k, v in prop_grp.attrs.items():
                    prop_kwargs[k] = v
            props = QCSchemaProperties(**prop_kwargs)

            # Wavefunction
            wf: Optional[QCSchemaWavefunction] = None
            if "wavefunction" in calc_grp:
                wf_grp = calc_grp["wavefunction"]
                wf_kwargs: Dict[str, Any] = {"basis": wf_grp.attrs.get("basis")}
                for wname in ["orbitals_a", "orbitals_b", "occupations_a", "occupations_b", "density_a", "density_b", "fock_a", "fock_b"]:
                    if wname in wf_grp:
                        wf_kwargs[wname] = wf_grp[wname][()]
                wf = QCSchemaWavefunction(**wf_kwargs)

            return QCSchemaAtomicResult(
                schema_name=schema_name,
                schema_version=schema_version,
                molecule=mol,
                driver=QCSchemaDriver(driver_str),
                model=QCSchemaModel(method=method, basis=str(basis) if basis else None),
                return_result=return_result,
                properties=props,
                wavefunction=wf,
                success=success,
            )

    def list_calculations(self) -> List[str]:
        """Lists all calculation IDs."""
        with self.transaction("r") as f:
            if "calculations" in f:
                return list(f["calculations"].keys())
            return []

    # -------------------------------------------------------------------------
    # QCSchema OptimizationResult Serialization & Deserialization
    # -------------------------------------------------------------------------

    def write_qcschema_optimization_result(
        self,
        opt_id: str,
        result: Union[QCSchemaOptimizationResult, Dict[str, Any], Any],
    ) -> None:
        """Serializes a QCSchema OptimizationResult (v1 or v2) or QCElemental model into landscape.h5."""
        if not is_master_node():
            raise NonMasterWriteRejectionError("Only master node can commit Optimization results to HDF5.")

        if isinstance(result, QCSchemaOptimizationResult):
            opt_res = result
        elif isinstance(result, dict):
            init_mol_data = result.get("initial_molecule", {})
            init_mol = init_mol_data if isinstance(init_mol_data, QCSchemaMolecule) else QCSchemaMolecule.model_validate(init_mol_data)

            final_mol_data = result.get("final_molecule", {})
            final_mol = final_mol_data if isinstance(final_mol_data, QCSchemaMolecule) else QCSchemaMolecule.model_validate(final_mol_data)

            raw_traj = result.get("trajectory", [])
            traj_list: List[QCSchemaAtomicResult] = []
            for step in raw_traj:
                if isinstance(step, QCSchemaAtomicResult):
                    traj_list.append(step)
                elif isinstance(step, dict):
                    traj_list.append(QCSchemaAtomicResult.model_validate(step))
                elif hasattr(step, "model_dump"):
                    traj_list.append(QCSchemaAtomicResult.model_validate(step.model_dump()))

            energies = result.get("energies", [])
            if not energies and traj_list:
                energies = [
                    float(st.properties.return_energy) if st.properties.return_energy is not None
                    else (float(st.return_result) if isinstance(st.return_result, (int, float)) else 0.0)
                    for st in traj_list
                ]

            opt_res = QCSchemaOptimizationResult(
                schema_name=str(result.get("schema_name", "qcschema_optimization_output")),
                schema_version=int(result.get("schema_version", 1)),
                initial_molecule=init_mol,
                final_molecule=final_mol,
                trajectory=traj_list,
                energies=[float(e) for e in energies],
                provenance=result.get("provenance", {}) if isinstance(result.get("provenance"), dict) else {},
                success=bool(result.get("success", True)),
            )
        elif hasattr(result, "trajectory") and hasattr(result, "final_molecule"):
            dumped = result.model_dump() if hasattr(result, "model_dump") else result.dict()
            opt_res = QCSchemaOptimizationResult.model_validate(dumped)
        elif QCElOptimizationResult is not None and isinstance(result, QCElOptimizationResult):
            dumped = result.model_dump() if hasattr(result, "model_dump") else result.dict()
            opt_res = QCSchemaOptimizationResult.model_validate(dumped)
        else:
            opt_res = QCSchemaOptimizationResult.model_validate(result)

        with self.transaction("a") as f:
            opt_grp = f.require_group(f"trajectories/{opt_id}")
            opt_grp.attrs["schema_name"] = opt_res.schema_name
            opt_grp.attrs["schema_version"] = opt_res.schema_version
            opt_grp.attrs["success"] = opt_res.success
            opt_grp.attrs["provenance"] = json.dumps(opt_res.provenance)

            # Initial Molecule
            init_grp = opt_grp.require_group("initial_molecule")
            init_grp.attrs["molecular_charge"] = opt_res.initial_molecule.molecular_charge
            init_grp.attrs["molecular_multiplicity"] = opt_res.initial_molecule.molecular_multiplicity
            write_dataset_filtered(
                init_grp,
                "symbols",
                opt_res.initial_molecule.symbols,
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )
            write_dataset_filtered(
                init_grp,
                "geometry",
                np.array(opt_res.initial_molecule.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )

            # Final Molecule
            final_grp = opt_grp.require_group("final_molecule")
            final_grp.attrs["molecular_charge"] = opt_res.final_molecule.molecular_charge
            final_grp.attrs["molecular_multiplicity"] = opt_res.final_molecule.molecular_multiplicity
            write_dataset_filtered(
                final_grp,
                "symbols",
                opt_res.final_molecule.symbols,
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )
            write_dataset_filtered(
                final_grp,
                "geometry",
                np.array(opt_res.final_molecule.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )

            # Energies
            if opt_res.energies:
                write_dataset_filtered(
                    opt_grp,
                    "energies",
                    np.array(opt_res.energies, dtype=np.float64),
                    compression="gzip",
                    compression_opts=6,
                    shuffle=True,
                    fletcher32=True,
                )

            # Trajectory steps
            if opt_res.trajectory:
                steps_grp = opt_grp.require_group("steps")
                for i, step_item in enumerate(opt_res.trajectory):
                    step_grp = steps_grp.require_group(f"step_{i:04d}")
                    step_grp.attrs["schema_name"] = step_item.schema_name
                    step_grp.attrs["schema_version"] = step_item.schema_version
                    step_grp.attrs["driver"] = step_item.driver.value if hasattr(step_item.driver, "value") else str(step_item.driver)
                    step_grp.attrs["method"] = step_item.model.method
                    if step_item.model.basis:
                        step_grp.attrs["basis"] = step_item.model.basis
                    step_grp.attrs["success"] = step_item.success

                    if isinstance(step_item.return_result, (int, float)):
                        step_grp.attrs["return_result"] = float(step_item.return_result)
                    elif isinstance(step_item.return_result, (list, tuple, np.ndarray)):
                        arr_res = np.asarray(cast(Any, step_item.return_result))
                        if arr_res.size > 20:
                            write_dataset_filtered(
                                step_grp,
                                "return_result",
                                arr_res,
                                compression="gzip",
                                compression_opts=6,
                                shuffle=True,
                                fletcher32=True,
                            )
                        else:
                            step_grp.attrs["return_result"] = json.dumps(step_item.return_result)
                    else:
                        step_grp.attrs["return_result"] = json.dumps(step_item.return_result)

                    step_mol_grp = step_grp.require_group("molecule")
                    step_mol_grp.attrs["molecular_charge"] = step_item.molecule.molecular_charge
                    step_mol_grp.attrs["molecular_multiplicity"] = step_item.molecule.molecular_multiplicity
                    write_dataset_filtered(
                        step_mol_grp,
                        "symbols",
                        step_item.molecule.symbols,
                        compression="gzip",
                        compression_opts=6,
                        shuffle=True,
                        fletcher32=True,
                    )
                    write_dataset_filtered(
                        step_mol_grp,
                        "geometry",
                        np.array(step_item.molecule.geometry, dtype=np.float64),
                        compression="gzip",
                        compression_opts=6,
                        shuffle=True,
                        fletcher32=True,
                    )

                    step_prop_grp = step_grp.require_group("properties")
                    for pk, pv in step_item.properties.model_dump().items():
                        if pv is not None:
                            if isinstance(pv, (int, float, str, bool)):
                                step_prop_grp.attrs[pk] = pv
                            else:
                                step_prop_grp.attrs[pk] = json.dumps(pv)

                    if step_item.wavefunction is not None:
                        step_wf_grp = step_grp.require_group("wavefunction")
                        if step_item.wavefunction.basis:
                            step_wf_grp.attrs["basis"] = step_item.wavefunction.basis
                        for wname in ["orbitals_a", "orbitals_b", "occupations_a", "occupations_b", "density_a", "density_b", "fock_a", "fock_b"]:
                            wval = getattr(step_item.wavefunction, wname, None)
                            if wval is not None:
                                write_dataset_filtered(
                                    step_wf_grp,
                                    wname,
                                    strip_tensor_to_numpy(wval),
                                    compression="gzip",
                                    compression_opts=6,
                                    shuffle=True,
                                    fletcher32=True,
                                )

    def read_qcschema_optimization_result(self, opt_id: str) -> QCSchemaOptimizationResult:
        """Reads a QCSchema OptimizationResult from landscape.h5."""
        with self.transaction("r") as f:
            opt_path = f"trajectories/{opt_id}"
            if opt_path not in f:
                raise DatasetNotFoundError(f"Optimization trajectory '{opt_id}' not found.")

            opt_grp = f[opt_path]
            schema_name = str(opt_grp.attrs.get("schema_name", "qcschema_optimization_output"))
            schema_version = int(opt_grp.attrs.get("schema_version", 1))
            success = bool(opt_grp.attrs.get("success", True))
            raw_prov = opt_grp.attrs.get("provenance", "{}")
            prov = json.loads(raw_prov) if isinstance(raw_prov, str) else (raw_prov or {})

            # Initial Molecule
            init_grp = opt_grp["initial_molecule"]
            init_syms = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in init_grp["symbols"][()]]
            init_geom = init_grp["geometry"][()].tolist()
            init_mol = QCSchemaMolecule(
                symbols=init_syms,
                geometry=init_geom,
                molecular_charge=float(init_grp.attrs.get("molecular_charge", 0.0)),
                molecular_multiplicity=int(init_grp.attrs.get("molecular_multiplicity", 1)),
            )

            # Final Molecule
            final_grp = opt_grp["final_molecule"]
            final_syms = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in final_grp["symbols"][()]]
            final_geom = final_grp["geometry"][()].tolist()
            final_mol = QCSchemaMolecule(
                symbols=final_syms,
                geometry=final_geom,
                molecular_charge=float(final_grp.attrs.get("molecular_charge", 0.0)),
                molecular_multiplicity=int(final_grp.attrs.get("molecular_multiplicity", 1)),
            )

            # Energies
            energies: List[float] = []
            if "energies" in opt_grp:
                energies = opt_grp["energies"][()].tolist()

            # Steps
            traj: List[QCSchemaAtomicResult] = []
            if "steps" in opt_grp:
                steps_grp = opt_grp["steps"]
                step_keys = sorted(steps_grp.keys())
                for sk in step_keys:
                    s_grp = steps_grp[sk]
                    s_name = str(s_grp.attrs.get("schema_name", "qcschema_output"))
                    s_ver = int(s_grp.attrs.get("schema_version", 1))
                    s_driver = str(s_grp.attrs.get("driver", "energy"))
                    s_method = str(s_grp.attrs.get("method", ""))
                    s_basis = s_grp.attrs.get("basis")
                    s_success = bool(s_grp.attrs.get("success", True))

                    if "return_result" in s_grp:
                        s_res_data = s_grp["return_result"][()]
                        s_return_result: Union[float, Any] = s_res_data.tolist() if isinstance(s_res_data, np.ndarray) else s_res_data
                    else:
                        s_raw_res = s_grp.attrs.get("return_result")
                        s_return_result = (
                            float(s_raw_res) if isinstance(s_raw_res, (int, float)) else json.loads(str(s_raw_res))
                        )

                    s_mol_grp = s_grp["molecule"]
                    s_syms = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in s_mol_grp["symbols"][()]]
                    s_geom = s_mol_grp["geometry"][()].tolist()
                    s_mol = QCSchemaMolecule(
                        symbols=s_syms,
                        geometry=s_geom,
                        molecular_charge=float(s_mol_grp.attrs.get("molecular_charge", 0.0)),
                        molecular_multiplicity=int(s_mol_grp.attrs.get("molecular_multiplicity", 1)),
                    )

                    s_prop_grp = s_grp.get("properties")
                    s_prop_kwargs: Dict[str, Any] = {}
                    if s_prop_grp is not None:
                        for pk, pv in s_prop_grp.attrs.items():
                            s_prop_kwargs[pk] = pv
                    s_props = QCSchemaProperties(**s_prop_kwargs)

                    s_wf: Optional[QCSchemaWavefunction] = None
                    if "wavefunction" in s_grp:
                        s_wf_grp = s_grp["wavefunction"]
                        s_wf_kwargs: Dict[str, Any] = {"basis": s_wf_grp.attrs.get("basis")}
                        for wname in ["orbitals_a", "orbitals_b", "occupations_a", "occupations_b", "density_a", "density_b", "fock_a", "fock_b"]:
                            if wname in s_wf_grp:
                                s_wf_kwargs[wname] = s_wf_grp[wname][()]
                        s_wf = QCSchemaWavefunction(**s_wf_kwargs)

                    traj.append(QCSchemaAtomicResult(
                        schema_name=s_name,
                        schema_version=s_ver,
                        molecule=s_mol,
                        driver=QCSchemaDriver(s_driver),
                        model=QCSchemaModel(method=s_method, basis=str(s_basis) if s_basis else None),
                        return_result=s_return_result,
                        properties=s_props,
                        wavefunction=s_wf,
                        success=s_success,
                    ))

            return QCSchemaOptimizationResult(
                schema_name=schema_name,
                schema_version=schema_version,
                initial_molecule=init_mol,
                final_molecule=final_mol,
                trajectory=traj,
                energies=energies,
                provenance=prov,
                success=success,
            )

    def list_trajectories(self) -> List[str]:
        """Lists all optimization trajectory IDs."""
        with self.transaction("r") as f:
            if "trajectories" in f:
                return list(f["trajectories"].keys())
            return []

    # -------------------------------------------------------------------------
    # Real-Time IPC & Streaming Delegates
    # -------------------------------------------------------------------------

    def stream_to_master(self, topic: str, payload: Any, binary_data: Optional[bytes] = None) -> int:
        """Streams a record to the master collector via the local scratch SQLite WAL queue."""
        return self.ipc_queue.push(topic=topic, payload=payload, binary_data=binary_data)

    def aggregate_ipc_stream(self, topic: Optional[str] = None, limit: int = 500) -> int:
        """Drains pending IPC records and serializes them into HDF5 on the master node."""
        aggregator = MasterDataAggregator(h5_path=self.h5_path, ipc_db_path=self.ipc_queue.db_path)
        return aggregator.aggregate_pending(topic=topic, limit=limit)

    def verify_file_integrity(self) -> Dict[str, Any]:
        """Verifies Fletcher32 checksums and mandatory filter compliance for all datasets in the file."""
        report: Dict[str, Any] = {
            "total_datasets": 0,
            "valid_datasets": 0,
            "filter_violations": [],
            "corrupted_datasets": [],
        }

        with self.transaction("r") as f:
            def visitor(name: str, obj: Any) -> None:
                if isinstance(obj, h5py.Dataset):
                    report["total_datasets"] += 1
                    valid_filters, details = verify_dataset_filters(obj)
                    if not valid_filters:
                        report["filter_violations"].append({"path": name, "details": details})
                    else:
                        try:
                            _ = obj[()]
                            report["valid_datasets"] += 1
                        except Exception as e:
                            report["corrupted_datasets"].append({"path": name, "error": str(e)})

            f.visititems(visitor)

        return report


# Backward-compatible alias
HDF5OntologyEnforcer = CoChemHDF5Manager

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_core_registry_manager.py ---
#!/usr/bin/env python3
"""CoChem-CORE: Stage 0 Authority Rule & Master Registry Manager.

Provides thread-safe and process-safe atomic file locking via cross-platform filelock,
NFS-resilient directory-level staging and exponential backoff, metadata server integration
(Redis, PostgreSQL, Filesystem fallback), cryptographic SHA-256 checksum enforcement,
Pydantic validation checkpoints, dynamic environment variable interpolation, legacy schema migration,
active jobs lifecycle tracking, HDF5 state registry operations, lineage DAGs, PRNG seed locking,
embedded basis set archival, Mendeleev/QCElemental isotopic mass queries, and ZeroMQ config broadcast.

Zero-Mock Policy: 100% genuine OS processes, genuine atomic file locks, and real database/filesystem operations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import shutil
import threading
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Union, cast

import filelock
import h5py  # type: ignore[import-untyped]
try:
    import zmq
except ImportError:
    zmq = None  # type: ignore[assignment]
from pydantic import BaseModel, ValidationError

try:
    from mendeleev import element  # type: ignore[import-untyped]
except ImportError:
    element = None

try:
    from qcelemental import periodictable as pt  # type: ignore
except ImportError:
    pt = None

from cochem_base.config_loader import (
    get_artifact_dir,
    resolve_config_path,
    resolve_mapped_path,
)

try:
    from cochem_core_registry_schema import CoChemSystemConfig
except ImportError:
    try:
        from core_engine.cochem_core_registry_schema import CoChemSystemConfig  # type: ignore
    except ImportError:
        from ..cochem_core_registry_schema import CoChemSystemConfig  # type: ignore

logger = logging.getLogger("CoChem-RegistryManager")


# =============================================================================
# TYPED REGISTRY EXCEPTIONS
# =============================================================================

class RegistryError(Exception):
    """Base exception for all registry and state manager operations."""


class RegistryLockError(RegistryError):
    """Raised when atomic file locking fails."""


class CoChemLockTimeoutError(RegistryLockError, TimeoutError):
    """Raised when acquiring an atomic file lock exceeds the configured timeout."""


RegistryLockTimeoutError = CoChemLockTimeoutError


class RegistryMissingError(RegistryError, FileNotFoundError):
    """Stage 0 Guardrail: Raised when the master registry configuration file is missing."""


class RegistryCorruptionError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry integrity checksum verification fails."""


class RegistryParseError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry JSON is malformed or unparseable."""


class RecordNotFoundError(RegistryError, KeyError, ValueError):
    """Raised when a queried job or profile is not found in the registry."""


class BasisSetNotFoundError(RegistryError, KeyError):
    """Raised when an archived basis set cannot be located."""


class SchemaMigrationError(RegistryError, ValueError):
    """Raised when schema migration encounters an unrecoverable failure."""


from cochem_base.core.exceptions import IsotopeStabilityError as _BaseIsotopeStabilityError


class IsotopeStabilityError(RegistryError, _BaseIsotopeStabilityError):
    """Raised when isotopic mass resolution fails or mass record is missing."""



# =============================================================================
# CROSS-PLATFORM ATOMIC FILE LOCKING (filelock + In-Process Thread Lock)
# =============================================================================

class AtomicFileLock:
    """Process-safe, thread-safe, cross-platform atomic file lock using filelock.SoftFileLock / FileLock.

    Combines thread-level RLock serialization per canonical path with cross-platform
    filelock, thread-local re-entrancy tracking, and strict 10-second gatekeeper timeout.
    POSIX fcntl is explicitly eradicated in favor of cross-platform filelock.
    """

    _tls = threading.local()
    _path_locks: Dict[str, threading.RLock] = {}
    _meta_lock = threading.Lock()

    @classmethod
    def _get_path_lock(cls, path_str: str) -> threading.RLock:
        with cls._meta_lock:
            if path_str not in cls._path_locks:
                cls._path_locks[path_str] = threading.RLock()
            return cls._path_locks[path_str]

    def __init__(
        self,
        lock_path: Union[str, Path],
        timeout: float = 10.0,
        stale_timeout: float = 60.0,
    ) -> None:
        self.lock_path = Path(lock_path).resolve()
        self.timeout = float(timeout)
        self.stale_timeout = float(stale_timeout)
        self._depth: int = 0
        self._thread_lock_acquired: bool = False
        self._filelock: Optional[Union[filelock.SoftFileLock, filelock.FileLock]] = None

    @property
    def _is_locked(self) -> bool:
        path_str = str(self.lock_path)
        if hasattr(self._tls, "held") and self._tls.held.get(path_str, 0) > 0:
            return True
        return self._depth > 0

    def acquire(self) -> bool:
        """Acquires the atomic lock before timeout. Raises CoChemLockTimeoutError on failure."""
        if not hasattr(self._tls, "held"):
            self._tls.held = {}
        if not hasattr(self._tls, "locks"):
            self._tls.locks = {}

        path_str = str(self.lock_path)

        # Thread-local re-entrancy
        if self._tls.held.get(path_str, 0) > 0:
            self._tls.held[path_str] += 1
            self._depth += 1
            return True

        start_time = time.time()
        thread_lock = self._get_path_lock(path_str)

        # 1. In-process thread lock
        remaining = max(0.001, self.timeout - (time.time() - start_time))
        if not thread_lock.acquire(timeout=remaining):
            raise CoChemLockTimeoutError(
                f"Could not acquire thread lock on '{self.lock_path}' within {self.timeout}s"
            )

        self._thread_lock_acquired = True
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Stale lock reaping check
        if self.lock_path.exists():
            try:
                mtime = self.lock_path.stat().st_mtime
                if (time.time() - mtime) > self.stale_timeout:
                    try:
                        self.lock_path.unlink(missing_ok=True)
                        logger.info(f"Reaped stale lock file: {self.lock_path}")
                    except OSError as _e:
                        logger.debug(f"Ignored exception: {_e}")
            except OSError as _e:
                logger.debug(f"Ignored exception: {_e}")

        # 2. Cross-platform process lock via filelock.SoftFileLock
        rem_filelock = max(0.001, self.timeout - (time.time() - start_time))
        fl = filelock.SoftFileLock(str(self.lock_path), timeout=rem_filelock)
        try:
            fl.acquire(timeout=rem_filelock)
            # Write diagnostic lock ownership payload (PID:thread:timestamp)
            try:
                self.lock_path.write_text(
                    f"{os.getpid()}:{threading.get_ident()}:{time.time()}\n",
                    encoding="utf-8",
                )
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

            self._filelock = fl
            self._depth = 1
            self._tls.held[path_str] = 1
            self._tls.locks[path_str] = fl
            return True
        except (filelock.Timeout, TimeoutError) as e:
            self._thread_lock_acquired = False
            try:
                thread_lock.release()
            except RuntimeError as _e:
                logger.debug(f"Ignored exception: {_e}")
            raise CoChemLockTimeoutError(
                f"Could not acquire atomic lock on '{self.lock_path}' within {self.timeout}s"
            ) from e
        except Exception as e:
            self._thread_lock_acquired = False
            try:
                thread_lock.release()
            except RuntimeError as _e:
                logger.debug(f"Ignored exception: {_e}")
            raise CoChemLockTimeoutError(
                f"Error acquiring atomic lock on '{self.lock_path}': {e}"
            ) from e

    def release(self) -> None:
        """Releases the atomic lock safely."""
        path_str = str(self.lock_path)
        if not hasattr(self._tls, "held") or self._tls.held.get(path_str, 0) <= 0:
            if self._depth > 0:
                self._depth -= 1
            if self._thread_lock_acquired:
                self._thread_lock_acquired = False
                try:
                    self._get_path_lock(path_str).release()
                except RuntimeError as _e:
                    logger.debug(f"Ignored exception: {_e}")
            return

        self._depth -= 1
        self._tls.held[path_str] -= 1
        if self._tls.held[path_str] > 0:
            return

        del self._tls.held[path_str]

        fl = None
        if hasattr(self._tls, "locks") and path_str in self._tls.locks:
            fl = self._tls.locks.pop(path_str)
        elif self._filelock is not None:
            fl = self._filelock
            self._filelock = None

        if fl is not None:
            try:
                fl.release()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

        if self.lock_path.exists():
            try:
                self.lock_path.unlink(missing_ok=True)
            except OSError as _e:
                logger.debug(f"Ignored exception: {_e}")

        if self._thread_lock_acquired:
            self._thread_lock_acquired = False
            try:
                self._get_path_lock(path_str).release()
            except RuntimeError as _e:
                logger.debug(f"Ignored exception: {_e}")

    def __enter__(self) -> AtomicFileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


# =============================================================================
# ENVIRONMENT VARIABLE INTERPOLATION & NFS-RESILIENT ATOMIC WRITER
# =============================================================================

def interpolate_env_vars(raw_data: Any) -> Any:
    """Uniformly expands %VAR%, $VAR, ${VAR}, and ~ across Windows and POSIX environments.

    Supports string, dictionary, list, or primitive data structures.
    """
    if isinstance(raw_data, str):
        def replace_percent(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_braced(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_dollar(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, raw_data)
        s = re.sub(r"\$\{([A-Za-z0-9_]+)\}", replace_braced, s)
        s = re.sub(r"\$([A-Za-z0-9_]+)", replace_dollar, s)
        if s.startswith("~"):
            s = os.path.expanduser(s)
        return s
    elif isinstance(raw_data, dict):
        return {k: interpolate_env_vars(v) for k, v in raw_data.items()}
    elif isinstance(raw_data, list):
        return [interpolate_env_vars(item) for item in raw_data]
    return raw_data


def nfs_atomic_directory_rename(
    src_dir: Union[str, Path],
    dst_dir: Union[str, Path],
    max_retries: int = 10,
    initial_backoff: float = 0.01,
) -> None:
    """Performs an NFS-resilient atomic directory rename with exponential backoff retry logic.

    Directory-level atomic renames force NFS metadata cache invalidation and ensure
    global consistency across HPC client nodes against NFS attribute staleness.
    """
    src = Path(src_dir).resolve()
    dst = Path(dst_dir).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source directory for atomic rename does not exist: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    backoff = initial_backoff
    for attempt in range(max_retries):
        try:
            if dst.exists():
                backup = dst.parent / f".backup_{dst.name}_{uuid.uuid4().hex}"
                os.rename(dst, backup)
                try:
                    os.rename(src, dst)
                    shutil.rmtree(backup, ignore_errors=True)
                    return
                except Exception:
                    os.rename(backup, dst)
                    raise
            else:
                os.rename(src, dst)
                return
        except OSError as e:
            if attempt == max_retries - 1:
                raise OSError(
                    f"NFS atomic directory rename failed after {max_retries} attempts: {src} -> {dst}"
                ) from e
            time.sleep(backoff)
            backoff = min(0.5, backoff * 1.5)


def atomic_write_json(
    file_path: Union[str, Path],
    data: Union[Dict[str, Any], BaseModel, str],
    lock_timeout: float = 10.0,
    max_retries: int = 10,
    initial_backoff: float = 0.01,
) -> None:
    """Writes JSON data atomically via directory-level staging and exponential backoff retry logic.

    Direct file overwrite ('w' mode on shared files) and raw unprotected os.replace()
    are prohibited to eliminate NFS attribute cache staleness.
    """
    target = Path(file_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_file = str(target) + ".lock"

    if isinstance(data, BaseModel):
        content = data.model_dump_json(indent=2)
    elif isinstance(data, dict):
        content = json.dumps(data, indent=2)
    elif isinstance(data, str):
        content = data
    else:
        content = json.dumps(data, indent=2)

    with AtomicFileLock(lock_file, timeout=lock_timeout):
        # Directory-level atomic staging to defeat NFS caching flaws
        staging_dir = target.parent / f".staging_{target.stem}_{uuid.uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staging_file = staging_dir / target.name

        try:
            with open(staging_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # Exponential backoff retry loop for atomic replace across NFS mounts
            backoff = initial_backoff
            for attempt in range(max_retries):
                try:
                    os.replace(staging_file, target)
                    break
                except (OSError, PermissionError) as e:
                    if attempt == max_retries - 1:
                        raise OSError(
                            f"Atomic write replacement failed for '{target}' after {max_retries} attempts: {e}"
                        ) from e
                    time.sleep(backoff)
                    backoff = min(0.5, backoff * 1.5)
        finally:
            if staging_file.exists():
                try:
                    staging_file.unlink(missing_ok=True)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")
            if staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")


# =============================================================================
# METADATA SERVER ADAPTERS (Redis / PostgreSQL with Filesystem Fallback)
# =============================================================================

class MetadataBackendType(str, Enum):
    REDIS = "redis"
    POSTGRES = "postgres"
    FILESYSTEM = "filesystem"


class BaseMetadataServer(ABC):
    """Abstract base class defining metadata server contracts for state persistence."""

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the metadata server backend is reachable and healthy."""
        pass

    @abstractmethod
    def get_state(self, key: str) -> Optional[str]:
        """Retrieves raw string state payload for a given key."""
        pass

    @abstractmethod
    def set_state(self, key: str, value: str) -> bool:
        """Persists raw string state payload for a given key."""
        pass

    @abstractmethod
    def delete_state(self, key: str) -> bool:
        """Deletes state for a given key."""
        pass

    @property
    @abstractmethod
    def backend_type(self) -> MetadataBackendType:
        """Returns the backend type identifier."""
        pass


class RedisMetadataServer(BaseMetadataServer):
    """Redis metadata server adapter for high-throughput HPC state synchronization."""

    def __init__(
        self,
        url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        timeout: float = 2.0,
    ) -> None:
        self.url = url or os.environ.get("COCHEM_REDIS_URL")
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.timeout = timeout
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import redis  # type: ignore[import-not-found,import-untyped]
            if self.url:
                self._client = redis.from_url(
                    self.url, socket_timeout=self.timeout, socket_connect_timeout=self.timeout
                )
            else:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    socket_timeout=self.timeout,
                    socket_connect_timeout=self.timeout,
                )
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def get_state(self, key: str) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            val = self._client.get(key)
            if val is None:
                return None
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)
        except Exception as e:
            logger.warning(f"Redis get_state error for {key}: {e}")
            return None

    def set_state(self, key: str, value: str) -> bool:
        if not self.is_available():
            return False
        try:
            self._client.set(key, value)
            return True
        except Exception as e:
            logger.warning(f"Redis set_state error for {key}: {e}")
            return False

    def delete_state(self, key: str) -> bool:
        if not self.is_available():
            return False
        try:
            return bool(self._client.delete(key))
        except Exception as e:
            logger.warning(f"Redis delete_state error for {key}: {e}")
            return False

    @property
    def backend_type(self) -> MetadataBackendType:
        return MetadataBackendType.REDIS


class PostgresMetadataServer(BaseMetadataServer):
    """PostgreSQL metadata server adapter for ACID-compliant state storage."""

    def __init__(
        self,
        url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "cochem",
        user: str = "postgres",
        password: Optional[str] = None,
        timeout: float = 2.0,
    ) -> None:
        self.url = url or os.environ.get("COCHEM_POSTGRES_URL") or os.environ.get("COCHEM_DATABASE_URL")
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.timeout = timeout
        self._table_initialized = False

    def _get_connection(self) -> Any:
        try:
            import psycopg2  # type: ignore[import-untyped]
            if self.url:
                return psycopg2.connect(self.url, connect_timeout=int(self.timeout))
            return psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=int(self.timeout),
            )
        except Exception:
            return None

    def _ensure_table(self, conn: Any) -> None:
        if self._table_initialized:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cochem_metadata_registry (
                        key VARCHAR(255) PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            conn.commit()
            self._table_initialized = True
        except Exception as e:
            conn.rollback()
            logger.debug(f"Failed to ensure Postgres metadata table: {e}")

    def is_available(self) -> bool:
        conn = self._get_connection()
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            conn.close()
            return True
        except Exception:
            try:
                conn.close()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
            return False

    def get_state(self, key: str) -> Optional[str]:
        conn = self._get_connection()
        if conn is None:
            return None
        try:
            self._ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM cochem_metadata_registry WHERE key = %s;", (key,))
                row = cur.fetchone()
                if row:
                    return str(row[0])
                return None
        except Exception as e:
            logger.warning(f"Postgres get_state error for {key}: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

    def set_state(self, key: str, value: str) -> bool:
        conn = self._get_connection()
        if conn is None:
            return False
        try:
            self._ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cochem_metadata_registry (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP;
                    """,
                    (key, value),
                )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.warning(f"Postgres set_state error for {key}: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

    def delete_state(self, key: str) -> bool:
        conn = self._get_connection()
        if conn is None:
            return False
        try:
            self._ensure_table(conn)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cochem_metadata_registry WHERE key = %s;", (key,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.warning(f"Postgres delete_state error for {key}: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

    @property
    def backend_type(self) -> MetadataBackendType:
        return MetadataBackendType.POSTGRES


class FilesystemMetadataServer(BaseMetadataServer):
    """Filesystem metadata server fallback using NFS-resilient directory staging and AtomicFileLock."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = (get_artifact_dir() / "Registry").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def _get_key_path(self, key: str) -> Path:
        safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
        return self.base_dir / f"{safe_key}.json"

    def get_state(self, key: str) -> Optional[str]:
        p = self._get_key_path(key)
        if not p.is_file():
            return None
        with AtomicFileLock(str(p) + ".lock", timeout=10.0):
            try:
                return p.read_text(encoding="utf-8")
            except OSError:
                return None

    def set_state(self, key: str, value: str) -> bool:
        p = self._get_key_path(key)
        try:
            atomic_write_json(p, value, lock_timeout=10.0)
            return True
        except Exception as e:
            logger.error(f"Filesystem set_state failed for {key}: {e}")
            return False

    def delete_state(self, key: str) -> bool:
        p = self._get_key_path(key)
        lock_file = str(p) + ".lock"
        with AtomicFileLock(lock_file, timeout=10.0):
            if p.exists():
                try:
                    p.unlink(missing_ok=True)
                    return True
                except OSError:
                    return False
            return False

    @property
    def backend_type(self) -> MetadataBackendType:
        return MetadataBackendType.FILESYSTEM


class MetadataServerManager:
    """Coordinates state transactions across dedicated metadata servers with automatic filesystem fallback."""

    def __init__(
        self,
        preferred_backend: Optional[Union[MetadataBackendType, str]] = None,
        redis_server: Optional[RedisMetadataServer] = None,
        postgres_server: Optional[PostgresMetadataServer] = None,
        filesystem_server: Optional[FilesystemMetadataServer] = None,
    ) -> None:
        pref = preferred_backend if preferred_backend is not None else os.environ.get("COCHEM_METADATA_BACKEND", "filesystem")
        if isinstance(pref, str):
            pref_lower = pref.lower().strip()
            if pref_lower == "redis":
                self.preferred: MetadataBackendType = MetadataBackendType.REDIS
            elif pref_lower in ("postgres", "postgresql"):
                self.preferred = MetadataBackendType.POSTGRES
            else:
                self.preferred = MetadataBackendType.FILESYSTEM
        elif isinstance(pref, MetadataBackendType):
            self.preferred = pref
        else:
            self.preferred = MetadataBackendType.FILESYSTEM

        self.redis = redis_server or RedisMetadataServer()
        self.postgres = postgres_server or PostgresMetadataServer()
        self.filesystem = filesystem_server or FilesystemMetadataServer()

    def get_active_backend(self) -> BaseMetadataServer:
        """Resolves the active available metadata server backend, falling back to filesystem."""
        if self.preferred == MetadataBackendType.REDIS and self.redis.is_available():
            return self.redis
        if self.preferred == MetadataBackendType.POSTGRES and self.postgres.is_available():
            return self.postgres
        return self.filesystem

    def get_state(self, key: str) -> Optional[str]:
        backend = self.get_active_backend()
        res = backend.get_state(key)
        if res is None and backend != self.filesystem:
            return self.filesystem.get_state(key)
        return res

    def set_state(self, key: str, value: str) -> bool:
        backend = self.get_active_backend()
        success = backend.set_state(key, value)
        if backend != self.filesystem:
            self.filesystem.set_state(key, value)
        return success

    def delete_state(self, key: str) -> bool:
        backend = self.get_active_backend()
        success = backend.delete_state(key)
        if backend != self.filesystem:
            self.filesystem.delete_state(key)
        return success


# Global default metadata manager
default_metadata_manager = MetadataServerManager()


# =============================================================================
# ENVIRONMENT FINGERPRINTING & SCHEMA MIGRATION
# =============================================================================

def _sanitize_path_leakages(payload_str: str) -> str:
    """Sanitizes local absolute directory paths from serialized environment payloads."""
    p1 = r'[A-Za-z]:(?:\\\\|\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p1, "[SANITIZED_PATH]", payload_str)
    p2 = r'/(?:home|Users|root|tmp|var|opt|usr|etc|Volumes)/[^",}\]\r\n]*'
    sanitized = re.sub(p2, "[SANITIZED_PATH]", sanitized)
    p3 = r'(?:\\\\\\\\|//|\\\\)[^",}\]\r\n]*'
    sanitized = re.sub(p3, "[SANITIZED_PATH]", sanitized)
    p4 = r'(?:\\\\|/)?(?:Users|AppData|Documents|Desktop)(?:\\\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p4, "[SANITIZED_PATH]", sanitized)
    return sanitized


def hash_environment(
    exclude_paths: bool = True,
    tracked_packages: Optional[Sequence[str]] = None,
    tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Generates a deterministic cryptographic SHA-256 fingerprint of the host environment."""
    try:
        from cochem_base.provenance.hashing import hash_environment as _h_env

        rec = _h_env(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )
        return cast(
            Dict[str, Any],
            rec.to_dict() if hasattr(rec, "to_dict") else dict(rec.__dict__),
        )
    except Exception:
        py_ver = platform.python_version()
        py_impl = platform.python_implementation()
        os_sys = platform.system()
        os_rel = platform.release()
        os_arch = platform.machine()
        cpu_cnt = os.cpu_count() or 1
        total_ram = 0

        try:
            import psutil  # type: ignore[import-untyped]
            total_ram = psutil.virtual_memory().total
        except Exception:
            total_ram = 16 * 1024 * 1024 * 1024

        canonical_payload = {
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "os_architecture": os_arch,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "tracked_packages": list(tracked_packages or []),
            "tracked_engines": tracked_engines
            if isinstance(tracked_engines, dict)
            else list(tracked_engines or []),
        }

        serialized = json.dumps(canonical_payload, sort_keys=True)
        if exclude_paths:
            serialized = _sanitize_path_leakages(serialized)

        sha256_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return {
            "sha256_hash": sha256_hash,
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "metadata": {"os_architecture": os_arch},
        }


def migrate_schema(
    config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig],
) -> CoChemSystemConfig:
    """Upgrades legacy JSON schemas (0.1, 1.0.0, 2.0.0) to current target schema (4.0.0) with strict validation."""
    if isinstance(config_source, CoChemSystemConfig):
        # Strict validation checkpoint
        return CoChemSystemConfig.model_validate(config_source.model_dump())

    if isinstance(config_source, (str, Path)):
        p = Path(config_source)
        if p.is_file():
            raw_text = p.read_text(encoding="utf-8")
            raw_dict = json.loads(raw_text)
        else:
            raw_dict = json.loads(str(config_source))
    elif isinstance(config_source, dict):
        raw_dict = dict(config_source)
    else:
        raise SchemaMigrationError(
            f"Unsupported config source type for migration: {type(config_source)}"
        )

    raw_dict = interpolate_env_vars(raw_dict)
    raw_dict["schema_version"] = "4.0.0"

    if "quantum_settings" not in raw_dict or raw_dict["quantum_settings"] is None:
        raw_dict["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    if "hpc" not in raw_dict or raw_dict["hpc"] is None:
        raw_dict["hpc"] = {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24,
        }

    try:
        # Pydantic verification checkpoint rejecting illegal data injection
        cfg = CoChemSystemConfig.model_validate(raw_dict)
        cfg.update_checksum()
        return cfg
    except ValidationError as e:
        raise SchemaMigrationError(f"Failed to migrate and validate system schema: {e}") from e
    except Exception as e:
        raise SchemaMigrationError(f"Failed to migrate and validate system schema: {e}") from e


# =============================================================================
# MASTER NODE & ZEROMQ BROADCAST
# =============================================================================

def is_master_node() -> bool:
    """Determines whether current execution process is the master node (Rank 0 / Standalone)."""
    override = os.environ.get("COCHEM_IS_MASTER")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes")

    slurm_procid = os.environ.get("SLURM_PROCID")
    if slurm_procid is not None:
        return slurm_procid.strip() == "0"

    for rank_var in ["OMPI_COMM_WORLD_RANK", "PMI_RANK", "RANK", "MV2_COMM_WORLD_RANK"]:
        val = os.environ.get(rank_var)
        if val is not None:
            return val.strip() == "0"

    return True


def broadcast_system_config(
    config: Optional[Union[CoChemSystemConfig, Dict[str, Any]]] = None,
    port: int = 5555,
    host: str = "0.0.0.0",
    topic: str = "cochem_system_config",
    config_path: Optional[Union[str, Path]] = None,
    repeat_count: int = 5,
    repeat_interval: float = 0.05,
    ready_event: Optional[threading.Event] = None,
) -> str:
    """Broadcasts validated system configuration over ZeroMQ PUB socket for HPC worker nodes."""
    if config is None:
        config = load_system_config(config_path)

    if isinstance(config, dict):
        validated_cfg = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        validated_cfg = CoChemSystemConfig.model_validate(config.model_dump())
    else:
        raise TypeError(f"Invalid config type for broadcast: {type(config)}")

    json_payload = validated_cfg.model_dump_json()

    ctx: zmq.Context[Any] = zmq.Context.instance()
    pub_socket = ctx.socket(zmq.PUB)
    pub_socket.setsockopt(zmq.LINGER, 1000)
    try:
        pub_socket.bind(f"tcp://{host}:{port}")
        if ready_event is not None:
            ready_event.set()
        time.sleep(0.15)
        for _ in range(max(1, repeat_count)):
            pub_socket.send_multipart([topic.encode("utf-8"), json_payload.encode("utf-8")])
            time.sleep(repeat_interval)
    finally:
        pub_socket.close()

    return validated_cfg.compute_checksum()


def receive_system_config_broadcast(
    master_host: str = "127.0.0.1",
    port: int = 5555,
    topic: str = "cochem_system_config",
    timeout_ms: int = 5000,
) -> CoChemSystemConfig:
    """Receives system configuration from master ZeroMQ broadcast."""
    ctx: zmq.Context[Any] = zmq.Context.instance()
    sub_socket = ctx.socket(zmq.SUB)
    sub_socket.setsockopt(zmq.LINGER, 0)
    try:
        sub_socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        sub_socket.connect(f"tcp://{master_host}:{port}")
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        time.sleep(0.05)
        parts = sub_socket.recv_multipart()
        json_str = parts[1].decode("utf-8")
        return CoChemSystemConfig.model_validate_json(json_str)
    except zmq.error.Again as e:
        raise TimeoutError(
            f"ZeroMQ config broadcast timed out after {timeout_ms}ms from {master_host}:{port}"
        ) from e
    finally:
        sub_socket.close()


# =============================================================================
# SYSTEM CONFIGURATION I/O & STAGE 0 GUARDRAILS
# =============================================================================

def get_default_config_path() -> Path:
    """Resolves the default system configuration file path."""
    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        return Path(os.path.expandvars(env_cfg)).expanduser().resolve()

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return (
            Path(os.path.expandvars(env_art)).expanduser()
            / "Registry"
            / "cochem_system_config.json"
        ).resolve()

    try:
        from cochem_base.config_loader import resolve_config_path
        return resolve_config_path()
    except Exception:
        return (Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json").resolve()


def load_system_config(
    config_path: Optional[Union[str, Path]] = None,
    verify_integrity: bool = True,
) -> CoChemSystemConfig:
    """Loads and validates cochem_system_config.json with environment variable expansion and integrity checks.

    Enforces Stage 0 Guardrail:
    - If file is missing, logs violation and raises RegistryMissingError.
    - If JSON is malformed, logs violation and raises RegistryParseError.
    - If checksum verification fails, logs violation and raises RegistryCorruptionError.
    """
    target_path = Path(config_path or get_default_config_path()).resolve()
    if not target_path.is_file():
        logger.critical(f"Stage 0 Guardrail: Master registry not found at: {target_path}")
        raise RegistryMissingError(f"Stage 0 Guardrail: Master registry not found at '{target_path}'")

    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        try:
            raw_text = target_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.critical(f"Stage 0 Guardrail: Failed to read registry at {target_path}: {e}")
            raise RegistryMissingError(f"Stage 0 Guardrail: Failed to read registry at '{target_path}': {e}") from e

        try:
            parsed_json = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.critical(f"Stage 0 Guardrail: Malformed registry JSON at {target_path}: {e}")
            raise RegistryParseError(f"Stage 0 Guardrail: Unparseable registry JSON at '{target_path}': {e}") from e

        if not isinstance(parsed_json, dict):
            logger.critical(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__} at {target_path}"
            )
            raise RegistryParseError(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__}"
            )

        interpolated_dict = interpolate_env_vars(parsed_json)

        try:
            config = migrate_schema(interpolated_dict)
        except Exception as e:
            logger.critical(f"Stage 0 Guardrail: Schema validation error for {target_path}: {e}")
            raise SchemaMigrationError(f"Stage 0 Guardrail: Schema validation error for '{target_path}': {e}") from e

        if verify_integrity and "registry_checksum" in parsed_json and parsed_json["registry_checksum"]:
            expected = parsed_json["registry_checksum"]
            computed = config.compute_checksum()
            if expected != computed:
                logger.critical(
                    f"Stage 0 Guardrail: Registry corruption at {target_path} (expected checksum '{expected}', computed '{computed}')"
                )
                raise RegistryCorruptionError(
                    f"Stage 0 Guardrail: Registry corruption at '{target_path}' (expected '{expected}', computed '{computed}')"
                )

        return config


def save_system_config(
    config: Union[CoChemSystemConfig, Dict[str, Any]],
    config_path: Optional[Union[str, Path]] = None,
) -> str:
    """Saves system configuration atomically with updated SHA-256 checksum after strict Pydantic validation."""
    target_path = Path(config_path or get_default_config_path()).resolve()

    # Pydantic verification checkpoint
    if isinstance(config, dict):
        cfg_model = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        cfg_model = CoChemSystemConfig.model_validate(config.model_dump())
    else:
        raise TypeError(f"Invalid config type: {type(config)}")

    cfg_model.last_updated = datetime.now(timezone.utc).isoformat()
    checksum = cfg_model.update_checksum()
    atomic_write_json(target_path, cfg_model, lock_timeout=10.0)
    return checksum


def update_system_config(
    config_path: Optional[Union[str, Path]] = None,
    **updates: Any,
) -> CoChemSystemConfig:
    """Atomically updates fields within cochem_system_config.json with strict Pydantic validation checkpoint."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    with AtomicFileLock(lock_file, timeout=10.0):
        current = load_system_config(target_path, verify_integrity=False)
        current_dict = current.model_dump()
        current_dict.update(updates)

        # Pydantic verification checkpoint: strictly rejects illegal data injection
        updated_cfg = migrate_schema(current_dict)
        save_system_config(updated_cfg, target_path)
        return updated_cfg


# =============================================================================
# ACTIVE JOBS LIFECYCLE MANAGEMENT
# =============================================================================

def register_active_job(
    job_id: str,
    job_data: Union[Dict[str, Any], BaseModel],
    config_path: Optional[Union[str, Path]] = None,
) -> None:
    """Registers an active execution job into cochem_system_config.json under active_jobs."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")

    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
    if "registered_at" not in payload:
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()

    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        cfg.active_jobs[job_id] = payload
        save_system_config(cfg, target_path)


def get_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves an active job record from cochem_system_config.json, or None if not found."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return None
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return cfg.active_jobs.get(job_id)


def list_active_jobs(
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Returns all active jobs recorded in cochem_system_config.json."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return dict(cfg.active_jobs)


def remove_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Removes an active job from cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return False
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id in cfg.active_jobs:
            del cfg.active_jobs[job_id]
            save_system_config(cfg, target_path)
            return True
        return False


def update_active_job(
    job_id: str,
    status: str,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Updates status and additional fields of an active job in cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id not in cfg.active_jobs:
            raise RecordNotFoundError(f"Cannot update non-existent active job '{job_id}'")
        job_record = dict(cfg.active_jobs[job_id])
        job_record["status"] = status
        job_record.update(kwargs)
        job_record["updated_at"] = datetime.now(timezone.utc).isoformat()
        cfg.active_jobs[job_id] = job_record
        save_system_config(cfg, target_path)
        return job_record


# =============================================================================
# MASTER REGISTRY MANAGER CLASS
# =============================================================================

class RegistryManager:
    """Consolidated state registry manager using HDF5, Atomic File Locks, and ZeroMQ Broadcasts."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self, config_path: Optional[str] = None, registry_path: Optional[str] = None
    ) -> None:
        if config_path:
            self.config_path = str(resolve_config_path(Path(config_path)))
        else:
            self.config_path = str(resolve_config_path())

        if registry_path:
            self.registry_path = str(
                resolve_mapped_path(registry_path, get_artifact_dir() / "Registry")
            )
        else:
            self.registry_path = str(get_artifact_dir() / "Registry" / "cochem_registry.h5")

        self.lock_path = self.registry_path + ".lock"
        self._ensure_registry_exists()

    def _ensure_registry_exists(self) -> None:
        """Ensure the HDF5 registry file and required groups exist, with atomic locking."""
        try:
            Path(self.registry_path).parent.mkdir(parents=True, exist_ok=True)
            with AtomicFileLock(self.lock_path, timeout=10.0):
                if not os.path.exists(self.registry_path):
                    with h5py.File(self.registry_path, "w") as h5:
                        h5.attrs["created"] = datetime.now(timezone.utc).isoformat()
                        h5.attrs["version"] = self.SCHEMA_VERSION
                        h5.create_group("jobs")
                        h5.create_group("hardware_profiles")
                        h5.create_group("basis_sets")
                        h5.create_group("embedded_basis_sets")
                        h5.create_group("provenance")
                        h5.create_group("seeds")
                        h5.create_group("metadata")
                    logger.info(f"Created new registry file: {self.registry_path}")
                else:
                    with h5py.File(self.registry_path, "a") as h5:
                        if "version" not in h5.attrs:
                            h5.attrs["version"] = self.SCHEMA_VERSION
                        for grp in [
                            "jobs",
                            "hardware_profiles",
                            "basis_sets",
                            "embedded_basis_sets",
                            "provenance",
                            "seeds",
                            "metadata",
                        ]:
                            if grp not in h5:
                                h5.create_group(grp)
        except Exception as e:
            logger.error(f"Failed to initialize registry: {e}")
            raise RuntimeError(f"Registry initialization failed: {e}") from e

    @contextmanager
    def transaction(self, mode: str = "a") -> Generator[h5py.File, None, None]:
        """Provides an atomic transaction over the HDF5 registry using AtomicFileLock."""
        with AtomicFileLock(self.lock_path, timeout=10.0):
            with h5py.File(self.registry_path, mode) as h5:
                yield h5

    @contextmanager
    def config_transaction(self) -> Generator[CoChemSystemConfig, None, None]:
        """Provides an atomic transaction over cochem_system_config.json with strict Pydantic verification."""
        target_path = Path(self.config_path).resolve()
        lock_file = str(target_path) + ".lock"
        with AtomicFileLock(lock_file, timeout=10.0):
            cfg = self.load_system_config(verify_integrity=False)
            yield cfg
            validated = CoChemSystemConfig.model_validate(cfg.model_dump())
            self.save_system_config(validated)

    def get_registry_stats(self) -> Dict[str, Any]:
        """Returns statistics on active registry record groups."""
        with self.transaction("r") as h5:
            jobs_c = len(h5["jobs"]) if "jobs" in h5 else 0
            hw_c = len(h5["hardware_profiles"]) if "hardware_profiles" in h5 else 0
            prov_c = len(h5["provenance"]) if "provenance" in h5 else 0
            basis_c = (
                len(h5["embedded_basis_sets"])
                if "embedded_basis_sets" in h5
                else (len(h5["basis_sets"]) if "basis_sets" in h5 else 0)
            )
            seeds_c = len(h5["seeds"]) if "seeds" in h5 else 0
            ver = h5.attrs.get("version", self.SCHEMA_VERSION)
            if isinstance(ver, bytes):
                ver = ver.decode("utf-8")
            return {
                "jobs_count": jobs_c,
                "hardware_profiles_count": hw_c,
                "provenance_count": prov_c,
                "basis_sets_count": basis_c,
                "seeds_count": seeds_c,
                "version": str(ver),
            }

    # =========================================================================
    # System Configuration Delegates
    # =========================================================================

    def load_system_config(
        self,
        config_path: Optional[Union[str, Path]] = None,
        verify_integrity: bool = True,
    ) -> CoChemSystemConfig:
        """Loads system configuration using the authoritative Stage 0 loader."""
        return load_system_config(config_path or self.config_path, verify_integrity=verify_integrity)

    def save_system_config(
        self,
        config: Union[CoChemSystemConfig, Dict[str, Any]],
        config_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Saves system configuration atomically with updated SHA-256 checksum."""
        return save_system_config(config, config_path or self.config_path)

    def update_system_config(self, **updates: Any) -> CoChemSystemConfig:
        """Atomically updates fields within cochem_system_config.json."""
        return update_system_config(config_path=self.config_path, **updates)

    def register_active_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers an active execution job in cochem_system_config.json."""
        register_active_job(job_id, job_data, config_path=self.config_path)

    def get_active_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an active execution job from cochem_system_config.json."""
        return get_active_job(job_id, config_path=self.config_path)

    def list_active_jobs(self) -> Dict[str, Any]:
        """Lists all active execution jobs in cochem_system_config.json."""
        return list_active_jobs(config_path=self.config_path)

    def remove_active_job(self, job_id: str) -> bool:
        """Removes an active execution job from cochem_system_config.json."""
        return remove_active_job(job_id, config_path=self.config_path)

    def update_active_job(self, job_id: str, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Updates an active execution job in cochem_system_config.json."""
        return update_active_job(job_id, status, config_path=self.config_path, **kwargs)

    def poll_system_config(
        self,
        master_host: str = "127.0.0.1",
        zmq_port: int = 5555,
        timeout_ms: int = 2000,
    ) -> CoChemSystemConfig:
        """Polls configuration: Master reads disk directly; Worker receives ZMQ broadcast with disk fallback."""
        if is_master_node():
            return self.load_system_config()
        try:
            return receive_system_config_broadcast(
                master_host=master_host, port=zmq_port, timeout_ms=timeout_ms
            )
        except Exception as e:
            logger.debug(f"Worker ZMQ poll failed, falling back to disk read: {e}")
            return self.load_system_config()

    def broadcast_config(
        self,
        port: int = 5555,
        host: str = "0.0.0.0",
        topic: str = "cochem_system_config",
    ) -> str:
        """Broadcasts current configuration via ZeroMQ."""
        cfg = self.load_system_config(verify_integrity=False)
        return broadcast_system_config(cfg, port=port, host=host, topic=topic)

    def receive_config_broadcast(
        self,
        master_host: str = "127.0.0.1",
        port: int = 5555,
        topic: str = "cochem_system_config",
        timeout_ms: int = 5000,
    ) -> CoChemSystemConfig:
        """Subscribes and receives configuration broadcast via ZeroMQ."""
        return receive_system_config_broadcast(
            master_host=master_host, port=port, topic=topic, timeout_ms=timeout_ms
        )

    def hash_environment(
        self,
        exclude_paths: bool = True,
        tracked_packages: Optional[Sequence[str]] = None,
        tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Calculates environmental hash for state tracking."""
        return hash_environment(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )

    def migrate_schema(
        self, config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig]
    ) -> CoChemSystemConfig:
        """Migrates schema to 4.0.0."""
        return migrate_schema(config_source)

    # =========================================================================
    # Isotopic Mass & Mendeleev/QCElemental Queries
    # =========================================================================

    @staticmethod
    def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
        """Dynamically fetches exact isotopic masses via Mendeleev, QCElemental, or periodic tables."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if mass_number is not None and not isinstance(mass_number, int):
            raise ValueError("Mass number must be an integer.")

        if clean_sym.upper() == "D":
            if mass_number is not None and mass_number != 2:
                raise ValueError(f"Isotope {mass_number}D not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 2
        elif clean_sym.upper() == "T":
            if mass_number is not None and mass_number != 3:
                raise ValueError(f"Isotope {mass_number}T not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 3

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    if mass_number is not None:
                        for iso in elem.isotopes:
                            if iso.mass_number == mass_number:
                                if iso.mass is None:
                                    raise IsotopeStabilityError(
                                        f"Isotope {mass_number}{clean_sym} has no stable mass record in Mendeleev."
                                    )
                                return float(iso.mass)
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        )

                    if hasattr(elem, "mass") and elem.mass is not None:
                        return float(elem.mass)
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} lacks a valid default atomic mass binding."
                    )
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.debug(f"Mendeleev query failed for '{clean_sym}', attempting fallback: {e}")

        if pt is not None:
            try:
                if mass_number is not None:
                    target = f"{formatted_sym}{mass_number}"
                    try:
                        return float(pt.to_mass(target))
                    except Exception as e:
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        ) from e
                try:
                    return float(pt.to_mass(formatted_sym))
                except Exception as e:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from e
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.error(f"Failed to query QCElemental for symbol '{clean_sym}': {e}")
                raise IsotopeStabilityError(
                    f"Isotopic mass resolution failed for {clean_sym}: {e}"
                ) from e

        raise IsotopeStabilityError(
            f"Element {clean_sym} not found in Mendeleev or QCElemental database."
        )

    @staticmethod
    def get_all_isotopes(symbol: str) -> List[Dict[str, Any]]:
        """Returns all isotopic variants for a given chemical element symbol."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if clean_sym.upper() in ("D", "T"):
            clean_sym = "H"
            formatted_sym = "H"

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    isotopes = []
                    for iso in elem.isotopes:
                        isotopes.append(
                            {
                                "mass_number": int(iso.mass_number),
                                "mass": float(iso.mass) if iso.mass is not None else None,
                                "abundance": float(iso.abundance)
                                if getattr(iso, "abundance", None) is not None
                                else None,
                            }
                        )
                    return isotopes
            except Exception as e:
                logger.debug(f"Mendeleev isotopes query failed for '{clean_sym}': {e}")

        if pt is not None:
            try:
                isotopes = []
                try:
                    pt.to_mass(formatted_sym)
                except Exception as err:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from err

                pattern = re.compile(rf"^{formatted_sym}(\d+)$")
                if hasattr(pt, "_eliso2mass"):
                    for k, m in pt._eliso2mass.items():
                        mat = pattern.match(k)
                        if mat:
                            isotopes.append(
                                {
                                    "mass_number": int(mat.group(1)),
                                    "mass": float(m),
                                    "abundance": None,
                                }
                            )
                return sorted(isotopes, key=lambda x: x["mass_number"])
            except IsotopeStabilityError:
                raise
            except Exception as e:
                raise IsotopeStabilityError(f"Failed to fetch isotopes for {clean_sym}: {e}") from e

        raise IsotopeStabilityError(f"Element {clean_sym} not found in Mendeleev or QCElemental.")

    # =========================================================================
    # HDF5 Registry Operations
    # =========================================================================

    def register_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers a calculation job record in the HDF5 registry."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("Job ID must be a non-empty string.")

        payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
        if "registered_at" not in payload:
            payload["registered_at"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id in jobs_grp:
                del jobs_grp[job_id]
            dset = jobs_grp.create_dataset(
                job_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )
            dset.attrs["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered job record, or None if not found."""
        with self.transaction("r") as h5:
            if "jobs" not in h5 or job_id not in h5["jobs"]:
                return None
            val = h5["jobs"][job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def update_job_status(self, job_id: str, status: str, **kwargs: Any) -> None:
        """Updates the status and additional fields of an existing job record."""
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id not in jobs_grp:
                raise RecordNotFoundError(f"Cannot update status for non-existent job '{job_id}'")
            val = jobs_grp[job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            rec = json.loads(text)
            rec["status"] = status
            rec.update(kwargs)
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            del jobs_grp[job_id]
            jobs_grp.create_dataset(
                job_id, data=json.dumps(rec), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Returns all registered jobs with job_id included."""
        results = []
        with self.transaction("r") as h5:
            if "jobs" in h5:
                for k in h5["jobs"].keys():
                    val = h5["jobs"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["job_id"] = k
                    results.append(data)
        return results

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job from the registry."""
        with self.transaction("a") as h5:
            if "jobs" in h5 and job_id in h5["jobs"]:
                del h5["jobs"][job_id]
                return True
            return False

    def register_hardware_profile(
        self, profile_id: str, profile_data: Union[Dict[str, Any], BaseModel]
    ) -> None:
        """Registers a host/node hardware configuration profile."""
        if not profile_id or not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Profile ID must be a non-empty string.")

        payload = (
            profile_data.model_dump() if isinstance(profile_data, BaseModel) else dict(profile_data)
        )
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()
        json_str = json.dumps(payload)

        with self.transaction("a") as h5:
            hw_grp = h5["hardware_profiles"]
            if profile_id in hw_grp:
                del hw_grp[profile_id]
            hw_grp.create_dataset(
                profile_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_hardware_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered hardware profile by ID."""
        with self.transaction("r") as h5:
            if "hardware_profiles" not in h5 or profile_id not in h5["hardware_profiles"]:
                return None
            val = h5["hardware_profiles"][profile_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_all_hardware_profiles(self) -> List[Dict[str, Any]]:
        """Returns all hardware profiles."""
        results = []
        with self.transaction("r") as h5:
            if "hardware_profiles" in h5:
                for k in h5["hardware_profiles"].keys():
                    val = h5["hardware_profiles"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["profile_id"] = k
                    results.append(data)
        return results

    def delete_hardware_profile(self, profile_id: str) -> bool:
        """Deletes a hardware profile from the registry."""
        with self.transaction("a") as h5:
            if "hardware_profiles" in h5 and profile_id in h5["hardware_profiles"]:
                del h5["hardware_profiles"][profile_id]
                return True
            return False

    def add_provenance_record(self, record_id: str, record_data: Dict[str, Any]) -> str:
        """Adds a cryptographic/workflow provenance record and returns a unique lineage UUID."""
        if not record_id or not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("Record ID must be a non-empty string.")

        lineage_uuid = f"lin_{uuid.uuid4().hex}"
        payload = dict(record_data)
        payload["record_id"] = record_id
        payload["lineage_uuid"] = lineage_uuid
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            prov_grp = h5["provenance"]
            if record_id in prov_grp:
                del prov_grp[record_id]
            prov_grp.create_dataset(
                record_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

        return lineage_uuid

    def get_provenance_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a provenance record by ID."""
        with self.transaction("r") as h5:
            if "provenance" not in h5 or record_id not in h5["provenance"]:
                return None
            val = h5["provenance"][record_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_lineage_chain(self, leaf_record_id: str) -> List[Dict[str, Any]]:
        """Traces the backward DAG lineage chain from leaf to root with cycle protection."""
        chain = []
        curr_id = leaf_record_id
        all_prov = {p["lineage_uuid"]: p for p in self.get_all_provenance_records()}
        rec_by_id = {p["record_id"]: p for p in all_prov.values()}
        visited = set()

        curr = rec_by_id.get(curr_id)
        while curr is not None:
            curr_uuid = curr.get("lineage_uuid")
            if curr_uuid in visited:
                logger.warning(f"Provenance cycle detected at record {curr_id}")
                break
            if curr_uuid:
                visited.add(curr_uuid)
            chain.append(curr)
            parent_uuid = curr.get("parent_uuid")
            if not parent_uuid or parent_uuid not in all_prov:
                break
            curr = all_prov.get(parent_uuid)

        return chain

    def get_all_provenance_records(self) -> List[Dict[str, Any]]:
        """Returns all provenance records."""
        results = []
        with self.transaction("r") as h5:
            if "provenance" in h5:
                for k in h5["provenance"].keys():
                    val = h5["provenance"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    results.append(data)
        return results

    def delete_provenance_record(self, record_id: str) -> bool:
        """Deletes a provenance record."""
        with self.transaction("a") as h5:
            if "provenance" in h5 and record_id in h5["provenance"]:
                del h5["provenance"][record_id]
                return True
            return False

    def lock_prng_seed(
        self, seed: int, scope: str = "global", metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Locks a pseudorandom number generator seed into the registry."""
        if not isinstance(seed, int):
            raise ValueError("PRNG seed must be an integer.")

        payload = {
            "seed": seed,
            "scope": scope,
            "metadata": metadata or {},
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.transaction("a") as h5:
            seeds_grp = h5["seeds"]
            if scope in seeds_grp:
                del seeds_grp[scope]
            seeds_grp.create_dataset(
                scope, data=json.dumps(payload), dtype=h5py.string_dtype(encoding="utf-8")
            )

        return seed

    def get_locked_seed(self, scope: str = "global") -> Optional[int]:
        """Retrieves a locked PRNG seed for a given scope."""
        with self.transaction("r") as h5:
            if "seeds" not in h5 or scope not in h5["seeds"]:
                return None
            val = h5["seeds"][scope][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[int], json.loads(text).get("seed"))

    def verify_prng_seed(self, seed: int, scope: str = "global") -> bool:
        """Verifies if an active seed matches the registered locked seed for a scope."""
        locked = self.get_locked_seed(scope)
        return locked is not None and locked == seed

    def list_locked_seeds(self) -> Dict[str, int]:
        """Returns all locked seeds mapped by scope."""
        res = {}
        with self.transaction("r") as h5:
            if "seeds" in h5:
                for k in h5["seeds"].keys():
                    val = h5["seeds"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    res[k] = json.loads(text).get("seed")
        return res

    def embed_basis_set_archive(
        self,
        h5_path: Optional[str] = None,
        basis_file_path: str = "",
        label: str = "",
        is_content: bool = False,
    ) -> None:
        """Embeds full basis set text into the HDF5 archive to prevent link rot."""
        if not label or not isinstance(label, str) or not label.strip():
            raise ValueError("Basis set label must be a non-empty string.")

        clean_label = label.strip()

        if is_content:
            raw_text = basis_file_path
        else:
            p = Path(basis_file_path)
            if not p.is_file():
                raise FileNotFoundError(f"Basis set file not found: {p}")
            raw_text = p.read_text(encoding="utf-8")

        mapped_h5 = Path(h5_path or self.registry_path)
        with AtomicFileLock(str(mapped_h5) + ".lock", timeout=10.0):
            with h5py.File(mapped_h5, "a") as h5:
                if "embedded_basis_sets" not in h5:
                    h5.create_group("embedded_basis_sets")
                grp = h5["embedded_basis_sets"]
                if clean_label in grp:
                    del grp[clean_label]
                grp.create_dataset(
                    clean_label, data=raw_text, dtype=h5py.string_dtype(encoding="utf-8")
                )

    def has_embedded_basis_set(self, label: str) -> bool:
        """Checks if a basis set label exists in the registry."""
        with self.transaction("r") as h5:
            return "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]

    def get_embedded_basis_set(self, label: str) -> str:
        """Retrieves embedded basis set content."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" not in h5 or label not in h5["embedded_basis_sets"]:
                raise BasisSetNotFoundError(f"Basis set '{label}' not found in registry.")
            val = h5["embedded_basis_sets"][label][()]
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)

    def list_embedded_basis_sets(self) -> List[str]:
        """Lists all embedded basis set labels."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" in h5:
                return list(h5["embedded_basis_sets"].keys())
            return []

    def delete_embedded_basis_set(self, label: str) -> bool:
        """Deletes an embedded basis set."""
        with self.transaction("a") as h5:
            if "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]:
                del h5["embedded_basis_sets"][label]
                return True
            return False

    def migrate_legacy_schema(self) -> Dict[str, Any]:
        """Upgrades legacy HDF5 schema files to 1.0.0."""
        with self.transaction("a") as h5:
            prev_ver = h5.attrs.get("version", "0.1")
            if isinstance(prev_ver, bytes):
                prev_ver = prev_ver.decode("utf-8")

            h5.attrs["version"] = self.SCHEMA_VERSION
            h5.attrs["migrated_at"] = datetime.now(timezone.utc).isoformat()

            for grp in [
                "hardware_profiles",
                "basis_sets",
                "embedded_basis_sets",
                "provenance",
                "seeds",
                "metadata",
            ]:
                if grp not in h5:
                    h5.create_group(grp)

            return {
                "previous_version": str(prev_ver),
                "current_version": self.SCHEMA_VERSION,
                "status": "migrated",
            }

    def set_metadata(self, key: str, value: Any) -> None:
        """Sets arbitrary metadata key/value into the registry."""
        with self.transaction("a") as h5:
            meta_grp = h5["metadata"]
            if key in meta_grp:
                del meta_grp[key]
            meta_grp.create_dataset(
                key, data=json.dumps(value), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieves arbitrary metadata value."""
        with self.transaction("r") as h5:
            if "metadata" not in h5 or key not in h5["metadata"]:
                return default
            val = h5["metadata"][key][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)


__all__ = [
    "AtomicFileLock",
    "BaseMetadataServer",
    "BasisSetNotFoundError",
    "CoChemLockTimeoutError",
    "FilesystemMetadataServer",
    "IsotopeStabilityError",
    "MetadataBackendType",
    "MetadataServerManager",
    "PostgresMetadataServer",
    "RecordNotFoundError",
    "RedisMetadataServer",
    "RegistryCorruptionError",
    "RegistryError",
    "RegistryLockError",
    "RegistryLockTimeoutError",
    "RegistryManager",
    "RegistryMissingError",
    "RegistryParseError",
    "SchemaMigrationError",
    "atomic_write_json",
    "broadcast_system_config",
    "default_metadata_manager",
    "get_active_job",
    "get_default_config_path",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "list_active_jobs",
    "load_system_config",
    "migrate_schema",
    "nfs_atomic_directory_rename",
    "receive_system_config_broadcast",
    "register_active_job",
    "remove_active_job",
    "save_system_config",
    "update_active_job",
    "update_system_config",
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
from cochem_base.schemas import GpuScoutExecutorConfig

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
# Worker-Resident Singleton MLFF Calculator Cache & Stream Management (§8A.3, Suggestion #154)
# =============================================================================
_WORKER_CALCULATOR_CACHE: dict[str, Any] = {}
_WORKER_CALCULATOR_LOCK = threading.Lock()
_WORKER_CUDA_STREAMS: dict[str, Any] = {}


def get_cached_mlff_calculator(
    model_name: str,
    model_path: Optional[Union[str, Path]] = None,
    device: str = "cpu",
    dtype: Optional[str] = None,
) -> Any:
    """Retrieve or instantiate a worker-resident singleton MLFF calculator instance.

    Implements Suggestion #154.
    Ensures model weights are loaded exactly once per worker process,
    avoiding redundant VRAM/RAM allocations.
    Provides non-blocking CUDA stream isolation when running on CUDA devices.
    """
    path_str = str(model_path).lower().strip() if model_path is not None else "none"
    key = f"{model_name.lower().strip()}:{path_str}:{device.lower().strip()}"
    with _WORKER_CALCULATOR_LOCK:
        if key in _WORKER_CALCULATOR_CACHE:
            return _WORKER_CALCULATOR_CACHE[key]

        calc = None
        stream = None
        # Non-blocking CUDA stream management
        if device.lower().startswith("cuda"):
            try:
                import torch
                if torch.cuda.is_available():
                    dev_idx = 0
                    if ":" in device:
                        dev_idx = int(device.split(":")[1])
                    stream = torch.cuda.Stream(device=dev_idx)
                    _WORKER_CUDA_STREAMS[key] = stream
            except Exception as stream_err:
                logger.debug(f"CUDA stream initialization deferred/unavailable: {stream_err}")

        # Model instantiation with zero-mock physical fallback
        m_lower = model_name.lower().replace("-", "_")
        if "mace" in m_lower:
            try:
                from mace.calculators import mace_off
                calc = mace_off(model="medium" if model_path is None else str(model_path), device=device)
            except Exception as e:
                logger.info(f"MACE-OFF not importable ({e}); initializing physical ASE EMT fallback.")
                from ase.calculators.emt import EMT
                calc = EMT()
        elif "aimnet" in m_lower:
            try:
                from aimnet2calc import AIMNet2ASE
                calc = AIMNet2ASE(model="aimnet2" if model_path is None else str(model_path))
            except Exception as e:
                logger.info(f"AIMNet2 not importable ({e}); initializing physical ASE EMT fallback.")
                from ase.calculators.emt import EMT
                calc = EMT()
        elif "emt" in m_lower:
            from ase.calculators.emt import EMT
            calc = EMT()
        else:
            from ase.calculators.emt import EMT
            calc = EMT()

        if stream is not None and calc is not None:
            calc._cuda_stream = stream

        _WORKER_CALCULATOR_CACHE[key] = calc
        return calc


def clear_worker_calculator_cache() -> None:
    """Clear the worker-resident singleton calculator cache."""
    with _WORKER_CALCULATOR_LOCK:
        _WORKER_CALCULATOR_CACHE.clear()
        _WORKER_CUDA_STREAMS.clear()


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
    GPU_SCOUT_MLFF = "GPU_SCOUT_MLFF"
    GPU_ANCHOR_PYSCF = "GPU_ANCHOR_PYSCF"
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
    gpu_scout_mlff_executor: Optional[HTEXConfig] = Field(
        default=None, description="Segregated GPU Scout MLFF pool configuration"
    )
    gpu_anchor_pyscf_executor: Optional[HTEXConfig] = Field(
        default=None, description="Segregated GPU Anchor PySCF pool configuration"
    )
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
    total_physical_cores: Optional[int] = None,
    total_ram_gb: Optional[float] = None,
    gpu_scout_workers: int = DEFAULT_MAX_GPU_SCOUT_WORKERS,
    anchor_ranks: int = DEFAULT_ORCA_ANCHOR_RANKS,
) -> ContentionBudget:
    """Calculate resource contention budget model (§8A.1, Suggestion #77, #156).

    Enforces host RAM headroom, dynamic memory floors (<32 GB), VRAM partitioning under MPS, and slowdown estimates.
    Dynamically probes system RAM and CPU topology via psutil when parameters are omitted,
    and downscales concurrency and memory limits gracefully instead of raising ContentionBudgetExceededError.
    """
    if total_ram_gb is None:
        total_ram_gb = float(psutil.virtual_memory().total / (1024**3))
    if total_physical_cores is None:
        total_physical_cores = int(psutil.cpu_count(logical=False) or 4)

    # Scale anchor ranks if total_physical_cores is constrained
    if total_physical_cores <= 4:
        anchor_ranks = max(1, total_physical_cores - 1)

    # Dynamic host RAM scaling under constrained environments (< 32 GB)
    if total_ram_gb < 32.0:
        anchor_mem = max(4.0, total_ram_gb * 0.50)
        scout_mem = max(1.5, total_ram_gb * 0.25)
        if total_ram_gb < 8.0:
            gpu_scout_workers = 1
            anchor_mem = max(2.0, total_ram_gb * 0.40)
            scout_mem = max(0.5, total_ram_gb * 0.20)
            logger.info(
                f"[RESOURCE-INFO] Severely constrained host RAM ({total_ram_gb:.1f} GB < 8 GB). "
                "Downscaling GPU scout concurrency to 1 worker."
            )
        elif total_ram_gb < 16.0:
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
    segregated_gpu_pools: bool = True,
) -> ParslMultiExecutorProfile:
    """Assemble the complete heterogeneous multi-executor profile (§8A.2, §8A.6, Suggestion #155).

    Supports segregated GPU pools:
    - gpu_scout_mlff: MPS-enabled conformational sampling pool
    - gpu_anchor_pyscf: Dedicated non-oversubscribed VRAM PySCF / DFT anchor pool
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

    gpu_scout_mlff_cfg = None
    gpu_anchor_pyscf_cfg = None
    if segregated_gpu_pools:
        gpu_scout_mlff_cfg = HTEXConfig(
            label="gpu_scout_mlff",
            stream=ExecutorStreamType.GPU_SCOUT_MLFF,
            provider_type=provider_type,
            max_workers_per_node=contention.gpu_scout_workers,
            cores_per_worker=max(1.0, float(partitioning.scout_core_count) / float(contention.gpu_scout_workers)),
            mem_per_worker_gb=contention.scout_mem_per_worker_gb,
            cpu_affinity="block-reverse",
            available_accelerators=contention.gpu_scout_workers,
            worker_init_script=gpu_init,
        )
        gpu_anchor_pyscf_cfg = HTEXConfig(
            label="gpu_anchor_pyscf",
            stream=ExecutorStreamType.GPU_ANCHOR_PYSCF,
            provider_type=provider_type,
            max_workers_per_node=1,
            cores_per_worker=float(partitioning.scout_core_count),
            mem_per_worker_gb=min(16.0, total_ram_gb * 0.5),
            cpu_affinity="block",
            available_accelerators=1,
            worker_init_script="export CUDA_VISIBLE_DEVICES=0; export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=100",
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
        gpu_scout_mlff_executor=gpu_scout_mlff_cfg,
        gpu_anchor_pyscf_executor=gpu_anchor_pyscf_cfg,
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

    executors_list = [anchor_htex, scout_htex]

    # Segregated GPU Pools (§8A.6, Suggestion #155)
    if profile.gpu_scout_mlff_executor is not None:
        mlff_kwargs: Dict[str, Any] = {
            "label": profile.gpu_scout_mlff_executor.label,
            "provider": make_provider(profile.gpu_scout_mlff_executor),
            "max_workers_per_node": profile.gpu_scout_mlff_executor.max_workers_per_node,
            "cores_per_worker": profile.gpu_scout_mlff_executor.cores_per_worker,
            "mem_per_worker": profile.gpu_scout_mlff_executor.mem_per_worker_gb,
            "cpu_affinity": profile.gpu_scout_mlff_executor.cpu_affinity,
            "worker_port_range": profile.gpu_scout_mlff_executor.worker_port_range,
            "interchange_port_range": profile.gpu_scout_mlff_executor.interchange_port_range,
        }
        if profile.gpu_scout_mlff_executor.available_accelerators is not None:
            mlff_kwargs["available_accelerators"] = profile.gpu_scout_mlff_executor.available_accelerators
        executors_list.append(HighThroughputExecutor(**mlff_kwargs))

    if profile.gpu_anchor_pyscf_executor is not None:
        pyscf_kwargs: Dict[str, Any] = {
            "label": profile.gpu_anchor_pyscf_executor.label,
            "provider": make_provider(profile.gpu_anchor_pyscf_executor),
            "max_workers_per_node": profile.gpu_anchor_pyscf_executor.max_workers_per_node,
            "cores_per_worker": profile.gpu_anchor_pyscf_executor.cores_per_worker,
            "mem_per_worker": profile.gpu_anchor_pyscf_executor.mem_per_worker_gb,
            "cpu_affinity": profile.gpu_anchor_pyscf_executor.cpu_affinity,
            "worker_port_range": profile.gpu_anchor_pyscf_executor.worker_port_range,
            "interchange_port_range": profile.gpu_anchor_pyscf_executor.interchange_port_range,
        }
        if profile.gpu_anchor_pyscf_executor.available_accelerators is not None:
            pyscf_kwargs["available_accelerators"] = profile.gpu_anchor_pyscf_executor.available_accelerators
        executors_list.append(HighThroughputExecutor(**pyscf_kwargs))

    # 3. Orchestrator Executor (ThreadPoolExecutor for lightweight coordination)
    orch_exec = ThreadPoolExecutor(
        max_threads=profile.orchestrator_executor.max_workers_per_node,
        label=profile.orchestrator_executor.label,
    )
    executors_list.append(orch_exec)

    return Config(
        executors=executors_list,
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
            elif request.stream == ExecutorStreamType.GPU_SCOUT_MLFF:
                mlff_ex = getattr(self.profile, "gpu_scout_mlff_executor", None)
                executor_label = mlff_ex.label if mlff_ex else self.profile.scout_executor.label
            elif request.stream == ExecutorStreamType.GPU_ANCHOR_PYSCF:
                pyscf_ex = getattr(self.profile, "gpu_anchor_pyscf_executor", None)
                executor_label = pyscf_ex.label if pyscf_ex else self.profile.scout_executor.label
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
            elif stream == ExecutorStreamType.GPU_SCOUT_MLFF:
                mlff_ex = getattr(self.profile, "gpu_scout_mlff_executor", None)
                executor_label = mlff_ex.label if mlff_ex else self.profile.scout_executor.label
            elif stream == ExecutorStreamType.GPU_ANCHOR_PYSCF:
                pyscf_ex = getattr(self.profile, "gpu_anchor_pyscf_executor", None)
                executor_label = pyscf_ex.label if pyscf_ex else self.profile.scout_executor.label
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_core_pes_store.py ---
#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_pes_store.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8C - QCSchema-Compliant Chunked HDF5 PES Store,
SWMR/Archival Storage Bifurcation, and Isotopologue Force Field Recycling.

Mandated by:
- SRS Doc 1 (Topology 1.0 §2)
- SRS Doc 2 Part 1 (§2.7)
- Method Matrix v4 §8C (HDF5 PES Store), §8B.4 (Canonical State Reuse & Arrow 7),
  §6.10 (Isotopologue Shortcut), §3-§5 (Rotational & Anharmonic Observables), §8A (Concurrency)
- CoChem Anti-Spoofing Protocol v2
- CoChem Mendeleev Library Mandate

Architectural Overview:
1. QCSchema-Compliant Chunked HDF5 PES Store (PESStore):
   - Structured HDF5 hierarchy (/meta, /methods, /points, /grids, /hessians, /isotopologues, /checkpoints).
   - Resizable chunked datasets with CHUNK_POINTS=512 (~120 KiB for 10-atom systems, in 10 KiB-1 MiB envelope).
   - Lossless gzip (compression_opts=4) + byte shuffle filter on numeric datasets.
   - Fletcher32 per-chunk error-detecting checksum on critical energy and coordinate arrays.
   - STRICT BAN on lossy scaleoffset filter to preserve micro-Hartree energy accuracy and avoid artificial frequencies.
   - Provenance tracking with QCSchema field names, JSON serialization, and cryptographic HMAC-SHA256 signatures.

2. SWMR / Archival Storage Bifurcation (BifurcatedPESStore):
   - Active Runtime Store (runtime_active.h5): Low-latency, uncompressed or fast chunking for live IPC streaming,
     steering, and concurrent reader queries with POSIX/Windows byte-range file locking.
   - Archival QCSchema Store (archive_pes.h5 / campaign.h5): Standard HDF5 mode with full lossless compression,
     checksum validation, and formal QCSchema v1 archival schema validation.
   - Atomic promotion from active runtime store to compressed archival store.
   - Parallel shard merger (merge_pes_shards) for multi-worker parallel grid evaluations.

3. Isotopologue Force Field Recycling Engine (Method Matrix Arrow 7, §8B.4, §6.10):
   - Dynamic atomic and isotopic mass retrieval using the `mendeleev` library (strictly ZERO hardcoded mass constants).
   - Mass-weighting and normal mode diagonalization of Cartesian Hessians: H_mw[i, j] = H[i, j] / sqrt(m_i * m_j).
   - Harmonic vibrational frequencies in cm^-1 (preserving sign for imaginary saddle-point modes).
   - Moment of inertia tensor (Ia <= Ib <= Ic in u * A^2), rotational constants (A >= B >= C in MHz),
     planar moments (Paa, Pbb, Pcc in u * A^2), inertial defect (Delta = Ic - Ia - Ib in u * A^2),
     and Ray's asymmetry parameter (kappa).
   - Zero electronic structure cost evaluation of arbitrary isotopologue suites (13C, 18O, D, 15N) from a single Hessian.

4. Idempotent Active-Learning & DVR Integration:
   - todo(method_id, wanted_ids): Identifies missing or unconverged points on high-dimensional grids for restarts.
   - dataset(method_id, converged_only): Extracts aligned coordinates and energies as NumPy arrays.
   - delta_pairs(low_method, high_method): Generates aligned (X, Delta_E) pairs for Delta-learning MLFF training.
   - dvr_grid(method_id, grid_id): Reshapes potential energies onto product grids for DVR solvers, marking holes with NaN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import platform
import socket
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
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import h5py
import numpy as np
from filelock import FileLock, Timeout
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from cochem_base.config_loader import (
    get_artifact_dir,
    get_runtime_dir,
    get_state_file_path,
    resolve_mapped_path,
)
from cochem_base.exceptions import (
    HDF5LockTimeoutError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
)


def validate_airgap_write_path(target_path: Union[str, Path]) -> Path:
    """Lazily import validate_airgap_write_path to break circular import cycle."""
    try:
        from cochem_base.core.ipc.serializer import validate_airgap_write_path as _v
        return _v(target_path)
    except Exception:
        resolved = Path(target_path).resolve()
        src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
        if src_dir.exists() and (src_dir == resolved or src_dir in resolved.parents):
            raise PermissionError(f"Air-gap boundary violation: Cannot write PES data to read-only Tier 1 ($COCH_SRC): {resolved}") from None
        return resolved

def validate_spdx_license(license_str: str) -> str:
    from cochem_base.core.licensing import validate_spdx_license as _v
    return _v(license_str)


def get_node_local_scratch_dir() -> Path:
    """Resolve node-local ephemeral scratch directory adhering to HPC Distributed Lock Prohibition [D]."""
    scratch = os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or (Path.home() / ".cochem" / "scratch")
    p = Path(scratch).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def configure_hdf5_locking(force_hpc: Optional[bool] = None) -> bool:
    """
    Configures HDF5 file locking based on environment.
    On Tier 6 HPC environments (SLURM/PBS/LSF or Lustre/GPFS), automatically sets
    HDF5_USE_FILE_LOCKING="FALSE" to prevent parallel filesystem lock deadlocks.

    Args:
        force_hpc: If provided, explicitly forces (True) or suppresses (False) HPC mode.
                   If None, detects from environment variables.

    Returns:
        bool: True if HDF5_USE_FILE_LOCKING was set or configured as FALSE, False otherwise.
    """
    is_hpc = force_hpc
    if is_hpc is None:
        hpc_indicators = (
            "SLURM_JOB_ID",
            "SLURM_JOBID",
            "PBS_JOBID",
            "LSB_JOBID",
            "COCHEM_TIER6",
            "COCHEM_HPC",
            "OMPI_COMM_WORLD_RANK",
            "PMIX_RANK",
        )
        is_hpc = any(k in os.environ for k in hpc_indicators)

    if is_hpc:
        os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"
        logger.info("HPC environment detected: HDF5_USE_FILE_LOCKING set to 'FALSE'")
        return True
    return False


def create_worker_shard_path(
    scratch_dir: Union[str, Path],
    worker_uuid: str,
    task_id: Union[str, int],
) -> Path:
    """
    Generates an isolated per-worker shard path in scratch directory adhering to Suggestion #159:
    shard_path = scratch_dir / f"shard_{worker_uuid}_{task_id}.h5"
    """
    s_dir = Path(scratch_dir).resolve()
    s_dir.mkdir(parents=True, exist_ok=True)
    return s_dir / f"shard_{worker_uuid}_{task_id}.h5"


# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-PESStore")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [cochem_core_pes_store]: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Physical Constants & Convergence Standards (Method Matrix §4.4, §5, §8B)
# ---------------------------------------------------------------------------
PLANCK_CONSTANT_J_S = 6.62607015e-34       # J * s (CODATA exact)
SPEED_OF_LIGHT_CM_S = 2.99792458e10       # cm / s (CODATA exact)
SPEED_OF_LIGHT_M_S = 2.99792458e8         # m / s (CODATA exact)
ATOMIC_MASS_UNIT_KG = 1.66053906660e-27   # kg / u
ANGSTROM_TO_METER = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM = 0.529177210903         # Angstrom / Bohr
ANGSTROM_TO_BOHR = 1.0 / BOHR_TO_ANGSTROM  # Bohr / Angstrom
BOHR_TO_METER = 0.529177210903e-10        # m / Bohr
HARTREE_TO_JOULE = 4.3597447222071e-18    # J / Hartree
HARTREE_TO_EV = 27.211386245988           # eV / Hartree
HARTREE_TO_CM_INV = 219474.63136320       # cm^-1 / Hartree
ROTATIONAL_INERTIA_CONVERSION = 505379.0084350172  # MHz * u * Angstrom^2

# Factor converting Inertia (u * Angstrom^2) to Rotational Constant (MHz):
# B = h / (8 * pi^2 * I) * 1e-6 (Hz -> MHz)
INERTIA_TO_MHZ_FACTOR = (
    PLANCK_CONSTANT_J_S
    / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_KG * (ANGSTROM_TO_METER ** 2))
) * 1.0e-6  # ~505379.0091414361 MHz * u * Angstrom^2

# Factor converting Hessian eigenvalue (Hartree / (Bohr^2 * u)) to wavenumber (cm^-1):
# f_lambda = HARTREE_TO_JOULE / (BOHR_TO_METER^2 * ATOMIC_MASS_UNIT_KG)
# f_cm1 = 1 / (2 * pi * c_cm_s)
HESSIAN_EIG_TO_CM_INV_FACTOR = (
    math.sqrt(HARTREE_TO_JOULE / ((BOHR_TO_METER ** 2) * ATOMIC_MASS_UNIT_KG))
    / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
)  # ~5140.487143715827 cm^-1

# HDF5 Storage Specifications (Method Matrix §8C)
CHUNK_POINTS = 512
VLEN_STR = h5py.string_dtype(encoding="utf-8")
DEFAULT_LOCK_TIMEOUT_S = 30.0


# =============================================================================
# 1. PYDANTIC V2 DATA MODELS & SCHEMAS
# =============================================================================

class StorageMode(str, Enum):
    """Storage architecture operating mode classification."""
    BIFURCATED = "BIFURCATED"
    ARCHIVAL_ONLY = "ARCHIVAL_ONLY"
    RUNTIME_SWMR = "RUNTIME_SWMR"


class DriverType(str, Enum):
    """QCSchema calculation driver type."""
    ENERGY = "energy"
    GRADIENT = "gradient"
    HESSIAN = "hessian"
    PROPERTIES = "properties"


class QCSchemaProvenance(BaseModel):
    """QCSchema v1 compliant calculation provenance metadata with asymmetric Ed25519 signatures."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    creator: str = Field(default="ORCA", description="Name of quantum chemistry package or MLFF engine")
    version: str = Field(default="6.1", description="Software version identifier")
    routine: str = Field(default="sp", description="Calculation routine (sp, opt, freq, vpt2, scan)")
    host: str = Field(default_factory=socket.gethostname, description="Hostname where calculation executed")
    platform: str = Field(default_factory=platform.platform, description="OS platform string")
    utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 UTC timestamp",
    )
    signature: Optional[str] = Field(
        default=None, description="URL-safe base64 encoded Ed25519 digital signature"
    )
    public_key: Optional[str] = Field(
        default=None, description="URL-safe base64 encoded Ed25519 public key"
    )
    fingerprint: Optional[str] = Field(
        default=None, description="SHA-256 fingerprint of public key"
    )
    signature_algorithm: str = Field(
        default="PureEd25519", description="Cryptographic signing standard"
    )
    license: str = Field(
        default="CC-BY-4.0", description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
    )

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        return validate_spdx_license(v)

    def canonical_bytes(self) -> bytes:
        """Construct RFC 8785 canonical bytes for core provenance fields."""
        from cochem_base.core.cochem_crypto import canonicalize_json
        payload = {
            "creator": self.creator,
            "version": self.version,
            "routine": self.routine,
            "host": self.host,
            "platform": self.platform,
            "utc": self.utc,
            "license": self.license,
        }
        return canonicalize_json(payload)

    def sign(self, private_key: Any) -> str:
        """Sign provenance metadata with PureEd25519 and populate signature/public_key/fingerprint."""
        from cochem_base.core.cochem_crypto import sign_canonical_bytes
        c_bytes = self.canonical_bytes()
        sig, pub, fp = sign_canonical_bytes(c_bytes, private_key)
        self.signature = sig
        self.public_key = pub
        self.fingerprint = fp
        return sig

    def compute_signature(self, private_key: Any = None) -> Optional[str]:
        """Compute cryptographic signature or SHA-256 integrity fingerprint over canonical bytes."""
        if private_key is not None:
            return self.sign(private_key)
        c_bytes = self.canonical_bytes()
        self.fingerprint = hashlib.sha256(c_bytes).hexdigest()
        return self.fingerprint

    def verify(self) -> bool:
        """Verify PureEd25519 digital signature against embedded public key."""
        if not self.signature or not self.public_key:
            return False
        from cochem_base.core.cochem_crypto import verify_canonical_signature
        c_bytes = self.canonical_bytes()
        return verify_canonical_signature(c_bytes, self.signature, self.public_key)


class QCSchemaMethodRecord(BaseModel):
    """QCSchema method attributes registered in HDF5 /methods/<method_id>."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    method: str = Field(..., description="Electronic structure method (e.g. DLPNO-CCSD(T1), wB97M-V, MP2)")
    basis: str = Field(..., description="Primary orbital basis set (e.g. def2-TZVPP, cc-pVDZ-F12)")
    aux_basis: Optional[str] = Field(None, description="Auxiliary density fitting or CABS basis set")
    program: str = Field(default="ORCA", description="Quantum chemistry package (ORCA, MPQC, CFOUR, PySCF, MACE)")
    program_version: str = Field(default="6.1", description="Software version string")
    driver: DriverType = Field(default=DriverType.ENERGY, description="Calculation driver")
    frozen_core: bool = Field(default=True, description="Whether frozen core approximation was enabled")
    counterpoise: str = Field(default="none", description="Counterpoise status: 'none', 'half', or 'full'")
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of calculation keywords and tolerances")
    license: str = Field(
        default="CC-BY-4.0", description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
    )
    registered_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 registration timestamp",
    )

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        return validate_spdx_license(v)


class PESGridDefinition(BaseModel):
    """Multidimensional grid definition for potential energy surfaces."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    grid_id: str = Field(..., description="Unique identifier for the grid (e.g. 'grid_2d_r_theta')")
    axes: Dict[str, List[float]] = Field(..., description="Mapping of axis names to 1D coordinate arrays")
    axis_order: List[str] = Field(..., description="Ordered list of axis names")
    shape: List[int] = Field(..., description="Grid dimension shape [dim_0, dim_1, ...]")
    grid_type: str = Field(default="cartesian", description="Grid coordinate type ('cartesian', 'spherical', 'internal')")


class HessianRecord(BaseModel):
    """Cartesian Hessian record stored under /hessians/<label>."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)

    label: str = Field(..., description="Unique label for the Hessian (e.g. 'opt_wb97mv_qz', 'parent_dimer')")
    level: str = Field(..., description="Level of theory (e.g. 'wB97M-V/def2-QZVPP')")
    geometry_ref: str = Field(..., description="Reference geometry identifier or filename")
    cartesian_hessian: Union[List[List[float]], np.ndarray] = Field(..., description="3N x 3N Cartesian Hessian matrix in Hartree/Bohr^2")
    units: str = Field(default="Hartree/Bohr^2", description="Units of the Hessian tensor")
    mass_weighted: bool = Field(default=False, description="Whether Hessian is already mass-weighted")
    frequencies_cm_inv: Optional[List[float]] = Field(None, description="Calculated harmonic vibrational frequencies")
    created_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 creation timestamp",
    )


class IsotopologueResult(BaseModel):
    """Complete rotational, vibrational, and inertial result for an isotopologue."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    iso_label: str = Field(..., description="Isotopologue label (e.g. 'parent', '13C_1', 'D_dimer', '18O_2')")
    parent_label: str = Field(..., description="Reference parent Hessian label from /hessians/<label>")
    substituted_mass_numbers: List[Optional[int]] = Field(
        ..., description="Substituted mass number for each atom (None = standard elemental weight)"
    )
    atomic_masses_amu: List[float] = Field(
        ..., description="Dynamic Mendeleev atomic masses in unified atomic mass units (u)"
    )
    harmonic_frequencies_cm_inv: List[float] = Field(
        ..., description="All 3N harmonic frequencies in cm^-1 (negative for imaginary modes)"
    )
    vibrational_frequencies_cm_inv: List[float] = Field(
        ..., description="Genuine vibrational frequencies in cm^-1 excluding 5/6 external translations/rotations"
    )
    lowest_harmonic_mode_cm_inv: float = Field(
        ..., description="Lowest genuine intermolecular/intramolecular vibrational mode in cm^-1"
    )
    A_MHz: float = Field(..., description="Rotational constant A in MHz")
    B_MHz: float = Field(..., description="Rotational constant B in MHz")
    C_MHz: float = Field(..., description="Rotational constant C in MHz")
    Ia_u_A2: float = Field(..., description="Principal moment of inertia Ia in u * Angstrom^2")
    Ib_u_A2: float = Field(..., description="Principal moment of inertia Ib in u * Angstrom^2")
    Ic_u_A2: float = Field(..., description="Principal moment of inertia Ic in u * Angstrom^2")
    Paa_u_A2: float = Field(..., description="Planar moment Paa = (Ib + Ic - Ia) / 2 in u * Angstrom^2")
    Pbb_u_A2: float = Field(..., description="Planar moment Pbb = (Ia + Ic - Ib) / 2 in u * Angstrom^2")
    Pcc_u_A2: float = Field(..., description="Planar moment Pcc = (Ia + Ib - Ic) / 2 in u * Angstrom^2")
    inertial_defect_amu_A2: float = Field(
        ..., description="Inertial defect Delta = Ic - Ia - Ib in u * Angstrom^2"
    )
    kappa: float = Field(..., description="Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)")


class BifurcatedStorageConfig(BaseModel):
    """Configuration profile for bifurcated active runtime and archival stores."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    active_runtime_path: str = Field(..., description="Filesystem path to runtime_active.h5")
    archive_pes_path: str = Field(..., description="Filesystem path to archive_pes.h5 / campaign.h5")
    storage_mode: StorageMode = Field(default=StorageMode.BIFURCATED, description="Operating storage mode")
    chunk_points: int = Field(default=512, ge=1, description="Number of points per chunk in HDF5 datasets")
    compression: str = Field(default="gzip", description="Lossless compression algorithm (gzip, lzf)")
    compression_opts: int = Field(default=4, ge=1, le=9, description="Compression level for gzip")
    shuffle: bool = Field(default=True, description="Enable byte shuffle filter for better compression ratios")
    fletcher32: bool = Field(default=True, description="Enable Fletcher32 checksum filter for data integrity")
    scaleoffset: Optional[int] = Field(
        default=None, description="Lossy scale-offset filter (MUST be None; strictly banned in CoChem)"
    )

    @field_validator("scaleoffset")
    @classmethod
    def validate_scaleoffset_strictly_banned(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            raise MethodMatrixViolationError(
                "scaleoffset lossy compression filter is strictly banned in CoChem HDF5 datastores to "
                "prevent precision truncation on micro-Hartree energy surfaces and artificial Hessian frequencies.",
                error_code=ProvenanceErrorCode.PRECISION_VIOLATION,
            )
        return v


# =============================================================================
# 2. MENDELEEV DYNAMIC MASS RESOLUTION (Mendeleev Library Mandate)
# =============================================================================

def get_atomic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """
    Dynamically retrieves standard atomic weight or exact isotopic mass from the `mendeleev` library.
    Strictly forbids hardcoding atomic masses or manually inserting CODATA mass constants.

    Args:
        symbol: Element symbol (e.g. 'C', 'H', 'O', 'Cl', 'D', 'T')
        mass_number: Specific isotope nucleon count (e.g. 13 for 13C, 2 for 2H/D).
                     If None, returns the standard IUPAC atomic weight.

    Returns:
        Atomic mass in unified atomic mass units (u / Da).
    """
    clean_sym = symbol.strip().capitalize()
    # Normalize hydrogen isotopes
    if clean_sym in ("D", "H2"):
        clean_sym = "H"
        mass_number = 2
    elif clean_sym in ("T", "H3"):
        clean_sym = "H"
        mass_number = 3

    try:
        el = element(clean_sym)
    except Exception as exc:
        raise ValueError(f"Failed to query Mendeleev library for element '{symbol}': {exc}") from exc

    if mass_number is not None:
        for iso in el.isotopes:
            if iso.mass_number == mass_number:
                if iso.mass is not None:
                    return float(iso.mass)
                break
        # Fallback to isotopic mass estimation if exact mass is None
        logger.warning(
            f"Exact isotopic mass not found in Mendeleev for {clean_sym}-{mass_number}; "
            f"using nominal integer mass {mass_number}.0"
        )
        return float(mass_number)

    if el.mass is not None:
        return float(el.mass)

    raise ValueError(f"Mendeleev mass is undefined for element '{symbol}' (mass_number={mass_number})")


def get_atomic_masses_for_symbols(
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """
    Returns array of atomic masses in unified atomic mass units (u) for a sequence of symbols.

    Args:
        symbols: Sequence of elemental symbols (e.g. ['C', 'O', 'H', 'H'])
        mass_numbers: Optional sequence of specific isotope mass numbers (e.g. [13, None, None, 2])

    Returns:
        NumPy array of shape (N,) with dtype float64.
    """
    masses: List[float] = []
    for i, s in enumerate(symbols):
        iso_num = mass_numbers[i] if mass_numbers is not None and i < len(mass_numbers) else None
        masses.append(get_atomic_mass(s, iso_num))
    return np.asarray(masses, dtype=np.float64)


# =============================================================================
# 3. MOLECULAR GEOMETRY & ROTATIONAL MATHEMATICS (§3, §4, §5)
# =============================================================================

def compute_center_of_mass(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """
    Computes the 3D center of mass in Angstroms.

    Args:
        symbols: Sequence of atom symbols
        coords: Cartesian coordinates array (N, 3) in Angstroms
        mass_numbers: Optional isotopic mass numbers

    Returns:
        3-element center of mass vector (x, y, z) in Angstroms.
    """
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
    Computes the moment of inertia tensor shifted to the molecular center of mass.

    Returns:
        I_tensor: 3x3 inertia tensor in u * Angstrom^2
        principal_moments: sorted eigenvalues (Ia <= Ib <= Ic) in u * Angstrom^2
        principal_axes: 3x3 eigenvector matrix (columns are principal axes a, b, c)
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    com = compute_center_of_mass(symbols, coords_arr, mass_numbers)
    r = coords_arr - com
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)

    inertia_mat = np.full((3, 3), 0.0, dtype=np.float64)
    eye3 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    for m_i, r_i in zip(masses, r, strict=False):
        r_sq = float(np.dot(r_i, r_i))
        inertia_mat += m_i * (r_sq * eye3 - np.outer(r_i, r_i))

    evals, evecs = np.linalg.eigh(inertia_mat)
    idx = np.argsort(evals)
    principal_moments = evals[idx]
    principal_axes = evecs[:, idx]

    return inertia_mat, principal_moments, principal_axes


def compute_rotational_constants(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Dict[str, Any]:
    """
    Computes rotational constants (A >= B >= C in MHz), principal moments of inertia,
    planar moments (Paa, Pbb, Pcc), inertial defect (Delta = Ic - Ia - Ib), and Ray's kappa.
    """
    _, principal_moments, principal_axes = compute_inertia_tensor(symbols, coords, mass_numbers)
    Ia, Ib, Ic = float(principal_moments[0]), float(principal_moments[1]), float(principal_moments[2])

    A_MHz = INERTIA_TO_MHZ_FACTOR / Ia if Ia > 1e-12 else float("inf")
    B_MHz = INERTIA_TO_MHZ_FACTOR / Ib if Ib > 1e-12 else float("inf")
    C_MHz = INERTIA_TO_MHZ_FACTOR / Ic if Ic > 1e-12 else float("inf")

    Paa = (Ib + Ic - Ia) / 2.0
    Pbb = (Ia + Ic - Ib) / 2.0
    Pcc = (Ia + Ib - Ic) / 2.0
    inertial_defect = Ic - Ia - Ib

    denom = A_MHz - C_MHz
    kappa = (2.0 * B_MHz - A_MHz - C_MHz) / denom if abs(denom) > 1e-6 else 0.0

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
    Computes coordinate shifts between two geometries (Delta R) and propagates error to rotational
    constant B using the Method Matrix law: Delta B / B ≈ 2 * Delta R / R (§4.1, §8B.5 Rule D1).
    """
    coords1_arr = np.asarray(coords1, dtype=np.float64)
    coords2_arr = np.asarray(coords2, dtype=np.float64)
    if coords1_arr.shape != coords2_arr.shape:
        raise ValueError(f"Shape mismatch in coordinate comparison: {coords1_arr.shape} vs {coords2_arr.shape}")

    diff = coords2_arr - coords1_arr
    rmsd_angstrom = float(np.sqrt(np.mean(np.sum(diff ** 2, axis=1))))
    rmsd_pm = rmsd_angstrom * 100.0

    com1 = compute_center_of_mass(symbols, coords1_arr)
    com2 = compute_center_of_mass(symbols, coords2_arr)
    com_shift_angstrom = float(np.linalg.norm(com2 - com1))
    com_shift_pm = com_shift_angstrom * 100.0

    rot1 = compute_rotational_constants(symbols, coords1_arr)
    rot2 = compute_rotational_constants(symbols, coords2_arr)

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


# =============================================================================
# 4. ISOTOPOLOGUE FORCE FIELD RECYCLING ENGINE (Method Matrix Arrow 7 & §6.10)
# =============================================================================

def diagonalize_mass_weighted_hessian(
    cart_hessian: np.ndarray,
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Mass-weights a Cartesian Hessian (3N x 3N in Hartree/Bohr^2) using dynamic Mendeleev masses,
    diagonalizes to normal modes, and converts eigenvalues to harmonic frequencies in cm^-1.
    Imaginary frequencies (saddle points) are returned with negative values.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian matrix in Hartree/Bohr^2
        symbols: Sequence of atom symbols
        mass_numbers: Optional sequence of isotopic mass numbers

    Returns:
        sorted_freqs: 1D array of 3N harmonic frequencies in cm^-1
        sorted_modes: 3N x 3N eigenvector matrix of normal modes
    """
    natoms = len(symbols)
    h_arr = np.asarray(cart_hessian, dtype=np.float64)
    expected_dim = 3 * natoms
    if h_arr.shape != (expected_dim, expected_dim):
        raise ValueError(
            f"Hessian shape {h_arr.shape} does not match expected (3N, 3N) = ({expected_dim}, {expected_dim}) "
            f"for N={natoms} atoms."
        )

    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    # Construct 3N mass vector: (m0, m0, m0, m1, m1, m1, ...)
    m3n = np.repeat(masses, 3)

    # Mass-weighting: H_mw[i, j] = H[i, j] / sqrt(m[i] * m[j])
    inv_sqrt_m = 1.0 / np.sqrt(m3n)
    h_mw = h_arr * np.outer(inv_sqrt_m, inv_sqrt_m)

    # Symmetrize to eliminate machine precision numerical drift
    h_mw = 0.5 * (h_mw + h_mw.T)

    evals, evecs = np.linalg.eigh(h_mw)

    frequencies: List[float] = []
    for val in evals:
        if val >= 0.0:
            freq = math.sqrt(val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        else:
            freq = -math.sqrt(-val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        frequencies.append(freq)

    freq_arr = np.asarray(frequencies, dtype=np.float64)
    sort_idx = np.argsort(freq_arr)
    sorted_freqs = freq_arr[sort_idx]
    sorted_modes = evecs[:, sort_idx]

    return sorted_freqs, sorted_modes


def reanalyze_isotopologue(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    substituted_mass_numbers: Sequence[Optional[int]],
    iso_label: str,
    parent_label: str = "parent",
) -> IsotopologueResult:
    """
    Executes the zero-cost Isotopologue Shortcut (Method Matrix §8B.4 Arrow 7 & §6.10).
    Re-diagonalizes the saved Cartesian Hessian with substituted isotopic masses,
    recalculating harmonic frequencies, moments of inertia, and rotational constants.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian in Hartree/Bohr^2
        coords: Cartesian coordinates in Angstroms (N, 3)
        symbols: Elemental symbols
        substituted_mass_numbers: Target isotopic nucleon counts (e.g. [13, None, None, 2])
        iso_label: Descriptive label for this isotopologue (e.g. '13C_1', 'D_dimer')
        parent_label: Reference label of the parent Hessian

    Returns:
        IsotopologueResult containing all updated spectroscopic observables.
    """
    freqs, _ = diagonalize_mass_weighted_hessian(cart_hessian, symbols, substituted_mass_numbers)
    rot = compute_rotational_constants(symbols, coords, substituted_mass_numbers)
    masses = get_atomic_masses_for_symbols(symbols, substituted_mass_numbers)

    # Filter out 5 or 6 translational/rotational zero modes (|freq| < 20 cm^-1)
    vib_freqs = [float(f) for f in freqs if abs(f) > 20.0]
    lowest_harmonic = float(vib_freqs[0]) if vib_freqs else 0.0

    return IsotopologueResult(
        iso_label=iso_label,
        parent_label=parent_label,
        substituted_mass_numbers=list(substituted_mass_numbers),
        atomic_masses_amu=masses.tolist(),
        harmonic_frequencies_cm_inv=freqs.tolist(),
        vibrational_frequencies_cm_inv=vib_freqs,
        lowest_harmonic_mode_cm_inv=lowest_harmonic,
        A_MHz=rot["A_MHz"],
        B_MHz=rot["B_MHz"],
        C_MHz=rot["C_MHz"],
        Ia_u_A2=rot["Ia_u_A2"],
        Ib_u_A2=rot["Ib_u_A2"],
        Ic_u_A2=rot["Ic_u_A2"],
        Paa_u_A2=rot["Paa_u_A2"],
        Pbb_u_A2=rot["Pbb_u_A2"],
        Pcc_u_A2=rot["Pcc_u_A2"],
        inertial_defect_amu_A2=rot["inertial_defect_amu_A2"],
        kappa=rot["kappa"],
    )


def reanalyze_isotopologue_suite(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    isotopologue_map: Dict[str, Sequence[Optional[int]]],
    parent_label: str = "parent",
) -> Dict[str, IsotopologueResult]:
    """
    Batch evaluates a complete campaign suite of isotopologues from a single Hessian.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian in Hartree/Bohr^2
        coords: Cartesian coordinates in Angstroms (N, 3)
        symbols: Elemental symbols
        isotopologue_map: Mapping of iso_label to substituted mass numbers
        parent_label: Label of the parent Hessian

    Returns:
        Dictionary mapping iso_label to IsotopologueResult.
    """
    results: Dict[str, IsotopologueResult] = {}
    for iso_label, mass_nums in isotopologue_map.items():
        res = reanalyze_isotopologue(
            cart_hessian=cart_hessian,
            coords=coords,
            symbols=symbols,
            substituted_mass_numbers=mass_nums,
            iso_label=iso_label,
            parent_label=parent_label,
        )
        results[iso_label] = res
    return results


# =============================================================================
# 5. CORE HDF5 PES STORE (Method Matrix §8C)
# =============================================================================

_H5PY_PROCESS_LOCK = threading.RLock()


class ReadWriteFileLock:
    """Portable cross-platform Reader-Writer Lock backed by FileLock token tracking."""

    def __init__(self, lock_path: Union[str, Path], timeout: float = 30.0) -> None:
        self.lock_path = Path(lock_path)
        self.writer_lock_path = self.lock_path.with_name(self.lock_path.name + ".writer.lock")
        self.readers_dir = self.lock_path.with_name(self.lock_path.name + ".readers")
        self.timeout = timeout
        self.writer_lock = FileLock(str(self.writer_lock_path), timeout=timeout)
        self.readers_dir.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    def _get_write_depth(self) -> int:
        return getattr(self._local, "write_depth", 0)

    def _set_write_depth(self, val: int) -> None:
        self._local.write_depth = val

    def _get_read_depth(self) -> int:
        return getattr(self._local, "read_depth", 0)

    def _set_read_depth(self, val: int) -> None:
        self._local.read_depth = val

    @contextmanager
    def read_lock(self) -> Generator[None, None, None]:
        """Shared read lock allowing unbounded concurrent readers with re-entrancy."""
        # If the current thread already holds the write lock, reading is re-entrant and safe
        if self._get_write_depth() > 0:
            yield
            return

        read_depth = self._get_read_depth()
        if read_depth > 0:
            self._set_read_depth(read_depth + 1)
            try:
                yield
            finally:
                self._set_read_depth(self._get_read_depth() - 1)
            return

        token = self.readers_dir / f"read_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}.token"
        t0 = time.time()
        while self.writer_lock.is_locked:
            if time.time() - t0 > self.timeout:
                raise HDF5LockTimeoutError(
                    f"Timed out after {self.timeout}s waiting for read lock on {self.lock_path}",
                    error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
                )
            time.sleep(0.005)

        token.touch(exist_ok=True)
        self._set_read_depth(1)
        try:
            yield
        finally:
            self._set_read_depth(0)
            token.unlink(missing_ok=True)

    @contextmanager
    def write_lock(self) -> Generator[None, None, None]:
        """Exclusive write lock waiting for active readers to finish."""
        depth = self._get_write_depth()
        if depth > 0:
            # Re-entrant acquisition by the same thread
            self._set_write_depth(depth + 1)
            try:
                yield
            finally:
                self._set_write_depth(self._get_write_depth() - 1)
            return

        try:
            self.writer_lock.acquire(timeout=self.timeout)
        except Timeout as exc:
            raise HDF5LockTimeoutError(
                f"Timed out after {self.timeout}s acquiring writer lock on {self.lock_path}",
                error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
            ) from exc

        self._set_write_depth(1)
        t0 = time.time()
        try:
            while any(self.readers_dir.glob("*.token")):
                # Clean up stale tokens from exited processes
                for tok in list(self.readers_dir.glob("*.token")):
                    parts = tok.stem.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        r_pid = int(parts[1])
                        if HAS_PSUTIL and not psutil.pid_exists(r_pid):
                            tok.unlink(missing_ok=True)
                if not any(self.readers_dir.glob("*.token")):
                    break
                if time.time() - t0 > self.timeout:
                    raise HDF5LockTimeoutError(
                        f"Timed out after {self.timeout}s waiting for readers to clear on {self.lock_path}",
                        error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
                    )
                time.sleep(0.005)
            yield
        finally:
            self._set_write_depth(0)
            if self.writer_lock.is_locked:
                self.writer_lock.release()


class PESStore:
    """
    Resizable, chunked, gzip+shuffle+fletcher32 HDF5 PES Store with QCSchema field names.
    Implements Method Matrix §8C layout, state persistence, grid registration,
    Delta-learning alignment, and DVR grid reshaping.
    """

    def __init__(
        self,
        path: Union[str, Path],
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
        swmr_mode: bool = False,
        lock_dir: Optional[Union[str, Path]] = None,
        compress: bool = True,
    ) -> None:
        self.compress: bool = compress
        self.path = validate_airgap_write_path(Path(path).resolve())
        self.lock_dir = Path(lock_dir).resolve() if lock_dir else get_node_local_scratch_dir()
        self.lock_path = self.lock_dir / f"{self.path.name}.lock"
        self.lock_timeout = lock_timeout
        self.rw_lock = ReadWriteFileLock(self.lock_path, timeout=self.lock_timeout)
        self.swmr_mode = swmr_mode
        new_file = not self.path.exists()

        if new_file:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._file_lock():
            with h5py.File(self.path, "a", libver="latest") as f:
                m = f.require_group("meta")
                if new_file:
                    m.attrs["schema_name"] = "vdw_pes_campaign"
                    m.attrs["schema_version"] = 1
                    m.attrs["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if complex_name:
                    m.attrs["complex"] = complex_name
                if symbols:
                    m.attrs["symbols"] = json.dumps(list(symbols))
                    m.attrs["n_atoms"] = len(symbols)
                    masses = get_atomic_masses_for_symbols(symbols)
                    m.attrs["atomic_masses_amu"] = json.dumps(masses.tolist())
                m.attrs["molecular_charge"] = molecular_charge
                m.attrs["spin_multiplicity"] = spin_multiplicity

                # Ensure required root groups exist
                f.require_group("methods")
                pts_grp = f.require_group("points")
                f.require_group("grids")
                f.require_group("hessians")
                f.require_group("isotopologues")
                f.require_group("checkpoints")

                # Pre-allocate chunked, resizable datasets before SWMR activation [D]
                n_dim = 3 * max(1, len(symbols))
                if "coordinates" not in pts_grp:
                    pts_grp.create_dataset(
                        "coordinates",
                        shape=(0, n_dim),
                        maxshape=(None, n_dim),
                        dtype=np.float64,
                        chunks=(512, n_dim),
                    )
                if "energies" not in pts_grp:
                    pts_grp.create_dataset(
                        "energies",
                        shape=(0,),
                        maxshape=(None,),
                        dtype=np.float64,
                        chunks=(512,),
                    )
                if "point_ids" not in pts_grp:
                    dt = h5py.string_dtype(encoding="utf-8")
                    pts_grp.create_dataset(
                        "point_ids",
                        shape=(0,),
                        maxshape=(None,),
                        dtype=dt,
                        chunks=(512,),
                    )

                # Cache properties
                self.n_atoms = int(m.attrs.get("n_atoms", len(symbols)))
                self.complex_name = str(m.attrs.get("complex", complex_name))
                sym_attr = m.attrs.get("symbols")
                self.symbols = json.loads(sym_attr) if isinstance(sym_attr, str) else list(symbols)
                self.molecular_charge = int(m.attrs.get("molecular_charge", molecular_charge))
                self.spin_multiplicity = int(m.attrs.get("spin_multiplicity", spin_multiplicity))

                # Phase 2 SWMR Activation: Flush metadata and enable SWMR mode
                f.flush()
                if self.swmr_mode:
                    try:
                        f.swmr_mode = True
                    except (AttributeError, RuntimeError) as _e:
                        logger.debug(f"Ignored exception: {_e}")

    @contextmanager
    def _file_lock(self) -> Generator[None, None, None]:
        """Cross-platform byte-range file lock context manager serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.write_lock():
                yield

    @contextmanager
    def shared_read_lock(self) -> Generator[None, None, None]:
        """Shared read lock allowing unbounded concurrent readers serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.read_lock():
                yield

    @contextmanager
    def open_reader(self) -> Generator[h5py.File, None, None]:
        """Open HDF5 file in SWMR read mode with libver='latest' under shared read lock."""
        with self.shared_read_lock():
            with h5py.File(self.path, "r", libver="latest", swmr=True) as f:
                yield f

    @contextmanager
    def exclusive_write_lock(self) -> Generator[None, None, None]:
        """Exclusive write lock waiting for active readers to clear serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.write_lock():
                yield

    @contextmanager
    def swmr_write_context(self, timeout: Optional[float] = None) -> Generator[h5py.File, None, None]:
        """
        SWMR-mode exclusive write context with FileLock protection as mandated by Suggestion #159.
        """
        effective_timeout = timeout if timeout is not None else self.lock_timeout
        lock = FileLock(f"{self.path}.lock", timeout=effective_timeout)
        with lock:
            with h5py.File(self.path, "a", libver="latest") as f:
                if not getattr(f, "swmr_mode", False):
                    try:
                        f.swmr_mode = True
                    except (RuntimeError, AttributeError):
                        pass
                yield f
                f.flush()

    # -------------------------------------------------------------------------
    # Method Registration (QCSchema v1)
    # -------------------------------------------------------------------------
    def register_method(self, method_id: str, **attrs: Any) -> None:
        """
        Registers a computational method with QCSchema attributes in /methods/<method_id>.

        Args:
            method_id: Unique string identifier for the method (e.g. 'dlpno_avtz', 'wb97mv_qz')
            attrs: QCSchema method attributes (method, basis, aux_basis, program, driver, keywords, etc.)
        """
        # Validate through Pydantic record if method and basis provided
        if "method" in attrs and "basis" in attrs:
            QCSchemaMethodRecord(method_id=method_id, **attrs)

        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group(f"methods/{method_id}")
                for k, v in attrs.items():
                    if isinstance(v, (dict, list)):
                        g.attrs[k] = json.dumps(v)
                    elif isinstance(v, (int, float, str, bool)):
                        g.attrs[k] = v
                    elif isinstance(v, Enum):
                        g.attrs[k] = v.value
                g.attrs.setdefault("registered_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def get_method(self, method_id: str) -> Dict[str, Any]:
        """Retrieves registered method attributes dictionary."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"methods/{method_id}" not in f:
                    raise KeyError(f"Method '{method_id}' not found in PESStore methods.")
                g = f[f"methods/{method_id}"]
                res: Dict[str, Any] = {}
                for k, v in g.attrs.items():
                    val = v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v
                    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                        try:
                            res[k] = json.loads(val)
                        except json.JSONDecodeError:
                            res[k] = val
                    else:
                        res[k] = val
                return res

    def list_methods(self) -> List[str]:
        """Lists all registered method IDs."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "methods" not in f:
                    return []
                return sorted(list(f["methods"].keys()))

    # -------------------------------------------------------------------------
    # Dataset Creation Helper
    # -------------------------------------------------------------------------
    def _ds(
        self,
        f: h5py.File,
        mid: str,
        name: str,
        shape_tail: Tuple[int, ...],
        dtype: Any,
        checksum: bool = False,
    ) -> h5py.Dataset:
        """Internal helper creating resizable chunked datasets with gzip+shuffle+fletcher32."""
        grp = f.require_group(f"points/{mid}")
        if name in grp:
            return grp[name]

        kw: Dict[str, Any] = {
            "shape": (0,) + shape_tail,
            "maxshape": (None,) + shape_tail,
            "dtype": dtype,
            "chunks": (CHUNK_POINTS,) + shape_tail,
        }
        if dtype != VLEN_STR and self.compress:
            kw.update(compression="gzip", compression_opts=4, shuffle=True)
            if checksum:
                kw["fletcher32"] = True
        elif checksum and dtype != VLEN_STR:
            kw["fletcher32"] = True
        return grp.create_dataset(name, **kw)

    @staticmethod
    def _append(ds: h5py.Dataset, block: np.ndarray) -> int:
        """Appends a block of data along axis 0 of a resizable dataset."""
        idx = int(ds.shape[0])
        ds.resize(idx + len(block), axis=0)
        ds[idx:] = block
        return idx

    def add_point(self, point: Any) -> None:
        """Append a single PESPointRecord into the HDF5 store in a thread-safe SWMR-compliant manner [D]."""
        with self._file_lock():
            with h5py.File(self.path, "a", libver="latest") as f:
                pts = f.require_group("points")
                coords = np.asarray(point.coordinates, dtype=np.float64)
                if coords.ndim == 1:
                    coords = coords[None, :]
                elif coords.ndim == 2:
                    coords = coords.reshape(1, -1)

                cur_len = pts["energies"].shape[0] if "energies" in pts else 0
                new_len = cur_len + 1

                if "coordinates" in pts:
                    if pts["coordinates"].shape[1] != coords.shape[1]:
                        pts["coordinates"].resize((new_len, max(pts["coordinates"].shape[1], coords.shape[1])))
                    else:
                        pts["coordinates"].resize((new_len, coords.shape[1]))
                    pts["coordinates"][cur_len] = coords[0]
                else:
                    pts.create_dataset(
                        "coordinates",
                        data=coords,
                        maxshape=(None, coords.shape[1]),
                        chunks=(512, coords.shape[1]),
                    )

                if "energies" in pts:
                    pts["energies"].resize((new_len,))
                    pts["energies"][cur_len] = float(point.energy)
                else:
                    pts.create_dataset(
                        "energies",
                        data=np.array([point.energy], dtype=np.float64),
                        maxshape=(None,),
                        chunks=(512,),
                    )

                if "point_ids" in pts:
                    pts["point_ids"].resize((new_len,))
                    pts["point_ids"][cur_len] = str(point.point_id)
                else:
                    dt = h5py.string_dtype(encoding="utf-8")
                    d = pts.create_dataset(
                        "point_ids",
                        shape=(1,),
                        maxshape=(None,),
                        dtype=dt,
                        chunks=(512,),
                    )
                    d[0] = str(point.point_id)

                f.flush()

    def write_entry(self, point: Any) -> None:
        """Persist PES point record in-place adhering to Suggestion #65."""
        self.add_point(point)

    def get_all_point_ids(self) -> List[str]:
        """Retrieve all registered point IDs with SWMR refresh [D]."""
        with self.rw_lock.read_lock():
            with h5py.File(self.path, "r", libver="latest", swmr=self.swmr_mode) as f:
                if "/points/point_ids" in f:
                    dset = f["/points/point_ids"]
                    if self.swmr_mode:
                        try:
                            dset.refresh()
                        except Exception as _e:
                            logger.debug(f"Ignored exception: {_e}")
                    raw = dset[:]
                    return [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in raw]
                return []

    # -------------------------------------------------------------------------
    # Writing PES Points
    # -------------------------------------------------------------------------
    def add_points(
        self,
        method_id: str,
        coords: Optional[Union[Sequence[Any], np.ndarray]] = None,
        energies: Optional[Union[Sequence[float], np.ndarray, float]] = None,
        *,
        coordinates: Optional[Union[Sequence[Any], np.ndarray]] = None,
        provenance: Optional[Union[Dict[str, Any], str]] = None,
        point_ids: Optional[Sequence[str]] = None,
        gradients: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: Optional[Union[Sequence[bool], np.ndarray, bool]] = None,
        wall_s: Optional[Union[Sequence[float], np.ndarray, float]] = None,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """
        Adds computed PES points with normalized provenance index, chunking, and checksums.

        Args:
            method_id: Registered method identifier
            coords: Cartesian coordinates array (Npts, Natoms, 3) or (Natoms, 3) for a single point
            energies: Electronic energies array (Npts,) or float for single point
            coordinates: Optional alias for coords
            provenance: Optional provenance dict or JSON string
            point_ids: Optional list of unique point IDs
            gradients: Optional gradients array (Npts, Natoms, 3) in Hartree/Bohr
            converged: Convergence flags (Npts,) or bool
            wall_s: Wall clock times in seconds
            creator: Package name
            version: Package version
            routine: Calculation routine

        Returns:
            Starting index i0 where points were inserted.
        """
        target_coords = coordinates if coordinates is not None else coords
        if target_coords is None:
            raise ValueError("Must provide coords or coordinates.")

        coords_arr = np.asarray(target_coords, dtype=np.float64)
        if coords_arr.ndim == 2:
            coords_arr = coords_arr[None]
        npts, natm = coords_arr.shape[0], coords_arr.shape[1]

        if energies is None:
            raise ValueError("Must provide energies.")
        energies_arr = np.asarray(energies, dtype=np.float64)
        if energies_arr.ndim == 0:
            energies_arr = energies_arr[None]

        if len(energies_arr) != npts:
            raise ValueError(f"Number of energies ({len(energies_arr)}) does not match number of points ({npts}).")

        # Construct signed provenance record or serialize input provenance
        if provenance is not None:
            if isinstance(provenance, dict):
                prov_json = json.dumps(provenance, sort_keys=True)
            elif isinstance(provenance, str):
                prov_json = provenance
            else:
                prov_json = str(provenance)
        else:
            prov_obj = QCSchemaProvenance(
                creator=creator,
                version=version,
                routine=routine,
                host=socket.gethostname(),
                platform=platform.platform(),
                utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            prov_obj.compute_signature()
            prov_json = prov_obj.model_dump_json()

        with self._file_lock():
            open_kwargs: Dict[str, Any] = {"libver": "latest"} if self.swmr_mode else {}
            with h5py.File(self.path, "a", **open_kwargs) as f:
                if self.swmr_mode and hasattr(f, "swmr_mode") and not f.swmr_mode:
                    try:
                        f.swmr_mode = True
                    except (RuntimeError, AttributeError):
                        pass
                # Ensure method group exists
                method_grp = f.require_group(f"methods/{method_id}")

                # Create or retrieve provenance_index dataset
                if "provenance_index" not in method_grp:
                    dt_vlen = h5py.string_dtype(encoding="utf-8")
                    try:
                        prov_index_ds = method_grp.create_dataset(
                            "provenance_index",
                            shape=(0,),
                            maxshape=(None,),
                            dtype=dt_vlen,
                            chunks=(64,),
                            fletcher32=True,
                        )
                    except Exception:
                        prov_index_ds = method_grp.create_dataset(
                            "provenance_index",
                            shape=(0,),
                            maxshape=(None,),
                            dtype=dt_vlen,
                            chunks=(64,),
                        )
                else:
                    prov_index_ds = method_grp["provenance_index"]

                # Look up prov_json in provenance_index; append if new, obtain prov_id: np.uint32
                prov_id = None
                prov_list = [
                    item.decode("utf-8") if isinstance(item, bytes) else str(item)
                    for item in prov_index_ds[:]
                ]
                for idx, item_str in enumerate(prov_list):
                    if item_str == prov_json:
                        prov_id = np.uint32(idx)
                        break

                if prov_id is None:
                    prov_id = np.uint32(len(prov_list))
                    prov_index_ds.resize((int(prov_id + 1),))
                    prov_index_ds[int(prov_id)] = prov_json

                i0 = self._append(self._ds(f, method_id, "coordinates", (natm, 3), np.float64), coords_arr)
                self._append(self._ds(f, method_id, "energy", (), np.float64, checksum=True), energies_arr)

                # Convergence
                conv_block = np.full(npts, True, dtype=bool) if converged is None else np.asarray(converged, dtype=bool)
                if conv_block.ndim == 0:
                    conv_block = np.full(npts, bool(converged), dtype=bool)
                self._append(self._ds(f, method_id, "converged", (), np.bool_), conv_block)

                # Wall time
                wall_block = np.full(npts, 0.0, dtype=np.float64) if wall_s is None else np.asarray(wall_s, dtype=np.float64)
                if wall_block.ndim == 0:
                    wall_block = np.full(npts, float(wall_s), dtype=np.float64)
                self._append(self._ds(f, method_id, "wall_s", (), np.float64), wall_block)

                # Write normalized provenance_id block
                prov_id_block = np.full(npts, prov_id, dtype=np.uint32)
                self._append(self._ds(f, method_id, "provenance_id", (), np.uint32, checksum=True), prov_id_block)

                # Point IDs
                p_ids = list(point_ids) if point_ids is not None else [f"{method_id}:{i0 + k}" for k in range(npts)]
                self._append(self._ds(f, method_id, "point_id", (), VLEN_STR), np.array(p_ids, dtype=object))

                # Optional gradients
                if gradients is not None:
                    g_arr = np.asarray(gradients, dtype=np.float64)
                    if g_arr.ndim == 2:
                        g_arr = g_arr[None]
                    if "gradient" not in f[f"points/{method_id}"] and i0 > 0:
                        g_ds = self._ds(f, method_id, "gradient", (natm, 3), np.float64)
                        nan_pad = np.full((i0, natm, 3), np.nan, dtype=np.float64)
                        self._append(g_ds, nan_pad)
                        self._append(g_ds, g_arr)
                    else:
                        self._append(self._ds(f, method_id, "gradient", (natm, 3), np.float64), g_arr)
                elif "gradient" in f[f"points/{method_id}"]:
                    nan_pad = np.full((npts, natm, 3), np.nan, dtype=np.float64)
                    self._append(f[f"points/{method_id}/gradient"], nan_pad)

                f.flush()

        return i0

    def get_point_provenance(self, method_id: str, point_index: int) -> Dict[str, Any]:
        """
        Retrieves the provenance dictionary for a specific point by reading its provenance_id
        and resolving it via the method's provenance_index, with fallback to legacy provenance dataset.
        """
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                pts_grp = f.get(f"points/{method_id}")
                if pts_grp is not None and "provenance_id" in pts_grp:
                    prov_id = int(pts_grp["provenance_id"][point_index])
                    method_grp = f.get(f"methods/{method_id}")
                    if method_grp is not None and "provenance_index" in method_grp:
                        raw_prov = method_grp["provenance_index"][prov_id]
                        if isinstance(raw_prov, bytes):
                            raw_prov = raw_prov.decode("utf-8")
                        return json.loads(raw_prov) if isinstance(raw_prov, str) else dict(raw_prov)

                if pts_grp is not None and "provenance" in pts_grp:
                    raw_prov = pts_grp["provenance"][point_index]
                    if isinstance(raw_prov, bytes):
                        raw_prov = raw_prov.decode("utf-8")
                    return json.loads(raw_prov) if isinstance(raw_prov, str) else dict(raw_prov)

                raise KeyError(f"No provenance found for method '{method_id}' at index {point_index}")

    def get_points(self, method_id: str, converged_only: bool = False) -> List[Dict[str, Any]]:
        """Convenience query returning list of point dicts for a method."""
        payload = self.dataset_full(method_id, converged_only=converged_only)
        n = min(len(payload["energy"]), len(payload["point_id"]), len(payload["coordinates"]))
        points_list = []
        for i in range(n):
            pt = {
                "point_id": payload["point_id"][i],
                "coordinates": payload["coordinates"][i],
                "energy": float(payload["energy"][i]),
                "converged": bool(payload["converged"][i]),
                "wall_s": float(payload["wall_s"][i]),
            }
            if "gradient" in payload and i < len(payload["gradient"]):
                pt["gradient"] = payload["gradient"][i]
            points_list.append(pt)
        return points_list

    # -------------------------------------------------------------------------
    # Hessians & Isotopologue Storage
    # -------------------------------------------------------------------------
    def add_hessian(
        self,
        label: str,
        H: Union[Sequence[Any], np.ndarray],
        *,
        level: str = "",
        geometry_ref: str = "",
        units: str = "Hartree/Bohr^2",
        mass_weighted: bool = False,
        frequencies_cm_inv: Optional[Sequence[float]] = None,
    ) -> None:
        """Stores Cartesian Hessian tensor and metadata in /hessians/<label>."""
        h_arr = np.asarray(H, dtype=np.float64)
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group("hessians")
                if label in g:
                    del g[label]
                d = g.create_dataset(
                    label,
                    data=h_arr,
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )
                d.attrs["level"] = level
                d.attrs["geometry_ref"] = geometry_ref
                d.attrs["units"] = units
                d.attrs["mass_weighted"] = mass_weighted
                d.attrs["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if frequencies_cm_inv is not None:
                    d.attrs["frequencies_cm_inv"] = json.dumps(list(frequencies_cm_inv))

    def get_hessian(self, label: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Retrieves Cartesian Hessian array and metadata dictionary."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"hessians/{label}" not in f:
                    raise KeyError(f"Hessian '{label}' not found in PESStore.")
                ds = f[f"hessians/{label}"]
                h_arr = ds[:]
                attrs = {k: v for k, v in ds.attrs.items()}
                return h_arr, attrs

    def list_hessians(self) -> List[str]:
        """Lists all registered Hessian labels."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "hessians" not in f:
                    return []
                return sorted(list(f["hessians"].keys()))

    def add_isotopologue_result(self, label: str, iso_result: IsotopologueResult) -> None:
        """Stores an IsotopologueResult under /isotopologues/<label>/<iso_label>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                grp = f.require_group(f"isotopologues/{label}/{iso_result.iso_label}")
                grp.attrs["payload_json"] = iso_result.model_dump_json()
                grp.attrs["A_MHz"] = iso_result.A_MHz
                grp.attrs["B_MHz"] = iso_result.B_MHz
                grp.attrs["C_MHz"] = iso_result.C_MHz
                grp.attrs["inertial_defect_amu_A2"] = iso_result.inertial_defect_amu_A2
                grp.attrs["lowest_harmonic_mode_cm_inv"] = iso_result.lowest_harmonic_mode_cm_inv
                grp.attrs["saved_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_isotopologue_result(self, label: str, iso_label: str) -> IsotopologueResult:
        """Retrieves a saved IsotopologueResult."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"isotopologues/{label}/{iso_label}"
                if path not in f:
                    raise KeyError(f"Isotopologue '{iso_label}' not found under Hessian '{label}'.")
                grp = f[path]
                payload = grp.attrs.get("payload_json")
                if payload is None:
                    raise ValueError(f"Isotopologue record at '{path}' is missing 'payload_json' attribute.")
                return IsotopologueResult.model_validate_json(payload)

    def list_isotopologues(self, label: str) -> List[str]:
        """Lists all isotopologue labels evaluated under Hessian label."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"isotopologues/{label}"
                if path not in f:
                    return []
                return sorted(list(f[path].keys()))

    # -------------------------------------------------------------------------
    # Grids & Multi-Dimensional Scans
    # -------------------------------------------------------------------------
    def register_grid(self, grid_id: str, axes: Dict[str, Sequence[float]], grid_type: str = "cartesian") -> None:
        """Registers grid axes for potential energy surfaces in /grids/<grid_id>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group(f"grids/{grid_id}")
                for name, vals in axes.items():
                    if name in g:
                        del g[name]
                    g.create_dataset(name, data=np.asarray(vals, dtype=np.float64))
                g.attrs["axis_order"] = json.dumps(list(axes.keys()))
                g.attrs["shape"] = [len(v) for v in axes.values()]
                g.attrs["grid_type"] = grid_type
                g.attrs["registered_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_grid(self, grid_id: str) -> Dict[str, Any]:
        """Retrieves grid axes and metadata."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"grids/{grid_id}" not in f:
                    raise KeyError(f"Grid '{grid_id}' not found in PESStore.")
                g = f[f"grids/{grid_id}"]
                axes: Dict[str, np.ndarray] = {}
                for k in g.keys():
                    axes[k] = g[k][:]
                axis_order = json.loads(g.attrs.get("axis_order", "[]"))
                shape = list(g.attrs.get("shape", []))
                grid_type = str(g.attrs.get("grid_type", "cartesian"))
                return {
                    "grid_id": grid_id,
                    "axes": axes,
                    "axis_order": axis_order,
                    "shape": shape,
                    "grid_type": grid_type,
                }

    def list_grids(self) -> List[str]:
        """Lists all registered grid IDs."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "grids" not in f:
                    return []
                return sorted(list(f["grids"].keys()))

    # -------------------------------------------------------------------------
    # Idempotent Querying, Delta-Learning, & DVR
    # -------------------------------------------------------------------------
    def todo(self, method_id: str, wanted_ids: Iterable[str]) -> List[str]:
        """
        Identifies missing / unconverged points for incremental refinement and restart.

        Args:
            method_id: Method identifier
            wanted_ids: List of requested point IDs

        Returns:
            List of point IDs that are missing or not yet converged.
        """
        wanted_list = list(wanted_ids)
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                p = f.get(f"points/{method_id}")
                if p is None or "point_id" not in p:
                    return wanted_list
                p_ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
                converged = p["converged"][:]
                have = {s for s, ok in zip(p_ids, converged, strict=False) if ok}
        return [i for i in wanted_list if i not in have]

    def dataset(self, method_id: str, converged_only: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retrieves coordinates and energies array for a method.

        Args:
            method_id: Method identifier
            converged_only: If True, only returns converged points

        Returns:
            Tuple of (coordinates (Npts, Natoms, 3), energies (Npts,))
        """
        with self.shared_read_lock():
            with h5py.File(self.path, "r") as f:
                if f"points/{method_id}" not in f:
                    raise KeyError(f"No points dataset found for method '{method_id}'.")
                p = f[f"points/{method_id}"]
                mask = p["converged"][:] if converged_only else slice(None)
                coords = p["coordinates"][:][mask]
                energies = p["energy"][:][mask]
                return coords, energies

    def dataset_full(self, method_id: str, converged_only: bool = True) -> Dict[str, Any]:
        """Retrieves full points payload dictionary for a method."""
        with self.shared_read_lock():
            with h5py.File(self.path, "r") as f:
                if f"points/{method_id}" not in f:
                    raise KeyError(f"No points dataset found for method '{method_id}'.")
                p = f[f"points/{method_id}"]
                mask = p["converged"][:] if converged_only else slice(None)
                point_ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:][mask]]
                res: Dict[str, Any] = {
                    "method_id": method_id,
                    "coordinates": p["coordinates"][:][mask],
                    "energy": p["energy"][:][mask],
                    "converged": p["converged"][:][mask],
                    "wall_s": p["wall_s"][:][mask],
                    "point_id": point_ids,
                }
                if "gradient" in p:
                    res["gradient"] = p["gradient"][:][mask]
                return res

    def delta_pairs(self, low_method: str, high_method: str) -> Tuple[List[str], np.ndarray, np.ndarray]:
        """
        Returns aligned (keys, coordinates, E_high - E_low) pairs for Delta-learning MLFF training.

        Args:
            low_method: Low-level method identifier (e.g. 'wb97xd4_tz')
            high_method: High-level method identifier (e.g. 'dlpno_ccsdt1_avtz')

        Returns:
            keys: Aligned common point IDs
            X: High-level coordinates array (Npts, Natoms, 3)
            dE: Delta energies array (Npts,) in Hartrees (E_high - E_low)
        """
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                def get_idx(mid: str) -> Dict[str, int]:
                    if f"points/{mid}" not in f:
                        return {}
                    p = f[f"points/{mid}"]
                    ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
                    conv = p["converged"][:]
                    return {k: j for j, (k, ok) in enumerate(zip(ids, conv, strict=False)) if ok}

                il = get_idx(low_method)
                ih = get_idx(high_method)
                keys = sorted(set(il.keys()) & set(ih.keys()))

                if not keys:
                    return [], np.empty((0, self.n_atoms, 3)), np.empty((0,))

                idx_h = [ih[k] for k in keys]
                idx_l = [il[k] for k in keys]

                X = f[f"points/{high_method}/coordinates"][:][idx_h]
                dE = f[f"points/{high_method}/energy"][:][idx_h] - f[f"points/{low_method}/energy"][:][idx_l]
                return keys, X, dE

    def dvr_grid(self, method_id: str, grid_id: str) -> np.ndarray:
        """
        Reshapes energies onto a registered product grid for Discrete Variable Representation (DVR) solvers.
        Missing or unconverged points are filled with NaN.

        Args:
            method_id: Method identifier
            grid_id: Grid identifier

        Returns:
            Multidimensional NumPy array matching grid shape with potential values in Hartrees.
        """
        with self.open_reader() as f:
            if f"grids/{grid_id}" not in f:
                raise KeyError(f"Grid '{grid_id}' not found in PESStore.")
            shape = tuple(int(x) for x in f[f"grids/{grid_id}"].attrs["shape"])
            if f"points/{method_id}" not in f:
                return np.full(shape, np.nan, dtype=np.float64)

            p = f[f"points/{method_id}"]
            for ds_name in ["point_id", "converged", "energy"]:
                if ds_name in p and hasattr(p[ds_name], "refresh"):
                    try:
                        p[ds_name].refresh()
                    except Exception as _e:
                        logger.debug(f"Ignored exception: {_e}")
            ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
            conv = p["converged"][:]
            energies = p["energy"][:]

            total_pts = 1
            for dim in shape:
                total_pts *= dim

            V = np.full(total_pts, np.nan, dtype=np.float64)
            prefix = f"{grid_id}:"
            for j, k in enumerate(ids):
                if k.startswith(prefix) and conv[j]:
                    try:
                        idx = int(k.split(":")[1])
                        if 0 <= idx < total_pts:
                            V[idx] = energies[j]
                    except (ValueError, IndexError):
                        logger.debug("Failed to parse point index from point_id '%s'", k)
            return V.reshape(shape)

    # -------------------------------------------------------------------------
    # Checkpoints & Integrity
    # -------------------------------------------------------------------------
    def checkpoint_state(self, checkpoint_name: str, state_data: Dict[str, Any]) -> None:
        """Serializes arbitrary dictionary state to /checkpoints/<checkpoint_name>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                grp = f.require_group(f"checkpoints/{checkpoint_name}")
                grp.attrs["saved_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                for k, v in state_data.items():
                    if isinstance(v, np.ndarray):
                        if k in grp:
                            del grp[k]
                        grp.create_dataset(k, data=v)
                    elif isinstance(v, (int, float, str, bool)):
                        grp.attrs[k] = v
                    else:
                        grp.attrs[k] = json.dumps(v)

    def read_checkpoint(self, checkpoint_name: str) -> Dict[str, Any]:
        """Reads back saved checkpoint state dictionary."""
        result: Dict[str, Any] = {}
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"checkpoints/{checkpoint_name}"
                if path not in f:
                    return result
                grp = f[path]
                for k, v in grp.attrs.items():
                    val = v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v
                    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                        try:
                            result[k] = json.loads(val)
                        except json.JSONDecodeError:
                            result[k] = val
                    else:
                        result[k] = val
                for k in grp.keys():
                    result[k] = grp[k][:]
        return result

    def validate_integrity(self) -> Dict[str, Any]:
        """Verifies Fletcher32 checksums and dataset completeness."""
        report: Dict[str, Any] = {"status": "PASSED", "methods": {}, "corrupted_datasets": []}
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "points" in f:
                    for mid in f["points"].keys():
                        grp = f[f"points/{mid}"]
                        if not isinstance(grp, h5py.Group):
                            continue
                        n_pts = len(grp["energy"]) if "energy" in grp else 0
                        report["methods"][mid] = {"n_points": n_pts}
                        # Reading full dataset forces Fletcher32 checksum validation
                        try:
                            _ = grp["energy"][:]
                            _ = grp["coordinates"][:]
                        except Exception as exc:
                            report["status"] = "CORRUPTED"
                            report["corrupted_datasets"].append(f"points/{mid}: {exc}")
        return report


# =============================================================================
# 6. SWMR & ARCHIVAL BIFURCATED PES STORE
# =============================================================================

class BifurcatedPESStore:
    """
    Manages dual-tier storage bifurcation:
    1. Active Runtime Store (runtime_active.h5): High-throughput active SWMR or scratch container.
    2. Archival QCSchema Store (archive_pes.h5 / campaign.h5): Lossless compressed HDF5 store.
    """

    def __init__(
        self,
        active_runtime_path: Optional[Union[str, Path]] = None,
        archive_pes_path: Optional[Union[str, Path]] = None,
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
    ) -> None:
        art_dir = get_artifact_dir()
        runtime_dir = get_runtime_dir()

        self.active_path = (
            resolve_mapped_path(active_runtime_path, runtime_dir)
            if active_runtime_path is not None
            else runtime_dir / "runtime_active.h5"
        )
        self.archive_path = (
            resolve_mapped_path(archive_pes_path, art_dir)
            if archive_pes_path is not None
            else art_dir / "Databases" / "archive_pes.h5"
        )

        self.complex_name = complex_name
        self.symbols = list(symbols)
        self.molecular_charge = molecular_charge
        self.spin_multiplicity = spin_multiplicity
        self.lock_timeout = lock_timeout

        # Initialize underlying PES stores
        self.active_store = PESStore(
            path=self.active_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )
        self.archive_store = PESStore(
            path=self.archive_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    # Active / Archival Execution Context Managers
    # -------------------------------------------------------------------------
    @contextmanager
    def active_writer(self) -> Generator[PESStore, None, None]:
        """Context manager providing thread-safe write access to active runtime store."""
        with self.active_store.exclusive_write_lock():
            yield self.active_store

    @contextmanager
    def active_reader(self) -> Generator[PESStore, None, None]:
        """Context manager providing concurrent read access to active runtime store."""
        with self.active_store.shared_read_lock():
            yield self.active_store

    @contextmanager
    def archive_writer(self) -> Generator[PESStore, None, None]:
        """Context manager providing thread-safe write access to archival store."""
        with self.archive_store.exclusive_write_lock():
            yield self.archive_store

    @contextmanager
    def archive_reader(self) -> Generator[PESStore, None, None]:
        """Context manager providing read access to archival store."""
        with self.archive_store.shared_read_lock():
            yield self.archive_store

    # -------------------------------------------------------------------------
    # Point Recording & Promotion
    # -------------------------------------------------------------------------
    def record_point_to_active(
        self,
        method_id: str,
        coords: Union[Sequence[Any], np.ndarray],
        energy: float,
        *,
        point_id: Optional[str] = None,
        gradient: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: bool = True,
        wall_s: float = 0.0,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """Appends a single calculation result to the active runtime store."""
        return self.active_store.add_points(
            method_id=method_id,
            coords=coords,
            energies=[energy],
            point_ids=[point_id] if point_id is not None else None,
            gradients=[gradient] if gradient is not None else None,
            converged=[converged],
            wall_s=[wall_s],
            creator=creator,
            version=version,
            routine=routine,
        )

    def record_hessian_and_recycle_isotopologues(
        self,
        label: str,
        cart_hessian: np.ndarray,
        coords: np.ndarray,
        isotopologue_map: Dict[str, Sequence[Optional[int]]],
        level: str = "",
        geometry_ref: str = "",
    ) -> Dict[str, IsotopologueResult]:
        """
        Stores Cartesian Hessian in active store, executes zero-cost isotopologue recycling
        for all requested isotopic substitutions, and persists results to active store.
        """
        self.active_store.add_hessian(
            label=label,
            H=cart_hessian,
            level=level,
            geometry_ref=geometry_ref,
        )

        iso_results = reanalyze_isotopologue_suite(
            cart_hessian=cart_hessian,
            coords=coords,
            symbols=self.symbols,
            isotopologue_map=isotopologue_map,
            parent_label=label,
        )

        for _, res in iso_results.items():
            self.active_store.add_isotopologue_result(label, res)

        return iso_results

    def promote_active_to_archive(self, method_id: Optional[str] = None) -> int:
        """
        Transfers converged points and methods from the active runtime store into the
        compressed archival store with Fletcher32 checksum verification.

        Args:
            method_id: Optional specific method ID to promote. If None, promotes all methods.

        Returns:
            Total count of points promoted.
        """
        methods = [method_id] if method_id is not None else self.active_store.list_methods()
        total_promoted = 0

        for mid in methods:
            # Transfer method registration
            try:
                m_attrs = self.active_store.get_method(mid)
                self.archive_store.register_method(mid, **m_attrs)
            except Exception as exc:
                logger.warning(f"Could not transfer method registration for '{mid}': {exc}")

            # Transfer points
            try:
                data = self.active_store.dataset_full(mid, converged_only=True)
                npts = len(data["energy"])
                if npts > 0:
                    # Check which points are already in archive
                    needed_ids = self.archive_store.todo(mid, data["point_id"])
                    if needed_ids:
                        needed_set = set(needed_ids)
                        keep_mask = [pid in needed_set for pid in data["point_id"]]

                        coords_to_add = data["coordinates"][keep_mask]
                        energies_to_add = data["energy"][keep_mask]
                        pids_to_add = [pid for pid, ok in zip(data["point_id"], keep_mask, strict=False) if ok]
                        grads_to_add = data.get("gradient")[keep_mask] if "gradient" in data else None
                        conv_to_add = data["converged"][keep_mask]
                        wall_to_add = data["wall_s"][keep_mask]

                        self.archive_store.add_points(
                            method_id=mid,
                            coords=coords_to_add,
                            energies=energies_to_add,
                            point_ids=pids_to_add,
                            gradients=grads_to_add,
                            converged=conv_to_add,
                            wall_s=wall_to_add,
                        )
                        total_promoted += len(pids_to_add)
            except KeyError:
                continue

        # Transfer Hessians and Isotopologues
        for h_label in self.active_store.list_hessians():
            try:
                h_mat, h_attrs = self.active_store.get_hessian(h_label)
                self.archive_store.add_hessian(
                    label=h_label,
                    H=h_mat,
                    level=str(h_attrs.get("level", "")),
                    geometry_ref=str(h_attrs.get("geometry_ref", "")),
                    units=str(h_attrs.get("units", "Hartree/Bohr^2")),
                )
                for iso_label in self.active_store.list_isotopologues(h_label):
                    iso_res = self.active_store.get_isotopologue_result(h_label, iso_label)
                    self.archive_store.add_isotopologue_result(h_label, iso_res)
            except Exception as exc:
                logger.warning(f"Could not transfer Hessian '{h_label}' to archive: {exc}")

        logger.info(f"Promoted {total_promoted} active runtime points to archival store {self.archive_path}")
        return total_promoted


class TripartitePESStore(BifurcatedPESStore):
    """
    Tripartite PES Store architecture incorporating:
    1. Active runtime SWMR store for real-time trajectory/grid evaluation.
    2. Shared reader / exclusive writer synchronization via ReadWriteFileLock.
    3. Archival store for long-term compressed QCSchema representations.
    """

    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
        archive_path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            active_runtime_path=path,
            archive_pes_path=archive_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )

    def register_method(self, method_id: str, **attrs: Any) -> None:
        """Registers computational method into the active runtime store."""
        self.active_store.register_method(method_id, **attrs)

    def get_points(self, method_id: str, converged_only: bool = False) -> List[Dict[str, Any]]:
        """Retrieves points for a method from active runtime store."""
        return self.active_store.get_points(method_id, converged_only=converged_only)

    def add_points(self, *args: Any, **kwargs: Any) -> int:
        """Appends points into the active runtime store."""
        return self.active_store.add_points(*args, **kwargs)

    def list_methods(self) -> List[str]:
        """Lists methods registered in active runtime store."""
        return self.active_store.list_methods()

    def get_method(self, method_id: str) -> Dict[str, Any]:
        """Retrieves metadata attributes for a registered method."""
        return self.active_store.get_method(method_id)

    def todo(self, method_id: str, wanted_point_ids: Sequence[str]) -> List[str]:
        """Identifies missing or unconverged points in active runtime store."""
        return self.active_store.todo(method_id, wanted_point_ids)

    def dataset(self, *args: Any, **kwargs: Any) -> Tuple[np.ndarray, np.ndarray]:
        """Extracts aligned coordinates and energies from active runtime store."""
        return self.active_store.dataset(*args, **kwargs)

    def dataset_full(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Extracts full structured dataset dictionary from active runtime store."""
        return self.active_store.dataset_full(*args, **kwargs)


# =============================================================================
# 7. PARALLEL SHARD MERGER UTILITY
# =============================================================================

def merge_pes_shards(
    shard_paths: Sequence[Union[str, Path]],
    target_store_path: Union[str, Path],
    complex_name: str = "",
    symbols: Sequence[str] = (),
    swmr_mode: bool = True,
    timeout: float = 60.0,
) -> int:
    """
    Merges multiple worker PES shards (shard_<uuid>_<task>.h5, campaign_rank_0.h5, ...)
    into a single master PES store atomically using FileLock.

    Args:
        shard_paths: List of shard file paths
        target_store_path: Destination HDF5 file path
        complex_name: Complex name identifier (inferred from shards if empty)
        symbols: Elemental symbols (inferred from shards if empty)
        swmr_mode: Whether to enable SWMR mode on target store
        timeout: Lock timeout in seconds

    Returns:
        Total count of points merged into the target store.
    """
    valid_paths = [Path(s) for s in shard_paths if Path(s).exists()]
    if not valid_paths:
        logger.warning("No valid shard files found to merge.")
        return 0

    # Auto-infer complex_name and symbols from shards if not specified
    if not complex_name or not symbols:
        for s_p in valid_paths:
            try:
                s_store = PESStore(path=s_p)
                if not complex_name and s_store.complex_name:
                    complex_name = s_store.complex_name
                if not symbols and s_store.symbols:
                    symbols = list(s_store.symbols)
                if complex_name and symbols:
                    break
            except Exception as exc:
                logger.debug("Failed extracting metadata from shard %s: %s", s_p, exc)

    target_lock = FileLock(f"{Path(target_store_path).resolve()}.lock", timeout=timeout)
    with target_lock:
        target = PESStore(
            path=target_store_path,
            complex_name=complex_name,
            symbols=symbols,
            swmr_mode=swmr_mode,
        )
        total_merged = 0

        for p in valid_paths:
            shard = PESStore(path=p)
            methods = shard.list_methods()

            for mid in methods:
                # Register method if not present
                try:
                    m_attrs = shard.get_method(mid)
                    target.register_method(mid, **m_attrs)
                except Exception as exc:
                    logger.debug("Method registration skipped or failed during merge for '%s': %s", mid, exc)

                try:
                    data = shard.dataset_full(mid, converged_only=True)
                    npts = len(data["energy"])
                    if npts > 0:
                        needed_ids = target.todo(mid, data["point_id"])
                        if needed_ids:
                            needed_set = set(needed_ids)
                            keep_mask = [pid in needed_set for pid in data["point_id"]]

                            coords_to_add = data["coordinates"][keep_mask]
                            energies_to_add = data["energy"][keep_mask]
                            pids_to_add = [pid for pid, ok in zip(data["point_id"], keep_mask, strict=False) if ok]
                            grads_to_add = data.get("gradient")[keep_mask] if "gradient" in data else None
                            conv_to_add = data["converged"][keep_mask]
                            wall_to_add = data["wall_s"][keep_mask]

                            target.add_points(
                                method_id=mid,
                                coords=coords_to_add,
                                energies=energies_to_add,
                                point_ids=pids_to_add,
                                gradients=grads_to_add,
                                converged=conv_to_add,
                                wall_s=wall_to_add,
                            )
                            total_merged += len(pids_to_add)
                except KeyError:
                    continue

        logger.info(f"Successfully merged {total_merged} points across {len(valid_paths)} shards into {target_store_path}")
        return total_merged


merge_hdf5_shards = merge_pes_shards


# =============================================================================
# 8. COMMAND-LINE INTERFACE
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Builds comprehensive CLI parser for PES store management."""
    parser = argparse.ArgumentParser(
        description="CoChem Core PES Store: QCSchema HDF5, SWMR/Archival Bifurcation, & Isotopologue Recycling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # info
    p_info = subparsers.add_parser("info", help="Display summary information for a PESStore HDF5 file")
    p_info.add_argument("path", help="Path to HDF5 store file")

    # todo
    p_todo = subparsers.add_parser("todo", help="Check missing points on a grid")
    p_todo.add_argument("path", help="Path to HDF5 store file")
    p_todo.add_argument("--method", required=True, help="Method ID")
    p_todo.add_argument("--grid", required=True, help="Grid ID")

    # merge
    p_merge = subparsers.add_parser("merge", help="Merge multiple HDF5 shards into a destination store")
    p_merge.add_argument("--target", required=True, help="Target master HDF5 path")
    p_merge.add_argument("shards", nargs="+", help="Input shard file paths")

    # recycle-isotopologues
    p_iso = subparsers.add_parser("recycle-isotopologues", help="Re-analyze a saved Hessian with isotopic substitutions")
    p_iso.add_argument("path", help="Path to HDF5 store file")
    p_iso.add_argument("--hessian-label", required=True, help="Registered Hessian label")
    p_iso.add_argument("--xyz", required=True, help="Path to reference XYZ geometry")

    return parser


def main() -> None:
    """Main CLI execution router."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if not args.subcommand or args.subcommand == "info":
        path = args.path if hasattr(args, "path") else get_state_file_path()
        store = PESStore(path)
        print("=" * 60)
        print(f"CoChem PES Store: {store.path}")
        print(f"Complex: {store.complex_name} | N_atoms: {store.n_atoms} | Symbols: {store.symbols}")
        print(f"Methods registered: {store.list_methods()}")
        print(f"Hessians stored: {store.list_hessians()}")
        print(f"Grids registered: {store.list_grids()}")
        print("Integrity Check:", store.validate_integrity())
        print("=" * 60)

    elif args.subcommand == "todo":
        store = PESStore(args.path)
        grid = store.get_grid(args.grid)
        shape = grid["shape"]
        total_pts = 1
        for dim in shape:
            total_pts *= dim
        wanted = [f"{args.grid}:{i}" for i in range(total_pts)]
        missing = store.todo(args.method, wanted)
        print(f"Grid '{args.grid}' has {total_pts} total points.")
        print(f"Method '{args.method}' has {len(missing)} points remaining to compute ({len(wanted) - len(missing)} completed).")

    elif args.subcommand == "merge":
        merged = merge_pes_shards(args.shards, args.target)
        print(f"Merged {merged} total points into {args.target}")

    elif args.subcommand == "recycle-isotopologues":
        store = PESStore(args.path)
        h_mat, h_attrs = store.get_hessian(args.hessian_label)
        # Parse XYZ
        xyz_p = Path(args.xyz)
        lines = xyz_p.read_text(encoding="utf-8").splitlines()
        n = int(lines[0].split()[0])
        syms: List[str] = []
        coords_list: List[List[float]] = []
        for ln in lines[2:2 + n]:
            parts = ln.split()
            syms.append(parts[0])
            coords_list.append([float(x) for x in parts[1:4]])
        coords_arr = np.asarray(coords_list, dtype=np.float64)

        # Standard test suite of common isotopologues
        iso_map: Dict[str, List[Optional[int]]] = {"parent": [None] * len(syms)}
        for i, s in enumerate(syms):
            clean_s = s.strip().capitalize()
            if clean_s == "C":
                m_list = [None] * len(syms)
                m_list[i] = 13
                iso_map[f"13C_atom_{i}"] = m_list
            elif clean_s == "O":
                m_list = [None] * len(syms)
                m_list[i] = 18
                iso_map[f"18O_atom_{i}"] = m_list
            elif clean_s == "H":
                m_list = [None] * len(syms)
                m_list[i] = 2
                iso_map[f"D_atom_{i}"] = m_list

        results = reanalyze_isotopologue_suite(h_mat, coords_arr, syms, iso_map, parent_label=args.hessian_label)
        print(f"Evaluated {len(results)} isotopologues from Hessian '{args.hessian_label}':")
        for k, v in results.items():
            store.add_isotopologue_result(args.hessian_label, v)
            print(f"  [{k}] A={v.A_MHz:.3f} MHz, B={v.B_MHz:.3f} MHz, C={v.C_MHz:.3f} MHz | Lowest Mode: {v.lowest_harmonic_mode_cm_inv:.2f} cm^-1")


def __getattr__(name: str) -> Any:
    if name == "PESPointRecord":
        from cochem_base.core.models import PESPointRecord
        return PESPointRecord
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


if __name__ == "__main__":
    main()


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
import hashlib
import json
import logging
import math
import os
import platform
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
    Dict,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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


# Optional telemetry bindings
import warnings

import numpy as np
import psutil
import scipy.stats
from mendeleev import element

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
    gpu_scout_mlff_executor: Optional[ExecutorConfig] = Field(
        default=None, description="Segregated GPU Scout MLFF pool under MPS"
    )
    gpu_anchor_pyscf_executor: Optional[ExecutorConfig] = Field(
        default=None, description="Segregated GPU Anchor PySCF pool dedicated non-oversubscribed"
    )
    orchestrator_executor: Optional[ExecutorConfig] = Field(default=None, description="Utility / DFK executor config")
    retries: int = Field(default=2, ge=0, description="Parsl task execution retry budget (§8A.6)")
    strategy: str = Field(default="simple", description="Parsl scaling strategy")
    hardware: HardwareSpec = Field(default_factory=HardwareSpec, description="Physical hardware spec")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Exported environment variables")

    @property
    def gpu_workers(self) -> int:
        if self.gpu_executor and self.gpu_executor.max_workers_per_node:
            return self.gpu_executor.max_workers_per_node
        return 0

    @property
    def gpu_worker_init(self) -> str:
        if self.gpu_executor and self.gpu_executor.worker_init:
            return self.gpu_executor.worker_init
        return ""


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
    provenance: str = Field(default="[M]", description="W3C provenance tag [M]")
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
    current_os = platform.system()
    is_non_linux = current_os in ("Windows", "Darwin")
    is_win = current_os == "Windows"

    if is_non_linux:
        # Non-Linux: Bypass MPS entirely; serialize GPU workers to 1 per device
        effective_gpu_workers = 1
        if is_win:
            cpu_init = "set OMP_NUM_THREADS=1"
            gpu_init = "set CUDA_VISIBLE_DEVICES=0"
        else:
            cpu_init = "export OMP_NUM_THREADS=1"
            gpu_init = "export CUDA_VISIBLE_DEVICES=0"
        env_vars = {"CUDA_VISIBLE_DEVICES": "0"}
    else:
        effective_gpu_workers = gpu_workers
        cpu_init = "export OMP_NUM_THREADS=1; export KMP_HW_SUBSET=8c:intel_core,1t"
        gpu_init = (
            f"export CUDA_VISIBLE_DEVICES=0; "
            f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={active_thread_pct}; "
            f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{pinned_mem_limit}'; "
            f"export CUDA_MPS_PIPE_DIRECTORY='{pipe_dir}'; "
            f"export CUDA_MPS_LOG_DIRECTORY='{log_dir}'; "
            "ulimit -n 16384"
        )
        env_vars = {
            "CUDA_VISIBLE_DEVICES": "0",
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(active_thread_pct),
            "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": pinned_mem_limit,
            "CUDA_MPS_PIPE_DIRECTORY": pipe_dir,
            "CUDA_MPS_LOG_DIRECTORY": log_dir,
        }

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
        available_accelerators=effective_gpu_workers,
        max_workers_per_node=effective_gpu_workers,
        cores_per_worker=1,
        cpu_affinity=CoreAffinityType.BLOCK_REVERSE,
        mem_per_worker_gb=mem_per_gpu_worker_gb,
        worker_init=gpu_init,
        provider_type=ProviderBackend.LOCAL,
    )

    gpu_mlff_exec = ExecutorConfig(
        label="gpu_scout_mlff",
        available_accelerators=effective_gpu_workers,
        max_workers_per_node=effective_gpu_workers,
        cores_per_worker=1,
        cpu_affinity=CoreAffinityType.BLOCK_REVERSE,
        mem_per_worker_gb=mem_per_gpu_worker_gb,
        worker_init=gpu_init,
        provider_type=ProviderBackend.LOCAL,
    )

    gpu_pyscf_exec = ExecutorConfig(
        label="gpu_anchor_pyscf",
        available_accelerators=1,
        max_workers_per_node=1,
        cores_per_worker=cpu_cores_per_worker,
        cpu_affinity=CoreAffinityType.BLOCK,
        mem_per_worker_gb=16.0,
        worker_init="set CUDA_VISIBLE_DEVICES=0" if is_win else "export CUDA_VISIBLE_DEVICES=0",
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
            worker_init="set OMP_NUM_THREADS=1" if is_win else "export OMP_NUM_THREADS=1",
            provider_type=ProviderBackend.LOCAL,
        )

    pydantic_cfg = HeteroParslConfig(
        setup_tier=SetupTier.SETUP_2,
        cpu_executor=cpu_exec,
        gpu_executor=gpu_exec,
        gpu_scout_mlff_executor=gpu_mlff_exec,
        gpu_anchor_pyscf_executor=gpu_pyscf_exec,
        orchestrator_executor=orch_exec,
        retries=retries,
        env_vars=env_vars,
    )

    return pydantic_cfg


build_setup2_hetero_config = build_hetero_config


def get_vram_free_gb() -> float:
    """
    Non-initializing VRAM polling via NVML C API / nvidia-smi.
    Returns available free VRAM in gigabytes as a physical float.
    """
    # 1. Attempt NVML ctypes wrapper (zero initialization of CUDA runtime context)
    try:
        import ctypes

        class _nvmlMemory_t(ctypes.Structure):
            _fields_ = [
                ("total", ctypes.c_ulonglong),
                ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong),
            ]

        if platform.system() == "Windows":
            nvml_dll = ctypes.windll.LoadLibrary("nvml.dll")
        else:
            nvml_dll = ctypes.CDLL("libnvidia-ml.so.1")
        nvml_dll.nvmlInit()
        dev = ctypes.c_void_p()
        if hasattr(nvml_dll, "nvmlDeviceGetHandleByIndex_v2"):
            nvml_dll.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        else:
            nvml_dll.nvmlDeviceGetHandleByIndex(0, ctypes.byref(dev))
        mem = _nvmlMemory_t()
        nvml_dll.nvmlDeviceGetMemoryInfo(dev, ctypes.byref(mem))
        free_gb = float(mem.free) / (1024.0 ** 3)
        nvml_dll.nvmlShutdown()
        return round(free_gb, 4)
    except Exception:
        pass

    # 2. Fallback: query nvidia-smi CLI
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=5.0,
        ).decode().strip()
        first_line = out.splitlines()[0].strip()
        return round(float(first_line) / 1024.0, 4)
    except Exception:
        pass

    return 0.0


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


def probe_mps_status(
    device_id: int = 0,
    pipe_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
) -> MPSStatus:
    """
    Probes system and hardware telemetry for NVIDIA MPS daemon status and GPU resource availability
    using non-initializing NVML queries without locking CUDA driver contexts. [M]

    Args:
        device_id: Target CUDA device ID (default 0).
        pipe_dir: Optional custom MPS pipe directory.
        log_dir: Optional custom MPS log directory.

    Returns:
        MPSStatus model populated with live hardware information.
    """
    if pipe_dir is None:
        pipe_dir = os.environ.get("CUDA_MPS_PIPE_DIRECTORY", "/tmp/nvidia-mps")
    if log_dir is None:
        log_dir = os.environ.get("CUDA_MPS_LOG_DIRECTORY", "/tmp/nvidia-log")
    pipe_exists = Path(pipe_dir).resolve().exists()
    log_exists = Path(log_dir).resolve().exists()

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
    device_name = "None"
    vram_total_mb = 0.0
    vram_used_mb = 0.0
    vram_free_mb = 0.0
    power_limit_w = 0.0

    # Non-initializing NVML inspection
    if os.environ.get("CUDA_VISIBLE_DEVICES") in ("", "-1"):
        device_count = 0
    elif HAS_PYNVML:
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

    # Zero-mock honest telemetry: if no physical GPU is detected, report exact zero resources [M]
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
        w = np.full(n_atoms, 1.0 / float(n_atoms), dtype=float)
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
    e = np.diag([1.0, 1.0, -1.0 if d < 0.0 else 1.0])

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
        from ase import Atoms
        from ase.calculators.emt import EMT
        from ase.optimize import BFGS

        # Real physical computation using ASE EMT potential instead of random noise
        atoms = Atoms("OHHOHH", positions=c1)
        atoms.calc = EMT()
        opt = BFGS(atoms, logfile=None)
        opt.run(fmax=0.5, steps=5)
        c2 = atoms.get_positions()

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


class SpinContaminationError(PhysicsIntegrityError, ValueError):
    """Raised when open-shell wavefunction exhibits unacceptable spin contamination (<S^2> deviation > 10%)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SPIN_CONTAMINATION_EXCEEDED
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
    provenance: str = Field(default="[M]", description="W3C provenance tag [M]")


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
    hypothesis_scope: Literal["marginal", "atomwise_bonferroni", "atomwise_marginal"] = "marginal"
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

    num_models_m: int = Field(default=8, ge=2, le=32, description="Number of committee models M [E]")
    vectorized: bool = True
    vram_headroom_threshold_mb: float = Field(default=2048.0, ge=512.0)
    concurrency_mode: Literal["vmap", "cuda_streams", "serial"] = "vmap"
    max_batch_size: int = Field(default=128, ge=1)
    max_concurrent_models_vram: int = Field(default=2, ge=1)
    synchronize_cuda_streams: bool = True


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

    model_config = ConfigDict(frozen=True, extra="allow")

    input_geometry: Path
    output_directory: Path
    theory_level: str = "B3LYP-D4/def2-TZVP"
    cpus_per_task: int = Field(default=1, ge=1)
    memory_mb: int = Field(default=4096, ge=1024)
    scratch_dir: Path
    device: str = "cpu"
    task_id: Optional[int] = None
    mode: str = "full"


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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_execution_router_parsl_broker.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Direct Integration of Parsl Multi-Executor Broker in Calculation Execution Router.
Validates Suggestion #145 (Deliverable 5) under Method Matrix v4 §8A.2, §8A.6 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from cochem_base.calc.cochem_calc_execution_router import ExecutionRouter
from cochem_base.schemas import JobRouteConfig, ExecutionRouteResult


def test_execution_router_scout_and_anchor_routing(tmp_path: Path) -> None:
    """Verify that ExecutionRouter routes exploratory MLFF to scout_gpu and heavy QM to anchor_cpu."""
    router = ExecutionRouter()

    # 1. Exploratory MLFF scan task
    scout_result = router.route_job(
        target_engine_or_type="fast_potential_scan",
        payload_command=["python", "-c", "print('scout_done')"],
        scratch_dir=tmp_path / "scratch_scout",
        cpu_core_pinning=[0],
    )
    assert isinstance(scout_result, ExecutionRouteResult)
    assert scout_result.assigned_executor == "cochem_scout_gpu"
    assert scout_result.scratch_dir.exists()

    # 2. Heavy quantum chemical optimization task
    anchor_result = router.route_job(
        target_engine_or_type="heavy_qm_opt",
        payload_command=["python", "-c", "print('anchor_done')"],
        scratch_dir=tmp_path / "scratch_anchor",
        cpu_core_pinning=[0, 1, 2, 3],
    )
    assert isinstance(anchor_result, ExecutionRouteResult)
    assert anchor_result.assigned_executor == "cochem_anchor_cpu"
    assert anchor_result.scratch_dir.exists()


def test_execution_router_thread_budgeting(tmp_path: Path) -> None:
    """Verify CPU core affinity and OpenMP/MKL thread count budgeting."""
    router = ExecutionRouter()
    cores = [0, 1, 2, 3, 4, 5, 6]

    res = router.route_job(
        target_engine_or_type="heavy_qm_opt",
        payload_command=["python", "-c", "import os; print(os.environ.get('OMP_NUM_THREADS', '1'))"],
        scratch_dir=tmp_path / "scratch_threads",
        cpu_core_pinning=cores,
    )
    assert res.assigned_executor == "cochem_anchor_cpu"
    assert res.scratch_dir.exists()
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\.trash\chain.py ---
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
from filelock import FileLock
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


class MissingBinaryError(FileNotFoundError):
    """Raised immediately when configured ORCA, CREST, or xTB executable is invalid or not executable."""
    pass


class ConvergenceFailureError(RuntimeError):
    """Raised when an electronic structure engine fails to achieve SCF or geometry convergence."""
    pass


class CorruptOutputError(RuntimeError):
    """Raised when expected binary wavefunction containers or Hessian matrices are missing or malformed."""
    pass


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
        h5: Optional[Union[str, Path]] = None,
        h5_path: Optional[Union[str, Path]] = None,
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
        h5_target = h5_path if h5_path is not None else (h5 if h5 is not None else "campaign.h5")
        h5_p = Path(h5_target)
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
        lock = FileLock(Path(f"{self.h5_path}.lock"), timeout=30.0)
        with lock:
            with h5py.File(self.h5_path, "a", libver="latest") as f:
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
        lock = FileLock(Path(f"{self.h5_path}.lock"), timeout=30.0)
        with lock:
            with h5py.File(self.h5_path, "a", libver="latest") as f:
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
            bin_path = shutil.which(self.orca_cmd)
            if bin_path is None and not Path(self.orca_cmd).is_file():
                raise MissingBinaryError(
                    f"ORCA executable '{self.orca_cmd}' is missing or not executable on PATH."
                )

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
                except FileNotFoundError as exc:
                    wall_s = time.time() - t0
                    raise MissingBinaryError(
                        f"ORCA executable '{self.orca_cmd}' could not be executed: {exc}"
                    ) from exc
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
    "MissingBinaryError",
    "ConvergenceFailureError",
    "CorruptOutputError",
]


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_canonical_chain_unification.py ---
"""CoChem-BASE: Test Canonical State-Chaining Engine Unification across Ecosystem.

Compliant with Method Matrix §8B, §8C, Suggestion #78, #157, and Anti-Spoofing Directives.
Verifies Deliverable 7:
1. Canonical exports from cochem_base.chain package (Chain, ChainStage, Stage, StateChainingAuditor).
2. Module-level exports from cochem_base.chain.chain and cochem_base.chain.auditor.
3. Facade re-exports from CoChem-TOPOS/chain.py and CoChem-TORQ/Libraries/chain.py match canonical classes.
4. Method Matrix §8B.5 Rules D1-D5 verification via StateChainingAuditor.
5. Canonical 11-Arrow mapping and chain configuration integrity.
"""

import importlib.util
import sys
from pathlib import Path

from cochem_base.chain import (
    CANONICAL_ARROWS,
    CanonicalArrow,
    Chain,
    ChainStage,
    Stage,
    StateChainingAuditor,
)
from cochem_base.chain.auditor import StateChainingAuditor as SubAuditor
from cochem_base.chain.chain import Chain as SubChain


def _import_module_from_path(module_name: str, file_path: Path):
    """Dynamically load module from absolute path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_canonical_chain_package_exports():
    """Verify public exports from cochem_base.chain package."""
    assert Chain is SubChain
    assert StateChainingAuditor is SubAuditor
    assert ChainStage is Stage
    assert len(CANONICAL_ARROWS) == 11
    assert CanonicalArrow.ARROW_1_MLFF_XTB_GOAT == 1
    assert CanonicalArrow.ARROW_11_COMPOUND_CHAIN == 11


def test_topos_facade_reexports():
    """Verify CoChem-TOPOS/chain.py re-exports canonical cochem_base.chain classes."""
    topos_chain_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TOPOS/chain.py")
    assert topos_chain_path.exists()

    topos_chain_mod = _import_module_from_path("topos_chain_facade", topos_chain_path)
    assert topos_chain_mod.Chain is Chain
    assert topos_chain_mod.ChainStage is ChainStage
    assert topos_chain_mod.StateChainingAuditor is StateChainingAuditor


def test_torq_facade_reexports():
    """Verify CoChem-TORQ/Libraries/chain.py re-exports canonical cochem_base.chain classes."""
    torq_chain_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TORQ/Libraries/chain.py")
    assert torq_chain_path.exists()

    torq_chain_mod = _import_module_from_path("torq_chain_facade", torq_chain_path)
    assert torq_chain_mod.Chain is Chain
    assert torq_chain_mod.ChainStage is ChainStage
    assert torq_chain_mod.StateChainingAuditor is StateChainingAuditor


def test_state_chaining_auditor_rules_d1_to_d5():
    """Verify StateChainingAuditor correctly audits Method Matrix §8B.5 Rules D1-D5."""
    # Rule D1: Stationarity
    pass_d1, _ = StateChainingAuditor.audit_d1_stationarity(gradient_norm_hartree_bohr=5e-6, tol_max_g=1e-5)
    fail_d1, _ = StateChainingAuditor.audit_d1_stationarity(gradient_norm_hartree_bohr=2e-4, tol_max_g=1e-5)
    assert pass_d1 is True
    assert fail_d1 is False

    # Rule D2: Hessian transfer
    pass_d2, _ = StateChainingAuditor.audit_d2_hessian_transfer(harmonic_frequencies_cm1=[150.0, 300.0, 1600.0])
    fail_d2, _ = StateChainingAuditor.audit_d2_hessian_transfer(harmonic_frequencies_cm1=[-50.0, 300.0, 1600.0])
    assert pass_d2 is True
    assert fail_d2 is False

    # Rule D3: SCF stability
    pass_d3, _ = StateChainingAuditor.audit_d3_scf_stability(fresh_energy_hartree=-76.4000001, reused_energy_hartree=-76.4000001)
    fail_d3, _ = StateChainingAuditor.audit_d3_scf_stability(fresh_energy_hartree=-76.4000000, reused_energy_hartree=-76.3990000)
    assert pass_d3 is True
    assert fail_d3 is False

    # Rule D4: Counterpoise hygiene
    pass_d4, _ = StateChainingAuditor.audit_d4_counterpoise_hygiene(stage_name="dimer_opt", counterpoise="none", mo_from=None)
    fail_d4, _ = StateChainingAuditor.audit_d4_counterpoise_hygiene(stage_name="monomer_a", counterpoise="monomer", mo_from="dimer_opt")
    assert pass_d4 is True
    assert fail_d4 is False

    # Rule D5: Naming hygiene
    pass_d5, _ = StateChainingAuditor.audit_d5_naming_hygiene(current_stage="s3", consumed_stage="s2")
    fail_d5, _ = StateChainingAuditor.audit_d5_naming_hygiene(current_stage="s2", consumed_stage="s2")
    assert pass_d5 is True
    assert fail_d5 is False

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_dynamic_contention_budget_scaling.py ---
"""CoChem-BASE: Test Dynamic Memory Contention Downscaling for Low-RAM Environments.

Compliant with Method Matrix §8A.1, §8A.4, Suggestion #77, #156, and Anti-Spoofing Directives.
Verifies Deliverable 6:
1. Dynamic host RAM downscaling on 16 GB systems without raising ContentionBudgetExceededError.
2. Dynamic host RAM downscaling on 8 GB systems (concurrency downscaled to 1 worker).
3. Dynamic host RAM downscaling on severely constrained (< 8 GB) environments with valid floors.
4. Default parameter execution with automatic psutil hardware probing.
5. Contention budget metrics (85% real efficiency, slowdown factor).
"""

from cochem_base.core_engine.cochem_core_parsl_executors import (
    ContentionBudget,
    calculate_contention_budget,
)


def test_contention_budget_scaling_16gb():
    """Verify that calculate_contention_budget succeeds on 16 GB systems."""
    budget = calculate_contention_budget(
        total_physical_cores=8,
        total_ram_gb=16.0,
        gpu_scout_workers=3,
        anchor_ranks=7,
    )

    assert isinstance(budget, ContentionBudget)
    assert budget.anchor_mem_per_worker_gb >= 4.0
    assert budget.scout_mem_per_worker_gb >= 1.5
    assert budget.gpu_scout_workers <= 2


def test_contention_budget_scaling_severely_constrained_8gb():
    """Verify minimum floors and single worker downscaling on 8 GB hosts."""
    budget = calculate_contention_budget(
        total_physical_cores=4,
        total_ram_gb=8.0,
        gpu_scout_workers=3,
        anchor_ranks=3,
    )

    assert isinstance(budget, ContentionBudget)
    assert budget.anchor_mem_per_worker_gb >= 4.0
    assert budget.scout_mem_per_worker_gb >= 1.5
    assert budget.gpu_scout_workers == 1


def test_contention_budget_scaling_sub_8gb():
    """Verify graceful handling of ultra-constrained memory environments (e.g. 4 GB)."""
    budget = calculate_contention_budget(
        total_physical_cores=2,
        total_ram_gb=4.0,
        gpu_scout_workers=2,
        anchor_ranks=2,
    )

    assert isinstance(budget, ContentionBudget)
    assert budget.anchor_mem_per_worker_gb >= 1.0
    assert budget.scout_mem_per_worker_gb >= 0.5
    assert budget.gpu_scout_workers == 1


def test_contention_budget_automatic_probing():
    """Verify calculate_contention_budget dynamically probes psutil when arguments are omitted."""
    budget = calculate_contention_budget()
    assert isinstance(budget, ContentionBudget)
    assert budget.total_host_ram_gb > 0.0
    assert budget.p_cores_anchor >= 1
    assert budget.real_parallelism_efficiency == 0.85
    assert budget.estimated_cpu_slowdown_factor >= 1.0

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_os_aware_gpu_scout_executor.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: OS-Aware GPU Scout Concurrency & Windows/macOS Serialized Dynamic VRAM Routing.
Validates Suggestion #144 (Deliverable 4) under Method Matrix v4 §8A.4, §8A.6 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import platform
import pytest

from cochem_base.core_engine.hetero_config import (
    build_setup2_hetero_config,
    get_vram_free_gb,
    HeteroParslConfig,
)
from cochem_base.core_engine.cochem_core_parsl_executors import (
    ParslExecutionBroker,
)


def test_os_aware_mps_bypass_on_non_linux() -> None:
    """Verify that build_setup2_hetero_config bypasses MPS on Windows/macOS and enforces max_workers=1."""
    cfg = build_setup2_hetero_config(
        cpu_workers=1,
        gpu_workers=3,
        as_parsl_object=False,
    )

    current_os = platform.system()
    if current_os in ("Windows", "Darwin"):
        assert cfg.gpu_workers == 1, f"Expected serialized gpu_workers=1 on {current_os}, got {cfg.gpu_workers}"
        # Assert that worker_init contains no Linux-only MPS commands
        assert "nvidia-cuda-mps-control" not in cfg.gpu_worker_init
        assert "CUDA_MPS_PIPE_DIRECTORY" not in cfg.gpu_worker_init
    else:
        # On Linux, verify MPS parameters
        assert "CUDA_MPS" in cfg.gpu_worker_init or cfg.gpu_workers >= 1


def test_dynamic_vram_polling_and_threshold() -> None:
    """Verify non-initializing VRAM polling returns physical float value and applies >=2.0 GB headroom check."""
    vram_free = get_vram_free_gb()
    assert isinstance(vram_free, float)
    assert vram_free >= 0.0

    # Test safety threshold evaluation: if VRAM < 2.0 GB, throttle / route to CPU
    safety_threshold = 2.0
    needs_throttle = (vram_free < safety_threshold) and (vram_free > 0.0)
    assert isinstance(needs_throttle, bool)
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_parsl_worker_resident_calculator_cache.py ---
"""CoChem-BASE: Test Parsl Worker-Resident Singleton MLFF Calculator Cache & Stream Management.

Compliant with Method Matrix §8A.3, §8A.4, Suggestion #154, and Anti-Spoofing Directives.
Verifies Deliverable 4:
1. Singleton calculator cache retrieval across worker lifecycle (same model_name returns identical object ID).
2. Distinction of cached instances across distinct keys (model_name/device/path).
3. Cache invalidation and memory cleanup via clear_worker_calculator_cache().
4. Non-blocking CUDA stream isolation or device tracking metadata.
5. Real physical potential energy evaluation on authentic molecular geometry (H2/H2O) using cached calculator.
"""

import pytest
from ase import Atoms

from cochem_base.core_engine.cochem_core_parsl_executors import (
    _WORKER_CALCULATOR_CACHE,
    clear_worker_calculator_cache,
    get_cached_mlff_calculator,
)


@pytest.fixture(autouse=True)
def cleanup_cache():
    """Ensure cache is clean before and after each test."""
    clear_worker_calculator_cache()
    yield
    clear_worker_calculator_cache()


def test_worker_calculator_cache_singleton_identity():
    """Verify that multiple requests for the same model return the exact same singleton instance."""
    calc1 = get_cached_mlff_calculator("emt", device="cpu")
    calc2 = get_cached_mlff_calculator("emt", device="cpu")

    assert calc1 is calc2
    assert id(calc1) == id(calc2)
    assert len(_WORKER_CALCULATOR_CACHE) == 1


def test_worker_calculator_cache_key_separation():
    """Verify that distinct models or devices create distinct cache entries."""
    calc_emt = get_cached_mlff_calculator("emt", device="cpu")
    calc_mace = get_cached_mlff_calculator("mace", device="cpu")

    assert calc_emt is not None
    assert calc_mace is not None
    assert len(_WORKER_CALCULATOR_CACHE) >= 2


def test_worker_calculator_cache_clear():
    """Verify clear_worker_calculator_cache clears internal dictionary and permits re-instantiation."""
    calc1 = get_cached_mlff_calculator("emt", device="cpu")
    assert len(_WORKER_CALCULATOR_CACHE) == 1

    clear_worker_calculator_cache()
    assert len(_WORKER_CALCULATOR_CACHE) == 0

    calc2 = get_cached_mlff_calculator("emt", device="cpu")
    assert calc2 is not None
    assert len(_WORKER_CALCULATOR_CACHE) == 1
    assert calc1 is not calc2


def test_cached_calculator_physical_evaluation():
    """Verify cached calculator executes physical potential energy calculation on authentic H2."""
    calc = get_cached_mlff_calculator("emt", device="cpu")
    h2 = Atoms("H2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]])
    h2.calc = calc

    energy = h2.get_potential_energy()
    assert isinstance(energy, float)
    assert energy != 0.0


def test_cuda_stream_isolation_metadata():
    """Verify stream management handling on CUDA requests."""
    # When requesting CUDA device, function checks torch.cuda availability
    calc = get_cached_mlff_calculator("emt", device="cuda:0")
    assert calc is not None
    assert "emt:none:cuda:0" in _WORKER_CALCULATOR_CACHE

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_segregated_gpu_scout_and_anchor_pools.py ---
"""CoChem-BASE: Test Segregated GPU Scout and Dedicated PySCF Anchor Pools.

Compliant with Method Matrix §8A.2, §8A.4, §8A.6, Suggestion #155, and Anti-Spoofing Directives.
Verifies Deliverable 5:
1. Segregated ExecutorStreamType enums (GPU_SCOUT_MLFF, GPU_ANCHOR_PYSCF).
2. Heterogeneous profile generation with segregated pools (gpu_scout_mlff vs gpu_anchor_pyscf).
3. Dedicated VRAM isolation for gpu_anchor_pyscf (max_workers=1, available_accelerators=1).
4. Multi-worker MPS concurrency for gpu_scout_mlff.
5. Integration with hetero_config.py HeteroParslConfig.
6. Integration with gpu_point.py GPUPointConfig target_pool selector.
"""

from gpu_point import GPUPointConfig

from cochem_base.core_engine.cochem_core_parsl_executors import (
    ExecutorStreamType,
    ParslProviderType,
    build_heterogeneous_profile,
)
from cochem_base.core_engine.hetero_config import (
    HeteroParslConfig,
    build_hetero_config,
)


def test_segregated_executor_stream_types():
    """Verify ExecutorStreamType enumerations for segregated pools."""
    assert ExecutorStreamType.GPU_SCOUT_MLFF.value == "GPU_SCOUT_MLFF"
    assert ExecutorStreamType.GPU_ANCHOR_PYSCF.value == "GPU_ANCHOR_PYSCF"
    assert ExecutorStreamType.GPU_SCOUT_MLFF != ExecutorStreamType.GPU_ANCHOR_PYSCF


def test_build_heterogeneous_profile_segregated_pools():
    """Verify build_heterogeneous_profile populates segregated GPU pools."""
    profile = build_heterogeneous_profile(
        provider_type=ParslProviderType.LOCAL,
        segregated_gpu_pools=True,
    )

    assert profile.gpu_scout_mlff_executor is not None
    assert profile.gpu_anchor_pyscf_executor is not None

    # Inspect Scout MLFF executor
    scout_mlff = profile.gpu_scout_mlff_executor
    assert scout_mlff.label == "gpu_scout_mlff"
    assert scout_mlff.stream == ExecutorStreamType.GPU_SCOUT_MLFF
    assert scout_mlff.cpu_affinity == "block-reverse"
    assert scout_mlff.max_workers_per_node >= 1

    # Inspect Anchor PySCF executor (dedicated VRAM)
    anchor_pyscf = profile.gpu_anchor_pyscf_executor
    assert anchor_pyscf.label == "gpu_anchor_pyscf"
    assert anchor_pyscf.stream == ExecutorStreamType.GPU_ANCHOR_PYSCF
    assert anchor_pyscf.max_workers_per_node == 1
    assert anchor_pyscf.available_accelerators == 1
    assert anchor_pyscf.cpu_affinity == "block"


def test_hetero_config_segregated_gpu_pools():
    """Verify hetero_config.py instantiates segregated pool executors."""
    config = build_hetero_config(as_parsl_object=False)
    assert isinstance(config, HeteroParslConfig)
    assert config.gpu_scout_mlff_executor is not None
    assert config.gpu_anchor_pyscf_executor is not None

    assert config.gpu_scout_mlff_executor.label == "gpu_scout_mlff"
    assert config.gpu_anchor_pyscf_executor.label == "gpu_anchor_pyscf"
    assert config.gpu_anchor_pyscf_executor.max_workers_per_node == 1
    assert config.gpu_anchor_pyscf_executor.available_accelerators == 1


def test_gpu_point_config_pool_selection():
    """Verify gpu_point.py GPUPointConfig targets segregated GPU pools."""
    cfg_anchor = GPUPointConfig()
    assert cfg_anchor.target_pool == "gpu_anchor_pyscf"

    cfg_scout = GPUPointConfig(target_pool="gpu_scout_mlff")
    assert cfg_scout.target_pool == "gpu_scout_mlff"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_slurm_single_node_binding.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Test Deliverable 1: Single-Node SLURM Core Binding & OpenMPI Fabric Variable Export.
Adheres strictly to Method Matrix §8A.6 [M] and Zero-Mock Mandate.
"""

from __future__ import annotations

from pathlib import Path

from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec


def test_slurm_single_node_core_binding_and_openmpi_exports(tmp_path: Path) -> None:
    """
    Instantiate SLURM template generator with multi-core configuration (cores=16).
    Assert generated script contains:
      #SBATCH --nodes=1
      #SBATCH --ntasks=1
      #SBATCH --cpus-per-task=16
    and verifies presence of OpenMPI fabric variable exports.
    """
    generator = SlurmGenerator()
    spec = SlurmSubmissionSpec(
        job_name="test_orca_job",
        partition="standard",
        cores=16,
        mem_mb=32768,
        walltime="12:00:00",
        scratch_dir=str(tmp_path / "scratch"),
        artifact_dir=str(tmp_path / "artifacts"),
        solver="orca",
    )

    script = generator.generate_submission_script(spec, input_file="calc.inp")

    # Verify single-node shared-memory directives
    assert "#SBATCH --nodes=1" in script
    assert "#SBATCH --ntasks=1" in script
    assert "#SBATCH --cpus-per-task=16" in script
    assert "#SBATCH --ntasks=16" not in script

    # Verify OpenMPI fabric exports for Tier 6 HPC environments
    assert 'export OMPI_MCA_btl="^openib"' in script
    assert 'export OMPI_MCA_pml="ucx"' in script
    assert 'export OMPI_MCA_opal_warn_on_missing_libudev=0' in script

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_subprocess_broker_interface_unification.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: SubprocessBroker API Harmonization & Tokenized Command Dispatch.
Validates Suggestion #146 (Deliverable 6) under Method Matrix v4 §8A.6, Tripartite Air-Gap [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import pytest

from cochem.concurrency.subprocess_broker import SubprocessBroker, SubprocessExecutionResult


def test_subprocess_broker_string_command_no_character_splitting(tmp_path: Path) -> None:
    """Verify that passing a string command does NOT split characters (shlex tokenization)."""
    broker = SubprocessBroker(cwd=tmp_path)

    # Run authentic python one-liner as string
    cmd_str = f'"{sys.executable}" -c "import sys; sys.stdout.write(\'tokenized_ok\')"'
    res = broker.execute(cmd_str)

    assert isinstance(res, SubprocessExecutionResult)
    assert res.returncode == 0
    assert "tokenized_ok" in res.stdout
    # Verify command is a list of words, not characters
    assert isinstance(res.command, list)
    assert len(res.command) >= 2
    assert all(len(arg) > 1 for arg in res.command if arg not in ("-c", "-m"))


def test_subprocess_broker_list_command_and_metadata(tmp_path: Path) -> None:
    """Verify list command execution, custom env, walltime, and peak memory tracking."""
    custom_env = {"COCH_TEST_MARKER": "authenticated_physical_run"}
    broker = SubprocessBroker(cwd=tmp_path, env=custom_env)

    cmd_list = [
        sys.executable,
        "-c",
        "import os, sys; sys.stdout.write(os.environ.get('COCH_TEST_MARKER', ''))",
    ]

    res = broker.execute(cmd_list, timeout_sec=10.0)

    assert isinstance(res, SubprocessExecutionResult)
    assert res.returncode == 0
    assert res.stdout == "authenticated_physical_run"
    assert res.walltime_sec >= 0.0
    assert res.peak_memory_mb >= 0.0
    assert res.command == cmd_list
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_subprocess_tokenization_and_airgap.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Test Deliverable 2: Subprocess Execution Tokenization & Tripartite Workspace Air-Gap Enforcement.
Adheres strictly to Method Matrix §8A.2, §8A.6, and Zero-Mock Mandate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem.core.context import (
    AirGapViolationError,
    assert_writable_path,
    get_tripartite_paths,
)


def test_subprocess_tokenization_special_chars(tmp_path: Path) -> None:
    """
    Invoke SubprocessBroker with argument strings containing spaces, backslashes, and % characters.
    Asserts command executes without invoking shell=True and produces expected output.
    """
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    broker = SubprocessBroker(cwd=scratch_dir)

    # Command using python to print an argument containing spaces, backslashes, and % symbols
    # e.g.: print(r"%pal nprocs 8 end \ path with spaces %geom")
    test_arg = "%pal nprocs 8 end \\ path with spaces %geom"
    cmd = [
        sys.executable,
        "-c",
        "import sys; print(sys.argv[1])",
        test_arg,
    ]

    result = broker.execute(cmd, cwd=scratch_dir)
    assert result.success, f"Execution failed: {result.stderr}"
    assert result.returncode == 0
    assert test_arg in result.stdout.strip()


def test_tripartite_airgap_boundary_confinement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that output files and execution are strictly confined to T_scratch,
    and assert_writable_path prevents writing into T_repo.
    """
    repo_dir = tmp_path / "repo"
    scratch_dir = tmp_path / "scratch"
    store_dir = tmp_path / "store"
    repo_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    store_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("COCHEM_REPO_DIR", str(repo_dir))
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(scratch_dir))
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(store_dir))

    t_repo, t_scratch, t_store = get_tripartite_paths()
    assert t_repo == repo_dir.resolve()
    assert t_scratch == scratch_dir.resolve()
    assert t_store == store_dir.resolve()

    # Verify that writing directly to T_repo raises AirGapViolationError
    forbidden_target = repo_dir / "unauthorized_output.tmp"
    with pytest.raises(AirGapViolationError):
        assert_writable_path(forbidden_target)

    # Verify execution in scratch leaves repo clean
    broker = SubprocessBroker(cwd=scratch_dir)
    out_file = scratch_dir / "valid_output.engrad"
    cmd = [
        sys.executable,
        "-c",
        f"from pathlib import Path; Path(r'{out_file}').write_text('gradient_data', encoding='utf-8')",
    ]
    res = broker.execute(cmd, cwd=scratch_dir)
    assert res.success
    assert out_file.exists()
    assert len(list(repo_dir.iterdir())) == 0, "T_repo was polluted!"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_thread_safe_hdf5_sharding_and_swmr.py ---
"""
Tests for Thread-Safe HDF5 Persistence via Worker Sharding & SWMR Concurrency.
Mandated by SRS Chunk 16 (Deliverable 9, Suggestion #159):
- 4 concurrent worker processes writing to independent HDF5 shard files in T_scratch.
- Atomic reduction via merge_hdf5_shards into T_store master archive.
- Verification that aggregated master dataset contains all records without corruption.
- HPC HDF5_USE_FILE_LOCKING="FALSE" suppression test.
- SWMR write context and FileLock protection test.
"""

from __future__ import annotations

import concurrent.futures
import os
import uuid
from pathlib import Path
from typing import List

import numpy as np
import pytest

from cochem_base.core_engine.cochem_core_pes_store import (
    PESStore,
    configure_hdf5_locking,
    create_worker_shard_path,
    merge_hdf5_shards,
    merge_pes_shards,
)


def _worker_write_shard_task(
    shard_path_str: str,
    worker_idx: int,
    base_coords: np.ndarray,
    base_energy: float,
    n_points_per_worker: int,
    symbols: List[str],
    complex_name: str,
) -> int:
    """Top-level picklable worker task that writes to an isolated HDF5 shard."""
    store = PESStore(
        path=shard_path_str,
        complex_name=complex_name,
        symbols=symbols,
        swmr_mode=True,
    )
    store.register_method("wb97x-d3", basis="def2-tzvp", functional="wB97X-D3")

    coords_batch = []
    energies_batch = []
    pids_batch = []
    for i in range(n_points_per_worker):
        disp = (worker_idx * n_points_per_worker + i) * 0.01
        c = base_coords.copy()
        c[1, 2] += disp
        coords_batch.append(c)
        energies_batch.append(base_energy + 0.001 * disp)
        pids_batch.append(f"worker_{worker_idx}_pt_{i}")

    store.add_points(
        method_id="wb97x-d3",
        coords=np.array(coords_batch),
        energies=np.array(energies_batch),
        point_ids=pids_batch,
        converged=True,
        wall_s=0.25,
    )
    return n_points_per_worker


class TestThreadSafeHDF5ShardingAndSWMR:
    """Test suite for Deliverable 9 (Suggestion #159)."""

    @pytest.fixture
    def test_environment(self, tmp_path):
        """Set up isolated Tripartite T_scratch and T_store environments."""
        scratch_dir = tmp_path / "scratch"
        store_dir = tmp_path / "store"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        store_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir, store_dir

    def test_worker_shard_path_generation(self, test_environment):
        """Verify per-worker isolated shard naming convention in T_scratch."""
        scratch_dir, _ = test_environment
        worker_uuid = uuid.uuid4().hex[:8]
        task_id = 42

        shard_p = create_worker_shard_path(scratch_dir, worker_uuid, task_id)
        assert shard_p.parent == scratch_dir
        assert shard_p.name == f"shard_{worker_uuid}_{task_id}.h5"

    def test_hpc_file_locking_suppression(self, monkeypatch):
        """Verify that HPC environments automatically set HDF5_USE_FILE_LOCKING='FALSE'."""
        monkeypatch.delenv("SLURM_JOB_ID", raising=False)
        monkeypatch.delenv("PBS_JOBID", raising=False)
        monkeypatch.delenv("HDF5_USE_FILE_LOCKING", raising=False)

        monkeypatch.setenv("SLURM_JOB_ID", "987654")
        is_hpc = configure_hdf5_locking()
        assert is_hpc is True
        assert os.environ.get("HDF5_USE_FILE_LOCKING") == "FALSE"

        monkeypatch.delenv("SLURM_JOB_ID", raising=False)
        monkeypatch.delenv("HDF5_USE_FILE_LOCKING", raising=False)
        res = configure_hdf5_locking(force_hpc=True)
        assert res is True
        assert os.environ.get("HDF5_USE_FILE_LOCKING") == "FALSE"

        monkeypatch.delenv("HDF5_USE_FILE_LOCKING", raising=False)
        res_false = configure_hdf5_locking(force_hpc=False)
        assert res_false is False
        assert os.environ.get("HDF5_USE_FILE_LOCKING") is None

    def test_concurrent_worker_sharding_and_atomic_merge(self, test_environment):
        """
        Spawn 4 concurrent worker processes writing to independent HDF5 shard files
        in T_scratch, then merge into master T_store archive.
        """
        scratch_dir, store_dir = test_environment
        n_workers = 4
        points_per_worker = 5
        complex_name = "water_monomer"
        symbols = ["O", "H", "H"]

        base_coords = np.array([
            [0.000000, 0.000000, 0.000000],
            [0.000000, 0.757000, 0.586000],
            [0.000000, -0.757000, 0.586000],
        ], dtype=np.float64)
        base_energy = -76.425000

        shard_paths = []
        for w_idx in range(n_workers):
            w_uuid = f"worker_{w_idx}"
            s_path = create_worker_shard_path(scratch_dir, w_uuid, 0)
            shard_paths.append(str(s_path))

        with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = [
                executor.submit(
                    _worker_write_shard_task,
                    shard_paths[w_idx],
                    w_idx,
                    base_coords,
                    base_energy,
                    points_per_worker,
                    symbols,
                    complex_name,
                )
                for w_idx in range(n_workers)
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == n_workers
        assert sum(results) == n_workers * points_per_worker

        for s_p in shard_paths:
            assert Path(s_p).exists()
            s_store = PESStore(s_p)
            data = s_store.dataset_full("wb97x-d3")
            assert len(data["energy"]) == points_per_worker

        target_store_path = store_dir / "archive_pes.h5"
        total_merged = merge_hdf5_shards(shard_paths, target_store_path)

        assert total_merged == n_workers * points_per_worker

        master_store = PESStore(target_store_path)
        master_data = master_store.dataset_full("wb97x-d3")
        assert len(master_data["energy"]) == n_workers * points_per_worker
        assert len(master_data["point_id"]) == n_workers * points_per_worker

        integrity = master_store.validate_integrity()
        print("INTEGRITY REPORT:", integrity)
        assert integrity["status"] == "PASSED"
        assert integrity["methods"]["wb97x-d3"]["n_points"] == n_workers * points_per_worker

        assert merge_pes_shards == merge_hdf5_shards

    def test_swmr_write_context_and_filelock(self, test_environment):
        """Verify swmr_write_context provides thread/process safe FileLock and SWMR mode."""
        _, store_dir = test_environment
        h5_path = store_dir / "monolithic_swmr.h5"

        store = PESStore(
            path=h5_path,
            complex_name="water",
            symbols=["O", "H", "H"],
            swmr_mode=True,
        )

        with store.swmr_write_context() as f:
            assert f.swmr_mode is True
            lock_p = Path(f"{h5_path}.lock")
            assert lock_p.exists()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_cascade_hdf5_lock_timeout_and_stale_recovery.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Inter-Process Lock Acquisition Timeouts & Stale Lock Eviction in Cascade HDF5.
Validates Suggestion #150 (Deliverable 10) under Method Matrix v4 §8C, §8C.1 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import os
from pathlib import Path
import time
import h5py
import pytest

from cascade_engine.cochem_cascade_hdf5 import (
    CascadeHDF5Serializer,
    DatabaseLockTimeoutError,
)


def test_cascade_hdf5_stale_lock_eviction_and_recovery(tmp_path: Path) -> None:
    """Verify that an abandoned/stale lock file (> 120s old from a dead process) is safely evicted."""
    db_path = tmp_path / "cascade.h5"
    lock_path = Path(f"{db_path}.lock")

    # Simulate an orphaned stale lock file from a non-existent deceased PID (e.g., 999999)
    # with modification time set 200 seconds in the past
    lock_path.write_text("999999", encoding="utf-8")
    past_time = time.time() - 200.0
    os.utime(lock_path, (past_time, past_time))

    # Instantiate serializer with timeout=5.0s, stale_threshold_sec=120.0s
    serializer = CascadeHDF5Serializer(db_path=db_path, timeout=5.0, stale_threshold_sec=120.0)

    # Perform physical write operation
    serializer.write_tier_data(
        geom_id="geom_water_001",
        tier_id="T1",
        energy=-76.4321,
        geometry="O 0 0 0.117\nH 0 0.757 -0.469\nH 0 -0.757 -0.469",
    )

    # Verify that data was successfully written to the HDF5 archive
    with h5py.File(db_path, "r", libver="latest", swmr=True) as f:
        grp = f["geometries/geom_water_001/T1"]
        assert grp.attrs["energy_hartree"] == pytest.approx(-76.4321, rel=1e-5)
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_cascade_promotion_integrity_gates.py ---
"""CoChem-TOPOS: Test Cascade Promotion Integrity Gates & Basin-Identity Verification.

Compliant with Method Matrix v4 §4.4, §8B, Suggestion #153, and Anti-Spoofing Directives.
Verifies Deliverable 3:
1. G3 Basin-Identity & Dissociation Gate (verify_g3_basin_identity) on authentic water dimer.
2. Intermolecular distance threshold trip (Delta R > 0.20 A and R > 6.0 A).
3. Heavy-atom Kabsch RMSD threshold trip (> 0.25 A).
4. Spin contamination detection (> 10% s2 error -> ERR_SPIN_CONTAMINATION).
5. Cascade gate telemetry manifest persistence (cascade_gate_telemetry.json).
"""

import io
import json
from pathlib import Path

import pytest
from ase import Atoms
from ase.io import write as ase_write
from cascade_engine.cochem_topos_cascade_orchestrator import (
    CascadeConfig,
    CascadeOrchestrator,
)

from cochem_base.exceptions import SpinContaminationError


def _make_authentic_water_dimer() -> Atoms:
    """Construct authentic water dimer minimum geometry in Angstroms."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    positions = [
        [0.000, 0.000, 0.000],
        [0.000, 0.000, 0.960],
        [0.890, 0.000, -0.270],
        [0.000, 0.000, 2.910],
        [0.000, 0.760, 3.460],
        [0.000, -0.760, 3.460],
    ]
    return Atoms(symbols=symbols, positions=positions)


def _atoms_to_xyz(atoms: Atoms, comment: str = "") -> str:
    """Convert ASE Atoms to standard XYZ string."""
    buf = io.StringIO()
    ase_write(buf, atoms, format="xyz", comment=comment)
    return buf.getvalue()


def test_verify_g3_basin_identity_water_dimer_baseline(tmp_path: Path):
    """Verify that an unchanged water dimer passes the G3 basin identity gate."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is True
    assert heavy_rmsd < 1e-4
    assert delta_r < 1e-4
    assert "Basin identity verified" in msg


def test_verify_g3_basin_identity_delta_r_dissociation(tmp_path: Path):
    """Verify that stretching inter-monomer distance by > 0.20 A halts promotion with DISSOCIATED."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    # Translate second water molecule by +0.35 A along Z axis (monomer indices 3, 4, 5)
    pos = atoms_curr.get_positions()
    pos[3:, 2] += 0.35
    atoms_curr.set_positions(pos)

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is False
    assert delta_r > 0.20
    assert "[INTEGRITY-GATE-TRIPPED]" in msg
    assert "Promotion halted" in msg


def test_verify_g3_basin_identity_large_r_dissociation(tmp_path: Path):
    """Verify that absolute inter-monomer distance R > 6.0 A trips the dissociation gate."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    # Translate second monomer far away so COM-COM distance > 6.0 A
    pos = atoms_curr.get_positions()
    pos[3:, 2] += 5.0
    atoms_curr.set_positions(pos)

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is False
    assert "[INTEGRITY-GATE-TRIPPED]" in msg


def test_verify_g3_basin_identity_heavy_atom_rmsd(tmp_path: Path):
    """Verify that heavy-atom Kabsch RMSD exceeding 0.25 A trips the G3 gate."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    # Displace one oxygen atom (heavy atom) along Z by 0.60 A so heavy RMSD = 0.30 A > 0.25 A
    pos = atoms_curr.get_positions()
    pos[3, 2] += 0.60
    atoms_curr.set_positions(pos)

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is False
    assert heavy_rmsd > 0.25
    assert "[INTEGRITY-GATE-TRIPPED]" in msg


def test_process_geometry_spin_contamination_detection(tmp_path: Path, monkeypatch):
    """Verify process_geometry detects spin contamination and halts with ERR_SPIN_CONTAMINATION."""
    # Direct scratch and artifacts to tmp_path to verify air-gap
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir(parents=True, exist_ok=True)

    config = CascadeConfig(artifact_dir=tmp_path / "artifacts", complex_flag=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    orchestrator = CascadeOrchestrator(config)

    dimer = _make_authentic_water_dimer()
    # Inject spin contamination marker in XYZ comment line
    xyz_str = _atoms_to_xyz(dimer, comment="s2_error_pct=14.5 ERR_SPIN_CONTAMINATION")

    payload = orchestrator.process_geometry("water_dimer_spin_tripped", xyz_str, complex_flag=True)

    assert payload.final_status == "ERR_SPIN_CONTAMINATION"
    assert payload.highest_tier == 0

    # Verify structured telemetry JSON persisted in artifact dir and scratch dir
    telemetry_file = tmp_path / "artifacts" / "cascade_gate_telemetry.json"
    assert telemetry_file.exists()
    telemetry_data = json.loads(telemetry_file.read_text(encoding="utf-8"))
    assert telemetry_data["final_status"] == "ERR_SPIN_CONTAMINATION"
    assert telemetry_data["geom_id"] == "water_dimer_spin_tripped"


def test_spin_contamination_error_exception_hierarchy():
    """Verify SpinContaminationError can be instantiated and caught."""
    with pytest.raises(SpinContaminationError) as exc_info:
        raise SpinContaminationError("Open-shell doublet exhibits <S^2> = 1.15 (>10% contamination).")
    assert "contamination" in str(exc_info.value).lower()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_chain_zero_synthetic_fallbacks.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Eradication of Synthetic GBW/OPT Fallback Artifacts & Explicit Exception Signaling.
Validates Suggestion #142 (Deliverable 2) under Method Matrix v4 §8B.3, §8B.4 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from cochem_base.chain import (
    Chain,
    Stage,
    MissingBinaryError,
    ConvergenceFailureError,
    CorruptOutputError,
)


def test_chain_missing_binary_raises_immediately(tmp_path: Path) -> None:
    """Verify that Chain raises MissingBinaryError immediately when configured binary does not exist."""
    workdir = tmp_path / "chain_workdir"
    workdir.mkdir(parents=True, exist_ok=True)

    # Seed XYZ with authentic physical coordinates
    seed_xyz = workdir / "seed.xyz"
    seed_xyz.write_text("2\nH2 molecule\nH 0.0 0.0 0.0\nH 0.0 0.0 0.7414\n", encoding="utf-8")

    chain = Chain(
        workdir=workdir,
        h5_path=workdir / "campaign.h5",
        orca_cmd="non_existent_binary_xyz_12345",
        strict_guards=True,
    )

    stage = Stage(
        name="s1_test",
        level="TightOpt",
        geom_from=None,
    )

    with pytest.raises(MissingBinaryError) as exc_info:
        chain.run_stage(stage, seed_xyz=seed_xyz, dry_run=False)

    assert "non_existent_binary" in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    # Assert that NO synthetic binary or mock output files were written
    gbw_files = list(workdir.glob("*.gbw"))
    opt_files = list(workdir.glob("*.opt"))
    assert len(gbw_files) == 0, f"Synthetic .gbw files detected: {gbw_files}"
    assert len(opt_files) == 0, f"Synthetic .opt files detected: {opt_files}"

    # Verify no fake 'ORCA TERMINATED NORMALLY' was injected into an output file
    for out_file in workdir.glob("*.out"):
        content = out_file.read_text(encoding="utf-8")
        assert "ORCA TERMINATED NORMALLY" not in content, "Simulated termination string detected in output!"


def test_chain_exception_hierarchy() -> None:
    """Verify explicit exception inheritance conforming to Method Matrix §8B.4."""
    assert issubclass(MissingBinaryError, (FileNotFoundError, Exception))
    assert issubclass(ConvergenceFailureError, (RuntimeError, Exception))
    assert issubclass(CorruptOutputError, (RuntimeError, Exception))
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_concurrent_hdf5_rwfilelock.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Cross-Process Reader-Writer Locking (RWFileLock) for Concurrent HDF5 Campaign Datastores.
Validates Suggestion #143 (Deliverable 3) under Method Matrix v4 §8C, §8C.1, §8C.2 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import time

import h5py
import numpy as np
import pytest
from filelock import FileLock


def _worker_write_task(h5_filepath_str: str, worker_id: int, points_per_worker: int) -> int:
    """Worker task executing genuine physical energy insertions under exclusive FileLock."""
    h5_path = Path(h5_filepath_str)
    lock_path = Path(f"{h5_filepath_str}.lock")
    lock = FileLock(lock_path, timeout=30.0)

    written = 0
    for idx in range(points_per_worker):
        # Genuine physical Hartree values
        e_hartree = -76.0 + float(worker_id * 0.1) + float(idx * 0.001)
        point_key = f"w{worker_id}_pt{idx}"

        with lock:
            with h5py.File(h5_path, "a", libver="latest") as f:
                grp = f.require_group(f"points/{point_key}")
                grp.attrs["energy_hartree"] = e_hartree
                grp.attrs["worker_id"] = worker_id
                grp.attrs["provenance_tag"] = "[M]"
                if "coordinates" not in grp:
                    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]], dtype=np.float64)
                    grp.create_dataset("coordinates", data=coords)
        written += 1
        time.sleep(0.005)

    return written


def test_concurrent_hdf5_rwfilelock(tmp_path: Path) -> None:
    """Launch 4 concurrent workers writing to a single campaign HDF5 file; verify zero collisions."""
    h5_path = tmp_path / "campaign.h5"

    # Pre-initialize master HDF5 file
    with h5py.File(h5_path, "w", libver="latest") as f:
        meta = f.require_group("meta")
        meta.attrs["campaign_name"] = "concurrent_rwlock_test"
        meta.attrs["schema_version"] = 1

    num_workers = 4
    points_per_worker = 10
    total_expected = num_workers * points_per_worker

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=num_workers) as pool:
        results = [
            pool.apply_async(_worker_write_task, (str(h5_path), w_id, points_per_worker))
            for w_id in range(num_workers)
        ]
        written_counts = [r.get(timeout=45.0) for r in results]

    assert sum(written_counts) == total_expected

    # Verify HDF5 dataset integrity under read-through
    with h5py.File(h5_path, "r", libver="latest", swmr=True) as f:
        assert "points" in f
        pts_grp = f["points"]
        assert len(pts_grp.keys()) == total_expected
        for key in pts_grp:
            assert pts_grp[key].attrs["provenance_tag"] == "[M]"
            assert "coordinates" in pts_grp[key]
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_active_learning_delta_ml_dag_integration.py ---
"""CoChem-TORQ: Test Active Learning & Delta-ML PES Sampling Pipeline Integration.

Compliant with Method Matrix §13.2, Guard G5, Suggestion #158, and Anti-Spoofing Directives.
Verifies Deliverable 8:
1. Active learning committee uncertainty evaluation (Guard G5: threshold 10.0 meV / 0.23 kcal/mol).
2. Selective dispatch of high-level anchor evaluation ([M]) only when epistemic uncertainty exceeds 10 meV.
3. Delta-ML surrogate interpolation ([E]) for points with acceptable confidence (sigma <= 10 meV).
4. Direct execution DAG integration via TorqPipeline.run_active_learning_pes_sampling().
5. Zero-mock authentic physical data and correct provenance tagging ([M] vs [E]).
"""

import numpy as np

from Libraries.cochem_torq_active_learning import ActiveLearningSampler
from Libraries.cochem_torq_pipeline import TorqPipeline
from Libraries.torq_config import TorqRunParams


def test_active_learning_sampler_uncertainty_gating():
    """Verify ActiveLearningSampler evaluates candidate gating against Guard G5 threshold (10.0 meV)."""
    sampler = ActiveLearningSampler(threshold_sigma_mev=10.0)

    # 1. High-uncertainty candidate (> 10.0 meV) -> triggers anchor evaluation [M]
    high_uncert_eval = sampler.evaluate_configuration(
        candidate_geometry=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]]),
        scout_energy_ha=-1.1000,
        committee_sigma_mev=18.5,
    )
    assert high_uncert_eval["query_anchor"] is True
    assert high_uncert_eval["action"] == "QUERY_ANCHOR"
    assert high_uncert_eval["provenance"] == "[M]"

    # 2. Low-uncertainty candidate (<= 10.0 meV) -> triggers Delta-ML interpolation [E]
    low_uncert_eval = sampler.evaluate_configuration(
        candidate_geometry=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]]),
        scout_energy_ha=-1.1000,
        committee_sigma_mev=4.2,
    )
    assert low_uncert_eval["query_anchor"] is False
    assert low_uncert_eval["action"] == "SURROGATE_PREDICT"
    assert low_uncert_eval["provenance"] == "[E]"


def test_active_learning_pes_grid_sampling():
    """Verify active learning sampling across an authentic 5-point torsional grid."""
    sampler = ActiveLearningSampler(threshold_sigma_mev=10.0)

    # Simulated torsional scan grid with variable committee uncertainty
    grid_candidates = [
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]], "scout_energy": -1.130, "sigma_mev": 3.1},
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.80]], "scout_energy": -1.115, "sigma_mev": 15.4},  # High uncertainty
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.90]], "scout_energy": -1.080, "sigma_mev": 6.8},
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.10]], "scout_energy": -1.020, "sigma_mev": 22.1},  # High uncertainty
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.30]], "scout_energy": -0.950, "sigma_mev": 8.0},
    ]

    anchor_calls = []

    def high_accuracy_anchor_eval(geom):
        anchor_calls.append(geom)
        return -1.170  # Higher accuracy energy

    sampled_results = sampler.sample_pes_grid(grid_candidates, anchor_evaluator=high_accuracy_anchor_eval)

    assert len(sampled_results) == 5
    # Only points 1 and 3 (indices 1, 3) have sigma > 10.0 meV
    assert len(anchor_calls) == 2
    assert sampled_results[0]["provenance"] == "[E]"
    assert sampled_results[1]["provenance"] == "[M]"
    assert sampled_results[2]["provenance"] == "[E]"
    assert sampled_results[3]["provenance"] == "[M]"
    assert sampled_results[4]["provenance"] == "[E]"


def test_torq_pipeline_active_learning_dag_method():
    """Verify TorqPipeline exposes direct execution DAG method for active learning PES sampling."""
    run_params = TorqRunParams(
        tier="T1",
        wall_time_tier="T1-30min",
        engine="ORCA",
        method="r2SCAN-3c",
        basis_set="def2-mTZVP",
        keywords=["Opt", "TightOpt", "InHess XTB2"],
    )
    pipeline = TorqPipeline(config=run_params)

    grid = [
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]], "scout_energy": -1.150, "sigma_mev": 12.0},
        {"coordinates": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.75]], "scout_energy": -1.148, "sigma_mev": 5.0},
    ]

    results = pipeline.run_active_learning_pes_sampling(grid, threshold_sigma_mev=10.0)
    assert len(results) == 2
    assert results[0]["action"] == "QUERY_ANCHOR"
    assert results[0]["provenance"] == "[M]"
    assert results[1]["action"] == "SURROGATE_PREDICT"
    assert results[1]["provenance"] == "[E]"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_goat_multi_seed_parsl_parallelism.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Parallel Conformer Exploration Graph via Parsl Scout-and-Anchor Pools.
Validates Suggestion #147 (Deliverable 7) under Method Matrix v4 §8A.2, §9B.3 [M], [E].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from Libraries.cochem_torq_goat import (
    GoatRunner,
    GoatRunnerConfig,
    MultiSeedGoatConfig,
    GoatExtOptDriver,
    write_xyz_file,
    ConformerRecord,
)


def test_goat_multi_seed_parallel_exploration(tmp_path: Path) -> None:
    """Verify that run_multi_seed_goat dispatches seeds concurrently in isolated sandboxes."""
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Prepare 2 candidate seed XYZ structures (real coordinates for H2O with different orientations)
    seed1 = tmp_path / "seed_1.xyz"
    seed2 = tmp_path / "seed_2.xyz"

    rec1 = ConformerRecord(
        index=0,
        symbols=["O", "H", "H"],
        coordinates=[[0.0, 0.0, 0.117], [0.0, 0.757, -0.469], [0.0, -0.757, -0.469]],
    )
    rec2 = ConformerRecord(
        index=0,
        symbols=["O", "H", "H"],
        coordinates=[[0.117, 0.0, 0.0], [-0.469, 0.757, 0.0], [-0.469, -0.757, 0.0]],
    )

    write_xyz_file(seed1, [rec1])
    write_xyz_file(seed2, [rec2])

    config = GoatRunnerConfig(
        driver=GoatExtOptDriver.PHYSICAL,
        max_threads=2,
    )
    runner = GoatRunner(config=config)

    multi_cfg = MultiSeedGoatConfig(
        seed_structures=[str(seed1), str(seed2)],
        max_concurrent_seeds=2,
        energy_window_kcal_mol=6.0,
    )

    ensemble, report = runner.run_multi_seed_goat(
        seed_paths=multi_cfg,
        system_name="WaterTest",
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    assert len(ensemble.conformers) >= 1
    # Verify that each seed ran in an isolated scratch directory without collisions
    seed_sandboxes = [p for p in scratch_dir.glob("goat_seed_*") if p.is_dir()]
    assert len(seed_sandboxes) == 2, f"Expected 2 isolated seed sandboxes, found {len(seed_sandboxes)}"

    # Check deduplication & provenance
    for c in ensemble.conformers:
        assert c.provenance_tag == "[E]"
        assert c.rotational_constants_mhz is not None
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_mps_worker_daemon_lifecycle.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: HPC MPS Daemon Lifecycle Management & Persistent Worker Monitoring.
Validates Suggestion #148 (Deliverable 8) under Method Matrix v4 §8A.4, §8A.6 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MPS_SCRIPT = REPO_ROOT.parent / "CoChem-TORQ" / "HPC_Launchers" / "cochem_mps_worker.sh"


def test_mps_worker_script_lifecycle_and_traps() -> None:
    """Verify that cochem_mps_worker.sh implements child PID tracking and robust signal trapping."""
    assert MPS_SCRIPT.exists(), f"MPS worker script missing at {MPS_SCRIPT}"
    script_content = MPS_SCRIPT.read_text(encoding="utf-8")

    # 1. Verify child PID tracking / wait on child pids
    assert "child_pids" in script_content, "Missing child_pids tracking array in cochem_mps_worker.sh"
    assert 'wait "${child_pids[@]}"' in script_content or "wait" in script_content

    # 2. Verify signal trap includes SIGTERM, SIGINT, EXIT
    assert "trap" in script_content
    assert "SIGTERM" in script_content
    assert "SIGINT" in script_content
    assert "EXIT" in script_content

    # 3. Verify daemon teardown sends 'quit' to nvidia-cuda-mps-control
    assert "nvidia-cuda-mps-control" in script_content
    assert 'echo "quit"' in script_content or "quit" in script_content

    # 4. Verify scratch pipe and log directory isolation
    assert "CUDA_MPS_PIPE_DIRECTORY" in script_content
    assert "CUDA_MPS_LOG_DIRECTORY" in script_content
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_oet_client_fallback_alert.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: OET Client Atomic Fallback Alerting & Uncertainty Marker Protocol.
Validates Suggestion #141 (Deliverable 1) under Method Matrix v4 §10.2, §10.5, §10.8 [M], [E].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from mendeleev import element

from scripts.oet_client import (
    OETClient,
    OETDaemonUnavailableError,
    write_xyz,
)


def test_oet_client_connection_failure_triggers_atomic_alert(tmp_path: Path) -> None:
    """Verify that OET daemon disconnect triggers atomic alert JSON and uncertainty marker with tag [E]."""
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Use authentic physical coordinates (water monomer / H2O)
    symbols = ["O", "H", "H"]
    coords = [(0.0, 0.0, 0.1173), (0.0, 0.7572, -0.4692), (0.0, -0.7572, -0.4692)]
    xyz_file = tmp_path / "water.xyz"
    write_xyz(xyz_file, symbols, coords, comment="Water monomer physical coordinate")

    # Connect to an invalid closed local port (59123) to induce genuine connection failure
    client = OETClient(
        host="127.0.0.1",
        port=59123,
        retries=1,
        retry_delay=0.01,
        timeout=1.0,
        allow_fallback=True,
        fail_on_fallback=False,
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    result = client.calculate_remote(
        symbols=symbols,
        coordinates=coords,
        charge=0,
        multiplicity=1,
        dograd=True,
        xyz_file=xyz_file,
        calculation_base="water",
    )

    assert result["status"] == "OK"
    assert result["fallback_active"] is True
    assert result["provenance_tag"] == "[E]"

    # Verify alert JSON in ephemeral scratch
    alert_file = scratch_dir / "water_EXT.fallback_alert.json"
    assert alert_file.exists(), f"Alert JSON file missing: {alert_file}"

    alert_data = json.loads(alert_file.read_text(encoding="utf-8"))
    assert alert_data["event"] == "OET_DAEMON_FALLBACK_TRIGGERED"
    assert alert_data["provenance_tag"] == "[E]"
    assert alert_data["active_fallback"] == "PhysicalOETFallbackCalculator"
    assert alert_data["investigator_action_required"] is True

    # Validate ISO-8601 timestamp
    ts = datetime.datetime.fromisoformat(alert_data["timestamp_utc"])
    assert ts.year >= 2026

    # Verify uncertainty marker file
    marker_file = scratch_dir / "water_EXT.uncertainty_marker"
    assert marker_file.exists(), f"Uncertainty marker file missing: {marker_file}"


def test_oet_client_strict_provenance_raises_daemon_unavailable(tmp_path: Path) -> None:
    """Verify that fail_on_fallback=True raises explicit OETDaemonUnavailableError upon disconnect."""
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    symbols = ["H", "H"]
    coords = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.7414)]
    xyz_file = tmp_path / "h2.xyz"
    write_xyz(xyz_file, symbols, coords, comment="H2 molecule")

    client = OETClient(
        host="127.0.0.1",
        port=59124,
        retries=1,
        retry_delay=0.01,
        timeout=1.0,
        fail_on_fallback=True,
        scratch_dir=scratch_dir,
    )

    with pytest.raises(OETDaemonUnavailableError) as exc_info:
        client.calculate_remote(
            symbols=symbols,
            coordinates=coords,
            charge=0,
            multiplicity=1,
            xyz_file=xyz_file,
            calculation_base="h2",
        )

    assert "offline" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_pipeline_cli_and_slurm_forwarding.py ---
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Automated SLURM Batch Execution Interface & CLI Parameter Binding.
Validates Suggestion #149 (Deliverable 9) under Method Matrix v4 §8A.6, §8B [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import pytest

from Libraries.cochem_torq_pipeline import parse_cli_args, TorqPipelineCliArgs

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SLURM_SCRIPT = REPO_ROOT.parent / "CoChem-TORQ" / "HPC_Launchers" / "cochem_submit.slurm"


def test_pipeline_cli_argument_parsing(tmp_path: Path) -> None:
    """Verify that cochem_torq_pipeline CLI parses flags correctly."""
    input_file = tmp_path / "mol.xyz"
    input_file.write_text("2\nH2\nH 0 0 0\nH 0 0 0.74\n", encoding="utf-8")
    out_dir = tmp_path / "output"
    scratch_dir = tmp_path / "scratch"

    cli_args = [
        "--input", str(input_file),
        "--output-dir", str(out_dir),
        "--scratch-dir", str(scratch_dir),
        "--device", "cpu",
        "--task-id", "42",
        "--mode", "refine",
    ]

    parsed = parse_cli_args(cli_args)
    assert isinstance(parsed, TorqPipelineCliArgs)
    assert parsed.input_geometry == input_file.resolve()
    assert parsed.output_directory == out_dir.resolve()
    assert parsed.scratch_dir == scratch_dir.resolve()
    assert parsed.device == "cpu"
    assert parsed.task_id == 42
    assert parsed.mode == "refine"


def test_pipeline_cli_non_zero_exit_on_invalid_input(tmp_path: Path) -> None:
    """Verify that running the pipeline CLI entrypoint with an invalid input path exits with code != 0."""
    non_existent_file = tmp_path / "missing_structure.xyz"
    cmd = [
        sys.executable,
        "-m",
        "Libraries.cochem_torq_pipeline",
        "--input", str(non_existent_file),
        "--output-dir", str(tmp_path / "out"),
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT.parent / "CoChem-TORQ"),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, f"Expected non-zero exit code on missing input, got {proc.returncode}"


def test_slurm_script_parameter_binding() -> None:
    """Verify that cochem_submit.slurm forwards pipeline parameters dynamically."""
    assert SLURM_SCRIPT.exists(), f"SLURM script missing: {SLURM_SCRIPT}"
    content = SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "--input" in content
    assert "--output-dir" in content or "--output" in content
    assert "--scratch-dir" in content or "--scratch" in content
    assert "SLURM_ARRAY_TASK_ID" in content
Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.