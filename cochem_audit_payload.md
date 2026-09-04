Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260903-061002-brainstorm\.in-progress\Perfected_SRS_Chunk_04_Core_Part_4_prompts.md.
Original prompt:
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 4: Suggestions #31–#40)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §5, §7, §8A, §8A.4, §8C, §9A.5, §16.1, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Storage Air-Gap Architecture (Source $T_{\text{src}}$ immutable read-only, Ephemeral Scratch $T_{\text{scr}}$ isolated, Artifacts $T_{\text{art}}$ read-write cryptographic commitments)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- Dynamic Mendeleev Invariant Mandate (`from mendeleev import element`, zero hardcoded atomic masses, strict $m_i > 0.0$ u physical invariant)
- Non-Blocking GPU Scheduling Directive (Dynamic ordinal selection via `CUDA_VISIBLE_DEVICES`, "no CUDA-locking" host mutex locks, NVIDIA MPS multi-process multiplexing)
- Cross-Platform Concurrency Directive (Standardized `filelock.FileLock` mutual exclusion, `multiprocessing.shared_memory.SharedMemory` RAII lifecycle)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #31 through #40 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical vulnerabilities across configuration ingestion authority, error diagnostics preservation, storage air-gap transaction sequencing, high-throughput potential energy surface (PES) database concurrency, inter-process communication (IPC) framing and memory safety, kernel shared memory lifecycle hygiene, cross-platform distributed network file locking, dynamic physical mass invariants, domain-specific quantum chemical exception routing, and unified namespace architecture with non-blocking GPU hardware dispatching across the 6-Tier Environment Matrix.

Specific targets include eliminating silent configuration fallbacks by introducing fail-fast TOML parsing diagnostics, protecting primary electronic structure convergence exceptions from being masked by secondary operating system cleanup errors during sandbox teardown, decoupling atomic artifact commits from ephemeral scratch file unlinking, eradicating $O(N \cdot M)$ disk I/O thrashing in HDF5 stores via Single-Writer Multiple-Reader (SWMR) synchronization and master queue arbitration, enforcing strict 256 MB payload framing and truncation diagnostics on IPC daemon sockets, implementing RAII and `weakref.finalize` garbage collection for OS shared memory segments, replacing custom `fcntl`/`msvcrt` primitives with standardized cross-platform `filelock.FileLock`, enforcing dynamic positive mass invariants ($m_i > 0.0$ u) via IUPAC/Mendeleev registries while rejecting transuranic null fallbacks, implementing domain-specific physical exceptions (`SpinContaminationError`, `HessianSymmetryError`) to drive autonomous swarm method pivots, and resolving broken core namespaces while eliminating static `device_id=0` GPU thread mutex locking.

Every modification must be accompanied by comprehensive, zero-mock unit and integration tests executing real physical computations, multi-threaded stress tests, OS-level process lifecycles, and genuine disk I/O.

---

## 2. Target Files & Deliverable Manifest

### Core Configuration, Sandbox & Storage Air-Gap Modules
1. `src/cochem/core/config.py` (Suggestion #31)
2. `src/cochem/core/cochem_sandbox.py` (Suggestion #32)
3. `src/cochem/core/airgap_coordinator.py` (Suggestions #32, #33)
4. `src/cochem/core/context.py` (Suggestion #37)

### IPC, Memory & PES Store Modules
5. `src/cochem/core/ipc/serializer.py` (Suggestions #34, #35, #36)
6. `src/cochem_geom/data/pes_store.py` (Suggestion #34)
7. `src/cochem/storage/cochem_core_pes_store.py` (Suggestion #34)
8. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestion #34)

### Physics Ingestors, Schemas & Hardware Dispatch Modules
9. `src/cochem/core/ingestors/protocols.py` (Suggestions #38, #39)
10. `src/cochem/core/mendeleev_invariants.py` (Suggestion #38)
11. `src/cochem_base/core/__init__.py` (Suggestion #40)
12. `src/cochem/runners/cuda_budget.py` (Suggestion #40)
13. `src/cochem/runners/async_process_runner.py` (Suggestion #40)
14. `src/cochem_base/core_engine/cochem_core_mps_orchestrator.py` (Suggestion #40)

### Zero-Mock Test Suite Deliverables
15. `tests/core/test_architecture_part4.py` (Validating Suggestions #31, #32, #33, #37, #40)
16. `tests/core/test_physics_integrity_part4.py` (Validating Suggestions #34, #35, #36, #38, #39)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Deterministic Configuration Parsing & Fail-Fast Authority (Suggestion #31)]
- **File Affected:** `src/cochem/core/config.py` (`_load_toml_file`, lines 146–156)
- **Problem Statement:**
  In `CoChemConfigManager._load_toml_file`, the TOML parsing routine catches all exceptions in a broad `except Exception as err:` block, emits a log warning, and silently returns an empty dictionary `{}`. When a user provides a configuration file (`cochem.toml`) containing syntax errors, formatting defects, or invalid types, the manager silently discards the user configuration and falls back to hardcoded defaults (4 GB RAM, loose convergence thresholds, unconstrained workers). This violates the Stage 0 Authority Rule and Method Matrix v4 §8A, executing expensive calculations outside user-configured physical boundaries and inducing out-of-memory crashes on HPC nodes.
- **Implementation Requirements:**
  1. Define a custom structured exception `ConfigurationParseError(Exception)` in `src/cochem/core/config.py` (and expose it in public re-exports).
  2. Refactor `_load_toml_file(self, path: Path) -> Dict[str, Any]`:
     - If the configuration file does not exist (`not path.exists()`), return `{}` (preserving optional overlay behavior).
     - If the file exists, read and parse it strictly using `tomllib.load(f)`.
     - Explicitly catch `tomllib.TOMLDecodeError` and raise `ConfigurationParseError`:
       ```python
       try:
           with open(path, "rb") as f:
               return tomllib.load(f)
       except tomllib.TOMLDecodeError as err:
           raise ConfigurationParseError(
               f"Fatal TOML syntax error in configuration file '{path.resolve()}' "
               f"at line {err.lineno}, column {err.colno}: {err}"
           ) from err
       except OSError as err:
           raise ConfigurationParseError(
               f"Fatal I/O or permissions error reading configuration file '{path.resolve()}': {err}"
           ) from err
       ```
     - Eradicate the broad `except Exception as err:` block. Swallowing configuration errors is strictly forbidden.
  3. Ensure that callers (`get_workspace_config`, `_load_user_config`, `_load_project_config`) allow `ConfigurationParseError` to propagate cleanly, halting pipeline initialization immediately across all 6 environment tiers before hardware dispatch.

---

### [Task 2: Primary Exception Preservation in Ephemeral Sandbox Teardown (Suggestion #32)]
- **File Affected:** `src/cochem/core/cochem_sandbox.py` (`SandboxContext.__exit__`, lines 69–76) and `src/cochem/core/airgap_coordinator.py`
- **Problem Statement:**
  `SandboxContext.__exit__` unconditionally invokes `self.cleanup()`. When cleanup encounters a transient operating system filesystem error (such as Windows `[WinError 32]` file locking, antivirus indexer collisions, or distributed NFS/Lustre file-handle lock delays after exhausting retries), `cleanup()` re-raises the `OSError`. Under standard Python context manager semantics, an exception escaping `__exit__` supersedes and completely discards any active scientific exception that occurred inside the `with SandboxContext(...)` block (e.g. SCF convergence failure, geometry optimization divergence, or gradient NaN). Autonomous debugging agents receive misleading filesystem permission errors instead of the true quantum chemical telemetry.
- **Implementation Requirements:**
  1. Update `SandboxContext.__exit__` to inspect `exc_type`:
     ```python
     def __exit__(
         self,
         exc_type: Optional[type[BaseException]],
         exc_val: Optional[BaseException],
         exc_tb: Optional[Any],
     ) -> None:
         is_unwinding = exc_type is not None
         try:
             self.cleanup()
         except OSError as cleanup_err:
             if is_unwinding:
                 logger.warning(
                     "Secondary OSError encountered during sandbox cleanup suppressed to preserve "
                     "primary scientific exception: %s (unreclaimed scratch path: %s)",
                     cleanup_err,
                     self.root,
                 )
                 # Allow the primary scientific exception to propagate without masking
                 return None
             raise
     ```
  2. If cleanup fails during exception unwinding, register the un-cleared scratch directory `self.root` with the background `ZombieReaperDaemon` or append to an asynchronous quarantine queue for sweep-up upon process exit.
  3. Ensure that if no primary exception is active (`is_unwinding is False`), cleanup failures still raise cleanly to signal filesystem degradation.

---

### [Task 3: Decoupled Atomic Artifact Publication & Source Tier Immutability (Suggestion #33)]
- **File Affected:** `src/cochem/core/airgap_coordinator.py` (`publish_artifact`, lines 104–146)
- **Problem Statement:**
  In `AirGapCoordinator.publish_artifact()`, post-commit scratch deletion (`source.unlink(missing_ok=True)`) is executed inside the primary publish `try` block alongside `os.replace(temp_dest, dest)`. If `source.unlink()` raises a `PermissionError` (common on Windows when background telemetry handles are still closing), the `except` block triggers rollback logic attempting `temp_dest.unlink()`. However, `temp_dest` was already moved to `dest` via `os.replace()`, so the rollback fails, and the caller is handed an unhandled exception. The destination artifact was already written, hashed, and cryptographically verified via SHA-256, but callers treat the publication as aborted and execute redundant re-computations. In addition, write protections on the Source Tier ($T_{\text{src}}$) are not strictly asserted.
- **Implementation Requirements:**
  1. Strictly decouple the atomic publication commit transaction from scratch cleanup:
     - **Phase 1 (Atomic Commit):** Copy `source` to `temp_dest` within the artifact destination directory, compute SHA-256 digest, and atomically rename `temp_dest` to `dest` using `os.replace(temp_dest, dest)`. If any error occurs during Phase 1, remove `temp_dest` (if it exists) and raise the error.
     - **Phase 2 (Post-Commit Teardown):** Once `os.replace()` succeeds, the artifact is committed. Wrap `source.unlink(missing_ok=True)` in an isolated `try...except OSError as cleanup_err:` block. If unlinking fails, log a warning and register `source` for background sweeping; **never** raise an exception or invalidate the committed publication transaction.
  2. Enforce Source Tier ($T_{\text{src}}$) Immutability:
     - Assert that neither `source_path` nor `relative_dest` attempts to write into or modify the read-only codebase root ($T_{\text{src}}$ / `config.source_root`).
     - If any mutation or target destination falls within `config.source_root`, raise `AirGapViolationError("Source tier (T_src) is strictly immutable and read-only.")`.
  3. Ensure that `publish_artifact()` returns `Tuple[pathlib.Path, Optional[str]]` containing the committed destination path and verified SHA-256 checksum deterministically.

---

### [Task 4: High-Throughput HDF5 SWMR Store & Single-Master Concurrency (Suggestion #34)]
- **Files Affected:** `src/cochem/core/ipc/serializer.py` (`PESStore`, lines 290–360), `src/cochem_geom/data/pes_store.py`, and `src/cochem/storage/cochem_core_pes_store.py`
- **Problem Statement:**
  `PESStore.write_entry()` currently handles persistence by copying the entire existing HDF5 file to a temporary file (`shutil.copyfile(self.file_path, tmp_path)`), appending the new calculation entry, and replacing the target file via `os.replace()`. For multi-point potential energy surface scans and high-throughput conformer generation, copying a multi-gigabyte HDF5 database on every coordinate point incurs $O(N \cdot M)$ disk I/O thrashing, exhausts scratch disk space, and corrupts datasets when concurrent workers overwrite each other's points. Furthermore, POSIX file locks cannot coordinate internal HDF5 B-tree cache pages across independent process address spaces on network filesystems (NFS/Lustre).
- **Implementation Requirements:**
  1. Completely eradicate `shutil.copyfile` and whole-file copy-on-write staging in `PESStore.write_entry`.
  2. Implement single-master writer arbitration and thread-level mutex protection:
     - Add an internal reentrant lock `self._write_lock = threading.RLock()` to serialize library calls within the process.
     - Wrap file access in cross-platform OS locking: `filelock.FileLock(str(self.file_path) + ".lock", timeout=30.0)` targeting node-local scratch storage.
  3. Configure HDF5 in Single-Writer Multiple-Reader (SWMR) mode:
     - Open the store directly with `h5py.File(self.file_path, "a", libver="latest")`.
     - When appending coordinate grids and results, utilize chunked datasets with pre-allocated extensible dimensions (`maxshape=(None, ...)`), compression (`compression="gzip"`, `compression_opts=4`), and Fletcher32 checksums (`fletcher32=True`).
     - Call `h5f.flush()` immediately after writing groups and datasets to commit B-tree metadata to disk, guaranteeing that concurrent readers in SWMR mode (`swmr=True`) observe consistent states.
  4. Implement pre-flight disk capacity verification:
     - Before writing, verify that the filesystem hosting `self.file_path` has at least 100 MB free (`shutil.disk_usage(self.file_path.parent).free >= 100 * 1024 * 1024`). If disk space is exhausted, raise `IOError("Insufficient disk space on target volume for PESStore append")`.

---

### [Task 5: IPC Payload Framing, Bounds Enforcement & Truncation Handling (Suggestion #35)]
- **File Affected:** `src/cochem/core/ipc/serializer.py` (`HMACSocketServer`, lines 206–239)
- **Problem Statement:**
  In `HMACSocketServer._accept_loop`, when an IPC client connection terminates prematurely or drops packets mid-transmission, the condition `if len(buffer) == payload_len:` evaluates to `False`. The loop drops silently through to `conn.close()` without logging an error, raising an exception, or notifying the server. `self._payload_event` is never signaled, causing callers in `get_received_payload()` to hang indefinitely until timeout. In addition, reading the 4-byte payload length header (`payload_len = struct.unpack("!I", len_bytes)[0]`) lacks bounds verification; a malformed or malicious packet specifying a large `payload_len` triggers `bytearray()` allocation up to $2^{32}-1$ bytes, crashing daemons with an unhandled `MemoryError`.
- **Implementation Requirements:**
  1. Define custom IPC exceptions in `src/cochem/core/ipc/serializer.py`:
     ```python
     class IPCPayloadError(Exception):
         """Base exception for IPC payload transmission failures."""
         pass

     class TruncatedPayloadError(IPCPayloadError):
         """Raised when an IPC connection terminates before receiving the full payload."""
         pass

     class OversizedPayloadError(IPCPayloadError):
         """Raised when a transmitted payload header exceeds the safety ceiling."""
         pass
     ```
  2. Enforce a strict maximum payload ceiling constant: `MAX_IPC_PAYLOAD_BYTES = 256 * 1024 * 1024` (256 MB [D]).
  3. In `HMACSocketServer._accept_loop`:
     - Inspect `payload_len`. If `payload_len > MAX_IPC_PAYLOAD_BYTES`:
       - Log an error: `logger.error("IPC payload rejected: size %d exceeds 256 MB ceiling", payload_len)`
       - Set `self._last_error = OversizedPayloadError(f"Payload size {payload_len} exceeds 256 MB limit")`
       - Set `self._payload_event.set()` and close the connection.
     - Stream chunks into `buffer`. If `conn.recv()` returns `b""` (EOF) while `len(buffer) < payload_len`:
       - Log an error: `logger.error("IPC stream truncated: received %d of %d bytes", len(buffer), payload_len)`
       - Set `self._last_error = TruncatedPayloadError(f"Stream truncated: received {len(buffer)} of {payload_len} bytes")`
       - Set `self._payload_event.set()` and close the connection.
  4. In `get_received_payload(self, timeout_sec: float = 5.0) -> Optional[Any]`:
     - If `self._last_error` is set, retrieve and clear the error, raising it directly to the caller so failures are detected immediately rather than timing out.

---

### [Task 6: Cross-Platform SharedMemoryBuffer RAII & Garbage Collection Hooks (Suggestion #36)]
- **File Affected:** `src/cochem/core/ipc/serializer.py` (`SharedMemoryBuffer`, lines 77–128)
- **Problem Statement:**
  `SharedMemoryBuffer` allocates operating system kernel shared memory via `multiprocessing.shared_memory.SharedMemory(create=True, size=total_bytes)`, but lacks a context manager implementation (`__enter__`/`__exit__`) and does not register a `weakref.finalize` garbage collection callback. When an unhandled exception occurs in a worker pipeline between memory allocation and manual `shm.unlink()` calls, the operating system shared memory segments remain orphaned in `/dev/shm` (on Linux) or in the paging system (on Windows). High-throughput conformer clustering jobs rapidly exhaust shared memory, causing subsequent calculations to crash with `FileExistsError` and halting compute nodes.
- **Implementation Requirements:**
  1. Implement RAII context manager semantics on `SharedMemoryBuffer`:
     ```python
     def __enter__(self) -> SharedMemoryBuffer:
         return self

     def __exit__(
         self,
         exc_type: Optional[type[BaseException]],
         exc_val: Optional[BaseException],
         exc_tb: Optional[Any],
     ) -> None:
         self.close()
         self.unlink()
     ```
  2. Implement automatic garbage collection cleanup using `weakref.finalize`:
     - Define a module-level standalone cleanup function `_finalize_shm(name: str) -> None`:
       ```python
       def _finalize_shm(name: str) -> None:
           try:
               s = sm.SharedMemory(name=name)
               s.close()
               s.unlink()
           except (FileNotFoundError, OSError):
               pass
       ```
     - In `SharedMemoryBuffer.__init__` (or when allocated via `from_array`), attach the finalizer:
       `self._finalizer = weakref.finalize(self, _finalize_shm, self.shm.name)`
     - Update `unlink()` to deregister the finalizer cleanly via `self._finalizer.detach()` if already explicitly unlinked.
  3. Ensure full cross-platform compatibility without `/dev/shm` filesystem path assumptions, operating uniformly on Windows, macOS, Linux Debian, Codespaces, and HPC environments.

---

### [Task 7: Centralized Cross-Platform Network File Locking via `filelock` (Suggestion #37)]
- **File Affected:** `src/cochem/core/context.py` (`FileLock`, lines 148–225)
- **Problem Statement:**
  `cochem.core.context.FileLock` maintains legacy, low-level locking wrappers calling `msvcrt.locking` on Windows and `fcntl.flock` on POSIX systems. Standard `fcntl.flock` semantics fail silently or cause split-brain corruptions across distributed network filesystems (NFS, Lustre, GPFS) on HPC clusters. In addition, `self._fd = os.open(...)` is executed before the acquisition loop; if an error occurs or the timeout expires, `_fd` remains unclosed, leaking file descriptors. This violates the project-wide Concurrency Directive: "fcntl eradication, use cross-platform `filelock` package!"
- **Implementation Requirements:**
  1. Completely replace low-level `fcntl.flock` and `msvcrt.locking` in `cochem.core.context.FileLock` with the centralized `filelock.FileLock`:
     - Delegate physical lock management to an internal `filelock.FileLock(str(self.lock_path) + ".lock", timeout=self.timeout_sec)`.
     - Convert all incoming path inputs using `pathlib.Path(lock_path).resolve()`.
  2. Eradicate raw `os.open()`, `os.close()`, and file descriptor tracking (`self._fd`).
  3. Ensure deterministic resource release:
     - Wrap lock acquisitions in clean `try...finally` blocks.
     - On timeout, raise `TimeoutError(f"Timed out after {self.timeout_sec}s acquiring lock on {self.lock_path}")`.
  4. Preserve the full existing API (`acquire()`, `release()`, `__enter__()`, `__exit__()`) while ensuring that no file descriptors leak under repeated timeouts or exceptions.

---

### [Task 8: Mendeleev Mass Invariant Enforcement & Transuranic Validation (Suggestion #38)]
- **Files Affected:** `src/cochem/core/ingestors/protocols.py` (`MolecularStructureData.validate_and_resolve_molecular_data()`, lines 105–144) and `src/cochem/core/mendeleev_invariants.py`
- **Problem Statement:**
  In `MolecularStructureData.validate_and_resolve_molecular_data()`, line 138 contains a fallback for transuranic or unlisted elements: `stable_mass = elem.mass_number or 0.0`, appending `0.0` to `resolved_masses` when `elem.mass_number` is `None`. Non-physical zero nuclear masses are silently injected into mathematical engines, causing divide-by-zero singularities in center-of-mass, moment-of-inertia, rotational constant ($B_e / B_0$), and DVR vibrational frequency solvers. This violates the IUPAC/Mendeleev Dynamic Invariant Mandate and Method Matrix v4 §3.0.
- **Implementation Requirements:**
  1. Define a domain exception `MendeleevInvariantError(ValueError)` in `src/cochem/core/mendeleev_invariants.py` and import into `protocols.py`.
  2. Refactor `validate_and_resolve_molecular_data()`:
     - Dynamically retrieve elemental and isotopic properties using `from mendeleev import element`. Hardcoded mass dictionaries or manual CODATA updates are strictly prohibited.
     - Enforce the physical invariant: every resolved nuclear mass must be strictly positive ($m_i > 0.0$ u [M]) and finite.
     - If an element lacks a standard atomic weight in Mendeleev (`elem.atomic_weight is None`):
       - Check `elem.mass_number`. If `elem.mass_number` is present and $> 0.0$, use it as the nominal mass.
       - If both `elem.atomic_weight` and `elem.mass_number` are missing or evaluate to $\le 0.0$, and the user did not supply an explicit mass number in `isotopes` or `masses`:
         ```python
         raise MendeleevInvariantError(
             f"Element '{clean_sym}' lacks a standard atomic weight and default mass number in dynamic "
             "Mendeleev/IUPAC tables. A physical isotopic mass number must be explicitly specified in "
             "'isotopes' (e.g., isotopes=[252, ...]) or 'masses'."
         )
         ```
     - Eradicate `or 0.0` fallbacks. Under no circumstances may a zero or negative mass be appended to `resolved_masses`.

---

### [Task 9: Dedicated Spin Contamination & Hessian Domain Exception Hierarchy (Suggestion #39)]
- **File Affected:** `src/cochem/core/ingestors/protocols.py` (`QCResultsSchema.validate_qc_results`, lines 163–228)
- **Problem Statement:**
  `QCResultsSchema.validate_qc_results` currently raises a generic standard library `ValueError` when an electronic structure calculation exhibits severe spin contamination ($\Delta\langle S^2 \rangle > 10\%$ [D]) or when the Cartesian Hessian violates matrix symmetry ($|H_{ij} - H_{ji}| > 10^{-5}$). Autonomous swarm orchestrators cannot distinguish physical quantum chemical convergence breakdowns from syntax errors, schema mismatches, or missing keys without fragile regex string parsing. This blocks automated method pivoting (`MAX_PIVOT_CYCLES=3` [D]) to broken-symmetry DFT, CASSCF, or NEVPT2.
- **Implementation Requirements:**
  1. Implement a dedicated physical exception hierarchy in `src/cochem/core/ingestors/protocols.py`:
     ```python
     class QCValidationError(ValueError):
         """Base domain exception for physical validation failures in quantum chemistry results."""
         pass

     class HessianSymmetryError(QCValidationError):
         """Raised when a Cartesian Hessian matrix violates symmetry |H_ij - H_ji| > 1e-5."""
         def __init__(self, message: str, max_asymmetry: float, indices: Tuple[int, int]):
             super().__init__(message)
             self.max_asymmetry = max_asymmetry
             self.indices = indices

     class SpinContaminationError(QCValidationError):
         """Raised when calculated <S^2> deviates by > 10% from ideal S(S+1) reference value."""
         def __init__(self, message: str, s2_calc: float, s2_ref: float, deviation_percent: float):
             super().__init__(message)
             self.s2_calc = s2_calc
             self.s2_ref = s2_ref
             self.deviation_percent = deviation_percent
     ```
  2. In `validate_qc_results`:
     - When Hessian asymmetry exceeds tolerance, raise `HessianSymmetryError`.
     - When spin contamination deviation exceeds 10% (`dev > 0.10`), raise `SpinContaminationError`.
     - Re-export `SpinContaminationError`, `HessianSymmetryError`, and `QCValidationError` from `cochem_base.core` so autonomous agents and schedulers can catch them programmatically and trigger automated method pivots.

---

### [Task 10: Unified Core Namespace Re-exports & Dynamic Non-Locking GPU Scheduling (Suggestion #40)]
- **Files Affected:**
  - `src/cochem_base/core/__init__.py`
  - `src/cochem/runners/cuda_budget.py` (lines 68–155)
  - `src/cochem/runners/async_process_runner.py` (lines 220–255)
  - `src/cochem_base/core_engine/cochem_core_mps_orchestrator.py`
- **Problem Statement:**
  `src/cochem_base/core/__init__.py` is currently an empty 0-byte file, causing `ModuleNotFoundError: No module named 'cochem_base.core.cochem_core_registry_manager'` when external modules and test suites attempt imports across the migrated package structure. Furthermore, hardware execution dispatchers in `cuda_budget.py` and `async_process_runner.py` hardcode `device_id = 0` or enforce static device mutex locks. This serializes multi-process workers on multi-GPU compute nodes, causes artificial thread contention, and violates Method Matrix v4 §8A.4 and the Non-Blocking GPU Scheduling Directive ("no CUDA-locking").
- **Implementation Requirements:**
  1. Populate `src/cochem_base/core/__init__.py` with authoritative public re-exports:
     - Re-export `cochem_core_registry_manager` and its core registry schemas.
     - Re-export `CoChemConfigManager` and `ConfigurationParseError` from `cochem.core.config`.
     - Re-export `SandboxContext`, `SandboxConfig` from `cochem.core.cochem_sandbox`.
     - Re-export `AirGapCoordinator`, `AirGapViolationError` from `cochem.core.airgap_coordinator`.
     - Re-export `FileLock` from `cochem.core.context`.
     - Re-export `PESStore`, `SharedMemoryBuffer`, `HMACSocketServer`, `TruncatedPayloadError`, `OversizedPayloadError` from `cochem.core.ipc.serializer`.
     - Re-export `MolecularStructureData`, `QCResultsSchema`, `SpinContaminationError`, `HessianSymmetryError`, `MendeleevInvariantError` from `cochem.core.ingestors.protocols`.
  2. Implement dynamic GPU ordinal scheduling in `cuda_budget.py` and `async_process_runner.py`:
     - Eradicate hardcoded `device_id = 0` locks.
     - Dynamically discover available GPU devices via `torch.cuda.device_count()` or `pynvml`.
     - Select the GPU ordinal with the highest unreserved VRAM capacity that satisfies the task budget.
     - Export isolation dynamically to subprocess environments via `env["CUDA_VISIBLE_DEVICES"] = str(selected_device_id)`.
     - Inject `env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"`.
     - Support NVIDIA Multi-Process Service (MPS) multiplexing without host thread mutex locks; if VRAM is temporarily constrained, yield execution back to the non-blocking event loop with exponential backoff rather than holding a thread lock.
     - If no CUDA device is present, fall back cleanly to CPU execution with `env["CUDA_VISIBLE_DEVICES"] = ""` without hanging or raising mock exceptions.

---

## 4. Zero-Mock Test Suite Specifications

Author comprehensive, production-grade test suites executing real physical operations with zero mocks, zero monkey-patched stubs, and zero synthetic loops.

### Test Suite 1: Architecture, Air-Gap & Concurrency (`tests/core/test_architecture_part4.py`)
1. **`test_config_manager_strict_toml_parsing()` (Suggestion #31):**
   - Write a temporary `cochem.toml` containing a deliberate syntax error (e.g. `memory_gb = [unclosed_bracket`).
   - Instantiate `CoChemConfigManager` targeting the temporary directory.
   - Assert that `ConfigurationParseError` is raised with the exact filename, line number, and parser diagnostic. Verify that execution halts and does not fall back to default settings.
   - Write a valid `cochem.toml` with `memory_gb = 64`. Assert that the manager correctly ingests 64 GB.
2. **`test_sandbox_preserves_primary_scientific_exception()` (Suggestion #32):**
   - Execute a failing scientific task inside `SandboxContext` (e.g. raising `RuntimeError("Electronic structure SCF failed to converge")`).
   - Simultaneously create an un-deletable locked file in the sandbox scratch directory to force an `OSError` during `self.cleanup()`.
   - Assert that the context manager propagates `RuntimeError("Electronic structure SCF failed to converge")` cleanly and does not raise `PermissionError` or mask the scientific traceback.
3. **`test_artifact_publication_atomicity_and_source_immutability()` (Suggestion #33):**
   - Create a valid calculation artifact in ephemeral scratch ($T_{\text{scr}}$).
   - Publish the artifact via `AirGapCoordinator.publish_artifact()`.
   - Assert that the destination file in $T_{\text{art}}$ exists and that its SHA-256 hash matches the source.
   - Verify that write attempts to the Source Tier ($T_{\text{src}}$) raise `AirGapViolationError`.
   - Simulate a scratch deletion lock collision; verify that the published artifact remains valid and the function returns success.
4. **`test_cross_platform_file_lock_mutual_exclusion()` (Suggestion #37):**
   - Initialize two independent `FileLock` instances targeting the same physical lockfile.
   - Acquire the lock with instance 1. Launch a separate thread attempting to acquire the lock with instance 2 with `timeout_sec=0.5`.
   - Assert that instance 2 raises `TimeoutError`. Release instance 1; assert that instance 2 subsequently acquires the lock successfully.
   - Assert that repeated timeouts leave zero open file descriptors leaked in the process.
5. **`test_unified_core_namespace_and_dynamic_gpu_scheduling()` (Suggestion #40):**
   - Import all authoritative symbols directly from `cochem_base.core` and assert that no `ModuleNotFoundError` is raised.
   - Request device allocation from `cuda_budget.py`; verify that it returns an available device ordinal or sets CPU fallback without locking threads.

### Test Suite 2: Physics Invariants, Memory & IPC (`tests/core/test_physics_integrity_part4.py`)
1. **`test_hdf5_pes_store_swmr_concurrent_writes()` (Suggestion #34):**
   - Initialize a `PESStore` instance.
   - Launch 4 concurrent threads, each writing 20 distinct calculation coordinate entries (`entry_id`) with 3D coordinate arrays and QCSchema metadata.
   - Assert that all 80 entries are successfully committed without data loss.
   - Read back entries in SWMR mode and verify array values and checksums.
   - Verify that `shutil.copyfile` was never invoked and that disk space remained bounded.
2. **`test_ipc_socket_payload_framing_and_truncation()` (Suggestion #35):**
   - Spin up `HMACSocketServer` on a dynamic loopback port.
   - Connect a raw TCP client, satisfy the HMAC handshake, send a 4-byte header specifying `payload_len = 1000`, but transmit only 200 bytes before closing the socket.
   - Assert that `HMACSocketServer` detects the truncation, logs the failure, and unblocks waiting callers by raising `TruncatedPayloadError`.
   - Send a packet specifying `payload_len = 500 * 1024 * 1024` (500 MB); assert that the server immediately rejects the packet with `OversizedPayloadError`.
3. **`test_shared_memory_raii_and_weakref_cleanup()` (Suggestion #36):**
   - Allocate a `SharedMemoryBuffer` from a 5000-element NumPy array using a `with SharedMemoryBuffer.from_array(arr) as shm_buf:` block.
   - Read the array back using `SharedMemoryBuffer.read_from_descriptor(shm_buf.descriptor)`. Assert numerical identity.
   - Exit the context manager; verify that the segment is unlinked and no longer accessible via `multiprocessing.shared_memory.SharedMemory(name=shm_buf.shm.name)`.
   - Allocate a buffer outside a context manager and delete the reference (`del shm_buf; gc.collect()`). Assert that the `weakref.finalize` hook unlinks the OS segment automatically.
4. **`test_mendeleev_mass_invariants_and_zero_mass_rejection()` (Suggestion #38):**
   - Pass valid molecules (H2O, CH4) through `MolecularStructureData.validate_and_resolve_molecular_data()`. Assert masses match dynamic Mendeleev CIAAW atomic weights.
   - Ingest an exotic transuranic element without standard CIAAW weights (e.g. element 119) without specifying an isotope number. Assert that `MendeleevInvariantError` is raised and that mass `0.0` is never returned.
   - Provide an explicit isotope (e.g., `isotopes=[252]`); assert that the mass resolves strictly to $> 0.0$ u [M].
5. **`test_spin_contamination_and_hessian_domain_exceptions()` (Suggestion #39):**
   - Provide a QC result dictionary with $\langle S^2 \rangle_{\text{calc}} = 1.25$ for a singlet reference ($S^2_{\text{ideal}} = 0.0$). Assert that `QCResultsSchema.validate_qc_results()` raises `SpinContaminationError`, with attributes `s2_calc`, `s2_ref`, and `deviation_percent`.
   - Provide an asymmetric Hessian ($|H_{01} - H_{10}| = 0.05$). Assert that validation raises `HessianSymmetryError`.
   - Assert that both errors inherit from `QCValidationError` and can be caught programmatically to trigger swarm method pivots.

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock & Zero-Stub Verification:**
   - Scan repository diffs across all modified files. Zero occurrences of `unittest.mock`, `MagicMock`, `@patch`, `TODO`, `pass`, or `NotImplementedError` permitted.
2. **Full Test Suite Execution:**
   - Execute `pytest tests/core/test_architecture_part4.py tests/core/test_physics_integrity_part4.py`.
   - 100% of authored tests must pass with physical I/O, actual IPC loopback transmissions, real OS shared memory allocations, and genuine multi-threaded concurrency.
3. **Cross-Platform Path Hygiene:**
   - All paths must use `pathlib.Path.resolve()`. Zero hardcoded Windows drive letters (`C:`, `D:`) or POSIX root assumptions in library logic.
4. **Method Matrix Provenance Compliance:**
   - Dynamic mass retrieval strictly through `mendeleev`.
   - Provenance tags (`[M]`, `[D]`, `[E]`) verified on all physical metrics.
5. **Audit Handoff:**
   - Prepare clean implementation diffs and physical test execution outputs for formal review by `cochem-audit` and `adversary`.

---

## 6. Agent Council Adversarial Audit & Ratification Record

### Adversarial Audit Dispatch Log
- **Peer Auditor 1 (`cochem-audit`):** Dispatched to Conversation ID `c2888a7d-16d6-4d1b-b0d6-c189f2f760d7`.
- **Peer Auditor 2 (`adversary`):** Dispatched to Conversation ID `bc253b24-769e-4521-affa-7e39bc7ebcf8`.
- **Audit Mandate Status:** Active audit requests verified and registered in `swarm_state.json`.

### Audit Evaluation & Verdict

| Audit Category | Evaluation Criterion | Verdict |
| :--- | :--- | :--- |
| **Configuration Authority** | Fail-fast TOML parsing diagnostics with `ConfigurationParseError`; zero exception swallowing | **PASS (VERIFIED)** |
| **Diagnostics Preservation** | Sandbox teardown preserves primary electronic structure exceptions during OS lock collisions | **PASS (VERIFIED)** |
| **Air-Gap Storage Atomicity** | Decoupled publish commit from scratch teardown; immutable read-only Source Tier ($T_{\text{src}}$) | **PASS (VERIFIED)** |
| **PES Store Concurrency** | Eradication of monolithic file copies; Single-Master & SWMR HDF5 synchronization with chunk pre-allocation | **PASS (VERIFIED)** |
| **IPC Transport Safety** | Enforced 256 MB payload ceiling; deterministic `TruncatedPayloadError` signaling on socket termination | **PASS (VERIFIED)** |
| **Memory Lifecycle RAII** | Context manager and `weakref.finalize` garbage collection for cross-platform OS shared memory | **PASS (VERIFIED)** |
| **Universal File Locking** | Complete eradication of `fcntl`/`msvcrt` primitives in favor of standardized `filelock.FileLock` | **PASS (VERIFIED)** |
| **Physical Mass Invariants** | Dynamic mass resolution via `mendeleev`; zero null fallbacks ($m_i > 0.0$ u [M]); `MendeleevInvariantError` | **PASS (VERIFIED)** |
| **Quantum Chemical Exceptions** | Domain-specific `SpinContaminationError` and `HessianSymmetryError` driving automated swarm pivots | **PASS (VERIFIED)** |
| **Hardware & Namespace** | Authoritative re-exports in `cochem_base.core`; dynamic non-locking GPU allocation under MPS | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero mocks, zero synthetic loops across all 10 tasks and test specifications | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 4: Suggestions #31–#40)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §5, §7, §8A, §8A.4, §8C, §9A.5, §16.1, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Storage Air-Gap Architecture (Source $T_{\text{src}}$ immutable read-only, Ephemeral Scratch $T_{\text{scr}}$ isolated, Artifacts $T_{\text{art}}$ read-write cryptographic commitments)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- Dynamic Mendeleev Invariant Mandate (`from mendeleev import element`, zero hardcoded atomic masses, strict $m_i > 0.0$ u physical invariant)
- Non-Blocking GPU Scheduling Directive (Dynamic ordinal selection via `CUDA_VISIBLE_DEVICES`, "no CUDA-locking" host mutex locks, NVIDIA MPS multi-process multiplexing)
- Cross-Platform Concurrency Directive (Standardized `filelock.FileLock` mutual exclusion, `multiprocessing.shared_memory.SharedMemory` RAII lifecycle)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #31 through #40 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical vulnerabilities across configuration ingestion authority, error diagnostics preservation, storage air-gap transaction sequencing, high-throughput potential energy surface (PES) database concurrency, inter-process communication (IPC) framing and memory safety, kernel shared memory lifecycle hygiene, cross-platform distributed network file locking, dynamic physical mass invariants, domain-specific quantum chemical exception routing, and unified namespace architecture with non-blocking GPU hardware dispatching across the 6-Tier Environment Matrix.

Specific targets include eliminating silent configuration fallbacks by introducing fail-fast TOML parsing diagnostics, protecting primary electronic structure convergence exceptions from being masked by secondary operating system cleanup errors during sandbox teardown, decoupling atomic artifact commits from ephemeral scratch file unlinking, eradicating $O(N \cdot M)$ disk I/O thrashing in HDF5 stores via Single-Writer Multiple-Reader (SWMR) synchronization and master queue arbitration, enforcing strict 256 MB payload framing and truncation diagnostics on IPC daemon sockets, implementing RAII and `weakref.finalize` garbage collection for OS shared memory segments, replacing custom `fcntl`/`msvcrt` primitives with standardized cross-platform `filelock.FileLock`, enforcing dynamic positive mass invariants ($m_i > 0.0$ u) via IUPAC/Mendeleev registries while rejecting transuranic null fallbacks, implementing domain-specific physical exceptions (`SpinContaminationError`, `HessianSymmetryError`) to drive autonomous swarm method pivots, and resolving broken core namespaces while eliminating static `device_id=0` GPU thread mutex locking.

Every modification must be accompanied by comprehensive, zero-mock unit and integration tests executing real physical computations, multi-threaded stress tests, OS-level process lifecycles, and genuine disk I/O.

---

## 2. Target Files & Deliverable Manifest

### Core Configuration, Sandbox & Storage Air-Gap Modules
1. `src/cochem/core/config.py` (Suggestion #31)
2. `src/cochem/core/cochem_sandbox.py` (Suggestion #32)
3. `src/cochem/core/airgap_coordinator.py` (Suggestions #32, #33)
4. `src/cochem/core/context.py` (Suggestion #37)

### IPC, Memory & PES Store Modules
5. `src/cochem/core/ipc/serializer.py` (Suggestions #34, #35, #36)
6. `src/cochem_geom/data/pes_store.py` (Suggestion #34)
7. `src/cochem/storage/cochem_core_pes_store.py` (Suggestion #34)
8. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestion #34)

### Physics Ingestors, Schemas & Hardware Dispatch Modules
9. `src/cochem/core/ingestors/protocols.py` (Suggestions #38, #39)
10. `src/cochem/core/mendeleev_invariants.py` (Suggestion #38)
11. `src/cochem_base/core/__init__.py` (Suggestion #40)
12. `src/cochem/runners/cuda_budget.py` (Suggestion #40)
13. `src/cochem/runners/async_process_runner.py` (Suggestion #40)
14. `src/cochem_base/core_engine/cochem_core_mps_orchestrator.py` (Suggestion #40)

### Zero-Mock Test Suite Deliverables
15. `tests/core/test_architecture_part4.py` (Validating Suggestions #31, #32, #33, #37, #40)
16. `tests/core/test_physics_integrity_part4.py` (Validating Suggestions #34, #35, #36, #38, #39)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Deterministic Configuration Parsing & Fail-Fast Authority (Suggestion #31)]
- **File Affected:** `src/cochem/core/config.py` (`_load_toml_file`, lines 146–156)
- **Problem Statement:**
  In `CoChemConfigManager._load_toml_file`, the TOML parsing routine catches all exceptions in a broad `except Exception as err:` block, emits a log warning, and silently returns an empty dictionary `{}`. When a user provides a configuration file (`cochem.toml`) containing syntax errors, formatting defects, or invalid types, the manager silently discards the user configuration and falls back to hardcoded defaults (4 GB RAM, loose convergence thresholds, unconstrained workers). This violates the Stage 0 Authority Rule and Method Matrix v4 §8A, executing expensive calculations outside user-configured physical boundaries and inducing out-of-memory crashes on HPC nodes.
- **Implementation Requirements:**
  1. Define a custom structured exception `ConfigurationParseError(Exception)` in `src/cochem/core/config.py` (and expose it in public re-exports).
  2. Refactor `_load_toml_file(self, path: Path) -> Dict[str, Any]`:
     - If the configuration file does not exist (`not path.exists()`), return `{}` (preserving optional overlay behavior).
     - If the file exists, read and parse it strictly using `tomllib.load(f)`.
     - Explicitly catch `tomllib.TOMLDecodeError` and raise `ConfigurationParseError`:
       ```python
       try:
           with open(path, "rb") as f:
               return tomllib.load(f)
       except tomllib.TOMLDecodeError as err:
           raise ConfigurationParseError(
               f"Fatal TOML syntax error in configuration file '{path.resolve()}' "
               f"at line {err.lineno}, column {err.colno}: {err}"
           ) from err
       except OSError as err:
           raise ConfigurationParseError(
               f"Fatal I/O or permissions error reading configuration file '{path.resolve()}': {err}"
           ) from err
       ```
     - Eradicate the broad `except Exception as err:` block. Swallowing configuration errors is strictly forbidden.
  3. Ensure that callers (`get_workspace_config`, `_load_user_config`, `_load_project_config`) allow `ConfigurationParseError` to propagate cleanly, halting pipeline initialization immediately across all 6 environment tiers before hardware dispatch.

---

### [Task 2: Primary Exception Preservation in Ephemeral Sandbox Teardown (Suggestion #32)]
- **File Affected:** `src/cochem/core/cochem_sandbox.py` (`SandboxContext.__exit__`, lines 69–76) and `src/cochem/core/airgap_coordinator.py`
- **Problem Statement:**
  `SandboxContext.__exit__` unconditionally invokes `self.cleanup()`. When cleanup encounters a transient operating system filesystem error (such as Windows `[WinError 32]` file locking, antivirus indexer collisions, or distributed NFS/Lustre file-handle lock delays after exhausting retries), `cleanup()` re-raises the `OSError`. Under standard Python context manager semantics, an exception escaping `__exit__` supersedes and completely discards any active scientific exception that occurred inside the `with SandboxContext(...)` block (e.g. SCF convergence failure, geometry optimization divergence, or gradient NaN). Autonomous debugging agents receive misleading filesystem permission errors instead of the true quantum chemical telemetry.
- **Implementation Requirements:**
  1. Update `SandboxContext.__exit__` to inspect `exc_type`:
     ```python
     def __exit__(
         self,
         exc_type: Optional[type[BaseException]],
         exc_val: Optional[BaseException],
         exc_tb: Optional[Any],
     ) -> None:
         is_unwinding = exc_type is not None
         try:
             self.cleanup()
         except OSError as cleanup_err:
             if is_unwinding:
                 logger.warning(
                     "Secondary OSError encountered during sandbox cleanup suppressed to preserve "
                     "primary scientific exception: %s (unreclaimed scratch path: %s)",
                     cleanup_err,
                     self.root,
                 )
                 # Allow the primary scientific exception to propagate without masking
                 return None
             raise
     ```
  2. If cleanup fails during exception unwinding, register the un-cleared scratch directory `self.root` with the background `ZombieReaperDaemon` or append to an asynchronous quarantine queue for sweep-up upon process exit.
  3. Ensure that if no primary exception is active (`is_unwinding is False`), cleanup failures still raise cleanly to signal filesystem degradation.

---

### [Task 3: Decoupled Atomic Artifact Publication & Source Tier Immutability (Suggestion #33)]
- **File Affected:** `src/cochem/core/airgap_coordinator.py` (`publish_artifact`, lines 104–146)
- **Problem Statement:**
  In `AirGapCoordinator.publish_artifact()`, post-commit scratch deletion (`source.unlink(missing_ok=True)`) is executed inside the primary publish `try` block alongside `os.replace(temp_dest, dest)`. If `source.unlink()` raises a `PermissionError` (common on Windows when background telemetry handles are still closing), the `except` block triggers rollback logic attempting `temp_dest.unlink()`. However, `temp_dest` was already moved to `dest` via `os.replace()`, so the rollback fails, and the caller is handed an unhandled exception. The destination artifact was already written, hashed, and cryptographically verified via SHA-256, but callers treat the publication as aborted and execute redundant re-computations. In addition, write protections on the Source Tier ($T_{\text{src}}$) are not strictly asserted.
- **Implementation Requirements:**
  1. Strictly decouple the atomic publication commit transaction from scratch cleanup:
     - **Phase 1 (Atomic Commit):** Copy `source` to `temp_dest` within the artifact destination directory, compute SHA-256 digest, and atomically rename `temp_dest` to `dest` using `os.replace(temp_dest, dest)`. If any error occurs during Phase 1, remove `temp_dest` (if it exists) and raise the error.
     - **Phase 2 (Post-Commit Teardown):** Once `os.replace()` succeeds, the artifact is committed. Wrap `source.unlink(missing_ok=True)` in an isolated `try...except OSError as cleanup_err:` block. If unlinking fails, log a warning and register `source` for background sweeping; **never** raise an exception or invalidate the committed publication transaction.
  2. Enforce Source Tier ($T_{\text{src}}$) Immutability:
     - Assert that neither `source_path` nor `relative_dest` attempts to write into or modify the read-only codebase root ($T_{\text{src}}$ / `config.source_root`).
     - If any mutation or target destination falls within `config.source_root`, raise `AirGapViolationError("Source tier (T_src) is strictly immutable and read-only.")`.
  3. Ensure that `publish_artifact()` returns `Tuple[pathlib.Path, Optional[str]]` containing the committed destination path and verified SHA-256 checksum deterministically.

---

### [Task 4: High-Throughput HDF5 SWMR Store & Single-Master Concurrency (Suggestion #34)]
- **Files Affected:** `src/cochem/core/ipc/serializer.py` (`PESStore`, lines 290–360), `src/cochem_geom/data/pes_store.py`, and `src/cochem/storage/cochem_core_pes_store.py`
- **Problem Statement:**
  `PESStore.write_entry()` currently handles persistence by copying the entire existing HDF5 file to a temporary file (`shutil.copyfile(self.file_path, tmp_path)`), appending the new calculation entry, and replacing the target file via `os.replace()`. For multi-point potential energy surface scans and high-throughput conformer generation, copying a multi-gigabyte HDF5 database on every coordinate point incurs $O(N \cdot M)$ disk I/O thrashing, exhausts scratch disk space, and corrupts datasets when concurrent workers overwrite each other's points. Furthermore, POSIX file locks cannot coordinate internal HDF5 B-tree cache pages across independent process address spaces on network filesystems (NFS/Lustre).
- **Implementation Requirements:**
  1. Completely eradicate `shutil.copyfile` and whole-file copy-on-write staging in `PESStore.write_entry`.
  2. Implement single-master writer arbitration and thread-level mutex protection:
     - Add an internal reentrant lock `self._write_lock = threading.RLock()` to serialize library calls within the process.
     - Wrap file access in cross-platform OS locking: `filelock.FileLock(str(self.file_path) + ".lock", timeout=30.0)` targeting node-local scratch storage.
  3. Configure HDF5 in Single-Writer Multiple-Reader (SWMR) mode:
     - Open the store directly with `h5py.File(self.file_path, "a", libver="latest")`.
     - When appending coordinate grids and results, utilize chunked datasets with pre-allocated extensible dimensions (`maxshape=(None, ...)`), compression (`compression="gzip"`, `compression_opts=4`), and Fletcher32 checksums (`fletcher32=True`).
     - Call `h5f.flush()` immediately after writing groups and datasets to commit B-tree metadata to disk, guaranteeing that concurrent readers in SWMR mode (`swmr=True`) observe consistent states.
  4. Implement pre-flight disk capacity verification:
     - Before writing, verify that the filesystem hosting `self.file_path` has at least 100 MB free (`shutil.disk_usage(self.file_path.parent).free >= 100 * 1024 * 1024`). If disk space is exhausted, raise `IOError("Insufficient disk space on target volume for PESStore append")`.

---

### [Task 5: IPC Payload Framing, Bounds Enforcement & Truncation Handling (Suggestion #35)]
- **File Affected:** `src/cochem/core/ipc/serializer.py` (`HMACSocketServer`, lines 206–239)
- **Problem Statement:**
  In `HMACSocketServer._accept_loop`, when an IPC client connection terminates prematurely or drops packets mid-transmission, the condition `if len(buffer) == payload_len:` evaluates to `False`. The loop drops silently through to `conn.close()` without logging an error, raising an exception, or notifying the server. `self._payload_event` is never signaled, causing callers in `get_received_payload()` to hang indefinitely until timeout. In addition, reading the 4-byte payload length header (`payload_len = struct.unpack("!I", len_bytes)[0]`) lacks bounds verification; a malformed or malicious packet specifying a large `payload_len` triggers `bytearray()` allocation up to $2^{32}-1$ bytes, crashing daemons with an unhandled `MemoryError`.
- **Implementation Requirements:**
  1. Define custom IPC exceptions in `src/cochem/core/ipc/serializer.py`:
     ```python
     class IPCPayloadError(Exception):
         """Base exception for IPC payload transmission failures."""
         pass

     class TruncatedPayloadError(IPCPayloadError):
         """Raised when an IPC connection terminates before receiving the full payload."""
         pass

     class OversizedPayloadError(IPCPayloadError):
         """Raised when a transmitted payload header exceeds the safety ceiling."""
         pass
     ```
  2. Enforce a strict maximum payload ceiling constant: `MAX_IPC_PAYLOAD_BYTES = 256 * 1024 * 1024` (256 MB [D]).
  3. In `HMACSocketServer._accept_loop`:
     - Inspect `payload_len`. If `payload_len > MAX_IPC_PAYLOAD_BYTES`:
       - Log an error: `logger.error("IPC payload rejected: size %d exceeds 256 MB ceiling", payload_len)`
       - Set `self._last_error = OversizedPayloadError(f"Payload size {payload_len} exceeds 256 MB limit")`
       - Set `self._payload_event.set()` and close the connection.
     - Stream chunks into `buffer`. If `conn.recv()` returns `b""` (EOF) while `len(buffer) < payload_len`:
       - Log an error: `logger.error("IPC stream truncated: received %d of %d bytes", len(buffer), payload_len)`
       - Set `self._last_error = TruncatedPayloadError(f"Stream truncated: received {len(buffer)} of {payload_len} bytes")`
       - Set `self._payload_event.set()` and close the connection.
  4. In `get_received_payload(self, timeout_sec: float = 5.0) -> Optional[Any]`:
     - If `self._last_error` is set, retrieve and clear the error, raising it directly to the caller so failures are detected immediately rather than timing out.

---

### [Task 6: Cross-Platform SharedMemoryBuffer RAII & Garbage Collection Hooks (Suggestion #36)]
- **File Affected:** `src/cochem/core/ipc/serializer.py` (`SharedMemoryBuffer`, lines 77–128)
- **Problem Statement:**
  `SharedMemoryBuffer` allocates operating system kernel shared memory via `multiprocessing.shared_memory.SharedMemory(create=True, size=total_bytes)`, but lacks a context manager implementation (`__enter__`/`__exit__`) and does not register a `weakref.finalize` garbage collection callback. When an unhandled exception occurs in a worker pipeline between memory allocation and manual `shm.unlink()` calls, the operating system shared memory segments remain orphaned in `/dev/shm` (on Linux) or in the paging system (on Windows). High-throughput conformer clustering jobs rapidly exhaust shared memory, causing subsequent calculations to crash with `FileExistsError` and halting compute nodes.
- **Implementation Requirements:**
  1. Implement RAII context manager semantics on `SharedMemoryBuffer`:
     ```python
     def __enter__(self) -> SharedMemoryBuffer:
         return self

     def __exit__(
         self,
         exc_type: Optional[type[BaseException]],
         exc_val: Optional[BaseException],
         exc_tb: Optional[Any],
     ) -> None:
         self.close()
         self.unlink()
     ```
  2. Implement automatic garbage collection cleanup using `weakref.finalize`:
     - Define a module-level standalone cleanup function `_finalize_shm(name: str) -> None`:
       ```python
       def _finalize_shm(name: str) -> None:
           try:
               s = sm.SharedMemory(name=name)
               s.close()
               s.unlink()
           except (FileNotFoundError, OSError):
               pass
       ```
     - In `SharedMemoryBuffer.__init__` (or when allocated via `from_array`), attach the finalizer:
       `self._finalizer = weakref.finalize(self, _finalize_shm, self.shm.name)`
     - Update `unlink()` to deregister the finalizer cleanly via `self._finalizer.detach()` if already explicitly unlinked.
  3. Ensure full cross-platform compatibility without `/dev/shm` filesystem path assumptions, operating uniformly on Windows, macOS, Linux Debian, Codespaces, and HPC environments.

---

### [Task 7: Centralized Cross-Platform Network File Locking via `filelock` (Suggestion #37)]
- **File Affected:** `src/cochem/core/context.py` (`FileLock`, lines 148–225)
- **Problem Statement:**
  `cochem.core.context.FileLock` maintains legacy, low-level locking wrappers calling `msvcrt.locking` on Windows and `fcntl.flock` on POSIX systems. Standard `fcntl.flock` semantics fail silently or cause split-brain corruptions across distributed network filesystems (NFS, Lustre, GPFS) on HPC clusters. In addition, `self._fd = os.open(...)` is executed before the acquisition loop; if an error occurs or the timeout expires, `_fd` remains unclosed, leaking file descriptors. This violates the project-wide Concurrency Directive: "fcntl eradication, use cross-platform `filelock` package!"
- **Implementation Requirements:**
  1. Completely replace low-level `fcntl.flock` and `msvcrt.locking` in `cochem.core.context.FileLock` with the centralized `filelock.FileLock`:
     - Delegate physical lock management to an internal `filelock.FileLock(str(self.lock_path) + ".lock", timeout=self.timeout_sec)`.
     - Convert all incoming path inputs using `pathlib.Path(lock_path).resolve()`.
  2. Eradicate raw `os.open()`, `os.close()`, and file descriptor tracking (`self._fd`).
  3. Ensure deterministic resource release:
     - Wrap lock acquisitions in clean `try...finally` blocks.
     - On timeout, raise `TimeoutError(f"Timed out after {self.timeout_sec}s acquiring lock on {self.lock_path}")`.
  4. Preserve the full existing API (`acquire()`, `release()`, `__enter__()`, `__exit__()`) while ensuring that no file descriptors leak under repeated timeouts or exceptions.

---

### [Task 8: Mendeleev Mass Invariant Enforcement & Transuranic Validation (Suggestion #38)]
- **Files Affected:** `src/cochem/core/ingestors/protocols.py` (`MolecularStructureData.validate_and_resolve_molecular_data()`, lines 105–144) and `src/cochem/core/mendeleev_invariants.py`
- **Problem Statement:**
  In `MolecularStructureData.validate_and_resolve_molecular_data()`, line 138 contains a fallback for transuranic or unlisted elements: `stable_mass = elem.mass_number or 0.0`, appending `0.0` to `resolved_masses` when `elem.mass_number` is `None`. Non-physical zero nuclear masses are silently injected into mathematical engines, causing divide-by-zero singularities in center-of-mass, moment-of-inertia, rotational constant ($B_e / B_0$), and DVR vibrational frequency solvers. This violates the IUPAC/Mendeleev Dynamic Invariant Mandate and Method Matrix v4 §3.0.
- **Implementation Requirements:**
  1. Define a domain exception `MendeleevInvariantError(ValueError)` in `src/cochem/core/mendeleev_invariants.py` and import into `protocols.py`.
  2. Refactor `validate_and_resolve_molecular_data()`:
     - Dynamically retrieve elemental and isotopic properties using `from mendeleev import element`. Hardcoded mass dictionaries or manual CODATA updates are strictly prohibited.
     - Enforce the physical invariant: every resolved nuclear mass must be strictly positive ($m_i > 0.0$ u [M]) and finite.
     - If an element lacks a standard atomic weight in Mendeleev (`elem.atomic_weight is None`):
       - Check `elem.mass_number`. If `elem.mass_number` is present and $> 0.0$, use it as the nominal mass.
       - If both `elem.atomic_weight` and `elem.mass_number` are missing or evaluate to $\le 0.0$, and the user did not supply an explicit mass number in `isotopes` or `masses`:
         ```python
         raise MendeleevInvariantError(
             f"Element '{clean_sym}' lacks a standard atomic weight and default mass number in dynamic "
             "Mendeleev/IUPAC tables. A physical isotopic mass number must be explicitly specified in "
             "'isotopes' (e.g., isotopes=[252, ...]) or 'masses'."
         )
         ```
     - Eradicate `or 0.0` fallbacks. Under no circumstances may a zero or negative mass be appended to `resolved_masses`.

---

### [Task 9: Dedicated Spin Contamination & Hessian Domain Exception Hierarchy (Suggestion #39)]
- **File Affected:** `src/cochem/core/ingestors/protocols.py` (`QCResultsSchema.validate_qc_results`, lines 163–228)
- **Problem Statement:**
  `QCResultsSchema.validate_qc_results` currently raises a generic standard library `ValueError` when an electronic structure calculation exhibits severe spin contamination ($\Delta\langle S^2 \rangle > 10\%$ [D]) or when the Cartesian Hessian violates matrix symmetry ($|H_{ij} - H_{ji}| > 10^{-5}$). Autonomous swarm orchestrators cannot distinguish physical quantum chemical convergence breakdowns from syntax errors, schema mismatches, or missing keys without fragile regex string parsing. This blocks automated method pivoting (`MAX_PIVOT_CYCLES=3` [D]) to broken-symmetry DFT, CASSCF, or NEVPT2.
- **Implementation Requirements:**
  1. Implement a dedicated physical exception hierarchy in `src/cochem/core/ingestors/protocols.py`:
     ```python
     class QCValidationError(ValueError):
         """Base domain exception for physical validation failures in quantum chemistry results."""
         pass

     class HessianSymmetryError(QCValidationError):
         """Raised when a Cartesian Hessian matrix violates symmetry |H_ij - H_ji| > 1e-5."""
         def __init__(self, message: str, max_asymmetry: float, indices: Tuple[int, int]):
             super().__init__(message)
             self.max_asymmetry = max_asymmetry
             self.indices = indices

     class SpinContaminationError(QCValidationError):
         """Raised when calculated <S^2> deviates by > 10% from ideal S(S+1) reference value."""
         def __init__(self, message: str, s2_calc: float, s2_ref: float, deviation_percent: float):
             super().__init__(message)
             self.s2_calc = s2_calc
             self.s2_ref = s2_ref
             self.deviation_percent = deviation_percent
     ```
  2. In `validate_qc_results`:
     - When Hessian asymmetry exceeds tolerance, raise `HessianSymmetryError`.
     - When spin contamination deviation exceeds 10% (`dev > 0.10`), raise `SpinContaminationError`.
     - Re-export `SpinContaminationError`, `HessianSymmetryError`, and `QCValidationError` from `cochem_base.core` so autonomous agents and schedulers can catch them programmatically and trigger automated method pivots.

---

### [Task 10: Unified Core Namespace Re-exports & Dynamic Non-Locking GPU Scheduling (Suggestion #40)]
- **Files Affected:**
  - `src/cochem_base/core/__init__.py`
  - `src/cochem/runners/cuda_budget.py` (lines 68–155)
  - `src/cochem/runners/async_process_runner.py` (lines 220–255)
  - `src/cochem_base/core_engine/cochem_core_mps_orchestrator.py`
- **Problem Statement:**
  `src/cochem_base/core/__init__.py` is currently an empty 0-byte file, causing `ModuleNotFoundError: No module named 'cochem_base.core.cochem_core_registry_manager'` when external modules and test suites attempt imports across the migrated package structure. Furthermore, hardware execution dispatchers in `cuda_budget.py` and `async_process_runner.py` hardcode `device_id = 0` or enforce static device mutex locks. This serializes multi-process workers on multi-GPU compute nodes, causes artificial thread contention, and violates Method Matrix v4 §8A.4 and the Non-Blocking GPU Scheduling Directive ("no CUDA-locking").
- **Implementation Requirements:**
  1. Populate `src/cochem_base/core/__init__.py` with authoritative public re-exports:
     - Re-export `cochem_core_registry_manager` and its core registry schemas.
     - Re-export `CoChemConfigManager` and `ConfigurationParseError` from `cochem.core.config`.
     - Re-export `SandboxContext`, `SandboxConfig` from `cochem.core.cochem_sandbox`.
     - Re-export `AirGapCoordinator`, `AirGapViolationError` from `cochem.core.airgap_coordinator`.
     - Re-export `FileLock` from `cochem.core.context`.
     - Re-export `PESStore`, `SharedMemoryBuffer`, `HMACSocketServer`, `TruncatedPayloadError`, `OversizedPayloadError` from `cochem.core.ipc.serializer`.
     - Re-export `MolecularStructureData`, `QCResultsSchema`, `SpinContaminationError`, `HessianSymmetryError`, `MendeleevInvariantError` from `cochem.core.ingestors.protocols`.
  2. Implement dynamic GPU ordinal scheduling in `cuda_budget.py` and `async_process_runner.py`:
     - Eradicate hardcoded `device_id = 0` locks.
     - Dynamically discover available GPU devices via `torch.cuda.device_count()` or `pynvml`.
     - Select the GPU ordinal with the highest unreserved VRAM capacity that satisfies the task budget.
     - Export isolation dynamically to subprocess environments via `env["CUDA_VISIBLE_DEVICES"] = str(selected_device_id)`.
     - Inject `env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"`.
     - Support NVIDIA Multi-Process Service (MPS) multiplexing without host thread mutex locks; if VRAM is temporarily constrained, yield execution back to the non-blocking event loop with exponential backoff rather than holding a thread lock.
     - If no CUDA device is present, fall back cleanly to CPU execution with `env["CUDA_VISIBLE_DEVICES"] = ""` without hanging or raising mock exceptions.

---

## 4. Zero-Mock Test Suite Specifications

Author comprehensive, production-grade test suites executing real physical operations with zero mocks, zero monkey-patched stubs, and zero synthetic loops.

### Test Suite 1: Architecture, Air-Gap & Concurrency (`tests/core/test_architecture_part4.py`)
1. **`test_config_manager_strict_toml_parsing()` (Suggestion #31):**
   - Write a temporary `cochem.toml` containing a deliberate syntax error (e.g. `memory_gb = [unclosed_bracket`).
   - Instantiate `CoChemConfigManager` targeting the temporary directory.
   - Assert that `ConfigurationParseError` is raised with the exact filename, line number, and parser diagnostic. Verify that execution halts and does not fall back to default settings.
   - Write a valid `cochem.toml` with `memory_gb = 64`. Assert that the manager correctly ingests 64 GB.
2. **`test_sandbox_preserves_primary_scientific_exception()` (Suggestion #32):**
   - Execute a failing scientific task inside `SandboxContext` (e.g. raising `RuntimeError("Electronic structure SCF failed to converge")`).
   - Simultaneously create an un-deletable locked file in the sandbox scratch directory to force an `OSError` during `self.cleanup()`.
   - Assert that the context manager propagates `RuntimeError("Electronic structure SCF failed to converge")` cleanly and does not raise `PermissionError` or mask the scientific traceback.
3. **`test_artifact_publication_atomicity_and_source_immutability()` (Suggestion #33):**
   - Create a valid calculation artifact in ephemeral scratch ($T_{\text{scr}}$).
   - Publish the artifact via `AirGapCoordinator.publish_artifact()`.
   - Assert that the destination file in $T_{\text{art}}$ exists and that its SHA-256 hash matches the source.
   - Verify that write attempts to the Source Tier ($T_{\text{src}}$) raise `AirGapViolationError`.
   - Simulate a scratch deletion lock collision; verify that the published artifact remains valid and the function returns success.
4. **`test_cross_platform_file_lock_mutual_exclusion()` (Suggestion #37):**
   - Initialize two independent `FileLock` instances targeting the same physical lockfile.
   - Acquire the lock with instance 1. Launch a separate thread attempting to acquire the lock with instance 2 with `timeout_sec=0.5`.
   - Assert that instance 2 raises `TimeoutError`. Release instance 1; assert that instance 2 subsequently acquires the lock successfully.
   - Assert that repeated timeouts leave zero open file descriptors leaked in the process.
5. **`test_unified_core_namespace_and_dynamic_gpu_scheduling()` (Suggestion #40):**
   - Import all authoritative symbols directly from `cochem_base.core` and assert that no `ModuleNotFoundError` is raised.
   - Request device allocation from `cuda_budget.py`; verify that it returns an available device ordinal or sets CPU fallback without locking threads.

### Test Suite 2: Physics Invariants, Memory & IPC (`tests/core/test_physics_integrity_part4.py`)
1. **`test_hdf5_pes_store_swmr_concurrent_writes()` (Suggestion #34):**
   - Initialize a `PESStore` instance.
   - Launch 4 concurrent threads, each writing 20 distinct calculation coordinate entries (`entry_id`) with 3D coordinate arrays and QCSchema metadata.
   - Assert that all 80 entries are successfully committed without data loss.
   - Read back entries in SWMR mode and verify array values and checksums.
   - Verify that `shutil.copyfile` was never invoked and that disk space remained bounded.
2. **`test_ipc_socket_payload_framing_and_truncation()` (Suggestion #35):**
   - Spin up `HMACSocketServer` on a dynamic loopback port.
   - Connect a raw TCP client, satisfy the HMAC handshake, send a 4-byte header specifying `payload_len = 1000`, but transmit only 200 bytes before closing the socket.
   - Assert that `HMACSocketServer` detects the truncation, logs the failure, and unblocks waiting callers by raising `TruncatedPayloadError`.
   - Send a packet specifying `payload_len = 500 * 1024 * 1024` (500 MB); assert that the server immediately rejects the packet with `OversizedPayloadError`.
3. **`test_shared_memory_raii_and_weakref_cleanup()` (Suggestion #36):**
   - Allocate a `SharedMemoryBuffer` from a 5000-element NumPy array using a `with SharedMemoryBuffer.from_array(arr) as shm_buf:` block.
   - Read the array back using `SharedMemoryBuffer.read_from_descriptor(shm_buf.descriptor)`. Assert numerical identity.
   - Exit the context manager; verify that the segment is unlinked and no longer accessible via `multiprocessing.shared_memory.SharedMemory(name=shm_buf.shm.name)`.
   - Allocate a buffer outside a context manager and delete the reference (`del shm_buf; gc.collect()`). Assert that the `weakref.finalize` hook unlinks the OS segment automatically.
4. **`test_mendeleev_mass_invariants_and_zero_mass_rejection()` (Suggestion #38):**
   - Pass valid molecules (H2O, CH4) through `MolecularStructureData.validate_and_resolve_molecular_data()`. Assert masses match dynamic Mendeleev CIAAW atomic weights.
   - Ingest an exotic transuranic element without standard CIAAW weights (e.g. element 119) without specifying an isotope number. Assert that `MendeleevInvariantError` is raised and that mass `0.0` is never returned.
   - Provide an explicit isotope (e.g., `isotopes=[252]`); assert that the mass resolves strictly to $> 0.0$ u [M].
5. **`test_spin_contamination_and_hessian_domain_exceptions()` (Suggestion #39):**
   - Provide a QC result dictionary with $\langle S^2 \rangle_{\text{calc}} = 1.25$ for a singlet reference ($S^2_{\text{ideal}} = 0.0$). Assert that `QCResultsSchema.validate_qc_results()` raises `SpinContaminationError`, with attributes `s2_calc`, `s2_ref`, and `deviation_percent`.
   - Provide an asymmetric Hessian ($|H_{01} - H_{10}| = 0.05$). Assert that validation raises `HessianSymmetryError`.
   - Assert that both errors inherit from `QCValidationError` and can be caught programmatically to trigger swarm method pivots.

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock & Zero-Stub Verification:**
   - Scan repository diffs across all modified files. Zero occurrences of `unittest.mock`, `MagicMock`, `@patch`, `TODO`, `pass`, or `NotImplementedError` permitted.
2. **Full Test Suite Execution:**
   - Execute `pytest tests/core/test_architecture_part4.py tests/core/test_physics_integrity_part4.py`.
   - 100% of authored tests must pass with physical I/O, actual IPC loopback transmissions, real OS shared memory allocations, and genuine multi-threaded concurrency.
3. **Cross-Platform Path Hygiene:**
   - All paths must use `pathlib.Path.resolve()`. Zero hardcoded Windows drive letters (`C:`, `D:`) or POSIX root assumptions in library logic.
4. **Method Matrix Provenance Compliance:**
   - Dynamic mass retrieval strictly through `mendeleev`.
   - Provenance tags (`[M]`, `[D]`, `[E]`) verified on all physical metrics.
5. **Audit Handoff:**
   - Prepare clean implementation diffs and physical test execution outputs for formal review by `cochem-audit` and `adversary`.

---

## 6. Agent Council Adversarial Audit & Ratification Record

### Adversarial Audit Dispatch Log
- **Peer Auditor 1 (`cochem-audit`):** Dispatched to Conversation ID `c2888a7d-16d6-4d1b-b0d6-c189f2f760d7`.
- **Peer Auditor 2 (`adversary`):** Dispatched to Conversation ID `bc253b24-769e-4521-affa-7e39bc7ebcf8`.
- **Audit Mandate Status:** Active audit requests verified and registered in `swarm_state.json`.

### Audit Evaluation & Verdict

| Audit Category | Evaluation Criterion | Verdict |
| :--- | :--- | :--- |
| **Configuration Authority** | Fail-fast TOML parsing diagnostics with `ConfigurationParseError`; zero exception swallowing | **PASS (VERIFIED)** |
| **Diagnostics Preservation** | Sandbox teardown preserves primary electronic structure exceptions during OS lock collisions | **PASS (VERIFIED)** |
| **Air-Gap Storage Atomicity** | Decoupled publish commit from scratch teardown; immutable read-only Source Tier ($T_{\text{src}}$) | **PASS (VERIFIED)** |
| **PES Store Concurrency** | Eradication of monolithic file copies; Single-Master & SWMR HDF5 synchronization with chunk pre-allocation | **PASS (VERIFIED)** |
| **IPC Transport Safety** | Enforced 256 MB payload ceiling; deterministic `TruncatedPayloadError` signaling on socket termination | **PASS (VERIFIED)** |
| **Memory Lifecycle RAII** | Context manager and `weakref.finalize` garbage collection for cross-platform OS shared memory | **PASS (VERIFIED)** |
| **Universal File Locking** | Complete eradication of `fcntl`/`msvcrt` primitives in favor of standardized `filelock.FileLock` | **PASS (VERIFIED)** |
| **Physical Mass Invariants** | Dynamic mass resolution via `mendeleev`; zero null fallbacks ($m_i > 0.0$ u [M]); `MendeleevInvariantError` | **PASS (VERIFIED)** |
| **Quantum Chemical Exceptions** | Domain-specific `SpinContaminationError` and `HessianSymmetryError` driving automated swarm pivots | **PASS (VERIFIED)** |
| **Hardware & Namespace** | Authoritative re-exports in `cochem_base.core`; dynamic non-locking GPU allocation under MPS | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero mocks, zero synthetic loops across all 10 tasks and test specifications | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.