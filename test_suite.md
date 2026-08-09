# CoChem Test Suite Architecture

> [!NOTE]
> This document outlines the comprehensive architectural blueprint for the `test_suite` directory. It dictates the methodology, tools, and testing boundaries for validating the entire CoChem computational regime (`CoChem-BASE`, `CoChem-TOPOS`, `CoChem-TORQ`, `CoChem-SpycFit`, and `CoChem-SCRIBE`) ensuring academic integrity, deterministic hardware fallbacks, and seamless inter-module data streaming.

## 1. Executive Summary & Scope

The `CoChem` test suite is designed to rigorously validate both software logic and chemical physics simulations. Because the suite relies on a complex matrix of theoretical models (from empirical `g-xTB` to explicit `F12-CCSD(T)`) and disparate hardware capabilities (CUDA vs CPU), the testing architecture is segmented. 
The test suite spans Unit tests (mocking hardware/quantum engines) and Integration tests (triggering real subprocess calls to ORCA, OpenMPI, and PyTorch tensors). It ensures the shared `cochem_state.h5` database safely persists across the 10-tier wall-clock logic without memory leaks or race conditions.

## 2. Testing Framework & Tools

The backend relies on the `pytest` ecosystem to manage the immense scale of the test matrix.

- **`pytest`**: The core execution engine. Uses fixtures to inject mocked `HDF5` registries or dummy `ORCA` outputs into functions.
- **`pytest-asyncio`**: Critical for testing `CoChem-BASE`'s asynchronous subprocess broker, enabling tests on time-tier constraints without physically waiting 3 days for a tier timeout.
- **`pytest-cov`**: Enforces strict >95% code coverage across all core routing logic to prevent regressions in chemical boundary edge-cases.
- **`unittest.mock`**: Used extensively to patch `subprocess.run` (to mock ORCA completions) and hardware detectors like `torch.cuda.is_available()`.

## 3. Module-Specific Testing Strategies

### 3.1 CoChem-BASE (Orchestration & Hardware)
- **Hardware Routing Tests**: Mock the system environment to report "Codespaces CPU" and verify `BASE` correctly reroutes `MACE-OFF24` calculations to `g-xTB`.
- **BSSE & Config Compiler Tests**: Pass `.xyz` geometries requiring CBS extrapolation and assert the generated `ORCA` inputs have forcibly suppressed the `%geom Counterpoise` blocks.
- **Time-Tier & Asynchronous Execution**: Using `pytest-asyncio`, mock an ORCA job that hangs, and verify the `JobManager` successfully executes `SIGTERM`/`SIGKILL` after the allotted time budget expires.
- **Pre-flight Validation**: Ensure the interactive `Start_Here.ipynb` backend successfully extracts `.tz` ORCA binaries and updates paths globally.

### 3.2 CoChem-TOPOS (Topology & Conformers)
- **GOAT Loop Logic**: Inject a dummy 1D potential array and verify the Global Optimization algorithm successfully escapes shallow local minima without falling into infinite loops.
- **Element Boundary Fallbacks**: Pass a transition-metal complex into TOPOS and verify it autonomously triggers the `AIMNet2` fallback prior to initiating the PyTorch inference pass.
- **NEB Convergence Checks**: Ensure the Nudged Elastic Band logic correctly calculates tangents and converges the transition state geometry within the required force thresholds.

### 3.3 CoChem-TORQ (PES Scans & Anharmonicity)
- **DVR Boundary Conditions**: Test the 3D Colbert-Miller Sinc-DVR grid generator by asserting the kinetic energy matrix elements correctly vanish at the infinite boundary edges.
- **VPT2 Resonance Guardrails**: Inject a dummy high-resonance vibrational output into the TORQ parser and assert the Deperturbed VPT2 logic correctly excises the mathematically explosive `alpha_i` parameters.
- **Ab Initio Molecular Dynamics (AIMD)**: Verify that TORQ accurately extracts the dipole-autocorrelation functions from simulated trajectories to construct IR spectra.

### 3.4 CoChem-SpycFit (Spectroscopy & Machine Learning)
- **JAX Convolver Stability**: Pass raw rotational constants into the `SpycFit` JAX-compiled Hamiltonian and assert the predicted megahertz transition frequencies remain numerically stable under 64-bit precision.
- **Information-Gain Active Learning**: Test the Bayesian prior updates. When the simulated CP-FTMW peak is labeled, ensure the posterior probability correctly narrows the search grid for the next rotational peak.
- **Mocked Feature Matching**: Verify the internal cross-correlation routines successfully match predicted a-type, b-type, and c-type rotational transitions to synthetic experimental spectra.

### 3.5 CoChem-SCRIBE (Archiving & Formatting)
- **HDF5 Tensor Polling**: Ensure SCRIBE correctly reads `cochem_state.h5` lockfiles to extract geometry and energy arrays without triggering file access violations while TORQ is writing.
- **Markdown & PDF Compilation**: Pass mock data structures and verify SCRIBE generates fully compliant Markdown documents incorporating LaTeX mathematical equations and Mermaid JS workflow diagrams.
- **Provenance Integrity**: Assert that SCRIBE injects the exact timestamp, hardware specs, and methodology tags extracted from `cochem_deployment_manifest.json` into the final academic report.

## 4. Mocking vs. Integration (Hardware Tiers)

To prevent CI/CD timeouts, the `test_suite` is split using `@pytest.mark.unit` and `@pytest.mark.integration` decorators.

> [!WARNING]
> **Unit Tests**: Must run in `< 5 minutes`. They completely mock the physical quantum chemistry calculations, PyTorch GPU tensors, and HDF5 heavy I/O operations. They focus strictly on algorithmic routing, string parsing, and boundary conditions.
>
> **Integration Tests**: Must be executed locally on a multi-core workstation. These tests trigger actual ORCA single-point calculations, construct real PyArrow memory-mapped tensors, and test OpenMPI parallelization across physical cores.

## 5. Continuous Integration Pipeline (GitHub Actions)

The suite is designed to be fully compatible with GitHub Actions via a `.github/workflows/test.yml` configuration:

```yaml
name: CoChem Suite Testing
on: [push, pull_request]

jobs:
  test-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r CoChem-BASE/requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      - name: Run Unit Tests (Mocked Hardware)
        run: |
          pytest CoChem-BASE/test_suite -m "not integration" --cov=CoChem-BASE --cov-report=xml
```

By enforcing this architecture, any future updates to `SpycFit` algorithms or `TORQ` basis sets will be automatically guarded against regressions in `BASE` orchestration.
