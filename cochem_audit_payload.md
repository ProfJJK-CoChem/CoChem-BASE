Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_10_Ecosystem_Part_10_prompts.md.
Original prompt:
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 10, Suggestions #91–#101)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring, platform compatibility remediation, and physical integrity enforcement specified in SRS Chunk 10 (Suggestions #91–#101).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§1.2, §3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds, §8A Contention Budgeting & Scout-and-Anchor Core Partitioning, §8A.4 NVIDIA MPS Mandatory Small-Job Concurrency, §8B.3 Methodological Bans, §8C SWMR Database Concurrency Protocols, §9B.1–§9B.3 Conformer Exploration Protocol, §11 Memory Router Governance, §20 Non-Covalent Complex Benchmarks), Tripartite Filesystem Air-Gap Architecture ($T_{\text{src}}$, $T_{\text{scr}}$, $T_{\text{store}}$), Anti-Spoofing Protocol v2 (Zero-Mock, Dynamic Mendeleev Retrieval, Dynamic Physical Constants, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, dummy loops, synthetic fallback coordinates, or fabricated energies.
  - Strict prohibition on `Calc_Hess true` for all geometry optimizations (enforce `InHess XTB2` or `Lindh`).
  - Strict prohibition on additive diffuse corrections and small-system ONIOM partitioning.
  - All atomic masses, isotopic masses, and covalent/vdW radii must be dynamically retrieved via `from mendeleev import element` (never hardcode physical constants).
  - All physical unit conversions must be queried dynamically via `scipy.constants.physical_constants` or `ase.units`.
  - Cross-platform IPC and persistent storage locking strictly via `filelock.FileLock` (POSIX `fcntl.flock` is strictly banned on network filesystems, container mounts, and Windows filesystems).
  - Strict Tripartite Workspace Air-Gap compliance: immutable source tree $T_{\text{src}}$ (`$COCH_SRC`), ephemeral scratch $T_{\text{scr}}$ (`$COCH_SCRATCH`), and persistent store $T_{\text{store}}$ (`$COCH_STORE_DIR`).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Non-Covalent Hydrogen & Halogen Bond Pre-Flight Geometry Validation (Suggestion #91)
**Target Module:** `CoChem-BASE` (`cochem/topos/geometry_validation.py`, lines 253–254)

### Detailed Requirements:
1. **Dynamic van der Waals Radii Retrieval:**
   - Eliminate hardcoded van der Waals radius lookup tables. Dynamically fetch van der Waals radii using `mendeleev`:
     ```python
     from mendeleev import element

     def get_vdw_radius(symbol: str) -> float:
         el = element(symbol)
         rad = el.vdw_radius
         if rad is None:
             rad = el.vdw_radius_alvarez
         return float(rad) / 100.0 if rad > 10.0 else float(rad)
     ```
2. **Polar Interaction Topology & Electrostatic Contraction Relaxation:**
   - In `cochem/topos/geometry_validation.py`, inspect connectivity prior to clash evaluation. Identify polar donor-bound hydrogens: an H atom bonded covalently ($d \le 1.20 \times (r_{\text{cov, H}} + r_{\text{cov, donor}})$) to an electronegative donor atom (O, N, F, Cl).
   - If an evaluated non-bonded pair comprises a polar donor-bound hydrogen and an electronegative acceptor atom (O, N, F, Cl), or represents a halogen-bonding pair (Lewis-acidic Cl, Br, I interacting with Lewis-basic O, N, S):
     - Relax the clash threshold multiplier from $0.65$ to $0.50$ [D]:
       $$\text{threshold}_{\text{clash}} = 0.50 \times (r_{\text{vdw}, i} + r_{\text{vdw}, j})$$
   - For an $\text{O–H}\cdots\text{O}$ hydrogen bond, the relaxed threshold evaluates to $0.50 \times (1.20 + 1.52)\text{ \AA} = 1.36\text{ \AA}$ [D], permitting authentic equilibrium hydrogen-bonded distances (1.65–1.75 Å [M]) to pass pre-flight qualification while preventing nuclear collapse ($< 1.35\text{ \AA}$).
3. **General Interatomic Clash Preservation:**
   - Retain the default threshold ($0.65 \times (r_{\text{vdw}, i} + r_{\text{vdw}, j})$) for all isotropic non-polar contacts (e.g., $\text{C}\cdots\text{C}$, $\text{C}\cdots\text{H}$).

---

## Deliverable 2: Complete Rotational Tensor & Permutation-Invariant Conformer Deduplication (Suggestion #92)
**Target Module:** `CoChem-TORQ` (`cochem_torq_goat.py`, lines 765–786, 1076–1082)

### Detailed Requirements:
1. **Full Rotational Tensor ($A, B, C$) & Inertial Defect Evaluation:**
   - In `cochem_torq_goat.py` (lines 1076–1082), deprecate conformer comparison relying solely on the scalar intermediate rotational constant $B$ (`rotational_constants_mhz[1]`).
   - Implement Method Matrix v4 §9B.1–§9B.3 screening over all three principal rotational constants:
     $$\Delta_{\text{rel}}(A) = \frac{|A_1 - A_2|}{\max(A_1, A_2)}, \quad \Delta_{\text{rel}}(B) = \frac{|B_1 - B_2|}{\max(B_1, B_2)}, \quad \Delta_{\text{rel}}(C) = \frac{|C_1 - C_2|}{\max(C_1, C_2)}$$
   - Two conformers are tagged as rotational candidates for equivalence only if $\max(\Delta_{\text{rel}}(A), \Delta_{\text{rel}}(B), \Delta_{\text{rel}}(C)) < 0.002$ ($0.2\%$).
   - Concurrently verify the inertial defect $\Delta = I_c - I_a - I_b$ [D] and planar moments ($P_a, P_b, P_c$) to discriminate planar from non-planar conformers and prevent false merging of asymmetric tops.
2. **Permutation-Invariant Hungarian RMSD Matching:**
   - In `compute_rmsd` (lines 765–786), eliminate rigid index-by-index Kabsch alignment that treats permutationally equivalent atom orderings (e.g., CREST vs. ORCA GOAT output) as distinct structures.
   - Implement permutation-invariant alignment:
     - Partition the molecular structure into identical element equivalence classes.
     - For each identical nucleus subset, determine optimal Cartesian correspondence using the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) after initial principal-axis or Kabsch rotational pre-alignment.
   - Deduplicate candidate structures if the permutation-minimized RMSD $\le 0.15\text{ \AA}$ [M].

---

## Deliverable 3: Cross-Platform SWMR HDF5 Concurrency, Lease Management & In-Process Thread Locking (Suggestion #93)
**Target Module:** `CoChem-BASE` (`src/cochem_base/cochem_h5_healer.py`, lines 93–135)

### Detailed Requirements:
1. **Cross-Platform `filelock` IPC & Lease Metadata:**
   - Completely remove POSIX-specific `fcntl.flock` calls.
   - Protect all persistent HDF5 operations using `filelock.FileLock` located dynamically via:
     ```python
     lock_dir = Path(os.environ.get("COCH_STORE_DIR", Path.home() / ".cochem" / "locks"))
     lock_dir.mkdir(parents=True, exist_ok=True)
     file_lock = filelock.FileLock(str(lock_dir / f"{Path(db_path).name}.lock"))
     ```
   - Store companion JSON lease metadata (`f"{db_path}.lease.json"`) containing:
     ```json
     {
       "pid": 12345,
       "hostname": "worker-node-01",
       "timestamp": 1725451200.0
     }
     ```
2. **Host-Identity Aware Zombie & Crash Eviction:**
   - In `detect_zombie_pids`, read the companion lease.
   - Verify `lease["hostname"] == platform.node()`. If hostnames match, check process existence locally via `psutil.pid_exists(lease["pid"])`. If the PID is dead, evict the stale lock immediately.
   - If `lease["hostname"] != platform.node()` (remote compute node across NFS/Lustre), enforce a 60.0-second lease expiration timeout: if `time.monotonic() - lease["timestamp"] > 60.0`, log a `[SWMR-LEASE-EVICTION]` warning and break the expired lock.
3. **In-Process Mutex Serialization (`threading.RLock`):**
   - Encapsulate all database handle open, dataset append, resize, and flush calls with an internal `threading.RLock` to eliminate race conditions between concurrent intra-process threads.
4. **Safe SWMR Initialization Protocol:**
   - Ensure all dataset chunks, filters (shuffle=True, Fletcher32=True), and root group headers are fully pre-allocated and flushed to disk *before* activating Single-Writer/Multiple-Reader mode (`h5.swmr_mode = True`).

---

## Deliverable 4: Robust Banner-Based Binary Interrogation for Heterogeneous Quantum Engines (Suggestion #94)
**Target Module:** `CoChem-BASE` (`src/cochem_base/orchestrator/cochem_setup_phase_3.py`, lines 512–570)

### Detailed Requirements:
1. **Elimination of `orca --version` Execution:**
   - In `interrogate_binary_version`, remove `subprocess.run([orca_bin, "--version"], check=True)`.
2. **Input-Deck Agnostic Header Interrogation:**
   - Execute the quantum engine binary with `check=False`, `timeout=10.0`, and `stdin=subprocess.DEVNULL`:
     ```python
     result = subprocess.run(
         [str(bin_path)],
         stdin=subprocess.DEVNULL,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         text=True,
         check=False,
         timeout=10.0,
     )
     combined_banner = f"{result.stdout}\n{result.stderr}"
     ```
3. **Regex Extraction for Multi-Generation Engines:**
   - Extract versions across ORCA releases (v4, v5, v6) using robust banner matching:
     ```python
     # Matches: "Program Version 6.0.0", "* O   R   C   A * Version 5.0.4", "ORCA-Version 5.0.3"
     match = re.search(r'(?:Program\s+Version|Version|ORCA-Version)\s+([4-6]\.\d+\.\d+)', combined_banner, re.IGNORECASE)
     if match:
         version_str = match.group(1)
     ```
   - Ensure support extends to CFOUR, xTB, and CREST banner headers across all 6 environment tiers without raising `CalledProcessError`.

---

## Deliverable 5: Tripartite Workspace Air-Gap Architecture & Sanitized Remediation Loops (Suggestion #95)
**Target Module:** `CoChem-BASE` (`src/cochem/concurrency/subprocess_broker.py`, lines 254–385)

### Detailed Requirements:
1. **Tripartite Workspace Air-Gap Enforcement:**
   - Standardize all execution paths into three strictly segregated zones:
     - **Ring 1 / Source Tree ($T_{\text{src}}$):** `$COCH_SRC` (immutable read-only codebase; zero runtime artifacts allowed).
     - **Ring 2 / Ephemeral Scratch ($T_{\text{scr}}$):** `$COCH_SCRATCH` (dynamically resolved to `pathlib.Path(os.environ.get("COCH_SCRATCH", Path.home() / ".cochem" / "scratch"))`). Transient calculations, wavefunctions, and raw stdout/stderr streams must execute exclusively here.
     - **Ring 3 / Persistent Store ($T_{\text{store}}$):** `$COCH_STORE_DIR` (dynamically resolved via `Path(os.environ.get("COCH_STORE_DIR", Path.home() / ".cochem" / "store"))`). Final converged geometries, normalized JSON/HDF5 data, and signed logs.
2. **Remediation Scratch Sanitization:**
   - In `SubprocessBroker.execute_with_remediation`, before executing a remediation retry step (e.g., transitioning model Hessian `Lindh` $\rightarrow$ `InHess XTB2`, or escalating grids `defgrid1` $\rightarrow$ `defgrid2` $\rightarrow$ `defgrid3`), execute active scratch purging:
     - Remove stale binary locks, dirty `.gbw`, `.tmp*`, `.prop`, and `.densities` files from the working scratch directory.
     - Provide an explicit retention bypass only when an orbital guess (`MOREAD`, `*.gbw`) is deliberately verified and designated for state reuse under Method Matrix v4 §8B.
3. **Offline Environment Safety:**
   - Validate that execution runs cleanly under `COCHEM_OFFLINE=1` without attempting network calls or leaking temporary files into $T_{\text{src}}$.

---

## Deliverable 6: PEP 425 ABI & Platform Architecture Verification for Offline Wheel Caching (Suggestion #96)
**Target Module:** `CoChem-BASE` (`src/cochem_base/orchestrator/dependency_manager.py`, lines 302–376)

### Detailed Requirements:
1. **PEP 425 Tag Inspection:**
   - In `scan_for_local_wheel_fallback`, import `packaging.tags.sys_tags`.
   - Parse each candidate `.whl` filename into its standard tuple: `(distribution, version, build, python_tag, abi_tag, platform_tag)` using `packaging.utils.parse_wheel_filename`.
2. **Host Compatibility Filtering:**
   - Query the host system's supported tags:
     ```python
     from packaging.tags import sys_tags
     from packaging.utils import parse_wheel_filename

     supported_tags = set(sys_tags())
     ```
   - For each candidate wheel in the offline cache directory (resolved dynamically via `Path.home() / ".cochem" / "wheels"` or `$COCHEM_ARTIFACTS_DIR`), verify whether any tag yielded by the wheel matches `supported_tags`.
   - Discard incompatible wheels (e.g., reject `manylinux` wheels on macOS OrbStack or Windows WSL native, reject `x86_64` on ARM64/Apple Silicon) before invoking `pip install --no-index`.

---

## Deliverable 7: Heterogeneous Apple Silicon Performance Core Discovery & Contention Partitioning (Suggestion #97)
**Target Module:** `CoChem-BASE` (`src/cochem/core/hardware/topology.py`, lines 42–126)

### Detailed Requirements:
1. **Darwin-Native `sysctl` Heterogeneous Core Probing:**
   - In `discover_p_e_cores`, eliminate the fallthrough on `sys.platform == "darwin"` that assigns uniform cores (`physical_total, 0`).
   - Execute Darwin-native `sysctl` queries:
     ```python
     if sys.platform == "darwin":
         p_cores = int(subprocess.check_output(["sysctl", "-n", "hw.perflevel0.physicalcpu"]).decode().strip())
         e_cores = int(subprocess.check_output(["sysctl", "-n", "hw.perflevel1.physicalcpu"]).decode().strip())
     ```
   - Fall back to parsing `sysctl -n machdep.cpu.brand_string` or total physical cores if performance levels are unavailable.
2. **Scout-and-Anchor Core Partitioning:**
   - Under Method Matrix v4 §8A Contention Budgeting:
     - Reserve Efficiency (E) cores exclusively for background orchestration, IO polling, and SWMR serialization.
     - Pin compute-heavy electronic structure jobs (ORCA, CFOUR, xTB) exclusively to Performance (P) cores.
3. **Containerized CPU Quota Compliance:**
   - On Linux/Debian/Codespaces/CI, inspect cgroup CFS quotas (`/sys/fs/cgroup/cpu.max` or `/sys/fs/cgroup/cpu/cpu.cfs_quota_us`) and clamp detected cores to the integer floor of the assigned quota.

---

## Deliverable 8: Win32 Multi-Group Processor Affinity & High-Core Pinning (Suggestion #98)
**Target Module:** `CoChem-BASE` (`src/cochem/core/hardware/topology.py`, lines 275–290)

### Detailed Requirements:
1. **Processor Group Detection:**
   - On Windows (`sys.platform == "win32"`), support systems with $> 64$ logical processors (dual-socket AMD EPYC / Threadripper, Intel Xeon) where standard 64-bit affinity masks overflow.
   - Use `ctypes` to query `GetActiveProcessorGroupCount()` and `GetActiveProcessorCount(group_number)`.
2. **`SetThreadGroupAffinity` Win32 Binding:**
   - Define the Win32 `GROUP_AFFINITY` structure:
     ```python
     import ctypes
     from ctypes import wintypes

     class GROUP_AFFINITY(ctypes.Structure):
         _fields_ = [
             ("Mask", ctypes.c_size_t),
             ("Group", wintypes.WORD),
             ("Reserved", wintypes.WORD * 3)
         ]
     ```
   - Map target `core_index` to the corresponding `group = core_index // 64` and `relative_core = core_index % 64`.
   - Apply binding via `kernel32.SetThreadGroupAffinity(current_thread_handle, ctypes.byref(group_affinity), None)`.
3. **POSIX Complement:**
   - Retain and verify standard `os.sched_setaffinity(0, {core_index})` on Linux and HPC clusters.

---

## Deliverable 9: Dynamic Sandbox Engine Liveness Probing & Automated Downgrade Ladder (Suggestion #99)
**Target Module:** `CoChem-BASE` (`src/cochem_mobile/core/sandbox_broker.py`, lines 69–94, 141–220)

### Detailed Requirements:
1. **Active Daemon Liveness Probing:**
   - In `detect_available_engines`, do not rely solely on binary presence (`shutil.which("docker") is not None`).
   - Probe daemon connectivity with an explicit 1.5 s timeout:
     ```python
     def is_docker_active() -> bool:
         if not shutil.which("docker"):
             return False
         try:
             res = subprocess.run(
                 ["docker", "info", "--format", "{{.ServerVersion}}"],
                 stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL,
                 timeout=1.5,
                 check=True
             )
             return True
         except (subprocess.SubprocessError, OSError):
             return False
     ```
2. **Automated Downgrade Fallback Ladder:**
   - In `SandboxBroker.execute`, if the primary container runtime fails or daemon connectivity times out, automatically cascade down the execution ladder:
     $$\text{Docker} \longrightarrow \text{Podman} \longrightarrow \text{Apptainer} \longrightarrow \text{Subprocess Broker (Local Quarantine)}$$
   - Log the active fallback engine with provenance tag `[D]`. Ensure non-root sandbox execution policies are enforced.

---

## Deliverable 10: Multi-Rank MPI Memory Governance & Watchdog Backoff Accounting (Suggestion #100)
**Target Modules:** `CoChem-BASE` / `CoChem-TORQ` (`src/cochem_base/cochem_torq_watchdog.py`, lines 173–235)

### Detailed Requirements:
1. **Per-Rank MPI `%maxcore` Accounting:**
   - In `dynamic_memory_backoff`, update signature to accept `nprocs: int = 1`.
   - Recognize that in ORCA, `%maxcore` specifies memory *per individual MPI core*; aggregate system memory demand is:
     $$\text{Memory}_{\text{total}} = N_{\text{procs}} \times \%\text{maxcore}$$
2. **Cgroup & Physical RAM Detection:**
   - Query available memory, clamping to container cgroup limits (`/sys/fs/cgroup/memory.max`) if lower than host physical RAM (`psutil.virtual_memory().available`).
3. **Bounded Memory Calculation:**
   - Scale `%maxcore` to guarantee total allocation does not exceed $85\%$ of available RAM:
     ```python
     safe_budget_mb = available_system_ram_mb * 0.85
     new_maxcore = max(256, int(safe_budget_mb // max(1, nprocs)))
     ```
   - If `new_maxcore < 512`, emit a directive recommendation to switch integral calculation from in-memory storage to direct disk calculation (`! NoRifDirect` or `! Direct`).

---

## Deliverable 11: Non-Initializing NVML Telemetry, MPS Socket Isolation & GPU Concurrency (Suggestion #101)
**Target Module:** `CoChem-BASE` (`src/cochem/runners/cuda_budget.py`)

### Detailed Requirements:
1. **Non-Initializing Telemetry Polling:**
   - Mandate that background GPU utilization telemetry queries NVML handles without creating active CUDA driver contexts:
     - Use `pynvml.nvmlDeviceGetHandleByIndex()` and `pynvml.nvmlDeviceGetMemoryInfo()`.
     - Strictly avoid calling initializing framework functions (e.g., `torch.cuda.memory_allocated()` or `cupy.cuda.Device(0)`) during background telemetry polling.
2. **Per-Worker NVIDIA MPS Socket Isolation:**
   - Under Method Matrix v4 §8A.4, establish per-worker MPS session directories:
     ```python
     mps_root = Path(os.environ.get("COCH_SCRATCH", Path.home() / ".cochem" / "scratch")) / "mps"
     mps_pipe_dir = mps_root / f"pipe_{worker_id}"
     mps_pipe_dir.mkdir(parents=True, exist_ok=True)
     env["CUDA_MPS_PIPE_DIRECTORY"] = str(mps_pipe_dir)
     ```
3. **Context Allocation Throttling & Automated CPU Fallback:**
   - Track concurrent active GPU worker contexts.
   - If active concurrent client contexts exceed 4 on consumer GPUs (RTX 3090/4090 without MIG support) [D], or if running in non-GPU environments (Codespaces, GitHub Actions CI, macOS without CUDA), automatically route jobs to CPU-optimized binaries (xTB, ORCA CPU).

---

## Zero-Mock Verification & Test Plan
Create or update comprehensive integration tests in `tests/` verifying all 11 deliverables against real data and physical bounds without synthetic mocks:

1. `tests/topos/test_geometry_validation_hbond.py`:
   - Construct an authentic water dimer ($(\text{H}_2\text{O})_2$) with $d(\text{O}\cdots\text{H}) = 1.72\text{ \AA}$ and formamidinium formate.
   - Assert validation succeeds without raising `GeometricPlausibilityError` or flagging steric clashes.
   - Construct a collapsed dimer ($d(\text{O}\cdots\text{H}) = 1.10\text{ \AA}$) and verify it is correctly rejected as a clash.
2. `tests/torq/test_rotational_tensor_deduplication.py`:
   - Provide two asymmetric top conformers with identical scalar $B$ but distinct $A$ and $C$ constants ($\Delta A / A = 1.2\%$). Assert deduplication preserves both.
   - Provide two identical conformers with scrambled atom orderings. Assert Hungarian permutation-invariant RMSD identifies equivalence ($\le 0.15\text{ \AA}$) and deduplicates them.
3. `tests/base/test_h5_healer_concurrency.py`:
   - Launch multiple concurrent processes performing SWMR writes to a test HDF5 database protected by `filelock` and `threading.RLock`.
   - Assert zero database corruption, zero unhandled lock contention exceptions, and verify proper eviction of simulated stale locks based on hostname/PID inspection.
4. `tests/base/test_binary_interrogation_orca.py`:
   - Invoke `interrogate_binary_version` against ORCA binary banners (simulated via stdout banner streams).
   - Assert that versions (4.x, 5.x, 6.x) are correctly parsed without invoking `--version` or throwing `CalledProcessError`.
5. `tests/concurrency/test_tripartite_subprocess_broker.py`:
   - Run a simulated multi-step parameter remediation loop.
   - Assert that $T_{\text{src}}$ remains untouched and read-only, that intermediate dirty files (`.tmp`, `.gbw`) in $T_{\text{scr}}$ are purged before retry steps, and that final outputs are cleanly promoted to $T_{\text{store}}$.
6. `tests/base/test_dependency_wheel_tags.py`:
   - Feed mock directory lists of wheels with varying PEP 425 tags (`manylinux`, `win_amd64`, `macosx_arm64`).
   - Assert that `scan_for_local_wheel_fallback` selects exclusively wheels matching `packaging.tags.sys_tags()`.
7. `tests/core/test_topology_apple_silicon.py`:
   - Test `discover_p_e_cores` on macOS systems (or verify Darwin sysctl parser branch).
   - Assert P-core and E-core separation matches hardware topology, and verify cgroup quota clamping on Linux.
8. `tests/core/test_topology_windows_groups.py`:
   - Test processor affinity assignment for `core_index >= 64`.
   - Verify `GROUP_AFFINITY` struct generation and `SetThreadGroupAffinity` execution paths on Windows.
9. `tests/sandbox/test_sandbox_broker_fallback.py`:
   - Simulate an inactive Docker daemon (CLI present, daemon socket unresponsive).
   - Assert that `SandboxBroker` times out within 1.5 s and cascades through Podman/Apptainer to local quarantine without halting.
10. `tests/torq/test_torq_watchdog_mpi_memory.py`:
    - Pass an ORCA configuration with 8 MPI ranks on a 16 GB memory-constrained host.
    - Assert that `dynamic_memory_backoff` divides the budget by `nprocs` such that $N_{\text{procs}} \times \%\text{maxcore} \le 85\%$ of available RAM.
11. `tests/runners/test_cuda_budget_mps.py`:
    - Verify non-initializing NVML polling executes without creating primary CUDA contexts.
    - Assert per-worker `CUDA_MPS_PIPE_DIRECTORY` environment variable isolation and verify automated CPU fallback when context limit is exceeded.

Execute all changes cleanly, adhere strictly to Python typing standards, dynamic OS-agnostic pathing, and verify that the ecosystem passes linting (`ruff check`) and formatting. Proceed with implementation.
# CoChem-Coder Implementation Prompt: Ecosystem Architectural & Physical Integrity (Chunk 10, Suggestions #91–#101)

## Context & Execution Mandate
You are `cochem-coder`, the autonomous implementation agent in the CoChem Swarm. You are tasked with executing the architectural refactoring, platform compatibility remediation, and physical integrity enforcement specified in SRS Chunk 10 (Suggestions #91–#101).

- **Target Repositories:**
  - `CoChem-BASE` (`D:\__CoChem\GitHub-Repo\CoChem-BASE`)
  - `CoChem-TOPOS` (`D:\__CoChem\GitHub-Repo\CoChem-TOPOS`)
  - `CoChem-TORQ` (`D:\__CoChem\GitHub-Repo\CoChem-TORQ`)
- **Authoritative Specifications:** Method Matrix v4 (§1.2, §3.0 $B_e$ vs $B_0$ Distinction, §3.3 Mandatory Spend Priority, §4.4 Tight Convergence Thresholds, §8A Contention Budgeting & Scout-and-Anchor Core Partitioning, §8A.4 NVIDIA MPS Mandatory Small-Job Concurrency, §8B.3 Methodological Bans, §8C SWMR Database Concurrency Protocols, §9B.1–§9B.3 Conformer Exploration Protocol, §11 Memory Router Governance, §20 Non-Covalent Complex Benchmarks), Tripartite Filesystem Air-Gap Architecture ($T_{\text{src}}$, $T_{\text{scr}}$, $T_{\text{store}}$), Anti-Spoofing Protocol v2 (Zero-Mock, Dynamic Mendeleev Retrieval, Dynamic Physical Constants, Hard Abort Criteria), and the 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions CI, HPC Clusters).
- **Absolute Constraints:**
  - Zero mock implementations, dummy loops, synthetic fallback coordinates, or fabricated energies.
  - Strict prohibition on `Calc_Hess true` for all geometry optimizations (enforce `InHess XTB2` or `Lindh`).
  - Strict prohibition on additive diffuse corrections and small-system ONIOM partitioning.
  - All atomic masses, isotopic masses, and covalent/vdW radii must be dynamically retrieved via `from mendeleev import element` (never hardcode physical constants).
  - All physical unit conversions must be queried dynamically via `scipy.constants.physical_constants` or `ase.units`.
  - Cross-platform IPC and persistent storage locking strictly via `filelock.FileLock` (POSIX `fcntl.flock` is strictly banned on network filesystems, container mounts, and Windows filesystems).
  - Strict Tripartite Workspace Air-Gap compliance: immutable source tree $T_{\text{src}}$ (`$COCH_SRC`), ephemeral scratch $T_{\text{scr}}$ (`$COCH_SCRATCH`), and persistent store $T_{\text{store}}$ (`$COCH_STORE_DIR`).
  - All JAX/DVR numerical simulation scripts must initialize `jax.config.update("jax_enable_x64", True)` on line 1.
  - Strict typing (Python 3.10+ `typing`), dynamic OS-agnostic pathing via `pathlib.Path`, and zero unhandled exceptions.

---

## Deliverable 1: Non-Covalent Hydrogen & Halogen Bond Pre-Flight Geometry Validation (Suggestion #91)
**Target Module:** `CoChem-BASE` (`cochem/topos/geometry_validation.py`, lines 253–254)

### Detailed Requirements:
1. **Dynamic van der Waals Radii Retrieval:**
   - Eliminate hardcoded van der Waals radius lookup tables. Dynamically fetch van der Waals radii using `mendeleev`:
     ```python
     from mendeleev import element

     def get_vdw_radius(symbol: str) -> float:
         el = element(symbol)
         rad = el.vdw_radius
         if rad is None:
             rad = el.vdw_radius_alvarez
         return float(rad) / 100.0 if rad > 10.0 else float(rad)
     ```
2. **Polar Interaction Topology & Electrostatic Contraction Relaxation:**
   - In `cochem/topos/geometry_validation.py`, inspect connectivity prior to clash evaluation. Identify polar donor-bound hydrogens: an H atom bonded covalently ($d \le 1.20 \times (r_{\text{cov, H}} + r_{\text{cov, donor}})$) to an electronegative donor atom (O, N, F, Cl).
   - If an evaluated non-bonded pair comprises a polar donor-bound hydrogen and an electronegative acceptor atom (O, N, F, Cl), or represents a halogen-bonding pair (Lewis-acidic Cl, Br, I interacting with Lewis-basic O, N, S):
     - Relax the clash threshold multiplier from $0.65$ to $0.50$ [D]:
       $$\text{threshold}_{\text{clash}} = 0.50 \times (r_{\text{vdw}, i} + r_{\text{vdw}, j})$$
   - For an $\text{O–H}\cdots\text{O}$ hydrogen bond, the relaxed threshold evaluates to $0.50 \times (1.20 + 1.52)\text{ \AA} = 1.36\text{ \AA}$ [D], permitting authentic equilibrium hydrogen-bonded distances (1.65–1.75 Å [M]) to pass pre-flight qualification while preventing nuclear collapse ($< 1.35\text{ \AA}$).
3. **General Interatomic Clash Preservation:**
   - Retain the default threshold ($0.65 \times (r_{\text{vdw}, i} + r_{\text{vdw}, j})$) for all isotropic non-polar contacts (e.g., $\text{C}\cdots\text{C}$, $\text{C}\cdots\text{H}$).

---

## Deliverable 2: Complete Rotational Tensor & Permutation-Invariant Conformer Deduplication (Suggestion #92)
**Target Module:** `CoChem-TORQ` (`cochem_torq_goat.py`, lines 765–786, 1076–1082)

### Detailed Requirements:
1. **Full Rotational Tensor ($A, B, C$) & Inertial Defect Evaluation:**
   - In `cochem_torq_goat.py` (lines 1076–1082), deprecate conformer comparison relying solely on the scalar intermediate rotational constant $B$ (`rotational_constants_mhz[1]`).
   - Implement Method Matrix v4 §9B.1–§9B.3 screening over all three principal rotational constants:
     $$\Delta_{\text{rel}}(A) = \frac{|A_1 - A_2|}{\max(A_1, A_2)}, \quad \Delta_{\text{rel}}(B) = \frac{|B_1 - B_2|}{\max(B_1, B_2)}, \quad \Delta_{\text{rel}}(C) = \frac{|C_1 - C_2|}{\max(C_1, C_2)}$$
   - Two conformers are tagged as rotational candidates for equivalence only if $\max(\Delta_{\text{rel}}(A), \Delta_{\text{rel}}(B), \Delta_{\text{rel}}(C)) < 0.002$ ($0.2\%$).
   - Concurrently verify the inertial defect $\Delta = I_c - I_a - I_b$ [D] and planar moments ($P_a, P_b, P_c$) to discriminate planar from non-planar conformers and prevent false merging of asymmetric tops.
2. **Permutation-Invariant Hungarian RMSD Matching:**
   - In `compute_rmsd` (lines 765–786), eliminate rigid index-by-index Kabsch alignment that treats permutationally equivalent atom orderings (e.g., CREST vs. ORCA GOAT output) as distinct structures.
   - Implement permutation-invariant alignment:
     - Partition the molecular structure into identical element equivalence classes.
     - For each identical nucleus subset, determine optimal Cartesian correspondence using the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) after initial principal-axis or Kabsch rotational pre-alignment.
   - Deduplicate candidate structures if the permutation-minimized RMSD $\le 0.15\text{ \AA}$ [M].

---

## Deliverable 3: Cross-Platform SWMR HDF5 Concurrency, Lease Management & In-Process Thread Locking (Suggestion #93)
**Target Module:** `CoChem-BASE` (`src/cochem_base/cochem_h5_healer.py`, lines 93–135)

### Detailed Requirements:
1. **Cross-Platform `filelock` IPC & Lease Metadata:**
   - Completely remove POSIX-specific `fcntl.flock` calls.
   - Protect all persistent HDF5 operations using `filelock.FileLock` located dynamically via:
     ```python
     lock_dir = Path(os.environ.get("COCH_STORE_DIR", Path.home() / ".cochem" / "locks"))
     lock_dir.mkdir(parents=True, exist_ok=True)
     file_lock = filelock.FileLock(str(lock_dir / f"{Path(db_path).name}.lock"))
     ```
   - Store companion JSON lease metadata (`f"{db_path}.lease.json"`) containing:
     ```json
     {
       "pid": 12345,
       "hostname": "worker-node-01",
       "timestamp": 1725451200.0
     }
     ```
2. **Host-Identity Aware Zombie & Crash Eviction:**
   - In `detect_zombie_pids`, read the companion lease.
   - Verify `lease["hostname"] == platform.node()`. If hostnames match, check process existence locally via `psutil.pid_exists(lease["pid"])`. If the PID is dead, evict the stale lock immediately.
   - If `lease["hostname"] != platform.node()` (remote compute node across NFS/Lustre), enforce a 60.0-second lease expiration timeout: if `time.monotonic() - lease["timestamp"] > 60.0`, log a `[SWMR-LEASE-EVICTION]` warning and break the expired lock.
3. **In-Process Mutex Serialization (`threading.RLock`):**
   - Encapsulate all database handle open, dataset append, resize, and flush calls with an internal `threading.RLock` to eliminate race conditions between concurrent intra-process threads.
4. **Safe SWMR Initialization Protocol:**
   - Ensure all dataset chunks, filters (shuffle=True, Fletcher32=True), and root group headers are fully pre-allocated and flushed to disk *before* activating Single-Writer/Multiple-Reader mode (`h5.swmr_mode = True`).

---

## Deliverable 4: Robust Banner-Based Binary Interrogation for Heterogeneous Quantum Engines (Suggestion #94)
**Target Module:** `CoChem-BASE` (`src/cochem_base/orchestrator/cochem_setup_phase_3.py`, lines 512–570)

### Detailed Requirements:
1. **Elimination of `orca --version` Execution:**
   - In `interrogate_binary_version`, remove `subprocess.run([orca_bin, "--version"], check=True)`.
2. **Input-Deck Agnostic Header Interrogation:**
   - Execute the quantum engine binary with `check=False`, `timeout=10.0`, and `stdin=subprocess.DEVNULL`:
     ```python
     result = subprocess.run(
         [str(bin_path)],
         stdin=subprocess.DEVNULL,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         text=True,
         check=False,
         timeout=10.0,
     )
     combined_banner = f"{result.stdout}\n{result.stderr}"
     ```
3. **Regex Extraction for Multi-Generation Engines:**
   - Extract versions across ORCA releases (v4, v5, v6) using robust banner matching:
     ```python
     # Matches: "Program Version 6.0.0", "* O   R   C   A * Version 5.0.4", "ORCA-Version 5.0.3"
     match = re.search(r'(?:Program\s+Version|Version|ORCA-Version)\s+([4-6]\.\d+\.\d+)', combined_banner, re.IGNORECASE)
     if match:
         version_str = match.group(1)
     ```
   - Ensure support extends to CFOUR, xTB, and CREST banner headers across all 6 environment tiers without raising `CalledProcessError`.

---

## Deliverable 5: Tripartite Workspace Air-Gap Architecture & Sanitized Remediation Loops (Suggestion #95)
**Target Module:** `CoChem-BASE` (`src/cochem/concurrency/subprocess_broker.py`, lines 254–385)

### Detailed Requirements:
1. **Tripartite Workspace Air-Gap Enforcement:**
   - Standardize all execution paths into three strictly segregated zones:
     - **Ring 1 / Source Tree ($T_{\text{src}}$):** `$COCH_SRC` (immutable read-only codebase; zero runtime artifacts allowed).
     - **Ring 2 / Ephemeral Scratch ($T_{\text{scr}}$):** `$COCH_SCRATCH` (dynamically resolved to `pathlib.Path(os.environ.get("COCH_SCRATCH", Path.home() / ".cochem" / "scratch"))`). Transient calculations, wavefunctions, and raw stdout/stderr streams must execute exclusively here.
     - **Ring 3 / Persistent Store ($T_{\text{store}}$):** `$COCH_STORE_DIR` (dynamically resolved via `Path(os.environ.get("COCH_STORE_DIR", Path.home() / ".cochem" / "store"))`). Final converged geometries, normalized JSON/HDF5 data, and signed logs.
2. **Remediation Scratch Sanitization:**
   - In `SubprocessBroker.execute_with_remediation`, before executing a remediation retry step (e.g., transitioning model Hessian `Lindh` $\rightarrow$ `InHess XTB2`, or escalating grids `defgrid1` $\rightarrow$ `defgrid2` $\rightarrow$ `defgrid3`), execute active scratch purging:
     - Remove stale binary locks, dirty `.gbw`, `.tmp*`, `.prop`, and `.densities` files from the working scratch directory.
     - Provide an explicit retention bypass only when an orbital guess (`MOREAD`, `*.gbw`) is deliberately verified and designated for state reuse under Method Matrix v4 §8B.
3. **Offline Environment Safety:**
   - Validate that execution runs cleanly under `COCHEM_OFFLINE=1` without attempting network calls or leaking temporary files into $T_{\text{src}}$.

---

## Deliverable 6: PEP 425 ABI & Platform Architecture Verification for Offline Wheel Caching (Suggestion #96)
**Target Module:** `CoChem-BASE` (`src/cochem_base/orchestrator/dependency_manager.py`, lines 302–376)

### Detailed Requirements:
1. **PEP 425 Tag Inspection:**
   - In `scan_for_local_wheel_fallback`, import `packaging.tags.sys_tags`.
   - Parse each candidate `.whl` filename into its standard tuple: `(distribution, version, build, python_tag, abi_tag, platform_tag)` using `packaging.utils.parse_wheel_filename`.
2. **Host Compatibility Filtering:**
   - Query the host system's supported tags:
     ```python
     from packaging.tags import sys_tags
     from packaging.utils import parse_wheel_filename

     supported_tags = set(sys_tags())
     ```
   - For each candidate wheel in the offline cache directory (resolved dynamically via `Path.home() / ".cochem" / "wheels"` or `$COCHEM_ARTIFACTS_DIR`), verify whether any tag yielded by the wheel matches `supported_tags`.
   - Discard incompatible wheels (e.g., reject `manylinux` wheels on macOS OrbStack or Windows WSL native, reject `x86_64` on ARM64/Apple Silicon) before invoking `pip install --no-index`.

---

## Deliverable 7: Heterogeneous Apple Silicon Performance Core Discovery & Contention Partitioning (Suggestion #97)
**Target Module:** `CoChem-BASE` (`src/cochem/core/hardware/topology.py`, lines 42–126)

### Detailed Requirements:
1. **Darwin-Native `sysctl` Heterogeneous Core Probing:**
   - In `discover_p_e_cores`, eliminate the fallthrough on `sys.platform == "darwin"` that assigns uniform cores (`physical_total, 0`).
   - Execute Darwin-native `sysctl` queries:
     ```python
     if sys.platform == "darwin":
         p_cores = int(subprocess.check_output(["sysctl", "-n", "hw.perflevel0.physicalcpu"]).decode().strip())
         e_cores = int(subprocess.check_output(["sysctl", "-n", "hw.perflevel1.physicalcpu"]).decode().strip())
     ```
   - Fall back to parsing `sysctl -n machdep.cpu.brand_string` or total physical cores if performance levels are unavailable.
2. **Scout-and-Anchor Core Partitioning:**
   - Under Method Matrix v4 §8A Contention Budgeting:
     - Reserve Efficiency (E) cores exclusively for background orchestration, IO polling, and SWMR serialization.
     - Pin compute-heavy electronic structure jobs (ORCA, CFOUR, xTB) exclusively to Performance (P) cores.
3. **Containerized CPU Quota Compliance:**
   - On Linux/Debian/Codespaces/CI, inspect cgroup CFS quotas (`/sys/fs/cgroup/cpu.max` or `/sys/fs/cgroup/cpu/cpu.cfs_quota_us`) and clamp detected cores to the integer floor of the assigned quota.

---

## Deliverable 8: Win32 Multi-Group Processor Affinity & High-Core Pinning (Suggestion #98)
**Target Module:** `CoChem-BASE` (`src/cochem/core/hardware/topology.py`, lines 275–290)

### Detailed Requirements:
1. **Processor Group Detection:**
   - On Windows (`sys.platform == "win32"`), support systems with $> 64$ logical processors (dual-socket AMD EPYC / Threadripper, Intel Xeon) where standard 64-bit affinity masks overflow.
   - Use `ctypes` to query `GetActiveProcessorGroupCount()` and `GetActiveProcessorCount(group_number)`.
2. **`SetThreadGroupAffinity` Win32 Binding:**
   - Define the Win32 `GROUP_AFFINITY` structure:
     ```python
     import ctypes
     from ctypes import wintypes

     class GROUP_AFFINITY(ctypes.Structure):
         _fields_ = [
             ("Mask", ctypes.c_size_t),
             ("Group", wintypes.WORD),
             ("Reserved", wintypes.WORD * 3)
         ]
     ```
   - Map target `core_index` to the corresponding `group = core_index // 64` and `relative_core = core_index % 64`.
   - Apply binding via `kernel32.SetThreadGroupAffinity(current_thread_handle, ctypes.byref(group_affinity), None)`.
3. **POSIX Complement:**
   - Retain and verify standard `os.sched_setaffinity(0, {core_index})` on Linux and HPC clusters.

---

## Deliverable 9: Dynamic Sandbox Engine Liveness Probing & Automated Downgrade Ladder (Suggestion #99)
**Target Module:** `CoChem-BASE` (`src/cochem_mobile/core/sandbox_broker.py`, lines 69–94, 141–220)

### Detailed Requirements:
1. **Active Daemon Liveness Probing:**
   - In `detect_available_engines`, do not rely solely on binary presence (`shutil.which("docker") is not None`).
   - Probe daemon connectivity with an explicit 1.5 s timeout:
     ```python
     def is_docker_active() -> bool:
         if not shutil.which("docker"):
             return False
         try:
             res = subprocess.run(
                 ["docker", "info", "--format", "{{.ServerVersion}}"],
                 stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL,
                 timeout=1.5,
                 check=True
             )
             return True
         except (subprocess.SubprocessError, OSError):
             return False
     ```
2. **Automated Downgrade Fallback Ladder:**
   - In `SandboxBroker.execute`, if the primary container runtime fails or daemon connectivity times out, automatically cascade down the execution ladder:
     $$\text{Docker} \longrightarrow \text{Podman} \longrightarrow \text{Apptainer} \longrightarrow \text{Subprocess Broker (Local Quarantine)}$$
   - Log the active fallback engine with provenance tag `[D]`. Ensure non-root sandbox execution policies are enforced.

---

## Deliverable 10: Multi-Rank MPI Memory Governance & Watchdog Backoff Accounting (Suggestion #100)
**Target Modules:** `CoChem-BASE` / `CoChem-TORQ` (`src/cochem_base/cochem_torq_watchdog.py`, lines 173–235)

### Detailed Requirements:
1. **Per-Rank MPI `%maxcore` Accounting:**
   - In `dynamic_memory_backoff`, update signature to accept `nprocs: int = 1`.
   - Recognize that in ORCA, `%maxcore` specifies memory *per individual MPI core*; aggregate system memory demand is:
     $$\text{Memory}_{\text{total}} = N_{\text{procs}} \times \%\text{maxcore}$$
2. **Cgroup & Physical RAM Detection:**
   - Query available memory, clamping to container cgroup limits (`/sys/fs/cgroup/memory.max`) if lower than host physical RAM (`psutil.virtual_memory().available`).
3. **Bounded Memory Calculation:**
   - Scale `%maxcore` to guarantee total allocation does not exceed $85\%$ of available RAM:
     ```python
     safe_budget_mb = available_system_ram_mb * 0.85
     new_maxcore = max(256, int(safe_budget_mb // max(1, nprocs)))
     ```
   - If `new_maxcore < 512`, emit a directive recommendation to switch integral calculation from in-memory storage to direct disk calculation (`! NoRifDirect` or `! Direct`).

---

## Deliverable 11: Non-Initializing NVML Telemetry, MPS Socket Isolation & GPU Concurrency (Suggestion #101)
**Target Module:** `CoChem-BASE` (`src/cochem/runners/cuda_budget.py`)

### Detailed Requirements:
1. **Non-Initializing Telemetry Polling:**
   - Mandate that background GPU utilization telemetry queries NVML handles without creating active CUDA driver contexts:
     - Use `pynvml.nvmlDeviceGetHandleByIndex()` and `pynvml.nvmlDeviceGetMemoryInfo()`.
     - Strictly avoid calling initializing framework functions (e.g., `torch.cuda.memory_allocated()` or `cupy.cuda.Device(0)`) during background telemetry polling.
2. **Per-Worker NVIDIA MPS Socket Isolation:**
   - Under Method Matrix v4 §8A.4, establish per-worker MPS session directories:
     ```python
     mps_root = Path(os.environ.get("COCH_SCRATCH", Path.home() / ".cochem" / "scratch")) / "mps"
     mps_pipe_dir = mps_root / f"pipe_{worker_id}"
     mps_pipe_dir.mkdir(parents=True, exist_ok=True)
     env["CUDA_MPS_PIPE_DIRECTORY"] = str(mps_pipe_dir)
     ```
3. **Context Allocation Throttling & Automated CPU Fallback:**
   - Track concurrent active GPU worker contexts.
   - If active concurrent client contexts exceed 4 on consumer GPUs (RTX 3090/4090 without MIG support) [D], or if running in non-GPU environments (Codespaces, GitHub Actions CI, macOS without CUDA), automatically route jobs to CPU-optimized binaries (xTB, ORCA CPU).

---

## Zero-Mock Verification & Test Plan
Create or update comprehensive integration tests in `tests/` verifying all 11 deliverables against real data and physical bounds without synthetic mocks:

1. `tests/topos/test_geometry_validation_hbond.py`:
   - Construct an authentic water dimer ($(\text{H}_2\text{O})_2$) with $d(\text{O}\cdots\text{H}) = 1.72\text{ \AA}$ and formamidinium formate.
   - Assert validation succeeds without raising `GeometricPlausibilityError` or flagging steric clashes.
   - Construct a collapsed dimer ($d(\text{O}\cdots\text{H}) = 1.10\text{ \AA}$) and verify it is correctly rejected as a clash.
2. `tests/torq/test_rotational_tensor_deduplication.py`:
   - Provide two asymmetric top conformers with identical scalar $B$ but distinct $A$ and $C$ constants ($\Delta A / A = 1.2\%$). Assert deduplication preserves both.
   - Provide two identical conformers with scrambled atom orderings. Assert Hungarian permutation-invariant RMSD identifies equivalence ($\le 0.15\text{ \AA}$) and deduplicates them.
3. `tests/base/test_h5_healer_concurrency.py`:
   - Launch multiple concurrent processes performing SWMR writes to a test HDF5 database protected by `filelock` and `threading.RLock`.
   - Assert zero database corruption, zero unhandled lock contention exceptions, and verify proper eviction of simulated stale locks based on hostname/PID inspection.
4. `tests/base/test_binary_interrogation_orca.py`:
   - Invoke `interrogate_binary_version` against ORCA binary banners (simulated via stdout banner streams).
   - Assert that versions (4.x, 5.x, 6.x) are correctly parsed without invoking `--version` or throwing `CalledProcessError`.
5. `tests/concurrency/test_tripartite_subprocess_broker.py`:
   - Run a simulated multi-step parameter remediation loop.
   - Assert that $T_{\text{src}}$ remains untouched and read-only, that intermediate dirty files (`.tmp`, `.gbw`) in $T_{\text{scr}}$ are purged before retry steps, and that final outputs are cleanly promoted to $T_{\text{store}}$.
6. `tests/base/test_dependency_wheel_tags.py`:
   - Feed mock directory lists of wheels with varying PEP 425 tags (`manylinux`, `win_amd64`, `macosx_arm64`).
   - Assert that `scan_for_local_wheel_fallback` selects exclusively wheels matching `packaging.tags.sys_tags()`.
7. `tests/core/test_topology_apple_silicon.py`:
   - Test `discover_p_e_cores` on macOS systems (or verify Darwin sysctl parser branch).
   - Assert P-core and E-core separation matches hardware topology, and verify cgroup quota clamping on Linux.
8. `tests/core/test_topology_windows_groups.py`:
   - Test processor affinity assignment for `core_index >= 64`.
   - Verify `GROUP_AFFINITY` struct generation and `SetThreadGroupAffinity` execution paths on Windows.
9. `tests/sandbox/test_sandbox_broker_fallback.py`:
   - Simulate an inactive Docker daemon (CLI present, daemon socket unresponsive).
   - Assert that `SandboxBroker` times out within 1.5 s and cascades through Podman/Apptainer to local quarantine without halting.
10. `tests/torq/test_torq_watchdog_mpi_memory.py`:
    - Pass an ORCA configuration with 8 MPI ranks on a 16 GB memory-constrained host.
    - Assert that `dynamic_memory_backoff` divides the budget by `nprocs` such that $N_{\text{procs}} \times \%\text{maxcore} \le 85\%$ of available RAM.
11. `tests/runners/test_cuda_budget_mps.py`:
    - Verify non-initializing NVML polling executes without creating primary CUDA contexts.
    - Assert per-worker `CUDA_MPS_PIPE_DIRECTORY` environment variable isolation and verify automated CPU fallback when context limit is exceeded.

Execute all changes cleanly, adhere strictly to Python typing standards, dynamic OS-agnostic pathing, and verify that the ecosystem passes linting (`ruff check`) and formatting. Proceed with implementation.
Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.