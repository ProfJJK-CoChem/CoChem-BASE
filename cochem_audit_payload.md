Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260903-061002-brainstorm\.in-progress\Perfected_SRS_Chunk_03_Core_Part_3_prompts.md.
Original prompt:
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 3: Suggestions #21–#30)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §8A, §8A.1, §8A.4, §8B, §8B.3, §8C, §9A.5, §16.1, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Workspace Air-Gap Architecture ($R_{\text{src}}$ read-only codebase, $R_{\text{data}}$ read-only data, $R_{\text{art}}$ read-write artifacts, $T_{\text{scr}}$ ephemeral isolated scratch)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- OS-Agnostic Dynamic Path Resolution Mandate (`pathlib.Path`, dynamic tempdir/slurm scratch, zero hardcoded drive letters or shell symbols)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #21 through #30 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical concurrency, hardware topology budgeting, filesystem synchronization, process containment, and self-healing fault remediation vulnerabilities across the 6-Tier Environment Matrix.

Specific targets include eliminating race conditions and thread thrashing in task dispatching and hardware core allocation, implementing cross-process and distributed network filesystem locking, enforcing Tripartite Workspace Air-Gap scratch isolation, providing true Reader-Writer locking and thread-safe HDF5 SWMR synchronization, injecting decoupled parameter remediation callbacks into subprocess failure loops, and verifying total process subtree termination to eliminate orphaned ghost processes and GPU memory leaks.

Every modification must be accompanied by comprehensive, zero-mock unit and integration tests executing real physical computations, thread stress tests, and OS-level process validations.

---

## 2. Target Files & Deliverable Manifest

### Core Concurrency, Scheduler & State Modules
1. `src/cochem/core/process_reaper.py` (Suggestions #21, #24, #30)
2. `src/cochem_base/core_engine/cochem_core_scheduler.py` (Suggestions #22, #23)
3. `src/cochem/core/hardware/topology.py` (Suggestion #25)

### Filesystem Synchronization & Air-Gap Modules
4. `src/cochem/concurrency/atomic_file_lock.py` (Suggestion #28)
5. `src/cochem/concurrency/network_lock.py` (Suggestion #26)
6. `src/cochem_base/cochem_spycfit_ml_storage.py` (Suggestion #26)
7. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestion #28)

### Subprocess Broker & Remediation Modules
8. `src/cochem/concurrency/subprocess_broker.py` (Suggestions #27, #29)
9. `src/cochem_base/core_engine/cochem_core_subprocess_broker.py` (Suggestions #27, #29)

### Zero-Mock Test Suite Deliverables
10. `tests/concurrency/test_concurrency_chunk3.py` (Validating Suggestions #21, #22, #24, #25, #30)
11. `tests/core/test_filesystem_remediation_chunk3.py` (Validating Suggestions #23, #26, #27, #28, #29)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Thread-Safe Process Tree Management & Atomic Snapshot Iteration (Suggestion #21)]
- **File Affected:** `src/cochem/core/process_reaper.py` (around lines 65–140, 217–285)
- **Problem Statement:**
  `ZombieReaperDaemon.sweep_orphans()` iterates over `self.tree_manager._tracked.keys()` while worker threads concurrently register new child processes via `register_process()`. Because `ProcessTreeManager` uses an unsynchronized Python dictionary, concurrent access under heavy job dispatch triggers `RuntimeError: dictionary changed size during iteration`, crashing the watchdog daemon and halting orphan process cleanup across all execution tiers.
- **Implementation Requirements:**
  1. Add a reentrant lock `self._lock = threading.RLock()` to `ProcessTreeManager.__init__()`.
  2. Guard all mutations and reads of `self._tracked` (`register_process`, `unregister_process`, `is_alive`, `get_metadata`, `tracked_pids`) under `with self._lock:`.
  3. Expose a thread-safe snapshot method `get_tracked_pids() -> List[int]` that returns `list(self._tracked.keys())` under lock.
  4. In `ZombieReaperDaemon.sweep_orphans()`, replace direct access to `self.tree_manager._tracked.keys()` with `self.tree_manager.get_tracked_pids()`, ensuring iteration operates on an immutable point-in-time snapshot.

---

### [Task 2: Thread-Safe Queue & Event-Driven Worker Saturation in CoreScheduler (Suggestion #22)]
- **File Affected:** `src/cochem_base/core_engine/cochem_core_scheduler.py` (lines 74–204)
- **Problem Statement:**
  `CoreScheduler` manages task dispatch via `self.task_queue: List[TaskConfig] = []` with unsynchronized `append()` and `pop(0)`. Under concurrent submissions, list `pop(0)` is not thread-safe, has $O(N)$ removal cost, and raises `IndexError`. Furthermore, `_scheduler_loop` sleeps for 0.5 s per tick and pops only a single task, artificially capping dispatch throughput to 2 tasks/s and introducing up to 500 ms of latency per task.
- **Implementation Requirements:**
  1. Replace `List[TaskConfig]` with `queue.Queue[TaskConfig]` (or `queue.PriorityQueue` supporting priority dispatch).
  2. Update `add_task(task: TaskConfig)` to use `self.task_queue.put(task)`.
  3. Refactor `_scheduler_loop` to use an event-driven worker saturation pattern:
     - Replace static `time.sleep(0.5)` with blocking `self.task_queue.get(timeout=0.1)` or `threading.Event` signaling.
     - While idle worker slots are available in `ThreadPoolExecutor` and tasks exist in the queue, immediately drain and submit tasks to saturate worker capacity without artificial delays.
  4. Handle graceful shutdown in `stop_scheduling()`: signal the shutdown event, drain pending queue state if necessary, and join the scheduler thread with a 2.0 s timeout.

---

### [Task 3: Cross-Process Atomic State Persistence & HPC Staging for `swarm_state.json` (Suggestion #23)]
- **File Affected:** `src/cochem_base/core_engine/cochem_core_scheduler.py` (lines 141–166)
- **Problem Statement:**
  `CoreScheduler._update_swarm_state` relies on an in-memory `self._state_lock = threading.Lock()` to synchronize updates to `swarm_state.json`. Because swarm agents, CLI tools, and background schedulers run as separate OS processes, in-memory locks provide zero protection across processes. Multiple processes writing concurrently cause file truncation, corrupted JSON syntax, and lost status telemetry. Furthermore, direct locking on HPC network filesystems causes distributed lock manager deadlocks.
- **Implementation Requirements:**
  1. On single-node environments (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions):
     - Wrap file access in `filelock.FileLock(str(state_file) + ".lock", timeout=10.0)`.
     - Implement atomic writes: write payload to an ephemeral sibling file `state_file.with_name(f"{state_file.name}.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")`, flush and sync via `os.fsync()`, and atomically replace the target using `os.replace()`.
  2. On Tier 6 HPC network filesystems (detected via `SLURM_JOB_ID`, `PBS_JOBID`, or parallel filesystem mounts Lustre/GPFS/NFS):
     - Stage updates to node-local fast scratch (`$SLURM_TMPDIR` or `$TMPDIR`).
     - Write the atomic temporary file, compute its SHA-256 digest, atomically copy/replace to the shared target path, and write an accompanying `.sha256` sidecar verification file to ensure downstream readers never ingest partial writes.
  3. Ensure robust error handling: if lock acquisition times out after 10.0 s, log an explicit warning and retry with exponential backoff before failing safely.

---

### [Task 4: Win32 Kernel Handle RAII Hygiene & POSIX Process Group Containment (Suggestion #24)]
- **File Affected:** `src/cochem/core/process_reaper.py` (lines 94–123)
- **Problem Statement:**
  In `ProcessTreeManager.register_process`, Windows execution calls `win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)` to obtain a process handle for `win32job.AssignProcessToJobObject(self._job_handle, process_handle)`. The handle is never closed. Because Win32 process handles are reference-counted kernel objects, omitting `win32api.CloseHandle(process_handle)` leaks open kernel handles indefinitely. Long-running daemons accumulate thousands of handles, degrading OS kernel performance and eventually failing process creation with `ERROR_NO_SYSTEM_RESOURCES` (Error 1450).
- **Implementation Requirements:**
  1. On Windows (`sys.platform == "win32"`):
     - Enforce strict RAII cleanup for process handles:
       ```python
       process_handle = None
       try:
           process_handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
           if process_handle:
               win32job.AssignProcessToJobObject(self._job_handle, process_handle)
       except Exception as assign_err:
           logger.debug("Could not assign PID %d to Windows Job Object: %s", pid, assign_err)
       finally:
           if process_handle:
               try:
                   win32api.CloseHandle(process_handle)
               except Exception as close_err:
                   logger.debug("Error closing process handle for PID %d: %s", pid, close_err)
       ```
  2. On POSIX environments (Linux, macOS, Codespaces, HPC):
     - Standardize process containment by ensuring that when spawning child subprocesses, `start_new_session=True` or `preexec_fn=os.setpgrp` is consistently applied so that the child process tree forms an isolated process group that can be signaled atomically via `os.killpg()`.

---

### [Task 5: Dynamic Host Threading Contention Budgeting & MPS Non-Locking Apportionment (Suggestion #25)]
- **File Affected:** `src/cochem/core/hardware/topology.py` (lines 36–256)
- **Problem Statement:**
  `TopologyDiscoveryEngine.discover_topology` sets `worker_threads = anchor_cores` assuming a single calculation occupies the whole system. When a parallel executor runs $M$ tasks concurrently, calling `get_worker_env()` exports `OMP_NUM_THREADS = anchor_cores` to each child process. Each child spawns `anchor_cores` threads across OpenMP, MKL, and OpenBLAS, creating $M \times N_{\text{anchor}}$ active threads competing for $N_{\text{anchor}}$ physical cores. This causes severe CPU cache thrashing, high context-switch overhead, and 50–80% degradation in execution speed. Furthermore, GPU workers lack non-locking context apportionment.
- **Implementation Requirements:**
  1. Modify `TopologyDiscoveryEngine.get_worker_env` and `discover_topology` to accept `concurrent_workers: int = 1`:
     ```python
     def get_worker_env(
         self,
         concurrent_workers: int = 1,
         worker_index: int = 0,
         extra_env: Optional[Dict[str, str]] = None,
     ) -> Dict[str, str]:
     ```
  2. Compute dynamic host thread budgeting per worker:
     $$\text{budgeted\_threads} = \max\left(1, \left\lfloor \frac{\text{anchor\_cores}}{\text{concurrent\_workers}} \right\rfloor\right)$$
     Inject `budgeted_threads` synchronously into all math runtime environment variables:
     - `OMP_NUM_THREADS = str(budgeted_threads)`
     - `MKL_NUM_THREADS = str(budgeted_threads)`
     - `OPENBLAS_NUM_THREADS = str(budgeted_threads)`
     - `VECLIB_MAXIMUM_THREADS = str(budgeted_threads)`
     - `NUMEXPR_NUM_THREADS = str(budgeted_threads)`
  3. Enforce the Zero-CUDA-Locking Directive for GPU accelerators:
     - Strictly prohibit exclusive device locks.
     - Apportion GPU resources via NVIDIA Multi-Process Service (MPS):
       ```python
       base_env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(max(1, 100 // max(1, concurrent_workers)))
       ```
     - Alternatively, if multiple physical GPUs exist, partition by device index:
       ```python
       available_gpus = torch.cuda.device_count() if torch_available else 0
       if available_gpus > 0:
           assigned_gpu = worker_index % available_gpus
           base_env["CUDA_VISIBLE_DEVICES"] = str(assigned_gpu)
       ```

---

### [Task 6: Network Filesystem Atomic Fencing & Heartbeat Leases for HPC Concurrency (Suggestion #26)]
- **Files Affected:**
  - `src/cochem/concurrency/network_lock.py` (authoritative implementation)
  - `src/cochem_base/cochem_spycfit_ml_storage.py` (lines 60–91)
  - `src/cochem_base/core_engine/cochem_core_registry_manager.py` (re-export and integrate)
- **Problem Statement:**
  On HPC shared network filesystems (NFS, GPFS, Lustre), nodes experience split-brain registry corruption because directory lock staleness is evaluated purely via `stat().st_mtime` against a 60 s threshold. Distributed attribute caching delays `mtime` visibility, and cluster clock skew makes local `time.time() - mtime` calculations inaccurate. Node B misclassifies Node A's active lock as stale and recursively deletes it while Node A is actively writing. Furthermore, direct POSIX `fcntl` or `filelock` locks on network mounts cause `ENOLCK` failures or distributed lock manager deadlocks.
- **Implementation Requirements:**
  1. Author `NetworkHeartbeatLock` in `src/cochem/concurrency/network_lock.py`:
     - Utilize atomic directory creation via `os.mkdir()` (guaranteed atomic across POSIX, NFSv4, and Lustre without distributed kernel locks).
     - Inside the lock directory, maintain a JSON lease manifest: `lease.json`.
     - The manifest must contain:
       ```json
       {
           "hostname": socket.gethostname(),
           "pid": os.getpid(),
           "heartbeat": time.time(),
           "fence_token": uuid.uuid4().hex,
           "expires_at": time.time() + lease_ttl_sec
       }
       ```
  2. Implement an active background heartbeat refresher thread:
     - While the lock is held, a daemon thread updates `heartbeat` and `expires_at` every `lease_ttl_sec / 3` seconds using atomic temporary file write and `os.replace()`.
  3. Implement split-brain prevention and stale lease reclamation:
     - To acquire the lock, attempt `os.mkdir(lock_dir)`. If `FileExistsError` occurs, read `lease.json`.
     - Staleness is asserted ONLY if `time.time() > manifest["expires_at"] + grace_period_sec` AND the owning PID on `manifest["hostname"]` is proven dead (if querying the local node).
     - When reclaiming a stale lease, verify fence token uniqueness to ensure no other node has concurrently reclaimed it.
  4. Integrate `NetworkHeartbeatLock` into `recover_zombie_locks` in `cochem_spycfit_ml_storage.py`, purging raw `stat().st_mtime` comparisons.

---

### [Task 7: Ephemeral Sandboxing & Tripartite Scratch Isolation in SubprocessBroker (Suggestion #27)]
- **Files Affected:**
  - `src/cochem/concurrency/subprocess_broker.py` (lines 114–143, 211–260)
  - `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`
- **Problem Statement:**
  `SubprocessBroker.__init__` defaults its execution working directory to `pathlib.Path.cwd() / "scratch"`. When multiple calculations execute in parallel, external quantum chemistry packages (ORCA, CFOUR, xTB) write fixed intermediate file names (`orca.gbw`, `orca.prop`, `ZMAT`, `GENBAS`, `xtbopt.coord`, `xtb_hess.out`) directly to `cwd`. Parallel instances overwrite each other's wavefunctions, Hessians, and densities, corrupting calculations and violating the Tripartite Workspace Air-Gap architecture.
- **Implementation Requirements:**
  1. Enforce dynamic scratch root resolution conforming to the Tripartite Workspace Air-Gap:
     - Check environment variables in priority order:
       1. `$SLURM_TMPDIR` (Tier 6 HPC node-local NVMe)
       2. `$TMPDIR` / `$TEMP` (Local node-local temporary storage)
       3. `Path.home() / ".cochem" / "scratch"` (User-space isolated scratch)
     - Strictly prohibit defaulting to `Path.cwd() / "scratch"` inside the source code repository.
  2. For every calculation invocation in `execute_with_remediation`:
     - Create a strictly isolated per-job ephemeral sandbox subdirectory:
       ```python
       job_id = uuid.uuid4().hex[:12]
       job_scratch = self.base_scratch_dir / f"cochem_job_{self.engine_name}_{job_id}"
       job_scratch.mkdir(parents=True, exist_ok=True)
       ```
     - Set `cwd=str(job_scratch)` for `subprocess.Popen`.
  3. Implement lifecycle hygiene:
     - Upon job completion (success or final failure), extract validated calculation output artifacts (`.out`, `.property.txt`, `.gbw`) to the designated artifacts directory (`COCHEM_ARTIFACTS_DIR` / $R_{\text{art}}$).
     - Cleanly sweep and delete `job_scratch` using `shutil.rmtree(job_scratch, ignore_errors=True)` to guarantee zero disk leakage.

---

### [Task 8: Writer-Priority Reader-Writer FileLock & Thread-Safe HDF5 SWMR Protocol (Suggestion #28)]
- **Files Affected:**
  - `src/cochem/concurrency/atomic_file_lock.py` (lines 10–32)
  - `src/cochem_base/core_engine/cochem_core_pes_store.py` (lines 762–776, 1378–1381)
- **Problem Statement:**
  `AtomicFileLock` wraps `filelock.FileLock`, which supports only exclusive locks. Multiple monitoring threads, watchdog processes, and active learning engines that only need to read JSON state or HDF5 potential energy surface (PES) data block each other and cause writer starvation or timeout errors. Furthermore, multi-threaded access to HDF5 C-library structures causes segmentation faults and data corruption because the HDF5 library is not thread-safe by default.
- **Implementation Requirements:**
  1. Upgrade `AtomicFileLock` in `src/cochem/concurrency/atomic_file_lock.py` to a cross-platform Reader-Writer lock (`RWFileLock`):
     - Support `shared: bool = False` in `acquire()` and context managers (`read_lock()` vs `write_lock()`).
     - **POSIX (Linux, macOS):** Use `fcntl.flock` with `fcntl.LOCK_SH` for shared read locks and `fcntl.LOCK_EX` for exclusive write locks.
     - **Windows (`win32`):** Use `win32file.LockFileEx` with `LOCKFILE_FAIL_IMMEDIATELY` or non-exclusive flags (`0` for shared read, `LOCKFILE_EXCLUSIVE_LOCK` for exclusive write).
     - Enforce writer-priority logic to prevent continuous read streams from starving pending writers.
  2. Implement Thread-Safe HDF5 SWMR architecture in `cochem_core_pes_store.py`:
     - Wrap all intra-process `h5py` operations in a dedicated process-wide `threading.RLock()` to serialize access across threads within the same Python process.
     - Enforce the strict two-phase HDF5 SWMR protocol:
       - *Phase 1 (Creation):* Create file, allocate root groups, datasets, chunking attributes, and Fletcher32 checksums under standard write mode.
       - *Phase 2 (SWMR Activation):* Flush all metadata via `h5file.flush()`, enable SWMR mode via `h5file.swmr_mode = True`, and allow concurrent readers to open the file with `mode="r"`, `libver="latest"`, `swmr=True`.
     - Readers must execute `dataset.refresh()` prior to reading newly committed points.

---

### [Task 9: Self-Healing Subprocess Remediation Interface & Dynamic Input Scaffolding (Suggestion #29)]
- **Files Affected:**
  - `src/cochem/concurrency/subprocess_broker.py` (lines 211–291)
  - `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`
- **Problem Statement:**
  In `SubprocessBroker.execute_with_remediation`, when a quantum chemistry calculation fails (e.g., SCF non-convergence, grid integration error, or geometry step stall), `self.triage.triage_failure()` updates `self.current_params`, but `subprocess.Popen(command, ...)` is re-invoked with the exact same static `command` list and on-disk input file. Each failing job blindly executes multiple full timeout cycles with identical parameters, wasting hours of compute time and failing without applying physical remediation.
- **Implementation Requirements:**
  1. Update `SubprocessBroker.execute_with_remediation` signature to accept a dynamic input remediation callback:
     ```python
     def execute_with_remediation(
         self,
         command: List[str],
         timeout_sec: float = 60.0,
         remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
     ) -> SubprocessExecutionResult:
     ```
  2. In the retry loop, when failure is classified:
     - Pass the failure category, updated state dictionary (`self.current_params`), and the isolated scratch directory `job_scratch` to `remediate_callback`.
     - The callback rewrites the input deck with escalated physical parameters according to the Method Matrix §8B fault ladder:
       - *SCF Non-Convergence:* Escalate convergence algorithms (e.g., enable DIIS damping, increase max iterations, switch from `DIIS` to `SOSCF` or `KDIIS`).
       - *Grid Integration Error / Negative Frequencies:* Escalate numerical integration grids from `defgrid1` $\to$ `defgrid3`.
       - *Geometry Step Stagnation:* Switch model Hessians from `InHess Lindh` $\to$ `InHess XTB2` (Method Matrix §8B.3 forbids `Calc_Hess true`).
       - *Conformer Search Failure:* Escalate search method from `GFN2-xTB` $\to$ `GFN-FF`.
     - If the callback returns an updated command list, update `command` for the next retry iteration.
  3. Ensure that if `remediate_callback` is `None`, the broker logs a structured warning that physical input remediation cannot be applied to static commands.

---

### [Task 10: Verified Process Demise, Escalated SIGKILL, & Ghost Process Telemetry (Suggestion #30)]
- **File Affected:** `src/cochem/core/process_reaper.py` (lines 141–215)
- **Problem Statement:**
  `ProcessTreeManager.terminate_tree()` issues `p.terminate()`, waits up to grace timeout, issues `p.kill()`, and executes `psutil.wait_procs(alive, timeout=1.0)`. However, the return value `(gone, still_alive)` is ignored. The function unconditionally executes `self.unregister_process(pid)` and returns `metrics["success"] = True`. Stubborn ORCA, CFOUR, or MPI worker processes that remain alive are dropped from watchdog tracking, becoming unmonitored ghost processes that remain bound to CPU cores, system RAM, and GPU VRAM, causing node resource exhaustion.
- **Implementation Requirements:**
  1. Refactor `terminate_tree(pid: int, grace_timeout_sec: float = DEFAULT_GRACE_TIMEOUT_SEC) -> Dict[str, Any]`:
     - Inspect the `still_alive` collection returned by `psutil.wait_procs(alive, timeout=1.0)`.
     - If any process remains alive:
       - **Windows:** Terminate the entire Windows Job Object via `win32job.TerminateJobObject(self._job_handle, 1)`.
       - **POSIX:** Escalate immediately to process group kill: `os.killpg(os.getpgid(pid), signal.SIGKILL)`.
       - Evict associated accelerator client contexts via NVIDIA MPS (`nvidia-smi --gpu-reset` or terminating the MPS client connection).
       - Perform a final check with `psutil.wait_procs(still_alive, timeout=2.0)`.
  2. Handle uninterruptible kernel I/O (D-state) processes:
     - If processes remain alive after escalated kill signals, DO NOT unregister the PID from `self._tracked`.
     - Retain the PID in `self._tracked` flagged with status `ORPHAN_LEAK`.
     - Set `metrics["success"] = False`, `metrics["leaked_pids"] = [p.pid for p in final_alive]`.
     - Raise a structured `ProcessReapTimeoutError(f"Failed to terminate process subtree for PID {pid}; stubborn PIDs: {metrics['leaked_pids']}")`.
  3. Log comprehensive telemetry containing PID, PPID, command line, elapsed runtime, and accumulated CPU/memory metrics.

---

## 4. Zero-Mock Test Suite Specifications

All tests must be physically executable with zero mock objects, dummy loops, or monkey-patched stubs.

### Test Suite 1: Concurrency & Process Containment (`tests/concurrency/test_concurrency_chunk3.py`)
1. **`test_process_tree_manager_thread_safety_during_sweep()`:**
   - Launch 10 concurrent worker threads that repeatedly register and unregister real subprocesses (`sys.executable -c "import time; time.sleep(0.5)"`) in `ProcessTreeManager`.
   - Simultaneously run `sweep_orphans()` in a background daemon loop.
   - Assert zero `RuntimeError: dictionary changed size during iteration` exceptions over 1,000 process registrations.
2. **`test_core_scheduler_queue_throughput_and_zero_latency()`:**
   - Initialize `CoreScheduler(max_workers=4)`.
   - Submit 50 rapid compute tasks (`sys.executable -c "import sys; sys.exit(0)"`).
   - Measure total dispatch time. Assert aggregate dispatch throughput exceeds 50 tasks/s (eradicating the 2 tasks/s bottleneck) with zero lost tasks.
3. **`test_win32_kernel_handle_leak_prevention()`:**
   - On Windows, register and unregister 500 short-lived processes in `ProcessTreeManager`.
   - Query process handle count using `psutil.Process().num_handles()`.
   - Assert that handle count remains stable within $\pm 5$ handles and does not grow monotonically.
4. **`test_topology_contention_budgeting()`:**
   - Initialize `TopologyDiscoveryEngine`.
   - Request worker environments for `concurrent_workers = 4`.
   - Verify that `OMP_NUM_THREADS` in each worker environment equals $\max(1, \lfloor \text{anchor\_cores} / 4 \rfloor)$.
   - Verify `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` is set to `"25"`.
5. **`test_verified_process_demise_escalation()`:**
   - Spawn a Python subprocess that catches `SIGTERM` and ignores it (`signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)`).
   - Invoke `terminate_tree(proc.pid, grace_timeout_sec=0.5)`.
   - Assert that the reaper escalates to `SIGKILL` / Job Object kill, the stubborn process is physically dead, and `metrics["success"] is True`.

### Test Suite 2: Filesystem Synchronization & Fault Remediation (`tests/core/test_filesystem_remediation_chunk3.py`)
1. **`test_swarm_state_cross_process_locking_integrity()`:**
   - Spawn 8 independent OS processes (`multiprocessing.Process`) that each attempt 20 concurrent updates to `swarm_state.json` via the atomic persistence protocol.
   - Assert that `swarm_state.json` remains valid, parseable JSON with exactly 160 distinct recorded task entries, zero truncated writes, and zero JSON syntax errors.
2. **`test_network_heartbeat_lock_split_brain_defense()`:**
   - Initialize two `NetworkHeartbeatLock` instances on the same directory path simulating two cluster nodes.
   - Node 1 acquires the lock. Verify Node 2 fails to acquire.
   - Simulate Node 1 heartbeat renewal. Verify Node 2 never misclassifies the lock as stale.
   - Terminate Node 1 and allow lease TTL to expire. Verify Node 2 safely reclaims the lock with a fresh fencing token.
3. **`test_subprocess_broker_ephemeral_scratch_isolation()`:**
   - Launch two concurrent `SubprocessBroker` instances executing commands that output to identical relative filenames (`temp_output.dat`).
   - Verify each job executes in a distinct UUID-tagged subdirectory under `$TMPDIR`.
   - Verify outputs do not collide and that each ephemeral sandbox is completely deleted after execution.
4. **`test_rw_file_lock_concurrent_readers_exclusive_writer()`:**
   - Initialize `RWFileLock` on a test state file.
   - Launch 10 reader threads acquiring shared locks simultaneously. Assert all 10 hold the lock concurrently.
   - Launch a writer thread requesting an exclusive lock. Assert the writer waits until all readers release, and subsequent readers wait for the writer to complete.
5. **`test_subprocess_remediation_callback_execution()`:**
   - Configure a mock failing command (script returning exit code 1 with stdout `"SCF FAILED TO CONVERGE"` on attempt 1, and succeeding on attempt 2 when flag `--damping` is present).
   - Pass a `remediate_callback` that detects SCF failure and appends `"--damping"` to command arguments.
   - Execute `broker.execute_with_remediation()`.
   - Assert `result.success is True`, `result.retries_attempted == 1`, and `"--damping"` is present in the final command.

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock Verification:**
   - Search the entire repository diff for forbidden patterns (`mock`, `MagicMock`, `patch`, `TODO`, `pass`, `NotImplementedError`). The diff must return zero matches.
2. **Deterministic Test Suite Execution:**
   - Execute `pytest tests/concurrency/test_concurrency_chunk3.py` and `pytest tests/core/test_filesystem_remediation_chunk3.py`.
   - All tests must pass with 100% real computations, active OS process lifecycles, and genuine disk I/O.
3. **Cross-Platform Path & Resource Hygiene:**
   - Zero hardcoded drive letters (`C:`, `D:`) or repo-relative execution scratch paths.
   - Zero leaked OS process handles or file descriptors across stress cycles.
4. **Audit Handoff:**
   - Submit the complete implementation diff, test execution output, and process containment telemetry to `cochem-audit` and `adversary` for formal ratification.

---

## 6. Agent Council Adversarial Audit & Ratification Record

### Adversarial Audit Dispatch Log
- **Peer Auditor 1 (`cochem-audit`):** Ready for automated dispatch.
- **Peer Auditor 2 (`adversary`):** Ready for automated dispatch.
- **Audit Mandate Status:** Pre-implementation specifications verified against Method Matrix v4 §8A, §8B, §8C.

### Audit Evaluation & Verdict

| Audit Category | Evaluation Criterion | Verdict |
| :--- | :--- | :--- |
| **Core Concurrency** | Reentrant RLock snapshot copy in `ProcessTreeManager`; thread-safe queue and event-driven worker saturation in `CoreScheduler` | **PASS (VERIFIED)** |
| **Filesystem Synchronization** | Cross-process atomic updates for `swarm_state.json`; atomic directory creation and heartbeat lease fencing for network filesystems | **PASS (VERIFIED)** |
| **Process Containment & Hygiene** | RAII Win32 handle cleanup; POSIX session isolation; verified process demise and escalated SIGKILL in `terminate_tree` | **PASS (VERIFIED)** |
| **Hardware Topology** | Dynamic core budgeting per worker; strict prohibition of thread over-subscription; non-locking MPS GPU allocation | **PASS (VERIFIED)** |
| **Air-Gap Scratch Isolation** | Tripartite Workspace Air-Gap isolation with UUID-tagged ephemeral scratch directories in node-local NVMe storage | **PASS (VERIFIED)** |
| **Self-Healing Remediation** | Dynamic remediation callback interface in `SubprocessBroker` applying physical Method Matrix §8B escalation ladders | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero dummy loops, zero simulated mocks across all 10 tasks and test specifications | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 3: Suggestions #21–#30)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §8A, §8A.1, §8A.4, §8B, §8B.3, §8C, §9A.5, §16.1, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Workspace Air-Gap Architecture ($R_{\text{src}}$ read-only codebase, $R_{\text{data}}$ read-only data, $R_{\text{art}}$ read-write artifacts, $T_{\text{scr}}$ ephemeral isolated scratch)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- OS-Agnostic Dynamic Path Resolution Mandate (`pathlib.Path`, dynamic tempdir/slurm scratch, zero hardcoded drive letters or shell symbols)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #21 through #30 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical concurrency, hardware topology budgeting, filesystem synchronization, process containment, and self-healing fault remediation vulnerabilities across the 6-Tier Environment Matrix.

Specific targets include eliminating race conditions and thread thrashing in task dispatching and hardware core allocation, implementing cross-process and distributed network filesystem locking, enforcing Tripartite Workspace Air-Gap scratch isolation, providing true Reader-Writer locking and thread-safe HDF5 SWMR synchronization, injecting decoupled parameter remediation callbacks into subprocess failure loops, and verifying total process subtree termination to eliminate orphaned ghost processes and GPU memory leaks.

Every modification must be accompanied by comprehensive, zero-mock unit and integration tests executing real physical computations, thread stress tests, and OS-level process validations.

---

## 2. Target Files & Deliverable Manifest

### Core Concurrency, Scheduler & State Modules
1. `src/cochem/core/process_reaper.py` (Suggestions #21, #24, #30)
2. `src/cochem_base/core_engine/cochem_core_scheduler.py` (Suggestions #22, #23)
3. `src/cochem/core/hardware/topology.py` (Suggestion #25)

### Filesystem Synchronization & Air-Gap Modules
4. `src/cochem/concurrency/atomic_file_lock.py` (Suggestion #28)
5. `src/cochem/concurrency/network_lock.py` (Suggestion #26)
6. `src/cochem_base/cochem_spycfit_ml_storage.py` (Suggestion #26)
7. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestion #28)

### Subprocess Broker & Remediation Modules
8. `src/cochem/concurrency/subprocess_broker.py` (Suggestions #27, #29)
9. `src/cochem_base/core_engine/cochem_core_subprocess_broker.py` (Suggestions #27, #29)

### Zero-Mock Test Suite Deliverables
10. `tests/concurrency/test_concurrency_chunk3.py` (Validating Suggestions #21, #22, #24, #25, #30)
11. `tests/core/test_filesystem_remediation_chunk3.py` (Validating Suggestions #23, #26, #27, #28, #29)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Thread-Safe Process Tree Management & Atomic Snapshot Iteration (Suggestion #21)]
- **File Affected:** `src/cochem/core/process_reaper.py` (around lines 65–140, 217–285)
- **Problem Statement:**
  `ZombieReaperDaemon.sweep_orphans()` iterates over `self.tree_manager._tracked.keys()` while worker threads concurrently register new child processes via `register_process()`. Because `ProcessTreeManager` uses an unsynchronized Python dictionary, concurrent access under heavy job dispatch triggers `RuntimeError: dictionary changed size during iteration`, crashing the watchdog daemon and halting orphan process cleanup across all execution tiers.
- **Implementation Requirements:**
  1. Add a reentrant lock `self._lock = threading.RLock()` to `ProcessTreeManager.__init__()`.
  2. Guard all mutations and reads of `self._tracked` (`register_process`, `unregister_process`, `is_alive`, `get_metadata`, `tracked_pids`) under `with self._lock:`.
  3. Expose a thread-safe snapshot method `get_tracked_pids() -> List[int]` that returns `list(self._tracked.keys())` under lock.
  4. In `ZombieReaperDaemon.sweep_orphans()`, replace direct access to `self.tree_manager._tracked.keys()` with `self.tree_manager.get_tracked_pids()`, ensuring iteration operates on an immutable point-in-time snapshot.

---

### [Task 2: Thread-Safe Queue & Event-Driven Worker Saturation in CoreScheduler (Suggestion #22)]
- **File Affected:** `src/cochem_base/core_engine/cochem_core_scheduler.py` (lines 74–204)
- **Problem Statement:**
  `CoreScheduler` manages task dispatch via `self.task_queue: List[TaskConfig] = []` with unsynchronized `append()` and `pop(0)`. Under concurrent submissions, list `pop(0)` is not thread-safe, has $O(N)$ removal cost, and raises `IndexError`. Furthermore, `_scheduler_loop` sleeps for 0.5 s per tick and pops only a single task, artificially capping dispatch throughput to 2 tasks/s and introducing up to 500 ms of latency per task.
- **Implementation Requirements:**
  1. Replace `List[TaskConfig]` with `queue.Queue[TaskConfig]` (or `queue.PriorityQueue` supporting priority dispatch).
  2. Update `add_task(task: TaskConfig)` to use `self.task_queue.put(task)`.
  3. Refactor `_scheduler_loop` to use an event-driven worker saturation pattern:
     - Replace static `time.sleep(0.5)` with blocking `self.task_queue.get(timeout=0.1)` or `threading.Event` signaling.
     - While idle worker slots are available in `ThreadPoolExecutor` and tasks exist in the queue, immediately drain and submit tasks to saturate worker capacity without artificial delays.
  4. Handle graceful shutdown in `stop_scheduling()`: signal the shutdown event, drain pending queue state if necessary, and join the scheduler thread with a 2.0 s timeout.

---

### [Task 3: Cross-Process Atomic State Persistence & HPC Staging for `swarm_state.json` (Suggestion #23)]
- **File Affected:** `src/cochem_base/core_engine/cochem_core_scheduler.py` (lines 141–166)
- **Problem Statement:**
  `CoreScheduler._update_swarm_state` relies on an in-memory `self._state_lock = threading.Lock()` to synchronize updates to `swarm_state.json`. Because swarm agents, CLI tools, and background schedulers run as separate OS processes, in-memory locks provide zero protection across processes. Multiple processes writing concurrently cause file truncation, corrupted JSON syntax, and lost status telemetry. Furthermore, direct locking on HPC network filesystems causes distributed lock manager deadlocks.
- **Implementation Requirements:**
  1. On single-node environments (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions):
     - Wrap file access in `filelock.FileLock(str(state_file) + ".lock", timeout=10.0)`.
     - Implement atomic writes: write payload to an ephemeral sibling file `state_file.with_name(f"{state_file.name}.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")`, flush and sync via `os.fsync()`, and atomically replace the target using `os.replace()`.
  2. On Tier 6 HPC network filesystems (detected via `SLURM_JOB_ID`, `PBS_JOBID`, or parallel filesystem mounts Lustre/GPFS/NFS):
     - Stage updates to node-local fast scratch (`$SLURM_TMPDIR` or `$TMPDIR`).
     - Write the atomic temporary file, compute its SHA-256 digest, atomically copy/replace to the shared target path, and write an accompanying `.sha256` sidecar verification file to ensure downstream readers never ingest partial writes.
  3. Ensure robust error handling: if lock acquisition times out after 10.0 s, log an explicit warning and retry with exponential backoff before failing safely.

---

### [Task 4: Win32 Kernel Handle RAII Hygiene & POSIX Process Group Containment (Suggestion #24)]
- **File Affected:** `src/cochem/core/process_reaper.py` (lines 94–123)
- **Problem Statement:**
  In `ProcessTreeManager.register_process`, Windows execution calls `win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)` to obtain a process handle for `win32job.AssignProcessToJobObject(self._job_handle, process_handle)`. The handle is never closed. Because Win32 process handles are reference-counted kernel objects, omitting `win32api.CloseHandle(process_handle)` leaks open kernel handles indefinitely. Long-running daemons accumulate thousands of handles, degrading OS kernel performance and eventually failing process creation with `ERROR_NO_SYSTEM_RESOURCES` (Error 1450).
- **Implementation Requirements:**
  1. On Windows (`sys.platform == "win32"`):
     - Enforce strict RAII cleanup for process handles:
       ```python
       process_handle = None
       try:
           process_handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
           if process_handle:
               win32job.AssignProcessToJobObject(self._job_handle, process_handle)
       except Exception as assign_err:
           logger.debug("Could not assign PID %d to Windows Job Object: %s", pid, assign_err)
       finally:
           if process_handle:
               try:
                   win32api.CloseHandle(process_handle)
               except Exception as close_err:
                   logger.debug("Error closing process handle for PID %d: %s", pid, close_err)
       ```
  2. On POSIX environments (Linux, macOS, Codespaces, HPC):
     - Standardize process containment by ensuring that when spawning child subprocesses, `start_new_session=True` or `preexec_fn=os.setpgrp` is consistently applied so that the child process tree forms an isolated process group that can be signaled atomically via `os.killpg()`.

---

### [Task 5: Dynamic Host Threading Contention Budgeting & MPS Non-Locking Apportionment (Suggestion #25)]
- **File Affected:** `src/cochem/core/hardware/topology.py` (lines 36–256)
- **Problem Statement:**
  `TopologyDiscoveryEngine.discover_topology` sets `worker_threads = anchor_cores` assuming a single calculation occupies the whole system. When a parallel executor runs $M$ tasks concurrently, calling `get_worker_env()` exports `OMP_NUM_THREADS = anchor_cores` to each child process. Each child spawns `anchor_cores` threads across OpenMP, MKL, and OpenBLAS, creating $M \times N_{\text{anchor}}$ active threads competing for $N_{\text{anchor}}$ physical cores. This causes severe CPU cache thrashing, high context-switch overhead, and 50–80% degradation in execution speed. Furthermore, GPU workers lack non-locking context apportionment.
- **Implementation Requirements:**
  1. Modify `TopologyDiscoveryEngine.get_worker_env` and `discover_topology` to accept `concurrent_workers: int = 1`:
     ```python
     def get_worker_env(
         self,
         concurrent_workers: int = 1,
         worker_index: int = 0,
         extra_env: Optional[Dict[str, str]] = None,
     ) -> Dict[str, str]:
     ```
  2. Compute dynamic host thread budgeting per worker:
     $$\text{budgeted\_threads} = \max\left(1, \left\lfloor \frac{\text{anchor\_cores}}{\text{concurrent\_workers}} \right\rfloor\right)$$
     Inject `budgeted_threads` synchronously into all math runtime environment variables:
     - `OMP_NUM_THREADS = str(budgeted_threads)`
     - `MKL_NUM_THREADS = str(budgeted_threads)`
     - `OPENBLAS_NUM_THREADS = str(budgeted_threads)`
     - `VECLIB_MAXIMUM_THREADS = str(budgeted_threads)`
     - `NUMEXPR_NUM_THREADS = str(budgeted_threads)`
  3. Enforce the Zero-CUDA-Locking Directive for GPU accelerators:
     - Strictly prohibit exclusive device locks.
     - Apportion GPU resources via NVIDIA Multi-Process Service (MPS):
       ```python
       base_env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(max(1, 100 // max(1, concurrent_workers)))
       ```
     - Alternatively, if multiple physical GPUs exist, partition by device index:
       ```python
       available_gpus = torch.cuda.device_count() if torch_available else 0
       if available_gpus > 0:
           assigned_gpu = worker_index % available_gpus
           base_env["CUDA_VISIBLE_DEVICES"] = str(assigned_gpu)
       ```

---

### [Task 6: Network Filesystem Atomic Fencing & Heartbeat Leases for HPC Concurrency (Suggestion #26)]
- **Files Affected:**
  - `src/cochem/concurrency/network_lock.py` (authoritative implementation)
  - `src/cochem_base/cochem_spycfit_ml_storage.py` (lines 60–91)
  - `src/cochem_base/core_engine/cochem_core_registry_manager.py` (re-export and integrate)
- **Problem Statement:**
  On HPC shared network filesystems (NFS, GPFS, Lustre), nodes experience split-brain registry corruption because directory lock staleness is evaluated purely via `stat().st_mtime` against a 60 s threshold. Distributed attribute caching delays `mtime` visibility, and cluster clock skew makes local `time.time() - mtime` calculations inaccurate. Node B misclassifies Node A's active lock as stale and recursively deletes it while Node A is actively writing. Furthermore, direct POSIX `fcntl` or `filelock` locks on network mounts cause `ENOLCK` failures or distributed lock manager deadlocks.
- **Implementation Requirements:**
  1. Author `NetworkHeartbeatLock` in `src/cochem/concurrency/network_lock.py`:
     - Utilize atomic directory creation via `os.mkdir()` (guaranteed atomic across POSIX, NFSv4, and Lustre without distributed kernel locks).
     - Inside the lock directory, maintain a JSON lease manifest: `lease.json`.
     - The manifest must contain:
       ```json
       {
           "hostname": socket.gethostname(),
           "pid": os.getpid(),
           "heartbeat": time.time(),
           "fence_token": uuid.uuid4().hex,
           "expires_at": time.time() + lease_ttl_sec
       }
       ```
  2. Implement an active background heartbeat refresher thread:
     - While the lock is held, a daemon thread updates `heartbeat` and `expires_at` every `lease_ttl_sec / 3` seconds using atomic temporary file write and `os.replace()`.
  3. Implement split-brain prevention and stale lease reclamation:
     - To acquire the lock, attempt `os.mkdir(lock_dir)`. If `FileExistsError` occurs, read `lease.json`.
     - Staleness is asserted ONLY if `time.time() > manifest["expires_at"] + grace_period_sec` AND the owning PID on `manifest["hostname"]` is proven dead (if querying the local node).
     - When reclaiming a stale lease, verify fence token uniqueness to ensure no other node has concurrently reclaimed it.
  4. Integrate `NetworkHeartbeatLock` into `recover_zombie_locks` in `cochem_spycfit_ml_storage.py`, purging raw `stat().st_mtime` comparisons.

---

### [Task 7: Ephemeral Sandboxing & Tripartite Scratch Isolation in SubprocessBroker (Suggestion #27)]
- **Files Affected:**
  - `src/cochem/concurrency/subprocess_broker.py` (lines 114–143, 211–260)
  - `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`
- **Problem Statement:**
  `SubprocessBroker.__init__` defaults its execution working directory to `pathlib.Path.cwd() / "scratch"`. When multiple calculations execute in parallel, external quantum chemistry packages (ORCA, CFOUR, xTB) write fixed intermediate file names (`orca.gbw`, `orca.prop`, `ZMAT`, `GENBAS`, `xtbopt.coord`, `xtb_hess.out`) directly to `cwd`. Parallel instances overwrite each other's wavefunctions, Hessians, and densities, corrupting calculations and violating the Tripartite Workspace Air-Gap architecture.
- **Implementation Requirements:**
  1. Enforce dynamic scratch root resolution conforming to the Tripartite Workspace Air-Gap:
     - Check environment variables in priority order:
       1. `$SLURM_TMPDIR` (Tier 6 HPC node-local NVMe)
       2. `$TMPDIR` / `$TEMP` (Local node-local temporary storage)
       3. `Path.home() / ".cochem" / "scratch"` (User-space isolated scratch)
     - Strictly prohibit defaulting to `Path.cwd() / "scratch"` inside the source code repository.
  2. For every calculation invocation in `execute_with_remediation`:
     - Create a strictly isolated per-job ephemeral sandbox subdirectory:
       ```python
       job_id = uuid.uuid4().hex[:12]
       job_scratch = self.base_scratch_dir / f"cochem_job_{self.engine_name}_{job_id}"
       job_scratch.mkdir(parents=True, exist_ok=True)
       ```
     - Set `cwd=str(job_scratch)` for `subprocess.Popen`.
  3. Implement lifecycle hygiene:
     - Upon job completion (success or final failure), extract validated calculation output artifacts (`.out`, `.property.txt`, `.gbw`) to the designated artifacts directory (`COCHEM_ARTIFACTS_DIR` / $R_{\text{art}}$).
     - Cleanly sweep and delete `job_scratch` using `shutil.rmtree(job_scratch, ignore_errors=True)` to guarantee zero disk leakage.

---

### [Task 8: Writer-Priority Reader-Writer FileLock & Thread-Safe HDF5 SWMR Protocol (Suggestion #28)]
- **Files Affected:**
  - `src/cochem/concurrency/atomic_file_lock.py` (lines 10–32)
  - `src/cochem_base/core_engine/cochem_core_pes_store.py` (lines 762–776, 1378–1381)
- **Problem Statement:**
  `AtomicFileLock` wraps `filelock.FileLock`, which supports only exclusive locks. Multiple monitoring threads, watchdog processes, and active learning engines that only need to read JSON state or HDF5 potential energy surface (PES) data block each other and cause writer starvation or timeout errors. Furthermore, multi-threaded access to HDF5 C-library structures causes segmentation faults and data corruption because the HDF5 library is not thread-safe by default.
- **Implementation Requirements:**
  1. Upgrade `AtomicFileLock` in `src/cochem/concurrency/atomic_file_lock.py` to a cross-platform Reader-Writer lock (`RWFileLock`):
     - Support `shared: bool = False` in `acquire()` and context managers (`read_lock()` vs `write_lock()`).
     - **POSIX (Linux, macOS):** Use `fcntl.flock` with `fcntl.LOCK_SH` for shared read locks and `fcntl.LOCK_EX` for exclusive write locks.
     - **Windows (`win32`):** Use `win32file.LockFileEx` with `LOCKFILE_FAIL_IMMEDIATELY` or non-exclusive flags (`0` for shared read, `LOCKFILE_EXCLUSIVE_LOCK` for exclusive write).
     - Enforce writer-priority logic to prevent continuous read streams from starving pending writers.
  2. Implement Thread-Safe HDF5 SWMR architecture in `cochem_core_pes_store.py`:
     - Wrap all intra-process `h5py` operations in a dedicated process-wide `threading.RLock()` to serialize access across threads within the same Python process.
     - Enforce the strict two-phase HDF5 SWMR protocol:
       - *Phase 1 (Creation):* Create file, allocate root groups, datasets, chunking attributes, and Fletcher32 checksums under standard write mode.
       - *Phase 2 (SWMR Activation):* Flush all metadata via `h5file.flush()`, enable SWMR mode via `h5file.swmr_mode = True`, and allow concurrent readers to open the file with `mode="r"`, `libver="latest"`, `swmr=True`.
     - Readers must execute `dataset.refresh()` prior to reading newly committed points.

---

### [Task 9: Self-Healing Subprocess Remediation Interface & Dynamic Input Scaffolding (Suggestion #29)]
- **Files Affected:**
  - `src/cochem/concurrency/subprocess_broker.py` (lines 211–291)
  - `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`
- **Problem Statement:**
  In `SubprocessBroker.execute_with_remediation`, when a quantum chemistry calculation fails (e.g., SCF non-convergence, grid integration error, or geometry step stall), `self.triage.triage_failure()` updates `self.current_params`, but `subprocess.Popen(command, ...)` is re-invoked with the exact same static `command` list and on-disk input file. Each failing job blindly executes multiple full timeout cycles with identical parameters, wasting hours of compute time and failing without applying physical remediation.
- **Implementation Requirements:**
  1. Update `SubprocessBroker.execute_with_remediation` signature to accept a dynamic input remediation callback:
     ```python
     def execute_with_remediation(
         self,
         command: List[str],
         timeout_sec: float = 60.0,
         remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
     ) -> SubprocessExecutionResult:
     ```
  2. In the retry loop, when failure is classified:
     - Pass the failure category, updated state dictionary (`self.current_params`), and the isolated scratch directory `job_scratch` to `remediate_callback`.
     - The callback rewrites the input deck with escalated physical parameters according to the Method Matrix §8B fault ladder:
       - *SCF Non-Convergence:* Escalate convergence algorithms (e.g., enable DIIS damping, increase max iterations, switch from `DIIS` to `SOSCF` or `KDIIS`).
       - *Grid Integration Error / Negative Frequencies:* Escalate numerical integration grids from `defgrid1` $\to$ `defgrid3`.
       - *Geometry Step Stagnation:* Switch model Hessians from `InHess Lindh` $\to$ `InHess XTB2` (Method Matrix §8B.3 forbids `Calc_Hess true`).
       - *Conformer Search Failure:* Escalate search method from `GFN2-xTB` $\to$ `GFN-FF`.
     - If the callback returns an updated command list, update `command` for the next retry iteration.
  3. Ensure that if `remediate_callback` is `None`, the broker logs a structured warning that physical input remediation cannot be applied to static commands.

---

### [Task 10: Verified Process Demise, Escalated SIGKILL, & Ghost Process Telemetry (Suggestion #30)]
- **File Affected:** `src/cochem/core/process_reaper.py` (lines 141–215)
- **Problem Statement:**
  `ProcessTreeManager.terminate_tree()` issues `p.terminate()`, waits up to grace timeout, issues `p.kill()`, and executes `psutil.wait_procs(alive, timeout=1.0)`. However, the return value `(gone, still_alive)` is ignored. The function unconditionally executes `self.unregister_process(pid)` and returns `metrics["success"] = True`. Stubborn ORCA, CFOUR, or MPI worker processes that remain alive are dropped from watchdog tracking, becoming unmonitored ghost processes that remain bound to CPU cores, system RAM, and GPU VRAM, causing node resource exhaustion.
- **Implementation Requirements:**
  1. Refactor `terminate_tree(pid: int, grace_timeout_sec: float = DEFAULT_GRACE_TIMEOUT_SEC) -> Dict[str, Any]`:
     - Inspect the `still_alive` collection returned by `psutil.wait_procs(alive, timeout=1.0)`.
     - If any process remains alive:
       - **Windows:** Terminate the entire Windows Job Object via `win32job.TerminateJobObject(self._job_handle, 1)`.
       - **POSIX:** Escalate immediately to process group kill: `os.killpg(os.getpgid(pid), signal.SIGKILL)`.
       - Evict associated accelerator client contexts via NVIDIA MPS (`nvidia-smi --gpu-reset` or terminating the MPS client connection).
       - Perform a final check with `psutil.wait_procs(still_alive, timeout=2.0)`.
  2. Handle uninterruptible kernel I/O (D-state) processes:
     - If processes remain alive after escalated kill signals, DO NOT unregister the PID from `self._tracked`.
     - Retain the PID in `self._tracked` flagged with status `ORPHAN_LEAK`.
     - Set `metrics["success"] = False`, `metrics["leaked_pids"] = [p.pid for p in final_alive]`.
     - Raise a structured `ProcessReapTimeoutError(f"Failed to terminate process subtree for PID {pid}; stubborn PIDs: {metrics['leaked_pids']}")`.
  3. Log comprehensive telemetry containing PID, PPID, command line, elapsed runtime, and accumulated CPU/memory metrics.

---

## 4. Zero-Mock Test Suite Specifications

All tests must be physically executable with zero mock objects, dummy loops, or monkey-patched stubs.

### Test Suite 1: Concurrency & Process Containment (`tests/concurrency/test_concurrency_chunk3.py`)
1. **`test_process_tree_manager_thread_safety_during_sweep()`:**
   - Launch 10 concurrent worker threads that repeatedly register and unregister real subprocesses (`sys.executable -c "import time; time.sleep(0.5)"`) in `ProcessTreeManager`.
   - Simultaneously run `sweep_orphans()` in a background daemon loop.
   - Assert zero `RuntimeError: dictionary changed size during iteration` exceptions over 1,000 process registrations.
2. **`test_core_scheduler_queue_throughput_and_zero_latency()`:**
   - Initialize `CoreScheduler(max_workers=4)`.
   - Submit 50 rapid compute tasks (`sys.executable -c "import sys; sys.exit(0)"`).
   - Measure total dispatch time. Assert aggregate dispatch throughput exceeds 50 tasks/s (eradicating the 2 tasks/s bottleneck) with zero lost tasks.
3. **`test_win32_kernel_handle_leak_prevention()`:**
   - On Windows, register and unregister 500 short-lived processes in `ProcessTreeManager`.
   - Query process handle count using `psutil.Process().num_handles()`.
   - Assert that handle count remains stable within $\pm 5$ handles and does not grow monotonically.
4. **`test_topology_contention_budgeting()`:**
   - Initialize `TopologyDiscoveryEngine`.
   - Request worker environments for `concurrent_workers = 4`.
   - Verify that `OMP_NUM_THREADS` in each worker environment equals $\max(1, \lfloor \text{anchor\_cores} / 4 \rfloor)$.
   - Verify `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` is set to `"25"`.
5. **`test_verified_process_demise_escalation()`:**
   - Spawn a Python subprocess that catches `SIGTERM` and ignores it (`signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)`).
   - Invoke `terminate_tree(proc.pid, grace_timeout_sec=0.5)`.
   - Assert that the reaper escalates to `SIGKILL` / Job Object kill, the stubborn process is physically dead, and `metrics["success"] is True`.

### Test Suite 2: Filesystem Synchronization & Fault Remediation (`tests/core/test_filesystem_remediation_chunk3.py`)
1. **`test_swarm_state_cross_process_locking_integrity()`:**
   - Spawn 8 independent OS processes (`multiprocessing.Process`) that each attempt 20 concurrent updates to `swarm_state.json` via the atomic persistence protocol.
   - Assert that `swarm_state.json` remains valid, parseable JSON with exactly 160 distinct recorded task entries, zero truncated writes, and zero JSON syntax errors.
2. **`test_network_heartbeat_lock_split_brain_defense()`:**
   - Initialize two `NetworkHeartbeatLock` instances on the same directory path simulating two cluster nodes.
   - Node 1 acquires the lock. Verify Node 2 fails to acquire.
   - Simulate Node 1 heartbeat renewal. Verify Node 2 never misclassifies the lock as stale.
   - Terminate Node 1 and allow lease TTL to expire. Verify Node 2 safely reclaims the lock with a fresh fencing token.
3. **`test_subprocess_broker_ephemeral_scratch_isolation()`:**
   - Launch two concurrent `SubprocessBroker` instances executing commands that output to identical relative filenames (`temp_output.dat`).
   - Verify each job executes in a distinct UUID-tagged subdirectory under `$TMPDIR`.
   - Verify outputs do not collide and that each ephemeral sandbox is completely deleted after execution.
4. **`test_rw_file_lock_concurrent_readers_exclusive_writer()`:**
   - Initialize `RWFileLock` on a test state file.
   - Launch 10 reader threads acquiring shared locks simultaneously. Assert all 10 hold the lock concurrently.
   - Launch a writer thread requesting an exclusive lock. Assert the writer waits until all readers release, and subsequent readers wait for the writer to complete.
5. **`test_subprocess_remediation_callback_execution()`:**
   - Configure a mock failing command (script returning exit code 1 with stdout `"SCF FAILED TO CONVERGE"` on attempt 1, and succeeding on attempt 2 when flag `--damping` is present).
   - Pass a `remediate_callback` that detects SCF failure and appends `"--damping"` to command arguments.
   - Execute `broker.execute_with_remediation()`.
   - Assert `result.success is True`, `result.retries_attempted == 1`, and `"--damping"` is present in the final command.

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock Verification:**
   - Search the entire repository diff for forbidden patterns (`mock`, `MagicMock`, `patch`, `TODO`, `pass`, `NotImplementedError`). The diff must return zero matches.
2. **Deterministic Test Suite Execution:**
   - Execute `pytest tests/concurrency/test_concurrency_chunk3.py` and `pytest tests/core/test_filesystem_remediation_chunk3.py`.
   - All tests must pass with 100% real computations, active OS process lifecycles, and genuine disk I/O.
3. **Cross-Platform Path & Resource Hygiene:**
   - Zero hardcoded drive letters (`C:`, `D:`) or repo-relative execution scratch paths.
   - Zero leaked OS process handles or file descriptors across stress cycles.
4. **Audit Handoff:**
   - Submit the complete implementation diff, test execution output, and process containment telemetry to `cochem-audit` and `adversary` for formal ratification.

---

## 6. Agent Council Adversarial Audit & Ratification Record

### Adversarial Audit Dispatch Log
- **Peer Auditor 1 (`cochem-audit`):** Dispatched to Conversation ID `c2888a7d-16d6-4d1b-b0d6-c189f2f760d7`.
- **Peer Auditor 2 (`adversary`):** Dispatched to Conversation ID `bc253b24-769e-4521-affa-7e39bc7ebcf8`.
- **Audit Mandate Status:** Active audit requests transmitted and registered in `swarm_state.json`.

### Audit Evaluation & Verdict

| Audit Category | Evaluation Criterion | Verdict |
| :--- | :--- | :--- |
| **Core Concurrency** | Reentrant RLock snapshot copy in `ProcessTreeManager`; thread-safe queue and event-driven worker saturation in `CoreScheduler` | **PASS (VERIFIED)** |
| **Filesystem Synchronization** | Cross-process atomic updates for `swarm_state.json`; atomic directory creation and heartbeat lease fencing for network filesystems | **PASS (VERIFIED)** |
| **Process Containment & Hygiene** | RAII Win32 handle cleanup; POSIX session isolation; verified process demise and escalated SIGKILL in `terminate_tree` | **PASS (VERIFIED)** |
| **Hardware Topology** | Dynamic core budgeting per worker; strict prohibition of thread over-subscription; non-locking MPS GPU allocation | **PASS (VERIFIED)** |
| **Air-Gap Scratch Isolation** | Tripartite Workspace Air-Gap isolation with UUID-tagged ephemeral scratch directories in node-local NVMe storage | **PASS (VERIFIED)** |
| **Self-Healing Remediation** | Dynamic remediation callback interface in `SubprocessBroker` applying physical Method Matrix §8B escalation ladders | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero dummy loops, zero simulated mocks across all 10 tasks and test specifications | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\concurrency\atomic_file_lock.py ---
"""Cross-platform Reader-Writer and atomic file locking architecture.

Implements Suggestion #28:
- Authentic OS-level kernel locking: LockFileEx/UnlockFileEx on Windows, fcntl.flock on POSIX.
- RWFileLock supporting concurrent shared readers and exclusive writer with writer-priority.
- Thread-safe and cross-process safe with re-entrancy depth tracking.
- AtomicFileLock maintaining backward compatibility.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger("cochem.concurrency.atomic_file_lock")

# Win32 Kernel primitives via ctypes
if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _OVERLAPPED(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_size_t),
            ("InternalHigh", ctypes.c_size_t),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    _kernel32 = ctypes.windll.kernel32
    _kernel32.LockFileEx.restype = wintypes.BOOL
    _kernel32.UnlockFileEx.restype = wintypes.BOOL

    _LOCKFILE_FAIL_IMMEDIATELY = 0x00000001
    _LOCKFILE_EXCLUSIVE_LOCK = 0x00000002

    def _os_lock_acquire(fd: int, exclusive: bool, timeout: float) -> bool:
        """Acquire OS-level lock on Windows using LockFileEx."""
        handle = msvcrt.get_osfhandle(fd)
        flags = _LOCKFILE_FAIL_IMMEDIATELY | (_LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0)
        ov = _OVERLAPPED()
        t0 = time.time()
        while True:
            if _kernel32.LockFileEx(handle, flags, 0, 1, 0, ctypes.byref(ov)):
                return True
            if time.time() - t0 >= timeout:
                return False
            time.sleep(0.002)

    def _os_lock_release(fd: int) -> None:
        """Release OS-level lock on Windows using UnlockFileEx."""
        handle = msvcrt.get_osfhandle(fd)
        ov = _OVERLAPPED()
        _kernel32.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(ov))

else:
    import fcntl

    def _os_lock_acquire(fd: int, exclusive: bool, timeout: float) -> bool:
        """Acquire OS-level lock on POSIX using fcntl.flock."""
        flags = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
        t0 = time.time()
        while True:
            try:
                fcntl.flock(fd, flags)
                return True
            except (BlockingIOError, OSError):
                if time.time() - t0 >= timeout:
                    return False
                time.sleep(0.002)

    def _os_lock_release(fd: int) -> None:
        """Release OS-level lock on POSIX using fcntl.flock."""
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


class RWFileLockTimeoutError(TimeoutError):
    """Raised when RWFileLock acquisition times out."""


class RWFileLock:
    """Kernel-level Reader-Writer file lock with writer-priority protocol.

    Uses two OS kernel lock files:
    - writer_intent: acquired shared by readers, acquired exclusive by writer.
      When a writer arrives, it acquires writer_intent exclusive, immediately blocking
      all subsequent readers.
    - data_lock: acquired shared by readers for read duration, acquired exclusive
      by writer for write duration.
    """

    def __init__(self, lock_path: Path | str, timeout: float = 10.0) -> None:
        self.lock_path = Path(lock_path).resolve()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = float(timeout)

        self._intent_path = str(self.lock_path.with_name(f"{self.lock_path.name}.writer_intent.lock"))
        self._data_path = str(self.lock_path.with_name(f"{self.lock_path.name}.data.lock"))

        self._local = threading.local()

    def _get_read_depth(self) -> int:
        return getattr(self._local, "read_depth", 0)

    def _set_read_depth(self, val: int) -> None:
        self._local.read_depth = val

    def _get_write_depth(self) -> int:
        return getattr(self._local, "write_depth", 0)

    def _set_write_depth(self, val: int) -> None:
        self._local.write_depth = val

    @contextmanager
    def read_lock(self, timeout: Optional[float] = None) -> Generator[None, None, None]:
        """Shared read lock allowing unbounded concurrent readers with writer priority."""
        t_limit = self.timeout if timeout is None else float(timeout)
        t0 = time.time()

        # Thread-level reentrancy for active writer
        if self._get_write_depth() > 0:
            yield
            return

        # Thread-level reentrancy for active reader
        depth = self._get_read_depth()
        if depth > 0:
            self._set_read_depth(depth + 1)
            try:
                yield
            finally:
                self._set_read_depth(self._get_read_depth() - 1)
            return

        # Open dedicated file descriptors for this thread/operation
        fd_intent = os.open(self._intent_path, os.O_RDWR | os.O_CREAT)
        fd_data = os.open(self._data_path, os.O_RDWR | os.O_CREAT)
        try:
            # Step 1: Check writer intent (acquire shared on intent lock)
            remaining = max(0.001, t_limit - (time.time() - t0))
            if not _os_lock_acquire(fd_intent, exclusive=False, timeout=remaining):
                raise RWFileLockTimeoutError(
                    f"Timed out waiting for writer intent on {self.lock_path} after {t_limit:.2f}s"
                )

            try:
                # Step 2: Acquire shared read lock on data file
                remaining = max(0.001, t_limit - (time.time() - t0))
                if not _os_lock_acquire(fd_data, exclusive=False, timeout=remaining):
                    raise RWFileLockTimeoutError(
                        f"Timed out acquiring shared read lock on {self.lock_path} after {t_limit:.2f}s"
                    )
            finally:
                # Release writer intent so another writer can request intent
                _os_lock_release(fd_intent)

            self._set_read_depth(1)
            try:
                yield
            finally:
                self._set_read_depth(0)
                _os_lock_release(fd_data)
        finally:
            os.close(fd_intent)
            os.close(fd_data)

    @contextmanager
    def write_lock(self, timeout: Optional[float] = None) -> Generator[None, None, None]:
        """Exclusive write lock with writer-priority blocking new incoming readers."""
        t_limit = self.timeout if timeout is None else float(timeout)
        t0 = time.time()

        # Thread-level reentrancy for active writer
        depth = self._get_write_depth()
        if depth > 0:
            self._set_write_depth(depth + 1)
            try:
                yield
            finally:
                self._set_write_depth(self._get_write_depth() - 1)
            return

        fd_intent = os.open(self._intent_path, os.O_RDWR | os.O_CREAT)
        fd_data = os.open(self._data_path, os.O_RDWR | os.O_CREAT)
        try:
            # Step 1: Acquire exclusive writer intent to block new readers immediately
            remaining = max(0.001, t_limit - (time.time() - t0))
            if not _os_lock_acquire(fd_intent, exclusive=True, timeout=remaining):
                raise RWFileLockTimeoutError(
                    f"Timed out acquiring writer intent on {self.lock_path} after {t_limit:.2f}s"
                )

            try:
                # Step 2: Acquire exclusive lock on data file (waits for active readers to clear)
                remaining = max(0.001, t_limit - (time.time() - t0))
                if not _os_lock_acquire(fd_data, exclusive=True, timeout=remaining):
                    raise RWFileLockTimeoutError(
                        f"Timed out acquiring exclusive write lock on {self.lock_path} after {t_limit:.2f}s"
                    )

                self._set_write_depth(1)
                try:
                    yield
                finally:
                    self._set_write_depth(0)
                    _os_lock_release(fd_data)
            finally:
                _os_lock_release(fd_intent)
        finally:
            os.close(fd_intent)
            os.close(fd_data)

    def acquire(self, shared: bool = False, timeout: Optional[float] = None) -> bool:
        """Acquire lock (shared read if shared=True, else exclusive write)."""
        t = self.timeout if timeout is None else timeout
        cm = self.read_lock(timeout=t) if shared else self.write_lock(timeout=t)
        cm.__enter__()
        self._local.cm = cm
        return True

    def release(self) -> None:
        """Release currently held lock."""
        cm = getattr(self._local, "cm", None)
        if cm is not None:
            self._local.cm = None
            cm.__exit__(None, None, None)

    def __enter__(self) -> RWFileLock:
        self.acquire(shared=False)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


class AtomicFileLock(RWFileLock):
    """Drop-in compatible wrapper around RWFileLock defaulting to exclusive locking."""

    def __init__(self, lock_path: Path | str, timeout: float = 10.0, **kwargs: Any) -> None:
        super().__init__(lock_path=lock_path, timeout=timeout)


__all__ = ["RWFileLock", "AtomicFileLock", "RWFileLockTimeoutError"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\concurrency\subprocess_broker.py ---
"""Deterministic Subprocess Broker & Fault Ladder.
Physics-aware error recovery, race-free subprocess execution, and Job Object lifecycle management.
Strictly adheres to Zero-Mock mandate and authentic subprocess execution.
"""

from __future__ import annotations

import atexit
import ctypes
import dataclasses
import enum
import logging
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

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

    success: bool
    stdout: str
    stderr: str
    returncode: int
    retries_attempted: int
    final_params: Dict[str, Any]


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
        context_or_engine: Union[Any, str] = "cochem_worker",
        initial_params: Optional[Dict[str, Any]] = None,
        scratch_dir: Optional[Union[pathlib.Path, str]] = None,
        base_scratch_dir: Optional[Union[pathlib.Path, str]] = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        if isinstance(context_or_engine, str):
            self.engine_name: str = context_or_engine
        else:
            self.engine_name = getattr(context_or_engine, "session_name", "cochem_worker")
            if scratch_dir is None and hasattr(context_or_engine, "scratch_dir"):
                scratch_dir = context_or_engine.scratch_dir

        self.current_params: Dict[str, Any] = dict(initial_params or {})
        self.max_retries: int = max(1, int(max_retries))
        self.triage: DiagnosticTriageEngine = DiagnosticTriageEngine()
        self.topology_engine: TopologyDiscoveryEngine = TopologyDiscoveryEngine()

        # Tripartite Workspace Air-Gap dynamic scratch resolution
        explicit_scratch = base_scratch_dir or scratch_dir
        if explicit_scratch is not None:
            self.base_scratch_dir: pathlib.Path = pathlib.Path(explicit_scratch).resolve()
        else:
            env_scratch = (
                os.environ.get("SLURM_TMPDIR")
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

    def execute(
        self,
        command: List[str],
        timeout_sec: float = 60.0,
        remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
    ) -> SubprocessExecutionResult:
        """Executes command under deterministic fault ladder with process containment."""
        return self.execute_with_remediation(
            command=command,
            timeout_sec=timeout_sec,
            remediate_callback=remediate_callback,
        )

    def execute_with_remediation(
        self,
        command: List[str],
        timeout_sec: float = 60.0,
        remediate_callback: Optional[Callable[[FailureCategory, Dict[str, Any], pathlib.Path], List[str]]] = None,
    ) -> SubprocessExecutionResult:
        """Execute command under deterministic fault ladder with up to MAX_RETRIES remediation cycles."""
        retries = 0
        last_stdout = ""
        last_stderr = ""
        last_code = 1

        # Ephemeral per-job sandbox subdirectory conforming to Tripartite Air-Gap
        job_id = uuid.uuid4().hex[:12]
        job_scratch = self.base_scratch_dir / f"cochem_job_{self.engine_name}_{job_id}"
        job_scratch.mkdir(parents=True, exist_ok=True)

        current_cmd = list(command)

        try:
            while retries < self.max_retries:
                env = dict(self.topology_engine.get_worker_env())
                # Scrub inherited CUDA_VISIBLE_DEVICES unless GPU assignment is explicitly designated
                if "CUDA_VISIBLE_DEVICES" in env and "CUDA_VISIBLE_DEVICES" not in self.current_params:
                    pass
                # Isolate MPS pipe paths per worker session to prevent uncoordinated GPU locking
                mps_pipe = job_scratch / f"mps_pipe_{os.getpid()}_{retries}"
                env["CUDA_MPS_PIPE_DIRECTORY"] = str(mps_pipe)

                kwargs: Dict[str, Any] = {
                    "cwd": str(job_scratch),
                    "env": env,
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                    "text": True,
                }

                if sys.platform == "win32":
                    CREATE_SUSPENDED = 0x00000004
                    kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_SUSPENDED
                else:
                    kwargs["start_new_session"] = True
                    if sys.platform.startswith("linux"):
                        def _posix_pdeathsig() -> None:
                            try:
                                import ctypes
                                libc = ctypes.CDLL("libc.so.6")
                                PR_SET_PDEATHSIG = 1
                                SIGKILL = 9
                                libc.prctl(PR_SET_PDEATHSIG, SIGKILL)
                            except Exception:
                                pass
                        kwargs["preexec_fn"] = _posix_pdeathsig

                try:
                    proc = subprocess.Popen(current_cmd, **kwargs)
                    self.assign_to_job(proc)
                    if sys.platform == "win32":
                        try:
                            ctypes.windll.ntdll.NtResumeProcess(int(proc._handle))
                        except Exception:
                            pass

                    try:
                        out, err = proc.communicate(timeout=timeout_sec)
                        code = proc.returncode
                    except subprocess.TimeoutExpired:
                        self.terminate_process_tree(proc)
                        out, err = "", "Subprocess execution timed out"
                        code = -1

                    last_stdout = out
                    last_stderr = err
                    last_code = code

                    if code == 0:
                        # Extract validated artifacts to artifacts dir if designated
                        artifacts_env = os.environ.get("COCHEM_ARTIFACTS_DIR") or os.environ.get("COCHEM_ARTIFACTS")
                        if artifacts_env:
                            art_dir = pathlib.Path(artifacts_env)
                            art_dir.mkdir(parents=True, exist_ok=True)
                            for ext in [".out", ".property.txt", ".gbw"]:
                                for f in job_scratch.glob(f"*{ext}"):
                                    try:
                                        shutil.copy2(str(f), str(art_dir / f.name))
                                    except Exception:
                                        pass

                        return SubprocessExecutionResult(
                            success=True,
                            stdout=last_stdout,
                            stderr=last_stderr,
                            returncode=0,
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
                success=False,
                stdout=last_stdout,
                stderr=last_stderr,
                returncode=last_code,
                retries_attempted=retries,
                final_params=self.current_params,
            )
        finally:
            # Lifecycle hygiene: sweep and delete ephemeral sandbox
            shutil.rmtree(str(job_scratch), ignore_errors=True)


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
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            parent.terminate()
            _, alive = psutil.wait_procs(children + [parent], timeout=grace_timeout)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            if sys.platform != "win32":
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
            else:
                try:
                    proc.kill()
                except Exception:
                    pass

    def cleanup(self) -> None:
        """Close Job Object handle and release scratch resources."""
        if sys.platform == "win32" and self._job_handle is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(self._job_handle)
            except Exception:
                pass
            self._job_handle = None

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\core\hardware\topology.py ---
"""Hybrid Architecture Aware Thread & Core Tuner.
Dynamically budgets CPU and GPU resources according to Method Matrix v4 §8A contention budgeting.
Strictly adheres to Zero-Mock mandate and physical OS topology discovery.
"""

from __future__ import annotations

import ctypes
import dataclasses
import logging
import os
import pathlib
import sys
from typing import Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger("cochem.core.hardware.topology")


@dataclasses.dataclass(slots=True, frozen=True)
class HardwareTopology:
    """Immutable hardware topology and core budgeting specification."""

    total_logical_cpus: int
    total_physical_cores: int
    p_cores: int
    e_cores: int
    resource_ceiling: int
    scout_cores: int
    anchor_cores: int
    gpu_mps_workers: int
    environment_variables: Dict[str, str]


class TopologyDiscoveryEngine:
    """Hardware discovery and Scout-and-Anchor budgeting engine."""

    def __init__(self) -> None:
        self._cached_topology: Optional[HardwareTopology] = None

    def discover_p_e_cores(self) -> Tuple[int, int]:
        """Distinguish Intel Performance (P) cores from Efficient (E) cores."""
        logical_total = psutil.cpu_count(logical=True) or os.cpu_count() or 1
        physical_total = psutil.cpu_count(logical=False) or max(1, logical_total // 2)

        # 1. Windows NT: Query GetLogicalProcessorInformationEx via Win32 API
        if sys.platform == "win32":
            try:
                # RelationProcessorCore = 0
                class PROCESSOR_RELATIONSHIP(ctypes.Structure):
                    _fields_ = [
                        ("Flags", ctypes.c_ubyte),
                        ("EfficiencyClass", ctypes.c_ubyte),
                        ("Reserved", ctypes.c_ubyte * 20),
                        ("GroupCount", ctypes.c_ushort),
                        ("GroupMask", ctypes.c_size_t * 1),
                    ]

                class SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX(ctypes.Structure):
                    _fields_ = [
                        ("Relationship", ctypes.c_uint),
                        ("Size", ctypes.c_ulong),
                        ("Processor", PROCESSOR_RELATIONSHIP),
                    ]

                buffer_size = ctypes.c_ulong(0)
                # First call to query required buffer size
                ctypes.windll.kernel32.GetLogicalProcessorInformationEx(
                    0,  # RelationProcessorCore
                    None,
                    ctypes.byref(buffer_size),
                )

                if buffer_size.value > 0:
                    buffer = (ctypes.c_byte * buffer_size.value)()
                    res = ctypes.windll.kernel32.GetLogicalProcessorInformationEx(
                        0,
                        ctypes.byref(buffer),
                        ctypes.byref(buffer_size),
                    )
                    if res != 0:
                        offset = 0
                        p_count = 0
                        e_count = 0
                        while offset < buffer_size.value:
                            info = ctypes.cast(
                                ctypes.byref(buffer, offset),
                                ctypes.POINTER(SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX),
                            ).contents
                            if info.Relationship == 0:  # RelationProcessorCore
                                eff_class = info.Processor.EfficiencyClass
                                if eff_class > 0:
                                    p_count += 1
                                else:
                                    e_count += 1
                            if info.Size == 0:
                                break
                            offset += info.Size

                        if (p_count + e_count) > 0:
                            return max(1, p_count), e_count
            except Exception as win_err:
                logger.debug("Windows processor information query bypassed: %s", win_err)

        # 2. Linux: Parse sysfs cpufreq
        if sys.platform.startswith("linux"):
            try:
                cpu_dir = pathlib.Path("/sys/devices/system/cpu")
                freqs: List[int] = []
                for p in cpu_dir.glob("cpu[0-9]*/cpufreq/cpuinfo_max_freq"):
                    try:
                        f_val = int(p.read_text().strip())
                        freqs.append(f_val)
                    except (OSError, ValueError):
                        continue
                if freqs and len(set(freqs)) > 1:
                    max_freq = max(freqs)
                    p_count = sum(1 for f in freqs if f == max_freq)
                    e_count = len(freqs) - p_count
                    return max(1, p_count), e_count
            except Exception as linux_err:
                logger.debug("Linux cpufreq query bypassed: %s", linux_err)

        # Uniform fallback
        return physical_total, 0

    def resolve_resource_ceiling(self) -> int:
        """Resolve effective CPU ceiling from Slurm, Cgroups v1/v2, affinity, or physical cores."""
        # 1. Slurm environment variable
        slurm_cpus = os.environ.get("SLURM_CPUS_PER_TASK")
        if slurm_cpus is not None:
            try:
                val = int(slurm_cpus)
                if val >= 1:
                    return val
            except ValueError:
                pass

        # 2. Linux Cgroups v2: /sys/fs/cgroup/cpu.max (quota period)
        cgroup_v2 = pathlib.Path("/sys/fs/cgroup/cpu.max")
        if cgroup_v2.exists():
            try:
                parts = cgroup_v2.read_text().strip().split()
                if len(parts) >= 2 and parts[0] != "max":
                    quota = float(parts[0])
                    period = float(parts[1])
                    if period > 0:
                        cores = int(quota / period)
                        if cores >= 1:
                            return cores
            except Exception:
                pass

        # 3. Linux Cgroups v1: cpu.cfs_quota_us / cpu.cfs_period_us
        cgroup_v1_quota = pathlib.Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        cgroup_v1_period = pathlib.Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        if cgroup_v1_quota.exists() and cgroup_v1_period.exists():
            try:
                quota_val = float(cgroup_v1_quota.read_text().strip())
                period_val = float(cgroup_v1_period.read_text().strip())
                if quota_val > 0 and period_val > 0:
                    cores = int(quota_val / period_val)
                    if cores >= 1:
                        return cores
            except Exception:
                pass

        # 4. POSIX process affinity
        if hasattr(os, "sched_getaffinity"):
            try:
                affinity_cores = len(os.sched_getaffinity(0))
                if affinity_cores >= 1:
                    return affinity_cores
            except Exception:
                pass

        # 5. Physical cores fallback
        physical = psutil.cpu_count(logical=False) or os.cpu_count() or 1
        return max(1, physical)

    def discover_topology(self, concurrent_workers: int = 1) -> HardwareTopology:
        """Calculate Scout-and-Anchor core budget and thread environment variables."""
        logical_total = psutil.cpu_count(logical=True) or os.cpu_count() or 1
        physical_total = psutil.cpu_count(logical=False) or max(1, logical_total // 2)
        ceiling = self.resolve_resource_ceiling()
        p_cores, e_cores = self.discover_p_e_cores()

        # Clamp P-cores to available ceiling
        effective_p_cores = max(1, min(p_cores, ceiling))

        # Scout-and-Anchor Concurrency Budget (Method Matrix v4 §8A):
        # Scout Core: 1 physical P-core dedicated to host orchestration and MACE ML
        # Anchor Cores: Remaining (N_P-cores - 1) cores across QC subprocesses (ORCA/CFOUR)
        if effective_p_cores > 2:
            scout_cores = 1
            anchor_cores = effective_p_cores - 1
        elif effective_p_cores == 2:
            scout_cores = 1
            anchor_cores = 1
        else:
            scout_cores = 1
            anchor_cores = 0

        # Worker thread injection values with dynamic contention budgeting
        budget_pool = anchor_cores if anchor_cores > 0 else scout_cores
        budgeted_threads = max(1, budget_pool // max(1, concurrent_workers))
        env_vars = {
            "OMP_NUM_THREADS": str(budgeted_threads),
            "MKL_NUM_THREADS": str(budgeted_threads),
            "OPENBLAS_NUM_THREADS": str(budgeted_threads),
            "VECLIB_MAXIMUM_THREADS": str(budgeted_threads),
            "NUMEXPR_NUM_THREADS": str(budgeted_threads),
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(max(1, 100 // max(1, concurrent_workers))),
        }

        # GPU MPS Worker Ceiling: 2 to 4 concurrent processes
        gpu_mps_workers = max(2, min(4, ceiling))

        topology = HardwareTopology(
            total_logical_cpus=logical_total,
            total_physical_cores=physical_total,
            p_cores=effective_p_cores,
            e_cores=e_cores,
            resource_ceiling=ceiling,
            scout_cores=scout_cores,
            anchor_cores=anchor_cores,
            gpu_mps_workers=gpu_mps_workers,
            environment_variables=env_vars,
        )
        self._cached_topology = topology
        return topology

    def get_worker_env(
        self,
        concurrent_workers: int = 1,
        worker_index: int = 0,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Construct subprocess execution environment with dynamically budgeted thread variables."""
        topo = self.discover_topology(concurrent_workers=concurrent_workers)
        base_env = dict(os.environ)
        base_env.update(topo.environment_variables)

        # Dynamic host thread budgeting per worker (Method Matrix §8A)
        budget_pool = topo.anchor_cores if topo.anchor_cores > 0 else topo.scout_cores
        budgeted_threads = max(1, budget_pool // max(1, concurrent_workers))
        base_env["OMP_NUM_THREADS"] = str(budgeted_threads)
        base_env["MKL_NUM_THREADS"] = str(budgeted_threads)
        base_env["OPENBLAS_NUM_THREADS"] = str(budgeted_threads)
        base_env["VECLIB_MAXIMUM_THREADS"] = str(budgeted_threads)
        base_env["NUMEXPR_NUM_THREADS"] = str(budgeted_threads)

        # Zero-CUDA-Locking Directive: Non-locking MPS GPU apportionment
        base_env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(max(1, 100 // max(1, concurrent_workers)))

        # Multi-GPU physical device indexing fallback
        available_gpus = 0
        try:
            import torch
            if torch.cuda.is_available():
                available_gpus = torch.cuda.device_count()
        except Exception:
            pass

        if available_gpus > 0:
            assigned_gpu = worker_index % available_gpus
            base_env["CUDA_VISIBLE_DEVICES"] = str(assigned_gpu)

        if extra_env is not None:
            base_env.update(extra_env)
        return base_env


    def pin_scout_affinity(self, core_index: int = 0) -> bool:
        """Bind host orchestration process to specific core index to avoid thread migration."""
        try:
            if hasattr(os, "sched_setaffinity"):
                os.sched_setaffinity(0, {core_index})
                return True
            elif sys.platform == "win32":
                mask = 1 << max(0, int(core_index))
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                res = ctypes.windll.kernel32.SetProcessAffinityMask(handle, ctypes.c_size_t(mask))
                return bool(res != 0)
        except Exception as pin_err:
            logger.debug("Affinity pinning error on core %d: %s", core_index, pin_err)
            return False
        return False

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\core\process_reaper.py ---
"""Cross-platform process lifecycle manager and zombie reaper daemon.

Provenance & Specifications:
- Method Matrix [M]: Reliable termination of orphaned QM/MM worker subprocesses.
- OS Containment [D]: Windows Job Objects and Linux PDEATHSIG containment primitives.
- Telemetry [E]: Progressive escalation (SIGTERM -> SIGKILL) with CPU/memory footprint capture.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import psutil

from src.cochem.orchestration.sqlite_queue import SQLiteTaskQueue

logger = logging.getLogger(__name__)

DEFAULT_GRACE_TIMEOUT_SEC: float = 5.0
DEFAULT_TIMEOUT_GRACE_PERIOD_SEC: float = 30.0


class ProcessReapTimeoutError(RuntimeError):
    """Raised when stubborn or uninterruptible processes fail to terminate within grace timeout."""


def set_pdeathsig(sig: int = signal.SIGTERM) -> bool:
    """Set PR_SET_PDEATHSIG on Linux/WSL via ctypes to ensure child termination on parent exit."""
    if sys.platform.startswith("linux"):
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            PR_SET_PDEATHSIG = 1
            ret = libc.prctl(PR_SET_PDEATHSIG, sig)
            return ret == 0
        except Exception as err:
            logger.debug("Failed to set PR_SET_PDEATHSIG: %s", err)
            return False
    return False


def get_pdeathsig_preexec_fn(sig: int = signal.SIGTERM) -> Optional[Any]:
    """Return a preexec callable suitable for subprocess.Popen to establish parent death signals on Linux."""
    if not sys.platform.startswith("linux"):
        return None

    def _preexec() -> None:
        set_pdeathsig(sig)

    return _preexec


@dataclass(frozen=True)
class ProcessMetadata:
    """Immutable snapshot of tracked process identity and origin."""

    pid: int
    ppid: int
    create_time: float
    task_id: Optional[str] = None
    status: str = "ACTIVE"


class ProcessTreeManager:
    """Manages process hierarchies and guarantees complete subtree termination."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tracked: Dict[int, ProcessMetadata] = {}
        self._job_handle: Optional[Any] = None
        self._init_platform_containment()

    def _init_platform_containment(self) -> None:
        """Initialize platform-specific containment primitives."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

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

                job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
                if job_handle:
                    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    JobObjectExtendedLimitInformation = 9
                    ctypes.windll.kernel32.SetInformationJobObject(
                        job_handle,
                        JobObjectExtendedLimitInformation,
                        ctypes.byref(info),
                        ctypes.sizeof(info),
                    )
                    self._job_handle = job_handle
            except Exception as err:
                logger.debug("Windows Job Object initialization bypassed: %s", err)
                self._job_handle = None

    def register_process(
        self,
        proc: Union[psutil.Process, int],
        task_id: Optional[str] = None,
    ) -> ProcessMetadata:
        """Register a child process for lifecycle tracking."""
        p = proc if isinstance(proc, psutil.Process) else psutil.Process(proc)
        pid = p.pid
        ppid = p.ppid()
        ctime = p.create_time()

        if sys.platform == "win32" and self._job_handle is not None:
            process_handle = None
            try:
                import ctypes
                PROCESS_ALL_ACCESS = 0x1F0FFF
                process_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
                if process_handle:
                    ctypes.windll.kernel32.AssignProcessToJobObject(self._job_handle, process_handle)
            except Exception as assign_err:
                logger.debug("Could not assign PID %d to Windows Job Object: %s", pid, assign_err)
            finally:
                if process_handle:
                    try:
                        import ctypes
                        ctypes.windll.kernel32.CloseHandle(process_handle)
                    except Exception as close_err:
                        logger.debug("Error closing process handle for PID %d: %s", pid, close_err)

        metadata = ProcessMetadata(
            pid=pid,
            ppid=ppid,
            create_time=ctime,
            task_id=task_id,
        )
        with self._lock:
            self._tracked[pid] = metadata
        return metadata

    def unregister_process(self, pid: int) -> None:
        """Remove process from active tracking register."""
        with self._lock:
            self._tracked.pop(pid, None)

    def is_alive(self, pid: int) -> bool:
        """Check if process exists and create_time matches registered snapshot."""
        with self._lock:
            meta = self._tracked.get(pid)
        if not psutil.pid_exists(pid):
            return False
        try:
            p = psutil.Process(pid)
            if meta is not None and abs(p.create_time() - meta.create_time) > 1.0:
                return False  # PID was recycled by OS
            return bool(p.is_running() and p.status() != psutil.STATUS_ZOMBIE)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def get_tracked_pids(self) -> List[int]:
        """Return point-in-time snapshot of tracked PIDs under reentrant lock."""
        with self._lock:
            return list(self._tracked.keys())

    def get_metadata(self, pid: int) -> Optional[ProcessMetadata]:
        """Retrieve metadata for a tracked process under lock."""
        with self._lock:
            return self._tracked.get(pid)

    @property
    def tracked_pids(self) -> List[int]:
        """Property returning snapshot of tracked PIDs."""
        with self._lock:
            return list(self._tracked.keys())

    def terminate_tree(
        self,
        pid: int,
        grace_timeout_sec: float = DEFAULT_GRACE_TIMEOUT_SEC,
    ) -> Dict[str, Any]:
        """Progressive termination escalation sequence: SIGTERM -> wait -> SIGKILL / Job Object."""
        metrics: Dict[str, Any] = {
            "pid": pid,
            "cpu_time": 0.0,
            "resident_memory_mb": 0.0,
            "terminated_children_count": 0,
            "success": False,
            "leaked_pids": [],
        }

        if not psutil.pid_exists(pid):
            self.unregister_process(pid)
            metrics["success"] = True
            return metrics

        try:
            parent = psutil.Process(pid)
        except psutil.NoSuchProcess:
            self.unregister_process(pid)
            metrics["success"] = True
            return metrics

        # Verify against PID recycling
        with self._lock:
            meta = self._tracked.get(pid)
        if meta is not None and abs(parent.create_time() - meta.create_time) > 1.0:
            self.unregister_process(pid)
            metrics["success"] = True
            return metrics

        # Gather resource telemetry before termination
        try:
            cpu_times = parent.cpu_times()
            metrics["cpu_time"] = cpu_times.user + cpu_times.system
            metrics["resident_memory_mb"] = parent.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            logger.debug("Could not sample telemetry before terminating PID %d", pid)

        # Collect child subtree
        try:
            children = parent.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            children = []

        all_processes = children + [parent]
        metrics["terminated_children_count"] = len(children)

        # Step 1: Issue SIGTERM / terminate()
        for p in all_processes:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Step 2: Await graceful termination
        gone, alive = psutil.wait_procs(all_processes, timeout=grace_timeout_sec)

        # Step 3: Issue SIGKILL / kill() for remaining stubborn processes
        if alive:
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Platform-specific process containment termination
            if sys.platform == "win32" and self._job_handle is not None:
                try:
                    import ctypes
                    ctypes.windll.kernel32.TerminateJobObject(self._job_handle, 1)
                except Exception as job_err:
                    logger.debug("TerminateJobObject error: %s", job_err)
            elif sys.platform != "win32":
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass

            # Evict MPS context if present
            if "CUDA_MPS_PIPE_DIRECTORY" in os.environ:
                try:
                    subprocess.run(["nvidia-smi", "--gpu-reset"], capture_output=True, timeout=2.0)
                except Exception:
                    pass

            # Final check with 2.0s timeout
            _, still_alive = psutil.wait_procs(alive, timeout=2.0)
        else:
            still_alive = []

        if still_alive:
            # Stubborn D-state or leaked processes
            metrics["success"] = False
            metrics["leaked_pids"] = [p.pid for p in still_alive]
            with self._lock:
                if pid in self._tracked:
                    old_meta = self._tracked[pid]
                    self._tracked[pid] = ProcessMetadata(
                        pid=old_meta.pid,
                        ppid=old_meta.ppid,
                        create_time=old_meta.create_time,
                        task_id=old_meta.task_id,
                        status="ORPHAN_LEAK",
                    )
            logger.error("Process subtree for PID %d could not be reaped: %s", pid, metrics["leaked_pids"])
            raise ProcessReapTimeoutError(
                f"Failed to terminate process subtree for PID {pid}; stubborn PIDs: {metrics['leaked_pids']}"
            )

        self.unregister_process(pid)
        metrics["success"] = True
        return metrics


class ZombieReaperDaemon:
    """Watchdog daemon sweeping orphaned subprocesses and reclaiming expired task leases."""

    def __init__(
        self,
        queue: Optional[SQLiteTaskQueue] = None,
        tree_manager: Optional[ProcessTreeManager] = None,
        parent_pid: Optional[int] = None,
        grace_period_sec: float = DEFAULT_TIMEOUT_GRACE_PERIOD_SEC,
        interval_sec: float = 5.0,
    ) -> None:
        self.queue = queue
        self.tree_manager = tree_manager or ProcessTreeManager()
        self.parent_pid = parent_pid or os.getpid()
        self.grace_period_sec = grace_period_sec
        self.interval_sec = interval_sec

    def is_orphan(self, pid: int) -> bool:
        """Classify process as orphaned by checking PPID and parent liveness."""
        try:
            if not psutil.pid_exists(pid):
                return False
            if self.parent_pid is not None and not psutil.pid_exists(self.parent_pid):
                return True
            p = psutil.Process(pid)
            ppid = p.ppid()
            if ppid == 1:
                return True
            if self.parent_pid is not None and ppid != self.parent_pid:
                if not psutil.pid_exists(ppid):
                    return True
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def sweep_orphans(self) -> List[int]:
        """Perform a single sweep across tracked processes and reclaim expired tasks."""
        terminated_pids: List[int] = []

        # 1. Sweep tracked processes using thread-safe snapshot
        active_pids = self.tree_manager.get_tracked_pids()
        for pid in active_pids:
            if not self.tree_manager.is_alive(pid):
                self.tree_manager.unregister_process(pid)
                continue

            meta = self.tree_manager.get_metadata(pid)
            task_id = meta.task_id if meta is not None else None

            # Check orphan conditions
            if self.is_orphan(pid):
                metrics = self.tree_manager.terminate_tree(pid)
                terminated_pids.append(pid)
                if self.queue is not None and task_id is not None:
                    self.queue.fail_task(
                        task_id,
                        f"Process {pid} orphaned and terminated: CPU={metrics['cpu_time']:.2f}s, RAM={metrics['resident_memory_mb']:.1f}MB",
                        can_retry=True,
                    )

        # 2. Reclaim expired task leases from SQLite queue
        if self.queue is not None:
            self.queue.reclaim_orphaned_tasks(timeout_grace_sec=self.grace_period_sec)

        return terminated_pids


    def run_watchdog_loop(self, max_iterations: Optional[int] = None) -> List[int]:
        """Execute sweep loop for up to max_iterations or indefinitely if None."""
        all_reaped: List[int] = []
        iterations = 0
        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            terminated = self.sweep_orphans()
            all_reaped.extend(terminated)
            if max_iterations is not None and iterations >= max_iterations:
                break
            time.sleep(self.interval_sec)
        return all_reaped


__all__ = [
    "ProcessMetadata",
    "ProcessTreeManager",
    "ZombieReaperDaemon",
    "ProcessReapTimeoutError",
    "set_pdeathsig",
    "get_pdeathsig_preexec_fn",
]


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\cochem_spycfit_ml_storage.py ---
# -*- coding: utf-8 -*-
"""CoChem-SpycFit ML: Thread-Safe HDF5 SWMR Storage, FileLock IPC & DAG Manager.

Provides:
- In-process threading.Lock and cross-process filelock.FileLock concurrency guards
- Single-Writer Multi-Reader (SWMR) HDF5 persistence for spectra and states
- Automatic zombie sidecar lock file detection and active PID recovery
- Ephemeral sandbox lifecycle manager for subprocess isolation
- Non-destructive DAG commit history and pointer swapping time-travel reversion

Authoritative Standards:
- Thread-Safe HDF5 Access Pattern (SWMR mode, libver='latest', lustre_bypass)
- Tripartite Air-Gap Persistence Architecture (Tier 2 Artifacts, Tier 3 Ephemeral)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import filelock
import h5py
import numpy as np

from cochem_spycfit_ml_schema import FitStateCommitSchema

logger = logging.getLogger("cochem.spycfit.ml.storage")


def _is_pid_alive(pid: int) -> bool:
    """Cross-platform check whether a PID is currently alive."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == STILL_ACTIVE
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def recover_zombie_locks(lock_file_path: Path, max_stale_seconds: float = 30.0) -> bool:
    """Detect and safely clean up orphaned/zombie lock files and directory leases."""
    lock_path = Path(lock_file_path).resolve()
    if not lock_path.exists():
        return False

    try:
        if lock_path.is_dir():
            from cochem.concurrency.network_lock import NetworkHeartbeatLock
            hb_lock = NetworkHeartbeatLock(lock_path, lease_ttl_sec=max_stale_seconds)
            if hb_lock.is_stale():
                logger.warning(f"Recovering stale directory lease: {lock_path}")
                shutil.rmtree(str(lock_path), ignore_errors=True)
                return True
            return False

        should_clean = False
        content = lock_path.read_text(encoding="utf-8").strip()

        if "." in content or ":" in content:
            parts = content.split(":")
            if len(parts) >= 2:
                try:
                    pid = int(parts[0])
                    timestamp = float(parts[1])
                    if not _is_pid_alive(pid) and (time.time() - timestamp) > max_stale_seconds:
                        should_clean = True
                except ValueError:
                    should_clean = True
        elif content.startswith("{"):
            try:
                manifest = json.loads(content)
                pid = int(manifest.get("pid", 0))
                expires_at = float(manifest.get("expires_at", 0.0))
                if time.time() > expires_at and not _is_pid_alive(pid):
                    should_clean = True
            except Exception:
                should_clean = True

        if should_clean:
            logger.warning(f"Recovering zombie lock file: {lock_path}")
            lock_path.unlink(missing_ok=True)
            return True
    except Exception as exc:
        logger.debug(f"Lock recovery check encountered error: {exc}")
    return False



class EphemeralSandbox:
    """Tier 3 Ephemeral sandbox context manager with guaranteed lifecycle cleanup."""

    def __init__(self, base_scratch_dir: Optional[Path] = None, prefix: str = "cochem_spycfit_") -> None:
        self.base_scratch_dir = Path(base_scratch_dir).resolve() if base_scratch_dir else Path(tempfile.gettempdir())
        self.prefix = prefix
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self.path: Optional[Path] = None

    def __enter__(self) -> EphemeralSandbox:
        self.base_scratch_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = tempfile.TemporaryDirectory(prefix=self.prefix, dir=str(self.base_scratch_dir))
        self.path = Path(self._temp_dir.name).resolve()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except Exception:
                if self.path and self.path.exists():
                    shutil.rmtree(self.path, ignore_errors=True)

    def create_scratch_file(self, filename: str, content: str) -> Path:
        """Create a scratch input/output file inside the sandbox."""
        if self.path is None:
            raise RuntimeError("Sandbox is not open")
        target = self.path / filename
        target.write_text(content, encoding="utf-8")
        return target


class SpycFitHDF5Storage:
    """Thread-safe, multi-process SWMR HDF5 persistence storage engine."""

    _global_thread_lock = threading.Lock()

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    @contextmanager
    def _acquire_guard(self, h5_path: Path, lustre_bypass: bool = False) -> Iterator[None]:
        """Acquire in-process thread lock and cross-process file lock."""
        h5_path = Path(h5_path).resolve()
        lock_file = h5_path.with_name(f"{h5_path.name}.lock")

        with self._global_thread_lock:
            if lustre_bypass:
                yield
            else:
                recover_zombie_locks(lock_file, max_stale_seconds=self.timeout_seconds * 3)
                fl = filelock.FileLock(str(lock_file), timeout=self.timeout_seconds)
                try:
                    with fl:
                        yield
                except filelock.Timeout as err:
                    logger.error(f"FileLock timeout on {lock_file}")
                    raise TimeoutError(f"Could not acquire lock on {h5_path} within {self.timeout_seconds}s") from err

    def initialize_store(self, h5_path: Path, lustre_bypass: bool = False) -> None:
        """Initialize HDF5 store topology with SWMR capability."""
        h5_path = Path(h5_path).resolve()
        h5_path.parent.mkdir(parents=True, exist_ok=True)

        with self._acquire_guard(h5_path, lustre_bypass=lustre_bypass):
            with h5py.File(h5_path, "a", libver="latest") as f:
                if "states" not in f:
                    f.create_group("states")
                if "datasets" not in f:
                    f.create_group("datasets")
                if "provenance" not in f:
                    f.create_group("provenance")

    def write_fit_state(self, state: FitStateCommitSchema, h5_path: Path, lustre_bypass: bool = False) -> None:
        """Persist a FitStateCommit snapshot into the /states group."""
        h5_path = Path(h5_path).resolve()
        with self._acquire_guard(h5_path, lustre_bypass=lustre_bypass):
            with h5py.File(h5_path, "a", libver="latest") as f:
                states_grp = f.require_group("states")
                state_json = state.model_dump_json()
                if state.state_id in states_grp:
                    del states_grp[state.state_id]
                ds = states_grp.create_dataset(state.state_id, data=state_json)
                ds.attrs["state_id"] = state.state_id
                ds.attrs["parent_id"] = state.parent_id or ""
                ds.attrs["timestamp"] = state.timestamp_iso
                ds.attrs["chi_squared"] = state.chi_squared
                ds.attrs["rms_residual_mhz"] = state.rms_residual_mhz

    def read_fit_state(self, state_id: str, h5_path: Path, lustre_bypass: bool = False) -> FitStateCommitSchema:
        """Retrieve a FitStateCommit snapshot by state_id."""
        h5_path = Path(h5_path).resolve()
        with self._acquire_guard(h5_path, lustre_bypass=lustre_bypass):
            with h5py.File(h5_path, "r", libver="latest") as f:
                states_grp = f["states"]
                if state_id not in states_grp:
                    raise KeyError(f"State ID '{state_id}' not found in {h5_path}")
                ds = states_grp[state_id]
                raw_json = ds[()].decode("utf-8") if isinstance(ds[()], bytes) else str(ds[()])
                return FitStateCommitSchema.model_validate_json(raw_json)

    def list_states(self, h5_path: Path, lustre_bypass: bool = False) -> List[str]:
        """List all state IDs stored in the HDF5 file."""
        h5_path = Path(h5_path).resolve()
        if not h5_path.exists():
            return []
        with self._acquire_guard(h5_path, lustre_bypass=lustre_bypass):
            with h5py.File(h5_path, "r", libver="latest") as f:
                if "states" not in f:
                    return []
                return list(f["states"].keys())

    def write_tensor_dataset(
        self,
        dataset_name: str,
        tensor: np.ndarray,
        h5_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
        lustre_bypass: bool = False,
    ) -> None:
        """Write raw NumPy array dataset into /datasets."""
        h5_path = Path(h5_path).resolve()
        with self._acquire_guard(h5_path, lustre_bypass=lustre_bypass):
            with h5py.File(h5_path, "a", libver="latest") as f:
                ds_grp = f.require_group("datasets")
                if dataset_name in ds_grp:
                    del ds_grp[dataset_name]
                dset = ds_grp.create_dataset(dataset_name, data=tensor)
                if metadata:
                    for k, v in metadata.items():
                        dset.attrs[k] = str(v)

    def read_tensor_dataset(self, dataset_name: str, h5_path: Path, lustre_bypass: bool = False) -> np.ndarray:
        """Read raw NumPy array dataset from /datasets."""
        h5_path = Path(h5_path).resolve()
        with self._acquire_guard(h5_path, lustre_bypass=lustre_bypass):
            with h5py.File(h5_path, "r", libver="latest") as f:
                ds_grp = f["datasets"]
                if dataset_name not in ds_grp:
                    raise KeyError(f"Dataset '{dataset_name}' not found in {h5_path}")
                return np.array(ds_grp[dataset_name])


class DAGCommitManager:
    """Branching Directed Acyclic Graph (DAG) state manager with non-destructive time travel."""

    def __init__(self, storage: SpycFitHDF5Storage, registry_path: Path) -> None:
        self.storage = storage
        self.registry_path = Path(registry_path).resolve()
        self.current_head_id: Optional[str] = None
        self._state_cache: Dict[str, FitStateCommitSchema] = {}

    def commit(self, state: FitStateCommitSchema, lustre_bypass: bool = False) -> str:
        """Record a new FitState snapshot and advance the active DAG head."""
        self.storage.write_fit_state(state, self.registry_path, lustre_bypass=lustre_bypass)
        self.current_head_id = state.state_id
        self._state_cache[state.state_id] = state
        return state.state_id

    def revert_to(self, state_id: str, lustre_bypass: bool = False) -> FitStateCommitSchema:
        """Revert active head pointer to target state (time-travel pointer swapping)."""
        if state_id in self._state_cache:
            state = self._state_cache[state_id]
        else:
            state = self.storage.read_fit_state(state_id, self.registry_path, lustre_bypass=lustre_bypass)
            self._state_cache[state_id] = state
        self.current_head_id = state_id
        return state

    def get_history(self, current_state_id: Optional[str] = None, lustre_bypass: bool = False) -> List[FitStateCommitSchema]:
        """Traverse DAG lineage from head backwards to root."""
        target_id = current_state_id or self.current_head_id
        if not target_id:
            return []

        history = []
        visited = set()

        curr_id: Optional[str] = target_id
        while curr_id and curr_id not in visited:
            visited.add(curr_id)
            if curr_id in self._state_cache:
                st = self._state_cache[curr_id]
            else:
                st = self.storage.read_fit_state(curr_id, self.registry_path, lustre_bypass=lustre_bypass)
                self._state_cache[curr_id] = st
            history.append(st)
            curr_id = st.parent_id

        return history

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
import atexit
import hashlib
import hmac
import json
import logging
import math
import os
import platform
import shutil
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
    Set,
    Tuple,
    Union,
    cast,
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
    CoChemError,
    HDF5LockTimeoutError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
    QCSchemaValidationError,
    SingularityError,
)

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
BOHR_TO_METER = 0.529177210903e-10        # m / Bohr
HARTREE_TO_JOULE = 4.3597447222071e-18    # J / Hartree
HARTREE_TO_EV = 27.211386245988           # eV / Hartree
HARTREE_TO_CM_INV = 219474.63136320       # cm^-1 / Hartree

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
    """QCSchema v1 compliant calculation provenance metadata."""
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
    hmac_signature: Optional[str] = Field(
        default=None, description="HMAC-SHA256 cryptographic signature for provenance audit"
    )

    def compute_signature(self, secret_key: str = "CoChem-Provenance-Secret") -> str:
        """Computes HMAC-SHA256 signature across core provenance fields."""
        payload = f"{self.creator}|{self.version}|{self.routine}|{self.host}|{self.platform}|{self.utc}"
        sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        self.hmac_signature = sig
        return sig


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
    registered_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 registration timestamp",
    )


class PESPointRecord(BaseModel):
    """Point record representing a single potential energy surface evaluation."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)

    point_id: str = Field(..., description="Unique stable point identifier (e.g. 'grid_2d:142', 'iso_003')")
    method_id: str = Field(..., description="Registered method identifier in /methods/<method_id>")
    coordinates: Union[List[List[float]], np.ndarray] = Field(..., description="Atomic Cartesian coordinates in Angstroms (N, 3)")
    energy: float = Field(..., description="Electronic energy in Hartrees")
    gradient: Optional[Union[List[List[float]], np.ndarray]] = Field(None, description="Energy gradients in Hartree/Bohr (N, 3)")
    converged: bool = Field(default=True, description="Whether SCF and geometry optimization converged")
    wall_s: float = Field(default=0.0, ge=0.0, description="Calculation wall clock time in seconds")
    provenance: QCSchemaProvenance = Field(default_factory=QCSchemaProvenance, description="Calculation provenance record")

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coords_array(cls, v: Any) -> Any:
        if isinstance(v, np.ndarray):
            return v
        if isinstance(v, (list, tuple)):
            return np.asarray(v, dtype=np.float64)
        return v

    @field_validator("gradient", mode="before")
    @classmethod
    def validate_grad_array(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, np.ndarray):
            return v
        if isinstance(v, (list, tuple)):
            return np.asarray(v, dtype=np.float64)
        return v


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

    I = np.full((3, 3), 0.0, dtype=np.float64)
    eye3 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    for m_i, r_i in zip(masses, r, strict=False):
        r_sq = float(np.dot(r_i, r_i))
        I += m_i * (r_sq * eye3 - np.outer(r_i, r_i))

    evals, evecs = np.linalg.eigh(I)
    idx = np.argsort(evals)
    principal_moments = evals[idx]
    principal_axes = evecs[:, idx]

    return I, principal_moments, principal_axes


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
    ) -> None:
        self.path = Path(path).resolve()
        self.lock_path = self.path.parent / f"{self.path.name}.lock"
        self.lock_timeout = lock_timeout
        self.rw_lock = ReadWriteFileLock(self.lock_path, timeout=self.lock_timeout)
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
                f.require_group("points")
                f.require_group("grids")
                f.require_group("hessians")
                f.require_group("isotopologues")
                f.require_group("checkpoints")

                # Cache properties
                self.n_atoms = int(m.attrs.get("n_atoms", len(symbols)))
                self.complex_name = str(m.attrs.get("complex", complex_name))
                sym_attr = m.attrs.get("symbols")
                self.symbols = json.loads(sym_attr) if isinstance(sym_attr, str) else list(symbols)
                self.molecular_charge = int(m.attrs.get("molecular_charge", molecular_charge))
                self.spin_multiplicity = int(m.attrs.get("spin_multiplicity", spin_multiplicity))

                # Phase 2 SWMR Activation: Flush metadata and enable SWMR mode
                f.flush()
                try:
                    f.swmr_mode = True
                except (AttributeError, RuntimeError):
                    pass

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
        if dtype != VLEN_STR:
            kw.update(compression="gzip", compression_opts=4, shuffle=True)
            if checksum:
                kw["fletcher32"] = True
        return grp.create_dataset(name, **kw)

    @staticmethod
    def _append(ds: h5py.Dataset, block: np.ndarray) -> int:
        """Appends a block of data along axis 0 of a resizable dataset."""
        idx = int(ds.shape[0])
        ds.resize(idx + len(block), axis=0)
        ds[idx:] = block
        return idx

    # -------------------------------------------------------------------------
    # Writing PES Points
    # -------------------------------------------------------------------------
    def add_points(
        self,
        method_id: str,
        coords: Union[Sequence[Any], np.ndarray],
        energies: Union[Sequence[float], np.ndarray, float],
        *,
        point_ids: Optional[Sequence[str]] = None,
        gradients: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: Optional[Union[Sequence[bool], np.ndarray, bool]] = None,
        wall_s: Optional[Union[Sequence[float], np.ndarray, float]] = None,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """
        Adds computed PES points with full QCSchema provenance, chunking, and checksums.

        Args:
            method_id: Registered method identifier
            coords: Cartesian coordinates array (Npts, Natoms, 3) or (Natoms, 3) for a single point
            energies: Electronic energies array (Npts,) or float for single point
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
        coords_arr = np.asarray(coords, dtype=np.float64)
        if coords_arr.ndim == 2:
            coords_arr = coords_arr[None]
        npts, natm = coords_arr.shape[0], coords_arr.shape[1]

        energies_arr = np.asarray(energies, dtype=np.float64)
        if energies_arr.ndim == 0:
            energies_arr = energies_arr[None]

        if len(energies_arr) != npts:
            raise ValueError(f"Number of energies ({len(energies_arr)}) does not match number of points ({npts}).")

        # Construct signed provenance record
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
            with h5py.File(self.path, "a") as f:
                # Ensure method group exists
                f.require_group(f"methods/{method_id}")

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

                # Provenance
                self._append(self._ds(f, method_id, "provenance", (), VLEN_STR), np.array([prov_json] * npts, dtype=object))

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
                    except Exception:
                        pass
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
) -> int:
    """
    Merges multiple worker PES shards (campaign_rank_0.h5, campaign_rank_1.h5, ...)
    into a single master PES store atomically.

    Args:
        shard_paths: List of shard file paths
        target_store_path: Destination HDF5 file path
        complex_name: Complex name identifier
        symbols: Elemental symbols

    Returns:
        Total count of points merged into the target store.
    """
    target = PESStore(
        path=target_store_path,
        complex_name=complex_name,
        symbols=symbols,
    )
    total_merged = 0

    for s_path in shard_paths:
        p = Path(s_path)
        if not p.exists():
            logger.warning(f"Shard file not found: {p}")
            continue

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

    logger.info(f"Successfully merged {total_merged} points across {len(shard_paths)} shards into {target_store_path}")
    return total_merged


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


if __name__ == "__main__":
    main()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_core_scheduler.py ---
# cochem_canvas_target: core_engine/cochem_core_scheduler.py
"""
Scheduler module for CoChem-CORE.
Manages scheduling and queuing of computational chemistry tasks.
"""

import atexit
import filelock
import hashlib
import json
import logging
import os
import psutil
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

# 1. Registry Consistency & Air-Gap Enforcement
ARTIFACTS_DIR = Path(os.environ.get("COCHEM_ARTIFACTS", Path.home() / "cochem_artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ARTIFACTS_DIR / "scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CoChem-CoreScheduler")

# 3. Graceful Failure & Subprocess Safety
def sweep_zombie_processes() -> None:
    """Sweep zombie processes using psutil."""
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            if child.status() == psutil.STATUS_ZOMBIE:
                child.wait(timeout=1)
    except psutil.NoSuchProcess:
        pass

atexit.register(sweep_zombie_processes)

def compute_sha256(filepath: Path) -> str:
    """Generate SHA-256 hash for a file."""
    if not filepath.exists():
        return ""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_hpc_filesystem(path: Path) -> bool:
    """Detect if path resides on an HPC distributed filesystem (Lustre, GPFS, NFS, Slurm/PBS)."""
    if "SLURM_JOB_ID" in os.environ or "PBS_JOBID" in os.environ:
        return True
    path_str = str(path.resolve()).lower()
    for marker in ["/lustre", "/gpfs", "nfs", "gluster", "weka"]:
        if marker in path_str:
            return True
    return False


def persist_swarm_state_atomic(
    state_file: Union[str, Path],
    task_id: str,
    entry: Dict[str, Any],
    timeout: float = 10.0,
    max_retries: int = 10,
) -> None:
    """Cross-process atomic persistence for swarm_state.json with HPC scratch staging support."""
    state_file = Path(state_file).resolve()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = state_file.with_name(f"{state_file.name}.lock")
    hpc_mode = is_hpc_filesystem(state_file)

    for attempt in range(max_retries):
        try:
            with filelock.FileLock(str(lock_file), timeout=timeout):
                state_data: Dict[str, Any] = {}
                if state_file.exists():
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            state_data = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        state_data = {}

                state_data[task_id] = entry

                if hpc_mode:
                    scratch_env = os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()
                    stage_dir = Path(scratch_env)
                    tmp_file = stage_dir / f"swarm_state_tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}.json"
                    sidecar_tmp = stage_dir / f"swarm_state_tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}.sha256"
                    try:
                        with open(tmp_file, "w", encoding="utf-8") as f:
                            json.dump(state_data, f, indent=4)
                            f.flush()
                            os.fsync(f.fileno())

                        sha = compute_sha256(tmp_file)
                        sidecar = state_file.with_name(f"{state_file.name}.sha256")
                        sidecar_tmp.write_text(f"{sha}  {state_file.name}\n", encoding="utf-8")

                        shutil.copyfile(str(tmp_file), str(state_file))
                        shutil.copyfile(str(sidecar_tmp), str(sidecar))
                    finally:
                        if tmp_file.exists():
                            try:
                                tmp_file.unlink(missing_ok=True)
                            except OSError:
                                pass
                        if sidecar_tmp.exists():
                            try:
                                sidecar_tmp.unlink(missing_ok=True)
                            except OSError:
                                pass
                else:
                    tmp_file = state_file.with_name(f"{state_file.name}.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")
                    try:
                        with open(tmp_file, "w", encoding="utf-8") as f:
                            json.dump(state_data, f, indent=4)
                            f.flush()
                            os.fsync(f.fileno())

                        replace_done = False
                        for r_try in range(10):
                            try:
                                os.replace(str(tmp_file), str(state_file))
                                replace_done = True
                                break
                            except (PermissionError, OSError):
                                time.sleep(0.005 * (1.5 ** r_try))

                        if not replace_done:
                            shutil.copyfile(str(tmp_file), str(state_file))
                    finally:
                        if tmp_file.exists():
                            try:
                                tmp_file.unlink(missing_ok=True)
                            except OSError:
                                pass
                return
        except (filelock.Timeout, PermissionError, OSError) as exc:
            if attempt == max_retries - 1:
                logger.error("Failed to persist swarm state atomically after %d attempts: %s", max_retries, exc)
                raise
            backoff = 0.05 * (1.5 ** attempt)
            logger.debug(
                "Contention on %s (%s, attempt %d/%d). Retrying in %.3fs",
                state_file,
                type(exc).__name__,
                attempt + 1,
                max_retries,
                backoff,
            )
            time.sleep(backoff)
        except Exception as exc:
            logger.error("Failed to persist swarm state atomically: %s", exc)
            raise


# 2. Rigorous Typing & Linting
class TaskConfig(BaseModel):
    task_id: str
    command: List[str]
    env_vars: Optional[Dict[str, str]] = Field(default_factory=dict)
    timeout_seconds: int = 3600


class TaskResult(BaseModel):
    task_id: str
    status: str
    return_code: Optional[int] = None
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    hashes: Dict[str, str] = Field(default_factory=dict)


class CoreScheduler:
    """
    Schedules and manages computational tasks across the system.
    """
    _state_lock = threading.Lock()

    def __init__(self, max_workers: int = 4, project_root: Optional[Path] = None) -> None:
        """Initialize the scheduler with a thread-safe task queue."""
        self.max_workers = max_workers
        self.project_root = Path(project_root).resolve() if project_root is not None else None
        self.task_queue: queue.Queue[TaskConfig] = queue.Queue()
        self.running_tasks: Dict[str, TaskResult] = {}
        self.is_running = False
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._scheduler_thread: Optional[threading.Thread] = None

    def add_task(self, task: TaskConfig) -> None:
        """Add a task to the scheduling queue."""
        logger.info(f"📥 Adding task {task.task_id} to queue")
        self.task_queue.put(task)


    def _execute_task(self, task: TaskConfig) -> TaskResult:
        """Execute a computational task safely using subprocess."""
        output_file = ARTIFACTS_DIR / f"{task.task_id}.out"
        env = os.environ.copy()
        if task.env_vars:
            env.update(task.env_vars)
        
        result = TaskResult(task_id=task.task_id, status="running")
        self.running_tasks[task.task_id] = result
        
        try:
            with open(output_file, 'w') as out_f:
                process = subprocess.run(
                    task.command,
                    env=env,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    timeout=task.timeout_seconds,
                    check=True
                )
            result.status = "completed"
            result.return_code = process.returncode
            result.output_file = str(output_file)
            
            # Generate hashes for .out and .gbw files if they exist
            result.hashes[str(output_file)] = compute_sha256(output_file)
            gbw_file = ARTIFACTS_DIR / f"{task.task_id}.gbw"
            if gbw_file.exists():
                result.hashes[str(gbw_file)] = compute_sha256(gbw_file)
                
            logger.info(f"✅ Task {task.task_id} completed successfully")
        except subprocess.TimeoutExpired as e:
            result.status = "timeout"
            result.error_message = f"Task timed out after {task.timeout_seconds}s"
            logger.error(f"Task {task.task_id} timeout: {e}")
        except subprocess.CalledProcessError as e:
            result.status = "failed"
            result.return_code = e.returncode
            result.error_message = f"Task failed with exit code {e.returncode}"
            logger.error(f"Task {task.task_id} failed: {e}")
        except FileNotFoundError as e:
            result.status = "failed"
            result.error_message = f"Command not found: {e}"
            logger.error(f"Task {task.task_id} command not found: {e}")
            
        self._update_swarm_state(result)
        return result

    def _update_swarm_state(self, result: TaskResult) -> None:
        """Update the swarm_state.json with task outcome using cross-process atomic persistence."""
        project_root = self.project_root or Path(os.environ.get("COCHEM_PROJECT_ROOT", os.getcwd()))
        state_file = project_root / "swarm_state.json"

        entry = {
            "agent": "cochem-core-scheduler",
            "status": "SUCCESS" if result.status == "completed" else "FAILURE",
            "artifacts": [result.output_file] if result.output_file else [],
            "hashes": result.hashes,
            "error_message": result.error_message,
            "timestamp": time.time(),
        }
        persist_swarm_state_atomic(state_file, result.task_id, entry)

    def schedule_next_task(self) -> Optional[TaskConfig]:
        """Schedule the next available task from thread-safe queue."""
        try:
            task = self.task_queue.get_nowait()
        except queue.Empty:
            return None

        logger.info(f"🕒 Scheduling task {task.task_id}")
        self._executor.submit(self._execute_task, task)
        self.task_queue.task_done()
        return task

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get the status of a specific task."""
        return self.running_tasks.get(task_id)

    def start_scheduling(self) -> None:
        """Start the scheduler."""
        if self.is_running:
            return
        self.is_running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("🔄 Scheduler started")

    def _scheduler_loop(self) -> None:
        """Continuously drain tasks from the queue using event-driven worker saturation."""
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            logger.info(f"🕒 Scheduling task {task.task_id}")
            self._executor.submit(self._execute_task, task)
            self.task_queue.task_done()

            # Worker saturation: immediately drain any pending tasks while running
            while self.is_running:
                try:
                    next_task = self.task_queue.get_nowait()
                    logger.info(f"🕒 Scheduling task {next_task.task_id}")
                    self._executor.submit(self._execute_task, next_task)
                    self.task_queue.task_done()
                except queue.Empty:
                    break

    def stop_scheduling(self) -> None:
        """Stop the scheduler and join background worker threads."""
        self.is_running = False
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=2.0)
            self._scheduler_thread = None
        self._executor.shutdown(wait=True)
        logger.info("🛑 Scheduler stopped")


def main() -> None:
    """Main entry point for the scheduler."""
    logger.info("Starting CoChem-CORE Scheduler")
    # Mocked data and fake workflows have been eradicated. 
    # Real execution driven by incoming requests is expected.
    logger.info("Ready to accept genuine workloads.")


if __name__ == "__main__":
    main()


__all__ = [
    "TaskConfig",
    "TaskResult",
    "CoreScheduler",
    "persist_swarm_state_atomic",
    "is_hpc_filesystem",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_core_subprocess_broker.py ---
#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 3.0 - The Subprocess Broker
Implements: Cross-platform Process Isolation, Win32 Job Objects,
psutil Process Tree Tracking, 10-Second Grace Period Recursive Tree Killing,
atexit Zombie Reaper Daemon, Segfault & Access Violation 256-byte Hex-Dump Sweeper,
OOM Preemption Polling, ZeroMQ Heartbeat Publisher with CurveZMQ / IPC, NUMA-Aware CPU Pinning,
Pre-Flight Disk Quota & 64KB SHA-256 Binary Probe, RAM-Disk Overlay Routing, Directory Lockdown,
and Dead-Man's Switch Daemon Transition.

Provides `safe_subprocess_run`, `register_popen_process`, `unregister_popen_process`,
`get_active_popen_processes`, `cleanup_zombie_processes`, `kill_process_tree`,
`extract_segfault_hex_dump`, `sweep_crash_hex_dump`, `CPUTopologyManager`,
`RAMDiskOverlayManager`, `ZMQHeartbeatManager`, `DeadMansSwitchWatchdog`,
`WindowsJobObject`, `ZombieReaper`, and `SubprocessBroker`.
"""

from __future__ import annotations

import atexit
import ctypes
import hashlib
import json
import logging
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

if platform.system() == "Windows":
    from ctypes import wintypes

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

try:
    from cochem_base.exceptions import DiskQuotaError
except ImportError:
    class DiskQuotaError(OSError):  # type: ignore
        """Fallback definition for DiskQuotaError if cochem_base.exceptions is unavailable."""
        default_error_code = "DISK_QUOTA_EXCEEDED"

        def __init__(
            self,
            message: Optional[Union[str, float]] = None,
            error_code: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
            timestamp: Optional[str] = None,
            *,
            required_gb: Optional[float] = None,
            available_gb: Optional[float] = None,
            path: Optional[Union[str, Path]] = None,
            **kwargs: Any,
        ) -> None:
            self.required_gb: float = float(required_gb) if required_gb is not None else 50.0
            self.available_gb: float = float(available_gb) if available_gb is not None else 0.0
            self.path: Optional[Path] = Path(path) if path is not None else None
            p_str = str(self.path) if self.path is not None else "workspace"
            msg = message if isinstance(message, str) else (
                f"Insufficient scratch disk quota at {p_str}: "
                f"required {self.required_gb:.2f} GB, available {self.available_gb:.2f} GB"
            )
            super().__init__(msg)

from cochem_base.config_loader import (
    get_artifact_dir,
    get_ramdisk_dir,
    get_runtime_dir,
    resolve_mapped_path,
)

try:
    from core_engine.cochem_core_telemetry_logger import TelemetryLogger
except ImportError:
    try:
        from cochem_core_telemetry_logger import TelemetryLogger  # type: ignore
    except ImportError:
        TelemetryLogger = None  # type: ignore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-Broker")

# Global Popen process tracking for zombie sweeping
_GLOBAL_ACTIVE_POPEN_PROCESSES: List[subprocess.Popen] = []
_GLOBAL_TRACKING_LOCK = threading.RLock()

# Comprehensive cross-platform segmentation fault, abort, access violation, and fatal crash return codes
CRITICAL_SEGFAULT_EXIT_CODES = {
    139, 134, 135, 136,                   # POSIX SIGSEGV, SIGABRT, SIGBUS, SIGFPE (128 + signal)
    -11, -6, -7, -8,                       # Subprocess negative signal numbers
    0xC0000005, -1073741819,  # Windows STATUS_ACCESS_VIOLATION (unsigned & signed 32-bit)
    0xC00000FD, -1073741571,  # Windows STATUS_STACK_OVERFLOW
    0xC000001D, -1073741795,  # Windows STATUS_ILLEGAL_INSTRUCTION
    0xC000002E, -1073741778,  # Windows STATUS_DATATYPE_MISALIGNMENT
}


# =====================================================================
# Segfault & Access Violation Hex-Dump Sweeper
# =====================================================================

def is_crash_returncode(code: Optional[int]) -> bool:
    """Evaluates whether an exit code corresponds to a critical crash, segfault, or access violation."""
    if code is None:
        return False
    if code in CRITICAL_SEGFAULT_EXIT_CODES:
        return True
    try:
        unsigned_code = code & 0xFFFFFFFF
        if unsigned_code in {0xC0000005, 0xC00000FD, 0xC000001D, 0xC000002E}:
            return True
    except Exception:
        pass
    return False


def extract_segfault_hex_dump(
    returncode: int,
    stderr_buffer: Union[str, bytes, bytearray, Sequence[str], None],
    max_bytes: int = 256,
) -> Dict[str, Any]:
    """Sweeps terminal stderr buffer upon process segfault or access violation.

    Extracts the final 256 bytes, generates both a canonical formatted hex dump and
    a raw hexadecimal trace string, and structures the diagnostic payload for JSON-L telemetry.
    """
    is_crash = is_crash_returncode(returncode)
    if not is_crash:
        return {
            "is_crash": False,
            "returncode": returncode,
            "crash_type": None,
            "raw_hex": "",
            "formatted_hex_dump": "",
            "byte_count": 0,
            "terminal_stderr_snippet": "",
        }

    raw_bytes: bytes
    if stderr_buffer is None:
        raw_bytes = b"Segmentation fault / Access violation (core dumped)\n"
    elif isinstance(stderr_buffer, (bytes, bytearray)):
        raw_bytes = bytes(stderr_buffer)
    elif isinstance(stderr_buffer, str):
        raw_bytes = stderr_buffer.encode("utf-8", errors="replace")
    elif isinstance(stderr_buffer, (list, tuple)):
        joined_str = "\n".join(str(line) for line in stderr_buffer)
        raw_bytes = joined_str.encode("utf-8", errors="replace")
    else:
        raw_bytes = str(stderr_buffer).encode("utf-8", errors="replace")

    if not raw_bytes:
        raw_bytes = b"Segmentation fault / Access violation (core dumped)\n"

    target_bytes = raw_bytes[-max_bytes:] if len(raw_bytes) >= max_bytes else raw_bytes
    raw_hex = target_bytes.hex()

    # Build canonical formatted hex dump
    lines: List[str] = []
    for offset in range(0, len(target_bytes), 16):
        chunk = target_bytes[offset:offset + 16]
        hex_parts = [f"{b:02x}" for b in chunk]
        hex_str = " ".join(hex_parts)
        ascii_chars = [chr(b) if 32 <= b <= 126 else "." for b in chunk]
        ascii_str = "".join(ascii_chars)
        lines.append(f"{offset:08x}:  {hex_str:<48}  |{ascii_str}|")

    formatted_hex_dump = "\n".join(lines)

    # Classify crash type
    crash_type = "CRITICAL_CRASH"
    if returncode in (-1073741819, 3221225477, 0xC0000005):
        crash_type = "STATUS_ACCESS_VIOLATION"
    elif returncode in (139, -11):
        crash_type = "SIGSEGV"
    elif returncode in (134, -6):
        crash_type = "SIGABRT"
    elif returncode in (-1073741571, 3221225725, 0xC00000FD):
        crash_type = "STATUS_STACK_OVERFLOW"
    elif returncode in (-1073741795, 3221225501, 0xC000001D):
        crash_type = "STATUS_ILLEGAL_INSTRUCTION"
    elif returncode in (-1073741778, 3221225518, 0xC000002E):
        crash_type = "STATUS_DATATYPE_MISALIGNMENT"

    return {
        "is_crash": True,
        "returncode": returncode,
        "crash_type": crash_type,
        "raw_hex": raw_hex,
        "formatted_hex_dump": formatted_hex_dump,
        "byte_count": len(target_bytes),
        "terminal_stderr_snippet": target_bytes.decode("utf-8", errors="replace"),
    }


# Dedicated alias for total naming consistency
sweep_crash_hex_dump = extract_segfault_hex_dump


# =====================================================================
# Win32 Job Object Definitions (Windows-only)
# =====================================================================

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001
PROCESS_ALL_ACCESS = 0x1F0FFF


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
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


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


class WindowsJobObject:
    """Encapsulates a Win32 Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.

    Guarantees OS-level atomic termination of all child and spawned grandchild
    processes when the job object handle is closed or the parent terminates.
    """

    def __init__(self, kill_on_close: bool = True) -> None:
        self.handle: Optional[int] = None
        self._is_windows = platform.system() == "Windows"
        if not self._is_windows:
            return

        try:
            self.handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
            if not self.handle:
                logger.warning("Failed to create Win32 Job Object.")
                return

            if kill_on_close:
                info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                res = ctypes.windll.kernel32.SetInformationJobObject(
                    self.handle,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
                if not res:
                    logger.warning("Failed to set JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE on Job Object.")
        except Exception as exc:
            logger.warning(f"Error initializing WindowsJobObject: {exc}")
            self.handle = None

    def assign_pid(self, pid: int) -> bool:
        """Assigns an active process PID to the Win32 Job Object."""
        if not self._is_windows or not self.handle:
            return False
        try:
            proc_handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_SET_QUOTA | PROCESS_TERMINATE,
                False,
                pid,
            )
            if not proc_handle:
                proc_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not proc_handle:
                return False

            res = ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, proc_handle)
            ctypes.windll.kernel32.CloseHandle(proc_handle)
            return bool(res)
        except Exception as exc:
            logger.debug(f"Failed to assign PID {pid} to Job Object: {exc}")
            return False

    def assign_popen(self, proc: subprocess.Popen) -> bool:
        """Assigns a subprocess.Popen instance to the Win32 Job Object."""
        return self.assign_pid(proc.pid)

    def set_kill_on_close(self, enable: bool = True) -> bool:
        """Dynamically enables or disables JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE on the Job Object."""
        if not self._is_windows or not self.handle:
            return False
        try:
            info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE if enable else 0
            res = ctypes.windll.kernel32.SetInformationJobObject(
                self.handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            return bool(res)
        except Exception as exc:
            logger.debug(f"Failed to update Job Object limit flags: {exc}")
            return False

    def close(self) -> None:
        """Closes the Job Object handle, terminating all assigned processes if kill_on_close is set."""
        if self._is_windows and self.handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            self.handle = None

    def __enter__(self) -> WindowsJobObject:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# =====================================================================
# Process Tracking and Zombie Reaper
# =====================================================================

def get_active_popen_processes() -> List[subprocess.Popen]:
    """Returns a list of currently running subprocess.Popen processes tracked globally."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        _GLOBAL_ACTIVE_POPEN_PROCESSES = [p for p in _GLOBAL_ACTIVE_POPEN_PROCESSES if p.poll() is None]
        return list(_GLOBAL_ACTIVE_POPEN_PROCESSES)


def register_popen_process(proc: subprocess.Popen) -> None:
    """Registers a Popen child process for automatic zombie cleanup on script exit."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        _GLOBAL_ACTIVE_POPEN_PROCESSES = [p for p in _GLOBAL_ACTIVE_POPEN_PROCESSES if p.poll() is None]
        if proc.poll() is None and proc not in _GLOBAL_ACTIVE_POPEN_PROCESSES:
            _GLOBAL_ACTIVE_POPEN_PROCESSES.append(proc)


def unregister_popen_process(proc: subprocess.Popen) -> None:
    """Unregisters a Popen child process from global tracking."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        if proc in _GLOBAL_ACTIVE_POPEN_PROCESSES:
            _GLOBAL_ACTIVE_POPEN_PROCESSES.remove(proc)


def kill_process_tree(pid: int, timeout: float = 10.0) -> None:
    """Terminates a process and all of its recursive child processes.

    Mathematically guarantees no orphaned process trees survive:
    1. Uses psutil recursive tree discovery (parent.children(recursive=True)).
    2. Sends graceful terminate signal (.terminate()) to all children and parent.
    3. Waits for a 10-second grace period (allowing .gbw caches to dump cleanly).
    4. Escalates to hard kill (.kill()) if any process remains alive after timeout.
    5. Performs final reap wait.
    """
    if HAS_PSUTIL:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                parent.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            procs_to_wait = [p for p in children + [parent] if psutil.pid_exists(p.pid)]
            if procs_to_wait:
                gone, alive = psutil.wait_procs(procs_to_wait, timeout=timeout)
                if alive:
                    for p in alive:
                        try:
                            p.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    # Final reap confirmation
                    psutil.wait_procs(alive, timeout=3.0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except (ProcessLookupError, PermissionError, OSError):
            pass
    else:
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(min(timeout, 0.5))
                    sig_kill = getattr(signal, "SIGKILL", signal.SIGTERM)
                    os.kill(pid, sig_kill)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
        except (ProcessLookupError, PermissionError, OSError):
            pass


def cleanup_zombie_processes() -> int:
    """Atexit / Signal hook to terminate any dangling Popen child process trees."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    count = 0
    with _GLOBAL_TRACKING_LOCK:
        active_list = list(_GLOBAL_ACTIVE_POPEN_PROCESSES)
        _GLOBAL_ACTIVE_POPEN_PROCESSES.clear()

    for proc in active_list:
        if proc.poll() is None:
            try:
                pid = proc.pid
                kill_process_tree(pid, timeout=10.0)
                count += 1
                logger.info(f"Terminated background child process PID {pid}")
            except (ProcessLookupError, PermissionError, OSError) as e:
                logger.warning(f"Failed to terminate process PID {proc.pid}: {e}")
    return count


class ZombieReaper:
    """Global and instance zombie sweeper with signal handlers and Win32 Job Object integration."""

    @staticmethod
    def reap_all() -> int:
        """Invokes global process cleanup."""
        return cleanup_zombie_processes()

    @staticmethod
    def reap_pid(pid: int, timeout: float = 10.0) -> None:
        """Kills a specific process tree with 10-second grace period."""
        kill_process_tree(pid, timeout=timeout)


def _signal_cleanup_handler(signum: int, frame: Any) -> None:
    logger.info(f"Received signal {signum}. Triggering zombie reaper cleanup...")
    cleanup_zombie_processes()
    sys.exit(128 + signum)


def _register_signal_handlers() -> None:
    try:
        if threading.current_thread() is threading.main_thread():
            for sig_name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
                if hasattr(signal, sig_name):
                    sig = getattr(signal, sig_name)
                    try:
                        signal.signal(sig, _signal_cleanup_handler)
                    except (ValueError, OSError, RuntimeError):
                        pass
    except Exception:
        pass


atexit.register(cleanup_zombie_processes)
_register_signal_handlers()


# =====================================================================
# NUMA-Aware Hardware Thread-Pinning & Oversubscription Prevention
# =====================================================================

def detect_cpu_topology() -> Dict[str, Any]:
    """Evaluates physical host CPU topology (cores, sockets, NUMA nodes).

    Returns a structured dictionary containing logical cores, physical cores,
    sockets, NUMA nodes with mapped CPU core IDs, and multi-threading ratio.
    """
    logical_cores = psutil.cpu_count(logical=True) if HAS_PSUTIL else (os.cpu_count() or 1)
    physical_cores = (psutil.cpu_count(logical=False) if HAS_PSUTIL else None) or logical_cores

    numa_nodes: List[Dict[str, Any]] = []
    sockets = 1

    if platform.system() == "Linux":
        node_dir = Path("/sys/devices/system/node")
        if node_dir.is_dir():
            for entry in sorted(node_dir.glob("node[0-9]*")):
                try:
                    node_id = int(entry.name.replace("node", ""))
                    cpulist_file = entry / "cpulist"
                    cpus: List[int] = []
                    if cpulist_file.exists():
                        raw = cpulist_file.read_text(encoding="utf-8").strip()
                        for part in raw.split(","):
                            if "-" in part:
                                start, end = map(int, part.split("-"))
                                cpus.extend(range(start, end + 1))
                            elif part.isdigit():
                                cpus.append(int(part))
                    numa_nodes.append({"node_id": node_id, "cpus": cpus})
                except Exception:
                    pass
            if numa_nodes:
                sockets = max(1, len(numa_nodes))

    elif platform.system() == "Windows":
        try:
            highest_node = wintypes.ULONG()
            if ctypes.windll.kernel32.GetNumaHighestNodeNumber(ctypes.byref(highest_node)):
                total_nodes = highest_node.value + 1
                sockets = max(1, total_nodes)
                cores_per_node = max(1, logical_cores // total_nodes)
                for nid in range(total_nodes):
                    node_cpus = list(range(nid * cores_per_node, min(logical_cores, (nid + 1) * cores_per_node)))
                    numa_nodes.append({"node_id": nid, "cpus": node_cpus})
        except Exception:
            pass

    if not numa_nodes:
        numa_nodes.append({"node_id": 0, "cpus": list(range(logical_cores))})
        sockets = 1

    return {
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
        "sockets": sockets,
        "numa_nodes": numa_nodes,
        "is_numa": len(numa_nodes) > 1,
        "threads_per_core": max(1, logical_cores // max(1, physical_cores)),
    }


class CPUTopologyManager:
    """Evaluates physical host topology (cores, sockets, NUMA nodes) and manages core allocations."""

    def __init__(self, topology: Optional[Dict[str, Any]] = None) -> None:
        self.topology = topology or detect_cpu_topology()
        self.logical_cores: int = self.topology.get("logical_cores", 1)
        self.physical_cores: int = self.topology.get("physical_cores", 1)
        self.sockets: int = self.topology.get("sockets", 1)
        self.numa_nodes: List[Dict[str, Any]] = self.topology.get("numa_nodes", [])
        self.is_numa: bool = self.topology.get("is_numa", False)

    def get_topology(self) -> Dict[str, Any]:
        """Returns cached CPU topology specification."""
        return dict(self.topology)

    def get_numa_node_for_core(self, core_id: int) -> int:
        """Determines the NUMA node index for a given CPU core."""
        for node in self.numa_nodes:
            if core_id in node.get("cpus", []):
                return int(node.get("node_id", 0))
        return 0

    def allocate_cores(self, count: int, numa_node: Optional[int] = None) -> List[int]:
        """Allocates contiguous CPU cores respecting NUMA node boundaries."""
        if numa_node is not None:
            for node in self.numa_nodes:
                if node.get("node_id") == numa_node:
                    cpus: List[int] = list(node.get("cpus", []))
                    return cpus[:count] if count <= len(cpus) else cpus
        all_cpus: List[int] = [c for node in self.numa_nodes for c in node.get("cpus", [])]
        if not all_cpus:
            all_cpus = list(range(self.logical_cores))
        return all_cpus[:count]

    def pin_process(self, pid: int, cpu_cores: Optional[List[int]] = None) -> bool:
        """Pins an active process to designated CPU cores."""
        return enforce_cpu_affinity(pid, cpu_cores)

    def calculate_thread_affinity(self, rank: int, threads_per_rank: int) -> List[int]:
        """Calculates thread pinning offsets for multi-rank execution."""
        start_core = (rank * threads_per_rank) % max(1, self.logical_cores)
        return [(start_core + i) % self.logical_cores for i in range(threads_per_rank)]


def enforce_cpu_affinity(pid: int, cpu_cores: Optional[List[int]] = None) -> bool:
    """Pins a process to specified CPU cores using OS-level affinity control.

    Gracefully handles macOS Darwin (which does not support process CPU affinity)
    and Windows processor group constraints without raising unhandled exceptions.
    """
    if cpu_cores is None or len(cpu_cores) == 0:
        return True
    if not HAS_PSUTIL:
        logger.warning("psutil unavailable; cannot enforce CPU affinity.")
        return False
    try:
        proc = psutil.Process(pid)
        proc.cpu_affinity(cpu_cores)
        logger.info(f"Pinned PID {pid} to CPU cores {cpu_cores} [M]")
        return True
    except (AttributeError, NotImplementedError):
        logger.debug(f"CPU affinity control is not supported on this platform ({platform.system()}).")
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError) as e:
        logger.warning(f"Failed to set CPU affinity on PID {pid}: {e}")
        return False


def build_thread_affinity_env(
    cores: Optional[Sequence[int]] = None,
    is_scout: bool = False,
    num_mps_ranks: Optional[int] = None,
    mps_mem_limit_mb: Optional[int] = None,
    base_env: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Constructs an environment dictionary with proactive OpenMP/MKL thread affinity
    and NVIDIA Multi-Process Service (MPS) mediation settings.

    Mandated by Suggestion #19 and Method Matrix §8A.1 Scout-and-Anchor policy:
    - Pre-injects GOMP_CPU_AFFINITY, KMP_AFFINITY, OMP_PLACES, OMP_PROC_BIND.
    - Zero CUDA-Locking MPS parameters: CUDA_MPS_ACTIVE_THREAD_PERCENTAGE,
      CUDA_MPS_PINNED_DEVICE_MEM_LIMIT.
    """
    env = dict(base_env if base_env is not None else os.environ)

    if cores is not None and len(cores) > 0:
        core_list = [int(c) for c in cores]
        core_str = ",".join(str(c) for c in core_list)
        env["GOMP_CPU_AFFINITY"] = core_str
        env["KMP_AFFINITY"] = f"explicit,proclist=[{core_str}],granularity=fine"
        env["OMP_PLACES"] = ",".join(f"{{{c}}}" for c in core_list)
        env["OMP_PROC_BIND"] = "close"

    if num_mps_ranks is not None and num_mps_ranks > 0:
        pct = max(1, int(100 / num_mps_ranks))
        env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(pct)

    if mps_mem_limit_mb is not None and mps_mem_limit_mb > 0:
        env["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = f"{int(mps_mem_limit_mb)}M"

    return env


def detect_mpi_environment(
    env: Optional[Dict[str, str]] = None,
    cmd: Optional[Union[str, List[str]]] = None,
) -> bool:
    """Detects if an OpenMPI, MPICH, SLURM, or ORCA multi-rank MPI environment is active."""
    target_env = env if env is not None else os.environ

    mpi_size_vars = ("OMPI_COMM_WORLD_SIZE", "PMI_SIZE", "SLURM_NTASKS", "MPI_SIZE", "OMPI_UNIVERSE_SIZE", "MV2_COMM_WORLD_SIZE")
    for var in mpi_size_vars:
        val = target_env.get(var)
        if val is not None:
            try:
                if int(val) > 1:
                    return True
            except ValueError:
                pass

    mpi_rank_indicators = ("MPI_LOCALRANKID", "OMPI_COMM_WORLD_RANK", "PMI_RANK", "PMIX_RANK", "SLURM_PROCID")
    for var in mpi_rank_indicators:
        if var in target_env:
            return True

    mpirun_in_use = target_env.get("MPIRUN_IN_USE", "").strip().lower()
    if mpirun_in_use in ("1", "true", "yes"):
        return True

    if cmd is not None:
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        cmd_lower = cmd_str.lower()
        mpi_executables = ("mpirun", "mpiexec", "orterun", "srun", "aprun", "oshrun")
        for mpi_bin in mpi_executables:
            parts = cmd_lower.split()
            if mpi_bin in parts or any(part.endswith(f"/{mpi_bin}") or part.endswith(f"\\{mpi_bin}") or part.endswith(f"/{mpi_bin}.exe") or part.endswith(f"\\{mpi_bin}.exe") for part in parts):
                return True
        if "%pal" in cmd_lower or "nprocs" in cmd_lower:
            return True

    return False


def sanitize_mpi_environment(
    env: Optional[Dict[str, str]] = None,
    force_single_thread: bool = False,
    cmd: Optional[Union[str, List[str]]] = None,
) -> Dict[str, str]:
    """Sanitizes environment variables for MPI workloads to prevent core oversubscription.

    When multi-rank MPI execution is detected or force_single_thread is True, forces:
    OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
    VECLIB_MAXIMUM_THREADS="1", NUMEXPR_NUM_THREADS="1", BLIS_NUM_THREADS="1".
    """
    target_env = dict(env) if env is not None else os.environ.copy()

    if force_single_thread or detect_mpi_environment(target_env, cmd=cmd):
        target_env["OMP_NUM_THREADS"] = "1"
        target_env["MKL_NUM_THREADS"] = "1"
        target_env["OPENBLAS_NUM_THREADS"] = "1"
        target_env["VECLIB_MAXIMUM_THREADS"] = "1"
        target_env["NUMEXPR_NUM_THREADS"] = "1"
        target_env["BLIS_NUM_THREADS"] = "1"
        logger.info("Sanitized MPI environment: forced OMP/MKL/OPENBLAS/VECLIB/NUMEXPR/BLIS=1 to prevent oversubscription.")

    return target_env


# =====================================================================
# Pre-Flight Disk Quota, 64KB SHA-256 Probe & RAM-Disk Routing
# =====================================================================

def lock_directory_permissions(target_dir: Union[str, Path]) -> bool:
    """Applies strict directory access controls: chmod 0o700 on POSIX or icacls on Windows."""
    path = Path(target_dir).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"Could not create directory {path} to lock permissions: {exc}")
            return False

    if platform.system() != "Windows":
        try:
            os.chmod(str(path), 0o700)
            return True
        except OSError as exc:
            logger.warning(f"Failed to chmod 0o700 on {path}: {exc}")
            return False
    else:
        try:
            username = os.environ.get("USERNAME") or os.environ.get("USER") or "Everyone"
            cmd = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(OI)(CI)F"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5.0)
            return res.returncode == 0
        except Exception as exc:
            logger.warning(f"Failed to lock Windows ACLs on {path}: {exc}")
            return False


def verify_scratch_quota_and_io(target_dir: Union[str, Path], required_gb: float = 50.0) -> bool:
    """Executes pre-flight storage quota assertion and 64KB unbuffered SHA-256 binary probe.

    Raises DiskQuotaError if available storage is less than required_gb.
    Raises IOError if binary readback SHA-256 checksum fails.
    """
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    usage = shutil.disk_usage(str(target_path))
    free_gb = usage.free / (1024 ** 3)

    if free_gb < required_gb:
        logger.error(f"Insufficient scratch disk space at {target_path}: {free_gb:.2f} GB free, {required_gb:.2f} GB required.")
        raise DiskQuotaError(required_gb=required_gb, available_gb=free_gb, path=target_path)

    probe_file = target_path / f".cochem_io_probe_{os.getpid()}_{int(time.time() * 1000)}.tmp"
    probe_data = os.urandom(64 * 1024)  # 64 KB physical binary probe
    expected_hash = hashlib.sha256(probe_data).hexdigest()

    try:
        with open(probe_file, "wb") as f:
            f.write(probe_data)
            f.flush()
            os.fsync(f.fileno())

        with open(probe_file, "rb") as f:
            read_back_data = f.read()

        read_hash = hashlib.sha256(read_back_data).hexdigest()

        if expected_hash != read_hash:
            raise IOError(f"Scratch I/O integrity probe failed: SHA-256 mismatch at {target_path}")

        logger.info(f"Verified scratch quota and I/O at {target_path} ({free_gb:.2f} GB free, {required_gb:.2f} GB required) [M]")
        return True
    except (OSError, IOError) as exc:
        logger.error(f"Scratch I/O verification error at {target_path}: {exc}")
        raise
    finally:
        probe_file.unlink(missing_ok=True)


def verify_scratch_io(scratch_dir: Union[str, Path], required_mb: int = 100) -> bool:
    """Backward-compatible scratch I/O verification wrapper."""
    required_gb = required_mb / 1024.0
    try:
        return verify_scratch_quota_and_io(scratch_dir, required_gb=required_gb)
    except (DiskQuotaError, IOError, OSError):
        return False


class RAMDiskOverlayManager:
    """Manages high-speed RAM-disk execution overlays and quantum artifact provenance synchronization."""

    def __init__(self, threshold_ram_gb: float = 128.0) -> None:
        self.threshold_ram_gb = threshold_ram_gb

    def get_total_host_ram_gb(self) -> float:
        """Returns physical host memory in Gigabytes."""
        if HAS_PSUTIL:
            total_bytes: float = float(psutil.virtual_memory().total)
            return float(total_bytes / (1024 ** 3))
        return 0.0

    def is_ramdisk_eligible(self, min_ram_gb: Optional[float] = None) -> bool:
        """Checks if host RAM exceeds the minimum provisioning threshold."""
        threshold = min_ram_gb if min_ram_gb is not None else self.threshold_ram_gb
        return self.get_total_host_ram_gb() >= threshold

    def provision_overlay(
        self,
        job_name: str,
        required_gb: float = 4.0,
        min_ram_gb: Optional[float] = None,
        fallback_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Autonomously provisions a high-speed RAM-disk overlay directory if eligible."""
        threshold = min_ram_gb if min_ram_gb is not None else self.threshold_ram_gb
        target_fallback = Path(fallback_dir).resolve() if fallback_dir is not None else (get_artifact_dir() / "Scratch")

        if self.is_ramdisk_eligible(threshold):
            ramdisk_path = get_ramdisk_dir()
            if ramdisk_path is not None and ramdisk_path.is_dir():
                try:
                    free_gb = shutil.disk_usage(str(ramdisk_path)).free / (1024 ** 3)
                    if free_gb > (required_gb * 1.2):
                        job_overlay_dir = ramdisk_path / f"cochem_{job_name}_{int(time.time() * 1000)}"
                        job_overlay_dir.mkdir(parents=True, exist_ok=True)
                        lock_directory_permissions(job_overlay_dir)
                        logger.info(
                            f"Provisioned RAM-disk execution directory: {job_overlay_dir} "
                            f"(Host RAM: {self.get_total_host_ram_gb():.1f} GB >= {threshold} GB)"
                        )
                        return job_overlay_dir
                except Exception as exc:
                    logger.debug(f"RAM-disk overlay check skipped: {exc}")

        target_fallback.mkdir(parents=True, exist_ok=True)
        lock_directory_permissions(target_fallback)
        return target_fallback

    def sync_and_cleanup(self, overlay_path: Path, permanent_path: Path) -> Dict[str, str]:
        """Synchronizes quantum artifacts from overlay back to permanent workspace and deletes overlay."""
        permanent_path.mkdir(parents=True, exist_ok=True)
        hashes: Dict[str, str] = {}

        if overlay_path != permanent_path and overlay_path.exists():
            logger.info(f"Syncing artifacts from RAM-disk {overlay_path} to permanent workspace {permanent_path}...")
            for item in overlay_path.iterdir():
                dest_path = permanent_path / item.name
                try:
                    if item.is_dir():
                        shutil.copytree(item, dest_path, dirs_exist_ok=True)
                    elif item.is_file():
                        shutil.copy2(item, dest_path)
                except Exception as exc:
                    logger.warning(f"Error copying artifact {item} to {dest_path}: {exc}")

            hashes = self.hash_artifacts(permanent_path)
            shutil.rmtree(overlay_path, ignore_errors=True)
        else:
            hashes = self.hash_artifacts(permanent_path)

        return hashes

    @staticmethod
    def hash_artifacts(target_dir: Path) -> Dict[str, str]:
        """Generates SHA-256 checksums for quantum chemistry artifacts."""
        hashes: Dict[str, str] = {}
        if not target_dir.exists():
            return hashes

        valid_suffixes = {".out", ".gbw", ".xyz", ".log", ".dat", ".json", ".h5", ".molden", ".cube"}
        for file_path in sorted(target_dir.iterdir()):
            if file_path.is_file() and (file_path.suffix in valid_suffixes or file_path.name.endswith(".out")):
                try:
                    hasher = hashlib.sha256()
                    with open(file_path, "rb") as f:
                        while chunk := f.read(65536):
                            hasher.update(chunk)
                    file_hash = hasher.hexdigest()
                    hashes[file_path.name] = file_hash
                    logger.info(f"Generated SHA-256 hash for {file_path.name}: {file_hash} [M]")
                except OSError as err:
                    logger.warning(f"Failed to hash {file_path.name}: {err}")
        return hashes


# =====================================================================
# ZeroMQ Heartbeat Integration & Dead-Man's Switch Watchdog
# =====================================================================

class ZMQHeartbeatManager:
    """ZeroMQ heartbeat publisher with CurveZMQ security on Windows and IPC on POSIX."""

    def __init__(self, job_id: str = "cochem_job") -> None:
        self.job_id = job_id
        self.endpoint: Optional[str] = None
        self.server_public: Optional[bytes] = None
        self.server_secret: Optional[bytes] = None
        self.client_public: Optional[bytes] = None
        self.client_secret: Optional[bytes] = None
        self.curve_enabled: bool = False

        self._context: Optional[Any] = None
        self._socket: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(
        self,
        endpoint: Optional[str] = None,
        interval_sec: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        use_curve: bool = True,
    ) -> str:
        """Binds and starts the background heartbeat publisher."""
        if not HAS_ZMQ:
            logger.warning("ZeroMQ (pyzmq) not available. Heartbeat publisher disabled.")
            return ""

        self.stop()
        self._stop_event.clear()

        try:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.PUB)

            if endpoint is None:
                if platform.system() == "Windows":
                    if use_curve and hasattr(zmq, "curve_keypair"):
                        try:
                            self.server_public, self.server_secret = zmq.curve_keypair()
                            self.client_public, self.client_secret = zmq.curve_keypair()
                            self._socket.curve_secretkey = self.server_secret
                            self._socket.curve_publickey = self.server_public
                            self._socket.curve_server = True
                            self.curve_enabled = True
                        except Exception as curve_err:
                            logger.debug(f"CurveZMQ initialization fallback: {curve_err}")
                            self.curve_enabled = False

                    port = self._socket.bind_to_random_port("tcp://127.0.0.1")
                    self.endpoint = f"tcp://127.0.0.1:{port}"
                else:
                    try:
                        ipc_dir = get_runtime_dir() / "ipc"
                    except Exception:
                        ipc_dir = Path(tempfile.gettempdir()) / "cochem_ipc"
                    ipc_dir.mkdir(parents=True, exist_ok=True)
                    lock_directory_permissions(ipc_dir)
                    ipc_path = ipc_dir / f"cochem_heartbeat_{self.job_id}.ipc"
                    self.endpoint = f"ipc://{ipc_path}"
                    try:
                        self._socket.bind(self.endpoint)
                    except Exception:
                        port = self._socket.bind_to_random_port("tcp://127.0.0.1")
                        self.endpoint = f"tcp://127.0.0.1:{port}"
            else:
                if endpoint.endswith(":*"):
                    base = endpoint[:-2]
                    port = self._socket.bind_to_random_port(base)
                    self.endpoint = f"{base}:{port}"
                else:
                    self.endpoint = endpoint
                    self._socket.bind(self.endpoint)

        except Exception as err:
            logger.error(f"Failed to bind ZeroMQ heartbeat publisher socket: {err}", exc_info=True)
            self.stop()
            return ""

        def heartbeat_worker() -> None:
            while not self._stop_event.is_set():
                alive_payload: Dict[str, Any] = {
                    "status": "alive",
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                    "job_id": self.job_id,
                    "metadata": metadata or {},
                }
                try:
                    if self._socket is not None:
                        self._socket.send_multipart([
                            b"heartbeat",
                            json.dumps(alive_payload).encode("utf-8"),
                        ])
                except Exception as ex:
                    logger.debug(f"ZeroMQ heartbeat send error: {ex}")
                self._stop_event.wait(interval_sec)

        self._thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self._thread.start()
        logger.info(f"ZeroMQ heartbeat publisher active on {self.endpoint} (Curve: {self.curve_enabled}) [M]")
        return str(self.endpoint)

    def publish_heartbeat(self, status: str = "alive", extra: Optional[Dict[str, Any]] = None) -> None:
        """Publishes an immediate manual heartbeat event."""
        if not HAS_ZMQ or self._socket is None:
            return
        payload = {
            "status": status,
            "timestamp": time.time(),
            "pid": os.getpid(),
            "job_id": self.job_id,
            "metadata": extra or {},
        }
        try:
            self._socket.send_multipart([
                b"heartbeat",
                json.dumps(payload).encode("utf-8"),
            ])
        except Exception as ex:
            logger.debug(f"Manual heartbeat publish error: {ex}")

    def stop(self) -> None:
        """Stops the heartbeat publisher thread and destroys sockets cleanly."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._socket is not None:
            try:
                self._socket.close(linger=0)
            except Exception:
                pass
            self._socket = None
        if self._context is not None:
            try:
                self._context.term()
            except Exception:
                pass
            self._context = None

    def __enter__(self) -> ZMQHeartbeatManager:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


class DeadMansSwitchWatchdog:
    """Monitors child process responsiveness via timestamp pings."""

    def __init__(
        self,
        job_id: str,
        proc: subprocess.Popen,
        timeout: float = 60.0,
        check_interval: float = 2.0,
        on_timeout: str = "daemonize",
    ) -> None:
        self.job_id = job_id
        self.proc = proc
        self.timeout = timeout
        self.check_interval = check_interval
        self.on_timeout = on_timeout
        self.last_ping: float = time.time()
        self.is_daemonized: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def ping(self) -> None:
        """Resets the dead-man's switch expiration timer."""
        self.last_ping = time.time()

    def start(self) -> None:
        """Starts the background watchdog monitoring loop."""
        self._stop_event.clear()
        self.last_ping = time.time()

        def watchdog_loop() -> None:
            while not self._stop_event.is_set():
                if self.proc.poll() is not None:
                    break
                elapsed = time.time() - self.last_ping
                if elapsed > self.timeout:
                    logger.warning(
                        f"Dead-man's switch expired for job '{self.job_id}' "
                        f"(no activity for {elapsed:.1f}s > {self.timeout:.1f}s)."
                    )
                    if self.on_timeout == "daemonize":
                        self.is_daemonized = True
                        unregister_popen_process(self.proc)
                        logger.info(
                            f"Orchestrator safely detached; child PID {self.proc.pid} "
                            f"transitioned to active autonomous daemon [M]"
                        )
                    elif self.on_timeout == "kill":
                        logger.error(f"Terminating unresponsive job '{self.job_id}' (PID {self.proc.pid}).")
                        kill_process_tree(self.proc.pid, timeout=10.0)
                    break
                self._stop_event.wait(self.check_interval)

        self._thread = threading.Thread(target=watchdog_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the watchdog thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def __enter__(self) -> DeadMansSwitchWatchdog:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


# =====================================================================
# Safe Subprocess Execution
# =====================================================================

def safe_subprocess_run(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    timeout: float = 300.0,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None,
    cpu_affinity: Optional[List[int]] = None,
    required_disk_gb: Optional[float] = None,
    sanitize_mpi: bool = True,
    use_job_object: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Executes a subprocess safely with cross-platform process isolation.

    Relies on robust tracking of process trees via `psutil` (avoiding POSIX-exclusive os.setsid),
    Win32 Job Object binding on Windows, pre-flight disk quota assertion, hardware CPU affinity pinning,
    10-second grace period recursive tree termination upon timeout, and Segfault & Access Violation
    256-byte stderr hex-dump extraction.
    """
    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            raise FileNotFoundError(f"Subprocess working directory does not exist: {cwd_path}")
        cwd_str = str(cwd_path)
    else:
        cwd_str = None
        cwd_path = Path.cwd()

    if required_disk_gb is not None and required_disk_gb > 0:
        verify_scratch_quota_and_io(cwd_path, required_gb=required_disk_gb)

    parsed_cmd: Union[List[str], str]
    if isinstance(cmd, str) and not kwargs.get("shell", False):
        if platform.system() == "Windows":
            parsed_cmd = cmd
        else:
            parsed_cmd = shlex.split(cmd, posix=True)
    else:
        parsed_cmd = cmd

    target_env = env.copy() if env is not None else os.environ.copy()
    if sanitize_mpi:
        target_env = sanitize_mpi_environment(target_env, cmd=parsed_cmd)

    if cpu_affinity is not None:
        target_env = build_thread_affinity_env(cores=cpu_affinity, base_env=target_env)

    popen_args: Dict[str, Any] = {
        "cwd": cwd_str,
        "env": target_env,
        "text": text,
        **kwargs,
    }
    if capture_output:
        popen_args["stdout"] = subprocess.PIPE
        popen_args["stderr"] = subprocess.PIPE

    job_obj = WindowsJobObject() if (use_job_object and platform.system() == "Windows") else None

    if job_obj is not None and platform.system() == "Windows":
        CREATE_SUSPENDED = 0x00000004
        popen_args["creationflags"] = popen_args.get("creationflags", 0) | CREATE_SUSPENDED
        proc = subprocess.Popen(parsed_cmd, **popen_args)
        register_popen_process(proc)
        job_obj.assign_popen(proc)
        try:
            ctypes.windll.ntdll.NtResumeProcess(int(proc._handle))
        except Exception:
            pass
    else:
        if platform.system() != "Windows":
            popen_args.setdefault("start_new_session", True)
            if platform.system() == "Linux":
                def _posix_pdeathsig() -> None:
                    try:
                        import ctypes
                        libc = ctypes.CDLL("libc.so.6")
                        PR_SET_PDEATHSIG = 1
                        SIGKILL = 9
                        libc.prctl(PR_SET_PDEATHSIG, SIGKILL)
                    except Exception:
                        pass
                popen_args.setdefault("preexec_fn", _posix_pdeathsig)

        proc = subprocess.Popen(parsed_cmd, **popen_args)
        register_popen_process(proc)

    if cpu_affinity is not None:
        enforce_cpu_affinity(proc.pid, cpu_affinity)

    stdout_data: Any = ""
    stderr_data: Any = ""

    try:
        stdout_data, stderr_data = proc.communicate(timeout=timeout)
        ret = proc.returncode

        crash_payload = extract_segfault_hex_dump(ret, stderr_data)
        if crash_payload.get("is_crash"):
            logger.error(
                f"Critical process crash detected ({crash_payload.get('crash_type')}, code {ret}):\n"
                f"{crash_payload.get('formatted_hex_dump')}"
            )

        completed = subprocess.CompletedProcess(args=cmd, returncode=ret, stdout=stdout_data, stderr=stderr_data)
        completed.crash_payload = crash_payload  # type: ignore[attr-defined]
        completed.hex_dump = crash_payload.get("raw_hex", "")  # type: ignore[attr-defined]

        if check and ret != 0:
            err = subprocess.CalledProcessError(ret, cmd, output=stdout_data, stderr=stderr_data)
            err.crash_payload = crash_payload  # type: ignore[attr-defined]
            err.hex_dump = crash_payload.get("raw_hex", "")  # type: ignore[attr-defined]
            raise err

        return completed
    except subprocess.TimeoutExpired:
        kill_process_tree(proc.pid, timeout=10.0)
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            pass
        logger.error(f"Subprocess '{cmd}' timed out after {timeout} seconds.")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess '{cmd}' failed with returncode {e.returncode}: {e.stderr}")
        raise
    except OSError as e:
        logger.error(f"Subprocess execution error for '{cmd}': {e}")
        raise
    finally:
        unregister_popen_process(proc)
        if job_obj is not None:
            job_obj.close()


# =====================================================================
# Subprocess Broker Core Engine
# =====================================================================

class SubprocessBroker:
    """Subprocess execution manager for computational quantum chemistry workloads.

    Handles cross-platform process lifecycles, memory safety, heartbeats, dead-man's switch watchdogs,
    RAM-disk overlays, CPU affinity pinning, crash hex-dump telemetry, and artifact provenance hashing.
    """

    def __init__(
        self,
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        memory_limit_gb: float = 8.0,
        total_ram_threshold_gb: float = 128.0,
    ) -> None:
        env_scratch = (
            os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TMPDIR")
            or os.environ.get("TEMP")
        )
        if env_scratch:
            default_work_dir = Path(env_scratch) / "cochem_scratch"
        else:
            default_work_dir = get_artifact_dir() / "Scratch"
        self.cwd = resolve_mapped_path(cwd, default_work_dir) if cwd is not None else default_work_dir
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.env = env if env is not None else os.environ.copy()
        self.memory_limit_bytes = memory_limit_gb * (1024 ** 3)
        self.total_ram_threshold_gb = total_ram_threshold_gb

        self.topology_manager = CPUTopologyManager()
        self.ramdisk_manager = RAMDiskOverlayManager(threshold_ram_gb=total_ram_threshold_gb)

        if TelemetryLogger is not None:
            self.telemetry: Optional[Any] = TelemetryLogger()
        else:
            self.telemetry = None

        self.active_processes: List[subprocess.Popen] = []
        self._lock = threading.RLock()

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._zmq_context: Optional[Any] = None
        self._zmq_socket: Optional[Any] = None
        self._zmq_thread: Optional[threading.Thread] = None
        self._zmq_stop_event = threading.Event()

    def __enter__(self) -> SubprocessBroker:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def shutdown(self) -> None:
        """Gracefully shuts down broker threads and terminates active subprocesses."""
        self.stop_oom_monitor()
        self.stop_zmq_heartbeat()
        self.execute_zombie_reaper()

    def close(self) -> None:
        """Closes the broker, stopping monitors and cleaning up process trees."""
        self.shutdown()

    def verify_scratch_io(self, target_dir: Optional[Union[str, Path]] = None, required_mb: int = 100) -> bool:
        """Verifies scratch directory I/O readiness."""
        path = target_dir or self.cwd
        return verify_scratch_io(path, required_mb=required_mb)

    def verify_scratch_quota_and_io(self, target_dir: Optional[Union[str, Path]] = None, required_gb: float = 50.0) -> bool:
        """Verifies scratch quota and binary readback probe."""
        path = target_dir or self.cwd
        return verify_scratch_quota_and_io(path, required_gb=required_gb)

    def _allocate_scratch_space(self, job_name: str, required_mb: int = 4000) -> Path:
        """Provisions an isolated scratch directory on high-speed RAM-disk or NVMe fallback."""
        return self.ramdisk_manager.provision_overlay(
            job_name=job_name,
            required_gb=max(0.01, required_mb / 1024.0),
            min_ram_gb=self.total_ram_threshold_gb,
            fallback_dir=self.cwd,
        )

    def start_oom_monitor(self, check_interval: float = 1.0, threshold_mb: Optional[float] = None) -> None:
        """Spawns a background thread that polls RSS memory of active process trees."""
        if not HAS_PSUTIL:
            logger.warning("psutil unavailable. OOM preemption monitor disabled.")
            return

        self.stop_oom_monitor()
        self._stop_event.clear()

        limit_bytes = (threshold_mb * (1024 ** 2)) if threshold_mb is not None else self.memory_limit_bytes

        def monitor_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    with self._lock:
                        active_pids = [p.pid for p in self.active_processes if p.poll() is None]
                    if active_pids:
                        total_rss = 0
                        for pid in active_pids:
                            try:
                                proc = psutil.Process(pid)
                                total_rss += proc.memory_info().rss
                                for child in proc.children(recursive=True):
                                    total_rss += child.memory_info().rss
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        if total_rss > limit_bytes:
                            logger.error(
                                f"Broker process tree memory exceeded limit: {total_rss / 1e6:.1f} MB > "
                                f"{limit_bytes / 1e6:.1f} MB. Preempting active processes."
                            )
                            self.execute_zombie_reaper()
                except Exception as exc:
                    logger.debug(f"OOM poll error: {exc}")
                self._stop_event.wait(check_interval)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_oom_monitor(self) -> None:
        """Stops the active OOM preemption monitor thread."""
        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

    def start_zmq_heartbeat(
        self,
        port: int = 5557,
        host: str = "127.0.0.1",
        interval_sec: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Starts a background ZeroMQ PUB heartbeat publisher emitting telemetry metadata."""
        if not HAS_ZMQ:
            logger.warning("ZeroMQ (pyzmq) not available. Heartbeat publisher disabled.")
            return

        self.stop_zmq_heartbeat()
        self._zmq_stop_event.clear()

        try:
            self._zmq_context = zmq.Context()
            self._zmq_socket = self._zmq_context.socket(zmq.PUB)
            self._zmq_socket.bind(f"tcp://{host}:{port}")
        except Exception as err:
            logger.error(f"Failed to bind ZeroMQ heartbeat socket on {host}:{port}: {err}")
            self.stop_zmq_heartbeat()
            return

        def heartbeat_worker() -> None:
            while not self._zmq_stop_event.is_set():
                alive_payload: Dict[str, Any] = {
                    "status": "alive",
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                    "active_processes": len(self.active_processes),
                    "metadata": metadata or {},
                }
                try:
                    if self._zmq_socket is not None:
                        self._zmq_socket.send_multipart([
                            b"heartbeat",
                            json.dumps(alive_payload).encode("utf-8"),
                        ])
                except Exception as ex:
                    logger.debug(f"ZeroMQ heartbeat send error: {ex}")
                self._zmq_stop_event.wait(interval_sec)

        self._zmq_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self._zmq_thread.start()
        logger.info(f"ZeroMQ heartbeat publisher started on tcp://{host}:{port} [M]")

    def stop_zmq_heartbeat(self) -> None:
        """Stops the ZeroMQ heartbeat publisher and releases socket resources."""
        self._zmq_stop_event.set()
        if self._zmq_thread is not None:
            self._zmq_thread.join(timeout=2.0)
            self._zmq_thread = None
        if self._zmq_socket is not None:
            try:
                self._zmq_socket.close(linger=0)
            except Exception:
                pass
            self._zmq_socket = None
        if self._zmq_context is not None:
            try:
                self._zmq_context.term()
            except Exception:
                pass
            self._zmq_context = None

    def execute_zombie_reaper(self) -> int:
        """Terminates all managed subprocesses and their orphaned children with 10-second grace period."""
        count = 0
        with self._lock:
            procs = list(self.active_processes)
            self.active_processes.clear()

        if not procs:
            return 0

        logger.info("Executing SubprocessBroker Zombie Reaper Protocol...")
        for proc in procs:
            if proc.poll() is None:
                try:
                    pid = proc.pid
                    kill_process_tree(pid, timeout=10.0)
                    unregister_popen_process(proc)
                    count += 1
                    logger.info(f"Reaped managed process tree PID {pid}")
                except (ProcessLookupError, PermissionError, OSError) as e:
                    logger.warning(f"Reaper failed on PID {proc.pid}: {e}")
            else:
                unregister_popen_process(proc)

        return count

    def garbage_collect_core_dumps(self, execution_dir: Optional[Union[str, Path]] = None) -> int:
        """Sweeps massive binary core.* files generated by Fortran segfaults."""
        target_dir = Path(execution_dir).resolve() if execution_dir is not None else self.cwd
        count = 0
        if not target_dir.exists():
            return 0
        for file in target_dir.glob("core.*"):
            if file.is_file():
                try:
                    file.unlink()
                    count += 1
                except OSError as err:
                    logger.debug(f"Unable to unlink core file {file}: {err}")
        if count > 0:
            logger.info(f"Garbage collection swept {count} binary dump(s).")
        return count

    def hash_quantum_artifacts(self, execution_dir: Optional[Union[str, Path]] = None) -> Dict[str, str]:
        """Calculates SHA-256 cryptographic provenance digests for all quantum chemistry artifacts."""
        target_dir = Path(execution_dir).resolve() if execution_dir is not None else self.cwd
        return RAMDiskOverlayManager.hash_artifacts(target_dir)

    def extract_crash_hex_dump(
        self,
        returncode: int,
        stderr_data: Union[str, bytes, Sequence[str], None],
    ) -> Dict[str, Any]:
        """Extracts 256-byte hexadecimal crash trace for crashed subprocesses."""
        return extract_segfault_hex_dump(returncode, stderr_data)

    def execute(
        self,
        payload_command: Union[str, List[str]],
        job_name: str = "cochem_job",
        timeout: Optional[float] = None,
        cpu_affinity: Optional[List[int]] = None,
        required_disk_gb: float = 0.05,
        dead_man_timeout: float = 60.0,
        daemonize_on_timeout: bool = True,
    ) -> int:
        """Dispatches an execution payload with cross-platform isolation and crash telemetry monitoring.

        Allocates high-speed RAM-disk if available, executes payload with dead-man's switch watchdog,
        enforces timeout, streams stdout/stderr, extracts segfault hex dumps if crashed,
        and copies artifacts back upon completion.
        """
        exec_path = self._allocate_scratch_space(job_name)
        verify_scratch_quota_and_io(exec_path, required_gb=max(0.01, required_disk_gb))

        cmd_str: str
        command: Union[str, List[str]]
        if isinstance(payload_command, str):
            if platform.system() == "Windows":
                command = payload_command
            else:
                command = shlex.split(payload_command, posix=True)
            cmd_str = payload_command
        else:
            command = payload_command
            cmd_str = " ".join(payload_command)

        sanitized_env = sanitize_mpi_environment(self.env, cmd=command)

        logger.info(f"Dispatching '{job_name}' to broker in {exec_path}...")

        stdout_hist: List[str] = []
        stderr_hist: List[str] = []

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(exec_path),
            "env": sanitized_env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
        }

        process: Optional[subprocess.Popen] = None
        job_obj = WindowsJobObject() if platform.system() == "Windows" else None
        watchdog: Optional[DeadMansSwitchWatchdog] = None
        exit_code: int = 0

        try:
            process = subprocess.Popen(command, **popen_kwargs)
            with self._lock:
                self.active_processes.append(process)
            register_popen_process(process)

            if job_obj is not None:
                job_obj.assign_popen(process)

            if cpu_affinity is not None:
                enforce_cpu_affinity(process.pid, cpu_affinity)

            watchdog = DeadMansSwitchWatchdog(
                job_id=job_name,
                proc=process,
                timeout=dead_man_timeout,
                on_timeout="daemonize" if daemonize_on_timeout else "kill",
            )
            watchdog.start()

            def _stream_stdout() -> None:
                if process and process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if watchdog:
                            watchdog.ping()
                        clean_line = line.strip()
                        stdout_hist.append(clean_line)
                        if self.telemetry and not self.telemetry.process_stream_chunk(clean_line):
                            logger.error("Telemetry trap triggered. Preempting process.")
                            kill_process_tree(process.pid, timeout=10.0)
                            break

            def _stream_stderr() -> None:
                if process and process.stderr:
                    for line in iter(process.stderr.readline, ''):
                        if watchdog:
                            watchdog.ping()
                        stderr_hist.append(line.strip())

            t_stdout = threading.Thread(target=_stream_stdout, daemon=True)
            t_stderr = threading.Thread(target=_stream_stderr, daemon=True)

            t_stdout.start()
            t_stderr.start()

            if timeout is not None and timeout > 0:
                try:
                    process.wait(timeout=timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    logger.error(f"Process '{job_name}' timed out after {timeout} seconds.")
                    kill_process_tree(process.pid, timeout=10.0)
                    try:
                        process.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        pass
                    exit_code = -124
            else:
                process.wait()
                exit_code = process.returncode

            t_stdout.join(timeout=2.0)
            t_stderr.join(timeout=2.0)

            # Check for segfault / access violation crash and sweep 256-byte hex dump
            crash_info = extract_segfault_hex_dump(exit_code, stderr_hist)
            if crash_info.get("is_crash"):
                logger.error(
                    f"Process payload '{job_name}' crashed ({crash_info.get('crash_type')}, code {exit_code}):\n"
                    f"{crash_info.get('formatted_hex_dump')}"
                )

        except KeyboardInterrupt:
            logger.error("Keyboard Interrupt. Triggering Reaper.")
            self.execute_zombie_reaper()
            exit_code = -1
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            logger.error(f"Dispatch Exception: {e}")
            self.execute_zombie_reaper()
            exit_code = -2
        finally:
            if watchdog is not None:
                watchdog.stop()

            if job_obj is not None:
                if watchdog is not None and watchdog.is_daemonized:
                    job_obj.set_kill_on_close(False)
                job_obj.close()

            if process is not None:
                with self._lock:
                    if process in self.active_processes:
                        self.active_processes.remove(process)
                unregister_popen_process(process)

            # Compute cryptographic dispatch audit hash
            dispatch_seed = f"{job_name}:{cmd_str}:{exit_code}:{time.time()}".encode('utf-8')
            dispatch_hash = hashlib.sha256(dispatch_seed).hexdigest()

            if self.telemetry:
                self.telemetry.aggregate_and_lock(job_name, stdout_hist, stderr_hist, exit_code, dispatch_hash)

            if not (watchdog is not None and watchdog.is_daemonized):
                self.garbage_collect_core_dumps(exec_path)
                self.ramdisk_manager.sync_and_cleanup(exec_path, self.cwd)
            else:
                logger.info(
                    f"Job '{job_name}' daemonized (PID {process.pid if process else 'N/A'}); "
                    f"preserving execution directory {exec_path} for active background completion."
                )

        return exit_code


__all__ = [
    "SubprocessBroker",
    "safe_subprocess_run",
    "register_popen_process",
    "unregister_popen_process",
    "get_active_popen_processes",
    "cleanup_zombie_processes",
    "kill_process_tree",
    "enforce_cpu_affinity",
    "build_thread_affinity_env",
    "detect_cpu_topology",
    "CPUTopologyManager",
    "detect_mpi_environment",
    "sanitize_mpi_environment",
    "verify_scratch_io",
    "verify_scratch_quota_and_io",
    "lock_directory_permissions",
    "RAMDiskOverlayManager",
    "ZMQHeartbeatManager",
    "DeadMansSwitchWatchdog",
    "WindowsJobObject",
    "ZombieReaper",
    "DiskQuotaError",
    "extract_segfault_hex_dump",
    "sweep_crash_hex_dump",
    "is_crash_returncode",
    "CRITICAL_SEGFAULT_EXIT_CODES",
    "HAS_PSUTIL",
    "HAS_ZMQ",
]


if __name__ == "__main__":
    broker = SubprocessBroker()
    logger.info("Broker Initialized and protections armed.")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\concurrency\network_lock.py ---
"""HPC Network Filesystem Atomic Fencing & Heartbeat Leases.

Implements Suggestion #26:
- Atomic directory creation via os.mkdir() across POSIX, NFSv4, and Lustre.
- Active background heartbeat refresher daemon thread.
- Split-brain defense with fencing tokens and validated stale lease reclamation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("cochem.concurrency.network_lock")


def _is_pid_alive(pid: int) -> bool:
    """Check if local PID is physically running and not a zombie."""
    if pid <= 0:
        return False
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return False
        p = psutil.Process(pid)
        return bool(p.is_running() and p.status() != psutil.STATUS_ZOMBIE)
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class NetworkHeartbeatLock:
    """Distributed directory lease lock with active heartbeat renewals and fencing tokens."""

    def __init__(
        self,
        lock_dir: Path | str,
        lease_ttl_sec: float = 30.0,
        grace_period_sec: float = 5.0,
        node_id: Optional[str] = None,
    ) -> None:
        self.lock_dir = Path(lock_dir).resolve()
        self.lease_ttl_sec = max(0.5, float(lease_ttl_sec))
        self.grace_period_sec = max(0.1, float(grace_period_sec))
        self.hostname = node_id or socket.gethostname()
        self.pid = os.getpid()

        self.lease_file = self.lock_dir / "lease.json"
        self._fence_token: Optional[str] = None
        self._is_held = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat = threading.Event()
        self._local_lock = threading.RLock()

    def _read_manifest(self) -> Optional[Dict[str, Any]]:
        """Read and parse lease manifest safely."""
        if not self.lease_file.exists():
            return None
        try:
            with open(self.lease_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _write_manifest(self, manifest: Dict[str, Any]) -> None:
        """Write manifest atomically via sibling temporary file."""
        tmp_file = self.lock_dir / f"lease.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_file), str(self.lease_file))

    def is_stale(self) -> bool:
        """Check if active lease is expired beyond TTL and grace period."""
        if not self.lock_dir.exists():
            return False
        manifest = self._read_manifest()
        if manifest is None:
            # Lock dir exists without valid manifest; check mtime fallback after grace period
            try:
                mtime = self.lock_dir.stat().st_mtime
                return (time.time() - mtime) > (self.lease_ttl_sec + self.grace_period_sec)
            except OSError:
                return False

        expires_at = float(manifest.get("expires_at", 0.0))
        now = time.time()
        if now <= expires_at + self.grace_period_sec:
            return False

        # If on the same host, verify the owning process is actually dead
        owning_host = manifest.get("hostname", "")
        owning_pid = int(manifest.get("pid", 0))
        if owning_host == self.hostname and owning_pid > 0:
            if _is_pid_alive(owning_pid):
                return False

        return True

    def is_locked(self) -> bool:
        """Check if lock directory exists and lease is currently valid."""
        if not self.lock_dir.exists():
            return False
        return not self.is_stale()

    def renew_heartbeat(self) -> bool:
        """Update lease heartbeat and expiration timestamp while holding lock."""
        with self._local_lock:
            if not self._is_held:
                return False
            now = time.time()
            manifest = {
                "hostname": self.hostname,
                "pid": self.pid,
                "heartbeat": now,
                "fence_token": self._fence_token,
                "expires_at": now + self.lease_ttl_sec,
            }
            try:
                self._write_manifest(manifest)
                return True
            except Exception as exc:
                logger.debug("Failed to renew heartbeat: %s", exc)
                return False

    def _heartbeat_worker(self) -> None:
        """Background thread refreshing heartbeat every TTL / 3 seconds."""
        interval = max(0.1, self.lease_ttl_sec / 3.0)
        while not self._stop_heartbeat.wait(interval):
            if not self.renew_heartbeat():
                break

    def acquire(self, timeout: float = 10.0) -> bool:
        """Acquire atomic directory lease with retry backoff and stale lease reclamation."""
        t0 = time.time()
        deadline = t0 + max(0.0, float(timeout))

        while True:
            # Step 1: Attempt atomic directory creation
            try:
                self.lock_dir.parent.mkdir(parents=True, exist_ok=True)
                os.mkdir(str(self.lock_dir))
                # Successfully created directory: become leaseholder
                self._fence_token = uuid.uuid4().hex
                now = time.time()
                manifest = {
                    "hostname": self.hostname,
                    "pid": self.pid,
                    "heartbeat": now,
                    "fence_token": self._fence_token,
                    "expires_at": now + self.lease_ttl_sec,
                }
                self._write_manifest(manifest)
                self._is_held = True

                # Start background heartbeat daemon
                self._stop_heartbeat.clear()
                self._heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
                self._heartbeat_thread.start()
                return True
            except FileExistsError:
                logger.debug("Lock directory %s already exists, assessing lease status.", self.lock_dir)

            # Step 2: Handle existing directory - check for staleness
            if self.is_stale():
                # Attempt stale lease reclamation with fencing check
                manifest_before = self._read_manifest()
                old_token = manifest_before.get("fence_token") if manifest_before else None
                try:
                    # Clean out stale directory atomically
                    shutil.rmtree(str(self.lock_dir), ignore_errors=True)
                except OSError as clean_err:
                    logger.debug("Could not remove stale lock dir: %s", clean_err)
                continue

            if time.time() >= deadline:
                return False

            time.sleep(0.05)

    def release(self) -> None:
        """Release directory lease and terminate heartbeat daemon."""
        with self._local_lock:
            if not self._is_held:
                return

            self._is_held = False
            self._stop_heartbeat.set()
            if self._heartbeat_thread is not None:
                self._heartbeat_thread.join(timeout=2.0)
                self._heartbeat_thread = None

            try:
                manifest = self._read_manifest()
                # Only delete if fence token matches our session
                if manifest is not None and manifest.get("fence_token") == self._fence_token:
                    shutil.rmtree(str(self.lock_dir), ignore_errors=True)
            except OSError as rel_err:
                logger.debug("Error removing lock dir on release: %s", rel_err)

    def __enter__(self) -> NetworkHeartbeatLock:
        if not self.acquire(timeout=self.lease_ttl_sec):
            raise TimeoutError(f"Could not acquire NetworkHeartbeatLock on {self.lock_dir}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


__all__ = ["NetworkHeartbeatLock"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\concurrency\test_concurrency_chunk3.py ---
"""Zero-Mock Concurrency & Process Containment Test Suite for Chunk 3.

Validates Suggestions #21, #22, #24, #25, #30:
- Thread-safe process tree management & atomic snapshot iteration in ProcessTreeManager
- Thread-safe queue and event-driven worker saturation in CoreScheduler (>50 tasks/s)
- Win32 kernel handle RAII hygiene & leak prevention
- Dynamic host threading contention budgeting and GPU MPS apportionment
- Verified process demise, escalated SIGKILL, and ghost process telemetry
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, List

import psutil
import pytest

from cochem.core.hardware.topology import TopologyDiscoveryEngine
from cochem.core.process_reaper import (
    ProcessReapTimeoutError,
    ProcessTreeManager,
    ZombieReaperDaemon,
)
from cochem_base.core_engine.cochem_core_scheduler import (
    CoreScheduler,
    TaskConfig,
)


def test_process_tree_manager_thread_safety_during_sweep() -> None:
    """Suggestion #21: Verify thread-safe process registration/unregistration during active sweeps."""
    manager = ProcessTreeManager()
    daemon = ZombieReaperDaemon(tree_manager=manager, interval_sec=0.01)

    errors: List[Exception] = []
    stop_event = threading.Event()
    registration_count = 0
    lock = threading.Lock()

    procs: List[subprocess.Popen[Any]] = []
    try:
        for _ in range(5):
            p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
            procs.append(p)

        def worker(worker_id: int) -> None:
            nonlocal registration_count
            while not stop_event.is_set():
                p = procs[worker_id % len(procs)]
                try:
                    manager.register_process(p.pid, task_id=f"task_{worker_id}")
                    with lock:
                        registration_count += 1
                        if registration_count >= 1000:
                            stop_event.set()
                            break
                    time.sleep(0.0005)
                    manager.unregister_process(p.pid)
                except Exception as exc:
                    errors.append(exc)
                    stop_event.set()
                    break

        def sweeper() -> None:
            while not stop_event.is_set():
                try:
                    daemon.sweep_orphans()
                except Exception as exc:
                    errors.append(exc)
                    stop_event.set()
                    break
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        sweep_thread = threading.Thread(target=sweeper)

        sweep_thread.start()
        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=15.0)
        stop_event.set()
        sweep_thread.join(timeout=5.0)

        assert not errors, f"Thread safety errors during sweep: {errors}"
        assert registration_count >= 1000
    finally:
        for p in procs:
            if psutil.pid_exists(p.pid):
                manager.terminate_tree(p.pid, grace_timeout_sec=0.5)


def test_core_scheduler_queue_throughput_and_zero_latency(tmp_path: Path) -> None:
    """Suggestion #22: Verify thread-safe queue dispatch saturates workers (>50 tasks/s) without 500ms delay."""
    scheduler = CoreScheduler(max_workers=16, project_root=tmp_path)
    scheduler.start_scheduling()

    num_tasks = 50
    t0 = time.perf_counter()

    for i in range(num_tasks):
        config = TaskConfig(
            task_id=f"throughput_task_{i}",
            command=[sys.executable, "-c", "import sys; sys.exit(0)"],
            timeout_seconds=10,
        )
        scheduler.add_task(config)

    deadline = time.perf_counter() + 10.0
    while time.perf_counter() < deadline:
        statuses = [scheduler.get_task_status(f"throughput_task_{i}") for i in range(num_tasks)]
        if all(s is not None and s.status in ("completed", "failed") for s in statuses):
            break
        time.sleep(0.005)

    t_elapsed = time.perf_counter() - t0
    scheduler.stop_scheduling()

    statuses = [scheduler.get_task_status(f"throughput_task_{i}") for i in range(num_tasks)]
    completed = [s for s in statuses if s is not None and s.status == "completed"]
    assert len(completed) == num_tasks, f"Only {len(completed)}/{num_tasks} tasks completed"

    dispatch_throughput = num_tasks / t_elapsed
    assert dispatch_throughput > 50.0, f"Throughput {dispatch_throughput:.1f} tasks/s too slow (elapsed: {t_elapsed:.2f}s)"
    assert t_elapsed < 5.0, f"Execution took too long: {t_elapsed:.2f}s"


def test_win32_kernel_handle_leak_prevention() -> None:
    """Suggestion #24: Verify Win32 OpenProcess handle RAII cleanup prevents monotonic handle growth."""
    if sys.platform != "win32":
        pytest.skip("Win32 kernel handle test is Windows-specific")

    manager = ProcessTreeManager()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        current_proc = psutil.Process()
        # Warmup registration
        for _ in range(20):
            manager.register_process(proc.pid)
            manager.unregister_process(proc.pid)

        initial_handles = current_proc.num_handles()

        for _ in range(500):
            manager.register_process(proc.pid)
            manager.unregister_process(proc.pid)

        final_handles = current_proc.num_handles()
        handle_delta = final_handles - initial_handles
        # Strict RAII: handle count must not grow by hundreds
        assert handle_delta <= 10, (
            f"Win32 process handle leak detected: initial={initial_handles}, "
            f"final={final_handles}, delta={handle_delta}"
        )
    finally:
        if psutil.pid_exists(proc.pid):
            manager.terminate_tree(proc.pid, grace_timeout_sec=0.5)


def test_topology_contention_budgeting() -> None:
    """Suggestion #25: Verify dynamic host thread budgeting per worker and MPS apportionment."""
    engine = TopologyDiscoveryEngine()
    topo = engine.discover_topology(concurrent_workers=4)

    expected_threads = max(1, topo.anchor_cores // 4)
    worker_env = engine.get_worker_env(concurrent_workers=4, worker_index=1)

    assert worker_env["OMP_NUM_THREADS"] == str(expected_threads)
    assert worker_env["MKL_NUM_THREADS"] == str(expected_threads)
    assert worker_env["OPENBLAS_NUM_THREADS"] == str(expected_threads)
    assert worker_env["VECLIB_MAXIMUM_THREADS"] == str(expected_threads)
    assert worker_env["NUMEXPR_NUM_THREADS"] == str(expected_threads)

    # NVIDIA MPS active thread percentage for 4 workers = 100 // 4 = 25
    assert worker_env.get("CUDA_MPS_ACTIVE_THREAD_PERCENTAGE") == "25"


def test_verified_process_demise_escalation() -> None:
    """Suggestion #30: Verify process reaper escalates to SIGKILL / Job Object termination for stubborn processes."""
    manager = ProcessTreeManager()

    # Launch a process that ignores SIGTERM
    script = (
        "import signal, time, sys\n"
        "def handler(signum, frame):\n"
        "    return None\n"
        "try:\n"
        "    signal.signal(signal.SIGTERM, handler)\n"
        "except Exception:\n"
        "    sys.stderr.write('Signal setup error\\n')\n"
        "time.sleep(15)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", script])
    pid = proc.pid
    manager.register_process(pid)

    time.sleep(0.2)
    assert manager.is_alive(pid)

    metrics = manager.terminate_tree(pid, grace_timeout_sec=0.5)
    assert metrics["success"] is True
    assert metrics["pid"] == pid
    assert not psutil.pid_exists(pid)
    assert manager.is_alive(pid) is False

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\core\test_filesystem_remediation_chunk3.py ---
"""Zero-Mock Filesystem Synchronization & Fault Remediation Test Suite for Chunk 3.

Validates Suggestions #23, #26, #27, #28, #29:
- Cross-process atomic persistence for swarm_state.json (multiprocessing stress test)
- NetworkHeartbeatLock split-brain defense, heartbeat renewal, and stale lease fencing
- SubprocessBroker ephemeral sandboxing & Tripartite scratch isolation
- RWFileLock concurrent shared readers with exclusive writer-priority
- Self-healing subprocess remediation callback with parameter and input deck escalation
"""

from __future__ import annotations

import json
import multiprocessing
import os
import pathlib
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, List

import pytest

from cochem.concurrency.atomic_file_lock import RWFileLock
from cochem.concurrency.network_lock import NetworkHeartbeatLock
from cochem.concurrency.subprocess_broker import (
    FailureCategory,
    SubprocessBroker,
    SubprocessExecutionResult,
)
from cochem_base.core_engine.cochem_core_scheduler import (
    CoreScheduler,
    TaskResult,
    persist_swarm_state_atomic,
)


def _worker_update_swarm_state(state_file_path: str, worker_id: int, count: int) -> None:
    """Worker function executed across independent OS processes."""
    state_file = pathlib.Path(state_file_path)
    for i in range(count):
        task_id = f"proc_task_{worker_id}_{i}"
        entry = {
            "agent": f"worker_{worker_id}",
            "status": "SUCCESS",
            "artifacts": [f"{task_id}.out"],
            "hashes": {"sha256": f"hash_{worker_id}_{i}"},
            "error_message": None,
            "timestamp": time.time(),
        }
        persist_swarm_state_atomic(state_file, task_id, entry)
        time.sleep(0.001)


def test_swarm_state_cross_process_locking_integrity(tmp_path: pathlib.Path) -> None:
    """Suggestion #23: 8 independent OS processes execute 20 concurrent updates each (160 total) without JSON corruption."""
    state_file = tmp_path / "swarm_state.json"

    num_processes = 8
    updates_per_proc = 20
    processes: List[multiprocessing.Process] = []

    for wid in range(num_processes):
        p = multiprocessing.Process(
            target=_worker_update_swarm_state,
            args=(str(state_file), wid, updates_per_proc),
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join(timeout=30.0)
        assert p.exitcode == 0, f"Worker process failed with exit code {p.exitcode}"

    assert state_file.exists(), "swarm_state.json was not created"
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    expected_total = num_processes * updates_per_proc
    assert len(data) == expected_total, f"Expected {expected_total} entries, got {len(data)}"
    for wid in range(num_processes):
        for i in range(updates_per_proc):
            key = f"proc_task_{wid}_{i}"
            assert key in data, f"Missing key {key}"
            assert data[key]["agent"] == f"worker_{wid}"
            assert data[key]["status"] == "SUCCESS"


def test_network_heartbeat_lock_split_brain_defense(tmp_path: pathlib.Path) -> None:
    """Suggestion #26: Atomic directory lease fencing, heartbeat renewals, and stale lease reclamation."""
    lock_dir = tmp_path / "hpc_cluster_lock.lease"

    # Node 1 acquires lease with 1.5s TTL
    lock_node1 = NetworkHeartbeatLock(lock_dir=lock_dir, lease_ttl_sec=1.5, node_id="node-1")
    acquired1 = lock_node1.acquire(timeout=2.0)
    assert acquired1 is True
    assert lock_node1.is_locked() is True

    # Node 2 fails to acquire while Node 1 holds active lease
    lock_node2 = NetworkHeartbeatLock(lock_dir=lock_dir, lease_ttl_sec=1.5, node_id="node-2")
    acquired2 = lock_node2.acquire(timeout=0.3)
    assert acquired2 is False

    # Simulate active heartbeat refresh on Node 1: verify lease remains valid
    time.sleep(0.6)
    assert lock_node1.renew_heartbeat() is True
    assert lock_node2.is_stale() is False

    # Node 1 terminates / releases or lease expires
    lock_node1.release()
    assert lock_node1.is_locked() is False

    # Node 2 safely acquires the lock
    acquired2_retry = lock_node2.acquire(timeout=2.0)
    assert acquired2_retry is True
    assert lock_node2.is_locked() is True
    lock_node2.release()


def test_subprocess_broker_ephemeral_scratch_isolation(tmp_path: pathlib.Path) -> None:
    """Suggestion #27: Two concurrent brokers write identical relative filenames without colliding."""
    scratch_root = tmp_path / "ephemeral_scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)

    broker1 = SubprocessBroker(context_or_engine="worker_1", base_scratch_dir=scratch_root)
    broker2 = SubprocessBroker(context_or_engine="worker_2", base_scratch_dir=scratch_root)

    script1 = (
        "import pathlib, time\n"
        "p = pathlib.Path('temp_output.dat')\n"
        "p.write_text('PAYLOAD_FROM_WORKER_1')\n"
        "time.sleep(0.3)\n"
        "assert p.read_text() == 'PAYLOAD_FROM_WORKER_1'\n"
    )
    script2 = (
        "import pathlib, time\n"
        "p = pathlib.Path('temp_output.dat')\n"
        "p.write_text('PAYLOAD_FROM_WORKER_2')\n"
        "time.sleep(0.3)\n"
        "assert p.read_text() == 'PAYLOAD_FROM_WORKER_2'\n"
    )

    t1_result: List[SubprocessExecutionResult] = []
    t2_result: List[SubprocessExecutionResult] = []

    def run_b1() -> None:
        res = broker1.execute_with_remediation([sys.executable, "-c", script1])
        t1_result.append(res)

    def run_b2() -> None:
        res = broker2.execute_with_remediation([sys.executable, "-c", script2])
        t2_result.append(res)

    th1 = threading.Thread(target=run_b1)
    th2 = threading.Thread(target=run_b2)

    th1.start()
    th2.start()
    th1.join(timeout=10.0)
    th2.join(timeout=10.0)

    assert len(t1_result) == 1 and t1_result[0].success is True, f"Broker 1 failed: {t1_result}"
    assert len(t2_result) == 1 and t2_result[0].success is True, f"Broker 2 failed: {t2_result}"

    # Verify each ephemeral job sandbox subdirectory was swept and deleted
    remaining_dirs = list(scratch_root.glob("cochem_job_*"))
    assert len(remaining_dirs) == 0, f"Scratch leakage detected: {remaining_dirs}"


def test_rw_file_lock_concurrent_readers_exclusive_writer(tmp_path: pathlib.Path) -> None:
    """Suggestion #28: Concurrent readers and writers run simultaneously without mutual exclusion violations."""
    state_file = tmp_path / "state_data.dat"
    state_file.write_text("initial_value", encoding="utf-8")
    rw_lock = RWFileLock(state_file, timeout=10.0)

    active_readers = 0
    active_writers = 0
    max_concurrent_readers = 0
    violations: List[str] = []
    counter_lock = threading.Lock()
    stop_event = threading.Event()

    def reader_task(reader_id: int) -> None:
        nonlocal active_readers, max_concurrent_readers
        for _ in range(15):
            if stop_event.is_set():
                break
            with rw_lock.read_lock():
                with counter_lock:
                    if active_writers > 0:
                        violations.append(f"Reader {reader_id} entered while writer active ({active_writers})")
                    active_readers += 1
                    if active_readers > max_concurrent_readers:
                        max_concurrent_readers = active_readers

                content = state_file.read_text(encoding="utf-8")
                assert "value" in content
                time.sleep(0.01)

                with counter_lock:
                    active_readers -= 1
            time.sleep(0.005)

    def writer_task(writer_id: int) -> None:
        nonlocal active_writers
        for step in range(5):
            if stop_event.is_set():
                break
            with rw_lock.write_lock():
                with counter_lock:
                    if active_readers > 0:
                        violations.append(f"Writer {writer_id} entered while {active_readers} readers active")
                    if active_writers > 0:
                        violations.append(f"Writer {writer_id} entered while another writer active")
                    active_writers += 1

                state_file.write_text(f"writer_value_{writer_id}_{step}", encoding="utf-8")
                time.sleep(0.02)

                with counter_lock:
                    active_writers -= 1
            time.sleep(0.01)

    reader_threads = [threading.Thread(target=reader_task, args=(i,)) for i in range(8)]
    writer_threads = [threading.Thread(target=writer_task, args=(j,)) for j in range(2)]
    all_threads = reader_threads + writer_threads

    for t in all_threads:
        t.start()
    for t in all_threads:
        t.join(timeout=15.0)

    assert not violations, f"Mutual exclusion violations detected: {violations}"
    assert max_concurrent_readers > 1, f"Expected concurrency, got max {max_concurrent_readers}"
    assert state_file.exists()


def test_subprocess_remediation_callback_execution(tmp_path: pathlib.Path) -> None:
    """Suggestion #29: Dynamic input deck and parameter remediation callback execution under failure."""
    broker = SubprocessBroker(scratch_dir=tmp_path)

    # Command fails on attempt 1 without '--damping', succeeds on attempt 2 when '--damping' is injected
    script = (
        "import sys\n"
        "if '--damping' not in sys.argv:\n"
        "    print('SCF FAILED TO CONVERGE', file=sys.stdout)\n"
        "    sys.exit(1)\n"
        "print('SCF CONVERGED SUCCESSFULLY', file=sys.stdout)\n"
        "sys.exit(0)\n"
    )

    base_cmd = [sys.executable, "-c", script]

    def remediate_cb(category: FailureCategory, params: Dict[str, Any], scratch: pathlib.Path) -> List[str]:
        assert category == FailureCategory.SCF_CONVERGENCE_FAILURE
        # Method Matrix §8B: escalate convergence by injecting damping
        return base_cmd + ["--damping"]

    result = broker.execute_with_remediation(
        command=base_cmd,
        timeout_sec=5.0,
        remediate_callback=remediate_cb,
    )

    assert result.success is True
    assert result.retries_attempted == 1
    assert "SCF CONVERGED SUCCESSFULLY" in result.stdout

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.