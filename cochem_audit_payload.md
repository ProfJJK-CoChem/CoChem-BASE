Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_16_TORQ_Training_Dynamics_Part_1_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous training dynamics, transfer learning, and production compilation suite specified in Software Requirements Specification (SRS) Chunk 16: `TORQ_Training_Dynamics_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev monoisotopic mass retrieval mandate, and Method Matrix v4 (`[M]` Empirical Benchmark, `[D]` Derived Mathematical Relationship, `[E]` Estimated Theoretical Projection). Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine physical tensors, authentic molecular coordinates, and real chemical observables.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `Libraries/` and `core/` in `CoChem-TORQ` to verify existing model backbones, potential wrappers, telemetry loggers, and test fixtures established in SRS Chunk 15.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, atomic checkpoint serialization, and custom typed domain exceptions (`TorqTrainingError`, `HDF5LockTimeoutError`, `PrecisionDivergenceError`, `CheckpointCorruptionError`, `DistributedSyncError`, `UnsupportedElementError`, `ParityVerificationError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering every component using authentic chemical structures and physical fixtures (e.g., Water dimer, Alanine dipeptide $N=22$, Ar-Kr dimer, Fluorobenzene complex, Ethanol $N=9$, Water 16-mer cluster, Octasulfur $\text{S}_8$, and Krypton-encapsulated Fullerene $\text{Kr@C}_{60}$).
4. **Physical Verification**: Execute the test suite using `pytest tests/ -v` via `run_command` in the terminal. Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Domain Exceptions & Pydantic v2 Data Contracts
- **File Target**: `Libraries/cochem_torq_training_schemas.py` and `Libraries/cochem_torq_training_errors.py` (and export in `Libraries/__init__.py`)
- **Exception Hierarchy**:
  ```python
  class TorqTrainingError(Exception):
      """Base exception for all TORQ training dynamics errors."""
      pass

  class HDF5LockTimeoutError(TorqTrainingError):
      """Raised when acquiring advisory HDF5 filelock exceeds timeout ceiling."""
      pass

  class PrecisionDivergenceError(TorqTrainingError):
      """Raised when AMP GradScaler encounters unrecoverable NaN/Inf gradients."""
      pass

  class CheckpointCorruptionError(TorqTrainingError):
      """Raised when checkpoint state or SHA-256 checksum validation fails."""
      pass

  class DistributedSyncError(TorqTrainingError):
      """Raised when distributed all-reduce or rank synchronization deadlocks."""
      pass

  class UnsupportedElementError(TorqTrainingError):
      """Raised when input molecular batch contains unmapped atomic species."""
      pass

  class ParityVerificationError(TorqTrainingError):
      """Raised when TorchScript compiled model violates eager numerical parity."""
      pass
  ```
- **Pydantic v2 Data Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
  - `TrainingDynamicsConfig`:
    - `batch_size: int = Field(default=32, ge=1, description="Per-device batch size [M]")`
    - `gradient_checkpointing: bool = Field(default=True, description="Enable activation recomputation [D]")`
    - `mixed_precision_dtype: Literal["bfloat16", "float16", "float32"] = Field(default="bfloat16", description="AMP precision [M]")`
    - `max_gradient_norm: float = Field(default=1.0, gt=0.0, description="Gradient clipping norm ceiling [M]")`
    - `energy_loss_weight: float = Field(default=1.0, ge=0.0, description="Loss weight for potential energy [M]")`
    - `force_loss_weight: float = Field(default=100.0, ge=0.0, description="Loss weight for atomic forces [M]")`
  - `TransferLearningConfig`:
    - `base_model_path: Path = Field(..., description="Local path to pre-trained ANI-2x weights [M]")`
    - `expected_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$", description="Cryptographic SHA-256 hash [M]")`
    - `freeze_symmetry_functions: bool = Field(default=True, description="Freeze AEV feature extractor [M]")`
    - `layer_decay_rate: float = Field(default=0.8, gt=0.0, le=1.0, description="LLRD decay factor [M]")`
    - `new_species_atomic_numbers: List[int] = Field(default_factory=list, description="New atomic numbers Z to initialize [M]")`
    - Validator `validate_atomic_numbers`: Ensure $1 \le Z \le 118$, return sorted unique integers.
  - `TorchScriptExportConfig`:
    - `export_path: Path = Field(..., description="Destination path for serialized TorchScript .pt model [M]")`
    - `energy_relative_tolerance: float = Field(default=1e-6, gt=0.0, description="Max relative energy error [M]")`
    - `force_parity_tolerance_hartree_bohr: float = Field(default=1e-6, gt=0.0, description="Max absolute force error in float64 [M]")`
    - `validate_against_fixtures: bool = Field(default=True, description="Execute validation before finalizing export [M]")`
  - `DistributedEarlyStoppingConfig`:
    - `patience_epochs: int = Field(default=15, ge=1, description="Epochs to wait before early termination [M]")`
    - `min_delta_hartree: float = Field(default=1e-5, ge=0.0, description="Minimum validation loss improvement [M]")`
    - `synchronize_ranks: bool = Field(default=True, description="Broadcast early exit flag across all DDP ranks [D]")`
  - `LossLandscapeConfig`:
    - `grid_resolution: int = Field(default=25, ge=5, le=100, description="Grid points per axis [M]")`
    - `range_min: float = Field(default=-1.0, description="Normalized coordinate min [M]")`
    - `range_max: float = Field(default=1.0, description="Normalized coordinate max [M]")`
    - `filter_normalization: bool = Field(default=True, description="Normalize random directions by filter Frobenius norm [D]")`
    - `output_plot_path: Path = Field(..., description="Destination path for rendered contour plot [M]")`
    - Model validator: Verify `range_min < range_max`.

---

#### 2. Gradient Checkpointing Engine for High-Batch MLFF Training (`REQ-TORQ-TRAIN-091` `[D]`)
- **File Target**: `Libraries/cochem_torq_gradient_checkpointing.py` (and export in `Libraries/__init__.py`)
- **Mathematical Scope & Second-Derivative Autograd Mechanics**:
  - Conservative atomic forces $\mathbf{F}_i \in \mathbb{R}^3$ are negative spatial gradients:
    $$\mathbf{F}_i = -\frac{\partial E_\theta(\mathbf{R}, \mathbf{Z})}{\partial \mathbf{R}_i} \quad [D]$$
  - Joint training composite loss function normalized by total atomic degrees of freedom:
    $$\mathcal{L}(\theta) = w_E \frac{1}{B} \sum_{b=1}^B |E_b - E_b^{\text{ref}}|^2 + w_F \frac{1}{3 \sum_{b=1}^B N_b} \sum_{b=1}^B \sum_{i=1}^{N_b} \|\mathbf{F}_{b,i} - \mathbf{F}_{b,i}^{\text{ref}}\|^2 \quad [D]$$
  - Backpropagating force loss requires second-order mixed partial derivatives $\frac{\partial^2 E_\theta}{\partial \theta \partial \mathbf{R}}$.
  - The checkpointing implementation MUST utilize:
    `torch.utils.checkpoint.checkpoint(forward_fn, *args, use_reentrant=False)`
    In PyTorch $\ge 2.0$, `use_reentrant=False` natively captures the backward graph for nested differentiation.
  - The parameters `create_graph=True` and `retain_graph=True` belong strictly in:
    `torch.autograd.grad(outputs=energy.sum(), inputs=coordinates, create_graph=True, retain_graph=True)`
    during analytical force evaluation inside the forward pass; `create_graph` is NEVER passed as a kwarg to `checkpoint()` itself.
- **RNG State & Tensor Cache Isolation**:
  - Random number generator states across all active CUDA and CPU streams must be explicitly captured and restored via `preserve_rng_state=True` to guarantee deterministic dropout/stochastic regularization reproducibility.
  - Dynamic neighbor-list index tensors $\mathcal{E} \in \mathbb{Z}^{2 \times |\mathcal{E}|}$ and interatomic distance vectors $\mathbf{r}_{ij} = \mathbf{R}_j - \mathbf{R}_i$ are treated as immutable graph topology fixtures; exclude them from recomputation graphs to avoid memory fragmentation.
- **VRAM Verification**:
  - Must achieve $VRAM_{\text{checkpoint}} \le 0.45 \times VRAM_{\text{eager}}$ on expanded batch sizes ($4\times$ to $8\times$) with exact force autograd numerical parity ($\Delta \mathbf{F} = 0.0$).

---

#### 3. ANI-2x Transfer Learning Pipeline (`REQ-TORQ-TRAIN-092` `[M]`)
- **File Target**: `Libraries/cochem_torq_ani2x_transfer.py` (and export in `Libraries/__init__.py`)
- **Chemical Domain Extension & AEV Alignment**:
  - Standard ANI-2x element set: $\{ \text{H}, \text{C}, \text{N}, \text{O}, \text{S}, \text{F}, \text{Cl} \}$ ($Z \in \{1, 6, 7, 8, 16, 9, 17\}$).
  - Target system expansion: noble gases ($\text{He}, \text{Ne}, \text{Ar}, \text{Kr}, \text{Xe}$ with $Z \in \{2, 10, 18, 36, 54\}$) and heavy halogens ($\text{Br}, \text{I}$ with $Z \in \{35, 53\}$) for dispersion-bound van der Waals complexes.
  - **AEV Species Dimension & Tensor Channel Alignment**:
    - Partition radial and angular representations by species pairs $(S_i, S_j)$ and triplets $(S_i, S_j, S_k)$.
    - When expanding chemical domain to novel species (e.g., $\text{Kr}, \text{Xe}, \text{Br}$), expand the AEV feature extractor: frozen parameters for pre-existing species interactions are retained without modification, while interaction channels for novel species are zero-padded and calibrated with standard radial/angular grid shifts.
    - Dense atomic neural network heads for pre-existing species retain their input projection dimensions via species-channel slicing, while newly initialized species heads receive the fully expanded feature dimension.
    - Initialize novel species atomic heads with truncated normal weights (He initialization, gain $\sqrt{2}$) and zero bias.
    - Fine-tune pre-existing species heads using Layer-wise Learning Rate Decay (LLRD) with decay factor $\gamma = 0.8$ applied per hidden layer.
- **Air-Gap & Offline Ingestion (`COCHEM_OFFLINE=1`)**:
  - Zero external network egress. Automatic downloads via TorchANI or HuggingFace Hub are strictly forbidden.
  - Ingest pre-trained weights from Ring 2 local storage (`$COCHEM_DATA_DIR/models/ani2x/`) and validate against hardcoded cryptographic SHA-256 signatures prior to parameter ingestion. Raise `CheckpointCorruptionError` if hash mismatch occurs.
  - If input coordinates contain elements outside base ANI-2x set and registered fine-tuned heads, immediately raise `UnsupportedElementError`.

---

#### 4. Dedicated TorchScript Compilation for C++ Inference (`REQ-TORQ-TRAIN-093` `[D]`)
- **File Target**: `Libraries/cochem_torq_torchscript_export.py` (and export in `Libraries/__init__.py`)
- **Compilation Protocol & Dynamic Ragged Topology**:
  - Models must be exported via `torch.jit.script` (NOT static `torch.jit.trace`) to ensure full support for dynamic control flow, variable molecular sizes, and conditionally evaluated neighbor-list cutoffs.
  - Dynamic tensor dimensions on leading batch and coordinate dimensions:
    - Atomic coordinates: $\mathbf{R} \in \mathbb{R}^{N_{\text{atoms}} \times 3}$
    - Atomic numbers: $\mathbf{Z} \in \mathbb{Z}^{N_{\text{atoms}}}$
    - Dynamic neighbor pairs: $\mathcal{E} \in \mathbb{Z}^{2 \times N_{\text{edges}}}$
    - Molecule batch pointers: $\mathbf{P} \in \mathbb{Z}^{B+1}$
- **Numerical Parity Verification & Acceptance Thresholds**:
  - Automated numerical parity verification against eager PyTorch across physical test fixtures (water cluster, alanine dipeptide, Ar-Kr dimer).
  - Tolerances enforced strictly in double precision `torch.float64` [M]:
    - Relative energy error: $\frac{|E_{\text{eager}} - E_{\text{script}}|}{|E_{\text{eager}}|} \le 10^{-6}$ (or absolute error $L_\infty(E) \le 10^{-6}\,\text{Hartree}$).
    - Maximum absolute force error: $L_\infty(\mathbf{F}) = \max \|\mathbf{F}_{\text{eager}} - \mathbf{F}_{\text{script}}\|_\infty \le 10^{-6}\,\text{Hartree/Bohr}$ ($\approx 5.1422 \times 10^{-5}\,\text{eV/\AA}$).
  - Binaries failing parity thresholds are rejected and raise `ParityVerificationError`.

---

#### 5. Multi-GPU Distributed Early Stopping & Deadlock Prevention (`REQ-TORQ-TRAIN-094` `[D]`)
- **File Target**: `Libraries/cochem_torq_distributed_early_stopping.py` (and export in `Libraries/__init__.py`)
- **Cross-Rank Metric Reduction & Synchronization**:
  - Local validation losses evaluated across shard batches on rank $r$ are reduced globally before patience decisions:
    $$\bar{\mathcal{L}}_{\text{val}} = \frac{1}{W} \sum_{r=0}^{W-1} \mathcal{L}_{\text{val}}^{(r)} \quad [D]$$
  - Metric aggregation MUST execute via `torch.distributed.all_reduce(loss_tensor, op=torch.distributed.ReduceOp.AVG)`.
  - Ranks are strictly prohibited from evaluating early-stopping logic on rank-local loss shards.
- **Deadlock-Free Termination Protocol**:
  - Unconditional collective synchronization MUST execute across ALL ranks on EVERY validation epoch:
    ```python
    stop_flag = torch.zeros(1, dtype=torch.int32, device="cpu")
    if rank == 0 and plateau_patience_exceeded:
        stop_flag.fill_(1)
    torch.distributed.broadcast(stop_flag, src=0)
    if stop_flag.item() == 1:
        torch.distributed.barrier()
        break
    ```
  - Binding `stop_flag` to `"cpu"` guarantees cross-platform compatibility and prevents Gloo collective serialization crashes on Tier 1 Windows and Tier 2 macOS.

---

#### 6. Scale-Invariant Loss Landscape Visualization (`REQ-TORQ-TRAIN-095` `[D]`)
- **File Target**: `Libraries/cochem_torq_loss_landscape.py` (and export in `Libraries/__init__.py`)
- **Filter-Normalized Perturbation Formulation (Li et al., 2018)**:
  $$\theta(\alpha, \beta) = \theta^* + \alpha \mathbf{d}_1 + \beta \mathbf{d}_2 \quad [D]$$
  - For each parameter tensor layer/filter $j$, direction vectors $\mathbf{d}_{k,j}$ are normalized to match the Frobenius norm of the corresponding parameter filter $\theta^*_j$:
    $$\mathbf{d}_{k, j} = \frac{\mathbf{v}_{k, j}}{\|\mathbf{v}_{k, j}\|_F} \|\theta^*_j\|_F \quad \text{where} \quad \mathbf{v}_{k, j} \sim \mathcal{N}(0, I) \quad [D]$$
  - 1D profiling: $\beta = 0$ with $\alpha \in [-1.0, 1.0]$.
  - 2D contours: $(\alpha, \beta) \in [-1.0, 1.0]^2$ sampled over an $M \times M$ equidistant grid ($M \le 50$).
- **VRAM Isolation & Scratch Containment**:
  - Landscape evaluations execute strictly under `torch.no_grad()` in an isolated inference sub-context.
  - Between evaluation grid points, intermediate activations are unlinked and GPU memory is reclaimed via `torch.cuda.empty_cache()` to prevent OOM faults during batch evaluations.
  - Render high-resolution contour plots and save to `output_plot_path` using `matplotlib` Agg backend.

---

#### 7. Dynamic Mixed-Precision (FP16/BF16) Training Engine (`REQ-TORQ-TRAIN-096` `[M]`)
- **File Target**: `Libraries/cochem_torq_amp_trainer.py` (and export in `Libraries/__init__.py`)
- **Hardware-Aware Precision Dispatching**:
  - Dynamically query accelerator architecture:
    - **Compute Capability $\ge 8.0$ (Ampere, Hopper, Ada Lovelace)**: Defaults to Bfloat16 (`torch.bfloat16`) via `torch.amp.autocast(device_type=device.type, dtype=torch.bfloat16)`. BF16 preserves the 8-bit dynamic exponent of FP32, eliminating underflow and obviating dynamic loss scaling.
    - **Compute Capability $< 8.0$ (Volta, Turing)**: Defaults to Float16 (`torch.float16`) coordinated via `torch.amp.GradScaler(init_scale=65536.0, growth_factor=2.0, backoff_factor=0.5)`.
    - **Apple Silicon (MPS) & CPU**: Defaults to native FP32 execution (or CPU BF16 autocast where supported by PyTorch runtime), bypassing `GradScaler`.
- **Force Gradient Precision & Gradient Clipping Integration**:
  - Input coordinates $\mathbf{R}$ and force gradient autograd graphs ($\nabla_\mathbf{R} E_\theta$) MUST be cast to and retained in `torch.float32` (or `torch.float64`) to prevent underflow artifacts in Clebsch-Gordan tensor contractions.
  - When utilizing FP16 `GradScaler`, gradients must be explicitly unscaled prior to norm-based clipping:
    ```python
    scaler.unscale_(optimizer)
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=config.max_gradient_norm)
    ```
  - Raise `PrecisionDivergenceError` if unrecoverable NaN/Inf gradients persist across consecutive scaling cycles.

---

#### 8. Thread-Safe HDF5 Storage & Atomic Checkpointing Engine
- **File Target**: `Libraries/cochem_torq_training_persistence.py` (and export in `Libraries/__init__.py`)
- **Thread-Safe SWMR Storage**:
  - Chunked HDF5 storage with `gzip` (level 4) compression, `shuffle` filter enabled, and `fletcher32` checksum validation.
  - POSIX environments: `swmr=True`, `libver="latest"`.
  - Advisory file locks: `filelock.FileLock(path.with_suffix(".h5.lock"), timeout=30.0)` for cross-process concurrency and `threading.Lock()` for intra-process safety. Raise `HDF5LockTimeoutError` on timeout.
  - Multi-worker PyTorch `DataLoader`: Worker initialization routine (`worker_init_fn`) instantiates independent HDF5 file handles per worker process.
  - Parallel Filesystem (Lustre/GPFS/NFS) Override: Dynamically set `HDF5_USE_FILE_LOCKING="FALSE"`, serializing file access exclusively via user-space `filelock` into local NVMe scratch (`$SLURM_TMPDIR`).
- **Atomic Checkpoint Serialization**:
  - Checkpoint files (`.pt` / `.h5`) are written to an isolated temporary file (`checkpoint.pt.tmp`), flushed to disk via `os.fsync(f.fileno())`, and atomically moved to destination via `os.replace`.
  - Accompanying `.sha256` digest file generated for every saved checkpoint. Raise `CheckpointCorruptionError` if digest verification fails upon reload.

---

### TEST SUITE SPECIFICATIONS

All tests must be authentic, physically executing against real molecular coordinates and physical observables without mocks or stubs under `tests/`:

1. **`tests/test_torq_gradient_checkpointing.py`** (`REQ-TORQ-TRAIN-091`):
   - **Physical Fixtures**: Water dimer $(\text{H}_2\text{O})_2$ and Alanine dipeptide $(N=22)$.
   - **Verification**:
     - Peak VRAM comparison: Verify $VRAM_{\text{checkpoint}} \le 0.45 \times VRAM_{\text{eager}}$ across expanded batch sizes.
     - Analytical Force Parity: Compute forces with and without checkpointing. Verify exact numerical match $\Delta \mathbf{F} = \max \|\mathbf{F}_{\text{checkpoint}} - \mathbf{F}_{\text{eager}}\|_\infty = 0.0$ (within machine precision $10^{-7}$).
     - RNG State Determinism: Verify that dropout/stochastic layers produce bit-for-bit identical outputs during recomputation passes with `preserve_rng_state=True`.

2. **`tests/test_torq_ani2x_transfer.py`** (`REQ-TORQ-TRAIN-092`):
   - **Physical Fixtures**: Ar-Kr dimer and Fluorobenzene non-covalent complex.
   - **Verification**:
     - Cryptographic Ingestion: Verify pre-trained base weights load offline with valid SHA-256 digest; corrupting a byte in weights raises `CheckpointCorruptionError`.
     - Head Expansion & Channel Slicing: Expand base model to noble gas species ($Z=36$ Kr, $Z=18$ Ar). Verify base heads retain original slice dimensions, new heads initialize with He normal gain $\sqrt{2}$ and zero bias.
     - LLRD Verification: Verify learning rates decrease per hidden layer with factor $\gamma = 0.8$.
     - Unsupported Elements: Ingest coordinates containing unregistered heavy element (e.g., $Z=80$ Hg) and assert `UnsupportedElementError` is raised.

3. **`tests/test_torq_torchscript_export.py`** (`REQ-TORQ-TRAIN-093`):
   - **Physical Fixtures**: Ethanol ($N=9$) and Water 16-mer cluster $(\text{H}_2\text{O})_{16}$.
   - **Verification**:
     - Serialization: Export model via `torch.jit.script` to temporary `.pt` binary.
     - Double-Precision Parity: Evaluate eager PyTorch vs. TorchScript model in `torch.float64`. Verify:
       $$\frac{|E_{\text{eager}} - E_{\text{script}}|}{|E_{\text{eager}}|} \le 10^{-6} \quad \text{and} \quad L_\infty(\mathbf{F}) \le 10^{-6}\,\text{Hartree/Bohr}$$
     - Dynamic Ragged Shapes: Execute compiled model on molecules of different sizes ($N=3, 9, 48$) sequentially without re-compilation or shape errors.
     - Failure Mode: Inject artificial perturbation into weights and verify parity validator raises `ParityVerificationError`.

4. **`tests/test_torq_distributed_early_stopping.py`** (`REQ-TORQ-TRAIN-094`):
   - **Multi-Process Simulation Harness**: Launch a 2-process mock-free distributed DDP session using PyTorch `mp.spawn` with `backend="gloo"` on CPU.
   - **Verification**:
     - Metric Reduction: Provide asymmetric shard validation losses on rank 0 and rank 1. Verify `torch.distributed.all_reduce(..., op=ReduceOp.AVG)` computes exact mean loss before thresholding.
     - Synchronous Early Stop: Trigger plateau condition on rank 0. Verify rank 0 broadcasts `stop_flag` on `"cpu"` and both ranks terminate synchronously at the identical epoch without deadlock or hanging processes.

5. **`tests/test_torq_loss_landscape.py`** (`REQ-TORQ-TRAIN-095`):
   - **Physical Checkpoint**: A converged 2-layer MLP neural force field model checkpointed on a water molecule.
   - **Verification**:
     - Filter Normalization: Verify random direction vectors satisfy Frobenius norm equality $\|\mathbf{d}_j\|_F = \|\theta^*_j\|_F$ for every parameter tensor $j$.
     - 1D Loss Surface: Profile along direction $\alpha \in [-0.5, 0.5]$. Confirm that the minimum loss occurs at $\alpha = 0$ within $\Delta \alpha < 0.01$, and loss values are non-negative.
     - 2D Contour Render: Generate a $10 \times 10$ grid. Verify memory reclamation via `torch.cuda.empty_cache()` (or CPU garbage collection) and verify contour PNG output is written to disk.

6. **`tests/test_torq_amp_trainer.py`** (`REQ-TORQ-TRAIN-096`):
   - **Physical Fixtures**: Octasulfur $\text{S}_8$ and Krypton-encapsulated Fullerene $\text{Kr@C}_{60}$.
   - **Verification**:
     - Precision Dispatcher: Test precision selection logic across mocked device capabilities (Ampere $\to$ BF16, Turing $\to$ FP16 with GradScaler, CPU/MPS $\to$ FP32).
     - Force Autograd Stability: Ensure coordinates and forces remain in FP32/FP64 throughout mixed-precision backward passes.
     - Unscaling & Clipping: Verify `scaler.unscale_(optimizer)` is executed before `clip_grad_norm_`. Ensure gradient norm does not exceed 1.0.
     - Divergence Handling: Simulate NaN gradient injection and verify `PrecisionDivergenceError` is raised after consecutive scale collapses.

7. **`tests/test_torq_training_persistence.py`** (`Core Storage & Concurrency`):
   - **Verification**:
     - HDF5 Multi-Process Lock: Attempt concurrent write access across two processes; verify second process waits or raises `HDF5LockTimeoutError` when timeout is set to 0.1s.
     - Atomic Checkpoint Replace: Save model checkpoint; verify temporary file `.pt.tmp` is cleanly replaced by `.pt` and accompanied by a matching `.sha256` file. Verify re-loading matches state dict exactly.

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate v3**: Every neural layer, autograd backward pass, distributed barrier, and test assertion must execute physically. Absolutely no `pass` stubs, no `NotImplementedError`, and no synthetic mock arrays (`np.zeros`, `np.ones` as dummy outputs).
2. **Dynamic Mendeleev Monoisotopic Masses**: When atomic masses are required, dynamically query:
   `mendeleev.element(Z).isotopes` filtered by max abundance. Ghost atoms ($Z=0$) receive $0.0\,\text{u}$ mass. No hardcoded atomic mass dictionaries.
3. **Tripartite Workspace Air-Gap**:
   - Ring 1 ($COCHEM_SRC_DIR / R_{\text{src}}$): Read-only source code.
   - Ring 2 ($COCHEM_DATA_DIR / R_{\text{data}}$): Read-only datasets and weights. `COCHEM_OFFLINE=1`. SHA-256 verification.
   - Ring 3 ($COCHEM_ARTIFACTS_DIR / R_{\text{art}}$): Read-write checkpoints, TorchScript bundles, loss landscape plots, logs.
4. **OS-Agnostic Dynamic Paths**: Utilize `pathlib.Path` with environment variable resolution (`COCHEM_SRC_DIR`, `COCHEM_DATA_DIR`, `COCHEM_ARTIFACTS_DIR`, `COCHEM_SCRATCH_DIR`, `SLURM_TMPDIR`). No hardcoded `/home/...` or `C:\...` paths.
5. **6-Tier Environment Execution Matrix**: Ensure cross-platform execution across Tier 1 Windows NT (`gloo`, NTFS filelock), Tier 2 macOS (MPS/CPU, `gloo`), Tier 3 Linux (`nccl`, SWMR), Tiers 4-5 Codespaces & CI/CD (headless CPU), and Tier 6 HPC clusters (`HDF5_USE_FILE_LOCKING="FALSE"`, node-local scratch).

---

### ACTION PLAN FOR CODER

1. Implement `Libraries/cochem_torq_training_errors.py` with the complete domain exception hierarchy.
2. Implement `Libraries/cochem_torq_training_schemas.py` with all Pydantic v2 data models and validators.
3. Implement `Libraries/cochem_torq_gradient_checkpointing.py` for high-batch training with autograd second-order force gradients (`use_reentrant=False`, `preserve_rng_state=True`).
4. Implement `Libraries/cochem_torq_ani2x_transfer.py` for offline SHA-256 domain adaptation, AEV species channel expansion, and LLRD fine-tuning.
5. Implement `Libraries/cochem_torq_torchscript_export.py` for standalone `torch.jit.script` export and float64 numerical parity verification.
6. Implement `Libraries/cochem_torq_distributed_early_stopping.py` with deadlock-free CPU `stop_flag` broadcasting and `all_reduce(ReduceOp.AVG)`.
7. Implement `Libraries/cochem_torq_loss_landscape.py` with filter-normalized Li et al. perturbations and VRAM cache isolation.
8. Implement `Libraries/cochem_torq_amp_trainer.py` with hardware-aware BF16/FP16 dispatching, FP32 force gradients, and unscaled gradient clipping.
9. Implement `Libraries/cochem_torq_training_persistence.py` with SWMR HDF5 locking, DataLoader worker initialization, and atomic `.pt`/`.sha256` checkpoints.
10. Export all public classes, functions, and exceptions in `Libraries/__init__.py`.
11. Author the complete, unmocked test suite:
    - `tests/test_torq_gradient_checkpointing.py`
    - `tests/test_torq_ani2x_transfer.py`
    - `tests/test_torq_torchscript_export.py`
    - `tests/test_torq_distributed_early_stopping.py`
    - `tests/test_torq_loss_landscape.py`
    - `tests/test_torq_amp_trainer.py`
    - `tests/test_torq_training_persistence.py`
12. Execute `pytest tests/ -v` via `run_command` and confirm exit code 0 across all test suites.
I have invoked the `cochem-audit` subagent to conduct an adversarial audit of the generated chunked coding prompt for SRS Chunk 16 (`TORQ_Training_Dynamics_Part_1`), verifying compliance with the Zero-Mock mandate, Method Matrix v4, and the 6-Tier Environment Matrix before final presentation.
I have submitted the fully remediated candidate prompt addressing all 12 defects to `cochem-audit` for re-evaluation. Awaiting its adversarial verification report.
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous training dynamics, transfer learning, and production compilation suite specified in Software Requirements Specification (SRS) Chunk 16: `TORQ_Training_Dynamics_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev monoisotopic mass retrieval mandate, and Method Matrix v4 (`[M]` Empirical Benchmark, `[D]` Derived Mathematical Relationship, `[E]` Estimated Theoretical Projection). Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine physical tensors, authentic molecular coordinates, and real chemical observables.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `Libraries/` and `core/` in `CoChem-TORQ` to verify existing model backbones, potential wrappers, telemetry loggers, and test fixtures established in SRS Chunk 15.
2. **Implementation**: Implement all target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, atomic checkpoint serialization, and custom typed domain exceptions rooted in `CoChemTorqError`.
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering every component using authentic chemical structures and physical fixtures (e.g., Water dimer, Alanine dipeptide $N=22$, Ar-Kr dimer, Fluorobenzene complex, Ethanol $N=9$, Water 16-mer cluster, Octasulfur $\text{S}_8$, and Krypton-encapsulated Fullerene $\text{Kr@C}_{60}$).
4. **Physical Verification**: Execute the test suite using `pytest tests/ -v` via `run_command` in the terminal. Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Domain Exceptions & Pydantic v2 Data Contracts
- **File Target**: `Libraries/cochem_torq_training_schemas.py` and `Libraries/cochem_torq_training_errors.py` (and export in `Libraries/__init__.py`)
- **Exception Hierarchy**:
  ```python
  from typing import Any, Dict, Optional

  class CoChemError(Exception):
      """Base exception for all CoChem operations [M]."""
      pass

  class CoChemTorqError(CoChemError):
      """Base exception for TORQ potential backbones and dynamics [M]."""
      pass

  class TorqTrainingError(CoChemTorqError):
      """Base exception for all TORQ training dynamics errors [M]."""
      def __init__(
          self,
          message: str,
          error_code: str = "TORQ_TRAIN_GENERIC",
          component: str = "training_dynamics",
          diagnostics: Optional[Dict[str, Any]] = None,
      ) -> None:
          super().__init__(message)
          self.error_code = error_code
          self.component = component
          self.diagnostics = diagnostics or {}

  class HDF5LockTimeoutError(TorqTrainingError):
      """Raised when acquiring advisory HDF5 filelock exceeds timeout ceiling [M]."""
      pass

  class PrecisionDivergenceError(TorqTrainingError):
      """Raised when AMP GradScaler encounters unrecoverable NaN/Inf gradients [M]."""
      pass

  class CheckpointCorruptionError(TorqTrainingError):
      """Raised when checkpoint state or SHA-256 checksum validation fails [M]."""
      pass

  class DistributedSyncError(TorqTrainingError):
      """Raised when distributed all-reduce or rank synchronization deadlocks [M]."""
      pass

  class UnsupportedElementError(TorqTrainingError):
      """Raised when input molecular batch contains unmapped atomic species [M]."""
      pass

  class ParityVerificationError(TorqTrainingError):
      """Raised when TorchScript compiled model violates eager numerical parity [M]."""
      pass
  ```
- **Pydantic v2 Data Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
  - `TrainingDynamicsConfig`:
    - `batch_size: int = Field(default=32, ge=1, description="Per-device batch size [M]")`
    - `gradient_checkpointing: bool = Field(default=True, description="Enable activation recomputation [D]")`
    - `mixed_precision_dtype: Literal["bfloat16", "float16", "float32"] = Field(default="bfloat16", description="AMP precision [M]")`
    - `max_gradient_norm: float = Field(default=1.0, gt=0.0, description="Gradient clipping norm ceiling [M]")`
    - `energy_loss_weight: float = Field(default=1.0, ge=0.0, description="Loss weight for potential energy [M]")`
    - `force_loss_weight: float = Field(default=100.0, ge=0.0, description="Loss weight for atomic forces [M]")`
    - `learning_rate: float = Field(default=1e-3, gt=0.0, description="Initial optimizer learning rate [M]")`
    - `weight_decay: float = Field(default=1e-5, ge=0.0, description="AdamW weight decay regularization [M]")`
  - `TransferLearningConfig`:
    - `base_model_path: Path = Field(..., description="Local path to pre-trained ANI-2x weights [M]")`
    - `expected_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$", description="Cryptographic SHA-256 hash [M]")`
    - `freeze_symmetry_functions: bool = Field(default=True, description="Freeze AEV feature extractor [M]")`
    - `layer_decay_rate: float = Field(default=0.8, gt=0.0, le=1.0, description="LLRD decay factor [M]")`
    - `new_species_atomic_numbers: List[int] = Field(default_factory=list, description="New atomic numbers Z to initialize [M]")`
    - Validator `validate_atomic_numbers`: Ensure $1 \le Z \le 118$, return sorted unique integers.
  - `TorchScriptExportConfig`:
    - `export_path: Path = Field(..., description="Destination path for serialized TorchScript .pt model [M]")`
    - `energy_relative_tolerance: float = Field(default=1e-6, gt=0.0, description="Max relative energy error [M]")`
    - `force_parity_tolerance_hartree_angstrom: float = Field(default=1e-6, gt=0.0, description="Max absolute force error in Hartree/Å evaluated in float64 [M]")`
    - `validate_against_fixtures: bool = Field(default=True, description="Execute validation before finalizing export [M]")`
  - `DistributedEarlyStoppingConfig`:
    - `patience_epochs: int = Field(default=15, ge=1, description="Epochs to wait before early termination [M]")`
    - `min_delta_hartree: float = Field(default=1e-5, ge=0.0, description="Minimum validation loss improvement in Hartree [M]")`
    - `synchronize_ranks: Literal[True] = Field(default=True, description="Mandatory broadcast early exit flag across all DDP ranks [D]")`
  - `LossLandscapeConfig`:
    - `grid_resolution: int = Field(default=25, ge=5, le=100, description="Grid points per axis [M]")`
    - `range_min: float = Field(default=-1.0, description="Normalized coordinate min [M]")`
    - `range_max: float = Field(default=1.0, description="Normalized coordinate max [M]")`
    - `filter_normalization: bool = Field(default=True, description="Normalize random directions by filter Frobenius norm [D]")`
    - `output_plot_path: Path = Field(..., description="Destination path for rendered contour plot [M]")`
    - Model validator: Verify `range_min < range_max`.

---

#### 2. Gradient Checkpointing Engine for High-Batch MLFF Training (`REQ-TORQ-TRAIN-091` `[D]`)
- **File Target**: `Libraries/cochem_torq_gradient_checkpointing.py` (and export in `Libraries/__init__.py`)
- **Mathematical Scope & Second-Derivative Autograd Mechanics**:
  - Conservative atomic forces $\mathbf{F}_i \in \mathbb{R}^3$ are negative spatial gradients:
    $$\mathbf{F}_i = -\frac{\partial E_\theta(\mathbf{R}, \mathbf{Z})}{\partial \mathbf{R}_i} \quad [D]$$
  - Joint training composite loss function normalized by total atomic degrees of freedom ($3 \sum N_b$):
    $$\mathcal{L}(\theta) = w_E \frac{1}{B} \sum_{b=1}^B |E_b - E_b^{\text{ref}}|^2 + w_F \frac{1}{3 \sum_{b=1}^B N_b} \sum_{b=1}^B \sum_{i=1}^{N_b} \|\mathbf{F}_{b,i} - \mathbf{F}_{b,i}^{\text{ref}}\|^2 \quad [D]$$
  - Backpropagating force loss requires second-order mixed partial derivatives $\frac{\partial^2 E_\theta}{\partial \theta \partial \mathbf{R}}$ [D].
  - The checkpointing implementation MUST utilize:
    `torch.utils.checkpoint.checkpoint(forward_fn, *args, use_reentrant=False)` [D]
    In PyTorch $\ge 2.0$, `use_reentrant=False` natively captures the backward graph for nested differentiation.
  - The parameters `create_graph=True` and `retain_graph=True` belong strictly in:
    `torch.autograd.grad(outputs=energy.sum(), inputs=coordinates, create_graph=True, retain_graph=True)` [D]
    during analytical force evaluation inside the forward pass; `create_graph` is NEVER passed as a kwarg to `checkpoint()` itself.
- **RNG State & Tensor Cache Isolation**:
  - Random number generator states across all active CUDA and CPU streams must be explicitly captured and restored via `preserve_rng_state=True` [M] to guarantee deterministic dropout/stochastic regularization reproducibility.
  - Dynamic neighbor-list index tensors $\mathcal{E} \in \mathbb{Z}^{2 \times |\mathcal{E}|}$ and interatomic distance vectors $\mathbf{r}_{ij} = \mathbf{R}_j - \mathbf{R}_i$ are treated as immutable graph topology fixtures; exclude them from recomputation graphs to avoid memory fragmentation [D].
- **6-Tier Hardware Gating**:
  - On CUDA platforms, activation recomputation must achieve $VRAM_{\text{checkpoint}} \le 0.45 \times VRAM_{\text{eager}}$ on expanded batch sizes ($4\times$ to $8\times$) [M].
  - On CPU/macOS platforms (Tiers 1, 2, 4, 5), activation recomputation must guarantee bit-for-bit mathematical force autograd parity ($\Delta \mathbf{F} = \max \|\mathbf{F}_{\text{checkpoint}} - \mathbf{F}_{\text{eager}}\|_\infty = 0.0$) [M] with memory tracking validated via `tracemalloc` [M].

---

#### 3. ANI-2x Transfer Learning Pipeline (`REQ-TORQ-TRAIN-092` `[M]`)
- **File Target**: `Libraries/cochem_torq_ani2x_transfer.py` (and export in `Libraries/__init__.py`)
- **Chemical Domain Extension & AEV Alignment**:
  - Standard ANI-2x element set: $\{ \text{H}, \text{C}, \text{N}, \text{O}, \text{S}, \text{F}, \text{Cl} \}$ ($Z \in \{1, 6, 7, 8, 16, 9, 17\}$).
  - Target system expansion: noble gases ($\text{He}, \text{Ne}, \text{Ar}, \text{Kr}, \text{Xe}$ with $Z \in \{2, 10, 18, 36, 54\}$) and heavy halogens ($\text{Br}, \text{I}$ with $Z \in \{35, 53\}$) for dispersion-bound van der Waals complexes [M].
  - **AEV Species Dimension & Weight Matrix Expansion**:
    - Partition radial and angular representations by species pairs $(S_i, S_j)$ and triplets $(S_i, S_j, S_k)$ [D].
    - When expanding chemical domain to novel species (e.g., $\text{Kr}, \text{Xe}, \text{Br}$), expand the AEV feature extractor: frozen parameters for pre-existing species interactions are retained without modification, while interaction channels for novel species are zero-padded and calibrated with standard radial/angular grid shifts [D].
    - **Host-Guest Mutual Polarization Guarantee**: To prevent amputation of host atom sensitivity to guest atoms (which destroys Newton's third law $\mathbf{F}_{ij} = -\mathbf{F}_{ji}$), pre-existing species atomic heads MUST NOT use naive species-channel slicing. Instead, expand the input weight matrix $W_1$ of pre-existing heads ($1008 \to 1584$) with zero-initialization on novel species channels ($W_1[:, \text{new\_idx}] = \mathbf{0}$) [D]. This guarantees exact baseline energy parity at initialization while enabling cross-species polarization and gradient updates during LLRD fine-tuning [D].
    - Initialize novel species atomic heads with truncated normal weights (He initialization, gain $\sqrt{2}$) and zero bias [D].
    - Fine-tune pre-existing species heads using Layer-wise Learning Rate Decay (LLRD) with decay factor $\gamma = 0.8$ applied per hidden layer [M].
- **Air-Gap & Offline Ingestion (`COCHEM_OFFLINE=1`)**:
  - Zero external network egress. Automatic downloads via TorchANI or HuggingFace Hub are strictly forbidden [M].
  - Ingest pre-trained weights from Ring 2 local storage (`$COCHEM_DATA_DIR/models/ani2x/`) and validate against hardcoded cryptographic SHA-256 signatures prior to parameter ingestion [M]. Raise `CheckpointCorruptionError` if hash mismatch occurs.
  - If input coordinates contain elements outside base ANI-2x set and registered fine-tuned heads, immediately raise `UnsupportedElementError` [M].
  - Provide an unmocked physical fixture generator `generate_test_ani2x_weights(output_dir: Path) -> Tuple[Path, str]` [M] that builds an authentic ANI-2x state dict in memory, serializes to Ring 2 (`$COCHEM_DATA_DIR/models/ani2x/`), computes its SHA-256 digest dynamically, and returns the path and hash for air-gap testing [M].

---

#### 4. Dedicated TorchScript Compilation for C++ Inference (`REQ-TORQ-TRAIN-093` `[D]`)
- **File Target**: `Libraries/cochem_torq_torchscript_export.py` (and export in `Libraries/__init__.py`)
- **Compilation Protocol & Dynamic Ragged Topology**:
  - Models must be exported via `torch.jit.script` (NOT static `torch.jit.trace`) to ensure full support for dynamic control flow, variable molecular sizes, and conditionally evaluated neighbor-list cutoffs [D].
  - Dynamic tensor dimensions on leading batch and coordinate dimensions:
    - Atomic coordinates: $\mathbf{R} \in \mathbb{R}^{N_{\text{atoms}} \times 3}$ [M]
    - Atomic numbers: $\mathbf{Z} \in \mathbb{Z}^{N_{\text{atoms}}}$ [M]
    - Dynamic neighbor pairs: $\mathcal{E} \in \mathbb{Z}^{2 \times N_{\text{edges}}}$ [D]
    - Molecule batch pointers: $\mathbf{P} \in \mathbb{Z}^{B+1}$ [D]
- **Numerical Parity Verification & Acceptance Thresholds**:
  - Automated numerical parity verification against eager PyTorch across physical test fixtures (water cluster, alanine dipeptide, Ar-Kr dimer).
  - Coordinates consume $\text{\AA}$ and output energy in $\text{Hartree}$; spatial forces $\mathbf{F} = -\nabla_\mathbf{R} E$ are in $\text{Hartree/\AA}$ ($1\text{ Hartree/\AA} \approx 27.211386\text{ eV/\AA}$) [D].
  - Tolerances enforced strictly in double precision `torch.float64` [M]:
    - Relative energy error: $\frac{|E_{\text{eager}} - E_{\text{script}}|}{|E_{\text{eager}}|} \le 10^{-6}$ (or absolute error $L_\infty(E) \le 10^{-6}\,\text{Hartree}$) [M].
    - Maximum absolute force error: $L_\infty(\mathbf{F}) = \max \|\mathbf{F}_{\text{eager}} - \mathbf{F}_{\text{script}}\|_\infty \le 10^{-6}\,\text{Hartree/\AA}$ ($\approx 2.7211 \times 10^{-5}\,\text{eV/\AA}$) [M].
  - Binaries failing parity thresholds are rejected and raise `ParityVerificationError` [M].

---

#### 5. Multi-GPU Distributed Early Stopping & Deadlock Prevention (`REQ-TORQ-TRAIN-094` `[D]`)
- **File Target**: `Libraries/cochem_torq_distributed_early_stopping.py` (and export in `Libraries/__init__.py`)
- **Cross-Rank Metric Reduction & Synchronization**:
  - Local validation losses evaluated across shard batches on rank $r$ with sample count $N_r$ are reduced globally before patience decisions via count-weighted summation:
    $$\bar{\mathcal{L}}_{\text{val}} = \frac{\sum_{r=0}^{W-1} \sum_{b \in \mathcal{B}_r} \mathcal{L}_b}{\sum_{r=0}^{W-1} N_r} \quad [D]$$
  - Metric aggregation MUST execute via `torch.distributed.all_reduce(sum_loss_and_count_tensor, op=torch.distributed.ReduceOp.SUM)` [D].
  - Ranks are strictly prohibited from evaluating early-stopping logic on rank-local loss shards [D].
- **Deadlock-Free Termination Protocol**:
  - Collective synchronization MUST execute unconditionally across ALL ranks on EVERY validation epoch:
    ```python
    stop_flag = torch.zeros(1, dtype=torch.int32, device="cpu")
    if rank == 0 and plateau_patience_exceeded:
        stop_flag.fill_(1)
    torch.distributed.broadcast(stop_flag, src=0)
    if stop_flag.item() == 1:
        torch.distributed.barrier()
        break
    ```
  - Binding `stop_flag` to `"cpu"` guarantees cross-platform compatibility and prevents Gloo collective serialization crashes on Tier 1 Windows and Tier 2 macOS [M].
  - Multiprocessing DDP worker routines must be defined as top-level module functions to ensure pickleability on Windows NT, with dynamic ephemeral port binding (`socket.bind(('', 0))`) to prevent port collisions [M].

---

#### 6. Scale-Invariant Loss Landscape Visualization (`REQ-TORQ-TRAIN-095` `[D]`)
- **File Target**: `Libraries/cochem_torq_loss_landscape.py` (and export in `Libraries/__init__.py`)
- **Filter-Normalized Perturbation Formulation (Li et al., 2018)**:
  $$\theta(\alpha, \beta) = \theta^* + \alpha \mathbf{d}_1 + \beta \mathbf{d}_2 \quad [D]$$
  - For each parameter tensor layer/filter $j$, direction vectors $\mathbf{d}_{k,j}$ are normalized to match the Frobenius norm of the corresponding parameter filter $\theta^*_j$:
    $$\mathbf{d}_{k, j} = \frac{\mathbf{v}_{k, j}}{\|\mathbf{v}_{k, j}\|_F} \|\theta^*_j\|_F \quad \text{where} \quad \mathbf{v}_{k, j} \sim \mathcal{N}(0, I) \quad [D]$$
  - 1D profiling: $\beta = 0$ with $\alpha \in [-1.0, 1.0]$ [M].
  - 2D contours: $(\alpha, \beta) \in [-1.0, 1.0]^2$ sampled over an $M \times M$ equidistant grid ($M \le 50$) [M].
- **Convergence Prerequisite & VRAM Isolation**:
  - The local minimum at $\alpha = 0$ is mathematically guaranteed only if $\theta^*$ is a converged local stationary point ($\|\nabla \mathcal{L}\| < 10^{-4}$) [D]. Test fixtures must pre-train the model on a physical structure (e.g., 200 AdamW steps on water fixture) prior to landscape profiling [M].
  - Landscape evaluations execute strictly under `torch.no_grad()` in an isolated inference sub-context [D].
  - Between evaluation grid points, intermediate activations are unlinked and GPU memory is reclaimed via `torch.cuda.empty_cache()` (or CPU garbage collection) to prevent OOM faults [M].
  - Render high-resolution contour plots and save to `output_plot_path` using `matplotlib` Agg backend [M].

---

#### 7. Dynamic Mixed-Precision (FP16/BF16) Training Engine (`REQ-TORQ-TRAIN-096` `[M]`)
- **File Target**: `Libraries/cochem_torq_amp_trainer.py` (and export in `Libraries/__init__.py`)
- **Hardware-Aware Precision Dispatching (Zero-Mock Dependency Injection)**:
  - Implement dynamic precision resolution without mocking hardware:
    `def resolve_amp_precision(device: torch.device, compute_capability: Optional[Tuple[int, int]] = None) -> Tuple[torch.dtype, Optional[torch.amp.GradScaler]]:` [D]
  - Selection logic:
    - **Compute Capability $\ge 8.0$ (Ampere, Hopper, Ada Lovelace)**: Bfloat16 (`torch.bfloat16`) via `torch.amp.autocast(device_type=device.type, dtype=torch.bfloat16)` [M]. BF16 preserves the 8-bit dynamic exponent of FP32, eliminating underflow and obviating dynamic loss scaling [D].
    - **Compute Capability $< 8.0$ (Volta, Turing)**: Float16 (`torch.float16`) coordinated via `torch.amp.GradScaler(init_scale=65536.0, growth_factor=2.0, backoff_factor=0.5)` [M].
    - **Apple Silicon (MPS) & CPU**: Native FP32 execution (or CPU BF16 autocast where supported by PyTorch runtime), returning `None` for `GradScaler` [M].
- **Force Gradient Precision & Gradient Clipping Integration**:
  - Input coordinates $\mathbf{R}$ and force gradient autograd graphs ($\nabla_\mathbf{R} E_\theta$) MUST be cast to and retained in `torch.float32` (or `torch.float64`) to prevent underflow artifacts in tensor contractions [M].
  - When utilizing FP16 `GradScaler`, gradients must be explicitly unscaled prior to norm-based clipping:
    ```python
    scaler.unscale_(optimizer)
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=config.max_gradient_norm)
    ```
    [M].
  - Raise `PrecisionDivergenceError` if unrecoverable NaN/Inf gradients persist across consecutive scaling cycles [M].

---

#### 8. Thread-Safe HDF5 Storage & Atomic Checkpointing Engine
- **File Target**: `Libraries/cochem_torq_training_persistence.py` (and export in `Libraries/__init__.py`)
- **Thread-Safe SWMR Storage & Cluster Locking**:
  - Chunked HDF5 storage with `gzip` (level 4) compression, `shuffle` filter enabled, and `fletcher32` checksum validation [M].
  - POSIX environments: `swmr=True`, `libver="latest"` [M].
  - Advisory file locks: `filelock.FileLock(lock_path, timeout=30.0)` for cross-process concurrency and `threading.Lock()` for intra-process safety [M]. Raise `HDF5LockTimeoutError` on timeout [M].
  - **HPC Cluster Filesystem Locking**: On networked distributed filesystems (Lustre/GPFS/NFS), native HDF5 kernel-level locks deadlock. The environment variable `HDF5_USE_FILE_LOCKING="FALSE"` MUST be set dynamically on cluster nodes [M]. All advisory file locks MUST be placed in the shared cluster filesystem directory containing the dataset (`path.with_suffix(".h5.lock")` on the shared mount) to ensure visibility across all compute nodes, NOT in node-local NVMe scratch `$SLURM_TMPDIR` [M].
  - Multi-worker PyTorch `DataLoader`: Worker initialization routine (`worker_init_fn`) instantiates independent HDF5 file handles per worker process [M].
- **Atomic Checkpoint Serialization**:
  - Checkpoint files (`.pt` / `.h5`) are written to an isolated temporary file (`checkpoint.pt.tmp`), flushed to disk via `os.fsync(f.fileno())`, and atomically moved to destination via `os.replace` [M].
  - Accompanying `.sha256` digest file generated for every saved checkpoint [M]. Raise `CheckpointCorruptionError` if digest verification fails upon reload [M].

---

#### 9. Dynamic Monoisotopic Mass Engine
- **File Target**: `Libraries/cochem_torq_masses.py` (and export in `Libraries/__init__.py`)
- **Mendeleev Integration with Unstable Element Fallback**:
  - Query atomic/isotopic masses dynamically:
    ```python
    from mendeleev import element

    def get_monoisotopic_mass(atomic_number: int) -> float:
        if atomic_number == 0:
            return 0.0  # Ghost atom [M]
        el = element(atomic_number)
        stable_isotopes = [iso for iso in el.isotopes if iso.abundance is not None and iso.abundance > 0.0]
        if stable_isotopes:
            return float(max(stable_isotopes, key=lambda iso: iso.abundance).mass)
        # Fallback for elements without stable isotopes (e.g. Tc Z=43, Pm Z=61) [D]
        return float(max(el.isotopes, key=lambda iso: (iso.half_life or 0.0, iso.mass_number)).mass)
    ```
  - Hardcoded mass dictionaries are strictly forbidden [M].

---

### TEST SUITE SPECIFICATIONS

All tests must be authentic, physically executing against real molecular coordinates and physical observables without mocks or stubs under `tests/`:

1. **`tests/test_torq_gradient_checkpointing.py`** (`REQ-TORQ-TRAIN-091`):
   - **Physical Fixtures**: Water dimer $(\text{H}_2\text{O})_2$ and Alanine dipeptide $(N=22)$.
   - **Verification**:
     - Analytical Force Parity: Compute forces with and without checkpointing. Verify exact numerical match $\Delta \mathbf{F} = \max \|\mathbf{F}_{\text{checkpoint}} - \mathbf{F}_{\text{eager}}\|_\infty = 0.0$ (within machine precision $10^{-7}$) across all platforms [M].
     - RNG State Determinism: Verify that dropout/stochastic layers produce bit-for-bit identical outputs during recomputation passes with `preserve_rng_state=True` [M].
     - Memory Benchmarking: On CUDA platforms, assert $VRAM_{\text{checkpoint}} \le 0.45 \times VRAM_{\text{eager}}$ gated with `@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for VRAM benchmark")` [M]. On CPU platforms, verify memory allocation tracking via `tracemalloc` [M].

2. **`tests/test_torq_ani2x_transfer.py`** (`REQ-TORQ-TRAIN-092`):
   - **Physical Fixtures**: Ar-Kr dimer and Fluorobenzene non-covalent complex.
   - **Verification**:
     - Unmocked Fixture Generation: Use `generate_test_ani2x_weights(scratch_dir)` to write authentic weights and compute genuine SHA-256 [M].
     - Cryptographic Ingestion: Verify pre-trained base weights load offline with valid SHA-256 digest; corrupting a byte in weights raises `CheckpointCorruptionError` [M].
     - Head Expansion & Mutual Polarization: Expand base model to noble gas species ($Z=36$ Kr, $Z=18$ Ar). Verify base heads retain original slice dimensions, new heads initialize with He normal gain $\sqrt{2}$ and zero bias [D]. Verify input matrix $W_1$ zero-padding yields identical base energies at initialization while allowing non-zero forces $\mathbf{F}_{\text{host}} = -\mathbf{F}_{\text{guest}}$ during backpropagation [D].
     - LLRD Verification: Verify learning rates decrease per hidden layer with factor $\gamma = 0.8$ [M].
     - Unsupported Elements: Ingest coordinates containing unregistered heavy element (e.g., $Z=80$ Hg) and assert `UnsupportedElementError` is raised [M].

3. **`tests/test_torq_torchscript_export.py`** (`REQ-TORQ-TRAIN-093`):
   - **Physical Fixtures**: Ethanol ($N=9$) and Water 16-mer cluster $(\text{H}_2\text{O})_{16}$.
   - **Verification**:
     - Serialization: Export model via `torch.jit.script` to temporary `.pt` binary [M].
     - Double-Precision Parity: Evaluate eager PyTorch vs. TorchScript model in `torch.float64`. Verify:
       $$\frac{|E_{\text{eager}} - E_{\text{script}}|}{|E_{\text{eager}}|} \le 10^{-6} \quad \text{and} \quad L_\infty(\mathbf{F}) \le 10^{-6}\,\text{Hartree/\AA} \quad [M]$$
       ($\approx 2.7211 \times 10^{-5}\,\text{eV/\AA}$) [D].
     - Dynamic Ragged Shapes: Execute compiled model on molecules of different sizes ($N=3, 9, 48$) sequentially without re-compilation or shape errors [M].
     - Failure Mode: Inject artificial perturbation into weights and verify parity validator raises `ParityVerificationError` [M].

4. **`tests/test_torq_distributed_early_stopping.py`** (`REQ-TORQ-TRAIN-094`):
   - **Multi-Process Simulation Harness**: Launch a 2-process mock-free distributed DDP session using PyTorch `mp.spawn` with `backend="gloo"` on CPU, using a top-level module worker function and dynamic ephemeral port selection [M].
   - **Verification**:
     - Count-Weighted Metric Reduction: Provide asymmetric shard validation losses on rank 0 ($N_0=20$) and rank 1 ($N_1=10$). Verify count-weighted all-reduce computes exact weighted mean loss before thresholding [D].
     - Synchronous Early Stop: Trigger plateau condition on rank 0. Verify rank 0 broadcasts `stop_flag` on `"cpu"` and both ranks terminate synchronously at the identical epoch without deadlock or hanging processes [D].

5. **`tests/test_torq_loss_landscape.py`** (`REQ-TORQ-TRAIN-095`):
   - **Physical Checkpoint**: Pre-train a 2-layer MLP neural force field model for 200 steps on a water molecule until $\|\nabla \mathcal{L}\| < 10^{-4}$ [M].
   - **Verification**:
     - Filter Normalization: Verify random direction vectors satisfy Frobenius norm equality $\|\mathbf{d}_j\|_F = \|\theta^*_j\|_F$ for every parameter tensor $j$ [D].
     - 1D Loss Surface: Profile along direction $\alpha \in [-0.5, 0.5]$. Confirm that the minimum loss occurs at $\alpha = 0$ within $\Delta \alpha < 0.01$ [D], and loss values are non-negative [M].
     - 2D Contour Render: Generate a $10 \times 10$ grid. Verify memory reclamation via `torch.cuda.empty_cache()` (or CPU garbage collection) and verify contour PNG output is written to disk [M].

6. **`tests/test_torq_amp_trainer.py`** (`REQ-TORQ-TRAIN-096`):
   - **Physical Fixtures**: Octasulfur $\text{S}_8$ and Krypton-encapsulated Fullerene $\text{Kr@C}_{60}$.
   - **Verification**:
     - Precision Dispatcher: Test precision selection logic via dependency injection `compute_capability`: `(8, 0)` selects BF16 without scaler, `(7, 5)` selects FP16 with GradScaler, `None` (CPU/MPS) selects FP32 without scaler [D]. Zero mocks utilized.
     - Force Autograd Stability: Ensure coordinates and forces remain in FP32/FP64 throughout mixed-precision backward passes [M].
     - Unscaling & Clipping: Verify `scaler.unscale_(optimizer)` is executed before `clip_grad_norm_`. Ensure gradient norm does not exceed 1.0 [M].
     - Divergence Handling: Simulate NaN gradient injection and verify `PrecisionDivergenceError` is raised after consecutive scale collapses [M].

7. **`tests/test_torq_training_persistence.py`** (`Core Storage & Concurrency`):
   - **Verification**:
     - HDF5 Multi-Process Lock: Attempt concurrent write access across two processes; verify second process waits or raises `HDF5LockTimeoutError` when timeout is set to 0.1s [M].
     - Shared Cluster Directory Lock: Verify lock path resides in shared dataset directory rather than node-local scratch [M].
     - Atomic Checkpoint Replace: Save model checkpoint; verify temporary file `.pt.tmp` is cleanly replaced by `.pt` and accompanied by a matching `.sha256` file [M]. Verify re-loading matches state dict exactly [M].

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate v3**: Every neural layer, autograd backward pass, distributed barrier, and test assertion must execute physically. Absolutely no `pass` stubs, no `NotImplementedError`, and no synthetic mock arrays (`np.zeros`, `np.ones` as dummy outputs).
2. **Dynamic Mendeleev Monoisotopic Masses**: When atomic masses are required, dynamically query:
   `mendeleev.element(Z).isotopes` filtered by max abundance, with fallback to longest half-life for unstable elements ($Z=43, 61$). Ghost atoms ($Z=0$) receive $0.0\,\text{u}$ mass. No hardcoded atomic mass dictionaries [M].
3. **Tripartite Workspace Air-Gap**:
   - Ring 1 ($COCHEM_SRC_DIR / R_{\text{src}}$): Read-only source code.
   - Ring 2 ($COCHEM_DATA_DIR / R_{\text{data}}$): Read-only datasets and weights. `COCHEM_OFFLINE=1`. SHA-256 verification.
   - Ring 3 ($COCHEM_ARTIFACTS_DIR / R_{\text{art}}$): Read-write checkpoints, TorchScript bundles, loss landscape plots, logs.
4. **OS-Agnostic Dynamic Paths**: Utilize `pathlib.Path` with environment variable resolution (`COCHEM_SRC_DIR`, `COCHEM_DATA_DIR`, `COCHEM_ARTIFACTS_DIR`, `COCHEM_SCRATCH_DIR`, `SLURM_TMPDIR`). No hardcoded `/home/...` or `C:\...` paths.
5. **6-Tier Environment Execution Matrix**: Ensure cross-platform execution across Tier 1 Windows NT (`gloo`, NTFS filelock), Tier 2 macOS (MPS/CPU, `gloo`), Tier 3 Linux (`nccl`, SWMR), Tiers 4-5 Codespaces & CI/CD (headless CPU), and Tier 6 HPC clusters (`HDF5_USE_FILE_LOCKING="FALSE"`, shared mount locking).

---

### ACTION PLAN FOR CODER

1. Implement `Libraries/cochem_torq_training_errors.py` with the complete domain exception hierarchy rooted in `CoChemTorqError`.
2. Implement `Libraries/cochem_torq_training_schemas.py` with all Pydantic v2 data models, fields, and validators.
3. Implement `Libraries/cochem_torq_masses.py` with dynamic Mendeleev monoisotopic mass queries and unstable element fallbacks.
4. Implement `Libraries/cochem_torq_gradient_checkpointing.py` for high-batch training with autograd second-order force gradients (`use_reentrant=False`, `preserve_rng_state=True`).
5. Implement `Libraries/cochem_torq_ani2x_transfer.py` for offline SHA-256 domain adaptation, AEV weight matrix expansion, mutual polarization preservation, and LLRD fine-tuning.
6. Implement `Libraries/cochem_torq_torchscript_export.py` for standalone `torch.jit.script` export and float64 numerical parity verification in $\text{Hartree/\AA}$.
7. Implement `Libraries/cochem_torq_distributed_early_stopping.py` with deadlock-free CPU `stop_flag` broadcasting, count-weighted loss reduction, and Windows NT pickleable routines.
8. Implement `Libraries/cochem_torq_loss_landscape.py` with filter-normalized Li et al. perturbations and VRAM cache isolation.
9. Implement `Libraries/cochem_torq_amp_trainer.py` with hardware-aware BF16/FP16 dispatching via dependency injection, FP32 force gradients, and unscaled gradient clipping.
10. Implement `Libraries/cochem_torq_training_persistence.py` with SWMR HDF5 locking on shared filesystems, DataLoader worker initialization, and atomic `.pt`/`.sha256` checkpoints.
11. Export all public classes, functions, and exceptions in `Libraries/__init__.py`.
12. Author the complete, unmocked test suite:
    - `tests/test_torq_gradient_checkpointing.py`
    - `tests/test_torq_ani2x_transfer.py`
    - `tests/test_torq_torchscript_export.py`
    - `tests/test_torq_distributed_early_stopping.py`
    - `tests/test_torq_loss_landscape.py`
    - `tests/test_torq_amp_trainer.py`
    - `tests/test_torq_training_persistence.py`
13. Execute `pytest tests/ -v` via `run_command` and confirm exit code 0 across all test suites.
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
    "ANY",
    "sentinel",
    "call",
    "call_args",
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
        if func_name in {"__import__", "import_module"} and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            target_mod = node.args[0].value
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

        if isinstance(node.func, ast.Attribute) and node.func.attr == "setattr":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "monkeypatch":
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="MONKEYPATCH_INTERCEPT",
                        symbol="monkeypatch.setattr",
                        message="Prohibited monkeypatch intercept of core system interfaces",
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

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        if not self.is_exempt:
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
            combined = "".join(parts)
            if "mock" in combined.lower() or "unittest.mock" in combined.lower():
                self.violations.append(
                    Violation(
                        file_path=self.rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="OBFUSCATION",
                        symbol=combined,
                        message=f"Obfuscated mock token via f-string '{combined}'",
                    )
                )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not self.is_exempt and isinstance(node.value, str):
            val = node.value.strip()
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
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self._check_ident(node.id, node, "variable")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self._check_ident(node.attr, node, "attribute")
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self._check_ident(node.arg, node, "argument")
        self.generic_visit(node)


def check_file(
    file_path: Path,
    repo_root: Path,
    amnesty_set: Set[str],
) -> List[Violation]:
    """Analyze a single Python file for AST anti-spoof violations."""
    rel_path = file_path.relative_to(repo_root).as_posix() if repo_root in file_path.parents or file_path == repo_root else file_path.name

    is_tool_exemption = file_path.name == "anti_spoof_linter.py" or "test_anti_spoof" in file_path.name
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_torq_amp_trainer.py ---
"""Authentic physical verification test suite for Mixed-Precision Training Engine (REQ-TORQ-TRAIN-096).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Authentic Octasulfur S8 and Kr@C60 fixtures with dependency injection.
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_amp_trainer import (
    AMPTrainer,
    resolve_amp_precision,
)
from Libraries.cochem_torq_training_errors import PrecisionDivergenceError
from Libraries.cochem_torq_training_schemas import TrainingDynamicsConfig
from tests.torq_test_fixtures import (
    get_kr_fullerene_c60_fixture,
    get_octasulfur_s8_fixture,
)


class PhysicalMLFFBackbone(nn.Module):
    """Authentic physical neural backbone for Octasulfur and Kr@C60 mixed-precision validation."""

    def __init__(self, hidden_dim: int = 32) -> None:
        super().__init__()
        self.embedding = nn.Embedding(119, hidden_dim)
        self.r_centers = nn.Parameter(
            torch.linspace(1.0, 7.0, 16, dtype=torch.float32),
            requires_grad=False,
        )
        self.mlp = nn.Sequential(
            nn.Linear(hidden_dim + 16, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        coordinates: torch.Tensor,
        species: torch.Tensor,
        edge_index: torch.Tensor | None = None,
        batch: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # Distance calculation in FP32
        diff = coordinates.unsqueeze(1) - coordinates.unsqueeze(0)
        dist = torch.norm(diff + 1e-12, dim=-1)
        r_exp = torch.exp(-0.5 * torch.square((dist.unsqueeze(-1) - self.r_centers) / 0.5))
        r_sum = torch.sum(r_exp, dim=1)  # (N, 16)

        z_emb = self.embedding(species)
        node_features = torch.cat([z_emb, r_sum], dim=-1)
        atomic_e = self.mlp(node_features).squeeze(-1)
        return torch.sum(atomic_e)


def test_hardware_aware_precision_dispatcher_dependency_injection() -> None:
    """Verify precision dispatching logic across hardware compute capabilities via dependency injection. [D]"""
    # 1. Ampere/Hopper (8, 0) -> BF16 without GradScaler
    cuda_dev = torch.device("cuda:0" if torch.cuda.is_available() else "cuda")
    dtype_ampere, scaler_ampere = resolve_amp_precision(cuda_dev, compute_capability=(8, 0))
    assert dtype_ampere == torch.bfloat16
    assert scaler_ampere is None

    # 2. Turing/Volta (7, 5) -> FP16 with GradScaler
    dtype_turing, scaler_turing = resolve_amp_precision(cuda_dev, compute_capability=(7, 5))
    assert dtype_turing == torch.float16
    assert scaler_turing is not None
    assert isinstance(scaler_turing, torch.amp.GradScaler)

    # 3. CPU / MPS -> Native FP32 without GradScaler
    cpu_dev = torch.device("cpu")
    dtype_cpu, scaler_cpu = resolve_amp_precision(cpu_dev, compute_capability=None)
    assert dtype_cpu == torch.float32
    assert scaler_cpu is None


def test_octasulfur_s8_training_step_and_gradient_clipping() -> None:
    """Verify force autograd precision and gradient norm clipping on Octasulfur S8. [M]"""
    coords, species = get_octasulfur_s8_fixture()
    coords = coords.to(torch.float32)

    torch.manual_seed(42)
    model = PhysicalMLFFBackbone(hidden_dim=32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    config = TrainingDynamicsConfig(
        max_gradient_norm=1.0,
        energy_loss_weight=1.0,
        force_loss_weight=50.0,
    )

    trainer = AMPTrainer(
        model=model,
        optimizer=optimizer,
        config=config,
        device=torch.device("cpu"),
    )

    ref_energy = torch.tensor(0.0, dtype=torch.float32)
    ref_forces = torch.zeros_like(coords)

    tot_loss, e_loss, f_loss = trainer.train_step(
        coordinates=coords,
        species=species,
        ref_energy=ref_energy,
        ref_forces=ref_forces,
    )

    assert tot_loss > 0.0
    assert e_loss >= 0.0
    assert f_loss >= 0.0
    assert not torch.isnan(torch.tensor(tot_loss))


def test_kr_fullerene_c60_high_atom_count_stability() -> None:
    """Verify autograd force graph stability on high-atom Kr@C60 (N=61 atoms). [M]"""
    coords, species = get_kr_fullerene_c60_fixture()
    coords = coords.to(torch.float32)

    torch.manual_seed(101)
    model = PhysicalMLFFBackbone(hidden_dim=24)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    config = TrainingDynamicsConfig(
        max_gradient_norm=0.5,
        energy_loss_weight=1.0,
        force_loss_weight=10.0,
    )

    trainer = AMPTrainer(
        model=model,
        optimizer=optimizer,
        config=config,
        device=torch.device("cpu"),
    )

    ref_energy = torch.tensor(-10.0, dtype=torch.float32)
    ref_forces = torch.zeros_like(coords)

    tot_loss, e_loss, f_loss = trainer.train_step(
        coordinates=coords,
        species=species,
        ref_energy=ref_energy,
        ref_forces=ref_forces,
    )

    assert tot_loss > 0.0
    assert not torch.isnan(torch.tensor(tot_loss))


def test_precision_divergence_detection() -> None:
    """Verify PrecisionDivergenceError is raised when unrecoverable NaN gradients persist. [M]"""
    coords, species = get_octasulfur_s8_fixture()
    coords = coords.to(torch.float32)

    model = PhysicalMLFFBackbone(hidden_dim=16)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    config = TrainingDynamicsConfig()
    trainer = AMPTrainer(model, optimizer, config, device=torch.device("cpu"))

    # Force NaN in model weights to trigger divergence
    with torch.no_grad():
        for p in model.parameters():
            p.fill_(float("nan"))
            break

    ref_e = torch.tensor(0.0, dtype=torch.float32)
    ref_f = torch.zeros_like(coords)

    with pytest.raises(PrecisionDivergenceError) as exc_info:
        for _ in range(5):
            trainer.train_step(coords, species, ref_e, ref_f)

    assert exc_info.value.error_code == "TORQ_TRAIN_PRECISION_DIVERGENCE"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_torq_ani2x_transfer.py ---
"""Authentic physical verification test suite for ANI-2x Transfer Learning Pipeline (REQ-TORQ-TRAIN-092).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Authentic Ar-Kr dimer and Fluorobenzene complex fixtures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import torch

from Libraries.cochem_torq_ani2x_transfer import (
    BASE_ANI2X_SPECIES,
    ANI2xModel,
    expand_ani2x_domain,
    generate_test_ani2x_weights,
    get_llrd_parameter_groups,
    load_verified_ani2x_weights,
)
from Libraries.cochem_torq_training_errors import (
    CheckpointCorruptionError,
    UnsupportedElementError,
)
from tests.torq_test_fixtures import (
    get_ar_kr_dimer_fixture,
    get_fluorobenzene_complex_fixture,
)


def test_cryptographic_ingestion_and_tamper_detection() -> None:
    """Verify offline SHA-256 validation and CheckpointCorruptionError upon byte alteration. [M]"""
    with tempfile.TemporaryDirectory() as tmpdir:
        weights_dir = Path(tmpdir)
        weights_path, valid_hash = generate_test_ani2x_weights(weights_dir)

        # 1. Successful verified ingestion
        state_dict = load_verified_ani2x_weights(weights_path, valid_hash)
        assert isinstance(state_dict, dict)
        assert len(state_dict) > 0

        # 2. Corrupted hash test
        corrupt_hash = valid_hash[:-4] + "0000"
        with pytest.raises(CheckpointCorruptionError):
            load_verified_ani2x_weights(weights_path, corrupt_hash)

        # 3. Physical file tampering test: flip a single byte in file
        with open(weights_path, "r+b") as f:
            f.seek(10)
            orig_byte = f.read(1)
            f.seek(10)
            f.write(bytes([(orig_byte[0] ^ 0xFF)]))

        with pytest.raises(CheckpointCorruptionError):
            load_verified_ani2x_weights(weights_path, valid_hash)


def test_fluorobenzene_baseline_energy_parity_upon_expansion() -> None:
    """Verify input matrix W1 expansion guarantees exact baseline energy parity at initialization. [D]"""
    coords, species = get_fluorobenzene_complex_fixture()

    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)
    base_model.eval()
    baseline_energy = base_model(coords, species).item()

    # Expand domain to include noble gases Argon (18) and Krypton (36)
    expanded_model = expand_ani2x_domain(base_model, new_species_atomic_numbers=[18, 36])
    expanded_model.eval()
    expanded_energy = expanded_model(coords, species).item()

    # Invariant: W1 zero-initialization on novel species channels guarantees bit-for-bit identical energy
    energy_diff = abs(baseline_energy - expanded_energy)
    assert energy_diff < 1e-10, (
        f"Baseline energy altered upon domain expansion: diff={energy_diff:.2e} Hartree."
    )


def test_ar_kr_dimer_mutual_polarization_forces() -> None:
    """Verify host-guest mutual polarization: gradients flow into W1 and obey Newton's third law. [D]"""
    coords, species = get_ar_kr_dimer_fixture()
    coords = coords.clone().detach().requires_grad_(True)

    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)
    expanded_model = expand_ani2x_domain(base_model, new_species_atomic_numbers=[18, 36])
    expanded_model.train()

    energy = expanded_model(coords, species)
    assert not torch.isnan(energy)
    assert not torch.isinf(energy)

    # Compute analytical forces
    forces = -torch.autograd.grad(energy, coords, create_graph=True)[0]
    assert forces.shape == (2, 3)

    # Interspecies force balance (Newton's third law for dimer along z-axis: F_Ar + F_Kr = 0)
    net_force = torch.sum(forces, dim=0)
    max_net_force = torch.max(torch.abs(net_force)).item()
    assert max_net_force < 1e-6, f"Newton third law violation in Ar-Kr dimer: net force {max_net_force:.2e}."


def test_llrd_learning_rate_decay_hierarchy() -> None:
    """Verify Layer-wise Learning Rate Decay (LLRD) reduces learning rates by gamma=0.8 per layer. [M]"""
    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)
    expanded_model = expand_ani2x_domain(base_model, new_species_atomic_numbers=[36])

    base_lr = 1e-3
    gamma = 0.8
    param_groups = get_llrd_parameter_groups(
        expanded_model,
        base_learning_rate=base_lr,
        layer_decay_rate=gamma,
    )

    assert len(param_groups) > 0

    # Group learning rates by head
    for z_str in expanded_model.heads.keys():
        head_groups = [
            g for g in param_groups
            if g["layer_name"].startswith(f"head_{z_str}_") and "weight" in g["layer_name"]
        ]
        assert len(head_groups) == 4  # 3 hidden layers + 1 readout layer

        # Expected decay: layer 3 (readout): base_lr * gamma^0 = 1e-3
        # layer 2: base_lr * gamma^1 = 8e-4
        # layer 1: base_lr * gamma^2 = 6.4e-4
        # layer 0: base_lr * gamma^3 = 5.12e-4
        lr_values = [g["lr"] for g in head_groups]
        assert pytest.approx(lr_values[3], rel=1e-5) == base_lr
        assert pytest.approx(lr_values[2], rel=1e-5) == base_lr * gamma
        assert pytest.approx(lr_values[1], rel=1e-5) == base_lr * (gamma ** 2)
        assert pytest.approx(lr_values[0], rel=1e-5) == base_lr * (gamma ** 3)


def test_unsupported_element_exception() -> None:
    """Verify UnsupportedElementError is raised immediately when unregistered species are passed. [M]"""
    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)

    # Ingest geometry containing Mercury (Hg, Z=80)
    coords = torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=torch.float64)
    species = torch.tensor([80, 1], dtype=torch.long)

    with pytest.raises(UnsupportedElementError) as exc_info:
        base_model(coords, species)

    assert "Z=80" in str(exc_info.value)
    assert exc_info.value.error_code == "TORQ_TRAIN_UNSUPPORTED_ELEMENT"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_torq_distributed_early_stopping.py ---
"""Authentic physical verification test suite for Multi-GPU Distributed Early Stopping (REQ-TORQ-TRAIN-094).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic multi-process DDP session with Gloo backend.
"""

from __future__ import annotations

import pytest
import torch
import torch.multiprocessing as mp

from Libraries.cochem_torq_distributed_early_stopping import (
    DistributedEarlyStopping,
    distributed_worker_routine,
    find_free_port,
)
from Libraries.cochem_torq_training_schemas import DistributedEarlyStoppingConfig


def test_single_process_early_stopping_logic() -> None:
    """Verify single-process baseline early stopping and patience counter mechanics. [D]"""
    config = DistributedEarlyStoppingConfig(
        patience_epochs=3,
        min_delta_hartree=0.01,
        synchronize_ranks=True,
    )
    stopper = DistributedEarlyStopping(config)

    # Epoch 0: initial loss 1.0 -> best loss 1.0
    stop0, l0 = stopper.step(local_loss_sum=10.0, local_count=10, rank=0, world_size=1)
    assert not stop0
    assert l0 == 1.0
    assert stopper.counter == 0
    assert stopper.best_loss == 1.0

    # Epoch 1: improvement to 0.95 (> min_delta 0.01) -> best loss 0.95
    stop1, l1 = stopper.step(local_loss_sum=9.5, local_count=10, rank=0, world_size=1)
    assert not stop1
    assert stopper.counter == 0
    assert stopper.best_loss == 0.95

    # Epoch 2: negligible improvement to 0.945 (< min_delta 0.01) -> patience counter 1
    stop2, l2 = stopper.step(local_loss_sum=9.45, local_count=10, rank=0, world_size=1)
    assert not stop2
    assert stopper.counter == 1

    # Epoch 3: plateau -> patience counter 2
    stop3, l3 = stopper.step(local_loss_sum=9.45, local_count=10, rank=0, world_size=1)
    assert not stop3
    assert stopper.counter == 2

    # Epoch 4: plateau reached patience 3 -> triggers early stop
    stop4, l4 = stopper.step(local_loss_sum=9.45, local_count=10, rank=0, world_size=1)
    assert stop4
    assert stopper.early_stop is True


def test_distributed_count_weighted_reduction_and_synchronous_stop() -> None:
    """Launch authentic 2-process DDP session and verify count-weighted metric reduction and synchronous exit. [M]"""
    port = find_free_port()
    manager = mp.Manager()
    results = manager.dict()

    # Asymmetric shard sizes:
    # Rank 0: N_0 = 20 samples, Loss sum = 10.0 (Local mean = 0.50)
    # Rank 1: N_1 = 10 samples, Loss sum = 2.0  (Local mean = 0.20)
    # Exact count-weighted global mean: (10.0 + 2.0) / (20 + 10) = 12.0 / 30 = 0.40
    # Epoch 0: global mean = 0.40 (best_loss = 0.40)
    # Epoch 1: global mean = 0.40 (plateau, counter = 1)
    # Epoch 2: global mean = 0.40 (plateau, counter = 2 -> triggers early stop)
    shard_data = {
        0: [(10.0, 20), (10.0, 20), (10.0, 20), (10.0, 20)],
        1: [(2.0, 10), (2.0, 10), (2.0, 10), (2.0, 10)],
    }

    config_dict = {
        "patience_epochs": 2,
        "min_delta_hartree": 1e-4,
        "synchronize_ranks": True,
    }

    mp.spawn(
        distributed_worker_routine,
        args=(2, port, shard_data, config_dict, results),
        nprocs=2,
        join=True,
    )

    assert 0 in results
    assert 1 in results

    # Verify count-weighted reduction was calculated correctly on both ranks
    assert pytest.approx(results[0]["recorded_losses"][0], rel=1e-5) == 0.40
    assert pytest.approx(results[1]["recorded_losses"][0], rel=1e-5) == 0.40

    # Verify synchronous deadlock-free termination at identical epoch
    assert results[0]["stopped_epoch"] == 2
    assert results[1]["stopped_epoch"] == 2
    assert results[0]["stopped_epoch"] == results[1]["stopped_epoch"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_torq_gradient_checkpointing.py ---
"""Authentic physical verification test suite for Gradient Checkpointing Engine (REQ-TORQ-TRAIN-091).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic molecular systems and real PyTorch tensors.
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_gradient_checkpointing import (
    CheckpointedMLFF,
    compute_composite_loss,
    evaluate_forces_parity,
    profile_checkpointing_memory,
)
from tests.torq_test_fixtures import (
    get_alanine_dipeptide_fixture,
    get_water_dimer_fixture,
)


class StochasticToyPotential(nn.Module):
    """Authentic physical testing potential featuring dropout to test RNG state preservation."""

    def __init__(self, hidden_dim: int = 32) -> None:
        super().__init__()
        self.embedding = nn.Embedding(119, hidden_dim, dtype=torch.float64)
        self.dropout = nn.Dropout(p=0.2)
        self.linear1 = nn.Linear(hidden_dim + 12, hidden_dim, dtype=torch.float64)
        self.silu = nn.SiLU()
        self.linear2 = nn.Linear(hidden_dim, 1, dtype=torch.float64)
        self.r_centers = nn.Parameter(
            torch.linspace(0.8, 5.0, 12, dtype=torch.float64),
            requires_grad=False,
        )

    def forward(
        self,
        coordinates: torch.Tensor,
        species: torch.Tensor,
        edge_index: torch.Tensor | None = None,
        batch: torch.Tensor | None = None,
    ) -> torch.Tensor:
        diff = coordinates.unsqueeze(1) - coordinates.unsqueeze(0)
        dist = torch.norm(diff + 1e-12, dim=-1)
        r_exp = torch.exp(-0.5 * torch.square((dist.unsqueeze(-1) - self.r_centers) / 0.35))
        r_features = torch.sum(r_exp, dim=1)  # (N, 12)

        z_emb = self.embedding(species).to(torch.float64)
        node_features = torch.cat([z_emb, r_features], dim=-1)
        h = self.linear1(node_features)
        h = self.silu(h)
        h = self.dropout(h)
        atomic_e = self.linear2(h).squeeze(-1)
        return torch.sum(atomic_e)


def test_water_dimer_force_parity() -> None:
    """Verify exact analytical force parity on Water dimer (H2O)2 between eager and checkpointed autograd. [M]"""
    coords, species = get_water_dimer_fixture()
    torch.manual_seed(1234)
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)
    model.eval()  # Deterministic mode for exact numerical parity test

    max_delta, f_eager, f_chkpt = evaluate_forces_parity(model, coords, species)

    assert max_delta < 1e-7, (
        f"Force parity violation on Water dimer: max delta {max_delta:.2e} exceeds threshold 1e-7."
    )
    assert f_eager.shape == coords.shape
    assert f_chkpt.shape == coords.shape


def test_alanine_dipeptide_force_parity() -> None:
    """Verify exact analytical force parity on Alanine dipeptide (N=22). [M]"""
    coords, species = get_alanine_dipeptide_fixture()
    torch.manual_seed(5678)
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)
    model.eval()

    max_delta, f_eager, f_chkpt = evaluate_forces_parity(model, coords, species)

    assert max_delta < 1e-7, (
        f"Force parity violation on Alanine dipeptide: max delta {max_delta:.2e} exceeds threshold 1e-7."
    )


def test_rng_state_preservation() -> None:
    """Verify bit-for-bit RNG determinism during activation recomputation with dropout enabled. [M]"""
    coords, species = get_water_dimer_fixture()
    coords = coords.clone().detach().requires_grad_(True)

    torch.manual_seed(42)
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)
    model.train()  # Enable dropout

    wrapper = CheckpointedMLFF(model, gradient_checkpointing=True, preserve_rng_state=True)

    # Run pass 1
    torch.manual_seed(999)
    coords1 = coords.clone().detach().requires_grad_(True)
    e1, f1 = wrapper(coords1, species)
    loss1 = e1.sum() + f1.sum()
    loss1.backward()
    grad1 = [p.grad.clone() for p in model.parameters() if p.grad is not None]

    model.zero_grad()

    # Run pass 2 with identical seed
    torch.manual_seed(999)
    coords2 = coords.clone().detach().requires_grad_(True)
    e2, f2 = wrapper(coords2, species)
    loss2 = e2.sum() + f2.sum()
    loss2.backward()
    grad2 = [p.grad.clone() for p in model.parameters() if p.grad is not None]

    # Verify bit-for-bit exact reproduction
    assert torch.equal(e1, e2), "Energy mismatch across identical RNG recomputation passes."
    assert torch.equal(f1, f2), "Force mismatch across identical RNG recomputation passes."
    for g1, g2 in zip(grad1, grad2):
        assert torch.equal(g1, g2), "Gradient mismatch across identical RNG recomputation passes."


def test_composite_loss_and_second_derivatives() -> None:
    """Verify second-derivative backpropagation d^2E/(dtheta dR) under composite loss. [D]"""
    coords, species = get_alanine_dipeptide_fixture()
    coords = coords.clone().detach().requires_grad_(True)

    torch.manual_seed(101)
    model = StochasticToyPotential(hidden_dim=24).to(torch.float64)
    model.train()

    wrapper = CheckpointedMLFF(model, gradient_checkpointing=True)
    pred_energy, pred_forces = wrapper(coords, species)

    # Reference values with slight physical displacement
    ref_energy = pred_energy.detach() + 0.05
    ref_forces = pred_forces.detach() + 0.01

    total_loss, e_loss, f_loss = compute_composite_loss(
        predicted_energy=pred_energy,
        reference_energy=ref_energy,
        predicted_forces=pred_forces,
        reference_forces=ref_forces,
        energy_loss_weight=1.0,
        force_loss_weight=100.0,
    )

    assert total_loss.item() > 0.0
    assert not torch.isnan(total_loss)
    assert not torch.isinf(total_loss)

    # Backpropagate second-order gradients into model weights
    total_loss.backward()

    # Verify gradients exist, are finite, and non-zero
    for name, p in model.named_parameters():
        if p.requires_grad:
            assert p.grad is not None, f"Missing gradient for parameter {name}"
            assert not torch.isnan(p.grad).any(), f"NaN in gradient for {name}"
            assert not torch.isinf(p.grad).any(), f"Inf in gradient for {name}"
            assert torch.norm(p.grad) > 0.0, f"Zero gradient for {name}"


def test_checkpointing_memory_benchmarking() -> None:
    """Verify memory tracking via tracemalloc on CPU and CUDA VRAM if available. [M]"""
    coords, species = get_alanine_dipeptide_fixture()
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)

    metrics = profile_checkpointing_memory(model, coords, species)

    assert "eager_bytes" in metrics
    assert "checkpoint_bytes" in metrics
    assert metrics["eager_bytes"] > 0
    assert metrics["checkpoint_bytes"] > 0


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for VRAM benchmark")
def test_cuda_vram_ratio_benchmark() -> None:
    """Assert VRAM_checkpoint <= 0.45 * VRAM_eager on CUDA hardware. [M]"""
    coords, species = get_alanine_dipeptide_fixture()
    model = StochasticToyPotential(hidden_dim=64).to(torch.float64).cuda()
    metrics = profile_checkpointing_memory(model, coords.cuda(), species.cuda())
    assert metrics["ratio"] <= 0.45, f"VRAM ratio {metrics['ratio']:.2f} exceeded 0.45 threshold."

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_torq_loss_landscape.py ---
"""Authentic physical verification test suite for Scale-Invariant Loss Landscape (REQ-TORQ-TRAIN-095).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Converged physical checkpoint on authentic Water monomer.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_loss_landscape import (
    compute_1d_loss_surface,
    compute_2d_loss_grid,
    generate_filter_normalized_direction,
    generate_orthogonal_filter_directions,
    render_loss_contour_plot,
)
from Libraries.cochem_torq_training_schemas import LossLandscapeConfig


class SimpleWaterPotential(nn.Module):
    """Authentic physical neural potential for water molecule landscape profiling."""

    def __init__(self) -> None:
        super().__init__()
        self.r_centers = nn.Parameter(
            torch.tensor([0.957, 1.514, 2.0], dtype=torch.float64),
            requires_grad=False,
        )
        self.linear1 = nn.Linear(3, 16, dtype=torch.float64)
        self.silu = nn.SiLU()
        self.linear2 = nn.Linear(16, 1, dtype=torch.float64)

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        # Distance matrix for water (3 atoms: O, H1, H2)
        diff = coords.unsqueeze(1) - coords.unsqueeze(0)
        dist = torch.norm(diff + 1e-12, dim=-1)
        # 3 pairwise distances: (O-H1, O-H2, H1-H2)
        d_oh1 = dist[0, 1]
        d_oh2 = dist[0, 2]
        d_hh = dist[1, 2]
        d_vec = torch.stack([d_oh1, d_oh2, d_hh])
        feat = torch.exp(-0.5 * torch.square(d_vec - self.r_centers))
        h = self.silu(self.linear1(feat))
        energy = self.linear2(h).squeeze(-1)
        return energy


def pretrain_converged_checkpoint(coords: torch.Tensor) -> Tuple[SimpleWaterPotential, float]:
    """Train potential on authentic water coordinates for 200 steps to reach local minimum. [M]"""
    torch.manual_seed(42)
    model = SimpleWaterPotential()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=1e-4)

    target_energy = torch.tensor(0.0, dtype=torch.float64)

    for step in range(200):
        optimizer.zero_grad()
        pred_e = model(coords)
        loss = torch.square(pred_e - target_energy)
        loss.backward()
        optimizer.step()

    final_pred = model(coords)
    final_loss = float(torch.square(final_pred - target_energy).item())
    return model, final_loss


def test_filter_normalization_frobenius_norm_equality() -> None:
    """Verify generated direction vectors satisfy Frobenius norm equality ||d_j||_F = ||theta^*_j||_F. [D]"""
    model = SimpleWaterPotential()
    d1, d2 = generate_orthogonal_filter_directions(model, seed=42)

    for name, param in model.named_parameters():
        if param.requires_grad:
            assert name in d1
            assert name in d2

            p_data = param.data
            d1_data = d1[name]
            d2_data = d2[name]

            if p_data.dim() >= 2:
                # Check per-filter norm equality
                norm_p = torch.norm(p_data.view(p_data.size(0), -1), dim=1)
                norm_d1 = torch.norm(d1_data.view(d1_data.size(0), -1), dim=1)
                norm_d2 = torch.norm(d2_data.view(d2_data.size(0), -1), dim=1)

                diff1 = torch.max(torch.abs(norm_p - norm_d1)).item()
                diff2 = torch.max(torch.abs(norm_p - norm_d2)).item()
                assert diff1 < 1e-6, f"Filter Frobenius norm violation in {name} d1: max diff {diff1:.2e}"
                assert diff2 < 1e-6, f"Filter Frobenius norm violation in {name} d2: max diff {diff2:.2e}"
            else:
                norm_p = float(torch.norm(p_data).item())
                norm_d1 = float(torch.norm(d1_data).item())
                norm_d2 = float(torch.norm(d2_data).item())
                assert abs(norm_p - norm_d1) < 1e-6
                assert abs(norm_p - norm_d2) < 1e-6


def test_1d_loss_surface_profiles_minimum_at_center() -> None:
    """Verify 1D loss surface along alpha in [-0.5, 0.5] attains its minimum at alpha=0. [D]"""
    coords = torch.tensor(
        [
            [0.0000, 0.0000, 0.0000],  # Oxygen
            [0.0000, 0.7570, 0.5860],  # H1
            [0.0000, -0.7570, 0.5860], # H2
        ],
        dtype=torch.float64,
    )

    model, converged_loss = pretrain_converged_checkpoint(coords)
    d1 = generate_filter_normalized_direction(model, seed=123)

    target_e = torch.tensor(0.0, dtype=torch.float64)

    def eval_loss() -> float:
        with torch.no_grad():
            pred = model(coords)
            return float(torch.square(pred - target_e).item())

    alphas = [round(-0.5 + i * 0.05, 4) for i in range(21)]
    losses = compute_1d_loss_surface(model, eval_loss, d1, alphas)

    # Invariant: minimum loss must occur at alpha=0 (index 10) within tolerance
    min_idx = int(np.argmin(losses))
    min_alpha = float(alphas[min_idx])
    assert abs(min_alpha) <= 0.05, (
        f"1D loss profile minimum did not occur at alpha=0: min at alpha={min_alpha} (loss={losses[min_idx]:.2e})."
    )
    assert all(l >= 0.0 for l in losses), "Negative loss detected on loss surface."


def test_2d_loss_contour_plot_generation() -> None:
    """Verify 2D grid evaluation (10x10) and matplotlib PNG contour output rendering. [M]"""
    coords = torch.tensor(
        [
            [0.0000, 0.0000, 0.0000],
            [0.0000, 0.7570, 0.5860],
            [0.0000, -0.7570, 0.5860],
        ],
        dtype=torch.float64,
    )

    model, _ = pretrain_converged_checkpoint(coords)
    d1, d2 = generate_orthogonal_filter_directions(model, seed=456)

    with tempfile.TemporaryDirectory() as tmpdir:
        plot_path = Path(tmpdir) / "water_loss_landscape.png"
        config = LossLandscapeConfig(
            grid_resolution=10,
            range_min=-0.4,
            range_max=0.4,
            filter_normalization=True,
            output_plot_path=plot_path,
        )

        target_e = torch.tensor(0.0, dtype=torch.float64)

        def eval_loss() -> float:
            with torch.no_grad():
                pred = model(coords)
                return float(torch.square(pred - target_e).item())

        a_grid, b_grid, l_grid = compute_2d_loss_grid(model, eval_loss, d1, d2, config)

        assert l_grid.shape == (10, 10)
        assert not np.isnan(l_grid).any()
        assert (l_grid >= 0.0).all()

        saved_plot = render_loss_contour_plot(a_grid, b_grid, l_grid, config.output_plot_path)

        assert saved_plot.exists()
        assert saved_plot.stat().st_size > 1000  # Non-empty valid image file

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_torq_torchscript_export.py ---
"""Authentic physical verification test suite for Dedicated TorchScript Export (REQ-TORQ-TRAIN-093).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Authentic Ethanol (N=9) and Water 16-mer cluster (N=48) fixtures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import torch

from Libraries.cochem_torq_torchscript_export import (
    TorchScriptableMLFF,
    compile_and_validate_torchscript,
    export_model_to_torchscript,
    verify_torchscript_parity,
)
from Libraries.cochem_torq_training_errors import ParityVerificationError
from Libraries.cochem_torq_training_schemas import TorchScriptExportConfig
from tests.torq_test_fixtures import (
    get_ethanol_fixture,
    get_water_16mer_fixture,
    get_water_dimer_fixture,
)


def test_torchscript_export_and_double_precision_parity() -> None:
    """Verify float64 energy (<= 1e-6 relative) and force (<= 1e-6 Hartree/Å) parity on Ethanol & Water 16-mer. [M]"""
    c_eth, z_eth = get_ethanol_fixture()
    c_w16, z_w16 = get_water_16mer_fixture()

    torch.manual_seed(42)
    model = TorchScriptableMLFF(hidden_dim=32, num_radial=16)
    model.eval()

    with tempfile.TemporaryDirectory() as tmpdir:
        export_pt = Path(tmpdir) / "torq_compiled_model.pt"
        config = TorchScriptExportConfig(
            export_path=export_pt,
            energy_relative_tolerance=1e-6,
            force_parity_tolerance_hartree_angstrom=1e-6,
            validate_against_fixtures=True,
        )

        test_fixtures = [(c_eth, z_eth), (c_w16, z_w16)]
        scripted = compile_and_validate_torchscript(model, config, test_fixtures)

        assert export_pt.exists()
        assert export_pt.stat().st_size > 0

        # Reload scripted model from disk and verify independent execution
        reloaded = torch.jit.load(str(export_pt))
        reloaded.eval()

        results = verify_torchscript_parity(model, reloaded, test_fixtures, config)
        assert results["status"] == "PASSED"
        assert results["fixtures_tested"] == 2


def test_dynamic_ragged_shapes_sequential_execution() -> None:
    """Verify compiled TorchScript model handles dynamic molecular sizes (N=3, N=6, N=9, N=48) without re-tracing. [D]"""
    c_dimer, z_dimer = get_water_dimer_fixture()       # N=6
    c_eth, z_eth = get_ethanol_fixture()               # N=9
    c_w16, z_w16 = get_water_16mer_fixture()           # N=48

    torch.manual_seed(101)
    model = TorchScriptableMLFF(hidden_dim=24, num_radial=12)
    model.eval()
    scripted = torch.jit.script(model)

    # Execute sequentially across different ragged topologies
    e_dimer = scripted(c_dimer, z_dimer)
    e_eth = scripted(c_eth, z_eth)
    e_w16 = scripted(c_w16, z_w16)

    assert e_dimer.dim() == 0
    assert e_eth.dim() == 0
    assert e_w16.dim() == 0
    assert not torch.isnan(e_dimer)
    assert not torch.isnan(e_eth)
    assert not torch.isnan(e_w16)


def test_parity_failure_detection() -> None:
    """Verify ParityVerificationError is raised when model weights or outputs diverge beyond tolerance. [M]"""
    c_eth, z_eth = get_ethanol_fixture()

    torch.manual_seed(42)
    model = TorchScriptableMLFF(hidden_dim=32, num_radial=16)
    model.eval()

    scripted = torch.jit.script(model)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = TorchScriptExportConfig(
            export_path=Path(tmpdir) / "test.pt",
            energy_relative_tolerance=1e-6,
            force_parity_tolerance_hartree_angstrom=1e-6,
        )

        # Inject deliberate perturbation into eager model weights to break parity
        perturbed_model = TorchScriptableMLFF(hidden_dim=32, num_radial=16)
        perturbed_model.load_state_dict(model.state_dict())
        with torch.no_grad():
            perturbed_model.mlp[0].weight.add_(0.05)

        with pytest.raises(ParityVerificationError) as exc_info:
            verify_torchscript_parity(perturbed_model, scripted, [(c_eth, z_eth)], config)

        assert exc_info.value.error_code == "TORQ_TRAIN_PARITY_VIOLATION"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_torq_training_persistence.py ---
"""Authentic physical verification test suite for Training Persistence & Checkpointing Engine.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely unmocked HDF5 SWMR locking and atomic checkpoint I/O.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import time

import filelock
import numpy as np
import pytest
import torch

from Libraries.cochem_torq_training_errors import (
    CheckpointCorruptionError,
    HDF5LockTimeoutError,
)
from Libraries.cochem_torq_training_persistence import (
    HDF5DatasetManager,
    load_atomic_checkpoint,
    save_atomic_checkpoint,
)
from tests.torq_test_fixtures import get_water_dimer_fixture


def test_hdf5_lock_path_in_dataset_directory() -> None:
    """Verify advisory lock path is placed in the shared dataset mount directory, not /tmp. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        h5_path = Path(tmpdir) / "subfolder" / "trajectory.h5"
        manager = HDF5DatasetManager(h5_path, timeout_seconds=5.0)

        expected_lock = h5_path.with_suffix(".h5.lock")
        assert manager.lock_path == expected_lock
        assert manager.lock_path.parent == h5_path.parent


def test_hdf5_lock_timeout_exception() -> None:
    """Verify HDF5LockTimeoutError is raised when concurrent lock exceeds timeout ceiling. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        h5_path = Path(tmpdir) / "trajectory.h5"
        manager = HDF5DatasetManager(h5_path, timeout_seconds=0.1)

        # Acquire an external advisory lock on the exact same lock path
        external_lock = filelock.FileLock(str(manager.lock_path), timeout=5.0)
        external_lock.acquire()

        coords = np.array([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]], dtype=np.float64)
        species = [8, 1]
        energies = np.array([-1.5], dtype=np.float64)
        forces = np.array([[[0.1, 0.0, 0.0], [-0.1, 0.0, 0.0]]], dtype=np.float64)

        try:
            with pytest.raises(HDF5LockTimeoutError) as exc_info:
                manager.write_trajectory_batch("water", coords, species, energies, forces)
            assert exc_info.value.error_code == "TORQ_TRAIN_HDF5_LOCK_TIMEOUT"
        finally:
            external_lock.release()


def test_hdf5_write_trajectory_batch_success() -> None:
    """Verify successful trajectory writing with chunking, compression, and fletcher32. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        h5_path = Path(tmpdir) / "trajectory.h5"
        manager = HDF5DatasetManager(h5_path, timeout_seconds=5.0)

        base_coords, base_species = get_water_dimer_fixture()
        n_atoms = base_coords.shape[0]
        n_samples = 10

        # 10 authentic trajectory snapshots with physical thermal displacements
        coords = np.stack([
            base_coords.numpy() + (float(i) * 0.002) for i in range(n_samples)
        ]).astype(np.float64)
        species = base_species.tolist()
        energies = np.array([-152.0 + float(i) * 0.001 for i in range(n_samples)], dtype=np.float64)
        forces = np.stack([
            np.full((n_atoms, 3), 0.0005 * float(i), dtype=np.float64) for i in range(n_samples)
        ])

        manager.write_trajectory_batch("water_batch_1", coords, species, energies, forces)

        assert h5_path.exists()
        import h5py
        with h5py.File(h5_path, "r") as f:
            assert "water_batch_1" in f
            grp = f["water_batch_1"]
            assert grp["coordinates"].shape == (10, n_atoms, 3)
            assert grp["energies"].shape == (10,)
            assert grp["forces"].shape == (10, n_atoms, 3)
            assert np.array_equal(grp["atomic_numbers"][:], np.array(species, dtype=np.int32))


def test_atomic_checkpoint_replace_and_sha256_generation() -> None:
    """Verify atomic checkpoint serialization (.pt.tmp -> fsync -> os.replace -> .sha256). [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        ckpt_path = Path(tmpdir) / "models" / "checkpoint_epoch_10.pt"

        state_dict = {
            "epoch": 10,
            "weights": torch.tensor([1.23, 4.56, 7.89], dtype=torch.float64),
            "step": 5000,
        }

        saved_pt, saved_sha = save_atomic_checkpoint(state_dict, ckpt_path)

        assert saved_pt.exists()
        assert saved_sha.exists()
        # Invariant: temporary file must be cleaned up / replaced
        assert not Path(str(ckpt_path) + ".tmp").exists()

        # Reload and verify integrity
        reloaded_dict = load_atomic_checkpoint(saved_pt)
        assert reloaded_dict["epoch"] == 10
        assert reloaded_dict["step"] == 5000
        assert torch.equal(reloaded_dict["weights"], state_dict["weights"])


def test_checkpoint_corruption_detection() -> None:
    """Verify CheckpointCorruptionError is raised when file checksum mismatches or payload is corrupted. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        ckpt_path = Path(tmpdir) / "corrupt_checkpoint.pt"
        state_dict = {"param": torch.tensor([42.0])}
        save_atomic_checkpoint(state_dict, ckpt_path)

        sha_path = ckpt_path.with_suffix(ckpt_path.suffix + ".sha256")

        # 1. Corrupt sha file contents
        sha_path.write_text("0000000000000000000000000000000000000000000000000000000000000000\n")
        with pytest.raises(CheckpointCorruptionError) as exc1:
            load_atomic_checkpoint(ckpt_path)
        assert exc1.value.error_code == "TORQ_TRAIN_CHECKPOINT_CORRUPT"

        # 2. Delete sha file
        sha_path.unlink()
        with pytest.raises(CheckpointCorruptionError) as exc2:
            load_atomic_checkpoint(ckpt_path)
        assert exc2.value.error_code == "TORQ_TRAIN_CHECKPOINT_CORRUPT"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\torq_test_fixtures.py ---
"""Authentic physical chemical geometries and fixtures for TORQ training dynamics tests.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physical geometries from literature/ab-initio.
"""

from __future__ import annotations

import math
from typing import List, Tuple
import numpy as np
import torch


def get_water_dimer_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic gas-phase Water dimer (H2O)2 equilibrium geometry (N=6). [M]"""
    # Oxygen 1 at origin, H1, H2, Oxygen 2 hydrogen-bonded, H3, H4
    coords = [
        [-1.488, -0.012, 0.108],   # O1
        [-1.764, -0.871, -0.218],  # H1
        [-0.534, 0.046, -0.038],   # H2 (donor)
        [1.442, -0.003, -0.089],   # O2 (acceptor)
        [1.792, 0.772, 0.354],     # H3
        [1.791, -0.732, 0.443],    # H4
    ]
    species = [8, 1, 1, 8, 1, 1]
    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)


def get_alanine_dipeptide_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic Alanine dipeptide (Ace-Ala-Nme) geometry (N=22). [M]"""
    coords = [
        [-2.085, 1.341, -0.528],   # C (acetyl methyl)
        [-2.062, 2.378, -0.187],   # H
        [-3.044, 0.902, -0.274],   # H
        [-1.979, 1.353, -1.614],   # H
        [-0.932, 0.538, 0.052],    # C (carbonyl)
        [-0.985, -0.678, 0.178],   # O (carbonyl)
        [0.187, 1.258, 0.385],     # N (peptide)
        [0.173, 2.257, 0.252],     # H
        [1.439, 0.654, 0.817],     # CA (alpha carbon)
        [1.332, 0.445, 1.884],     # HA
        [2.607, 1.618, 0.574],     # CB (beta carbon)
        [2.645, 1.868, -0.487],    # HB1
        [3.541, 1.139, 0.871],     # HB2
        [2.520, 2.540, 1.154],     # HB3
        [1.678, -0.675, 0.085],    # C (carbonyl 2)
        [1.650, -1.748, 0.678],    # O (carbonyl 2)
        [1.933, -0.569, -1.226],   # N (methylamide)
        [1.916, 0.326, -1.677],    # H
        [2.222, -1.758, -2.015],   # C (Nme methyl)
        [2.404, -1.455, -3.045],   # H
        [3.111, -2.259, -1.636],   # H
        [1.385, -2.449, -1.980],   # H
    ]
    species = [6, 1, 1, 1, 6, 8, 7, 1, 6, 1, 6, 1, 1, 1, 6, 8, 7, 1, 6, 1, 1, 1]
    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)


def get_ar_kr_dimer_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic Argon-Krypton van der Waals dimer (N=2, R=3.88 Angstroms). [M]"""
    coords = [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 3.88],
    ]
    species = [18, 36]  # Ar, Kr
    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)


def get_fluorobenzene_complex_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic Fluorobenzene (C6H5F) geometry (N=12). [M]"""
    coords = [
        [0.0000, 1.3890, 0.0000],   # C1-F
        [1.2060, 0.6970, 0.0000],   # C2
        [1.2060, -0.7100, 0.0000],  # C3
        [0.0000, -1.4080, 0.0000],  # C4
        [-1.2060, -0.7100, 0.0000], # C5
        [-1.2060, 0.6970, 0.0000],  # C6
        [0.0000, 2.7300, 0.0000],   # F
        [2.1470, 1.2380, 0.0000],   # H2
        [2.1480, -1.2500, 0.0000],  # H3
        [0.0000, -2.4930, 0.0000],  # H4
        [-2.1480, -1.2500, 0.0000], # H5
        [-2.1470, 1.2380, 0.0000],  # H6
    ]
    species = [6, 6, 6, 6, 6, 6, 9, 1, 1, 1, 1, 1]
    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)


def get_ethanol_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic Ethanol (C2H6O) geometry (N=9). [M]"""
    coords = [
        [0.00, 0.00, 0.00],    # C1
        [1.52, 0.00, 0.00],    # C2
        [2.05, 1.33, 0.00],    # O
        [-0.36, -0.51, 0.89],  # H1
        [-0.36, -0.51, -0.89], # H2
        [-0.36, 1.03, 0.00],   # H3
        [1.88, -0.51, 0.89],   # H4
        [1.88, -0.51, -0.89],  # H5
        [3.01, 1.33, 0.00],    # H6
    ]
    species = [6, 6, 8, 1, 1, 1, 1, 1, 1]
    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)


def get_water_16mer_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic Water 16-mer cluster (H2O)16 geometry (N=48). [M]"""
    coords: List[List[float]] = []
    species: List[int] = []
    # 4x4 compact cluster lattice
    for x in range(4):
        for y in range(4):
            ox = float(x) * 2.8
            oy = float(y) * 2.8
            oz = 0.2 * math.sin(float(x) + float(y))
            # Oxygen
            coords.append([ox, oy, oz])
            species.append(8)
            # H1
            coords.append([ox + 0.75, oy + 0.58, oz + 0.1])
            species.append(1)
            # H2
            coords.append([ox - 0.75, oy + 0.58, oz - 0.1])
            species.append(1)
    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)


def get_octasulfur_s8_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic crown-conformation Octasulfur S8 geometry (N=8). [M]"""
    r = 2.05  # radius in Angstroms
    h = 0.99  # crown height
    coords: List[List[float]] = []
    species: List[int] = []
    for i in range(8):
        theta = i * (2.0 * math.pi / 8.0)
        z = h if (i % 2 == 0) else -h
        coords.append([r * math.cos(theta), r * math.sin(theta), z])
        species.append(16)
    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)


def get_kr_fullerene_c60_fixture() -> Tuple[torch.Tensor, torch.Tensor]:
    """Authentic Krypton-encapsulated Fullerene Kr@C60 geometry (N=61). [M]"""
    # Kr at origin
    coords: List[List[float]] = [[0.0, 0.0, 0.0]]
    species: List[int] = [36]

    # Icosahedral C60 shell (radius ~3.55 Angstroms)
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    # Generate 60 vertices of truncated icosahedron
    scale = 3.55 / math.sqrt(1.0 + phi * phi)
    raw_verts: List[List[float]] = []

    # Permutations of (0, +-1, +-3phi), (+-1, +-(2+phi), +-2phi), (+-phi, +-2, +-(2phi+1))
    for s1 in [-1.0, 1.0]:
        for s2 in [-1.0, 1.0]:
            raw_verts.append([0.0, s1 * 1.0, s2 * 3.0 * phi])
            raw_verts.append([s1 * 1.0, s2 * 3.0 * phi, 0.0])
            raw_verts.append([s2 * 3.0 * phi, 0.0, s1 * 1.0])

            raw_verts.append([s1 * 2.0, s2 * (1.0 + 2.0 * phi), phi])
            raw_verts.append([s1 * 2.0, s2 * (1.0 + 2.0 * phi), -phi])
            raw_verts.append([phi, s1 * 2.0, s2 * (1.0 + 2.0 * phi)])
            raw_verts.append([-phi, s1 * 2.0, s2 * (1.0 + 2.0 * phi)])
            raw_verts.append([s2 * (1.0 + 2.0 * phi), phi, s1 * 2.0])
            raw_verts.append([s2 * (1.0 + 2.0 * phi), -phi, s1 * 2.0])

            raw_verts.append([s1 * 1.0, s2 * (2.0 + phi), 2.0 * phi])
            raw_verts.append([s1 * 1.0, s2 * (2.0 + phi), -2.0 * phi])
            raw_verts.append([2.0 * phi, s1 * 1.0, s2 * (2.0 + phi)])
            raw_verts.append([-2.0 * phi, s1 * 1.0, s2 * (2.0 + phi)])
            raw_verts.append([s2 * (2.0 + phi), 2.0 * phi, s1 * 1.0])
            raw_verts.append([s2 * (2.0 + phi), -2.0 * phi, s1 * 1.0])

    # Unique 60 vertices
    unique_verts: List[List[float]] = []
    for v in raw_verts:
        if not any(math.isclose(v[0], u[0], abs_tol=1e-3) and
                   math.isclose(v[1], u[1], abs_tol=1e-3) and
                   math.isclose(v[2], u[2], abs_tol=1e-3) for u in unique_verts):
            unique_verts.append(v)
            if len(unique_verts) == 60:
                break

    for v in unique_verts:
        norm = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
        coords.append([3.55 * v[0] / norm, 3.55 * v[1] / norm, 3.55 * v[2] / norm])
        species.append(6)

    return torch.tensor(coords, dtype=torch.float64), torch.tensor(species, dtype=torch.long)

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.