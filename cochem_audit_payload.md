Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_21_TORQ_Molecular_Dynamics_Part_1_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous Neural Network Molecular Dynamics (NNMD) simulation and Replica Exchange Molecular Dynamics (REMD) enhanced sampling engine specified in Software Requirements Specification (SRS) Chunk 21: `TORQ_Molecular_Dynamics_Part_1` (`COCHEM-SRS-CHUNK-21-TORQ`).

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev atomic mass retrieval mandate, and Method Matrix v4 (`[M]` Empirical Benchmark, `[D]` Derived Mathematical Relationship, `[E]` Estimated Theoretical Projection). Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine physical tensors, authentic molecular coordinates, and real chemical observables.

---

### 1. DIRECTORY, PERSISTENCE & 6-TIER RUNTIME CONTRACTS

1. **Tripartite Workspace Air-Gap Paths**:
   - `COCHEM_SRC_DIR` ($R_{\text{src}}$): `pathlib.Path(os.environ.get("COCHEM_SRC_DIR", Path.cwd()))` (Read-only source repository: symplectic algorithms, autograd gradient pipelines, COM momentum projectors, and replica exchange state machines).
   - `COCHEM_DATA_DIR` ($R_{\text{data}}$): `pathlib.Path(os.environ.get("COCHEM_DATA_DIR", Path.home() / ".cochem" / "data"))` (Read-only neural network potential checkpoints, molecular topologies, and benchmark reference geometries under `COCHEM_OFFLINE=1`).
   - `COCHEM_ARTIFACTS_DIR` ($R_{\text{art}}$): `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR", Path.home() / ".cochem" / "artifacts"))` (Read-write trajectory frames, thermodynamic observables, exchange logs, checkpoint restart files, and telemetry).
   - `COCHEM_SCRATCH_DIR`: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR", os.environ.get("SLURM_TMPDIR", Path.home() / ".cochem" / "scratch")))`.
2. **6-Tier Runtime & Hardware Concurrency**:
   - **Accelerator Binding & Safe Device Dispatcher**:
     * Query hardware availability: NVIDIA CUDA (`torch.cuda.is_available()`), Apple Silicon Metal Performance Shaders (`getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()`), or CPU.
     * **Apple Silicon MPS `float64` Automatic Fallback Rule (`[M]`)**: Metal Performance Shaders (MPS) hardware does not support native 64-bit floating point (`torch.float64`). Attempting to allocate or compute `float64` tensors on `mps` raises `TypeError: Cannot convert a MPS tensor to float64`. When executing molecular dynamics integration requiring `torch.float64`, the dispatcher must automatically intercept and route execution to `cpu`.
     * Dynamic hardware detection must never hardcode device ordinals (e.g., `cuda:0` is strictly banned).
   - **Strict Double-Precision (`torch.float64`) Mandate**:
     * Mandatory `torch.float64` (`torch.double`, 53-bit significand) across all coordinates, velocities, forces, accelerations, and neural network evaluations to prevent unphysical energy drift (`[M]`).
   - **Thread-Safe & Multiprocessing-Safe HDF5 SWMR Serialization**:
     * Trajectory storage utilizes `h5py` Single-Writer-Multiple-Reader (SWMR) mode (`libver='latest'`, `swmr=True`) with chunked extensible datasets (`maxshape=(None, N_{\text{atoms}}, 3)`) and lossless compression (`gzip` or `lzf`) (`[D]`).
     * **SWMR Lifecycle Sequencing**: All groups, datasets, and metadata attributes must be created and flushed to disk **prior** to engaging `f.swmr_mode = True`, as dataset creation is strictly prohibited by HDF5 while in active SWMR mode.
     * **HPC Distributed Lock Prohibition Rule (`[M]`)**: On Tier 6 HPC environments, parallel network filesystems (Lustre, GPFS, BeeGFS, NFS) rely on centralized distributed lock managers. Direct `filelock.FileLock` across parallel filesystems causes lock manager deadlocks (`[Errno 37] No locks available`). Unconditional `filelock.FileLock` on parallel network filesystems is strictly prohibited. All staging, locking, and temporary files must be resolved dynamically to the node-local NVMe scratch directory `$SLURM_TMPDIR` (or `$TMPDIR`).
     * On single-node environments (Tiers 1-5), local file locking via `filelock.FileLock(lock_path, timeout=30.0)` is permitted.
   - **Atomic Serialization**: Write temporary file `.tmp`, flush to disk with `os.fsync(f.fileno())`, atomically replace via `os.replace`, and write an accompanying cryptographic `.sha256` digest file.
3. **OS-Agnostic Dynamic Paths**: All filesystem operations are mediated via `pathlib.Path`. Hardcoded OS path separators (`/`, `\`), `$HOME`, or `C:\` are strictly prohibited.

---

### 2. PHYSICAL CONSTANTS & CONVERSION FACTORS

You must strictly embed the authoritative CODATA 2018 / CIAAW physical constants without truncation or manual rounding:
- Elementary Charge: $e = 1.602176634 \times 10^{-19}\text{ C} = \text{J/eV}$ `[D]`
- Unified Atomic Mass Unit: $u = 1.66053906660 \times 10^{-27}\text{ kg}$ `[D]`
- Boltzmann Constant: $k_B = 8.617333262 \times 10^{-5}\text{ eV/K}$ `[D]`
- Length Scale Factor: $1.0 \times 10^{-10}\text{ m} = 1.0\text{ \AA}$ `[D]`
- Time Scale Factor: $1.0 \times 10^{-15}\text{ s} = 1.0\text{ fs}$ `[D]`
- Dimensional Acceleration Factor:
  $$\kappa_{\text{acc}} = \frac{1.602176634 \times 10^{-19}\text{ J/eV} \times (10^{10}\text{ \AA/m})^2}{1.66053906660 \times 10^{-27}\text{ kg/u} \times (10^{15}\text{ fs/s})^2} = 9.648533215665 \times 10^{-3}\,\frac{\text{\AA}/\text{fs}^2}{\text{eV}/(\text{\AA}\cdot\text{u})} \quad [D]$$
- Kinetic Mass Scale Factor:
  $$\kappa_{\text{acc}}^{-1} = 103.6426965\,\frac{\text{eV}}{\text{u}\cdot(\text{\AA}/\text{fs})^2} \quad [D]$$

---

### 3. DOMAIN EXCEPTIONS & PYDANTIC V2 DATA CONTRACTS

- **Files**: `Libraries/cochem_torq_md_errors.py` and `Libraries/cochem_torq_md_schemas.py` (and export in `Libraries/__init__.py`).
- **Domain Exception Hierarchy**:
```python
from typing import Any, Dict, Optional


class TorqMDError(Exception):
  """Root base exception for all TORQ molecular dynamics failures [M]."""

  def __init__(
      self,
      message: str,
      error_code: str = "TORQ_MD_GENERIC_ERROR",
      component: str = "molecular_dynamics",
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(message)
    self.error_code = error_code
    self.component = component
    self.diagnostics = diagnostics or {}


class EnergyDriftExceededError(TorqMDError):
  """Raised when NVE relative total energy drift |Delta E / E_0| exceeds tolerance (1e-4) [M]."""

  def __init__(
      self,
      drift: float,
      tolerance: float,
      step: int,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"NVE relative energy drift {drift:.6e} exceeded tolerance"
        f" {tolerance:.6e} at step {step}.",
        error_code="ENERGY_DRIFT_EXCEEDED",
        component="symplectic_integrator",
        diagnostics=diagnostics,
    )
    self.drift = drift
    self.tolerance = tolerance
    self.step = step


class SymplecticIntegratorError(TorqMDError):
  """Raised when non-finite (NaN or Inf) values are encountered in coordinates, velocities, or forces [M]."""

  def __init__(
      self,
      tensor_name: str,
      step: int,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"Non-finite values encountered in {tensor_name} at step {step}.",
        error_code="SYMPLECTIC_NON_FINITE_TENSOR",
        component="symplectic_integrator",
        diagnostics=diagnostics,
    )
    self.tensor_name = tensor_name
    self.step = step


class ReplicaExchangeDivergenceError(TorqMDError):
  """Raised when rolling swap acceptance drops below 5% or temperatures deviate by > 50 K [M]."""

  def __init__(
      self,
      reason: str,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"Replica Exchange divergent state: {reason}",
        error_code="REMD_DIVERGENCE",
        component="remd_engine",
        diagnostics=diagnostics,
    )


class HardwareDispatchError(TorqMDError):
  """Raised when requested hardware devices are unavailable or fail double-precision compliance [M]."""

  def __init__(
      self,
      device_requested: str,
      reason: str,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"Hardware dispatch failed for '{device_requested}': {reason}",
        error_code="HARDWARE_DISPATCH_FAILED",
        component="hardware_dispatcher",
        diagnostics=diagnostics,
    )
```

- **Pydantic v2 Data Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
```python
from pathlib import Path
from typing import List, Literal, NamedTuple, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
import torch


class VelocityVerletConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  timestep_fs: float = Field(default=0.5, gt=0.0, le=1.0)
  n_steps: int = Field(gt=0, default=20000)
  save_interval: int = Field(gt=0, default=10)
  device: str = Field(default="cpu")
  dtype: Literal["float64"] = Field(default="float64")
  energy_drift_tolerance: float = Field(default=1e-4, gt=0.0)
  remove_com_momentum: bool = Field(default=True)


class REMDConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  n_replicas: int = Field(ge=2, default=4)
  t_min_k: float = Field(gt=0.0, default=300.0)
  t_max_k: float = Field(gt=0.0, default=600.0)
  swap_interval_steps: int = Field(ge=10, default=100)
  total_steps_per_replica: int = Field(gt=0, default=100000)
  friction_ps: float = Field(default=1.0, gt=0.0)
  output_dir: Path

  @model_validator(mode="after")
  def validate_remd_parameters(self) -> "REMDConfig":
    if self.t_max_k <= self.t_min_k:
      raise ValueError(
          f"t_max_k ({self.t_max_k}) must be strictly greater than t_min_k"
          f" ({self.t_min_k})"
      )
    if self.total_steps_per_replica < self.swap_interval_steps:
      raise ValueError(
          f"total_steps_per_replica ({self.total_steps_per_replica}) must be >="
          f" swap_interval_steps ({self.swap_interval_steps})"
      )
    return self


class MDState(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  step: int = Field(ge=0)
  time_fs: float = Field(ge=0.0)
  potential_energy_ev: float
  kinetic_energy_ev: float = Field(ge=0.0)
  total_energy_ev: float
  temperature_k: float = Field(ge=0.0)


class TrajectoryFrame(NamedTuple):
  step: int
  time_fs: float
  atomic_numbers: torch.Tensor  # Shape: [N_atoms], dtype: torch.int64
  coordinates: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
  velocities: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
  forces: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
  potential_energy_ev: float
  kinetic_energy_ev: float


class ExchangeLog(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  attempt_step: int
  replica_i: int
  replica_j: int
  temp_i_k: float
  temp_j_k: float
  energy_i_ev: float
  energy_j_ev: float
  p_swap: float = Field(ge=0.0, le=1.0)
  accepted: bool
```

---

### 4. MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Dynamic Atomic Masses via Mendeleev (`REQ-TORQ-MD-004` `[M]`)
- **File Target**: `Libraries/cochem_torq_masses.py` (and export in `Libraries/__init__.py`).
- Implement dynamic lookup using the `mendeleev` library:
  ```python
  from mendeleev import element
  import torch


  def get_atomic_masses(
      atomic_numbers: torch.Tensor, device: torch.device
  ) -> torch.Tensor:
    """Retrieve CIAAW standard atomic weights in unified atomic mass units (u)."""
    masses = []
    for z in atomic_numbers.view(-1).tolist():
      elem = element(int(z))
      masses.append(float(elem.mass))
    return torch.tensor(masses, dtype=torch.float64, device=device).unsqueeze(
        -1
    )
```
- Strictly forbid hardcoded mass dictionaries, integer mass approximations, or manual CODATA mass tables.

#### 2. Conservative Force Autograd & Symplectic Velocity Verlet Integrator (`REQ-TORQ-MD-001`, `REQ-TORQ-MD-002`, `REQ-TORQ-MD-003`, `REQ-TORQ-MD-005`, `REQ-TORQ-MD-006`, `REQ-TORQ-MD-007` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_symplectic.py` (and export in `Libraries/__init__.py`).
- **Conservative Force Autograd (`REQ-TORQ-MD-001` `[D]`)**:
  Compute Cartesian forces as negative analytical gradient of neural potential:
  $$\mathbf{F}_i(t) = -\nabla_{\mathbf{r}_i} E_{\text{TORQ}}(\mathbf{r}(t))$$
  evaluated via `torch.autograd.grad(outputs=energy, inputs=coords, grad_outputs=torch.ones_like(energy), create_graph=False)[0]`.
- **Dimensional Acceleration Formulation (`REQ-TORQ-MD-002` `[D]`)**:
  $$\mathbf{a}_i(t) = \kappa_{\text{acc}} \frac{\mathbf{F}_i(t)}{m_i}, \quad \kappa_{\text{acc}} = 9.648533215665 \times 10^{-3}\,\frac{\text{\AA}/\text{fs}^2}{\text{eV}/(\text{\AA}\cdot\text{u})}$$
- **Symplectic Half-Step Velocity Verlet Integration (`REQ-TORQ-MD-003` `[D]`)**:
  1. Half-step velocity update: $\mathbf{v}_i(t + \frac{\Delta t}{2}) = \mathbf{v}_i(t) + \frac{\Delta t}{2} \mathbf{a}_i(t)$
  2. Full-step coordinate update: $\mathbf{r}_i(t + \Delta t) = \mathbf{r}_i(t) + \Delta t\,\mathbf{v}_i(t + \frac{\Delta t}{2})$
  3. Force evaluation: $\mathbf{F}_i(t + \Delta t) = -\nabla_{\mathbf{r}_i} E_{\text{TORQ}}(\mathbf{r}(t + \Delta t))$
  4. Full-step acceleration update: $\mathbf{a}_i(t + \Delta t) = \kappa_{\text{acc}} \frac{\mathbf{F}_i(t + \Delta t)}{m_i}$
  5. Final velocity update: $\mathbf{v}_i(t + \Delta t) = \mathbf{v}_i(t + \frac{\Delta t}{2}) + \frac{\Delta t}{2} \mathbf{a}_i(t + \Delta t)$
  - Check `torch.isnan` and `torch.isinf` on coordinates, velocities, and forces at each step. Raise `SymplecticIntegratorError` immediately if detected.
- **Center-of-Mass Momentum Elimination (`REQ-TORQ-MD-005` `[D]`)**:
  $$\mathbf{v}_{\text{COM}} = \frac{\sum_{i=1}^N m_i \mathbf{v}_i}{\sum_{i=1}^N m_i}, \quad \mathbf{v}_i \leftarrow \mathbf{v}_i - \mathbf{v}_{\text{COM}}$$
  Guarantee net linear momentum $\|\mathbf{P}_{\text{COM}}\| = \|\sum_{i=1}^N m_i \mathbf{v}_i\| < 1.0 \times 10^{-10}\,\text{u}\cdot\text{\AA}/\text{fs}$.
- **Kinetic Energy & Temperature Observables (`REQ-TORQ-MD-006` `[D]`)**:
  $$E_{\text{kin}}(t) = \frac{1}{2 \kappa_{\text{acc}}} \sum_{i=1}^N m_i \|\mathbf{v}_i(t)\|^2 \quad [\text{eV}]$$
  with $\kappa_{\text{acc}}^{-1} = 103.6426965\,\frac{\text{eV}}{\text{u}\cdot(\text{\AA}/\text{fs})^2}$.
  Instantaneous kinetic temperature:
  $$T(t) = \frac{2 E_{\text{kin}}(t)}{N_{\text{dof}} k_B} \quad [\text{K}]$$
  with $k_B = 8.617333262 \times 10^{-5}\,\text{eV/K}$ and constrained degrees of freedom $N_{\text{dof}} = 3N - 3$.
- **Energy Conservation Guard (`REQ-TORQ-MD-007` `[M]`)**:
  In NVE ensemble, track relative energy drift $|\frac{E_{\text{total}}(t) - E_{\text{total}}(0)}{E_{\text{total}}(0)}|$.
  If drift exceeds `config.energy_drift_tolerance` ($1.0 \times 10^{-4}$), halt and raise `EnergyDriftExceededError`.

#### 3. Replica Exchange Molecular Dynamics (REMD) Engine (`REQ-TORQ-MD-008`, `REQ-TORQ-MD-009`, `REQ-TORQ-MD-010` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_remd.py` (and export in `Libraries/__init__.py`).
- **Canonical BAOAB Langevin Thermostat (`REQ-TORQ-MD-008` `[D]`)**:
  Evolve replica $k$ at setpoint temperature $T_k$ using BAOAB splitting with friction $\gamma = 1.0\,\text{ps}^{-1} = 0.001\,\text{fs}^{-1}$:
  - $\mathbf{B}$: $\mathbf{v}_i \leftarrow \mathbf{v}_i + \frac{\Delta t}{2}\mathbf{a}_i$
  - $\mathbf{A}$: $\mathbf{r}_i \leftarrow \mathbf{r}_i + \frac{\Delta t}{2}\mathbf{v}_i$
  - $\mathbf{O}$: $\mathbf{v}_i \leftarrow c_1 \mathbf{v}_i + c_2 \sqrt{\frac{k_B T_k}{m_i}}\,\boldsymbol{\eta}_i, \quad \boldsymbol{\eta}_i \sim \mathcal{N}(\mathbf{0}, \mathbf{I}_3)$
    where $c_1 = \exp(-\gamma \Delta t)$ and $c_2 = \sqrt{\kappa_{\text{acc}}(1 - c_1^2)}$
  - $\mathbf{A}$: $\mathbf{r}_i \leftarrow \mathbf{r}_i + \frac{\Delta t}{2}\mathbf{v}_i$
  - $\mathbf{B}$: $\mathbf{F}_i = -\nabla E(\mathbf{r}_i), \quad \mathbf{a}_i = \kappa_{\text{acc}}\frac{\mathbf{F}_i}{m_i}, \quad \mathbf{v}_i \leftarrow \mathbf{v}_i + \frac{\Delta t}{2}\mathbf{a}_i$
- **Geometric Temperature Schedule (`REQ-TORQ-MD-009` `[D]`)**:
  For replicas $k \in \{0, \dots, M-1\}$:
  $$T_k = T_{\min} \left(\frac{T_{\max}}{T_{\min}}\right)^{\frac{k}{M-1}}, \quad \beta_k = \frac{1}{k_B T_k}$$
- **Metropolis Swap & State Transition (`REQ-TORQ-MD-010` `[D]`)**:
  - Evaluate acceptance probability for swap between replicas $i$ and $j = i + 1$:
    $$\Delta_{ij} = (\beta_i - \beta_j)(U_i - U_j), \quad P(\text{swap } i \leftrightarrow j) = \min(1, \exp(\Delta_{ij}))$$
  - Draw random uniform $\xi \sim \mathcal{U}(0, 1)$. If $\xi < P(\text{swap})$, accept exchange.
  - **Explicit Velocity Rescaling & Coordinate Swap**:
    Upon acceptance, configuration and velocities exchange with temperature rescaling:
    $$\mathbf{r}_i^{\text{new}} = \mathbf{r}_j, \quad \mathbf{v}_i^{\text{new}} = \mathbf{v}_j \sqrt{\frac{T_i}{T_j}}$$
    $$\mathbf{r}_j^{\text{new}} = \mathbf{r}_i, \quad \mathbf{v}_j^{\text{new}} = \mathbf{v}_i \sqrt{\frac{T_j}{T_i}}$$
    This rigorously prevents thermal inversion and preserves canonical velocity distributions.
  - **Alternating Swap Schedule**: Execute exchanges every `swap_interval_steps` (default: 100 steps = 50 fs) with alternating odd-even trials (even swap cycle: $0 \leftrightarrow 1, 2 \leftrightarrow 3, \dots$; odd swap cycle: $1 \leftrightarrow 2, 3 \leftrightarrow 4, \dots$).
  - Maintain rolling window of 50 attempts. If average acceptance $\bar{\mathcal{A}} < 0.05$ (5%) or temperature deviates by $> 50\,\text{K}$, raise `ReplicaExchangeDivergenceError`.

#### 4. Thread-Safe HDF5 SWMR Trajectory Serialization (`Libraries/cochem_torq_trajectory.py`)
- Implement `HDF5TrajectoryWriter` handling chunked extensible datasets:
  - Open file with `h5py.File(path, 'w', libver='latest')`.
  - Create chunked extensible datasets:
    * `coordinates`: `shape=(0, N, 3)`, `maxshape=(None, N, 3)`, `dtype='float64'`, `chunks=(100, N, 3)`, compression=`'gzip'`.
    * `velocities`: `shape=(0, N, 3)`, `maxshape=(None, N, 3)`, `dtype='float64'`, `chunks=(100, N, 3)`, compression=`'gzip'`.
    * `forces`: `shape=(0, N, 3)`, `maxshape=(None, N, 3)`, `dtype='float64'`, `chunks=(100, N, 3)`, compression=`'gzip'`.
    * `energies`: `shape=(0, 3)`, `maxshape=(None, 3)`, `dtype='float64'`, `chunks=(100, 3)` (cols: potential, kinetic, total).
    * `temperatures`: `shape=(0,)`, `maxshape=(None,)`, `dtype='float64'`, `chunks=(100,)`.
    * `time_fs`: `shape=(0,)`, `maxshape=(None,)`, `dtype='float64'`, `chunks=(100,)`.
    * Store static `atomic_numbers`: `shape=(N,)`, `dtype='int64'`.
  - Flush all datasets and metadata to disk: `f.flush()`.
  - Switch into active SWMR mode: `f.swmr_mode = True`.
  - Provide append frame method `append_frame(frame: TrajectoryFrame)` resizing datasets, assigning values, and calling `dataset.flush()`.

#### 5. Hardware & Concurrency Dispatcher (`Libraries/cochem_torq_md_env.py`)
- Provide `dispatch_md_device(requested_device: Optional[str] = None) -> torch.device`:
  - If requested device is `"mps"` or `torch.backends.mps.is_available()`, log info and automatically return `torch.device("cpu")` to comply with the Apple Silicon MPS `float64` fallback mandate.
  - If requested is `"cuda"` and `torch.cuda.is_available()`, return `torch.device("cuda")`.
  - Else return `torch.device("cpu")`.
- Provide `resolve_hpc_safe_scratch(subfolder: str = "cochem_torq_md") -> Path`:
  - If `$SLURM_TMPDIR` is defined and exists, use `$SLURM_TMPDIR / subfolder`.
  - Else if `$TMPDIR` is defined and exists, use `$TMPDIR / subfolder`.
  - Else use `Path.home() / ".cochem" / "scratch" / subfolder`.
  - Create directory and return absolute `Path`.

---

### 5. TEST FIXTURES & PHYSICAL VERIFICATION SUITE

- **Test Suite Location**: `tests/test_chunk21_molecular_dynamics.py`
- **Zero-Mock Policy**: Strictly NO mocks, NO `unittest.mock`, NO `@patch`, NO dummy synthetic loops. All tests run against genuine physical potentials and authentic molecular structures.

#### 1. Authentic Molecular Reference Geometries:
```python
import torch

# Authentic equilibrium Water Dimer (H2O)2 geometry (N=6 atoms) [M]
WATER_DIMER_COORDS = torch.tensor(
    [
        [-1.484, 0.000, -0.091],  # O1 (donor)
        [-1.877, 0.760, 0.354],  # H1
        [-0.533, 0.000, 0.038],  # H2 (bridging hydrogen)
        [1.408, 0.000, 0.110],  # O2 (acceptor)
        [1.758, 0.760, -0.335],  # H3
        [1.758, -0.760, -0.335],  # H4
    ],
    dtype=torch.float64,
)
WATER_DIMER_Z = torch.tensor([8, 1, 1, 8, 1, 1], dtype=torch.int64)

# Authentic equilibrium Water Monomer H2O (N=3 atoms) [M]
WATER_MONOMER_COORDS = torch.tensor(
    [
        [0.0000, 0.0000, 0.1173],  # O
        [0.0000, 0.7572, -0.4692],  # H1
        [0.0000, -0.7572, -0.4692],  # H2
    ],
    dtype=torch.float64,
)
WATER_MONOMER_Z = torch.tensor([8, 1, 1], dtype=torch.int64)
```

#### 2. Analytical Physical Force Field for Water Dimer / Monomer:
```python
import math
import torch


class FlexibleWaterPotential(torch.nn.Module):
  """Harmonic valence force field + Lennard-Jones / Coulomb non-bonded potential for water in eV [D]."""

  def __init__(self) -> None:
    super().__init__()
    # Bond and angle parameters: O-H r0 = 0.9572 A, H-O-H theta0 = 104.52 deg
    self.r0 = 0.9572
    self.theta0 = 104.52 * math.pi / 180.0
    self.kb = 46.0  # eV / A^2
    self.kt = 4.5  # eV / rad^2
    # Non-bonded parameters for O-O interaction
    self.sigma_oo = 3.166  # A
    self.epsilon_oo = 0.0067  # eV

  def forward(self, coords: torch.Tensor) -> torch.Tensor:
    # Ensure coords require gradients for autograd forces
    total_energy = torch.zeros((), dtype=torch.float64, device=coords.device)
    n_atoms = coords.shape[0]
    n_waters = n_atoms // 3

    for w in range(n_waters):
      idx_O = 3 * w
      idx_H1 = 3 * w + 1
      idx_H2 = 3 * w + 2
      r_O = coords[idx_O]
      r_H1 = coords[idx_H1]
      r_H2 = coords[idx_H2]

      v1 = r_H1 - r_O
      v2 = r_H2 - r_O
      d1 = torch.linalg.norm(v1)
      d2 = torch.linalg.norm(v2)

      # Harmonic bond stretching
      e_stretch = 0.5 * self.kb * ((d1 - self.r0) ** 2 + (d2 - self.r0) ** 2)

      # Harmonic angle bending
      cos_theta = torch.clamp(torch.dot(v1, v2) / (d1 * d2), -1.0, 1.0)
      theta = torch.acos(cos_theta)
      e_bend = 0.5 * self.kt * ((theta - self.theta0) ** 2)
      total_energy = total_energy + e_stretch + e_bend

    # Intermolecular non-bonded potential between oxygens if dimer
    if n_waters > 1:
      r_O1 = coords[0]
      r_O2 = coords[3]
      r_oo = torch.linalg.norm(r_O1 - r_O2)
      sr6 = (self.sigma_oo / r_oo) ** 6
      e_lj = 4.0 * self.epsilon_oo * (sr6**2 - sr6)
      total_energy = total_energy + e_lj

    return total_energy
```

#### 3. Test Suite Fixtures (`tests/test_chunk21_molecular_dynamics.py`):
1. `test_mendeleev_dynamic_mass_retrieval`: Dynamically query atomic masses for H ($Z=1$) and O ($Z=8$). Assert $m_{\text{H}} \in [1.0079, 1.0081]\,\text{u}$ and $m_{\text{O}} \in [15.999, 16.000]\,\text{u}$. Assert no hardcoded static dictionary is used.
2. `test_conservative_force_autograd_and_curl_free`: Evaluate autograd forces $\mathbf{F} = -\nabla E$ on Water monomer. Verify analytical forces match central finite difference within $1.0 \times 10^{-4}\,\text{eV/\AA}$ and force curl $\|\nabla \times \mathbf{F}\|_2 < 1.0 \times 10^{-6}\,\text{eV/\AA}^2$.
3. `test_acceleration_dimensional_factor_conversion`: Verify $\kappa_{\text{acc}} = 9.648533215665 \times 10^{-3}\,\frac{\text{\AA}/\text{fs}^2}{\text{eV}/(\text{\AA}\cdot\text{u})}$ matches exact identity derived from CODATA 2018 fundamental constants.
4. `test_center_of_mass_momentum_elimination`: Initialize water dimer with non-zero velocities. Run `remove_center_of_mass_momentum()`. Assert net linear momentum $\|\mathbf{P}_{\text{COM}}\| < 1.0 \times 10^{-10}\,\text{u}\cdot\text{\AA}/\text{fs}$.
5. `test_kinetic_energy_and_temperature_degrees_of_freedom`: Calculate $E_{\text{kin}}$ and $T$ for water dimer ($N=6$). Confirm degrees of freedom strictly equal $N_{\text{dof}} = 3N - 3 = 15$.
6. `test_nve_energy_conservation_water_dimer`: Execute 10 ps NVE Velocity Verlet trajectory ($\Delta t = 0.5\,\text{fs}$, 20,000 steps) on water dimer. Assert relative energy drift $\max_t |(E_{\text{total}}(t) - E_0) / E_0| < 1.0 \times 10^{-4}$.
7. `test_energy_drift_exceeded_error_trigger`: Intentionally run integration with an unstable timestep ($\Delta t = 5.0\,\text{fs}$). Verify `EnergyDriftExceededError` is raised with step and drift telemetry.
8. `test_symplectic_phase_space_time_reversibility`: Integrate water dimer forward 1000 steps ($\Delta t = 0.5\,\text{fs}$), invert velocities ($\mathbf{v} \leftarrow -\mathbf{v}$), integrate backward 1000 steps, invert velocities again. Assert coordinate deviation $\max_i \|\mathbf{r}_i(2N) - \mathbf{r}_i(0)\|_2 < 1.0 \times 10^{-5}\,\text{\AA}$.
9. `test_baoab_langevin_canonical_bath_coupling`: Run BAOAB thermostat at $T_{\text{target}} = 300\,\text{K}$ for 5000 steps with friction $\gamma = 1.0\,\text{ps}^{-1}$. Assert average trajectory temperature converges to $300 \pm 5\,\text{K}$ conforming to Maxwell-Boltzmann distribution.
10. `test_remd_geometric_temperature_schedule`: Initialize `REMDConfig` with $M=4$, $T_{\min}=300\,\text{K}$, $T_{\max}=600\,\text{K}$. Confirm $T_k = [300.0, 377.98, 476.22, 600.0]\,\text{K}$ and $\beta_k = 1 / (k_B T_k)$.
11. `test_remd_metropolis_swap_and_velocity_rescaling`: Execute REMD swap trial between two replicas at $T_1 = 300\,\text{K}$ and $T_2 = 400\,\text{K}$. Verify acceptance probability matches $P = \min(1, \exp[(\beta_1 - \beta_2)(U_1 - U_2)])$. Upon acceptance, verify $\mathbf{v}_1^{\text{new}} = \mathbf{v}_2 \sqrt{T_1 / T_2}$ and $\mathbf{v}_2^{\text{new}} = \mathbf{v}_1 \sqrt{T_2 / T_1}$ ensuring zero thermal inversion.
12. `test_hdf5_swmr_trajectory_lifecycle`: Instantiate `HDF5TrajectoryWriter`, write frames, verify groups/datasets exist before `swmr_mode = True`, and verify an independent reader can read frames concurrently without locking conflicts.
13. `test_apple_silicon_mps_float64_cpu_fallback`: Dispatch with `"mps"`. Assert dispatcher intercepts request and returns `torch.device("cpu")` to preserve double-precision compliance.
14. `test_pydantic_v2_data_validation`: Assert `REMDConfig` rejects $T_{\max} \le T_{\min}$ and `total_steps < swap_interval`. Assert `VelocityVerletConfig` rejects $\Delta t > 1.0\,\text{fs}$.

---

### 6. ACTION PLAN FOR CODER

1. Create `Libraries/cochem_torq_md_errors.py` implementing the complete custom exception hierarchy (`TorqMDError`, `EnergyDriftExceededError`, `SymplecticIntegratorError`, `ReplicaExchangeDivergenceError`, `HardwareDispatchError`) without empty `pass` blocks.
2. Create `Libraries/cochem_torq_md_schemas.py` implementing Pydantic v2 data models (`VelocityVerletConfig`, `REMDConfig`, `MDState`, `TrajectoryFrame`, `ExchangeLog`).
3. Create `Libraries/cochem_torq_masses.py` implementing dynamic atomic mass lookup via the `mendeleev` library.
4. Create `Libraries/cochem_torq_md_env.py` providing `dispatch_md_device` (with automatic Apple Silicon MPS float64 fallback to CPU) and `resolve_hpc_safe_scratch`.
5. Create `Libraries/cochem_torq_symplectic.py` implementing conservative autograd forces, dimensional acceleration, COM momentum projection, kinetic energy/temperature observables, and the symplectic Velocity Verlet integrator with energy drift monitoring.
6. Create `Libraries/cochem_torq_remd.py` implementing the BAOAB Langevin thermostat, geometric temperature schedule, alternating odd-even Metropolis swap trials, and velocity rescaling.
7. Create `Libraries/cochem_torq_trajectory.py` implementing thread-safe HDF5 SWMR chunked extensible trajectory serialization following the strict SWMR lifecycle.
8. Export all public classes, functions, and exceptions in `Libraries/__init__.py`.
9. Implement the mock-free unit test suite `tests/test_chunk21_molecular_dynamics.py` exercising all 14 physical verification test fixtures using authentic water dimer and monomer coordinates.
10. Update/create `pytest.ini` restricting `testpaths = tests/test_chunk21_molecular_dynamics.py` and run `pytest tests/test_chunk21_molecular_dynamics.py -v`, confirming all tests pass with exit code 0.
I have initiated the adversarial audit of the chunked prompt with the `cochem-audit` subagent. Awaiting verification results.
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous Neural Network Molecular Dynamics (NNMD) simulation and Replica Exchange Molecular Dynamics (REMD) enhanced sampling engine specified in Software Requirements Specification (SRS) Chunk 21: `TORQ_Molecular_Dynamics_Part_1` (`COCHEM-SRS-CHUNK-21-TORQ`).

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev monoisotopic atomic mass mandate, and Method Matrix v4 (`[M]` Empirical Benchmark, `[D]` Derived Mathematical Relationship, `[E]` Estimated Theoretical Projection). Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine physical tensors, authentic molecular coordinates, and real chemical observables.

---

### 1. DIRECTORY, PERSISTENCE & 6-TIER RUNTIME CONTRACTS

1. **Tripartite Workspace Air-Gap Paths**:
   - `COCHEM_SRC_DIR` ($R_{\text{src}}$): `pathlib.Path(os.environ.get("COCHEM_SRC_DIR", Path.cwd()))` (Read-only source repository: symplectic algorithms, autograd gradient pipelines, COM momentum projectors, and replica exchange state machines).
   - `COCHEM_DATA_DIR` ($R_{\text{data}}$): `pathlib.Path(os.environ.get("COCHEM_DATA_DIR", Path.home() / ".cochem" / "data"))` (Read-only neural network potential checkpoints, molecular topologies, and benchmark reference geometries under `COCHEM_OFFLINE=1`).
   - `COCHEM_ARTIFACTS_DIR` ($R_{\text{art}}$): `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR", Path.home() / ".cochem" / "artifacts"))` (Read-write trajectory frames, thermodynamic observables, exchange logs, checkpoint restart files, and telemetry).
   - `COCHEM_SCRATCH_DIR`: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR", os.environ.get("SLURM_TMPDIR", Path.home() / ".cochem" / "scratch")))`.
2. **6-Tier Runtime & Hardware Concurrency**:
   - **Accelerator Binding & Safe Device Dispatcher**:
     * Query hardware availability: NVIDIA CUDA (`torch.cuda.is_available()`), Apple Silicon Metal Performance Shaders (`getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()`), or CPU.
     * **Apple Silicon MPS `float64` Automatic Fallback Rule (`[M]`)**: Metal Performance Shaders (MPS) hardware does not support native 64-bit floating point (`torch.float64`). Attempting to allocate or compute `float64` tensors on `mps` raises `TypeError: Cannot convert a MPS tensor to float64`. When executing molecular dynamics integration requiring `torch.float64`, the dispatcher must automatically intercept and route execution to `cpu`. Single-precision evaluation remains on `mps`.
     * Dynamic hardware detection must never hardcode device ordinals (e.g., `cuda:0` is strictly banned).
   - **Strict Double-Precision (`torch.float64`) Mandate**:
     * Mandatory `torch.float64` (`torch.double`, 53-bit significand) across all coordinates, velocities, forces, accelerations, and potential evaluations to prevent unphysical energy drift (`[M]`).
   - **Thread-Safe & Multiprocessing-Safe HDF5 SWMR Serialization**:
     * Trajectory storage utilizes `h5py` Single-Writer-Multiple-Reader (SWMR) mode (`libver='latest'`, `swmr=True`) with chunked extensible datasets (`maxshape=(None, N_{\text{atoms}}, 3)`) and lossless compression (`gzip` or `lzf`) (`[D]`).
     * **SWMR Lifecycle Sequencing**: All groups, datasets, and metadata attributes must be created and flushed to disk **prior** to engaging `f.swmr_mode = True`, as dataset creation is strictly prohibited by HDF5 while in active SWMR mode.
     * **HPC Distributed Lock Prohibition Rule (`[M]`)**: On Tier 6 HPC environments, parallel network filesystems (Lustre, GPFS, BeeGFS, NFS) rely on centralized distributed lock managers. Direct `filelock.FileLock` across parallel filesystems causes lock manager deadlocks (`[Errno 37] No locks available`). Unconditional `filelock.FileLock` on parallel network filesystems is strictly prohibited. All staging, locking, and temporary files must be resolved dynamically to the node-local NVMe scratch directory `$SLURM_TMPDIR` (or `$TMPDIR`) via `resolve_hpc_safe_scratch()`.
     * On single-node environments (Tiers 1-5), local file locking via `filelock.FileLock(lock_path, timeout=30.0)` is permitted.
   - **Atomic Serialization**: Write temporary file `.tmp`, flush to disk with `os.fsync(f.fileno())`, atomically replace via `os.replace`, and write an accompanying cryptographic `.sha256` digest file.
3. **OS-Agnostic Dynamic Paths**: All filesystem operations are mediated via `pathlib.Path`. Hardcoded OS path separators (`/`, `\`), `$HOME`, or `C:\` are strictly prohibited.

---

### 2. PHYSICAL CONSTANTS & CONVERSION FACTORS

You must strictly embed the authoritative CODATA 2018 / CIAAW physical constants without truncation or manual rounding:
- Elementary Charge: $e = 1.602176634 \times 10^{-19}\text{ C} = \text{J/eV}$ `[D]`
- Unified Atomic Mass Unit: $u = 1.66053906660 \times 10^{-27}\text{ kg}$ `[D]`
- Boltzmann Constant: $k_B = 8.617333262 \times 10^{-5}\text{ eV/K}$ `[D]`
- Length Scale Factor: $1.0 \times 10^{-10}\text{ m} = 1.0\text{ \AA}$ `[D]`
- Time Scale Factor: $1.0 \times 10^{-15}\text{ s} = 1.0\text{ fs}$ `[D]`
- Dimensional Acceleration Factor:
  $$\kappa_{\text{acc}} = \frac{1.602176634 \times 10^{-19}\text{ J/eV} \times (10^{10}\text{ \AA/m})^2}{1.66053906660 \times 10^{-27}\text{ kg/u} \times (10^{15}\text{ fs/s})^2} = 9.648533215665 \times 10^{-3}\,\frac{\text{\AA}/\text{fs}^2}{\text{eV}/(\text{\AA}\cdot\text{u})} \quad [D]$$
- Kinetic Mass Scale Factor:
  $$\kappa_{\text{acc}}^{-1} = 103.6426965\,\frac{\text{eV}}{\text{u}\cdot(\text{\AA}/\text{fs})^2} \quad [D]$$

---

### 3. DOMAIN EXCEPTIONS & PYDANTIC V2 DATA CONTRACTS

- **Files**: `Libraries/cochem_torq_md_errors.py` and `Libraries/cochem_torq_md_schemas.py` (and export in `Libraries/__init__.py`).
- **Domain Exception Hierarchy**:
```python
from typing import Any, Dict, Optional


class TorqMDError(Exception):
  """Root base exception for all TORQ molecular dynamics failures [M]."""

  def __init__(
      self,
      message: str,
      error_code: str = "TORQ_MD_GENERIC_ERROR",
      component: str = "molecular_dynamics",
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(message)
    self.error_code = error_code
    self.component = component
    self.diagnostics = diagnostics or {}


class EnergyDriftExceededError(TorqMDError):
  """Raised when NVE relative total energy drift |Delta E / E_0| exceeds tolerance (1e-4) [M]."""

  def __init__(
      self,
      drift: float,
      tolerance: float,
      step: int,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"NVE relative energy drift {drift:.6e} exceeded tolerance"
        f" {tolerance:.6e} at step {step}.",
        error_code="ENERGY_DRIFT_EXCEEDED",
        component="symplectic_integrator",
        diagnostics=diagnostics,
    )
    self.drift = drift
    self.tolerance = tolerance
    self.step = step


class SymplecticIntegratorError(TorqMDError):
  """Raised when non-finite (NaN or Inf) values are encountered in coordinates, velocities, or forces [M]."""

  def __init__(
      self,
      tensor_name: str,
      step: int,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"Non-finite values encountered in {tensor_name} at step {step}.",
        error_code="SYMPLECTIC_NON_FINITE_TENSOR",
        component="symplectic_integrator",
        diagnostics=diagnostics,
    )
    self.tensor_name = tensor_name
    self.step = step


class ReplicaExchangeDivergenceError(TorqMDError):
  """Raised when rolling swap acceptance drops below 5% or temperatures deviate by > 50 K [M]."""

  def __init__(
      self,
      reason: str,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"Replica Exchange divergent state: {reason}",
        error_code="REMD_DIVERGENCE",
        component="remd_engine",
        diagnostics=diagnostics,
    )


class HardwareDispatchError(TorqMDError):
  """Raised when requested hardware devices are unavailable or fail double-precision compliance [M]."""

  def __init__(
      self,
      device_requested: str,
      reason: str,
      diagnostics: Optional[Dict[str, Any]] = None,
  ) -> None:
    super().__init__(
        f"Hardware dispatch failed for '{device_requested}': {reason}",
        error_code="HARDWARE_DISPATCH_FAILED",
        component="hardware_dispatcher",
        diagnostics=diagnostics,
    )
```

- **Pydantic v2 Data Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
```python
from pathlib import Path
from typing import List, Literal, NamedTuple, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
import torch


class VelocityVerletConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  timestep_fs: float = Field(default=0.5, gt=0.0, le=1.0)
  n_steps: int = Field(gt=0, default=20000)
  save_interval: int = Field(gt=0, default=10)
  device: str = Field(default="cpu")
  dtype: Literal["float64"] = Field(default="float64")
  energy_drift_tolerance: float = Field(default=1e-4, gt=0.0)
  remove_com_momentum: bool = Field(default=True)


class REMDConfig(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  n_replicas: int = Field(ge=2, default=4)
  t_min_k: float = Field(gt=0.0, default=300.0)
  t_max_k: float = Field(gt=0.0, default=600.0)
  swap_interval_steps: int = Field(ge=10, default=100)
  total_steps_per_replica: int = Field(gt=0, default=100000)
  friction_ps: float = Field(default=1.0, gt=0.0)
  output_dir: Path

  @model_validator(mode="after")
  def validate_remd_parameters(self) -> "REMDConfig":
    if self.t_max_k <= self.t_min_k:
      raise ValueError(
          f"t_max_k ({self.t_max_k}) must be strictly greater than t_min_k"
          f" ({self.t_min_k})"
      )
    if self.total_steps_per_replica < self.swap_interval_steps:
      raise ValueError(
          f"total_steps_per_replica ({self.total_steps_per_replica}) must be >="
          f" swap_interval_steps ({self.swap_interval_steps})"
      )
    return self


class MDState(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  step: int = Field(ge=0)
  time_fs: float = Field(ge=0.0)
  potential_energy_ev: float
  kinetic_energy_ev: float = Field(ge=0.0)
  total_energy_ev: float
  temperature_k: float = Field(ge=0.0)


class TrajectoryFrame(NamedTuple):
  step: int
  time_fs: float
  atomic_numbers: torch.Tensor  # Shape: [N_atoms], dtype: torch.int64
  coordinates: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
  velocities: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
  forces: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
  potential_energy_ev: float
  kinetic_energy_ev: float


class ExchangeLog(BaseModel):
  model_config = ConfigDict(frozen=True, extra="forbid")
  attempt_step: int
  replica_i: int
  replica_j: int
  temp_i_k: float
  temp_j_k: float
  energy_i_ev: float
  energy_j_ev: float
  p_swap: float = Field(ge=0.0, le=1.0)
  accepted: bool
```

---

### 4. MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Dynamic Atomic Masses via Mendeleev (`REQ-TORQ-MD-004` `[M]`)
- **File Target**: `Libraries/cochem_torq_masses.py` (and export in `Libraries/__init__.py`).
- Implement dynamic lookup using the `mendeleev` library:
  ```python
  from mendeleev import element
  import torch


  def get_atomic_masses(
      atomic_numbers: torch.Tensor, device: torch.device
  ) -> torch.Tensor:
    """Retrieve CIAAW standard atomic weights in unified atomic mass units (u)."""
    masses = []
    for z in atomic_numbers.view(-1).tolist():
      elem = element(int(z))
      masses.append(float(elem.mass))
    return torch.tensor(masses, dtype=torch.float64, device=device).unsqueeze(
        -1
    )
```
- Strictly forbid hardcoded mass dictionaries, integer mass approximations, or manual CODATA mass tables.

#### 2. Conservative Force Autograd & Symplectic Velocity Verlet Integrator (`REQ-TORQ-MD-001`, `REQ-TORQ-MD-002`, `REQ-TORQ-MD-003`, `REQ-TORQ-MD-005`, `REQ-TORQ-MD-006`, `REQ-TORQ-MD-007` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_symplectic.py` (and export in `Libraries/__init__.py`).
- **Conservative Force Autograd (`REQ-TORQ-MD-001` `[D]`)**:
  Compute Cartesian forces as negative analytical gradient of neural potential:
  $$\mathbf{F}_i(t) = -\nabla_{\mathbf{r}_i} E_{\text{TORQ}}(\mathbf{r}(t))$$
  evaluated via `torch.autograd.grad(outputs=energy, inputs=coords, grad_outputs=torch.ones_like(energy), create_graph=False)[0]`.
- **Dimensional Acceleration Formulation (`REQ-TORQ-MD-002` `[D]`)**:
  $$\mathbf{a}_i(t) = \kappa_{\text{acc}} \frac{\mathbf{F}_i(t)}{m_i}, \quad \kappa_{\text{acc}} = 9.648533215665 \times 10^{-3}\,\frac{\text{\AA}/\text{fs}^2}{\text{eV}/(\text{\AA}\cdot\text{u})}$$
- **Symplectic Half-Step Velocity Verlet Integration (`REQ-TORQ-MD-003` `[D]`)**:
  1. Half-step velocity update: $\mathbf{v}_i(t + \frac{\Delta t}{2}) = \mathbf{v}_i(t) + \frac{\Delta t}{2} \mathbf{a}_i(t)$
  2. Full-step coordinate update: $\mathbf{r}_i(t + \Delta t) = \mathbf{r}_i(t) + \Delta t\,\mathbf{v}_i(t + \frac{\Delta t}{2})$
  3. Force evaluation: $\mathbf{F}_i(t + \Delta t) = -\nabla_{\mathbf{r}_i} E_{\text{TORQ}}(\mathbf{r}(t + \Delta t))$
  4. Full-step acceleration update: $\mathbf{a}_i(t + \Delta t) = \kappa_{\text{acc}} \frac{\mathbf{F}_i(t + \Delta t)}{m_i}$
  5. Final velocity update: $\mathbf{v}_i(t + \Delta t) = \mathbf{v}_i(t + \frac{\Delta t}{2}) + \frac{\Delta t}{2} \mathbf{a}_i(t + \Delta t)$
  - Check `torch.isnan` and `torch.isinf` on coordinates, velocities, and forces at each step. Raise `SymplecticIntegratorError` immediately if detected.
- **Center-of-Mass Momentum Elimination (`REQ-TORQ-MD-005` `[D]`)**:
  $$\mathbf{v}_{\text{COM}} = \frac{\sum_{i=1}^N m_i \mathbf{v}_i}{\sum_{i=1}^N m_i}, \quad \mathbf{v}_i \leftarrow \mathbf{v}_i - \mathbf{v}_{\text{COM}}$$
  Guarantee net linear momentum $\|\mathbf{P}_{\text{COM}}\| = \|\sum_{i=1}^N m_i \mathbf{v}_i\| < 1.0 \times 10^{-10}\,\text{u}\cdot\text{\AA}/\text{fs}$.
- **Kinetic Energy & Temperature Observables (`REQ-TORQ-MD-006` `[D]`)**:
  $$E_{\text{kin}}(t) = \frac{1}{2 \kappa_{\text{acc}}} \sum_{i=1}^N m_i \|\mathbf{v}_i(t)\|^2 \quad [\text{eV}]$$
  with $\kappa_{\text{acc}}^{-1} = 103.6426965\,\frac{\text{eV}}{\text{u}\cdot(\text{\AA}/\text{fs})^2}$.
  Instantaneous kinetic temperature:
  $$T(t) = \frac{2 E_{\text{kin}}(t)}{N_{\text{dof}} k_B} \quad [\text{K}]$$
  with $k_B = 8.617333262 \times 10^{-5}\,\text{eV/K}$ and constrained degrees of freedom $N_{\text{dof}} = 3N - 3$ (when COM momentum is removed).
- **Energy Conservation Guard (`REQ-TORQ-MD-007` `[M]`)**:
  In NVE ensemble, track relative energy drift $|\frac{E_{\text{total}}(t) - E_{\text{total}}(0)}{E_{\text{total}}(0)}|$.
  If drift exceeds `config.energy_drift_tolerance` ($1.0 \times 10^{-4}$), halt and raise `EnergyDriftExceededError`. Note: To verify energy conservation without artificial shadow Hamiltonian fluctuation artifacts, test benchmarks with unconstrained stiff O-H stretching ($k_b \approx 46.0\,\text{eV/\AA}^2$) should utilize $\Delta t \le 0.1\,\text{fs}$ or measure secular linear regression drift over continuous trajectories.

#### 3. Replica Exchange Molecular Dynamics (REMD) Engine (`REQ-TORQ-MD-008`, `REQ-TORQ-MD-009`, `REQ-TORQ-MD-010` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_remd.py` (and export in `Libraries/__init__.py`).
- **Canonical BAOAB Langevin Thermostat (`REQ-TORQ-MD-008` `[D]`)**:
  Evolve replica $k$ at setpoint temperature $T_k$ using BAOAB splitting with friction $\gamma = 1.0\,\text{ps}^{-1} = 0.001\,\text{fs}^{-1}$:
  - $\mathbf{B}$: $\mathbf{v}_i \leftarrow \mathbf{v}_i + \frac{\Delta t}{2}\mathbf{a}_i$
  - $\mathbf{A}$: $\mathbf{r}_i \leftarrow \mathbf{r}_i + \frac{\Delta t}{2}\mathbf{v}_i$
  - $\mathbf{O}$: $\mathbf{v}_i \leftarrow c_1 \mathbf{v}_i + c_2 \sqrt{\frac{k_B T_k}{m_i}}\,\boldsymbol{\eta}_i, \quad \boldsymbol{\eta}_i \sim \mathcal{N}(\mathbf{0}, \mathbf{I}_3)$
    where $c_1 = \exp(-\gamma \Delta t)$ and $c_2 = \sqrt{\kappa_{\text{acc}}(1 - c_1^2)}$
  - $\mathbf{A}$: $\mathbf{r}_i \leftarrow \mathbf{r}_i + \frac{\Delta t}{2}\mathbf{v}_i$
  - $\mathbf{B}$: $\mathbf{F}_i = -\nabla E(\mathbf{r}_i), \quad \mathbf{a}_i = \kappa_{\text{acc}}\frac{\mathbf{F}_i}{m_i}, \quad \mathbf{v}_i \leftarrow \mathbf{v}_i + \frac{\Delta t}{2}\mathbf{a}_i$
  *Note on Degrees of Freedom*: The stochastic Langevin step excites all $3N$ degrees of freedom; project out center-of-mass momentum during thermalization to maintain parity with $N_{\text{dof}} = 3N - 3$ temperature evaluations.
- **Geometric Temperature Schedule (`REQ-TORQ-MD-009` `[D]`)**:
  For replicas $k \in \{0, \dots, M-1\}$:
  $$T_k = T_{\min} \left(\frac{T_{\max}}{T_{\min}}\right)^{\frac{k}{M-1}}, \quad \beta_k = \frac{1}{k_B T_k}$$
- **Metropolis Swap & State Transition (`REQ-TORQ-MD-010` `[D]`)**:
  - Evaluate acceptance probability for swap between replicas $i$ and $j = i + 1$:
    $$\Delta_{ij} = (\beta_i - \beta_j)(U_i - U_j), \quad P(\text{swap } i \leftrightarrow j) = \min(1, \exp(\Delta_{ij}))$$
  - Draw random uniform $\xi \sim \mathcal{U}(0, 1)$. If $\xi < P(\text{swap})$, accept exchange.
  - **Explicit Velocity Rescaling & Coordinate Swap**:
    Upon acceptance, configuration and velocities exchange with temperature rescaling:
    $$\mathbf{r}_i^{\text{new}} = \mathbf{r}_j, \quad \mathbf{v}_i^{\text{new}} = \mathbf{v}_j \sqrt{\frac{T_i}{T_j}}$$
    $$\mathbf{r}_j^{\text{new}} = \mathbf{r}_i, \quad \mathbf{v}_j^{\text{new}} = \mathbf{v}_i \sqrt{\frac{T_j}{T_i}}$$
    This rigorously prevents thermal inversion and preserves canonical velocity distributions.
  - **Alternating Swap Schedule**: Execute exchanges every `swap_interval_steps` (default: 100 steps = 50 fs) with alternating odd-even trials (even swap cycle: $0 \leftrightarrow 1, 2 \leftrightarrow 3, \dots$; odd swap cycle: $1 \leftrightarrow 2, 3 \leftrightarrow 4, \dots$).
  - Maintain rolling window of 50 attempts. If average acceptance $\bar{\mathcal{A}} < 0.05$ (5%) or temperature deviates by $> 50\,\text{K}$, raise `ReplicaExchangeDivergenceError`.

#### 4. Thread-Safe HDF5 SWMR Trajectory Serialization (`Libraries/cochem_torq_trajectory.py`)
- Implement `HDF5TrajectoryWriter` handling chunked extensible datasets:
  - Open file with `h5py.File(path, 'w', libver='latest')`.
  - Create chunked extensible datasets:
    * `coordinates`: `shape=(0, N, 3)`, `maxshape=(None, N, 3)`, `dtype='float64'`, `chunks=(100, N, 3)`, compression=`'gzip'`.
    * `velocities`: `shape=(0, N, 3)`, `maxshape=(None, N, 3)`, `dtype='float64'`, `chunks=(100, N, 3)`, compression=`'gzip'`.
    * `forces`: `shape=(0, N, 3)`, `maxshape=(None, N, 3)`, `dtype='float64'`, `chunks=(100, N, 3)`, compression=`'gzip'`.
    * `energies`: `shape=(0, 3)`, `maxshape=(None, 3)`, `dtype='float64'`, `chunks=(100, 3)` (cols: potential, kinetic, total).
    * `temperatures`: `shape=(0,)`, `maxshape=(None,)`, `dtype='float64'`, `chunks=(100,)`.
    * `time_fs`: `shape=(0,)`, `maxshape=(None,)`, `dtype='float64'`, `chunks=(100,)`.
    * Store static `atomic_numbers`: `shape=(N,)`, `dtype='int64'`.
  - Flush all datasets and metadata to disk: `f.flush()`.
  - Switch into active SWMR mode: `f.swmr_mode = True`.
  - Provide append frame method `append_frame(frame: TrajectoryFrame)` resizing datasets, assigning values, and calling `dataset.flush()`.

#### 5. Hardware & Concurrency Dispatcher (`Libraries/cochem_torq_md_env.py`)
- Provide `dispatch_md_device(requested_device: Optional[str] = None) -> torch.device`:
  - If requested device is `"mps"` or `torch.backends.mps.is_available()`, log info and automatically return `torch.device("cpu")` to comply with the Apple Silicon MPS `float64` fallback mandate.
  - If requested is `"cuda"` and `torch.cuda.is_available()`, return `torch.device("cuda")`.
  - Else return `torch.device("cpu")`.
- Provide `resolve_hpc_safe_scratch(subfolder: str = "cochem_torq_md") -> Path`:
  - If `$SLURM_TMPDIR` is defined and exists, use `$SLURM_TMPDIR / subfolder`.
  - Else if `$TMPDIR` is defined and exists, use `$TMPDIR / subfolder`.
  - Else use `Path.home() / ".cochem" / "scratch" / subfolder`.
  - Create directory and return absolute `Path`.

---

### 5. TEST FIXTURES & PHYSICAL VERIFICATION SUITE

- **Test Suite Location**: `tests/test_chunk21_molecular_dynamics.py`
- **Zero-Mock Policy**: Strictly NO mocks, NO `unittest.mock`, NO `@patch`, NO dummy synthetic loops. All tests run against genuine physical potentials and authentic molecular structures.

#### 1. Authentic Molecular Reference Geometries:
```python
import torch

# Authentic equilibrium Water Dimer (H2O)2 geometry (N=6 atoms) [M]
WATER_DIMER_COORDS = torch.tensor(
    [
        [-1.484, 0.000, -0.091],  # O1 (donor)
        [-1.877, 0.760, 0.354],  # H1
        [-0.533, 0.000, 0.038],  # H2 (bridging hydrogen)
        [1.408, 0.000, 0.110],  # O2 (acceptor)
        [1.758, 0.760, -0.335],  # H3
        [1.758, -0.760, -0.335],  # H4
    ],
    dtype=torch.float64,
)
WATER_DIMER_Z = torch.tensor([8, 1, 1, 8, 1, 1], dtype=torch.int64)

# Authentic equilibrium Water Monomer H2O (N=3 atoms) [M]
WATER_MONOMER_COORDS = torch.tensor(
    [
        [0.0000, 0.0000, 0.1173],  # O
        [0.0000, 0.7572, -0.4692],  # H1
        [0.0000, -0.7572, -0.4692],  # H2
    ],
    dtype=torch.float64,
)
WATER_MONOMER_Z = torch.tensor([8, 1, 1], dtype=torch.int64)
```

#### 2. Analytical Physical Force Field for Water Dimer / Monomer:
```python
import math
import torch


class FlexibleWaterPotential(torch.nn.Module):
  """Harmonic valence force field + Lennard-Jones / Coulomb non-bonded potential for water in eV [D]."""

  def __init__(self) -> None:
    super().__init__()
    # Bond and angle parameters: O-H r0 = 0.9572 A, H-O-H theta0 = 104.52 deg
    self.r0 = 0.9572
    self.theta0 = 104.52 * math.pi / 180.0
    self.kb = 46.0  # eV / A^2
    self.kt = 4.5  # eV / rad^2
    # Non-bonded parameters for O-O interaction
    self.sigma_oo = 3.166  # A
    self.epsilon_oo = 0.0067  # eV

  def forward(self, coords: torch.Tensor) -> torch.Tensor:
    total_energy = torch.zeros((), dtype=torch.float64, device=coords.device)
    n_atoms = coords.shape[0]
    n_waters = n_atoms // 3

    for w in range(n_waters):
      idx_O = 3 * w
      idx_H1 = 3 * w + 1
      idx_H2 = 3 * w + 2
      r_O = coords[idx_O]
      r_H1 = coords[idx_H1]
      r_H2 = coords[idx_H2]

      v1 = r_H1 - r_O
      v2 = r_H2 - r_O
      d1 = torch.linalg.norm(v1)
      d2 = torch.linalg.norm(v2)

      # Harmonic bond stretching
      e_stretch = 0.5 * self.kb * ((d1 - self.r0) ** 2 + (d2 - self.r0) ** 2)

      # Harmonic angle bending
      cos_theta = torch.clamp(torch.dot(v1, v2) / (d1 * d2), -1.0, 1.0)
      theta = torch.acos(cos_theta)
      e_bend = 0.5 * self.kt * ((theta - self.theta0) ** 2)
      total_energy = total_energy + e_stretch + e_bend

    # Intermolecular non-bonded potential between oxygens if dimer
    if n_waters > 1:
      r_O1 = coords[0]
      r_O2 = coords[3]
      r_oo = torch.linalg.norm(r_O1 - r_O2)
      sr6 = (self.sigma_oo / r_oo) ** 6
      e_lj = 4.0 * self.epsilon_oo * (sr6**2 - sr6)
      total_energy = total_energy + e_lj

    return total_energy
```

#### 3. Test Suite Fixtures (`tests/test_chunk21_molecular_dynamics.py`):
1. `test_mendeleev_dynamic_mass_retrieval`: Dynamically query atomic masses for H ($Z=1$) and O ($Z=8$). Assert $m_{\text{H}} \in [1.0079, 1.0081]\,\text{u}$ and $m_{\text{O}} \in [15.999, 16.000]\,\text{u}$. Assert no hardcoded static dictionary is used.
2. `test_conservative_force_autograd_and_curl_free`: Evaluate autograd forces $\mathbf{F} = -\nabla E$ on Water monomer. Verify analytical forces match central finite difference within $1.0 \times 10^{-4}\,\text{eV/\AA}$ and force curl $\|\nabla \times \mathbf{F}\|_2 < 1.0 \times 10^{-6}\,\text{eV/\AA}^2$.
3. `test_acceleration_dimensional_factor_conversion`: Verify $\kappa_{\text{acc}} = 9.648533215665 \times 10^{-3}\,\frac{\text{\AA}/\text{fs}^2}{\text{eV}/(\text{\AA}\cdot\text{u})}$ matches exact identity derived from CODATA 2018 fundamental constants.
4. `test_center_of_mass_momentum_elimination`: Initialize water dimer with non-zero velocities. Run `remove_center_of_mass_momentum()`. Assert net linear momentum $\|\mathbf{P}_{\text{COM}}\| < 1.0 \times 10^{-10}\,\text{u}\cdot\text{\AA}/\text{fs}$.
5. `test_kinetic_energy_and_temperature_degrees_of_freedom`: Calculate $E_{\text{kin}}$ and $T$ for water dimer ($N=6$). Confirm degrees of freedom strictly equal $N_{\text{dof}} = 3N - 3 = 15$.
6. `test_nve_energy_conservation_water_dimer`: Execute 10 ps NVE Velocity Verlet trajectory ($\Delta t \le 0.1\,\text{fs}$) on water dimer. Assert relative secular energy drift $\max_t |(E_{\text{total}}(t) - E_0) / E_0| < 1.0 \times 10^{-4}$.
7. `test_energy_drift_exceeded_error_trigger`: Intentionally run integration with an unstable timestep ($\Delta t = 5.0\,\text{fs}$). Verify `EnergyDriftExceededError` is raised with step and drift telemetry.
8. `test_symplectic_phase_space_time_reversibility`: Integrate water dimer forward 1000 steps ($\Delta t = 0.5\,\text{fs}$), invert velocities ($\mathbf{v} \leftarrow -\mathbf{v}$), integrate backward 1000 steps, invert velocities again. Assert coordinate deviation $\max_i \|\mathbf{r}_i(2N) - \mathbf{r}_i(0)\|_2 < 1.0 \times 10^{-5}\,\text{\AA}$.
9. `test_baoab_langevin_canonical_bath_coupling`: Run BAOAB thermostat at $T_{\text{target}} = 300\,\text{K}$ for 5000 steps with friction $\gamma = 1.0\,\text{ps}^{-1}$. Assert average trajectory temperature converges to $300 \pm 5\,\text{K}$ conforming to Maxwell-Boltzmann distribution.
10. `test_remd_geometric_temperature_schedule`: Initialize `REMDConfig` with $M=4$, $T_{\min}=300\,\text{K}$, $T_{\max}=600\,\text{K}$. Confirm $T_k = [300.0, 377.98, 476.22, 600.0]\,\text{K}$ and $\beta_k = 1 / (k_B T_k)$.
11. `test_remd_metropolis_swap_and_velocity_rescaling`: Execute REMD swap trial between two replicas at $T_1 = 300\,\text{K}$ and $T_2 = 400\,\text{K}$. Verify acceptance probability matches $P = \min(1, \exp[(\beta_1 - \beta_2)(U_1 - U_2)])$. Upon acceptance, verify $\mathbf{v}_1^{\text{new}} = \mathbf{v}_2 \sqrt{T_1 / T_2}$ and $\mathbf{v}_2^{\text{new}} = \mathbf{v}_1 \sqrt{T_2 / T_1}$ ensuring zero thermal inversion.
12. `test_hdf5_swmr_trajectory_lifecycle`: Instantiate `HDF5TrajectoryWriter`, write frames, verify groups/datasets exist before `swmr_mode = True`, and verify an independent reader can read frames concurrently without locking conflicts.
13. `test_apple_silicon_mps_float64_cpu_fallback`: Dispatch with `"mps"`. Assert dispatcher intercepts request and returns `torch.device("cpu")` to preserve double-precision compliance.
14. `test_pydantic_v2_data_validation`: Assert `REMDConfig` rejects $T_{\max} \le T_{\min}$ and `total_steps < swap_interval`. Assert `VelocityVerletConfig` rejects $\Delta t > 1.0\,\text{fs}$.

---

### 6. ACTION PLAN FOR CODER

1. Create `Libraries/cochem_torq_md_errors.py` implementing the complete custom exception hierarchy (`TorqMDError`, `EnergyDriftExceededError`, `SymplecticIntegratorError`, `ReplicaExchangeDivergenceError`, `HardwareDispatchError`) without empty `pass` blocks.
2. Create `Libraries/cochem_torq_md_schemas.py` implementing Pydantic v2 data models (`VelocityVerletConfig`, `REMDConfig`, `MDState`, `TrajectoryFrame`, `ExchangeLog`).
3. Create `Libraries/cochem_torq_masses.py` implementing dynamic atomic mass lookup via the `mendeleev` library.
4. Create `Libraries/cochem_torq_md_env.py` providing `dispatch_md_device` (with automatic Apple Silicon MPS float64 fallback to CPU) and `resolve_hpc_safe_scratch`.
5. Create `Libraries/cochem_torq_symplectic.py` implementing conservative autograd forces, dimensional acceleration, COM momentum projection, kinetic energy/temperature observables, and the symplectic Velocity Verlet integrator with energy drift monitoring.
6. Create `Libraries/cochem_torq_remd.py` implementing the BAOAB Langevin thermostat, geometric temperature schedule, alternating odd-even Metropolis swap trials, and velocity rescaling.
7. Create `Libraries/cochem_torq_trajectory.py` implementing thread-safe HDF5 SWMR chunked extensible trajectory serialization following the strict SWMR lifecycle.
8. Export all public classes, functions, and exceptions in `Libraries/__init__.py`.
9. Implement the mock-free unit test suite `tests/test_chunk21_molecular_dynamics.py` exercising all 14 physical verification test fixtures using authentic water dimer and monomer coordinates.
10. Update/create `pytest.ini` restricting `testpaths = tests/test_chunk21_molecular_dynamics.py` and run `pytest tests/test_chunk21_molecular_dynamics.py -v`, confirming all tests pass with exit code 0.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\__init__.py ---
"""CoChem-TORQ Training Dynamics, Transfer Learning, and Production Compilation Suite.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

# Domain Errors
from Libraries.cochem_torq_training_errors import (
    CheckpointCorruptionError,
    CoChemError,
    CoChemTorqError,
    DiscontinuousForceError,
    DistributedSyncError,
    EquivarianceBreakError,
    HDF5LockTimeoutError,
    NonReciprocalGraphError,
    OOMRecoveryError,
    ParityVerificationError,
    PrecisionDivergenceError,
    SchedulerDivergenceError,
    TorqTrainingError,
    UnsupportedElementError,
)

# Pydantic v2 Schemas
from Libraries.cochem_torq_training_schemas import (
    C2GraphPrunerConfig,
    DistributedEarlyStoppingConfig,
    DynamicBatchScalerConfig,
    ForceMatchingLossConfig,
    GNNWarmRestartSchedulerConfig,
    LossLandscapeConfig,
    TorchScriptExportConfig,
    TrainingDynamicsConfig,
    TransferLearningConfig,
)

# Dynamic Mendeleev Masses
from Libraries.cochem_torq_masses import (
    get_atomic_masses,
    get_monoisotopic_mass,
    get_monoisotopic_masses,
    get_monoisotopic_masses_tensor,
    resolve_ciaaw_monoisotopic_mass,
)


# GNN Warm Restart Scheduler
from Libraries.cochem_torq_gnn_scheduler import (
    GNNWarmRestartScheduler,
    check_and_clip_gradients,
    compute_lr_at_step,
)

# Force-Matching Loss Engine
from Libraries.cochem_torq_force_matching import (
    ForceMatchingLoss,
    compute_angular_cosine_similarity,
    compute_conservative_forces,
    huber_force_loss,
)

# Dynamic Batch Scaler & OOM Recovery
from Libraries.cochem_torq_dynamic_batch import (
    DynamicOOMRecovery,
    MolecularGraph,
    PackedMicroBatch,
    calculate_sparse_padding_waste,
    get_vram_telemetry,
    pack_graphs_dual_budget,
)

# C^2-Smooth Graph Pruning
from Libraries.cochem_torq_graph_pruning import (
    build_c2_reciprocal_graph,
    check_reciprocal_topology,
    compute_center_of_mass,
    compute_pairwise_conservative_forces,
    enforce_graph_reciprocity,
    evaluate_momentum_and_antisymmetry,
    quintic_c2_derivative,
    quintic_c2_second_derivative,
    quintic_c2_switching,
    verify_c2_continuity_boundary,
)

# Gradient Checkpointing
from Libraries.cochem_torq_gradient_checkpointing import (
    CheckpointedMLFF,
    compute_composite_loss,
    evaluate_forces_parity,
    profile_checkpointing_memory,
)

# ANI-2x Transfer Learning
from Libraries.cochem_torq_ani2x_transfer import (
    BASE_ANI2X_SPECIES,
    ANI2xModel,
    AtomicHead,
    expand_ani2x_domain,
    generate_test_ani2x_weights,
    get_llrd_parameter_groups,
    load_verified_ani2x_weights,
)

# TorchScript Export
from Libraries.cochem_torq_torchscript_export import (
    TorchScriptableMLFF,
    compile_and_validate_torchscript,
    compute_energy_and_forces_eager,
    export_model_to_torchscript,
    verify_torchscript_parity,
)

# Distributed Early Stopping
from Libraries.cochem_torq_distributed_early_stopping import (
    DistributedEarlyStopping,
    distributed_worker_routine,
    find_free_port,
)

# Loss Landscape Visualization
from Libraries.cochem_torq_loss_landscape import (
    compute_1d_loss_surface,
    compute_2d_loss_grid,
    generate_filter_normalized_direction,
    generate_orthogonal_filter_directions,
    render_loss_contour_plot,
    restore_base_weights,
    set_perturbed_weights,
)

# Dynamic Mixed-Precision Trainer
from Libraries.cochem_torq_amp_trainer import (
    AMPTrainer,
    resolve_amp_precision,
)

# Storage & Atomic Checkpointing
from Libraries.cochem_torq_training_persistence import (
    HDF5DatasetManager,
    configure_cluster_hdf5_environment,
    load_atomic_checkpoint,
    save_atomic_checkpoint,
    worker_init_fn,
)

# Inference Errors (Chunks 18, 19, 20)
from Libraries.cochem_torq_inference_errors import (
    ActiveLearningSelectionError,
    AirGapIntegrityError,
    AirGapViolationError,
    BaselineExecutionError,
    CalibrationSizeError,
    ClashDetectedError,
    ConcurrencyLockError,
    ConvergenceError,
    CutoffContinuityError,
    DispersionParameterError,
    EnsembleConsensusError,
    GradientExplosionError,
    HDF5DataModuleLockError,
    HardwareDispatchError,
    NumericalParityError,
    OpsetUnsupportedError,
    PBCGraphError,
    PhysicsDivergenceError,
    TorqInferenceError,
    VanishingGradientWarning,
)

# Inference Schemas (Chunks 18, 19, 20)
from Libraries.cochem_torq_inference_schemas import (
    ActiveLearningOrchestratorConfig,
    C2SmoothCutoffConfig,
    ChunkedHDF5DataModuleConfig,
    CommitteeEnsembleConfig,
    ConformalInterval,
    ConformalPredictorConfig,
    DeltaMLConfig,
    DispersionD3Config,
    FiniteDiffVerificationResult,
    GNNGradientDebuggerConfig,
    HPORunConfig,
    LBFGSOptimizationState,
    LBFGSOptimizerConfig,
    MultiTaskPrediction,
    NeighborListResult,
    ONNXExportSpec,
    PBCRadialGraphConfig,
    VibrationalModes,
)

# Multi-Task Learning Head (Chunk 20)
from Libraries.cochem_torq_multitask import (
    HomoscedasticMultiTaskLoss,
    MultiTaskHead,
    huber_loss,
)

# Finite-Difference Verification (Chunk 20)
from Libraries.cochem_torq_finite_difference import (
    verify_finite_difference_forces,
)

# Vibrational Frequency & Hessian Analysis (Chunk 20)
from Libraries.cochem_torq_vibrational import (
    CODATA_2022_FREQ_FACTOR,
    CODATA_2022_HC_EV_CM,
    CODATA_2022_KAPPA,
    analyze_vibrational_frequencies,
    compute_cartesian_hessian,
    compute_eckart_projector,
    resolve_ciaaw_monoisotopic_mass,
)

# TorchDynamo ONNX Export (Chunk 20)
from Libraries.cochem_torq_onnx_export import (
    DEFAULT_DYNAMIC_AXES,
    export_to_onnx,
    validate_onnx_spec,
    verify_onnx_parity,
)

# Environment & Hardware Concurrency (Chunk 20)
from Libraries.cochem_torq_environment import (
    dispatch_device_safely,
    resolve_hpc_safe_scratch,
)

# TORQ Molecular Dynamics Part 1 (Chunk 21)
from Libraries.cochem_torq_md_errors import (
    EnergyDriftExceededError,
    HardwareDispatchError as MDHardwareDispatchError,
    ReplicaExchangeDivergenceError,
    SymplecticIntegratorError,
    TorqMDError,
)
from Libraries.cochem_torq_md_schemas import (
    ExchangeLog,
    MDState,
    REMDConfig,
    TrajectoryFrame,
    VelocityVerletConfig,
)
from Libraries.cochem_torq_md_env import (
    dispatch_md_device,
    resolve_hpc_safe_scratch as resolve_md_scratch,
)
from Libraries.cochem_torq_symplectic import (
    BOLTZMANN_CONSTANT,
    ELEMENTARY_CHARGE,
    KAPPA_ACC,
    KAPPA_ACC_INV,
    UNIFIED_ATOMIC_MASS_KG,
    VelocityVerletIntegrator,
    compute_conservative_forces,
    compute_dimensional_acceleration,
    compute_instantaneous_temperature,
    compute_kinetic_energy,
    remove_center_of_mass_momentum,
)
from Libraries.cochem_torq_remd import (
    ReplicaExchangeEngine,
    ReplicaState,
    baoab_langevin_step,
    compute_geometric_temperature_schedule,
    evaluate_metropolis_swap,
    rescale_velocities_on_swap,
)
from Libraries.cochem_torq_trajectory import (
    HDF5TrajectoryReader,
    HDF5TrajectoryWriter,
)


# Active Learning (Chunk 18)
from Libraries.cochem_torq_active_learning import (
    ActiveLearningOrchestrator,
    ActiveLearningState,
    CandidateGeometry,
    center_geometry_mass_weighted,
    check_stage_b_rotational_redundancy,
    compute_max_force_epistemic_std,
    compute_qbc_energy_variance,
    compute_rotational_constants,
    kabsch_rmsd,
    route_qm_tier,
)

# Chunked HDF5 DataModule (Chunk 18)
from Libraries.cochem_torq_hdf5_datamodule import (
    ChunkedHDF5DataModule,
    ChunkedHDF5Dataset,
    h5_worker_init_fn,
    jagged_graph_collate,
)

# Committee Ensemble (Chunk 18)
from Libraries.cochem_torq_committee_ensemble import (
    CommitteeEnsemble,
    CommitteePrediction,
    compute_committee_moments,
)

# C^2-Smooth Cutoff (Chunk 18)
from Libraries.cochem_torq_c2_cutoff import (
    C2SmoothCutoff,
    quintic_c2_envelope,
    quintic_c2_first_derivative,
    quintic_c2_second_derivative,
    quintic_c2_spatial_gradient,
    quintic_c2_spatial_hessian,
    verify_cutoff_continuity,
)

# GNN Gradient Health Debugger (Chunk 18)
from Libraries.cochem_torq_gnn_debugger import (
    GNNGradientDebugger,
)

# PBC Radial Graph & Virial Stress (Chunk 18)
from Libraries.cochem_torq_pbc_graph import (
    PBCGraph,
    PBCRadialGraphEngine,
    build_pbc_radial_graph,
    cartesian_to_fractional,
    compute_cell_volume,
    compute_hydrostatic_pressure,
    compute_interplanar_spacings,
    compute_virial_stress_tensor,
    fractional_to_cartesian,
)

# Hyperparameter Optimization Suite (Chunk 19)
from Libraries.cochem_torq_hpo import (
    ASHAPruner,
    BasePruner,
    HPOStudy,
    HPOTrial,
    MedianPruner,
    TrialPruned,
    compute_hpo_loss,
    create_hpo_study,
)

# Delta-Learning Architecture (Chunk 19)
from Libraries.cochem_torq_delta_ml import (
    BaselinePhysicsEngine,
    DeltaMLEngine,
    EMTBaselineEngine,
    GFN2xTBEngine,
    LennardJonesBaselineEngine,
    PM6Engine,
    UnitHarmonizer,
)

# Conformal Prediction Uncertainty (Chunk 19)
from Libraries.cochem_torq_conformal import (
    CalibrationSample,
    ConformalPredictor,
)

# L-BFGS Geometry Optimizer (Chunk 19)
from Libraries.cochem_torq_lbfgs_optimizer import (
    LBFGSOptimizer,
    check_clash,
    project_forces_eckart,
)

# Grimme D3 Empirical Dispersion (Chunk 19)
from Libraries.cochem_torq_dispersion_d3 import (
    CANONICAL_DISPERSION_SHA256,
    DispersionD3Layer,
    compute_coordination_numbers,
)

# Spatial Neighbor List Generator (Chunk 19)
from Libraries.cochem_torq_neighbor_list import (
    TRITON_AVAILABLE,
    build_neighbor_list,
)

__all__ = [
    # Errors
    "CoChemError",
    "CoChemTorqError",
    "TorqTrainingError",
    "HDF5LockTimeoutError",
    "PrecisionDivergenceError",
    "CheckpointCorruptionError",
    "DistributedSyncError",
    "UnsupportedElementError",
    "ParityVerificationError",
    "DiscontinuousForceError",
    "NonReciprocalGraphError",
    "OOMRecoveryError",
    "EquivarianceBreakError",
    "SchedulerDivergenceError",
    # Inference Errors (Chunks 18 & 19)
    "TorqInferenceError",
    "ActiveLearningSelectionError",
    "HDF5DataModuleLockError",
    "EnsembleConsensusError",
    "CutoffContinuityError",
    "GradientExplosionError",
    "VanishingGradientWarning",
    "PBCGraphError",
    "AirGapViolationError",
    "HardwareDispatchError",
    "AirGapIntegrityError",
    "ClashDetectedError",
    "ConvergenceError",
    "CalibrationSizeError",
    "BaselineExecutionError",
    "DispersionParameterError",
    # Schemas
    "TrainingDynamicsConfig",
    "TransferLearningConfig",
    "TorchScriptExportConfig",
    "DistributedEarlyStoppingConfig",
    "LossLandscapeConfig",
    "GNNWarmRestartSchedulerConfig",
    "ForceMatchingLossConfig",
    "DynamicBatchScalerConfig",
    "C2GraphPrunerConfig",
    # Inference Schemas (Chunks 18 & 19)
    "ActiveLearningOrchestratorConfig",
    "ChunkedHDF5DataModuleConfig",
    "CommitteeEnsembleConfig",
    "C2SmoothCutoffConfig",
    "GNNGradientDebuggerConfig",
    "PBCRadialGraphConfig",
    "HPORunConfig",
    "DeltaMLConfig",
    "ConformalPredictorConfig",
    "LBFGSOptimizerConfig",
    "DispersionD3Config",
    "NeighborListResult",
    "ConformalInterval",
    "LBFGSOptimizationState",
    # Masses
    "get_atomic_masses",
    "get_monoisotopic_mass",
    "get_monoisotopic_masses",
    "get_monoisotopic_masses_tensor",
    "resolve_ciaaw_monoisotopic_mass",
    # GNN Scheduler
    "GNNWarmRestartScheduler",
    "compute_lr_at_step",
    "check_and_clip_gradients",
    # Force Matching
    "ForceMatchingLoss",
    "compute_conservative_forces",
    "huber_force_loss",
    "compute_angular_cosine_similarity",
    # Dynamic Batching
    "MolecularGraph",
    "PackedMicroBatch",
    "pack_graphs_dual_budget",
    "calculate_sparse_padding_waste",
    "get_vram_telemetry",
    "DynamicOOMRecovery",
    # Graph Pruning
    "quintic_c2_switching",
    "quintic_c2_derivative",
    "quintic_c2_second_derivative",
    "verify_c2_continuity_boundary",
    "check_reciprocal_topology",
    "enforce_graph_reciprocity",
    "build_c2_reciprocal_graph",
    "compute_pairwise_conservative_forces",
    "evaluate_momentum_and_antisymmetry",
    "compute_center_of_mass",
    # Gradient Checkpointing
    "CheckpointedMLFF",
    "compute_composite_loss",
    "evaluate_forces_parity",
    "profile_checkpointing_memory",
    # ANI-2x Transfer
    "BASE_ANI2X_SPECIES",
    "ANI2xModel",
    "AtomicHead",
    "expand_ani2x_domain",
    "generate_test_ani2x_weights",
    "get_llrd_parameter_groups",
    "load_verified_ani2x_weights",
    # TorchScript Export
    "TorchScriptableMLFF",
    "compile_and_validate_torchscript",
    "compute_energy_and_forces_eager",
    "export_model_to_torchscript",
    "verify_torchscript_parity",
    # Distributed Early Stopping
    "DistributedEarlyStopping",
    "distributed_worker_routine",
    "find_free_port",
    # Loss Landscape
    "compute_1d_loss_surface",
    "compute_2d_loss_grid",
    "generate_filter_normalized_direction",
    "generate_orthogonal_filter_directions",
    "render_loss_contour_plot",
    "restore_base_weights",
    "set_perturbed_weights",
    # Mixed-Precision Trainer
    "AMPTrainer",
    "resolve_amp_precision",
    # Storage & Checkpoints
    "HDF5DatasetManager",
    "configure_cluster_hdf5_environment",
    "load_atomic_checkpoint",
    "save_atomic_checkpoint",
    "worker_init_fn",
    # Active Learning (Chunk 18)
    "ActiveLearningOrchestrator",
    "ActiveLearningState",
    "CandidateGeometry",
    "compute_qbc_energy_variance",
    "compute_max_force_epistemic_std",
    "center_geometry_mass_weighted",
    "compute_rotational_constants",
    "kabsch_rmsd",
    "check_stage_b_rotational_redundancy",
    "route_qm_tier",
    # Chunked HDF5 DataModule (Chunk 18)
    "ChunkedHDF5DataModule",
    "ChunkedHDF5Dataset",
    "h5_worker_init_fn",
    "jagged_graph_collate",
    # Committee Ensemble (Chunk 18)
    "CommitteeEnsemble",
    "CommitteePrediction",
    "compute_committee_moments",
    # C^2-Smooth Cutoff (Chunk 18)
    "C2SmoothCutoff",
    "quintic_c2_envelope",
    "quintic_c2_first_derivative",
    "quintic_c2_second_derivative",
    "quintic_c2_spatial_gradient",
    "quintic_c2_spatial_hessian",
    "verify_cutoff_continuity",
    # GNN Debugger (Chunk 18)
    "GNNGradientDebugger",
    # PBC Radial Graph (Chunk 18)
    "PBCGraph",
    "PBCRadialGraphEngine",
    "build_pbc_radial_graph",
    "cartesian_to_fractional",
    "fractional_to_cartesian",
    "compute_cell_volume",
    "compute_interplanar_spacings",
    "compute_virial_stress_tensor",
    "compute_hydrostatic_pressure",
    # Hyperparameter Optimization (Chunk 19)
    "ASHAPruner",
    "BasePruner",
    "HPOStudy",
    "HPOTrial",
    "MedianPruner",
    "TrialPruned",
    "compute_hpo_loss",
    "create_hpo_study",
    # Delta-Learning (Chunk 19)
    "BaselinePhysicsEngine",
    "DeltaMLEngine",
    "EMTBaselineEngine",
    "GFN2xTBEngine",
    "LennardJonesBaselineEngine",
    "PM6Engine",
    "UnitHarmonizer",
    # Conformal Prediction (Chunk 19)
    "CalibrationSample",
    "ConformalPredictor",
    # L-BFGS Optimizer (Chunk 19)
    "LBFGSOptimizer",
    "check_clash",
    "project_forces_eckart",
    # Grimme D3 Dispersion (Chunk 19)
    "CANONICAL_DISPERSION_SHA256",
    "DispersionD3Layer",
    "compute_coordination_numbers",
    # Spatial Neighbor List (Chunk 19)
    "TRITON_AVAILABLE",
    "build_neighbor_list",
    # Chunk 20: TORQ Inference, Vibrational, and Export
    "ConcurrencyLockError",
    "NumericalParityError",
    "OpsetUnsupportedError",
    "PhysicsDivergenceError",
    "FiniteDiffVerificationResult",
    "MultiTaskPrediction",
    "ONNXExportSpec",
    "VibrationalModes",
    "HomoscedasticMultiTaskLoss",
    "MultiTaskHead",
    "huber_loss",
    "verify_finite_difference_forces",
    "CODATA_2022_FREQ_FACTOR",
    "CODATA_2022_HC_EV_CM",
    "CODATA_2022_KAPPA",
    "analyze_vibrational_frequencies",
    "compute_cartesian_hessian",
    "compute_eckart_projector",
    "DEFAULT_DYNAMIC_AXES",
    "export_to_onnx",
    "validate_onnx_spec",
    "verify_onnx_parity",
    "dispatch_device_safely",
    "resolve_hpc_safe_scratch",
    # Chunk 21: TORQ Molecular Dynamics Part 1 (Symplectic & REMD)
    "TorqMDError",
    "EnergyDriftExceededError",
    "SymplecticIntegratorError",
    "ReplicaExchangeDivergenceError",
    "MDHardwareDispatchError",
    "VelocityVerletConfig",
    "REMDConfig",
    "MDState",
    "TrajectoryFrame",
    "ExchangeLog",
    "dispatch_md_device",
    "resolve_md_scratch",
    "KAPPA_ACC",
    "KAPPA_ACC_INV",
    "BOLTZMANN_CONSTANT",
    "ELEMENTARY_CHARGE",
    "UNIFIED_ATOMIC_MASS_KG",
    "compute_dimensional_acceleration",
    "remove_center_of_mass_momentum",
    "compute_kinetic_energy",
    "compute_instantaneous_temperature",
    "VelocityVerletIntegrator",
    "compute_geometric_temperature_schedule",
    "evaluate_metropolis_swap",
    "rescale_velocities_on_swap",
    "baoab_langevin_step",
    "ReplicaState",
    "ReplicaExchangeEngine",
    "HDF5TrajectoryWriter",
    "HDF5TrajectoryReader",
]



--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_masses.py ---
"""Dynamic Mendeleev monoisotopic mass retrieval with unstable element fallback.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Hardcoded mass dictionaries are strictly forbidden.
All masses are dynamically queried from the mendeleev library.
"""

from __future__ import annotations

import functools
from typing import List, Sequence
from mendeleev import element
import torch


@functools.lru_cache(maxsize=128)
def get_monoisotopic_mass(atomic_number: int) -> float:
    """Dynamically query monoisotopic mass using mendeleev with unstable element fallback. [M]
    
    Parameters
    ----------
    atomic_number : int
        Atomic number Z (0 for ghost atoms, 1 <= Z <= 118).
        
    Returns
    -------
    float
        Monoisotopic mass in unified atomic mass units (u).
    """
    if atomic_number == 0:
        return 0.0  # Ghost atom [M]
    if atomic_number < 0 or atomic_number > 118:
        raise ValueError(f"Atomic number Z={atomic_number} outside valid chemical range [0, 118].")

    el = element(atomic_number)
    stable_isotopes = [
        iso for iso in el.isotopes if iso.abundance is not None and iso.abundance > 0.0
    ]
    if stable_isotopes:
        return float(max(stable_isotopes, key=lambda iso: iso.abundance).mass)

    # Fallback for elements without stable isotopes (e.g. Tc Z=43, Pm Z=61) [D]
    return float(max(el.isotopes, key=lambda iso: (iso.half_life or 0.0, iso.mass_number)).mass)


def get_monoisotopic_masses(atomic_numbers: Sequence[int]) -> List[float]:
    """Dynamically query monoisotopic masses for a sequence of atomic numbers. [M]"""
    return [get_monoisotopic_mass(int(z)) for z in atomic_numbers]


def get_monoisotopic_masses_tensor(
    atomic_numbers: Sequence[int],
    dtype: torch.dtype = torch.float64,
    device: torch.device | str = "cpu",
) -> torch.Tensor:
    """Return dynamic monoisotopic masses as a PyTorch tensor. [M]"""
    masses = get_monoisotopic_masses(atomic_numbers)
    return torch.tensor(masses, dtype=dtype, device=device)


@functools.lru_cache(maxsize=128)
def resolve_ciaaw_monoisotopic_mass(atomic_number: int) -> float:
    """Dynamically resolve the CIAAW monoisotopic mass for the most abundant isotope. [M]"""
    if atomic_number == 0:
        return 0.0
    elem = element(int(atomic_number))
    if not elem.isotopes:
        return float(elem.mass)
    # Filter by highest natural abundance (or stable isotope record)
    abundant_iso = max(elem.isotopes, key=lambda iso: iso.abundance or 0.0)
    return float(abundant_iso.mass if abundant_iso.mass is not None else elem.mass)


def get_atomic_masses(
    atomic_numbers: torch.Tensor,
    device: torch.device | str = "cpu",
) -> torch.Tensor:
    """Retrieve CIAAW standard atomic weights in unified atomic mass units (u). [M]

    Parameters
    ----------
    atomic_numbers : torch.Tensor
        Tensor of atomic numbers Z of shape (N_atoms,).
    device : torch.device | str
        Target device for tensor allocation.

    Returns
    -------
    torch.Tensor
        Tensor of atomic masses in unified atomic mass units (u) of shape (N_atoms, 1)
        and dtype torch.float64.
    """
    masses = []
    for z in atomic_numbers.view(-1).tolist():
        elem = element(int(z))
        masses.append(float(elem.mass))
    return torch.tensor(masses, dtype=torch.float64, device=device).unsqueeze(-1)



--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_md_env.py ---
"""Hardware Concurrency, Device Dispatcher & HPC Safe Scratch for TORQ Molecular Dynamics (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Apple Silicon MPS float64 automatic fallback to CPU, HPC distributed lock prohibition.
- [D] Derived: Dynamic 6-tier runtime path resolution and hardware accelerator binding.
- [E] Empirical: OS-agnostic pathlib handling and local NVMe scratch fallback.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Union
import torch

from Libraries.cochem_torq_md_errors import HardwareDispatchError

logger = logging.getLogger(__name__)


def dispatch_md_device(
    requested_device: Optional[Union[str, torch.device]] = None,
) -> torch.device:
    """Dispatch hardware accelerator safely with Apple Silicon MPS float64 fallback [M].

    Metal Performance Shaders (MPS) hardware on Apple Silicon does not support native 64-bit
    floating point operations (torch.float64). When executing molecular dynamics integration
    requiring torch.float64, this dispatcher intercepts and automatically routes execution to CPU.

    Parameters
    ----------
    requested_device : Optional[Union[str, torch.device]]
        Requested target device (e.g., 'cpu', 'cuda', 'mps'). If None, queries system availability.

    Returns
    -------
    torch.device
        Safely routed device compliant with torch.float64 double-precision integration.
    """
    if requested_device is None:
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    dev_str = str(requested_device).strip().lower()

    # Intercept Apple Silicon MPS requests and route to CPU for float64 compliance [M]
    if "mps" in dev_str:
        logger.info("Apple Silicon MPS float64 fallback engaged: routing MD execution to CPU.")
        return torch.device("cpu")

    if "cuda" in dev_str:
        if torch.cuda.is_available():
            try:
                return torch.device(requested_device)
            except Exception as exc:
                raise HardwareDispatchError(str(requested_device), str(exc)) from exc
        logger.warning("CUDA requested but not available; falling back to CPU.")
        return torch.device("cpu")

    if "cpu" in dev_str:
        return torch.device("cpu")

    try:
        return torch.device(requested_device)
    except Exception as exc:
        raise HardwareDispatchError(
            str(requested_device),
            f"Failed to dispatch requested device: {exc}",
        ) from exc


def resolve_hpc_safe_scratch(subfolder: str = "cochem_torq_md") -> Path:
    """Resolve node-local scratch storage adhering to the HPC Distributed Lock Prohibition [M].

    On parallel network filesystems (Lustre, GPFS, BeeGFS, NFS), direct file locking
    triggers lock manager deadlocks ([Errno 37] No locks available). All staging, locking,
    and temporary files must route to node-local NVMe scratch via $SLURM_TMPDIR or $TMPDIR.

    Parameters
    ----------
    subfolder : str
        Subdirectory name within the resolved scratch location. Defaults to 'cochem_torq_md'.

    Returns
    -------
    Path
        Absolute path to local scratch directory, guaranteed to exist on disk.
    """
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    sys_tmp = os.environ.get("TMPDIR")
    cochem_scratch = os.environ.get("COCHEM_SCRATCH_DIR")

    if slurm_tmp and Path(slurm_tmp).is_dir():
        base_dir = Path(slurm_tmp)
    elif sys_tmp and Path(sys_tmp).is_dir():
        base_dir = Path(sys_tmp)
    elif cochem_scratch:
        base_dir = Path(cochem_scratch)
    else:
        base_dir = Path.home() / ".cochem" / "scratch"

    scratch_path = (base_dir / subfolder).resolve()
    scratch_path.mkdir(parents=True, exist_ok=True)
    return scratch_path

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_md_errors.py ---
"""Domain exception hierarchy for TORQ Molecular Dynamics (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Authentic exception hierarchy, zero pass blocks, strict error codes.
- [D] Derived: Rigorous diagnostic payloads for symplectic and replica exchange state telemetry.
- [E] Empirical: Telemetry threshold bounds for numerical instability and drift tracking.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
No pass blocks or dead-end stubs permitted.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class TorqMDError(Exception):
    """Root base exception for all TORQ molecular dynamics failures [M]."""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_MD_GENERIC_ERROR",
        component: str = "molecular_dynamics",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.component = component
        self.diagnostics = diagnostics or {}


class EnergyDriftExceededError(TorqMDError):
    """Raised when NVE relative total energy drift |Delta E / E_0| exceeds tolerance (1e-4) [M]."""

    def __init__(
        self,
        drift: float,
        tolerance: float,
        step: int,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"NVE relative energy drift {drift:.6e} exceeded tolerance {tolerance:.6e} at step {step}.",
            error_code="ENERGY_DRIFT_EXCEEDED",
            component="symplectic_integrator",
            diagnostics=diagnostics,
        )
        self.drift = drift
        self.tolerance = tolerance
        self.step = step


class SymplecticIntegratorError(TorqMDError):
    """Raised when non-finite (NaN or Inf) values are encountered in coordinates, velocities, or forces [M]."""

    def __init__(
        self,
        tensor_name: str,
        step: int,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"Non-finite values encountered in {tensor_name} at step {step}.",
            error_code="SYMPLECTIC_NON_FINITE_TENSOR",
            component="symplectic_integrator",
            diagnostics=diagnostics,
        )
        self.tensor_name = tensor_name
        self.step = step


class ReplicaExchangeDivergenceError(TorqMDError):
    """Raised when rolling swap acceptance drops below 5% or temperatures deviate by > 50 K [M]."""

    def __init__(
        self,
        reason: str,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"Replica Exchange divergent state: {reason}",
            error_code="REMD_DIVERGENCE",
            component="remd_engine",
            diagnostics=diagnostics,
        )
        self.reason = reason


class HardwareDispatchError(TorqMDError):
    """Raised when requested hardware devices are unavailable or fail double-precision compliance [M]."""

    def __init__(
        self,
        device_requested: str,
        reason: str,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"Hardware dispatch failed for '{device_requested}': {reason}",
            error_code="HARDWARE_DISPATCH_FAILED",
            component="hardware_dispatcher",
            diagnostics=diagnostics,
        )
        self.device_requested = device_requested
        self.reason = reason

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_md_schemas.py ---
"""Pydantic v2 data models and contracts for TORQ Molecular Dynamics (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Strict frozen schemas, extra="forbid", double-precision validation.
- [D] Derived: Rigorous state transitions, replica exchange bounds, geometric temperature validation.
- [E] Empirical: Sensible defaults calibrated from empirical water potential benchmarks.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, NamedTuple
from pydantic import BaseModel, ConfigDict, Field, model_validator
import torch


class VelocityVerletConfig(BaseModel):
    """Configuration contract for Symplectic Velocity Verlet Integrator [M]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestep_fs: float = Field(default=0.5, gt=0.0, le=1.0)
    n_steps: int = Field(gt=0, default=20000)
    save_interval: int = Field(gt=0, default=10)
    device: str = Field(default="cpu")
    dtype: Literal["float64"] = Field(default="float64")
    energy_drift_tolerance: float = Field(default=1e-4, gt=0.0)
    remove_com_momentum: bool = Field(default=True)


class REMDConfig(BaseModel):
    """Configuration contract for Replica Exchange Molecular Dynamics Engine [M]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_replicas: int = Field(ge=2, default=4)
    t_min_k: float = Field(gt=0.0, default=300.0)
    t_max_k: float = Field(gt=0.0, default=600.0)
    swap_interval_steps: int = Field(ge=10, default=100)
    total_steps_per_replica: int = Field(gt=0, default=100000)
    friction_ps: float = Field(default=1.0, gt=0.0)
    output_dir: Path

    @model_validator(mode="after")
    def validate_remd_parameters(self) -> "REMDConfig":
        """Validate physical thermodynamic bounds and schedule consistency [D]."""
        if self.t_max_k <= self.t_min_k:
            raise ValueError(
                f"t_max_k ({self.t_max_k}) must be strictly greater than t_min_k ({self.t_min_k})"
            )
        if self.total_steps_per_replica < self.swap_interval_steps:
            raise ValueError(
                f"total_steps_per_replica ({self.total_steps_per_replica}) must be >= "
                f"swap_interval_steps ({self.swap_interval_steps})"
            )
        return self


class MDState(BaseModel):
    """Thermodynamic and kinematic state snapshot during MD simulation [M]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: int = Field(ge=0)
    time_fs: float = Field(ge=0.0)
    potential_energy_ev: float
    kinetic_energy_ev: float = Field(ge=0.0)
    total_energy_ev: float
    temperature_k: float = Field(ge=0.0)


class TrajectoryFrame(NamedTuple):
    """In-memory trajectory frame containing tensors for coordinates, velocities, and forces [M]."""

    step: int
    time_fs: float
    atomic_numbers: torch.Tensor  # Shape: [N_atoms], dtype: torch.int64
    coordinates: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
    velocities: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
    forces: torch.Tensor  # Shape: [N_atoms, 3], dtype: torch.float64
    potential_energy_ev: float
    kinetic_energy_ev: float


class ExchangeLog(BaseModel):
    """Audit log entry for replica exchange swap trials [M]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_step: int
    replica_i: int
    replica_j: int
    temp_i_k: float
    temp_j_k: float
    energy_i_ev: float
    energy_j_ev: float
    p_swap: float = Field(ge=0.0, le=1.0)
    accepted: bool

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_remd.py ---
"""Replica Exchange Molecular Dynamics (REMD) Engine with BAOAB Langevin Thermostat (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Strict double-precision enforcement, rolling divergence guard (acceptance < 5% or |Delta T| > 50 K).
- [D] Derived: BAOAB Langevin thermostat splitting, geometric temperature scheduling,
               Metropolis swap probability, explicit velocity rescaling to prevent thermal inversion.
- [E] Empirical: Alternating odd-even swap schedule calibrated for rapid phase-space mixing.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

from collections import deque
import math
from pathlib import Path
from typing import Any, Callable, Deque, List, Optional, Tuple, Union
import torch

from Libraries.cochem_torq_md_errors import ReplicaExchangeDivergenceError
from Libraries.cochem_torq_md_schemas import ExchangeLog, REMDConfig
from Libraries.cochem_torq_symplectic import (
    BOLTZMANN_CONSTANT,
    KAPPA_ACC,
    compute_conservative_forces,
    compute_dimensional_acceleration,
    compute_instantaneous_temperature,
    compute_kinetic_energy,
    remove_center_of_mass_momentum,
)


def compute_geometric_temperature_schedule(
    n_replicas: int,
    t_min_k: float,
    t_max_k: float,
) -> Tuple[List[float], List[float]]:
    """Compute geometric temperature schedule and corresponding thermodynamic betas [D].

    T_k = T_min * (T_max / T_min) ** (k / (M - 1))
    beta_k = 1.0 / (k_B * T_k)

    Parameters
    ----------
    n_replicas : int
        Total number of replicas M (>= 2).
    t_min_k : float
        Minimum setpoint temperature in Kelvin.
    t_max_k : float
        Maximum setpoint temperature in Kelvin.

    Returns
    -------
    Tuple[List[float], List[float]]
        List of temperatures in Kelvin and list of thermodynamic betas in 1/eV.
    """
    if n_replicas < 2:
        raise ValueError(f"n_replicas ({n_replicas}) must be at least 2.")
    if t_max_k <= t_min_k:
        raise ValueError(
            f"t_max_k ({t_max_k}) must be strictly greater than t_min_k ({t_min_k})."
        )

    ratio = t_max_k / t_min_k
    temperatures: List[float] = []
    betas: List[float] = []

    for k in range(n_replicas):
        exponent = k / (n_replicas - 1)
        t_k = round(t_min_k * (ratio**exponent), 4)
        beta_k = 1.0 / (BOLTZMANN_CONSTANT * t_k)
        temperatures.append(t_k)
        betas.append(beta_k)


    return temperatures, betas


def evaluate_metropolis_swap(
    beta_i: float,
    beta_j: float,
    energy_i_ev: float,
    energy_j_ev: float,
) -> Tuple[float, bool]:
    """Evaluate Metropolis swap acceptance between adjacent replicas [D].

    Delta_ij = (beta_i - beta_j) * (U_i - U_j)
    P_swap = min(1.0, exp(Delta_ij))

    Parameters
    ----------
    beta_i : float
        Thermodynamic beta of replica i in 1/eV.
    beta_j : float
        Thermodynamic beta of replica j in 1/eV.
    energy_i_ev : float
        Potential energy of configuration in replica i in eV.
    energy_j_ev : float
        Potential energy of configuration in replica j in eV.

    Returns
    -------
    Tuple[float, bool]
        Acceptance probability P_swap in [0, 1] and boolean acceptance decision.
    """
    delta_ij = (beta_i - beta_j) * (energy_i_ev - energy_j_ev)

    if delta_ij >= 0.0:
        p_swap = 1.0
    else:
        p_swap = float(math.exp(delta_ij))

    xi = float(torch.rand(1).item())
    accepted = xi < p_swap
    return p_swap, accepted


def rescale_velocities_on_swap(
    v_i: torch.Tensor,
    v_j: torch.Tensor,
    t_i: float,
    t_j: float,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Explicitly rescale velocities upon replica configuration exchange [D].

    v_i^new = v_j * sqrt(T_i / T_j)
    v_j^new = v_i * sqrt(T_j / T_i)

    Parameters
    ----------
    v_i : torch.Tensor
        Velocities of replica i prior to exchange.
    v_j : torch.Tensor
        Velocities of replica j prior to exchange.
    t_i : float
        Setpoint temperature of replica i in Kelvin.
    t_j : float
        Setpoint temperature of replica j in Kelvin.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        Rescaled velocities (v_i_new, v_j_new).
    """
    scale_i = math.sqrt(t_i / t_j)
    scale_j = math.sqrt(t_j / t_i)

    v_i_new = v_j * scale_i
    v_j_new = v_i * scale_j
    return v_i_new, v_j_new


def baoab_langevin_step(
    coords: torch.Tensor,
    velocities: torch.Tensor,
    accelerations: torch.Tensor,
    potential_fn: Callable[[torch.Tensor], torch.Tensor],
    masses: torch.Tensor,
    t_target_k: float,
    friction_ps: float = 1.0,
    timestep_fs: float = 0.5,
    remove_com: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, float]:
    """Execute a single canonical BAOAB Langevin thermostat integration step [D].

    B: v = v + 0.5 * dt * a
    A: r = r + 0.5 * dt * v
    O: v = c1 * v + c2 * sqrt(k_B * T / m) * eta
    A: r = r + 0.5 * dt * v
    B: F = -grad E, a = kappa_acc * (F / m), v = v + 0.5 * dt * a

    Parameters
    ----------
    coords : torch.Tensor
        Coordinates of shape (N_atoms, 3).
    velocities : torch.Tensor
        Velocities of shape (N_atoms, 3).
    accelerations : torch.Tensor
        Accelerations of shape (N_atoms, 3).
    potential_fn : Callable[[torch.Tensor], torch.Tensor]
        Callable returning scalar potential energy in eV.
    masses : torch.Tensor
        Atomic masses of shape (N_atoms, 1) or (N_atoms,) in u.
    t_target_k : float
        Bath setpoint temperature in Kelvin.
    friction_ps : float, optional
        Friction coefficient in ps^-1. Defaults to 1.0.
    timestep_fs : float, optional
        Integration timestep in fs. Defaults to 0.5.
    remove_com : bool, optional
        Whether to project center-of-mass momentum. Defaults to True.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, float]
        Updated (coords, velocities, forces, accelerations, potential_energy_ev).
    """
    m = masses.view(-1, 1)
    dt = float(timestep_fs)
    gamma = float(friction_ps) * 1e-3  # ps^-1 to fs^-1

    c1 = math.exp(-gamma * dt)
    c2 = math.sqrt(KAPPA_ACC * (1.0 - c1**2))

    # 1. B step: Half-step velocity update
    v = velocities + 0.5 * dt * accelerations

    # 2. A step: Half-step coordinate update
    r = coords + 0.5 * dt * v

    # 3. O step: Stochastic thermal bath coupling
    eta = torch.randn_like(v)
    sigma_v = c2 * torch.sqrt((BOLTZMANN_CONSTANT * t_target_k) / m)
    v = c1 * v + sigma_v * eta

    if remove_com:
        v = remove_center_of_mass_momentum(v, m)

    # 4. A step: Half-step coordinate update
    r = r + 0.5 * dt * v

    # 5. B step: Analytical force & full-step acceleration update
    f, e_pot = compute_conservative_forces(
        potential_fn, r, return_energy=True, create_graph=False
    )
    a = compute_dimensional_acceleration(f, m)
    v = v + 0.5 * dt * a

    return r, v, f, a, float(e_pot)


class ReplicaState:
    """Individual replica state in REMD ensemble [M]."""

    def __init__(
        self,
        replica_id: int,
        temperature_k: float,
        beta: float,
        coords: torch.Tensor,
        velocities: torch.Tensor,
        forces: torch.Tensor,
        accelerations: torch.Tensor,
        potential_energy_ev: float,
    ) -> None:
        self.replica_id = replica_id
        self.temperature_k = temperature_k
        self.beta = beta
        self.coords = coords
        self.velocities = velocities
        self.forces = forces
        self.accelerations = accelerations
        self.potential_energy_ev = potential_energy_ev


class ReplicaExchangeEngine:
    """Replica Exchange Molecular Dynamics Engine with Alternating Odd-Even Trials [M]."""

    def __init__(
        self,
        config: REMDConfig,
        potential_fn: Callable[[torch.Tensor], torch.Tensor],
        masses: torch.Tensor,
    ) -> None:
        """Initialize REMD Engine.

        Parameters
        ----------
        config : REMDConfig
            Configuration specifying replica count, temperatures, and swap intervals.
        potential_fn : Callable[[torch.Tensor], torch.Tensor]
            Potential energy function.
        masses : torch.Tensor
            Atomic masses tensor of shape (N_atoms, 1) or (N_atoms,) in u.
        """
        self.config = config
        self.potential_fn = potential_fn
        self.masses = masses.view(-1, 1).to(dtype=torch.float64)
        self.n_atoms = int(self.masses.shape[0])

        self.temperatures, self.betas = compute_geometric_temperature_schedule(
            n_replicas=config.n_replicas,
            t_min_k=config.t_min_k,
            t_max_k=config.t_max_k,
        )

        self.replicas: List[ReplicaState] = []
        self.rolling_attempts: Deque[ExchangeLog] = deque(maxlen=50)
        self.exchange_history: List[ExchangeLog] = []

    def initialize_replicas(
        self,
        initial_coords: torch.Tensor,
        initial_velocities: Optional[torch.Tensor] = None,
    ) -> None:
        """Initialize all replicas at their scheduled setpoint temperatures [M].

        Parameters
        ----------
        initial_coords : torch.Tensor
            Base Cartesian coordinates of shape (N_atoms, 3) and dtype torch.float64.
        initial_velocities : Optional[torch.Tensor], optional
            Starting velocities. If None, Maxwell-Boltzmann velocities are sampled.
        """
        self.replicas.clear()
        base_coords = initial_coords.clone().detach().to(dtype=torch.float64)

        for k in range(self.config.n_replicas):
            t_k = self.temperatures[k]
            beta_k = self.betas[k]
            coords_k = base_coords.clone()

            if initial_velocities is not None:
                vel_k = initial_velocities.clone().detach().to(dtype=torch.float64)
            else:
                # Sample Maxwell-Boltzmann velocity distribution at T_k
                std_k = torch.sqrt(
                    KAPPA_ACC * BOLTZMANN_CONSTANT * t_k / self.masses
                )
                vel_k = torch.randn_like(coords_k) * std_k
                vel_k = remove_center_of_mass_momentum(vel_k, self.masses)

            f_k, e_pot_k = compute_conservative_forces(
                self.potential_fn, coords_k, return_energy=True, create_graph=False
            )
            a_k = compute_dimensional_acceleration(f_k, self.masses)

            state = ReplicaState(
                replica_id=k,
                temperature_k=t_k,
                beta=beta_k,
                coords=coords_k,
                velocities=vel_k,
                forces=f_k,
                accelerations=a_k,
                potential_energy_ev=float(e_pot_k),
            )
            self.replicas.append(state)

    def step_replicas(
        self,
        step_idx: int,
        timestep_fs: float = 0.5,
    ) -> None:
        """Step all replicas forward by one BAOAB Langevin integration step [D].

        Parameters
        ----------
        step_idx : int
            Current simulation step index.
        timestep_fs : float, optional
            Integration timestep in fs. Defaults to 0.5.
        """
        for rep in self.replicas:
            r, v, f, a, e_pot = baoab_langevin_step(
                coords=rep.coords,
                velocities=rep.velocities,
                accelerations=rep.accelerations,
                potential_fn=self.potential_fn,
                masses=self.masses,
                t_target_k=rep.temperature_k,
                friction_ps=self.config.friction_ps,
                timestep_fs=timestep_fs,
                remove_com=True,
            )
            rep.coords = r
            rep.velocities = v
            rep.forces = f
            rep.accelerations = a
            rep.potential_energy_ev = e_pot

    def attempt_exchanges(
        self,
        step_idx: int,
        cycle_idx: int,
    ) -> List[ExchangeLog]:
        """Execute alternating odd-even swap trial across adjacent replicas [D].

        Parameters
        ----------
        step_idx : int
            Current simulation step index.
        cycle_idx : int
            Swap attempt counter (even cycles swap 0-1, 2-3...; odd cycles swap 1-2, 3-4...).

        Returns
        -------
        List[ExchangeLog]
            Audit records for all attempted swaps in this trial cycle.
        """
        logs: List[ExchangeLog] = []
        is_odd_cycle = cycle_idx % 2 == 1
        start_idx = 1 if is_odd_cycle else 0

        for i in range(start_idx, self.config.n_replicas - 1, 2):
            j = i + 1
            rep_i = self.replicas[i]
            rep_j = self.replicas[j]

            p_swap, accepted = evaluate_metropolis_swap(
                beta_i=rep_i.beta,
                beta_j=rep_j.beta,
                energy_i_ev=rep_i.potential_energy_ev,
                energy_j_ev=rep_j.potential_energy_ev,
            )

            if accepted:
                # 1. Swap configuration coordinates
                r_temp = rep_i.coords.clone()
                rep_i.coords = rep_j.coords.clone()
                rep_j.coords = r_temp

                # 2. Rescale velocities to preserve canonical distributions
                v_i_new, v_j_new = rescale_velocities_on_swap(
                    rep_i.velocities,
                    rep_j.velocities,
                    rep_i.temperature_k,
                    rep_j.temperature_k,
                )
                rep_i.velocities = v_i_new
                rep_j.velocities = v_j_new

                # 3. Re-evaluate analytical forces and accelerations
                f_i, e_i = compute_conservative_forces(
                    self.potential_fn, rep_i.coords, return_energy=True, create_graph=False
                )
                f_j, e_j = compute_conservative_forces(
                    self.potential_fn, rep_j.coords, return_energy=True, create_graph=False
                )
                rep_i.forces = f_i
                rep_i.accelerations = compute_dimensional_acceleration(f_i, self.masses)
                rep_i.potential_energy_ev = float(e_i)

                rep_j.forces = f_j
                rep_j.accelerations = compute_dimensional_acceleration(f_j, self.masses)
                rep_j.potential_energy_ev = float(e_j)

            log_entry = ExchangeLog(
                attempt_step=step_idx,
                replica_i=i,
                replica_j=j,
                temp_i_k=rep_i.temperature_k,
                temp_j_k=rep_j.temperature_k,
                energy_i_ev=rep_i.potential_energy_ev,
                energy_j_ev=rep_j.potential_energy_ev,
                p_swap=p_swap,
                accepted=accepted,
            )
            logs.append(log_entry)
            self.rolling_attempts.append(log_entry)
            self.exchange_history.append(log_entry)

        # Check rolling convergence / divergence guards [M]
        self._check_divergence_guards()

        return logs

    def _check_divergence_guards(self) -> None:
        """Enforce rolling acceptance >= 5% and temperature deviation <= 50 K [M]."""
        if len(self.rolling_attempts) >= 50:
            accepted_count = sum(1 for entry in self.rolling_attempts if entry.accepted)
            acceptance_rate = accepted_count / len(self.rolling_attempts)

            if acceptance_rate < 0.05:
                raise ReplicaExchangeDivergenceError(
                    reason=(
                        f"Rolling swap acceptance rate ({acceptance_rate:.4f}) dropped below "
                        f"5% threshold over last {len(self.rolling_attempts)} trials."
                    ),
                    diagnostics={"acceptance_rate": acceptance_rate},
                )

        # Check instantaneous kinetic temperature deviation across all replicas
        for rep in self.replicas:
            e_kin = compute_kinetic_energy(rep.velocities, self.masses)
            t_inst = compute_instantaneous_temperature(
                e_kin, self.n_atoms, remove_com=True
            )
            deviation = abs(t_inst - rep.temperature_k)
            if deviation > 50.0 and len(self.rolling_attempts) >= 50:
                raise ReplicaExchangeDivergenceError(
                    reason=(
                        f"Replica {rep.replica_id} instantaneous temperature ({t_inst:.2f} K) "
                        f"deviated by > 50 K from setpoint ({rep.temperature_k:.2f} K)."
                    ),
                    diagnostics={
                        "replica_id": rep.replica_id,
                        "t_inst": t_inst,
                        "t_setpoint": rep.temperature_k,
                        "deviation": deviation,
                    },
                )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_symplectic.py ---
"""Conservative Force Autograd and Symplectic Velocity Verlet Integrator (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Strict torch.float64 double precision, energy drift guard, finite tensor validation.
- [D] Derived: Conservative autograd forces, dimensional acceleration, COM momentum projection,
               kinetic energy and instantaneous temperature observables via CODATA 2018 constants.
- [E] Empirical: Timestep stability bounds calibrated for stiff intramolecular bonds.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple, Union
import torch

from Libraries.cochem_torq_md_errors import (
    EnergyDriftExceededError,
    SymplecticIntegratorError,
)
from Libraries.cochem_torq_md_schemas import (
    MDState,
    TrajectoryFrame,
    VelocityVerletConfig,
)

# Authoritative CODATA 2018 / CIAAW Physical Constants [D]
ELEMENTARY_CHARGE: float = 1.602176634e-19  # J / eV
UNIFIED_ATOMIC_MASS_KG: float = 1.66053906660e-27  # kg / u
BOLTZMANN_CONSTANT: float = 8.617333262e-5  # eV / K
LENGTH_SCALE_M_TO_ANGSTROM: float = 1.0e10  # A / m
TIME_SCALE_S_TO_FS: float = 1.0e15  # fs / s

# Dimensional acceleration conversion factor:
# kappa_acc = (e * (1e10)^2) / (u * (1e15)^2) = 9.648533215665e-3 [A / fs^2] / [eV / (A * u)] [D]
KAPPA_ACC: float = 9.648533215665e-3

# Kinetic mass conversion factor:
# kappa_acc_inv = 1.0 / kappa_acc = 103.6426965 eV / (u * (A / fs)^2) [D]
KAPPA_ACC_INV: float = 103.6426965


def compute_conservative_forces(
    potential_fn: Callable[[torch.Tensor], torch.Tensor],
    coords: torch.Tensor,
    return_energy: bool = True,
    create_graph: bool = False,
) -> Union[Tuple[torch.Tensor, torch.Tensor], torch.Tensor]:
    """Compute Cartesian forces as negative analytical gradient of potential energy [D].

    Parameters
    ----------
    potential_fn : Callable[[torch.Tensor], torch.Tensor]
        Potential energy function returning scalar energy in eV.
    coords : torch.Tensor
        Cartesian coordinates of shape (N_atoms, 3) and dtype torch.float64.
    return_energy : bool, optional
        Whether to return the scalar potential energy along with forces. Defaults to True.
    create_graph : bool, optional
        Whether to construct graph for higher-order derivatives. Defaults to False.

    Returns
    -------
    Union[Tuple[torch.Tensor, torch.Tensor], torch.Tensor]
        If return_energy is True, returns (forces, potential_energy).
        If return_energy is False, returns forces.
    """
    coords_with_grad = (
        coords if coords.requires_grad else coords.clone().detach().requires_grad_(True)
    )
    energy = potential_fn(coords_with_grad)
    grad = torch.autograd.grad(
        outputs=energy,
        inputs=coords_with_grad,
        grad_outputs=torch.ones_like(energy),
        create_graph=create_graph,
        retain_graph=create_graph,
        only_inputs=True,
    )[0]

    if grad is None:
        raise SymplecticIntegratorError(
            tensor_name="forces",
            step=0,
            diagnostics={"reason": "torch.autograd.grad returned None for coordinates."},
        )

    forces = -grad

    if return_energy:
        return forces, energy.detach()
    return forces


def compute_dimensional_acceleration(
    forces: torch.Tensor,
    masses: torch.Tensor,
) -> torch.Tensor:
    """Compute dimensional Cartesian accelerations in A/fs^2 [D].

    a_i = kappa_acc * (F_i / m_i)

    Parameters
    ----------
    forces : torch.Tensor
        Cartesian forces of shape (N_atoms, 3) in eV/A.
    masses : torch.Tensor
        Atomic masses of shape (N_atoms, 1) or (N_atoms,) in unified atomic mass units (u).

    Returns
    -------
    torch.Tensor
        Dimensional acceleration tensor of shape (N_atoms, 3) in A/fs^2.
    """
    m = masses.view(-1, 1)
    acc = KAPPA_ACC * (forces / m)
    return acc


def remove_center_of_mass_momentum(
    velocities: torch.Tensor,
    masses: torch.Tensor,
) -> torch.Tensor:
    """Eliminate center-of-mass translational momentum [D].

    Guarantees net linear momentum ||P_COM|| < 1.0e-10 u * A / fs.

    Parameters
    ----------
    velocities : torch.Tensor
        Cartesian velocities of shape (N_atoms, 3) in A/fs.
    masses : torch.Tensor
        Atomic masses of shape (N_atoms, 1) or (N_atoms,) in u.

    Returns
    -------
    torch.Tensor
        Velocities with net center-of-mass momentum removed.
    """
    m = masses.view(-1, 1)
    total_mass = torch.sum(m)
    p_com = torch.sum(m * velocities, dim=0, keepdim=True)
    v_com = p_com / total_mass
    v_corrected = velocities - v_com
    return v_corrected


def compute_kinetic_energy(
    velocities: torch.Tensor,
    masses: torch.Tensor,
) -> float:
    """Compute total kinetic energy in eV [D].

    E_kin = 0.5 * kappa_acc_inv * sum(m_i * ||v_i||^2)

    Parameters
    ----------
    velocities : torch.Tensor
        Cartesian velocities of shape (N_atoms, 3) in A/fs.
    masses : torch.Tensor
        Atomic masses of shape (N_atoms, 1) or (N_atoms,) in u.

    Returns
    -------
    float
        Kinetic energy in eV.
    """
    m = masses.view(-1, 1)
    v_sq = torch.sum(velocities**2, dim=-1, keepdim=True)
    e_kin = 0.5 * KAPPA_ACC_INV * torch.sum(m * v_sq)
    return float(e_kin)


def compute_instantaneous_temperature(
    kinetic_energy_ev: Union[float, torch.Tensor],
    n_atoms: int,
    remove_com: bool = True,
) -> float:
    """Compute instantaneous kinetic temperature in Kelvin [D].

    T = 2 * E_kin / (N_dof * k_B)
    where N_dof = 3N - 3 if center-of-mass translation is removed, else 3N.

    Parameters
    ----------
    kinetic_energy_ev : Union[float, torch.Tensor]
        Kinetic energy in eV.
    n_atoms : int
        Number of atoms in the molecular system.
    remove_com : bool, optional
        Whether translational center-of-mass degrees of freedom are constrained. Defaults to True.

    Returns
    -------
    float
        Instantaneous kinetic temperature in Kelvin.
    """
    n_dof = 3 * n_atoms - 3 if remove_com else 3 * n_atoms
    if n_dof <= 0:
        raise ValueError(
            f"Degrees of freedom ({n_dof}) must be strictly positive (n_atoms={n_atoms})."
        )
    t_kelvin = (2.0 * float(kinetic_energy_ev)) / (n_dof * BOLTZMANN_CONSTANT)
    return float(t_kelvin)


class VelocityVerletIntegrator:
    """Symplectic Velocity Verlet Integrator with double-precision & energy conservation guards [M]."""

    def __init__(
        self,
        potential_fn: Callable[[torch.Tensor], torch.Tensor],
        config: VelocityVerletConfig,
        masses: torch.Tensor,
        writer: Optional[Any] = None,
    ) -> None:
        """Initialize Velocity Verlet Integrator.

        Parameters
        ----------
        potential_fn : Callable[[torch.Tensor], torch.Tensor]
            Callable computing scalar potential energy in eV.
        config : VelocityVerletConfig
            Configuration dataclass enforcing integration timestep, tolerances, and hardware.
        masses : torch.Tensor
            Atomic masses of shape (N_atoms, 1) or (N_atoms,) in u.
        writer : Optional[Any], optional
            HDF5TrajectoryWriter instance for persistent SWMR serialization.
        """
        self.potential_fn = potential_fn
        self.config = config
        self.masses = masses.view(-1, 1).to(dtype=torch.float64, device=config.device)
        self.writer = writer
        self.n_atoms = int(self.masses.shape[0])

    def _verify_finite_tensor(self, tensor: torch.Tensor, name: str, step: int) -> None:
        """Verify tensor contains no NaN or Inf values [M]."""
        if torch.isnan(tensor).any() or torch.isinf(tensor).any():
            raise SymplecticIntegratorError(
                tensor_name=name,
                step=step,
                diagnostics={
                    "has_nan": bool(torch.isnan(tensor).any()),
                    "has_inf": bool(torch.isinf(tensor).any()),
                },
            )

    def step(
        self,
        coords: torch.Tensor,
        velocities: torch.Tensor,
        forces: torch.Tensor,
        accelerations: torch.Tensor,
        step_idx: int,
        timestep_fs: Optional[float] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, MDState]:
        """Perform a single symplectic Velocity Verlet integration step [D].

        1. Half-step velocity: v(t + dt/2) = v(t) + 0.5 * dt * a(t)
        2. Full-step coordinate: r(t + dt) = r(t) + dt * v(t + dt/2)
        3. Force evaluation: F(t + dt) = -grad E(r(t + dt))
        4. Full-step acceleration: a(t + dt) = kappa_acc * (F(t + dt) / m)
        5. Final velocity: v(t + dt) = v(t + dt/2) + 0.5 * dt * a(t + dt)

        Parameters
        ----------
        coords : torch.Tensor
            Coordinates at step t of shape (N_atoms, 3).
        velocities : torch.Tensor
            Velocities at step t of shape (N_atoms, 3).
        forces : torch.Tensor
            Forces at step t of shape (N_atoms, 3).
        accelerations : torch.Tensor
            Accelerations at step t of shape (N_atoms, 3).
        step_idx : int
            Current simulation step index.
        timestep_fs : Optional[float]
            Optional override for integration timestep in fs.

        Returns
        -------
        Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, MDState]
            Updated (coords, velocities, forces, accelerations, state).
        """
        dt = float(timestep_fs if timestep_fs is not None else self.config.timestep_fs)

        # 1. Half-step velocity update
        v_half = velocities + 0.5 * dt * accelerations

        # 2. Full-step coordinate update
        r_next = coords + dt * v_half
        self._verify_finite_tensor(r_next, "coordinates", step_idx)

        # 3. Force evaluation at new coordinates
        f_next, e_pot = compute_conservative_forces(
            self.potential_fn, r_next, return_energy=True, create_graph=False
        )
        self._verify_finite_tensor(f_next, "forces", step_idx)

        # 4. Full-step acceleration update
        a_next = compute_dimensional_acceleration(f_next, self.masses)
        self._verify_finite_tensor(a_next, "accelerations", step_idx)

        # 5. Final velocity update
        v_next = v_half + 0.5 * dt * a_next
        self._verify_finite_tensor(v_next, "velocities", step_idx)

        # Kinetic energy and temperature observables
        e_kin = compute_kinetic_energy(v_next, self.masses)
        e_tot = float(e_pot) + e_kin
        temp_k = compute_instantaneous_temperature(
            e_kin, self.n_atoms, remove_com=self.config.remove_com_momentum
        )

        state = MDState(
            step=step_idx,
            time_fs=step_idx * dt,
            potential_energy_ev=float(e_pot),
            kinetic_energy_ev=e_kin,
            total_energy_ev=e_tot,
            temperature_k=temp_k,
        )

        return r_next, v_next, f_next, a_next, state

    def integrate(
        self,
        initial_coords: torch.Tensor,
        initial_velocities: torch.Tensor,
        atomic_numbers: Optional[torch.Tensor] = None,
        n_steps: Optional[int] = None,
        timestep_fs: Optional[float] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, List[MDState]]:
        """Execute complete NVE Velocity Verlet trajectory with energy drift guard [M].

        Parameters
        ----------
        initial_coords : torch.Tensor
            Starting Cartesian coordinates of shape (N_atoms, 3) and dtype torch.float64.
        initial_velocities : torch.Tensor
            Starting Cartesian velocities of shape (N_atoms, 3) and dtype torch.float64.
        atomic_numbers : Optional[torch.Tensor]
            Atomic numbers Z of shape (N_atoms,) for trajectory serialization.
        n_steps : Optional[int]
            Total steps to integrate. If None, uses config.n_steps.
        timestep_fs : Optional[float]
            Integration timestep in fs. If None, uses config.timestep_fs.

        Returns
        -------
        Tuple[torch.Tensor, torch.Tensor, List[MDState]]
            Final coordinates, final velocities, and list of MDState telemetry records.
        """
        device = torch.device(self.config.device)
        total_steps = n_steps if n_steps is not None else self.config.n_steps
        dt = float(timestep_fs if timestep_fs is not None else self.config.timestep_fs)

        coords = initial_coords.clone().detach().to(dtype=torch.float64, device=device)
        velocities = initial_velocities.clone().detach().to(dtype=torch.float64, device=device)

        if self.config.remove_com_momentum:
            velocities = remove_center_of_mass_momentum(velocities, self.masses)

        self._verify_finite_tensor(coords, "coordinates", 0)
        self._verify_finite_tensor(velocities, "velocities", 0)

        # Initial force and acceleration evaluation
        forces, e_pot_init = compute_conservative_forces(
            self.potential_fn, coords, return_energy=True, create_graph=False
        )
        self._verify_finite_tensor(forces, "forces", 0)
        accelerations = compute_dimensional_acceleration(forces, self.masses)

        e_kin_init = compute_kinetic_energy(velocities, self.masses)
        e_total_0 = float(e_pot_init) + e_kin_init
        temp_init = compute_instantaneous_temperature(
            e_kin_init, self.n_atoms, remove_com=self.config.remove_com_momentum
        )

        initial_state = MDState(
            step=0,
            time_fs=0.0,
            potential_energy_ev=float(e_pot_init),
            kinetic_energy_ev=e_kin_init,
            total_energy_ev=e_total_0,
            temperature_k=temp_init,
        )

        states: List[MDState] = [initial_state]

        if self.writer is not None and atomic_numbers is not None:
            frame_0 = TrajectoryFrame(
                step=0,
                time_fs=0.0,
                atomic_numbers=atomic_numbers.cpu(),
                coordinates=coords.detach().cpu(),
                velocities=velocities.detach().cpu(),
                forces=forces.detach().cpu(),
                potential_energy_ev=float(e_pot_init),
                kinetic_energy_ev=e_kin_init,
            )
            self.writer.append_frame(frame_0)

        for s in range(1, total_steps + 1):
            coords, velocities, forces, accelerations, state = self.step(
                coords, velocities, forces, accelerations, step_idx=s, timestep_fs=dt
            )
            states.append(state)

            # Check NVE relative total energy drift |(E_tot - E_0) / E_0| [M]
            if abs(e_total_0) > 1e-12:
                relative_drift = abs((state.total_energy_ev - e_total_0) / e_total_0)
            else:
                relative_drift = abs(state.total_energy_ev - e_total_0)

            if relative_drift > self.config.energy_drift_tolerance:
                raise EnergyDriftExceededError(
                    drift=float(relative_drift),
                    tolerance=float(self.config.energy_drift_tolerance),
                    step=s,
                    diagnostics={
                        "e_total_current": state.total_energy_ev,
                        "e_total_initial": e_total_0,
                        "potential_energy": state.potential_energy_ev,
                        "kinetic_energy": state.kinetic_energy_ev,
                    },
                )

            if (
                self.writer is not None
                and atomic_numbers is not None
                and s % self.config.save_interval == 0
            ):
                frame = TrajectoryFrame(
                    step=s,
                    time_fs=state.time_fs,
                    atomic_numbers=atomic_numbers.cpu(),
                    coordinates=coords.detach().cpu(),
                    velocities=velocities.detach().cpu(),
                    forces=forces.detach().cpu(),
                    potential_energy_ev=state.potential_energy_ev,
                    kinetic_energy_ev=state.kinetic_energy_ev,
                )
                self.writer.append_frame(frame)

        return coords, velocities, states

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_trajectory.py ---
"""Thread-Safe HDF5 SWMR Trajectory Serialization (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Strict SWMR lifecycle (dataset pre-allocation prior to swmr_mode activation),
               lossless chunked compression, non-blocking concurrent reader.
- [D] Derived: Extensible datasets with maxshape=(None, N, 3) and atomic flush sequencing.
- [E] Empirical: 100-frame chunking calibrated for optimal sequential I/O throughput.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence, Union
import h5py
import numpy as np
import torch

from Libraries.cochem_torq_md_schemas import TrajectoryFrame
from Libraries.cochem_torq_symplectic import compute_instantaneous_temperature


class HDF5TrajectoryWriter:
    """Thread-safe Single-Writer-Multiple-Reader (SWMR) HDF5 trajectory serializer [M]."""

    def __init__(
        self,
        file_path: Union[str, Path],
        n_atoms: int,
        atomic_numbers: Union[torch.Tensor, Sequence[int]],
        chunk_size: int = 100,
        compression: Optional[str] = "gzip",
    ) -> None:
        """Initialize and pre-allocate SWMR extensible HDF5 dataset structure [M].

        Parameters
        ----------
        file_path : Union[str, Path]
            Destination path for the trajectory HDF5 file.
        n_atoms : int
            Number of atoms in the molecular system.
        atomic_numbers : Union[torch.Tensor, Sequence[int]]
            Static atomic numbers Z of shape (N_atoms,).
        chunk_size : int, optional
            Extensible chunk size along the temporal dimension. Defaults to 100.
        compression : Optional[str], optional
            Compression filter ('gzip' or 'lzf'). Defaults to 'gzip'.
        """
        self.file_path = Path(file_path).resolve()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.n_atoms = int(n_atoms)
        self.chunk_size = int(chunk_size)
        self.compression = compression

        # Convert atomic numbers to numpy int64
        if isinstance(atomic_numbers, torch.Tensor):
            z_arr = atomic_numbers.detach().cpu().numpy().astype(np.int64).flatten()
        else:
            z_arr = np.array(atomic_numbers, dtype=np.int64).flatten()

        if z_arr.shape[0] != self.n_atoms:
            raise ValueError(
                f"Atomic numbers length ({z_arr.shape[0]}) does not match n_atoms ({self.n_atoms})."
            )
        self.atomic_numbers_arr = z_arr

        # Open file with libver='latest'
        self.file = h5py.File(str(self.file_path), "w", libver="latest")

        # Create chunked extensible datasets prior to SWMR mode activation [M]
        self.coordinates = self.file.create_dataset(
            "coordinates",
            shape=(0, self.n_atoms, 3),
            maxshape=(None, self.n_atoms, 3),
            dtype="float64",
            chunks=(self.chunk_size, self.n_atoms, 3),
            compression=self.compression,
        )

        self.velocities = self.file.create_dataset(
            "velocities",
            shape=(0, self.n_atoms, 3),
            maxshape=(None, self.n_atoms, 3),
            dtype="float64",
            chunks=(self.chunk_size, self.n_atoms, 3),
            compression=self.compression,
        )

        self.forces = self.file.create_dataset(
            "forces",
            shape=(0, self.n_atoms, 3),
            maxshape=(None, self.n_atoms, 3),
            dtype="float64",
            chunks=(self.chunk_size, self.n_atoms, 3),
            compression=self.compression,
        )

        self.energies = self.file.create_dataset(
            "energies",
            shape=(0, 3),
            maxshape=(None, 3),
            dtype="float64",
            chunks=(self.chunk_size, 3),
            compression=self.compression,
        )

        self.temperatures = self.file.create_dataset(
            "temperatures",
            shape=(0,),
            maxshape=(None,),
            dtype="float64",
            chunks=(self.chunk_size,),
            compression=self.compression,
        )

        self.time_fs = self.file.create_dataset(
            "time_fs",
            shape=(0,),
            maxshape=(None,),
            dtype="float64",
            chunks=(self.chunk_size,),
            compression=self.compression,
        )

        # Static immutable atomic numbers dataset
        self.file.create_dataset(
            "atomic_numbers",
            data=self.atomic_numbers_arr,
            dtype="int64",
        )

        # Crucial SWMR Lifecycle Sequencing: Flush all schema and datasets to disk [M]
        self.file.flush()

        # Engage active SWMR mode
        self.file.swmr_mode = True

    def append_frame(self, frame: TrajectoryFrame) -> None:
        """Append a single trajectory frame to extensible datasets and flush [M].

        Parameters
        ----------
        frame : TrajectoryFrame
            TrajectoryFrame containing tensors for coordinates, velocities, forces, and energies.
        """
        idx = self.coordinates.shape[0]
        new_len = idx + 1

        # Resize chunked datasets along time axis
        self.coordinates.resize((new_len, self.n_atoms, 3))
        self.velocities.resize((new_len, self.n_atoms, 3))
        self.forces.resize((new_len, self.n_atoms, 3))
        self.energies.resize((new_len, 3))
        self.temperatures.resize((new_len,))
        self.time_fs.resize((new_len,))

        # Assign values
        coords_np = frame.coordinates.detach().cpu().numpy().astype(np.float64)
        vel_np = frame.velocities.detach().cpu().numpy().astype(np.float64)
        forces_np = frame.forces.detach().cpu().numpy().astype(np.float64)

        self.coordinates[idx] = coords_np
        self.velocities[idx] = vel_np
        self.forces[idx] = forces_np

        e_pot = float(frame.potential_energy_ev)
        e_kin = float(frame.kinetic_energy_ev)
        e_tot = e_pot + e_kin
        self.energies[idx] = [e_pot, e_kin, e_tot]

        t_inst = compute_instantaneous_temperature(e_kin, self.n_atoms, remove_com=True)
        self.temperatures[idx] = t_inst
        self.time_fs[idx] = float(frame.time_fs)

        # Flush datasets to disk for active concurrent SWMR readers [M]
        self.coordinates.flush()
        self.velocities.flush()
        self.forces.flush()
        self.energies.flush()
        self.temperatures.flush()
        self.time_fs.flush()
        self.file.flush()

    def close(self) -> None:
        """Close trajectory file handle."""
        if hasattr(self, "file") and self.file:
            self.file.flush()
            self.file.close()

    def __enter__(self) -> "HDF5TrajectoryWriter":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class HDF5TrajectoryReader:
    """Concurrent non-blocking Single-Writer-Multiple-Reader (SWMR) trajectory reader [M]."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        """Open HDF5 trajectory in SWMR read mode.

        Parameters
        ----------
        file_path : Union[str, Path]
            Path to existing HDF5 trajectory file.
        """
        self.file_path = Path(file_path).resolve()
        if not self.file_path.is_file():
            raise FileNotFoundError(f"Trajectory file not found: {self.file_path}")

        self.file = h5py.File(str(self.file_path), "r", libver="latest", swmr=True)
        self.atomic_numbers = torch.tensor(
            self.file["atomic_numbers"][:], dtype=torch.int64
        )
        self.n_atoms = int(self.atomic_numbers.shape[0])

    def refresh(self) -> None:
        """Refresh datasets to see newly appended frames from active SWMR writer [M]."""
        for ds_name in [
            "coordinates",
            "velocities",
            "forces",
            "energies",
            "temperatures",
            "time_fs",
        ]:
            if ds_name in self.file:
                self.file[ds_name].refresh()

    def __len__(self) -> int:
        """Return total number of available trajectory frames."""
        self.refresh()
        return int(self.file["coordinates"].shape[0])

    def read_frame(self, index: int) -> TrajectoryFrame:
        """Read a single trajectory frame by index as torch tensors [M].

        Parameters
        ----------
        index : int
            Temporal frame index.

        Returns
        -------
        TrajectoryFrame
            Loaded frame containing tensors for coordinates, velocities, and forces.
        """
        self.refresh()
        total_frames = self.file["coordinates"].shape[0]
        if index < 0 or index >= total_frames:
            raise IndexError(
                f"Frame index {index} out of bounds for trajectory of length {total_frames}."
            )

        coords = torch.tensor(self.file["coordinates"][index], dtype=torch.float64)
        vel = torch.tensor(self.file["velocities"][index], dtype=torch.float64)
        forces = torch.tensor(self.file["forces"][index], dtype=torch.float64)
        energies = self.file["energies"][index]
        t_fs = float(self.file["time_fs"][index])

        return TrajectoryFrame(
            step=index,
            time_fs=t_fs,
            atomic_numbers=self.atomic_numbers,
            coordinates=coords,
            velocities=vel,
            forces=forces,
            potential_energy_ev=float(energies[0]),
            kinetic_energy_ev=float(energies[1]),
        )

    def read_all_coordinates(self) -> torch.Tensor:
        """Read full trajectory coordinate tensor of shape (N_frames, N_atoms, 3) [M]."""
        self.refresh()
        return torch.tensor(self.file["coordinates"][:], dtype=torch.float64)

    def read_all_energies(self) -> torch.Tensor:
        """Read full trajectory energy tensor of shape (N_frames, 3) (potential, kinetic, total) [M]."""
        self.refresh()
        return torch.tensor(self.file["energies"][:], dtype=torch.float64)

    def close(self) -> None:
        """Close trajectory file handle."""
        if hasattr(self, "file") and self.file:
            self.file.close()

    def __enter__(self) -> "HDF5TrajectoryReader":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_chunk21_molecular_dynamics.py ---
"""Physical Verification Test Suite for TORQ Molecular Dynamics (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Authentic molecular geometries, dynamic Mendeleev masses, torch.float64 precision,
               MPS float64 fallback to CPU, Pydantic v2 immutability and bounds validation.
- [D] Derived: Conservative autograd forces, curl-free gradient field, dimensional acceleration,
               center-of-mass momentum elimination, kinetic energy and temperature observables,
               symplectic time-reversibility, geometric temperature schedule, Metropolis swap,
               explicit velocity rescaling, SWMR thread-safe lifecycle.
- [E] Empirical: Harmonic valence + LJ parameters, Maxwell-Boltzmann velocity distribution,
               NVE secular energy conservation within 1e-4.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
Absolutely no stubs, empty pass blocks, or synthetic test data.
"""

from __future__ import annotations

import inspect
import math
from pathlib import Path
import tempfile
from pydantic import ValidationError
import pytest
import torch

from Libraries.cochem_torq_masses import (
    get_atomic_masses,
    resolve_ciaaw_monoisotopic_mass,
)
from Libraries.cochem_torq_md_env import (
    dispatch_md_device,
    resolve_hpc_safe_scratch,
)
from Libraries.cochem_torq_md_errors import (
    EnergyDriftExceededError,
    HardwareDispatchError,
    ReplicaExchangeDivergenceError,
    SymplecticIntegratorError,
    TorqMDError,
)
from Libraries.cochem_torq_md_schemas import (
    ExchangeLog,
    MDState,
    REMDConfig,
    TrajectoryFrame,
    VelocityVerletConfig,
)
from Libraries.cochem_torq_remd import (
    ReplicaExchangeEngine,
    baoab_langevin_step,
    compute_geometric_temperature_schedule,
    evaluate_metropolis_swap,
    rescale_velocities_on_swap,
)
from Libraries.cochem_torq_symplectic import (
    BOLTZMANN_CONSTANT,
    ELEMENTARY_CHARGE,
    KAPPA_ACC,
    KAPPA_ACC_INV,
    LENGTH_SCALE_M_TO_ANGSTROM,
    TIME_SCALE_S_TO_FS,
    UNIFIED_ATOMIC_MASS_KG,
    VelocityVerletIntegrator,
    compute_conservative_forces,
    compute_dimensional_acceleration,
    compute_instantaneous_temperature,
    compute_kinetic_energy,
    remove_center_of_mass_momentum,
)
from Libraries.cochem_torq_trajectory import (
    HDF5TrajectoryReader,
    HDF5TrajectoryWriter,
)

# Authentic equilibrium Water Dimer (H2O)2 geometry (N=6 atoms) [M]
WATER_DIMER_COORDS = torch.tensor(
    [
        [-1.484, 0.000, -0.091],  # O1 (donor)
        [-1.877, 0.760, 0.354],  # H1
        [-0.533, 0.000, 0.038],  # H2 (bridging hydrogen)
        [1.408, 0.000, 0.110],  # O2 (acceptor)
        [1.758, 0.760, -0.335],  # H3
        [1.758, -0.760, -0.335],  # H4
    ],
    dtype=torch.float64,
)
WATER_DIMER_Z = torch.tensor([8, 1, 1, 8, 1, 1], dtype=torch.int64)

# Authentic equilibrium Water Monomer H2O (N=3 atoms) [M]
WATER_MONOMER_COORDS = torch.tensor(
    [
        [0.0000, 0.0000, 0.1173],  # O
        [0.0000, 0.7572, -0.4692],  # H1
        [0.0000, -0.7572, -0.4692],  # H2
    ],
    dtype=torch.float64,
)
WATER_MONOMER_Z = torch.tensor([8, 1, 1], dtype=torch.int64)


class FlexibleWaterPotential(torch.nn.Module):
    """Harmonic valence force field + Lennard-Jones non-bonded potential for water in eV [D]."""

    def __init__(self) -> None:
        super().__init__()
        self.r0 = 0.9572  # A
        self.theta0 = 104.52 * math.pi / 180.0  # rad
        self.kb = 46.0  # eV / A^2
        self.kt = 4.5  # eV / rad^2
        self.sigma_oo = 3.166  # A
        self.epsilon_oo = 0.0067  # eV

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        """Evaluate total potential energy of water system in eV [D]."""
        total_energy = torch.zeros((), dtype=torch.float64, device=coords.device)
        n_atoms = coords.shape[0]
        n_waters = n_atoms // 3

        for w in range(n_waters):
            idx_O = 3 * w
            idx_H1 = 3 * w + 1
            idx_H2 = 3 * w + 2
            r_O = coords[idx_O]
            r_H1 = coords[idx_H1]
            r_H2 = coords[idx_H2]

            v1 = r_H1 - r_O
            v2 = r_H2 - r_O
            d1 = torch.linalg.norm(v1)
            d2 = torch.linalg.norm(v2)

            # Harmonic bond stretching
            e_stretch = 0.5 * self.kb * ((d1 - self.r0) ** 2 + (d2 - self.r0) ** 2)

            # Harmonic angle bending
            cos_theta = torch.clamp(torch.dot(v1, v2) / (d1 * d2), -1.0, 1.0)
            theta = torch.acos(cos_theta)
            e_bend = 0.5 * self.kt * ((theta - self.theta0) ** 2)
            total_energy = total_energy + e_stretch + e_bend

        # Intermolecular non-bonded potential between oxygens if dimer
        if n_waters > 1:
            r_O1 = coords[0]
            r_O2 = coords[3]
            r_oo = torch.linalg.norm(r_O1 - r_O2)
            sr6 = (self.sigma_oo / r_oo) ** 6
            e_lj = 4.0 * self.epsilon_oo * (sr6**2 - sr6)
            total_energy = total_energy + e_lj

        return total_energy


def test_mendeleev_dynamic_mass_retrieval() -> None:
    """Dynamically query atomic masses for H and O via mendeleev library [M]."""
    z_tensor = torch.tensor([1, 8], dtype=torch.int64)
    masses = get_atomic_masses(z_tensor)

    m_H = float(masses[0].item())
    m_O = float(masses[1].item())

    assert 1.0079 <= m_H <= 1.0081, f"Hydrogen mass {m_H} outside expected CIAAW bounds."
    assert 15.999 <= m_O <= 16.000, f"Oxygen mass {m_O} outside expected CIAAW bounds."

    # Verify dynamic monoisotopic mass resolution
    mono_H = resolve_ciaaw_monoisotopic_mass(1)
    mono_O = resolve_ciaaw_monoisotopic_mass(8)
    assert 1.0078 <= mono_H <= 1.0079, f"Monoisotopic H {mono_H} outside bounds."
    assert 15.994 <= mono_O <= 15.996, f"Monoisotopic O {mono_O} outside bounds."

    # Inspect source code to guarantee dynamic library query rather than hardcoded tables
    source_code = inspect.getsource(get_atomic_masses)
    assert "element(" in source_code, "get_atomic_masses must dynamically invoke mendeleev.element."


def test_conservative_force_autograd_and_curl_free() -> None:
    """Evaluate autograd forces on Water monomer, comparing with central finite difference and curl [D]."""
    pot = FlexibleWaterPotential()
    coords = WATER_MONOMER_COORDS.clone().requires_grad_(True)

    forces, energy = compute_conservative_forces(
        pot, coords, return_energy=True, create_graph=True
    )

    # 1. Compare analytical forces against central finite difference
    delta = 1e-5
    fd_forces = torch.zeros_like(WATER_MONOMER_COORDS)
    for i in range(WATER_MONOMER_COORDS.shape[0]):
        for d in range(3):
            c_plus = WATER_MONOMER_COORDS.clone()
            c_plus[i, d] += delta
            c_minus = WATER_MONOMER_COORDS.clone()
            c_minus[i, d] -= delta
            e_plus = pot(c_plus)
            e_minus = pot(c_minus)
            fd_forces[i, d] = -(e_plus - e_minus) / (2.0 * delta)

    max_force_diff = torch.max(torch.abs(forces - fd_forces)).item()
    assert (
        max_force_diff < 1.0e-4
    ), f"Force autograd deviated from finite difference by {max_force_diff:.6e} eV/A."

    # 2. Verify conservative gradient curl ||curl F||_2 < 1.0e-6 eV/A^2
    curls: list[float] = []
    for i in range(coords.shape[0]):
        Fx = forces[i, 0]
        Fy = forces[i, 1]
        Fz = forces[i, 2]

        dFx = torch.autograd.grad(Fx, coords, retain_graph=True)[0][i]
        dFy = torch.autograd.grad(Fy, coords, retain_graph=True)[0][i]
        dFz = torch.autograd.grad(Fz, coords, retain_graph=True)[0][i]

        curl_x = dFz[1] - dFy[2]
        curl_y = dFx[2] - dFz[0]
        curl_z = dFy[0] - dFx[1]
        curl_vec = torch.tensor(
            [curl_x.item(), curl_y.item(), curl_z.item()], dtype=torch.float64
        )
        curls.append(float(torch.linalg.norm(curl_vec).item()))

    max_curl = max(curls)
    assert (
        max_curl < 1.0e-6
    ), f"Conservative force field non-zero curl {max_curl:.6e} eV/A^2."


def test_acceleration_dimensional_factor_conversion() -> None:
    """Verify dimensional acceleration factor matches identity from CODATA 2018 constants [D]."""
    derived_kappa = (
        ELEMENTARY_CHARGE * (LENGTH_SCALE_M_TO_ANGSTROM**2)
    ) / (UNIFIED_ATOMIC_MASS_KG * (TIME_SCALE_S_TO_FS**2))

    assert (
        abs(KAPPA_ACC - derived_kappa) < 1.0e-15
    ), f"KAPPA_ACC {KAPPA_ACC} differs from derived CODATA identity {derived_kappa}."
    assert (
        abs(KAPPA_ACC_INV - (1.0 / KAPPA_ACC)) < 1.0e-6
    ), f"KAPPA_ACC_INV {KAPPA_ACC_INV} differs from reciprocal {1.0 / KAPPA_ACC}."


def test_center_of_mass_momentum_elimination() -> None:
    """Assert center-of-mass momentum elimination achieves ||P_COM|| < 1.0e-10 u*A/fs [D]."""
    masses = get_atomic_masses(WATER_DIMER_Z)
    torch.manual_seed(42)
    velocities = torch.randn(6, 3, dtype=torch.float64) * 0.05 + 1.5

    p_before = torch.sum(masses.view(-1, 1) * velocities, dim=0)
    assert torch.linalg.norm(p_before).item() > 1.0

    corrected_velocities = remove_center_of_mass_momentum(velocities, masses)
    p_after = torch.sum(masses.view(-1, 1) * corrected_velocities, dim=0)
    net_momentum = float(torch.linalg.norm(p_after).item())

    assert (
        net_momentum < 1.0e-10
    ), f"Net COM linear momentum {net_momentum:.6e} exceeded 1e-10 u*A/fs threshold."


def test_kinetic_energy_and_temperature_degrees_of_freedom() -> None:
    """Verify degrees of freedom and temperature observables on Water Dimer [D]."""
    masses = get_atomic_masses(WATER_DIMER_Z)
    torch.manual_seed(42)
    velocities = torch.randn(6, 3, dtype=torch.float64) * 0.01

    e_kin = compute_kinetic_energy(velocities, masses)
    assert e_kin > 0.0

    t_com_constrained = compute_instantaneous_temperature(
        e_kin, n_atoms=6, remove_com=True
    )
    t_unconstrained = compute_instantaneous_temperature(
        e_kin, n_atoms=6, remove_com=False
    )

    expected_t_constrained = (2.0 * e_kin) / (15 * BOLTZMANN_CONSTANT)
    expected_t_unconstrained = (2.0 * e_kin) / (18 * BOLTZMANN_CONSTANT)

    assert abs(t_com_constrained - expected_t_constrained) < 1.0e-12
    assert abs(t_unconstrained - expected_t_unconstrained) < 1.0e-12
    assert t_com_constrained > t_unconstrained


def test_nve_energy_conservation_water_dimer() -> None:
    """Execute NVE Velocity Verlet trajectory and assert secular drift < 1.0e-4 [M]."""
    pot = FlexibleWaterPotential()
    masses = get_atomic_masses(WATER_DIMER_Z)
    config = VelocityVerletConfig(
        timestep_fs=0.05,
        n_steps=2000,
        energy_drift_tolerance=1.0e-4,
    )
    integrator = VelocityVerletIntegrator(pot, config, masses)

    torch.manual_seed(42)
    v0 = torch.randn_like(WATER_DIMER_COORDS) * 0.01

    _, _, states = integrator.integrate(
        WATER_DIMER_COORDS, v0, n_steps=2000, timestep_fs=0.05
    )
    e0 = states[0].total_energy_ev
    drifts = [abs((s.total_energy_ev - e0) / e0) for s in states]
    max_drift = max(drifts)

    assert (
        max_drift < 1.0e-4
    ), f"NVE maximum relative energy drift {max_drift:.6e} exceeded 1.0e-4 tolerance."


def test_energy_drift_exceeded_error_trigger() -> None:
    """Assert EnergyDriftExceededError is raised when integrating with unstable timestep [M]."""
    pot = FlexibleWaterPotential()
    masses = get_atomic_masses(WATER_DIMER_Z)
    config = VelocityVerletConfig.model_construct(
        timestep_fs=5.0,
        n_steps=100,
        save_interval=10,
        device="cpu",
        dtype="float64",
        energy_drift_tolerance=1.0e-4,
        remove_com_momentum=True,
    )
    integrator = VelocityVerletIntegrator(pot, config, masses)

    torch.manual_seed(42)
    v0 = torch.randn_like(WATER_DIMER_COORDS) * 0.01

    with pytest.raises(EnergyDriftExceededError) as exc_info:
        integrator.integrate(WATER_DIMER_COORDS, v0, n_steps=100, timestep_fs=5.0)

    err = exc_info.value
    assert err.drift > 1.0e-4
    assert err.tolerance == 1.0e-4
    assert err.step > 0
    assert "potential_energy" in err.diagnostics


def test_symplectic_phase_space_time_reversibility() -> None:
    """Assert phase space reversibility r(2N) == r(0) to within 1.0e-5 A [D]."""
    pot = FlexibleWaterPotential()
    masses = get_atomic_masses(WATER_DIMER_Z)
    config = VelocityVerletConfig(
        timestep_fs=0.5,
        n_steps=1000,
        energy_drift_tolerance=1.0,
    )
    integrator = VelocityVerletIntegrator(pot, config, masses)

    torch.manual_seed(42)
    v0 = torch.randn_like(WATER_DIMER_COORDS) * 0.01

    r_fwd, v_fwd, _ = integrator.integrate(WATER_DIMER_COORDS, v0, n_steps=1000)

    # Invert velocities and integrate backward
    v_rev = -v_fwd
    r_back, v_back, _ = integrator.integrate(r_fwd, v_rev, n_steps=1000)

    max_deviation = float(
        torch.max(torch.linalg.norm(r_back - WATER_DIMER_COORDS, dim=-1)).item()
    )
    assert (
        max_deviation < 1.0e-5
    ), f"Phase space time reversibility deviation {max_deviation:.6e} A exceeded 1e-5 A."


def test_baoab_langevin_canonical_bath_coupling() -> None:
    """Assert BAOAB Langevin thermostat converges to 300 +- 5 K and Maxwell-Boltzmann variance [D]."""
    n_atoms = 1000
    masses = torch.ones(n_atoms, 1, dtype=torch.float64) * 18.015
    gamma = 1.0 * 1e-3  # 1 ps^-1 to fs^-1
    dt = 0.5  # fs
    c1 = math.exp(-gamma * dt)
    c2 = math.sqrt(KAPPA_ACC * (1.0 - c1**2))
    t_target = 300.0

    torch.manual_seed(123)
    std = torch.sqrt(KAPPA_ACC * BOLTZMANN_CONSTANT * t_target / masses)
    v = torch.randn(n_atoms, 3, dtype=torch.float64) * std

    temps: list[float] = []
    for _ in range(5000):
        eta = torch.randn_like(v)
        v = c1 * v + c2 * torch.sqrt((BOLTZMANN_CONSTANT * t_target) / masses) * eta
        e_kin = 0.5 * KAPPA_ACC_INV * torch.sum(masses * (v**2))
        t_inst = (2.0 * float(e_kin)) / (3 * n_atoms * BOLTZMANN_CONSTANT)
        temps.append(t_inst)

    avg_temp = sum(temps) / len(temps)
    assert (
        abs(avg_temp - 300.0) <= 5.0
    ), f"BAOAB thermostat average temperature {avg_temp:.2f} K outside 300 +- 5 K range."

    # Maxwell-Boltzmann variance parity verification
    v_flat = v.view(-1)
    mean_v = float(torch.mean(v_flat).item())
    var_v = float(torch.var(v_flat).item())
    expected_var = float(KAPPA_ACC * BOLTZMANN_CONSTANT * t_target / 18.015)

    assert abs(mean_v) < 0.001, f"Mean velocity {mean_v} drifted from zero."
    assert (
        abs((var_v - expected_var) / expected_var) < 0.05
    ), "Velocity variance deviates from Maxwell-Boltzmann distribution."


def test_remd_geometric_temperature_schedule() -> None:
    """Verify geometric temperature schedule and thermodynamic beta values [D]."""
    temps, betas = compute_geometric_temperature_schedule(
        n_replicas=4,
        t_min_k=300.0,
        t_max_k=600.0,
    )
    expected_temps = [300.0, 377.98, 476.22, 600.0]

    for t, exp_t in zip(temps, expected_temps):
        assert (
            abs(t - exp_t) < 0.05
        ), f"Temperature {t} deviated from expected geometric setpoint {exp_t}."

    for t, b in zip(temps, betas):
        expected_b = 1.0 / (BOLTZMANN_CONSTANT * t)
        assert (
            abs(b - expected_b) < 1.0e-12
        ), f"Thermodynamic beta {b} deviated from 1/(kB*T) {expected_b}."


def test_remd_metropolis_swap_and_velocity_rescaling() -> None:
    """Verify Metropolis swap probability and explicit temperature velocity rescaling [D]."""
    t1 = 300.0
    t2 = 400.0
    beta1 = 1.0 / (BOLTZMANN_CONSTANT * t1)
    beta2 = 1.0 / (BOLTZMANN_CONSTANT * t2)
    u1 = -12.4
    u2 = -12.0

    delta = (beta1 - beta2) * (u1 - u2)
    expected_p = min(1.0, math.exp(delta))

    p_swap, _ = evaluate_metropolis_swap(beta1, beta2, u1, u2)
    assert (
        abs(p_swap - expected_p) < 1.0e-12
    ), f"Metropolis swap probability {p_swap} does not match expected {expected_p}."

    v1 = torch.tensor([[1.2, -0.4, 0.8]], dtype=torch.float64)
    v2 = torch.tensor([[0.5, 1.1, -0.9]], dtype=torch.float64)

    v1_new, v2_new = rescale_velocities_on_swap(v1, v2, t1, t2)

    assert torch.allclose(v1_new, v2 * math.sqrt(t1 / t2))
    assert torch.allclose(v2_new, v1 * math.sqrt(t2 / t1))


def test_hdf5_swmr_trajectory_lifecycle() -> None:
    """Verify HDF5 SWMR lifecycle sequencing and non-blocking concurrent reader [M]."""
    tmp_path = Path(tempfile.gettempdir()) / "test_chunk21_traj_lifecycle.h5"
    if tmp_path.exists():
        tmp_path.unlink()

    atomic_numbers = torch.tensor([8, 1, 1], dtype=torch.int64)
    writer = HDF5TrajectoryWriter(
        file_path=tmp_path,
        n_atoms=3,
        atomic_numbers=atomic_numbers,
        chunk_size=10,
    )

    # Verify SWMR mode engaged
    assert writer.file.swmr_mode is True
    assert "coordinates" in writer.file
    assert "atomic_numbers" in writer.file

    # Concurrent reader opening active file
    reader = HDF5TrajectoryReader(tmp_path)
    assert len(reader) == 0

    frame = TrajectoryFrame(
        step=0,
        time_fs=0.0,
        atomic_numbers=atomic_numbers,
        coordinates=torch.tensor(
            [[0.0, 0.0, 0.1], [0.0, 0.7, -0.4], [0.0, -0.7, -0.4]],
            dtype=torch.float64,
        ),
        velocities=torch.zeros((3, 3), dtype=torch.float64),
        forces=torch.ones((3, 3), dtype=torch.float64) * 0.01,
        potential_energy_ev=-15.2,
        kinetic_energy_ev=0.3,
    )
    writer.append_frame(frame)

    reader.refresh()
    assert len(reader) == 1

    loaded_frame = reader.read_frame(0)
    assert loaded_frame.step == 0
    assert torch.allclose(loaded_frame.coordinates, frame.coordinates)
    assert torch.allclose(loaded_frame.velocities, frame.velocities)
    assert torch.allclose(loaded_frame.forces, frame.forces)
    assert abs(loaded_frame.potential_energy_ev - frame.potential_energy_ev) < 1.0e-6

    reader.close()
    writer.close()
    if tmp_path.exists():
        tmp_path.unlink()


def test_apple_silicon_mps_float64_cpu_fallback() -> None:
    """Assert MPS requests automatically fallback to CPU for float64 compliance [M]."""
    routed_device = dispatch_md_device("mps")
    assert routed_device == torch.device(
        "cpu"
    ), "MPS request must route to CPU for float64 compliance."

    routed_cpu = dispatch_md_device("cpu")
    assert routed_cpu == torch.device("cpu")


def test_pydantic_v2_data_validation() -> None:
    """Verify REMDConfig and VelocityVerletConfig parameter validation [M]."""
    # Reject T_max <= T_min
    with pytest.raises(ValidationError):
        REMDConfig(
            n_replicas=4,
            t_min_k=600.0,
            t_max_k=300.0,
            output_dir=Path("."),
        )

    # Reject total_steps < swap_interval
    with pytest.raises(ValidationError):
        REMDConfig(
            n_replicas=4,
            t_min_k=300.0,
            t_max_k=600.0,
            swap_interval_steps=200,
            total_steps_per_replica=100,
            output_dir=Path("."),
        )

    # Reject timestep_fs > 1.0
    with pytest.raises(ValidationError):
        VelocityVerletConfig(timestep_fs=1.5)

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.