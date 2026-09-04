Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_03_Ecosystem_Part_3_prompts.md.
Original prompt:
# CoChem Implementation Prompt: Ecosystem Architectural & Physical Integrity Refactor (Part 3)

**Target Repositories:** `D:\__CoChem\GitHub-Repo\CoChem-BASE` (incorporating `TOPOS` and `TORQ` submodules)  
**Target Files:**
1. `src/cochem_base/cochem_torq_watchdog.py`
2. `src/cochem_base/topology/cochem_topos_crusher.py`
3. `Libraries/cochem_torq_delta_ml.py`
4. `Libraries/cochem_torq_active_learning.py`
5. `Libraries/cochem_torq_storage.py`
6. `cli.py`
7. `ui/voila_layout/cochem_gui.py`
8. `Libraries/cochem_torq_environment.py`
9. `src/cochem/concurrency/subprocess_broker.py`
10. `src/cochem/core/hardware/topology.py`
11. `src/cochem_base/orchestrator/cochem_setup_phase_3.py`
12. `src/cochem_base/exceptions.py`

---

## Objective & Scope

Implement the refactored architectural and physical integrity fixes specified in **SRS Chunk 03 (Suggestions #21–#30)**. These changes enforce strict compliance with **Method Matrix v4**, the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC), the **Anti-Spoofing Protocol v2 (enforcing Zero-Mock, Asymmetric Verification, Hard Abort Criteria, and MAX_PIVOT_CYCLES)**, **Tripartite Air-Gap Sandboxing**, and **HPC Distributed Lock Prohibitions [M]**.

Every implementation must be concrete, fully typed (Python 3.10+), and executable without dummy mocks, synthetic stubs, or placeholder loops.

---

## Detailed Implementation Tasks

### Task 1: MPI Topology-Aware Memory Router & Operating System Floor Protection (Suggestion #21)
- **Target File:** `src/cochem_base/cochem_torq_watchdog.py`
- **Method Matrix Reference:** §11 Memory Router [M] & Stage 4.0 Watchdog Step-Back Recovery.
- **Requirements:**
  1. Refactor `dynamic_memory_backoff` to accept the parallel process count:
     ```python
     def dynamic_memory_backoff(
         req_mb: int,
         total_system_ram_mb: int,
         available_system_ram_mb: int,
         nprocs: int = 1
     ) -> int:
     ```
  2. Implement an operating system and MPI buffer reserve floor:
     $$\text{min\_os\_reserve} = \max(2048, \operatorname{int}(\text{total\_system\_ram\_mb} \times 0.15))$$
  3. Deduct `min_os_reserve` from `available_system_ram_mb` prior to per-core division:
     $$\text{usable\_ram} = \max(0, \text{available\_system\_ram\_mb} - \text{min\_os\_reserve})$$
     $$\text{new\_maxcore} = \max(256, \operatorname{int}(\text{usable\_ram} // \max(1, nprocs)))$$
  4. Guard against underflow: If `usable_ram < 256 * nprocs`, clamp `new_maxcore` to 256 MB and log a structured warning indicating that integral evaluation must transition to direct SCF (disk-based) to avoid an OS OOM kill.

---

### Task 2: Physical Fallback Cascade & CIP Stereochemical Invariant Verification (Suggestion #22)
- **Target File:** `src/cochem_base/topology/cochem_topos_crusher.py`
- **Method Matrix Reference:** Stage 2.4 TOPOS Conformer Generation [M] & Anti-Spoofing Protocol.
- **Requirements:**
  1. In `GOATConformerEngine._goat_single_worker`, completely purge unparameterized ASE `LennardJones()`.
  2. Implement an authentic physical force-field / potential fallback cascade when CREST is not utilized:
     - **Tier 1:** GFN-FF evaluation via `xtb --gfnff` (or `xtb-python` if bound).
     - **Tier 2:** RDKit MMFF94 (with fallback to UFF if MMFF atom types are unparameterized).
     - **Tier 3:** TORQ MACE-MP0 neural network potential (if PyTorch and MACE are available).
  3. Implement post-thermalization stereochemical integrity verification:
     - Use RDKit `Chem.FindMolChiralCenters(mol, includeUnassigned=True)` to record chiral center configurations $(R/S)$ and double-bond stereochemistry $(E/Z)$ before Langevin dynamics.
     - Re-evaluate chiral centers on the thermalized geometry.
     - If any chiral center inverts, racemizes, or if covalent bonds break, discard the candidate conformer immediately and log the event.

---

### Task 3: In-Memory `xtb-python` API Priority, Radical Multiplicity & Electron Parity Validation (Suggestion #23)
- **Target File:** `Libraries/cochem_torq_delta_ml.py`
- **Method Matrix Reference:** Delta-Learning Architecture [M] & Open-Shell Radical Standards.
- **Requirements:**
  1. Refactor `GFN2xTBEngine`:
     - Prioritize direct in-memory evaluation via the `xtb-python` C-API bindings (`from xtb.interface import Calculator, Param`).
     - Provide a robust subprocess fallback to standalone CLI `xtb` only if `xtb-python` is uninstalled or raises an interface exception.
  2. Update `calculate` signature:
     ```python
     def calculate(
         self,
         atoms: Any,
         charge: int = 0,
         multiplicity: int = 1,
         **kwargs: Any
     ) -> Dict[str, Any]:
     ```
  3. Validate physical electron-spin parity before computation:
     - Compute total nuclear charge $Z_{\text{tot}} = \sum Z_i$.
     - Compute total electron count $N_e = Z_{\text{tot}} - \text{charge}$.
     - Determine unpaired electron count $2S = \text{multiplicity} - 1$.
     - Enforce the parity condition:
       $$(N_e - 2S) \equiv 0 \pmod 2 \quad \text{and} \quad 2S \ge 0 \quad \text{and} \quad N_e > 0$$
     - Raise a typed `ValueError` if spin multiplicity does not physically match the system's electron count.
  4. Correctly map spin state to xTB parameters:
     - Pass `uhf = multiplicity - 1` ($2S$) and `charge` into the `xtb-python` calculator or CLI flags (`--chrg {charge} --uhf {uhf}`). Never map multiplicity $M$ directly to `--uhf`.

---

### Task 4: Active Learning Hardware Triage Gate & Thread-Safe HDF5 SWMR Persistence (Suggestion #24)
- **Target Files:** `Libraries/cochem_torq_active_learning.py` and `Libraries/cochem_torq_storage.py`
- **Method Matrix Reference:** Investigator-in-the-Loop Decision Gates, §12 Thread-Safe HDF5 Storage [M], and HPC Distributed Lock Prohibition [M].
- **Requirements:**
  1. Refactor `route_qm_tier` in `Libraries/cochem_torq_active_learning.py`:
     - Ingest a `HardwareTopology` object.
     - Inspect available local computational engines (e.g., ORCA, CFOUR) and the allocated compute budget before assigning high-force-uncertainty candidates to high-cost composite tiers (`T3O-1h`, `T3O-12h`).
     - If a required engine is absent or projected wall-clock time exceeds budget, trigger an interactive decision gate or gracefully degrade to the highest supported tier (e.g., `B3LYP-D4/def2-TZVP`).
  2. Refactor HDF5 dataset persistence in `Libraries/cochem_torq_storage.py`:
     - Open HDF5 files with SWMR support: `h5py.File(filename, 'a', libver='latest')`.
     - **Preallocation Invariant:** All extensible datasets (`coordinates`, `energies`, `forces`, `uncertainties`) must have their maximum chunk boundaries preallocated before enabling SWMR mode (`f.swmr_mode = True`).
     - Wrap all multi-process write operations in cross-platform `filelock.FileLock` (using local lock paths). Strictly avoid POSIX `fcntl` on network mounts.

---

### Task 5: Setup Graceful Degradation & Voila GUI `DEGRADED_OPERATIONAL` State (Suggestion #25)
- **Target Files:** `cli.py` and `ui/voila_layout/cochem_gui.py`
- **Method Matrix Reference:** Investigator-in-the-Loop Pedagogical Interface & SRS Document 2 Part 1 (§1.6).
- **Requirements:**
  1. In `cli.py` (`action_setup`):
     - Decouple hard execution gates. Phases 1 & 2 (Core Python environment and essential scientific dependencies) remain mandatory hard gates.
     - Phases 3+ (External quantum chemistry engines: ORCA, CFOUR, PyMOL, CREST) are classified as optional solver tracks.
     - If Phases 1 & 2 succeed but optional third-party engines fail, exit setup with status `DEGRADED_OPERATIONAL` and record missing capabilities in `cochem_system_config.json`. Do not halt the entire installation.
  2. In `ui/voila_layout/cochem_gui.py`:
     - In `_detect_environment`, recognize `DEGRADED_OPERATIONAL` status as functional.
     - Keep the No-Code Matrix (`btn_matrix`) and Data Inspector (`btn_inspector`) enabled.
     - Dynamically inspect available engines and disable only the dropdown items corresponding to uninstalled engines, attaching explicit tooltips explaining how to provision them.

---

### Task 6: Cross-Platform Local Scratch Resolution & Local Locking (Suggestion #26)
- **Target Files:** `Libraries/cochem_torq_environment.py` and `src/cochem/concurrency/`
- **Method Matrix Reference:** Method Matrix v4 HPC Distributed Lock Prohibition [M] and 6-Tier Environment Matrix.
- **Requirements:**
  1. In `Libraries/cochem_torq_environment.py`, refactor `resolve_hpc_safe_scratch`:
     - **Windows (`win32`):** Check `os.environ.get("LOCALAPPDATA")` and `os.environ.get("TEMP")` before falling back to `Path.home() / ".cochem"`. Strictly prevent defaulting to network-hosted SMB user roaming profiles (`C:\Users\<username>`).
     - **Linux / macOS / HPC:** Check `$SLURM_TMPDIR`, `$TMPDIR`, `/tmp`, and `/var/tmp` before `$HOME` to ensure fast local NVMe/SSD execution and prevent NFS lock stalls.
  2. Enforce `filelock.FileLock` anchored inside the resolved local scratch directory.
  3. Implement context-managed scratch directory scaffolding (`EphemeralScratchSession`) that registers automated post-execution purge hooks to prevent disk bloat.

---

### Task 7: Multi-GPU Division-by-Zero Guard & Tripartite Air-Gap Execution Sandboxing (Suggestion #27)
- **Target Files:** `src/cochem/concurrency/subprocess_broker.py` and `src/cochem/core/hardware/topology.py`
- **Method Matrix Reference:** §8A Hardware Topology, Zero-CUDA-Locking Directive [M], and Tripartite Air-Gap Sandboxing.
- **Requirements:**
  1. In `src/cochem/core/hardware/topology.py` and `subprocess_broker.py`:
     - Guard GPU allocation logic against CPU-only environments:
       ```python
       available_gpus = topology.get_available_gpus()
       num_gpus = len(available_gpus)
       if num_gpus > 0:
           assigned = self.current_params.get("assigned_gpu", available_gpus[worker_index % num_gpus])
           env["CUDA_VISIBLE_DEVICES"] = str(assigned)
       else:
           env["CUDA_VISIBLE_DEVICES"] = ""
       ```
     - Eliminate unlinked `pass` statements; scrub ambient `CUDA_VISIBLE_DEVICES` before assigning specific worker stripes.
  2. Implement Tripartite Air-Gap execution sandboxing:
     - Subprocesses must NEVER execute inside the source repository root.
     - Spawn all calculations inside isolated ephemeral sandboxes: `Path(scratch_dir) / f"cochem_exec_{uuid.uuid4().hex}"`.
     - Capture subprocess stdout/stderr using bounded 10 MB ring buffers (`collections.deque(maxlen=10485760)` or chunked streaming) to prevent unbounded memory growth during high-throughput runs.
     - Provide automatic teardown of the ephemeral execution directory upon job completion or termination.

---

### Task 8: CREST Toolchain Co-Existence & OpenMP Virtual Memory Safeguards (Suggestion #28)
- **Target File:** `src/cochem_base/topology/cochem_topos_crusher.py`
- **Method Matrix Reference:** Method Matrix v4 Conformer Generation (CREST/ORCA GOAT combination approach) [M].
- **Requirements:**
  1. In `CRESTConformerEngine.execute_secondary_search`:
     - Audit mutual toolchain co-existence: Verify that both `crest` and `xtb` executables exist on the system `$PATH` using `shutil.which`.
     - If either binary is missing, raise a typed `EcosystemDependencyError` stating that CREST relies intrinsically on xTB.
  2. Inject mandatory OpenMP stack and thread limits into the subprocess execution environment:
     ```python
     env = os.environ.copy()
     env["OMP_STACKSIZE"] = "1G"
     env["OMP_NUM_THREADS"] = str(budgeted_threads)
     env["MKL_NUM_THREADS"] = str(budgeted_threads)
     ```
  3. Propagate the hardware topology thread budget into `CRESTConformerEngine` rather than relying on unconstrained ambient system threads.

---

### Task 9: Cross-Platform Dynamic Linkage Auditor for Phase 3 Binary Setup (Suggestion #29)
- **Target File:** `src/cochem_base/orchestrator/cochem_setup_phase_3.py`
- **Method Matrix Reference:** Stage 0.0 Multi-Track Quantum Engine Discovery & Zero-Mock Authenticity.
- **Requirements:**
  1. Extend `discover_binary_path` with an active Dynamic Linkage Auditor:
     ```python
     def audit_binary_linkage(binary_path: Path) -> Tuple[bool, List[str]]:
     ```
  2. Implement platform-specific shared library dependency inspection:
     - **Linux:** Execute `ldd <binary_path>` and parse output for missing shared objects (`"not found"`).
     - **macOS:** Execute `otool -L <binary_path>` and verify the existence of dynamic libraries.
     - **Windows:** Check binary imports using `dumpbin /dependents <binary_path>` or inspect PE headers via `pefile` if available.
  3. If unresolved library dependencies are found in sibling directories (e.g., `../lib` relative to the binary or an adjacent OpenMPI installation), automatically append those paths to the Golden Master Registry environment overrides (`LD_LIBRARY_PATH`, `DYLD_LIBRARY_PATH`, or `PATH`).

---

### Task 10: Dual-Audience Pedagogical & Telemetry Exception Architecture (Suggestion #30)
- **Target Files:** `src/cochem_base/exceptions.py` and `ui/voila_layout/cochem_gui.py`
- **Method Matrix Reference:** Investigator-in-the-Loop Pedagogical Scaffolding & Guided Decision Gates.
- **Requirements:**
  1. Extend `CoChemBaseException` in `src/cochem_base/exceptions.py` with bifurcated presentation interfaces:
     - `to_pedagogical_guidance() -> str`: Translates low-level quantum chemical failure signatures (e.g., SCF divergence, severe atomic overlap / clash, negative vibrational frequencies on a transition state, basis set linear dependency, OOM threshold) into clear, didactic chemical intuition with actionable remediation advice for undergraduate students.
     - `to_diagnostic_telemetry() -> Dict[str, Any]`: Formats full system telemetry (stack trace, exit codes, process memory footprint, convergence histories, active hardware profile, and timestamp) into a structured dictionary for PIs, auditors, and automated bug reports.
  2. In `ui/voila_layout/cochem_gui.py`:
     - Update the calculation error display widget to prominently render `to_pedagogical_guidance()` in the primary notification view.
     - Provide an expandable accordion or secondary tab displaying `to_diagnostic_telemetry()` for advanced inspection.

---

## Coding Directives & Constraints

1. **Anti-Spoofing Protocol v2 (enforcing Zero-Mock, Asymmetric Verification, Hard Abort Criteria, and MAX_PIVOT_CYCLES):**
   - Strictly NO mock classes, fake loops, synthetic strings, or placeholder `pass` / `...` statements.
   - All environment checks, binary inspections, and physical calculations must execute authentically against real system state and genuine molecular graphs.
2. **Dynamic Atomic Mass Retrieval (Mendeleev Mandate):**
   - If atomic or isotopic masses are referenced in conformer filtering, masses MUST be retrieved dynamically using `mendeleev` (`from mendeleev import element`). Hardcoding atomic masses is strictly forbidden.
3. **Cross-Platform Portability:**
   - All filesystem paths must use `pathlib.Path` or OS-agnostic path resolvers. Do NOT hardcode POSIX `/tmp` or Windows `C:\` roots.
4. **JAX 64-Bit Initialization:**
   - If JAX is imported in any touched module, ensure `jax.config.update("jax_enable_x64", True)` is executed immediately upon startup.
5. **Provenance Tagging:**
   - Maintain explicit provenance tags (`[M]`, `[D]`, `[E]`) in module docstrings and thermochemical calculation outputs.
# CoChem Implementation Prompt: Ecosystem Architectural & Physical Integrity Refactor (Part 3)

**Target Repositories:** `D:\__CoChem\GitHub-Repo\CoChem-BASE` (incorporating `TOPOS` and `TORQ` submodules)  
**Target Files:**
1. `src/cochem_base/cochem_torq_watchdog.py`
2. `src/cochem_base/topology/cochem_topos_crusher.py`
3. `Libraries/cochem_torq_delta_ml.py`
4. `Libraries/cochem_torq_active_learning.py`
5. `Libraries/cochem_torq_storage.py`
6. `cli.py`
7. `ui/voila_layout/cochem_gui.py`
8. `Libraries/cochem_torq_environment.py`
9. `src/cochem/concurrency/subprocess_broker.py`
10. `src/cochem/core/hardware/topology.py`
11. `src/cochem_base/orchestrator/cochem_setup_phase_3.py`
12. `src/cochem_base/exceptions.py`

---

## Objective & Scope

Implement the refactored architectural and physical integrity fixes specified in **SRS Chunk 03 (Suggestions #21–#30)**. These changes enforce strict compliance with **Method Matrix v4**, the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC), the **Anti-Spoofing Protocol v2 (enforcing Zero-Mock, Asymmetric Verification, Hard Abort Criteria, and MAX_PIVOT_CYCLES)**, **Tripartite Air-Gap Sandboxing**, and **HPC Distributed Lock Prohibitions [M]**.

Every implementation must be concrete, fully typed (Python 3.10+), and executable without dummy mocks, synthetic stubs, or placeholder loops.

---

## Detailed Implementation Tasks

### Task 1: MPI Topology-Aware Memory Router & Operating System Floor Protection (Suggestion #21)
- **Target File:** `src/cochem_base/cochem_torq_watchdog.py`
- **Method Matrix Reference:** §11 Memory Router [M] & Stage 4.0 Watchdog Step-Back Recovery.
- **Requirements:**
  1. Refactor `dynamic_memory_backoff` to accept the parallel process count:
     ```python
     def dynamic_memory_backoff(
         req_mb: int,
         total_system_ram_mb: int,
         available_system_ram_mb: int,
         nprocs: int = 1
     ) -> int:
     ```
  2. Implement an operating system and MPI buffer reserve floor:
     $$\text{min\_os\_reserve} = \max(2048, \operatorname{int}(\text{total\_system\_ram\_mb} \times 0.15))$$
  3. Deduct `min_os_reserve` from `available_system_ram_mb` prior to per-core division:
     $$\text{usable\_ram} = \max(0, \text{available\_system\_ram\_mb} - \text{min\_os\_reserve})$$
     $$\text{new\_maxcore} = \max(256, \operatorname{int}(\text{usable\_ram} // \max(1, nprocs)))$$
  4. Guard against underflow: If `usable_ram < 256 * nprocs`, clamp `new_maxcore` to 256 MB and log a structured warning indicating that integral evaluation must transition to direct SCF (disk-based) to avoid an OS OOM kill.

---

### Task 2: Physical Fallback Cascade & CIP Stereochemical Invariant Verification (Suggestion #22)
- **Target File:** `src/cochem_base/topology/cochem_topos_crusher.py`
- **Method Matrix Reference:** Stage 2.4 TOPOS Conformer Generation [M] & Anti-Spoofing Protocol.
- **Requirements:**
  1. In `GOATConformerEngine._goat_single_worker`, completely purge unparameterized ASE `LennardJones()`.
  2. Implement an authentic physical force-field / potential fallback cascade when CREST is not utilized:
     - **Tier 1:** GFN-FF evaluation via `xtb --gfnff` (or `xtb-python` if bound).
     - **Tier 2:** RDKit MMFF94 (with fallback to UFF if MMFF atom types are unparameterized).
     - **Tier 3:** TORQ MACE-MP0 neural network potential (if PyTorch and MACE are available).
  3. Implement post-thermalization stereochemical integrity verification:
     - Use RDKit `Chem.FindMolChiralCenters(mol, includeUnassigned=True)` to record chiral center configurations $(R/S)$ and double-bond stereochemistry $(E/Z)$ before Langevin dynamics.
     - Re-evaluate chiral centers on the thermalized geometry.
     - If any chiral center inverts, racemizes, or if covalent bonds break, discard the candidate conformer immediately and log the event.

---

### Task 3: In-Memory `xtb-python` API Priority, Radical Multiplicity & Electron Parity Validation (Suggestion #23)
- **Target File:** `Libraries/cochem_torq_delta_ml.py`
- **Method Matrix Reference:** Delta-Learning Architecture [M] & Open-Shell Radical Standards.
- **Requirements:**
  1. Refactor `GFN2xTBEngine`:
     - Prioritize direct in-memory evaluation via the `xtb-python` C-API bindings (`from xtb.interface import Calculator, Param`).
     - Provide a robust subprocess fallback to standalone CLI `xtb` only if `xtb-python` is uninstalled or raises an interface exception.
  2. Update `calculate` signature:
     ```python
     def calculate(
         self,
         atoms: Any,
         charge: int = 0,
         multiplicity: int = 1,
         **kwargs: Any
     ) -> Dict[str, Any]:
     ```
  3. Validate physical electron-spin parity before computation:
     - Compute total nuclear charge $Z_{\text{tot}} = \sum Z_i$.
     - Compute total electron count $N_e = Z_{\text{tot}} - \text{charge}$.
     - Determine unpaired electron count $2S = \text{multiplicity} - 1$.
     - Enforce the parity condition:
       $$(N_e - 2S) \equiv 0 \pmod 2 \quad \text{and} \quad 2S \ge 0 \quad \text{and} \quad N_e > 0$$
     - Raise a typed `ValueError` if spin multiplicity does not physically match the system's electron count.
  4. Correctly map spin state to xTB parameters:
     - Pass `uhf = multiplicity - 1` ($2S$) and `charge` into the `xtb-python` calculator or CLI flags (`--chrg {charge} --uhf {uhf}`). Never map multiplicity $M$ directly to `--uhf`.

---

### Task 4: Active Learning Hardware Triage Gate & Thread-Safe HDF5 SWMR Persistence (Suggestion #24)
- **Target Files:** `Libraries/cochem_torq_active_learning.py` and `Libraries/cochem_torq_storage.py`
- **Method Matrix Reference:** Investigator-in-the-Loop Decision Gates, §12 Thread-Safe HDF5 Storage [M], and HPC Distributed Lock Prohibition [M].
- **Requirements:**
  1. Refactor `route_qm_tier` in `Libraries/cochem_torq_active_learning.py`:
     - Ingest a `HardwareTopology` object.
     - Inspect available local computational engines (e.g., ORCA, CFOUR) and the allocated compute budget before assigning high-force-uncertainty candidates to high-cost composite tiers (`T3O-1h`, `T3O-12h`).
     - If a required engine is absent or projected wall-clock time exceeds budget, trigger an interactive decision gate or gracefully degrade to the highest supported tier (e.g., `B3LYP-D4/def2-TZVP`).
  2. Refactor HDF5 dataset persistence in `Libraries/cochem_torq_storage.py`:
     - Open HDF5 files with SWMR support: `h5py.File(filename, 'a', libver='latest')`.
     - **Preallocation Invariant:** All extensible datasets (`coordinates`, `energies`, `forces`, `uncertainties`) must have their maximum chunk boundaries preallocated before enabling SWMR mode (`f.swmr_mode = True`).
     - Wrap all multi-process write operations in cross-platform `filelock.FileLock` (using local lock paths). Strictly avoid POSIX `fcntl` on network mounts.

---

### Task 5: Setup Graceful Degradation & Voila GUI `DEGRADED_OPERATIONAL` State (Suggestion #25)
- **Target Files:** `cli.py` and `ui/voila_layout/cochem_gui.py`
- **Method Matrix Reference:** Investigator-in-the-Loop Pedagogical Interface & SRS Document 2 Part 1 (§1.6).
- **Requirements:**
  1. In `cli.py` (`action_setup`):
     - Decouple hard execution gates. Phases 1 & 2 (Core Python environment and essential scientific dependencies) remain mandatory hard gates.
     - Phases 3+ (External quantum chemistry engines: ORCA, CFOUR, PyMOL, CREST) are classified as optional solver tracks.
     - If Phases 1 & 2 succeed but optional third-party engines fail, exit setup with status `DEGRADED_OPERATIONAL` and record missing capabilities in `cochem_system_config.json`. Do not halt the entire installation.
  2. In `ui/voila_layout/cochem_gui.py`:
     - In `_detect_environment`, recognize `DEGRADED_OPERATIONAL` status as functional.
     - Keep the No-Code Matrix (`btn_matrix`) and Data Inspector (`btn_inspector`) enabled.
     - Dynamically inspect available engines and disable only the dropdown items corresponding to uninstalled engines, attaching explicit tooltips explaining how to provision them.

---

### Task 6: Cross-Platform Local Scratch Resolution & Local Locking (Suggestion #26)
- **Target Files:** `Libraries/cochem_torq_environment.py` and `src/cochem/concurrency/`
- **Method Matrix Reference:** Method Matrix v4 HPC Distributed Lock Prohibition [M] and 6-Tier Environment Matrix.
- **Requirements:**
  1. In `Libraries/cochem_torq_environment.py`, refactor `resolve_hpc_safe_scratch`:
     - **Windows (`win32`):** Check `os.environ.get("LOCALAPPDATA")` and `os.environ.get("TEMP")` before falling back to `Path.home() / ".cochem"`. Strictly prevent defaulting to network-hosted SMB user roaming profiles (`C:\Users\<username>`).
     - **Linux / macOS / HPC:** Check `$SLURM_TMPDIR`, `$TMPDIR`, `/tmp`, and `/var/tmp` before `$HOME` to ensure fast local NVMe/SSD execution and prevent NFS lock stalls.
  2. Enforce `filelock.FileLock` anchored inside the resolved local scratch directory.
  3. Implement context-managed scratch directory scaffolding (`EphemeralScratchSession`) that registers automated post-execution purge hooks to prevent disk bloat.

---

### Task 7: Multi-GPU Division-by-Zero Guard & Tripartite Air-Gap Execution Sandboxing (Suggestion #27)
- **Target Files:** `src/cochem/concurrency/subprocess_broker.py` and `src/cochem/core/hardware/topology.py`
- **Method Matrix Reference:** §8A Hardware Topology, Zero-CUDA-Locking Directive [M], and Tripartite Air-Gap Sandboxing.
- **Requirements:**
  1. In `src/cochem/core/hardware/topology.py` and `subprocess_broker.py`:
     - Guard GPU allocation logic against CPU-only environments:
       ```python
       available_gpus = topology.get_available_gpus()
       num_gpus = len(available_gpus)
       if num_gpus > 0:
           assigned = self.current_params.get("assigned_gpu", available_gpus[worker_index % num_gpus])
           env["CUDA_VISIBLE_DEVICES"] = str(assigned)
       else:
           env["CUDA_VISIBLE_DEVICES"] = ""
       ```
     - Eliminate unlinked `pass` statements; scrub ambient `CUDA_VISIBLE_DEVICES` before assigning specific worker stripes.
  2. Implement Tripartite Air-Gap execution sandboxing:
     - Subprocesses must NEVER execute inside the source repository root.
     - Spawn all calculations inside isolated ephemeral sandboxes: `Path(scratch_dir) / f"cochem_exec_{uuid.uuid4().hex}"`.
     - Capture subprocess stdout/stderr using bounded 10 MB ring buffers (`collections.deque(maxlen=10485760)` or chunked streaming) to prevent unbounded memory growth during high-throughput runs.
     - Provide automatic teardown of the ephemeral execution directory upon job completion or termination.

---

### Task 8: CREST Toolchain Co-Existence & OpenMP Virtual Memory Safeguards (Suggestion #28)
- **Target File:** `src/cochem_base/topology/cochem_topos_crusher.py`
- **Method Matrix Reference:** Method Matrix v4 Conformer Generation (CREST/ORCA GOAT combination approach) [M].
- **Requirements:**
  1. In `CRESTConformerEngine.execute_secondary_search`:
     - Audit mutual toolchain co-existence: Verify that both `crest` and `xtb` executables exist on the system `$PATH` using `shutil.which`.
     - If either binary is missing, raise a typed `EcosystemDependencyError` stating that CREST relies intrinsically on xTB.
  2. Inject mandatory OpenMP stack and thread limits into the subprocess execution environment:
     ```python
     env = os.environ.copy()
     env["OMP_STACKSIZE"] = "1G"
     env["OMP_NUM_THREADS"] = str(budgeted_threads)
     env["MKL_NUM_THREADS"] = str(budgeted_threads)
     ```
  3. Propagate the hardware topology thread budget into `CRESTConformerEngine` rather than relying on unconstrained ambient system threads.

---

### Task 9: Cross-Platform Dynamic Linkage Auditor for Phase 3 Binary Setup (Suggestion #29)
- **Target File:** `src/cochem_base/orchestrator/cochem_setup_phase_3.py`
- **Method Matrix Reference:** Stage 0.0 Multi-Track Quantum Engine Discovery & Zero-Mock Authenticity.
- **Requirements:**
  1. Extend `discover_binary_path` with an active Dynamic Linkage Auditor:
     ```python
     def audit_binary_linkage(binary_path: Path) -> Tuple[bool, List[str]]:
     ```
  2. Implement platform-specific shared library dependency inspection:
     - **Linux:** Execute `ldd <binary_path>` and parse output for missing shared objects (`"not found"`).
     - **macOS:** Execute `otool -L <binary_path>` and verify the existence of dynamic libraries.
     - **Windows:** Check binary imports using `dumpbin /dependents <binary_path>` or inspect PE headers via `pefile` if available.
  3. If unresolved library dependencies are found in sibling directories (e.g., `../lib` relative to the binary or an adjacent OpenMPI installation), automatically append those paths to the Golden Master Registry environment overrides (`LD_LIBRARY_PATH`, `DYLD_LIBRARY_PATH`, or `PATH`).

---

### Task 10: Dual-Audience Pedagogical & Telemetry Exception Architecture (Suggestion #30)
- **Target Files:** `src/cochem_base/exceptions.py` and `ui/voila_layout/cochem_gui.py`
- **Method Matrix Reference:** Investigator-in-the-Loop Pedagogical Scaffolding & Guided Decision Gates.
- **Requirements:**
  1. Extend `CoChemBaseException` in `src/cochem_base/exceptions.py` with bifurcated presentation interfaces:
     - `to_pedagogical_guidance() -> str`: Translates low-level quantum chemical failure signatures (e.g., SCF divergence, severe atomic overlap / clash, negative vibrational frequencies on a transition state, basis set linear dependency, OOM threshold) into clear, didactic chemical intuition with actionable remediation advice for undergraduate students.
     - `to_diagnostic_telemetry() -> Dict[str, Any]`: Formats full system telemetry (stack trace, exit codes, process memory footprint, convergence histories, active hardware profile, and timestamp) into a structured dictionary for PIs, auditors, and automated bug reports.
  2. In `ui/voila_layout/cochem_gui.py`:
     - Update the calculation error display widget to prominently render `to_pedagogical_guidance()` in the primary notification view.
     - Provide an expandable accordion or secondary tab displaying `to_diagnostic_telemetry()` for advanced inspection.

---

## Coding Directives & Constraints

1. **Anti-Spoofing Protocol v2 (enforcing Zero-Mock, Asymmetric Verification, Hard Abort Criteria, and MAX_PIVOT_CYCLES):**
   - Strictly NO mock classes, fake loops, synthetic strings, or placeholder `pass` / `...` statements.
   - All environment checks, binary inspections, and physical calculations must execute authentically against real system state and genuine molecular graphs.
2. **Dynamic Atomic Mass Retrieval (Mendeleev Mandate):**
   - If atomic or isotopic masses are referenced in conformer filtering, masses MUST be retrieved dynamically using `mendeleev` (`from mendeleev import element`). Hardcoding atomic masses is strictly forbidden.
3. **Cross-Platform Portability:**
   - All filesystem paths must use `pathlib.Path` or OS-agnostic path resolvers. Do NOT hardcode POSIX `/tmp` or Windows `C:\` roots.
4. **JAX 64-Bit Initialization:**
   - If JAX is imported in any touched module, ensure `jax.config.update("jax_enable_x64", True)` is executed immediately upon startup.
5. **Provenance Tagging:**
   - Maintain explicit provenance tags (`[M]`, `[D]`, `[E]`) in module docstrings and thermochemical calculation outputs.
Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.