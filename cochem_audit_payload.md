Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_20_TORQ_Inference_and_Export_Part_3_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous multi-task learning head (HOMO-LUMO gap and total potential energy), machine-precision central finite-difference gradient verification suite, double-autograd Cartesian Hessian calculator with dynamic CIAAW monoisotopic masses, Gram-Schmidt Eckart translational/rotational projection, CODATA 2022-scaled signed vibrational frequency analyzer, and PyTorch 2.0+ TorchDynamo ONNX edge-export pipeline with 3D dynamic axes and molecular graph connectivity specified in Software Requirements Specification (SRS) Chunk 20: `TORQ_Inference_and_Export_Part_3` (`COCHEM-SRS-CHUNK-20-TORQ`).

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev monoisotopic mass retrieval mandate, and Method Matrix v4 (`[M]` Empirical Benchmark, `[D]` Derived Mathematical Relationship, `[E]` Estimated Theoretical Projection). Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine physical tensors, authentic molecular coordinates, and real chemical observables.

---

### 1. DIRECTORY, PERSISTENCE & 6-TIER RUNTIME CONTRACTS

1. **Tripartite Workspace Air-Gap Paths**:
   - `COCHEM_SRC_DIR` ($R_{\text{src}}$): `pathlib.Path(os.environ.get("COCHEM_SRC_DIR", Path.cwd()))` (Read-only source repository).
   - `COCHEM_DATA_DIR` ($R_{\text{data}}$): `pathlib.Path(os.environ.get("COCHEM_DATA_DIR", Path.home() / ".cochem" / "data"))` (Read-only datasets, reference tables, and weights under `COCHEM_OFFLINE=1`).
   - `COCHEM_ARTIFACTS_DIR` ($R_{\text{art}}$): `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR", Path.home() / ".cochem" / "artifacts"))` (Read-write checkpoints, vibrational frequency reports, ONNX binaries, manifests, logs, and telemetry).
   - `COCHEM_SCRATCH_DIR`: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR", os.environ.get("SLURM_TMPDIR", Path.home() / ".cochem" / "scratch")))`.
2. **6-Tier Runtime & Hardware Concurrency**:
   - **Accelerator Binding & Safe Device Dispatcher**:
     * Query hardware availability: NVIDIA CUDA (`torch.cuda.is_available()`), Apple Silicon Metal Performance Shaders (`getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()`), or CPU.
     * **Apple Silicon MPS `float64` Automatic Fallback Rule (`DEF-10` `[M]`)**: Metal Performance Shaders (MPS) hardware architecture does not support native 64-bit floating point (`torch.float64`). Attempting to allocate or compute `float64` tensors on `mps` raises an immediate `TypeError: Cannot convert a MPS tensor to float64`. When executing high-precision routines (finite-difference verification, double-autograd Hessians, Eckart projections, eigensolvers) requiring `torch.float64`, the dispatcher must automatically intercept and route execution to `cpu`. Single-precision `float32` inference remains on `mps`.
     * Dynamic hardware detection must never hardcode device ordinals (e.g., `cuda:0` is strictly banned).
   - **Strict Tensor Precision & Dtype Synchronization**:
     * Mandatory `torch.float64` (`torch.double`, 53-bit significand) across all coordinate inputs, energy evaluations, finite differences, mass weighting, and eigensolvers (`DEF-06` `[M]`). Single precision (`torch.float32`) is restricted strictly to inference-only deployment where analytical forces are evaluated directly.
   - **Thread-Safe Storage & Concurrency**:
     * **HPC Distributed Lock Prohibition Rule (`DEF-10` `[M]`)**: On Tier 6 HPC environments, parallel network filesystems (Lustre, GPFS, BeeGFS, NFS) rely on centralized distributed lock managers. Direct `filelock.FileLock` across parallel filesystems causes lock manager deadlocks (`[Errno 37] No locks available`). Unconditional `filelock.FileLock` on parallel network filesystems is strictly prohibited. All staging, locking, and temporary files must be resolved dynamically to the node-local NVMe scratch directory `$SLURM_TMPDIR` (or `$TMPDIR`) via `resolve_hpc_safe_scratch()`.
     * Atomic state updates on shared storage must use atomic rename sidecars (`tempfile.NamedTemporaryFile` in local scratch committed via `os.replace`).
     * On single-node environments (Tiers 1-5), local file locking via `filelock.FileLock(lock_path, timeout=30.0)` is permitted.
     * HDF5 datasets and `PESStore` operate under Single-Writer Multiple-Reader (`libver='latest'`, `swmr=True`).
   - **Atomic Serialization**: Write temporary file `.tmp`, flush to disk with `os.fsync(f.fileno())`, atomically replace via `os.replace`, and write an accompanying cryptographic `.sha256` digest file.
3. **OS-Agnostic Dynamic Paths**: All filesystem operations are mediated via `pathlib.Path`. Hardcoded OS path separators (`/`, `\`), `$HOME`, or `C:\` are strictly prohibited.

---

### 2. DOMAIN EXCEPTIONS & PYDANTIC V2 DATA CONTRACTS

- **Files**: `Libraries/cochem_torq_inference_errors.py` and `Libraries/cochem_torq_inference_schemas.py` (and export in `Libraries/__init__.py`).
- **Domain Exception Hierarchy**:
  ```python
  from typing import Any, Dict, Optional


  class CoChemTorqError(Exception):
    """Root base exception for all CoChem-TORQ runtime operations [M]."""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_GENERIC_ERROR",
        component: str = "inference_export",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
      super().__init__(message)
      self.error_code = error_code
      self.component = component
      self.diagnostics = diagnostics or {}


  class PhysicsDivergenceError(CoChemTorqError):
    """Raised when fundamental physical invariants are violated (non-positive gap, negative mass, unphysical ZPVE) [M]."""

    pass


  class NumericalParityError(CoChemTorqError):
    """Raised when finite-difference gradients diverge from analytical forces beyond acceptance tolerance or float32 is detected [M]."""

    pass


  class ConcurrencyLockError(CoChemTorqError):
    """Raised when filesystem locking fails or HPC distributed lock prohibitions are violated on shared filesystems [M]."""

    pass


  class OpsetUnsupportedError(CoChemTorqError):
    """Raised when an unsupported ONNX opset (< 17) or invalid autograd export pipeline is invoked [M]."""

    pass
```

- **Pydantic v2 Data Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
  ```python
  from typing import Dict, List
  from pydantic import BaseModel, ConfigDict, Field, field_validator


  class MultiTaskPrediction(BaseModel):
    """Encapsulates multi-task predictions for potential energy, forces, and HOMO-LUMO gap."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    energy: float = Field(
        ..., description="Molecular potential energy in eV [M]"
    )
    forces: List[List[float]] = Field(
        ...,
        description=(
            "Atomic Cartesian forces [N, 3] in eV/Angstrom [M]"
        ),
    )
    homo_lumo_gap: float = Field(
        ...,
        gt=0.0,
        description="Fundamental HOMO-LUMO electronic gap in eV [M]",
    )
    energy_log_variance: float = Field(
        ..., description="Task log-variance s_E = log(sigma_E^2) [D]"
    )
    gap_log_variance: float = Field(
        ..., description="Task log-variance s_G = log(sigma_G^2) [D]"
    )

    @field_validator("forces")
    @classmethod
    def validate_forces_shape(cls, v: List[List[float]]) -> List[List[float]]:
      if not v or len(v) == 0:
        raise ValueError("Forces tensor cannot be empty.")
      for row in v:
        if len(row) != 3:
          raise ValueError(
              f"Each force vector must be 3D Cartesian [x, y, z], got dimension"
              f" {len(row)}."
          )
      return v


  class FiniteDiffVerificationResult(BaseModel):
    """Validation report certifying agreement between analytic and finite-difference forces."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_absolute_error: float = Field(
        ...,
        description=(
            "Maximum absolute force component error (L_infinity) in"
            " eV/Angstrom [M]"
        ),
    )
    relative_frobenius_error: float = Field(
        ..., description="Relative Frobenius norm error [M]"
    )
    step_size: float = Field(
        ..., description="Displacement step size h in Angstrom [E]"
    )
    passed: bool = Field(
        ...,
        description=(
            "True if within acceptance criteria (L_inf < 1e-4 eV/A) [M]"
        ),
    )
    dtype: str = Field(
        ...,
        description="Execution tensor precision, strictly torch.float64 [M]",
    )
    atom_count: int = Field(
        ...,
        ge=1,
        description="Number of atoms in the evaluated structure [M]",
    )


  class VibrationalModes(BaseModel):
    """Full normal mode report containing projected harmonic frequencies and zero-point energy."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    frequencies_cm1: List[float] = Field(
        ...,
        description=(
            "Signed harmonic vibrational frequencies in cm^-1 (nu < 0 for"
            " imaginary modes) [D]"
        ),
    )
    zero_point_energy_ev: float = Field(
        ...,
        ge=0.0,
        description="Harmonic Zero-Point Vibrational Energy (ZPVE) in eV [D]",
    )
    imaginary_mode_count: int = Field(
        ...,
        ge=0,
        description=(
            "Count of transition-state imaginary normal modes (nu < 0) [D]"
        ),
    )
    eigenvalues: List[float] = Field(
        ...,
        description=(
            "Mass-weighted Hessian eigenvalues in eV/(Angstrom^2 * u) [D]"
        ),
    )
    projected_degrees_of_freedom: int = Field(
        ...,
        description=(
            "Number of projected translational and rotational degrees of"
            " freedom (5 or 6) [D]"
        ),
    )
    mass_weighting_standard: str = Field(
        default="CIAAW_MONOISOTOPIC",
        description="Governing standard for isotopic masses [M]",
    )


  class ONNXExportSpec(BaseModel):
    """Configuration specification governing TorchDynamo ONNX compilation and dynamic axes."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    opset_version: int = Field(
        ..., ge=17, description="Target ONNX opset version (>= 17) [E]"
    )
    export_mechanism: str = Field(
        ...,
        description=(
            "Export engine: dynamo_export_aot_autograd or"
            " direct_analytical_force_head [D]"
        ),
    )
    dynamic_axes: Dict[str, Dict[int, str]] = Field(
        ...,
        description=(
            "Dynamic axes dictionary covering 3D tensors and edge_index [D]"
        ),
    )
    precision: str = Field(
        ..., description="Model numerical precision: float32 or float64 [E]"
    )
```

---

### 3. MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Multi-Task Learning Head with Log-Variance Homoscedastic Loss (`REQ-TORQ-INF-301` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_multitask.py` (and export in `Libraries/__init__.py`)
- **Auxiliary Equivariant Regression Head**:
  - Integrate onto the shared invariant/equivariant representation backbone to predict total potential energy $E \in \mathbb{R}^{B \times 1}$ (in $\text{eV}$) and the fundamental frontier orbital gap $\Delta \epsilon_{\text{HL}} = \epsilon_{\text{LUMO}} - \epsilon_{\text{HOMO}} \in \mathbb{R}^{B \times 1}$ (in $\text{eV}$).
  - Strictly enforce $\Delta \epsilon_{\text{HL}} > 0$ via a smooth Softplus activation function ($\Delta \epsilon_{\text{HL}} = \operatorname{Softplus}(x) + \epsilon_{\text{gap}}$, where $\epsilon_{\text{gap}} = 10^{-4}\,\text{eV}$). If any predicted gap $\le 0$, raise `PhysicsDivergenceError`.
- **Log-Variance Homoscedastic Formulation (`DEF-08` `[D]`)**:
  - Directly optimizing raw task variances $\sigma_E, \sigma_G$ risks floating-point overflow (`Inf`) when $\sigma \to 0$ or domain violations when $\sigma < 0$. Task variances are reparameterized into unconstrained log-variances:
    $$s_E = \log(\sigma_E^2), \quad s_G = \log(\sigma_G^2) \quad [D]$$
  - Learnable parameters $s_E, s_G \in \mathbb{R}$ initialized at $s_{E, 0} = 0.0$ `[E]` and $s_{G, 0} = 0.0$ `[E]`.
- **Task-Specific Smooth Huber Loss Envelopes (`DEF-08` `[D]`/`[E]`)**:
  - Smooth Huber envelope:
    $$\mathcal{L}_{\text{Huber}}(y, y^*; \delta) = \begin{cases} \frac{1}{2}(y - y^*)^2, & \text{if } |y - y^*| \le \delta \\ \delta\left(|y - y^*| - \frac{1}{2}\delta\right), & \text{if } |y - y^*| > \delta \end{cases} \quad [D]$$
  - Threshold parameters:
    * Potential Energy: $\delta_E = 0.01\,\text{eV}$ ($\approx 0.23\,\text{kcal/mol}$, sub-chemical accuracy limit) `[E]`.
    * HOMO-LUMO Gap: $\delta_G = 0.05\,\text{eV}$ ($\approx 1.15\,\text{kcal/mol}$, optical band edge tolerance) `[E]`.
- **Joint Multi-Task Objective & Gradients**:
  $$\mathcal{L}_{\text{multi}} = \frac{1}{2} \exp(-s_E) \mathcal{L}_{\text{Huber}}(E, E^*; \delta_E) + \frac{1}{2} \exp(-s_G) \mathcal{L}_{\text{Huber}}(\Delta \epsilon_{\text{HL}}, \Delta \epsilon_{\text{HL}}^*; \delta_G) + \frac{1}{2}(s_E + s_G) \quad [D]$$
  - Exact analytical log-variance gradients:
    $$\frac{\partial \mathcal{L}_{\text{multi}}}{\partial s_E} = -\frac{1}{2}\exp(-s_E)\mathcal{L}_{\text{Huber}}(E, E^*; \delta_E) + \frac{1}{2} \quad [D]$$
    $$\frac{\partial \mathcal{L}_{\text{multi}}}{\partial s_G} = -\frac{1}{2}\exp(-s_G)\mathcal{L}_{\text{Huber}}(\Delta \epsilon_{\text{HL}}, \Delta \epsilon_{\text{HL}}^*; \delta_G) + \frac{1}{2} \quad [D]$$
    Equilibrium is attained dynamically when $\exp(s_k) = \mathcal{L}_{\text{Huber}, k}$.

---

#### 2. Machine-Precision Finite-Difference Gradient Verification (`REQ-TORQ-INF-302` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_finite_difference.py` (and export in `Libraries/__init__.py`)
- **Mathematical Formulation**:
  - Conservative analytical forces via automatic differentiation:
    $$\mathbf{F}_{\text{analytic}, i} = -\nabla_{\mathbf{R}_i} E(\mathbf{R}) \in \mathbb{R}^3 \quad [D]$$
  - Central two-point finite-difference numerical forces across all $3N$ degrees of freedom:
    $$F_{\text{num}, i\alpha} = -\frac{E(\mathbf{R} + h \mathbf{e}_{i\alpha}) - E(\mathbf{R} - h \mathbf{e}_{i\alpha})}{2h} \quad [D]$$
    where displacement parameter is fixed at $h = 1.0 \times 10^{-4}\,\text{\AA}$ `[E]`.
- **The float32 Subtractive Cancellation Disaster & float64 Mandate (`DEF-06` `[M]`/`[D]`)**:
  - In IEEE-754 single precision (`torch.float32`), $\epsilon_{\text{mach}} \approx 1.19 \times 10^{-7}$. Evaluating finite differences on a molecule with $|E| \approx 10^2\,\text{eV}$ yields numerical cancellation noise:
    $$\Delta F_{\text{num}} \approx \frac{\epsilon_{\text{mach}} |E|}{2h} \approx \frac{1.19 \times 10^{-7} \times 10^2}{2 \times 10^{-4}} \approx 5.95 \times 10^{-2}\,\text{eV/\AA} \quad [D]$$
    This noise ($0.06\,\text{eV/\AA}$) is 600 times larger than acceptance tolerances, causing unconditional failure.
  - **Mandatory Precision Guard**: Coordinates, energy evaluations, and forces must execute strictly in `torch.float64` (`torch.double`, 53-bit significand, $\epsilon_{\text{mach}} \approx 2.22 \times 10^{-16}$). In double precision, numerical subtraction noise is suppressed to $\approx 1.11 \times 10^{-10}\,\text{eV/\AA} \ll 1.0 \times 10^{-4}\,\text{eV/\AA}$.
  - Any input passed with `dtype != torch.float64` must raise an immediate `NumericalParityError`.
- **Acceptance Criteria**:
  1. $L_\infty$ Force Norm Metric:
     $$L_\infty = \max_{i \in \{1 \dots N\}, \alpha \in \{x, y, z\}} \left| F_{\text{analytic}, i\alpha} - F_{\text{num}, i\alpha} \right| < 1.0 \times 10^{-4}\,\text{eV/\AA} \quad [M]$$
  2. Relative Frobenius Norm Metric:
     $$\text{RelErr}_F = \frac{\|\mathbf{F}_{\text{analytic}} - \mathbf{F}_{\text{num}}\|_F}{\|\mathbf{F}_{\text{analytic}}\|_F + 10^{-12}} < 1.0 \times 10^{-4} \quad [M]$$
  - Return certified `FiniteDiffVerificationResult`. If tolerances are violated, raise `NumericalParityError`.

---

#### 3. Double-Autograd Cartesian Hessian, Dynamic CIAAW Masses, Eckart Projection & Vibrational Frequencies (`REQ-TORQ-INF-303` `[M]`/`[D]`)
- **File Target**: `Libraries/cochem_torq_vibrational.py` (and export in `Libraries/__init__.py`)
- **Double-Autograd Cartesian Hessian Construction**:
  - Full Cartesian Hessian $\mathbf{H} \in \mathbb{R}^{3N \times 3N}$ is evaluated via nested reverse-mode automatic differentiation in `torch.float64`:
    $$H_{i\alpha, j\beta} = \frac{\partial^2 E}{\partial R_{i\alpha} \partial R_{j\beta}} = -\frac{\partial F_{\text{analytic}, i\alpha}}{\partial R_{j\beta}} \quad [D]$$
    using `torch.autograd.grad(..., create_graph=True)`.
  - Active Hermitian symmetrization to eliminate numerical asymmetry:
    $$\mathbf{H} = \frac{1}{2}\left(\mathbf{H} + \mathbf{H}^T\right) \quad [D]$$
- **Dynamic CIAAW Monoisotopic Mass Resolution (`DEF-04` `[M]`)**:
  - Terrestrial average atomic weights from standard chemistry tables (e.g. standard `mendeleev.element(Z).mass`) break quantal point-group symmetries ($C_{2v}, C_{3v}, D_{6h}$), split degenerate normal modes, and induce systematic shifts of $5\text{--}30\,\text{cm}^{-1}$.
  - Every nuclear mass $m_i$ must be resolved dynamically at runtime as the pure monoisotopic mass of the most abundant stable isotope via `mendeleev.element(int(Z)).isotopes` (e.g. $^{1}\text{H} = 1.00782503223\,\text{u}$, $^{12}\text{C} = 12.0000000000\,\text{u}$, $^{14}\text{N} = 14.0030740044\,\text{u}$, $^{16}\text{O} = 15.9949146196\,\text{u}$, $^{35}\text{Cl} = 34.968852721\,\text{u}$). Hardcoded mass tables or average atomic weights are strictly banned.
- **Mass-Weighted Hessian Transformation**:
  $$\tilde{H}_{i\alpha, j\beta} = \frac{H_{i\alpha, j\beta}}{\sqrt{m_i m_j}} \quad [D]$$
  Eigenvalues $\lambda_k$ carry physical units of $\text{eV}/(\text{\AA}^2 \cdot \text{u})$.
- **Explicit Gram-Schmidt Eckart Projection Operator (`DEF-05` `[D]`)**:
  1. Center of Mass Translation:
     $$\mathbf{R}_{\text{COM}} = \frac{\sum_{i=1}^N m_i \mathbf{r}_i}{\sum_{i=1}^N m_i} \quad [D]$$
  2. Mass-weighted translation basis vectors ($\mathbf{T}_\alpha \in \mathbb{R}^{3N}$, $\alpha \in \{x, y, z\}$):
     $$(\mathbf{T}_\alpha)_{i\beta} = \sqrt{m_i} \delta_{\alpha\beta} \quad [D]$$
  3. Mass-weighted rotation basis vectors ($\mathbf{R}_\alpha \in \mathbb{R}^{3N}$, $\alpha \in \{x, y, z\}$):
     $$(\mathbf{R}_\alpha)_i = \sqrt{m_i} \left( \mathbf{e}_\alpha \times (\mathbf{r}_i - \mathbf{R}_{\text{COM}}) \right) \quad [D]$$
  4. Sequential Gram-Schmidt orthonormalization of the 6 basis vectors $\{\mathbf{T}_x, \mathbf{T}_y, \mathbf{T}_z, \mathbf{R}_x, \mathbf{R}_y, \mathbf{R}_z\}$, discarding null vectors ($\|\mathbf{v}\| < 10^{-7}$) to yield transformation matrix $\mathbf{U} \in \mathbb{R}^{3N \times D}$ ($D=6$ for non-linear molecules, $D=5$ for linear molecules) with $\mathbf{U}^T \mathbf{U} = \mathbf{I}_D$.
  5. Eckart Projection Operator:
     $$\mathbf{P} = \mathbf{I}_{3N} - \mathbf{U} \mathbf{U}^T \quad [D]$$
     Satisfies idempotency $\mathbf{P}^2 = \mathbf{P}$, symmetry $\mathbf{P}^T = \mathbf{P}$, and rank $\operatorname{Tr}(\mathbf{P}) = 3N - D$.
  6. Projected Mass-Weighted Hessian:
     $$\tilde{\mathbf{H}}_{\text{proj}} = \mathbf{P} \tilde{\mathbf{H}} \mathbf{P} \quad [D]$$
     Diagonalization via `torch.linalg.eigh` produces exactly $D$ zero eigenvalues ($|\lambda| < 10^{-7}\,\text{eV}/(\text{\AA}^2\cdot\text{u})$) and $3N - D$ non-zero normal mode eigenvalues $\lambda_k$.
- **CODATA 2022 Physical Constants & Signed Frequencies (`DEF-03` `[M]`/`[D]`)**:
  - Fundamental constants:
    * $1\,\text{eV} = 1.602176634 \times 10^{-19}\,\text{J}$ `[M]`
    * $1\,\text{\AA} = 10^{-10}\,\text{m}$ `[M]`
    * $1\,\text{u} = 1.66053906660 \times 10^{-27}\,\text{kg}$ `[M]`
    * $c = 2.99792458 \times 10^{10}\,\text{cm/s}$ `[M]`
    * $h = 4.135667696 \times 10^{-15}\,\text{eV}\cdot\text{s}$ `[M]`
  - Dimensional conversion factor $\kappa$:
    $$\kappa = \frac{1.602176634 \times 10^{-19}}{(10^{-10})^2 \times 1.66053906660 \times 10^{-27}} = 9.648533212331 \times 10^{27}\,\text{s}^{-2}/(\text{eV}\cdot\text{\AA}^{-2}\cdot\text{u}^{-1}) \quad [D]$$
  - Spectroscopic wavenumber prefactor:
    $$\mathcal{C}_{\text{freq}} = \frac{\sqrt{\kappa}}{2\pi c} = 521.4708316\,\text{cm}^{-1} / \sqrt{\text{eV}/(\text{\AA}^2\cdot\text{u})} \quad [D]$$
  - **Signed Imaginary Frequency Reporting (Transition States)**:
    Evaluating $\sqrt{\lambda_k}$ when $\lambda_k < 0$ causes IEEE-754 `NaN` domain errors. The specification mandates signed reporting:
    $$\tilde{\nu}_k = \operatorname{sgn}(\lambda_k) \mathcal{C}_{\text{freq}} \sqrt{|\lambda_k|} \quad [D]$$
    where $\tilde{\nu}_k < 0$ reports transition-state imaginary frequencies without `NaN`.
- **Harmonic Zero-Point Vibrational Energy (ZPVE)**:
  $$E_{\text{ZPE}} = \frac{1}{2} \sum_{k: \lambda_k > 0} h c \tilde{\nu}_k \quad (\text{in eV}) \quad [D]$$
  Summed strictly over real, bound modes ($\lambda_k > 0$).

---

#### 4. PyTorch 2.0+ TorchDynamo ONNX Edge-Export Pipeline (`REQ-TORQ-INF-304` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_onnx_export.py` (and export in `Libraries/__init__.py`)
- **Resolution of the Autograd ONNX Serialization Roadblock (`DEF-07` `[D]`)**:
  - Legacy TorchScript tracing (`torch.onnx.export`) fails on `torch.autograd.grad`, throwing `RuntimeError: Cannot insert PythonException`.
  - Implement export via **TorchDynamo ONNX Exporter with AOTAutograd** (`torch.onnx.dynamo_export` unrolling reverse-mode automatic differentiation into static forward primitive math operators) OR provide the **Direct Analytical Equivariant Force Head** option.
- **Dynamic Axes Specification Covering 3D Tensors & `edge_index` (`DEF-07` `[D]`/`[E]`)**:
  ```python
  dynamic_axes = {
      # 3D Coordinate tensor: [batch_size, num_atoms, spatial_dim=3]
      "coordinates": {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"},
      # 2D Atomic numbers: [batch_size, num_atoms]
      "atomic_numbers": {0: "batch_size", 1: "num_atoms"},
      # 2D Graph connectivity edge index: [2, num_edges]
      "edge_index": {0: "edge_direction", 1: "num_edges"},
      # Scalar outputs: [batch_size]
      "energy": {0: "batch_size"},
      "homo_lumo_gap": {0: "batch_size"},
      # 3D Force tensor: [batch_size, num_atoms, spatial_dim=3]
      "forces": {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"},
  }
```
- **Opset Version & Parity Verification**:
  - Target ONNX opset version $\ge 17$ (recommended Opset 18 `[E]`). Opset $< 17$ raises `OpsetUnsupportedError`.
  - Numerical parity validation comparing PyTorch graph evaluations ($Y_{\text{torch}}$) against ONNX Runtime `InferenceSession` outputs ($Y_{\text{onnx}}$) across identical physical geometries:
    $$\max |Y_{\text{torch}} - Y_{\text{onnx}}| < 1.0 \times 10^{-5} \quad [M]$$
  - Exported binaries must load cleanly inside an isolated ONNX Runtime environment completely independent of native PyTorch runtime or GPU driver libraries.

---

### 4. DYNAMIC MENDELEEV CIAAW MONOISOTOPIC MASS UTILITY

Implement and export the CIAAW monoisotopic mass resolution helper:

```python
import mendeleev
from Libraries.cochem_torq_inference_errors import PhysicsDivergenceError


def resolve_ciaaw_monoisotopic_mass(atomic_number: int) -> float:
  """Retrieve pure CIAAW monoisotopic mass for the most abundant isotope of element Z [M].

  Queries mendeleev.element(Z).isotopes and filters by maximum terrestrial
  isotopic abundance. Standard terrestrial average weights are strictly
  forbidden.
  """
  elem = mendeleev.element(int(atomic_number))
  isotopes = [
      iso
      for iso in elem.isotopes
      if iso.abundance is not None and iso.abundance > 0.0
  ]
  if not isotopes:
    isotopes = elem.isotopes
  if not isotopes:
    raise PhysicsDivergenceError(
        f"No isotopic mass records available for atomic number"
        f" Z={atomic_number}."
    )
  most_abundant = max(isotopes, key=lambda iso: iso.abundance or 0.0)
  if most_abundant.mass is None:
    raise PhysicsDivergenceError(
        f"CIAAW mass undefined for element {elem.symbol} (Z={atomic_number})."
    )
  return float(most_abundant.mass)
```

---

### 5. AUTHENTIC MOLECULAR TEST FIXTURES & VERIFICATION SUITE

All test suites under `tests/` must ingest genuine physical molecular coordinates without mocks, dummy loops, or synthetic stubs.

#### 1. Embedded Authentic Molecular Geometries:
```python
import torch

# Authentic C2v equilibrium geometry for Water (H2O) [M]
H2O_COORDS = torch.tensor(
    [
        [0.0000000, 0.0000000, 0.1173000],  # O
        [0.0000000, 0.7572000, -0.4692000],  # H1
        [0.0000000, -0.7572000, -0.4692000],  # H2
    ],
    dtype=torch.float64,
)
H2O_Z = [8, 1, 1]

# Authentic equilibrium geometry for Methanol (CH3OH, N=6) [M]
METHANOL_COORDS = torch.tensor(
    [
        [-0.0466000, 0.6646000, 0.0000000],  # C
        [-0.0466000, -0.7543000, 0.0000000],  # O
        [0.8400000, -1.0805000, 0.0000000],  # H_O
        [-1.0772000, 1.0268000, 0.0000000],  # H1
        [0.4578000, 1.0538000, 0.8918000],  # H2
        [0.4578000, 1.0538000, -0.8918000],  # H3
    ],
    dtype=torch.float64,
)
METHANOL_Z = [6, 8, 1, 1, 1, 1]
```

#### 2. Analytical Molecular Potential Functions:
```python
import math
import torch


def h2o_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
  """Harmonic valence force field for Water (H2O) in eV [D].

  Equilibrium parameters: r_e = 0.9578 A, theta_e = 104.5 deg. kb = 48.0
  eV/A^2, kt = 5.0 eV/rad^2.
  """
  r_O = coords[0]
  r_H1 = coords[1]
  r_H2 = coords[2]

  r1 = torch.linalg.norm(r_H1 - r_O)
  r2 = torch.linalg.norm(r_H2 - r_O)

  v1 = (r_H1 - r_O) / r1
  v2 = (r_H2 - r_O) / r2
  cos_theta = torch.clamp(torch.dot(v1, v2), -1.0, 1.0)
  theta = torch.acos(cos_theta)

  r0 = 0.9578
  theta0 = 104.5 * math.pi / 180.0
  kb = 48.0
  kt = 5.0

  e_str = 0.5 * kb * ((r1 - r0) ** 2 + (r2 - r0) ** 2)
  e_bend = 0.5 * kt * ((theta - theta0) ** 2)
  return e_str + e_bend


def methanol_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
  """Harmonic bonded potential for Methanol (CH3OH) in eV [D].

  C=0, O=1, H_O=2, H1=3, H2=4, H3=5.
  """
  r_C = coords[0]
  r_O = coords[1]
  r_HO = coords[2]
  r_H1 = coords[3]
  r_H2 = coords[4]
  r_H3 = coords[5]

  r_CO = torch.linalg.norm(r_C - r_O)
  r_OH = torch.linalg.norm(r_O - r_HO)
  r_CH1 = torch.linalg.norm(r_C - r_H1)
  r_CH2 = torch.linalg.norm(r_C - r_H2)
  r_CH3 = torch.linalg.norm(r_C - r_H3)

  k_co = 35.0
  k_oh = 48.0
  k_ch = 32.0

  e_bonds = (
      0.5 * k_co * (r_CO - 1.42) ** 2
      + 0.5 * k_oh * (r_OH - 0.96) ** 2
      + 0.5 * k_ch * (r_CH1 - 1.09) ** 2
      + 0.5 * k_ch * (r_CH2 - 1.09) ** 2
      + 0.5 * k_ch * (r_CH3 - 1.09) ** 2
  )

  v_OC = (r_C - r_O) / r_CO
  v_OH = (r_HO - r_O) / r_OH
  cos_coh = torch.clamp(torch.dot(v_OC, v_OH), -1.0, 1.0)
  theta_coh = torch.acos(cos_coh)
  e_angle = 0.5 * 4.5 * (theta_coh - (108.5 * math.pi / 180.0)) ** 2

  return e_bonds + e_angle
```

#### 3. Test Suite Requirements (`tests/test_chunk20_verification_suite.py`):
1. `test_ciaaw_monoisotopic_vs_average_mass`: Assert monoisotopic masses diverge from terrestrial average atomic weights (especially $^{35}\text{Cl}$ with $|35.45 - 34.96885| > 0.4\,\text{u}$).
2. `test_multitask_homoscedastic_huber_loss`: Assert log-variance formulation $s_E, s_G$ computes finite, positive loss and verifies analytical gradients during backward pass.
3. `test_finite_difference_float64_enforcement_and_precision`: Verify Water forces satisfy $L_\infty < 10^{-4}\,\text{eV/\AA}$ and relative Frobenius norm $< 10^{-4}$ in `torch.float64`.
4. `test_finite_difference_float32_rejection`: Assert attempting finite differences in `torch.float32` immediately raises `NumericalParityError`.
5. `test_eckart_projector_idempotency_and_symmetry`: Assert Eckart projector satisfies $\max |P^2 - P| < 10^{-14}$, $\max |P - P^T| < 10^{-14}$, and trace equals $3N - 6 = 3$ for Water.
6. `test_vibrational_frequencies_water_codata_scaling`: Assert CODATA 2022 factor $\kappa$ yields physical frequencies for Water (bend $\approx 1500\text{--}2000\,\text{cm}^{-1}$, symmetric/asymmetric stretches $\approx 3500\text{--}4000\,\text{cm}^{-1}$), 0 imaginary modes, and $E_{\text{ZPE}} > 0$.
7. `test_signed_imaginary_frequency_reporting`: On inverted transition-state potential, assert imaginary modes report as signed negative wavenumbers ($\tilde{\nu} < 0$) without IEEE-754 `NaN`.
8. `test_apple_silicon_mps_float64_cpu_fallback`: Assert device dispatcher routes `("mps", torch.float64)` requests safely to CPU.
9. `test_hpc_distributed_lock_prohibition_staging`: Assert SLURM environment stages temporary scratch files to `$SLURM_TMPDIR/cochem_torq_scratch`.
10. `test_pydantic_v2_validation_and_contracts`: Test Pydantic schemas trap dimension errors, non-positive HOMO-LUMO gaps, and validate correct payloads.
11. `test_methanol_finite_difference_and_modes`: Test 6-atom Methanol benchmark confirms $3N - 6 = 12$ vibrational modes and passes finite differences under $10^{-4}\,\text{eV/\AA}$.
12. `test_onnx_export_spec_validation`: Test ONNX dynamic axes specification includes 3D coordinate/force tensors, 2D `edge_index`, and traps opset $< 17$ with `OpsetUnsupportedError`.

---

### 6. ACTION PLAN FOR CODER

1. Implement `Libraries/cochem_torq_inference_errors.py` providing the custom exception class hierarchy rooted in `CoChemTorqError` without empty `pass` blocks.
2. Implement `Libraries/cochem_torq_inference_schemas.py` providing Pydantic v2 data models (`MultiTaskPrediction`, `FiniteDiffVerificationResult`, `VibrationalModes`, `ONNXExportSpec`).
3. Implement `Libraries/cochem_torq_multitask.py` featuring log-variance homoscedastic loss, task-specific smooth Huber loss envelopes, and analytical gradient tracking.
4. Implement `Libraries/cochem_torq_finite_difference.py` featuring machine-precision finite differences with strict `torch.float64` enforcement.
5. Implement `Libraries/cochem_torq_vibrational.py` implementing double-autograd Cartesian Hessians, dynamic CIAAW monoisotopic mass retrieval, Gram-Schmidt Eckart projection, CODATA 2022 dimensional scaling, and signed frequency reporting.
6. Implement `Libraries/cochem_torq_onnx_export.py` implementing TorchDynamo AOTAutograd export and dynamic axes specification.
7. Implement `Libraries/cochem_torq_environment.py` implementing `dispatch_device_safely` (Apple Silicon MPS `float64` fallback) and `resolve_hpc_safe_scratch` (HPC Distributed Lock Prohibition rule).
8. Export all public functions, classes, and exceptions in `Libraries/__init__.py`.
9. Implement the complete, mock-free test suite `tests/test_chunk20_verification_suite.py` exercising authentic $\text{H}_2\text{O}$ and $\text{CH}_3\text{OH}$ benchmarks.
10. Execute `pytest tests/test_chunk20_verification_suite.py -v` and confirm 12/12 test fixtures pass with exit code 0.
I have invoked the `cochem-audit` subagent to conduct an adversarial compliance audit on the generated chunked coding prompt for `SRS_Chunk_20_TORQ_Inference_and_Export_Part_3`. Standing by for the auditor's certification.
I have copied the remediated prompt artifact to the canonical repository destination and notified `cochem-audit` for final council certification. Standing by for the audit verdict.
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous multi-task learning head (HOMO-LUMO gap and total potential energy), machine-precision central finite-difference gradient verification suite, double-autograd Cartesian Hessian calculator with dynamic CIAAW monoisotopic masses, Gram-Schmidt Eckart translational/rotational projection, CODATA 2022-scaled signed vibrational frequency analyzer, and PyTorch 2.0+ TorchDynamo ONNX edge-export pipeline with 3D dynamic axes and molecular graph connectivity specified in Software Requirements Specification (SRS) Chunk 20: `TORQ_Inference_and_Export_Part_3` (`COCHEM-SRS-CHUNK-20-TORQ`).

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev monoisotopic mass retrieval mandate, and Method Matrix v4 (`[M]` Empirical Benchmark, `[D]` Derived Mathematical Relationship, `[E]` Estimated Theoretical Projection). Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine physical tensors, authentic molecular coordinates, and real chemical observables.

---

### 1. DIRECTORY, PERSISTENCE & 6-TIER RUNTIME CONTRACTS

1. **Tripartite Workspace Air-Gap Paths**:
   - `COCHEM_SRC_DIR` ($R_{\text{src}}$): `pathlib.Path(os.environ.get("COCHEM_SRC_DIR", Path.cwd()))` (Read-only source repository).
   - `COCHEM_DATA_DIR` ($R_{\text{data}}$): `pathlib.Path(os.environ.get("COCHEM_DATA_DIR", Path.home() / ".cochem" / "data"))` (Read-only datasets, reference tables, and weights under `COCHEM_OFFLINE=1`).
   - `COCHEM_ARTIFACTS_DIR` ($R_{\text{art}}$): `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR", Path.home() / ".cochem" / "artifacts"))` (Read-write checkpoints, vibrational frequency reports, ONNX binaries, manifests, logs, and telemetry).
   - `COCHEM_SCRATCH_DIR`: `pathlib.Path(os.environ.get("COCHEM_SCRATCH_DIR", os.environ.get("SLURM_TMPDIR", Path.home() / ".cochem" / "scratch")))`.
2. **6-Tier Runtime & Hardware Concurrency**:
   - **Accelerator Binding & Safe Device Dispatcher**:
     * Query hardware availability: NVIDIA CUDA (`torch.cuda.is_available()`), Apple Silicon Metal Performance Shaders (`getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()`), or CPU.
     * **Apple Silicon MPS `float64` Automatic Fallback Rule (`DEF-10` `[M]`)**: Metal Performance Shaders (MPS) hardware architecture does not support native 64-bit floating point (`torch.float64`). Attempting to allocate or compute `float64` tensors on `mps` raises an immediate `TypeError: Cannot convert a MPS tensor to float64`. When executing high-precision routines (finite-difference verification, double-autograd Hessians, Eckart projections, eigensolvers) requiring `torch.float64`, the dispatcher must automatically intercept and route execution to `cpu`. Single-precision `float32` inference remains on `mps`.
     * Dynamic hardware detection must never hardcode device ordinals (e.g., `cuda:0` is strictly banned).
   - **Strict Tensor Precision & Dtype Synchronization**:
     * Mandatory `torch.float64` (`torch.double`, 53-bit significand) across all coordinate inputs, energy evaluations, finite differences, mass weighting, and eigensolvers (`DEF-06` `[M]`). Single precision (`torch.float32`) is restricted strictly to inference-only deployment where analytical forces are evaluated directly.
   - **Thread-Safe Storage & Concurrency**:
     * **HPC Distributed Lock Prohibition Rule (`DEF-10` `[M]`)**: On Tier 6 HPC environments, parallel network filesystems (Lustre, GPFS, BeeGFS, NFS) rely on centralized distributed lock managers. Direct `filelock.FileLock` across parallel filesystems causes lock manager deadlocks (`[Errno 37] No locks available`). Unconditional `filelock.FileLock` on parallel network filesystems is strictly prohibited. All staging, locking, and temporary files must be resolved dynamically to the node-local NVMe scratch directory `$SLURM_TMPDIR` (or `$TMPDIR`) via `resolve_hpc_safe_scratch()`.
     * Atomic state updates on shared storage must use atomic rename sidecars (`tempfile.NamedTemporaryFile` in local scratch committed via `os.replace`).
     * On single-node environments (Tiers 1-5), local file locking via `filelock.FileLock(lock_path, timeout=30.0)` is permitted.
     * HDF5 datasets and `PESStore` operate under Single-Writer Multiple-Reader (`libver='latest'`, `swmr=True`).
   - **Atomic Serialization**: Write temporary file `.tmp`, flush to disk with `os.fsync(f.fileno())`, atomically replace via `os.replace`, and write an accompanying cryptographic `.sha256` digest file.
3. **OS-Agnostic Dynamic Paths**: All filesystem operations are mediated via `pathlib.Path`. Hardcoded OS path separators (`/`, `\`), `$HOME`, or `C:\` are strictly prohibited.

---

### 2. DOMAIN EXCEPTIONS & PYDANTIC V2 DATA CONTRACTS

- **Files**: `Libraries/cochem_torq_inference_errors.py` and `Libraries/cochem_torq_inference_schemas.py` (and export in `Libraries/__init__.py`).
- **Domain Exception Hierarchy**:
  ```python
  from typing import Any, Dict, Optional


  class CoChemTorqError(Exception):
    """Root base exception for all CoChem-TORQ runtime operations [M]."""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_GENERIC_ERROR",
        component: str = "inference_export",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
      super().__init__(message)
      self.error_code = error_code
      self.component = component
      self.diagnostics = diagnostics or {}


  class PhysicsDivergenceError(CoChemTorqError):
    """Raised when fundamental physical invariants are violated (non-positive gap, negative mass, unphysical ZPVE) [M]."""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_PHYSICS_DIVERGENCE",
        component: str = "physical_invariants",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
      super().__init__(
          message,
          error_code=error_code,
          component=component,
          diagnostics=diagnostics,
      )


  class NumericalParityError(CoChemTorqError):
    """Raised when finite-difference gradients diverge from analytical forces beyond acceptance tolerance or float32 is detected [M]."""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_NUMERICAL_PARITY_ERROR",
        component: str = "finite_difference",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
      super().__init__(
          message,
          error_code=error_code,
          component=component,
          diagnostics=diagnostics,
      )


  class ConcurrencyLockError(CoChemTorqError):
    """Raised when filesystem locking fails or HPC distributed lock prohibitions are violated on shared filesystems [M]."""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_CONCURRENCY_LOCK_ERROR",
        component: str = "environment_concurrency",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
      super().__init__(
          message,
          error_code=error_code,
          component=component,
          diagnostics=diagnostics,
      )


  class OpsetUnsupportedError(CoChemTorqError):
    """Raised when an unsupported ONNX opset (< 17) or invalid autograd export pipeline is invoked [M]."""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_OPSET_UNSUPPORTED",
        component: str = "onnx_export",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
      super().__init__(
          message,
          error_code=error_code,
          component=component,
          diagnostics=diagnostics,
      )
```

- **Pydantic v2 Data Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
  ```python
  from typing import Dict, List
  from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


  class MultiTaskPrediction(BaseModel):
    """Encapsulates multi-task predictions for potential energy, forces, and HOMO-LUMO gap."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    energy: float = Field(
        ..., description="Molecular potential energy in eV [M]"
    )
    forces: List[List[float]] = Field(
        ...,
        description=(
            "Atomic Cartesian forces [N, 3] in eV/Angstrom [M]"
        ),
    )
    homo_lumo_gap: float = Field(
        ...,
        gt=0.0,
        description="Fundamental HOMO-LUMO electronic gap in eV [M]",
    )
    energy_log_variance: float = Field(
        ..., description="Task log-variance s_E = log(sigma_E^2) [D]"
    )
    gap_log_variance: float = Field(
        ..., description="Task log-variance s_G = log(sigma_G^2) [D]"
    )

    @field_validator("forces")
    @classmethod
    def validate_forces_shape(cls, v: List[List[float]]) -> List[List[float]]:
      if not v or len(v) == 0:
        raise ValueError("Forces tensor cannot be empty.")
      for row in v:
        if len(row) != 3:
          raise ValueError(
              f"Each force vector must be 3D Cartesian [x, y, z], got dimension"
              f" {len(row)}."
          )
      return v


  class FiniteDiffVerificationResult(BaseModel):
    """Validation report certifying agreement between analytic and finite-difference forces."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_absolute_error: float = Field(
        ...,
        description=(
            "Maximum absolute force component error (L_infinity) in"
            " eV/Angstrom [M]"
        ),
    )
    relative_frobenius_error: float = Field(
        ..., description="Relative Frobenius norm error [M]"
    )
    step_size: float = Field(
        ..., description="Displacement step size h in Angstrom [E]"
    )
    passed: bool = Field(
        ...,
        description=(
            "True if within acceptance criteria (L_inf < 1e-4 eV/A) [M]"
        ),
    )
    dtype: str = Field(
        ...,
        description="Execution tensor precision, strictly torch.float64 [M]",
    )
    atom_count: int = Field(
        ...,
        ge=1,
        description="Number of atoms in the evaluated structure [M]",
    )


  class VibrationalModes(BaseModel):
    """Full normal mode report containing projected harmonic frequencies and zero-point energy."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    frequencies_cm1: List[float] = Field(
        ...,
        description=(
            "Signed harmonic vibrational frequencies in cm^-1 (nu < 0 for"
            " imaginary modes) [D]"
        ),
    )
    zero_point_energy_ev: float = Field(
        ...,
        ge=0.0,
        description="Harmonic Zero-Point Vibrational Energy (ZPVE) in eV [D]",
    )
    imaginary_mode_count: int = Field(
        ...,
        ge=0,
        description=(
            "Count of transition-state imaginary normal modes (nu < 0) [D]"
        ),
    )
    eigenvalues: List[float] = Field(
        ...,
        description=(
            "Mass-weighted Hessian eigenvalues in eV/(Angstrom^2 * u) [D]"
        ),
    )
    projected_degrees_of_freedom: int = Field(
        ...,
        description=(
            "Number of projected translational and rotational degrees of"
            " freedom (5 or 6) [D]"
        ),
    )
    mass_weighting_standard: str = Field(
        default="CIAAW_MONOISOTOPIC",
        description="Governing standard for isotopic masses [M]",
    )

    @model_validator(mode="after")
    def validate_mode_consistency(self) -> "VibrationalModes":
      actual_imaginary = sum(1 for f in self.frequencies_cm1 if f < 0.0)
      if self.imaginary_mode_count != actual_imaginary:
        raise ValueError(
            f"imaginary_mode_count mismatch: reported {self.imaginary_mode_count}, "
            f"but frequencies_cm1 contains {actual_imaginary} negative modes."
        )
      if len(self.frequencies_cm1) != len(self.eigenvalues):
        raise ValueError(
            f"Dimension mismatch between frequencies ({len(self.frequencies_cm1)}) "
            f"and eigenvalues ({len(self.eigenvalues)})."
        )
      return self


  class ONNXExportSpec(BaseModel):
    """Configuration specification governing TorchDynamo ONNX compilation and dynamic axes."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    opset_version: int = Field(
        ..., ge=17, description="Target ONNX opset version (>= 17) [E]"
    )
    export_mechanism: str = Field(
        ...,
        description=(
            "Export engine: dynamo_export_aot_autograd or"
            " direct_analytical_force_head [D]"
        ),
    )
    dynamic_axes: Dict[str, Dict[int, str]] = Field(
        ...,
        description=(
            "Dynamic axes dictionary covering 3D tensors and edge_index [D]"
        ),
    )
    precision: str = Field(
        ..., description="Model numerical precision: float32 or float64 [E]"
    )
```

---

### 3. MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Multi-Task Learning Head with Log-Variance Homoscedastic Loss (`REQ-TORQ-INF-301` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_multitask.py` (and export in `Libraries/__init__.py`)
- **Auxiliary Equivariant Regression Head**:
  - Integrate onto the shared invariant/equivariant representation backbone to predict total potential energy $E \in \mathbb{R}^{B \times 1}$ (in $\text{eV}$) and the fundamental frontier orbital gap $\Delta \epsilon_{\text{HL}} = \epsilon_{\text{LUMO}} - \epsilon_{\text{HOMO}} \in \mathbb{R}^{B \times 1}$ (in $\text{eV}$).
  - Strictly enforce $\Delta \epsilon_{\text{HL}} > 0$ via a smooth Softplus activation function ($\Delta \epsilon_{\text{HL}} = \operatorname{Softplus}(x) + \epsilon_{\text{gap}}$, where $\epsilon_{\text{gap}} = 10^{-4}\,\text{eV}$). If any predicted gap $\le 0$, raise `PhysicsDivergenceError`.
- **Log-Variance Homoscedastic Formulation (`DEF-08` `[D]`)**:
  - Directly optimizing raw task variances $\sigma_E, \sigma_G$ risks floating-point overflow (`Inf`) when $\sigma \to 0$ or domain violations when $\sigma < 0$. Task variances are reparameterized into unconstrained log-variances:
    $$s_E = \log(\sigma_E^2), \quad s_G = \log(\sigma_G^2) \quad [D]$$
  - Learnable parameters $s_E, s_G \in \mathbb{R}$ initialized at $s_{E, 0} = 0.0$ `[E]` and $s_{G, 0} = 0.0$ `[E]`.
- **Task-Specific Smooth Huber Loss Envelopes (`DEF-08` `[D]`/`[E]`)**:
  - Smooth Huber envelope:
    $$\mathcal{L}_{\text{Huber}}(y, y^*; \delta) = \begin{cases} \frac{1}{2}(y - y^*)^2, & \text{if } |y - y^*| \le \delta \\ \delta\left(|y - y^*| - \frac{1}{2}\delta\right), & \text{if } |y - y^*| > \delta \end{cases} \quad [D]$$
  - Threshold parameters:
    * Potential Energy: $\delta_E = 0.01\,\text{eV}$ ($\approx 0.23\,\text{kcal/mol}$, sub-chemical accuracy limit) `[E]`.
    * HOMO-LUMO Gap: $\delta_G = 0.05\,\text{eV}$ ($\approx 1.15\,\text{kcal/mol}$, optical band edge tolerance) `[E]`.
- **Joint Multi-Task Objective & Gradients**:
  $$\mathcal{L}_{\text{multi}} = \frac{1}{2} \exp(-s_E) \mathcal{L}_{\text{Huber}}(E, E^*; \delta_E) + \frac{1}{2} \exp(-s_G) \mathcal{L}_{\text{Huber}}(\Delta \epsilon_{\text{HL}}, \Delta \epsilon_{\text{HL}}^*; \delta_G) + \frac{1}{2}(s_E + s_G) \quad [D]$$
  - Exact analytical log-variance gradients:
    $$\frac{\partial \mathcal{L}_{\text{multi}}}{\partial s_E} = -\frac{1}{2}\exp(-s_E)\mathcal{L}_{\text{Huber}}(E, E^*; \delta_E) + \frac{1}{2} \quad [D]$$
    $$\frac{\partial \mathcal{L}_{\text{multi}}}{\partial s_G} = -\frac{1}{2}\exp(-s_G)\mathcal{L}_{\text{Huber}}(\Delta \epsilon_{\text{HL}}, \Delta \epsilon_{\text{HL}}^*; \delta_G) + \frac{1}{2} \quad [D]$$
    Equilibrium is attained dynamically when $\exp(s_k) = \mathcal{L}_{\text{Huber}, k}$.

---

#### 2. Machine-Precision Finite-Difference Gradient Verification (`REQ-TORQ-INF-302` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_finite_difference.py` (and export in `Libraries/__init__.py`)
- **Mathematical Formulation**:
  - Conservative analytical forces via automatic differentiation:
    $$\mathbf{F}_{\text{analytic}, i} = -\nabla_{\mathbf{R}_i} E(\mathbf{R}) \in \mathbb{R}^3 \quad [D]$$
  - Central two-point finite-difference numerical forces across all $3N$ degrees of freedom:
    $$F_{\text{num}, i\alpha} = -\frac{E(\mathbf{R} + h \mathbf{e}_{i\alpha}) - E(\mathbf{R} - h \mathbf{e}_{i\alpha})}{2h} \quad [D]$$
    where displacement parameter is fixed at $h = 1.0 \times 10^{-4}\,\text{\AA}$ `[E]`.
- **The float32 Subtractive Cancellation Disaster & float64 Mandate (`DEF-06` `[M]`/`[D]`)**:
  - In IEEE-754 single precision (`torch.float32`), $\epsilon_{\text{mach}} \approx 1.19 \times 10^{-7}$. Evaluating finite differences on a molecule with $|E| \approx 10^2\,\text{eV}$ yields numerical cancellation noise:
    $$\Delta F_{\text{num}} \approx \frac{\epsilon_{\text{mach}} |E|}{2h} \approx \frac{1.19 \times 10^{-7} \times 10^2}{2 \times 10^{-4}} \approx 5.95 \times 10^{-2}\,\text{eV/\AA} \quad [D]$$
    This noise ($0.06\,\text{eV/\AA}$) is 600 times larger than acceptance tolerances, causing unconditional failure.
  - **Mandatory Precision Guard**: Coordinates, energy evaluations, and forces must execute strictly in `torch.float64` (`torch.double`, 53-bit significand, $\epsilon_{\text{mach}} \approx 2.22 \times 10^{-16}$). In double precision, numerical subtraction noise is suppressed to $\approx 1.11 \times 10^{-10}\,\text{eV/\AA} \ll 1.0 \times 10^{-4}\,\text{eV/\AA}$.
  - Any input passed with `dtype != torch.float64` must raise an immediate `NumericalParityError`.
- **Acceptance Criteria**:
  1. $L_\infty$ Force Norm Metric:
     $$L_\infty = \max_{i \in \{1 \dots N\}, \alpha \in \{x, y, z\}} \left| F_{\text{analytic}, i\alpha} - F_{\text{num}, i\alpha} \right| < 1.0 \times 10^{-4}\,\text{eV/\AA} \quad [M]$$
  2. Relative Frobenius Norm Metric:
     $$\text{RelErr}_F = \frac{\|\mathbf{F}_{\text{analytic}} - \mathbf{F}_{\text{num}}\|_F}{\|\mathbf{F}_{\text{analytic}}\|_F + 10^{-12}} < 1.0 \times 10^{-4} \quad [M]$$
  - Return certified `FiniteDiffVerificationResult`. If tolerances are violated, raise `NumericalParityError`.

---

#### 3. Double-Autograd Cartesian Hessian, Dynamic CIAAW Masses, Eckart Projection & Vibrational Frequencies (`REQ-TORQ-INF-303` `[M]`/`[D]`)
- **File Target**: `Libraries/cochem_torq_vibrational.py` (and export in `Libraries/__init__.py`)
- **Double-Autograd Cartesian Hessian Construction**:
  - Full Cartesian Hessian $\mathbf{H} \in \mathbb{R}^{3N \times 3N}$ is evaluated via nested reverse-mode automatic differentiation in `torch.float64`:
    $$H_{i\alpha, j\beta} = \frac{\partial^2 E}{\partial R_{i\alpha} \partial R_{j\beta}} = -\frac{\partial F_{\text{analytic}, i\alpha}}{\partial R_{j\beta}} \quad [D]$$
    using `torch.autograd.grad(..., create_graph=True)`.
  - Active Hermitian symmetrization to eliminate numerical asymmetry:
    $$\mathbf{H} = \frac{1}{2}\left(\mathbf{H} + \mathbf{H}^T\right) \quad [D]$$
- **Dynamic CIAAW Monoisotopic Mass Resolution (`DEF-04` `[M]`)**:
  - Terrestrial average atomic weights from standard chemistry tables (e.g. standard `mendeleev.element(Z).mass`) break quantal point-group symmetries ($C_{2v}, C_{3v}, D_{6h}$), split degenerate normal modes, and induce systematic shifts of $5\text{--}30\,\text{cm}^{-1}$.
  - Every nuclear mass $m_i$ must be resolved dynamically at runtime as the pure monoisotopic mass of the most abundant stable isotope via `mendeleev.element(int(Z)).isotopes` (e.g. $^{1}\text{H} = 1.00782503223\,\text{u}$, $^{12}\text{C} = 12.0000000000\,\text{u}$, $^{14}\text{N} = 14.0030740044\,\text{u}$, $^{16}\text{O} = 15.9949146196\,\text{u}$, $^{35}\text{Cl} = 34.968852721\,\text{u}$). Hardcoded mass tables or average atomic weights are strictly banned.
- **Mass-Weighted Hessian Transformation**:
  $$\tilde{H}_{i\alpha, j\beta} = \frac{H_{i\alpha, j\beta}}{\sqrt{m_i m_j}} \quad [D]$$
  Eigenvalues $\lambda_k$ carry physical units of $\text{eV}/(\text{\AA}^2 \cdot \text{u})$.
- **Explicit Gram-Schmidt Eckart Projection Operator (`DEF-05` `[D]`)**:
  1. Center of Mass Translation:
     $$\mathbf{R}_{\text{COM}} = \frac{\sum_{i=1}^N m_i \mathbf{r}_i}{\sum_{i=1}^N m_i} \quad [D]$$
  2. Mass-weighted translation basis vectors ($\mathbf{T}_\alpha \in \mathbb{R}^{3N}$, $\alpha \in \{x, y, z\}$):
     $$(\mathbf{T}_\alpha)_{i\beta} = \sqrt{m_i} \delta_{\alpha\beta} \quad [D]$$
  3. Mass-weighted rotation basis vectors ($\mathbf{R}_\alpha \in \mathbb{R}^{3N}$, $\alpha \in \{x, y, z\}$):
     $$(\mathbf{R}_\alpha)_i = \sqrt{m_i} \left( \mathbf{e}_\alpha \times (\mathbf{r}_i - \mathbf{R}_{\text{COM}}) \right) \quad [D]$$
  4. Sequential Gram-Schmidt orthonormalization of the 6 basis vectors $\{\mathbf{T}_x, \mathbf{T}_y, \mathbf{T}_z, \mathbf{R}_x, \mathbf{R}_y, \mathbf{R}_z\}$, discarding null vectors ($\|\mathbf{v}\| < 10^{-7}$) to yield transformation matrix $\mathbf{U} \in \mathbb{R}^{3N \times D}$ ($D=6$ for non-linear molecules, $D=5$ for linear molecules) with $\mathbf{U}^T \mathbf{U} = \mathbf{I}_D$.
  5. Eckart Projection Operator:
     $$\mathbf{P} = \mathbf{I}_{3N} - \mathbf{U} \mathbf{U}^T \quad [D]$$
     Satisfies idempotency $\mathbf{P}^2 = \mathbf{P}$, symmetry $\mathbf{P}^T = \mathbf{P}$, and rank $\operatorname{Tr}(\mathbf{P}) = 3N - D$.
  6. Projected Mass-Weighted Hessian:
     $$\tilde{\mathbf{H}}_{\text{proj}} = \mathbf{P} \tilde{\mathbf{H}} \mathbf{P} \quad [D]$$
     Diagonalization via `torch.linalg.eigh` produces exactly $D$ zero eigenvalues ($|\lambda| < 10^{-7}\,\text{eV}/(\text{\AA}^2\cdot\text{u})$) and $3N - D$ non-zero normal mode eigenvalues $\lambda_k$.
- **CODATA 2022 Physical Constants & Signed Frequencies (`DEF-03` `[M]`/`[D]`)**:
  - Fundamental constants:
    * $1\,\text{eV} = 1.602176634 \times 10^{-19}\,\text{J}$ `[M]`
    * $1\,\text{\AA} = 10^{-10}\,\text{m}$ `[M]`
    * $1\,\text{u} = 1.66053906660 \times 10^{-27}\,\text{kg}$ `[M]`
    * $c = 2.99792458 \times 10^{10}\,\text{cm/s}$ `[M]`
    * $h = 4.135667696 \times 10^{-15}\,\text{eV}\cdot\text{s}$ `[M]`
  - Dimensional conversion factor $\kappa$:
    $$\kappa = \frac{1.602176634 \times 10^{-19}}{(10^{-10})^2 \times 1.66053906660 \times 10^{-27}} = 9.648533212331 \times 10^{27}\,\text{s}^{-2}/(\text{eV}\cdot\text{\AA}^{-2}\cdot\text{u}^{-1}) \quad [D]$$
  - Spectroscopic wavenumber prefactor:
    $$\mathcal{C}_{\text{freq}} = \frac{\sqrt{\kappa}}{2\pi c} = 521.4708316\,\text{cm}^{-1} / \sqrt{\text{eV}/(\text{\AA}^2\cdot\text{u})} \quad [D]$$
  - **Signed Imaginary Frequency Reporting (Transition States)**:
    Evaluating $\sqrt{\lambda_k}$ when $\lambda_k < 0$ causes IEEE-754 `NaN` domain errors. The specification mandates signed reporting:
    $$\tilde{\nu}_k = \operatorname{sgn}(\lambda_k) \mathcal{C}_{\text{freq}} \sqrt{|\lambda_k|} \quad [D]$$
    where $\tilde{\nu}_k < 0$ reports transition-state imaginary frequencies without `NaN`.
- **Harmonic Zero-Point Vibrational Energy (ZPVE)**:
  $$E_{\text{ZPE}} = \frac{1}{2} \sum_{k: \lambda_k > 0} h c \tilde{\nu}_k \quad (\text{in eV}) \quad [D]$$
  Summed strictly over real, bound modes ($\lambda_k > 0$).

---

#### 4. PyTorch 2.0+ TorchDynamo ONNX Edge-Export Pipeline (`REQ-TORQ-INF-304` `[M]`/`[D]`/`[E]`)
- **File Target**: `Libraries/cochem_torq_onnx_export.py` (and export in `Libraries/__init__.py`)
- **Resolution of the Autograd ONNX Serialization Roadblock (`DEF-07` `[D]`)**:
  - Legacy TorchScript tracing (`torch.onnx.export`) fails on `torch.autograd.grad`, throwing `RuntimeError: Cannot insert PythonException`.
  - Implement export via **TorchDynamo ONNX Exporter with AOTAutograd** (`torch.onnx.dynamo_export` unrolling reverse-mode automatic differentiation into static forward primitive math operators) OR provide the **Direct Analytical Equivariant Force Head** option.
- **Dynamic Axes Specification Covering 3D Tensors & `edge_index` (`DEF-07` `[D]`/`[E]`)**:
  ```python
  dynamic_axes = {
      # 3D Coordinate tensor: [batch_size, num_atoms, spatial_dim=3]
      "coordinates": {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"},
      # 2D Atomic numbers: [batch_size, num_atoms]
      "atomic_numbers": {0: "batch_size", 1: "num_atoms"},
      # 2D Graph connectivity edge index: [2, num_edges]
      "edge_index": {0: "edge_direction", 1: "num_edges"},
      # Scalar outputs: [batch_size]
      "energy": {0: "batch_size"},
      "homo_lumo_gap": {0: "batch_size"},
      # 3D Force tensor: [batch_size, num_atoms, spatial_dim=3]
      "forces": {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"},
  }
```
- **Opset Version & Parity Verification**:
  - Target ONNX opset version $\ge 17$ (recommended Opset 18 `[E]`). Opset $< 17$ raises `OpsetUnsupportedError`.
  - Numerical parity validation comparing PyTorch graph evaluations ($Y_{\text{torch}}$) against ONNX Runtime `InferenceSession` outputs ($Y_{\text{onnx}}$) across identical physical geometries:
    $$\max |Y_{\text{torch}} - Y_{\text{onnx}}| < 1.0 \times 10^{-5} \quad [M]$$
  - Exported binaries must load cleanly inside an isolated ONNX Runtime environment completely independent of native PyTorch runtime or GPU driver libraries.

---

### 4. DYNAMIC MENDELEEV CIAAW MONOISOTOPIC MASS UTILITY

Implement and export the CIAAW monoisotopic mass resolution helper:

```python
import mendeleev
from Libraries.cochem_torq_inference_errors import PhysicsDivergenceError


def resolve_ciaaw_monoisotopic_mass(atomic_number: int) -> float:
  """Retrieve pure CIAAW monoisotopic mass for the most abundant isotope of element Z [M].

  Queries mendeleev.element(Z).isotopes and filters by maximum terrestrial
  isotopic abundance. Standard terrestrial average weights are strictly
  forbidden.
  """
  elem = mendeleev.element(int(atomic_number))
  isotopes = [
      iso
      for iso in elem.isotopes
      if iso.abundance is not None and iso.abundance > 0.0
  ]
  if not isotopes:
    isotopes = elem.isotopes
  if not isotopes:
    raise PhysicsDivergenceError(
        f"No isotopic mass records available for atomic number"
        f" Z={atomic_number}."
    )
  most_abundant = max(isotopes, key=lambda iso: iso.abundance or 0.0)
  if most_abundant.mass is None:
    raise PhysicsDivergenceError(
        f"CIAAW mass undefined for element {elem.symbol} (Z={atomic_number})."
    )
  return float(most_abundant.mass)
```

---

### 5. AUTHENTIC MOLECULAR TEST FIXTURES & VERIFICATION SUITE

All test suites under `tests/` must ingest genuine physical molecular coordinates without mocks, dummy loops, or synthetic stubs.

#### 1. Embedded Authentic Molecular Geometries:
```python
import torch

# Authentic C2v equilibrium geometry for Water (H2O) [M]
H2O_COORDS = torch.tensor(
    [
        [0.0000000, 0.0000000, 0.1173000],  # O
        [0.0000000, 0.7572000, -0.4692000],  # H1
        [0.0000000, -0.7572000, -0.4692000],  # H2
    ],
    dtype=torch.float64,
)
H2O_Z = [8, 1, 1]

# Authentic equilibrium geometry for Methanol (CH3OH, N=6) [M]
METHANOL_COORDS = torch.tensor(
    [
        [-0.0466000, 0.6646000, 0.0000000],  # C
        [-0.0466000, -0.7543000, 0.0000000],  # O
        [0.8400000, -1.0805000, 0.0000000],  # H_O
        [-1.0772000, 1.0268000, 0.0000000],  # H1
        [0.4578000, 1.0538000, 0.8918000],  # H2
        [0.4578000, 1.0538000, -0.8918000],  # H3
    ],
    dtype=torch.float64,
)
METHANOL_Z = [6, 8, 1, 1, 1, 1]
```

#### 2. Analytical Molecular Potential Functions:
```python
import math
import torch


def h2o_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
  """Harmonic valence force field for Water (H2O) in eV [D].

  Equilibrium parameters: r_e = 0.9578 A, theta_e = 104.5 deg. kb = 48.0
  eV/A^2, kt = 5.0 eV/rad^2.
  """
  r_O = coords[0]
  r_H1 = coords[1]
  r_H2 = coords[2]

  r1 = torch.linalg.norm(r_H1 - r_O)
  r2 = torch.linalg.norm(r_H2 - r_O)

  v1 = (r_H1 - r_O) / r1
  v2 = (r_H2 - r_O) / r2
  cos_theta = torch.clamp(torch.dot(v1, v2), -1.0, 1.0)
  theta = torch.acos(cos_theta)

  r0 = 0.9578
  theta0 = 104.5 * math.pi / 180.0
  kb = 48.0
  kt = 5.0

  e_str = 0.5 * kb * ((r1 - r0) ** 2 + (r2 - r0) ** 2)
  e_bend = 0.5 * kt * ((theta - theta0) ** 2)
  return e_str + e_bend


def methanol_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
  """Harmonic bonded potential for Methanol (CH3OH) in eV [D].

  C=0, O=1, H_O=2, H1=3, H2=4, H3=5.
  """
  r_C = coords[0]
  r_O = coords[1]
  r_HO = coords[2]
  r_H1 = coords[3]
  r_H2 = coords[4]
  r_H3 = coords[5]

  r_CO = torch.linalg.norm(r_C - r_O)
  r_OH = torch.linalg.norm(r_O - r_HO)
  r_CH1 = torch.linalg.norm(r_C - r_H1)
  r_CH2 = torch.linalg.norm(r_C - r_H2)
  r_CH3 = torch.linalg.norm(r_C - r_H3)

  k_co = 35.0
  k_oh = 48.0
  k_ch = 32.0

  e_bonds = (
      0.5 * k_co * (r_CO - 1.42) ** 2
      + 0.5 * k_oh * (r_OH - 0.96) ** 2
      + 0.5 * k_ch * (r_CH1 - 1.09) ** 2
      + 0.5 * k_ch * (r_CH2 - 1.09) ** 2
      + 0.5 * k_ch * (r_CH3 - 1.09) ** 2
  )

  v_OC = (r_C - r_O) / r_CO
  v_OH = (r_HO - r_O) / r_OH
  cos_coh = torch.clamp(torch.dot(v_OC, v_OH), -1.0, 1.0)
  theta_coh = torch.acos(cos_coh)
  e_angle = 0.5 * 4.5 * (theta_coh - (108.5 * math.pi / 180.0)) ** 2

  return e_bonds + e_angle
```

#### 3. Test Suite Requirements (`tests/test_chunk20_verification_suite.py`):
1. `test_ciaaw_monoisotopic_vs_average_mass`: Assert monoisotopic masses diverge from terrestrial average atomic weights (especially $^{35}\text{Cl}$ with $|35.45 - 34.96885| > 0.4\,\text{u}$).
2. `test_multitask_homoscedastic_huber_loss`: Assert log-variance formulation $s_E, s_G$ computes finite, positive loss and verifies analytical gradients during backward pass.
3. `test_finite_difference_float64_enforcement_and_precision`: Verify Water forces satisfy $L_\infty < 10^{-4}\,\text{eV/\AA}$ and relative Frobenius norm $< 10^{-4}$ in `torch.float64`.
4. `test_finite_difference_float32_rejection`: Assert attempting finite differences in `torch.float32` immediately raises `NumericalParityError`.
5. `test_eckart_projector_idempotency_and_symmetry`: Assert Eckart projector satisfies $\max |P^2 - P| < 10^{-14}$, $\max |P - P^T| < 10^{-14}$, and trace equals $3N - 6 = 3$ for Water.
6. `test_vibrational_frequencies_water_codata_scaling`: Assert CODATA 2022 factor $\kappa$ yields physical frequencies for Water (bend $\approx 1500\text{--}2000\,\text{cm}^{-1}$, symmetric/asymmetric stretches $\approx 3500\text{--}4000\,\text{cm}^{-1}$), 0 imaginary modes, and $E_{\text{ZPE}} > 0$.
7. `test_signed_imaginary_frequency_reporting`: On inverted transition-state potential, assert imaginary modes report as signed negative wavenumbers ($\tilde{\nu} < 0$) without IEEE-754 `NaN`.
8. `test_apple_silicon_mps_float64_cpu_fallback`: Assert device dispatcher routes `("mps", torch.float64)` requests safely to CPU.
9. `test_hpc_distributed_lock_prohibition_staging`: Assert SLURM environment stages temporary scratch files to `$SLURM_TMPDIR/cochem_torq_scratch`.
10. `test_pydantic_v2_validation_and_contracts`: Test Pydantic schemas trap dimension errors, non-positive HOMO-LUMO gaps, and validate correct payloads.
11. `test_methanol_finite_difference_and_modes`: Test 6-atom Methanol benchmark confirms $3N - 6 = 12$ vibrational modes and passes finite differences under $10^{-4}\,\text{eV/\AA}$.
12. `test_onnx_export_spec_validation`: Test ONNX dynamic axes specification includes 3D coordinate/force tensors, 2D `edge_index`, and traps opset $< 17$ with `OpsetUnsupportedError`.

---

### 6. ACTION PLAN FOR CODER

1. Implement `Libraries/cochem_torq_inference_errors.py` providing the custom exception class hierarchy rooted in `CoChemTorqError` without empty `pass` blocks.
2. Implement `Libraries/cochem_torq_inference_schemas.py` providing Pydantic v2 data models (`MultiTaskPrediction`, `FiniteDiffVerificationResult`, `VibrationalModes`, `ONNXExportSpec`).
3. Implement `Libraries/cochem_torq_multitask.py` featuring log-variance homoscedastic loss, task-specific smooth Huber loss envelopes, and analytical gradient tracking.
4. Implement `Libraries/cochem_torq_finite_difference.py` featuring machine-precision finite differences with strict `torch.float64` enforcement.
5. Implement `Libraries/cochem_torq_vibrational.py` implementing double-autograd Cartesian Hessians, dynamic CIAAW monoisotopic mass retrieval, Gram-Schmidt Eckart projection, CODATA 2022 dimensional scaling, and signed frequency reporting.
6. Implement `Libraries/cochem_torq_onnx_export.py` implementing TorchDynamo AOTAutograd export and dynamic axes specification.
7. Implement `Libraries/cochem_torq_environment.py` implementing `dispatch_device_safely` (Apple Silicon MPS `float64` fallback) and `resolve_hpc_safe_scratch` (HPC Distributed Lock Prohibition rule).
8. Export all public functions, classes, and exceptions in `Libraries/__init__.py`.
9. Implement the complete, mock-free test suite `tests/test_chunk20_verification_suite.py` exercising authentic $\text{H}_2\text{O}$ and $\text{CH}_3\text{OH}$ benchmarks.
10. Execute `pytest tests/test_chunk20_verification_suite.py -v` and confirm 12/12 test fixtures pass with exit code 0.
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
]


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_inference_errors.py ---
"""Domain-specific typed exceptions for CoChem-TORQ Inference, Active Learning, and Export.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Absolutely no stubs or empty pass blocks.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class CoChemError(Exception):
    """Root exception for CoChem framework. [M]"""

    def __init__(self, message: str = "Generic CoChem error") -> None:
        super().__init__(message)
        self.message = message


class CoChemTorqError(CoChemError):
    """Base exception for all TORQ sub-framework operations. [M]"""

    def __init__(
        self,
        message: str = "Generic TORQ error",
        error_code: str = "TORQ_GENERIC_ERROR",
        component: str = "inference_export",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.component = component
        self.diagnostics = diagnostics or {}


class PhysicsDivergenceError(CoChemTorqError):
    """Raised when fundamental physical invariants are violated (non-positive gap, negative mass, unphysical ZPVE) [M]."""

    def __init__(
        self,
        message: str = "Physical invariant violation detected",
        error_code: str = "TORQ_PHYSICS_DIVERGENCE",
        component: str = "physical_invariants",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            component=component,
            diagnostics=diagnostics,
        )


class NumericalParityError(CoChemTorqError):
    """Raised when finite-difference gradients diverge from analytical forces beyond acceptance tolerance or float32 is detected [M]."""

    def __init__(
        self,
        message: str = "Numerical parity tolerance exceeded or unsupported precision",
        error_code: str = "TORQ_NUMERICAL_PARITY_ERROR",
        component: str = "finite_difference",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            component=component,
            diagnostics=diagnostics,
        )


class ConcurrencyLockError(CoChemTorqError):
    """Raised when filesystem locking fails or HPC distributed lock prohibitions are violated on shared filesystems [M]."""

    def __init__(
        self,
        message: str = "Filesystem locking failure or distributed lock prohibition violated",
        error_code: str = "TORQ_CONCURRENCY_LOCK_ERROR",
        component: str = "environment_concurrency",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            component=component,
            diagnostics=diagnostics,
        )


class OpsetUnsupportedError(CoChemTorqError):
    """Raised when an unsupported ONNX opset (< 17) or invalid autograd export pipeline is invoked [M]."""

    def __init__(
        self,
        message: str = "Unsupported ONNX opset or invalid autograd export pipeline",
        error_code: str = "TORQ_OPSET_UNSUPPORTED",
        component: str = "onnx_export",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            component=component,
            diagnostics=diagnostics,
        )


class TorqInferenceError(CoChemTorqError):
    """Base exception for all TORQ inference and export errors. [M]"""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_INF_GENERIC",
        component: str = "inference_engine",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            component=component,
            diagnostics=diagnostics,
        )


class ActiveLearningSelectionError(TorqInferenceError):
    """Raised when active learning selection or pool deduplication fails. [M]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_AL_SELECTION_ERR",
            component="active_learning",
            **kwargs,
        )


class HDF5DataModuleLockError(TorqInferenceError):
    """Raised when multi-worker HDF5 handle acquisition encounters lock timeout. [M]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_HDF5_LOCK_ERR",
            component="hdf5_datamodule",
            **kwargs,
        )


class EnsembleConsensusError(TorqInferenceError):
    """Raised when committee ensemble encounters dimension mismatch or consensus divergence. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_ENSEMBLE_ERR",
            component="committee_ensemble",
            **kwargs,
        )


class CutoffContinuityError(TorqInferenceError):
    """Raised when radial cutoff function violates C^2 smoothness or boundary zero condition. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message, error_code="TORQ_CUTOFF_ERR", component="c2_cutoff", **kwargs
        )


class GradientExplosionError(TorqInferenceError):
    """Raised when GNN message passing activations or gradients exceed stability threshold. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_GRAD_EXPLOSION_ERR",
            component="gnn_debugger",
            **kwargs,
        )


class VanishingGradientWarning(UserWarning):
    """Emitted when message passing gradients drop below minimum threshold across consecutive layers. [D]"""

    def __init__(
        self, message: str = "GNN message passing gradients vanishing"
    ) -> None:
        super().__init__(message)
        self.message = message


class PBCGraphError(TorqInferenceError):
    """Raised when periodic boundary condition graph construction or virial calculation fails. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_PBC_GRAPH_ERR",
            component="pbc_graph",
            **kwargs,
        )


class AirGapViolationError(TorqInferenceError):
    """Raised when inference or active learning loops attempt forbidden outbound networking or direct subprocess execution. [M]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_AIRGAP_ERR",
            component="airgap_sandbox",
            **kwargs,
        )


class HardwareDispatchError(TorqInferenceError):
    """Raised if hardware accelerator encounters unrecoverable runtime states without a valid fallback. [M]"""

    def __init__(
        self, message: str, diagnostics: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message,
            error_code="TORQ_HW_DISPATCH_FAIL",
            component="hardware_dispatcher",
            diagnostics=diagnostics,
        )


class AirGapIntegrityError(TorqInferenceError):
    """Raised if network sockets are opened during inference or if Ring 2 data SHA-256 hashes mismatch. [M]"""

    def __init__(
        self, message: str, diagnostics: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message,
            error_code="TORQ_AIRGAP_INTEGRITY_FAIL",
            component="airgap_enforcer",
            diagnostics=diagnostics,
        )


class ClashDetectedError(TorqInferenceError):
    """Raised during L-BFGS line-search if any interatomic distance drops below 0.7 Angstroms. [E]"""

    def __init__(
        self,
        message: str,
        min_distance: float,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        diags = dict(diagnostics or {})
        diags["min_distance_angstrom"] = float(min_distance)
        super().__init__(
            message,
            error_code="TORQ_GEOM_CLASH_DETECTED",
            component="lbfgs_optimizer",
            diagnostics=diags,
        )


class ConvergenceError(TorqInferenceError):
    """Raised if geometry optimization fails to reach Method Matrix force thresholds within maximum iterations. [M]"""

    def __init__(
        self,
        message: str,
        iterations: int,
        final_force: float,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        diags = dict(diagnostics or {})
        diags["iterations"] = int(iterations)
        diags["final_max_force"] = float(final_force)
        super().__init__(
            message,
            error_code="TORQ_LBFGS_NON_CONVERGENCE",
            component="lbfgs_optimizer",
            diagnostics=diags,
        )


class CalibrationSizeError(TorqInferenceError):
    """Raised in strict initialization mode if conformal calibration dataset size n < ceil((1 - alpha) / alpha). [M]"""

    def __init__(self, message: str, n_samples: int, n_required: int) -> None:
        super().__init__(
            message,
            error_code="TORQ_CONFORMAL_INSUFFICIENT_CALIBRATION",
            component="conformal_predictor",
            diagnostics={"n_samples": int(n_samples), "n_required": int(n_required)},
        )


class BaselineExecutionError(TorqInferenceError):
    """Raised when Delta-ML baseline calculation fails or returns non-physical values. [M]"""

    def __init__(
        self,
        message: str,
        method: str = "GFN2-xTB",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        diags = dict(diagnostics or {})
        diags["baseline_method"] = method
        super().__init__(
            message,
            error_code="TORQ_DELTA_BASELINE_FAIL",
            component="delta_ml_engine",
            diagnostics=diags,
        )


class DispersionParameterError(TorqInferenceError):
    """Raised when dispersion damping parameters or C6/C8 tables fail SHA-256 verification. [M]"""

    def __init__(
        self, message: str, expected_sha: str, calculated_sha: str
    ) -> None:
        super().__init__(
            message,
            error_code="TORQ_DISPERSION_PARAM_CORRUPT",
            component="dispersion_layer",
            diagnostics={
                "expected_sha256": expected_sha,
                "calculated_sha256": calculated_sha,
            },
        )


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_inference_schemas.py ---
"""Pydantic v2 schemas and data contracts for CoChem-TORQ Inference, Active Learning, and Export.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Strongly typed, validated configurations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, NamedTuple, Optional, Union
import torch
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActiveLearningOrchestratorConfig(BaseModel):
    """Configuration contract for the active learning acquisition and deduplication engine. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_capacity_k: int = Field(
        default=64,
        ge=1,
        le=512,
        description="Active learning batch selection capacity K [E]",
    )
    force_uncertainty_threshold_ev_per_angstrom: float = Field(
        default=0.05,
        gt=0.0,
        description="Epistemic force standard deviation threshold theta_force in eV/Angstrom [E]",
    )
    energy_uncertainty_threshold_ev2_per_atom: float = Field(
        default=0.001,
        gt=0.0,
        description="QBC energy variance threshold theta_energy in eV^2/atom [E]",
    )
    stage_a_rmsd_threshold_angstrom: float = Field(
        default=0.125,
        gt=0.0,
        description="Method Matrix v4 Stage A geometric RMSD threshold delta_RMSD [M]",
    )
    stage_b_rotational_threshold: float = Field(
        default=0.001,
        gt=0.0,
        description="Method Matrix v4 Stage B relative rotational constant invariance delta_B/B (--bthr) [M]",
    )
    triage_tier: Literal["T3-10s", "T3-1h", "T3-12h", "T3O-1h", "T3O-12h"] = Field(
        default="T3-10s",
        description="Initial baseline QM routing tier [M]",
    )
    staging_manifest_dir: Path = Field(
        ...,
        description="Air-gapped manifest export directory in Ring 3 [M]",
    )

    @model_validator(mode="before")
    @classmethod
    def remap_legacy_field_names(cls, data: Any) -> Any:
        """Support field name aliases across specification revisions. [D]"""
        if isinstance(data, dict):
            mapped = dict(data)
            if "force_uncertainty_threshold" in mapped and "force_uncertainty_threshold_ev_per_angstrom" not in mapped:
                mapped["force_uncertainty_threshold_ev_per_angstrom"] = mapped.pop("force_uncertainty_threshold")
            if "energy_uncertainty_threshold" in mapped and "energy_uncertainty_threshold_ev2_per_atom" not in mapped:
                mapped["energy_uncertainty_threshold_ev2_per_atom"] = mapped.pop("energy_uncertainty_threshold")
            if "rmsd_dedup_threshold_angstrom" in mapped and "stage_a_rmsd_threshold_angstrom" not in mapped:
                mapped["stage_a_rmsd_threshold_angstrom"] = mapped.pop("rmsd_dedup_threshold_angstrom")
            return mapped
        return data

    @property
    def force_uncertainty_threshold(self) -> float:
        """Alias for force_uncertainty_threshold_ev_per_angstrom. [D]"""
        return self.force_uncertainty_threshold_ev_per_angstrom

    @property
    def energy_uncertainty_threshold(self) -> float:
        """Alias for energy_uncertainty_threshold_ev2_per_atom. [D]"""
        return self.energy_uncertainty_threshold_ev2_per_atom

    @property
    def rmsd_dedup_threshold_angstrom(self) -> float:
        """Alias for stage_a_rmsd_threshold_angstrom. [D]"""
        return self.stage_a_rmsd_threshold_angstrom


class ChunkedHDF5DataModuleConfig(BaseModel):
    """Configuration contract for chunked HDF5 PyTorch Lightning DataModule. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    h5_path: Path = Field(..., description="Path to chunked HDF5 dataset [M]")
    batch_size: int = Field(default=32, ge=1, description="Batch size per device [M]")
    num_workers: int = Field(
        default=2, ge=0, description="Number of dataloader worker processes [M]"
    )
    chunk_cache_bytes: int = Field(
        default=16 * 1024 * 1024,
        ge=1024 * 1024,
        description="HDF5 raw data chunk cache size rdcc_nbytes [E]",
    )
    chunk_cache_slots: int = Field(
        default=10007,
        ge=1009,
        description="Prime number of chunk cache hash slots rdcc_nslots [D]",
    )
    pin_memory: bool = Field(
        default=True,
        description="Pin host memory for non-blocking GPU transfer [M]",
    )
    train_val_test_split: List[float] = Field(
        default=[0.8, 0.1, 0.1],
        description="Train, validation, and test split ratios [M]",
    )

    @model_validator(mode="after")
    def validate_splits(self) -> "ChunkedHDF5DataModuleConfig":
        """Verify train, val, and test splits sum to unity within tolerance. [D]"""
        if abs(sum(self.train_val_test_split) - 1.0) > 1e-5:
            raise ValueError("train_val_test_split must sum to 1.0")
        return self


class CommitteeEnsembleConfig(BaseModel):
    """Configuration contract for Committee Ensemble uncertainty wrapper. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    num_models_m: int = Field(
        default=8, ge=2, le=32, description="Number of committee models M [E]"
    )
    max_concurrent_models_vram: int = Field(
        default=2,
        ge=1,
        description="Maximum models loaded into active VRAM simultaneously [E]",
    )
    synchronize_cuda_streams: bool = Field(
        default=True,
        description="Execute stream synchronization between model forward passes [D]",
    )


class C2SmoothCutoffConfig(BaseModel):
    """Configuration contract for C^2-smooth radial cutoff envelope. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cutoff_radius_rc: float = Field(
        default=5.0,
        gt=1.0,
        description="Radial cutoff boundary radius r_c in Angstroms [M]",
    )
    polynomial_degree: Literal[5] = Field(
        default=5,
        description="Degree of C^2 continuous switching polynomial [D]",
    )


class GNNGradientDebuggerConfig(BaseModel):
    """Configuration contract for message-passing GNN gradient health debugger. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exploding_grad_threshold: float = Field(
        default=1e3, gt=0.0, description="L2 gradient norm explosion threshold [D]"
    )
    vanishing_grad_threshold: float = Field(
        default=1e-7, gt=0.0, description="L2 gradient norm vanishing threshold [D]"
    )
    consecutive_vanishing_blocks: int = Field(
        default=3,
        ge=1,
        description="Consecutive layers below vanishing threshold before alert [D]",
    )
    enabled: bool = Field(
        default=True, description="Enable active hook monitoring [M]"
    )


class PBCRadialGraphConfig(BaseModel):
    """Configuration contract for periodic boundary condition graph engine. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cutoff_radius_rc: float = Field(
        default=5.0,
        gt=1.0,
        description="Radial graph cutoff radius in Angstroms [M]",
    )
    compute_virial_stress: bool = Field(
        default=True,
        description="Compute analytical unit cell virial stress tensor [D]",
    )


class HPORunConfig(BaseModel):
    """Configuration contract for automated hyperparameter optimization. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    study_name: str = Field(
        ..., description="Unique identifier for the HPO study [M]"
    )
    n_trials: int = Field(
        default=100, ge=1, description="Total optimization trials [E]"
    )
    pruner: Literal["ASHA", "MedianPruner", "Hyperband"] = Field(
        default="ASHA", description="Pruning strategy [E]"
    )
    grace_period: int = Field(
        default=10, ge=1, description="Epochs before pruning evaluation [E]"
    )
    storage_uri: str = Field(
        ..., description="Storage backend URI (sqlite:///... or h5py) [M]"
    )
    w_energy: float = Field(
        default=1.0, ge=0.0, description="Potential energy loss weight [E]"
    )
    w_force: float = Field(
        default=10.0, ge=0.0, description="Atomic force loss weight [E]"
    )
    lr_min: float = Field(
        default=1e-5, gt=0.0, description="Lower bound for learning rate [E]"
    )
    lr_max: float = Field(
        default=1e-2, gt=0.0, description="Upper bound for learning rate [E]"
    )
    cutoff_min: float = Field(
        default=4.0, ge=1.0, description="Minimum cutoff radius in Angstroms [E]"
    )
    cutoff_max: float = Field(
        default=6.5, ge=1.0, description="Maximum cutoff radius in Angstroms [E]"
    )
    rbf_options: List[int] = Field(
        default=[16, 32, 64], description="Candidate RBF basis counts [E]"
    )
    depth_options: List[int] = Field(
        default=[3, 4, 5, 6], description="Candidate interaction depths [E]"
    )
    embedding_dim_options: List[int] = Field(
        default=[64, 128, 256],
        description="Candidate feature embedding dimensions [E]",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "HPORunConfig":
        """Verify learning rate and cutoff interval boundaries. [D]"""
        if self.lr_min >= self.lr_max:
            raise ValueError("lr_min must be strictly less than lr_max")
        if self.cutoff_min >= self.cutoff_max:
            raise ValueError("cutoff_min must be strictly less than cutoff_max")
        return self


class DeltaMLConfig(BaseModel):
    """Configuration contract for Delta-Learning architecture. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_method: Literal["GFN2-xTB", "PM6", "LennardJones", "EMT"] = Field(
        default="GFN2-xTB", description="Baseline physical engine [M]"
    )
    qm_target_method: str = Field(
        default="wB97M-V/def2-TZVP",
        description="High-level QM target benchmark [M]",
    )
    energy_unit: Literal["eV", "Hartree", "kcal/mol"] = Field(
        default="eV", description="Internal standard energy unit [D]"
    )
    length_unit: Literal["Angstrom", "Bohr"] = Field(
        default="Angstrom", description="Internal standard length unit [D]"
    )


class ConformalPredictorConfig(BaseModel):
    """Configuration contract for inductive conformal prediction uncertainty. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alpha: float = Field(
        default=0.05,
        gt=0.0,
        lt=1.0,
        description="Target miscoverage significance level [D]",
    )
    regularization_energy: float = Field(
        default=1e-6,
        gt=0.0,
        description="Numerical regularizer epsilon_E in eV [E]",
    )
    regularization_force: float = Field(
        default=1e-6,
        gt=0.0,
        description="Numerical regularizer epsilon_F in eV/Angstrom [E]",
    )
    strict_calibration_size: bool = Field(
        default=True,
        description=(
            "Raise CalibrationSizeError if calibration sample size is"
            " insufficient [M]"
        ),
    )
    apply_bonferroni: bool = Field(
        default=False,
        description=(
            "Apply Bonferroni correction for simultaneous joint 3N force bounds"
            " [D]"
        ),
    )


class LBFGSOptimizerConfig(BaseModel):
    """Configuration contract for L-BFGS geometry optimizer with Eckart projection. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_iterations: int = Field(
        default=500, ge=1, description="Maximum optimization iterations [M]"
    )
    history_size: int = Field(
        default=10, ge=1, description="Two-loop recursion memory depth [D]"
    )
    dtype: Literal["float64"] = Field(
        default="float64",
        description="Mandatory precision for geometry optimization [M]",
    )
    tol_max_g: float = Field(
        default=0.00051422,
        gt=0.0,
        description="Max force convergence threshold in eV/Angstrom [M]",
    )
    tol_rms_g: float = Field(
        default=0.00034453,
        gt=0.0,
        description="RMS force convergence threshold in eV/Angstrom [M]",
    )
    tol_max_d: float = Field(
        default=5.29177e-5,
        gt=0.0,
        description="Max displacement threshold in Angstroms [M]",
    )
    tol_rms_d: float = Field(
        default=3.54549e-5,
        gt=0.0,
        description="RMS displacement threshold in Angstroms [M]",
    )
    tol_energy: float = Field(
        default=2.72114e-5,
        gt=0.0,
        description="Energy change convergence threshold in eV [M]",
    )
    max_step: float = Field(
        default=0.1,
        gt=0.0,
        description="Maximum Cartesian step displacement in Angstroms [E]",
    )
    clash_distance: float = Field(
        default=0.7,
        gt=0.0,
        description="Clash distance abort threshold in Angstroms [E]",
    )
    c1: float = Field(
        default=1e-4,
        gt=0.0,
        lt=0.5,
        description="Strong Wolfe Armijo sufficient decrease parameter [D]",
    )
    c2: float = Field(
        default=0.9,
        gt=0.0,
        lt=1.0,
        description="Strong Wolfe curvature condition parameter [D]",
    )


class DispersionD3Config(BaseModel):
    """Configuration contract for Grimme D3 empirical dispersion layer. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    functional: str = Field(
        default="wB97M-V", description="Underlying DFT functional [M]"
    )
    damping: Literal["BJ", "zero"] = Field(
        default="BJ", description="Dispersion damping variant [D]"
    )
    s6: float = Field(default=1.0, ge=0.0, description="Dipole scale factor [E]")
    s8: float = Field(
        default=1.0, ge=0.0, description="Quadrupole scale factor [E]"
    )
    a1: float = Field(
        default=0.5, ge=0.0, description="Becke-Johnson damping parameter a1 [E]"
    )
    a2: float = Field(
        default=3.0, ge=0.0, description="Becke-Johnson damping parameter a2 [E]"
    )
    c9_cutoff: float = Field(
        default=16.0,
        gt=0.0,
        description="Three-body dispersion cutoff in Angstroms [E]",
    )
    pair_cutoff: float = Field(
        default=25.0,
        gt=0.0,
        description="Pairwise dispersion cutoff in Angstroms [E]",
    )
    data_manifest_sha256: str = Field(
        default="7dc504e705bf220fc0a014f21f18e02ad205cb68e714ca3aaec2c8b48fc7e327",
        description="SHA-256 checksum of Ring 2 dispersion table [M]",
    )



class NeighborListResult(NamedTuple):
    """Container for spatial neighbor list search results. [M]"""

    edge_index: torch.Tensor  # Shape: [2, num_edges], dtype: torch.int64
    edge_vector: torch.Tensor  # Shape: [num_edges, 3], dtype matches coordinates (float32/float64)
    edge_distance: torch.Tensor  # Shape: [num_edges], dtype matches coordinates (float32/float64)


class ConformalInterval(NamedTuple):
    """Container for rigorous conformal uncertainty intervals. [D]"""

    energy_lower: float  # Unit: eV
    energy_upper: float  # Unit: eV
    force_lower: torch.Tensor  # Shape: [N, 3], Unit: eV/Angstrom
    force_upper: torch.Tensor  # Shape: [N, 3], Unit: eV/Angstrom
    confidence_level: float  # 1 - alpha, e.g., 0.95


class LBFGSOptimizationState(BaseModel):
    """Telemetry and state snapshot of L-BFGS geometry optimization. [M]"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    converged: bool
    iterations: int
    final_energy: float  # Unit: eV
    max_force: float  # Unit: eV/Angstrom
    rms_force: float  # Unit: eV/Angstrom
    max_displacement: Optional[float] = None  # Unit: Angstrom
    rms_displacement: Optional[float] = None  # Unit: Angstrom
    energy_change: Optional[float] = None  # Unit: eV
    final_coordinates: Optional[torch.Tensor] = (
        None  # Shape: [N, 3], Unit: Angstrom
    )


class MultiTaskPrediction(BaseModel):
    """Encapsulates multi-task predictions for potential energy, forces, and HOMO-LUMO gap [M]."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    energy: float = Field(
        ..., description="Molecular potential energy in eV [M]"
    )
    forces: List[List[float]] = Field(
        ...,
        description="Atomic Cartesian forces [N, 3] in eV/Angstrom [M]",
    )
    homo_lumo_gap: float = Field(
        ...,
        gt=0.0,
        description="Fundamental HOMO-LUMO electronic gap in eV [M]",
    )
    energy_log_variance: float = Field(
        ..., description="Task log-variance s_E = log(sigma_E^2) [D]"
    )
    gap_log_variance: float = Field(
        ..., description="Task log-variance s_G = log(sigma_G^2) [D]"
    )

    @field_validator("forces")
    @classmethod
    def validate_forces_shape(cls, v: List[List[float]]) -> List[List[float]]:
        if not v or len(v) == 0:
            raise ValueError("Forces tensor cannot be empty.")
        for row in v:
            if len(row) != 3:
                raise ValueError(
                    f"Each force vector must be 3D Cartesian [x, y, z], got dimension {len(row)}."
                )
        return v


class FiniteDiffVerificationResult(BaseModel):
    """Validation report certifying agreement between analytic and finite-difference forces [M]."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_absolute_error: float = Field(
        ...,
        description="Maximum absolute force component error (L_infinity) in eV/Angstrom [M]",
    )
    relative_frobenius_error: float = Field(
        ..., description="Relative Frobenius norm error [M]"
    )
    step_size: float = Field(
        ..., description="Displacement step size h in Angstrom [E]"
    )
    passed: bool = Field(
        ...,
        description="True if within acceptance criteria (L_inf < 1e-4 eV/A) [M]",
    )
    dtype: str = Field(
        ...,
        description="Execution tensor precision, strictly torch.float64 [M]",
    )
    atom_count: int = Field(
        ...,
        ge=1,
        description="Number of atoms in the evaluated structure [M]",
    )


class VibrationalModes(BaseModel):
    """Full normal mode report containing projected harmonic frequencies and zero-point energy [D]."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    frequencies_cm1: List[float] = Field(
        ...,
        description="Signed harmonic vibrational frequencies in cm^-1 (nu < 0 for imaginary modes) [D]",
    )
    zero_point_energy_ev: float = Field(
        ...,
        ge=0.0,
        description="Harmonic Zero-Point Vibrational Energy (ZPVE) in eV [D]",
    )
    imaginary_mode_count: int = Field(
        ...,
        ge=0,
        description="Count of transition-state imaginary normal modes (nu < 0) [D]",
    )
    eigenvalues: List[float] = Field(
        ...,
        description="Mass-weighted Hessian eigenvalues in eV/(Angstrom^2 * u) [D]",
    )
    projected_degrees_of_freedom: int = Field(
        ...,
        description="Number of projected translational and rotational degrees of freedom (5 or 6) [D]",
    )
    mass_weighting_standard: str = Field(
        default="CIAAW_MONOISOTOPIC",
        description="Governing standard for isotopic masses [M]",
    )

    @model_validator(mode="after")
    def validate_mode_consistency(self) -> "VibrationalModes":
        actual_imaginary = sum(1 for f in self.frequencies_cm1 if f < 0.0)
        if self.imaginary_mode_count != actual_imaginary:
            raise ValueError(
                f"imaginary_mode_count mismatch: reported {self.imaginary_mode_count}, "
                f"but frequencies_cm1 contains {actual_imaginary} negative modes."
            )
        if len(self.frequencies_cm1) != len(self.eigenvalues):
            raise ValueError(
                f"Dimension mismatch between frequencies ({len(self.frequencies_cm1)}) "
                f"and eigenvalues ({len(self.eigenvalues)})."
            )
        return self


class ONNXExportSpec(BaseModel):
    """Configuration specification governing TorchDynamo ONNX compilation and dynamic axes [D]."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    opset_version: int = Field(
        ..., ge=17, description="Target ONNX opset version (>= 17) [E]"
    )
    export_mechanism: str = Field(
        ...,
        description="Export engine: dynamo_export_aot_autograd or direct_analytical_force_head [D]",
    )
    dynamic_axes: Dict[str, Dict[int, str]] = Field(
        ...,
        description="Dynamic axes dictionary covering 3D tensors and edge_index [D]",
    )
    precision: str = Field(
        ..., description="Model numerical precision: float32 or float64 [E]"
    )

    @field_validator("opset_version")
    @classmethod
    def validate_opset(cls, v: int) -> int:
        if v < 17:
            from Libraries.cochem_torq_inference_errors import OpsetUnsupportedError

            raise OpsetUnsupportedError(
                f"Target ONNX opset {v} is unsupported. CoChem-TORQ requires opset >= 17 for PyTorch 2.0+ Dynamo export."
            )
        return v



--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_environment.py ---
"""Hardware Concurrency, Device Dispatcher & HPC Safe Scratch for CoChem-TORQ.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Apple Silicon MPS float64 automatic fallback to CPU, HPC distributed lock prohibition.
- [D] Derived: Dynamic 6-tier runtime path resolution and hardware binding.
- [E] Empirical: OS-agnostic pathlib handling and local NVMe scratch fallback.

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union
import torch


def dispatch_device_safely(
    device: Union[str, torch.device],
    dtype: torch.dtype,
) -> torch.device:
    """Dispatch hardware accelerator safely with Apple Silicon MPS float64 fallback [M].

    Metal Performance Shaders (MPS) does not support 64-bit floating point operations.
    When execution requests torch.float64, this dispatcher intercepts and reroutes to CPU,
    while permitting single-precision torch.float32 on MPS.

    Parameters
    ----------
    device : Union[str, torch.device]
        Requested target device (e.g. 'cpu', 'cuda', 'mps').
    dtype : torch.dtype
        Computation numerical precision.

    Returns
    -------
    torch.device
        Safely routed device.
    """
    dev_str = str(device).strip().lower()

    # Intercept MPS float64 requests and fallback to CPU [M]
    if "mps" in dev_str and dtype == torch.float64:
        return torch.device("cpu")

    return torch.device(device)


def resolve_hpc_safe_scratch() -> Path:
    """Resolve node-local scratch storage adhering to the HPC Distributed Lock Prohibition [M].

    On parallel network filesystems (Lustre, GPFS, BeeGFS, NFS), direct file locking
    triggers lock manager deadlocks ([Errno 37] No locks available). All staging and locking
    must route to local NVMe scratch via $SLURM_TMPDIR or $TMPDIR.

    Returns
    -------
    Path
        Path to local 'cochem_torq_scratch' directory, guaranteed to exist on disk.
    """
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    sys_tmp = os.environ.get("TMPDIR")
    cochem_scratch = os.environ.get("COCHEM_SCRATCH_DIR")

    if slurm_tmp:
        base_dir = Path(slurm_tmp)
    elif sys_tmp:
        base_dir = Path(sys_tmp)
    elif cochem_scratch:
        base_dir = Path(cochem_scratch)
    else:
        base_dir = Path.home() / ".cochem" / "scratch"

    scratch_path = base_dir / "cochem_torq_scratch"
    scratch_path.mkdir(parents=True, exist_ok=True)
    return scratch_path

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_finite_difference.py ---
"""Machine-Precision Finite-Difference Gradient Verification Suite for CoChem-TORQ.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Strict torch.float64 precision enforcement and finite-difference acceptance tolerances.
- [D] Derived: Central finite-difference mathematical formulation and relative Frobenius error metric.
- [E] Empirical: Displacement step size h = 1e-4 Angstrom and tolerance = 1e-4 eV/Angstrom.

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
"""

from __future__ import annotations

from typing import Callable
import torch

from Libraries.cochem_torq_inference_errors import NumericalParityError
from Libraries.cochem_torq_inference_schemas import FiniteDiffVerificationResult


def verify_finite_difference_forces(
    coords: torch.Tensor,
    energy_fn: Callable[[torch.Tensor], torch.Tensor],
    step_size: float = 1e-4,
    tolerance: float = 1e-4,
) -> FiniteDiffVerificationResult:
    """Verify conservative analytical forces against central finite-difference gradients [M].

    Parameters
    ----------
    coords : torch.Tensor
        Cartesian coordinates of shape [N, 3]. Must strictly have dtype=torch.float64.
    energy_fn : Callable[[torch.Tensor], torch.Tensor]
        Function computing total molecular potential energy in eV.
    step_size : float
        Displacement step size h in Angstroms (default 1e-4 A) [E].
    tolerance : float
        Acceptance threshold for L_infinity and relative Frobenius error (default 1e-4 eV/A) [M].

    Returns
    -------
    FiniteDiffVerificationResult
        Validation report certifying parity and precision metrics.

    Raises
    ------
    NumericalParityError
        If coords.dtype != torch.float64, or if force errors exceed tolerance.
    """
    if coords.dtype != torch.float64:
        raise NumericalParityError(
            f"Mandatory float64 precision violated: received tensor of dtype {coords.dtype}. "
            "Finite-difference force verification requires torch.float64 to eliminate subtractive cancellation noise.",
            error_code="TORQ_PRECISION_MISMATCH",
            component="finite_difference",
            diagnostics={"received_dtype": str(coords.dtype), "required_dtype": "torch.float64"},
        )

    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"Cartesian coordinates must have shape [N, 3], got shape {list(coords.shape)}.")

    num_atoms = coords.shape[0]
    h = float(step_size)

    # 1. Analytical forces via automatic differentiation [D]
    coords_eval = coords.detach().clone().requires_grad_(True)
    energy = energy_fn(coords_eval)
    grad = torch.autograd.grad(energy, coords_eval, create_graph=False)[0]
    forces_analytic = -grad

    # 2. Central finite-difference numerical forces across 3N degrees of freedom [D]
    forces_num = torch.zeros_like(coords)
    for i in range(num_atoms):
        for alpha in range(3):
            coords_plus = coords.detach().clone()
            coords_minus = coords.detach().clone()
            coords_plus[i, alpha] += h
            coords_minus[i, alpha] -= h

            e_plus = energy_fn(coords_plus)
            e_minus = energy_fn(coords_minus)

            forces_num[i, alpha] = -(e_plus - e_minus) / (2.0 * h)

    # 3. Acceptance metrics [M]
    abs_errors = torch.abs(forces_analytic - forces_num)
    max_absolute_error = float(torch.max(abs_errors).item())

    frob_diff = torch.linalg.norm(forces_analytic - forces_num).item()
    frob_analytic = torch.linalg.norm(forces_analytic).item()
    relative_frobenius_error = float(frob_diff / (frob_analytic + 1e-12))

    passed = bool(max_absolute_error < tolerance and relative_frobenius_error < tolerance)

    if not passed:
        raise NumericalParityError(
            f"Finite-difference force parity check failed: "
            f"L_infinity = {max_absolute_error:.6e} eV/A (tol = {tolerance:.6e}), "
            f"RelErr_F = {relative_frobenius_error:.6e} (tol = {tolerance:.6e}).",
            error_code="TORQ_NUMERICAL_PARITY_ERROR",
            component="finite_difference",
            diagnostics={
                "max_absolute_error": max_absolute_error,
                "relative_frobenius_error": relative_frobenius_error,
                "step_size": h,
                "tolerance": float(tolerance),
                "passed": False,
            },
        )

    return FiniteDiffVerificationResult(
        max_absolute_error=max_absolute_error,
        relative_frobenius_error=relative_frobenius_error,
        step_size=h,
        passed=passed,
        dtype=str(coords.dtype),
        atom_count=num_atoms,
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_multitask.py ---
"""Multi-Task Learning Head with Log-Variance Homoscedastic Loss for CoChem-TORQ.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Multi-task auxiliary head for total potential energy and HOMO-LUMO gap.
- [D] Derived: Log-variance homoscedastic uncertainty loss formulation and analytical gradients.
- [E] Empirical: Huber loss threshold limits (delta_E = 0.01 eV, delta_G = 0.05 eV).

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
"""

from __future__ import annotations

from typing import Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from Libraries.cochem_torq_inference_errors import PhysicsDivergenceError


def huber_loss(
    pred: torch.Tensor,
    target: torch.Tensor,
    delta: float,
) -> torch.Tensor:
    """Smooth Huber loss envelope for robust regression against outliers [D].

    L_Huber(y, y*; delta) = 0.5 * (y - y*)^2        if |y - y*| <= delta
                          = delta * (|y - y*| - 0.5 * delta)  otherwise
    """
    diff = torch.abs(pred - target)
    loss = torch.where(
        diff <= delta,
        0.5 * (diff**2),
        delta * (diff - 0.5 * delta),
    )
    return torch.mean(loss)


class MultiTaskHead(nn.Module):
    """Auxiliary equivariant regression head predicting energy and HOMO-LUMO gap [M].

    Enforces strictly positive HOMO-LUMO frontier orbital gap via smooth Softplus
    activation and defensive physical divergence checks.
    """

    def __init__(
        self,
        in_features: int = 128,
        hidden_dim: int = 64,
        epsilon_gap: float = 1e-4,
        dtype: torch.dtype = torch.float64,
    ) -> None:
        super().__init__()
        self.in_features = in_features
        self.hidden_dim = hidden_dim
        self.epsilon_gap = float(epsilon_gap)

        self.energy_head = nn.Sequential(
            nn.Linear(in_features, hidden_dim, dtype=dtype),
            nn.SiLU(),
            nn.Linear(hidden_dim, 1, dtype=dtype),
        )

        self.gap_head = nn.Sequential(
            nn.Linear(in_features, hidden_dim, dtype=dtype),
            nn.SiLU(),
            nn.Linear(hidden_dim, 1, dtype=dtype),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass predicting potential energy and HOMO-LUMO gap [M].

        Parameters
        ----------
        x : torch.Tensor
            Latent representation tensor of shape [batch_size, in_features].

        Returns
        -------
        Tuple[torch.Tensor, torch.Tensor]
            energy: [batch_size, 1] in eV.
            homo_lumo_gap: [batch_size, 1] in eV.
        """
        weight_dtype = self.energy_head[0].weight.dtype
        if x.dtype != weight_dtype:
            if x.dtype == torch.float64:
                self.to(torch.float64)
            else:
                x = x.to(weight_dtype)

        energy = self.energy_head(x)
        raw_gap = self.gap_head(x)
        gap = F.softplus(raw_gap) + self.epsilon_gap

        if not torch.jit.is_tracing():
            if (gap <= 0.0).any():
                min_val = float(torch.min(gap).item())
                raise PhysicsDivergenceError(
                    f"HOMO-LUMO gap predicted non-positive value: {min_val:.6e} eV.",
                    error_code="TORQ_GAP_DIVERGENCE",
                    component="multi_task_head",
                    diagnostics={"min_gap_ev": min_val, "epsilon_gap": self.epsilon_gap},
                )

        return energy, gap


class HomoscedasticMultiTaskLoss(nn.Module):
    """Joint homoscedastic multi-task objective with learnable log-variances [D].

    L_multi = 0.5 * exp(-s_E) * L_E(delta_E) + 0.5 * exp(-s_G) * L_G(delta_G) + 0.5 * (s_E + s_G)
    """

    def __init__(
        self,
        delta_energy: float = 0.01,
        delta_gap: float = 0.05,
        init_s_energy: float = 0.0,
        init_s_gap: float = 0.0,
    ) -> None:
        super().__init__()
        self.delta_energy = float(delta_energy)
        self.delta_gap = float(delta_gap)

        self.s_E = nn.Parameter(torch.tensor(float(init_s_energy), dtype=torch.float64))
        self.s_G = nn.Parameter(torch.tensor(float(init_s_gap), dtype=torch.float64))

    def forward(
        self,
        pred_energy: torch.Tensor,
        target_energy: torch.Tensor,
        pred_gap: torch.Tensor,
        target_gap: torch.Tensor,
    ) -> torch.Tensor:
        """Evaluate joint homoscedastic loss [D].

        Parameters
        ----------
        pred_energy : torch.Tensor
            Predicted energy in eV.
        target_energy : torch.Tensor
            Reference energy in eV.
        pred_gap : torch.Tensor
            Predicted HOMO-LUMO gap in eV.
        target_gap : torch.Tensor
            Reference HOMO-LUMO gap in eV.

        Returns
        -------
        torch.Tensor
            Joint scalar loss.
        """
        loss_E = huber_loss(pred_energy, target_energy, self.delta_energy)
        loss_G = huber_loss(pred_gap, target_gap, self.delta_gap)

        s_E_cast = self.s_E.to(loss_E.dtype)
        s_G_cast = self.s_G.to(loss_G.dtype)

        term_E = 0.5 * torch.exp(-s_E_cast) * loss_E
        term_G = 0.5 * torch.exp(-s_G_cast) * loss_G
        regularization = 0.5 * (s_E_cast + s_G_cast)

        return term_E + term_G + regularization

    def compute_analytical_log_variance_gradients(
        self,
        pred_energy: torch.Tensor,
        target_energy: torch.Tensor,
        pred_gap: torch.Tensor,
        target_gap: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute exact analytical gradients dL/ds_E and dL/ds_G [D].

        dL/ds_E = -0.5 * exp(-s_E) * L_E + 0.5
        dL/ds_G = -0.5 * exp(-s_G) * L_G + 0.5
        """
        loss_E = huber_loss(pred_energy, target_energy, self.delta_energy)
        loss_G = huber_loss(pred_gap, target_gap, self.delta_gap)

        s_E_cast = self.s_E.to(loss_E.dtype)
        s_G_cast = self.s_G.to(loss_G.dtype)

        grad_s_E = -0.5 * torch.exp(-s_E_cast) * loss_E + 0.5
        grad_s_G = -0.5 * torch.exp(-s_G_cast) * loss_G + 0.5

        return grad_s_E, grad_s_G

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_onnx_export.py ---
"""PyTorch 2.0+ TorchDynamo ONNX Edge-Export Pipeline with Dynamic Axes for CoChem-TORQ.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Numerical parity verification between PyTorch eager graph and ONNX Runtime (tol = 1e-5).
- [D] Derived: Dynamic axes specification covering 3D tensors, edge_index, and analytical outputs.
- [E] Empirical: Minimum ONNX opset version >= 17 (recommended 18).

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
"""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import torch
import torch.nn as nn

from Libraries.cochem_torq_inference_errors import (
    NumericalParityError,
    OpsetUnsupportedError,
)
from Libraries.cochem_torq_inference_schemas import ONNXExportSpec

# Canonical 3D Dynamic Axes Specification [D]/[E]
DEFAULT_DYNAMIC_AXES: Dict[str, Dict[int, str]] = {
    "coordinates": {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"},
    "atomic_numbers": {0: "batch_size", 1: "num_atoms"},
    "edge_index": {0: "edge_direction", 1: "num_edges"},
    "energy": {0: "batch_size"},
    "homo_lumo_gap": {0: "batch_size"},
    "forces": {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"},
}


def validate_onnx_spec(spec: ONNXExportSpec) -> None:
    """Validate that ONNXExportSpec conforms to PyTorch 2.0+ requirements [M].

    Parameters
    ----------
    spec : ONNXExportSpec
        Export specification contract.

    Raises
    ------
    OpsetUnsupportedError
        If opset_version < 17 or unsupported export mechanism.
    """
    if spec.opset_version < 17:
        raise OpsetUnsupportedError(
            f"Target ONNX opset {spec.opset_version} is unsupported. CoChem-TORQ requires opset >= 17.",
            error_code="TORQ_OPSET_UNSUPPORTED",
            component="onnx_export",
            diagnostics={"opset_version": spec.opset_version},
        )

    supported_mechanisms = {"dynamo_export_aot_autograd", "direct_analytical_force_head"}
    if spec.export_mechanism not in supported_mechanisms:
        raise OpsetUnsupportedError(
            f"Unsupported ONNX export mechanism: '{spec.export_mechanism}'. "
            f"Supported mechanisms: {sorted(supported_mechanisms)}.",
            error_code="TORQ_EXPORT_MECHANISM_UNSUPPORTED",
            component="onnx_export",
            diagnostics={"export_mechanism": spec.export_mechanism},
        )


def export_to_onnx(
    model: nn.Module,
    sample_inputs: Union[torch.Tensor, Tuple[torch.Tensor, ...]],
    export_path: Union[str, Path],
    spec: ONNXExportSpec,
    input_names: Optional[List[str]] = None,
    output_names: Optional[List[str]] = None,
) -> Path:
    """Compile and export PyTorch model to an ONNX binary artifact [M]/[D].

    Parameters
    ----------
    model : nn.Module
        PyTorch model to export.
    sample_inputs : Union[torch.Tensor, Tuple[torch.Tensor, ...]]
        Representative inputs for model tracing or shape analysis.
    export_path : Union[str, Path]
        Target file path for the .onnx binary.
    spec : ONNXExportSpec
        Configuration specification governing opset version and dynamic axes.
    input_names : Optional[List[str]]
        Names for input nodes in the exported ONNX graph.
    output_names : Optional[List[str]]
        Names for output nodes in the exported ONNX graph.

    Returns
    -------
    Path
        Absolute path to the validated ONNX file.

    Raises
    ------
    OpsetUnsupportedError
        If spec.opset_version < 17 or invalid export mechanism.
    """
    validate_onnx_spec(spec)

    out_path = Path(export_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not isinstance(sample_inputs, tuple):
        sample_inputs = (sample_inputs,)

    if input_names is None:
        input_names = [f"input_{i}" for i in range(len(sample_inputs))]
    if output_names is None:
        output_names = ["output_0"]

    # Filter dynamic axes to match only the specified input/output names and tensor dimensions
    filtered_dynamic_axes: Dict[str, Dict[int, str]] = {}
    for name, tensor in zip(input_names, sample_inputs):
        if name in spec.dynamic_axes:
            filtered_dynamic_axes[name] = {
                ax: ax_name
                for ax, ax_name in spec.dynamic_axes[name].items()
                if ax < tensor.ndim
            }
    for name in output_names:
        if name in spec.dynamic_axes:
            filtered_dynamic_axes[name] = spec.dynamic_axes[name]

    eval_model = model.eval()

    # Route based on spec.export_mechanism
    if spec.export_mechanism == "dynamo_export_aot_autograd":
        try:
            buffer = io.StringIO()
            err_buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(err_buffer):
                if hasattr(torch.onnx, "dynamo_export"):
                    onnx_program = torch.onnx.dynamo_export(eval_model, *sample_inputs)
                    onnx_program.save(str(out_path))
                else:
                    torch.onnx.export(
                        eval_model,
                        sample_inputs,
                        str(out_path),
                        export_params=True,
                        opset_version=spec.opset_version,
                        do_constant_folding=True,
                        input_names=input_names,
                        output_names=output_names,
                        dynamic_axes=filtered_dynamic_axes if filtered_dynamic_axes else None,
                    )
        except Exception:
            buffer = io.StringIO()
            err_buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(err_buffer):
                torch.onnx.export(
                    eval_model,
                    sample_inputs,
                    str(out_path),
                    export_params=True,
                    opset_version=spec.opset_version,
                    do_constant_folding=True,
                    input_names=input_names,
                    output_names=output_names,
                    dynamic_axes=filtered_dynamic_axes if filtered_dynamic_axes else None,
                    dynamo=False,
                )
    elif spec.export_mechanism == "direct_analytical_force_head":
        buffer = io.StringIO()
        err_buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(err_buffer):
            torch.onnx.export(
                eval_model,
                sample_inputs,
                str(out_path),
                export_params=True,
                opset_version=spec.opset_version,
                do_constant_folding=True,
                input_names=input_names,
                output_names=output_names,
                dynamic_axes=filtered_dynamic_axes if filtered_dynamic_axes else None,
                dynamo=False,
            )
    else:
        raise OpsetUnsupportedError(
            f"Unsupported ONNX export mechanism: '{spec.export_mechanism}'. "
            f"Supported mechanisms: 'dynamo_export_aot_autograd', 'direct_analytical_force_head'.",
            error_code="TORQ_EXPORT_MECHANISM_UNSUPPORTED",
            component="onnx_export",
            diagnostics={"export_mechanism": spec.export_mechanism},
        )

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"Failed to generate ONNX artifact at {out_path}.")

    return out_path


def verify_onnx_parity(
    torch_model: nn.Module,
    onnx_path: Union[str, Path],
    sample_inputs: Union[torch.Tensor, Tuple[torch.Tensor, ...]],
    tolerance: float = 1e-5,
) -> float:
    """Validate numerical parity between PyTorch eager execution and ONNX Runtime session [M].

    Parameters
    ----------
    torch_model : nn.Module
        Eager PyTorch model.
    onnx_path : Union[str, Path]
        Path to compiled ONNX binary artifact.
    sample_inputs : Union[torch.Tensor, Tuple[torch.Tensor, ...]]
        Input tensors for parity execution.
    tolerance : float
        Maximum allowable absolute elementwise discrepancy (default 1e-5) [M].

    Returns
    -------
    float
        Maximum absolute discrepancy across all graph outputs.

    Raises
    ------
    NumericalParityError
        If discrepancy exceeds tolerance or evaluation fails.
    """
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError("onnxruntime is required for verify_onnx_parity.") from exc

    if not isinstance(sample_inputs, tuple):
        sample_inputs = (sample_inputs,)

    model_eval = torch_model.eval()
    with torch.no_grad():
        torch_outputs = model_eval(*sample_inputs)

    if isinstance(torch_outputs, torch.Tensor):
        torch_outputs_list = [torch_outputs]
    elif isinstance(torch_outputs, (tuple, list)):
        torch_outputs_list = list(torch_outputs)
    else:
        raise TypeError(f"Unsupported model output type: {type(torch_outputs)}.")

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    ort_input_names = [inp.name for inp in session.get_inputs()]

    ort_feed: Dict[str, np.ndarray] = {}
    for name, tensor in zip(ort_input_names, sample_inputs):
        ort_feed[name] = tensor.detach().cpu().numpy()

    ort_outputs = session.run(None, ort_feed)

    max_absolute_error = 0.0
    for t_out, o_out in zip(torch_outputs_list, ort_outputs):
        t_np = t_out.detach().cpu().numpy()
        abs_diff = float(np.max(np.abs(t_np - o_out)))
        if abs_diff > max_absolute_error:
            max_absolute_error = abs_diff

    if max_absolute_error > tolerance:
        raise NumericalParityError(
            f"ONNX parity verification failed: maximum absolute error {max_absolute_error:.6e} "
            f"exceeds tolerance {tolerance:.6e}.",
            error_code="TORQ_ONNX_PARITY_DIVERGENCE",
            component="onnx_verifier",
            diagnostics={
                "max_absolute_error": max_absolute_error,
                "tolerance": float(tolerance),
            },
        )

    return max_absolute_error

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\Libraries\cochem_torq_vibrational.py ---
"""Double-Autograd Cartesian Hessian, CIAAW Masses, Eckart Projection & Vibrational Analyzer.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Dynamic Mendeleev CIAAW monoisotopic mass retrieval, float64 precision.
- [D] Derived: Double-autograd Cartesian Hessian, Gram-Schmidt Eckart projector, CODATA 2022 dimensional scaling.
- [E] Empirical: Orthonormalization threshold 1e-7, signed frequency non-NaN reporting.

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
"""

from __future__ import annotations

import math
from typing import Callable, List, Sequence, Tuple
import mendeleev
import torch

from Libraries.cochem_torq_inference_errors import (
    NumericalParityError,
    PhysicsDivergenceError,
)
from Libraries.cochem_torq_inference_schemas import VibrationalModes

# CODATA 2022 Fundamental Constants [M]/[D]
# 1 eV = 1.602176634e-19 J
# 1 A  = 1.0e-10 m
# 1 u  = 1.66053906660e-27 kg
# c    = 2.99792458e10 cm/s
# h    = 4.135667696e-15 eV*s
# kappa = 1.602176634e-19 / ( (1e-10)^2 * 1.66053906660e-27 ) = 9.648533212331e27 s^-2 / (eV * A^-2 * u^-1)
CODATA_2022_KAPPA = 9.648533212331e27
CODATA_2022_C_CMS = 2.99792458e10
CODATA_2022_H_EVS = 4.135667696e-15
CODATA_2022_HC_EV_CM = CODATA_2022_H_EVS * CODATA_2022_C_CMS  # 1.239841984e-4 eV*cm
# Conversion factor from sqrt(eV / (A^2 * u)) to cm^-1: sqrt(kappa) / (2 * pi * c)
CODATA_2022_FREQ_FACTOR = math.sqrt(CODATA_2022_KAPPA) / (2.0 * math.pi * CODATA_2022_C_CMS)  # ~521.4708316 cm^-1


def resolve_ciaaw_monoisotopic_mass(atomic_number: int) -> float:
    """Retrieve pure CIAAW monoisotopic mass for the most abundant isotope of element Z [M].

    Queries mendeleev.element(Z).isotopes and filters by maximum terrestrial
    isotopic abundance. Standard terrestrial average weights are strictly forbidden.

    Parameters
    ----------
    atomic_number : int
        Nuclear charge Z (1 <= Z <= 118).

    Returns
    -------
    float
        Pure monoisotopic mass in unified atomic mass units (u).

    Raises
    ------
    PhysicsDivergenceError
        If element is invalid or no isotopic record is available.
    """
    if atomic_number < 1 or atomic_number > 118:
        raise PhysicsDivergenceError(
            f"Invalid atomic number Z={atomic_number}. Must be in chemical domain [1, 118].",
            error_code="TORQ_INVALID_ATOMIC_NUMBER",
            component="monoisotopic_resolver",
            diagnostics={"atomic_number": atomic_number},
        )

    try:
        elem = mendeleev.element(int(atomic_number))
    except Exception as exc:
        raise PhysicsDivergenceError(
            f"Failed to retrieve element record for Z={atomic_number}: {exc}",
            error_code="TORQ_MENDELEEV_QUERY_FAIL",
            component="monoisotopic_resolver",
            diagnostics={"atomic_number": atomic_number, "exception": str(exc)},
        ) from exc

    isotopes = [
        iso
        for iso in elem.isotopes
        if iso.abundance is not None and iso.abundance > 0.0
    ]
    if not isotopes:
        isotopes = elem.isotopes
    if not isotopes:
        raise PhysicsDivergenceError(
            f"No isotopic mass records available for atomic number Z={atomic_number}.",
            error_code="TORQ_NO_ISOTOPES",
            component="monoisotopic_resolver",
            diagnostics={"atomic_number": atomic_number, "symbol": elem.symbol},
        )

    most_abundant = max(isotopes, key=lambda iso: iso.abundance or 0.0)
    if most_abundant.mass is None:
        raise PhysicsDivergenceError(
            f"CIAAW mass undefined for element {elem.symbol} (Z={atomic_number}).",
            error_code="TORQ_UNDEFINED_ISOTOPE_MASS",
            component="monoisotopic_resolver",
            diagnostics={"atomic_number": atomic_number, "symbol": elem.symbol},
        )

    return float(most_abundant.mass)


def compute_cartesian_hessian(
    coords: torch.Tensor,
    energy_fn: Callable[[torch.Tensor], torch.Tensor],
) -> torch.Tensor:
    """Evaluate Cartesian second-derivative Hessian matrix via double autograd in torch.float64 [D].

    Parameters
    ----------
    coords : torch.Tensor
        Cartesian coordinates of shape [N, 3], strictly torch.float64.
    energy_fn : Callable[[torch.Tensor], torch.Tensor]
        Total potential energy function in eV.

    Returns
    -------
    torch.Tensor
        Symmetrized Cartesian Hessian matrix of shape [3N, 3N] in eV / A^2.

    Raises
    ------
    NumericalParityError
        If coords.dtype != torch.float64.
    """
    if coords.dtype != torch.float64:
        raise NumericalParityError(
            f"Double-autograd Hessian requires torch.float64, got {coords.dtype}.",
            error_code="TORQ_PRECISION_MISMATCH",
            component="cartesian_hessian",
            diagnostics={"dtype": str(coords.dtype)},
        )

    coords_eval = coords.detach().clone().requires_grad_(True)
    energy = energy_fn(coords_eval)
    grad = torch.autograd.grad(energy, coords_eval, create_graph=True)[0]
    grad_flat = grad.reshape(-1)
    num_dofs = grad_flat.shape[0]

    hessian_rows = []
    for k in range(num_dofs):
        retain = k < (num_dofs - 1)
        row = torch.autograd.grad(
            grad_flat[k],
            coords_eval,
            retain_graph=retain,
            create_graph=False,
        )[0]
        hessian_rows.append(row.reshape(-1))

    H = torch.stack(hessian_rows, dim=0)
    # Active Hermitian symmetrization to eliminate numerical asymmetry [D]
    H_sym = 0.5 * (H + H.T)
    return H_sym


def compute_eckart_projector(
    coords: torch.Tensor,
    masses: torch.Tensor,
) -> Tuple[torch.Tensor, int]:
    """Construct Gram-Schmidt Eckart projection operator removing translational and rotational modes [D].

    Parameters
    ----------
    coords : torch.Tensor
        Cartesian coordinates of shape [N, 3], strictly torch.float64.
    masses : torch.Tensor
        Atomic masses of shape [N], strictly torch.float64.

    Returns
    -------
    Tuple[torch.Tensor, int]
        P: Eckart projection operator [3N, 3N] satisfying P^2 = P, P^T = P, Tr(P) = 3N - D.
        D: Number of projected degrees of freedom (6 for non-linear, 5 for linear, 3 for single atom).
    """
    if coords.dtype != torch.float64 or masses.dtype != torch.float64:
        raise NumericalParityError(
            "Eckart projector requires torch.float64 precision for both coordinates and masses.",
            error_code="TORQ_PRECISION_MISMATCH",
            component="eckart_projector",
            diagnostics={"coords_dtype": str(coords.dtype), "masses_dtype": str(masses.dtype)},
        )

    num_atoms = coords.shape[0]
    device = coords.device

    # 1. Center of mass translation [D]
    total_mass = torch.sum(masses)
    if total_mass <= 0.0:
        raise PhysicsDivergenceError(
            f"Total molecular mass is non-positive: {total_mass.item():.6e} u.",
            component="eckart_projector",
        )
    r_com = torch.sum(coords * masses.unsqueeze(1), dim=0) / total_mass
    rel_coords = coords - r_com

    # 2. Mass-weighted translation basis vectors (T_alpha, alpha in {x, y, z}) [D]
    sqrt_masses = torch.sqrt(masses)
    basis_candidates = []
    for alpha in range(3):
        t = torch.zeros((num_atoms, 3), dtype=torch.float64, device=device)
        t[:, alpha] = sqrt_masses
        basis_candidates.append(t.reshape(-1))

    # 3. Mass-weighted rotation basis vectors (R_alpha, alpha in {x, y, z}) [D]
    unit_axes = torch.eye(3, dtype=torch.float64, device=device)
    for alpha in range(3):
        axis = unit_axes[alpha]
        rot = torch.zeros((num_atoms, 3), dtype=torch.float64, device=device)
        for i in range(num_atoms):
            rot[i] = sqrt_masses[i] * torch.linalg.cross(axis, rel_coords[i])
        basis_candidates.append(rot.reshape(-1))

    # 4. Sequential Gram-Schmidt orthonormalization, discarding null vectors (< 1e-7) [D]
    ortho_basis = []
    for candidate in basis_candidates:
        w = candidate.clone()
        for u in ortho_basis:
            w = w - torch.dot(u, w) * u
        norm = torch.linalg.norm(w)
        if norm > 1e-7:
            ortho_basis.append(w / norm)

    d_proj = len(ortho_basis)
    if d_proj == 0:
        p_matrix = torch.eye(3 * num_atoms, dtype=torch.float64, device=device)
        return p_matrix, 0

    u_matrix = torch.stack(ortho_basis, dim=1)  # [3N, D]
    identity = torch.eye(3 * num_atoms, dtype=torch.float64, device=device)
    p_matrix = identity - u_matrix @ u_matrix.T
    p_matrix = 0.5 * (p_matrix + p_matrix.T)

    return p_matrix, d_proj


def analyze_vibrational_frequencies(
    coords: torch.Tensor,
    atomic_numbers: Sequence[int],
    energy_fn: Callable[[torch.Tensor], torch.Tensor],
    filter_projected: bool = True,
) -> VibrationalModes:
    """Compute mass-weighted projected normal modes, CODATA 2022 frequencies, and ZPVE [M]/[D].

    Parameters
    ----------
    coords : torch.Tensor
        Equilibrium Cartesian coordinates [N, 3] in Angstroms, strictly torch.float64.
    atomic_numbers : Sequence[int]
        Nuclear charges Z for each atom.
    energy_fn : Callable[[torch.Tensor], torch.Tensor]
        Total potential energy function in eV.
    filter_projected : bool
        If True (default), project and remove the D translational/rotational zero modes,
        reporting strictly the 3N - D genuine vibrational normal modes.

    Returns
    -------
    VibrationalModes
        Certified normal mode report containing signed wavenumbers (cm^-1), eigenvalues,
        imaginary mode count, and ZPVE (eV).
    """
    if coords.dtype != torch.float64:
        raise NumericalParityError(
            f"Vibrational analysis requires torch.float64 coordinates, got {coords.dtype}.",
            error_code="TORQ_PRECISION_MISMATCH",
            component="vibrational_analyzer",
            diagnostics={"dtype": str(coords.dtype)},
        )

    num_atoms = coords.shape[0]
    if len(atomic_numbers) != num_atoms:
        raise ValueError(
            f"Atomic numbers length ({len(atomic_numbers)}) does not match coordinates atom count ({num_atoms})."
        )

    # 1. Resolve pure CIAAW monoisotopic masses [M]
    mass_list = [resolve_ciaaw_monoisotopic_mass(int(z)) for z in atomic_numbers]
    masses = torch.tensor(mass_list, dtype=torch.float64, device=coords.device)

    # 2. Evaluate Cartesian Hessian [D]
    H_cart = compute_cartesian_hessian(coords, energy_fn)

    # 3. Mass-weight the Hessian: H_tilde_{ia, jb} = H_{ia, jb} / sqrt(m_i * m_j) [D]
    mass_repeat = torch.repeat_interleave(masses, 3)
    inv_sqrt_mass = 1.0 / torch.sqrt(mass_repeat)
    H_tilde = H_cart * torch.outer(inv_sqrt_mass, inv_sqrt_mass)

    # 4. Gram-Schmidt Eckart projection [D]
    P_eckart, d_proj = compute_eckart_projector(coords, masses)
    H_proj = P_eckart @ H_tilde @ P_eckart
    H_proj = 0.5 * (H_proj + H_proj.T)

    # 5. Diagonalization via torch.linalg.eigh [D]
    raw_eigenvalues, _ = torch.linalg.eigh(H_proj)

    # 6. Filter out the D translational and rotational zero modes (|lambda| < 1e-7) [D]
    if filter_projected and d_proj > 0:
        # Sort indices by absolute eigenvalue magnitude; the D smallest are the projected zero modes
        abs_order = sorted(range(len(raw_eigenvalues)), key=lambda i: abs(raw_eigenvalues[i].item()))
        vib_indices = sorted(abs_order[d_proj:])
        selected_eigenvalues = [raw_eigenvalues[i].item() for i in vib_indices]
    else:
        selected_eigenvalues = [ev.item() for ev in raw_eigenvalues]

    # Sort genuine normal modes by signed eigenvalue
    selected_eigenvalues = sorted(selected_eigenvalues)

    # 7. CODATA 2022 Signed Frequencies: nu_k = sgn(lambda_k) * C_freq * sqrt(|lambda_k|) [D]
    frequencies_cm1: List[float] = []
    imaginary_count = 0
    for lam in selected_eigenvalues:
        if abs(lam) < 1e-12:
            freq = 0.0
        else:
            sgn = 1.0 if lam >= 0.0 else -1.0
            freq = sgn * CODATA_2022_FREQ_FACTOR * math.sqrt(abs(lam))

        frequencies_cm1.append(float(freq))
        if freq < 0.0:
            imaginary_count += 1

    # 8. Harmonic Zero-Point Vibrational Energy (ZPVE) summed over real modes (lambda_k > 0) [D]
    # E_ZPE = 0.5 * sum_{k: nu_k > 0} (h * c * nu_k) in eV
    zpe_ev = 0.5 * sum(
        CODATA_2022_HC_EV_CM * f
        for f in frequencies_cm1
        if f > 0.0
    )

    return VibrationalModes(
        frequencies_cm1=frequencies_cm1,
        zero_point_energy_ev=float(zpe_ev),
        imaginary_mode_count=imaginary_count,
        eigenvalues=selected_eigenvalues,
        projected_degrees_of_freedom=d_proj,
        mass_weighting_standard="CIAAW_MONOISOTOPIC",
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_chunk20_verification_suite.py ---
"""Verification suite for SRS Chunk 20: TORQ Inference, Vibrational Analysis & ONNX Export.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Authentic molecular test fixtures, float64 precision enforcement, CIAAW masses.
- [D] Derived: Double-autograd Hessians, Gram-Schmidt Eckart projection, CODATA 2022 constants.
- [E] Empirical: Finite-difference step sizes, Huber envelopes, ONNX dynamic axes.

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
All tests ingest genuine physical molecular coordinates and authentic potentials.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List
import mendeleev
from pydantic import ValidationError
import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_environment import (
    dispatch_device_safely,
    resolve_hpc_safe_scratch,
)
from Libraries.cochem_torq_finite_difference import (
    verify_finite_difference_forces,
)
from Libraries.cochem_torq_inference_errors import (
    NumericalParityError,
    OpsetUnsupportedError,
    PhysicsDivergenceError,
)
from Libraries.cochem_torq_inference_schemas import (
    FiniteDiffVerificationResult,
    MultiTaskPrediction,
    ONNXExportSpec,
    VibrationalModes,
)
from Libraries.cochem_torq_multitask import (
    HomoscedasticMultiTaskLoss,
    MultiTaskHead,
    huber_loss,
)
from Libraries.cochem_torq_onnx_export import (
    DEFAULT_DYNAMIC_AXES,
    export_to_onnx,
    validate_onnx_spec,
    verify_onnx_parity,
)
from Libraries.cochem_torq_vibrational import (
    CODATA_2022_FREQ_FACTOR,
    CODATA_2022_HC_EV_CM,
    CODATA_2022_KAPPA,
    analyze_vibrational_frequencies,
    compute_cartesian_hessian,
    compute_eckart_projector,
    resolve_ciaaw_monoisotopic_mass,
)

# Authentic C2v equilibrium geometry for Water (H2O) [M]
H2O_COORDS = torch.tensor(
    [
        [0.0000000, 0.0000000, 0.1173000],   # O
        [0.0000000, 0.7572000, -0.4692000],  # H1
        [0.0000000, -0.7572000, -0.4692000], # H2
    ],
    dtype=torch.float64,
)
H2O_Z = [8, 1, 1]

# Authentic equilibrium geometry for Methanol (CH3OH, N=6) [M]
METHANOL_COORDS = torch.tensor(
    [
        [-0.0466000, 0.6646000, 0.0000000],   # C
        [-0.0466000, -0.7543000, 0.0000000],  # O
        [0.8400000, -1.0805000, 0.0000000],   # H_O
        [-1.0772000, 1.0268000, 0.0000000],   # H1
        [0.4578000, 1.0538000, 0.8918000],    # H2
        [0.4578000, 1.0538000, -0.8918000],   # H3
    ],
    dtype=torch.float64,
)
METHANOL_Z = [6, 8, 1, 1, 1, 1]


def h2o_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
    """Harmonic valence force field for Water (H2O) in eV [D].

    Equilibrium parameters: r_e = 0.9578 A, theta_e = 104.5 deg.
    kb = 48.0 eV/A^2, kt = 5.0 eV/rad^2.
    """
    r_O = coords[0]
    r_H1 = coords[1]
    r_H2 = coords[2]

    r1 = torch.linalg.norm(r_H1 - r_O)
    r2 = torch.linalg.norm(r_H2 - r_O)

    v1 = (r_H1 - r_O) / r1
    v2 = (r_H2 - r_O) / r2
    cos_theta = torch.clamp(torch.dot(v1, v2), -1.0, 1.0)
    theta = torch.acos(cos_theta)

    r0 = 0.9578
    theta0 = 104.5 * math.pi / 180.0
    kb = 48.0
    kt = 5.0

    e_str = 0.5 * kb * ((r1 - r0) ** 2 + (r2 - r0) ** 2)
    e_bend = 0.5 * kt * ((theta - theta0) ** 2)
    return e_str + e_bend


def methanol_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
    """Harmonic bonded potential for Methanol (CH3OH) in eV [D].

    C=0, O=1, H_O=2, H1=3, H2=4, H3=5.
    """
    r_C = coords[0]
    r_O = coords[1]
    r_HO = coords[2]
    r_H1 = coords[3]
    r_H2 = coords[4]
    r_H3 = coords[5]

    r_CO = torch.linalg.norm(r_C - r_O)
    r_OH = torch.linalg.norm(r_O - r_HO)
    r_CH1 = torch.linalg.norm(r_C - r_H1)
    r_CH2 = torch.linalg.norm(r_C - r_H2)
    r_CH3 = torch.linalg.norm(r_C - r_H3)

    k_co = 35.0
    k_oh = 48.0
    k_ch = 32.0

    e_bonds = (
        0.5 * k_co * (r_CO - 1.42) ** 2
        + 0.5 * k_oh * (r_OH - 0.96) ** 2
        + 0.5 * k_ch * (r_CH1 - 1.09) ** 2
        + 0.5 * k_ch * (r_CH2 - 1.09) ** 2
        + 0.5 * k_ch * (r_CH3 - 1.09) ** 2
    )

    v_OC = (r_C - r_O) / r_CO
    v_OH = (r_HO - r_O) / r_OH
    cos_coh = torch.clamp(torch.dot(v_OC, v_OH), -1.0, 1.0)
    theta_coh = torch.acos(cos_coh)
    e_angle = 0.5 * 4.5 * (theta_coh - (108.5 * math.pi / 180.0)) ** 2

    return e_bonds + e_angle


def test_ciaaw_monoisotopic_vs_average_mass() -> None:
    """1. Assert monoisotopic masses diverge from terrestrial average atomic weights [M]."""
    # Chlorine (Z=17): monoisotopic 35Cl is ~34.96885 u vs terrestrial average 35.45 u
    elem_cl = mendeleev.element(17)
    avg_mass_cl = float(elem_cl.mass)
    mono_mass_cl = resolve_ciaaw_monoisotopic_mass(17)
    assert abs(avg_mass_cl - mono_mass_cl) > 0.4
    assert abs(mono_mass_cl - 34.9688527) < 1e-3

    # Hydrogen (Z=1), Carbon (Z=6), Nitrogen (Z=7), Oxygen (Z=8)
    mono_h = resolve_ciaaw_monoisotopic_mass(1)
    mono_c = resolve_ciaaw_monoisotopic_mass(6)
    mono_n = resolve_ciaaw_monoisotopic_mass(7)
    mono_o = resolve_ciaaw_monoisotopic_mass(8)

    assert abs(mono_h - 1.007825032) < 1e-5
    assert abs(mono_c - 12.000000000) < 1e-5
    assert abs(mono_n - 14.003074004) < 1e-5
    assert abs(mono_o - 15.994914620) < 1e-5

    # Invalid atomic number bounds
    with pytest.raises(PhysicsDivergenceError):
        resolve_ciaaw_monoisotopic_mass(0)

    with pytest.raises(PhysicsDivergenceError):
        resolve_ciaaw_monoisotopic_mass(119)


def test_multitask_homoscedastic_huber_loss() -> None:
    """2. Assert log-variance homoscedastic Huber loss computes finite positive loss and exact analytical gradients [D]."""
    head = MultiTaskHead(in_features=16, hidden_dim=32, epsilon_gap=1e-4)
    water_feats = torch.cat([
        H2O_COORDS.flatten(),
        torch.tensor(H2O_Z, dtype=torch.float64),
        torch.tensor([1.0078, 15.9949, 0.9578, 104.5], dtype=torch.float64),
    ])
    x = torch.stack([
        water_feats,
        water_feats * 1.005,
        water_feats * 0.995,
        water_feats * 1.010,
    ], dim=0)
    pred_E, pred_gap = head(x)
    assert pred_E.shape == (4, 1)
    assert pred_gap.shape == (4, 1)
    assert (pred_gap > 0.0).all()

    # Homoscedastic Huber loss
    loss_fn = HomoscedasticMultiTaskLoss(delta_energy=0.01, delta_gap=0.05)
    target_E = pred_E.detach() + 0.005
    target_gap = pred_gap.detach() - 0.002

    loss = loss_fn(pred_E, target_E, pred_gap, target_gap)
    assert torch.isfinite(loss)
    assert loss.item() > 0.0

    # Gradient check for log-variances
    loss.backward()
    assert loss_fn.s_E.grad is not None
    assert loss_fn.s_G.grad is not None

    grad_s_E_analytic, grad_s_G_analytic = loss_fn.compute_analytical_log_variance_gradients(
        pred_E, target_E, pred_gap, target_gap
    )
    torch.testing.assert_close(loss_fn.s_E.grad, grad_s_E_analytic, atol=1e-12, rtol=1e-12)
    torch.testing.assert_close(loss_fn.s_G.grad, grad_s_G_analytic, atol=1e-12, rtol=1e-12)


def test_finite_difference_float64_enforcement_and_precision() -> None:
    """3. Verify Water forces satisfy L_inf < 1e-4 eV/A and relative Frobenius norm < 1e-4 in torch.float64 [M]."""
    result = verify_finite_difference_forces(
        H2O_COORDS,
        h2o_molecular_potential,
        step_size=1e-4,
        tolerance=1e-4,
    )
    assert isinstance(result, FiniteDiffVerificationResult)
    assert result.passed is True
    assert result.max_absolute_error < 1.0e-4
    assert result.relative_frobenius_error < 1.0e-4
    assert result.dtype == "torch.float64"
    assert result.atom_count == 3


def test_finite_difference_float32_rejection() -> None:
    """4. Assert attempting finite differences in torch.float32 immediately raises NumericalParityError [M]."""
    coords_f32 = H2O_COORDS.to(torch.float32)
    with pytest.raises(NumericalParityError) as exc_info:
        verify_finite_difference_forces(coords_f32, h2o_molecular_potential)
    assert exc_info.value.error_code == "TORQ_PRECISION_MISMATCH"
    assert "float64" in str(exc_info.value).lower()


def test_eckart_projector_idempotency_and_symmetry() -> None:
    """5. Assert Eckart projector satisfies max |P^2 - P| < 1e-14, max |P - P^T| < 1e-14, and Tr(P) = 3N - 6 = 3 [D]."""
    masses = torch.tensor([resolve_ciaaw_monoisotopic_mass(z) for z in H2O_Z], dtype=torch.float64)
    P, d_proj = compute_eckart_projector(H2O_COORDS, masses)

    assert d_proj == 6
    diff_idempotent = torch.max(torch.abs(P @ P - P)).item()
    diff_symmetric = torch.max(torch.abs(P - P.T)).item()
    trace_val = torch.trace(P).item()

    assert diff_idempotent < 1.0e-14
    assert diff_symmetric < 1.0e-14
    assert abs(trace_val - 3.0) < 1.0e-12


def test_vibrational_frequencies_water_codata_scaling() -> None:
    """6. Assert CODATA 2022 factor yields physical frequencies for Water (bend 1500-2000 cm^-1, stretches 3500-4000 cm^-1) [D]."""
    modes = analyze_vibrational_frequencies(H2O_COORDS, H2O_Z, h2o_molecular_potential)
    assert isinstance(modes, VibrationalModes)
    assert modes.imaginary_mode_count == 0
    assert modes.zero_point_energy_ev > 0.0
    assert len(modes.frequencies_cm1) == 3
    assert modes.projected_degrees_of_freedom == 6

    # Water vibrational frequencies: 1 bending mode and 2 stretching modes
    bend_freq = modes.frequencies_cm1[0]
    sym_stretch = modes.frequencies_cm1[1]
    asym_stretch = modes.frequencies_cm1[2]

    assert 1500.0 <= bend_freq <= 2000.0
    assert 3500.0 <= sym_stretch <= 4000.0
    assert 3500.0 <= asym_stretch <= 4000.0


def test_signed_imaginary_frequency_reporting() -> None:
    """7. On inverted transition-state potential, assert imaginary modes report as signed negative wavenumbers without NaN [D]."""
    def ts_potential(coords: torch.Tensor) -> torch.Tensor:
        # Invert curvature along H1-y coordinate to model a saddle point
        return h2o_molecular_potential(coords) - 20.0 * (coords[1, 1] - 0.7572) ** 2

    modes = analyze_vibrational_frequencies(H2O_COORDS, H2O_Z, ts_potential)
    assert modes.imaginary_mode_count >= 1

    # Verify imaginary mode reports negative signed frequency
    imaginary_modes = [f for f in modes.frequencies_cm1 if f < 0.0]
    assert len(imaginary_modes) == modes.imaginary_mode_count
    assert not any(math.isnan(f) for f in modes.frequencies_cm1)
    assert not any(math.isnan(ev) for ev in modes.eigenvalues)


def test_apple_silicon_mps_float64_cpu_fallback() -> None:
    """8. Assert device dispatcher routes ('mps', torch.float64) requests safely to CPU [M]."""
    dispatched_f64 = dispatch_device_safely("mps", torch.float64)
    assert dispatched_f64 == torch.device("cpu")

    dispatched_f32 = dispatch_device_safely("mps", torch.float32)
    assert dispatched_f32 == torch.device("mps")

    dispatched_cpu = dispatch_device_safely("cpu", torch.float64)
    assert dispatched_cpu == torch.device("cpu")


def test_hpc_distributed_lock_prohibition_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """9. Assert SLURM environment stages temporary scratch files to $SLURM_TMPDIR/cochem_torq_scratch [M]."""
    staging_slurm_nvme = tmp_path / "slurm_node_nvme"
    staging_slurm_nvme.mkdir()
    monkeypatch.setenv("SLURM_TMPDIR", str(staging_slurm_nvme))

    scratch_dir = resolve_hpc_safe_scratch()
    assert scratch_dir == staging_slurm_nvme / "cochem_torq_scratch"
    assert scratch_dir.is_dir()


def test_pydantic_v2_validation_and_contracts() -> None:
    """10. Test Pydantic schemas trap dimension errors, non-positive HOMO-LUMO gaps, and validate correct payloads [M]."""
    # 1. MultiTaskPrediction validation
    with pytest.raises(ValidationError):
        MultiTaskPrediction(
            energy=-14.2,
            forces=[[0.0, 0.0, 1.0]],
            homo_lumo_gap=-0.5,  # Invalid: non-positive gap
            energy_log_variance=0.0,
            gap_log_variance=0.0,
        )

    with pytest.raises(ValidationError):
        MultiTaskPrediction(
            energy=-14.2,
            forces=[[0.0, 1.0]],  # Invalid dimension != 3
            homo_lumo_gap=2.5,
            energy_log_variance=0.0,
            gap_log_variance=0.0,
        )

    valid_pred = MultiTaskPrediction(
        energy=-14.2,
        forces=[[0.0, 0.0, 1.0]],
        homo_lumo_gap=2.5,
        energy_log_variance=-1.2,
        gap_log_variance=-0.8,
    )
    assert valid_pred.homo_lumo_gap == 2.5

    # 2. FiniteDiffVerificationResult validation
    with pytest.raises(ValidationError):
        FiniteDiffVerificationResult(
            max_absolute_error=1e-5,
            relative_frobenius_error=1e-5,
            step_size=1e-4,
            passed=True,
            dtype="torch.float64",
            atom_count=0,  # Invalid: atom_count < 1
        )

    # 3. VibrationalModes validation
    with pytest.raises(ValidationError):
        VibrationalModes(
            frequencies_cm1=[1500.0, -200.0],
            zero_point_energy_ev=0.5,
            imaginary_mode_count=0,  # Invalid: reported 0 but frequencies has 1 negative
            eigenvalues=[10.0, -2.0],
            projected_degrees_of_freedom=6,
        )

    with pytest.raises(ValidationError):
        VibrationalModes(
            frequencies_cm1=[1500.0],
            zero_point_energy_ev=0.5,
            imaginary_mode_count=0,
            eigenvalues=[10.0, 20.0],  # Invalid: dimension mismatch
            projected_degrees_of_freedom=6,
        )


def test_methanol_finite_difference_and_modes() -> None:
    """11. Test 6-atom Methanol benchmark confirms 3N - 6 = 12 vibrational modes and passes finite differences under 1e-4 eV/A [M]."""
    # Finite-difference verification across all 18 Cartesian degrees of freedom
    fd_result = verify_finite_difference_forces(
        METHANOL_COORDS,
        methanol_molecular_potential,
        step_size=1e-4,
        tolerance=1e-4,
    )
    assert fd_result.passed is True
    assert fd_result.max_absolute_error < 1.0e-4

    # Vibrational analysis confirming 3N - 6 = 12 vibrational modes
    modes = analyze_vibrational_frequencies(
        METHANOL_COORDS,
        METHANOL_Z,
        methanol_molecular_potential,
    )
    assert modes.projected_degrees_of_freedom == 6
    assert len(modes.frequencies_cm1) == 12
    assert len(modes.eigenvalues) == 12
    assert modes.zero_point_energy_ev > 0.0


def test_onnx_export_spec_validation(tmp_path: Path) -> None:
    """12. Test ONNX dynamic axes specification includes 3D coordinate/force tensors, 2D edge_index, and traps opset < 17 [M]."""
    # Verify dynamic axes coverage
    assert "coordinates" in DEFAULT_DYNAMIC_AXES
    assert DEFAULT_DYNAMIC_AXES["coordinates"] == {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"}
    assert "forces" in DEFAULT_DYNAMIC_AXES
    assert DEFAULT_DYNAMIC_AXES["forces"] == {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"}
    assert "edge_index" in DEFAULT_DYNAMIC_AXES
    assert DEFAULT_DYNAMIC_AXES["edge_index"] == {0: "edge_direction", 1: "num_edges"}

    # Verify trap for opset < 17
    with pytest.raises((OpsetUnsupportedError, ValidationError)):
        ONNXExportSpec(
            opset_version=16,
            export_mechanism="dynamo_export_aot_autograd",
            dynamic_axes=DEFAULT_DYNAMIC_AXES,
            precision="float32",
        )

    # Valid export specification
    spec = ONNXExportSpec(
        opset_version=18,
        export_mechanism="direct_analytical_force_head",
        dynamic_axes=DEFAULT_DYNAMIC_AXES,
        precision="float32",
    )
    assert spec.opset_version == 18

    # Verify rejection of unsupported export mechanism
    with pytest.raises(OpsetUnsupportedError):
        invalid_spec = ONNXExportSpec(
            opset_version=18,
            export_mechanism="invalid_unknown_mechanism",
            dynamic_axes=DEFAULT_DYNAMIC_AXES,
            precision="float32",
        )
        validate_onnx_spec(invalid_spec)

    # End-to-end ONNX export and parity verification directly testing authentic MultiTaskHead
    class MolecularMultiTaskModel(nn.Module):
        """Physical molecular model integrating MultiTaskHead with 3D Cartesian coordinates [M]."""

        def __init__(self, in_features: int = 9, hidden_dim: int = 16) -> None:
            super().__init__()
            self.head = MultiTaskHead(
                in_features=in_features,
                hidden_dim=hidden_dim,
                epsilon_gap=1e-4,
                dtype=torch.float32,
            )

        def forward(self, coordinates: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            # coordinates: [batch_size, num_atoms, spatial_dim=3]
            batch_size = coordinates.shape[0]
            flat_coords = coordinates.reshape(batch_size, -1)
            energy, gap = self.head(flat_coords)
            return energy, gap

    model = MolecularMultiTaskModel(in_features=9, hidden_dim=16).eval()
    # Batched authentic physical Water coordinates converted to float32 [2, 3, 3]
    h2o_f32 = H2O_COORDS.to(torch.float32)
    sample_inputs = torch.stack([h2o_f32, h2o_f32 * 1.01], dim=0)  # [2, 3, 3]
    onnx_file = tmp_path / "multitask_head.onnx"

    # 1. End-to-end ONNX export and parity verification for direct_analytical_force_head with Water coordinates [M]
    export_to_onnx(
        model=model,
        sample_inputs=sample_inputs,
        export_path=onnx_file,
        spec=spec,
        input_names=["coordinates"],
        output_names=["energy", "homo_lumo_gap"],
    )
    assert onnx_file.exists()
    assert onnx_file.stat().st_size > 0

    max_err = verify_onnx_parity(
        torch_model=model,
        onnx_path=onnx_file,
        sample_inputs=sample_inputs,
        tolerance=1e-5,
    )
    assert max_err < 1e-5

    # 2. End-to-end ONNX export and parity verification for dynamo_export_aot_autograd with Methanol coordinates [M]
    spec_dynamo = ONNXExportSpec(
        opset_version=18,
        export_mechanism="dynamo_export_aot_autograd",
        dynamic_axes=DEFAULT_DYNAMIC_AXES,
        precision="float32",
    )
    methanol_model = MolecularMultiTaskModel(in_features=18, hidden_dim=16).eval()
    methanol_f32 = METHANOL_COORDS.to(torch.float32)
    methanol_inputs = torch.stack([methanol_f32, methanol_f32 * 1.005], dim=0)  # [2, 6, 3]
    onnx_file_dynamo = tmp_path / "methanol_dynamo.onnx"

    export_to_onnx(
        model=methanol_model,
        sample_inputs=methanol_inputs,
        export_path=onnx_file_dynamo,
        spec=spec_dynamo,
        input_names=["coordinates"],
        output_names=["energy", "homo_lumo_gap"],
    )
    assert onnx_file_dynamo.exists()
    assert onnx_file_dynamo.stat().st_size > 0

    max_err_dynamo = verify_onnx_parity(
        torch_model=methanol_model,
        onnx_path=onnx_file_dynamo,
        sample_inputs=methanol_inputs,
        tolerance=1e-5,
    )
    assert max_err_dynamo < 1e-5

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.