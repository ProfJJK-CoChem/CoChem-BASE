Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260901-suggestions\.in-progress\Perfected_SRS_Chunk_15_TORQ_Model_Backbones_Part_1_prompts.md.
Original prompt:
YOU ARE `cochem-coder`. Your task is to implement the complete, physically verified, and mathematically rigorous feature suite specified in Software Requirements Specification (SRS) Chunk 15: `TORQ_Model_Backbones_Part_1`.

You must implement every component in full adherence to the CoChem Zero-Mock directive, the Tripartite Workspace Air-Gap architecture, the dynamic Mendeleev mass retrieval mandate, the 6-Tier Environment Matrix, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must operate on genuine molecular geometries, authentic physical coordinates, and real chemical observables.

---

### MISSION & EXECUTION WORKFLOW

1. **Codebase Exploration**: Inspect the repository structure under `Libraries/` and `core/` in `CoChem-TORQ` to verify existing model wrappers, calculator interfaces, telemetry logging, and test fixtures.
2. **Implementation**: Implement all 5 target modules specified below with strict Python 3.10+ PEP 484 type annotations, thread-safe persistence, and custom typed domain exceptions (`EquivarianceViolationError`, `ForcefieldInferenceError`, `ObservableComputationError`, `TelemetryLoggingError`).
3. **Physical Test Suite**: Write comprehensive, unmocked test suites covering every component using authentic chemical structures (e.g., $\text{H}_2\text{O}$, Ethanol, Benzene, and small peptides). Validate rotational/translational $SE(3)$ energy invariance, force equivariance $\mathbf{F}(\mathbf{R}\mathbf{x}) = \mathbf{R}\mathbf{F}(\mathbf{x})$, and numerical finite-difference gradient parity.
4. **Physical Verification**: Execute the test suite using `pytest tests/ -v` via `run_command` in the terminal. Verify that all tests pass cleanly (exit code 0) and report raw STDOUT/STDERR.
5. **Execution Reporting**: Provide a final structured execution report detailing all files created and modified on disk.

---

### MODULE SPECIFICATIONS

#### 1. [TORQ] MACE (Multi-ACE) Equivariant Machine Learning Force Field Backbone
- **File Target**: `Libraries/cochem_torq_mace_backbone.py` (and export in `Libraries/__init__.py`)
- **Requirements**:
  - Implement `MACENetworkConfig` frozen dataclass:
    - `r_max: float = 5.0` (cutoff radius in Ångströms)
    - `num_bessel: int = 8` (radial Bessel basis count)
    - `num_polynomial_cutoff: int = 5` (polynomial envelope degree)
    - `max_ell: int = 3` (maximum spherical harmonic degree $l \le 3$)
    - `correlation: int = 3` (correlation order $\nu = 3$ for higher-body ACE contractions)
    - `hidden_irreps: str = "64x0e + 64x1o + 64x2e"`
    - `atomic_energies: dict[int, float] | None = None`
  - Implement `MACEBackbone(torch.nn.Module)`:
    - **Radial Expansion**: Spherical Bessel basis functions $j_0(n \pi r / r_{\max})$ multiplied by a smooth polynomial cutoff envelope $f_{\text{cut}}(r) = 1 - \frac{(p+1)(p+2)}{2} \left(\frac{r}{r_{\max}}\right)^p + p(p+2)\left(\frac{r}{r_{\max}}\right)^{p+1} - \frac{p(p+1)}{2}\left(\frac{r}{r_{\max}}\right)^{p+2}$ with $p=5$.
    - **Equivariant Node & Edge Feature Embedding**: Species embedding projection using dynamic atomic numbers $\mathbf{Z} \in \mathbb{Z}^N$.
    - **Multi-Body Tensor Contraction**: Construct higher-order atomic cluster expansion (ACE) features by contracting symmetric tensor products of equivariant edge messages over Clebsch-Gordan coefficients, mapping to invariant atomic scalar energies $E_i$.
    - **Total Potential Energy**: Evaluate total system potential energy $E = \sum_{i=1}^N E_i + \sum_{i=1}^N E_{\text{isolated}}(Z_i)$.
    - **Conservative Analytical Atomic Forces**: Calculate conservative atomic forces via exact spatial autograd:
      $$\mathbf{F}_i = -\frac{\partial E}{\partial \mathbf{R}_i}$$
      Enforce `torch.autograd.grad(outputs=E.sum(), inputs=coordinates, create_graph=True, retain_graph=True)`.
    - **SE(3) Equivariance & Invariance**: Guarantee strict potential energy rotational/translational invariance $E(\mathbf{R}\mathbf{x} + \mathbf{t}) = E(\mathbf{x})$ and force vector equivariance $\mathbf{F}(\mathbf{R}\mathbf{x}) = \mathbf{R}\mathbf{F}(\mathbf{x})$ within numerical precision ($10^{-6}\,\text{Hartree}$).
    - Raise `EquivarianceViolationError` if finite rotation tests fail equivariance verification thresholds.

#### 2. [TORQ] Customized NequIP Equivariant Potential Wrapper & ASE Calculator
- **File Target**: `Libraries/cochem_torq_nequip.py` (and export in `Libraries/__init__.py`)
- **Requirements**:
  - Implement `NequIPConfig` dataclass and `NequIPWrapper(torch.nn.Module)`:
    - Equivariant graph convolution interaction layers using tensor products of node representations and spherical harmonics $Y_l^m(\hat{\mathbf{r}}_{ij})$.
    - Continuous radial weight networks parameterizing interatomic convolutions.
    - Self-interaction layers with parity-preserving scalar/vector activations (e.g., shifted softplus for scalar parity $0e$, gate non-linearities for higher irreducible representations).
    - Energy readout head summing per-atom contributions $E = \sum_i \epsilon_i$ and analytical force backpropagation $\mathbf{F} = -\nabla_\mathbf{R} E$.
  - Implement `CoChemNequIPCalculator(ase.calculators.calculator.Calculator)`:
    - Inherit from ASE's base `Calculator` providing standard interfaces: `calculate(atoms, properties, system_changes)`.
    - Dynamic conversion between ASE `Atoms` objects (Cartesian coordinates, atomic numbers, periodic boundary conditions) and PyTorch equivariant graph tensors.
    - Return `energy` (converted to eV), `forces` (converted to eV/Å), and analytical virial stress tensor $\boldsymbol{\sigma} \in \mathbb{R}^{3 \times 3}$ when periodic boundary conditions are active:
      $$\sigma_{\alpha\beta} = -\frac{1}{V} \left( \sum_{i=1}^N m_i v_{i,\alpha} v_{i,\beta} + \sum_{i < j} r_{ij,\alpha} F_{ij,\beta} \right)$$
    - Dynamic mass retrieval using `mendeleev.element(symbol).mass`.
    - Trajectory stability: Verify energy conservation during microcanonical (NVE) molecular dynamics integration (drift $< 10^{-4}\,\text{eV/atom/ps}$).

#### 3. [TORQ] SchNet Invariant Continuous-Filter Convolutional Backbone
- **File Target**: `Libraries/cochem_torq_schnet.py` (and export in `Libraries/__init__.py`)
- **Requirements**:
  - Implement `SchNetConfig` frozen dataclass:
    - `num_features: int = 128`
    - `num_filters: int = 128`
    - `num_interactions: int = 6`
    - `r_max: float = 5.0`
    - `num_gaussians: int = 50`
  - Implement `SchNetBackbone(torch.nn.Module)`:
    - **Continuous-Filter Convolution (CFConv)**:
      $$v_i^{(l+1)} = \sum_{j \in \mathcal{N}(i)} v_j^{(l)} \odot W^{(l)}(d_{ij})$$
    - **Radial Distance Smearing**: Gaussian radial basis function expansion:
      $$e_k(d_{ij}) = \exp\left(-\gamma (d_{ij} - \mu_k)^2\right), \quad \mu_k \in [0, r_{\max}]$$
      combined with a cosine cutoff filter $f_{\text{cut}}(d_{ij}) = \frac{1}{2}\left[\cos\left(\frac{\pi d_{ij}}{r_{\max}}\right) + 1\right]$ for $d_{ij} \le r_{\max}$.
    - **Atom-wise Readout & Force Derivation**: Atom-wise energy multi-layer perceptron yielding atomic energies $E_i$; aggregate total energy $E = \sum_i E_i$.
    - Compute conservative forces via analytical gradient $\mathbf{F}_i = -\nabla_{\mathbf{R}_i} E$.
  - Implement `SchNetFallbackRouter`:
    - Provide automatic fallback routing to SchNet when GPU memory constraints or missing equivariant dependencies prevent MACE/NequIP execution.
    - Seamlessly preserve unified input/output schema across all backbones.

#### 4. [TORQ] Differentiable Physical Observables (Dipole Moments & Polarizability)
- **File Target**: `Libraries/cochem_torq_observables.py` (and export in `Libraries/__init__.py`)
- **Requirements**:
  - Implement `DifferentiableObservables(torch.nn.Module)`:
    - **Equivariant Permanent Dipole Moment $\vec{\mu}$**:
      - Method A (Vector Head): Sum of atomic $l=1$ equivariant vector projections: $\vec{\mu}_{\text{vec}} = \sum_{i=1}^N \mathbf{v}_i^{(l=1)}$.
      - Method B (Latent Charge Redistribution): Predict latent partial atomic charges $q_i(\mathbf{R}, \mathbf{Z})$ with strict conservation of total formal molecular charge $Q_{\text{tot}}$:
        $$\tilde{q}_i = q_i - \frac{1}{N} \left( \sum_{j=1}^N q_j - Q_{\text{tot}} \right)$$
        $$\vec{\mu}_{\text{charge}} = \sum_{i=1}^N \tilde{q}_i (\mathbf{r}_i - \mathbf{r}_{\text{COM}})$$
        where $\mathbf{r}_{\text{COM}} = \frac{\sum_i m_i \mathbf{r}_i}{\sum_i m_i}$ is the molecular center of mass evaluated dynamically with `mendeleev` atomic masses.
      - Enforce translational invariance: for neutral molecules ($Q_{\text{tot}} = 0$), $\vec{\mu}$ is invariant to arbitrary origin translations $\mathbf{r} \to \mathbf{r} + \mathbf{t}$.
    - **Molecular Polarizability Tensor $\boldsymbol{\alpha} \in \mathbb{R}^{3 \times 3}$**:
      - Formulate polarizability as the analytical response to an external electric field $\boldsymbol{\mathcal{E}}$ added to the Hamiltonian: $E(\mathbf{R}, \boldsymbol{\mathcal{E}}) = E_0(\mathbf{R}) - \vec{\mu} \cdot \boldsymbol{\mathcal{E}} - \frac{1}{2} \boldsymbol{\mathcal{E}}^T \boldsymbol{\alpha} \boldsymbol{\mathcal{E}}$.
      - Compute tensor elements via second-order reverse-mode automatic differentiation:
        $$\alpha_{\mu\nu} = -\frac{\partial^2 E}{\partial \mathcal{E}_\mu \partial \mathcal{E}_\nu} = \frac{\partial \mu_\mu}{\partial \mathcal{E}_\nu}$$
      - Evaluate physical tensor invariants:
        - Mean isotropic polarizability: $\bar{\alpha} = \frac{1}{3} \operatorname{Tr}(\boldsymbol{\alpha}) = \frac{\alpha_{xx} + \alpha_{yy} + \alpha_{zz}}{3}$.
        - Anisotropic polarizability: $\Delta \alpha = \sqrt{\frac{1}{2} \left[ (\alpha_{xx} - \alpha_{yy})^2 + (\alpha_{yy} - \alpha_{zz})^2 + (\alpha_{zz} - \alpha_{xx})^2 + 6(\alpha_{xy}^2 + \alpha_{yz}^2 + \alpha_{zx}^2) \right]}$.
    - Raise `ObservableComputationError` on singular matrices or broken tensor symmetry ($|\alpha_{\mu\nu} - \alpha_{\nu\mu}| > 10^{-5}$).

#### 5. [TORQ] E(3) Equivariant TensorBoard Telemetry & Visualizer
- **File Target**: `Libraries/cochem_torq_tensorboard.py` (and export in `Libraries/__init__.py`)
- **Requirements**:
  - Implement `EquivariantTensorBoardLogger`:
    - `__init__(log_dir: Path | str, flush_secs: int = 10, purge_step: int | None = None) -> None`
    - Support air-gap environments: use `filelock.FileLock` for multi-process safe file writing.
    - Deterministically detect headless environments and suppress interactive GUI errors.
  - Implement methods:
    - `log_forces_3d(tag: str, coords: np.ndarray, pred_forces: np.ndarray, ref_forces: np.ndarray | None, step: int) -> None`:
      - Construct 3D vector glyphs (coordinates, direction vectors, magnitudes) and export point clouds/meshes using `SummaryWriter.add_mesh`.
      - Color glyphs dynamically based on force discrepancy norm $\|\mathbf{F}_{\text{pred}} - \mathbf{F}_{\text{ref}}\|$.
    - `log_dipole_vector(tag: str, coords: np.ndarray, dipole: np.ndarray, step: int) -> None`:
      - Render molecular geometry alongside the total dipole moment vector originating from the center of mass.
    - `log_equivariance_error(tag: str, rotation_matrix: np.ndarray, error_norm: float, step: int) -> None`:
      - Log rotational equivariance parity metrics as scalar summaries across training epochs.
    - `log_metrics(metrics: dict[str, float], step: int) -> None`:
      - Record energy MAE, force RMSE, force cosine similarity, and observable residuals.

---

### TEST SUITE SPECIFICATIONS

1. **`tests/test_torq_mace_backbone.py`**:
   - **SE(3) Transformation Tests**: For Water ($\text{H}_2\text{O}$), Ethanol, and Benzene, generate 5 random 3D rotation matrices $\mathbf{R} \in SO(3)$ and translations $\mathbf{t} \in \mathbb{R}^3$. Verify:
     - Energy Invariance: $|E(\mathbf{R}\mathbf{x} + \mathbf{t}) - E(\mathbf{x})| < 10^{-5}\,\text{Hartree}$.
     - Force Equivariance: $\|\mathbf{F}(\mathbf{R}\mathbf{x}) - \mathbf{R}\mathbf{F}(\mathbf{x})\|_\infty < 10^{-5}\,\text{Hartree/Bohr}$.
   - **Numerical Force Parity**: Compute analytical forces $-\nabla_\mathbf{R} E$ and compare against central finite-difference gradients with step $h = 10^{-4}\text{ \AA}$. Verify relative error $< 10^{-3}$.

2. **`tests/test_torq_nequip.py`**:
   - **Equivariant Convolution**: Verify message-passing forward pass preserves equivariance through all interaction blocks.
   - **ASE Calculator Integration**: Wrap model in `CoChemNequIPCalculator` and attach to an ASE `Atoms` object for $\text{H}_2\text{O}$. Run 10 steps of Velocity Verlet NVE molecular dynamics. Verify total energy is conserved within $10^{-4}\,\text{eV}$.

3. **`tests/test_torq_schnet.py`**:
   - **Continuous-Filter Invariance**: Confirm SchNet energy output is strictly invariant under arbitrary 3D rotations and translations.
   - **Force Derivative Verification**: Verify that analytical forces computed from SchNet match spatial autograd gradients and conserve total momentum ($\sum_i \mathbf{F}_i = \mathbf{0}$).
   - **Fallback Routing**: Test `SchNetFallbackRouter` dynamically selecting SchNet when higher-order equivariant backbones are toggled off.

4. **`tests/test_torq_observables.py`**:
   - **Dipole Origin Invariance**: For neutral molecules (e.g., $\text{CO}_2$, $\text{H}_2\text{O}$), shift coordinates by arbitrary translation $\mathbf{t} = (10.0, -5.0, 2.5)\text{ \AA}$. Verify calculated dipole moment $\vec{\mu}$ remains identical within $10^{-6}\text{ Debye}$.
   - **Polarizability Symmetry**: Verify $\alpha_{\mu\nu} = \alpha_{\nu\mu}$ across all $3 \times 3$ tensor components for Benzene and Water. Verify $\operatorname{Tr}(\boldsymbol{\alpha}) > 0$.

5. **`tests/test_torq_tensorboard.py`**:
   - **Headless Telemetry**: Instantiate `EquivariantTensorBoardLogger` in a temporary directory (`tempfile.TemporaryDirectory`). Log 3D force vectors, dipole vectors, and scalar training metrics. Ensure no unhandled exceptions or headless display crashes occur and event files are written to disk.

---

### STRICT COMPLIANCE & ARCHITECTURAL INVARIANTS

1. **Zero-Mock Mandate**: Every neural layer, mathematical formula, autograd step, and test assertion must execute physically. Absolutely no `pass` stubs, no `NotImplementedError`, and no synthetic mock arrays (`np.zeros`, `np.ones` as dummy outputs).
2. **Mendeleev Mandate**: Dynamic mass lookups must execute strictly via `mendeleev.element(symbol).mass` or `element(Z).mass`. No hardcoded atomic mass dictionaries.
3. **Tripartite Workspace Air-Gap**: Temporary geometries, scratch tensors, and tensorboard logs must reside strictly in `$COCHEM_SCRATCH_DIR` or `tempfile.gettempdir()`. Source code resides in Ring 1; persistent models in Ring 2 (`$COCHEM_ARTIFACTS_DIR`).
4. **Thread-Safety & Multi-Process Locking**: File I/O for telemetry and checkpoints must be protected by `filelock.FileLock`.

---

### ACTION PLAN FOR CODER

1. Implement `Libraries/cochem_torq_mace_backbone.py` with `MACEBackbone` and analytical force gradients.
2. Implement `Libraries/cochem_torq_nequip.py` with `NequIPWrapper` and `CoChemNequIPCalculator` (ASE integration).
3. Implement `Libraries/cochem_torq_schnet.py` with `SchNetBackbone` and `SchNetFallbackRouter`.
4. Implement `Libraries/cochem_torq_observables.py` with permanent dipole moments and polarizability tensor derivatives.
5. Implement `Libraries/cochem_torq_tensorboard.py` with `EquivariantTensorBoardLogger`.
6. Export new components in `Libraries/__init__.py`.
7. Author unmocked test suites:
   - `tests/test_torq_mace_backbone.py`
   - `tests/test_torq_nequip.py`
   - `tests/test_torq_schnet.py`
   - `tests/test_torq_observables.py`
   - `tests/test_torq_tensorboard.py`
8. Execute tests via `pytest tests/ -v` using `run_command` and verify exit code 0.
Waiting for `cochem-audit` to complete the adversarial verification of the generated prompt.
Waiting for `cochem-scribe` to complete the remediation of the Coding Prompt.
Waiting for `cochem-scribe` to finish generating the remediated prompt.
Waiting for `cochem-audit` to complete its evaluation of the remediated prompt.
YOU ARE cochem-coder. Your task is to implement the complete, mathematically rigorous, fully remediated, and physically verified machine learning potential and tensor backbone suite specified in Software Requirements Specification (SRS) Chunk 15: `TORQ_Model_Backbones_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev monoisotopic mass mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical species, genuine molecular coordinates, and CODATA 2022 physical constants.

---

### MANDATORY REMEDIATION OF ALL 9 AUDIT DEFECTS

1. **DEF-01: Virial Stress via Strain Autograd [D]:**
   The ASE static potential calculator (`TORQCalculator`) must evaluate virial stress strictly via spatial strain automatic differentiation:
   $$\sigma_{\alpha\beta} = \left. \frac{1}{V} \frac{\partial E}{\partial \epsilon_{\alpha\beta}} \right|_{\boldsymbol{\epsilon}=\mathbf{0}} \quad [D]$$
   where the unit cell $\mathbf{C}$ and atomic coordinates $\mathbf{R}$ undergo symmetric virtual strain $\mathbf{R}' = \mathbf{R}(\mathbf{I} + \boldsymbol{\epsilon})$ and $\mathbf{C}' = \mathbf{C}(\mathbf{I} + \boldsymbol{\epsilon})$. Virial stress must be returned strictly in standard ASE 6-element Voigt notation:
   $$\mathbf{v}_{\text{Voigt}} = [ \sigma_{xx}, \sigma_{yy}, \sigma_{zz}, \sigma_{yz}, \sigma_{xz}, \sigma_{xy} ] \quad [M]$$
   in units of $\text{eV/\AA}^3$ [M]. The calculator MUST NOT include any particle velocities, momenta, or kinetic energy terms ($m_i v_{i\alpha} v_{i\beta}$), as kinetic stress is handled independently by molecular dynamics integrators. Pairwise virial summations ($\sum r_{ij} F_{ij}$) are strictly forbidden due to multi-body potential non-locality in MACE and NequIP.

2. **DEF-02: Rigorous Polarizability Formulation [D]:**
   Implement polarizability using a physically rigorous, differentiable formulation via:
   - **Primary Readout Head:** A direct equivariant rank-2 symmetric tensor readout head:
     $$\boldsymbol{\alpha}(\mathbf{R}) = \sum_{i=1}^N \boldsymbol{\alpha}_i = \sum_{i=1}^N \left( a_i^{(0e)} \mathbf{I}_{3 \times 3} + \mathbf{A}_i^{(2e)} \right) \quad [D]$$
     where $a_i^{(0e)}$ is an invariant scalar trace density ($\bar{\alpha}_i = \frac{1}{3}\text{Tr}(\boldsymbol{\alpha}_i)$), and $\mathbf{A}_i^{(2e)}$ is an equivariant symmetric traceless rank-2 tensor constructed from irreducible representations or dyadic vector feature products ($\sum_k w_k (\vec{\mathbf{v}}_{i,k} \otimes \vec{\mathbf{v}}_{i,k} - \frac{1}{3}\|\vec{\mathbf{v}}_{i,k}\|^2 \mathbf{I})$). The antisymmetric component ($1e$) identically vanishes for static response.
   - **Response Head:** Explicit field-coupled message passing where an external electric field $\boldsymbol{\mathcal{E}} \in \mathbb{R}^3$ is injected into edge displacements or atomic vector features, inducing a polarized dipole $\vec{\mu}(\mathbf{R}, \boldsymbol{\mathcal{E}})$, allowing polarizability to be evaluated analytically or via autograd response:
     $$\alpha_{\mu\nu} = \left. \frac{\partial \mu_\mu(\mathbf{R}, \boldsymbol{\mathcal{E}})}{\partial \mathcal{E}_\nu} \right|_{\boldsymbol{\mathcal{E}}=\mathbf{0}} \quad [D]$$

3. **DEF-03: $C^2$-Smooth Polynomial Cutoff Envelope [D]:**
   Replace cosine cutoffs across all models (SchNet, MACE, NequIP) with the $C^2$-smooth polynomial cutoff envelope function:
   $$f_{\text{cut}}(r) = \begin{cases} 1 - 10\left(\frac{r}{r_{\max}}\right)^3 + 15\left(\frac{r}{r_{\max}}\right)^4 - 6\left(\frac{r}{r_{\max}}\right)^5 & \text{for } r \le r_{\max} \\ 0 & \text{for } r > r_{\max} \end{cases} \quad [D]$$
   guaranteeing $f_{\text{cut}}(r_{\max}) = 0$, $f'_{\text{cut}}(r_{\max}) = 0$, and $f''_{\text{cut}}(r_{\max}) = 0$ to eliminate delta-function singularities in vibrational Hessians and second-order response tensors.

4. **DEF-04: Unit System Consistency & Strict Numerical Tolerances [M]:**
   Standardize strictly on CODATA 2022 / ASE base units:
   - Energy: $\text{eV}$ ($1\text{ eV} = 1.602176634 \times 10^{-19}\text{ J}$) [M]
   - Coordinates: $\text{\AA}$ ($1\text{ \AA} = 10^{-10}\text{ m}$) [M]
   - Forces: $\text{eV/\AA}$ ($1\text{ eV/\AA} \approx 1.602176634 \times 10^{-9}\text{ N}$) [M]
   - Stress: $\text{eV/\AA}^3$ ($1\text{ eV/\AA}^3 \approx 160.21766208\text{ GPa}$) [M]
   - Dipole Moment: $\text{Debye}$ ($1\text{ e}\cdot\text{\AA} = 4.80320427\text{ Debye}$) [M]
   - Polarizability: $\text{\AA}^3$ (volume polarizability $\alpha' = \alpha / 4\pi\epsilon_0$) [M]
   - Conversion Constants: $1\text{ Hartree} = 27.211386245988\text{ eV}$ [M], $1\text{ Bohr} = 0.529177210903\text{ \AA}$ [M], $1\text{ Hartree/Bohr} \approx 51.4220674763\text{ eV/\AA}$ [D].
   - Finite-difference verification must use step size $h = 10^{-4}\text{ \AA}$ in `torch.float64` with absolute tolerance $\max_{i,\alpha} |F_{i,\alpha}^{\text{autograd}} - F_{i,\alpha}^{\text{FD}}| \le 10^{-4}\text{ eV/\AA}$ [M].
   - Net force conservation (zero momentum drift): $\|\sum_i \mathbf{F}_i\|_2 \le 10^{-6}\text{ eV/\AA}$ [M].

5. **DEF-05: Self-Contained Pure-PyTorch $E(3)$ Tensor Implementation & `float64` Mandate [M], [D]:**
   Because `e3nn`, `mace`, and `nequip` are not present in the runtime environment, implement a self-contained, mathematically complete pure-PyTorch real spherical harmonics ($l \le 2$) and Cartesian equivariant tensor layer module. Provide seamless fallback routing to invariant SchNet for Tier 1 CPU. Mandate `torch.float64` for all finite-difference checks to eliminate single-precision subtractive cancellation errors.

6. **DEF-06: Pydantic v2 Configuration Schemas & Exception Hierarchy [M]:**
   All configuration and data schemas must be Pydantic v2 `BaseModel` classes configured with `model_config = ConfigDict(frozen=True, extra="forbid")`. All custom exceptions must inherit from `TorqError`, which inherits from `CoChemError`.

7. **DEF-07: HDF5 Persistence with Concurrency Dual-Locking [M]:**
   Provide thread-safe and process-safe HDF5 persistence for datasets, weights, and telemetry using dual-locking: `filelock.FileLock(path.with_suffix(".h5.lock"), timeout=30.0)` for cross-process concurrency and `threading.Lock()` for intra-process thread-safety.

8. **DEF-08: Method Matrix v4 Provenance Tags [M]:**
   Every equation, parameter, threshold, and operational constant must bear explicit provenance tags: `[M]` (Mandated/Measured), `[D]` (Derived), or `[E]` (Empirical/Calibrated).

9. **DEF-09: Dynamic Pure Monoisotopic Masses [M], [D]:**
   Query pure monoisotopic masses via `mendeleev.element(Z).isotopes` filtered by maximum abundance (`max(el.isotopes, key=lambda iso: (iso.abundance or 0.0, iso.mass_number)).mass`). Cast queried masses dynamically to a PyTorch tensor matching the active device and dtype (`torch.tensor(masses, dtype=dtype, device=device)`). Ghost atoms ($Z=0$) are assigned $0.0\,\text{u}$ mass without querying `mendeleev`.

---

### MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Domain Exceptions & Pydantic v2 Models (`cochem/torq/models/schemas.py` & `cochem/torq/errors.py`)
- **Exception Hierarchy**:
  ```python
  class CoChemError(Exception):
      """Base exception for all CoChem operations."""
      pass

  class TorqError(CoChemError):
      """Base exception for TORQ potential backbones and calculators."""
      pass

  class TorqModelBackboneError(TorqError):
      """Raised when network forward pass or tensor contraction fails."""
      pass

  class EquivarianceViolationError(TorqError):
      """Raised when E(3) rotational or inversion equivariance tolerance is violated."""
      pass

  class AutogradForceError(TorqError):
      """Raised when coordinate autograd graph construction or force derivation fails."""
      pass

  class ObservableComputationError(TorqError):
      """Raised when dipole or polarizability evaluation encounters singular values."""
      pass

  class TorqPersistenceLockError(TorqError):
      """Raised when filelock or threading lock acquisition exceeds timeout ceiling."""
      pass

  class TorqDeviceAllocationError(TorqError):
      """Raised when GPU device indexing or CUDA memory allocation fails."""
      pass

  class PeriodicBoundaryConditionError(TorqError):
      """Raised when PBC cell vectors are singular or minimum image convention fails."""
      pass
  ```
- **Pydantic v2 Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
  - `TorqModelConfig`:
    - `model_name: Literal["schnet", "mace", "nequip", "cartesian_equivariant"] = "cartesian_equivariant"`
    - `r_max: float = Field(default=5.0, gt=0.0, le=10.0, description="Cutoff radius in Angstroms [E]")`
    - `num_radial_basis: int = Field(default=32, ge=8, le=128, description="Number of radial basis functions [E]")`
    - `num_channels: int = Field(default=64, ge=16, le=512, description="Hidden feature dimensionality [E]")`
    - `num_layers: int = Field(default=3, ge=1, le=8, description="Number of interaction layers [E]")`
    - `l_max: int = Field(default=2, ge=0, le=3, description="Maximum spherical tensor degree [M]")`
    - `charge_neutral: bool = Field(default=True, description="Enforce molecular charge neutrality [M]")`
  - `AtomicConfigurationInput`:
    - `atomic_numbers: List[int] = Field(min_length=1, description="IUPAC atomic numbers Z [M]")`
    - `coordinates: List[Tuple[float, float, float]] = Field(min_length=1, description="Cartesian coordinates in Angstroms [M]")`
    - `pbc: Tuple[bool, bool, bool] = Field(default=(False, False, False), description="Periodic boundary conditions [M]")`
    - `cell: Optional[List[List[float]]] = Field(default=None, description="3x3 unit cell vectors in Angstroms [M]")`
    - `total_charge: float = Field(default=0.0, description="Net molecular charge in elementary charge units [M]")`
  - `PotentialEnergyOutput`:
    - `energy: float = Field(description="Scalar potential energy in eV [M]")`
    - `forces: List[Tuple[float, float, float]] = Field(description="Negative energy gradients in eV/Angstrom [M]")`
    - `stress: Optional[List[float]] = Field(default=None, description="Voigt 6-vector virial stress in eV/Angstrom^3 [M]")`
  - `ObservableOutput`:
    - `dipole_vector: Tuple[float, float, float] = Field(description="Electric dipole moment vector in Debye [M]")`
    - `polarizability_tensor: List[List[float]] = Field(description="3x3 symmetric polarizability tensor in Angstrom^3 [M]")`
    - `mean_polarizability: float = Field(description="Isotropic polarizability scalar in Angstrom^3 [M]")`
    - `anisotropy: float = Field(description="Polarizability tensor anisotropy in Angstrom^3 [D]")`
  - `HDF5PersistenceConfig`:
    - `file_path: Path = Field(description="Target .h5 file path")`
    - `compression: str = Field(default="gzip", description="HDF5 compression filter")`
    - `compression_opts: int = Field(default=4, ge=0, le=9)`
    - `lock_timeout_seconds: float = Field(default=30.0, gt=0.0)`

---

#### 2. Monoisotopic Mass Engine (`cochem/torq/utils/mendeleev_masses.py`)
- Provide `get_monoisotopic_masses(atomic_numbers: List[int], device: torch.device, dtype: torch.dtype) -> torch.Tensor`:
  - Dynamically query `mendeleev.element(Z).isotopes`.
  - Filter by maximum isotopic abundance:
    ```python
    isotopes = [iso for iso in el.isotopes if iso.abundance is not None and iso.abundance > 0.0]
    if isotopes:
        mono_mass = float(max(isotopes, key=lambda iso: iso.abundance).mass)
    else:
        mono_mass = float(max(el.isotopes, key=lambda iso: iso.mass_number).mass)
    ```
  - Ghost atoms ($Z=0$): assign $0.0\,\text{u}$ without calling `mendeleev`.
  - Return `torch.tensor(mass_list, dtype=dtype, device=device)`.

---

#### 3. $C^2$-Smooth Radial Basis & Spherical Harmonics (`cochem/torq/backbones/cutoff.py` & `spherical_harmonics.py`)
- **Cutoff Envelope**:
  ```python
  def polynomial_cutoff(r: torch.Tensor, r_max: float) -> torch.Tensor:
      """
      C^2-smooth polynomial cutoff envelope [D]:
      f_cut(r) = 1 - 10(r/r_max)^3 + 15(r/r_max)^4 - 6(r/r_max)^5 for r <= r_max, else 0.
      """
      u = r / r_max
      mask = (r <= r_max).to(r.dtype)
      u_clamped = torch.clamp(u, max=1.0)
      envelope = 1.0 - 10.0 * (u_clamped ** 3) + 15.0 * (u_clamped ** 4) - 6.0 * (u_clamped ** 5)
      return envelope * mask
  ```
- **Pure-PyTorch Real Spherical Harmonics ($l \le 2$)**:
  - Implement exact analytical formulas for unit direction vectors $\hat{\mathbf{r}} = \mathbf{r} / \|\mathbf{r}\|$:
    - $Y_0^0(\hat{\mathbf{r}}) = \frac{1}{\sqrt{4\pi}}$ [D]
    - $Y_1^{-1}(\hat{\mathbf{r}}) = \sqrt{\frac{3}{4\pi}}\hat{y}$, $Y_1^0(\hat{\mathbf{r}}) = \sqrt{\frac{3}{4\pi}}\hat{z}$, $Y_1^1(\hat{\mathbf{r}}) = \sqrt{\frac{3}{4\pi}}\hat{x}$ [D]
    - $Y_2^{-2} = \sqrt{\frac{15}{4\pi}}\hat{x}\hat{y}$, $Y_2^{-1} = \sqrt{\frac{15}{4\pi}}\hat{y}\hat{z}$, $Y_2^0 = \sqrt{\frac{5}{16\pi}}(3\hat{z}^2 - 1)$, $Y_2^1 = \sqrt{\frac{15}{4\pi}}\hat{x}\hat{z}$, $Y_2^2 = \sqrt{\frac{15}{16\pi}}(\hat{x}^2 - \hat{y}^2)$ [D]
- **Radial Bessel / Gaussian Basis**:
  - Sinusoidal Bessel or Gaussian basis expanded across `num_radial_basis` bins, multiplied by `polynomial_cutoff(r, r_max)`.

---

#### 4. Neural Network Potentials (`cochem/torq/backbones/`)
- **SchNet Continuous-Filter Convolution Backbone** (`schnet.py`):
  - Invariant scalar message passing with $C^2$ polynomial cutoff.
  - Embedding layer for atomic numbers $Z \in [1, 118]$.
  - Interaction blocks: continuous-filter convolution (`CFConv`) using dense radial filter generator on interatomic distances $d_{ij}$.
  - Shifted softplus activation: $s(x) = \ln\left(\frac{1 + e^x}{2}\right)$ or SiLU.
  - Atomic energy readout head: $E_i = \text{MLP}(s_i)$, $E = \sum_i E_i$.
- **Cartesian Equivariant Tensor Backbone (MACE / NequIP)** (`equivariant_tensor.py`):
  - Self-contained pure-PyTorch equivariant message passing updating:
    - Scalar features $\mathbf{s}_i \in \mathbb{R}^{C}$ ($L=0$)
    - Vector features $\vec{\mathbf{v}}_i \in \mathbb{R}^{C \times 3}$ ($L=1$)
  - Equivariant updates:
    $$\Delta \vec{\mathbf{v}}_i = \sum_{j \in \mathcal{N}(i)} \left( W_{vv}(r_{ij}) \vec{\mathbf{v}}_j + W_{sv}(r_{ij}) \mathbf{s}_j \hat{\mathbf{r}}_{ij} \right) f_{\text{cut}}(r_{ij}) \quad [D]$$
    $$\Delta \mathbf{s}_i = \sum_{j \in \mathcal{N}(i)} \left( W_{ss}(r_{ij}) \mathbf{s}_j + W_{vs}(r_{ij}) (\vec{\mathbf{v}}_j \cdot \hat{\mathbf{r}}_{ij}) \right) f_{\text{cut}}(r_{ij}) \quad [D]$$
  - Multi-body tensor contraction:
    $$\mathbf{A}_i^{(2e)} = \sum_{c=1}^{C} w_c \left( \vec{\mathbf{v}}_{i,c} \otimes \vec{\mathbf{v}}_{i,c} - \frac{1}{3}\|\vec{\mathbf{v}}_{i,c}\|^2 \mathbf{I}_{3 \times 3} \right) \quad [D]$$
  - Energy readout: $E_i = \text{MLP}(\mathbf{s}_i)$, $E = \sum_i E_i$ [D].
  - Forces evaluated analytically via autograd: $\mathbf{F}_i = -\frac{\partial E}{\partial \mathbf{r}_i}$ [D].
  - Center-of-mass momentum projection:
    $$\mathbf{F}_i^{\text{proj}} = \mathbf{F}_i - \frac{1}{N} \sum_{j=1}^N \mathbf{F}_j \quad [D]$$
    guaranteeing $\|\sum_i \mathbf{F}_i^{\text{proj}}\| \le 10^{-6}\text{ eV/\AA}$ [M].

---

#### 5. Differentiable Observables Engine (`cochem/torq/backbones/observables.py`)
- **Electric Dipole Moment**:
  - Predicted via atomic partial charges $q_i = \text{MLP}_q(\mathbf{s}_i)$ and atomic polarization vectors $\vec{\mathbf{p}}_i = \text{Linear}(\vec{\mathbf{v}}_i)$.
  - Charge neutrality constraint:
    $$\tilde{q}_i = q_i - \frac{1}{N} \left( \sum_{j=1}^N q_j - Q_{\text{tot}} \right) \quad [D]$$
  - Dipole vector:
    $$\vec{\mu} = \left[ \sum_{i=1}^N \tilde{q}_i (\mathbf{r}_i - \mathbf{r}_{\text{COM}}) + \sum_{i=1}^N \vec{\mathbf{p}}_i \right] \times 4.80320427 \quad [\text{Debye}] \quad [M]$$
- **Polarizability Tensor**:
  - Direct equivariant rank-2 tensor readout head:
    $$\boldsymbol{\alpha} = \sum_{i=1}^N \left( a_i^{(0e)} \mathbf{I}_{3 \times 3} + \mathbf{A}_i^{(2e)} \right) \quad [\text{\AA}^3] \quad [D]$$
  - Mean isotropic polarizability: $\bar{\alpha} = \frac{1}{3} \text{Tr}(\boldsymbol{\alpha})$ [D].
  - Polarizability anisotropy:
    $$\gamma^2 = \frac{1}{2} \left[ (\alpha_{xx} - \alpha_{yy})^2 + (\alpha_{yy} - \alpha_{zz})^2 + (\alpha_{zz} - \alpha_{xx})^2 + 6(\alpha_{xy}^2 + \alpha_{yz}^2 + \alpha_{xz}^2) \right] \quad [D]$$
  - Field-coupled response verification: Provide numerical verification that coupling an external electric field $\boldsymbol{\mathcal{E}}$ verifies $\alpha_{\mu\nu} = \left. \frac{\partial \mu_\mu}{\partial \mathcal{E}_\nu} \right|_{\boldsymbol{\mathcal{E}}=\mathbf{0}}$ [D].

---

#### 6. ASE Calculator with Strain Autograd Virial Stress (`cochem/torq/calculators/ase_calc.py`)
- Implement `TORQCalculator(ase.calculators.calculator.Calculator)`:
  - Supported properties: `["energy", "forces", "stress", "dipole", "polarizability"]` [M].
  - In `calculate(atoms, properties, system_changes)`:
    - Convert `atoms.get_positions()` to `torch.tensor(..., dtype=torch.float64, requires_grad=True)`.
    - If `stress` requested and `atoms.pbc.any()`:
      - Create virtual strain tensor $\boldsymbol{\epsilon} \in \mathbb{R}^{3 \times 3}$ initialized to zeros with `requires_grad=True`.
      - Symmetrize strain: $\boldsymbol{\epsilon}_{\text{sym}} = \frac{1}{2}(\boldsymbol{\epsilon} + \boldsymbol{\epsilon}^T)$.
      - Deform positions: $\mathbf{R}' = \mathbf{R} + \mathbf{R} \boldsymbol{\epsilon}_{\text{sym}}$.
      - Deform cell: $\mathbf{C}' = \mathbf{C} + \mathbf{C} \boldsymbol{\epsilon}_{\text{sym}}$.
      - Forward pass: $E = \text{model}(\mathbf{Z}, \mathbf{R}', \mathbf{C}')$.
      - Analytical forces: $\mathbf{F} = -\nabla_{\mathbf{R}} E$ in $\text{eV/\AA}$ [M].
      - Virial stress:
        $$\boldsymbol{\sigma} = \frac{1}{V} \frac{\partial E}{\partial \boldsymbol{\epsilon}} \quad [\text{eV/\AA}^3] \quad [D]$$
      - Convert to Voigt 6-vector via ASE convention:
        `[sigma[0,0], sigma[1,1], sigma[2,2], sigma[1,2], sigma[0,2], sigma[0,1]]` [M].
      - No velocities or kinetic energy terms!

---

#### 7. Dual-Locked Thread-Safe & Process-Safe HDF5 Persistence (`cochem/torq/storage/hdf5_persister.py`)
- Implement `HDF5TorqStorage`:
  - Dual-locking mechanism:
    ```python
    self._thread_lock = threading.Lock()
    self._file_lock = filelock.FileLock(str(self.path) + ".lock", timeout=self.timeout)
    ```
  - Context manager `with self._thread_lock, self._file_lock:` for all read/write operations.
  - Datasets structured with gzip compression and chunking:
    - `/trajectories/{traj_id}/coordinates`: $(T, N, 3)$ float64
    - `/trajectories/{traj_id}/forces`: $(T, N, 3)$ float64
    - `/trajectories/{traj_id}/energy`: $(T,)$ float64
    - `/trajectories/{traj_id}/stress`: $(T, 6)$ float64
    - `/trajectories/{traj_id}/dipole`: $(T, 3)$ float64
    - `/trajectories/{traj_id}/polarizability`: $(T, 3, 3)$ float64
    - `/trajectories/{traj_id}/atomic_numbers`: $(N,)$ int32
    - `/trajectories/{traj_id}/monoisotopic_masses`: $(N,)$ float64

---

### ZERO-MOCK TEST SUITE SPECIFICATIONS (`tests/torq/test_model_backbones.py`)

Write an exhaustive, unmocked test suite executing strictly against physical molecular fixtures:
1. **Physical Molecular Fixtures**:
   - Water Monomer ($H_2O$): $O(0, 0, 0)$, $H_1(0, 0.757, 0.586)$, $H_2(0, -0.757, 0.586)$ in $\text{\AA}$.
   - Water Dimer ($(H_2O)_2$): Authentic hydrogen-bonded dimer coordinates.
   - Ethanol ($C_2H_6O$): All-atom Cartesian coordinates.
   - Periodic Silicon or Diamond Unit Cell ($Si_8$ or $C_8$): Authentic diamond cubic lattice ($a = 5.431\text{ \AA}$ or $3.567\text{ \AA}$).

2. **Mandatory Test Cases**:
   - `test_def01_virial_stress_strain_autograd`: Verify that `TORQCalculator` calculates stress strictly via strain autograd, returning Voigt 6-vector in $\text{eV/\AA}^3$ matching numerical cell strain finite differences to $< 10^{-4}\text{ eV/\AA}^3$. Verify that no kinetic velocity terms are present.
   - `test_def02_polarizability_tensor_equivariance_and_response`: Verify that polarizability transforms as $\boldsymbol{\alpha}(R\mathbf{R}) = R \boldsymbol{\alpha}(\mathbf{R}) R^T$ with Frobenius error $< 10^{-5}\text{ \AA}^3$. Verify that the field-coupled numerical derivative $\left.\frac{\partial \mu}{\partial \mathcal{E}}\right|_{\mathcal{E}=0}$ matches the analytic polarizability head.
   - `test_def03_c2_smooth_polynomial_cutoff`: Verify that at $r = r_{\max}$, $f_{\text{cut}}(r) = 0$, $f'_{\text{cut}}(r) = 0$, and $f''_{\text{cut}}(r) = 0$ within $10^{-12}$. Verify that coordinate Hessians across the cutoff boundary do not produce NaN or step jumps.
   - `test_def04_unit_system_and_finite_diff_forces`: In `torch.float64`, perturb coordinates with $h = 10^{-4}\text{ \AA}$ and verify that analytical autograd forces match central finite differences with $\max |F^{\text{autograd}} - F^{\text{FD}}| \le 10^{-4}\text{ eV/\AA}$. Verify center-of-mass force drift $\|\sum \mathbf{F}_i\| \le 10^{-6}\text{ eV/\AA}$.
   - `test_def05_e3_rotational_and_inversion_equivariance`: Rotate $H_2O$ and ethanol with random $R \in SO(3)$ and inversion $P = -\mathbf{I}$. Verify energy invariance $|E(R\mathbf{R}) - E(\mathbf{R})| \le 10^{-5}\text{ eV}$ and force equivariance $\|\mathbf{F}(R\mathbf{R}) - R\mathbf{F}(\mathbf{R})\|_\infty \le 10^{-5}\text{ eV/\AA}$.
   - `test_def06_pydantic_v2_and_exceptions`: Verify that `TorqModelConfig` forbids extra fields and mutations. Verify that `TorqModelBackboneError` and all domain exceptions inherit from `TorqError(CoChemError)`.
   - `test_def07_dual_locked_hdf5_persistence`: Spawn 4 concurrent threads writing trajectory frames to the same `.h5` file. Verify zero data corruption and clean lock release.
   - `test_def08_provenance_and_codata_constants`: Assert CODATA 2022 conversion factors ($1\text{ Hartree} = 27.211386245988\text{ eV}$, $1\text{ e}\cdot\text{\AA} = 4.80320427\text{ Debye}$).
   - `test_def09_mendeleev_monoisotopic_masses`: Verify that $Z=6$ returns $12.000000\,\text{u}$, $Z=17$ returns $34.968853\,\text{u}$ (not $35.45\,\text{u}$), $Z=0$ returns $0.0\,\text{u}$, and returned tensors dynamically match device and dtype.

---

### ACTIONABLE IMPLEMENTATION STEPS

1. **Step 1: Exceptions & Schemas**: Create `cochem/torq/errors.py` and `cochem/torq/models/schemas.py`.
2. **Step 2: Mendeleev Monoisotopic Masses**: Create `cochem/torq/utils/mendeleev_masses.py`.
3. **Step 3: Geometry & Cutoff**: Create `cochem/torq/backbones/cutoff.py` and `cochem/torq/backbones/spherical_harmonics.py`.
4. **Step 4: Backbones & Observables**: Implement `cochem/torq/backbones/schnet.py`, `cochem/torq/backbones/equivariant_tensor.py`, and `cochem/torq/backbones/observables.py`.
5. **Step 5: ASE Calculator**: Implement `cochem/torq/calculators/ase_calc.py` with strain autograd virial stress.
6. **Step 6: Dual-Locked HDF5 Persister**: Implement `cochem/torq/storage/hdf5_persister.py`.
7. **Step 7: Verification Suite**: Implement `tests/torq/test_model_backbones.py` and run `pytest tests/torq/test_model_backbones.py -v`. Ensure 100% pass rate.
8. **Step 8: Final Report**: Report full test output and file modification ledger.
YOU ARE cochem-coder. Your task is to implement the complete, mathematically rigorous, fully remediated, and physically verified machine learning potential and tensor backbone suite specified in Software Requirements Specification (SRS) Chunk 15: `TORQ_Model_Backbones_Part_1`.

You must implement every component in strict adherence to the CoChem Zero-Mock directive v3, the Tripartite Workspace Air-Gap architecture, the 6-Tier Environment Matrix, the dynamic Mendeleev monoisotopic mass mandate, and Method Matrix v4. Absolutely no stubs, no `pass` blocks, no `NotImplementedError`, and no synthetic mock data are permitted. All implementations and test fixtures must execute physically against authentic chemical species, genuine molecular coordinates, and CODATA 2022 physical constants.

---

### MANDATORY REMEDIATION OF ALL 9 AUDIT DEFECTS

1. **DEF-01: Virial Stress via Strain Autograd [D]:**
   The ASE static potential calculator (`TORQCalculator`) must evaluate virial stress strictly via spatial strain automatic differentiation:
   $$\sigma_{\alpha\beta} = \left. \frac{1}{V} \frac{\partial E}{\partial \epsilon_{\alpha\beta}} \right|_{\boldsymbol{\epsilon}=\mathbf{0}} \quad [D]$$
   where the unit cell $\mathbf{C}$ and atomic coordinates $\mathbf{R}$ undergo symmetric virtual strain $\mathbf{R}' = \mathbf{R}(\mathbf{I} + \boldsymbol{\epsilon})$ and $\mathbf{C}' = \mathbf{C}(\mathbf{I} + \boldsymbol{\epsilon})$. Virial stress must be returned strictly in standard ASE 6-element Voigt notation:
   $$\mathbf{v}_{\text{Voigt}} = [ \sigma_{xx}, \sigma_{yy}, \sigma_{zz}, \sigma_{yz}, \sigma_{xz}, \sigma_{xy} ] \quad [M]$$
   in units of $\text{eV/\AA}^3$ [M]. The calculator MUST NOT include any particle velocities, momenta, or kinetic energy terms ($m_i v_{i\alpha} v_{i\beta}$), as kinetic stress is handled independently by molecular dynamics integrators. Pairwise virial summations ($\sum r_{ij} F_{ij}$) are strictly forbidden due to multi-body potential non-locality in MACE and NequIP.

2. **DEF-02: Rigorous Polarizability Formulation [D]:**
   Implement polarizability using a physically rigorous, differentiable formulation via:
   - **Primary Readout Head:** A direct equivariant rank-2 symmetric tensor readout head:
     $$\boldsymbol{\alpha}(\mathbf{R}) = \sum_{i=1}^N \boldsymbol{\alpha}_i = \sum_{i=1}^N \left( a_i^{(0e)} \mathbf{I}_{3 \times 3} + \mathbf{A}_i^{(2e)} \right) \quad [D]$$
     where $a_i^{(0e)}$ is an invariant scalar trace density ($\bar{\alpha}_i = \frac{1}{3}\text{Tr}(\boldsymbol{\alpha}_i)$), and $\mathbf{A}_i^{(2e)}$ is an equivariant symmetric traceless rank-2 tensor constructed from irreducible representations or dyadic vector feature products ($\sum_k w_k (\vec{\mathbf{v}}_{i,k} \otimes \vec{\mathbf{v}}_{i,k} - \frac{1}{3}\|\vec{\mathbf{v}}_{i,k}\|^2 \mathbf{I})$). The antisymmetric component ($1e$) identically vanishes for static response.
   - **Response Head:** Explicit field-coupled message passing where an external electric field $\boldsymbol{\mathcal{E}} \in \mathbb{R}^3$ is injected into edge displacements or atomic vector features, inducing a polarized dipole $\vec{\mu}(\mathbf{R}, \boldsymbol{\mathcal{E}})$, allowing polarizability to be evaluated analytically or via autograd response:
     $$\alpha_{\mu\nu} = \left. \frac{\partial \mu_\mu(\mathbf{R}, \boldsymbol{\mathcal{E}})}{\partial \mathcal{E}_\nu} \right|_{\boldsymbol{\mathcal{E}}=\mathbf{0}} \quad [D]$$

3. **DEF-03: $C^2$-Smooth Polynomial Cutoff Envelope [D]:**
   Replace cosine cutoffs across all models (SchNet, MACE, NequIP) with the $C^2$-smooth polynomial cutoff envelope function:
   $$f_{\text{cut}}(r) = \begin{cases} 1 - 10\left(\frac{r}{r_{\max}}\right)^3 + 15\left(\frac{r}{r_{\max}}\right)^4 - 6\left(\frac{r}{r_{\max}}\right)^5 & \text{for } r \le r_{\max} \\ 0 & \text{for } r > r_{\max} \end{cases} \quad [D]$$
   guaranteeing $f_{\text{cut}}(r_{\max}) = 0$, $f'_{\text{cut}}(r_{\max}) = 0$, and $f''_{\text{cut}}(r_{\max}) = 0$ to eliminate delta-function singularities in vibrational Hessians and second-order response tensors.

4. **DEF-04: Unit System Consistency & Strict Numerical Tolerances [M]:**
   Standardize strictly on CODATA 2022 / ASE base units:
   - Energy: $\text{eV}$ ($1\text{ eV} = 1.602176634 \times 10^{-19}\text{ J}$) [M]
   - Coordinates: $\text{\AA}$ ($1\text{ \AA} = 10^{-10}\text{ m}$) [M]
   - Forces: $\text{eV/\AA}$ ($1\text{ eV/\AA} \approx 1.602176634 \times 10^{-9}\text{ N}$) [M]
   - Stress: $\text{eV/\AA}^3$ ($1\text{ eV/\AA}^3 \approx 160.21766208\text{ GPa}$) [M]
   - Dipole Moment: $\text{Debye}$ ($1\text{ e}\cdot\text{\AA} = 4.80320427\text{ Debye}$) [M]
   - Polarizability: $\text{\AA}^3$ (volume polarizability $\alpha' = \alpha / 4\pi\epsilon_0$) [M]
   - Conversion Constants: $1\text{ Hartree} = 27.211386245988\text{ eV}$ [M], $1\text{ Bohr} = 0.529177210903\text{ \AA}$ [M], $1\text{ Hartree/Bohr} \approx 51.4220674763\text{ eV/\AA}$ [D].
   - Finite-difference verification must use step size $h = 10^{-4}\text{ \AA}$ in `torch.float64` with absolute tolerance $\max_{i,\alpha} |F_{i,\alpha}^{\text{autograd}} - F_{i,\alpha}^{\text{FD}}| \le 10^{-4}\text{ eV/\AA}$ [M].
   - Net force conservation (zero momentum drift): $\|\sum_i \mathbf{F}_i\|_2 \le 10^{-6}\text{ eV/\AA}$ [M].

5. **DEF-05: Self-Contained Pure-PyTorch $E(3)$ Tensor Implementation & `float64` Mandate [M], [D]:**
   Because `e3nn`, `mace`, and `nequip` are not present in the runtime environment, implement a self-contained, mathematically complete pure-PyTorch real spherical harmonics ($l \le 2$) and Cartesian equivariant tensor layer module. Provide seamless fallback routing to invariant SchNet for Tier 1 CPU. Mandate `torch.float64` for all finite-difference checks to eliminate single-precision subtractive cancellation errors.

6. **DEF-06: Pydantic v2 Configuration Schemas & Exception Hierarchy [M]:**
   All configuration and data schemas must be Pydantic v2 `BaseModel` classes configured with `model_config = ConfigDict(frozen=True, extra="forbid")`. All custom exceptions must inherit from `TorqError`, which inherits from `CoChemError`.

7. **DEF-07: HDF5 Persistence with Concurrency Dual-Locking [M]:**
   Provide thread-safe and process-safe HDF5 persistence for datasets, weights, and telemetry using dual-locking: `filelock.FileLock(path.with_suffix(".h5.lock"), timeout=30.0)` for cross-process concurrency and `threading.Lock()` for intra-process thread-safety.

8. **DEF-08: Method Matrix v4 Provenance Tags [M]:**
   Every equation, parameter, threshold, and operational constant must bear explicit provenance tags: `[M]` (Mandated/Measured), `[D]` (Derived), or `[E]` (Empirical/Calibrated).

9. **DEF-09: Dynamic Pure Monoisotopic Masses [M], [D]:**
   Query pure monoisotopic masses via `mendeleev.element(Z).isotopes` filtered by maximum abundance (`max(el.isotopes, key=lambda iso: (iso.abundance or 0.0, iso.mass_number)).mass`). Cast queried masses dynamically to a PyTorch tensor matching the active device and dtype (`torch.tensor(masses, dtype=dtype, device=device)`). Ghost atoms ($Z=0$) are assigned $0.0\,\text{u}$ mass without querying `mendeleev`.

---

### MODULE IMPLEMENTATION SPECIFICATIONS

#### 1. Domain Exceptions & Pydantic v2 Models (`cochem/torq/models/schemas.py` & `cochem/torq/errors.py`)
- **Exception Hierarchy**:
  ```python
  class CoChemError(Exception):
      """Base exception for all CoChem operations."""
      pass

  class TorqError(CoChemError):
      """Base exception for TORQ potential backbones and calculators."""
      pass

  class TorqModelBackboneError(TorqError):
      """Raised when network forward pass or tensor contraction fails."""
      pass

  class EquivarianceViolationError(TorqError):
      """Raised when E(3) rotational or inversion equivariance tolerance is violated."""
      pass

  class AutogradForceError(TorqError):
      """Raised when coordinate autograd graph construction or force derivation fails."""
      pass

  class ObservableComputationError(TorqError):
      """Raised when dipole or polarizability evaluation encounters singular values."""
      pass

  class TorqPersistenceLockError(TorqError):
      """Raised when filelock or threading lock acquisition exceeds timeout ceiling."""
      pass

  class TorqDeviceAllocationError(TorqError):
      """Raised when GPU device indexing or CUDA memory allocation fails."""
      pass

  class PeriodicBoundaryConditionError(TorqError):
      """Raised when PBC cell vectors are singular or minimum image convention fails."""
      pass
  ```
- **Pydantic v2 Models** (`model_config = ConfigDict(frozen=True, extra="forbid")`):
  - `TorqModelConfig`:
    - `model_name: Literal["schnet", "mace", "nequip", "cartesian_equivariant"] = "cartesian_equivariant"`
    - `r_max: float = Field(default=5.0, gt=0.0, le=10.0, description="Cutoff radius in Angstroms [E]")`
    - `num_radial_basis: int = Field(default=32, ge=8, le=128, description="Number of radial basis functions [E]")`
    - `num_channels: int = Field(default=64, ge=16, le=512, description="Hidden feature dimensionality [E]")`
    - `num_layers: int = Field(default=3, ge=1, le=8, description="Number of interaction layers [E]")`
    - `l_max: int = Field(default=2, ge=0, le=3, description="Maximum spherical tensor degree [M]")`
    - `charge_neutral: bool = Field(default=True, description="Enforce molecular charge neutrality [M]")`
  - `AtomicConfigurationInput`:
    - `atomic_numbers: List[int] = Field(min_length=1, description="IUPAC atomic numbers Z [M]")`
    - `coordinates: List[Tuple[float, float, float]] = Field(min_length=1, description="Cartesian coordinates in Angstroms [M]")`
    - `pbc: Tuple[bool, bool, bool] = Field(default=(False, False, False), description="Periodic boundary conditions [M]")`
    - `cell: Optional[List[List[float]]] = Field(default=None, description="3x3 unit cell vectors in Angstroms [M]")`
    - `total_charge: float = Field(default=0.0, description="Net molecular charge in elementary charge units [M]")`
  - `PotentialEnergyOutput`:
    - `energy: float = Field(description="Scalar potential energy in eV [M]")`
    - `forces: List[Tuple[float, float, float]] = Field(description="Negative energy gradients in eV/Angstrom [M]")`
    - `stress: Optional[List[float]] = Field(default=None, description="Voigt 6-vector virial stress in eV/Angstrom^3 [M]")`
  - `ObservableOutput`:
    - `dipole_vector: Tuple[float, float, float] = Field(description="Electric dipole moment vector in Debye [M]")`
    - `polarizability_tensor: List[List[float]] = Field(description="3x3 symmetric polarizability tensor in Angstrom^3 [M]")`
    - `mean_polarizability: float = Field(description="Isotropic polarizability scalar in Angstrom^3 [M]")`
    - `anisotropy: float = Field(description="Polarizability tensor anisotropy in Angstrom^3 [D]")`
  - `HDF5PersistenceConfig`:
    - `file_path: Path = Field(description="Target .h5 file path")`
    - `compression: str = Field(default="gzip", description="HDF5 compression filter")`
    - `compression_opts: int = Field(default=4, ge=0, le=9)`
    - `lock_timeout_seconds: float = Field(default=30.0, gt=0.0)`

---

#### 2. Monoisotopic Mass Engine (`cochem/torq/utils/mendeleev_masses.py`)
- Provide `get_monoisotopic_masses(atomic_numbers: List[int], device: torch.device, dtype: torch.dtype) -> torch.Tensor`:
  - Dynamically query `mendeleev.element(Z).isotopes`.
  - Filter by maximum isotopic abundance:
    ```python
    isotopes = [iso for iso in el.isotopes if iso.abundance is not None and iso.abundance > 0.0]
    if isotopes:
        mono_mass = float(max(isotopes, key=lambda iso: iso.abundance).mass)
    else:
        mono_mass = float(max(el.isotopes, key=lambda iso: iso.mass_number).mass)
    ```
  - Ghost atoms ($Z=0$): assign $0.0\,\text{u}$ without calling `mendeleev`.
  - Return `torch.tensor(mass_list, dtype=dtype, device=device)`.

---

#### 3. $C^2$-Smooth Radial Basis & Spherical Harmonics (`cochem/torq/backbones/cutoff.py` & `spherical_harmonics.py`)
- **Cutoff Envelope**:
  ```python
  def polynomial_cutoff(r: torch.Tensor, r_max: float) -> torch.Tensor:
      """
      C^2-smooth polynomial cutoff envelope [D]:
      f_cut(r) = 1 - 10(r/r_max)^3 + 15(r/r_max)^4 - 6(r/r_max)^5 for r <= r_max, else 0.
      """
      u = r / r_max
      mask = (r <= r_max).to(r.dtype)
      u_clamped = torch.clamp(u, max=1.0)
      envelope = 1.0 - 10.0 * (u_clamped ** 3) + 15.0 * (u_clamped ** 4) - 6.0 * (u_clamped ** 5)
      return envelope * mask
  ```
- **Pure-PyTorch Real Spherical Harmonics ($l \le 2$)**:
  - Implement exact analytical formulas for unit direction vectors $\hat{\mathbf{r}} = \mathbf{r} / \|\mathbf{r}\|$:
    - $Y_0^0(\hat{\mathbf{r}}) = \frac{1}{\sqrt{4\pi}}$ [D]
    - $Y_1^{-1}(\hat{\mathbf{r}}) = \sqrt{\frac{3}{4\pi}}\hat{y}$, $Y_1^0(\hat{\mathbf{r}}) = \sqrt{\frac{3}{4\pi}}\hat{z}$, $Y_1^1(\hat{\mathbf{r}}) = \sqrt{\frac{3}{4\pi}}\hat{x}$ [D]
    - $Y_2^{-2} = \sqrt{\frac{15}{4\pi}}\hat{x}\hat{y}$, $Y_2^{-1} = \sqrt{\frac{15}{4\pi}}\hat{y}\hat{z}$, $Y_2^0 = \sqrt{\frac{5}{16\pi}}(3\hat{z}^2 - 1)$, $Y_2^1 = \sqrt{\frac{15}{4\pi}}\hat{x}\hat{z}$, $Y_2^2 = \sqrt{\frac{15}{16\pi}}(\hat{x}^2 - \hat{y}^2)$ [D]
- **Radial Bessel / Gaussian Basis**:
  - Sinusoidal Bessel or Gaussian basis expanded across `num_radial_basis` bins, multiplied by `polynomial_cutoff(r, r_max)`.

---

#### 4. Neural Network Potentials (`cochem/torq/backbones/`)
- **SchNet Continuous-Filter Convolution Backbone** (`schnet.py`):
  - Invariant scalar message passing with $C^2$ polynomial cutoff.
  - Embedding layer for atomic numbers $Z \in [1, 118]$.
  - Interaction blocks: continuous-filter convolution (`CFConv`) using dense radial filter generator on interatomic distances $d_{ij}$.
  - Shifted softplus activation: $s(x) = \ln\left(\frac{1 + e^x}{2}\right)$ or SiLU.
  - Atomic energy readout head: $E_i = \text{MLP}(s_i)$, $E = \sum_i E_i$.
- **Cartesian Equivariant Tensor Backbone (MACE / NequIP)** (`equivariant_tensor.py`):
  - Self-contained pure-PyTorch equivariant message passing updating:
    - Scalar features $\mathbf{s}_i \in \mathbb{R}^{C}$ ($L=0$)
    - Vector features $\vec{\mathbf{v}}_i \in \mathbb{R}^{C \times 3}$ ($L=1$)
  - Equivariant updates:
    $$\Delta \vec{\mathbf{v}}_i = \sum_{j \in \mathcal{N}(i)} \left( W_{vv}(r_{ij}) \vec{\mathbf{v}}_j + W_{sv}(r_{ij}) \mathbf{s}_j \hat{\mathbf{r}}_{ij} \right) f_{\text{cut}}(r_{ij}) \quad [D]$$
    $$\Delta \mathbf{s}_i = \sum_{j \in \mathcal{N}(i)} \left( W_{ss}(r_{ij}) \mathbf{s}_j + W_{vs}(r_{ij}) (\vec{\mathbf{v}}_j \cdot \hat{\mathbf{r}}_{ij}) \right) f_{\text{cut}}(r_{ij}) \quad [D]$$
  - Multi-body tensor contraction:
    $$\mathbf{A}_i^{(2e)} = \sum_{c=1}^{C} w_c \left( \vec{\mathbf{v}}_{i,c} \otimes \vec{\mathbf{v}}_{i,c} - \frac{1}{3}\|\vec{\mathbf{v}}_{i,c}\|^2 \mathbf{I}_{3 \times 3} \right) \quad [D]$$
  - Energy readout: $E_i = \text{MLP}(\mathbf{s}_i)$, $E = \sum_i E_i$ [D].
  - Forces evaluated analytically via autograd: $\mathbf{F}_i = -\frac{\partial E}{\partial \mathbf{r}_i}$ [D].
  - Center-of-mass momentum projection:
    $$\mathbf{F}_i^{\text{proj}} = \mathbf{F}_i - \frac{1}{N} \sum_{j=1}^N \mathbf{F}_j \quad [D]$$
    guaranteeing $\|\sum_i \mathbf{F}_i^{\text{proj}}\| \le 10^{-6}\text{ eV/\AA}$ [M].

---

#### 5. Differentiable Observables Engine (`cochem/torq/backbones/observables.py`)
- **Electric Dipole Moment**:
  - Predicted via atomic partial charges $q_i = \text{MLP}_q(\mathbf{s}_i)$ and atomic polarization vectors $\vec{\mathbf{p}}_i = \text{Linear}(\vec{\mathbf{v}}_i)$.
  - Charge neutrality constraint:
    $$\tilde{q}_i = q_i - \frac{1}{N} \left( \sum_{j=1}^N q_j - Q_{\text{tot}} \right) \quad [D]$$
  - Dipole vector:
    $$\vec{\mu} = \left[ \sum_{i=1}^N \tilde{q}_i (\mathbf{r}_i - \mathbf{r}_{\text{COM}}) + \sum_{i=1}^N \vec{\mathbf{p}}_i \right] \times 4.80320427 \quad [\text{Debye}] \quad [M]$$
- **Polarizability Tensor**:
  - Direct equivariant rank-2 tensor readout head:
    $$\boldsymbol{\alpha} = \sum_{i=1}^N \left( a_i^{(0e)} \mathbf{I}_{3 \times 3} + \mathbf{A}_i^{(2e)} \right) \quad [\text{\AA}^3] \quad [D]$$
  - Mean isotropic polarizability: $\bar{\alpha} = \frac{1}{3} \text{Tr}(\boldsymbol{\alpha})$ [D].
  - Polarizability anisotropy:
    $$\gamma^2 = \frac{1}{2} \left[ (\alpha_{xx} - \alpha_{yy})^2 + (\alpha_{yy} - \alpha_{zz})^2 + (\alpha_{zz} - \alpha_{xx})^2 + 6(\alpha_{xy}^2 + \alpha_{yz}^2 + \alpha_{xz}^2) \right] \quad [D]$$
  - Field-coupled response verification: Provide numerical verification that coupling an external electric field $\boldsymbol{\mathcal{E}}$ verifies $\alpha_{\mu\nu} = \left. \frac{\partial \mu_\mu}{\partial \mathcal{E}_\nu} \right|_{\boldsymbol{\mathcal{E}}=\mathbf{0}}$ [D].

---

#### 6. ASE Calculator with Strain Autograd Virial Stress (`cochem/torq/calculators/ase_calc.py`)
- Implement `TORQCalculator(ase.calculators.calculator.Calculator)`:
  - Supported properties: `["energy", "forces", "stress", "dipole", "polarizability"]` [M].
  - In `calculate(atoms, properties, system_changes)`:
    - Convert `atoms.get_positions()` to `torch.tensor(..., dtype=torch.float64, requires_grad=True)`.
    - If `stress` requested and `atoms.pbc.any()`:
      - Create virtual strain tensor $\boldsymbol{\epsilon} \in \mathbb{R}^{3 \times 3}$ initialized to zeros with `requires_grad=True`.
      - Symmetrize strain: $\boldsymbol{\epsilon}_{\text{sym}} = \frac{1}{2}(\boldsymbol{\epsilon} + \boldsymbol{\epsilon}^T)$.
      - Deform positions: $\mathbf{R}' = \mathbf{R} + \mathbf{R} \boldsymbol{\epsilon}_{\text{sym}}$.
      - Deform cell: $\mathbf{C}' = \mathbf{C} + \mathbf{C} \boldsymbol{\epsilon}_{\text{sym}}$.
      - Forward pass: $E = \text{model}(\mathbf{Z}, \mathbf{R}', \mathbf{C}')$.
      - Analytical forces: $\mathbf{F} = -\nabla_{\mathbf{R}} E$ in $\text{eV/\AA}$ [M].
      - Virial stress:
        $$\boldsymbol{\sigma} = \frac{1}{V} \frac{\partial E}{\partial \boldsymbol{\epsilon}} \quad [\text{eV/\AA}^3] \quad [D]$$
      - Convert to Voigt 6-vector via ASE convention:
        `[sigma[0,0], sigma[1,1], sigma[2,2], sigma[1,2], sigma[0,2], sigma[0,1]]` [M].
      - No velocities or kinetic energy terms!

---

#### 7. Dual-Locked Thread-Safe & Process-Safe HDF5 Persistence (`cochem/torq/storage/hdf5_persister.py`)
- Implement `HDF5TorqStorage`:
  - Dual-locking mechanism:
    ```python
    self._thread_lock = threading.Lock()
    self._file_lock = filelock.FileLock(str(self.path) + ".lock", timeout=self.timeout)
    ```
  - Context manager `with self._thread_lock, self._file_lock:` for all read/write operations.
  - Datasets structured with gzip compression and chunking:
    - `/trajectories/{traj_id}/coordinates`: $(T, N, 3)$ float64
    - `/trajectories/{traj_id}/forces`: $(T, N, 3)$ float64
    - `/trajectories/{traj_id}/energy`: $(T,)$ float64
    - `/trajectories/{traj_id}/stress`: $(T, 6)$ float64
    - `/trajectories/{traj_id}/dipole`: $(T, 3)$ float64
    - `/trajectories/{traj_id}/polarizability`: $(T, 3, 3)$ float64
    - `/trajectories/{traj_id}/atomic_numbers`: $(N,)$ int32
    - `/trajectories/{traj_id}/monoisotopic_masses`: $(N,)$ float64

---

### ZERO-MOCK TEST SUITE SPECIFICATIONS (`tests/torq/test_model_backbones.py`)

Write an exhaustive, unmocked test suite executing strictly against physical molecular fixtures:
1. **Physical Molecular Fixtures**:
   - Water Monomer ($H_2O$): $O(0, 0, 0)$, $H_1(0, 0.757, 0.586)$, $H_2(0, -0.757, 0.586)$ in $\text{\AA}$.
   - Water Dimer ($(H_2O)_2$): Authentic hydrogen-bonded dimer coordinates.
   - Ethanol ($C_2H_6O$): All-atom Cartesian coordinates.
   - Periodic Silicon or Diamond Unit Cell ($Si_8$ or $C_8$): Authentic diamond cubic lattice ($a = 5.431\text{ \AA}$ or $3.567\text{ \AA}$).

2. **Mandatory Test Cases**:
   - `test_def01_virial_stress_strain_autograd`: Verify that `TORQCalculator` calculates stress strictly via strain autograd, returning Voigt 6-vector in $\text{eV/\AA}^3$ matching numerical cell strain finite differences to $< 10^{-4}\text{ eV/\AA}^3$. Verify that no kinetic velocity terms are present.
   - `test_def02_polarizability_tensor_equivariance_and_response`: Verify that polarizability transforms as $\boldsymbol{\alpha}(R\mathbf{R}) = R \boldsymbol{\alpha}(\mathbf{R}) R^T$ with Frobenius error $< 10^{-5}\text{ \AA}^3$. Verify that the field-coupled numerical derivative $\left.\frac{\partial \mu}{\partial \mathcal{E}}\right|_{\mathcal{E}=0}$ matches the analytic polarizability head.
   - `test_def03_c2_smooth_polynomial_cutoff`: Verify that at $r = r_{\max}$, $f_{\text{cut}}(r) = 0$, $f'_{\text{cut}}(r) = 0$, and $f''_{\text{cut}}(r) = 0$ within $10^{-12}$. Verify that coordinate Hessians across the cutoff boundary do not produce NaN or step jumps.
   - `test_def04_unit_system_and_finite_diff_forces`: In `torch.float64`, perturb coordinates with $h = 10^{-4}\text{ \AA}$ and verify that analytical autograd forces match central finite differences with $\max |F^{\text{autograd}} - F^{\text{FD}}| \le 10^{-4}\text{ eV/\AA}$. Verify center-of-mass force drift $\|\sum \mathbf{F}_i\| \le 10^{-6}\text{ eV/\AA}$.
   - `test_def05_e3_rotational_and_inversion_equivariance`: Rotate $H_2O$ and ethanol with random $R \in SO(3)$ and inversion $P = -\mathbf{I}$. Verify energy invariance $|E(R\mathbf{R}) - E(\mathbf{R})| \le 10^{-5}\text{ eV}$ and force equivariance $\|\mathbf{F}(R\mathbf{R}) - R\mathbf{F}(\mathbf{R})\|_\infty \le 10^{-5}\text{ eV/\AA}$.
   - `test_def06_pydantic_v2_and_exceptions`: Verify that `TorqModelConfig` forbids extra fields and mutations. Verify that `TorqModelBackboneError` and all domain exceptions inherit from `TorqError(CoChemError)`.
   - `test_def07_dual_locked_hdf5_persistence`: Spawn 4 concurrent threads writing trajectory frames to the same `.h5` file. Verify zero data corruption and clean lock release.
   - `test_def08_provenance_and_codata_constants`: Assert CODATA 2022 conversion factors ($1\text{ Hartree} = 27.211386245988\text{ eV}$, $1\text{ e}\cdot\text{\AA} = 4.80320427\text{ Debye}$).
   - `test_def09_mendeleev_monoisotopic_masses`: Verify that $Z=6$ returns $12.000000\,\text{u}$, $Z=17$ returns $34.968853\,\text{u}$ (not $35.45\,\text{u}$), $Z=0$ returns $0.0\,\text{u}$, and returned tensors dynamically match device and dtype.

---

### ACTIONABLE IMPLEMENTATION STEPS

1. **Step 1: Exceptions & Schemas**: Create `cochem/torq/errors.py` and `cochem/torq/models/schemas.py`.
2. **Step 2: Mendeleev Monoisotopic Masses**: Create `cochem/torq/utils/mendeleev_masses.py`.
3. **Step 3: Geometry & Cutoff**: Create `cochem/torq/backbones/cutoff.py` and `cochem/torq/backbones/spherical_harmonics.py`.
4. **Step 4: Backbones & Observables**: Implement `cochem/torq/backbones/schnet.py`, `cochem/torq/backbones/equivariant_tensor.py`, and `cochem/torq/backbones/observables.py`.
5. **Step 5: ASE Calculator**: Implement `cochem/torq/calculators/ase_calc.py` with strain autograd virial stress.
6. **Step 6: Dual-Locked HDF5 Persister**: Implement `cochem/torq/storage/hdf5_persister.py`.
7. **Step 7: Verification Suite**: Implement `tests/torq/test_model_backbones.py` and run `pytest tests/torq/test_model_backbones.py -v`. Ensure 100% pass rate.
8. **Step 8: Final Report**: Report full test output and file modification ledger.
Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.