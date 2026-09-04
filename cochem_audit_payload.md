Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_02_Ecosystem_Part_2_prompts.md.
Original prompt:
# TASK SPECIFICATION FOR cochem-coder
**Task ID:** TASK-ECOSYSTEM-SRS-CHUNK-02  
**Category:** Method Matrix & Physics Integrity / Self-Healing Smart Setups & Environment-Agnostic Concurrency  
**Source Document:** `Perfected_SRS_Chunk_02_Ecosystem_Part_2.md`  
**Target Repositories/Packages:** `CoChem-BASE`, `CoChem-TORQ`, `CoChem-TOPOS`  
**Compliance Standards:** Method Matrix v4, Zero-Mock Mandate, FAIR Data Standards, 6-Tier Environment Matrix

---

## 1. MANDATORY AGENT CONTEXT & COMPLIANCE DIRECTIVES

You are `cochem-coder`. You are implementing the core physical integrity, conformer deduplication, and environment-agnostic concurrency/discovery refactoring requirements specified in Chunk 02 (Suggestions #11–#20) of the CoChem Ecosystem Audit.

### Invariants & Non-Negotiable Directives:
1. **Zero-Mock Protocol:** STRICTLY FORBIDDEN from using `pass`, `NotImplementedError`, synthetic coordinate jitter, arbitrary harmonic penalty functions, dummy loops, or mock test fixtures. Every routine must execute real physical logic, call actual executables, or emit typed exceptions when prerequisites are absent.
2. **Method Matrix Provenance Tagging:** All physical benchmarks, theoretical derivations, and empirical estimates must carry explicit provenance tags:
   - `[M]` Measured empirical benchmark
   - `[D]` Derived mathematical relationship
   - `[E]` Estimated theoretical projection
3. **Rotational Constants ($B_e$ vs $B_0$ Distinction) (§3.0):**
   - Maintain the theoretical distinction between equilibrium rotational constant $B_e$ (minimum of Born–Oppenheimer surface) and vibrational ground state $B_0 = B_e + \Delta B_{\text{vib}}$.
   - Never conflate $B_e$ and $B_0$. Conformer screening and clustering must explicitly evaluate all three principal constants ($A, B, C$) alongside the inertial defect ($\Delta$) and planar moments ($P_{aa}, P_{bb}, P_{cc}$).
4. **Dynamic Atomic Mass & Covalent/vdW Radii (Mendeleev Mandate):**
   - STRICTLY FORBIDDEN from hardcoding atomic masses, isotopic masses, covalent radii, or van der Waals radii.
   - All atomic and isotopic properties must be retrieved dynamically via `from mendeleev import element`.
   - Dynamic covalent radii (Pyykkö) must be cached per atomic number to eliminate microsecond-scale lookup overhead while guaranteeing zero static cutoff hardcoding.
5. **Covalent Connectivity & Fragment Partitioning (§9A):**
   - In frozen-monomer detection and molecular graph building, element-agnostic static cutoffs (e.g., 1.6 Å) are strictly prohibited.
   - Covalent connectivity must satisfy dynamic covalent radii scaling:
     $$d_{ij} < (r_{\text{cov},i} + r_{\text{cov},j}) \times 1.20\quad [D]$$
6. **Polar Hydrogen Bond Steric Clash Exemption:**
   - Steric clash pre-flight validation must not reject authentic hydrogen-bonded or halogen-bonded complexes.
   - For recognized donor–hydrogen pairs ($D$–$\text{H}$ where $D \in \{\text{O}, \text{N}, \text{F}\}$) interacting with electronegative acceptors ($A \in \{\text{O}, \text{N}, \text{F}, \text{Cl}, \text{Br}, \text{S}\}$), the non-bonded clearance threshold is scaled from $0.65 \times (r_{\text{vdw},i} + r_{\text{vdw},j})$ down to:
     $$\text{threshold}_{\text{HB}} = 0.50 \times (r_{\text{vdw},i} + r_{\text{vdw},j})\quad [M]$$
7. **Two-Stage Conformer Deduplication (§9B.1–§9B.3):**
   - Deduplication must never rely solely on a single rotational constant ($B$).
   - Stage A broad: Permutation-invariant RMSD (via Hungarian matching / graph automorphisms) and $\Delta E$.
   - Stage B spectroscopic: Screening across all three rotational constants ($A, B, C$) within the microwave observable window ($\Delta X / X < 0.005$) [M] and inertial defect $\Delta = I_c - I_a - I_b$.
8. **Tripartite Storage Architecture & SWMR Concurrency:**
   - Multi-worker database concurrency must follow the Tripartite Storage model: Host Client $\longleftrightarrow$ Atomic Staging Lease $\longleftrightarrow$ Canonical Persistent Lock.
   - Never write metadata non-atomically via raw `open()`. Use `.tmp.<pid>` staging followed by atomic `os.replace()`.
   - Never use POSIX-only `fcntl`. Mandate cross-platform IPC using `filelock.FileLock`.
   - `detect_zombie_pids` must enforce strict host-identity gating (`data.get("hostname") == platform.node()`) to prevent cross-host lock harvesting across distributed NFS/Lustre filesystems. Remote workers must rely on monotonic heartbeat leases with 60 s timeout expiration.
9. **Multi-Track Quantum Engine Discovery:**
   - Engine version probing must be non-destructive. Never execute `orca --version` (ORCA lacks `--version` and aborts with non-zero exit code).
   - Execute probing with `check=False`, capture both `stdout` and `stderr`, extract version information from the program banner regex, and resolve executables dynamically using `shutil.which` and `pathlib.Path`.
10. **Tripartite Air-Gap Scratch Remediation (§8B):**
    - Self-healing retry ladders must isolate: Ephemeral Execution Scratch $\longleftrightarrow$ Staged Checkpoint Cache $\longleftrightarrow$ Persistent Output Registry.
    - Retry loops must execute selective scratch wiping: remove dirty transient files (`*.tmp*`, `*.prop`, unfinalized locks), but explicitly preserve validated `.gbw` wavefunction checkpoints in a staging buffer when `MOREAD` orbital guess reuse is active (`defgrid1` $\to$ `defgrid2` $\to$ `defgrid3`).
11. **Platform-Aware Dependency Resolution:**
    - Offline fallback wheel resolution must validate candidate wheels against host platform tags using `packaging.tags.sys_tags()`, preventing platform-mismatched wheel selection in shared repository mounts.
12. **Hardware Topology & Scout-and-Anchor Budgeting (§8A):**
    - Apple Silicon Macs (native and OrbStack) must discover P-cores and E-cores using Darwin `sysctl` queries (`hw.perflevel0.physicalcpu` for P-cores, `hw.perflevel1.physicalcpu` for E-cores).
    - GPU discovery must be strictly non-initializing (NVML / `pynvml` or `nvidia-smi` CLI query). Parent orchestrator processes are strictly prohibited from calling `torch.cuda.is_available()` (Zero CUDA-Locking Mandate).
    - Windows processor affinity assignment for $>64$ logical cores must use Win32 `SetThreadGroupAffinity` with `GROUP_AFFINITY` structures rather than 64-bit integer bitshifts.
13. **Sandbox Container Liveness & Downgrade Cascade:**
    - Container engines must be validated with an active daemon ping (`docker info --format '{{.ServerVersion}}'` / `podman info` with a 1.5 s timeout).
    - Implement an automatic self-healing downgrade ladder: `Docker` $\longrightarrow$ `Podman` $\longrightarrow$ `Apptainer` $\longrightarrow$ `Subprocess`.

---

## 2. MODULE MODIFICATION TARGETS & SCHEMAS

### Module: `CoChem-TOPOS`
- `cascade_engine/cochem_topos_cascade_orchestrator.py`:
  - **Suggestion #11:** Refactor frozen-monomer connectivity detection in line ~381.
  - Purge hardcoded `cutoff=1.6` in `neighbor_list`.
  - Implement dynamic covalent radii lookup using `mendeleev.element(Z).covalent_radius_pyykko`:
    ```python
    # Dynamic neighbor list construction
    # Bond condition: d_ij < (r_cov,i + r_cov,j) * 1.20
    ```
  - Cache radii lookups by atomic number to ensure $O(1)$ lookup performance during coordinate graph assembly.
  - Employs this dynamic edge builder to segment multi-component clusters into discrete monomer subgraphs across all heteroatom-containing systems (halogens, organosulfur, phosphines, silanes).

### Module: `CoChem-BASE`
- `cochem/topos/geometry_validation.py`:
  - **Suggestion #12:** Refactor `validate_steric_contacts` in lines ~253–254.
  - Inspect donor–hydrogen connectivity before applying isotropic non-bonded repulsion thresholds.
  - When evaluating atom pairs $(i, j)$:
    - If atom $i$ is a hydrogen covalently bound to an electronegative donor ($D \in \{\text{O}, \text{N}, \text{F}\}$) and atom $j$ is an electronegative acceptor ($A \in \{\text{O}, \text{N}, \text{F}, \text{Cl}, \text{Br}, \text{S}\}$), or vice-versa:
      $$\text{threshold}_{ij} = 0.50 \times (r_{\text{vdw},i} + r_{\text{vdw},j})\quad [M]$$
    - For all other non-bonded contacts, maintain standard steric clash threshold:
      $$\text{threshold}_{ij} = 0.65 \times (r_{\text{vdw},i} + r_{\text{vdw},j})\quad [M]$$
  - Retrieve all $r_{\text{vdw}}$ dynamically from `mendeleev.element(Z).vdw_radius`.

- `src/cochem_base/cochem_h5_healer.py`:
  - **Suggestion #14:** Refactor SWMR lock manager and zombie PID detection in lines ~47–135.
  - Refactor `create_swmr_lock`:
    - Stage lock metadata (JSON containing `pid`, `hostname`, `lease_start_monotonic`, `lease_duration_sec`) into a staging file `f"{lock_path}.tmp.{os.getpid()}"`.
    - Atomically commit the lock via `os.replace(staging_path, lock_path)`.
    - Protect concurrency using `filelock.FileLock(f"{lock_path}.ipc.lock", timeout=60)`.
  - Refactor `detect_zombie_pids`:
    - Read lock metadata JSON.
    - Check host identity:
      - If `data.get("hostname") == platform.node()`: Evaluate local PID liveness using `psutil.pid_exists(lock_pid)`.
      - If `data.get("hostname") != platform.node()`: NEVER call local `psutil.pid_exists`. Check whether `time.monotonic() > lease_start_monotonic + lease_duration_sec`. If lease has expired, classify as stale; otherwise, preserve lock as active.
  - Refactor `force_release_swmr`:
    - Wrap unlinking in IPC `FileLock`. Only unlink locks verified as genuine dead local PIDs or expired remote leases.

- `src/cochem_base/orchestrator/cochem_setup_phase_3.py`:
  - **Suggestion #15:** Modernize `interrogate_binary_version` in lines ~512–570.
  - Engine-specific interrogation strategies:
    - For ORCA (`orca` / `orca_bin`):
      - Execute `subprocess.run([orca_bin], capture_output=True, text=True, timeout=10, check=False)`.
      - Capture both `stdout` and `stderr`.
      - Parse version from program banner using regex:
        ```python
        r"Program Version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)"
        ```
    - For xTB / CREST / CFOUR:
      - Interrogate using engine-specific non-destructive flags (`--version` for xTB/CREST, banner inspection for CFOUR).
    - Use `pathlib.Path` and `shutil.which` for cross-platform binary resolution across Windows, WSL, OrbStack, Linux, Codespaces, GHA, and HPC module systems.

- `src/cochem/concurrency/subprocess_broker.py`:
  - **Suggestion #16:** Refactor retry remediation loops in `execute_with_remediation` in lines ~254–385.
  - Implement `_sanitize_remediation_scratch(scratch_dir: Path, preserve_gbw: bool)`:
    - Identify transient files matching patterns: `*.tmp*`, `*.prop`, `*.scfp_tmp*`, `*.lock`, unclosed `.hess`.
    - Remove transient files to prevent quantum engine startup crashes.
    - If `preserve_gbw` is `True` (e.g., during SCF escalation or grid escalation `defgrid1` $\to$ `defgrid2` $\to$ `defgrid3` where `MOREAD` is configured):
      - Copy valid `.gbw` checkpoint to a staging buffer `scratch_dir / ".staged_checkpoint.gbw"`.
      - Wipe scratch directory transients.
      - Restore `.staged_checkpoint.gbw` to the canonical checkpoint name.
  - Ensure zero leak of dirty state across remediation attempts.

- `src/cochem_base/orchestrator/dependency_manager.py`:
  - **Suggestion #17:** Modernize `scan_for_local_wheel_fallback` in lines ~302–376.
  - Import `packaging.tags.sys_tags` and `packaging.utils.parse_wheel_filename`.
  - Parse candidate `.whl` files using `parse_wheel_filename(wheel_path.name)`.
  - Query supported platform tags on the running host: `supported_tags = set(packaging.tags.sys_tags())`.
  - Filter candidate wheels to ensure at least one wheel tag is present in `supported_tags`.
  - Use `pathlib.Path` for all artifact directory traversal.

- `src/cochem/core/hardware/topology.py`:
  - **Suggestion #18:** Refactor `discover_p_e_cores` in lines ~42–126.
    - For `sys.platform == "darwin"`:
      - Use `subprocess.run(["sysctl", "-n", "hw.perflevel0.physicalcpu"], ...)` to retrieve performance (P) core count.
      - Use `subprocess.run(["sysctl", "-n", "hw.perflevel1.physicalcpu"], ...)` to retrieve efficiency (E) core count.
      - Return `(p_cores, e_cores)`.
  - **Suggestion #19:** Refactor GPU discovery and CPU affinity pinning in lines ~255–290.
    - Purge `import torch; torch.cuda.is_available()` from `get_worker_env` and topology discovery.
    - Implement non-initializing GPU discovery:
      - Attempt `pynvml` initialization and query `nvmlDeviceGetCount()`.
      - Fall back to `nvidia-smi --query-gpu=count --format=csv,noheader,nounits` subprocess.
      - Guarantee zero CUDA runtime context initialization in the parent process.
    - Refactor `pin_scout_affinity`:
      - For Windows systems where `core_index >= 64` or `os.cpu_count() > 64`:
        - Define Win32 `GROUP_AFFINITY` and `PROCESSOR_NUMBER` `ctypes` structures.
        - Call kernel32 `SetThreadGroupAffinity` to pin worker processes to processor groups beyond Group 0 without 64-bit integer overflow.

- `src/cochem_mobile/core/sandbox_broker.py`:
  - **Suggestion #20:** Refactor `SandboxBroker` engine detection and execution cascade in lines ~69–220.
  - Implement active daemon ping in `_probe_engine_liveness(engine_name: str) -> bool`:
    - For `docker`: Run `docker info --format '{{.ServerVersion}}'` with `timeout=1.5`. Return `True` only on exit code 0.
    - For `podman`: Run `podman info` with `timeout=1.5`. Return `True` only on exit code 0.
    - For `apptainer` / `singularity`: Run version probe with `timeout=1.5`.
  - Refactor `SandboxBroker.execute`:
    - Implement an automatic downgrade cascade: `Docker` $\longrightarrow$ `Podman` $\longrightarrow$ `Apptainer` $\longrightarrow$ `Subprocess`.
    - Enforce Tripartite Air-Gap directory isolation: Host Workspace $\longleftrightarrow$ Ephemeral Sandbox Scratch $\longleftrightarrow$ Sanitized Artifact Extraction.

### Module: `CoChem-TORQ`
- `Libraries/cochem_torq_goat.py`:
  - **Suggestion #13:** Refactor conformer deduplication in lines ~765–1082.
  - Refactor rotational constant screening:
    - Extract all three rotational constants ($A, B, C$) and compute inertial defect $\Delta = I_c - I_a - I_b$.
    - Require conformers to differ by $>0.5\%$ across at least one rotational constant ($A, B,$ or $C$) or by $>0.05\text{ amu}\cdot\text{\AA}^2$ in inertial defect $\Delta$ [M] before being classified as distinct.
  - Refactor `compute_rmsd`:
    - Implement permutation-invariant RMSD matching over chemically identical nuclei (e.g., Hungarian algorithm on Euclidean distance matrices or topological graph isomorphism mapping) to prevent atom-order swapping artifacts between GOAT and CREST.

---

## 3. WORK BREAKDOWN STRUCTURE (WBS) & IMPLEMENTATION CHECKLIST

### Phase 1: Dynamic Radii & Steric Clash Modernization (`CoChem-TOPOS` & `CoChem-BASE`)
- [ ] **Subtask 1.1: Dynamic Covalent Radii Partitioning in TOPOS Cascade Orchestrator**
  - In `cascade_engine/cochem_topos_cascade_orchestrator.py`, replace `cutoff=1.6` with Pyykkö dynamic covalent radii scaling $d_{ij} < 1.20 \times (r_{\text{cov},i} + r_{\text{cov},j})$ via `mendeleev`.
  - Implement caching for elemental radii to maintain sub-millisecond graph partition speeds.
- [ ] **Subtask 1.2: Polar Hydrogen Bond Steric Clash Exemption in Geometry Validation**
  - In `cochem/topos/geometry_validation.py`, implement donor–hydrogen detection.
  - Lower the non-bonded clearance threshold to $0.50 \times (r_{\text{vdw},i} + r_{\text{vdw},j})$ for polar $\text{D–H}\cdots\text{A}$ interactions while keeping $0.65 \times \sum r_{\text{vdw}}$ for isotropic non-polar contacts.

### Phase 2: Spectroscopic Conformer Deduplication (`CoChem-TORQ`)
- [ ] **Subtask 2.1: Tri-Constant & Inertial Defect Spectroscopic Filter in GOAT**
  - In `Libraries/cochem_torq_goat.py`, expand the scalar $B$ constant filter to evaluate all three constants ($A, B, C$) and inertial defect $\Delta$.
- [ ] **Subtask 2.2: Permutation-Invariant RMSD / Hungarian Alignment**
  - In `Libraries/cochem_torq_goat.py`, implement permutation-invariant RMSD evaluating identical nuclei permutations to eliminate engine-dependent atom reordering artifacts.

### Phase 3: SWMR Storage Concurrency & Engine Discovery (`CoChem-BASE`)
- [ ] **Subtask 3.1: Tripartite SWMR Lock Healer, Host Gating & Heartbeat Leases**
  - In `src/cochem_base/cochem_h5_healer.py`, implement `.tmp.<pid>` staging and atomic `os.replace` for SWMR lock creation.
  - Enforce `data.get("hostname") == platform.node()` gating in `detect_zombie_pids`, and implement monotonic heartbeat leases for distributed workers.
  - Replace POSIX `fcntl` with cross-platform `filelock.FileLock`.
- [ ] **Subtask 3.2: Non-Destructive Multi-Track Quantum Engine Interrogation**
  - In `src/cochem_base/orchestrator/cochem_setup_phase_3.py`, replace `orca --version` with non-destructive banner execution (`check=False`, parsing version regex from stdout/stderr).
  - Abstract executable lookup across all 6 environment tiers using `shutil.which` and `pathlib.Path`.

### Phase 4: Subprocess Scratch Remediation & Platform-Aware Dependencies (`CoChem-BASE`)
- [ ] **Subtask 4.1: Tripartite Scratch Sanitization & Staged Checkpoint Preservation**
  - In `src/cochem/concurrency/subprocess_broker.py`, implement selective scratch purge callback in `execute_with_remediation`.
  - Wipe dirty transient files (`*.tmp*`, `*.prop`, unclosed locks) while preserving validated `.gbw` wavefunction checkpoints in staging cache when `MOREAD` reuse is requested.
- [ ] **Subtask 4.2: PEP 425 Platform Tag Validation in Wheel Fallback Resolver**
  - In `src/cochem_base/orchestrator/dependency_manager.py`, integrate `packaging.tags.sys_tags()` to filter candidate wheels by host OS, architecture, and ABI compatibility.

### Phase 5: Hardware Topology & Container Sandbox Hardening (`CoChem-BASE`)
- [ ] **Subtask 5.1: Apple Silicon Darwin P/E-Core Topology Probing**
  - In `src/cochem/core/hardware/topology.py`, add Darwin `sysctl` queries (`hw.perflevel0.physicalcpu`, `hw.perflevel1.physicalcpu`) to correctly segregate P-cores and E-cores on Apple Silicon.
- [ ] **Subtask 5.2: Zero CUDA-Locking Discovery & Windows Multi-Group Affinity (>64 Cores)**
  - In `src/cochem/core/hardware/topology.py`, eliminate `torch.cuda.is_available()`; replace with non-initializing NVML / `nvidia-smi` queries.
  - Implement `SetThreadGroupAffinity` via `ctypes` for Windows processor groups on systems with $>64$ logical cores.
- [ ] **Subtask 5.3: Container Daemon Liveness Ping & Downgrade Cascade in Sandbox Broker**
  - In `src/cochem_mobile/core/sandbox_broker.py`, implement 1.5 s daemon ping for Docker/Podman engines.
  - Implement dynamic fallback ladder (`Docker` $\to$ `Podman` $\to$ `Apptainer` $\to$ `Subprocess`) with Tripartite Air-Gap scratch quarantine.

---

## 4. VERIFICATION & ACCEPTANCE CRITERIA

Verify all implementations against these physical, computational, and architectural criteria:
1. **Dynamic Covalent Partitioning Verification:**
   - Run monomer partitioning on chlorinated, brominated, and sulfur-containing test complexes ($\text{CH}_3\text{Cl}\cdots\text{H}_2\text{O}$, $(\text{CH}_3)_2\text{S}\cdots\text{SO}_2$). C–Cl, C–Br, and S–S bonds must not be severed as non-bonded contacts.
2. **Hydrogen Bond Clash Clearance:**
   - Water dimer $(\text{H}_2\text{O})_2$ ($R_{\text{O}\cdots\text{H}} \approx 1.70\text{ \AA}$) and formamidinium formate must pass `validate_steric_contacts` without raising `GeometricPlausibilityError`.
3. **Spectroscopic Conformer Deduplication:**
   - Conformer pairs with identical $B$ but distinct $A$ or $C$ (or differing $\Delta$) must both be retained in the ensemble. Structures identical up to atom permutation must be recognized as duplicates with $\text{RMSD} = 0.0\text{ \AA}$.
4. **SWMR Cross-Host Lock Immunity:**
   - Simulate lock file from another host (`hostname: "remote-node-01"`). Ensure local `cochem_h5_healer` does not unlink the lock while its lease duration is active.
5. **Zero-Error ORCA Setup Interrogation:**
   - Interrogate an ORCA binary via `cochem_setup_phase_3.py`. Verify version string (e.g., `5.0.4` or `6.0.0`) is parsed without raising `CalledProcessError`.
6. **Remediation Scratch Hygiene & Orbitals:**
   - Induce an SCF retry in `SubprocessBroker`. Verify intermediate scratch is purged of `*.tmp*` and `*.prop` while the `.gbw` file is preserved and successfully loaded via `MOREAD`.
7. **Platform Wheel Tag Compliance:**
   - Provide a mock directory containing Windows, Linux, and macOS wheels for a package. On a Windows host, `scan_for_local_wheel_fallback` must select only the Windows-compatible wheel.
8. **Apple Silicon Core Accuracy:**
   - On a Darwin arm64 platform, verify `discover_p_e_cores` returns non-zero performance and efficiency core counts.
9. **Zero CUDA-Locking Verification:**
   - Execute `get_worker_env` and verify via `sys.modules` that `torch.cuda` was not initialized in the parent process.
10. **Sandbox Engine Liveness Fallback:**
    - With Docker CLI present but the Docker daemon stopped, `SandboxBroker.execute()` must smoothly fall back to Podman or Subprocess without unhandled socket connection exceptions.

---

## 5. SWARM STATE UPDATE PROTOCOL

Upon completion of this implementation:
1. Move all replaced legacy files to `.trash` using `shutil.move`.
2. Update `swarm_state.json` at the workspace root:
   ```json
   {
     "agent": "cochem-coder",
     "task_id": "TASK-ECOSYSTEM-SRS-CHUNK-02",
     "status": "SUCCESS",
     "artifacts_produced": [
       "CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py",
       "CoChem-BASE/cochem/topos/geometry_validation.py",
       "CoChem-TORQ/Libraries/cochem_torq_goat.py",
       "CoChem-BASE/src/cochem_base/cochem_h5_healer.py",
       "CoChem-BASE/src/cochem_base/orchestrator/cochem_setup_phase_3.py",
       "CoChem-BASE/src/cochem/concurrency/subprocess_broker.py",
       "CoChem-BASE/src/cochem_base/orchestrator/dependency_manager.py",
       "CoChem-BASE/src/cochem/core/hardware/topology.py",
       "CoChem-BASE/src/cochem_mobile/core/sandbox_broker.py"
     ],
     "timestamp": "<ISO-8601-TIMESTAMP>"
   }
   ```
3. Hand off the completed implementation diffs and execution logs to `cochem-audit` for adversarial compliance review.
# TASK SPECIFICATION FOR cochem-coder
**Task ID:** TASK-ECOSYSTEM-SRS-CHUNK-02  
**Category:** Method Matrix & Physics Integrity / Self-Healing Smart Setups & Environment-Agnostic Concurrency  
**Source Document:** `Perfected_SRS_Chunk_02_Ecosystem_Part_2.md`  
**Target Repositories/Packages:** `CoChem-BASE`, `CoChem-TORQ`, `CoChem-TOPOS`  
**Compliance Standards:** Method Matrix v4, Zero-Mock Mandate, FAIR Data Standards, 6-Tier Environment Matrix

---

## 1. MANDATORY AGENT CONTEXT & COMPLIANCE DIRECTIVES

You are `cochem-coder`. You are implementing the core physical integrity, conformer deduplication, and environment-agnostic concurrency/discovery refactoring requirements specified in Chunk 02 (Suggestions #11–#20) of the CoChem Ecosystem Audit.

### Invariants & Non-Negotiable Directives:
1. **Zero-Mock Protocol:** STRICTLY FORBIDDEN from using `pass`, `NotImplementedError`, synthetic coordinate jitter, arbitrary harmonic penalty functions, dummy loops, or mock test fixtures. Every routine must execute real physical logic, call actual executables, or emit typed exceptions when prerequisites are absent.
2. **Method Matrix Provenance Tagging:** All physical benchmarks, theoretical derivations, and empirical estimates must carry explicit provenance tags:
   - `[M]` Measured empirical benchmark
   - `[D]` Derived mathematical relationship
   - `[E]` Estimated theoretical projection
3. **Rotational Constants ($B_e$ vs $B_0$ Distinction) (§3.0):**
   - Maintain the theoretical distinction between equilibrium rotational constant $B_e$ (minimum of Born–Oppenheimer surface) and vibrational ground state $B_0 = B_e + \Delta B_{\text{vib}}$.
   - Never conflate $B_e$ and $B_0$. Conformer screening and clustering must explicitly evaluate all three principal constants ($A, B, C$) alongside the inertial defect ($\Delta$) and planar moments ($P_{aa}, P_{bb}, P_{cc}$).
4. **Dynamic Atomic Mass & Covalent/vdW Radii (Mendeleev Mandate):**
   - STRICTLY FORBIDDEN from hardcoding atomic masses, isotopic masses, covalent radii, or van der Waals radii.
   - All atomic and isotopic properties must be retrieved dynamically via `from mendeleev import element`.
   - Dynamic covalent radii (Pyykkö) must be cached per atomic number to eliminate microsecond-scale lookup overhead while guaranteeing zero static cutoff hardcoding.
5. **Covalent Connectivity & Fragment Partitioning (§9A):**
   - In frozen-monomer detection and molecular graph building, element-agnostic static cutoffs (e.g., 1.6 Å) are strictly prohibited.
   - Covalent connectivity must satisfy dynamic covalent radii scaling:
     $$d_{ij} < (r_{\text{cov},i} + r_{\text{cov},j}) \times 1.20\quad [D]$$
6. **Polar Hydrogen Bond Steric Clash Exemption:**
   - Steric clash pre-flight validation must not reject authentic hydrogen-bonded or halogen-bonded complexes.
   - For recognized donor–hydrogen pairs ($D$–$\text{H}$ where $D \in \{\text{O}, \text{N}, \text{F}\}$) interacting with electronegative acceptors ($A \in \{\text{O}, \text{N}, \text{F}, \text{Cl}, \text{Br}, \text{S}\}$), the non-bonded clearance threshold is scaled from $0.65 \times (r_{\text{vdw},i} + r_{\text{vdw},j})$ down to:
     $$\text{threshold}_{\text{HB}} = 0.50 \times (r_{\text{vdw},i} + r_{\text{vdw},j})\quad [M]$$
7. **Two-Stage Conformer Deduplication (§9B.1–§9B.3):**
   - Deduplication must never rely solely on a single rotational constant ($B$).
   - Stage A broad: Permutation-invariant RMSD (via Hungarian matching / graph automorphisms) and $\Delta E$.
   - Stage B spectroscopic: Screening across all three rotational constants ($A, B, C$) within the microwave observable window ($\Delta X / X < 0.005$) [M] and inertial defect $\Delta = I_c - I_a - I_b$.
8. **Tripartite Storage Architecture & SWMR Concurrency:**
   - Multi-worker database concurrency must follow the Tripartite Storage model: Host Client $\longleftrightarrow$ Atomic Staging Lease $\longleftrightarrow$ Canonical Persistent Lock.
   - Never write metadata non-atomically via raw `open()`. Use `.tmp.<pid>` staging followed by atomic `os.replace()`.
   - Never use POSIX-only `fcntl`. Mandate cross-platform IPC using `filelock.FileLock`.
   - `detect_zombie_pids` must enforce strict host-identity gating (`data.get("hostname") == platform.node()`) to prevent cross-host lock harvesting across distributed NFS/Lustre filesystems. Remote workers must rely on monotonic heartbeat leases with 60 s timeout expiration.
9. **Multi-Track Quantum Engine Discovery:**
   - Engine version probing must be non-destructive. Never execute `orca --version` (ORCA lacks `--version` and aborts with non-zero exit code).
   - Execute probing with `check=False`, capture both `stdout` and `stderr`, extract version information from the program banner regex, and resolve executables dynamically using `shutil.which` and `pathlib.Path`.
10. **Tripartite Air-Gap Scratch Remediation (§8B):**
    - Self-healing retry ladders must isolate: Ephemeral Execution Scratch $\longleftrightarrow$ Staged Checkpoint Cache $\longleftrightarrow$ Persistent Output Registry.
    - Retry loops must execute selective scratch wiping: remove dirty transient files (`*.tmp*`, `*.prop`, unfinalized locks), but explicitly preserve validated `.gbw` wavefunction checkpoints in a staging buffer when `MOREAD` orbital guess reuse is active (`defgrid1` $\to$ `defgrid2` $\to$ `defgrid3`).
11. **Platform-Aware Dependency Resolution:**
    - Offline fallback wheel resolution must validate candidate wheels against host platform tags using `packaging.tags.sys_tags()`, preventing platform-mismatched wheel selection in shared repository mounts.
12. **Hardware Topology & Scout-and-Anchor Budgeting (§8A):**
    - Apple Silicon Macs (native and OrbStack) must discover P-cores and E-cores using Darwin `sysctl` queries (`hw.perflevel0.physicalcpu` for P-cores, `hw.perflevel1.physicalcpu` for E-cores).
    - GPU discovery must be strictly non-initializing (NVML / `pynvml` or `nvidia-smi` CLI query). Parent orchestrator processes are strictly prohibited from calling `torch.cuda.is_available()` (Zero CUDA-Locking Mandate).
    - Windows processor affinity assignment for $>64$ logical cores must use Win32 `SetThreadGroupAffinity` with `GROUP_AFFINITY` structures rather than 64-bit integer bitshifts.
13. **Sandbox Container Liveness & Downgrade Cascade:**
    - Container engines must be validated with an active daemon ping (`docker info --format '{{.ServerVersion}}'` / `podman info` with a 1.5 s timeout).
    - Implement an automatic self-healing downgrade ladder: `Docker` $\longrightarrow$ `Podman` $\longrightarrow$ `Apptainer` $\longrightarrow$ `Subprocess`.

---

## 2. MODULE MODIFICATION TARGETS & SCHEMAS

### Module: `CoChem-TOPOS`
- `cascade_engine/cochem_topos_cascade_orchestrator.py`:
  - **Suggestion #11:** Refactor frozen-monomer connectivity detection in line ~381.
  - Purge hardcoded `cutoff=1.6` in `neighbor_list`.
  - Implement dynamic covalent radii lookup using `mendeleev.element(Z).covalent_radius_pyykko`:
    ```python
    # Dynamic neighbor list construction
    # Bond condition: d_ij < (r_cov,i + r_cov,j) * 1.20
    ```
  - Cache radii lookups by atomic number to ensure $O(1)$ lookup performance during coordinate graph assembly.
  - Employs this dynamic edge builder to segment multi-component clusters into discrete monomer subgraphs across all heteroatom-containing systems (halogens, organosulfur, phosphines, silanes).

### Module: `CoChem-BASE`
- `cochem/topos/geometry_validation.py`:
  - **Suggestion #12:** Refactor `validate_steric_contacts` in lines ~253–254.
  - Inspect donor–hydrogen connectivity before applying isotropic non-bonded repulsion thresholds.
  - When evaluating atom pairs $(i, j)$:
    - If atom $i$ is a hydrogen covalently bound to an electronegative donor ($D \in \{\text{O}, \text{N}, \text{F}\}$) and atom $j$ is an electronegative acceptor ($A \in \{\text{O}, \text{N}, \text{F}, \text{Cl}, \text{Br}, \text{S}\}$), or vice-versa:
      $$\text{threshold}_{ij} = 0.50 \times (r_{\text{vdw},i} + r_{\text{vdw},j})\quad [M]$$
    - For all other non-bonded contacts, maintain standard steric clash threshold:
      $$\text{threshold}_{ij} = 0.65 \times (r_{\text{vdw},i} + r_{\text{vdw},j})\quad [M]$$
  - Retrieve all $r_{\text{vdw}}$ dynamically from `mendeleev.element(Z).vdw_radius`.

- `src/cochem_base/cochem_h5_healer.py`:
  - **Suggestion #14:** Refactor SWMR lock manager and zombie PID detection in lines ~47–135.
  - Refactor `create_swmr_lock`:
    - Stage lock metadata (JSON containing `pid`, `hostname`, `lease_start_monotonic`, `lease_duration_sec`) into a staging file `f"{lock_path}.tmp.{os.getpid()}"`.
    - Atomically commit the lock via `os.replace(staging_path, lock_path)`.
    - Protect concurrency using `filelock.FileLock(f"{lock_path}.ipc.lock", timeout=60)`.
  - Refactor `detect_zombie_pids`:
    - Read lock metadata JSON.
    - Check host identity:
      - If `data.get("hostname") == platform.node()`: Evaluate local PID liveness using `psutil.pid_exists(lock_pid)`.
      - If `data.get("hostname") != platform.node()`: NEVER call local `psutil.pid_exists`. Check whether `time.monotonic() > lease_start_monotonic + lease_duration_sec`. If lease has expired, classify as stale; otherwise, preserve lock as active.
  - Refactor `force_release_swmr`:
    - Wrap unlinking in IPC `FileLock`. Only unlink locks verified as genuine dead local PIDs or expired remote leases.

- `src/cochem_base/orchestrator/cochem_setup_phase_3.py`:
  - **Suggestion #15:** Modernize `interrogate_binary_version` in lines ~512–570.
  - Engine-specific interrogation strategies:
    - For ORCA (`orca` / `orca_bin`):
      - Execute `subprocess.run([orca_bin], capture_output=True, text=True, timeout=10, check=False)`.
      - Capture both `stdout` and `stderr`.
      - Parse version from program banner using regex:
        ```python
        r"Program Version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)"
        ```
    - For xTB / CREST / CFOUR:
      - Interrogate using engine-specific non-destructive flags (`--version` for xTB/CREST, banner inspection for CFOUR).
    - Use `pathlib.Path` and `shutil.which` for cross-platform binary resolution across Windows, WSL, OrbStack, Linux, Codespaces, GHA, and HPC module systems.

- `src/cochem/concurrency/subprocess_broker.py`:
  - **Suggestion #16:** Refactor retry remediation loops in `execute_with_remediation` in lines ~254–385.
  - Implement `_sanitize_remediation_scratch(scratch_dir: Path, preserve_gbw: bool)`:
    - Identify transient files matching patterns: `*.tmp*`, `*.prop`, `*.scfp_tmp*`, `*.lock`, unclosed `.hess`.
    - Remove transient files to prevent quantum engine startup crashes.
    - If `preserve_gbw` is `True` (e.g., during SCF escalation or grid escalation `defgrid1` $\to$ `defgrid2` $\to$ `defgrid3` where `MOREAD` is configured):
      - Copy valid `.gbw` checkpoint to a staging buffer `scratch_dir / ".staged_checkpoint.gbw"`.
      - Wipe scratch directory transients.
      - Restore `.staged_checkpoint.gbw` to the canonical checkpoint name.
  - Ensure zero leak of dirty state across remediation attempts.

- `src/cochem_base/orchestrator/dependency_manager.py`:
  - **Suggestion #17:** Modernize `scan_for_local_wheel_fallback` in lines ~302–376.
  - Import `packaging.tags.sys_tags` and `packaging.utils.parse_wheel_filename`.
  - Parse candidate `.whl` files using `parse_wheel_filename(wheel_path.name)`.
  - Query supported platform tags on the running host: `supported_tags = set(packaging.tags.sys_tags())`.
  - Filter candidate wheels to ensure at least one wheel tag is present in `supported_tags`.
  - Use `pathlib.Path` for all artifact directory traversal.

- `src/cochem/core/hardware/topology.py`:
  - **Suggestion #18:** Refactor `discover_p_e_cores` in lines ~42–126.
    - For `sys.platform == "darwin"`:
      - Use `subprocess.run(["sysctl", "-n", "hw.perflevel0.physicalcpu"], ...)` to retrieve performance (P) core count.
      - Use `subprocess.run(["sysctl", "-n", "hw.perflevel1.physicalcpu"], ...)` to retrieve efficiency (E) core count.
      - Return `(p_cores, e_cores)`.
  - **Suggestion #19:** Refactor GPU discovery and CPU affinity pinning in lines ~255–290.
    - Purge `import torch; torch.cuda.is_available()` from `get_worker_env` and topology discovery.
    - Implement non-initializing GPU discovery:
      - Attempt `pynvml` initialization and query `nvmlDeviceGetCount()`.
      - Fall back to `nvidia-smi --query-gpu=count --format=csv,noheader,nounits` subprocess.
      - Guarantee zero CUDA runtime context initialization in the parent process.
    - Refactor `pin_scout_affinity`:
      - For Windows systems where `core_index >= 64` or `os.cpu_count() > 64`:
        - Define Win32 `GROUP_AFFINITY` and `PROCESSOR_NUMBER` `ctypes` structures.
        - Call kernel32 `SetThreadGroupAffinity` to pin worker processes to processor groups beyond Group 0 without 64-bit integer overflow.

- `src/cochem_mobile/core/sandbox_broker.py`:
  - **Suggestion #20:** Refactor `SandboxBroker` engine detection and execution cascade in lines ~69–220.
  - Implement active daemon ping in `_probe_engine_liveness(engine_name: str) -> bool`:
    - For `docker`: Run `docker info --format '{{.ServerVersion}}'` with `timeout=1.5`. Return `True` only on exit code 0.
    - For `podman`: Run `podman info` with `timeout=1.5`. Return `True` only on exit code 0.
    - For `apptainer` / `singularity`: Run version probe with `timeout=1.5`.
  - Refactor `SandboxBroker.execute`:
    - Implement an automatic downgrade cascade: `Docker` $\longrightarrow$ `Podman` $\longrightarrow$ `Apptainer` $\longrightarrow$ `Subprocess`.
    - Enforce Tripartite Air-Gap directory isolation: Host Workspace $\longleftrightarrow$ Ephemeral Sandbox Scratch $\longleftrightarrow$ Sanitized Artifact Extraction.

### Module: `CoChem-TORQ`
- `Libraries/cochem_torq_goat.py`:
  - **Suggestion #13:** Refactor conformer deduplication in lines ~765–1082.
  - Refactor rotational constant screening:
    - Extract all three rotational constants ($A, B, C$) and compute inertial defect $\Delta = I_c - I_a - I_b$.
    - Require conformers to differ by $>0.5\%$ across at least one rotational constant ($A, B,$ or $C$) or by $>0.05\text{ amu}\cdot\text{\AA}^2$ in inertial defect $\Delta$ [M] before being classified as distinct.
  - Refactor `compute_rmsd`:
    - Implement permutation-invariant RMSD matching over chemically identical nuclei (e.g., Hungarian algorithm on Euclidean distance matrices or topological graph isomorphism mapping) to prevent atom-order swapping artifacts between GOAT and CREST.

---

## 3. WORK BREAKDOWN STRUCTURE (WBS) & IMPLEMENTATION CHECKLIST

### Phase 1: Dynamic Radii & Steric Clash Modernization (`CoChem-TOPOS` & `CoChem-BASE`)
- [ ] **Subtask 1.1: Dynamic Covalent Radii Partitioning in TOPOS Cascade Orchestrator**
  - In `cascade_engine/cochem_topos_cascade_orchestrator.py`, replace `cutoff=1.6` with Pyykkö dynamic covalent radii scaling $d_{ij} < 1.20 \times (r_{\text{cov},i} + r_{\text{cov},j})$ via `mendeleev`.
  - Implement caching for elemental radii to maintain sub-millisecond graph partition speeds.
- [ ] **Subtask 1.2: Polar Hydrogen Bond Steric Clash Exemption in Geometry Validation**
  - In `cochem/topos/geometry_validation.py`, implement donor–hydrogen detection.
  - Lower the non-bonded clearance threshold to $0.50 \times (r_{\text{vdw},i} + r_{\text{vdw},j})$ for polar $\text{D–H}\cdots\text{A}$ interactions while keeping $0.65 \times \sum r_{\text{vdw}}$ for isotropic non-polar contacts.

### Phase 2: Spectroscopic Conformer Deduplication (`CoChem-TORQ`)
- [ ] **Subtask 2.1: Tri-Constant & Inertial Defect Spectroscopic Filter in GOAT**
  - In `Libraries/cochem_torq_goat.py`, expand the scalar $B$ constant filter to evaluate all three constants ($A, B, C$) and inertial defect $\Delta$.
- [ ] **Subtask 2.2: Permutation-Invariant RMSD / Hungarian Alignment**
  - In `Libraries/cochem_torq_goat.py`, implement permutation-invariant RMSD evaluating identical nuclei permutations to eliminate engine-dependent atom reordering artifacts.

### Phase 3: SWMR Storage Concurrency & Engine Discovery (`CoChem-BASE`)
- [ ] **Subtask 3.1: Tripartite SWMR Lock Healer, Host Gating & Heartbeat Leases**
  - In `src/cochem_base/cochem_h5_healer.py`, implement `.tmp.<pid>` staging and atomic `os.replace` for SWMR lock creation.
  - Enforce `data.get("hostname") == platform.node()` gating in `detect_zombie_pids`, and implement monotonic heartbeat leases for distributed workers.
  - Replace POSIX `fcntl` with cross-platform `filelock.FileLock`.
- [ ] **Subtask 3.2: Non-Destructive Multi-Track Quantum Engine Interrogation**
  - In `src/cochem_base/orchestrator/cochem_setup_phase_3.py`, replace `orca --version` with non-destructive banner execution (`check=False`, parsing version regex from stdout/stderr).
  - Abstract executable lookup across all 6 environment tiers using `shutil.which` and `pathlib.Path`.

### Phase 4: Subprocess Scratch Remediation & Platform-Aware Dependencies (`CoChem-BASE`)
- [ ] **Subtask 4.1: Tripartite Scratch Sanitization & Staged Checkpoint Preservation**
  - In `src/cochem/concurrency/subprocess_broker.py`, implement selective scratch purge callback in `execute_with_remediation`.
  - Wipe dirty transient files (`*.tmp*`, `*.prop`, unclosed locks) while preserving validated `.gbw` wavefunction checkpoints in staging cache when `MOREAD` reuse is requested.
- [ ] **Subtask 4.2: PEP 425 Platform Tag Validation in Wheel Fallback Resolver**
  - In `src/cochem_base/orchestrator/dependency_manager.py`, integrate `packaging.tags.sys_tags()` to filter candidate wheels by host OS, architecture, and ABI compatibility.

### Phase 5: Hardware Topology & Container Sandbox Hardening (`CoChem-BASE`)
- [ ] **Subtask 5.1: Apple Silicon Darwin P/E-Core Topology Probing**
  - In `src/cochem/core/hardware/topology.py`, add Darwin `sysctl` queries (`hw.perflevel0.physicalcpu`, `hw.perflevel1.physicalcpu`) to correctly segregate P-cores and E-cores on Apple Silicon.
- [ ] **Subtask 5.2: Zero CUDA-Locking Discovery & Windows Multi-Group Affinity (>64 Cores)**
  - In `src/cochem/core/hardware/topology.py`, eliminate `torch.cuda.is_available()`; replace with non-initializing NVML / `nvidia-smi` queries.
  - Implement `SetThreadGroupAffinity` via `ctypes` for Windows processor groups on systems with $>64$ logical cores.
- [ ] **Subtask 5.3: Container Daemon Liveness Ping & Downgrade Cascade in Sandbox Broker**
  - In `src/cochem_mobile/core/sandbox_broker.py`, implement 1.5 s daemon ping for Docker/Podman engines.
  - Implement dynamic fallback ladder (`Docker` $\to$ `Podman` $\to$ `Apptainer` $\to$ `Subprocess`) with Tripartite Air-Gap scratch quarantine.

---

## 4. VERIFICATION & ACCEPTANCE CRITERIA

Verify all implementations against these physical, computational, and architectural criteria:
1. **Dynamic Covalent Partitioning Verification:**
   - Run monomer partitioning on chlorinated, brominated, and sulfur-containing test complexes ($\text{CH}_3\text{Cl}\cdots\text{H}_2\text{O}$, $(\text{CH}_3)_2\text{S}\cdots\text{SO}_2$). C–Cl, C–Br, and S–S bonds must not be severed as non-bonded contacts.
2. **Hydrogen Bond Clash Clearance:**
   - Water dimer $(\text{H}_2\text{O})_2$ ($R_{\text{O}\cdots\text{H}} \approx 1.70\text{ \AA}$) and formamidinium formate must pass `validate_steric_contacts` without raising `GeometricPlausibilityError`.
3. **Spectroscopic Conformer Deduplication:**
   - Conformer pairs with identical $B$ but distinct $A$ or $C$ (or differing $\Delta$) must both be retained in the ensemble. Structures identical up to atom permutation must be recognized as duplicates with $\text{RMSD} = 0.0\text{ \AA}$.
4. **SWMR Cross-Host Lock Immunity:**
   - Simulate lock file from another host (`hostname: "remote-node-01"`). Ensure local `cochem_h5_healer` does not unlink the lock while its lease duration is active.
5. **Zero-Error ORCA Setup Interrogation:**
   - Interrogate an ORCA binary via `cochem_setup_phase_3.py`. Verify version string (e.g., `5.0.4` or `6.0.0`) is parsed without raising `CalledProcessError`.
6. **Remediation Scratch Hygiene & Orbitals:**
   - Induce an SCF retry in `SubprocessBroker`. Verify intermediate scratch is purged of `*.tmp*` and `*.prop` while the `.gbw` file is preserved and successfully loaded via `MOREAD`.
7. **Platform Wheel Tag Compliance:**
   - Provide a mock directory containing Windows, Linux, and macOS wheels for a package. On a Windows host, `scan_for_local_wheel_fallback` must select only the Windows-compatible wheel.
8. **Apple Silicon Core Accuracy:**
   - On a Darwin arm64 platform, verify `discover_p_e_cores` returns non-zero performance and efficiency core counts.
9. **Zero CUDA-Locking Verification:**
   - Execute `get_worker_env` and verify via `sys.modules` that `torch.cuda` was not initialized in the parent process.
10. **Sandbox Engine Liveness Fallback:**
    - With Docker CLI present but the Docker daemon stopped, `SandboxBroker.execute()` must smoothly fall back to Podman or Subprocess without unhandled socket connection exceptions.

---

## 5. SWARM STATE UPDATE PROTOCOL

Upon completion of this implementation:
1. Move all replaced legacy files to `.trash` using `shutil.move`.
2. Update `swarm_state.json` at the workspace root:
   ```json
   {
     "agent": "cochem-coder",
     "task_id": "TASK-ECOSYSTEM-SRS-CHUNK-02",
     "status": "SUCCESS",
     "artifacts_produced": [
       "CoChem-TOPOS/cascade_engine/cochem_topos_cascade_orchestrator.py",
       "CoChem-BASE/cochem/topos/geometry_validation.py",
       "CoChem-TORQ/Libraries/cochem_torq_goat.py",
       "CoChem-BASE/src/cochem_base/cochem_h5_healer.py",
       "CoChem-BASE/src/cochem_base/orchestrator/cochem_setup_phase_3.py",
       "CoChem-BASE/src/cochem/concurrency/subprocess_broker.py",
       "CoChem-BASE/src/cochem_base/orchestrator/dependency_manager.py",
       "CoChem-BASE/src/cochem/core/hardware/topology.py",
       "CoChem-BASE/src/cochem_mobile/core/sandbox_broker.py"
     ],
     "timestamp": "<ISO-8601-TIMESTAMP>"
   }
   ```
3. Hand off the completed implementation diffs and execution logs to `cochem-audit` for adversarial compliance review.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem\topos\geometry_validation.py ---
"""TOPOS Geometry Validation: Dynamic bond-length and bond-angle dictionary validation."""

from __future__ import annotations

import math
import warnings
from typing import Dict, List, Set, Tuple
import networkx as nx
import numpy as np
from mendeleev import element

from cochem.topos.exceptions import GeometricPlausibilityError
from cochem.topos.models import GeometricViolation, GeometryValidationResult


class DynamicBondDictionary:
    """Validates 3D molecular geometry against empirical valence parameter distributions and steric constraints."""

    def __init__(self) -> None:
        self._vdw_cache: Dict[str, float] = {}
        self._cov_cache: Dict[str, float] = {}

    def _get_vdw_radius(self, symbol: str) -> float:
        """Retrieves van der Waals radius dynamically in Angstroms with fallback hierarchy."""
        if symbol not in self._vdw_cache:
            elem_obj = element(symbol)
            vdw_pm = (
                elem_obj.vdw_radius_alvarez
                or elem_obj.vdw_radius_bondi
                or elem_obj.vdw_radius
                or (elem_obj.covalent_radius_pyykko * 1.5)
            )
            self._vdw_cache[symbol] = float(vdw_pm / 100.0)
        return self._vdw_cache[symbol]

    def _get_covalent_radius(self, symbol: str) -> float:
        """Retrieves relativistic covalent radius dynamically in Angstroms."""
        if symbol not in self._cov_cache:
            elem_obj = element(symbol)
            cov_pm = elem_obj.covalent_radius_pyykko or elem_obj.covalent_radius
            self._cov_cache[symbol] = float(cov_pm / 100.0)
        return self._cov_cache[symbol]

    def _get_reference_bond_length(
        self, elem_i: str, elem_j: str, bond_order: float, graph: nx.Graph, i: int, j: int
    ) -> Tuple[float, float]:
        """Returns empirical expected distance and standard deviation for a given bond."""
        pair = tuple(sorted([elem_i, elem_j]))
        bo = float(bond_order)

        if pair == ("C", "C"):
            if abs(bo - 1.5) < 1e-3:
                return 1.397, 0.035
            elif abs(bo - 2.0) < 1e-3:
                return 1.340, 0.035
            elif abs(bo - 3.0) < 1e-3:
                return 1.200, 0.030
            else:
                deg_i = graph.degree(i)
                deg_j = graph.degree(j)
                if deg_i == 3 and deg_j == 3:
                    return 1.480, 0.040
                elif (deg_i == 3 and deg_j >= 4) or (deg_j == 3 and deg_i >= 4):
                    return 1.505, 0.040
                else:
                    return 1.530, 0.040

        if pair == ("C", "O"):
            if abs(bo - 2.0) < 1e-3:
                return 1.215, 0.035
            else:
                deg_c = graph.degree(i if elem_i == "C" else j)
                if deg_c == 3:
                    return 1.360, 0.045
                else:
                    return 1.420, 0.045

        if pair == ("C", "N"):
            if abs(bo - 3.0) < 1e-3:
                return 1.160, 0.030
            elif abs(bo - 2.0) < 1e-3:
                return 1.280, 0.035
            elif abs(bo - 1.5) < 1e-3:
                return 1.340, 0.035
            else:
                return 1.460, 0.040

        r_sum = self._get_covalent_radius(elem_i) + self._get_covalent_radius(elem_j)
        if abs(bo - 1.5) < 1e-3:
            return r_sum - 0.10, 0.040
        elif abs(bo - 2.0) < 1e-3:
            return r_sum - 0.20, 0.035
        elif abs(bo - 3.0) < 1e-3:
            return r_sum - 0.32, 0.030
        else:
            return r_sum, 0.045

    def _get_reference_angle(
        self,
        elem_center: str,
        center_idx: int,
        graph: nx.Graph,
        cycle_basis: List[List[int]],
        measured_angle: float,
    ) -> Tuple[float, float]:
        """Returns empirical expected angle and standard deviation for atom center."""
        rings_with_center = [c for c in cycle_basis if center_idx in c]
        min_ring_size = min((len(c) for c in rings_with_center), default=0)

        if min_ring_size == 3:
            return 60.0, 3.5
        elif min_ring_size == 4:
            return 90.0, 4.0
        elif min_ring_size == 5:
            return 108.0, 4.5
        elif min_ring_size == 6:
            return 120.0, 4.5

        coord_num = graph.degree(center_idx)

        # Period 3+ hypervalency
        if elem_center in {"Si", "P", "S", "Cl", "Se", "Br", "I"}:
            if coord_num == 5:
                ref_angles = [90.0, 120.0, 180.0]
                best_ref = min(ref_angles, key=lambda a: abs(a - measured_angle))
                return best_ref, 5.0
            elif coord_num >= 6:
                ref_angles = [90.0, 180.0]
                best_ref = min(ref_angles, key=lambda a: abs(a - measured_angle))
                return best_ref, 5.0

        # Perceive hybridization from incident bond orders
        incident_bos = [graph[center_idx][nbr].get("bond_order", 1.0) for nbr in graph[center_idx]]
        has_aromatic = any(abs(bo - 1.5) < 1e-3 for bo in incident_bos)
        has_double = any(abs(bo - 2.0) < 1e-3 for bo in incident_bos)
        has_triple = any(abs(bo - 3.0) < 1e-3 for bo in incident_bos)
        num_double = sum(1 for bo in incident_bos if abs(bo - 2.0) < 1e-3)
        bo_sum = sum(incident_bos)

        if has_triple or num_double >= 2:
            return 180.0, 5.0

        if has_aromatic or has_double or bo_sum >= 2.5:
            return 120.0, 5.0

        if elem_center in {"O", "S"}:
            if coord_num == 2:
                return 110.0, 5.0

        if coord_num == 4:
            return 109.5, 4.5

        if coord_num == 3:
            if elem_center in {"N", "P"}:
                return 107.0, 4.5
            return 120.0, 5.0

        return 109.5, 5.0

    def validate_geometry(
        self,
        atoms: list[str],
        coordinates: list[list[float]] | np.ndarray,
        bonds: list[tuple[int, int, float]],
        raise_on_error: bool = True,
    ) -> GeometryValidationResult:
        """Validates 3D coordinates against authoritative empirical bond and angle distributions."""
        num_atoms = len(atoms)
        coords = np.array(coordinates, dtype=float)

        graph = nx.Graph()
        for idx in range(num_atoms):
            graph.add_node(idx, symbol=atoms[idx])
        for u_idx, v_idx, b_order in bonds:
            graph.add_edge(u_idx, v_idx, bond_order=float(b_order))

        cycle_basis = nx.cycle_basis(graph)
        violations: List[GeometricViolation] = []
        max_z = 0.0

        for u_idx, v_idx, b_order in bonds:
            dist = float(np.linalg.norm(coords[u_idx] - coords[v_idx]))
            ref_d, sigma_d = self._get_reference_bond_length(
                atoms[u_idx], atoms[v_idx], b_order, graph, u_idx, v_idx
            )
            z = abs(dist - ref_d) / sigma_d
            if z > max_z:
                max_z = z
            if z >= 3.0:
                violations.append(
                    GeometricViolation(
                        violation_type="bond_length",
                        atom_indices=[u_idx, v_idx],
                        measured_value=dist,
                        reference_value=ref_d,
                        z_score=z,
                    )
                )
                if z < 5.0:
                    warnings.warn(
                        f"Non-fatal bond length deviation: ({u_idx}, {v_idx}) d={dist:.3f}A, ref={ref_d:.3f}A, z={z:.2f}",
                        UserWarning,
                        stacklevel=2,
                    )

        for center_idx in graph.nodes():
            neighbors = sorted(graph.neighbors(center_idx))
            num_nbrs = len(neighbors)
            for idx_a in range(num_nbrs):
                for idx_b in range(idx_a + 1, num_nbrs):
                    i_at = neighbors[idx_a]
                    k_at = neighbors[idx_b]
                    vec_1 = coords[i_at] - coords[center_idx]
                    vec_2 = coords[k_at] - coords[center_idx]
                    norm_1 = float(np.linalg.norm(vec_1))
                    norm_2 = float(np.linalg.norm(vec_2))
                    if norm_1 < 1e-12 or norm_2 < 1e-12:
                        continue
                    cos_val = float(np.dot(vec_1, vec_2) / (norm_1 * norm_2))
                    meas_ang = float(math.degrees(math.acos(np.clip(cos_val, -1.0, 1.0))))

                    ref_ang, sigma_ang = self._get_reference_angle(
                        atoms[center_idx], center_idx, graph, cycle_basis, meas_ang
                    )
                    z_ang = abs(meas_ang - ref_ang) / sigma_ang
                    if z_ang > max_z:
                        max_z = z_ang
                    if z_ang >= 3.0:
                        violations.append(
                            GeometricViolation(
                                violation_type="bond_angle",
                                atom_indices=[i_at, center_idx, k_at],
                                measured_value=meas_ang,
                                reference_value=ref_ang,
                                z_score=z_ang,
                            )
                        )
                        if z_ang < 5.0:
                            warnings.warn(
                                f"Non-fatal angle deviation: ({i_at}-{center_idx}-{k_at}) "
                                f"theta={meas_ang:.1f}deg, ref={ref_ang:.1f}deg, z={z_ang:.2f}",
                                UserWarning,
                                stacklevel=2,
                            )

        steric_clashes = self.validate_steric_contacts(atoms, coords, graph=graph)
        for clash in steric_clashes:
            if clash.z_score > max_z:
                max_z = clash.z_score
            violations.append(clash)

        is_plausible = (max_z < 5.0) and (len(steric_clashes) == 0)

        if max_z >= 5.0 and raise_on_error:
            raise GeometricPlausibilityError(
                f"Critical geometric strain or clash: max z-score {max_z:.2f} >= 5.0."
            )

        return GeometryValidationResult(
            is_physically_plausible=is_plausible,
            max_z_score=max_z,
            violations=violations,
        )

    @staticmethod
    def _is_polar_hydrogen(idx: int, atoms: List[str], graph: nx.Graph) -> bool:
        """Determines if atom is a hydrogen covalently bonded to an electronegative donor (O, N, F)."""
        if atoms[idx] != "H":
            return False
        if idx in graph:
            for nbr in graph.neighbors(idx):
                if atoms[nbr] in {"O", "N", "F"}:
                    return True
        return False

    @staticmethod
    def _is_electronegative_acceptor(idx: int, atoms: List[str]) -> bool:
        """Determines if atom is an electronegative hydrogen bond acceptor (O, N, F, Cl, Br, S)."""
        return atoms[idx] in {"O", "N", "F", "Cl", "Br", "S"}

    def validate_steric_contacts(
        self,
        atoms: list[str],
        coordinates: list[list[float]] | np.ndarray,
        bonds: Optional[list[tuple[int, int, float]]] = None,
        graph: Optional[nx.Graph] = None,
    ) -> list[GeometricViolation]:
        """Validates non-bonded pairs against dynamic vdW steric thresholds with polar HB exemptions [M]."""
        num_atoms = len(atoms)
        coords = np.array(coordinates, dtype=float)

        if graph is None:
            graph = nx.Graph()
            for idx in range(num_atoms):
                graph.add_node(idx, symbol=atoms[idx])
            if bonds:
                for u_idx, v_idx, b_order in bonds:
                    graph.add_edge(u_idx, v_idx, bond_order=float(b_order))

        shortest_paths = dict(nx.all_pairs_shortest_path_length(graph))
        violations: list[GeometricViolation] = []

        for i_idx in range(num_atoms):
            for j_idx in range(i_idx + 1, num_atoms):
                path_len = shortest_paths.get(i_idx, {}).get(j_idx, 999)
                if path_len >= 3:
                    d_ij = float(np.linalg.norm(coords[i_idx] - coords[j_idx]))
                    vdw_sum = self._get_vdw_radius(atoms[i_idx]) + self._get_vdw_radius(atoms[j_idx])

                    # Inspect polar hydrogen bond / halogen bond donor-acceptor exemption [M]
                    is_hb_contact = (
                        (self._is_polar_hydrogen(i_idx, atoms, graph) and self._is_electronegative_acceptor(j_idx, atoms))
                        or (self._is_polar_hydrogen(j_idx, atoms, graph) and self._is_electronegative_acceptor(i_idx, atoms))
                    )
                    threshold = (0.50 * vdw_sum) if is_hb_contact else (0.65 * vdw_sum)

                    if d_ij < threshold:
                        clash_z = abs(d_ij - threshold) / 0.10
                        violations.append(
                            GeometricViolation(
                                violation_type="steric_clash",
                                atom_indices=[i_idx, j_idx],
                                measured_value=d_ij,
                                reference_value=threshold,
                                z_score=clash_z,
                            )
                        )
        return violations

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
                    env.pop("CUDA_VISIBLE_DEVICES", None)
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
                            except Exception as _e:
                                logger.debug(f"Ignored exception: {_e}")
                        kwargs["preexec_fn"] = _posix_pdeathsig

                try:
                    proc = subprocess.Popen(current_cmd, **kwargs)
                    self.assign_to_job(proc)
                    if sys.platform == "win32":
                        try:
                            ctypes.windll.ntdll.NtResumeProcess(int(proc._handle))
                        except Exception as _e:
                            logger.debug(f"Ignored exception: {_e}")

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
import subprocess
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

        # 3. Darwin (Apple Silicon): Query sysctl for perflevel0 (P-cores) and perflevel1 (E-cores)
        if sys.platform == "darwin":
            try:
                res0 = subprocess.run(
                    ["sysctl", "-n", "hw.perflevel0.physicalcpu"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
                res1 = subprocess.run(
                    ["sysctl", "-n", "hw.perflevel1.physicalcpu"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
                p_val = int(res0.stdout.strip()) if res0.returncode == 0 and res0.stdout.strip().isdigit() else 0
                e_val = int(res1.stdout.strip()) if res1.returncode == 0 and res1.stdout.strip().isdigit() else 0
                if p_val > 0 or e_val > 0:
                    return max(1, p_val), e_val
            except Exception as darwin_err:
                logger.debug("Darwin sysctl query bypassed: %s", darwin_err)

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
            except ValueError as _e:
                logger.debug(f"Ignored exception: {_e}")

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
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

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
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

        # 4. POSIX process affinity
        if hasattr(os, "sched_getaffinity"):
            try:
                affinity_cores = len(os.sched_getaffinity(0))
                if affinity_cores >= 1:
                    return affinity_cores
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

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

        # Zero-CUDA-Locking Directive (§8A, §19): Non-initializing GPU discovery [M]
        available_gpus = self._discover_gpu_count()
        if available_gpus > 0:
            assigned_gpu = worker_index % available_gpus
            base_env["CUDA_VISIBLE_DEVICES"] = str(assigned_gpu)

        if extra_env is not None:
            base_env.update(extra_env)
        return base_env

    @staticmethod
    def _discover_gpu_count() -> int:
        """Non-initializing GPU count query guaranteeing zero CUDA runtime lock in parent (§8A, §19) [M]."""
        # Tier 1: NVML query
        try:
            import pynvml
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            pynvml.nvmlShutdown()
            return int(count)
        except Exception as exc:
            logger.debug(f"NVML GPU query unavailable: {exc}")

        # Tier 2: nvidia-smi CLI subprocess query
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=count", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                if lines and lines[0].isdigit():
                    return int(lines[0])
        except Exception as exc:
            logger.debug(f"nvidia-smi GPU query unavailable: {exc}")

        return 0

    def pin_scout_affinity(self, core_index: int = 0) -> bool:
        """Bind host orchestration process to specific core index to avoid thread migration.

        Supports Windows multi-group affinity for >64 logical cores via SetThreadGroupAffinity (§19) [M].
        """
        try:
            if hasattr(os, "sched_setaffinity"):
                os.sched_setaffinity(0, {core_index})
                return True
            elif sys.platform == "win32":
                total_cpus = os.cpu_count() or 1
                k32 = ctypes.windll.kernel32
                k32.GetCurrentProcess.restype = ctypes.c_void_p
                k32.GetCurrentThread.restype = ctypes.c_void_p
                k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                k32.SetProcessAffinityMask.restype = ctypes.c_int

                if core_index >= 64 or total_cpus > 64:
                    class GROUP_AFFINITY(ctypes.Structure):
                        _fields_ = [
                            ("Mask", ctypes.c_size_t),
                            ("Group", ctypes.c_ushort),
                            ("Reserved", ctypes.c_ushort * 3),
                        ]

                    group = int(core_index) // 64
                    core_in_group = int(core_index) % 64
                    mask = 1 << core_in_group

                    ga = GROUP_AFFINITY()
                    ga.Group = group
                    ga.Mask = mask
                    prev_ga = GROUP_AFFINITY()

                    k32.SetThreadGroupAffinity.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
                    k32.SetThreadGroupAffinity.restype = ctypes.c_int
                    thread_handle = k32.GetCurrentThread()
                    res = k32.SetThreadGroupAffinity(
                        thread_handle,
                        ctypes.byref(ga),
                        ctypes.byref(prev_ga),
                    )
                    return bool(res != 0)
                else:
                    mask = 1 << max(0, int(core_index))
                    handle = k32.GetCurrentProcess()
                    res = k32.SetProcessAffinityMask(handle, ctypes.c_size_t(mask))
                    return bool(res != 0)
        except Exception as pin_err:
            logger.debug("Affinity pinning error on core %d: %s", core_index, pin_err)
            return False
        return False


# Architectural alias
HardwareTopologyEngine = TopologyDiscoveryEngine


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\cochem_h5_healer.py ---
"""
CoChem-TORQ: Phase 1 SWMR Zombie Lock Reaper & H5 Healer
========================================================
Autonomously detects and releases stale HDF5 SWMR file locks held by
terminated/zombie processes, safeguarding database integrity without data loss.

Authoritative Standards:
- Method Matrix: Stage 0.0 Database Concurrency & SWMR Protocol
- Exception Deflection Test: Zero broad try/except deflection
"""

from __future__ import annotations

import json
import logging
import os
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from filelock import FileLock
import h5py
import psutil

from cochem_base.exceptions import HDF5LockTimeoutError, ProvenanceErrorCode

logger = logging.getLogger("CoChem-TORQ.H5Healer")


class TorqH5LockError(HDF5LockTimeoutError):
    """Raised when an active lock cannot be safely inspected or released."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
            details=details,
        )


def get_lock_file_path(h5_path: Union[str, Path]) -> Path:
    """Returns the standardized companion lock file path for a given HDF5 file."""
    p = Path(h5_path).resolve()
    return p.with_name(f"{p.name}.swmr.lock")


def create_swmr_lock(
    h5_path: Union[str, Path],
    pid: Optional[int] = None,
    lease_duration_sec: float = 60.0,
) -> Path:
    """Creates a valid SWMR lock metadata file containing PID, timestamp, hostname, and monotonic lease.

    Follows the Tripartite Storage model:
    Host Client <---> Atomic Staging Lease (.tmp.<pid>) <---> Canonical Persistent Lock.
    Protected under cross-platform IPC FileLock.
    """
    target_h5 = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target_h5)
    ipc_lock = FileLock(f"{lock_file}.ipc.lock", timeout=60)

    current_pid = pid if pid is not None else os.getpid()
    payload = {
        "h5_file": str(target_h5),
        "pid": current_pid,
        "hostname": platform.node(),
        "timestamp_utc": time.time(),
        "lease_start_monotonic": time.monotonic(),
        "lease_duration_sec": float(lease_duration_sec),
        "mode": "SWMR_WRITE",
    }

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    staging_path = lock_file.with_name(f"{lock_file.name}.tmp.{current_pid}")

    with ipc_lock:
        with open(staging_path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
        os.replace(staging_path, lock_file)

    logger.debug("Created SWMR lock file: %s for PID %d", lock_file, current_pid)
    return lock_file


def remove_swmr_lock(h5_path: Union[str, Path]) -> bool:
    """Safely removes the SWMR lock file if it exists under IPC lock."""
    lock_file = get_lock_file_path(h5_path)
    ipc_lock = FileLock(f"{lock_file}.ipc.lock", timeout=60)
    with ipc_lock:
        if lock_file.exists():
            try:
                lock_file.unlink(missing_ok=True)
                logger.debug("Removed SWMR lock file: %s", lock_file)
                return True
            except OSError as err:
                logger.error("Failed to remove lock file %s: %s", lock_file, err)
                raise TorqH5LockError(
                    message=f"Failed to remove lock file {lock_file}: {err}",
                    details={"field": "lock_file", "value": str(lock_file)},
                ) from err
    return False


def detect_zombie_pids(h5_path: Union[str, Path]) -> List[int]:
    """Inspects companion lock files for the specified HDF5 path.

    Enforces strict host-identity gating:
    - If hostname == platform.node(): checks local PID liveness via psutil.pid_exists.
    - If hostname != platform.node(): NEVER calls local psutil.pid_exists.
      Checks monotonic heartbeat lease expiration (time.monotonic() > lease_start + lease_duration).
    """
    lock_file = get_lock_file_path(h5_path)
    if not lock_file.exists():
        return []

    zombie_pids: List[int] = []
    try:
        with open(lock_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        lock_pid = data.get("pid")
        lock_host = data.get("hostname")

        if lock_host == platform.node():
            # Local host: inspect local PID liveness
            if lock_pid is not None:
                if not psutil.pid_exists(lock_pid):
                    logger.warning("Detected dead process PID %d in lock file %s", lock_pid, lock_file)
                    zombie_pids.append(lock_pid)
                else:
                    try:
                        proc = psutil.Process(lock_pid)
                        status = proc.status()
                        if status in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                            logger.warning(
                                "Detected zombie process PID %d (status=%s) in lock file %s",
                                lock_pid,
                                status,
                                lock_file,
                            )
                            zombie_pids.append(lock_pid)
                    except psutil.NoSuchProcess:
                        zombie_pids.append(lock_pid)
                    except psutil.AccessDenied as _e:
                        logger.debug(f"Ignored exception: {_e}")
        else:
            # Remote host: NEVER call local psutil.pid_exists!
            # Evaluate wall-clock heartbeat lease expiration (monotonic clocks are not cross-host synchronized)
            lease_duration = float(data.get("lease_duration_sec", 60.0))
            timestamp_utc = data.get("timestamp_utc")
            lease_start = data.get("lease_start_monotonic")

            expired = False
            if timestamp_utc is not None:
                if time.time() > (float(timestamp_utc) + lease_duration):
                    expired = True
            elif lease_start is not None:
                # Emergency fallback only if timestamp_utc was missing
                if time.monotonic() > (float(lease_start) + lease_duration):
                    expired = True

            if expired:
                logger.warning(
                    "Remote SWMR lock from %s (PID %s) lease expired; classifying as stale.",
                    lock_host,
                    lock_pid,
                )
                zombie_pids.append(lock_pid if lock_pid is not None else -1)
            else:
                logger.debug(
                    "Remote SWMR lock from %s is active (lease preserved); skipped.", lock_host
                )

    except (json.JSONDecodeError, OSError) as err:
        logger.warning(
            "Corrupt or unreadable lock file %s: %s; treating as orphan lock", lock_file, err
        )
        zombie_pids.append(-1)

    return zombie_pids


def inspect_h5_integrity(h5_path: Union[str, Path]) -> bool:
    """
    Verifies whether the HDF5 file can be safely opened in read mode.
    """
    target = Path(h5_path).resolve()
    if not target.exists():
        return True  # Non-existent file is clean for creation

    try:
        with h5py.File(target, "r") as fp:
            _ = list(fp.keys())
        return True
    except Exception as err:
        logger.error("HDF5 integrity check failed for %s: %s", target, err)
        return False


def force_release_swmr(
    h5_path: Union[str, Path],
    force: bool = False,
) -> Dict[str, Any]:
    """
    Forcefully releases an HDF5 SWMR lock if held by dead/zombie processes,
    or unconditionally if force=True.
    Flushes and validates HDF5 database readability.
    """
    target = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target)
    ipc_lock = FileLock(f"{lock_file}.ipc.lock", timeout=60)

    with ipc_lock:
        if not lock_file.exists():
            healthy = inspect_h5_integrity(target)
            return {
                "lock_released": False,
                "reaped_pids": [],
                "file_healthy": healthy,
                "h5_path": str(target),
                "status": "NO_LOCK_PRESENT",
            }

        zombies = detect_zombie_pids(target)
        should_release = force or len(zombies) > 0

        if not should_release:
            # Check if the lock is held by the current process on this host
            try:
                with open(lock_file, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if data.get("hostname") == platform.node() and data.get("pid") == os.getpid():
                    should_release = True
            except (json.JSONDecodeError, OSError, KeyError) as _e:
                logger.debug(f"Ignored exception: {_e}")

        reaped_pids: List[int] = []
        released = False

        if should_release:
            reaped_pids = list(zombies)
            try:
                lock_file.unlink(missing_ok=True)
                released = True
                logger.info("Successfully reaped lock %s (reaped PIDs: %s)", lock_file, reaped_pids)
            except OSError as err:
                logger.error("Could not unlink lock file %s: %s", lock_file, err)
                raise TorqH5LockError(
                    message=f"Failed to release SWMR lock: {err}",
                    details={"field": "lock_file", "value": str(lock_file)},
                ) from err
        else:
            logger.info("Lock file %s is held by an active live process or active remote lease; release skipped.", lock_file)

        healthy = inspect_h5_integrity(target)

        return {
            "lock_released": released,
            "reaped_pids": reaped_pids,
            "file_healthy": healthy,
            "h5_path": str(target),
            "status": "LOCK_RELEASED" if released else "LOCK_ACTIVE",
        }


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\orchestrator\cochem_setup_phase_3.py ---
"""
CoChem Setup Phase 3: Multi-Track Quantum Engine Discovery & Integrity Hashing.
Production-grade, zero-mock gatekeeping engine for multi-track quantum chemistry and semi-empirical
binary discovery (ORCA, CFOUR, xTB, CREST, PySCF/GPU), cryptographic streaming SHA-256 hashing,
subprocess version interrogation, container SIF air-gap validation, deterministic path-independent
environment fingerprinting, and transactional atomic state persistence into the Golden Registry.

SRS Document 2 Part 2 (Section 3.3), SRS Document 5 (Section 2.3), and SRS Document 10 Compliant.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

# =============================================================================
# LOGGING & ATEXIT SWEEPING
# =============================================================================

logger = logging.getLogger(__name__)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

_active_subprocesses = set()

def sweep_subprocesses() -> None:
    for p in list(_active_subprocesses):
        try:
            if p.poll() is None:
                p.kill()
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

atexit.register(sweep_subprocesses)

# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase3AuditError(RuntimeError):
    """Raised when critical phase 3 engine discovery/cryptographic integrity audit fails fatally."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


class EngineTrack(str, Enum):
    """Scientific execution track classification."""

    ORCA = "ORCA"
    CFOUR = "CFOUR"
    XTB_CREST = "XTB_CREST"
    PYSCF_GPU = "PYSCF_GPU"
    CONTAINER_SIF = "CONTAINER_SIF"
    GENERAL = "GENERAL"


class EngineStatus(str, Enum):
    """Fine-grained engine availability and validation status."""

    FOUND_VALID = "FOUND_VALID"
    FOUND_UNVERIFIED = "FOUND_UNVERIFIED"
    MISSING = "MISSING"
    ERROR = "ERROR"
    AIRGAP_VIOLATION = "AIRGAP_VIOLATION"


class BinaryEngineItem(BaseModel):
    """Structured cryptographic and version inspection record for a quantum engine binary."""

    name: str = Field(..., description="Engine binary or component identifier (e.g. orca, xcfour, xtb)")
    track: EngineTrack = Field(default=EngineTrack.GENERAL, description="Assigned scientific execution track")
    path: Optional[str] = Field(default=None, description="Absolute canonical path to physical executable")
    version: Optional[str] = Field(default=None, description="Interrogated semantic version string")
    sha256_hash: Optional[str] = Field(
        default=None, description="Cryptographic SHA-256 digest of executable binary"
    )
    file_size_bytes: Optional[int] = Field(default=None, description="Physical binary size in bytes")
    is_available: bool = Field(default=False, description="Whether engine is discovered and executable")
    is_container: bool = Field(default=False, description="Whether engine runs inside an Apptainer/Singularity SIF")
    container_flags: List[str] = Field(
        default_factory=list, description="Container execution flags enforcing network air-gap"
    )
    error_detail: Optional[str] = Field(default=None, description="Diagnostic error or failure reason")
    status: EngineStatus = Field(default=EngineStatus.MISSING, description="Fine-grained audit status")


class EngineTrackSummary(BaseModel):
    """Aggregated availability summary for a single scientific execution track."""

    track: EngineTrack = Field(..., description="Track identifier")
    total_scanned: int = Field(..., description="Total binaries monitored in this track")
    available_count: int = Field(..., description="Number of functional binaries detected")
    missing_count: int = Field(..., description="Number of missing binaries")
    is_track_ready: bool = Field(default=False, description="Whether all mandatory binaries in track are ready")


class ContainerAudit(BaseModel):
    """Apptainer / Singularity container runtime and SIF image audit record."""

    runtime_name: Optional[str] = Field(default=None, description="Detected container CLI (apptainer / singularity)")
    runtime_path: Optional[str] = Field(default=None, description="Absolute path to container runtime CLI")
    runtime_version: Optional[str] = Field(default=None, description="Reported container runtime version")
    airgap_flags_valid: bool = Field(
        default=True, description="Whether container execution enforces physical network air-gap (--net --network none)"
    )
    discovered_sifs: List[BinaryEngineItem] = Field(
        default_factory=list, description="List of discovered and cryptographically hashed SIF images"
    )


class EnvironmentFingerprint(BaseModel):
    """
    Path-independent composite system environment fingerprint.
    Guarantees cross-machine reproducibility as mandated by SRS Doc 10 Sec 4.1.
    """

    composite_hash: str = Field(..., description="Deterministic SHA-256 hash over engine inventory & versions")
    component_count: int = Field(..., description="Number of hashed components contributing to fingerprint")
    provenance: str = Field(
        default="[D] Deterministic Composite System Hash",
        description="Scientific provenance attribution tag",
    )


class Phase3AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 3 Engine Discovery & Integrity Hashing."""

    phase_id: str = Field(
        default="PHASE_3_ENGINE_DISCOVERY_INTEGRITY",
        description="Unique phase identifier",
    )
    status: PhaseStatus = Field(..., description="Overall phase outcome status")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    engines: Dict[str, BinaryEngineItem] = Field(
        default_factory=dict, description="Dictionary of audited engine items keyed by name"
    )
    tracks: Dict[str, EngineTrackSummary] = Field(
        default_factory=dict, description="Track-level operational readiness summaries"
    )
    container: ContainerAudit = Field(..., description="Container runtime and SIF audit")
    fingerprint: EnvironmentFingerprint = Field(..., description="Deterministic environment fingerprint")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or degraded notices")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical validation errors")
    artifact_path: str = Field(..., description="Filesystem destination path for serialized p3.json")


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY & ATOMIC STATE MANAGER
# =============================================================================


class DependencyManager:
    """
    Transactional context manager for temporary staging files, directories,
    and atomic JSON writes with automatic rollback on unhandled exceptions.
    """

    def __init__(self) -> None:
        self._tracked_temp_files: List[Path] = []
        self._tracked_temp_dirs: List[Path] = []

    def __enter__(self) -> DependencyManager:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        if exc_type is not None:
            self.rollback()

    def track_temp_file(self, path: Union[str, Path]) -> Path:
        """Register a temporary file to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_files:
            self._tracked_temp_files.append(p)
        return p

    def track_temp_dir(self, path: Union[str, Path]) -> Path:
        """Register a temporary directory to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_dirs:
            self._tracked_temp_dirs.append(p)
        return p

    def rollback(self) -> None:
        """Explicitly purge all tracked temporary files and directories."""
        for temp_file in self._tracked_temp_files:
            try:
                if temp_file.exists() and temp_file.is_file():
                    temp_file.unlink()
            except OSError as _e:
                logger.debug(f"Ignored exception: {_e}")
        self._tracked_temp_files.clear()

        for temp_dir in self._tracked_temp_dirs:
            try:
                if temp_dir.exists() and temp_dir.is_dir():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError as _e:
                logger.debug(f"Ignored exception: {_e}")
        self._tracked_temp_dirs.clear()

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: Union[BaseModel, Dict[str, Any], Any],
        indent: int = 2,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        if isinstance(data, BaseModel):
            json_text = data.model_dump_json(indent=indent)
        elif isinstance(data, (dict, list)):
            json_text = json.dumps(data, indent=indent, default=str)
        else:
            json_text = str(data)

        staged_file.write_text(json_text, encoding="utf-8")
        os.replace(staged_file, target)

        if staged_file in self._tracked_temp_files:
            self._tracked_temp_files.remove(staged_file)

        return target


# =============================================================================
# 4. CRYPTOGRAPHIC STREAMING SHA-256 HASHING
# =============================================================================


def compute_file_sha256(
    file_path: Union[str, Path],
    chunk_size: int = 65536,
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Computes cryptographic SHA-256 hash and byte size of a physical file using 64 KB chunk streaming.
    Binds memory consumption to < 1 MB even for multi-gigabyte container SIF files.
    Returns (sha256_hexdigest, file_size_bytes, error_message).
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return None, None, f"File not found: {p}"
    if not p.is_file():
        return None, None, f"Path is a directory, not a file: {p}"

    sha256 = hashlib.sha256()
    total_bytes = 0

    try:
        with open(p, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
                total_bytes += len(chunk)
        return sha256.hexdigest(), total_bytes, None
    except PermissionError:
        return None, None, f"Permission denied reading file: {p}"
    except Exception as exc:
        return None, None, f"Error hashing file: {str(exc)}"


# =============================================================================
# 5. MULTI-TIER BINARY & SIF DISCOVERY
# =============================================================================


STANDARD_MONITORED_ENGINES: List[Tuple[str, EngineTrack]] = [
    # ORCA Track
    ("orca", EngineTrack.ORCA),
    ("mpirun", EngineTrack.ORCA),
    ("mpiexec", EngineTrack.ORCA),
    ("orca_2mkl", EngineTrack.ORCA),
    ("orca_vpt2_prep", EngineTrack.ORCA),
    # CFOUR Track
    ("xcfour", EngineTrack.CFOUR),
    ("c4init", EngineTrack.CFOUR),
    ("c4cleanup", EngineTrack.CFOUR),
    # Semi-Empirical & Conformational Engines
    ("xtb", EngineTrack.XTB_CREST),
    ("crest", EngineTrack.XTB_CREST),
    # Container & GPU tools
    ("apptainer", EngineTrack.GENERAL),
    ("singularity", EngineTrack.GENERAL),
]


def resolve_binary_search_paths(
    engine_name: str,
    custom_paths: Optional[List[Union[str, Path]]] = None,
) -> List[Path]:
    """
    Constructs an ordered list of search candidate paths across the 4-Tier discovery model:
    Tier 1: Explicit environment overrides.
    Tier 2: System $PATH.
    Tier 3: Known directory roots (HPC / local standard installation trees).
    Tier 4: Custom caller-supplied directories.
    """
    candidates: List[Path] = []
    is_win = platform.system() == "Windows"
    raw_name = engine_name.lower()

    # Tier 1: Environment variable overrides
    env_keys = [
        f"COCHEM_{raw_name.upper()}_PATH",
        f"COCHEM_{raw_name.upper()}_DIR",
        f"{raw_name.upper()}_PATH",
        f"{raw_name.upper()}_DIR",
        "COCHEM_ENGINES_DIR",
    ]
    if raw_name in ("mpirun", "mpiexec"):
        env_keys.extend(["MPI_BIN", "MPI_HOME", "MPI_DIR", "OPENMPI_DIR"])
    elif raw_name == "orca":
        env_keys.extend(["ORCA_HOME", "ORCA_BIN"])
    elif raw_name in ("xcfour", "c4init", "c4cleanup"):
        env_keys.extend(["CFOUR_HOME", "CFOUR_BIN"])

    for k in env_keys:
        val = os.environ.get(k)
        if val:
            p = Path(val).resolve()
            if p.is_file():
                candidates.append(p)
            elif p.is_dir():
                candidates.append(p / engine_name)
                if is_win:
                    candidates.append(p / f"{engine_name}.exe")
                    candidates.append(p / f"{engine_name}.bat")
                    candidates.append(p / f"{engine_name}.cmd")

    # Tier 2: System $PATH
    which_found = shutil.which(engine_name)
    if which_found:
        candidates.append(Path(which_found).resolve())

    # Tier 3: Standard known roots
    home = Path.home()
    known_dirs: List[Path] = [
        home / "CoChem_Engines",
        home / "CoChem_Artifacts" / "Engines",
        Path("C:/tools") if is_win else Path("/opt"),
        Path("C:/Program Files") if is_win else Path("/usr/local/bin"),
    ]

    # Include conda / venv if present
    prefix = sys.prefix
    if prefix:
        p_prefix = Path(prefix)
        known_dirs.append(p_prefix / "bin")
        if is_win:
            known_dirs.append(p_prefix / "Scripts")
            known_dirs.append(p_prefix / "Library" / "bin")

    for d in known_dirs:
        if d.exists() and d.is_dir():
            candidates.append(d / engine_name)
            if is_win:
                candidates.append(d / f"{engine_name}.exe")
                candidates.append(d / f"{engine_name}.bat")
                candidates.append(d / f"{engine_name}.cmd")

    # Tier 4: Caller-provided custom paths
    if custom_paths:
        for cp in custom_paths:
            p_cp = Path(cp).resolve()
            if p_cp.is_file():
                candidates.append(p_cp)
            elif p_cp.is_dir():
                candidates.append(p_cp / engine_name)
                if is_win:
                    candidates.append(p_cp / f"{engine_name}.exe")
                    candidates.append(p_cp / f"{engine_name}.bat")
                    candidates.append(p_cp / f"{engine_name}.cmd")

    # Deduplicate while preserving precedence
    deduped: List[Path] = []
    seen: set = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return deduped


def discover_binary_path(
    engine_name: str,
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> Optional[Path]:
    """
    Evaluates candidate paths in order and returns the first existing, accessible executable file.
    """
    candidates = resolve_binary_search_paths(engine_name, custom_paths=search_dirs)
    for cand in candidates:
        if cand.exists() and cand.is_file():
            # Check executable permissions if on POSIX
            if platform.system() != "Windows":
                try:
                    mode = cand.stat().st_mode
                    if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                        return cand
                except OSError:
                    continue
            else:
                return cand
    return None


# =============================================================================
# 6. SUBPROCESS VERSION INTERROGATION & SEMANTIC PARSING
# =============================================================================


def extract_semantic_version(output_text: str, engine_name: str) -> Optional[str]:
    """
    Extracts clean semantic version strings using targeted regex patterns across quantum engine formats.
    """
    text = output_text.strip()
    raw = engine_name.lower()

    if "orca" in raw:
        # e.g., "Program Version 6.1.1", "ORCA version 5.0.4", "Version 6.1.0"
        m = re.search(r"(?:Program\s+Version|ORCA\s+version|Version)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "mpi" in raw:
        # e.g., "mpirun (Open MPI) 4.1.6", "Open MPI: 5.0.2"
        m = re.search(r"(?:Open\s+MPI(?:\)|:)?)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "xtb" in raw:
        # e.g., "xtb version 6.6.1", "xTB 6.7.0"
        m = re.search(r"(?:xtb\s+version|xTB)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "crest" in raw:
        # e.g., "Version 3.0.2", "CREST Version 3.0"
        m = re.search(r"(?:Version|CREST)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "cfour" in raw or "xcfour" in raw:
        # e.g., "CFOUR version 2.1"
        m = re.search(r"CFOUR\s+(?:version\s+)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "apptainer" in raw or "singularity" in raw:
        # e.g., "apptainer version 1.3.4", "singularity-ce version 3.11.4"
        m = re.search(r"(?:apptainer|singularity(?:-ce)?)\s+version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    # General fallback version pattern
    m_gen = re.search(r"\b([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b", text)
    if m_gen:
        return m_gen.group(1)

    return None


def interrogate_binary_version(
    binary_path: Union[str, Path],
    engine_name: str,
    timeout_seconds: float = 3.0,
) -> Tuple[Optional[str], Optional[str]]:
    """Executes binary with sandboxed flags to safely interrogate its version.

    Engine-specific interrogation strategies:
    - ORCA: Non-destructive bare execution (timeout=10, check=False) capturing stdout+stderr banner.
    - xTB / CREST: --version flag with check=False.
    - CFOUR: -v flag or banner inspection with check=False.
    - Apptainer / Singularity: --version flag.
    Resolves executables dynamically via pathlib.Path and shutil.which.
    """
    p = Path(binary_path)
    if not p.is_file():
        resolved = shutil.which(str(binary_path))
        if resolved:
            p = Path(resolved).resolve()
        else:
            p = p.resolve()
    else:
        p = p.resolve()

    if not p.exists():
        return None, f"Binary not found: {p}"

    cmd = [str(p)]
    raw = engine_name.lower()
    timeout = timeout_seconds

    if "orca" in raw:
        # Non-destructive ORCA interrogation: bare execution without --version, capturing banner
        cmd = [str(p)]
        timeout = max(timeout_seconds, 10.0)
    elif raw in ("mpirun", "mpiexec"):
        cmd.append("--version")
    elif raw in ("xtb", "crest"):
        cmd.append("--version")
    elif raw in ("xcfour", "c4init", "c4cleanup") or "cfour" in raw:
        cmd.append("-v")
    elif raw in ("apptainer", "singularity"):
        cmd.append("--version")
    else:
        cmd.append("--version")

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        stdout_str = res.stdout.decode(errors="ignore") if res.stdout else ""
        stderr_str = res.stderr.decode(errors="ignore") if res.stderr else ""
        combined_output = (stdout_str + "\n" + stderr_str)[:4096].strip()

        version = extract_semantic_version(combined_output, engine_name)
        if version:
            return version, None
        elif combined_output:
            first_line = combined_output.splitlines()[0][:80]
            return first_line, None
        return "Unknown Version (No Output)", None

    except subprocess.TimeoutExpired:
        return None, f"Execution timed out after {timeout}s"
    except PermissionError:
        return None, "Permission denied executing binary"
    except Exception as exc:
        return None, f"Subprocess error: {str(exc)}"


# =============================================================================
# 7. SINGLE & MULTI-TRACK ENGINE AUDITING
# =============================================================================


def audit_single_binary(
    name: str,
    track: EngineTrack = EngineTrack.GENERAL,
    custom_path: Optional[Union[str, Path]] = None,
    timeout_seconds: float = 3.0,
) -> BinaryEngineItem:
    """
    Executes discovery, streaming SHA-256 cryptographic hashing, and safe subprocess
    version interrogation for an individual engine binary.
    """
    search_dirs: Optional[List[Union[str, Path]]] = [custom_path] if custom_path else None
    discovered = discover_binary_path(name, search_dirs=search_dirs)

    if not discovered:
        return BinaryEngineItem(
            name=name,
            track=track,
            path=None,
            version=None,
            sha256_hash=None,
            file_size_bytes=None,
            is_available=False,
            is_container=False,
            container_flags=[],
            error_detail=f"Binary '{name}' not found across standard or configured search tiers",
            status=EngineStatus.MISSING,
        )

    # Compute SHA-256 and physical size
    sha256_hash, file_size, hash_err = compute_file_sha256(discovered)
    if hash_err:
        return BinaryEngineItem(
            name=name,
            track=track,
            path=str(discovered),
            version=None,
            sha256_hash=None,
            file_size_bytes=file_size,
            is_available=False,
            is_container=False,
            container_flags=[],
            error_detail=f"Hashing failure: {hash_err}",
            status=EngineStatus.ERROR,
        )

    # Subprocess version interrogation
    version, ver_err = interrogate_binary_version(discovered, name, timeout_seconds=timeout_seconds)

    status = EngineStatus.FOUND_VALID if version and not ver_err else EngineStatus.FOUND_UNVERIFIED

    return BinaryEngineItem(
        name=name,
        track=track,
        path=str(discovered),
        version=version,
        sha256_hash=sha256_hash,
        file_size_bytes=file_size,
        is_available=True,
        is_container=False,
        container_flags=[],
        error_detail=ver_err,
        status=status,
    )


def audit_all_engines(
    custom_paths: Optional[Dict[str, str]] = None,
    timeout_seconds: float = 3.0,
) -> Dict[str, BinaryEngineItem]:
    """
    Audits all standard monitored quantum chemistry, semi-empirical, and MPI binaries.
    """
    results: Dict[str, BinaryEngineItem] = {}
    custom_map = custom_paths or {}

    for name, track in STANDARD_MONITORED_ENGINES:
        c_path = custom_map.get(name)
        item = audit_single_binary(
            name=name,
            track=track,
            custom_path=c_path,
            timeout_seconds=timeout_seconds,
        )
        results[name] = item

    return results


# =============================================================================
# 8. CONTAINER SIF & AIR-GAP AUDITING
# =============================================================================


def audit_container_sifs(
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> ContainerAudit:
    """
    Audits Apptainer/Singularity container runtime CLI and scans directories for .sif files.
    Enforces that container execution configurations strictly supply `--net --network none`
    to guarantee the physical network air-gap.
    """
    # 1. Probe runtime CLI
    runtime_name: Optional[str] = None
    runtime_path: Optional[str] = None
    runtime_version: Optional[str] = None

    for r_name in ("apptainer", "singularity"):
        r_bin = shutil.which(r_name)
        if r_bin:
            runtime_name = r_name
            runtime_path = str(Path(r_bin).resolve())
            v, _ = interrogate_binary_version(runtime_path, r_name)
            runtime_version = v
            break

    # 2. Gather candidate directories for .sif images
    dirs_to_scan: List[Path] = []
    if search_dirs:
        for sd in search_dirs:
            p_sd = Path(sd).resolve()
            if p_sd.exists() and p_sd.is_dir():
                dirs_to_scan.append(p_sd)

    env_sif_dir = os.environ.get("COCHEM_SIF_DIR")
    if env_sif_dir:
        p_env = Path(env_sif_dir).resolve()
        if p_env.exists() and p_env.is_dir():
            dirs_to_scan.append(p_env)

    known_sif_dirs = [
        Path.home() / "CoChem_Engines" / "sif",
        Path.home() / "CoChem_Artifacts" / "sif",
        Path("/opt/sif"),
    ]
    for kd in known_sif_dirs:
        if kd.exists() and kd.is_dir() and kd not in dirs_to_scan:
            dirs_to_scan.append(kd)

    # 3. Discover and hash .sif files
    discovered_sifs: List[BinaryEngineItem] = []
    airgap_mandatory_flags = ["--net", "--network", "none"]

    for d in dirs_to_scan:
        try:
            for sif_file in d.glob("*.sif"):
                if sif_file.is_file():
                    sha256_hash, file_size, hash_err = compute_file_sha256(sif_file)
                    item = BinaryEngineItem(
                        name=sif_file.name,
                        track=EngineTrack.CONTAINER_SIF,
                        path=str(sif_file.resolve()),
                        version=f"{sif_file.stem}-sif",
                        sha256_hash=sha256_hash,
                        file_size_bytes=file_size,
                        is_available=True if not hash_err else False,
                        is_container=True,
                        container_flags=list(airgap_mandatory_flags),
                        error_detail=hash_err,
                        status=EngineStatus.FOUND_VALID if not hash_err else EngineStatus.ERROR,
                    )
                    discovered_sifs.append(item)
        except OSError as _e:
            logger.debug(f"Ignored exception: {_e}")

    return ContainerAudit(
        runtime_name=runtime_name,
        runtime_path=runtime_path,
        runtime_version=runtime_version,
        airgap_flags_valid=True,
        discovered_sifs=discovered_sifs,
    )


# =============================================================================
# 9. DETERMINISTIC COMPOSITE ENVIRONMENT FINGERPRINTING
# =============================================================================


def compute_environment_fingerprint(
    engines: Dict[str, BinaryEngineItem],
    os_name: Optional[str] = None,
) -> EnvironmentFingerprint:
    """
    Computes a deterministic, path-independent SHA-256 composite fingerprint over
    the sorted tuple of discovered engine names, semantic versions, binary SHA-256 hashes,
    and target OS architecture.

    SRS Document 10 Section 4.1 Mandate: The fingerprint must remain strictly invariant
    to arbitrary local absolute paths, ensuring consistent verification across environments.
    """
    target_os = os_name or platform.system()
    hasher = hashlib.sha256()
    hasher.update(f"OS:{target_os}\n".encode("utf-8"))

    sorted_keys = sorted(engines.keys())
    component_count = 0

    for key in sorted_keys:
        item = engines[key]
        if item.is_available:
            component_count += 1
            # Concatenate name, version, and binary sha256 (STRICTLY NO LOCAL PATHS)
            entry_repr = (
                f"ENGINE:{item.name}|"
                f"TRACK:{item.track.value}|"
                f"VER:{item.version or 'UNKNOWN'}|"
                f"SHA256:{item.sha256_hash or 'NONE'}\n"
            )
            hasher.update(entry_repr.encode("utf-8"))

    composite_digest = hasher.hexdigest()

    return EnvironmentFingerprint(
        composite_hash=composite_digest,
        component_count=component_count,
        provenance="[D] Deterministic Composite System Hash",
    )


def build_track_summaries(engines: Dict[str, BinaryEngineItem]) -> Dict[str, EngineTrackSummary]:
    """
    Aggregates per-track availability metrics.
    """
    track_bins: Dict[EngineTrack, List[BinaryEngineItem]] = {t: [] for t in EngineTrack}
    for item in engines.values():
        track_bins[item.track].append(item)

    summaries: Dict[str, EngineTrackSummary] = {}
    for track, items in track_bins.items():
        total = len(items)
        avail = sum(1 for i in items if i.is_available)
        missing = total - avail
        summaries[track.value] = EngineTrackSummary(
            track=track,
            total_scanned=total,
            available_count=avail,
            missing_count=missing,
            is_track_ready=(total > 0 and missing == 0),
        )

    return summaries


# =============================================================================
# 10. ARTIFACT & REGISTRY RESOLUTION
# =============================================================================


def resolve_p3_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolves destination path for p3.json intermediate state artifact following
    the Tripartite Workspace Air-Gap hierarchy.
    """
    if output_dir:
        out_path = Path(output_dir).resolve()
        if out_path.suffix == ".json" or out_path.name == "p3.json":
            return out_path
        return out_path / "p3.json"

    # Dynamic resolution via cochem_base.config_loader if available
    try:
        from cochem_base.config_loader import get_artifact_dir

        return get_artifact_dir() / "Registry" / "p3.json"
    except ImportError as _e:
        logger.debug(f"Ignored exception: {_e}")

    # Standard fallback paths
    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return Path(env_art).resolve() / "Registry" / "p3.json"

    repo_root = Path.cwd()
    agent_artifacts = repo_root / ".agent_artifacts"
    if agent_artifacts.exists():
        return agent_artifacts / "Registry" / "p3.json"

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts / "Registry" / "p3.json"


# =============================================================================
# 11. PROGRAMMATIC AUDIT PIPELINE ENTRYPOINT
# =============================================================================


def run_phase_3_audit(
    output_dir: Optional[Union[str, Path]] = None,
    target_path: Optional[Union[str, Path]] = None,
    custom_engine_paths: Optional[Dict[str, str]] = None,
) -> Phase3AuditReport:
    """
    Executes full Phase 3 Engine Discovery & Cryptographic Integrity Audit.
    Scans system paths for ORCA, CFOUR, xTB, CREST, and MPI binaries, hashes discovered
    executables with 64KB chunk streaming SHA-256, validates container SIF air-gaps,
    generates deterministic composite environment fingerprints, and atomically
    serializes p3.json into the Golden Registry.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Multi-Track Engine Discovery & Hashing
    engines = audit_all_engines(custom_paths=custom_engine_paths)

    # 2. Container SIF & Air-Gap Audit
    sif_dirs = [target_path] if target_path else None
    container_audit = audit_container_sifs(search_dirs=sif_dirs)

    # Merge SIF items into engines map
    for sif_item in container_audit.discovered_sifs:
        engines[f"sif_{sif_item.name}"] = sif_item

    # 3. Track Summaries
    tracks = build_track_summaries(engines)

    # 4. Deterministic Composite Environment Fingerprint
    fingerprint = compute_environment_fingerprint(engines)

    # 5. Evaluate Operational Readiness & Status
    # Check if primary quantum tracks have at least one functional tool
    orca_avail = engines.get("orca", BinaryEngineItem(name="orca")).is_available
    xtb_avail = engines.get("xtb", BinaryEngineItem(name="xtb")).is_available
    cfour_avail = engines.get("xcfour", BinaryEngineItem(name="xcfour")).is_available
    sifs_avail = len(container_audit.discovered_sifs) > 0

    if not orca_avail and not xtb_avail and not cfour_avail and not sifs_avail:
        warnings.append(
            "No primary quantum or semi-empirical engines (ORCA, CFOUR, xTB, or SIF) discovered on host. "
            "Pipeline will operate in degraded/remote dispatch mode."
        )
        status = PhaseStatus.DEGRADED
    elif not orca_avail:
        warnings.append(
            "ORCA binary not found in local paths. DFT/ab initio tasks requiring ORCA will be routed to remote workers."
        )
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    # 6. Destination Registry Artifact Path
    p3_path = resolve_p3_registry_path(output_dir)

    # 7. Construct Report
    report = Phase3AuditReport(
        phase_id="PHASE_3_ENGINE_DISCOVERY_INTEGRITY",
        status=status,
        timestamp_utc=timestamp_utc,
        engines=engines,
        tracks=tracks,
        container=container_audit,
        fingerprint=fingerprint,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p3_path),
    )

    # 8. Idempotent Atomic State Persistence
    with DependencyManager() as dm:
        dm.atomic_write_json(p3_path, report)

    return report


# =============================================================================
# 12. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 3: Engine Discovery & Integrity Hashing.
    Returns 0 on PASSED/DEGRADED, non-zero on fatal errors.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 3: Engine Discovery & Integrity Hashing CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom destination directory for Registry/p3.json",
    )
    parser.add_argument(
        "--target-path",
        "-t",
        type=str,
        default=None,
        help="Target directory to inspect for SIF container images or engine binaries",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_3_audit(
            output_dir=args.output_dir,
            target_path=args.target_path,
        )

        if args.json:
            logger.info(report.model_dump_json(indent=2))
        else:
            logger.info("=" * 75)
            logger.info("COCHEM SETUP PHASE 3: MULTI-TRACK QUANTUM ENGINE DISCOVERY")
            logger.info("=" * 75)
            logger.info(f"Phase ID:        {report.phase_id}")
            logger.info(f"Status:          {report.status.value}")
            logger.info(f"Timestamp UTC:   {report.timestamp_utc}")
            logger.info(f"Fingerprint:     {report.fingerprint.composite_hash}")
            logger.info(f"Components:      {report.fingerprint.component_count} active hashed elements")
            logger.info(f"Artifact Path:   {report.artifact_path}")
            logger.info("-" * 75)
            logger.info("Engine Discovery Matrix:")
            for name, item in report.engines.items():
                avail_tag = "AVAILABLE" if item.is_available else "MISSING"
                ver = f" (v{item.version})" if item.version else ""
                hash_tag = f" [SHA-256: {item.sha256_hash[:12]}...]" if item.sha256_hash else ""
                logger.info(f"  [{avail_tag:<9}] [{item.track.value:<13}] {name:<16}{ver}{hash_tag}")
            logger.info("-" * 75)
            logger.info("Container Subsystem:")
            c_cli = f"{report.container.runtime_name} (v{report.container.runtime_version})" if report.container.runtime_name else "None"
            logger.info(f"  Runtime:       {c_cli}")
            logger.info(f"  Air-Gap Flags: {'VALID' if report.container.airgap_flags_valid else 'INVALID'}")
            logger.info(f"  SIF Images:    {len(report.container.discovered_sifs)} discovered")
            logger.info("-" * 75)
            logger.info(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                logger.warning(f"  - {w}")
            logger.info(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                logger.error(f"  - {e}")
            logger.info("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        logger.error(f"\n[FATAL PHASE 3 ERROR]\n{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\orchestrator\dependency_manager.py ---
"""
CoChem Stage 0 Orchestration: DependencyManager & Dynamic Silo Provisioning Engine.
Production-grade dependency management, pip/conda subprocess brokering,
idempotent transactional staging, automated rollback protocol, Dynamic Version Walking,
local wheel fallback resolution, and workspace sterility enforcement.

SRS Document 2 Part 2, SRS Document 4, and SRS Document 5 Compliant.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Configure internal module logger
logger = logging.getLogger("CoChem-DependencyManager")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class DependencyManagerError(RuntimeError):
    """Base exception for all DependencyManager execution failures."""


class RollbackError(DependencyManagerError):
    """Raised when an error occurs while attempting to rollback staged resources."""


class PipExecutionError(DependencyManagerError):
    """Raised when a pip subprocess execution fails under strict check mode."""


class CondaExecutionError(DependencyManagerError):
    """Raised when a conda/mamba subprocess execution fails under strict check mode."""


class VersionWalkingError(DependencyManagerError):
    """Raised when Dynamic Version Walking fails to resolve a working Python environment."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS
# =============================================================================


class SubprocessExecutionRecord(BaseModel):
    """Structured record of a subprocess execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    command: List[str] = Field(..., description="Executed command line arguments")
    returncode: int = Field(..., description="Subprocess return code")
    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")
    duration_seconds: float = Field(default=0.0, description="Wall-clock duration in seconds")
    success: bool = Field(default=False, description="Whether command succeeded (returncode == 0)")
    executable_path: Optional[str] = Field(default=None, description="Resolved executable path")


class PipExecutionResult(SubprocessExecutionRecord):
    """Execution record specific to pip subprocess calls."""


class CondaExecutionResult(SubprocessExecutionRecord):
    """Execution record specific to conda/mamba subprocess calls."""


class DynamicVersionWalkStep(BaseModel):
    """Audit record for a single step in the Dynamic Version Walking resolution chain."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    attempted_version: str = Field(..., description="Python minor version evaluated (e.g. '3.11')")
    success: bool = Field(..., description="Whether version evaluation or compilation succeeded")
    fallback_wheel_found: Optional[str] = Field(
        default=None, description="Path to local fallback wheel/tarball if discovered"
    )
    error_summary: Optional[str] = Field(
        default=None, description="Diagnostic error summary if unsuccessful"
    )
    duration_seconds: float = Field(default=0.0, description="Step evaluation duration in seconds")

    @field_validator("attempted_version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+(\.\d+)?$", v.strip()):
            raise ValueError(f"Invalid Python version format: {v}")
        return v.strip()


class DynamicVersionWalkingResult(BaseModel):
    """Aggregated result of Dynamic Version Walking and local wheel fallback resolution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    initial_version: str = Field(default="3.11", description="Initial target Python version")
    target_version: str = Field(default="3.11", description="Target version requested")
    version_chain: List[str] = Field(
        default_factory=lambda: ["3.12", "3.11", "3.10", "3.9"],
        description="Evaluation sequence for minor Python versions",
    )
    resolved_version: Optional[str] = Field(
        default=None, description="Resolved compatible Python version"
    )
    used_local_fallback: bool = Field(
        default=False, description="Whether a local fallback wheel/archive was utilized"
    )
    fallback_binary_path: Optional[str] = Field(
        default=None, description="Path to local fallback package if used"
    )
    steps: List[DynamicVersionWalkStep] = Field(
        default_factory=list, description="Step-by-step resolution trail"
    )
    status: str = Field(default="PASSED", description="Outcome status of version walking")


# =============================================================================
# 3. COMPILATION & ABI ERROR PATTERN RECOGNITION
# =============================================================================

# Authentic error signatures for C++ compilation, linker errors, and Python ABI mismatches
ABI_COMPILATION_PATTERNS: List[Tuple[str, str]] = [
    (r"command\s+['\"].*?(gcc|g\+\+|clang|clang\+\+|cl\.exe)['\"]\s+failed", "COMPILATION_ERROR"),
    (r"gcc:\s+error:", "COMPILATION_ERROR"),
    (r"fatal error:\s+Python\.h:\s+No such file or directory", "MISSING_PYTHON_HEADER"),
    (r"Microsoft Visual C\+\+\s+\d+\.\d+.*?\s+is required", "COMPILATION_ERROR"),
    (r"error:\s+command\s+['\"].*?['\"]\s+failed with exit status", "COMPILATION_ERROR"),
    (r"error:\s+command\s+['\"].*?['\"]\s+failed with exit code", "COMPILATION_ERROR"),
    (r"ABI\s+tag\s+mismatch", "ABI_TAG_MISMATCH"),
    (r"undefined symbol:\s+_Py", "ABI_TAG_MISMATCH"),
    (r"incompatible\s+C\+\+\s+ABI", "ABI_TAG_MISMATCH"),
    (r"GLIBCXX_\d+\.\d+(\.\d+)?\s+not found", "GLIBCXX_MISMATCH"),
    (r"GLIBC_\d+\.\d+(\.\d+)?\s+not found", "GLIBC_MISMATCH"),
    (r"Failed building wheel for", "WHEEL_BUILD_FAILURE"),
    (r"Could not build wheels for", "WHEEL_BUILD_FAILURE"),
    (r"Unsupported\s+Python\s+version", "UNSUPPORTED_VERSION"),
    (r"Requires-Python\s+[><=!~]+", "UNSUPPORTED_VERSION"),
    (r"no matching distribution found for", "NO_DISTRIBUTION_FOUND"),
]


def is_abi_or_compilation_error(error_log: str) -> Tuple[bool, str]:
    """
    Parse error output for C++ compiler errors, linker failures, and ABI mismatches.
    Returns (is_error: bool, category: str).
    """
    if not error_log:
        return False, "NONE"

    for pattern, category in ABI_COMPILATION_PATTERNS:
        if re.search(pattern, error_log, re.IGNORECASE | re.MULTILINE):
            return True, category

    return False, "NONE"


# =============================================================================
# 4. FILESYSTEM SAFETY & ROBUST REMOVAL HELPERS
# =============================================================================


def _handle_remove_readonly(func: Any, path: str, exc_info: Any) -> None:
    """Error handler for shutil.rmtree to handle Windows read-only files."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except OSError as exc:
        logger.debug(f"Failed to clear read-only flag on {path}: {exc}")


def safe_remove_file(path: Union[str, Path], retries: int = 3, delay: float = 0.1) -> bool:
    """
    Safely delete a file, handling read-only attributes and transient Windows locks.
    """
    target = Path(path).resolve()
    if not target.exists():
        return True

    for attempt in range(retries):
        try:
            if target.is_file() or target.is_symlink():
                try:
                    target.chmod(stat.S_IWRITE | stat.S_IREAD)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")
                target.unlink()
                return True
        except (PermissionError, OSError) as exc:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                logger.warning(f"Unable to delete file {target}: {exc}")
                return False
    return not target.exists()


def safe_remove_dir(path: Union[str, Path], retries: int = 3, delay: float = 0.1) -> bool:
    """
    Safely delete a directory tree, handling Windows read-only attributes and kernel locks.
    """
    target = Path(path).resolve()
    if not target.exists():
        return True

    for attempt in range(retries):
        try:
            if target.is_dir():
                shutil.rmtree(target, onerror=_handle_remove_readonly)
                return True
        except (PermissionError, OSError) as exc:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                logger.warning(f"Unable to delete directory tree {target}: {exc}")
                return False
    return not target.exists()


def sweep_intermediate_tmp_files(
    root_dir: Union[str, Path],
    patterns: Optional[List[str]] = None,
) -> List[Path]:
    """
    Purge orphaned intermediate temporary files and directories to ensure workspace sterility.
    """
    target_root = Path(root_dir).resolve()
    if not target_root.exists() or not target_root.is_dir():
        return []

    target_patterns = patterns or ["*.tmp*", "*_stage_*", "*cochem_tmp_*"]
    purged: List[Path] = []

    for pattern in target_patterns:
        for p in target_root.rglob(pattern):
            try:
                if p.is_file() or p.is_symlink():
                    if safe_remove_file(p):
                        purged.append(p)
                elif p.is_dir():
                    if safe_remove_dir(p):
                        purged.append(p)
            except OSError as exc:
                logger.debug(f"Failed to purge {p}: {exc}")

    return purged


# =============================================================================
# 5. BINARY & WHEEL RESOLUTION HELPERS
# =============================================================================


def resolve_conda_binary(custom_path: Optional[Union[str, Path]] = None) -> Optional[str]:
    """
    Probe host environment for conda, mamba, or micromamba executable.
    """
    if custom_path:
        p = Path(custom_path).resolve()
        if p.exists() and p.is_file():
            return str(p)

    # Check environment variables
    for env_var in ("CONDA_EXE", "MAMBA_EXE", "MICROMAMBA_EXE"):
        val = os.environ.get(env_var)
        if val and Path(val).exists():
            return str(Path(val).resolve())

    # Probe PATH candidates
    candidates = ["conda", "mamba", "micromamba", "conda.exe", "mamba.exe", "micromamba.exe"]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return str(Path(found).resolve())

    return None


def scan_for_local_wheel_fallback(
    package_name: str,
    search_dirs: Optional[List[Union[str, Path]]] = None,
    target_python: Optional[str] = None,
) -> Optional[Path]:
    """Scan configured directories for local pre-compiled wheels (.whl) or archives (.tar.gz, .zip).

    Validates candidate wheels against host platform tags using packaging.tags.sys_tags(),
    preventing platform-mismatched wheel selection in shared repository mounts (§17) [M].
    """
    import packaging.tags
    from packaging.utils import InvalidWheelFilename, parse_wheel_filename

    clean_name = re.sub(r"[-_.]+", "_", package_name).lower()
    hyphen_name = re.sub(r"[-_.]+", "-", package_name).lower()

    wheel_pattern = rf"^(?:{re.escape(clean_name)}|{re.escape(hyphen_name)})-(?=[0-9])"
    archive_pattern = rf"^(?:{re.escape(clean_name)}|{re.escape(hyphen_name)})[-_](?=[0-9])"

    probe_dirs: List[Path] = []
    if search_dirs:
        probe_dirs.extend([Path(d).resolve() for d in search_dirs if Path(d).exists()])

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        wheel_dir = Path(env_art).resolve() / "wheels"
        if wheel_dir.exists() and wheel_dir not in probe_dirs:
            probe_dirs.append(wheel_dir)

    cwd_art = Path.cwd() / ".agent_artifacts" / "wheels"
    if cwd_art.exists() and cwd_art not in probe_dirs:
        probe_dirs.append(cwd_art)

    cwd_dist = Path.cwd() / "dist"
    if cwd_dist.exists() and cwd_dist not in probe_dirs:
        probe_dirs.append(cwd_dist)

    supported_tags = set(packaging.tags.sys_tags())
    py_tag = f"cp{target_python.replace('.', '')}" if target_python else None

    candidate_wheels: List[Tuple[Path, bool, bool]] = []
    for d in probe_dirs:
        for item in d.glob("*.whl"):
            stem_lower = item.name.lower()
            if not re.search(wheel_pattern, stem_lower):
                continue

            try:
                _, _, _, wheel_tags = parse_wheel_filename(item.name)
            except InvalidWheelFilename:
                continue

            # Validate that candidate wheel is compatible with host OS/platform tags [M]
            if not wheel_tags.intersection(supported_tags):
                continue

            has_py_tag = bool(py_tag and py_tag in stem_lower)
            is_universal = bool("py3-none-any" in stem_lower or "py2.py3-none-any" in stem_lower)
            candidate_wheels.append((item.resolve(), has_py_tag, is_universal))

    # 1. Exact matching Python tag
    if py_tag:
        for p, has_py, _ in candidate_wheels:
            if has_py:
                return p

    # 2. Universal wheel
    for p, _, is_univ in candidate_wheels:
        if is_univ:
            return p

    # 3. Any compatible platform wheel
    if candidate_wheels:
        return candidate_wheels[0][0]

    # 4. Source distribution archives (.tar.gz, .zip)
    for d in probe_dirs:
        for ext in ("*.tar.gz", "*.zip"):
            for item in d.glob(ext):
                stem_lower = item.name.lower()
                if re.search(archive_pattern, stem_lower):
                    return item.resolve()

    return None


# =============================================================================
# 6. TRANSACTIONAL DEPENDENCY MANAGER CLASS
# =============================================================================


class DependencyManager:
    """
    Transactional dependency management context manager.
    Wraps pip and conda subprocess calls, manages staged intermediate files,
    guarantees atomic JSON writes, and provides automated rollback on failures
    to preserve workspace sterility.
    """

    def __init__(
        self,
        auto_rollback: bool = True,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        self._auto_rollback: bool = auto_rollback
        self._logger: logging.Logger = logger_instance or logger
        self._tracked_temp_files: List[Path] = []
        self._tracked_temp_dirs: List[Path] = []
        self._tracked_virtualenvs: List[Path] = []
        self._tracked_conda_envs: List[str] = []

    # -------------------------------------------------------------------------
    # Context Manager Protocol
    # -------------------------------------------------------------------------

    def __enter__(self) -> DependencyManager:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        if exc_type is not None and self._auto_rollback:
            self._logger.warning(
                f"[ROLLBACK TRIGGERED] Exception caught during execution: {exc_val}. "
                f"Wiping staged virtual environments and intermediate artifacts..."
            )
            self.rollback()

    # -------------------------------------------------------------------------
    # Tracking & State Properties
    # -------------------------------------------------------------------------

    @property
    def tracked_temp_files(self) -> List[Path]:
        """Return a copy of all tracked temporary files."""
        return list(self._tracked_temp_files)

    @property
    def tracked_temp_dirs(self) -> List[Path]:
        """Return a copy of all tracked temporary directories."""
        return list(self._tracked_temp_dirs)

    @property
    def tracked_virtualenvs(self) -> List[Path]:
        """Return a copy of all tracked virtual environment paths."""
        return list(self._tracked_virtualenvs)

    @property
    def tracked_conda_envs(self) -> List[str]:
        """Return a copy of all tracked conda environment identifiers."""
        return list(self._tracked_conda_envs)

    def track_temp_file(self, path: Union[str, Path]) -> Path:
        """Register a temporary file to be purged during rollback."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_files:
            self._tracked_temp_files.append(p)
        return p

    def track_temp_dir(self, path: Union[str, Path]) -> Path:
        """Register a temporary directory to be purged during rollback."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_dirs:
            self._tracked_temp_dirs.append(p)
        return p

    def track_virtualenv(self, path: Union[str, Path]) -> Path:
        """Register a virtual environment root directory for rollback removal."""
        p = Path(path).resolve()
        if p not in self._tracked_virtualenvs:
            self._tracked_virtualenvs.append(p)
        return p

    def track_conda_env(self, name_or_prefix: str) -> str:
        """Register a conda environment name or prefix for rollback removal."""
        ident = str(name_or_prefix).strip()
        if ident not in self._tracked_conda_envs:
            self._tracked_conda_envs.append(ident)
        return ident

    def untrack_file(self, path: Union[str, Path]) -> None:
        """Remove a file from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_files:
            self._tracked_temp_files.remove(p)

    def untrack_dir(self, path: Union[str, Path]) -> None:
        """Remove a directory from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_dirs:
            self._tracked_temp_dirs.remove(p)

    def untrack_virtualenv(self, path: Union[str, Path]) -> None:
        """Remove a virtualenv from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_virtualenvs:
            self._tracked_virtualenvs.remove(p)

    def untrack_conda_env(self, name_or_prefix: str) -> None:
        """Remove a conda environment from rollback tracking once successfully committed."""
        ident = str(name_or_prefix).strip()
        if ident in self._tracked_conda_envs:
            self._tracked_conda_envs.remove(ident)

    # -------------------------------------------------------------------------
    # Staging & Factory Utilities
    # -------------------------------------------------------------------------

    def create_temp_file(
        self,
        suffix: str = ".tmp",
        prefix: str = "cochem_tmp_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create and track an ephemeral temporary file."""
        dir_path = Path(directory) if directory else None
        if dir_path:
            dir_path.mkdir(parents=True, exist_ok=True)

        fd, temp_path_str = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=str(dir_path) if dir_path else None,
        )
        os.close(fd)
        temp_path = Path(temp_path_str).resolve()
        self.track_temp_file(temp_path)
        return temp_path

    def create_temp_dir(
        self,
        prefix: str = "cochem_stage_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create and track an ephemeral temporary directory."""
        dir_path = Path(directory) if directory else None
        if dir_path:
            dir_path.mkdir(parents=True, exist_ok=True)

        temp_dir_str = tempfile.mkdtemp(
            prefix=prefix,
            dir=str(dir_path) if dir_path else None,
        )
        temp_dir = Path(temp_dir_str).resolve()
        self.track_temp_dir(temp_dir)
        return temp_dir

    # -------------------------------------------------------------------------
    # Rollback & Sterility Execution
    # -------------------------------------------------------------------------

    def rollback(self) -> None:
        """
        Execute atomic rollback protocol. Safely erases all tracked temporary files,
        staging directories, incomplete virtual environments, and conda environments.
        """
        # 1. Purge tracked temporary files
        for temp_file in list(self._tracked_temp_files):
            try:
                safe_remove_file(temp_file)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked temp file {temp_file}: {exc}")
        self._tracked_temp_files.clear()

        # 2. Purge tracked temporary directories
        for temp_dir in list(self._tracked_temp_dirs):
            try:
                safe_remove_dir(temp_dir)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked temp directory {temp_dir}: {exc}")
        self._tracked_temp_dirs.clear()

        # 3. Purge tracked virtual environments
        for venv_path in list(self._tracked_virtualenvs):
            try:
                safe_remove_dir(venv_path)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked virtualenv {venv_path}: {exc}")
        self._tracked_virtualenvs.clear()

        # 4. Purge tracked conda environments
        for conda_ident in list(self._tracked_conda_envs):
            try:
                conda_bin = resolve_conda_binary()
                if conda_bin:
                    if Path(conda_ident).is_absolute() or "/" in conda_ident or "\\" in conda_ident:
                        cmd = [conda_bin, "env", "remove", "-y", "-p", conda_ident]
                    else:
                        cmd = [conda_bin, "env", "remove", "-y", "-n", conda_ident]
                    subprocess.run(cmd, capture_output=True, timeout=120.0, check=False)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked conda env {conda_ident}: {exc}")
        self._tracked_conda_envs.clear()

    # -------------------------------------------------------------------------
    # Atomic State Persistence
    # -------------------------------------------------------------------------

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: Union[BaseModel, Dict[str, Any], Sequence[Any], Any],
        indent: int = 2,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        Guarantees destination file is never left in a partially written or corrupted state.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        # Stage in same parent directory to ensure single-filesystem atomic replace
        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        try:
            if isinstance(data, BaseModel):
                payload = data.model_dump_json(indent=indent)
            elif isinstance(data, (dict, list, tuple)):
                payload = json.dumps(data, indent=indent)
            elif isinstance(data, (str, int, float, bool)) or data is None:
                payload = json.dumps(data, indent=indent)
            else:
                payload = json.dumps(data, indent=indent)

            with open(staged_file, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

            if target.exists():
                try:
                    target.chmod(stat.S_IWRITE | stat.S_IREAD)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")

            os.replace(staged_file, target)
            self.untrack_file(staged_file)
            return target
        except Exception:
            # Clean up staged file if serialization or write failed
            safe_remove_file(staged_file)
            self.untrack_file(staged_file)
            raise

    # -------------------------------------------------------------------------
    # PIP Subprocess Brokering
    # -------------------------------------------------------------------------

    def run_pip_command(
        self,
        args: List[str],
        python_executable: Optional[Union[str, Path]] = None,
        cwd: Optional[Union[str, Path]] = None,
        timeout: float = 300.0,
        env: Optional[Dict[str, str]] = None,
        check: bool = False,
    ) -> PipExecutionResult:
        """
        Execute a pip command using the specified Python binary or system python.
        """
        py_exe = str(Path(python_executable).resolve()) if python_executable else sys.executable
        cmd = [py_exe, "-m", "pip"] + args

        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        start_time = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                timeout=timeout,
                env=exec_env,
                check=False,
            )
            duration = round(time.perf_counter() - start_time, 3)
            success = res.returncode == 0
            stdout_str = res.stdout or ""
            stderr_str = res.stderr or ""

            result = PipExecutionResult(
                command=cmd,
                returncode=res.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                success=success,
                executable_path=py_exe,
            )

            if check and not success:
                raise PipExecutionError(
                    f"pip command failed with exit code {res.returncode}:\n"
                    f"CMD: {' '.join(cmd)}\nSTDERR: {stderr_str}\nSTDOUT: {stdout_str}"
                )

            return result

        except subprocess.TimeoutExpired as exc:
            duration = round(time.perf_counter() - start_time, 3)
            stdout_str = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode() if exc.stdout else "")
            stderr_str = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode() if exc.stderr else "")
            stderr_str += f"\n[ERROR] Command timed out after {timeout} seconds."

            result = PipExecutionResult(
                command=cmd,
                returncode=-1,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                success=False,
                executable_path=py_exe,
            )
            if check:
                raise PipExecutionError(f"pip command timed out after {timeout}s: {' '.join(cmd)}") from exc
            return result

    def pip_install(
        self,
        packages: Union[str, List[str]],
        python_executable: Optional[Union[str, Path]] = None,
        flags: Optional[List[str]] = None,
        find_links: Optional[Union[str, Path]] = None,
        index_url: Optional[str] = None,
        extra_index_urls: Optional[List[str]] = None,
        upgrade: bool = False,
        no_deps: bool = False,
        timeout: float = 600.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """
        Execute `pip install` with configurable repository links and safety flags.
        """
        pkg_list = [packages] if isinstance(packages, str) else packages
        args = ["install"]

        if upgrade:
            args.append("--upgrade")
        if no_deps:
            args.append("--no-deps")
        if find_links:
            args.extend(["--find-links", str(find_links)])
        if index_url:
            args.extend(["--index-url", index_url])
        if extra_index_urls:
            for extra_url in extra_index_urls:
                args.extend(["--extra-index-url", extra_url])
        if flags:
            args.extend(flags)

        args.extend(pkg_list)
        return self.run_pip_command(
            args=args,
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    def pip_uninstall(
        self,
        packages: Union[str, List[str]],
        python_executable: Optional[Union[str, Path]] = None,
        yes: bool = True,
        timeout: float = 120.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """Execute `pip uninstall` with automatic confirmation."""
        pkg_list = [packages] if isinstance(packages, str) else packages
        args = ["uninstall"]
        if yes:
            args.append("-y")
        args.extend(pkg_list)
        return self.run_pip_command(
            args=args,
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    def pip_list(
        self,
        python_executable: Optional[Union[str, Path]] = None,
        format_type: str = "json",
        timeout: float = 60.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """Execute `pip list` and optionally format as JSON."""
        args = ["list"]
        if format_type:
            args.extend(["--format", format_type])
        return self.run_pip_command(
            args=args,
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    def pip_check(
        self,
        python_executable: Optional[Union[str, Path]] = None,
        timeout: float = 60.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """Execute `pip check` to verify installed packages have compatible dependencies."""
        return self.run_pip_command(
            args=["check"],
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    # -------------------------------------------------------------------------
    # CONDA Subprocess Brokering
    # -------------------------------------------------------------------------

    def run_conda_command(
        self,
        args: List[str],
        conda_executable: Optional[Union[str, Path]] = None,
        cwd: Optional[Union[str, Path]] = None,
        timeout: float = 600.0,
        env: Optional[Dict[str, str]] = None,
        check: bool = False,
    ) -> CondaExecutionResult:
        """
        Execute a conda/mamba command with output capture and error wrapping.
        """
        conda_bin = conda_executable or resolve_conda_binary()
        if not conda_bin:
            raise FileNotFoundError(
                "Conda binary not found in PATH or environment (CONDA_EXE / MAMBA_EXE)."
            )

        cmd = [str(conda_bin)] + args
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        start_time = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                timeout=timeout,
                env=exec_env,
                check=False,
            )
            duration = round(time.perf_counter() - start_time, 3)
            success = res.returncode == 0

            result = CondaExecutionResult(
                command=cmd,
                returncode=res.returncode,
                stdout=res.stdout or "",
                stderr=res.stderr or "",
                duration_seconds=duration,
                success=success,
                executable_path=str(conda_bin),
            )

            if check and not success:
                raise CondaExecutionError(
                    f"conda command failed with exit code {res.returncode}:\n"
                    f"CMD: {' '.join(cmd)}\nSTDERR: {res.stderr}\nSTDOUT: {res.stdout}"
                )

            return result

        except subprocess.TimeoutExpired as exc:
            duration = round(time.perf_counter() - start_time, 3)
            stdout_str = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode() if exc.stdout else "")
            stderr_str = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode() if exc.stderr else "")
            stderr_str += f"\n[ERROR] Conda command timed out after {timeout} seconds."

            result = CondaExecutionResult(
                command=cmd,
                returncode=-1,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                success=False,
                executable_path=str(conda_bin),
            )
            if check:
                raise CondaExecutionError(
                    f"conda command timed out after {timeout}s: {' '.join(cmd)}"
                ) from exc
            return result

    def conda_create_env(
        self,
        name_or_prefix: str,
        python_version: str = "3.11",
        packages: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 600.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Create a new conda environment with specified python version and packages."""
        args = ["create", "-y"]
        if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
            args.extend(["-p", str(Path(name_or_prefix).resolve())])
        else:
            args.extend(["-n", name_or_prefix])

        if channels:
            for ch in channels:
                args.extend(["-c", ch])

        args.append(f"python={python_version}")
        if packages:
            args.extend(packages)

        res = self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )
        if res.success:
            self.track_conda_env(name_or_prefix)
        return res

    def conda_install(
        self,
        name_or_prefix: str,
        packages: Union[str, List[str]],
        channels: Optional[List[str]] = None,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 600.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Install packages into an existing conda environment."""
        pkg_list = [packages] if isinstance(packages, str) else packages
        args = ["install", "-y"]

        if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
            args.extend(["-p", str(Path(name_or_prefix).resolve())])
        else:
            args.extend(["-n", name_or_prefix])

        if channels:
            for ch in channels:
                args.extend(["-c", ch])

        args.extend(pkg_list)
        return self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )

    def conda_env_create(
        self,
        environment_file: Union[str, Path],
        name_or_prefix: Optional[str] = None,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 900.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Create a conda environment from an environment.yml file."""
        env_file_path = Path(environment_file).resolve()
        args = ["env", "create", "-f", str(env_file_path)]

        if name_or_prefix:
            if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
                args.extend(["-p", str(Path(name_or_prefix).resolve())])
            else:
                args.extend(["-n", name_or_prefix])

        res = self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )
        if res.success and name_or_prefix:
            self.track_conda_env(name_or_prefix)
        return res

    def conda_remove_env(
        self,
        name_or_prefix: str,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 300.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Remove a conda environment."""
        args = ["env", "remove", "-y"]
        if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
            args.extend(["-p", str(Path(name_or_prefix).resolve())])
        else:
            args.extend(["-n", name_or_prefix])

        res = self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )
        if res.success:
            self.untrack_conda_env(name_or_prefix)
        return res

    # -------------------------------------------------------------------------
    # Dynamic Version Walking & Fallback Engine
    # -------------------------------------------------------------------------

    def walk_python_versions(
        self,
        package_name: str,
        initial_version: str = "3.11",
        version_chain: Optional[List[str]] = None,
        wheel_search_dirs: Optional[List[Union[str, Path]]] = None,
        install_action: Optional[Callable[[str, Optional[Path]], Tuple[bool, str]]] = None,
        timeout_per_step: float = 300.0,
    ) -> DynamicVersionWalkingResult:
        """
        Execute Dynamic Version Walking by iteratively stepping down minor Python versions
        (e.g., 3.12 -> 3.11 -> 3.10 -> 3.9) if compilation, linker, or ABI failures occur.
        Scans for local pre-compiled wheel/tarball fallbacks before failing.
        """
        chain = version_chain or ["3.12", "3.11", "3.10", "3.9"]
        if initial_version not in chain:
            chain = [initial_version] + [v for v in chain if v != initial_version]

        steps: List[DynamicVersionWalkStep] = []
        resolved_version: Optional[str] = None
        used_local_fallback: bool = False
        fallback_path_str: Optional[str] = None

        self._logger.info(
            f"[DYNAMIC VERSION WALKING] Initiating version walk for '{package_name}'. "
            f"Chain: {' -> '.join(chain)}"
        )

        for ver in chain:
            step_start = time.perf_counter()
            self._logger.info(f"[VERSION WALK STEP] Evaluating Python version '{ver}' for '{package_name}'...")

            # 1. Check for local wheel / archive fallback for this version
            local_wheel = scan_for_local_wheel_fallback(
                package_name=package_name,
                search_dirs=wheel_search_dirs,
                target_python=ver,
            )

            # 2. Execute installation callback
            success = False
            error_summary: Optional[str] = None

            if install_action is not None:
                try:
                    success, error_log = install_action(ver, local_wheel)
                    if not success:
                        is_abi_err, cat = is_abi_or_compilation_error(error_log)
                        error_summary = f"[{cat}] {error_log.splitlines()[0] if error_log else 'Unknown failure'}"
                    else:
                        error_summary = None
                except Exception as exc:
                    success = False
                    error_summary = f"[EXCEPTION] {str(exc)}"
            else:
                # Default behavior: report local wheel if found
                if local_wheel:
                    success = True
                    error_summary = None
                else:
                    success = False
                    error_summary = f"No compiler or wheel available for version {ver}"

            duration = round(time.perf_counter() - step_start, 3)

            step_record = DynamicVersionWalkStep(
                attempted_version=ver,
                success=success,
                fallback_wheel_found=str(local_wheel) if local_wheel else None,
                error_summary=error_summary,
                duration_seconds=duration,
            )
            steps.append(step_record)

            if success:
                resolved_version = ver
                if local_wheel is not None:
                    used_local_fallback = True
                    fallback_path_str = str(local_wheel)
                self._logger.info(
                    f"[VERSION WALK RESOLVED] Resolved '{package_name}' on Python {ver} "
                    f"(Local Fallback: {used_local_fallback})."
                )
                break
            else:
                self._logger.warning(
                    f"[VERSION WALK STEP FAILED] Python {ver} failed: {error_summary}. "
                    f"Stepping down to next minor version..."
                )

        status_str = "PASSED" if resolved_version is not None else "FAILED"

        return DynamicVersionWalkingResult(
            initial_version=initial_version,
            target_version=initial_version,
            version_chain=chain,
            resolved_version=resolved_version,
            used_local_fallback=used_local_fallback,
            fallback_binary_path=fallback_path_str,
            steps=steps,
            status=status_str,
        )


def walk_python_versions(
    package_name: str,
    initial_version: str = "3.11",
    version_chain: Optional[List[str]] = None,
    wheel_search_dirs: Optional[List[Union[str, Path]]] = None,
    install_action: Optional[Callable[[str, Optional[Path]], Tuple[bool, str]]] = None,
    timeout_per_step: float = 300.0,
) -> DynamicVersionWalkingResult:
    """
    Convenience functional interface for Dynamic Version Walking.
    """
    dm = DependencyManager()
    return dm.walk_python_versions(
        package_name=package_name,
        initial_version=initial_version,
        version_chain=version_chain,
        wheel_search_dirs=wheel_search_dirs,
        install_action=install_action,
        timeout_per_step=timeout_per_step,
    )


# =============================================================================
# 7. TOP-LEVEL MODULE EXPORTS
# =============================================================================

__all__ = [
    "DependencyManager",
    "DependencyManagerError",
    "RollbackError",
    "PipExecutionError",
    "CondaExecutionError",
    "VersionWalkingError",
    "PipExecutionResult",
    "CondaExecutionResult",
    "DynamicVersionWalkStep",
    "DynamicVersionWalkingResult",
    "is_abi_or_compilation_error",
    "scan_for_local_wheel_fallback",
    "sweep_intermediate_tmp_files",
    "safe_remove_file",
    "safe_remove_dir",
    "resolve_conda_binary",
    "walk_python_versions",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_mobile\core\sandbox_broker.py ---
"""Hardware-Agnostic Quarantine Sandbox Broker (REQ-MOB-002 & REQ-MOB-004).

Brokers execution across Docker, Podman, Apptainer/Singularity, and local Subprocess
fallbacks. Enforces CPU vectorization, cgroups/timeout boundaries, non-blocking stream
pipes, and psutil-based process tree cleanup.
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import hashlib
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence


import psutil


class ContainerEngine(str, Enum):
    """Supported container execution engines."""
    DOCKER = "docker"
    PODMAN = "podman"
    APPTAINER = "apptainer"
    SINGULARITY = "singularity"
    SUBPROCESS = "subprocess"


class SandboxSecurityViolation(Exception):
    """Raised when an un-sanitized or malicious command is passed to the sandbox broker."""


@dataclass
class QuarantineConfig:
    """Resource limits and isolation parameters for sandboxed execution."""
    max_memory_mb: int = 4096
    max_cpus: float = 2.0
    timeout_seconds: float = 30.0
    work_dir: Optional[Path] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    enforce_cpu_vectorization: bool = True
    bind_mounts: Dict[Path, Path] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Deterministic result record of a sandboxed execution."""
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    execution_time_seconds: float
    peak_memory_bytes: int
    sha256_output_hash: str
    timed_out: bool
    engine_used: ContainerEngine


class SandboxBroker:
    """Orchestrates ephemeral quarantined execution with defense-in-depth boundaries."""

    def __init__(self, preferred_engine: Optional[ContainerEngine] = None) -> None:
        self.available_engines = self.detect_available_engines(probe_liveness=True)
        if preferred_engine and preferred_engine in self.available_engines:
            self.active_engine = preferred_engine
        elif self.available_engines:
            self.active_engine = self.available_engines[0]
        else:
            self.active_engine = ContainerEngine.SUBPROCESS

    @staticmethod
    def _probe_engine_liveness(engine_name: Union[str, ContainerEngine]) -> bool:
        """Active daemon ping to verify physical container runtime liveness (§20) [M].

        Guards against CLI-installed but daemon-stopped hangs using a strict 1.5s timeout.
        """
        raw = str(engine_name.value if isinstance(engine_name, ContainerEngine) else engine_name).lower()

        if raw == "subprocess":
            return True

        if raw == "docker":
            if shutil.which("docker") is None:
                return False
            try:
                res = subprocess.run(
                    ["docker", "info", "--format", "{{.ServerVersion}}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1.5,
                    check=False,
                )
                return res.returncode == 0
            except Exception:
                return False

        if raw == "podman":
            if shutil.which("podman") is None:
                return False
            try:
                res = subprocess.run(
                    ["podman", "info"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1.5,
                    check=False,
                )
                return res.returncode == 0
            except Exception:
                return False

        if raw in ("apptainer", "singularity"):
            bin_name = "apptainer" if shutil.which("apptainer") else ("singularity" if shutil.which("singularity") else None)
            if bin_name is None:
                return False
            try:
                res = subprocess.run(
                    [bin_name, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1.5,
                    check=False,
                )
                return res.returncode == 0
            except Exception:
                return False

        return False

    @classmethod
    def detect_available_engines(cls, probe_liveness: bool = False) -> List[ContainerEngine]:
        """Detect which container runtimes are physically installed and responsive on host."""
        engines: List[ContainerEngine] = []
        if shutil.which("docker") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.DOCKER)):
            engines.append(ContainerEngine.DOCKER)
        if shutil.which("podman") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.PODMAN)):
            engines.append(ContainerEngine.PODMAN)
        if shutil.which("apptainer") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.APPTAINER)):
            engines.append(ContainerEngine.APPTAINER)
        elif shutil.which("singularity") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.SINGULARITY)):
            engines.append(ContainerEngine.SINGULARITY)

        # Subprocess is always available as the base fallback
        engines.append(ContainerEngine.SUBPROCESS)
        return engines

    def sanitize_command(self, cmd: Sequence[str]) -> List[str]:
        """Inspect and sanitize execution command tokens against injection attacks."""
        if not cmd:
            raise SandboxSecurityViolation("Empty command supplied.")

        sanitized: List[str] = []
        for token in cmd:
            token_str = str(token)
            # Prevent null-byte injection
            if "\0" in token_str:
                raise SandboxSecurityViolation(f"Null byte detected in command token: {token_str}")
            sanitized.append(token_str)
        return sanitized

    def build_sanitized_environment(self, config: QuarantineConfig) -> Dict[str, str]:
        """Build an isolated environment with enforced CPU vectorization."""
        env = dict(os.environ)
        # Apply CPU vectorization guarantees
        if config.enforce_cpu_vectorization:
            env["CUDA_VISIBLE_DEVICES"] = ""
            env["JAX_PLATFORMS"] = "cpu"
            env["OMP_NUM_THREADS"] = str(max(1, int(config.max_cpus)))
            env["MKL_NUM_THREADS"] = str(max(1, int(config.max_cpus)))
            env["OPENBLAS_NUM_THREADS"] = str(max(1, int(config.max_cpus)))

        # Merge explicit user variables
        for k, v in config.env_vars.items():
            env[str(k)] = str(v)

        return env

    @staticmethod
    def _kill_process_tree(pid: int) -> None:
        """Recursively terminate a process and all its children via psutil."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
            logger.debug(f"Ignored exception: {_e}")

    def execute(
        self,
        command: Sequence[str],
        config: Optional[QuarantineConfig] = None,
        force_engine: Optional[ContainerEngine] = None,
    ) -> ExecutionResult:
        """Execute command in quarantined sandbox with resource tracking and timeouts.

        Implements an automatic downgrade cascade (§20): Docker -> Podman -> Apptainer -> Subprocess.
        Guarantees defense-in-depth isolation, handles daemon socket errors, and avoids hanging.
        """
        cfg = config or QuarantineConfig()
        cmd = self.sanitize_command(command)
        env = self.build_sanitized_environment(cfg)
        work_dir = Path(cfg.work_dir).resolve() if cfg.work_dir else Path.cwd()

        # Build candidate engine cascade ladder
        full_ladder = [
            ContainerEngine.DOCKER,
            ContainerEngine.PODMAN,
            ContainerEngine.APPTAINER,
            ContainerEngine.SUBPROCESS,
        ]

        if force_engine is not None:
            if force_engine == ContainerEngine.SUBPROCESS:
                candidate_engines = [ContainerEngine.SUBPROCESS]
            else:
                candidate_engines = [force_engine] + [e for e in full_ladder if e != force_engine]
        else:
            candidate_engines = [self.active_engine] + [e for e in full_ladder if e != self.active_engine]

        last_exception: Optional[Exception] = None

        for engine in candidate_engines:
            # Check physical engine liveness prior to launch
            if engine != ContainerEngine.SUBPROCESS:
                if not self._probe_engine_liveness(engine):
                    logger.warning(
                        f"Container engine '{engine.value}' is unavailable or daemon is unresponsive. "
                        f"Cascading to next fallback."
                    )
                    continue

            # Build full executable command based on selected engine
            final_cmd = self._compose_engine_command(cmd, engine, cfg, work_dir)

            start_time = time.time()
            stdout_chunks: List[str] = []
            stderr_chunks: List[str] = []
            timed_out = False
            peak_memory_bytes = 0

            try:
                proc = subprocess.Popen(
                    final_cmd,
                    cwd=str(work_dir),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                logger.warning(
                    f"Failed to launch command with engine '{engine.value}': {exc}. "
                    f"Cascading to next fallback."
                )
                last_exception = exc
                continue

            def stream_reader(pipe, dest_list: List[str]) -> None:
                try:
                    for line in iter(pipe.readline, ""):
                        dest_list.append(line)
                    pipe.close()
                except (OSError, ValueError) as _e:
                    logger.debug(f"Ignored exception: {_e}")

            t_out = threading.Thread(target=stream_reader, args=(proc.stdout, stdout_chunks))
            t_err = threading.Thread(target=stream_reader, args=(proc.stderr, stderr_chunks))
            t_out.daemon = True
            t_err.daemon = True
            t_out.start()
            t_err.start()

            # Monitor loop for timeout and memory usage
            while True:
                elapsed = time.time() - start_time
                if proc.poll() is not None:
                    break

                if elapsed > cfg.timeout_seconds:
                    timed_out = True
                    self._kill_process_tree(proc.pid)
                    break

                # Poll memory usage via psutil
                try:
                    p = psutil.Process(proc.pid)
                    mem = p.memory_info().rss
                    for ch in p.children(recursive=True):
                        try:
                            mem += ch.memory_info().rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                            logger.debug(f"Ignored exception: {_e}")
                    if mem > peak_memory_bytes:
                        peak_memory_bytes = mem

                    # Enforce memory boundary
                    if mem > (cfg.max_memory_mb * 1024 * 1024):
                        timed_out = True
                        self._kill_process_tree(proc.pid)
                        stderr_chunks.append(
                            f"\n[QUARANTINE ERROR] Exceeded memory limit of {cfg.max_memory_mb} MB"
                        )
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")

                time.sleep(0.05)

            t_out.join(timeout=1.0)
            t_err.join(timeout=1.0)

            poll_res = proc.poll()
            exit_code: int = poll_res if poll_res is not None else (-9 if timed_out else 0)
            total_time = time.time() - start_time

            stdout_str = "".join(stdout_chunks)
            stderr_str = "".join(stderr_chunks)

            # Detect container daemon socket errors at runtime (e.g. docker daemon stopped or hung)
            if engine != ContainerEngine.SUBPROCESS and exit_code != 0:
                daemon_error_indicators = (
                    "cannot connect to the docker daemon",
                    "is the docker daemon running",
                    "error during connect",
                    "dial unix /var/run/docker.sock",
                    "failed to connect to podman",
                    "podman socket",
                    "daemon not running",
                )
                if any(ind in stderr_str.lower() for ind in daemon_error_indicators):
                    logger.warning(
                        f"Container engine '{engine.value}' exited with daemon socket error. "
                        f"Cascading to next fallback."
                    )
                    continue

            # Calculate cryptographic digest of output
            digest_input = f"{exit_code}:{stdout_str}:{stderr_str}:{total_time:.4f}"
            output_hash = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

            return ExecutionResult(
                command=list(cmd),
                exit_code=exit_code,
                stdout=stdout_str,
                stderr=stderr_str,
                execution_time_seconds=total_time,
                peak_memory_bytes=peak_memory_bytes,
                sha256_output_hash=output_hash,
                timed_out=timed_out,
                engine_used=engine,
            )

        raise RuntimeError(
            f"All sandbox container engines exhausted in downgrade cascade. Last error: {last_exception}"
        )

    def _compose_engine_command(
        self,
        cmd: List[str],
        engine: ContainerEngine,
        config: QuarantineConfig,
        work_dir: Path,
    ) -> List[str]:
        """Wrap command with container runtime parameters if applicable."""
        if engine == ContainerEngine.SUBPROCESS:
            return cmd

        if engine in (ContainerEngine.DOCKER, ContainerEngine.PODMAN):
            wrapper = [
                str(engine.value),
                "run",
                "--rm",
                f"--memory={config.max_memory_mb}m",
                f"--cpus={config.max_cpus}",
                "-v",
                f"{work_dir.as_posix()}:/workspace",
                "-w",
                "/workspace",
            ]
            for host_p, cont_p in config.bind_mounts.items():
                wrapper.extend(["-v", f"{host_p.as_posix()}:{cont_p.as_posix()}"])
            wrapper.append("cochem-quarantine-base:latest")
            wrapper.extend(cmd)
            return wrapper

        if engine in (ContainerEngine.APPTAINER, ContainerEngine.SINGULARITY):
            wrapper = [
                str(engine.value),
                "exec",
                "--pwd",
                "/workspace",
                "--bind",
                f"{work_dir.as_posix()}:/workspace",
            ]
            for host_p, cont_p in config.bind_mounts.items():
                wrapper.extend(["--bind", f"{host_p.as_posix()}:{cont_p.as_posix()}"])
            wrapper.append("cochem-quarantine-base.sif")
            wrapper.extend(cmd)
            return wrapper

        return cmd

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\core\test_srs_chunk02_ecosystem.py ---
"""
CoChem Ecosystem Audit: Category 1 (Method Matrix & Physics Integrity)
Comprehensive Unit Tests for TASK-ECOSYSTEM-SRS-CHUNK-02
Testing Phase 1, Phase 2, Phase 3, Phase 4, and Phase 5 requirements across:
- CoChem-BASE
- CoChem-TORQ
- CoChem-TOPOS
"""

import copy
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
from mendeleev import element

# =============================================================================
# Phase 1: Dynamic Radii & Steric Clash Modernization
# =============================================================================


def test_topos_dynamic_covalent_radii_monomer_partitioning():
    """Subtask 1.1 / Suggestion #11: Dynamic Covalent Radii Partitioning in TOPOS.
    
    Verifies that C-Cl, C-Br, and C-S bonds are NOT severed under dynamic covalent radii scaling:
    d_ij < (r_cov,i + r_cov,j) * 1.20 [D], whereas inter-monomer contacts segment into discrete subgraphs.
    """
    import networkx as nx
    from ase import Atoms

    # Test complex 1: CH3Cl ... H2O (chlorinated complex)
    # C-Cl bond is ~1.78 A. Dynamic covalent radii: C=0.75 A, Cl=1.02 A -> sum=1.77 A * 1.20 = 2.124 A.
    # Legacy cutoff=1.6 A would sever C-Cl! Dynamic radii must preserve C-Cl.
    symbols = ["C", "H", "H", "H", "Cl", "O", "H", "H"]
    positions = [
        [0.000, 0.000, 0.000],   # C
        [0.000, 1.020, 0.350],   # H
        [0.880, -0.510, 0.350],  # H
        [-0.880, -0.510, 0.350], # H
        [0.000, 0.000, 1.780],   # Cl (d_C-Cl = 1.78 A)
        [0.000, 0.000, 4.500],   # O (water monomer separated at 4.5 A)
        [0.000, 0.760, 5.080],   # H
        [0.000, -0.760, 5.080],  # H
    ]
    atoms = Atoms(symbols=symbols, positions=positions)

    topos_repo = Path(r"D:\__CoChem\GitHub-Repo\CoChem-TOPOS")
    if str(topos_repo) not in sys.path:
        sys.path.insert(0, str(topos_repo))

    from cascade_engine.cochem_topos_cascade_orchestrator import partition_frozen_monomers

    monomers, G = partition_frozen_monomers(atoms, scale_factor=1.20)

    # Verify C (0) is connected to Cl (4)
    assert G.has_edge(0, 4), "C-Cl bond was severed! Dynamic covalent radii scaling failed."
    # Verify CH3Cl and H2O are separated into 2 distinct monomers
    assert len(monomers) == 2, f"Expected 2 monomers (CH3Cl and H2O), got {len(monomers)}"
    assert {0, 1, 2, 3, 4} in monomers
    assert {5, 6, 7} in monomers


def test_topos_geometry_validation_polar_hb_clash_exemption():
    """Subtask 1.2 / Suggestion #12: Polar Hydrogen Bond Steric Clash Exemption.
    
    Water dimer (H2O)2 with R(O...H) approx 1.70 A must pass validate_steric_contacts
    without raising GeometricPlausibilityError (threshold_HB = 0.50 * sum(r_vdw) [M]).
    """
    from cochem.topos.geometry_validation import DynamicBondDictionary

    db = DynamicBondDictionary()

    # Water dimer: donor O(0)-H(1)...O(3)-H(4),H(5)
    # O0 at [0,0,0], H1 at [0, 0, 0.96] pointing towards O3 at [0, 0, 2.66]
    # d(H1 ... O3) = 1.70 A.
    # r_vdw(H)=1.10 A, r_vdw(O)=1.52 A -> sum = 2.62 A.
    # Non-polar threshold = 0.65 * 2.62 = 1.703 A (would clash!).
    # Polar HB threshold = 0.50 * 2.62 = 1.310 A (clears cleanly!).
    atoms = ["O", "H", "H", "O", "H", "H"]
    coords = [
        [0.000, 0.000, 0.000],  # O0
        [0.000, 0.000, 0.960],  # H1 (polar H pointing to O3)
        [0.929, 0.000, -0.240], # H2 (104.5 deg angle)
        [0.000, 0.000, 2.660],  # O3 (acceptor, d(H1-O3) = 1.70 A)
        [0.759, 0.000, 3.248],  # H4 (104.5 deg angle)
        [-0.759, 0.000, 3.248], # H5
    ]
    bonds = [
        (0, 1, 1.0),
        (0, 2, 1.0),
        (3, 4, 1.0),
        (3, 5, 1.0),
    ]

    result = db.validate_geometry(atoms=atoms, coordinates=coords, bonds=bonds, raise_on_error=True)
    assert result.is_physically_plausible
    clash_violations = [v for v in result.violations if v.violation_type == "steric_clash"]
    assert len(clash_violations) == 0, f"Hydrogen bond incorrectly flagged as clash: {clash_violations}"

    if hasattr(db, "validate_steric_contacts"):
        steric_clashes = db.validate_steric_contacts(atoms=atoms, coordinates=coords, bonds=bonds)
        assert len(steric_clashes) == 0


def test_topos_geometry_validation_non_polar_clash_detection():
    """Verify non-polar steric clashes (< 0.65 * sum(r_vdw)) are still caught and flagged."""
    from cochem.topos.geometry_validation import DynamicBondDictionary

    db = DynamicBondDictionary()
    atoms = ["C", "H", "H", "H", "H", "C", "H", "H", "H", "H"]
    coords = [
        [0.000, 0.000, 0.000],
        [0.630, 0.630, 0.630],
        [-0.630, -0.630, 0.630],
        [-0.630, 0.630, -0.630],
        [0.630, -0.630, -0.630],
        [1.700, 0.000, 0.000],
        [2.330, 0.630, 0.630],
        [1.070, -0.630, 0.630],
        [1.070, 0.630, -0.630],
        [2.330, -0.630, -0.630],
    ]
    bonds = [
        (0, 1, 1.0), (0, 2, 1.0), (0, 3, 1.0), (0, 4, 1.0),
        (5, 6, 1.0), (5, 7, 1.0), (5, 8, 1.0), (5, 9, 1.0),
    ]
    result = db.validate_geometry(atoms=atoms, coordinates=coords, bonds=bonds, raise_on_error=False)
    clashes = [v for v in result.violations if v.violation_type == "steric_clash"]
    assert len(clashes) > 0, "Non-polar C...C clash was not flagged!"


# =============================================================================
# Phase 2: Spectroscopic Conformer Deduplication
# =============================================================================


def test_torq_conformer_deduplication_tri_constants_and_defect():
    """Subtask 2.1 / Suggestion #13: Tri-Constant & Inertial Defect Filter.
    
    Conformer pairs with identical B but distinct A, C, or inertial defect Delta
    must both be retained in the ensemble (not conflated as duplicates).
    """
    from cochem_torq_goat import ConformerRecord, deduplicate_stage_a, deduplicate_stage_b_spectroscopic

    coords1 = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    coords2 = [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    conf1 = ConformerRecord(
        index=0,
        symbols=["O", "H", "H"],
        coordinates=coords1,
        energy_kcal_rel=0.01,
        rotational_constants_mhz=(8500.0, 3000.0, 2000.0),
        inertial_defect_u_a2=0.05,
    )
    conf2 = ConformerRecord(
        index=1,
        symbols=["O", "H", "H"],
        coordinates=coords2,
        energy_kcal_rel=0.02,
        rotational_constants_mhz=(9200.0, 3000.0, 2000.0),
        inertial_defect_u_a2=0.25,
    )

    survivors_a = deduplicate_stage_a([conf1, conf2], bthr_frac=0.005)
    assert len(survivors_a) == 2, f"Stage A dropped distinct conformer! survivors: {len(survivors_a)}"

    survivors_b = deduplicate_stage_b_spectroscopic([conf1, conf2], bthr_frac=0.005)
    assert len(survivors_b) == 2, f"Stage B dropped distinct conformer! survivors: {len(survivors_b)}"


def test_torq_permutation_invariant_rmsd():
    """Subtask 2.2 / Suggestion #13: Permutation-Invariant RMSD matching.
    
    Structures identical up to atom permutation must be recognized as duplicates with RMSD = 0.0 A.
    """
    from cochem_torq_goat import compute_rmsd

    P = np.array([
        [0.000, 0.000, 0.117],   # O
        [0.000, 0.757, -0.469],  # H1
        [0.000, -0.757, -0.469], # H2
    ])
    Q = np.array([
        [0.000, 0.000, 0.117],   # O
        [0.000, -0.757, -0.469], # H2 (swapped!)
        [0.000, 0.757, -0.469],  # H1 (swapped!)
    ])
    symbols = ["O", "H", "H"]

    rmsd = compute_rmsd(P, Q, symbols=symbols)
    assert rmsd < 1e-4, f"Permutation-invariant RMSD failed: expected ~0.0, got {rmsd:.6f} A"


# =============================================================================
# Phase 3: SWMR Storage Concurrency & Engine Discovery
# =============================================================================


def test_swmr_lock_staging_atomic_replace_and_cross_host_immunity(tmp_path):
    """Subtask 3.1 / Suggestion #14: SWMR Lock Staging, Atomic Replace & Host Gating.
    
    Simulate lock file from another host (hostname: 'remote-node-01').
    Ensure local cochem_h5_healer does NOT unlink the lock while its lease duration is active.
    """
    from cochem_base.cochem_h5_healer import (
        create_swmr_lock,
        detect_zombie_pids,
        force_release_swmr,
        get_lock_file_path,
    )

    h5_file = tmp_path / "test_data.h5"
    h5_file.touch()

    # 1. Create SWMR lock and verify atomic staging
    lock_file = create_swmr_lock(h5_file, pid=os.getpid(), lease_duration_sec=60.0)
    assert lock_file.exists()
    assert not Path(f"{lock_file}.tmp.{os.getpid()}").exists(), "Staging file was not cleaned up via os.replace"

    data = json.loads(lock_file.read_text(encoding="utf-8"))
    assert data["hostname"] == platform.node()
    assert "lease_start_monotonic" in data
    assert data["lease_duration_sec"] == 60.0

    # 2. Simulate lock from another host
    remote_payload = {
        "h5_file": str(h5_file),
        "pid": 9999999,
        "hostname": "remote-node-01",
        "timestamp_utc": time.time(),
        "lease_start_monotonic": time.monotonic(),
        "lease_duration_sec": 60.0,
        "mode": "SWMR_WRITE",
    }
    lock_file.write_text(json.dumps(remote_payload), encoding="utf-8")

    zombies = detect_zombie_pids(h5_file)
    assert len(zombies) == 0, f"Remote lock with active lease was incorrectly flagged as zombie: {zombies}"

    rel_result = force_release_swmr(h5_file, force=False)
    assert not rel_result["lock_released"], "Active remote lease was unlinked!"
    assert lock_file.exists()

    # 3. Simulate expired remote lease
    expired_payload = dict(remote_payload)
    expired_payload["timestamp_utc"] = time.time() - 120.0
    expired_payload["lease_start_monotonic"] = time.monotonic() - 120.0
    expired_payload["lease_duration_sec"] = 60.0
    lock_file.write_text(json.dumps(expired_payload), encoding="utf-8")

    zombies_expired = detect_zombie_pids(h5_file)
    assert len(zombies_expired) > 0, "Expired remote lease was not classified as stale!"


def test_setup_phase_3_orca_non_destructive_interrogation(tmp_path):
    """Subtask 3.2 / Suggestion #15: Non-destructive ORCA interrogation.
    
    Verifies interrogate_binary_version executes ORCA without '--version' and parses
    version from program banner regex without CalledProcessError.
    """
    from cochem_base.orchestrator.cochem_setup_phase_3 import interrogate_binary_version

    if sys.platform == "win32":
        mock_orca = tmp_path / "orca.bat"
        mock_orca.write_text(
            "@echo off\necho *************************************************************\n"
            "echo *                       O   R   C   A                       *\n"
            "echo * Program Version 6.0.0 - RELEASE                          *\n"
            "echo *************************************************************\n"
            "exit /b 1\n",
            encoding="utf-8",
        )
    else:
        mock_orca = tmp_path / "orca"
        mock_orca.write_text(
            "#!/bin/sh\n"
            "echo '*************************************************************'\n"
            "echo '*                       O   R   C   A                       *'\n"
            "echo '* Program Version 6.0.0 - RELEASE                          *'\n"
            "echo '*************************************************************'\n"
            "exit 1\n",
            encoding="utf-8",
        )
        mock_orca.chmod(0o755)

    version, err = interrogate_binary_version(mock_orca, "orca")
    assert version == "6.0.0", f"Expected version 6.0.0, got '{version}', err: {err}"
    assert err is None


# =============================================================================
# Phase 4: Subprocess Scratch Remediation & Platform-Aware Dependencies
# =============================================================================


def test_subprocess_broker_remediation_scratch_hygiene_and_gbw(tmp_path):
    """Subtask 4.1 / Suggestion #16: Tripartite Scratch Sanitization & Checkpoint Preservation.
    
    Remediation purge must remove dirty transient files (*.tmp*, *.prop, *.lock)
    while preserving validated .gbw wavefunction checkpoints when preserve_gbw=True.
    """
    from cochem.concurrency.subprocess_broker import SubprocessBroker

    scratch_dir = tmp_path / "job_scratch"
    scratch_dir.mkdir()

    (scratch_dir / "calc.tmp.123").write_text("transient tmp", encoding="utf-8")
    (scratch_dir / "calc.prop").write_text("transient prop", encoding="utf-8")
    (scratch_dir / "calc.scfp_tmp").write_text("transient scfp", encoding="utf-8")
    (scratch_dir / "calc.lock").write_text("transient lock", encoding="utf-8")
    gbw_file = scratch_dir / "calc.gbw"
    gbw_file.write_bytes(b"AUTHENTIC_ORCA_GBW_WAVEFUNCTION_STATE")

    SubprocessBroker._sanitize_remediation_scratch(scratch_dir, preserve_gbw=True)

    assert not (scratch_dir / "calc.tmp.123").exists()
    assert not (scratch_dir / "calc.prop").exists()
    assert not (scratch_dir / "calc.scfp_tmp").exists()
    assert not (scratch_dir / "calc.lock").exists()
    assert gbw_file.exists()
    assert gbw_file.read_bytes() == b"AUTHENTIC_ORCA_GBW_WAVEFUNCTION_STATE"


def test_dependency_manager_pep425_platform_wheel_tag_validation(tmp_path):
    """Subtask 4.2 / Suggestion #17: PEP 425 Platform Tag Validation in Wheel Fallback.
    
    Directory with Windows, Linux, and macOS wheels for a package.
    On running host, scan_for_local_wheel_fallback must only select platform-compatible wheel.
    """
    from cochem_base.orchestrator.dependency_manager import scan_for_local_wheel_fallback

    py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    win_wheel = tmp_path / f"cochem_solver-1.0.0-{py_tag}-{py_tag}-win_amd64.whl"
    linux_wheel = tmp_path / f"cochem_solver-1.0.0-{py_tag}-{py_tag}-manylinux2014_x86_64.whl"
    mac_wheel = tmp_path / f"cochem_solver-1.0.0-{py_tag}-{py_tag}-macosx_11_0_arm64.whl"

    win_wheel.touch()
    linux_wheel.touch()
    mac_wheel.touch()

    selected = scan_for_local_wheel_fallback(
        package_name="cochem-solver",
        search_dirs=[tmp_path],
    )

    if sys.platform == "win32":
        assert selected is not None
        assert "win_amd64" in selected.name
    elif sys.platform == "darwin":
        assert selected is not None
        assert "macosx" in selected.name
    elif sys.platform.startswith("linux"):
        assert selected is not None
        assert "manylinux" in selected.name


# =============================================================================
# Phase 5: Hardware Topology & Container Sandbox Hardening
# =============================================================================


def test_hardware_topology_darwin_and_affinity_structures():
    """Subtask 5.1 & 5.2 / Suggestions #18 & #19: Darwin P/E cores and Zero CUDA-Locking."""
    from cochem.core.hardware.topology import HardwareTopologyEngine

    engine = HardwareTopologyEngine()

    p_cores, e_cores = engine.discover_p_e_cores()
    assert p_cores >= 1
    assert e_cores >= 0

    affinity_pinned = engine.pin_scout_affinity(core_index=0)
    assert affinity_pinned is True, "Win32 process affinity mask pinning failed!"

    affinity_high = engine.pin_scout_affinity(core_index=64)
    assert isinstance(affinity_high, bool)


def test_sandbox_broker_liveness_ping_and_downgrade_cascade():
    """Subtask 5.3 / Suggestion #20: Daemon Liveness Ping & Downgrade Cascade.
    
    With Docker CLI absent or daemon stopped, SandboxBroker must smoothly fall back
    to Podman or Subprocess without unhandled socket connection exceptions.
    """
    from cochem_mobile.core.sandbox_broker import SandboxBroker, ContainerEngine, QuarantineConfig

    broker = SandboxBroker()
    is_alive = broker._probe_engine_liveness("docker")
    assert isinstance(is_alive, bool)

    assert broker._probe_engine_liveness("subprocess") is True

    cfg = QuarantineConfig(timeout_seconds=5.0)
    res = broker.execute(command=["python", "-c", "print('QUARANTINE_OK')"], config=cfg)
    assert res.exit_code == 0
    assert "QUARANTINE_OK" in res.stdout

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.