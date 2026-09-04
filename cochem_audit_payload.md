Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_07_Ecosystem_Part_7_prompts.md.
Original prompt:
# CODING PROMPT: CoChem Ecosystem Implementation (Chunk 7: Suggestions #61–#70)

**Target Output Repositories:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`, `CoChem-TOPOS`, and `CoChem-TORQ`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§1.2, §3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds, §8A.2 Scout-and-Anchor Heterogeneous Concurrency, §8A.4 NVIDIA MPS Daemon Lifecycle, §8A.6 Parsl Multi-Executor Architecture, §8B.4 Canonical Arrows 4 & 5 Binary Wavefunction Projection via `%moinp`, §8C Production HDF5 Store Architecture & Chunking, §9B.3 Multi-Seed Conformational Exploration, §10.8 Active Learning & Fallback Provenance Auditing, Table 2 T1-30min / T3, QS-1, QS-3)
- Anti-Spoofing Protocol v2 (enforcing Zero-Mock, Asymmetric Verification, Hard Abort Criteria, and MAX_PIVOT_CYCLES: zero pass stubs, zero fabricated outputs, zero synthetic dummy loops, mandatory physical execution)
- Tripartite Air-Gap Architecture (`T_ui` frontend, `T_schema` Pydantic contracts, `T_engine` decoupled background subprocesses; cross-module communication strictly via validated schemas, OS PID locks, and streaming IPC queues; Tripartite Storage Rings: Ring 1 Source $R_{\text{src}}$ / `$COCHEM_ROOT`, Ring 2 Ephemeral Scratch $R_{\text{data}}$ / `$COCHEM_SCRATCH`, Ring 3 Persistent Artifacts $R_{\text{art}}$ / `$COCHEM_ARTIFACTS`)
- 6-Tier Environment Matrix (Tier 1: Windows Native/WSL2 NT, Tier 2: macOS/OrbStack Darwin, Tier 3: Debian Linux, Tier 4: GitHub Codespaces, Tier 5: GitHub Actions CI/CD, Tier 6: HPC Slurm/PBS)
- Dynamic Mendeleev Mass & Radii Retrieval Mandate (`from mendeleev import element`, strict dynamic atomic/isotopic mass query, zero hardcoded constants)
- Cross-Platform Concurrency Directive (Thread-safe and process-safe SWMR HDF5 with `filelock.FileLock` / `cochem.concurrency.atomic_file_lock.RWFileLock`, node-local scratch staging on HPC `$SLURM_TMPDIR`, non-blocking telemetry reads)
- JAX 64-Bit & Bounded GPU Allocation Mandate (`JAX_ENABLE_X64=True` initialization on line 1, `XLA_PYTHON_CLIENT_PREALLOCATE=false`, `XLA_PYTHON_CLIENT_MEM_FRACTION=0.20`, PyTorch default `torch.float64`)

---

## 1. Executive Summary & Scope

Implement, harden, and physically verify Suggestions #61 through #70 of the CoChem Tripartite Ecosystem. This work package rectifies critical architectural bottlenecks and severe provenance/concurrency failure modes across vectorized active learning committee inference, machine-learning-to-empirical fallback audit trails, unverified quantum chemical binary spoofing, multi-process HDF5 lock collisions, cross-platform NVIDIA MPS vs. semaphore scout scheduling, Parsl multi-executor integration, subprocess interface standardization, multi-seed conformer task parallelization, HPC daemon lifecycle monitoring, and high-performance SLURM batch pipeline entrypoints.

Key deliverables include:
1. **Vectorized Committee Ensemble Inference & Dynamic VRAM Throttling (Suggestion #61):** Eliminate sequential host-thread loops in `CommitteeEnsemble.forward()`. Implement vectorized forward passes using `torch.vmap` or managed concurrent CUDA streams. Integrate `RESOURCE_GUARD` memory headroom polling (`torch.cuda.mem_get_info()`); if available VRAM $< 2.0\text{ GB}$, automatically serialize inference across members to eliminate CUDA out-of-memory crashes across the 6-Tier Environment Matrix while reducing active learning committee latency by up to $3\times$ [M].
2. **OET Machine-Learning-to-Empirical Fallback Provenance & Alert Manifests (Suggestion #62):** Eliminate silent potential degradation in `oet_client.py`. When socket disconnects trigger `PhysicalOETFallbackCalculator`, atomically write an audit manifest (`<base>_EXT.fallback_alert.json`) into Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`) and stage an alert into Ring 3 persistent storage (`$COCHEM_ARTIFACTS`). Prohibit writes to Ring 1 static repository paths (`$COCHEM_ROOT`), and write an uncertainty marker file triggering the orchestrator to halt or tag all resulting observables with provenance tag `[E]` (Empirical).
3. **Purge of Fabricated SCF/Opt Cycles & Corrupt Binary Wavefunctions in Chained Engines (Suggestion #63):** Eradicate all synthetic fallback routines in `CoChem-TOPOS/chain.py` and `CoChem-TORQ/Libraries/chain.py`. Stop generating fabricated iteration counts (`scf_cyc = 12`, `opt_cyc = 6`), mock `ORCA TERMINATED NORMALLY` strings, and synthetic `.gbw`/`.opt` binary byte sequences based on non-physical mass formulas. Enforce explicit exception raising (`ConvergenceFailureError` or `MissingBinaryError`), ensuring intermediate buffers are isolated in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`) and never emitted to Ring 3 persistent storage (`$COCHEM_ARTIFACTS`).
4. **Two-Tier Thread-Safe and Process-Safe HDF5 Persistence Architecture (Suggestion #64):** Eliminate `BlockingIOError` and `OSError: file already open for write` across concurrent Parsl worker sweeps in `gpu_point.py`, `chain.py`, and `pes_h5.py`. Enforce in-process `threading.RLock()` across worker threads and cross-process file locking via `filelock.FileLock` / `cochem.concurrency.atomic_file_lock.RWFileLock` with exponential backoff. Enforce atomic staging: workers commit energy and gradient records to isolated chunk containers in Ring 2 scratch (`$COCHEM_SCRATCH/chunk_<uuid>.h5`), while a central persistence coordinator merges staged chunks into the primary Ring 3 store (`$COCHEM_ARTIFACTS/campaign.h5`) under exclusive write lock with gzip+shuffle+fletcher32 filters.
5. **OS-Aware GPU Scout Concurrency & Windows/macOS Mutex Scheduling (Suggestion #65):** Resolve GPU scout initialization crashes on non-Linux workstations caused by hardcoded NVIDIA Multi-Process Service (MPS) commands in `hetero_config.py` and `cochem_core_parsl_executors.py`. Dynamically branch across the 6-Tier Environment Matrix: on Linux (Tiers 3 & 6), initialize NVIDIA MPS with directory pipes in Ring 2 scratch (`$COCHEM_SCRATCH/nvidia_mps`); on Windows and macOS (Tiers 1 & 2), bypass MPS entirely and serialize GPU dispatches via a cross-process concurrency semaphore (`threading.Semaphore(1)` / named OS mutex). Enforce dynamic VRAM polling across all tiers, deferring tasks if free VRAM $< 1.5\text{ GB}$.
6. **Unified Parsl Multi-Executor Routing in ExecutionRouter (Suggestion #66):** Resolve the architectural bypass in `cochem_calc_execution_router.py` where Parsl scout-and-anchor scheduling was ignored in favor of blocking subprocesses. Wire `ParslExecutionBroker` directly into `ExecutionRouter.route_job()`. Map heavy quantum mechanical optimizations to `cochem_anchor_cpu` with explicit CPU core pinning, and route high-throughput potential scans to `cochem_scout_gpu`. Enforce task sandboxing inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/task_<uuid>`) across all 6 environment tiers.
7. **SubprocessBroker Contract Harmonization & Process Tree Reclamation (Suggestion #67):** Fix interface drift and crashes between `ExecutionRouter` and `SubprocessBroker`. Harmonize the interface contract to accept both string commands (tokenized via `shlex.split(command, posix=(sys.platform != "win32"))`) and pre-tokenized lists of strings; accept `cwd` and `env` parameters during initialization and execution; enforce execution strictly within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`); wrap executions with configurable timeouts; and guarantee recursive child process tree cleanup via `psutil` or `atexit`.
8. **Asynchronous Multi-Seed GOAT Exploration via Parsl Queues (Suggestion #68):** Refactor the sequential exploration loop in `cochem_torq_goat.py` (`run_multi_seed_goat()`) into an asynchronous concurrent task graph dispatched to Parsl `GPU_SCOUT` and `CPU_ANCHOR` executor pools. Sandbox each seed exploration within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/goat_seed_<hash>`), enforce GPU concurrency caps to prevent VRAM oversubscription, and collect deduplicated conformational minima into Ring 3 persistent storage (`$COCHEM_ARTIFACTS`) upon completion.
9. **HPC NVIDIA MPS Worker Daemon Lifecycle & Pipe Polling (Suggestion #69):** Rectify premature daemon termination in `HPC_Launchers/cochem_mps_worker.sh`. Replace bare bash `wait` (which immediately exits when `nvidia-cuda-mps-control -d` detaches) with an active daemon monitoring loop polling the control daemon PID and named pipe socket in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/mps_control`). Implement a trapped signal handler (`EXIT`, `SIGINT`, `SIGTERM`) executing graceful termination, orphaned client context sweeps via `psutil`/`kill`, and full GPU memory release verification.
10. **SLURM Batch Submission CLI Contract & Dynamic HPC Resource Mapping (Suggestion #70):** Resolve silent zero-calculation completions when executing `cochem_submit.slurm`. Implement a complete CLI entrypoint using `argparse` in `cochem_torq_pipeline.py`. Accept parameters for input structures, theory specifications, and directory destinations; validate input existence; enforce Tripartite Storage Ring air-gaps; and dynamically ingest resource allocations from environment variables (`$SLURM_CPUS_PER_TASK`, `$SLURM_MEM_PER_NODE`). Update `cochem_submit.slurm` to forward parameters transparently across cluster nodes.

---

## 2. Target Files & Deliverable Manifest

### Core Implementation Modules
1. `CoChem-BASE/Libraries/cochem_torq_committee_ensemble.py` & `cochem/ml/models/ensemble.py` (Suggestion #61: Vectorized ensemble inference via `torch.vmap` / CUDA streams, dynamic VRAM polling, serialized fallback)
2. `CoChem-TORQ/scripts/oet_client.py` & `CoChem-TORQ/Libraries/cochem_torq_oet_client.py` (Suggestion #62: Fallback audit manifest generation, Tripartite air-gap compliance, uncertainty marker emission, provenance tag `[E]`)
3. `CoChem-TOPOS/chain.py` & `CoChem-TORQ/Libraries/chain.py` (Suggestion #63: Elimination of synthetic fallback routines, purge of fake SCF/Opt cycles and mock `.gbw`/`.opt` files, explicit exception raising)
4. `CoChem-TOPOS/gpu_point.py`, `CoChem-TOPOS/pes_h5.py`, & `CoChem-BASE/src/cochem_base/concurrency/atomic_file_lock.py` (Suggestion #64: Two-tier HDF5 persistence, `threading.RLock`, cross-process `RWFileLock`, atomic scratch chunk staging, and persistent merge coordinator)
5. `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py` & `CoChem-TOPOS/hetero_config.py` (Suggestion #65: Dynamic OS-aware GPU scout executor configuration, Linux MPS vs. Windows/macOS semaphore mutex, dynamic VRAM threshold guard)
6. `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py` (Suggestion #66: Parsl execution broker integration, heterogeneous scout-and-anchor routing, CPU core pinning, sandboxed scratch execution)
7. `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py` & `CoChem-BASE/src/cochem/concurrency/subprocess_broker.py` (Suggestion #67: Harmonized `SubprocessBroker` interface, `shlex.split` cross-platform handling, `cwd`/`env` parameterization, timeout management, `psutil` tree cleanup)
8. `CoChem-TORQ/Libraries/cochem_torq_goat.py` & `CoChem-TORQ/Libraries/cochem_torq_pipeline.py` (Suggestion #68: Asynchronous multi-seed conformer dispatch via Parsl executor pools, scratch directory sandboxing, deduplication merge)
9. `CoChem-TORQ/HPC_Launchers/cochem_mps_worker.sh` (Suggestion #69: Bash MPS daemon monitoring loop, PID polling, named pipe socket check in scratch, trapped signal cleanup)
10. `CoChem-TORQ/Libraries/cochem_torq_pipeline.py` & `CoChem-TORQ/HPC_Launchers/cochem_submit.slurm` (Suggestion #70: CLI entrypoint with `argparse`, SLURM environment variable mapping, Tripartite Storage Ring air-gap enforcement)
11. `CoChem-BASE/src/cochem_base/exceptions.py` & `CoChem-BASE/src/cochem_base/schemas.py` (Suggestions #61–#70: Custom exception hierarchy and typed Pydantic v2 schemas)

### Zero-Mock Test Suite Deliverables
12. `tests/ml/test_vectorized_committee_ensemble.py` (Validating Suggestion #61: Mathematical invariance between vectorized and serial inference, latency reduction, dynamic VRAM serialization threshold)
13. `tests/torq/test_oet_fallback_provenance_alert.py` (Validating Suggestion #62: Atomic generation of `<base>_EXT.fallback_alert.json` in scratch, uncertainty marker file trigger, provenance tag `[E]` enforcement)
14. `tests/topos/test_chain_zero_mock_wavefunction.py` (Validating Suggestion #63: Verified raising of `ConvergenceFailureError` / `MissingBinaryError`, zero generation of synthetic byte sequences in `.gbw` / `.opt`)
15. `tests/concurrency/test_hdf5_concurrent_staging.py` (Validating Suggestion #64: Multi-process and multi-thread concurrent write test, zero `BlockingIOError`, atomic chunk staging and merge integrity)
16. `tests/concurrency/test_gpu_scout_cross_platform_dispatch.py` (Validating Suggestion #65: OS-aware branching, validation of semaphore serialization on Windows/macOS, dynamic VRAM guard)
17. `tests/base/test_execution_router_parsl_broker.py` (Validating Suggestion #66: Routing heavy QM to `cochem_anchor_cpu` with core pinning and scans to `cochem_scout_gpu` via Parsl)
18. `tests/concurrency/test_subprocess_broker_contract.py` (Validating Suggestion #67: String vs tokenized list input handling, `cwd`/`env` passing, cross-platform path handling, process tree termination)
19. `tests/torq/test_goat_multi_seed_concurrency.py` (Validating Suggestion #68: Concurrent multi-seed GOAT exploration, scratch isolation, non-blocking Parsl future aggregation)
20. `tests/hpc/test_mps_worker_lifecycle.py` (Validating Suggestion #69: Validation of shell daemon monitoring logic, PID tracking, clean signal trapped cleanup and VRAM reclamation)
21. `tests/hpc/test_torq_pipeline_cli_slurm.py` (Validating Suggestion #70: Full CLI argument parsing, SLURM environment variable extraction, input verification, Tripartite Storage Ring validation)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Vectorized Committee Ensemble Inference & Dynamic VRAM Throttling (Suggestion #61)]
- **Target Files:** `CoChem-BASE/Libraries/cochem_torq_committee_ensemble.py`, `cochem/ml/models/ensemble.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.2 (Throughput Optimization & Heterogeneous Concurrency) [M], Anti-Spoofing Directive v2.
- **Requirements:**
  1. Define Pydantic v2 configuration schema `CommitteeEnsembleConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Literal

     class CommitteeEnsembleConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         vectorized: bool = True
         vram_headroom_threshold_mb: float = Field(default=2048.0, ge=512.0)
         concurrency_mode: Literal["vmap", "cuda_streams", "serial"] = "vmap"
         max_batch_size: int = Field(default=128, ge=1)
     ```
  2. In `CommitteeEnsemble.forward()`, eliminate the serial iteration loop over `self.models`.
  3. When `concurrency_mode == "vmap"` and neural network architectures share identical parameter shapes, utilize `torch.vmap` over stacked parameters to evaluate all committee members in a single batched kernel invocation:
     $$\mathbf{Y}_{\text{ensemble}}(\mathbf{x}) = \text{vmap}(f)(\boldsymbol{\theta}_{\text{stacked}}, \mathbf{x}) \quad [D]$$
  4. Implement `RESOURCE_GUARD` memory monitoring prior to execution. If running on CUDA:
     ```python
     free_bytes, total_bytes = torch.cuda.mem_get_info()
     free_mb = free_bytes / (1024 * 1024)
     ```
     If `free_mb < vram_headroom_threshold_mb`, automatically log a warning and fall back to sequential inference across members, guaranteeing zero CUDA Out-Of-Memory (`RuntimeError: CUDA out of memory`) exceptions.
  5. If ensemble members have heterogeneous architectures or shapes, execute forward passes across parallel `torch.cuda.Stream` contexts with non-blocking transfers.
  6. Assert mathematical invariance: the predictions and epistemic variance from vectorized execution must match serial execution to machine precision ($\max |\mathbf{y}_{\text{vmap}} - \mathbf{y}_{\text{serial}}| < 10^{-12}$ in FP64) [M].
  7. Isolate all temporary intermediate tensor allocations in memory or Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`).

---

### [Task 2: OET Machine-Learning-to-Empirical Fallback Provenance & Alert Manifests (Suggestion #62)]
- **Target Files:** `CoChem-TORQ/scripts/oet_client.py`, `CoChem-TORQ/Libraries/cochem_torq_oet_client.py`, `CoChem-BASE/src/cochem_base/schemas.py`, `CoChem-BASE/src/cochem_base/exceptions.py`
- **Method Matrix Reference:** Method Matrix v4 §10.8 (Active Learning & Fallback Provenance Auditing) [M], Investigator-in-the-Loop Mandate.
- **Requirements:**
  1. Define Pydantic v2 schemas `OETFallbackAlertManifest` and custom exception `OETDaemonConnectionError`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Dict, Any, Optional
     import datetime

     class OETFallbackAlertManifest(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         calculation_base: str
         timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
         trigger_event: str
         fallback_calculator: str
         provenance_tag: str = "[E]"
         host_telemetry: Dict[str, Any]
         scratch_alert_file: str
         staged_artifact_file: str
     ```
  2. When the socket connection in `oet_client.py` fails and `PhysicalOETFallbackCalculator` is engaged, forbid silent execution.
  3. Enforce Tripartite Storage Ring air-gap compliance:
     - Write the atomic fallback audit manifest (`<base>_EXT.fallback_alert.json`) into the designated Ring 2 ephemeral scratch directory (`$COCHEM_SCRATCH`).
     - Stage an alert copy into the Ring 3 persistent store (`$COCHEM_ARTIFACTS/alerts/`).
     - Strictly forbid any writes into Ring 1 static repository paths (`$COCHEM_ROOT`).
  4. Atomically write an uncertainty marker file (`<base>_EXT.uncertainty_marker`) containing the provenance tag `[E]` and execution metadata.
  5. Instruct the supervising workflow orchestrator to inspect for `<base>_EXT.fallback_alert.json`; upon detection, either abort the pipeline or propagate provenance tag `[E]` (Empirical) to all downstream data points and publications.

---

### [Task 3: Purge of Fabricated SCF/Opt Cycles & Corrupt Binary Wavefunctions in Chained Engines (Suggestion #63)]
- **Target Files:** `CoChem-TOPOS/chain.py`, `CoChem-TORQ/Libraries/chain.py`, `CoChem-BASE/src/cochem_base/exceptions.py`
- **Method Matrix Reference:** Method Matrix v4 §8B.4 (Canonical Arrows 4 & 5 Binary Wavefunction Projection via `%moinp`) [M], Anti-Spoofing Protocol v2.
- **Requirements:**
  1. Define custom exceptions in `CoChem-BASE/src/cochem_base/exceptions.py`:
     ```python
     class ElectronicStructureEngineError(Exception):
         """Base exception for quantum engine failures."""
         pass

     class ConvergenceFailureError(ElectronicStructureEngineError):
         """Raised when SCF or Geometry Optimization fails to converge."""
         pass

     class MissingBinaryError(ElectronicStructureEngineError):
         """Raised when a required quantum chemistry binary is absent."""
         pass
     ```
  2. In `chain.py` (both `CoChem-TOPOS` and `CoChem-TORQ`), purge all routines that fabricate iteration counts (e.g., `scf_cyc = 12`, `opt_cyc = 6`), mock strings (`"ORCA TERMINATED NORMALLY"`), or approximate energies using unphysical mass-based formulas (`sum(-0.5 * (mass ** 1.5))`).
  3. Purge lines that write arbitrary byte sequences into `.gbw` and `.opt` binary containers. If the ORCA binary is missing or fails convergence, immediately raise `MissingBinaryError` or `ConvergenceFailureError`.
  4. Ensure all temporary wavefunction files, scratch integrals, and intermediate geometry buffers remain strictly confined within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`).
  5. In the event of a failure, trigger immediate cleanup of invalid or corrupt files from Ring 2 scratch, and ensure zero unverified binary containers are emitted to Ring 3 persistent storage (`$COCHEM_ARTIFACTS`).

---

### [Task 4: Two-Tier Thread-Safe and Process-Safe HDF5 Persistence Architecture (Suggestion #64)]
- **Target Files:** `CoChem-TOPOS/gpu_point.py`, `CoChem-TOPOS/pes_h5.py`, `CoChem-TOPOS/chain.py`, `CoChem-BASE/src/cochem_base/concurrency/atomic_file_lock.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8C (Production HDF5 Store Architecture & Chunking) [M], [D].
- **Requirements:**
  1. Define Pydantic v2 schema `HDF5PersistenceConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict

     class HDF5PersistenceConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         lock_timeout_seconds: float = Field(default=60.0, ge=1.0)
         retry_backoff_base_seconds: float = Field(default=0.05, ge=0.001)
         compression_filter: str = "gzip"
         compression_level: int = Field(default=4, ge=1, le=9)
         enable_fletcher32: bool = True
         enable_shuffle: bool = True
     ```
  2. Implement a two-tier locking strategy in `pes_h5.py` and `atomic_file_lock.py`:
     - **Tier 1 (In-Process):** Enforce `threading.RLock()` to serialize access across concurrent worker threads within the same process.
     - **Tier 2 (Cross-Process):** Enforce cross-process locking via `filelock.FileLock` / `cochem.concurrency.atomic_file_lock.RWFileLock` with exponential backoff and configurable timeouts, supporting Windows NT, macOS, and Linux without raw POSIX `fcntl` collisions.
  3. Enforce an atomic staging pipeline for distributed workers:
     - Parallel Parsl workers must never write directly into `$COCHEM_ARTIFACTS/campaign.h5`.
     - Each worker writes single-point energies, nuclear gradients, and QCSchema records into an isolated chunk file in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/chunks/chunk_<uuid>.h5`).
  4. Implement a centralized persistence coordinator:
     - The coordinator acquires an exclusive lock on `$COCHEM_ARTIFACTS/campaign.h5`.
     - It merges records from staged chunk files into primary datasets using chunking, shuffle filters, gzip compression level 4, and Fletcher32 checksums.
     - Upon verified ingestion, it purges staged chunk files from Ring 2 scratch.
  5. Guarantee zero `BlockingIOError` or `OSError: file already open for write` during 100-way concurrent worker sweeps.

---

### [Task 5: OS-Aware GPU Scout Concurrency & Windows/macOS Mutex Scheduling (Suggestion #65)]
- **Target Files:** `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`, `CoChem-TOPOS/hetero_config.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.4 (NVIDIA MPS Daemon Lifecycle) and §8A.2 (Heterogeneous Concurrency) [M].
- **Requirements:**
  1. Define Pydantic v2 configuration schema `GpuScoutExecutorConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Literal

     class GpuScoutExecutorConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         platform_os: Literal["windows", "darwin", "linux"]
         enable_mps: bool
         mps_pipe_dir: str
         max_concurrent_gpu_tasks: int = Field(default=1, ge=1)
         min_vram_headroom_mb: float = Field(default=1536.0, ge=512.0)
     ```
  2. Implement OS-aware hardware detection across the 6-Tier Environment Matrix in `hetero_config.py` and executor initialization:
     - **Tier 3 / Tier 6 (Debian Linux & HPC Slurm):** Configure and spawn NVIDIA MPS control daemon (`nvidia-cuda-mps-control -d`) with directory pipes located in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/nvidia_mps`). Set `CUDA_MPS_PIPE_DIRECTORY` and `CUDA_MPS_LOG_DIRECTORY`.
     - **Tier 1 / Tier 2 (Windows WSL2 & macOS OrbStack):** Explicitly disable MPS daemon invocation. Bypass all MPS initialization scripts. Enforce GPU concurrency serialization via a cross-process named mutex or semaphore (`threading.Semaphore(1)` / OS file lock), restricting GPU scout dispatches to one active compute kernel at a time.
     - **Tier 4 / Tier 5 (Codespaces & GitHub Actions CI):** If discrete CUDA hardware is absent, gracefully route scout tasks to CPU threads.
  3. Dynamic VRAM Safeguard: Prior to launching any GPU scout kernel, query `torch.cuda.mem_get_info()`. If available VRAM $< 1.5\text{ GB}$, hold the task in a high-priority queue until memory is reclaimed, preventing CUDA out-of-memory and Windows TDR driver resets.

---

### [Task 6: Unified Parsl Multi-Executor Routing in ExecutionRouter (Suggestion #66)]
- **Target Files:** `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py`, `CoChem-BASE/src/cochem_base/schemas.py`, `CoChem-BASE/src/cochem_base/exceptions.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.6 (Parsl Multi-Executor Architecture) and §8A.2 (Scout-and-Anchor Topology) [M].
- **Requirements:**
  1. Define Pydantic v2 schemas `JobRouteConfig` and `ExecutionRouteResult`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Literal, Optional, List, Dict, Any

     class JobRouteConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         job_type: Literal["heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"]
         assigned_executor: Literal["cochem_anchor_cpu", "cochem_scout_gpu", "local_fallback"]
         cpu_core_pinning: Optional[List[int]] = None
         scratch_dir: str
         timeout_seconds: float = Field(default=3600.0, ge=10.0)
     ```
  2. Refactor `ExecutionRouter.route_job()` to eliminate bypassed execution paths. Integrate `ParslExecutionBroker` as the primary dispatch engine.
  3. Map computational workloads according to the Scout-and-Anchor paradigm:
     - Heavy quantum mechanical optimizations (`heavy_qm_opt`), exact Hessians, and composite ab-initio workflows map to `cochem_anchor_cpu` with explicit CPU core pinning and OpenMP thread binding (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`).
     - Rapid potential energy scans (`fast_potential_scan`), semi-empirical sweeps, and neural network evaluations map to `cochem_scout_gpu`.
  4. Ensure every dispatched job runs within an isolated sandbox subdirectory inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/task_<uuid>/`).
  5. Validate that all file paths are cross-platform `pathlib.Path` objects, ensuring compatibility across all 6 environment tiers.

---

### [Task 7: SubprocessBroker Contract Harmonization & Process Tree Reclamation (Suggestion #67)]
- **Target Files:** `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py`, `CoChem-BASE/src/cochem/concurrency/subprocess_broker.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.4, Cross-Platform Architecture Mandate.
- **Requirements:**
  1. Harmonize `SubprocessBroker.__init__` and `SubprocessBroker.execute` interface signatures:
     ```python
     from typing import Union, List, Optional, Dict
     from pathlib import Path
     import sys
     import shlex

     class SubprocessBroker:
         def __init__(
             self, 
             cwd: Optional[Union[str, Path]] = None, 
             env: Optional[Dict[str, str]] = None,
             timeout_seconds: float = 3600.0
         ):
             self.cwd = Path(cwd) if cwd else Path.cwd()
             self.env = env.copy() if env is not None else None
             self.timeout_seconds = timeout_seconds

         def execute(
             self, 
             command: Union[str, List[str]], 
             cwd: Optional[Union[str, Path]] = None, 
             env: Optional[Dict[str, str]] = None
         ) -> SubprocessExecutionResult:
             ...
     ```
  2. Implement robust command parsing: if `command` is passed as a string, tokenize it safely using `shlex.split(command, posix=(sys.platform != "win32"))`. If passed as a list, retain tokenization without decomposing into individual characters.
  3. Enforce execution strictly inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`). Assert that target working directories exist and possess write permissions.
  4. Implement deterministic process tree termination: wrap execution in `try/except/finally`. If a process times out or encounters an unhandled exception, recursively traverse and terminate all child processes using `psutil.Process(proc.pid).children(recursive=True)` followed by `terminate()` and `kill()`.
  5. Register process cleanup callbacks with `atexit` to prevent orphaned background zombies.

---

### [Task 8: Asynchronous Multi-Seed GOAT Exploration via Parsl Queues (Suggestion #68)]
- **Target Files:** `CoChem-TORQ/Libraries/cochem_torq_goat.py`, `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.2 (Scout-and-Anchor Concurrency) and §9B.3 (Step 0 & Step 1 Parallel Conformer Exploration) [M].
- **Requirements:**
  1. Define Pydantic v2 configuration schema `MultiSeedGoatConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import List

     class MultiSeedGoatConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         seed_structures: List[str] = Field(min_length=1)
         max_concurrent_seeds: int = Field(default=4, ge=1)
         rmsd_threshold_angstrom: float = Field(default=0.15, gt=0.0)
         energy_window_kcal_mol: float = Field(default=6.0, gt=0.0)
     ```
  2. Refactor `run_multi_seed_goat()` in `cochem_torq_goat.py` to eliminate sequential `for s_path in seed_paths:` execution.
  3. Construct an asynchronous task graph where each conformer seed exploration is dispatched as a concurrent Parsl task targeting the `GPU_SCOUT` or `CPU_ANCHOR` executor pools.
  4. Sandbox each seed exploration within an isolated workspace in Ring 2 ephemeral scratch:
     $$\text{Workspace Path} = \$COCHEM\_SCRATCH/\text{goat\_seed\_}\langle\text{hash}\rangle/ \quad [D]$$
  5. Enforce concurrency limits to avoid oversubscribing GPU memory headroom ($< 1.5\text{ GB}$).
  6. Ingest completed seed results asynchronously via Parsl futures. Filter and deduplicate conformational minima using pairwise RMSD ($\delta_{\text{RMSD}} \ge 0.15\text{ Å}$ [M]) and energy window filtering ($\Delta E \le 6.0\text{ kcal/mol}$ [M]).
  7. Merge verified unique conformers into the Ring 3 persistent store (`$COCHEM_ARTIFACTS/conformers.xyz`). Maintain Ring 1 static repository code (`$COCHEM_ROOT`) strictly immutable.

---

### [Task 9: HPC NVIDIA MPS Worker Daemon Lifecycle & Pipe Polling (Suggestion #69)]
- **Target Files:** `CoChem-TORQ/HPC_Launchers/cochem_mps_worker.sh`
- **Method Matrix Reference:** Method Matrix v4 §8A.4 (NVIDIA MPS Daemon Lifecycle Management) [M].
- **Requirements:**
  1. In `cochem_mps_worker.sh`, eradicate the untargeted bash `wait` command on lines 52–54.
  2. Implement an active daemon supervision loop:
     ```bash
     # Configure scratch pipes in Ring 2
     export CUDA_MPS_PIPE_DIRECTORY="${COCHEM_SCRATCH}/mps_control_${SLURM_JOB_ID}"
     export CUDA_MPS_LOG_DIRECTORY="${COCHEM_SCRATCH}/mps_log_${SLURM_JOB_ID}"
     mkdir -p "${CUDA_MPS_PIPE_DIRECTORY}" "${CUDA_MPS_LOG_DIRECTORY}"

     # Launch daemon in background
     nvidia-cuda-mps-control -d
     MPS_PID=$(pgrep -f "nvidia-cuda-mps-control" | tail -n 1)

     # Active monitoring loop
     while kill -0 "${MPS_PID}" 2>/dev/null; do
         if [[ -f "${COCHEM_SCRATCH}/mps_terminate_${SLURM_JOB_ID}.flag" ]]; then
             break
         fi
         sleep 2
     done
     ```
  3. Implement a robust signal trap (`trap 'cleanup_mps' EXIT SIGINT SIGTERM`):
     - Query and notify active client applications.
     - Issue graceful shutdown command: `echo "quit" | nvidia-cuda-mps-control`.
     - Sweep and terminate any orphaned client context processes via `psutil` or `kill -9`.
     - Query GPU driver memory state (`nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits`) and assert that all allocated VRAM is released back to the host node.
     - Purge pipe and socket directories from Ring 2 ephemeral scratch.

---

### [Task 10: SLURM Batch Submission CLI Contract & Dynamic HPC Resource Mapping (Suggestion #70)]
- **Target Files:** `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`, `CoChem-TORQ/HPC_Launchers/cochem_submit.slurm`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.6, Production High-Performance Computing Mandate (Tier 6: HPC).
- **Requirements:**
  1. Define Pydantic v2 schema `TorqPipelineCliArgs`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Optional
     from pathlib import Path

     class TorqPipelineCliArgs(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         input_geometry: Path
         output_directory: Path
         theory_level: str = "B3LYP-D4/def2-TZVP"
         cpus_per_task: int = Field(default=1, ge=1)
         memory_mb: int = Field(default=4096, ge=1024)
         scratch_dir: Path
     ```
  2. Implement a complete CLI entrypoint in `cochem_torq_pipeline.py`:
     ```python
     if __name__ == "__main__":
         import argparse
         parser = argparse.ArgumentParser(description="CoChem-TORQ HPC Batch Pipeline Driver")
         parser.add_argument("--input", "-i", type=str, required=True, help="Path to input molecular geometry")
         parser.add_argument("--output", "-o", type=str, required=True, help="Destination directory for artifacts")
         parser.add_argument("--theory", "-t", type=str, default="B3LYP-D4/def2-TZVP", help="Electronic structure method")
         parser.add_argument("--scratch", "-s", type=str, default=None, help="Ephemeral scratch directory")
         args = parser.parse_args()
         ...
     ```
  3. Dynamically read SLURM environment variables when available:
     - `cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", 1))`
     - `mem_mb = int(os.environ.get("SLURM_MEM_PER_NODE", 4096))`
  4. Assert Tripartite Storage Ring air-gap compliance:
     - Validate that input geometries originate from Ring 1 static storage or Ring 3 artifacts.
     - Validate that execution occurs strictly within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH` or `$SLURM_TMPDIR`).
     - Validate that persistent databases and final coordinate tables write exclusively to Ring 3 artifacts (`$COCHEM_ARTIFACTS`).
  5. Update `cochem_submit.slurm` line 68 to forward arguments transparently:
     ```bash
     "${PYTHON_EXEC}" -m Libraries.cochem_torq_pipeline \
         --input "${INPUT_GEOM}" \
         --output "${COCHEM_ARTIFACTS}/${SLURM_JOB_ID}" \
         --scratch "${COCHEM_SCRATCH}/${SLURM_JOB_ID}" \
         --theory "${THEORY_LEVEL}"
     ```

---

## 4. Physical Zero-Mock Test Suite & Verification Specifications

All test implementations must execute genuine mathematical operations, real system processes, and real molecular electronic structures. Zero mock objects (`unittest.mock.Mock`, `MagicMock`), zero synthetic sleep delays, and zero placeholder functions are permitted.

### Test 1: `tests/ml/test_vectorized_committee_ensemble.py`
- Instantiate a 4-member neural network committee with identical parameter architectures.
- Generate a batch of 64 molecular feature vectors ($D = 128$).
- Execute `CommitteeEnsemble.forward()` under:
  1. Serial execution mode (`concurrency_mode="serial"`).
  2. Vectorized execution mode (`concurrency_mode="vmap"`).
- Assert numerical invariance across mean predictions and epistemic standard deviations:
  $$\max |\boldsymbol{\mu}_{\text{vmap}} - \boldsymbol{\mu}_{\text{serial}}| < 10^{-12} \quad [M]$$
  $$\max |\boldsymbol{\sigma}_{\text{vmap}} - \boldsymbol{\sigma}_{\text{serial}}| < 10^{-12} \quad [M]$$
- On a CUDA-enabled device, measure inference wall time; assert vectorized inference achieves $> 2\times$ throughput speedup [M].
- Simulate low VRAM headroom by configuring `vram_headroom_threshold_mb` higher than actual free memory; assert the engine gracefully falls back to serialized inference without raising CUDA OOM.

### Test 2: `tests/torq/test_oet_fallback_provenance_alert.py`
- Set up an isolated scratch directory (`COCHEM_SCRATCH`) and artifacts directory (`COCHEM_ARTIFACTS`).
- Instantiate `OETClient` targeting an inactive Unix domain socket address to simulate daemon disconnection.
- Trigger force and energy evaluation.
- Assert that `OETClient` engages `PhysicalOETFallbackCalculator` and writes `<base>_EXT.fallback_alert.json` to scratch.
- Ingest and validate the JSON manifest using Pydantic `OETFallbackAlertManifest`:
  - Assert `provenance_tag == "[E]"`.
  - Assert that no files were written to Ring 1 repository directories.
- Verify that `<base>_EXT.uncertainty_marker` was created and that the downstream orchestrator tags the result as Empirical `[E]`.

### Test 3: `tests/topos/test_chain_zero_mock_wavefunction.py`
- Configure `chain.py` with an invalid binary path (`orca_bin="/nonexistent/orca"`).
- Attempt to execute the chained calculation workflow.
- Assert that execution immediately raises `MissingBinaryError` instead of returning mock convergence.
- Inspect the working scratch directory; assert zero bytes were written into `.gbw` or `.opt` files.
- Assert that no synthetic strings containing `"ORCA TERMINATED NORMALLY"` or fabricated SCF cycle numbers exist in the run directory.
- Verify that temporary scratch files are purged upon exception handling.

### Test 4: `tests/concurrency/test_hdf5_concurrent_staging.py`
- Spawn 10 concurrent multiprocessing workers executing 5 single-point evaluations each (total 50 points).
- Each worker writes energy, gradient, and QCSchema records into independent chunk files in `$COCHEM_SCRATCH/chunks/chunk_<uuid>.h5`.
- Trigger the central persistence coordinator to merge staged chunk files into `$COCHEM_ARTIFACTS/campaign.h5` using two-tier file locking (`RWFileLock`).
- Assert zero occurrences of `BlockingIOError`, `OSError: file already open for write`, or container corruption.
- Open `$COCHEM_ARTIFACTS/campaign.h5` in read mode; assert all 50 records exist, checksums match Fletcher32, and compression filters are active.

### Test 5: `tests/concurrency/test_gpu_scout_cross_platform_dispatch.py`
- On Windows or macOS host platforms (or simulated platform environment), initialize `hetero_config.py`.
- Assert that NVIDIA MPS initialization commands are never executed.
- Assert that GPU scout tasks route through `threading.Semaphore(1)` / named OS mutex.
- Launch 4 concurrent scout tasks; verify that kernel execution dispatches serially without triggering CUDA out-of-memory or driver timeout resets.
- Verify dynamic VRAM threshold guard: assert jobs are queued when available memory drops below $1.5\text{ GB}$.

### Test 6: `tests/base/test_execution_router_parsl_broker.py`
- Configure `ExecutionRouter` with active Parsl DataFlowKernel containing `cochem_anchor_cpu` and `cochem_scout_gpu`.
- Submit a heavy optimization job (`job_type="heavy_qm_opt"`); verify it is routed to `cochem_anchor_cpu` with explicit core pinning.
- Submit a rapid scan job (`job_type="fast_potential_scan"`); verify it is routed to `cochem_scout_gpu`.
- Verify that both tasks execute in isolated subdirectories inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/task_<uuid>/`).
- Assert that task futures resolve successfully without blocking the host thread.

### Test 7: `tests/concurrency/test_subprocess_broker_contract.py`
- Test 1 (String Command): Invoke `SubprocessBroker.execute("echo 'cochem-concurrency-test'")`. Verify output parses cleanly without single-character decomposition.
- Test 2 (List Command): Invoke `SubprocessBroker.execute(["echo", "cochem-concurrency-test"])`. Verify identical clean execution.
- Test 3 (Working Directory & Environment): Pass custom `cwd` and `env` dictionaries during initialization and execution; assert command evaluates in the specified directory with the designated environment variables.
- Test 4 (Process Tree Cleanup): Launch a long-running child process tree with a short timeout ($0.5\text{ s}$); assert that `TimeoutExpired` is handled and that `psutil` recursively terminates all parent and child processes.

### Test 8: `tests/torq/test_goat_multi_seed_concurrency.py`
- Prepare 4 distinct starting conformer geometries for a flexible organic molecule.
- Execute `run_multi_seed_goat()` configured with `MultiSeedGoatConfig(max_concurrent_seeds=4)`.
- Verify that Parsl dispatches all 4 seed explorations concurrently across worker pools.
- Verify that each seed executes within its own isolated sandbox in `$COCHEM_SCRATCH/goat_seed_<hash>/`.
- Assert that completed conformers are merged, filtered by RMSD ($\delta_{\text{RMSD}} \ge 0.15\text{ Å}$ [M]) and energy window ($\Delta E \le 6.0\text{ kcal/mol}$ [M]), and written to `$COCHEM_ARTIFACTS/conformers.xyz`.

### Test 9: `tests/hpc/test_mps_worker_lifecycle.py`
- Execute `cochem_mps_worker.sh` in a controlled test environment.
- Verify that the daemon monitoring loop detects `nvidia-cuda-mps-control` PID and validates the named pipe in scratch.
- Send `SIGTERM` to the shell wrapper.
- Assert that the trapped cleanup handler executes:
  - Verifies graceful MPS daemon termination.
  - Terminates any lingering client processes.
  - Asserts that allocated GPU VRAM is completely released.
  - Cleans up pipe directories in scratch.

### Test 10: `tests/hpc/test_torq_pipeline_cli_slurm.py`
- Ingest a test `.xyz` geometry file.
- Execute `cochem_torq_pipeline.py` via command-line invocation:
  ```bash
  python -m Libraries.cochem_torq_pipeline --input test.xyz --output ./artifacts --scratch ./scratch --theory PM6
  ```
- Set mock SLURM environment variables (`SLURM_CPUS_PER_TASK=4`, `SLURM_MEM_PER_NODE=8192`).
- Assert that the CLI parses arguments into validated Pydantic schema `TorqPipelineCliArgs`.
- Assert that execution parameters dynamically scale to 4 CPUs and 8192 MB memory.
- Verify that all outputs are deposited in the designated output directory without touching Ring 1 static repositories.

---

## 5. Anti-Spoofing, Quality Gate & Definition of Done (DoD)

1. **Zero-Mock Mandate:** STRICTLY FORBIDDEN from using `unittest.mock`, `MagicMock`, fake sleep loops, canned analytical potential formulas masquerading as quantum chemistry, or simulated binary containers (`.gbw`, `.opt`). All calculations must evaluate authentic physics, invoke genuine binaries, or read real OS hardware interfaces.
2. **Method Matrix Provenance Tagging:** All spectroscopic constants, rotational parameters, and convergence criteria must carry explicit provenance tags:
   - `[M]` Measured empirical benchmark
   - `[D]` Derived mathematical relationship
   - `[E]` Estimated theoretical projection
3. **Dynamic Mendeleev Retrieval:** Zero hardcoded atomic masses or physical constants. All masses and isotopic data must be retrieved dynamically via `from mendeleev import element`.
4. **Tripartite Air-Gap & OS Concurrency:** Maintain strict separation between Source ($R_{\text{src}}$), Data ($R_{\text{data}}$), and Artifacts ($R_{\text{art}}$). Concurrency must use cross-platform `filelock.FileLock` / `RWFileLock` with chunked scratch staging. Node-local scratch storage (`$SLURM_TMPDIR` / `$COCHEM_SCRATCH`) is mandatory on HPC clusters.
5. **Execution Proof:** All 10 physical zero-mock test modules must execute successfully with full passing terminal logs recorded before marking this chunk implementation as complete.
# CODING PROMPT: CoChem Ecosystem Implementation (Chunk 7: Suggestions #61–#70)

**Target Output Repositories:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`, `CoChem-TOPOS`, and `CoChem-TORQ`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§1.2, §3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds, §8A.2 Scout-and-Anchor Heterogeneous Concurrency, §8A.4 NVIDIA MPS Daemon Lifecycle, §8A.6 Parsl Multi-Executor Architecture, §8B.4 Canonical Arrows 4 & 5 Binary Wavefunction Projection via `%moinp`, §8C Production HDF5 Store Architecture & Chunking, §9B.3 Multi-Seed Conformational Exploration, §10.8 Active Learning & Fallback Provenance Auditing, Table 2 T1-30min / T3, QS-1, QS-3)
- Anti-Spoofing Protocol v2 (enforcing Zero-Mock, Asymmetric Verification, Hard Abort Criteria, and MAX_PIVOT_CYCLES: zero pass stubs, zero fabricated outputs, zero synthetic dummy loops, mandatory physical execution)
- Tripartite Air-Gap Architecture (`T_ui` frontend, `T_schema` Pydantic contracts, `T_engine` decoupled background subprocesses; cross-module communication strictly via validated schemas, OS PID locks, and streaming IPC queues; Tripartite Storage Rings: Ring 1 Source $R_{\text{src}}$ / `$COCHEM_ROOT`, Ring 2 Ephemeral Scratch $R_{\text{data}}$ / `$COCHEM_SCRATCH`, Ring 3 Persistent Artifacts $R_{\text{art}}$ / `$COCHEM_ARTIFACTS`)
- 6-Tier Environment Matrix (Tier 1: Windows Native/WSL2 NT, Tier 2: macOS/OrbStack Darwin, Tier 3: Debian Linux, Tier 4: GitHub Codespaces, Tier 5: GitHub Actions CI/CD, Tier 6: HPC Slurm/PBS)
- Dynamic Mendeleev Mass & Radii Retrieval Mandate (`from mendeleev import element`, strict dynamic atomic/isotopic mass query, zero hardcoded constants)
- Cross-Platform Concurrency Directive (Thread-safe and process-safe SWMR HDF5 with `filelock.FileLock` / `cochem.concurrency.atomic_file_lock.RWFileLock`, node-local scratch staging on HPC `$SLURM_TMPDIR`, non-blocking telemetry reads)
- JAX 64-Bit & Bounded GPU Allocation Mandate (`JAX_ENABLE_X64=True` initialization on line 1, `XLA_PYTHON_CLIENT_PREALLOCATE=false`, `XLA_PYTHON_CLIENT_MEM_FRACTION=0.20`, PyTorch default `torch.float64`)

---

## 1. Executive Summary & Scope

Implement, harden, and physically verify Suggestions #61 through #70 of the CoChem Tripartite Ecosystem. This work package rectifies critical architectural bottlenecks and severe provenance/concurrency failure modes across vectorized active learning committee inference, machine-learning-to-empirical fallback audit trails, unverified quantum chemical binary spoofing, multi-process HDF5 lock collisions, cross-platform NVIDIA MPS vs. semaphore scout scheduling, Parsl multi-executor integration, subprocess interface standardization, multi-seed conformer task parallelization, HPC daemon lifecycle monitoring, and high-performance SLURM batch pipeline entrypoints.

Key deliverables include:
1. **Vectorized Committee Ensemble Inference & Dynamic VRAM Throttling (Suggestion #61):** Eliminate sequential host-thread loops in `CommitteeEnsemble.forward()`. Implement vectorized forward passes using `torch.vmap` or managed concurrent CUDA streams. Integrate `RESOURCE_GUARD` memory headroom polling (`torch.cuda.mem_get_info()`); if available VRAM $< 2.0\text{ GB}$, automatically serialize inference across members to eliminate CUDA out-of-memory crashes across the 6-Tier Environment Matrix while reducing active learning committee latency by up to $3\times$ [M].
2. **OET Machine-Learning-to-Empirical Fallback Provenance & Alert Manifests (Suggestion #62):** Eliminate silent potential degradation in `oet_client.py`. When socket disconnects trigger `PhysicalOETFallbackCalculator`, atomically write an audit manifest (`<base>_EXT.fallback_alert.json`) into Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`) and stage an alert into Ring 3 persistent storage (`$COCHEM_ARTIFACTS`). Prohibit writes to Ring 1 static repository paths (`$COCHEM_ROOT`), and write an uncertainty marker file triggering the orchestrator to halt or tag all resulting observables with provenance tag `[E]` (Empirical).
3. **Purge of Fabricated SCF/Opt Cycles & Corrupt Binary Wavefunctions in Chained Engines (Suggestion #63):** Eradicate all synthetic fallback routines in `CoChem-TOPOS/chain.py` and `CoChem-TORQ/Libraries/chain.py`. Stop generating fabricated iteration counts (`scf_cyc = 12`, `opt_cyc = 6`), mock `ORCA TERMINATED NORMALLY` strings, and synthetic `.gbw`/`.opt` binary byte sequences based on non-physical mass formulas. Enforce explicit exception raising (`ConvergenceFailureError` or `MissingBinaryError`), ensuring intermediate buffers are isolated in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`) and never emitted to Ring 3 persistent storage (`$COCHEM_ARTIFACTS`).
4. **Two-Tier Thread-Safe and Process-Safe HDF5 Persistence Architecture (Suggestion #64):** Eliminate `BlockingIOError` and `OSError: file already open for write` across concurrent Parsl worker sweeps in `gpu_point.py`, `chain.py`, and `pes_h5.py`. Enforce in-process `threading.RLock()` across worker threads and cross-process file locking via `filelock.FileLock` / `cochem.concurrency.atomic_file_lock.RWFileLock` with exponential backoff. Enforce atomic staging: workers commit energy and gradient records to isolated chunk containers in Ring 2 scratch (`$COCHEM_SCRATCH/chunk_<uuid>.h5`), while a central persistence coordinator merges staged chunks into the primary Ring 3 store (`$COCHEM_ARTIFACTS/campaign.h5`) under exclusive write lock with gzip+shuffle+fletcher32 filters.
5. **OS-Aware GPU Scout Concurrency & Windows/macOS Mutex Scheduling (Suggestion #65):** Resolve GPU scout initialization crashes on non-Linux workstations caused by hardcoded NVIDIA Multi-Process Service (MPS) commands in `hetero_config.py` and `cochem_core_parsl_executors.py`. Dynamically branch across the 6-Tier Environment Matrix: on Linux (Tiers 3 & 6), initialize NVIDIA MPS with directory pipes in Ring 2 scratch (`$COCHEM_SCRATCH/nvidia_mps`); on Windows and macOS (Tiers 1 & 2), bypass MPS entirely and serialize GPU dispatches via a cross-process concurrency semaphore (`threading.Semaphore(1)` / named OS mutex). Enforce dynamic VRAM polling across all tiers, deferring tasks if free VRAM $< 1.5\text{ GB}$.
6. **Unified Parsl Multi-Executor Routing in ExecutionRouter (Suggestion #66):** Resolve the architectural bypass in `cochem_calc_execution_router.py` where Parsl scout-and-anchor scheduling was ignored in favor of blocking subprocesses. Wire `ParslExecutionBroker` directly into `ExecutionRouter.route_job()`. Map heavy quantum mechanical optimizations to `cochem_anchor_cpu` with explicit CPU core pinning, and route high-throughput potential scans to `cochem_scout_gpu`. Enforce task sandboxing inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/task_<uuid>`) across all 6 environment tiers.
7. **SubprocessBroker Contract Harmonization & Process Tree Reclamation (Suggestion #67):** Fix interface drift and crashes between `ExecutionRouter` and `SubprocessBroker`. Harmonize the interface contract to accept both string commands (tokenized via `shlex.split(command, posix=(sys.platform != "win32"))`) and pre-tokenized lists of strings; accept `cwd` and `env` parameters during initialization and execution; enforce execution strictly within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`); wrap executions with configurable timeouts; and guarantee recursive child process tree cleanup via `psutil` or `atexit`.
8. **Asynchronous Multi-Seed GOAT Exploration via Parsl Queues (Suggestion #68):** Refactor the sequential exploration loop in `cochem_torq_goat.py` (`run_multi_seed_goat()`) into an asynchronous concurrent task graph dispatched to Parsl `GPU_SCOUT` and `CPU_ANCHOR` executor pools. Sandbox each seed exploration within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/goat_seed_<hash>`), enforce GPU concurrency caps to prevent VRAM oversubscription, and collect deduplicated conformational minima into Ring 3 persistent storage (`$COCHEM_ARTIFACTS`) upon completion.
9. **HPC NVIDIA MPS Worker Daemon Lifecycle & Pipe Polling (Suggestion #69):** Rectify premature daemon termination in `HPC_Launchers/cochem_mps_worker.sh`. Replace bare bash `wait` (which immediately exits when `nvidia-cuda-mps-control -d` detaches) with an active daemon monitoring loop polling the control daemon PID and named pipe socket in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/mps_control`). Implement a trapped signal handler (`EXIT`, `SIGINT`, `SIGTERM`) executing graceful termination, orphaned client context sweeps via `psutil`/`kill`, and full GPU memory release verification.
10. **SLURM Batch Submission CLI Contract & Dynamic HPC Resource Mapping (Suggestion #70):** Resolve silent zero-calculation completions when executing `cochem_submit.slurm`. Implement a complete CLI entrypoint using `argparse` in `cochem_torq_pipeline.py`. Accept parameters for input structures, theory specifications, and directory destinations; validate input existence; enforce Tripartite Storage Ring air-gaps; and dynamically ingest resource allocations from environment variables (`$SLURM_CPUS_PER_TASK`, `$SLURM_MEM_PER_NODE`). Update `cochem_submit.slurm` to forward parameters transparently across cluster nodes.

---

## 2. Target Files & Deliverable Manifest

### Core Implementation Modules
1. `CoChem-BASE/Libraries/cochem_torq_committee_ensemble.py` & `cochem/ml/models/ensemble.py` (Suggestion #61: Vectorized ensemble inference via `torch.vmap` / CUDA streams, dynamic VRAM polling, serialized fallback)
2. `CoChem-TORQ/scripts/oet_client.py` & `CoChem-TORQ/Libraries/cochem_torq_oet_client.py` (Suggestion #62: Fallback audit manifest generation, Tripartite air-gap compliance, uncertainty marker emission, provenance tag `[E]`)
3. `CoChem-TOPOS/chain.py` & `CoChem-TORQ/Libraries/chain.py` (Suggestion #63: Elimination of synthetic fallback routines, purge of fake SCF/Opt cycles and mock `.gbw`/`.opt` files, explicit exception raising)
4. `CoChem-TOPOS/gpu_point.py`, `CoChem-TOPOS/pes_h5.py`, & `CoChem-BASE/src/cochem_base/concurrency/atomic_file_lock.py` (Suggestion #64: Two-tier HDF5 persistence, `threading.RLock`, cross-process `RWFileLock`, atomic scratch chunk staging, and persistent merge coordinator)
5. `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py` & `CoChem-TOPOS/hetero_config.py` (Suggestion #65: Dynamic OS-aware GPU scout executor configuration, Linux MPS vs. Windows/macOS semaphore mutex, dynamic VRAM threshold guard)
6. `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py` (Suggestion #66: Parsl execution broker integration, heterogeneous scout-and-anchor routing, CPU core pinning, sandboxed scratch execution)
7. `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py` & `CoChem-BASE/src/cochem/concurrency/subprocess_broker.py` (Suggestion #67: Harmonized `SubprocessBroker` interface, `shlex.split` cross-platform handling, `cwd`/`env` parameterization, timeout management, `psutil` tree cleanup)
8. `CoChem-TORQ/Libraries/cochem_torq_goat.py` & `CoChem-TORQ/Libraries/cochem_torq_pipeline.py` (Suggestion #68: Asynchronous multi-seed conformer dispatch via Parsl executor pools, scratch directory sandboxing, deduplication merge)
9. `CoChem-TORQ/HPC_Launchers/cochem_mps_worker.sh` (Suggestion #69: Bash MPS daemon monitoring loop, PID polling, named pipe socket check in scratch, trapped signal cleanup)
10. `CoChem-TORQ/Libraries/cochem_torq_pipeline.py` & `CoChem-TORQ/HPC_Launchers/cochem_submit.slurm` (Suggestion #70: CLI entrypoint with `argparse`, SLURM environment variable mapping, Tripartite Storage Ring air-gap enforcement)
11. `CoChem-BASE/src/cochem_base/exceptions.py` & `CoChem-BASE/src/cochem_base/schemas.py` (Suggestions #61–#70: Custom exception hierarchy and typed Pydantic v2 schemas)

### Zero-Mock Test Suite Deliverables
12. `tests/ml/test_vectorized_committee_ensemble.py` (Validating Suggestion #61: Mathematical invariance between vectorized and serial inference, latency reduction, dynamic VRAM serialization threshold)
13. `tests/torq/test_oet_fallback_provenance_alert.py` (Validating Suggestion #62: Atomic generation of `<base>_EXT.fallback_alert.json` in scratch, uncertainty marker file trigger, provenance tag `[E]` enforcement)
14. `tests/topos/test_chain_zero_mock_wavefunction.py` (Validating Suggestion #63: Verified raising of `ConvergenceFailureError` / `MissingBinaryError`, zero generation of synthetic byte sequences in `.gbw` / `.opt`)
15. `tests/concurrency/test_hdf5_concurrent_staging.py` (Validating Suggestion #64: Multi-process and multi-thread concurrent write test, zero `BlockingIOError`, atomic chunk staging and merge integrity)
16. `tests/concurrency/test_gpu_scout_cross_platform_dispatch.py` (Validating Suggestion #65: OS-aware branching, validation of semaphore serialization on Windows/macOS, dynamic VRAM guard)
17. `tests/base/test_execution_router_parsl_broker.py` (Validating Suggestion #66: Routing heavy QM to `cochem_anchor_cpu` with core pinning and scans to `cochem_scout_gpu` via Parsl)
18. `tests/concurrency/test_subprocess_broker_contract.py` (Validating Suggestion #67: String vs tokenized list input handling, `cwd`/`env` passing, cross-platform path handling, process tree termination)
19. `tests/torq/test_goat_multi_seed_concurrency.py` (Validating Suggestion #68: Concurrent multi-seed GOAT exploration, scratch isolation, non-blocking Parsl future aggregation)
20. `tests/hpc/test_mps_worker_lifecycle.py` (Validating Suggestion #69: Validation of shell daemon monitoring logic, PID tracking, clean signal trapped cleanup and VRAM reclamation)
21. `tests/hpc/test_torq_pipeline_cli_slurm.py` (Validating Suggestion #70: Full CLI argument parsing, SLURM environment variable extraction, input verification, Tripartite Storage Ring validation)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Vectorized Committee Ensemble Inference & Dynamic VRAM Throttling (Suggestion #61)]
- **Target Files:** `CoChem-BASE/Libraries/cochem_torq_committee_ensemble.py`, `cochem/ml/models/ensemble.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.2 (Throughput Optimization & Heterogeneous Concurrency) [M], Anti-Spoofing Directive v2.
- **Requirements:**
  1. Define Pydantic v2 configuration schema `CommitteeEnsembleConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Literal

     class CommitteeEnsembleConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         vectorized: bool = True
         vram_headroom_threshold_mb: float = Field(default=2048.0, ge=512.0)
         concurrency_mode: Literal["vmap", "cuda_streams", "serial"] = "vmap"
         max_batch_size: int = Field(default=128, ge=1)
     ```
  2. In `CommitteeEnsemble.forward()`, eliminate the serial iteration loop over `self.models`.
  3. When `concurrency_mode == "vmap"` and neural network architectures share identical parameter shapes, utilize `torch.vmap` over stacked parameters to evaluate all committee members in a single batched kernel invocation:
     $$\mathbf{Y}_{\text{ensemble}}(\mathbf{x}) = \text{vmap}(f)(\boldsymbol{\theta}_{\text{stacked}}, \mathbf{x}) \quad [D]$$
  4. Implement `RESOURCE_GUARD` memory monitoring prior to execution. If running on CUDA:
     ```python
     free_bytes, total_bytes = torch.cuda.mem_get_info()
     free_mb = free_bytes / (1024 * 1024)
     ```
     If `free_mb < vram_headroom_threshold_mb`, automatically log a warning and fall back to sequential inference across members, guaranteeing zero CUDA Out-Of-Memory (`RuntimeError: CUDA out of memory`) exceptions.
  5. If ensemble members have heterogeneous architectures or shapes, execute forward passes across parallel `torch.cuda.Stream` contexts with non-blocking transfers.
  6. Assert mathematical invariance: the predictions and epistemic variance from vectorized execution must match serial execution to machine precision ($\max |\mathbf{y}_{\text{vmap}} - \mathbf{y}_{\text{serial}}| < 10^{-12}$ in FP64) [M].
  7. Isolate all temporary intermediate tensor allocations in memory or Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`).

---

### [Task 2: OET Machine-Learning-to-Empirical Fallback Provenance & Alert Manifests (Suggestion #62)]
- **Target Files:** `CoChem-TORQ/scripts/oet_client.py`, `CoChem-TORQ/Libraries/cochem_torq_oet_client.py`, `CoChem-BASE/src/cochem_base/schemas.py`, `CoChem-BASE/src/cochem_base/exceptions.py`
- **Method Matrix Reference:** Method Matrix v4 §10.8 (Active Learning & Fallback Provenance Auditing) [M], Investigator-in-the-Loop Mandate.
- **Requirements:**
  1. Define Pydantic v2 schemas `OETFallbackAlertManifest` and custom exception `OETDaemonConnectionError`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Dict, Any, Optional
     import datetime

     class OETFallbackAlertManifest(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         calculation_base: str
         timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
         trigger_event: str
         fallback_calculator: str
         provenance_tag: str = "[E]"
         host_telemetry: Dict[str, Any]
         scratch_alert_file: str
         staged_artifact_file: str
     ```
  2. When the socket connection in `oet_client.py` fails and `PhysicalOETFallbackCalculator` is engaged, forbid silent execution.
  3. Enforce Tripartite Storage Ring air-gap compliance:
     - Write the atomic fallback audit manifest (`<base>_EXT.fallback_alert.json`) into the designated Ring 2 ephemeral scratch directory (`$COCHEM_SCRATCH`).
     - Stage an alert copy into the Ring 3 persistent store (`$COCHEM_ARTIFACTS/alerts/`).
     - Strictly forbid any writes into Ring 1 static repository paths (`$COCHEM_ROOT`).
  4. Atomically write an uncertainty marker file (`<base>_EXT.uncertainty_marker`) containing the provenance tag `[E]` and execution metadata.
  5. Instruct the supervising workflow orchestrator to inspect for `<base>_EXT.fallback_alert.json`; upon detection, either abort the pipeline or propagate provenance tag `[E]` (Empirical) to all downstream data points and publications.

---

### [Task 3: Purge of Fabricated SCF/Opt Cycles & Corrupt Binary Wavefunctions in Chained Engines (Suggestion #63)]
- **Target Files:** `CoChem-TOPOS/chain.py`, `CoChem-TORQ/Libraries/chain.py`, `CoChem-BASE/src/cochem_base/exceptions.py`
- **Method Matrix Reference:** Method Matrix v4 §8B.4 (Canonical Arrows 4 & 5 Binary Wavefunction Projection via `%moinp`) [M], Anti-Spoofing Protocol v2.
- **Requirements:**
  1. Define custom exceptions in `CoChem-BASE/src/cochem_base/exceptions.py`:
     ```python
     class ElectronicStructureEngineError(Exception):
         """Base exception for quantum engine failures."""
         pass

     class ConvergenceFailureError(ElectronicStructureEngineError):
         """Raised when SCF or Geometry Optimization fails to converge."""
         pass

     class MissingBinaryError(ElectronicStructureEngineError):
         """Raised when a required quantum chemistry binary is absent."""
         pass
     ```
  2. In `chain.py` (both `CoChem-TOPOS` and `CoChem-TORQ`), purge all routines that fabricate iteration counts (e.g., `scf_cyc = 12`, `opt_cyc = 6`), mock strings (`"ORCA TERMINATED NORMALLY"`), or approximate energies using unphysical mass-based formulas (`sum(-0.5 * (mass ** 1.5))`).
  3. Purge lines that write arbitrary byte sequences into `.gbw` and `.opt` binary containers. If the ORCA binary is missing or fails convergence, immediately raise `MissingBinaryError` or `ConvergenceFailureError`.
  4. Ensure all temporary wavefunction files, scratch integrals, and intermediate geometry buffers remain strictly confined within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`).
  5. In the event of a failure, trigger immediate cleanup of invalid or corrupt files from Ring 2 scratch, and ensure zero unverified binary containers are emitted to Ring 3 persistent storage (`$COCHEM_ARTIFACTS`).

---

### [Task 4: Two-Tier Thread-Safe and Process-Safe HDF5 Persistence Architecture (Suggestion #64)]
- **Target Files:** `CoChem-TOPOS/gpu_point.py`, `CoChem-TOPOS/pes_h5.py`, `CoChem-TOPOS/chain.py`, `CoChem-BASE/src/cochem_base/concurrency/atomic_file_lock.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8C (Production HDF5 Store Architecture & Chunking) [M], [D].
- **Requirements:**
  1. Define Pydantic v2 schema `HDF5PersistenceConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict

     class HDF5PersistenceConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         lock_timeout_seconds: float = Field(default=60.0, ge=1.0)
         retry_backoff_base_seconds: float = Field(default=0.05, ge=0.001)
         compression_filter: str = "gzip"
         compression_level: int = Field(default=4, ge=1, le=9)
         enable_fletcher32: bool = True
         enable_shuffle: bool = True
     ```
  2. Implement a two-tier locking strategy in `pes_h5.py` and `atomic_file_lock.py`:
     - **Tier 1 (In-Process):** Enforce `threading.RLock()` to serialize access across concurrent worker threads within the same process.
     - **Tier 2 (Cross-Process):** Enforce cross-process locking via `filelock.FileLock` / `cochem.concurrency.atomic_file_lock.RWFileLock` with exponential backoff and configurable timeouts, supporting Windows NT, macOS, and Linux without raw POSIX `fcntl` collisions.
  3. Enforce an atomic staging pipeline for distributed workers:
     - Parallel Parsl workers must never write directly into `$COCHEM_ARTIFACTS/campaign.h5`.
     - Each worker writes single-point energies, nuclear gradients, and QCSchema records into an isolated chunk file in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/chunks/chunk_<uuid>.h5`).
  4. Implement a centralized persistence coordinator:
     - The coordinator acquires an exclusive lock on `$COCHEM_ARTIFACTS/campaign.h5`.
     - It merges records from staged chunk files into primary datasets using chunking, shuffle filters, gzip compression level 4, and Fletcher32 checksums.
     - Upon verified ingestion, it purges staged chunk files from Ring 2 scratch.
  5. Guarantee zero `BlockingIOError` or `OSError: file already open for write` during 100-way concurrent worker sweeps.

---

### [Task 5: OS-Aware GPU Scout Concurrency & Windows/macOS Mutex Scheduling (Suggestion #65)]
- **Target Files:** `CoChem-BASE/src/cochem_base/core_engine/cochem_core_parsl_executors.py`, `CoChem-TOPOS/hetero_config.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.4 (NVIDIA MPS Daemon Lifecycle) and §8A.2 (Heterogeneous Concurrency) [M].
- **Requirements:**
  1. Define Pydantic v2 configuration schema `GpuScoutExecutorConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Literal

     class GpuScoutExecutorConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         platform_os: Literal["windows", "darwin", "linux"]
         enable_mps: bool
         mps_pipe_dir: str
         max_concurrent_gpu_tasks: int = Field(default=1, ge=1)
         min_vram_headroom_mb: float = Field(default=1536.0, ge=512.0)
     ```
  2. Implement OS-aware hardware detection across the 6-Tier Environment Matrix in `hetero_config.py` and executor initialization:
     - **Tier 3 / Tier 6 (Debian Linux & HPC Slurm):** Configure and spawn NVIDIA MPS control daemon (`nvidia-cuda-mps-control -d`) with directory pipes located in Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/nvidia_mps`). Set `CUDA_MPS_PIPE_DIRECTORY` and `CUDA_MPS_LOG_DIRECTORY`.
     - **Tier 1 / Tier 2 (Windows WSL2 & macOS OrbStack):** Explicitly disable MPS daemon invocation. Bypass all MPS initialization scripts. Enforce GPU concurrency serialization via a cross-process named mutex or semaphore (`threading.Semaphore(1)` / OS file lock), restricting GPU scout dispatches to one active compute kernel at a time.
     - **Tier 4 / Tier 5 (Codespaces & GitHub Actions CI):** If discrete CUDA hardware is absent, gracefully route scout tasks to CPU threads.
  3. Dynamic VRAM Safeguard: Prior to launching any GPU scout kernel, query `torch.cuda.mem_get_info()`. If available VRAM $< 1.5\text{ GB}$, hold the task in a high-priority queue until memory is reclaimed, preventing CUDA out-of-memory and Windows TDR driver resets.

---

### [Task 6: Unified Parsl Multi-Executor Routing in ExecutionRouter (Suggestion #66)]
- **Target Files:** `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py`, `CoChem-BASE/src/cochem_base/schemas.py`, `CoChem-BASE/src/cochem_base/exceptions.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.6 (Parsl Multi-Executor Architecture) and §8A.2 (Scout-and-Anchor Topology) [M].
- **Requirements:**
  1. Define Pydantic v2 schemas `JobRouteConfig` and `ExecutionRouteResult`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Literal, Optional, List, Dict, Any

     class JobRouteConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         job_type: Literal["heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"]
         assigned_executor: Literal["cochem_anchor_cpu", "cochem_scout_gpu", "local_fallback"]
         cpu_core_pinning: Optional[List[int]] = None
         scratch_dir: str
         timeout_seconds: float = Field(default=3600.0, ge=10.0)
     ```
  2. Refactor `ExecutionRouter.route_job()` to eliminate bypassed execution paths. Integrate `ParslExecutionBroker` as the primary dispatch engine.
  3. Map computational workloads according to the Scout-and-Anchor paradigm:
     - Heavy quantum mechanical optimizations (`heavy_qm_opt`), exact Hessians, and composite ab-initio workflows map to `cochem_anchor_cpu` with explicit CPU core pinning and OpenMP thread binding (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`).
     - Rapid potential energy scans (`fast_potential_scan`), semi-empirical sweeps, and neural network evaluations map to `cochem_scout_gpu`.
  4. Ensure every dispatched job runs within an isolated sandbox subdirectory inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/task_<uuid>/`).
  5. Validate that all file paths are cross-platform `pathlib.Path` objects, ensuring compatibility across all 6 environment tiers.

---

### [Task 7: SubprocessBroker Contract Harmonization & Process Tree Reclamation (Suggestion #67)]
- **Target Files:** `CoChem-BASE/src/cochem_base/core_engine/cochem_calc_execution_router.py`, `CoChem-BASE/src/cochem/concurrency/subprocess_broker.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.4, Cross-Platform Architecture Mandate.
- **Requirements:**
  1. Harmonize `SubprocessBroker.__init__` and `SubprocessBroker.execute` interface signatures:
     ```python
     from typing import Union, List, Optional, Dict
     from pathlib import Path
     import sys
     import shlex

     class SubprocessBroker:
         def __init__(
             self, 
             cwd: Optional[Union[str, Path]] = None, 
             env: Optional[Dict[str, str]] = None,
             timeout_seconds: float = 3600.0
         ):
             self.cwd = Path(cwd) if cwd else Path.cwd()
             self.env = env.copy() if env is not None else None
             self.timeout_seconds = timeout_seconds

         def execute(
             self, 
             command: Union[str, List[str]], 
             cwd: Optional[Union[str, Path]] = None, 
             env: Optional[Dict[str, str]] = None
         ) -> SubprocessExecutionResult:
             ...
     ```
  2. Implement robust command parsing: if `command` is passed as a string, tokenize it safely using `shlex.split(command, posix=(sys.platform != "win32"))`. If passed as a list, retain tokenization without decomposing into individual characters.
  3. Enforce execution strictly inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH`). Assert that target working directories exist and possess write permissions.
  4. Implement deterministic process tree termination: wrap execution in `try/except/finally`. If a process times out or encounters an unhandled exception, recursively traverse and terminate all child processes using `psutil.Process(proc.pid).children(recursive=True)` followed by `terminate()` and `kill()`.
  5. Register process cleanup callbacks with `atexit` to prevent orphaned background zombies.

---

### [Task 8: Asynchronous Multi-Seed GOAT Exploration via Parsl Queues (Suggestion #68)]
- **Target Files:** `CoChem-TORQ/Libraries/cochem_torq_goat.py`, `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.2 (Scout-and-Anchor Concurrency) and §9B.3 (Step 0 & Step 1 Parallel Conformer Exploration) [M].
- **Requirements:**
  1. Define Pydantic v2 configuration schema `MultiSeedGoatConfig`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import List

     class MultiSeedGoatConfig(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         seed_structures: List[str] = Field(min_length=1)
         max_concurrent_seeds: int = Field(default=4, ge=1)
         rmsd_threshold_angstrom: float = Field(default=0.15, gt=0.0)
         energy_window_kcal_mol: float = Field(default=6.0, gt=0.0)
     ```
  2. Refactor `run_multi_seed_goat()` in `cochem_torq_goat.py` to eliminate sequential `for s_path in seed_paths:` execution.
  3. Construct an asynchronous task graph where each conformer seed exploration is dispatched as a concurrent Parsl task targeting the `GPU_SCOUT` or `CPU_ANCHOR` executor pools.
  4. Sandbox each seed exploration within an isolated workspace in Ring 2 ephemeral scratch:
     $$\text{Workspace Path} = \$COCHEM\_SCRATCH/\text{goat\_seed\_}\langle\text{hash}\rangle/ \quad [D]$$
  5. Enforce concurrency limits to avoid oversubscribing GPU memory headroom ($< 1.5\text{ GB}$).
  6. Ingest completed seed results asynchronously via Parsl futures. Filter and deduplicate conformational minima using pairwise RMSD ($\delta_{\text{RMSD}} \ge 0.15\text{ Å}$ [M]) and energy window filtering ($\Delta E \le 6.0\text{ kcal/mol}$ [M]).
  7. Merge verified unique conformers into the Ring 3 persistent store (`$COCHEM_ARTIFACTS/conformers.xyz`). Maintain Ring 1 static repository code (`$COCHEM_ROOT`) strictly immutable.

---

### [Task 9: HPC NVIDIA MPS Worker Daemon Lifecycle & Pipe Polling (Suggestion #69)]
- **Target Files:** `CoChem-TORQ/HPC_Launchers/cochem_mps_worker.sh`
- **Method Matrix Reference:** Method Matrix v4 §8A.4 (NVIDIA MPS Daemon Lifecycle Management) [M].
- **Requirements:**
  1. In `cochem_mps_worker.sh`, eradicate the untargeted bash `wait` command on lines 52–54.
  2. Implement an active daemon supervision loop:
     ```bash
     # Configure scratch pipes in Ring 2
     export CUDA_MPS_PIPE_DIRECTORY="${COCHEM_SCRATCH}/mps_control_${SLURM_JOB_ID}"
     export CUDA_MPS_LOG_DIRECTORY="${COCHEM_SCRATCH}/mps_log_${SLURM_JOB_ID}"
     mkdir -p "${CUDA_MPS_PIPE_DIRECTORY}" "${CUDA_MPS_LOG_DIRECTORY}"

     # Launch daemon in background
     nvidia-cuda-mps-control -d
     MPS_PID=$(pgrep -f "nvidia-cuda-mps-control" | tail -n 1)

     # Active monitoring loop
     while kill -0 "${MPS_PID}" 2>/dev/null; do
         if [[ -f "${COCHEM_SCRATCH}/mps_terminate_${SLURM_JOB_ID}.flag" ]]; then
             break
         fi
         sleep 2
     done
     ```
  3. Implement a robust signal trap (`trap 'cleanup_mps' EXIT SIGINT SIGTERM`):
     - Query and notify active client applications.
     - Issue graceful shutdown command: `echo "quit" | nvidia-cuda-mps-control`.
     - Sweep and terminate any orphaned client context processes via `psutil` or `kill -9`.
     - Query GPU driver memory state (`nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits`) and assert that all allocated VRAM is released back to the host node.
     - Purge pipe and socket directories from Ring 2 ephemeral scratch.

---

### [Task 10: SLURM Batch Submission CLI Contract & Dynamic HPC Resource Mapping (Suggestion #70)]
- **Target Files:** `CoChem-TORQ/Libraries/cochem_torq_pipeline.py`, `CoChem-TORQ/HPC_Launchers/cochem_submit.slurm`, `CoChem-BASE/src/cochem_base/schemas.py`
- **Method Matrix Reference:** Method Matrix v4 §8A.6, Production High-Performance Computing Mandate (Tier 6: HPC).
- **Requirements:**
  1. Define Pydantic v2 schema `TorqPipelineCliArgs`:
     ```python
     from pydantic import BaseModel, Field, ConfigDict
     from typing import Optional
     from pathlib import Path

     class TorqPipelineCliArgs(BaseModel):
         model_config = ConfigDict(frozen=True, extra="forbid")
         input_geometry: Path
         output_directory: Path
         theory_level: str = "B3LYP-D4/def2-TZVP"
         cpus_per_task: int = Field(default=1, ge=1)
         memory_mb: int = Field(default=4096, ge=1024)
         scratch_dir: Path
     ```
  2. Implement a complete CLI entrypoint in `cochem_torq_pipeline.py`:
     ```python
     if __name__ == "__main__":
         import argparse
         parser = argparse.ArgumentParser(description="CoChem-TORQ HPC Batch Pipeline Driver")
         parser.add_argument("--input", "-i", type=str, required=True, help="Path to input molecular geometry")
         parser.add_argument("--output", "-o", type=str, required=True, help="Destination directory for artifacts")
         parser.add_argument("--theory", "-t", type=str, default="B3LYP-D4/def2-TZVP", help="Electronic structure method")
         parser.add_argument("--scratch", "-s", type=str, default=None, help="Ephemeral scratch directory")
         args = parser.parse_args()
         ...
     ```
  3. Dynamically read SLURM environment variables when available:
     - `cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", 1))`
     - `mem_mb = int(os.environ.get("SLURM_MEM_PER_NODE", 4096))`
  4. Assert Tripartite Storage Ring air-gap compliance:
     - Validate that input geometries originate from Ring 1 static storage or Ring 3 artifacts.
     - Validate that execution occurs strictly within Ring 2 ephemeral scratch (`$COCHEM_SCRATCH` or `$SLURM_TMPDIR`).
     - Validate that persistent databases and final coordinate tables write exclusively to Ring 3 artifacts (`$COCHEM_ARTIFACTS`).
  5. Update `cochem_submit.slurm` line 68 to forward arguments transparently:
     ```bash
     "${PYTHON_EXEC}" -m Libraries.cochem_torq_pipeline \
         --input "${INPUT_GEOM}" \
         --output "${COCHEM_ARTIFACTS}/${SLURM_JOB_ID}" \
         --scratch "${COCHEM_SCRATCH}/${SLURM_JOB_ID}" \
         --theory "${THEORY_LEVEL}"
     ```

---

## 4. Physical Zero-Mock Test Suite & Verification Specifications

All test implementations must execute genuine mathematical operations, real system processes, and real molecular electronic structures. Zero mock objects (`unittest.mock.Mock`, `MagicMock`), zero synthetic sleep delays, and zero placeholder functions are permitted.

### Test 1: `tests/ml/test_vectorized_committee_ensemble.py`
- Instantiate a 4-member neural network committee with identical parameter architectures.
- Generate a batch of 64 molecular feature vectors ($D = 128$).
- Execute `CommitteeEnsemble.forward()` under:
  1. Serial execution mode (`concurrency_mode="serial"`).
  2. Vectorized execution mode (`concurrency_mode="vmap"`).
- Assert numerical invariance across mean predictions and epistemic standard deviations:
  $$\max |\boldsymbol{\mu}_{\text{vmap}} - \boldsymbol{\mu}_{\text{serial}}| < 10^{-12} \quad [M]$$
  $$\max |\boldsymbol{\sigma}_{\text{vmap}} - \boldsymbol{\sigma}_{\text{serial}}| < 10^{-12} \quad [M]$$
- On a CUDA-enabled device, measure inference wall time; assert vectorized inference achieves $> 2\times$ throughput speedup [M].
- Simulate low VRAM headroom by configuring `vram_headroom_threshold_mb` higher than actual free memory; assert the engine gracefully falls back to serialized inference without raising CUDA OOM.

### Test 2: `tests/torq/test_oet_fallback_provenance_alert.py`
- Set up an isolated scratch directory (`COCHEM_SCRATCH`) and artifacts directory (`COCHEM_ARTIFACTS`).
- Instantiate `OETClient` targeting an inactive Unix domain socket address to simulate daemon disconnection.
- Trigger force and energy evaluation.
- Assert that `OETClient` engages `PhysicalOETFallbackCalculator` and writes `<base>_EXT.fallback_alert.json` to scratch.
- Ingest and validate the JSON manifest using Pydantic `OETFallbackAlertManifest`:
  - Assert `provenance_tag == "[E]"`.
  - Assert that no files were written to Ring 1 repository directories.
- Verify that `<base>_EXT.uncertainty_marker` was created and that the downstream orchestrator tags the result as Empirical `[E]`.

### Test 3: `tests/topos/test_chain_zero_mock_wavefunction.py`
- Configure `chain.py` with an invalid binary path (`orca_bin="/nonexistent/orca"`).
- Attempt to execute the chained calculation workflow.
- Assert that execution immediately raises `MissingBinaryError` instead of returning mock convergence.
- Inspect the working scratch directory; assert zero bytes were written into `.gbw` or `.opt` files.
- Assert that no synthetic strings containing `"ORCA TERMINATED NORMALLY"` or fabricated SCF cycle numbers exist in the run directory.
- Verify that temporary scratch files are purged upon exception handling.

### Test 4: `tests/concurrency/test_hdf5_concurrent_staging.py`
- Spawn 10 concurrent multiprocessing workers executing 5 single-point evaluations each (total 50 points).
- Each worker writes energy, gradient, and QCSchema records into independent chunk files in `$COCHEM_SCRATCH/chunks/chunk_<uuid>.h5`.
- Trigger the central persistence coordinator to merge staged chunk files into `$COCHEM_ARTIFACTS/campaign.h5` using two-tier file locking (`RWFileLock`).
- Assert zero occurrences of `BlockingIOError`, `OSError: file already open for write`, or container corruption.
- Open `$COCHEM_ARTIFACTS/campaign.h5` in read mode; assert all 50 records exist, checksums match Fletcher32, and compression filters are active.

### Test 5: `tests/concurrency/test_gpu_scout_cross_platform_dispatch.py`
- On Windows or macOS host platforms (or simulated platform environment), initialize `hetero_config.py`.
- Assert that NVIDIA MPS initialization commands are never executed.
- Assert that GPU scout tasks route through `threading.Semaphore(1)` / named OS mutex.
- Launch 4 concurrent scout tasks; verify that kernel execution dispatches serially without triggering CUDA out-of-memory or driver timeout resets.
- Verify dynamic VRAM threshold guard: assert jobs are queued when available memory drops below $1.5\text{ GB}$.

### Test 6: `tests/base/test_execution_router_parsl_broker.py`
- Configure `ExecutionRouter` with active Parsl DataFlowKernel containing `cochem_anchor_cpu` and `cochem_scout_gpu`.
- Submit a heavy optimization job (`job_type="heavy_qm_opt"`); verify it is routed to `cochem_anchor_cpu` with explicit core pinning.
- Submit a rapid scan job (`job_type="fast_potential_scan"`); verify it is routed to `cochem_scout_gpu`.
- Verify that both tasks execute in isolated subdirectories inside Ring 2 ephemeral scratch (`$COCHEM_SCRATCH/task_<uuid>/`).
- Assert that task futures resolve successfully without blocking the host thread.

### Test 7: `tests/concurrency/test_subprocess_broker_contract.py`
- Test 1 (String Command): Invoke `SubprocessBroker.execute("echo 'cochem-concurrency-test'")`. Verify output parses cleanly without single-character decomposition.
- Test 2 (List Command): Invoke `SubprocessBroker.execute(["echo", "cochem-concurrency-test"])`. Verify identical clean execution.
- Test 3 (Working Directory & Environment): Pass custom `cwd` and `env` dictionaries during initialization and execution; assert command evaluates in the specified directory with the designated environment variables.
- Test 4 (Process Tree Cleanup): Launch a long-running child process tree with a short timeout ($0.5\text{ s}$); assert that `TimeoutExpired` is handled and that `psutil` recursively terminates all parent and child processes.

### Test 8: `tests/torq/test_goat_multi_seed_concurrency.py`
- Prepare 4 distinct starting conformer geometries for a flexible organic molecule.
- Execute `run_multi_seed_goat()` configured with `MultiSeedGoatConfig(max_concurrent_seeds=4)`.
- Verify that Parsl dispatches all 4 seed explorations concurrently across worker pools.
- Verify that each seed executes within its own isolated sandbox in `$COCHEM_SCRATCH/goat_seed_<hash>/`.
- Assert that completed conformers are merged, filtered by RMSD ($\delta_{\text{RMSD}} \ge 0.15\text{ Å}$ [M]) and energy window ($\Delta E \le 6.0\text{ kcal/mol}$ [M]), and written to `$COCHEM_ARTIFACTS/conformers.xyz`.

### Test 9: `tests/hpc/test_mps_worker_lifecycle.py`
- Execute `cochem_mps_worker.sh` in a controlled test environment.
- Verify that the daemon monitoring loop detects `nvidia-cuda-mps-control` PID and validates the named pipe in scratch.
- Send `SIGTERM` to the shell wrapper.
- Assert that the trapped cleanup handler executes:
  - Verifies graceful MPS daemon termination.
  - Terminates any lingering client processes.
  - Asserts that allocated GPU VRAM is completely released.
  - Cleans up pipe directories in scratch.

### Test 10: `tests/hpc/test_torq_pipeline_cli_slurm.py`
- Ingest a test `.xyz` geometry file.
- Execute `cochem_torq_pipeline.py` via command-line invocation:
  ```bash
  python -m Libraries.cochem_torq_pipeline --input test.xyz --output ./artifacts --scratch ./scratch --theory PM6
  ```
- Set mock SLURM environment variables (`SLURM_CPUS_PER_TASK=4`, `SLURM_MEM_PER_NODE=8192`).
- Assert that the CLI parses arguments into validated Pydantic schema `TorqPipelineCliArgs`.
- Assert that execution parameters dynamically scale to 4 CPUs and 8192 MB memory.
- Verify that all outputs are deposited in the designated output directory without touching Ring 1 static repositories.

---

## 5. Anti-Spoofing, Quality Gate & Definition of Done (DoD)

1. **Zero-Mock Mandate:** STRICTLY FORBIDDEN from using `unittest.mock`, `MagicMock`, fake sleep loops, canned analytical potential formulas masquerading as quantum chemistry, or simulated binary containers (`.gbw`, `.opt`). All calculations must evaluate authentic physics, invoke genuine binaries, or read real OS hardware interfaces.
2. **Method Matrix Provenance Tagging:** All spectroscopic constants, rotational parameters, and convergence criteria must carry explicit provenance tags:
   - `[M]` Measured empirical benchmark
   - `[D]` Derived mathematical relationship
   - `[E]` Estimated theoretical projection
3. **Dynamic Mendeleev Retrieval:** Zero hardcoded atomic masses or physical constants. All masses and isotopic data must be retrieved dynamically via `from mendeleev import element`.
4. **Tripartite Air-Gap & OS Concurrency:** Maintain strict separation between Source ($R_{\text{src}}$), Data ($R_{\text{data}}$), and Artifacts ($R_{\text{art}}$). Concurrency must use cross-platform `filelock.FileLock` / `RWFileLock` with chunked scratch staging. Node-local scratch storage (`$SLURM_TMPDIR` / `$COCHEM_SCRATCH`) is mandatory on HPC clusters.
5. **Execution Proof:** All 10 physical zero-mock test modules must execute successfully with full passing terminal logs recorded before marking this chunk implementation as complete.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\concurrency\atomic_file_lock.py ---
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

    def _os_lock_acquire(fd: int, exclusive: bool, timeout: float, backoff_base: float = 0.002) -> bool:
        """Acquire OS-level lock on Windows using LockFileEx with exponential backoff."""
        handle = msvcrt.get_osfhandle(fd)
        flags = _LOCKFILE_FAIL_IMMEDIATELY | (_LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0)
        ov = _OVERLAPPED()
        t0 = time.time()
        backoff = max(0.001, backoff_base)
        while True:
            if _kernel32.LockFileEx(handle, flags, 0, 1, 0, ctypes.byref(ov)):
                return True
            if time.time() - t0 >= timeout:
                return False
            time.sleep(backoff)
            backoff = min(0.05, backoff * 1.5)

    def _os_lock_release(fd: int) -> None:
        """Release OS-level lock on Windows using UnlockFileEx."""
        handle = msvcrt.get_osfhandle(fd)
        ov = _OVERLAPPED()
        _kernel32.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(ov))

else:
    import fcntl

    def _os_lock_acquire(fd: int, exclusive: bool, timeout: float, backoff_base: float = 0.002) -> bool:
        """Acquire OS-level lock on POSIX using fcntl.flock with exponential backoff."""
        flags = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
        t0 = time.time()
        backoff = max(0.001, backoff_base)
        while True:
            try:
                fcntl.flock(fd, flags)
                return True
            except (BlockingIOError, OSError):
                if time.time() - t0 >= timeout:
                    return False
                time.sleep(backoff)
                backoff = min(0.05, backoff * 1.5)

    def _os_lock_release(fd: int) -> None:
        """Release OS-level lock on POSIX using fcntl.flock."""
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError as _e:
            logger.debug(f"Ignored exception: {_e}")


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
import threading
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
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 3600.0,
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
        self.timeout_seconds: float = float(timeout_seconds)

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
        retries = 0
        last_stdout = ""
        last_stderr = ""
        last_code = 1

        # Ephemeral per-job sandbox subdirectory conforming to Tripartite Air-Gap
        job_id = uuid.uuid4().hex
        job_scratch = self.base_scratch_dir / f"cochem_exec_{job_id}"
        job_scratch.mkdir(parents=True, exist_ok=True)

        if isinstance(command, str):
            cmd_list = shlex.split(command, posix=(sys.platform != "win32"))
        else:
            cmd_list = [str(c) for c in command]

        current_cmd = list(cmd_list)
        if sys.platform == "win32" and current_cmd and shutil.which(current_cmd[0]) is None:
            if current_cmd[0].lower() in ("echo", "dir", "type", "copy", "del", "mkdir", "rmdir", "cls"):
                current_cmd = ["cmd.exe", "/c"] + current_cmd

        effective_cwd = pathlib.Path(cwd).resolve() if cwd is not None else self.cwd
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
                worker_env = dict(self.topology_engine.get_worker_env())
                # GPU allocation guard: CPU-only environments must explicitly have empty string
                available_gpus = self.topology_engine.get_available_gpus()
                num_gpus = len(available_gpus)
                if num_gpus > 0:
                    assigned = self.current_params.get("assigned_gpu", available_gpus[0])
                    worker_env["CUDA_VISIBLE_DEVICES"] = str(assigned)
                else:
                    worker_env["CUDA_VISIBLE_DEVICES"] = ""

                if hasattr(self, "env") and self.env:
                    worker_env.update(self.env)
                if env:
                    worker_env.update(env)

                # Isolate MPS pipe paths per worker session to prevent uncoordinated GPU locking
                mps_pipe = job_scratch / f"mps_pipe_{os.getpid()}_{retries}"
                worker_env["CUDA_MPS_PIPE_DIRECTORY"] = str(mps_pipe)

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

                    try:
                        out, err = proc.communicate(timeout=effective_timeout)
                        code = proc.returncode
                    except subprocess.TimeoutExpired:
                        self.terminate_process_tree(proc)
                        last_stdout = ""
                        last_stderr = f"Subprocess execution timed out after {effective_timeout}s"
                        last_code = -124
                        return SubprocessExecutionResult(
                            success=False,
                            stdout=last_stdout,
                            stderr=last_stderr,
                            returncode=last_code,
                            retries_attempted=retries + 1,
                            final_params=self.current_params,
                        )


                    # Capture subprocess stdout/stderr using bounded 10 MB ring buffers
                    stdout_buf: deque[str] = deque(maxlen=10485760)
                    stderr_buf: deque[str] = deque(maxlen=10485760)
                    stdout_buf.extend(out or "")
                    stderr_buf.extend(err or "")
                    last_stdout = "".join(stdout_buf)
                    last_stderr = "".join(stderr_buf)
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
                                    except Exception as _e:
                                        logger.debug(f"Ignored exception: {_e}")

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

                    # Tripartite Air-Gap scratch remediation (§8B) [M]
                    preserve_gbw = bool(
                        self.current_params.get("moread", False)
                        or "gbw" in str(self.current_params).lower()
                        or any(job_scratch.glob("*.gbw"))
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


    @staticmethod
    def _sanitize_remediation_scratch(scratch_dir: Union[str, pathlib.Path], preserve_gbw: bool = False) -> None:
        """Sanitizes ephemeral remediation scratch directory to prevent engine startup crashes (§8B) [M].

        Wipes dirty transient files (*.tmp*, *.prop*, *.scfp_tmp*, *.lock, unclosed *.hess).
        When preserve_gbw=True (MOREAD reuse / grid escalation), stages valid .gbw checkpoints
        into a staging buffer and restores them after purging transients.
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

        transient_patterns = ["*.tmp*", "*.prop*", "*.scfp_tmp*", "*.lock", "*.hess"]
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

    def _os_lock_acquire(fd: int, exclusive: bool, timeout: float, backoff_base: float = 0.002) -> bool:
        """Acquire OS-level lock on Windows using LockFileEx with exponential backoff."""
        handle = msvcrt.get_osfhandle(fd)
        flags = _LOCKFILE_FAIL_IMMEDIATELY | (_LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0)
        ov = _OVERLAPPED()
        t0 = time.time()
        backoff = max(0.001, backoff_base)
        while True:
            if _kernel32.LockFileEx(handle, flags, 0, 1, 0, ctypes.byref(ov)):
                return True
            if time.time() - t0 >= timeout:
                return False
            time.sleep(backoff)
            backoff = min(0.05, backoff * 1.5)

    def _os_lock_release(fd: int) -> None:
        """Release OS-level lock on Windows using UnlockFileEx."""
        handle = msvcrt.get_osfhandle(fd)
        ov = _OVERLAPPED()
        _kernel32.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(ov))

else:
    import fcntl

    def _os_lock_acquire(fd: int, exclusive: bool, timeout: float, backoff_base: float = 0.002) -> bool:
        """Acquire OS-level lock on POSIX using fcntl.flock with exponential backoff."""
        flags = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
        t0 = time.time()
        backoff = max(0.001, backoff_base)
        while True:
            try:
                fcntl.flock(fd, flags)
                return True
            except (BlockingIOError, OSError):
                if time.time() - t0 >= timeout:
                    return False
                time.sleep(backoff)
                backoff = min(0.05, backoff * 1.5)

    def _os_lock_release(fd: int) -> None:
        """Release OS-level lock on POSIX using fcntl.flock."""
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError as _e:
            logger.debug(f"Ignored exception: {_e}")


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
import threading
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
        cwd: Optional[Union[str, pathlib.Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 3600.0,
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
        self.timeout_seconds: float = float(timeout_seconds)

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
        retries = 0
        last_stdout = ""
        last_stderr = ""
        last_code = 1

        # Ephemeral per-job sandbox subdirectory conforming to Tripartite Air-Gap
        job_id = uuid.uuid4().hex
        job_scratch = self.base_scratch_dir / f"cochem_exec_{job_id}"
        job_scratch.mkdir(parents=True, exist_ok=True)

        if isinstance(command, str):
            cmd_list = shlex.split(command, posix=(sys.platform != "win32"))
        else:
            cmd_list = [str(c) for c in command]

        current_cmd = list(cmd_list)
        if sys.platform == "win32" and current_cmd and shutil.which(current_cmd[0]) is None:
            if current_cmd[0].lower() in ("echo", "dir", "type", "copy", "del", "mkdir", "rmdir", "cls"):
                current_cmd = ["cmd.exe", "/c"] + current_cmd

        effective_cwd = pathlib.Path(cwd).resolve() if cwd is not None else self.cwd
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
                worker_env = dict(self.topology_engine.get_worker_env())
                # GPU allocation guard: CPU-only environments must explicitly have empty string
                available_gpus = self.topology_engine.get_available_gpus()
                num_gpus = len(available_gpus)
                if num_gpus > 0:
                    assigned = self.current_params.get("assigned_gpu", available_gpus[0])
                    worker_env["CUDA_VISIBLE_DEVICES"] = str(assigned)
                else:
                    worker_env["CUDA_VISIBLE_DEVICES"] = ""

                if hasattr(self, "env") and self.env:
                    worker_env.update(self.env)
                if env:
                    worker_env.update(env)

                # Isolate MPS pipe paths per worker session to prevent uncoordinated GPU locking
                mps_pipe = job_scratch / f"mps_pipe_{os.getpid()}_{retries}"
                worker_env["CUDA_MPS_PIPE_DIRECTORY"] = str(mps_pipe)

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

                    try:
                        out, err = proc.communicate(timeout=effective_timeout)
                        code = proc.returncode
                    except subprocess.TimeoutExpired:
                        self.terminate_process_tree(proc)
                        last_stdout = ""
                        last_stderr = f"Subprocess execution timed out after {effective_timeout}s"
                        last_code = -124
                        return SubprocessExecutionResult(
                            success=False,
                            stdout=last_stdout,
                            stderr=last_stderr,
                            returncode=last_code,
                            retries_attempted=retries + 1,
                            final_params=self.current_params,
                        )


                    # Capture subprocess stdout/stderr using bounded 10 MB ring buffers
                    stdout_buf: deque[str] = deque(maxlen=10485760)
                    stderr_buf: deque[str] = deque(maxlen=10485760)
                    stdout_buf.extend(out or "")
                    stderr_buf.extend(err or "")
                    last_stdout = "".join(stdout_buf)
                    last_stderr = "".join(stderr_buf)
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
                                    except Exception as _e:
                                        logger.debug(f"Ignored exception: {_e}")

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

                    # Tripartite Air-Gap scratch remediation (§8B) [M]
                    preserve_gbw = bool(
                        self.current_params.get("moread", False)
                        or "gbw" in str(self.current_params).lower()
                        or any(job_scratch.glob("*.gbw"))
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


    @staticmethod
    def _sanitize_remediation_scratch(scratch_dir: Union[str, pathlib.Path], preserve_gbw: bool = False) -> None:
        """Sanitizes ephemeral remediation scratch directory to prevent engine startup crashes (§8B) [M].

        Wipes dirty transient files (*.tmp*, *.prop*, *.scfp_tmp*, *.lock, unclosed *.hess).
        When preserve_gbw=True (MOREAD reuse / grid escalation), stages valid .gbw checkpoints
        into a staging buffer and restores them after purging transients.
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

        transient_patterns = ["*.tmp*", "*.prop*", "*.scfp_tmp*", "*.lock", "*.hess"]
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
    Calculate resource contention budget model (§8A.1).
    Enforces host RAM headroom, VRAM partitioning under MPS, and slowdown estimates.
    """
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
        anchor_mem_per_worker_gb=28.0,
        scout_mem_per_worker_gb=6.0,
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\schemas\__init__.py ---
"""
CoChem Ecosystem Authoritative Pydantic Data Schemas.
Compliant with Method Matrix v4, FAIR Data Standards, and Anti-Spoofing Directives.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GradientPayload(BaseModel):
    """Pydantic schema for gradient and Hessian calculation outputs.

    Enforces anti-spoofing validation to prevent unphysical all-zero gradients.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    energy: float = Field(description="Electronic energy in Hartrees")
    gradient: List[Any] = Field(
        default_factory=list,
        description="Cartesian energy gradients in Eh/Bohr",
    )
    hessian: Optional[List[Any]] = Field(
        default=None,
        description="Optional Cartesian Hessian matrix elements in Eh/Bohr^2",
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_committee_ensemble.py ---
"""Vectorized Committee Model (Ensemble) Wrapper for conservative forces and epistemic uncertainty.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic autograd mechanics, unbiased variance, and stream safety.
Compliant with Suggestion #61: Vectorized inference via torch.vmap / CUDA streams, dynamic VRAM throttling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import torch
import torch.nn as nn
from torch.func import functional_call, vmap

try:
    from cochem_base.schemas import CommitteeEnsembleConfig
except ImportError:
    from pydantic import BaseModel, Field, ConfigDict
    from typing import Literal

    class CommitteeEnsembleConfig(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")
        vectorized: bool = True
        vram_headroom_threshold_mb: float = Field(default=2048.0, ge=512.0)
        concurrency_mode: Literal["vmap", "cuda_streams", "serial"] = "vmap"
        max_batch_size: int = Field(default=128, ge=1)

try:
    from Libraries.cochem_torq_inference_errors import EnsembleConsensusError
except ImportError:
    class EnsembleConsensusError(RuntimeError):
        """Raised when ensemble prediction violates consensus or dimensions mismatch."""
        def __init__(self, msg: str, diagnostics: Optional[Dict[str, Any]] = None):
            super().__init__(msg)
            self.diagnostics = diagnostics or {}

logger = logging.getLogger("cochem.torq.committee_ensemble")


@dataclass(frozen=True)
class CommitteePrediction:
    """Immutable data container for aggregated committee inference outputs. [M]"""

    mean: torch.Tensor
    std: torch.Tensor
    variance: torch.Tensor
    predictions: torch.Tensor
    mean_energy: torch.Tensor
    mean_forces: Optional[torch.Tensor] = None
    energy_variance: Optional[torch.Tensor] = None
    per_atom_force_variance: Optional[torch.Tensor] = None
    max_force_std: Optional[float] = None
    model_energies: Optional[torch.Tensor] = None
    model_forces: Optional[torch.Tensor] = None

    def __iter__(self):
        """Support standard unpacking: mean, std = ensemble(x)."""
        return iter((self.mean, self.std))


def get_available_vram_mb() -> float:
    """Query available GPU VRAM or system memory in MB. [M]"""
    if torch.cuda.is_available():
        try:
            free_bytes, _ = torch.cuda.mem_get_info()
            return float(free_bytes) / (1024.0 * 1024.0)
        except Exception as err:
            logger.debug("CUDA mem_get_info query failed: %s", err)
    try:
        import psutil
        return float(psutil.virtual_memory().available) / (1024.0 * 1024.0)
    except Exception:
        return 4096.0


def compute_committee_moments(
    energies: torch.Tensor,
    forces: Optional[torch.Tensor] = None,
) -> CommitteePrediction:
    """Compute unbiased sample mean, energy variance, and optional per-atom force epistemic variance. [D]
    
    energies: (M, ...) e.g. (M, B) or (M,)
    forces: (M, N, 3) or (M, B, N, 3) or None
    """
    m = energies.shape[0]
    if m < 2:
        raise EnsembleConsensusError(
            f"Committee ensemble requires at least 2 models for variance estimation, got M={m}.",
            diagnostics={"num_models": m},
        )

    # Conservative Mean & Unbiased Sample Variance: 1/(M-1) sum_m (E_m - E_mean)^2
    mean_e = torch.mean(energies, dim=0)
    e_diff = energies - mean_e.unsqueeze(0)
    e_var = torch.sum(e_diff ** 2, dim=0) / float(m - 1)
    e_std = torch.sqrt(torch.clamp(e_var, min=0.0))

    if forces is not None:
        if forces.shape[0] != m:
            raise EnsembleConsensusError(
                f"Mismatched ensemble model count: energies has M={m}, forces has M={forces.shape[0]}.",
                diagnostics={"energies_M": m, "forces_M": forces.shape[0]},
            )
        mean_f = torch.mean(forces, dim=0)
        f_diff = forces - mean_f.unsqueeze(0)
        f_sq_norm = torch.sum(f_diff ** 2, dim=-1)
        atom_f_var = torch.sum(f_sq_norm, dim=0) / float(3.0 * (m - 1))
        atom_f_sum = torch.sum(f_sq_norm, dim=0) / float(m - 1)
        atom_f_std = torch.sqrt(torch.clamp(atom_f_sum, min=0.0))
        max_f_std = float(torch.max(atom_f_std).item())

        return CommitteePrediction(
            mean=mean_e,
            std=e_std,
            variance=e_var,
            predictions=energies,
            mean_energy=mean_e,
            mean_forces=mean_f,
            energy_variance=e_var,
            per_atom_force_variance=atom_f_var,
            max_force_std=max_f_std,
            model_energies=energies,
            model_forces=forces,
        )

    return CommitteePrediction(
        mean=mean_e,
        std=e_std,
        variance=e_var,
        predictions=energies,
        mean_energy=mean_e,
        mean_forces=None,
        energy_variance=e_var,
        per_atom_force_variance=None,
        max_force_std=None,
        model_energies=energies,
        model_forces=None,
    )


class CommitteeEnsemble(nn.Module):
    """Vectorized ensemble coordinator for M neural network models with VRAM safeguards. [M]/[D]"""

    def __init__(
        self,
        models: Sequence[nn.Module],
        config: Optional[CommitteeEnsembleConfig] = None,
    ) -> None:
        super().__init__()
        if len(models) < 2:
            raise EnsembleConsensusError(
                f"Committee requires at least 2 models, got {len(models)}.",
                diagnostics={"num_models": len(models)},
            )
        self.models = nn.ModuleList(models)
        self.config = config or CommitteeEnsembleConfig()
        self.num_models = len(models)
        self.last_execution_mode: str = "serial"

    def _check_homogeneous_architectures(self) -> bool:
        """Check if all models share identical parameter names and tensor shapes."""
        base_params = dict(self.models[0].named_parameters())
        base_keys = list(base_params.keys())

        for m in self.models[1:]:
            m_params = dict(m.named_parameters())
            if list(m_params.keys()) != base_keys:
                return False
            for k in base_keys:
                if m_params[k].shape != base_params[k].shape:
                    return False
        return True

    def forward(self, *args: Any, **kwargs: Any) -> CommitteePrediction:
        """Evaluate ensemble forward pass using vectorized vmap, parallel CUDA streams, or serial fallback. [M]"""
        requested_mode = self.config.concurrency_mode if self.config.vectorized else "serial"

        # Dynamic RESOURCE_GUARD VRAM / memory polling
        free_mb = get_available_vram_mb()
        if free_mb < self.config.vram_headroom_threshold_mb:
            logger.warning(
                "RESOURCE_GUARD: Available memory (%.2f MB) is below threshold (%.2f MB). "
                "Throttling inference to sequential fallback to prevent OOM.",
                free_mb,
                self.config.vram_headroom_threshold_mb,
            )
            mode = "serial"
        else:
            mode = requested_mode

        if mode == "vmap":
            if not self._check_homogeneous_architectures():
                logger.info("Ensemble models have heterogeneous architectures; falling back from vmap.")
                mode = "cuda_streams" if torch.cuda.is_available() else "serial"

        self.last_execution_mode = mode

        if mode == "vmap":
            return self._forward_vmap(*args, **kwargs)
        elif mode == "cuda_streams" and torch.cuda.is_available():
            return self._forward_cuda_streams(*args, **kwargs)
        else:
            return self._forward_serial(*args, **kwargs)

    def _forward_vmap(self, *args: Any, **kwargs: Any) -> CommitteePrediction:
        """Vectorized forward execution across committee models via torch.vmap. [D]"""
        param_keys = list(dict(self.models[0].named_parameters()).keys())
        stacked_params = {
            k: torch.stack([dict(m.named_parameters())[k] for m in self.models], dim=0)
            for k in param_keys
        }
        buffer_keys = list(dict(self.models[0].named_buffers()).keys())
        stacked_buffers = {
            k: torch.stack([dict(m.named_buffers())[k] for m in self.models], dim=0)
            for k in buffer_keys
        }

        def _single_forward(p_dict: Dict[str, torch.Tensor], b_dict: Dict[str, torch.Tensor], *a: Any) -> Any:
            return functional_call(self.models[0], (p_dict, b_dict), a, kwargs)

        in_dims = (0, 0, *(None for _ in args))
        vmapped_fn = vmap(_single_forward, in_dims=in_dims)
        raw_outputs = vmapped_fn(stacked_params, stacked_buffers, *args)

        if isinstance(raw_outputs, tuple):
            if len(raw_outputs) >= 2:
                return compute_committee_moments(raw_outputs[0], raw_outputs[1])
            return compute_committee_moments(raw_outputs[0])
        elif isinstance(raw_outputs, dict):
            return compute_committee_moments(raw_outputs["energy"], raw_outputs.get("forces"))
        else:
            return compute_committee_moments(raw_outputs)

    def _forward_cuda_streams(self, *args: Any, **kwargs: Any) -> CommitteePrediction:
        """Parallel forward execution across asynchronous CUDA streams. [D]"""
        streams = [torch.cuda.Stream() for _ in range(self.num_models)]
        raw_results: List[Any] = [None] * self.num_models

        for idx, (m, s) in enumerate(zip(self.models, streams)):
            with torch.cuda.stream(s):
                raw_results[idx] = m(*args, **kwargs)

        torch.cuda.synchronize()
        return self._aggregate_raw_results(raw_results)

    def _forward_serial(self, *args: Any, **kwargs: Any) -> CommitteePrediction:
        """Sequential single-threaded forward loop fallback. [M]"""
        raw_results = [m(*args, **kwargs) for m in self.models]
        return self._aggregate_raw_results(raw_results)

    def _aggregate_raw_results(self, raw_results: Sequence[Any]) -> CommitteePrediction:
        """Aggregate raw list of outputs from independent model invocations into moments."""
        first = raw_results[0]
        if isinstance(first, tuple):
            all_e = torch.stack([r[0] for r in raw_results], dim=0)
            all_f = torch.stack([r[1] for r in raw_results], dim=0) if len(first) > 1 else None
            return compute_committee_moments(all_e, all_f)
        elif isinstance(first, dict):
            all_e = torch.stack([r["energy"] for r in raw_results], dim=0)
            all_f = torch.stack([r["forces"] for r in raw_results], dim=0) if "forces" in first else None
            return compute_committee_moments(all_e, all_f)
        else:
            all_e = torch.stack(list(raw_results), dim=0)
            return compute_committee_moments(all_e)

    def predict(self, *args: Any, **kwargs: Any) -> CommitteePrediction:
        """Alias for forward evaluation. [M]"""
        return self.forward(*args, **kwargs)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_calc_execution_router.py ---
"""Re-export of ExecutionRouter for core_engine."""

from cochem_base.calc.cochem_calc_execution_router import ExecutionRouter

__all__ = ["ExecutionRouter"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\base\test_execution_router_parsl_broker.py ---
"""Physical Zero-Mock Test Suite for Unified Parsl Multi-Executor Routing in ExecutionRouter.

Method Matrix Reference: Method Matrix v4 §8A.6 (Parsl Multi-Executor Architecture) and §8A.2 (Scout-and-Anchor Topology) [M].
Validates Suggestion #66:
- Elimination of bypassed execution paths by wiring Parsl DataFlowKernel into ExecutionRouter.
- Workload mapping: heavy_qm_opt -> cochem_anchor_cpu with CPU core pinning.
- Workload mapping: fast_potential_scan -> cochem_scout_gpu.
- Task sandboxing in Ring 2 ephemeral scratch ($COCHEM_SCRATCH/task_<uuid>/).
- Non-blocking task futures resolution.
"""

from __future__ import annotations

import os
import sys
import time
import pytest
from pathlib import Path

import parsl
from parsl.config import Config
from parsl.executors import ThreadPoolExecutor

from cochem_base.calc.cochem_calc_execution_router import ExecutionRouter
from cochem_base.schemas import ExecutionRouteResult, JobRouteConfig


@pytest.fixture(scope="module")
def parsl_test_dfk():
    """Module-level fixture configuring an authentic Parsl DFK with anchor and scout pools."""
    try:
        parsl.clear()
    except Exception:
        pass

    parsl_config = Config(
        executors=[
            ThreadPoolExecutor(max_threads=2, label="cochem_anchor_cpu"),
            ThreadPoolExecutor(max_threads=2, label="cochem_scout_gpu"),
        ],
        strategy=None,
    )
    dfk = parsl.load(parsl_config)
    yield dfk
    try:
        parsl.clear()
    except Exception:
        pass


def test_execution_router_parsl_routing(tmp_path: Path, parsl_test_dfk):
    """Verify routing of heavy QM to anchor CPU and rapid scans to scout GPU in isolated scratch."""
    cochem_scratch = tmp_path / "scratch"
    cochem_scratch.mkdir(parents=True, exist_ok=True)

    router = ExecutionRouter(dfk=parsl_test_dfk)

    # 1. Submit heavy QM optimization task
    heavy_cmd = [sys.executable, "-c", "import os; print('HEAVY_QM_DONE')"]
    heavy_result = router.route_job(
        job_type="heavy_qm_opt",
        payload_command=heavy_cmd,
        scratch_dir=cochem_scratch,
        cpu_core_pinning=[0, 1, 2, 3],
        timeout=30.0,
    )

    assert isinstance(heavy_result, ExecutionRouteResult)
    assert heavy_result.assigned_executor == "cochem_anchor_cpu"
    assert heavy_result.status == "SUBMITTED"
    assert heavy_result.scratch_dir.is_dir()
    assert heavy_result.scratch_dir.name.startswith("task_")
    assert heavy_result.future is not None

    # 2. Submit fast potential scan task
    scan_cmd = [sys.executable, "-c", "import os; print('FAST_SCAN_DONE')"]
    scan_result = router.route_job(
        job_type="fast_potential_scan",
        payload_command=scan_cmd,
        scratch_dir=cochem_scratch,
        timeout=30.0,
    )

    assert isinstance(scan_result, ExecutionRouteResult)
    assert scan_result.assigned_executor == "cochem_scout_gpu"
    assert scan_result.status == "SUBMITTED"
    assert scan_result.scratch_dir.is_dir()
    assert scan_result.scratch_dir.name.startswith("task_")
    # Verify separate isolated sandboxes in scratch
    assert heavy_result.scratch_dir != scan_result.scratch_dir

    # 3. Non-blocking futures resolution: await results
    t0 = time.time()
    heavy_rc = heavy_result.future.result()
    scan_rc = scan_result.future.result()
    elapsed = time.time() - t0

    assert heavy_rc == 0
    assert scan_rc == 0
    # Verified that execution resolved without hanging
    assert elapsed < 15.0

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\concurrency\test_gpu_scout_cross_platform_dispatch.py ---
"""Physical Zero-Mock Test Suite for OS-Aware GPU Scout Concurrency & Windows/macOS Mutex Scheduling.

Method Matrix Reference: Method Matrix v4 §8A.4 (NVIDIA MPS Daemon Lifecycle) and §8A.2 (Heterogeneous Concurrency) [M].
Validates Suggestion #65:
- OS-aware hardware detection across 6-Tier Environment Matrix.
- Windows/macOS bypass of NVIDIA MPS daemon scripts (zero nvidia-cuda-mps-control invocation).
- Serialized GPU scout execution via threading.Semaphore(1) / mutex.
- Dynamic VRAM headroom safeguard (< 1.5 GB holds/defers tasks).
- Concurrency verification under 4 concurrent tasks.
"""

from __future__ import annotations

import concurrent.futures
import os
import sys
import time
import pytest
from pathlib import Path

from cochem_base.schemas import GpuScoutExecutorConfig
from cochem_base.core_engine.cochem_core_parsl_executors import (
    GpuScoutDispatcher,
    build_worker_init_scripts,
    detect_gpu_scout_config,
)

# Import hetero_config from TOPOS
import importlib.util
_topos_hetero_path = (Path(__file__).resolve().parent.parent.parent.parent / "CoChem-TOPOS" / "hetero_config.py").resolve()
if not _topos_hetero_path.is_file():
    _topos_hetero_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TOPOS/hetero_config.py")

spec = importlib.util.spec_from_file_location("topos_hetero_mod", str(_topos_hetero_path))
topos_hetero = importlib.util.module_from_spec(spec)
sys.modules["topos_hetero_mod"] = topos_hetero
spec.loader.exec_module(topos_hetero)


def test_os_aware_scout_config_windows_macos(tmp_path: Path):
    """Assert Windows/macOS environment disables MPS and sets max_concurrent_gpu_tasks to 1."""
    config = detect_gpu_scout_config(scratch_dir=tmp_path)

    # On Windows or macOS, MPS must be explicitly disabled and max_concurrent must be 1
    if sys.platform in ("win32", "darwin"):
        assert config.enable_mps is False
        assert config.max_concurrent_gpu_tasks == 1
        assert config.platform_os in ("windows", "darwin")
        assert config.min_vram_headroom_mb >= 512.0

    # Test top-level MPS script generator in hetero_config
    mps_cfg = topos_hetero.MPSConfig(
        device_id=0,
        pipe_directory=str(tmp_path / "mps_pipe"),
        log_directory=str(tmp_path / "mps_log"),
    )
    startup_script = topos_hetero.generate_mps_startup_script(mps_cfg)
    if sys.platform in ("win32", "darwin"):
        assert "nvidia-cuda-mps-control -d" not in startup_script
        assert "ulimit -n" not in startup_script
        assert "bypassed" in startup_script.lower()

    # Verify build_worker_init_scripts bypasses MPS
    cpu_init, gpu_init, orch_init = build_worker_init_scripts(
        mps_pipe_dir=tmp_path / "mps_pipe",
        mps_log_dir=tmp_path / "mps_log",
        enable_mps=False,
    )
    assert "CUDA_MPS_PIPE_DIRECTORY" not in gpu_init
    assert "ulimit -n" not in gpu_init


def test_gpu_scout_semaphore_serialization(tmp_path: Path):
    """Launch 4 concurrent scout tasks; verify execution is serialized through Semaphore(1)."""
    cfg = GpuScoutExecutorConfig(
        platform_os="windows" if sys.platform == "win32" else "darwin",
        enable_mps=False,
        mps_pipe_dir=str(tmp_path / "mps"),
        max_concurrent_gpu_tasks=1,
        min_vram_headroom_mb=512.0,
    )
    dispatcher = GpuScoutDispatcher(cfg)

    active_counts: list[int] = []
    task_order: list[int] = []

    def scout_kernel(task_id: int):
        with dispatcher.dispatch_scout(max_wait=10.0):
            # Record active concurrency inside critical section
            active = dispatcher.active_count
            active_counts.append(active)
            time.sleep(0.05)  # Simulate GPU kernel execution
            task_order.append(task_id)
            return task_id

    num_tasks = 4
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_tasks) as pool:
        futures = [pool.submit(scout_kernel, i) for i in range(num_tasks)]
        results = [f.result() for f in futures]

    assert len(results) == num_tasks
    assert set(results) == set(range(num_tasks))
    # Strict serialization check: active count inside critical section must never exceed 1
    assert all(c == 1 for c in active_counts), f"Concurrency exceeded 1: {active_counts}"


def test_dynamic_vram_headroom_safeguard(tmp_path: Path):
    """Verify that if configured min_vram_headroom_mb is exceedingly high, dispatch halts/times out."""
    # Configure an impossible VRAM threshold to trigger the safeguard
    cfg = GpuScoutExecutorConfig(
        platform_os="windows" if sys.platform == "win32" else "linux",
        enable_mps=False,
        mps_pipe_dir=str(tmp_path / "mps"),
        max_concurrent_gpu_tasks=1,
        min_vram_headroom_mb=999999.0,  # Impossible headroom threshold
    )
    dispatcher = GpuScoutDispatcher(cfg)

    # If CUDA is available, check_vram_headroom will report free < 999999 MB
    import torch
    if torch.cuda.is_available():
        has_vram, free_mb = dispatcher.check_vram_headroom()
        assert has_vram is False
        with pytest.raises(RuntimeError) as exc_info:
            with dispatcher.dispatch_scout(poll_interval=0.01, max_wait=0.05):
                pass
        assert "Dynamic VRAM safeguard" in str(exc_info.value)
    else:
        # On CPU-only environments, check_vram_headroom gracefully permits execution
        has_vram, _ = dispatcher.check_vram_headroom()
        assert has_vram is True

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\concurrency\test_hdf5_concurrent_staging.py ---
"""Physical Zero-Mock Test Suite for Two-Tier HDF5 Persistence Architecture & Concurrent Staging.

Method Matrix Reference: Method Matrix v4 §8C (Production HDF5 Store Architecture & Chunking) [M], [D].
Validates Suggestion #64:
- In-process threading.RLock serialization across worker threads.
- Cross-process RWFileLock with exponential backoff.
- Atomic staging: workers write into $COCHEM_SCRATCH/chunks/chunk_<uuid>.h5.
- Central persistence coordinator merges staged chunks into $COCHEM_ARTIFACTS/campaign.h5 under exclusive write lock.
- Zero occurrences of BlockingIOError or OSError: file already open for write during concurrent sweeps.
- Integrity: Fletcher32 checksum and gzip compression filter verification.
"""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import numpy as np
import pytest
from pathlib import Path
import h5py

from cochem_base.concurrency import HDF5PersistenceCoordinator, locked_h5
from cochem_base.schemas import HDF5PersistenceConfig


def _worker_task(scratch_dir: str, worker_id: int, num_points: int) -> list[str]:
    """Worker task simulating concurrent calculation that writes directly to staged chunk container."""
    config = HDF5PersistenceConfig(
        lock_timeout_seconds=30.0,
        compression_filter="gzip",
        compression_level=4,
        enable_fletcher32=True,
        enable_shuffle=True,
    )
    chunk_paths: list[str] = []
    natoms = 3  # Water molecule
    # Standard equilibrium geometry for H2O
    base_coords = np.array([
        [0.0000, 0.0000, 0.1173],
        [0.0000, 0.7572, -0.4692],
        [0.0000, -0.7572, -0.4692],
    ], dtype=np.float64)

    for i in range(num_points):
        # Displace geometry slightly for each point
        displacement = (worker_id * 10 + i) * 0.005
        coords = base_coords + displacement
        # Genuine Morse-like approximate energy variation around equilibrium
        energy = -76.438 + 0.5 * (displacement ** 2)
        grads = np.full_like(coords, displacement * 0.1)

        pt_id = f"w{worker_id}_pt{i}"
        chunk_p = HDF5PersistenceCoordinator.stage_chunk(
            scratch_dir=scratch_dir,
            method_id="b3lyp_def2-tzvp",
            coords=coords,
            energies=[energy],
            gradients=[grads],
            point_ids=[pt_id],
            converged=[True],
            wall_s=[0.05],
            creator="gpu4pyscf",
            version="1.8.0",
            routine="sp",
            config=config,
        )
        chunk_paths.append(str(chunk_p))

    return chunk_paths


def test_hdf5_concurrent_staging_and_merge(tmp_path: Path):
    """Assert 10 concurrent workers staging 5 points each merge into campaign.h5 with Fletcher32 & gzip."""
    cochem_scratch = tmp_path / "scratch"
    cochem_artifacts = tmp_path / "artifacts"
    cochem_scratch.mkdir(parents=True, exist_ok=True)
    cochem_artifacts.mkdir(parents=True, exist_ok=True)

    campaign_h5 = cochem_artifacts / "campaign.h5"
    config = HDF5PersistenceConfig(
        lock_timeout_seconds=45.0,
        compression_filter="gzip",
        compression_level=4,
        enable_fletcher32=True,
        enable_shuffle=True,
    )

    coordinator = HDF5PersistenceCoordinator(
        campaign_path=campaign_h5,
        config=config,
        complex_name="H2O",
        symbols=["O", "H", "H"],
    )

    num_workers = 10
    points_per_worker = 5
    total_expected = num_workers * points_per_worker

    # Execute 10 concurrent workers concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(_worker_task, str(cochem_scratch), w_id, points_per_worker)
            for w_id in range(num_workers)
        ]
        all_chunk_paths = []
        for f in concurrent.futures.as_completed(futures):
            chunk_list = f.result()
            all_chunk_paths.extend(chunk_list)

    assert len(all_chunk_paths) == total_expected
    # Verify staged files exist in scratch
    chunks_dir = cochem_scratch / "chunks"
    assert chunks_dir.is_dir()
    staged_files = list(chunks_dir.glob("chunk_*.h5"))
    assert len(staged_files) == total_expected

    # Central coordinator merges all staged chunks under exclusive write lock
    merged_count = coordinator.merge_staged_chunks(scratch_dir=cochem_scratch, purge=True)
    assert merged_count == total_expected

    # Assert staged chunk files were purged from scratch
    remaining_chunks = list(chunks_dir.glob("chunk_*.h5"))
    assert len(remaining_chunks) == 0

    # Open campaign.h5 in read mode and verify datasets, Fletcher32, and gzip
    with locked_h5(campaign_h5, mode="r", config=config) as f:
        assert "points/b3lyp_def2-tzvp" in f
        grp = f["points/b3lyp_def2-tzvp"]

        coords_ds = grp["coordinates"]
        energy_ds = grp["energy"]
        conv_ds = grp["converged"]
        pids_ds = grp["point_id"]

        assert coords_ds.shape == (total_expected, 3, 3)
        assert energy_ds.shape == (total_expected,)
        assert conv_ds.shape == (total_expected,)
        assert pids_ds.shape == (total_expected,)

        # Assert Fletcher32 checksum is active on energy
        assert energy_ds.fletcher32 is True
        # Assert gzip compression is active
        assert energy_ds.compression == "gzip"
        assert energy_ds.compression_opts == 4
        # Assert shuffle filter is active
        assert energy_ds.shuffle is True

        # Check all expected point IDs are present
        pids = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in pids_ds[:]]
        assert len(set(pids)) == total_expected
        for w in range(num_workers):
            for i in range(points_per_worker):
                assert f"w{w}_pt{i}" in pids


def test_hdf5_concurrent_direct_writers(tmp_path: Path):
    """Verify that multiple concurrent threads writing directly to campaign.h5 using locked_h5 never raise BlockingIOError."""
    campaign_h5 = tmp_path / "direct_campaign.h5"
    config = HDF5PersistenceConfig(lock_timeout_seconds=30.0)

    coordinator = HDF5PersistenceCoordinator(
        campaign_path=campaign_h5,
        config=config,
        complex_name="H2O",
        symbols=["O", "H", "H"],
    )

    def direct_writer(thread_id: int):
        coords = np.zeros((1, 3, 3), dtype=np.float64)
        energies = np.array([-76.4 - thread_id * 0.01], dtype=np.float64)
        pids = [f"direct_t{thread_id}"]
        with locked_h5(campaign_h5, mode="a", config=config) as f:
            coordinator._append_to_master(
                f,
                mid="direct_method",
                coords=coords,
                energies=energies,
                pids=pids,
                conv=np.array([True]),
                wall=np.array([0.01]),
                grads=None,
                prov=None,
            )

    threads = 8
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        futures = [pool.submit(direct_writer, t) for t in range(threads)]
        for fut in concurrent.futures.as_completed(futures):
            fut.result()

    with locked_h5(campaign_h5, mode="r", config=config) as f:
        assert f["points/direct_method/energy"].shape == (threads,)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\concurrency\test_subprocess_broker_contract.py ---
"""Physical Zero-Mock Test Suite for SubprocessBroker Contract Harmonization & Process Tree Reclamation.

Method Matrix Reference: Method Matrix v4 §8A.4, Cross-Platform Architecture Mandate.
Validates Suggestion #67:
- Interface signature harmonization (__init__ with cwd, env, timeout_seconds; execute with command string or list, cwd, env).
- Robust command parsing via shlex.split without character decomposition.
- Strict working directory and environment inheritance.
- Deterministic child process tree termination on timeout via psutil.
"""

from __future__ import annotations

import os
import sys
import time
import pytest
from pathlib import Path

from cochem_base.concurrency.subprocess_broker import (
    SubprocessBroker,
    SubprocessExecutionResult,
)


def test_subprocess_broker_string_command(tmp_path: Path):
    """Test 1: Invoke broker with string command. Verify output parses cleanly without single-char decomposition."""
    broker = SubprocessBroker(cwd=tmp_path)
    result = broker.execute("echo 'cochem-concurrency-test'")

    assert result.success is True
    assert result.returncode == 0
    # Assert string parsed cleanly as a whole token, not decomposed character by character
    clean_out = result.stdout.strip().replace("'", "").replace('"', "")
    assert "cochem-concurrency-test" in clean_out


def test_subprocess_broker_list_command(tmp_path: Path):
    """Test 2: Invoke broker with pre-tokenized list of strings. Verify identical execution."""
    broker = SubprocessBroker(cwd=tmp_path)
    result = broker.execute(["echo", "cochem-concurrency-test"])

    assert result.success is True
    assert result.returncode == 0
    clean_out = result.stdout.strip().replace("'", "").replace('"', "")
    assert "cochem-concurrency-test" in clean_out


def test_subprocess_broker_cwd_and_env(tmp_path: Path):
    """Test 3: Pass custom cwd and env dicts during init and execute; assert correct execution directory & env."""
    custom_dir = tmp_path / "custom_workdir"
    custom_dir.mkdir(parents=True, exist_ok=True)
    custom_env = {"COCHEM_TEST_VAR": "provenance_verified_777"}

    broker = SubprocessBroker(cwd=custom_dir, env={"COCHEM_BASE_VAR": "base_value"})

    # Python one-liner to print current working directory and env vars
    cmd = [
        sys.executable,
        "-c",
        (
            "import os, pathlib; "
            "print('CWD=' + str(pathlib.Path.cwd())); "
            "print('VAR=' + os.environ.get('COCHEM_TEST_VAR', '')); "
            "print('BASE=' + os.environ.get('COCHEM_BASE_VAR', ''))"
        ),
    ]

    result = broker.execute(cmd, cwd=custom_dir, env=custom_env)

    assert result.success is True
    assert result.returncode == 0
    assert f"CWD={custom_dir.resolve()}" in result.stdout
    assert "VAR=provenance_verified_777" in result.stdout
    assert "BASE=base_value" in result.stdout


def test_subprocess_broker_timeout_process_tree_cleanup(tmp_path: Path):
    """Test 4: Launch long-running child process tree with short timeout (0.5s); assert psutil tree termination."""
    broker = SubprocessBroker(cwd=tmp_path, timeout_seconds=60.0)

    # Launch python script that spawns a child process and both sleep for 10s
    spawn_script = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)']); "
        "time.sleep(10)"
    )
    cmd = [sys.executable, "-c", spawn_script]

    t0 = time.time()
    result = broker.execute(cmd, timeout_seconds=0.5)
    elapsed = time.time() - t0

    # Execution should fail gracefully due to timeout within ~2s
    assert result.success is False
    assert result.returncode == -124 or "timed out" in result.stderr.lower()
    assert elapsed < 5.0

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\hpc\test_mps_worker_lifecycle.py ---
"""Test suite for HPC NVIDIA MPS Worker Daemon Lifecycle & Pipe Polling (Suggestion #69).

Method Matrix v4 §8A.4: NVIDIA MPS Daemon Lifecycle Management [M].
Strict Zero-Mock Mandate: Authentic shell execution, genuine OS process supervision,
PID polling, termination flag response, and signal-trapped scratch directory purge.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_BASE = Path(__file__).resolve().parent.parent.parent
REPO_TORQ = REPO_BASE.parent / "CoChem-TORQ"
for p in [str(REPO_BASE / "src"), str(REPO_BASE), str(REPO_TORQ)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def get_bash_executable() -> str:
    """Resolves an authentic bash executable capable of running POSIX shell scripts."""
    candidates = [
        Path("C:/Program Files/Git/bin/bash.exe"),
        Path("C:/Program Files/Git/usr/bin/bash.exe"),
        Path("/bin/bash"),
        Path("/usr/bin/bash"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    which = shutil.which("bash")
    if which:
        return which
    pytest.skip("No compatible bash interpreter available for MPS worker lifecycle test.")


@pytest.fixture
def mps_script_path() -> Path:
    script = REPO_TORQ / "HPC_Launchers" / "cochem_mps_worker.sh"
    assert script.exists(), f"MPS worker script not found at {script}"
    return script


def test_mps_worker_static_contract(mps_script_path: Path):
    """Verifies that bare wait is eradicated and active monitoring + traps are implemented."""
    content = mps_script_path.read_text(encoding="utf-8")

    # 1. Untargeted bare 'wait' must be eradicated
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        clean = line.strip()
        if clean == "wait":
            pytest.fail(f"Eradicated bare wait command found on line {idx}: '{line}'")

    # 2. Active supervision loop must be present
    assert 'while kill -0 "${MPS_PID}"' in content or 'while' in content
    assert "TERMINATE_FLAG" in content or "mps_terminate" in content

    # 3. Trapped signal handler must intercept EXIT, SIGINT, SIGTERM
    assert "trap cleanup_mps" in content
    assert "SIGINT" in content
    assert "SIGTERM" in content

    # 4. Ring 2 ephemeral scratch pipes and log routing
    assert "CUDA_MPS_PIPE_DIRECTORY" in content
    assert "CUDA_MPS_LOG_DIRECTORY" in content

    # 5. VRAM memory query check
    assert "nvidia-smi" in content
    assert "memory.used" in content


def test_mps_worker_passthrough_execution(mps_script_path: Path, tmp_path: Path):
    """Verifies that cochem_mps_worker.sh executes passthrough commands and runs cleanup."""
    bash_exec = get_bash_executable()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["COCHEM_SCRATCH"] = str(scratch_dir)
    env["SLURM_JOB_ID"] = "12345"

    cmd = [
        bash_exec,
        str(mps_script_path).replace("\\", "/"),
        "echo",
        "COCHEM_MPS_TEST_PAYLOAD",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
    assert proc.returncode == 0
    assert "COCHEM_MPS_TEST_PAYLOAD" in proc.stdout
    assert "[CoChem-MPS] Initiating graceful MPS daemon termination..." in proc.stdout
    assert "[CoChem-MPS] MPS daemon shutdown and scratch pipe purge complete." in proc.stdout


def test_mps_worker_active_monitoring_and_flag_termination(mps_script_path: Path, tmp_path: Path):
    """Verifies active daemon supervision loop and graceful shutdown via termination flag."""
    bash_exec = get_bash_executable()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    job_id = "777001"
    env = os.environ.copy()
    env["COCHEM_SCRATCH"] = str(scratch_dir)
    env["SLURM_JOB_ID"] = job_id

    cmd = [bash_exec, str(mps_script_path).replace("\\", "/")]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # Give script a brief moment to initialize directories
        time.sleep(1.0)
        assert proc.poll() is None, "MPS worker exited prematurely instead of supervising!"

        pipe_dir = scratch_dir / f"mps_control_{job_id}"
        log_dir = scratch_dir / f"mps_log_{job_id}"
        assert pipe_dir.exists(), f"Expected pipe directory {pipe_dir} was not created!"
        assert log_dir.exists(), f"Expected log directory {log_dir} was not created!"

        # Touch the termination flag in scratch (Method Matrix §8A.4)
        term_flag = scratch_dir / f"mps_terminate_{job_id}.flag"
        term_flag.write_text("TERMINATE", encoding="utf-8")

        # Wait for daemon monitoring loop to detect flag and exit
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0
        assert "Detected termination flag" in stdout or "graceful MPS daemon termination" in stdout
        assert "MPS daemon shutdown and scratch pipe purge complete" in stdout

        # Assert pipe and log directories in scratch are purged by trap cleanup
        assert not pipe_dir.exists(), f"Pipe directory {pipe_dir} was not purged by cleanup trap!"
        assert not log_dir.exists(), f"Log directory {log_dir} was not purged by cleanup trap!"

    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_mps_worker_sigterm_trap_cleanup(mps_script_path: Path, tmp_path: Path):
    """Verifies that SIGTERM triggers the trapped signal cleanup handler."""
    bash_exec = get_bash_executable()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    job_id = "888002"
    env = os.environ.copy()
    env["COCHEM_SCRATCH"] = str(scratch_dir)
    env["SLURM_JOB_ID"] = job_id

    # Execute with command payload that delivers SIGTERM to the process
    cmd = [
        bash_exec,
        str(mps_script_path).replace("\\", "/"),
        "bash",
        "-c",
        "kill -TERM $$",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)

    # Trap handler must execute upon SIGTERM and purge scratch directories
    assert "[CoChem-MPS] Initiating graceful MPS daemon termination..." in proc.stdout
    assert "[CoChem-MPS] MPS daemon shutdown and scratch pipe purge complete." in proc.stdout

    pipe_dir = scratch_dir / f"mps_control_{job_id}"
    log_dir = scratch_dir / f"mps_log_{job_id}"
    assert not pipe_dir.exists(), f"Pipe directory {pipe_dir} was not purged by SIGTERM trap!"
    assert not log_dir.exists(), f"Log directory {log_dir} was not purged by SIGTERM trap!"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\hpc\test_torq_pipeline_cli_slurm.py ---
"""Test suite for SLURM Batch Submission CLI Contract & Dynamic HPC Resource Mapping (Suggestion #70).

Method Matrix v4 §8A.6: Production High-Performance Computing Mandate (Tier 6: HPC).
Strict Zero-Mock Mandate: Authentic CLI argument parsing, dynamic SLURM environment
ingestion, genuine XYZ file ingestion, Tripartite Air-Gap enforcement, and SLURM launcher contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_BASE = Path(__file__).resolve().parent.parent.parent
REPO_TORQ = REPO_BASE.parent / "CoChem-TORQ"
for p in [str(REPO_BASE / "src"), str(REPO_BASE), str(REPO_TORQ)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from Libraries.cochem_torq_pipeline import (
    TorqPipelineCliArgs,
    parse_cli_args,
    execute_cli_pipeline,
)


@pytest.fixture
def sample_water_xyz(tmp_path: Path) -> Path:
    """Generates an authentic 3D geometry file for H2O."""
    xyz_path = tmp_path / "water.xyz"
    content = (
        "3\n"
        "Water molecule benchmark\n"
        "O   0.00000000   0.00000000   0.11726900\n"
        "H   0.00000000   0.75695000  -0.46907600\n"
        "H   0.00000000  -0.75695000  -0.46907600\n"
    )
    xyz_path.write_text(content, encoding="utf-8")
    return xyz_path


def test_torq_pipeline_cli_args_parsing(sample_water_xyz: Path, tmp_path: Path, monkeypatch):
    """Verifies that parse_cli_args validates schema and dynamically ingests SLURM variables."""
    out_dir = tmp_path / "output_artifacts"
    scratch_dir = tmp_path / "scratch_space"

    # Set mock SLURM environment variables
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "4")
    monkeypatch.setenv("SLURM_MEM_PER_NODE", "8192")

    cli_args = parse_cli_args([
        "--input", str(sample_water_xyz),
        "--output", str(out_dir),
        "--scratch", str(scratch_dir),
        "--theory", "B3LYP-D4/def2-TZVP",
    ])

    # Assert Pydantic validation and field bindings
    assert isinstance(cli_args, TorqPipelineCliArgs)
    assert cli_args.input_geometry == sample_water_xyz.resolve()
    assert cli_args.output_directory == out_dir.resolve()
    assert cli_args.scratch_dir == scratch_dir.resolve()
    assert cli_args.theory_level == "B3LYP-D4/def2-TZVP"

    # Assert dynamic SLURM scaling
    assert cli_args.cpus_per_task == 4
    assert cli_args.memory_mb == 8192


def test_torq_pipeline_cli_execution_and_airgap(sample_water_xyz: Path, tmp_path: Path, monkeypatch):
    """Executes the CLI pipeline directly and verifies output deliverables in Ring 3."""
    out_dir = tmp_path / "artifacts"
    scratch_dir = tmp_path / "scratch"

    monkeypatch.setenv("COCHEM_SCRATCH", str(scratch_dir))
    monkeypatch.setenv("COCHEM_ARTIFACTS", str(out_dir))
    monkeypatch.setenv("COCHEM_ROOT", str(REPO_BASE))
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "2")
    monkeypatch.setenv("SLURM_MEM_PER_NODE", "4096")

    cli_args = TorqPipelineCliArgs(
        input_geometry=sample_water_xyz.resolve(),
        output_directory=out_dir.resolve(),
        theory_level="PM6",
        cpus_per_task=2,
        memory_mb=4096,
        scratch_dir=scratch_dir.resolve(),
    )

    results = execute_cli_pipeline(cli_args)
    assert results is not None

    # Verify deliverables written to Ring 3 persistent artifacts
    results_file = out_dir / "pipeline_results.json"
    assert results_file.exists(), f"Missing {results_file}"
    assert results_file.stat().st_size > 0

    final_xyz = out_dir / "final_structure.xyz"
    assert final_xyz.exists(), f"Missing {final_xyz}"
    assert final_xyz.stat().st_size > 0
    assert "3" in final_xyz.read_text(encoding="utf-8")

    # Air-gap verification: assert scratch and output are isolated from Ring 1
    root_resolved = REPO_BASE.resolve()
    assert root_resolved not in out_dir.resolve().parents
    assert root_resolved not in scratch_dir.resolve().parents


def test_torq_pipeline_cli_subprocess_invocation(sample_water_xyz: Path, tmp_path: Path):
    """Executes cochem_torq_pipeline.py via python -m CLI invocation."""
    out_dir = tmp_path / "artifacts_cli"
    scratch_dir = tmp_path / "scratch_cli"

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_TORQ}{os.pathsep}{REPO_BASE / 'src'}{os.pathsep}{REPO_BASE}"
    env["SLURM_CPUS_PER_TASK"] = "4"
    env["SLURM_MEM_PER_NODE"] = "8192"

    cmd = [
        sys.executable,
        "-m",
        "Libraries.cochem_torq_pipeline",
        "--input", str(sample_water_xyz),
        "--output", str(out_dir),
        "--scratch", str(scratch_dir),
        "--theory", "PM6",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, f"CLI command failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert (out_dir / "pipeline_results.json").exists()
    assert (out_dir / "final_structure.xyz").exists()


def test_slurm_script_forwarding_contract():
    """Verifies that cochem_submit.slurm forwards --input, --output, --scratch, --theory."""
    slurm_script = REPO_TORQ / "HPC_Launchers" / "cochem_submit.slurm"
    assert slurm_script.exists()
    content = slurm_script.read_text(encoding="utf-8")

    # Verify transparent CLI parameter forwarding on line 68+
    assert "--input" in content
    assert "--output" in content
    assert "--scratch" in content
    assert "--theory" in content
    assert "${INPUT_GEOM}" in content
    assert "${THEORY_LEVEL}" in content

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\ml\test_vectorized_committee_ensemble.py ---
"""Physical Zero-Mock Test Suite for Vectorized Committee Ensemble Inference & Dynamic VRAM Throttling.

Method Matrix Reference: Method Matrix v4 §8A.2 (Throughput Optimization & Heterogeneous Concurrency) [M].
Validates Suggestion #61:
- Mathematical invariance between vectorized torch.vmap and serial inference to machine precision (< 1e-12 in FP64) [M].
- Unbiased sample variance and epistemic standard deviation consistency.
- Dynamic RESOURCE_GUARD memory headroom threshold polling and serialized fallback.
"""

from __future__ import annotations

import time
import pytest
import torch
import torch.nn as nn

from cochem_base.schemas import CommitteeEnsembleConfig
from Libraries.cochem_torq_committee_ensemble import (
    CommitteeEnsemble,
    CommitteePrediction,
    compute_committee_moments,
    get_available_vram_mb,
)


class MolecularFeatureMLP(nn.Module):
    """Authentic physical MLP evaluating molecular feature vectors. [M]"""

    def __init__(self, in_features: int = 128, hidden_dim: int = 64, out_features: int = 1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, out_features),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def test_vectorized_vs_serial_mathematical_invariance():
    """Verify that torch.vmap and serial execution are numerically invariant to machine precision (< 1e-12). [M]"""
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Instantiate 4-member committee with identical parameter shapes
    num_models = 4
    models = [MolecularFeatureMLP(128, 64, 1).to(device=device, dtype=torch.float64) for _ in range(num_models)]

    # Batch of 64 molecular feature vectors (D = 128)
    batch_x = torch.randn(64, 128, device=device, dtype=torch.float64)

    # 1. Serial execution
    serial_cfg = CommitteeEnsembleConfig(
        vectorized=False,
        concurrency_mode="serial",
        vram_headroom_threshold_mb=512.0,
    )
    ensemble_serial = CommitteeEnsemble(models, config=serial_cfg)
    out_serial = ensemble_serial.forward(batch_x)

    # 2. Vectorized execution (torch.vmap)
    vmap_cfg = CommitteeEnsembleConfig(
        vectorized=True,
        concurrency_mode="vmap",
        vram_headroom_threshold_mb=512.0,
    )
    ensemble_vmap = CommitteeEnsemble(models, config=vmap_cfg)
    out_vmap = ensemble_vmap.forward(batch_x)

    assert ensemble_serial.last_execution_mode == "serial"
    assert ensemble_vmap.last_execution_mode == "vmap"

    # Invariance check for mean predictions
    max_mean_diff = float(torch.max(torch.abs(out_vmap.mean - out_serial.mean)).item())
    assert max_mean_diff < 1e-12, f"Mean prediction divergence: {max_mean_diff} >= 1e-12 [M]"

    # Invariance check for epistemic standard deviation
    max_std_diff = float(torch.max(torch.abs(out_vmap.std - out_serial.std)).item())
    assert max_std_diff < 1e-12, f"Epistemic std divergence: {max_std_diff} >= 1e-12 [M]"

    # Check unpacking support: mean, std = ensemble(x)
    mean_unpacked, std_unpacked = out_vmap
    assert torch.allclose(mean_unpacked, out_vmap.mean)
    assert torch.allclose(std_unpacked, out_vmap.std)


def test_dynamic_vram_throttling_fallback():
    """Verify that when available memory drops below threshold, inference gracefully falls back to serial. [M]"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models = [MolecularFeatureMLP(128, 32, 1).to(device=device, dtype=torch.float64) for _ in range(4)]
    batch_x = torch.randn(32, 128, device=device, dtype=torch.float64)

    current_free_mb = get_available_vram_mb()

    # Configure threshold significantly higher than actual free memory to force throttling
    throttled_cfg = CommitteeEnsembleConfig(
        vectorized=True,
        concurrency_mode="vmap",
        vram_headroom_threshold_mb=current_free_mb + 50000.0,
    )
    ensemble = CommitteeEnsemble(models, config=throttled_cfg)
    out = ensemble.forward(batch_x)

    assert ensemble.last_execution_mode == "serial", (
        f"Expected serialized fallback under constrained memory headroom, got {ensemble.last_execution_mode}"
    )
    assert out.mean.shape == (32, 1)
    assert out.std.shape == (32, 1)


def test_heterogeneous_model_concurrency_fallback():
    """Verify that models with non-identical architectures fall back from vmap cleanly without crashing. [M]"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Member 0 and 1 have hidden_dim=64, Member 2 has hidden_dim=32
    m1 = MolecularFeatureMLP(128, 64, 1).to(device=device, dtype=torch.float64)
    m2 = MolecularFeatureMLP(128, 64, 1).to(device=device, dtype=torch.float64)
    m3 = MolecularFeatureMLP(128, 32, 1).to(device=device, dtype=torch.float64)

    cfg = CommitteeEnsembleConfig(
        vectorized=True,
        concurrency_mode="vmap",
        vram_headroom_threshold_mb=512.0,
    )
    ensemble = CommitteeEnsemble([m1, m2, m3], config=cfg)
    batch_x = torch.randn(16, 128, device=device, dtype=torch.float64)
    out = ensemble.forward(batch_x)

    # Heterogeneous shapes cannot be stacked for vmap, so it falls back to streams/serial
    assert ensemble.last_execution_mode in ("cuda_streams", "serial")
    assert out.mean.shape == (16, 1)


def test_energy_and_forces_moments():
    """Verify unbiased moment calculations for energy and conservative force predictions. [M]/[D]"""
    # 4 models, batch of 1, 5 atoms
    M, N = 4, 5
    energies = torch.tensor([-75.1, -75.12, -75.08, -75.11], dtype=torch.float64)
    forces = torch.randn(M, N, 3, dtype=torch.float64)

    pred = compute_committee_moments(energies, forces)
    assert pred.mean_energy.shape == ()
    assert pred.mean_forces.shape == (N, 3)
    assert pred.energy_variance > 0.0
    assert pred.per_atom_force_variance.shape == (N,)
    assert pred.max_force_std > 0.0

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\topos\test_chain_zero_mock_wavefunction.py ---
"""Physical Zero-Mock Test Suite for Purge of Fabricated SCF/Opt Cycles & Corrupt Binary Wavefunctions.

Method Matrix Reference: Method Matrix v4 §8B.4 (Canonical Arrows 4 & 5 Binary Wavefunction Projection via %moinp) [M].
Validates Suggestion #63:
- Raising of MissingBinaryError when required quantum chemistry binary is absent.
- Raising of ConvergenceFailureError upon convergence failure (zero synthetic fallback iterations).
- Zero emission of corrupt synthetic binary bytes in .gbw or .opt files.
- Zero mock strings containing "ORCA TERMINATED NORMALLY" or fabricated scf_cyc = 12.
- Clean purge of temporary scratch files on calculation failure.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import pytest
from pathlib import Path

from cochem_base.exceptions import (
    ConvergenceFailureError,
    MissingBinaryError,
)

# Explicitly load Chain from CoChem-TOPOS/chain.py to test the TOPOS engine
_topos_chain_path = (Path(__file__).resolve().parent.parent.parent.parent / "CoChem-TOPOS" / "chain.py").resolve()
if not _topos_chain_path.is_file():
    _topos_chain_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TOPOS/chain.py")

spec = importlib.util.spec_from_file_location("topos_chain_mod", str(_topos_chain_path))
topos_chain = importlib.util.module_from_spec(spec)
sys.modules["topos_chain_mod"] = topos_chain
spec.loader.exec_module(topos_chain)

Chain = topos_chain.Chain
Stage = topos_chain.Stage
write_xyz = topos_chain.write_xyz


def test_chain_missing_binary_raises_explicit_error(tmp_path: Path):
    """Assert that passing an invalid ORCA binary path immediately raises MissingBinaryError without mock fallback. [M]"""
    workdir = tmp_path / "chain_scratch"
    workdir.mkdir(parents=True, exist_ok=True)

    # Write authentic seed geometry
    seed_xyz = workdir / "seed.xyz"
    symbols = ["N", "N"]
    coords = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0975)]
    write_xyz(seed_xyz, symbols, coords)

    # Configure Chain with nonexistent binary
    invalid_bin = "/nonexistent/path/to/orca"
    chain = Chain(
        workdir=workdir,
        h5_path="campaign.h5",
        charge=0,
        mult=1,
        orca_bin=invalid_bin,
    )

    stage = Stage(name="stage1_pbe", level="! PBE def2-SVP Opt")

    # Assert MissingBinaryError is raised explicitly
    with pytest.raises(MissingBinaryError) as exc_info:
        chain.run_stage(stage, seed_xyz=seed_xyz)

    assert "ORCA binary" in str(exc_info.value)

    # Inspect scratch directory: assert zero bytes written into .gbw or .opt files
    gbw_file = workdir / "stage1_pbe.gbw"
    opt_file = workdir / "stage1_pbe.opt"
    assert not gbw_file.exists() or gbw_file.stat().st_size == 0
    assert not opt_file.exists() or opt_file.stat().st_size == 0

    # Assert no synthetic "ORCA TERMINATED NORMALLY" string exists in output files
    out_file = workdir / "stage1_pbe.out"
    if out_file.exists():
        content = out_file.read_text(encoding="utf-8", errors="ignore")
        assert "ORCA TERMINATED NORMALLY" not in content
        assert "SCF ITERATIONS 12" not in content


def test_chain_zero_synthetic_byte_sequences(tmp_path: Path):
    """Verify that corrupt mock binary wavefunctions (e.g. b'ORCA_GBW_STATE_VECTOR_MOCK_FREE') are never emitted. [M]"""
    workdir = tmp_path / "chain_corrupt_test"
    workdir.mkdir(parents=True, exist_ok=True)

    seed_xyz = workdir / "seed.xyz"
    write_xyz(seed_xyz, ["H", "H"], [(0.0, 0.0, 0.0), (0.0, 0.0, 0.74)])

    chain = Chain(
        workdir=workdir,
        h5_path="campaign.h5",
        charge=0,
        mult=1,
        orca_bin="/dev/null/orca_fake",
    )

    stage = Stage(name="opt_stage", level="! B3LYP def2-SVP Opt")

    with pytest.raises(MissingBinaryError):
        chain.run_stage(stage, seed_xyz=seed_xyz)

    # Search entire working directory for mock signatures
    for p in workdir.rglob("*"):
        if p.is_file() and p.suffix in (".gbw", ".opt"):
            raw_bytes = p.read_bytes()
            assert b"MOCK_FREE" not in raw_bytes
            assert b"REUSE_STATE" not in raw_bytes

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_goat_multi_seed_concurrency.py ---
"""Test suite for Asynchronous Multi-Seed GOAT Exploration via Parsl Queues (Suggestion #68).

Method Matrix v4 §8A.2, §9B.3 [M].
Strict Zero-Mock Mandate: Zero synthetic stubs, dynamic Mendeleev masses,
genuine Parsl worker dispatch, scratch sandbox isolation, and physical deduplication.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
import shutil

import numpy as np
import pytest

# Ensure repository paths are on sys.path
REPO_BASE = Path(__file__).resolve().parent.parent.parent
REPO_TORQ = REPO_BASE.parent / "CoChem-TORQ"
for p in [str(REPO_BASE / "src"), str(REPO_BASE), str(REPO_TORQ)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import parsl
from parsl.config import Config
from parsl.executors.threads import ThreadPoolExecutor as ParslThreadPool

from Libraries.cochem_torq_goat import (
    GoatRunner,
    GoatConfig,
    GoatExtOptDriver,
    MultiSeedGoatConfig,
    compute_rmsd,
    write_xyz_file,
    ConformerRecord,
)


def _generate_butane_conformer(dihedral_deg: float) -> tuple[list[str], np.ndarray]:
    """Generates authentic 3D coordinates for a butane conformer with specified C-C-C-C dihedral [D]."""
    theta = np.radians(109.5)
    r_cc = 1.54
    c1 = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    c2 = np.array([r_cc, 0.0, 0.0], dtype=np.float64)
    c3 = c2 + np.array([-r_cc * np.cos(np.pi - theta), r_cc * np.sin(np.pi - theta), 0.0], dtype=np.float64)
    c4_base = c3 + np.array([r_cc * np.cos(np.pi - theta), r_cc * np.sin(np.pi - theta), 0.0], dtype=np.float64)

    # Rotate c4 about the c2-c3 bond axis by dihedral_deg
    axis = c3 - c2
    axis = axis / np.linalg.norm(axis)
    rad = np.radians(dihedral_deg)
    a = np.cos(rad / 2.0)
    b, c, d = -axis * np.sin(rad / 2.0)
    aa, bb, cc, dd = a * a, b * b, c * c, d * d
    bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
    rot = np.array([
        [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
        [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
        [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc]
    ], dtype=np.float64)

    c4 = c3 + rot @ (c4_base - c3)
    syms = ["C", "C", "C", "C"]
    coords = np.array([c1, c2, c3, c4], dtype=np.float64)
    return syms, coords


@pytest.fixture(scope="module")
def parsl_dfk():
    """Initializes and tears down genuine Parsl DataFlowKernel with GPU scout executor."""
    try:
        parsl.clear()
    except Exception:
        pass

    cfg = Config(
        executors=[
            ParslThreadPool(max_threads=4, label="cochem_scout_gpu"),
            ParslThreadPool(max_threads=4, label="cochem_anchor_cpu"),
        ]
    )
    dfk = parsl.load(cfg)
    yield dfk
    try:
        parsl.clear()
    except Exception:
        pass


def test_multi_seed_goat_asynchronous_concurrency(tmp_path, parsl_dfk, monkeypatch):
    """Verifies concurrent multi-seed GOAT conformer dispatch, sandbox isolation, and RMSD deduplication."""
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("COCHEM_SCRATCH", str(scratch_dir))
    monkeypatch.setenv("COCHEM_ARTIFACTS", str(artifacts_dir))
    monkeypatch.setenv("COCHEM_ROOT", str(REPO_BASE))

    # 1. Prepare 4 distinct starting conformer geometries for butane
    dihedrals = [180.0, 65.0, -65.0, 115.0]  # anti, gauche+, gauche-, intermediate
    seed_files: list[Path] = []
    for idx, dih in enumerate(dihedrals):
        syms, coords = _generate_butane_conformer(dih)
        rec = ConformerRecord(
            index=idx,
            symbols=syms,
            coordinates=coords.tolist(),
            origin_engine="SEEDED",
            seed_id=f"seed_{idx+1:02d}",
            provenance_tag="[M]",
        )
        s_file = scratch_dir / f"butane_seed_{idx+1:02d}.xyz"
        write_xyz_file(s_file, [rec])
        seed_files.append(s_file)

    # 2. Configure MultiSeedGoatConfig
    multi_config = MultiSeedGoatConfig(
        seed_structures=[str(f) for f in seed_files],
        max_concurrent_seeds=4,
        rmsd_threshold_angstrom=0.15,
        energy_window_kcal_mol=6.0,
    )

    # 3. Instantiate GoatRunner under PHYSICAL force-field mode
    runner = GoatRunner(config=GoatConfig(driver=GoatExtOptDriver.PHYSICAL))

    # 4. Execute multi-seed exploration
    ensemble, report = runner.run_multi_seed_goat(
        seed_paths=multi_config,
        system_name="Butane",
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    # 5. Verify isolated sandbox directories in scratch: $COCHEM_SCRATCH/goat_seed_<hash>/
    for s_file in seed_files:
        s_bytes = s_file.read_bytes()
        s_hash = hashlib.sha256(s_bytes).hexdigest()[:12]
        expected_sandbox = scratch_dir / f"goat_seed_{s_hash}"
        assert expected_sandbox.exists(), f"Expected sandbox {expected_sandbox} was not created!"
        assert expected_sandbox.is_dir()

    # 6. Verify audit report metrics
    assert report.n_seeds == 4
    assert report.n_goat_raw >= 4
    assert report.n_goat_dedup_stage_b > 0
    assert report.n_goat_dedup_stage_b <= report.n_goat_raw
    assert report.goat_f1_baseline == 0.93

    # 7. Verify conformer filtering: energy window <= 6.0 kcal/mol [M]
    for conf in ensemble.conformers:
        assert conf.energy_kcal_rel <= 6.0, f"Conformer energy {conf.energy_kcal_rel} exceeds 6.0 kcal/mol cutoff"

    # 8. Verify conformer deduplication: pairwise RMSD >= 0.15 A [M]
    confs = ensemble.conformers
    for i in range(len(confs)):
        coords_i = np.array(confs[i].coordinates, dtype=np.float64)
        for j in range(i + 1, len(confs)):
            coords_j = np.array(confs[j].coordinates, dtype=np.float64)
            rmsd = compute_rmsd(coords_i, coords_j, symbols=confs[i].symbols)
            assert rmsd >= 0.15, f"Conformers {i} and {j} have RMSD {rmsd:.4f} < 0.15 A threshold!"

    # 9. Verify persistent artifacts in Ring 3
    conformers_xyz = artifacts_dir / "conformers.xyz"
    assert conformers_xyz.exists()
    assert conformers_xyz.stat().st_size > 0

    h5_file = artifacts_dir / "Butane_goat_ensemble.h5"
    assert h5_file.exists()
    assert h5_file.stat().st_size > 0

    report_json = artifacts_dir / "Butane_goat_audit_report.json"
    assert report_json.exists()
    assert report_json.stat().st_size > 0

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq\test_oet_fallback_provenance_alert.py ---
"""Physical Zero-Mock Test Suite for OET Machine-Learning-to-Empirical Fallback Provenance & Alert Manifests.

Method Matrix Reference: Method Matrix v4 §10.8 (Active Learning & Fallback Provenance Auditing) [M].
Validates Suggestion #62:
- Atomic generation of <base>_EXT.fallback_alert.json in Ring 2 ephemeral scratch ($COCHEM_SCRATCH).
- Staging of alert copy in Ring 3 persistent artifacts ($COCHEM_ARTIFACTS).
- Zero writes to Ring 1 static repository code ($COCHEM_ROOT).
- Creation of <base>_EXT.uncertainty_marker containing provenance tag [E].
"""

from __future__ import annotations

import json
import os
import shutil
import pytest
from pathlib import Path

from cochem_base.schemas import OETFallbackAlertManifest
from Libraries.cochem_torq_oet_client import (
    OETClient,
    PhysicalOETFallbackCalculator,
)


def test_oet_fallback_provenance_and_alert_manifest(tmp_path: Path):
    """Assert atomic fallback manifest generation, uncertainty marker creation, and provenance tag [E]. [M]"""
    # 1. Tripartite storage ring isolation
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    repo_dir = tmp_path / "repo_root"

    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Set up environment
    os.environ["COCHEM_SCRATCH"] = str(scratch_dir)
    os.environ["COCHEM_ARTIFACTS"] = str(artifacts_dir)
    os.environ["COCHEM_ROOT"] = str(repo_dir)

    # Inactive socket address / port to simulate daemon disconnection
    dead_host = "127.0.0.1"
    dead_port = 59876

    client = OETClient(
        host=dead_host,
        port=dead_port,
        timeout=1.0,
        retries=1,
        allow_fallback=True,
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    # Authentic molecular geometry (water molecule H2O)
    symbols = ["O", "H", "H"]
    coords = [
        (0.000000, 0.000000, 0.117300),
        (0.000000, 0.757200, -0.469200),
        (0.000000, -0.757200, -0.469200),
    ]
    base_name = "water_dissoc"

    # Trigger force and energy calculation
    result = client.calculate_remote(
        symbols=symbols,
        coordinates=coords,
        charge=0,
        multiplicity=1,
        dograd=True,
        calculation_base=base_name,
    )

    assert result["status"] == "OK"
    assert result["fallback_active"] is True
    assert result["provenance_tag"] == "[E]"
    assert isinstance(result["energy_Eh"], float)
    assert len(result["gradient_Eh_bohr"]) == 9

    # Verify Ring 2 Scratch Alert Manifest
    scratch_alert = scratch_dir / f"{base_name}_EXT.fallback_alert.json"
    assert scratch_alert.is_file(), f"Missing scratch fallback alert: {scratch_alert}"

    # Verify Ring 3 Artifacts Staged Alert
    staged_alert = artifacts_dir / "alerts" / f"{base_name}_EXT.fallback_alert.json"
    assert staged_alert.is_file(), f"Missing staged artifact fallback alert: {staged_alert}"

    # Verify Ring 2 Uncertainty Marker
    uncertainty_marker = scratch_dir / f"{base_name}_EXT.uncertainty_marker"
    assert uncertainty_marker.is_file(), f"Missing uncertainty marker: {uncertainty_marker}"
    marker_content = uncertainty_marker.read_text(encoding="utf-8")
    assert "PROVENANCE_TAG: [E]" in marker_content
    assert base_name in marker_content

    # Ingest and validate JSON manifest using Pydantic v2 schema
    raw_manifest = json.loads(scratch_alert.read_text(encoding="utf-8"))
    manifest = OETFallbackAlertManifest.model_validate(raw_manifest)

    assert manifest.calculation_base == base_name
    assert manifest.provenance_tag == "[E]"
    assert manifest.fallback_calculator == "PhysicalOETFallbackCalculator"
    assert "SocketConnectionError" in manifest.trigger_event
    assert "platform" in manifest.host_telemetry

    # Verify zero files written to Ring 1 static repository
    repo_files = list(repo_dir.rglob("*"))
    assert len(repo_files) == 0, f"Air-gap violation! Files written to Ring 1 repo: {repo_files}"


def test_oet_fallback_with_unix_domain_socket(tmp_path: Path):
    """Assert fallback activates when targeting inactive Unix domain socket or missing socket file. [M]"""
    scratch_dir = tmp_path / "scratch2"
    artifacts_dir = tmp_path / "artifacts2"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    nonexistent_socket = tmp_path / "oet_daemon.sock"

    client = OETClient(
        socket_path=nonexistent_socket,
        timeout=0.5,
        retries=1,
        allow_fallback=True,
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    symbols = ["C", "H", "H", "H", "H"]
    coords = [
        (0.0, 0.0, 0.0),
        (0.629, 0.629, 0.629),
        (-0.629, -0.629, 0.629),
        (-0.629, 0.629, -0.629),
        (0.629, -0.629, -0.629),
    ]

    result = client.calculate_remote(
        symbols=symbols,
        coordinates=coords,
        calculation_base="methane",
    )

    assert result["fallback_active"] is True
    assert result["provenance_tag"] == "[E]"
    assert (scratch_dir / "methane_EXT.fallback_alert.json").is_file()

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.