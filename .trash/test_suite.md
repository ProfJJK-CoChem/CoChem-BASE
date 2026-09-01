# CoChem Test Suite Architecture

> [!NOTE]
> This document outlines the comprehensive architectural blueprint for the `test_suite` directory. It dictates the methodology, tools, and strict physical testing boundaries for validating the entire CoChem computational regime (`CoChem-BASE`, `CoChem-TOPOS`, `CoChem-TORQ`, `CoChem-SpycFit`, and `CoChem-SCRIBE`). It enforces academic integrity, ephemeral isolation, and completely forbids mocked logic.

## 1. Executive Summary & Scope

The `CoChem` test suite is designed to rigorously validate both software logic and chemical physics simulations without relying on synthetic benchmarking or simulated architectures. Because the suite relies on a complex matrix of theoretical models (from empirical `g-xTB` to explicit `F12-CCSD(T)`) and disparate hardware capabilities (CUDA vs CPU), the testing architecture is strictly physical. 

The test suite consists entirely of genuine, executable physical tests triggering real subprocess calls to ORCA, OpenMPI, and PyTorch tensors. Testing speed is maintained not by mocking, but by physically scaling down the computational system (e.g., substituting large complexes with He2 or H2O at def2-SVP limits). It ensures the shared `cochem_state.h5` database safely persists across the 10-tier wall-clock logic without memory leaks or race conditions.

## 2. Testing Framework & Tools

The backend relies on the `pytest` ecosystem to manage the immense scale of the test matrix, strictly executing isolated physical environments.

- **`pytest`**: The core execution engine. Uses fixtures to spin up sterile, ephemeral `/tmp/cochem_exec_<uuid>/` directories containing real, minimal inputs.
- **`pytest-asyncio`**: Used for testing `CoChem-BASE`'s asynchronous subprocess broker, verifying real POSIX OS-level `SIGTERM`/`SIGKILL` boundaries.
- **`pytest-cov`**: Enforces strict >95% code coverage across all core routing logic to prevent regressions in chemical boundary edge-cases.
- **Physical Test Scaling**: Replaces the use of `unittest.mock`. To test heavy I/O or GPU boundaries, tests execute minimal physical structures (e.g., hydrogen dimer) to preserve true hardware constraint validation while maintaining CI speed.

## 3. Module-Specific Testing Strategies

### 3.1 CoChem-BASE (Orchestration & Hardware)
- **Hardware Routing Tests**: Dynamically inject real physical environment variables mapping to specific OS hardware profiles to verify `BASE` correctly reroutes calculations physically.
- **BSSE & Config Compiler Tests**: Pass minimal `.xyz` geometries requiring CBS extrapolation and assert the genuinely generated `ORCA` inputs have physically suppressed the `%geom Counterpoise` blocks.
- **Time-Tier & Asynchronous Execution**: Using physical lightweight scripts that trap execution, verify the `JobManager` successfully executes POSIX `SIGTERM`/`SIGKILL` after the allotted time budget expires.
- **Pre-flight Validation**: Ensure the interactive `Start_Here.ipynb` backend successfully extracts actual `.tz` ORCA binaries and updates paths dynamically via `pathlib`.

### 3.2 CoChem-TOPOS (Topology & Conformers)
- **GOAT Loop Logic**: Execute a physical conformational search on a lightweight system (e.g., butane) and verify the Global Optimization algorithm successfully escapes local minima.
- **Element Boundary Fallbacks**: Pass a real physical transition-metal complex into TOPOS and verify it autonomously triggers the `AIMNet2` physical fallback.
- **NEB Convergence Checks**: Ensure the Nudged Elastic Band logic correctly calculates tangents and physically converges the transition state geometry on a real minimal reaction (e.g., H + H2).

### 3.3 CoChem-TORQ (PES Scans & Anharmonicity)
- **DVR Boundary Conditions**: Test the 3D Colbert-Miller Sinc-DVR grid generator by asserting the physical kinetic energy matrix elements correctly vanish at the infinite boundary edges using genuine Hamiltonian constraints.
- **VPT2 Resonance Guardrails**: Process real, pre-computed high-resonance vibrational output physical files through the TORQ parser and assert the Deperturbed VPT2 logic correctly excises mathematically explosive parameters.
- **Ab Initio Molecular Dynamics (AIMD)**: Verify that TORQ accurately extracts the dipole-autocorrelation functions from genuinely computed molecular trajectories.

### 3.4 CoChem-SpycFit (Spectroscopy & Machine Learning)
- **JAX Convolver Stability**: Pass real, physical rotational constants into the `SpycFit` JAX-compiled Hamiltonian and assert the predicted megahertz transition frequencies remain numerically stable under 64-bit precision.
- **Information-Gain Active Learning**: Test the Bayesian prior updates using physically recorded experimental microwave transitions.
- **Physical Feature Matching**: Verify the internal cross-correlation routines successfully match predicted a-type, b-type, and c-type rotational transitions to genuine experimental spectra.

### 3.5 CoChem-SCRIBE (Archiving & Formatting)
- **HDF5 Tensor Polling**: Ensure SCRIBE correctly reads `cochem_state.h5` lockfiles to extract true geometry and energy arrays physically generated by upstream processes.
- **Markdown & PDF Compilation**: Pass physically populated data structures and verify SCRIBE generates fully compliant Markdown documents incorporating LaTeX mathematical equations and Mermaid JS workflow diagrams.
- **Provenance Integrity**: Assert that SCRIBE injects the exact timestamp, physical hardware specs, and strict methodology tags extracted directly from a genuinely populated `cochem_deployment_manifest.json`.

## 4. The Zero-Mock Physical Testing Mandate

To preserve absolute academic and architectural integrity, the `test_suite` strictly prohibits the use of dummy stubs, simulated state, or `unittest.mock`.

> [!WARNING]
> **No Synthetic Benchmarking or Mocking Permitted**: All tests must execute physical OS-level IO, memory mapping, and subprocess execution.
>
> **Maintaining CI Velocity**: To keep test suites fast (< 5 minutes), developers MUST NOT use mocking. Instead, tests must scale the physical problem down to its minimal viable physics (e.g., executing PyTorch on 2-atom tensors, or running `g-xTB` single points on water molecules). This ensures all hardware boundaries, threading locks, and numeric precision constraints are natively validated without deflecting errors.

## 5. Continuous Integration Pipeline (GitHub Actions)

The suite is designed to be fully compatible with GitHub Actions via a `.github/workflows/test.yml` configuration:

```yaml
name: CoChem Suite Testing
on: [push, pull_request]

jobs:
  test-physical:
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
      - name: Run Physical Integration Tests (Zero-Mock)
        run: |
          pytest CoChem-BASE/test_suite --cov=CoChem-BASE --cov-report=xml
```

By enforcing this architecture, any future updates to `SpycFit` algorithms or `TORQ` basis sets will be physically guarded against regressions, guaranteeing true mathematical continuity.
