Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\20260903-061002-brainstorm\.in-progress\Perfected_SRS_Chunk_07_Core_Part_7_prompts.md.
Original prompt:
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 7: Suggestions #61–#70)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §6.4, §6.10, §8.2, §8.3, §8.4, §8A, §8A.4, §8B.4, §8B.6, §8C, §9A, §9B, Table 3, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Storage Air-Gap Architecture (Source $T_{\text{src}}$ immutable read-only, Ephemeral Scratch $T_{\text{scr}}$ isolated, State & Artifacts $T_{\text{state}}/T_{\text{export}}$ read-write cryptographic commitments)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- Dynamic Mendeleev Invariant Mandate (`from mendeleev import element`, zero hardcoded atomic masses, strict dynamic IUPAC/CIAAW physical mass retrieval)
- FAIR Principles Compliance (F1, F2, A1, I1, I2, I3, R1, R1.1, R1.2, R1.3)
- MolSSI QCSchema v1 Compliance (`schema_name="qcschema_output"`, `schema_version=1`, explicit `AtomicResult` mapping)
- IETF RFC 8785 JSON Canonicalization Scheme (JCS) §3.2.2.3 IEEE 754 Number-to-String formatting mandate
- Cross-Platform Concurrency Directive (Thread-safe SWMR HDF5 with `threading.RLock()` and `filelock.FileLock`, non-blocking CUDA stream handling under NVIDIA MPS isolation, strictly no POSIX `fcntl` on network filesystems)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #61 through #70 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical vulnerabilities across long-term archival data persistence, RFC 8785 canonical serialization parity, quasi-harmonic thermodynamic provenance logging, machine-actionable exception architectures, in-place HDF5 SWMR chunk resizing, cached dynamic mass resolution without GPU context stalls, lazy zero-cost module initialization, ephemeral sandbox memory leaks, low-overhead process monitoring, and cached session scratch verification.

Specific implementation targets include:
1. Injecting a mandatory `schema_version: int = 1` field into all Pydantic models across `cochem_base.core.models`, enforcing `model_config = ConfigDict(frozen=True, extra="forbid")`, and establishing an automated schema migration dispatch protocol supporting long-term backward-compatible deserialization (FAIR F2, I1, R1).
2. Implementing an RFC 8785-compliant IEEE 754 Number-to-String formatting kernel in `cochem_base.core.cochem_crypto.canonicalize_json` to eliminate cross-platform SHA-256 hash divergence caused by standard Python `float.__repr__` formatting.
3. Embedding all quasi-harmonic thermodynamic parameters (`low_freq_cutoff_cm1`, `damping_model="grimme_quasi_rrho"`, `temperature_k`, `pressure_atm=1.0`) into `DAGNode.payload["thermodynamics_provenance"]` metadata dictionaries to guarantee 100% reproducible vibrational free energies and Boltzmann populations (FAIR R1.2, Method Matrix §8B.4).
4. Standardizing all custom exceptions across `cochem_base.core` by subclassing a base `CoChemError` class and attaching machine-actionable error codes (e.g. `CoordinateShapeError` with code `COCHEM_E_INVALID_COORD_SHAPE`, `AirGapBoundaryError` with code `COCHEM_E_AIRGAP_BREACH`) to support automated ETL triage (FAIR A1, I1).
5. Refactoring `PESStore.write_entry()` to eliminate quadratic `shutil.copyfile` latency degradation, implementing in-place HDF5 SWMR chunk resizing (`ds.resize(new_len, axis=0)`) with dual-layer synchronization (`threading.RLock()` and cross-platform `filelock.FileLock`) and strict Tripartite Air-Gap path boundary enforcement.
6. Applying `@functools.lru_cache(maxsize=256)` to all dynamic Mendeleev mass resolution routines in `cochem_base.core_engine`, ensuring mass lookups execute in CPU precomputation without blocking active CUDA streams or locking GPU context workers under NVIDIA Multi-Process Service (MPS) daemon isolation (§8A.4).
7. Refactoring `_build_element_cache()` in `cochem_base.core.mendeleev_invariants` into a lazy, thread-safe singleton initialization pattern to eliminate the $200\text{--}600\text{ ms}$ module import lag on multiprocessing worker spawn pools.
8. Purging unbounded `atexit` callbacks in `cochem_base.core.cochem_sandbox.SandboxContext` by explicitly invoking `atexit.unregister(self.cleanup)` upon context exit, while enforcing strict dynamic sandbox root containment in Tier 3 (`$COCH_SCRATCH`).
9. Replacing recursive full-system process tree discovery (`psutil.Process().children(recursive=True)`) in `ProcessTreeManager` with direct polling across explicitly registered child PIDs in `_tracked`, reducing monitoring CPU consumption by $>80\%$ and eliminating quantum chemistry kernel cache perturbation.
10. Decoupling the 64 KB binary physical I/O integrity probe in `cochem_core_subprocess_broker.py` from individual subprocess invocations by implementing a session-level scratch verification cache with a configurable time-to-live ($\text{TTL} = 300\text{ s}$) keyed on workspace path.

All code modifications must be accompanied by comprehensive, zero-mock unit and integration tests executing real Mendeleev lookups, real IEEE 754 serialization roundtrips, real HDF5 SWMR dataset extensions, physical multi-process reaper monitoring, and real subprocess executions.

---

## 2. Target Files & Deliverable Manifest

### Core Models, Exceptions & Cryptographic Modules
1. `src/cochem_base/core/models.py` (Suggestions #61, #64)
2. `src/cochem_base/core/exceptions.py` (Suggestion #64)
3. `src/cochem_base/core/cochem_crypto.py` (Suggestion #62)
4. `src/cochem_base/core/cochem_provenance.py` (Suggestion #63)

### Engine, Storage & Concurrency Architecture Modules
5. `src/cochem_base/core/ipc/serializer.py` (Suggestion #65)
6. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestion #65)
7. `src/cochem_base/core_engine/cochem_mass_resolver.py` (Suggestion #66)
8. `src/cochem_base/core/mendeleev_invariants.py` (Suggestion #67)
9. `src/cochem_base/core/cochem_sandbox.py` (Suggestion #68)
10. `src/cochem_base/core/process_reaper.py` (Suggestion #69)
11. `src/cochem_base/core_engine/cochem_core_subprocess_broker.py` (Suggestion #70)

### Zero-Mock Test Suite Deliverables
12. `tests/core/test_physics_integrity_part7.py` (Validating Suggestions #61, #62, #63, #64, #66)
13. `tests/core/test_architecture_part7.py` (Validating Suggestions #65, #67, #68, #69, #70)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Pydantic Model Versioning & Schema Migration Dispatch (Suggestion #61)]
- **Files Affected:** `src/cochem_base/core/models.py`, `src/cochem_base/core/exceptions.py`
- **Problem Statement:**
  Archival data records generated by older versions of CoChem cannot be ingested by newer versions because models in `cochem_base.core.models` lack an explicit `schema_version` attribute and schema migration hooks. When a new field is added to a Pydantic model configured with `extra="forbid"`, deserializing older records missing that field triggers a fatal `ValidationError`, destroying multi-year scientific reproducibility and violating FAIR Principles F2, I1, and R1.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/models.py`, define global schema constants:
     ```python
     CURRENT_CORE_SCHEMA_VERSION: int = 1
     ```
  2. Inject a mandatory schema version attribute with a default into all core data models (e.g. `MolecularTopology`, `QCSchemaInput`, `QCSchemaOutput`, `PESPointRecord`, `CalculationJobPayload`, `AtomicResult`):
     ```python
     schema_version: int = Field(
         default=CURRENT_CORE_SCHEMA_VERSION,
         description="Semantic schema version for archival data deserialization and migration contracts."
     )
     ```
  3. Enforce strict immutability and forbid extraneous undeclared fields:
     ```python
     model_config = ConfigDict(frozen=True, extra="forbid")
     ```
  4. Implement an extensible schema migration registry and dispatcher:
     ```python
     MigrationCallable = Callable[[Dict[str, Any]], Dict[str, Any]]
     _MIGRATION_REGISTRY: Dict[Tuple[str, int], MigrationCallable] = {}

     def register_migration(model_name: str, from_version: int) -> Callable[[MigrationCallable], MigrationCallable]:
         """Decorator registering a transformation function from a specific schema version to from_version + 1."""
         def decorator(func: MigrationCallable) -> MigrationCallable:
             _MIGRATION_REGISTRY[(model_name, from_version)] = func
             return func
         return decorator

     def migrate_payload(payload: Dict[str, Any], target_model: Type[BaseModel]) -> Dict[str, Any]:
         """Migrates a raw dictionary payload sequentially up to target_model's current schema_version."""
         model_name = target_model.__name__
         current_version = payload.get("schema_version", 0)
         target_version = getattr(target_model, "CURRENT_VERSION", CURRENT_CORE_SCHEMA_VERSION)

         data = dict(payload)
         while current_version < target_version:
             key = (model_name, current_version)
             if key not in _MIGRATION_REGISTRY:
                 raise SchemaMigrationError(
                     f"No migration path registered for {model_name} from version {current_version} to {current_version + 1}.",
                     error_code="COCHEM_E_SCHEMA_MIGRATION_FAILED",
                     details={"model": model_name, "from_version": current_version, "target_version": target_version}
                 )
             data = _MIGRATION_REGISTRY[key](data)
             current_version = data.get("schema_version", current_version + 1)

         return data
     ```
  5. Provide a classmethod on all versioned models:
     ```python
     @classmethod
     def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
         """Parses a dictionary, executing automated migrations if schema_version is older than current."""
         migrated = migrate_payload(data, cls)
         return cls.model_validate(migrated)
     ```

---

### [Task 2: RFC 8785-Compliant IEEE 754 Float Canonicalization Kernel (Suggestion #62)]
- **Files Affected:** `src/cochem_base/core/cochem_crypto.py`
- **Problem Statement:**
  Cryptographic hashes of canonical JSON payloads diverge between Python and external verifiers (in Node.js, Go, Rust) because `canonicalize_json` relies on Python's built-in `json.dumps()` for float formatting. RFC 8785 (JSON Canonicalization Scheme - JCS) §3.2.2.3 strictly mandates the ECMAScript IEEE 754 Number-to-String formatting algorithm. Python's `float.__repr__` outputs exponential notations with 2-digit padded exponents (e.g. `1e-05`) or differing precision thresholds, breaking deterministic cross-platform SHA-256 verification [M].
- **Implementation Requirements:**
  1. In `src/cochem_base/core/cochem_crypto.py`, implement a dedicated RFC 8785 ECMAScript IEEE 754 float string formatting kernel:
     ```python
     def format_rfc8785_float(val: float) -> str:
         """Formats an IEEE 754 double-precision float strictly adhering to RFC 8785 §3.2.2.3 (ECMAScript Number::toString).
         
         Rules:
         - NaN and Infinities are strictly disallowed in JSON (raise ValueError).
         - Signed zero (-0.0) must format as '0'.
         - Absolute value in range 1e-6 <= |val| < 1e21 formats in fixed decimal notation without unnecessary trailing zeros.
         - Absolute value < 1e-6 or >= 1e21 formats in exponential notation with lowercase 'e' and exponent without leading zero.
         """
         import math
         if math.isnan(val) or math.isinf(val):
             raise ValueError(f"RFC 8785 forbids non-finite float values: {val}")
         if val == 0.0:
             return "0"

         # ECMAScript Number-to-String algorithm compliance:
         # Use standard 17-digit precision formatting
         s = f"{val:.17g}"
         
         # Normalize scientific notation exponent (e.g., '1e-05' -> '1e-5', '1e+05' -> '1e+5')
         if 'e' in s:
             base, exp = s.split('e')
             exp_sign = exp[0]
             exp_val = exp[1:].lstrip('0') or '0'
             s = f"{base}e{exp_sign}{exp_val}"
         
         # Handle corner-case ranges where Python emits scientific notation but ECMAScript mandates fixed:
         # 1e-6 <= |val| < 1e-5 (e.g., 0.000001 -> '0.000001', not '1e-6')
         abs_val = abs(val)
         if 1e-6 <= abs_val < 1e-4 and 'e' in s:
             # Expand to decimal
             s = f"{val:.10f}".rstrip('0').rstrip('.')
             
         return s
     ```
  2. Implement `canonicalize_json(data: Any) -> bytes`:
     ```python
     def canonicalize_json(data: Any) -> bytes:
         """Serializes arbitrary Python data structures to deterministic UTF-8 bytes adhering to RFC 8785 (JCS).
         
         - Lexicographical sorting of object keys by UTF-8 code point values.
         - Zero whitespace around delimiters (',' and ':').
         - IEEE 754 float formatting via format_rfc8785_float.
         - UTF-8 output without BOM.
         """
         return _serialize_jcs(data).encode("utf-8")

     def _serialize_jcs(obj: Any) -> str:
         if obj is None:
             return "null"
         elif isinstance(obj, bool):
             return "true" if obj else "false"
         elif isinstance(obj, int):
             return str(obj)
         elif isinstance(obj, float):
             return format_rfc8785_float(obj)
         elif isinstance(obj, str):
             import json
             return json.dumps(obj, ensure_ascii=False)
         elif isinstance(obj, (list, tuple)):
             items = [_serialize_jcs(item) for item in obj]
             return "[" + ",".join(items) + "]"
         elif isinstance(obj, dict):
             # Sort keys by UTF-16 code units / UTF-8 byte order
             sorted_keys = sorted(obj.keys(), key=lambda k: k.encode("utf-8"))
             pairs = [
                 json.dumps(k, ensure_ascii=False) + ":" + _serialize_jcs(obj[k])
                 for k in sorted_keys
             ]
             return "{" + ",".join(pairs) + "}"
         elif hasattr(obj, "model_dump"):
             return _serialize_jcs(obj.model_dump(mode="json"))
         else:
             raise TypeError(f"Object of type {type(obj).__name__} is not RFC 8785 JCS serializable")
     ```
  3. Ensure that `hash_canonical_json(data: Any, algorithm: str = "sha256") -> str` in `cochem_crypto.py` calls `canonicalize_json(data)`.

---

### [Task 3: Quasi-Harmonic Thermodynamic Parameter Provenance Logging (Suggestion #63)]
- **Files Affected:** `src/cochem_base/core/cochem_provenance.py`, `src/cochem_base/core/models.py`
- **Problem Statement:**
  External researchers cannot reproduce the exact Boltzmann populations computed by `compute_boltzmann_weights()` because the function applies Grimme's quasi-RRHO low-frequency interpolation using a procedural $100\text{ cm}^{-1}$ cutoff without logging the cutoff, rotor cutoff, or damping scheme into node metadata. Because low-frequency torsional modes in fluxional complexes dominate vibrational entropy, shifting the cutoff between $50$ and $150\text{ cm}^{-1}$ alters relative conformer free energies by up to $1.5\text{ kcal/mol}$ [D], violating FAIR Principle R1.2 and Method Matrix v4 §8B.4 / §9B.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/models.py`, define the provenance model:
     ```python
     class ThermodynamicsProvenance(BaseModel):
         """Provenance metadata for quasi-harmonic thermodynamic corrections and Boltzmann weighting."""
         damping_model: str = Field(
             default="grimme_quasi_rrho",
             description="Vibrational entropy damping model (e.g. grimme_quasi_rrho, truhlar_quasi_harmonic, harmonic)."
         )
         low_freq_cutoff_cm1: float = Field(
             default=100.0,
             description="Low-frequency cutoff/interpolation threshold in wavenumbers (cm^-1)."
         )
         temperature_k: float = Field(
             default=298.15,
             description="Thermodynamic temperature in Kelvin."
         )
         pressure_atm: float = Field(
             default=1.0,
             description="Standard state pressure in atmospheres."
         )
         rotor_cutoff_cm1: Optional[float] = Field(
             default=None,
             description="Free-rotor transition threshold if using Head-Gordon or multi-cutoff damping."
         )
         provenance_tag: str = Field(
             default="[D]",
             description="Method Matrix provenance marker ([M] measured, [D] derived, [E] estimated)."
         )
         schema_version: int = Field(default=CURRENT_CORE_SCHEMA_VERSION)
         model_config = ConfigDict(frozen=True, extra="forbid")
     ```
  2. Refactor `compute_boltzmann_weights()` in `src/cochem_base/core/cochem_provenance.py`:
     ```python
     def compute_boltzmann_weights(
         free_energies_kcal_mol: Sequence[float],
         temperature_k: float = 298.15,
         low_freq_cutoff_cm1: float = 100.0,
         damping_model: str = "grimme_quasi_rrho",
         pressure_atm: float = 1.0,
         dag_node: Optional[Any] = None
     ) -> Tuple[List[float], ThermodynamicsProvenance]:
         """Computes normalized Boltzmann weights while recording thermodynamic provenance.
         
         Weights: w_i = exp(-Delta G_i / (R * T)) / sum(exp(-Delta G_j / (R * T)))
         Logs ThermodynamicsProvenance into dag_node.payload['thermodynamics_provenance'] if provided.
         """
         import numpy as np
         # R in kcal / (mol * K)
         R_KCAL_MOL_K: float = 0.00198720425864083
         
         G = np.asarray(free_energies_kcal_mol, dtype=np.float64)
         if len(G) == 0:
             return [], ThermodynamicsProvenance(
                 damping_model=damping_model,
                 low_freq_cutoff_cm1=low_freq_cutoff_cm1,
                 temperature_k=temperature_k,
                 pressure_atm=pressure_atm
             )

         delta_G = G - np.min(G)
         beta = 1.0 / (R_KCAL_MOL_K * temperature_k)
         unnorm_weights = np.exp(-beta * delta_G)
         weights = (unnorm_weights / np.sum(unnorm_weights)).tolist()

         prov = ThermodynamicsProvenance(
             damping_model=damping_model,
             low_freq_cutoff_cm1=float(low_freq_cutoff_cm1),
             temperature_k=float(temperature_k),
             pressure_atm=float(pressure_atm),
             provenance_tag="[D]"
         )

         if dag_node is not None and hasattr(dag_node, "payload") and isinstance(dag_node.payload, dict):
             dag_node.payload["thermodynamics_provenance"] = prov.model_dump(mode="json")

         return weights, prov
     ```

---

### [Task 4: Machine-Actionable Exception Hierarchy & Typed Error Codes (Suggestion #64)]
- **Files Affected:** `src/cochem_base/core/exceptions.py`, `src/cochem_base/core/models.py`
- **Problem Statement:**
  Coordinate shape validation and core integrity checks currently raise generic `ValueError` or unformatted standard library exceptions. Automated ingest and high-throughput execution pipelines cannot programmatically distinguish dimensionality failures, unphysical nuclear charges, schema version conflicts, or air-gap breaches without fragile regex parsing of error strings, violating FAIR Principles A1 and I1 and Global Swarm Protocols.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/exceptions.py`, define the root structured exception class and specialized error codes:
     ```python
     from typing import Optional, Dict, Any

     class CoChemError(Exception):
         """Base error class for all CoChem operations with machine-actionable error codes."""
         def __init__(
             self,
             message: str,
             error_code: str = "COCHEM_E_GENERIC",
             details: Optional[Dict[str, Any]] = None
         ) -> None:
             super().__init__(f"[{error_code}] {message}")
             self.message = message
             self.error_code = error_code
             self.details = details or {}

     class CoordinateShapeError(CoChemError):
         """Raised when molecular coordinate arrays violate dimensionality constraints (e.g. not N x 3)."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_INVALID_COORD_SHAPE", details=details)

     class AirGapBoundaryError(CoChemError):
         """Raised when an operation attempts to write to a read-only or out-of-tier filesystem boundary."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_AIRGAP_BREACH", details=details)

     class SchemaMigrationError(CoChemError):
         """Raised when deserializing a payload lacking a valid migration path to current schema_version."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_SCHEMA_MIGRATION_FAILED", details=details)

     class PESStorageError(CoChemError):
         """Raised when HDF5 SWMR store operations fail or encounter lock contention."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_PES_STORAGE_FAILURE", details=details)

     class ProcessReaperError(CoChemError):
         """Raised when process termination or resource sampling fails unexpectedly."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_PROCESS_REAPER_FAILURE", details=details)

     class SubprocessBrokerError(CoChemError):
         """Raised when isolated subprocess execution fails pre-flight or runtime contracts."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_SUBPROCESS_BROKER_FAILURE", details=details)

     class ThermodynamicsParameterError(CoChemError):
         """Raised when required quasi-harmonic parameters are missing from thermodynamic calculations."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_THERMO_PARAM_MISSING", details=details)
     ```
  2. In `src/cochem_base/core/models.py`, refactor `MolecularTopology` validator to raise `CoordinateShapeError`:
     ```python
     @field_validator("coordinates", mode="after")
     @classmethod
     def validate_coordinates_shape(cls, v: List[List[float]]) -> List[List[float]]:
         for idx, atom_coord in enumerate(v):
             if len(atom_coord) != 3:
                 raise CoordinateShapeError(
                     f"Atom index {idx} has dimensionality {len(atom_coord)}; expected exactly 3 (x, y, z).",
                     details={"atom_index": idx, "actual_len": len(atom_coord), "expected_len": 3}
                 )
         return v
     ```

---

### [Task 5: In-Place HDF5 SWMR Chunk Resizing & Dual-Layer Locking (Suggestion #65)]
- **Files Affected:** `src/cochem_base/core/ipc/serializer.py`, `src/cochem_base/core_engine/cochem_core_pes_store.py`
- **Problem Statement:**
  `PESStore.write_entry()` currently copies the entire pre-existing HDF5 database to a temporary file via `shutil.copyfile` before writing, implementing scalar whole-file atomic replacement semantics. Appending $N$ grid points sequentially to a database of size $S$ generates $O(N \cdot S)$ disk I/O, writing gigabytes of redundant copies [M], invalidating open SWMR reader file descriptors, causing severe multi-process lock contention, and failing to validate Tripartite Air-Gap path boundaries.
- **Implementation Requirements:**
  1. Eliminate all calls to `shutil.copyfile` and `os.replace` in `PESStore.write_entry()` and HDF5 serialization routines.
  2. Implement in-place HDF5 SWMR chunk resizing:
     - On dataset creation: specify `maxshape=(None, ...)` on the initial dimension, `chunks=(512, ...)` or appropriate chunk points, and compression filters (`gzip`, `shuffle`, `fletcher32`).
     - On append: invoke `dataset.resize(new_length, axis=0)`, slice-assign the new record, and call `dataset.flush()` and `file.flush()` to ensure SWMR visibility.
  3. Implement dual-layer concurrency locking:
     - In-process: module-level `_HDF5_MEM_LOCK = threading.RLock()` guarding C-library HDF5 API calls.
     - Cross-process IPC: use `filelock.FileLock` operating on node-local scratch storage (`$COCH_SCRATCH`), with a configurable timeout (default `30.0` s). Strictly prohibit lockfile allocation on networked filesystems (Lustre/GPFS/NFS).
  4. Enforce Tripartite Air-Gap boundary validation:
     ```python
     def validate_airgap_write_path(target_path: Path) -> Path:
         """Validates that target write path resides strictly within Tier 4 ($COCH_STATE) or Tier 3 ($COCH_SCRATCH).
         Raises AirGapBoundaryError if write is attempted in Tier 1 ($COCH_SRC) or Tier 2 ($COCH_DATA).
         """
         resolved = target_path.resolve()
         src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
         data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()

         if src_dir.exists() and src_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Air-gap boundary violation: Cannot write PES data to read-only Tier 1 ($COCH_SRC): {resolved}",
                 details={"target_path": str(resolved), "tier": "Tier 1 ($COCH_SRC)"}
             )
         if data_dir.exists() and data_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Air-gap boundary violation: Cannot write PES data to immutable Tier 2 ($COCH_DATA): {resolved}",
                 details={"target_path": str(resolved), "tier": "Tier 2 ($COCH_DATA)"}
             )
         return resolved
     ```
  5. Refactor `PESStore.write_entry(point: PESPointRecord) -> None`:
     - Validate target path with `validate_airgap_write_path(self.file_path)`.
     - Acquire dual-layer lock (`with _HDF5_MEM_LOCK: with filelock.FileLock(self.lock_path, timeout=30.0):`).
     - Open HDF5 with `libver='latest'`, resize dataset along axis 0, commit point attributes, flush buffers.

---

### [Task 6: Dynamic Mendeleev Mass Resolution In-Memory Caching (Suggestion #66)]
- **Files Affected:** `src/cochem_base/core_engine/cochem_mass_resolver.py`
- **Problem Statement:**
  Core solvers query dynamic Mendeleev masses synchronously without memoization. Because `mendeleev.element(symbol)` executes SQL SELECT queries against the bundled SQLite database on disk ($\sim 100\ \mu\text{s}$ per query [M]), multidimensional Discrete Variable Representation (DVR) solvers and Eckart frame projections query masses tens of thousands of times across multidimensional coordinate meshes. Furthermore, synchronous SQLite queries on the host thread stall non-blocking CUDA streams and lock GPU context workers under NVIDIA Multi-Process Service (MPS) daemon isolation (§8A.4).
- **Implementation Requirements:**
  1. Create or refactor `src/cochem_base/core_engine/cochem_mass_resolver.py`.
  2. Implement `@functools.lru_cache(maxsize=256)` on dynamic mass resolution functions:
     ```python
     from functools import lru_cache
     from typing import Union, Optional
     import mendeleev
     from cochem_base.core.exceptions import CoChemError

     class IsotopeMassResolutionError(CoChemError):
         """Raised when requested isotope cannot be resolved to physical mass."""
         def __init__(self, message: str, details: Optional[dict] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_ISOTOPE_NOT_FOUND", details=details)

     @lru_cache(maxsize=256)
     def get_dynamic_atomic_mass(symbol_or_z: Union[str, int]) -> float:
         """Returns standard atomic weight from Mendeleev with LRU memory caching.
         Reduces latency from ~100 us (SQLite I/O) to ~50 ns (in-memory lookup) [M].
         """
         el = mendeleev.element(symbol_or_z)
         if el.atomic_weight is not None:
             return float(el.atomic_weight)
         if el.mass is not None:
             return float(el.mass)
         raise IsotopeMassResolutionError(
             f"Atomic weight unavailable for element '{symbol_or_z}'.",
             details={"element": symbol_or_z}
         )

     @lru_cache(maxsize=256)
     def get_dynamic_isotopic_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
         """Returns exact physical isotopic nuclear mass from Mendeleev with LRU memory caching.
         Guarantees zero fallback to terrestrial average atomic weights.
         """
         el = mendeleev.element(symbol_or_z)
         for iso in el.isotopes:
             if iso.mass_number == int(mass_number):
                 if iso.mass is not None and float(iso.mass) > 0.0:
                     return float(iso.mass)
         raise IsotopeMassResolutionError(
             f"Isotope '{el.symbol}-{mass_number}' cannot be resolved to a physical mass.",
             details={"element": el.symbol, "mass_number": mass_number}
         )
     ```
  3. Ensure all DVR, PES store, and moment-of-inertia calculation routines import from `cochem_mass_resolver.py`.
  4. Guarantee that mass lookup arrays are pre-resolved on the host CPU prior to launching asynchronous GPU kernels, preventing CUDA stream stalls or GPU context blocking under NVIDIA MPS daemon isolation (§8A.4).

---

### [Task 7: Lazy Thread-Safe Singleton for Mendeleev Invariants (Suggestion #67)]
- **Files Affected:** `src/cochem_base/core/mendeleev_invariants.py`
- **Problem Statement:**
  Importing `cochem_base.core.mendeleev_invariants` eagerly executes `_build_element_cache()` at top level, calling `_mendeleev_element(z)` 118 times from $Z=1$ to $Z=118$ and running 118 sequential SQLite queries. In multiprocessing architectures using the `spawn` context (Windows and HPC SLURM worker pools), every single worker process re-imports the module and re-runs all 118 SQL queries sequentially upon initialization, incurring a $200\text{--}600\text{ ms}$ startup penalty per spawned process [M].
- **Implementation Requirements:**
  1. Remove the eager module-level execution of `_build_element_cache()` at line 107 in `mendeleev_invariants.py`.
  2. Implement a thread-safe lazy singleton pattern:
     ```python
     import threading
     from typing import Dict, Optional, Any

     _ELEMENT_CACHE_LOCK = threading.Lock()
     _ELEMENT_CACHE: Optional[Dict[int, Any]] = None

     def get_element_cache() -> Dict[int, Any]:
         """Lazy thread-safe accessor for the 118-element Mendeleev invariants cache.
         Eliminates 200-600 ms top-level module import overhead across spawned worker processes [M].
         """
         global _ELEMENT_CACHE
         if _ELEMENT_CACHE is None:
             with _ELEMENT_CACHE_LOCK:
                 if _ELEMENT_CACHE is None:
                     _ELEMENT_CACHE = _build_element_cache()
         return _ELEMENT_CACHE
     ```
  3. Refactor all external functions in `mendeleev_invariants.py` (e.g. `get_element_data(z)`, `get_symbol(z)`, `get_atomic_number(symbol)`) to query `get_element_cache()` rather than directly referencing a global module dictionary.
  4. Ensure module import time drops to $< 5\text{ ms}$ [M].

---

### [Task 8: Ephemeral Sandbox Lifecycle & `atexit` Leak Elimination (Suggestion #68)]
- **Files Affected:** `src/cochem_base/core/cochem_sandbox.py`
- **Problem Statement:**
  `SandboxContext.__enter__()` registers `atexit.register(self.cleanup)` on every entry, but `cleanup()` and `__exit__()` fail to call `atexit.unregister(self.cleanup)`. In multi-stage calculation campaigns creating hundreds of ephemeral workspaces, the Python interpreter retains strong references to completed `SandboxContext` instances and their associated configurations in `atexit._nref`, causing unbounded heap memory accumulation and multi-second shutdown stalls during process termination.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/cochem_sandbox.py`, update `SandboxContext`:
     ```python
     import atexit
     import shutil
     from pathlib import Path
     from typing import Optional
     from cochem_base.core.exceptions import AirGapBoundaryError

     class SandboxContext:
         """Manages ephemeral calculation workspaces adhering to Tripartite Air-Gap Domain C."""
         def __init__(self, scratch_root: Optional[Path] = None, prefix: str = "cochem_job_") -> None:
             self.scratch_root = self._resolve_and_validate_scratch_root(scratch_root)
             self.prefix = prefix
             self.path: Optional[Path] = None
             self._cleaned: bool = False

         def _resolve_and_validate_scratch_root(self, root: Optional[Path]) -> Path:
             if root is None:
                 root = Path(os.environ.get("COCH_SCRATCH", "/tmp/cochem_scratch"))
             resolved = root.resolve()

             # Enforce Tripartite Air-Gap: Prohibit sandbox creation in Tier 1 ($COCH_SRC) or Tier 2 ($COCH_DATA)
             src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
             data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()
             if src_dir.exists() and src_dir in resolved.parents:
                 raise AirGapBoundaryError(
                     f"Cannot create ephemeral sandbox inside Tier 1 ($COCH_SRC): {resolved}",
                     details={"attempted_path": str(resolved), "tier": "Tier 1"}
                 )
             if data_dir.exists() and data_dir in resolved.parents:
                 raise AirGapBoundaryError(
                     f"Cannot create ephemeral sandbox inside Tier 2 ($COCH_DATA): {resolved}",
                     details={"attempted_path": str(resolved), "tier": "Tier 2"}
                 )
             return resolved

         def __enter__(self) -> "SandboxContext":
             import tempfile
             self.scratch_root.mkdir(parents=True, exist_ok=True)
             self.path = Path(tempfile.mkdtemp(prefix=self.prefix, dir=self.scratch_root))
             self._cleaned = False
             atexit.register(self.cleanup)
             return self

         def cleanup(self) -> None:
             """Idempotently cleans up scratch directory and removes atexit registration."""
             if self._cleaned:
                 return
             self._cleaned = True
             atexit.unregister(self.cleanup)
             if self.path is not None and self.path.exists():
                 try:
                     shutil.rmtree(self.path, ignore_errors=True)
                 except Exception:
                     pass

         def __exit__(self, exc_type, exc_val, exc_tb) -> None:
             self.cleanup()
     ```
  2. Verify that repeated entries and exits from `SandboxContext` result in zero net change to `len(atexit._nref)` or internal callback queues.

---

### [Task 9: Direct Child PID Monitoring in Process Reaper (Suggestion #69)]
- **Files Affected:** `src/cochem_base/core/process_reaper.py`
- **Problem Statement:**
  Monitoring daemons periodically invoke `sample_process_tree_rss_bytes()` and `terminate_tree()` at short intervals ($0.1\text{--}1.0\text{ s}$) using `psutil.Process().children(recursive=True)`. The OS must traverse the entire system process table on every polling cycle, inducing significant host CPU consumption ($>15\%$), CPU cache eviction, and kernel thread contention on active compute cores dedicated to high-precision quantum chemical kernels (ORCA, CFOUR) and GPU MPS host workers (§8A.4).
- **Implementation Requirements:**
  1. In `src/cochem_base/core/process_reaper.py`, update `ProcessTreeManager`:
     - Maintain an explicit registry of active child PIDs:
       ```python
       self._tracked: Set[int] = set()
       ```
     - Provide registration methods:
       ```python
       def register_process(self, pid: int) -> None:
           """Explicitly registers a newly spawned subprocess PID for targeted telemetry and reaping."""
           if pid > 0:
               self._tracked.add(pid)

       def unregister_process(self, pid: int) -> None:
           """Removes a process PID upon normal exit."""
           self._tracked.discard(pid)
       ```
  2. Refactor `sample_process_tree_rss_bytes() -> int`:
     ```python
     def sample_process_tree_rss_bytes(self) -> int:
         """Samples memory consumption across tracked PIDs directly without traversing the full OS process table.
         Drops monitoring daemon CPU consumption by >80% [E] and preserves scout-and-anchor thread budgets.
         """
         total_rss = 0
         dead_pids = set()

         # Include parent process
         try:
             total_rss += self._parent_proc.memory_info().rss
         except (psutil.NoSuchProcess, psutil.AccessDenied):
             pass

         # Query tracked child PIDs directly
         for pid in list(self._tracked):
             try:
                 p = psutil.Process(pid)
                 total_rss += p.memory_info().rss
             except psutil.NoSuchProcess:
                 dead_pids.add(pid)
             except (psutil.AccessDenied, psutil.ZombieProcess):
                 pass

         self._tracked.difference_update(dead_pids)
         return total_rss
     ```
  3. In `terminate_tree(timeout: float = 5.0) -> None`:
     - Directly signal all PIDs in `_tracked` with `SIGTERM` (or `taskkill /PID` on Windows), wait up to `timeout` seconds, and escalate to `SIGKILL` only for stubborn processes.
     - Fall back to recursive system-wide `children(recursive=True)` discovery ONLY when detached orphan subprocesses are suspected.

---

### [Task 10: Session-Level Scratch Verification Cache with TTL (Suggestion #70)]
- **Files Affected:** `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`
- **Problem Statement:**
  `safe_subprocess_run()` invokes `verify_scratch_quota_and_io()` prior to executing `subprocess.Popen`. This function writes a 64 KB binary probe to disk, flushes the stream, invokes `os.fsync()`, reads back the file, computes two SHA-256 digests, and unlinks the probe file before every command. This synchronous barrier adds a $20\text{--}100\text{ ms}$ dispatch latency per execution [M] and floods clustered/networked filesystems (Lustre, GPFS, NFS) with redundant metadata journal flushes during high-throughput calculations.
- **Implementation Requirements:**
  1. In `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`, implement a thread-safe session-level scratch verification cache:
     ```python
     import time
     import os
     import hashlib
     from pathlib import Path
     from typing import Dict, Tuple, Optional
     from cochem_base.core.exceptions import AirGapBoundaryError, SubprocessBrokerError

     _SCRATCH_CACHE_LOCK = threading.Lock()
     # Maps resolved Path -> float (monotonic timestamp of last successful verification)
     _SCRATCH_VERIFICATION_CACHE: Dict[Path, float] = {}

     def verify_scratch_quota_and_io(
         scratch_dir: Path,
         ttl_seconds: float = 300.0,
         force: bool = False
     ) -> bool:
         """Verifies write, fsync, and SHA-256 read-back integrity on scratch_dir.
         Caches verification success for ttl_seconds to eliminate 20-100 ms dispatch latency per subprocess [M].
         Enforces Tripartite Air-Gap: scratch_dir must strictly reside within Tier 3 ($COCH_SCRATCH).
         """
         resolved = scratch_dir.resolve()

         # Air-gap boundary validation
         src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
         data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()
         if src_dir.exists() and src_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Cannot execute subprocess scratch operations in read-only Tier 1 ($COCH_SRC): {resolved}",
                 details={"path": str(resolved), "tier": "Tier 1"}
             )
         if data_dir.exists() and data_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Cannot execute subprocess scratch operations in immutable Tier 2 ($COCH_DATA): {resolved}",
                 details={"path": str(resolved), "tier": "Tier 2"}
             )

         now = time.monotonic()
         with _SCRATCH_CACHE_LOCK:
             if not force and resolved in _SCRATCH_VERIFICATION_CACHE:
                 last_verified = _SCRATCH_VERIFICATION_CACHE[resolved]
                 if (now - last_verified) < ttl_seconds:
                     return True

         # Perform physical 64 KB probe
         resolved.mkdir(parents=True, exist_ok=True)
         probe_file = resolved / f".io_probe_{os.getpid()}_{time.time_ns()}.bin"
         probe_data = os.urandom(64 * 1024)
         probe_hash = hashlib.sha256(probe_data).hexdigest()

         try:
             with open(probe_file, "wb") as f:
                 f.write(probe_data)
                 f.flush()
                 os.fsync(f.fileno())

             with open(probe_file, "rb") as f:
                 read_data = f.read()

             read_hash = hashlib.sha256(read_data).hexdigest()
             if read_hash != probe_hash:
                 raise SubprocessBrokerError(
                     f"Scratch I/O integrity probe failed: SHA-256 mismatch in {resolved}",
                     details={"scratch_dir": str(resolved), "expected": probe_hash, "actual": read_hash}
                 )
         finally:
             if probe_file.exists():
                 try:
                     probe_file.unlink()
                 except OSError:
                     pass

         with _SCRATCH_CACHE_LOCK:
             _SCRATCH_VERIFICATION_CACHE[resolved] = time.monotonic()

         return True
     ```
  2. In `safe_subprocess_run()`, call `verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0, force=False)` prior to executing `subprocess.Popen`.

---

## 4. Pytest Unit & Integration Test Specifications

### Deliverable 1: `tests/core/test_physics_integrity_part7.py`
This test suite verifies physics integrity across data models, serialization kernels, thermodynamic provenance, exception structures, and mass caching.

```python
import math
import os
import time
import pytest
from pydantic import ValidationError
from cochem_base.core.models import (
    MolecularTopology,
    CURRENT_CORE_SCHEMA_VERSION,
    register_migration,
    migrate_payload
)
from cochem_base.core.exceptions import (
    CoChemError,
    CoordinateShapeError,
    SchemaMigrationError,
    AirGapBoundaryError
)
from cochem_base.core.cochem_crypto import (
    format_rfc8785_float,
    canonicalize_json
)
from cochem_base.core.cochem_provenance import (
    compute_boltzmann_weights,
    ThermodynamicsProvenance
)
from cochem_base.core_engine.cochem_mass_resolver import (
    get_dynamic_atomic_mass,
    get_dynamic_isotopic_mass,
    IsotopeMassResolutionError
)

def test_pydantic_model_schema_version_and_migration():
    """Validates Suggestion #61: schema_version injection and automated backward-compatible migration."""
    # Test current model instantiation
    top = MolecularTopology(
        symbols=["H", "H"],
        coordinates=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
        molecular_charge=0,
        spin_multiplicity=1
    )
    assert top.schema_version == CURRENT_CORE_SCHEMA_VERSION

    # Register mock legacy migration from v0 to v1
    @register_migration("MolecularTopology", 0)
    def migrate_v0_to_v1(data):
        d = dict(data)
        d["schema_version"] = 1
        if "spin_multiplicity" not in d:
            d["spin_multiplicity"] = 1
        return d

    legacy_payload = {
        "schema_version": 0,
        "symbols": ["O", "H", "H"],
        "coordinates": [[0.0, 0.0, 0.0], [0.0, 0.75, 0.5], [0.0, -0.75, 0.5]],
        "molecular_charge": 0
    }
    migrated_top = MolecularTopology.from_archival_dict(legacy_payload)
    assert migrated_top.schema_version == 1
    assert migrated_top.spin_multiplicity == 1

def test_rfc8785_ieee754_canonical_float_formatting():
    """Validates Suggestion #62: ECMAScript IEEE 754 float formatting parity in canonicalize_json."""
    # Signed zero formatting
    assert format_rfc8785_float(0.0) == "0"
    assert format_rfc8785_float(-0.0) == "0"

    # Disallow NaN and Infinity
    with pytest.raises(ValueError):
        format_rfc8785_float(float("nan"))
    with pytest.raises(ValueError):
        format_rfc8785_float(float("inf"))

    # Exponential notation without leading zero in exponent
    assert format_rfc8785_float(1e-5) == "0.00001" or format_rfc8785_float(1e-5) == "1e-5"
    assert format_rfc8785_float(1e-7) == "1e-7"
    assert format_rfc8785_float(1e21) == "1e+21"

    # Canonicalize dictionary with sorted keys and floats
    payload = {"b": 1e-7, "a": -0.0, "c": [1, 2.5]}
    canonical_bytes = canonicalize_json(payload)
    # Keys must be sorted 'a', 'b', 'c', -0.0 as 0, 1e-7 without leading zero
    assert canonical_bytes == b'{"a":0,"b":1e-7,"c":[1,2.5]}'

def test_quasi_rrho_thermodynamics_provenance_logging():
    """Validates Suggestion #63: Quasi-harmonic thermodynamic parameter provenance logging."""
    class DummyNode:
        def __init__(self):
            self.payload = {}

    node = DummyNode()
    energies = [0.0, 0.5, 1.2]
    weights, prov = compute_boltzmann_weights(
        energies,
        temperature_k=298.15,
        low_freq_cutoff_cm1=100.0,
        damping_model="grimme_quasi_rrho",
        dag_node=node
    )
    assert len(weights) == 3
    assert math.isclose(sum(weights), 1.0, rel_tol=1e-6)
    assert "thermodynamics_provenance" in node.payload
    logged = node.payload["thermodynamics_provenance"]
    assert logged["damping_model"] == "grimme_quasi_rrho"
    assert logged["low_freq_cutoff_cm1"] == 100.0
    assert logged["temperature_k"] == 298.15
    assert logged["provenance_tag"] == "[D]"

def test_machine_actionable_exception_hierarchy():
    """Validates Suggestion #64: Structured exception hierarchy with machine-actionable error codes."""
    # Coordinate shape mismatch raises CoordinateShapeError
    with pytest.raises(CoordinateShapeError) as exc_info:
        MolecularTopology(
            symbols=["H"],
            coordinates=[[0.0, 0.0]], # 2D instead of 3D
            molecular_charge=0,
            spin_multiplicity=1
        )
    err = exc_info.value
    assert err.error_code == "COCHEM_E_INVALID_COORD_SHAPE"
    assert err.details["actual_len"] == 2
    assert err.details["expected_len"] == 3

def test_dynamic_mendeleev_mass_resolution_lru_cache():
    """Validates Suggestion #66: LRU memory caching on dynamic Mendeleev mass resolution."""
    # Warmup
    mass_c = get_dynamic_atomic_mass("C")
    assert math.isclose(mass_c, 12.011, rel_tol=1e-2)

    # Measure lookup latency for cached access
    start = time.perf_counter()
    for _ in range(1000):
        _ = get_dynamic_atomic_mass("C")
    cached_duration = time.perf_counter() - start

    # 1000 lookups should complete in less than 5 milliseconds
    assert cached_duration < 0.005

    # Nuclear isotopic masses
    mass_14c = get_dynamic_isotopic_mass("C", 14)
    assert math.isclose(mass_14c, 14.003241, rel_tol=1e-4)

    with pytest.raises(IsotopeMassResolutionError):
        get_dynamic_isotopic_mass("C", 999)
```

---

### Deliverable 2: `tests/core/test_architecture_part7.py`
This test suite verifies architecture, concurrency, air-gap boundaries, and OS-level lifecycle management.

```python
import os
import time
import atexit
import threading
import tempfile
from pathlib import Path
import pytest
import h5py
from cochem_base.core.exceptions import AirGapBoundaryError
from cochem_base.core.mendeleev_invariants import get_element_cache
from cochem_base.core.cochem_sandbox import SandboxContext
from cochem_base.core.process_reaper import ProcessTreeManager
from cochem_base.core_engine.cochem_core_subprocess_broker import (
    verify_scratch_quota_and_io,
    _SCRATCH_VERIFICATION_CACHE
)

def test_hdf5_swmr_inplace_resizing_and_airgap(tmp_path):
    """Validates Suggestion #65: In-place HDF5 SWMR chunk resizing and Air-Gap enforcement."""
    # Mock environment
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    os.environ["COCH_SRC"] = str(src_dir)

    # Attempting to write into Tier 1 ($COCH_SRC) must raise AirGapBoundaryError
    h5_src_path = src_dir / "store.h5"
    with pytest.raises(AirGapBoundaryError) as exc_info:
        from cochem_base.core.ipc.serializer import validate_airgap_write_path
        validate_airgap_write_path(h5_src_path)
    assert exc_info.value.error_code == "COCHEM_E_AIRGAP_BREACH"

    # Valid write into temporary scratch
    h5_scratch_path = tmp_path / "scratch" / "store.h5"
    h5_scratch_path.parent.mkdir()
    
    # Create SWMR dataset
    with h5py.File(h5_scratch_path, "w", libver="latest") as f:
        ds = f.create_dataset(
            "energies",
            shape=(1,),
            maxshape=(None,),
            chunks=(512,),
            dtype="float64",
            compression="gzip"
        )
        ds[0] = -76.432

    # In-place chunk resizing
    with h5py.File(h5_scratch_path, "a", libver="latest") as f:
        ds = f["energies"]
        new_len = ds.shape[0] + 1
        ds.resize((new_len,))
        ds[new_len - 1] = -76.435
        ds.flush()

    # Verify length without whole-file copying
    with h5py.File(h5_scratch_path, "r") as f:
        assert f["energies"].shape[0] == 2
        assert math.isclose(f["energies"][1], -76.435)

def test_mendeleev_invariants_lazy_singleton_startup():
    """Validates Suggestion #67: Lazy singleton initialization eliminates top-level import lag."""
    # Ensure cache function returns valid mapping from Z=1 to Z=118
    cache = get_element_cache()
    assert len(cache) >= 118
    assert cache[1].symbol == "H"
    assert cache[6].symbol == "C"

def test_sandbox_context_atexit_unregister_and_airgap(tmp_path):
    """Validates Suggestion #68: atexit callback unregistration on context exit."""
    scratch_dir = tmp_path / "scratch"
    os.environ["COCH_SCRATCH"] = str(scratch_dir)

    initial_atexit_count = len(atexit._nref) if hasattr(atexit, "_nref") else 0

    with SandboxContext(scratch_root=scratch_dir) as sb:
        assert sb.path.exists()
        inside_atexit_count = len(atexit._nref) if hasattr(atexit, "_nref") else 0

    # Path must be unlinked and cleaned
    assert not sb.path.exists()
    final_atexit_count = len(atexit._nref) if hasattr(atexit, "_nref") else 0

    # Cleaned flag must be set
    assert sb._cleaned is True

def test_process_reaper_direct_pid_monitoring():
    """Validates Suggestion #69: Direct child PID tracking in ProcessTreeManager."""
    manager = ProcessTreeManager()
    
    # Spawn dummy child process
    import subprocess
    import sys
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    manager.register_process(proc.pid)

    assert proc.pid in manager._tracked
    rss = manager.sample_process_tree_rss_bytes()
    assert rss > 0

    # Terminate tracked process
    manager.terminate_tree()
    proc.wait()
    assert not proc.poll() is None

def test_subprocess_broker_scratch_verification_cache(tmp_path):
    """Validates Suggestion #70: Scratch verification caching with TTL."""
    scratch_dir = tmp_path / "scratch_io"
    scratch_dir.mkdir()
    _SCRATCH_VERIFICATION_CACHE.clear()

    # First call must perform physical write probe
    t0 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t1 = time.perf_counter()
    initial_duration = t1 - t0

    # Second call within TTL must hit cache and return immediately (< 1 ms)
    t2 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t3 = time.perf_counter()
    cached_duration = t3 - t2

    assert cached_duration < 0.002
    assert cached_duration < initial_duration
```

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock & Zero-Stub Verification:**
   - Strict scan across all modified files. Zero occurrences of `unittest.mock`, `MagicMock`, `@patch`, `TODO`, `pass`, or `NotImplementedError` permitted.
2. **Full Test Suite Execution:**
   - Execute `pytest tests/core/test_physics_integrity_part7.py tests/core/test_architecture_part7.py`.
   - 100% of authored tests must pass with physical file operations, genuine Mendeleev lookups, real HDF5 SWMR resizing, physical subprocess tracking, and real RFC 8785 byte comparisons.
3. **Cross-Platform Path & Concurrency Hygiene:**
   - All paths must use `pathlib.Path.resolve()`. Zero hardcoded Windows drive letters (`C:`, `D:`) or POSIX-only roots in core modules.
   - Node-local scratch directory locking strictly enforced; zero lockfile allocation on remote parallel filesystems (Lustre/GPFS/NFS).
4. **Method Matrix Provenance Compliance:**
   - Dynamic mass retrieval strictly through `mendeleev`.
   - Zero CUDA runtime locking in orchestrator telemetry path.
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
| **Model Versioning** | Mandatory `schema_version` attribute and automated migration dispatcher | **PASS (VERIFIED)** |
| **RFC 8785 Float Parity** | ECMAScript IEEE 754 Number-to-String formatting kernel in `canonicalize_json` | **PASS (VERIFIED)** |
| **Thermodynamic Provenance** | Embedding Grimme quasi-RRHO cutoff and damping parameters into `DAGNode` | **PASS (VERIFIED)** |
| **Actionable Exceptions** | Structured `CoChemError` hierarchy with typed machine-actionable error codes | **PASS (VERIFIED)** |
| **In-Place SWMR Resizing** | Elimination of `shutil.copyfile` and implementation of in-place HDF5 `ds.resize` | **PASS (VERIFIED)** |
| **Mendeleev Mass Caching** | `@functools.lru_cache` on dynamic lookups without GPU context stalls | **PASS (VERIFIED)** |
| **Lazy Invariant Singleton** | Deferral of 118-element SQLite queries until first access; zero-lag module import | **PASS (VERIFIED)** |
| **Sandbox Memory Leaks** | Explicit `atexit.unregister(self.cleanup)` calls and Tier 3 scratch enforcement | **PASS (VERIFIED)** |
| **Reaper Direct Polling** | Querying registered child PIDs directly without recursive full-OS traversal | **PASS (VERIFIED)** |
| **Cached Scratch Probe** | Session-level scratch integrity cache with configurable TTL to eliminate fsync stalls | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero mocks, zero synthetic loops across all 10 tasks and test suites | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
# CODING PROMPT: CoChem-BASE Core Architecture Implementation (Chunk 7: Suggestions #61–#70)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-BASE`  
**Execution Agent Target:** `@cochem-coder` (Autonomous Iterative Implementation & Feature Building Agent)  
**Supervising & Auditing Personas:** `0rchestrator`, `cochem-sdp-manager`, `cochem-audit`, `adversary`  
**Governing Specifications:**
- Method Matrix v4 (§3.0, §4.4, §6.4, §6.10, §8.2, §8.3, §8.4, §8A, §8A.4, §8B.4, §8B.6, §8C, §9A, §9B, Table 3, QS-1, QS-3)
- Zero-Mock Anti-Spoofing Protocol v2 (Zero placeholders, zero stubs, zero simulated mocks, 100% real physical execution)
- Tripartite Storage Air-Gap Architecture (Source $T_{\text{src}}$ immutable read-only, Ephemeral Scratch $T_{\text{scr}}$ isolated, State & Artifacts $T_{\text{state}}/T_{\text{export}}$ read-write cryptographic commitments)
- 6-Tier Environment Matrix (Local-Windows/WSL, Local-macOS/OrbStack, Local-Linux/Debian, Codespaces, GitHub Actions, HPC)
- Dynamic Mendeleev Invariant Mandate (`from mendeleev import element`, zero hardcoded atomic masses, strict dynamic IUPAC/CIAAW physical mass retrieval)
- FAIR Principles Compliance (F1, F2, A1, I1, I2, I3, R1, R1.1, R1.2, R1.3)
- MolSSI QCSchema v1 Compliance (`schema_name="qcschema_output"`, `schema_version=1`, explicit `AtomicResult` mapping)
- IETF RFC 8785 JSON Canonicalization Scheme (JCS) §3.2.2.3 IEEE 754 Number-to-String formatting mandate
- Cross-Platform Concurrency Directive (Thread-safe SWMR HDF5 with `threading.RLock()` and `filelock.FileLock`, non-blocking CUDA stream handling under NVIDIA MPS isolation, strictly no POSIX `fcntl` on network filesystems)

---

## 1. Executive Summary & Objective

Implement, harden, and physically verify Suggestions #61 through #70 of the CoChem-BASE Core Architecture Improvement Specification. This work package resolves critical vulnerabilities across long-term archival data persistence, RFC 8785 canonical serialization parity, quasi-harmonic thermodynamic provenance logging, machine-actionable exception architectures, in-place HDF5 SWMR chunk resizing, cached dynamic mass resolution without GPU context stalls, lazy zero-cost module initialization, ephemeral sandbox memory leaks, low-overhead process monitoring, and cached session scratch verification.

Specific implementation targets include:
1. Injecting a mandatory `schema_version: int = 1` field into all Pydantic models across `cochem_base.core.models`, enforcing `model_config = ConfigDict(frozen=True, extra="forbid")`, and establishing an automated schema migration dispatch protocol supporting long-term backward-compatible deserialization (FAIR F2, I1, R1).
2. Implementing an RFC 8785-compliant IEEE 754 Number-to-String formatting kernel in `cochem_base.core.cochem_crypto.canonicalize_json` to eliminate cross-platform SHA-256 hash divergence caused by standard Python `float.__repr__` formatting.
3. Embedding all quasi-harmonic thermodynamic parameters (`low_freq_cutoff_cm1`, `damping_model="grimme_quasi_rrho"`, `temperature_k`, `pressure_atm=1.0`) into `DAGNode.payload["thermodynamics_provenance"]` metadata dictionaries to guarantee 100% reproducible vibrational free energies and Boltzmann populations (FAIR R1.2, Method Matrix §8B.4).
4. Standardizing all custom exceptions across `cochem_base.core` by subclassing a base `CoChemError` class and attaching machine-actionable error codes (e.g. `CoordinateShapeError` with code `COCHEM_E_INVALID_COORD_SHAPE`, `AirGapBoundaryError` with code `COCHEM_E_AIRGAP_BREACH`) to support automated ETL triage (FAIR A1, I1).
5. Refactoring `PESStore.write_entry()` to eliminate quadratic `shutil.copyfile` latency degradation, implementing in-place HDF5 SWMR chunk resizing (`ds.resize(new_len, axis=0)`) with dual-layer synchronization (`threading.RLock()` and cross-platform `filelock.FileLock`) and strict Tripartite Air-Gap path boundary enforcement.
6. Applying `@functools.lru_cache(maxsize=256)` to all dynamic Mendeleev mass resolution routines in `cochem_base.core_engine`, ensuring mass lookups execute in CPU precomputation without blocking active CUDA streams or locking GPU context workers under NVIDIA Multi-Process Service (MPS) daemon isolation (§8A.4).
7. Refactoring `_build_element_cache()` in `cochem_base.core.mendeleev_invariants` into a lazy, thread-safe singleton initialization pattern to eliminate the $200\text{--}600\text{ ms}$ module import lag on multiprocessing worker spawn pools.
8. Purging unbounded `atexit` callbacks in `cochem_base.core.cochem_sandbox.SandboxContext` by explicitly invoking `atexit.unregister(self.cleanup)` upon context exit, while enforcing strict dynamic sandbox root containment in Tier 3 (`$COCH_SCRATCH`).
9. Replacing recursive full-system process tree discovery (`psutil.Process().children(recursive=True)`) in `ProcessTreeManager` with direct polling across explicitly registered child PIDs in `_tracked`, reducing monitoring CPU consumption by $>80\%$ and eliminating quantum chemistry kernel cache perturbation.
10. Decoupling the 64 KB binary physical I/O integrity probe in `cochem_core_subprocess_broker.py` from individual subprocess invocations by implementing a session-level scratch verification cache with a configurable time-to-live ($\text{TTL} = 300\text{ s}$) keyed on workspace path.

All code modifications must be accompanied by comprehensive, zero-mock unit and integration tests executing real Mendeleev lookups, real IEEE 754 serialization roundtrips, real HDF5 SWMR dataset extensions, physical multi-process reaper monitoring, and real subprocess executions.

---

## 2. Target Files & Deliverable Manifest

### Core Models, Exceptions & Cryptographic Modules
1. `src/cochem_base/core/models.py` (Suggestions #61, #64)
2. `src/cochem_base/core/exceptions.py` (Suggestion #64)
3. `src/cochem_base/core/cochem_crypto.py` (Suggestion #62)
4. `src/cochem_base/core/cochem_provenance.py` (Suggestion #63)

### Engine, Storage & Concurrency Architecture Modules
5. `src/cochem_base/core/ipc/serializer.py` (Suggestion #65)
6. `src/cochem_base/core_engine/cochem_core_pes_store.py` (Suggestion #65)
7. `src/cochem_base/core_engine/cochem_mass_resolver.py` (Suggestion #66)
8. `src/cochem_base/core/mendeleev_invariants.py` (Suggestion #67)
9. `src/cochem_base/core/cochem_sandbox.py` (Suggestion #68)
10. `src/cochem_base/core/process_reaper.py` (Suggestion #69)
11. `src/cochem_base/core_engine/cochem_core_subprocess_broker.py` (Suggestion #70)

### Zero-Mock Test Suite Deliverables
12. `tests/core/test_physics_integrity_part7.py` (Validating Suggestions #61, #62, #63, #64, #66)
13. `tests/core/test_architecture_part7.py` (Validating Suggestions #65, #67, #68, #69, #70)

---

## 3. Detailed Work Breakdown Structure (WBS) & Implementation Instructions

### [Task 1: Pydantic Model Versioning & Schema Migration Dispatch (Suggestion #61)]
- **Files Affected:** `src/cochem_base/core/models.py`, `src/cochem_base/core/exceptions.py`
- **Problem Statement:**
  Archival data records generated by older versions of CoChem cannot be ingested by newer versions because models in `cochem_base.core.models` lack an explicit `schema_version` attribute and schema migration hooks. When a new field is added to a Pydantic model configured with `extra="forbid"`, deserializing older records missing that field triggers a fatal `ValidationError`, destroying multi-year scientific reproducibility and violating FAIR Principles F2, I1, and R1.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/models.py`, define global schema constants:
     ```python
     CURRENT_CORE_SCHEMA_VERSION: int = 1
     ```
  2. Inject a mandatory schema version attribute with a default into all core data models (e.g. `MolecularTopology`, `QCSchemaInput`, `QCSchemaOutput`, `PESPointRecord`, `CalculationJobPayload`, `AtomicResult`):
     ```python
     schema_version: int = Field(
         default=CURRENT_CORE_SCHEMA_VERSION,
         description="Semantic schema version for archival data deserialization and migration contracts."
     )
     ```
  3. Enforce strict immutability and forbid extraneous undeclared fields:
     ```python
     model_config = ConfigDict(frozen=True, extra="forbid")
     ```
  4. Implement an extensible schema migration registry and dispatcher:
     ```python
     MigrationCallable = Callable[[Dict[str, Any]], Dict[str, Any]]
     _MIGRATION_REGISTRY: Dict[Tuple[str, int], MigrationCallable] = {}

     def register_migration(model_name: str, from_version: int) -> Callable[[MigrationCallable], MigrationCallable]:
         """Decorator registering a transformation function from a specific schema version to from_version + 1."""
         def decorator(func: MigrationCallable) -> MigrationCallable:
             _MIGRATION_REGISTRY[(model_name, from_version)] = func
             return func
         return decorator

     def migrate_payload(payload: Dict[str, Any], target_model: Type[BaseModel]) -> Dict[str, Any]:
         """Migrates a raw dictionary payload sequentially up to target_model's current schema_version."""
         model_name = target_model.__name__
         current_version = payload.get("schema_version", 0)
         target_version = getattr(target_model, "CURRENT_VERSION", CURRENT_CORE_SCHEMA_VERSION)

         data = dict(payload)
         while current_version < target_version:
             key = (model_name, current_version)
             if key not in _MIGRATION_REGISTRY:
                 raise SchemaMigrationError(
                     f"No migration path registered for {model_name} from version {current_version} to {current_version + 1}.",
                     error_code="COCHEM_E_SCHEMA_MIGRATION_FAILED",
                     details={"model": model_name, "from_version": current_version, "target_version": target_version}
                 )
             data = _MIGRATION_REGISTRY[key](data)
             current_version = data.get("schema_version", current_version + 1)

         return data
     ```
  5. Provide a classmethod on all versioned models:
     ```python
     @classmethod
     def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
         """Parses a dictionary, executing automated migrations if schema_version is older than current."""
         migrated = migrate_payload(data, cls)
         return cls.model_validate(migrated)
     ```

---

### [Task 2: RFC 8785-Compliant IEEE 754 Float Canonicalization Kernel (Suggestion #62)]
- **Files Affected:** `src/cochem_base/core/cochem_crypto.py`
- **Problem Statement:**
  Cryptographic hashes of canonical JSON payloads diverge between Python and external verifiers (in Node.js, Go, Rust) because `canonicalize_json` relies on Python's built-in `json.dumps()` for float formatting. RFC 8785 (JSON Canonicalization Scheme - JCS) §3.2.2.3 strictly mandates the ECMAScript IEEE 754 Number-to-String formatting algorithm. Python's `float.__repr__` outputs exponential notations with 2-digit padded exponents (e.g. `1e-05`) or differing precision thresholds, breaking deterministic cross-platform SHA-256 verification [M].
- **Implementation Requirements:**
  1. In `src/cochem_base/core/cochem_crypto.py`, implement a dedicated RFC 8785 ECMAScript IEEE 754 float string formatting kernel:
     ```python
     def format_rfc8785_float(val: float) -> str:
         """Formats an IEEE 754 double-precision float strictly adhering to RFC 8785 §3.2.2.3 (ECMAScript Number::toString).
         
         Rules:
         - NaN and Infinities are strictly disallowed in JSON (raise ValueError).
         - Signed zero (-0.0) must format as '0'.
         - Absolute value in range 1e-6 <= |val| < 1e21 formats in fixed decimal notation without unnecessary trailing zeros.
         - Absolute value < 1e-6 or >= 1e21 formats in exponential notation with lowercase 'e' and exponent without leading zero.
         """
         import math
         if math.isnan(val) or math.isinf(val):
             raise ValueError(f"RFC 8785 forbids non-finite float values: {val}")
         if val == 0.0:
             return "0"

         s = f"{val:.17g}"
         
         # Normalize scientific notation exponent (e.g., '1e-05' -> '1e-5', '1e+05' -> '1e+5')
         if 'e' in s:
             base, exp = s.split('e')
             exp_sign = exp[0]
             exp_val = exp[1:].lstrip('0') or '0'
             s = f"{base}e{exp_sign}{exp_val}"
         
         # Handle corner-case ranges where Python emits scientific notation but ECMAScript mandates fixed:
         abs_val = abs(val)
         if 1e-6 <= abs_val < 1e-4 and 'e' in s:
             s = f"{val:.10f}".rstrip('0').rstrip('.')
             
         return s
     ```
  2. Implement `canonicalize_json(data: Any) -> bytes`:
     ```python
     def canonicalize_json(data: Any) -> bytes:
         """Serializes arbitrary Python data structures to deterministic UTF-8 bytes adhering to RFC 8785 (JCS).
         
         - Lexicographical sorting of object keys by UTF-8 code point values.
         - Zero whitespace around delimiters (',' and ':').
         - IEEE 754 float formatting via format_rfc8785_float.
         - UTF-8 output without BOM.
         """
         return _serialize_jcs(data).encode("utf-8")

     def _serialize_jcs(obj: Any) -> str:
         if obj is None:
             return "null"
         elif isinstance(obj, bool):
             return "true" if obj else "false"
         elif isinstance(obj, int):
             return str(obj)
         elif isinstance(obj, float):
             return format_rfc8785_float(obj)
         elif isinstance(obj, str):
             import json
             return json.dumps(obj, ensure_ascii=False)
         elif isinstance(obj, (list, tuple)):
             items = [_serialize_jcs(item) for item in obj]
             return "[" + ",".join(items) + "]"
         elif isinstance(obj, dict):
             sorted_keys = sorted(obj.keys(), key=lambda k: k.encode("utf-8"))
             pairs = [
                 json.dumps(k, ensure_ascii=False) + ":" + _serialize_jcs(obj[k])
                 for k in sorted_keys
             ]
             return "{" + ",".join(pairs) + "}"
         elif hasattr(obj, "model_dump"):
             return _serialize_jcs(obj.model_dump(mode="json"))
         else:
             raise TypeError(f"Object of type {type(obj).__name__} is not RFC 8785 JCS serializable")
     ```
  3. Ensure that `hash_canonical_json(data: Any, algorithm: str = "sha256") -> str` in `cochem_crypto.py` calls `canonicalize_json(data)`.

---

### [Task 3: Quasi-Harmonic Thermodynamic Parameter Provenance Logging (Suggestion #63)]
- **Files Affected:** `src/cochem_base/core/cochem_provenance.py`, `src/cochem_base/core/models.py`
- **Problem Statement:**
  External researchers cannot reproduce the exact Boltzmann populations computed by `compute_boltzmann_weights()` because the function applies Grimme's quasi-RRHO low-frequency interpolation using a procedural $100\text{ cm}^{-1}$ cutoff without logging the cutoff, rotor cutoff, or damping scheme into node metadata. Because low-frequency torsional modes in fluxional complexes dominate vibrational entropy, shifting the cutoff between $50$ and $150\text{ cm}^{-1}$ alters relative conformer free energies by up to $1.5\text{ kcal/mol}$ [D], violating FAIR Principle R1.2 and Method Matrix v4 §8B.4 / §9B.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/models.py`, define the provenance model:
     ```python
     class ThermodynamicsProvenance(BaseModel):
         """Provenance metadata for quasi-harmonic thermodynamic corrections and Boltzmann weighting."""
         damping_model: str = Field(
             default="grimme_quasi_rrho",
             description="Vibrational entropy damping model (e.g. grimme_quasi_rrho, truhlar_quasi_harmonic, harmonic)."
         )
         low_freq_cutoff_cm1: float = Field(
             default=100.0,
             description="Low-frequency cutoff/interpolation threshold in wavenumbers (cm^-1)."
         )
         temperature_k: float = Field(
             default=298.15,
             description="Thermodynamic temperature in Kelvin."
         )
         pressure_atm: float = Field(
             default=1.0,
             description="Standard state pressure in atmospheres."
         )
         rotor_cutoff_cm1: Optional[float] = Field(
             default=None,
             description="Free-rotor transition threshold if using Head-Gordon or multi-cutoff damping."
         )
         provenance_tag: str = Field(
             default="[D]",
             description="Method Matrix provenance marker ([M] measured, [D] derived, [E] estimated)."
         )
         schema_version: int = Field(default=CURRENT_CORE_SCHEMA_VERSION)
         model_config = ConfigDict(frozen=True, extra="forbid")
     ```
  2. Refactor `compute_boltzmann_weights()` in `src/cochem_base/core/cochem_provenance.py`:
     ```python
     def compute_boltzmann_weights(
         free_energies_kcal_mol: Sequence[float],
         temperature_k: float = 298.15,
         low_freq_cutoff_cm1: float = 100.0,
         damping_model: str = "grimme_quasi_rrho",
         pressure_atm: float = 1.0,
         dag_node: Optional[Any] = None
     ) -> Tuple[List[float], ThermodynamicsProvenance]:
         """Computes normalized Boltzmann weights while recording thermodynamic provenance.
         
         Weights: w_i = exp(-Delta G_i / (R * T)) / sum(exp(-Delta G_j / (R * T)))
         Logs ThermodynamicsProvenance into dag_node.payload['thermodynamics_provenance'] if provided.
         """
         import numpy as np
         R_KCAL_MOL_K: float = 0.00198720425864083
         
         G = np.asarray(free_energies_kcal_mol, dtype=np.float64)
         if len(G) == 0:
             return [], ThermodynamicsProvenance(
                 damping_model=damping_model,
                 low_freq_cutoff_cm1=low_freq_cutoff_cm1,
                 temperature_k=temperature_k,
                 pressure_atm=pressure_atm
             )

         delta_G = G - np.min(G)
         beta = 1.0 / (R_KCAL_MOL_K * temperature_k)
         unnorm_weights = np.exp(-beta * delta_G)
         weights = (unnorm_weights / np.sum(unnorm_weights)).tolist()

         prov = ThermodynamicsProvenance(
             damping_model=damping_model,
             low_freq_cutoff_cm1=float(low_freq_cutoff_cm1),
             temperature_k=float(temperature_k),
             pressure_atm=float(pressure_atm),
             provenance_tag="[D]"
         )

         if dag_node is not None and hasattr(dag_node, "payload") and isinstance(dag_node.payload, dict):
             dag_node.payload["thermodynamics_provenance"] = prov.model_dump(mode="json")

         return weights, prov
     ```

---

### [Task 4: Machine-Actionable Exception Hierarchy & Typed Error Codes (Suggestion #64)]
- **Files Affected:** `src/cochem_base/core/exceptions.py`, `src/cochem_base/core/models.py`
- **Problem Statement:**
  Coordinate shape validation and core integrity checks currently raise generic `ValueError` or unformatted standard library exceptions. Automated ingest and high-throughput execution pipelines cannot programmatically distinguish dimensionality failures, unphysical nuclear charges, schema version conflicts, or air-gap breaches without fragile regex parsing of error strings, violating FAIR Principles A1 and I1 and Global Swarm Protocols.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/exceptions.py`, define the root structured exception class and specialized error codes:
     ```python
     from typing import Optional, Dict, Any

     class CoChemError(Exception):
         """Base error class for all CoChem operations with machine-actionable error codes."""
         def __init__(
             self,
             message: str,
             error_code: str = "COCHEM_E_GENERIC",
             details: Optional[Dict[str, Any]] = None
         ) -> None:
             super().__init__(f"[{error_code}] {message}")
             self.message = message
             self.error_code = error_code
             self.details = details or {}

     class CoordinateShapeError(CoChemError):
         """Raised when molecular coordinate arrays violate dimensionality constraints (e.g. not N x 3)."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_INVALID_COORD_SHAPE", details=details)

     class AirGapBoundaryError(CoChemError):
         """Raised when an operation attempts to write to a read-only or out-of-tier filesystem boundary."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_AIRGAP_BREACH", details=details)

     class SchemaMigrationError(CoChemError):
         """Raised when deserializing a payload lacking a valid migration path to current schema_version."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_SCHEMA_MIGRATION_FAILED", details=details)

     class PESStorageError(CoChemError):
         """Raised when HDF5 SWMR store operations fail or encounter lock contention."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_PES_STORAGE_FAILURE", details=details)

     class ProcessReaperError(CoChemError):
         """Raised when process termination or resource sampling fails unexpectedly."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_PROCESS_REAPER_FAILURE", details=details)

     class SubprocessBrokerError(CoChemError):
         """Raised when isolated subprocess execution fails pre-flight or runtime contracts."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_SUBPROCESS_BROKER_FAILURE", details=details)

     class ThermodynamicsParameterError(CoChemError):
         """Raised when required quasi-harmonic parameters are missing from thermodynamic calculations."""
         def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_THERMO_PARAM_MISSING", details=details)
     ```
  2. In `src/cochem_base/core/models.py`, refactor `MolecularTopology` validator to raise `CoordinateShapeError`:
     ```python
     @field_validator("coordinates", mode="after")
     @classmethod
     def validate_coordinates_shape(cls, v: List[List[float]]) -> List[List[float]]:
         for idx, atom_coord in enumerate(v):
             if len(atom_coord) != 3:
                 raise CoordinateShapeError(
                     f"Atom index {idx} has dimensionality {len(atom_coord)}; expected exactly 3 (x, y, z).",
                     details={"atom_index": idx, "actual_len": len(atom_coord), "expected_len": 3}
                 )
         return v
     ```

---

### [Task 5: In-Place HDF5 SWMR Chunk Resizing & Dual-Layer Locking (Suggestion #65)]
- **Files Affected:** `src/cochem_base/core/ipc/serializer.py`, `src/cochem_base/core_engine/cochem_core_pes_store.py`
- **Problem Statement:**
  `PESStore.write_entry()` currently copies the entire pre-existing HDF5 database to a temporary file via `shutil.copyfile` before writing, implementing scalar whole-file atomic replacement semantics. Appending $N$ grid points sequentially to a database of size $S$ generates $O(N \cdot S)$ disk I/O, writing gigabytes of redundant copies [M], invalidating open SWMR reader file descriptors, causing severe multi-process lock contention, and failing to validate Tripartite Air-Gap path boundaries.
- **Implementation Requirements:**
  1. Eliminate all calls to `shutil.copyfile` and `os.replace` in `PESStore.write_entry()` and HDF5 serialization routines.
  2. Implement in-place HDF5 SWMR chunk resizing:
     - On dataset creation: specify `maxshape=(None, ...)` on the initial dimension, `chunks=(512, ...)` or appropriate chunk points, and compression filters (`gzip`, `shuffle`, `fletcher32`).
     - On append: invoke `dataset.resize(new_length, axis=0)`, slice-assign the new record, and call `dataset.flush()` and `file.flush()` to ensure SWMR visibility.
  3. Implement dual-layer concurrency locking:
     - In-process: module-level `_HDF5_MEM_LOCK = threading.RLock()` guarding C-library HDF5 API calls.
     - Cross-process IPC: use `filelock.FileLock` operating on node-local scratch storage (`$COCH_SCRATCH`), with a configurable timeout (default `30.0` s). Strictly prohibit lockfile allocation on networked filesystems (Lustre/GPFS/NFS).
  4. Enforce Tripartite Air-Gap boundary validation:
     ```python
     def validate_airgap_write_path(target_path: Path) -> Path:
         """Validates that target write path resides strictly within Tier 4 ($COCH_STATE) or Tier 3 ($COCH_SCRATCH).
         Raises AirGapBoundaryError if write is attempted in Tier 1 ($COCH_SRC) or Tier 2 ($COCH_DATA).
         """
         resolved = target_path.resolve()
         src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
         data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()

         if src_dir.exists() and src_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Air-gap boundary violation: Cannot write PES data to read-only Tier 1 ($COCH_SRC): {resolved}",
                 details={"target_path": str(resolved), "tier": "Tier 1 ($COCH_SRC)"}
             )
         if data_dir.exists() and data_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Air-gap boundary violation: Cannot write PES data to immutable Tier 2 ($COCH_DATA): {resolved}",
                 details={"target_path": str(resolved), "tier": "Tier 2 ($COCH_DATA)"}
             )
         return resolved
     ```
  5. Refactor `PESStore.write_entry(point: PESPointRecord) -> None`:
     - Validate target path with `validate_airgap_write_path(self.file_path)`.
     - Acquire dual-layer lock (`with _HDF5_MEM_LOCK: with filelock.FileLock(self.lock_path, timeout=30.0):`).
     - Open HDF5 with `libver='latest'`, resize dataset along axis 0, commit point attributes, flush buffers.

---

### [Task 6: Dynamic Mendeleev Mass Resolution In-Memory Caching (Suggestion #66)]
- **Files Affected:** `src/cochem_base/core_engine/cochem_mass_resolver.py`
- **Problem Statement:**
  Core solvers query dynamic Mendeleev masses synchronously without memoization. Because `mendeleev.element(symbol)` executes SQL SELECT queries against the bundled SQLite database on disk ($\sim 100\ \mu\text{s}$ per query [M]), multidimensional Discrete Variable Representation (DVR) solvers and Eckart frame projections query masses tens of thousands of times across multidimensional coordinate meshes. Furthermore, synchronous SQLite queries on the host thread stall non-blocking CUDA streams and lock GPU context workers under NVIDIA Multi-Process Service (MPS) daemon isolation (§8A.4).
- **Implementation Requirements:**
  1. Create or refactor `src/cochem_base/core_engine/cochem_mass_resolver.py`.
  2. Implement `@functools.lru_cache(maxsize=256)` on dynamic mass resolution functions:
     ```python
     from functools import lru_cache
     from typing import Union, Optional
     import mendeleev
     from cochem_base.core.exceptions import CoChemError

     class IsotopeMassResolutionError(CoChemError):
         """Raised when requested isotope cannot be resolved to physical mass."""
         def __init__(self, message: str, details: Optional[dict] = None) -> None:
             super().__init__(message, error_code="COCHEM_E_ISOTOPE_NOT_FOUND", details=details)

     @lru_cache(maxsize=256)
     def get_dynamic_atomic_mass(symbol_or_z: Union[str, int]) -> float:
         """Returns standard atomic weight from Mendeleev with LRU memory caching.
         Reduces latency from ~100 us (SQLite I/O) to ~50 ns (in-memory lookup) [M].
         """
         el = mendeleev.element(symbol_or_z)
         if el.atomic_weight is not None:
             return float(el.atomic_weight)
         if el.mass is not None:
             return float(el.mass)
         raise IsotopeMassResolutionError(
             f"Atomic weight unavailable for element '{symbol_or_z}'.",
             details={"element": symbol_or_z}
         )

     @lru_cache(maxsize=256)
     def get_dynamic_isotopic_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
         """Returns exact physical isotopic nuclear mass from Mendeleev with LRU memory caching.
         Guarantees zero fallback to terrestrial average atomic weights.
         """
         el = mendeleev.element(symbol_or_z)
         for iso in el.isotopes:
             if iso.mass_number == int(mass_number):
                 if iso.mass is not None and float(iso.mass) > 0.0:
                     return float(iso.mass)
         raise IsotopeMassResolutionError(
             f"Isotope '{el.symbol}-{mass_number}' cannot be resolved to a physical mass.",
             details={"element": el.symbol, "mass_number": mass_number}
         )
     ```
  3. Ensure all DVR, PES store, and moment-of-inertia calculation routines import from `cochem_mass_resolver.py`.
  4. Guarantee that mass lookup arrays are pre-resolved on the host CPU prior to launching asynchronous GPU kernels, preventing CUDA stream stalls or GPU context blocking under NVIDIA MPS daemon isolation (§8A.4).

---

### [Task 7: Lazy Thread-Safe Singleton for Mendeleev Invariants (Suggestion #67)]
- **Files Affected:** `src/cochem_base/core/mendeleev_invariants.py`
- **Problem Statement:**
  Importing `cochem_base.core.mendeleev_invariants` eagerly executes `_build_element_cache()` at top level, calling `_mendeleev_element(z)` 118 times from $Z=1$ to $Z=118$ and running 118 sequential SQLite queries. In multiprocessing architectures using the `spawn` context (Windows and HPC SLURM worker pools), every single worker process re-imports the module and re-runs all 118 SQL queries sequentially upon initialization, incurring a $200\text{--}600\text{ ms}$ startup penalty per spawned process [M].
- **Implementation Requirements:**
  1. Remove the eager module-level execution of `_build_element_cache()` at line 107 in `mendeleev_invariants.py`.
  2. Implement a thread-safe lazy singleton pattern:
     ```python
     import threading
     from typing import Dict, Optional, Any

     _ELEMENT_CACHE_LOCK = threading.Lock()
     _ELEMENT_CACHE: Optional[Dict[int, Any]] = None

     def get_element_cache() -> Dict[int, Any]:
         """Lazy thread-safe accessor for the 118-element Mendeleev invariants cache.
         Eliminates 200-600 ms top-level module import overhead across spawned worker processes [M].
         """
         global _ELEMENT_CACHE
         if _ELEMENT_CACHE is None:
             with _ELEMENT_CACHE_LOCK:
                 if _ELEMENT_CACHE is None:
                     _ELEMENT_CACHE = _build_element_cache()
         return _ELEMENT_CACHE
     ```
  3. Refactor all external functions in `mendeleev_invariants.py` (e.g. `get_element_data(z)`, `get_symbol(z)`, `get_atomic_number(symbol)`) to query `get_element_cache()` rather than directly referencing a global module dictionary.
  4. Ensure module import time drops to $< 5\text{ ms}$ [M].

---

### [Task 8: Ephemeral Sandbox Lifecycle & `atexit` Leak Elimination (Suggestion #68)]
- **Files Affected:** `src/cochem_base/core/cochem_sandbox.py`
- **Problem Statement:**
  `SandboxContext.__enter__()` registers `atexit.register(self.cleanup)` on every entry, but `cleanup()` and `__exit__()` fail to call `atexit.unregister(self.cleanup)`. In multi-stage calculation campaigns creating hundreds of ephemeral workspaces, the Python interpreter retains strong references to completed `SandboxContext` instances and their associated configurations in `atexit._nref`, causing unbounded heap memory accumulation and multi-second shutdown stalls during process termination.
- **Implementation Requirements:**
  1. In `src/cochem_base/core/cochem_sandbox.py`, update `SandboxContext`:
     ```python
     import atexit
     import shutil
     from pathlib import Path
     from typing import Optional
     from cochem_base.core.exceptions import AirGapBoundaryError

     class SandboxContext:
         """Manages ephemeral calculation workspaces adhering to Tripartite Air-Gap Domain C."""
         def __init__(self, scratch_root: Optional[Path] = None, prefix: str = "cochem_job_") -> None:
             self.scratch_root = self._resolve_and_validate_scratch_root(scratch_root)
             self.prefix = prefix
             self.path: Optional[Path] = None
             self._cleaned: bool = False

         def _resolve_and_validate_scratch_root(self, root: Optional[Path]) -> Path:
             if root is None:
                 root = Path(os.environ.get("COCH_SCRATCH", "/tmp/cochem_scratch"))
             resolved = root.resolve()

             src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
             data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()
             if src_dir.exists() and src_dir in resolved.parents:
                 raise AirGapBoundaryError(
                     f"Cannot create ephemeral sandbox inside Tier 1 ($COCH_SRC): {resolved}",
                     details={"attempted_path": str(resolved), "tier": "Tier 1"}
                 )
             if data_dir.exists() and data_dir in resolved.parents:
                 raise AirGapBoundaryError(
                     f"Cannot create ephemeral sandbox inside Tier 2 ($COCH_DATA): {resolved}",
                     details={"attempted_path": str(resolved), "tier": "Tier 2"}
                 )
             return resolved

         def __enter__(self) -> "SandboxContext":
             import tempfile
             self.scratch_root.mkdir(parents=True, exist_ok=True)
             self.path = Path(tempfile.mkdtemp(prefix=self.prefix, dir=self.scratch_root))
             self._cleaned = False
             atexit.register(self.cleanup)
             return self

         def cleanup(self) -> None:
             """Idempotently cleans up scratch directory and removes atexit registration."""
             if self._cleaned:
                 return
             self._cleaned = True
             atexit.unregister(self.cleanup)
             if self.path is not None and self.path.exists():
                 try:
                     shutil.rmtree(self.path, ignore_errors=True)
                 except Exception:
                     pass

         def __exit__(self, exc_type, exc_val, exc_tb) -> None:
             self.cleanup()
     ```
  2. Verify that repeated entries and exits from `SandboxContext` result in zero net change to `len(atexit._nref)` or internal callback queues.

---

### [Task 9: Direct Child PID Monitoring in Process Reaper (Suggestion #69)]
- **Files Affected:** `src/cochem_base/core/process_reaper.py`
- **Problem Statement:**
  Monitoring daemons periodically invoke `sample_process_tree_rss_bytes()` and `terminate_tree()` at short intervals ($0.1\text{--}1.0\text{ s}$) using `psutil.Process().children(recursive=True)`. The OS must traverse the entire system process table on every polling cycle, inducing significant host CPU consumption ($>15\%$), CPU cache eviction, and kernel thread contention on active compute cores dedicated to high-precision quantum chemical kernels (ORCA, CFOUR) and GPU MPS host workers (§8A.4).
- **Implementation Requirements:**
  1. In `src/cochem_base/core/process_reaper.py`, update `ProcessTreeManager`:
     - Maintain an explicit registry of active child PIDs:
       ```python
       self._tracked: Set[int] = set()
       ```
     - Provide registration methods:
       ```python
       def register_process(self, pid: int) -> None:
           """Explicitly registers a newly spawned subprocess PID for targeted telemetry and reaping."""
           if pid > 0:
               self._tracked.add(pid)

       def unregister_process(self, pid: int) -> None:
           """Removes a process PID upon normal exit."""
           self._tracked.discard(pid)
       ```
  2. Refactor `sample_process_tree_rss_bytes() -> int`:
     ```python
     def sample_process_tree_rss_bytes(self) -> int:
         """Samples memory consumption across tracked PIDs directly without traversing the full OS process table.
         Drops monitoring daemon CPU consumption by >80% [E] and preserves scout-and-anchor thread budgets.
         """
         total_rss = 0
         dead_pids = set()

         try:
             total_rss += self._parent_proc.memory_info().rss
         except (psutil.NoSuchProcess, psutil.AccessDenied):
             pass

         for pid in list(self._tracked):
             try:
                 p = psutil.Process(pid)
                 total_rss += p.memory_info().rss
             except psutil.NoSuchProcess:
                 dead_pids.add(pid)
             except (psutil.AccessDenied, psutil.ZombieProcess):
                 pass

         self._tracked.difference_update(dead_pids)
         return total_rss
     ```
  3. In `terminate_tree(timeout: float = 5.0) -> None`:
     - Directly signal all PIDs in `_tracked` with `SIGTERM` (or `taskkill /PID` on Windows), wait up to `timeout` seconds, and escalate to `SIGKILL` only for stubborn processes.
     - Fall back to recursive system-wide `children(recursive=True)` discovery ONLY when detached orphan subprocesses are suspected.

---

### [Task 10: Session-Level Scratch Verification Cache with TTL (Suggestion #70)]
- **Files Affected:** `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`
- **Problem Statement:**
  `safe_subprocess_run()` invokes `verify_scratch_quota_and_io()` prior to executing `subprocess.Popen`. This function writes a 64 KB binary probe to disk, flushes the stream, invokes `os.fsync()`, reads back the file, computes two SHA-256 digests, and unlinks the probe file before every command. This synchronous barrier adds a $20\text{--}100\text{ ms}$ dispatch latency per execution [M] and floods clustered/networked filesystems (Lustre, GPFS, NFS) with redundant metadata journal flushes during high-throughput calculations.
- **Implementation Requirements:**
  1. In `src/cochem_base/core_engine/cochem_core_subprocess_broker.py`, implement a thread-safe session-level scratch verification cache:
     ```python
     import time
     import os
     import hashlib
     from pathlib import Path
     from typing import Dict, Tuple, Optional
     from cochem_base.core.exceptions import AirGapBoundaryError, SubprocessBrokerError

     _SCRATCH_CACHE_LOCK = threading.Lock()
     _SCRATCH_VERIFICATION_CACHE: Dict[Path, float] = {}

     def verify_scratch_quota_and_io(
         scratch_dir: Path,
         ttl_seconds: float = 300.0,
         force: bool = False
     ) -> bool:
         """Verifies write, fsync, and SHA-256 read-back integrity on scratch_dir.
         Caches verification success for ttl_seconds to eliminate 20-100 ms dispatch latency per subprocess [M].
         Enforces Tripartite Air-Gap: scratch_dir must strictly reside within Tier 3 ($COCH_SCRATCH).
         """
         resolved = scratch_dir.resolve()

         src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
         data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()
         if src_dir.exists() and src_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Cannot execute subprocess scratch operations in read-only Tier 1 ($COCH_SRC): {resolved}",
                 details={"path": str(resolved), "tier": "Tier 1"}
             )
         if data_dir.exists() and data_dir in resolved.parents:
             raise AirGapBoundaryError(
                 f"Cannot execute subprocess scratch operations in immutable Tier 2 ($COCH_DATA): {resolved}",
                 details={"path": str(resolved), "tier": "Tier 2"}
             )

         now = time.monotonic()
         with _SCRATCH_CACHE_LOCK:
             if not force and resolved in _SCRATCH_VERIFICATION_CACHE:
                 last_verified = _SCRATCH_VERIFICATION_CACHE[resolved]
                 if (now - last_verified) < ttl_seconds:
                     return True

         resolved.mkdir(parents=True, exist_ok=True)
         probe_file = resolved / f".io_probe_{os.getpid()}_{time.time_ns()}.bin"
         probe_data = os.urandom(64 * 1024)
         probe_hash = hashlib.sha256(probe_data).hexdigest()

         try:
             with open(probe_file, "wb") as f:
                 f.write(probe_data)
                 f.flush()
                 os.fsync(f.fileno())

             with open(probe_file, "rb") as f:
                 read_data = f.read()

             read_hash = hashlib.sha256(read_data).hexdigest()
             if read_hash != probe_hash:
                 raise SubprocessBrokerError(
                     f"Scratch I/O integrity probe failed: SHA-256 mismatch in {resolved}",
                     details={"scratch_dir": str(resolved), "expected": probe_hash, "actual": read_hash}
                 )
         finally:
             if probe_file.exists():
                 try:
                     probe_file.unlink()
                 except OSError:
                     pass

         with _SCRATCH_CACHE_LOCK:
             _SCRATCH_VERIFICATION_CACHE[resolved] = time.monotonic()

         return True
     ```
  2. In `safe_subprocess_run()`, call `verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0, force=False)` prior to executing `subprocess.Popen`.

---

## 4. Pytest Unit & Integration Test Specifications

### Deliverable 1: `tests/core/test_physics_integrity_part7.py`
This test suite verifies physics integrity across data models, serialization kernels, thermodynamic provenance, exception structures, and mass caching.

```python
import math
import os
import time
import pytest
from pydantic import ValidationError
from cochem_base.core.models import (
    MolecularTopology,
    CURRENT_CORE_SCHEMA_VERSION,
    register_migration,
    migrate_payload
)
from cochem_base.core.exceptions import (
    CoChemError,
    CoordinateShapeError,
    SchemaMigrationError,
    AirGapBoundaryError
)
from cochem_base.core.cochem_crypto import (
    format_rfc8785_float,
    canonicalize_json
)
from cochem_base.core.cochem_provenance import (
    compute_boltzmann_weights,
    ThermodynamicsProvenance
)
from cochem_base.core_engine.cochem_mass_resolver import (
    get_dynamic_atomic_mass,
    get_dynamic_isotopic_mass,
    IsotopeMassResolutionError
)

def test_pydantic_model_schema_version_and_migration():
    """Validates Suggestion #61: schema_version injection and automated backward-compatible migration."""
    top = MolecularTopology(
        symbols=["H", "H"],
        coordinates=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
        molecular_charge=0,
        spin_multiplicity=1
    )
    assert top.schema_version == CURRENT_CORE_SCHEMA_VERSION

    @register_migration("MolecularTopology", 0)
    def migrate_v0_to_v1(data):
        d = dict(data)
        d["schema_version"] = 1
        if "spin_multiplicity" not in d:
            d["spin_multiplicity"] = 1
        return d

    legacy_payload = {
        "schema_version": 0,
        "symbols": ["O", "H", "H"],
        "coordinates": [[0.0, 0.0, 0.0], [0.0, 0.75, 0.5], [0.0, -0.75, 0.5]],
        "molecular_charge": 0
    }
    migrated_top = MolecularTopology.from_archival_dict(legacy_payload)
    assert migrated_top.schema_version == 1
    assert migrated_top.spin_multiplicity == 1

def test_rfc8785_ieee754_canonical_float_formatting():
    """Validates Suggestion #62: ECMAScript IEEE 754 float formatting parity in canonicalize_json."""
    assert format_rfc8785_float(0.0) == "0"
    assert format_rfc8785_float(-0.0) == "0"

    with pytest.raises(ValueError):
        format_rfc8785_float(float("nan"))
    with pytest.raises(ValueError):
        format_rfc8785_float(float("inf"))

    assert format_rfc8785_float(1e-5) == "0.00001" or format_rfc8785_float(1e-5) == "1e-5"
    assert format_rfc8785_float(1e-7) == "1e-7"
    assert format_rfc8785_float(1e21) == "1e+21"

    payload = {"b": 1e-7, "a": -0.0, "c": [1, 2.5]}
    canonical_bytes = canonicalize_json(payload)
    assert canonical_bytes == b'{"a":0,"b":1e-7,"c":[1,2.5]}'

def test_quasi_rrho_thermodynamics_provenance_logging():
    """Validates Suggestion #63: Quasi-harmonic thermodynamic parameter provenance logging."""
    class DummyNode:
        def __init__(self):
            self.payload = {}

    node = DummyNode()
    energies = [0.0, 0.5, 1.2]
    weights, prov = compute_boltzmann_weights(
        energies,
        temperature_k=298.15,
        low_freq_cutoff_cm1=100.0,
        damping_model="grimme_quasi_rrho",
        dag_node=node
    )
    assert len(weights) == 3
    assert math.isclose(sum(weights), 1.0, rel_tol=1e-6)
    assert "thermodynamics_provenance" in node.payload
    logged = node.payload["thermodynamics_provenance"]
    assert logged["damping_model"] == "grimme_quasi_rrho"
    assert logged["low_freq_cutoff_cm1"] == 100.0
    assert logged["temperature_k"] == 298.15
    assert logged["provenance_tag"] == "[D]"

def test_machine_actionable_exception_hierarchy():
    """Validates Suggestion #64: Structured exception hierarchy with machine-actionable error codes."""
    with pytest.raises(CoordinateShapeError) as exc_info:
        MolecularTopology(
            symbols=["H"],
            coordinates=[[0.0, 0.0]],
            molecular_charge=0,
            spin_multiplicity=1
        )
    err = exc_info.value
    assert err.error_code == "COCHEM_E_INVALID_COORD_SHAPE"
    assert err.details["actual_len"] == 2
    assert err.details["expected_len"] == 3

def test_dynamic_mendeleev_mass_resolution_lru_cache():
    """Validates Suggestion #66: LRU memory caching on dynamic Mendeleev mass resolution."""
    mass_c = get_dynamic_atomic_mass("C")
    assert math.isclose(mass_c, 12.011, rel_tol=1e-2)

    start = time.perf_counter()
    for _ in range(1000):
        _ = get_dynamic_atomic_mass("C")
    cached_duration = time.perf_counter() - start

    assert cached_duration < 0.005

    mass_14c = get_dynamic_isotopic_mass("C", 14)
    assert math.isclose(mass_14c, 14.003241, rel_tol=1e-4)

    with pytest.raises(IsotopeMassResolutionError):
        get_dynamic_isotopic_mass("C", 999)
```

---

### Deliverable 2: `tests/core/test_architecture_part7.py`
This test suite verifies architecture, concurrency, air-gap boundaries, and OS-level lifecycle management.

```python
import os
import time
import atexit
import threading
import tempfile
from pathlib import Path
import pytest
import h5py
from cochem_base.core.exceptions import AirGapBoundaryError
from cochem_base.core.mendeleev_invariants import get_element_cache
from cochem_base.core.cochem_sandbox import SandboxContext
from cochem_base.core.process_reaper import ProcessTreeManager
from cochem_base.core_engine.cochem_core_subprocess_broker import (
    verify_scratch_quota_and_io,
    _SCRATCH_VERIFICATION_CACHE
)

def test_hdf5_swmr_inplace_resizing_and_airgap(tmp_path):
    """Validates Suggestion #65: In-place HDF5 SWMR chunk resizing and Air-Gap enforcement."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    os.environ["COCH_SRC"] = str(src_dir)

    h5_src_path = src_dir / "store.h5"
    with pytest.raises(AirGapBoundaryError) as exc_info:
        from cochem_base.core.ipc.serializer import validate_airgap_write_path
        validate_airgap_write_path(h5_src_path)
    assert exc_info.value.error_code == "COCHEM_E_AIRGAP_BREACH"

    h5_scratch_path = tmp_path / "scratch" / "store.h5"
    h5_scratch_path.parent.mkdir()
    
    with h5py.File(h5_scratch_path, "w", libver="latest") as f:
        ds = f.create_dataset(
            "energies",
            shape=(1,),
            maxshape=(None,),
            chunks=(512,),
            dtype="float64",
            compression="gzip"
        )
        ds[0] = -76.432

    with h5py.File(h5_scratch_path, "a", libver="latest") as f:
        ds = f["energies"]
        new_len = ds.shape[0] + 1
        ds.resize((new_len,))
        ds[new_len - 1] = -76.435
        ds.flush()

    with h5py.File(h5_scratch_path, "r") as f:
        assert f["energies"].shape[0] == 2
        assert math.isclose(f["energies"][1], -76.435)

def test_mendeleev_invariants_lazy_singleton_startup():
    """Validates Suggestion #67: Lazy singleton initialization eliminates top-level import lag."""
    cache = get_element_cache()
    assert len(cache) >= 118
    assert cache[1].symbol == "H"
    assert cache[6].symbol == "C"

def test_sandbox_context_atexit_unregister_and_airgap(tmp_path):
    """Validates Suggestion #68: atexit callback unregistration on context exit."""
    scratch_dir = tmp_path / "scratch"
    os.environ["COCH_SCRATCH"] = str(scratch_dir)

    with SandboxContext(scratch_root=scratch_dir) as sb:
        assert sb.path.exists()

    assert not sb.path.exists()
    assert sb._cleaned is True

def test_process_reaper_direct_pid_monitoring():
    """Validates Suggestion #69: Direct child PID tracking in ProcessTreeManager."""
    manager = ProcessTreeManager()
    
    import subprocess
    import sys
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    manager.register_process(proc.pid)

    assert proc.pid in manager._tracked
    rss = manager.sample_process_tree_rss_bytes()
    assert rss > 0

    manager.terminate_tree()
    proc.wait()
    assert not proc.poll() is None

def test_subprocess_broker_scratch_verification_cache(tmp_path):
    """Validates Suggestion #70: Scratch verification caching with TTL."""
    scratch_dir = tmp_path / "scratch_io"
    scratch_dir.mkdir()
    _SCRATCH_VERIFICATION_CACHE.clear()

    t0 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t1 = time.perf_counter()
    initial_duration = t1 - t0

    t2 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t3 = time.perf_counter()
    cached_duration = t3 - t2

    assert cached_duration < 0.002
    assert cached_duration < initial_duration
```

---

## 5. Verification & Acceptance Criteria

1. **Zero-Mock & Zero-Stub Verification:**
   - Strict scan across all modified files. Zero occurrences of `unittest.mock`, `MagicMock`, `@patch`, `TODO`, `pass`, or `NotImplementedError` permitted.
2. **Full Test Suite Execution:**
   - Execute `pytest tests/core/test_physics_integrity_part7.py tests/core/test_architecture_part7.py`.
   - 100% of authored tests must pass with physical file operations, genuine Mendeleev lookups, real HDF5 SWMR resizing, physical subprocess tracking, and real RFC 8785 byte comparisons.
3. **Cross-Platform Path & Concurrency Hygiene:**
   - All paths must use `pathlib.Path.resolve()`. Zero hardcoded Windows drive letters (`C:`, `D:`) or POSIX-only roots in core modules.
   - Node-local scratch directory locking strictly enforced; zero lockfile allocation on remote parallel filesystems (Lustre/GPFS/NFS).
4. **Method Matrix Provenance Compliance:**
   - Dynamic mass retrieval strictly through `mendeleev`.
   - Zero CUDA runtime locking in orchestrator telemetry path.
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
| **Model Versioning** | Mandatory `schema_version` attribute and automated migration dispatcher | **PASS (VERIFIED)** |
| **RFC 8785 Float Parity** | ECMAScript IEEE 754 Number-to-String formatting kernel in `canonicalize_json` | **PASS (VERIFIED)** |
| **Thermodynamic Provenance** | Embedding Grimme quasi-RRHO cutoff and damping parameters into `DAGNode` | **PASS (VERIFIED)** |
| **Actionable Exceptions** | Structured `CoChemError` hierarchy with typed machine-actionable error codes | **PASS (VERIFIED)** |
| **In-Place SWMR Resizing** | Elimination of `shutil.copyfile` and implementation of in-place HDF5 `ds.resize` | **PASS (VERIFIED)** |
| **Mendeleev Mass Caching** | `@functools.lru_cache` on dynamic lookups without GPU context stalls | **PASS (VERIFIED)** |
| **Lazy Invariant Singleton** | Deferral of 118-element SQLite queries until first access; zero-lag module import | **PASS (VERIFIED)** |
| **Sandbox Memory Leaks** | Explicit `atexit.unregister(self.cleanup)` calls and Tier 3 scratch enforcement | **PASS (VERIFIED)** |
| **Reaper Direct Polling** | Querying registered child PIDs directly without recursive full-OS traversal | **PASS (VERIFIED)** |
| **Cached Scratch Probe** | Session-level scratch integrity cache with configurable TTL to eliminate fsync stalls | **PASS (VERIFIED)** |
| **Zero-Mock Mandate** | Zero stubs, zero mocks, zero synthetic loops across all 10 tasks and test suites | **PASS (VERIFIED)** |

**Council Ratification Verdict:** `RATIFIED: APPROVED FOR CODER IMPLEMENTATION`
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\core\exceptions.py ---
"""Authoritative Core Exception Hierarchy for CoChem Core.

Adheres to:
- Method Matrix [M] & Provenance Standards
- Zero-Mock Anti-Spoofing Protocol
- Dynamic Mendeleev Invariant Mandate
"""

from __future__ import annotations

from typing import Any, Optional

from cochem_base.core.exceptions import (
    AirGapBoundaryError,
    CoChemError,
    CoordinateShapeError,
    IsotopeMassResolutionError,
    IsotopeStabilityError,
    PESStorageError,
    ProcessReaperError,
    RadiusNotFoundError,
    SchemaMigrationError,
    SubprocessBrokerError,
    ThermodynamicsParameterError,
)

try:
    from cochem_base.exceptions import (
        MissingDataError as BaseMissingDataError,
        SingularityError,
    )
except ImportError:
    class BaseMissingDataError(CoChemError, KeyError):
        def __init__(self, message: str, details: Optional[Any] = None) -> None:
            super().__init__(message, error_code="COCHEM_E_MISSING_DATA")

    class SingularityError(CoChemError, ValueError):
        def __init__(self, message: str, details: Optional[Any] = None) -> None:
            super().__init__(message, error_code="COCHEM_E_SINGULARITY")


class MissingDataError(BaseMissingDataError):
    """Raised when required element, isotope, basis set, or calculation data is missing."""

    def __init__(self, message: str, symbol_or_query: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.symbol_or_query = symbol_or_query


class MendeleevInvariantError(MissingDataError):
    """Raised when chemical element or isotopic queries violate Mendeleev physical invariants."""

    def __init__(self, message: str, symbol_or_query: Optional[Any] = None) -> None:
        super().__init__(message, symbol_or_query=symbol_or_query)


class RotationalGridInstabilityError(CoChemError, ValueError):
    """Raised when Cartesian DFT integration grid breaks rotational invariance or induces imaginary modes."""

    def __init__(self, message: str, delta_cm1: Optional[float] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_ROT_GRID_INSTABILITY")
        self.message = message
        self.delta_cm1 = delta_cm1


class JobTimeoutError(CoChemError, TimeoutError):
    """Raised when an asynchronous calculation or subprocess job exceeds temporal limits."""

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_JOB_TIMEOUT")


__all__ = [
    "CoChemError",
    "MissingDataError",
    "MendeleevInvariantError",
    "RotationalGridInstabilityError",
    "JobTimeoutError",
    "CoordinateShapeError",
    "AirGapBoundaryError",
    "SchemaMigrationError",
    "PESStorageError",
    "ProcessReaperError",
    "SubprocessBrokerError",
    "ThermodynamicsParameterError",
    "IsotopeMassResolutionError",
    "IsotopeStabilityError",
    "RadiusNotFoundError",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\core\ipc\serializer.py ---
"""Pure-Wheel Fast IPC Serialization & HDF5 PESStore.
High-throughput binary Msgpack serialization, SharedMemory descriptors, HMAC socket transport,
and QCSchema-compliant HDF5 tensor persistence in SWMR mode.
Strictly adheres to Zero-Mock mandate and authentic binary serialization.
"""

from __future__ import annotations

import atexit
import dataclasses
import datetime
import errno
import hashlib
import hmac
import json
import logging
import multiprocessing.shared_memory as sm
import os
import pathlib
import secrets
import shutil
import socket
import struct
import tempfile
import threading
import time
import uuid
import weakref
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
import h5py
import msgpack  # type: ignore[import-untyped]
import numpy as np
from pydantic import BaseModel

from cochem.core.context import assert_writable_path

logger = logging.getLogger("cochem.core.ipc.serializer")

NUMPY_EXT_CODE: int = 42

MAX_IPC_PAYLOAD_BYTES: int = 256 * 1024 * 1024  # 256 MB ceiling [D]


class IPCBindError(OSError):
    """Base exception for IPC socket binding failures."""

    pass


class PortContentionError(IPCBindError):
    """Raised when an IPC port remains in contention after retry exhaustion."""

    pass


class IPCPayloadError(Exception):
    """Base exception for IPC payload transmission failures."""

    pass


class TruncatedPayloadError(IPCPayloadError):
    """Raised when an IPC connection terminates before receiving the full payload."""

    pass


class OversizedPayloadError(IPCPayloadError):
    """Raised when a transmitted payload header exceeds the safety ceiling."""

    pass


# ==============================================================================
# Msgpack Custom Extension Codecs
# ==============================================================================
def _msgpack_encoder(obj: Any) -> Any:
    """Encode custom structures (NumPy arrays, Pydantic models, Path/UUID) for Msgpack."""
    if isinstance(obj, np.ndarray):
        dtype_str = obj.dtype.str  # type: ignore[attr-defined]
        shape_tuple = tuple(obj.shape)
        raw_buffer = obj.tobytes()
        payload = msgpack.packb((dtype_str, shape_tuple, raw_buffer), use_bin_type=True)
        return msgpack.ExtType(NUMPY_EXT_CODE, payload)
    elif isinstance(obj, BaseModel):
        return obj.model_dump()
    elif isinstance(obj, (pathlib.Path, uuid.UUID)):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON/Msgpack serializable")


def _msgpack_decoder(code: int, data: bytes) -> Any:
    """Reconstruct NumPy arrays from Msgpack custom extension payload."""
    if code == NUMPY_EXT_CODE:
        dtype_str, shape_tuple, raw_buffer = msgpack.unpackb(data, raw=False)
        reconstructed = np.frombuffer(raw_buffer, dtype=dtype_str).reshape(tuple(shape_tuple))
        return reconstructed
    return msgpack.ExtType(code, data)


def pack_payload(data: Any) -> bytes:
    """Serialize payload into binary Msgpack bytes with NumPy array extension hooks."""
    return bytes(msgpack.packb(data, default=_msgpack_encoder, use_bin_type=True))


def unpack_payload(raw_bytes: bytes) -> Any:
    """Deserialize binary Msgpack payload and reconstruct NumPy arrays."""
    return msgpack.unpackb(raw_bytes, ext_hook=_msgpack_decoder, raw=False)


# ==============================================================================
# Zero-Copy Shared Memory Optimization
# ==============================================================================
_REGISTRY_LOCK = threading.Lock()
_ACTIVE_SHM: Dict[str, Dict[str, Any]] = {}


def _cleanup_all_shared_memory() -> None:
    """Atexit handler ensuring zero lingering shared memory blocks."""
    with _REGISTRY_LOCK:
        for name, info in list(_ACTIVE_SHM.items()):
            try:
                info["shm"].close()
            except Exception:
                pass
            try:
                info["shm"].unlink()
            except Exception:
                pass
        _ACTIVE_SHM.clear()


atexit.register(_cleanup_all_shared_memory)


def _finalize_shm(name: str) -> None:
    with _REGISTRY_LOCK:
        info = _ACTIVE_SHM.pop(name, None)
    if info is not None:
        try:
            info["shm"].close()
            info["shm"].unlink()
        except (FileNotFoundError, OSError):
            pass
    try:
        s = sm.SharedMemory(name=name)
        s.close()
        s.unlink()
    except (FileNotFoundError, OSError):
        pass


@dataclasses.dataclass
class SharedMemoryBuffer:
    """Encapsulates a POSIX/Windows shared memory segment for large array transfers."""

    shm: sm.SharedMemory
    descriptor: Dict[str, Any]
    _finalizer: Optional[weakref.finalize] = dataclasses.field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._finalizer is None:
            self._finalizer = weakref.finalize(self, _finalize_shm, self.shm.name)

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

    @classmethod
    def from_array(cls, arr: np.ndarray, total_attachments: int = 2) -> SharedMemoryBuffer:
        """Allocate shared memory buffer, copy array memory, and generate transfer descriptor."""
        total_bytes = max(1, arr.nbytes)
        shm = sm.SharedMemory(create=True, size=total_bytes)
        try:
            from multiprocessing import resource_tracker
            resource_tracker.register(shm._name, "shared_memory")
        except Exception as exc:
            logger.debug("Resource tracker registration bypassed: %s", exc)

        shm_array = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)  # type: ignore[arg-type]
        shm_array[:] = arr[:]

        desc = {
            "name": shm.name,
            "shape": list(arr.shape),
            "dtype": arr.dtype.str,  # type: ignore[attr-defined]
            "size": total_bytes,
            "total_attachments": total_attachments,
            "closed_attachments": 0,
        }

        with _REGISTRY_LOCK:
            _ACTIVE_SHM[shm.name] = {
                "shm": shm,
                "total": total_attachments,
                "closed": 0,
            }

        return cls(shm=shm, descriptor=desc)

    @classmethod
    def _notify_closed(cls, name: str) -> None:
        """Atomically increment closed attachments and unlink once all attachments finish."""
        with _REGISTRY_LOCK:
            info = _ACTIVE_SHM.get(name)
            if info is not None:
                info["closed"] += 1
                if info["closed"] >= info["total"]:
                    try:
                        info["shm"].unlink()
                    except (OSError, FileNotFoundError) as exc:
                        logger.debug("Shared memory unlink bypassed: %s", exc)
                    _ACTIVE_SHM.pop(name, None)
            else:
                try:
                    s = sm.SharedMemory(name=name)
                    s.close()
                    s.unlink()
                except Exception as exc:
                    logger.debug("Shared memory cleanup bypassed: %s", exc)

    @classmethod
    def read_from_descriptor(cls, descriptor: Dict[str, Any]) -> np.ndarray:
        """Map existing shared memory segment and extract copy of array."""
        name = descriptor["name"]
        shape = tuple(descriptor["shape"])
        dtype = descriptor["dtype"]

        client_shm = sm.SharedMemory(name=name)
        try:
            mapped = np.ndarray(shape, dtype=dtype, buffer=client_shm.buf)
            extracted = mapped.copy()
            return extracted
        finally:
            client_shm.close()
            cls._notify_closed(name)

    def close(self) -> None:
        """Close local memory map and unlink if all attachments are closed."""
        try:
            self.shm.close()
        except OSError as exc:
            logger.debug("Shared memory close bypassed: %s", exc)
        SharedMemoryBuffer._notify_closed(self.shm.name)

    def unlink(self) -> None:
        """Explicitly unlink OS shared memory segment immediately."""
        if self._finalizer is not None and self._finalizer.alive:
            self._finalizer.detach()
        try:
            self.shm.unlink()
        except (OSError, FileNotFoundError) as exc:
            logger.debug("Shared memory unlink bypassed: %s", exc)
        with _REGISTRY_LOCK:
            _ACTIVE_SHM.pop(self.shm.name, None)


# ==============================================================================
# Ephemeral HMAC-SHA256 Socket Transport
# ==============================================================================
class HMACSocketServer:
    """Loopback TCP socket server secured by HMAC-SHA256 challenge-response handshake."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        secret_key: bytes = b"",
    ) -> None:
        self.host: str = host
        self.requested_port: int = port
        self.secret_key: bytes = secret_key
        self.port: int = 0

        self._server_sock: Optional[socket.socket] = None
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._received_payloads: List[Any] = []
        self._payload_event: threading.Event = threading.Event()
        self._last_error: Optional[IPCPayloadError] = None
        self._descriptor_path: Optional[pathlib.Path] = None

    def start(self, port_fallback: bool = True, max_retries: int = 5) -> int:
        """Bind listening socket and launch background accept loop.

        Recovers dynamically from port contention (EADDRINUSE / WinError 10048).
        Publishes atomic port descriptor to COCHEM_SCRATCH_DIR.
        """
        target_port = self.requested_port
        backoff_base = 0.05
        bound = False

        for attempt in range(max_retries):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self.host, target_port))
                sock.listen(5)
                self._server_sock = sock
                self.port = sock.getsockname()[1]
                bound = True
                break
            except OSError as err:
                sock.close()
                self._server_sock = None
                # Check for port contention: EADDRINUSE or Windows 10048 / 10013 / EACCES
                is_in_use = (
                    err.errno in (errno.EADDRINUSE, errno.EACCES)
                    or getattr(err, "winerror", None) in (10048, 10013)
                    or err.errno in (10048, 10013)
                )
                if is_in_use:
                    if port_fallback:
                        # Fallback immediately to ephemeral port 0
                        fb_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        fb_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        try:
                            fb_sock.bind((self.host, 0))
                            fb_sock.listen(5)
                            self._server_sock = fb_sock
                            self.port = fb_sock.getsockname()[1]
                            bound = True
                            break
                        except OSError as fb_err:
                            fb_sock.close()
                            self._server_sock = None
                            raise IPCBindError(f"Failed to bind ephemeral fallback port: {fb_err}") from fb_err
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(backoff_base * (2**attempt))
                            continue
                        else:
                            raise PortContentionError(
                                f"Port {target_port} contention exhausted after {max_retries} retries: {err}"
                            ) from err
                else:
                    raise IPCBindError(f"Socket bind failed on {self.host}:{target_port}: {err}") from err

        if not bound or self._server_sock is None:
            raise PortContentionError(f"Could not bind to port {target_port}")

        # Publish active binding metadata to atomic file ipc_server_{pid}.json in COCHEM_SCRATCH_DIR
        scratch_dir_env = (
            os.environ.get("COCHEM_SCRATCH_DIR")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TMPDIR")
        )
        if scratch_dir_env:
            scratch_dir = pathlib.Path(scratch_dir_env).resolve()
        else:
            scratch_dir = pathlib.Path(tempfile.gettempdir()).resolve()
        scratch_dir.mkdir(parents=True, exist_ok=True)

        pid = os.getpid()
        desc_file = scratch_dir / f"ipc_server_{pid}.json"
        tmp_file = scratch_dir / f"ipc_server_{pid}_{uuid.uuid4().hex[:8]}.tmp"

        auth_token_hash = hashlib.sha256(self.secret_key).hexdigest()
        created_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta = {
            "pid": pid,
            "host": self.host,
            "port": self.port,
            "created_utc": created_utc,
            "auth_token_hash": auth_token_hash,
        }

        payload_bytes = json.dumps(meta, indent=2).encode("utf-8")
        with open(tmp_file, "wb") as f:
            f.write(payload_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, desc_file)
        self._descriptor_path = desc_file

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._accept_loop,
            name="HMACSocketServerLoop",
            daemon=True,
        )
        self._thread.start()
        return self.port

    def stop(self) -> None:
        """Shutdown server socket, clean up descriptor file, and join accept thread."""
        self._stop_event.set()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError as exc:
                logger.debug("Server socket close error ignored: %s", exc)
            self._server_sock = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._descriptor_path is not None and self._descriptor_path.exists():
            try:
                self._descriptor_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.debug("Descriptor unlink error ignored: %s", exc)
            self._descriptor_path = None

    def _accept_loop(self) -> None:
        """Accept inbound client connections and execute HMAC handshake."""
        while not self._stop_event.is_set():
            try:
                if self._server_sock is None:
                    break
                self._server_sock.settimeout(0.5)
                conn, _ = self._server_sock.accept()
            except (socket.timeout, OSError):
                continue

            try:
                # 1. Ephemeral 32-byte cryptographic challenge
                challenge = secrets.token_bytes(32)
                conn.sendall(challenge)

                # 2. Receive 32-byte HMAC-SHA256 response
                response = conn.recv(32)
                expected = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()

                if not hmac.compare_digest(response, expected):
                    logger.warning("IPC connection rejected: HMAC authentication failed")
                    conn.sendall(b"DENIED")
                    conn.close()
                    continue

                conn.sendall(b"ACCEPT")

                # 3. Read 4-byte payload length header
                len_bytes = conn.recv(4)
                if len(len_bytes) < 4:
                    conn.close()
                    continue
                (payload_len,) = struct.unpack("!I", len_bytes)

                if payload_len > MAX_IPC_PAYLOAD_BYTES:
                    logger.error("IPC payload rejected: size %d exceeds 256 MB ceiling", payload_len)
                    self._last_error = OversizedPayloadError(
                        f"Payload size {payload_len} exceeds 256 MB limit"
                    )
                    self._payload_event.set()
                    conn.close()
                    continue

                # 4. Stream payload bytes
                buffer = bytearray()
                while len(buffer) < payload_len:
                    chunk = conn.recv(min(65536, payload_len - len(buffer)))
                    if not chunk:
                        break
                    buffer.extend(chunk)

                if len(buffer) < payload_len:
                    logger.error("IPC stream truncated: received %d of %d bytes", len(buffer), payload_len)
                    self._last_error = TruncatedPayloadError(
                        f"Stream truncated: received {len(buffer)} of {payload_len} bytes"
                    )
                    self._payload_event.set()
                    conn.close()
                    continue

                if len(buffer) == payload_len:
                    payload = unpack_payload(bytes(buffer))
                    self._received_payloads.append(payload)
                    self._payload_event.set()
            except Exception as conn_err:
                logger.debug("Error processing client connection: %s", conn_err)
            finally:
                try:
                    conn.close()
                except OSError as exc:
                    logger.debug("Client conn close error ignored: %s", exc)

    def get_received_payload(self, timeout_sec: float = 5.0) -> Optional[Any]:
        """Await reception of payload from client."""
        if self._payload_event.wait(timeout_sec):
            if self._last_error is not None:
                err = self._last_error
                self._last_error = None
                self._payload_event.clear()
                raise err
            if self._received_payloads:
                payload = self._received_payloads.pop(0)
                if not self._received_payloads:
                    self._payload_event.clear()
                return payload
        if self._last_error is not None:
            err = self._last_error
            self._last_error = None
            raise err
        return None


class HMACSocketClient:
    """Client communicating over loopback TCP with HMAC-SHA256 authentication."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        secret_key: bytes = b"",
    ) -> None:
        self.host: str = host
        self.port: int = port
        self.secret_key: bytes = secret_key

    def send_payload(self, data: Any) -> None:
        """Connect to server, satisfy HMAC challenge, and transmit Msgpack payload."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        try:
            # 1. Receive 32-byte challenge
            challenge = sock.recv(32)
            if len(challenge) != 32:
                raise ConnectionError("Invalid challenge received from server")

            # 2. Compute and send response
            response = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()
            sock.sendall(response)

            status = sock.recv(6)
            if status != b"ACCEPT":
                raise PermissionError("HMAC handshake rejected by server")

            # 3. Pack payload and send with length header
            packed_bytes = pack_payload(data)
            header = struct.pack("!I", len(packed_bytes))
            sock.sendall(header + packed_bytes)
        finally:
            sock.close()


# ==============================================================================
# HDF5 PESStore Tensor Persistence (QCSchema & SWMR)
# ==============================================================================
from cochem_base.core.ipc.serializer import validate_airgap_write_path


class PESStore:
    """Multidimensional tensor persistence store for Potential Energy Surfaces using HDF5 SWMR."""

    def __init__(self, file_path: Union[pathlib.Path, str]) -> None:
        self.file_path: pathlib.Path = validate_airgap_write_path(pathlib.Path(file_path).resolve())
        assert_writable_path(self.file_path)
        self.lock_path: pathlib.Path = pathlib.Path(str(self.file_path) + ".lock").resolve()
        self._write_lock: threading.RLock = threading.RLock()

    def write_entry(
        self,
        entry_id: str,
        molecule: Dict[str, Any],
        driver: str,
        model: Dict[str, Any],
        return_result: np.ndarray,
    ) -> None:
        """Persist QCSchema calculation entry into HDF5 file in SWMR mode."""
        validate_airgap_write_path(self.file_path)
        assert_writable_path(self.file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if shutil.disk_usage(self.file_path.parent).free < 100 * 1024 * 1024:
            raise IOError("Insufficient disk space on target volume for PESStore append")

        arr = np.asarray(return_result)
        chunk_shape: Optional[Tuple[int, ...]] = None
        max_shape: Optional[Tuple[Optional[int], ...]] = None
        if arr.ndim > 0:
            chunk_shape = tuple(max(1, min(s, 128)) for s in arr.shape)
            max_shape = tuple(None for _ in arr.shape)

        with self._write_lock:
            with filelock.FileLock(str(self.lock_path), timeout=30.0):
                with h5py.File(self.file_path, "a", libver="latest") as h5f:
                    if entry_id in h5f:
                        del h5f[entry_id]

                    grp = h5f.create_group(entry_id)
                    grp.attrs["schema_name"] = "qcschema_output"
                    grp.attrs["driver"] = str(driver)
                    grp.attrs["molecule_json"] = json.dumps(molecule)
                    grp.attrs["model_json"] = json.dumps(model)

                    if arr.ndim > 0:
                        grp.create_dataset(
                            "return_result",
                            data=arr,
                            maxshape=max_shape,
                            chunks=chunk_shape,
                            compression="gzip",
                            compression_opts=4,
                            fletcher32=True,
                        )
                    else:
                        grp.create_dataset("return_result", data=arr)

                    h5f.flush()

    def read_entry(self, entry_id: str) -> Dict[str, Any]:
        """Read QCSchema entry in SWMR mode without file locking collisions."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"PESStore file not found at {self.file_path}")

        with h5py.File(self.file_path, "r", libver="latest", swmr=True) as h5f:
            if entry_id not in h5f:
                raise KeyError(f"Entry '{entry_id}' not found in PESStore")

            grp = h5f[entry_id]
            schema_name = str(grp.attrs.get("schema_name", "qcschema_output"))
            driver = str(grp.attrs.get("driver", "unknown"))
            mol_json = str(grp.attrs.get("molecule_json", "{}"))
            model_json = str(grp.attrs.get("model_json", "{}"))
            result_arr = grp["return_result"][:]

            return {
                "schema_name": schema_name,
                "entry_id": entry_id,
                "molecule": json.loads(mol_json),
                "driver": driver,
                "model": json.loads(model_json),
                "return_result": result_arr,
            }

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem\core\mendeleev_invariants.py ---
"""Dynamic Mendeleev Invariants & Element Resolver.

Provenance & Specifications:
- Method Matrix [M]: Quantum spin-parity and IUPAC CIAAW standard atomic weight invariants.
- Dynamic Resolution [D]: Zero-hardcoding dynamic element and isotopic mass lookup via mendeleev.
- Telemetry [E]: Thread-safe in-memory cache populated dynamically on demand.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from mendeleev import element as _mendeleev_element

from cochem.core.exceptions import MissingDataError


class MendeleevInvariantError(ValueError, MissingDataError):
    """Raised when chemical element queries violate Mendeleev physical invariants."""

    def __init__(self, message: str, symbol_or_query: Any = None) -> None:
        ValueError.__init__(self, message)
        MissingDataError.__init__(
            self,
            message=message,
            symbol_or_query=symbol_or_query,
        )
        self.symbol_or_query = symbol_or_query


@dataclass(slots=True, frozen=True)
class ElementData:
    """Immutable ground-truth chemical element properties."""

    atomic_number: int
    symbol: str
    name: str
    atomic_weight: float
    isotopes: Tuple[Tuple[int, float, float], ...]  # (mass_number, exact_mass_amu, natural_abundance)
    covalent_radius_pm: Optional[float]
    vdw_radius_pm: Optional[float]
    valence_electrons: int
    mass: float = 0.0
    mass_number: Optional[int] = None
    formal_charge: int = 0
    is_isotope: bool = False


_CACHE_LOCK = threading.Lock()
_ELEMENTS_BY_SYMBOL: Dict[str, ElementData] = {}
_ELEMENTS_BY_Z: Dict[int, ElementData] = {}


def _load_element_data(z_or_sym: Union[int, str]) -> ElementData:
    """Dynamically fetch and cache ElementData for Z=1..118 via mendeleev."""
    try:
        elem = _mendeleev_element(z_or_sym)
    except Exception as exc:
        raise MendeleevInvariantError(
            f"Dynamic element resolution failed for query '{z_or_sym}': {exc}",
            symbol_or_query=z_or_sym,
        ) from exc

    z = int(elem.atomic_number)
    symbol = str(elem.symbol)
    name = str(elem.name)

    # Standard atomic weight with dynamic fallback to most stable isotope mass
    weight = elem.atomic_weight
    if weight is None or float(weight) <= 0.0:
        iso_masses = [iso.mass_number for iso in elem.isotopes if iso.mass_number is not None]
        if iso_masses:
            weight = float(max(iso_masses))
        else:
            weight = float(z)
    else:
        weight = float(weight)

    # Isotope tuple: (mass_number, exact_mass_amu, abundance)
    isotope_list: List[Tuple[int, float, float]] = []
    for iso in elem.isotopes:
        if iso.mass_number is not None:
            m_num = int(iso.mass_number)
            m_exact = float(iso.mass) if iso.mass is not None and float(iso.mass) > 0.0 else float(m_num)
            m_abund = float(iso.abundance) if iso.abundance is not None else 0.0
            isotope_list.append((m_num, m_exact, m_abund))
    isotopes_tuple = tuple(sorted(isotope_list, key=lambda x: x[0]))

    # Radii in picometers
    cov_r = elem.covalent_radius_pyykko or elem.covalent_radius
    cov_radius_pm = float(cov_r) if cov_r is not None else None

    vdw_r = elem.vdw_radius or elem.vdw_radius_alvarez or elem.vdw_radius_bondi or elem.vdw_radius_batsanov
    vdw_radius_pm = float(vdw_r) if vdw_r is not None else None

    # Valence electrons
    if hasattr(elem, "nvalence") and callable(elem.nvalence):
        val_e = int(elem.nvalence())
    elif elem.electrons is not None:
        val_e = int(elem.electrons)
    else:
        val_e = 0

    data = ElementData(
        atomic_number=z,
        symbol=symbol,
        name=name,
        atomic_weight=weight,
        isotopes=isotopes_tuple,
        covalent_radius_pm=cov_radius_pm,
        vdw_radius_pm=vdw_radius_pm,
        valence_electrons=val_e,
        mass=weight,
        mass_number=None,
        formal_charge=0,
        is_isotope=False,
    )

    with _CACHE_LOCK:
        _ELEMENTS_BY_SYMBOL[symbol] = data
        _ELEMENTS_BY_Z[z] = data

    return data


def parse_symbol_or_isotope(symbol: str) -> Tuple[str, Optional[int]]:
    """Authoritative regex and alias pre-processor for chemical symbols and isotopes.

    Maps:
    - 'D' -> ('H', 2)
    - 'T' -> ('H', 3)
    - '13C' -> ('C', 13)
    - '18O' -> ('O', 18)
    - '2H' -> ('H', 2)
    - Standard symbols ('H', 'C', 'Ar') -> ('H', None), etc.
    """
    raw = str(symbol).strip()
    if not raw or raw.isdigit():
        raise MissingDataError(
            f"Invalid chemical symbol or isotope '{symbol}'. Symbol cannot be empty or purely numeric.",
            symbol_or_query=symbol,
        )

    # Specific alias mappings
    if raw.upper() == "D":
        return "H", 2
    if raw.upper() == "T":
        return "H", 3

    # Check for leading mass number: e.g. "13C", "18O", "2H", "35Cl"
    m_iso = re.match(r"^(\d+)([A-Za-z]+)$", raw)
    if m_iso:
        mass_num = int(m_iso.group(1))
        sym_part = m_iso.group(2)
        norm_sym = sym_part[0].upper() + sym_part[1:].lower() if len(sym_part) > 1 else sym_part.upper()
        # Verify element exists in Mendeleev
        try:
            get_element(norm_sym)
        except Exception:
            raise MissingDataError(
                f"Unresolvable atomic element or isotope symbol: {symbol}",
                symbol_or_query=symbol,
            )
        return norm_sym, mass_num

    # Standard elemental symbol: e.g. "C", "Cl", "Ar"
    m_sym = re.match(r"^[A-Za-z]+$", raw)
    if m_sym:
        norm_sym = raw[0].upper() + raw[1:].lower() if len(raw) > 1 else raw.upper()
        try:
            elem_data = get_element(norm_sym)
            return elem_data.symbol, None
        except Exception:
            # Check by element name
            try:
                elem_data = _load_element_data(raw)
                return elem_data.symbol, None
            except Exception:
                pass

    raise MissingDataError(
        f"Unresolvable atomic element or isotope symbol: {symbol}",
        symbol_or_query=symbol,
    )


def get_element(symbol_or_z: Union[str, int]) -> ElementData:
    """Retrieve immutable ElementData by atomic number, chemical symbol, formal charge, or isotope."""
    if isinstance(symbol_or_z, int):
        if symbol_or_z < 1 or symbol_or_z > 118:
            raise MendeleevInvariantError(
                f"Invalid atomic number Z={symbol_or_z}. Must be between 1 and 118.",
                symbol_or_query=symbol_or_z,
            )
        with _CACHE_LOCK:
            cached = _ELEMENTS_BY_Z.get(symbol_or_z)
        if cached is not None:
            return cached
        return _load_element_data(symbol_or_z)

    raw = str(symbol_or_z).strip()
    if not raw or raw.isdigit():
        raise MendeleevInvariantError(
            f"Invalid chemical symbol '{symbol_or_z}'. Symbol cannot be empty or purely numeric.",
            symbol_or_query=symbol_or_z,
        )

    pattern = re.compile(r"^(?P<isotope>\d+)?(?P<symbol>[A-Za-z]+)(?P<charge>(?:\d+[+-]|[+-]\d*|[+-]))?$")
    match = pattern.match(raw)
    if not match:
        raise MendeleevInvariantError(
            f"Dynamic element resolution failed for query '{symbol_or_z}'.",
            symbol_or_query=symbol_or_z,
        )

    iso_str = match.group("isotope")
    sym_raw = match.group("symbol")
    charge_str = match.group("charge")

    # Alias mappings for Deuterium (D) and Tritium (T)
    if sym_raw.upper() == "D":
        norm_sym = "H"
        mass_number: Optional[int] = 2
    elif sym_raw.upper() == "T":
        norm_sym = "H"
        mass_number = 3
    else:
        norm_sym = sym_raw[0].upper() + sym_raw[1:].lower() if len(sym_raw) > 1 else sym_raw.upper()
        mass_number = int(iso_str) if iso_str else None

    formal_charge: int = 0
    if charge_str:
        if charge_str.endswith("+"):
            val = charge_str[:-1]
            formal_charge = int(val) if val else 1
        elif charge_str.endswith("-"):
            val = charge_str[:-1]
            formal_charge = -int(val) if val else -1
        elif charge_str.startswith("+"):
            val = charge_str[1:]
            formal_charge = int(val) if val else 1
        elif charge_str.startswith("-"):
            val = charge_str[1:]
            formal_charge = -int(val) if val else -1

    # Dynamic lookup via mendeleev
    try:
        elem = _mendeleev_element(norm_sym)
        base_data = _load_element_data(norm_sym)
    except Exception as exc:
        # Fallback to query by full element name (e.g. 'Carbon')
        try:
            elem = _mendeleev_element(sym_raw)
            base_data = _load_element_data(sym_raw)
            norm_sym = str(elem.symbol)
        except Exception:
            raise MendeleevInvariantError(
                f"Dynamic element resolution failed for query '{symbol_or_z}': element '{norm_sym}' not found.",
                symbol_or_query=symbol_or_z,
            ) from exc

    if mass_number is not None:
        is_isotope = True
        iso = next((i for i in elem.isotopes if i.mass_number == mass_number), None)
        if iso is None or iso.mass is None or float(iso.mass) <= 0.0:
            raise MendeleevInvariantError(
                f"No isotope with mass number A={mass_number} found for element '{norm_sym}'.",
                symbol_or_query=symbol_or_z,
            )
        mass = float(iso.mass)
    else:
        is_isotope = False
        mass = float(base_data.atomic_weight)

    return ElementData(
        atomic_number=base_data.atomic_number,
        symbol=base_data.symbol,
        name=base_data.name,
        atomic_weight=base_data.atomic_weight,
        isotopes=base_data.isotopes,
        covalent_radius_pm=base_data.covalent_radius_pm,
        vdw_radius_pm=base_data.vdw_radius_pm,
        valence_electrons=base_data.valence_electrons,
        mass=mass,
        mass_number=mass_number,
        formal_charge=formal_charge,
        is_isotope=is_isotope,
    )


def get_isotope_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Dynamically resolve IUPAC exact isotopic mass in unified atomic mass units (u)."""
    element_data = get_element(symbol_or_z)
    for iso_m_num, iso_exact, _ in element_data.isotopes:
        if iso_m_num == mass_number:
            return iso_exact

    # Dynamic fallback query directly to mendeleev element isotopes
    try:
        m_elem = _mendeleev_element(element_data.symbol)
        for iso in m_elem.isotopes:
            if iso.mass_number == mass_number and iso.mass is not None:
                return float(iso.mass)
    except Exception:
        pass

    raise MendeleevInvariantError(
        f"No isotope with mass number A={mass_number} found for element '{element_data.symbol}'.",
        symbol_or_query=f"{element_data.symbol}-{mass_number}",
    )


def get_element_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically resolve atomic or isotopic mass in unified atomic mass units (u).

    Handles standard elements ('H', 'C', 'Ar') and isotopic aliases ('D', 'T', '13C', '18O').
    """
    if isinstance(symbol_or_z, int):
        return get_element(symbol_or_z).atomic_weight

    clean_sym, mass_number = parse_symbol_or_isotope(symbol_or_z)
    if mass_number is not None:
        return get_isotope_mass(clean_sym, mass_number)
    return get_element(clean_sym).atomic_weight


class MendeleevResolver:
    """Thread-safe dynamic Mendeleev element and isotope mass resolver for backward compatibility."""

    def get_element(self, symbol_or_z: Union[str, int]) -> Any:
        elem_data = get_element(symbol_or_z)
        return _mendeleev_element(elem_data.atomic_number)

    def get_atomic_number(self, symbol_or_z: Union[str, int]) -> int:
        return get_element(symbol_or_z).atomic_number

    def get_atomic_weight(self, symbol_or_z: Union[str, int]) -> float:
        return get_element(symbol_or_z).atomic_weight

    def get_element_mass(self, symbol_or_z: Union[str, int]) -> float:
        return get_element_mass(symbol_or_z)

    def get_symbol(self, symbol_or_z: Union[str, int]) -> str:
        return get_element(symbol_or_z).symbol

    def get_name(self, symbol_or_z: Union[str, int]) -> str:
        return get_element(symbol_or_z).name

    def get_covalent_radius(self, symbol_or_z: Union[str, int]) -> Optional[float]:
        return get_element(symbol_or_z).covalent_radius_pm

    def get_vdw_radius(self, symbol_or_z: Union[str, int]) -> float:
        r = get_element(symbol_or_z).vdw_radius_pm
        if r is None:
            raise MissingDataError(f"Van der Waals radius is not available for element '{symbol_or_z}'.")
        return r

    def get_vdw_radius_angstrom(self, symbol_or_z: Union[str, int]) -> float:
        return self.get_vdw_radius(symbol_or_z) / 100.0

    def get_isotope_mass(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        return get_isotope_mass(symbol_or_z, mass_number)

    def get_isotope_abundance(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        elem_data = get_element(symbol_or_z)
        for m_num, _, abund in elem_data.isotopes:
            if m_num == mass_number:
                return abund
        return 0.0

    def get_available_isotopes(self, symbol_or_z: Union[str, int]) -> List[int]:
        return [m_num for m_num, _, _ in get_element(symbol_or_z).isotopes]

    def clear_cache(self) -> None:
        raise MissingDataError("Mendeleev element cache is immutable and cannot be cleared.")


# Default global resolver instance for backwards compatibility
mendeleev_resolver = MendeleevResolver()

from cochem_base.core.mendeleev_invariants import get_element_cache

__all__ = [
    "ElementData",
    "MendeleevInvariantError",
    "MissingDataError",
    "get_element_cache",
    "get_element",
    "get_isotope_mass",
    "get_element_mass",
    "parse_symbol_or_isotope",
    "MendeleevResolver",
    "mendeleev_resolver",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_crypto.py ---
"""Authoritative IETF RFC 8032 PureEd25519, RFC 8785 JSON Canonicalization Scheme (JCS), & W3C Linked Data Proofs.

Provides pure asymmetric cryptographic provenance generation, verification, and offline
did:key resolution using multicodec 0xed01 prefix and base58btc encoding.
Eradicates non-standard intermediate SHA-512 pre-hashing, signing raw canonical bytes directly.
Includes an RFC 8785 §3.2.2.3 compliant ECMAScript IEEE 754 float formatting kernel.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel

# Standard Bitcoin / IPFS base58btc alphabet
B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ED25519_MULTICODEC_PREFIX = b"\xed\x01"


def b58encode(data: bytes) -> str:
    """Encode bytes into base58btc string."""
    orig_len = len(data)
    data_stripped = data.lstrip(b"\x00")
    leading_zeros = orig_len - len(data_stripped)

    if not data_stripped:
        return "1" * leading_zeros

    acc = int.from_bytes(data_stripped, byteorder="big")
    chars = []
    while acc > 0:
        acc, rem = divmod(acc, 58)
        chars.append(B58_ALPHABET[rem])

    res = "".join(reversed(chars))
    return ("1" * leading_zeros) + res


def b58decode(s: str) -> bytes:
    """Decode base58btc string into raw bytes."""
    orig_len = len(s)
    s_stripped = s.lstrip("1")
    leading_zeros = orig_len - len(s_stripped)

    if not s_stripped:
        return b"\x00" * leading_zeros

    acc = 0
    for char in s_stripped:
        idx = B58_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid character '{char}' in base58 string")
        acc = acc * 58 + idx

    byte_len = (acc.bit_length() + 7) // 8
    raw = acc.to_bytes(byte_len, byteorder="big")
    return (b"\x00" * leading_zeros) + raw


def public_key_to_did_key(public_key: Union[ed25519.Ed25519PublicKey, bytes]) -> str:
    """Encode an Ed25519 public key into a standard W3C did:key identifier offline [D].

    Prefixes raw 32-byte key with multicodec 0xed01 and encodes with base58btc.
    """
    if hasattr(public_key, "public_bytes_raw"):
        raw_bytes = public_key.public_bytes_raw()
    elif isinstance(public_key, ed25519.Ed25519PublicKey):
        raw_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    elif isinstance(public_key, bytes):
        raw_bytes = public_key
    else:
        raise TypeError(f"Expected Ed25519PublicKey or 32-byte bytes, got {type(public_key)}")

    if len(raw_bytes) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(raw_bytes)}")

    multicodec_pub = ED25519_MULTICODEC_PREFIX + raw_bytes
    return "did:key:z" + b58encode(multicodec_pub)


def did_key_to_public_key(did_key: str) -> ed25519.Ed25519PublicKey:
    """Decode a standard W3C did:key identifier into an Ed25519PublicKey offline [D].

    Dispatches zero network calls to external DID registries.
    """
    if not isinstance(did_key, str) or not did_key.startswith("did:key:z"):
        raise ValueError(f"Invalid did:key string format: '{did_key}'")

    multibase_str = did_key[len("did:key:z") :]
    decoded_bytes = b58decode(multibase_str)

    if len(decoded_bytes) < 34 or decoded_bytes[:2] != ED25519_MULTICODEC_PREFIX:
        raise ValueError("Invalid multicodec prefix for Ed25519 did:key")

    raw_pub_bytes = decoded_bytes[2:34]
    return ed25519.Ed25519PublicKey.from_public_bytes(raw_pub_bytes)


def format_rfc8785_float(val: float) -> str:
    """Formats an IEEE 754 double-precision float strictly adhering to RFC 8785 §3.2.2.3 (ECMAScript Number::toString).

    Rules:
    - NaN and Infinities are strictly disallowed in JSON (raise ValueError).
    - Signed zero (-0.0) must format as '0'.
    - Absolute value in range 1e-6 <= |val| < 1e21 formats in fixed decimal notation without unnecessary trailing zeros.
    - Absolute value < 1e-6 or >= 1e21 formats in exponential notation with lowercase 'e' and exponent without leading zero.
    """
    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"RFC 8785 forbids non-finite float values: {val}")
    if val == 0.0:
        return "0"

    s = repr(val)

    # Normalize scientific notation exponent (e.g., '1e-05' -> '1e-5', '1e+05' -> '1e+5')
    if "e" in s:
        base, exp = s.split("e")
        exp_sign = exp[0]
        exp_val = exp[1:].lstrip("0") or "0"
        s = f"{base}e{exp_sign}{exp_val}"

    # Handle corner-case ranges where Python emits scientific notation but ECMAScript mandates fixed:
    abs_val = abs(val)
    if 1e-6 <= abs_val < 1e-4 and "e" in s:
        s = f"{val:.10f}".rstrip("0").rstrip(".")

    return s


def _serialize_jcs(obj: Any) -> str:
    """Internal recursive serializer for RFC 8785 JSON Canonicalization Scheme."""
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, int):
        return str(obj)
    elif isinstance(obj, float):
        return format_rfc8785_float(obj)
    elif isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    elif isinstance(obj, (list, tuple)):
        items = [_serialize_jcs(item) for item in obj]
        return "[" + ",".join(items) + "]"
    elif isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=lambda k: str(k).encode("utf-8"))
        pairs = [
            json.dumps(str(k), ensure_ascii=False) + ":" + _serialize_jcs(obj[k])
            for k in sorted_keys
        ]
        return "{" + ",".join(pairs) + "}"
    elif hasattr(obj, "model_dump"):
        return _serialize_jcs(obj.model_dump(mode="json"))
    elif isinstance(obj, BaseModel):
        return _serialize_jcs(obj.dict())
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not RFC 8785 JCS serializable")


def canonicalize_json(data: Any) -> bytes:
    """Serializes arbitrary Python data structures to deterministic UTF-8 bytes adhering to RFC 8785 (JCS).

    - Lexicographical sorting of object keys by UTF-8 code point values.
    - Zero whitespace around delimiters (',' and ':').
    - IEEE 754 float formatting via format_rfc8785_float.
    - UTF-8 output without BOM.
    """
    return _serialize_jcs(data).encode("utf-8")


def hash_canonical_json(data: Any, algorithm: str = "sha256") -> str:
    """Compute cryptographic hash over RFC 8785 canonicalized JSON bytes."""
    canonical_bytes = canonicalize_json(data)
    h = hashlib.new(algorithm)
    h.update(canonical_bytes)
    return h.hexdigest()


def generate_ed25519_key_pair() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Generate a genuine cryptographically secure Ed25519 key pair."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def _b64_decode_tolerant(b64_str: str) -> bytes:
    """Safely decode standard or URL-safe base64 string with missing padding."""
    clean = b64_str.strip()
    pad_len = (-len(clean)) % 4
    padded = clean + ("=" * pad_len)
    try:
        return base64.urlsafe_b64decode(padded)
    except Exception:
        return base64.b64decode(padded)


def sign_canonical_bytes(
    canonical_bytes: bytes,
    private_key: ed25519.Ed25519PrivateKey,
) -> Tuple[str, str, str]:
    """Sign raw canonical bytes directly conforming to RFC 8032 PureEd25519 without double-hashing.

    Returns:
        Tuple[str, str, str]: (signature_urlsafe_b64, public_key_urlsafe_b64, fingerprint_sha256_hex)
    """
    signature_bytes = private_key.sign(canonical_bytes)

    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    signature_b64 = base64.urlsafe_b64encode(signature_bytes).decode("utf-8")
    public_key_b64 = base64.urlsafe_b64encode(pub_bytes).decode("utf-8")
    fingerprint = hashlib.sha256(pub_bytes).hexdigest()

    return signature_b64, public_key_b64, fingerprint


def verify_canonical_signature(
    canonical_bytes: bytes,
    signature_b64: str,
    public_key_b64: str,
) -> bool:
    """Verify an RFC 8032 PureEd25519 digital signature over raw canonical bytes."""
    try:
        pub_bytes = _b64_decode_tolerant(public_key_b64)
        sig_bytes = _b64_decode_tolerant(signature_b64)

        if len(pub_bytes) != 32:
            return False
        if len(sig_bytes) != 64:
            return False

        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, canonical_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def verify_report_signature(
    canonical_bytes: bytes,
    signature_b64: str,
    public_key_b64: str,
) -> bool:
    """Ergonomic backward-compatible alias for verify_canonical_signature."""
    return verify_canonical_signature(canonical_bytes, signature_b64, public_key_b64)


def sign_ed25519ph(
    canonical_bytes: bytes,
    private_key: ed25519.Ed25519PrivateKey,
    context: bytes = b"",
) -> Tuple[str, str, str]:
    """Support RFC 8032 §5.1 Ed25519ph pre-hashed signing when domain-separated hashing is explicitly requested."""
    hasher = hashlib.sha512()
    hasher.update(canonical_bytes)
    ph_bytes = hasher.digest()

    return sign_canonical_bytes(ph_bytes, private_key)


def sign_report_payload(
    payload: Dict[str, Any],
    private_key: ed25519.Ed25519PrivateKey,
) -> Dict[str, Any]:
    """Emit standard W3C Linked Data Proof envelope with pure cryptographic did:key resolution [D].

    Envelopes payload with an Ed25519Signature2020 proof block.
    """
    clean_payload = {k: v for k, v in payload.items() if k != "proof"}
    canonical_bytes = canonicalize_json(clean_payload)
    signature_bytes = private_key.sign(canonical_bytes)

    proof = {
        "type": "Ed25519Signature2020",
        "created": datetime.now(timezone.utc).isoformat(),
        "verificationMethod": public_key_to_did_key(private_key.public_key()),
        "proofPurpose": "assertionMethod",
        "proofValue": base64.urlsafe_b64encode(signature_bytes).decode("ascii"),
    }

    return {
        **clean_payload,
        "proof": proof,
    }


def verify_report_payload(signed_payload: Dict[str, Any]) -> bool:
    """Verify standard W3C Linked Data Proof envelope completely offline [D]."""
    if not isinstance(signed_payload, dict) or "proof" not in signed_payload:
        return False

    proof = signed_payload.get("proof")
    if not isinstance(proof, dict):
        return False

    did_key = proof.get("verificationMethod")
    proof_value = proof.get("proofValue")
    if not did_key or not proof_value:
        return False

    try:
        public_key = did_key_to_public_key(str(did_key))
        sig_bytes = _b64_decode_tolerant(str(proof_value))
        clean_payload = {k: v for k, v in signed_payload.items() if k != "proof"}
        canonical_bytes = canonicalize_json(clean_payload)
        public_key.verify(sig_bytes, canonical_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return False


__all__ = [
    "format_rfc8785_float",
    "canonicalize_json",
    "hash_canonical_json",
    "generate_ed25519_key_pair",
    "sign_canonical_bytes",
    "verify_canonical_signature",
    "verify_report_signature",
    "sign_ed25519ph",
    "public_key_to_did_key",
    "did_key_to_public_key",
    "sign_report_payload",
    "verify_report_payload",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_provenance.py ---
"""Authoritative W3C PROV-O Conformer Lineage & Semantic Provenance Graphs.

Complies strictly with:
- W3C PROV-O Linked Data Standard (prov:Entity, prov:Activity, prov:wasDerivedFrom)
- Tripartite Air-Gap Mandate (Offline local JSON-LD context catalog resolution)
- FAIR Principles I1, I3, and R1.2
- Method Matrix v4 §8B.4 & §9B (Quasi-Harmonic Thermodynamics Provenance)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from cochem_base.core.models import ThermodynamicsProvenance


def get_local_prov_context() -> Dict[str, Any]:
    """Retrieve bundled offline local W3C PROV-O JSON-LD context [D].

    Dispatches zero network calls to http://www.w3.org/ns/prov#, guaranteeing air-gapped execution.
    """
    ctx_path = Path(__file__).resolve().parent.parent / "schemas" / "contexts" / "prov_o_context.jsonld"
    if not ctx_path.exists():
        candidates = [
            Path(__file__).resolve().parent / "prov_o_context.jsonld",
            Path(__file__).resolve().parents[2] / "schemas" / "contexts" / "prov_o_context.jsonld",
        ]
        for cand in candidates:
            if cand.exists():
                ctx_path = cand
                break

    if not ctx_path.exists():
        raise FileNotFoundError(f"Offline local JSON-LD context not found at expected path: {ctx_path}")

    return json.loads(ctx_path.read_text(encoding="utf-8"))


class DAGNode(BaseModel):
    """Semantic Directed Acyclic Graph (DAG) node representing conformers or computational workflows."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    node_id: str = Field(..., description="Unique node identifier within the lineage graph")
    node_type: Literal["entity", "activity", "agent"] = Field(
        default="entity", description="PROV-O class classification"
    )
    activity_type: Optional[str] = Field(
        default=None, description="Specific activity type URI or curie (e.g. 'cochem:Optimization')"
    )
    parents: List[str] = Field(
        default_factory=list, description="Identifiers of ancestor nodes (prov:wasDerivedFrom)"
    )
    activity: Optional[str] = Field(
        default=None, description="Identifier of generating activity (prov:wasGeneratedBy)"
    )
    started_at_time: Optional[str] = Field(
        default=None, description="ISO 8601 UTC start timestamp"
    )
    ended_at_time: Optional[str] = Field(
        default=None, description="ISO 8601 UTC completion timestamp"
    )
    relative_energy_kcal_mol: Optional[float] = Field(
        default=None, description="Relative electronic energy in kcal/mol"
    )
    rotational_constants_mhz: Optional[List[float]] = Field(
        default=None, description="Principal rotational constants [A, B, C] in MHz"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary execution payload and thermodynamic provenance"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary execution or quantum chemistry metadata"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert DAGNode to standard dictionary representation."""
        return self.model_dump()

    def to_prov_jsonld(self, base_uri: str = "urn:cochem:conformer:") -> Dict[str, Any]:
        """Construct W3C PROV-O compliant JSON-LD document with offline context resolution [D].

        Args:
            base_uri: Uniform Resource Name prefix for node resolution.

        Returns:
            Dict[str, Any]: Validated JSON-LD semantic dictionary.
        """
        ctx_doc = get_local_prov_context()
        doc: Dict[str, Any] = {
            "@context": ctx_doc.get("@context", {}),
            "@id": f"{base_uri}{self.node_id}",
        }

        if self.node_type == "activity":
            types = ["prov:Activity"]
            if self.activity_type:
                types.append(self.activity_type)
            else:
                types.append("cochem:Optimization")
            doc["@type"] = types
        elif self.node_type == "agent":
            doc["@type"] = ["prov:Agent", "cochem:SoftwareAgent"]
        else:
            doc["@type"] = ["prov:Entity", "cochem:Conformer"]

        if self.parents:
            doc["prov:wasDerivedFrom"] = [{"@id": f"{base_uri}{parent_id}"} for parent_id in self.parents]

        if self.activity:
            doc["prov:wasGeneratedBy"] = {"@id": f"urn:cochem:activity:{self.activity}"}

        if self.started_at_time:
            doc["prov:startedAtTime"] = self.started_at_time
        if self.ended_at_time:
            doc["prov:endedAtTime"] = self.ended_at_time

        if self.relative_energy_kcal_mol is not None:
            doc["cochem:relativeEnergy"] = float(self.relative_energy_kcal_mol)

        if self.rotational_constants_mhz is not None:
            doc["cochem:rotationalConstants"] = [float(rc) for rc in self.rotational_constants_mhz]

        for k, v in self.metadata.items():
            doc[f"cochem:{k}"] = v

        return doc


def compute_boltzmann_weights(
    free_energies_kcal_mol: Sequence[float],
    temperature_k: float = 298.15,
    low_freq_cutoff_cm1: float = 100.0,
    damping_model: str = "grimme_quasi_rrho",
    pressure_atm: float = 1.0,
    dag_node: Optional[Any] = None,
) -> Tuple[List[float], ThermodynamicsProvenance]:
    """Computes normalized Boltzmann weights while recording thermodynamic provenance.

    Weights: w_i = exp(-Delta G_i / (R * T)) / sum(exp(-Delta G_j / (R * T)))
    Logs ThermodynamicsProvenance into dag_node.payload['thermodynamics_provenance'] if provided.
    """
    R_KCAL_MOL_K: float = 0.00198720425864083

    G = np.asarray(free_energies_kcal_mol, dtype=np.float64)
    if len(G) == 0:
        return [], ThermodynamicsProvenance(
            damping_model=damping_model,
            low_freq_cutoff_cm1=float(low_freq_cutoff_cm1),
            temperature_k=float(temperature_k),
            pressure_atm=float(pressure_atm),
            provenance_tag="[D]",
        )

    delta_G = G - np.min(G)
    beta = 1.0 / (R_KCAL_MOL_K * temperature_k)
    unnorm_weights = np.exp(-beta * delta_G)
    weights = (unnorm_weights / np.sum(unnorm_weights)).tolist()

    prov = ThermodynamicsProvenance(
        damping_model=damping_model,
        low_freq_cutoff_cm1=float(low_freq_cutoff_cm1),
        temperature_k=float(temperature_k),
        pressure_atm=float(pressure_atm),
        provenance_tag="[D]",
    )

    if dag_node is not None:
        if hasattr(dag_node, "payload") and isinstance(dag_node.payload, dict):
            dag_node.payload["thermodynamics_provenance"] = prov.model_dump(mode="json")
        elif hasattr(dag_node, "metadata") and isinstance(dag_node.metadata, dict):
            dag_node.metadata["thermodynamics_provenance"] = prov.model_dump(mode="json")

    return weights, prov


__all__ = [
    "DAGNode",
    "get_local_prov_context",
    "ThermodynamicsProvenance",
    "compute_boltzmann_weights",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\exceptions.py ---
"""Authoritative Core Domain Exceptions for CoChem-BASE.

Provides physical invariant exceptions for isotopic stability, empirical radii,
and domain perceptions adhering to Method Matrix v4 §6.10, §8C, and §20.
Includes machine-actionable error codes for automated ETL triage.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class CoChemError(Exception):
    """Base error class for all CoChem operations with machine-actionable error codes."""

    def __init__(
        self,
        message: str,
        error_code: str = "COCHEM_E_GENERIC",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(f"[{error_code}] {message}")
        self.message: str = message
        self.error_code: str = error_code
        self.details: Dict[str, Any] = details if details is not None else {}


class CoordinateShapeError(CoChemError):
    """Raised when molecular coordinate arrays violate dimensionality constraints (e.g. not N x 3)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_INVALID_COORD_SHAPE", details=details)


class AirGapBoundaryError(CoChemError):
    """Raised when an operation attempts to write to a read-only or out-of-tier filesystem boundary."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_AIRGAP_BREACH", details=details)


class SchemaMigrationError(CoChemError):
    """Raised when deserializing a payload lacking a valid migration path to current schema_version."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_SCHEMA_MIGRATION_FAILED", details=details)


class PESStorageError(CoChemError):
    """Raised when HDF5 SWMR store operations fail or encounter lock contention."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_PES_STORAGE_FAILURE", details=details)


class ProcessReaperError(CoChemError):
    """Raised when process termination or resource sampling fails unexpectedly."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_PROCESS_REAPER_FAILURE", details=details)


class SubprocessBrokerError(CoChemError):
    """Raised when isolated subprocess execution fails pre-flight or runtime contracts."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_SUBPROCESS_BROKER_FAILURE", details=details)


class ThermodynamicsParameterError(CoChemError):
    """Raised when required quasi-harmonic parameters are missing from thermodynamic calculations."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_THERMO_PARAM_MISSING", details=details)


class IsotopeMassResolutionError(CoChemError):
    """Raised when requested isotope cannot be resolved to physical mass."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_ISOTOPE_NOT_FOUND", details=details)


class IsotopeStabilityError(CoChemError, ValueError):
    """Raised when a requested isotope cannot be physically resolved to an isotopic nuclear mass."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_ISOTOPE_STABILITY", details=details)


class RadiusNotFoundError(CoChemError, KeyError):
    """Raised when empirical covalent or van der Waals radius is unavailable for an element."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_RADIUS_NOT_FOUND", details=details)


__all__ = [
    "CoChemError",
    "CoordinateShapeError",
    "AirGapBoundaryError",
    "SchemaMigrationError",
    "PESStorageError",
    "ProcessReaperError",
    "SubprocessBrokerError",
    "ThermodynamicsParameterError",
    "IsotopeMassResolutionError",
    "IsotopeStabilityError",
    "RadiusNotFoundError",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\models.py ---
"""Authoritative Core Data Models & MolSSI QCSchema v1 Envelopes.

Defines QCResultsRecord (AtomicResult), MolecularTopology, PESPointRecord, and CalculationJobPayload
with explicit spatial coordinate envelopes, CODATA 2022 constants, deterministic UUIDv5 content hashing,
machine-readable SPDX licensing, and schema version migration contracts adhering to FAIR F2, I1, and R1.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Callable, ClassVar, Dict, List, Literal, Optional, Tuple, Type, TypeVar, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cochem_base.core.cochem_crypto import canonicalize_json
from cochem_base.core.exceptions import CoordinateShapeError, SchemaMigrationError
from cochem_base.core.glossary import CalculationFidelity
from cochem_base.core.licensing import validate_spdx_license

# Authoritative CODATA 2022 conversion factors
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_BOHR: float = 1.0 / BOHR_TO_ANGSTROM

# Authoritative CoChem Namespace UUID for deterministic UUIDv5 hashing
NAMESPACE_COCHEM: uuid.UUID = uuid.UUID("a6c4f69a-2d4e-4e68-912f-6e2101e4a682")

# Global schema version constant (FAIR F2, I1, R1)
CURRENT_CORE_SCHEMA_VERSION: int = 1

T = TypeVar("T", bound=BaseModel)
MigrationCallable = Callable[[Dict[str, Any]], Dict[str, Any]]
_MIGRATION_REGISTRY: Dict[Tuple[str, int], MigrationCallable] = {}


def register_migration(model_name: str, from_version: int) -> Callable[[MigrationCallable], MigrationCallable]:
    """Decorator registering a transformation function from a specific schema version to from_version + 1."""

    def decorator(func: MigrationCallable) -> MigrationCallable:
        _MIGRATION_REGISTRY[(model_name, from_version)] = func
        return func

    return decorator


def migrate_payload(payload: Dict[str, Any], target_model: Type[BaseModel]) -> Dict[str, Any]:
    """Migrates a raw dictionary payload sequentially up to target_model's current schema_version."""
    model_name = target_model.__name__
    current_version = payload.get("schema_version", 0)
    target_version = getattr(target_model, "CURRENT_VERSION", CURRENT_CORE_SCHEMA_VERSION)

    data = dict(payload)
    while current_version < target_version:
        key = (model_name, current_version)
        if key not in _MIGRATION_REGISTRY:
            raise SchemaMigrationError(
                f"No migration path registered for {model_name} from version {current_version} to {current_version + 1}.",
                details={"model": model_name, "from_version": current_version, "target_version": target_version},
            )
        data = _MIGRATION_REGISTRY[key](data)
        current_version = data.get("schema_version", current_version + 1)

    return data


class ThermodynamicsProvenance(BaseModel):
    """Provenance metadata for quasi-harmonic thermodynamic corrections and Boltzmann weighting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    damping_model: str = Field(
        default="grimme_quasi_rrho",
        description="Vibrational entropy damping model (e.g. grimme_quasi_rrho, truhlar_quasi_harmonic, harmonic).",
    )
    low_freq_cutoff_cm1: float = Field(
        default=100.0,
        description="Low-frequency cutoff/interpolation threshold in wavenumbers (cm^-1).",
    )
    temperature_k: float = Field(
        default=298.15,
        description="Thermodynamic temperature in Kelvin.",
    )
    pressure_atm: float = Field(
        default=1.0,
        description="Standard state pressure in atmospheres.",
    )
    rotor_cutoff_cm1: Optional[float] = Field(
        default=None,
        description="Free-rotor transition threshold if using Head-Gordon or multi-cutoff damping.",
    )
    provenance_tag: str = Field(
        default="[D]",
        description="Method Matrix provenance marker ([M] measured, [D] derived, [E] estimated).",
    )

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)


class QCResultsRecord(BaseModel):
    """MolSSI QCSchema v1 compliant AtomicResult record with backward-compatible accessors."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True, validate_assignment=True)

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_name: Literal["qcschema_output"] = "qcschema_output"
    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    molecule: Dict[str, Any] = Field(default_factory=dict, description="Nested molecular topology specifications")
    driver: Literal["energy", "gradient", "hessian", "properties"] = "energy"
    model: Dict[str, Any] = Field(default_factory=lambda: {"method": "unknown", "basis": None})
    return_result: Union[float, List[float], List[List[float]]] = 0.0
    properties: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: Optional[Dict[str, Any]] = None
    license: str = Field(
        default="CC-BY-4.0",
        description="SPDX license identifier governing data reuse rights (FAIR R1.1)",
    )

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

    @field_validator("license")
    @classmethod
    def validate_license_spdx(cls, v: str) -> str:
        return validate_spdx_license(v)

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_validate_qcschema(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Convenience conversion for top-level symbols and geometry
        if "molecule" not in data or not data["molecule"]:
            mol: Dict[str, Any] = {}
            if "symbols" in data:
                mol["symbols"] = list(data.pop("symbols"))
            if "geometry" in data:
                geom = data.pop("geometry")
                if isinstance(geom, np.ndarray):
                    geom = geom.flatten().tolist()
                elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
                    flat_geom = []
                    for pt in geom:
                        flat_geom.extend(pt)
                    geom = flat_geom
                mol["geometry"] = geom
            if "molecular_charge" in data:
                mol["molecular_charge"] = data.pop("molecular_charge")
            if "molecular_multiplicity" in data:
                mol["molecular_multiplicity"] = data.pop("molecular_multiplicity")
            data["molecule"] = mol
        else:
            mol = dict(data["molecule"])
            if "geometry" in mol:
                geom = mol["geometry"]
                if isinstance(geom, np.ndarray):
                    geom = geom.flatten().tolist()
                elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
                    flat_geom = []
                    for pt in geom:
                        flat_geom.extend(pt)
                    geom = flat_geom
                mol["geometry"] = geom
            data["molecule"] = mol

        # Format return_result if given as NumPy array
        if "return_result" in data:
            res = data["return_result"]
            if isinstance(res, np.ndarray):
                if res.ndim == 1:
                    data["return_result"] = res.tolist()
                elif res.ndim == 0:
                    data["return_result"] = float(res)
                else:
                    data["return_result"] = res.tolist()

        # Handle backward-compatible energy_hartree kwarg
        if "energy_hartree" in data and "return_result" not in data:
            e = float(data.pop("energy_hartree"))
            data["return_result"] = e
            if "properties" not in data:
                data["properties"] = {}
            data["properties"]["return_energy"] = e

        return data

    @property
    def energy_hartree(self) -> Optional[float]:
        """Backward-compatible property returning total electronic energy in Hartree."""
        if "return_energy" in self.properties:
            return float(self.properties["return_energy"])
        if self.driver == "energy" and isinstance(self.return_result, (int, float)):
            return float(self.return_result)
        return None

    @property
    def gradient_bohr(self) -> Optional[List[float]]:
        """Backward-compatible property returning Cartesian nuclear gradient in Hartree/Bohr."""
        if self.driver == "gradient":
            if isinstance(self.return_result, list):
                if self.return_result and isinstance(self.return_result[0], list):
                    flat_grad: List[float] = []
                    for row in self.return_result:  # type: ignore[union-attr]
                        flat_grad.extend([float(x) for x in row])
                    return flat_grad
                return [float(x) for x in self.return_result]  # type: ignore[union-attr]
        if "return_gradient" in self.properties:
            grad = self.properties["return_gradient"]
            if isinstance(grad, list):
                return [float(x) for x in grad]
        return None

    @property
    def hessian(self) -> Optional[Union[List[float], List[List[float]]]]:
        """Backward-compatible property returning Cartesian nuclear Hessian."""
        if self.driver == "hessian":
            if isinstance(self.return_result, list):
                return self.return_result
        if "return_hessian" in self.properties:
            h = self.properties["return_hessian"]
            if isinstance(h, list):
                return h
        return None


# MolSSI QCSchema Aliases
AtomicResult = QCResultsRecord
QCSchemaOutput = QCResultsRecord


class MolecularTopology(BaseModel):
    """Molecular spatial coordinates standardized to flat 1D arrays or 2D coordinate lists with explicit unit tagging."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    symbols: List[str] = Field(..., description="Ordered IUPAC elemental symbols")
    coordinates: Optional[List[List[float]]] = Field(default=None, description="2D Cartesian coordinate list (N x 3)")
    geometry: Optional[List[float]] = Field(default=None, description="Flat 1D atomic Cartesian coordinates (size 3*N)")
    units: Literal["bohr", "angstrom"] = Field(default="bohr", description="Physical coordinate unit")
    molecular_charge: int = Field(default=0, description="Net molecular charge")
    spin_multiplicity: int = Field(default=1, description="Spin multiplicity (2S + 1)")

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

    @field_validator("coordinates", mode="after")
    @classmethod
    def validate_coordinates_shape(cls, v: Optional[List[List[float]]]) -> Optional[List[List[float]]]:
        if v is None:
            return v
        for idx, atom_coord in enumerate(v):
            if len(atom_coord) != 3:
                raise CoordinateShapeError(
                    f"Atom index {idx} has dimensionality {len(atom_coord)}; expected exactly 3 (x, y, z).",
                    details={"atom_index": idx, "actual_len": len(atom_coord), "expected_len": 3},
                )
        return v

    @model_validator(mode="before")
    @classmethod
    def _validate_and_flatten_coords(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        symbols = data.get("symbols", [])
        coords = data.get("coordinates")
        geom = data.get("geometry")

        if coords is not None:
            if isinstance(coords, np.ndarray):
                coords = coords.tolist()
                data["coordinates"] = coords
            # Only synthesize geometry if all coordinate rows have valid length 3
            if geom is None and isinstance(coords, list):
                if all(isinstance(c, (list, tuple)) and len(c) == 3 for c in coords):
                    flat = []
                    for pt in coords:
                        flat.extend([float(c) for c in pt])
                    data["geometry"] = flat
        elif geom is not None:
            if isinstance(geom, np.ndarray):
                geom = geom.flatten().tolist()
            elif isinstance(geom, list) and geom and isinstance(geom[0], (list, tuple)):
                flat = []
                for pt in geom:
                    flat.extend([float(c) for c in pt])
                geom = flat
            elif isinstance(geom, list):
                geom = [float(c) for c in geom]
            data["geometry"] = geom

            n_atoms = len(symbols)
            if n_atoms > 0 and len(geom) != 3 * n_atoms:
                raise CoordinateShapeError(
                    f"Geometry coordinate dimension mismatch: expected {3 * n_atoms} components for {n_atoms} atoms, got {len(geom)}",
                    details={"actual_len": len(geom), "expected_len": 3 * n_atoms},
                )
            if "coordinates" not in data and len(geom) % 3 == 0:
                data["coordinates"] = [
                    geom[3 * i : 3 * i + 3] for i in range(len(geom) // 3)
                ]

        return data

    def to_angstrom(self) -> MolecularTopology:
        """Convert coordinates to Angstroms using authoritative CODATA 2022 constant."""
        if self.units == "angstrom":
            return self
        converted_geom = (
            [float(c * BOHR_TO_ANGSTROM) for c in self.geometry]
            if self.geometry is not None
            else None
        )
        converted_coords = (
            [[float(c * BOHR_TO_ANGSTROM) for c in pt] for pt in self.coordinates]
            if self.coordinates is not None
            else None
        )
        return MolecularTopology(
            schema_version=self.schema_version,
            symbols=list(self.symbols),
            geometry=converted_geom,
            coordinates=converted_coords,
            units="angstrom",
            molecular_charge=self.molecular_charge,
            spin_multiplicity=self.spin_multiplicity,
        )

    def to_bohr(self) -> MolecularTopology:
        """Convert coordinates to Bohr using authoritative CODATA 2022 constant."""
        if self.units == "bohr":
            return self
        converted_geom = (
            [float(c * ANGSTROM_TO_BOHR) for c in self.geometry]
            if self.geometry is not None
            else None
        )
        converted_coords = (
            [[float(c * ANGSTROM_TO_BOHR) for c in pt] for pt in self.coordinates]
            if self.coordinates is not None
            else None
        )
        return MolecularTopology(
            schema_version=self.schema_version,
            symbols=list(self.symbols),
            geometry=converted_geom,
            coordinates=converted_coords,
            units="bohr",
            molecular_charge=self.molecular_charge,
            spin_multiplicity=self.spin_multiplicity,
        )


class PESPointRecord(BaseModel):
    """Point record representing a single potential energy surface evaluation with deterministic UUIDv5 [D]."""

    model_config = ConfigDict(extra="allow", validate_assignment=True, arbitrary_types_allowed=True)

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    point_id: str = Field(default="", description="Deterministic UUIDv5 content-addressable point identifier")
    method_id: str = Field(default="unknown", description="Registered method identifier")
    coordinates: List[float] = Field(default_factory=list, description="Flat 1D atomic coordinates (size 3*N)")
    symbols: List[str] = Field(default_factory=list, description="Ordered IUPAC elemental symbols")
    method: str = Field(default="unknown", description="Electronic structure method")
    basis: Optional[str] = Field(default=None, description="Primary basis set")
    energy: float = Field(default=0.0, description="Electronic energy in Hartrees")
    gradient: Optional[List[float]] = Field(None, description="Flat 1D gradient in Hartree/Bohr (size 3*N)")
    units: Literal["bohr", "angstrom"] = Field(default="bohr", description="Physical unit of spatial coordinates")
    converged: bool = Field(default=True, description="Whether SCF and geometry optimization converged")
    wall_s: float = Field(default=0.0, ge=0.0, description="Calculation wall clock time in seconds")
    provenance: Any = Field(default_factory=dict, description="Calculation provenance record")
    license: str = Field(default="CC-BY-4.0", description="SPDX license identifier")

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

    @classmethod
    def generate_point_id(
        cls,
        geometry: List[float],
        symbols: List[str],
        method: str,
        basis: Optional[str] = None,
    ) -> str:
        """Deterministically generate UUIDv5 point ID from canonical RFC 8785 JSON representation [D]."""
        normalized_payload = {
            "symbols": [str(s).upper() for s in symbols],
            "geometry": [round(float(c), 8) for c in geometry],
            "method": str(method).strip().lower(),
            "basis": (basis or "").strip().lower(),
        }
        canonical_bytes = canonicalize_json(normalized_payload)
        return str(uuid.uuid5(NAMESPACE_COCHEM, canonical_bytes.decode("utf-8")))

    @field_validator("license")
    @classmethod
    def validate_license_spdx(cls, v: str) -> str:
        return validate_spdx_license(v)

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coords_array(cls, v: Any) -> List[float]:
        if isinstance(v, np.ndarray):
            return [float(x) for x in v.flatten()]
        if isinstance(v, (list, tuple)):
            flat: List[float] = []
            for item in v:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend([float(x) for x in item])
                else:
                    flat.append(float(item))
            return flat
        raise ValueError(f"Invalid coordinate format: {type(v)}")

    @field_validator("gradient", mode="before")
    @classmethod
    def validate_grad_array(cls, v: Any) -> Optional[List[float]]:
        if v is None:
            return None
        if isinstance(v, np.ndarray):
            return [float(x) for x in v.flatten()]
        if isinstance(v, (list, tuple)):
            flat: List[float] = []
            for item in v:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend([float(x) for x in item])
                else:
                    flat.append(float(item))
            return flat
        raise ValueError(f"Invalid gradient format: {type(v)}")

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_default_point_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if "coordinates" not in data and "geometry" in data:
            data["coordinates"] = data["geometry"]
        elif "coordinates" in data and "geometry" not in data:
            data["geometry"] = data["coordinates"]

        coords = data.get("coordinates") or []
        if isinstance(coords, np.ndarray):
            coords = coords.flatten().tolist()
            data["coordinates"] = coords
        elif isinstance(coords, list) and coords and isinstance(coords[0], (list, tuple)):
            flat = []
            for item in coords:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend([float(x) for x in item])
                else:
                    flat.append(float(item))
            coords = flat
            data["coordinates"] = coords

        if not data.get("point_id"):
            syms = data.get("symbols") or []
            meth = data.get("method") or data.get("method_id") or "unknown"
            bas = data.get("basis") or ""
            data["point_id"] = cls.generate_point_id(
                geometry=coords,
                symbols=syms,
                method=meth,
                basis=bas,
            )

        if not data.get("method_id") and data.get("method"):
            data["method_id"] = data["method"]

        return data

    def to_angstrom(self) -> PESPointRecord:
        """Convert coordinates and gradients to Angstroms using authoritative CODATA 2022 constants."""
        if self.units == "angstrom":
            return self
        converted_coords = [float(c * BOHR_TO_ANGSTROM) for c in self.coordinates]
        converted_grad = (
            [float(g * ANGSTROM_TO_BOHR) for g in self.gradient]
            if self.gradient is not None
            else None
        )
        return PESPointRecord(
            schema_version=self.schema_version,
            point_id=self.point_id,
            method_id=self.method_id,
            coordinates=converted_coords,
            symbols=list(self.symbols),
            method=self.method,
            basis=self.basis,
            energy=self.energy,
            gradient=converted_grad,
            units="angstrom",
            converged=self.converged,
            wall_s=self.wall_s,
            provenance=copy.deepcopy(self.provenance),
            license=self.license,
        )

    def to_bohr(self) -> PESPointRecord:
        """Convert coordinates and gradients to Bohr using authoritative CODATA 2022 constants."""
        if self.units == "bohr":
            return self
        converted_coords = [float(c * ANGSTROM_TO_BOHR) for c in self.coordinates]
        converted_grad = (
            [float(g * BOHR_TO_ANGSTROM) for g in self.gradient]
            if self.gradient is not None
            else None
        )
        return PESPointRecord(
            schema_version=self.schema_version,
            point_id=self.point_id,
            method_id=self.method_id,
            coordinates=converted_coords,
            symbols=list(self.symbols),
            method=self.method,
            basis=self.basis,
            energy=self.energy,
            gradient=converted_grad,
            units="bohr",
            converged=self.converged,
            wall_s=self.wall_s,
            provenance=copy.deepcopy(self.provenance),
            license=self.license,
        )


class CalculationJobPayload(BaseModel):
    """Calculation job specification supporting Method Matrix v4 fidelity tiers [D]."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    CURRENT_VERSION: ClassVar[int] = CURRENT_CORE_SCHEMA_VERSION

    schema_version: int = Field(
        default=CURRENT_CORE_SCHEMA_VERSION,
        description="Semantic schema version for archival data deserialization and migration contracts.",
    )
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique job identifier")
    molecule: Dict[str, Any] = Field(default_factory=dict, description="Target molecular topology specifications")
    driver: Literal["energy", "gradient", "hessian", "properties"] = "energy"
    fidelity: Union[CalculationFidelity, str] = Field(
        default=CalculationFidelity.R_DFT,
        description="Canonical fidelity tier or custom specification",
    )
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Calculation keywords")
    license: str = Field(default="CC-BY-4.0", description="SPDX license identifier")

    @classmethod
    def from_archival_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Parses a dictionary, executing automated migrations if schema_version is older than current."""
        migrated = migrate_payload(data, cls)
        return cls.model_validate(migrated)

    @field_validator("fidelity", mode="before")
    @classmethod
    def validate_fidelity(cls, v: Any) -> Union[CalculationFidelity, str]:
        if isinstance(v, CalculationFidelity):
            return v
        if isinstance(v, str):
            clean = v.strip()
            for member in CalculationFidelity:
                if member.value.lower() == clean.lower() or member.name.lower() == clean.lower():
                    return member
            return clean
        raise ValueError(f"Invalid fidelity specification: {v}")

    @field_validator("license")
    @classmethod
    def validate_license_spdx(cls, v: str) -> str:
        return validate_spdx_license(v)


__all__ = [
    "BOHR_TO_ANGSTROM",
    "ANGSTROM_TO_BOHR",
    "NAMESPACE_COCHEM",
    "CURRENT_CORE_SCHEMA_VERSION",
    "register_migration",
    "migrate_payload",
    "ThermodynamicsProvenance",
    "QCResultsRecord",
    "AtomicResult",
    "QCSchemaOutput",
    "MolecularTopology",
    "PESPointRecord",
    "CalculationJobPayload",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_core_pes_store.py ---
#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_pes_store.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8C - QCSchema-Compliant Chunked HDF5 PES Store,
SWMR/Archival Storage Bifurcation, and Isotopologue Force Field Recycling.

Mandated by:
- SRS Doc 1 (Topology 1.0 §2)
- SRS Doc 2 Part 1 (§2.7)
- Method Matrix v4 §8C (HDF5 PES Store), §8B.4 (Canonical State Reuse & Arrow 7),
  §6.10 (Isotopologue Shortcut), §3-§5 (Rotational & Anharmonic Observables), §8A (Concurrency)
- CoChem Anti-Spoofing Protocol v2
- CoChem Mendeleev Library Mandate

Architectural Overview:
1. QCSchema-Compliant Chunked HDF5 PES Store (PESStore):
   - Structured HDF5 hierarchy (/meta, /methods, /points, /grids, /hessians, /isotopologues, /checkpoints).
   - Resizable chunked datasets with CHUNK_POINTS=512 (~120 KiB for 10-atom systems, in 10 KiB-1 MiB envelope).
   - Lossless gzip (compression_opts=4) + byte shuffle filter on numeric datasets.
   - Fletcher32 per-chunk error-detecting checksum on critical energy and coordinate arrays.
   - STRICT BAN on lossy scaleoffset filter to preserve micro-Hartree energy accuracy and avoid artificial frequencies.
   - Provenance tracking with QCSchema field names, JSON serialization, and cryptographic HMAC-SHA256 signatures.

2. SWMR / Archival Storage Bifurcation (BifurcatedPESStore):
   - Active Runtime Store (runtime_active.h5): Low-latency, uncompressed or fast chunking for live IPC streaming,
     steering, and concurrent reader queries with POSIX/Windows byte-range file locking.
   - Archival QCSchema Store (archive_pes.h5 / campaign.h5): Standard HDF5 mode with full lossless compression,
     checksum validation, and formal QCSchema v1 archival schema validation.
   - Atomic promotion from active runtime store to compressed archival store.
   - Parallel shard merger (merge_pes_shards) for multi-worker parallel grid evaluations.

3. Isotopologue Force Field Recycling Engine (Method Matrix Arrow 7, §8B.4, §6.10):
   - Dynamic atomic and isotopic mass retrieval using the `mendeleev` library (strictly ZERO hardcoded mass constants).
   - Mass-weighting and normal mode diagonalization of Cartesian Hessians: H_mw[i, j] = H[i, j] / sqrt(m_i * m_j).
   - Harmonic vibrational frequencies in cm^-1 (preserving sign for imaginary saddle-point modes).
   - Moment of inertia tensor (Ia <= Ib <= Ic in u * A^2), rotational constants (A >= B >= C in MHz),
     planar moments (Paa, Pbb, Pcc in u * A^2), inertial defect (Delta = Ic - Ia - Ib in u * A^2),
     and Ray's asymmetry parameter (kappa).
   - Zero electronic structure cost evaluation of arbitrary isotopologue suites (13C, 18O, D, 15N) from a single Hessian.

4. Idempotent Active-Learning & DVR Integration:
   - todo(method_id, wanted_ids): Identifies missing or unconverged points on high-dimensional grids for restarts.
   - dataset(method_id, converged_only): Extracts aligned coordinates and energies as NumPy arrays.
   - delta_pairs(low_method, high_method): Generates aligned (X, Delta_E) pairs for Delta-learning MLFF training.
   - dvr_grid(method_id, grid_id): Reshapes potential energies onto product grids for DVR solvers, marking holes with NaN.
"""

from __future__ import annotations

import argparse
import atexit
import copy
import hashlib
import hmac
import json
import logging
import math
import os
import platform
import shutil
import socket
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

import h5py
import numpy as np
from filelock import FileLock, Timeout
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from cochem_base.config_loader import (
    get_artifact_dir,
    get_runtime_dir,
    get_state_file_path,
    resolve_mapped_path,
)
from cochem_base.exceptions import (
    CoChemError,
    HDF5LockTimeoutError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
    QCSchemaValidationError,
    SingularityError,
)
from cochem_base.core.ipc.serializer import validate_airgap_write_path
from cochem_base.core.licensing import validate_spdx_license
from cochem_base.core.models import NAMESPACE_COCHEM, PESPointRecord


def get_node_local_scratch_dir() -> Path:
    """Resolve node-local ephemeral scratch directory adhering to HPC Distributed Lock Prohibition [D]."""
    scratch = os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or (Path.home() / ".cochem" / "scratch")
    p = Path(scratch).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-PESStore")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [cochem_core_pes_store]: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Physical Constants & Convergence Standards (Method Matrix §4.4, §5, §8B)
# ---------------------------------------------------------------------------
PLANCK_CONSTANT_J_S = 6.62607015e-34       # J * s (CODATA exact)
SPEED_OF_LIGHT_CM_S = 2.99792458e10       # cm / s (CODATA exact)
SPEED_OF_LIGHT_M_S = 2.99792458e8         # m / s (CODATA exact)
ATOMIC_MASS_UNIT_KG = 1.66053906660e-27   # kg / u
ANGSTROM_TO_METER = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM = 0.529177210903         # Angstrom / Bohr
ANGSTROM_TO_BOHR = 1.0 / BOHR_TO_ANGSTROM  # Bohr / Angstrom
BOHR_TO_METER = 0.529177210903e-10        # m / Bohr
HARTREE_TO_JOULE = 4.3597447222071e-18    # J / Hartree
HARTREE_TO_EV = 27.211386245988           # eV / Hartree
HARTREE_TO_CM_INV = 219474.63136320       # cm^-1 / Hartree
ROTATIONAL_INERTIA_CONVERSION = 505379.0084350172  # MHz * u * Angstrom^2

# Factor converting Inertia (u * Angstrom^2) to Rotational Constant (MHz):
# B = h / (8 * pi^2 * I) * 1e-6 (Hz -> MHz)
INERTIA_TO_MHZ_FACTOR = (
    PLANCK_CONSTANT_J_S
    / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_KG * (ANGSTROM_TO_METER ** 2))
) * 1.0e-6  # ~505379.0091414361 MHz * u * Angstrom^2

# Factor converting Hessian eigenvalue (Hartree / (Bohr^2 * u)) to wavenumber (cm^-1):
# f_lambda = HARTREE_TO_JOULE / (BOHR_TO_METER^2 * ATOMIC_MASS_UNIT_KG)
# f_cm1 = 1 / (2 * pi * c_cm_s)
HESSIAN_EIG_TO_CM_INV_FACTOR = (
    math.sqrt(HARTREE_TO_JOULE / ((BOHR_TO_METER ** 2) * ATOMIC_MASS_UNIT_KG))
    / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
)  # ~5140.487143715827 cm^-1

# HDF5 Storage Specifications (Method Matrix §8C)
CHUNK_POINTS = 512
VLEN_STR = h5py.string_dtype(encoding="utf-8")
DEFAULT_LOCK_TIMEOUT_S = 30.0


# =============================================================================
# 1. PYDANTIC V2 DATA MODELS & SCHEMAS
# =============================================================================

class StorageMode(str, Enum):
    """Storage architecture operating mode classification."""
    BIFURCATED = "BIFURCATED"
    ARCHIVAL_ONLY = "ARCHIVAL_ONLY"
    RUNTIME_SWMR = "RUNTIME_SWMR"


class DriverType(str, Enum):
    """QCSchema calculation driver type."""
    ENERGY = "energy"
    GRADIENT = "gradient"
    HESSIAN = "hessian"
    PROPERTIES = "properties"


class QCSchemaProvenance(BaseModel):
    """QCSchema v1 compliant calculation provenance metadata with asymmetric Ed25519 signatures."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    creator: str = Field(default="ORCA", description="Name of quantum chemistry package or MLFF engine")
    version: str = Field(default="6.1", description="Software version identifier")
    routine: str = Field(default="sp", description="Calculation routine (sp, opt, freq, vpt2, scan)")
    host: str = Field(default_factory=socket.gethostname, description="Hostname where calculation executed")
    platform: str = Field(default_factory=platform.platform, description="OS platform string")
    utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 UTC timestamp",
    )
    signature: Optional[str] = Field(
        default=None, description="URL-safe base64 encoded Ed25519 digital signature"
    )
    public_key: Optional[str] = Field(
        default=None, description="URL-safe base64 encoded Ed25519 public key"
    )
    fingerprint: Optional[str] = Field(
        default=None, description="SHA-256 fingerprint of public key"
    )
    signature_algorithm: str = Field(
        default="PureEd25519", description="Cryptographic signing standard"
    )
    license: str = Field(
        default="CC-BY-4.0", description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
    )

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        return validate_spdx_license(v)

    def canonical_bytes(self) -> bytes:
        """Construct RFC 8785 canonical bytes for core provenance fields."""
        from cochem_base.core.cochem_crypto import canonicalize_json
        payload = {
            "creator": self.creator,
            "version": self.version,
            "routine": self.routine,
            "host": self.host,
            "platform": self.platform,
            "utc": self.utc,
            "license": self.license,
        }
        return canonicalize_json(payload)

    def sign(self, private_key: Any) -> str:
        """Sign provenance metadata with PureEd25519 and populate signature/public_key/fingerprint."""
        from cochem_base.core.cochem_crypto import sign_canonical_bytes
        c_bytes = self.canonical_bytes()
        sig, pub, fp = sign_canonical_bytes(c_bytes, private_key)
        self.signature = sig
        self.public_key = pub
        self.fingerprint = fp
        return sig

    def verify(self) -> bool:
        """Verify PureEd25519 digital signature against embedded public key."""
        if not self.signature or not self.public_key:
            return False
        from cochem_base.core.cochem_crypto import verify_canonical_signature
        c_bytes = self.canonical_bytes()
        return verify_canonical_signature(c_bytes, self.signature, self.public_key)


class QCSchemaMethodRecord(BaseModel):
    """QCSchema method attributes registered in HDF5 /methods/<method_id>."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    method: str = Field(..., description="Electronic structure method (e.g. DLPNO-CCSD(T1), wB97M-V, MP2)")
    basis: str = Field(..., description="Primary orbital basis set (e.g. def2-TZVPP, cc-pVDZ-F12)")
    aux_basis: Optional[str] = Field(None, description="Auxiliary density fitting or CABS basis set")
    program: str = Field(default="ORCA", description="Quantum chemistry package (ORCA, MPQC, CFOUR, PySCF, MACE)")
    program_version: str = Field(default="6.1", description="Software version string")
    driver: DriverType = Field(default=DriverType.ENERGY, description="Calculation driver")
    frozen_core: bool = Field(default=True, description="Whether frozen core approximation was enabled")
    counterpoise: str = Field(default="none", description="Counterpoise status: 'none', 'half', or 'full'")
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of calculation keywords and tolerances")
    license: str = Field(
        default="CC-BY-4.0", description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
    )
    registered_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 registration timestamp",
    )

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        return validate_spdx_license(v)


class PESGridDefinition(BaseModel):
    """Multidimensional grid definition for potential energy surfaces."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    grid_id: str = Field(..., description="Unique identifier for the grid (e.g. 'grid_2d_r_theta')")
    axes: Dict[str, List[float]] = Field(..., description="Mapping of axis names to 1D coordinate arrays")
    axis_order: List[str] = Field(..., description="Ordered list of axis names")
    shape: List[int] = Field(..., description="Grid dimension shape [dim_0, dim_1, ...]")
    grid_type: str = Field(default="cartesian", description="Grid coordinate type ('cartesian', 'spherical', 'internal')")


class HessianRecord(BaseModel):
    """Cartesian Hessian record stored under /hessians/<label>."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)

    label: str = Field(..., description="Unique label for the Hessian (e.g. 'opt_wb97mv_qz', 'parent_dimer')")
    level: str = Field(..., description="Level of theory (e.g. 'wB97M-V/def2-QZVPP')")
    geometry_ref: str = Field(..., description="Reference geometry identifier or filename")
    cartesian_hessian: Union[List[List[float]], np.ndarray] = Field(..., description="3N x 3N Cartesian Hessian matrix in Hartree/Bohr^2")
    units: str = Field(default="Hartree/Bohr^2", description="Units of the Hessian tensor")
    mass_weighted: bool = Field(default=False, description="Whether Hessian is already mass-weighted")
    frequencies_cm_inv: Optional[List[float]] = Field(None, description="Calculated harmonic vibrational frequencies")
    created_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 creation timestamp",
    )


class IsotopologueResult(BaseModel):
    """Complete rotational, vibrational, and inertial result for an isotopologue."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    iso_label: str = Field(..., description="Isotopologue label (e.g. 'parent', '13C_1', 'D_dimer', '18O_2')")
    parent_label: str = Field(..., description="Reference parent Hessian label from /hessians/<label>")
    substituted_mass_numbers: List[Optional[int]] = Field(
        ..., description="Substituted mass number for each atom (None = standard elemental weight)"
    )
    atomic_masses_amu: List[float] = Field(
        ..., description="Dynamic Mendeleev atomic masses in unified atomic mass units (u)"
    )
    harmonic_frequencies_cm_inv: List[float] = Field(
        ..., description="All 3N harmonic frequencies in cm^-1 (negative for imaginary modes)"
    )
    vibrational_frequencies_cm_inv: List[float] = Field(
        ..., description="Genuine vibrational frequencies in cm^-1 excluding 5/6 external translations/rotations"
    )
    lowest_harmonic_mode_cm_inv: float = Field(
        ..., description="Lowest genuine intermolecular/intramolecular vibrational mode in cm^-1"
    )
    A_MHz: float = Field(..., description="Rotational constant A in MHz")
    B_MHz: float = Field(..., description="Rotational constant B in MHz")
    C_MHz: float = Field(..., description="Rotational constant C in MHz")
    Ia_u_A2: float = Field(..., description="Principal moment of inertia Ia in u * Angstrom^2")
    Ib_u_A2: float = Field(..., description="Principal moment of inertia Ib in u * Angstrom^2")
    Ic_u_A2: float = Field(..., description="Principal moment of inertia Ic in u * Angstrom^2")
    Paa_u_A2: float = Field(..., description="Planar moment Paa = (Ib + Ic - Ia) / 2 in u * Angstrom^2")
    Pbb_u_A2: float = Field(..., description="Planar moment Pbb = (Ia + Ic - Ib) / 2 in u * Angstrom^2")
    Pcc_u_A2: float = Field(..., description="Planar moment Pcc = (Ia + Ib - Ic) / 2 in u * Angstrom^2")
    inertial_defect_amu_A2: float = Field(
        ..., description="Inertial defect Delta = Ic - Ia - Ib in u * Angstrom^2"
    )
    kappa: float = Field(..., description="Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)")


class BifurcatedStorageConfig(BaseModel):
    """Configuration profile for bifurcated active runtime and archival stores."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    active_runtime_path: str = Field(..., description="Filesystem path to runtime_active.h5")
    archive_pes_path: str = Field(..., description="Filesystem path to archive_pes.h5 / campaign.h5")
    storage_mode: StorageMode = Field(default=StorageMode.BIFURCATED, description="Operating storage mode")
    chunk_points: int = Field(default=512, ge=1, description="Number of points per chunk in HDF5 datasets")
    compression: str = Field(default="gzip", description="Lossless compression algorithm (gzip, lzf)")
    compression_opts: int = Field(default=4, ge=1, le=9, description="Compression level for gzip")
    shuffle: bool = Field(default=True, description="Enable byte shuffle filter for better compression ratios")
    fletcher32: bool = Field(default=True, description="Enable Fletcher32 checksum filter for data integrity")
    scaleoffset: Optional[int] = Field(
        default=None, description="Lossy scale-offset filter (MUST be None; strictly banned in CoChem)"
    )

    @field_validator("scaleoffset")
    @classmethod
    def validate_scaleoffset_strictly_banned(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            raise MethodMatrixViolationError(
                "scaleoffset lossy compression filter is strictly banned in CoChem HDF5 datastores to "
                "prevent precision truncation on micro-Hartree energy surfaces and artificial Hessian frequencies.",
                error_code=ProvenanceErrorCode.PRECISION_VIOLATION,
            )
        return v


# =============================================================================
# 2. MENDELEEV DYNAMIC MASS RESOLUTION (Mendeleev Library Mandate)
# =============================================================================

def get_atomic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """
    Dynamically retrieves standard atomic weight or exact isotopic mass from the `mendeleev` library.
    Strictly forbids hardcoding atomic masses or manually inserting CODATA mass constants.

    Args:
        symbol: Element symbol (e.g. 'C', 'H', 'O', 'Cl', 'D', 'T')
        mass_number: Specific isotope nucleon count (e.g. 13 for 13C, 2 for 2H/D).
                     If None, returns the standard IUPAC atomic weight.

    Returns:
        Atomic mass in unified atomic mass units (u / Da).
    """
    clean_sym = symbol.strip().capitalize()
    # Normalize hydrogen isotopes
    if clean_sym in ("D", "H2"):
        clean_sym = "H"
        mass_number = 2
    elif clean_sym in ("T", "H3"):
        clean_sym = "H"
        mass_number = 3

    try:
        el = element(clean_sym)
    except Exception as exc:
        raise ValueError(f"Failed to query Mendeleev library for element '{symbol}': {exc}") from exc

    if mass_number is not None:
        for iso in el.isotopes:
            if iso.mass_number == mass_number:
                if iso.mass is not None:
                    return float(iso.mass)
                break
        # Fallback to isotopic mass estimation if exact mass is None
        logger.warning(
            f"Exact isotopic mass not found in Mendeleev for {clean_sym}-{mass_number}; "
            f"using nominal integer mass {mass_number}.0"
        )
        return float(mass_number)

    if el.mass is not None:
        return float(el.mass)

    raise ValueError(f"Mendeleev mass is undefined for element '{symbol}' (mass_number={mass_number})")


def get_atomic_masses_for_symbols(
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """
    Returns array of atomic masses in unified atomic mass units (u) for a sequence of symbols.

    Args:
        symbols: Sequence of elemental symbols (e.g. ['C', 'O', 'H', 'H'])
        mass_numbers: Optional sequence of specific isotope mass numbers (e.g. [13, None, None, 2])

    Returns:
        NumPy array of shape (N,) with dtype float64.
    """
    masses: List[float] = []
    for i, s in enumerate(symbols):
        iso_num = mass_numbers[i] if mass_numbers is not None and i < len(mass_numbers) else None
        masses.append(get_atomic_mass(s, iso_num))
    return np.asarray(masses, dtype=np.float64)


# =============================================================================
# 3. MOLECULAR GEOMETRY & ROTATIONAL MATHEMATICS (§3, §4, §5)
# =============================================================================

def compute_center_of_mass(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """
    Computes the 3D center of mass in Angstroms.

    Args:
        symbols: Sequence of atom symbols
        coords: Cartesian coordinates array (N, 3) in Angstroms
        mass_numbers: Optional isotopic mass numbers

    Returns:
        3-element center of mass vector (x, y, z) in Angstroms.
    """
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    total_mass = float(np.sum(masses))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    com = np.sum(coords * masses[:, None], axis=0) / total_mass
    return com


def compute_inertia_tensor(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes the moment of inertia tensor shifted to the molecular center of mass.

    Returns:
        I_tensor: 3x3 inertia tensor in u * Angstrom^2
        principal_moments: sorted eigenvalues (Ia <= Ib <= Ic) in u * Angstrom^2
        principal_axes: 3x3 eigenvector matrix (columns are principal axes a, b, c)
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    com = compute_center_of_mass(symbols, coords_arr, mass_numbers)
    r = coords_arr - com
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)

    I = np.full((3, 3), 0.0, dtype=np.float64)
    eye3 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    for m_i, r_i in zip(masses, r, strict=False):
        r_sq = float(np.dot(r_i, r_i))
        I += m_i * (r_sq * eye3 - np.outer(r_i, r_i))

    evals, evecs = np.linalg.eigh(I)
    idx = np.argsort(evals)
    principal_moments = evals[idx]
    principal_axes = evecs[:, idx]

    return I, principal_moments, principal_axes


def compute_rotational_constants(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Dict[str, Any]:
    """
    Computes rotational constants (A >= B >= C in MHz), principal moments of inertia,
    planar moments (Paa, Pbb, Pcc), inertial defect (Delta = Ic - Ia - Ib), and Ray's kappa.
    """
    _, principal_moments, principal_axes = compute_inertia_tensor(symbols, coords, mass_numbers)
    Ia, Ib, Ic = float(principal_moments[0]), float(principal_moments[1]), float(principal_moments[2])

    A_MHz = INERTIA_TO_MHZ_FACTOR / Ia if Ia > 1e-12 else float("inf")
    B_MHz = INERTIA_TO_MHZ_FACTOR / Ib if Ib > 1e-12 else float("inf")
    C_MHz = INERTIA_TO_MHZ_FACTOR / Ic if Ic > 1e-12 else float("inf")

    Paa = (Ib + Ic - Ia) / 2.0
    Pbb = (Ia + Ic - Ib) / 2.0
    Pcc = (Ia + Ib - Ic) / 2.0
    inertial_defect = Ic - Ia - Ib

    denom = A_MHz - C_MHz
    kappa = (2.0 * B_MHz - A_MHz - C_MHz) / denom if abs(denom) > 1e-6 else 0.0

    return {
        "A_MHz": A_MHz,
        "B_MHz": B_MHz,
        "C_MHz": C_MHz,
        "Ia_u_A2": Ia,
        "Ib_u_A2": Ib,
        "Ic_u_A2": Ic,
        "Paa_u_A2": Paa,
        "Pbb_u_A2": Pbb,
        "Pcc_u_A2": Pcc,
        "inertial_defect_amu_A2": inertial_defect,
        "kappa": kappa,
        "principal_axes": principal_axes,
    }


def compute_delta_r_and_delta_b(
    coords1: np.ndarray,
    coords2: np.ndarray,
    symbols: Sequence[str],
) -> Dict[str, float]:
    """
    Computes coordinate shifts between two geometries (Delta R) and propagates error to rotational
    constant B using the Method Matrix law: Delta B / B ≈ 2 * Delta R / R (§4.1, §8B.5 Rule D1).
    """
    coords1_arr = np.asarray(coords1, dtype=np.float64)
    coords2_arr = np.asarray(coords2, dtype=np.float64)
    if coords1_arr.shape != coords2_arr.shape:
        raise ValueError(f"Shape mismatch in coordinate comparison: {coords1_arr.shape} vs {coords2_arr.shape}")

    diff = coords2_arr - coords1_arr
    rmsd_angstrom = float(np.sqrt(np.mean(np.sum(diff ** 2, axis=1))))
    rmsd_pm = rmsd_angstrom * 100.0

    com1 = compute_center_of_mass(symbols, coords1_arr)
    com2 = compute_center_of_mass(symbols, coords2_arr)
    com_shift_angstrom = float(np.linalg.norm(com2 - com1))
    com_shift_pm = com_shift_angstrom * 100.0

    rot1 = compute_rotational_constants(symbols, coords1_arr)
    rot2 = compute_rotational_constants(symbols, coords2_arr)

    b1 = rot1["B_MHz"]
    b2 = rot2["B_MHz"]
    delta_b_mhz = abs(b2 - b1)
    rel_b_error_pct = (delta_b_mhz / b1) * 100.0 if b1 > 0 else 0.0

    return {
        "rmsd_angstrom": rmsd_angstrom,
        "rmsd_pm": rmsd_pm,
        "com_shift_angstrom": com_shift_angstrom,
        "com_shift_pm": com_shift_pm,
        "B_initial_MHz": b1,
        "B_final_MHz": b2,
        "delta_B_MHz": delta_b_mhz,
        "rel_B_error_pct": rel_b_error_pct,
    }


# =============================================================================
# 4. ISOTOPOLOGUE FORCE FIELD RECYCLING ENGINE (Method Matrix Arrow 7 & §6.10)
# =============================================================================

def diagonalize_mass_weighted_hessian(
    cart_hessian: np.ndarray,
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Mass-weights a Cartesian Hessian (3N x 3N in Hartree/Bohr^2) using dynamic Mendeleev masses,
    diagonalizes to normal modes, and converts eigenvalues to harmonic frequencies in cm^-1.
    Imaginary frequencies (saddle points) are returned with negative values.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian matrix in Hartree/Bohr^2
        symbols: Sequence of atom symbols
        mass_numbers: Optional sequence of isotopic mass numbers

    Returns:
        sorted_freqs: 1D array of 3N harmonic frequencies in cm^-1
        sorted_modes: 3N x 3N eigenvector matrix of normal modes
    """
    natoms = len(symbols)
    h_arr = np.asarray(cart_hessian, dtype=np.float64)
    expected_dim = 3 * natoms
    if h_arr.shape != (expected_dim, expected_dim):
        raise ValueError(
            f"Hessian shape {h_arr.shape} does not match expected (3N, 3N) = ({expected_dim}, {expected_dim}) "
            f"for N={natoms} atoms."
        )

    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    # Construct 3N mass vector: (m0, m0, m0, m1, m1, m1, ...)
    m3n = np.repeat(masses, 3)

    # Mass-weighting: H_mw[i, j] = H[i, j] / sqrt(m[i] * m[j])
    inv_sqrt_m = 1.0 / np.sqrt(m3n)
    h_mw = h_arr * np.outer(inv_sqrt_m, inv_sqrt_m)

    # Symmetrize to eliminate machine precision numerical drift
    h_mw = 0.5 * (h_mw + h_mw.T)

    evals, evecs = np.linalg.eigh(h_mw)

    frequencies: List[float] = []
    for val in evals:
        if val >= 0.0:
            freq = math.sqrt(val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        else:
            freq = -math.sqrt(-val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        frequencies.append(freq)

    freq_arr = np.asarray(frequencies, dtype=np.float64)
    sort_idx = np.argsort(freq_arr)
    sorted_freqs = freq_arr[sort_idx]
    sorted_modes = evecs[:, sort_idx]

    return sorted_freqs, sorted_modes


def reanalyze_isotopologue(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    substituted_mass_numbers: Sequence[Optional[int]],
    iso_label: str,
    parent_label: str = "parent",
) -> IsotopologueResult:
    """
    Executes the zero-cost Isotopologue Shortcut (Method Matrix §8B.4 Arrow 7 & §6.10).
    Re-diagonalizes the saved Cartesian Hessian with substituted isotopic masses,
    recalculating harmonic frequencies, moments of inertia, and rotational constants.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian in Hartree/Bohr^2
        coords: Cartesian coordinates in Angstroms (N, 3)
        symbols: Elemental symbols
        substituted_mass_numbers: Target isotopic nucleon counts (e.g. [13, None, None, 2])
        iso_label: Descriptive label for this isotopologue (e.g. '13C_1', 'D_dimer')
        parent_label: Reference label of the parent Hessian

    Returns:
        IsotopologueResult containing all updated spectroscopic observables.
    """
    freqs, _ = diagonalize_mass_weighted_hessian(cart_hessian, symbols, substituted_mass_numbers)
    rot = compute_rotational_constants(symbols, coords, substituted_mass_numbers)
    masses = get_atomic_masses_for_symbols(symbols, substituted_mass_numbers)

    # Filter out 5 or 6 translational/rotational zero modes (|freq| < 20 cm^-1)
    vib_freqs = [float(f) for f in freqs if abs(f) > 20.0]
    lowest_harmonic = float(vib_freqs[0]) if vib_freqs else 0.0

    return IsotopologueResult(
        iso_label=iso_label,
        parent_label=parent_label,
        substituted_mass_numbers=list(substituted_mass_numbers),
        atomic_masses_amu=masses.tolist(),
        harmonic_frequencies_cm_inv=freqs.tolist(),
        vibrational_frequencies_cm_inv=vib_freqs,
        lowest_harmonic_mode_cm_inv=lowest_harmonic,
        A_MHz=rot["A_MHz"],
        B_MHz=rot["B_MHz"],
        C_MHz=rot["C_MHz"],
        Ia_u_A2=rot["Ia_u_A2"],
        Ib_u_A2=rot["Ib_u_A2"],
        Ic_u_A2=rot["Ic_u_A2"],
        Paa_u_A2=rot["Paa_u_A2"],
        Pbb_u_A2=rot["Pbb_u_A2"],
        Pcc_u_A2=rot["Pcc_u_A2"],
        inertial_defect_amu_A2=rot["inertial_defect_amu_A2"],
        kappa=rot["kappa"],
    )


def reanalyze_isotopologue_suite(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    isotopologue_map: Dict[str, Sequence[Optional[int]]],
    parent_label: str = "parent",
) -> Dict[str, IsotopologueResult]:
    """
    Batch evaluates a complete campaign suite of isotopologues from a single Hessian.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian in Hartree/Bohr^2
        coords: Cartesian coordinates in Angstroms (N, 3)
        symbols: Elemental symbols
        isotopologue_map: Mapping of iso_label to substituted mass numbers
        parent_label: Label of the parent Hessian

    Returns:
        Dictionary mapping iso_label to IsotopologueResult.
    """
    results: Dict[str, IsotopologueResult] = {}
    for iso_label, mass_nums in isotopologue_map.items():
        res = reanalyze_isotopologue(
            cart_hessian=cart_hessian,
            coords=coords,
            symbols=symbols,
            substituted_mass_numbers=mass_nums,
            iso_label=iso_label,
            parent_label=parent_label,
        )
        results[iso_label] = res
    return results


# =============================================================================
# 5. CORE HDF5 PES STORE (Method Matrix §8C)
# =============================================================================

_H5PY_PROCESS_LOCK = threading.RLock()


class ReadWriteFileLock:
    """Portable cross-platform Reader-Writer Lock backed by FileLock token tracking."""

    def __init__(self, lock_path: Union[str, Path], timeout: float = 30.0) -> None:
        self.lock_path = Path(lock_path)
        self.writer_lock_path = self.lock_path.with_name(self.lock_path.name + ".writer.lock")
        self.readers_dir = self.lock_path.with_name(self.lock_path.name + ".readers")
        self.timeout = timeout
        self.writer_lock = FileLock(str(self.writer_lock_path), timeout=timeout)
        self.readers_dir.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    def _get_write_depth(self) -> int:
        return getattr(self._local, "write_depth", 0)

    def _set_write_depth(self, val: int) -> None:
        self._local.write_depth = val

    def _get_read_depth(self) -> int:
        return getattr(self._local, "read_depth", 0)

    def _set_read_depth(self, val: int) -> None:
        self._local.read_depth = val

    @contextmanager
    def read_lock(self) -> Generator[None, None, None]:
        """Shared read lock allowing unbounded concurrent readers with re-entrancy."""
        # If the current thread already holds the write lock, reading is re-entrant and safe
        if self._get_write_depth() > 0:
            yield
            return

        read_depth = self._get_read_depth()
        if read_depth > 0:
            self._set_read_depth(read_depth + 1)
            try:
                yield
            finally:
                self._set_read_depth(self._get_read_depth() - 1)
            return

        token = self.readers_dir / f"read_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}.token"
        t0 = time.time()
        while self.writer_lock.is_locked:
            if time.time() - t0 > self.timeout:
                raise HDF5LockTimeoutError(
                    f"Timed out after {self.timeout}s waiting for read lock on {self.lock_path}",
                    error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
                )
            time.sleep(0.005)

        token.touch(exist_ok=True)
        self._set_read_depth(1)
        try:
            yield
        finally:
            self._set_read_depth(0)
            token.unlink(missing_ok=True)

    @contextmanager
    def write_lock(self) -> Generator[None, None, None]:
        """Exclusive write lock waiting for active readers to finish."""
        depth = self._get_write_depth()
        if depth > 0:
            # Re-entrant acquisition by the same thread
            self._set_write_depth(depth + 1)
            try:
                yield
            finally:
                self._set_write_depth(self._get_write_depth() - 1)
            return

        try:
            self.writer_lock.acquire(timeout=self.timeout)
        except Timeout as exc:
            raise HDF5LockTimeoutError(
                f"Timed out after {self.timeout}s acquiring writer lock on {self.lock_path}",
                error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
            ) from exc

        self._set_write_depth(1)
        t0 = time.time()
        try:
            while any(self.readers_dir.glob("*.token")):
                # Clean up stale tokens from exited processes
                for tok in list(self.readers_dir.glob("*.token")):
                    parts = tok.stem.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        r_pid = int(parts[1])
                        if HAS_PSUTIL and not psutil.pid_exists(r_pid):
                            tok.unlink(missing_ok=True)
                if not any(self.readers_dir.glob("*.token")):
                    break
                if time.time() - t0 > self.timeout:
                    raise HDF5LockTimeoutError(
                        f"Timed out after {self.timeout}s waiting for readers to clear on {self.lock_path}",
                        error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
                    )
                time.sleep(0.005)
            yield
        finally:
            self._set_write_depth(0)
            if self.writer_lock.is_locked:
                self.writer_lock.release()


class PESStore:
    """
    Resizable, chunked, gzip+shuffle+fletcher32 HDF5 PES Store with QCSchema field names.
    Implements Method Matrix §8C layout, state persistence, grid registration,
    Delta-learning alignment, and DVR grid reshaping.
    """

    def __init__(
        self,
        path: Union[str, Path],
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
        swmr_mode: bool = False,
        lock_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.path = validate_airgap_write_path(Path(path).resolve())
        self.lock_dir = Path(lock_dir).resolve() if lock_dir else get_node_local_scratch_dir()
        self.lock_path = self.lock_dir / f"{self.path.name}.lock"
        self.lock_timeout = lock_timeout
        self.rw_lock = ReadWriteFileLock(self.lock_path, timeout=self.lock_timeout)
        self.swmr_mode = swmr_mode
        new_file = not self.path.exists()

        if new_file:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._file_lock():
            with h5py.File(self.path, "a", libver="latest") as f:
                m = f.require_group("meta")
                if new_file:
                    m.attrs["schema_name"] = "vdw_pes_campaign"
                    m.attrs["schema_version"] = 1
                    m.attrs["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if complex_name:
                    m.attrs["complex"] = complex_name
                if symbols:
                    m.attrs["symbols"] = json.dumps(list(symbols))
                    m.attrs["n_atoms"] = len(symbols)
                    masses = get_atomic_masses_for_symbols(symbols)
                    m.attrs["atomic_masses_amu"] = json.dumps(masses.tolist())
                m.attrs["molecular_charge"] = molecular_charge
                m.attrs["spin_multiplicity"] = spin_multiplicity

                # Ensure required root groups exist
                f.require_group("methods")
                pts_grp = f.require_group("points")
                f.require_group("grids")
                f.require_group("hessians")
                f.require_group("isotopologues")
                f.require_group("checkpoints")

                # Pre-allocate chunked, resizable datasets before SWMR activation [D]
                n_dim = 3 * max(1, len(symbols))
                if "coordinates" not in pts_grp:
                    pts_grp.create_dataset(
                        "coordinates",
                        shape=(0, n_dim),
                        maxshape=(None, n_dim),
                        dtype=np.float64,
                        chunks=(512, n_dim),
                    )
                if "energies" not in pts_grp:
                    pts_grp.create_dataset(
                        "energies",
                        shape=(0,),
                        maxshape=(None,),
                        dtype=np.float64,
                        chunks=(512,),
                    )
                if "point_ids" not in pts_grp:
                    dt = h5py.string_dtype(encoding="utf-8")
                    pts_grp.create_dataset(
                        "point_ids",
                        shape=(0,),
                        maxshape=(None,),
                        dtype=dt,
                        chunks=(512,),
                    )

                # Cache properties
                self.n_atoms = int(m.attrs.get("n_atoms", len(symbols)))
                self.complex_name = str(m.attrs.get("complex", complex_name))
                sym_attr = m.attrs.get("symbols")
                self.symbols = json.loads(sym_attr) if isinstance(sym_attr, str) else list(symbols)
                self.molecular_charge = int(m.attrs.get("molecular_charge", molecular_charge))
                self.spin_multiplicity = int(m.attrs.get("spin_multiplicity", spin_multiplicity))

                # Phase 2 SWMR Activation: Flush metadata and enable SWMR mode
                f.flush()
                if self.swmr_mode:
                    try:
                        f.swmr_mode = True
                    except (AttributeError, RuntimeError):
                        pass

    @contextmanager
    def _file_lock(self) -> Generator[None, None, None]:
        """Cross-platform byte-range file lock context manager serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.write_lock():
                yield

    @contextmanager
    def shared_read_lock(self) -> Generator[None, None, None]:
        """Shared read lock allowing unbounded concurrent readers serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.read_lock():
                yield

    @contextmanager
    def open_reader(self) -> Generator[h5py.File, None, None]:
        """Open HDF5 file in SWMR read mode with libver='latest' under shared read lock."""
        with self.shared_read_lock():
            with h5py.File(self.path, "r", libver="latest", swmr=True) as f:
                yield f

    @contextmanager
    def exclusive_write_lock(self) -> Generator[None, None, None]:
        """Exclusive write lock waiting for active readers to clear serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.write_lock():
                yield

    # -------------------------------------------------------------------------
    # Method Registration (QCSchema v1)
    # -------------------------------------------------------------------------
    def register_method(self, method_id: str, **attrs: Any) -> None:
        """
        Registers a computational method with QCSchema attributes in /methods/<method_id>.

        Args:
            method_id: Unique string identifier for the method (e.g. 'dlpno_avtz', 'wb97mv_qz')
            attrs: QCSchema method attributes (method, basis, aux_basis, program, driver, keywords, etc.)
        """
        # Validate through Pydantic record if method and basis provided
        if "method" in attrs and "basis" in attrs:
            QCSchemaMethodRecord(method_id=method_id, **attrs)

        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group(f"methods/{method_id}")
                for k, v in attrs.items():
                    if isinstance(v, (dict, list)):
                        g.attrs[k] = json.dumps(v)
                    elif isinstance(v, (int, float, str, bool)):
                        g.attrs[k] = v
                    elif isinstance(v, Enum):
                        g.attrs[k] = v.value
                g.attrs.setdefault("registered_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def get_method(self, method_id: str) -> Dict[str, Any]:
        """Retrieves registered method attributes dictionary."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"methods/{method_id}" not in f:
                    raise KeyError(f"Method '{method_id}' not found in PESStore methods.")
                g = f[f"methods/{method_id}"]
                res: Dict[str, Any] = {}
                for k, v in g.attrs.items():
                    val = v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v
                    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                        try:
                            res[k] = json.loads(val)
                        except json.JSONDecodeError:
                            res[k] = val
                    else:
                        res[k] = val
                return res

    def list_methods(self) -> List[str]:
        """Lists all registered method IDs."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "methods" not in f:
                    return []
                return sorted(list(f["methods"].keys()))

    # -------------------------------------------------------------------------
    # Dataset Creation Helper
    # -------------------------------------------------------------------------
    def _ds(
        self,
        f: h5py.File,
        mid: str,
        name: str,
        shape_tail: Tuple[int, ...],
        dtype: Any,
        checksum: bool = False,
    ) -> h5py.Dataset:
        """Internal helper creating resizable chunked datasets with gzip+shuffle+fletcher32."""
        grp = f.require_group(f"points/{mid}")
        if name in grp:
            return grp[name]

        kw: Dict[str, Any] = {
            "shape": (0,) + shape_tail,
            "maxshape": (None,) + shape_tail,
            "dtype": dtype,
            "chunks": (CHUNK_POINTS,) + shape_tail,
        }
        if dtype != VLEN_STR:
            kw.update(compression="gzip", compression_opts=4, shuffle=True)
            if checksum:
                kw["fletcher32"] = True
        return grp.create_dataset(name, **kw)

    @staticmethod
    def _append(ds: h5py.Dataset, block: np.ndarray) -> int:
        """Appends a block of data along axis 0 of a resizable dataset."""
        idx = int(ds.shape[0])
        ds.resize(idx + len(block), axis=0)
        ds[idx:] = block
        return idx

    def add_point(self, point: PESPointRecord) -> None:
        """Append a single PESPointRecord into the HDF5 store in a thread-safe SWMR-compliant manner [D]."""
        with self._file_lock():
            with h5py.File(self.path, "a", libver="latest") as f:
                pts = f.require_group("points")
                coords = np.asarray(point.coordinates, dtype=np.float64)
                if coords.ndim == 1:
                    coords = coords[None, :]
                elif coords.ndim == 2:
                    coords = coords.reshape(1, -1)

                cur_len = pts["energies"].shape[0] if "energies" in pts else 0
                new_len = cur_len + 1

                if "coordinates" in pts:
                    if pts["coordinates"].shape[1] != coords.shape[1]:
                        pts["coordinates"].resize((new_len, max(pts["coordinates"].shape[1], coords.shape[1])))
                    else:
                        pts["coordinates"].resize((new_len, coords.shape[1]))
                    pts["coordinates"][cur_len] = coords[0]
                else:
                    pts.create_dataset(
                        "coordinates",
                        data=coords,
                        maxshape=(None, coords.shape[1]),
                        chunks=(512, coords.shape[1]),
                    )

                if "energies" in pts:
                    pts["energies"].resize((new_len,))
                    pts["energies"][cur_len] = float(point.energy)
                else:
                    pts.create_dataset(
                        "energies",
                        data=np.array([point.energy], dtype=np.float64),
                        maxshape=(None,),
                        chunks=(512,),
                    )

                if "point_ids" in pts:
                    pts["point_ids"].resize((new_len,))
                    pts["point_ids"][cur_len] = str(point.point_id)
                else:
                    dt = h5py.string_dtype(encoding="utf-8")
                    d = pts.create_dataset(
                        "point_ids",
                        shape=(1,),
                        maxshape=(None,),
                        dtype=dt,
                        chunks=(512,),
                    )
                    d[0] = str(point.point_id)

                f.flush()

    def write_entry(self, point: Any) -> None:
        """Persist PES point record in-place adhering to Suggestion #65."""
        self.add_point(point)

    def get_all_point_ids(self) -> List[str]:
        """Retrieve all registered point IDs with SWMR refresh [D]."""
        with self.rw_lock.read_lock():
            with h5py.File(self.path, "r", libver="latest", swmr=self.swmr_mode) as f:
                if "/points/point_ids" in f:
                    dset = f["/points/point_ids"]
                    if self.swmr_mode:
                        try:
                            dset.refresh()
                        except Exception:
                            pass
                    raw = dset[:]
                    return [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in raw]
                return []

    # -------------------------------------------------------------------------
    # Writing PES Points
    # -------------------------------------------------------------------------
    def add_points(
        self,
        method_id: str,
        coords: Union[Sequence[Any], np.ndarray],
        energies: Union[Sequence[float], np.ndarray, float],
        *,
        point_ids: Optional[Sequence[str]] = None,
        gradients: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: Optional[Union[Sequence[bool], np.ndarray, bool]] = None,
        wall_s: Optional[Union[Sequence[float], np.ndarray, float]] = None,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """
        Adds computed PES points with full QCSchema provenance, chunking, and checksums.

        Args:
            method_id: Registered method identifier
            coords: Cartesian coordinates array (Npts, Natoms, 3) or (Natoms, 3) for a single point
            energies: Electronic energies array (Npts,) or float for single point
            point_ids: Optional list of unique point IDs
            gradients: Optional gradients array (Npts, Natoms, 3) in Hartree/Bohr
            converged: Convergence flags (Npts,) or bool
            wall_s: Wall clock times in seconds
            creator: Package name
            version: Package version
            routine: Calculation routine

        Returns:
            Starting index i0 where points were inserted.
        """
        coords_arr = np.asarray(coords, dtype=np.float64)
        if coords_arr.ndim == 2:
            coords_arr = coords_arr[None]
        npts, natm = coords_arr.shape[0], coords_arr.shape[1]

        energies_arr = np.asarray(energies, dtype=np.float64)
        if energies_arr.ndim == 0:
            energies_arr = energies_arr[None]

        if len(energies_arr) != npts:
            raise ValueError(f"Number of energies ({len(energies_arr)}) does not match number of points ({npts}).")

        # Construct signed provenance record
        prov_obj = QCSchemaProvenance(
            creator=creator,
            version=version,
            routine=routine,
            host=socket.gethostname(),
            platform=platform.platform(),
            utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        prov_obj.compute_signature()
        prov_json = prov_obj.model_dump_json()

        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                # Ensure method group exists
                f.require_group(f"methods/{method_id}")

                i0 = self._append(self._ds(f, method_id, "coordinates", (natm, 3), np.float64), coords_arr)
                self._append(self._ds(f, method_id, "energy", (), np.float64, checksum=True), energies_arr)

                # Convergence
                conv_block = np.full(npts, True, dtype=bool) if converged is None else np.asarray(converged, dtype=bool)
                if conv_block.ndim == 0:
                    conv_block = np.full(npts, bool(converged), dtype=bool)
                self._append(self._ds(f, method_id, "converged", (), np.bool_), conv_block)

                # Wall time
                wall_block = np.full(npts, 0.0, dtype=np.float64) if wall_s is None else np.asarray(wall_s, dtype=np.float64)
                if wall_block.ndim == 0:
                    wall_block = np.full(npts, float(wall_s), dtype=np.float64)
                self._append(self._ds(f, method_id, "wall_s", (), np.float64), wall_block)

                # Provenance
                self._append(self._ds(f, method_id, "provenance", (), VLEN_STR), np.array([prov_json] * npts, dtype=object))

                # Point IDs
                p_ids = list(point_ids) if point_ids is not None else [f"{method_id}:{i0 + k}" for k in range(npts)]
                self._append(self._ds(f, method_id, "point_id", (), VLEN_STR), np.array(p_ids, dtype=object))

                # Optional gradients
                if gradients is not None:
                    g_arr = np.asarray(gradients, dtype=np.float64)
                    if g_arr.ndim == 2:
                        g_arr = g_arr[None]
                    if "gradient" not in f[f"points/{method_id}"] and i0 > 0:
                        g_ds = self._ds(f, method_id, "gradient", (natm, 3), np.float64)
                        nan_pad = np.full((i0, natm, 3), np.nan, dtype=np.float64)
                        self._append(g_ds, nan_pad)
                        self._append(g_ds, g_arr)
                    else:
                        self._append(self._ds(f, method_id, "gradient", (natm, 3), np.float64), g_arr)
                elif "gradient" in f[f"points/{method_id}"]:
                    nan_pad = np.full((npts, natm, 3), np.nan, dtype=np.float64)
                    self._append(f[f"points/{method_id}/gradient"], nan_pad)

                f.flush()

        return i0

    def get_points(self, method_id: str, converged_only: bool = False) -> List[Dict[str, Any]]:
        """Convenience query returning list of point dicts for a method."""
        payload = self.dataset_full(method_id, converged_only=converged_only)
        n = min(len(payload["energy"]), len(payload["point_id"]), len(payload["coordinates"]))
        points_list = []
        for i in range(n):
            pt = {
                "point_id": payload["point_id"][i],
                "coordinates": payload["coordinates"][i],
                "energy": float(payload["energy"][i]),
                "converged": bool(payload["converged"][i]),
                "wall_s": float(payload["wall_s"][i]),
            }
            if "gradient" in payload and i < len(payload["gradient"]):
                pt["gradient"] = payload["gradient"][i]
            points_list.append(pt)
        return points_list

    # -------------------------------------------------------------------------
    # Hessians & Isotopologue Storage
    # -------------------------------------------------------------------------
    def add_hessian(
        self,
        label: str,
        H: Union[Sequence[Any], np.ndarray],
        *,
        level: str = "",
        geometry_ref: str = "",
        units: str = "Hartree/Bohr^2",
        mass_weighted: bool = False,
        frequencies_cm_inv: Optional[Sequence[float]] = None,
    ) -> None:
        """Stores Cartesian Hessian tensor and metadata in /hessians/<label>."""
        h_arr = np.asarray(H, dtype=np.float64)
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group("hessians")
                if label in g:
                    del g[label]
                d = g.create_dataset(
                    label,
                    data=h_arr,
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )
                d.attrs["level"] = level
                d.attrs["geometry_ref"] = geometry_ref
                d.attrs["units"] = units
                d.attrs["mass_weighted"] = mass_weighted
                d.attrs["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if frequencies_cm_inv is not None:
                    d.attrs["frequencies_cm_inv"] = json.dumps(list(frequencies_cm_inv))

    def get_hessian(self, label: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Retrieves Cartesian Hessian array and metadata dictionary."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"hessians/{label}" not in f:
                    raise KeyError(f"Hessian '{label}' not found in PESStore.")
                ds = f[f"hessians/{label}"]
                h_arr = ds[:]
                attrs = {k: v for k, v in ds.attrs.items()}
                return h_arr, attrs

    def list_hessians(self) -> List[str]:
        """Lists all registered Hessian labels."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "hessians" not in f:
                    return []
                return sorted(list(f["hessians"].keys()))

    def add_isotopologue_result(self, label: str, iso_result: IsotopologueResult) -> None:
        """Stores an IsotopologueResult under /isotopologues/<label>/<iso_label>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                grp = f.require_group(f"isotopologues/{label}/{iso_result.iso_label}")
                grp.attrs["payload_json"] = iso_result.model_dump_json()
                grp.attrs["A_MHz"] = iso_result.A_MHz
                grp.attrs["B_MHz"] = iso_result.B_MHz
                grp.attrs["C_MHz"] = iso_result.C_MHz
                grp.attrs["inertial_defect_amu_A2"] = iso_result.inertial_defect_amu_A2
                grp.attrs["lowest_harmonic_mode_cm_inv"] = iso_result.lowest_harmonic_mode_cm_inv
                grp.attrs["saved_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_isotopologue_result(self, label: str, iso_label: str) -> IsotopologueResult:
        """Retrieves a saved IsotopologueResult."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"isotopologues/{label}/{iso_label}"
                if path not in f:
                    raise KeyError(f"Isotopologue '{iso_label}' not found under Hessian '{label}'.")
                grp = f[path]
                payload = grp.attrs.get("payload_json")
                if payload is None:
                    raise ValueError(f"Isotopologue record at '{path}' is missing 'payload_json' attribute.")
                return IsotopologueResult.model_validate_json(payload)

    def list_isotopologues(self, label: str) -> List[str]:
        """Lists all isotopologue labels evaluated under Hessian label."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"isotopologues/{label}"
                if path not in f:
                    return []
                return sorted(list(f[path].keys()))

    # -------------------------------------------------------------------------
    # Grids & Multi-Dimensional Scans
    # -------------------------------------------------------------------------
    def register_grid(self, grid_id: str, axes: Dict[str, Sequence[float]], grid_type: str = "cartesian") -> None:
        """Registers grid axes for potential energy surfaces in /grids/<grid_id>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group(f"grids/{grid_id}")
                for name, vals in axes.items():
                    if name in g:
                        del g[name]
                    g.create_dataset(name, data=np.asarray(vals, dtype=np.float64))
                g.attrs["axis_order"] = json.dumps(list(axes.keys()))
                g.attrs["shape"] = [len(v) for v in axes.values()]
                g.attrs["grid_type"] = grid_type
                g.attrs["registered_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_grid(self, grid_id: str) -> Dict[str, Any]:
        """Retrieves grid axes and metadata."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"grids/{grid_id}" not in f:
                    raise KeyError(f"Grid '{grid_id}' not found in PESStore.")
                g = f[f"grids/{grid_id}"]
                axes: Dict[str, np.ndarray] = {}
                for k in g.keys():
                    axes[k] = g[k][:]
                axis_order = json.loads(g.attrs.get("axis_order", "[]"))
                shape = list(g.attrs.get("shape", []))
                grid_type = str(g.attrs.get("grid_type", "cartesian"))
                return {
                    "grid_id": grid_id,
                    "axes": axes,
                    "axis_order": axis_order,
                    "shape": shape,
                    "grid_type": grid_type,
                }

    def list_grids(self) -> List[str]:
        """Lists all registered grid IDs."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "grids" not in f:
                    return []
                return sorted(list(f["grids"].keys()))

    # -------------------------------------------------------------------------
    # Idempotent Querying, Delta-Learning, & DVR
    # -------------------------------------------------------------------------
    def todo(self, method_id: str, wanted_ids: Iterable[str]) -> List[str]:
        """
        Identifies missing / unconverged points for incremental refinement and restart.

        Args:
            method_id: Method identifier
            wanted_ids: List of requested point IDs

        Returns:
            List of point IDs that are missing or not yet converged.
        """
        wanted_list = list(wanted_ids)
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                p = f.get(f"points/{method_id}")
                if p is None or "point_id" not in p:
                    return wanted_list
                p_ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
                converged = p["converged"][:]
                have = {s for s, ok in zip(p_ids, converged, strict=False) if ok}
        return [i for i in wanted_list if i not in have]

    def dataset(self, method_id: str, converged_only: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retrieves coordinates and energies array for a method.

        Args:
            method_id: Method identifier
            converged_only: If True, only returns converged points

        Returns:
            Tuple of (coordinates (Npts, Natoms, 3), energies (Npts,))
        """
        with self.shared_read_lock():
            with h5py.File(self.path, "r") as f:
                if f"points/{method_id}" not in f:
                    raise KeyError(f"No points dataset found for method '{method_id}'.")
                p = f[f"points/{method_id}"]
                mask = p["converged"][:] if converged_only else slice(None)
                coords = p["coordinates"][:][mask]
                energies = p["energy"][:][mask]
                return coords, energies

    def dataset_full(self, method_id: str, converged_only: bool = True) -> Dict[str, Any]:
        """Retrieves full points payload dictionary for a method."""
        with self.shared_read_lock():
            with h5py.File(self.path, "r") as f:
                if f"points/{method_id}" not in f:
                    raise KeyError(f"No points dataset found for method '{method_id}'.")
                p = f[f"points/{method_id}"]
                mask = p["converged"][:] if converged_only else slice(None)
                point_ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:][mask]]
                res: Dict[str, Any] = {
                    "method_id": method_id,
                    "coordinates": p["coordinates"][:][mask],
                    "energy": p["energy"][:][mask],
                    "converged": p["converged"][:][mask],
                    "wall_s": p["wall_s"][:][mask],
                    "point_id": point_ids,
                }
                if "gradient" in p:
                    res["gradient"] = p["gradient"][:][mask]
                return res

    def delta_pairs(self, low_method: str, high_method: str) -> Tuple[List[str], np.ndarray, np.ndarray]:
        """
        Returns aligned (keys, coordinates, E_high - E_low) pairs for Delta-learning MLFF training.

        Args:
            low_method: Low-level method identifier (e.g. 'wb97xd4_tz')
            high_method: High-level method identifier (e.g. 'dlpno_ccsdt1_avtz')

        Returns:
            keys: Aligned common point IDs
            X: High-level coordinates array (Npts, Natoms, 3)
            dE: Delta energies array (Npts,) in Hartrees (E_high - E_low)
        """
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                def get_idx(mid: str) -> Dict[str, int]:
                    if f"points/{mid}" not in f:
                        return {}
                    p = f[f"points/{mid}"]
                    ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
                    conv = p["converged"][:]
                    return {k: j for j, (k, ok) in enumerate(zip(ids, conv, strict=False)) if ok}

                il = get_idx(low_method)
                ih = get_idx(high_method)
                keys = sorted(set(il.keys()) & set(ih.keys()))

                if not keys:
                    return [], np.empty((0, self.n_atoms, 3)), np.empty((0,))

                idx_h = [ih[k] for k in keys]
                idx_l = [il[k] for k in keys]

                X = f[f"points/{high_method}/coordinates"][:][idx_h]
                dE = f[f"points/{high_method}/energy"][:][idx_h] - f[f"points/{low_method}/energy"][:][idx_l]
                return keys, X, dE

    def dvr_grid(self, method_id: str, grid_id: str) -> np.ndarray:
        """
        Reshapes energies onto a registered product grid for Discrete Variable Representation (DVR) solvers.
        Missing or unconverged points are filled with NaN.

        Args:
            method_id: Method identifier
            grid_id: Grid identifier

        Returns:
            Multidimensional NumPy array matching grid shape with potential values in Hartrees.
        """
        with self.open_reader() as f:
            if f"grids/{grid_id}" not in f:
                raise KeyError(f"Grid '{grid_id}' not found in PESStore.")
            shape = tuple(int(x) for x in f[f"grids/{grid_id}"].attrs["shape"])
            if f"points/{method_id}" not in f:
                return np.full(shape, np.nan, dtype=np.float64)

            p = f[f"points/{method_id}"]
            for ds_name in ["point_id", "converged", "energy"]:
                if ds_name in p and hasattr(p[ds_name], "refresh"):
                    try:
                        p[ds_name].refresh()
                    except Exception:
                        pass
            ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
            conv = p["converged"][:]
            energies = p["energy"][:]

            total_pts = 1
            for dim in shape:
                total_pts *= dim

            V = np.full(total_pts, np.nan, dtype=np.float64)
            prefix = f"{grid_id}:"
            for j, k in enumerate(ids):
                if k.startswith(prefix) and conv[j]:
                    try:
                        idx = int(k.split(":")[1])
                        if 0 <= idx < total_pts:
                            V[idx] = energies[j]
                    except (ValueError, IndexError):
                        logger.debug("Failed to parse point index from point_id '%s'", k)
            return V.reshape(shape)

    # -------------------------------------------------------------------------
    # Checkpoints & Integrity
    # -------------------------------------------------------------------------
    def checkpoint_state(self, checkpoint_name: str, state_data: Dict[str, Any]) -> None:
        """Serializes arbitrary dictionary state to /checkpoints/<checkpoint_name>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                grp = f.require_group(f"checkpoints/{checkpoint_name}")
                grp.attrs["saved_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                for k, v in state_data.items():
                    if isinstance(v, np.ndarray):
                        if k in grp:
                            del grp[k]
                        grp.create_dataset(k, data=v)
                    elif isinstance(v, (int, float, str, bool)):
                        grp.attrs[k] = v
                    else:
                        grp.attrs[k] = json.dumps(v)

    def read_checkpoint(self, checkpoint_name: str) -> Dict[str, Any]:
        """Reads back saved checkpoint state dictionary."""
        result: Dict[str, Any] = {}
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"checkpoints/{checkpoint_name}"
                if path not in f:
                    return result
                grp = f[path]
                for k, v in grp.attrs.items():
                    val = v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v
                    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                        try:
                            result[k] = json.loads(val)
                        except json.JSONDecodeError:
                            result[k] = val
                    else:
                        result[k] = val
                for k in grp.keys():
                    result[k] = grp[k][:]
        return result

    def validate_integrity(self) -> Dict[str, Any]:
        """Verifies Fletcher32 checksums and dataset completeness."""
        report: Dict[str, Any] = {"status": "PASSED", "methods": {}, "corrupted_datasets": []}
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "points" in f:
                    for mid in f["points"].keys():
                        grp = f[f"points/{mid}"]
                        n_pts = len(grp["energy"]) if "energy" in grp else 0
                        report["methods"][mid] = {"n_points": n_pts}
                        # Reading full dataset forces Fletcher32 checksum validation
                        try:
                            _ = grp["energy"][:]
                            _ = grp["coordinates"][:]
                        except Exception as exc:
                            report["status"] = "CORRUPTED"
                            report["corrupted_datasets"].append(f"points/{mid}: {exc}")
        return report


# =============================================================================
# 6. SWMR & ARCHIVAL BIFURCATED PES STORE
# =============================================================================

class BifurcatedPESStore:
    """
    Manages dual-tier storage bifurcation:
    1. Active Runtime Store (runtime_active.h5): High-throughput active SWMR or scratch container.
    2. Archival QCSchema Store (archive_pes.h5 / campaign.h5): Lossless compressed HDF5 store.
    """

    def __init__(
        self,
        active_runtime_path: Optional[Union[str, Path]] = None,
        archive_pes_path: Optional[Union[str, Path]] = None,
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
    ) -> None:
        art_dir = get_artifact_dir()
        runtime_dir = get_runtime_dir()

        self.active_path = (
            resolve_mapped_path(active_runtime_path, runtime_dir)
            if active_runtime_path is not None
            else runtime_dir / "runtime_active.h5"
        )
        self.archive_path = (
            resolve_mapped_path(archive_pes_path, art_dir)
            if archive_pes_path is not None
            else art_dir / "Databases" / "archive_pes.h5"
        )

        self.complex_name = complex_name
        self.symbols = list(symbols)
        self.molecular_charge = molecular_charge
        self.spin_multiplicity = spin_multiplicity
        self.lock_timeout = lock_timeout

        # Initialize underlying PES stores
        self.active_store = PESStore(
            path=self.active_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )
        self.archive_store = PESStore(
            path=self.archive_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    # Active / Archival Execution Context Managers
    # -------------------------------------------------------------------------
    @contextmanager
    def active_writer(self) -> Generator[PESStore, None, None]:
        """Context manager providing thread-safe write access to active runtime store."""
        with self.active_store.exclusive_write_lock():
            yield self.active_store

    @contextmanager
    def active_reader(self) -> Generator[PESStore, None, None]:
        """Context manager providing concurrent read access to active runtime store."""
        with self.active_store.shared_read_lock():
            yield self.active_store

    @contextmanager
    def archive_writer(self) -> Generator[PESStore, None, None]:
        """Context manager providing thread-safe write access to archival store."""
        with self.archive_store.exclusive_write_lock():
            yield self.archive_store

    @contextmanager
    def archive_reader(self) -> Generator[PESStore, None, None]:
        """Context manager providing read access to archival store."""
        with self.archive_store.shared_read_lock():
            yield self.archive_store

    # -------------------------------------------------------------------------
    # Point Recording & Promotion
    # -------------------------------------------------------------------------
    def record_point_to_active(
        self,
        method_id: str,
        coords: Union[Sequence[Any], np.ndarray],
        energy: float,
        *,
        point_id: Optional[str] = None,
        gradient: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: bool = True,
        wall_s: float = 0.0,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """Appends a single calculation result to the active runtime store."""
        return self.active_store.add_points(
            method_id=method_id,
            coords=coords,
            energies=[energy],
            point_ids=[point_id] if point_id is not None else None,
            gradients=[gradient] if gradient is not None else None,
            converged=[converged],
            wall_s=[wall_s],
            creator=creator,
            version=version,
            routine=routine,
        )

    def record_hessian_and_recycle_isotopologues(
        self,
        label: str,
        cart_hessian: np.ndarray,
        coords: np.ndarray,
        isotopologue_map: Dict[str, Sequence[Optional[int]]],
        level: str = "",
        geometry_ref: str = "",
    ) -> Dict[str, IsotopologueResult]:
        """
        Stores Cartesian Hessian in active store, executes zero-cost isotopologue recycling
        for all requested isotopic substitutions, and persists results to active store.
        """
        self.active_store.add_hessian(
            label=label,
            H=cart_hessian,
            level=level,
            geometry_ref=geometry_ref,
        )

        iso_results = reanalyze_isotopologue_suite(
            cart_hessian=cart_hessian,
            coords=coords,
            symbols=self.symbols,
            isotopologue_map=isotopologue_map,
            parent_label=label,
        )

        for _, res in iso_results.items():
            self.active_store.add_isotopologue_result(label, res)

        return iso_results

    def promote_active_to_archive(self, method_id: Optional[str] = None) -> int:
        """
        Transfers converged points and methods from the active runtime store into the
        compressed archival store with Fletcher32 checksum verification.

        Args:
            method_id: Optional specific method ID to promote. If None, promotes all methods.

        Returns:
            Total count of points promoted.
        """
        methods = [method_id] if method_id is not None else self.active_store.list_methods()
        total_promoted = 0

        for mid in methods:
            # Transfer method registration
            try:
                m_attrs = self.active_store.get_method(mid)
                self.archive_store.register_method(mid, **m_attrs)
            except Exception as exc:
                logger.warning(f"Could not transfer method registration for '{mid}': {exc}")

            # Transfer points
            try:
                data = self.active_store.dataset_full(mid, converged_only=True)
                npts = len(data["energy"])
                if npts > 0:
                    # Check which points are already in archive
                    needed_ids = self.archive_store.todo(mid, data["point_id"])
                    if needed_ids:
                        needed_set = set(needed_ids)
                        keep_mask = [pid in needed_set for pid in data["point_id"]]

                        coords_to_add = data["coordinates"][keep_mask]
                        energies_to_add = data["energy"][keep_mask]
                        pids_to_add = [pid for pid, ok in zip(data["point_id"], keep_mask, strict=False) if ok]
                        grads_to_add = data.get("gradient")[keep_mask] if "gradient" in data else None
                        conv_to_add = data["converged"][keep_mask]
                        wall_to_add = data["wall_s"][keep_mask]

                        self.archive_store.add_points(
                            method_id=mid,
                            coords=coords_to_add,
                            energies=energies_to_add,
                            point_ids=pids_to_add,
                            gradients=grads_to_add,
                            converged=conv_to_add,
                            wall_s=wall_to_add,
                        )
                        total_promoted += len(pids_to_add)
            except KeyError:
                continue

        # Transfer Hessians and Isotopologues
        for h_label in self.active_store.list_hessians():
            try:
                h_mat, h_attrs = self.active_store.get_hessian(h_label)
                self.archive_store.add_hessian(
                    label=h_label,
                    H=h_mat,
                    level=str(h_attrs.get("level", "")),
                    geometry_ref=str(h_attrs.get("geometry_ref", "")),
                    units=str(h_attrs.get("units", "Hartree/Bohr^2")),
                )
                for iso_label in self.active_store.list_isotopologues(h_label):
                    iso_res = self.active_store.get_isotopologue_result(h_label, iso_label)
                    self.archive_store.add_isotopologue_result(h_label, iso_res)
            except Exception as exc:
                logger.warning(f"Could not transfer Hessian '{h_label}' to archive: {exc}")

        logger.info(f"Promoted {total_promoted} active runtime points to archival store {self.archive_path}")
        return total_promoted


class TripartitePESStore(BifurcatedPESStore):
    """
    Tripartite PES Store architecture incorporating:
    1. Active runtime SWMR store for real-time trajectory/grid evaluation.
    2. Shared reader / exclusive writer synchronization via ReadWriteFileLock.
    3. Archival store for long-term compressed QCSchema representations.
    """

    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
        archive_path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            active_runtime_path=path,
            archive_pes_path=archive_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )

    def register_method(self, method_id: str, **attrs: Any) -> None:
        """Registers computational method into the active runtime store."""
        self.active_store.register_method(method_id, **attrs)

    def get_points(self, method_id: str, converged_only: bool = False) -> List[Dict[str, Any]]:
        """Retrieves points for a method from active runtime store."""
        return self.active_store.get_points(method_id, converged_only=converged_only)

    def add_points(self, *args: Any, **kwargs: Any) -> int:
        """Appends points into the active runtime store."""
        return self.active_store.add_points(*args, **kwargs)

    def list_methods(self) -> List[str]:
        """Lists methods registered in active runtime store."""
        return self.active_store.list_methods()

    def get_method(self, method_id: str) -> Dict[str, Any]:
        """Retrieves metadata attributes for a registered method."""
        return self.active_store.get_method(method_id)

    def todo(self, method_id: str, wanted_point_ids: Sequence[str]) -> List[str]:
        """Identifies missing or unconverged points in active runtime store."""
        return self.active_store.todo(method_id, wanted_point_ids)

    def dataset(self, *args: Any, **kwargs: Any) -> Tuple[np.ndarray, np.ndarray]:
        """Extracts aligned coordinates and energies from active runtime store."""
        return self.active_store.dataset(*args, **kwargs)

    def dataset_full(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Extracts full structured dataset dictionary from active runtime store."""
        return self.active_store.dataset_full(*args, **kwargs)


# =============================================================================
# 7. PARALLEL SHARD MERGER UTILITY
# =============================================================================

def merge_pes_shards(
    shard_paths: Sequence[Union[str, Path]],
    target_store_path: Union[str, Path],
    complex_name: str = "",
    symbols: Sequence[str] = (),
) -> int:
    """
    Merges multiple worker PES shards (campaign_rank_0.h5, campaign_rank_1.h5, ...)
    into a single master PES store atomically.

    Args:
        shard_paths: List of shard file paths
        target_store_path: Destination HDF5 file path
        complex_name: Complex name identifier
        symbols: Elemental symbols

    Returns:
        Total count of points merged into the target store.
    """
    target = PESStore(
        path=target_store_path,
        complex_name=complex_name,
        symbols=symbols,
    )
    total_merged = 0

    for s_path in shard_paths:
        p = Path(s_path)
        if not p.exists():
            logger.warning(f"Shard file not found: {p}")
            continue

        shard = PESStore(path=p)
        methods = shard.list_methods()

        for mid in methods:
            # Register method if not present
            try:
                m_attrs = shard.get_method(mid)
                target.register_method(mid, **m_attrs)
            except Exception as exc:
                logger.debug("Method registration skipped or failed during merge for '%s': %s", mid, exc)

            try:
                data = shard.dataset_full(mid, converged_only=True)
                npts = len(data["energy"])
                if npts > 0:
                    needed_ids = target.todo(mid, data["point_id"])
                    if needed_ids:
                        needed_set = set(needed_ids)
                        keep_mask = [pid in needed_set for pid in data["point_id"]]

                        coords_to_add = data["coordinates"][keep_mask]
                        energies_to_add = data["energy"][keep_mask]
                        pids_to_add = [pid for pid, ok in zip(data["point_id"], keep_mask, strict=False) if ok]
                        grads_to_add = data.get("gradient")[keep_mask] if "gradient" in data else None
                        conv_to_add = data["converged"][keep_mask]
                        wall_to_add = data["wall_s"][keep_mask]

                        target.add_points(
                            method_id=mid,
                            coords=coords_to_add,
                            energies=energies_to_add,
                            point_ids=pids_to_add,
                            gradients=grads_to_add,
                            converged=conv_to_add,
                            wall_s=wall_to_add,
                        )
                        total_merged += len(pids_to_add)
            except KeyError:
                continue

    logger.info(f"Successfully merged {total_merged} points across {len(shard_paths)} shards into {target_store_path}")
    return total_merged


# =============================================================================
# 8. COMMAND-LINE INTERFACE
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Builds comprehensive CLI parser for PES store management."""
    parser = argparse.ArgumentParser(
        description="CoChem Core PES Store: QCSchema HDF5, SWMR/Archival Bifurcation, & Isotopologue Recycling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # info
    p_info = subparsers.add_parser("info", help="Display summary information for a PESStore HDF5 file")
    p_info.add_argument("path", help="Path to HDF5 store file")

    # todo
    p_todo = subparsers.add_parser("todo", help="Check missing points on a grid")
    p_todo.add_argument("path", help="Path to HDF5 store file")
    p_todo.add_argument("--method", required=True, help="Method ID")
    p_todo.add_argument("--grid", required=True, help="Grid ID")

    # merge
    p_merge = subparsers.add_parser("merge", help="Merge multiple HDF5 shards into a destination store")
    p_merge.add_argument("--target", required=True, help="Target master HDF5 path")
    p_merge.add_argument("shards", nargs="+", help="Input shard file paths")

    # recycle-isotopologues
    p_iso = subparsers.add_parser("recycle-isotopologues", help="Re-analyze a saved Hessian with isotopic substitutions")
    p_iso.add_argument("path", help="Path to HDF5 store file")
    p_iso.add_argument("--hessian-label", required=True, help="Registered Hessian label")
    p_iso.add_argument("--xyz", required=True, help="Path to reference XYZ geometry")

    return parser


def main() -> None:
    """Main CLI execution router."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if not args.subcommand or args.subcommand == "info":
        path = args.path if hasattr(args, "path") else get_state_file_path()
        store = PESStore(path)
        print("=" * 60)
        print(f"CoChem PES Store: {store.path}")
        print(f"Complex: {store.complex_name} | N_atoms: {store.n_atoms} | Symbols: {store.symbols}")
        print(f"Methods registered: {store.list_methods()}")
        print(f"Hessians stored: {store.list_hessians()}")
        print(f"Grids registered: {store.list_grids()}")
        print("Integrity Check:", store.validate_integrity())
        print("=" * 60)

    elif args.subcommand == "todo":
        store = PESStore(args.path)
        grid = store.get_grid(args.grid)
        shape = grid["shape"]
        total_pts = 1
        for dim in shape:
            total_pts *= dim
        wanted = [f"{args.grid}:{i}" for i in range(total_pts)]
        missing = store.todo(args.method, wanted)
        print(f"Grid '{args.grid}' has {total_pts} total points.")
        print(f"Method '{args.method}' has {len(missing)} points remaining to compute ({len(wanted) - len(missing)} completed).")

    elif args.subcommand == "merge":
        merged = merge_pes_shards(args.shards, args.target)
        print(f"Merged {merged} total points into {args.target}")

    elif args.subcommand == "recycle-isotopologues":
        store = PESStore(args.path)
        h_mat, h_attrs = store.get_hessian(args.hessian_label)
        # Parse XYZ
        xyz_p = Path(args.xyz)
        lines = xyz_p.read_text(encoding="utf-8").splitlines()
        n = int(lines[0].split()[0])
        syms: List[str] = []
        coords_list: List[List[float]] = []
        for ln in lines[2:2 + n]:
            parts = ln.split()
            syms.append(parts[0])
            coords_list.append([float(x) for x in parts[1:4]])
        coords_arr = np.asarray(coords_list, dtype=np.float64)

        # Standard test suite of common isotopologues
        iso_map: Dict[str, List[Optional[int]]] = {"parent": [None] * len(syms)}
        for i, s in enumerate(syms):
            clean_s = s.strip().capitalize()
            if clean_s == "C":
                m_list = [None] * len(syms)
                m_list[i] = 13
                iso_map[f"13C_atom_{i}"] = m_list
            elif clean_s == "O":
                m_list = [None] * len(syms)
                m_list[i] = 18
                iso_map[f"18O_atom_{i}"] = m_list
            elif clean_s == "H":
                m_list = [None] * len(syms)
                m_list[i] = 2
                iso_map[f"D_atom_{i}"] = m_list

        results = reanalyze_isotopologue_suite(h_mat, coords_arr, syms, iso_map, parent_label=args.hessian_label)
        print(f"Evaluated {len(results)} isotopologues from Hessian '{args.hessian_label}':")
        for k, v in results.items():
            store.add_isotopologue_result(args.hessian_label, v)
            print(f"  [{k}] A={v.A_MHz:.3f} MHz, B={v.B_MHz:.3f} MHz, C={v.C_MHz:.3f} MHz | Lowest Mode: {v.lowest_harmonic_mode_cm_inv:.2f} cm^-1")


if __name__ == "__main__":
    main()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_core_subprocess_broker.py ---
#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 3.0 - The Subprocess Broker
Implements: Cross-platform Process Isolation, Win32 Job Objects,
psutil Process Tree Tracking, 10-Second Grace Period Recursive Tree Killing,
atexit Zombie Reaper Daemon, Segfault & Access Violation 256-byte Hex-Dump Sweeper,
OOM Preemption Polling, ZeroMQ Heartbeat Publisher with CurveZMQ / IPC, NUMA-Aware CPU Pinning,
Pre-Flight Disk Quota & 64KB SHA-256 Binary Probe, RAM-Disk Overlay Routing, Directory Lockdown,
and Dead-Man's Switch Daemon Transition.

Provides `safe_subprocess_run`, `register_popen_process`, `unregister_popen_process`,
`get_active_popen_processes`, `cleanup_zombie_processes`, `kill_process_tree`,
`extract_segfault_hex_dump`, `sweep_crash_hex_dump`, `CPUTopologyManager`,
`RAMDiskOverlayManager`, `ZMQHeartbeatManager`, `DeadMansSwitchWatchdog`,
`WindowsJobObject`, `ZombieReaper`, and `SubprocessBroker`.
"""

from __future__ import annotations

import atexit
import ctypes
import hashlib
import json
import logging
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

if platform.system() == "Windows":
    from ctypes import wintypes

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

from cochem_base.core.exceptions import AirGapBoundaryError, SubprocessBrokerError

try:
    from cochem_base.exceptions import DiskQuotaError
except ImportError:
    class DiskQuotaError(OSError):  # type: ignore
        """Fallback definition for DiskQuotaError if cochem_base.exceptions is unavailable."""
        default_error_code = "DISK_QUOTA_EXCEEDED"

        def __init__(
            self,
            message: Optional[Union[str, float]] = None,
            error_code: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
            timestamp: Optional[str] = None,
            *,
            required_gb: Optional[float] = None,
            available_gb: Optional[float] = None,
            path: Optional[Union[str, Path]] = None,
            **kwargs: Any,
        ) -> None:
            self.required_gb: float = float(required_gb) if required_gb is not None else 50.0
            self.available_gb: float = float(available_gb) if available_gb is not None else 0.0
            self.path: Optional[Path] = Path(path) if path is not None else None
            p_str = str(self.path) if self.path is not None else "workspace"
            msg = message if isinstance(message, str) else (
                f"Insufficient scratch disk quota at {p_str}: "
                f"required {self.required_gb:.2f} GB, available {self.available_gb:.2f} GB"
            )
            super().__init__(msg)

from cochem_base.config_loader import (
    get_artifact_dir,
    get_ramdisk_dir,
    get_runtime_dir,
    resolve_mapped_path,
)

try:
    from core_engine.cochem_core_telemetry_logger import TelemetryLogger
except ImportError:
    try:
        from cochem_core_telemetry_logger import TelemetryLogger  # type: ignore
    except ImportError:
        TelemetryLogger = None  # type: ignore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-Broker")

# Global Popen process tracking for zombie sweeping
_GLOBAL_ACTIVE_POPEN_PROCESSES: List[subprocess.Popen] = []
_GLOBAL_TRACKING_LOCK = threading.RLock()

# Comprehensive cross-platform segmentation fault, abort, access violation, and fatal crash return codes
CRITICAL_SEGFAULT_EXIT_CODES = {
    139, 134, 135, 136,                   # POSIX SIGSEGV, SIGABRT, SIGBUS, SIGFPE (128 + signal)
    -11, -6, -7, -8,                       # Subprocess negative signal numbers
    0xC0000005, -1073741819,  # Windows STATUS_ACCESS_VIOLATION (unsigned & signed 32-bit)
    0xC00000FD, -1073741571,  # Windows STATUS_STACK_OVERFLOW
    0xC000001D, -1073741795,  # Windows STATUS_ILLEGAL_INSTRUCTION
    0xC000002E, -1073741778,  # Windows STATUS_DATATYPE_MISALIGNMENT
}


# =====================================================================
# Segfault & Access Violation Hex-Dump Sweeper
# =====================================================================

def is_crash_returncode(code: Optional[int]) -> bool:
    """Evaluates whether an exit code corresponds to a critical crash, segfault, or access violation."""
    if code is None:
        return False
    if code in CRITICAL_SEGFAULT_EXIT_CODES:
        return True
    try:
        unsigned_code = code & 0xFFFFFFFF
        if unsigned_code in {0xC0000005, 0xC00000FD, 0xC000001D, 0xC000002E}:
            return True
    except Exception:
        pass
    return False


def extract_segfault_hex_dump(
    returncode: int,
    stderr_buffer: Union[str, bytes, bytearray, Sequence[str], None],
    max_bytes: int = 256,
) -> Dict[str, Any]:
    """Sweeps terminal stderr buffer upon process segfault or access violation.

    Extracts the final 256 bytes, generates both a canonical formatted hex dump and
    a raw hexadecimal trace string, and structures the diagnostic payload for JSON-L telemetry.
    """
    is_crash = is_crash_returncode(returncode)
    if not is_crash:
        return {
            "is_crash": False,
            "returncode": returncode,
            "crash_type": None,
            "raw_hex": "",
            "formatted_hex_dump": "",
            "byte_count": 0,
            "terminal_stderr_snippet": "",
        }

    raw_bytes: bytes
    if stderr_buffer is None:
        raw_bytes = b"Segmentation fault / Access violation (core dumped)\n"
    elif isinstance(stderr_buffer, (bytes, bytearray)):
        raw_bytes = bytes(stderr_buffer)
    elif isinstance(stderr_buffer, str):
        raw_bytes = stderr_buffer.encode("utf-8", errors="replace")
    elif isinstance(stderr_buffer, (list, tuple)):
        joined_str = "\n".join(str(line) for line in stderr_buffer)
        raw_bytes = joined_str.encode("utf-8", errors="replace")
    else:
        raw_bytes = str(stderr_buffer).encode("utf-8", errors="replace")

    if not raw_bytes:
        raw_bytes = b"Segmentation fault / Access violation (core dumped)\n"

    target_bytes = raw_bytes[-max_bytes:] if len(raw_bytes) >= max_bytes else raw_bytes
    raw_hex = target_bytes.hex()

    # Build canonical formatted hex dump
    lines: List[str] = []
    for offset in range(0, len(target_bytes), 16):
        chunk = target_bytes[offset:offset + 16]
        hex_parts = [f"{b:02x}" for b in chunk]
        hex_str = " ".join(hex_parts)
        ascii_chars = [chr(b) if 32 <= b <= 126 else "." for b in chunk]
        ascii_str = "".join(ascii_chars)
        lines.append(f"{offset:08x}:  {hex_str:<48}  |{ascii_str}|")

    formatted_hex_dump = "\n".join(lines)

    # Classify crash type
    crash_type = "CRITICAL_CRASH"
    if returncode in (-1073741819, 3221225477, 0xC0000005):
        crash_type = "STATUS_ACCESS_VIOLATION"
    elif returncode in (139, -11):
        crash_type = "SIGSEGV"
    elif returncode in (134, -6):
        crash_type = "SIGABRT"
    elif returncode in (-1073741571, 3221225725, 0xC00000FD):
        crash_type = "STATUS_STACK_OVERFLOW"
    elif returncode in (-1073741795, 3221225501, 0xC000001D):
        crash_type = "STATUS_ILLEGAL_INSTRUCTION"
    elif returncode in (-1073741778, 3221225518, 0xC000002E):
        crash_type = "STATUS_DATATYPE_MISALIGNMENT"

    return {
        "is_crash": True,
        "returncode": returncode,
        "crash_type": crash_type,
        "raw_hex": raw_hex,
        "formatted_hex_dump": formatted_hex_dump,
        "byte_count": len(target_bytes),
        "terminal_stderr_snippet": target_bytes.decode("utf-8", errors="replace"),
    }


# Dedicated alias for total naming consistency
sweep_crash_hex_dump = extract_segfault_hex_dump


# =====================================================================
# Win32 Job Object Definitions (Windows-only)
# =====================================================================

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001
PROCESS_ALL_ACCESS = 0x1F0FFF


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
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


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


class WindowsJobObject:
    """Encapsulates a Win32 Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.

    Guarantees OS-level atomic termination of all child and spawned grandchild
    processes when the job object handle is closed or the parent terminates.
    """

    def __init__(self, kill_on_close: bool = True) -> None:
        self.handle: Optional[int] = None
        self._is_windows = platform.system() == "Windows"
        if not self._is_windows:
            return

        try:
            self.handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
            if not self.handle:
                logger.warning("Failed to create Win32 Job Object.")
                return

            if kill_on_close:
                info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                res = ctypes.windll.kernel32.SetInformationJobObject(
                    self.handle,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
                if not res:
                    logger.warning("Failed to set JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE on Job Object.")
        except Exception as exc:
            logger.warning(f"Error initializing WindowsJobObject: {exc}")
            self.handle = None

    def assign_pid(self, pid: int) -> bool:
        """Assigns an active process PID to the Win32 Job Object."""
        if not self._is_windows or not self.handle:
            return False
        try:
            proc_handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_SET_QUOTA | PROCESS_TERMINATE,
                False,
                pid,
            )
            if not proc_handle:
                proc_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not proc_handle:
                return False

            res = ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, proc_handle)
            ctypes.windll.kernel32.CloseHandle(proc_handle)
            return bool(res)
        except Exception as exc:
            logger.debug(f"Failed to assign PID {pid} to Job Object: {exc}")
            return False

    def assign_popen(self, proc: subprocess.Popen) -> bool:
        """Assigns a subprocess.Popen instance to the Win32 Job Object."""
        return self.assign_pid(proc.pid)

    def set_kill_on_close(self, enable: bool = True) -> bool:
        """Dynamically enables or disables JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE on the Job Object."""
        if not self._is_windows or not self.handle:
            return False
        try:
            info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE if enable else 0
            res = ctypes.windll.kernel32.SetInformationJobObject(
                self.handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            return bool(res)
        except Exception as exc:
            logger.debug(f"Failed to update Job Object limit flags: {exc}")
            return False

    def close(self) -> None:
        """Closes the Job Object handle, terminating all assigned processes if kill_on_close is set."""
        if self._is_windows and self.handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            self.handle = None

    def __enter__(self) -> WindowsJobObject:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# =====================================================================
# Process Tracking and Zombie Reaper
# =====================================================================

def get_active_popen_processes() -> List[subprocess.Popen]:
    """Returns a list of currently running subprocess.Popen processes tracked globally."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        _GLOBAL_ACTIVE_POPEN_PROCESSES = [p for p in _GLOBAL_ACTIVE_POPEN_PROCESSES if p.poll() is None]
        return list(_GLOBAL_ACTIVE_POPEN_PROCESSES)


def register_popen_process(proc: subprocess.Popen) -> None:
    """Registers a Popen child process for automatic zombie cleanup on script exit."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        _GLOBAL_ACTIVE_POPEN_PROCESSES = [p for p in _GLOBAL_ACTIVE_POPEN_PROCESSES if p.poll() is None]
        if proc.poll() is None and proc not in _GLOBAL_ACTIVE_POPEN_PROCESSES:
            _GLOBAL_ACTIVE_POPEN_PROCESSES.append(proc)


def unregister_popen_process(proc: subprocess.Popen) -> None:
    """Unregisters a Popen child process from global tracking."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        if proc in _GLOBAL_ACTIVE_POPEN_PROCESSES:
            _GLOBAL_ACTIVE_POPEN_PROCESSES.remove(proc)


def kill_process_tree(pid: int, timeout: float = 10.0) -> None:
    """Terminates a process and all of its recursive child processes.

    Mathematically guarantees no orphaned process trees survive:
    1. Uses psutil recursive tree discovery (parent.children(recursive=True)).
    2. Sends graceful terminate signal (.terminate()) to all children and parent.
    3. Waits for a 10-second grace period (allowing .gbw caches to dump cleanly).
    4. Escalates to hard kill (.kill()) if any process remains alive after timeout.
    5. Performs final reap wait.
    """
    if HAS_PSUTIL:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                parent.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            procs_to_wait = [p for p in children + [parent] if psutil.pid_exists(p.pid)]
            if procs_to_wait:
                gone, alive = psutil.wait_procs(procs_to_wait, timeout=timeout)
                if alive:
                    for p in alive:
                        try:
                            p.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    # Final reap confirmation
                    psutil.wait_procs(alive, timeout=3.0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except (ProcessLookupError, PermissionError, OSError):
            pass
    else:
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(min(timeout, 0.5))
                    sig_kill = getattr(signal, "SIGKILL", signal.SIGTERM)
                    os.kill(pid, sig_kill)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
        except (ProcessLookupError, PermissionError, OSError):
            pass


def cleanup_zombie_processes() -> int:
    """Atexit / Signal hook to terminate any dangling Popen child process trees."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    count = 0
    with _GLOBAL_TRACKING_LOCK:
        active_list = list(_GLOBAL_ACTIVE_POPEN_PROCESSES)
        _GLOBAL_ACTIVE_POPEN_PROCESSES.clear()

    for proc in active_list:
        if proc.poll() is None:
            try:
                pid = proc.pid
                kill_process_tree(pid, timeout=10.0)
                count += 1
                logger.info(f"Terminated background child process PID {pid}")
            except (ProcessLookupError, PermissionError, OSError) as e:
                logger.warning(f"Failed to terminate process PID {proc.pid}: {e}")
    return count


class ZombieReaper:
    """Global and instance zombie sweeper with signal handlers and Win32 Job Object integration."""

    @staticmethod
    def reap_all() -> int:
        """Invokes global process cleanup."""
        return cleanup_zombie_processes()

    @staticmethod
    def reap_pid(pid: int, timeout: float = 10.0) -> None:
        """Kills a specific process tree with 10-second grace period."""
        kill_process_tree(pid, timeout=timeout)


def _signal_cleanup_handler(signum: int, frame: Any) -> None:
    logger.info(f"Received signal {signum}. Triggering zombie reaper cleanup...")
    cleanup_zombie_processes()
    sys.exit(128 + signum)


def _register_signal_handlers() -> None:
    try:
        if threading.current_thread() is threading.main_thread():
            for sig_name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
                if hasattr(signal, sig_name):
                    sig = getattr(signal, sig_name)
                    try:
                        signal.signal(sig, _signal_cleanup_handler)
                    except (ValueError, OSError, RuntimeError):
                        pass
    except Exception:
        pass


atexit.register(cleanup_zombie_processes)
_register_signal_handlers()


# =====================================================================
# NUMA-Aware Hardware Thread-Pinning & Oversubscription Prevention
# =====================================================================

def detect_cpu_topology() -> Dict[str, Any]:
    """Evaluates physical host CPU topology (cores, sockets, NUMA nodes).

    Returns a structured dictionary containing logical cores, physical cores,
    sockets, NUMA nodes with mapped CPU core IDs, and multi-threading ratio.
    """
    logical_cores = psutil.cpu_count(logical=True) if HAS_PSUTIL else (os.cpu_count() or 1)
    physical_cores = (psutil.cpu_count(logical=False) if HAS_PSUTIL else None) or logical_cores

    numa_nodes: List[Dict[str, Any]] = []
    sockets = 1

    if platform.system() == "Linux":
        node_dir = Path("/sys/devices/system/node")
        if node_dir.is_dir():
            for entry in sorted(node_dir.glob("node[0-9]*")):
                try:
                    node_id = int(entry.name.replace("node", ""))
                    cpulist_file = entry / "cpulist"
                    cpus: List[int] = []
                    if cpulist_file.exists():
                        raw = cpulist_file.read_text(encoding="utf-8").strip()
                        for part in raw.split(","):
                            if "-" in part:
                                start, end = map(int, part.split("-"))
                                cpus.extend(range(start, end + 1))
                            elif part.isdigit():
                                cpus.append(int(part))
                    numa_nodes.append({"node_id": node_id, "cpus": cpus})
                except Exception:
                    pass
            if numa_nodes:
                sockets = max(1, len(numa_nodes))

    elif platform.system() == "Windows":
        try:
            highest_node = wintypes.ULONG()
            if ctypes.windll.kernel32.GetNumaHighestNodeNumber(ctypes.byref(highest_node)):
                total_nodes = highest_node.value + 1
                sockets = max(1, total_nodes)
                cores_per_node = max(1, logical_cores // total_nodes)
                for nid in range(total_nodes):
                    node_cpus = list(range(nid * cores_per_node, min(logical_cores, (nid + 1) * cores_per_node)))
                    numa_nodes.append({"node_id": nid, "cpus": node_cpus})
        except Exception:
            pass

    if not numa_nodes:
        numa_nodes.append({"node_id": 0, "cpus": list(range(logical_cores))})
        sockets = 1

    return {
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
        "sockets": sockets,
        "numa_nodes": numa_nodes,
        "is_numa": len(numa_nodes) > 1,
        "threads_per_core": max(1, logical_cores // max(1, physical_cores)),
    }


class CPUTopologyManager:
    """Evaluates physical host topology (cores, sockets, NUMA nodes) and manages core allocations."""

    def __init__(self, topology: Optional[Dict[str, Any]] = None) -> None:
        self.topology = topology or detect_cpu_topology()
        self.logical_cores: int = self.topology.get("logical_cores", 1)
        self.physical_cores: int = self.topology.get("physical_cores", 1)
        self.sockets: int = self.topology.get("sockets", 1)
        self.numa_nodes: List[Dict[str, Any]] = self.topology.get("numa_nodes", [])
        self.is_numa: bool = self.topology.get("is_numa", False)

    def get_topology(self) -> Dict[str, Any]:
        """Returns cached CPU topology specification."""
        return dict(self.topology)

    def get_numa_node_for_core(self, core_id: int) -> int:
        """Determines the NUMA node index for a given CPU core."""
        for node in self.numa_nodes:
            if core_id in node.get("cpus", []):
                return int(node.get("node_id", 0))
        return 0

    def allocate_cores(self, count: int, numa_node: Optional[int] = None) -> List[int]:
        """Allocates contiguous CPU cores respecting NUMA node boundaries."""
        if numa_node is not None:
            for node in self.numa_nodes:
                if node.get("node_id") == numa_node:
                    cpus: List[int] = list(node.get("cpus", []))
                    return cpus[:count] if count <= len(cpus) else cpus
        all_cpus: List[int] = [c for node in self.numa_nodes for c in node.get("cpus", [])]
        if not all_cpus:
            all_cpus = list(range(self.logical_cores))
        return all_cpus[:count]

    def pin_process(self, pid: int, cpu_cores: Optional[List[int]] = None) -> bool:
        """Pins an active process to designated CPU cores."""
        return enforce_cpu_affinity(pid, cpu_cores)

    def calculate_thread_affinity(self, rank: int, threads_per_rank: int) -> List[int]:
        """Calculates thread pinning offsets for multi-rank execution."""
        start_core = (rank * threads_per_rank) % max(1, self.logical_cores)
        return [(start_core + i) % self.logical_cores for i in range(threads_per_rank)]


def enforce_cpu_affinity(pid: int, cpu_cores: Optional[List[int]] = None) -> bool:
    """Pins a process to specified CPU cores using OS-level affinity control.

    Gracefully handles macOS Darwin (which does not support process CPU affinity)
    and Windows processor group constraints without raising unhandled exceptions.
    """
    if cpu_cores is None or len(cpu_cores) == 0:
        return True
    if not HAS_PSUTIL:
        logger.warning("psutil unavailable; cannot enforce CPU affinity.")
        return False
    try:
        proc = psutil.Process(pid)
        proc.cpu_affinity(cpu_cores)
        logger.info(f"Pinned PID {pid} to CPU cores {cpu_cores} [M]")
        return True
    except (AttributeError, NotImplementedError):
        logger.debug(f"CPU affinity control is not supported on this platform ({platform.system()}).")
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError) as e:
        logger.warning(f"Failed to set CPU affinity on PID {pid}: {e}")
        return False


def build_thread_affinity_env(
    cores: Optional[Sequence[int]] = None,
    is_scout: bool = False,
    num_mps_ranks: Optional[int] = None,
    mps_mem_limit_mb: Optional[int] = None,
    base_env: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Constructs an environment dictionary with proactive OpenMP/MKL thread affinity
    and NVIDIA Multi-Process Service (MPS) mediation settings.

    Mandated by Suggestion #19 and Method Matrix §8A.1 Scout-and-Anchor policy:
    - Pre-injects GOMP_CPU_AFFINITY, KMP_AFFINITY, OMP_PLACES, OMP_PROC_BIND.
    - Zero CUDA-Locking MPS parameters: CUDA_MPS_ACTIVE_THREAD_PERCENTAGE,
      CUDA_MPS_PINNED_DEVICE_MEM_LIMIT.
    """
    env = dict(base_env if base_env is not None else os.environ)

    if cores is not None and len(cores) > 0:
        core_list = [int(c) for c in cores]
        core_str = ",".join(str(c) for c in core_list)
        env["GOMP_CPU_AFFINITY"] = core_str
        env["KMP_AFFINITY"] = f"explicit,proclist=[{core_str}],granularity=fine"
        env["OMP_PLACES"] = ",".join(f"{{{c}}}" for c in core_list)
        env["OMP_PROC_BIND"] = "close"

    if num_mps_ranks is not None and num_mps_ranks > 0:
        pct = max(1, int(100 / num_mps_ranks))
        env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(pct)

    if mps_mem_limit_mb is not None and mps_mem_limit_mb > 0:
        env["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = f"{int(mps_mem_limit_mb)}M"

    return env


def detect_mpi_environment(
    env: Optional[Dict[str, str]] = None,
    cmd: Optional[Union[str, List[str]]] = None,
) -> bool:
    """Detects if an OpenMPI, MPICH, SLURM, or ORCA multi-rank MPI environment is active."""
    target_env = env if env is not None else os.environ

    mpi_size_vars = ("OMPI_COMM_WORLD_SIZE", "PMI_SIZE", "SLURM_NTASKS", "MPI_SIZE", "OMPI_UNIVERSE_SIZE", "MV2_COMM_WORLD_SIZE")
    for var in mpi_size_vars:
        val = target_env.get(var)
        if val is not None:
            try:
                if int(val) > 1:
                    return True
            except ValueError:
                pass

    mpi_rank_indicators = ("MPI_LOCALRANKID", "OMPI_COMM_WORLD_RANK", "PMI_RANK", "PMIX_RANK", "SLURM_PROCID")
    for var in mpi_rank_indicators:
        if var in target_env:
            return True

    mpirun_in_use = target_env.get("MPIRUN_IN_USE", "").strip().lower()
    if mpirun_in_use in ("1", "true", "yes"):
        return True

    if cmd is not None:
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        cmd_lower = cmd_str.lower()
        mpi_executables = ("mpirun", "mpiexec", "orterun", "srun", "aprun", "oshrun")
        for mpi_bin in mpi_executables:
            parts = cmd_lower.split()
            if mpi_bin in parts or any(part.endswith(f"/{mpi_bin}") or part.endswith(f"\\{mpi_bin}") or part.endswith(f"/{mpi_bin}.exe") or part.endswith(f"\\{mpi_bin}.exe") for part in parts):
                return True
        if "%pal" in cmd_lower or "nprocs" in cmd_lower:
            return True

    return False


def sanitize_mpi_environment(
    env: Optional[Dict[str, str]] = None,
    force_single_thread: bool = False,
    cmd: Optional[Union[str, List[str]]] = None,
) -> Dict[str, str]:
    """Sanitizes environment variables for MPI workloads to prevent core oversubscription.

    When multi-rank MPI execution is detected or force_single_thread is True, forces:
    OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
    VECLIB_MAXIMUM_THREADS="1", NUMEXPR_NUM_THREADS="1", BLIS_NUM_THREADS="1".
    """
    target_env = dict(env) if env is not None else os.environ.copy()

    if force_single_thread or detect_mpi_environment(target_env, cmd=cmd):
        target_env["OMP_NUM_THREADS"] = "1"
        target_env["MKL_NUM_THREADS"] = "1"
        target_env["OPENBLAS_NUM_THREADS"] = "1"
        target_env["VECLIB_MAXIMUM_THREADS"] = "1"
        target_env["NUMEXPR_NUM_THREADS"] = "1"
        target_env["BLIS_NUM_THREADS"] = "1"
        logger.info("Sanitized MPI environment: forced OMP/MKL/OPENBLAS/VECLIB/NUMEXPR/BLIS=1 to prevent oversubscription.")

    return target_env


# =====================================================================
# Pre-Flight Disk Quota, 64KB SHA-256 Probe & RAM-Disk Routing
# =====================================================================

def lock_directory_permissions(target_dir: Union[str, Path]) -> bool:
    """Applies strict directory access controls: chmod 0o700 on POSIX or icacls on Windows."""
    path = Path(target_dir).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"Could not create directory {path} to lock permissions: {exc}")
            return False

    if platform.system() != "Windows":
        try:
            os.chmod(str(path), 0o700)
            return True
        except OSError as exc:
            logger.warning(f"Failed to chmod 0o700 on {path}: {exc}")
            return False
    else:
        try:
            username = os.environ.get("USERNAME") or os.environ.get("USER") or "Everyone"
            cmd = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(OI)(CI)F"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5.0)
            return res.returncode == 0
        except Exception as exc:
            logger.warning(f"Failed to lock Windows ACLs on {path}: {exc}")
            return False


_SCRATCH_CACHE_LOCK = threading.Lock()
_SCRATCH_VERIFICATION_CACHE: Dict[Path, float] = {}


def verify_scratch_quota_and_io(
    target_dir: Union[str, Path],
    required_gb: Optional[float] = None,
    ttl_seconds: float = 300.0,
    force: bool = False,
) -> bool:
    """Verifies write, fsync, and SHA-256 read-back integrity on target_dir.

    Caches verification success for ttl_seconds to eliminate 20-100 ms dispatch latency per subprocess [M].
    Enforces Tripartite Air-Gap: target_dir must strictly reside within Tier 3 ($COCH_SCRATCH).
    """
    resolved = Path(target_dir).resolve()

    # Air-gap boundary validation
    src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
    data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()
    if src_dir.exists() and (src_dir == resolved or src_dir in resolved.parents):
        raise AirGapBoundaryError(
            f"Cannot execute subprocess scratch operations in read-only Tier 1 ($COCH_SRC): {resolved}",
            details={"path": str(resolved), "tier": "Tier 1"},
        )
    if data_dir.exists() and (data_dir == resolved or data_dir in resolved.parents):
        raise AirGapBoundaryError(
            f"Cannot execute subprocess scratch operations in immutable Tier 2 ($COCH_DATA): {resolved}",
            details={"path": str(resolved), "tier": "Tier 2"},
        )

    now = time.monotonic()
    with _SCRATCH_CACHE_LOCK:
        if not force and resolved in _SCRATCH_VERIFICATION_CACHE:
            last_verified = _SCRATCH_VERIFICATION_CACHE[resolved]
            if (now - last_verified) < ttl_seconds:
                return True

    resolved.mkdir(parents=True, exist_ok=True)

    if required_gb is not None and required_gb > 0:
        usage = shutil.disk_usage(str(resolved))
        free_gb = usage.free / (1024 ** 3)
        if free_gb < required_gb:
            logger.error(f"Insufficient scratch disk space at {resolved}: {free_gb:.2f} GB free, {required_gb:.2f} GB required.")
            raise DiskQuotaError(required_gb=required_gb, available_gb=free_gb, path=resolved)

    probe_file = resolved / f".cochem_io_probe_{os.getpid()}_{time.time_ns()}.bin"
    probe_data = os.urandom(64 * 1024)  # 64 KB physical binary probe
    expected_hash = hashlib.sha256(probe_data).hexdigest()

    try:
        with open(probe_file, "wb") as f:
            f.write(probe_data)
            f.flush()
            os.fsync(f.fileno())

        with open(probe_file, "rb") as f:
            read_back_data = f.read()

        read_hash = hashlib.sha256(read_back_data).hexdigest()

        if expected_hash != read_hash:
            raise SubprocessBrokerError(
                f"Scratch I/O integrity probe failed: SHA-256 mismatch in {resolved}",
                details={"scratch_dir": str(resolved), "expected": expected_hash, "actual": read_hash},
            )

        with _SCRATCH_CACHE_LOCK:
            _SCRATCH_VERIFICATION_CACHE[resolved] = time.monotonic()

        logger.info(f"Verified scratch quota and I/O at {resolved} [M]")
        return True
    except (OSError, IOError) as exc:
        if not isinstance(exc, (DiskQuotaError, SubprocessBrokerError, AirGapBoundaryError)):
            logger.error(f"Scratch I/O verification error at {resolved}: {exc}")
        raise
    finally:
        if probe_file.exists():
            try:
                probe_file.unlink()
            except OSError:
                pass


def verify_scratch_io(scratch_dir: Union[str, Path], required_mb: int = 100) -> bool:
    """Backward-compatible scratch I/O verification wrapper."""
    required_gb = required_mb / 1024.0
    try:
        return verify_scratch_quota_and_io(scratch_dir, required_gb=required_gb)
    except (DiskQuotaError, IOError, OSError):
        return False


class RAMDiskOverlayManager:
    """Manages high-speed RAM-disk execution overlays and quantum artifact provenance synchronization."""

    def __init__(self, threshold_ram_gb: float = 128.0) -> None:
        self.threshold_ram_gb = threshold_ram_gb

    def get_total_host_ram_gb(self) -> float:
        """Returns physical host memory in Gigabytes."""
        if HAS_PSUTIL:
            total_bytes: float = float(psutil.virtual_memory().total)
            return float(total_bytes / (1024 ** 3))
        return 0.0

    def is_ramdisk_eligible(self, min_ram_gb: Optional[float] = None) -> bool:
        """Checks if host RAM exceeds the minimum provisioning threshold."""
        threshold = min_ram_gb if min_ram_gb is not None else self.threshold_ram_gb
        return self.get_total_host_ram_gb() >= threshold

    def provision_overlay(
        self,
        job_name: str,
        required_gb: float = 4.0,
        min_ram_gb: Optional[float] = None,
        fallback_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Autonomously provisions a high-speed RAM-disk overlay directory if eligible."""
        threshold = min_ram_gb if min_ram_gb is not None else self.threshold_ram_gb
        target_fallback = Path(fallback_dir).resolve() if fallback_dir is not None else (get_artifact_dir() / "Scratch")

        if self.is_ramdisk_eligible(threshold):
            ramdisk_path = get_ramdisk_dir()
            if ramdisk_path is not None and ramdisk_path.is_dir():
                try:
                    free_gb = shutil.disk_usage(str(ramdisk_path)).free / (1024 ** 3)
                    if free_gb > (required_gb * 1.2):
                        job_overlay_dir = ramdisk_path / f"cochem_{job_name}_{int(time.time() * 1000)}"
                        job_overlay_dir.mkdir(parents=True, exist_ok=True)
                        lock_directory_permissions(job_overlay_dir)
                        logger.info(
                            f"Provisioned RAM-disk execution directory: {job_overlay_dir} "
                            f"(Host RAM: {self.get_total_host_ram_gb():.1f} GB >= {threshold} GB)"
                        )
                        return job_overlay_dir
                except Exception as exc:
                    logger.debug(f"RAM-disk overlay check skipped: {exc}")

        target_fallback.mkdir(parents=True, exist_ok=True)
        lock_directory_permissions(target_fallback)
        return target_fallback

    def sync_and_cleanup(self, overlay_path: Path, permanent_path: Path) -> Dict[str, str]:
        """Synchronizes quantum artifacts from overlay back to permanent workspace and deletes overlay."""
        permanent_path.mkdir(parents=True, exist_ok=True)
        hashes: Dict[str, str] = {}

        if overlay_path != permanent_path and overlay_path.exists():
            logger.info(f"Syncing artifacts from RAM-disk {overlay_path} to permanent workspace {permanent_path}...")
            for item in overlay_path.iterdir():
                dest_path = permanent_path / item.name
                try:
                    if item.is_dir():
                        shutil.copytree(item, dest_path, dirs_exist_ok=True)
                    elif item.is_file():
                        shutil.copy2(item, dest_path)
                except Exception as exc:
                    logger.warning(f"Error copying artifact {item} to {dest_path}: {exc}")

            hashes = self.hash_artifacts(permanent_path)
            shutil.rmtree(overlay_path, ignore_errors=True)
        else:
            hashes = self.hash_artifacts(permanent_path)

        return hashes

    @staticmethod
    def hash_artifacts(target_dir: Path) -> Dict[str, str]:
        """Generates SHA-256 checksums for quantum chemistry artifacts."""
        hashes: Dict[str, str] = {}
        if not target_dir.exists():
            return hashes

        valid_suffixes = {".out", ".gbw", ".xyz", ".log", ".dat", ".json", ".h5", ".molden", ".cube"}
        for file_path in sorted(target_dir.iterdir()):
            if file_path.is_file() and (file_path.suffix in valid_suffixes or file_path.name.endswith(".out")):
                try:
                    hasher = hashlib.sha256()
                    with open(file_path, "rb") as f:
                        while chunk := f.read(65536):
                            hasher.update(chunk)
                    file_hash = hasher.hexdigest()
                    hashes[file_path.name] = file_hash
                    logger.info(f"Generated SHA-256 hash for {file_path.name}: {file_hash} [M]")
                except OSError as err:
                    logger.warning(f"Failed to hash {file_path.name}: {err}")
        return hashes


# =====================================================================
# ZeroMQ Heartbeat Integration & Dead-Man's Switch Watchdog
# =====================================================================

class ZMQHeartbeatManager:
    """ZeroMQ heartbeat publisher with CurveZMQ security on Windows and IPC on POSIX."""

    def __init__(self, job_id: str = "cochem_job") -> None:
        self.job_id = job_id
        self.endpoint: Optional[str] = None
        self.server_public: Optional[bytes] = None
        self.server_secret: Optional[bytes] = None
        self.client_public: Optional[bytes] = None
        self.client_secret: Optional[bytes] = None
        self.curve_enabled: bool = False

        self._context: Optional[Any] = None
        self._socket: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(
        self,
        endpoint: Optional[str] = None,
        interval_sec: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        use_curve: bool = True,
    ) -> str:
        """Binds and starts the background heartbeat publisher."""
        if not HAS_ZMQ:
            logger.warning("ZeroMQ (pyzmq) not available. Heartbeat publisher disabled.")
            return ""

        self.stop()
        self._stop_event.clear()

        try:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.PUB)

            if endpoint is None:
                if platform.system() == "Windows":
                    if use_curve and hasattr(zmq, "curve_keypair"):
                        try:
                            self.server_public, self.server_secret = zmq.curve_keypair()
                            self.client_public, self.client_secret = zmq.curve_keypair()
                            self._socket.curve_secretkey = self.server_secret
                            self._socket.curve_publickey = self.server_public
                            self._socket.curve_server = True
                            self.curve_enabled = True
                        except Exception as curve_err:
                            logger.debug(f"CurveZMQ initialization fallback: {curve_err}")
                            self.curve_enabled = False

                    port = self._socket.bind_to_random_port("tcp://127.0.0.1")
                    self.endpoint = f"tcp://127.0.0.1:{port}"
                else:
                    try:
                        ipc_dir = get_runtime_dir() / "ipc"
                    except Exception:
                        ipc_dir = Path(tempfile.gettempdir()) / "cochem_ipc"
                    ipc_dir.mkdir(parents=True, exist_ok=True)
                    lock_directory_permissions(ipc_dir)
                    ipc_path = ipc_dir / f"cochem_heartbeat_{self.job_id}.ipc"
                    self.endpoint = f"ipc://{ipc_path}"
                    try:
                        self._socket.bind(self.endpoint)
                    except Exception:
                        port = self._socket.bind_to_random_port("tcp://127.0.0.1")
                        self.endpoint = f"tcp://127.0.0.1:{port}"
            else:
                if endpoint.endswith(":*"):
                    base = endpoint[:-2]
                    port = self._socket.bind_to_random_port(base)
                    self.endpoint = f"{base}:{port}"
                else:
                    self.endpoint = endpoint
                    self._socket.bind(self.endpoint)

        except Exception as err:
            logger.error(f"Failed to bind ZeroMQ heartbeat publisher socket: {err}", exc_info=True)
            self.stop()
            return ""

        def heartbeat_worker() -> None:
            while not self._stop_event.is_set():
                alive_payload: Dict[str, Any] = {
                    "status": "alive",
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                    "job_id": self.job_id,
                    "metadata": metadata or {},
                }
                try:
                    if self._socket is not None:
                        self._socket.send_multipart([
                            b"heartbeat",
                            json.dumps(alive_payload).encode("utf-8"),
                        ])
                except Exception as ex:
                    logger.debug(f"ZeroMQ heartbeat send error: {ex}")
                self._stop_event.wait(interval_sec)

        self._thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self._thread.start()
        logger.info(f"ZeroMQ heartbeat publisher active on {self.endpoint} (Curve: {self.curve_enabled}) [M]")
        return str(self.endpoint)

    def publish_heartbeat(self, status: str = "alive", extra: Optional[Dict[str, Any]] = None) -> None:
        """Publishes an immediate manual heartbeat event."""
        if not HAS_ZMQ or self._socket is None:
            return
        payload = {
            "status": status,
            "timestamp": time.time(),
            "pid": os.getpid(),
            "job_id": self.job_id,
            "metadata": extra or {},
        }
        try:
            self._socket.send_multipart([
                b"heartbeat",
                json.dumps(payload).encode("utf-8"),
            ])
        except Exception as ex:
            logger.debug(f"Manual heartbeat publish error: {ex}")

    def stop(self) -> None:
        """Stops the heartbeat publisher thread and destroys sockets cleanly."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._socket is not None:
            try:
                self._socket.close(linger=0)
            except Exception:
                pass
            self._socket = None
        if self._context is not None:
            try:
                self._context.term()
            except Exception:
                pass
            self._context = None

    def __enter__(self) -> ZMQHeartbeatManager:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


class DeadMansSwitchWatchdog:
    """Monitors child process responsiveness via timestamp pings."""

    def __init__(
        self,
        job_id: str,
        proc: subprocess.Popen,
        timeout: float = 60.0,
        check_interval: float = 2.0,
        on_timeout: str = "daemonize",
    ) -> None:
        self.job_id = job_id
        self.proc = proc
        self.timeout = timeout
        self.check_interval = check_interval
        self.on_timeout = on_timeout
        self.last_ping: float = time.time()
        self.is_daemonized: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def ping(self) -> None:
        """Resets the dead-man's switch expiration timer."""
        self.last_ping = time.time()

    def start(self) -> None:
        """Starts the background watchdog monitoring loop."""
        self._stop_event.clear()
        self.last_ping = time.time()

        def watchdog_loop() -> None:
            while not self._stop_event.is_set():
                if self.proc.poll() is not None:
                    break
                elapsed = time.time() - self.last_ping
                if elapsed > self.timeout:
                    logger.warning(
                        f"Dead-man's switch expired for job '{self.job_id}' "
                        f"(no activity for {elapsed:.1f}s > {self.timeout:.1f}s)."
                    )
                    if self.on_timeout == "daemonize":
                        self.is_daemonized = True
                        unregister_popen_process(self.proc)
                        logger.info(
                            f"Orchestrator safely detached; child PID {self.proc.pid} "
                            f"transitioned to active autonomous daemon [M]"
                        )
                    elif self.on_timeout == "kill":
                        logger.error(f"Terminating unresponsive job '{self.job_id}' (PID {self.proc.pid}).")
                        kill_process_tree(self.proc.pid, timeout=10.0)
                    break
                self._stop_event.wait(self.check_interval)

        self._thread = threading.Thread(target=watchdog_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the watchdog thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def __enter__(self) -> DeadMansSwitchWatchdog:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


# =====================================================================
# Safe Subprocess Execution
# =====================================================================

def safe_subprocess_run(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    timeout: float = 300.0,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None,
    cpu_affinity: Optional[List[int]] = None,
    required_disk_gb: Optional[float] = None,
    sanitize_mpi: bool = True,
    use_job_object: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Executes a subprocess safely with cross-platform process isolation.

    Relies on robust tracking of process trees via `psutil` (avoiding POSIX-exclusive os.setsid),
    Win32 Job Object binding on Windows, pre-flight disk quota assertion, hardware CPU affinity pinning,
    10-second grace period recursive tree termination upon timeout, and Segfault & Access Violation
    256-byte stderr hex-dump extraction.
    """
    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            raise FileNotFoundError(f"Subprocess working directory does not exist: {cwd_path}")
        cwd_str = str(cwd_path)
    else:
        cwd_str = None
        cwd_path = Path.cwd()

    verify_scratch_quota_and_io(cwd_path, required_gb=required_disk_gb, ttl_seconds=300.0, force=False)

    parsed_cmd: Union[List[str], str]
    if isinstance(cmd, str) and not kwargs.get("shell", False):
        if platform.system() == "Windows":
            parsed_cmd = cmd
        else:
            parsed_cmd = shlex.split(cmd, posix=True)
    else:
        parsed_cmd = cmd

    target_env = env.copy() if env is not None else os.environ.copy()
    if sanitize_mpi:
        target_env = sanitize_mpi_environment(target_env, cmd=parsed_cmd)

    if cpu_affinity is not None:
        target_env = build_thread_affinity_env(cores=cpu_affinity, base_env=target_env)

    popen_args: Dict[str, Any] = {
        "cwd": cwd_str,
        "env": target_env,
        "text": text,
        **kwargs,
    }
    if capture_output:
        popen_args["stdout"] = subprocess.PIPE
        popen_args["stderr"] = subprocess.PIPE

    job_obj = WindowsJobObject() if (use_job_object and platform.system() == "Windows") else None

    if job_obj is not None and platform.system() == "Windows":
        CREATE_SUSPENDED = 0x00000004
        popen_args["creationflags"] = popen_args.get("creationflags", 0) | CREATE_SUSPENDED
        proc = subprocess.Popen(parsed_cmd, **popen_args)
        register_popen_process(proc)
        job_obj.assign_popen(proc)
        try:
            ctypes.windll.ntdll.NtResumeProcess(int(proc._handle))
        except Exception:
            pass
    else:
        if platform.system() != "Windows":
            popen_args.setdefault("start_new_session", True)
            if platform.system() == "Linux":
                def _posix_pdeathsig() -> None:
                    try:
                        import ctypes
                        libc = ctypes.CDLL("libc.so.6")
                        PR_SET_PDEATHSIG = 1
                        SIGKILL = 9
                        libc.prctl(PR_SET_PDEATHSIG, SIGKILL)
                    except Exception:
                        pass
                popen_args.setdefault("preexec_fn", _posix_pdeathsig)

        proc = subprocess.Popen(parsed_cmd, **popen_args)
        register_popen_process(proc)

    if cpu_affinity is not None:
        enforce_cpu_affinity(proc.pid, cpu_affinity)

    stdout_data: Any = ""
    stderr_data: Any = ""

    try:
        stdout_data, stderr_data = proc.communicate(timeout=timeout)
        ret = proc.returncode

        crash_payload = extract_segfault_hex_dump(ret, stderr_data)
        if crash_payload.get("is_crash"):
            logger.error(
                f"Critical process crash detected ({crash_payload.get('crash_type')}, code {ret}):\n"
                f"{crash_payload.get('formatted_hex_dump')}"
            )

        completed = subprocess.CompletedProcess(args=cmd, returncode=ret, stdout=stdout_data, stderr=stderr_data)
        completed.crash_payload = crash_payload  # type: ignore[attr-defined]
        completed.hex_dump = crash_payload.get("raw_hex", "")  # type: ignore[attr-defined]

        if check and ret != 0:
            err = subprocess.CalledProcessError(ret, cmd, output=stdout_data, stderr=stderr_data)
            err.crash_payload = crash_payload  # type: ignore[attr-defined]
            err.hex_dump = crash_payload.get("raw_hex", "")  # type: ignore[attr-defined]
            raise err

        return completed
    except subprocess.TimeoutExpired:
        kill_process_tree(proc.pid, timeout=10.0)
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            pass
        logger.error(f"Subprocess '{cmd}' timed out after {timeout} seconds.")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess '{cmd}' failed with returncode {e.returncode}: {e.stderr}")
        raise
    except OSError as e:
        logger.error(f"Subprocess execution error for '{cmd}': {e}")
        raise
    finally:
        unregister_popen_process(proc)
        if job_obj is not None:
            job_obj.close()


# =====================================================================
# Subprocess Broker Core Engine
# =====================================================================

class SubprocessBroker:
    """Subprocess execution manager for computational quantum chemistry workloads.

    Handles cross-platform process lifecycles, memory safety, heartbeats, dead-man's switch watchdogs,
    RAM-disk overlays, CPU affinity pinning, crash hex-dump telemetry, and artifact provenance hashing.
    """

    def __init__(
        self,
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        memory_limit_gb: float = 8.0,
        total_ram_threshold_gb: float = 128.0,
    ) -> None:
        env_scratch = (
            os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TMPDIR")
            or os.environ.get("TEMP")
        )
        if env_scratch:
            default_work_dir = Path(env_scratch) / "cochem_scratch"
        else:
            default_work_dir = get_artifact_dir() / "Scratch"
        self.cwd = resolve_mapped_path(cwd, default_work_dir) if cwd is not None else default_work_dir
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.env = env if env is not None else os.environ.copy()
        self.memory_limit_bytes = memory_limit_gb * (1024 ** 3)
        self.total_ram_threshold_gb = total_ram_threshold_gb

        self.topology_manager = CPUTopologyManager()
        self.ramdisk_manager = RAMDiskOverlayManager(threshold_ram_gb=total_ram_threshold_gb)

        if TelemetryLogger is not None:
            self.telemetry: Optional[Any] = TelemetryLogger()
        else:
            self.telemetry = None

        self.active_processes: List[subprocess.Popen] = []
        self._lock = threading.RLock()

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._zmq_context: Optional[Any] = None
        self._zmq_socket: Optional[Any] = None
        self._zmq_thread: Optional[threading.Thread] = None
        self._zmq_stop_event = threading.Event()

    def __enter__(self) -> SubprocessBroker:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def shutdown(self) -> None:
        """Gracefully shuts down broker threads and terminates active subprocesses."""
        self.stop_oom_monitor()
        self.stop_zmq_heartbeat()
        self.execute_zombie_reaper()

    def close(self) -> None:
        """Closes the broker, stopping monitors and cleaning up process trees."""
        self.shutdown()

    def verify_scratch_io(self, target_dir: Optional[Union[str, Path]] = None, required_mb: int = 100) -> bool:
        """Verifies scratch directory I/O readiness."""
        path = target_dir or self.cwd
        return verify_scratch_io(path, required_mb=required_mb)

    def verify_scratch_quota_and_io(self, target_dir: Optional[Union[str, Path]] = None, required_gb: float = 50.0) -> bool:
        """Verifies scratch quota and binary readback probe."""
        path = target_dir or self.cwd
        return verify_scratch_quota_and_io(path, required_gb=required_gb)

    def _allocate_scratch_space(self, job_name: str, required_mb: int = 4000) -> Path:
        """Provisions an isolated scratch directory on high-speed RAM-disk or NVMe fallback."""
        return self.ramdisk_manager.provision_overlay(
            job_name=job_name,
            required_gb=max(0.01, required_mb / 1024.0),
            min_ram_gb=self.total_ram_threshold_gb,
            fallback_dir=self.cwd,
        )

    def start_oom_monitor(self, check_interval: float = 1.0, threshold_mb: Optional[float] = None) -> None:
        """Spawns a background thread that polls RSS memory of active process trees."""
        if not HAS_PSUTIL:
            logger.warning("psutil unavailable. OOM preemption monitor disabled.")
            return

        self.stop_oom_monitor()
        self._stop_event.clear()

        limit_bytes = (threshold_mb * (1024 ** 2)) if threshold_mb is not None else self.memory_limit_bytes

        def monitor_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    with self._lock:
                        active_pids = [p.pid for p in self.active_processes if p.poll() is None]
                    if active_pids:
                        total_rss = 0
                        for pid in active_pids:
                            try:
                                proc = psutil.Process(pid)
                                total_rss += proc.memory_info().rss
                                for child in proc.children(recursive=True):
                                    total_rss += child.memory_info().rss
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        if total_rss > limit_bytes:
                            logger.error(
                                f"Broker process tree memory exceeded limit: {total_rss / 1e6:.1f} MB > "
                                f"{limit_bytes / 1e6:.1f} MB. Preempting active processes."
                            )
                            self.execute_zombie_reaper()
                except Exception as exc:
                    logger.debug(f"OOM poll error: {exc}")
                self._stop_event.wait(check_interval)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_oom_monitor(self) -> None:
        """Stops the active OOM preemption monitor thread."""
        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

    def start_zmq_heartbeat(
        self,
        port: int = 5557,
        host: str = "127.0.0.1",
        interval_sec: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Starts a background ZeroMQ PUB heartbeat publisher emitting telemetry metadata."""
        if not HAS_ZMQ:
            logger.warning("ZeroMQ (pyzmq) not available. Heartbeat publisher disabled.")
            return

        self.stop_zmq_heartbeat()
        self._zmq_stop_event.clear()

        try:
            self._zmq_context = zmq.Context()
            self._zmq_socket = self._zmq_context.socket(zmq.PUB)
            self._zmq_socket.bind(f"tcp://{host}:{port}")
        except Exception as err:
            logger.error(f"Failed to bind ZeroMQ heartbeat socket on {host}:{port}: {err}")
            self.stop_zmq_heartbeat()
            return

        def heartbeat_worker() -> None:
            while not self._zmq_stop_event.is_set():
                alive_payload: Dict[str, Any] = {
                    "status": "alive",
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                    "active_processes": len(self.active_processes),
                    "metadata": metadata or {},
                }
                try:
                    if self._zmq_socket is not None:
                        self._zmq_socket.send_multipart([
                            b"heartbeat",
                            json.dumps(alive_payload).encode("utf-8"),
                        ])
                except Exception as ex:
                    logger.debug(f"ZeroMQ heartbeat send error: {ex}")
                self._zmq_stop_event.wait(interval_sec)

        self._zmq_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self._zmq_thread.start()
        logger.info(f"ZeroMQ heartbeat publisher started on tcp://{host}:{port} [M]")

    def stop_zmq_heartbeat(self) -> None:
        """Stops the ZeroMQ heartbeat publisher and releases socket resources."""
        self._zmq_stop_event.set()
        if self._zmq_thread is not None:
            self._zmq_thread.join(timeout=2.0)
            self._zmq_thread = None
        if self._zmq_socket is not None:
            try:
                self._zmq_socket.close(linger=0)
            except Exception:
                pass
            self._zmq_socket = None
        if self._zmq_context is not None:
            try:
                self._zmq_context.term()
            except Exception:
                pass
            self._zmq_context = None

    def execute_zombie_reaper(self) -> int:
        """Terminates all managed subprocesses and their orphaned children with 10-second grace period."""
        count = 0
        with self._lock:
            procs = list(self.active_processes)
            self.active_processes.clear()

        if not procs:
            return 0

        logger.info("Executing SubprocessBroker Zombie Reaper Protocol...")
        for proc in procs:
            if proc.poll() is None:
                try:
                    pid = proc.pid
                    kill_process_tree(pid, timeout=10.0)
                    unregister_popen_process(proc)
                    count += 1
                    logger.info(f"Reaped managed process tree PID {pid}")
                except (ProcessLookupError, PermissionError, OSError) as e:
                    logger.warning(f"Reaper failed on PID {proc.pid}: {e}")
            else:
                unregister_popen_process(proc)

        return count

    def garbage_collect_core_dumps(self, execution_dir: Optional[Union[str, Path]] = None) -> int:
        """Sweeps massive binary core.* files generated by Fortran segfaults."""
        target_dir = Path(execution_dir).resolve() if execution_dir is not None else self.cwd
        count = 0
        if not target_dir.exists():
            return 0
        for file in target_dir.glob("core.*"):
            if file.is_file():
                try:
                    file.unlink()
                    count += 1
                except OSError as err:
                    logger.debug(f"Unable to unlink core file {file}: {err}")
        if count > 0:
            logger.info(f"Garbage collection swept {count} binary dump(s).")
        return count

    def hash_quantum_artifacts(self, execution_dir: Optional[Union[str, Path]] = None) -> Dict[str, str]:
        """Calculates SHA-256 cryptographic provenance digests for all quantum chemistry artifacts."""
        target_dir = Path(execution_dir).resolve() if execution_dir is not None else self.cwd
        return RAMDiskOverlayManager.hash_artifacts(target_dir)

    def extract_crash_hex_dump(
        self,
        returncode: int,
        stderr_data: Union[str, bytes, Sequence[str], None],
    ) -> Dict[str, Any]:
        """Extracts 256-byte hexadecimal crash trace for crashed subprocesses."""
        return extract_segfault_hex_dump(returncode, stderr_data)

    def execute(
        self,
        payload_command: Union[str, List[str]],
        job_name: str = "cochem_job",
        timeout: Optional[float] = None,
        cpu_affinity: Optional[List[int]] = None,
        required_disk_gb: float = 0.05,
        dead_man_timeout: float = 60.0,
        daemonize_on_timeout: bool = True,
    ) -> int:
        """Dispatches an execution payload with cross-platform isolation and crash telemetry monitoring.

        Allocates high-speed RAM-disk if available, executes payload with dead-man's switch watchdog,
        enforces timeout, streams stdout/stderr, extracts segfault hex dumps if crashed,
        and copies artifacts back upon completion.
        """
        exec_path = self._allocate_scratch_space(job_name)
        verify_scratch_quota_and_io(exec_path, required_gb=max(0.01, required_disk_gb))

        cmd_str: str
        command: Union[str, List[str]]
        if isinstance(payload_command, str):
            if platform.system() == "Windows":
                command = payload_command
            else:
                command = shlex.split(payload_command, posix=True)
            cmd_str = payload_command
        else:
            command = payload_command
            cmd_str = " ".join(payload_command)

        sanitized_env = sanitize_mpi_environment(self.env, cmd=command)

        logger.info(f"Dispatching '{job_name}' to broker in {exec_path}...")

        stdout_hist: List[str] = []
        stderr_hist: List[str] = []

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(exec_path),
            "env": sanitized_env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
        }

        process: Optional[subprocess.Popen] = None
        job_obj = WindowsJobObject() if platform.system() == "Windows" else None
        watchdog: Optional[DeadMansSwitchWatchdog] = None
        exit_code: int = 0

        try:
            process = subprocess.Popen(command, **popen_kwargs)
            with self._lock:
                self.active_processes.append(process)
            register_popen_process(process)

            if job_obj is not None:
                job_obj.assign_popen(process)

            if cpu_affinity is not None:
                enforce_cpu_affinity(process.pid, cpu_affinity)

            watchdog = DeadMansSwitchWatchdog(
                job_id=job_name,
                proc=process,
                timeout=dead_man_timeout,
                on_timeout="daemonize" if daemonize_on_timeout else "kill",
            )
            watchdog.start()

            def _stream_stdout() -> None:
                if process and process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if watchdog:
                            watchdog.ping()
                        clean_line = line.strip()
                        stdout_hist.append(clean_line)
                        if self.telemetry and not self.telemetry.process_stream_chunk(clean_line):
                            logger.error("Telemetry trap triggered. Preempting process.")
                            kill_process_tree(process.pid, timeout=10.0)
                            break

            def _stream_stderr() -> None:
                if process and process.stderr:
                    for line in iter(process.stderr.readline, ''):
                        if watchdog:
                            watchdog.ping()
                        stderr_hist.append(line.strip())

            t_stdout = threading.Thread(target=_stream_stdout, daemon=True)
            t_stderr = threading.Thread(target=_stream_stderr, daemon=True)

            t_stdout.start()
            t_stderr.start()

            if timeout is not None and timeout > 0:
                try:
                    process.wait(timeout=timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    logger.error(f"Process '{job_name}' timed out after {timeout} seconds.")
                    kill_process_tree(process.pid, timeout=10.0)
                    try:
                        process.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        pass
                    exit_code = -124
            else:
                process.wait()
                exit_code = process.returncode

            t_stdout.join(timeout=2.0)
            t_stderr.join(timeout=2.0)

            # Check for segfault / access violation crash and sweep 256-byte hex dump
            crash_info = extract_segfault_hex_dump(exit_code, stderr_hist)
            if crash_info.get("is_crash"):
                logger.error(
                    f"Process payload '{job_name}' crashed ({crash_info.get('crash_type')}, code {exit_code}):\n"
                    f"{crash_info.get('formatted_hex_dump')}"
                )

        except KeyboardInterrupt:
            logger.error("Keyboard Interrupt. Triggering Reaper.")
            self.execute_zombie_reaper()
            exit_code = -1
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            logger.error(f"Dispatch Exception: {e}")
            self.execute_zombie_reaper()
            exit_code = -2
        finally:
            if watchdog is not None:
                watchdog.stop()

            if job_obj is not None:
                if watchdog is not None and watchdog.is_daemonized:
                    job_obj.set_kill_on_close(False)
                job_obj.close()

            if process is not None:
                with self._lock:
                    if process in self.active_processes:
                        self.active_processes.remove(process)
                unregister_popen_process(process)

            # Compute cryptographic dispatch audit hash
            dispatch_seed = f"{job_name}:{cmd_str}:{exit_code}:{time.time()}".encode('utf-8')
            dispatch_hash = hashlib.sha256(dispatch_seed).hexdigest()

            if self.telemetry:
                self.telemetry.aggregate_and_lock(job_name, stdout_hist, stderr_hist, exit_code, dispatch_hash)

            if not (watchdog is not None and watchdog.is_daemonized):
                self.garbage_collect_core_dumps(exec_path)
                self.ramdisk_manager.sync_and_cleanup(exec_path, self.cwd)
            else:
                logger.info(
                    f"Job '{job_name}' daemonized (PID {process.pid if process else 'N/A'}); "
                    f"preserving execution directory {exec_path} for active background completion."
                )

        return exit_code


__all__ = [
    "SubprocessBroker",
    "safe_subprocess_run",
    "register_popen_process",
    "unregister_popen_process",
    "get_active_popen_processes",
    "cleanup_zombie_processes",
    "kill_process_tree",
    "enforce_cpu_affinity",
    "build_thread_affinity_env",
    "detect_cpu_topology",
    "CPUTopologyManager",
    "detect_mpi_environment",
    "sanitize_mpi_environment",
    "verify_scratch_io",
    "verify_scratch_quota_and_io",
    "_SCRATCH_VERIFICATION_CACHE",
    "lock_directory_permissions",
    "RAMDiskOverlayManager",
    "ZMQHeartbeatManager",
    "DeadMansSwitchWatchdog",
    "WindowsJobObject",
    "ZombieReaper",
    "DiskQuotaError",
    "extract_segfault_hex_dump",
    "sweep_crash_hex_dump",
    "is_crash_returncode",
    "CRITICAL_SEGFAULT_EXIT_CODES",
    "HAS_PSUTIL",
    "HAS_ZMQ",
]


if __name__ == "__main__":
    broker = SubprocessBroker()
    logger.info("Broker Initialized and protections armed.")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\cochem_sandbox.py ---
"""Ephemeral Sandbox Context & Path Jailbreak Defense.

Strictly adheres to:
- CoChem Anti-Spoofing Protocol v2
- Tripartite Storage Air-Gap Architecture (Tier 3 $COCH_SCRATCH isolation)
- Suggestion #68: atexit callback unregistration on context exit eliminating memory leaks.
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional, Union

from cochem_base.core.exceptions import AirGapBoundaryError

logger = logging.getLogger("cochem_sandbox")


class SandboxContext:
    """Manages ephemeral calculation workspaces adhering to Tripartite Air-Gap Domain C."""

    def __init__(
        self,
        scratch_root: Optional[Union[Path, str, Any]] = None,
        prefix: str = "cochem_job_",
    ) -> None:
        # Support SandboxConfig object if passed as first argument
        resolved_root: Optional[Path] = None
        if scratch_root is not None:
            if hasattr(scratch_root, "scratch_parent_dir") and scratch_root.scratch_parent_dir is not None:
                resolved_root = Path(scratch_root.scratch_parent_dir)
            elif isinstance(scratch_root, (str, Path)):
                resolved_root = Path(scratch_root)
        self.scratch_root: Path = self._resolve_and_validate_scratch_root(resolved_root)
        self.prefix: str = prefix
        self.path: Optional[Path] = None
        self._cleaned: bool = False

    def _resolve_and_validate_scratch_root(self, root: Optional[Path]) -> Path:
        if root is None:
            root = Path(os.environ.get("COCH_SCRATCH", os.environ.get("COCHEM_SCRATCH_DIR", "/tmp/cochem_scratch")))
        resolved = root.resolve()

        # Enforce Tripartite Air-Gap: Prohibit sandbox creation in Tier 1 ($COCH_SRC) or Tier 2 ($COCH_DATA)
        src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
        data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()
        if src_dir.exists() and (src_dir == resolved or src_dir in resolved.parents):
            raise AirGapBoundaryError(
                f"Cannot create ephemeral sandbox inside Tier 1 ($COCH_SRC): {resolved}",
                details={"attempted_path": str(resolved), "tier": "Tier 1"},
            )
        if data_dir.exists() and (data_dir == resolved or data_dir in resolved.parents):
            raise AirGapBoundaryError(
                f"Cannot create ephemeral sandbox inside Tier 2 ($COCH_DATA): {resolved}",
                details={"attempted_path": str(resolved), "tier": "Tier 2"},
            )
        return resolved

    @property
    def root(self) -> Optional[Path]:
        """Backward-compatible alias for self.path."""
        return self.path

    def __enter__(self) -> SandboxContext:
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix, dir=self.scratch_root))
        self._cleaned = False
        atexit.register(self.cleanup)
        return self

    def cleanup(self) -> None:
        """Idempotently cleans up scratch directory and removes atexit registration."""
        if self._cleaned:
            return
        self._cleaned = True
        try:
            atexit.unregister(self.cleanup)
        except Exception as exc:
            logger.debug("atexit unregister error: %s", exc)
        if self.path is not None and self.path.exists():
            try:
                shutil.rmtree(self.path, ignore_errors=True)
            except Exception as exc:
                logger.debug("shutil.rmtree error during cleanup: %s", exc)

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.cleanup()


__all__ = [
    "SandboxContext",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\mendeleev_invariants.py ---
"""Dynamic Mendeleev Invariants & Element Resolver.

Provenance & Specifications:
- Method Matrix [M]: Quantum spin-parity and IUPAC CIAAW standard atomic weight invariants.
- Dynamic Resolution [D]: Zero-hardcoding dynamic element and isotopic mass lookup via mendeleev.
- Telemetry [E]: Thread-safe in-memory cache populated dynamically on demand.
- Suggestion #67: Lazy singleton initialization eliminates 200-600 ms top-level module import lag.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from mendeleev import element as _mendeleev_element

from cochem_base.core.exceptions import CoChemError

logger = logging.getLogger("mendeleev_invariants")


class MissingDataError(CoChemError, KeyError):
    """Raised when required element, isotope, basis set, or calculation data is missing."""

    def __init__(self, message: str, symbol_or_query: Optional[Any] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_MISSING_DATA")
        self.message: str = message
        self.symbol_or_query: Optional[Any] = symbol_or_query


class MendeleevInvariantError(CoChemError, ValueError):
    """Raised when chemical element queries violate Mendeleev physical invariants."""

    def __init__(self, message: str, symbol_or_query: Optional[Any] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_MENDELEEV_INVARIANT_VIOLATION")
        self.message: str = message
        self.symbol_or_query: Optional[Any] = symbol_or_query


@dataclass(slots=True, frozen=True)
class ElementData:
    """Immutable ground-truth chemical element properties."""

    atomic_number: int
    symbol: str
    name: str
    atomic_weight: float
    isotopes: Tuple[Tuple[int, float, float], ...]  # (mass_number, exact_mass_amu, natural_abundance)
    covalent_radius_pm: Optional[float]
    vdw_radius_pm: Optional[float]
    valence_electrons: int
    mass: float = 0.0
    mass_number: Optional[int] = None
    formal_charge: int = 0
    is_isotope: bool = False


_ELEMENT_CACHE_LOCK = threading.Lock()
_ELEMENT_CACHE: Optional[Dict[int, ElementData]] = None
_ELEMENTS_BY_SYMBOL: Dict[str, ElementData] = {}


def _load_single_element(z_or_sym: Union[int, str]) -> ElementData:
    """Dynamically fetch ElementData for Z=1..118 via mendeleev."""
    try:
        elem = _mendeleev_element(z_or_sym)
    except Exception as exc:
        raise MendeleevInvariantError(
            f"Dynamic element resolution failed for query '{z_or_sym}': {exc}",
            symbol_or_query=z_or_sym,
        ) from exc

    z = int(elem.atomic_number)
    symbol = str(elem.symbol)
    name = str(elem.name)

    # Standard atomic weight with dynamic fallback to most stable isotope mass
    weight = elem.atomic_weight
    if weight is None or float(weight) <= 0.0:
        iso_masses = [iso.mass_number for iso in elem.isotopes if iso.mass_number is not None]
        if iso_masses:
            weight = float(max(iso_masses))
        else:
            weight = float(z)
    else:
        weight = float(weight)

    # Isotope tuple: (mass_number, exact_mass_amu, abundance)
    isotope_list: List[Tuple[int, float, float]] = []
    for iso in elem.isotopes:
        if iso.mass_number is not None:
            m_num = int(iso.mass_number)
            m_exact = float(iso.mass) if iso.mass is not None and float(iso.mass) > 0.0 else float(m_num)
            m_abund = float(iso.abundance) if iso.abundance is not None else 0.0
            isotope_list.append((m_num, m_exact, m_abund))
    isotopes_tuple = tuple(sorted(isotope_list, key=lambda x: x[0]))

    cov_r = elem.covalent_radius_pyykko or elem.covalent_radius
    cov_radius_pm = float(cov_r) if cov_r is not None else None

    vdw_r = elem.vdw_radius or elem.vdw_radius_alvarez or elem.vdw_radius_bondi or elem.vdw_radius_batsanov
    vdw_radius_pm = float(vdw_r) if vdw_r is not None else None

    if hasattr(elem, "nvalence") and callable(elem.nvalence):
        val_e = int(elem.nvalence())
    elif elem.electrons is not None:
        val_e = int(elem.electrons)
    else:
        val_e = 0

    return ElementData(
        atomic_number=z,
        symbol=symbol,
        name=name,
        atomic_weight=weight,
        isotopes=isotopes_tuple,
        covalent_radius_pm=cov_radius_pm,
        vdw_radius_pm=vdw_radius_pm,
        valence_electrons=val_e,
        mass=weight,
        mass_number=None,
        formal_charge=0,
        is_isotope=False,
    )


def _build_element_cache() -> Dict[int, ElementData]:
    """Dynamically populates in-memory dictionary of ElementData for Z=1..118."""
    cache: Dict[int, ElementData] = {}
    for z in range(1, 119):
        data = _load_single_element(z)
        cache[z] = data
        _ELEMENTS_BY_SYMBOL[data.symbol.upper()] = data
    return cache


def get_element_cache() -> Dict[int, ElementData]:
    """Lazy thread-safe accessor for the 118-element Mendeleev invariants cache.

    Eliminates 200-600 ms top-level module import overhead across spawned worker processes [M].
    """
    global _ELEMENT_CACHE
    if _ELEMENT_CACHE is None:
        with _ELEMENT_CACHE_LOCK:
            if _ELEMENT_CACHE is None:
                _ELEMENT_CACHE = _build_element_cache()
    return _ELEMENT_CACHE


def get_element_data(z: int) -> ElementData:
    """Retrieve ElementData by atomic number."""
    cache = get_element_cache()
    if z not in cache:
        raise MendeleevInvariantError(f"Invalid atomic number Z={z}. Must be between 1 and 118.", symbol_or_query=z)
    return cache[z]


def get_symbol(z: int) -> str:
    """Retrieve chemical symbol by atomic number."""
    return get_element_data(z).symbol


def get_atomic_number(symbol: str) -> int:
    """Retrieve atomic number by chemical symbol."""
    cache = get_element_cache()
    clean = str(symbol).strip().upper()
    if clean in _ELEMENTS_BY_SYMBOL:
        return _ELEMENTS_BY_SYMBOL[clean].atomic_number
    for el in cache.values():
        if el.symbol.upper() == clean:
            return el.atomic_number
    raise MissingDataError(f"Unresolvable atomic element symbol: {symbol}", symbol_or_query=symbol)


def parse_symbol_or_isotope(symbol: str) -> Tuple[str, Optional[int]]:
    """Authoritative regex and alias pre-processor for chemical symbols and isotopes.

    Maps:
    - 'D' -> ('H', 2)
    - 'T' -> ('H', 3)
    - '13C' -> ('C', 13)
    - '18O' -> ('O', 18)
    - '2H' -> ('H', 2)
    - Standard symbols ('H', 'C', 'Ar') -> ('H', None), etc.
    """
    raw = str(symbol).strip()
    if not raw or raw.isdigit():
        raise MissingDataError(
            f"Invalid chemical symbol or isotope '{symbol}'. Symbol cannot be empty or purely numeric.",
            symbol_or_query=symbol,
        )

    if raw.upper() == "D":
        return "H", 2
    if raw.upper() == "T":
        return "H", 3

    m_iso = re.match(r"^(\d+)([A-Za-z]+)$", raw)
    if m_iso:
        mass_num = int(m_iso.group(1))
        sym_part = m_iso.group(2)
        norm_sym = sym_part[0].upper() + sym_part[1:].lower() if len(sym_part) > 1 else sym_part.upper()
        try:
            get_element(norm_sym)
        except Exception:
            raise MissingDataError(
                f"Unresolvable atomic element or isotope symbol: {symbol}",
                symbol_or_query=symbol,
            )
        return norm_sym, mass_num

    m_sym = re.match(r"^[A-Za-z]+$", raw)
    if m_sym:
        norm_sym = raw[0].upper() + raw[1:].lower() if len(raw) > 1 else raw.upper()
        try:
            elem_data = get_element(norm_sym)
            return elem_data.symbol, None
        except Exception as exc:
            logger.debug("Symbol parse lookup fallback: %s", exc)

    raise MissingDataError(
        f"Unresolvable atomic element or isotope symbol: {symbol}",
        symbol_or_query=symbol,
    )


def get_element(symbol_or_z: Union[str, int]) -> ElementData:
    """Retrieve immutable ElementData by atomic number, chemical symbol, formal charge, or isotope."""
    cache = get_element_cache()

    if isinstance(symbol_or_z, int):
        if symbol_or_z < 1 or symbol_or_z > 118:
            raise MendeleevInvariantError(
                f"Invalid atomic number Z={symbol_or_z}. Must be between 1 and 118.",
                symbol_or_query=symbol_or_z,
            )
        return cache[symbol_or_z]

    raw = str(symbol_or_z).strip()
    if not raw or raw.isdigit():
        raise MendeleevInvariantError(
            f"Invalid chemical symbol '{symbol_or_z}'. Symbol cannot be empty or purely numeric.",
            symbol_or_query=symbol_or_z,
        )

    pattern = re.compile(r"^(?P<isotope>\d+)?(?P<symbol>[A-Za-z]+)(?P<charge>(?:\d+[+-]|[+-]\d*|[+-]))?$")
    match = pattern.match(raw)
    if not match:
        raise MendeleevInvariantError(
            f"Dynamic element resolution failed for query '{symbol_or_z}'.",
            symbol_or_query=symbol_or_z,
        )

    iso_str = match.group("isotope")
    sym_raw = match.group("symbol")
    charge_str = match.group("charge")

    if sym_raw.upper() == "D":
        norm_sym = "H"
        mass_number: Optional[int] = 2
    elif sym_raw.upper() == "T":
        norm_sym = "H"
        mass_number = 3
    else:
        norm_sym = sym_raw[0].upper() + sym_raw[1:].lower() if len(sym_raw) > 1 else sym_raw.upper()
        mass_number = int(iso_str) if iso_str else None

    formal_charge: int = 0
    if charge_str:
        if charge_str.endswith("+"):
            val = charge_str[:-1]
            formal_charge = int(val) if val else 1
        elif charge_str.endswith("-"):
            val = charge_str[:-1]
            formal_charge = -int(val) if val else -1
        elif charge_str.startswith("+"):
            val = charge_str[1:]
            formal_charge = int(val) if val else 1
        elif charge_str.startswith("-"):
            val = charge_str[1:]
            formal_charge = -int(val) if val else -1

    base_data: Optional[ElementData] = None
    clean_key = norm_sym.upper()
    if clean_key in _ELEMENTS_BY_SYMBOL:
        base_data = _ELEMENTS_BY_SYMBOL[clean_key]
    else:
        for el in cache.values():
            if el.symbol.upper() == clean_key or el.name.lower() == sym_raw.lower():
                base_data = el
                break

    if base_data is None:
        raise MendeleevInvariantError(
            f"Dynamic element resolution failed for query '{symbol_or_z}': element '{norm_sym}' not found.",
            symbol_or_query=symbol_or_z,
        )

    if mass_number is not None:
        is_isotope = True
        elem = _mendeleev_element(base_data.atomic_number)
        iso = next((i for i in elem.isotopes if i.mass_number == mass_number), None)
        if iso is None or iso.mass is None or float(iso.mass) <= 0.0:
            raise MendeleevInvariantError(
                f"No isotope with mass number A={mass_number} found for element '{norm_sym}'.",
                symbol_or_query=symbol_or_z,
            )
        mass = float(iso.mass)
    else:
        is_isotope = False
        mass = float(base_data.atomic_weight)

    return ElementData(
        atomic_number=base_data.atomic_number,
        symbol=base_data.symbol,
        name=base_data.name,
        atomic_weight=base_data.atomic_weight,
        isotopes=base_data.isotopes,
        covalent_radius_pm=base_data.covalent_radius_pm,
        vdw_radius_pm=base_data.vdw_radius_pm,
        valence_electrons=base_data.valence_electrons,
        mass=mass,
        mass_number=mass_number,
        formal_charge=formal_charge,
        is_isotope=is_isotope,
    )


def get_isotope_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Dynamically resolve IUPAC exact isotopic mass in unified atomic mass units (u)."""
    element_data = get_element(symbol_or_z)
    for iso_m_num, iso_exact, _ in element_data.isotopes:
        if iso_m_num == mass_number:
            return iso_exact

    try:
        m_elem = _mendeleev_element(element_data.symbol)
        for iso in m_elem.isotopes:
            if iso.mass_number == mass_number and iso.mass is not None:
                return float(iso.mass)
    except Exception as exc:
        logger.debug("Isotope fallback resolution error: %s", exc)

    raise MendeleevInvariantError(
        f"No isotope with mass number A={mass_number} found for element '{element_data.symbol}'.",
        symbol_or_query=f"{element_data.symbol}-{mass_number}",
    )


def get_element_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically resolve atomic or isotopic mass in unified atomic mass units (u)."""
    if isinstance(symbol_or_z, int):
        return get_element(symbol_or_z).atomic_weight

    clean_sym, mass_number = parse_symbol_or_isotope(symbol_or_z)
    if mass_number is not None:
        return get_isotope_mass(clean_sym, mass_number)
    return get_element(clean_sym).atomic_weight


class MendeleevResolver:
    """Thread-safe dynamic Mendeleev element and isotope mass resolver for backward compatibility."""

    def get_element(self, symbol_or_z: Union[str, int]) -> Any:
        elem_data = get_element(symbol_or_z)
        return _mendeleev_element(elem_data.atomic_number)

    def get_atomic_number(self, symbol_or_z: Union[str, int]) -> int:
        return get_element(symbol_or_z).atomic_number

    def get_atomic_weight(self, symbol_or_z: Union[str, int]) -> float:
        return get_element(symbol_or_z).atomic_weight

    def get_element_mass(self, symbol_or_z: Union[str, int]) -> float:
        return get_element_mass(symbol_or_z)

    def get_symbol(self, symbol_or_z: Union[str, int]) -> str:
        return get_element(symbol_or_z).symbol

    def get_name(self, symbol_or_z: Union[str, int]) -> str:
        return get_element(symbol_or_z).name

    def get_covalent_radius(self, symbol_or_z: Union[str, int]) -> Optional[float]:
        return get_element(symbol_or_z).covalent_radius_pm

    def get_vdw_radius(self, symbol_or_z: Union[str, int]) -> float:
        r = get_element(symbol_or_z).vdw_radius_pm
        if r is None:
            raise MissingDataError(f"Van der Waals radius is not available for element '{symbol_or_z}'.")
        return r

    def get_vdw_radius_angstrom(self, symbol_or_z: Union[str, int]) -> float:
        return self.get_vdw_radius(symbol_or_z) / 100.0

    def get_isotope_mass(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        return get_isotope_mass(symbol_or_z, mass_number)

    def get_isotope_abundance(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        elem_data = get_element(symbol_or_z)
        for m_num, _, abund in elem_data.isotopes:
            if m_num == mass_number:
                return abund
        return 0.0

    def get_available_isotopes(self, symbol_or_z: Union[str, int]) -> List[int]:
        return [m_num for m_num, _, _ in get_element(symbol_or_z).isotopes]

    def clear_cache(self) -> None:
        raise MissingDataError("Mendeleev element cache is immutable and cannot be cleared.")


mendeleev_resolver = MendeleevResolver()

__all__ = [
    "ElementData",
    "MendeleevInvariantError",
    "MissingDataError",
    "get_element_cache",
    "get_element",
    "get_element_data",
    "get_symbol",
    "get_atomic_number",
    "get_isotope_mass",
    "get_element_mass",
    "parse_symbol_or_isotope",
    "MendeleevResolver",
    "mendeleev_resolver",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core\process_reaper.py ---
"""Cross-platform process lifecycle manager and direct PID monitoring reaper.

Complies with:
- Method Matrix [M]: Low-overhead targeted telemetry and reaping of QM/MM worker subprocesses.
- Suggestion #69: Direct child PID monitoring in ProcessTreeManager dropping CPU usage by >80%.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Union

import psutil

from cochem_base.core.exceptions import ProcessReaperError

logger = logging.getLogger("CoChem-ProcessReaper")


class ProcessTreeManager:
    """Manages process hierarchies with direct child PID tracking to eliminate full-OS scans."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tracked: Set[int] = set()
        try:
            self._parent_proc: psutil.Process = psutil.Process()
        except Exception:
            self._parent_proc = None  # type: ignore

    def register_process(
        self,
        proc: Union[psutil.Process, int],
        task_id: Optional[str] = None,
    ) -> None:
        """Explicitly registers a newly spawned subprocess PID for targeted telemetry and reaping."""
        pid = proc.pid if isinstance(proc, psutil.Process) else int(proc)
        if pid > 0:
            with self._lock:
                self._tracked.add(pid)

    def unregister_process(self, pid: int) -> None:
        """Removes a process PID upon normal exit."""
        with self._lock:
            self._tracked.discard(pid)

    def is_alive(self, pid: int) -> bool:
        """Check if process exists and is running."""
        try:
            p = psutil.Process(pid)
            return bool(p.is_running() and p.status() != psutil.STATUS_ZOMBIE)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def get_tracked_pids(self) -> List[int]:
        """Return snapshot of tracked PIDs."""
        with self._lock:
            return list(self._tracked)

    def sample_process_tree_rss_bytes(self) -> int:
        """Samples memory consumption across tracked PIDs directly without traversing the full OS process table.

        Drops monitoring daemon CPU consumption by >80% [E] and preserves scout-and-anchor thread budgets.
        """
        total_rss = 0
        dead_pids: Set[int] = set()

        # Include parent process
        if self._parent_proc is not None:
            try:
                total_rss += self._parent_proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("Parent process memory sampling error: %s", exc)

        # Query tracked child PIDs directly
        with self._lock:
            current_pids = list(self._tracked)

        for pid in current_pids:
            try:
                p = psutil.Process(pid)
                total_rss += p.memory_info().rss
            except psutil.NoSuchProcess:
                dead_pids.add(pid)
            except (psutil.AccessDenied, psutil.ZombieProcess) as exc:
                logger.debug("Child PID %d memory sampling error: %s", pid, exc)

        with self._lock:
            self._tracked.difference_update(dead_pids)

        return total_rss

    def terminate_tree(
        self,
        pid: Optional[int] = None,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        """Directly signals tracked PIDs with SIGTERM (or terminate), waits up to timeout, and escalates to SIGKILL."""
        with self._lock:
            if pid is not None:
                pids_to_kill = [pid]
            else:
                pids_to_kill = list(self._tracked)

        procs: List[psutil.Process] = []
        for p_id in pids_to_kill:
            try:
                procs.append(psutil.Process(p_id))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                with self._lock:
                    self._tracked.discard(p_id)

        # Signal termination
        for p in procs:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("Process %d terminate error: %s", p.pid, exc)

        # Await graceful termination
        gone, alive = psutil.wait_procs(procs, timeout=timeout)

        # Escalate to kill for remaining stubborn processes
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("Process %d kill error: %s", p.pid, exc)

        with self._lock:
            if pid is not None:
                self._tracked.discard(pid)
            else:
                self._tracked.clear()

        return {
            "terminated_count": len(gone) + len(alive),
            "surviving_count": 0,
        }


__all__ = [
    "ProcessTreeManager",
    "ProcessReaperError",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_base\core_engine\cochem_mass_resolver.py ---
"""Authoritative Dynamic Mendeleev Mass Resolver with LRU In-Memory Caching.

Complies strictly with:
- Method Matrix v4 §8A.4: Precomputation of masses on CPU before CUDA kernels without GPU context stalls.
- Dynamic Mendeleev Invariant Mandate: Dynamic atomic and isotopic mass retrieval using `mendeleev`.
- Zero-Mock Anti-Spoofing Protocol: Authentic physical mass resolution.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional, Union

import mendeleev
from cochem_base.core.exceptions import CoChemError, IsotopeMassResolutionError


@lru_cache(maxsize=256)
def get_dynamic_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Returns standard atomic weight from Mendeleev with LRU memory caching.

    Reduces latency from ~100 us (SQLite I/O) to ~50 ns (in-memory lookup) [M].
    """
    try:
        el = mendeleev.element(symbol_or_z)
    except Exception as exc:
        raise IsotopeMassResolutionError(
            f"Element '{symbol_or_z}' cannot be resolved via Mendeleev: {exc}",
            details={"element": symbol_or_z},
        ) from exc

    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.mass is not None:
        return float(el.mass)
    raise IsotopeMassResolutionError(
        f"Atomic weight unavailable for element '{symbol_or_z}'.",
        details={"element": symbol_or_z},
    )


@lru_cache(maxsize=256)
def get_dynamic_isotopic_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Returns exact physical isotopic nuclear mass from Mendeleev with LRU memory caching.

    Guarantees zero fallback to terrestrial average atomic weights.
    """
    try:
        el = mendeleev.element(symbol_or_z)
    except Exception as exc:
        raise IsotopeMassResolutionError(
            f"Element '{symbol_or_z}' cannot be resolved via Mendeleev: {exc}",
            details={"element": symbol_or_z, "mass_number": mass_number},
        ) from exc

    for iso in el.isotopes:
        if iso.mass_number == int(mass_number):
            if iso.mass is not None and float(iso.mass) > 0.0:
                return float(iso.mass)
    raise IsotopeMassResolutionError(
        f"Isotope '{el.symbol}-{mass_number}' cannot be resolved to a physical mass.",
        details={"element": el.symbol, "mass_number": mass_number},
    )


__all__ = [
    "get_dynamic_atomic_mass",
    "get_dynamic_isotopic_mass",
    "IsotopeMassResolutionError",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\core\test_architecture_part7.py ---
"""Tests for architecture - Part 7 (Suggestions #65, #67, #68, #69, #70)."""

import math
import os
import time
import atexit
import threading
import tempfile
from pathlib import Path
import pytest
import h5py
from cochem_base.core.exceptions import AirGapBoundaryError
from cochem_base.core.mendeleev_invariants import get_element_cache
from cochem_base.core.cochem_sandbox import SandboxContext
from cochem_base.core.process_reaper import ProcessTreeManager
from cochem_base.core_engine.cochem_core_subprocess_broker import (
    verify_scratch_quota_and_io,
    _SCRATCH_VERIFICATION_CACHE,
)


def test_hdf5_swmr_inplace_resizing_and_airgap(tmp_path):
    """Validates Suggestion #65: In-place HDF5 SWMR chunk resizing and Air-Gap enforcement."""
    # Configure test environment
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    os.environ["COCH_SRC"] = str(src_dir)

    # Attempting to write into Tier 1 ($COCH_SRC) must raise AirGapBoundaryError
    h5_src_path = src_dir / "store.h5"
    with pytest.raises(AirGapBoundaryError) as exc_info:
        from cochem_base.core.ipc.serializer import validate_airgap_write_path
        validate_airgap_write_path(h5_src_path)
    assert exc_info.value.error_code == "COCHEM_E_AIRGAP_BREACH"

    # Valid write into temporary scratch
    h5_scratch_path = tmp_path / "scratch" / "store.h5"
    h5_scratch_path.parent.mkdir()

    # Create SWMR dataset
    with h5py.File(h5_scratch_path, "w", libver="latest") as f:
        ds = f.create_dataset(
            "energies",
            shape=(1,),
            maxshape=(None,),
            chunks=(512,),
            dtype="float64",
            compression="gzip",
        )
        ds[0] = -76.432

    # In-place chunk resizing
    with h5py.File(h5_scratch_path, "a", libver="latest") as f:
        ds = f["energies"]
        new_len = ds.shape[0] + 1
        ds.resize((new_len,))
        ds[new_len - 1] = -76.435
        ds.flush()

    # Verify length without whole-file copying
    with h5py.File(h5_scratch_path, "r") as f:
        assert f["energies"].shape[0] == 2
        assert math.isclose(f["energies"][1], -76.435)


def test_mendeleev_invariants_lazy_singleton_startup():
    """Validates Suggestion #67: Lazy singleton initialization eliminates top-level import lag."""
    # Ensure cache function returns valid mapping from Z=1 to Z=118
    cache = get_element_cache()
    assert len(cache) >= 118
    assert cache[1].symbol == "H"
    assert cache[6].symbol == "C"


def test_sandbox_context_atexit_unregister_and_airgap(tmp_path):
    """Validates Suggestion #68: atexit callback unregistration on context exit."""
    # Air-gap boundary assertion: attempting to allocate sandbox inside Tier 1 ($COCH_SRC) must fail
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    os.environ["COCH_SRC"] = str(src_dir)
    with pytest.raises(AirGapBoundaryError) as exc_info:
        SandboxContext(scratch_root=src_dir)
    assert exc_info.value.error_code == "COCHEM_E_AIRGAP_BREACH"

    scratch_dir = tmp_path / "scratch"
    os.environ["COCH_SCRATCH"] = str(scratch_dir)

    with SandboxContext(scratch_root=scratch_dir) as sb:
        assert sb.path.exists()

    # Path must be unlinked and cleaned
    assert not sb.path.exists()

    # Cleaned flag must be set
    assert sb._cleaned is True


def test_process_reaper_direct_pid_monitoring():
    """Validates Suggestion #69: Direct child PID tracking in ProcessTreeManager."""
    manager = ProcessTreeManager()

    # Spawn child process
    import subprocess
    import sys
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    manager.register_process(proc.pid)

    assert proc.pid in manager._tracked
    rss = manager.sample_process_tree_rss_bytes()
    assert rss > 0

    # Terminate tracked process
    manager.terminate_tree()
    proc.wait()
    assert not proc.poll() is None


def test_subprocess_broker_scratch_verification_cache(tmp_path):
    """Validates Suggestion #70: Scratch verification caching with TTL."""
    scratch_dir = tmp_path / "scratch_io"
    scratch_dir.mkdir()
    _SCRATCH_VERIFICATION_CACHE.clear()

    # First call must perform physical write probe
    t0 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t1 = time.perf_counter()
    initial_duration = t1 - t0

    # Second call within TTL must hit cache and return immediately (< 2 ms)
    t2 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t3 = time.perf_counter()
    cached_duration = t3 - t2

    assert cached_duration < 0.002
    assert cached_duration < initial_duration

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\core\test_physics_integrity_part7.py ---
"""Tests for physics integrity - Part 7 (Suggestions #61, #62, #63, #64, #66)."""

import math
import os
import time
import pytest
from pydantic import ValidationError
from cochem_base.core.models import (
    MolecularTopology,
    CURRENT_CORE_SCHEMA_VERSION,
    register_migration,
    migrate_payload,
)
from cochem_base.core.exceptions import (
    CoChemError,
    CoordinateShapeError,
    SchemaMigrationError,
    AirGapBoundaryError,
)
from cochem_base.core.cochem_crypto import (
    format_rfc8785_float,
    canonicalize_json,
)
from cochem_base.core.cochem_provenance import (
    compute_boltzmann_weights,
    ThermodynamicsProvenance,
    DAGNode,
)
from cochem_base.core_engine.cochem_mass_resolver import (
    get_dynamic_atomic_mass,
    get_dynamic_isotopic_mass,
    IsotopeMassResolutionError,
)


def test_pydantic_model_schema_version_and_migration():
    """Validates Suggestion #61: schema_version injection and automated backward-compatible migration."""
    # Test current model instantiation
    top = MolecularTopology(
        symbols=["H", "H"],
        coordinates=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
        molecular_charge=0,
        spin_multiplicity=1,
    )
    assert top.schema_version == CURRENT_CORE_SCHEMA_VERSION

    # Register legacy migration from v0 to v1
    @register_migration("MolecularTopology", 0)
    def migrate_v0_to_v1(data):
        d = dict(data)
        d["schema_version"] = 1
        if "spin_multiplicity" not in d:
            d["spin_multiplicity"] = 1
        return d

    legacy_payload = {
        "schema_version": 0,
        "symbols": ["O", "H", "H"],
        "coordinates": [[0.0, 0.0, 0.0], [0.0, 0.75, 0.5], [0.0, -0.75, 0.5]],
        "molecular_charge": 0,
    }
    migrated_top = MolecularTopology.from_archival_dict(legacy_payload)
    assert migrated_top.schema_version == 1
    assert migrated_top.spin_multiplicity == 1


def test_rfc8785_ieee754_canonical_float_formatting():
    """Validates Suggestion #62: ECMAScript IEEE 754 float formatting parity in canonicalize_json."""
    # Signed zero formatting
    assert format_rfc8785_float(0.0) == "0"
    assert format_rfc8785_float(-0.0) == "0"

    # Disallow NaN and Infinity
    with pytest.raises(ValueError):
        format_rfc8785_float(float("nan"))
    with pytest.raises(ValueError):
        format_rfc8785_float(float("inf"))

    # Exponential notation without leading zero in exponent
    assert format_rfc8785_float(1e-5) == "0.00001" or format_rfc8785_float(1e-5) == "1e-5"
    assert format_rfc8785_float(1e-7) == "1e-7"
    assert format_rfc8785_float(1e21) == "1e+21"

    # Canonicalize dictionary with sorted keys and floats
    payload = {"b": 1e-7, "a": -0.0, "c": [1, 2.5]}
    canonical_bytes = canonicalize_json(payload)
    # Keys must be sorted 'a', 'b', 'c', -0.0 as 0, 1e-7 without leading zero
    assert canonical_bytes == b'{"a":0,"b":1e-7,"c":[1,2.5]}'


def test_quasi_rrho_thermodynamics_provenance_logging():
    """Validates Suggestion #63: Quasi-harmonic thermodynamic parameter provenance logging."""
    node = DAGNode(node_id="act-opt-001", node_type="activity")
    energies = [0.0, 0.5, 1.2]
    weights, prov = compute_boltzmann_weights(
        energies,
        temperature_k=298.15,
        low_freq_cutoff_cm1=100.0,
        damping_model="grimme_quasi_rrho",
        dag_node=node,
    )
    assert len(weights) == 3
    assert math.isclose(sum(weights), 1.0, rel_tol=1e-6)
    assert "thermodynamics_provenance" in node.payload
    logged = node.payload["thermodynamics_provenance"]
    assert logged["damping_model"] == "grimme_quasi_rrho"
    assert logged["low_freq_cutoff_cm1"] == 100.0
    assert logged["temperature_k"] == 298.15
    assert logged["provenance_tag"] == "[D]"


def test_machine_actionable_exception_hierarchy():
    """Validates Suggestion #64: Structured exception hierarchy with machine-actionable error codes."""
    # Coordinate shape mismatch raises CoordinateShapeError
    with pytest.raises(CoordinateShapeError) as exc_info:
        MolecularTopology(
            symbols=["H"],
            coordinates=[[0.0, 0.0]],  # 2D instead of 3D
            molecular_charge=0,
            spin_multiplicity=1,
        )
    err = exc_info.value
    assert err.error_code == "COCHEM_E_INVALID_COORD_SHAPE"
    assert err.details["actual_len"] == 2
    assert err.details["expected_len"] == 3


def test_dynamic_mendeleev_mass_resolution_lru_cache():
    """Validates Suggestion #66: LRU memory caching on dynamic Mendeleev mass resolution."""
    # Warmup
    mass_c = get_dynamic_atomic_mass("C")
    assert math.isclose(mass_c, 12.011, rel_tol=1e-2)

    # Measure lookup latency for cached access
    start = time.perf_counter()
    for _ in range(1000):
        _ = get_dynamic_atomic_mass("C")
    cached_duration = time.perf_counter() - start

    # 1000 lookups should complete in less than 5 milliseconds
    assert cached_duration < 0.005

    # Nuclear isotopic masses
    mass_14c = get_dynamic_isotopic_mass("C", 14)
    assert math.isclose(mass_14c, 14.003241, rel_tol=1e-4)

    with pytest.raises(IsotopeMassResolutionError):
        get_dynamic_isotopic_mass("C", 999)

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.